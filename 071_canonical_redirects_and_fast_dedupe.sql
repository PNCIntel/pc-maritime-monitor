-- Power & Corridors
-- 071_canonical_redirects_and_fast_dedupe.sql
-- Non-destructive canonicalization of high-confidence duplicate identities.

begin;

create table if not exists public.pc_canonical_redirects (
  object_type text not null,
  old_id text not null,
  canonical_id text not null,
  reason text,
  repair_batch text not null,
  created_at timestamptz not null default now(),
  primary key(object_type,old_id)
);

insert into public.pc_canonical_redirects(object_type,old_id,canonical_id,reason,repair_batch)
values
  ('entity','ENTITY_AUTO_D540F54A753AB8AEE06F','COMP_ADPORTS','Exact AD Ports Group duplicate; established verified canonical retained','071'),
  ('entity','ENTITY_AUTO_14AC45E381E56D016C0C','ENTITY_AI_804FD23236FD75DD3B53','Exact CMA CGM duplicate; verified richer canonical retained','071'),
  ('entity','ENTITY_AUTO_B0294574BC3FAAF9C658','ENTITY_AI_60FFF9C19D88574917BD','Exact Maersk duplicate; earlier typed canonical retained','071'),
  ('entity','ENTITY_AI_DED57FF6C015BF3A7BF5','ENTITY_AI_17857DBB958CD17489CB','Equivalent Drydocks World / DP World shell','071'),

  ('asset','ASSET_91C8D829DDF6787C904E','ASSET_036C76352AB148DA','Exact East-West Oil Pipeline duplicate','071'),
  ('asset','PORT_UK_HARWICH_INTERNATIONAL_PORT','PORTG0244','Harwich alias duplicate; verified high-quality port retained','071'),
  ('asset','ASSET_82E9227D149AAD81','ASSET011','Exact Khalifa Port duplicate; established verified port retained','071'),
  ('asset','ASSET_2A78730707EA6F88','ASSET_2483ACCCA4843D63','Exact Matson Auburn cross-dock duplicate','071'),
  ('asset','ASSET_0B02CB2FEAF8FDAC','ASSET_A2DC810FE588C63A','Exact Matson Oakland warehouse duplicate','071'),
  ('asset','ASSET_5494F7E8C7D5A6DE','ASSET_CFD036329508E17E','Exact Matson Pooler warehouse duplicate','071'),
  ('asset','ASSET_C5707183525F070BC4BE','PORTG0123','Exact Port of Odesa duplicate','071'),
  ('asset','ASSET_AI_PORT_OF_TILBURY_C64FFA1FAD','UKP031','Port of Tilbury alias duplicate; verified high-quality port retained','071')
on conflict(object_type,old_id) do update
set canonical_id=excluded.canonical_id,
    reason=excluded.reason,
    repair_batch=excluded.repair_batch;

-- Generic graph endpoints.
-- Build the FINAL redirected relationship identity first. This avoids violating
-- ux_pc_relationships_identity when the canonical object already has the same edge.
drop table if exists pc_071_relationship_redirect_plan;
create temporary table pc_071_relationship_redirect_plan on commit drop as
with desired as (
  select
    r.relationship_id::text relationship_id,
    r.source_type,
    r.source_id::text old_source_id,
    coalesce(ds.canonical_id,r.source_id::text) desired_source_id,
    r.relationship_type,
    r.target_type,
    r.target_id::text old_target_id,
    coalesce(dt.canonical_id,r.target_id::text) desired_target_id,
    r.valid_from,
    r.record_status,
    r.confidence,
    r.created_at,
    (ds.old_id is not null or dt.old_id is not null) as affected
  from public.pc_relationships r
  left join public.pc_canonical_redirects ds
    on ds.object_type=lower(r.source_type)
   and ds.old_id=r.source_id::text
   and ds.repair_batch='071'
  left join public.pc_canonical_redirects dt
    on dt.object_type=lower(r.target_type)
   and dt.old_id=r.target_id::text
   and dt.repair_batch='071'
),
ranked as (
  select
    d.*,
    row_number() over (
      partition by
        lower(coalesce(d.source_type,'')),
        d.desired_source_id,
        lower(coalesce(d.relationship_type,'')),
        lower(coalesce(d.target_type,'')),
        d.desired_target_id,
        coalesce(d.valid_from,date '0001-01-01')
      order by
        case when d.old_source_id=d.desired_source_id
                  and d.old_target_id=d.desired_target_id then 0 else 1 end,
        case when lower(coalesce(d.record_status,''))='verified' then 0 else 1 end,
        case
          when lower(trim(coalesce(d.confidence::text,''))) in ('very high','high') then 4
          when lower(trim(coalesce(d.confidence::text,'')))='medium' then 3
          when lower(trim(coalesce(d.confidence::text,'')))='low' then 2
          when nullif(trim(coalesce(d.confidence::text,'')),'') is not null then 1
          else 0
        end desc,
        d.created_at nulls last,
        d.relationship_id
    ) as canonical_rank
  from desired d
)
select * from ranked;

