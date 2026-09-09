# P&C Trade System v1.25 — GitHub / Streamlit Split-Excel Deployment

Upload the contents of this package to the repository root.

Structure:

- app.py
- requirements.txt
- data_manifest.json
- data/
  - 01_core_entities.xlsx
  - 02_maritime.xlsx
  - 03_rail.xlsx
  - 04_road_trucking.xlsx
  - 05_aviation.xlsx
  - 06_infrastructure.xlsx
  - 07_corporate_markets.xlsx
  - 08_transactions.xlsx
  - 09_intelligence.xlsx
  - 10_sources_evidence.xlsx

The Streamlit app reads each logical table from the appropriate Excel workbook and sheet.
The CSV fallback remains temporarily for backwards compatibility.

This is the v1.25 theory/stress-test model before Supabase migration.
