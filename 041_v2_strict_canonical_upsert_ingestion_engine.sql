-- Power & Corridors
-- 041_v2_strict_canonical_upsert_ingestion_engine.sql
-- Purpose: replace reconciliation choreography with a simple canonical upsert engine.
-- Core model: resolve/upsert objects first, then relationships/event links, then QA.
-- Safe to run repeatedly. Does not delete canonical data.
-- Requires 043 for alias-aware matching and naming policy.

begin;

do $$
begin
    if to_regclass('public.pc_identity_aliases_v2') is null then
        raise exception '043_canonical_identity_naming_audit.sql must be installed before 041 v2';
    end if;
    if to_regprocedure('public.pc_object_exists(text,text)') is null then
        raise exception '044_canonical_merge_framework.sql must be installed before 041 v2';
    end if;
end $$;

-- ---------------------------------------------------------------------------
-- 1. Helpers
-- ---------------------------------------------------------------------------
create or replace function public.pc_norm_text(p_text text)
returns text
language sql
immutable
as $$
    select nullif(regexp_replace(lower(trim(coalesce(p_text,''))), '[^a-z0-9]+', ' ', 'g'), '');
$$;


create or replace function public.pc_alias_match_count(
    p_object_type text,
    p_name text
)
returns integer
language sql
stable
as $$
    select count(distinct canonical_id)::integer
    from public.pc_identity_aliases_v2
    where object_type=lower(p_object_type)
      and normalized_alias=public.pc_norm_identity_text(p_name);
$$;

create or replace function public.pc_alias_unique_id(
    p_object_type text,
    p_name text
)
returns text
language sql
stable
as $$
    select min(canonical_id)
    from public.pc_identity_aliases_v2
    where object_type=lower(p_object_type)
      and normalized_alias=public.pc_norm_identity_text(p_name)
    having count(distinct canonical_id)=1;
$$;

create or replace function public.pc_minimum_identity_ok(
    p_object_type text,
    p_payload jsonb
)
returns boolean
language plpgsql
immutable
as $$
declare
    t text:=lower(p_object_type);
begin
    if t='entity' then
        return nullif(trim(p_payload->>'name'),'') is not null
           and (
                nullif(trim(p_payload->>'country'),'') is not null
                or nullif(trim(p_payload->>'entity_type'),'') is not null
                or nullif(trim(p_payload->>'source_url'),'') is not null
                or jsonb_typeof(p_payload->'research_sources')='array'
           );
    elsif t='asset' then
        return nullif(trim(p_payload->>'name'),'') is not null
           and nullif(trim(p_payload->>'asset_type'),'') is not null
           and (
                nullif(trim(p_payload->>'country'),'') is not null
                or nullif(trim(p_payload->>'region_city'),'') is not null
                or nullif(trim(p_payload->>'latitude'),'') is not null
                or nullif(trim(p_payload->>'source_url'),'') is not null
           );
    elsif t in ('mobile_asset','vessel') then
        return nullif(trim(p_payload->>'name'),'') is not null
           and (
                nullif(trim(p_payload->>'imo'),'') is not null
                or nullif(trim(p_payload->>'mmsi'),'') is not null
                or (
                    nullif(trim(p_payload->>'flag'),'') is not null
                    and nullif(trim(p_payload->>'asset_type'),'') is not null
                )
           );
    elsif t='event' then
        return coalesce(nullif(trim(p_payload->>'title'),''),nullif(trim(p_payload->>'name'),'')) is not null
           and (
                nullif(trim(p_payload->>'start_date'),'') is not null
                or nullif(trim(p_payload->>'event_date'),'') is not null
           );
    end if;
    return false;
end;
$$;

create or replace function public.pc_merge_metadata(p_old jsonb, p_new jsonb)
returns jsonb
language plpgsql
immutable
as $$
declare
    v_old jsonb := coalesce(p_old,'{}'::jsonb);
    v_new jsonb := coalesce(p_new,'{}'::jsonb);
    v_sources jsonb := '[]'::jsonb;
