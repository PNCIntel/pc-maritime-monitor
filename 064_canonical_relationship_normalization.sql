-- Power & Corridors
-- 064_canonical_relationship_normalization.sql
-- Deterministically promotes explicit foreign-key relationships into pc_relationships.
--
-- SAFE SCOPE:
--   * No fuzzy/name matching
--   * No canonical merges
--   * No deletions
--   * No inferred ownership/control
--   * Only relationships already explicit in live canonical/specialist tables
--
-- Purpose:
--   Ensure the generic graph reflects relationships already stored elsewhere in the model,
--   so Trade / Intelligence / Sanctions / Strategic Industries see the same connected object.

begin;

create or replace function public.pc_normalize_canonical_relationships()
returns jsonb
language plpgsql
security definer
set search_path=public
as $$
declare
    n_assets bigint:=0;
    n_mobile bigint:=0;
    n_programmes bigint:=0;
    n_production bigint:=0;
    n_capacity bigint:=0;
    n_operations bigint:=0;
    n_milestones bigint:=0;
    n_added bigint:=0;
begin

    -- -----------------------------------------------------------------------
    -- Fixed assets: explicit owner/operator foreign keys
    -- -----------------------------------------------------------------------
    insert into public.pc_relationships(
        relationship_id,source_type,source_id,relationship_type,target_type,target_id,
        confidence,record_status,notes,metadata
    )
    select
        'REL_NORM_'||upper(substr(md5(concat_ws('|','asset_owner',a.owner_entity_id::text,a.asset_id::text)),1,24)),
        'entity',a.owner_entity_id::text,'owns','asset',a.asset_id::text,
        '1.0','verified',
        'Normalized from pc_assets.owner_entity_id',
        jsonb_build_object('normalized_from','pc_assets.owner_entity_id','normalizer','064')
    from public.pc_assets a
    where a.owner_entity_id is not null
      and not exists (
        select 1 from public.pc_relationships r
        where lower(coalesce(r.source_type,''))='entity'
          and r.source_id::text=a.owner_entity_id::text
          and lower(coalesce(r.target_type,''))='asset'
          and r.target_id::text=a.asset_id::text
          and lower(coalesce(r.relationship_type,'')) in ('owns','owner','owned_by')
      )
    on conflict (relationship_id) do nothing;
    get diagnostics n_assets=row_count;

    insert into public.pc_relationships(
        relationship_id,source_type,source_id,relationship_type,target_type,target_id,
        confidence,record_status,notes,metadata
    )
    select
        'REL_NORM_'||upper(substr(md5(concat_ws('|','asset_operator',a.operator_entity_id::text,a.asset_id::text)),1,24)),
        'entity',a.operator_entity_id::text,'operates','asset',a.asset_id::text,
        '1.0','verified',
        'Normalized from pc_assets.operator_entity_id',
        jsonb_build_object('normalized_from','pc_assets.operator_entity_id','normalizer','064')
    from public.pc_assets a
    where a.operator_entity_id is not null
      and not exists (
        select 1 from public.pc_relationships r
        where lower(coalesce(r.source_type,''))='entity'
          and r.source_id::text=a.operator_entity_id::text
          and lower(coalesce(r.target_type,''))='asset'
          and r.target_id::text=a.asset_id::text
          and lower(coalesce(r.relationship_type,'')) in ('operates','operator','operated_by')
      )
    on conflict (relationship_id) do nothing;
    get diagnostics n_added=row_count;
    n_assets:=n_assets+n_added;

    -- -----------------------------------------------------------------------
    -- Mobile assets: explicit owner/operator/manager foreign keys
    -- -----------------------------------------------------------------------
    insert into public.pc_relationships(
        relationship_id,source_type,source_id,relationship_type,target_type,target_id,
        confidence,record_status,notes,metadata
    )
    select
        'REL_NORM_'||upper(substr(md5(concat_ws('|','mobile_owner',m.owner_entity_id::text,m.mobile_asset_id::text)),1,24)),
        'entity',m.owner_entity_id::text,'owns','mobile_asset',m.mobile_asset_id::text,
        '1.0','verified',
        'Normalized from pc_mobile_assets.owner_entity_id',
        jsonb_build_object('normalized_from','pc_mobile_assets.owner_entity_id','normalizer','064')
    from public.pc_mobile_assets m
    where m.owner_entity_id is not null
      and not exists (
        select 1 from public.pc_relationships r
        where lower(coalesce(r.source_type,''))='entity'
          and r.source_id::text=m.owner_entity_id::text
          and lower(coalesce(r.target_type,'')) in ('mobile_asset','vessel')
          and r.target_id::text=m.mobile_asset_id::text
          and lower(coalesce(r.relationship_type,'')) in ('owns','owner','owned_by')
      )
    on conflict (relationship_id) do nothing;
    get diagnostics n_mobile=row_count;

    insert into public.pc_relationships(
        relationship_id,source_type,source_id,relationship_type,target_type,target_id,
        confidence,record_status,notes,metadata
    )
    select
        'REL_NORM_'||upper(substr(md5(concat_ws('|','mobile_operator',m.operator_entity_id::text,m.mobile_asset_id::text)),1,24)),
        'entity',m.operator_entity_id::text,'operates','mobile_asset',m.mobile_asset_id::text,
        '1.0','verified',
        'Normalized from pc_mobile_assets.operator_entity_id',
        jsonb_build_object('normalized_from','pc_mobile_assets.operator_entity_id','normalizer','064')
    from public.pc_mobile_assets m
    where m.operator_entity_id is not null
      and not exists (
        select 1 from public.pc_relationships r
        where lower(coalesce(r.source_type,''))='entity'
          and r.source_id::text=m.operator_entity_id::text
          and lower(coalesce(r.target_type,'')) in ('mobile_asset','vessel')
          and r.target_id::text=m.mobile_asset_id::text
          and lower(coalesce(r.relationship_type,'')) in ('operates','operator','operated_by')
      )
    on conflict (relationship_id) do nothing;
    get diagnostics n_added=row_count;
    n_mobile:=n_mobile+n_added;

    if exists (
      select 1 from information_schema.columns
      where table_schema='public' and table_name='pc_mobile_assets' and column_name='manager_entity_id'
    ) then
      execute $q$
        insert into public.pc_relationships(
            relationship_id,source_type,source_id,relationship_type,target_type,target_id,
            confidence,record_status,notes,metadata
        )
        select
            'REL_NORM_'||upper(substr(md5(concat_ws('|','mobile_manager',m.manager_entity_id::text,m.mobile_asset_id::text)),1,24)),
            'entity',m.manager_entity_id::text,'manages','mobile_asset',m.mobile_asset_id::text,
            '1.0','verified',
            'Normalized from pc_mobile_assets.manager_entity_id',
            jsonb_build_object('normalized_from','pc_mobile_assets.manager_entity_id','normalizer','064')
        from public.pc_mobile_assets m
        where m.manager_entity_id is not null
          and not exists (
            select 1 from public.pc_relationships r
            where lower(coalesce(r.source_type,''))='entity'
              and r.source_id::text=m.manager_entity_id::text
              and lower(coalesce(r.target_type,'')) in ('mobile_asset','vessel')
              and r.target_id::text=m.mobile_asset_id::text
              and lower(coalesce(r.relationship_type,'')) in ('manages','manager','managed_by','ism_manager')
          )
        on conflict (relationship_id) do nothing
      $q$;
      get diagnostics n_added=row_count;
    n_mobile:=n_mobile+n_added;
    end if;

    -- -----------------------------------------------------------------------
    -- Defence programmes
    -- -----------------------------------------------------------------------
    if to_regclass('public.pc_defence_programmes') is not null then
      insert into public.pc_relationships(
          relationship_id,source_type,source_id,relationship_type,target_type,target_id,
          confidence,record_status,evidence_source_id,notes,metadata
      )
      select
          'REL_NORM_'||upper(substr(md5(concat_ws('|','programme_lead',p.lead_contractor_entity_id::text,p.defence_programme_id::text)),1,24)),
          'entity',p.lead_contractor_entity_id::text,'lead_contractor','programme',p.defence_programme_id::text,
          coalesce(p.verification_status,'1.0'),'verified',p.source_id,
          'Normalized from pc_defence_programmes.lead_contractor_entity_id',
          jsonb_build_object('normalized_from','pc_defence_programmes.lead_contractor_entity_id','normalizer','064')
      from public.pc_defence_programmes p
      where p.lead_contractor_entity_id is not null
        and not exists (
          select 1 from public.pc_relationships r
          where lower(coalesce(r.source_type,''))='entity'
            and r.source_id::text=p.lead_contractor_entity_id::text
            and lower(coalesce(r.target_type,''))='programme'
            and r.target_id::text=p.defence_programme_id::text
        )
      on conflict (relationship_id) do nothing;
      get diagnostics n_programmes=row_count;

      insert into public.pc_relationships(
          relationship_id,source_type,source_id,relationship_type,target_type,target_id,
          confidence,record_status,evidence_source_id,notes,metadata
      )
      select
          'REL_NORM_'||upper(substr(md5(concat_ws('|','programme_customer',p.customer_entity_id::text,p.defence_programme_id::text)),1,24)),
          'entity',p.customer_entity_id::text,'customer','programme',p.defence_programme_id::text,
          coalesce(p.verification_status,'1.0'),'verified',p.source_id,
          'Normalized from pc_defence_programmes.customer_entity_id',
          jsonb_build_object('normalized_from','pc_defence_programmes.customer_entity_id','normalizer','064')
      from public.pc_defence_programmes p
      where p.customer_entity_id is not null
        and not exists (
          select 1 from public.pc_relationships r
          where lower(coalesce(r.source_type,''))='entity'
            and r.source_id::text=p.customer_entity_id::text
            and lower(coalesce(r.target_type,''))='programme'
            and r.target_id::text=p.defence_programme_id::text
        )
      on conflict (relationship_id) do nothing;
      get diagnostics n_added=row_count;
      n_programmes:=n_programmes+n_added;
    end if;

    if to_regclass('public.pc_defence_programme_participants') is not null then
      insert into public.pc_relationships(
          relationship_id,source_type,source_id,relationship_type,target_type,target_id,
          confidence,record_status,evidence_source_id,notes,metadata
      )
      select
          'REL_NORM_'||upper(substr(md5(concat_ws('|','programme_participant',pp.entity_id::text,pp.defence_programme_id::text,coalesce(pp.participant_role,'participant'))),1,24)),
          'entity',pp.entity_id::text,coalesce(nullif(pp.participant_role,''),'participant'),
          'programme',pp.defence_programme_id::text,
          coalesce(pp.verification_status,'1.0'),'verified',pp.source_id,
          'Normalized from pc_defence_programme_participants',
          jsonb_build_object('normalized_from','pc_defence_programme_participants','normalizer','064')
      from public.pc_defence_programme_participants pp
      where pp.entity_id is not null
        and pp.defence_programme_id is not null
        and not exists (
          select 1 from public.pc_relationships r
          where lower(coalesce(r.source_type,''))='entity'
            and r.source_id::text=pp.entity_id::text
            and lower(coalesce(r.target_type,''))='programme'
            and r.target_id::text=pp.defence_programme_id::text
        )
      on conflict (relationship_id) do nothing;
      get diagnostics n_added=row_count;
      n_programmes:=n_programmes+n_added;
    end if;

    -- -----------------------------------------------------------------------
    -- Shipbuilding production + capacity
    -- -----------------------------------------------------------------------
    if to_regclass('public.pc_shipbuilding_production_tasks') is not null then
      insert into public.pc_relationships(
          relationship_id,source_type,source_id,relationship_type,target_type,target_id,
          confidence,record_status,evidence_source_id,notes,metadata
      )
      select
          'REL_NORM_'||upper(substr(md5(concat_ws('|','production_builder',t.builder_entity_id::text,t.shipyard_asset_id::text,coalesce(t.task_type,'builder_at'))),1,24)),
          'entity',t.builder_entity_id::text,coalesce(nullif(t.task_type,''),'builder_at'),
          'asset',t.shipyard_asset_id::text,
          coalesce(t.verification_status,'1.0'),'verified',t.source_id,
          'Normalized from pc_shipbuilding_production_tasks',
          jsonb_build_object(
              'normalized_from','pc_shipbuilding_production_tasks',
              'production_task_id',t.production_task_id,
              'defence_programme_id',t.defence_programme_id,
              'normalizer','064'
          )
      from public.pc_shipbuilding_production_tasks t
      where t.builder_entity_id is not null
        and t.shipyard_asset_id is not null
        and not exists (
          select 1 from public.pc_relationships r
          where lower(coalesce(r.source_type,''))='entity'
            and r.source_id::text=t.builder_entity_id::text
            and lower(coalesce(r.target_type,''))='asset'
            and r.target_id::text=t.shipyard_asset_id::text
        )
      on conflict (relationship_id) do nothing;
      get diagnostics n_production=row_count;
    end if;

    if to_regclass('public.pc_shipyard_capacity_history') is not null then
      insert into public.pc_relationships(
          relationship_id,source_type,source_id,relationship_type,target_type,target_id,
          confidence,record_status,evidence_source_id,notes,metadata
      )
      select
          'REL_NORM_'||upper(substr(md5(concat_ws('|','capacity_operator',h.operator_entity_id::text,h.shipyard_asset_id::text)),1,24)),
          'entity',h.operator_entity_id::text,'operates_shipyard','asset',h.shipyard_asset_id::text,
          coalesce(h.verification_status,'1.0'),'verified',h.source_id,
          'Normalized from pc_shipyard_capacity_history',
          jsonb_build_object('normalized_from','pc_shipyard_capacity_history','normalizer','064')
      from public.pc_shipyard_capacity_history h
      where h.operator_entity_id is not null
        and h.shipyard_asset_id is not null
        and not exists (
          select 1 from public.pc_relationships r
          where lower(coalesce(r.source_type,''))='entity'
            and r.source_id::text=h.operator_entity_id::text
            and lower(coalesce(r.target_type,''))='asset'
            and r.target_id::text=h.shipyard_asset_id::text
        )
      on conflict (relationship_id) do nothing;
      get diagnostics n_capacity=row_count;
    end if;

    -- -----------------------------------------------------------------------
    -- Security operations
    -- -----------------------------------------------------------------------
    if to_regclass('public.pc_security_operations') is not null then
      insert into public.pc_relationships(
          relationship_id,source_type,source_id,relationship_type,target_type,target_id,
          confidence,record_status,evidence_source_id,notes,metadata
      )
      select
          'REL_NORM_'||upper(substr(md5(concat_ws('|','security_lead',o.lead_entity_id::text,o.security_operation_id::text)),1,24)),
          'entity',o.lead_entity_id::text,'leads','security_operation',o.security_operation_id::text,
          coalesce(o.verification_status,'1.0'),'verified',o.source_id,
          'Normalized from pc_security_operations.lead_entity_id',
          jsonb_build_object('normalized_from','pc_security_operations.lead_entity_id','normalizer','064')
      from public.pc_security_operations o
      where o.lead_entity_id is not null
        and not exists (
          select 1 from public.pc_relationships r
          where lower(coalesce(r.source_type,''))='entity'
            and r.source_id::text=o.lead_entity_id::text
            and lower(coalesce(r.target_type,''))='security_operation'
            and r.target_id::text=o.security_operation_id::text
        )
      on conflict (relationship_id) do nothing;
      get diagnostics n_operations=row_count;
    end if;

    if to_regclass('public.pc_security_operation_participants') is not null then
      insert into public.pc_relationships(
          relationship_id,source_type,source_id,relationship_type,target_type,target_id,
          confidence,record_status,evidence_source_id,notes,metadata
      )
      select
          'REL_NORM_'||upper(substr(md5(concat_ws('|','security_participant',p.entity_id::text,p.security_operation_id::text,coalesce(p.participant_role,'participant'))),1,24)),
          'entity',p.entity_id::text,coalesce(nullif(p.participant_role,''),'participant'),
          'security_operation',p.security_operation_id::text,
          coalesce(p.verification_status,'1.0'),'verified',p.source_id,
          'Normalized from pc_security_operation_participants',
          jsonb_build_object('normalized_from','pc_security_operation_participants','normalizer','064')
      from public.pc_security_operation_participants p
      where p.entity_id is not null
        and p.security_operation_id is not null
        and not exists (
          select 1 from public.pc_relationships r
          where lower(coalesce(r.source_type,''))='entity'
            and r.source_id::text=p.entity_id::text
            and lower(coalesce(r.target_type,''))='security_operation'
            and r.target_id::text=p.security_operation_id::text
        )
      on conflict (relationship_id) do nothing;
      get diagnostics n_added=row_count;
      n_operations:=n_operations+n_added;
    end if;

    -- -----------------------------------------------------------------------
    -- Company milestones: explicit event/asset/entity refs
    -- -----------------------------------------------------------------------
    if to_regclass('public.pc_company_milestones') is not null then
      insert into public.pc_relationships(
          relationship_id,source_type,source_id,relationship_type,target_type,target_id,
          confidence,record_status,evidence_source_id,notes,metadata
      )
      select
          'REL_NORM_'||upper(substr(md5(concat_ws('|','milestone_asset',m.entity_id::text,m.related_asset_id::text,coalesce(m.milestone_type,'milestone'))),1,24)),
          'entity',m.entity_id::text,coalesce(nullif(m.milestone_type,''),'milestone'),
          'asset',m.related_asset_id::text,
          coalesce(m.milestone_status,'1.0'),'verified',m.source_id,
          'Normalized from pc_company_milestones.related_asset_id',
          jsonb_build_object('normalized_from','pc_company_milestones.related_asset_id','normalizer','064')
      from public.pc_company_milestones m
      where m.entity_id is not null and m.related_asset_id is not null
        and not exists (
          select 1 from public.pc_relationships r
          where lower(coalesce(r.source_type,''))='entity'
            and r.source_id::text=m.entity_id::text
            and lower(coalesce(r.target_type,''))='asset'
            and r.target_id::text=m.related_asset_id::text
        )
      on conflict (relationship_id) do nothing;
      get diagnostics n_milestones=row_count;

      insert into public.pc_relationships(
          relationship_id,source_type,source_id,relationship_type,target_type,target_id,
          confidence,record_status,evidence_source_id,notes,metadata
      )
      select
          'REL_NORM_'||upper(substr(md5(concat_ws('|','milestone_entity',m.entity_id::text,m.related_entity_id::text,coalesce(m.milestone_type,'milestone'))),1,24)),
          'entity',m.entity_id::text,coalesce(nullif(m.milestone_type,''),'related_to'),
          'entity',m.related_entity_id::text,
          coalesce(m.milestone_status,'1.0'),'verified',m.source_id,
          'Normalized from pc_company_milestones.related_entity_id',
          jsonb_build_object('normalized_from','pc_company_milestones.related_entity_id','normalizer','064')
      from public.pc_company_milestones m
      where m.entity_id is not null and m.related_entity_id is not null
        and not exists (
          select 1 from public.pc_relationships r
          where lower(coalesce(r.source_type,''))='entity'
            and r.source_id::text=m.entity_id::text
            and lower(coalesce(r.target_type,''))='entity'
            and r.target_id::text=m.related_entity_id::text
        )
      on conflict (relationship_id) do nothing;
      get diagnostics n_added=row_count;
      n_milestones:=n_milestones+n_added;
    end if;

    return jsonb_build_object(
      'status','ok',
      'asset_relationships_added',n_assets,
      'mobile_relationships_added',n_mobile,
      'programme_relationships_added',n_programmes,
      'production_relationships_added',n_production,
      'shipyard_capacity_relationships_added',n_capacity,
      'security_operation_relationships_added',n_operations,
      'milestone_relationships_added',n_milestones,
      'completed_at',now()
    );
end;
$$;

grant execute on function public.pc_normalize_canonical_relationships() to service_role,postgres;

-- Run once now.
select public.pc_normalize_canonical_relationships();

-- Rebuild terminal read indexes after graph normalization.
select public.pc_refresh_terminal_indexes();
do $$
begin
  if to_regprocedure('public.pc_refresh_terminal_industrial_links()') is not null then
    perform public.pc_refresh_terminal_industrial_links();
  end if;
end $$;

commit;

-- After running:
-- select * from public.pc_v_model_audit_summary;
-- select * from public.pc_v_model_relationship_gaps order by source_name,issue_type;
