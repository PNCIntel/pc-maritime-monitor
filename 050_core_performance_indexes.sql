-- Power & Corridors
-- 050_core_performance_indexes.sql
--
-- Purpose:
-- Add targeted indexes for the canonical graph, intelligence/event drill-downs,
-- company/asset/vessel search, ingestion jobs and staging/review workflows.
--
-- Design:
--   * CREATE INDEX IF NOT EXISTS wherever columns are known.
--   * Schema-safe helper checks before optional indexes.
--   * pg_trgm indexes for fast partial-name search / ILIKE '%...%'.
--   * Avoid indexing every column; focus on join/filter/search paths actually
--     used by app.py, pc-intelligence.py, pc_drilldown.py and Power Admin.
--
-- Safe to run repeatedly.
-- NOTE: Creating indexes can take time on large tables. Run during a quieter period.

begin;

-- Useful for ILIKE '%text%' searches on company, port, vessel and event names.
create extension if not exists pg_trgm;

-- ------------------------------------------------------------------
-- Helper: create an index only when every referenced column exists.
-- ------------------------------------------------------------------
create or replace function public.pc_create_index_if_columns_exist(
    p_index_name text,
    p_table_name text,
    p_index_sql text,
    p_columns text[]
)
returns boolean
language plpgsql
security definer
set search_path=public
as $$
declare
    v_col text;
begin
    if to_regclass('public.'||p_table_name) is null then
        return false;
    end if;

    foreach v_col in array p_columns loop
        if not exists (
            select 1
              from information_schema.columns
             where table_schema='public'
               and table_name=p_table_name
               and column_name=v_col
        ) then
            return false;
        end if;
    end loop;

    execute format(
        'create index if not exists %I on public.%I %s',
        p_index_name,
        p_table_name,
        p_index_sql
    );
    return true;
end;
$$;

-- ==================================================================
-- CORE GRAPH: event links
-- ==================================================================
select public.pc_create_index_if_columns_exist(
    'idx_pc_event_links_event_id',
    'pc_event_links',
    '(event_id)',
    array['event_id']
);

select public.pc_create_index_if_columns_exist(
    'idx_pc_event_links_linked_object',
    'pc_event_links',
    '(linked_type, linked_id)',
    array['linked_type','linked_id']
);

select public.pc_create_index_if_columns_exist(
    'idx_pc_event_links_event_linked',
    'pc_event_links',
    '(event_id, linked_type, linked_id)',
    array['event_id','linked_type','linked_id']
);

select public.pc_create_index_if_columns_exist(
    'idx_pc_event_links_relationship',
    'pc_event_links',
    '(relationship)',
    array['relationship']
);

-- ==================================================================
-- CORE GRAPH: relationships
-- ==================================================================
select public.pc_create_index_if_columns_exist(
    'idx_pc_relationships_source',
    'pc_relationships',
    '(source_type, source_id)',
    array['source_type','source_id']
);

select public.pc_create_index_if_columns_exist(
    'idx_pc_relationships_target',
    'pc_relationships',
    '(target_type, target_id)',
    array['target_type','target_id']
);

select public.pc_create_index_if_columns_exist(
    'idx_pc_relationships_source_target',
    'pc_relationships',
    '(source_type, source_id, target_type, target_id)',
    array['source_type','source_id','target_type','target_id']
);

select public.pc_create_index_if_columns_exist(
    'idx_pc_relationships_relationship_type',
    'pc_relationships',
    '(relationship_type)',
    array['relationship_type']
);

-- ==================================================================
-- EVENTS / INTELLIGENCE
-- ==================================================================
select public.pc_create_index_if_columns_exist(
    'idx_pc_events_start_date_desc',
    'pc_events',
    '(start_date desc)',
    array['start_date']
);

select public.pc_create_index_if_columns_exist(
    'idx_pc_events_severity_start_date',
    'pc_events',
    '(severity, start_date desc)',
    array['severity','start_date']
);

select public.pc_create_index_if_columns_exist(
    'idx_pc_events_domain_start_date',
    'pc_events',
    '(event_domain, start_date desc)',
    array['event_domain','start_date']
);

select public.pc_create_index_if_columns_exist(
    'idx_pc_events_type_start_date',
    'pc_events',
    '(event_type, start_date desc)',
    array['event_type','start_date']
);

select public.pc_create_index_if_columns_exist(
    'idx_pc_events_status_start_date',
    'pc_events',
    '(status, start_date desc)',
    array['status','start_date']
);

select public.pc_create_index_if_columns_exist(
    'idx_pc_events_title_trgm',
    'pc_events',
    'using gin (title gin_trgm_ops)',
    array['title']
);

select public.pc_create_index_if_columns_exist(
    'idx_pc_events_location_trgm',
    'pc_events',
    'using gin (location gin_trgm_ops)',
    array['location']
);

-- ==================================================================
-- ENTITIES / COMPANIES
-- ==================================================================
select public.pc_create_index_if_columns_exist(
    'idx_pc_entities_name_trgm',
    'pc_entities',
    'using gin (name gin_trgm_ops)',
    array['name']
);

select public.pc_create_index_if_columns_exist(
    'idx_pc_entities_entity_type',
    'pc_entities',
    '(entity_type)',
    array['entity_type']
);

select public.pc_create_index_if_columns_exist(
    'idx_pc_entities_hq_country',
    'pc_entities',
    '(hq_country)',
    array['hq_country']
);

-- ==================================================================
-- FIXED ASSETS / PORTS / TERMINALS / INFRASTRUCTURE
-- ==================================================================
select public.pc_create_index_if_columns_exist(
    'idx_pc_assets_name_trgm',
    'pc_assets',
    'using gin (name gin_trgm_ops)',
    array['name']
);

