-- P&C v1.8 document intelligence layer. Additive only.
create extension if not exists pgcrypto;

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

create table if not exists public.pc_document_authors (
  document_author_id uuid primary key default gen_random_uuid(),
  document_id uuid not null references public.pc_documents(document_id) on delete cascade,
  author_name text not null,
  author_entity_id text,
  metadata jsonb not null default '{}'::jsonb,
  unique(document_id, author_name)
);

create index if not exists pc_documents_source_entity_idx on public.pc_documents(source_entity_id);
create index if not exists pc_documents_date_idx on public.pc_documents(published_date desc);
create index if not exists pc_documents_products_gin on public.pc_documents using gin(products);
create index if not exists pc_documents_topics_gin on public.pc_documents using gin(topics);
create index if not exists pc_documents_geographies_gin on public.pc_documents using gin(geographies);
create index if not exists pc_documents_search_fts on public.pc_documents using gin(to_tsvector('english', coalesce(search_text,'')));
create index if not exists pc_document_entity_links_entity_idx on public.pc_document_entity_links(entity_id);

revoke all on public.pc_documents from anon, authenticated;
revoke all on public.pc_document_entity_links from anon, authenticated;
revoke all on public.pc_document_authors from anon, authenticated;
grant select, insert, update, delete on public.pc_documents to service_role, postgres;
grant select, insert, update, delete on public.pc_document_entity_links to service_role, postgres;
grant select, insert, update, delete on public.pc_document_authors to service_role, postgres;
