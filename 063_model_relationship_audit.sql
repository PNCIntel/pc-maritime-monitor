-- Power & Corridors
-- 063_model_relationship_audit.sql
-- Live audit of canonical objects, relationship coverage and graph gaps.
--
-- Purpose:
--   Diagnose why rich entities/assets can appear empty in the applications.
--   This script is READ-ONLY apart from creating audit views/functions.
--   It does not merge, rewrite or delete canonical records.

begin;

-- ---------------------------------------------------------------------------
-- 1. Entity relationship coverage
-- ---------------------------------------------------------------------------
create or replace view public.pc_v_entity_relationship_coverage as
with base as (
    select
        e.entity_id::text as entity_id,
        e.name,
        coalesce(to_jsonb(e)->>'entity_type','') as entity_type,
        coalesce(to_jsonb(e)->>'subtype','') as subtype,
        coalesce(to_jsonb(e)->>'hq_country',to_jsonb(e)->>'country','') as country
    from public.pc_entities e
),
generic as (
    select entity_id,count(*)::bigint generic_relationships
    from (
        select source_id::text entity_id
        from public.pc_relationships
        where lower(coalesce(source_type,''))='entity'
        union all
        select target_id::text
        from public.pc_relationships
        where lower(coalesce(target_type,''))='entity'
    ) x
    group by entity_id
),
asset_roles as (
    select entity_id::text entity_id,count(*)::bigint company_asset_roles
    from public.pc_company_asset_roles
    group by entity_id::text
),
direct_fixed as (
    select entity_id,count(*)::bigint direct_fixed_asset_refs
    from (
        select owner_entity_id::text entity_id from public.pc_assets where owner_entity_id is not null
        union all
        select operator_entity_id::text from public.pc_assets where operator_entity_id is not null
    ) x group by entity_id
),
direct_mobile as (
    select entity_id,count(*)::bigint direct_mobile_asset_refs
    from (
        select owner_entity_id::text entity_id from public.pc_mobile_assets where owner_entity_id is not null
        union all
        select operator_entity_id::text from public.pc_mobile_assets where operator_entity_id is not null
        union all
        select manager_entity_id::text from public.pc_mobile_assets where manager_entity_id is not null
    ) x group by entity_id
),
events as (
    select linked_id::text entity_id,count(*)::bigint event_links
    from public.pc_event_links
    where lower(coalesce(linked_type,'')) in ('entity','company','organisation','organization')
    group by linked_id::text
),
corridors as (
    select entity_id::text entity_id,count(*)::bigint corridor_roles
    from public.pc_company_corridor_roles
    group by entity_id::text
),
portfolio as (
    select entity_id,count(*)::bigint portfolio_positions
    from (
        select holder_entity_id::text entity_id
        from public.pc_company_portfolio_positions
        where holder_entity_id is not null
        union all
        select investee_entity_id::text
        from public.pc_company_portfolio_positions
        where investee_entity_id is not null
    ) x group by entity_id
),
documents as (
    select entity_id::text entity_id,count(*)::bigint document_links
    from public.pc_document_entity_links
    group by entity_id::text
),
sanctions as (
    select entity_id::text entity_id,count(*)::bigint sanctions_records
    from public.pc_sanctions_designations
    where entity_id is not null
    group by entity_id::text
),
programmes as (
    select entity_id,count(*)::bigint defence_programme_links
    from (
        select lead_contractor_entity_id::text entity_id
        from public.pc_defence_programmes
        where lead_contractor_entity_id is not null
        union all
        select customer_entity_id::text
        from public.pc_defence_programmes
        where customer_entity_id is not null
        union all
        select entity_id::text
        from public.pc_defence_programme_participants
        where entity_id is not null
    ) x group by entity_id
),
production as (
    select builder_entity_id::text entity_id,count(*)::bigint production_links
    from public.pc_shipbuilding_production_tasks
    where builder_entity_id is not null
    group by builder_entity_id::text
),
capacity as (
    select operator_entity_id::text entity_id,count(*)::bigint shipyard_capacity_links
    from public.pc_shipyard_capacity_history
    where operator_entity_id is not null
    group by operator_entity_id::text
),
security_ops as (
    select entity_id,count(*)::bigint security_operation_links
    from (
        select lead_entity_id::text entity_id
        from public.pc_security_operations
        where lead_entity_id is not null
        union all
        select entity_id::text
        from public.pc_security_operation_participants
        where entity_id is not null
    ) x group by entity_id
)
select
    b.*,
    coalesce(g.generic_relationships,0) as generic_relationships,
    coalesce(ar.company_asset_roles,0) as company_asset_roles,
    coalesce(df.direct_fixed_asset_refs,0) as direct_fixed_asset_refs,
    coalesce(dm.direct_mobile_asset_refs,0) as direct_mobile_asset_refs,
    coalesce(ev.event_links,0) as event_links,
    coalesce(cr.corridor_roles,0) as corridor_roles,
    coalesce(pp.portfolio_positions,0) as portfolio_positions,
    coalesce(doc.document_links,0) as document_links,
    coalesce(sa.sanctions_records,0) as sanctions_records,
    coalesce(pg.defence_programme_links,0) as defence_programme_links,
    coalesce(pr.production_links,0) as production_links,
    coalesce(cp.shipyard_capacity_links,0) as shipyard_capacity_links,
    coalesce(so.security_operation_links,0) as security_operation_links,
    (
      coalesce(g.generic_relationships,0)+
      coalesce(ar.company_asset_roles,0)+
      coalesce(df.direct_fixed_asset_refs,0)+
      coalesce(dm.direct_mobile_asset_refs,0)+
      coalesce(ev.event_links,0)+
      coalesce(cr.corridor_roles,0)+
      coalesce(pp.portfolio_positions,0)+
      coalesce(doc.document_links,0)+
      coalesce(sa.sanctions_records,0)+
      coalesce(pg.defence_programme_links,0)+
      coalesce(pr.production_links,0)+
      coalesce(cp.shipyard_capacity_links,0)+
      coalesce(so.security_operation_links,0)
    )::bigint as total_known_connections,
    (
      coalesce(g.generic_relationships,0)=0
      and (
        coalesce(ar.company_asset_roles,0)+
        coalesce(df.direct_fixed_asset_refs,0)+
        coalesce(dm.direct_mobile_asset_refs,0)+
        coalesce(ev.event_links,0)+
        coalesce(cr.corridor_roles,0)+
        coalesce(pp.portfolio_positions,0)+
        coalesce(doc.document_links,0)+
        coalesce(sa.sanctions_records,0)+
        coalesce(pg.defence_programme_links,0)+
        coalesce(pr.production_links,0)+
        coalesce(cp.shipyard_capacity_links,0)+
        coalesce(so.security_operation_links,0)
      ) > 0
    ) as rich_but_missing_generic_graph
