-- P&C v8 | NON-DESTRUCTIVE REPAIR OF HORMUZ SOURCE OBSERVATIONS
-- Creates a durable reconciliation ledger; does not overwrite the underlying assessment or event.
-- Specifically prevents repeated job imports from being mistaken for separate attacks.
BEGIN;
CREATE TABLE IF NOT EXISTS public.pc_repair_observation_ledger (
 assessment_id bigint PRIMARY KEY,
 ingestion_job_id uuid,
 source_record_key text,
 observed_title text,
 observation_fingerprint text,
 incident_case_key text,
 case_role text NOT NULL DEFAULT 'unreviewed',
 review_status text NOT NULL DEFAULT 'pending',
 suggested_vessel text,
 incident_date date,
 source_url text,
 rationale text,
 linked_event_id text,
 reviewed_by text,
 reviewed_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now(),
 CONSTRAINT pc_repair_review_status_chk CHECK (review_status IN ('pending','requires_source_review','reviewed','rejected')),
 CONSTRAINT pc_repair_case_role_chk CHECK (case_role IN ('unreviewed','primary_observation','repeat_import','ambiguous_distinct_case'))
);

-- Rows assigned to the same input key AND matching source content across these two
-- specific jobs represent a repeated import. Differing input keys are NOT merged.
WITH candidates AS (
 SELECT a.assessment_id::bigint AS assessment_id,
        a.ingestion_job_id, a.source_record_key, a.event_title,
        md5(concat_ws('|',lower(trim(coalesce(a.event_title,''))),
            lower(trim(coalesce(a.what_happened,''))),
            coalesce(a.evidence_urls::text,''))) AS fp,
        row_number() OVER (
          PARTITION BY a.source_record_key,
            md5(concat_ws('|',lower(trim(coalesce(a.event_title,''))),
              lower(trim(coalesce(a.what_happened,''))), coalesce(a.evidence_urls::text,'')))
          ORDER BY a.created_at, a.assessment_id
        ) AS repeat_number,
        a.evidence_urls::text AS source_urls
 FROM public.pc_v07_event_assessments a
 WHERE a.assessment_id IN (157,160,162,163,164,165,174,176,177,178,179)
   AND a.ingestion_job_id::text IN (
      'bf8b8545-d96a-4e03-9fdc-f4f799e2f5e8',
      'a08db16e-7e6f-4cdc-8a13-775ac8ba2e96')
), proposed AS (
 SELECT c.*,
   CASE c.source_record_key
    WHEN 'input:6' THEN 'HORMUZ-20260914-UNKNOWN'
    WHEN 'input:24' THEN 'HORMUZ-20261001-KAZIMAHIII'
    WHEN 'input:26' THEN 'HORMUZ-20260928-ALFUNTAS'
    WHEN 'input:27' THEN 'HORMUZ-20260929-VESSEL-A'
    WHEN 'input:28' THEN 'HORMUZ-20260929-VESSEL-B'
    WHEN 'input:29' THEN 'HORMUZ-20260929-VESSEL-C'
   END AS case_key,
   CASE c.source_record_key
    WHEN 'input:6' THEN DATE '2026-09-14'
    WHEN 'input:24' THEN DATE '2026-10-01'
    WHEN 'input:26' THEN DATE '2026-09-28'
    ELSE DATE '2026-09-29'
   END AS proposed_date,
   CASE c.source_record_key
    WHEN 'input:24' THEN 'Kazimah III (source review needed)'
    WHEN 'input:26' THEN 'Al Funtas (source review needed)'
    ELSE NULL
   END AS vessel_hint
 FROM candidates c
)
INSERT INTO public.pc_repair_observation_ledger (
 assessment_id,ingestion_job_id,source_record_key,observed_title,
 observation_fingerprint,incident_case_key,case_role,review_status,
 suggested_vessel,incident_date,source_url,rationale
)
SELECT p.assessment_id,p.ingestion_job_id,p.source_record_key,p.event_title,
 p.fp,p.case_key,
 CASE WHEN p.repeat_number>1 THEN 'repeat_import'
      WHEN p.source_record_key IN ('input:27','input:28','input:29')
       THEN 'ambiguous_distinct_case'
      ELSE 'primary_observation' END,
 'requires_source_review',p.vessel_hint,p.proposed_date,
 CASE WHEN p.source_record_key='input:6' THEN
 'https://www.twz.com/news-features/claims-swirl-around-u-s-marines-injured-aboard-mystery-vessel-attacked-in-the-strait-of-hormuz'
 ELSE 'https://splash247.com/fresh-attacks-hit-hormuz-tanker-and-saudi-oil-gateway/' END,
 CASE WHEN p.repeat_number>1 THEN 'Repeated import of the same source key/content across two jobs; retain for provenance, not as an extra incident.'
      WHEN p.source_record_key IN ('input:27','input:28','input:29') THEN 'One of three separate reported 29 Sep vessel attacks; vessel-to-input mapping NOT independently proven.'
      ELSE 'Candidate source observation; verify vessel, date and any corresponding canonical event before approval.' END
FROM proposed p
ON CONFLICT (assessment_id) DO NOTHING;

-- Expose only one observation per source key in this specific reviewed group;
-- this view does not imply that one observation equals one verified incident.
CREATE OR REPLACE VIEW public.pc_v8_hormuz_observation_review AS
SELECT l.assessment_id,l.ingestion_job_id,l.source_record_key,
 l.incident_case_key,l.case_role,l.review_status,l.suggested_vessel,
 l.incident_date,l.source_url,l.linked_event_id,l.rationale,
 a.event_title,a.what_happened,a.evidence_urls,a.assessment_status
FROM public.pc_repair_observation_ledger l
JOIN public.pc_v07_event_assessments a ON a.assessment_id=l.assessment_id
WHERE l.incident_case_key LIKE 'HORMUZ-%';
COMMIT;

-- Expect: 11 stored observation rows, 6 proposed source cases,
-- 5 repeated-import rows; 3 ambiguous source cases awaiting vessel resolution.
SELECT case_role, count(*) FROM public.pc_v8_hormuz_observation_review GROUP BY case_role ORDER BY case_role;
SELECT incident_case_key,count(*) AS observation_rows,
 count(*) FILTER (WHERE case_role='repeat_import') AS repeated_import_rows,
 string_agg(assessment_id::text, ', ' ORDER BY assessment_id) AS assessment_ids
FROM public.pc_v8_hormuz_observation_review GROUP BY incident_case_key ORDER BY incident_case_key;
