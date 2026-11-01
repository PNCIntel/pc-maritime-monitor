-- BTW maritime security taxonomy / phase 1
-- Execute in Supabase SQL editor after reviewing the scoped event IDs.
-- Updates classification LABELS only. Does not alter event identity, sources,
-- verification, geography, severity, record status or dates.
-- Keeps event_type as originally reported for auditability.
BEGIN;

-- Guard against editing the wrong ReCAAP archive.
DO $$
DECLARE n int; missing int;
BEGIN
 SELECT count(*), count(*) FILTER (WHERE metadata->>'source_record_id' IS NULL)
 INTO n, missing FROM public.pc_events
 WHERE metadata->>'source_dataset'='recaap_incidents_2024_2026';
 IF n <> 277 OR missing <> 0 THEN
  RAISE EXCEPTION 'Stopped: expected 277 ReCAAP rows and zero missing IDs; found %, %',n,missing;
 END IF;
END $$;

-- A unified family/category; attempt stays distinct. CAT 1–4 untouched.
UPDATE public.pc_events
SET event_domain='maritime',
    event_family='maritime_crime',
    event_category='piracy_and_armed_robbery',
    event_subcategory=CASE
      WHEN event_type ILIKE 'Attempted Piracy / Armed Robbery'
        THEN 'attempted_piracy_or_armed_robbery'
      ELSE 'reported_piracy_or_armed_robbery'
    END,
    updated_at=now()
WHERE metadata->>'source_dataset'='recaap_incidents_2024_2026'
  AND event_type IN ('Piracy / Armed Robbery','Attempted Piracy / Armed Robbery')
  AND (
     event_domain IS DISTINCT FROM 'maritime'
     OR event_family IS DISTINCT FROM 'maritime_crime'
     OR event_category IS DISTINCT FROM 'piracy_and_armed_robbery'
     OR event_subcategory IS DISTINCT FROM
        CASE WHEN event_type='Attempted Piracy / Armed Robbery'
            THEN 'attempted_piracy_or_armed_robbery'
            ELSE 'reported_piracy_or_armed_robbery' END
  );

-- Individually documented piracy candidates, not composite summaries.
WITH scoped(event_id,category,subcategory) AS (
 VALUES
 ('EVT_SEC_002','piracy_and_armed_robbery','attempted_boarding'),
 ('EVT_INTEL_20260917_UKMTO_ADEN_SKIFF','piracy_and_armed_robbery','suspicious_approach'),
 ('EVENT_2AFAA287B764B728','piracy_and_armed_robbery','attempted_boarding')
)
UPDATE public.pc_events e
SET event_domain='maritime',
    event_family='maritime_crime',
    event_category=s.category,
    event_subcategory=s.subcategory,
    updated_at=now()
FROM scoped s
WHERE e.event_id=s.event_id;

-- Conflict-related reports. Preserve original event_type and uncertainty.
-- Explicit IDs only; broad Hormuz groups require individual review.
WITH scoped(event_id,subcategory) AS (
 VALUES
 ('PC_UKMTO_189_26_20261030','reported_projectile_attack'),
 ('PC_UKMTO_186_26_20261029','reported_projectile_attack'),
 ('PC_HORMUZ_GFS_GISELLE_20261014','reported_vessel_attack'),
 ('EVT_PC_GFS_GISELLE_ATTACK_20261014','reported_vessel_attack'),
 ('PC_HORMUZ_GFS_PRIDE_20261013','reported_vessel_attack'),
 ('EVT_PC_GFS_PRIDE_ATTACK_20261013','reported_vessel_attack'),
 ('EVT_PC_AL_SAADIYAT_ATTACK_20261013','reported_vessel_attack'),
 ('EVT_PC_ALFONSO_ATTACK_20261013','reported_vessel_attack'),
 ('EVT_MAR_20260916_US_CONTRACTED_VESSEL_HORMUZ_ATTACK','missile_drone_attack'),
 ('EVT_HORMUZ_20260920_AL_MARYAH_DRONE','reported_drone_attack'),
 ('HOU026','reported_houthi_attack'),
 ('HOU025','reported_houthi_attack'),
 ('HOU021','reported_houthi_attack'),
 ('HOU019','reported_houthi_attack')
)
UPDATE public.pc_events e
SET event_domain='maritime',
    event_family='armed_conflict',
    event_category='conflict_related_vessel_attack',
    event_subcategory=s.subcategory,
    updated_at=now()
FROM scoped s
WHERE e.event_id=s.event_id;

-- Postflight: check exactly what is classified.
SELECT event_family,event_category,event_subcategory,count(*) AS events
FROM public.pc_events
WHERE metadata->>'source_dataset'='recaap_incidents_2024_2026'
   OR event_id IN ('EVT_SEC_002','EVT_INTEL_20260917_UKMTO_ADEN_SKIFF',
      'EVENT_2AFAA287B764B728','PC_UKMTO_189_26_20261030',
      'PC_UKMTO_186_26_20261029','HOU026')
GROUP BY 1,2,3 ORDER BY 1,2,3;

COMMIT;

-- Review separately before updating:
-- EVT_PIRACY_20260910 combines GLAMOR boarding with SWARD ransom release.
-- EL GAIA, AL MARYAH and GFS vessels may have multiple descriptions of one incident.
-- Broad 'strait_of_hormuz' family records require evidence-level classification.
-- No aviation hijack claims, military boarding exercises, smuggling operations,
-- vessel accidents, or traffic indicators should enter the piracy layer by keyword.
