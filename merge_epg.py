import requests
import gzip
from lxml import etree 
from io import BytesIO
from urllib.parse import urljoin
import re 

# --- Configuration ---
BASE_URL = "https://epgshare01.online/epgshare01/"
EPG_KEYS_TO_FIND = ["UK", "US", "NZ", "DUMMY_CHANNELS", "ID", "MY", "US_SPORTS", "AU", "CA", "SG", "HK","PEACOCK"]

EXTRA_STATIC_URLS = [
    "https://github.com/matthuisman/i.mjh.nz/raw/master/SamsungTVPlus/gb.xml.gz",
    "https://github.com/matthuisman/i.mjh.nz/raw/master/DStv/za.xml.gz",
    "https://github.com/matthuisman/i.mjh.nz/raw/master/PlutoTV/gb.xml.gz"
]

HEADERS = {"User-Agent": "EPG-Minimalist/3.0"}
TIMEOUT = 60

def apply_aggressive_cleanup(root: etree.Element):
    """
    The 'Meat and Potatoes' cleanup:
    1. Removes all metadata from <channel> except the name.
    2. Removes all metadata from <programme> except the title.
    3. Truncates timestamps to save character space.
    """
    print("🧹 Starting aggressive cleanup...")
    
    # Clean Channels: Remove icons, URLs, and extra descriptions
    for channel in root.xpath('//channel'):
        for child in list(channel):
            if child.tag != 'display-name':
                channel.remove(child)

    # Clean Programmes: This is where 90% of the weight is
    for programme in root.xpath('//programme'):
        # 1. Strip timezone from start/stop (e.g., "20260309140000 +0000" -> "20260309140000")
        for attr in ['start', 'stop']:
            val = programme.get(attr)
            if val and " " in val:
                programme.set(attr, val.split(' ')[0])
        
        # 2. Delete every tag that ISN'T the title (removes desc, category, icon, credits, etc.)
        for child in list(programme):
            if child.tag != 'title':
                programme.remove(child)
        
        # 3. Clean whitespace in titles
        title = programme.find('title')
        if title is not None and title.text:
            title.text = " ".join(title.text.split())

def get_latest_epg_urls():
    print(f"Scraping index from {BASE_URL}...")
    try:
        r = requests.get(BASE_URL, timeout=TIMEOUT, headers=HEADERS)
        r.raise_for_status()
        filenames = re.findall(r'<a href="(epg_ripper_.*?\.xml\.gz)">', r.text)
        
        found_epgs = {}
        pattern = re.compile(r'^epg_ripper_([A-Z_]+?)(\d*)\.xml\.gz$')

        for fname in filenames:
            match = pattern.match(fname)
            if match:
                key, ver = match.group(1), int(match.group(2) or 0)
                if key not in found_epgs or ver > found_epgs[key]['v']:
                    found_epgs[key] = {'v': ver, 'f': fname}

        return [urljoin(BASE_URL, found_epgs[k]['f']) for k in EPG_KEYS_TO_FIND if k in found_epgs]
    except Exception as e:
        print(f"❌ Scraping failed: {e}")
        return []

def main():
    dynamic_urls = get_latest_epg_urls()
    all_urls = dynamic_urls + EXTRA_STATIC_URLS
    
    # Root element for the new merged XML
    root = etree.Element("tv")
    
    print(f"\nMerging {len(all_urls)} sources...")
    
    for url in all_urls:
        try:
            r = requests.get(url, timeout=TIMEOUT, headers=HEADERS)
            r.raise_for_status()
            with gzip.GzipFile(fileobj=BytesIO(r.content)) as gz:
                source_tree = etree.fromstring(gz.read())
                for element in source_tree:
                    root.append(element)
                source_tree.clear() # Clear memory from processed source
            print(f"  ✅ Merged: {url.split('/')[-1]}")
        except Exception as e:
            print(f"  ❌ Failed {url}: {e}")

    # Run the cleanup
    apply_aggressive_cleanup(root)

    # Convert to string with NO pretty printing (saves massive space on newlines/indentation)
    final_xml = etree.tostring(root, xml_declaration=True, encoding='utf-8', pretty_print=False)

    # Save to disk
    output_fn = "minimal_epg.xml.gz"
    with gzip.open(output_fn, "wb", compresslevel=9) as f:
        f.write(final_xml)
    
    uncompressed_mb = len(final_xml) / (1024 * 1024)
    print(f"\n🚀 Success!")
    print(f"Uncompressed Size: {uncompressed_mb:.2f} MB")
    print(f"Compressed file saved as: {output_fn}")

if __name__ == "__main__":
    main()
