-- P&C Enrichment factory: normalize evidence, then expand child objects.
-- No canonical mutations. All writes are repeat-safe, reviewer-controlled.
BEGIN;
CREATE TABLE IF NOT EXISTS public.pc_enrichment_discoveries (
 discovery_key text PRIMARY KEY,
 parent_type text NOT NULL,
 parent_id text NOT NULL,
 proposed_object_type text NOT NULL,
 name text NOT NULL,
 identifier_kind text,
 identifier_value text,
 properties jsonb NOT NULL DEFAULT '{}'::jsonb,
 relationship_kind text,
 source_url text NOT NULL,
 source_publisher text,
 observed_at date,
 valid_from date,
 valid_to date,
 confidence text NOT NULL DEFAULT 'unreviewed',
 review_status text NOT NULL DEFAULT 'candidate'
 CHECK (review_status IN ('candidate','verified','ambiguous','rejected','published')),
 matched_object_type text,
 matched_object_id text,
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS pc_enrichment_discoveries_parent_idx
 ON public.pc_enrichment_discoveries(parent_type,parent_id,review_status);
CREATE INDEX IF NOT EXISTS pc_enrichment_discoveries_id_idx
 ON public.pc_enrichment_discoveries(identifier_kind,identifier_value)
 WHERE identifier_value IS NOT NULL;
CREATE INDEX IF NOT EXISTS pc_enrichment_discoveries_review_idx
 ON public.pc_enrichment_discoveries(review_status,proposed_object_type);

CREATE OR REPLACE VIEW public.pc_v_enrichment_factory_progress AS
SELECT parent_type,proposed_object_type,review_status,
 COUNT(*) AS candidate_children,
 COUNT(DISTINCT (parent_type,parent_id)) AS parent_objects,
 COUNT(DISTINCT source_url) AS source_urls,
 COUNT(*) FILTER(WHERE matched_object_id IS NOT NULL) AS canonical_matches
FROM public.pc_enrichment_discoveries
GROUP BY parent_type,proposed_object_type,review_status;

CREATE OR REPLACE VIEW public.pc_v_enrichment_source_production AS
SELECT source_url,source_publisher,count(*) AS child_facts,
 count(DISTINCT (parent_type,parent_id)) AS parent_objects,
 count(*) FILTER(WHERE review_status='verified') AS verified,
 count(*) FILTER(WHERE review_status='ambiguous') AS ambiguous
FROM public.pc_enrichment_discoveries
GROUP BY source_url,source_publisher;

COMMIT;

-- The immediate next load is source-driven: port -> terminals -> berths,
-- company -> controlled entities -> assets, vessel -> temporal managers/flags.
-- Each extracted child must have its own URL and matching evidence.
SELECT * FROM public.pc_v_enrichment_factory_progress;
