
begin;

-- ------------------------------------------------------------------
-- Natural-key / alias registry
-- ------------------------------------------------------------------
create table if not exists pc_identity_aliases (
    alias_id uuid primary key default gen_random_uuid(),
    alias_type text not null,
    alias_value text not null,
    canonical_type text not null,
    canonical_id text not null,
    ingestion_job_id uuid null,
    confidence numeric null,
    resolution_method text null,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    unique(alias_type, alias_value, canonical_type, canonical_id)
);

create index if not exists idx_pc_identity_aliases_lookup
    on pc_identity_aliases(alias_type, lower(alias_value), canonical_type);

-- ------------------------------------------------------------------
-- Apply safe NEW entity records using the actual canonical pc_entities
-- schema. Rich research-only fields remain under metadata.source_payload.
-- ------------------------------------------------------------------
create or replace function pc_apply_new_staged_entities(p_ingestion_job_id uuid)
returns jsonb
language plpgsql
security definer
set search_path=public
as $$
declare
    v_inserted integer := 0;
    v_closed integer := 0;
begin
    insert into pc_entities (
        entity_id,
        name,
        entity_type,
        subtype,
        hq_city,
        hq_country,
        ownership_summary,
        status,
        record_status,
        data_quality,
        source_id,
        as_of,
        metadata
    )
    select
        s.payload->>'entity_id',
        coalesce(nullif(s.payload->>'name',''), nullif(s.payload->>'canonical_name','')),
        s.payload->>'entity_type',
        coalesce(nullif(s.payload->>'subtype',''), nullif(s.payload->>'company_type','')),
        coalesce(
            nullif(s.payload->>'hq_city',''),
            nullif(split_part(coalesce(s.payload->>'headquarters',''), ',', 1),'')
        ),
        coalesce(
            nullif(s.payload->>'hq_country',''),
            nullif(s.payload->>'jurisdiction','')
        ),
        coalesce(
            nullif(s.payload->>'ownership_summary',''),
            nullif(s.payload->>'public_private_state_owned','')
        ),
        coalesce(nullif(s.payload->>'status',''),'Active'),
        coalesce(nullif(s.payload->>'record_status',''),'provisional'),
        coalesce(nullif(s.payload->>'data_quality',''),'medium'),
        nullif(s.payload->>'source_id',''),
        coalesce(
            nullif(s.payload->>'as_of','')::date,
            nullif(s.payload->'metadata'->'research_attributes'->>'last_updated','')::date,
            current_date
        ),
        coalesce(s.payload->'metadata','{}'::jsonb)
        || jsonb_build_object(
            'source_payload',
            coalesce(s.payload,'{}'::jsonb) - 'metadata',
            'ingestion_job_id',
            s.ingestion_job_id::text
        )
    from pc_staged_records s
    where s.ingestion_job_id=p_ingestion_job_id
      and s.target_table='pc_entities'
      and s.resolution_status='NEW'
      and coalesce(s.review_status,'pending') in ('pending','approved')
      and coalesce(s.payload->>'entity_id','') <> ''
      and coalesce(s.payload->>'entity_type','') <> ''
      and coalesce(s.payload->>'name',s.payload->>'canonical_name','') <> ''
    on conflict (entity_id) do nothing;

    get diagnostics v_inserted=row_count;

    update pc_staged_records s
       set review_status='applied',
           validation_status='validated',
           resolved_entity_id=s.payload->>'entity_id',
           resolution_method='CANONICAL_ID'
     where s.ingestion_job_id=p_ingestion_job_id
       and s.target_table='pc_entities'
       and s.resolution_status='NEW'
       and coalesce(s.review_status,'pending') in ('pending','approved')
       and exists (
           select 1 from pc_entities e
           where e.entity_id=s.payload->>'entity_id'
       );

    get diagnostics v_closed=row_count;

    return jsonb_build_object(
        'inserted',v_inserted,
        'staging_closed',v_closed
    );
