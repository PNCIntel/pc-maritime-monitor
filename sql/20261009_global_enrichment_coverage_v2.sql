-- P&C global enrichment audit v2
-- Replaces v1's placeholder zero source/geography metrics.
-- Detects fields defensively from row JSON, so optional columns don't break deployment.
-- Signals are candidate evidence only; they are NOT verified sources/positions.
BEGIN;
CREATE OR REPLACE VIEW public.pc_v_global_enrichment_coverage AS
WITH objects AS (
  SELECT 'company'::text object_type, entity_id::text object_id,
         name::text display_name, to_jsonb(c) AS payload
    FROM public.pc_entities c
  UNION ALL
  SELECT 'infrastructure',asset_id::text,name::text,to_jsonb(a)
    FROM public.pc_assets a
  UNION ALL
  SELECT 'mobile_asset',mobile_asset_id::text,name::text,to_jsonb(m)
    FROM public.pc_mobile_assets m
  UNION ALL
  SELECT 'event',event_id::text,title::text,to_jsonb(e)
    FROM public.pc_events e
), signals AS (
 SELECT o.*,
  COALESCE(o.payload->'metadata','{}'::jsonb) AS metadata_json,
  COALESCE(o.payload->'sources','[]'::jsonb) AS sources_json
 FROM objects o
)
SELECT s.object_type,s.object_id,s.display_name,
 (NULLIF(BTRIM(s.display_name),'') IS NOT NULL) AS has_name,
 (
   COALESCE(NULLIF(BTRIM(s.payload->>'source_url'),''),'') <> ''
   OR COALESCE(NULLIF(BTRIM(s.payload->>'website_url'),''),'') <> ''
   OR COALESCE(NULLIF(BTRIM(s.metadata_json->>'source_url'),''),'') <> ''
   OR COALESCE(NULLIF(BTRIM(s.metadata_json->>'source'),''),'') <> ''
   OR s.metadata_json ? 'research_sources'
   OR (jsonb_typeof(s.sources_json)='array' AND jsonb_array_length(s.sources_json)>0)
 ) AS has_source_link,
 (
   CASE WHEN s.object_type='event'
    THEN EXISTS (SELECT 1 FROM public.pc_event_locations loc
                 WHERE loc.event_id=s.object_id)
    ELSE (
       NULLIF(BTRIM(COALESCE(s.payload->>'latitude',s.payload->>'lat','')),'') IS NOT NULL
       AND NULLIF(BTRIM(COALESCE(s.payload->>'longitude',s.payload->>'lon','')),'') IS NOT NULL
    )
   END
 ) AS has_verified_geography,
 CASE
  WHEN s.object_type='event' AND COALESCE(s.payload->>'verification_status','')=''
   THEN 'Verification status absent'
  WHEN s.object_type='mobile_asset' AND COALESCE(s.payload->>'imo','')=''
   THEN 'IMO missing or not applicable'
  ELSE NULL
 END::text AS review_detail
FROM signals s;

COMMENT ON VIEW public.pc_v_global_enrichment_coverage IS
 'V2 signals only. has_verified_geography is a legacy column name: it means a recorded event spatial link or a populated coordinate pair, not independently verified coordinates. has_source_link is an unverified candidate source signal.';

CREATE OR REPLACE VIEW public.pc_v_global_enrichment_backlog AS
SELECT *,
 CASE WHEN NOT has_name THEN 'identity_review'
      WHEN object_type='event' AND NOT has_verified_geography THEN 'event_spatial_link_review'
      WHEN NOT has_source_link THEN 'source_discovery'
      WHEN review_detail IS NOT NULL THEN 'record_validation'
      ELSE 'relationship_and_history_enrichment' END AS next_workstream
FROM public.pc_v_global_enrichment_coverage;

COMMIT;

SELECT object_type,COUNT(*) AS total,
 COUNT(*) FILTER (WHERE has_source_link) AS source_candidates,
 COUNT(*) FILTER (WHERE has_verified_geography) AS location_signals,
 COUNT(*) FILTER (WHERE NOT has_name) AS missing_names
FROM public.pc_v_global_enrichment_coverage
GROUP BY object_type ORDER BY object_type;
