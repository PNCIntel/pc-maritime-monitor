-- Curated context for Medina. IDs come from the user's 15 October existing-event query.
-- Exact existing events only; no launch attribution, causation, shared perpetrator or direct asset impact inferred.
BEGIN;
UPDATE public.pc_events e SET metadata=coalesce(e.metadata,'{}'::jsonb)||jsonb_build_object(
'curated_related_events',jsonb_build_array(
 jsonb_build_object('event_id','PC_YE_HOUTHI_ARAMCO_THREATS_20261013','relationship','Reported targeting threats','rationale','Reported energy and aviation target declarations; contextual escalation, not Medina launch attribution'),
 jsonb_build_object('event_id','PC_YE_AL_SABABAH_FUEL_20261013','relationship','Reported coalition operation','rationale','Contemporaneous Yemen theatre operation; operational connection to Medina interception not established'),
 jsonb_build_object('event_id','PC_SA_DHAHRAN_INTERCEPTION_20261013','relationship','Saudi air-defence context','rationale','Separate reported interception in Saudi Arabia'),
 jsonb_build_object('event_id','EV_SA_COALITION_AIR_THREAT_20261012','relationship','Earlier threat tracking','rationale','Earlier reported coalition tracking of aerial threats'),
 jsonb_build_object('event_id','PC_SA_RIYADH_MISSILE_INTERCEPTED_20261012','relationship','Earlier reported interception','rationale','Separate reported Saudi interception'),
 jsonb_build_object('event_id','PC_SA_RUH_CLOSURE_EXTENSION_20261012','relationship','Aviation operating consequence','rationale','Separate officially reported Riyadh closure extension; not impact from Medina incident'),
 jsonb_build_object('event_id','saudi_aviation_20261011_sanaa11','relationship','Yemen theatre context','rationale','Separate reported strike at Sanaa airport'),
 jsonb_build_object('event_id','saudi_aviation_20261011_ruh11','relationship','Saudi aviation incident context','rationale','Earlier reported Riyadh Terminal 4 incident'),
 jsonb_build_object('event_id','saudi_aviation_update04_20261012_dmm11','relationship','Saudi aviation incident context','rationale','Earlier reported Dammam airport incident')
)) WHERE e.event_id='PC_SA_MEDINA_CRUISE_INTERCEPTION_20261015';
COMMIT;
-- Audit actual resolved links before presenting; no absent record can be opened.
SELECT x->>'event_id' AS related_id, x->>'relationship' AS relationship,
       p.title,p.verification_status,
       CASE WHEN p.event_id IS NULL THEN 'MISSING' ELSE 'EXISTS' END AS resolution
FROM public.pc_events e CROSS JOIN LATERAL jsonb_array_elements(coalesce(e.metadata->'curated_related_events','[]'::jsonb)) x
LEFT JOIN public.pc_events p ON p.event_id=x->>'event_id'
WHERE e.event_id='PC_SA_MEDINA_CRUISE_INTERCEPTION_20261015';
