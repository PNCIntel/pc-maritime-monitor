-- Power & Corridors SQL 033
-- Dependency auto-create engine
-- PostgreSQL / Supabase
-- Run AFTER 032_event_first_dependency_engine.sql
--
-- Goal:
--   Turn missing relationship/event-link endpoints into a database concern,
--   not an analyst/operator task.
--
-- Safe behavior:
--   * exact canonical match first
--   * alias match second
--   * conservative unique prefix/metadata-alias match third
--   * auto-create only when source provenance exists
--   * ambiguous references are NEVER auto-created
--   * created dependencies are provisional/medium quality and source-backed
--   * transport geography such as E11/highway/road corridor can be promoted
--     to a canonical asset when the relationship itself is transport-specific
--
-- This file intentionally leaves genuinely ambiguous records for review.

begin;

-- ---------------------------------------------------------------------------
-- 1. Source/provenance guard
-- ---------------------------------------------------------------------------
create or replace function pc_staged_record_has_provenance(p_staged_record_id uuid)
returns boolean
language plpgsql
stable
security definer
set search_path=public
as $$
declare
    s pc_staged_records%rowtype;
    v_sources jsonb;
begin
    select * into s from pc_staged_records where staged_record_id=p_staged_record_id;
    if not found then return false; end if;

    if nullif(s.source_id,'') is not null then
        return true;
    end if;

    if nullif(s.payload->>'source_url','') is not null then
        return true;
    end if;

    v_sources := coalesce(
        case when jsonb_typeof(s.payload->'metadata'->'research_sources')='array'
             then s.payload->'metadata'->'research_sources' end,
        case when jsonb_typeof(s.payload->'research_sources')='array'
             then s.payload->'research_sources' end,
        '[]'::jsonb
    );

    return jsonb_array_length(v_sources) > 0;
end;
$$;

-- ---------------------------------------------------------------------------
-- 2. Conservative type inference
-- ---------------------------------------------------------------------------
create or replace function pc_infer_entity_type(p_name text, p_payload jsonb default '{}'::jsonb)
returns text
language plpgsql
immutable
as $$
declare
    n text := lower(coalesce(p_name,''));
    hinted text := coalesce(nullif(p_payload->>'entity_type',''), nullif(p_payload->>'subtype',''));
begin
    if hinted is not null then return hinted; end if;

    if n ~ '(ministry|department of|government|authority|commission|agency|customs|coast guard|navy|army|air force)' then
        return 'Government entity';
    elsif n ~ '(university|institute|research centre|research center)' then
        return 'Research institution';
    else
        return 'Company';
    end if;
end;
$$;

create or replace function pc_infer_asset_type(
    p_name text,
    p_relationship_type text default null,
    p_payload jsonb default '{}'::jsonb
)
returns text
language plpgsql
immutable
as $$
declare
    n text := lower(coalesce(p_name,''));
    r text := lower(coalesce(p_relationship_type,''));
    hinted text := coalesce(nullif(p_payload->>'asset_type',''), nullif(p_payload->>'subtype',''));
begin
    if hinted is not null then return hinted; end if;

    if n ~ '(berth|quay)' then return 'Port terminal / berth'; end if;
    if n ~ '(container terminal|terminal)' then return 'Terminal'; end if;
    if n ~ '(port|harbour|harbor)' then return 'Port / harbour'; end if;
    if n ~ '(shipyard|drydock|dry dock)' then return 'Shipyard / repair hub'; end if;
    if n ~ '(warehouse|logistics park|distribution centre|distribution center)' then return 'Logistics facility'; end if;
    if n ~ '(refinery|smelter|plant|factory|facility|complex)' then return 'Industrial asset'; end if;
    if n ~ '(pipeline)' then return 'Pipeline'; end if;
    if n ~ '(airport|airfield)' then return 'Airport'; end if;
    if n ~ '(rail terminal|dry port|inland port)' then return 'Rail / inland terminal'; end if;
    if n ~ '(highway|motorway|road corridor)' or r like '%road%' then return 'Road corridor'; end if;
    if n ~ '(rail corridor|railway corridor)' or r like '%rail%' then return 'Rail corridor'; end if;
    if n ~ '(industrial zone|economic zone|free zone|kezad|kizad|icad)' then return 'Economic/free zone'; end if;
    return 'Infrastructure asset';
end;
$$;

create or replace function pc_infer_mobile_asset_type(p_name text, p_original_type text, p_payload jsonb default '{}'::jsonb)
returns text
language plpgsql
immutable
as $$
declare
    n text := lower(coalesce(p_name,''));
    t text := lower(coalesce(p_original_type,''));
    hinted text := coalesce(nullif(p_payload->>'asset_type',''), nullif(p_payload->>'subtype',''));
