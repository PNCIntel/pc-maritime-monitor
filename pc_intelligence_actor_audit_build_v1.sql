-- Power & Corridors Intelligence
-- Actors & Networks: canonical schema + audit layer
-- Version: 1.0 | 2026-09-15
-- Target: Supabase / PostgreSQL
--
-- Design principles:
-- 1) Keep actors canonical; aliases resolve to one actor.
-- 2) Do NOT infer event role from a text mention.
-- 3) Audit mentions first; create event-actor links only after analyst review.
-- 4) Preserve legacy actor IDs (e.g. ACT007 for PKK) where known.
-- 5) event_id is stored as text in the link/audit layer so this migration works
--    whether pc_events.event_id is text, uuid, or another scalar type.

begin;

create extension if not exists pgcrypto;

-- -----------------------------------------------------------------------------
-- 1. Canonical actors
-- -----------------------------------------------------------------------------
create table if not exists public.pc_actors (
    actor_id uuid primary key default gen_random_uuid(),
    legacy_actor_id text unique,
    canonical_name text not null,
    short_name text,
    actor_class text not null,
    actor_subtype text,
    status text default 'active',
    primary_country text,
    countries text[] default '{}'::text[],
    description text,
    confidence text default 'medium',
    designation_summary jsonb default '{}'::jsonb,
    metadata jsonb default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint pc_actors_actor_class_chk check (actor_class in (
        'state',
        'government',
        'military',
        'state_security',
        'armed_group',
        'armed_network',
        'paramilitary',
        'terrorist_group',
        'criminal_network',
        'smuggling_network',
        'piracy_network',
        'political_group',
        'unknown_network',
        'other'
    )),
    constraint pc_actors_confidence_chk check (confidence in ('high','medium','low','unknown'))
);

create unique index if not exists ux_pc_actors_canonical_name_ci
    on public.pc_actors (lower(canonical_name));
create index if not exists ix_pc_actors_class on public.pc_actors(actor_class);
create index if not exists ix_pc_actors_status on public.pc_actors(status);

-- -----------------------------------------------------------------------------
-- 2. Aliases / alternate names
-- -----------------------------------------------------------------------------
create table if not exists public.pc_actor_aliases (
    alias_id uuid primary key default gen_random_uuid(),
    actor_id uuid not null references public.pc_actors(actor_id) on delete cascade,
    alias text not null,
    alias_type text default 'alias',
    language text,
    is_primary boolean not null default false,
    source_note text,
    created_at timestamptz not null default now()
);

create unique index if not exists ux_pc_actor_aliases_alias_ci
    on public.pc_actor_aliases (lower(alias));
create index if not exists ix_pc_actor_aliases_actor on public.pc_actor_aliases(actor_id);

-- -----------------------------------------------------------------------------
-- 3. Actor-to-actor relationships
-- -----------------------------------------------------------------------------
create table if not exists public.pc_actor_relationships (
    actor_relationship_id uuid primary key default gen_random_uuid(),
    from_actor_id uuid not null references public.pc_actors(actor_id) on delete cascade,
    to_actor_id uuid not null references public.pc_actors(actor_id) on delete cascade,
    relationship_type text not null,
    relationship_class text,
    status text default 'active',
    confidence text default 'medium',
    basis text,
    source_id text,
    start_date date,
    end_date date,
    metadata jsonb default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint pc_actor_relationships_not_self_chk check (from_actor_id <> to_actor_id),
    constraint pc_actor_relationships_confidence_chk check (confidence in ('high','medium','low','unknown'))
);

create index if not exists ix_pc_actor_relationships_from on public.pc_actor_relationships(from_actor_id);
create index if not exists ix_pc_actor_relationships_to on public.pc_actor_relationships(to_actor_id);
create index if not exists ix_pc_actor_relationships_type on public.pc_actor_relationships(relationship_type);

-- -----------------------------------------------------------------------------
-- 4. Event-to-actor links
--    event_id intentionally text; join to pc_events with e.event_id::text.
-- -----------------------------------------------------------------------------
create table if not exists public.pc_event_actor_links (
    event_actor_link_id uuid primary key default gen_random_uuid(),
    event_id text not null,
    actor_id uuid not null references public.pc_actors(actor_id) on delete cascade,
    actor_role text not null,
    attribution_status text default 'associated',
    confidence text default 'medium',
    link_basis text,
    source_id text,
    analyst_reviewed boolean not null default false,
    metadata jsonb default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint pc_event_actor_links_confidence_chk check (confidence in ('high','medium','low','unknown')),
    constraint pc_event_actor_links_attribution_chk check (attribution_status in (
        'confirmed',
        'claimed',
        'assessed',
        'probable',
        'possible',
        'suspected',
        'associated',
        'context_only',
        'disputed',
        'unknown'
    ))
);