-- Preserve any redirected edge that would become a duplicate of a better existing
-- canonical edge, then remove only that redundant graph row.
insert into public.pc_model_repair_audit(
  repair_audit_id,repair_batch,object_type,object_id,repair_action,before_record
)
select
  'AUDIT_071_'||upper(substr(md5('relationship_collision|'||p.relationship_id),1,24)),
  '071',
  'relationship',
  p.relationship_id,
  'dedupe_relationship_during_redirect',
  to_jsonb(r)
from pc_071_relationship_redirect_plan p
join public.pc_relationships r
  on r.relationship_id::text=p.relationship_id
where p.affected
  and p.canonical_rank>1
on conflict (repair_audit_id) do nothing;

delete from public.pc_relationships r
using pc_071_relationship_redirect_plan p
where r.relationship_id::text=p.relationship_id
  and p.affected
  and p.canonical_rank>1;

-- Repoint the surviving affected graph rows directly to their final canonical IDs.
update public.pc_relationships r
set source_id=p.desired_source_id,
    target_id=p.desired_target_id,
    metadata=coalesce(r.metadata,'{}'::jsonb)
      || jsonb_build_object(
           'canonical_redirect',
           jsonb_build_object(
             'batch','071',
             'previous_source_id',p.old_source_id,
             'previous_target_id',p.old_target_id
           )
         ),
    updated_at=now()
from pc_071_relationship_redirect_plan p
where r.relationship_id::text=p.relationship_id
  and p.affected
  and p.canonical_rank=1;

-- Event links.
update public.pc_event_links el
set linked_id=d.canonical_id
from public.pc_canonical_redirects d
where (
      d.object_type='entity'
      and lower(coalesce(el.linked_type,'')) in ('entity','company','organisation','organization')
      and el.linked_id::text=d.old_id
    )
   or (
      d.object_type='asset'
      and lower(coalesce(el.linked_type,''))='asset'
      and el.linked_id::text=d.old_id
    );

-- Entity foreign keys in canonical objects.
update public.pc_assets a
set owner_entity_id=d.canonical_id
from public.pc_canonical_redirects d
where d.object_type='entity' and a.owner_entity_id::text=d.old_id;

update public.pc_assets a
set operator_entity_id=d.canonical_id
from public.pc_canonical_redirects d
where d.object_type='entity' and a.operator_entity_id::text=d.old_id;

update public.pc_mobile_assets m
set owner_entity_id=d.canonical_id
from public.pc_canonical_redirects d
where d.object_type='entity' and m.owner_entity_id::text=d.old_id;

update public.pc_mobile_assets m
set operator_entity_id=d.canonical_id
from public.pc_canonical_redirects d
where d.object_type='entity' and m.operator_entity_id::text=d.old_id;

update public.pc_mobile_assets m
set manager_entity_id=d.canonical_id
from public.pc_canonical_redirects d
where d.object_type='entity' and m.manager_entity_id::text=d.old_id;

