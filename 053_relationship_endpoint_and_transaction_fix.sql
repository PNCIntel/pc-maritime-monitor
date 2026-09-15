-- Power & Corridors
-- 053_relationship_endpoint_and_transaction_fix.sql
--
-- Fixes the two remaining Qinzhou failures after 052:
--
-- 1) pc_relationships -> MISSING_SOURCE_ENDPOINT
--    Root cause: pc_relationships.source_id is the RELATIONSHIP ENDPOINT,
--    not a provenance/source-record FK. 052 incorrectly passed relationship
--    payloads through pc_source_fk_safe_payload(), which could remove source_id.
--
-- 2) pc_transactions -> invalid input syntax for type boolean: "developer"
--    Root cause: the workbook's operating_control value is descriptive text,
--    while the canonical pc_transactions.operating_control column is boolean.
--
-- This migration:
--   * preserves relationship source_id / target_id as graph endpoints
--   * only FK-sanitizes relationship evidence_source_id
--   * remaps package-local relationship endpoints through pc_ingestion_key_map
--   * adds a transaction-specific canonical writer
--   * remaps transaction entity/asset endpoint IDs
--   * normalizes boolean operating_control safely
--   * preserves descriptive non-boolean operating_control text in metadata
--   * replaces pc_process_ingestion_job_v5 in-place so the current Power Admin
--     retry button can use the corrected logic without an app change
--
-- Safe to run repeatedly.

begin;

-- ---------------------------------------------------------------------------
-- 1. Relationship writer: source_id is an endpoint, NOT provenance.
-- ---------------------------------------------------------------------------
create or replace function public.pc_upsert_relationship_from_payload(
    p_job uuid,
    p_payload jsonb
)
returns jsonb
language plpgsql
security definer
set search_path=public
as $$
declare
    v jsonb := public.pc_evidence_source_fk_safe_payload(coalesce(p_payload,'{}'::jsonb));
    v_source_type text := lower(nullif(v->>'source_type',''));
    v_target_type text := lower(nullif(v->>'target_type',''));
    v_source_raw text := nullif(v->>'source_id','');
    v_target_raw text := nullif(v->>'target_id','');
    v_source text;
    v_target text;
begin
    -- Normalize legacy synonym.
    if v_source_type='vessel' then
        v_source_type:='mobile_asset';
        v:=jsonb_set(v,'{source_type}',to_jsonb(v_source_type),true);
    end if;
    if v_target_type='vessel' then
        v_target_type:='mobile_asset';
        v:=jsonb_set(v,'{target_type}',to_jsonb(v_target_type),true);
    end if;

    if v_source_type is null or v_source_raw is null then
        return jsonb_build_object(
            'status','REVIEW',
            'reason','MISSING_SOURCE_ENDPOINT',
            'source_type',v_source_type,
            'source_id',v_source_raw
        );
    end if;

    if v_target_type is null or v_target_raw is null then
        return jsonb_build_object(
            'status','REVIEW',
            'reason','MISSING_TARGET_ENDPOINT',
            'target_type',v_target_type,
            'target_id',v_target_raw
        );
    end if;

    -- Resolve package-local IDs to canonical IDs created/matched earlier
    -- in the same ingestion job.
    v_source:=public.pc_mapped_id(p_job,v_source_type,v_source_raw);
    v_target:=public.pc_mapped_id(p_job,v_target_type,v_target_raw);

    if not public.pc_object_exists(v_source_type,v_source) then
        return jsonb_build_object(
            'status','REVIEW',
            'reason','MISSING_SOURCE_ENDPOINT',
            'source_type',v_source_type,
            'source_id',v_source,
            'source_input_id',v_source_raw
        );
    end if;

    if not public.pc_object_exists(v_target_type,v_target) then
        return jsonb_build_object(
            'status','REVIEW',
            'reason','MISSING_TARGET_ENDPOINT',
            'target_type',v_target_type,
            'target_id',v_target,
            'target_input_id',v_target_raw
        );
    end if;

    v:=jsonb_set(v,'{source_id}',to_jsonb(v_source),true);
    v:=jsonb_set(v,'{target_id}',to_jsonb(v_target),true);

    perform public.pc_upsert_json(
        'pc_relationships',
        v,
        array['relationship_id']
    );

    return jsonb_build_object(
        'status','OK',
        'relationship_id',v->>'relationship_id',
        'source_id',v_source,
        'target_id',v_target
    );
