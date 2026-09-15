-- Power & Corridors
-- 052_source_fk_safe_objects_and_direct_tables.sql
--
-- Fixes the failure pattern seen in the Qinzhou package:
--   * pc_entities source_id FK failures
--   * pc_assets source_id FK failures
--   * pc_assets owner/operator FK failures caused by parent entity failure
--   * downstream BROKEN_REFERENCE relationships/event_links
--   * pc_transactions / pc_transport_routes excluded when their staging types are
--     not registered in pc_meta_entity_types
--
-- This migration DOES NOT weaken canonical endpoint integrity. It preserves
-- workbook source references in metadata/source_url, but only keeps source_id /
-- evidence_source_id when the referenced canonical pc_sources row actually exists.
--
-- Safe to run repeatedly.

begin;

-- ---------------------------------------------------------------------------
-- 1. Ensure optional canonical staging tables used by current loader exist.
--    IMPORTANT: pc_meta_entity_types has unique constraints on BOTH entity_type
--    and table_name. Existing deployments may already register pc_transactions
--    or pc_transport_routes under a different entity_type. Prefer the existing
--    table_name registration rather than inserting a duplicate row.
-- ---------------------------------------------------------------------------
do $$
begin
    if to_regclass('public.pc_meta_entity_types') is not null then
        -- TRANSACTIONS -------------------------------------------------------
        if exists (
            select 1 from public.pc_meta_entity_types
            where table_name='pc_transactions'
        ) then
            update public.pc_meta_entity_types
               set primary_key_column='transaction_id',
                   display_name_column=coalesce(nullif(display_name_column,''),'target_name'),
                   id_prefix=coalesce(nullif(id_prefix,''),'TXN_'),
                   canonical=true,
                   active=true,
                   allow_insert=true,
                   allow_update=true,
                   description=coalesce(nullif(description,''),'Canonical commercial transactions, investments and deals')
             where table_name='pc_transactions';

        elsif exists (
            select 1 from public.pc_meta_entity_types
            where entity_type='transaction'
        ) then
            update public.pc_meta_entity_types
               set table_name='pc_transactions',
                   primary_key_column='transaction_id',
                   display_name_column=coalesce(nullif(display_name_column,''),'target_name'),
                   id_prefix=coalesce(nullif(id_prefix,''),'TXN_'),
                   canonical=true,
                   active=true,
                   allow_insert=true,
                   allow_update=true,
                   description='Canonical commercial transactions, investments and deals'
             where entity_type='transaction';

        else
            insert into public.pc_meta_entity_types(
                entity_type,table_name,primary_key_column,display_name_column,id_prefix,
                canonical,active,allow_insert,allow_update,description
            ) values (
                'transaction','pc_transactions','transaction_id','target_name','TXN_',
                true,true,true,true,'Canonical commercial transactions, investments and deals'
            );
        end if;

        -- ROUTES -------------------------------------------------------------
        if exists (
            select 1 from public.pc_meta_entity_types
            where table_name='pc_transport_routes'
        ) then
            update public.pc_meta_entity_types
               set primary_key_column='route_id',
                   display_name_column=coalesce(nullif(display_name_column,''),'route_name'),
                   id_prefix=coalesce(nullif(id_prefix,''),'ROUTE_'),
                   canonical=true,
                   active=true,
                   allow_insert=true,
                   allow_update=true,
                   description=coalesce(nullif(description,''),'Canonical transport routes and corridors')
             where table_name='pc_transport_routes';

        elsif exists (
            select 1 from public.pc_meta_entity_types
            where entity_type='route'
        ) then
            update public.pc_meta_entity_types
               set table_name='pc_transport_routes',
                   primary_key_column='route_id',
                   display_name_column=coalesce(nullif(display_name_column,''),'route_name'),
                   id_prefix=coalesce(nullif(id_prefix,''),'ROUTE_'),
                   canonical=true,
                   active=true,
                   allow_insert=true,
                   allow_update=true,
                   description='Canonical transport routes and corridors'
             where entity_type='route';

        else
            insert into public.pc_meta_entity_types(
                entity_type,table_name,primary_key_column,display_name_column,id_prefix,
                canonical,active,allow_insert,allow_update,description
            ) values (
                'route','pc_transport_routes','route_id','route_name','ROUTE_',
                true,true,true,true,'Canonical transport routes and corridors'
            );
        end if;
    end if;
