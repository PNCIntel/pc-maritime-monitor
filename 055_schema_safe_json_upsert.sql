-- Power & Corridors
-- 055_schema_safe_json_upsert.sql
--
-- SYSTEM-WIDE FIX FOR REPEATED LOADER CAST ERRORS
--
-- Recent packages have repeatedly failed because workbook / AI payloads carry
-- descriptive strings into strongly typed PostgreSQL columns, especially BOOLEAN:
--
--   "control"   -> pc_relationships.operating_control boolean
--   "developer" -> pc_transactions.operating_control boolean
--   "true"      -> other boolean fields arriving as text
--
-- The canonical loader should not require a new SQL patch for every workbook.
--
-- 055 fixes this at the common write layer:
--   pc_upsert_json(...)
--
-- Before jsonb_populate_record casts a payload into a live table row, the payload
-- is normalized against the ACTUAL PostgreSQL column types.
--
-- For BOOLEAN columns:
--   true / t / yes / y / 1 / active / enabled / control / controlled -> true
--   false / f / no / n / 0 / inactive / disabled / no-control       -> false
--   unknown descriptive text is moved into metadata.ingest_labels.<column>
--   and removed from the typed column rather than crashing the entire record.
--
-- This means the correction automatically applies to:
--   pc_entities
--   pc_assets
--   pc_mobile_assets
--   pc_events
--   pc_relationships
--   pc_event_links
--   pc_transactions
--   pc_transport_routes
--   and other tables written through pc_upsert_json.
--
-- It does NOT weaken identity or endpoint validation.
-- It does NOT invent values.
-- It preserves non-castable descriptive text in metadata.
--
-- Safe to run repeatedly.

begin;

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
begin
    if v_name !~ '^pc_[a-z0-9_]+$' then
        raise exception 'Unsafe table name: %', p_table;
    end if;

    if to_regclass('public.'||v_name) is null then
        raise exception 'Unknown canonical table: %', v_name;
    end if;

    -- ------------------------------------------------------------------
    -- Normalize every BOOLEAN column that is present in the incoming JSON.
    -- ------------------------------------------------------------------
    for r in
        select
            c.column_name,
            c.data_type
        from information_schema.columns c
        where c.table_schema='public'
          and c.table_name=v_name
          and c.data_type='boolean'
          and v ? c.column_name
    loop
        -- Already a proper JSON boolean.
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
            v := jsonb_set(v, array[r.column_name], 'true'::jsonb, true);

        elsif v_norm in (
            'false','f','no','n','0',
            'inactive','disabled','disable',
            'non-control','non control','no control',
            'not controlled','minority non-control'
        ) then
            v := jsonb_set(v, array[r.column_name], 'false'::jsonb, true);

        else
            -- Do not guess. Preserve the descriptive source value in metadata.
            v_meta := case
                when jsonb_typeof(v->'metadata')='object' then v->'metadata'
                else '{}'::jsonb
            end;

            v_labels := case
                when jsonb_typeof(v_meta->'ingest_labels')='object'
                then v_meta->'ingest_labels'
                else '{}'::jsonb
            end;

            v_labels := jsonb_set(
                v_labels,
                array[r.column_name],
                to_jsonb(v_raw),
                true
            );

            v_meta := jsonb_set(
                v_meta,
                '{ingest_labels}',
                v_labels,
                true
            );

            v := jsonb_set(v,'{metadata}',v_meta,true);
            v := v - r.column_name;
        end if;
    end loop;

    return v;
end;
$$;