end;
$$;

-- ------------------------------------------------------------------
-- Apply safe NEW event records using the known canonical pc_events schema.
-- This is intentionally conservative: only the event payload itself is
-- written; dependencies are handled separately.
-- ------------------------------------------------------------------
create or replace function pc_apply_new_staged_events(p_ingestion_job_id uuid)
returns jsonb
language plpgsql
security definer
set search_path=public
as $$
declare
    v_inserted integer := 0;
    v_closed integer := 0;
begin
    insert into pc_events (
        event_id,
        start_date,
        end_date,
        event_nature,
        event_domain,
        event_family,
        event_type,
        severity,
        status,
        mode,
        countries,
        location,
        title,
        description,
        operational_impact,
        commercial_impact,
        confidence,
        trade_relevance,
        intelligence_relevance,
        trade_visible,
        intelligence_visible,
        alert_worthy,
        record_status,
        source_id,
        metadata
    )
    select
        s.payload->>'event_id',
        coalesce(
            nullif(s.payload->>'start_date','')::timestamptz,
            nullif(s.payload->>'event_date','')::timestamptz,
            nullif(s.payload->'metadata'->'research_attributes'->>'event_date','')::timestamptz,
            nullif(s.payload->'metadata'->'research_attributes'->>'award_date','')::timestamptz,
            nullif(s.payload->'metadata'->'research_attributes'->>'announcement_date','')::timestamptz
        ),
        nullif(s.payload->>'end_date','')::timestamptz,
        nullif(s.payload->>'event_nature',''),
        nullif(s.payload->>'event_domain',''),
        nullif(s.payload->>'event_family',''),
        nullif(s.payload->>'event_type',''),
        nullif(s.payload->>'severity',''),
        nullif(s.payload->>'status',''),
        nullif(s.payload->>'mode',''),
        coalesce(nullif(s.payload->>'countries',''), nullif(s.payload->>'country','')),
        nullif(s.payload->>'location',''),
        coalesce(nullif(s.payload->>'title',''), nullif(s.payload->>'name','')),
        nullif(s.payload->>'description',''),
        nullif(s.payload->>'operational_impact',''),
        nullif(s.payload->>'commercial_impact',''),
        nullif(s.payload->>'confidence',''),
        greatest(0,least(5,coalesce(nullif(s.payload->>'trade_relevance','')::int,0)))::smallint,
        greatest(0,least(5,coalesce(nullif(s.payload->>'intelligence_relevance','')::int,0)))::smallint,
        coalesce(nullif(s.payload->>'trade_visible','')::boolean,false),
        coalesce(nullif(s.payload->>'intelligence_visible','')::boolean,false),
        coalesce(nullif(s.payload->>'alert_worthy','')::boolean,false),
        coalesce(nullif(s.payload->>'record_status',''),'provisional'),
        nullif(s.payload->>'source_id',''),
        coalesce(s.payload->'metadata','{}'::jsonb)
        || jsonb_build_object(
            'source_payload',
            coalesce(s.payload,'{}'::jsonb) - 'metadata',
            'ingestion_job_id',
            s.ingestion_job_id::text,
            'research_natural_key',
            s.natural_key
        )
    from pc_staged_records s
    where s.ingestion_job_id=p_ingestion_job_id
      and s.target_table='pc_events'
      and s.resolution_status='NEW'
      and coalesce(s.review_status,'pending') in ('pending','approved')
      and coalesce(s.payload->>'event_id','') <> ''
      and coalesce(s.payload->>'title',s.payload->>'name','') <> ''
    on conflict (event_id) do nothing;

    get diagnostics v_inserted=row_count;

    update pc_staged_records s
       set review_status='applied',
           validation_status='validated',
           resolved_entity_id=s.payload->>'event_id',
           resolution_method='CANONICAL_ID'
     where s.ingestion_job_id=p_ingestion_job_id
       and s.target_table='pc_events'
       and s.resolution_status='NEW'
       and coalesce(s.review_status,'pending') in ('pending','approved')
       and exists (
           select 1 from pc_events e
           where e.event_id=s.payload->>'event_id'
       );

    get diagnostics v_closed=row_count;

    return jsonb_build_object(
        'inserted',v_inserted,
        'staging_closed',v_closed
    );
