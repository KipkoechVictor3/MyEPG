import requests
import json

M3U_URL = "https://bit.ly/47dWcV1"
OUTPUT_FILE = "modified_playlist.m3u"
MAPPING_FILE = "channel_mapping.json"

def load_mapping():
    with open(MAPPING_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def update_m3u():
    mapping = load_mapping()
    m3u_lines = requests.get(M3U_URL).text.splitlines()
    output_lines = []

    for i, line in enumerate(m3u_lines):
        if line.startswith("#EXTINF"):
            name_after_comma = line.split(",", 1)[1].strip()
            if name_after_comma in mapping:
                new_id = mapping[name_after_comma]["tvg-id"]
                logo = mapping[name_after_comma]["logo"]

                if 'tvg-id="' in line:
                    line = line.replace(f'tvg-id="{line.split("tvg-id=")[1].split("\"")[0]}"', f'tvg-id="{new_id}"')
                else:
                    line = line.replace("#EXTINF:-1", f'#EXTINF:-1 tvg-id="{new_id}"')

                if logo and 'tvg-logo="' not in line:
                    line = line.replace(f'tvg-id="{new_id}"', f'tvg-id="{new_id}" tvg-logo="{logo}"')

        output_lines.append(line)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))

if __name__ == "__main__":
    update_m3u()