create unique index if not exists ux_pc_event_actor_link_identity
    on public.pc_event_actor_links(event_id, actor_id, actor_role, attribution_status);
create index if not exists ix_pc_event_actor_links_event on public.pc_event_actor_links(event_id);
create index if not exists ix_pc_event_actor_links_actor on public.pc_event_actor_links(actor_id);
create index if not exists ix_pc_event_actor_links_role on public.pc_event_actor_links(actor_role);

-- -----------------------------------------------------------------------------
-- 5. Audit dictionary
--    This is intentionally broader than the canonical actor registry. It lets us
--    find groups mentioned anywhere in event text before deciding whether they
--    should become / map to canonical actors.
-- -----------------------------------------------------------------------------
create table if not exists public.pc_actor_audit_terms (
    audit_term_id uuid primary key default gen_random_uuid(),
    term text not null,
    suggested_canonical_name text,
    suggested_actor_class text,
    actor_id uuid references public.pc_actors(actor_id) on delete set null,
    enabled boolean not null default true,
    notes text,
    created_at timestamptz not null default now()
);

create unique index if not exists ux_pc_actor_audit_terms_term_ci
    on public.pc_actor_audit_terms(lower(term));

-- -----------------------------------------------------------------------------
-- 6. Seed actors already evidenced in the existing P&C actor model, plus Houthis
-- -----------------------------------------------------------------------------
insert into public.pc_actors
    (legacy_actor_id, canonical_name, short_name, actor_class, actor_subtype, status, primary_country, countries, description, confidence, metadata)
values
    ('ACT007', 'Kurdistan Workers'' Party', 'PKK', 'armed_group', 'non-state armed group', 'disarmament process', 'Türkiye', array['Türkiye','Iraq'], 'Legacy P&C actor model record.', 'high', '{"seed":"legacy_model"}'::jsonb),
    ('ACT009', 'Islamic Revolutionary Guard Corps', 'IRGC', 'state_security', 'state military / security', 'active', 'Iran', array['Iran'], 'Legacy P&C actor model record.', 'high', '{"seed":"legacy_model"}'::jsonb),
    ('ACT010', 'Iran-backed Iraqi militia groups', 'Iran-aligned Iraqi militias', 'armed_network', 'umbrella category', 'active', 'Iraq', array['Iraq'], 'Analytical umbrella; use a named faction when verified.', 'high', '{"seed":"legacy_model"}'::jsonb),
    ('ACT011', 'Islamic Resistance in Iraq', 'IRI', 'armed_network', 'operational armed-group umbrella', 'active', 'Iraq', array['Iraq'], 'Legacy P&C actor model record.', 'high', '{"seed":"legacy_model"}'::jsonb),
    ('ACT012', 'Kataib Hezbollah', 'KH', 'armed_group', 'PMF-linked armed group', 'active', 'Iraq', array['Iraq'], 'Legacy P&C actor model record.', 'high', '{"seed":"legacy_model"}'::jsonb),
    ('ACT013', 'Harakat al-Nujaba', 'HaN', 'armed_group', 'Iran-aligned Iraqi armed group', 'active', 'Iraq', array['Iraq'], 'Legacy P&C actor model record.', 'high', '{"seed":"legacy_model"}'::jsonb),
    (null, 'Ansar Allah', 'Houthis', 'armed_group', 'Yemeni armed movement', 'active', 'Yemen', array['Yemen'], 'Canonical actor for Houthi / Ansar Allah references.', 'high', '{"seed":"actor_audit_v1"}'::jsonb)
on conflict do nothing;

