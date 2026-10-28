import os
import time
import hashlib
import pandas as pd
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# Configuration
URL = "https://riyadhmou.org/detention-list/"
DATA_FOLDER = "data_exports"
CSV_FILE_PATH = os.path.join(DATA_FOLDER, "riyadh_mou_detentions.csv")

def create_unique_id(row):
    """
    Generates a deterministic unique hash using the exact column keys 
    visible on the Riyadh MOU live table interface.
    """
    # Exact keys mapped directly from the website's HTML headers
    imo = str(row.get("IMO", "")).strip()
    ship_name = str(row.get("Ship Name", "")).strip()
    insp_date = str(row.get("Inspection Date", "")).strip()
    
    # Fallback to prevent hashing blank lines
    if not imo and not ship_name:
        return "invalid_row_" + str(time.time())
        
    unique_string = f"{imo}-{insp_date}-{ship_name}"
    return hashlib.md5(unique_string.encode('utf-8')).hexdigest()

def extract_table_data(html_content):
    """Parses the active data matrix using targeted cleanups."""
    soup = BeautifulSoup(html_content, "lxml")
    table = soup.find("table")
    
    if not table:
        return None
        
    try:
        df_list = pd.read_html(str(table))
        if df_list:
            df = df_list[0]
            # Normalize column text to clean trailing invisible characters
            df.columns = [str(col).strip() for col in df.columns]
            return df
    except Exception as e:
        print(f"Error compiling table block: {e}")
    return None

def scrape_pipeline():
    os.makedirs(DATA_FOLDER, exist_ok=True)
    all_pages_data = []
    
    with sync_playwright() as p:
        # Launch browser context mimicking a standard browser footprint
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1440, "height": 900}
        )
        page = context.new_page()
        
        print(f"Connecting to: {URL}")
        page.goto(URL, wait_until="networkidle")
        
        # Click the 'Apply' button to force trigger the AJAX table content load
        apply_button = page.locator("button:has-text('Apply')")
        if apply_button.count() > 0:
            print("Applying filter constraints...")
            apply_button.first.click()
            page.wait_for_timeout(5000) # Give the system full time to load the background content
            
        page_num = 1
        while True:
            print(f"Processing Page {page_num}...")
            
            # Scrape active view frame state
            current_html = page.content()
            df_page = extract_table_data(current_html)
            
            if df_page is not None and not df_page.empty:
                # Remove empty placeholder entries
                df_page = df_page.dropna(subset=['IMO'], errors='ignore')
                all_pages_data.append(df_page)
                print(f"Successfully retrieved {len(df_page)} rows.")
            else:
                print("End of tracking history reached or page table unreadable.")
                break
                
            # Locate the exact nested dynamic arrow pagination icon seen in the screenshot
            next_button = page.locator("a:has-text('›'), .pagination-next, li.next a")
            
            if next_button.count() > 0 and next_button.first.is_visible() and next_button.first.is_enabled():
                print("Advancing to next table page...")
                next_button.first.click()
                page.wait_for_timeout(4000) # Rate limit safely
                page_num += 1
            else:
                print("No further pages accessible.")
                break
                
        browser.close()
        
    if not all_pages_data:
        print("Pipeline execution failed: No matrix data extracted.")
        return

    # Consolidate frames
    master_df = pd.concat(all_pages_data, ignore_index=True)
    master_df.dropna(how='all', inplace=True)
    
    # Apply structural unique ID
    master_df['record_hash_id'] = master_df.apply(create_unique_id, axis=1)
    # Remove any broken rows
    master_df = master_df[~master_df['record_hash_id'].str.startswith('invalid_row_')]
    
    # Update local archive
    if os.path.exists(CSV_FILE_PATH):
        print("Merging with historical data ledger...")
        existing_df = pd.read_csv(CSV_FILE_PATH)
        combined_df = pd.concat([master_df, existing_df], ignore_index=True)
        final_df = combined_df.drop_duplicates(subset=['record_hash_id'], keep='first')
        print(f"Update finished. Total logged tracking database rows: {len(final_df)}")
    else:
        final_df = master_df
        print(f"New tracking database initialized with {len(final_df)} entries.")
        
    final_df.to_csv(CSV_FILE_PATH, index=False)
    print(f"Data saved successfully to: {CSV_FILE_PATH}")

if __name__ == "__main__":
    scrape_pipeline()
