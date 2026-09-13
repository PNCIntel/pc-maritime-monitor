
begin;

create table if not exists pc_documents (
    document_id uuid primary key default gen_random_uuid(),
    title text not null,
    document_type text not null default 'research_document',
    file_name text null,
    file_sha256 text null,
    mime_type text null,
    publisher text null,
    publication_date date null,
    source_url text null,
    storage_path text null,
    extracted_text text null,
    extraction_status text not null default 'extracted',
    ingestion_job_id uuid null,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create unique index if not exists uq_pc_documents_hash
    on pc_documents(file_sha256)
    where file_sha256 is not null;

create table if not exists pc_document_links (
    document_link_id uuid primary key default gen_random_uuid(),
    document_id uuid not null references pc_documents(document_id) on delete cascade,
    linked_type text not null,
    linked_id text not null,
    relationship text not null default 'source_for',
    notes text null,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create index if not exists idx_pc_document_links_target
    on pc_document_links(linked_type, linked_id);

create table if not exists pc_document_extractions (
    document_extraction_id uuid primary key default gen_random_uuid(),
    document_id uuid not null references pc_documents(document_id) on delete cascade,
    extraction_type text not null,
    status text not null default 'draft',
    extracted_payload jsonb not null default '{}'::jsonb,
    ingestion_job_id uuid null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

comment on table pc_documents is
'Source documents, reports and uploaded files tied to companies, events, vessels, assets, programmes and intelligence products.';

commit;
