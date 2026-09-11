-- Post-migration checks
select 'entities' as object,count(*) from pc_entities
union all select 'assets',count(*) from pc_assets
union all select 'mobile_assets',count(*) from pc_mobile_assets
union all select 'relationships',count(*) from pc_relationships
union all select 'events',count(*) from pc_events
union all select 'event_locations',count(*) from pc_event_locations
union all select 'event_links',count(*) from pc_event_links
union all select 'legacy_rows',count(*) from pc_legacy_sheet_rows;

select event_nature,count(*) from pc_events group by 1 order by 2 desc;
select count(*) as intelligence_corporate_leakage
from pc_events where intelligence_visible and event_nature='CORPORATE';

select a.asset_id,a.name,g.authority_name,g.governance_role
from pc_assets a left join pc_governance_links g on g.governed_type='asset' and g.governed_id=a.asset_id
where lower(a.name) like '%busan%';

select object_type,issue_type,severity,count(*)
from pc_data_quality_issues where status='open'
group by 1,2,3 order by 4 desc;
