-- Power & Corridors SQL 034
-- Ingestion integrity and completion checks
-- Run AFTER 033_dependency_autocreate_engine.sql

begin;

-- Compact per-job health view for the Admin console.
drop view if exists pc_v_ingestion_job_health;
create view pc_v_ingestion_job_health as
with s as (
    select
        ingestion_job_id,
        count(*) as staged_total,
        count(*) filter (where review_status='applied' and validation_status='validated') as applied_validated,
        count(*) filter (where resolution_status='MATCHED') as matched,
        count(*) filter (where resolution_status='READY') as ready,
        count(*) filter (where resolution_status='PARTIAL') as partial,
        count(*) filter (where resolution_status='AMBIGUOUS') as ambiguous,
        count(*) filter (where resolution_status='BROKEN_REFERENCE') as broken_reference,
        count(*) filter (where resolution_status='INVALID') as invalid,
        count(*) filter (
            where coalesce(review_status,'pending') <> 'applied'
               or resolution_status in ('PARTIAL','AMBIGUOUS','BROKEN_REFERENCE','INVALID','UNRESOLVED')
        ) as operator_exceptions
    from pc_staged_records
    group by ingestion_job_id
)
select
    j.ingestion_job_id,
    j.status as job_status,
    j.created_at,
    coalesce(s.staged_total,0) as staged_total,
    coalesce(s.applied_validated,0) as applied_validated,
    coalesce(s.matched,0) as matched,
    coalesce(s.ready,0) as ready,
    coalesce(s.partial,0) as partial,
    coalesce(s.ambiguous,0) as ambiguous,
    coalesce(s.broken_reference,0) as broken_reference,
    coalesce(s.invalid,0) as invalid,
    coalesce(s.operator_exceptions,0) as operator_exceptions,
    case
      when coalesce(s.operator_exceptions,0)=0 then 'CLEAN'
      when coalesce(s.ambiguous,0)>0 then 'REVIEW_AMBIGUITY'
      when coalesce(s.broken_reference,0)>0 then 'REPAIR_REFERENCE'
      when coalesce(s.invalid,0)>0 then 'DOMAIN_MAPPING'
      when coalesce(s.partial,0)>0 then 'AUTO_RECONCILE_AGAIN'
      else 'REVIEW'
    end as health_status
from pc_ingestion_jobs j
left join s on s.ingestion_job_id=j.ingestion_job_id;

-- Canonical references that should never remain broken after a clean run.
drop view if exists pc_v_ingestion_integrity_failures;
create view pc_v_ingestion_integrity_failures as

-- Generic relationships with missing canonical endpoints.
select
    'RELATIONSHIP_SOURCE_MISSING'::text as failure_type,
    r.relationship_id::text as object_id,
    r.source_type as object_type,
    r.source_id as referenced_id,
    jsonb_build_object('relationship_type',r.relationship_type,'target_type',r.target_type,'target_id',r.target_id) as details
from pc_relationships r
where (
       (lower(r.source_type)='entity' and not exists(select 1 from pc_entities e where e.entity_id=r.source_id))
    or (lower(r.source_type)='asset' and not exists(select 1 from pc_assets a where a.asset_id=r.source_id))
    or (lower(r.source_type)='mobile_asset' and not exists(select 1 from pc_mobile_assets m where m.mobile_asset_id=r.source_id))
    or (lower(r.source_type)='event' and not exists(select 1 from pc_events e where e.event_id=r.source_id))
)

union all
select
    'RELATIONSHIP_TARGET_MISSING',
    r.relationship_id::text,
    r.target_type,
    r.target_id,
    jsonb_build_object('relationship_type',r.relationship_type,'source_type',r.source_type,'source_id',r.source_id)
from pc_relationships r
where (
       (lower(r.target_type)='entity' and not exists(select 1 from pc_entities e where e.entity_id=r.target_id))
    or (lower(r.target_type)='asset' and not exists(select 1 from pc_assets a where a.asset_id=r.target_id))
    or (lower(r.target_type)='mobile_asset' and not exists(select 1 from pc_mobile_assets m where m.mobile_asset_id=r.target_id))
    or (lower(r.target_type)='event' and not exists(select 1 from pc_events e where e.event_id=r.target_id))
)

