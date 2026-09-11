# P&C Trade System v3.3.2 — Port Geography, Cruise Restore & Intelligence Maps

Build date: 11 September 2026

## Fixes

### Cruise
The v3.3 workbook set does not contain the former dedicated `Cruise Lines`, `Cruise Ships`, `Cruise Destinations` and `Cruise Routes` sheets. The Streamlit Cruise workspace now restores those views from canonical company records and the retained `Great Lakes Cruise` deployment layer, rather than returning empty tabs.

### Ports
The `Global Port Reference` dataset contains 1,377 geocoded port records. The Ports workspace now:

- displays all geocoded reference ports on a named interactive map;
- enriches safely matching canonical ports with reference coordinates;
- appends unmatched reference ports as `Reference port seed` rows so users can start from port name + location and enrich commercial detail later;
- keeps canonical terminal, governance and event links intact for canonical ports.

### P&C Intelligence mapping
Regional maps now have two location paths:

1. explicit coordinates in `Event Locations`;
2. named-place / global-port-reference inference when coordinates are missing.

The map uses the full regional event register for geographic visibility while the regional incident list continues to focus on operational/security events. This allows strategic infrastructure alerts such as the Ningbo/Xiangshan port-development event to remain visible geographically without turning the security incident list into an investment feed.

The Middle East/Gulf map also adds approximate points for IMO-confirmed incidents where IMO publishes a usable location. Named coastal reference points and distance/direction expressions are treated as approximate, not exact, and are labelled accordingly in map metadata.
