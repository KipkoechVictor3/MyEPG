# NOTE: This script requires the 'lxml' and 'requests' libraries. 
# Install them using: pip install lxml requests
import requests
import gzip
from lxml import etree # Replaced xml.etree.ElementTree with lxml
from io import BytesIO
from urllib.parse import urljoin
import re 
import sys 

# --- Configuration ---
BASE_URL = "https://epgshare01.online/epgshare01/"

# EPG source keys to fetch.
EPG_KEYS_TO_FIND = [
    "UK", "US", "NZ", "DUMMY_CHANNELS", "ZA", "ID", "MY",
    "US_SPORTS", "AU", "CA", "SG", "NG", "KE"
]

HEADERS = {"User-Agent": "EPG-Merger-Dynamic-Reduced/1.2 (+https://github.com)"}
TIMEOUT = 60
# ---------------------

# --- New Function for Size Reduction (Content Cleanup) ---
def optimize_epg_content(root: etree.Element):
    """
    Applies aggressive content optimizations to the merged XML tree before final writing.
    This focuses on removing optional, high-volume, or redundant data elements.
    """
    print("Applying AGGRESSIVE content optimization (stripping non-essential tags)...")
    
    # 1. Iterate through all 'programme' elements for deep cleanup
    for programme in root.iter('programme'):
        
        # AGGRESSIVE STRATEGY 1: Remove common non-essential and high-volume elements
        # Removing these optional tags can drastically reduce the byte count.
        elements_to_strip = [
            'sub-title',  # Often repeats information or is low-value
            'credits',    # Unless critical, actors/directors lists are large
            'star-rating',
            'review',
            'icon',       # URLs are compressible, but removing the tag saves structure bytes
            'language',   # If the language is consistent across the source, removing this saves a lot of repetition
        ]
        
        for tag in elements_to_strip:
            element = programme.find(tag)
            if element is not None:
                parent = element.getparent()
                if parent is not None:
                    parent.remove(element)

        
        # AGGRESSIVE STRATEGY 2: Remove remaining empty tags and optimize descriptions
        elements_to_check = ['desc', 'title']
        for tag in elements_to_check:
            element = programme.find(tag)
            
            if element is not None and element.text is not None:
                # Optimize <desc> and <title> Content by normalizing excessive whitespace
                # Replace 2 or more consecutive spaces/newlines with a single space, then strip leading/trailing
                element.text = re.sub(r'\s{2,}', ' ', element.text).strip()
                
                # If after cleaning the element is now empty, remove it entirely
                if not element.text:
                    parent = element.getparent()
                    if parent is not None:
                        parent.remove(element)
            
            # Remove tags that were empty initially
            elif (element is not None and 
                len(element) == 0 and 
                (element.text is None or not element.text.strip()) and
                not element.attrib):
                
                parent = element.getparent()
                if parent is not None:
                    parent.remove(element)

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
        pretty_print=False, # <-- Key change for size reduction
        xml_declaration=True,
        encoding='utf-8'
    )
    
    print("\nWriting final REDUCED EPG files...")
    
    # Write uncompressed XML (minimal format, no pretty-print)
    output_xml_path = "combined_epg_reduced.xml"
    try:
        # Report the uncompressed size for comparison
        uncompressed_size_mb = len(xml_bytes) / (1024*1024)
        with open(output_xml_path, "wb") as f:
            f.write(xml_bytes)
        print(f"  ✅ Saved {output_xml_path} (Uncompressed Size: {uncompressed_size_mb:.2f} MB)")
    except Exception as e:
        print(f"  ❌ Failed to write {output_xml_path}: {e}")

    # Write compressed gzipped XML (minimal format, max compression)
    output_gz_path = "combined_epg.xml.gz"
    try:
        # compresslevel=9 provides the maximum compression ratio
        with gzip.open(output_gz_path, "wb", compresslevel=9) as f:
            f.write(xml_bytes)
        
        # NOTE: The true compressed size must be checked on the disk 
        # (e.g., using 'ls -lh combined_epg.xml.gz').
        print(f"  ✅ Saved {output_gz_path}. Check file size on disk for final compression gains.")
    except Exception as e:
        print(f"  ❌ Failed to write {output_gz_path}: {e}")
        
    print("\nWorkflow complete.")


if __name__ == "__main__":
    main()
