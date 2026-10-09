# P&C universal object resolver — v3

## Install
Merge `pc_object_resolver.py` and the included `pc_market_lenses.py` into your existing repo beside `pc_terminal.py`. Keep all other repo modules, environment secrets and Streamlit launchers. Test in a branch before deployment. This archive is a complete merge overlay of the prior seven-app release, not a replacement repository.

## What is actually wired
- Trade & Strategic Industries fixed-facility context (`_scope`) now uses one shared facility resolver.
- Trade's Risks & Disruptions tab uses the shared resolver and separately counts directly linked incidents vs incidents at explicitly connected facilities.
- The shared API also supports entity and mobile-asset direct event lookup, but other existing profile pages do not yet call it.
- No special-casing for Fujairah, Rotterdam, UAE, or any specific vessel.
- No database writes or new tables.

## Limitations / next integration step
- The Trade *Operations & Trade* dossier still uses the existing `pc_terminal_asset_dossier` RPC and existing fallback. Its zero-facilities display may persist until its data retrieval uses this resolver or the RPC is fixed.
- Coverage depends on actual DB link table columns/permissions. The resolver is read-only and treats missing query responses as incomplete, not zero real-world incidents.
- It is not an authorization layer; product licensing must be enforced separately on the server side.
- Any event present without a direct typed link intentionally will not be counted as an incident at the facility.

## Test
`python -m unittest discover -s tests -v`
Tests exercise airport, port terminal, vessel, and non-inference behavior with a mock DB adapter. Live Supabase/Streamlit remains untested.
