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

## v1.25.1 enrichment
- Inocea: Davie, Helsinki Shipyard, Gulf Copper, Sata Shipbuilding, Davie Defense and Federal Fleet Services.
- CLI: Itaqui added as a canonical port; CLI Norte and CLI Sul added as actual terminal records linked to Itaqui and Santos.
- Seaspan: searchable company/alias handling, Entity Registry coverage, fleet portfolio and ten official operating-fleet examples.
- News: additional entity-linked Inocea, Seaspan, CLI, Macquarie/Qube and AD Ports records.
- AD Ports Group: 24 official monthly share-price observations for 2024–2025 plus an in-app price chart.
