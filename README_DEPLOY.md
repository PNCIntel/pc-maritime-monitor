# P&C v1.5.2 — publisher safety hotfix

**Scope:** one replacement file: `pc_v15_bulk_replay.py`, for the existing deployed Power Admin v1.5/v1.5.1. No SQL, Trade app, intake, or database reset. Keep the existing 85-record job `cf0aead2-d558-4ca3-91d7-42b70cc5e8fe`.

## What it corrects
- Dates of the form `YYYY-MM` supplied to date fields are *held as exceptions*. No arbitrary day is invented. Full invalid calendar dates are held too.
- Conservative record-type checks hold obvious misclassifications (e.g. HPC advisory or Port of Hastings development strategy as companies; Tecon Rio Grande crane delivery as a physical asset; Quebec terminal redevelopment as a duplicate port asset). These cases require corrected staged proposals and evidence, not manual direct database writes.
- The publish operation processes companies/assets before events, uses small backed-up groups and isolates individual RPC failures; it reports individual failures instead of aborting the entire batch.
- Existing canonical publication items are excluded on a fresh reanalysis, so a retry does not intentionally publish them again. Refresh the page and click `3 · Analyse entire staged batch` after each run to refresh the plan.

## Deploy and resume
1. In **Power Admin** GitHub repository, replace ONLY root `pc_v15_bulk_replay.py` with the file in this archive; commit/deploy and restart Power Admin. Do NOT replace `pc-power-admin.py` from an older ZIP; retain the v1.5.1 persistent-intake fix.
2. Open **Reload & republish — end-to-end**; enter existing job ID `cf0aead2-d558-4ca3-91d7-42b70cc5e8fe`.
3. Confirm `Queued 0 / Staged 85`. Click **3 · Analyse entire staged batch** again. It should show more exceptions and fewer eligible rows than the old 77/7 analysis; inspect them before approving.
4. Only after approving the revised list, press **4 · BACKUP + PUBLISH ELIGIBLE BATCH + SYNC GRAPH** once. Review the publication report including `publication_failures`, then confirm actual LIVE Trade pages.
5. Keep uncertain DP World duplicate, unverified source URLs and incorrect types in exceptions until research resolves them. No fabricated IMO, full dates, or relationship claims.

**Limitations:** This is a targeted safety fix, not full automated research or a complete remapping of every P&C entity class. Test first on a staging DB where available. Local tests verify syntax, date/type guards and isolation; *live Supabase publishing is untested*. The previous failed attempt may have committed earlier groups, so the reanalysis reads `pc_v10_publication_items` to exclude them.