begin
    select coalesce(jsonb_agg(to_jsonb(x) order by x),'[]'::jsonb)
      into v_sources
      from (
        select distinct value as x
        from (
            select value
              from jsonb_array_elements_text(
                    case when jsonb_typeof(v_old->'research_sources')='array'
                         then v_old->'research_sources' else '[]'::jsonb end)
            union all
            select value
              from jsonb_array_elements_text(
                    case when jsonb_typeof(v_new->'research_sources')='array'
                         then v_new->'research_sources' else '[]'::jsonb end)
        ) s
        where nullif(trim(value),'') is not null
      ) d;

    v_old := v_old || v_new;
    if jsonb_array_length(v_sources) > 0 then
        v_old := jsonb_set(v_old,'{research_sources}',v_sources,true);
    end if;
    return v_old;
end;
$$;

-- Source/workbook IDs are not canonical IDs. Keep an explicit map per ingestion job.
create table if not exists public.pc_ingestion_key_map (
    ingestion_job_id uuid not null,
    object_type text not null,
    source_key text not null,
    canonical_id text not null,
    resolution_method text not null default 'upsert',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    primary key (ingestion_job_id, object_type, source_key)
);
create index if not exists idx_pc_ingestion_key_map_canonical
    on public.pc_ingestion_key_map(ingestion_job_id, object_type, canonical_id);

create or replace function public.pc_map_ingestion_key(
    p_job uuid, p_type text, p_source_key text, p_canonical_id text, p_method text default 'upsert'
) returns void
language plpgsql
security definer
set search_path=public
as $$
begin
    if p_job is null or nullif(trim(p_source_key),'') is null or nullif(trim(p_canonical_id),'') is null then
        return;
    end if;
    insert into public.pc_ingestion_key_map(ingestion_job_id,object_type,source_key,canonical_id,resolution_method)
    values (p_job,lower(p_type),p_source_key,p_canonical_id,coalesce(p_method,'upsert'))
    on conflict (ingestion_job_id,object_type,source_key)
    do update set canonical_id=excluded.canonical_id,
                  resolution_method=excluded.resolution_method,
                  updated_at=now();
end;
$$;

create or replace function public.pc_mapped_id(p_job uuid,p_type text,p_source_key text)
returns text
language sql
stable
as $$
    select coalesce(
        (select canonical_id from public.pc_ingestion_key_map
          where ingestion_job_id=p_job and object_type=lower(p_type) and source_key=p_source_key),
        p_source_key
    );
$$;

-- Generic schema-safe upsert. Only payload keys that are actual writable columns are used.
-- Existing non-null data is preserved when incoming values are null. metadata is merged.
create or replace function public.pc_upsert_json(
    p_table text,
    p_payload jsonb,
    p_conflict_cols text[]
) returns jsonb
language plpgsql
security definer
set search_path=public
as $$
declare
    v_cols text[];
    v_col_list text;
    v_select_list text;
    v_conflict text;
    v_update text;
    v_sql text;
    v_result jsonb;
    v_schema text := 'public';
    v_name text := replace(p_table,'public.','');
begin
    if v_name !~ '^pc_[a-z0-9_]+$' then
        raise exception 'Unsafe table name: %', p_table;
    end if;

    select array_agg(a.attname order by a.attnum)
      into v_cols
      from pg_attribute a
      join pg_class c on c.oid=a.attrelid
      join pg_namespace n on n.oid=c.relnamespace
     where n.nspname=v_schema
       and c.relname=v_name
       and a.attnum>0 and not a.attisdropped
       and a.attgenerated=''
       and p_payload ? a.attname;

    if coalesce(array_length(v_cols,1),0)=0 then
        raise exception 'No writable payload columns for %', v_name;
    end if;

    if exists (
        select 1 from unnest(p_conflict_cols) x
        where not (x=any(v_cols)) or nullif(p_payload->>x,'') is null
    ) then
        raise exception 'Missing conflict key for %: %', v_name, p_conflict_cols;
    end if;

    select string_agg(format('%I',x),',') into v_col_list from unnest(v_cols) x;
    select string_agg(format('(r).%I',x),',') into v_select_list from unnest(v_cols) x;
    select string_agg(format('%I',x),',') into v_conflict from unnest(p_conflict_cols) x;

    select string_agg(
        case when x='metadata' then
            format('%I = public.pc_merge_metadata(%I.%I, excluded.%I)',x,v_name,x,x)
        else
            format('%I = coalesce(excluded.%I, %I.%I)',x,x,v_name,x)
        end, ',')
      into v_update
      from unnest(v_cols) x
     where not (x=any(p_conflict_cols));

    v_sql := format(
        'with src as (select jsonb_populate_record(null::public.%I,$1) r), '
        'u as (insert into public.%I (%s) select %s from src '
        'on conflict (%s) do update set %s returning to_jsonb(%I.*)) '
        'select coalesce((select * from u),''{}''::jsonb)',
        v_name,v_name,v_col_list,v_select_list,v_conflict,
        coalesce(nullif(v_update,''),' '),v_name
    );

    execute v_sql using p_payload into v_result;
    return v_result;
