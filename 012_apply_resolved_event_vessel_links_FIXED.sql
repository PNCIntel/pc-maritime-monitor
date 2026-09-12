-- Power & Corridors SQL 012
-- Controlled promotion of resolved event -> vessel relationships into pc_event_links.
-- Requires SQL 010 and SQL 011.
-- PostgreSQL / Supabase

begin;

-- Keep resolution state separate from canonical-apply state.
alter table pc_staged_relationships add column if not exists apply_status text not null default 'PENDING';
alter table pc_staged_relationships add column if not exists applied_at timestamptz;
alter table pc_staged_relationships add column if not exists canonical_relationship_id text;
alter table pc_staged_relationships add column if not exists apply_error text;

create index if not exists idx_pc_staged_rel_apply
  on pc_staged_relationships(apply_status,resolution_status,relationship_type);

-- Stable fallback ID for a canonical event link when the staged proposal does not
-- carry a usable event_link_id.
create or replace function pc_event_link_id(
  p_event_id text,
  p_linked_type text,
  p_linked_id text,
  p_relationship text
)
returns text
language sql
immutable
as $$
  select 'EVL_' || upper(substr(md5(
    coalesce(p_event_id,'') || '|' ||
    coalesce(p_linked_type,'') || '|' ||
    coalesce(p_linked_id,'') || '|' ||
    coalesce(p_relationship,'')
  ),1,24));
$$;

-- Apply one READY relationship. This is intentionally limited to an event as the
-- source endpoint. For the current ReCAAP backlog the target is mobile_asset,
-- creating the missing vessel -> event linkage in pc_event_links.
create or replace function pc_apply_staged_event_relationship(p_staged_relationship_id uuid)
returns jsonb
language plpgsql
security definer
set search_path=public
as $$
declare
  r pc_staged_relationships%rowtype;
  x record;
  s pc_staged_records%rowtype;
  v_linked_type text;
  v_event_link_id text;
  v_proposed_id text;
  v_existing text;
  v_target_name text;
  v_metadata jsonb;