end $$;

-- ---------------------------------------------------------------------------
-- 2. Generic source-FK safety helper (redefines 049 helper defensively).
-- ---------------------------------------------------------------------------
create or replace function public.pc_source_fk_safe_payload(p_payload jsonb)
returns jsonb
language plpgsql
stable
security definer
set search_path=public
as $$
declare
    v jsonb := coalesce(p_payload,'{}'::jsonb);
    v_source_id text := nullif(trim(v->>'source_id'),'');
    v_meta jsonb;
    v_exists boolean := false;
begin
    if v_source_id is null then
        return v;
    end if;

    v_meta := case when jsonb_typeof(v->'metadata')='object' then v->'metadata' else '{}'::jsonb end;
    v_meta := jsonb_set(v_meta,'{source_reference_id}',to_jsonb(v_source_id),true);
    v := jsonb_set(v,'{metadata}',v_meta,true);

    if to_regclass('public.pc_sources') is not null then
        execute 'select exists(select 1 from public.pc_sources where source_id::text=$1)'
           into v_exists using v_source_id;
    end if;

    if not v_exists then
        v := v - 'source_id';
    end if;
    return v;
end;
$$;

create or replace function public.pc_evidence_source_fk_safe_payload(p_payload jsonb)
returns jsonb
language plpgsql
stable
security definer
set search_path=public
as $$
declare
    v jsonb := coalesce(p_payload,'{}'::jsonb);
    v_source_id text := nullif(trim(v->>'evidence_source_id'),'');
    v_meta jsonb;
    v_exists boolean := false;
begin
    if v_source_id is null then
        return v;
    end if;

    v_meta := case when jsonb_typeof(v->'metadata')='object' then v->'metadata' else '{}'::jsonb end;
    v_meta := jsonb_set(v_meta,'{evidence_source_reference_id}',to_jsonb(v_source_id),true);
    v := jsonb_set(v,'{metadata}',v_meta,true);

    if to_regclass('public.pc_sources') is not null then
        execute 'select exists(select 1 from public.pc_sources where source_id::text=$1)'
           into v_exists using v_source_id;
    end if;

    if not v_exists then
        v := v - 'evidence_source_id';
    end if;
    return v;
end;
$$;

-- ---------------------------------------------------------------------------
-- 3. Entity resolver: schema-safe + source-FK-safe.
-- ---------------------------------------------------------------------------
create or replace function public.pc_resolve_upsert_entity(p_job uuid,p_payload jsonb)
returns jsonb
language plpgsql
security definer
set search_path=public
as $$
declare
    v_source_id text := nullif(p_payload->>'entity_id','');
    v_id text;
    v_count integer;
    v_payload jsonb := public.pc_source_fk_safe_payload(p_payload);
    v_action text;
    v_payload_country text := coalesce(nullif(p_payload->>'hq_country',''),nullif(p_payload->>'country',''));