-- -----------------------------------------------------------------------------
-- 7. Seed aliases for known actors
-- -----------------------------------------------------------------------------
with a as (
    select actor_id, canonical_name from public.pc_actors
)
insert into public.pc_actor_aliases(actor_id, alias, alias_type, is_primary, source_note)
select actor_id, alias, alias_type, is_primary, 'P&C actor audit v1'
from (
    select actor_id, 'Kurdistan Workers'' Party'::text alias, 'canonical'::text alias_type, true is_primary from a where canonical_name='Kurdistan Workers'' Party'
    union all select actor_id, 'PKK', 'abbreviation', false from a where canonical_name='Kurdistan Workers'' Party'

    union all select actor_id, 'Islamic Revolutionary Guard Corps', 'canonical', true from a where canonical_name='Islamic Revolutionary Guard Corps'
    union all select actor_id, 'IRGC', 'abbreviation', false from a where canonical_name='Islamic Revolutionary Guard Corps'
    union all select actor_id, 'Revolutionary Guards', 'alias', false from a where canonical_name='Islamic Revolutionary Guard Corps'

    union all select actor_id, 'Iran-backed Iraqi militia groups', 'canonical', true from a where canonical_name='Iran-backed Iraqi militia groups'
    union all select actor_id, 'Iran-backed Iraqi militias', 'alias', false from a where canonical_name='Iran-backed Iraqi militia groups'
    union all select actor_id, 'Iran-aligned Iraqi militias', 'alias', false from a where canonical_name='Iran-backed Iraqi militia groups'

    union all select actor_id, 'Islamic Resistance in Iraq', 'canonical', true from a where canonical_name='Islamic Resistance in Iraq'
    union all select actor_id, 'IRI', 'abbreviation', false from a where canonical_name='Islamic Resistance in Iraq'

    union all select actor_id, 'Kataib Hezbollah', 'canonical', true from a where canonical_name='Kataib Hezbollah'
    union all select actor_id, 'Kata''ib Hezbollah', 'alias', false from a where canonical_name='Kataib Hezbollah'
    union all select actor_id, 'KH', 'abbreviation', false from a where canonical_name='Kataib Hezbollah'

    union all select actor_id, 'Harakat al-Nujaba', 'canonical', true from a where canonical_name='Harakat al-Nujaba'
    union all select actor_id, 'Harakat Hezbollah al-Nujaba', 'alias', false from a where canonical_name='Harakat al-Nujaba'

    union all select actor_id, 'Ansar Allah', 'canonical', true from a where canonical_name='Ansar Allah'
    union all select actor_id, 'Ansarallah', 'alias', false from a where canonical_name='Ansar Allah'
    union all select actor_id, 'Houthis', 'alias', false from a where canonical_name='Ansar Allah'
    union all select actor_id, 'Houthi', 'alias', false from a where canonical_name='Ansar Allah'
    union all select actor_id, 'Houthi movement', 'alias', false from a where canonical_name='Ansar Allah'
) s
on conflict do nothing;

