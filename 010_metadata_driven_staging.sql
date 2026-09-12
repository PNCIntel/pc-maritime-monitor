-- Power & Corridors Trade System
-- 010_metadata_driven_staging.sql
-- Metadata-driven model registry, entity resolution, identifiers, and generic staging.
-- PostgreSQL / Supabase
-- Designed as an additive migration over 001_core_platform.sql through 009_trade_system_expansion.sql.

begin;

create extension if not exists pgcrypto;
create extension if not exists pg_trgm;

-- ============================================================================
-- 1. MODEL REGISTRY: THE DATABASE DESCRIBES ITS OWN CANONICAL MODEL
-- ============================================================================

create table if not exists pc_meta_entity_types (
  entity_type text primary key,
  table_name text not null unique,
  primary_key_column text not null,
  display_name_column text,
  id_prefix text,
  canonical boolean not null default true,
  active boolean not null default true,
  allow_insert boolean not null default true,
  allow_update boolean not null default true,
  description text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists pc_meta_columns (
  meta_column_id uuid primary key default gen_random_uuid(),
  entity_type text not null references pc_meta_entity_types(entity_type) on delete cascade,
  table_name text not null,
  column_name text not null,
  ordinal_position integer,
  data_type text,
  udt_name text,
  nullable boolean,
  required boolean not null default false,
  is_primary_key boolean not null default false,
  is_natural_key boolean not null default false,
  identifier_type text,
  match_priority integer,
  normalizer text,
  reference_entity_type text references pc_meta_entity_types(entity_type),
  reference_column text,
  allow_stage boolean not null default true,
  allow_update boolean not null default true,
  metadata jsonb not null default '{}'::jsonb,
  unique(entity_type, column_name)
);
create index if not exists idx_pc_meta_columns_table on pc_meta_columns(table_name, ordinal_position);
create index if not exists idx_pc_meta_columns_identifier on pc_meta_columns(entity_type, identifier_type) where identifier_type is not null;

create table if not exists pc_meta_relationship_types (
  relationship_type text primary key,
  from_entity_type text not null references pc_meta_entity_types(entity_type),
  to_entity_type text not null references pc_meta_entity_types(entity_type),
  relationship_table text not null,
  from_key_column text not null,
  to_key_column text not null,
  relationship_type_column text,
  inverse_relationship_type text,
  cardinality text,
  active boolean not null default true,
  description text,
  metadata jsonb not null default '{}'::jsonb
);

create table if not exists pc_meta_match_rules (
  match_rule_id uuid primary key default gen_random_uuid(),
  entity_type text not null references pc_meta_entity_types(entity_type) on delete cascade,
  priority integer not null,
  rule_name text not null,
  match_type text not null check (match_type in ('IDENTIFIER','FIELD_EXACT','FIELD_NORMALIZED','FIELD_FUZZY')),
  source_column text,
  identifier_type text,
  canonical_column text,
  comparison_method text not null default 'exact',
  minimum_score numeric not null default 1.0,
  required boolean not null default false,
  active boolean not null default true,
  metadata jsonb not null default '{}'::jsonb,
  unique(entity_type, priority, rule_name)
);
create index if not exists idx_pc_meta_match_rules_entity on pc_meta_match_rules(entity_type, active, priority);

-- ============================================================================
-- 2. CANONICAL IDENTIFIER REGISTRY
--    Keeps external/natural identifiers separate from P&C canonical keys.
-- ============================================================================

create table if not exists pc_entity_identifiers (
  identifier_id uuid primary key default gen_random_uuid(),
  entity_type text not null references pc_meta_entity_types(entity_type),
  entity_id text not null,
  identifier_type text not null,
  identifier_value text not null,
  normalized_value text not null,
  issuer text,
  is_primary boolean not null default false,
  valid_from date,
  valid_to date,
  source_id text references pc_sources(source_id),
  confidence numeric,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(entity_type, identifier_type, normalized_value)
);
create index if not exists idx_pc_identifiers_lookup on pc_entity_identifiers(entity_type, identifier_type, normalized_value);
create index if not exists idx_pc_identifiers_entity on pc_entity_identifiers(entity_type, entity_id);

-- ============================================================================
-- 3. EXTEND EXISTING STAGED RECORDS WITHOUT BREAKING POWER ADMIN
-- ============================================================================

alter table pc_staged_records add column if not exists target_entity_type text references pc_meta_entity_types(entity_type);
alter table pc_staged_records add column if not exists source_record_key text;
alter table pc_staged_records add column if not exists resolution_status text not null default 'UNRESOLVED';
alter table pc_staged_records add column if not exists resolved_entity_id text;
alter table pc_staged_records add column if not exists resolution_method text;
alter table pc_staged_records add column if not exists resolution_confidence numeric;
alter table pc_staged_records add column if not exists candidate_count integer;
alter table pc_staged_records add column if not exists resolution_details jsonb not null default '{}'::jsonb;

create index if not exists idx_pc_stage_resolution on pc_staged_records(resolution_status, target_entity_type);
create index if not exists idx_pc_stage_job_entity on pc_staged_records(ingestion_job_id, target_entity_type);

-- EAV/attribute staging layer requested for generic imports.
-- pc_staged_records remains the record envelope and raw JSON compatibility layer.
create table if not exists pc_staged_values (
  staged_value_id uuid primary key default gen_random_uuid(),
  staged_record_id uuid not null references pc_staged_records(staged_record_id) on delete cascade,
  entity_type text references pc_meta_entity_types(entity_type),
  table_name text not null,
  column_name text not null,
  value_text text,
  value_json jsonb,
  value_type text,
  ordinal integer not null default 1,
  normalized_value text,
  validation_status text not null default 'pending',
  validation_message text,
  created_at timestamptz not null default now(),
  unique(staged_record_id, table_name, column_name, ordinal)
);
create index if not exists idx_pc_staged_values_record on pc_staged_values(staged_record_id);
create index if not exists idx_pc_staged_values_lookup on pc_staged_values(entity_type, column_name, normalized_value);

create table if not exists pc_staged_relationships (
  staged_relationship_id uuid primary key default gen_random_uuid(),
  ingestion_job_id uuid references pc_ingestion_jobs(ingestion_job_id) on delete cascade,
  source_staged_record_id uuid references pc_staged_records(staged_record_id) on delete set null,
  relationship_type text,

  from_entity_type text not null references pc_meta_entity_types(entity_type),
  from_source_key text,
  from_identifier_type text,
  from_identifier_value text,
  from_name text,
  resolved_from_entity_id text,

  to_entity_type text not null references pc_meta_entity_types(entity_type),
  to_source_key text,
  to_identifier_type text,
  to_identifier_value text,
  to_name text,
  resolved_to_entity_id text,

  valid_from date,
  valid_to date,
  confidence numeric,
  source_id text references pc_sources(source_id),
  resolution_status text not null default 'UNRESOLVED',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists idx_pc_staged_rel_status on pc_staged_relationships(resolution_status, relationship_type);

create table if not exists pc_resolution_log (
  resolution_id bigserial primary key,
  ingestion_job_id uuid references pc_ingestion_jobs(ingestion_job_id) on delete set null,
  staged_record_id uuid references pc_staged_records(staged_record_id) on delete set null,
  staged_relationship_id uuid references pc_staged_relationships(staged_relationship_id) on delete set null,
  entity_type text,
  candidate_entity_id text,
  rule_used text,
  score numeric,
  decision text not null,
  details jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists idx_pc_resolution_log_record on pc_resolution_log(staged_record_id, created_at desc);

-- ============================================================================
-- 4. NORMALIZATION HELPERS
-- ============================================================================

create or replace function pc_normalize_name(p_value text)
returns text
language sql
immutable
as $$
  select nullif(trim(regexp_replace(upper(coalesce(p_value,'')), '[^A-Z0-9]+', ' ', 'g')), '');
$$;

create or replace function pc_normalize_imo(p_value text)
returns text
language sql
immutable
as $$
  select case
    when regexp_replace(coalesce(p_value,''), '[^0-9]', '', 'g') ~ '^[0-9]{7}$'
      then regexp_replace(p_value, '[^0-9]', '', 'g')
    else null
  end;
$$;

create or replace function pc_normalize_identifier(p_identifier_type text, p_value text)
returns text
language plpgsql
immutable
as $$
begin
  if p_value is null then return null; end if;
  case upper(coalesce(p_identifier_type,''))
    when 'IMO' then return pc_normalize_imo(p_value);
    when 'MMSI' then return nullif(regexp_replace(p_value, '[^0-9]', '', 'g'),'');
    when 'UNLOCODE' then return nullif(regexp_replace(upper(p_value), '[^A-Z0-9]', '', 'g'),'');
    when 'LEI' then return nullif(regexp_replace(upper(p_value), '[^A-Z0-9]', '', 'g'),'');
    when 'TICKER' then return nullif(upper(trim(p_value)),'');
    else return pc_normalize_name(p_value);
  end case;
end;
$$;

-- ============================================================================
-- 5. MODEL REGISTRY REFRESH FROM INFORMATION_SCHEMA
-- ============================================================================

create or replace function pc_refresh_model_registry()
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  v_count integer;
begin
  insert into pc_meta_columns (
    entity_type, table_name, column_name, ordinal_position, data_type, udt_name,
    nullable, required, is_primary_key
  )
  select
    e.entity_type,
    c.table_name,
    c.column_name,
    c.ordinal_position,
    c.data_type,
    c.udt_name,
    (c.is_nullable = 'YES'),
    (c.is_nullable = 'NO' and c.column_default is null),
    (c.column_name = e.primary_key_column)
  from pc_meta_entity_types e
  join information_schema.columns c
    on c.table_schema = 'public'
   and c.table_name = e.table_name
  on conflict (entity_type, column_name) do update set
    table_name = excluded.table_name,
    ordinal_position = excluded.ordinal_position,
    data_type = excluded.data_type,
    udt_name = excluded.udt_name,
    nullable = excluded.nullable,
    required = excluded.required,
    is_primary_key = excluded.is_primary_key;

  get diagnostics v_count = row_count;
  return v_count;
end;
$$;

-- ============================================================================
-- 6. EXPAND JSON PAYLOAD INTO COLUMN/VALUE STAGING
-- ============================================================================

create or replace function pc_expand_staged_payload(p_staged_record_id uuid)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  v_table text;
  v_entity_type text;
  v_payload jsonb;
  v_count integer := 0;
  r record;
begin
  select s.target_table, coalesce(s.target_entity_type, e.entity_type), s.payload
    into v_table, v_entity_type, v_payload
  from pc_staged_records s
  left join pc_meta_entity_types e on e.table_name = s.target_table
  where s.staged_record_id = p_staged_record_id;

  if not found then
    raise exception 'Unknown staged_record_id %', p_staged_record_id;
  end if;

  update pc_staged_records
     set target_entity_type = coalesce(target_entity_type, v_entity_type)
   where staged_record_id = p_staged_record_id;

  for r in
    select key, value
    from jsonb_each(coalesce(v_payload, '{}'::jsonb))
  loop
    insert into pc_staged_values(
      staged_record_id, entity_type, table_name, column_name,
      value_text, value_json, value_type, normalized_value
    ) values (
      p_staged_record_id,
      v_entity_type,
      v_table,
      r.key,
      case when jsonb_typeof(r.value) in ('string','number','boolean','null')
           then trim(both '"' from r.value::text) end,
      r.value,
      jsonb_typeof(r.value),
      case
        when r.key in ('name','title','asset_name','company_name','vessel_name')
          then pc_normalize_name(trim(both '"' from r.value::text))
        when r.key = 'imo'
          then pc_normalize_imo(trim(both '"' from r.value::text))
        else null
      end
    )
    on conflict (staged_record_id, table_name, column_name, ordinal)
    do update set
      entity_type = excluded.entity_type,
      value_text = excluded.value_text,
      value_json = excluded.value_json,
      value_type = excluded.value_type,
      normalized_value = excluded.normalized_value;
    v_count := v_count + 1;
  end loop;

  return v_count;
end;
$$;

-- ============================================================================
-- 7. IDENTIFIER REGISTRATION / EXISTING DATA BACKFILL
-- ============================================================================

create or replace function pc_register_identifier(
  p_entity_type text,
  p_entity_id text,
  p_identifier_type text,
  p_identifier_value text,
  p_source_id text default null,
  p_is_primary boolean default false,
  p_confidence numeric default 1.0
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_normalized text;
  v_id uuid;
begin
  v_normalized := pc_normalize_identifier(p_identifier_type, p_identifier_value);
  if v_normalized is null then return null; end if;

  insert into pc_entity_identifiers(
    entity_type, entity_id, identifier_type, identifier_value,
    normalized_value, source_id, is_primary, confidence
  ) values (
    p_entity_type, p_entity_id, upper(p_identifier_type), p_identifier_value,
    v_normalized, p_source_id, p_is_primary, p_confidence
  )
  on conflict (entity_type, identifier_type, normalized_value)
  do update set
    identifier_value = excluded.identifier_value,
    source_id = coalesce(excluded.source_id, pc_entity_identifiers.source_id),
    is_primary = pc_entity_identifiers.is_primary or excluded.is_primary,
    confidence = greatest(coalesce(pc_entity_identifiers.confidence,0), coalesce(excluded.confidence,0)),
    updated_at = now()
  returning identifier_id into v_id;

  return v_id;
end;
$$;

-- ============================================================================
-- 8. METADATA-DRIVEN STAGED RECORD RESOLUTION
--    Exact identifiers first; then exact/normalized fields. Fuzzy matches are
--    logged as candidates but deliberately not auto-promoted here.
-- ============================================================================

create or replace function pc_resolve_staged_record(p_staged_record_id uuid)
returns table(
  resolution_status text,
  resolved_entity_id text,
  resolution_method text,
  resolution_confidence numeric,
  candidate_count integer
)
language plpgsql
security definer
set search_path = public
as $$
declare
  s pc_staged_records%rowtype;
  e pc_meta_entity_types%rowtype;
  r pc_meta_match_rules%rowtype;
  v_value text;
  v_norm text;
  v_candidate text;
  v_count integer;
  v_sql text;
  v_status text := 'NEW';
  v_method text := 'NO_MATCH';
  v_conf numeric := 0;
  v_candidates integer := 0;
begin
  select * into s from pc_staged_records where staged_record_id = p_staged_record_id;
  if not found then raise exception 'Unknown staged_record_id %', p_staged_record_id; end if;

  select * into e
  from pc_meta_entity_types
  where active and (entity_type = s.target_entity_type or table_name = s.target_table)
  order by case when entity_type = s.target_entity_type then 0 else 1 end
  limit 1;

  if not found then
    update pc_staged_records set resolution_status='INVALID', resolution_method='NO_ENTITY_METADATA'
    where staged_record_id=p_staged_record_id;
    return query select 'INVALID'::text, null::text, 'NO_ENTITY_METADATA'::text, 0::numeric, 0;
    return;
  end if;

  update pc_staged_records set target_entity_type=e.entity_type where staged_record_id=p_staged_record_id;
  perform pc_expand_staged_payload(p_staged_record_id);

  for r in
    select * from pc_meta_match_rules
    where entity_type=e.entity_type and active
    order by priority
  loop
    v_value := null;

    if r.source_column is not null then
      select coalesce(value_text, trim(both '"' from value_json::text))
        into v_value
      from pc_staged_values
      where staged_record_id=p_staged_record_id
        and column_name=r.source_column
      order by ordinal
      limit 1;

      if v_value is null and s.payload ? r.source_column then
        v_value := trim(both '"' from (s.payload -> r.source_column)::text);
      end if;
    end if;

    if coalesce(trim(v_value),'') = '' then
      if r.required then
        continue;
      else
        continue;
      end if;
    end if;

    if r.match_type = 'IDENTIFIER' then
      v_norm := pc_normalize_identifier(r.identifier_type, v_value);
      select count(*), min(entity_id)
        into v_count, v_candidate
      from pc_entity_identifiers
      where entity_type=e.entity_type
        and identifier_type=upper(r.identifier_type)
        and normalized_value=v_norm;

      if v_count = 1 then
        v_status := 'MATCHED'; v_method := r.rule_name; v_conf := 1.0; v_candidates := 1;
        exit;
      elsif v_count > 1 then
        v_status := 'AMBIGUOUS'; v_method := r.rule_name; v_conf := 0.0; v_candidates := v_count;
        exit;
      end if;

    elsif r.match_type = 'FIELD_EXACT' then
      v_sql := format('select count(*), min(%I::text) from %I where %I::text = $1',
                      e.primary_key_column, e.table_name, coalesce(r.canonical_column,r.source_column));
      execute v_sql into v_count, v_candidate using v_value;
      if v_count = 1 then
        v_status := 'MATCHED'; v_method := r.rule_name; v_conf := 1.0; v_candidates := 1;
        exit;
      elsif v_count > 1 then
        v_status := 'AMBIGUOUS'; v_method := r.rule_name; v_conf := 0.0; v_candidates := v_count;
        exit;
      end if;

    elsif r.match_type = 'FIELD_NORMALIZED' then
      v_norm := pc_normalize_name(v_value);
      v_sql := format('select count(*), min(%I::text) from %I where pc_normalize_name(%I::text) = $1',
                      e.primary_key_column, e.table_name, coalesce(r.canonical_column,r.source_column));
      execute v_sql into v_count, v_candidate using v_norm;
      if v_count = 1 then
        v_status := 'MATCHED'; v_method := r.rule_name; v_conf := r.minimum_score; v_candidates := 1;
        exit;
      elsif v_count > 1 then
        v_status := 'AMBIGUOUS'; v_method := r.rule_name; v_conf := 0.0; v_candidates := v_count;
        exit;
      end if;

    elsif r.match_type = 'FIELD_FUZZY' then
      -- Candidate generation only. Never auto-match fuzzy candidates at this layer.
      v_norm := pc_normalize_name(v_value);
      v_sql := format(
        'select %I::text, similarity(pc_normalize_name(%I::text), $1) as score '
        'from %I where similarity(pc_normalize_name(%I::text), $1) >= $2 '
        'order by score desc limit 5',
        e.primary_key_column, coalesce(r.canonical_column,r.source_column),
        e.table_name, coalesce(r.canonical_column,r.source_column)
      );
      -- We intentionally do not execute fuzzy dynamic candidate promotion here.
      -- Power Admin / AI review may use the metadata rule and threshold to inspect candidates.
    end if;
  end loop;

  if v_status = 'NEW' then v_candidate := null; end if;

  update pc_staged_records
     set resolution_status=v_status,
         resolved_entity_id=v_candidate,
         resolution_method=v_method,
         resolution_confidence=v_conf,
         candidate_count=v_candidates,
         resolution_details=jsonb_build_object('entity_type',e.entity_type,'table_name',e.table_name)
   where staged_record_id=p_staged_record_id;

  insert into pc_resolution_log(
    ingestion_job_id, staged_record_id, entity_type, candidate_entity_id,
    rule_used, score, decision, details
  ) values (
    s.ingestion_job_id, p_staged_record_id, e.entity_type, v_candidate,
    v_method, v_conf, v_status,
    jsonb_build_object('candidate_count',v_candidates,'target_table',e.table_name)
  );

  return query select v_status, v_candidate, v_method, v_conf, v_candidates;
end;
$$;

create or replace function pc_process_ingestion_job(p_ingestion_job_id uuid)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  r record;
  v_total integer := 0;
  v_matched integer := 0;
  v_new integer := 0;
  v_ambiguous integer := 0;
  v_invalid integer := 0;
  v_result record;
begin
  for r in
    select staged_record_id
    from pc_staged_records
    where ingestion_job_id=p_ingestion_job_id
      and review_status not in ('rejected','applied')
    order by created_at, staged_record_id
  loop
    v_total := v_total + 1;
    select * into v_result from pc_resolve_staged_record(r.staged_record_id);
    case v_result.resolution_status
      when 'MATCHED' then v_matched := v_matched + 1;
      when 'NEW' then v_new := v_new + 1;
      when 'AMBIGUOUS' then v_ambiguous := v_ambiguous + 1;
      else v_invalid := v_invalid + 1;
    end case;
  end loop;

  update pc_ingestion_jobs
  set stats = coalesce(stats,'{}'::jsonb) || jsonb_build_object(
      'resolved_total',v_total,
      'matched',v_matched,
      'new',v_new,
      'ambiguous',v_ambiguous,
      'invalid',v_invalid,
      'resolved_at',now()
    )
  where ingestion_job_id=p_ingestion_job_id;

  return jsonb_build_object(
    'total',v_total,'matched',v_matched,'new',v_new,
    'ambiguous',v_ambiguous,'invalid',v_invalid
  );
end;
$$;

-- ============================================================================
-- 9. SEED THE LOGICAL MODEL FOR CURRENT CORE TABLES
-- ============================================================================

insert into pc_meta_entity_types(entity_type,table_name,primary_key_column,display_name_column,id_prefix,description)
values
  ('entity','pc_entities','entity_id','name','ENTITY','Company, organization, authority, person or other canonical entity'),
  ('asset','pc_assets','asset_id','name','ASSET','Fixed infrastructure asset: port, terminal, airport, dry port, logistics node, etc.'),
  ('mobile_asset','pc_mobile_assets','mobile_asset_id','name','MOBILE','Mobile asset: vessel, aircraft, rolling stock or other mobile platform'),
  ('event','pc_events','event_id','title','EVENT','Canonical event record'),
  ('relationship','pc_relationships','relationship_id',null,'REL','Canonical cross-entity relationship'),
  ('event_link','pc_event_links','event_link_id','linked_name','ELINK','Link between an event and another canonical object'),
  ('geography','pc_geographies','geo_id','name','GEO','Canonical geography/watch area'),
  ('source','pc_sources','source_id','source_name','SRC','Canonical source registry'),
  ('transport_route','pc_transport_routes','route_id','route_name','ROUTE','Rail, road, pipeline, inland waterway, air cargo or multimodal route'),
  ('chokepoint','pc_chokepoints','chokepoint_id','name','CHOKE','Strategic physical chokepoint')
on conflict (entity_type) do update set
  table_name=excluded.table_name,
  primary_key_column=excluded.primary_key_column,
  display_name_column=excluded.display_name_column,
  id_prefix=excluded.id_prefix,
  description=excluded.description,
  updated_at=now();

-- Current high-confidence match rules.
insert into pc_meta_match_rules(entity_type,priority,rule_name,match_type,source_column,identifier_type,canonical_column,comparison_method,minimum_score,required)
values
  ('mobile_asset',10,'IMO_EXACT','IDENTIFIER','imo','IMO',null,'exact',1.0,false),
  ('mobile_asset',20,'MMSI_EXACT','IDENTIFIER','mmsi','MMSI',null,'exact',1.0,false),
  ('mobile_asset',30,'VESSEL_NAME_NORMALIZED','FIELD_NORMALIZED','name',null,'name','normalized',1.0,false),
  ('entity',10,'ENTITY_NAME_NORMALIZED','FIELD_NORMALIZED','name',null,'name','normalized',1.0,false),
  ('asset',10,'ASSET_NAME_NORMALIZED','FIELD_NORMALIZED','name',null,'name','normalized',1.0,false),
  ('event',10,'EVENT_ID_EXACT','FIELD_EXACT','event_id',null,'event_id','exact',1.0,false),
  ('source',10,'SOURCE_ID_EXACT','FIELD_EXACT','source_id',null,'source_id','exact',1.0,false),
  ('geography',10,'GEO_NAME_NORMALIZED','FIELD_NORMALIZED','name',null,'name','normalized',1.0,false)
on conflict (entity_type,priority,rule_name) do update set
  match_type=excluded.match_type,
  source_column=excluded.source_column,
  identifier_type=excluded.identifier_type,
  canonical_column=excluded.canonical_column,
  comparison_method=excluded.comparison_method,
  minimum_score=excluded.minimum_score,
  required=excluded.required,
  active=true;

-- Mark identifier/natural-key metadata after information_schema refresh.
select pc_refresh_model_registry();

update pc_meta_columns set is_natural_key=true, identifier_type='IMO', match_priority=10, normalizer='pc_normalize_imo'
where entity_type='mobile_asset' and column_name='imo';
update pc_meta_columns set is_natural_key=true, identifier_type='MMSI', match_priority=20, normalizer='pc_normalize_identifier'
where entity_type='mobile_asset' and column_name='mmsi';
update pc_meta_columns set is_natural_key=true, match_priority=30, normalizer='pc_normalize_name'
where entity_type='mobile_asset' and column_name='name';
update pc_meta_columns set is_natural_key=true, match_priority=10, normalizer='pc_normalize_name'
where entity_type in ('entity','asset','geography') and column_name='name';

-- Backfill existing vessel identifiers. Canonical P&C ids remain untouched.
insert into pc_entity_identifiers(entity_type,entity_id,identifier_type,identifier_value,normalized_value,is_primary,source_id,confidence)
select 'mobile_asset', mobile_asset_id, 'IMO', imo, pc_normalize_imo(imo), true, source_id, 1.0
from pc_mobile_assets
where pc_normalize_imo(imo) is not null
on conflict (entity_type,identifier_type,normalized_value) do nothing;

insert into pc_entity_identifiers(entity_type,entity_id,identifier_type,identifier_value,normalized_value,is_primary,source_id,confidence)
select 'mobile_asset', mobile_asset_id, 'MMSI', mmsi, pc_normalize_identifier('MMSI',mmsi), false, source_id, 1.0
from pc_mobile_assets
where pc_normalize_identifier('MMSI',mmsi) is not null
on conflict (entity_type,identifier_type,normalized_value) do nothing;

-- Backfill target_entity_type on existing stage rows from registered table metadata.
update pc_staged_records s
set target_entity_type=e.entity_type
from pc_meta_entity_types e
where s.target_entity_type is null and s.target_table=e.table_name;

-- Expand existing staged payloads so the new EAV layer is immediately useful.
do $$
declare r record;
begin
  for r in select staged_record_id from pc_staged_records loop
    perform pc_expand_staged_payload(r.staged_record_id);
  end loop;
end $$;

-- ============================================================================
-- 10. MODEL INTROSPECTION VIEWS FOR POWER ADMIN / DOCUMENTATION
-- ============================================================================

create or replace view pc_v_model_registry as
select
  e.entity_type,
  e.table_name,
  e.primary_key_column,
  e.display_name_column,
  e.id_prefix,
  e.active,
  c.column_name,
  c.ordinal_position,
  c.data_type,
  c.nullable,
  c.required,
  c.is_primary_key,
  c.is_natural_key,
  c.identifier_type,
  c.match_priority,
  c.reference_entity_type,
  c.reference_column
from pc_meta_entity_types e
left join pc_meta_columns c on c.entity_type=e.entity_type
order by e.entity_type, c.ordinal_position;

create or replace view pc_v_staging_resolution as
select
  s.staged_record_id,
  s.ingestion_job_id,
  s.target_entity_type,
  s.target_table,
  s.natural_key,
  s.source_record_key,
  s.action,
  s.validation_status,
  s.review_status,
  s.resolution_status,
  s.resolved_entity_id,
  s.resolution_method,
  s.resolution_confidence,
  s.candidate_count,
  s.source_id,
  s.created_at,
  count(v.staged_value_id) as staged_value_count
from pc_staged_records s
left join pc_staged_values v on v.staged_record_id=s.staged_record_id
group by s.staged_record_id;

comment on table pc_meta_entity_types is 'Executable registry of logical P&C entity types and their canonical tables.';
comment on table pc_meta_columns is 'Metadata registry for canonical columns, keys, identifier semantics, references and staging behaviour.';
comment on table pc_entity_identifiers is 'Canonical registry of external/natural identifiers mapped to P&C canonical ids.';
comment on table pc_staged_values is 'Generic column/value staging layer. One staged record may contain many target table/column/value rows.';
comment on function pc_resolve_staged_record(uuid) is 'Resolves one staged record against metadata-driven match rules without directly writing canonical data.';
comment on function pc_process_ingestion_job(uuid) is 'Runs metadata-driven resolution across an ingestion job and records results for analyst review.';

commit;
