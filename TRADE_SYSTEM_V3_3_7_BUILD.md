# P&C Trade System v3.3.7 — Compact Multimodal UI

## Navigation changes
- Removed the two-step Workspace → View radio navigation from Trade.
- Replaced it with one-click grouped navigation.
- Restored Defence & Shipbuilding as a first-class Trade domain.
- Consolidated Ferries and Cruise under Maritime tabs.
- Kept detailed Shipyards as a deep-linked page rather than a permanent sidebar item.
- Reduced sidebar destinations while preserving existing routes and deep links.

## Defence & Shipbuilding
New workspace tabs:
- Overview
- Programmes
- Shipyards
- Vessels
- Contracts
- Events & Announcements
- Delivery Routes

Uses the existing 12_defence_shipbuilding.xlsx canonical tables, including GRSE / Sagar Manthan and other programmes.

## Intelligence alignment
- Domain navigation now parallels Trade more closely.
- Maritime is one domain rather than a separate 'Maritime Security' naming convention.
- Added Defence & Strategic Industry.
- Regional Maps remains a primary operating-picture destination.

## Data
No dataset rows were removed. This build carries forward the v3.3.6 data package, including security/trade backfill and Montevideo parent-port event linkage.