-- -----------------------------------------------------------------------------
-- 8. Seed broad discovery terms. These do NOT auto-create actors or links.
--    They are only used to identify likely records for analyst review.
-- -----------------------------------------------------------------------------
insert into public.pc_actor_audit_terms(term, suggested_canonical_name, suggested_actor_class, actor_id, notes)
select v.term, v.canonical_name, v.actor_class, a.actor_id, v.notes
from (values
    ('Houthi', 'Ansar Allah', 'armed_group', 'Known alias'),
    ('Houthis', 'Ansar Allah', 'armed_group', 'Known alias'),
    ('Ansar Allah', 'Ansar Allah', 'armed_group', 'Known canonical name'),
    ('Ansarallah', 'Ansar Allah', 'armed_group', 'Known alias'),
    ('PKK', 'Kurdistan Workers'' Party', 'armed_group', 'Known abbreviation'),
    ('Kurdistan Workers'' Party', 'Kurdistan Workers'' Party', 'armed_group', 'Known canonical name'),
    ('Islamic Resistance in Iraq', 'Islamic Resistance in Iraq', 'armed_network', 'Known actor'),
    ('Kataib Hezbollah', 'Kataib Hezbollah', 'armed_group', 'Known actor'),
    ('Kata''ib Hezbollah', 'Kataib Hezbollah', 'armed_group', 'Known alias'),
    ('Harakat al-Nujaba', 'Harakat al-Nujaba', 'armed_group', 'Known actor'),
    ('IRGC', 'Islamic Revolutionary Guard Corps', 'state_security', 'Known abbreviation'),
    ('Islamic Revolutionary Guard Corps', 'Islamic Revolutionary Guard Corps', 'state_security', 'Known canonical name'),
    ('Hezbollah', 'Hezbollah', 'armed_group', 'Discovery only; review before creating canonical actor'),
    ('Hamas', 'Hamas', 'armed_group', 'Discovery only; review before creating canonical actor'),
    ('Palestinian Islamic Jihad', 'Palestinian Islamic Jihad', 'armed_group', 'Discovery only; review before creating canonical actor'),
    ('PIJ', 'Palestinian Islamic Jihad', 'armed_group', 'Discovery only; short term may create false positives'),
    ('al-Shabaab', 'al-Shabaab', 'terrorist_group', 'Discovery only; review before creating canonical actor'),
    ('Al Shabaab', 'al-Shabaab', 'terrorist_group', 'Discovery alias'),
    ('ISIS', 'Islamic State', 'terrorist_group', 'Discovery only; review branch / geography'),
    ('ISIL', 'Islamic State', 'terrorist_group', 'Discovery only; review branch / geography'),
    ('Islamic State', 'Islamic State', 'terrorist_group', 'Discovery only; branch may be required'),
    ('ISIS-K', 'Islamic State Khorasan Province', 'terrorist_group', 'Discovery only'),
    ('ISKP', 'Islamic State Khorasan Province', 'terrorist_group', 'Discovery only'),
    ('AQAP', 'Al-Qaeda in the Arabian Peninsula', 'terrorist_group', 'Discovery only'),
    ('Al-Qaeda in the Arabian Peninsula', 'Al-Qaeda in the Arabian Peninsula', 'terrorist_group', 'Discovery only'),
    ('al-Qaeda', 'al-Qaeda', 'terrorist_group', 'Discovery only; affiliate may be required'),
    ('pirate action group', null, 'piracy_network', 'Generic discovery term; do not create actor automatically'),
    ('smuggling network', null, 'smuggling_network', 'Generic discovery term; do not create actor automatically'),
    ('smugglers', null, 'smuggling_network', 'Generic discovery term; do not create actor automatically'),
    ('trafficking network', null, 'criminal_network', 'Generic discovery term; do not create actor automatically')
) as v(term, canonical_name, actor_class, notes)
left join public.pc_actors a on lower(a.canonical_name)=lower(v.canonical_name)
on conflict do nothing;

-- -----------------------------------------------------------------------------
-- 9. Event corpus view used by the audit
-- -----------------------------------------------------------------------------
create or replace view public.v_pc_event_actor_corpus as
select
    e.event_id::text as event_id,
    e.start_date,
    e.event_family,
    e.event_type,
    e.severity,
    e.countries,
    e.location,
    e.title,
    e.description,
    e.operational_impact,
    e.commercial_impact,
    e.confidence as event_confidence,
    concat_ws(' ',
        coalesce(e.event_nature::text,''),
        coalesce(e.event_domain::text,''),
        coalesce(e.event_family::text,''),
        coalesce(e.event_type::text,''),
        coalesce(e.countries::text,''),
        coalesce(e.location::text,''),
        coalesce(e.title::text,''),
        coalesce(e.description::text,''),
        coalesce(e.operational_impact::text,''),
        coalesce(e.commercial_impact::text,''),
        coalesce(e.metadata::text,'')
    ) as actor_search_text
from public.pc_events e;

-- -----------------------------------------------------------------------------
-- 10. Audit hits: every event mentioning a tracked term
--     Uses conservative word-ish boundaries to reduce substring false positives.
-- -----------------------------------------------------------------------------
create or replace view public.v_pc_actor_audit_hits as
select
    c.event_id,
    c.start_date,
    c.event_family,
    c.event_type,
    c.severity,
    c.countries,
    c.location,
    c.title,
    t.audit_term_id,
    t.term as matched_term,
    t.suggested_canonical_name,
    t.suggested_actor_class,
    t.actor_id,
    case when t.actor_id is null then false else true end as canonical_actor_exists,
    c.event_confidence
from public.v_pc_event_actor_corpus c
join public.pc_actor_audit_terms t
  on t.enabled = true
 and c.actor_search_text ~* ('(^|[^[:alnum:]_])' || regexp_replace(t.term, '([\\.\\+\\*\\?\\[\\]\\^\\$\\(\\)\\{\\}=!<>|:\\-])', '\\\\\1', 'g') || '([^[:alnum:]_]|$)');

-- -----------------------------------------------------------------------------
-- 11. Missing links: canonical actor is known, event mentions it, but no reviewed
--     or unreviewed event-actor link exists yet.
-- -----------------------------------------------------------------------------
create or replace view public.v_pc_actor_mentions_missing_links as
select
    h.event_id,
    h.start_date,
    h.event_type,
    h.severity,
    h.countries,
    h.location,
    h.title,
    h.matched_term,
    h.suggested_canonical_name,
    h.actor_id,
    h.event_confidence
