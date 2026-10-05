-- 2026-10-05 P&C Strategic Industry graph audit
-- READ ONLY: creates diagnostic views/functions; does not invent or repair links.

CREATE OR REPLACE VIEW public.pc_v_strategic_entity_audit AS
WITH x AS (
 SELECT e.entity_id,e.name,e.entity_type,e.subtype,e.hq_country
 FROM public.pc_entities e
 WHERE EXISTS (SELECT 1 FROM public.pc_company_asset_roles r WHERE r.entity_id=e.entity_id)
    OR EXISTS (SELECT 1 FROM public.pc_shipyard_details s WHERE s.owner_entity_id=e.entity_id OR s.operator_entity_id=e.entity_id)
    OR EXISTS (SELECT 1 FROM public.pc_defence_programmes p WHERE p.customer_entity_id=e.entity_id OR p.lead_contractor_entity_id=e.entity_id)
    OR EXISTS (SELECT 1 FROM public.pc_defence_programme_participants p WHERE p.entity_id=e.entity_id)
    OR EXISTS (SELECT 1 FROM public.pc_contract_participants p WHERE p.entity_id=e.entity_id)
    OR EXISTS (SELECT 1 FROM public.pc_shipbuilding_orders o WHERE o.buyer_entity_id=e.entity_id OR o.builder_entity_id=e.entity_id)
)
SELECT x.*,
 (SELECT count(*) FROM public.pc_company_asset_roles r WHERE r.entity_id=x.entity_id AND r.valid_to IS NULL) asset_roles,
 (SELECT count(*) FROM public.pc_shipyard_details s WHERE s.owner_entity_id=x.entity_id OR s.operator_entity_id=x.entity_id) shipyards,
 (SELECT count(DISTINCT p.defence_programme_id) FROM public.pc_defence_programmes p LEFT JOIN public.pc_defence_programme_participants q ON q.defence_programme_id=p.defence_programme_id WHERE p.customer_entity_id=x.entity_id OR p.lead_contractor_entity_id=x.entity_id OR q.entity_id=x.entity_id) programmes,
 (SELECT count(*) FROM public.pc_contract_participants p WHERE p.entity_id=x.entity_id) contract_participations,
 (SELECT count(*) FROM public.pc_shipbuilding_orders o WHERE o.buyer_entity_id=x.entity_id OR o.builder_entity_id=x.entity_id) shipbuilding_orders,
 CASE
  WHEN EXISTS (SELECT 1 FROM public.pc_shipyard_details s WHERE (s.owner_entity_id=x.entity_id OR s.operator_entity_id=x.entity_id))
   AND NOT EXISTS (SELECT 1 FROM public.pc_company_asset_roles r WHERE r.entity_id=x.entity_id AND r.valid_to IS NULL)
   THEN 'SHIPYARD_ENTITY_WITHOUT_ASSET_ROLE'
  WHEN EXISTS (SELECT 1 FROM public.pc_defence_programme_participants p WHERE p.entity_id=x.entity_id)
   AND NOT EXISTS (SELECT 1 FROM public.pc_company_asset_roles r WHERE r.entity_id=x.entity_id AND r.valid_to IS NULL)
   AND NOT EXISTS (SELECT 1 FROM public.pc_shipyard_details s WHERE s.owner_entity_id=x.entity_id OR s.operator_entity_id=x.entity_id)
   THEN 'PROGRAMME_ENTITY_WITHOUT_FACILITY_PATH'
  ELSE 'CONNECTED_OR_CONTEXTUAL'
 END graph_status
FROM x;

CREATE OR REPLACE VIEW public.pc_v_strategic_facility_audit AS
SELECT a.asset_id,a.name,a.asset_type,a.subtype,a.country,a.region_city,
 s.owner_entity_id,oe.name owner_name,s.operator_entity_id,op.name operator_name,
 (SELECT count(*) FROM public.pc_company_asset_roles r WHERE r.asset_id=a.asset_id AND r.valid_to IS NULL) company_roles,
 (SELECT count(*) FROM public.pc_defence_programme_participants p WHERE p.shipyard_asset_id=a.asset_id) programme_participations,
 (SELECT count(*) FROM public.pc_shipbuilding_orders o WHERE o.shipyard_asset_id=a.asset_id) shipbuilding_orders,
 (SELECT count(*) FROM public.pc_relationships r WHERE r.valid_to IS NULL AND
   ((r.source_type='asset' AND r.source_id=a.asset_id) OR (r.target_type='asset' AND r.target_id=a.asset_id))) graph_edges,
 CASE
  WHEN NOT EXISTS (SELECT 1 FROM public.pc_relationships r WHERE r.valid_to IS NULL AND
   ((r.source_type='asset' AND r.source_id=a.asset_id) OR (r.target_type='asset' AND r.target_id=a.asset_id)))
   THEN 'FACILITY_WITHOUT_GRAPH_EDGE'
  WHEN (s.owner_entity_id IS NOT NULL OR s.operator_entity_id IS NOT NULL)
   AND NOT EXISTS (SELECT 1 FROM public.pc_company_asset_roles r WHERE r.asset_id=a.asset_id AND r.valid_to IS NULL)
   THEN 'OWNER_OPERATOR_NOT_MIRRORED_TO_ASSET_ROLE'
  ELSE 'CONNECTED_OR_CONTEXTUAL'
 END graph_status
