-- Power & Corridors Core Platform v1.0
-- PostgreSQL / Supabase
-- One canonical model, two base client products (Trade + Intelligence), NERAI add-on,
-- one internal admin plane, and a multi-tenant client workspace layer.

begin;

create extension if not exists pgcrypto;
create extension if not exists pg_trgm;
create extension if not exists postgis;

-- ---------------------------------------------------------------------------
-- Shared reference / source layer
-- ---------------------------------------------------------------------------
create table if not exists pc_sources (
  source_id text primary key,
  publisher text,
  source_name text,
  source_type text,
  coverage text,
  url text,
  published_at timestamptz,
  checked_at timestamptz,
  reliability text,
  ingestion_method text,
  license_notes text,
  active boolean not null default true,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists pc_entities (
  entity_id text primary key,
  name text not null,
  entity_type text not null,
  subtype text,
  hq_city text,
  hq_country text,
  ownership_summary text,
  status text,
  record_status text not null default 'provisional',
  data_quality text not null default 'medium',
  source_id text references pc_sources(source_id),
  as_of date,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists idx_pc_entities_name_trgm on pc_entities using gin (name gin_trgm_ops);
create index if not exists idx_pc_entities_type on pc_entities(entity_type);

create table if not exists pc_entity_aliases (
  alias_id uuid primary key default gen_random_uuid(),
  entity_id text not null references pc_entities(entity_id) on delete cascade,
  alias text not null,
  alias_type text,
  source_id text references pc_sources(source_id),
  unique(entity_id, alias)
);
create index if not exists idx_pc_entity_alias_trgm on pc_entity_aliases using gin (alias gin_trgm_ops);

create table if not exists pc_assets (
  asset_id text primary key,
  name text not null,
  asset_type text not null,
  subtype text,
  country text,
  region_city text,
  latitude double precision,
  longitude double precision,
  geom geography(point,4326) generated always as (
    case when latitude is not null and longitude is not null
      then st_setsrid(st_makepoint(longitude,latitude),4326)::geography
    end
  ) stored,
  operator_entity_id text references pc_entities(entity_id),
  owner_entity_id text references pc_entities(entity_id),
  capacity_value numeric,
  capacity_unit text,
  status text,
  record_status text not null default 'provisional',
  data_quality text not null default 'medium',
  source_id text references pc_sources(source_id),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists idx_pc_assets_name_trgm on pc_assets using gin (name gin_trgm_ops);
create index if not exists idx_pc_assets_type on pc_assets(asset_type);
create index if not exists idx_pc_assets_geom on pc_assets using gist(geom);

create table if not exists pc_mobile_assets (
  mobile_asset_id text primary key,
  name text not null,
  asset_type text not null,
  subtype text,
  imo text,
  mmsi text,
  registration text,
  call_sign text,
  flag text,
  year_built integer,
  dwt numeric,
  capacity_value numeric,
  capacity_unit text,
  owner_entity_id text references pc_entities(entity_id),
  operator_entity_id text references pc_entities(entity_id),
  manager_entity_id text references pc_entities(entity_id),
  status text,
  record_status text not null default 'provisional',
  data_quality text not null default 'medium',
  source_id text references pc_sources(source_id),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create unique index if not exists idx_pc_mobile_imo_unique on pc_mobile_assets(imo) where imo is not null and btrim(imo) <> '';
create index if not exists idx_pc_mobile_name_trgm on pc_mobile_assets using gin(name gin_trgm_ops);

create table if not exists pc_relationships (
  relationship_id text primary key,
  source_type text not null,
  source_id text not null,
  relationship_type text not null,
  target_type text not null,
  target_id text not null,
  ownership_percent numeric,
  operating_control boolean,
  valid_from date,
  valid_to date,
  confidence text,
  record_status text not null default 'provisional',
  evidence_source_id text references pc_sources(source_id),
  notes text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists idx_pc_rel_source on pc_relationships(source_type,source_id);
create index if not exists idx_pc_rel_target on pc_relationships(target_type,target_id);

create table if not exists pc_geographies (
  geo_id text primary key,
  name text not null,
  geo_type text not null,
  parent_geo_id text references pc_geographies(geo_id),
  countries text,
  geom geometry(Geometry,4326),
  watch_status text,
  risk_level text,
  record_status text not null default 'provisional',
  source_id text references pc_sources(source_id),
  notes text,
  metadata jsonb not null default '{}'::jsonb
);
create index if not exists idx_pc_geo_geom on pc_geographies using gist(geom);

-- ---------------------------------------------------------------------------
-- Events: one event universe, explicit routing to Trade and Intelligence
-- ---------------------------------------------------------------------------
create table if not exists pc_events (
  event_id text primary key,
  start_date timestamptz,
  end_date timestamptz,
  event_nature text,                -- SECURITY / DISRUPTION / CORPORATE / OTHER
  event_domain text,                -- maritime, port, rail, road, aviation, defence, etc.
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
  trade_relevance smallint not null default 0 check (trade_relevance between 0 and 5),
  intelligence_relevance smallint not null default 0 check (intelligence_relevance between 0 and 5),
  trade_visible boolean not null default false,
  intelligence_visible boolean not null default false,
  alert_worthy boolean not null default false,
  record_status text not null default 'provisional',
  source_id text references pc_sources(source_id),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists idx_pc_events_date on pc_events(start_date desc);
create index if not exists idx_pc_events_trade on pc_events(trade_visible,trade_relevance desc,start_date desc);
create index if not exists idx_pc_events_intel on pc_events(intelligence_visible,intelligence_relevance desc,start_date desc);
create index if not exists idx_pc_events_title_trgm on pc_events using gin(title gin_trgm_ops);

create table if not exists pc_event_locations (
  event_location_id text primary key,
  event_id text not null references pc_events(event_id) on delete cascade,
  location_name text,
  country text,
  latitude double precision,
  longitude double precision,
  accuracy text,
  geom geography(point,4326) generated always as (
    case when latitude is not null and longitude is not null
      then st_setsrid(st_makepoint(longitude,latitude),4326)::geography
    end
  ) stored,
  notes text
);
create index if not exists idx_pc_event_locations_geom on pc_event_locations using gist(geom);

create table if not exists pc_event_links (
  event_link_id text primary key,
  event_id text not null references pc_events(event_id) on delete cascade,
  linked_type text not null,
  linked_id text not null,
  linked_name text,
  relationship text not null,
  confidence text,
  source_id text references pc_sources(source_id),
  metadata jsonb not null default '{}'::jsonb
);
create index if not exists idx_pc_event_links_event on pc_event_links(event_id);
create index if not exists idx_pc_event_links_target on pc_event_links(linked_type,linked_id);

create table if not exists pc_impact_chains (
  impact_chain_id text primary key,
  event_id text not null references pc_events(event_id) on delete cascade,
  step integer,
  trigger text,
  direct_impact text,
  secondary_impact text,
  tertiary_impact text,
  strategic_commercial_outcome text,
  propagation_type text
);

create table if not exists pc_governance_links (
  governance_id uuid primary key default gen_random_uuid(),
  governed_type text not null,
  governed_id text not null,
  authority_entity_id text references pc_entities(entity_id),
  authority_name text,
  governance_role text,
  model_note text,
  status text default 'current',
  source_id text references pc_sources(source_id),
  source_url text,
  unique(governed_type,governed_id,authority_entity_id,governance_role)
);
create index if not exists idx_pc_governed_object on pc_governance_links(governed_type,governed_id);

-- ---------------------------------------------------------------------------
-- Commercial / market / compliance / analysis
-- ---------------------------------------------------------------------------
create table if not exists pc_transactions (
  transaction_id text primary key,
  announced_date date,
  effective_date date,
  buyer_entity_id text references pc_entities(entity_id),
  seller_name text,
  target_entity_id text references pc_entities(entity_id),
  target_asset_id text references pc_assets(asset_id),
  target_name text,
  asset_class text,
  country_region text,
  transaction_type text,
  equity_percent numeric,
  reported_value numeric,
  currency text,
  operating_control boolean,
  status text,
  regulatory_status text,
  source_id text references pc_sources(source_id),
  notes text,
  metadata jsonb not null default '{}'::jsonb
);

create table if not exists pc_financial_records (
  financial_record_id text primary key,
  entity_id text references pc_entities(entity_id),
  period_or_date date,
  record_type text,
  metric_or_project text,
  value numeric,
  unit text,
  currency text,
  country_region text,
  asset_id text references pc_assets(asset_id),
  spend_type text,
  status text,
  source_id text references pc_sources(source_id),
  notes text,
  metadata jsonb not null default '{}'::jsonb
);

create table if not exists pc_market_data (
  market_record_id text primary key,
  entity_id text not null references pc_entities(entity_id),
  exchange text,
  ticker text,
  trade_date date not null,
  open numeric,
  high numeric,
  low numeric,
  close numeric,
  volume numeric,
  currency text,
  source_id text references pc_sources(source_id),
  metadata jsonb not null default '{}'::jsonb
);
create index if not exists idx_pc_market_entity_date on pc_market_data(entity_id,trade_date desc);

create table if not exists pc_security_compliance (
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
  source_id text references pc_sources(source_id),
  notes text,
  metadata jsonb not null default '{}'::jsonb
);

create table if not exists pc_analysis (
  analysis_id text primary key,
  product_code text,
  analysis_type text not null,
  title text not null,
  family text,
  geography_id text references pc_geographies(geo_id),
  status text,
  start_date date,
  time_horizon text,
  monitoring_question text,
  indicators jsonb not null default '[]'::jsonb,
  trigger_threshold text,
  confidence text,
  ghost_post_id text,
  ghost_url text,
  publication_status text,
  published_at timestamptz,
  source_id text references pc_sources(source_id),
  notes text,
  metadata jsonb not null default '{}'::jsonb
);

-- ---------------------------------------------------------------------------
-- Legacy mirror: lets existing Streamlit apps switch to Supabase without a
-- complete page rewrite on migration night.
-- ---------------------------------------------------------------------------
create table if not exists pc_legacy_sheet_rows (
  legacy_row_id uuid primary key default gen_random_uuid(),
  source_book text not null,
  source_sheet text not null,
  row_number integer not null,
  row_key text,
  row_data jsonb not null,
  checksum text not null,
  imported_at timestamptz not null default now(),
  unique(source_book,source_sheet,row_number)
);
create index if not exists idx_pc_legacy_sheet on pc_legacy_sheet_rows(source_book,source_sheet,row_number);
create index if not exists idx_pc_legacy_row_data on pc_legacy_sheet_rows using gin(row_data);

-- ---------------------------------------------------------------------------
-- Multi-tenant client layer
-- ---------------------------------------------------------------------------
create table if not exists pc_organizations (
  organization_id uuid primary key default gen_random_uuid(),
  name text not null unique,
  slug text not null unique,
  status text not null default 'active',
  seat_limit integer not null default 5 check (seat_limit >= 1),
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists pc_profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  display_name text,
  email text,
  global_role text not null default 'user', -- super_admin / staff / user
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists pc_organization_members (
  organization_id uuid not null references pc_organizations(organization_id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null default 'viewer', -- org_admin / senior_analyst / analyst / executive / viewer
  active boolean not null default true,
  joined_at timestamptz not null default now(),
  primary key(organization_id,user_id)
);

create table if not exists pc_products (
  product_code text primary key,
  product_name text not null,
  active boolean not null default true
);
insert into pc_products(product_code,product_name) values
  ('TRADE','P&C Trade'),
  ('INTELLIGENCE','P&C Intelligence'),
  ('NERAI','NERAI')
on conflict(product_code) do update set product_name=excluded.product_name;

create table if not exists pc_organization_entitlements (
  organization_id uuid not null references pc_organizations(organization_id) on delete cascade,
  product_code text not null references pc_products(product_code),
  tier text not null default 'base',
  active boolean not null default true,
  start_date date,
  end_date date,
  monthly_ai_limit integer,
  monthly_export_limit integer,
  feature_overrides jsonb not null default '{}'::jsonb,
  primary key(organization_id,product_code)
);

create table if not exists pc_saved_queries (
  saved_query_id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references pc_organizations(organization_id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  product_code text not null references pc_products(product_code),
  title text,
  query_text text not null,
  query_type text,
  parameters jsonb not null default '{}'::jsonb,
  last_result jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists pc_saved_watchlists (
  watchlist_id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references pc_organizations(organization_id) on delete cascade,
  created_by uuid not null references auth.users(id),
  product_code text not null references pc_products(product_code),
  name text not null,
  description text,
  shared_with_org boolean not null default true,
  created_at timestamptz not null default now()
);

create table if not exists pc_watchlist_items (
  watchlist_item_id uuid primary key default gen_random_uuid(),
  watchlist_id uuid not null references pc_saved_watchlists(watchlist_id) on delete cascade,
  item_type text not null,
  item_id text,
  item_name text not null,
  notes text
);

create table if not exists pc_ai_sessions (
  session_id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references pc_organizations(organization_id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  product_code text not null references pc_products(product_code),
  title text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists pc_ai_messages (
  message_id uuid primary key default gen_random_uuid(),
  session_id uuid not null references pc_ai_sessions(session_id) on delete cascade,
  role text not null,
  content text not null,
  model text,
  data_snapshot_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists pc_scenario_runs (
  scenario_run_id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references pc_organizations(organization_id) on delete cascade,
  user_id uuid not null references auth.users(id),
  product_code text not null references pc_products(product_code),
  title text,
  prompt text not null,
  inputs jsonb not null default '{}'::jsonb,
  result jsonb,
  model_version text,
  created_at timestamptz not null default now()
);

create table if not exists pc_client_notes (
  note_id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references pc_organizations(organization_id) on delete cascade,
  user_id uuid not null references auth.users(id),
  object_type text,
  object_id text,
  note_text text not null,
  shared_with_org boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists pc_client_admin_requests (
  request_id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references pc_organizations(organization_id) on delete cascade,
  requested_by uuid not null references auth.users(id),
  request_type text not null,
  requested_email text,
  requested_role text,
  requested_product text,
  details jsonb not null default '{}'::jsonb,
  status text not null default 'pending',
  reviewed_by uuid references auth.users(id),
  reviewed_at timestamptz,
  created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Admin / AI ingestion and controlled write plane
-- ---------------------------------------------------------------------------
create table if not exists pc_ingestion_jobs (
  ingestion_job_id uuid primary key default gen_random_uuid(),
  job_type text not null,
  title text,
  query_text text,
  source_scope jsonb not null default '{}'::jsonb,
  status text not null default 'queued',
  requested_by uuid references auth.users(id),
  started_at timestamptz,
  completed_at timestamptz,
  stats jsonb not null default '{}'::jsonb,
  error_text text,
  created_at timestamptz not null default now()
);

create table if not exists pc_staged_records (
  staged_record_id uuid primary key default gen_random_uuid(),
  ingestion_job_id uuid references pc_ingestion_jobs(ingestion_job_id) on delete cascade,
  target_table text not null,
  natural_key text,
  action text not null, -- INSERT / UPDATE / POSSIBLE_DUPLICATE / CONFLICT / IGNORE
  payload jsonb not null,
  current_record jsonb,
  confidence numeric,
  validation_status text not null default 'pending',
  review_status text not null default 'pending',
  source_id text,
  created_at timestamptz not null default now(),
  reviewed_at timestamptz,
  reviewed_by uuid references auth.users(id)
);
create index if not exists idx_pc_stage_review on pc_staged_records(review_status,validation_status);

create table if not exists pc_data_quality_issues (
  issue_id uuid primary key default gen_random_uuid(),
  object_type text,
  object_id text,
  issue_type text not null,
  severity text not null default 'medium',
  description text not null,
  suggested_action text,
  status text not null default 'open',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  resolved_at timestamptz
);

create table if not exists pc_audit_log (
  audit_id bigserial primary key,
  user_id uuid references auth.users(id),
  organization_id uuid references pc_organizations(organization_id),
  action text not null,
  object_type text,
  object_id text,
  before_data jsonb,
  after_data jsonb,
  created_at timestamptz not null default now()
);

commit;
