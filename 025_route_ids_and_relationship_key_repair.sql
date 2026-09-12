-- Power & Corridors Trade System
-- 025_route_ids_and_relationship_key_repair.sql
-- Completes candidate IDs for researched transport routes and repairs malformed
-- fleet/corporate relationship natural keys caused by case-sensitive slug generation.
-- Staging only except for function definitions/views; no canonical business rows are inserted.

begin;

-- ---------------------------------------------------------------------------
-- 1. Deterministic candidate IDs for staged transport routes.
-- ---------------------------------------------------------------------------

create or replace function pc_prepare_transport_route_candidates(
    p_ingestion_job_id uuid
)
returns jsonb
language plpgsql
security definer
set search_path=public
as $$
declare
    r record;
    v_payload jsonb;
    v_id text;
    v_total integer := 0;
    v_prepared integer := 0;
begin
    for r in
        select *
        from pc_staged_records
        where ingestion_job_id=p_ingestion_job_id
          and target_table='pc_transport_routes'
          and coalesce(review_status,'pending') not in ('rejected','applied')
    loop
        v_total := v_total + 1;
        v_payload := coalesce(r.payload,'{}'::jsonb);
        v_id := nullif(trim(v_payload->>'route_id'),'');

        if v_id is null then
            v_id := 'ROUTE_' || upper(substr(md5(
                coalesce(nullif(r.natural_key,''),r.staged_record_id::text)
            ),1,16));

            v_payload := jsonb_set(v_payload,'{route_id}',to_jsonb(v_id),true);

            update pc_staged_records
               set payload=v_payload,
                   resolution_status=case
                       when coalesce(resolution_status,'UNRESOLVED') in ('UNRESOLVED','INVALID')
                       then 'NEW'
                       else resolution_status
                   end,
                   resolution_method=case
                       when coalesce(resolution_method,'')='' then 'NO_CANONICAL_MATCH'
                       else resolution_method
                   end,
                   resolution_confidence=coalesce(resolution_confidence,1.0),
                   validation_status=case when validation_status='invalid' then 'pending' else validation_status end,
                   resolution_details=coalesce(resolution_details,'{}'::jsonb)
                     || jsonb_build_object(
                          'candidate_kind','NEW',
                          'candidate_id',v_id,
                          'candidate_preparer','SQL025'
                        )
             where staged_record_id=r.staged_record_id;

            begin
                perform pc_expand_staged_payload(r.staged_record_id);
            exception when undefined_function then
                null;
            end;

            v_prepared := v_prepared + 1;
        end if;
    end loop;

    return jsonb_build_object(
        'job_id',p_ingestion_job_id,
        'routes_seen',v_total,
        'route_ids_prepared',v_prepared
    );
end;
$$;


-- ---------------------------------------------------------------------------
-- 2. Repair malformed natural keys already staged by SQL020/024.
--    The original slug expression used [a-z0-9] against potentially uppercase
--    normalized names, producing corp___parent_of___ / fleet___operates__.
-- ---------------------------------------------------------------------------

update pc_staged_records
   set natural_key =
       'fleet_' ||
       regexp_replace(lower(pc_normalize_name(
           coalesce(payload->>'source_name',payload->>'from_name','source')
       )),'[^a-z0-9]+','_','g') ||
       '_' || lower(coalesce(payload->>'relationship_type','operates')) || '_' ||
       regexp_replace(lower(pc_normalize_name(
           coalesce(payload->>'target_name',payload->>'to_name','target')
       )),'[^a-z0-9]+','_','g'),
       source_record_key =
       'fleet_' ||
       regexp_replace(lower(pc_normalize_name(
           coalesce(payload->>'source_name',payload->>'from_name','source')
       )),'[^a-z0-9]+','_','g') ||
       '_' || lower(coalesce(payload->>'relationship_type','operates')) || '_' ||
       regexp_replace(lower(pc_normalize_name(
           coalesce(payload->>'target_name',payload->>'to_name','target')
       )),'[^a-z0-9]+','_','g')
 where target_table='pc_relationships'
   and natural_key like 'fleet_%'
   and (
       natural_key ~ '^fleet_+[^a-z0-9]*operates_*$'
       or natural_key in ('fleet___operates__','fleet___owns__','fleet___manages__','fleet___charters__')
   );

