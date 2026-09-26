-- P&C v1.0: controlled first-wave publication for companies, infrastructure, vessels and events.
-- Install after v0.7 and v0.8. Run in a non-production Supabase project first.
-- Fail closed: no automatic publication, no destructive staging moves, no inferred graph links.
create table if not exists public.pc_v10_approvals (
 staged_record_id uuid primary key references public.pc_staged_records(staged_record_id) on delete restrict,
 ingestion_job_id uuid not null,
 decision text not null check (decision in ('match_existing','create_new')),
 canonical_id text,
 source_verified boolean not null default false,
 event_duplicate_checked boolean not null default false,
 content_reviewed boolean not null default false,
 client_visible boolean not null default false,
 approved_by text not null,
 reviewed_at timestamptz not null default now(),
 check (decision <> 'match_existing' or (canonical_id is not null and length(trim(canonical_id)) > 2))
);
create index if not exists pc_v10_approvals_job_idx on public.pc_v10_approvals(ingestion_job_id);

-- Each backup is independent and immutable. Back up BEFORE publication so it survives a failed publish.
create table if not exists public.pc_v10_stage_backups (
 backup_id uuid primary key default gen_random_uuid(),
 ingestion_job_id uuid not null,
 snapshot jsonb not null,
 record_count integer not null,
 snapshot_md5 text not null,
 backed_up_by text not null,
 created_at timestamptz not null default now()
);
create index if not exists pc_v10_backups_job_idx on public.pc_v10_stage_backups(ingestion_job_id,created_at desc);

create table if not exists public.pc_v10_publications (
 publication_id uuid primary key default gen_random_uuid(),
 ingestion_job_id uuid not null,
 backup_id uuid not null references public.pc_v10_stage_backups(backup_id),
 published_by text not null,
 item_count integer not null,
 published_at timestamptz not null default now()
);
create table if not exists public.pc_v10_publication_items (
 staged_record_id uuid primary key references public.pc_staged_records(staged_record_id) on delete restrict,
 publication_id uuid not null references public.pc_v10_publications(publication_id),
 canonical_table text not null,
 canonical_id text not null,
 action text not null check (action in ('matched','inserted')),
 published_at timestamptz not null default now()
);
create index if not exists pc_v10_pub_items_canonical_idx on public.pc_v10_publication_items(canonical_table,canonical_id);

-- A content projection for Trade. Not readable by anonymous users; client apps enforce access.
create table if not exists public.pc_v10_published_content (
 content_id bigint generated always as identity primary key,
 staged_record_id uuid not null unique references public.pc_staged_records(staged_record_id) on delete restrict,
 publication_id uuid not null references public.pc_v10_publications(publication_id),
 target_table text not null,
 canonical_id text not null,
 title text not null,
 description text,
 what_it_means text,
 operational_impact text,
 commercial_implications text,
 pc_assessment text,
 monitoring_indicators jsonb not null default '[]'::jsonb,
 research_gaps jsonb not null default '[]'::jsonb,
 source_evidence jsonb not null default '[]'::jsonb,
 content_origin text not null default 'source_supplied',
 visible_in_trade boolean not null default false,
 published_at timestamptz not null default now(),
 unique (target_table,canonical_id,staged_record_id)
);
create index if not exists pc_v10_content_target_idx on public.pc_v10_published_content(target_table,canonical_id,published_at desc);

alter table public.pc_v10_approvals enable row level security;
alter table public.pc_v10_stage_backups enable row level security;
alter table public.pc_v10_publications enable row level security;
alter table public.pc_v10_publication_items enable row level security;
alter table public.pc_v10_published_content enable row level security;
revoke all on public.pc_v10_approvals,public.pc_v10_stage_backups,public.pc_v10_publications,
 public.pc_v10_publication_items,public.pc_v10_published_content from anon,authenticated;
grant select,insert,update,delete on public.pc_v10_approvals,public.pc_v10_stage_backups,public.pc_v10_publications,
 public.pc_v10_publication_items,public.pc_v10_published_content to service_role;
grant usage,select on all sequences in schema public to service_role;

