-- Power & Corridors Trade System
-- 011_aviation_airport_expansion.sql
-- Aviation / airport infrastructure expansion for Trade + Intelligence
-- Additive migration over 001_core_platform.sql ... 010_metadata_driven_staging.sql
--
-- Canonical rule:
--   * Airport identity lives once in pc_assets (asset_type='airport' / 'air_base' / 'joint_use_airport').
--   * Runways are also canonical pc_assets rows (asset_type='airport_runway') so events can link to a runway directly.
--   * The tables below extend those canonical records; they do not create a second airport identity store.

begin;

create extension if not exists pgcrypto;

-- ============================================================================
-- 1. AIRPORT PROFILE
-- ============================================================================

create table if not exists pc_airports (
  asset_id text primary key references pc_assets(asset_id) on delete cascade,

  -- External identifiers / source keys
  ourairports_id bigint,
  ourairports_ident text,
  icao_code text,
  iata_code text,
  gps_code text,
  local_code text,

  -- Classification
  airport_type text,              -- large_airport / medium_airport / small_airport / heliport / seaplane_base / etc.
  use_type text,                  -- civil / military / joint_use / private / government / other
  scheduled_service boolean,
  passenger_enabled boolean,
  cargo_enabled boolean,
  customs_available boolean,
  border_control_available boolean,
  operating_24h boolean,
  slot_coordinated boolean,
  curfew_applies boolean,

  -- Physical profile
  elevation_ft numeric,
  elevation_m numeric,
  timezone text,
  runway_count integer,
  longest_runway_m numeric,

  -- Current governance pointers (history belongs in pc_relationships / pc_airport_governance)
  owner_entity_id text references pc_entities(entity_id),
  operator_entity_id text references pc_entities(entity_id),
  airport_authority_entity_id text references pc_entities(entity_id),
  regulator_entity_id text references pc_entities(entity_id),
  air_navigation_provider_entity_id text references pc_entities(entity_id),
  military_operator_entity_id text references pc_entities(entity_id),

  -- Operating / commercial profile
  primary_role text,
  operational_status text,
  security_classification text,
  home_link text,
  last_verified date,
  source_id text references pc_sources(source_id),
  metadata jsonb not null default '{}'::jsonb
);

create index if not exists idx_pc_airports_icao on pc_airports(icao_code) where icao_code is not null;
create index if not exists idx_pc_airports_iata on pc_airports(iata_code) where iata_code is not null;
create index if not exists idx_pc_airports_ident on pc_airports(ourairports_ident) where ourairports_ident is not null;
create index if not exists idx_pc_airports_type on pc_airports(airport_type,use_type);
create index if not exists idx_pc_airports_cargo on pc_airports(cargo_enabled) where cargo_enabled=true;
create index if not exists idx_pc_airports_operator on pc_airports(operator_entity_id);

-- ============================================================================
-- 2. RUNWAYS
-- Runways are canonical fixed assets so an event can affect a runway without
-- incorrectly marking the entire airport closed.
-- ============================================================================

create table if not exists pc_airport_runways (
  runway_asset_id text primary key references pc_assets(asset_id) on delete cascade,
  airport_id text not null references pc_assets(asset_id) on delete cascade,
  ourairports_runway_id bigint,

  runway_ident text,              -- e.g. 13/31 or 06/24
  le_ident text,
  he_ident text,

  length_ft numeric,
  length_m numeric,
  width_ft numeric,
  width_m numeric,
  surface text,
  lighted boolean,
  closed boolean,

  le_latitude numeric,
  le_longitude numeric,
  le_elevation_ft numeric,
  le_heading_deg_true numeric,
  le_displaced_threshold_ft numeric,

  he_latitude numeric,
  he_longitude numeric,
  he_elevation_ft numeric,
  he_heading_deg_true numeric,
  he_displaced_threshold_ft numeric,

  -- Enrichment fields not consistently available from OurAirports
  le_ils_category text,
  he_ils_category text,
  le_approach_capabilities text[],
  he_approach_capabilities text[],
  declared_distances jsonb not null default '{}'::jsonb,
  pavement_classification text,
  operational_status text,

  source_id text references pc_sources(source_id),
  last_verified date,
  metadata jsonb not null default '{}'::jsonb,

  unique(airport_id, runway_ident)
);