begin
    if hinted is not null then return hinted; end if;
    if t in ('aircraft','plane') or n ~ '(flight |aircraft|boeing|airbus)' then return 'Aircraft'; end if;
    if t in ('rolling_stock','train','locomotive') then return 'Rolling stock'; end if;
    return 'Vessel';
end;
$$;

-- ---------------------------------------------------------------------------
-- 3. Conservative existing-object finder
--    Exact canonical -> alias registry -> metadata aliases -> unique slash-prefix.
-- ---------------------------------------------------------------------------
create or replace function pc_find_existing_dependency(
    p_entity_type text,
    p_name text,
    p_direct_id text default null
)
returns text
language plpgsql
stable
security definer
set search_path=public
as $$
declare
    r record;
    v_id text;
    v_count integer := 0;
    v_prefix text;
    v_norm text;
begin
    if nullif(trim(coalesce(p_name,'')),'') is null
       and nullif(trim(coalesce(p_direct_id,'')),'') is null then
        return null;
    end if;

    select * into r
    from pc_resolve_reference(p_entity_type,p_direct_id,null,null,p_name);
    if r.endpoint_status='MATCHED' then return r.entity_id; end if;
    if r.endpoint_status='AMBIGUOUS' then return null; end if;

    -- Alias registry.
    select a.canonical_id into v_id
    from pc_identity_aliases a
    where a.canonical_type=p_entity_type
      and pc_normalize_name(a.alias_value)=pc_normalize_name(p_name)
    order by a.created_at desc
    limit 1;
    if v_id is not null then return v_id; end if;

    -- Metadata aliases from canonical records.
    if p_entity_type='entity' then
        select count(*),min(e.entity_id) into v_count,v_id
        from pc_entities e
        where exists (
            select 1
            from jsonb_array_elements_text(
                case when jsonb_typeof(e.metadata->'aliases')='array' then e.metadata->'aliases' else '[]'::jsonb end
            ) a(alias_name)
            where pc_normalize_name(a.alias_name)=pc_normalize_name(p_name)
        );
    elsif p_entity_type='asset' then
        select count(*),min(a.asset_id) into v_count,v_id
        from pc_assets a
        where exists (
            select 1
            from jsonb_array_elements_text(
                case when jsonb_typeof(a.metadata->'aliases')='array' then a.metadata->'aliases' else '[]'::jsonb end
            ) x(alias_name)
            where pc_normalize_name(x.alias_name)=pc_normalize_name(p_name)
        );
    elsif p_entity_type='mobile_asset' then
        select count(*),min(m.mobile_asset_id) into v_count,v_id
        from pc_mobile_assets m
        where exists (
            select 1
            from jsonb_array_elements_text(
                case when jsonb_typeof(m.metadata->'aliases')='array' then m.metadata->'aliases' else '[]'::jsonb end
            ) x(alias_name)
            where pc_normalize_name(x.alias_name)=pc_normalize_name(p_name)
        );
    end if;

    if v_count=1 then return v_id; end if;
    if v_count>1 then return null; end if;

    -- Conservative slash-prefix match. Useful for names such as
    -- "KEZAD Musaffah / ICAD" -> "KEZAD Musaffah / Industrial City of Abu Dhabi".
    if position('/' in coalesce(p_name,'')) > 0 then
        v_prefix := trim(split_part(p_name,'/',1));
        v_norm := pc_normalize_name(v_prefix);

        if p_entity_type='entity' then
            select count(*),min(entity_id) into v_count,v_id
            from pc_entities
            where pc_normalize_name(name) like v_norm || '%';
        elsif p_entity_type='asset' then
            select count(*),min(asset_id) into v_count,v_id
            from pc_assets
            where pc_normalize_name(name) like v_norm || '%';
        elsif p_entity_type='mobile_asset' then
            select count(*),min(mobile_asset_id) into v_count,v_id
            from pc_mobile_assets
            where pc_normalize_name(name) like v_norm || '%';
        end if;

        if v_count=1 then return v_id; end if;
    end if;

    return null;
end;
$$;

-- ---------------------------------------------------------------------------
-- 4. Auto-create source-backed provisional dependencies.
-- ---------------------------------------------------------------------------
create or replace function pc_autocreate_entity_dependency(
    p_name text,
    p_payload jsonb,
    p_ingestion_job_id uuid,
    p_source_id text default null,
    p_alias text default null
)
returns text
language plpgsql
security definer
set search_path=public
as $$
declare
    v_id text;
    v_type text;
    v_country text;
    v_existing text;
    v_meta jsonb;
