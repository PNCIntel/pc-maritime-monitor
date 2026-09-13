
begin;

create table if not exists pc_contacts (
    contact_id uuid primary key default gen_random_uuid(),
    name text null,
    email text not null,
    organisation text null,
    role_title text null,
    country text null,
    subscription_status text not null default 'subscribed',
    consent_source text null,
    source text null,
    notes text null,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create unique index if not exists uq_pc_contacts_email_lower
    on pc_contacts(lower(email));

create table if not exists pc_distribution_lists (
    distribution_list_id uuid primary key default gen_random_uuid(),
    name text not null,
    description text null,
    product_scope text null,
    active boolean not null default true,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create unique index if not exists uq_pc_distribution_lists_name_lower
    on pc_distribution_lists(lower(name));

create table if not exists pc_distribution_memberships (
    distribution_membership_id uuid primary key default gen_random_uuid(),
    distribution_list_id uuid not null references pc_distribution_lists(distribution_list_id) on delete cascade,
    contact_id uuid not null references pc_contacts(contact_id) on delete cascade,
    status text not null default 'active',
    joined_at timestamptz not null default now(),
    metadata jsonb not null default '{}'::jsonb,
    unique(distribution_list_id,contact_id)
);

create table if not exists pc_email_import_jobs (
    email_import_job_id uuid primary key default gen_random_uuid(),
    file_name text null,
    status text not null default 'completed',
    rows_seen integer not null default 0,
    contacts_upserted integer not null default 0,
    memberships_upserted integer not null default 0,
    errors jsonb not null default '[]'::jsonb,
    created_at timestamptz not null default now()
);

commit;