create index if not exists idx_pc_airport_runways_airport on pc_airport_runways(airport_id);
create index if not exists idx_pc_airport_runways_length on pc_airport_runways(length_m desc);
create index if not exists idx_pc_airport_runways_status on pc_airport_runways(closed,operational_status);

-- ============================================================================
-- 3. AIRPORT CAPABILITY PROFILE
-- One current capability row per airport; historical changes can be observed
-- through pc_observations and events.
-- ============================================================================

create table if not exists pc_airport_capabilities (
  airport_id text primary key references pc_assets(asset_id) on delete cascade,

  dedicated_cargo_terminal boolean,
  freighter_capable boolean,
  widebody_freighter_capable boolean,
  cargo_apron boolean,
  bonded_warehouse boolean,
  free_zone_linked boolean,
  cold_chain boolean,
  pharma_handling boolean,
  dangerous_goods boolean,
  live_animals boolean,
  perishables boolean,
  valuable_cargo boolean,
  e_commerce boolean,

  fuel_available boolean,
  mro_available boolean,
  fbo_available boolean,
  customs_clearance boolean,
  border_control boolean,

  road_connected boolean,
  rail_connected boolean,
  nearest_port_id text references pc_assets(asset_id),
  linked_logistics_zone_id text references pc_assets(asset_id),

  cargo_terminal_count integer,
  warehouse_area_sqm numeric,
  freighter_stand_count integer,

  source_id text references pc_sources(source_id),
  last_verified date,
  metadata jsonb not null default '{}'::jsonb
);

-- ============================================================================
-- 4. AIRPORT SERVICE PROVIDERS
-- Cargo airlines, ground handlers, fuel, MRO, FBO, catering, security and
-- logistics providers. Company identity remains pc_entities.
-- ============================================================================

create table if not exists pc_airport_service_providers (
  provider_link_id uuid primary key default gen_random_uuid(),
  airport_id text not null references pc_assets(asset_id) on delete cascade,
  provider_entity_id text not null references pc_entities(entity_id) on delete cascade,
  provider_type text not null,     -- cargo_airline / airline / ground_handler / fuel / mro / fbo / catering / security / logistics / warehouse / customs_broker
  facility_asset_id text references pc_assets(asset_id) on delete set null,
  service_scope text,
  dedicated_facility boolean,
  status text not null default 'active',
  valid_from date,
  valid_to date,
  source_id text references pc_sources(source_id),
  confidence text,
  metadata jsonb not null default '{}'::jsonb,
  unique(airport_id,provider_entity_id,provider_type,facility_asset_id)
);

create index if not exists idx_pc_airport_providers_airport on pc_airport_service_providers(airport_id,provider_type);
create index if not exists idx_pc_airport_providers_entity on pc_airport_service_providers(provider_entity_id,provider_type);

-- ============================================================================
-- 5. GOVERNANCE / CONTROL HISTORY
-- Current pointers can live in pc_airports; this table preserves role history.
-- Generic pc_relationships should also be created for Company/Assets display.
-- ============================================================================

create table if not exists pc_airport_governance (
  governance_id uuid primary key default gen_random_uuid(),
  airport_id text not null references pc_assets(asset_id) on delete cascade,
  entity_id text not null references pc_entities(entity_id) on delete cascade,
  role_type text not null,         -- owner / operator / airport_authority / regulator / air_navigation_provider / military_operator / concessionaire
  ownership_percent numeric,
  operating_control text,
  concession_name text,
  valid_from date,
  valid_to date,
  status text not null default 'active',
  source_id text references pc_sources(source_id),
  confidence text,
  metadata jsonb not null default '{}'::jsonb,
  unique(airport_id,entity_id,role_type,valid_from)
);

