import requests
import gzip
import xmltodict

EPG_URLS = [
    "https://epgshare01.online/epgshare01/epg_ripper_UK1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_US1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_NZ1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_DUMMY_CHANNELS.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_ZA1.xml.gz"
]
OUTPUT_FILE = "combined_epg.xml.gz"

def merge_epgs():
    merged = {"tv": {"channel": [], "programme": []}}
    seen_channels = set()

    for url in EPG_URLS:
        gz_data = requests.get(url).content
        xml_data = gzip.decompress(gz_data).decode("utf-8", errors="ignore")
        epg_dict = xmltodict.parse(xml_data)

        for ch in epg_dict["tv"]["channel"]:
            if ch["@id"] not in seen_channels:
                merged["tv"]["channel"].append(ch)
                seen_channels.add(ch["@id"])

        merged["tv"]["programme"].extend(epg_dict["tv"]["programme"])

    xml_bytes = xmltodict.unparse(merged, pretty=True).encode("utf-8")
    with gzip.open(OUTPUT_FILE, "wb") as f:
        f.write(xml_bytes)

if __name__ == "__main__":
    merge_epgs()
