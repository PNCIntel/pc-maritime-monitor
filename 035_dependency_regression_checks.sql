-- Power & Corridors SQL 035
-- Regression checks for the dependency auto-create engine.
-- This file is read-only: it does not mutate canonical data.

-- 1. No relationship should point at a missing canonical endpoint.
select * from pc_v_ingestion_integrity_failures order by failure_type, object_id;

-- 2. Auto-created dependencies should retain provenance.
select *
from pc_v_autocreated_dependency_quality
where quality_status <> 'OK'
order by canonical_type,name;

-- 3. Recent jobs should show only genuine exceptions after reconcile.
select *
from pc_v_ingestion_job_health
order by created_at desc
limit 25;

-- 4. The historical failure patterns that motivated SQL 033 should now be handled
-- automatically when they recur in new jobs:
--   * missing company endpoint (Al Ghurair / EMSTEEL / Tenaris pattern)
--   * missing facility/berth endpoint (EGA berth pattern)
--   * alias/short-name endpoint (KEZAD Musaffah / ICAD pattern)
--   * transport geography promoted to a corridor asset (E11 pattern)
--   * array event participants created before event-link expansion (Canada DDI pattern)
--   * ambiguous canonical endpoints remain unresolved for analyst review (Khalifa Port duplicate pattern)
