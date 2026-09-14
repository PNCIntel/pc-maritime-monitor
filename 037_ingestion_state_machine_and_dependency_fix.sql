-- Power & Corridors
-- 037_ingestion_state_machine_and_dependency_fix.sql
-- Purpose: make ingestion monotonic, dependency-aware and operator-friendly.
-- Safe to run repeatedly.

begin;

-- ---------------------------------------------------------------------------
-- 1. Workflow stage ranking
-- ---------------------------------------------------------------------------
create or replace function public.pc_workflow_stage_rank(p_stage text)
returns integer
language sql
immutable
as $$
    select case upper(coalesce(p_stage,''))
        when 'UPLOAD' then 1
        when 'MAP_TABLES' then 2
        when 'MAP_FIELDS' then 3
        when 'FILL_KEYS' then 4
        when 'STAGE' then 5
        when 'PREPARE_IDS' then 6
        when 'RECONCILE' then 7
        when 'RELATIONSHIPS' then 8
        when 'REVIEW' then 9
        when 'APPLY' then 10
        when 'QA' then 11
        when 'COMPLETE' then 12
        else 0
    end;
$$;

-- ---------------------------------------------------------------------------
-- 2. Applied staging rows are terminal.
--    Reconciliation may enrich diagnostics, but it must never move an APPLIED
--    row backwards into pending/partial/broken-reference/etc.
-- ---------------------------------------------------------------------------
create or replace function public.pc_guard_applied_staging_terminal()
returns trigger
language plpgsql
as $$
begin
    if lower(coalesce(old.review_status,'')) = 'applied' then
        new.review_status := 'applied';
        new.resolution_status := old.resolution_status;
        new.resolved_entity_id := old.resolved_entity_id;
        new.resolution_method := old.resolution_method;
        new.resolution_confidence := old.resolution_confidence;
        new.candidate_count := old.candidate_count;
        new.validation_status := old.validation_status;
    end if;
    return new;
end;
$$;

drop trigger if exists trg_pc_staged_records_applied_terminal on public.pc_staged_records;
create trigger trg_pc_staged_records_applied_terminal
before update on public.pc_staged_records
for each row execute function public.pc_guard_applied_staging_terminal();

-- ---------------------------------------------------------------------------
-- 3. Workflow stage progression is monotonic.
-- ---------------------------------------------------------------------------
create or replace function public.pc_guard_workflow_monotonic()
returns trigger
language plpgsql
as $$
declare
    old_rank integer;
    new_rank integer;
begin
    old_rank := greatest(coalesce(old.stage_order,0), public.pc_workflow_stage_rank(old.current_stage));
    new_rank := greatest(coalesce(new.stage_order,0), public.pc_workflow_stage_rank(new.current_stage));

    if new_rank < old_rank then
        new.current_stage := old.current_stage;
        new.stage_order := old.stage_order;
        if lower(coalesce(old.status,'')) in ('completed','complete','success','succeeded') then
            new.status := old.status;
        end if;
    end if;
    return new;
end;
$$;

drop trigger if exists trg_pc_workflow_runs_monotonic on public.pc_workflow_runs;
create trigger trg_pc_workflow_runs_monotonic
before update on public.pc_workflow_runs
for each row execute function public.pc_guard_workflow_monotonic();

