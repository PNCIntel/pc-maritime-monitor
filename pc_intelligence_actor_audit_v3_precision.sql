
-- ============================================================================
-- P&C Intelligence — Actors & Networks Audit v3
-- Precision matching + canonical reconciliation + operational evidence views
-- 2026-09-15
-- ============================================================================

begin;

-- --------------------------------------------------------------------------
-- 1. Reconcile audit terms with existing canonical actors.
--    This fixes cases such as Hezbollah already existing in pc_actors while
--    pc_actor_audit_terms.actor_id is still NULL.
-- --------------------------------------------------------------------------

update public.pc_actor_audit_terms t
set actor_id = a.actor_id
from public.pc_actors a
where t.actor_id is null
  and t.suggested_canonical_name is not null
  and lower(trim(a.canonical_name)) = lower(trim(t.suggested_canonical_name));

-- Also try canonical short names where appropriate.
update public.pc_actor_audit_terms t
set actor_id = a.actor_id
from public.pc_actors a
where t.actor_id is null
  and (
      lower(trim(a.short_name)) = lower(trim(t.term))
      or lower(trim(a.short_name)) = lower(trim(t.suggested_canonical_name))
  );

-- --------------------------------------------------------------------------
-- 2. Regex escape helper for literal audit terms.
-- --------------------------------------------------------------------------

create or replace function public.pc_regex_escape(v text)
returns text
language sql
immutable
as $$
    select regexp_replace(
        coalesce(v,''),
        '([\\.\^\$\|\(\)\[\]\{\}\*\+\?])',
        '\\\1',
        'g'
    );
$$;

-- --------------------------------------------------------------------------
-- 3. Precision matcher.
--
-- Uses PostgreSQL word boundaries \m and \M. This prevents:
--   Hamas -> Bahamas
-- while preserving:
--   Houthi
--   Houthis
--   al-Shabaab
--   Kata'ib Hezbollah
--   Islamic Resistance in Iraq
-- --------------------------------------------------------------------------

create or replace function public.pc_actor_term_matches(value_text text, search_term text)
returns boolean
language sql
immutable
as $$
    select case
        when nullif(trim(value_text),'') is null
          or nullif(trim(search_term),'') is null
        then false
        else value_text ~* (
            '\m' || public.pc_regex_escape(trim(search_term)) || '\M'
        )
    end;
$$;

-- --------------------------------------------------------------------------
-- 4. Replace the database-wide sweep with precision matching.
-- --------------------------------------------------------------------------

create or replace procedure public.refresh_pc_actor_database_audit()
language plpgsql
as $$
declare
    c record;
    t record;
    q text;
begin
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
                  and public.pc_actor_term_matches(x.%I::text, %L)
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
                t.term
            );

            execute q;
        end loop;
    end loop;
end;
$$;

-- --------------------------------------------------------------------------
-- 5. Operational evidence classification.
--
-- The wide audit is still useful for discovery, but analytics/review should
-- not count staging machinery, IDs, aliases, ingestion queries, or the actor
-- dictionary itself as operational evidence.
-- --------------------------------------------------------------------------

create or replace view public.v_pc_actor_database_operational_hits as
select h.*
from public.pc_actor_database_audit_hits h
where h.source_table not in (
    'pc_actors',
    'pc_actor_aliases',
    'pc_actor_audit_terms',
    'pc_actor_relationships',
    'pc_event_actor_links',
    'pc_identity_aliases',
    'pc_identity_aliases_v2',
    'pc_staged_records',
    'pc_staged_values',
    'pc_ingestion_jobs',
    'pc_ingestion_key_map'
)
and h.source_column not in (
    'event_id',
    'event_link_id',
    'actor_id',
    'entity_id',
    'asset_id',
    'mobile_asset_id',
    'source_id',
    'canonical_id',
    'source_record_key',
    'natural_key',
    'resolved_entity_id',
    'url'
);

-- --------------------------------------------------------------------------
-- 6. Operational summary by term.
-- --------------------------------------------------------------------------

create or replace view public.v_pc_actor_operational_audit_summary as
select
    t.term,
    t.suggested_canonical_name,
    t.suggested_actor_class,
    t.actor_id,
    (t.actor_id is not null) as canonical_actor_exists,
    count(distinct h.source_table) as operational_tables,
    count(distinct (h.source_table || ':' || h.source_column)) as operational_columns,
    count(distinct coalesce(
        h.source_table || ':' || h.source_record_id,
        h.source_table || ':' || h.source_column || ':' || md5(coalesce(h.matched_value,''))
    )) as operational_records,
    count(h.audit_hit_id) as operational_raw_hits