begin
    if not public.pc_minimum_identity_ok('entity',p_payload) then
        return jsonb_build_object('status','REVIEW','reason','INSUFFICIENT_ENTITY_IDENTITY');
    end if;

    if v_source_id is not null and exists(select 1 from public.pc_entities e where e.entity_id::text=v_source_id) then
        v_id:=v_source_id; v_action:='UPSERT_ID';
    else
        v_count:=public.pc_alias_match_count('entity',p_payload->>'name');
        if v_count=1 then
            v_id:=public.pc_alias_unique_id('entity',p_payload->>'name'); v_action:='UPSERT_ALIAS';
        elsif v_count>1 then
            return jsonb_build_object('status','REVIEW','reason','AMBIGUOUS_ENTITY_ALIAS','candidate_count',v_count);
        end if;

        if v_id is null then
            select count(*),min(e.entity_id::text)
              into v_count,v_id
              from public.pc_entities e
             where public.pc_norm_identity_text(e.name)=public.pc_norm_identity_text(p_payload->>'name')
               and (v_payload_country is null or public.pc_norm_identity_text(coalesce(to_jsonb(e)->>'hq_country',to_jsonb(e)->>'country'))=public.pc_norm_identity_text(v_payload_country))
               and (nullif(p_payload->>'entity_type','') is null or public.pc_norm_identity_text(coalesce(to_jsonb(e)->>'entity_type',to_jsonb(e)->>'type'))=public.pc_norm_identity_text(p_payload->>'entity_type'));
            if v_count>1 then
                return jsonb_build_object('status','REVIEW','reason','AMBIGUOUS_ENTITY','candidate_count',v_count);
            elsif v_count=1 then v_action:='UPSERT_NAME';
            else v_id:=null;
            end if;
        end if;

        if v_id is null then
            v_id:='ENTITY_'||upper(substr(md5(
                coalesce(public.pc_norm_identity_text(p_payload->>'name'),'')||'|'||
                coalesce(public.pc_norm_identity_text(v_payload_country),'')||'|'||
                coalesce(public.pc_norm_identity_text(p_payload->>'entity_type'),'')
            ),1,20));
            v_action:='CREATE';
        end if;
    end if;

    if v_payload_country is not null then
        v_payload:=jsonb_set(v_payload,'{hq_country}',to_jsonb(v_payload_country),true);
    end if;
    v_payload:=jsonb_set(v_payload,'{entity_id}',to_jsonb(v_id),true);

    perform public.pc_upsert_json('pc_entities',v_payload,array['entity_id']);
    perform public.pc_map_ingestion_key(p_job,'entity',coalesce(v_source_id,v_id),v_id,lower(v_action));

    insert into public.pc_identity_aliases_v2(object_type,canonical_id,alias_name,alias_type)
    values('entity',v_id,p_payload->>'name',case when v_action='CREATE' then 'official' else 'source' end)
    on conflict (object_type,canonical_id,normalized_alias) do nothing;

    return jsonb_build_object('status','OK','canonical_id',v_id,'action',v_action);
end;
$$;

-- ---------------------------------------------------------------------------
-- 4. Asset resolver: source-FK-safe; owner/operator remapped after entities.
-- ---------------------------------------------------------------------------
create or replace function public.pc_resolve_upsert_asset(p_job uuid,p_payload jsonb)
returns jsonb
language plpgsql
security definer
set search_path=public
as $$
declare
    v_source_id text := nullif(p_payload->>'asset_id','');
    v_id text; v_count integer;
    v_payload jsonb:=public.pc_source_fk_safe_payload(p_payload);
    v_action text;
