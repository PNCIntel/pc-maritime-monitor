begin;

-- ============================================================================
-- P&C Workflow 037
-- Make AI Research reconciliation one-pass and operator-light.
--
-- Incorporates the production fixes verified on job
-- a3256a49-3a4c-4f67-aa13-4a44ed8549da:
--   * event payload v2 promotion runs before event-link resolution
--   * event-link staging accepts linked_* AND AI Research entity_* field names
--   * canonical names are registered as reusable aliases
--   * alias lookup may use job-local or global aliases
--   * exact canonical matches auto-close as applied/validated
--   * array event links are expanded before dependency repair/resolution
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 1. Alias lookup: prefer job-local aliases, but allow global canonical aliases.
-- ---------------------------------------------------------------------------
create or replace function pc_resolve_alias(
    p_alias_value text,
    p_canonical_type text,
    p_ingestion_job_id uuid default null
)
returns text
language sql
stable
security definer
set search_path=public
as $$
select a.canonical_id
from pc_identity_aliases a
where lower(trim(a.alias_value)) = lower(trim(p_alias_value))
  and a.canonical_type = p_canonical_type
  and (
        p_ingestion_job_id is null
        or a.ingestion_job_id = p_ingestion_job_id
        or a.ingestion_job_id is null
      )
order by
    case
      when p_ingestion_job_id is not null and a.ingestion_job_id = p_ingestion_job_id then 0
      when a.ingestion_job_id is null then 1
      else 2
    end,
    a.created_at desc
limit 1;
$$;

comment on function pc_resolve_alias(text,text,uuid) is
'Resolves identity aliases, preferring job-local aliases while allowing reusable global canonical-name aliases.';

-- ---------------------------------------------------------------------------
-- 2. Register canonical names for records touched by a job.
--    These are global aliases so later jobs can resolve names without a manual
--    backfill.  Natural-key aliases remain job-local via pc_register_job_aliases.
-- ---------------------------------------------------------------------------
create or replace function pc_register_canonical_name_aliases(
    p_ingestion_job_id uuid
)
returns jsonb
language plpgsql
security definer
set search_path=public
as $$
declare
    v_entities integer := 0;
    v_assets integer := 0;
    v_mobile_assets integer := 0;
    v_events integer := 0;
begin
    insert into pc_identity_aliases(
        alias_type, alias_value, canonical_type, canonical_id,
        ingestion_job_id, confidence, resolution_method, metadata
    )
    select distinct
        'canonical_name',
        e.name,
        'entity',
        e.entity_id,
        null,
        s.confidence,
        'CANONICAL_NAME',
        jsonb_build_object(
            'source','automatic_canonical_name_registration',
            'target_table','pc_entities',
            'source_ingestion_job_id',p_ingestion_job_id
        )
    from pc_staged_records s
    join pc_entities e
      on e.entity_id = coalesce(s.resolved_entity_id, s.payload->>'entity_id')
    where s.ingestion_job_id = p_ingestion_job_id
      and s.target_table = 'pc_entities'
      and nullif(trim(e.name),'') is not null
    on conflict do nothing;
    get diagnostics v_entities = row_count;

    insert into pc_identity_aliases(
        alias_type, alias_value, canonical_type, canonical_id,
        ingestion_job_id, confidence, resolution_method, metadata
    )
    select distinct
        'canonical_name',
        a.name,
        'asset',
        a.asset_id,
        null,
        s.confidence,
        'CANONICAL_NAME',
        jsonb_build_object(
            'source','automatic_canonical_name_registration',
            'target_table','pc_assets',
            'source_ingestion_job_id',p_ingestion_job_id
        )
    from pc_staged_records s
    join pc_assets a
      on a.asset_id = coalesce(s.resolved_entity_id, s.payload->>'asset_id')
    where s.ingestion_job_id = p_ingestion_job_id
      and s.target_table = 'pc_assets'
      and nullif(trim(a.name),'') is not null
    on conflict do nothing;
    get diagnostics v_assets = row_count;

    insert into pc_identity_aliases(
        alias_type, alias_value, canonical_type, canonical_id,
        ingestion_job_id, confidence, resolution_method, metadata
    )
    select distinct
        'canonical_name',
        m.name,
        'mobile_asset',
        m.mobile_asset_id,
        null,
        s.confidence,
        'CANONICAL_NAME',
        jsonb_build_object(
            'source','automatic_canonical_name_registration',
            'target_table','pc_mobile_assets',
            'source_ingestion_job_id',p_ingestion_job_id
        )
    from pc_staged_records s
    join pc_mobile_assets m
      on m.mobile_asset_id = coalesce(s.resolved_entity_id, s.payload->>'mobile_asset_id')
    where s.ingestion_job_id = p_ingestion_job_id
      and s.target_table = 'pc_mobile_assets'
      and nullif(trim(m.name),'') is not null
    on conflict do nothing;
    get diagnostics v_mobile_assets = row_count;

    insert into pc_identity_aliases(
        alias_type, alias_value, canonical_type, canonical_id,
        ingestion_job_id, confidence, resolution_method, metadata
    )
    select distinct
        'canonical_name',
        e.title,
        'event',
        e.event_id,
        null,
        s.confidence,
        'CANONICAL_NAME',
        jsonb_build_object(
            'source','automatic_canonical_name_registration',
            'target_table','pc_events',
            'source_ingestion_job_id',p_ingestion_job_id
        )
    from pc_staged_records s
    join pc_events e
      on e.event_id = coalesce(s.resolved_entity_id, s.payload->>'event_id')
    where s.ingestion_job_id = p_ingestion_job_id
      and s.target_table = 'pc_events'
      and nullif(trim(e.title),'') is not null
    on conflict do nothing;
    get diagnostics v_events = row_count;

    return jsonb_build_object(
        'entity_names',v_entities,
        'asset_names',v_assets,
        'mobile_asset_names',v_mobile_assets,
        'event_titles',v_events
    );
