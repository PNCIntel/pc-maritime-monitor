-- Power & Corridors SQL 011
-- Metadata-driven relationship resolution
-- PostgreSQL / Supabase
-- Run AFTER 010_metadata_driven_staging.sql

begin;

-- ---------------------------------------------------------------------------
-- 1. Relationship-resolution audit fields
-- ---------------------------------------------------------------------------

alter table pc_staged_relationships add column if not exists from_resolution_method text;
alter table pc_staged_relationships add column if not exists from_resolution_confidence numeric;
alter table pc_staged_relationships add column if not exists from_candidate_count integer;
alter table pc_staged_relationships add column if not exists to_resolution_method text;
alter table pc_staged_relationships add column if not exists to_resolution_confidence numeric;
alter table pc_staged_relationships add column if not exists to_candidate_count integer;
alter table pc_staged_relationships add column if not exists existing_relationship_id text;
alter table pc_staged_relationships add column if not exists resolution_details jsonb not null default '{}'::jsonb;
alter table pc_staged_relationships add column if not exists resolved_at timestamptz;

create index if not exists idx_pc_staged_rel_source_record
  on pc_staged_relationships(source_staged_record_id)
  where source_staged_record_id is not null;

-- ---------------------------------------------------------------------------
-- 2. Relationship metadata for the polymorphic pc_event_links table
-- ---------------------------------------------------------------------------

insert into pc_meta_relationship_types(
  relationship_type,from_entity_type,to_entity_type,relationship_table,
  from_key_column,to_key_column,relationship_type_column,cardinality,description,metadata
)
values
  ('event_to_mobile_asset','event','mobile_asset','pc_event_links','event_id','linked_id','relationship','N:N',
   'Event linked to a vessel or other mobile asset.', '{"linked_type":"mobile_asset"}'::jsonb),
  ('event_to_entity','event','entity','pc_event_links','event_id','linked_id','relationship','N:N',
   'Event linked to a company, organization or person entity.', '{"linked_type":"entity"}'::jsonb),
  ('event_to_asset','event','asset','pc_event_links','event_id','linked_id','relationship','N:N',
   'Event linked to a fixed asset such as a port, terminal or infrastructure site.', '{"linked_type":"asset"}'::jsonb),
  ('event_to_geography','event','geography','pc_event_links','event_id','linked_id','relationship','N:N',
   'Event linked to a canonical geography.', '{"linked_type":"geography"}'::jsonb)
on conflict (relationship_type) do update set
  from_entity_type=excluded.from_entity_type,
  to_entity_type=excluded.to_entity_type,
  relationship_table=excluded.relationship_table,
  from_key_column=excluded.from_key_column,
  to_key_column=excluded.to_key_column,
  relationship_type_column=excluded.relationship_type_column,
  active=true,
  description=excluded.description,
  metadata=excluded.metadata;

-- ---------------------------------------------------------------------------
-- 3. Endpoint type normalization
-- ---------------------------------------------------------------------------

create or replace function pc_linked_type_to_entity_type(p_linked_type text)
returns text
language plpgsql
immutable
as $$
declare v text := lower(trim(coalesce(p_linked_type,'')));
begin
  if v in ('mobile_asset','mobile asset','vessel','ship','aircraft','rolling_stock','rolling stock') then
    return 'mobile_asset';
  elsif v in ('entity','company','organization','organisation','person','operator','owner','manager') then
    return 'entity';
  elsif v in ('asset','port','terminal','airport','rail_terminal','rail terminal','facility','infrastructure') then
    return 'asset';
  elsif v in ('event') then
    return 'event';
  elsif v in ('geography','geo','location','country','region') then
    return 'geography';
  end if;
  return nullif(v,'');
end;
$$;

-- ---------------------------------------------------------------------------
-- 4. Generic endpoint resolver
--    Order: canonical ID -> external identifier -> normalized exact name.
--    It deliberately does not auto-resolve fuzzy names.
-- ---------------------------------------------------------------------------

