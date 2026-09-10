# P&C Trade System v2

This is the clean XLSX-native implementation of the Power & Corridors Trade System. It preserves the connected company, port, vessel, infrastructure, rail, aviation, commercial, intelligence, compliance, events and defence model while removing the older CSV deployment assumptions.

## Repository layout

- `app.py` — Streamlit application
- `data/` — 14 canonical domain workbooks
- `data_manifest.json` — workbook and sheet routing contract
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

The verifier checks the Python syntax, required files, workbook readability, manifest-to-sheet routing, spreadsheet error markers, canonical primary keys and IMO uniqueness.
