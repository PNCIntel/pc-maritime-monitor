# P&C Shared Infrastructure Risks — Trade / Intelligence / Sanctions

Replace `pc_market_lenses.py` and add `pc_shared_infrastructure_risks.py` **in both deployed app repositories** if Trade and Intelligence are separate deployments. Keep existing `pc_terminal.py`, `pc_object_resolver.py`, and all other modules unchanged. Restart/redeploy Streamlit.

Existing **Risks & Disruptions** renderer replaces the flat list with dated, expandable evidence panels while preserving the current counts, connected infrastructure map, and graph resolution. Works through both the Intelligence asset dossier and Trade's Risks & Disruptions selector. Trade's Operations & Trade view is not altered.

Existing Sanctions & Compliance view gains a contextual actor panel derived strictly from existing `pc_event_entity_links`. It is **not** a designation screen and does not assert that an actor is legally sanctioned. The existing designations/screening UI remains. A Houthi/IRGC designation must have its own sourced legal designation with jurisdiction and dates; attack responsibility must be separately sourced.

**No SQL necessary.** Four live cases to test: `PC_SA26_AP_OERK` (RUH), `ASSET_A136EB0EEC4A78BA0AF3` (DXB), `ASSET014` (Jebel Ali), `ASSET_E593175E79E03FACB9B0` (FOTT). Compare existing direct/connected counts and validate that opening each row goes to its event.

Caution: this patch intentionally does not create an independent Sanctions app router or update `pc_visual_workspaces.py` briefing-level navigation. It extends the existing shared asset market-lens module. Python compile tested; production DB/UI not executed here.
