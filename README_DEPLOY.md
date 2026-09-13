# P&C Workflow Console v5 — 13 Sep 2026

This package restores the complete operator workflow without restoring the oversized Admin navigation.

## Day-to-day navigation

The new `pc-power-admin.py` exposes only seven destinations:

1. **Home** — workflow/job status.
2. **AI Research** — run source-backed AI research into staging.
3. **Bulk Load** — upload CSV/XLSX/JSON, map sections/fields, stage, then auto-reconcile.
4. **Documents** — save PDF/DOCX/TXT/MD source documents, link them to canonical objects, optionally AI-extract facts, then auto-reconcile.
5. **Email & Distribution** — contacts, lists and CSV/XLSX contact imports.
6. **Reconcile & Review** — dependency auto-create, endpoint resolution and genuine exceptions.
7. **System** — QA/governance fallback.

The old broad Admin is retained as `pc-power-admin-legacy.py` for specialist maintenance only.

## SQL install order

Run these in Supabase SQL Editor, in order:

```text
027_workflow_orchestration.sql
028_document_ingestion.sql
029_intelligence_authoring.sql
030_distribution_lists.sql
031_reconciliation_cleanup.sql
031A_fix_ingestion_jobs_timestamp.sql   # compatibility patch where needed
032_event_first_dependency_engine.sql
033_dependency_autocreate_engine.sql
034_ingestion_quality_checks.sql
035_dependency_regression_checks.sql
036_compact_workflow_views.sql
```

`036_compact_workflow_views.sql` also recreates `pc_v_ingestion_dependency_exceptions` with `resolution_method`, fixing the debug-query mismatch encountered during KEZAD testing.

## Key behavior change

All workflows now prefer:

```sql
select pc_reconcile_ingestion_job_v2('<job-id>'::uuid);
```

This means AI research, bulk imports and document extraction can create source-backed missing dependencies before relationships are resolved. Straightforward missing companies/facilities should not be an operator task.

## New-load test

Use **AI Research**, **Bulk Load**, or **Documents** to create a fresh job. After staging, the console runs the v2 dependency engine. Go to **Reconcile & Review** only if exceptions remain.

Expected operator exceptions after a healthy run are limited to real ambiguity, conflicting evidence, broken references or unsupported structures.
