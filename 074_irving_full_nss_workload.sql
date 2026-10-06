-- Power & Corridors
-- 074_irving_full_nss_workload.sql
--
-- Expands Irving Shipbuilding from the two CCG AOPS already materialised in 072
-- to the wider National Shipbuilding Strategy workload:
--   * 6 delivered RCN Arctic and Offshore Patrol Ships
--   * 2 CCG AOPS (existing Donjek / Sermilik retained)
--   * River-class Destroyer programme
--   * Batch 1 implementation-contract context
--   * first 3 named RCD hulls
--
-- Official programme facts are retained in metadata with source URLs.

begin;

-- ---------------------------------------------------------------------------
-- A. RCN AOPS programme
-- ---------------------------------------------------------------------------
insert into public.pc_defence_programmes(
  programme_name,
  customer_entity_id,
  lead_contractor_entity_id,
  programme_type,
  programme_status,
  firm_quantity,
  announced_value,
  currency,
  verification_status,
  metadata,
  created_at,
  updated_at
)
select
  'Royal Canadian Navy Arctic and Offshore Patrol Ships',
  (
    select e.entity_id
    from public.pc_entities e
    where public.pc_norm_identity_text(e.name)=public.pc_norm_identity_text('Royal Canadian Navy')
    order by case when lower(coalesce(e.record_status,''))='verified' then 0 else 1 end,
             e.created_at
    limit 1
  ),
  'COMP_IRVING',
  'naval_shipbuilding',
  'delivered',
  6,
  4980000000,
  'CAD',
  'verified',
  jsonb_build_object(
    'materialisation','074',
    'class_name','Harry DeWolf-class',
    'delivery_period','2020-2025',
    'shipyard','Irving Shipbuilding Inc., Halifax, Nova Scotia',
    'source_url','https://www.canada.ca/en/public-services-procurement/services/acquisitions/defence-marine/national-shipbuilding-strategy/projects/large-vessels/arctic-patrol-navy.html',
    'source_authority','Government of Canada'
  ),
  now(),
  now()
where not exists (
  select 1 from public.pc_defence_programmes p
  where public.pc_norm_identity_text(p.programme_name)=
        public.pc_norm_identity_text('Royal Canadian Navy Arctic and Offshore Patrol Ships')
);

-- Irving participant on RCN AOPS.
insert into public.pc_defence_programme_participants(
  defence_programme_id,
  entity_id,
  shipyard_asset_id,
  participant_role,
  participation_status,
  verification_status,
  metadata,
  created_at,
  updated_at
)
select
  p.defence_programme_id,
  'COMP_IRVING',
  a.asset_id,
  'builder',
  'completed',
  'verified',
  jsonb_build_object(
    'materialisation','074',
    'source_url','https://www.canada.ca/en/public-services-procurement/services/acquisitions/defence-marine/national-shipbuilding-strategy/projects/large-vessels/arctic-patrol-navy.html'
  ),
  now(),
  now()
from public.pc_defence_programmes p
cross join lateral (
  select a1.asset_id
  from public.pc_assets a1
  where public.pc_norm_identity_text(a1.name)=public.pc_norm_identity_text('Halifax Shipyard')
  order by case when a1.asset_id='ASSET_STRAT_IRVING_HALIFAX_SHIPYARD' then 0 else 1 end
  limit 1
) a
where public.pc_norm_identity_text(p.programme_name)=
      public.pc_norm_identity_text('Royal Canadian Navy Arctic and Offshore Patrol Ships')
  and not exists (
    select 1 from public.pc_defence_programme_participants pp
    where pp.defence_programme_id=p.defence_programme_id
      and pp.entity_id='COMP_IRVING'
      and pp.shipyard_asset_id=a.asset_id
      and lower(coalesce(pp.participant_role,''))='builder'
  );