end;
$$;


-- ---------------------------------------------------------------------------
-- 2. Transaction helper: safely normalize FK endpoints and booleans.
-- ---------------------------------------------------------------------------
create or replace function public.pc_upsert_transaction_from_payload(
    p_job uuid,
    p_payload jsonb
)
returns jsonb
language plpgsql
security definer
set search_path=public
as $$
declare
    v jsonb := public.pc_source_fk_safe_payload(coalesce(p_payload,'{}'::jsonb));
    v_meta jsonb;
    v_raw text;
    v_mapped text;
begin
    if nullif(v->>'transaction_id','') is null then
        return jsonb_build_object(
            'status','REVIEW',
            'reason','MISSING_TRANSACTION_ID'
        );
    end if;

    -- ---------------------------------------------------------------
    -- Canonical endpoint remapping.
    -- ---------------------------------------------------------------
    if nullif(v->>'buyer_entity_id','') is not null then
        v_raw:=v->>'buyer_entity_id';
        v_mapped:=public.pc_mapped_id(p_job,'entity',v_raw);
        if not public.pc_object_exists('entity',v_mapped) then
            return jsonb_build_object(
                'status','REVIEW',
                'reason','MISSING_BUYER_ENDPOINT',
                'buyer_entity_id',v_mapped,
                'buyer_input_id',v_raw
            );
        end if;
        v:=jsonb_set(v,'{buyer_entity_id}',to_jsonb(v_mapped),true);
    end if;

    if nullif(v->>'seller_entity_id','') is not null then
        v_raw:=v->>'seller_entity_id';
        v_mapped:=public.pc_mapped_id(p_job,'entity',v_raw);
        if not public.pc_object_exists('entity',v_mapped) then
            return jsonb_build_object(
                'status','REVIEW',
                'reason','MISSING_SELLER_ENDPOINT',
                'seller_entity_id',v_mapped,
                'seller_input_id',v_raw
            );
        end if;
        v:=jsonb_set(v,'{seller_entity_id}',to_jsonb(v_mapped),true);
    end if;

    if nullif(v->>'target_entity_id','') is not null then
        v_raw:=v->>'target_entity_id';
        v_mapped:=public.pc_mapped_id(p_job,'entity',v_raw);
        if not public.pc_object_exists('entity',v_mapped) then
            return jsonb_build_object(
                'status','REVIEW',
                'reason','MISSING_TARGET_ENTITY_ENDPOINT',
                'target_entity_id',v_mapped,
                'target_input_id',v_raw
            );
        end if;
        v:=jsonb_set(v,'{target_entity_id}',to_jsonb(v_mapped),true);
    end if;

    if nullif(v->>'target_asset_id','') is not null then
        v_raw:=v->>'target_asset_id';
        v_mapped:=public.pc_mapped_id(p_job,'asset',v_raw);
        if not public.pc_object_exists('asset',v_mapped) then
            return jsonb_build_object(
                'status','REVIEW',
                'reason','MISSING_TARGET_ASSET_ENDPOINT',
                'target_asset_id',v_mapped,
                'target_input_id',v_raw
            );
        end if;
        v:=jsonb_set(v,'{target_asset_id}',to_jsonb(v_mapped),true);
    end if;

    -- ---------------------------------------------------------------
    -- pc_transactions.operating_control is boolean in the live schema.
    -- Accept real booleans / common boolean strings. Preserve any
    -- descriptive text such as "developer" in metadata instead.
    -- ---------------------------------------------------------------
    if v ? 'operating_control' then
        if jsonb_typeof(v->'operating_control')='boolean' then
            null; -- already valid
        else
            v_raw:=lower(trim(coalesce(v->>'operating_control','')));

            if v_raw in ('true','t','yes','y','1') then
                v:=jsonb_set(v,'{operating_control}','true'::jsonb,true);

            elsif v_raw in ('false','f','no','n','0') then
                v:=jsonb_set(v,'{operating_control}','false'::jsonb,true);

            elsif v_raw='' then
                v:=v-'operating_control';

            else
                v_meta:=case
                    when jsonb_typeof(v->'metadata')='object' then v->'metadata'
                    else '{}'::jsonb
                end;

                v_meta:=jsonb_set(
                    v_meta,
                    '{operating_control_label}',
                    to_jsonb(v->>'operating_control'),
                    true
                );

                v:=jsonb_set(v,'{metadata}',v_meta,true);
                v:=v-'operating_control';
            end if;
        end if;
    end if;

    perform public.pc_upsert_json(
        'pc_transactions',
        v,
        array['transaction_id']
    );

    return jsonb_build_object(
        'status','OK',
        'transaction_id',v->>'transaction_id'
    );
