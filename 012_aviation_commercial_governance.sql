-- Power & Corridors Trade System
-- 012_aviation_commercial_governance.sql
-- Layer 2: airport facilities, governance and commercial/cargo integration
-- Requires: 011_aviation_airport_expansion.sql

begin;

create extension if not exists pgcrypto;

-- ============================================================================
-- 1. AIRPORT FACILITIES
-- Facility identity is a canonical pc_assets row. This table extends it.
-- Examples: cargo terminal, cargo village, bonded warehouse, MRO hangar,
-- fuel farm, FBO, integrator facility, express hub, free-zone logistics area.
-- ============================================================================

create table if not exists pc_airport_facilities (
  facility_asset_id text primary key references pc_assets(asset_id) on delete cascade,
  airport_id text not null references pc_assets(asset_id) on delete cascade,

  facility_type text not null,
  facility_name text,
  operator_entity_id text references pc_entities(entity_id),
  owner_entity_id text references pc_entities(entity_id),

  airside_access boolean,
  landside_access boolean,
  bonded boolean,
  customs_on_site boolean,
  free_zone boolean,
  cold_chain boolean,
  pharma_capable boolean,
  dangerous_goods boolean,
  live_animals boolean,
  perishables boolean,
  valuable_cargo boolean,
  e_commerce boolean,
  express_integrator boolean,

  warehouse_area_sqm numeric,
  land_area_sqm numeric,
  annual_capacity_tonnes numeric,
  apron_stands integer,
  dock_doors integer,

  status text not null default 'active',
  opening_date date,
  planned_completion date,

  source_id text references pc_sources(source_id),
  last_verified date,
  metadata jsonb not null default '{}'::jsonb
);

create index if not exists idx_pc_airport_facilities_airport
  on pc_airport_facilities(airport_id,facility_type);
create index if not exists idx_pc_airport_facilities_operator
  on pc_airport_facilities(operator_entity_id,facility_type);
create index if not exists idx_pc_airport_facilities_status
  on pc_airport_facilities(status);

-- ============================================================================
-- 2. PROVIDER ROLE DETAIL
-- Add optional facility link + quantitative handling information if 011 table
-- already exists.
-- ============================================================================

alter table pc_airport_service_providers
  add column if not exists handling_capacity_tonnes numeric,
  add column if not exists annual_volume_tonnes numeric,
  add column if not exists terminal_area_sqm numeric,
  add column if not exists service_24h boolean,
  add column if not exists cargo_categories text[];

-- ============================================================================
-- 3. GOVERNANCE DETAIL
-- ============================================================================

alter table pc_airport_governance
  add column if not exists governance_level text,
  add column if not exists legal_basis text,
  add column if not exists jurisdiction text;

-- ============================================================================
-- 4. CARGO / GOVERNANCE VIEWS
-- ============================================================================

create or replace view pc_trade_airport_facilities as
select
  f.facility_asset_id,
  fa.name as facility_name,
  f.airport_id,
  aa.name as airport_name,
  aa.country,
  aa.region_city,
  f.facility_type,
  f.operator_entity_id,
  op.name as operator_name,
  f.owner_entity_id,
  ow.name as owner_name,
  f.airside_access,
  f.bonded,
  f.customs_on_site,
  f.free_zone,
  f.cold_chain,
  f.pharma_capable,
  f.dangerous_goods,
  f.live_animals,
  f.perishables,
  f.valuable_cargo,
  f.e_commerce,
  f.express_integrator,
  f.warehouse_area_sqm,
  f.land_area_sqm,
  f.annual_capacity_tonnes,
  f.status,
  f.last_verified
from pc_airport_facilities f
join pc_assets fa on fa.asset_id=f.facility_asset_id
join pc_assets aa on aa.asset_id=f.airport_id
left join pc_entities op on op.entity_id=f.operator_entity_id
left join pc_entities ow on ow.entity_id=f.owner_entity_id
where coalesce(fa.record_status,'provisional') <> 'rejected';

