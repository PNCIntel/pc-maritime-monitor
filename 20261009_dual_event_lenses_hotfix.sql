-- P&C v6: business-ready dual Security / Trade event lenses.
-- Additive, read-only views over existing production records.
-- Prerequisite: pc_intel_event_details and the existing assessment/impact structures.
BEGIN;
CREATE OR REPLACE VIEW public.pc_v6_event_assessment_basis AS
WITH linked AS (
 SELECT DISTINCT assessment_id, event_id FROM public.pc_risk_assessment_events
), combined AS (
 SELECT l.event_id, r.assessment_id, r.assessment_date,
        r.risk_level, r.trend, r.confidence, r.approval_status, r.coverage_status,
        to_jsonb(r) AS assessment_record
 FROM linked l JOIN public.pc_risk_assessments r ON r.assessment_id = l.assessment_id
)
SELECT DISTINCT ON (event_id) event_id, assessment_id, assessment_date,
 risk_level, trend, confidence, approval_status, coverage_status, assessment_record
FROM combined
ORDER BY event_id,
 CASE WHEN lower(coalesce(approval_status,'')) IN ('approved','published') THEN 0 ELSE 1 END,
 assessment_date DESC NULLS LAST, assessment_id DESC;

-- No implicit ratings are generated from event volume, severity or metadata.
CREATE OR REPLACE VIEW public.pc_v6_security_events AS
SELECT e.event_id, e.title, e.event_type, e.event_family, e.occurred_at,
 e.narrative, e.location_label, e.latitude_text, e.longitude_text,
 e.record_status, e.recorded_severity, e.evidence_count, e.evidence,
 COALESCE(NULLIF(to_jsonb(src)->>'verification_status',''),
          NULLIF(to_jsonb(src)->>'record_status','')) AS event_verification,
 a.assessment_id, a.assessment_date,
 CASE WHEN lower(coalesce(a.approval_status,'')) IN ('approved','published') THEN a.risk_level END AS approved_risk_level,
 CASE WHEN lower(coalesce(a.approval_status,'')) IN ('approved','published') THEN a.trend END AS approved_risk_trend,
 a.approval_status AS assessment_approval_status, a.confidence AS assessment_confidence,
 a.coverage_status, a.assessment_record,
 (SELECT jsonb_agg(to_jsonb(loc)) FROM public.pc_event_locations loc WHERE loc.event_id=e.event_id) AS recorded_locations,
 NULL::jsonb AS risk_tags, -- deferred: pc_event_risk_tags has no event_id; requires verified mapping
 (SELECT jsonb_agg(to_jsonb(im)) FROM public.pc_event_impacts im WHERE im.event_id=e.event_id) AS incident_impacts,
 (SELECT jsonb_agg(to_jsonb(alert)) FROM public.pc_monitoring_alerts alert WHERE alert.event_id=e.event_id) AS monitoring_alerts,
 (SELECT jsonb_agg(to_jsonb(o)) FROM public.pc_monitoring_observations o WHERE o.event_id=e.event_id) AS monitoring_observations
FROM public.pc_intel_event_details e
LEFT JOIN public.pc_events src ON src.event_id=e.event_id
LEFT JOIN public.pc_v6_event_assessment_basis a ON a.event_id=e.event_id;

-- Trade derives consequences from the SAME canonical event, but not security-only conclusions.
-- Both generic and specialist logistics effects are retained verbatim with provenance.
CREATE OR REPLACE VIEW public.pc_v6_trade_event_effects AS
SELECT s.event_id, s.title, s.event_type, s.event_family, s.occurred_at,
 s.narrative, s.location_label, s.record_status, s.event_verification,
 s.recorded_severity, s.approved_risk_level, s.approved_risk_trend,
 s.assessment_date,
 (SELECT jsonb_agg(to_jsonb(im)) FROM public.pc_logistics_event_impacts im WHERE im.event_id=s.event_id) AS logistics_impacts,
 s.incident_impacts AS other_impacts,
 (SELECT jsonb_agg(to_jsonb(ce)) FROM public.pc_company_event_effects ce WHERE ce.event_id=s.event_id) AS company_effects,
 (SELECT jsonb_agg(to_jsonb(l)) FROM public.pc_intel_object_events l WHERE l.event_id=s.event_id) AS linked_objects,
 s.recorded_locations, s.evidence_count, s.evidence
FROM public.pc_v6_security_events s;
COMMIT;

-- Useful validation: event counts, linked assessments and business impacts.
SELECT count(*) AS security_events,
 count(approved_risk_level) AS events_with_approved_rating,
 count(*) FILTER (WHERE recorded_locations IS NOT NULL) AS events_with_location_records
FROM public.pc_v6_security_events;
SELECT count(*) AS trade_events,
 count(*) FILTER (WHERE logistics_impacts IS NOT NULL) AS events_with_logistics_impacts,
 count(*) FILTER (WHERE company_effects IS NOT NULL) AS events_with_company_effects
FROM public.pc_v6_trade_event_effects;
