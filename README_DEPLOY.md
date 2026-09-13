# P&C Workflow / Analyst Build

This package adds the orchestration layer discussed on 13 Sep 2026.

## Install SQL in this order
1. `027_workflow_orchestration.sql`
2. `028_document_ingestion.sql`
3. `029_intelligence_authoring.sql`
4. `030_distribution_lists.sql`
5. `031_reconciliation_cleanup.sql`

These are additive migrations. Existing SQL 010–026 remains in place.

## Deploy apps
- Replace the repository `pc-power-admin.py` with the included `pc-power-admin.py`.
- Add `pc-analyst-intelligence.py` as a new Streamlit app/entry point.

## Power Admin additions
- Workflow Center
- AI Research Workflow
- Bulk Import Workflow
- Multi-Table Bulk Loader
- Reconciliation Center
- Document Loader
- Distribution Lists

### Multi-table loader
XLSX: each worksheet can be mapped to a different canonical table.
CSV/JSON: if a `target_table` column exists, rows are automatically split by table.
The loader:
1. Maps source sections to canonical tables.
2. Suggests source-column → canonical-field mappings.
3. Keeps unmapped fields under `metadata.source_payload`.
4. Generates deterministic staging IDs for missing keys.
5. Stages all tables under one ingestion job.
6. Runs the standard reconciliation pipeline.

### Standard reconciliation
SQL 031 provides:
- `pc_cleanup_staging_names(job_uuid)`
- `pc_cleanup_staging_keys(job_uuid)`
- `pc_reconciliation_summary(job_uuid)`
- `pc_run_standard_reconciliation(job_uuid)`
- `pc_v_reconciliation_queue`
- `pc_v_stale_ingestion_jobs`

## Analyst Intelligence app
The authoring structure matches the P&C Intelligence site:
- Alerts
- Assessments
- Monitoring
- Situation Reports

An analyst can upload a DOCX/PDF/TXT/MD source document. The app can:
- parse known section headings into the structured form;
- optionally use AI to structure the document without outside research;
- save the source to `pc_documents`;
- save the report to `pc_intelligence_reports`;
- link canonical companies/entities, assets, vessels and events;
- generate web HTML and email-safe HTML;
- preserve sources and a 14-word summary.

The source document can populate only part of a report. Blank sections remain available for analyst completion.

## Email/distribution
SQL 030 and the Power Admin Distribution Lists page add:
- contacts
- distribution lists
- memberships
- CSV/XLSX contact import

Recipient/contact data remains separate from the trade entity model.


## SQL 032 — Event-first dependency engine

Install `032_event_first_dependency_engine.sql` after SQL 031.

This migration changes the ingestion model from independent-row processing to dependency-aware bundle reconciliation.

### New behavior

Research jobs are processed in this order:

1. Normalize staging names and keys.
2. Resolve candidate identities.
3. Apply deterministic NEW entities.
4. Apply deterministic NEW events.
5. Register research natural keys as aliases of canonical IDs.
6. Resolve normal event links and generic relationships.
7. Expand array-based `linked_entities` into individual canonical event links.
8. Infer event-link roles from the canonical event metadata where supported:
   - contractor
   - customer
   - awarding_authority
   - counterparty
   - participant
9. Apply READY event links and generic relationships.
10. Surface only remaining dependency exceptions and genuine ambiguities.

Primary entry point:

```sql
select pc_reconcile_ingestion_job('<JOB_UUID>'::uuid);
```

### New Power Admin pages

- **Bundle Review** — presents one AI/bulk/document ingestion job as a connected research bundle.
- **Dependency Graph** — groups remaining issues into dependency categories instead of raw PARTIAL/INVALID/BROKEN labels.

The intended operator workflow is now:

`Research → Review bundle → Resolve safe dependencies → Review true exceptions → Apply/QA`

The Canada Defence Drone Initiative case is the reference test: a research natural-key event plus three contractors, a customer and an awarding authority should resolve without manual SQL once the dependencies are staged.