begin
    if not public.pc_minimum_identity_ok('asset',p_payload) then
        return jsonb_build_object('status','REVIEW','reason','INSUFFICIENT_ASSET_IDENTITY');
    end if;

    if v_source_id is not null and exists(select 1 from public.pc_assets where asset_id::text=v_source_id) then
        v_id:=v_source_id; v_action:='UPSERT_ID';
    else
        v_count:=public.pc_alias_match_count('asset',p_payload->>'name');
        if v_count=1 then
            v_id:=public.pc_alias_unique_id('asset',p_payload->>'name'); v_action:='UPSERT_ALIAS';
        elsif v_count>1 then
            return jsonb_build_object('status','REVIEW','reason','AMBIGUOUS_ASSET_ALIAS','candidate_count',v_count);
        end if;

        if v_id is null then
            select count(*),min(asset_id::text) into v_count,v_id
              from public.pc_assets
             where public.pc_norm_identity_text(name)=public.pc_norm_identity_text(p_payload->>'name')
               and (nullif(p_payload->>'country','') is null or public.pc_norm_identity_text(country::text)=public.pc_norm_identity_text(p_payload->>'country'))
               and (nullif(p_payload->>'region_city','') is null or public.pc_norm_identity_text(region_city::text)=public.pc_norm_identity_text(p_payload->>'region_city'))
               and public.pc_norm_identity_text(asset_type::text)=public.pc_norm_identity_text(p_payload->>'asset_type');
            if v_count>1 then
                return jsonb_build_object('status','REVIEW','reason','AMBIGUOUS_ASSET','candidate_count',v_count);
            elsif v_count=1 then v_action:='UPSERT_NAME';
            else v_id:=null;
            end if;
        end if;

        if v_id is null then
            v_id:='ASSET_'||upper(substr(md5(
                coalesce(public.pc_norm_identity_text(p_payload->>'name'),'')||'|'||
                coalesce(public.pc_norm_identity_text(p_payload->>'country'),'')||'|'||
                coalesce(public.pc_norm_identity_text(p_payload->>'region_city'),'')||'|'||
                coalesce(public.pc_norm_identity_text(p_payload->>'asset_type'),'')
            ),1,20));
            v_action:='CREATE';
        end if;
    end if;

    if nullif(v_payload->>'owner_entity_id','') is not null then
        v_payload:=jsonb_set(v_payload,'{owner_entity_id}',to_jsonb(public.pc_mapped_id(p_job,'entity',v_payload->>'owner_entity_id')),true);
    end if;
    if nullif(v_payload->>'operator_entity_id','') is not null then
        v_payload:=jsonb_set(v_payload,'{operator_entity_id}',to_jsonb(public.pc_mapped_id(p_job,'entity',v_payload->>'operator_entity_id')),true);
    end if;

    v_payload:=jsonb_set(v_payload,'{asset_id}',to_jsonb(v_id),true);
    perform public.pc_upsert_json('pc_assets',v_payload,array['asset_id']);
    perform public.pc_map_ingestion_key(p_job,'asset',coalesce(v_source_id,v_id),v_id,lower(v_action));

    insert into public.pc_identity_aliases_v2(object_type,canonical_id,alias_name,alias_type)
    values('asset',v_id,p_payload->>'name',case when v_action='CREATE' then 'official' else 'source' end)
    on conflict (object_type,canonical_id,normalized_alias) do nothing;

    return jsonb_build_object('status','OK','canonical_id',v_id,'action',v_action);
end;
$$;

-- ---------------------------------------------------------------------------
-- 5. Relationship writer: endpoint-safe + evidence-source-FK-safe.
-- ---------------------------------------------------------------------------
create or replace function public.pc_upsert_relationship_from_payload(p_job uuid,p_payload jsonb)
returns jsonb
language plpgsql
security definer
set search_path=public
as $$
declare
    v jsonb:=public.pc_evidence_source_fk_safe_payload(public.pc_source_fk_safe_payload(p_payload));
    v_source_type text:=lower(v->>'source_type');
    v_target_type text:=lower(v->>'target_type');
    v_source text; v_target text;
begin
    v_source:=public.pc_mapped_id(p_job,v_source_type,v->>'source_id');
    v_target:=public.pc_mapped_id(p_job,v_target_type,v->>'target_id');

    if not public.pc_object_exists(v_source_type,v_source) then
        return jsonb_build_object('status','REVIEW','reason','MISSING_SOURCE_ENDPOINT','source_type',v_source_type,'source_id',v_source);
    end if;
    if not public.pc_object_exists(v_target_type,v_target) then
        return jsonb_build_object('status','REVIEW','reason','MISSING_TARGET_ENDPOINT','target_type',v_target_type,'target_id',v_target);
    end if;

    v:=jsonb_set(v,'{source_id}',to_jsonb(v_source),true);
    v:=jsonb_set(v,'{target_id}',to_jsonb(v_target),true);
    perform public.pc_upsert_json('pc_relationships',v,array['relationship_id']);
    return jsonb_build_object('status','OK','relationship_id',v->>'relationship_id','source_id',v_source,'target_id',v_target);
end;
$$;

-- ---------------------------------------------------------------------------
-- 6. Processor v5: source-FK-safe direct tables as well.
-- ---------------------------------------------------------------------------
create or replace function public.pc_process_ingestion_job_v5(p_ingestion_job_id uuid)
returns jsonb
language plpgsql
security definer
set search_path=public
as $$
declare
    r record;
    v_result jsonb;
    v_payload jsonb;
    v_processed int:=0; v_created int:=0; v_upserted int:=0; v_review int:=0; v_errors int:=0; v_edges int:=0;