update pc_staged_records
   set natural_key =
       'corp_' ||
       regexp_replace(lower(pc_normalize_name(
           coalesce(payload->>'source_name',payload->>'from_name','source')
       )),'[^a-z0-9]+','_','g') ||
       '_' || lower(coalesce(payload->>'relationship_type','related_to')) || '_' ||
       regexp_replace(lower(pc_normalize_name(
           coalesce(payload->>'target_name',payload->>'to_name','target')
       )),'[^a-z0-9]+','_','g'),
       source_record_key =
       'corp_' ||
       regexp_replace(lower(pc_normalize_name(
           coalesce(payload->>'source_name',payload->>'from_name','source')
       )),'[^a-z0-9]+','_','g') ||
       '_' || lower(coalesce(payload->>'relationship_type','related_to')) || '_' ||
       regexp_replace(lower(pc_normalize_name(
           coalesce(payload->>'target_name',payload->>'to_name','target')
       )),'[^a-z0-9]+','_','g')
 where target_table='pc_relationships'
   and natural_key like 'corp_%'
   and natural_key like '%___%';


-- ---------------------------------------------------------------------------
-- 3. Rebuild SQL024 fleet-link staging function with safe lowercase slugs.
-- ---------------------------------------------------------------------------

create or replace function pc_stage_missing_mobile_asset_links(
    p_ingestion_job_id uuid,
    p_company_name text,
    p_relationship_type text default 'operates'
)
returns jsonb
language plpgsql
security definer
set search_path=public
as $$
declare
    r record;
    v_payload jsonb;
    v_natural_key text;
    v_staged_record_id uuid;
    v_staged_relationship_id uuid;
    v_resolution jsonb;
    v_total integer := 0;
    v_staged integer := 0;
    v_skipped_existing integer := 0;
    v_skipped_no_source integer := 0;
    v_rel text;
begin
    if p_ingestion_job_id is null then
        raise exception 'p_ingestion_job_id is required';
    end if;
    if coalesce(trim(p_company_name),'')='' then
        raise exception 'p_company_name is required';
    end if;

    v_rel := lower(trim(coalesce(p_relationship_type,'operates')));
    if v_rel not in ('operates','owns','manages','charters') then
        raise exception 'Unsupported mobile asset relationship_type: %',v_rel;
    end if;

    for r in
        select *
        from pc_v_population_mobile_asset_coverage
        where ingestion_job_id=p_ingestion_job_id
        order by mobile_asset_name
    loop
        v_total := v_total + 1;

        if r.has_company_link then
            v_skipped_existing := v_skipped_existing + 1;
            continue;
        end if;

        if coalesce(jsonb_array_length(
            case
                when jsonb_typeof(r.metadata->'research_sources')='array'
                then r.metadata->'research_sources'
                else '[]'::jsonb
            end
        ),0)=0 and r.source_id is null then
            v_skipped_no_source := v_skipped_no_source + 1;
            continue;
        end if;

        v_natural_key :=
            'fleet_' ||
            trim(both '_' from regexp_replace(
                lower(pc_normalize_name(p_company_name)),
                '[^a-z0-9]+','_','g'
            )) ||
            '_' || v_rel || '_' ||
            trim(both '_' from regexp_replace(
                lower(pc_normalize_name(r.mobile_asset_name)),
                '[^a-z0-9]+','_','g'
            ));

        v_payload := jsonb_strip_nulls(jsonb_build_object(
            'source_type','entity',
            'source_name',p_company_name,
            'relationship_type',v_rel,
            'target_type','mobile_asset',
            'target_name',r.mobile_asset_name,
            'target_id',r.mobile_asset_id,
            'evidence_source_id',r.source_id,
            'metadata',coalesce(r.metadata,'{}'::jsonb) || jsonb_build_object(
                'relationship_family','fleet',
                'generated_from_mobile_asset_staging',true,
                'source_mobile_staged_record_id',r.staged_record_id
            )
        ));

        select staged_record_id
          into v_staged_record_id
          from pc_staged_records
         where ingestion_job_id=p_ingestion_job_id
           and target_table='pc_relationships'
           and natural_key=v_natural_key
           and coalesce(review_status,'pending') not in ('rejected','applied')
         order by created_at desc
         limit 1;

        if v_staged_record_id is null then
            insert into pc_staged_records(
                ingestion_job_id,target_table,source_record_key,natural_key,action,payload,
                confidence,validation_status,review_status,resolution_status
            )
            values (
                p_ingestion_job_id,'pc_relationships',v_natural_key,v_natural_key,'REVIEW',v_payload,
                coalesce(r.confidence,0.95),'pending','pending','UNRESOLVED'
            )
            returning staged_record_id into v_staged_record_id;
        else
            update pc_staged_records
               set payload=v_payload,
                   source_record_key=v_natural_key,
                   validation_status='pending',
                   review_status='pending',
                   resolution_status='UNRESOLVED'
             where staged_record_id=v_staged_record_id;
        end if;

        v_staged_relationship_id := pc_stage_generic_relationship(v_staged_record_id);
        v_resolution := pc_resolve_generic_relationship(v_staged_relationship_id);
        v_staged := v_staged + 1;
    end loop;

    return jsonb_build_object(
        'job_id',p_ingestion_job_id,
        'company_name',p_company_name,
        'relationship_type',v_rel,
        'mobile_assets_seen',v_total,
        'fleet_links_staged',v_staged,
        'skipped_existing_link',v_skipped_existing,
        'skipped_no_source',v_skipped_no_source
    );
