P&C Trade v3.3.47 — Fleet Graph Browser

Replace app.py only. No SQL changes.

Fixes:
- Company profiles recover canonical vessels from source-backed owner/operator/manager metadata when FK/graph links are incomplete.
- Relationship endpoint types are inferred from canonical IDs/tables when source_type/target_type is missing or inconsistent.
- Relationship metadata source/target names can reconnect duplicate/migrated company IDs.
- Vessels page searches company/group names (MSC, CMA CGM, P&O Ferries, etc.) through the canonical entity graph.
- Fleet search shows fleet summary and table before individual-vessel drilldown.
