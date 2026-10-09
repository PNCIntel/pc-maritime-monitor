-- P&C Intelligence Delivery v1. Additive to pc_delivery_v1 migration.
-- Run after 20261009_delivery_views.sql. No source-table updates.
-- The views intentionally remain LIVE during rapid SQL ingestion.
BEGIN;

-- Complete event records: narrative and source metadata stay available.
-- jsonb accessor avoids depending on optional source-table columns.
CREATE OR REPLACE VIEW public.pc_intel_event_details AS
SELECT e.event_id::text AS event_id,
       e.title::text AS title,
       e.event_type::text AS event_type,
       e.start_date AS occurred_at,
       e.record_status::text AS record_status,
       COALESCE(NULLIF(to_jsonb(e)->>'description',''), NULLIF(to_jsonb(e)->>'summary',''), NULLIF(to_jsonb(e)->>'narrative','')) AS narrative,
       COALESCE(NULLIF(to_jsonb(e)->>'event_family',''),NULLIF(to_jsonb(e)->>'event_domain',''),'Other') AS event_family,
       COALESCE(NULLIF(to_jsonb(e)->>'severity',''),'not assessed') AS recorded_severity,
       COALESCE(NULLIF(to_jsonb(e)->>'country',''),NULLIF(to_jsonb(e)->>'countries','')) AS location_label,
       COALESCE(NULLIF(to_jsonb(e)->>'latitude',''),NULLIF(to_jsonb(e)->'metadata'->>'latitude','')) AS latitude_text,
       COALESCE(NULLIF(to_jsonb(e)->>'longitude',''),NULLIF(to_jsonb(e)->'metadata'->>'longitude','')) AS longitude_text,
       COALESCE(NULLIF(to_jsonb(e)->>'risk_level',''),NULLIF(to_jsonb(e)->'metadata'->>'risk_level','')) AS source_risk_level,
       COALESCE(NULLIF(to_jsonb(e)->>'risk_trend',''),NULLIF(to_jsonb(e)->'metadata'->>'risk_trend','')) AS source_risk_trend,
       to_jsonb(e)->'metadata' AS metadata,
       (SELECT count(*) FROM public.pc_event_evidence ev WHERE ev.event_id=e.event_id)::integer AS evidence_count,
       (SELECT jsonb_agg(jsonb_build_object('claim',ev.claim,'verification',ev.verification_status,
             'url',ev.original_url,'published_at',ev.published_at) ORDER BY ev.evidence_id)
          FROM public.pc_event_evidence ev WHERE ev.event_id=e.event_id) AS evidence
FROM public.pc_events e;

-- Reconcile multiple link surfaces to unique (object,event) pairs.
CREATE OR REPLACE VIEW public.pc_intel_object_events AS
SELECT l.object_type,l.object_id,l.event_id,
       count(*)::integer AS link_records,
       array_agg(DISTINCT l.link_source ORDER BY l.link_source) AS link_sources
FROM public.pc_delivery_direct_incidents l
GROUP BY l.object_type,l.object_id,l.event_id;

-- The network used by both market products; parent-child roles are explicit.
CREATE OR REPLACE VIEW public.pc_intel_network AS
SELECT c.parent_object_id::text AS object_id, 'asset'::text AS object_type,
       c.child_object_id::text AS connected_id, 'asset'::text AS connected_type,
       COALESCE(a.name,c.child_object_id)::text AS connected_name,
       'contains_facility'::text AS business_relationship,
       a.asset_type::text AS connected_category,
       a.country::text AS country,
       a.latitude::double precision AS latitude,
       a.longitude::double precision AS longitude
FROM public.pc_delivery_facility_children c
LEFT JOIN public.pc_assets a ON a.asset_id=c.child_object_id
UNION ALL
SELECT a.asset_id::text, 'asset', a.operator_entity_id::text, 'entity',
       COALESCE(e.name,a.operator_entity_id)::text, 'operated_by',
       'company',a.country::text,NULL::double precision,NULL::double precision
FROM public.pc_assets a JOIN public.pc_entities e ON e.entity_id=a.operator_entity_id
WHERE a.operator_entity_id IS NOT NULL
UNION ALL
SELECT m.mobile_asset_id::text,'mobile_asset',m.owner_entity_id::text,'entity',
       COALESCE(e.name,m.owner_entity_id)::text,'recorded_owner',
       'company',NULL::text,NULL::double precision,NULL::double precision
FROM public.pc_mobile_assets m JOIN public.pc_entities e ON e.entity_id=m.owner_entity_id
WHERE m.owner_entity_id IS NOT NULL
UNION ALL
SELECT m.mobile_asset_id::text,'mobile_asset',m.operator_entity_id::text,'entity',
       COALESCE(e.name,m.operator_entity_id)::text,'recorded_operator',
       'company',NULL::text,NULL::double precision,NULL::double precision
FROM public.pc_mobile_assets m JOIN public.pc_entities e ON e.entity_id=m.operator_entity_id
WHERE m.operator_entity_id IS NOT NULL;

-- Three data products for each of the first two apps.
-- A: operating picture, B: business network, C: full development history.
CREATE OR REPLACE VIEW public.pc_intel_trade_picture AS
SELECT trade_section AS section,object_type,object_id,name,category,subtype,country,
       latitude,longitude,payload
FROM public.pc_delivery_catalog;

CREATE OR REPLACE VIEW public.pc_intel_security_picture AS
SELECT event_id,title,event_type,event_family,recorded_severity,
       source_risk_level,source_risk_trend,occurred_at,location_label,
       latitude_text,longitude_text,record_status,metadata,
       evidence_count,narrative
FROM public.pc_intel_event_details;

CREATE OR REPLACE VIEW public.pc_intel_trade_network AS
SELECT * FROM public.pc_intel_network;
CREATE OR REPLACE VIEW public.pc_intel_security_network AS
SELECT * FROM public.pc_intel_network;

CREATE OR REPLACE VIEW public.pc_intel_trade_developments AS
SELECT e.*,l.object_type,l.object_id,l.link_sources,
       CASE WHEN l.event_id IS NULL THEN false ELSE true END AS explicitly_linked
FROM public.pc_intel_event_details e
LEFT JOIN public.pc_intel_object_events l ON l.event_id=e.event_id;
CREATE OR REPLACE VIEW public.pc_intel_security_developments AS
SELECT e.*,l.object_type,l.object_id,l.link_sources,
       CASE WHEN l.event_id IS NULL THEN false ELSE true END AS explicitly_linked
FROM public.pc_intel_event_details e
LEFT JOIN public.pc_intel_object_events l ON l.event_id=e.event_id;
COMMIT;

-- A view is live after commit; no manual refresh needed during SQL seeding.
-- Source risk fields are surfaced only where recorded; no risk ratings are invented.
-- Tests:
-- SELECT event_id,title,narrative,evidence_count FROM public.pc_intel_event_details WHERE title ILIKE '%YM Pioneer%';
-- SELECT connected_name,business_relationship FROM public.pc_intel_trade_network WHERE object_id='PORT_UAE_PORT_OF_FUJAIRAH';
-- SELECT event_id,object_type,object_id FROM public.pc_intel_security_developments WHERE event_id='EVT_20260714_MARITIME_SECURITY_INCIDENT_9937799';
