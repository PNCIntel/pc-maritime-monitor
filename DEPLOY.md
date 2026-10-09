# P&C Trade + Security — Map-led Workspace v2

## What is implemented
- Replaces **home operating pictures** in Trade and Intelligence with map-led, searchable working views based on `pc_intel_trade_picture`, `pc_intel_trade_developments`, and `pc_intel_security_picture`.
- Preserves the existing global search, selected object dossiers, supporting maps, sidebar routes and reporting.
- Opens selected companies/facilities/events through the existing terminal's context navigation.
- Filters Trade by business section, country and search; filters Security by event category, date and search.
- Shows narratives and only *recorded* risk levels/trends. Does not calculate unsupported HIGH/INCREASING ratings.
- Does not write to the database, infer vessel position, or turn regional proximity into direct impact.

## Prerequisites
1. Existing P&C application repository and its supporting modules (`pc_db`, `pc_drilldown`, `pc_corporate_network`, `shared/`, etc.).
2. Prior deployed SQL migrations `20261009_delivery_views.sql` and `20261009_intelligence_layer.sql`.
3. Working Supabase credentials in the existing Streamlit environment.

## Install to TEST branch
1. Back up current files.
2. Overlay `pc_terminal.py`, `pc_market_lenses.py`, `pc_prepared_bridge.py`, `pc_intelligence_presentation.py` and NEW `pc_visual_workspaces.py` alongside existing Python modules.
3. Do **not** replace the entire repo. The two launchers are provided as reference; use existing launchers unless they differ.
4. Restart both Streamlit apps and clear Streamlit caches if necessary.
5. Test Trade Home and Intelligence Operating Picture with a range of objects/countries, then open event/facility links to ensure existing dossiers work.

## Known limitations / follow-up
- Home operating pictures are now view-fed; **other operational sidebar sections and selected-object dossier internals are not fully migrated to the prepared views.** This is not the completed 3-data-product / every-sidebar architecture.
- `st.map` shows point geometry, not route lines or a complete interactive relationship network; full layer-control maps, source-aware line geometry and timelines are subsequent work.
- View query failures display the existing home dashboard as a fallback rather than asserting zero data.
- Streamlit queries are limited to 5,000 records per view, so large growing datasets need server-side filtering, pagination or tiles later.
- Materialized refresh management, privileged subscriptions/entitlements, and automated SQL-to-UI visibility tests are not included.

## Suggested checks
`SELECT count(*) FROM public.pc_intel_trade_picture;`
`SELECT count(*) FROM public.pc_intel_security_picture;`
`SELECT count(*) FROM public.pc_intel_security_picture WHERE latitude_text IS NOT NULL AND longitude_text IS NOT NULL;`

No schema changes in this patch. Test live against Supabase before production.
