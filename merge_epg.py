import requests
import gzip
import xml.etree.ElementTree as ET
from io import BytesIO

# Your 4 EPG source URLs
epg_urls = [
    "https://epgshare01.online/epgshare01/epg_ripper_UK1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_US1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_NZ1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_DUMMY_CHANNELS.xml.gz"
]

headers = {"User-Agent": "EPG-Merger/1.0 (+https://github.com)"}
root = ET.Element("tv")

for url in epg_urls:
    print(f"Downloading {url} ...")
    try:
        r = requests.get(url, timeout=60, headers=headers)
        r.raise_for_status()
        with gzip.GzipFile(fileobj=BytesIO(r.content)) as gz:
            xml_content = gz.read()
        epg_tree = ET.fromstring(xml_content)
        for child in epg_tree:
            root.append(child)
        print(f"  ✅ Added: {url}")
    except Exception as e:
        print(f"  ❌ Failed {url}: {e}")

# Write uncompressed XML (optional)
tree = ET.ElementTree(root)
tree.write("combined_epg.xml", encoding="utf-8", xml_declaration=True)

# Write compressed gzipped XML
with gzip.open("combined_epg.xml.gz", "wb") as f:
    tree.write(f, encoding="utf-8", xml_declaration=True)

print("Saved combined_epg.xml and combined_epg.xml.gz")