from base b
left join generic g using(entity_id)
left join asset_roles ar using(entity_id)
left join direct_fixed df using(entity_id)
left join direct_mobile dm using(entity_id)
left join events ev using(entity_id)
left join corridors cr using(entity_id)
left join portfolio pp using(entity_id)
left join documents doc using(entity_id)
left join sanctions sa using(entity_id)
left join programmes pg using(entity_id)
left join production pr using(entity_id)
left join capacity cp using(entity_id)
left join security_ops so using(entity_id);


-- ---------------------------------------------------------------------------
-- 2. Relationship gaps: facts exist in specialist/direct tables but are absent
--    from the generic canonical graph.
-- ---------------------------------------------------------------------------
create or replace view public.pc_v_model_relationship_gaps as

-- Fixed asset owner links absent from generic graph.
select
    'asset_owner_missing_generic_edge'::text as issue_type,
    'pc_assets'::text as source_table,
    'entity'::text as source_type,
    a.owner_entity_id::text as source_id,
    e.name as source_name,
    'asset'::text as target_type,
    a.asset_id::text as target_id,
    a.name as target_name,
    'owns'::text as expected_relationship,
    'Asset owner_entity_id exists but no equivalent pc_relationships edge.'::text as reason
from public.pc_assets a
left join public.pc_entities e on e.entity_id=a.owner_entity_id
where a.owner_entity_id is not null
  and not exists (
    select 1 from public.pc_relationships r
    where lower(coalesce(r.source_type,''))='entity'
      and r.source_id::text=a.owner_entity_id::text
      and lower(coalesce(r.target_type,''))='asset'
      and r.target_id::text=a.asset_id::text
      and lower(coalesce(r.relationship_type,'')) in ('owns','owner','owned_by')
  )

union all

-- Fixed asset operator links absent from generic graph.
select
    'asset_operator_missing_generic_edge',
    'pc_assets',
    'entity',
    a.operator_entity_id::text,
    e.name,
    'asset',
    a.asset_id::text,
    a.name,
    'operates',
    'Asset operator_entity_id exists but no equivalent pc_relationships edge.'
