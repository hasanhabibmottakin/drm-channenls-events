import requests
import json
import os
import urllib.parse

FOLDER_NAME = "__DLIVE__"
os.makedirs(FOLDER_NAME, exist_ok=True)

MAIN_API_URL = os.environ.get("MAIN_API_URL")
DECODE_API_URL = os.environ.get("DECODE_API_URL")
STREAM_BASE_URL = os.environ.get("STREAM_BASE_URL")

SECOND_API_URL = os.environ.get("SECOND_API_URL")
SECOND_STREAM_BASE = os.environ.get("SECOND_STREAM_BASE")

if not all([MAIN_API_URL, DECODE_API_URL, STREAM_BASE_URL, SECOND_API_URL, SECOND_STREAM_BASE]):
    print("Error: Missing Environment Variables")
    exit(1)

if not STREAM_BASE_URL.endswith('/'):
    STREAM_BASE_URL += '/'
    
if not SECOND_STREAM_BASE.endswith('/'):
    SECOND_STREAM_BASE += '/'

def fetch_and_decode_stream(slug, identifier, base_url):
    stream_url = slug if slug.startswith("http") else f"{base_url}{slug}"
    print(f"    -> Fetching stream info for: {identifier}...")
    
    try:
        res = requests.get(stream_url, timeout=15)
        res.raise_for_status()
        stream_data = res.json()
        
        encoded_links = stream_data.get("links", "")
        if not encoded_links:
            return None
            
        clean_links = encoded_links.replace('\n', '').replace('\r', '').strip()
        safe_url_param = urllib.parse.quote(clean_links)
        decode_api = f"{DECODE_API_URL}{safe_url_param}"
        
        dec_res = requests.get(decode_api, timeout=15)
        dec_res.raise_for_status()
        return dec_res.json()
        
    except Exception as e:
        print(f"Error for stream {identifier}: {e}")
        return None

def process_and_merge_events(encoded_str_list, base_url):
    all_merged_events = []
    
    try:
        if isinstance(encoded_str_list, str):
            cleaned_str = encoded_str_list.replace('\n', '').replace('\r', '')
            item_list = json.loads(cleaned_str, strict=False)
        else:
            item_list = encoded_str_list
    except Exception as e:
        print(f"Error parsing event data: {e}")
        return []

    for i, encoded_item in enumerate(item_list):
        if not isinstance(encoded_item, str): continue
            
        safe_url_param = urllib.parse.quote(encoded_item.strip())
        decode_api = f"{DECODE_API_URL}{safe_url_param}"
        
        print(f"\nDecoding event chunk {i + 1}...")
        try:
            res = requests.get(decode_api, timeout=15)
            res.raise_for_status()
            decoded_events = res.json()
            
            if isinstance(decoded_events, list):
                for event_obj in decoded_events:
                    slug = event_obj.get("slug")
                    links_id = event_obj.get("links_id")
                    
                    if slug and links_id:
                        stream_data = fetch_and_decode_stream(slug, links_id, base_url)
                        if stream_data:
                            event_obj["stream_details"] = stream_data
                    all_merged_events.append(event_obj)
                        
        except Exception as e:
            print(f"Error decoding event chunk {i + 1}: {e}")

    return all_merged_events

def process_and_merge_sports(sports_slug, base_url):
    if not sports_slug: return []
    
    sports_url = sports_slug if sports_slug.startswith("http") else f"{base_url}{sports_slug}"
    all_merged_sports = []
    
    print(f"\nFetching sports data from: {sports_url}")
    try:
        res = requests.get(sports_url, timeout=15)
        res.raise_for_status()
        sports_list = res.json()
        
        if not isinstance(sports_list, list):
            print("Sports data is not a list.")
            return []

        for i, item in enumerate(sports_list):
            encoded_channel = item.get("channel", "")
            if not encoded_channel:
                continue
                
            clean_channel = encoded_channel.replace('\n', '').replace('\r', '').strip()
            safe_url_param = urllib.parse.quote(clean_channel)
            decode_api = f"{DECODE_API_URL}{safe_url_param}"
            
            print(f"Decoding sports channel chunk {i + 1}...")
            dec_res = requests.get(decode_api, timeout=15)
            dec_res.raise_for_status()
            decoded_channels = dec_res.json()
            
            if isinstance(decoded_channels, list):
                for channel_obj in decoded_channels:
                    slug = channel_obj.get("links")
                    channel_name = channel_obj.get("name", f"Sport_{i}")
                    
                    if slug:
                        stream_data = fetch_and_decode_stream(slug, channel_name, base_url)
                        if stream_data:
                            channel_obj["stream_details"] = stream_data
                    all_merged_sports.append(channel_obj)
            
        return all_merged_sports

    except Exception as e:
        print(f"Error processing sports data: {e}")
        return []