-- Backup up to 200 staged records per invocation. Snapshots include original payload AND draft analysis/news.
create or replace function public.pc_v10_backup_staged(p_job uuid,p_stage_ids uuid[],p_reviewer text)
returns uuid language plpgsql security definer set search_path=public,pg_temp as $$
declare v_id uuid; v_snap jsonb; v_count int; v_hash text;
begin
 if current_setting('request.jwt.claim.role',true) is distinct from 'service_role' and session_user <> 'postgres' then
   raise exception 'service role required'; end if;
 if nullif(trim(p_reviewer),'') is null then raise exception 'Reviewer is required'; end if;
 if coalesce(array_length(p_stage_ids,1),0) not between 1 and 200 then raise exception 'Select 1-200 rows'; end if;
 if array_length(p_stage_ids,1) <> (select count(distinct x) from unnest(p_stage_ids) x) then
   raise exception 'Duplicate selected staged IDs'; end if;
 select count(*),jsonb_agg(jsonb_build_object(
    'staged_record',to_jsonb(s),
    'draft_content',(select jsonb_agg(to_jsonb(c)) from public.pc_v08_trade_content c where c.ingestion_job_id=s.ingestion_job_id and c.source_record_key=s.source_record_key),
    'news',(select jsonb_agg(to_jsonb(n)) from public.pc_v08_news_items n where n.ingestion_job_id=s.ingestion_job_id and n.source_record_key=s.source_record_key),
    'approval',(select to_jsonb(a) from public.pc_v10_approvals a where a.staged_record_id=s.staged_record_id)
   ) order by s.source_record_key,s.staged_record_id)
 into v_count,v_snap from public.pc_staged_records s
 where s.ingestion_job_id=p_job and s.staged_record_id=any(p_stage_ids);
 if v_count <> array_length(p_stage_ids,1) then raise exception 'One or more staged IDs are absent from this job'; end if;
 v_hash=md5(v_snap::text);
 insert into public.pc_v10_stage_backups(ingestion_job_id,snapshot,record_count,snapshot_md5,backed_up_by)
 values(p_job,v_snap,v_count,v_hash,p_reviewer) returning backup_id into v_id;
 return v_id;
end $$;
revoke all on function public.pc_v10_backup_staged(uuid,uuid[],text) from public,anon,authenticated;
grant execute on function public.pc_v10_backup_staged(uuid,uuid[],text) to service_role;

-- Transactional publisher. All selected rows publish or none do.
-- Deliberately limits initial scope to four validated Trade domains; edges stay in staging.
create or replace function public.pc_v10_publish_approved(p_job uuid,p_stage_ids uuid[],p_backup uuid,p_reviewer text)
returns jsonb language plpgsql security definer set search_path=public,pg_temp as $$
declare
 r record; a record; c record; v_pub uuid; v_pk text; v_id text; v_new text; v_exists boolean;
 v_payload jsonb; v_filtered jsonb; v_cols text[]; v_col_list text; v_select_list text; v_action text;
 v_count int=0; v_inserted int=0; v_matched int=0; v_meta jsonb; v_analysis jsonb;
