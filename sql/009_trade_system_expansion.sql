-- P&C Trade System Expansion v1.0
-- Energy, industrial, markets, trade-flow, port-economics, corridor and macro layers.
-- Designed to sit on top of pc_entities / pc_assets / pc_relationships without duplicating canonical objects.
begin;

-- ---------------------------------------------------------------------------
-- Provenance / observation layer: every imported or derived datapoint can point
-- back to its source, licence and methodology.
-- ---------------------------------------------------------------------------
alter table pc_sources add column if not exists license_name text;
alter table pc_sources add column if not exists redistribution_status text;
alter table pc_sources add column if not exists attribution_required boolean default false;
alter table pc_sources add column if not exists terms_url text;

create table if not exists pc_observations (
  observation_id uuid primary key default gen_random_uuid(),
  source_id text references pc_sources(source_id),
  source_name text,
  source_url text,
  source_type text,
  retrieved_at timestamptz not null default now(),
  published_at timestamptz,
  observation_date date,
  license_name text,
  redistribution_status text,
  attribution_required boolean not null default false,
  raw_value jsonb,
  derived_value jsonb,
  methodology text,
  confidence text,
  review_status text not null default 'pending' check (review_status in ('pending','approved','rejected')),
  record_status text not null default 'provisional',
  metadata jsonb not null default '{}'::jsonb
);
create index if not exists idx_pc_observations_source on pc_observations(source_id, observation_date desc);
create index if not exists idx_pc_observations_review on pc_observations(review_status, observation_date desc);

-- ---------------------------------------------------------------------------
-- Energy infrastructure extensions. Canonical identity remains pc_assets.
-- ---------------------------------------------------------------------------
create table if not exists pc_energy_assets (
  asset_id text primary key references pc_assets(asset_id) on delete cascade,
  energy_asset_type text not null, -- refinery / LNG / gas processing / field / terminal / storage / pipeline / petrochemical / power
  owner_entity_id text references pc_entities(entity_id),
  operator_entity_id text references pc_entities(entity_id),
  capacity_value numeric,
  capacity_unit text,
  crude_distillation_bpd numeric,
  conversion_capacity_bpd numeric,
  coking_capacity_bpd numeric,
  hydrocracking_capacity_bpd numeric,
  desulfurisation_capacity_bpd numeric,
  primary_inputs text[],
  primary_products text[],
  commissioned_date date,
  last_known_turnaround date,
  operational_status text,
  sanctions_status text,
  security_risk text,
  last_incident_date date,
  associated_port_id text references pc_assets(asset_id),
  associated_terminal_id text references pc_assets(asset_id),
  source_id text references pc_sources(source_id),
  last_verified date,
  metadata jsonb not null default '{}'::jsonb
);
create index if not exists idx_pc_energy_type on pc_energy_assets(energy_asset_type);
create index if not exists idx_pc_energy_operator on pc_energy_assets(operator_entity_id);

create table if not exists pc_energy_asset_connections (
  connection_id uuid primary key default gen_random_uuid(),
  source_asset_id text not null references pc_assets(asset_id) on delete cascade,
  target_type text not null check (target_type in ('ASSET','ENTITY','SYSTEM','GEOGRAPHY','MARKET_INSTRUMENT')),
  target_id text not null,
  relationship_type text not null, -- supplies / receives_from / connected_by_pipeline / exports_via / benchmark_exposure etc.
  product_or_commodity text,
  capacity_value numeric,
  capacity_unit text,
  valid_from date,
  valid_to date,
  confidence text,
  source_id text references pc_sources(source_id),
  notes text,
  metadata jsonb not null default '{}'::jsonb,
  unique(source_asset_id,target_type,target_id,relationship_type,product_or_commodity)
);

-- ---------------------------------------------------------------------------
-- Industrial / production assets: mines, smelters, mills, factories, silos etc.
-- ---------------------------------------------------------------------------
create table if not exists pc_industrial_assets (
  asset_id text primary key references pc_assets(asset_id) on delete cascade,
  industrial_asset_type text not null,
  owner_entity_id text references pc_entities(entity_id),
  operator_entity_id text references pc_entities(entity_id),
  commodity_or_product text,
  annual_capacity numeric,
  capacity_unit text,
  annual_production numeric,
  production_unit text,
  reserves_value numeric,
  reserves_unit text,
  processing_type text,
  export_terminal_id text references pc_assets(asset_id),
  rail_linked boolean,
  road_linked boolean,
  pipeline_linked boolean,
  destination_markets text[],
  operational_status text,
  source_id text references pc_sources(source_id),
  last_verified date,
  metadata jsonb not null default '{}'::jsonb
);
create index if not exists idx_pc_industrial_type on pc_industrial_assets(industrial_asset_type);
create index if not exists idx_pc_industrial_commodity on pc_industrial_assets(commodity_or_product);

