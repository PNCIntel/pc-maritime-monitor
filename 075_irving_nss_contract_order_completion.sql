-- Power & Corridors
-- 075_irving_nss_contract_order_completion.sql
--
-- Completes Irving / Canadian National Shipbuilding Strategy materialisation
-- by using the live generic contract + shipbuilding order model rather than
-- leaving awards and hulls only in programme/mobile-asset metadata.
--
-- Materialises:
--   * RCN AOPS construction contract/order + 6 delivered order units
--   * CCG AOPS 7/8 contract/order + Donjek and Sermilik order units
--   * River-class Destroyer Batch 1 implementation contract/order + 3 named units
--   * pc_defence_programmes -> contract/order links
--   * existing CCG / HMCS Fraser production tasks -> order/unit links
--
-- Important modelling distinction:
--   * project/acquisition budgets remain programme metadata/announced_value
--   * pc_contracts.reported_value is only populated where a public contract
--     value is explicitly reported
--
-- Helsinki ownership/resolver logic is intentionally untouched.

begin;

-- ---------------------------------------------------------------------------
-- 0. Preconditions
-- ---------------------------------------------------------------------------
do $$
begin
  if not exists (select 1 from public.pc_entities where entity_id='COMP_IRVING') then
    raise exception 'Missing canonical Irving entity COMP_IRVING';
  end if;

  if not exists (
    select 1 from public.pc_assets
    where asset_id='ASSET_STRAT_IRVING_HALIFAX_SHIPYARD'
       or public.pc_norm_identity_text(name)=public.pc_norm_identity_text('Halifax Shipyard')
  ) then
    raise exception 'Missing Halifax Shipyard asset';
  end if;

  if not exists (
    select 1 from public.pc_defence_programmes
    where public.pc_norm_identity_text(programme_name)=
          public.pc_norm_identity_text('Royal Canadian Navy Arctic and Offshore Patrol Ships')
  ) then
    raise exception 'Missing RCN AOPS programme from 074';
  end if;

  if not exists (
    select 1 from public.pc_defence_programmes
    where public.pc_norm_identity_text(programme_name)=
          public.pc_norm_identity_text('Canadian Coast Guard Arctic and Offshore Patrol Ships')
  ) then
    raise exception 'Missing CCG AOPS programme from 072';
  end if;

  if not exists (
    select 1 from public.pc_defence_programmes
    where public.pc_norm_identity_text(programme_name)=
          public.pc_norm_identity_text('River-class Destroyer Project')
  ) then
    raise exception 'Missing River-class Destroyer programme from 074';
  end if;
end $$;


-- ---------------------------------------------------------------------------
-- 1. Canonical contracts
-- ---------------------------------------------------------------------------

-- 1A. RCN AOPS construction contract.
-- Public contract value: CAD 2.6bn including taxes.
-- Acquisition/project budget is separately retained at programme level.
insert into public.pc_contracts(
  contract_id,
  contract_name,
  contract_type,
  announced_date,
  signed_date,
  status,
  reported_value,
  currency,
  quantity,
  quantity_unit,
  scope_summary,
  award_method,
  source_url,
  primary_source_url,
  record_status,
  metadata,
  created_at,
  updated_at
)
values(
  'CONTRACT_CA_RCN_AOPS_BUILD',
  'Royal Canadian Navy Arctic and Offshore Patrol Ships construction contract',
  'shipbuilding',
  '2015-01-23'::date,
  '2014-12-23'::date,
  'completed',
  2600000000,
  'CAD',
  6,
  'vessels',
  'Construction of six Harry DeWolf-class Arctic and Offshore Patrol Ships for the Royal Canadian Navy by Irving Shipbuilding Inc. at Halifax Shipyard.',
  'National Shipbuilding Strategy',
  'https://www.canada.ca/en/department-national-defence/services/procurement/arctic-offshore-patrol-ships.html',
  'https://www.canada.ca/en/department-national-defence/services/procurement/arctic-offshore-patrol-ships.html',
  'approved',
  jsonb_build_object(
    'materialisation','075',
    'contract_value_basis','Government of Canada reports January 2015 CAD 2.6bn construction contract including taxes',
    'project_budget_cad_excluding_tax',4980000000,
    'project_budget_is_not_contract_value',true,
    'builder_entity_id','COMP_IRVING',
    'shipyard_asset_id','ASSET_STRAT_IRVING_HALIFAX_SHIPYARD'
  ),
  now(),
  now()
)
on conflict(contract_id) do update set
  contract_name=excluded.contract_name,
  contract_type=excluded.contract_type,
  announced_date=excluded.announced_date,
  signed_date=excluded.signed_date,
  status=excluded.status,
  reported_value=excluded.reported_value,
  currency=excluded.currency,
  quantity=excluded.quantity,
  quantity_unit=excluded.quantity_unit,
  scope_summary=excluded.scope_summary,
  source_url=excluded.source_url,
  primary_source_url=excluded.primary_source_url,
  record_status=excluded.record_status,
  metadata=coalesce(public.pc_contracts.metadata,'{}'::jsonb)||excluded.metadata,
  updated_at=now();


