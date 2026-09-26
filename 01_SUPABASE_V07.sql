-- P&C v0.7. Run in Supabase SQL Editor after reviewing. ADDITIVE ONLY.
-- No existing canonical tables are altered or overwritten by this migration.
create table if not exists public.pc_v07_queue (
  queue_id bigint generated always as identity primary key,
  ingestion_job_id uuid not null,
  source_record_key text not null,
  target_table text not null,
  natural_key text not null,
  payload jsonb not null default '{}'::jsonb,
  source_url text,
  priority smallint not null default 50,
  status text not null default 'queued'
    check (status in ('queued','processing','staged','needs_review','failed')),
  attempts integer not null default 0,
  lease_owner text,
  lease_until timestamptz,
  error_text text,
  staged_record_id uuid,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (ingestion_job_id, source_record_key)
);
create index if not exists pc_v07_queue_claim_idx
 on public.pc_v07_queue (status, priority desc, queue_id)
 where status in ('queued', 'processing');
create index if not exists pc_v07_queue_job_idx
 on public.pc_v07_queue (ingestion_job_id, queue_id);

-- Preserves source publications as individual observations (not one event per article).
create table if not exists public.pc_v07_observations (
 observation_id bigint generated always as identity primary key,
 ingestion_job_id uuid not null,
 source_record_key text not null,
 target_table text not null,
 natural_key text not null,
 source_url text,
 source_snapshot jsonb not null default '{}'::jsonb,
 observed_at timestamptz not null default now(),
 unique (ingestion_job_id,source_record_key)
);
create index if not exists pc_v07_obs_target_idx on public.pc_v07_observations(target_table,natural_key);

-- Event analysis is versioned and stays DRAFT until an explicit separate publish step.
create table if not exists public.pc_v07_event_assessments (
 assessment_id bigint generated always as identity primary key,
 ingestion_job_id uuid not null,
 source_record_key text not null,
 event_id text,
 event_title text not null,
 what_happened text,
 what_it_means text,
 operational_impact text,
 commercial_impact text,
 pc_assessment text,
 monitoring_indicators jsonb not null default '[]'::jsonb,
 research_gaps jsonb not null default '[]'::jsonb,
 evidence_urls jsonb not null default '[]'::jsonb,
 assessment_status text not null default 'draft' check (assessment_status in ('draft','reviewed','published')),
 version integer not null default 1,
 created_at timestamptz not null default now(),
 unique (ingestion_job_id, source_record_key, version)
);
create index if not exists pc_v07_assessments_event_idx
 on public.pc_v07_event_assessments(event_id,version desc);
create index if not exists pc_v07_assessments_job_idx
 on public.pc_v07_event_assessments(ingestion_job_id);

create table if not exists public.pc_v07_research_cache (
 research_key text primary key,
 domain text not null,
 subject text not null,
 findings jsonb not null,
 evidence_urls jsonb not null default '[]'::jsonb,
 verified boolean not null default false,
 researched_at timestamptz not null default now(),
 refresh_after timestamptz
);

-- All new tables contain unpublished work. Service-role access only.
alter table public.pc_v07_queue enable row level security;
alter table public.pc_v07_observations enable row level security;
alter table public.pc_v07_event_assessments enable row level security;
alter table public.pc_v07_research_cache enable row level security;
revoke all on public.pc_v07_queue, public.pc_v07_observations,
 public.pc_v07_event_assessments, public.pc_v07_research_cache from anon,authenticated;

