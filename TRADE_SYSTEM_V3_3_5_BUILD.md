# P&C Trade System v3.3.5 — Trade / Intelligence Boundary + Mapping Fix

Build date: 11 September 2026

## Fixes

- Fixed the Ports page pandas 3.x coordinate-enrichment TypeError by normalising Latitude/Longitude columns to numeric before reference writes.
- Added **Trade Network Map** to the Trade app with global-reference and canonical-port views.
- Retained the 1,377-port global reference as the geography seed layer and canonical enrichment source.
- Added representative route maps to Cruise routes and the Great Lakes cruise network.
- Added Great Lakes cargo corridor route maps under Corridors & Systems.
- Tightened the P&C Intelligence routing gate so routine commercial development (new cranes, terminal openings, investments, commissioning, fleet orders, etc.) remains in Trade unless the same record contains a concrete adverse security/disruption incident.
- Fixed the P&C Intelligence `port_terminals` NameError.
- Changed Intelligence **Port drill-down** to show only ports/facilities linked to routed security/disruption events, including terminal-parent inheritance and cautious event-name matching.
- Expanded Intelligence **Vessel Exposure** to include canonical vessel metadata (IMO, vessel type and flag) and the IMO-confirmed incident layer. The 75 IMO records are treated as official evidence against vessel objects, not a separate commercial fleet.
- Synchronised `pc_intelligence_app.py` with `pc-intelligence.py` for the deployed Streamlit entry point.

## Architecture rule

P&C Trade owns the complete commercial network and geography. P&C Intelligence receives only security, disruption, sanctions/compliance and other operational-risk exposure linked back to those canonical assets.
