-- Power & Corridors
-- 070_rapid_integrity_repair.sql
--
-- Fast deterministic cleanup:
--   1) fixes relationship endpoint TYPE mismatches where the referenced ID already exists
--      uniquely in another canonical object table
--   2) creates the missing HMS Duncan mobile-asset shell from the existing provisional entity
--      and repoints its event links
--   3) reclassifies the composite UK Ministry of Defence / Royal Navy shell so it is
--      no longer treated as a company
--
-- No fuzzy matching. No deletes. No broad merges.

begin;

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
-- 1. Deterministic relationship endpoint type corrections
-- ---------------------------------------------------------------------------

-- Snapshot relationships eligible for safe type repair.
insert into public.pc_model_repair_audit(
  repair_audit_id,repair_batch,object_type,object_id,repair_action,before_record
)
select
  'AUDIT_070_'||upper(substr(md5('rel_endpoint|'||t.relationship_id),1,24)),
  '070',
  'relationship',
  t.relationship_id,
  'repair_endpoint_type',
  to_jsonb(r)
from public.pc_v_invalid_relationship_endpoint_triage t
join public.pc_relationships r
  on r.relationship_id::text=t.relationship_id
where t.repair_class in ('source_type_mismatch','target_type_mismatch')
on conflict (repair_audit_id) do nothing;

-- Repair source type where deterministic.
update public.pc_relationships r
set source_type=t.suggested_source_type,
    metadata=coalesce(r.metadata,'{}'::jsonb)
      || jsonb_build_object(
           'endpoint_type_repair',
           jsonb_build_object(
             'batch','070',
             'side','source',
             'previous_type',r.source_type,
             'new_type',t.suggested_source_type
           )
         ),
    updated_at=now()
from public.pc_v_invalid_relationship_endpoint_triage t
where r.relationship_id::text=t.relationship_id
  and t.repair_class='source_type_mismatch'
  and t.suggested_source_type is not null;

-- Repair target type where deterministic.
update public.pc_relationships r
set target_type=t.suggested_target_type,
    metadata=coalesce(r.metadata,'{}'::jsonb)
      || jsonb_build_object(
           'endpoint_type_repair',
           jsonb_build_object(
             'batch','070',
             'side','target',
             'previous_type',r.target_type,
             'new_type',t.suggested_target_type
           )
         ),
    updated_at=now()
from public.pc_v_invalid_relationship_endpoint_triage t
where r.relationship_id::text=t.relationship_id
  and t.repair_class='target_type_mismatch'
  and t.suggested_target_type is not null;

-- Fill after snapshots for endpoint repairs.
update public.pc_model_repair_audit a
set after_record=to_jsonb(r)
from public.pc_relationships r
where a.repair_batch='070'
  and a.repair_action='repair_endpoint_type'
  and a.object_id=r.relationship_id::text;


-- ---------------------------------------------------------------------------
-- 2. HMS Duncan: missing mobile asset canonical object
-- ---------------------------------------------------------------------------
-- Create only if:
--   * the provisional entity shell exists
--   * no exact-normalized mobile asset exists already
-- ---------------------------------------------------------------------------

insert into public.pc_model_repair_audit(
  repair_audit_id,repair_batch,object_type,object_id,repair_action,before_record
)
select
  'AUDIT_070_'||upper(substr(md5('hms_duncan|'||e.entity_id::text),1,24)),
  '070',
  'entity',
  e.entity_id::text,
  'create_mobile_asset_and_repoint',
  to_jsonb(e)
from public.pc_entities e
where e.entity_id::text='ENTITY_AI_063523CE108C9BE2BD91'
on conflict (repair_audit_id) do nothing;

insert into public.pc_mobile_assets(
  mobile_asset_id,
  name,
  asset_type,
  subtype,
  status,
  record_status,
  data_quality,
  metadata,
  created_at,
  updated_at
)
select
  'MOBILE_REPAIR_HMS_DUNCAN',
  e.name,
  'vessel',
  'naval vessel',
  'Active',
  'provisional',
  'medium',
  jsonb_build_object(
    'classification_repair',
    jsonb_build_object(
      'batch','070',
      'source_entity_id',e.entity_id,
      'reason','mobile asset was previously stored only as a provisional company entity'
    ),
    'research_attributes',
    jsonb_build_object(
      'canonical_name',e.name,
      'service','Royal Navy'
    )
  ),
  now(),
  now()