end;
$$;

-- ------------------------------------------------------------------
-- Register job-local aliases so later records can refer to natural keys
-- rather than already knowing the canonical generated ID.
-- ------------------------------------------------------------------
create or replace function pc_register_job_aliases(p_ingestion_job_id uuid)
returns jsonb
language plpgsql
security definer
set search_path=public
as $$
declare
    v_entities integer := 0;
    v_events integer := 0;
begin
    insert into pc_identity_aliases(
        alias_type,alias_value,canonical_type,canonical_id,
        ingestion_job_id,confidence,resolution_method,metadata
    )
    select
        'natural_key',
        s.natural_key,
        'entity',
        coalesce(s.resolved_entity_id,s.payload->>'entity_id'),
        s.ingestion_job_id,
        s.confidence,
        coalesce(s.resolution_method,'CANONICAL_ID'),
        jsonb_build_object('target_table','pc_entities')
    from pc_staged_records s
    where s.ingestion_job_id=p_ingestion_job_id
      and s.target_table='pc_entities'
      and coalesce(s.natural_key,'') <> ''
      and coalesce(s.resolved_entity_id,s.payload->>'entity_id','') <> ''
      and exists (
          select 1 from pc_entities e
          where e.entity_id=coalesce(s.resolved_entity_id,s.payload->>'entity_id')
      )
    on conflict do nothing;

    get diagnostics v_entities=row_count;

    insert into pc_identity_aliases(
        alias_type,alias_value,canonical_type,canonical_id,
        ingestion_job_id,confidence,resolution_method,metadata
    )
    select
        'natural_key',
        s.natural_key,
        'event',
        coalesce(s.resolved_entity_id,s.payload->>'event_id'),
        s.ingestion_job_id,
        s.confidence,
        coalesce(s.resolution_method,'CANONICAL_ID'),
        jsonb_build_object('target_table','pc_events')
    from pc_staged_records s
    where s.ingestion_job_id=p_ingestion_job_id
      and s.target_table='pc_events'
      and coalesce(s.natural_key,'') <> ''
      and coalesce(s.resolved_entity_id,s.payload->>'event_id','') <> ''
      and exists (
          select 1 from pc_events e
          where e.event_id=coalesce(s.resolved_entity_id,s.payload->>'event_id')
      )
    on conflict do nothing;

    get diagnostics v_events=row_count;

    return jsonb_build_object('entity_aliases',v_entities,'event_aliases',v_events);
end;
$$;

-- ------------------------------------------------------------------
-- Resolve a research natural key into a canonical ID.
-- ------------------------------------------------------------------
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
where lower(a.alias_value)=lower(p_alias_value)
  and a.canonical_type=p_canonical_type
  and (p_ingestion_job_id is null or a.ingestion_job_id=p_ingestion_job_id)
order by
    case when a.ingestion_job_id=p_ingestion_job_id then 0 else 1 end,
    a.created_at desc
limit 1;
$$;

-- ------------------------------------------------------------------
-- Expand malformed array-based event links into one canonical event link
-- per participant once the event and entities are canonical.
--
-- Role inference:
-- contractor / customer / awarding_authority / counterparty / participant
-- based on canonical event research_attributes.
-- ------------------------------------------------------------------
create or replace function pc_expand_event_link_arrays(p_ingestion_job_id uuid)
returns jsonb
language plpgsql
security definer
set search_path=public
as $$
declare
    s record;
    v_event_id text;
    v_name text;
    v_entity_id text;
    v_relationship text;
    v_total integer := 0;
    v_inserted integer := 0;
    v_unresolved integer := 0;
    v_expected integer;
    v_done integer;
    v_unresolved_names jsonb;
    v_attrs jsonb;
