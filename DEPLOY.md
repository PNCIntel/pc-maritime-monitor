# P&C Intelligence Delivery Layer — Trade & Security v1

## Design
The customer never sees database modes, record IDs, SQL views, technical dumps or an app switcher. The four existing customer renderers and three existing specialist renderers remain intact. The extra PostgreSQL views are a **data delivery contract**, not UI pages.

The **six live PostgreSQL views** are organized as three logical datasets per product:

| Product | Operating picture | Connections | Developments |
|---|---|---|---|
| Trade | `pc_intel_trade_picture` | `pc_intel_trade_network` | `pc_intel_trade_developments` |
| Security | `pc_intel_security_picture` | `pc_intel_security_network` | `pc_intel_security_developments` |

`pc_intel_event_details`, `pc_intel_object_events`, and `pc_intel_network` are reusable shared definitions. Events include descriptions, full metadata, linked evidence, dates, explicit relationships and available coordinates. `HIGH` and `INCREASING` are shown only if they exist as source fields; the patch does not compute or fabricate them.

## Installation order

1. Preserve a copy of the live repository and deploy to a **test branch** first.
2. If not already installed, apply the previous `sql/20261009_delivery_views.sql` from Data Delivery v1. Do **not** run it if those views already exist.
3. Run **this package's** `sql/20261009_intelligence_layer.sql` in Supabase SQL Editor. It creates/replaces *views only*; it does not change your source tables or SQL loading procedure. Do not enable broad grants for customer roles as a shortcut.
4. Copy only the changed Python modules `pc_terminal.py`, `pc_market_lenses.py`, `pc_specialist_markets.py` and new `pc_intelligence_presentation.py` to your existing repo, preserving `shared/pc_db.py`, `pc_drilldown.py`, `pc_corporate_network.py`, all other modules and app secrets. Do not replace the repo with the ZIP.
5. Restart all seven Streamlit apps. **No Data Views / Existing Dashboard radio** should appear. The legacy map-driven customer pages remain. On Trade and Security home pages there is an additional source-backed map and activity section; event dossiers use the full event details view with fallback to the existing renderer if the new view is unavailable.
6. Keep SQL insertion as the test dataset loading mechanism. Ordinary views reflect committed new records without `REFRESH MATERIALIZED VIEW`; Streamlit caches in existing code may need a user refresh.

## Verify in SQL

```sql
SELECT event_id,title,narrative,evidence_count
FROM public.pc_intel_event_details
WHERE title ILIKE '%YM Pioneer%'
LIMIT 5;

SELECT connected_id,connected_name,business_relationship
FROM public.pc_intel_trade_network
WHERE object_id='PORT_UAE_PORT_OF_FUJAIRAH';

SELECT event_id,object_type,object_id,explicitly_linked
FROM public.pc_intel_security_developments
WHERE event_id='EVT_20260714_MARITIME_SECURITY_INCIDENT_9937799';
```

## Limitations / next hardening

- This is **v1**, not a claim that every left-panel operational tab now consumes only the six views. Existing nav screens still use their original curated queries. Migrating the rest requires the actual section renderers' individual query paths to be replaced and tested against live Supabase results, a step not possible offline.
- The network includes confirmed terminal parenthood, asset operators and current mobile owner/operators. It is not yet a full temporal investment, airline, rail, sanctions or multi-hop network. Existing richer graph code is intentionally preserved.
- Risk status and trends must be sourced from an approved assessment methodology or stored assessment: absent fields remain blank. Never infer HIGH from a simple event count.
- The view is currently live, not materialized. For rapid SQL loading this avoids stale results; selectively materialize expensive aggregates later, with controlled refreshes.
- Existing app security policies must still be checked, including Supabase view permissions and product entitlements. SQL views alone are **not** a substitute for access control.
- All changes are offline-built. Syntax checks are not live integration tests.
