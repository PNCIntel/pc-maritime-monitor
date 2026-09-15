
-- ============================================================================
-- P&C Intelligence — Actor Registry v4
-- Canonical actor expansion + designation layer + app-ready views
-- Built against actual pc_actors schema confirmed 2026-09-15
-- ============================================================================

begin;

-- --------------------------------------------------------------------------
-- 1. Canonical actor additions
--
-- actor_class is organisational, not a legal designation.
-- Legal / sanctions / terrorism designations belong in pc_actor_designations.
-- --------------------------------------------------------------------------

insert into public.pc_actors (
    canonical_name,
    short_name,
    actor_class,
    actor_subtype,
    status,
    primary_country,
    countries,
    description,
    confidence,
    designation_summary,
    metadata,
    created_at,
    updated_at
)
select *
from (
    values
    (
        'Hamas',
        'Hamas',
        'armed_group',
        'Palestinian non-state armed and political organisation',
        'active',
        'Palestinian Territories',
        array['Palestinian Territories']::text[],
        'Canonical P&C actor record for Hamas references.',
        'high',
        '{}'::jsonb,
        '{"seed":"actor_registry_v4"}'::jsonb,
        now(),
        now()
    ),
    (
        'Hezbollah',
        'Hezbollah',
        'armed_group',
        'Lebanese non-state armed and political organisation',
        'active',
        'Lebanon',
        array['Lebanon']::text[],
        'Canonical P&C actor record for Hezbollah references.',
        'high',
        '{}'::jsonb,
        '{"seed":"actor_registry_v4"}'::jsonb,
        now(),
        now()
    ),
    (
        'Islamic State',
        'ISIS',
        'armed_group',
        'Transnational jihadist armed organisation',
        'active',
        null,
        array[]::text[],
        'Canonical P&C actor record for Islamic State / ISIS / ISIL references.',
        'high',
        '{}'::jsonb,
        '{"seed":"actor_registry_v4"}'::jsonb,
        now(),
        now()
    ),
    (
        'Islamic State Khorasan Province',
        'ISKP',
        'armed_group',
        'Islamic State regional affiliate',
        'active',
        'Afghanistan',
        array['Afghanistan','Pakistan']::text[],
        'Canonical P&C actor record for Islamic State Khorasan Province / ISIS-K / ISKP references.',
        'high',
        '{}'::jsonb,
        '{"seed":"actor_registry_v4"}'::jsonb,
        now(),
        now()
    ),
    (
        'al-Qaeda',
        'AQ',
        'armed_network',
        'Transnational jihadist armed network',
        'active',
        null,
        array[]::text[],
        'Canonical P&C actor record for al-Qaeda references.',
        'high',
        '{}'::jsonb,
        '{"seed":"actor_registry_v4"}'::jsonb,
        now(),
        now()
    ),
    (
        'Al-Qaeda in the Arabian Peninsula',
        'AQAP',
        'armed_group',
        'al-Qaeda regional affiliate',
        'active',
        'Yemen',
        array['Yemen']::text[],
        'Canonical P&C actor record for Al-Qaeda in the Arabian Peninsula / AQAP references.',
        'high',
        '{}'::jsonb,
        '{"seed":"actor_registry_v4"}'::jsonb,
        now(),
        now()
    ),
    (
        'al-Shabaab',
        'al-Shabaab',
        'armed_group',
        'Somalia-based jihadist armed organisation',
        'active',
        'Somalia',
        array['Somalia','Kenya']::text[],
        'Canonical P&C actor record for al-Shabaab references.',
        'high',
        '{}'::jsonb,
        '{"seed":"actor_registry_v4"}'::jsonb,
        now(),
        now()
    ),
    (
        'Palestinian Islamic Jihad',
        'PIJ',
        'armed_group',
        'Palestinian non-state armed organisation',
        'active',
        'Palestinian Territories',
        array['Palestinian Territories']::text[],
        'Canonical P&C actor record for Palestinian Islamic Jihad / PIJ references.',
        'high',
        '{}'::jsonb,
        '{"seed":"actor_registry_v4"}'::jsonb,
        now(),
        now()
    )
) as v(
    canonical_name,
    short_name,
    actor_class,
    actor_subtype,
    status,
    primary_country,
    countries,
    description,
    confidence,
    designation_summary,
    metadata,
    created_at,
    updated_at
)
where not exists (
    select 1
    from public.pc_actors a
    where lower(trim(a.canonical_name)) = lower(trim(v.canonical_name))
);

-- --------------------------------------------------------------------------
-- 2. Map audit terms to the newly-created canonical actors.
-- --------------------------------------------------------------------------

update public.pc_actor_audit_terms t
set actor_id = a.actor_id
from public.pc_actors a
where t.actor_id is null
  and t.suggested_canonical_name is not null
  and lower(trim(a.canonical_name)) = lower(trim(t.suggested_canonical_name));

-- --------------------------------------------------------------------------
-- 3. Separate legal / sanctions / terrorism designation layer.
-- --------------------------------------------------------------------------

