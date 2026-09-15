-- Power & Corridors
-- 057_event_identity_repair_and_actor_seed.sql
--
-- PURPOSE
-- Fix the current 28-row package where:
--
--   11 pc_assets -> MATCHED / applied
--   17 pc_events -> AMBIGUOUS / pending
--   exact reason -> INSUFFICIENT_EVENT_IDENTITY
--
-- The staged event rows contain useful information inside
-- payload.metadata.source_payload, but the canonical event resolver only checks
-- top-level canonical fields such as title/start_date/event_type/etc.
--
-- This migration:
--   1. Repairs staged event payloads from common source-column aliases.
--   2. Preserves the original source payload.
--   3. Uses event_id + repaired title/date/source evidence for identity.
--   4. Creates/updates simple actor entities when an event source payload names
--      an actor/organization and provides an entity type.
--   5. Does NOT misuse pc_meta_entity_types for company/militia/government
--      subtypes; that table is the canonical OBJECT-TABLE registry, not the
--      organization taxonomy.
--
-- Safe to run repeatedly.

begin;

-- ===========================================================================
-- A. HELPER: first non-empty value from candidate JSON keys
-- ===========================================================================
create or replace function public.pc_first_json_text(
    p_obj jsonb,
    p_keys text[]
)
returns text
language plpgsql
immutable
as $$
declare
    k text;
    v text;
begin
    if jsonb_typeof(p_obj) <> 'object' then
        return null;
    end if;

    foreach k in array p_keys loop
        v := nullif(trim(p_obj->>k),'');
        if v is not null then
            return v;
        end if;
    end loop;

    return null;
end;
$$;