begin
  select * into r
  from pc_staged_relationships
  where staged_relationship_id=p_staged_relationship_id
  for update;

  if not found then
    raise exception 'Unknown staged relationship %',p_staged_relationship_id;
  end if;

  if r.apply_status in ('APPLIED','SKIPPED_EXISTS') then
    return jsonb_build_object(
      'status',r.apply_status,
      'staged_relationship_id',r.staged_relationship_id,
      'canonical_relationship_id',r.canonical_relationship_id
    );
  end if;

  if r.from_entity_type <> 'event' then
    update pc_staged_relationships
       set apply_status='ERROR',apply_error='SQL 012 only promotes event relationships'
     where staged_relationship_id=r.staged_relationship_id;
    return jsonb_build_object('status','ERROR','error','SQL 012 only promotes event relationships');
  end if;

  -- Re-resolve at apply time so a stale READY decision cannot be promoted.
  select * into x from pc_resolve_staged_relationship(r.staged_relationship_id);
  select * into r from pc_staged_relationships where staged_relationship_id=p_staged_relationship_id;

  if x.resolution_status='ALREADY_EXISTS' then
    update pc_staged_relationships
       set apply_status='SKIPPED_EXISTS',
           canonical_relationship_id=x.existing_relationship_id,
           applied_at=now(),apply_error=null
     where staged_relationship_id=r.staged_relationship_id;

    if r.source_staged_record_id is not null then
      update pc_staged_records
         set review_status='applied',validation_status='validated',reviewed_at=coalesce(reviewed_at,now()),
             resolution_details=coalesce(resolution_details,'{}'::jsonb) || jsonb_build_object(
               'apply_status','SKIPPED_EXISTS','canonical_relationship_id',x.existing_relationship_id
             )
       where staged_record_id=r.source_staged_record_id;
    end if;

    return jsonb_build_object('status','SKIPPED_EXISTS','canonical_relationship_id',x.existing_relationship_id);
  end if;

  if x.resolution_status <> 'READY' then
    update pc_staged_relationships
       set apply_status='BLOCKED',apply_error='Resolution status is '||coalesce(x.resolution_status,'NULL')
     where staged_relationship_id=r.staged_relationship_id;
    return jsonb_build_object('status','BLOCKED','resolution_status',x.resolution_status);
  end if;

  -- Resolve the polymorphic pc_event_links linked_type from the logical target.
  v_linked_type := case r.to_entity_type
    when 'mobile_asset' then 'mobile_asset'
    when 'entity' then 'entity'
    when 'asset' then 'asset'
    when 'geography' then 'geography'
    else r.to_entity_type
  end;

  -- Recheck the exact canonical event -> target relationship immediately before insert.
  select l.event_link_id into v_existing
  from pc_event_links l
  where l.event_id=r.resolved_from_entity_id
    and pc_linked_type_to_entity_type(l.linked_type)=r.to_entity_type
    and l.linked_id=r.resolved_to_entity_id
    and coalesce(l.relationship,'')=coalesce(r.relationship_type,'')
  order by l.event_link_id
  limit 1;

  if v_existing is not null then
    update pc_staged_relationships
       set resolution_status='ALREADY_EXISTS',existing_relationship_id=v_existing,
           apply_status='SKIPPED_EXISTS',canonical_relationship_id=v_existing,
           applied_at=now(),apply_error=null
     where staged_relationship_id=r.staged_relationship_id;

    if r.source_staged_record_id is not null then
      update pc_staged_records
         set review_status='applied',validation_status='validated',reviewed_at=coalesce(reviewed_at,now()),
             resolution_status='ALREADY_EXISTS',
             resolution_details=coalesce(resolution_details,'{}'::jsonb) || jsonb_build_object(
               'apply_status','SKIPPED_EXISTS','canonical_relationship_id',v_existing
             )
       where staged_record_id=r.source_staged_record_id;
    end if;

    return jsonb_build_object('status','SKIPPED_EXISTS','canonical_relationship_id',v_existing);
  end if;

  if r.source_staged_record_id is not null then
    select * into s from pc_staged_records where staged_record_id=r.source_staged_record_id;
  end if;

  v_proposed_id := nullif(coalesce(r.metadata->>'event_link_id', s.payload->>'event_link_id'),'');
  v_event_link_id := coalesce(v_proposed_id,
    pc_event_link_id(r.resolved_from_entity_id,v_linked_type,r.resolved_to_entity_id,r.relationship_type));

  -- If an imported ID collides with a different canonical row, fall back to a stable generated ID.
  if exists(select 1 from pc_event_links where event_link_id=v_event_link_id) then
    v_event_link_id := pc_event_link_id(
      r.resolved_from_entity_id,v_linked_type,r.resolved_to_entity_id,r.relationship_type
    );
  end if;

  -- Prefer current canonical display names rather than trusting imported text.
  if r.to_entity_type='mobile_asset' then
    select name into v_target_name from pc_mobile_assets where mobile_asset_id=r.resolved_to_entity_id;
  elsif r.to_entity_type='entity' then
    select name into v_target_name from pc_entities where entity_id=r.resolved_to_entity_id;
  elsif r.to_entity_type='asset' then
    select name into v_target_name from pc_assets where asset_id=r.resolved_to_entity_id;
  elsif r.to_entity_type='geography' then
    select name into v_target_name from pc_geographies where geo_id=r.resolved_to_entity_id;
  end if;
  v_target_name := coalesce(v_target_name,r.to_name,r.resolved_to_entity_id);

  v_metadata := coalesce(r.metadata->'original_metadata','{}'::jsonb)
    || jsonb_build_object(
      'staged_relationship_id',r.staged_relationship_id,
      'source_staged_record_id',r.source_staged_record_id,
      'resolution_method',coalesce(r.from_resolution_method,'')||' -> '||coalesce(r.to_resolution_method,''),
      'resolved_at',r.resolved_at,
      'applied_from_sql','012_apply_resolved_event_vessel_links.sql'
    );

  insert into pc_event_links(
    event_link_id,event_id,linked_type,linked_id,linked_name,relationship,confidence,source_id,metadata
  ) values (
    v_event_link_id,
    r.resolved_from_entity_id,
    v_linked_type,
    r.resolved_to_entity_id,
    v_target_name,
    coalesce(r.relationship_type,'linked object'),
    case when r.confidence is null then null else r.confidence::text end,
    r.source_id,
    v_metadata
  );

  update pc_staged_relationships
     set apply_status='APPLIED',canonical_relationship_id=v_event_link_id,
         applied_at=now(),apply_error=null
   where staged_relationship_id=r.staged_relationship_id;

  if r.source_staged_record_id is not null then
    update pc_staged_records
       set review_status='applied',validation_status='validated',reviewed_at=coalesce(reviewed_at,now()),
           resolved_entity_id=r.resolved_to_entity_id,
           resolution_details=coalesce(resolution_details,'{}'::jsonb) || jsonb_build_object(
             'apply_status','APPLIED',
             'canonical_relationship_id',v_event_link_id,
             'canonical_event_id',r.resolved_from_entity_id,
             'canonical_linked_type',v_linked_type,
             'canonical_linked_id',r.resolved_to_entity_id
           )
     where staged_record_id=r.source_staged_record_id;
  end if;

  insert into pc_audit_log(action,object_type,object_id,before_data,after_data)
  values (
    'STAGED_RELATIONSHIP_APPLY','pc_event_links',v_event_link_id,null,
    jsonb_build_object(
      'event_id',r.resolved_from_entity_id,
      'linked_type',v_linked_type,
      'linked_id',r.resolved_to_entity_id,
      'linked_name',v_target_name,
      'relationship',r.relationship_type,
      'staged_relationship_id',r.staged_relationship_id
    )
  );

  return jsonb_build_object(
    'status','APPLIED',
    'canonical_relationship_id',v_event_link_id,
    'event_id',r.resolved_from_entity_id,
    'linked_type',v_linked_type,
    'linked_id',r.resolved_to_entity_id,
    'linked_name',v_target_name
  );
