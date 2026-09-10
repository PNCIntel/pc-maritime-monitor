-- P&C Core Intelligence Model v3.0 validation queries

-- 1. PGSA-listed canonical vessels and their known operators/owners.
select sc.target_name, sc.identifier, sc.status, ma.owner_entity_id, ma.operator_entity_id
from security_compliance sc
left join mobile_assets ma on ma.mobile_asset_id = sc.target_id
where sc.record_type = 'Compliance designation'
  and sc.regime = 'PGSA Maritime Compliance Regime'
order by sc.target_name;

-- 2. Potential PGSA secondary exposure through STS relationships.
select target_name as listed_vessel, identifier, related_target as counterparty,
       relationship, status, confidence
from security_compliance
where record_type = 'Secondary exposure'
order by target_name;

-- 3. Official MARSEC incidents in Japan, South Korea and India.
select start_date, countries, event_type, severity, title, operational_impact
from events
where source_id in ('SRC_JCG','SRC_KCG','SRC_ICG','SRC_DGS_INDIA')
order by start_date desc;

-- 4. Events connected to a specific tracked asset.
select ev.start_date, ev.title, ev.event_type, ev.severity, el.relationship
from events ev
join event_links el on el.event_id = ev.event_id
where el.linked_id = 'PORT_ROTTERDAM'
order by ev.start_date desc;

-- 5. AD Ports financial metrics and investments.
select period_or_date, record_type, metric_or_project, value, unit, currency, spend_type, status
from financial_investment
where entity_id = 'COMP_ADPORTS'
order by period_or_date desc, record_type;

-- 6. AD Ports historical share-price sample.
select trade_date, high, low, close, currency
from market_data
where entity_id = 'COMP_ADPORTS' and record_type = 'Monthly price'
order by trade_date;

-- 7. All assets owned or operated by AD Ports in the seed.
select a.asset_id, a.name, a.asset_type, a.country, a.status
from assets a
where a.owner_entity_id = 'COMP_ADPORTS'
   or a.operator_entity_id = 'COMP_ADPORTS'
order by a.country, a.name;

-- 8. Active intelligence monitoring / PIRs.
select * from vw_intel_active_security order by geography, analysis_type, title;

-- 9. Security events that can also create trade/commercial consequences.
select start_date, event_family, event_type, title, operational_impact, commercial_impact
from events
where commercial_impact is not null
order by start_date desc;

-- 10. Data-quality audit: provisional canonical entities/mobile assets.
select 'entity' as object_type, entity_id as object_id, name, record_status, data_quality
from entities where record_status <> 'verified'
union all
select 'mobile_asset', mobile_asset_id, name, record_status, data_quality
from mobile_assets where record_status <> 'verified'
order by object_type, name;

-- 11. Orphan check for event links. Should return zero rows.
select el.*
from event_links el
left join events e on e.event_id = el.event_id
where e.event_id is null;

-- 12. Duplicate IMO/identifier check. Should return zero rows.
select imo_or_identifier, count(*)
from mobile_assets
where imo_or_identifier is not null and imo_or_identifier <> ''
group by imo_or_identifier
having count(*) > 1;

-- 13. Source coverage by type.
select source_type, count(*) as source_count
from sources
group by source_type
order by source_count desc;

-- 14. Cross-product example: same canonical vessel exposed in both trade and intelligence lenses.
select ma.name, ma.subtype, ma.owner_entity_id, ma.operator_entity_id,
       sc.status as compliance_status, sc.regime, sc.exposure_type
from mobile_assets ma
left join security_compliance sc on sc.target_id = ma.mobile_asset_id
where ma.mobile_asset_id in ('VESSEL_MRAWEH','VESSEL_TARIF','VESSEL_GASLOG_SHANGHAI','VESSEL_AL_REKAYYAT')
order by ma.name, sc.record_type;

-- 15. Assets/infrastructure with event exposure.
select a.name as asset, a.asset_type, a.country, ev.start_date, ev.title, ev.severity
from assets a
join event_links el on el.linked_type = 'Asset' and el.linked_id = a.asset_id
join events ev on ev.event_id = el.event_id
order by ev.start_date desc;
