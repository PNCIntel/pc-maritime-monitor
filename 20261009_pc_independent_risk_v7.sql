-- Power & Corridors | Independent risk prototype v7
-- Additive views/functions. NO change to GSA records, existing risk tables or event records.
-- Event severity != regional risk. Every calculated score is PRELIMINARY / model-derived.
BEGIN;

CREATE OR REPLACE VIEW public.pc_v7_event_analytical_basis AS
WITH latest AS (
  SELECT DISTINCT ON (event_id) event_id, version, assessment_id, assessment_status,
    what_happened, what_it_means, commercial_impact, operational_impact,
    pc_assessment, monitoring_indicators, evidence_urls, research_gaps
  FROM public.pc_v07_event_assessments
  ORDER BY event_id, version DESC NULLS LAST, assessment_id DESC NULLS LAST
), basis AS (
  SELECT d.event_id,d.title,d.event_type,d.event_family,d.occurred_at,d.narrative,
    d.location_label,d.recorded_severity,d.evidence_count,d.evidence,
    COALESCE(NULLIF(to_jsonb(e)->>'region_code',''),
             NULLIF(to_jsonb(d)->>'region_code','')) AS explicit_region_code,
    COALESCE(NULLIF(to_jsonb(e)->>'verification_status',''),
             NULLIF(to_jsonb(e)->>'record_status','')) AS verification_status,
    COALESCE(NULLIF(d.recorded_severity,''),NULLIF(e.severity,'')) AS severity_label,
    a.version AS analysis_version,a.assessment_status AS event_analysis_status,
    a.what_happened,a.what_it_means,a.commercial_impact,a.operational_impact,
    a.pc_assessment,a.monitoring_indicators,a.evidence_urls,a.research_gaps,
    (SELECT count(*) FROM public.pc_event_locations el WHERE el.event_id=d.event_id) AS location_count,
    (SELECT count(*) FROM public.pc_event_impacts im WHERE im.event_id=d.event_id) AS structured_impact_count
  FROM public.pc_intel_event_details d
  LEFT JOIN public.pc_events e ON e.event_id=d.event_id
  LEFT JOIN latest a ON a.event_id=d.event_id
), rated AS (
  SELECT b.*,
    CASE upper(trim(coalesce(severity_label,'')))
      WHEN 'CRITICAL' THEN 90 WHEN 'EXTREME' THEN 95 WHEN 'SEVERE' THEN 85
      WHEN 'HIGH' THEN 70 WHEN 'MAJOR' THEN 75 WHEN 'MEDIUM' THEN 50
      WHEN 'MODERATE' THEN 50 WHEN 'LOW' THEN 25 WHEN 'MINOR' THEN 25
      WHEN 'INFO' THEN 10 WHEN 'INFORMATIONAL' THEN 10
      ELSE NULL END AS severity_weight,
    CASE
      WHEN lower(coalesce(verification_status,'')) IN ('confirmed','verified','official','corroborated') THEN 'confirmed_or_verified'
      WHEN lower(coalesce(verification_status,'')) IN ('disputed','refuted','false') THEN 'disputed_or_refuted'
      WHEN lower(coalesce(verification_status,'')) IN ('unverified','reported','pending','provisional') THEN 'unverified_or_provisional'
      ELSE 'not_established' END AS verification_band
  FROM basis b
)
SELECT rated.*,
  -- The event score expresses documented incident SEVERITY, not probability or an approved regional threat rating.
  CASE WHEN severity_weight IS NOT NULL
       THEN LEAST(100, severity_weight + CASE WHEN structured_impact_count > 0 THEN 5 ELSE 0 END)
       ELSE NULL END::integer AS pc_event_significance_score,
  CASE WHEN severity_weight IS NULL THEN 'not_scored_missing_or_unmapped_severity'
       WHEN verification_band = 'disputed_or_refuted' THEN 'disputed_do_not_aggregate'
       WHEN verification_band = 'confirmed_or_verified' THEN 'model_scored_evidence_review_required'
       ELSE 'provisional_verification_required' END AS pc_event_scoring_status,
  'P&C prototype v7: mapped reported severity (10-95) plus five points where structured impact exists; verification affects eligibility, not factual severity. No GSA input.'::text AS pc_scoring_explanation
FROM rated;