-- 1B. CCG AOPS 7/8 construction award.
-- The Government publicly reports a CAD 2.1bn project budget; this is not
-- written into reported_value because a clean current contract value is not
-- established by the programme page.
insert into public.pc_contracts(
  contract_id,
  contract_name,
  contract_type,
  announced_date,
  signed_date,
  status,
  reported_value,
  currency,
  quantity,
  quantity_unit,
  scope_summary,
  award_method,
  source_url,
  primary_source_url,
  record_status,
  metadata,
  created_at,
  updated_at
)
values(
  'CONTRACT_CA_CCG_AOPS_7_8',
  'Canadian Coast Guard Arctic and Offshore Patrol Ships 7 and 8 construction award',
  'shipbuilding',
  '2019-05-22'::date,
  '2019-05-22'::date,
  'active',
  null,
  'CAD',
  2,
  'vessels',
  'Construction by Irving Shipbuilding Inc. of two Arctic and Offshore Patrol Ship variants adapted for Canadian Coast Guard missions.',
  'National Shipbuilding Strategy',
  'https://www.canada.ca/en/public-services-procurement/services/acquisitions/defence-marine/national-shipbuilding-strategy/projects/large-vessels/arctic-patrol-coast-guard.html',
  'https://www.canada.ca/en/public-services-procurement/services/acquisitions/defence-marine/national-shipbuilding-strategy/projects/large-vessels/arctic-patrol-coast-guard.html',
  'approved',
  jsonb_build_object(
    'materialisation','075',
    'project_budget_cad',2100000000,
    'project_budget_is_not_contract_value',true,
    'award_date_publicly_reported','2019-05-22',
    'builder_entity_id','COMP_IRVING',
    'shipyard_asset_id','ASSET_STRAT_IRVING_HALIFAX_SHIPYARD'
  ),
  now(),
  now()
)
on conflict(contract_id) do update set
  contract_name=excluded.contract_name,
  contract_type=excluded.contract_type,
  announced_date=excluded.announced_date,
  signed_date=excluded.signed_date,
  status=excluded.status,
  currency=excluded.currency,
  quantity=excluded.quantity,
  quantity_unit=excluded.quantity_unit,
  scope_summary=excluded.scope_summary,
  source_url=excluded.source_url,
  primary_source_url=excluded.primary_source_url,
  record_status=excluded.record_status,
  metadata=coalesce(public.pc_contracts.metadata,'{}'::jsonb)||excluded.metadata,
  updated_at=now();


-- 1C. River-class Destroyer Batch 1 implementation contract.
insert into public.pc_contracts(
  contract_id,
  contract_name,
  contract_type,
  announced_date,
  signed_date,
  effective_date,
  status,
  reported_value,
  currency,
  quantity,
  quantity_unit,
  scope_summary,
  award_method,
  source_url,
  primary_source_url,
  record_status,
  metadata,
  created_at,
  updated_at
)
values(
  'CONTRACT_CA_RCD_BATCH1_IMPL',
  'River-class Destroyer Batch 1 implementation contract',
  'shipbuilding',
  '2025-03-08'::date,
  '2025-03-03'::date,
  '2025-03-03'::date,
  'active',
  8000000000,
  'CAD',
  3,
  'vessels',
  'Initial implementation contract for construction and delivery of the first three River-class destroyers, including associated training, spares and maintenance products.',
  'National Shipbuilding Strategy',
  'https://www.canada.ca/en/department-national-defence/news/2025/03/government-of-canada-announces-contract-award-for-the-construction-of-the-river-class-destroyers-for-the-royal-canadian-navy.html',
  'https://www.canada.ca/en/public-services-procurement/services/acquisitions/defence-marine/national-shipbuilding-strategy/projects/large-vessels/river-class-destroyer.html',
  'approved',
  jsonb_build_object(
    'materialisation','075',
    'contract_value_includes_tax',true,
    'initial_contract_value_cad',8000000000,
    'batch_1_total_estimated_cost_cad_excluding_tax',22200000000,
    'total_estimated_cost_is_not_contract_value',true,
    'contract_funds_first_six_years_of_construction',true,
    'builder_entity_id','COMP_IRVING',
    'shipyard_asset_id','ASSET_STRAT_IRVING_HALIFAX_SHIPYARD'
  ),
  now(),
  now()
)
on conflict(contract_id) do update set
  contract_name=excluded.contract_name,
  contract_type=excluded.contract_type,
  announced_date=excluded.announced_date,
  signed_date=excluded.signed_date,
  effective_date=excluded.effective_date,
  status=excluded.status,
  reported_value=excluded.reported_value,
  currency=excluded.currency,
  quantity=excluded.quantity,
  quantity_unit=excluded.quantity_unit,
  scope_summary=excluded.scope_summary,
  source_url=excluded.source_url,
  primary_source_url=excluded.primary_source_url,
  record_status=excluded.record_status,
  metadata=coalesce(public.pc_contracts.metadata,'{}'::jsonb)||excluded.metadata,
  updated_at=now();