create index if not exists idx_pc_airport_governance_airport on pc_airport_governance(airport_id,role_type);
create index if not exists idx_pc_airport_governance_entity on pc_airport_governance(entity_id,role_type);

-- ============================================================================
-- 6. COMMUNICATION FREQUENCIES
-- ============================================================================

create table if not exists pc_airport_frequencies (
  frequency_id text primary key,
  airport_id text not null references pc_assets(asset_id) on delete cascade,
  external_frequency_id bigint,
  frequency_type text,
  description text,
  frequency_mhz numeric,
  active boolean not null default true,
  source_id text references pc_sources(source_id),
  last_verified date,
  metadata jsonb not null default '{}'::jsonb
);

create index if not exists idx_pc_airport_frequency_airport on pc_airport_frequencies(airport_id,frequency_type);

-- ============================================================================
-- 7. AIRPORT METRICS / THROUGHPUT
-- Generic metric design supports cargo, passengers, movements, freighter calls,
-- capacity, congestion, delays and other operational series.
-- ============================================================================

create table if not exists pc_airport_metrics (
  airport_metric_id uuid primary key default gen_random_uuid(),
  airport_id text not null references pc_assets(asset_id) on delete cascade,
  observation_date date,
  period_start date,
  period_end date,
  frequency text,
  metric_name text not null,
  metric_value numeric,
  metric_unit text,
  cargo_type text,
  source_id text references pc_sources(source_id),
  observation_id uuid references pc_observations(observation_id),
  confidence text,
  methodology text,
  metadata jsonb not null default '{}'::jsonb,
  unique(airport_id,period_start,period_end,metric_name,cargo_type,source_id)
);

create index if not exists idx_pc_airport_metrics_airport on pc_airport_metrics(airport_id,period_end desc);
create index if not exists idx_pc_airport_metrics_name on pc_airport_metrics(metric_name,period_end desc);

-- ============================================================================
-- 8. OPERATIONAL STATUS / DISRUPTIONS
-- Lets Intelligence distinguish "airport open, runway 13/31 closed" from a
-- full airport closure.
-- ============================================================================

create table if not exists pc_airport_operational_status (
  status_id uuid primary key default gen_random_uuid(),
  subject_asset_id text not null references pc_assets(asset_id) on delete cascade,
  airport_id text references pc_assets(asset_id) on delete cascade,
  status_type text not null,       -- airport_status / runway_status / cargo_status / airspace_restriction / fuel_constraint / security_posture
  status_value text not null,      -- open / closed / restricted / partial / diverted / suspended / degraded
  effective_from timestamptz,
  effective_to timestamptz,
  reason text,
  event_id text references pc_events(event_id) on delete set null,
  source_id text references pc_sources(source_id),
  confidence text,
  metadata jsonb not null default '{}'::jsonb
);

create index if not exists idx_pc_airport_status_subject on pc_airport_operational_status(subject_asset_id,effective_from desc);
create index if not exists idx_pc_airport_status_airport on pc_airport_operational_status(airport_id,effective_from desc);

-- ============================================================================
-- 9. CLIENT / ADMIN VIEWS
-- ============================================================================

create or replace view pc_trade_airports as
select
  a.asset_id,
  a.name,
  a.asset_type,
  a.subtype,
  a.country,
  a.region_city,
  a.latitude,
  a.longitude,
  p.icao_code,
  p.iata_code,
  p.ourairports_ident,
  p.airport_type,
  p.use_type,
  p.scheduled_service,
  p.elevation_ft,
  p.elevation_m,
  p.passenger_enabled,
  p.cargo_enabled,
  p.customs_available,
  p.operating_24h,
  p.runway_count,
  p.longest_runway_m,
  p.owner_entity_id,
  p.operator_entity_id,
  p.airport_authority_entity_id,
  p.regulator_entity_id,
  p.air_navigation_provider_entity_id,
  p.military_operator_entity_id,
  p.primary_role,
  p.operational_status,
  p.last_verified
