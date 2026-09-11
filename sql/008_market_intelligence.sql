-- P&C Trade market-intelligence layer
-- Initial public-source use case: The Signal Group Weekly Market Monitor.
-- Values are stored as attributed observations, not as unattributed P&C market data.
begin;

create table if not exists pc_market_reports (
  market_report_id uuid primary key default gen_random_uuid(),
  provider text not null,
  report_family text not null,
  report_title text not null,
  report_date date,
  iso_year integer,
  week_number integer,
  market_scope text,
  source_url text not null unique,
  source_methodology text,
  content_hash text,
  extracted_summary text,
  tags text[] not null default '{}',
  review_status text not null default 'pending' check (review_status in ('pending','approved','rejected')),
  client_visible boolean not null default false,
  ingested_at timestamptz not null default now(),
  last_checked_at timestamptz not null default now(),
  metadata jsonb not null default '{}'::jsonb
);

create table if not exists pc_market_observations (
  market_observation_id uuid primary key default gen_random_uuid(),
  market_report_id uuid not null references pc_market_reports(market_report_id) on delete cascade,
  observation_date date,
  period_start date,
  period_end date,
  market text,
  vessel_class text,
  route_code text,
  route_description text,
  origin_text text,
  destination_text text,
  commodity text,
  metric_family text not null,
  metric_name text not null,
  value_numeric numeric,
  value_text text,
  unit text,
  currency text,
  change_wow numeric,
  change_yoy numeric,
  benchmark text,
  pc_market_signal text,
  pc_direction text,
  pc_driver text,
  confidence text,
  source_excerpt text,
  review_status text not null default 'pending' check (review_status in ('pending','approved','rejected')),
  client_visible boolean not null default false,
  created_at timestamptz not null default now(),
  metadata jsonb not null default '{}'::jsonb
);

create table if not exists pc_market_observation_links (
  market_observation_link_id uuid primary key default gen_random_uuid(),
  market_observation_id uuid not null references pc_market_observations(market_observation_id) on delete cascade,
  target_type text not null check (target_type in ('ENTITY','ASSET','MOBILE_ASSET','SYSTEM','GEOGRAPHY')),
  target_id text not null,
  relationship text,
  confidence text,
  notes text,
  unique(market_observation_id,target_type,target_id,relationship)
);

create index if not exists idx_pc_market_reports_date on pc_market_reports(report_date desc);
create index if not exists idx_pc_market_reports_family on pc_market_reports(report_family, report_date desc);
create index if not exists idx_pc_market_observations_date on pc_market_observations(observation_date desc);
create index if not exists idx_pc_market_observations_route on pc_market_observations(route_code, observation_date desc);
create index if not exists idx_pc_market_observations_metric on pc_market_observations(metric_family, metric_name, observation_date desc);
create index if not exists idx_pc_market_observations_commodity on pc_market_observations(commodity, observation_date desc);

create or replace view pc_trade_market_reports as
select *
from pc_market_reports
where review_status='approved' and client_visible=true;

create or replace view pc_trade_market_observations as
select
  o.*,
  r.provider,
  r.report_family,
  r.report_title,
  r.report_date,
  r.week_number,
  r.source_url as report_url,
  r.source_methodology
from pc_market_observations o
join pc_market_reports r using (market_report_id)
where o.review_status='approved'
  and o.client_visible=true
  and r.review_status='approved'
  and r.client_visible=true;

-- Market data is shared Trade content. Writes are service-role/admin only.
alter table pc_market_reports enable row level security;
alter table pc_market_observations enable row level security;
alter table pc_market_observation_links enable row level security;

drop policy if exists pc_market_reports_read on pc_market_reports;
create policy pc_market_reports_read on pc_market_reports for select to authenticated using (true);
drop policy if exists pc_market_observations_read on pc_market_observations;
create policy pc_market_observations_read on pc_market_observations for select to authenticated using (true);
drop policy if exists pc_market_links_read on pc_market_observation_links;
create policy pc_market_links_read on pc_market_observation_links for select to authenticated using (true);

commit;
