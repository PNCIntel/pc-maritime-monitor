# P&C Trade System Intelligence Model v1.27

**Global Trade, Infrastructure & Defence Industrial Systems — Stress-Test Build**

This build carries forward the v1.26.1 port, corridor, rail and waterway model and adds a first-class defence/commercial shipbuilding layer plus a redesigned Streamlit interface.

## Interface

The primary UI is now:

1. **Search P&C** — ranked cross-workbook search without needing table names.
2. **Entity Explorer** — one profile across companies, assets, shipyards, programmes, contracts, vessels and news.
3. **Systems & Corridors** — port / rail / waterway / governance systems.
4. **Shipyards & Defence** — yard facilities, capabilities, programmes, contracts and sales routes.
5. **Intelligence** — news and announced activities.
6. **Data Explorer** — raw tables retained as evidence/debug layer.

Internal IDs remain backend keys and are hidden from normal table display.

## v1.27 defence / shipbuilding stress tests

Deep seeds include:
- EDGE Group / ADSB / **MAESTRAL**
- Fincantieri and UAE Navy / UAE Coast Guard sales routes
- Irving Shipbuilding / Halifax Shipyard / River-class Destroyer / AOPS
- Seaspan Shipyards / Vancouver / Victoria / Vancouver Drydock / JSS / CCG polar icebreaker
- Inocea / Davie / Helsinki Shipyard / Davie Defense / US and Canadian icebreaker programmes
- Bollinger Shipyards / Houma / Gulfport / Mississippi network
- Rauma Marine Constructions / Rauma facilities
- Damen / Antalya / Dutch Caribbean Coast Guard programme
- RMK Marine and Sefine as Turkey dual-use/commercial shipbuilding seeds

The data model tests the chain:

`Company → Shipyard → Facility → Capability → Programme → Contract → Vessel → Customer → Sales/Delivery Route → Announcement`

## New infrastructure lifecycle tests

The systems workbook also adds:
- **Badagry / Lagos Gateway Development** — prospective APM Terminals involvement kept distinct from existing Apapa / Onne assets.
- **Simandou / Morebaya** — mine → 70 km rail spur → Transguinean line → commissioning port → temporary WCS export gateway → China route.

## Evidence handling

Where official announcements create potentially overlapping or evolving programme records, records remain separate and carry evidence/status notes rather than being silently merged. This is intentional for stress testing temporal/source-aware modelling.

## Deployment

Upload the repository contents to GitHub and point Streamlit Community Cloud at `app.py`.

`requirements.txt` contains the required Python packages.