begin
    v_existing := pc_find_existing_dependency('entity',p_name,null);
    if v_existing is not null then return v_existing; end if;

    v_id := 'ENTITY_' || upper(substr(md5(lower(trim(p_name))),1,16));
    v_type := pc_infer_entity_type(p_name,p_payload);
    v_country := coalesce(
        nullif(p_payload->>'hq_country',''),
        nullif(p_payload->>'country',''),
        nullif(p_payload->'metadata'->'research_attributes'->>'country','')
    );

    v_meta := coalesce(p_payload->'metadata','{}'::jsonb)
        || jsonb_build_object(
            'autocreated_dependency',true,
            'created_from_ingestion_job',p_ingestion_job_id::text,
            'dependency_source_payload',coalesce(p_payload,'{}'::jsonb) - 'metadata'
        );

    if nullif(p_alias,'') is not null and pc_normalize_name(p_alias) <> pc_normalize_name(p_name) then
        v_meta := v_meta || jsonb_build_object('aliases',jsonb_build_array(p_alias));
    end if;

    insert into pc_entities(
        entity_id,name,entity_type,hq_country,status,record_status,data_quality,source_id,as_of,metadata
    ) values (
        v_id,p_name,v_type,v_country,'Active','provisional','medium',p_source_id,current_date,v_meta
    ) on conflict (entity_id) do nothing;

    insert into pc_identity_aliases(
        alias_type,alias_value,canonical_type,canonical_id,ingestion_job_id,
        confidence,resolution_method,metadata
    ) values (
        'name',p_name,'entity',v_id,p_ingestion_job_id,0.90,'AUTO_CREATED_DEPENDENCY',
        jsonb_build_object('provisional',true)
    ) on conflict do nothing;

    if nullif(p_alias,'') is not null then
        insert into pc_identity_aliases(
            alias_type,alias_value,canonical_type,canonical_id,ingestion_job_id,
            confidence,resolution_method,metadata
        ) values (
            'name',p_alias,'entity',v_id,p_ingestion_job_id,0.90,'AUTO_CREATED_DEPENDENCY_ALIAS',
            jsonb_build_object('provisional',true)
        ) on conflict do nothing;
    end if;

    return v_id;
end;
$$;

create or replace function pc_autocreate_asset_dependency(
    p_name text,
    p_relationship_type text,
    p_payload jsonb,
    p_ingestion_job_id uuid,
    p_source_id text default null,
    p_alias text default null
)
returns text
language plpgsql
security definer
set search_path=public
as $$
declare
    v_id text;
    v_type text;
    v_country text;
    v_region text;
    v_existing text;
    v_meta jsonb;
begin
    v_existing := pc_find_existing_dependency('asset',p_name,null);
    if v_existing is not null then return v_existing; end if;

    v_type := pc_infer_asset_type(p_name,p_relationship_type,p_payload);
    v_country := coalesce(
        nullif(p_payload->>'country',''),
        nullif(p_payload->'metadata'->'research_attributes'->>'country','')
    );
    v_region := coalesce(
        nullif(p_payload->>'region_city',''),
        nullif(p_payload->>'location','')
    );
    v_id := 'ASSET_' || upper(substr(md5(lower(trim(p_name)) || '|' || lower(coalesce(v_country,'')) || '|' || lower(v_type)),1,16));

    v_meta := coalesce(p_payload->'metadata','{}'::jsonb)
        || jsonb_build_object(
            'autocreated_dependency',true,
            'created_from_ingestion_job',p_ingestion_job_id::text,
            'dependency_relationship_type',p_relationship_type,
            'dependency_source_payload',coalesce(p_payload,'{}'::jsonb) - 'metadata'
        );

    if nullif(p_alias,'') is not null and pc_normalize_name(p_alias) <> pc_normalize_name(p_name) then
        v_meta := v_meta || jsonb_build_object('aliases',jsonb_build_array(p_alias));
    end if;

    insert into pc_assets(
        asset_id,name,asset_type,subtype,country,region_city,status,record_status,metadata
    ) values (
        v_id,p_name,v_type,null,v_country,v_region,
        coalesce(nullif(p_payload->>'status',''),'Active'),
        'provisional',v_meta
    ) on conflict (asset_id) do nothing;

    insert into pc_identity_aliases(
        alias_type,alias_value,canonical_type,canonical_id,ingestion_job_id,
        confidence,resolution_method,metadata
    ) values (
        'name',p_name,'asset',v_id,p_ingestion_job_id,0.90,'AUTO_CREATED_DEPENDENCY',
        jsonb_build_object('provisional',true)
    ) on conflict do nothing;

    if nullif(p_alias,'') is not null then
        insert into pc_identity_aliases(
            alias_type,alias_value,canonical_type,canonical_id,ingestion_job_id,
            confidence,resolution_method,metadata
        ) values (
            'name',p_alias,'asset',v_id,p_ingestion_job_id,0.90,'AUTO_CREATED_DEPENDENCY_ALIAS',
            jsonb_build_object('provisional',true)
        ) on conflict do nothing;
    end if;

    return v_id;
end;
$$;

