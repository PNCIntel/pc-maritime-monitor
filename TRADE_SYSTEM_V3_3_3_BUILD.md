# P&C Trade System v3.3.3 — Legacy Test Fix

## Corrections
- Restores Cruise data when dedicated Cruise Lines / Cruise Ships / Cruise Destinations / Cruise Routes sheets are absent.
- Cruise fallback now seeds from Fleet Research Universe, canonical cruise companies, canonical cruise vessels and Great Lakes Cruise deployment data.
- Removes the recursive Cruise fallback bug present in the interim v3.3.2 build.
- Ports view now exposes the full uploaded geocoded global-port reference layer with port names on map hover.
- Canonical ports are enriched from the global port reference when a safe name match exists; reference-only ports remain visible as enrichment seeds.
- P&C Intelligence regional maps infer coordinates for named event locations when Event Locations has no coordinate pair.
- Asia-Pacific named-place support includes Ningbo, Xiangshan, Qingdao and Manila South Harbour.
- IMO Middle East confirmed incidents are plotted as approximate points where IMO provides a named location / NM offset.

## Mapping rule
Explicit Event Locations coordinates remain highest priority. Inferred / IMO points are labelled approximate and do not overwrite the source record.
