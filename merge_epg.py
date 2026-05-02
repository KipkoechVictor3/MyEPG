import requests
import gzip
from lxml import etree 
from io import BytesIO
from urllib.parse import urljoin
import re 
import sys 

# --- Configuration ---
BASE_URL = "https://epgshare01.online/epgshare01/"

EPG_KEYS_TO_FIND = [
    "UK", "US2", "NZ", "DUMMY_CHANNELS", "ID", "MY",
    "US_SPORTS", "US_LOCALS1", "AU", "CA", "SG", "HK", "PEACOCK"
]

EXTRA_STATIC_URLS = [
    "https://github.com/matthuisman/i.mjh.nz/raw/master/SamsungTVPlus/gb.xml.gz",
    "https://github.com/matthuisman/i.mjh.nz/raw/master/DStv/za.xml.gz",
]

HEADERS = {"User-Agent": "EPG-Merger-Universal/3.1"}
TIMEOUT = 60
# ---------------------

def fix_and_optimize_timestamps(root: etree.Element):
    """
    Standardizes timestamps to YYYYMMDDHHMMSS +0000.
    iMPlayer requires the offset (+0000) to parse correctly.
    """
    print("Standardizing timestamps for iMPlayer compatibility...")
    for programme in root.iter('programme'):
        for attr in ['start', 'stop']:
            time_val = programme.get(attr)
            if time_val:
                # Extract first 14 digits and force +0000 offset
                clean_time = re.sub(r'\D', '', time_val)[:14]
                programme.set(attr, f"{clean_time} +0000")

def optimize_epg_content(root: etree.Element):
    """
    Aggressive tag removal for file reduction and LIVE event capitalization.
    """
    print("Applying content optimization and LIVE event formatting...")
    # 1. Clean Channels (Keep display-name)
    for channel in root.xpath('//channel'):
        for child in list(channel):
            if child.tag != 'display-name':
                channel.remove(child)

    # 2. Clean Programmes (Keep only title and apply CAPS to Live events)
    for programme in root.xpath('//programme'):
        for child in list(programme):
            if child.tag != 'title':
                programme.remove(child)
        
        title_elem = programme.find('title')
        if title_elem is not None and title_elem.text:
            # Clean whitespace
            text = " ".join(title_elem.text.split()).strip()
            
            # Check if 'live' is in the title (case insensitive)
            if "live" in text.lower():
                text = text.upper()
            
            title_elem.text = text

def get_latest_epg_urls():
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

    return [urljoin(BASE_URL, found_epgs[k]['filename']) for k in EPG_KEYS_TO_FIND if k in found_epgs]

def main():
    dynamic_urls = get_latest_epg_urls()
    all_epg_urls = dynamic_urls + EXTRA_STATIC_URLS

    if not all_epg_urls:
        print("\n❌ No URLs found.")
        return

    root = etree.Element("tv", {
        "generator-info-name": "EPG-Reducer-V3.1",
        "generator-info-url": "https://github.com"
    })
    
    for url in all_epg_urls:
        print(f"Downloading {url.split('/')[-1]}...")
        try:
            r = requests.get(url, timeout=TIMEOUT, headers=HEADERS)
            r.raise_for_status()
            with gzip.GzipFile(fileobj=BytesIO(r.content)) as gz:
                epg_tree = etree.fromstring(gz.read())
                for child in epg_tree:
                    root.append(child)
                epg_tree.clear()
        except Exception as e:
            print(f"  ❌ Failed: {e}")

    optimize_epg_content(root)
    fix_and_optimize_timestamps(root) 

    xml_bytes = etree.tostring(
        root, 
        pretty_print=False, 
        xml_declaration=True,
        encoding='utf-8'
    )
    
    # Save Compressed (Primary)
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
