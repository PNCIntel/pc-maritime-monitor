-- Power & Corridors
-- 039_dependency_endpoint_remap.sql
-- Purpose: remap staged event-link and relationship endpoints from workbook/logical IDs
-- to canonical IDs resolved earlier in the same ingestion job.
-- This fixes the common pattern where a staged entity MATCHED an existing canonical
-- entity under a different ID, but child event_links/relationships still point at the
-- workbook ID and remain BROKEN_REFERENCE/PARTIAL.
-- Safe to run repeatedly after 037 and 038.

begin;

-- ---------------------------------------------------------------------------
-- Canonical existence helper by logical object type.
-- ---------------------------------------------------------------------------
create or replace function public.pc_canonical_object_exists(p_type text, p_id text)
returns boolean
language plpgsql
stable
security definer
set search_path=public
as $$
declare
    t text := lower(coalesce(p_type,''));
begin
    if coalesce(p_id,'')='' then return false; end if;

    if t='entity' then
        return exists(select 1 from public.pc_entities where entity_id=p_id);
    elsif t='asset' then
        return exists(select 1 from public.pc_assets where asset_id=p_id);
    elsif t in ('mobile_asset','vessel') then
        return exists(select 1 from public.pc_mobile_assets where mobile_asset_id=p_id);
    elsif t='event' then
        return exists(select 1 from public.pc_events where event_id=p_id);
    else
        return false;
    end if;
end;
$$;

-- ---------------------------------------------------------------------------
-- Resolve one job-local workbook/logical ID to the canonical ID.
-- Preference order:
--   1. ID already exists canonically -> keep it
--   2. matching staged parent row's resolved_entity_id, if canonical
--   3. matching staged parent row's own payload ID, if canonical (NEW/applied case)
--   4. otherwise return original ID unchanged
-- ---------------------------------------------------------------------------
create or replace function public.pc_resolve_job_object_id_v4(
    p_job_id uuid,
    p_type text,
    p_logical_id text
)
returns text
language plpgsql
stable
security definer
set search_path=public
as $$
declare
    t text := lower(coalesce(p_type,''));
    tbl text;
    id_field text;
    v text;
begin
    if coalesce(p_logical_id,'')='' then return p_logical_id; end if;
    if public.pc_canonical_object_exists(t,p_logical_id) then return p_logical_id; end if;

    if t='entity' then
        tbl:='pc_entities'; id_field:='entity_id';
    elsif t='asset' then
        tbl:='pc_assets'; id_field:='asset_id';
    elsif t in ('mobile_asset','vessel') then
        tbl:='pc_mobile_assets'; id_field:='mobile_asset_id';
    elsif t='event' then
        tbl:='pc_events'; id_field:='event_id';
    else
        return p_logical_id;
    end if;

    -- First prefer an explicit resolved canonical ID from the staged parent.
    select s.resolved_entity_id
      into v
      from public.pc_staged_records s
     where s.ingestion_job_id=p_job_id
       and s.target_table=tbl
       and (
            coalesce(s.payload->>id_field,'')=p_logical_id
            or coalesce(s.natural_key,'')=p_logical_id
            or coalesce(s.source_record_key,'')=p_logical_id
       )
       and coalesce(s.resolved_entity_id,'')<>''
     order by
       case when lower(coalesce(s.review_status,''))='applied' then 0 else 1 end,
       case when upper(coalesce(s.resolution_status,''))='MATCHED' then 0 else 1 end,
       s.created_at desc
     limit 1;

    if coalesce(v,'')<>'' and public.pc_canonical_object_exists(t,v) then
        return v;
    end if;

    -- Then accept the staged parent payload ID when that object now exists canonically.
    select s.payload->>id_field
      into v
      from public.pc_staged_records s
     where s.ingestion_job_id=p_job_id
       and s.target_table=tbl
       and (
            coalesce(s.payload->>id_field,'')=p_logical_id
            or coalesce(s.natural_key,'')=p_logical_id
            or coalesce(s.source_record_key,'')=p_logical_id
       )
     order by
       case when lower(coalesce(s.review_status,''))='applied' then 0 else 1 end,
       s.created_at desc
     limit 1;

    if coalesce(v,'')<>'' and public.pc_canonical_object_exists(t,v) then
        return v;
    end if;

    return p_logical_id;