from pc_assets a
join pc_airports p on p.asset_id=a.asset_id
where coalesce(a.record_status,'provisional') <> 'rejected';

create or replace view pc_trade_airport_runways as
select
  r.runway_asset_id,
  ra.name as runway_name,
  r.airport_id,
  aa.name as airport_name,
  aa.country,
  aa.region_city,
  r.runway_ident,
  r.length_m,
  r.width_m,
  r.surface,
  r.lighted,
  r.closed,
  r.le_ident,
  r.he_ident,
  r.le_heading_deg_true,
  r.he_heading_deg_true,
  r.le_ils_category,
  r.he_ils_category,
  r.operational_status,
  r.last_verified
from pc_airport_runways r
join pc_assets ra on ra.asset_id=r.runway_asset_id
join pc_assets aa on aa.asset_id=r.airport_id
where coalesce(ra.record_status,'provisional') <> 'rejected';

create or replace view pc_trade_airport_cargo as
select
  a.asset_id,
  a.name,
  a.country,
  a.region_city,
  p.icao_code,
  p.iata_code,
  p.cargo_enabled,
  c.dedicated_cargo_terminal,
  c.freighter_capable,
  c.widebody_freighter_capable,
  c.bonded_warehouse,
  c.free_zone_linked,
  c.cold_chain,
  c.pharma_handling,
  c.dangerous_goods,
  c.perishables,
  c.e_commerce,
  c.cargo_terminal_count,
  c.warehouse_area_sqm,
  c.freighter_stand_count
from pc_assets a
join pc_airports p on p.asset_id=a.asset_id
left join pc_airport_capabilities c on c.airport_id=a.asset_id
where coalesce(a.record_status,'provisional') <> 'rejected';

-- ============================================================================
-- 10. IDENTIFIER BACKFILL
-- External identifiers resolve to the canonical pc_assets id.
-- ============================================================================

insert into pc_entity_identifiers(
  entity_type,entity_id,identifier_type,identifier_value,normalized_value,
  is_primary,source_id,confidence
)
select 'asset',asset_id,'ICAO',icao_code,pc_normalize_identifier('ICAO',icao_code),true,source_id,1.0
from pc_airports
where pc_normalize_identifier('ICAO',icao_code) is not null
on conflict (entity_type,identifier_type,normalized_value) do update set
  entity_id=excluded.entity_id,
  identifier_value=excluded.identifier_value,
  source_id=coalesce(excluded.source_id,pc_entity_identifiers.source_id),
  confidence=greatest(coalesce(pc_entity_identifiers.confidence,0),coalesce(excluded.confidence,0));

insert into pc_entity_identifiers(
  entity_type,entity_id,identifier_type,identifier_value,normalized_value,
  is_primary,source_id,confidence
)
select 'asset',asset_id,'IATA',iata_code,pc_normalize_identifier('IATA',iata_code),false,source_id,1.0
from pc_airports
where pc_normalize_identifier('IATA',iata_code) is not null
on conflict (entity_type,identifier_type,normalized_value) do update set
  entity_id=excluded.entity_id,
  identifier_value=excluded.identifier_value,
  source_id=coalesce(excluded.source_id,pc_entity_identifiers.source_id),
  confidence=greatest(coalesce(pc_entity_identifiers.confidence,0),coalesce(excluded.confidence,0));

insert into pc_entity_identifiers(
  entity_type,entity_id,identifier_type,identifier_value,normalized_value,
  is_primary,source_id,confidence
)
select 'asset',asset_id,'OURAIRPORTS_IDENT',ourairports_ident,pc_normalize_identifier('OURAIRPORTS_IDENT',ourairports_ident),false,source_id,1.0
from pc_airports
where pc_normalize_identifier('OURAIRPORTS_IDENT',ourairports_ident) is not null
on conflict (entity_type,identifier_type,normalized_value) do update set
  entity_id=excluded.entity_id,
  identifier_value=excluded.identifier_value,
  source_id=coalesce(excluded.source_id,pc_entity_identifiers.source_id),
  confidence=greatest(coalesce(pc_entity_identifiers.confidence,0),coalesce(excluded.confidence,0));

