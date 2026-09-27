# P&C v1.5.4 — use one shared canonical registry; guard record types

This is an incremental safety fix for the existing 85-record staged job, **not** a new ingest, database migration or a claim that the remaining exceptions are automatically researched and published.

## Deploy

1. In Power Admin repo ROOT, replace `pc-power-admin.py` with the attached file.
2. In the SAME repo ROOT, replace `pc_v15_bulk_replay.py` with the attached file (replaces v1.5.3).
3. Commit and redeploy. No SQL, Trade/Intelligence code change or re-extraction.
4. Open Reload & republish. At the top verify `Publisher build: 1.5.4-model-guard` before doing anything else.
5. Enter your existing job ID `cf0aead2-d558-4ca3-91d7-42b70cc5e8fe` and click **3 · Analyse entire staged batch**. Download the fresh eligible and exception exports. DO NOT use an earlier saved approval or previous export.

## What is fixed

- Universal Intake's `Run Identity Match` previously looked up ONLY incoming exact SQL names, so it could not discover a fuzzy candidate not already fetched. It now uses the same complete paginated canonical registry + cross-domain candidate search as the v1.5 bulk publisher. The shared database is read-only during audit.
- A `pc_entities` extraction with a project/advisory/strategy title, and `pc_assets` extraction with equipment purchase, expansion or vessel title, is HELD for type correction instead of inserted into the wrong table. The source PDF is NOT reloaded.
- Short legal acronyms that the registry has not uniquely identified are HELD for authoritative alias research. A uniquely verified existing IMO still matches first.
- Cross-domain fuzzy candidate checks hold a potential company name that actually resembles an existing terminal/asset; they do NOT automatically merge different kinds of record.
- The deployed publisher version is shown on screen so we can tell whether Streamlit is serving the old or new file.

## Honest limitations

- Classification defects are prevented from corrupting the shared database, but misclassified staging rows still need **automatic research and correction** before they can publish as proper developments or mobile assets. This hotfix does not mutate old staged records or write invented relationships.
- Existing fuzzy match decisions are recommendations, not legal proof. Fully automated research and evidence-backed restaging of the held records is the next step; the current stage export alone lacks enough fields and source texts to implement and live-test that safely.
- Tests are mocked and local. Production Supabase and LIVE Trade have **not** been tested here.
