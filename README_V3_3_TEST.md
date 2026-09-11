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


## v3.3.1 maritime-security integration

- Replaced the separate **Official Maritime Security** navigation view with **Maritime Security**.
- IMO confirmed incidents now resolve directly to the canonical vessel profile by IMO number (with a minimal in-memory legacy-test vessel stub where the vessel is not yet populated in the canonical workbook).
- Added **Maritime Security & Compliance** to commercial vessel profiles; IMO confirmation appears on the vessel itself.
- The Maritime Security workspace now treats the IMO register as a confirmation layer, with **Open vessel** actions for every incident.
- Theatre baselines, operational measures and chokepoint governance remain within the Maritime Security workspace rather than being detached reference pages.

## v3.3.2 ports, cruise and intelligence-map integration

- Restores the Cruise workspace when the dedicated Cruise Lines/Ships/Destinations/Routes sheets are absent by rebuilding the view from canonical cruise companies, Great Lakes cruise deployments and any cruise-class vessel records.
- Adds the uploaded 1,377-port global reference as the geographic backbone of the Ports page. Reference-only ports appear as geocoded seed records with port name and coordinates, ready for later operator/terminal/ownership enrichment.
- Port maps now use named hover points rather than anonymous dots where PyDeck is available.
- P&C Intelligence regional maps now use explicit Event Locations first and then infer approximate coordinates from named ports/places when an event has a usable location but no coordinate row.
- Asia-Pacific geographic vocabulary now includes Ningbo and Xiangshan, so the 9 September Ningbo/Xiangshan offshore-wind port event is geographically visible on the Asia-Pacific map.
- IMO Middle East confirmed incidents are plotted as approximate official points when IMO publishes a usable location; distance/direction wording such as `24NM northwest of Port Rashid` is converted to an approximate plotting point.
- `pc_intelligence_app.py` is resynchronised with `pc-intelligence.py` so both deployment entry points carry the same map logic.
