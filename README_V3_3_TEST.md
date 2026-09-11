# Power & Corridors Trade System v3.3 — Legacy Excel Test Release

This package preserves the existing Excel/Streamlit platform while adding the reference-intelligence architecture needed for the later Supabase/Postgres migration.

## Run locally

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

No Supabase credentials are required for the legacy Excel test. If Supabase secrets are configured, the existing bridge continues to use them; Freight & Commodity Markets falls back to the bundled Signal reference workbook when the database has no approved observations.

## Workbook set

The original 14 canonical workbooks remain intact and five new workbooks are added:

15. `15_market_intelligence_reference.xlsx` — Signal observations, market instruments, chokepoint market series, Accuracy Shipping historical sample.
16. `16_global_ports_reference.xlsx` — 1,377-port research reference, throughput ranking and aggregated 2050 fuel scenarios.
17. `17_trade_connectivity_reference.xlsx` — FTA/LSBCI and World Bank/UNCTAD reference registry plus corridor seeds.
18. `18_official_maritime_security.xlsx` — IMO confirmed Middle East incidents, theatre baselines, Hormuz operational measures and chokepoint governance.
19. `19_risk_benchmarks.xlsx` — historical port-accident distributions and port-delay model staging.

## Canonical v3.3 additions

The live canonical workbooks also now include Ocean Melody (IMO 9303065), Qingdao Beihai Shipbuilding, CSSC, Huili Shipping, Yuyangkunpeng Shanghai Ship Management, the 10 September Qingdao fire, linked companies/assets/location, and the new institutional/Signal source records.

## Architecture

v3.3 separates data into three layers:

1. **Canonical structural graph** — companies, vessels, ports, shipyards, terminals, rail, aviation, energy/industry and relationships.
2. **Dynamic intelligence** — events, hazards, sanctions, investments, market observations and news/signals.
3. **Reference/analytical layer** — trade connectivity, port benchmarks, historical accidents, market series, scenarios and model outputs.

Research-scale source datasets are stored under `external_data/` and are not all loaded at Streamlit startup. This keeps the old platform responsive while preserving migration-ready source material.

## New Streamlit views

- Operations → **Official Maritime Security**
- Markets & Policy → **Reference & Benchmarks**
- Data → **Reference Library**
- Freight & Commodity Markets → Supabase first, bundled Excel Signal fallback

## Supabase migration

Apply SQL files in numeric order. `sql/010_reference_intelligence.sql` adds reference datasets/observations, official incidents, operational measures, chokepoint governance, port reference/scenario metrics and delay-model tables.

`python scripts/stage_reference_datasets.py` validates the large normalized CSV layer and writes `staging/reference_staging_manifest.json`.
