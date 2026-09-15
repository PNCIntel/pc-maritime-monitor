-- Power & Corridors
-- 056_numeric_and_fk_safe_ingestion.sql
--
-- PURPOSE
-- Fix the remaining repeated ingestion errors shown in the 105-row package:
--
--   10 x pc_event_links       -> MISSING_EVENT_ENDPOINT
--    2 x parent/event rows    -> invalid input syntax for type numeric: "true"
--    4 x pc_transport_routes  -> foreign-key violation on direct upsert
--
-- The child event-link failures are downstream. Fix the parent rows and direct
-- route FK handling first; then retry so the links can resolve.
--
-- 056 makes two system-wide improvements:
--
-- 1) Typed-column normalization in pc_schema_safe_payload()
--    * booleans remain handled
--    * numeric/integer columns now accept valid numeric strings
--    * non-numeric text such as "true" is preserved under
--      metadata.ingest_labels.<column> and removed from the typed field instead
--      of crashing the record
--
-- 2) Generic FK-safe direct writes
--    * inspects the LIVE PostgreSQL FK constraints
--    * remaps package-local entity/asset/mobile_asset/event IDs through
--      pc_ingestion_key_map when possible
--    * source_id/evidence-source FKs are removed from typed FK columns when the
--      source registry row does not exist, while preserving the original value
--      in metadata
--    * optional unresolved FKs are preserved in metadata and omitted instead of
--      crashing the whole direct record
--    * required unresolved FKs return REVIEW rather than silently inventing data
--
-- This is a common-layer fix, not a workbook-specific patch.
-- Safe to run repeatedly.

begin;

-- ===========================================================================
-- A. TYPE-SAFE PAYLOAD NORMALIZER
-- ===========================================================================
create or replace function public.pc_schema_safe_payload(
    p_table text,
    p_payload jsonb
)
returns jsonb
language plpgsql
stable
security definer
set search_path=public
as $$
declare
    v_name text := replace(p_table,'public.','');
    v jsonb := coalesce(p_payload,'{}'::jsonb);
    r record;
    v_raw text;
    v_norm text;
    v_meta jsonb;
    v_labels jsonb;
    v_num numeric;
begin
    if v_name !~ '^pc_[a-z0-9_]+$' then
        raise exception 'Unsafe table name: %', p_table;
    end if;

    if to_regclass('public.'||v_name) is null then
        raise exception 'Unknown canonical table: %', v_name;
    end if;

    for r in
        select
            c.column_name,
            c.data_type,
            c.udt_name
        from information_schema.columns c
        where c.table_schema='public'
          and c.table_name=v_name
          and v ? c.column_name
    loop
        -- ---------------------------------------------------------------
        -- BOOLEAN
        -- ---------------------------------------------------------------
        if r.data_type='boolean' then
            if jsonb_typeof(v->r.column_name)='boolean' then
                continue;
            end if;

            v_raw := nullif(trim(coalesce(v->>r.column_name,'')),'');
            v_norm := lower(coalesce(v_raw,''));

            if v_raw is null then
                v := v - r.column_name;

            elsif v_norm in (
                'true','t','yes','y','1',
                'active','enabled','enable',
                'control','controlled','controlling','operating control',
                'direct control','majority control'
            ) then
                v := jsonb_set(v,array[r.column_name],'true'::jsonb,true);

            elsif v_norm in (
                'false','f','no','n','0',
                'inactive','disabled','disable',
                'non-control','non control','no control',
                'not controlled','minority non-control'
            ) then
                v := jsonb_set(v,array[r.column_name],'false'::jsonb,true);

            else
                v_meta := case
                    when jsonb_typeof(v->'metadata')='object' then v->'metadata'
                    else '{}'::jsonb
                end;
                v_labels := case
                    when jsonb_typeof(v_meta->'ingest_labels')='object'
                    then v_meta->'ingest_labels'
                    else '{}'::jsonb
                end;
                v_labels := jsonb_set(v_labels,array[r.column_name],to_jsonb(v_raw),true);
                v_meta := jsonb_set(v_meta,'{ingest_labels}',v_labels,true);
                v := jsonb_set(v,'{metadata}',v_meta,true);
                v := v - r.column_name;
            end if;

        -- ---------------------------------------------------------------
        -- NUMERIC / INTEGER / FLOAT
        -- ---------------------------------------------------------------
        elsif r.data_type in (
            'smallint','integer','bigint',
            'numeric','decimal','real','double precision'
        ) then
            if jsonb_typeof(v->r.column_name)='number' then
                continue;
            end if;

            -- JSON booleans are never silently converted to 1/0 for numeric
            -- business fields; preserve the raw source value instead.
            if jsonb_typeof(v->r.column_name)='boolean' then
                v_raw := v->>r.column_name;
            else
                v_raw := nullif(trim(coalesce(v->>r.column_name,'')),'');
            end if;

            if v_raw is null then
                v := v - r.column_name;
            else
                begin
                    -- Permit commas and a leading currency symbol only when the
                    -- remainder is actually numeric.
                    v_norm := replace(v_raw,',','');
                    v_norm := regexp_replace(v_norm,'^[\$€£¥₹]\s*','','');
                    v_num := v_norm::numeric;

                    if r.data_type in ('smallint','integer','bigint') then
                        v := jsonb_set(
                            v,
                            array[r.column_name],
                            to_jsonb(trunc(v_num)::bigint),
                            true
                        );
                    else
                        v := jsonb_set(
                            v,
                            array[r.column_name],
                            to_jsonb(v_num),
                            true
                        );
                    end if;

                exception when invalid_text_representation or numeric_value_out_of_range then
                    v_meta := case
                        when jsonb_typeof(v->'metadata')='object' then v->'metadata'
                        else '{}'::jsonb
                    end;
                    v_labels := case
                        when jsonb_typeof(v_meta->'ingest_labels')='object'
                        then v_meta->'ingest_labels'
                        else '{}'::jsonb
                    end;
                    v_labels := jsonb_set(v_labels,array[r.column_name],to_jsonb(v_raw),true);
                    v_meta := jsonb_set(v_meta,'{ingest_labels}',v_labels,true);
                    v := jsonb_set(v,'{metadata}',v_meta,true);
                    v := v - r.column_name;
                end;
            end if;
        end if;
    end loop;

    return v;