FROM public.pc_shipyard_details s
JOIN public.pc_assets a ON a.asset_id=s.asset_id
LEFT JOIN public.pc_entities oe ON oe.entity_id=s.owner_entity_id
LEFT JOIN public.pc_entities op ON op.entity_id=s.operator_entity_id;

CREATE OR REPLACE VIEW public.pc_v_strategic_programme_audit AS
SELECT p.defence_programme_id,p.programme_name,p.programme_type,p.programme_status,
 p.customer_entity_id,c.name customer_name,p.lead_contractor_entity_id,l.name lead_contractor_name,
 p.contract_id,p.shipbuilding_order_id,
 (SELECT count(*) FROM public.pc_defence_programme_participants x WHERE x.defence_programme_id=p.defence_programme_id) participants,
 (SELECT count(*) FROM public.pc_defence_programme_participants x WHERE x.defence_programme_id=p.defence_programme_id AND x.shipyard_asset_id IS NOT NULL) linked_shipyards,
 (SELECT count(*) FROM public.pc_defence_programme_milestones m WHERE m.defence_programme_id=p.defence_programme_id) milestones,
 CASE
  WHEN NOT EXISTS (SELECT 1 FROM public.pc_defence_programme_participants x WHERE x.defence_programme_id=p.defence_programme_id) THEN 'PROGRAMME_WITHOUT_PARTICIPANTS'
  WHEN p.contract_id IS NULL AND p.shipbuilding_order_id IS NULL THEN 'PROGRAMME_WITHOUT_CONTRACT_OR_ORDER'
  WHEN NOT EXISTS (SELECT 1 FROM public.pc_defence_programme_participants x WHERE x.defence_programme_id=p.defence_programme_id AND x.shipyard_asset_id IS NOT NULL) THEN 'PROGRAMME_WITHOUT_FACILITY_PATH'
  ELSE 'CONNECTED_OR_CONTEXTUAL'
 END graph_status
FROM public.pc_defence_programmes p
LEFT JOIN public.pc_entities c ON c.entity_id=p.customer_entity_id
LEFT JOIN public.pc_entities l ON l.entity_id=p.lead_contractor_entity_id;

CREATE OR REPLACE VIEW public.pc_v_strategic_contract_audit AS
SELECT c.contract_id,c.contract_name,c.contract_type,c.status,
 (SELECT count(*) FROM public.pc_contract_participants p WHERE p.contract_id=c.contract_id) participants,
 (SELECT count(*) FROM public.pc_contract_links l WHERE l.contract_id=c.contract_id) links,
 (SELECT count(*) FROM public.pc_defence_programmes p WHERE p.contract_id=c.contract_id) programmes,
 (SELECT count(*) FROM public.pc_shipbuilding_orders o WHERE o.contract_id=c.contract_id) shipbuilding_orders,
 CASE WHEN
  NOT EXISTS (SELECT 1 FROM public.pc_contract_participants p WHERE p.contract_id=c.contract_id)
  AND NOT EXISTS (SELECT 1 FROM public.pc_contract_links l WHERE l.contract_id=c.contract_id)
  AND NOT EXISTS (SELECT 1 FROM public.pc_defence_programmes p WHERE p.contract_id=c.contract_id)
  AND NOT EXISTS (SELECT 1 FROM public.pc_shipbuilding_orders o WHERE o.contract_id=c.contract_id)
 THEN 'ORPHAN_CONTRACT' ELSE 'CONNECTED_OR_CONTEXTUAL' END graph_status
FROM public.pc_contracts c;

