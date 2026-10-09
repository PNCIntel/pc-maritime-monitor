# P&C fast workspaces v3 — test branch only

Replace `pc_visual_workspaces.py` and `pc_terminal.py` in the deployed repository with these files. Keep existing shared modules, `pc_market_lenses.py`, `pc_prepared_bridge.py`, and the rest of the repository intact. No SQL changes and no new tables are required. Requires prepared views `pc_intel_trade_picture`, `pc_intel_trade_developments`, and `pc_intel_security_picture` from the earlier SQL release.

Trade: loads a bounded prepared catalogue, maps facility records (not company names), defaults to **all infrastructure** and paginates results in sets of 20. Security: maps incident coordinates, deduplicates events, and paginates narratives 12 at a time. Corporate Tree: draws direct relationships first; only loads multi-hop historical network when explicitly toggled. These changes are generic across assets/companies/regions; no location-specific code.

If Trade still has zero map coordinates, verify that `pc_intel_trade_picture.latitude/longitude` are populated, or inspect `pc_assets` data. Verify database view permissions and Streamlit service-role configuration. The fallback triggers when the prepared view has no asset rows, not when all existing asset rows lack coordinates.

The code is syntax-checked but **not tested against live Supabase**. Scope: performance-oriented first-pass release, not the final complete sidebar migration. Store credentials server-side and secure service-role access before customer deployment.
