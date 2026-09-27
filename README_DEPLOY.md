# P&C v1.5.5 — one-file canonical matching correction

## Why this file

The uploaded current `pc_v15_bulk_replay.py` keeps the extraction and staging job, but its publisher still compares strict `entity_type` / `asset_type` strings and lacks split-name and legal-suffix alias discovery. It also incorrectly treats `YYYY-MM` dates in JSON metadata as SQL DATE errors. This replacement corrects those three defects without changing source data or database schema.

## Deploy

1. Replace the root `pc_v15_bulk_replay.py` in the EXISTING Power Admin repository with the file under this package. Do not replace `pc-power-admin.py` or any Trade/Intelligence file.
2. Redeploy and check the Reload & republish page displays `Publisher build: 1.5.5-alias-type-date`.
3. Use the EXISTING staged job `cf0aead2-d558-4ca3-91d7-42b70cc5e8fe`. Do not re-extract, requeue, or reset staging.
4. Click `3 · Analyse entire staged batch for automatic publication`. Inspect the fresh eligible and exception exports. Do not approve old results.
5. **Do not publish the complete job until the outstanding misclassified records have been re-extracted/corrected and the source-backed event dependencies verified.** This patch fixes matching—not automatic research or classification repair.

## What changes

- Canonical aliases embedded in names (`X / Y`) are considered for exact identity discovery; known legal endings (S.A., Ltd, LLC and similar) are stripped for candidate discovery. Multiple identities still remain exceptions.
- `government` versus `government_agency`, `company` versus `ports_logistics_group`, and `proposed_port` versus `port` no longer generate false "type disagrees" exceptions when there is only one matching canonical identity. Port versus terminal remains distinct.
- Different country evidence remains an explicit hold; no country conflict is silently merged. `Port of Los Angeles` is only mapped to the harbour authority when the incoming type actually describes a compatible authority; an infrastructure port remains separate.
- Month-only dates in JSON metadata (e.g. `metadata.seizure_date: 2026-04`) preserve their source precision and no longer block the whole mobile-asset record. Incomplete top-level SQL dates such as `start_date: 2024-06` remain on hold—no invented day.
- Eligible preview now shows the actual extracted name/title rather than an internal slug; old approval checkbox is cleared on re-analysis.

## Remaining work, explicitly not claimed as fixed

- A record named `HPC ... advisory 2026` must be rewritten as a sourced **development linked to existing HPC**, not approved as a new company. The current stage payload cannot safely be rewritten by name alone.
- Source-linked repairs of vessel records (Vindnes/Vestnes) and crane-fleet deliveries still require correct target schema and source-specific facts from the existing staged payload/source material.
- Some newsletter records have **no original article URL** in their staging rows. They must be researched from the PDF's links or primary documents before public publication.
- No production Supabase mutation, publication, graph sync, or Trade UI verification was performed in this environment.

`test_local.py` runs 13 offline regression assertions and does not connect to the database.
