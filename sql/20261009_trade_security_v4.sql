-- Additive delivery improvements. Requires the v1 delivery and intelligence views.
-- No writes to canonical records; these are LIVE views during SQL batch loading.
BEGIN;
CREATE OR REPLACE VIEW public.pc_v4_trade_facilities AS
SELECT a.asset_id::text AS object_id, a.name::text AS name,
       a.asset_type::text AS category, a.subtype::text AS subtype,
       a.country::text AS country, a.latitude::double precision AS latitude,
       a.longitude::double precision AS longitude,
       a.operator_entity_id::text AS operator_id,
       e.name::text AS operator_name,
       CASE WHEN a.latitude BETWEEN -90 AND 90 AND a.longitude BETWEEN -180 AND 180
                 AND NOT (a.latitude=0 AND a.longitude=0) THEN true ELSE false END AS is_mapped
FROM public.pc_assets a
LEFT JOIN public.pc_entities e ON e.entity_id=a.operator_entity_id;

-- Keep incident location separate from the location of an explicitly linked fixed asset.
-- An asset marker is geographic CONTEXT, not an assertion of incident coordinates.
CREATE OR REPLACE VIEW public.pc_v4_security_geo AS
WITH direct AS (
 SELECT d.event_id, d.occurred_at,d.title,d.event_type,d.event_family,d.narrative,
        d.location_label,d.source_risk_level,d.source_risk_trend,d.record_status,
        d.evidence_count,d.latitude_text,d.longitude_text,
        CASE WHEN d.latitude_text ~ '^[-+]?[0-9]+(\.[0-9]+)?$'
            THEN d.latitude_text::double precision ELSE NULL END AS event_lat,
        CASE WHEN d.longitude_text ~ '^[-+]?[0-9]+(\.[0-9]+)?$'
            THEN d.longitude_text::double precision ELSE NULL END AS event_lon
 FROM public.pc_intel_event_details d
), linked AS (
 SELECT DISTINCT ON (l.event_id)
        l.event_id, a.asset_id AS location_asset_id, a.name AS location_asset_name,
        a.latitude::double precision AS asset_lat, a.longitude::double precision AS asset_lon
 FROM public.pc_delivery_direct_incidents l
 JOIN public.pc_assets a ON a.asset_id=l.object_id
 WHERE l.object_type='asset' AND a.latitude BETWEEN -90 AND 90
       AND a.longitude BETWEEN -180 AND 180 AND NOT (a.latitude=0 AND a.longitude=0)
 ORDER BY l.event_id,a.asset_id
)
SELECT d.event_id,d.occurred_at,d.title,d.event_type,d.event_family,d.narrative,
       d.location_label,d.source_risk_level,d.source_risk_trend,d.record_status,d.evidence_count,
       CASE WHEN d.event_lat BETWEEN -90 AND 90 AND d.event_lon BETWEEN -180 AND 180
                  AND NOT (d.event_lat=0 AND d.event_lon=0) THEN d.event_lat
            ELSE l.asset_lat END AS latitude,
       CASE WHEN d.event_lat BETWEEN -90 AND 90 AND d.event_lon BETWEEN -180 AND 180
                  AND NOT (d.event_lat=0 AND d.event_lon=0) THEN d.event_lon
            ELSE l.asset_lon END AS longitude,
       CASE WHEN d.event_lat BETWEEN -90 AND 90 AND d.event_lon BETWEEN -180 AND 180
                  AND NOT (d.event_lat=0 AND d.event_lon=0) THEN 'event_location'
            WHEN l.location_asset_id IS NOT NULL THEN 'linked_facility_context'
            ELSE 'unmapped' END AS map_precision,
       l.location_asset_id,l.location_asset_name
FROM direct d LEFT JOIN linked l ON l.event_id=d.event_id;
COMMIT;
-- Verify the sources and confirm geographic precision is described correctly:
-- SELECT map_precision,count(*) FROM public.pc_v4_security_geo GROUP BY map_precision;
-- SELECT name,country,latitude,longitude FROM public.pc_v4_trade_facilities WHERE name ILIKE '%Fujairah%' OR name ILIKE '%Khalifa%';
-- SELECT title,map_precision,latitude,longitude FROM public.pc_v4_security_geo WHERE title ILIKE '%Hormuz%' LIMIT 30;
