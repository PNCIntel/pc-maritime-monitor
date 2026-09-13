P&C Trade / Workflow Fix v3.3.39 / v5.3

Replace:
  app.py
  pc-power-admin.py

Trade changes:
- Commercial Pulse suppresses nan placeholders and resolves Buyer/Target fields correctly.
- Latest canonical activity becomes Latest trade updates.
- Adds alerts/events, transactions, trade flows and canonical relationships as readable updates.
- Newly created companies/entities move to a secondary expander instead of dominating the feed.
- Infrastructure additions remain prominent.

Workflow changes:
- Fixes AI Research failure: _dependency_reconcile was undefined.
- AI Research now calls the existing _run_reconciliation wrapper, which prefers pc_reconcile_ingestion_job_v2 and falls back safely.

No new SQL required.
