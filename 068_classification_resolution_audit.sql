-- Power & Corridors
-- 068_classification_resolution_audit.sql
-- Resolves known classification anomalies against the correct canonical tables.
--
-- READ-ONLY. No records are moved, merged, deleted, or retyped.

begin;

create or replace view public.pc_v_classification_resolution_candidates as
with anomalies as (
  select *
  from public.pc_v_entity_classification_anomalies
),
base as (
  select
    a.*,
    public.pc_norm_identity_text(a.name) as normalized_name,
    case
      when a.anomaly_type='possible_mobile_asset_stored_as_entity' then 'mobile_asset'
      when a.anomaly_type='possible_physical_asset_stored_as_entity' then 'asset'
      when a.anomaly_type='possible_public_body_misclassified_as_company' then 'entity'
      when a.anomaly_type='possible_security_actor_misclassified_as_company' then 'entity'
      else 'review'
    end as expected_object_type
  from anomalies a
),
resolved as (
  select
    b.*,

    -- exact normalized mobile-asset matches
    (
      select count(*)
      from public.pc_mobile_assets m
      where public.pc_norm_identity_text(m.name)=b.normalized_name
    ) as mobile_exact_match_count,

    (
      select jsonb_agg(jsonb_build_object(
        'mobile_asset_id',m.mobile_asset_id,
        'name',m.name,
        'asset_type',m.asset_type,
        'subtype',m.subtype,
        'imo',m.imo,
        'flag',m.flag,
        'record_status',m.record_status
      ))
      from public.pc_mobile_assets m
      where public.pc_norm_identity_text(m.name)=b.normalized_name
    ) as mobile_exact_matches,

    -- exact normalized fixed-asset matches
    (
      select count(*)
      from public.pc_assets x
      where public.pc_norm_identity_text(x.name)=b.normalized_name
    ) as asset_exact_match_count,

    (
      select jsonb_agg(jsonb_build_object(
        'asset_id',x.asset_id,
        'name',x.name,
        'asset_type',x.asset_type,
        'subtype',x.subtype,
        'country',x.country,
        'region_city',x.region_city,
        'record_status',x.record_status
      ))
      from public.pc_assets x
      where public.pc_norm_identity_text(x.name)=b.normalized_name
    ) as asset_exact_matches,

    -- alternate canonical entity shells with the same normalized name
    (
      select count(*)
      from public.pc_entities e2
      where e2.entity_id::text<>b.entity_id::text
        and public.pc_norm_identity_text(e2.name)=b.normalized_name
    ) as alternate_entity_match_count,

    (
      select jsonb_agg(jsonb_build_object(
        'entity_id',e2.entity_id,
        'name',e2.name,
        'entity_type',e2.entity_type,
        'subtype',e2.subtype,
        'hq_country',e2.hq_country,
        'record_status',e2.record_status
      ))
      from public.pc_entities e2
      where e2.entity_id::text<>b.entity_id::text
        and public.pc_norm_identity_text(e2.name)=b.normalized_name
    ) as alternate_entity_matches,

    -- how many live graph edges use the misclassified entity
    (
      select count(*)
      from public.pc_relationships r
      where (lower(coalesce(r.source_type,''))='entity' and r.source_id::text=b.entity_id::text)
         or (lower(coalesce(r.target_type,''))='entity' and r.target_id::text=b.entity_id::text)
    ) as generic_relationship_count,

    (
      select jsonb_agg(to_jsonb(r))
      from public.pc_relationships r
      where (lower(coalesce(r.source_type,''))='entity' and r.source_id::text=b.entity_id::text)
         or (lower(coalesce(r.target_type,''))='entity' and r.target_id::text=b.entity_id::text)
    ) as generic_relationships,

    (
      select count(*)
      from public.pc_event_links el
      where lower(coalesce(el.linked_type,'')) in ('entity','company','organisation','organization')
        and el.linked_id::text=b.entity_id::text
    ) as event_link_count

  from base b
)
select
  r.*,
  case
    when r.entity_id in (
      'ENTITY_AUTO_3FB34BFF94A1BB95C095',
      'ENTITY_AUTO_CF905548CFCA9B790F35'
    )
      then 'likely_false_positive_company_name'

    when r.expected_object_type='mobile_asset'
      and r.mobile_exact_match_count=1
      then 'safe_candidate_repoint_to_existing_mobile_asset'

    when r.expected_object_type='mobile_asset'
      and r.mobile_exact_match_count=0
      then 'mobile_asset_missing_needs_canonical_creation'

    when r.expected_object_type='mobile_asset'
      and r.mobile_exact_match_count>1
      then 'ambiguous_mobile_asset_match'

    when r.expected_object_type='asset'
      and r.asset_exact_match_count=1
      then 'safe_candidate_repoint_to_existing_asset'

    when r.expected_object_type='asset'
      and r.asset_exact_match_count=0
      then 'physical_asset_missing_needs_canonical_creation'

    when r.expected_object_type='asset'
      and r.asset_exact_match_count>1
      then 'ambiguous_asset_match'

    when r.expected_object_type='entity'
      and r.alternate_entity_match_count=1
      then 'safe_candidate_merge_to_existing_entity'

    when r.expected_object_type='entity'
      and r.alternate_entity_match_count=0
      then 'same_entity_retype_candidate'

    when r.expected_object_type='entity'
      and r.alternate_entity_match_count>1
      then 'ambiguous_entity_identity'

    else 'manual_review'
  end as resolution_class,

  case
    when r.name='Dubai Police' then 'government_agency'
    when r.name='U.S. Department of the Treasury' then 'government_agency'
    when r.name='UK Ministry of Defence' then 'government_ministry'
    when r.name='UK Ministry of Defence / Royal Navy' then 'composite_identity_review'
    when r.name='Vietnam Ministry of Industry and Trade' then 'government_ministry'
    when r.name='Houthi forces' then 'armed_group'
    when r.name='Yemeni government forces' then 'military_force'
    else null
  end as suggested_entity_type

from resolved r;


create or replace view public.pc_v_classification_resolution_summary as
select resolution_class,count(*)::bigint issue_count
from public.pc_v_classification_resolution_candidates
group by resolution_class
order by resolution_class;

grant select on public.pc_v_classification_resolution_candidates to authenticated,service_role;
grant select on public.pc_v_classification_resolution_summary to authenticated,service_role;

commit;

-- Recommended:
--
-- select * from public.pc_v_classification_resolution_summary;
--
-- select
--   entity_id,name,entity_type,anomaly_type,expected_object_type,
--   mobile_exact_match_count,asset_exact_match_count,alternate_entity_match_count,
--   generic_relationship_count,event_link_count,resolution_class,suggested_entity_type,
--   mobile_exact_matches,asset_exact_matches,alternate_entity_matches
-- from public.pc_v_classification_resolution_candidates
-- order by resolution_class,name;
