# P&C v1.9.1 — identity callback hotfix

This fixes the live v1.9 population error:

`_identity_candidates() missing 1 required positional argument: 'registry'`

## Deploy
Replace only:

- `pc_intelligence_pipeline.py`

No SQL migration. No new job. No re-upload. No re-extraction.

After Streamlit reloads, open the same intelligence load and click **Resume this load**.
The 58 staged records remain persisted in Supabase.

## Why it failed
`link_researched_events()` expects a four-argument identity-matching callback. The v1.9 pipeline passed the internal five-argument `_identity_candidates()` function directly. This hotfix builds the canonical identity index once and passes the correct four-argument wrapper, matching the already-working pattern in `pc_v15_bulk_replay.py`.
