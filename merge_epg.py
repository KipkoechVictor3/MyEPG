import requests
import gzip
import xml.etree.ElementTree as ET
from io import BytesIO
import difflib

# --- EPG URLs ---
epg_urls = [
    "https://epgshare01.online/epgshare01/epg_ripper_UK1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_US1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_NZ1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_DUMMY_CHANNELS.xml.gz"
]

# --- Playlist URL ---
m3u_url = "https://bit.ly/47dWcV1"

headers = {"User-Agent": "EPG-Merger/1.0 (+https://github.com)"}

# --- Step 1: Download & parse M3U ---
print(f"Downloading playlist from {m3u_url} ...")
r = requests.get(m3u_url, timeout=60, headers=headers)
r.raise_for_status()
playlist_text = r.text.strip().splitlines()

m3u_channels = []
current = {}
for line in playlist_text:
    if line.startswith("#EXTINF:"):
        if 'tvg-id="' in line:
            current['tvg-id'] = line.split('tvg-id="')[1].split('"')[0]
        else:
            current['tvg-id'] = None
        if 'tvg-name="' in line:
            current['tvg-name'] = line.split('tvg-name="')[1].split('"')[0]
        else:
            current['tvg-name'] = line.split(",")[-1].strip()
    elif line.startswith("http"):
        current['url'] = line.strip()
        m3u_channels.append(current)
        current = {}

print(f"✅ Parsed {len(m3u_channels)} channels from M3U")

# Prepare lookup lists for fuzzy matching
playlist_names = [c['tvg-name'].lower() for c in m3u_channels]

# --- Step 2: Merge all EPGs ---
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

# --- Step 3: Align EPG channel IDs with playlist using fuzzy match ---
for channel in root.findall("channel"):
    display_elem = channel.find("display-name")
    if display_elem is not None and display_elem.text:
        display_name = display_elem.text.strip().lower()

        # Try exact match first
        match = next((c for c in m3u_channels if c['tvg-name'].lower() == display_name), None)

        # If no exact match, try fuzzy matching
        if not match:
            best_match_name = difflib.get_close_matches(display_name, playlist_names, n=1, cutoff=0.7)
            if best_match_name:
                match = next((c for c in m3u_channels if c['tvg-name'].lower() == best_match_name[0]), None)

        if match:
            new_id = match['tvg-id'] if match['tvg-id'] else match['tvg-name']
            channel.set("id", new_id)

# --- Step 4: Save aligned EPG ---
tree = ET.ElementTree(root)
with gzip.open("aligned_epg.xml.gz", "wb") as f:
    tree.write(f, encoding="utf-8", xml_declaration=True)

# --- Step 5: Save aligned M3U ---
with open("aligned_playlist.m3u", "w", encoding="utf-8") as f:
    f.write("#EXTM3U\n")
    for ch in m3u_channels:
        tvg_id = ch['tvg-id'] if ch['tvg-id'] else ch['tvg-name']
        f.write(f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-name="{ch["tvg-name"]}",{ch["tvg-name"]}\n')
        f.write(f"{ch['url']}\n")

print("✅ Saved aligned_epg.xml.gz and aligned_playlist.m3u")