end;
$$;

-- ---------------------------------------------------------------------------
-- 2. Canonical resolvers / upserts
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
    v_payload jsonb := p_payload;
    v_action text;
begin
    if not public.pc_minimum_identity_ok('entity',p_payload) then
        return jsonb_build_object('status','REVIEW','reason','INSUFFICIENT_ENTITY_IDENTITY');
    end if;

    -- Source/workbook IDs are hints only; they are not trusted as canonical IDs.
    if v_source_id is not null and exists(select 1 from pc_entities where entity_id::text=v_source_id) then
        v_id:=v_source_id; v_action:='UPSERT_ID';
    else
        -- Alias first.
        v_count:=public.pc_alias_match_count('entity',p_payload->>'name');
        if v_count=1 then
            v_id:=public.pc_alias_unique_id('entity',p_payload->>'name');
            v_action:='UPSERT_ALIAS';
        elsif v_count>1 then
            return jsonb_build_object('status','REVIEW','reason','AMBIGUOUS_ENTITY_ALIAS','candidate_count',v_count);
        end if;

        -- Then exact normalized canonical name + geography/type context.
        if v_id is null then
            select count(*), min(entity_id::text)
              into v_count,v_id
              from pc_entities
             where public.pc_norm_identity_text(name)=public.pc_norm_identity_text(p_payload->>'name')
               and (
                    nullif(p_payload->>'country','') is null
                    or public.pc_norm_identity_text(country::text)=public.pc_norm_identity_text(p_payload->>'country')
               )
               and (
                    nullif(p_payload->>'entity_type','') is null
                    or public.pc_norm_identity_text(entity_type::text)=public.pc_norm_identity_text(p_payload->>'entity_type')
               );
            if v_count>1 then
                return jsonb_build_object('status','REVIEW','reason','AMBIGUOUS_ENTITY','candidate_count',v_count);
            elsif v_count=1 then
                v_action:='UPSERT_NAME';
            else
                v_id:=null;
            end if;
        end if;

        if v_id is null then
            -- Create a NEW canonical ID generated by the database. Do not reuse arbitrary workbook IDs.
            v_id:='ENTITY_'||upper(substr(md5(
                coalesce(public.pc_norm_identity_text(p_payload->>'name'),'')||'|'||
                coalesce(public.pc_norm_identity_text(p_payload->>'country'),'')||'|'||
                coalesce(public.pc_norm_identity_text(p_payload->>'entity_type'),'')
            ),1,20));
            v_action:='CREATE';
        end if;
    end if;

    v_payload:=jsonb_set(v_payload,'{entity_id}',to_jsonb(v_id),true);
    perform pc_upsert_json('pc_entities',v_payload,array['entity_id']);
    perform pc_map_ingestion_key(p_job,'entity',coalesce(v_source_id,v_id),v_id,lower(v_action));

    insert into pc_identity_aliases_v2(object_type,canonical_id,alias_name,alias_type)
    values('entity',v_id,p_payload->>'name',case when v_action='CREATE' then 'official' else 'source' end)
    on conflict (object_type,canonical_id,normalized_alias) do nothing;

    return jsonb_build_object('status','OK','canonical_id',v_id,'action',v_action);