select public.pc_create_index_if_columns_exist(
    'idx_pc_assets_type_country',
    'pc_assets',
    '(asset_type, country)',
    array['asset_type','country']
);

select public.pc_create_index_if_columns_exist(
    'idx_pc_assets_country',
    'pc_assets',
    '(country)',
    array['country']
);

select public.pc_create_index_if_columns_exist(
    'idx_pc_assets_region_city_trgm',
    'pc_assets',
    'using gin (region_city gin_trgm_ops)',
    array['region_city']
);

-- ==================================================================
-- MOBILE ASSETS / VESSELS
-- ==================================================================
select public.pc_create_index_if_columns_exist(
    'idx_pc_mobile_assets_imo',
    'pc_mobile_assets',
    '(imo)',
    array['imo']
);

select public.pc_create_index_if_columns_exist(
    'idx_pc_mobile_assets_mmsi',
    'pc_mobile_assets',
    '(mmsi)',
    array['mmsi']
);

select public.pc_create_index_if_columns_exist(
    'idx_pc_mobile_assets_name_trgm',
    'pc_mobile_assets',
    'using gin (name gin_trgm_ops)',
    array['name']
);

select public.pc_create_index_if_columns_exist(
    'idx_pc_mobile_assets_type_flag',
    'pc_mobile_assets',
    '(asset_type, flag)',
    array['asset_type','flag']
);

select public.pc_create_index_if_columns_exist(
    'idx_pc_mobile_assets_subtype',
    'pc_mobile_assets',
    '(subtype)',
    array['subtype']
);

-- ==================================================================
-- IDENTITY / ALIAS RESOLUTION
-- ==================================================================
select public.pc_create_index_if_columns_exist(
    'idx_pc_identity_aliases_v2_lookup',
    'pc_identity_aliases_v2',
    '(object_type, normalized_alias)',
    array['object_type','normalized_alias']
);

select public.pc_create_index_if_columns_exist(
    'idx_pc_identity_aliases_lookup',
    'pc_identity_aliases',
    '(object_type, normalized_alias)',
    array['object_type','normalized_alias']
);

-- ==================================================================
-- INGESTION / POWER ADMIN
-- ==================================================================
select public.pc_create_index_if_columns_exist(
    'idx_pc_staged_records_job',
    'pc_staged_records',
    '(ingestion_job_id)',
    array['ingestion_job_id']
);

select public.pc_create_index_if_columns_exist(
    'idx_pc_staged_records_job_review',
    'pc_staged_records',
    '(ingestion_job_id, review_status)',
    array['ingestion_job_id','review_status']
);

select public.pc_create_index_if_columns_exist(
    'idx_pc_staged_records_job_resolution',
    'pc_staged_records',
    '(ingestion_job_id, resolution_status)',
    array['ingestion_job_id','resolution_status']
);

select public.pc_create_index_if_columns_exist(
    'idx_pc_staged_records_target_table',
    'pc_staged_records',
    '(target_table, review_status)',
    array['target_table','review_status']
);

select public.pc_create_index_if_columns_exist(
    'idx_pc_staged_records_natural_key',
    'pc_staged_records',
    '(target_table, natural_key)',
    array['target_table','natural_key']
);

select public.pc_create_index_if_columns_exist(
    'idx_pc_ingestion_jobs_created_at',
    'pc_ingestion_jobs',
    '(created_at desc)',
    array['created_at']
);

select public.pc_create_index_if_columns_exist(
    'idx_pc_ingestion_jobs_status_created',
    'pc_ingestion_jobs',
    '(status, created_at desc)',
    array['status','created_at']
);

select public.pc_create_index_if_columns_exist(
    'idx_pc_workflow_runs_job',
    'pc_workflow_runs',
    '(ingestion_job_id)',
    array['ingestion_job_id']
);

select public.pc_create_index_if_columns_exist(
    'idx_pc_workflow_runs_status_updated',
    'pc_workflow_runs',
    '(status, updated_at desc)',
    array['status','updated_at']
);

-- ==================================================================
-- COMMON DIRECT RELATIONSHIP COLUMNS, if present
-- ==================================================================
select public.pc_create_index_if_columns_exist(
    'idx_pc_assets_owner_entity',
    'pc_assets',
    '(owner_entity_id)',
    array['owner_entity_id']
);

select public.pc_create_index_if_columns_exist(
    'idx_pc_assets_operator_entity',
    'pc_assets',
    '(operator_entity_id)',
    array['operator_entity_id']
);

select public.pc_create_index_if_columns_exist(
    'idx_pc_mobile_assets_owner_entity',
    'pc_mobile_assets',
    '(owner_entity_id)',
    array['owner_entity_id']
);

select public.pc_create_index_if_columns_exist(
    'idx_pc_mobile_assets_operator_entity',
    'pc_mobile_assets',
    '(operator_entity_id)',
    array['operator_entity_id']
);

select public.pc_create_index_if_columns_exist(
    'idx_pc_mobile_assets_manager_entity',
    'pc_mobile_assets',
    '(manager_entity_id)',
    array['manager_entity_id']
);

commit;

-- Refresh planner statistics after index creation.
analyze public.pc_event_links;
analyze public.pc_relationships;
analyze public.pc_events;
analyze public.pc_entities;
analyze public.pc_assets;
analyze public.pc_mobile_assets;
analyze public.pc_staged_records;
analyze public.pc_ingestion_jobs;

-- Optional quick verification:
-- select schemaname, tablename, indexname, indexdef
-- from pg_indexes
-- where schemaname='public'
--   and indexname like 'idx_pc_%'
-- order by tablename,indexname;