-- Company/asset specialist links.
update public.pc_company_asset_roles x
set entity_id=d.canonical_id
from public.pc_canonical_redirects d
where d.object_type='entity' and x.entity_id::text=d.old_id;

update public.pc_company_asset_roles x
set asset_id=d.canonical_id
from public.pc_canonical_redirects d
where d.object_type='asset' and x.asset_id::text=d.old_id;

update public.pc_company_corridor_roles x
set entity_id=d.canonical_id
from public.pc_canonical_redirects d
where d.object_type='entity' and x.entity_id::text=d.old_id;

update public.pc_company_portfolio_positions x
set entity_id=d.canonical_id
from public.pc_canonical_redirects d
where d.object_type='entity' and x.entity_id::text=d.old_id;

update public.pc_document_entity_links x
set entity_id=d.canonical_id
from public.pc_canonical_redirects d
where d.object_type='entity' and x.entity_id::text=d.old_id;

-- Industrial tables.
update public.pc_defence_programmes p
set lead_contractor_entity_id=d.canonical_id
from public.pc_canonical_redirects d
where d.object_type='entity' and p.lead_contractor_entity_id::text=d.old_id;

update public.pc_defence_programmes p
set customer_entity_id=d.canonical_id
from public.pc_canonical_redirects d
where d.object_type='entity' and p.customer_entity_id::text=d.old_id;

update public.pc_defence_programme_participants p
set entity_id=d.canonical_id
from public.pc_canonical_redirects d
where d.object_type='entity' and p.entity_id::text=d.old_id;

update public.pc_defence_programme_participants p
set shipyard_asset_id=d.canonical_id
from public.pc_canonical_redirects d
where d.object_type='asset' and p.shipyard_asset_id::text=d.old_id;

update public.pc_shipbuilding_production_tasks p
set builder_entity_id=d.canonical_id
from public.pc_canonical_redirects d
where d.object_type='entity' and p.builder_entity_id::text=d.old_id;

update public.pc_shipbuilding_production_tasks p
set shipyard_asset_id=d.canonical_id
from public.pc_canonical_redirects d
where d.object_type='asset' and p.shipyard_asset_id::text=d.old_id;

update public.pc_shipyard_capacity_history p
set operator_entity_id=d.canonical_id
from public.pc_canonical_redirects d
where d.object_type='entity' and p.operator_entity_id::text=d.old_id;

update public.pc_shipyard_capacity_history p
set shipyard_asset_id=d.canonical_id
from public.pc_canonical_redirects d
where d.object_type='asset' and p.shipyard_asset_id::text=d.old_id;

-- Preserve redirect on old object metadata so UI/loaders can recognize it.
update public.pc_entities e
set metadata=coalesce(e.metadata,'{}'::jsonb) ||
  jsonb_build_object('canonical_redirect',
    jsonb_build_object('canonical_id',d.canonical_id,'batch','071','reason',d.reason)),
    updated_at=now()
from public.pc_canonical_redirects d
where d.object_type='entity' and e.entity_id::text=d.old_id;

update public.pc_assets a
set metadata=coalesce(a.metadata,'{}'::jsonb) ||
  jsonb_build_object('canonical_redirect',
    jsonb_build_object('canonical_id',d.canonical_id,'batch','071','reason',d.reason)),
    updated_at=now()
from public.pc_canonical_redirects d
where d.object_type='asset' and a.asset_id::text=d.old_id;

select public.pc_normalize_canonical_relationships();
select public.pc_fanout_mobile_asset_metadata_relationships(null);
select public.pc_refresh_terminal_indexes();

do $$
begin
  if to_regprocedure('public.pc_refresh_terminal_industrial_links()') is not null then
    perform public.pc_refresh_terminal_industrial_links();
  end if;
end $$;

grant select on public.pc_canonical_redirects to authenticated,service_role;

commit;

-- Validate:
-- select * from public.pc_canonical_redirects where repair_batch='071';
-- select * from public.pc_v_model_audit_summary;