-- Exactly the same canonical events feed Trade. Potential impacts remain explicitly potential.
CREATE OR REPLACE VIEW public.pc_v7_trade_event_intelligence AS
SELECT event_id,title,event_type,event_family,occurred_at,location_label,
  explicit_region_code,verification_status,severity_label,
  what_happened,what_it_means,commercial_impact,operational_impact,
  pc_assessment,monitoring_indicators,research_gaps,evidence_urls,
  event_analysis_status,analysis_version,structured_impact_count,
  pc_event_significance_score,pc_event_scoring_status,
  CASE WHEN structured_impact_count > 0 THEN 'structured_impacts_recorded'
       WHEN nullif(trim(coalesce(operational_impact,'')),'') IS NOT NULL THEN 'analyst_operational_impact_not_independently_verified'
       WHEN nullif(trim(coalesce(commercial_impact,'')),'') IS NOT NULL THEN 'analyst_commercial_impact_not_independently_verified'
       ELSE 'impact_not_recorded' END AS impact_evidence_level
FROM public.pc_v7_event_analytical_basis;

-- Function enables historic as-of views without falsely redating events to the query date.
-- Only explicit event region codes are accepted; no fuzzy location-name matching.
CREATE OR REPLACE FUNCTION public.pc_v7_independent_region_risk_at(p_as_of date)
RETURNS TABLE (
 region_code text, as_of_date date, events_last_30d bigint,
 events_previous_30d bigint, scored_events bigint,
 confirmed_scored_events bigint, average_significance numeric,
 activity_change text, pc_indicative_risk text, coverage_status text,
 assessment_status text, methodology text
)
LANGUAGE sql STABLE AS $$
 WITH regional_events AS (
   SELECT b.explicit_region_code AS region,
     (b.occurred_at::date) event_day, b.pc_event_significance_score score,
     b.verification_band
   FROM public.pc_v7_event_analytical_basis b
   WHERE b.explicit_region_code IS NOT NULL
     AND b.occurred_at IS NOT NULL
     AND b.verification_band <> 'disputed_or_refuted'
     AND b.occurred_at::date > p_as_of - 60
     AND b.occurred_at::date <= p_as_of
 ), grouped AS (
  SELECT r.region,
   count(*) FILTER (WHERE event_day > p_as_of-30) n_current,
   count(*) FILTER (WHERE event_day <= p_as_of-30) n_previous,
   count(score) FILTER (WHERE event_day > p_as_of-30) n_scored,
   count(score) FILTER (WHERE event_day > p_as_of-30 AND verification_band='confirmed_or_verified') n_confirmed,
   round(avg(score) FILTER (WHERE event_day > p_as_of-30),1) avg_score
  FROM regional_events r GROUP BY r.region
 )
 SELECT g.region, p_as_of, g.n_current,g.n_previous,g.n_scored,g.n_confirmed,g.avg_score,
   CASE WHEN g.n_current < 3 THEN 'INSUFFICIENT_DATA'
        WHEN g.n_previous < 3 THEN 'BASELINE_INSUFFICIENT'
        WHEN g.n_current >= g.n_previous*1.5 AND g.n_current-g.n_previous >= 3 THEN 'INCREASING'
        WHEN g.n_current*1.5 <= g.n_previous AND g.n_previous-g.n_current >= 3 THEN 'DECREASING'
        ELSE 'STABLE_EVENT_FREQUENCY' END,
   CASE WHEN g.n_current < 3 OR g.n_scored < 3 OR g.n_confirmed < 2 THEN 'NOT_RATED'
        WHEN g.avg_score >= 82 AND g.n_current >= 5 THEN 'SEVERE'
        WHEN g.avg_score >= 65 THEN 'HIGH'
        WHEN g.avg_score >= 45 THEN 'ELEVATED'
        ELSE 'LOWER_OBSERVED_SEVERITY' END,
   CASE WHEN g.n_current < 3 OR g.n_scored < 3 OR g.n_confirmed < 2 THEN 'INSUFFICIENT_CONFIRMED_COVERAGE'
        ELSE 'PARTIAL_OBSERVED_EVENT_COVERAGE' END,
   'MODEL_DRAFT_NOT_APPROVED',
   'P&C v7 preliminary: last 30 days explicit-region events; >=3 events, >=3 scored, >=2 verified; mean mapped incident severity, frequency trend relative to preceding 30 days; not a probability model and not derived from GSA.'
 FROM grouped g;
$$;
COMMIT;

-- Read-only validation: inspect region assignment and preliminary model results.
SELECT count(*) AS total_events,
 count(*) FILTER (WHERE severity_weight IS NOT NULL) AS mapped_severity,
 count(*) FILTER (WHERE explicit_region_code IS NOT NULL) AS explicitly_geocoded_region,
 count(*) FILTER (WHERE verification_band='confirmed_or_verified') AS confirmed_or_verified,
 count(*) FILTER (WHERE what_it_means IS NOT NULL) AS with_event_analysis
FROM public.pc_v7_event_analytical_basis;
SELECT * FROM public.pc_v7_independent_region_risk_at(current_date) ORDER BY events_last_30d DESC LIMIT 25;
