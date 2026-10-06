-- Power & Corridors
-- 067_model_integrity_triage.sql
-- Read-only integrity triage for invalid graph endpoints, duplicate canonical objects,
-- and obvious object-classification anomalies.
--
-- This migration DOES NOT merge, delete, reclassify, or rewrite relationships.

begin;

-- ---------------------------------------------------------------------------
-- 1. Invalid endpoint triage
--    Adds "where does this ID actually exist?" evidence to the 063 endpoint audit.
-- ---------------------------------------------------------------------------
create or replace view public.pc_v_invalid_relationship_endpoint_triage as
with base as (
    select a.*
    from public.pc_v_relationship_endpoint_audit a
),
typed as (
    select
      b.*,

      array_remove(array[
        case when exists(select 1 from public.pc_entities e where e.entity_id::text=b.source_id) then 'entity' end,
        case when exists(select 1 from public.pc_assets a where a.asset_id::text=b.source_id) then 'asset' end,
        case when exists(select 1 from public.pc_mobile_assets m where m.mobile_asset_id::text=b.source_id) then 'mobile_asset' end,
        case when exists(select 1 from public.pc_events ev where ev.event_id::text=b.source_id) then 'event' end,
        case when to_regclass('public.pc_defence_programmes') is not null
                  and exists(select 1 from public.pc_defence_programmes p where p.defence_programme_id::text=b.source_id)
             then 'programme' end,
        case when to_regclass('public.pc_security_operations') is not null
                  and exists(select 1 from public.pc_security_operations s where s.security_operation_id::text=b.source_id)
             then 'security_operation' end
      ],null) as source_id_exists_as,

      array_remove(array[
        case when exists(select 1 from public.pc_entities e where e.entity_id::text=b.target_id) then 'entity' end,
        case when exists(select 1 from public.pc_assets a where a.asset_id::text=b.target_id) then 'asset' end,
        case when exists(select 1 from public.pc_mobile_assets m where m.mobile_asset_id::text=b.target_id) then 'mobile_asset' end,
        case when exists(select 1 from public.pc_events ev where ev.event_id::text=b.target_id) then 'event' end,
        case when to_regclass('public.pc_defence_programmes') is not null
                  and exists(select 1 from public.pc_defence_programmes p where p.defence_programme_id::text=b.target_id)
             then 'programme' end,
        case when to_regclass('public.pc_security_operations') is not null
                  and exists(select 1 from public.pc_security_operations s where s.security_operation_id::text=b.target_id)
             then 'security_operation' end
      ],null) as target_id_exists_as
    from base b
)
select
  t.*,
  case
    when cardinality(source_id_exists_as)=1
      and lower(coalesce(source_type,''))<>lower(source_id_exists_as[1])
      then 'source_type_mismatch'
    when cardinality(target_id_exists_as)=1
      and lower(coalesce(target_type,''))<>lower(target_id_exists_as[1])
      then 'target_type_mismatch'
    when cardinality(source_id_exists_as)=0
      and issue like 'missing_source_%'
      then 'missing_source_object'
    when cardinality(target_id_exists_as)=0
      and issue like 'missing_target_%'
      then 'missing_target_object'
    when cardinality(source_id_exists_as)>1
      or cardinality(target_id_exists_as)>1
      then 'ambiguous_id_collision'
    else 'manual_review'
  end as repair_class,
  case
    when cardinality(source_id_exists_as)=1
      and lower(coalesce(source_type,''))<>lower(source_id_exists_as[1])
      then source_id_exists_as[1]
    else null
  end as suggested_source_type,
  case
    when cardinality(target_id_exists_as)=1
      and lower(coalesce(target_type,''))<>lower(target_id_exists_as[1])
      then target_id_exists_as[1]
    else null
  end as suggested_target_type
from typed t;