end;
$$;

-- ---------------------------------------------------------------------------
-- 3. Auto-close safe exact identity matches.
--    A resolved canonical ID must actually exist before a row is closed.
-- ---------------------------------------------------------------------------
create or replace function pc_auto_close_exact_staging_matches(
    p_ingestion_job_id uuid
)
returns jsonb
language plpgsql
security definer
set search_path=public
as $$
declare
    v_entities integer := 0;
    v_assets integer := 0;
    v_mobile integer := 0;
    v_events integer := 0;
begin
    update pc_staged_records s
       set review_status = 'applied',
           validation_status = 'validated'
     where s.ingestion_job_id = p_ingestion_job_id
       and s.target_table = 'pc_entities'
       and s.resolution_status = 'MATCHED'
       and coalesce(s.review_status,'pending') <> 'applied'
       and coalesce(s.resolution_method,'') in (
           'PRIMARY_KEY_EXACT','CANONICAL_ID','CANONICAL_APPLY','CANONICAL_ID_EXACT'
       )
       and exists (
           select 1 from pc_entities e
           where e.entity_id = coalesce(s.resolved_entity_id,s.payload->>'entity_id')
       );
    get diagnostics v_entities = row_count;

    update pc_staged_records s
       set review_status = 'applied',
           validation_status = 'validated'
     where s.ingestion_job_id = p_ingestion_job_id
       and s.target_table = 'pc_assets'
       and s.resolution_status = 'MATCHED'
       and coalesce(s.review_status,'pending') <> 'applied'
       and coalesce(s.resolution_method,'') in (
           'PRIMARY_KEY_EXACT','CANONICAL_ID','CANONICAL_APPLY','CANONICAL_ID_EXACT'
       )
       and exists (
           select 1 from pc_assets a
           where a.asset_id = coalesce(s.resolved_entity_id,s.payload->>'asset_id')
       );
    get diagnostics v_assets = row_count;

    update pc_staged_records s
       set review_status = 'applied',
           validation_status = 'validated'
     where s.ingestion_job_id = p_ingestion_job_id
       and s.target_table = 'pc_mobile_assets'
       and s.resolution_status = 'MATCHED'
       and coalesce(s.review_status,'pending') <> 'applied'
       and coalesce(s.resolution_method,'') in (
           'PRIMARY_KEY_EXACT','CANONICAL_ID','CANONICAL_APPLY','CANONICAL_ID_EXACT'
       )
       and exists (
           select 1 from pc_mobile_assets m
           where m.mobile_asset_id = coalesce(s.resolved_entity_id,s.payload->>'mobile_asset_id')
       );
    get diagnostics v_mobile = row_count;

    update pc_staged_records s
       set review_status = 'applied',
           validation_status = 'validated'
     where s.ingestion_job_id = p_ingestion_job_id
       and s.target_table = 'pc_events'
       and s.resolution_status = 'MATCHED'
       and coalesce(s.review_status,'pending') <> 'applied'
       and coalesce(s.resolution_method,'') in (
           'PRIMARY_KEY_EXACT','CANONICAL_ID','CANONICAL_APPLY','CANONICAL_ID_EXACT',
           'CANONICAL_EVENT_ALREADY_EXISTS','AUTO_EVENT_PROMOTION_V2'
       )
       and exists (
           select 1 from pc_events e
           where e.event_id = coalesce(s.resolved_entity_id,s.payload->>'event_id')
       );
    get diagnostics v_events = row_count;

    return jsonb_build_object(
        'entities_closed',v_entities,
        'assets_closed',v_assets,
        'mobile_assets_closed',v_mobile,
        'events_closed',v_events
    );
