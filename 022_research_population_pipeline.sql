-- Power & Corridors Trade System
-- 022_research_population_pipeline.sql
-- Unified, staging-first population preparation for company research jobs.
--
-- Goal:
--   One deterministic server-side preparation pass after AI/web research:
--     1) normalize staged identity rows
--     2) classify identities MATCHED / NEW / AMBIGUOUS
--     3) assign deterministic candidate IDs to NEW identities
--     4) stage every pc_relationships proposal into pc_staged_relationships
--     5) resolve both relationship endpoints
--     6) report exceptions instead of silently dropping them
--
-- IMPORTANT:
--   This function does NOT automatically write researched entities/assets/vessels
--   or relationships into canonical business tables. Analyst approval/apply remains
--   the controlled write boundary.

begin;

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
        select 1 from pc_ingestion_jobs
        where ingestion_job_id=p_ingestion_job_id
    ) then
        raise exception 'Unknown ingestion job %',p_ingestion_job_id;
    end if;

    -- -----------------------------------------------------------------------
    -- A. Normalize staged rows without changing canonical data.
    -- -----------------------------------------------------------------------
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

    -- -----------------------------------------------------------------------
    -- B. Identity decision + candidate-ID generation.
    -- SQL 019 owns the deterministic MATCHED/NEW logic.
    -- -----------------------------------------------------------------------
    begin
        v_identity_result :=
            pc_repair_unresolved_identity_candidates(p_ingestion_job_id);
    exception when undefined_function then
        raise exception
            'pc_repair_unresolved_identity_candidates(uuid) is missing. Run SQL 019 before SQL 022.';
    end;

    -- -----------------------------------------------------------------------
    -- C. Stage and resolve all generic graph proposals.
    -- This includes company->company, company->asset, entity->vessel, etc.
    -- -----------------------------------------------------------------------
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
                           'population_pipeline_sql','022'
                         )
             where staged_record_id=r.staged_record_id;
        end;
    end loop;

    -- Event-link proposals continue to use the specialized resolver where present.
    if exists (
        select 1 from pc_staged_records
        where ingestion_job_id=p_ingestion_job_id
          and target_table='pc_event_links'
          and coalesce(review_status,'pending') not in ('rejected','applied')
    ) then
        begin
            perform pc_process_relationship_backlog(p_ingestion_job_id);
        exception when undefined_function then
            null;
        end;
    end if;

    -- -----------------------------------------------------------------------
    -- D. Job-level status counts.
    -- -----------------------------------------------------------------------
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

    -- Required semantic classifiers. These should normally be supplied by the
    -- research output contract; remaining gaps are explicit review exceptions.
    select count(*) into v_semantic_missing
      from pc_staged_records
     where ingestion_job_id=p_ingestion_job_id
       and coalesce(review_status,'pending') <> 'rejected'
       and (
            (target_table='pc_entities'
             and coalesce(nullif(payload->>'entity_type',''),'')='')
         or (target_table='pc_assets'
             and coalesce(nullif(payload->>'asset_type',''),'')='')
         or (target_table='pc_mobile_assets'
             and coalesce(nullif(payload->>'asset_type',''),'')='')
         or (target_table='pc_events'
             and coalesce(nullif(payload->>'event_type',''),'')='')
       );

    -- Relationship endpoint names are mandatory for research populations.
    select count(*) into v_missing_relationship_names
      from pc_staged_records
     where ingestion_job_id=p_ingestion_job_id
       and target_table='pc_relationships'
       and coalesce(review_status,'pending') <> 'rejected'
       and (
            coalesce(nullif(payload->>'source_name',''),
                     nullif(payload->>'from_name','')) is null
         or coalesce(nullif(payload->>'target_name',''),
                     nullif(payload->>'to_name','')) is null
       );

    v_pipeline := jsonb_build_object(
        'job_id',p_ingestion_job_id,
        'total_staged_records',v_total_records,
        'identity_records',v_identity_records,
        'identity',jsonb_build_object(
            'matched',v_matched,
            'new',v_new,
            'ambiguous',v_ambiguous,
            'invalid',v_invalid,
            'unresolved',v_unresolved,
            'repair',v_identity_result
        ),
        'relationships',jsonb_build_object(
            'staged',v_relationship_records,
            'ready',v_ready,
            'partial',v_partial,
            'ambiguous',v_rel_ambiguous,
            'broken',v_broken,
            'already_exists',v_already_exists
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


create or replace view pc_v_population_pipeline_status as
select
    j.ingestion_job_id,
    j.title,
    j.job_type,
    j.status as job_status,
    j.created_at,
    count(s.staged_record_id) filter (
        where coalesce(s.review_status,'pending') <> 'rejected'
    ) as staged_records,

    count(s.staged_record_id) filter (
        where s.resolution_status='MATCHED'
    ) as matched_records,

    count(s.staged_record_id) filter (
        where s.resolution_status='NEW'
    ) as new_records,

    count(s.staged_record_id) filter (
        where s.resolution_status='AMBIGUOUS'
    ) as ambiguous_records,

    count(s.staged_record_id) filter (
        where coalesce(s.resolution_status,'UNRESOLVED')='UNRESOLVED'
          and s.target_table not in ('pc_relationships','pc_event_links','research_bundle')
    ) as unresolved_identity_records,

    count(distinct sr.staged_relationship_id) as staged_relationships,

    count(distinct sr.staged_relationship_id) filter (
        where sr.resolution_status='READY'
    ) as ready_relationships,

    count(distinct sr.staged_relationship_id) filter (
        where sr.resolution_status='PARTIAL'
    ) as partial_relationships,

    count(distinct sr.staged_relationship_id) filter (
        where sr.resolution_status='ALREADY_EXISTS'
    ) as existing_relationships,

    count(distinct sr.staged_relationship_id) filter (
        where sr.resolution_status in ('AMBIGUOUS','BROKEN_REFERENCE')
    ) as relationship_exceptions

from pc_ingestion_jobs j
left join pc_staged_records s
    on s.ingestion_job_id=j.ingestion_job_id
left join pc_staged_relationships sr
    on sr.ingestion_job_id=j.ingestion_job_id
group by
    j.ingestion_job_id,j.title,j.job_type,j.status,j.created_at;


comment on function pc_prepare_research_population(uuid) is
'Unified staging-first population preparation: identity classification/candidate IDs plus generic relationship staging/resolution and explicit exception counts. Does not apply canonical writes.';

comment on view pc_v_population_pipeline_status is
'Job-level research-population preparation status for Power Admin.';

commit;