create or replace function pc_autocreate_mobile_asset_dependency(
    p_name text,
    p_original_type text,
    p_payload jsonb,
    p_ingestion_job_id uuid,
    p_source_id text default null,
    p_alias text default null
)
returns text
language plpgsql
security definer
set search_path=public
as $$
declare
    v_id text;
    v_type text;
    v_imo text;
    v_existing text;
    v_meta jsonb;
begin
    v_existing := pc_find_existing_dependency('mobile_asset',p_name,null);
    if v_existing is not null then return v_existing; end if;

    v_imo := coalesce(
        nullif(p_payload->>'imo',''),
        nullif(p_payload->'metadata'->>'imo',''),
        nullif(p_payload->'metadata'->'research_attributes'->>'imo','')
    );

    -- Do not invent a mobile asset from a vague name unless the endpoint type
    -- itself says vessel/ship/aircraft/rolling_stock or an IMO is present.
    if v_imo is null and lower(coalesce(p_original_type,'')) not in
       ('mobile_asset','vessel','ship','aircraft','rolling_stock') then
        return null;
    end if;

    v_type := pc_infer_mobile_asset_type(p_name,p_original_type,p_payload);
    v_id := 'MOBILE_' || upper(substr(md5(lower(trim(p_name)) || '|' || coalesce(v_imo,'') || '|' || lower(v_type)),1,16));

    v_meta := coalesce(p_payload->'metadata','{}'::jsonb)
        || jsonb_build_object(
            'autocreated_dependency',true,
            'created_from_ingestion_job',p_ingestion_job_id::text,
            'dependency_source_payload',coalesce(p_payload,'{}'::jsonb) - 'metadata'
        );

    if nullif(p_alias,'') is not null and pc_normalize_name(p_alias) <> pc_normalize_name(p_name) then
        v_meta := v_meta || jsonb_build_object('aliases',jsonb_build_array(p_alias));
    end if;

    insert into pc_mobile_assets(
        mobile_asset_id,name,asset_type,subtype,imo,status,record_status,metadata
    ) values (
        v_id,p_name,v_type,null,v_imo,
        coalesce(nullif(p_payload->>'status',''),'Active'),
        'provisional',v_meta
    ) on conflict (mobile_asset_id) do nothing;

    insert into pc_identity_aliases(
        alias_type,alias_value,canonical_type,canonical_id,ingestion_job_id,
        confidence,resolution_method,metadata
    ) values (
        'name',p_name,'mobile_asset',v_id,p_ingestion_job_id,0.90,'AUTO_CREATED_DEPENDENCY',
        jsonb_build_object('provisional',true)
    ) on conflict do nothing;

    return v_id;
end;
$$;

-- ---------------------------------------------------------------------------
-- 5. Apply NEW fixed/mobile assets that are already explicitly staged.
-- ---------------------------------------------------------------------------
create or replace function pc_apply_new_staged_assets(p_ingestion_job_id uuid)
returns jsonb
language plpgsql
security definer
set search_path=public
as $$
declare
    v_inserted integer := 0;
    v_closed integer := 0;
begin
    insert into pc_assets(
        asset_id,name,asset_type,subtype,country,region_city,status,record_status,metadata
    )
    select
        s.payload->>'asset_id',
        s.payload->>'name',
        s.payload->>'asset_type',
        nullif(s.payload->>'subtype',''),
        nullif(s.payload->>'country',''),
        nullif(s.payload->>'region_city',''),
        nullif(s.payload->>'status',''),
        coalesce(nullif(s.payload->>'record_status',''),'provisional'),
        coalesce(s.payload->'metadata','{}'::jsonb)
        || jsonb_build_object('ingestion_job_id',s.ingestion_job_id::text,'research_natural_key',s.natural_key)
    from pc_staged_records s
    where s.ingestion_job_id=p_ingestion_job_id
      and s.target_table='pc_assets'
      and s.resolution_status='NEW'
      and coalesce(s.review_status,'pending') in ('pending','approved','applied')
      and coalesce(s.payload->>'asset_id','') <> ''
      and coalesce(s.payload->>'name','') <> ''
      and coalesce(s.payload->>'asset_type','') <> ''
    on conflict (asset_id) do nothing;

    get diagnostics v_inserted=row_count;

    update pc_staged_records s
       set review_status='applied',validation_status='validated',
           resolved_entity_id=s.payload->>'asset_id',resolution_status='MATCHED',
           resolution_method='CANONICAL_ID'
     where s.ingestion_job_id=p_ingestion_job_id
       and s.target_table='pc_assets'
       and coalesce(s.payload->>'asset_id','') <> ''
       and exists(select 1 from pc_assets a where a.asset_id=s.payload->>'asset_id');

    get diagnostics v_closed=row_count;
    return jsonb_build_object('inserted',v_inserted,'staging_closed',v_closed);
end;
$$;

create or replace function pc_apply_new_staged_mobile_assets(p_ingestion_job_id uuid)
returns jsonb
language plpgsql
security definer
set search_path=public
as $$
declare
    v_inserted integer := 0;
    v_closed integer := 0;