-- ---------------------------------------------------------------------------
-- 2. Contract participants: customer + Irving prime/builder
-- ---------------------------------------------------------------------------
with contract_programmes(contract_id,programme_name) as (
  values
    ('CONTRACT_CA_RCN_AOPS_BUILD','Royal Canadian Navy Arctic and Offshore Patrol Ships'),
    ('CONTRACT_CA_CCG_AOPS_7_8','Canadian Coast Guard Arctic and Offshore Patrol Ships'),
    ('CONTRACT_CA_RCD_BATCH1_IMPL','River-class Destroyer Project')
),
participants as (
  select cp.contract_id,p.customer_entity_id as entity_id,'customer'::text as role
  from contract_programmes cp
  join public.pc_defence_programmes p
    on public.pc_norm_identity_text(p.programme_name)=public.pc_norm_identity_text(cp.programme_name)
  where p.customer_entity_id is not null

  union all

  select cp.contract_id,'COMP_IRVING'::text,'prime_contractor'::text
  from contract_programmes cp
)
insert into public.pc_contract_participants(
  contract_participant_id,
  contract_id,
  entity_id,
  participant_name,
  role,
  source_id,
  metadata
)
select
  gen_random_uuid(),
  x.contract_id,
  x.entity_id,
  null,
  x.role,
  null,
  jsonb_build_object('materialisation','075')
from participants x
where exists(select 1 from public.pc_entities e where e.entity_id=x.entity_id)
  and not exists (
    select 1
    from public.pc_contract_participants p
    where p.contract_id=x.contract_id
      and p.entity_id=x.entity_id
      and lower(coalesce(p.role,''))=lower(x.role)
  );


-- ---------------------------------------------------------------------------
-- 3. Shipbuilding orders
-- ---------------------------------------------------------------------------

-- 3A. Six RCN AOPS.
insert into public.pc_shipbuilding_orders(
  shipbuilding_order_id,
  contract_id,
  buyer_entity_id,
  builder_entity_id,
  shipyard_asset_id,
  order_date,
  announced_date,
  firm_quantity,
  option_quantity,
  vessel_type,
  contract_value,
  currency,
  first_delivery_date,
  final_delivery_date,
  status,
  source_url,
  primary_source_url,
  metadata,
  created_at,
  updated_at
)
select
  'SHIPORDER_CA_RCN_AOPS_6',
  'CONTRACT_CA_RCN_AOPS_BUILD',
  p.customer_entity_id,
  'COMP_IRVING',
  a.asset_id,
  '2014-12-23'::date,
  '2015-01-23'::date,
  6,
  0,
  'Harry DeWolf-class Arctic and Offshore Patrol Ship',
  2600000000,
  'CAD',
  '2020-07-31'::date,
  '2025-08-21'::date,
  'delivered',
  'https://www.canada.ca/en/department-national-defence/services/procurement/arctic-offshore-patrol-ships.html',
  'https://www.canada.ca/en/public-services-procurement/services/acquisitions/defence-marine/national-shipbuilding-strategy/projects/large-vessels/arctic-patrol-navy.html',
  jsonb_build_object(
    'materialisation','075',
    'programme','Royal Canadian Navy Arctic and Offshore Patrol Ships',
    'project_budget_cad_excluding_tax',4980000000,
    'contract_value_basis','construction contract, not total project acquisition budget'
  ),
  now(),
  now()
from public.pc_defence_programmes p
cross join lateral (
  select a1.asset_id
  from public.pc_assets a1
  where a1.asset_id='ASSET_STRAT_IRVING_HALIFAX_SHIPYARD'
     or public.pc_norm_identity_text(a1.name)=public.pc_norm_identity_text('Halifax Shipyard')
  order by case when a1.asset_id='ASSET_STRAT_IRVING_HALIFAX_SHIPYARD' then 0 else 1 end
  limit 1
) a
where public.pc_norm_identity_text(p.programme_name)=
      public.pc_norm_identity_text('Royal Canadian Navy Arctic and Offshore Patrol Ships')