begin
    for r in
        select * from public.pc_staged_records
         where ingestion_job_id=p_ingestion_job_id
           and coalesce(review_status,'pending')<>'applied'
           and target_table in ('pc_entities','pc_assets','pc_mobile_assets','pc_events')
         order by case target_table when 'pc_entities' then 1 when 'pc_assets' then 2 when 'pc_mobile_assets' then 3 when 'pc_events' then 4 else 9 end,
                  created_at nulls last
    loop
        begin
            if r.target_table='pc_entities' then v_result:=public.pc_resolve_upsert_entity(p_ingestion_job_id,r.payload);
            elsif r.target_table='pc_assets' then v_result:=public.pc_resolve_upsert_asset(p_ingestion_job_id,r.payload);
            elsif r.target_table='pc_mobile_assets' then v_result:=public.pc_resolve_upsert_mobile_asset(p_ingestion_job_id,public.pc_source_fk_safe_payload(r.payload));
            else v_result:=public.pc_resolve_upsert_event(p_ingestion_job_id,r.payload);
            end if;

            if v_result->>'status'='REVIEW' then
                update public.pc_staged_records set resolution_status='AMBIGUOUS',review_status='pending',validation_status='reviewed',
                       resolution_method=v_result->>'reason',candidate_count=coalesce((v_result->>'candidate_count')::int,0)
                 where staged_record_id=r.staged_record_id;
                v_review:=v_review+1;
            else
                update public.pc_staged_records set review_status='applied',validation_status='validated',resolution_status='MATCHED',
                       resolution_method=lower(v_result->>'action'),resolved_entity_id=v_result->>'canonical_id',resolution_confidence=1
                 where staged_record_id=r.staged_record_id;
                if v_result->>'action'='CREATE' then v_created:=v_created+1; else v_upserted:=v_upserted+1; end if;
                v_processed:=v_processed+1;
            end if;
        exception when others then
            update public.pc_staged_records set resolution_status='INVALID',validation_status='invalid',review_status='pending',
                   resolution_method='PROCESS_ERROR: '||sqlerrm
             where staged_record_id=r.staged_record_id;
            v_errors:=v_errors+1;
        end;
    end loop;

    for r in
        select * from public.pc_staged_records
         where ingestion_job_id=p_ingestion_job_id
           and coalesce(review_status,'pending')<>'applied'
           and target_table in ('pc_relationships','pc_event_links')
         order by case target_table when 'pc_relationships' then 1 else 2 end,created_at nulls last
    loop
        begin
            if r.target_table='pc_relationships' then
                v_result:=public.pc_upsert_relationship_from_payload(p_ingestion_job_id,r.payload);
            else
                v_result:=public.pc_upsert_event_link_from_payload(p_ingestion_job_id,r.payload);
            end if;
            if v_result->>'status'='REVIEW' then
                update public.pc_staged_records
                   set resolution_status=case when v_result->>'reason' like 'MISSING_%' then 'BROKEN_REFERENCE' else 'UNRESOLVED' end,
                       validation_status='reviewed',review_status='pending',resolution_method=v_result->>'reason'
                 where staged_record_id=r.staged_record_id;
                v_review:=v_review+1;
            else
                update public.pc_staged_records
                   set review_status='applied',validation_status='validated',resolution_status='MATCHED',
                       resolution_method='canonical_edge_upsert',resolution_confidence=1
                 where staged_record_id=r.staged_record_id;
                v_processed:=v_processed+1; v_edges:=v_edges+1;
            end if;
        exception when foreign_key_violation then
            update public.pc_staged_records set resolution_status='BROKEN_REFERENCE',validation_status='reviewed',review_status='pending',
                   resolution_method='MISSING_CANONICAL_ENDPOINT: '||sqlerrm
             where staged_record_id=r.staged_record_id;
            v_review:=v_review+1;
        when others then
            update public.pc_staged_records set resolution_status='INVALID',validation_status='invalid',review_status='pending',
                   resolution_method='EDGE_PROCESS_ERROR: '||sqlerrm
             where staged_record_id=r.staged_record_id;
            v_errors:=v_errors+1;
        end;
    end loop;

    for r in
        select * from public.pc_staged_records
         where ingestion_job_id=p_ingestion_job_id
           and coalesce(review_status,'pending')<>'applied'
           and target_table in ('pc_transactions','pc_transport_routes','pc_chokepoints','pc_market_instruments','pc_trade_flows','pc_supply_series','pc_observations')
         order by created_at nulls last
    loop
        begin
            v_payload:=public.pc_source_fk_safe_payload(r.payload);
            if r.target_table='pc_transactions' then v_result:=public.pc_upsert_json(r.target_table,v_payload,array['transaction_id']);
            elsif r.target_table='pc_transport_routes' then v_result:=public.pc_upsert_json(r.target_table,v_payload,array['route_id']);
            elsif r.target_table='pc_chokepoints' then v_result:=public.pc_upsert_json(r.target_table,v_payload,array['chokepoint_id']);
            elsif r.target_table='pc_market_instruments' then v_result:=public.pc_upsert_json(r.target_table,v_payload,array['market_instrument_id']);
            elsif r.target_table='pc_trade_flows' then v_result:=public.pc_upsert_json(r.target_table,v_payload,array['trade_flow_id']);
            elsif r.target_table='pc_supply_series' then v_result:=public.pc_upsert_json(r.target_table,v_payload,array['supply_series_id']);
            else v_result:=public.pc_upsert_json(r.target_table,v_payload,array['observation_id']); end if;

            update public.pc_staged_records set review_status='applied',validation_status='validated',resolution_status='MATCHED',resolution_method='direct_upsert',resolution_confidence=1
             where staged_record_id=r.staged_record_id;
            v_processed:=v_processed+1; v_upserted:=v_upserted+1;
        exception when others then
            update public.pc_staged_records set resolution_status='INVALID',validation_status='invalid',review_status='pending',
                   resolution_method='DIRECT_UPSERT_ERROR: '||sqlerrm
             where staged_record_id=r.staged_record_id;
            v_errors:=v_errors+1;
        end;
    end loop;

    update public.pc_ingestion_jobs
       set status=case when v_review=0 and v_errors=0 then 'completed' else 'review' end,
           completed_at=case when v_review=0 and v_errors=0 then now() else completed_at end,
           stats=coalesce(stats,'{}'::jsonb)||jsonb_build_object(
               'processor','pc_process_ingestion_job_v5','processed',v_processed,'created',v_created,
               'upserted',v_upserted,'edges',v_edges,'review',v_review,'errors',v_errors)
     where ingestion_job_id=p_ingestion_job_id;

    return jsonb_build_object('job_id',p_ingestion_job_id,'processed',v_processed,'created',v_created,
                              'upserted',v_upserted,'edges',v_edges,'review',v_review,'errors',v_errors,
                              'status',case when v_review=0 and v_errors=0 then 'completed' else 'review' end);
