P&C Research-First Analyst Loader v3.4.1 hotfix

Fixes live-schema error:
  column pc_staged_records.source_url does not exist

Change:
- pc_connected_research.py no longer selects source_url from pc_staged_records.
- source provenance continues to be read from payload.metadata.source_url / research_sources.

Deployment:
- Replace pc_connected_research.py with this version (or deploy the full package).
- Reopen the same persisted job and click Resume this load.
- Do NOT reload/research St Helena again.
