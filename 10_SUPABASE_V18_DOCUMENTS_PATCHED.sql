-- P&C v1.8 document intelligence layer — PATCHED / idempotent.
-- Safe for an existing pc_documents table created by an earlier schema.
-- Adds missing columns before creating indexes. Does not drop or rename existing data.

create extension if not exists pgcrypto;

-- ---------------------------------------------------------------------------
-- Documents
-- ---------------------------------------------------------------------------
create table if not exists public.pc_documents (
  document_id uuid primary key default gen_random_uuid(),
  title text not null,
  document_type text,
  published_date date,
  source_entity_id text,
  source_name text,
  source_url text,
  authors text[] not null default '{}',
  products text[] not null default '{}',
  summary text,
  analytical_abstract text,
  key_findings jsonb not null default '[]'::jsonb,
  topics text[] not null default '{}',
  geographies text[] not null default '{}',
  search_text text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- CREATE TABLE IF NOT EXISTS does not add columns to an already-existing table.
-- Add every v1.8 field defensively.
alter table public.pc_documents add column if not exists document_type text;
alter table public.pc_documents add column if not exists published_date date;
alter table public.pc_documents add column if not exists source_entity_id text;
alter table public.pc_documents add column if not exists source_name text;
alter table public.pc_documents add column if not exists source_url text;
alter table public.pc_documents add column if not exists authors text[] default '{}';
alter table public.pc_documents add column if not exists products text[] default '{}';
alter table public.pc_documents add column if not exists summary text;
alter table public.pc_documents add column if not exists analytical_abstract text;
alter table public.pc_documents add column if not exists key_findings jsonb default '[]'::jsonb;
alter table public.pc_documents add column if not exists topics text[] default '{}';
alter table public.pc_documents add column if not exists geographies text[] default '{}';
alter table public.pc_documents add column if not exists search_text text;
alter table public.pc_documents add column if not exists metadata jsonb default '{}'::jsonb;
alter table public.pc_documents add column if not exists created_at timestamptz default now();
alter table public.pc_documents add column if not exists updated_at timestamptz default now();

-- ---------------------------------------------------------------------------
-- Document -> entity links
-- ---------------------------------------------------------------------------
create table if not exists public.pc_document_entity_links (
  document_link_id uuid primary key default gen_random_uuid(),
  document_id uuid not null references public.pc_documents(document_id) on delete cascade,
  entity_id text not null,
  relationship text not null default 'mentions',
  confidence numeric,
  evidence jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique(document_id, entity_id, relationship)
);

alter table public.pc_document_entity_links add column if not exists entity_id text;
alter table public.pc_document_entity_links add column if not exists relationship text default 'mentions';
alter table public.pc_document_entity_links add column if not exists confidence numeric;
alter table public.pc_document_entity_links add column if not exists evidence jsonb default '{}'::jsonb;
alter table public.pc_document_entity_links add column if not exists created_at timestamptz default now();

-- ---------------------------------------------------------------------------
-- Document authors
-- ---------------------------------------------------------------------------
create table if not exists public.pc_document_authors (
  document_author_id uuid primary key default gen_random_uuid(),
  document_id uuid not null references public.pc_documents(document_id) on delete cascade,
  author_name text not null,
  author_entity_id text,
  metadata jsonb not null default '{}'::jsonb,
  unique(document_id, author_name)
);

alter table public.pc_document_authors add column if not exists author_entity_id text;
alter table public.pc_document_authors add column if not exists metadata jsonb default '{}'::jsonb;

-- ---------------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------------
create index if not exists pc_documents_source_entity_idx
  on public.pc_documents(source_entity_id);
create index if not exists pc_documents_date_idx
  on public.pc_documents(published_date desc);
create index if not exists pc_documents_products_gin
  on public.pc_documents using gin(products);
create index if not exists pc_documents_topics_gin
  on public.pc_documents using gin(topics);
create index if not exists pc_documents_geographies_gin
  on public.pc_documents using gin(geographies);
create index if not exists pc_documents_search_fts
  on public.pc_documents using gin(to_tsvector('english', coalesce(search_text,'')));
create index if not exists pc_document_entity_links_entity_idx
  on public.pc_document_entity_links(entity_id);

-- ---------------------------------------------------------------------------
-- Permissions
-- ---------------------------------------------------------------------------
revoke all on public.pc_documents from anon, authenticated;
revoke all on public.pc_document_entity_links from anon, authenticated;
revoke all on public.pc_document_authors from anon, authenticated;

grant select, insert, update, delete on public.pc_documents to service_role, postgres;
grant select, insert, update, delete on public.pc_document_entity_links to service_role, postgres;
grant select, insert, update, delete on public.pc_document_authors to service_role, postgres;