end;
$$;

grant execute on function public.pc_source_fk_safe_payload(jsonb) to authenticated;
grant execute on function public.pc_evidence_source_fk_safe_payload(jsonb) to authenticated;
grant execute on function public.pc_resolve_upsert_entity(uuid,jsonb) to authenticated;
grant execute on function public.pc_resolve_upsert_asset(uuid,jsonb) to authenticated;
grant execute on function public.pc_upsert_relationship_from_payload(uuid,jsonb) to authenticated;
grant execute on function public.pc_process_ingestion_job_v5(uuid) to authenticated;

commit;

-- ---------------------------------------------------------------------------
-- EXPECTED RECOVERY FOR THE CURRENT QINZHOU JOB
-- ---------------------------------------------------------------------------
-- After installing 052, use Power Admin -> Retry unresolved rows in this package.
-- Expected current 20-row job:
--   pc_entities        3 -> MATCHED/APPLIED
--   pc_assets          4 -> MATCHED/APPLIED
--   pc_relationships   6 -> MATCHED/APPLIED
--   pc_events          1 -> already applied
--   pc_event_links     5 -> MATCHED/APPLIED
--   pc_transport_routes 1 -> already applied
--   Total             20 -> 20 applied, 0 review, 0 broken refs
--
-- Then RELOAD the workbook once. 052 registers pc_transactions, so the transaction
-- sheet should now be included and the package total should become 21. Existing
-- canonical objects will upsert/match; the RMB941.22m transaction should be added.
