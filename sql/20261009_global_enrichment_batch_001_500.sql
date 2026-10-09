-- P&C | Global Enrichment | Batch 001 (500 canonical records)
-- Requires sql/20261009_global_enrichment_coverage_v2.sql.
-- Creates review findings and queues 125 objects in each of the four audited classes.
-- Non-destructive: never modifies canonical object, relationship or source tables.
BEGIN;
CREATE TABLE IF NOT EXISTS public.pc_enrichment_batch_items (
 batch_key text NOT NULL,
 object_type text NOT NULL,
 object_id text NOT NULL,
 display_name text,
 priority integer NOT NULL,
 source_signal boolean NOT NULL,
 location_signal boolean NOT NULL,
 review_status text NOT NULL DEFAULT 'queued'
   CHECK (review_status IN ('queued','researching','needs_confirmation','ready_for_approval','approved','rejected','published')),
 findings jsonb NOT NULL DEFAULT '{}'::jsonb,
 reviewer_notes text,
 reviewed_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY (batch_key,object_type,object_id)
);
CREATE INDEX IF NOT EXISTS pc_enrichment_batch_queue_idx
 ON public.pc_enrichment_batch_items(batch_key,review_status,priority,object_type);

WITH ranked AS (
 SELECT c.*,
  CASE
   WHEN NOT c.has_name THEN 100
   WHEN NOT c.has_source_link AND c.object_type='event' AND NOT c.has_verified_geography THEN 95
   WHEN NOT c.has_source_link THEN 90
   WHEN c.object_type='event' AND NOT c.has_verified_geography THEN 80
   WHEN c.review_detail IS NOT NULL THEN 70
   ELSE 20 END AS priority,
  ROW_NUMBER() OVER (PARTITION BY c.object_type ORDER BY
    CASE
     WHEN NOT c.has_name THEN 100
     WHEN NOT c.has_source_link AND c.object_type='event' AND NOT c.has_verified_geography THEN 95
     WHEN NOT c.has_source_link THEN 90
     WHEN c.object_type='event' AND NOT c.has_verified_geography THEN 80
     WHEN c.review_detail IS NOT NULL THEN 70
     ELSE 20 END DESC,
    c.object_id ASC
  ) AS within_type
 FROM public.pc_v_global_enrichment_coverage c
 WHERE c.object_type IN ('company','infrastructure','mobile_asset','event')
), chosen AS (
 SELECT * FROM ranked WHERE within_type <= 125
), enriched AS (
 SELECT c.*,
  CASE c.object_type
   WHEN 'company' THEN (SELECT to_jsonb(x) FROM public.pc_entities x WHERE x.entity_id::text=c.object_id LIMIT 1)
   WHEN 'infrastructure' THEN (SELECT to_jsonb(x) FROM public.pc_assets x WHERE x.asset_id::text=c.object_id LIMIT 1)
   WHEN 'mobile_asset' THEN (SELECT to_jsonb(x) FROM public.pc_mobile_assets x WHERE x.mobile_asset_id::text=c.object_id LIMIT 1)
   WHEN 'event' THEN (SELECT to_jsonb(x) FROM public.pc_events x WHERE x.event_id::text=c.object_id LIMIT 1)
  END AS original
 FROM chosen c
)
INSERT INTO public.pc_enrichment_batch_items
(batch_key,object_type,object_id,display_name,priority,source_signal,location_signal,findings)
SELECT 'GLOBAL-001-500',object_type,object_id,display_name,priority,
 has_source_link,has_verified_geography,
 jsonb_build_object(
  'review_detail', review_detail,
  'source_url_candidate',COALESCE(NULLIF(original->>'source_url',''),NULLIF(original->>'website_url',''),
                                NULLIF(original#>>'{metadata,source_url}','')),
  'country_candidate',COALESCE(NULLIF(original->>'country',''),NULLIF(original->>'country_code','')),
  'coordinates_present',has_verified_geography,
  'source_signal_present',has_source_link,
  'name',display_name,
  'identified_gaps',to_jsonb(array_remove(ARRAY[
    CASE WHEN NOT has_source_link THEN 'discover_primary_sources' END,
    CASE WHEN object_type='event' AND NOT has_verified_geography THEN 'review_event_location' END,
    CASE WHEN object_type='infrastructure' AND NOT has_verified_geography THEN 'review_facility_geography' END,
    CASE WHEN review_detail IS NOT NULL THEN 'review_identity_or_status' END
  ]::text[],NULL))
 )
FROM enriched
ON CONFLICT(batch_key,object_type,object_id) DO NOTHING;
COMMIT;

-- QA gate: exactly 500 rows, 125 per class, each unique by canonical object ID.
SELECT object_type,COUNT(*) AS queued,
 COUNT(*) FILTER(WHERE NOT source_signal) AS source_research_needed,
 COUNT(*) FILTER(WHERE NOT location_signal) AS missing_location_signal,
 COUNT(*) FILTER(WHERE review_status='queued') AS still_queued
FROM public.pc_enrichment_batch_items
WHERE batch_key='GLOBAL-001-500'
GROUP BY object_type ORDER BY object_type;

-- Export this SELECT as CSV from Supabase SQL Editor and return the file for
-- manual source research, provenance verification and proposed enrichments.
SELECT batch_key,object_type,object_id,display_name,priority,
       source_signal,location_signal,review_status,
       findings->>'source_url_candidate' AS candidate_source,
       findings->>'country_candidate' AS recorded_country,
       findings->'identified_gaps' AS identified_gaps,
       reviewer_notes
FROM public.pc_enrichment_batch_items
WHERE batch_key='GLOBAL-001-500'
ORDER BY priority DESC,object_type,object_id;