-- ---------------------------------------------------------------------------
-- 2. Duplicate entity groups
--    Exact normalized identity only; country is included to avoid cross-country
--    legal-name collisions.
-- ---------------------------------------------------------------------------
create or replace view public.pc_v_duplicate_entity_triage as
with normalized as (
  select
    e.*,
    public.pc_norm_identity_text(e.name) as normalized_name,
    public.pc_norm_identity_text(coalesce(e.hq_country,'')) as normalized_country
  from public.pc_entities e
),
groups as (
  select
    normalized_name,
    normalized_country,
    count(*)::bigint as record_count
  from normalized
  where normalized_name<>''
  group by normalized_name,normalized_country
  having count(*)>1
)
select
  g.normalized_name,
  g.normalized_country,
  g.record_count,
  jsonb_agg(
    jsonb_build_object(
      'entity_id',n.entity_id,
      'name',n.name,
      'entity_type',n.entity_type,
      'subtype',n.subtype,
      'hq_country',n.hq_country,
      'hq_city',n.hq_city,
      'record_status',n.record_status,
      'data_quality',n.data_quality,
      'created_at',n.created_at,
      'updated_at',n.updated_at
    )
    order by
      case when upper(n.entity_id::text) like 'ENTITY_AI_%'
             or upper(n.entity_id::text) like 'ENTITY_AUTO_%'
           then 1 else 0 end,
      n.created_at
  ) as records
from groups g
join normalized n
  on n.normalized_name=g.normalized_name
 and n.normalized_country=g.normalized_country
group by g.normalized_name,g.normalized_country,g.record_count;


-- ---------------------------------------------------------------------------
-- 3. Duplicate fixed-asset groups
--    Exact normalized name + country. Asset type is retained in the member list
--    because a port complex and a terminal can legitimately share a name.
-- ---------------------------------------------------------------------------
create or replace view public.pc_v_duplicate_asset_triage as
with normalized as (
  select
    a.*,
    public.pc_norm_identity_text(a.name) as normalized_name,
    public.pc_norm_identity_text(coalesce(a.country,'')) as normalized_country
  from public.pc_assets a
),
groups as (
  select
    normalized_name,
    normalized_country,
    count(*)::bigint as record_count
  from normalized
  where normalized_name<>''
  group by normalized_name,normalized_country
  having count(*)>1
)
select
  g.normalized_name,
  g.normalized_country,
  g.record_count,
  count(distinct public.pc_norm_identity_text(coalesce(n.asset_type,''))) as distinct_asset_types,
  jsonb_agg(
    jsonb_build_object(
      'asset_id',n.asset_id,
      'name',n.name,
      'asset_type',n.asset_type,
      'subtype',n.subtype,
      'country',n.country,
      'region_city',n.region_city,
      'owner_entity_id',n.owner_entity_id,
      'operator_entity_id',n.operator_entity_id,
      'record_status',n.record_status,
      'data_quality',n.data_quality,
      'created_at',n.created_at,
      'updated_at',n.updated_at
    )
    order by
      case when upper(n.asset_id::text) like 'ASSET_AI_%'
             or upper(n.asset_id::text) like 'ASSET_AUTO_%'
           then 1 else 0 end,
      n.created_at
  ) as records
from groups g
join normalized n
  on n.normalized_name=g.normalized_name
 and n.normalized_country=g.normalized_country
group by g.normalized_name,g.normalized_country,g.record_count;


