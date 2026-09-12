-- Power & Corridors Trade System
-- 023_fix_population_pipeline_status_counts.sql
-- Fixes multiplicative counts in pc_v_population_pipeline_status caused by
-- joining pc_staged_records directly to pc_staged_relationships.

begin;

create or replace view pc_v_population_pipeline_status as
with staged as (
    select
        ingestion_job_id,
        count(*) filter (
            where coalesce(review_status,'pending') <> 'rejected'
        ) as staged_records,
        count(*) filter (
            where resolution_status='MATCHED'
              and coalesce(review_status,'pending') <> 'rejected'
        ) as matched_records,
        count(*) filter (
            where resolution_status='NEW'
              and coalesce(review_status,'pending') <> 'rejected'
        ) as new_records,
        count(*) filter (
            where resolution_status='AMBIGUOUS'
              and coalesce(review_status,'pending') <> 'rejected'
        ) as ambiguous_records,
        count(*) filter (
            where coalesce(resolution_status,'UNRESOLVED')='UNRESOLVED'
              and target_table not in ('pc_relationships','pc_event_links','research_bundle')
              and coalesce(review_status,'pending') <> 'rejected'
        ) as unresolved_identity_records
    from pc_staged_records
    group by ingestion_job_id
),
rels as (
    select
        ingestion_job_id,
        count(*) as staged_relationships,
        count(*) filter (where resolution_status='READY') as ready_relationships,
        count(*) filter (where resolution_status='PARTIAL') as partial_relationships,
        count(*) filter (where resolution_status='ALREADY_EXISTS') as existing_relationships,
        count(*) filter (
            where resolution_status in ('AMBIGUOUS','BROKEN_REFERENCE')
        ) as relationship_exceptions
    from pc_staged_relationships
    group by ingestion_job_id
)
select
    j.ingestion_job_id,
    j.title,
    j.job_type,
    j.status as job_status,
    j.created_at,
    coalesce(s.staged_records,0) as staged_records,
    coalesce(s.matched_records,0) as matched_records,
    coalesce(s.new_records,0) as new_records,
    coalesce(s.ambiguous_records,0) as ambiguous_records,
    coalesce(s.unresolved_identity_records,0) as unresolved_identity_records,
    coalesce(r.staged_relationships,0) as staged_relationships,
    coalesce(r.ready_relationships,0) as ready_relationships,
    coalesce(r.partial_relationships,0) as partial_relationships,
    coalesce(r.existing_relationships,0) as existing_relationships,
    coalesce(r.relationship_exceptions,0) as relationship_exceptions
from pc_ingestion_jobs j
left join staged s on s.ingestion_job_id=j.ingestion_job_id
left join rels r on r.ingestion_job_id=j.ingestion_job_id;

comment on view pc_v_population_pipeline_status is
'Job-level population status with staged-record and staged-relationship counts aggregated independently to prevent multiplicative join inflation.';

commit;