begin
    insert into pc_mobile_assets(
        mobile_asset_id,name,asset_type,subtype,imo,status,record_status,metadata
    )
    select
        s.payload->>'mobile_asset_id',
        s.payload->>'name',
        s.payload->>'asset_type',
        nullif(s.payload->>'subtype',''),
        nullif(s.payload->>'imo',''),
        nullif(s.payload->>'status',''),
        coalesce(nullif(s.payload->>'record_status',''),'provisional'),
        coalesce(s.payload->'metadata','{}'::jsonb)
        || jsonb_build_object('ingestion_job_id',s.ingestion_job_id::text,'research_natural_key',s.natural_key)
    from pc_staged_records s
    where s.ingestion_job_id=p_ingestion_job_id
      and s.target_table='pc_mobile_assets'
      and s.resolution_status='NEW'
      and coalesce(s.review_status,'pending') in ('pending','approved','applied')
      and coalesce(s.payload->>'mobile_asset_id','') <> ''
      and coalesce(s.payload->>'name','') <> ''
      and coalesce(s.payload->>'asset_type','') <> ''
    on conflict (mobile_asset_id) do nothing;

    get diagnostics v_inserted=row_count;

    update pc_staged_records s
       set review_status='applied',validation_status='validated',
           resolved_entity_id=s.payload->>'mobile_asset_id',resolution_status='MATCHED',
           resolution_method='CANONICAL_ID'
     where s.ingestion_job_id=p_ingestion_job_id
       and s.target_table='pc_mobile_assets'
       and coalesce(s.payload->>'mobile_asset_id','') <> ''
       and exists(select 1 from pc_mobile_assets m where m.mobile_asset_id=s.payload->>'mobile_asset_id');

    get diagnostics v_closed=row_count;
    return jsonb_build_object('inserted',v_inserted,'staging_closed',v_closed);
end;
$$;

-- ---------------------------------------------------------------------------
-- 6. Auto-resolve/create missing relationship endpoints.
-- ---------------------------------------------------------------------------
create or replace function pc_autocreate_relationship_dependencies(p_ingestion_job_id uuid)
returns jsonb
language plpgsql
security definer
set search_path=public
as $$
declare
    s pc_staged_records%rowtype;
    p jsonb;
    v_source_type text;
    v_target_type text;
    v_source_original_type text;
    v_target_original_type text;
    v_source_name text;
    v_target_name text;
    v_rel text;
    v_source_id text;
    v_target_id text;
    v_has_source boolean;
    v_created integer := 0;
    v_reused integer := 0;
    v_skipped integer := 0;
    v_changed boolean;
