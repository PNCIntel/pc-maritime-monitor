# P&C Trade System v1.13 — Port Infrastructure Patch

This patch upgrades the v1.12 data model and the latest Streamlit application branch with a normalized global port/terminal infrastructure layer.

## What changed

The port model is now separated into:

- `ports.csv` — canonical parent ports / port complexes
- `port_terminals.csv` — canonical physical terminals and facilities
- `port_berths.csv` — berth/quay/depth records
- `port_equipment.csv` — STS, RTG, RMG, ASC, straddle, reach-stacker and related equipment
- `port_ownership.csv` — owner/operator/JV/concession relationships
- `port_news.csv` — terminal-linked news and development events with live source URLs

`Assets` remains in the model for backward compatibility, but physical terminal infrastructure should now be queried from the normalized port tables.

## Operator coverage in the normalized layer

The current canonical port layer consolidates source data for:

- DP World
- AD Ports Group / Abu Dhabi Ports / Noatum Ports / Noatum Automotive
- CMA CGM / CMA Terminals / Terminal Link
- MSC / Terminal Investment Limited (TiL)
- APM Terminals / Maersk

Known cross-operator/JV duplicates are represented once as physical terminals, with multiple ownership/operator relationships attached separately.

## Streamlit deployment

1. Back up the current GitHub repository.
2. Replace the deployed root `app.py` with the `app.py` in this patch.
3. Copy the files from this patch's `data/` directory into the repository's existing `data/` directory, replacing same-named files where present.
4. **Do not delete other existing data files**. The application still depends on the vessel, incident, sanctions, ferry, Great Lakes, Black Sea, shipyard, weather and other datasets already in the repository.
5. Commit and push. Streamlit Community Cloud should redeploy automatically if the existing app remains connected to the repository.

The loader in the current app searches recursively under `data/`, so the new `port_*.csv` files can remain at `data/` root or later be moved into a unique `data/ports/` subfolder without changing their filenames.

## Streamlit changes

The updated Ports & Terminals page now includes:

1. Terminal Network
2. Port / Terminal Detail
3. Berths & Depth
4. Equipment
5. Ownership & JVs
6. Latest Port News
7. Great Lakes / St. Lawrence
8. Infrastructure & Investment

Port detail views show infrastructure metrics, berth/depth records, terminal equipment, ownership/JV relationships and clickable current-news/source links.

`Ask P&C` now receives the new parent-port, terminal, berth, equipment, ownership and port-news tables as queryable datasets.

Internal IDs and raw URL columns remain hidden from normal analyst-facing tables; canonical names and readable relationship labels are displayed instead.

## Model workbook

`PC_Trade_System_Intelligence_Model_v1_13_Port_Infrastructure.xlsx` is the revised research/model workbook. New sheets:

- Port Terminals
- Port Berths
- Port Equipment
- Port Ownership
- Port News
- Port Model v1.13

The existing Ports, Companies, Sources, Entity Registry, Data Dictionary and Runtime Table Crosswalk were also updated.

## Current normalized counts

- Companies: 173
- Parent ports: 246
- Canonical terminals/facilities: 245
- Berth/interface records: 125
- Equipment records: 192
- Ownership/operator/JV edges: 264
- Port news/development records: 66
- Sources: 318

Blank infrastructure values mean **not publicly verified**, not zero.

## APM Terminals source dataset

`source_operator_data/apm_terminals/` contains the standalone APM Terminals research pass used to feed the canonical layer. It is retained for provenance and further enrichment, but the Streamlit app should use the normalized `port_*.csv` tables rather than loading the operator-source files directly.
