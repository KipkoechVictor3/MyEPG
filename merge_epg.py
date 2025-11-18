# merge_epg.py

import requests
import gzip
import xml.etree.ElementTree as ET
from io import BytesIO
from urllib.parse import urljoin # Needed for safe URL construction
import re # Needed for HTML parsing

# --- Configuration ---
BASE_URL = "https://epgshare01.online/epgshare01/"

# EPG source keys to fetch. The script will dynamically find the highest 
# numbered version for each of these keys (e.g., 'US' will resolve to US2 if available).
# Note: These keys must match the part of the filename BEFORE the number (if any).
EPG_KEYS_TO_FIND = [
    "UK", "US", "NZ", "DUMMY_CHANNELS", "ZA", "ID", "MY",
    "US_SPORTS", "AU", "CA", "SG", "NG", "KE"
]

HEADERS = {"User-Agent": "EPG-Merger-Dynamic/1.0 (+https://github.com)"}
TIMEOUT = 60
# ---------------------


def get_latest_epg_urls():
    """
    Scrapes the base URL's index to find the latest version of the desired EPG files.
    Determines the "latest" by selecting the highest numeric suffix (e.g., US2 over US1).
    
    Returns:
        A list of full, dynamically resolved EPG URLs.
    """
    print(f"Scraping index from {BASE_URL} to find latest EPG URLs...")
    
    try:
        # 1. Download the directory index page
        r = requests.get(BASE_URL, timeout=TIMEOUT, headers=HEADERS)
        r.raise_for_status()
        html_content = r.text
    except Exception as e:
        print(f"❌ Failed to download directory index: {e}")
        return []
    
    # 2. Extract all epg_ripper_*.xml.gz filenames from the HTML
    file_link_pattern = re.compile(r'<a href="(epg_ripper_.*?\.xml\.gz)">')
    all_xml_filenames = file_link_pattern.findall(html_content)
    
    # 3. Parse and group files by their base key, keeping only the highest version
    # Pattern to extract: epg_ripper_ [BASE_KEY] [VERSION_NUMBER] .xml.gz
    filename_parser_pattern = re.compile(r'^epg_ripper_([A-Z_]+?)(\d*)\.xml\.gz$')

    found_epgs = {} # key: {'version': int, 'filename': str}

    for filename in all_xml_filenames:
        match = filename_parser_pattern.match(filename)
        
        if match:
            # Group 1: The base name (e.g., 'US', 'DUMMY_CHANNELS')
            base_key_for_lookup = match.group(1) 
            # Group 2: The version number (e.g., '2'), defaulting to 0 if not present
            version = int(match.group(2) or 0)

            # Keep the filename if it's a new key or a higher version number for an existing key
            if base_key_for_lookup not in found_epgs or version > found_epgs[base_key_for_lookup]['version']:
                found_epgs[base_key_for_lookup] = {'version': version, 'filename': filename}


    # 4. Filter the resolved files against the desired EPG_KEYS_TO_FIND
    resolved_urls = []
    for key in EPG_KEYS_TO_FIND:
        if key in found_epgs:
            filename = found_epgs[key]['filename']
            # Safely join the base URL and the filename
            full_url = urljoin(BASE_URL, filename)
            resolved_urls.append(full_url)
            print(f"  ✅ Resolved '{key}' to: {filename}")
        else:
            print(f"  ⚠️ Warning: Could not find any file for key '{key}'. Skipping.")

    return resolved_urls


def main():
    """Main function to run the EPG merger workflow."""
    
    # 1. Dynamically find the latest URLs
    epg_urls = get_latest_epg_urls()

    if not epg_urls:
        print("\n❌ No EPG URLs were successfully resolved. Exiting.")
        return

    # 2. Initialize XML tree
    root = ET.Element("tv")
    
    # 3. Download and merge EPG files
    for url in epg_urls:
        print(f"\nDownloading {url} ...")
        try:
            r = requests.get(url, timeout=TIMEOUT, headers=HEADERS)
            r.raise_for_status()

            # Decompress and parse the XML
            with gzip.GzipFile(fileobj=BytesIO(r.content)) as gz:
                xml_content = gz.read()
            
            epg_tree = ET.fromstring(xml_content)
            
            # Append all child elements (channels and programmes) to the root
            for child in epg_tree:
                root.append(child)
            
            print(f"  ✅ Added: {url}")
            
        except Exception as e:
            print(f"  ❌ Failed to process {url}: {e}")

    # 4. Final output
    tree = ET.ElementTree(root)

    # Write uncompressed XML
    print("\nWriting final EPG files...")
    try:
        tree.write("combined_epg.xml", encoding="utf-8", xml_declaration=True)
        print("  ✅ Saved combined_epg.xml")
    except Exception as e:
        print(f"  ❌ Failed to write combined_epg.xml: {e}")

    # Write compressed gzipped XML
    try:
        with gzip.open("combined_epg.xml.gz", "wb") as f:
            tree.write(f, encoding="utf-8", xml_declaration=True)
        print("  ✅ Saved combined_epg.xml.gz")
    except Exception as e:
        print(f"  ❌ Failed to write combined_epg.xml.gz: {e}")
        
    print("\nWorkflow complete.")


if __name__ == "__main__":
    main()