create or replace function pc_resolve_reference(
  p_entity_type text,
  p_direct_id text default null,
  p_identifier_type text default null,
  p_identifier_value text default null,
  p_name text default null
)
returns table(
  endpoint_status text,
  entity_id text,
  resolution_method text,
  resolution_confidence numeric,
  candidate_count integer
)
language plpgsql
security definer
set search_path=public
as $$
declare
  e pc_meta_entity_types%rowtype;
  v_sql text;
  v_count integer := 0;
  v_id text;
  v_norm text;
begin
  select * into e
  from pc_meta_entity_types
  where entity_type=p_entity_type and active
  limit 1;

  if not found then
    return query select 'INVALID_TYPE'::text,null::text,'UNKNOWN_ENTITY_TYPE'::text,0::numeric,0;
    return;
  end if;

  -- 1. Direct canonical ID.
  if nullif(trim(p_direct_id),'') is not null then
    v_sql := format(
      'select count(*), min(%I::text) from %I where %I::text=$1',
      e.primary_key_column,e.table_name,e.primary_key_column
    );
    execute v_sql into v_count,v_id using trim(p_direct_id);
    if v_count=1 then
      return query select 'MATCHED'::text,v_id,'CANONICAL_ID'::text,1.0::numeric,1;
      return;
    end if;
  end if;

  -- 2. External/natural identifier registry.
  if nullif(trim(p_identifier_type),'') is not null and nullif(trim(p_identifier_value),'') is not null then
    v_norm := pc_normalize_identifier(p_identifier_type,p_identifier_value);
    if v_norm is not null then
      select count(*),min(i.entity_id)
      into v_count,v_id
      from pc_entity_identifiers i
      where i.entity_type=p_entity_type
        and upper(i.identifier_type)=upper(trim(p_identifier_type))
        and i.normalized_value=v_norm;

      if v_count=1 then
        return query select 'MATCHED'::text,v_id,
          ('IDENTIFIER:'||upper(trim(p_identifier_type)))::text,1.0::numeric,1;
        return;
      elsif v_count>1 then
        return query select 'AMBIGUOUS'::text,null::text,
          ('IDENTIFIER:'||upper(trim(p_identifier_type)))::text,0.0::numeric,v_count;
        return;
      end if;
    end if;
  end if;

  -- 3. Exact normalized display name.
  if nullif(trim(p_name),'') is not null and e.display_name_column is not null then
    v_norm := pc_normalize_name(p_name);
    v_sql := format(
      'select count(*), min(%I::text) from %I where pc_normalize_name(%I::text)=$1',
      e.primary_key_column,e.table_name,e.display_name_column
    );
    execute v_sql into v_count,v_id using v_norm;

    if v_count=1 then
      return query select 'MATCHED'::text,v_id,'NORMALIZED_NAME'::text,0.98::numeric,1;
      return;
    elsif v_count>1 then
      return query select 'AMBIGUOUS'::text,null::text,'NORMALIZED_NAME'::text,0.0::numeric,v_count;
      return;
    end if;
  end if;

  return query select 'NOT_FOUND'::text,null::text,'NO_MATCH'::text,0::numeric,0;
end;
$$;

-- ---------------------------------------------------------------------------
-- 5. Convert an existing staged pc_event_links row into pc_staged_relationships
-- ---------------------------------------------------------------------------

create or replace function pc_stage_event_link_relationship(p_staged_record_id uuid)
returns uuid
language plpgsql
security definer
set search_path=public
as $$
declare
  s pc_staged_records%rowtype;
  p jsonb;
  m jsonb;
  v_rel_id uuid;
  v_to_type text;
  v_identifier_type text;
  v_identifier_value text;
  v_relationship text;