begin
    for s in
        select *
        from pc_staged_records
        where ingestion_job_id=p_ingestion_job_id
          and target_table='pc_event_links'
          and jsonb_typeof(payload->'linked_entities')='array'
          and coalesce(review_status,'pending') <> 'applied'
    loop
        v_total := v_total + 1;

        -- Resolve canonical event.
        v_event_id := null;

        if coalesce(s.payload->>'event_id','') <> ''
           and exists(select 1 from pc_events e where e.event_id=s.payload->>'event_id')
        then
            v_event_id := s.payload->>'event_id';
        end if;

        if v_event_id is null and coalesce(s.payload->>'event_natural_key','') <> '' then
            v_event_id := pc_resolve_alias(
                s.payload->>'event_natural_key','event',p_ingestion_job_id
            );
        end if;

        -- Compatibility fallback: find the applied staged event by natural key.
        if v_event_id is null and coalesce(s.payload->>'event_natural_key','') <> '' then
            select coalesce(x.resolved_entity_id,x.payload->>'event_id')
              into v_event_id
            from pc_staged_records x
            where x.ingestion_job_id=p_ingestion_job_id
              and x.target_table='pc_events'
              and x.natural_key=s.payload->>'event_natural_key'
              and exists(
                  select 1 from pc_events e
                  where e.event_id=coalesce(x.resolved_entity_id,x.payload->>'event_id')
              )
            order by x.created_at desc
            limit 1;
        end if;

        if v_event_id is null then
            update pc_staged_records
               set resolution_status='BROKEN_REFERENCE',
                   payload=payload || jsonb_build_object(
                       'dependency_error','EVENT_NOT_CANONICAL',
                       'dependency_event_natural_key',payload->>'event_natural_key'
                   )
             where staged_record_id=s.staged_record_id;
            v_unresolved := v_unresolved + 1;
            continue;
        end if;

        select coalesce(e.metadata->'research_attributes','{}'::jsonb)
          into v_attrs
        from pc_events e
        where e.event_id=v_event_id;

        v_expected := jsonb_array_length(s.payload->'linked_entities');
        v_done := 0;
        v_unresolved_names := '[]'::jsonb;

        for v_name in
            select jsonb_array_elements_text(s.payload->'linked_entities')
        loop
            v_entity_id := null;

            select e.entity_id
              into v_entity_id
            from pc_entities e
            where lower(trim(e.name))=lower(trim(v_name))
            order by e.created_at desc
            limit 1;

            -- Fallback via applied staged entity names.
            if v_entity_id is null then
                select coalesce(x.resolved_entity_id,x.payload->>'entity_id')
                  into v_entity_id
                from pc_staged_records x
                where x.ingestion_job_id=p_ingestion_job_id
                  and x.target_table='pc_entities'
                  and lower(trim(coalesce(x.payload->>'name',x.payload->>'canonical_name','')))=lower(trim(v_name))
                  and exists (
                      select 1 from pc_entities e
                      where e.entity_id=coalesce(x.resolved_entity_id,x.payload->>'entity_id')
                  )
                order by x.created_at desc
                limit 1;
            end if;

            if v_entity_id is null then
                v_unresolved_names := v_unresolved_names || to_jsonb(v_name);
                continue;
            end if;

            v_relationship := 'participant';

            if position(lower(v_name) in lower(coalesce(v_attrs->>'contractor',''))) > 0
               or position(lower(v_name) in lower(coalesce(v_attrs->>'company',''))) > 0
            then
                v_relationship := 'contractor';
            end if;

            if lower(trim(v_name))=lower(trim(coalesce(v_attrs->>'customer',''))) then
                v_relationship := 'customer';
            end if;

            if position(lower(v_name) in lower(coalesce(v_attrs->>'awarding_authority',''))) > 0 then
                v_relationship := 'awarding_authority';
            elsif position(lower(v_name) in lower(coalesce(v_attrs->>'counterparty',''))) > 0
                  and v_relationship='participant'
            then
                v_relationship := 'counterparty';
            end if;

            insert into pc_event_links(
                event_link_id,event_id,linked_type,linked_id,linked_name,
                relationship,confidence,source_id,metadata
            )
            values(
                pc_event_link_id(v_event_id,'entity',v_entity_id,v_relationship),
                v_event_id,
                'entity',
                v_entity_id,
                v_name,
                v_relationship,
                coalesce(s.payload->>'confidence','high'),
                nullif(s.payload->>'source_id',''),
                coalesce(s.payload->'metadata','{}'::jsonb)
                || jsonb_build_object(
                    'expanded_from_staged_record_id',s.staged_record_id::text,
                    'event_natural_key',s.payload->>'event_natural_key'
                )
            )
            on conflict (event_link_id) do nothing;

            v_done := v_done + 1;
            v_inserted := v_inserted + 1;
        end loop;

        if v_done=v_expected then
            update pc_staged_records
               set resolution_status='ALREADY_EXISTS',
                   review_status='applied',
                   validation_status='validated',
                   resolution_method='ARRAY_EXPANSION',
                   payload=payload || jsonb_build_object(
                       'canonical_event_id',v_event_id,
                       'repair_completed',true,
                       'expanded_link_count',v_done
                   )
             where staged_record_id=s.staged_record_id;
        else
            update pc_staged_records
               set resolution_status='BROKEN_REFERENCE',
                   payload=payload || jsonb_build_object(
                       'canonical_event_id',v_event_id,
                       'expanded_link_count',v_done,
                       'expected_link_count',v_expected,
                       'unresolved_linked_entities',v_unresolved_names
                   )
             where staged_record_id=s.staged_record_id;
            v_unresolved := v_unresolved + 1;
        end if;
    end loop;

    return jsonb_build_object(
        'aggregate_rows_seen',v_total,
        'canonical_links_attempted',v_inserted,
        'aggregate_rows_unresolved',v_unresolved
    );