CREATE OR REPLACE FUNCTION public.pc_strategic_entity_dossier(p_entity_id text)
RETURNS jsonb LANGUAGE sql STABLE AS $$
WITH facilities AS (
 SELECT DISTINCT a.* FROM public.pc_assets a
 LEFT JOIN public.pc_company_asset_roles r ON r.asset_id=a.asset_id AND r.valid_to IS NULL
 LEFT JOIN public.pc_shipyard_details s ON s.asset_id=a.asset_id
 WHERE r.entity_id=p_entity_id OR s.owner_entity_id=p_entity_id OR s.operator_entity_id=p_entity_id
), programmes AS (
 SELECT DISTINCT p.* FROM public.pc_defence_programmes p
 LEFT JOIN public.pc_defence_programme_participants x ON x.defence_programme_id=p.defence_programme_id
 WHERE p.customer_entity_id=p_entity_id OR p.lead_contractor_entity_id=p_entity_id OR x.entity_id=p_entity_id
), contracts AS (
 SELECT DISTINCT c.* FROM public.pc_contracts c
 LEFT JOIN public.pc_contract_participants cp ON cp.contract_id=c.contract_id
 LEFT JOIN public.pc_defence_programmes p ON p.contract_id=c.contract_id
 LEFT JOIN public.pc_shipbuilding_orders o ON o.contract_id=c.contract_id
 WHERE cp.entity_id=p_entity_id OR p.customer_entity_id=p_entity_id OR p.lead_contractor_entity_id=p_entity_id OR o.buyer_entity_id=p_entity_id OR o.builder_entity_id=p_entity_id
), orders AS (
 SELECT DISTINCT o.* FROM public.pc_shipbuilding_orders o
 LEFT JOIN programmes p ON p.shipbuilding_order_id=o.shipbuilding_order_id
 WHERE o.buyer_entity_id=p_entity_id OR o.builder_entity_id=p_entity_id OR p.defence_programme_id IS NOT NULL
), platforms AS (
 SELECT DISTINCT m.* FROM public.pc_mobile_assets m
 JOIN public.pc_shipbuilding_order_units u ON u.mobile_asset_id=m.mobile_asset_id
 JOIN orders o ON o.shipbuilding_order_id=u.shipbuilding_order_id
)
SELECT jsonb_build_object(
 'entity',(SELECT to_jsonb(e) FROM public.pc_entities e WHERE e.entity_id=p_entity_id LIMIT 1),
 'facilities',COALESCE((SELECT jsonb_agg(to_jsonb(f)) FROM facilities f),'[]'::jsonb),
 'programmes',COALESCE((SELECT jsonb_agg(to_jsonb(p)) FROM programmes p),'[]'::jsonb),
 'contracts',COALESCE((SELECT jsonb_agg(to_jsonb(c)) FROM contracts c),'[]'::jsonb),
 'orders',COALESCE((SELECT jsonb_agg(to_jsonb(o)) FROM orders o),'[]'::jsonb),
 'platforms',COALESCE((SELECT jsonb_agg(to_jsonb(m)) FROM platforms m),'[]'::jsonb),
 'counts',jsonb_build_object('facilities',(SELECT count(*) FROM facilities),'programmes',(SELECT count(*) FROM programmes),'contracts',(SELECT count(*) FROM contracts),'orders',(SELECT count(*) FROM orders),'platforms',(SELECT count(*) FROM platforms))
);
$$;

GRANT SELECT ON public.pc_v_strategic_entity_audit,public.pc_v_strategic_facility_audit,public.pc_v_strategic_programme_audit,public.pc_v_strategic_contract_audit TO authenticated,anon;
GRANT EXECUTE ON FUNCTION public.pc_strategic_entity_dossier(text) TO authenticated,anon;

-- Diagnostics: run after install.
SELECT * FROM public.pc_v_strategic_entity_audit
ORDER BY (graph_status='CONNECTED_OR_CONTEXTUAL'),name;
SELECT * FROM public.pc_v_strategic_facility_audit
ORDER BY (graph_status='CONNECTED_OR_CONTEXTUAL'),country,name;
SELECT * FROM public.pc_v_strategic_programme_audit
ORDER BY (graph_status='CONNECTED_OR_CONTEXTUAL'),programme_name;
SELECT * FROM public.pc_v_strategic_contract_audit
WHERE graph_status<>'CONNECTED_OR_CONTEXTUAL' ORDER BY contract_name;
SELECT * FROM public.pc_v_strategic_entity_audit
WHERE lower(name) LIKE ANY(ARRAY['%edge%','%irving%','%seaspan%','%fincantieri%','%damen%','%inocea%','%helsinki%','%rotterdam%','%antwerp%','%zeebrugge%'])
ORDER BY name;