end;
$$;

-- ---------------------------------------------------------------------------
-- 4. Event-link staging compatibility.
--    Accept both legacy/canonical linked_* fields and AI Research entity_* fields.
-- ---------------------------------------------------------------------------
create or replace function pc_stage_event_link_relationship(
    p_staged_record_id uuid
)
returns uuid
language plpgsql
security definer
set search_path=public
as $$
declare
    s pc_staged_records%rowtype;
    p jsonb;
    m jsonb;
    v_rel_id uuid;
    v_to_type text;
    v_identifier_type text;
    v_identifier_value text;
    v_relationship text;
    v_linked_name text;
    v_linked_id text;
begin
    select *
      into s
      from pc_staged_records
     where staged_record_id = p_staged_record_id;

    if not found then
        raise exception 'Unknown staged record %', p_staged_record_id;
    end if;

    if s.target_table <> 'pc_event_links' then
        raise exception 'Staged record % targets %, not pc_event_links',
            p_staged_record_id, s.target_table;
    end if;

    p := coalesce(s.payload,'{}'::jsonb);
    m := case
            when jsonb_typeof(p->'metadata')='object' then p->'metadata'
            else '{}'::jsonb
         end;

    v_to_type := pc_linked_type_to_entity_type(
        coalesce(
            nullif(p->>'linked_type',''),
            nullif(p->>'entity_type','')
        )
    );

    v_linked_name := coalesce(
        nullif(p->>'linked_name',''),
        nullif(p->>'entity_name','')
    );

    v_linked_id := coalesce(
        nullif(p->>'linked_id',''),
        nullif(p->>'entity_id','')
    );

    v_relationship := coalesce(
        nullif(p->>'relationship',''),
        nullif(p->>'link_type',''),
        'linked object'
    );

    if nullif(m->>'imo','') is not null then
        v_identifier_type := 'IMO';
        v_identifier_value := m->>'imo';
    elsif nullif(m->>'mmsi','') is not null then
        v_identifier_type := 'MMSI';
        v_identifier_value := m->>'mmsi';
    end if;

    select staged_relationship_id
      into v_rel_id
      from pc_staged_relationships
     where source_staged_record_id = p_staged_record_id
     order by created_at desc
     limit 1;

    if v_rel_id is null then
        insert into pc_staged_relationships(
            ingestion_job_id,
            source_staged_record_id,
            relationship_type,
            from_entity_type,
            from_source_key,
            from_name,
            to_entity_type,
            to_source_key,
            to_identifier_type,
            to_identifier_value,
            to_name,
            confidence,
            source_id,
            resolution_status,
            metadata
        )
        values (
            s.ingestion_job_id,
            s.staged_record_id,
            v_relationship,
            'event',
            p->>'event_id',
            p->>'event_id',
            coalesce(v_to_type,'mobile_asset'),
            v_linked_id,
            v_identifier_type,
            v_identifier_value,
            v_linked_name,
            coalesce(s.confidence,1.0),
            coalesce(s.source_id,p->>'source_id'),
            'UNRESOLVED',
            jsonb_build_object(
                'event_link_id',p->>'event_link_id',
                'linked_type',coalesce(p->>'linked_type',p->>'entity_type'),
                'linked_name',v_linked_name,
                'original_metadata',m
            )
        )
        returning staged_relationship_id into v_rel_id;
    else
        update pc_staged_relationships
           set ingestion_job_id = s.ingestion_job_id,
               relationship_type = v_relationship,
               from_entity_type = 'event',
               from_source_key = p->>'event_id',
               from_name = p->>'event_id',
               to_entity_type = coalesce(v_to_type,to_entity_type),
               to_source_key = v_linked_id,
               to_identifier_type = v_identifier_type,
               to_identifier_value = v_identifier_value,
               to_name = v_linked_name,
               confidence = coalesce(s.confidence,confidence),
               source_id = coalesce(s.source_id,p->>'source_id',source_id),
               resolution_status = case
                    when resolution_status in ('PARTIAL','BROKEN_REFERENCE','INVALID') then 'UNRESOLVED'
                    else resolution_status
               end,
               metadata = coalesce(metadata,'{}'::jsonb) || jsonb_build_object(
                    'event_link_id',p->>'event_link_id',
                    'linked_type',coalesce(p->>'linked_type',p->>'entity_type'),
                    'linked_name',v_linked_name,
                    'original_metadata',m
               )
         where staged_relationship_id = v_rel_id;
    end if;

    return v_rel_id;