-- ---------------------------------------------------------------------------
-- B. Six delivered RCN AOPS
-- ---------------------------------------------------------------------------
with ships(mobile_asset_id,name,delivery_date) as (
  values
    ('MOBILE_CA_HMCS_HARRY_DEWOLF','HMCS Harry DeWolf','2020-07-31'::date),
    ('MOBILE_CA_HMCS_MARGARET_BROOKE','HMCS Margaret Brooke','2021-07-15'::date),
    ('MOBILE_CA_HMCS_MAX_BERNAYS','HMCS Max Bernays','2022-09-02'::date),
    ('MOBILE_CA_HMCS_WILLIAM_HALL','HMCS William Hall','2023-08-30'::date),
    ('MOBILE_CA_HMCS_FREDERICK_ROLETTE','HMCS Frédérick Rolette','2024-08-29'::date),
    ('MOBILE_CA_HMCS_ROBERT_HAMPTON_GRAY','HMCS Robert Hampton Gray','2025-08-21'::date)
)
insert into public.pc_mobile_assets(
  mobile_asset_id,
  name,
  asset_type,
  subtype,
  status,
  record_status,
  data_quality,
  metadata,
  created_at,
  updated_at
)
select
  s.mobile_asset_id,
  s.name,
  'naval vessel',
  'Harry DeWolf-class Arctic and Offshore Patrol Ship',
  'Delivered / active service',
  'verified',
  'high',
  jsonb_build_object(
    'materialisation','074',
    'research_attributes',jsonb_build_object(
      'builder','Irving Shipbuilding Inc.',
      'shipyard','Halifax Shipyard',
      'programme','Royal Canadian Navy Arctic and Offshore Patrol Ships',
      'operator','Royal Canadian Navy',
      'service','Royal Canadian Navy',
      'class','Harry DeWolf-class',
      'delivery_date',s.delivery_date
    ),
    'source_url','https://www.canada.ca/en/public-services-procurement/services/acquisitions/defence-marine/national-shipbuilding-strategy/projects/large-vessels/arctic-patrol-navy.html',
    'source_authority','Government of Canada'
  ),
  now(),
  now()
from ships s
where not exists (
  select 1 from public.pc_mobile_assets m
  where public.pc_norm_identity_text(m.name)=public.pc_norm_identity_text(s.name)
);

-- ---------------------------------------------------------------------------
-- C. River-class Destroyer programme
-- ---------------------------------------------------------------------------
insert into public.pc_defence_programmes(
  programme_name,
  customer_entity_id,
  lead_contractor_entity_id,
  programme_type,
  programme_status,
  firm_quantity,
  announced_value,
  currency,
  verification_status,
  metadata,
  created_at,
  updated_at
)
select
  'River-class Destroyer Project',
  (
    select e.entity_id
    from public.pc_entities e
    where public.pc_norm_identity_text(e.name)=public.pc_norm_identity_text('Royal Canadian Navy')
    order by case when lower(coalesce(e.record_status,''))='verified' then 0 else 1 end,
             e.created_at
    limit 1
  ),
  'COMP_IRVING',
  'naval_shipbuilding',
  'design_build',
  15,
  22200000000,
  'CAD',
  'verified',
  jsonb_build_object(
    'materialisation','074',
    'former_name','Canadian Surface Combatant',
    'design_basis','BAE Systems Type 26 Global Combat Ship',
    'batch_1_quantity',3,
    'batch_1_implementation_contract_value_cad_including_tax',8000000000,
    'batch_1_total_estimated_cost_cad',22200000000,
    'implementation_contract_awarded','2025-03-03',
    'full_rate_production_started','2025-04-25',
    'first_ship_delivery','early 2030s',
    'final_ship_target','2050',
    'prime_contractor','Irving Shipbuilding Inc.',
    'design_team_lead','Lockheed Martin Canada',
    'source_url','https://www.canada.ca/en/public-services-procurement/services/acquisitions/defence-marine/national-shipbuilding-strategy/projects/large-vessels/river-class-destroyer.html',
    'contract_source_url','https://www.canada.ca/en/department-national-defence/news/2025/03/government-of-canada-announces-contract-award-for-the-construction-of-the-river-class-destroyers-for-the-royal-canadian-navy.html'
  ),
  now(),
  now()
where not exists (
  select 1 from public.pc_defence_programmes p
  where public.pc_norm_identity_text(p.programme_name)=
        public.pc_norm_identity_text('River-class Destroyer Project')
);

-- Irving participant on River-class programme.
insert into public.pc_defence_programme_participants(
  defence_programme_id,
  entity_id,
  shipyard_asset_id,
  participant_role,
  participation_status,
  verification_status,
  metadata,
  created_at,
  updated_at
)
select
  p.defence_programme_id,
  'COMP_IRVING',
  a.asset_id,
  'prime',
  'active',
  'verified',
  jsonb_build_object(
    'materialisation','074',
    'implementation_contract_awarded','2025-03-03',
    'initial_contract_value_cad_including_tax',8000000000,
    'source_url','https://www.canada.ca/en/department-national-defence/news/2025/03/government-of-canada-announces-contract-award-for-the-construction-of-the-river-class-destroyers-for-the-royal-canadian-navy.html'
  ),
  now(),
  now()
