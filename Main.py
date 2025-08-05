import asyncio
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError
import json
import os
from datetime import datetime, timezone, timedelta
import re
import httpx

async def generate_filtered_timstreams_playlist():
    """
    Fetches channel data from TimStreams API, filters events by specified genre IDs,
    and includes events that have a time attribute, explicitly excluding "24/7" categories.
    It then visits embed URLs to derive M3U8 links with necessary HTTP headers,
    and appends the playlist content to 'fstv.m3u8' with specific formatting,
    including multiple streams with their respective labels if available.
    """
    playlist_entries = []
    api_url = "https://timstreams.cipkbcg8mja9tleutkr2j9.website/main" 

    TARGET_GENRE_IDS = [1, 2, 3] # Example: 1 for Soccer, 2 for Motorsport

    GENRE_MAP = {
        1: "Soccer",
        2: "Motorsport",
        3: "MMA (Mixed Martial Arts)",
    }

    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True), args=["--no-sandbox"])
        context = await browser.new_context()
        page = await context.new_page()

        print("Step 1: Fetching channel data from TimStreams API...")
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                print(f"  Fetching API data directly from: {api_url}")
                response = await client.get(api_url)
                response.raise_for_status()
                categories = response.json()

            print("\n--- Full Parsed JSON Content from API ---")
            print(json.dumps(categories, indent=2))
            print("--- End of Full Parsed JSON Content ---\n")
            
            if not categories:
                print("Error: No categories found in the API response.")
                return "\n# No categories found.\n"

            print(f"Filtering for genres: {', '.join(str(g) for g in TARGET_GENRE_IDS)}")
            found_events_count = 0

            current_utc_time = datetime.now(timezone.utc)
            print(f"Current UTC time: {current_utc_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")

            for category in categories:
                category_name = category.get('category')

                # Skip 24/7 categories as requested
                if category_name and category_name.lower() == '24/7':
                    print(f"  Skipping category: '{category_name}' (24/7 channels are excluded).")
                    continue

                events = category.get('events')
                if events:
                    for event in events:
                        channel_genre_id = event.get('genre')

                        if channel_genre_id in TARGET_GENRE_IDS: # Filter by genre ID
                            event_time_str = event.get('time')
                            if event_time_str: # Check for valid time attribute
                                try:
                                    event_time = datetime.strptime(event_time_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
                                except ValueError:
                                    print(f"  Warning: Could not parse time for event '{event.get('name', 'Unnamed Event')}': {event_time_str}, skipping.")
                                    continue
                            else:
                                print(f"  Warning: No time information for event '{event.get('name', 'Unnamed Event')}', skipping.")
                                continue

                            channel_name = event.get('name')
                            channel_logo = event.get('logo')
                            stream_details = event.get('streams') # This is now a list of all streams for the event

                            if not channel_name or not stream_details or not isinstance(stream_details, list) or not stream_details:
                                print(f"Skipping incomplete or invalid stream data for event: {event.get('name', 'Unnamed Event')}")
                                continue

                            # --- MODIFICATION START ---
                            for stream in stream_details:
                                stream_url = stream.get('url')
                                stream_label = stream.get('label') # Get the label for the current stream

                                if not stream_url:
                                    print(f"  Skipping stream for event '{channel_name}' due to missing URL.")
                                    continue

                                final_m3u8_link = None
                                intercepted_origin = None 
                                intercepted_referrer = None
                                intercepted_user_agent = None

                                print(f"  Attempting to get full M3U8 URL with token for {channel_name} (Label: {stream_label or 'N/A'}) from {stream_url}")
                                try:
                                    async with page.expect_response(
                                        lambda response: ".m3u8" in response.url and "?auth=" in response.url and response.status == 200,
                                        timeout=60000
                                    ) as response_event:
                                        await page.goto(stream_url, wait_until="domcontentloaded", timeout=60000)

                                    response = await response_event.value

                                    final_m3u8_link = response.url

                                    intercepted_origin = response.request.headers.get("origin")
                                    intercepted_referrer = response.request.headers.get("referer")
                                    intercepted_user_agent = response.request.headers.get("user-agent")

                                    print(f"  Successfully retrieved full M3U8 URL for '{channel_name}' (Label: {stream_label or 'N/A'}): {final_m3u8_link}")
                                    print(f"  Intercepted Headers - Origin: {intercepted_origin}, Referrer: {intercepted_referrer}, User-Agent: {intercepted_user_agent}")

                                except PlaywrightTimeoutError:
                                    print(f"  Timeout retrieving full M3U8 URL for '{channel_name}' (Label: {stream_label or 'N/A'}). Stream request not found within the increased timeout.")
                                    continue
                                except PlaywrightError as pe:
                                    print(f"  Playwright error retrieving full M3U8 URL for '{channel_name}' (Label: {stream_label or 'N/A'}): {pe}")
                                    continue
                                except Exception as e:
                                    print(f"  Other error retrieving full M3U8 URL for '{channel_name}' (Label: {stream_label or 'N/A'}): {e}")
                                    continue

                                if final_m3u8_link:
                                    found_events_count += 1
                                    channel_genre_name = GENRE_MAP.get(channel_genre_id, f"Genre ID {channel_genre_id}")

                                    display_name = f"{channel_genre_name} ✦ {channel_name}"
                                    if stream_label: # Append label if it exists
                                        display_name += f" ✦ {stream_label}"

                                    extinf_line = f'#EXTINF:-1 group-title="Timstreams Live"'
                                    if channel_logo:
                                        extinf_line += f' tvg-logo="{channel_logo}"'
                                    extinf_line += f', {display_name}'
                                    playlist_entries.append(extinf_line)

                                    if intercepted_origin:
                                        playlist_entries.append(f'#EXTVLCOPT:http-origin={intercepted_origin}')
                                    if intercepted_referrer:
                                        playlist_entries.append(f'#EXTVLCOPT:http-referrer={intercepted_referrer}')
                                    if intercepted_user_agent:
                                        playlist_entries.append(f'#EXTVLCOPT:http-user-agent={intercepted_user_agent}')

                                    playlist_entries.append(final_m3u8_link)
                                else:
                                    print(f"  Could not determine a valid M3U8 stream link for {channel_name} (Genre {channel_genre_id}, Label: {stream_label or 'N/A'}).")
                            # --- MODIFICATION END ---

            if found_events_count == 0:
                print("No events found matching the target genre IDs and having a time attribute.")
                return "\n# No matching events found for the specified genres and time criteria.\n"
            else:
                print(f"\nFound {found_events_count} events matching the target genre IDs and having a time attribute.")

        except httpx.HTTPStatusError as e:
            print(f"HTTP error fetching API data: {e.response.status_code} - {e.response.text}")
            return f"\n# Error generating playlist: HTTP error fetching API data: {e.response.status_code}\n"
        except httpx.RequestError as e:
            print(f"Network error fetching API data: {e}")
            return f"\n# Error generating playlist: Network error fetching API data: {e}\n"
        except json.JSONDecodeError as e:
            print(f"Error decoding API response JSON: {e}")
            return f"\n# Error generating playlist: JSON decoding error\n"
        except Exception as e:
            print(f"An unexpected error occurred during data fetching or processing: {e}")
            return f"\n# Error generating playlist: {e}\n"
        finally:
            await browser.close()

    output_filename = "fstv.m3u8"
    try:
        with open(output_filename, "a", encoding="utf-8") as f:
            f.write("\n\n\n\n\n")           
            f.write('                                             ###########################################################################\n')
            f.write('                                             ###########                     TIMSTREAMS                   ##############\n')
            f.write('                                             ###########################################################################\n')
            f.write('\n\n\n\n')
            # Only write #EXTM3U if the file is empty at the start of the write operation
            if os.path.getsize(output_filename) == 0 or f.tell() == 0:
                 f.write("#EXTM3U\n")

            for line in playlist_entries:
                f.write(line + "\n")
        print(f"\n--- Filtered TimStreams Live playlist appended to {output_filename} ---")
        print(f"You can find the file '{output_filename}' in the same directory where this script is executed.")
    except Exception as e:
        print(f"\nError appending playlist to file: {e}")
        print("\n--- Generated Filtered M3U Playlist (printed to console due to file append error) ---\n")
        print("#EXTM3U\n" + "\n".join(playlist_entries))
        print("\n--- End of Playlist ---")

    return ""

if __name__ == "__main__":
    asyncio.run(generate_filtered_timstreams_playlist())