-- ---------------------------------------------------------------------------
-- Warehousing, logistics parks, free zones and distribution infrastructure.
-- ---------------------------------------------------------------------------
create table if not exists pc_logistics_facilities (
  asset_id text primary key references pc_assets(asset_id) on delete cascade,
  facility_type text not null, -- logistics park / free zone / warehouse / cold chain / distribution centre
  developer_entity_id text references pc_entities(entity_id),
  operator_entity_id text references pc_entities(entity_id),
  owner_entity_id text references pc_entities(entity_id),
  anchor_tenants text[],
  area_sqm numeric,
  storage_capacity numeric,
  storage_capacity_unit text,
  investment_value numeric,
  investment_currency text,
  nearest_port_id text references pc_assets(asset_id),
  nearest_airport_id text references pc_assets(asset_id),
  rail_connected boolean,
  road_corridor_id text,
  customs_bonded boolean,
  source_id text references pc_sources(source_id),
  last_verified date,
  metadata jsonb not null default '{}'::jsonb
);

-- ---------------------------------------------------------------------------
-- Market instruments and prices. A market instrument is canonical once and can
-- be linked to assets, companies, commodities and corridors.
-- ---------------------------------------------------------------------------
create table if not exists pc_market_instruments (
  market_instrument_id text primary key,
  name text not null,
  symbol text,
  asset_class text not null, -- commodity / equity / freight / fx / energy / agriculture
  commodity text,
  benchmark_location text,
  exchange text,
  currency text,
  unit text,
  provider text,
  source_id text references pc_sources(source_id),
  redistribution_status text,
  attribution_required boolean not null default false,
  active boolean not null default true,
  metadata jsonb not null default '{}'::jsonb
);
create index if not exists idx_pc_market_instrument_class on pc_market_instruments(asset_class);
create index if not exists idx_pc_market_instrument_symbol on pc_market_instruments(symbol);

create table if not exists pc_market_prices (
  market_price_id uuid primary key default gen_random_uuid(),
  market_instrument_id text not null references pc_market_instruments(market_instrument_id) on delete cascade,
  observation_timestamp timestamptz not null,
  open numeric,
  high numeric,
  low numeric,
  close numeric,
  volume numeric,
  daily_change numeric,
  weekly_change numeric,
  monthly_change numeric,
  raw_value jsonb,
  source_id text references pc_sources(source_id),
  observation_id uuid references pc_observations(observation_id),
  data_status text default 'reported',
  metadata jsonb not null default '{}'::jsonb,
  unique(market_instrument_id,observation_timestamp,source_id)
);
create index if not exists idx_pc_market_prices_series on pc_market_prices(market_instrument_id,observation_timestamp desc);

create table if not exists pc_market_exposure_links (
  exposure_link_id uuid primary key default gen_random_uuid(),
  target_type text not null check (target_type in ('ENTITY','ASSET','MOBILE_ASSET','SYSTEM','GEOGRAPHY')),
  target_id text not null,
  market_instrument_id text not null references pc_market_instruments(market_instrument_id) on delete cascade,
  exposure_type text not null, -- input cost / output price / freight benchmark / equity / fx etc.
  direction text,
  materiality text,
  notes text,
  source_id text references pc_sources(source_id),
  unique(target_type,target_id,market_instrument_id,exposure_type)
);

