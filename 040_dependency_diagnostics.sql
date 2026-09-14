
-- 040_dependency_diagnostics.sql
-- Job-scoped diagnostics for staged event_links / relationships that remain BROKEN_REFERENCE.
-- Read-only diagnostic function. Does not mutate canonical or staged data.

create or replace function public.pc_debug_ingestion_dependencies(p_ingestion_job_id uuid)
returns table (
    staged_record_id uuid,
    target_table text,
    natural_key text,
    resolution_status text,
    review_status text,
    event_id text,
    event_exists boolean,
    linked_type text,
    linked_id text,
    linked_exists boolean,
    staged_parent_table text,
    staged_parent_status text,
    staged_parent_resolved_id text,
    source_id text,
    source_exists boolean,
    source_staged_resolved_id text,
    target_id text,
    target_exists boolean,
    target_staged_resolved_id text,
    diagnostic text
)
language sql
security definer
set search_path = public
as $$
with s as (
    select
        r.staged_record_id,
        r.target_table,
        r.natural_key,
        r.resolution_status,
        r.review_status,
        r.payload
    from public.pc_staged_records r
    where r.ingestion_job_id = p_ingestion_job_id
      and r.target_table in ('pc_event_links','pc_relationships')
      and coalesce(r.review_status,'pending') <> 'applied'
),
event_link_diag as (
    select
        s.staged_record_id,
        s.target_table,
        s.natural_key,
        s.resolution_status,
        s.review_status,
        s.payload->>'event_id' as event_id,
        exists(
            select 1 from public.pc_events e
            where e.event_id::text = s.payload->>'event_id'
        ) as event_exists,
        s.payload->>'linked_type' as linked_type,
        s.payload->>'linked_id' as linked_id,
        case lower(coalesce(s.payload->>'linked_type',''))
            when 'entity' then exists(select 1 from public.pc_entities x where x.entity_id::text = s.payload->>'linked_id')
            when 'asset' then exists(select 1 from public.pc_assets x where x.asset_id::text = s.payload->>'linked_id')
            when 'mobile_asset' then exists(select 1 from public.pc_mobile_assets x where x.mobile_asset_id::text = s.payload->>'linked_id')
            when 'vessel' then exists(select 1 from public.pc_mobile_assets x where x.mobile_asset_id::text = s.payload->>'linked_id')
            when 'event' then exists(select 1 from public.pc_events x where x.event_id::text = s.payload->>'linked_id')
            else false
        end as linked_exists,
        sp.target_table as staged_parent_table,
        sp.resolution_status as staged_parent_status,
        sp.resolved_entity_id::text as staged_parent_resolved_id,
        null::text as source_id,
        null::boolean as source_exists,
        null::text as source_staged_resolved_id,
        null::text as target_id,
        null::boolean as target_exists,
        null::text as target_staged_resolved_id,
        case
            when not exists(select 1 from public.pc_events e where e.event_id::text = s.payload->>'event_id')
                then 'PARENT_EVENT_MISSING'
            when lower(coalesce(s.payload->>'linked_type','')) not in ('entity','asset','mobile_asset','vessel','event')
                then 'UNSUPPORTED_LINKED_TYPE'
            when (
                case lower(coalesce(s.payload->>'linked_type',''))
                    when 'entity' then exists(select 1 from public.pc_entities x where x.entity_id::text = s.payload->>'linked_id')
                    when 'asset' then exists(select 1 from public.pc_assets x where x.asset_id::text = s.payload->>'linked_id')
                    when 'mobile_asset' then exists(select 1 from public.pc_mobile_assets x where x.mobile_asset_id::text = s.payload->>'linked_id')
                    when 'vessel' then exists(select 1 from public.pc_mobile_assets x where x.mobile_asset_id::text = s.payload->>'linked_id')
                    when 'event' then exists(select 1 from public.pc_events x where x.event_id::text = s.payload->>'linked_id')
                    else false
                end
            ) = false and sp.resolved_entity_id is not null
                then 'LINK_ID_STILL_LOGICAL__STAGED_PARENT_HAS_CANONICAL_ID'
            when (
                case lower(coalesce(s.payload->>'linked_type',''))
                    when 'entity' then exists(select 1 from public.pc_entities x where x.entity_id::text = s.payload->>'linked_id')
                    when 'asset' then exists(select 1 from public.pc_assets x where x.asset_id::text = s.payload->>'linked_id')
                    when 'mobile_asset' then exists(select 1 from public.pc_mobile_assets x where x.mobile_asset_id::text = s.payload->>'linked_id')
                    when 'vessel' then exists(select 1 from public.pc_mobile_assets x where x.mobile_asset_id::text = s.payload->>'linked_id')
                    when 'event' then exists(select 1 from public.pc_events x where x.event_id::text = s.payload->>'linked_id')
                    else false
                end
            ) = false
                then 'LINKED_ENDPOINT_MISSING'
            else 'ENDPOINTS_EXIST__RESOLVER_STATE_STALE'
        end as diagnostic
    from s
    left join lateral (
        select p.target_table, p.resolution_status, p.resolved_entity_id
        from public.pc_staged_records p
        where p.ingestion_job_id = p_ingestion_job_id
          and (
            (lower(coalesce(s.payload->>'linked_type',''))='entity'
                and p.target_table='pc_entities'
                and (p.payload->>'entity_id') = s.payload->>'linked_id')
            or
            (lower(coalesce(s.payload->>'linked_type',''))='asset'
                and p.target_table='pc_assets'
                and (p.payload->>'asset_id') = s.payload->>'linked_id')
            or
            (lower(coalesce(s.payload->>'linked_type','')) in ('mobile_asset','vessel')
                and p.target_table='pc_mobile_assets'
                and (p.payload->>'mobile_asset_id') = s.payload->>'linked_id')
            or
            (lower(coalesce(s.payload->>'linked_type',''))='event'
                and p.target_table='pc_events'
                and (p.payload->>'event_id') = s.payload->>'linked_id')
          )
        order by p.created_at desc nulls last
        limit 1
    ) sp on true
    where s.target_table='pc_event_links'
),
rel_diag as (
    select
        s.staged_record_id,
        s.target_table,
        s.natural_key,
        s.resolution_status,
        s.review_status,
        null::text as event_id,
        null::boolean as event_exists,
        null::text as linked_type,
        null::text as linked_id,
        null::boolean as linked_exists,
        null::text as staged_parent_table,
        null::text as staged_parent_status,
        null::text as staged_parent_resolved_id,
        s.payload->>'source_id' as source_id,
        case lower(coalesce(s.payload->>'source_type',''))
            when 'entity' then exists(select 1 from public.pc_entities x where x.entity_id::text = s.payload->>'source_id')
            when 'asset' then exists(select 1 from public.pc_assets x where x.asset_id::text = s.payload->>'source_id')
            when 'mobile_asset' then exists(select 1 from public.pc_mobile_assets x where x.mobile_asset_id::text = s.payload->>'source_id')
            when 'vessel' then exists(select 1 from public.pc_mobile_assets x where x.mobile_asset_id::text = s.payload->>'source_id')
            when 'event' then exists(select 1 from public.pc_events x where x.event_id::text = s.payload->>'source_id')
            else false
        end as source_exists,
        sp_src.resolved_entity_id::text as source_staged_resolved_id,
        s.payload->>'target_id' as target_id,
        case lower(coalesce(s.payload->>'target_type',''))
            when 'entity' then exists(select 1 from public.pc_entities x where x.entity_id::text = s.payload->>'target_id')
            when 'asset' then exists(select 1 from public.pc_assets x where x.asset_id::text = s.payload->>'target_id')
            when 'mobile_asset' then exists(select 1 from public.pc_mobile_assets x where x.mobile_asset_id::text = s.payload->>'target_id')
            when 'vessel' then exists(select 1 from public.pc_mobile_assets x where x.mobile_asset_id::text = s.payload->>'target_id')
            when 'event' then exists(select 1 from public.pc_events x where x.event_id::text = s.payload->>'target_id')
            else false
        end as target_exists,
        sp_tgt.resolved_entity_id::text as target_staged_resolved_id,
        case
            when (
                case lower(coalesce(s.payload->>'source_type',''))
                    when 'entity' then exists(select 1 from public.pc_entities x where x.entity_id::text = s.payload->>'source_id')
                    when 'asset' then exists(select 1 from public.pc_assets x where x.asset_id::text = s.payload->>'source_id')
                    when 'mobile_asset' then exists(select 1 from public.pc_mobile_assets x where x.mobile_asset_id::text = s.payload->>'source_id')
                    when 'vessel' then exists(select 1 from public.pc_mobile_assets x where x.mobile_asset_id::text = s.payload->>'source_id')
                    when 'event' then exists(select 1 from public.pc_events x where x.event_id::text = s.payload->>'source_id')
                    else false
                end
            ) = false and sp_src.resolved_entity_id is not null
                then 'SOURCE_ID_STILL_LOGICAL__STAGED_PARENT_HAS_CANONICAL_ID'
            when (
                case lower(coalesce(s.payload->>'target_type',''))
                    when 'entity' then exists(select 1 from public.pc_entities x where x.entity_id::text = s.payload->>'target_id')
                    when 'asset' then exists(select 1 from public.pc_assets x where x.asset_id::text = s.payload->>'target_id')
                    when 'mobile_asset' then exists(select 1 from public.pc_mobile_assets x where x.mobile_asset_id::text = s.payload->>'target_id')
                    when 'vessel' then exists(select 1 from public.pc_mobile_assets x where x.mobile_asset_id::text = s.payload->>'target_id')
                    when 'event' then exists(select 1 from public.pc_events x where x.event_id::text = s.payload->>'target_id')
                    else false
                end
            ) = false and sp_tgt.resolved_entity_id is not null
                then 'TARGET_ID_STILL_LOGICAL__STAGED_PARENT_HAS_CANONICAL_ID'
            else 'CHECK_ENDPOINT_EXISTENCE_COLUMNS'
        end as diagnostic
    from s
    left join lateral (
        select p.resolved_entity_id
        from public.pc_staged_records p
        where p.ingestion_job_id = p_ingestion_job_id
          and (
            (lower(coalesce(s.payload->>'source_type',''))='entity' and p.target_table='pc_entities' and p.payload->>'entity_id'=s.payload->>'source_id')
            or (lower(coalesce(s.payload->>'source_type',''))='asset' and p.target_table='pc_assets' and p.payload->>'asset_id'=s.payload->>'source_id')
            or (lower(coalesce(s.payload->>'source_type','')) in ('mobile_asset','vessel') and p.target_table='pc_mobile_assets' and p.payload->>'mobile_asset_id'=s.payload->>'source_id')
            or (lower(coalesce(s.payload->>'source_type',''))='event' and p.target_table='pc_events' and p.payload->>'event_id'=s.payload->>'source_id')
          )
        order by p.created_at desc nulls last limit 1
    ) sp_src on true
    left join lateral (
        select p.resolved_entity_id
        from public.pc_staged_records p
        where p.ingestion_job_id = p_ingestion_job_id
          and (
            (lower(coalesce(s.payload->>'target_type',''))='entity' and p.target_table='pc_entities' and p.payload->>'entity_id'=s.payload->>'target_id')
            or (lower(coalesce(s.payload->>'target_type',''))='asset' and p.target_table='pc_assets' and p.payload->>'asset_id'=s.payload->>'target_id')
            or (lower(coalesce(s.payload->>'target_type','')) in ('mobile_asset','vessel') and p.target_table='pc_mobile_assets' and p.payload->>'mobile_asset_id'=s.payload->>'target_id')
            or (lower(coalesce(s.payload->>'target_type',''))='event' and p.target_table='pc_events' and p.payload->>'event_id'=s.payload->>'target_id')
          )
        order by p.created_at desc nulls last limit 1
    ) sp_tgt on true
    where s.target_table='pc_relationships'
)
select * from event_link_diag
union all
select * from rel_diag
order by target_table,natural_key;
$$;

grant execute on function public.pc_debug_ingestion_dependencies(uuid) to authenticated;