begin
    for s in
        select *
        from pc_staged_records
        where ingestion_job_id=p_ingestion_job_id
          and target_table='pc_relationships'
          and coalesce(review_status,'pending') not in ('applied','rejected')
        order by created_at,staged_record_id
    loop
        p := coalesce(s.payload,'{}'::jsonb);
        v_source_original_type := coalesce(p->>'source_type',p->>'from_type');
        v_target_original_type := coalesce(p->>'target_type',p->>'to_type');
        v_source_type := pc_relationship_endpoint_type(v_source_original_type);
        v_target_type := pc_relationship_endpoint_type(v_target_original_type);
        v_source_name := coalesce(nullif(p->>'source_name',''),nullif(p->>'from_name',''));
        v_target_name := coalesce(nullif(p->>'target_name',''),nullif(p->>'to_name',''));
        v_rel := coalesce(nullif(p->>'relationship_type',''),nullif(p->>'relationship',''),'related_to');
        v_has_source := pc_staged_record_has_provenance(s.staged_record_id);
        v_changed := false;

        v_source_id := pc_find_existing_dependency(v_source_type,v_source_name,p->>'source_id');
        v_target_id := pc_find_existing_dependency(v_target_type,v_target_name,p->>'target_id');

        -- A transport geography used as a relationship endpoint is better represented
        -- as an asset/corridor in the canonical graph.
        if v_target_id is null and v_target_type='geography'
           and (lower(v_rel) like '%road%' or lower(v_rel) like '%rail%' or lower(v_target_name) ~ '(highway|motorway|road corridor|rail corridor)')
        then
            v_target_type := 'asset';
            p := jsonb_set(p,'{target_type}',to_jsonb('asset'::text),true);
        end if;
        if v_source_id is null and v_source_type='geography'
           and (lower(v_rel) like '%road%' or lower(v_rel) like '%rail%' or lower(v_source_name) ~ '(highway|motorway|road corridor|rail corridor)')
        then
            v_source_type := 'asset';
            p := jsonb_set(p,'{source_type}',to_jsonb('asset'::text),true);
        end if;

        -- Re-run after possible geography->asset promotion.
        if v_source_id is null then
            v_source_id := pc_find_existing_dependency(v_source_type,v_source_name,p->>'source_id');
        end if;
        if v_target_id is null then
            v_target_id := pc_find_existing_dependency(v_target_type,v_target_name,p->>'target_id');
        end if;

        if v_source_id is null and v_has_source and nullif(v_source_name,'') is not null then
            if v_source_type='entity' then
                v_source_id := pc_autocreate_entity_dependency(v_source_name,p,p_ingestion_job_id,s.source_id,v_source_name);
            elsif v_source_type='asset' then
                v_source_id := pc_autocreate_asset_dependency(v_source_name,v_rel,p,p_ingestion_job_id,s.source_id,v_source_name);
            elsif v_source_type='mobile_asset' then
                v_source_id := pc_autocreate_mobile_asset_dependency(v_source_name,v_source_original_type,p,p_ingestion_job_id,s.source_id,v_source_name);
            end if;
            if v_source_id is not null then v_created := v_created + 1; end if;
        elsif v_source_id is not null then
            v_reused := v_reused + 1;
        end if;

        if v_target_id is null and v_has_source and nullif(v_target_name,'') is not null then
            if v_target_type='entity' then
                v_target_id := pc_autocreate_entity_dependency(v_target_name,p,p_ingestion_job_id,s.source_id,v_target_name);
            elsif v_target_type='asset' then
                v_target_id := pc_autocreate_asset_dependency(v_target_name,v_rel,p,p_ingestion_job_id,s.source_id,v_target_name);
            elsif v_target_type='mobile_asset' then
                v_target_id := pc_autocreate_mobile_asset_dependency(v_target_name,v_target_original_type,p,p_ingestion_job_id,s.source_id,v_target_name);
            end if;
            if v_target_id is not null then v_created := v_created + 1; end if;
        elsif v_target_id is not null then
            v_reused := v_reused + 1;
        end if;

        if v_source_id is not null then
            p := jsonb_set(p,'{source_id}',to_jsonb(v_source_id),true);
            v_changed := true;
        end if;
        if v_target_id is not null then
            p := jsonb_set(p,'{target_id}',to_jsonb(v_target_id),true);
            v_changed := true;
        end if;

        if v_changed then
            update pc_staged_records
               set payload=p,
                   resolution_details=coalesce(resolution_details,'{}'::jsonb)
                       || jsonb_build_object(
                           'dependency_autocreate_pass',true,
                           'source_endpoint_id',v_source_id,
                           'target_endpoint_id',v_target_id
                       )
             where staged_record_id=s.staged_record_id;
        else
            v_skipped := v_skipped + 1;
        end if;
    end loop;

    if to_regprocedure('pc_process_generic_relationship_backlog(uuid)') is not null then
        perform pc_process_generic_relationship_backlog(p_ingestion_job_id);
    end if;

    return jsonb_build_object('created_or_attempted',v_created,'reused_endpoints',v_reused,'unchanged',v_skipped);
end;
$$;

-- ---------------------------------------------------------------------------
-- 7. Auto-create dependencies referenced by event-link records.
-- ---------------------------------------------------------------------------
create or replace function pc_autocreate_event_link_dependencies(p_ingestion_job_id uuid)
returns jsonb
language plpgsql
security definer
set search_path=public
as $$
declare
    s pc_staged_records%rowtype;
    p jsonb;
    v_event_id text;
    v_linked_type text;
    v_original_type text;
    v_name text;
    v_id text;
    v_name_item text;
    v_has_source boolean;
    v_created integer := 0;
    v_patched integer := 0;
