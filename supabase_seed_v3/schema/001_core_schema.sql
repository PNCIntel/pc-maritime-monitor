-- P&C Core Intelligence Model v3.0 - sample migration schema
-- PostgreSQL / Supabase compatible. PostGIS is optional but recommended.

create extension if not exists pgcrypto;
create extension if not exists postgis;

create table if not exists sources (
  source_id text primary key,
  publisher text not null,
  source_type text,
  coverage text,
  url text,
  checked_as_of date,
  reliability text,
  ingestion_method text,
  active boolean default true,
  notes text
);

create table if not exists entities (
  entity_id text primary key,
  name text not null,
  entity_type text not null,
  subtype text,
  hq_city text,
  hq_country text,
  ownership_summary text,
  status text,
  record_status text check (record_status in ('verified','provisional','synthetic_test','incomplete','archived')),
  data_quality text check (data_quality in ('high','medium','low')),
  source_id text references sources(source_id),
  as_of date
);

create table if not exists assets (
  asset_id text primary key,
  name text not null,
  asset_type text not null,
  subtype text,
  country text,
  region_city text,
  operator_entity_id text references entities(entity_id),
  owner_entity_id text references entities(entity_id),
  capacity_value numeric,
  capacity_unit text,
  status text,
  record_status text,
  data_quality text,
  source_id text references sources(source_id)
);

create table if not exists mobile_assets (
  mobile_asset_id text primary key,
  name text not null,
  asset_type text not null,
  subtype text,
  imo_or_identifier text,
  flag text,
  year_built integer,
  owner_entity_id text references entities(entity_id),
  operator_entity_id text references entities(entity_id),
  status text,
  record_status text,
  data_quality text,
  source_id text references sources(source_id)
);
create unique index if not exists idx_mobile_imo on mobile_assets(imo_or_identifier) where imo_or_identifier is not null and imo_or_identifier <> '';

create table if not exists relationships (
  relationship_id text primary key,
  source_type text not null,
  source_id text not null,
  relationship_type text not null,
  target_type text not null,
  target_id text not null,
  ownership_percent numeric,
  valid_from date,
  valid_to date,
  confidence text,
  record_status text,
  source_record_id text references sources(source_id),
  notes text
);

create table if not exists geographies (
  geo_id text primary key,
  name text not null,
  geo_type text not null,
  parent_geo_id text references geographies(geo_id),
  countries text,
  geometry_status text,
  geom geometry(Geometry,4326),
  watch_status text,
  risk_level text,
  record_status text,
  source_id text references sources(source_id),
  notes text
);

create table if not exists events (
  event_id text primary key,
  start_date date,
  end_date date,
  event_family text,
  event_type text,
  severity text,
  status text,
  mode text,
  countries text,
  location text,
  title text not null,
  description text,
  operational_impact text,
  commercial_impact text,
  confidence text,
  record_status text,
  source_id text references sources(source_id)
);

create table if not exists event_links (
  event_link_id text primary key,
  event_id text not null references events(event_id) on delete cascade,
  linked_type text not null,
  linked_id text not null,
  relationship text not null,
  confidence text,
  source_id text references sources(source_id)
);

create table if not exists security_compliance (
  security_record_id text primary key,
  record_type text not null,
  regime text,
  event_date date,
  target_type text,
  target_id text,
  target_name text,
  identifier text,
  status text,
  exposure_type text,
  related_target text,
  relationship text,
  confidence text,
  record_status text,
  source_id text references sources(source_id),
  notes text
);

create table if not exists financial_investment (
  financial_record_id text primary key,
  record_type text not null,
  entity_id text references entities(entity_id),
  period_or_date date,
  metric_or_project text,
  value numeric,
  unit text,
  currency text,
  country_region text,
  asset_id text references assets(asset_id),
  spend_type text,
  status text,
  record_status text,
  source_id text references sources(source_id),
  notes text
);

create table if not exists market_data (
  market_record_id text primary key,
  entity_id text not null references entities(entity_id),
  exchange text,
  ticker text,
  trade_date date not null,
  open numeric,
  high numeric,
  low numeric,
  close numeric,
  volume numeric,
  currency text,
  record_type text,
  record_status text,
  source_id text references sources(source_id),
  notes text
);
create index if not exists idx_market_entity_date on market_data(entity_id, trade_date desc);

create table if not exists intelligence_analysis (
  analysis_id text primary key,
  analysis_type text not null,
  title text not null,
  family text,
  geography_id text references geographies(geo_id),
  status text,
  start_date date,
  time_horizon text,
  monitoring_question text,
  indicators text,
  trigger_threshold text,
  linked_event_ids text,
  linked_entity_or_asset_ids text,
  confidence text,
  record_status text,
  source_id text references sources(source_id),
  notes text
);

-- Useful views for the two products.
create or replace view vw_intel_active_security as
select
  ia.analysis_id, ia.analysis_type, ia.title, g.name as geography,
  ia.status, ia.time_horizon, ia.monitoring_question, ia.indicators,
  ia.trigger_threshold, ia.confidence
from intelligence_analysis ia
left join geographies g on g.geo_id = ia.geography_id
where ia.status ilike 'Active%';

create or replace view vw_intel_pgsa as
select
  sc.security_record_id, sc.record_type, sc.target_name, sc.identifier,
  sc.status, sc.exposure_type, sc.related_target, sc.relationship,
  sc.confidence, sc.notes
from security_compliance sc
where sc.regime = 'PGSA Maritime Compliance Regime';

create or replace view vw_trade_company_financials as
select
  e.entity_id, e.name as company, fi.period_or_date, fi.metric_or_project,
  fi.value, fi.unit, fi.currency, fi.spend_type, fi.status
from financial_investment fi
join entities e on e.entity_id = fi.entity_id
order by e.name, fi.period_or_date desc;

create or replace view vw_trade_market_history as
select
  e.name as company, md.exchange, md.ticker, md.trade_date,
  md.open, md.high, md.low, md.close, md.volume, md.currency
from market_data md
join entities e on e.entity_id = md.entity_id
order by e.name, md.trade_date;

create or replace view vw_event_exposure as
select
  ev.event_id, ev.start_date, ev.event_family, ev.event_type, ev.severity,
  ev.title, el.linked_type, el.linked_id, el.relationship, ev.operational_impact,
  ev.commercial_impact
from events ev
join event_links el on el.event_id = ev.event_id;
