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


## v1.26.1 — Genoa megaship-access stress test

Added **Genoa Megaship Access / Rhine-Alpine Gateway** as the 11th systems test.

The new graph tests:
- Western Ligurian Sea Port Authority → Port of Genoa
- Port authority → New Genoa Breakwater
- PerGenova Breakwater consortium → construction programme
- Webuild / Fincantieri Infrastructure / Fincosit / SIDRA → consortium participation
- Breakwater → access channel / turning basin / megaship capability
- Port of Genoa → Terzo Valico dei Giovi–Genoa Junction
- Terzo Valico / Genoa → Rhine–Alpine Corridor
- 8 Sep 2026 news → authority / port / asset / contractors / rail project / corridor

This adds marine-access infrastructure as a first-class facility category alongside berths,
yards, rail sidings, locks, canals, warehouses and other infrastructure.

## v1.28.3 interface fix
The Entity Explorer is now relationship-aware rather than table-aware. For shipbuilding companies it directly resolves:
- shipyards and yard facilities/capabilities
- defence/coast guard sample vessels
- commercial maritime vessels from the maritime workbook
- programmes and programme participation
- contracts
- sales/delivery routes
- announcements and linked news
- corporate relationships and system/corridor exposure

The Shipyards & Defence page is company-first, so selecting Seaspan, Inocea, Bollinger, MAESTRAL, Fincantieri, etc. immediately exposes the connected layers.

## v1.27.2 group traversal
Company profiles now traverse controlled/owned subsidiaries and JVs up to three levels.
This fixes parent-group profiles such as Inocea and EDGE:
- Inocea now exposes Davie, Helsinki Shipyard and Davie Defense yards/programmes.
- EDGE now exposes ADSB and MAESTRAL shipbuilding activity.
The profile also labels the operating company on each yard and the prime/lead company on programmes.

## v1.27.3 maritime asset traversal
Company profiles now traverse the dedicated Maritime workbook:
Company → Port Terminals → Parent Ports → Port Ownership/JV → Berths → Equipment → Port News.
This fixes APM Terminals, DP World, PSA, Hutchison Ports and other terminal operators whose asset networks were already populated but hidden from the entity profile.

## v1.27.4 readability + visuals
- Fixes unreadable white Streamlit detail/popover boxes in dark mode.
- Resolves internal company/entity/programme/yard/port/terminal/vessel keys to English names before display.
- Internal IDs are hidden throughout the normal interface; Data Explorer has an explicit debug-only toggle.
- Adds company port-footprint maps where canonical port coordinates exist.
- Adds terminal-by-country and seeded terminal-capacity charts.
- Adds shipyard country/capability charts.
- Restores company market-price line charts where a time series exists.
- Adds system composition charts and system maps where system ports have coordinates.
- Also hardens Source link keys against StreamlitDuplicateElementKey.

## v1.27.5 stability + visual fix
- Eliminates repeated Streamlit link-button widgets that caused DuplicateElementKey crashes.
- Source links are now ordinary HTML/markdown links.
- Forces Streamlit Cloud header/toolbar into the dark app theme.
- Keeps white detail/popover surfaces readable with dark text.
- Adds shipyard footprint maps for the detailed stress-test yards.
- Moves maps/charts to the top of company Overview pages.

## v1.28 — Events, Hazards & Impact Propagation

New data workbook:
- `data/13_events_hazards.xlsx`

New model layers:
- unified events
- event locations
- event-to-asset links
- event-to-company links
- event-to-system/corridor links
- impact chains
- event status history
- event taxonomy

Interface:
- top navigation: Search | Companies | Ports | Shipyards | Vessels | Contracts | News & Events | Systems | Data
- News & Events is map-first
- company profiles overlay linked events on assets
- ports, shipyards and systems expose linked events and impact chains
- Contracts combines government procurement with commercial/infrastructure transactions and sales routes

## v1.28.1 navigation stability fix
- Fixes `StreamlitWidgetAlreadyInstantiatedError` from Search → Open.
- Page changes now use a deferred `nav_request`, applied before the top navigation widget is created on the next run.
- Search can open a company profile without mutating the instantiated `top_nav` widget key.
- Improves dark-theme contrast for ordinary Streamlit buttons.

## v1.28.2 search readability fix
App-only update:
- Commercial / contract search cards use English titles such as `AD Ports Group → MBS Logistics`.
- Raw transaction/deal IDs are no longer used as card titles.
- Semicolon-delimited company IDs are resolved into company names.
- Markdown `**...**` markers are no longer displayed literally inside HTML cards.
- Commercial cards prioritize buyer/investor, target, type, value, status and dates.

## v1.28.3 connected object navigation
App-only update:
- Event-linked assets, companies and systems are rendered as navigable object cards.
- `Open` routes Zayed Port / Shanghai / Odesa to Ports, yards to Shipyards, companies to Companies, systems to Systems and vessels to Vessels.
- Ports, Shipyards and Systems honor direct object selections from event links.
- Technical enum values are humanized: `DIRECTLY_AFFECTED` → `Directly affected`, `COAST_GUARD_NEWBUILD` → `Coast guard newbuild`.
- Internal Link / Event / Observation identifiers are suppressed from normal tables.
