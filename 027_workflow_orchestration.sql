
begin;

create table if not exists pc_workflow_runs (
    workflow_run_id uuid primary key default gen_random_uuid(),
    workflow_type text not null,
    title text not null,
    ingestion_job_id uuid null,
    current_stage text not null default 'CREATED',
    stage_order integer not null default 1,
    status text not null default 'running',
    started_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    completed_at timestamptz null,
    stats jsonb not null default '{}'::jsonb,
    metadata jsonb not null default '{}'::jsonb
);

create index if not exists idx_pc_workflow_runs_job
    on pc_workflow_runs(ingestion_job_id);
create index if not exists idx_pc_workflow_runs_status
    on pc_workflow_runs(status, updated_at desc);

create table if not exists pc_workflow_stage_events (
    workflow_stage_event_id uuid primary key default gen_random_uuid(),
    workflow_run_id uuid not null references pc_workflow_runs(workflow_run_id) on delete cascade,
    stage_name text not null,
    stage_order integer not null,
    stage_status text not null,
    message text null,
    stats jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists pc_import_batches (
    import_batch_id uuid primary key default gen_random_uuid(),
    workflow_run_id uuid null references pc_workflow_runs(workflow_run_id) on delete set null,
    ingestion_job_id uuid null,
    file_name text not null,
    file_sha256 text null,
    file_type text null,
    status text not null default 'mapping',
    selected_tables jsonb not null default '[]'::jsonb,
    mapping jsonb not null default '{}'::jsonb,
    stats jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    completed_at timestamptz null
);

create table if not exists pc_import_table_maps (
    import_table_map_id uuid primary key default gen_random_uuid(),
    import_batch_id uuid not null references pc_import_batches(import_batch_id) on delete cascade,
    source_section text not null,
    target_table text not null,
    target_entity_type text null,
    column_mapping jsonb not null default '{}'::jsonb,
    row_count integer not null default 0,
    status text not null default 'mapped',
    stats jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create or replace function pc_workflow_set_stage(
    p_workflow_run_id uuid,
    p_stage_name text,
    p_stage_order integer,
    p_stage_status text default 'running',
    p_message text default null,
    p_stats jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path=public
as $$
declare
    v_completed timestamptz;
begin
    if lower(coalesce(p_stage_status,'')) in ('completed','failed','cancelled') then
        v_completed=now();
    else
        v_completed=null;
    end if;

    update pc_workflow_runs
       set current_stage=p_stage_name,
           stage_order=p_stage_order,
           status=case
                    when lower(coalesce(p_stage_status,''))='failed' then 'failed'
                    when lower(coalesce(p_stage_status,''))='completed'
                         and p_stage_name in ('COMPLETE','PUBLISHED') then 'completed'
                    else 'running'
                  end,
           updated_at=now(),
           completed_at=case
                          when p_stage_name in ('COMPLETE','PUBLISHED')
                           and lower(coalesce(p_stage_status,''))='completed'
                          then now()
                          else completed_at
                        end,
           stats=coalesce(stats,'{}'::jsonb) || coalesce(p_stats,'{}'::jsonb)
     where workflow_run_id=p_workflow_run_id;

    insert into pc_workflow_stage_events(
        workflow_run_id,stage_name,stage_order,stage_status,message,stats
    ) values (
        p_workflow_run_id,p_stage_name,p_stage_order,p_stage_status,p_message,coalesce(p_stats,'{}'::jsonb)
    );

    return jsonb_build_object(
        'workflow_run_id',p_workflow_run_id,
        'stage_name',p_stage_name,
        'stage_order',p_stage_order,
        'stage_status',p_stage_status
    );
end;
$$;

create or replace view pc_v_workflow_dashboard as
select
    w.workflow_run_id,
    w.workflow_type,
    w.title,
    w.ingestion_job_id,
    w.current_stage,
    w.stage_order,
    w.status,
    w.started_at,
    w.updated_at,
    w.completed_at,
    now()-w.updated_at as time_since_update,
    w.stats,
    w.metadata
from pc_workflow_runs w
order by w.updated_at desc;

comment on table pc_workflow_runs is
'Power Admin orchestration state for AI research, bulk import, document ingestion, analyst authoring and distribution workflows.';

commit;
