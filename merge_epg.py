# NOTE: This script requires the 'lxml' and 'requests' libraries. 
# Install them using: pip install lxml requests
import requests
import gzip
from lxml import etree 
from io import BytesIO
from urllib.parse import urljoin
import re 
import sys 

# --- Configuration ---
BASE_URL = "https://epgshare01.online/epgshare01/"

# EPG source keys to find in the main directory
EPG_KEYS_TO_FIND = [
    "UK", "US2", "NZ", "DUMMY_CHANNELS", "ID", "MY",
    "US_SPORTS", "AU", "CA", "SG", "HK","PEACOCK"
]

# Static URLs to always include
EXTRA_STATIC_URLS = [
    "https://github.com/matthuisman/i.mjh.nz/raw/master/SamsungTVPlus/gb.xml.gz",
    "https://github.com/matthuisman/i.mjh.nz/raw/master/DStv/za.xml.gz",
    "https://github.com/matthuisman/i.mjh.nz/raw/master/PlutoTV/gb.xml.gz"
]

HEADERS = {"User-Agent": "EPG-Merger-Dynamic-Reduced/2.0"}
TIMEOUT = 60
# ---------------------

def optimize_timestamps(root: etree.Element):
    """
    Strips timezone offsets and extra space from timestamps to save space.
    """
    print("Applying timestamp optimization (stripping offsets)...")
    for programme in root.iter('programme'):
        for attr in ['start', 'stop']:
            time_val = programme.get(attr)
            if time_val and " " in time_val:
                # Truncates '20260309140000 +0000' to '20260309140000'
                programme.set(attr, time_val.split(' ')[0])

def optimize_epg_content(root: etree.Element):
    """
    Aggressively removes ALL tags except <title> for programmes 
    and <display-name> for channels.
    """
    print("Applying ULTRA-AGGRESSIVE content optimization...")
    
    # 1. Clean Channels (Keep only name)
    for channel in root.xpath('//channel'):
        for child in list(channel):
            if child.tag != 'display-name':
                channel.remove(child)

    # 2. Clean Programmes (Keep only title)
    for programme in root.xpath('//programme'):
        # Strip every child element that isn't the title
        for child in list(programme):
            if child.tag != 'title':
                programme.remove(child)
        
        # Normalize whitespace in titles to save a few extra bytes
        title_elem = programme.find('title')
        if title_elem is not None and title_elem.text:
            title_elem.text = " ".join(title_elem.text.split()).strip()

def get_latest_epg_urls():
    """Scrapes the index to find latest EPG files."""
    print(f"Scraping index from {BASE_URL}...")
    try:
        r = requests.get(BASE_URL, timeout=TIMEOUT, headers=HEADERS)
        r.raise_for_status()
        html_content = r.text
    except Exception as e:
        print(f"❌ Failed to download directory index: {e}")
        return []
    
    file_link_pattern = re.compile(r'<a href="(epg_ripper_.*?\.xml\.gz)">')
    all_xml_filenames = file_link_pattern.findall(html_content)
    
    filename_parser_pattern = re.compile(r'^epg_ripper_([A-Z_]+?)(\d*)\.xml\.gz$')
    found_epgs = {}

    for filename in all_xml_filenames:
        match = filename_parser_pattern.match(filename)
        if match:
            base_key = match.group(1) 
            version = int(match.group(2) or 0)
            if base_key not in found_epgs or version > found_epgs[base_key]['version']:
                found_epgs[base_key] = {'version': version, 'filename': filename}

    resolved_urls = []
    for key in EPG_KEYS_TO_FIND:
        if key in found_epgs:
            resolved_urls.append(urljoin(BASE_URL, found_epgs[key]['filename']))
    return resolved_urls

def main():
    dynamic_urls = get_latest_epg_urls()
    all_epg_urls = dynamic_urls + EXTRA_STATIC_URLS

    if not all_epg_urls:
        print("\n❌ No EPG URLs found. Exiting.")
        return

    root = etree.Element("tv")
    
    for url in all_epg_urls:
        print(f"Downloading {url.split('/')[-1]}...")
        try:
            r = requests.get(url, timeout=TIMEOUT, headers=HEADERS)
            r.raise_for_status()
            with gzip.GzipFile(fileobj=BytesIO(r.content)) as gz:
                epg_tree = etree.fromstring(gz.read())
                for child in epg_tree:
                    root.append(child)
                epg_tree.clear() # Clear memory
        except Exception as e:
            print(f"  ❌ Failed: {e}")

    # Apply optimizations back-to-back
    optimize_epg_content(root)
    optimize_timestamps(root) 

    # Serialize with no pretty print to ensure minimum size
    xml_bytes = etree.tostring(
        root, 
        pretty_print=False, 
        xml_declaration=True,
        encoding='utf-8'
    )
    
    print("\nWriting final REDUCED EPG files...")
    
    # Write Uncompressed
    output_xml_path = "combined_epg_reduced.xml"
    try:
        with open(output_xml_path, "wb") as f:
            f.write(xml_bytes)
        print(f"  ✅ Saved {output_xml_path} ({len(xml_bytes)/(1024*1024):.2f} MB)")
    except Exception as e:
        print(f"  ❌ Failed to write XML: {e}")

    # Write Compressed
    output_gz_path = "combined_epg.xml.gz"
    try:
        with gzip.open(output_gz_path, "wb", compresslevel=9) as f:
            f.write(xml_bytes)
        print(f"  ✅ Saved {output_gz_path}")
    except Exception as e:
        print(f"  ❌ Failed to write GZ: {e}")
        
    print("\nWorkflow complete.")

if __name__ == "__main__":
    main()