-- ===========================================================================
-- B. REPAIR ONE EVENT PAYLOAD FROM metadata.source_payload
-- ===========================================================================
create or replace function public.pc_repair_event_payload_v4(
    p_payload jsonb
)
returns jsonb
language plpgsql
immutable
as $$
declare
    v jsonb := coalesce(p_payload,'{}'::jsonb);
    s jsonb := case
        when jsonb_typeof(p_payload#>'{metadata,source_payload}')='object'
        then p_payload#>'{metadata,source_payload}'
        else '{}'::jsonb
    end;

    v_title text;
    v_date text;
    v_type text;
    v_family text;
    v_domain text;
    v_country text;
    v_location text;
    v_description text;
    v_severity text;
    v_status text;
    v_mode text;
    v_source_url text;
begin
    v_title := coalesce(
        nullif(trim(v->>'title'),''),
        public.pc_first_json_text(s,array[
            'title','event_title','headline','incident_title','name',
            'event','summary_title','development'
        ])
    );

    v_date := coalesce(
        nullif(trim(v->>'start_date'),''),
        nullif(trim(v->>'event_date'),''),
        public.pc_first_json_text(s,array[
            'start_date','event_date','date','incident_date','reported_date',
            'published_date','observed_date','as_of'
        ])
    );

    v_type := coalesce(
        nullif(trim(v->>'event_type'),''),
        public.pc_first_json_text(s,array[
            'event_type','type','incident_type','category','event_category'
        ])
    );

    v_family := coalesce(
        nullif(trim(v->>'event_family'),''),
        public.pc_first_json_text(s,array[
            'event_family','family','event_group','incident_family'
        ])
    );

    v_domain := coalesce(
        nullif(trim(v->>'event_domain'),''),
        public.pc_first_json_text(s,array[
            'event_domain','domain','sector','security_domain'
        ])
    );

    v_country := coalesce(
        nullif(trim(v->>'countries'),''),
        nullif(trim(v->>'country'),''),
        public.pc_first_json_text(s,array[
            'countries','country','country_name','jurisdiction'
        ])
    );

    v_location := coalesce(
        nullif(trim(v->>'location'),''),
        public.pc_first_json_text(s,array[
            'location','place','city','region','site','facility','area'
        ])
    );

    v_description := coalesce(
        nullif(trim(v->>'description'),''),
        public.pc_first_json_text(s,array[
            'description','summary','details','event_summary','incident_summary',
            'narrative','what_happened'
        ])
    );

    v_severity := coalesce(
        nullif(trim(v->>'severity'),''),
        public.pc_first_json_text(s,array[
            'severity','risk_level','priority'
        ])
    );

    v_status := coalesce(
        nullif(trim(v->>'status'),''),
        public.pc_first_json_text(s,array[
            'status','event_status','incident_status'
        ])
    );

    v_mode := coalesce(
        nullif(trim(v->>'mode'),''),
        public.pc_first_json_text(s,array[
            'mode','transport_mode','domain_mode'
        ])
    );

    v_source_url := coalesce(
        nullif(trim(v->>'source_url'),''),
        public.pc_first_json_text(s,array[
            'source_url','url','link','article_url','source'
        ])
    );

    if v_title is not null then
        v:=jsonb_set(v,'{title}',to_jsonb(v_title),true);
    end if;

    if v_date is not null then
        v:=jsonb_set(v,'{start_date}',to_jsonb(v_date),true);
    end if;

    if v_type is not null then
        v:=jsonb_set(v,'{event_type}',to_jsonb(v_type),true);
    end if;

    if v_family is not null then
        v:=jsonb_set(v,'{event_family}',to_jsonb(v_family),true);
    end if;

    if v_domain is not null then
        v:=jsonb_set(v,'{event_domain}',to_jsonb(v_domain),true);
    end if;

    if v_country is not null then
        v:=jsonb_set(v,'{countries}',to_jsonb(v_country),true);
    end if;

    if v_location is not null then
        v:=jsonb_set(v,'{location}',to_jsonb(v_location),true);
    end if;

    if v_description is not null then
        v:=jsonb_set(v,'{description}',to_jsonb(v_description),true);
    end if;

    if v_severity is not null then
        v:=jsonb_set(v,'{severity}',to_jsonb(v_severity),true);
    end if;

    if v_status is not null then
        v:=jsonb_set(v,'{status}',to_jsonb(v_status),true);
    end if;

    if v_mode is not null then
        v:=jsonb_set(v,'{mode}',to_jsonb(v_mode),true);
    end if;

    if v_source_url is not null then
        v:=jsonb_set(v,'{source_url}',to_jsonb(v_source_url),true);
    end if;

    return v;
end;
$$;


-- ===========================================================================
-- C. REPAIR ALL PENDING EVENT ROWS SYSTEM-WIDE
-- ===========================================================================
create or replace function public.pc_repair_pending_event_identities_v4(
    p_job uuid default null
)
returns jsonb
language plpgsql
security definer
set search_path=public
as $$
declare
    v_count int:=0;
begin
    update public.pc_staged_records s
       set payload=public.pc_repair_event_payload_v4(s.payload),
           resolution_status='NEW',
           validation_status='pending',
           resolution_method='EVENT_PAYLOAD_REPAIRED_V4',
           candidate_count=0
     where s.target_table='pc_events'
       and coalesce(lower(s.review_status),'pending')<>'applied'
       and (p_job is null or s.ingestion_job_id=p_job)
       and (
            s.resolution_method='INSUFFICIENT_EVENT_IDENTITY'
            or s.resolution_status in ('AMBIGUOUS','INVALID','UNRESOLVED')
       );

    get diagnostics v_count=row_count;

    return jsonb_build_object(
        'status','OK',
        'repaired_event_rows',v_count,
        'job_id',p_job
    );
end;
$$;


-- ===========================================================================
-- D. OPTIONAL ACTOR ENTITY SEEDING
--
-- If source payloads explicitly carry:
--   actor_name / organization / organisation / actor
-- plus:
--   actor_type / entity_type / organization_type
--
-- create/upsert those as canonical pc_entities.
--
-- This is intentionally conservative: no actor name -> no entity is invented.
-- ===========================================================================
create or replace function public.pc_seed_event_actor_entities_v1(
    p_job uuid default null
)
returns jsonb
language plpgsql
security definer
set search_path=public
as $$
declare
    r record;
    s jsonb;
    v_name text;
    v_type text;
    v_country text;
    v_source_url text;
    v_id text;
    v_payload jsonb;
    v_result jsonb;
    v_created int:=0;
    v_matched int:=0;
begin
    for r in
        select *
        from public.pc_staged_records
        where target_table='pc_events'
          and coalesce(lower(review_status),'pending')<>'applied'
          and (p_job is null or ingestion_job_id=p_job)
    loop
        s := case
            when jsonb_typeof(r.payload#>'{metadata,source_payload}')='object'
            then r.payload#>'{metadata,source_payload}'
            else '{}'::jsonb
        end;

        v_name := public.pc_first_json_text(s,array[
            'actor_name','organization','organisation','actor',
            'company','entity_name','operator'
        ]);

        v_type := public.pc_first_json_text(s,array[
            'actor_type','entity_type','organization_type',
            'organisation_type'
        ]);

        v_country := public.pc_first_json_text(s,array[
            'actor_country','country','country_name','jurisdiction'
        ]);

        v_source_url := coalesce(
            nullif(r.payload->>'source_url',''),
            public.pc_first_json_text(s,array['source_url','url','link'])
        );

        -- Do not fabricate an entity without a named actor.
        if v_name is null then
            continue;
        end if;

        -- Generic fallback is acceptable for a known named organization.
        if v_type is null then
            v_type := 'organization';
        end if;

        v_id := 'ENT_'||upper(substr(md5(
            public.pc_norm_identity_text(v_name)||'|'||
            coalesce(public.pc_norm_identity_text(v_country),'')||'|'||
            coalesce(public.pc_norm_identity_text(v_type),'')
        ),1,20));

        v_payload := jsonb_build_object(
            'entity_id',v_id,
            'name',v_name,
            'entity_type',v_type,
            'status','active',
            'record_status','provisional'
        );

        if v_country is not null then
            v_payload:=jsonb_set(v_payload,'{country}',to_jsonb(v_country),true);
            v_payload:=jsonb_set(v_payload,'{hq_country}',to_jsonb(v_country),true);
        end if;

        if v_source_url is not null then
            v_payload:=jsonb_set(v_payload,'{source_url}',to_jsonb(v_source_url),true);
        end if;

        v_payload:=jsonb_set(
            v_payload,
            '{metadata}',
            jsonb_build_object(
                'seeded_from_event',r.natural_key,
                'ingestion_job_id',r.ingestion_job_id
            ),
            true
        );

        v_result:=public.pc_resolve_upsert_entity(
            r.ingestion_job_id,
            v_payload
        );

        if v_result->>'action'='CREATE' then
            v_created:=v_created+1;
        else
            v_matched:=v_matched+1;
        end if;
    end loop;

    return jsonb_build_object(
        'status','OK',
        'created',v_created,
        'matched_or_upserted',v_matched,
        'job_id',p_job
    );
end;
$$;


-- ===========================================================================
-- E. MAKE EVENT RESOLVER REPAIR SOURCE PAYLOAD BEFORE IDENTITY CHECK
-- ===========================================================================
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
    v_source_event_id text;
    v_id text;
    v_count integer;
    v_payload jsonb;
    v_action text;
    v_start_date text;
    v_end_date text;
begin
    v_payload := public.pc_repair_event_payload_v4(
        public.pc_source_fk_safe_payload(coalesce(p_payload,'{}'::jsonb))
    );

    v_source_event_id := nullif(v_payload->>'event_id','');

    if not public.pc_minimum_identity_ok('event',v_payload) then
        return jsonb_build_object(
            'status','REVIEW',
            'reason','INSUFFICIENT_EVENT_IDENTITY',
            'event_id',v_source_event_id,
            'has_title',nullif(v_payload->>'title','') is not null,
            'has_date',(
                nullif(v_payload->>'start_date','') is not null
                or nullif(v_payload->>'event_date','') is not null
            ),
            'has_source',nullif(v_payload->>'source_url','') is not null
        );
    end if;

    v_start_date:=public.pc_normalize_ingest_date_text(v_payload->>'start_date');
    v_end_date:=public.pc_normalize_ingest_date_text(v_payload->>'end_date');

    if v_start_date is not null then
        v_payload:=jsonb_set(v_payload,'{start_date}',to_jsonb(v_start_date),true);
    else
        v_payload:=v_payload-'start_date';
    end if;

    if v_end_date is not null then
        v_payload:=jsonb_set(v_payload,'{end_date}',to_jsonb(v_end_date),true);
    else
        v_payload:=v_payload-'end_date';
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
        'normalized_start_date',v_start_date
    );
end;
$$;


grant execute on function public.pc_first_json_text(jsonb,text[]) to authenticated;
grant execute on function public.pc_repair_event_payload_v4(jsonb) to authenticated;
grant execute on function public.pc_repair_pending_event_identities_v4(uuid) to authenticated;
grant execute on function public.pc_seed_event_actor_entities_v1(uuid) to authenticated;
grant execute on function public.pc_resolve_upsert_event(uuid,jsonb) to authenticated;

commit;


-- ===========================================================================
-- HOW TO USE ON THE CURRENT 28-ROW PACKAGE
-- ===========================================================================
--
-- 1) Find the job ID in Power Admin, then run:
--
-- select public.pc_repair_pending_event_identities_v4(
--   '<JOB_UUID>'::uuid
-- );
--
-- 2) Optional but recommended if the source rows name new government/military/
--    militia/company actors:
--
-- select public.pc_seed_event_actor_entities_v1(
--   '<JOB_UUID>'::uuid
-- );
--
-- 3) Back in Power Admin:
--    Retry unresolved rows in this package
--
-- Current:
--   Total    28
--   Applied  11
--   Review   17
--   Broken    0
--
-- Expected if the source_payload contains title/date/source fields:
--   Total    28
--   Applied  28
--   Review    0
--   Broken    0
--
-- Any remaining rows after this are genuine cases where the source payload
-- itself lacks enough event identity, not missing taxonomy plumbing.
