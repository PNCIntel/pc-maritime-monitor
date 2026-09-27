# v1.5.3 — Shared canonical reconciliation hotfix

## Scope and deployment
Replace **only** the root `pc_v15_bulk_replay.py` in the currently deployed Power Admin repository. Preserve your v1.5.1 persistent-intake changes, v1.5.2 validation safeguards, all current Trade and Intelligence applications, and all existing SQL migrations. **No SQL, new intake, queue job, database reset or manual canonical IDs.**

Use existing staged job: `cf0aead2-d558-4ca3-91d7-42b70cc5e8fe`. After deployment, open Reload & republish, enter the job ID, and click **3 · Analyse entire staged batch**. Export/check the new results. Do not reuse old 69-eligible/15-exception counts or approve a plan from an old running Streamlit session.

## Specific fix to prior broken workflow
The v1.5.2 publisher checked only exact, case-sensitive SQL `IN(name)` names from the incoming batch. A staged name like `port_of_los_angeles` could incorrectly become `create_new` even if `Port of Los Angeles` already existed in the common database.

v1.5.3 pages through the **full canonical identity columns** in the shared `pc_entities`, `pc_assets`, `pc_mobile_assets` and `pc_events` tables (plus cross-table entity/asset checks). It normalizes punctuation, underscores, case and accents, reuses single same-type canonical matches, detects multiple matches, and blocks fuzzy candidates / same-name cross-type clashes until verified. An IMO match takes precedence for mobile assets. It rechecks the entire live plan immediately before approval-based publication and invalidates stale plans. It never automatically equates similarly named companies or ports. Validation holds month-only dates and obvious misclassified topic/equipment records, retaining v1.5.2 backup-first per-batch publication and partial-failure isolation.

A failure/incomplete registry scan **aborts analysis** instead of treating unseen records as absent. Current hard safety cap is 25,000 identities **per canonical table**. If a table exceeds that, a dedicated server-side identity query is required before permitting any new records.

## Limitations and success conditions
This **does not rewrite old staging proposals or guarantee automatic web research for unresolved identities**; those remain review/research exceptions until verified. An exact normalized name is still only an identity candidate—conflicting type evidence is held. Names absent from this core registry may exist as unindexed alternate names in other model tables: fuzzy screening reduces risk but cannot guarantee zero duplicates. The source documents are already staged; there is no reason to re-upload or re-extract. Test the new counts and exported eligible list first; inspect LIVE Trade after any separately approved publish. All local tests use mocked Supabase data; live deployment and production publishing are untested.