end;
$$;

create or replace function public.pc_resolve_upsert_asset(p_job uuid,p_payload jsonb)
returns jsonb
language plpgsql
security definer
set search_path=public
as $$
declare
    v_source_id text := nullif(p_payload->>'asset_id','');
    v_id text; v_count integer; v_payload jsonb:=p_payload; v_action text;
begin
    if not public.pc_minimum_identity_ok('asset',p_payload) then
        return jsonb_build_object('status','REVIEW','reason','INSUFFICIENT_ASSET_IDENTITY');
    end if;

    if v_source_id is not null and exists(select 1 from pc_assets where asset_id::text=v_source_id) then
        v_id:=v_source_id; v_action:='UPSERT_ID';
    else
        v_count:=public.pc_alias_match_count('asset',p_payload->>'name');
        if v_count=1 then
            v_id:=public.pc_alias_unique_id('asset',p_payload->>'name');
            v_action:='UPSERT_ALIAS';
        elsif v_count>1 then
            return jsonb_build_object('status','REVIEW','reason','AMBIGUOUS_ASSET_ALIAS','candidate_count',v_count);
        end if;

        if v_id is null then
            select count(*),min(asset_id::text) into v_count,v_id
              from pc_assets
             where public.pc_norm_identity_text(name)=public.pc_norm_identity_text(p_payload->>'name')
               and (
                    nullif(p_payload->>'country','') is null
                    or public.pc_norm_identity_text(country::text)=public.pc_norm_identity_text(p_payload->>'country')
               )
               and (
                    nullif(p_payload->>'region_city','') is null
                    or public.pc_norm_identity_text(region_city::text)=public.pc_norm_identity_text(p_payload->>'region_city')
               )
               and public.pc_norm_identity_text(asset_type::text)=public.pc_norm_identity_text(p_payload->>'asset_type');
            if v_count>1 then
                return jsonb_build_object('status','REVIEW','reason','AMBIGUOUS_ASSET','candidate_count',v_count);
            elsif v_count=1 then
                v_action:='UPSERT_NAME';
            else
                v_id:=null;
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
        v_payload:=jsonb_set(v_payload,'{owner_entity_id}',to_jsonb(pc_mapped_id(p_job,'entity',v_payload->>'owner_entity_id')),true);
    end if;
    if nullif(v_payload->>'operator_entity_id','') is not null then
        v_payload:=jsonb_set(v_payload,'{operator_entity_id}',to_jsonb(pc_mapped_id(p_job,'entity',v_payload->>'operator_entity_id')),true);
    end if;

    v_payload:=jsonb_set(v_payload,'{asset_id}',to_jsonb(v_id),true);
    perform pc_upsert_json('pc_assets',v_payload,array['asset_id']);
    perform pc_map_ingestion_key(p_job,'asset',coalesce(v_source_id,v_id),v_id,lower(v_action));

    insert into pc_identity_aliases_v2(object_type,canonical_id,alias_name,alias_type)
    values('asset',v_id,p_payload->>'name',case when v_action='CREATE' then 'official' else 'source' end)
    on conflict (object_type,canonical_id,normalized_alias) do nothing;

    return jsonb_build_object('status','OK','canonical_id',v_id,'action',v_action);
end;
$$;

create or replace function public.pc_resolve_upsert_mobile_asset(p_job uuid,p_payload jsonb)
returns jsonb
language plpgsql
security definer
set search_path=public
as $$
declare
    v_source_id text:=nullif(p_payload->>'mobile_asset_id','');
    v_id text; v_count integer; v_payload jsonb:=p_payload; v_action text;
    v_display_name text;
