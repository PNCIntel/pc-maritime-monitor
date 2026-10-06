-- Power & Corridors
-- 072_strategic_industrial_materialisation.sql
--
-- Materialises high-confidence strategic-industry structure already present in
-- canonical research metadata, with Irving Shipbuilding as the first targeted backfill.
-- Also restores the explicit Damen Naval -> Damen group corporate path.
--
-- Safety:
--   * exact canonical IDs / exact normalized programme names only
--   * no fuzzy entity matching
--   * no invented capacity figures
--   * new facility/programme records remain provisional/reported
--   * provenance is retained in metadata

begin;

-- ---------------------------------------------------------------------------
-- 1. Irving Halifax shipyard facility
-- ---------------------------------------------------------------------------
insert into public.pc_assets(
  asset_id,
  name,
  asset_type,
  subtype,
  country,
  region_city,
  operator_entity_id,
  record_status,
  data_quality,
  metadata,
  created_at,
  updated_at
)
select
  'ASSET_STRAT_IRVING_HALIFAX_SHIPYARD',
  'Halifax Shipyard',
  'shipyard',
  'naval_shipyard',
  'Canada',
  'Halifax, Nova Scotia',
  'COMP_IRVING',
  'provisional',
  'medium',
  jsonb_build_object(
    'materialisation','072',
    'materialisation_basis','Irving-built Canadian Coast Guard AOPS mobile assets identify Halifax, Nova Scotia as shipyard location',
    'inference_level','bounded',
    'source_mobile_asset_ids',jsonb_build_array(
      'MOBILE_FBBB0486AD609D1F',
      'MOBILE_04A0BEF409ACAFA1'
    )
  ),
  now(),
  now()
where exists (
  select 1 from public.pc_entities e
  where e.entity_id='COMP_IRVING'
)
and not exists (
  select 1 from public.pc_assets a
  where public.pc_norm_identity_text(a.name)=public.pc_norm_identity_text('Halifax Shipyard')
    and (
      lower(coalesce(a.asset_type,'')) like '%shipyard%'
      or lower(coalesce(a.subtype,'')) like '%shipyard%'
    )
);

-- If an exact Halifax Shipyard already existed, use it below. Otherwise use the
-- deterministic asset created above.


-- ---------------------------------------------------------------------------
-- 2. Canadian Coast Guard AOPS programme from exact structured metadata
-- ---------------------------------------------------------------------------
insert into public.pc_defence_programmes(
  programme_name,
  customer_entity_id,
  lead_contractor_entity_id,
  programme_type,
  programme_status,
  verification_status,
  metadata,
  created_at,
  updated_at
)
select
  'Canadian Coast Guard Arctic and Offshore Patrol Ships',
  (
    select e.entity_id
    from public.pc_entities e
    where public.pc_norm_identity_text(e.name)=public.pc_norm_identity_text('Canadian Coast Guard')
    group by e.entity_id
    having (
      select count(*)
      from public.pc_entities e2
      where public.pc_norm_identity_text(e2.name)=public.pc_norm_identity_text('Canadian Coast Guard')
    )=1
    limit 1
  ),
  'COMP_IRVING',
  'coast_guard',
  'active',
  'reported',
  jsonb_build_object(
    'materialisation','072',
    'materialisation_basis','Exact programme value stored in pc_mobile_assets.metadata.research_attributes.programme',
    'source_mobile_asset_ids',jsonb_build_array(
      'MOBILE_FBBB0486AD609D1F',
      'MOBILE_04A0BEF409ACAFA1'
    )
  ),
  now(),
  now()
where exists (
  select 1 from public.pc_entities e where e.entity_id='COMP_IRVING'
)
and exists (
  select 1
  from public.pc_mobile_assets m
  where m.mobile_asset_id in ('MOBILE_FBBB0486AD609D1F','MOBILE_04A0BEF409ACAFA1')
    and public.pc_norm_identity_text(m.metadata->'research_attributes'->>'programme')=
        public.pc_norm_identity_text('Canadian Coast Guard Arctic and Offshore Patrol Ships')
)
and not exists (
  select 1
  from public.pc_defence_programmes p
  where public.pc_norm_identity_text(p.programme_name)=
        public.pc_norm_identity_text('Canadian Coast Guard Arctic and Offshore Patrol Ships')
);


