-- P&C Global Risk Briefing: independently authored forward outlook.
-- Worldwide, mode-agnostic; no default risk score or inferred forecast.
-- Apply in Supabase SQL editor before publishing outlook records.
CREATE TABLE IF NOT EXISTS public.pc_risk_assessment_outlooks (
 assessment_id text PRIMARY KEY,
 risk_outlook text NOT NULL CHECK (length(btrim(risk_outlook)) > 0),
 monitoring_indicators jsonb NOT NULL DEFAULT '[]'::jsonb
   CHECK (jsonb_typeof(monitoring_indicators)='array'),
 assessed_at timestamptz NOT NULL,
 publication_status text NOT NULL DEFAULT 'draft'
   CHECK (publication_status IN ('draft','published','withdrawn')),
 source_note text,
 updated_at timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE public.pc_risk_assessment_outlooks IS
 'Analyst-authored outlook linked to published P&C assessment; independent of incident severity, trend or editorial review date.';
-- Existing security assessment feed and all source/event data remain unchanged.
-- Publish only after an analyst has supported the outlook from underlying evidence.
-- No seed rows: illustrative outlook labels must never be auto-populated.
