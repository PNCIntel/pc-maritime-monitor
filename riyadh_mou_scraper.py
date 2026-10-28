import os
import time
import hashlib
import pandas as pd
import requests

# The exact endpoint discovered in your DevTools Network tab
API_URL = "https://riyadhmou.org"
DATA_FOLDER = "data_exports"
CSV_FILE_PATH = os.path.join(DATA_FOLDER, "riyadh_mou_detentions.csv")

def create_unique_id(row):
    """Generates a deterministic unique hash key for deduplication."""
    # Maps typical column keys returned from the database
    imo = str(row.get("imo_number", row.get("imo", row.get("IMO", "")))).strip()
    ship_name = str(row.get("ship_name", row.get("Ship Name", ""))).strip()
    insp_date = str(row.get("inspection_date", row.get("Inspection Date", ""))).strip()
    
    unique_string = f"{imo}-{insp_date}-{ship_name}"
    return hashlib.md5(unique_string.encode('utf-8')).hexdigest()

def run_scraper():
    os.makedirs(DATA_FOLDER, exist_ok=True)
    all_records = []
    
    # Mirror standard browser request headers to prevent firewall blocks
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": "https://riyadhmou.org",
        "Referer": "https://riyadhmou.org"
    }

    # Form payload parameters matching WordPress dynamic table actions
    payload = {
        "action": "riyadh_mou_detentions",  # Target hook mapped from the admin-ajax calls
        "page": 1,
        "per_page": 20,
        "inspection_result": "Detained",
        "sort_by": "inspection_date",
        "sort_direction": "desc"
    }

    print("Connecting directly to the Riyadh MOU database API...")
    
    while True:
        print(f"Fetching data block from Page {payload['page']}...")
        try:
            # Send the request as form-encoded data (matching the XHR protocol)
            response = requests.post(API_URL, data=payload, headers=headers, timeout=10)
            
            if response.status_code != 200:
                print(f"API disconnected or returned an error status: {response.status_code}")
                break
                
            data = response.json()
            
            # Extract data rows depending on whether they are nested inside a data list or raw array
            records = data.get("data", data.get("rows", data if isinstance(data, list) else None))
            
            if not records or len(records) == 0:
                print("No more entries found. Tracking sequence complete.")
                break
                
            print(f"Successfully processed {len(records)} entries.")
            all_records.extend(records)
            
            # Check pagination metadata if returned by the API to break early
            total_pages = data.get("total_pages", data.get("last_page"))
            if total_pages and payload['page'] >= int(total_pages):
                print("Reached maximum page limit specified by backend metadata.")
                break
                
            # Increment to target the next page segment
            payload['page'] += 1
            time.sleep(1.5)  # Be polite to the port servers to avoid getting blacklisted
            
        except Exception as e:
            print(f"Encountered data layout error or parsing variance: {e}")
            break

    if not all_records:
        print("Pipeline failure: No records harvested from backend API.")
        return

    # Convert the JSON array into a Pandas Dataframe structure
    new_df = pd.DataFrame(all_records)
    
    # Apply change detection hash keys
    new_df['record_hash_id'] = new_df.apply(create_unique_id, axis=1)
    
    # Delta merge tracking (Upsert logic)
    if os.path.exists(CSV_FILE_PATH):
        print("Merging with existing tracking archives...")
        existing_df = pd.read_csv(CSV_FILE_PATH)
        combined_df = pd.concat([new_df, existing_df], ignore_index=True)
        final_df = combined_df.drop_duplicates(subset=['record_hash_id'], keep='first')
        print(f"Database synchronized. Total unique trackable vessels logged: {len(final_df)}")
    else:
        final_df = new_df
        print(f"New system master file created with {len(final_df)} baseline vessels.")
        
    final_df.to_csv(CSV_FILE_PATH, index=False)
    print(f"Data saved securely to file path: {CSV_FILE_PATH}")

if __name__ == "__main__":
    run_scraper()
