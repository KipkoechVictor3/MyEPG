import gzip
import xml.etree.ElementTree as ET
import requests
from io import BytesIO
import os

EPG_URL = "https://epgshare01.online/epgshare01/epg_ripper_ALL_SOURCES1.xml.gz"
CHANNELS_FILE = "Allchannels.txt"
OUTPUT_FILE = "filtered_epg.xml.gz"
HEADERS = {"User-Agent": "EPG-Filter/Stream/1.0 (+https://github.com)"}

def load_tvg_ids(filepath):
    with open(filepath, encoding="utf-8") as f:
        ids = [line.strip().lower() for line in f if line.strip()]
    return set(ids)

def download_epg_stream(url):
    print(f"📡 Downloading EPG (stream mode) from {url} ...")
    r = requests.get(url, headers=HEADERS, timeout=600, stream=True)
    r.raise_for_status()
    # Return a BytesIO containing the gzipped data
    data = BytesIO()
    for chunk in r.iter_content(chunk_size=1024 * 512):
        data.write(chunk)
    data.seek(0)
    print(f"✅ Download complete ({data.tell()/1024/1024:.1f} MB gzipped)")
    return data

def filter_epg_stream(gz_data, wanted_ids):
    print("🔍 Filtering by tvg-id (streaming)...")
    filtered_root = ET.Element("tv")

    kept_channels = set()
    prog_count = 0
    ch_count = 0

    # open gz as a stream
    with gzip.GzipFile(fileobj=gz_data) as f:
        context = ET.iterparse(f, events=("end",))
        for event, elem in context:
            tag = elem.tag

            if tag == "channel":
                cid = elem.attrib.get("id", "").lower()
                if cid in wanted_ids:
                    filtered_root.append(elem)
                    kept_channels.add(elem.attrib.get("id"))
                    ch_count += 1
                elem.clear()  # free memory

            elif tag == "programme":
                if elem.attrib.get("channel") in kept_channels:
                    filtered_root.append(elem)
                    prog_count += 1
                elem.clear()

    print(f"✅ Kept {ch_count} channels and {prog_count} programmes")
    return filtered_root

def save_filtered_epg(root, output_file):
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

    gz_data = download_epg_stream(EPG_URL)
    filtered_root = filter_epg_stream(gz_data, wanted_ids)
    save_filtered_epg(filtered_root, OUTPUT_FILE)
    print("🎉 Done — your filtered EPG is ready!")

if __name__ == "__main__":
    main()