-- ---------------------------------------------------------------------------
-- 4. Obvious entity/object classification anomalies
--    Candidate list only. Nothing is automatically reclassified.
-- ---------------------------------------------------------------------------
create or replace view public.pc_v_entity_classification_anomalies as
select
  e.entity_id,
  e.name,
  e.entity_type,
  e.subtype,
  e.hq_country,
  e.record_status,
  case
    when lower(coalesce(e.entity_type,'')) in ('company','business','corporation')
      and (
        upper(e.name) ~ '^(HMS|USS|USNS|HMCS|CCGS|INS|BRP)[[:space:]]'
        or lower(e.name) like '% ship'
      )
      then 'possible_mobile_asset_stored_as_entity'

    when lower(coalesce(e.entity_type,'')) in ('company','business','corporation')
      and (
        lower(e.name) like '% navy'
        or lower(e.name) like '% coast guard'
        or lower(e.name) like '% police'
        or lower(e.name) like '% civil defence'
        or lower(e.name) like '% civil defense'
        or lower(e.name) like '% ministry%'
        or lower(e.name) like '% department%'
      )
      then 'possible_public_body_misclassified_as_company'

    when lower(coalesce(e.entity_type,'')) in ('company','business','corporation')
      and (
        lower(e.name) like 'hmnb %'
        or lower(e.name) like '% naval base%'
        or lower(e.name) like '% air base%'
      )
      then 'possible_physical_asset_stored_as_entity'

    when lower(coalesce(e.entity_type,'')) in ('company','business','corporation')
      and (
        lower(e.name) like '% forces'
        or lower(e.name) like '% movement'
        or lower(e.name) like '% militia%'
      )
      then 'possible_security_actor_misclassified_as_company'

    else 'other_review'
  end as anomaly_type
from public.pc_entities e
where
  (
    lower(coalesce(e.entity_type,'')) in ('company','business','corporation')
    and (
      upper(e.name) ~ '^(HMS|USS|USNS|HMCS|CCGS|INS|BRP)[[:space:]]'
      or lower(e.name) like '% ship'
      or lower(e.name) like '% navy'
      or lower(e.name) like '% coast guard'
      or lower(e.name) like '% police'
      or lower(e.name) like '% civil defence'
      or lower(e.name) like '% civil defense'
      or lower(e.name) like '% ministry%'
      or lower(e.name) like '% department%'
      or lower(e.name) like 'hmnb %'
      or lower(e.name) like '% naval base%'
      or lower(e.name) like '% air base%'
      or lower(e.name) like '% forces'
      or lower(e.name) like '% movement'
      or lower(e.name) like '% militia%'
    )
  );


-- ---------------------------------------------------------------------------
-- 5. Compact integrity triage summary
-- ---------------------------------------------------------------------------
create or replace view public.pc_v_model_integrity_triage_summary as
select 'invalid_endpoints_total'::text check_name,count(*)::bigint issue_count
from public.pc_v_invalid_relationship_endpoint_triage
union all
select 'endpoint_type_mismatches',count(*)
from public.pc_v_invalid_relationship_endpoint_triage
where repair_class in ('source_type_mismatch','target_type_mismatch')
union all
select 'endpoint_missing_objects',count(*)
from public.pc_v_invalid_relationship_endpoint_triage
where repair_class in ('missing_source_object','missing_target_object')
union all
select 'endpoint_ambiguous_id_collisions',count(*)
from public.pc_v_invalid_relationship_endpoint_triage
where repair_class='ambiguous_id_collision'
union all
select 'exact_duplicate_entity_groups',count(*)
from public.pc_v_duplicate_entity_triage
union all
select 'exact_duplicate_asset_groups',count(*)
from public.pc_v_duplicate_asset_triage
union all
select 'entity_classification_anomalies',count(*)
from public.pc_v_entity_classification_anomalies;


grant select on public.pc_v_invalid_relationship_endpoint_triage to authenticated,service_role;
grant select on public.pc_v_duplicate_entity_triage to authenticated,service_role;
grant select on public.pc_v_duplicate_asset_triage to authenticated,service_role;
grant select on public.pc_v_entity_classification_anomalies to authenticated,service_role;
grant select on public.pc_v_model_integrity_triage_summary to authenticated,service_role;

commit;

-- Run these after installation:
--
-- select * from public.pc_v_model_integrity_triage_summary;
--
-- select *
-- from public.pc_v_invalid_relationship_endpoint_triage
-- order by repair_class,relationship_id;
--
-- select * from public.pc_v_duplicate_entity_triage;
-- select * from public.pc_v_duplicate_asset_triage;
--
-- select *
-- from public.pc_v_entity_classification_anomalies
-- order by anomaly_type,name;
