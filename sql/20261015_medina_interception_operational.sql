-- P&C | Medina region cruise-missile interception | 15 October 2026
-- Source-qualified published analysis; no airport strike, damage, closure or attacker asserted.
BEGIN;
INSERT INTO public.pc_events
 (event_id,title,start_date,event_type,verification_status,description,metadata,intelligence_visible)
VALUES
 ('PC_SA_MEDINA_CRUISE_INTERCEPTION_20261015',
 'Coalition reports cruise-missile interception in Medina region',
 '2026-10-15T00:00:00Z','air_defence_interception','reported',
 'Saudi-led coalition said it intercepted and destroyed a cruise missile in the Medina region on 15 October. The coalition did not attribute the launch; Houthis denied targeting Saudi Arabia that day. No damage, casualties or Medina airport operating disruption established. Time is day-precision placeholder, not actual interception time.',
 jsonb_build_object(
   'event_date_precision','day','incident_time_unconfirmed',true,
   'intelligence_lens','security_disruption','editorial_classification','security',
   'situation_id','SIT-SAU-AVIATION-ESCALATION-202610',
   'reported_weapon','cruise missile','launch_actor','unconfirmed',
   'houthi_denial','reported','airport_impact','not established',
   'geographic_scope','Medina region, Saudi Arabia',
   'do_not_geocode_to_airport',true,
   'infrastructure_context',jsonb_build_array(
     jsonb_build_object('name','Prince Mohammad bin Abdulaziz International Airport (MED/OEMA)','role','contingency travel / monitoring','status','No strike or operating disruption established from this interception'),
     jsonb_build_object('name','King Abdulaziz International Airport (JED/OEJN)','role','regional alternate departure / schedule monitoring','status','No impact attributed to Medina interception'),
     jsonb_build_object('name','Yanbu Airport (YNB/OEYN)','role','western Saudi alternative aviation / monitoring','status','No impact attributed to Medina interception'),
     jsonb_build_object('name','Haramain High Speed Railway, Medina–Jeddah–Mecca','role','intercity passenger connectivity','status','No rail disruption established'),
     jsonb_build_object('name','Medina access roads and onward western Saudi road network','role','ground contingency connectivity','status','No road closure established')
   ),
   'editorial_guardrail','Potential geographic exposure is not evidence of asset damage, closure or direct targeting',
   'source_urls',jsonb_build_array(
     'https://apnews.com/article/ffa2a29fe8f91f400b0b75067d269ad3',
     'https://www.channelnewsasia.com/world/saudi-arabia-medina-missile-intercepted-houthi-6462156',
     'https://www.gov.uk/foreign-travel-advice/saudi-arabia/regional-risks')
 ),true)
ON CONFLICT(event_id) DO UPDATE SET
 description=EXCLUDED.description,
 metadata=COALESCE(public.pc_events.metadata,'{}'::jsonb)||EXCLUDED.metadata,
 intelligence_visible=true;

-- Connect only to exact existing assets, where discoverable, as contextual exposure; never mark damage.
WITH resolved AS (
 SELECT e.event_id,
   COALESCE(jsonb_agg(jsonb_build_object(
       'asset_id',a.asset_id,'name',a.name,'relationship','relevant infrastructure / monitoring',
       'impact_status','not established') ORDER BY a.name)
       FILTER (WHERE a.asset_id IS NOT NULL),'[]'::jsonb) AS assets
 FROM public.pc_events e
 LEFT JOIN public.pc_assets a ON
      (lower(a.name) IN ('prince mohammad bin abdulaziz international airport',
                        'prince mohammed bin abdulaziz international airport',
                        'medina airport','king abdulaziz international airport',
                        'yanbu airport','haramain high speed railway'))
 WHERE e.event_id='PC_SA_MEDINA_CRUISE_INTERCEPTION_20261015'
 GROUP BY e.event_id
)
UPDATE public.pc_events e SET metadata=COALESCE(e.metadata,'{}'::jsonb)||
 jsonb_build_object('resolved_infrastructure_context',resolved.assets)
FROM resolved WHERE e.event_id=resolved.event_id;

INSERT INTO public.pc_v07_event_assessments
 (ingestion_job_id,source_record_key,event_id,event_title,what_happened,what_it_means,
 operational_impact,commercial_impact,pc_assessment,monitoring_indicators,research_gaps,
 evidence_urls,assessment_status,version)
