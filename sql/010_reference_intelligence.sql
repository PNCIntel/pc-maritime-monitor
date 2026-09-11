-- P&C Trade System v3.3 - reference intelligence expansion
create extension if not exists pgcrypto;

create table if not exists pc_reference_datasets (
  dataset_id uuid primary key default gen_random_uuid(),
  dataset_key text unique not null,
  dataset_name text not null,
  dataset_family text,
  source_organization text,
  source_url text,
  coverage_start date,
  coverage_end date,
  source_as_of date,
  storage_mode text default 'REFERENCE',
  methodology_notes text,
  metadata jsonb default '{}'::jsonb,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists pc_reference_observations (
  observation_id uuid primary key default gen_random_uuid(),
  dataset_key text not null,
  observation_date date,
  geography_scope text,
  origin_entity_id text,
  destination_entity_id text,
  metric_family text,
  metric_name text not null,
  category text,
  value_numeric numeric,
  value_text text,
  unit text,
  source_url text,
  confidence text,
  metadata jsonb default '{}'::jsonb,
  created_at timestamptz default now()
);
create index if not exists idx_pc_reference_obs_dataset on pc_reference_observations(dataset_key);
create index if not exists idx_pc_reference_obs_metric on pc_reference_observations(metric_family,metric_name);

create table if not exists pc_official_incidents (
  official_incident_id uuid primary key default gen_random_uuid(),
  authority text not null,
  authority_record_key text,
  incident_date date,
  vessel_name text,
  imo text,
  location_text text,
  damage_status text,
  pollution_status text,
  fatalities integer,
  injuries integer,
  incident_status text,
  confirmation_status text default 'CONFIRMED',
  source_url text not null,
  source_as_of date,
  linked_event_id text,
  metadata jsonb default '{}'::jsonb,
  unique(authority,authority_record_key)
);
create index if not exists idx_pc_official_incidents_imo on pc_official_incidents(imo);
create index if not exists idx_pc_official_incidents_date on pc_official_incidents(incident_date desc);

create table if not exists pc_operational_measures (
  measure_id uuid primary key default gen_random_uuid(),
  measure_key text unique,
  theatre text,
  measure_type text,
  issuing_authority text,
  status text,
  effective_date date,
  affected_population text,
  navigation_instruction text,
  risk_basis text,
  source_url text,
  source_as_of date,
  metadata jsonb default '{}'::jsonb
);

create table if not exists pc_chokepoint_governance (
  governance_id uuid primary key default gen_random_uuid(),
  chokepoint_id text,
  chokepoint_name text not null,
  governance_mechanism text,
  authorities text,
  navigation_regime text,
  safety_measures text,
  alternative_routes text,
  source_url text,
  source_as_of date,
  metadata jsonb default '{}'::jsonb
);

create table if not exists pc_port_reference (
  port_reference_id uuid primary key default gen_random_uuid(),
  source_dataset_key text not null,
  source_port_key text,
  port_name text not null,
  country text,
  latitude numeric,
  longitude numeric,
  exports numeric,
  imports numeric,
  transshipment numeric,
  throughput numeric,
  source_url text,
  source_as_of date,
  canonical_port_id text,
  metadata jsonb default '{}'::jsonb
);
create index if not exists idx_pc_port_reference_name on pc_port_reference(lower(port_name));

create table if not exists pc_port_scenario_metrics (
  scenario_metric_id uuid primary key default gen_random_uuid(),
  source_dataset_key text not null,
  source_port_key text,
  canonical_port_id text,
  scenario_year integer,
  scenario_name text,
  metric_name text,
  value_numeric numeric,
  unit text,
  metadata jsonb default '{}'::jsonb
);

create table if not exists pc_delay_factor_models (
  delay_factor_id uuid primary key default gen_random_uuid(),
  model_family text,
  stakeholder_group text,
  factor_name text,
  factor_code text,
  rank_value numeric,
  causal_score numeric,
  effect_score numeric,
  source_dataset_key text,
  source_url text,
  metadata jsonb default '{}'::jsonb
);