union all
select
    'EVENT_LINK_EVENT_MISSING',
    l.event_link_id,
    'event',
    l.event_id,
    jsonb_build_object('linked_type',l.linked_type,'linked_id',l.linked_id,'relationship',l.relationship)
from pc_event_links l
where not exists(select 1 from pc_events e where e.event_id=l.event_id)

union all
select
    'EVENT_LINK_OBJECT_MISSING',
    l.event_link_id,
    l.linked_type,
    l.linked_id,
    jsonb_build_object('event_id',l.event_id,'relationship',l.relationship,'linked_name',l.linked_name)
from pc_event_links l
where (
       (lower(l.linked_type)='entity' and not exists(select 1 from pc_entities e where e.entity_id=l.linked_id))
    or (lower(l.linked_type)='asset' and not exists(select 1 from pc_assets a where a.asset_id=l.linked_id))
    or (lower(l.linked_type) in ('mobile_asset','vessel') and not exists(select 1 from pc_mobile_assets m where m.mobile_asset_id=l.linked_id))
);

-- Provenance check for automatically-created provisional objects.
drop view if exists pc_v_autocreated_dependency_quality;
create view pc_v_autocreated_dependency_quality as
select
    'entity'::text as canonical_type,
    e.entity_id as canonical_id,
    e.name,
    e.record_status,
    e.data_quality,
    case
      when coalesce(e.metadata->>'autocreated_dependency','false')::boolean
       and e.source_id is null
       and jsonb_array_length(
           case when jsonb_typeof(e.metadata->'research_sources')='array' then e.metadata->'research_sources' else '[]'::jsonb end
       )=0
      then 'MISSING_PROVENANCE'
      else 'OK'
    end as quality_status,
    e.metadata
from pc_entities e
where coalesce(e.metadata->>'autocreated_dependency','false')::boolean

union all
select
    'asset',
    a.asset_id,
    a.name,
    a.record_status,
    null::text,
    case
      when coalesce(a.metadata->>'autocreated_dependency','false')::boolean
       and jsonb_array_length(
           case when jsonb_typeof(a.metadata->'research_sources')='array' then a.metadata->'research_sources' else '[]'::jsonb end
       )=0
      then 'MISSING_PROVENANCE'
      else 'OK'
    end,
    a.metadata
from pc_assets a
where coalesce(a.metadata->>'autocreated_dependency','false')::boolean

union all
select
    'mobile_asset',
    m.mobile_asset_id,
    m.name,
    m.record_status,
    null::text,
    case
      when coalesce(m.metadata->>'autocreated_dependency','false')::boolean
       and jsonb_array_length(
           case when jsonb_typeof(m.metadata->'research_sources')='array' then m.metadata->'research_sources' else '[]'::jsonb end
       )=0
      then 'MISSING_PROVENANCE'
      else 'OK'
    end,
    m.metadata
from pc_mobile_assets m
where coalesce(m.metadata->>'autocreated_dependency','false')::boolean;

-- A single job-level QA result suitable for RPC/Admin display.
create or replace function pc_ingestion_quality_summary(p_ingestion_job_id uuid)
returns jsonb
language plpgsql
stable
security definer
set search_path=public
as $$
declare
    v_exceptions integer;
    v_ambiguous integer;
    v_partial integer;
    v_invalid integer;
    v_broken integer;
    v_ready integer;
begin
    select
        count(*),
        count(*) filter(where resolution_status='AMBIGUOUS'),
        count(*) filter(where resolution_status='PARTIAL'),
        count(*) filter(where resolution_status='INVALID'),
        count(*) filter(where resolution_status='BROKEN_REFERENCE'),
        count(*) filter(where resolution_status='READY')
    into v_exceptions,v_ambiguous,v_partial,v_invalid,v_broken,v_ready
    from pc_v_ingestion_operator_exceptions
    where ingestion_job_id=p_ingestion_job_id;

    return jsonb_build_object(
        'clean',v_exceptions=0,
        'operator_exceptions',v_exceptions,
        'ambiguous',v_ambiguous,
        'partial',v_partial,
        'invalid',v_invalid,
        'broken_reference',v_broken,
        'ready_unapplied',v_ready
    );
end;
$$;

commit;