-- ---------------------------------------------------------------------------
-- 4. Repair legacy staged payloads where the Excel field existed but an older
--    mapper stranded it in metadata/source_payload or dropped source_url.
-- ---------------------------------------------------------------------------
create or replace function public.pc_repair_staged_payload_v2(p_job_id uuid)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    v_updated integer := 0;
begin
    with repaired as (
        update public.pc_staged_records s
        set payload = jsonb_strip_nulls(
            coalesce(s.payload,'{}'::jsonb)
            || case
                when s.target_table='pc_entities'
                 and coalesce(s.payload->>'entity_type','')=''
                then jsonb_build_object(
                    'entity_type',
                    coalesce(
                        nullif(s.payload#>>'{metadata,source_payload,entity_type}',''),
                        case
                            when lower(coalesce(s.payload->>'subtype',s.payload#>>'{metadata,source_payload,subtype}','')) ~ '(government|municipality|authority|agency)' then 'government_entity'
                            when lower(coalesce(s.payload->>'subtype',s.payload#>>'{metadata,source_payload,subtype}','')) ~ '(institutional_investor|pension_fund)' then 'institutional_investor'
                            else 'company'
                        end
                    )
                ) else '{}'::jsonb end
            || case
                when s.target_table='pc_assets'
                 and coalesce(s.payload->>'asset_type','')=''
                then jsonb_build_object(
                    'asset_type',
                    coalesce(
                        nullif(s.payload#>>'{metadata,source_payload,asset_type}',''),
                        case
                            when lower(coalesce(s.payload->>'subtype',s.payload#>>'{metadata,source_payload,subtype}','')) like '%terminal%' then 'terminal'
                            when lower(coalesce(s.payload->>'subtype',s.payload#>>'{metadata,source_payload,subtype}','')) like '%port%' then 'port'
                            when lower(coalesce(s.payload->>'subtype',s.payload#>>'{metadata,source_payload,subtype}','')) ~ '(rail|yard)' then 'rail_asset'
                            else 'infrastructure_asset'
                        end
                    )
                ) else '{}'::jsonb end
            || case
                when s.target_table='pc_mobile_assets'
                 and coalesce(s.payload->>'asset_type','')=''
                then jsonb_build_object(
                    'asset_type',
                    coalesce(nullif(s.payload#>>'{metadata,source_payload,asset_type}',''),'vessel')
                ) else '{}'::jsonb end
            || case
                when s.target_table='pc_events'
                 and coalesce(s.payload->>'event_type','')=''
                 and coalesce(s.payload#>>'{metadata,source_payload,event_type}','')<>''
                then jsonb_build_object('event_type',s.payload#>>'{metadata,source_payload,event_type}')
                else '{}'::jsonb end
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
        validation_status = case when lower(coalesce(s.review_status,''))='applied' then s.validation_status else 'pending' end
        where s.ingestion_job_id = p_job_id
          and lower(coalesce(s.review_status,'pending')) <> 'applied'
        returning 1
    )
    select count(*) into v_updated from repaired;

    return jsonb_build_object('job_id',p_job_id,'updated',v_updated);
end;
$$;

-- ---------------------------------------------------------------------------
-- 5. ALREADY_EXISTS is a successful no-op, not a blocker.
-- ---------------------------------------------------------------------------
create or replace function public.pc_finalize_already_exists_v2(p_job_id uuid)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    v_count integer := 0;
begin
    update public.pc_staged_records
       set review_status='applied',
           validation_status='reviewed'
     where ingestion_job_id=p_job_id
       and upper(coalesce(resolution_status,''))='ALREADY_EXISTS'
       and lower(coalesce(review_status,'pending')) <> 'applied';
    get diagnostics v_count = row_count;
    return jsonb_build_object('job_id',p_job_id,'finalized',v_count);
end;
$$;

-- ---------------------------------------------------------------------------
-- 6. Requeue BROKEN_REFERENCE event links once their parent/target now exists.
--    The existing relationship resolver can then do its normal work.
-- ---------------------------------------------------------------------------
create or replace function public.pc_requeue_resolved_event_links_v2(p_job_id uuid)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    v_count integer := 0;
begin
    update public.pc_staged_records s
       set resolution_status='UNRESOLVED',
           resolution_method='dependency_requeued',
           validation_status='pending'
     where s.ingestion_job_id=p_job_id
       and s.target_table='pc_event_links'
       and upper(coalesce(s.resolution_status,''))='BROKEN_REFERENCE'
       and lower(coalesce(s.review_status,'pending')) <> 'applied'
       and exists (
            select 1 from public.pc_events e
            where e.event_id = s.payload->>'event_id'
       )
       and (
            (lower(s.payload->>'linked_type')='entity' and exists (select 1 from public.pc_entities e where e.entity_id=s.payload->>'linked_id'))
         or (lower(s.payload->>'linked_type')='asset' and exists (select 1 from public.pc_assets a where a.asset_id=s.payload->>'linked_id'))
         or (lower(s.payload->>'linked_type') in ('mobile_asset','vessel') and exists (select 1 from public.pc_mobile_assets m where m.mobile_asset_id=s.payload->>'linked_id'))
         or (lower(s.payload->>'linked_type')='event' and exists (select 1 from public.pc_events e2 where e2.event_id=s.payload->>'linked_id'))
       );
    get diagnostics v_count = row_count;
    return jsonb_build_object('job_id',p_job_id,'requeued',v_count);
end;
$$;

-- ---------------------------------------------------------------------------
-- 7. Authoritative row-state view. Mutually exclusive state_class.
-- ---------------------------------------------------------------------------
create or replace view public.pc_v_ingestion_row_state_v2 as
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
        when upper(coalesce(s.resolution_status,'')) in ('UNRESOLVED','AMBIGUOUS','PARTIAL') then 'EXCEPTION'
        when upper(coalesce(s.resolution_status,'')) in ('INVALID','BROKEN_REFERENCE') then 'BLOCKED'
        when upper(coalesce(s.resolution_status,''))='ALREADY_EXISTS' then 'NOOP_EXISTS'
        when upper(coalesce(s.resolution_status,'')) in ('READY','MATCHED','NEW') then 'READY'
        else 'OTHER'
    end as state_class,
    case
        when lower(coalesce(s.review_status,''))='applied' then null
        when upper(coalesce(s.resolution_status,''))='BROKEN_REFERENCE' then 'BROKEN_REFERENCE'
        when upper(coalesce(s.resolution_status,''))='INVALID' then 'INVALID'
        when upper(coalesce(s.resolution_status,''))='AMBIGUOUS' then 'AMBIGUOUS_MATCH'
        when upper(coalesce(s.resolution_status,''))='PARTIAL' then 'PARTIAL_MATCH'
        when upper(coalesce(s.resolution_status,''))='UNRESOLVED' then 'UNRESOLVED'
        when upper(coalesce(s.resolution_status,''))='ALREADY_EXISTS' then 'ALREADY_EXISTS'
        else null
    end as block_reason,
    s.payload,
    s.created_at
from public.pc_staged_records s;

create or replace view public.pc_v_ingestion_job_state_v2 as
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
from public.pc_v_ingestion_row_state_v2
group by ingestion_job_id;

grant select on public.pc_v_ingestion_row_state_v2 to authenticated, service_role;
grant select on public.pc_v_ingestion_job_state_v2 to authenticated, service_role;
grant execute on function public.pc_repair_staged_payload_v2(uuid) to authenticated, service_role;
grant execute on function public.pc_finalize_already_exists_v2(uuid) to authenticated, service_role;
grant execute on function public.pc_requeue_resolved_event_links_v2(uuid) to authenticated, service_role;

commit;

-- Suggested smoke tests after install:
-- select * from pc_v_ingestion_job_state_v2 order by staged desc;
-- select state_class, block_reason, target_table, count(*)
-- from pc_v_ingestion_row_state_v2
-- where ingestion_job_id='<JOB_UUID>'::uuid
-- group by 1,2,3 order by 4 desc;
