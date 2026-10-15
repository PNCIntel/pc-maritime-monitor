-- Medina completion pack, run after 20261015_medina_interception_operational.sql.
-- Existing published judgment is the authority; this script does not fabricate impact or actor attribution.
BEGIN;
UPDATE public.pc_events e SET metadata=coalesce(e.metadata,'{}'::jsonb) ||
jsonb_build_object(
 'risk_scope','Medina region / western Saudi contingency travel and connected transport',
 'infrastructure_context',jsonb_build_array(
 jsonb_build_object('name','Prince Mohammad bin Abdulaziz International Airport (MED)','mode','aviation','relationship','Relevant contingency airport; no incident impact established'),
 jsonb_build_object('name','King Abdulaziz International Airport (JED)','mode','aviation','relationship','Alternative gateway; no impact attributed to Medina incident'),
 jsonb_build_object('name','Yanbu Airport (YNB)','mode','aviation','relationship','Alternative gateway; no impact attributed to Medina incident'),
 jsonb_build_object('name','Haramain High Speed Railway','mode','rail','relationship','Western Saudi connectivity; no disruption established'),
 jsonb_build_object('name','Medina regional access roads','mode','road','relationship','Potential contingency movement; no closure established')),
 'source_claims',jsonb_build_array(
 jsonb_build_object('publisher','Associated Press','url','https://apnews.com/article/ffa2a29fe8f91f400b0b75067d269ad3','claim','Coalition-reported interception in Medina region; reported attribution and denial must remain distinguished','verification','attributed contemporary reporting'),
 jsonb_build_object('publisher','Channel NewsAsia','url','https://www.channelnewsasia.com/world/saudi-arabia-medina-missile-intercepted-houthi-6462156','claim','Contemporary reporting on interception and Houthi denial','verification','attributed contemporary reporting'),
 jsonb_build_object('publisher','UK FCDO','url','https://www.gov.uk/foreign-travel-advice/saudi-arabia/regional-risks','claim','Travel-advice context; not proof of continuous airport operations','verification','official travel-advice context')),
 'source_claims_scope','Editorial source references; not substituted for independently populated pc_event_evidence',
 'attribution_guardrail','Do not attribute launch to Houthis: denial reported; launching actor unconfirmed')
WHERE e.event_id='PC_SA_MEDINA_CRUISE_INTERCEPTION_20261015';
COMMIT;
-- Review actual existing candidates. A shared actor mention is NOT a proven operational link.
SELECT event_id,title,start_date,verification_status,
 metadata->>'situation_id' AS situation_id,
 metadata->>'launch_actor' AS launch_actor
FROM public.pc_events
WHERE event_id <> 'PC_SA_MEDINA_CRUISE_INTERCEPTION_20261015'
AND (title ILIKE '%Houthi%' OR description ILIKE '%Houthi%'
  OR metadata->>'situation_id'='SIT-SAU-AVIATION-ESCALATION-202610')
ORDER BY start_date DESC LIMIT 80;
-- After candidate review, add individual pc_event_relationships rows using the live schema.
-- Only 'same wider escalation context' is permissible absent corroborated operational causation.
