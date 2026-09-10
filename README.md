# P&C Trade System v2.4

This is the Excel-backed test implementation of the Power & Corridors Trade System ahead of the planned PostgreSQL migration. It preserves the 14 canonical domain workbooks while adding live public API layers for operational, maritime-safety and global-signal testing.

## Repository layout

- `app.py` — Streamlit application
- `data/` — 14 canonical domain workbooks (model v1.34)
- `data_manifest.json` — workbook and sheet routing contract
- `api_sources.json` — public API registry
- `verify_deployment.py` — package, schema and integrity checks
- `requirements.txt` — Python dependencies
- `.streamlit/config.toml` — deployment theme and server settings

## Deploy on Streamlit Community Cloud

1. Upload the contents of this folder to the root of the GitHub repository.
2. Keep all 14 `.xlsx` files under `data/` with their canonical filenames.
3. Set the Streamlit entry point to `app.py`.
4. Deploy or reboot the application.

## Validate before deployment

```bash
python verify_deployment.py
```

The verifier checks Python syntax, required files, workbook readability, manifest-to-sheet routing, spreadsheet error markers, canonical primary keys and IMO uniqueness.

## v2.4 additions

- USCG CGMIX / PSIX added as an on-demand vessel-safety and compliance layer: vessel lookup, USCG contacts/cases, deficiencies and operational controls.
- USCG Incident Investigation Reports (IIR) added for on-demand searches of published Coast Guard marine-casualty investigations.
- GDELT DOC 2.0 added as a `Global Signals` discovery layer with maritime-security, port disruption, rail/intermodal, logistics and infrastructure-deal query presets plus custom queries.
- GDELT-derived results remain discovery signals only; they are not automatically promoted into the canonical event model.
- GDELT GEO 2.0 is registered in `api_sources.json` for later geographic/entity enrichment but is not persisted in this Excel test build.
- Existing IMF PortWatch and Strait of Hormuz live API functions remain enabled.
- All API results in v2.4 are cached in-app and remain external to the canonical XLSX model, making the storage-layer migration to PostgreSQL cleaner.

## API persistence rule for this test

The 14 Excel workbooks remain the source-of-truth model. Live API output is deliberately ephemeral in v2.4. During PostgreSQL migration, selected observations can be moved into dedicated fact/evidence tables after entity resolution, deduplication and verification rules are finalized.


## v2.5 live-feed visual model
- **Live Feeds > Maritime AIS:** AISHub map + vessel observation table; activates only when `AISHUB_USERNAME` is configured.
- **Live Feeds > Intermodal Mobility:** Navitia coverage, place/stop map and disruption table; activates only when `NAVITIA_TOKEN` is configured.
- **Live Feeds > API Catalog:** visual status cards distinguish enabled, credential-gated, trial/deferred and excluded feeds.
- Cirium FlightStats is catalogued as trial/deferred; ADS-B Exchange is explicitly excluded from the free production stack.
- Excel remains the canonical entity layer; all new API observations are ephemeral in this pre-Postgres test.


## v2.6 navigation
The app now uses six grouped workspaces in the sidebar: Command Center, Network, Operations, Markets & Policy, Intelligence, and Data. CGMIX/GDELT are deferred from the active UI. NewsData.io is available under Intelligence > News & Signals after adding `NEWSDATA_API_KEY` to Streamlit secrets.