begin
    if not public.pc_minimum_identity_ok('mobile_asset',p_payload) then
        return jsonb_build_object('status','REVIEW','reason','INSUFFICIENT_MOBILE_ASSET_IDENTITY');
    end if;

    if v_source_id is not null and exists(select 1 from pc_mobile_assets where mobile_asset_id::text=v_source_id) then
        v_id:=v_source_id; v_action:='UPSERT_ID';
    elsif nullif(p_payload->>'imo','') is not null then
        select count(*),min(mobile_asset_id::text)
          into v_count,v_id
          from pc_mobile_assets
         where regexp_replace(coalesce(imo::text,''),'[^0-9]','','g')
             = regexp_replace(coalesce(p_payload->>'imo',''),'[^0-9]','','g');
        if v_count>1 then
            return jsonb_build_object('status','REVIEW','reason','DUPLICATE_CANONICAL_IMO','candidate_count',v_count);
        elsif v_count=1 then
            v_action:='UPSERT_IMO';
        end if;
    end if;

    if v_id is null and nullif(p_payload->>'mmsi','') is not null then
        select count(*),min(mobile_asset_id::text)
          into v_count,v_id
          from pc_mobile_assets
         where regexp_replace(coalesce(mmsi::text,''),'[^0-9]','','g')
             = regexp_replace(coalesce(p_payload->>'mmsi',''),'[^0-9]','','g');
        if v_count>1 then
            return jsonb_build_object('status','REVIEW','reason','DUPLICATE_CANONICAL_MMSI','candidate_count',v_count);
        elsif v_count=1 then
            v_action:='UPSERT_MMSI';
        end if;
    end if;

    if v_id is null then
        v_count:=public.pc_alias_match_count('mobile_asset',p_payload->>'name');
        if v_count=1 then
            v_id:=public.pc_alias_unique_id('mobile_asset',p_payload->>'name');
            v_action:='UPSERT_ALIAS';
        elsif v_count>1 then
            return jsonb_build_object('status','REVIEW','reason','AMBIGUOUS_MOBILE_ASSET_ALIAS','candidate_count',v_count);
        end if;
    end if;

    if v_id is null then
        select count(*),min(mobile_asset_id::text)
          into v_count,v_id
          from pc_mobile_assets
         where public.pc_norm_identity_text(name)=public.pc_norm_identity_text(p_payload->>'name')
           and (
                nullif(p_payload->>'flag','') is null
                or public.pc_norm_identity_text(flag::text)=public.pc_norm_identity_text(p_payload->>'flag')
           )
           and (
                nullif(p_payload->>'asset_type','') is null
                or public.pc_norm_identity_text(asset_type::text)=public.pc_norm_identity_text(p_payload->>'asset_type')
           );
        if v_count>1 then
            return jsonb_build_object('status','REVIEW','reason','AMBIGUOUS_MOBILE_ASSET','candidate_count',v_count);
        elsif v_count=1 then
            v_action:='UPSERT_NAME';
        else
            v_id:=null;
        end if;
    end if;

    if v_id is null then
        v_id:='MOBILE_'||upper(substr(md5(
            coalesce(regexp_replace(p_payload->>'imo','[^0-9]','','g'),'')||'|'||
            coalesce(public.pc_norm_identity_text(p_payload->>'name'),'')||'|'||
            coalesce(public.pc_norm_identity_text(p_payload->>'flag'),'')||'|'||
            coalesce(public.pc_norm_identity_text(p_payload->>'asset_type'),'')
        ),1,20));
        v_action:='CREATE';
    end if;

    v_display_name:=public.pc_apply_display_name_policy(
        'mobile_asset',
        p_payload->>'name',
        p_payload->>'asset_type',
        p_payload->>'subtype'
    );
    if v_display_name is not null then
        v_payload:=jsonb_set(v_payload,'{name}',to_jsonb(v_display_name),true);
    end if;

    foreach v_source_id in array array['owner_entity_id','operator_entity_id','manager_entity_id'] loop
        if nullif(v_payload->>v_source_id,'') is not null then
            v_payload:=jsonb_set(v_payload,array[v_source_id],to_jsonb(pc_mapped_id(p_job,'entity',v_payload->>v_source_id)),true);
        end if;
    end loop;

    v_payload:=jsonb_set(v_payload,'{mobile_asset_id}',to_jsonb(v_id),true);
    perform pc_upsert_json('pc_mobile_assets',v_payload,array['mobile_asset_id']);
    perform pc_map_ingestion_key(p_job,'mobile_asset',coalesce(nullif(p_payload->>'mobile_asset_id',''),v_id),v_id,lower(v_action));
    perform pc_map_ingestion_key(p_job,'vessel',coalesce(nullif(p_payload->>'mobile_asset_id',''),v_id),v_id,lower(v_action));

    insert into pc_identity_aliases_v2(object_type,canonical_id,alias_name,alias_type)
    values('mobile_asset',v_id,p_payload->>'name',case when v_action='CREATE' then 'official' else 'source' end)
    on conflict (object_type,canonical_id,normalized_alias) do nothing;

    return jsonb_build_object('status','OK','canonical_id',v_id,'action',v_action);