begin
    for s in
        select *
        from pc_staged_records
        where ingestion_job_id=p_ingestion_job_id
          and target_table='pc_event_links'
          and coalesce(review_status,'pending') not in ('applied','rejected')
        order by created_at,staged_record_id
    loop
        p := coalesce(s.payload,'{}'::jsonb);
        v_has_source := pc_staged_record_has_provenance(s.staged_record_id);

        v_event_id := nullif(p->>'event_id','');
        if v_event_id is null and nullif(p->>'event_natural_key','') is not null then
            v_event_id := pc_resolve_alias(p->>'event_natural_key','event',p_ingestion_job_id);
        end if;
        if v_event_id is not null and exists(select 1 from pc_events where event_id=v_event_id) then
            p := jsonb_set(p,'{event_id}',to_jsonb(v_event_id),true);
            v_patched := v_patched + 1;
        end if;

        -- Aggregate linked_entities: create missing source-backed entities now;
        -- pc_expand_event_link_arrays() will create the individual links afterward.
        if jsonb_typeof(p->'linked_entities')='array' and v_has_source then
            for v_name_item in select jsonb_array_elements_text(p->'linked_entities')
            loop
                v_id := pc_find_existing_dependency('entity',v_name_item,null);
                if v_id is null then
                    v_id := pc_autocreate_entity_dependency(v_name_item,p,p_ingestion_job_id,s.source_id,v_name_item);
                    if v_id is not null then v_created := v_created + 1; end if;
                end if;
            end loop;
        else
            v_original_type := coalesce(p->>'linked_type','entity');
            v_linked_type := pc_linked_type_to_entity_type(v_original_type);
            v_name := coalesce(nullif(p->>'linked_name',''),nullif(p->>'name',''));
            v_id := pc_find_existing_dependency(v_linked_type,v_name,p->>'linked_id');

            if v_id is null and v_has_source and nullif(v_name,'') is not null then
                if v_linked_type='entity' then
                    v_id := pc_autocreate_entity_dependency(v_name,p,p_ingestion_job_id,s.source_id,v_name);
                elsif v_linked_type='asset' then
                    v_id := pc_autocreate_asset_dependency(v_name,coalesce(p->>'relationship','event_link'),p,p_ingestion_job_id,s.source_id,v_name);
                elsif v_linked_type='mobile_asset' then
                    v_id := pc_autocreate_mobile_asset_dependency(v_name,v_original_type,p,p_ingestion_job_id,s.source_id,v_name);
                end if;
                if v_id is not null then v_created := v_created + 1; end if;
            end if;

            if v_id is not null then
                p := jsonb_set(p,'{linked_id}',to_jsonb(v_id),true);
                v_patched := v_patched + 1;
            end if;
        end if;

        update pc_staged_records set payload=p where staged_record_id=s.staged_record_id;
    end loop;

    if to_regprocedure('pc_process_relationship_backlog(uuid)') is not null then
        perform pc_process_relationship_backlog(p_ingestion_job_id);
    end if;

    return jsonb_build_object('dependencies_created',v_created,'records_patched',v_patched);
end;
$$;

-- ---------------------------------------------------------------------------
-- 8. Normalize stale staging states after successful canonical application.
-- ---------------------------------------------------------------------------
create or replace function pc_normalize_applied_staging(p_ingestion_job_id uuid)
returns jsonb
language plpgsql
security definer
set search_path=public
as $$
declare
    v_identity integer := 0;
    v_domain integer := 0;
begin
    update pc_staged_records s
       set resolution_status='MATCHED',
           resolution_method=case
             when coalesce(resolution_method,'') in ('','NO_CANONICAL_MATCH','NO_ENTITY_METADATA') then 'CANONICAL_APPLY'
             else resolution_method end
     where s.ingestion_job_id=p_ingestion_job_id
       and s.review_status='applied'
       and s.validation_status='validated'
       and (
            (s.target_table='pc_entities' and exists(select 1 from pc_entities e where e.entity_id=coalesce(s.resolved_entity_id,s.payload->>'entity_id')))
         or (s.target_table='pc_assets' and exists(select 1 from pc_assets a where a.asset_id=coalesce(s.resolved_entity_id,s.payload->>'asset_id')))
         or (s.target_table='pc_mobile_assets' and exists(select 1 from pc_mobile_assets m where m.mobile_asset_id=coalesce(s.resolved_entity_id,s.payload->>'mobile_asset_id')))
         or (s.target_table='pc_events' and exists(select 1 from pc_events e where e.event_id=coalesce(s.resolved_entity_id,s.payload->>'event_id')))
       );
    get diagnostics v_identity=row_count;

    -- These rows were already applied by a domain-specific procedure or operator;
    -- stale INVALID/NEW labels should not keep them in the exception queue.
    update pc_staged_records
       set resolution_status='MATCHED',
           resolution_method=case
             when coalesce(resolution_method,'') in ('','NO_CANONICAL_MATCH','NO_ENTITY_METADATA') then 'DOMAIN_APPLY'
             else resolution_method end
     where ingestion_job_id=p_ingestion_job_id
       and review_status='applied'
       and validation_status='validated'
       and target_table in (
           'pc_observations','pc_trade_flows','pc_transactions','pc_transport_routes',
           'pc_energy_assets','pc_industrial_assets','pc_logistics_facilities','pc_chokepoints'
       )
       and resolution_status in ('NEW','INVALID','UNRESOLVED');
    get diagnostics v_domain=row_count;

    return jsonb_build_object('identity_rows_normalized',v_identity,'domain_rows_normalized',v_domain);
end;
$$;