from public.pc_assets a
left join public.pc_entities e on e.entity_id=a.operator_entity_id
where a.operator_entity_id is not null
  and not exists (
    select 1 from public.pc_relationships r
    where lower(coalesce(r.source_type,''))='entity'
      and r.source_id::text=a.operator_entity_id::text
      and lower(coalesce(r.target_type,''))='asset'
      and r.target_id::text=a.asset_id::text
      and lower(coalesce(r.relationship_type,'')) in ('operates','operator','operated_by')
  )

union all

-- Mobile asset owner.
select
    'mobile_owner_missing_generic_edge',
    'pc_mobile_assets',
    'entity',
    m.owner_entity_id::text,
    e.name,
    'mobile_asset',
    m.mobile_asset_id::text,
    m.name,
    'owns',
    'Mobile asset owner_entity_id exists but no equivalent pc_relationships edge.'
from public.pc_mobile_assets m
left join public.pc_entities e on e.entity_id=m.owner_entity_id
where m.owner_entity_id is not null
  and not exists (
    select 1 from public.pc_relationships r
    where lower(coalesce(r.source_type,''))='entity'
      and r.source_id::text=m.owner_entity_id::text
      and lower(coalesce(r.target_type,'')) in ('mobile_asset','vessel')
      and r.target_id::text=m.mobile_asset_id::text
      and lower(coalesce(r.relationship_type,'')) in ('owns','owner','owned_by')
  )

union all

-- Mobile asset operator.
select
    'mobile_operator_missing_generic_edge',
    'pc_mobile_assets',
    'entity',
    m.operator_entity_id::text,
    e.name,
    'mobile_asset',
    m.mobile_asset_id::text,
    m.name,
    'operates',
    'Mobile asset operator_entity_id exists but no equivalent pc_relationships edge.'
from public.pc_mobile_assets m
left join public.pc_entities e on e.entity_id=m.operator_entity_id
where m.operator_entity_id is not null
  and not exists (
    select 1 from public.pc_relationships r
    where lower(coalesce(r.source_type,''))='entity'
      and r.source_id::text=m.operator_entity_id::text
      and lower(coalesce(r.target_type,'')) in ('mobile_asset','vessel')
      and r.target_id::text=m.mobile_asset_id::text
      and lower(coalesce(r.relationship_type,'')) in ('operates','operator','operated_by')
  )

union all

-- Programme lead contractor.
select
    'programme_lead_contractor_missing_generic_edge',
    'pc_defence_programmes',
    'entity',
    p.lead_contractor_entity_id::text,
    e.name,
    'programme',
    p.defence_programme_id::text,
    p.programme_name,
    'lead_contractor',
    'Lead contractor exists in defence programme but no generic graph edge.'
from public.pc_defence_programmes p
left join public.pc_entities e on e.entity_id=p.lead_contractor_entity_id
where p.lead_contractor_entity_id is not null
  and not exists (
    select 1 from public.pc_relationships r
    where lower(coalesce(r.source_type,''))='entity'
      and r.source_id::text=p.lead_contractor_entity_id::text
      and lower(coalesce(r.target_type,''))='programme'
      and r.target_id::text=p.defence_programme_id::text
  )

union all

-- Programme participant.
select
    'programme_participant_missing_generic_edge',
    'pc_defence_programme_participants',
    'entity',
    pp.entity_id::text,
    e.name,
    'programme',
    pp.defence_programme_id::text,
    p.programme_name,
    coalesce(pp.participant_role,'participant'),
    'Programme participant exists but no generic graph edge.'
from public.pc_defence_programme_participants pp
left join public.pc_entities e on e.entity_id=pp.entity_id
left join public.pc_defence_programmes p on p.defence_programme_id=pp.defence_programme_id
where pp.entity_id is not null
  and not exists (
    select 1 from public.pc_relationships r
    where lower(coalesce(r.source_type,''))='entity'
      and r.source_id::text=pp.entity_id::text
      and lower(coalesce(r.target_type,''))='programme'
      and r.target_id::text=pp.defence_programme_id::text
  )

union all

-- Production builder -> shipyard.
select
    'production_builder_shipyard_missing_generic_edge',
    'pc_shipbuilding_production_tasks',
    'entity',
    t.builder_entity_id::text,
    e.name,
    'asset',
    t.shipyard_asset_id::text,
    a.name,
    coalesce(t.task_type,'builder_at'),
    'Production task explicitly links builder and shipyard but generic edge is absent.'
from public.pc_shipbuilding_production_tasks t
left join public.pc_entities e on e.entity_id=t.builder_entity_id
left join public.pc_assets a on a.asset_id=t.shipyard_asset_id
where t.builder_entity_id is not null
  and t.shipyard_asset_id is not null
  and not exists (
    select 1 from public.pc_relationships r
    where lower(coalesce(r.source_type,''))='entity'
      and r.source_id::text=t.builder_entity_id::text
      and lower(coalesce(r.target_type,''))='asset'
      and r.target_id::text=t.shipyard_asset_id::text
  )

