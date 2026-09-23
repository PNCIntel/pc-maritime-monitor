-- POWER & CORRIDORS | PHASE 13A | PUBLIC SHARED-MODEL EXPANSION
-- Prepared from the public schema export of 2026-09-23.
-- FIRST RUN: Supabase SQL editor, as a privileged migration role.
-- Scope: structural tables only, no changes to existing data/views/policies.
-- Newly created tables are RLS-enabled and only service_role is granted DML.
-- Separate subsequent phase: populate pc_meta_entity_types / pc_meta_columns,
-- and then update Power Admin handlers and per-app authorization policies.
BEGIN;

DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'pc_entities','pc_events','pc_trade_corridors','pc_corridor_segments',
    'pc_sources','pc_source_records','pc_documents','pc_market_observations',
    'pc_sanctions_designations','pc_transactions'
  ] LOOP
    IF to_regclass(format('public.%I', t)) IS NULL THEN
      RAISE EXCEPTION 'Required public table % is missing. Stop migration.', t;
    END IF;
  END LOOP;
END $$;

-- 1) PERSISTENT RESEARCH: investigations, claims, evidence, hypotheses
CREATE TABLE IF NOT EXISTS public.pc_research_projects (
  research_project_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  title text NOT NULL,
  research_domain text NOT NULL,
  question_summary text,
  project_status text NOT NULL DEFAULT 'draft'
    CHECK (project_status IN ('draft','active','paused','completed','archived')),
  audience_codes text[] NOT NULL DEFAULT '{}'::text[],
  scope jsonb NOT NULL DEFAULT '{}'::jsonb,
  owner_label text,
  opened_at timestamptz NOT NULL DEFAULT now(),
  closed_at timestamptz,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (closed_at IS NULL OR closed_at >= opened_at)
);

CREATE TABLE IF NOT EXISTS public.pc_research_questions (
  research_question_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  research_project_id uuid NOT NULL REFERENCES public.pc_research_projects(research_project_id),
  parent_question_id uuid REFERENCES public.pc_research_questions(research_question_id),
  question_text text NOT NULL,
  priority text NOT NULL DEFAULT 'normal'
    CHECK (priority IN ('low','normal','high','urgent')),
  question_status text NOT NULL DEFAULT 'open'
    CHECK (question_status IN ('open','in_progress','answered','unresolved','closed')),
  answer_summary text,
  due_at timestamptz,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.pc_research_claims (
  research_claim_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  research_project_id uuid REFERENCES public.pc_research_projects(research_project_id),
  research_question_id uuid REFERENCES public.pc_research_questions(research_question_id),
  claim_text text NOT NULL,
  claim_type text NOT NULL DEFAULT 'reported'
    CHECK (claim_type IN ('reported','observed','official','derived','analytical','hypothetical')),
  verification_status text NOT NULL DEFAULT 'unverified'
    CHECK (verification_status IN ('unverified','corroborated','verified','contested','refuted','superseded')),
  subject_type text,
  subject_id text,
  valid_from timestamptz,
  valid_to timestamptz,
  reported_at timestamptz,
  confidence numeric(4,3) CHECK (confidence BETWEEN 0 AND 1),
  supersedes_claim_id uuid REFERENCES public.pc_research_claims(research_claim_id),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from)
);

CREATE TABLE IF NOT EXISTS public.pc_claim_evidence (
  claim_evidence_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  research_claim_id uuid NOT NULL REFERENCES public.pc_research_claims(research_claim_id),
  evidence_role text NOT NULL CHECK (evidence_role IN ('supports','contradicts','qualifies','context')),
  source_id text REFERENCES public.pc_sources(source_id),
  source_record_uuid uuid REFERENCES public.pc_source_records(source_record_uuid),
  document_id uuid REFERENCES public.pc_documents(document_id),
  source_url text,
  source_locator text,
  excerpt text,
  observed_at timestamptz,
  captured_at timestamptz NOT NULL DEFAULT now(),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  CHECK (num_nonnulls(source_id,source_record_uuid,document_id,source_url) >= 1)
);