-- ---------------------------------------------------------------------------
-- 3. Irving participant role: builder at Halifax Shipyard
-- ---------------------------------------------------------------------------
insert into public.pc_defence_programme_participants(
  defence_programme_id,
  entity_id,
  shipyard_asset_id,
  participant_role,
  participation_status,
  verification_status,
  metadata,
  created_at,
  updated_at
)
select
  p.defence_programme_id,
  'COMP_IRVING',
  a.asset_id,
  'builder',
  'active',
  'reported',
  jsonb_build_object(
    'materialisation','072',
    'basis','builder/programme/shipyard values from structured mobile-asset research'
  ),
  now(),
  now()
from public.pc_defence_programmes p
join lateral (
  select a1.asset_id
  from public.pc_assets a1
  where public.pc_norm_identity_text(a1.name)=public.pc_norm_identity_text('Halifax Shipyard')
    and (
      lower(coalesce(a1.asset_type,'')) like '%shipyard%'
      or lower(coalesce(a1.subtype,'')) like '%shipyard%'
    )
  order by
    case when a1.asset_id='ASSET_STRAT_IRVING_HALIFAX_SHIPYARD' then 0 else 1 end,
    a1.created_at
  limit 1
) a on true
where public.pc_norm_identity_text(p.programme_name)=
      public.pc_norm_identity_text('Canadian Coast Guard Arctic and Offshore Patrol Ships')
and not exists (
  select 1
  from public.pc_defence_programme_participants pp
  where pp.defence_programme_id=p.defence_programme_id
    and pp.entity_id='COMP_IRVING'
    and pp.shipyard_asset_id=a.asset_id
    and lower(coalesce(pp.participant_role,''))='builder'
);


-- ---------------------------------------------------------------------------
-- 4. Production records for the two Irving AOPS vessels
-- ---------------------------------------------------------------------------
insert into public.pc_shipbuilding_production_tasks(
  defence_programme_id,
  shipyard_asset_id,
  builder_entity_id,
  task_type,
  task_status,
  verification_status,
  metadata,
  created_at,
  updated_at
)
select
  p.defence_programme_id,
  a.asset_id,
  'COMP_IRVING',
  'other',
  coalesce(nullif(m.status,''),'reported'),
  'reported',
  jsonb_build_object(
    'materialisation','072',
    'mobile_asset_id',m.mobile_asset_id,
    'mobile_asset_name',m.name,
    'research_attributes',coalesce(m.metadata->'research_attributes','{}'::jsonb),
    'basis','canonical mobile-asset builder/programme/shipyard metadata'
  ),
  now(),
  now()
from public.pc_mobile_assets m
cross join lateral (
  select p1.defence_programme_id
  from public.pc_defence_programmes p1
  where public.pc_norm_identity_text(p1.programme_name)=
        public.pc_norm_identity_text('Canadian Coast Guard Arctic and Offshore Patrol Ships')
  order by p1.created_at
  limit 1
) p
cross join lateral (
  select a1.asset_id
  from public.pc_assets a1
  where public.pc_norm_identity_text(a1.name)=public.pc_norm_identity_text('Halifax Shipyard')
    and (
      lower(coalesce(a1.asset_type,'')) like '%shipyard%'
      or lower(coalesce(a1.subtype,'')) like '%shipyard%'
    )
  order by
    case when a1.asset_id='ASSET_STRAT_IRVING_HALIFAX_SHIPYARD' then 0 else 1 end,
    a1.created_at
  limit 1
) a
where m.mobile_asset_id in ('MOBILE_FBBB0486AD609D1F','MOBILE_04A0BEF409ACAFA1')
  and public.pc_norm_identity_text(m.metadata->'research_attributes'->>'builder')=
      public.pc_norm_identity_text('Irving Shipbuilding Inc.')
  and not exists (
    select 1
    from public.pc_shipbuilding_production_tasks t
    where t.defence_programme_id=p.defence_programme_id
      and t.shipyard_asset_id=a.asset_id
      and t.builder_entity_id='COMP_IRVING'
      and t.metadata->>'mobile_asset_id'=m.mobile_asset_id
  );


