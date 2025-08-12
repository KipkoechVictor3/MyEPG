# update_m3u_epg.py
import requests
import gzip
import xml.etree.ElementTree as ET
from io import BytesIO
from rapidfuzz import process, fuzz
import re
from datetime import datetime

# -------- CONFIG --------
M3U_URL = "https://your-original-m3u-url-here"
EPG_URLS = [
    "https://epgshare01.online/epgshare01/epg_ripper_UK1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_US1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_NZ1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_DUMMY_CHANNELS.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_ZA1.xml.gz"
]
SIMILARITY_THRESHOLD = 85  # fuzzy match %
OUTPUT_M3U = "updated_playlist.m3u"
OUTPUT_EPG = "combined_epg.xml.gz"

# -------- FUNCTIONS --------
def download_epgs():
    channels = {}
    for url in EPG_URLS:
        print(f"Downloading EPG: {url}")
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        with gzip.GzipFile(fileobj=BytesIO(r.content)) as f:
            tree = ET.parse(f)
            root = tree.getroot()
            for ch in root.findall("channel"):
                tvg_id = ch.get("id")
                display_names = [dn.text for dn in ch.findall("display-name")]
                logo_elem = ch.find("icon")
                logo = logo_elem.get("src") if logo_elem is not None else None
                for name in display_names:
                    channels[name.lower()] = {
                        "tvg-id": tvg_id,
                        "tvg-logo": logo
                    }
    print(f"Collected {len(channels)} channels from EPG")
    return channels

def download_m3u():
    print(f"Downloading M3U: {M3U_URL}")
    r = requests.get(M3U_URL, timeout=30)
    r.raise_for_status()
    return r.text.splitlines()

def update_m3u(epg_channels, m3u_lines):
    updated_lines = []
    channel_names = list(epg_channels.keys())

    for i, line in enumerate(m3u_lines):
        if line.startswith("#EXTINF"):
            # Extract tvg-name and tvg-id
            name_match = re.search(r'tvg-name="([^"]+)"', line)
            id_match = re.search(r'tvg-id="([^"]+)"', line)
            logo_match = re.search(r'tvg-logo="([^"]+)"', line)

            original_name = name_match.group(1) if name_match else None
            original_id = id_match.group(1) if id_match else ""
            original_logo = logo_match.group(1) if logo_match else ""

            if original_name:
                best_match = process.extractOne(
                    original_name.lower(),
                    channel_names,
                    scorer=fuzz.token_sort_ratio
                )

                if best_match and best_match[1] >= SIMILARITY_THRESHOLD:
                    match_data = epg_channels[best_match[0]]
                    new_tvg_id = match_data["tvg-id"]
                    new_logo = match_data["tvg-logo"]

                    # Replace only tvg-id
                    line = re.sub(r'tvg-id="([^"]*)"', f'tvg-id="{new_tvg_id}"', line)

                    # Fill logo if missing
                    if not original_logo and new_logo:
                        if 'tvg-logo="' in line:
                            line = re.sub(r'tvg-logo="([^"]*)"', f'tvg-logo="{new_logo}"', line)
                        else:
                            line = line.replace(original_name, f'tvg-logo="{new_logo}" {original_name}')

        updated_lines.append(line)

    return "\n".join(updated_lines)

def combine_epgs():
    print("Combining EPGs...")
    root = ET.Element("tv")
    for url in EPG_URLS:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        with gzip.GzipFile(fileobj=BytesIO(r.content)) as f:
            tree = ET.parse(f)
            for elem in tree.getroot():
                root.append(elem)
    buf = BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="w") as f:
        ET.ElementTree(root).write(f, encoding="utf-8")
    with open(OUTPUT_EPG, "wb") as f:
        f.write(buf.getvalue())
    print(f"Saved combined EPG to {OUTPUT_EPG}")

if __name__ == "__main__":
    epg_data = download_epgs()
    m3u_data = download_m3u()
    updated_m3u = update_m3u(epg_data, m3u_data)

    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.write(updated_m3u)

    combine_epgs()
    print(f"Updated playlist saved to {OUTPUT_M3U} — {datetime.utcnow()} UTC")
