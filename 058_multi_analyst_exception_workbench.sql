-- 058_multi_analyst_exception_workbench.sql
-- Shared analyst exception queue with atomic claim/release/resolve semantics.

create extension if not exists pgcrypto;

create table if not exists public.pc_analyst_exceptions (
  exception_id uuid primary key default gen_random_uuid(),
  ingestion_job_id uuid not null,
  staged_record_id uuid,
  exception_key text not null,
  workstream text not null default 'cross' check (workstream in ('trade','intelligence','sanctions','cross')),
  exception_type text not null default 'canonical_review',
  target_table text,
  subject_name text,
  reason text not null,
  priority smallint not null default 50 check (priority between 0 and 100),
  status text not null default 'open' check (status in ('open','claimed','resolved','dismissed')),
  assigned_to text,
  assigned_name text,
  claimed_at timestamptz,
  resolved_at timestamptz,
  resolution jsonb not null default '{}'::jsonb,
  context jsonb not null default '{}'::jsonb,
  version integer not null default 1,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (ingestion_job_id, exception_key)
);

create index if not exists pc_analyst_exceptions_status_priority_idx
  on public.pc_analyst_exceptions(status, priority desc, created_at);
create index if not exists pc_analyst_exceptions_assigned_idx
  on public.pc_analyst_exceptions(assigned_to, status, updated_at desc);
create index if not exists pc_analyst_exceptions_workstream_idx
  on public.pc_analyst_exceptions(workstream, status, priority desc);
create index if not exists pc_analyst_exceptions_job_idx
  on public.pc_analyst_exceptions(ingestion_job_id, status);

create or replace function public.pc_claim_next_exception(
  p_analyst text,
  p_analyst_name text default null,
  p_workstreams text[] default null
) returns setof public.pc_analyst_exceptions
language plpgsql
security definer
set search_path = public
as $$
declare v_id uuid;
begin
  select exception_id into v_id
  from public.pc_analyst_exceptions
  where status='open'
    and (p_workstreams is null or workstream = any(p_workstreams))
  order by priority desc, created_at asc
  for update skip locked
  limit 1;

  if v_id is null then return; end if;

  return query
  update public.pc_analyst_exceptions
  set status='claimed', assigned_to=p_analyst, assigned_name=coalesce(p_analyst_name,p_analyst),
      claimed_at=now(), updated_at=now(), version=version+1
  where exception_id=v_id and status='open'
  returning *;
end $$;

create or replace function public.pc_claim_exception(
  p_exception uuid,
  p_analyst text,
  p_analyst_name text default null
) returns setof public.pc_analyst_exceptions
language sql
security definer
set search_path = public
as $$
  update public.pc_analyst_exceptions
  set status='claimed', assigned_to=p_analyst, assigned_name=coalesce(p_analyst_name,p_analyst),
      claimed_at=now(), updated_at=now(), version=version+1
  where exception_id=p_exception and status='open'
  returning *;
$$;

create or replace function public.pc_release_exception(
  p_exception uuid,
  p_analyst text,
  p_version integer
) returns boolean
language plpgsql
security definer
set search_path = public
as $$
begin
  update public.pc_analyst_exceptions
  set status='open', assigned_to=null, assigned_name=null, claimed_at=null,
      updated_at=now(), version=version+1
  where exception_id=p_exception and status='claimed'
    and assigned_to=p_analyst and version=p_version;
  return found;
end $$;

create or replace function public.pc_resolve_exception(
  p_exception uuid,
  p_analyst text,
  p_version integer,
  p_resolution jsonb,
  p_dismiss boolean default false
) returns boolean
language plpgsql
security definer
set search_path = public
as $$
begin
  update public.pc_analyst_exceptions
  set status=case when p_dismiss then 'dismissed' else 'resolved' end,
      resolution=coalesce(p_resolution,'{}'::jsonb),
      resolved_at=now(), updated_at=now(), version=version+1
  where exception_id=p_exception and status='claimed'
    and assigned_to=p_analyst and version=p_version;
  return found;
end $$;

grant select, insert, update on public.pc_analyst_exceptions to service_role;
grant execute on function public.pc_claim_next_exception(text,text,text[]) to service_role;
grant execute on function public.pc_claim_exception(uuid,text,text) to service_role;
grant execute on function public.pc_release_exception(uuid,text,integer) to service_role;
grant execute on function public.pc_resolve_exception(uuid,text,integer,jsonb,boolean) to service_role;