-- ---------------------------------------------------------------------------
-- Physical trade and commodity flows.
-- ---------------------------------------------------------------------------
create table if not exists pc_trade_flows (
  trade_flow_id uuid primary key default gen_random_uuid(),
  observation_date date,
  period_start date,
  period_end date,
  frequency text,
  origin_country text,
  destination_country text,
  origin_asset_id text references pc_assets(asset_id),
  destination_asset_id text references pc_assets(asset_id),
  commodity text,
  hs_code text,
  quantity numeric,
  quantity_unit text,
  trade_value_usd numeric,
  transport_mode text,
  corridor_id text,
  source_id text references pc_sources(source_id),
  observation_id uuid references pc_observations(observation_id),
  confidence text,
  methodology text,
  metadata jsonb not null default '{}'::jsonb
);
create index if not exists idx_pc_trade_flows_period on pc_trade_flows(period_start desc, period_end desc);
create index if not exists idx_pc_trade_flows_od on pc_trade_flows(origin_country,destination_country,commodity);
create index if not exists idx_pc_trade_flows_assets on pc_trade_flows(origin_asset_id,destination_asset_id);

-- Production, supply, inventories and agricultural/mining baselines.
create table if not exists pc_supply_series (
  supply_record_id uuid primary key default gen_random_uuid(),
  observation_date date,
  period_start date,
  period_end date,
  geography text,
  entity_id text references pc_entities(entity_id),
  asset_id text references pc_assets(asset_id),
  commodity text,
  metric_name text not null,
  value numeric,
  unit text,
  crop_year text,
  source_id text references pc_sources(source_id),
  observation_id uuid references pc_observations(observation_id),
  metadata jsonb not null default '{}'::jsonb
);
create index if not exists idx_pc_supply_series on pc_supply_series(commodity,metric_name,period_end desc);

-- ---------------------------------------------------------------------------
-- Port economics and operational history.
-- ---------------------------------------------------------------------------
create table if not exists pc_port_metrics (
  port_metric_id uuid primary key default gen_random_uuid(),
  port_asset_id text not null references pc_assets(asset_id) on delete cascade,
  observation_date date,
  period_start date,
  period_end date,
  metric_name text not null, -- throughput_teu / dry_bulk_tonnes / liquid_bulk_tonnes / vehicle_units / vessel_calls / wait etc.
  value numeric,
  unit text,
  commodity text,
  source_id text references pc_sources(source_id),
  observation_id uuid references pc_observations(observation_id),
  metadata jsonb not null default '{}'::jsonb
);
create index if not exists idx_pc_port_metrics_series on pc_port_metrics(port_asset_id,metric_name,period_end desc);

create table if not exists pc_port_capabilities (
  port_asset_id text primary key references pc_assets(asset_id) on delete cascade,
  container_capacity_teu numeric,
  liquid_bulk_capacity numeric,
  liquid_bulk_unit text,
  dry_bulk_capacity numeric,
  dry_bulk_unit text,
  rail_connected boolean,
  pipeline_connected boolean,
  free_zone boolean,
  industrial_zone boolean,
  major_customers text[],
  commodities text[],
  source_id text references pc_sources(source_id),
  last_verified date,
  metadata jsonb not null default '{}'::jsonb
);

-- ---------------------------------------------------------------------------
-- Rail / road / border / chokepoint operational layer.
-- ---------------------------------------------------------------------------
create table if not exists pc_transport_routes (
  route_id text primary key,
  route_name text not null,
  mode text not null, -- rail / road / pipeline / inland-waterway / air-cargo / multimodal
  operator_entity_id text references pc_entities(entity_id),
  origin_type text,
  origin_id text,
  destination_type text,
  destination_id text,
  countries text[],
  gauge text,
  electrification text,
  capacity_value numeric,
  capacity_unit text,
  freight_types text[],
  average_transit_time_hours numeric,
  known_bottlenecks text[],
  current_status text,
  source_id text references pc_sources(source_id),
  metadata jsonb not null default '{}'::jsonb
);

create table if not exists pc_transport_route_status (
  route_status_id uuid primary key default gen_random_uuid(),
  route_id text not null references pc_transport_routes(route_id) on delete cascade,
  observation_timestamp timestamptz not null,
  strike_status text,
  closure_status text,
  weather_status text,
  border_status text,
  delay_hours numeric,
  queue_value numeric,
  queue_unit text,
  source_id text references pc_sources(source_id),
  observation_id uuid references pc_observations(observation_id),
  metadata jsonb not null default '{}'::jsonb
);

create table if not exists pc_chokepoints (
  chokepoint_id text primary key,
  asset_id text references pc_assets(asset_id),
  name text not null,
  chokepoint_type text not null, -- strait / canal / land border / rail crossing / bridge / tunnel / pass / river crossing
  country_a text,
  country_b text,
  latitude double precision,
  longitude double precision,
  normal_capacity numeric,
  capacity_unit text,
  current_status text,
  operating_hours text,
  commodity_dependency text[],
  alternative_routes text[],
  source_id text references pc_sources(source_id),
  metadata jsonb not null default '{}'::jsonb
);

