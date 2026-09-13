
begin;

create table if not exists pc_intelligence_reports (
    report_id uuid primary key default gen_random_uuid(),
    product_type text not null,
    subtype text null,
    title text not null,
    report_date date not null default current_date,
    region text null,
    status text not null default 'draft',
    confidence text null,
    summary_14 text null,
    site_path text null,
    ghost_tag text null,
    fields jsonb not null default '{}'::jsonb,
    body_markdown text null,
    web_html text null,
    email_html text null,
    source_document_id uuid null references pc_documents(document_id) on delete set null,
    created_by text null,
    approved_by text null,
    published_at timestamptz null,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_pc_intelligence_reports_type_date
    on pc_intelligence_reports(product_type, report_date desc);
create index if not exists idx_pc_intelligence_reports_status
    on pc_intelligence_reports(status, updated_at desc);

create table if not exists pc_intelligence_report_links (
    report_link_id uuid primary key default gen_random_uuid(),
    report_id uuid not null references pc_intelligence_reports(report_id) on delete cascade,
    linked_type text not null,
    linked_id text not null,
    relationship text not null default 'referenced_in',
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create index if not exists idx_pc_intelligence_report_links_target
    on pc_intelligence_report_links(linked_type, linked_id);

create table if not exists pc_intelligence_report_sources (
    report_source_id uuid primary key default gen_random_uuid(),
    report_id uuid not null references pc_intelligence_reports(report_id) on delete cascade,
    source_order integer not null default 1,
    title text null,
    publisher text null,
    source_url text null,
    source_date date null,
    source_document_id uuid null references pc_documents(document_id) on delete set null,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists pc_intelligence_report_versions (
    report_version_id uuid primary key default gen_random_uuid(),
    report_id uuid not null references pc_intelligence_reports(report_id) on delete cascade,
    version_number integer not null,
    fields jsonb not null default '{}'::jsonb,
    body_markdown text null,
    web_html text null,
    email_html text null,
    status text not null,
    created_by text null,
    created_at timestamptz not null default now(),
    unique(report_id, version_number)
);

comment on table pc_intelligence_reports is
'Analyst-authored P&C Intelligence products aligned to Alerts, Assessments, Monitoring and Situation Reports.';

commit;
