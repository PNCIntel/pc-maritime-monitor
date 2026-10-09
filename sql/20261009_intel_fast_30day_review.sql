-- Global intelligence: reuse existing 30-day canonical events as a fast review inbox.
-- A VIEW, not a copy or new batch of fabricated observations.
CREATE OR REPLACE VIEW public.pc_v_intel_30day_review AS
SELECT e.event_id, e.start_date::date AS observed_on,
       e.title AS headline, e.location AS geography, e.event_type,
       e.verification_status, e.record_status,
       e.severity, e.metadata->'research_sources' AS research_sources
FROM public.pc_events e
WHERE e.start_date >= now() - interval '30 days'
  AND e.start_date <= now()
ORDER BY e.start_date DESC;
SELECT COUNT(*) AS recent_events FROM public.pc_v_intel_30day_review;