begin
  select * into s from pc_staged_records where staged_record_id=p_staged_record_id;
  if not found then raise exception 'Unknown staged record %',p_staged_record_id; end if;
  if s.target_table <> 'pc_event_links' then
    raise exception 'Staged record % targets %, not pc_event_links',p_staged_record_id,s.target_table;
  end if;

  p := coalesce(s.payload,'{}'::jsonb);
  m := case when jsonb_typeof(p->'metadata')='object' then p->'metadata' else '{}'::jsonb end;
  v_to_type := pc_linked_type_to_entity_type(p->>'linked_type');
  v_relationship := coalesce(nullif(p->>'relationship',''),'linked object');

  if nullif(m->>'imo','') is not null then
    v_identifier_type := 'IMO';
    v_identifier_value := m->>'imo';
  elsif nullif(m->>'mmsi','') is not null then
    v_identifier_type := 'MMSI';
    v_identifier_value := m->>'mmsi';
  end if;

  select staged_relationship_id into v_rel_id
  from pc_staged_relationships
  where source_staged_record_id=p_staged_record_id
  order by created_at desc
  limit 1;

  if v_rel_id is null then
    insert into pc_staged_relationships(
      ingestion_job_id,source_staged_record_id,relationship_type,
      from_entity_type,from_source_key,from_name,
      to_entity_type,to_source_key,to_identifier_type,to_identifier_value,to_name,
      confidence,source_id,resolution_status,metadata
    ) values (
      s.ingestion_job_id,s.staged_record_id,v_relationship,
      'event',p->>'event_id',p->>'event_id',
      coalesce(v_to_type,'mobile_asset'),p->>'linked_id',v_identifier_type,v_identifier_value,p->>'linked_name',
      coalesce(s.confidence,1.0),coalesce(s.source_id,p->>'source_id'),'UNRESOLVED',
      jsonb_build_object(
        'event_link_id',p->>'event_link_id',
        'linked_type',p->>'linked_type',
        'original_metadata',m
      )
    ) returning staged_relationship_id into v_rel_id;
  else
    update pc_staged_relationships set
      ingestion_job_id=s.ingestion_job_id,
      relationship_type=v_relationship,
      from_entity_type='event',
      from_source_key=p->>'event_id',
      from_name=p->>'event_id',
      to_entity_type=coalesce(v_to_type,to_entity_type),
      to_source_key=p->>'linked_id',
      to_identifier_type=v_identifier_type,
      to_identifier_value=v_identifier_value,
      to_name=p->>'linked_name',
      confidence=coalesce(s.confidence,confidence),
      source_id=coalesce(s.source_id,p->>'source_id',source_id),
      metadata=metadata || jsonb_build_object(
        'event_link_id',p->>'event_link_id',
        'linked_type',p->>'linked_type',
        'original_metadata',m
      )
    where staged_relationship_id=v_rel_id;
  end if;

  return v_rel_id;
end;
$$;

-- ---------------------------------------------------------------------------
-- 6. Resolve a staged relationship
-- ---------------------------------------------------------------------------

create or replace function pc_resolve_staged_relationship(p_staged_relationship_id uuid)
returns table(
  resolution_status text,
  resolved_from_entity_id text,
  resolved_to_entity_id text,
  resolution_method text,
  resolution_confidence numeric,
  candidate_count integer,
  existing_relationship_id text
)
language plpgsql
security definer
set search_path=public
as $$
declare
  r pc_staged_relationships%rowtype;
  fr record;
  tr record;
  v_status text;
  v_method text;
  v_conf numeric;
  v_candidates integer;
  v_existing text;
  v_linked_type text;
  v_event_link_id text;
