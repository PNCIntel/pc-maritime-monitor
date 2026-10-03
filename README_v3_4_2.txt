P&C Research-First Analyst Loader v3.4.2 — replay connected-findings review

Purpose
- No new research architecture.
- Fixes validated-dossier replay so the analyst sees the actual connected graph before approval.
- Designed to resume the existing persisted St Helena job without rerunning OpenAI research.

Changes
1. pc_connected_research.py
   - Replays validated dossier identity_history, relationships, claims, timeline, locations and holds directly.
   - Recovers the neutral/core event already staged for the job so event and attributed claims can be reviewed side-by-side.
   - Does not re-run AI/web research for a validated replay.

2. pc_intelligence_pipeline.py
   - Connected review summary now counts vessel, name/identity history, relationships, events, claims, transactions, validator holds and research gaps.
   - Replayed dossiers get analyst-facing tabs:
     * Identity history
     * Relationships
     * Event & claims
     * Holds / gaps
     * Raw dossier
   - Database IDs and SQL remain hidden.

Expected St Helena review
- M/V St Helena candidate, IMO 8716306
- historical name MNG Tahiti
- source-backed MNG Maritime / Extreme E / Terra Nova relationships where validator allowed them
- neutral projectile-strike event separated from unconfirmed attribution/Marines claims
- explicit validator holds and unresolved current ownership/research gaps

Deployment
- Replace pc_connected_research.py and pc_intelligence_pipeline.py from this ZIP (or deploy full package).
- Reopen the SAME persisted St Helena job and click Resume this load.
- Do not rerun the source URL or dossier research.
- Review connected findings before approving publication.

Validation performed
- Python compile passed.
- Existing graph validator, connected research, and research dossier tests: 6/6 passed.
