
begin;

create or replace function pc_cleanup_staging_names(p_job_id uuid default null)
returns jsonb
language plpgsql
security definer
set search_path=public
as $$
declare
    v_updated integer := 0;
begin
    update pc_staged_records
       set payload=jsonb_set(
            coalesce(payload,'{}'::jsonb),
            '{name}',
            to_jsonb(coalesce(
                nullif(payload->>'name',''),
                nullif(payload->>'canonical_name',''),
                nullif(payload->>'entity_name',''),
                nullif(payload->>'vessel_name',''),
                nullif(payload->>'asset_name',''),
                nullif(payload->>'display_name',''),
                nullif(payload->>'title',''),
                natural_key
            )),
            true
       )
     where (p_job_id is null or ingestion_job_id=p_job_id)
       and target_table in ('pc_entities','pc_assets','pc_mobile_assets')
       and coalesce(payload->>'name','')='';

    get diagnostics v_updated=row_count;
    return jsonb_build_object('updated',v_updated);
end;
$$;

create or replace function pc_cleanup_staging_keys(p_job_id uuid default null)
returns jsonb
language plpgsql
security definer
set search_path=public
as $$
declare
    v_updated integer := 0;
begin
    update pc_staged_records s
       set payload =
         case s.target_table
           when 'pc_entities' then
             jsonb_set(coalesce(s.payload,'{}'::jsonb),'{entity_id}',
                to_jsonb(coalesce(nullif(s.payload->>'entity_id',''),'ENTITY_'||upper(substr(md5(coalesce(s.natural_key,s.staged_record_id::text)),1,16)))),true)
           when 'pc_assets' then
             jsonb_set(coalesce(s.payload,'{}'::jsonb),'{asset_id}',
                to_jsonb(coalesce(nullif(s.payload->>'asset_id',''),'ASSET_'||upper(substr(md5(coalesce(s.natural_key,s.staged_record_id::text)),1,16)))),true)
           when 'pc_mobile_assets' then
             jsonb_set(coalesce(s.payload,'{}'::jsonb),'{mobile_asset_id}',
                to_jsonb(coalesce(nullif(s.payload->>'mobile_asset_id',''),'MOBILE_'||upper(substr(md5(coalesce(s.natural_key,s.staged_record_id::text)),1,16)))),true)
           when 'pc_relationships' then
             jsonb_set(coalesce(s.payload,'{}'::jsonb),'{relationship_id}',
                to_jsonb(coalesce(nullif(s.payload->>'relationship_id',''),'REL_'||upper(substr(md5(coalesce(s.natural_key,s.staged_record_id::text)),1,24)))),true)
           when 'pc_events' then
             jsonb_set(coalesce(s.payload,'{}'::jsonb),'{event_id}',
                to_jsonb(coalesce(nullif(s.payload->>'event_id',''),'EVENT_'||upper(substr(md5(coalesce(s.natural_key,s.staged_record_id::text)),1,20)))),true)
           when 'pc_event_links' then
             jsonb_set(coalesce(s.payload,'{}'::jsonb),'{event_link_id}',
                to_jsonb(coalesce(nullif(s.payload->>'event_link_id',''),'EVLINK_'||upper(substr(md5(coalesce(s.natural_key,s.staged_record_id::text)),1,20)))),true)
           when 'pc_transactions' then
             jsonb_set(coalesce(s.payload,'{}'::jsonb),'{transaction_id}',
                to_jsonb(coalesce(nullif(s.payload->>'transaction_id',''),'TXN_'||upper(substr(md5(coalesce(s.natural_key,s.staged_record_id::text)),1,20)))),true)
           when 'pc_transport_routes' then
             jsonb_set(coalesce(s.payload,'{}'::jsonb),'{route_id}',
                to_jsonb(coalesce(nullif(s.payload->>'route_id',''),'ROUTE_'||upper(substr(md5(coalesce(s.natural_key,s.staged_record_id::text)),1,20)))),true)
           when 'pc_chokepoints' then
             jsonb_set(coalesce(s.payload,'{}'::jsonb),'{chokepoint_id}',
                to_jsonb(coalesce(nullif(s.payload->>'chokepoint_id',''),'CHOKE_'||upper(substr(md5(coalesce(s.natural_key,s.staged_record_id::text)),1,20)))),true)
           else s.payload
         end
     where (p_job_id is null or ingestion_job_id=p_job_id)
       and s.target_table in (
         'pc_entities','pc_assets','pc_mobile_assets','pc_relationships',
         'pc_events','pc_event_links','pc_transactions','pc_transport_routes','pc_chokepoints'
       );

    get diagnostics v_updated=row_count;
    return jsonb_build_object('updated',v_updated);