end;
$$;


-- ===========================================================================
-- B. MAP A REFERENCED TABLE TO THE CANONICAL OBJECT TYPE USED BY pc_mapped_id
-- ===========================================================================
create or replace function public.pc_object_type_for_table(
    p_table text
)
returns text
language sql
stable
as $$
    select case replace($1,'public.','')
        when 'pc_entities' then 'entity'
        when 'pc_assets' then 'asset'
        when 'pc_mobile_assets' then 'mobile_asset'
        when 'pc_events' then 'event'
        when 'pc_transport_routes' then 'route'
        when 'pc_transactions' then 'transaction'
        else null
    end;
$$;


-- ===========================================================================
-- C. GENERIC LIVE-FK NORMALIZER
-- ===========================================================================
create or replace function public.pc_fk_safe_payload(
    p_job uuid,
    p_table text,
    p_payload jsonb
)
returns jsonb
language plpgsql
security definer
set search_path=public
as $$
declare
    v_name text := replace(p_table,'public.','');
    v jsonb := coalesce(p_payload,'{}'::jsonb);
    r record;
    v_raw text;
    v_mapped text;
    v_object_type text;
    v_exists boolean;
    v_meta jsonb;
    v_fk_labels jsonb;
begin
    if v_name !~ '^pc_[a-z0-9_]+$' then
        raise exception 'Unsafe table name: %', p_table;
    end if;

    if to_regclass('public.'||v_name) is null then
        raise exception 'Unknown canonical table: %', v_name;
    end if;

    -- One-column FK constraints only; that matches the canonical endpoint/source
    -- FKs currently used by these ingestion tables.
    for r in
        select
            a.attname as local_column,
            n2.nspname as ref_schema,
            c2.relname as ref_table,
            a2.attname as ref_column,
            coalesce(cols.is_nullable,'YES') as is_nullable
        from pg_constraint con
        join pg_class c1 on c1.oid=con.conrelid
        join pg_namespace n1 on n1.oid=c1.relnamespace
        join pg_class c2 on c2.oid=con.confrelid
        join pg_namespace n2 on n2.oid=c2.relnamespace
        join lateral unnest(con.conkey) with ordinality k(attnum,ord) on true
        join lateral unnest(con.confkey) with ordinality fk(attnum,ord)
          on fk.ord=k.ord
        join pg_attribute a on a.attrelid=c1.oid and a.attnum=k.attnum
        join pg_attribute a2 on a2.attrelid=c2.oid and a2.attnum=fk.attnum
        left join information_schema.columns cols
          on cols.table_schema=n1.nspname
         and cols.table_name=c1.relname
         and cols.column_name=a.attname
        where con.contype='f'
          and n1.nspname='public'
          and c1.relname=v_name
          and array_length(con.conkey,1)=1
          and v ? a.attname
    loop
        v_raw := nullif(trim(coalesce(v->>r.local_column,'')),'');
        if v_raw is null then
            v := v - r.local_column;
            continue;
        end if;

        -- Check original value first.
        execute format(
            'select exists(select 1 from %I.%I where %I::text=$1)',
            r.ref_schema,r.ref_table,r.ref_column
        )
        into v_exists
        using v_raw;

        if v_exists then
            continue;
        end if;

        -- Try this ingestion job's canonical ID mapping where the referenced
        -- table corresponds to a canonical object class.
        v_object_type := public.pc_object_type_for_table(r.ref_table);

        if v_object_type is not null then
            begin
                v_mapped := public.pc_mapped_id(p_job,v_object_type,v_raw);
            exception when others then
                v_mapped := v_raw;
            end;

            if v_mapped is not null and v_mapped<>'' then
                execute format(
                    'select exists(select 1 from %I.%I where %I::text=$1)',
                    r.ref_schema,r.ref_table,r.ref_column
                )
                into v_exists
                using v_mapped;

                if v_exists then
                    v := jsonb_set(v,array[r.local_column],to_jsonb(v_mapped),true);
                    continue;
                end if;
            end if;
        end if;

        -- Preserve unresolved optional FK value in metadata rather than causing
        -- the direct row itself to fail.
        v_meta := case
            when jsonb_typeof(v->'metadata')='object' then v->'metadata'
            else '{}'::jsonb
        end;
        v_fk_labels := case
            when jsonb_typeof(v_meta->'unresolved_fk_labels')='object'
            then v_meta->'unresolved_fk_labels'
            else '{}'::jsonb
        end;
        v_fk_labels := jsonb_set(
            v_fk_labels,
            array[r.local_column],
            jsonb_build_object(
                'value',v_raw,
                'references',r.ref_table||'.'||r.ref_column
            ),
            true
        );
        v_meta := jsonb_set(v_meta,'{unresolved_fk_labels}',v_fk_labels,true);
        v := jsonb_set(v,'{metadata}',v_meta,true);

        if upper(r.is_nullable)='YES' then
            v := v - r.local_column;
        else
            -- Keep the value so the caller receives a real REVIEW/error rather
            -- than silently fabricating a mandatory endpoint.
            null;
        end if;
    end loop;

    return v;
