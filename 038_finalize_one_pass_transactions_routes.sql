begin;

-- ============================================================================
-- P&C Workflow 038
-- Finalize one-pass AI Research reconciliation for transactions + routes.
--
-- Verified against fresh multisource AI Research job:
--   ecef5adc-9d5a-4207-b667-6f7b1b574f8d
--
-- Adds:
--   * source-backed transaction promotion into pc_transactions
--   * source-backed route promotion into pc_transport_routes
--   * safe transaction value-scale normalization when source text explicitly
--     says million/billion/trillion
--   * boolean-safe operating_control handling
--   * corrected global alias registration UUID casts
--   * orchestration calls for transactions/routes before final QA
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 1. Correct canonical-name alias registration typing from Workflow 037.
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
        null::uuid,
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
        null::uuid,
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
        null::uuid,
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
        null::uuid,
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
-- 2. Promote staged transaction records.
-- ---------------------------------------------------------------------------
create or replace function pc_apply_new_staged_transactions_v2(
    p_ingestion_job_id uuid
)
returns jsonb
language plpgsql
security definer
set search_path=public
as $$
declare
    r record;
    p jsonb;
    v_transaction_id text;
    v_operating_control boolean;
    v_reported_value numeric;
    v_source_blob text;
    v_buyer_entity_id text;
    v_inserted integer := 0;
    v_existing integer := 0;
    v_failed integer := 0;
begin
    for r in
        select staged_record_id, natural_key, payload, source_id
        from pc_staged_records
        where ingestion_job_id = p_ingestion_job_id
          and target_table = 'pc_transactions'
          and coalesce(review_status,'pending') <> 'applied'
          and resolution_status in ('NEW','INVALID','UNRESOLVED','MATCHED')
    loop
        begin
            p := coalesce(r.payload,'{}'::jsonb);
            v_transaction_id := nullif(p->>'transaction_id','');

            if v_transaction_id is null then
                update pc_staged_records
                   set resolution_status='INVALID',
                       resolution_method='TRANSACTION_PAYLOAD_MISSING_TRANSACTION_ID',
                       validation_status='invalid'
                 where staged_record_id=r.staged_record_id;
                v_failed := v_failed + 1;
                continue;
            end if;

            if exists(select 1 from pc_transactions where transaction_id=v_transaction_id) then
                update pc_staged_records
                   set resolution_status='MATCHED',
                       review_status='applied',
                       validation_status='validated',
                       resolution_method='CANONICAL_TRANSACTION_ALREADY_EXISTS',
                       resolved_entity_id=v_transaction_id
                 where staged_record_id=r.staged_record_id;
                v_existing := v_existing + 1;
                continue;
            end if;

            v_operating_control :=
                case lower(trim(coalesce(p->>'operating_control','')))
                    when 'true' then true when 'yes' then true when '1' then true
                    when 'false' then false when 'no' then false when '0' then false
                    else null
                end;

            v_reported_value := case
                when nullif(p->>'reported_value','') is not null
                then (p->>'reported_value')::numeric
                else null
            end;

            -- AI research may occasionally emit 22.9 for "$22.9 billion".
            -- Scale only when the full source-backed payload explicitly states
            -- a scale word and the numeric field is still a small unscaled value.
            v_source_blob := lower(p::text);
            if v_reported_value is not null and abs(v_reported_value) < 1000000 then
                if v_source_blob like '%trillion%' then
                    v_reported_value := v_reported_value * 1000000000000::numeric;
                elsif v_source_blob like '%billion%' then
                    v_reported_value := v_reported_value * 1000000000::numeric;
                elsif v_source_blob like '%million%' then
                    v_reported_value := v_reported_value * 1000000::numeric;
                end if;
            end if;

            v_buyer_entity_id := null;
            if nullif(p->>'buyer','') is not null
               and to_regprocedure('pc_resolve_alias(text,text,uuid)') is not null then
                execute 'select pc_resolve_alias($1,$2,$3)'
                   into v_buyer_entity_id
                   using p->>'buyer','entity',p_ingestion_job_id;
            end if;

            insert into pc_transactions(
                transaction_id,
                announced_date,
                buyer_entity_id,
                seller_name,
                target_name,
                asset_class,
                country_region,
                transaction_type,
                reported_value,
                currency,
                operating_control,
                status,
                source_id,
                notes,
                metadata
            )
            values(
                v_transaction_id,
                nullif(p->>'announced_date','')::date,
                v_buyer_entity_id,
                coalesce(nullif(p->>'seller',''),nullif(p->>'contractor','')),
                coalesce(nullif(p->>'target_name',''),nullif(p->>'asset_class','')),
                nullif(p->>'asset_class',''),
                nullif(p->>'country_region',''),
                nullif(p->>'transaction_type',''),
                v_reported_value,
                nullif(p->>'currency',''),
                v_operating_control,
                nullif(p->>'status',''),
                r.source_id,
                null,
                coalesce(p->'metadata','{}'::jsonb)
                || jsonb_build_object(
                    'buyer',p->>'buyer',
                    'seller',p->>'seller',
                    'customer',p->>'customer',
                    'contractor',p->>'contractor',
                    'awarding_authority',p->>'awarding_authority',
                    'operating_control_raw',p->>'operating_control',
                    'source_url',p->>'source_url',
                    'created_from_ingestion_job',p_ingestion_job_id,
                    'research_natural_key',r.natural_key,
                    'auto_promoted_transaction',true,
                    'reported_value_normalized',v_reported_value
                )
            );

            update pc_staged_records
               set resolution_status='MATCHED',
                   review_status='applied',
                   validation_status='validated',
                   resolution_method='AUTO_TRANSACTION_PROMOTION_V2',
                   resolved_entity_id=v_transaction_id
             where staged_record_id=r.staged_record_id;

            v_inserted := v_inserted + 1;
        exception when others then
            update pc_staged_records
               set resolution_status='INVALID',
                   resolution_method='TRANSACTION_PROMOTION_ERROR: ' || left(sqlerrm,200)
             where staged_record_id=r.staged_record_id;
            v_failed := v_failed + 1;
        end;
    end loop;

    return jsonb_build_object(
        'inserted',v_inserted,
        'already_existing',v_existing,
        'failed',v_failed
    );