from public.pc_actor_audit_terms t
left join public.v_pc_actor_database_operational_hits h
  on h.audit_term_id = t.audit_term_id
where t.enabled = true
group by
    t.audit_term_id,
    t.term,
    t.suggested_canonical_name,
    t.suggested_actor_class,
    t.actor_id;

-- --------------------------------------------------------------------------
-- 7. Canonical actor summary, collapsing all aliases to one actor.
-- --------------------------------------------------------------------------

create or replace view public.v_pc_actor_operational_canonical_summary as
select
    h.actor_id,
    min(h.suggested_canonical_name) as canonical_actor,
    min(h.suggested_actor_class) as actor_class,
    count(distinct h.source_table) as operational_tables,
    count(distinct coalesce(
        h.source_table || ':' || h.source_record_id,
        h.source_table || ':' || h.source_column || ':' || md5(coalesce(h.matched_value,''))
    )) as operational_records,
    string_agg(distinct h.term, ', ' order by h.term) as matched_aliases
from public.v_pc_actor_database_operational_hits h
where h.actor_id is not null
group by h.actor_id;

-- --------------------------------------------------------------------------
-- 8. Operational unresolved queue.
-- --------------------------------------------------------------------------

create or replace view public.v_pc_actor_operational_unresolved as
select
    h.term,
    h.suggested_canonical_name,
    h.suggested_actor_class,
    h.source_table,
    h.source_column,
    h.source_record_id,
    h.matched_value,
    h.row_data
from public.v_pc_actor_database_operational_hits h
where h.actor_id is null;

-- --------------------------------------------------------------------------
-- 9. Existing actor records whose audit terms are now mapped.
-- --------------------------------------------------------------------------

create or replace view public.v_pc_actor_term_mapping_status as
select
    t.term,
    t.suggested_canonical_name,
    t.suggested_actor_class,
    t.actor_id,
    a.canonical_name,
    a.short_name,
    case
        when t.actor_id is not null and a.actor_id is not null then 'mapped'
        when t.actor_id is null and exists (
            select 1
            from public.pc_actors ax
            where lower(trim(ax.canonical_name))
                = lower(trim(t.suggested_canonical_name))
        ) then 'actor_exists_term_unmapped'
        else 'no_canonical_actor'
    end as mapping_status
from public.pc_actor_audit_terms t
left join public.pc_actors a
  on a.actor_id = t.actor_id
where t.enabled = true;

commit;

-- ============================================================================
-- RUN AFTER INSTALL
-- ============================================================================

-- Re-run the precision audit:
-- call public.refresh_pc_actor_database_audit();

-- A. Check term -> actor mapping:
-- select *
-- from public.v_pc_actor_term_mapping_status
-- order by mapping_status, suggested_canonical_name nulls last, term;

-- B. Clean operational actor counts:
-- select *
-- from public.v_pc_actor_operational_audit_summary
-- order by operational_records desc, suggested_canonical_name nulls last, term;

-- C. Collapse Houthi / Houthis / Ansar Allah into one canonical actor:
-- select *
-- from public.v_pc_actor_operational_canonical_summary
-- order by operational_records desc, canonical_actor;

-- D. Genuine unresolved actor/network references:
-- select *
-- from public.v_pc_actor_operational_unresolved
-- order by suggested_canonical_name nulls last, source_table, source_record_id;

-- E. Confirm Hamas/Bahamas false positives have disappeared:
-- select *
-- from public.pc_actor_database_audit_hits
-- where lower(term) = 'hamas'
-- order by source_table, source_column;

-- F. Inspect generic entity duplicates around Ansar Allah/Houthis:
-- select *
-- from public.pc_entities
-- where name ~* '\m(Houthi|Houthis|Ansar Allah|Ansarallah)\M'
-- order by name;

-- G. Inspect actor records for Hezbollah / Hamas / Islamic State:
-- select actor_id, canonical_name, short_name, actor_class, actor_type, status
-- from public.pc_actors
-- where canonical_name ~* '\m(Hezbollah|Hamas|Islamic State)\M'
--    or short_name ~* '\m(Hezbollah|Hamas|ISIS|ISIL)\M'
-- order by canonical_name;
