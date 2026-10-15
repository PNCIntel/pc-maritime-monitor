-- READ ONLY: Run in Supabase SQL Editor; return outputs to P&C for reconciliation.
-- Same intelligence_visible scope as the app, with explicit commercial exclusions.
-- Classifications are audit candidates; review edge cases before changing publication status.
WITH scope AS (
 SELECT e.event_id,e.title,e.start_date,e.event_type,e.verification_status,
        lower(coalesce(e.event_type,'')) AS typ,
        lower(coalesce(e.metadata->>'intelligence_lens',e.metadata->>'intelligence_classification','')) AS lens,
        lower(coalesce(e.metadata->>'event_category','')) AS category
 FROM public.pc_events e
 WHERE e.intelligence_visible IS TRUE
), eligible AS (
 SELECT * FROM scope
 WHERE lens NOT IN ('commercial','trade','capital','not intelligence','excluded')
 AND (
  lens IN ('security','security & disruption','security and disruption','disruption')
  OR category IN ('security','disruption')
  OR typ ~ '(attack|strike|missile|intercept|military|sanction|protest|unrest|drone|grounding|sinking|wreck|boarding|fire|collision|derail|closure|disruption|outage|incident|flood|storm|weather|aviation|security|hazard|emergency)'
 )
), versions AS (
 SELECT a.event_id,count(*) AS versions,
 count(*) FILTER(WHERE a.assessment_status='published') AS published_versions,
 count(*) FILTER(WHERE a.assessment_status='reviewed') AS reviewed_versions,
 count(*) FILTER(WHERE a.assessment_status='draft') AS draft_versions,
 count(*) FILTER(WHERE nullif(btrim(a.pc_assessment),'') IS NOT NULL) AS with_analysis,
 count(*) FILTER(WHERE jsonb_array_length(coalesce(a.monitoring_indicators,'[]'::jsonb))>0) AS with_indicators,
 max(a.created_at) AS last_assessment_at
 FROM public.pc_v07_event_assessments a
 WHERE a.event_id IS NOT NULL
 GROUP BY a.event_id
), audited AS (
 SELECT e.*,coalesce(v.versions,0) AS versions,coalesce(v.published_versions,0) AS published_versions,
 coalesce(v.reviewed_versions,0) AS reviewed_versions,coalesce(v.draft_versions,0) AS draft_versions,
 coalesce(v.with_analysis,0) AS with_analysis,coalesce(v.with_indicators,0) AS with_indicators,
 v.last_assessment_at,
 CASE WHEN v.event_id IS NULL THEN 'MISSING_ASSESSMENT'
      WHEN coalesce(v.with_analysis,0)=0 THEN 'NO_SUBSTANTIVE_ANALYSIS'
      WHEN coalesce(v.published_versions,0)=0 THEN 'NOT_PUBLISHED'
      WHEN coalesce(v.with_indicators,0)=0 THEN 'MISSING_MONITORING_INDICATORS'
      ELSE 'EVENT_ASSESSMENT_PRESENT' END AS audit_status
 FROM eligible e LEFT JOIN versions v ON v.event_id=e.event_id
)
SELECT audit_status,count(*) AS event_count
FROM audited GROUP BY audit_status ORDER BY event_count DESC;

-- Detailed coverage by event ID: run separately if needed.
WITH scope AS (
 SELECT e.event_id,e.title,e.start_date,e.event_type,e.verification_status,
 lower(coalesce(e.event_type,'')) typ,
 lower(coalesce(e.metadata->>'intelligence_lens',e.metadata->>'intelligence_classification','')) lens,
 lower(coalesce(e.metadata->>'event_category','')) category
 FROM public.pc_events e WHERE e.intelligence_visible IS TRUE
)
SELECT s.event_id,s.start_date,s.title,s.event_type,s.verification_status,
 count(a.assessment_id) AS assessment_versions,
 count(a.assessment_id) FILTER(WHERE a.assessment_status='published') AS published_versions,
 max(a.created_at) AS last_assessed_at,
 CASE WHEN count(a.assessment_id)=0 THEN 'MISSING'
      WHEN count(a.assessment_id) FILTER(WHERE a.assessment_status='published')=0 THEN 'DRAFT_OR_REVIEWED_ONLY'
      ELSE 'PUBLISHED_VERSION_EXISTS' END AS assessment_coverage
FROM scope s LEFT JOIN public.pc_v07_event_assessments a ON a.event_id=s.event_id
WHERE s.lens NOT IN ('commercial','trade','capital','not intelligence','excluded')
 AND (s.lens IN ('security','security & disruption','security and disruption','disruption')
 OR s.category IN ('security','disruption')
 OR s.typ ~ '(attack|strike|missile|intercept|military|sanction|protest|unrest|drone|grounding|sinking|wreck|boarding|fire|collision|derail|closure|disruption|outage|incident|flood|storm|weather|aviation|security|hazard|emergency)')
GROUP BY s.event_id,s.start_date,s.title,s.event_type,s.verification_status
ORDER BY s.start_date DESC NULLS LAST,s.event_id;
