-- P&C event intelligence dossier: analyst-approved forward judgments.
-- No generated defaults, inferred status, or fabricated geography.
CREATE TABLE IF NOT EXISTS public.pc_event_intelligence_outlooks (
 event_id text PRIMARY KEY,
 current_risk text,
 confidence text,
 pc_assessment text NOT NULL CHECK (length(btrim(pc_assessment)) > 0),
 risk_outlook text NOT NULL CHECK (length(btrim(risk_outlook)) > 0),
 monitoring_indicators jsonb NOT NULL DEFAULT '[]'::jsonb
    CHECK (jsonb_typeof(monitoring_indicators)='array'),
 assessed_at timestamptz NOT NULL,
 publication_status text NOT NULL DEFAULT 'draft'
    CHECK (publication_status IN ('draft','published','withdrawn')),
 source_note text,
 updated_at timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE public.pc_event_intelligence_outlooks IS
 'Reviewed, forward-looking event-level intelligence; no automatic severity-to-risk conversion.';
-- Coverage audit: one row per existing canonical event, not a new event silo.
CREATE OR REPLACE VIEW public.pc_v_event_dossier_readiness AS
SELECT e.event_id, e.title, e.start_date,
  (SELECT count(*) FROM public.pc_event_evidence v WHERE v.event_id=e.event_id) AS evidence_observations,
  (SELECT count(*) FROM public.pc_event_asset_links l WHERE l.event_id=e.event_id) AS explicit_asset_links,
  (SELECT count(*) FROM public.pc_event_relationships l
     WHERE l.from_event_id=e.event_id OR l.to_event_id=e.event_id) AS connected_developments,
  EXISTS (SELECT 1 FROM public.pc_v07_event_assessments a WHERE a.event_id=e.event_id
     AND lower(coalesce(a.assessment_status,'')) IN ('published','approved','reviewed')) AS approved_analysis,
  EXISTS (SELECT 1 FROM public.pc_event_intelligence_outlooks o WHERE o.event_id=e.event_id
     AND o.publication_status='published') AS published_outlook
FROM public.pc_events e;
-- Populate by source-linked analysis, then explicitly approve publication.
-- Audit priority: SELECT * FROM public.pc_v_event_dossier_readiness
-- WHERE evidence_observations=0 OR NOT approved_analysis OR NOT published_outlook
-- ORDER BY start_date DESC LIMIT 100;
