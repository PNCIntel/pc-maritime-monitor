-- P&C v5: additive LIVE relational delivery; no canonical data writes.
-- Requires pc_delivery_resolve_object_id and pc_delivery_identity_aliases (installed).
BEGIN;
CREATE OR REPLACE VIEW public.pc_v5_infrastructure_connections AS
WITH explicit_edges AS (
 SELECT public.pc_delivery_resolve_object_id('asset',t.parent_port_asset_id) AS parent_asset_id,
        public.pc_delivery_resolve_object_id('asset',t.asset_id) AS child_asset_id,
        'Terminal / port facility'::text AS business_role,
        'pc_terminal_details'::text AS evidence_table
 FROM public.pc_terminal_details t
 UNION ALL
 SELECT public.pc_delivery_resolve_object_id('asset',r.source_id),
        public.pc_delivery_resolve_object_id('asset',r.target_id),
        r.relationship_type::text,'pc_relationships'::text
 FROM public.pc_relationships r
 WHERE r.source_type='asset' AND r.target_type='asset'
 UNION ALL
 SELECT public.pc_delivery_resolve_object_id('asset',r.target_id),
        public.pc_delivery_resolve_object_id('asset',r.source_id),
        r.relationship_type::text,'pc_relationships'::text
 FROM public.pc_relationships r
 WHERE r.source_type='asset' AND r.target_type='asset'
), dedup AS (
 SELECT parent_asset_id,child_asset_id,
        array_agg(DISTINCT business_role ORDER BY business_role) AS relationship_labels,
        array_agg(DISTINCT evidence_table ORDER BY evidence_table) AS relationship_sources
 FROM explicit_edges WHERE parent_asset_id<>child_asset_id
 GROUP BY parent_asset_id,child_asset_id
)
SELECT d.parent_asset_id,d.child_asset_id,a.name AS connected_name,
       a.asset_type,a.subtype,a.country,a.latitude,a.longitude,
       a.operator_entity_id,e.name AS operator_name,
       d.relationship_labels,d.relationship_sources
FROM dedup d
JOIN public.pc_assets a ON a.asset_id=d.child_asset_id
LEFT JOIN public.pc_entities e ON e.entity_id=a.operator_entity_id;

CREATE OR REPLACE VIEW public.pc_v5_infrastructure_companies AS
WITH roles AS (
 SELECT public.pc_delivery_resolve_object_id('asset',r.target_id) AS asset_id,
        r.source_id AS entity_id,r.relationship_type::text AS role
 FROM public.pc_relationships r WHERE r.source_type='entity' AND r.target_type='asset'
 UNION ALL
 SELECT public.pc_delivery_resolve_object_id('asset',r.source_id),
        r.target_id,r.relationship_type::text
 FROM public.pc_relationships r WHERE r.source_type='asset' AND r.target_type='entity'
 UNION ALL
 SELECT public.pc_delivery_resolve_object_id('asset',a.asset_id),a.operator_entity_id,'Operator'::text
 FROM public.pc_assets a WHERE a.operator_entity_id IS NOT NULL
)
SELECT DISTINCT r.asset_id,r.entity_id,e.name AS company_name,r.role
FROM roles r JOIN public.pc_entities e ON e.entity_id=r.entity_id;
COMMIT;
-- Validation: SELECT count(*) FROM public.pc_v5_infrastructure_connections WHERE parent_asset_id='PORT_UAE_PORT_OF_FUJAIRAH';
