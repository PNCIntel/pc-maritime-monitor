-- P&C Port & Maritime Regulatory Notice Monitor
-- 2026-10-04
-- Run once in Supabase SQL Editor before opening Power Admin > Port notices.

create extension if not exists pgcrypto;

create table if not exists public.pc_maritime_notice_sources (
  source_id uuid primary key default gen_random_uuid(),
  source_key text not null unique,
  source_name text not null,
  authority_name text not null,
  country_code text,
  country_name text,
  region text,
  port_name text,
  authority_type text not null default 'PORT_AUTHORITY',
  source_type text not null default 'PORT_NOTICE_INDEX',
  source_url text not null,
  archive_url text,
  parser_kind text not null default 'GENERIC_LINK_INDEX',
  language text not null default 'en',
  notice_classes jsonb not null default '[]'::jsonb,
  priority smallint not null default 3 check (priority between 1 and 5),
  poll_minutes integer not null default 1440 check (poll_minutes >= 60),
  active boolean not null default true,
  last_checked_at timestamptz,
  last_success_at timestamptz,
  last_error text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.pc_maritime_notices (
  notice_id uuid primary key default gen_random_uuid(),
  source_id uuid not null references public.pc_maritime_notice_sources(source_id) on delete cascade,
  source_notice_key text not null,
  notice_number text,
  title text not null,
  notice_category text not null default 'OTHER',
  published_date date,
  effective_from timestamptz,
  effective_to timestamptz,
  status text not null default 'DISCOVERED',
  jurisdiction text,
  geographic_scope text,
  port_name text,
  legal_basis text,
  summary text,
  source_page_url text not null,
  document_url text,
  stored_document_id text,
  supersedes_notice_id uuid references public.pc_maritime_notices(notice_id),
  superseded_by_notice_id uuid references public.pc_maritime_notices(notice_id),
  raw_excerpt text,
  extracted_imo_numbers jsonb not null default '[]'::jsonb,
  metadata jsonb not null default '{}'::jsonb,
  discovered_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  reviewed_at timestamptz,
  reviewed_by text,
  unique(source_id, source_notice_key)
);

create table if not exists public.pc_maritime_notice_asset_links (
  link_id uuid primary key default gen_random_uuid(),
  notice_id uuid not null references public.pc_maritime_notices(notice_id) on delete cascade,
  mobile_asset_id text,
  imo_number text,
  relationship_type text not null default 'AFFECTS_VESSEL',
  match_status text not null default 'UNRESOLVED',
  confidence numeric(5,4),
  evidence text,
  created_at timestamptz not null default now(),
  unique(notice_id, imo_number, relationship_type)
);

create index if not exists idx_pc_notice_sources_active_due
  on public.pc_maritime_notice_sources(active, priority, last_checked_at);
create index if not exists idx_pc_maritime_notices_discovered
  on public.pc_maritime_notices(discovered_at desc);
create index if not exists idx_pc_maritime_notices_category
  on public.pc_maritime_notices(notice_category, published_date desc);
create index if not exists idx_pc_maritime_notices_status
  on public.pc_maritime_notices(status, discovered_at desc);
create index if not exists idx_pc_notice_asset_links_imo
  on public.pc_maritime_notice_asset_links(imo_number);

comment on table public.pc_maritime_notice_sources is
'Official port, harbour-master, canal, coast-guard and maritime-regulator notice indexes monitored by P&C.';
comment on table public.pc_maritime_notices is
'Source-backed operational/regulatory maritime notices; status is temporal and notices may supersede or cancel earlier notices.';
comment on table public.pc_maritime_notice_asset_links is
'Links notices to canonical mobile assets where an IMO can be resolved; unresolved IMOs remain retained for review.';