end;
$$;

create or replace function public.pc_resolve_upsert_event(p_job uuid,p_payload jsonb)
returns jsonb
language plpgsql
security definer
set search_path=public
as $$
declare
    v_source_id text:=nullif(p_payload->>'event_id','');
    v_id text; v_count integer; v_payload jsonb:=p_payload; v_action text;
begin
    if v_source_id is not null and exists(select 1 from pc_events where event_id::text=v_source_id) then
        v_id:=v_source_id; v_action:='UPSERT';
    else
        select count(*),min(event_id::text) into v_count,v_id
          from pc_events
         where pc_norm_text(title)=pc_norm_text(p_payload->>'title')
           and (
             nullif(p_payload->>'start_date','') is null
             or start_date::date = (p_payload->>'start_date')::date
           );
        if v_count>1 then return jsonb_build_object('status','REVIEW','reason','AMBIGUOUS_EVENT','candidate_count',v_count); end if;
        if v_count=1 then v_action:='UPSERT';
        else
            v_id:=coalesce(v_source_id,'EVENT_'||upper(substr(md5(coalesce(p_payload->>'title','')||'|'||coalesce(p_payload->>'start_date','')||'|'||coalesce(p_payload->>'event_type','')),1,20)));
            v_action:='CREATE';
        end if;
    end if;

    v_payload:=jsonb_set(v_payload,'{event_id}',to_jsonb(v_id),true);
    perform pc_upsert_json('pc_events',v_payload,array['event_id']);
    perform pc_map_ingestion_key(p_job,'event',coalesce(v_source_id,v_id),v_id,lower(v_action));
    return jsonb_build_object('status','OK','canonical_id',v_id,'action',v_action);
end;
$$;

-- ---------------------------------------------------------------------------
-- 3. Edge writers. Endpoints are always canonical before writing the edge.
-- ---------------------------------------------------------------------------
create or replace function public.pc_upsert_relationship_from_payload(p_job uuid,p_payload jsonb)
returns jsonb
language plpgsql
security definer
set search_path=public
as $$
declare
    v jsonb:=p_payload;
    v_source_type text:=lower(v->>'source_type');
    v_target_type text:=lower(v->>'target_type');
    v_source text; v_target text;
begin
    v_source:=pc_mapped_id(p_job,v_source_type,v->>'source_id');
    v_target:=pc_mapped_id(p_job,v_target_type,v->>'target_id');

    if not pc_object_exists(v_source_type,v_source) then
        return jsonb_build_object('status','REVIEW','reason','MISSING_SOURCE_ENDPOINT','source_type',v_source_type,'source_id',v_source);
    end if;
    if not pc_object_exists(v_target_type,v_target) then
        return jsonb_build_object('status','REVIEW','reason','MISSING_TARGET_ENDPOINT','target_type',v_target_type,'target_id',v_target);
    end if;

    v:=jsonb_set(v,'{source_id}',to_jsonb(v_source),true);
    v:=jsonb_set(v,'{target_id}',to_jsonb(v_target),true);
    perform pc_upsert_json('pc_relationships',v,array['relationship_id']);
    return jsonb_build_object('status','OK','relationship_id',v->>'relationship_id','source_id',v_source,'target_id',v_target);
end;
$$;

create or replace function public.pc_upsert_event_link_from_payload(p_job uuid,p_payload jsonb)
returns jsonb
language plpgsql
security definer
set search_path=public
as $$
declare
    v jsonb:=p_payload;
    v_event text; v_linked text; v_type text:=lower(v->>'linked_type');