on conflict(shipbuilding_order_id) do update set
  contract_id=excluded.contract_id,
  buyer_entity_id=excluded.buyer_entity_id,
  builder_entity_id=excluded.builder_entity_id,
  shipyard_asset_id=excluded.shipyard_asset_id,
  order_date=excluded.order_date,
  announced_date=excluded.announced_date,
  firm_quantity=excluded.firm_quantity,
  option_quantity=excluded.option_quantity,
  vessel_type=excluded.vessel_type,
  contract_value=excluded.contract_value,
  currency=excluded.currency,
  first_delivery_date=excluded.first_delivery_date,
  final_delivery_date=excluded.final_delivery_date,
  status=excluded.status,
  source_url=excluded.source_url,
  primary_source_url=excluded.primary_source_url,
  metadata=coalesce(public.pc_shipbuilding_orders.metadata,'{}'::jsonb)||excluded.metadata,
  updated_at=now();


-- 3B. Two CCG AOPS.
insert into public.pc_shipbuilding_orders(
  shipbuilding_order_id,
  contract_id,
  buyer_entity_id,
  builder_entity_id,
  shipyard_asset_id,
  order_date,
  announced_date,
  firm_quantity,
  option_quantity,
  vessel_type,
  contract_value,
  currency,
  first_delivery_date,
  final_delivery_date,
  status,
  source_url,
  primary_source_url,
  metadata,
  created_at,
  updated_at
)
select
  'SHIPORDER_CA_CCG_AOPS_2',
  'CONTRACT_CA_CCG_AOPS_7_8',
  p.customer_entity_id,
  'COMP_IRVING',
  a.asset_id,
  '2019-05-22'::date,
  '2019-05-22'::date,
  2,
  0,
  'Canadian Coast Guard Arctic and Offshore Patrol Ship',
  null,
  'CAD',
  null,
  null,
  'under_construction',
  'https://www.canada.ca/en/public-services-procurement/services/acquisitions/defence-marine/national-shipbuilding-strategy/projects/large-vessels/arctic-patrol-coast-guard.html',
  'https://www.canada.ca/en/public-services-procurement/services/acquisitions/defence-marine/national-shipbuilding-strategy/projects/large-vessels/arctic-patrol-coast-guard.html',
  jsonb_build_object(
    'materialisation','075',
    'programme','Canadian Coast Guard Arctic and Offshore Patrol Ships',
    'project_budget_cad',2100000000,
    'project_budget_is_not_contract_value',true,
    'aops_sequence',jsonb_build_array(7,8)
  ),
  now(),
  now()
from public.pc_defence_programmes p
cross join lateral (
  select a1.asset_id
  from public.pc_assets a1
  where a1.asset_id='ASSET_STRAT_IRVING_HALIFAX_SHIPYARD'
     or public.pc_norm_identity_text(a1.name)=public.pc_norm_identity_text('Halifax Shipyard')
  order by case when a1.asset_id='ASSET_STRAT_IRVING_HALIFAX_SHIPYARD' then 0 else 1 end
  limit 1
) a
where public.pc_norm_identity_text(p.programme_name)=
      public.pc_norm_identity_text('Canadian Coast Guard Arctic and Offshore Patrol Ships')
on conflict(shipbuilding_order_id) do update set
  contract_id=excluded.contract_id,
  buyer_entity_id=excluded.buyer_entity_id,
  builder_entity_id=excluded.builder_entity_id,
  shipyard_asset_id=excluded.shipyard_asset_id,
  order_date=excluded.order_date,
  announced_date=excluded.announced_date,
  firm_quantity=excluded.firm_quantity,
  option_quantity=excluded.option_quantity,
  vessel_type=excluded.vessel_type,
  currency=excluded.currency,
  status=excluded.status,
  source_url=excluded.source_url,
  primary_source_url=excluded.primary_source_url,
  metadata=coalesce(public.pc_shipbuilding_orders.metadata,'{}'::jsonb)||excluded.metadata,
  updated_at=now();