from public.v_pc_actor_audit_hits h
left join public.pc_event_actor_links l
  on l.event_id = h.event_id
 and l.actor_id = h.actor_id
where h.actor_id is not null
  and l.event_actor_link_id is null;

-- -----------------------------------------------------------------------------
-- 12. Unresolved actor mentions: term appears in events but no canonical actor
--     has yet been mapped. This is the main queue for finding Hezbollah, ISIS,
--     al-Shabaab, AQAP, smuggling/piracy networks, etc. already in the database.
-- -----------------------------------------------------------------------------
create or replace view public.v_pc_actor_unresolved_mentions as
select
    h.suggested_canonical_name,
    h.suggested_actor_class,
    h.matched_term,
    count(*) as event_mentions,
    min(h.start_date) as first_seen,
    max(h.start_date) as last_seen,
    array_agg(distinct h.event_id order by h.event_id) as event_ids
from public.v_pc_actor_audit_hits h
where h.actor_id is null
group by h.suggested_canonical_name, h.suggested_actor_class, h.matched_term;

-- -----------------------------------------------------------------------------
-- 13. Actor activity summary for app / analytics
-- -----------------------------------------------------------------------------
create or replace view public.v_pc_actor_activity_summary as
select
    a.actor_id,
    a.legacy_actor_id,
    a.canonical_name,
    a.short_name,
    a.actor_class,
    a.actor_subtype,
    a.status,
    a.primary_country,
    count(distinct l.event_id) as linked_events,
    count(distinct l.event_id) filter (where l.analyst_reviewed) as reviewed_events,
    max(e.start_date) as latest_event_date,
    count(distinct l.event_id) filter (where lower(coalesce(e.severity,'')) in ('critical','high')) as high_or_critical_events
from public.pc_actors a
left join public.pc_event_actor_links l on l.actor_id=a.actor_id
left join public.pc_events e on e.event_id::text=l.event_id
group by a.actor_id, a.legacy_actor_id, a.canonical_name, a.short_name, a.actor_class, a.actor_subtype, a.status, a.primary_country;

-- -----------------------------------------------------------------------------
-- 14. Useful indexes on pc_events for normal analytics. We cannot index the full
--     concatenated audit corpus via a view, but these common fields help elsewhere.
-- -----------------------------------------------------------------------------
create index if not exists ix_pc_events_start_date on public.pc_events(start_date);
create index if not exists ix_pc_events_event_type on public.pc_events(event_type);
create index if not exists ix_pc_events_event_family on public.pc_events(event_family);
create index if not exists ix_pc_events_severity on public.pc_events(severity);

commit;

-- =============================================================================
-- POST-MIGRATION AUDIT QUERIES
-- Run these after the migration.
-- =============================================================================

-- A. What actor terms are already present in the database?
-- select matched_term, suggested_canonical_name, suggested_actor_class,
--        canonical_actor_exists, count(*) as events,
--        min(start_date) as first_seen, max(start_date) as last_seen
-- from public.v_pc_actor_audit_hits
-- group by matched_term, suggested_canonical_name, suggested_actor_class, canonical_actor_exists
-- order by events desc, matched_term;

-- B. Specifically inspect Houthi / Ansar Allah records.
-- select *
-- from public.v_pc_actor_audit_hits
-- where lower(coalesce(suggested_canonical_name,''))='ansar allah'
-- order by start_date desc;

-- C. Canonical actors mentioned in events but not linked yet.
-- select *
-- from public.v_pc_actor_mentions_missing_links
-- order by start_date desc, suggested_canonical_name;

-- D. Actor/network names that need canonical review / creation.
-- select *
-- from public.v_pc_actor_unresolved_mentions
-- order by event_mentions desc, suggested_canonical_name;

-- E. Existing actor coverage summary.
-- select *
-- from public.v_pc_actor_activity_summary
-- order by linked_events desc, canonical_name;

-- IMPORTANT:
-- Do not bulk-insert pc_event_actor_links from text hits alone. A mention of an
-- actor does not establish whether it was initiator, claimant, target, sponsor,
-- negotiating party, territorial controller, contextual actor, etc. Review each
-- candidate and assign actor_role + attribution_status + confidence deliberately.