end;
$$;

create or replace function pc_reconciliation_summary(p_job_id uuid default null)
returns jsonb
language sql
security definer
set search_path=public
as $$
select jsonb_build_object(
    'total',count(*),
    'pending',count(*) filter (where coalesce(review_status,'pending')='pending'),
    'unresolved',count(*) filter (where coalesce(resolution_status,'UNRESOLVED')='UNRESOLVED'),
    'ambiguous',count(*) filter (where coalesce(resolution_status,'')='AMBIGUOUS'),
    'partial',count(*) filter (where coalesce(resolution_status,'')='PARTIAL'),
    'ready',count(*) filter (where coalesce(resolution_status,'') in ('READY','MATCHED','NEW')),
    'missing_name',count(*) filter (
        where target_table in ('pc_entities','pc_assets','pc_mobile_assets')
          and coalesce(payload->>'name','')=''
    )
)
from pc_staged_records
where p_job_id is null or ingestion_job_id=p_job_id;
$$;

create or replace view pc_v_reconciliation_queue as
select
    s.staged_record_id,
    s.ingestion_job_id,
    s.target_table,
    s.target_entity_type,
    s.natural_key,
    s.resolution_status,
    s.resolved_entity_id,
    s.resolution_method,
    s.confidence,
    s.validation_status,
    s.review_status,
    case
      when s.target_table in ('pc_entities','pc_assets','pc_mobile_assets')
       and coalesce(s.payload->>'name','')='' then 'MISSING_NAME'
      when coalesce(s.resolution_status,'UNRESOLVED')='UNRESOLVED' then 'UNRESOLVED'
      when coalesce(s.resolution_status,'')='AMBIGUOUS' then 'AMBIGUOUS'
      when coalesce(s.resolution_status,'')='PARTIAL' then 'PARTIAL_RELATIONSHIP'
      when coalesce(s.resolution_status,'')='BROKEN_REFERENCE' then 'BROKEN_REFERENCE'
      else 'REVIEW'
    end as cleanup_reason,
    s.payload,
    s.created_at
from pc_staged_records s
where coalesce(s.review_status,'pending') in ('pending','needs_changes')
order by s.created_at desc;

create or replace view pc_v_stale_ingestion_jobs as
select
    ingestion_job_id,
    job_type,
    title,
    status,
    created_at,
    updated_at,
    now()-coalesce(updated_at,created_at) as time_since_update,
    stats,
    error_text
from pc_ingestion_jobs
where status='running'
  and coalesce(updated_at,created_at) < now()-interval '45 minutes'
order by coalesce(updated_at,created_at);

create or replace function pc_run_standard_reconciliation(p_job_id uuid)
returns jsonb
language plpgsql
security definer
set search_path=public
as $$
declare
    v_result jsonb := '{}'::jsonb;
    v_part jsonb;
begin
    v_part:=pc_cleanup_staging_names(p_job_id);
    v_result:=v_result||jsonb_build_object('names',v_part);

    v_part:=pc_cleanup_staging_keys(p_job_id);
    v_result:=v_result||jsonb_build_object('keys',v_part);

    if to_regprocedure('pc_prepare_canonical_candidates(uuid)') is not null then
        execute 'select pc_prepare_canonical_candidates($1)' into v_part using p_job_id;
        v_result:=v_result||jsonb_build_object('prepare_candidates',v_part);
    end if;

    if to_regprocedure('pc_repair_unresolved_identity_candidates(uuid)') is not null then
        execute 'select pc_repair_unresolved_identity_candidates($1)' into v_part using p_job_id;
        v_result:=v_result||jsonb_build_object('repair_identities',v_part);
    end if;

    if to_regprocedure('pc_process_relationship_backlog(uuid)') is not null then
        execute 'select pc_process_relationship_backlog($1)' into v_part using p_job_id;
        v_result:=v_result||jsonb_build_object('event_relationships',v_part);
    end if;

    if to_regprocedure('pc_process_generic_relationship_backlog(uuid)') is not null then
        execute 'select pc_process_generic_relationship_backlog($1)' into v_part using p_job_id;
        v_result:=v_result||jsonb_build_object('generic_relationships',v_part);
    end if;

    v_part:=pc_reconciliation_summary(p_job_id);
    v_result:=v_result||jsonb_build_object('summary',v_part);

    return v_result;
end;
$$;

comment on function pc_run_standard_reconciliation(uuid) is
'Job-scoped repeatable cleanup pipeline: normalize names, fill deterministic staging keys, prepare/re-resolve identities and relationship endpoints, then return a summary.';

commit;