-- 3C. River-class Destroyer Batch 1.
insert into public.pc_shipbuilding_orders(
  shipbuilding_order_id,
  contract_id,
  buyer_entity_id,
  builder_entity_id,
  shipyard_asset_id,
  order_date,
  announced_date,
  firm_quantity,
  option_quantity,
  vessel_type,
  contract_value,
  currency,
  first_delivery_date,
  final_delivery_date,
  status,
  source_url,
  primary_source_url,
  metadata,
  created_at,
  updated_at
)
select
  'SHIPORDER_CA_RCD_BATCH1_3',
  'CONTRACT_CA_RCD_BATCH1_IMPL',
  p.customer_entity_id,
  'COMP_IRVING',
  a.asset_id,
  '2025-03-03'::date,
  '2025-03-08'::date,
  3,
  0,
  'River-class guided-missile destroyer',
  8000000000,
  'CAD',
  null,
  null,
  'under_construction',
  'https://www.canada.ca/en/department-national-defence/news/2025/03/government-of-canada-announces-contract-award-for-the-construction-of-the-river-class-destroyers-for-the-royal-canadian-navy.html',
  'https://www.canada.ca/en/public-services-procurement/services/acquisitions/defence-marine/national-shipbuilding-strategy/projects/large-vessels/river-class-destroyer.html',
  jsonb_build_object(
    'materialisation','075',
    'programme','River-class Destroyer Project',
    'batch',1,
    'batch_1_total_estimated_cost_cad_excluding_tax',22200000000,
    'implementation_contract_value_cad_including_tax',8000000000,
    'full_rate_production_started','2025-04-25',
    'first_ship_delivery_public_guidance','early 2030s'
  ),
  now(),
  now()
from public.pc_defence_programmes p
cross join lateral (
  select a1.asset_id
  from public.pc_assets a1
  where a1.asset_id='ASSET_STRAT_IRVING_HALIFAX_SHIPYARD'
     or public.pc_norm_identity_text(a1.name)=public.pc_norm_identity_text('Halifax Shipyard')
  order by case when a1.asset_id='ASSET_STRAT_IRVING_HALIFAX_SHIPYARD' then 0 else 1 end
  limit 1
) a
where public.pc_norm_identity_text(p.programme_name)=
      public.pc_norm_identity_text('River-class Destroyer Project')
on conflict(shipbuilding_order_id) do update set
  contract_id=excluded.contract_id,
  buyer_entity_id=excluded.buyer_entity_id,
  builder_entity_id=excluded.builder_entity_id,
  shipyard_asset_id=excluded.shipyard_asset_id,
  order_date=excluded.order_date,
  announced_date=excluded.announced_date,
  firm_quantity=excluded.firm_quantity,
  option_quantity=excluded.option_quantity,
  vessel_type=excluded.vessel_type,
  contract_value=excluded.contract_value,
  currency=excluded.currency,
  status=excluded.status,
  source_url=excluded.source_url,
  primary_source_url=excluded.primary_source_url,
  metadata=coalesce(public.pc_shipbuilding_orders.metadata,'{}'::jsonb)||excluded.metadata,
  updated_at=now();


-- ---------------------------------------------------------------------------
-- 4. Order units / hulls
-- ---------------------------------------------------------------------------

-- 4A. Six delivered RCN AOPS already materialised as canonical mobile assets in 074.
with units(
  shipbuilding_order_unit_id,unit_number,mobile_asset_id,vessel_name,status,delivery_date
) as (
  values
    ('SHIPUNIT_CA_RCN_AOPS_01',1,'MOBILE_CA_HMCS_HARRY_DEWOLF','HMCS Harry DeWolf','delivered','2020-07-31'::date),
    ('SHIPUNIT_CA_RCN_AOPS_02',2,'MOBILE_CA_HMCS_MARGARET_BROOKE','HMCS Margaret Brooke','delivered','2021-07-15'::date),
    ('SHIPUNIT_CA_RCN_AOPS_03',3,'MOBILE_CA_HMCS_MAX_BERNAYS','HMCS Max Bernays','delivered','2022-09-02'::date),
    ('SHIPUNIT_CA_RCN_AOPS_04',4,'MOBILE_CA_HMCS_WILLIAM_HALL','HMCS William Hall','delivered','2023-08-30'::date),
    ('SHIPUNIT_CA_RCN_AOPS_05',5,'MOBILE_CA_HMCS_FREDERICK_ROLETTE','HMCS Frédérick Rolette','delivered','2024-08-29'::date),
    ('SHIPUNIT_CA_RCN_AOPS_06',6,'MOBILE_CA_HMCS_ROBERT_HAMPTON_GRAY','HMCS Robert Hampton Gray','delivered','2025-08-21'::date)
)
insert into public.pc_shipbuilding_order_units(
  shipbuilding_order_unit_id,
  shipbuilding_order_id,
  unit_number,
  mobile_asset_id,
  hull_number,
  vessel_name,
  status,
  delivery_date,
  source_id,
  metadata
)
select
  u.shipbuilding_order_unit_id,
  'SHIPORDER_CA_RCN_AOPS_6',
  u.unit_number,
  u.mobile_asset_id,
  'AOPS '||u.unit_number::text,
  u.vessel_name,
  u.status,
  u.delivery_date,
  null,
  jsonb_build_object(
    'materialisation','075',
    'source_url','https://www.canada.ca/en/public-services-procurement/services/acquisitions/defence-marine/national-shipbuilding-strategy/projects/large-vessels/arctic-patrol-navy.html'
  )