SELECT 'b2ad9fa3-3dd1-4c41-a0a0-202610150014'::uuid,
 'PC_GSA_UPDATE14_MEDINA_20261015',e.event_id,e.title,e.description,
 'Medina-region interception broadens geographic contingency-planning exposure in western Saudi Arabia without proving a missile attack on, or interruption at, Medina Airport.',
 'No reported Medina airport suspension, ground transport restriction, casualties or physical damage linked to this incident.',
 'Operators dependent on a single western Saudi exit gateway should test alternate itineraries against live operator and authority notices.',
 'The Medina-region interception challenges reliance on Medina as the sole aviation contingency. The FCDO exception for Medina Airport is travel advice, not a guarantee of uninterrupted operations.',
 '["Saudi coalition and Civil Defence updates","MED, JED and YNB airline and airport operating notices","FCDO travel-advice revisions","Haramain rail and intercity access notices","Debris/casualty confirmation","Authoritative attribution updates"]'::jsonb,
 '["Actual interception time and location not published","Launcher unconfirmed","No airport or surface infrastructure impact established"]'::jsonb,
 '["https://apnews.com/article/ffa2a29fe8f91f400b0b75067d269ad3","https://www.channelnewsasia.com/world/saudi-arabia-medina-missile-intercepted-houthi-6462156","https://www.gov.uk/foreign-travel-advice/saudi-arabia/regional-risks"]'::jsonb,
 'published',1
FROM public.pc_events e WHERE e.event_id='PC_SA_MEDINA_CRUISE_INTERCEPTION_20261015'
AND NOT EXISTS(SELECT 1 FROM public.pc_v07_event_assessments a WHERE a.event_id=e.event_id AND a.source_record_key='PC_GSA_UPDATE14_MEDINA_20261015');

INSERT INTO public.pc_event_assessment_judgments
 (event_id,assessment_id,current_risk,risk_scope,risk_outlook,monitoring_indicators,confidence,
 evidence_basis,judgment_status,assessed_at,valid_until,analyst_approval,risk_level,risk_rationale,rating_as_of)
SELECT e.event_id,a.assessment_id,
 'ELEVATED geographic contingency exposure; no evidence of Medina Airport being struck or suspended.',
 'Medina region and western Saudi aviation / alternative exit-route planning',
 'Further official warnings or airport operating restrictions could affect alternate-exit planning. No direct MED, JED, YNB or rail interruption follows from this interception alone.',
 '["Saudi Civil Defence and coalition bulletins","MED/JED/YNB operating and airline notices","Updated FCDO advice","Intercity road and Haramain rail operational notices","Verified debris/casualty reports","Attribution and further launches"]'::jsonb,
 'Moderate',
 '[{"claim":"Coalition reported Medina-region cruise missile interception; launcher not named; Houthis denied involvement","source_url":"https://apnews.com/article/ffa2a29fe8f91f400b0b75067d269ad3","claim_status":"attributed reporting"},{"claim":"Medina remains an explicit airport exception in UK advice at this assessment date","source_url":"https://www.gov.uk/foreign-travel-advice/saudi-arabia/regional-risks","claim_status":"official guidance"}]'::jsonb,
 'published',now(),now()+interval '72 hours','operational_source_qualified','ELEVATED',
 'A reported interception in the Medina region increases western Saudi contingency-route exposure. This is a geographic planning risk, not a claim of airport attack, closure or damage.',
 DATE '2026-10-15'
FROM public.pc_events e
JOIN LATERAL (SELECT assessment_id FROM public.pc_v07_event_assessments a
 WHERE a.event_id=e.event_id ORDER BY version DESC,created_at DESC LIMIT 1)a ON true
WHERE e.event_id='PC_SA_MEDINA_CRUISE_INTERCEPTION_20261015'
ON CONFLICT(event_id) DO UPDATE SET
 assessment_id=excluded.assessment_id,current_risk=excluded.current_risk,risk_scope=excluded.risk_scope,
 risk_outlook=excluded.risk_outlook,monitoring_indicators=excluded.monitoring_indicators,
 confidence=excluded.confidence,evidence_basis=excluded.evidence_basis,
 judgment_status='published',assessed_at=excluded.assessed_at,valid_until=excluded.valid_until,
 analyst_approval=excluded.analyst_approval,risk_level=excluded.risk_level,
 risk_rationale=excluded.risk_rationale,rating_as_of=excluded.rating_as_of,updated_at=now();
COMMIT;
SELECT e.event_id,e.title,e.start_date,j.risk_level,j.confidence,j.risk_scope,j.risk_rationale,j.risk_outlook,j.judgment_status,e.metadata->'resolved_infrastructure_context' AS linked_existing_assets
FROM public.pc_events e JOIN public.pc_event_assessment_judgments j USING(event_id)
WHERE e.event_id='PC_SA_MEDINA_CRUISE_INTERCEPTION_20261015';
