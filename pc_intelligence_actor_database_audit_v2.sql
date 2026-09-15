
-- ============================================================================
-- P&C Intelligence — Actors & Networks
-- Database-wide actor / network audit v2
-- 2026-09-15
--
-- Purpose:
--   1. Search all public pc_* tables for actor/network watch terms.
--   2. Preserve table + column + row context for review.
--   3. Do NOT automatically convert text mentions into event attribution.
--   4. Reuse canonical actor mappings already present in pc_actor_audit_terms.
-- ============================================================================

begin;

create table if not exists public.pc_actor_database_audit_hits (
    audit_hit_id uuid primary key default gen_random_uuid(),
    audit_term_id uuid,
    term text not null,
    suggested_canonical_name text,
    suggested_actor_class text,
    actor_id uuid,
    source_table text not null,
    source_column text not null,
    source_record_id text,
    matched_value text,
    row_data jsonb,
    audited_at timestamptz not null default now()
);

create index if not exists idx_pc_actor_database_audit_hits_term
    on public.pc_actor_database_audit_hits(term);

create index if not exists idx_pc_actor_database_audit_hits_actor
    on public.pc_actor_database_audit_hits(actor_id);

create index if not exists idx_pc_actor_database_audit_hits_source
    on public.pc_actor_database_audit_hits(source_table, source_column);

create index if not exists idx_pc_actor_database_audit_hits_record
    on public.pc_actor_database_audit_hits(source_record_id);

-- Prevent duplicate storage from repeat audit runs.
create unique index if not exists uq_pc_actor_database_audit_hit_dedupe
on public.pc_actor_database_audit_hits (
    coalesce(audit_term_id::text,''),
    source_table,
    source_column,
    coalesce(source_record_id,''),
    md5(coalesce(matched_value,''))
);

-- --------------------------------------------------------------------------
-- Helper: derive the most useful record identifier from a row JSON object.
-- This intentionally checks common P&C canonical keys before falling back.
-- --------------------------------------------------------------------------
create or replace function public.pc_actor_audit_record_id(j jsonb)
returns text
language sql
immutable
as $$
    select coalesce(
        j->>'event_id',
        j->>'actor_id',
        j->>'source_id',
        j->>'company_id',
        j->>'entity_id',
        j->>'asset_id',
        j->>'mobile_asset_id',
        j->>'port_id',
        j->>'location_id',
        j->>'monitoring_id',
        j->>'news_id',
        j->>'designation_id',
        j->>'programme_id',
        j->>'relationship_id',
        j->>'id'
    );
$$;

-- --------------------------------------------------------------------------
-- Main sweep procedure.
--
-- Searches:
--   - all BASE TABLES in public
--   - table name beginning pc_
--   - text/varchar/char columns
--
-- Excludes the audit machinery itself to avoid self-matches.
--
-- This is intentionally a REVIEW audit. A mention in a source, note, title,
-- sanctions record or metadata field is not automatically an attribution.
-- --------------------------------------------------------------------------
create or replace procedure public.refresh_pc_actor_database_audit()
language plpgsql
as $$
declare
    c record;
    t record;
    q text;
begin
    -- Refresh from scratch so counts stay interpretable.
    truncate table public.pc_actor_database_audit_hits;

    for c in
        select
            cols.table_schema,
            cols.table_name,
            cols.column_name
        from information_schema.columns cols
        join information_schema.tables tabs
          on tabs.table_schema = cols.table_schema
         and tabs.table_name = cols.table_name
        where cols.table_schema = 'public'
          and tabs.table_type = 'BASE TABLE'
          and cols.table_name like 'pc\_%' escape '\'
          and cols.table_name not in (
              'pc_actor_database_audit_hits',
              'pc_actor_audit_terms',
              'pc_actor_aliases',
              'pc_actor_relationships',
              'pc_event_actor_links'
          )
          and cols.data_type in (
              'text',
              'character varying',
              'character'
          )
        order by cols.table_name, cols.ordinal_position
    loop
        for t in
            select
                audit_term_id,
                term,
                suggested_canonical_name,
                suggested_actor_class,
                actor_id
            from public.pc_actor_audit_terms
            where enabled = true
              and nullif(trim(term),'') is not null
        loop
            q := format(
                $fmt$
                insert into public.pc_actor_database_audit_hits (
                    audit_term_id,
                    term,
                    suggested_canonical_name,
                    suggested_actor_class,
                    actor_id,
                    source_table,
                    source_column,
                    source_record_id,
                    matched_value,
                    row_data
                )
                select
                    %L::uuid,
                    %L,
                    %L,
                    %L,
                    %L::uuid,
                    %L,
                    %L,
                    public.pc_actor_audit_record_id(to_jsonb(x)),
                    left(x.%I::text, 4000),
                    to_jsonb(x)
                from public.%I x
                where x.%I is not null
                  and x.%I::text ilike %L
                on conflict do nothing
                $fmt$,
                t.audit_term_id,
                t.term,
                t.suggested_canonical_name,
                t.suggested_actor_class,
                t.actor_id,
                c.table_name,
                c.column_name,
                c.column_name,
                c.table_name,
                c.column_name,
                c.column_name,
                '%' || t.term || '%'
            );

            execute q;
        end loop;
    end loop;