create table if not exists public.pc_actor_designations (
    actor_designation_id uuid primary key default gen_random_uuid(),
    actor_id uuid not null references public.pc_actors(actor_id) on delete cascade,
    authority text not null,
    designation_name text,
    designation_type text,
    programme text,
    effective_date date,
    end_date date,
    status text not null default 'active',
    source_id text,
    source_url text,
    notes text,
    confidence text,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_pc_actor_designations_actor
    on public.pc_actor_designations(actor_id);

create index if not exists idx_pc_actor_designations_authority
    on public.pc_actor_designations(authority);

create unique index if not exists uq_pc_actor_designation_identity
    on public.pc_actor_designations (
        actor_id,
        lower(authority),
        lower(coalesce(designation_name,'')),
        lower(coalesce(designation_type,'')),
        coalesce(effective_date, date '0001-01-01')
    );

-- --------------------------------------------------------------------------
-- 4. Keep pc_actors.designation_summary useful as a cached UI summary.
--    This view is authoritative; designation_summary can later be refreshed
--    from it if/when designation records are populated.
-- --------------------------------------------------------------------------

create or replace view public.v_pc_actor_designation_summary as
select
    a.actor_id,
    a.canonical_name,
    count(d.actor_designation_id) as designation_count,
    coalesce(
        jsonb_agg(
            jsonb_build_object(
                'authority', d.authority,
                'designation_name', d.designation_name,
                'designation_type', d.designation_type,
                'programme', d.programme,
                'effective_date', d.effective_date,
                'status', d.status,
                'source_url', d.source_url
            )
            order by d.authority, d.effective_date
        ) filter (where d.actor_designation_id is not null),
        '[]'::jsonb
    ) as designations
from public.pc_actors a
left join public.pc_actor_designations d
  on d.actor_id = a.actor_id
group by a.actor_id, a.canonical_name;

-- --------------------------------------------------------------------------
-- 5. App-ready actor profile view.
-- --------------------------------------------------------------------------

create or replace view public.v_pc_actor_profiles as
select
    a.actor_id,
    a.legacy_actor_id,
    a.canonical_name,
    a.short_name,
    a.actor_class,
    a.actor_subtype,
    a.status,
    a.primary_country,
    a.countries,
    a.description,
    a.confidence,
    a.designation_summary,
    a.metadata,
    a.created_at,
    a.updated_at,
    coalesce(s.designation_count,0) as designation_count,
    coalesce(s.designations,'[]'::jsonb) as designations
from public.pc_actors a
left join public.v_pc_actor_designation_summary s
  on s.actor_id = a.actor_id;

-- --------------------------------------------------------------------------
-- 6. App-ready activity summary.
--    Uses pc_event_actor_links if present. Roles remain distinct.
-- --------------------------------------------------------------------------

create or replace view public.v_pc_actor_event_activity as
select
    a.actor_id,
    a.canonical_name,
    a.short_name,
    a.actor_class,
    a.actor_subtype,
    a.status,
    count(distinct l.event_id) as linked_events,
    max(e.start_date) as latest_event_date,
    count(distinct l.event_id) filter (
        where lower(coalesce(e.severity,'')) in ('high','critical','severe')
    ) as high_critical_events,
    count(distinct l.actor_role) as distinct_roles,
    string_agg(distinct l.actor_role, ', ' order by l.actor_role)
        filter (where l.actor_role is not null and trim(l.actor_role) <> '')
        as roles_seen
from public.pc_actors a
left join public.pc_event_actor_links l
  on l.actor_id = a.actor_id
left join public.pc_events e
  on e.event_id = l.event_id
group by
    a.actor_id,
    a.canonical_name,
    a.short_name,
    a.actor_class,
    a.actor_subtype,
    a.status;

-- --------------------------------------------------------------------------
-- 7. Unified Actors & Networks directory view for the Intelligence app.
-- --------------------------------------------------------------------------

create or replace view public.v_pc_actor_directory as
select
    p.actor_id,
    p.legacy_actor_id,
    p.canonical_name,
    p.short_name,
    p.actor_class,
    p.actor_subtype,
    p.status,
    p.primary_country,
    p.countries,
    p.description,
    p.confidence,
    p.designation_count,
    p.designations,
    coalesce(ev.linked_events,0) as linked_events,
    ev.latest_event_date,
    coalesce(ev.high_critical_events,0) as high_critical_events,
    coalesce(ev.distinct_roles,0) as distinct_roles,
    ev.roles_seen
from public.v_pc_actor_profiles p
left join public.v_pc_actor_event_activity ev
  on ev.actor_id = p.actor_id;

commit;

-- ============================================================================
-- RUN AFTER INSTALL
-- ============================================================================

-- 1. Confirm actor registry:
-- select
--     actor_id,
--     legacy_actor_id,
--     canonical_name,
--     short_name,
--     actor_class,
--     actor_subtype,
--     status,
--     primary_country,
--     countries
-- from public.pc_actors
-- order by canonical_name;

-- 2. Confirm all audit terms now map where a canonical actor exists:
-- select *
-- from public.v_pc_actor_term_mapping_status
-- order by mapping_status, suggested_canonical_name nulls last, term;

-- 3. Re-run database audit after actor additions:
-- call public.refresh_pc_actor_database_audit();

-- 4. Clean operational counts:
-- select *
-- from public.v_pc_actor_operational_canonical_summary
-- order by operational_records desc, canonical_actor;

-- 5. App-ready directory:
-- select *
-- from public.v_pc_actor_directory
-- order by linked_events desc, canonical_name;

-- 6. Actors with no event links yet:
-- select *
-- from public.v_pc_actor_directory
-- where linked_events = 0
-- order by canonical_name;
