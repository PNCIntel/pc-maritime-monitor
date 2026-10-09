-- Database-wide REVIEW ONLY. Fingerprints are candidate duplicates, not certified identical incidents.
-- Does not update the source records or automatically create canonical events.
CREATE OR REPLACE VIEW public.pc_v8_assessment_reimport_candidates AS
WITH source_rows AS (
 SELECT a.assessment_id, a.ingestion_job_id,a.source_record_key,
        a.event_id,a.event_title,a.created_at,
        md5(concat_ws('|',lower(trim(coalesce(a.event_title,''))),
              lower(trim(coalesce(a.what_happened,''))),
              coalesce(a.evidence_urls::text,''))) fingerprint
 FROM public.pc_v07_event_assessments a
 WHERE a.event_id IS NULL
), ranked AS (
 SELECT s.*,
 count(*) OVER (PARTITION BY fingerprint) AS repeated_rows,
 row_number() OVER (PARTITION BY fingerprint ORDER BY created_at, assessment_id) AS duplicate_candidate_number
 FROM source_rows s
)
SELECT * FROM ranked WHERE repeated_rows>1;

SELECT count(*) AS candidate_rows,
 count(*) FILTER (WHERE duplicate_candidate_number>1) AS redundant_content_candidates,
 count(DISTINCT fingerprint) AS repeat_content_groups
FROM public.pc_v8_assessment_reimport_candidates;
