-- Power & Corridors
-- Horizon + reporting + event impacts extension
-- 17 September 2026

begin;

-- 1) Extend canonical events for forward-looking / scheduled material.
alter table public.pc_events
    add column if not exists event_temporality text,
    add column if not exists event_phase text,
    add column if not exists event_category text,
    add column if not exists event_subcategory text,
    add column if not exists all_day boolean default false,
    add column if not exists date_precision text,
    add column if not exists expected_attendance integer,
    add column if not exists expected_disruption text,
    add column if not exists impact_probability text,
    add column if not exists impact_horizon text,
    add column if not exists baseline_condition text,
    add column if not exists trigger_threshold text,
    add column if not exists recurrence_rule text,
    add column if not exists parent_event_id text,
    add column if not exists calendar_year integer,
    add column if not exists verification_status text,
    add column if not exists last_verified_at timestamptz;

create index if not exists idx_pc_events_temporality
    on public.pc_events(event_temporality, start_date);

create index if not exists idx_pc_events_category
    on public.pc_events(event_category, start_date);

create index if not exists idx_pc_events_calendar_year
    on public.pc_events(calendar_year, start_date);

-- 2) Normalized multi-domain impacts.
create table if not exists public.pc_event_impacts (
    impact_id uuid primary key default gen_random_uuid(),
    event_id text not null references public.pc_events(event_id) on delete cascade,
    impact_domain text not null,
    impact_type text,
    impact_level text,
    expected boolean not null default true,
    probability text,
    start_date timestamptz,
    end_date timestamptz,
    geography text,
    description text,
    confidence text,
    source_id text references public.pc_sources(source_id),
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_pc_event_impacts_event
    on public.pc_event_impacts(event_id);

create index if not exists idx_pc_event_impacts_domain
    on public.pc_event_impacts(impact_domain, impact_level);

-- 3) Persistent publication/report layer.
create table if not exists public.pc_reports (
    report_id uuid primary key default gen_random_uuid(),
    report_type text not null,
    report_title text not null,
    geography text,
    period_start date,
    period_end date,
    publication_date date,
    status text not null default 'draft',
    template_key text,
    executive_summary text,
    planning_assumption text,
    analyst_notes text,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.pc_report_sections (
    report_section_id uuid primary key default gen_random_uuid(),
    report_id uuid not null references public.pc_reports(report_id) on delete cascade,
    section_key text not null,
    section_title text not null,
    sort_order integer not null default 0,
    section_summary text,
    metadata jsonb not null default '{}'::jsonb,
    unique(report_id, section_key)
);

create table if not exists public.pc_report_stories (
    report_story_id uuid primary key default gen_random_uuid(),
    report_id uuid not null references public.pc_reports(report_id) on delete cascade,
    report_section_id uuid references public.pc_report_sections(report_section_id) on delete set null,
    event_id text references public.pc_events(event_id) on delete set null,
    headline text not null,
    analyst_risk_rating text,
    analyst_trend text,
    situation_update text,
    assessment_impact text,
    business_implications text,
    mitigations text,
    target_word_count integer,
    sort_order integer not null default 0,
    ai_generated boolean not null default false,
    ai_model text,
    analyst_approved boolean not null default false,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.pc_report_story_sources (
    report_story_source_id uuid primary key default gen_random_uuid(),
    report_story_id uuid not null references public.pc_report_stories(report_story_id) on delete cascade,
    source_id text references public.pc_sources(source_id),
    source_url text,
    source_reference_number integer,
    notes text,
    unique(report_story_id, source_reference_number)
);

create index if not exists idx_pc_reports_pubdate
    on public.pc_reports(publication_date desc);

create index if not exists idx_pc_report_stories_event
    on public.pc_report_stories(event_id);

-- 4) Helpful view for horizon consumers.
create or replace view public.v_pc_horizon_events as
select
    e.*,
    case
        when e.start_date < now() and coalesce(e.end_date,e.start_date) >= now() then 'active'
        when e.start_date >= now() then 'upcoming'
        when coalesce(e.end_date,e.start_date) < now() then 'completed'
        else coalesce(e.event_phase,'unknown')
    end as derived_phase
from public.pc_events e
where
    coalesce(e.event_temporality,'') in ('scheduled','forecast','recurring','seasonal')
    or coalesce(e.event_category,'') in (
        'election','referendum','anniversary','holiday','summit','conference',
        'sporting_event','mass_gathering','planned_protest','strike',
        'military_exercise','regulatory_deadline','sanctions_deadline',
        'planned_closure','seasonal_hazard'
    );

commit;
