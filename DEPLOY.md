# P&C Infrastructure Incident Dossier — 12 October 2026

Replace the four existing same-named modules together:
- pc_visual_workspaces.py
- pc_intelligence_presentation.py
- pc_event_navigation.py
- pc_airport_event_dossier.py

Add the fifth module:
- pc_infrastructure_incident_dossier.py

Do not overwrite pc_terminal.py or pc_market_lenses.py. No SQL changes are needed.

This is a shared event-to-asset timeline for canonical airport and parent-port records, rendered from pc_event_asset_links and pc_events. The airport-only runway, facility and aviation observations remain intact. No headline-only inference creates an event-to-asset relationship; records must already be explicitly linked in the database. The user can filter category and evidence relationship, and use Open event dossier.

After deploy: open a Riyadh event, navigate to King Khalid Airport, then open a port with existing attack links. Confirm each gets the same generic incident history and that unlinked incidents are not added. The UI uses relationship labels rather than interpreting every `directly_affected` link as confirmed damage.

Static Python compile passed. Runtime integration and port coverage are NOT yet validated against live Streamlit/Supabase.