union all

-- Shipyard capacity operator.
select
    'shipyard_operator_missing_generic_edge',
    'pc_shipyard_capacity_history',
    'entity',
    h.operator_entity_id::text,
    e.name,
    'asset',
    h.shipyard_asset_id::text,
    a.name,
    'operates_shipyard',
    'Shipyard capacity record has operator but generic edge is absent.'
from public.pc_shipyard_capacity_history h
left join public.pc_entities e on e.entity_id=h.operator_entity_id
left join public.pc_assets a on a.asset_id=h.shipyard_asset_id
where h.operator_entity_id is not null
  and h.shipyard_asset_id is not null
  and not exists (
    select 1 from public.pc_relationships r
    where lower(coalesce(r.source_type,''))='entity'
      and r.source_id::text=h.operator_entity_id::text
      and lower(coalesce(r.target_type,''))='asset'
      and r.target_id::text=h.shipyard_asset_id::text
  );


-- ---------------------------------------------------------------------------
-- 3. Invalid endpoints / stale IDs
-- ---------------------------------------------------------------------------
create or replace view public.pc_v_relationship_endpoint_audit as
select
    r.relationship_id::text,
    r.source_type,
    r.source_id::text,
    r.relationship_type,
    r.target_type,
    r.target_id::text,
    case
      when lower(r.source_type)='entity'
       and not exists(select 1 from public.pc_entities e where e.entity_id::text=r.source_id::text)
        then 'missing_source_entity'
      when lower(r.source_type)='asset'
       and not exists(select 1 from public.pc_assets a where a.asset_id::text=r.source_id::text)
        then 'missing_source_asset'
      when lower(r.source_type) in ('mobile_asset','vessel')
       and not exists(select 1 from public.pc_mobile_assets m where m.mobile_asset_id::text=r.source_id::text)
        then 'missing_source_mobile_asset'
      when lower(r.source_type)='event'
       and not exists(select 1 from public.pc_events e where e.event_id::text=r.source_id::text)
        then 'missing_source_event'
      when lower(r.source_type)='programme'
       and not exists(select 1 from public.pc_defence_programmes p where p.defence_programme_id::text=r.source_id::text)
        then 'missing_source_programme'
      when lower(r.target_type)='entity'
       and not exists(select 1 from public.pc_entities e where e.entity_id::text=r.target_id::text)
        then 'missing_target_entity'
      when lower(r.target_type)='asset'
       and not exists(select 1 from public.pc_assets a where a.asset_id::text=r.target_id::text)
        then 'missing_target_asset'
      when lower(r.target_type) in ('mobile_asset','vessel')
       and not exists(select 1 from public.pc_mobile_assets m where m.mobile_asset_id::text=r.target_id::text)
        then 'missing_target_mobile_asset'
      when lower(r.target_type)='event'
       and not exists(select 1 from public.pc_events e where e.event_id::text=r.target_id::text)
        then 'missing_target_event'
      when lower(r.target_type)='programme'
       and not exists(select 1 from public.pc_defence_programmes p where p.defence_programme_id::text=r.target_id::text)
        then 'missing_target_programme'
      else null
    end as issue
from public.pc_relationships r
where
    (lower(r.source_type)='entity' and not exists(select 1 from public.pc_entities e where e.entity_id::text=r.source_id::text))
 or (lower(r.source_type)='asset' and not exists(select 1 from public.pc_assets a where a.asset_id::text=r.source_id::text))
 or (lower(r.source_type) in ('mobile_asset','vessel') and not exists(select 1 from public.pc_mobile_assets m where m.mobile_asset_id::text=r.source_id::text))
 or (lower(r.source_type)='event' and not exists(select 1 from public.pc_events e where e.event_id::text=r.source_id::text))
 or (lower(r.source_type)='programme' and not exists(select 1 from public.pc_defence_programmes p where p.defence_programme_id::text=r.source_id::text))
 or (lower(r.target_type)='entity' and not exists(select 1 from public.pc_entities e where e.entity_id::text=r.target_id::text))
 or (lower(r.target_type)='asset' and not exists(select 1 from public.pc_assets a where a.asset_id::text=r.target_id::text))
 or (lower(r.target_type) in ('mobile_asset','vessel') and not exists(select 1 from public.pc_mobile_assets m where m.mobile_asset_id::text=r.target_id::text))
 or (lower(r.target_type)='event' and not exists(select 1 from public.pc_events e where e.event_id::text=r.target_id::text))
 or (lower(r.target_type)='programme' and not exists(select 1 from public.pc_defence_programmes p where p.defence_programme_id::text=r.target_id::text));