end;
$$;

-- ------------------------------------------------------------------
-- Human-readable dependency / exception view.
-- ------------------------------------------------------------------
create or replace view pc_v_ingestion_dependency_exceptions as
select
    s.staged_record_id,
    s.ingestion_job_id,
    s.target_table,
    s.natural_key,
    s.resolution_status,
    s.review_status,
    s.validation_status,
    case
        when s.target_table='pc_event_links'
         and jsonb_typeof(s.payload->'linked_entities')='array'
         and s.resolution_status='BROKEN_REFERENCE'
            then 'EVENT_LINK_DEPENDENCY'
        when s.target_table='pc_event_links'
         and jsonb_typeof(s.payload->'linked_entities')='array'
            then 'ARRAY_EXPANSION_REQUIRED'
        when s.resolution_status='BROKEN_REFERENCE'
            then 'BROKEN_REFERENCE'
        when s.resolution_status='PARTIAL'
            then 'PARTIAL_RELATIONSHIP'
        when s.resolution_status='AMBIGUOUS'
            then 'TRUE_AMBIGUITY'
        when s.resolution_status='INVALID'
            then 'UNSUPPORTED_OR_INVALID_TARGET'
        when s.resolution_status='NEW'
         and coalesce(s.review_status,'pending')='pending'
            then 'READY_FOR_CANONICAL_PREP'
        else 'REVIEW'
    end as exception_type,
    s.payload,
    s.created_at
from pc_staged_records s
where coalesce(s.review_status,'pending') <> 'applied'
   or s.resolution_status in ('BROKEN_REFERENCE','PARTIAL','AMBIGUOUS','INVALID');