def process_categories(encoded_str_list, start_index=1):
    try:
        if isinstance(encoded_str_list, str):
            cleaned_str = encoded_str_list.replace('\n', '').replace('\r', '')
            item_list = json.loads(cleaned_str, strict=False)
        else:
            item_list = encoded_str_list
    except Exception:
        return start_index

    for i, encoded_item in enumerate(item_list):
        if not isinstance(encoded_item, str): continue
        safe_url_param = urllib.parse.quote(encoded_item.strip())
        try:
            res = requests.get(f"{DECODE_API_URL}{safe_url_param}", timeout=15)
            with open(os.path.join(FOLDER_NAME, f"category_{start_index + i}.json"), "w", encoding="utf-8") as f:
                json.dump(res.json(), f, indent=4, ensure_ascii=False)
        except Exception:
            pass
            
    return start_index + len(item_list)

def find_target_dictionary(data):
    queue = [data]
    while queue:
        current = queue.pop(0)
        if isinstance(current, dict):
            if "events" in current or "categories" in current:
                return current
        elif isinstance(current, list):
            queue.extend(current)
    return None

def fetch_api_data(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        return find_target_dictionary(response.json())
    except Exception as e:
        print(f"Error connecting to API ({url}): {e}")
        return None

def main():
    print("Fetching 1st API (Main)...")
    app_data_1 = fetch_api_data(MAIN_API_URL)
    
    print("Fetching 2nd API (Pro)...")
    app_data_2 = fetch_api_data(SECOND_API_URL)

    all_combined_events = []
    all_combined_sports = []
    category_index = 1 

    if app_data_1:
        print("\n=== Processing 1st API Data ===")
        events_1 = process_and_merge_events(app_data_1.get("events", "[]"), STREAM_BASE_URL)
        if events_1: all_combined_events.extend(events_1)
        
        sports_1 = process_and_merge_sports(app_data_1.get("sports_slug", ""), STREAM_BASE_URL)
        if sports_1: all_combined_sports.extend(sports_1)
        
        category_index = process_categories(app_data_1.get("categories", "[]"), category_index)
    else:
        print("\nCould not find expected dictionary in 1st API response.")

    if app_data_2:
        print("\n=== Processing 2nd API Data ===")
        events_2 = process_and_merge_events(app_data_2.get("events", "[]"), SECOND_STREAM_BASE)
        if events_2: all_combined_events.extend(events_2)
        
        sports_2 = process_and_merge_sports(app_data_2.get("sports_slug", ""), SECOND_STREAM_BASE)
        if sports_2: all_combined_sports.extend(sports_2)
        
        category_index = process_categories(app_data_2.get("categories", "[]"), category_index)
    else:
        print("\nCould not find expected dictionary in 2nd API response.")

    if all_combined_events:
        final_events_path = os.path.join(FOLDER_NAME, "all_events.json")
        with open(final_events_path, "w", encoding="utf-8") as f:
            json.dump(all_combined_events, f, indent=4, ensure_ascii=False)
        print(f"\nSuccessfully saved ALL merged events ({len(all_combined_events)} items) to: {final_events_path}")

    if all_combined_sports:
        final_sports_path = os.path.join(FOLDER_NAME, "sports_channels.json")
        with open(final_sports_path, "w", encoding="utf-8") as f:
            json.dump(all_combined_sports, f, indent=4, ensure_ascii=False)
        print(f"Successfully saved ALL merged sports channels ({len(all_combined_sports)} items) to: {final_sports_path}")

    print("\nAll categories saved successfully!")

if __name__ == "__main__":
    main()
