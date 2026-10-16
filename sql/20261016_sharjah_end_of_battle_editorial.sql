-- Sharjah End of Battle: substantive editorial profile, no automated approval.
BEGIN;
UPDATE public.pc_events e
SET metadata = coalesce(e.metadata,'{}'::jsonb) || jsonb_build_object(
 'editorial_profile', jsonb_build_object(
 'review_status','draft_for_analyst_review',
 'significance','major',
 'current_threat','not_assessed',
 'operational_exposure','none_identified_in_supplied_reports',
 'client_action','information_only_monitor_material_updates',
 'significance_rationale','The scale, international reach and combination of cyber intrusion, virtual-asset laundering and reported violent coercion make the police operation a major intelligence development. Significance is not a finding of continuing threat or confirmed client exposure.',
 'analysis','Sharjah Police and prosecutors reported the disruption of four interconnected cross-border criminal networks involving alleged system intrusion, digital-wallet theft, fraud, laundering and violent coercion. The authorities reported preventing a kidnapping and killing plot linked to obtaining wallet access. The case illustrates the convergence of cyber-enabled financial crime and physical intimidation, and the investigative importance of tracing digital-asset flows across jurisdictions. The reported police action reduces the immediate exposure associated with the identified operation, but the reporting does not establish whether other participants, assets or related networks remain active. It does not name affected P&C client infrastructure or establish transport-service interruption. The accused have not been convicted on the supplied reporting.',
 'outlook','No incident-specific probability forecast is warranted from these two articles. The material next developments are any authoritative charging or court updates, clarification of recoveries and protected institutions, identification of additional connected networks, and credible evidence of continuing threats. An escalation assessment would require new verified information, not merely the size of the historical allegations.',
 'monitoring',jsonb_build_array(
  'Judicial process: verify charges, corporate-entity proceedings and subsequent court outcomes; do not describe allegations as proven.',
  'Financial tracing: distinguish alleged flows, safeguarded assets and actually seized or recovered assets as authorities revise figures.',
  'Network continuity: look for official identification of outstanding suspects, linked cells or further arrests before inferring ongoing threat.',
  'Victim and sector exposure: identify any confirmed institution or infrastructure victim and any demonstrated operational outage before creating exposure links.',
  'Cross-border cooperation: record new jurisdictional actions where supported by official statements or independently attributed reporting.'
 ),
 'reported_measures',jsonb_build_array(
  jsonb_build_object('label','Networks disrupted','value','Four','qualification','Police-reported'),
  jsonb_build_object('label','Accused individuals','value','33 from 12 nationalities','qualification','Reported; no finding of guilt'),
  jsonb_build_object('label','Suspected money laundering','value','AED 8.825 billion','qualification','Alleged flows, not recovered proceeds'),
  jsonb_build_object('label','Assets reportedly safeguarded','value','AED 65 billion','qualification','Protected exposure, not seized property'),
  jsonb_build_object('label','Funds and assets seized','value','More than AED 200 million','qualification','Seizure measure; not additive with the other figures'),
  jsonb_build_object('label','Digital wallets examined','value','More than 3,000','qualification','As reported')
 ),
 'source_urls',e.metadata->'source_urls',
 'report_date_qualification','15 October 2026 is the public reporting date, not independently verified raid date'
 )
)
WHERE e.event_id='PC_AE_SHARJAH_END_OF_BATTLE_20261015'
  AND coalesce(e.metadata->'editorial_profile'->>'review_status','') <> 'approved';
COMMIT;
SELECT event_id,record_status,verification_status,
 metadata->'editorial_profile'->>'review_status' as editorial_review_status,
 metadata->'editorial_profile'->>'significance' as proposed_significance,
 jsonb_array_length(coalesce(metadata->'source_claims','[]'::jsonb)) as source_claims
FROM public.pc_events WHERE event_id='PC_AE_SHARJAH_END_OF_BATTLE_20261015';