end;
$$;

-- --------------------------------------------------------------------------
-- Summary: one row per search term, across the whole database.
-- --------------------------------------------------------------------------
create or replace view public.v_pc_actor_database_audit_summary as
select
    t.term,
    t.suggested_canonical_name,
    t.suggested_actor_class,
    t.actor_id,
    (t.actor_id is not null) as canonical_actor_exists,
    count(distinct h.source_table) as tables_with_hits,
    count(distinct (h.source_table || ':' || h.source_column)) as columns_with_hits,
    count(distinct coalesce(
        h.source_table || ':' || h.source_record_id,
        h.source_table || ':' || h.source_column || ':' || md5(coalesce(h.matched_value,''))
    )) as records_with_hits,
    count(h.audit_hit_id) as raw_hits
from public.pc_actor_audit_terms t
left join public.pc_actor_database_audit_hits h
  on h.audit_term_id = t.audit_term_id
where t.enabled = true
group by
    t.audit_term_id,
    t.term,
    t.suggested_canonical_name,
    t.suggested_actor_class,
    t.actor_id;

-- --------------------------------------------------------------------------
-- Where are actor references being found?
-- --------------------------------------------------------------------------
create or replace view public.v_pc_actor_database_locations as
select
    term,
    suggested_canonical_name,
    suggested_actor_class,
    actor_id,
    source_table,
    source_column,
    count(*) as hits,
    count(distinct source_record_id) filter (where source_record_id is not null)
        as identified_records
from public.pc_actor_database_audit_hits
group by
    term,
    suggested_canonical_name,
    suggested_actor_class,
    actor_id,
    source_table,
    source_column;

-- --------------------------------------------------------------------------
-- Canonical actors referenced somewhere in the database.
-- --------------------------------------------------------------------------
create or replace view public.v_pc_actor_database_canonical_mentions as
select
    h.*
from public.pc_actor_database_audit_hits h
where h.actor_id is not null;

-- --------------------------------------------------------------------------
-- Terms found in the database but not yet mapped to a canonical actor.
-- These are candidates for actor creation / alias resolution.
-- --------------------------------------------------------------------------
create or replace view public.v_pc_actor_database_unresolved_mentions as
select
    suggested_canonical_name,
    suggested_actor_class,
    term,
    count(distinct source_table) as tables_with_hits,
    count(distinct coalesce(
        source_table || ':' || source_record_id,
        source_table || ':' || source_column || ':' || md5(coalesce(matched_value,''))
    )) as records_with_hits,
    count(*) as raw_hits
from public.pc_actor_database_audit_hits
where actor_id is null
group by
    suggested_canonical_name,
    suggested_actor_class,
    term;

-- --------------------------------------------------------------------------
-- Detailed review queue for unresolved actor/network mentions.
-- --------------------------------------------------------------------------
create or replace view public.v_pc_actor_database_unresolved_review as
select
    term,
    suggested_canonical_name,
    suggested_actor_class,
    source_table,
    source_column,
    source_record_id,
    matched_value,
    row_data,
    audited_at
from public.pc_actor_database_audit_hits
where actor_id is null;

-- --------------------------------------------------------------------------
-- Existing actor references by canonical actor, deduplicated at record level.
-- --------------------------------------------------------------------------
create or replace view public.v_pc_actor_database_canonical_summary as
select
    actor_id,
    suggested_canonical_name as canonical_actor,
    suggested_actor_class as actor_class,
    count(distinct source_table) as tables_with_hits,
    count(distinct coalesce(
        source_table || ':' || source_record_id,
        source_table || ':' || source_column || ':' || md5(coalesce(matched_value,''))
    )) as records_with_hits,
    string_agg(distinct term, ', ' order by term) as matched_terms
from public.pc_actor_database_audit_hits
where actor_id is not null
group by actor_id, suggested_canonical_name, suggested_actor_class;

commit;

-- ============================================================================
-- RUN AFTER INSTALL
-- ============================================================================

-- 1. Perform database-wide scan:
-- call public.refresh_pc_actor_database_audit();

-- 2. Overall results including zero-hit terms:
-- select *
-- from public.v_pc_actor_database_audit_summary
-- order by records_with_hits desc, suggested_canonical_name nulls last, term;

-- 3. See which tables/columns contain actor references:
-- select *
-- from public.v_pc_actor_database_locations
-- order by hits desc, suggested_canonical_name nulls last, source_table, source_column;

-- 4. Find terms actually present but not canonicalised:
-- select *
-- from public.v_pc_actor_database_unresolved_mentions
-- order by records_with_hits desc, suggested_canonical_name nulls last, term;

-- 5. Inspect the actual unresolved records:
-- select
--     suggested_canonical_name,
--     suggested_actor_class,
--     term,
--     source_table,
--     source_column,
--     source_record_id,
--     matched_value
-- from public.v_pc_actor_database_unresolved_review
-- order by suggested_canonical_name nulls last, source_table, source_record_id;

-- 6. Canonical actors already visible somewhere in database:
-- select *
-- from public.v_pc_actor_database_canonical_summary
-- order by records_with_hits desc, canonical_actor;
