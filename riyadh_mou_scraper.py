import os
import json
import time
import hashlib
import pandas as pd
from playwright.sync_api import sync_playwright

# Configuration
URL = "https://riyadhmou.org"
DATA_FOLDER = "data_exports"
CSV_FILE_PATH = os.path.join(DATA_FOLDER, "riyadh_mou_detentions.csv")

# Global placeholder to catch the intercepted API payloads
intercepted_data_records = []

def create_unique_id(row):
    """Generates a deterministic unique hash using the exact structural keys."""
    imo = str(row.get("IMO", row.get("imo_number", row.get("imo", "")))).strip()
    ship_name = str(row.get("Ship Name", row.get("ship_name", ""))).strip()
    insp_date = str(row.get("Inspection Date", row.get("inspection_date", ""))).strip()
    
    if not imo and not ship_name:
        return "invalid_row_" + str(time.time())
        
    unique_string = f"{imo}-{insp_date}-{ship_name}"
    return hashlib.md5(unique_string.encode('utf-8')).hexdigest()

def handle_response(response):
    """Network interceptor that filters responses for admin-ajax requests."""
    global intercepted_data_records
    
    if "admin-ajax.php" in response.url:
        try:
            # Check if the content type is valid JSON
            content_type = response.headers.get("content-type", "")
            if "application/json" in content_type or "text/javascript" in content_type:
                json_data = response.json()
                
                # Dig down into common WordPress AJAX return blocks
                records = json_data.get("data", json_data.get("rows", None))
                
                # Fallback if the data is just the root object or an array
                if records is None and isinstance(json_data, list):
                    records = json_data
                elif records is None and isinstance(json_data, dict):
                    # Loop down keys to see if an inner array holds our rows
                    for key, val in json_data.items():
                        if isinstance(val, list) and len(val) > 0:
                            records = val
                            break
                            
                if records and len(records) > 0:
                    print(f"[Network Sniffer] Intercepted {len(records)} live rows from data stream.")
                    intercepted_data_records.extend(records)
        except Exception:
            # Pass over non-JSON responses gracefully (like administrative HTML chunks)
            pass

def scrape_hybrid_pipeline():
    global intercepted_data_records
    intercepted_data_records = [] # Reset local matrix
    os.makedirs(DATA_FOLDER, exist_ok=True)
    
    with sync_playwright() as p:
        print("Launching automated browser instance...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1440, "height": 900}
        )
        page = context.new_page()
        
        # Attach the network sniffing event handler
        page.on("response", handle_response)
        
        print(f"Navigating to browser portal: {URL}")
        page.goto(URL, wait_until="networkidle")
        
        # Force activate button index 5 ("Apply") as flagged in your diagnostics log
        apply_button = page.locator("button:has-text('Apply'), input[type='button'][value='Apply']")
        if apply_button.count() > 0:
            print("Clicking 'Apply' button to trigger session authentication...")
            apply_button.first.click()
            page.wait_for_timeout(5000)  # Allow ample processing time for backend authentication
        else:
            # Fallback tracking if text matching misses
            print("Targeting button nodes via class attributes...")
            page.locator("button").nth(5).click()
            page.wait_for_timeout(5000)
            
        page_num = 1
        while True:
            print(f"Tracking Page Loop Index: {page_num}")
            
            # Locate the exact next pagination button chevron (`›`) seen on the platform layout
            next_button = page.locator("a:has-text('›'), .pagination-next, li.next a")
            
            if next_button.count() > 0 and next_button.first.is_visible() and next_button.first.is_enabled():
                print("Clicking next chevron to populate next data segment...")
                next_button.first.click()
                page.wait_for_timeout(4000)  # Rate limit safely to avoid firewall triggers
                page_num += 1
                
                # Quick circuit breaker protection for local testing
                if page_num > 5: 
                    print("Reached limit threshold for verification block.")
                    break
            else:
                print("No more clickable navigation chevrons available.")
                break
                
        browser.close()

    if not intercepted_data_records:
        print("Pipeline Failure: No background JSON streams captured. Check field parameters.")
        return

    # Convert captured JSON array directly into an organized DataFrame layout
    master_df = pd.DataFrame(intercepted_data_records)
    
    # Calculate tracking hashes to maintain consistency
    master_df['record_hash_id'] = master_df.apply(create_unique_id, axis=1)
    master_df = master_df[~master_df['record_hash_id'].str.startswith('invalid_row_')]
    
    # Deduplicate and merge with local CSV log
    if os.path.exists(CSV_FILE_PATH):
        print("Synchronizing data array with existing logs...")
        existing_df = pd.read_csv(CSV_FILE_PATH)
        combined_df = pd.concat([master_df, existing_df], ignore_index=True)
        final_df = combined_df.drop_duplicates(subset=['record_hash_id'], keep='first')
        print(f"Merge operation complete. Total unique records tracked: {len(final_df)}")
    else:
        final_df = master_df
        print(f"Fresh tracking catalog written with {len(final_df)} baseline entries.")
        
    final_df.to_csv(CSV_FILE_PATH, index=False)
    print(f"Data saved successfully to local file path: {CSV_FILE_PATH}")

if __name__ == "__main__":
    scrape_hybrid_pipeline()
