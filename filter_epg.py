#!/usr/bin/env python3
import gzip
import xml.etree.ElementTree as ET
import requests
from io import BytesIO
import os
import time

EPG_URL = "https://epgshare01.online/epgshare01/epg_ripper_ALL_SOURCES1.xml.gz"
CHANNELS_FILE = "Allchannels.txt"
OUTPUT_FILE = "filtered_epg.xml.gz"
HEADERS = {"User-Agent": "EPG-Filter/Stream/1.1 (+https://github.com)"}

PROGRESS_EVERY = 10000  # print progress every N parsed elements

def load_tvg_ids(filepath):
    with open(filepath, encoding="utf-8") as f:
        ids = [line.strip() for line in f if line.strip()]
    lower_ids = set(i.lower() for i in ids)
    return ids, lower_ids  # return original list and lowercase set

def download_epg_stream(url):
    print(f"📡 Downloading EPG (stream mode) from {url} ...")
    r = requests.get(url, headers=HEADERS, timeout=600, stream=True)
    r.raise_for_status()
    data = BytesIO()
    for chunk in r.iter_content(chunk_size=1024 * 512):
        if chunk:
            data.write(chunk)
    size_mb = data.tell() / 1024 / 1024
    data.seek(0)
    print(f"✅ Download complete ({size_mb:.1f} MB gzipped)")
    return data

def serialize_element(elem):
    """Return bytes containing the XML serialization of elem (including tail cleared)."""
    b = ET.tostring(elem, encoding="utf-8")
    return b

def filter_epg_stream(gz_data, wanted_ids_lower):
    print("🔍 Filtering by tvg-id (streaming write)...")
    kept_channel_ids = set()
    prog_counts = {}  # channel_id -> count
    total_parsed = 0
    total_programmes_written = 0
    total_channels_written = 0
    start = time.time()

    # Open output gz and write header and opening <tv>
    with gzip.open(OUTPUT_FILE, "wb") as out_gz:
        out_gz.write(b'<?xml version="1.0" encoding="utf-8"?>\n')
        out_gz.write(b"<tv>\n")

        # parse gz stream
        with gzip.GzipFile(fileobj=gz_data) as f:
            context = ET.iterparse(f, events=("end",))
            for event, elem in context:
                total_parsed += 1
                tag = elem.tag

                if tag == "channel":
                    cid_raw = elem.attrib.get("id", "")
                    cid = cid_raw.lower()
                    if cid in wanted_ids_lower:
                        # serialize & write this channel
                        out_gz.write(serialize_element(elem) + b"\n")
                        kept_channel_ids.add(cid_raw)
                        prog_counts[cid_raw] = 0
                        total_channels_written += 1
                    # clear to free memory
                    elem.clear()

                elif tag == "programme":
                    ch = elem.attrib.get("channel")
                    if ch in prog_counts:  # matched channel id (exact case)
                        out_gz.write(serialize_element(elem) + b"\n")
                        prog_counts[ch] += 1
                        total_programmes_written += 1
                    elem.clear()

                # progress logging
                if total_parsed % PROGRESS_EVERY == 0:
                    elapsed = time.time() - start
                    print(f"  parsed {total_parsed:,} elements — channels kept {len(kept_channel_ids)} — programmes written {total_programmes_written:,} — elapsed {elapsed:.0f}s")

        # write closing tag
        out_gz.write(b"</tv>\n")

    return {
        "channels_written": total_channels_written,
        "programmes_written": total_programmes_written,
        "kept_channel_ids": kept_channel_ids,
        "prog_counts": prog_counts,
        "elements_parsed": total_parsed
    }

def pretty_summary(original_ids, results):
    total_requested = len(original_ids)
    found = results["channels_written"]
    total_prog = results["programmes_written"]
    print("\n📊 Summary:")
    print(f"  • Requested tvg-ids (in {CHANNELS_FILE}): {total_requested}")
    print(f"  • Channels found & written: {found}")
    print(f"  • Programmes written: {total_prog:,}")
    print(f"  • Total XML elements parsed: {results['elements_parsed']:,}")

    # print top channels by programme count (desc), but only if >0 programmes
    counts = results["prog_counts"]
    if counts:
        print("\n  Top channels by programme count (up to 20):")
        sorted_counts = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        for ch, cnt in sorted_counts[:20]:
            print(f"    - {ch}: {cnt}")
    else:
        print("  No programme counts available.")

def main():
    if not os.path.exists(CHANNELS_FILE):
        print(f"❌ Missing {CHANNELS_FILE}. Please create it in the same folder.")
        return

    original_ids, wanted_ids_lower = load_tvg_ids(CHANNELS_FILE)
    print(f"📖 Loaded {len(original_ids)} tvg-ids from {CHANNELS_FILE}")

    gz_data = download_epg_stream(EPG_URL)
    results = filter_epg_stream(gz_data, wanted_ids_lower)

    # show size of produced file
    try:
        size_mb = os.path.getsize(OUTPUT_FILE) / 1024 / 1024
        print(f"\n💾 Saved filtered EPG to {OUTPUT_FILE} ({size_mb:.2f} MB)")
    except Exception:
        print(f"\n💾 Saved filtered EPG to {OUTPUT_FILE}")

    pretty_summary(original_ids, results)
    print("\n🎉 Done — your filtered EPG is ready!")

if __name__ == "__main__":
    main()