end;
$$;


-- ---------------------------------------------------------------------------
-- 3. Replace processor v5 IN PLACE so Power Admin's existing retry action
--    picks up the corrected relationship + transaction logic.
-- ---------------------------------------------------------------------------
create or replace function public.pc_process_ingestion_job_v5(
    p_ingestion_job_id uuid
)
returns jsonb
language plpgsql
security definer
set search_path=public
as $$
declare
    r record;
    v_result jsonb;
    v_payload jsonb;
    v_processed int:=0;
    v_created int:=0;
    v_upserted int:=0;
    v_review int:=0;
    v_errors int:=0;
    v_edges int:=0;
begin
    -- ---------------------------------------------------------------
    -- Canonical object parents first.
    -- ---------------------------------------------------------------
    for r in
        select *
        from public.pc_staged_records
        where ingestion_job_id=p_ingestion_job_id
          and coalesce(review_status,'pending')<>'applied'
          and target_table in (
              'pc_entities',
              'pc_assets',
              'pc_mobile_assets',
              'pc_events'
          )
        order by
            case target_table
                when 'pc_entities' then 1
                when 'pc_assets' then 2
                when 'pc_mobile_assets' then 3
                when 'pc_events' then 4
                else 9
            end,
            created_at nulls last
    loop
        begin
            if r.target_table='pc_entities' then
                v_result:=public.pc_resolve_upsert_entity(
                    p_ingestion_job_id,
                    r.payload
                );

            elsif r.target_table='pc_assets' then
                v_result:=public.pc_resolve_upsert_asset(
                    p_ingestion_job_id,
                    r.payload
                );

            elsif r.target_table='pc_mobile_assets' then
                v_result:=public.pc_resolve_upsert_mobile_asset(
                    p_ingestion_job_id,
                    public.pc_source_fk_safe_payload(r.payload)
                );

            else
                v_result:=public.pc_resolve_upsert_event(
                    p_ingestion_job_id,
                    r.payload
                );
            end if;

            if v_result->>'status'='REVIEW' then
                update public.pc_staged_records
                set
                    resolution_status='AMBIGUOUS',
                    review_status='pending',
                    validation_status='reviewed',
                    resolution_method=v_result->>'reason',
                    candidate_count=coalesce((v_result->>'candidate_count')::int,0)
                where staged_record_id=r.staged_record_id;

                v_review:=v_review+1;

            else
                update public.pc_staged_records
                set
                    review_status='applied',
                    validation_status='validated',
                    resolution_status='MATCHED',
                    resolution_method=lower(v_result->>'action'),
                    resolved_entity_id=v_result->>'canonical_id',
                    resolution_confidence=1
                where staged_record_id=r.staged_record_id;

                if v_result->>'action'='CREATE' then
                    v_created:=v_created+1;
                else
                    v_upserted:=v_upserted+1;
                end if;

                v_processed:=v_processed+1;
            end if;

        exception when others then
            update public.pc_staged_records
            set
                resolution_status='INVALID',
                validation_status='invalid',
                review_status='pending',
                resolution_method='PROCESS_ERROR: '||sqlerrm
            where staged_record_id=r.staged_record_id;

            v_errors:=v_errors+1;
        end;
    end loop;

    -- ---------------------------------------------------------------
    -- Graph edges second.
    -- ---------------------------------------------------------------
    for r in
        select *
        from public.pc_staged_records
        where ingestion_job_id=p_ingestion_job_id
          and coalesce(review_status,'pending')<>'applied'
          and target_table in ('pc_relationships','pc_event_links')
        order by
            case target_table
                when 'pc_relationships' then 1
                else 2
            end,
            created_at nulls last
    loop
        begin
            if r.target_table='pc_relationships' then
                v_result:=public.pc_upsert_relationship_from_payload(
                    p_ingestion_job_id,
                    r.payload
                );
            else
                v_result:=public.pc_upsert_event_link_from_payload(
                    p_ingestion_job_id,
                    r.payload
                );
            end if;

            if v_result->>'status'='REVIEW' then
                update public.pc_staged_records
                set
                    resolution_status=
                        case
                            when v_result->>'reason' like 'MISSING_%'
                            then 'BROKEN_REFERENCE'
                            else 'UNRESOLVED'
                        end,
                    validation_status='reviewed',
                    review_status='pending',
                    resolution_method=v_result->>'reason'
                where staged_record_id=r.staged_record_id;

                v_review:=v_review+1;

            else
                update public.pc_staged_records
                set
                    review_status='applied',
                    validation_status='validated',
                    resolution_status='MATCHED',
                    resolution_method='canonical_edge_upsert',
                    resolution_confidence=1
                where staged_record_id=r.staged_record_id;

                v_processed:=v_processed+1;
                v_edges:=v_edges+1;
            end if;

        exception when foreign_key_violation then
            update public.pc_staged_records
            set
                resolution_status='BROKEN_REFERENCE',
                validation_status='reviewed',
                review_status='pending',
                resolution_method='MISSING_CANONICAL_ENDPOINT: '||sqlerrm
            where staged_record_id=r.staged_record_id;

            v_review:=v_review+1;

        when others then
            update public.pc_staged_records
            set
                resolution_status='INVALID',
                validation_status='invalid',
                review_status='pending',
                resolution_method='EDGE_PROCESS_ERROR: '||sqlerrm
            where staged_record_id=r.staged_record_id;

            v_errors:=v_errors+1;
        end;
    end loop;

    -- ---------------------------------------------------------------
    -- Direct/optional canonical tables last.
    -- ---------------------------------------------------------------
    for r in
        select *
        from public.pc_staged_records
        where ingestion_job_id=p_ingestion_job_id
          and coalesce(review_status,'pending')<>'applied'
          and target_table in (
              'pc_transactions',
              'pc_transport_routes',
              'pc_chokepoints',
              'pc_market_instruments',
              'pc_trade_flows',
              'pc_supply_series',
              'pc_observations'
          )
        order by created_at nulls last
    loop
        begin
            if r.target_table='pc_transactions' then
                v_result:=public.pc_upsert_transaction_from_payload(
                    p_ingestion_job_id,
                    r.payload
                );

                if v_result->>'status'='REVIEW' then
                    update public.pc_staged_records
                    set
                        resolution_status=
                            case
                                when v_result->>'reason' like 'MISSING_%'
                                then 'BROKEN_REFERENCE'
                                else 'UNRESOLVED'
                            end,
                        validation_status='reviewed',
                        review_status='pending',
                        resolution_method=v_result->>'reason'
                    where staged_record_id=r.staged_record_id;

                    v_review:=v_review+1;
                    continue;
                end if;

            else
                v_payload:=public.pc_source_fk_safe_payload(r.payload);

                if r.target_table='pc_transport_routes' then
                    v_result:=public.pc_upsert_json(
                        r.target_table,
                        v_payload,
                        array['route_id']
                    );
                elsif r.target_table='pc_chokepoints' then
                    v_result:=public.pc_upsert_json(
                        r.target_table,
                        v_payload,
                        array['chokepoint_id']
                    );
                elsif r.target_table='pc_market_instruments' then
                    v_result:=public.pc_upsert_json(
                        r.target_table,
                        v_payload,
                        array['market_instrument_id']
                    );
                elsif r.target_table='pc_trade_flows' then
                    v_result:=public.pc_upsert_json(
                        r.target_table,
                        v_payload,
                        array['trade_flow_id']
                    );
                elsif r.target_table='pc_supply_series' then
                    v_result:=public.pc_upsert_json(
                        r.target_table,
                        v_payload,
                        array['supply_series_id']
                    );
                else
                    v_result:=public.pc_upsert_json(
                        r.target_table,
                        v_payload,
                        array['observation_id']
                    );
                end if;
            end if;

            update public.pc_staged_records
            set
                review_status='applied',
                validation_status='validated',
                resolution_status='MATCHED',
                resolution_method='direct_upsert',
                resolution_confidence=1
            where staged_record_id=r.staged_record_id;

            v_processed:=v_processed+1;
            v_upserted:=v_upserted+1;

        exception when others then
            update public.pc_staged_records
            set
                resolution_status='INVALID',
                validation_status='invalid',
                review_status='pending',
                resolution_method='DIRECT_UPSERT_ERROR: '||sqlerrm
            where staged_record_id=r.staged_record_id;

            v_errors:=v_errors+1;
        end;
    end loop;

    update public.pc_ingestion_jobs
    set
        status=
            case
                when v_review=0 and v_errors=0
                then 'completed'
                else 'review'
            end,
        completed_at=
            case
                when v_review=0 and v_errors=0
                then now()
                else completed_at
            end,
        stats=
            coalesce(stats,'{}'::jsonb)
            || jsonb_build_object(
                'processor','pc_process_ingestion_job_v5',
                'processed',v_processed,
                'created',v_created,
                'upserted',v_upserted,
                'edges',v_edges,
                'review',v_review,
                'errors',v_errors
            )
    where ingestion_job_id=p_ingestion_job_id;

    return jsonb_build_object(
        'job_id',p_ingestion_job_id,
        'processed',v_processed,
        'created',v_created,
        'upserted',v_upserted,
        'edges',v_edges,
        'review',v_review,
        'errors',v_errors,
        'status',
        case
            when v_review=0 and v_errors=0
            then 'completed'
            else 'review'
        end
    );
end;
$$;


grant execute on function public.pc_upsert_relationship_from_payload(uuid,jsonb)
to authenticated;

grant execute on function public.pc_upsert_transaction_from_payload(uuid,jsonb)
to authenticated;

grant execute on function public.pc_process_ingestion_job_v5(uuid)
to authenticated;

commit;


-- ---------------------------------------------------------------------------
-- CURRENT QINZHOU EXPECTATION
-- ---------------------------------------------------------------------------
-- Your latest screenshot shows:
--
--   Total       21
--   Applied     14
--   Review       7
--   Broken refs  6
--
-- Remaining:
--
--   pc_relationships   6  MISSING_SOURCE_ENDPOINT
--   pc_transactions    1  DIRECT_UPSERT_ERROR:
--                         invalid input syntax for type boolean: "developer"
--
-- After installing 053:
--
--   Open the same Qinzhou job in Power Admin.
--   Click "Retry unresolved rows in this package".
--
-- Expected:
--   relationships  6 -> MATCHED / applied
--   transaction    1 -> MATCHED / applied
--
-- Final expected package:
--   Total       21
--   Applied     21
--   Review       0
--   Broken refs  0
