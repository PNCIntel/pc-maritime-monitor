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
    Generates a deterministic unique hash for change detection.
    Prevents duplicates by combining key static values.
    """
    # Fallback strings if fields are empty
    imo = str(row.get("IMO number", row.get("IMO Number", ""))).strip()
    insp_date = str(row.get("Inspection date", row.get("Inspection Date", ""))).strip()
    ship_name = str(row.get("Ship name", row.get("Ship Name", ""))).strip()
    
    unique_string = f"{imo}-{insp_date}-{ship_name}"
    return hashlib.md5(unique_string.encode('utf-8')).hexdigest()

def extract_table_data(html_content):
    """Parses a single page's HTML structure for data rows."""
    soup = BeautifulSoup(html_content, "lxml")
    table = soup.find("table")
    
    if not table:
        return None
        
    try:
        # Read HTML tables natively into list of DataFrames
        df_list = pd.read_html(str(table))
        if df_list:
            df = df_list[0]
            # Strip potential whitespace from columns
            df.columns = [str(col).strip() for col in df.columns]
            return df
    except Exception as e:
        print(f"Error compiling table block: {e}")
    return None

def scrape_pipeline():
    os.makedirs(DATA_FOLDER, exist_ok=True)
    all_pages_data = []
    
    with sync_playwright() as p:
        # Launch browser context mimicking standard human headers
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()
        
        print(f"Navigating to: {URL}")
        page.goto(URL, wait_until="networkidle")
        
        # Trigger the query submission panel if required by the state
        search_button = page.locator("button:has-text('Search'), input[type='submit'][value='Search'], button:has-text('Apply')")
        if search_button.count() > 0:
            print("Activating data filters...")
            search_button.first.click()
            page.wait_for_timeout(4000) # Give AJAX elements plenty of room to assemble
            
        page_num = 1
        while True:
            print(f"Processing Page {page_num}...")
            
            # Scrape the active page layout
            current_html = page.content()
            df_page = extract_table_data(current_html)
            
            if df_page is not None and not df_page.empty:
                all_pages_data.append(df_page)
                print(f"Successfully retrieved {len(df_page)} records.")
            else:
                print("No data records visible or end of records reached.")
                break
                
            # Handle Pagination safely
            # Locates standard layout pagination links (e.g., 'Next', '>', or sequential anchors)
            next_button = page.locator("a:has-text('Next'), a:has-text('›'), .pagination-next, .next a")
            
            # Check if a clickable, valid Next element exists
            if next_button.count() > 0 and next_button.first.is_visible() and next_button.first.is_enabled():
                print("Moving to subsequent ledger index...")
                next_button.first.click()
                page.wait_for_timeout(3000) # Rate limit politely to guard against server firewall triggers
                page_num += 1
            else:
                print("Terminal list iteration achieved. Finalizing ledger aggregation...")
                break
                
        browser.close()
        
    if not all_pages_data:
        print("Pipeline execution failed: No matrix data extracted.")
        return

    # Master list generation
    master_df = pd.concat(all_pages_data, ignore_index=True)
    master_df.dropna(how='all', inplace=True)
    
    # Apply unique cryptographic tracking ID to map incoming data rows
    master_df['record_hash_id'] = master_df.apply(create_unique_id, axis=1)
    
    # Intelligent Change-Detection (Upsert Logic)
    if os.path.exists(CSV_FILE_PATH):
        print("Existing database found. Merging tracking nodes...")
        existing_df = pd.read_csv(CSV_FILE_PATH)
        
        # Combine records and drop rows matching identical tracking IDs, preserving newest records
        combined_df = pd.concat([master_df, existing_df], ignore_index=True)
        final_df = combined_df.drop_duplicates(subset=['record_hash_id'], keep='first')
        new_records = len(final_df) - len(existing_df)
        print(f"Database update complete. Logged {new_records} completely new vessel detentions.")
    else:
        final_df = master_df
        print(f"Fresh database established with {len(final_df)} base entries.")
        
    final_df.to_csv(CSV_FILE_PATH, index=False)
    print(f"Master file saved securely at: {CSV_FILE_PATH}")

if __name__ == "__main__":
    start_time = time.time()
    scrape_pipeline()
    print(f"Pipeline finished in {round(time.time() - start_time, 2)} seconds.")
