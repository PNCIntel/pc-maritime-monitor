-- 2026-10-05 P&C Strategic Industry discovery/audit v2
-- Broadens discovery across all generations of the canonical graph.
-- READ ONLY with respect to business data: creates/replaces views/functions only.

CREATE OR REPLACE VIEW public.pc_v_strategic_entity_audit AS
WITH strategic_assets AS (
  SELECT a.asset_id,a.owner_entity_id,a.operator_entity_id
  FROM public.pc_assets a
  WHERE lower(coalesce(a.asset_type,'')) LIKE ANY(ARRAY['%shipyard%','%naval%','%defence%','%defense%','%coast guard%'])
     OR lower(coalesce(a.subtype,'')) LIKE ANY(ARRAY['%shipyard%','%naval%','%defence%','%defense%','%coast guard%'])
     OR EXISTS (SELECT 1 FROM public.pc_shipyard_details sd WHERE sd.asset_id=a.asset_id)
), seeds AS (
  SELECT e.entity_id FROM public.pc_entities e WHERE
       EXISTS (SELECT 1 FROM public.pc_company_asset_roles r WHERE r.entity_id=e.entity_id)
    OR EXISTS (SELECT 1 FROM strategic_assets a WHERE a.owner_entity_id=e.entity_id OR a.operator_entity_id=e.entity_id)
    OR EXISTS (SELECT 1 FROM public.pc_shipyard_details s WHERE s.owner_entity_id=e.entity_id OR s.operator_entity_id=e.entity_id)
    OR EXISTS (SELECT 1 FROM public.pc_defence_programmes p WHERE p.customer_entity_id=e.entity_id OR p.lead_contractor_entity_id=e.entity_id)
    OR EXISTS (SELECT 1 FROM public.pc_defence_programme_participants p WHERE p.entity_id=e.entity_id)
    OR EXISTS (SELECT 1 FROM public.pc_contract_participants p WHERE p.entity_id=e.entity_id)
    OR EXISTS (SELECT 1 FROM public.pc_shipbuilding_orders o WHERE o.buyer_entity_id=e.entity_id OR o.builder_entity_id=e.entity_id)
    OR EXISTS (SELECT 1 FROM public.pc_relationships r WHERE
         (r.source_type='entity' AND r.source_id=e.entity_id AND r.target_type IN ('asset','mobile_asset'))
      OR (r.target_type='entity' AND r.target_id=e.entity_id AND r.source_type IN ('asset','mobile_asset')))
), family AS (
  SELECT entity_id FROM seeds
  UNION
  SELECT DISTINCT r.source_id FROM public.pc_relationships r JOIN seeds s ON r.target_type='entity' AND r.target_id=s.entity_id
   WHERE r.source_type='entity' AND lower(replace(r.relationship_type,'_',' ')) IN
    ('owns','controls','parent of','part of','owns / controls','subsidiary of')
  UNION
  SELECT DISTINCT r.target_id FROM public.pc_relationships r JOIN seeds s ON r.source_type='entity' AND r.source_id=s.entity_id
   WHERE r.target_type='entity' AND lower(replace(r.relationship_type,'_',' ')) IN
    ('owns','controls','parent of','part of','owns / controls','subsidiary of','owns 51 percent','owns 49 percent')
), x AS (
 SELECT e.entity_id,e.name,e.entity_type,e.subtype,e.hq_country
 FROM public.pc_entities e JOIN family f ON f.entity_id=e.entity_id
)
SELECT x.*,
 (SELECT count(*) FROM public.pc_company_asset_roles r WHERE r.entity_id=x.entity_id AND r.valid_to IS NULL) asset_roles,
 (SELECT count(*) FROM public.pc_shipyard_details s WHERE s.owner_entity_id=x.entity_id OR s.operator_entity_id=x.entity_id) shipyards,
 (SELECT count(DISTINCT p.defence_programme_id) FROM public.pc_defence_programmes p LEFT JOIN public.pc_defence_programme_participants q ON q.defence_programme_id=p.defence_programme_id WHERE p.customer_entity_id=x.entity_id OR p.lead_contractor_entity_id=x.entity_id OR q.entity_id=x.entity_id) programmes,
 (SELECT count(*) FROM public.pc_contract_participants p WHERE p.entity_id=x.entity_id) contract_participations,
 (SELECT count(*) FROM public.pc_shipbuilding_orders o WHERE o.buyer_entity_id=x.entity_id OR o.builder_entity_id=x.entity_id) shipbuilding_orders,
 (SELECT count(*) FROM public.pc_relationships r WHERE
    (r.source_type='entity' AND r.source_id=x.entity_id) OR (r.target_type='entity' AND r.target_id=x.entity_id)) generic_relationships,
 (SELECT count(*) FROM public.pc_relationships r WHERE
    ((r.source_type='entity' AND r.source_id=x.entity_id AND r.target_type IN ('asset','mobile_asset'))
     OR (r.target_type='entity' AND r.target_id=x.entity_id AND r.source_type IN ('asset','mobile_asset')))) direct_graph_assets,
 CASE
  WHEN EXISTS (SELECT 1 FROM public.pc_shipyard_details s WHERE s.owner_entity_id=x.entity_id OR s.operator_entity_id=x.entity_id)
   AND NOT EXISTS (SELECT 1 FROM public.pc_company_asset_roles r WHERE r.entity_id=x.entity_id AND r.valid_to IS NULL)
   THEN 'SHIPYARD_ENTITY_WITHOUT_ASSET_ROLE'
  WHEN EXISTS (SELECT 1 FROM public.pc_defence_programme_participants p WHERE p.entity_id=x.entity_id)
   AND NOT EXISTS (SELECT 1 FROM public.pc_company_asset_roles r WHERE r.entity_id=x.entity_id AND r.valid_to IS NULL)
   AND NOT EXISTS (SELECT 1 FROM public.pc_shipyard_details s WHERE s.owner_entity_id=x.entity_id OR s.operator_entity_id=x.entity_id)
   AND NOT EXISTS (SELECT 1 FROM public.pc_relationships r WHERE r.source_type='entity' AND r.source_id=x.entity_id AND r.target_type IN ('asset','mobile_asset'))
   THEN 'PROGRAMME_ENTITY_WITHOUT_FACILITY_PATH'
  WHEN EXISTS (SELECT 1 FROM public.pc_relationships r WHERE
      (r.source_type='entity' AND r.source_id=x.entity_id) OR (r.target_type='entity' AND r.target_id=x.entity_id))
   AND NOT EXISTS (SELECT 1 FROM public.pc_company_asset_roles r WHERE r.entity_id=x.entity_id AND r.valid_to IS NULL)
   AND NOT EXISTS (SELECT 1 FROM public.pc_defence_programmes p WHERE p.customer_entity_id=x.entity_id OR p.lead_contractor_entity_id=x.entity_id)
   AND NOT EXISTS (SELECT 1 FROM public.pc_defence_programme_participants p WHERE p.entity_id=x.entity_id)
   THEN 'LEGACY_GRAPH_ONLY'
  ELSE 'CONNECTED_OR_CONTEXTUAL'
 END graph_status
