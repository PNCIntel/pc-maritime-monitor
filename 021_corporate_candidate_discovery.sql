-- Power & Corridors Trade System
-- 021_corporate_candidate_discovery.sql
-- Makes company/entity candidates discoverable across canonical data, staged entity rows,
-- and staged relationship endpoints, independent of incorrect ingestion-job titles/assignment.

begin;

drop view if exists pc_v_corporate_entity_candidates;

create view pc_v_corporate_entity_candidates as

-- Canonical entities.
select
    'canonical'::text as candidate_origin,
    e.entity_id,
    e.name,
    e.entity_type,
    e.subtype,
    null::uuid as staged_record_id,
    null::uuid as ingestion_job_id,
    null::text as ingestion_job_title,
    'MATCHED'::text as resolution_status,
    null::text as source_id,
    '{}'::jsonb as metadata
from pc_entities e
where coalesce(trim(e.name),'') <> ''

union all

-- Staged entity records from every ingestion job.
select
    'staged_entity'::text as candidate_origin,
    coalesce(s.resolved_entity_id, s.payload ->> 'entity_id') as entity_id,
    coalesce(nullif(trim(s.payload ->> 'name'),''), s.natural_key) as name,
    coalesce(nullif(trim(s.payload ->> 'entity_type'),''), s.target_entity_type, 'entity') as entity_type,
    nullif(trim(s.payload ->> 'subtype'),'') as subtype,
    s.staged_record_id,
    s.ingestion_job_id,
    j.title as ingestion_job_title,
    coalesce(s.resolution_status,'UNRESOLVED') as resolution_status,
    s.source_id,
    coalesce(s.payload -> 'metadata','{}'::jsonb) as metadata
from pc_staged_records s
left join pc_ingestion_jobs j on j.ingestion_job_id=s.ingestion_job_id
where s.target_table='pc_entities'
  and coalesce(s.review_status,'pending') <> 'rejected'
  and coalesce(trim(coalesce(s.payload ->> 'name',s.natural_key)),'') <> ''

union all

-- Entity endpoints already present inside staged generic relationships.
-- This recovers names even when the underlying staged entity was attached to a bad job
-- or has already moved out of the pending review set.
select distinct
    'relationship_endpoint'::text as candidate_origin,
    sr.resolved_from_entity_id as entity_id,
    sr.from_name as name,
    'entity'::text as entity_type,
    null::text as subtype,
    sr.source_staged_record_id as staged_record_id,
    sr.ingestion_job_id,
    j.title as ingestion_job_title,
    coalesce(sr.resolution_status,'UNRESOLVED') as resolution_status,
    sr.source_id,
    '{}'::jsonb as metadata
from pc_staged_relationships sr
left join pc_ingestion_jobs j on j.ingestion_job_id=sr.ingestion_job_id
where sr.from_entity_type='entity'
  and coalesce(trim(sr.from_name),'') <> ''

union all

select distinct
    'relationship_endpoint'::text as candidate_origin,
    sr.resolved_to_entity_id as entity_id,
    sr.to_name as name,
    'entity'::text as entity_type,
    null::text as subtype,
    sr.source_staged_record_id as staged_record_id,
    sr.ingestion_job_id,
    j.title as ingestion_job_title,
    coalesce(sr.resolution_status,'UNRESOLVED') as resolution_status,
    sr.source_id,
    '{}'::jsonb as metadata
from pc_staged_relationships sr
left join pc_ingestion_jobs j on j.ingestion_job_id=sr.ingestion_job_id
where sr.to_entity_type='entity'
  and coalesce(trim(sr.to_name),'') <> '';

comment on view pc_v_corporate_entity_candidates is
'Corporate entity candidate pool across canonical entities, all staged entity rows, and staged relationship endpoints. Used by Power Admin so corporate link building is not constrained by incorrect ingestion-job assignment.';

commit;
