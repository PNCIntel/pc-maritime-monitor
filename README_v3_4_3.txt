P&C Research-First Analyst Loader v3.4.3 — restart-safe resume

Fixes Streamlit restart/deploy handoff:
- pc-power-admin now finds recent ingestion jobs whose persisted source_scope.connected_research status is 'researching' or 'review'.
- Analysts see an 'Interrupted load' selector and 'Resume interrupted load' button in the sidebar.
- Resume restores the exact ingestion_job_id into the Load intelligence workspace.
- The existing pc_intelligence_pipeline then reconstructs connected_research or connected_review from Supabase.
- No source reload, requeue, database IDs, SQL, or repeated OpenAI research required.

Deploy:
- Replace pc-power-admin.py (minimum required).
- Full ZIP is included to keep versions aligned.

For the St Helena test:
1. Deploy/restart.
2. In sidebar, use Interrupted load -> select the St Helena job -> Resume interrupted load.
3. It should return directly to connected research/review based on persisted source_scope.
4. Do not restore/requeue/research the TWZ article again.

Validation:
- Python compile passed for pc-power-admin.py, pc_intelligence_pipeline.py and pc_connected_research.py.
- ZIP integrity tested.
