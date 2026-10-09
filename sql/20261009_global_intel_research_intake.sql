-- P&C Intelligence research intake: global, cross-modal, source-provenanced.
-- Additive staging only: does not imply that reports are verified incidents.
-- Repeat-safe. Run in Supabase SQL Editor, then open Research & source intake.
BEGIN;
CREATE TABLE IF NOT EXISTS public.pc_intel_research_queue (
  research_key text PRIMARY KEY,
  headline text NOT NULL,
  observation_date date,
  geography text,
  mode text NOT NULL,
  observation_kind text NOT NULL,
  summary text NOT NULL,
  source_url text NOT NULL,
  source_name text NOT NULL,
  evidence_status text NOT NULL DEFAULT 'reported_unverified'
    CHECK (evidence_status IN ('reported_unverified','source_review','corroborated','verified','rejected')),
  canonical_event_id text,
  vessel_imo text,
  research_notes text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS pc_intel_research_queue_date_idx
 ON public.pc_intel_research_queue (observation_date DESC);
CREATE INDEX IF NOT EXISTS pc_intel_research_queue_status_idx
 ON public.pc_intel_research_queue (evidence_status, mode);

INSERT INTO public.pc_intel_research_queue
(research_key,headline,observation_date,geography,mode,observation_kind,summary,
 source_url,source_name,evidence_status,research_notes,metadata)
VALUES
('PCRC_20261007_QATAR_TANKER',
 'Tanker attack reported north of Qatar',DATE '2026-10-07','North of Qatar / Central Gulf',
 'maritime','reported_attack',
 'Maritime reporting describes a tanker attack and casualties north of Qatar; identity, casualty figures and operational consequences require source reconciliation.',
 'https://www.rivieramm.com/news-content-hub/casualties-reported-in-tanker-attack-off-qatar-vlcc-on-fire-near-fujairah-90225',
 'Riviera Maritime Media','source_review',
 'Check UKMTO 158-26, original Ambrey/Vanguard/Marisks reporting, IMO, owner and manager. Confirm whether canonical event exists before publishing.',
 '{"claim_sources":["UKMTO","Ambrey","Vanguard","Marisks"],"claimed_vessel":"ACERS","identity_not_corroborated_in_this_batch":true}'::jsonb),
('PCRC_20261008_FUJAIRAH_OFFSHORE',
 'Suspected offshore tanker fire east of Fujairah',DATE '2026-10-08','Offshore Fujairah / Gulf of Oman',
 'maritime','suspected_incident',
 'A reported satellite thermal anomaly and suspected vessel fire east of Fujairah require independent confirmation; do not count as an established hostile attack.',
 'https://www.rivieramm.com/news-content-hub/casualties-reported-in-tanker-attack-off-qatar-vlcc-on-fire-near-fujairah-90225',
 'Riviera Maritime Media','reported_unverified',
 'Check the original satellite observation, vessel identity and whether an incident is independently verified.',
 '{"reported_evidence":"satellite thermal anomaly","location_precision":"approximate offshore zone"}'::jsonb),
('PCRC_20261009_AMBREY_EG_SERVICE',
 'Maritime security service footprint advertised for Equatorial Guinea',NULL,
 'Equatorial Guinea / Gulf of Guinea','security_services','provider_service',
 'A provider advertises an Equatorial Guinea maritime security service; delivery arrangements, regulatory permissions, coverage and local operating assets require direct verification.',
 'https://ambrey.com/vessel-support-services/equatorial-guinea-security-service/',
 'Ambrey','source_review',
 'Model as a security service offering, NOT as a vessel attack. Verify current page content, licensing, dates, local partnerships and delivery method before asset linkage.',
 '{"provider":"Ambrey","service_type":"maritime_security","not_an_incident":true}'::jsonb)
ON CONFLICT (research_key) DO UPDATE SET
  headline=EXCLUDED.headline,summary=EXCLUDED.summary,
  source_url=EXCLUDED.source_url,source_name=EXCLUDED.source_name,
  research_notes=EXCLUDED.research_notes,
  updated_at=now();

CREATE OR REPLACE VIEW public.pc_v_intel_research_inbox AS
 SELECT research_key,headline,observation_date,geography,mode,observation_kind,
 summary,source_url,source_name,evidence_status,canonical_event_id,vessel_imo,
 research_notes,metadata FROM public.pc_intel_research_queue;

COMMIT;
SELECT evidence_status,mode,count(*) AS observations
FROM public.pc_v_intel_research_inbox
GROUP BY evidence_status,mode ORDER BY mode,evidence_status;