CREATE TABLE IF NOT EXISTS public.pc_research_hypotheses (
  research_hypothesis_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  research_project_id uuid NOT NULL REFERENCES public.pc_research_projects(research_project_id),
  hypothesis_text text NOT NULL,
  hypothesis_status text NOT NULL DEFAULT 'open'
    CHECK (hypothesis_status IN ('open','under_test','supported','weakened','rejected','closed')),
  alternative_to_id uuid REFERENCES public.pc_research_hypotheses(research_hypothesis_id),
  assumptions jsonb NOT NULL DEFAULT '[]'::jsonb,
  indicators jsonb NOT NULL DEFAULT '[]'::jsonb,
  assessment text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- Separate hypothetical research candidates from actual transactions.
CREATE TABLE IF NOT EXISTS public.pc_research_opportunities (
  research_opportunity_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  research_project_id uuid NOT NULL REFERENCES public.pc_research_projects(research_project_id),
  opportunity_type text NOT NULL,
  title text NOT NULL,
  sponsor_entity_id text REFERENCES public.pc_entities(entity_id),
  candidate_entity_id text REFERENCES public.pc_entities(entity_id),
  candidate_asset_id text,
  corridor_key text REFERENCES public.pc_trade_corridors(corridor_key),
  evidence_level text NOT NULL DEFAULT 'hypothesis'
    CHECK (evidence_level IN ('hypothesis','reported_interest','documented_process','official_announcement')),
  research_status text NOT NULL DEFAULT 'open'
    CHECK (research_status IN ('open','investigating','monitoring','closed')),
  rationale text,
  constraints jsonb NOT NULL DEFAULT '[]'::jsonb,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (sponsor_entity_id IS DISTINCT FROM candidate_entity_id)
);

-- 2) CORRIDOR ROUTE VARIANTS AND OPERATIONAL EXPOSURE
CREATE TABLE IF NOT EXISTS public.pc_corridor_variants (
  corridor_variant_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  corridor_key text NOT NULL REFERENCES public.pc_trade_corridors(corridor_key),
  variant_name text NOT NULL,
  variant_type text NOT NULL
    CHECK (variant_type IN ('primary','alternative','seasonal','contingency','proposed')),
  modes text[] NOT NULL DEFAULT '{}'::text[],
  route_segments jsonb NOT NULL DEFAULT '[]'::jsonb,
  availability_status text NOT NULL DEFAULT 'unknown',
  capacity_value numeric,
  capacity_unit text,
  transit_time_hours numeric,
  cost_basis text,
  effective_from date,
  effective_to date,
  source_id text REFERENCES public.pc_sources(source_id),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (corridor_key, variant_name),
  CHECK (transit_time_hours IS NULL OR transit_time_hours >= 0),
  CHECK (capacity_value IS NULL OR capacity_value >= 0)
);

CREATE TABLE IF NOT EXISTS public.pc_corridor_exposures (
  corridor_exposure_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  corridor_key text NOT NULL REFERENCES public.pc_trade_corridors(corridor_key),
  corridor_variant_id uuid REFERENCES public.pc_corridor_variants(corridor_variant_id),
  affected_segment_key text REFERENCES public.pc_corridor_segments(segment_key),
  event_id text REFERENCES public.pc_events(event_id),
  subject_type text,
  subject_id text,
  exposure_type text NOT NULL,
  impact_status text NOT NULL DEFAULT 'potential'
    CHECK (impact_status IN ('potential','forecast','observed','confirmed','resolved','refuted')),
  impact_description text,
  delay_hours numeric,
  capacity_reduction_pct numeric,
  observation_at timestamptz,
  source_id text REFERENCES public.pc_sources(source_id),
  research_claim_id uuid REFERENCES public.pc_research_claims(research_claim_id),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (delay_hours IS NULL OR delay_hours >= 0),
  CHECK (capacity_reduction_pct IS NULL OR capacity_reduction_pct BETWEEN 0 AND 100),
  CHECK (event_id IS NOT NULL OR subject_id IS NOT NULL OR research_claim_id IS NOT NULL)
);

