-- Power & Corridors
-- 062_terminal_industrial_relationship_graph.sql
-- Extends the terminal relationship read model with deterministic strategic-industry
-- edges already supported by canonical specialist tables.
--
-- This does NOT infer ownership/control. It only materialises relationships explicitly
-- present through foreign keys in the specialist model.

begin;

create or replace function public.pc_refresh_terminal_industrial_links()
returns jsonb
language plpgsql
security definer
set search_path=public
as $$
declare
  inserted_count bigint := 0;
begin
  if to_regclass('public.pc_terminal_link_index') is null then
    raise exception 'pc_terminal_link_index is missing; run 059_terminal_cross_domain_read_model.sql first';
  end if;

  -- Remove only the families owned by this extension so the refresh is repeatable.
  delete from public.pc_terminal_link_index
   where relation_family in (
     'shipbuilding_production',
     'shipyard_capacity',
     'programme_milestone',
     'company_milestone',
     'security_operation_lead',
     'defence_organisation'
   );

  -- Builder entity -> shipyard asset, and programme -> production site.
  if to_regclass('public.pc_shipbuilding_production_tasks') is not null then
    execute $q$
      insert into public.pc_terminal_link_index
      (link_key,source_type,source_id,target_type,target_id,relation_type,relation_family,
       source_table,source_record_id,event_id,confidence,evidence_url,metadata)
      select
        md5(concat_ws('|','pc_shipbuilding_production_tasks',j->>'production_task_id',
                      'builder',j->>'builder_entity_id','shipyard',j->>'shipyard_asset_id')),
        'entity',j->>'builder_entity_id',
        'asset',j->>'shipyard_asset_id',
        coalesce(nullif(j->>'task_type',''),'builder_at'),
        'shipbuilding_production',
        'pc_shipbuilding_production_tasks',
        j->>'production_task_id',
        null,
        j->>'verification_status',
        j->>'source_url',
        j
      from public.pc_shipbuilding_production_tasks t
      cross join lateral to_jsonb(t) j
      where nullif(j->>'builder_entity_id','') is not null
        and nullif(j->>'shipyard_asset_id','') is not null
      on conflict (link_key) do nothing
    $q$;

    execute $q$
      insert into public.pc_terminal_link_index
      (link_key,source_type,source_id,target_type,target_id,relation_type,relation_family,
       source_table,source_record_id,event_id,confidence,evidence_url,metadata)
      select
        md5(concat_ws('|','pc_shipbuilding_production_tasks',j->>'production_task_id',
                      'programme',j->>'defence_programme_id','shipyard',j->>'shipyard_asset_id')),
        'programme',j->>'defence_programme_id',
        'asset',j->>'shipyard_asset_id',
        coalesce(nullif(j->>'task_type',''),'production_at'),
        'shipbuilding_production',
        'pc_shipbuilding_production_tasks',
        j->>'production_task_id',
        null,
        j->>'verification_status',
        j->>'source_url',
        j
      from public.pc_shipbuilding_production_tasks t
      cross join lateral to_jsonb(t) j
      where nullif(j->>'defence_programme_id','') is not null
        and nullif(j->>'shipyard_asset_id','') is not null
      on conflict (link_key) do nothing
    $q$;
  end if;

  -- Explicit shipyard operator -> shipyard asset capacity relationship.
  if to_regclass('public.pc_shipyard_capacity_history') is not null then
    execute $q$
      insert into public.pc_terminal_link_index
      (link_key,source_type,source_id,target_type,target_id,relation_type,relation_family,
       source_table,source_record_id,event_id,confidence,evidence_url,metadata)
      select
        md5(concat_ws('|','pc_shipyard_capacity_history',j->>'shipyard_capacity_history_id',
                      j->>'operator_entity_id',j->>'shipyard_asset_id')),
        'entity',j->>'operator_entity_id',
        'asset',j->>'shipyard_asset_id',
        'operates_shipyard',
        'shipyard_capacity',
        'pc_shipyard_capacity_history',
        j->>'shipyard_capacity_history_id',
        null,
        j->>'verification_status',
        j->>'source_url',
        j
      from public.pc_shipyard_capacity_history t
      cross join lateral to_jsonb(t) j
      where nullif(j->>'operator_entity_id','') is not null
        and nullif(j->>'shipyard_asset_id','') is not null
      on conflict (link_key) do nothing
    $q$;
  end if;

  -- Programme milestones -> canonical event when the milestone is event-backed.
  if to_regclass('public.pc_defence_programme_milestones') is not null then
    execute $q$
      insert into public.pc_terminal_link_index
      (link_key,source_type,source_id,target_type,target_id,relation_type,relation_family,
       source_table,source_record_id,event_id,confidence,evidence_url,metadata)
      select
        md5(concat_ws('|','pc_defence_programme_milestones',j->>'defence_milestone_id',
                      j->>'defence_programme_id',j->>'event_id')),
        'programme',j->>'defence_programme_id',
        'event',j->>'event_id',
        coalesce(nullif(j->>'milestone_type',''),'milestone'),
        'programme_milestone',
        'pc_defence_programme_milestones',
        j->>'defence_milestone_id',
        j->>'event_id',
        j->>'verification_status',
        j->>'source_url',
        j
      from public.pc_defence_programme_milestones t
      cross join lateral to_jsonb(t) j
      where nullif(j->>'defence_programme_id','') is not null
        and nullif(j->>'event_id','') is not null
      on conflict (link_key) do nothing
    $q$;
  end if;

  -- Company milestones -> events/assets. These are explicit FKs, not text matches.
  if to_regclass('public.pc_company_milestones') is not null then
    execute $q$
      insert into public.pc_terminal_link_index
      (link_key,source_type,source_id,target_type,target_id,relation_type,relation_family,
       source_table,source_record_id,event_id,confidence,evidence_url,metadata)
      select
        md5(concat_ws('|','pc_company_milestones',j->>'company_milestone_id',
                      j->>'entity_id','event',j->>'event_id')),
        'entity',j->>'entity_id',
        'event',j->>'event_id',
        coalesce(nullif(j->>'milestone_type',''),'milestone'),
        'company_milestone',
        'pc_company_milestones',
        j->>'company_milestone_id',
        j->>'event_id',
        j->>'milestone_status',
        j->>'source_url',
        j
      from public.pc_company_milestones t
      cross join lateral to_jsonb(t) j
      where nullif(j->>'entity_id','') is not null
        and nullif(j->>'event_id','') is not null
      on conflict (link_key) do nothing
    $q$;

    execute $q$
      insert into public.pc_terminal_link_index
      (link_key,source_type,source_id,target_type,target_id,relation_type,relation_family,
       source_table,source_record_id,event_id,confidence,evidence_url,metadata)
      select
        md5(concat_ws('|','pc_company_milestones',j->>'company_milestone_id',
                      j->>'entity_id','asset',j->>'related_asset_id')),
        'entity',j->>'entity_id',
        'asset',j->>'related_asset_id',
        coalesce(nullif(j->>'milestone_type',''),'related_asset'),
        'company_milestone',
        'pc_company_milestones',
        j->>'company_milestone_id',
        j->>'event_id',
        j->>'milestone_status',
        j->>'source_url',
        j
      from public.pc_company_milestones t
      cross join lateral to_jsonb(t) j
      where nullif(j->>'entity_id','') is not null
        and nullif(j->>'related_asset_id','') is not null
      on conflict (link_key) do nothing
    $q$;
  end if;

  -- Security operation lead entity.
  if to_regclass('public.pc_security_operations') is not null then
    execute $q$
      insert into public.pc_terminal_link_index
      (link_key,source_type,source_id,target_type,target_id,relation_type,relation_family,
       source_table,source_record_id,event_id,confidence,evidence_url,metadata)
      select
        md5(concat_ws('|','pc_security_operations',j->>'security_operation_id',
                      'lead',j->>'lead_entity_id')),
        'security_operation',j->>'security_operation_id',
        'entity',j->>'lead_entity_id',
        'lead_entity',
        'security_operation_lead',
        'pc_security_operations',
        j->>'security_operation_id',
        null,
        j->>'verification_status',
        j->>'source_url',
        j
      from public.pc_security_operations t
      cross join lateral to_jsonb(t) j
      where nullif(j->>'security_operation_id','') is not null
        and nullif(j->>'lead_entity_id','') is not null
      on conflict (link_key) do nothing
    $q$;
  end if;

  -- Parent relationships for defence/coast-guard organisations.
  if to_regclass('public.pc_defence_organisations') is not null then
    execute $q$
      insert into public.pc_terminal_link_index
      (link_key,source_type,source_id,target_type,target_id,relation_type,relation_family,
       source_table,source_record_id,event_id,confidence,evidence_url,metadata)
      select
        md5(concat_ws('|','pc_defence_organisations',j->>'entity_id','parent',j->>'parent_entity_id')),
        'entity',j->>'entity_id',
        'entity',j->>'parent_entity_id',
        'part_of',
        'defence_organisation',
        'pc_defence_organisations',
        j->>'entity_id',
        null,
        j->>'verification_status',
        j->>'source_url',
        j
      from public.pc_defence_organisations t
      cross join lateral to_jsonb(t) j
      where nullif(j->>'entity_id','') is not null
        and nullif(j->>'parent_entity_id','') is not null
      on conflict (link_key) do nothing
    $q$;
  end if;

  select count(*) into inserted_count
  from public.pc_terminal_link_index
  where relation_family in (
    'shipbuilding_production','shipyard_capacity','programme_milestone',
    'company_milestone','security_operation_lead','defence_organisation'
  );

  return jsonb_build_object(
    'status','ok',
    'industrial_links',inserted_count,
    'refreshed_at',now()
  );
end;
$$;

grant execute on function public.pc_refresh_terminal_industrial_links() to service_role;

-- Build the complete read graph now. The normal 059 refresh runs first because it
-- truncates the terminal index; this extension must run second.
select public.pc_refresh_terminal_indexes();
select public.pc_refresh_terminal_industrial_links();

commit;
