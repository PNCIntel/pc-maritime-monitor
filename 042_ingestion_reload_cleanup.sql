-- Power & Corridors
-- 042_ingestion_reload_cleanup.sql
-- Purpose: archive and clear ONLY ingestion/workflow state so researched Excel files can be reloaded cleanly.
-- Canonical tables (pc_entities, pc_assets, pc_mobile_assets, pc_events, pc_relationships, pc_event_links, etc.) are NOT deleted.
-- Run 041 first.

begin;

create table if not exists public.pc_ingestion_archive (
    archive_id bigserial primary key,
    archived_at timestamptz not null default now(),
    ingestion_job_id uuid,
    record_kind text not null,
    record_data jsonb not null
);
create index if not exists idx_pc_ingestion_archive_job on public.pc_ingestion_archive(ingestion_job_id,archived_at);

create or replace function public.pc_archive_reset_ingestion_job(p_job_id uuid)
returns jsonb
language plpgsql
security definer
set search_path=public
as $$
declare
    v_staged int:=0; v_workflow int:=0; v_maps int:=0; v_rel int:=0; v_logs int:=0;
begin
    -- Archive key workflow objects before clearing them.
    insert into pc_ingestion_archive(ingestion_job_id,record_kind,record_data)
    select p_job_id,'pc_ingestion_jobs',to_jsonb(j) from pc_ingestion_jobs j where ingestion_job_id=p_job_id;

    insert into pc_ingestion_archive(ingestion_job_id,record_kind,record_data)
    select p_job_id,'pc_staged_records',to_jsonb(s) from pc_staged_records s where ingestion_job_id=p_job_id;
    get diagnostics v_staged = row_count;

    insert into pc_ingestion_archive(ingestion_job_id,record_kind,record_data)
    select p_job_id,'pc_workflow_runs',to_jsonb(w) from pc_workflow_runs w where ingestion_job_id=p_job_id;
    get diagnostics v_workflow = row_count;

    -- Optional tables vary by deployment; delete dynamically only when present.
    if to_regclass('public.pc_staged_relationships') is not null then
        execute 'insert into public.pc_ingestion_archive(ingestion_job_id,record_kind,record_data) '
             || 'select $1,''pc_staged_relationships'',to_jsonb(x) from public.pc_staged_relationships x where ingestion_job_id=$1'
        using p_job_id;
        execute 'delete from public.pc_staged_relationships where ingestion_job_id=$1' using p_job_id;
        get diagnostics v_rel = row_count;
    end if;

    if to_regclass('public.pc_resolution_log') is not null then
        execute 'insert into public.pc_ingestion_archive(ingestion_job_id,record_kind,record_data) '
             || 'select $1,''pc_resolution_log'',to_jsonb(x) from public.pc_resolution_log x where ingestion_job_id=$1'
        using p_job_id;
        execute 'delete from public.pc_resolution_log where ingestion_job_id=$1' using p_job_id;
        get diagnostics v_logs = row_count;
    end if;

    delete from pc_ingestion_key_map where ingestion_job_id=p_job_id;
    get diagnostics v_maps = row_count;
    delete from pc_workflow_runs where ingestion_job_id=p_job_id;
    delete from pc_staged_records where ingestion_job_id=p_job_id;

    update pc_ingestion_jobs
       set status='archived', started_at=null, completed_at=now(), error_text=null
     where ingestion_job_id=p_job_id;

    return jsonb_build_object('job_id',p_job_id,'archived_staged',v_staged,'archived_workflow',v_workflow,
                              'cleared_key_maps',v_maps,'cleared_staged_relationships',v_rel,'cleared_resolution_log',v_logs,
                              'canonical_data_deleted',false);
end;
$$;

-- Archive/reset every BATCH_IMPORT or AI_RESEARCH job matching a title fragment.
create or replace function public.pc_archive_reset_ingestion_jobs_by_title(p_title_fragment text)
returns jsonb
language plpgsql
security definer
set search_path=public
as $$
declare
    r record; v_count int:=0; v_results jsonb:='[]'::jsonb;
begin
    for r in
        select ingestion_job_id,title
          from pc_ingestion_jobs
         where upper(coalesce(job_type,'')) in ('BATCH_IMPORT','AI_RESEARCH')
           and lower(title) like '%'||lower(p_title_fragment)||'%'
         order by created_at
    loop
        v_results := v_results || jsonb_build_array(pc_archive_reset_ingestion_job(r.ingestion_job_id));
        v_count:=v_count+1;
    end loop;
    return jsonb_build_object('matched_jobs',v_count,'results',v_results);
end;
$$;

grant execute on function public.pc_archive_reset_ingestion_job(uuid) to authenticated;
grant execute on function public.pc_archive_reset_ingestion_jobs_by_title(text) to authenticated;

commit;

-- Examples (DO NOT run blindly):
-- select public.pc_archive_reset_ingestion_jobs_by_title('COSCO Heavy Industry');
-- select public.pc_archive_reset_ingestion_jobs_by_title('700');
-- select public.pc_archive_reset_ingestion_jobs_by_title('OSV');
-- select public.pc_archive_reset_ingestion_jobs_by_title('24H');
-- Then reload the spreadsheets. Canonical rows remain and 041 will UPSERT/enrich them.
