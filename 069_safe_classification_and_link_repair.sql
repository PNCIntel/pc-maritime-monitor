-- Power & Corridors
-- 069_safe_classification_and_link_repair.sql
--
-- Applies ONLY the safe repairs identified by 068:
--   * repoint exact event links from misclassified entity shells to existing canonical assets/mobile assets
--   * retype clearly misclassified government/security entities in place
--
-- Explicitly NOT touched:
--   * HMS Duncan (correct mobile asset does not yet exist)
--   * UK Ministry of Defence / Royal Navy (composite identity)
--   * WILHELMSEN AHRENKIEL SHIP (likely legitimate company name)
--   * ZHIYUAN INTERNATIONAL SHIP (likely legitimate company name)

begin;

-- ---------------------------------------------------------------------------
-- 1. Snapshot affected rows for auditability
-- ---------------------------------------------------------------------------
create table if not exists public.pc_model_repair_audit (
  repair_audit_id text primary key,
  repair_batch text not null,
  object_type text not null,
  object_id text not null,
  repair_action text not null,
  before_record jsonb,
  after_record jsonb,
  created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- 2. Repoint event links to existing canonical objects
-- ---------------------------------------------------------------------------

-- HMS Prince of Wales: entity shell -> existing mobile asset
insert into public.pc_model_repair_audit(
  repair_audit_id,repair_batch,object_type,object_id,repair_action,before_record
)
select
  'AUDIT_069_'||upper(substr(md5('event_links|ENTITY_AI_72C75936CC0799066D06'),1,24)),
  '069','entity','ENTITY_AI_72C75936CC0799066D06',
  'repoint_event_links_to_mobile_asset',
  coalesce(jsonb_agg(to_jsonb(el)),'[]'::jsonb)
from public.pc_event_links el
where lower(coalesce(el.linked_type,'')) in ('entity','company','organisation','organization')
  and el.linked_id::text='ENTITY_AI_72C75936CC0799066D06'
on conflict (repair_audit_id) do nothing;

update public.pc_event_links
set linked_type='mobile_asset',
    linked_id='MOBILE_AI_730DEBDAAFFD72E64B55'
where lower(coalesce(linked_type,'')) in ('entity','company','organisation','organization')
  and linked_id::text='ENTITY_AI_72C75936CC0799066D06';

-- HMS Queen Elizabeth: entity shell -> existing mobile asset
insert into public.pc_model_repair_audit(
  repair_audit_id,repair_batch,object_type,object_id,repair_action,before_record
)
select
  'AUDIT_069_'||upper(substr(md5('event_links|ENTITY_AI_5C1D528272E899557726'),1,24)),
  '069','entity','ENTITY_AI_5C1D528272E899557726',
  'repoint_event_links_to_mobile_asset',
  coalesce(jsonb_agg(to_jsonb(el)),'[]'::jsonb)
from public.pc_event_links el
where lower(coalesce(el.linked_type,'')) in ('entity','company','organisation','organization')
  and el.linked_id::text='ENTITY_AI_5C1D528272E899557726'
on conflict (repair_audit_id) do nothing;

update public.pc_event_links
set linked_type='mobile_asset',
    linked_id='MOBILE_AI_B866A98EAD3431AD5F74'
where lower(coalesce(linked_type,'')) in ('entity','company','organisation','organization')
  and linked_id::text='ENTITY_AI_5C1D528272E899557726';

-- HMNB Portsmouth: entity shell -> existing fixed asset
insert into public.pc_model_repair_audit(
  repair_audit_id,repair_batch,object_type,object_id,repair_action,before_record
)
select
  'AUDIT_069_'||upper(substr(md5('event_links|ENTITY_AI_E9840ED39162A47928E8'),1,24)),
  '069','entity','ENTITY_AI_E9840ED39162A47928E8',
  'repoint_event_links_to_asset',
  coalesce(jsonb_agg(to_jsonb(el)),'[]'::jsonb)
from public.pc_event_links el
where lower(coalesce(el.linked_type,'')) in ('entity','company','organisation','organization')
  and el.linked_id::text='ENTITY_AI_E9840ED39162A47928E8'
on conflict (repair_audit_id) do nothing;

update public.pc_event_links
set linked_type='asset',
    linked_id='ASSET_AI_HMNB_PORTSMOUTH_C35CFB8923'
where lower(coalesce(linked_type,'')) in ('entity','company','organisation','organization')
  and linked_id::text='ENTITY_AI_E9840ED39162A47928E8';

-- ---------------------------------------------------------------------------
-- 3. Retype clearly misclassified entities in place
-- ---------------------------------------------------------------------------
with fixes(entity_id,new_type) as (
  values
    ('ENTITY_AI_0FC44F24937F7D41269D','government_agency'),
    ('ENTITY_AI_1393C6216DEB1012F04D','government_agency'),
    ('ENTITY_AI_02ABC1F8F65D82056DED','government_ministry'),
    ('ENTITY_AI_D5C2E835B5E91C1AA98F','government_ministry'),
    ('ENTITY_AI_1F773FFB09DF96D578BB','armed_group'),
    ('ENTITY_AI_742B537F08A308199F84','military_force')
)
insert into public.pc_model_repair_audit(
  repair_audit_id,repair_batch,object_type,object_id,repair_action,before_record
)
select
  'AUDIT_069_'||upper(substr(md5('entity_retype|'||e.entity_id::text),1,24)),
  '069','entity',e.entity_id::text,
  'retype_entity',
  to_jsonb(e)
from public.pc_entities e
join fixes f on f.entity_id=e.entity_id::text
on conflict (repair_audit_id) do nothing;

with fixes(entity_id,new_type) as (
  values
    ('ENTITY_AI_0FC44F24937F7D41269D','government_agency'),
    ('ENTITY_AI_1393C6216DEB1012F04D','government_agency'),
    ('ENTITY_AI_02ABC1F8F65D82056DED','government_ministry'),
    ('ENTITY_AI_D5C2E835B5E91C1AA98F','government_ministry'),
    ('ENTITY_AI_1F773FFB09DF96D578BB','armed_group'),
    ('ENTITY_AI_742B537F08A308199F84','military_force')
)
update public.pc_entities e
set entity_type=f.new_type,
    metadata=coalesce(e.metadata,'{}'::jsonb)
      || jsonb_build_object(
           'classification_repair',
           jsonb_build_object(
             'batch','069',
             'previous_entity_type',e.entity_type,
             'reason','safe classification repair from 068 audit'
           )
         ),
    updated_at=now()
from fixes f
where e.entity_id::text=f.entity_id;

-- Fill after_record for retyped entities.
update public.pc_model_repair_audit a
set after_record=to_jsonb(e)
from public.pc_entities e
where a.repair_batch='069'
  and a.repair_action='retype_entity'
  and a.object_id=e.entity_id::text;

-- Fill after_record for repointed link repairs.
update public.pc_model_repair_audit a
set after_record=(
  case a.object_id
    when 'ENTITY_AI_72C75936CC0799066D06' then
      (select coalesce(jsonb_agg(to_jsonb(el)),'[]'::jsonb)
       from public.pc_event_links el
       where lower(coalesce(el.linked_type,''))='mobile_asset'
         and el.linked_id::text='MOBILE_AI_730DEBDAAFFD72E64B55')
    when 'ENTITY_AI_5C1D528272E899557726' then
      (select coalesce(jsonb_agg(to_jsonb(el)),'[]'::jsonb)
       from public.pc_event_links el
       where lower(coalesce(el.linked_type,''))='mobile_asset'
         and el.linked_id::text='MOBILE_AI_B866A98EAD3431AD5F74')
    when 'ENTITY_AI_E9840ED39162A47928E8' then
      (select coalesce(jsonb_agg(to_jsonb(el)),'[]'::jsonb)
       from public.pc_event_links el
       where lower(coalesce(el.linked_type,''))='asset'
         and el.linked_id::text='ASSET_AI_HMNB_PORTSMOUTH_C35CFB8923')
    else a.after_record
  end
)
where a.repair_batch='069'
  and a.repair_action in ('repoint_event_links_to_mobile_asset','repoint_event_links_to_asset');

-- ---------------------------------------------------------------------------
-- 4. Refresh relationship fanout/read models after the repairs
-- ---------------------------------------------------------------------------
select public.pc_normalize_canonical_relationships();
select public.pc_fanout_mobile_asset_metadata_relationships(null);
select public.pc_refresh_terminal_indexes();

do $$
begin
  if to_regprocedure('public.pc_refresh_terminal_industrial_links()') is not null then
    perform public.pc_refresh_terminal_industrial_links();
  end if;
end $$;

commit;

-- ---------------------------------------------------------------------------
-- Validation
-- ---------------------------------------------------------------------------
-- select * from public.pc_v_classification_resolution_summary;
-- select * from public.pc_v_model_integrity_triage_summary;
-- select * from public.pc_v_model_audit_summary;
--
-- select repair_batch,repair_action,count(*)
-- from public.pc_model_repair_audit
-- where repair_batch='069'
-- group by repair_batch,repair_action
-- order by repair_action;