-- ---------------------------------------------------------------------------
-- Replace the COMMON JSON upsert function in place.
-- All existing resolver/writer functions continue to call pc_upsert_json,
-- but now benefit from live-schema coercion automatically.
-- ---------------------------------------------------------------------------
create or replace function public.pc_upsert_json(
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
    v_cols text[];
    v_col_list text;
    v_select_list text;
    v_conflict text;
    v_update text;
    v_sql text;
    v_result jsonb;
    v_schema text := 'public';
    v_name text := replace(p_table,'public.','');
    v_payload jsonb;
begin
    if v_name !~ '^pc_[a-z0-9_]+$' then
        raise exception 'Unsafe table name: %', p_table;
    end if;

    -- Central schema-safe normalization.
    v_payload := public.pc_schema_safe_payload(v_name,coalesce(p_payload,'{}'::jsonb));

    select array_agg(a.attname order by a.attnum)
      into v_cols
      from pg_attribute a
      join pg_class c on c.oid=a.attrelid
      join pg_namespace n on n.oid=c.relnamespace
     where n.nspname=v_schema
       and c.relname=v_name
       and a.attnum>0
       and not a.attisdropped
       and a.attgenerated=''
       and v_payload ? a.attname;

    if coalesce(array_length(v_cols,1),0)=0 then
        raise exception 'No writable payload columns for %', v_name;
    end if;

    if exists (
        select 1
        from unnest(p_conflict_cols) x
        where not (x=any(v_cols))
           or nullif(v_payload->>x,'') is null
    ) then
        raise exception 'Missing conflict key for %: %', v_name, p_conflict_cols;
    end if;

    select string_agg(format('%I',x),',')
      into v_col_list
      from unnest(v_cols) x;

    select string_agg(format('(r).%I',x),',')
      into v_select_list
      from unnest(v_cols) x;

    select string_agg(format('%I',x),',')
      into v_conflict
      from unnest(p_conflict_cols) x;

    select string_agg(
        case
            when x='metadata' then
                format(
                    '%I = public.pc_merge_metadata(%I.%I, excluded.%I)',
                    x,v_name,x,x
                )
            else
                format(
                    '%I = coalesce(excluded.%I, %I.%I)',
                    x,x,v_name,x
                )
        end,
        ','
    )
    into v_update
    from unnest(v_cols) x
    where not (x=any(p_conflict_cols));

    v_sql := format(
        'with src as (
             select jsonb_populate_record(null::public.%I,$1) r
         ),
         u as (
             insert into public.%I (%s)
             select %s from src
             on conflict (%s)
             do update set %s
             returning to_jsonb(%I.*)
         )
         select coalesce((select * from u),''{}''::jsonb)',
        v_name,
        v_name,
        v_col_list,
        v_select_list,
        v_conflict,
        coalesce(nullif(v_update,''),' '),
        v_name
    );

    execute v_sql using v_payload into v_result;
    return v_result;
end;
$$;


grant execute on function public.pc_schema_safe_payload(text,jsonb)
to authenticated;

grant execute on function public.pc_upsert_json(text,jsonb,text[])
to authenticated;

commit;


-- ---------------------------------------------------------------------------
-- AFTER INSTALLING 055
-- ---------------------------------------------------------------------------
-- On the CURRENT 105-row package:
--
--   click "Retry unresolved rows in this package"
--
-- The repeated boolean cast failures should clear automatically.
--
-- Any event_links showing MISSING_EVENT_ENDPOINT or MISSING_LINKED_ENDPOINT
-- should then resolve on the same/next retry once their parent events/assets
-- have successfully applied.
--
-- If links remain after the first retry, click retry once more because the
-- parent objects must exist before the child links are written.
--
-- Useful post-check:
--
-- select
--     target_table,
--     resolution_status,
--     review_status,
--     resolution_method,
--     count(*)
-- from public.pc_staged_records
-- where ingestion_job_id = '<CURRENT_JOB_UUID>'::uuid
-- group by 1,2,3,4
-- order by 1,2,3,4;
--
-- To inspect any genuinely remaining exceptions:
--
-- select
--     target_table,
--     natural_key,
--     resolution_status,
--     resolution_method,
--     payload
-- from public.pc_staged_records
-- where ingestion_job_id = '<CURRENT_JOB_UUID>'::uuid
--   and coalesce(review_status,'pending') <> 'applied'
-- order by target_table,natural_key;