FROM x;

CREATE OR REPLACE FUNCTION public.pc_strategic_entity_dossier(p_entity_id text)
RETURNS jsonb LANGUAGE sql STABLE AS $$
WITH RECURSIVE entity_graph(entity_id,depth) AS (
 SELECT p_entity_id,0
 UNION
 SELECT CASE WHEN r.source_id=g.entity_id THEN r.target_id ELSE r.source_id END,g.depth+1
 FROM entity_graph g JOIN public.pc_relationships r
   ON (r.source_type='entity' AND r.target_type='entity')
  AND (r.source_id=g.entity_id OR r.target_id=g.entity_id)
 WHERE g.depth<3
   AND lower(replace(r.relationship_type,'_',' ')) IN
    ('owns','controls','parent of','part of','owns / controls','subsidiary of','owns 51 percent','owns 49 percent')
), entities AS (SELECT DISTINCT entity_id FROM entity_graph),
facilities AS (
 SELECT DISTINCT a.* FROM public.pc_assets a
 LEFT JOIN public.pc_company_asset_roles car ON car.asset_id=a.asset_id AND car.valid_to IS NULL
 LEFT JOIN public.pc_shipyard_details sd ON sd.asset_id=a.asset_id
 LEFT JOIN public.pc_relationships r ON r.target_type='asset' AND r.target_id=a.asset_id AND r.source_type='entity'
 WHERE car.entity_id IN (SELECT entity_id FROM entities)
    OR a.owner_entity_id IN (SELECT entity_id FROM entities)
    OR a.operator_entity_id IN (SELECT entity_id FROM entities)
    OR sd.owner_entity_id IN (SELECT entity_id FROM entities)
    OR sd.operator_entity_id IN (SELECT entity_id FROM entities)
    OR r.source_id IN (SELECT entity_id FROM entities)
), programmes AS (
 SELECT DISTINCT p.* FROM public.pc_defence_programmes p
 LEFT JOIN public.pc_defence_programme_participants x ON x.defence_programme_id=p.defence_programme_id
 WHERE p.customer_entity_id IN (SELECT entity_id FROM entities)
    OR p.lead_contractor_entity_id IN (SELECT entity_id FROM entities)
    OR x.entity_id IN (SELECT entity_id FROM entities)
), contracts AS (
 SELECT DISTINCT c.* FROM public.pc_contracts c
 LEFT JOIN public.pc_contract_participants cp ON cp.contract_id=c.contract_id
 LEFT JOIN programmes p ON p.contract_id=c.contract_id
 LEFT JOIN public.pc_shipbuilding_orders o ON o.contract_id=c.contract_id
 WHERE cp.entity_id IN (SELECT entity_id FROM entities)
    OR p.defence_programme_id IS NOT NULL
    OR o.buyer_entity_id IN (SELECT entity_id FROM entities)
    OR o.builder_entity_id IN (SELECT entity_id FROM entities)
), orders AS (
 SELECT DISTINCT o.* FROM public.pc_shipbuilding_orders o
 LEFT JOIN programmes p ON p.shipbuilding_order_id=o.shipbuilding_order_id
 WHERE o.buyer_entity_id IN (SELECT entity_id FROM entities)
    OR o.builder_entity_id IN (SELECT entity_id FROM entities)
    OR p.defence_programme_id IS NOT NULL
), platforms AS (
 SELECT DISTINCT m.* FROM public.pc_mobile_assets m
 LEFT JOIN public.pc_shipbuilding_order_units u ON u.mobile_asset_id=m.mobile_asset_id
 LEFT JOIN orders o ON o.shipbuilding_order_id=u.shipbuilding_order_id
 LEFT JOIN public.pc_relationships r ON r.target_type='mobile_asset' AND r.target_id=m.mobile_asset_id AND r.source_type='entity'
 WHERE o.shipbuilding_order_id IS NOT NULL OR r.source_id IN (SELECT entity_id FROM entities)
)
SELECT jsonb_build_object(
 'entity',(SELECT to_jsonb(e) FROM public.pc_entities e WHERE e.entity_id=p_entity_id LIMIT 1),
 'entity_graph',COALESCE((SELECT jsonb_agg(to_jsonb(e)) FROM public.pc_entities e WHERE e.entity_id IN (SELECT entity_id FROM entities)),'[]'::jsonb),
 'facilities',COALESCE((SELECT jsonb_agg(to_jsonb(f)) FROM facilities f),'[]'::jsonb),
 'programmes',COALESCE((SELECT jsonb_agg(to_jsonb(p)) FROM programmes p),'[]'::jsonb),
 'contracts',COALESCE((SELECT jsonb_agg(to_jsonb(c)) FROM contracts c),'[]'::jsonb),
 'orders',COALESCE((SELECT jsonb_agg(to_jsonb(o)) FROM orders o),'[]'::jsonb),
 'platforms',COALESCE((SELECT jsonb_agg(to_jsonb(m)) FROM platforms m),'[]'::jsonb),
 'counts',jsonb_build_object(
   'entities',(SELECT count(*) FROM entities),
   'facilities',(SELECT count(*) FROM facilities),
   'programmes',(SELECT count(*) FROM programmes),
   'contracts',(SELECT count(*) FROM contracts),
   'orders',(SELECT count(*) FROM orders),
   'platforms',(SELECT count(*) FROM platforms))
);
$$;