-- 3) SHARED MONITORING: audience-specific rules, shared underlying records
CREATE TABLE IF NOT EXISTS public.pc_monitoring_profiles (
  monitoring_profile_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_name text NOT NULL,
  profile_domain text NOT NULL,
  audience_codes text[] NOT NULL DEFAULT '{}'::text[],
  scope jsonb NOT NULL DEFAULT '{}'::jsonb,
  active boolean NOT NULL DEFAULT true,
  owner_label text,
  research_project_id uuid REFERENCES public.pc_research_projects(research_project_id),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.pc_monitoring_rules (
  monitoring_rule_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  monitoring_profile_id uuid NOT NULL REFERENCES public.pc_monitoring_profiles(monitoring_profile_id),
  rule_name text NOT NULL,
  rule_type text NOT NULL,
  target_type text,
  target_id text,
  criteria jsonb NOT NULL DEFAULT '{}'::jsonb,
  threshold jsonb NOT NULL DEFAULT '{}'::jsonb,
  evaluation_interval_minutes integer CHECK (evaluation_interval_minutes IS NULL OR evaluation_interval_minutes >= 60),
  severity text NOT NULL DEFAULT 'informational',
  active boolean NOT NULL DEFAULT true,
  valid_from timestamptz,
  valid_to timestamptz,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from)
);

CREATE TABLE IF NOT EXISTS public.pc_monitoring_observations (
  monitoring_observation_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  monitoring_profile_id uuid NOT NULL REFERENCES public.pc_monitoring_profiles(monitoring_profile_id),
  monitoring_rule_id uuid REFERENCES public.pc_monitoring_rules(monitoring_rule_id),
  observed_at timestamptz NOT NULL,
  reported_at timestamptz,
  observation_type text NOT NULL,
  event_id text REFERENCES public.pc_events(event_id),
  corridor_key text REFERENCES public.pc_trade_corridors(corridor_key),
  target_type text,
  target_id text,
  source_id text REFERENCES public.pc_sources(source_id),
  source_record_uuid uuid REFERENCES public.pc_source_records(source_record_uuid),
  research_claim_id uuid REFERENCES public.pc_research_claims(research_claim_id),
  observation_data jsonb NOT NULL DEFAULT '{}'::jsonb,
  confidence numeric(4,3) CHECK (confidence BETWEEN 0 AND 1),
  review_status text NOT NULL DEFAULT 'pending'
    CHECK (review_status IN ('pending','reviewed','approved','rejected')),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.pc_monitoring_alerts (
  monitoring_alert_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  monitoring_profile_id uuid NOT NULL REFERENCES public.pc_monitoring_profiles(monitoring_profile_id),
  monitoring_rule_id uuid REFERENCES public.pc_monitoring_rules(monitoring_rule_id),
  monitoring_observation_id uuid REFERENCES public.pc_monitoring_observations(monitoring_observation_id),
  event_id text REFERENCES public.pc_events(event_id),
  headline text NOT NULL,
  alert_status text NOT NULL DEFAULT 'draft'
    CHECK (alert_status IN ('draft','pending_review','approved','sent','updated','closed','retracted')),
  severity text NOT NULL DEFAULT 'informational',
  audience_codes text[] NOT NULL DEFAULT '{}'::text[],
  assessment text,
  triggered_at timestamptz NOT NULL DEFAULT now(),
  reviewed_at timestamptz,
  sent_at timestamptz,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- 4) WEATHER: forecast issue time != forecast valid time != observed time
CREATE TABLE IF NOT EXISTS public.pc_weather_observations (
  weather_observation_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  provider text NOT NULL,
  provider_record_id text,
  weather_kind text NOT NULL CHECK (weather_kind IN ('forecast','warning','observation','historical_analysis')),
  hazard_type text NOT NULL,
  issued_at timestamptz,
  valid_from timestamptz,
  valid_to timestamptz,
  observed_at timestamptz,
  latitude double precision CHECK (latitude BETWEEN -90 AND 90),
  longitude double precision CHECK (longitude BETWEEN -180 AND 180),
  geographic_scope jsonb NOT NULL DEFAULT '{}'::jsonb,
  severity text,
  metrics jsonb NOT NULL DEFAULT '{}'::jsonb,
  corridor_key text REFERENCES public.pc_trade_corridors(corridor_key),
  event_id text REFERENCES public.pc_events(event_id),
  source_id text REFERENCES public.pc_sources(source_id),
  source_record_uuid uuid REFERENCES public.pc_source_records(source_record_uuid),
  source_url text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from),
  CHECK (weather_kind <> 'forecast' OR issued_at IS NOT NULL),
  CHECK (weather_kind <> 'observation' OR observed_at IS NOT NULL),
  UNIQUE (provider,provider_record_id,weather_kind,valid_from)
);