end;
$$;

comment on function pc_apply_new_staged_transactions_v2(uuid) is
'Promotes source-backed staged transactions into pc_transactions, safely handling boolean operating_control and explicit value scales.';

-- ---------------------------------------------------------------------------
-- 3. Promote staged transport routes.
-- ---------------------------------------------------------------------------
create or replace function pc_apply_new_staged_transport_routes_v2(
    p_ingestion_job_id uuid
)
returns jsonb
language plpgsql
security definer
set search_path=public
as $$
declare
    r record;
    p jsonb;
    v_route_id text;
    v_route_name text;
    v_mode text;
    v_countries text[];
    v_inserted integer := 0;
    v_existing integer := 0;
    v_failed integer := 0;
begin
    for r in
        select staged_record_id, natural_key, payload, source_id
        from pc_staged_records
        where ingestion_job_id=p_ingestion_job_id
          and target_table='pc_transport_routes'
          and coalesce(review_status,'pending') <> 'applied'
          and resolution_status in ('NEW','INVALID','UNRESOLVED','MATCHED')
    loop
        begin
            p := coalesce(r.payload,'{}'::jsonb);
            v_route_id := nullif(p->>'route_id','');
            v_route_name := coalesce(nullif(p->>'route_name',''),nullif(p->>'name',''));

            if v_route_id is null or v_route_name is null then
                update pc_staged_records
                   set resolution_status='INVALID',
                       resolution_method='ROUTE_PAYLOAD_MISSING_REQUIRED_FIELDS',
                       validation_status='invalid'
                 where staged_record_id=r.staged_record_id;
                v_failed := v_failed + 1;
                continue;
            end if;

            if exists(select 1 from pc_transport_routes where route_id=v_route_id) then
                update pc_staged_records
                   set resolution_status='MATCHED',
                       review_status='applied',
                       validation_status='validated',
                       resolution_method='CANONICAL_ROUTE_ALREADY_EXISTS',
                       resolved_entity_id=v_route_id
                 where staged_record_id=r.staged_record_id;
                v_existing := v_existing + 1;
                continue;
            end if;

            v_mode := case
                when lower(coalesce(p->>'route_type','')) like '%pipeline%'
                  or lower(v_route_name) like '%pipeline%' then 'Pipeline'
                when lower(coalesce(p->>'route_type','')) like '%rail%'
                  or lower(v_route_name) like '%rail%' then 'Rail'
                when lower(coalesce(p->>'route_type','')) like '%road%'
                  or lower(v_route_name) like '%highway%' then 'Road'
                when lower(coalesce(p->>'route_type','')) like '%aviation%'
                  or lower(v_route_name) like '%air corridor%' then 'Aviation'
                when lower(coalesce(p->>'route_type','')) like '%maritime%'
                  or lower(v_route_name) like '%seaway%'
                  or lower(v_route_name) like '%shipping%' then 'Maritime'
                else 'Multimodal'
            end;

            v_countries := case
                when nullif(p->>'country_region','') is null then null
                else regexp_split_to_array(p->>'country_region','\s*/\s*|\s*;\s*')
            end;

            insert into pc_transport_routes(
                route_id, route_name, mode, countries,
                current_status, source_id, metadata
            )
            values(
                v_route_id,
                v_route_name,
                v_mode,
                v_countries,
                nullif(p->>'status',''),
                r.source_id,
                coalesce(p->'metadata','{}'::jsonb)
                || jsonb_build_object(
                    'route_type',p->>'route_type',
                    'country_region_raw',p->>'country_region',
                    'created_from_ingestion_job',p_ingestion_job_id,
                    'research_natural_key',r.natural_key,
                    'auto_promoted_route',true
                )
            );

            update pc_staged_records
               set resolution_status='MATCHED',
                   review_status='applied',
                   validation_status='validated',
                   resolution_method='AUTO_ROUTE_PROMOTION_V2',
                   resolved_entity_id=v_route_id
             where staged_record_id=r.staged_record_id;

            v_inserted := v_inserted + 1;
        exception when others then
            update pc_staged_records
               set resolution_status='INVALID',
                   resolution_method='ROUTE_PROMOTION_ERROR: ' || left(sqlerrm,200)
             where staged_record_id=r.staged_record_id;
            v_failed := v_failed + 1;
        end;
    end loop;

    return jsonb_build_object(
        'inserted',v_inserted,
        'already_existing',v_existing,
        'failed',v_failed
    );
