
-- ============================================================================
-- P&C Intelligence — Event Actor Link Backfill v5
-- Conservative actor-event linking from reviewed audit candidates
-- 2026-09-15
--
-- Principle:
--   A text mention is NOT automatically an attribution.
--   Initial links are created as:
--       actor_role          = referenced_actor
--       attribution_status  = associated
--       confidence          = medium
--       analyst_reviewed    = false
--
-- Existing event/actor links are never overwritten.
-- ============================================================================

begin;

-- --------------------------------------------------------------------------
-- 1. Candidate view: only pc_events evidence, deduplicated to one actor/event.
-- --------------------------------------------------------------------------

create or replace view public.v_pc_event_actor_backfill_candidates as
select
    h.source_record_id as event_id,
    h.actor_id,
    min(h.suggested_canonical_name) as canonical_actor,
    min(h.suggested_actor_class) as actor_class,
    string_agg(distinct h.term, ', ' order by h.term) as matched_aliases,
    string_agg(distinct h.source_column, ', ' order by h.source_column) as matched_columns,
    min(h.matched_value) as sample_text
from public.v_pc_actor_database_operational_hits h
where h.source_table = 'pc_events'
  and h.actor_id is not null
  and h.source_record_id is not null
  and h.source_column in (
      'title',
      'description',
      'operational_impact',
      'location'
  )
group by
    h.source_record_id,
    h.actor_id;

-- --------------------------------------------------------------------------
-- 2. Review queue: candidates not already represented in pc_event_actor_links.
-- --------------------------------------------------------------------------

create or replace view public.v_pc_event_actor_backfill_review as
select
    c.*
from public.v_pc_event_actor_backfill_candidates c
where not exists (
    select 1
    from public.pc_event_actor_links l
    where l.event_id = c.event_id
      and l.actor_id = c.actor_id
);

-- --------------------------------------------------------------------------
-- 3. Conservative insert.
--
-- Important: this does NOT assign "initiator", "target", "controller", etc.
-- Those roles require analyst review of the event context.
-- --------------------------------------------------------------------------

insert into public.pc_event_actor_links (
    event_id,
    actor_id,
    actor_role,
    attribution_status,
    confidence,
    link_basis,
    source_id,
    analyst_reviewed,
    metadata
)
select
    c.event_id,
    c.actor_id,
    'referenced_actor' as actor_role,
    'associated' as attribution_status,
    'medium' as confidence,
    'Database-wide actor audit matched canonical actor via: '
        || c.matched_aliases
        || '. Matched columns: '
        || c.matched_columns
        as link_basis,
    null as source_id,
    false as analyst_reviewed,
    jsonb_build_object(
        'backfill_version', 'actor_link_backfill_v5',
        'method', 'precision_term_match',
        'canonical_actor', c.canonical_actor,
        'actor_class', c.actor_class,
        'matched_aliases', c.matched_aliases,
        'matched_columns', c.matched_columns,
        'sample_text', c.sample_text
    ) as metadata
from public.v_pc_event_actor_backfill_review c;

-- --------------------------------------------------------------------------
-- 4. Analyst role-review queue.
-- --------------------------------------------------------------------------

create or replace view public.v_pc_event_actor_role_review as
select
    l.event_actor_link_id,
    l.event_id,
    e.start_date,
    e.event_type,
    e.severity,
    e.title,
    e.description,
    a.actor_id,
    a.canonical_name,
    a.short_name,
    a.actor_class,
    l.actor_role,
    l.attribution_status,
    l.confidence,
    l.link_basis,
    l.source_id,
    l.analyst_reviewed,
    l.metadata,
    l.created_at,
    l.updated_at
from public.pc_event_actor_links l
join public.pc_actors a
  on a.actor_id = l.actor_id
left join public.pc_events e
  on e.event_id = l.event_id
where l.actor_role = 'referenced_actor'
  and l.analyst_reviewed = false;

commit;

-- ============================================================================
-- POST-RUN CHECKS
-- ============================================================================

-- A. How many actor/event links exist now?
-- select
--     a.canonical_name,
--     count(distinct l.event_id) as linked_events
-- from public.pc_actors a
-- left join public.pc_event_actor_links l
--   on l.actor_id = a.actor_id
-- group by a.actor_id, a.canonical_name
-- order by linked_events desc, a.canonical_name;

-- B. Review unclassified roles:
-- select *
-- from public.v_pc_event_actor_role_review
-- order by start_date desc nulls last, canonical_name;

-- C. App-ready actor directory should now show linked events:
-- select *
-- from public.v_pc_actor_directory
-- order by linked_events desc, canonical_name;

-- D. Confirm no duplicate event/actor links were created:
-- select
--     event_id,
--     actor_id,
--     count(*) as links
-- from public.pc_event_actor_links
-- group by event_id, actor_id
-- having count(*) > 1
-- order by links desc, event_id;