end;
$$;


-- ---------------------------------------------------------------------------
-- 4. Extend unified population preparation so route IDs are completed too.
-- ---------------------------------------------------------------------------

create or replace function pc_prepare_research_population(
    p_ingestion_job_id uuid
)
returns jsonb
language plpgsql
security definer
set search_path=public
as $$
declare
    r record;
    v_rel_id uuid;
    v_rel_result jsonb;
    v_identity_result jsonb := '{}'::jsonb;
    v_route_result jsonb := '{}'::jsonb;

    v_total_records integer := 0;
    v_identity_records integer := 0;
    v_relationship_records integer := 0;

    v_matched integer := 0;
    v_new integer := 0;
    v_ambiguous integer := 0;
    v_invalid integer := 0;
    v_unresolved integer := 0;

    v_ready integer := 0;
    v_partial integer := 0;
    v_rel_ambiguous integer := 0;
    v_broken integer := 0;
    v_already_exists integer := 0;

    v_semantic_missing integer := 0;
    v_missing_relationship_names integer := 0;
    v_pipeline jsonb;
begin
    if p_ingestion_job_id is null then
        raise exception 'p_ingestion_job_id is required';
    end if;

    if not exists (
        select 1 from pc_ingestion_jobs where ingestion_job_id=p_ingestion_job_id
    ) then
        raise exception 'Unknown ingestion job %',p_ingestion_job_id;
    end if;

    update pc_staged_records s
       set review_status=coalesce(s.review_status,'pending'),
           source_record_key=coalesce(nullif(s.source_record_key,''),s.natural_key,s.staged_record_id::text)
     where s.ingestion_job_id=p_ingestion_job_id
       and coalesce(s.review_status,'pending') not in ('rejected','applied');

    update pc_staged_records s
       set target_entity_type=m.entity_type
      from pc_meta_entity_types m
     where s.ingestion_job_id=p_ingestion_job_id
       and coalesce(s.review_status,'pending') not in ('rejected','applied')
       and m.active
       and m.table_name=s.target_table
       and coalesce(s.target_entity_type,'')='';

    v_identity_result := pc_repair_unresolved_identity_candidates(p_ingestion_job_id);
    v_route_result := pc_prepare_transport_route_candidates(p_ingestion_job_id);

    for r in
        select staged_record_id
        from pc_staged_records
        where ingestion_job_id=p_ingestion_job_id
          and target_table='pc_relationships'
          and coalesce(review_status,'pending') not in ('rejected','applied')
        order by created_at,staged_record_id
    loop
        begin
            v_rel_id := pc_stage_generic_relationship(r.staged_record_id);
            v_rel_result := pc_resolve_generic_relationship(v_rel_id);
        exception when others then
            update pc_staged_records
               set validation_status='needs_review',
                   resolution_details=coalesce(resolution_details,'{}'::jsonb)
                     || jsonb_build_object(
                          'population_pipeline_error',sqlerrm,
                          'population_pipeline_sql','025'
                        )
             where staged_record_id=r.staged_record_id;
        end;
    end loop;

    begin
        perform pc_process_relationship_backlog(p_ingestion_job_id);
    exception when undefined_function then
        null;
    end;

    select count(*) into v_total_records
      from pc_staged_records
     where ingestion_job_id=p_ingestion_job_id
       and coalesce(review_status,'pending') <> 'rejected';

    select count(*) into v_identity_records
      from pc_staged_records s
     where s.ingestion_job_id=p_ingestion_job_id
       and coalesce(s.review_status,'pending') <> 'rejected'
       and exists (
           select 1 from pc_meta_entity_types m
           where m.active and m.table_name=s.target_table
       );

    select count(*) filter (where resolution_status='MATCHED'),
           count(*) filter (where resolution_status='NEW'),
           count(*) filter (where resolution_status='AMBIGUOUS'),
           count(*) filter (where resolution_status='INVALID'),
           count(*) filter (where coalesce(resolution_status,'UNRESOLVED')='UNRESOLVED')
      into v_matched,v_new,v_ambiguous,v_invalid,v_unresolved
      from pc_staged_records s
     where s.ingestion_job_id=p_ingestion_job_id
       and coalesce(s.review_status,'pending') <> 'rejected'
       and exists (
           select 1 from pc_meta_entity_types m
           where m.active and m.table_name=s.target_table
       );

    select count(*) into v_relationship_records
      from pc_staged_relationships
     where ingestion_job_id=p_ingestion_job_id;

    select count(*) filter (where resolution_status='READY'),
           count(*) filter (where resolution_status='PARTIAL'),
           count(*) filter (where resolution_status='AMBIGUOUS'),
           count(*) filter (where resolution_status='BROKEN_REFERENCE'),
           count(*) filter (where resolution_status='ALREADY_EXISTS')
      into v_ready,v_partial,v_rel_ambiguous,v_broken,v_already_exists
      from pc_staged_relationships
     where ingestion_job_id=p_ingestion_job_id;

    select count(*) into v_semantic_missing
      from pc_staged_records
     where ingestion_job_id=p_ingestion_job_id
       and coalesce(review_status,'pending') <> 'rejected'
       and (
            (target_table='pc_entities' and coalesce(nullif(payload->>'entity_type',''),'')='')
         or (target_table='pc_assets' and coalesce(nullif(payload->>'asset_type',''),'')='')
         or (target_table='pc_mobile_assets' and coalesce(nullif(payload->>'asset_type',''),'')='')
         or (target_table='pc_events' and coalesce(nullif(payload->>'event_type',''),'')='')
       );

    select count(*) into v_missing_relationship_names
      from pc_staged_records
     where ingestion_job_id=p_ingestion_job_id
       and target_table='pc_relationships'
       and coalesce(review_status,'pending') <> 'rejected'
       and (
            coalesce(nullif(payload->>'source_name',''),nullif(payload->>'from_name','')) is null
         or coalesce(nullif(payload->>'target_name',''),nullif(payload->>'to_name','')) is null
       );

    v_pipeline := jsonb_build_object(
        'job_id',p_ingestion_job_id,
        'total_staged_records',v_total_records,
        'identity_records',v_identity_records,
        'identity',jsonb_build_object(
            'matched',v_matched,'new',v_new,'ambiguous',v_ambiguous,
            'invalid',v_invalid,'unresolved',v_unresolved,'repair',v_identity_result
        ),
        'routes',v_route_result,
        'relationships',jsonb_build_object(
            'staged',v_relationship_records,'ready',v_ready,'partial',v_partial,
            'ambiguous',v_rel_ambiguous,'broken',v_broken,'already_exists',v_already_exists
        ),
        'exceptions',jsonb_build_object(
            'semantic_missing',v_semantic_missing,
            'relationship_endpoint_names_missing',v_missing_relationship_names
        ),
        'canonical_writes',false
    );

    update pc_ingestion_jobs
       set stats=coalesce(stats,'{}'::jsonb)
         || jsonb_build_object('population_pipeline',v_pipeline)
     where ingestion_job_id=p_ingestion_job_id;

    return v_pipeline;
end;
$$;

comment on function pc_prepare_transport_route_candidates(uuid) is
'Assigns deterministic staging route_ids to researched pc_transport_routes rows so NEW routes can pass schema review without canonical writes.';

comment on function pc_prepare_research_population(uuid) is
'SQL025 unified staging preparation: identities, route candidate IDs, relationship resolution, and exception counts.';

commit;
