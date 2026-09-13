begin;

create or replace view pc_v_stale_ingestion_jobs as
select
    ingestion_job_id,
    job_type,
    title,
    status,
    created_at,
    now()-created_at as time_since_update,
    stats,
    error_text
from pc_ingestion_jobs
where status='running'
  and created_at < now()-interval '45 minutes'
order by created_at;

commit;
