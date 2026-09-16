-- Power & Corridors
-- 055_verify_and_retry_deferred_apply.sql
-- Run AFTER 054_fix_deferred_canonical_apply.sql
-- This proves which function version is active and retries the latest unresolved canonical package.

-- 1) Verify installed function body contains the v21 marker.
select
    p.proname as function_name,
    case
        when pg_get_functiondef(p.oid) like '%sql_v21_transaction_participant_apply%'
         and pg_get_functiondef(p.oid) like '%sql_v21_event_link_apply%'
        then 'V21_ACTIVE'
        when pg_get_functiondef(p.oid) like '%sql_v20_deferred_apply_error%'
        then 'OLD_V20_ACTIVE'
        else 'UNKNOWN_VERSION'
    end as deferred_function_version
from pg_proc p
join pg_namespace n on n.oid = p.pronamespace
where n.nspname='public'
  and p.proname='pc_apply_deferred_canonical_job_v1';

-- 2) Retry the most recent package that still has unresolved transaction participants/event links.
with latest_job as (
    select ingestion_job_id
    from pc_staged_records
    where target_table in ('pc_transaction_participants','pc_event_links')
      and review_status <> 'applied'
    order by created_at desc
    limit 1
)
select pc_apply_deferred_canonical_job_v1(ingestion_job_id) as retry_result
from latest_job;

-- 3) Show exact post-retry status and actual SQL reason, if any.
with latest_job as (
    select ingestion_job_id
    from pc_staged_records
    where target_table in ('pc_transaction_participants','pc_event_links')
    order by created_at desc
    limit 1
)
select
    target_table,
    natural_key,
    resolution_status,
    review_status,
    resolution_method,
    resolution_details->>'sqlstate' as sqlstate,
    resolution_details->>'reason' as exact_reason
from pc_staged_records
where ingestion_job_id=(select ingestion_job_id from latest_job)
order by target_table,natural_key;
