# P&C Trade + Security — prepared-view integration patch

## What this fixes

The previous SQL intelligence release left the old `pc_terminal_asset_dossier` in charge of the main dossiers. Its new views were rendered only in secondary expanders and selected event panes. This patch connects the main Trade facility dossier to `pc_intel_network` and `pc_intel_object_events` / `pc_intel_event_details`. It also switches **Intelligence infrastructure dossiers** to the Security presentation, rather than showing the generic commercial dossier.

No database migration or write. It needs the prior `20261009_delivery_views.sql` and `20261009_intelligence_layer.sql` migrations installed.

## Deploy

Copy `pc_terminal.py`, `pc_market_lenses.py`, `pc_prepared_bridge.py`, and `pc_intelligence_presentation.py` into a **test branch** of the current repository; retain all other supporting modules and secrets. Restart Trade and Intelligence. Do not deploy these files to only one app if the two apps use different revisions of the shared files.

## Validate

1. Rotterdam Trade: should retain its existing map and profiles, while including additional explicitly linked facilities and developments returned by the views.
2. Fujairah Trade: compare `pc_intel_network WHERE object_id='PORT_UAE_PORT_OF_FUJAIRAH'` with displayed connected facilities. This patch depends on that view containing the correct relationships; it does not invent them.
3. Fujairah Intelligence: should open **Risks & Disruptions** by default, with direct versus connected incidents distinguished. The map plots connected facilities with verified stored coordinates.
4. Select a ReCAAP incident: confirm its prepared event view contains narrative and evidence. The event renderer uses this view through the existing dossier pane.

## Constraints

- This is a **targeted, incremental wiring correction**, not yet every sidebar section consuming prepared views. Trade and Security home navigation and specialist subsections still retain legacy query paths.
- Materialized refreshes are not required for the *ordinary* SQL views used in this patch, but Streamlit caches might need clearing.
- Missing view/connection failures retain legacy results, instead of claiming zero incident coverage.
- Exact event relationships are deduplicated by event ID and split into direct and connected; mere geographic proximity is not counted.
- Risk assessment levels are displayed only when present in prepared data; no synthetic HIGH or INCREASING labels.
- The same generic code works with any selected infrastructure asset, not merely a port.
- Run a live Supabase smoke test before production; syntax checks alone are insufficient.
