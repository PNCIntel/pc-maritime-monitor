-- Explicit user-approved Sharjah editorial review, 16 October 2026.
-- Major development significance does not imply high current threat.
BEGIN;
UPDATE public.pc_events
SET metadata=jsonb_set(
 jsonb_set(
  jsonb_set(coalesce(metadata,'{}'::jsonb),'{editorial_profile,review_status}',to_jsonb('approved'::text),true),
  '{editorial_profile,assessed_at}',to_jsonb('2026-10-16T00:00:00+04:00'::text),true),
 '{editorial_profile,evidence_confidence}',to_jsonb('High — police announcement; allegations not adjudicated'::text),true)
 || jsonb_build_object(
  'geographic_reference',jsonb_build_object(
   'label','Sharjah, United Arab Emirates — city reference only',
   'latitude',25.3463,'longitude',55.4209,
   'source_url','https://www.openstreetmap.org/search?query=Sharjah%20United%20Arab%20Emirates',
   'precision','city reference; not an arrest, raid or crime scene')
 )
WHERE event_id='PC_AE_SHARJAH_END_OF_BATTLE_20261015'
 AND metadata->'editorial_profile'->>'significance'='major';
COMMIT;
SELECT event_id,metadata->'editorial_profile'->>'review_status' editorial_status,
 metadata->'editorial_profile'->>'assessed_at' assessment_date,
 metadata->'editorial_profile'->>'evidence_confidence' evidence_confidence,
 metadata->'geographic_reference' geographic_reference
FROM public.pc_events WHERE event_id='PC_AE_SHARJAH_END_OF_BATTLE_20261015';