begin
  select * into r from pc_staged_relationships where staged_relationship_id=p_staged_relationship_id;
  if not found then raise exception 'Unknown staged relationship %',p_staged_relationship_id; end if;

  select * into fr from pc_resolve_reference(
    r.from_entity_type,r.from_source_key,r.from_identifier_type,r.from_identifier_value,r.from_name
  );
  select * into tr from pc_resolve_reference(
    r.to_entity_type,r.to_source_key,r.to_identifier_type,r.to_identifier_value,r.to_name
  );

  v_candidates := greatest(coalesce(fr.candidate_count,0),coalesce(tr.candidate_count,0));
  v_conf := least(coalesce(fr.resolution_confidence,0),coalesce(tr.resolution_confidence,0));
  v_method := coalesce(fr.resolution_method,'NO_MATCH') || ' -> ' || coalesce(tr.resolution_method,'NO_MATCH');

  if fr.endpoint_status='AMBIGUOUS' or tr.endpoint_status='AMBIGUOUS' then
    v_status := 'AMBIGUOUS';
  elsif fr.endpoint_status<>'MATCHED' then
    -- The relationship cannot exist if the parent/source endpoint itself is missing.
    v_status := 'BROKEN_REFERENCE';
  elsif tr.endpoint_status<>'MATCHED' then
    -- Parent exists but target needs creation/research/linkage.
    v_status := 'PARTIAL';
  else
    -- Both endpoints resolved. Check existing canonical relationship.
    if r.from_entity_type='event' then
      v_linked_type := case r.to_entity_type
        when 'mobile_asset' then 'mobile_asset'
        when 'entity' then 'entity'
        when 'asset' then 'asset'
        when 'geography' then 'geography'
        else r.to_entity_type end;

      select l.event_link_id into v_existing
      from pc_event_links l
      where l.event_id=fr.entity_id
        and pc_linked_type_to_entity_type(l.linked_type)=r.to_entity_type
        and l.linked_id=tr.entity_id
        and coalesce(l.relationship,'')=coalesce(r.relationship_type,'')
      order by l.event_link_id
      limit 1;
    end if;

    if v_existing is not null then
      v_status := 'ALREADY_EXISTS';
    else
      v_status := 'READY';
    end if;
  end if;

  update pc_staged_relationships set
    resolved_from_entity_id=fr.entity_id,
    resolved_to_entity_id=tr.entity_id,
    from_resolution_method=fr.resolution_method,
    from_resolution_confidence=fr.resolution_confidence,
    from_candidate_count=fr.candidate_count,
    to_resolution_method=tr.resolution_method,
    to_resolution_confidence=tr.resolution_confidence,
    to_candidate_count=tr.candidate_count,
    resolution_status=v_status,
    existing_relationship_id=v_existing,
    resolution_details=jsonb_build_object(
      'from_status',fr.endpoint_status,
      'to_status',tr.endpoint_status,
      'from_method',fr.resolution_method,
      'to_method',tr.resolution_method
    ),
    resolved_at=now()
  where staged_relationship_id=p_staged_relationship_id;

  -- Mirror the relationship decision to the staged-record envelope used by Power Admin.
  if r.source_staged_record_id is not null then
    update pc_staged_records set
      resolution_status=v_status,
      resolved_entity_id=tr.entity_id,
      resolution_method='RELATIONSHIP: '||v_method,
      resolution_confidence=v_conf,
      candidate_count=v_candidates,
      resolution_details=coalesce(resolution_details,'{}'::jsonb) || jsonb_build_object(
        'staged_relationship_id',p_staged_relationship_id,
        'resolved_from_entity_id',fr.entity_id,
        'resolved_to_entity_id',tr.entity_id,
        'existing_relationship_id',v_existing,
        'relationship_status',v_status
      )
    where staged_record_id=r.source_staged_record_id;

    -- If target ID was resolved by IMO/name rather than the incoming linked_id,
    -- correct the staged payload proposal before analyst review.
    if tr.entity_id is not null then
      update pc_staged_records
      set payload=jsonb_set(payload,'{linked_id}',to_jsonb(tr.entity_id),true)
      where staged_record_id=r.source_staged_record_id;
    end if;
  end if;

  insert into pc_resolution_log(
    ingestion_job_id,staged_record_id,staged_relationship_id,entity_type,
    candidate_entity_id,rule_used,score,decision,details
  ) values (
    r.ingestion_job_id,r.source_staged_record_id,r.staged_relationship_id,r.to_entity_type,
    tr.entity_id,v_method,v_conf,v_status,
    jsonb_build_object('from_status',fr.endpoint_status,'to_status',tr.endpoint_status,'existing_relationship_id',v_existing)
  );

  return query select v_status,fr.entity_id,tr.entity_id,v_method,v_conf,v_candidates,v_existing;
end;
$$;

-- ---------------------------------------------------------------------------
-- 7. Resolve one pc_event_links staged record and whole backlogs
-- ---------------------------------------------------------------------------

