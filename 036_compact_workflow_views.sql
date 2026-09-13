-- Power & Corridors SQL 036
-- Compact workflow views + compatibility patch for dependency exceptions.
-- Run AFTER 035_dependency_regression_checks.sql

begin;

-- Recreate the older dependency view with resolution_method exposed so SQL/debug
-- queries can use the same diagnostic field as the newer operator view.
drop view if exists pc_v_ingestion_dependency_exceptions;
create view pc_v_ingestion_dependency_exceptions as
select
    s.staged_record_id,
    s.ingestion_job_id,
    s.target_table,
    s.natural_key,
    s.resolution_status,
    s.review_status,
    s.validation_status,
    s.resolution_method,
    case
        when s.target_table='pc_event_links'
         and jsonb_typeof(s.payload->'linked_entities')='array'
         and s.resolution_status='BROKEN_REFERENCE' then 'EVENT_LINK_DEPENDENCY'
        when s.target_table='pc_event_links'
         and jsonb_typeof(s.payload->'linked_entities')='array' then 'ARRAY_EXPANSION_REQUIRED'
        when s.resolution_status='BROKEN_REFERENCE' then 'BROKEN_REFERENCE'
        when s.resolution_status='PARTIAL' then 'PARTIAL_RELATIONSHIP'
        when s.resolution_status='AMBIGUOUS' then 'TRUE_AMBIGUITY'
        when s.resolution_status='INVALID' then 'UNSUPPORTED_OR_INVALID_TARGET'
        when s.resolution_status='NEW'
         and coalesce(s.review_status,'pending')='pending' then 'READY_FOR_CANONICAL_PREP'
        else 'REVIEW'
    end as exception_type,
    s.payload,
    s.created_at
from pc_staged_records s
where coalesce(s.review_status,'pending') <> 'applied'
   or s.resolution_status in ('BROKEN_REFERENCE','PARTIAL','AMBIGUOUS','INVALID','UNRESOLVED');

-- One compact home view for the simplified Admin.
drop view if exists pc_v_workflow_home;
create view pc_v_workflow_home as
select
    j.ingestion_job_id,
    j.job_type,
    j.title,
    j.status as ingestion_status,
    j.created_at,
    h.staged_total,
    h.applied_validated,
    h.ready,
    h.partial,
    h.ambiguous,
    h.broken_reference,
    h.invalid,
    h.operator_exceptions,
    h.health_status,
    w.workflow_run_id,
    w.workflow_type,
    w.current_stage,
    w.stage_order,
    w.status as workflow_status,
    w.updated_at as workflow_updated_at
from pc_ingestion_jobs j
left join pc_v_ingestion_job_health h on h.ingestion_job_id=j.ingestion_job_id
left join lateral (
    select x.*
    from pc_workflow_runs x
    where x.ingestion_job_id=j.ingestion_job_id
    order by x.updated_at desc
    limit 1
) w on true
order by j.created_at desc;

commit;