end;
$$;


-- ===========================================================================
-- D. COMMON DIRECT-TABLE WRITER
-- ===========================================================================
create or replace function public.pc_upsert_direct_from_payload(
    p_job uuid,
    p_table text,
    p_payload jsonb,
    p_conflict_cols text[]
)
returns jsonb
language plpgsql
security definer
set search_path=public
as $$
declare
    v jsonb;
    v_result jsonb;
begin
    -- source provenance first, live FK normalization second, typed fields third
    v := public.pc_source_fk_safe_payload(coalesce(p_payload,'{}'::jsonb));
    v := public.pc_fk_safe_payload(p_job,p_table,v);
    v := public.pc_schema_safe_payload(p_table,v);

    v_result := public.pc_upsert_json(
        p_table,
        v,
        p_conflict_cols
    );

    return jsonb_build_object(
        'status','OK',
        'table',replace(p_table,'public.',''),
        'result',v_result
    );
end;
$$;


-- ===========================================================================
-- E. REPLACE THE PROCESSOR IN PLACE
--    Parent objects -> graph edges -> optional/direct tables
-- ===========================================================================
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
    v_processed int:=0;
    v_created int:=0;
    v_upserted int:=0;
    v_review int:=0;
    v_errors int:=0;
    v_edges int:=0;
