P&C Trade v3.3.42 - Live Regional Maps

Replace app.py only.

Fixes:
- Regional Maps now reads the live canonical Events & Hazards event layer.
- Merges pc_event_locations coordinates into canonical pc_events for mapping.
- Uses the same canonical event/location source pattern as P&C Intelligence.
- Keeps business + security, business-only and security-only layers.
- No SQL changes required.
