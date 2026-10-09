-- Global P&C enrichment coverage and review queue v1
-- Read-only across existing canonical tables. No inferred identities or scores.
CREATE OR REPLACE VIEW public.pc_v_global_enrichment_coverage AS
SELECT 'company'::text object_type, entity_id::text object_id, name::text display_name,
       (NULLIF(BTRIM(name),'') IS NOT NULL) has_name,
       false has_source_link,
       false has_verified_geography,
       NULL::text review_detail
FROM public.pc_entities
UNION ALL
SELECT 'infrastructure',asset_id::text,name::text,
       (NULLIF(BTRIM(name),'') IS NOT NULL),
       false,false,NULL::text
FROM public.pc_assets
UNION ALL
SELECT 'mobile_asset',mobile_asset_id::text,name::text,
       (NULLIF(BTRIM(name),'') IS NOT NULL),
       (NULLIF(BTRIM(COALESCE(metadata->>'source_url','')),'') IS NOT NULL),
       false,
       CASE WHEN imo IS NULL OR BTRIM(imo)='' THEN 'IMO missing or not applicable' ELSE NULL END
FROM public.pc_mobile_assets
UNION ALL
SELECT 'event',event_id::text,title::text,
       (NULLIF(BTRIM(title),'') IS NOT NULL),
       (metadata ? 'research_sources' OR metadata ? 'source_url'),
       EXISTS (SELECT 1 FROM public.pc_event_locations l WHERE l.event_id=pc_events.event_id),
       CASE WHEN verification_status IS NULL THEN 'Verification not recorded' ELSE NULL END
FROM public.pc_events;

CREATE OR REPLACE VIEW public.pc_v_global_enrichment_backlog AS
SELECT *, 
 CASE WHEN NOT has_name THEN 'critical_identity'
      WHEN object_type='event' AND NOT has_verified_geography THEN 'geography_review'
      WHEN object_type='event' AND NOT has_source_link THEN 'source_review'
      WHEN object_type='mobile_asset' AND review_detail IS NOT NULL THEN 'identifier_review'
      ELSE 'general_enrichment' END AS next_workstream
FROM public.pc_v_global_enrichment_coverage;

SELECT object_type,COUNT(*) total,
 SUM(has_name::int) named,
 SUM(has_source_link::int) with_source_signal,
 SUM(has_verified_geography::int) spatially_linked,
 COUNT(*) FILTER(WHERE next_workstream='critical_identity') missing_names
FROM public.pc_v_global_enrichment_backlog GROUP BY object_type ORDER BY object_type;