-- ============================================================================
-- 11. METADATA-DRIVEN STAGING REGISTRY
-- Extension tables are non-canonical profiles: canonical identity still lives
-- in pc_assets / pc_entities.
-- ============================================================================

insert into pc_meta_entity_types(
  entity_type,table_name,primary_key_column,display_name_column,id_prefix,
  canonical,active,allow_insert,allow_update,description
)
values
  ('airport_profile','pc_airports','asset_id',null,'AIRPORT',false,true,true,true,
   'Aviation profile extension for a canonical airport/air-base asset'),
  ('airport_runway_profile','pc_airport_runways','runway_asset_id',null,'RUNWAY',false,true,true,true,
   'Runway extension for a canonical airport_runway asset'),
  ('airport_capability','pc_airport_capabilities','airport_id',null,'AIRCAP',false,true,true,true,
   'Current cargo/handling/connectivity capability profile for an airport'),
  ('airport_frequency','pc_airport_frequencies','frequency_id',null,'AIRFREQ',false,true,true,true,
   'Airport communication frequency record'),
  ('airport_metric','pc_airport_metrics','airport_metric_id',null,'AIRMETRIC',false,true,true,true,
   'Airport throughput/capacity/performance observation'),
  ('airport_service_provider','pc_airport_service_providers','provider_link_id',null,'AIRPROV',false,true,true,true,
   'Airport service-provider link with aviation-specific attributes'),
  ('airport_governance','pc_airport_governance','governance_id',null,'AIRGOV',false,true,true,true,
   'Airport governance/control history'),
  ('airport_operational_status','pc_airport_operational_status','status_id',null,'AIRSTAT',false,true,true,true,
   'Airport/runway/cargo operational status observation')
on conflict (entity_type) do update set
  table_name=excluded.table_name,
  primary_key_column=excluded.primary_key_column,
  display_name_column=excluded.display_name_column,
  id_prefix=excluded.id_prefix,
  canonical=excluded.canonical,
  active=true,
  allow_insert=true,
  allow_update=true,
  description=excluded.description,
  updated_at=now();

select pc_refresh_model_registry();

-- Staging profiles must match their parent canonical asset by exact id.
insert into pc_meta_match_rules(
  entity_type,priority,rule_name,match_type,source_column,canonical_column,
  comparison_method,minimum_score,required
)
values
  ('airport_profile',10,'AIRPORT_ASSET_ID_EXACT','FIELD_EXACT','asset_id','asset_id','exact',1.0,true),
  ('airport_runway_profile',10,'RUNWAY_ASSET_ID_EXACT','FIELD_EXACT','runway_asset_id','runway_asset_id','exact',1.0,true),
  ('airport_capability',10,'AIRPORT_CAPABILITY_ID_EXACT','FIELD_EXACT','airport_id','airport_id','exact',1.0,true),
  ('airport_frequency',10,'AIRPORT_FREQUENCY_ID_EXACT','FIELD_EXACT','frequency_id','frequency_id','exact',1.0,true)
on conflict (entity_type,priority,rule_name) do update set
  match_type=excluded.match_type,
  source_column=excluded.source_column,
  canonical_column=excluded.canonical_column,
  comparison_method=excluded.comparison_method,
  minimum_score=excluded.minimum_score,
  required=excluded.required,
  active=true;