from units u
where exists(select 1 from public.pc_mobile_assets m where m.mobile_asset_id=u.mobile_asset_id)
on conflict(shipbuilding_order_unit_id) do update set
  shipbuilding_order_id=excluded.shipbuilding_order_id,
  unit_number=excluded.unit_number,
  mobile_asset_id=excluded.mobile_asset_id,
  hull_number=excluded.hull_number,
  vessel_name=excluded.vessel_name,
  status=excluded.status,
  delivery_date=excluded.delivery_date,
  metadata=coalesce(public.pc_shipbuilding_order_units.metadata,'{}'::jsonb)||excluded.metadata;


-- 4B. CCG AOPS 7/8: canonical IDs confirmed in the live Irving dossier.
with units(
  shipbuilding_order_unit_id,unit_number,mobile_asset_id,hull_number,vessel_name,status,
  keel_laying_date,launch_date
) as (
  values
    ('SHIPUNIT_CA_CCG_AOPS_07',1,'MOBILE_FBBB0486AD609D1F','AOPS 7','CCGS Donjek','launched',null::date,'2026-04-29'::date),
    ('SHIPUNIT_CA_CCG_AOPS_08',2,'MOBILE_04A0BEF409ACAFA1','AOPS 8','CCGS Sermilik','under_construction','2025-11-06'::date,null::date)
)
insert into public.pc_shipbuilding_order_units(
  shipbuilding_order_unit_id,
  shipbuilding_order_id,
  unit_number,
  mobile_asset_id,
  hull_number,
  vessel_name,
  status,
  keel_laying_date,
  launch_date,
  source_id,
  metadata
)
select
  u.shipbuilding_order_unit_id,
  'SHIPORDER_CA_CCG_AOPS_2',
  u.unit_number,
  u.mobile_asset_id,
  u.hull_number,
  u.vessel_name,
  u.status,
  u.keel_laying_date,
  u.launch_date,
  null,
  jsonb_build_object(
    'materialisation','075',
    'source_url','https://www.canada.ca/en/public-services-procurement/services/acquisitions/defence-marine/national-shipbuilding-strategy/projects/large-vessels/arctic-patrol-coast-guard.html',
    'expected_delivery',case when u.unit_number=1 then 'Late 2026' else '2027' end
  )
from units u
where exists(select 1 from public.pc_mobile_assets m where m.mobile_asset_id=u.mobile_asset_id)
on conflict(shipbuilding_order_unit_id) do update set
  shipbuilding_order_id=excluded.shipbuilding_order_id,
  unit_number=excluded.unit_number,
  mobile_asset_id=excluded.mobile_asset_id,
  hull_number=excluded.hull_number,
  vessel_name=excluded.vessel_name,
  status=excluded.status,
  keel_laying_date=excluded.keel_laying_date,
  launch_date=excluded.launch_date,
  metadata=coalesce(public.pc_shipbuilding_order_units.metadata,'{}'::jsonb)||excluded.metadata;


-- 4C. River-class Destroyer Batch 1.
with units(
  shipbuilding_order_unit_id,unit_number,mobile_asset_id,vessel_name,status,keel_laying_date
) as (
  values
    ('SHIPUNIT_CA_RCD_B1_01',1,'MOBILE_CA_HMCS_FRASER_RCD','HMCS Fraser','under_construction','2026-06-12'::date),
    ('SHIPUNIT_CA_RCD_B1_02',2,'MOBILE_CA_HMCS_SAINT_LAURENT_RCD','HMCS Saint-Laurent','ordered',null::date),
    ('SHIPUNIT_CA_RCD_B1_03',3,'MOBILE_CA_HMCS_MACKENZIE_RCD','HMCS Mackenzie','ordered',null::date)
)
insert into public.pc_shipbuilding_order_units(
  shipbuilding_order_unit_id,
  shipbuilding_order_id,
  unit_number,
  mobile_asset_id,
  hull_number,
  vessel_name,
  status,
  keel_laying_date,
  source_id,
  metadata
)
select
  u.shipbuilding_order_unit_id,
  'SHIPORDER_CA_RCD_BATCH1_3',
  u.unit_number,
  u.mobile_asset_id,
  null,
  u.vessel_name,
  u.status,
  u.keel_laying_date,
  null,
  jsonb_build_object(
    'materialisation','075',
    'batch',1,
    'source_url','https://www.canada.ca/en/public-services-procurement/services/acquisitions/defence-marine/national-shipbuilding-strategy/projects/large-vessels/river-class-destroyer.html'
  )