create table if not exists pc_chokepoint_status (
  chokepoint_status_id uuid primary key default gen_random_uuid(),
  chokepoint_id text not null references pc_chokepoints(chokepoint_id) on delete cascade,
  observation_timestamp timestamptz not null,
  current_status text,
  queue_value numeric,
  queue_unit text,
  restriction_text text,
  source_id text references pc_sources(source_id),
  observation_id uuid references pc_observations(observation_id),
  metadata jsonb not null default '{}'::jsonb
);

-- ---------------------------------------------------------------------------
-- Country macro / logistics indicators.
-- ---------------------------------------------------------------------------
create table if not exists pc_macro_indicators (
  macro_record_id uuid primary key default gen_random_uuid(),
  country text not null,
  indicator_code text,
  indicator_name text not null,
  observation_date date,
  period_start date,
  period_end date,
  value numeric,
  unit text,
  source_id text references pc_sources(source_id),
  observation_id uuid references pc_observations(observation_id),
  metadata jsonb not null default '{}'::jsonb
);
create index if not exists idx_pc_macro_country_indicator on pc_macro_indicators(country,indicator_name,period_end desc);

-- ---------------------------------------------------------------------------
-- Client-safe views: only approved observations; raw source/licence fields kept.
-- ---------------------------------------------------------------------------
create or replace view pc_trade_energy_assets as
select a.asset_id,a.name,a.asset_type,a.subtype,a.country,a.region_city,a.latitude,a.longitude,
       e.energy_asset_type,e.owner_entity_id,e.operator_entity_id,e.capacity_value,e.capacity_unit,
       e.crude_distillation_bpd,e.primary_inputs,e.primary_products,e.operational_status,e.sanctions_status,
       e.security_risk,e.last_incident_date,e.associated_port_id,e.associated_terminal_id,e.last_verified,e.metadata
from pc_assets a join pc_energy_assets e using(asset_id)
where a.record_status <> 'rejected';

create or replace view pc_trade_industrial_assets as
select a.asset_id,a.name,a.asset_type,a.subtype,a.country,a.region_city,a.latitude,a.longitude,
       i.industrial_asset_type,i.owner_entity_id,i.operator_entity_id,i.commodity_or_product,
       i.annual_capacity,i.capacity_unit,i.annual_production,i.production_unit,i.reserves_value,i.reserves_unit,
       i.export_terminal_id,i.rail_linked,i.road_linked,i.pipeline_linked,i.destination_markets,i.operational_status,i.last_verified
from pc_assets a join pc_industrial_assets i using(asset_id)
where a.record_status <> 'rejected';

-- Read access for authenticated client apps. Service role/admin performs writes.
alter table pc_observations enable row level security;
alter table pc_energy_assets enable row level security;
alter table pc_energy_asset_connections enable row level security;
alter table pc_industrial_assets enable row level security;
alter table pc_logistics_facilities enable row level security;
alter table pc_market_instruments enable row level security;
alter table pc_market_prices enable row level security;
alter table pc_market_exposure_links enable row level security;
alter table pc_trade_flows enable row level security;
alter table pc_supply_series enable row level security;
alter table pc_port_metrics enable row level security;
alter table pc_port_capabilities enable row level security;
alter table pc_transport_routes enable row level security;
alter table pc_transport_route_status enable row level security;
alter table pc_chokepoints enable row level security;
alter table pc_chokepoint_status enable row level security;
alter table pc_macro_indicators enable row level security;

do $$
declare t text;
begin
  foreach t in array array[
    'pc_observations','pc_energy_assets','pc_energy_asset_connections','pc_industrial_assets','pc_logistics_facilities',
    'pc_market_instruments','pc_market_prices','pc_market_exposure_links','pc_trade_flows','pc_supply_series',
    'pc_port_metrics','pc_port_capabilities','pc_transport_routes','pc_transport_route_status','pc_chokepoints',
    'pc_chokepoint_status','pc_macro_indicators'
  ] loop
    execute format('drop policy if exists %I on %I', t||'_read', t);
    execute format('create policy %I on %I for select to authenticated using (true)', t||'_read', t);
  end loop;
end $$;

commit;
