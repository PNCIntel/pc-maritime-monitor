-- Power & Corridors
-- 038_event_dependency_normalization.sql
-- Purpose: normalize staged pc_events and pc_event_links so parent events can be
-- applied before dependent links, and existing canonical rows become terminal.
-- Safe to run repeatedly after 037.

begin;

-- ---------------------------------------------------------------------------
-- Helper: does a staged payload contain source provenance?
-- ---------------------------------------------------------------------------
create or replace function public.pc_payload_has_source(p_payload jsonb)
returns boolean
language sql
immutable
as $$
    select
        coalesce(p_payload->>'source_url','') ~* '^https?://'
        or coalesce(p_payload#>>'{metadata,source_url}','') ~* '^https?://'
        or exists (
            select 1
            from jsonb_array_elements_text(
                case
                    when jsonb_typeof(p_payload#>'{metadata,research_sources}')='array'
                    then p_payload#>'{metadata,research_sources}'
                    else '[]'::jsonb
                end
            ) x
            where x ~* '^https?://'
        );
$$;

-- ---------------------------------------------------------------------------
-- Normalize one ingestion job's event parents and event-link children.
-- This function does NOT write new canonical events/links. It only restores
-- staging states so the normal safe-apply engine can promote them in order.
-- Existing canonical rows are finalized as APPLIED no-ops.
-- ---------------------------------------------------------------------------
create or replace function public.pc_normalize_event_dependencies_v3(p_job_id uuid)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    v_events_payload_repaired integer := 0;
    v_events_existing integer := 0;
    v_events_new integer := 0;
    v_links_existing integer := 0;
    v_links_ready integer := 0;
begin
    -- 1) Recover event_type/source_url if an older workbook mapper stranded them.
    with u as (
        update public.pc_staged_records s
           set payload = jsonb_strip_nulls(
               coalesce(s.payload,'{}'::jsonb)
               || case
                    when coalesce(s.payload->>'event_type','')=''
                    then jsonb_build_object(
                        'event_type',
                        coalesce(
                            nullif(s.payload#>>'{metadata,source_payload,event_type}',''),
                            nullif(s.payload#>>'{metadata,event_type}','')
                        )
                    ) else '{}'::jsonb end
               || case
                    when coalesce(s.payload->>'source_url','')=''
                    then jsonb_build_object(
                        'source_url',
                        coalesce(
                            nullif(s.payload#>>'{metadata,source_payload,source_url}',''),
                            nullif(s.payload#>>'{metadata,source_url}',''),
                            (
                                select x
                                from jsonb_array_elements_text(
                                    case
                                        when jsonb_typeof(s.payload#>'{metadata,research_sources}')='array'
                                        then s.payload#>'{metadata,research_sources}'
                                        else '[]'::jsonb
                                    end
                                ) x
                                where x ~* '^https?://'
                                limit 1
                            )
                        )
                    ) else '{}'::jsonb end
           ),
           validation_status = case
               when lower(coalesce(s.review_status,''))='applied' then s.validation_status
               else 'pending'
           end
         where s.ingestion_job_id=p_job_id
           and s.target_table='pc_events'
           and lower(coalesce(s.review_status,'pending')) <> 'applied'
           and (
                coalesce(s.payload->>'event_type','')=''
                or coalesce(s.payload->>'source_url','')=''
           )
         returning 1
    )
    select count(*) into v_events_payload_repaired from u;

    -- 2) If the canonical event already exists, the staged parent is a terminal no-op.
    with u as (
        update public.pc_staged_records s
           set review_status='applied',
               validation_status='reviewed',
               resolution_status='ALREADY_EXISTS',
               resolution_method='canonical_event_exists',
               resolved_entity_id=s.payload->>'event_id',
               resolution_confidence=1.0,
               candidate_count=1
         where s.ingestion_job_id=p_job_id
           and s.target_table='pc_events'
           and lower(coalesce(s.review_status,'pending')) <> 'applied'
           and coalesce(s.payload->>'event_id','')<>''
           and exists (
               select 1 from public.pc_events e
               where e.event_id=s.payload->>'event_id'
           )
         returning 1
    )
    select count(*) into v_events_existing from u;

    -- 3) A source-backed, schema-complete event that does not yet exist is NEW.
    --    This deliberately overrides legacy INVALID classifications.
    with u as (
        update public.pc_staged_records s
           set resolution_status='NEW',
               resolution_method='event_schema_source_valid_v3',
               resolved_entity_id=null,
               resolution_confidence=1.0,
               candidate_count=0,
               validation_status='pending',
               review_status=case
                   when lower(coalesce(s.review_status,'')) in ('rejected','needs_changes') then s.review_status
                   else 'pending'
               end
         where s.ingestion_job_id=p_job_id
           and s.target_table='pc_events'
           and lower(coalesce(s.review_status,'pending')) <> 'applied'
           and upper(coalesce(s.resolution_status,'')) in ('INVALID','UNRESOLVED','PARTIAL','BROKEN_REFERENCE','')
           and coalesce(s.payload->>'event_id','')<>''
           and coalesce(s.payload->>'event_type','')<>''
           and public.pc_payload_has_source(s.payload)
           and not exists (
               select 1 from public.pc_events e
               where e.event_id=s.payload->>'event_id'
           )
         returning 1
    )
    select count(*) into v_events_new from u;

    -- 4) Existing canonical event links are also terminal no-ops.
    with u as (
        update public.pc_staged_records s
           set review_status='applied',
               validation_status='reviewed',
               resolution_status='ALREADY_EXISTS',
               resolution_method='canonical_event_link_exists',
               resolution_confidence=1.0,
               candidate_count=1
         where s.ingestion_job_id=p_job_id
           and s.target_table='pc_event_links'
           and lower(coalesce(s.review_status,'pending')) <> 'applied'
           and coalesce(s.payload->>'event_link_id','')<>''
           and exists (
               select 1 from public.pc_event_links l
               where l.event_link_id=s.payload->>'event_link_id'
           )
         returning 1
    )
    select count(*) into v_links_existing from u;

    -- 5) Reclassify BROKEN_REFERENCE/UNRESOLVED event links to READY as soon as
    --    both their parent event and polymorphic target exist canonically.
    with u as (
        update public.pc_staged_records s
           set resolution_status='READY',
               resolution_method='canonical_endpoints_exist_v3',
               resolution_confidence=1.0,
               candidate_count=1,
               validation_status='pending',
               review_status=case
                   when lower(coalesce(s.review_status,'')) in ('rejected','needs_changes') then s.review_status
                   else 'pending'
               end
         where s.ingestion_job_id=p_job_id
           and s.target_table='pc_event_links'
           and lower(coalesce(s.review_status,'pending')) <> 'applied'
           and upper(coalesce(s.resolution_status,'')) in ('BROKEN_REFERENCE','UNRESOLVED','PARTIAL','INVALID','')
           and coalesce(s.payload->>'event_link_id','')<>''
           and coalesce(s.payload->>'event_id','')<>''
           and coalesce(s.payload->>'linked_type','')<>''
           and coalesce(s.payload->>'linked_id','')<>''
           and coalesce(s.payload->>'relationship','')<>''
           and exists (
               select 1 from public.pc_events e
               where e.event_id=s.payload->>'event_id'
           )
           and (
                (lower(s.payload->>'linked_type')='entity' and exists (
                    select 1 from public.pc_entities e where e.entity_id=s.payload->>'linked_id'
                ))
             or (lower(s.payload->>'linked_type')='asset' and exists (
                    select 1 from public.pc_assets a where a.asset_id=s.payload->>'linked_id'
                ))
             or (lower(s.payload->>'linked_type') in ('mobile_asset','vessel') and exists (
                    select 1 from public.pc_mobile_assets m where m.mobile_asset_id=s.payload->>'linked_id'
                ))
             or (lower(s.payload->>'linked_type')='event' and exists (
                    select 1 from public.pc_events e2 where e2.event_id=s.payload->>'linked_id'
                ))
           )
         returning 1
    )
    select count(*) into v_links_ready from u;

    return jsonb_build_object(
        'job_id',p_job_id,
        'events_payload_repaired',v_events_payload_repaired,
        'events_existing_finalized',v_events_existing,
        'events_reclassified_new',v_events_new,
        'event_links_existing_finalized',v_links_existing,
        'event_links_reclassified_ready',v_links_ready
    );
end;
$$;

-- ---------------------------------------------------------------------------
-- Convenience state view: make INVALID/BROKEN_REFERENCE explicit rather than OTHER.
-- ---------------------------------------------------------------------------
create or replace view public.pc_v_ingestion_row_state_v3 as
select
    s.staged_record_id,
    s.ingestion_job_id,
    s.target_table,
    s.natural_key,
    s.review_status,
    s.resolution_status,
    s.validation_status,
    s.resolved_entity_id,
    case
        when lower(coalesce(s.review_status,''))='applied' then 'APPLIED'
        when lower(coalesce(s.review_status,''))='approved' then 'APPROVED'
        when upper(coalesce(s.resolution_status,''))='ALREADY_EXISTS' then 'NOOP_EXISTS'
        when upper(coalesce(s.resolution_status,'')) in ('INVALID','BROKEN_REFERENCE') then 'BLOCKED'
        when upper(coalesce(s.resolution_status,'')) in ('UNRESOLVED','AMBIGUOUS','PARTIAL') then 'EXCEPTION'
        when upper(coalesce(s.resolution_status,'')) in ('READY','MATCHED','NEW') then 'READY'
        else 'OTHER'
    end as state_class,
    case
        when upper(coalesce(s.resolution_status,''))='INVALID' then 'INVALID'
        when upper(coalesce(s.resolution_status,''))='BROKEN_REFERENCE' then 'BROKEN_REFERENCE'
        when upper(coalesce(s.resolution_status,''))='UNRESOLVED' then 'UNRESOLVED'
        when upper(coalesce(s.resolution_status,''))='AMBIGUOUS' then 'AMBIGUOUS_MATCH'
        when upper(coalesce(s.resolution_status,''))='PARTIAL' then 'PARTIAL_MATCH'
        when upper(coalesce(s.resolution_status,''))='ALREADY_EXISTS' then 'ALREADY_EXISTS'
        else null
    end as block_reason,
    s.payload,
    s.created_at
from public.pc_staged_records s;

create or replace view public.pc_v_ingestion_job_state_v3 as
select
    ingestion_job_id,
    count(*)::bigint as staged,
    count(*) filter (where state_class='READY')::bigint as ready,
    count(*) filter (where state_class='EXCEPTION')::bigint as exceptions,
    count(*) filter (where state_class='BLOCKED')::bigint as blocked,
    count(*) filter (where state_class='APPROVED')::bigint as approved,
    count(*) filter (where state_class='APPLIED')::bigint as applied,
    count(*) filter (where state_class='NOOP_EXISTS')::bigint as already_exists,
    count(*) filter (where state_class='OTHER')::bigint as other
from public.pc_v_ingestion_row_state_v3
group by ingestion_job_id;

grant execute on function public.pc_payload_has_source(jsonb) to authenticated, service_role;
grant execute on function public.pc_normalize_event_dependencies_v3(uuid) to authenticated, service_role;
grant select on public.pc_v_ingestion_row_state_v3 to authenticated, service_role;
grant select on public.pc_v_ingestion_job_state_v3 to authenticated, service_role;

commit;

-- COSCO smoke test after install:
-- select pc_normalize_event_dependencies_v3('09b15f8d-8a63-4370-a033-ca0c0377f6dc'::uuid);
-- select target_table,resolution_status,review_status,count(*)
-- from pc_staged_records
-- where ingestion_job_id='09b15f8d-8a63-4370-a033-ca0c0377f6dc'::uuid
-- group by 1,2,3 order by 1,2,3;