end;
$$;

comment on function pc_stage_event_link_relationship(uuid) is
'Builds event-link relationship staging from either linked_* canonical fields or entity_* AI Research fields.';

-- ---------------------------------------------------------------------------
-- 5. One-pass reconcile orchestration.
-- ---------------------------------------------------------------------------
create or replace function pc_reconcile_ingestion_job_v2(p_ingestion_job_id uuid)
returns jsonb
language plpgsql
security definer
set search_path=public
as $$
declare
    v_result jsonb := '{}'::jsonb;
    v_part jsonb;
    v_remaining integer;
begin
    -- Normalize and prepare candidates.
    if to_regprocedure('pc_cleanup_staging_names(uuid)') is not null then
        execute 'select pc_cleanup_staging_names($1)' into v_part using p_ingestion_job_id;
        v_result := v_result || jsonb_build_object('normalize_names',v_part);
    end if;

    if to_regprocedure('pc_cleanup_staging_keys(uuid)') is not null then
        execute 'select pc_cleanup_staging_keys($1)' into v_part using p_ingestion_job_id;
        v_result := v_result || jsonb_build_object('fill_keys',v_part);
    end if;

    if to_regprocedure('pc_prepare_canonical_candidates(uuid)') is not null then
        execute 'select pc_prepare_canonical_candidates($1)' into v_part using p_ingestion_job_id;
        v_result := v_result || jsonb_build_object('prepare_candidates',v_part);
    end if;

    if to_regprocedure('pc_repair_unresolved_identity_candidates(uuid)') is not null then
        execute 'select pc_repair_unresolved_identity_candidates($1)' into v_part using p_ingestion_job_id;
        v_result := v_result || jsonb_build_object('repair_identities',v_part);
    end if;

    -- Canonical dependencies first.
    v_part := pc_apply_new_staged_entities(p_ingestion_job_id);
    v_result := v_result || jsonb_build_object('entities',v_part);

    v_part := pc_apply_new_staged_assets(p_ingestion_job_id);
    v_result := v_result || jsonb_build_object('assets',v_part);

    v_part := pc_apply_new_staged_mobile_assets(p_ingestion_job_id);
    v_result := v_result || jsonb_build_object('mobile_assets',v_part);

    -- IMPORTANT: promote events before event links. Prefer the verified AI payload v2.
    if to_regprocedure('pc_apply_new_staged_events_v2(uuid)') is not null then
        execute 'select pc_apply_new_staged_events_v2($1)' into v_part using p_ingestion_job_id;
    else
        v_part := pc_apply_new_staged_events(p_ingestion_job_id);
    end if;
    v_result := v_result || jsonb_build_object('events',v_part);

    -- Close canonical exact matches that need no operator decision.
    v_part := pc_auto_close_exact_staging_matches(p_ingestion_job_id);
    v_result := v_result || jsonb_build_object('exact_matches_closed',v_part);

    -- Job-local natural keys + reusable canonical names.
    v_part := pc_register_job_aliases(p_ingestion_job_id);
    v_result := v_result || jsonb_build_object('natural_key_aliases',v_part);

    v_part := pc_register_canonical_name_aliases(p_ingestion_job_id);
    v_result := v_result || jsonb_build_object('canonical_name_aliases',v_part);

    -- Expand compound/array event links BEFORE dependency repair so newly-created
    -- link records participate in this same reconciliation pass.
    v_part := pc_expand_event_link_arrays(p_ingestion_job_id);
    v_result := v_result || jsonb_build_object('event_link_arrays',v_part);

    -- Source-backed dependency creation.
    v_part := pc_autocreate_relationship_dependencies(p_ingestion_job_id);
    v_result := v_result || jsonb_build_object('relationship_dependencies',v_part);

    v_part := pc_autocreate_event_link_dependencies(p_ingestion_job_id);
    v_result := v_result || jsonb_build_object('event_link_dependencies',v_part);

    -- Auto-created dependencies also get reusable name aliases immediately.
    v_part := pc_register_canonical_name_aliases(p_ingestion_job_id);
    v_result := v_result || jsonb_build_object('post_dependency_aliases',v_part);

    -- Resolve all relationship layers after dependencies and aliases exist.
    if to_regprocedure('pc_process_generic_relationship_backlog(uuid)') is not null then
        execute 'select pc_process_generic_relationship_backlog($1)' into v_part using p_ingestion_job_id;
        v_result := v_result || jsonb_build_object('generic_relationship_resolution',v_part);
    end if;

    if to_regprocedure('pc_process_relationship_backlog(uuid)') is not null then
        execute 'select pc_process_relationship_backlog($1)' into v_part using p_ingestion_job_id;
        v_result := v_result || jsonb_build_object('event_link_resolution',v_part);
    end if;

    -- Apply READY event links and generic relationships.
    if to_regprocedure('pc_apply_ready_event_relationships(uuid)') is not null then
        execute 'select pc_apply_ready_event_relationships($1)' into v_part using p_ingestion_job_id;
        v_result := v_result || jsonb_build_object('event_links_applied',v_part);
    end if;

    if to_regprocedure('pc_apply_ready_generic_relationships(uuid)') is not null then
        execute 'select pc_apply_ready_generic_relationships($1)' into v_part using p_ingestion_job_id;
        v_result := v_result || jsonb_build_object('relationships_applied',v_part);
    end if;

    -- Final safe cleanup.
    v_part := pc_auto_close_exact_staging_matches(p_ingestion_job_id);
    v_result := v_result || jsonb_build_object('final_exact_match_cleanup',v_part);

    v_part := pc_normalize_applied_staging(p_ingestion_job_id);
    v_result := v_result || jsonb_build_object('staging_normalized',v_part);

    -- Include quality summary when the quality package is installed.
    if to_regprocedure('pc_ingestion_quality_summary(uuid)') is not null then
        execute 'select pc_ingestion_quality_summary($1)' into v_part using p_ingestion_job_id;
        v_result := v_result || jsonb_build_object('quality',v_part);
    end if;

    select count(*)
      into v_remaining
      from pc_v_ingestion_operator_exceptions
     where ingestion_job_id = p_ingestion_job_id;

    v_result := v_result || jsonb_build_object(
        'remaining_operator_exceptions',v_remaining,
        'pipeline_version','037-one-pass-ai-research'
    );

    return v_result;
end;
$$;

comment on function pc_reconcile_ingestion_job_v2(uuid) is
'One-pass AI Research reconciliation: canonical dependencies -> event v2 promotion -> aliases -> event-link expansion -> dependency repair -> relationship resolution/apply -> safe exact-match closure -> quality summary. Human review remains only for genuine ambiguity/conflict/unsupported structure.';

commit;