begin
 if current_setting('request.jwt.claim.role',true) is distinct from 'service_role' and session_user <> 'postgres' then
  raise exception 'service role required'; end if;
 if nullif(trim(p_reviewer),'') is null then raise exception 'Reviewer is required'; end if;
 if coalesce(array_length(p_stage_ids,1),0) not between 1 and 50 then raise exception 'Publish 1-50 at a time'; end if;
 if array_length(p_stage_ids,1) <> (select count(distinct x) from unnest(p_stage_ids) x) then
  raise exception 'Duplicate selected staged IDs'; end if;
 if not exists(select 1 from public.pc_v10_stage_backups b
   where b.backup_id=p_backup and b.ingestion_job_id=p_job
   and (select count(*) from jsonb_array_elements(b.snapshot) j
     where (j->'staged_record'->>'staged_record_id')::uuid=any(p_stage_ids))=array_length(p_stage_ids,1)) then
  raise exception 'Independent backup covering all selected records is required'; end if;
 if (select count(*) from public.pc_staged_records s where s.ingestion_job_id=p_job and s.staged_record_id=any(p_stage_ids)) <> array_length(p_stage_ids,1) then
  raise exception 'Selected staged record does not belong to this job'; end if;
 if exists(select 1 from public.pc_v10_publication_items p where p.staged_record_id=any(p_stage_ids)) then
  raise exception 'At least one selected record has already been published; select remaining records'; end if;
 if exists(select 1 from public.pc_staged_records s join public.pc_v10_approvals a on a.staged_record_id=s.staged_record_id
    where s.staged_record_id=any(p_stage_ids) and a.decision='create_new'
    group by s.target_table,lower(trim(coalesce(s.payload->>'name',s.payload->>'title',s.natural_key))),coalesce(s.payload->>'start_date','')
    having count(*)>1) then raise exception 'Duplicate new identities/events within selected batch'; end if;
 insert into public.pc_v10_publications(ingestion_job_id,backup_id,published_by,item_count)
 values(p_job,p_backup,p_reviewer,array_length(p_stage_ids,1)) returning publication_id into v_pub;
 for r in select s.* from public.pc_staged_records s
   where s.ingestion_job_id=p_job and s.staged_record_id=any(p_stage_ids)
   order by case s.target_table when 'pc_entities' then 1 when 'pc_assets' then 2 when 'pc_mobile_assets' then 3 when 'pc_events' then 4 else 99 end,s.source_record_key
   for update
 loop
  if r.target_table not in ('pc_entities','pc_assets','pc_mobile_assets','pc_events') then
   raise exception 'Unsupported table %: graph edges and corridor links still require separate validation',r.target_table;
  end if;
  -- Fail if a staged row changed since the independent backup.
  if not exists (select 1 from public.pc_v10_stage_backups b, jsonb_array_elements(b.snapshot) entry
     where b.backup_id=p_backup and (entry->'staged_record'->>'staged_record_id')::uuid=r.staged_record_id
       and entry->'staged_record'=to_jsonb(r)) then
   raise exception 'Staged record changed since backup: %',r.natural_key; end if;
  select * into a from public.pc_v10_approvals
    where staged_record_id=r.staged_record_id and ingestion_job_id=p_job and source_verified
      and approved_by=p_reviewer;
  if not found then raise exception 'Missing verified approval for %',r.natural_key; end if;
  if not exists (select 1 from public.pc_v10_stage_backups b,jsonb_array_elements(b.snapshot) entry
     where b.backup_id=p_backup and (entry->'staged_record'->>'staged_record_id')::uuid=r.staged_record_id
       and entry->'approval'=to_jsonb(a)) then
    raise exception 'Approval changed since backup: take a fresh backup'; end if;
  if r.target_table='pc_events' and not a.event_duplicate_checked then
   raise exception 'Event duplicate check required: %',r.natural_key; end if;
  v_pk=case r.target_table when 'pc_entities' then 'entity_id' when 'pc_assets' then 'asset_id'
    when 'pc_mobile_assets' then 'mobile_asset_id' else 'event_id' end;
  if a.decision='match_existing' then
   v_id=a.canonical_id;
   execute format('select exists (select 1 from public.%I where %I::text=$1)',r.target_table,v_pk)
    using v_id into v_exists;
   if not v_exists then raise exception 'Canonical target % not found for %',v_id,r.natural_key;end if;
   v_action='matched';v_matched=v_matched+1;
  else
   -- Refuse even an approved NEW candidate if canonical registry already has an exact name.
   if r.target_table='pc_events' then
    execute 'select exists(select 1 from public.pc_events where lower(trim(title))=lower(trim($1)) and start_date is not distinct from $2::date)'
       using coalesce(r.payload->>'title',r.natural_key),nullif(r.payload->>'start_date','') into v_exists;
   else
    execute format('select exists(select 1 from public.%I where lower(trim(name))=lower(trim($1)))',r.target_table)
      using coalesce(r.payload->>'name',r.natural_key) into v_exists;
   end if;
   if v_exists then raise exception 'Exact canonical name/event already exists for %: choose MATCH instead',r.natural_key; end if;
   -- NO automatic merge by name. New canonical IDs are generated; original temporary IDs remain in snapshot.
   v_id=case r.target_table when 'pc_entities' then 'ENTITY_AUTO_' when 'pc_assets' then 'ASSET_AUTO_'
     when 'pc_mobile_assets' then 'MOBILE_AUTO_' else 'EVT_PC_' end || upper(substr(md5(gen_random_uuid()::text),1,20));
   v_payload=coalesce(r.payload,'{}'::jsonb);
   v_meta=case when jsonb_typeof(v_payload->'metadata')='object' then v_payload->'metadata' else '{}'::jsonb end;
   v_meta=v_meta||jsonb_build_object('pc_v10_staged_record_id',r.staged_record_id::text,
     'pc_v10_source_temporary_id',v_payload->>v_pk,'pc_v10_ingestion_job_id',p_job::text);
   v_payload=v_payload||jsonb_build_object(v_pk,v_id,'metadata',v_meta);
   if r.target_table='pc_entities' and nullif(v_payload->>'hq_country','') is null and nullif(v_payload->>'country','') is not null then
     v_payload=v_payload||jsonb_build_object('hq_country',v_payload->>'country');end if;
   -- Prevent provisional source labels from being treated as verified registry facts.
   if r.target_table in ('pc_entities','pc_assets','pc_mobile_assets') then
     v_payload=v_payload||jsonb_build_object('record_status','verified');end if;
   if r.target_table='pc_events' then v_payload=v_payload||jsonb_build_object('trade_visible',a.client_visible and a.content_reviewed);end if;
   select array_agg(column_name::text) into v_cols from information_schema.columns
    where table_schema='public' and table_name=r.target_table
     and column_name=any(case r.target_table
      when 'pc_entities' then array['entity_id','name','entity_type','hq_country','record_status','metadata']
      when 'pc_assets' then array['asset_id','name','asset_type','country','record_status','metadata']
      when 'pc_mobile_assets' then array['mobile_asset_id','name','asset_type','imo','flag','record_status','metadata']
      else array['event_id','title','start_date','event_domain','event_nature','event_type','location','description','operational_impact','commercial_impact','metadata','trade_visible'] end);
   if not (v_pk=any(v_cols)) or not ((case when r.target_table='pc_events' then 'title' else 'name' end)=any(v_cols)) then
    raise exception 'Canonical schema % lacks required columns',r.target_table; end if;
   -- Fail on NOT NULL schema additions without defaults instead of silently dropping fields.
   if exists(select 1 from information_schema.columns col where col.table_schema='public' and col.table_name=r.target_table
      and col.is_nullable='NO' and col.column_default is null and col.is_identity='NO'
      and not(col.column_name=any(v_cols))) then
     raise exception 'Canonical % has required unmapped columns; inspect schema before publishing',r.target_table;end if;
   select coalesce(jsonb_object_agg(k,v),'{}'::jsonb) into v_filtered
    from jsonb_each(v_payload) e(k,v) where k=any(v_cols);
   if r.target_table='pc_events' and coalesce(nullif(trim(v_filtered->>'title'),''),'')='' then
      raise exception 'Event title is required'; end if;
   if r.target_table<>'pc_events' and coalesce(nullif(trim(v_filtered->>'name'),''),'')='' then
      raise exception 'Entity name is required'; end if;
   select string_agg(format('%I',x),','),string_agg(format('(jsonb_populate_record(null::public.%I,$1)).%I',r.target_table,x),',')
    into v_col_list,v_select_list from unnest(v_cols) x;
   execute format('insert into public.%I (%s) select %s',r.target_table,v_col_list,v_select_list)
     using v_filtered;
   v_action='inserted';v_inserted=v_inserted+1;
  end if;
  insert into public.pc_v10_publication_items(staged_record_id,publication_id,canonical_table,canonical_id,action)
  values(r.staged_record_id,v_pub,r.target_table,v_id,v_action);
  -- Publish source-faithful narrative. Existing canonical fields are not overwritten on matches.
  select * into c from public.pc_v08_trade_content
    where ingestion_job_id=p_job and source_record_key=r.source_record_key
    order by version desc,content_id desc limit 1;
  v_payload=coalesce(r.payload,'{}'::jsonb);
  v_meta=case when jsonb_typeof(v_payload->'metadata')='object' then v_payload->'metadata' else '{}'::jsonb end;
  v_analysis=case when jsonb_typeof(v_meta->'analysis')='object' then v_meta->'analysis' else '{}'::jsonb end;
  if a.content_reviewed then
    insert into public.pc_v10_published_content(staged_record_id,publication_id,target_table,canonical_id,title,
      description,what_it_means,operational_impact,commercial_implications,pc_assessment,
      monitoring_indicators,research_gaps,source_evidence,content_origin,visible_in_trade)
    values(r.staged_record_id,v_pub,r.target_table,v_id,coalesce(nullif(c.title,''),nullif(v_payload->>'title',''),r.natural_key),
      coalesce(c.description,v_payload->>'what_happened',v_analysis->>'what_happened',v_payload->>'description',v_meta->>'event_summary'),
      coalesce(c.what_it_means,v_payload->>'what_it_means',v_analysis->>'what_it_means',v_meta->>'why_it_matters'),
      coalesce(c.operational_impact,v_payload->>'operational_impact',v_analysis->>'operational_impact'),
      coalesce(c.commercial_implications,v_payload->>'commercial_impact',v_payload->>'commercial_implications',v_analysis->>'commercial_implications',v_meta->>'commercial_implications'),
      coalesce(c.pc_assessment,v_analysis->>'pc_assessment',v_meta->>'assessment'),
      coalesce(c.monitoring_indicators,v_analysis->'monitoring_indicators',v_meta->'monitoring_indicators','[]'::jsonb),
      coalesce(c.research_gaps,v_analysis->'research_gaps',v_meta->'research_gaps','[]'::jsonb),
      coalesce(c.source_evidence,v_meta->'research_sources',r.resolution_details->'source_urls','[]'::jsonb),
      coalesce(c.text_origin,'source_supplied'),a.client_visible);
  end if;
  v_count=v_count+1;
 end loop;
 return jsonb_build_object('publication_id',v_pub,'published',v_count,'inserted',v_inserted,
  'matched',v_matched,'backup_id',p_backup);
end $$;
revoke all on function public.pc_v10_publish_approved(uuid,uuid[],uuid,text) from public,anon,authenticated;
grant execute on function public.pc_v10_publish_approved(uuid,uuid[],uuid,text) to service_role;