begin
    v_event:=pc_mapped_id(p_job,'event',v->>'event_id');
    v_linked:=pc_mapped_id(p_job,v_type,v->>'linked_id');

    if not pc_object_exists('event',v_event) then
        return jsonb_build_object('status','REVIEW','reason','MISSING_EVENT_ENDPOINT','event_id',v_event);
    end if;
    if not pc_object_exists(v_type,v_linked) then
        return jsonb_build_object('status','REVIEW','reason','MISSING_LINKED_ENDPOINT','linked_type',v_type,'linked_id',v_linked);
    end if;

    v:=jsonb_set(v,'{event_id}',to_jsonb(v_event),true);
    v:=jsonb_set(v,'{linked_id}',to_jsonb(v_linked),true);
    perform pc_upsert_json('pc_event_links',v,array['event_link_id']);
    return jsonb_build_object('status','OK','event_link_id',v->>'event_link_id','event_id',v_event,'linked_id',v_linked);
end;
$$;

-- ---------------------------------------------------------------------------
-- 4. One job processor: objects -> edges -> direct upserts -> QA summary.
--    Genuine ambiguity is the only normal reason to remain in review.
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
    v_processed int:=0; v_created int:=0; v_upserted int:=0; v_review int:=0; v_errors int:=0;
    v_edges int:=0;