end;
$$;

-- ---------------------------------------------------------------------------
-- Rewrite event-link and generic relationship endpoints for one job, then
-- promote rows whose canonical endpoints now exist.
-- ---------------------------------------------------------------------------
create or replace function public.pc_rewrite_dependency_endpoints_v4(p_job_id uuid)
returns jsonb
language plpgsql
security definer
set search_path=public
as $$
declare
    v_event_links_rewritten integer := 0;
    v_event_links_ready integer := 0;
    v_relationships_rewritten integer := 0;
    v_relationships_ready integer := 0;
    v_event_links_existing integer := 0;
    v_relationships_existing integer := 0;
begin
    -- A) Rewrite event_id / linked_id using same-job parent resolution mappings.
    with x as (
        select
            s.staged_record_id,
            s.payload,
            public.pc_resolve_job_object_id_v4(p_job_id,'event',s.payload->>'event_id') as new_event_id,
            public.pc_resolve_job_object_id_v4(p_job_id,s.payload->>'linked_type',s.payload->>'linked_id') as new_linked_id
        from public.pc_staged_records s
        where s.ingestion_job_id=p_job_id
          and s.target_table='pc_event_links'
          and lower(coalesce(s.review_status,'pending')) <> 'applied'
    ), u as (
        update public.pc_staged_records s
           set payload = jsonb_set(
                         jsonb_set(coalesce(s.payload,'{}'::jsonb),'{event_id}',to_jsonb(x.new_event_id),true),
                         '{linked_id}',to_jsonb(x.new_linked_id),true
                       ),
               validation_status='pending',
               resolution_method=case
                    when x.new_event_id is distinct from (s.payload->>'event_id')
                      or x.new_linked_id is distinct from (s.payload->>'linked_id')
                    then 'job_endpoint_remap_v4'
                    else s.resolution_method
               end
          from x
         where s.staged_record_id=x.staged_record_id
           and (
                x.new_event_id is distinct from (s.payload->>'event_id')
                or x.new_linked_id is distinct from (s.payload->>'linked_id')
           )
        returning 1
    )
    select count(*) into v_event_links_rewritten from u;

    -- B) Finalize canonical event links that already exist by event_link_id.
    with u as (
        update public.pc_staged_records s
           set review_status='applied',
               validation_status='reviewed',
               resolution_status='ALREADY_EXISTS',
               resolution_method='canonical_event_link_exists_v4',
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
    select count(*) into v_event_links_existing from u;

    -- C) Promote event links to READY when both remapped endpoints now exist.
    with u as (
        update public.pc_staged_records s
           set resolution_status='READY',
               resolution_method='canonical_endpoints_exist_v4',
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
           and coalesce(s.payload->>'event_link_id','')<>''
           and coalesce(s.payload->>'event_id','')<>''
           and coalesce(s.payload->>'linked_type','')<>''
           and coalesce(s.payload->>'linked_id','')<>''
           and coalesce(s.payload->>'relationship','')<>''
           and public.pc_canonical_object_exists('event',s.payload->>'event_id')
           and public.pc_canonical_object_exists(s.payload->>'linked_type',s.payload->>'linked_id')
        returning 1
    )
    select count(*) into v_event_links_ready from u;

    -- D) Rewrite generic relationship endpoints using the same parent mappings.
    with x as (
        select
            s.staged_record_id,
            s.payload,
            public.pc_resolve_job_object_id_v4(p_job_id,s.payload->>'source_type',s.payload->>'source_id') as new_source_id,
            public.pc_resolve_job_object_id_v4(p_job_id,s.payload->>'target_type',s.payload->>'target_id') as new_target_id
        from public.pc_staged_records s
        where s.ingestion_job_id=p_job_id
          and s.target_table='pc_relationships'
          and lower(coalesce(s.review_status,'pending')) <> 'applied'
    ), u as (
        update public.pc_staged_records s
           set payload = jsonb_set(
                         jsonb_set(coalesce(s.payload,'{}'::jsonb),'{source_id}',to_jsonb(x.new_source_id),true),
                         '{target_id}',to_jsonb(x.new_target_id),true
                       ),
               validation_status='pending',
               resolution_method=case
                    when x.new_source_id is distinct from (s.payload->>'source_id')
                      or x.new_target_id is distinct from (s.payload->>'target_id')
                    then 'job_endpoint_remap_v4'
                    else s.resolution_method
               end
          from x
         where s.staged_record_id=x.staged_record_id
           and (
                x.new_source_id is distinct from (s.payload->>'source_id')
                or x.new_target_id is distinct from (s.payload->>'target_id')
           )
        returning 1
    )
    select count(*) into v_relationships_rewritten from u;

    -- E) Finalize canonical relationships that already exist by relationship_id.
    with u as (
        update public.pc_staged_records s
           set review_status='applied',
               validation_status='reviewed',
               resolution_status='ALREADY_EXISTS',
               resolution_method='canonical_relationship_exists_v4',
               resolution_confidence=1.0,
               candidate_count=1
         where s.ingestion_job_id=p_job_id
           and s.target_table='pc_relationships'
           and lower(coalesce(s.review_status,'pending')) <> 'applied'
           and coalesce(s.payload->>'relationship_id','')<>''
           and exists (
               select 1 from public.pc_relationships r
               where r.relationship_id=s.payload->>'relationship_id'
           )
        returning 1
    )
    select count(*) into v_relationships_existing from u;

    -- F) Promote generic relationships to READY when both remapped endpoints exist.
    with u as (
        update public.pc_staged_records s
           set resolution_status='READY',
               resolution_method='canonical_endpoints_exist_v4',
               resolution_confidence=1.0,
               candidate_count=1,
               validation_status='pending',
               review_status=case
                    when lower(coalesce(s.review_status,'')) in ('rejected','needs_changes') then s.review_status
                    else 'pending'
               end
         where s.ingestion_job_id=p_job_id
           and s.target_table='pc_relationships'
           and lower(coalesce(s.review_status,'pending')) <> 'applied'
           and coalesce(s.payload->>'relationship_id','')<>''
           and coalesce(s.payload->>'source_type','')<>''
           and coalesce(s.payload->>'source_id','')<>''
           and coalesce(s.payload->>'target_type','')<>''
           and coalesce(s.payload->>'target_id','')<>''
           and coalesce(s.payload->>'relationship_type','')<>''
           and public.pc_canonical_object_exists(s.payload->>'source_type',s.payload->>'source_id')
           and public.pc_canonical_object_exists(s.payload->>'target_type',s.payload->>'target_id')
        returning 1
    )
    select count(*) into v_relationships_ready from u;

    return jsonb_build_object(
        'job_id',p_job_id,
        'event_links_rewritten',v_event_links_rewritten,
        'event_links_existing_finalized',v_event_links_existing,
        'event_links_ready',v_event_links_ready,
        'relationships_rewritten',v_relationships_rewritten,
        'relationships_existing_finalized',v_relationships_existing,
        'relationships_ready',v_relationships_ready
    );
end;
$$;

-- Diagnostics view: exposes original logical IDs and current remapped endpoints.
create or replace view public.pc_v_dependency_endpoint_diagnostics_v4 as
select
    s.staged_record_id,
    s.ingestion_job_id,
    s.target_table,
    s.natural_key,
    s.resolution_status,
    s.review_status,
    s.resolution_method,
    case when s.target_table='pc_event_links' then s.payload->>'event_id' end as event_id,
    case when s.target_table='pc_event_links' then s.payload->>'linked_type' end as linked_type,
    case when s.target_table='pc_event_links' then s.payload->>'linked_id' end as linked_id,
    case when s.target_table='pc_relationships' then s.payload->>'source_type' end as source_type,
    case when s.target_table='pc_relationships' then s.payload->>'source_id' end as source_id,
    case when s.target_table='pc_relationships' then s.payload->>'target_type' end as target_type,
    case when s.target_table='pc_relationships' then s.payload->>'target_id' end as target_id,
    s.payload
from public.pc_staged_records s
where s.target_table in ('pc_event_links','pc_relationships');

commit;
