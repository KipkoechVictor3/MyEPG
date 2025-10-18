import gzip
import xml.etree.ElementTree as ET
import requests
from io import BytesIO
import os

# === SETTINGS ===
EPG_URL = "https://epgshare01.online/epgshare01/epg_ripper_ALL_SOURCES1.xml.gz"
CHANNELS_FILE = "Allchannels.txt"
OUTPUT_FILE = "filtered_epg.xml.gz"
HEADERS = {"User-Agent": "EPG-Filter/1.0 (+https://github.com)"}

def load_tvg_ids(filepath):
    """Load and normalize wanted tvg-id list."""
    with open(filepath, encoding="utf-8") as f:
        ids = [line.strip() for line in f if line.strip()]
    # normalize to lowercase for comparison
    return set(i.lower() for i in ids)

def download_epg(url):
    """Download and decompress the EPG .gz file."""
    print(f"📡 Downloading EPG from {url} ...")
    r = requests.get(url, headers=HEADERS, timeout=300)
    r.raise_for_status()
    with gzip.GzipFile(fileobj=BytesIO(r.content)) as gz:
        xml_data = gz.read()
    print(f"✅ Downloaded and decompressed ({len(xml_data)/1024/1024:.1f} MB uncompressed)")
    return xml_data

def filter_epg(xml_data, wanted_ids):
    """Keep only <channel> and <programme> elements with matching ids."""
    print("🔍 Filtering by tvg-id ...")
    root = ET.fromstring(xml_data)
    filtered_root = ET.Element("tv")

    kept_ids = set()
    # Pass 1: Filter <channel> elements
    for ch in root.findall("channel"):
        ch_id = ch.attrib.get("id", "").lower()
        if ch_id in wanted_ids:
            filtered_root.append(ch)
            kept_ids.add(ch.attrib["id"])
    print(f"✅ Kept {len(kept_ids)} channels")

    # Pass 2: Filter <programme> elements
    prog_count = 0
    for prog in root.findall("programme"):
        if prog.attrib.get("channel") in kept_ids:
            filtered_root.append(prog)
            prog_count += 1
    print(f"✅ Kept {prog_count} programme entries")

    return filtered_root

def save_filtered_epg(root, output_file):
    """Save filtered EPG to gzipped XML."""
    tree = ET.ElementTree(root)
    with gzip.open(output_file, "wb") as f:
        tree.write(f, encoding="utf-8", xml_declaration=True)
    print(f"💾 Saved filtered EPG to {output_file}")

def main():
    if not os.path.exists(CHANNELS_FILE):
        print(f"❌ Missing {CHANNELS_FILE}. Please create it in the same folder.")
        return

    wanted_ids = load_tvg_ids(CHANNELS_FILE)
    print(f"📖 Loaded {len(wanted_ids)} tvg-ids from {CHANNELS_FILE}")

    xml_data = download_epg(EPG_URL)
    filtered_root = filter_epg(xml_data, wanted_ids)
    save_filtered_epg(filtered_root, OUTPUT_FILE)
    print("🎉 Done — your filtered EPG is ready!")

if __name__ == "__main__":
    main()
