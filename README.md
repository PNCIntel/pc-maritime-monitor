# P&C Data Delivery v1 — SQL-first visibility

## Install (test branch first)
1. Keep the existing project, `shared/pc_db.py`, `pc_drilldown.py`, `pc_corporate_network.py`, `pc_document_vessels.py`, secrets and deployment config unchanged.
2. Run `sql/20261009_delivery_views.sql` using Supabase SQL Editor. **Read the SQL first**; it is additive, creates/replaces only `pc_delivery_*` and `pc_app_*` views, never writes to production entity/asset/event tables.
3. Copy this bundle's `.py` files into the existing repository at its root, including new `pc_delivery_ui.py`. Preserve other files in repository.
4. Restart each Streamlit app. It defaults to `Data Views`; `Existing Dashboard` preserves the former interface, search, dossiers and reports.
5. Test select navigation for Trade, Intelligence, and the other five. New SQL records should appear in views on next query; no materialized refresh required. Query limit and Streamlit cache still apply to other legacy UI.

## Seven business app views
`pc_app_trade_records`, `pc_app_security_records`, `pc_app_strategic_records`, `pc_app_sanctions_records`, `pc_app_capital_records`, `pc_app_commodities_records`, `pc_app_markets_records`. These provide first-pass section routing from established `pc_entities`, `pc_assets`, `pc_mobile_assets`, and `pc_events`. `pc_delivery_direct_incidents` and `pc_delivery_facility_children` provide explicit evidence-linked relations.

## Important limits (do not mistake scaffolding for completion)
* **This is an initial live-data delivery layer, not finished seven-domain analytical SQL packages.** The capital, sanctions, markets and commodity menus show discoverable objects but do **not yet** implement dedicated portfolios, sanctions designations, benchmark rates, commodity flows, time-aware contract lookups or full graph relationship traversal. Add specialist delivery views incrementally using real schema.
* The row tables are intentionally **live ordinary views**, not materialized: newly SQL-loaded data appears without a refresh. Once data contracts stabilize, expensive overview aggregates can be materialized and refreshed from admin.
* Direct incidents are read from `pc_event_asset_links`, `pc_event_links` and `pc_v_event_vessel_links`; they are not automatically 'security' events. Validate event categories before using them for threat analytics.
* Underlying PostgREST permissions/RLS policies still control access to SQL views; **do not deploy service-role credentials to untrusted public users**. Some existing apps use a privileged shared client; this package does not solve subscription entitlements or row-level access. Harden before public release.
* The original 'UAE / OFAC vessel overlap' and 'Documents & vessel restrictions' sidebar buttons are removed from legacy navigation; underlying sources/views and routines are kept. The diagnostic code still exists but is not linked in customer-facing nav.
* Tests are syntax and mocked data-client checks only; no live Supabase verification possible from this environment.

## Visibility smoke tests
```sql
SELECT section,count(*) FROM public.pc_app_trade_records GROUP BY section ORDER BY section;
SELECT section,count(*) FROM public.pc_app_security_records GROUP BY section ORDER BY section;
SELECT * FROM public.pc_delivery_facility_children WHERE parent_object_id='PORT_UAE_PORT_OF_FUJAIRAH';
SELECT * FROM public.pc_delivery_direct_incidents WHERE object_id='VESSEL_00092';
```

### Subsequent stage
Add source-grounded specialist `view`/RPC contracts behind each operational left-menu section; migrate high-value existing dossier components to those contracts. Reporting intentionally stays in `Existing Dashboard` for now.