create or replace function pc_resolve_event_link_staged_record(p_staged_record_id uuid)
returns jsonb
language plpgsql
security definer
set search_path=public
as $$
declare
  v_rel uuid;
  x record;
begin
  v_rel := pc_stage_event_link_relationship(p_staged_record_id);
  select * into x from pc_resolve_staged_relationship(v_rel);
  return jsonb_build_object(
    'staged_record_id',p_staged_record_id,
    'staged_relationship_id',v_rel,
    'status',x.resolution_status,
    'from_id',x.resolved_from_entity_id,
    'to_id',x.resolved_to_entity_id,
    'method',x.resolution_method,
    'confidence',x.resolution_confidence,
    'candidate_count',x.candidate_count,
    'existing_relationship_id',x.existing_relationship_id
  );
end;
$$;

create or replace function pc_process_relationship_backlog(p_ingestion_job_id uuid default null)
returns jsonb
language plpgsql
security definer
set search_path=public
as $$
declare
  s record;
  x jsonb;
  n_total integer:=0;
  n_ready integer:=0;
  n_exists integer:=0;
  n_partial integer:=0;
  n_ambiguous integer:=0;
  n_broken integer:=0;
  n_invalid integer:=0;
  v_status text;
begin
  for s in
    select staged_record_id
    from pc_staged_records
    where target_table='pc_event_links'
      and (p_ingestion_job_id is null or ingestion_job_id=p_ingestion_job_id)
      and review_status not in ('applied','rejected')
    order by created_at,staged_record_id
  loop
    n_total:=n_total+1;
    begin
      x:=pc_resolve_event_link_staged_record(s.staged_record_id);
      v_status:=x->>'status';
      if v_status='READY' then n_ready:=n_ready+1;
      elsif v_status='ALREADY_EXISTS' then n_exists:=n_exists+1;
      elsif v_status='PARTIAL' then n_partial:=n_partial+1;
      elsif v_status='AMBIGUOUS' then n_ambiguous:=n_ambiguous+1;
      elsif v_status='BROKEN_REFERENCE' then n_broken:=n_broken+1;
      else n_invalid:=n_invalid+1;
      end if;
    exception when others then
      n_invalid:=n_invalid+1;
      update pc_staged_records set
        resolution_status='INVALID',resolution_method='RELATIONSHIP_ERROR',
        resolution_details=coalesce(resolution_details,'{}'::jsonb)||jsonb_build_object('error',sqlerrm)
      where staged_record_id=s.staged_record_id;
    end;
  end loop;

  return jsonb_build_object(
    'total',n_total,
    'ready',n_ready,
    'already_exists',n_exists,
    'partial',n_partial,
    'ambiguous',n_ambiguous,
    'broken_reference',n_broken,
    'invalid',n_invalid
  );
end;
$$;

-- ---------------------------------------------------------------------------
-- 8. Power Admin views
-- ---------------------------------------------------------------------------

create or replace view pc_v_relationship_resolution as
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
  r.confidence,
  r.source_id,
  r.resolved_at,
  r.metadata
from pc_staged_relationships r
left join pc_staged_records s on s.staged_record_id=r.source_staged_record_id;

create or replace view pc_v_relationship_resolution_summary as
select
  resolution_status,
  count(*) as records
from pc_staged_relationships
group by resolution_status
order by resolution_status;

-- ---------------------------------------------------------------------------
-- 9. Backfill and resolve the existing pc_event_links staging backlog.
--    This performs NO canonical inserts/updates.
-- ---------------------------------------------------------------------------

select pc_process_relationship_backlog(null);

comment on function pc_resolve_reference(text,text,text,text,text) is
  'Metadata-driven endpoint resolver: canonical id, identifier registry, then normalized exact name.';
comment on function pc_resolve_staged_relationship(uuid) is
  'Resolves both endpoints of a staged relationship and classifies READY/PARTIAL/AMBIGUOUS/BROKEN_REFERENCE/ALREADY_EXISTS.';
comment on function pc_process_relationship_backlog(uuid) is
  'Resolves staged pc_event_links relationship proposals without writing canonical relationships.';

commit;
