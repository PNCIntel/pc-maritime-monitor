-- Power & Corridors
-- 051_reset_unresolved_review_queue.sql
--
-- PURPOSE
-- Clean out old unresolved / pending staging records across the canonical ingestion
-- system so the review queue starts fresh, WITHOUT deleting canonical data that has
-- already been applied to pc_entities / pc_assets / pc_mobile_assets / pc_events /
-- pc_event_links / pc_relationships.
--
-- WHAT THIS DOES
-- 1. Archives every non-applied row from pc_staged_records into a generic JSON archive.
-- 2. Deletes those non-applied staging rows.
-- 3. Archives + clears unresolved rows from pc_staged_relationships where present.
-- 4. Closes old ingestion/workflow jobs that no longer have unresolved staging rows.
-- 5. Leaves canonical tables untouched.
--
-- SAFE TO RE-RUN.
--
-- IMPORTANT
-- This is intentionally a "start fresh" reset for review/staging state. It assumes
-- the canonical records you care about are already loaded/applied, as requested.

begin;

-- -------------------------------------------------------------------
-- Generic archive table for reset operations
-- -------------------------------------------------------------------
create table if not exists public.pc_ingestion_reset_archive (
    archive_id uuid primary key default gen_random_uuid(),
    reset_batch_id uuid not null,
    source_table text not null,
    ingestion_job_id uuid null,
    staged_record_id uuid null,
    archived_at timestamptz not null default now(),
    archive_reason text not null,
    row_data jsonb not null
);

create index if not exists idx_pc_ingestion_reset_archive_batch
    on public.pc_ingestion_reset_archive(reset_batch_id);

create index if not exists idx_pc_ingestion_reset_archive_job
    on public.pc_ingestion_reset_archive(ingestion_job_id);

-- One batch id for this reset run.
do $$
declare
    v_batch uuid := gen_random_uuid();
    v_count bigint := 0;