exception when others then
  update pc_staged_relationships
     set apply_status='ERROR',apply_error=sqlerrm
   where staged_relationship_id=p_staged_relationship_id;
  return jsonb_build_object('status','ERROR','error',sqlerrm,'staged_relationship_id',p_staged_relationship_id);
end;
$$;

-- Bulk apply. Optional job filter allows one ingestion batch at a time.
create or replace function pc_apply_ready_event_relationships(p_ingestion_job_id uuid default null)
returns jsonb
language plpgsql
security definer
set search_path=public
as $$
declare
  r record;
  x jsonb;
  n_total integer:=0;
  n_applied integer:=0;
  n_exists integer:=0;
  n_blocked integer:=0;
  n_error integer:=0;
  v_status text;
begin
  for r in
    select staged_relationship_id
    from pc_staged_relationships
    where from_entity_type='event'
      and resolution_status in ('READY','ALREADY_EXISTS')
      and apply_status not in ('APPLIED','SKIPPED_EXISTS')
      and (p_ingestion_job_id is null or ingestion_job_id=p_ingestion_job_id)
    order by created_at,staged_relationship_id
  loop
    n_total:=n_total+1;
    x:=pc_apply_staged_event_relationship(r.staged_relationship_id);
    v_status:=x->>'status';
    if v_status='APPLIED' then n_applied:=n_applied+1;
    elsif v_status='SKIPPED_EXISTS' then n_exists:=n_exists+1;
    elsif v_status='BLOCKED' then n_blocked:=n_blocked+1;
    else n_error:=n_error+1;
    end if;
  end loop;

  return jsonb_build_object(
    'total',n_total,
    'applied',n_applied,
    'already_exists',n_exists,
    'blocked',n_blocked,
    'errors',n_error
  );
end;
$$;

-- Verification view: this is the actual canonical vessel-to-event linkage state.
create or replace view pc_v_event_vessel_links as
select
  l.event_link_id,
  l.event_id,
  e.start_date as event_date,
  e.title as event_title,
  l.linked_id as mobile_asset_id,
  v.name as vessel_name,
  v.imo,
  v.mmsi,
  v.flag,
  v.subtype as vessel_type,
  l.relationship,
  l.confidence,
  l.source_id,
  l.metadata
from pc_event_links l
join pc_events e on e.event_id=l.event_id
join pc_mobile_assets v
  on pc_linked_type_to_entity_type(l.linked_type)='mobile_asset'
 and v.mobile_asset_id=l.linked_id;

-- Extend the relationship-resolution view with apply state.
-- PostgreSQL cannot rename/reorder existing view columns with CREATE OR REPLACE VIEW.
-- Drop and recreate this admin view because SQL 012 adds apply-state columns.
drop view if exists pc_v_relationship_resolution;
create view pc_v_relationship_resolution as
select
  r.staged_relationship_id,
  r.ingestion_job_id,
  r.source_staged_record_id as staged_record_id,
  s.created_at,
  s.natural_key,
  s.target_table,
  s.review_status,
  s.validation_status,
  r.relationship_type,
  r.from_entity_type,
  r.from_source_key,
  r.from_name,
  r.resolved_from_entity_id,
  r.from_resolution_method,
  r.from_resolution_confidence,
  r.from_candidate_count,
  r.to_entity_type,
  r.to_source_key,
  r.to_identifier_type,
  r.to_identifier_value,
  r.to_name,
  r.resolved_to_entity_id,
  r.to_resolution_method,
  r.to_resolution_confidence,
  r.to_candidate_count,
  r.resolution_status,
  r.existing_relationship_id,
  r.apply_status,
  r.canonical_relationship_id,
  r.applied_at,
  r.apply_error,
  r.confidence,
  r.source_id,
  r.resolved_at,
  r.metadata
from pc_staged_relationships r
left join pc_staged_records s on s.staged_record_id=r.source_staged_record_id;

comment on function pc_apply_staged_event_relationship(uuid) is
  'Revalidates and promotes one READY staged event relationship into canonical pc_event_links, including vessel-to-event links.';
comment on function pc_apply_ready_event_relationships(uuid) is
  'Bulk-promotes READY event relationships after endpoint revalidation, skips duplicates, audits writes, and marks staging applied.';
comment on view pc_v_event_vessel_links is
  'Canonical event-to-vessel links joined to current vessel identity data for verification and client use.';

commit;
