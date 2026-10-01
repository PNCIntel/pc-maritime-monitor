# P&C Connected Analyst Loader v2.0

This patch upgrades the existing Power Admin workflow without changing the database model.

## What changed

- Every unpublished core proposal is researched, including companies/vessels that already match canonical records.
- Article research can return up to 12 directly evidenced additional objects and 20 relationships instead of 6/10.
- A new connected-research stage runs **after canonical core publication** and researches directly loaded companies and vessels one evidence-backed hop deeper.
- Company research is split into dedicated facets: identity/ownership, leadership/offices, group structure/acquisitions, operations/projects/contracts, and verified vessel fleet.
- The analyst sees names/evidence only. Existing Supabase resolver RPCs handle canonical IDs.
- Source-backed findings can populate:
  - `pc_company_profiles`
  - `pc_company_offices`
  - `pc_people` + `pc_company_people_roles`
  - `pc_relationships`
  - `pc_mobile_assets`
  - `pc_vessel_identity_history`
  - `pc_company_operating_footprint`
  - `pc_transactions`
  - `pc_contracts` + `pc_contract_participants`
  - `pc_assets` + `pc_project_details`
- Merchant vessel creation requires a valid verified 7-digit IMO. Name-only fleet candidates are held.
- Announced/pending transactions are preserved as transactions and do not overwrite completed ownership.
- Connected research state is persisted in `pc_ingestion_jobs.source_scope` so it can resume after Streamlit restarts.
- Re-running the same source under v2 creates/reuses a v2 fingerprint rather than silently reusing an older v0.7/v1.x job.
- The document loader can optionally create a connected company-research review for the issuing organisation after saving the document.

## Files to deploy

Replace/add these files together:

- `pc-power-admin.py`
- `pc_intelligence_pipeline.py`
- `pc_v07_core.py`
- `pc_v16_research.py`
- `pc_document_loader.py`
- `pc_connected_research.py` (new)

No new SQL migration is required by this patch. It uses tables and RPCs already present in the supplied data model.

## Svitzer acceptance test

1. Deploy to staging.
2. Open **Research company**.
3. Company: `Svitzer`
4. Official website: `https://svitzer.com/`
5. Click **Research company**.
6. Review the category counts and evidence-backed findings.
7. Confirm one approval and click **Approve & populate company graph**.

### The test should no longer look like the old result

The old result (`Svitzer`, `Svitzer Fleet`, `Svitzer Regional Commercial Teams`) is not sufficient.

A useful Svitzer research pass should attempt all of these categories separately:

- company profile / headquarters
- named leadership and exact roles
- offices / operating footprint
- subsidiaries, acquisitions, parent/child relationships
- contracts / projects / partnerships
- verified individual vessels with IMO where found
- vessel identity history where evidence supports it
- research gaps for anything not verified

`Svitzer Fleet` must **not** become one physical asset. `Svitzer Regional Commercial Teams` must **not** become a company.

## Normal article/newsletter workflow

The analyst still uses **Load intelligence**:

1. paste URLs / upload newsletters, files or notes;
2. choose **AI web research + extraction** and prepare the package;
3. queue the package;
4. click **Research, resolve & POPULATE DATABASE**;
5. review the connected findings once and approve connected enrichment.

No SQL, canonical IDs or table selection is exposed to the analyst.

## Important limitations

This is a controlled v2 improvement, not a claim that every one of the ~360 database tables is now automatically populated. The connected publisher covers the specialist structures listed above, which are the critical paths for the Svitzer / AD Ports / DP World / KKR / MNG-St Helena cases.

The current document loader still stores the document, metadata and entity links first; v2 additionally creates a connected company-research review for the issuer. It does not yet convert every financial line item in an annual report into all financial specialist tables.

Dashboard reader fixes are separate from this loader patch. Publication into the canonical database does not by itself prove every Trade/Intelligence screen is querying the relevant table.

## Local validation performed

- All supplied Python files compile with `py_compile`.
- `test_connected_research.py`: 3 tests passed.
- Tests cover IMO checksum validation, prevention of generic fleet creation without verified IMO, and safe date/numeric cleaning.

Live Supabase and live OpenAI/web-search execution have not been run from this environment; staging is required before production deployment.
