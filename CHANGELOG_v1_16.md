# P&C Trade System v1.16 — Port Network & News Entity Enrichment

## Added
- Canonical terminal-network expansion for PSA, Hutchison Ports, COSCO SHIPPING Ports, ICTSI, China Merchants Port, Gulftainer, SSA Marine, EUROGATE and HHLA.
- `port_operator_coverage.csv` for network-level QA and coverage review.
- New company/entity rows for operator networks and news-linked operating entities.
- Current port-development/news links for selected operator projects and terminal changes.

## Enriched
- Parent ports, terminal ownership/operator relationships, berth data and equipment data.
- Davao International Container Terminal operator relationship.
- SPAN ASIA 39 identity: IMO 9385568, MMSI 548582800 and vessel particulars.
- ALPHA CRUX identity: IMO 9024621, MMSI 273252010 and Vodoley owner/operator relationship.
- Canonical identifier rows now exist for every news-linked vessel, including explicitly unresolved identities.
- ICTSI/TLG news linked to relevant African terminal assets.

## Streamlit
- Company → Assets now resolves primary-operated port terminals and ferry terminals.
- Company → Fleet now resolves canonical aircraft and ferry-system overlays in addition to vessels.
- Ports & Terminals operator filter now derives from the terminal layer, so shared/JV ports resolve correctly.
- Added operator-network coverage view.

## Model rule
A physical port/terminal exists once. Ownership, operating control, JV participation, network brand, transactions and news are linked as relationships rather than duplicated physical assets.
