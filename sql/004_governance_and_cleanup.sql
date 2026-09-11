-- Governance / quality fixes that can be run after normalization.
-- IDs below reflect the current P&C source workbooks where known.

-- Preserve the existing governance relationships copied from workbook 11 first.
-- Then backfill Korean authorities that are canonical company/entity records but were not
-- mapped in Port Governance, which is why Busan currently renders "No dedicated governance".

insert into pc_governance_links(governed_type,governed_id,authority_entity_id,authority_name,governance_role,model_note,status)
select 'asset', a.asset_id, 'COMP_BUSAN_PA', 'Busan Port Authority', 'PORT AUTHORITY',
       'State-owned port authority responsible for port governance and operations.', 'current'
from pc_assets a
where a.asset_type ilike '%port%' and lower(a.name) in ('busan','port of busan')
  and exists(select 1 from pc_entities e where e.entity_id='COMP_BUSAN_PA')
on conflict do nothing;

insert into pc_governance_links(governed_type,governed_id,authority_entity_id,authority_name,governance_role,model_note,status)
select 'asset', a.asset_id, 'COMP_INCHEON_PA', 'Incheon Port Authority', 'PORT AUTHORITY',
       'State-owned port authority responsible for port governance and operations.', 'current'
from pc_assets a
where a.asset_type ilike '%port%' and lower(a.name) in ('incheon','port of incheon')
  and exists(select 1 from pc_entities e where e.entity_id='COMP_INCHEON_PA')
on conflict do nothing;

insert into pc_governance_links(governed_type,governed_id,authority_entity_id,authority_name,governance_role,model_note,status)
select 'asset', a.asset_id, 'COMP_ULSAN_PA', 'Ulsan Port Authority', 'PORT AUTHORITY',
       'State-owned port authority responsible for port governance and operations.', 'current'
from pc_assets a
where a.asset_type ilike '%port%' and lower(a.name) in ('ulsan','port of ulsan')
  and exists(select 1 from pc_entities e where e.entity_id='COMP_ULSAN_PA')
on conflict do nothing;

insert into pc_governance_links(governed_type,governed_id,authority_entity_id,authority_name,governance_role,model_note,status)
select 'asset', a.asset_id, 'COMP_YEOSU_GWANGYANG_PA', 'Yeosu Gwangyang Port Authority', 'PORT AUTHORITY',
       'State-owned port authority responsible for port governance and operations.', 'current'
from pc_assets a
where a.asset_type ilike '%port%' and (lower(a.name) like '%gwangyang%' or lower(a.name) like '%yeosu%')
  and exists(select 1 from pc_entities e where e.entity_id='COMP_YEOSU_GWANGYANG_PA')
on conflict do nothing;

-- Flag duplicate canonical port candidates instead of silently deleting them.
insert into pc_data_quality_issues(object_type,object_id,issue_type,severity,description,suggested_action,metadata)
select 'asset', min(asset_id), 'POSSIBLE_DUPLICATE_PORT','medium',
       'Multiple port records share the same normalized name and country.',
       'Review aliases/terminal parentage and select one canonical port ID.',
       jsonb_build_object('name',lower(regexp_replace(name,'^port of\\s+','','i')),'country',country,'asset_ids',jsonb_agg(asset_id))
from pc_assets
where asset_type ilike '%port%'
group by lower(regexp_replace(name,'^port of\\s+','','i')),country
having count(*) > 1;
