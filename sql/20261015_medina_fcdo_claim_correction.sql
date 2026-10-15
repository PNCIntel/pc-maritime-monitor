-- Correct previously published Medina analytical wording without changing risk level,
-- source event facts or unrelated assessments. Apply in Supabase SQL editor.
BEGIN;
UPDATE public.pc_v07_event_assessments SET
pc_assessment='The reported Medina-region interception challenges reliance on a single western Saudi contingency gateway. FCDO regional advice warns of renewed Houthi threats to Saudi infrastructure, including airports, and potential further escalation; it does not attest to Medina Airport operating status.'
WHERE event_id='PC_SA_MEDINA_CRUISE_INTERCEPTION_20261015'
  AND pc_assessment LIKE '%FCDO exception for Medina Airport%';
UPDATE public.pc_events SET metadata=COALESCE(metadata,'{}'::jsonb) ||
jsonb_build_object('fdco_claim_correction_20261015',jsonb_build_object(
 'status','unsupported_exception_withdrawn',
 'source_url','https://www.gov.uk/foreign-travel-advice/saudi-arabia/regional-risks',
 'source_claim','FCDO warns of renewed Houthi threats against infrastructure including airports, and possible escalation; no Medina Airport operating-status guarantee',
 'interpretation','Verify any operating restrictions directly against Saudi aviation authorities, airport and airline notices',
 'source_type','official travel guidance'))
WHERE event_id='PC_SA_MEDINA_CRUISE_INTERCEPTION_20261015';
COMMIT;
