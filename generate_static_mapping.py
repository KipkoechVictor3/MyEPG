import requests
import gzip
import xmltodict
import json
from rapidfuzz import fuzz

# CONFIG
M3U_URL = "https://bit.ly/47dWcV1"  # original source M3U
EPG_URLS = [
    "https://epgshare01.online/epgshare01/epg_ripper_UK1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_US1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_NZ1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_DUMMY_CHANNELS.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_ZA1.xml.gz"
]
SIM_THRESHOLD = 85  # fuzzy match threshold

def download_m3u(url):
    return requests.get(url).text.splitlines()

def download_epg_channels():
    epg_channels = []
    for url in EPG_URLS:
        gz_data = requests.get(url).content
        xml_data = gzip.decompress(gz_data).decode("utf-8", errors="ignore")
        epg_dict = xmltodict.parse(xml_data)
        for ch in epg_dict["tv"]["channel"]:
            epg_channels.append({
                "id": ch.get("@id", "").strip(),
                "name": ch.get("display-name", [""])[0].strip() if isinstance(ch.get("display-name"), list) else ch.get("display-name", "").strip(),
                "logo": ch.get("icon", {}).get("@src", "") if ch.get("icon") else ""
            })
    return epg_channels

def parse_m3u(m3u_lines):
    channels = []
    for i, line in enumerate(m3u_lines):
        if line.startswith("#EXTINF"):
            attrs, display_name = line.split(",", 1)
            tvg_id = ""
            tvg_name = ""
            if 'tvg-id="' in attrs:
                tvg_id = attrs.split('tvg-id="')[1].split('"')[0]
            if 'tvg-name="' in attrs:
                tvg_name = attrs.split('tvg-name="')[1].split('"')[0]
            channels.append({
                "tvg-id": tvg_id,
                "tvg-name": tvg_name,
                "display-name": display_name.strip()
            })
    return channels

def match_channels(m3u_channels, epg_channels):
    mapping = {}
    for m in m3u_channels:
        best_score = 0
        best_epg = None
        m_candidates = [m["tvg-name"], m["display-name"]]
        for epg in epg_channels:
            for candidate in m_candidates:
                score = fuzz.token_sort_ratio(candidate.lower(), epg["name"].lower())
                if score > best_score and score >= SIM_THRESHOLD:
                    best_score = score
                    best_epg = epg
        if best_epg:
            mapping[m["display-name"]] = {
                "tvg-id": best_epg["id"],
                "logo": best_epg["logo"]
            }
    return mapping

if __name__ == "__main__":
    m3u_lines = download_m3u(M3U_URL)
    epg_channels = download_epg_channels()
    m3u_channels = parse_m3u(m3u_lines)
    mapping = match_channels(m3u_channels, epg_channels)

    with open("channel_mapping.json", "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=2, ensure_ascii=False)

    print(f"Generated mapping for {len(mapping)} channels.")
