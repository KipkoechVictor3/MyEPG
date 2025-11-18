import requests
import gzip
from lxml import etree # Replaced xml.etree.ElementTree with lxml
from io import BytesIO
from urllib.parse import urljoin
import re 
import sys # Used for final output size check

# --- Configuration ---
BASE_URL = "https://epgshare01.online/epgshare01/"

# EPG source keys to fetch.
EPG_KEYS_TO_FIND = [
    "UK", "US", "NZ", "DUMMY_CHANNELS", "ZA", "ID", "MY",
    "US_SPORTS", "AU", "CA", "SG", "NG", "KE"
]

HEADERS = {"User-Agent": "EPG-Merger-Dynamic-Reduced/1.1 (+https://github.com)"}
TIMEOUT = 60
# ---------------------

# --- New Function for Size Reduction (Content Cleanup) ---
def optimize_epg_content(root: etree.Element):
    """
    Applies small content optimizations to the merged XML tree before final writing.
    This helps remove redundancy not stripped by the main parser.
    """
    print("Applying content optimization (removing redundant/empty elements)...")
    
    # 1. Iterate through all 'programme' elements
    for programme in root.iter('programme'):
        
        # Remove common non-essential, empty elements if present
        elements_to_check = ['credits', 'star-rating', 'review', 'icon']
        for tag in elements_to_check:
            element = programme.find(tag)
            
            # Check if element exists AND has no children AND has no text content
            if (element is not None and 
                len(element) == 0 and 
                (element.text is None or not element.text.strip()) and
                not element.attrib):
                
                # Safely remove it
                parent = element.getparent()
                if parent is not None:
                    parent.remove(element)
        
        # 2. Optimize <desc> (Description) Content by normalizing excessive whitespace
        desc = programme.find('desc')
        if desc is not None and desc.text is not None:
            # Replace 2 or more consecutive spaces/newlines with a single space, then strip leading/trailing
            desc.text = re.sub(r'\s{2,}', ' ', desc.text).strip()
            
            # If after cleaning the description is now empty, remove the element entirely
            if not desc.text:
                parent = desc.getparent()
                if parent is not None:
                    parent.remove(desc)

    # Note: LXML is namespace-aware; standard XMLTV tags (like 'tv', 'channel', 'programme') 
    # don't typically have namespaces defined, so direct tag iteration works fine.
    print("Optimization complete.")


# --- Existing Functions (Updated to use lxml for merging) ---

def get_latest_epg_urls():
    """
    Scrapes the base URL's index to find the latest version of the desired EPG files.
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
    filename_parser_pattern = re.compile(r'^epg_ripper_([A-Z_]+?)(\d*)\.xml\.gz$')

    found_epgs = {} # key: {'version': int, 'filename': str}

    for filename in all_xml_filenames:
        match = filename_parser_pattern.match(filename)
        
        if match:
            base_key_for_lookup = match.group(1) 
            version = int(match.group(2) or 0)

            if base_key_for_lookup not in found_epgs or version > found_epgs[base_key_for_lookup]['version']:
                found_epgs[base_key_for_lookup] = {'version': version, 'filename': filename}


    # 4. Filter the resolved files against the desired EPG_KEYS_TO_FIND
    resolved_urls = []
    for key in EPG_KEYS_TO_FIND:
        if key in found_epgs:
            filename = found_epgs[key]['filename']
            full_url = urljoin(BASE_URL, filename)
            resolved_urls.append(full_url)
            print(f"  ✅ Resolved '{key}' to: {filename}")
        else:
            print(f"  ⚠️ Warning: Could not find any file for key '{key}'. Skipping.")

    return resolved_urls


def main():
    """Main function to run the EPG merger workflow with size reduction."""
    
    # 1. Dynamically find the latest URLs
    epg_urls = get_latest_epg_urls()

    if not epg_urls:
        print("\n❌ No EPG URLs were successfully resolved. Exiting.")
        return

    # 2. Initialize XML tree using lxml
    root = etree.Element("tv")
    
    # 3. Download and merge EPG files
    for url in epg_urls:
        print(f"\nDownloading {url} ...")
        try:
            r = requests.get(url, timeout=TIMEOUT, headers=HEADERS)
            r.raise_for_status()

            # Decompress and parse the XML using lxml
            with gzip.GzipFile(fileobj=BytesIO(r.content)) as gz:
                xml_content = gz.read()
            
            # Use etree.fromstring() for parsing
            epg_tree = etree.fromstring(xml_content)
            
            # Append all child elements (channels and programmes) to the root
            for child in epg_tree:
                root.append(child)
            
            print(f"  ✅ Added: {url}")
            
        except Exception as e:
            print(f"  ❌ Failed to process {url}: {e}")

    # 4. Apply size reduction optimizations
    optimize_epg_content(root)

    # 5. Final output serialization and compression
    
    # CRITICAL SIZE REDUCTION STEP: 
    # Use etree.tostring with pretty_print=False to remove all whitespace/indentation.
    xml_bytes = etree.tostring(
        root, 
        pretty_print=False, # <-- This is the key change for size reduction
        xml_declaration=True,
        encoding='utf-8'
    )
    
    print("\nWriting final REDUCED EPG files...")
    
    # Write uncompressed XML (minimal format, no pretty-print)
    output_xml_path = "combined_epg_reduced.xml"
    try:
        with open(output_xml_path, "wb") as f:
            f.write(xml_bytes)
        print(f"  ✅ Saved {output_xml_path} ({len(xml_bytes) / (1024*1024):.2f} MB)")
    except Exception as e:
        print(f"  ❌ Failed to write {output_xml_path}: {e}")

    # Write compressed gzipped XML (minimal format, max compression)
    output_gz_path = "combined_epg.xml.gz"
    try:
        # compresslevel=9 provides the maximum compression ratio
        with gzip.open(output_gz_path, "wb", compresslevel=9) as f:
            f.write(xml_bytes)
        
        # Read back the size to report compression gains
        compressed_size = sys.getsizeof(gzip.compress(xml_bytes, compresslevel=9))
        print(f"  ✅ Saved {output_gz_path} (Compressed: {compressed_size / (1024*1024):.2f} MB)")
    except Exception as e:
        print(f"  ❌ Failed to write {output_gz_path}: {e}")
        
    print("\nWorkflow complete.")


if __name__ == "__main__":
    main()