from units u
where exists(select 1 from public.pc_mobile_assets m where m.mobile_asset_id=u.mobile_asset_id)
on conflict(shipbuilding_order_unit_id) do update set
  shipbuilding_order_id=excluded.shipbuilding_order_id,
  unit_number=excluded.unit_number,
  mobile_asset_id=excluded.mobile_asset_id,
  vessel_name=excluded.vessel_name,
  status=excluded.status,
  keel_laying_date=excluded.keel_laying_date,
  metadata=coalesce(public.pc_shipbuilding_order_units.metadata,'{}'::jsonb)||excluded.metadata;


-- ---------------------------------------------------------------------------
-- 5. Attach programme records to the new canonical contract/order objects
-- ---------------------------------------------------------------------------
update public.pc_defence_programmes
set
  contract_id='CONTRACT_CA_RCN_AOPS_BUILD',
  shipbuilding_order_id='SHIPORDER_CA_RCN_AOPS_6',
  updated_at=now(),
  metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object(
    'materialisation_075',true,
    'canonical_contract_id','CONTRACT_CA_RCN_AOPS_BUILD',
    'canonical_shipbuilding_order_id','SHIPORDER_CA_RCN_AOPS_6'
  )
where public.pc_norm_identity_text(programme_name)=
      public.pc_norm_identity_text('Royal Canadian Navy Arctic and Offshore Patrol Ships');

update public.pc_defence_programmes
set
  contract_id='CONTRACT_CA_CCG_AOPS_7_8',
  shipbuilding_order_id='SHIPORDER_CA_CCG_AOPS_2',
  firm_quantity=coalesce(firm_quantity,2),
  announced_date=coalesce(announced_date,'2019-05-22'::date),
  announced_value=coalesce(announced_value,2100000000),
  currency=coalesce(currency,'CAD'),
  updated_at=now(),
  metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object(
    'materialisation_075',true,
    'canonical_contract_id','CONTRACT_CA_CCG_AOPS_7_8',
    'canonical_shipbuilding_order_id','SHIPORDER_CA_CCG_AOPS_2',
    'announced_value_basis','project budget, not contract value'
  )
where public.pc_norm_identity_text(programme_name)=
      public.pc_norm_identity_text('Canadian Coast Guard Arctic and Offshore Patrol Ships');

update public.pc_defence_programmes
set
  contract_id='CONTRACT_CA_RCD_BATCH1_IMPL',
  shipbuilding_order_id='SHIPORDER_CA_RCD_BATCH1_3',
  updated_at=now(),
  metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object(
    'materialisation_075',true,
    'canonical_contract_id','CONTRACT_CA_RCD_BATCH1_IMPL',
    'canonical_shipbuilding_order_id','SHIPORDER_CA_RCD_BATCH1_3'
  )
where public.pc_norm_identity_text(programme_name)=
      public.pc_norm_identity_text('River-class Destroyer Project');


-- ---------------------------------------------------------------------------
-- 6. Attach existing production tasks to orders / order units
-- ---------------------------------------------------------------------------
update public.pc_shipbuilding_production_tasks t
set
  shipbuilding_order_id='SHIPORDER_CA_CCG_AOPS_2',
  shipbuilding_order_unit_id=case t.metadata->>'mobile_asset_id'
    when 'MOBILE_FBBB0486AD609D1F' then 'SHIPUNIT_CA_CCG_AOPS_07'
    when 'MOBILE_04A0BEF409ACAFA1' then 'SHIPUNIT_CA_CCG_AOPS_08'
    else t.shipbuilding_order_unit_id
  end,
  updated_at=now(),
  metadata=coalesce(t.metadata,'{}'::jsonb)||jsonb_build_object('materialisation_075_linked',true)
where t.builder_entity_id='COMP_IRVING'
  and t.metadata->>'mobile_asset_id' in ('MOBILE_FBBB0486AD609D1F','MOBILE_04A0BEF409ACAFA1');

update public.pc_shipbuilding_production_tasks t
set
  shipbuilding_order_id='SHIPORDER_CA_RCD_BATCH1_3',
  shipbuilding_order_unit_id='SHIPUNIT_CA_RCD_B1_01',
  updated_at=now(),
  metadata=coalesce(t.metadata,'{}'::jsonb)||jsonb_build_object('materialisation_075_linked',true)
where t.builder_entity_id='COMP_IRVING'
  and t.metadata->>'mobile_asset_id'='MOBILE_CA_HMCS_FRASER_RCD';