begin
    -- -----------------------------------------------------------------------
    -- PARENTS
    -- -----------------------------------------------------------------------
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
                    public.pc_schema_safe_payload(
                        'pc_entities',
                        public.pc_fk_safe_payload(
                            p_ingestion_job_id,
                            'pc_entities',
                            public.pc_source_fk_safe_payload(r.payload)
                        )
                    )
                );

            elsif r.target_table='pc_assets' then
                v_result:=public.pc_resolve_upsert_asset(
                    p_ingestion_job_id,
                    public.pc_schema_safe_payload(
                        'pc_assets',
                        public.pc_fk_safe_payload(
                            p_ingestion_job_id,
                            'pc_assets',
                            public.pc_source_fk_safe_payload(r.payload)
                        )
                    )
                );

            elsif r.target_table='pc_mobile_assets' then
                v_result:=public.pc_resolve_upsert_mobile_asset(
                    p_ingestion_job_id,
                    public.pc_schema_safe_payload(
                        'pc_mobile_assets',
                        public.pc_fk_safe_payload(
                            p_ingestion_job_id,
                            'pc_mobile_assets',
                            public.pc_source_fk_safe_payload(r.payload)
                        )
                    )
                );

            else
                v_result:=public.pc_resolve_upsert_event(
                    p_ingestion_job_id,
                    public.pc_schema_safe_payload(
                        'pc_events',
                        public.pc_fk_safe_payload(
                            p_ingestion_job_id,
                            'pc_events',
                            public.pc_source_fk_safe_payload(r.payload)
                        )
                    )
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
                    resolution_method=coalesce(lower(v_result->>'action'),'canonical_parent_upsert'),
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

    -- -----------------------------------------------------------------------
    -- GRAPH EDGES
    -- -----------------------------------------------------------------------
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
                    public.pc_schema_safe_payload('pc_relationships',r.payload)
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

    -- -----------------------------------------------------------------------
    -- DIRECT / OPTIONAL TABLES
    -- -----------------------------------------------------------------------
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
                    public.pc_schema_safe_payload(
                        'pc_transactions',
                        public.pc_fk_safe_payload(
                            p_ingestion_job_id,
                            'pc_transactions',
                            public.pc_source_fk_safe_payload(r.payload)
                        )
                    )
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

            elsif r.target_table='pc_transport_routes' then
                v_result:=public.pc_upsert_direct_from_payload(
                    p_ingestion_job_id,
                    'pc_transport_routes',
                    r.payload,
                    array['route_id']
                );

            elsif r.target_table='pc_chokepoints' then
                v_result:=public.pc_upsert_direct_from_payload(
                    p_ingestion_job_id,
                    'pc_chokepoints',
                    r.payload,
                    array['chokepoint_id']
                );

            elsif r.target_table='pc_market_instruments' then
                v_result:=public.pc_upsert_direct_from_payload(
                    p_ingestion_job_id,
                    'pc_market_instruments',
                    r.payload,
                    array['market_instrument_id']
                );

            elsif r.target_table='pc_trade_flows' then
                v_result:=public.pc_upsert_direct_from_payload(
                    p_ingestion_job_id,
                    'pc_trade_flows',
                    r.payload,
                    array['trade_flow_id']
                );

            elsif r.target_table='pc_supply_series' then
                v_result:=public.pc_upsert_direct_from_payload(
                    p_ingestion_job_id,
                    'pc_supply_series',
                    r.payload,
                    array['supply_series_id']
                );

            else
                v_result:=public.pc_upsert_direct_from_payload(
                    p_ingestion_job_id,
                    'pc_observations',
                    r.payload,
                    array['observation_id']
                );
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

        exception when foreign_key_violation then
            update public.pc_staged_records
            set
                resolution_status='BROKEN_REFERENCE',
                validation_status='reviewed',
                review_status='pending',
                resolution_method='DIRECT_FK_ERROR: '||sqlerrm
            where staged_record_id=r.staged_record_id;
            v_review:=v_review+1;

        when others then
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
                when v_review=0 and v_errors=0 then 'completed'
                else 'review'
            end,
        completed_at=
            case
                when v_review=0 and v_errors=0 then now()
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
            when v_review=0 and v_errors=0 then 'completed'
            else 'review'
        end
    );
end;
$$;


grant execute on function public.pc_schema_safe_payload(text,jsonb) to authenticated;
grant execute on function public.pc_object_type_for_table(text) to authenticated;
grant execute on function public.pc_fk_safe_payload(uuid,text,jsonb) to authenticated;
grant execute on function public.pc_upsert_direct_from_payload(uuid,text,jsonb,text[]) to authenticated;
grant execute on function public.pc_process_ingestion_job_v5(uuid) to authenticated;

commit;


-- ===========================================================================
-- EXPECTED CURRENT-JOB BEHAVIOR
-- ===========================================================================
-- Before 056:
--   Total        105
--   Applied       89
--   Review        16
--   Broken refs   10
--
-- Observed remaining classes:
--   pc_event_links       10  MISSING_EVENT_ENDPOINT
--   parent/event rows     2  PROCESS_ERROR invalid numeric value such as "true"
--   pc_transport_routes   4  DIRECT_UPSERT_ERROR / FK violation
--
-- After installing 056:
--
-- 1) Click "Retry unresolved rows in this package"
--    - the 2 numeric/type failures should normalize
--    - the 4 route FK failures should remap or safely preserve optional FK labels
--
-- 2) Click Retry a SECOND time if event links remain
--    - their parent events now exist, so the 10 MISSING_EVENT_ENDPOINT rows should apply
--
-- Target:
--   Total        105
--   Applied      105
--   Review         0
--   Broken refs     0
--
-- If anything remains after two retries, it should now be a genuine missing
-- mandatory endpoint/identity rather than a SQL type/FK plumbing error.
