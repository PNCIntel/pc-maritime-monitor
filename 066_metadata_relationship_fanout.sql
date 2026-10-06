-- Power & Corridors
-- 066_metadata_relationship_fanout.sql
-- Deterministically promotes structured research_attributes from canonical mobile assets
-- into explicit graph relationships when the referenced canonical object already exists.
--
-- Safety:
--   * exact normalized match only
--   * requires exactly one canonical candidate
--   * no fuzzy matching
--   * no canonical object creation
--   * no merges/deletes
--   * provenance retained in relationship metadata

begin;

create or replace function public.pc_norm_identity_text(p_text text)
returns text
language sql
immutable
as $$
  select trim(regexp_replace(lower(regexp_replace(coalesce(p_text,''),'[^a-zA-Z0-9]+',' ','g')),'\s+',' ','g'));
$$;

create or replace function public.pc_fanout_mobile_asset_metadata_relationships(p_mobile_asset_id text default null)
returns jsonb
language plpgsql
security definer
set search_path=public
as $$
declare
  n_builder bigint:=0;
  n_operator bigint:=0;
  n_owner bigint:=0;
  n_manager bigint:=0;
  n_programme bigint:=0;
  n_shipyard bigint:=0;
begin

  -- BUILDER -> built -> mobile asset
  with candidates as (
    select
      m.mobile_asset_id::text mobile_asset_id,
      m.name mobile_name,
      m.metadata,
      m.metadata->'research_attributes'->>'builder' builder_name,
      (
        select e.entity_id::text
        from public.pc_entities e
        where public.pc_norm_identity_text(e.name) =
              public.pc_norm_identity_text(m.metadata->'research_attributes'->>'builder')
        and (
          select count(*)
          from public.pc_entities e2
          where public.pc_norm_identity_text(e2.name)=public.pc_norm_identity_text(e.name)
        )=1
        limit 1
      ) entity_id
    from public.pc_mobile_assets m
    where (p_mobile_asset_id is null or m.mobile_asset_id::text=p_mobile_asset_id)
      and nullif(m.metadata->'research_attributes'->>'builder','') is not null
  )
  insert into public.pc_relationships(
    relationship_id,source_type,source_id,relationship_type,target_type,target_id,
    confidence,record_status,notes,metadata
  )
  select
    'REL_META_'||upper(substr(md5(concat_ws('|','builder',c.entity_id,c.mobile_asset_id)),1,24)),
    'entity',c.entity_id,'built','mobile_asset',c.mobile_asset_id,
    '1.0','verified',
    'Promoted from pc_mobile_assets.metadata.research_attributes.builder',
    jsonb_build_object(
      'normalized_from','pc_mobile_assets.metadata.research_attributes.builder',
      'source_value',c.builder_name,
      'fanout','066'
    )
  from candidates c
  where c.entity_id is not null
    and not exists (
      select 1 from public.pc_relationships r
      where lower(coalesce(r.source_type,''))='entity'
        and r.source_id::text=c.entity_id
        and lower(coalesce(r.target_type,'')) in ('mobile_asset','vessel')
        and r.target_id::text=c.mobile_asset_id
        and lower(coalesce(r.relationship_type,'')) in ('built','builder','built_by')
    )
  on conflict (relationship_id) do nothing;
  get diagnostics n_builder=row_count;

  -- OPERATOR -> operates -> mobile asset
  with candidates as (
    select
      m.mobile_asset_id::text mobile_asset_id,
      m.metadata->'research_attributes'->>'operator' operator_name,
      (
        select e.entity_id::text
        from public.pc_entities e
        where public.pc_norm_identity_text(e.name) =
              public.pc_norm_identity_text(m.metadata->'research_attributes'->>'operator')
        and (
          select count(*)
          from public.pc_entities e2
          where public.pc_norm_identity_text(e2.name)=public.pc_norm_identity_text(e.name)
        )=1
        limit 1
      ) entity_id
    from public.pc_mobile_assets m
    where (p_mobile_asset_id is null or m.mobile_asset_id::text=p_mobile_asset_id)
      and nullif(m.metadata->'research_attributes'->>'operator','') is not null
  )
  insert into public.pc_relationships(
    relationship_id,source_type,source_id,relationship_type,target_type,target_id,
    confidence,record_status,notes,metadata
  )
  select
    'REL_META_'||upper(substr(md5(concat_ws('|','operator',c.entity_id,c.mobile_asset_id)),1,24)),
    'entity',c.entity_id,'operates','mobile_asset',c.mobile_asset_id,
    '1.0','verified',
    'Promoted from pc_mobile_assets.metadata.research_attributes.operator',
    jsonb_build_object(
      'normalized_from','pc_mobile_assets.metadata.research_attributes.operator',
      'source_value',c.operator_name,
      'fanout','066'
    )
  from candidates c
  where c.entity_id is not null
    and not exists (
      select 1 from public.pc_relationships r
      where lower(coalesce(r.source_type,''))='entity'
        and r.source_id::text=c.entity_id
        and lower(coalesce(r.target_type,'')) in ('mobile_asset','vessel')
        and r.target_id::text=c.mobile_asset_id
        and lower(coalesce(r.relationship_type,'')) in ('operates','operator','operated_by')
    )
  on conflict (relationship_id) do nothing;
  get diagnostics n_operator=row_count;

  -- OWNER -> owns -> mobile asset
  with candidates as (
    select
      m.mobile_asset_id::text mobile_asset_id,
      m.metadata->'research_attributes'->>'owner' owner_name,
      (
        select e.entity_id::text
        from public.pc_entities e
        where public.pc_norm_identity_text(e.name) =
              public.pc_norm_identity_text(m.metadata->'research_attributes'->>'owner')
        and (
          select count(*)
          from public.pc_entities e2
          where public.pc_norm_identity_text(e2.name)=public.pc_norm_identity_text(e.name)
        )=1
        limit 1
      ) entity_id
    from public.pc_mobile_assets m
    where (p_mobile_asset_id is null or m.mobile_asset_id::text=p_mobile_asset_id)
      and nullif(m.metadata->'research_attributes'->>'owner','') is not null
  )
  insert into public.pc_relationships(
    relationship_id,source_type,source_id,relationship_type,target_type,target_id,
    confidence,record_status,notes,metadata
  )
  select
    'REL_META_'||upper(substr(md5(concat_ws('|','owner',c.entity_id,c.mobile_asset_id)),1,24)),
    'entity',c.entity_id,'owns','mobile_asset',c.mobile_asset_id,
    '1.0','verified',
    'Promoted from pc_mobile_assets.metadata.research_attributes.owner',
    jsonb_build_object(
      'normalized_from','pc_mobile_assets.metadata.research_attributes.owner',
      'source_value',c.owner_name,
      'fanout','066'
    )
  from candidates c
  where c.entity_id is not null
    and not exists (
      select 1 from public.pc_relationships r
      where lower(coalesce(r.source_type,''))='entity'
        and r.source_id::text=c.entity_id
        and lower(coalesce(r.target_type,'')) in ('mobile_asset','vessel')
        and r.target_id::text=c.mobile_asset_id
        and lower(coalesce(r.relationship_type,'')) in ('owns','owner','owned_by')
    )
  on conflict (relationship_id) do nothing;
  get diagnostics n_owner=row_count;

  -- MANAGER -> manages -> mobile asset
  with candidates as (
    select
      m.mobile_asset_id::text mobile_asset_id,
      coalesce(
        m.metadata->'research_attributes'->>'manager',
        m.metadata->'research_attributes'->>'ism_manager'
      ) manager_name,
      (
        select e.entity_id::text
        from public.pc_entities e
        where public.pc_norm_identity_text(e.name) =
              public.pc_norm_identity_text(
                coalesce(
                  m.metadata->'research_attributes'->>'manager',
                  m.metadata->'research_attributes'->>'ism_manager'
                )
              )
        and (
          select count(*)
          from public.pc_entities e2
          where public.pc_norm_identity_text(e2.name)=public.pc_norm_identity_text(e.name)
        )=1
        limit 1
      ) entity_id
    from public.pc_mobile_assets m
    where (p_mobile_asset_id is null or m.mobile_asset_id::text=p_mobile_asset_id)
      and nullif(coalesce(
        m.metadata->'research_attributes'->>'manager',
        m.metadata->'research_attributes'->>'ism_manager'
      ),'') is not null
  )
  insert into public.pc_relationships(
    relationship_id,source_type,source_id,relationship_type,target_type,target_id,
    confidence,record_status,notes,metadata
  )
  select
    'REL_META_'||upper(substr(md5(concat_ws('|','manager',c.entity_id,c.mobile_asset_id)),1,24)),
    'entity',c.entity_id,'manages','mobile_asset',c.mobile_asset_id,
    '1.0','verified',
    'Promoted from pc_mobile_assets.metadata.research_attributes manager field',
    jsonb_build_object(
      'normalized_from','pc_mobile_assets.metadata.research_attributes.manager',
      'source_value',c.manager_name,
      'fanout','066'
    )
  from candidates c
  where c.entity_id is not null
    and not exists (
      select 1 from public.pc_relationships r
      where lower(coalesce(r.source_type,''))='entity'
        and r.source_id::text=c.entity_id
        and lower(coalesce(r.target_type,'')) in ('mobile_asset','vessel')
        and r.target_id::text=c.mobile_asset_id
        and lower(coalesce(r.relationship_type,'')) in ('manages','manager','managed_by','ism_manager')
    )
  on conflict (relationship_id) do nothing;
  get diagnostics n_manager=row_count;

  -- Existing programme exact match -> mobile asset part_of_programme
  if to_regclass('public.pc_defence_programmes') is not null then
    with candidates as (
      select
        m.mobile_asset_id::text mobile_asset_id,
        m.metadata->'research_attributes'->>'programme' programme_name,
        (
          select p.defence_programme_id::text
          from public.pc_defence_programmes p
          where public.pc_norm_identity_text(p.programme_name) =
                public.pc_norm_identity_text(m.metadata->'research_attributes'->>'programme')
          and (
            select count(*)
            from public.pc_defence_programmes p2
            where public.pc_norm_identity_text(p2.programme_name)=public.pc_norm_identity_text(p.programme_name)
          )=1
          limit 1
        ) programme_id
      from public.pc_mobile_assets m
      where (p_mobile_asset_id is null or m.mobile_asset_id::text=p_mobile_asset_id)
        and nullif(m.metadata->'research_attributes'->>'programme','') is not null
    )
    insert into public.pc_relationships(
      relationship_id,source_type,source_id,relationship_type,target_type,target_id,
      confidence,record_status,notes,metadata
    )
    select
      'REL_META_'||upper(substr(md5(concat_ws('|','programme',c.mobile_asset_id,c.programme_id)),1,24)),
      'mobile_asset',c.mobile_asset_id,'part_of_programme','programme',c.programme_id,
      '1.0','verified',
      'Promoted from pc_mobile_assets.metadata.research_attributes.programme',
      jsonb_build_object(
        'normalized_from','pc_mobile_assets.metadata.research_attributes.programme',
        'source_value',c.programme_name,
        'fanout','066'
      )
    from candidates c
    where c.programme_id is not null
      and not exists (
        select 1 from public.pc_relationships r
        where lower(coalesce(r.source_type,'')) in ('mobile_asset','vessel')
          and r.source_id::text=c.mobile_asset_id
          and lower(coalesce(r.target_type,''))='programme'
          and r.target_id::text=c.programme_id
      )
    on conflict (relationship_id) do nothing;
    get diagnostics n_programme=row_count;
  end if;

  -- Existing shipyard asset exact match -> mobile asset built_at
  with candidates as (
    select
      m.mobile_asset_id::text mobile_asset_id,
      m.metadata->'research_attributes'->>'shipyard' shipyard_name,
      (
        select a.asset_id::text
        from public.pc_assets a
        where public.pc_norm_identity_text(a.name) =
              public.pc_norm_identity_text(m.metadata->'research_attributes'->>'shipyard')
          and (
            lower(coalesce(a.asset_type,'')) like '%shipyard%'
            or lower(coalesce(a.subtype,'')) like '%shipyard%'
            or lower(coalesce(a.name,'')) like '%shipyard%'
          )
        and (
          select count(*)
          from public.pc_assets a2
          where public.pc_norm_identity_text(a2.name)=public.pc_norm_identity_text(a.name)
        )=1
        limit 1
      ) shipyard_asset_id
    from public.pc_mobile_assets m
    where (p_mobile_asset_id is null or m.mobile_asset_id::text=p_mobile_asset_id)
      and nullif(m.metadata->'research_attributes'->>'shipyard','') is not null
  )
  insert into public.pc_relationships(
    relationship_id,source_type,source_id,relationship_type,target_type,target_id,
    confidence,record_status,notes,metadata
  )
  select
    'REL_META_'||upper(substr(md5(concat_ws('|','shipyard',c.mobile_asset_id,c.shipyard_asset_id)),1,24)),
    'mobile_asset',c.mobile_asset_id,'built_at','asset',c.shipyard_asset_id,
    '1.0','verified',
    'Promoted from pc_mobile_assets.metadata.research_attributes.shipyard',
    jsonb_build_object(
      'normalized_from','pc_mobile_assets.metadata.research_attributes.shipyard',
      'source_value',c.shipyard_name,
      'fanout','066'
    )
  from candidates c
  where c.shipyard_asset_id is not null
    and not exists (
      select 1 from public.pc_relationships r
      where lower(coalesce(r.source_type,'')) in ('mobile_asset','vessel')
        and r.source_id::text=c.mobile_asset_id
        and lower(coalesce(r.target_type,''))='asset'
        and r.target_id::text=c.shipyard_asset_id
        and lower(coalesce(r.relationship_type,'')) in ('built_at','built','shipyard')
    )
  on conflict (relationship_id) do nothing;
  get diagnostics n_shipyard=row_count;

  return jsonb_build_object(
    'status','ok',
    'builder_relationships_added',n_builder,
    'operator_relationships_added',n_operator,
    'owner_relationships_added',n_owner,
    'manager_relationships_added',n_manager,
    'programme_relationships_added',n_programme,
    'shipyard_relationships_added',n_shipyard,
    'completed_at',now()
  );
end;
$$;

grant execute on function public.pc_fanout_mobile_asset_metadata_relationships(text)
to service_role,postgres;

-- Backfill all existing canonical mobile assets.
select public.pc_fanout_mobile_asset_metadata_relationships(null);

-- Rebuild shared read indexes after fanout.
select public.pc_refresh_terminal_indexes();
do $$
begin
  if to_regprocedure('public.pc_refresh_terminal_industrial_links()') is not null then
    perform public.pc_refresh_terminal_industrial_links();
  end if;
end $$;

commit;

-- Validate:
-- select public.pc_model_audit_entity('COMP_IRVING');
-- select * from public.pc_v_model_audit_summary;