-- One atomic worker lease; crashed jobs re-enter queue after timeout.
create or replace function public.pc_v07_claim_queue(p_worker text, p_limit integer default 100)
returns setof public.pc_v07_queue
language plpgsql security definer set search_path = public, pg_temp
as $$
begin
  if current_setting('request.jwt.claim.role', true) is distinct from 'service_role'
     and session_user <> 'postgres' then
    raise exception 'service_role required';
  end if;
  return query
  with selected as (
    select q.queue_id from public.pc_v07_queue q
    where q.status = 'queued' or (q.status = 'processing' and q.lease_until < now())
    order by q.priority desc, q.queue_id
    for update skip locked
    limit least(greatest(p_limit,1),250)
  )
  update public.pc_v07_queue q
  set status='processing', lease_owner=p_worker,
      lease_until=now()+interval '10 minutes', attempts=q.attempts+1,
      updated_at=now()
  from selected s where q.queue_id=s.queue_id
  returning q.*;
end $$;
revoke all on function public.pc_v07_claim_queue(text,integer) from public, anon, authenticated;
grant execute on function public.pc_v07_claim_queue(text,integer) to service_role;

-- Existing staging indexes. Inspect duplicate IDs before adding any new UNIQUE index.
create index if not exists pc_v07_staged_job_page_idx
 on public.pc_staged_records(ingestion_job_id, created_at desc, staged_record_id);
create index if not exists pc_v07_jobs_recent_idx
 on public.pc_ingestion_jobs(created_at desc, ingestion_job_id);
create index if not exists pc_v07_events_recent_idx
 on public.pc_events(start_date desc, event_id);
create index if not exists pc_v07_event_links_parent_idx
 on public.pc_event_links(event_id);
create index if not exists pc_v07_mobile_imo_idx
 on public.pc_mobile_assets(imo) where imo is not null;

-- Targeted optional research tasks: deduplicated by (target table, normalised subject).
create table if not exists public.pc_v07_research_tasks (
 research_key text primary key,
 ingestion_job_id uuid not null,
 target_table text not null,
 subject text not null,
 source_urls jsonb not null default '[]'::jsonb,
 status text not null default 'queued'
    check (status in ('queued','processing','completed','failed')),
 attempts integer not null default 0,
 lease_owner text, lease_until timestamptz,
 error_text text,
 created_at timestamptz not null default now(),
 updated_at timestamptz not null default now()
);
create index if not exists pc_v07_research_claim_idx
 on public.pc_v07_research_tasks(status,created_at)
 where status in ('queued','processing');
alter table public.pc_v07_research_tasks enable row level security;
revoke all on public.pc_v07_research_tasks from anon,authenticated;

create or replace function public.pc_v07_claim_research(p_worker text,p_limit integer default 3)
returns setof public.pc_v07_research_tasks
language plpgsql security definer set search_path=public,pg_temp
as $$
begin
 if current_setting('request.jwt.claim.role', true) is distinct from 'service_role'
    and session_user <> 'postgres' then raise exception 'service_role required'; end if;
 return query
 with selected as (
  select t.research_key from public.pc_v07_research_tasks t
  where t.status='queued' or (t.status='processing' and t.lease_until < now())
  order by t.created_at for update skip locked
  limit least(greatest(p_limit,1),10)
 )
 update public.pc_v07_research_tasks t
 set status='processing',lease_owner=p_worker,lease_until=now()+interval '7 minutes',
     attempts=t.attempts+1,updated_at=now()
 from selected s where t.research_key=s.research_key returning t.*;
end $$;
revoke all on function public.pc_v07_claim_research(text,integer) from public,anon,authenticated;
grant execute on function public.pc_v07_claim_research(text,integer) to service_role;

-- Performance for content-hash job reuse and job-scoped staged rows.
create index if not exists pc_v07_jobs_scope_idx on public.pc_ingestion_jobs using gin(source_scope jsonb_path_ops);
create index if not exists pc_v07_staged_retry_idx on public.pc_staged_records(ingestion_job_id, source_record_key);

-- SQL editor owns new tables; explicitly permit the service-role API client.
grant select,insert,update,delete on public.pc_v07_queue,public.pc_v07_observations,
 public.pc_v07_event_assessments,public.pc_v07_research_cache,public.pc_v07_research_tasks to service_role;
grant usage,select on all sequences in schema public to service_role;