-- ---------------------------------------------------------------------------
-- 4. One compact audit summary
-- ---------------------------------------------------------------------------
create or replace view public.pc_v_model_audit_summary as
select 'entities_total'::text check_name,count(*)::bigint issue_count from public.pc_entities
union all
select 'entities_with_zero_known_connections',count(*)
from public.pc_v_entity_relationship_coverage
where total_known_connections=0
union all
select 'rich_entities_missing_generic_graph',count(*)
from public.pc_v_entity_relationship_coverage
where rich_but_missing_generic_graph
union all
select 'relationship_gaps',count(*) from public.pc_v_model_relationship_gaps
union all
select 'invalid_relationship_endpoints',count(*) from public.pc_v_relationship_endpoint_audit
union all
select 'duplicate_entity_groups',count(*) from public.pc_v_duplicate_entity_candidates
union all
select 'duplicate_asset_groups',count(*) from public.pc_v_duplicate_asset_candidates
union all
select 'duplicate_mobile_asset_groups',count(*) from public.pc_v_duplicate_mobile_asset_candidates
union all
select 'duplicate_mobile_identifiers',count(*) from public.pc_v_duplicate_mobile_asset_identifiers;


create or replace function public.pc_model_audit_entity(p_entity_id text)
returns jsonb
language sql
stable
security definer
set search_path=public
as $$
    select jsonb_build_object(
      'entity',
      coalesce((select to_jsonb(x) from public.pc_v_entity_relationship_coverage x where x.entity_id=p_entity_id),'{}'::jsonb),
      'relationship_gaps',
      coalesce((select jsonb_agg(to_jsonb(g)) from public.pc_v_model_relationship_gaps g where g.source_id=p_entity_id),'[]'::jsonb),
      'generic_relationships',
      coalesce((
        select jsonb_agg(to_jsonb(r))
        from public.pc_relationships r
        where (lower(coalesce(r.source_type,''))='entity' and r.source_id::text=p_entity_id)
           or (lower(coalesce(r.target_type,''))='entity' and r.target_id::text=p_entity_id)
      ),'[]'::jsonb),
      'asset_roles',
      coalesce((select jsonb_agg(to_jsonb(r)) from public.pc_company_asset_roles r where r.entity_id::text=p_entity_id),'[]'::jsonb),
      'programme_roles',
      coalesce((
        select jsonb_agg(x) from (
          select to_jsonb(p) x from public.pc_defence_programmes p
           where p.lead_contractor_entity_id::text=p_entity_id or p.customer_entity_id::text=p_entity_id
          union all
          select to_jsonb(pp) from public.pc_defence_programme_participants pp where pp.entity_id::text=p_entity_id
        ) q
      ),'[]'::jsonb),
      'production_roles',
      coalesce((select jsonb_agg(to_jsonb(t)) from public.pc_shipbuilding_production_tasks t where t.builder_entity_id::text=p_entity_id),'[]'::jsonb),
      'capacity_roles',
      coalesce((select jsonb_agg(to_jsonb(h)) from public.pc_shipyard_capacity_history h where h.operator_entity_id::text=p_entity_id),'[]'::jsonb),
      'event_links',
      coalesce((select jsonb_agg(to_jsonb(el)) from public.pc_event_links el
                where lower(coalesce(el.linked_type,'')) in ('entity','company','organisation','organization')
                  and el.linked_id::text=p_entity_id),'[]'::jsonb)
    );
$$;

grant select on public.pc_v_entity_relationship_coverage to authenticated,service_role;
grant select on public.pc_v_model_relationship_gaps to authenticated,service_role;
grant select on public.pc_v_relationship_endpoint_audit to authenticated,service_role;
grant select on public.pc_v_model_audit_summary to authenticated,service_role;
grant execute on function public.pc_model_audit_entity(text) to authenticated,service_role;

commit;

-- Recommended first queries:
--
-- select * from public.pc_v_model_audit_summary;
--
-- select *
-- from public.pc_v_entity_relationship_coverage
-- where rich_but_missing_generic_graph
-- order by total_known_connections desc, name;
--
-- select *
-- from public.pc_v_model_relationship_gaps
-- order by source_name, issue_type;
--
-- select public.pc_model_audit_entity('COMP_IRVING');
-- select public.pc_model_audit_entity('<SEASPAN_ENTITY_ID>');
