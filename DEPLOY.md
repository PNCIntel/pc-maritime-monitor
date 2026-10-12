# P&C Riyadh canonical data + UI integrated repair

1. Run `01_riyadh_graph_quality_ONE_RUN.sql` in Supabase and inspect its JSON report. No destructive merge, no new airport.
2. Copy four `.py` files alongside the existing application modules, replacing the three same-named modules. Preserve your entry point and `pc_terminal.py`.
3. Redeploy Streamlit. In Intelligence or Trade, open the canonical airport `PC_SA26_AP_OERK` through an explicit linked-event facility Open control.
4. In its embedded dossier, inspect dated operational and security developments, then toggle the airport event lens. The three global Intelligence lenses remain unchanged.
5. Confirm historical incidents, restriction notices and 12 Oct airline exposure remain *separate* events. Check NOTAM expiry is labelled reported, not reopening. The duplicate-looking ASSET_8DCF... remains subject to stewardship.

Caveats: Query-based UI tested by syntax compilation only, not live Streamlit. The UI's event lens is a presentation grouping over source-labelled event types, not a new canonical classification. Existing metadata attribution for GSA remains confidential: do not expose the original report beyond authorised viewers. This package does not perform database-wide deduplication or reconcile secondary airport record into the canonical id.
