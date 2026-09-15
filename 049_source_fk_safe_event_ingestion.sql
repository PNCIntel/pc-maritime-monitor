-- Power & Corridors
-- 049_source_fk_safe_event_ingestion.sql
--
-- Purpose:
-- Some canonical-loader workbooks carry package-local source_id values such as
-- SRC_REUTERS_20260901. pc_events.source_id / pc_event_links.source_id may be
-- FK-constrained to pc_sources. If the source registry row was not loaded first,
-- the event insert fails even though source_url + metadata provenance are valid.
--
-- Behavior:
--   * preserve the incoming source_id in metadata.source_reference_id
--   * keep source_url / research_sources provenance
--   * retain source_id only when it already exists in pc_sources
--   * otherwise remove source_id before canonical upsert
--
-- This does NOT create fake pc_sources rows and does not weaken endpoint checks.
-- Safe to run repeatedly. Requires the current canonical functions installed.

begin;

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

    -- Preserve the workbook/source-registry key in provenance regardless of
    -- whether it is already canonical in pc_sources.
    v_meta := case
        when jsonb_typeof(v->'metadata')='object' then v->'metadata'
        else '{}'::jsonb
    end;
    v_meta := jsonb_set(
        v_meta,
        '{source_reference_id}',
        to_jsonb(v_source_id),
        true
    );
    v := jsonb_set(v,'{metadata}',v_meta,true);

    if to_regclass('public.pc_sources') is not null then
        execute
            'select exists(select 1 from public.pc_sources where source_id::text=$1)'
        into v_exists
        using v_source_id;
    end if;

    if not v_exists then
        v := v - 'source_id';
    end if;

    return v;
end;
$$;

-- Preserve 048 date normalization while making source_id FK-safe.
create or replace function public.pc_resolve_upsert_event(
    p_job uuid,
    p_payload jsonb
)
returns jsonb
language plpgsql
security definer
set search_path=public
as $$
declare
    v_source_event_id text:=nullif(p_payload->>'event_id','');
    v_id text;
    v_count integer;
    v_payload jsonb:=public.pc_source_fk_safe_payload(p_payload);
    v_action text;
    v_start_date text:=public.pc_normalize_ingest_date_text(p_payload->>'start_date');
    v_end_date text:=public.pc_normalize_ingest_date_text(p_payload->>'end_date');
begin
    if not public.pc_minimum_identity_ok('event',p_payload) then
        return jsonb_build_object(
            'status','REVIEW',
            'reason','INSUFFICIENT_EVENT_IDENTITY'
        );
    end if;

    if v_start_date is not null then
        v_payload:=jsonb_set(v_payload,'{start_date}',to_jsonb(v_start_date),true);
    else
        v_payload:=v_payload - 'start_date';
    end if;

    if v_end_date is not null then
        v_payload:=jsonb_set(v_payload,'{end_date}',to_jsonb(v_end_date),true);
    else
        v_payload:=v_payload - 'end_date';
    end if;

    if v_source_event_id is not null
       and exists(
            select 1 from public.pc_events e
            where e.event_id::text=v_source_event_id
       )
    then
        v_id:=v_source_event_id;
        v_action:='UPSERT_ID';
    else
        select count(*),min(e.event_id::text)
          into v_count,v_id
          from public.pc_events e
         where public.pc_norm_text(e.title)=public.pc_norm_text(v_payload->>'title')
           and (
                v_start_date is null
                or e.start_date::date=v_start_date::date
           );

        if v_count>1 then
            return jsonb_build_object(
                'status','REVIEW',
                'reason','AMBIGUOUS_EVENT',
                'candidate_count',v_count
            );
        elsif v_count=1 then
            v_action:='UPSERT_NAME_DATE';
        else
            v_id:=coalesce(
                v_source_event_id,
                'EVENT_'||upper(substr(md5(
                    coalesce(v_payload->>'title','')||'|'||
                    coalesce(v_start_date,'')||'|'||
                    coalesce(v_payload->>'event_type','')
                ),1,20))
            );
            v_action:='CREATE';
        end if;
    end if;

    v_payload:=jsonb_set(v_payload,'{event_id}',to_jsonb(v_id),true);

    perform public.pc_upsert_json(
        'pc_events',
        v_payload,
        array['event_id']
    );

    perform public.pc_map_ingestion_key(
        p_job,
        'event',
        coalesce(v_source_event_id,v_id),
        v_id,
        lower(v_action)
    );

    return jsonb_build_object(
        'status','OK',
        'canonical_id',v_id,
        'action',v_action,
        'normalized_start_date',v_start_date,
        'source_id_retained',v_payload ? 'source_id'
    );
end;
$$;

create or replace function public.pc_upsert_event_link_from_payload(
    p_job uuid,
    p_payload jsonb
)
returns jsonb
language plpgsql
security definer
set search_path=public
as $$
declare
    v jsonb:=public.pc_source_fk_safe_payload(p_payload);
    v_event text;
    v_linked text;
    v_type text:=lower(v->>'linked_type');
begin
    if v_type='vessel' then
        v_type:='mobile_asset';
        v:=jsonb_set(v,'{linked_type}',to_jsonb(v_type),true);
    end if;

    v_event:=public.pc_mapped_id(p_job,'event',v->>'event_id');
    v_linked:=public.pc_mapped_id(p_job,v_type,v->>'linked_id');

    if not public.pc_object_exists('event',v_event) then
        return jsonb_build_object(
            'status','REVIEW',
            'reason','MISSING_EVENT_ENDPOINT',
            'event_id',v_event
        );
    end if;

    if not public.pc_object_exists(v_type,v_linked) then
        return jsonb_build_object(
            'status','REVIEW',
            'reason','MISSING_LINKED_ENDPOINT',
            'linked_type',v_type,
            'linked_id',v_linked
        );
    end if;

    v:=jsonb_set(v,'{event_id}',to_jsonb(v_event),true);
    v:=jsonb_set(v,'{linked_id}',to_jsonb(v_linked),true);

    perform public.pc_upsert_json(
        'pc_event_links',
        v,
        array['event_link_id']
    );

    return jsonb_build_object(
        'status','OK',
        'event_link_id',v->>'event_link_id',
        'event_id',v_event,
        'linked_id',v_linked,
        'source_id_retained',v ? 'source_id'
    );
end;
$$;

grant execute on function public.pc_source_fk_safe_payload(jsonb) to authenticated;
grant execute on function public.pc_resolve_upsert_event(uuid,jsonb) to authenticated;
grant execute on function public.pc_upsert_event_link_from_payload(uuid,jsonb) to authenticated;

commit;

-- After installing:
-- 1) open the existing 81-row Black Sea ingestion job
-- 2) click "Retry unresolved rows in this package"
-- Expected:
--    30 pc_events retry
--    then 37 pc_event_links retry after parent events exist
--    the 14 already-applied asset/mobile-asset rows remain terminal.