end;
$$;

comment on function pc_apply_new_staged_transport_routes_v2(uuid) is
'Promotes source-backed AI Research route records into pc_transport_routes and infers the required mode conservatively.';

-- ---------------------------------------------------------------------------
-- 4. One-pass reconcile orchestration v038.
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

    -- Promote events before event links.
    if to_regprocedure('pc_apply_new_staged_events_v2(uuid)') is not null then
        execute 'select pc_apply_new_staged_events_v2($1)' into v_part using p_ingestion_job_id;
    else
        v_part := pc_apply_new_staged_events(p_ingestion_job_id);
    end if;
    v_result := v_result || jsonb_build_object('events',v_part);

    -- Promote domain records that should not be treated as identity rows.
    v_part := pc_apply_new_staged_transactions_v2(p_ingestion_job_id);
    v_result := v_result || jsonb_build_object('transactions',v_part);

    v_part := pc_apply_new_staged_transport_routes_v2(p_ingestion_job_id);
    v_result := v_result || jsonb_build_object('transport_routes',v_part);

    -- Close exact matches.
    v_part := pc_auto_close_exact_staging_matches(p_ingestion_job_id);
    v_result := v_result || jsonb_build_object('exact_matches_closed',v_part);

    -- Alias registration.
    v_part := pc_register_job_aliases(p_ingestion_job_id);
    v_result := v_result || jsonb_build_object('natural_key_aliases',v_part);

    v_part := pc_register_canonical_name_aliases(p_ingestion_job_id);
    v_result := v_result || jsonb_build_object('canonical_name_aliases',v_part);

    -- Event-link expansion and dependency repair.
    v_part := pc_expand_event_link_arrays(p_ingestion_job_id);
    v_result := v_result || jsonb_build_object('event_link_arrays',v_part);

    v_part := pc_autocreate_relationship_dependencies(p_ingestion_job_id);
    v_result := v_result || jsonb_build_object('relationship_dependencies',v_part);

    v_part := pc_autocreate_event_link_dependencies(p_ingestion_job_id);
    v_result := v_result || jsonb_build_object('event_link_dependencies',v_part);

    v_part := pc_register_canonical_name_aliases(p_ingestion_job_id);
    v_result := v_result || jsonb_build_object('post_dependency_aliases',v_part);

    -- Resolve relationship layers.
    if to_regprocedure('pc_process_generic_relationship_backlog(uuid)') is not null then
        execute 'select pc_process_generic_relationship_backlog($1)' into v_part using p_ingestion_job_id;
        v_result := v_result || jsonb_build_object('generic_relationship_resolution',v_part);
    end if;

    if to_regprocedure('pc_process_relationship_backlog(uuid)') is not null then
        execute 'select pc_process_relationship_backlog($1)' into v_part using p_ingestion_job_id;
        v_result := v_result || jsonb_build_object('event_link_resolution',v_part);
    end if;

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

    if to_regprocedure('pc_ingestion_quality_summary(uuid)') is not null then
        execute 'select pc_ingestion_quality_summary($1)' into v_part using p_ingestion_job_id;
        v_result := v_result || jsonb_build_object('quality',v_part);
    end if;

    select count(*) into v_remaining
      from pc_v_ingestion_operator_exceptions
     where ingestion_job_id=p_ingestion_job_id;

    v_result := v_result || jsonb_build_object(
        'remaining_operator_exceptions',v_remaining,
        'pipeline_version','038-one-pass-ai-research-transactions-routes'
    );

    return v_result;
end;
$$;

comment on function pc_reconcile_ingestion_job_v2(uuid) is
'Workflow 038 one-pass AI Research reconciliation including events, transactions and transport routes before final quality checks.';

commit;