-- ---------------------------------------------------------------------------
-- 5. Explicit generic relationships for Irving's materialised industrial graph
-- ---------------------------------------------------------------------------
insert into public.pc_relationships(
  relationship_id,source_type,source_id,relationship_type,target_type,target_id,
  confidence,record_status,notes,metadata
)
select
  'REL_072_'||upper(substr(md5('irving|operates|halifax|'||a.asset_id),1,24)),
  'entity','COMP_IRVING','operates_shipyard','asset',a.asset_id,
  'High','verified',
  'Materialised from Irving AOPS builder/shipyard research context',
  jsonb_build_object('materialisation','072','inference_level','bounded')
from public.pc_assets a
where public.pc_norm_identity_text(a.name)=public.pc_norm_identity_text('Halifax Shipyard')
  and (
    lower(coalesce(a.asset_type,'')) like '%shipyard%'
    or lower(coalesce(a.subtype,'')) like '%shipyard%'
  )
  and not exists (
    select 1 from public.pc_relationships r
    where lower(coalesce(r.source_type,''))='entity'
      and r.source_id='COMP_IRVING'
      and lower(coalesce(r.target_type,''))='asset'
      and r.target_id=a.asset_id
  )
order by case when a.asset_id='ASSET_STRAT_IRVING_HALIFAX_SHIPYARD' then 0 else 1 end
limit 1;

-- Programme lead relationship will also be generated by 064; this explicit insert
-- makes the materialised object immediately visible even before later refreshes.
insert into public.pc_relationships(
  relationship_id,source_type,source_id,relationship_type,target_type,target_id,
  confidence,record_status,notes,metadata
)
select
  'REL_072_'||upper(substr(md5('irving|lead|'||p.defence_programme_id::text),1,24)),
  'entity','COMP_IRVING','lead_contractor','programme',p.defence_programme_id::text,
  'High','verified',
  'Materialised from exact programme/builder metadata on Irving AOPS mobile assets',
  jsonb_build_object('materialisation','072')
from public.pc_defence_programmes p
where public.pc_norm_identity_text(p.programme_name)=
      public.pc_norm_identity_text('Canadian Coast Guard Arctic and Offshore Patrol Ships')
  and not exists (
    select 1 from public.pc_relationships r
    where lower(coalesce(r.source_type,''))='entity'
      and r.source_id='COMP_IRVING'
      and lower(coalesce(r.target_type,''))='programme'
      and r.target_id=p.defence_programme_id::text
  )
order by p.created_at
limit 1;


-- ---------------------------------------------------------------------------
-- 6. Damen Naval -> Damen Shipyards Group corporate path
-- ---------------------------------------------------------------------------
insert into public.pc_relationships(
  relationship_id,source_type,source_id,relationship_type,target_type,target_id,
  confidence,record_status,notes,metadata
)
select
  'REL_072_DAMEN_NAVAL_PARENT',
  'entity','COMP_DAMEN','parent_of','entity','ENT_SI_DAMEN_NAVAL',
  'High','verified',
  'Strategic-industry canonical family path',
  jsonb_build_object('materialisation','072')
where exists(select 1 from public.pc_entities where entity_id='COMP_DAMEN')
  and exists(select 1 from public.pc_entities where entity_id='ENT_SI_DAMEN_NAVAL')
  and not exists (
    select 1 from public.pc_relationships r
    where lower(coalesce(r.source_type,''))='entity'
      and r.source_id='COMP_DAMEN'
      and lower(coalesce(r.target_type,''))='entity'
      and r.target_id='ENT_SI_DAMEN_NAVAL'
      and lower(replace(coalesce(r.relationship_type,''),'_',' ')) in
          ('parent of','owns','controls','part of','subsidiary of')
  );


-- ---------------------------------------------------------------------------
-- 7. Re-run exact metadata fanout and shared graph materialisation
-- ---------------------------------------------------------------------------
select public.pc_normalize_canonical_relationships();
select public.pc_fanout_mobile_asset_metadata_relationships(null);
select public.pc_refresh_terminal_indexes();
select public.pc_refresh_terminal_industrial_links();

commit;

-- Validation:
-- select public.pc_strategic_entity_dossier('COMP_IRVING')->'counts';
-- select public.pc_strategic_entity_dossier('ENT_SI_DAMEN_NAVAL')->'counts';
-- select * from public.pc_model_audit_entity('COMP_IRVING');