begin
    raise notice 'P&C unresolved reset batch: %', v_batch;

    -- ---------------------------------------------------------------
    -- 1. Archive all non-applied staged records
    -- ---------------------------------------------------------------
    if to_regclass('public.pc_staged_records') is not null then
        insert into public.pc_ingestion_reset_archive(
            reset_batch_id,
            source_table,
            ingestion_job_id,
            staged_record_id,
            archive_reason,
            row_data
        )
        select
            v_batch,
            'pc_staged_records',
            s.ingestion_job_id,
            s.staged_record_id,
            'START_FRESH_RESET_NON_APPLIED',
            to_jsonb(s)
        from public.pc_staged_records s
        where coalesce(lower(s.review_status),'pending') <> 'applied';

        get diagnostics v_count = row_count;
        raise notice 'Archived % non-applied pc_staged_records rows', v_count;

        delete from public.pc_staged_records s
        where coalesce(lower(s.review_status),'pending') <> 'applied';

        get diagnostics v_count = row_count;
        raise notice 'Deleted % non-applied pc_staged_records rows', v_count;
    end if;

    -- ---------------------------------------------------------------
    -- 2. Archive + clear pc_staged_relationships when present
    --    This table is staging-only; canonical relationships live in
    --    pc_relationships and are not touched here.
    -- ---------------------------------------------------------------
    if to_regclass('public.pc_staged_relationships') is not null then
        execute format($q$
            insert into public.pc_ingestion_reset_archive(
                reset_batch_id,
                source_table,
                ingestion_job_id,
                staged_record_id,
                archive_reason,
                row_data
            )
            select
                %L::uuid,
                'pc_staged_relationships',
                case
                    when to_jsonb(r) ? 'ingestion_job_id'
                    then nullif(to_jsonb(r)->>'ingestion_job_id','')::uuid
                    else null
                end,
                null,
                'START_FRESH_RESET_STAGED_RELATIONSHIP',
                to_jsonb(r)
            from public.pc_staged_relationships r
        $q$, v_batch);

        execute 'delete from public.pc_staged_relationships';
        get diagnostics v_count = row_count;
        raise notice 'Deleted % pc_staged_relationships rows', v_count;
    end if;

    -- ---------------------------------------------------------------
    -- 3. Close ingestion jobs that no longer have unresolved rows
    -- ---------------------------------------------------------------
    if to_regclass('public.pc_ingestion_jobs') is not null then
        update public.pc_ingestion_jobs j
        set
            status = case
                when exists (
                    select 1
                    from public.pc_staged_records s
                    where s.ingestion_job_id=j.ingestion_job_id
                      and lower(coalesce(s.review_status,''))='applied'
                ) then 'completed'
                else 'reset'
            end,
            completed_at = coalesce(j.completed_at, now()),
            stats = coalesce(j.stats,'{}'::jsonb)
                    || jsonb_build_object(
                        'review_queue_reset', true,
                        'review_queue_reset_at', now(),
                        'review_queue_reset_batch', v_batch
                    ),
            error_text = null
        where coalesce(lower(j.status),'') not in ('completed','reset')
          and not exists (
              select 1
              from public.pc_staged_records s
              where s.ingestion_job_id=j.ingestion_job_id
                and coalesce(lower(s.review_status),'pending') <> 'applied'
          );

        get diagnostics v_count = row_count;
        raise notice 'Closed/reset % ingestion jobs', v_count;
    end if;

    -- ---------------------------------------------------------------
    -- 4. Close workflow runs for jobs with no unresolved staging rows
    -- ---------------------------------------------------------------
    if to_regclass('public.pc_workflow_runs') is not null then
        update public.pc_workflow_runs w
        set
            status='completed',
            current_stage='COMPLETE',
            completed_at=coalesce(w.completed_at,now()),
            updated_at=now(),
            metadata=coalesce(w.metadata,'{}'::jsonb)
                     || jsonb_build_object(
                         'review_queue_reset',true,
                         'review_queue_reset_at',now(),
                         'review_queue_reset_batch',v_batch
                     )
        where coalesce(lower(w.status),'') <> 'completed'
          and w.ingestion_job_id is not null
          and not exists (
              select 1
              from public.pc_staged_records s
              where s.ingestion_job_id=w.ingestion_job_id
                and coalesce(lower(s.review_status),'pending') <> 'applied'
          );

        get diagnostics v_count = row_count;
        raise notice 'Closed % workflow runs', v_count;
    end if;

    -- ---------------------------------------------------------------
    -- 5. Optional cleanup of stale resolution logs tied to rows that
    --    no longer exist in staging. This is audit/log data only.
    -- ---------------------------------------------------------------
    if to_regclass('public.pc_resolution_log') is not null then
        -- Archive before delete.
        insert into public.pc_ingestion_reset_archive(
            reset_batch_id,
            source_table,
            ingestion_job_id,
            staged_record_id,
            archive_reason,
            row_data
        )
        select
            v_batch,
            'pc_resolution_log',
            case
                when to_jsonb(r) ? 'ingestion_job_id'
                then nullif(to_jsonb(r)->>'ingestion_job_id','')::uuid
                else null
            end,
            case
                when to_jsonb(r) ? 'staged_record_id'
                then nullif(to_jsonb(r)->>'staged_record_id','')::uuid
                else null
            end,
            'START_FRESH_RESET_ORPHAN_RESOLUTION_LOG',
            to_jsonb(r)
        from public.pc_resolution_log r
        where (
            to_jsonb(r) ? 'staged_record_id'
            and nullif(to_jsonb(r)->>'staged_record_id','') is not null
            and not exists (
                select 1
                from public.pc_staged_records s
                where s.staged_record_id::text=(to_jsonb(r)->>'staged_record_id')
            )
        );

        delete from public.pc_resolution_log r
        where (
            to_jsonb(r) ? 'staged_record_id'
            and nullif(to_jsonb(r)->>'staged_record_id','') is not null
            and not exists (
                select 1
                from public.pc_staged_records s
                where s.staged_record_id::text=(to_jsonb(r)->>'staged_record_id')
            )
        );

        get diagnostics v_count = row_count;
        raise notice 'Deleted % orphan resolution-log rows', v_count;
    end if;

end $$;

commit;

-- -------------------------------------------------------------------
-- Post-reset checks
-- -------------------------------------------------------------------

-- Should return 0 unresolved rows:
select
    count(*) as unresolved_staged_rows
from public.pc_staged_records
where coalesce(lower(review_status),'pending') <> 'applied';

-- Applied history remains:
select
    count(*) as applied_staged_rows_remaining
from public.pc_staged_records
where lower(coalesce(review_status,''))='applied';

-- Archive count from this reset:
select
    reset_batch_id,
    source_table,
    count(*) as archived_rows,
    min(archived_at) as archived_from,
    max(archived_at) as archived_to
from public.pc_ingestion_reset_archive
group by reset_batch_id,source_table
order by max(archived_at) desc,source_table;

-- Review-queue views should now collapse to zero/near-zero:
-- select * from public.pc_v_reconciliation_queue limit 50;
-- select * from public.pc_v_ingestion_operator_exceptions limit 50;
-- select * from public.pc_v_workflow_dashboard limit 50;

-- Canonical tables are untouched. Useful sanity counts:
select 'pc_entities' as table_name,count(*) from public.pc_entities
union all
select 'pc_assets',count(*) from public.pc_assets
union all
select 'pc_mobile_assets',count(*) from public.pc_mobile_assets
union all
select 'pc_events',count(*) from public.pc_events
union all
select 'pc_event_links',count(*) from public.pc_event_links
union all
select 'pc_relationships',count(*) from public.pc_relationships;