GRANT SELECT ON public.pc_v_strategic_entity_audit TO authenticated,anon;
GRANT EXECUTE ON FUNCTION public.pc_strategic_entity_dossier(text) TO authenticated,anon;

-- Regression set: these must be discoverable without fuzzy identity merging.
SELECT * FROM public.pc_v_strategic_entity_audit
WHERE entity_id IN (
 'COMP_EDGE','COMP_FINCANTIERI','COMP_FINCANTIERI_INFRA','COMP_HELSINKI_SHIPYARD',
 'COMP_INOCEA','COMP_IRVING','COMP_SEASPAN_CORP','COMP_SEASPAN_ULC',
 'ENTITY_AI_18F679A25BB2795587E4','ENTITY_69A9164ED4B9229E',
 'COMP_DAMEN','ENT_SI_DAMEN_NAVAL','ENTITY_RT_021EB1191FB292FC788DAE94',
 'ENTITY_RT_293730AF74185BC2BB0C0D77'
)
ORDER BY name;

-- Dossier regression examples.
SELECT 'EDGE' test, (public.pc_strategic_entity_dossier('COMP_EDGE')->'counts') counts
UNION ALL SELECT 'Inocea', public.pc_strategic_entity_dossier('COMP_INOCEA')->'counts'
UNION ALL SELECT 'Irving', public.pc_strategic_entity_dossier('COMP_IRVING')->'counts'
UNION ALL SELECT 'Seaspan ULC', public.pc_strategic_entity_dossier('COMP_SEASPAN_ULC')->'counts'
UNION ALL SELECT 'Fincantieri', public.pc_strategic_entity_dossier('COMP_FINCANTIERI')->'counts'
UNION ALL SELECT 'Helsinki', public.pc_strategic_entity_dossier('COMP_HELSINKI_SHIPYARD')->'counts'
UNION ALL SELECT 'Damen Naval', public.pc_strategic_entity_dossier('ENT_SI_DAMEN_NAVAL')->'counts';