-- 5) EVENT CHRONOLOGY: occurrence/report/update/correction kept distinct
CREATE TABLE IF NOT EXISTS public.pc_event_updates (
  event_update_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id text NOT NULL REFERENCES public.pc_events(event_id),
  update_type text NOT NULL CHECK (update_type IN
    ('initial_report','development','correction','confirmation','impact_update','resolution','retraction')),
  occurred_at timestamptz,
  reported_at timestamptz,
  published_at timestamptz,
  source_id text REFERENCES public.pc_sources(source_id),
  source_record_uuid uuid REFERENCES public.pc_source_records(source_record_uuid),
  document_id uuid REFERENCES public.pc_documents(document_id),
  summary text NOT NULL,
  new_claims jsonb NOT NULL DEFAULT '[]'::jsonb,
  review_status text NOT NULL DEFAULT 'pending'
    CHECK (review_status IN ('pending','approved','rejected')),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- 6) SANCTIONS SCREENING: a candidate match is not a legal designation
CREATE TABLE IF NOT EXISTS public.pc_screening_cases (
  screening_case_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  case_reference text UNIQUE,
  subject_type text NOT NULL,
  subject_id text,
  submitted_name text NOT NULL,
  screening_purpose text NOT NULL,
  jurisdiction_codes text[] NOT NULL DEFAULT '{}'::text[],
  case_status text NOT NULL DEFAULT 'open'
    CHECK (case_status IN ('open','under_review','escalated','cleared','confirmed_match','closed')),
  opened_at timestamptz NOT NULL DEFAULT now(),
  closed_at timestamptz,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  CHECK (closed_at IS NULL OR closed_at >= opened_at)
);

CREATE TABLE IF NOT EXISTS public.pc_screening_matches (
  screening_match_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  screening_case_id uuid NOT NULL REFERENCES public.pc_screening_cases(screening_case_id),
  sanctions_designation_id uuid NOT NULL
    REFERENCES public.pc_sanctions_designations(sanctions_designation_id),
  match_status text NOT NULL DEFAULT 'candidate'
    CHECK (match_status IN ('candidate','needs_review','confirmed','false_positive','inconclusive')),
  match_score numeric(5,4) CHECK (match_score BETWEEN 0 AND 1),
  match_basis jsonb NOT NULL DEFAULT '{}'::jsonb,
  analyst_reason text,
  reviewed_by_label text,
  reviewed_at timestamptz,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (screening_case_id,sanctions_designation_id)
);

-- 7) SOURCE-BACKED MARKET/CORRIDOR ASSOCIATION: reuse market data already stored
CREATE TABLE IF NOT EXISTS public.pc_market_corridor_links (
  market_corridor_link_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  market_observation_id uuid NOT NULL
    REFERENCES public.pc_market_observations(market_observation_id),
  corridor_key text NOT NULL REFERENCES public.pc_trade_corridors(corridor_key),
  corridor_variant_id uuid REFERENCES public.pc_corridor_variants(corridor_variant_id),
  relevance_type text NOT NULL,
  source_id text REFERENCES public.pc_sources(source_id),
  research_claim_id uuid REFERENCES public.pc_research_claims(research_claim_id),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE (market_observation_id,corridor_key,relevance_type)
);