from public.pc_entities e
where e.entity_id::text='ENTITY_AI_063523CE108C9BE2BD91'
  and not exists (
    select 1
    from public.pc_mobile_assets m
    where public.pc_norm_identity_text(m.name)=public.pc_norm_identity_text(e.name)
  )
on conflict (mobile_asset_id) do nothing;

-- Repoint event links from the bad entity shell to whichever exact HMS Duncan
-- mobile asset now exists (created above or pre-existing).
with exact_duncan as (
  select m.mobile_asset_id::text mobile_asset_id
  from public.pc_mobile_assets m
  where public.pc_norm_identity_text(m.name)=public.pc_norm_identity_text('HMS Duncan')
  order by case when m.mobile_asset_id::text='MOBILE_REPAIR_HMS_DUNCAN' then 0 else 1 end,
           m.created_at
  limit 1
)
update public.pc_event_links el
set linked_type='mobile_asset',
    linked_id=d.mobile_asset_id
from exact_duncan d
where lower(coalesce(el.linked_type,'')) in ('entity','company','organisation','organization')
  and el.linked_id::text='ENTITY_AI_063523CE108C9BE2BD91';

-- Record after state.
update public.pc_model_repair_audit a
set after_record=(
  select jsonb_build_object(
    'mobile_asset',
      (select to_jsonb(m)
       from public.pc_mobile_assets m
       where public.pc_norm_identity_text(m.name)=public.pc_norm_identity_text('HMS Duncan')
       order by case when m.mobile_asset_id::text='MOBILE_REPAIR_HMS_DUNCAN' then 0 else 1 end,
                m.created_at
       limit 1),
    'event_links',
      (select coalesce(jsonb_agg(to_jsonb(el)),'[]'::jsonb)
       from public.pc_event_links el
       where lower(coalesce(el.linked_type,''))='mobile_asset'
         and el.linked_id::text in (
           select m.mobile_asset_id::text
           from public.pc_mobile_assets m
           where public.pc_norm_identity_text(m.name)=public.pc_norm_identity_text('HMS Duncan')
         ))
  )
)
where a.repair_batch='070'
  and a.repair_action='create_mobile_asset_and_repoint'
  and a.object_id='ENTITY_AI_063523CE108C9BE2BD91';


-- ---------------------------------------------------------------------------
-- 3. Composite UK Ministry of Defence / Royal Navy shell
-- ---------------------------------------------------------------------------
insert into public.pc_model_repair_audit(
  repair_audit_id,repair_batch,object_type,object_id,repair_action,before_record
)
select
  'AUDIT_070_'||upper(substr(md5('composite|'||e.entity_id::text),1,24)),
  '070',
  'entity',
  e.entity_id::text,
  'mark_composite_identity',
  to_jsonb(e)
from public.pc_entities e
where e.entity_id::text='ENTITY_AI_F3F4355697A527EC5AB8'
on conflict (repair_audit_id) do nothing;

update public.pc_entities
set entity_type='composite_identity',
    subtype='government_defence_composite',
    metadata=coalesce(metadata,'{}'::jsonb)
      || jsonb_build_object(
           'classification_repair',
           jsonb_build_object(
             'batch','070',
             'previous_entity_type',entity_type,
             'reason','record combines UK Ministry of Defence and Royal Navy; requires later identity split'
           )
         ),
    updated_at=now()
where entity_id::text='ENTITY_AI_F3F4355697A527EC5AB8'
  and lower(coalesce(entity_type,''))='company';

update public.pc_model_repair_audit a
set after_record=to_jsonb(e)
from public.pc_entities e
where a.repair_batch='070'
  and a.repair_action='mark_composite_identity'
  and a.object_id=e.entity_id::text;


-- ---------------------------------------------------------------------------
-- 4. Normalize and refresh
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
-- select * from public.pc_v_model_integrity_triage_summary;
-- select * from public.pc_v_model_audit_summary;
-- select * from public.pc_v_classification_resolution_summary;
--
-- select repair_action,count(*)
-- from public.pc_model_repair_audit
-- where repair_batch='070'
-- group by repair_action
-- order by repair_action;
--
-- select *
-- from public.pc_v_invalid_relationship_endpoint_triage
-- order by repair_class,relationship_id;