-- ---------------------------------------------------------------------------
-- 9. Compact operator exception view
-- ---------------------------------------------------------------------------
drop view if exists pc_v_ingestion_operator_exceptions;
create view pc_v_ingestion_operator_exceptions as
select
    s.staged_record_id,
    s.ingestion_job_id,
    s.target_table,
    s.natural_key,
    s.resolution_status,
    s.review_status,
    s.validation_status,
    s.resolution_method,
    case
      when s.resolution_status='AMBIGUOUS' then 'TRUE_AMBIGUITY'
      when s.resolution_status='PARTIAL' then 'MISSING_ENDPOINT'
      when s.resolution_status='BROKEN_REFERENCE' then 'BROKEN_REFERENCE'
      when s.resolution_status='INVALID' then 'UNSUPPORTED_MAPPING'
      when s.resolution_status in ('NEW','UNRESOLVED') and coalesce(s.review_status,'pending') <> 'applied' then 'PENDING_CANONICAL'
      when s.review_status='approved' then 'APPROVED_NOT_APPLIED'
      else 'REVIEW'
    end as exception_type,
    case
      when s.resolution_status='AMBIGUOUS' then 'Choose the intended canonical record; do not auto-create.'
      when s.resolution_status='PARTIAL' then 'Run dependency auto-create; review only if the missing endpoint is still unresolved.'
      when s.resolution_status='BROKEN_REFERENCE' then 'Repair the referenced event/object or source structure.'
      when s.resolution_status='INVALID' then 'Use a domain-specific apply handler or correct the target mapping.'
      when s.review_status='approved' then 'Apply the approved record.'
      else 'Review record structure and provenance.'
    end as suggested_action,
    s.payload,
    s.created_at
from pc_staged_records s
where coalesce(s.review_status,'pending') <> 'applied'
   or s.resolution_status in ('PARTIAL','AMBIGUOUS','BROKEN_REFERENCE','INVALID','UNRESOLVED');

-- ---------------------------------------------------------------------------
-- 10. V2 one-click reconcile orchestration
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
    -- Existing normalization/candidate prep.
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

    -- Explicitly staged canonical dependencies first.
    v_part := pc_apply_new_staged_entities(p_ingestion_job_id);
    v_result := v_result || jsonb_build_object('entities',v_part);

    v_part := pc_apply_new_staged_assets(p_ingestion_job_id);
    v_result := v_result || jsonb_build_object('assets',v_part);

    v_part := pc_apply_new_staged_mobile_assets(p_ingestion_job_id);
    v_result := v_result || jsonb_build_object('mobile_assets',v_part);

    v_part := pc_apply_new_staged_events(p_ingestion_job_id);
    v_result := v_result || jsonb_build_object('events',v_part);

    v_part := pc_register_job_aliases(p_ingestion_job_id);
    v_result := v_result || jsonb_build_object('aliases',v_part);

    -- Create missing source-backed dependencies referenced only by relationships.
    v_part := pc_autocreate_relationship_dependencies(p_ingestion_job_id);
    v_result := v_result || jsonb_build_object('relationship_dependencies',v_part);

    v_part := pc_autocreate_event_link_dependencies(p_ingestion_job_id);
    v_result := v_result || jsonb_build_object('event_link_dependencies',v_part);

    -- Resolve again after auto-create.
    if to_regprocedure('pc_process_generic_relationship_backlog(uuid)') is not null then
        execute 'select pc_process_generic_relationship_backlog($1)' into v_part using p_ingestion_job_id;
        v_result := v_result || jsonb_build_object('generic_relationship_resolution',v_part);
    end if;
    if to_regprocedure('pc_process_relationship_backlog(uuid)') is not null then
        execute 'select pc_process_relationship_backlog($1)' into v_part using p_ingestion_job_id;
        v_result := v_result || jsonb_build_object('event_link_resolution',v_part);
    end if;

    -- Expand array event links after referenced entities exist.
    v_part := pc_expand_event_link_arrays(p_ingestion_job_id);
    v_result := v_result || jsonb_build_object('event_link_arrays',v_part);

    -- Apply READY relationships and event links.
    if to_regprocedure('pc_apply_ready_event_relationships(uuid)') is not null then
        execute 'select pc_apply_ready_event_relationships($1)' into v_part using p_ingestion_job_id;
        v_result := v_result || jsonb_build_object('event_links_applied',v_part);
    end if;
    if to_regprocedure('pc_apply_ready_generic_relationships(uuid)') is not null then
        execute 'select pc_apply_ready_generic_relationships($1)' into v_part using p_ingestion_job_id;
        v_result := v_result || jsonb_build_object('relationships_applied',v_part);
    end if;

    v_part := pc_normalize_applied_staging(p_ingestion_job_id);
    v_result := v_result || jsonb_build_object('staging_normalized',v_part);

    select count(*) into v_remaining
    from pc_v_ingestion_operator_exceptions
    where ingestion_job_id=p_ingestion_job_id;

    v_result := v_result || jsonb_build_object('remaining_operator_exceptions',v_remaining);
    return v_result;
end;
$$;

comment on function pc_reconcile_ingestion_job_v2(uuid) is
'Operator-light reconciliation: apply explicit dependencies, auto-create source-backed missing relationship/event-link endpoints, resolve/apply safe links, normalize stale staging states, and leave only genuine exceptions.';

commit;