-- Generic graph relationships used by Companies, Assets, Trade and Intelligence.
insert into pc_meta_relationship_types(
  relationship_type,from_entity_type,to_entity_type,relationship_table,
  from_key_column,to_key_column,relationship_type_column,
  inverse_relationship_type,cardinality,active,description
)
values
  ('part_of','asset','asset','pc_relationships','source_id','target_id','relationship_type','contains','many_to_one',true,'Child runway/cargo/facility asset belongs to an airport'),
  ('owns','entity','asset','pc_relationships','source_id','target_id','relationship_type','owned_by','one_to_many',true,'Entity owns airport or airport facility'),
  ('operates','entity','asset','pc_relationships','source_id','target_id','relationship_type','operated_by','one_to_many',true,'Entity operates airport or airport facility'),
  ('governs','entity','asset','pc_relationships','source_id','target_id','relationship_type','governed_by','one_to_many',true,'Airport authority/government entity governs airport'),
  ('regulates','entity','asset','pc_relationships','source_id','target_id','relationship_type','regulated_by','one_to_many',true,'Civil aviation regulator regulates airport'),
  ('provides_air_navigation','entity','asset','pc_relationships','source_id','target_id','relationship_type','air_navigation_by','one_to_many',true,'ANSP provides air navigation services'),
  ('military_operates','entity','asset','pc_relationships','source_id','target_id','relationship_type','military_operated_by','one_to_many',true,'Military entity operates air base or joint-use facility'),
  ('cargo_operator_at','entity','asset','pc_relationships','source_id','target_id','relationship_type','has_cargo_operator','many_to_many',true,'Cargo airline/logistics operator active at airport'),
  ('ground_handler_at','entity','asset','pc_relationships','source_id','target_id','relationship_type','has_ground_handler','many_to_many',true,'Ground handler active at airport'),
  ('mro_provider_at','entity','asset','pc_relationships','source_id','target_id','relationship_type','has_mro_provider','many_to_many',true,'MRO provider active at airport'),
  ('fuel_provider_at','entity','asset','pc_relationships','source_id','target_id','relationship_type','has_fuel_provider','many_to_many',true,'Fuel provider active at airport')
on conflict (relationship_type) do update set
  from_entity_type=excluded.from_entity_type,
  to_entity_type=excluded.to_entity_type,
  relationship_table=excluded.relationship_table,
  from_key_column=excluded.from_key_column,
  to_key_column=excluded.to_key_column,
  relationship_type_column=excluded.relationship_type_column,
  inverse_relationship_type=excluded.inverse_relationship_type,
  cardinality=excluded.cardinality,
  active=true,
  description=excluded.description;

-- ============================================================================
-- 12. RLS / READ POLICIES
-- ============================================================================

alter table pc_airports enable row level security;
alter table pc_airport_runways enable row level security;
alter table pc_airport_capabilities enable row level security;
alter table pc_airport_service_providers enable row level security;
alter table pc_airport_governance enable row level security;
alter table pc_airport_frequencies enable row level security;
alter table pc_airport_metrics enable row level security;
alter table pc_airport_operational_status enable row level security;

do $$
declare t text;
begin
  foreach t in array array[
    'pc_airports','pc_airport_runways','pc_airport_capabilities',
    'pc_airport_service_providers','pc_airport_governance',
    'pc_airport_frequencies','pc_airport_metrics','pc_airport_operational_status'
  ] loop
    execute format('drop policy if exists %I on %I', t||'_read', t);
    execute format('create policy %I on %I for select to authenticated using (true)', t||'_read', t);
  end loop;
end $$;

comment on table pc_airports is 'Aviation profile extension keyed to canonical pc_assets airport/air-base records.';
comment on table pc_airport_runways is 'Runway profile extension keyed to canonical pc_assets airport_runway records.';
comment on table pc_airport_capabilities is 'Airport cargo, handling and intermodal capability profile.';
comment on table pc_airport_service_providers is 'Cargo airline, ground handling, fuel, MRO, FBO and logistics provider presence at airports.';
comment on table pc_airport_governance is 'Airport owner/operator/authority/regulator/ANSP/military control history.';
comment on table pc_airport_operational_status is 'Time-bounded airport/runway/cargo operational state for Trade and Intelligence.';

commit;