from public.pc_defence_programmes p
cross join lateral (
  select a1.asset_id
  from public.pc_assets a1
  where public.pc_norm_identity_text(a1.name)=public.pc_norm_identity_text('Halifax Shipyard')
  order by case when a1.asset_id='ASSET_STRAT_IRVING_HALIFAX_SHIPYARD' then 0 else 1 end
  limit 1
) a
where public.pc_norm_identity_text(p.programme_name)=
      public.pc_norm_identity_text('River-class Destroyer Project')
  and not exists (
    select 1 from public.pc_defence_programme_participants pp
    where pp.defence_programme_id=p.defence_programme_id
      and pp.entity_id='COMP_IRVING'
      and pp.shipyard_asset_id=a.asset_id
      and lower(coalesce(pp.participant_role,'')) in ('prime','builder')
  );

-- ---------------------------------------------------------------------------
-- D. First three named River-class destroyers
-- ---------------------------------------------------------------------------
with ships(mobile_asset_id,name,status_text,construction_note) as (
  values
    ('MOBILE_CA_HMCS_FRASER_RCD','HMCS Fraser','Under construction','Full-rate production began 2025-04-25; keel laid 2026-06-12'),
    ('MOBILE_CA_HMCS_SAINT_LAURENT_RCD','HMCS Saint-Laurent','Planned / Batch 1','Named Batch 1 River-class destroyer'),
    ('MOBILE_CA_HMCS_MACKENZIE_RCD','HMCS Mackenzie','Planned / Batch 1','Named Batch 1 River-class destroyer')
)
insert into public.pc_mobile_assets(
  mobile_asset_id,
  name,
  asset_type,
  subtype,
  status,
  record_status,
  data_quality,
  metadata,
  created_at,
  updated_at
)
select
  s.mobile_asset_id,
  s.name,
  'naval vessel',
  'River-class guided-missile destroyer',
  s.status_text,
  'verified',
  'high',
  jsonb_build_object(
    'materialisation','074',
    'research_attributes',jsonb_build_object(
      'builder','Irving Shipbuilding Inc.',
      'shipyard','Halifax Shipyard',
      'programme','River-class Destroyer Project',
      'operator','Royal Canadian Navy',
      'service','Royal Canadian Navy',
      'class','River-class destroyer',
      'construction_status',s.construction_note
    ),
    'source_url','https://www.canada.ca/en/public-services-procurement/services/acquisitions/defence-marine/national-shipbuilding-strategy/projects/large-vessels/river-class-destroyer.html',
    'source_authority','Government of Canada'
  ),
  now(),
  now()
from ships s
where not exists (
  select 1 from public.pc_mobile_assets m
  where public.pc_norm_identity_text(m.name)=public.pc_norm_identity_text(s.name)
);

-- ---------------------------------------------------------------------------
-- E. Production record for HMCS Fraser
-- ---------------------------------------------------------------------------
insert into public.pc_shipbuilding_production_tasks(
  defence_programme_id,
  shipyard_asset_id,
  builder_entity_id,
  task_type,
  task_status,
  actual_start,
  verification_status,
  metadata,
  created_at,
  updated_at
)
select
  p.defence_programme_id,
  a.asset_id,
  'COMP_IRVING',
  'hull',
  'in_progress',
  '2025-04-25'::date,
  'verified',
  jsonb_build_object(
    'materialisation','074',
    'mobile_asset_id','MOBILE_CA_HMCS_FRASER_RCD',
    'mobile_asset_name','HMCS Fraser',
    'keel_laid','2026-06-12',
    'source_url','https://www.canada.ca/en/department-national-defence/news/2026/06/canada-celebrates-keel-laying-for-the-first-river-class-destroyer.html'
  ),
  now(),
  now()
from public.pc_defence_programmes p
cross join lateral (
  select a1.asset_id
  from public.pc_assets a1
  where public.pc_norm_identity_text(a1.name)=public.pc_norm_identity_text('Halifax Shipyard')
  order by case when a1.asset_id='ASSET_STRAT_IRVING_HALIFAX_SHIPYARD' then 0 else 1 end
  limit 1
) a
where public.pc_norm_identity_text(p.programme_name)=
      public.pc_norm_identity_text('River-class Destroyer Project')
  and not exists (
    select 1 from public.pc_shipbuilding_production_tasks t
    where t.defence_programme_id=p.defence_programme_id
      and t.builder_entity_id='COMP_IRVING'
      and t.metadata->>'mobile_asset_id'='MOBILE_CA_HMCS_FRASER_RCD'
  );

-- ---------------------------------------------------------------------------
-- F. Exact fanout creates Irving-built, programme and shipyard graph edges
-- ---------------------------------------------------------------------------
select public.pc_fanout_mobile_asset_metadata_relationships(null);
select public.pc_normalize_canonical_relationships();
select public.pc_refresh_terminal_indexes();
select public.pc_refresh_terminal_industrial_links();

commit;

-- Validation:
-- select public.pc_strategic_entity_dossier('COMP_IRVING')->'counts';
-- select * from public.pc_model_audit_entity('COMP_IRVING');