begin
    -- OBJECTS FIRST
    for r in
        select * from pc_staged_records
         where ingestion_job_id=p_ingestion_job_id
           and coalesce(review_status,'pending')<>'applied'
           and target_table in ('pc_entities','pc_assets','pc_mobile_assets','pc_events')
         order by case target_table when 'pc_entities' then 1 when 'pc_assets' then 2 when 'pc_mobile_assets' then 3 when 'pc_events' then 4 else 9 end,
                  created_at nulls last
    loop
        begin
            if r.target_table='pc_entities' then v_result:=pc_resolve_upsert_entity(p_ingestion_job_id,r.payload);
            elsif r.target_table='pc_assets' then v_result:=pc_resolve_upsert_asset(p_ingestion_job_id,r.payload);
            elsif r.target_table='pc_mobile_assets' then v_result:=pc_resolve_upsert_mobile_asset(p_ingestion_job_id,r.payload);
            else v_result:=pc_resolve_upsert_event(p_ingestion_job_id,r.payload);
            end if;

            if v_result->>'status'='REVIEW' then
                update pc_staged_records set resolution_status='AMBIGUOUS',review_status='pending',validation_status='reviewed',
                       resolution_method=v_result->>'reason',candidate_count=coalesce((v_result->>'candidate_count')::int,0)
                 where staged_record_id=r.staged_record_id;
                v_review:=v_review+1;
            else
                update pc_staged_records set review_status='applied',validation_status='validated',resolution_status='MATCHED',
                       resolution_method=lower(v_result->>'action'),resolved_entity_id=v_result->>'canonical_id',resolution_confidence=1
                 where staged_record_id=r.staged_record_id;
                if v_result->>'action'='CREATE' then v_created:=v_created+1; else v_upserted:=v_upserted+1; end if;
                v_processed:=v_processed+1;
            end if;
        exception when others then
            update pc_staged_records set resolution_status='INVALID',validation_status='invalid',review_status='pending',
                   resolution_method='PROCESS_ERROR: '||sqlerrm
             where staged_record_id=r.staged_record_id;
            v_errors:=v_errors+1;
        end;
    end loop;

    -- EDGES SECOND
    for r in
        select * from pc_staged_records
         where ingestion_job_id=p_ingestion_job_id
           and coalesce(review_status,'pending')<>'applied'
           and target_table in ('pc_relationships','pc_event_links')
         order by case target_table when 'pc_relationships' then 1 else 2 end, created_at nulls last
    loop
        begin
            if r.target_table='pc_relationships' then
                v_result:=pc_upsert_relationship_from_payload(p_ingestion_job_id,r.payload);
            else
                v_result:=pc_upsert_event_link_from_payload(p_ingestion_job_id,r.payload);
            end if;
            if v_result->>'status'='REVIEW' then
                update pc_staged_records
                   set resolution_status=case
                        when v_result->>'reason' like 'MISSING_%' then 'BROKEN_REFERENCE'
                        else 'UNRESOLVED'
                       end,
                       validation_status='reviewed',
                       review_status='pending',
                       resolution_method=v_result->>'reason'
                 where staged_record_id=r.staged_record_id;
                v_review:=v_review+1;
            else
                update pc_staged_records
                   set review_status='applied',
                       validation_status='validated',
                       resolution_status='MATCHED',
                       resolution_method='canonical_edge_upsert',
                       resolution_confidence=1
                 where staged_record_id=r.staged_record_id;
                v_processed:=v_processed+1;
                v_edges:=v_edges+1;
            end if;
        exception when foreign_key_violation then
            update pc_staged_records set resolution_status='BROKEN_REFERENCE',validation_status='reviewed',review_status='pending',
                   resolution_method='MISSING_CANONICAL_ENDPOINT: '||sqlerrm
             where staged_record_id=r.staged_record_id;
            v_review:=v_review+1;
        when others then
            update pc_staged_records set resolution_status='INVALID',validation_status='invalid',review_status='pending',
                   resolution_method='EDGE_PROCESS_ERROR: '||sqlerrm
             where staged_record_id=r.staged_record_id;
            v_errors:=v_errors+1;
        end;
    end loop;

    -- Direct-ID tables can be upserted after graph objects. This keeps 041 useful for existing workbooks.
    for r in
        select * from pc_staged_records
         where ingestion_job_id=p_ingestion_job_id
           and coalesce(review_status,'pending')<>'applied'
           and target_table in ('pc_transactions','pc_transport_routes','pc_chokepoints','pc_market_instruments','pc_trade_flows','pc_supply_series','pc_observations')
         order by created_at nulls last
    loop
        begin
            if r.target_table='pc_transactions' then v_result:=pc_upsert_json(r.target_table,r.payload,array['transaction_id']);
            elsif r.target_table='pc_transport_routes' then v_result:=pc_upsert_json(r.target_table,r.payload,array['route_id']);
            elsif r.target_table='pc_chokepoints' then v_result:=pc_upsert_json(r.target_table,r.payload,array['chokepoint_id']);
            elsif r.target_table='pc_market_instruments' then v_result:=pc_upsert_json(r.target_table,r.payload,array['market_instrument_id']);
            elsif r.target_table='pc_trade_flows' then v_result:=pc_upsert_json(r.target_table,r.payload,array['trade_flow_id']);
            elsif r.target_table='pc_supply_series' then v_result:=pc_upsert_json(r.target_table,r.payload,array['supply_series_id']);
            else v_result:=pc_upsert_json(r.target_table,r.payload,array['observation_id']); end if;
            update pc_staged_records set review_status='applied',validation_status='validated',resolution_status='MATCHED',resolution_method='direct_upsert',resolution_confidence=1
             where staged_record_id=r.staged_record_id;
            v_processed:=v_processed+1; v_upserted:=v_upserted+1;
        exception when others then
            update pc_staged_records set resolution_status='INVALID',validation_status='invalid',review_status='pending',resolution_method='DIRECT_UPSERT_ERROR: '||sqlerrm
             where staged_record_id=r.staged_record_id;
            v_errors:=v_errors+1;
        end;
    end loop;

    update pc_ingestion_jobs
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

grant execute on function public.pc_process_ingestion_job_v5(uuid) to authenticated;
grant execute on function public.pc_resolve_upsert_entity(uuid,jsonb) to authenticated;
grant execute on function public.pc_resolve_upsert_asset(uuid,jsonb) to authenticated;
grant execute on function public.pc_resolve_upsert_mobile_asset(uuid,jsonb) to authenticated;
grant execute on function public.pc_resolve_upsert_event(uuid,jsonb) to authenticated;
grant execute on function public.pc_upsert_relationship_from_payload(uuid,jsonb) to authenticated;
grant execute on function public.pc_upsert_event_link_from_payload(uuid,jsonb) to authenticated;

commit;