-- Read/query indexes. Avoid duplicate storage of the existing source, event,
-- sanctions, market, route and corridor base objects.
CREATE INDEX IF NOT EXISTS idx_pc13_research_question_project ON public.pc_research_questions(research_project_id,question_status);
CREATE INDEX IF NOT EXISTS idx_pc13_claim_subject ON public.pc_research_claims(subject_type,subject_id,verification_status);
CREATE INDEX IF NOT EXISTS idx_pc13_claim_project ON public.pc_research_claims(research_project_id,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_pc13_claim_evidence_claim ON public.pc_claim_evidence(research_claim_id,evidence_role);
CREATE INDEX IF NOT EXISTS idx_pc13_opportunities_sponsor ON public.pc_research_opportunities(sponsor_entity_id,research_status);
CREATE INDEX IF NOT EXISTS idx_pc13_opportunities_candidate ON public.pc_research_opportunities(candidate_entity_id);
CREATE INDEX IF NOT EXISTS idx_pc13_corridor_variants_corridor ON public.pc_corridor_variants(corridor_key,variant_type);
CREATE INDEX IF NOT EXISTS idx_pc13_corridor_exposure_event ON public.pc_corridor_exposures(event_id);
CREATE INDEX IF NOT EXISTS idx_pc13_corridor_exposure_key ON public.pc_corridor_exposures(corridor_key,impact_status);
CREATE INDEX IF NOT EXISTS idx_pc13_monitoring_rules_profile ON public.pc_monitoring_rules(monitoring_profile_id,active);
CREATE INDEX IF NOT EXISTS idx_pc13_monitoring_observation_time ON public.pc_monitoring_observations(monitoring_profile_id,observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_pc13_monitoring_observation_event ON public.pc_monitoring_observations(event_id);
CREATE INDEX IF NOT EXISTS idx_pc13_monitoring_alerts_status ON public.pc_monitoring_alerts(monitoring_profile_id,alert_status,triggered_at DESC);
CREATE INDEX IF NOT EXISTS idx_pc13_weather_time ON public.pc_weather_observations(hazard_type,valid_from DESC);
CREATE INDEX IF NOT EXISTS idx_pc13_weather_corridor ON public.pc_weather_observations(corridor_key,valid_from DESC);
CREATE INDEX IF NOT EXISTS idx_pc13_event_updates_event ON public.pc_event_updates(event_id,reported_at DESC);
CREATE INDEX IF NOT EXISTS idx_pc13_screening_cases_subject ON public.pc_screening_cases(subject_type,subject_id,case_status);
CREATE INDEX IF NOT EXISTS idx_pc13_screening_matches_designation ON public.pc_screening_matches(sanctions_designation_id,match_status);
CREATE INDEX IF NOT EXISTS idx_pc13_market_corridors ON public.pc_market_corridor_links(corridor_key,relevance_type);

-- Harden NEW tables only. Existing views, existing grants and existing RLS
-- policies are deliberately untouched. App user permissions come later.
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'pc_research_projects','pc_research_questions','pc_research_claims',
    'pc_claim_evidence','pc_research_hypotheses','pc_research_opportunities',
    'pc_corridor_variants','pc_corridor_exposures','pc_monitoring_profiles',
    'pc_monitoring_rules','pc_monitoring_observations','pc_monitoring_alerts',
    'pc_weather_observations','pc_event_updates','pc_screening_cases',
    'pc_screening_matches','pc_market_corridor_links'
  ] LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY',t);
    EXECUTE format('REVOKE ALL ON public.%I FROM PUBLIC',t);
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='anon') THEN
      EXECUTE format('REVOKE ALL ON public.%I FROM anon',t);
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN
      EXECUTE format('REVOKE ALL ON public.%I FROM authenticated',t);
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='service_role') THEN
      EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON public.%I TO service_role',t);
    END IF;
  END LOOP;
END $$;
COMMIT;

-- POST-MIGRATION CHECK (read-only; return 17 expected rows)
SELECT c.relname AS table_name,
       c.relrowsecurity AS rls_enabled,
       EXISTS (SELECT 1 FROM pg_attribute a WHERE a.attrelid=c.oid
                AND a.attname='metadata' AND a.attnum>0 AND NOT a.attisdropped) AS has_metadata
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='public' AND c.relname IN (
  'pc_research_projects','pc_research_questions','pc_research_claims',
  'pc_claim_evidence','pc_research_hypotheses','pc_research_opportunities',
  'pc_corridor_variants','pc_corridor_exposures','pc_monitoring_profiles',
  'pc_monitoring_rules','pc_monitoring_observations','pc_monitoring_alerts',
  'pc_weather_observations','pc_event_updates','pc_screening_cases',
  'pc_screening_matches','pc_market_corridor_links'
) AND c.relkind='r' ORDER BY c.relname;
