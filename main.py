import requests
import json
import os
import urllib.parse

FOLDER_NAME = "__DLIVE__"
os.makedirs(FOLDER_NAME, exist_ok=True)

MAIN_API_URL = os.environ.get("MAIN_API_URL")
DECODE_API_URL = os.environ.get("DECODE_API_URL")
STREAM_BASE_URL = os.environ.get("STREAM_BASE_URL")

if not all([MAIN_API_URL, DECODE_API_URL, STREAM_BASE_URL]):
    print("Error: Missing Environment ")
    exit(1)

def fetch_and_decode_stream(slug, links_id):
    stream_url = f"{STREAM_BASE_URL}{slug}"
    print(f"    -> Fetching stream info for ID: {links_id}...")
    
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
        print(f" Error for stream {links_id}: {e}")
        return None

def process_and_merge_events(encoded_str_list):
    all_merged_events = []
    
    try:
        if isinstance(encoded_str_list, str):
            cleaned_str = encoded_str_list.replace('\n', '').replace('\r', '')
            item_list = json.loads(cleaned_str, strict=False)
        else:
            item_list = encoded_str_list
    except Exception as e:
        print(f"Error parsing event data: {e}")
        return

    for i, encoded_item in enumerate(item_list):
        if not isinstance(encoded_item, str): continue
            
        safe_url_param = urllib.parse.quote(encoded_item.strip())
        decode_api = f"{DECODE_API_URL}{safe_url_param}"
        
        print(f"\n")
        try:
            res = requests.get(decode_api, timeout=15)
            res.raise_for_status()
            decoded_events = res.json()
            
            if isinstance(decoded_events, list):
                for event_obj in decoded_events:
                    slug = event_obj.get("slug")
                    links_id = event_obj.get("links_id")
                    
                    if slug and links_id:
                        stream_data = fetch_and_decode_stream(slug, links_id)
                        if stream_data:
                            event_obj["stream_details"] = stream_data
                    all_merged_events.append(event_obj)
                        
        except Exception as e:
            print(f"Error decoding event chunk {i + 1}: {e}")

    if all_merged_events:
        final_file_path = os.path.join(FOLDER_NAME, "all_events_merged.json")
        with open(final_file_path, "w", encoding="utf-8") as f:
            json.dump(all_merged_events, f, indent=4, ensure_ascii=False)
        print(f"\n")

def process_categories(encoded_str_list):
    try:
        if isinstance(encoded_str_list, str):
            cleaned_str = encoded_str_list.replace('\n', '').replace('\r', '')
            item_list = json.loads(cleaned_str, strict=False)
        else:
            item_list = encoded_str_list
    except Exception:
        return

    for i, encoded_item in enumerate(item_list):
        if not isinstance(encoded_item, str): continue
        safe_url_param = urllib.parse.quote(encoded_item.strip())
        try:
            res = requests.get(f"{DECODE_API_URL}{safe_url_param}", timeout=15)
            with open(os.path.join(FOLDER_NAME, f"category_{i + 1}.json"), "w", encoding="utf-8") as f:
                json.dump(res.json(), f, indent=4, ensure_ascii=False)
        except Exception:
            pass

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

def main():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    print("Fetching main API...")
    try:
        response = requests.get(MAIN_API_URL, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        app_data = find_target_dictionary(data)
        
        if app_data:
            events_str = app_data.get("events", "[]")
            categories_str = app_data.get("categories", "[]")
            
            print("\n")
            process_and_merge_events(events_str)
            
            print("\n")
            process_categories(categories_str)
            print("Categories saved.")
        else:
            print("Could not find expected dictionary in response.")
            
    except Exception as e:
        print(f"Error connecting to main API: {e}")

if __name__ == "__main__":
    main()
