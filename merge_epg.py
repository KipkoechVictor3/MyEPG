import requests
import gzip
import xml.etree.ElementTree as ET
from io import BytesIO
import difflib
import re

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

# --- Words to ignore for matching ---
IGNORE_WORDS = ["hd", "fhd", "sd", "uhd", "4k", "1080p"]

def clean_name(name: str) -> str:
    """Lowercase, strip, and remove quality tags while keeping unique identifiers."""
    name = name.lower().strip()
    # Remove extra spaces and punctuation
    name = re.sub(r"[\(\)\[\]\-\.]", " ", name)
    # Remove quality tags only if standalone words
    words = [w for w in name.split() if w not in IGNORE_WORDS]
    return " ".join(words)

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

# Precompute cleaned names for fuzzy matching
playlist_names_clean = [clean_name(c['tvg-name']) for c in m3u_channels]

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

# --- Step 3: Align EPG channel IDs ---
for channel in root.findall("channel"):
    display_elem = channel.find("display-name")
    if display_elem is not None and display_elem.text:
        display_name = display_elem.text.strip()
        clean_display = clean_name(display_name)

        # 1. Exact clean match
        match = None
        if clean_display in playlist_names_clean:
            idx = playlist_names_clean.index(clean_display)
            match = m3u_channels[idx]

        # 2. Fuzzy clean match
        if not match:
            best_match = difflib.get_close_matches(clean_display, playlist_names_clean, n=1, cutoff=0.7)
            if best_match:
                idx = playlist_names_clean.index(best_match[0])
                match = m3u_channels[idx]

        # If found, update EPG ID
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

# --- Step 6: Save compressed M3U ---
with open("aligned_playlist.m3u", "rb") as f_in:
    with gzip.open("aligned_playlist.m3u.gz", "wb") as f_out:
        f_out.writelines(f_in)

print("✅ Saved aligned_epg.xml.gz, aligned_playlist.m3u, and aligned_playlist.m3u.gz")