-- ---------------------------------------------------------------------------
-- 7. Contract links: contracts -> programmes and orders
-- ---------------------------------------------------------------------------
with programme_map(contract_id,programme_name,order_id) as (
  values
    ('CONTRACT_CA_RCN_AOPS_BUILD','Royal Canadian Navy Arctic and Offshore Patrol Ships','SHIPORDER_CA_RCN_AOPS_6'),
    ('CONTRACT_CA_CCG_AOPS_7_8','Canadian Coast Guard Arctic and Offshore Patrol Ships','SHIPORDER_CA_CCG_AOPS_2'),
    ('CONTRACT_CA_RCD_BATCH1_IMPL','River-class Destroyer Project','SHIPORDER_CA_RCD_BATCH1_3')
),
links as (
  select
    m.contract_id,
    'programme'::text as linked_type,
    p.defence_programme_id::text as linked_id,
    'governs_programme'::text as relationship_type
  from programme_map m
  join public.pc_defence_programmes p
    on public.pc_norm_identity_text(p.programme_name)=public.pc_norm_identity_text(m.programme_name)

  union all

  select
    m.contract_id,
    'shipbuilding_order',
    m.order_id,
    'implemented_by_order'
  from programme_map m
)
insert into public.pc_contract_links(
  contract_link_id,
  contract_id,
  linked_type,
  linked_id,
  relationship_type,
  source_id,
  metadata
)
select
  gen_random_uuid(),
  l.contract_id,
  l.linked_type,
  l.linked_id,
  l.relationship_type,
  null,
  jsonb_build_object('materialisation','075')
from links l
where not exists (
  select 1
  from public.pc_contract_links x
  where x.contract_id=l.contract_id
    and lower(coalesce(x.linked_type,''))=lower(l.linked_type)
    and x.linked_id=l.linked_id
    and lower(coalesce(x.relationship_type,''))=lower(l.relationship_type)
);


-- ---------------------------------------------------------------------------
-- 8. Refresh shared graph/read models
-- ---------------------------------------------------------------------------
select public.pc_normalize_canonical_relationships();
select public.pc_refresh_terminal_indexes();

do $$
begin
  if to_regprocedure('public.pc_refresh_terminal_industrial_links()') is not null then
    perform public.pc_refresh_terminal_industrial_links();
  end if;
end $$;

commit;


-- ---------------------------------------------------------------------------
-- Validation
-- ---------------------------------------------------------------------------

-- 3 canonical Irving NSS contracts:
select
  contract_id,contract_name,status,reported_value,currency,quantity,quantity_unit
from public.pc_contracts
where contract_id in (
  'CONTRACT_CA_RCN_AOPS_BUILD',
  'CONTRACT_CA_CCG_AOPS_7_8',
  'CONTRACT_CA_RCD_BATCH1_IMPL'
)
order by contract_id;

-- 3 canonical orders with expected unit counts 6 / 2 / 3:
select
  o.shipbuilding_order_id,
  o.contract_id,
  o.firm_quantity,
  o.status,
  count(u.shipbuilding_order_unit_id) as unit_count
from public.pc_shipbuilding_orders o
left join public.pc_shipbuilding_order_units u
  on u.shipbuilding_order_id=o.shipbuilding_order_id
where o.shipbuilding_order_id in (
  'SHIPORDER_CA_RCN_AOPS_6',
  'SHIPORDER_CA_CCG_AOPS_2',
  'SHIPORDER_CA_RCD_BATCH1_3'
)
group by o.shipbuilding_order_id,o.contract_id,o.firm_quantity,o.status
order by o.shipbuilding_order_id;

-- Programme FK completion:
select
  programme_name,contract_id,shipbuilding_order_id,firm_quantity,announced_value,currency
from public.pc_defence_programmes
where public.pc_norm_identity_text(programme_name) in (
  public.pc_norm_identity_text('Royal Canadian Navy Arctic and Offshore Patrol Ships'),
  public.pc_norm_identity_text('Canadian Coast Guard Arctic and Offshore Patrol Ships'),
  public.pc_norm_identity_text('River-class Destroyer Project')
)
order by programme_name;

-- Production-task linkage for CCG AOPS and HMCS Fraser:
select
  production_task_id,
  metadata->>'mobile_asset_name' as mobile_asset_name,
  shipbuilding_order_id,
  shipbuilding_order_unit_id
from public.pc_shipbuilding_production_tasks
where builder_entity_id='COMP_IRVING'
  and metadata->>'mobile_asset_id' in (
    'MOBILE_FBBB0486AD609D1F',
    'MOBILE_04A0BEF409ACAFA1',
    'MOBILE_CA_HMCS_FRASER_RCD'
  )
order by mobile_asset_name;

-- Full Irving dossier after completion:
-- select public.pc_strategic_entity_dossier('COMP_IRVING')->'counts';
-- select * from public.pc_model_audit_entity('COMP_IRVING');
