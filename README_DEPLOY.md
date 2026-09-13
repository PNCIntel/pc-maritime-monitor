# P&C Dependency Auto-Create + Compact Admin

This build changes the operating model from **manual cleanup** to **database-led dependency resolution**.

The analyst/operator should not have to create a company, facility, vessel, berth or corridor simply because a relationship references it. The database now tries to resolve that dependency first and, where the source evidence is sufficient and there is no ambiguity, creates a provisional canonical object automatically.

## Files

- `031_reconciliation_cleanup.sql` — existing cleanup helpers.
- `031A_fix_ingestion_jobs_timestamp.sql` — compatibility fix for ingestion-job timestamps.
- `032_event_first_dependency_engine.sql` — event-first baseline.
- `033_dependency_autocreate_engine.sql` — **new dependency auto-create engine**.
- `034_ingestion_quality_checks.sql` — compact health/integrity views and QA summary.
- `035_dependency_regression_checks.sql` — read-only regression checks.
- `pc-power-admin.py` — **new compact day-to-day Ingestion Console**.
- `pc-power-admin-legacy.py` — copy of the previous large Admin retained for specialist/migration work.

## SQL deployment order

If 031/032 are already installed, you only need to run:

1. `033_dependency_autocreate_engine.sql`
2. `034_ingestion_quality_checks.sql`

Then run `035_dependency_regression_checks.sql` as a read-only verification script.

## What SQL 033 changes

The new orchestration function is:

```sql
select pc_reconcile_ingestion_job_v2('<JOB_UUID>'::uuid);
```

Its flow is:

```text
normalize
→ prepare candidates
→ apply explicitly staged entities/assets/mobile assets/events
→ register aliases
→ resolve relationship endpoints
→ auto-create missing source-backed dependencies
→ resolve event-link dependencies
→ expand array event participants
→ apply READY event links and relationships
→ normalize stale staging statuses
→ return remaining operator exceptions
```

### Auto-create rules

The engine will auto-create a missing dependency only when:

- the staged record has source provenance (`source_id`, source URL, or `metadata.research_sources`), and
- the reference is not ambiguous, and
- the endpoint is a supported canonical class (`entity`, `asset`, or `mobile_asset`).

Auto-created records are deliberately conservative:

- `record_status = provisional`
- entity `data_quality = medium`
- source/research metadata is retained
- `autocreated_dependency = true` is written into metadata
- an alias is registered for the incoming name

### What remains human review

The engine intentionally does **not** guess through:

- multiple exact/normalized canonical matches
- genuine ambiguity
- conflicting evidence
- unsupported object types
- source-less dependencies

Those records stay in `pc_v_ingestion_operator_exceptions`.

## Failure patterns now covered

The new engine was designed from the real cleanup cases encountered in the P&C database:

- Missing company endpoint: **Al Ghurair Iron & Steel / EMSTEEL / Tenaris** pattern.
- Missing facility endpoint: **EGA dedicated berth** pattern.
- Short-name / alias endpoint: **KEZAD Musaffah / ICAD** pattern.
- Transport geography used as a graph endpoint: **E11 highway corridor** pattern.
- Array event participants: **Canada DDI multi-party award** pattern.
- Missing companies/vessels referenced by alerts and event links.
- Duplicate/ambiguous canonical endpoints remain exceptions rather than being guessed.

## Compact Admin

The new `pc-power-admin.py` intentionally has only three sections:

### Operations

- choose ingestion job
- see five useful counts
- `Run auto reconcile`
- `Apply ready`
- see only records that still need attention

### Exceptions

Only genuine analyst-review items grouped by exception type.

### Advanced

Small fallback page for:

- legacy reconcile
- staging normalization
- quality summary
- recent jobs

The previous large Admin is preserved as `pc-power-admin-legacy.py` rather than keeping every maintenance screen in the primary interface.

## Recommended deployment

Replace the current day-to-day `pc-power-admin.py` with the compact version in this package. Keep the legacy file in the repository but do not make it the normal operator entry point.

Then test against a recent ingestion job:

```sql
select pc_reconcile_ingestion_job_v2('1ff9915e-bf42-4397-b59a-176018e4bbe6'::uuid);
```

and inspect:

```sql
select *
from pc_v_ingestion_operator_exceptions
where ingestion_job_id='1ff9915e-bf42-4397-b59a-176018e4bbe6'::uuid
order by exception_type,natural_key;
```

For the current KEZAD example, the three missing anchor-cargo companies should now be created as provisional source-backed entities automatically and their relationships should resolve on the same reconcile pass. The truly ambiguous Khalifa Port rail endpoint should remain for review.

## Important next phase

SQL 033 fixes the **dependency layer**, which was the largest source of manual work. A subsequent domain-apply package should make `pc_observations`, `pc_trade_flows`, `pc_transactions`, energy/industrial specializations and other non-identity tables equally automatic. SQL 034 already makes those unsupported mappings visible without cluttering the operator workflow.