create or replace view pc_trade_airport_governance as
select
  g.governance_id,
  g.airport_id,
  a.name as airport_name,
  a.country,
  g.entity_id,
  e.name as entity_name,
  g.role_type,
  g.ownership_percent,
  g.operating_control,
  g.concession_name,
  g.governance_level,
  g.jurisdiction,
  g.valid_from,
  g.valid_to,
  g.status,
  g.confidence
from pc_airport_governance g
join pc_assets a on a.asset_id=g.airport_id
join pc_entities e on e.entity_id=g.entity_id
where coalesce(a.record_status,'provisional') <> 'rejected';

create or replace view pc_trade_airport_service_network as
select
  s.provider_link_id,
  s.airport_id,
  a.name as airport_name,
  a.country,
  s.provider_entity_id,
  e.name as provider_name,
  s.provider_type,
  s.facility_asset_id,
  f.name as facility_name,
  s.service_scope,
  s.dedicated_facility,
  s.handling_capacity_tonnes,
  s.annual_volume_tonnes,
  s.terminal_area_sqm,
  s.service_24h,
  s.cargo_categories,
  s.status,
  s.valid_from,
  s.valid_to,
  s.confidence
from pc_airport_service_providers s
join pc_assets a on a.asset_id=s.airport_id
join pc_entities e on e.entity_id=s.provider_entity_id
left join pc_assets f on f.asset_id=s.facility_asset_id
where coalesce(a.record_status,'provisional') <> 'rejected';

-- ============================================================================
-- 5. METADATA REGISTRY
-- ============================================================================

insert into pc_meta_entity_types(
  entity_type,table_name,primary_key_column,display_name_column,id_prefix,
  canonical,active,allow_insert,allow_update,description
)
values
  ('airport_facility','pc_airport_facilities','facility_asset_id','facility_name','AIRFAC',false,true,true,true,
   'Airport cargo/logistics/MRO/fuel/FBO/free-zone facility extension for canonical pc_assets records')
on conflict (entity_type) do update set
  table_name=excluded.table_name,
  primary_key_column=excluded.primary_key_column,
  display_name_column=excluded.display_name_column,
  id_prefix=excluded.id_prefix,
  canonical=false,
  active=true,
  allow_insert=true,
  allow_update=true,
  description=excluded.description,
  updated_at=now();

select pc_refresh_model_registry();

insert into pc_meta_match_rules(
  entity_type,priority,rule_name,match_type,source_column,canonical_column,
  comparison_method,minimum_score,required
)
values
  ('airport_facility',10,'AIRPORT_FACILITY_ASSET_ID_EXACT','FIELD_EXACT','facility_asset_id','facility_asset_id','exact',1.0,true)
on conflict (entity_type,priority,rule_name) do update set
  active=true,
  source_column=excluded.source_column,
  canonical_column=excluded.canonical_column,
  comparison_method=excluded.comparison_method,
  minimum_score=excluded.minimum_score,
  required=excluded.required;

-- Generic graph types for facility precision.
insert into pc_meta_relationship_types(
  relationship_type,from_entity_type,to_entity_type,relationship_table,
  from_key_column,to_key_column,relationship_type_column,
  inverse_relationship_type,cardinality,active,description
)
values
  ('located_at','asset','asset','pc_relationships','source_id','target_id','relationship_type','hosts','many_to_one',true,'Facility is located at an airport'),
  ('operates_facility','entity','asset','pc_relationships','source_id','target_id','relationship_type','facility_operated_by','one_to_many',true,'Company operates an airport facility'),
  ('owns_facility','entity','asset','pc_relationships','source_id','target_id','relationship_type','facility_owned_by','one_to_many',true,'Company/government owns an airport facility')
on conflict (relationship_type) do update set
  active=true,
  description=excluded.description,
  inverse_relationship_type=excluded.inverse_relationship_type,
  cardinality=excluded.cardinality;

-- ============================================================================
-- 6. RLS
-- ============================================================================

alter table pc_airport_facilities enable row level security;
drop policy if exists pc_airport_facilities_read on pc_airport_facilities;
create policy pc_airport_facilities_read
on pc_airport_facilities for select to authenticated using (true);

comment on table pc_airport_facilities is
  'Airport cargo, logistics, MRO, fuel, FBO and free-zone facilities keyed to canonical pc_assets child assets.';

commit;