-- ------------------------------------------------------------------
-- One-click dependency-aware reconciliation.
-- It deliberately applies only entity/event records for which canonical
-- schemas are known here. Other domain tables remain reviewable.
-- ------------------------------------------------------------------
create or replace function pc_reconcile_ingestion_job(p_ingestion_job_id uuid)
returns jsonb
language plpgsql
security definer
set search_path=public
as $$
declare
    v_result jsonb := '{}'::jsonb;
    v_part jsonb;
begin
    -- Existing normalization/ID cleanup where available.
    if to_regprocedure('pc_cleanup_staging_names(uuid)') is not null then
        execute 'select pc_cleanup_staging_names($1)' into v_part using p_ingestion_job_id;
        v_result := v_result || jsonb_build_object('normalize_names',v_part);
    end if;

    if to_regprocedure('pc_cleanup_staging_keys(uuid)') is not null then
        execute 'select pc_cleanup_staging_keys($1)' into v_part using p_ingestion_job_id;
        v_result := v_result || jsonb_build_object('fill_keys',v_part);
    end if;

    -- Resolve candidates before safe canonical writes.
    if to_regprocedure('pc_prepare_canonical_candidates(uuid)') is not null then
        execute 'select pc_prepare_canonical_candidates($1)' into v_part using p_ingestion_job_id;
        v_result := v_result || jsonb_build_object('prepare_candidates',v_part);
    end if;

    if to_regprocedure('pc_repair_unresolved_identity_candidates(uuid)') is not null then
        execute 'select pc_repair_unresolved_identity_candidates($1)' into v_part using p_ingestion_job_id;
        v_result := v_result || jsonb_build_object('repair_identities',v_part);
    end if;

    v_part := pc_apply_new_staged_entities(p_ingestion_job_id);
    v_result := v_result || jsonb_build_object('entities',v_part);

    v_part := pc_apply_new_staged_events(p_ingestion_job_id);
    v_result := v_result || jsonb_build_object('events',v_part);

    v_part := pc_register_job_aliases(p_ingestion_job_id);
    v_result := v_result || jsonb_build_object('aliases',v_part);

    -- First normal event-link and graph pass.
    if to_regprocedure('pc_process_relationship_backlog(uuid)') is not null then
        execute 'select pc_process_relationship_backlog($1)' into v_part using p_ingestion_job_id;
        v_result := v_result || jsonb_build_object('event_relationship_resolution',v_part);
    end if;

    if to_regprocedure('pc_process_generic_relationship_backlog(uuid)') is not null then
        execute 'select pc_process_generic_relationship_backlog($1)' into v_part using p_ingestion_job_id;
        v_result := v_result || jsonb_build_object('generic_relationship_resolution',v_part);
    end if;

    -- Expand malformed array links after dependencies are canonical.
    v_part := pc_expand_event_link_arrays(p_ingestion_job_id);
    v_result := v_result || jsonb_build_object('event_link_arrays',v_part);

    -- Apply only rows already deemed READY by existing resolvers.
    if to_regprocedure('pc_apply_ready_event_relationships(uuid)') is not null then
        execute 'select pc_apply_ready_event_relationships($1)' into v_part using p_ingestion_job_id;
        v_result := v_result || jsonb_build_object('event_links_applied',v_part);
    end if;

    if to_regprocedure('pc_apply_ready_generic_relationships(uuid)') is not null then
        execute 'select pc_apply_ready_generic_relationships($1)' into v_part using p_ingestion_job_id;
        v_result := v_result || jsonb_build_object('relationships_applied',v_part);
    end if;

    if to_regprocedure('pc_reconciliation_summary(uuid)') is not null then
        execute 'select pc_reconciliation_summary($1)' into v_part using p_ingestion_job_id;
        v_result := v_result || jsonb_build_object('summary',v_part);
    end if;

    return v_result;
end;
$$;

comment on function pc_reconcile_ingestion_job(uuid) is
'Dependency-aware ingestion reconciliation: normalize, resolve/apply safe entities and events, register natural-key aliases, expand array event links, resolve/apply READY relationships, and return a job summary.';

commit;
