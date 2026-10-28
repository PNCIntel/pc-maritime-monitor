"""Small, read-only Riyadh MoU detention-page connectivity experiment.

This page is intentionally isolated from the P&C database and other apps.
Only fetches ONE public page; does not crawl or write data.
"""
from __future__ import annotations

from datetime import datetime, timezone
from io import StringIO
import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup

URL = "https://riyadhmou.org/detention-list/"

st.set_page_config(page_title="Riyadh MoU | Test", layout="wide")
st.title("Riyadh MoU — Detention Data Test")
st.caption("Maritime Monitor experiment • read-only • one page • no Supabase writes")
st.info("This is a connectivity/HTML extraction test, not an approved commercial ingestion feed. Please check Riyadh MoU usage terms before automated bulk collection.")
st.markdown(f"[Open source detention list]({URL})")
st.write("Click **Fetch one page** to check connectivity and see whether the public HTML includes detention rows.")

def analyse(html: str):
    soup = BeautifulSoup(html, "html.parser")
    all_tables = soup.find_all("table")
    summary = []
    frames = []
    for i, table in enumerate(all_tables):
        try:
            df = pd.read_html(StringIO(str(table)))[0]
            df.columns = [str(c).strip() for c in df.columns]
            summary.append({"table": i + 1, "rows": len(df), "columns": ", ".join(df.columns)[:220]})
            if len(df):
                frames.append((i + 1, df))
        except (ValueError, ImportError) as exc:
            summary.append({"table": i + 1, "rows": 0, "columns": f"not parsed: {exc}"})
    return soup, summary, frames

if st.button("Fetch one page", type="primary"):
    with st.spinner("Contacting Riyadh MoU..."):
        try:
            response = requests.get(URL, timeout=25, headers={"User-Agent": "P&C Maritime Monitor research test (read-only; contact administrator)"})
            fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            st.write({"status_code": response.status_code, "final_url": response.url, "fetched_utc": fetched_at, "html_bytes": len(response.content)})
            response.raise_for_status()
            soup, summary, frames = analyse(response.text)
            st.subheader("HTML table discovery")
            if summary:
                st.dataframe(pd.DataFrame(summary), use_container_width=True, hide_index=True)
            else:
                st.warning("No HTML tables returned. The detention results may require the site's Search/Apply action or JavaScript. This does NOT mean there are no detentions.")
            st.subheader("Extracted data preview")
            if frames:
                selected = st.selectbox("Table", [idx for idx, _ in frames])
                df = next(df for idx, df in frames if idx == selected)
                st.dataframe(df.head(100), use_container_width=True)
                st.download_button("Download this one-page test CSV", df.to_csv(index=False).encode("utf-8"), "riyadh_mou_test_page.csv", mime="text/csv")
                st.caption("Preview is unverified raw site data. Validate table headers and records before using it.")
            else:
                st.info("No parsed rows on initial GET. The existing Playwright scraper may be needed to click Search/Apply before results appear.")
            with st.expander("Diagnostics — page title and form controls"):
                st.write("Page title:", soup.title.get_text(" ", strip=True) if soup.title else "(none)")
                st.write("Forms:", len(soup.find_all("form")), "Tables:", len(soup.find_all("table")))
                st.write("Buttons:", [b.get_text(" ", strip=True) or b.get("value") for b in soup.find_all(["button", "input"]) if b.name == "button" or b.get("type") in ("submit","button")][:25])
        except requests.RequestException as exc:
            st.error(f"Request failed: {exc}")
            st.write("The source may block automated access or be temporarily unavailable. No data was saved.")
