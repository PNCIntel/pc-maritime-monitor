-- POWER & CORRIDORS | PHASE 13B | CORPORATE INTELLIGENCE
-- Run AFTER Phase 13A, once its post-migration check returns 17 rows.
-- Extends public only. No existing row updates, view replacements, RLS-policy edits,
-- canonical mergers, inferred ownership stakes, or fictitious seed data.
-- Execute as the database migration owner (e.g. Supabase SQL Editor).
BEGIN;

DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'pc_entities','pc_company_profiles','pc_company_operating_footprint',
    'pc_assets','pc_mobile_assets','pc_events','pc_trade_corridors',
    'pc_transport_services','pc_transactions','pc_sources','pc_documents',
    'pc_research_claims','pc_research_projects'
  ] LOOP
    IF to_regclass(format('public.%I',t)) IS NULL THEN
      RAISE EXCEPTION 'Missing required public.%; run/verify Phase 13A first',t;
    END IF;
  END LOOP;
END $$;

-- 1. Locations: company headquarters, branches, agency offices, warehouses,
--    representative sites etc. A location owned by an agent is NOT a company office.
CREATE TABLE IF NOT EXISTS public.pc_company_offices (
  company_office_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  entity_id text NOT NULL REFERENCES public.pc_entities(entity_id),
  office_name text,
  office_type text NOT NULL CHECK (office_type IN
    ('registered','headquarters','regional','branch','representative','agency','commercial','operations','depot','other')),
  address_lines text,
  city text,
  region text,
  country text,
  postal_code text,
  latitude double precision CHECK (latitude BETWEEN -90 AND 90),
  longitude double precision CHECK (longitude BETWEEN -180 AND 180),
  phone_public text,
  email_public text,
  website_url text,
  site_asset_id text REFERENCES public.pc_assets(asset_id),
  related_agent_entity_id text REFERENCES public.pc_entities(entity_id),
  office_status text NOT NULL DEFAULT 'reported'
    CHECK (office_status IN ('reported','active','inactive','closed','planned','unverified')),
  valid_from date,
  valid_to date,
  as_of date,
  source_id text REFERENCES public.pc_sources(source_id),
  source_url text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from)
);
CREATE INDEX IF NOT EXISTS idx_pc13b_office_entity ON public.pc_company_offices(entity_id,office_status,country);
CREATE INDEX IF NOT EXISTS idx_pc13b_office_agent ON public.pc_company_offices(related_agent_entity_id);

-- 2. Public leadership identities. Do not store personal secrets or private contact data.
CREATE TABLE IF NOT EXISTS public.pc_people (
  person_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  display_name text NOT NULL,
  normalized_name text,
  public_bio text,
  source_id text REFERENCES public.pc_sources(source_id),
  source_url text,
  identity_status text NOT NULL DEFAULT 'provisional'
    CHECK (identity_status IN ('provisional','verified','ambiguous','superseded')),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_pc13b_people_name ON public.pc_people(lower(display_name));

-- 3. Historical appointments, not a mutable CEO string on the company row.
CREATE TABLE IF NOT EXISTS public.pc_company_people_roles (
  company_people_role_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  entity_id text NOT NULL REFERENCES public.pc_entities(entity_id),
  person_id uuid NOT NULL REFERENCES public.pc_people(person_id),
  office_id uuid REFERENCES public.pc_company_offices(company_office_id),
  position_title text NOT NULL,
  role_family text NOT NULL DEFAULT 'executive'
    CHECK (role_family IN ('executive','board','management','founder','adviser','other')),
  appointment_type text,
  appointment_status text NOT NULL DEFAULT 'reported'
    CHECK (appointment_status IN ('reported','current','former','announced','unverified')),
  valid_from date,
  valid_to date,
  as_of date,
  source_id text REFERENCES public.pc_sources(source_id),
  source_url text,
  document_id uuid REFERENCES public.pc_documents(document_id),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from)
);
CREATE INDEX IF NOT EXISTS idx_pc13b_roles_company ON public.pc_company_people_roles(entity_id,appointment_status,valid_from DESC);
CREATE INDEX IF NOT EXISTS idx_pc13b_roles_person ON public.pc_company_people_roles(person_id,valid_from DESC);

-- 4. Time-bound direct/indirect investment positions, distinct from operating control
--    and from planned transactions. Percentage is NULL unless verified. A proposed
--    post-settlement percentage is NOT current ownership.
CREATE TABLE IF NOT EXISTS public.pc_company_portfolio_positions (
  portfolio_position_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  holder_entity_id text NOT NULL REFERENCES public.pc_entities(entity_id),
  investee_entity_id text REFERENCES public.pc_entities(entity_id),
  investee_asset_id text REFERENCES public.pc_assets(asset_id),
  investment_vehicle_entity_id text REFERENCES public.pc_entities(entity_id),
  position_type text NOT NULL CHECK (position_type IN
    ('direct_equity','indirect_equity','fund_interest','joint_venture','investment_management',
     'economic_interest','concession','other')),
  ownership_percent numeric(8,5) CHECK (ownership_percent BETWEEN 0 AND 100),
  percentage_qualifier text CHECK (percentage_qualifier IN ('exact','approximately','over','at_least','up_to')),
  position_status text NOT NULL DEFAULT 'reported'
    CHECK (position_status IN ('reported','held','pending','disposed','historical','disputed')),
  valid_from date,
  valid_to date,
  as_of date,
  linked_transaction_id text REFERENCES public.pc_transactions(transaction_id),
  source_id text REFERENCES public.pc_sources(source_id),
  research_claim_id uuid REFERENCES public.pc_research_claims(research_claim_id),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (num_nonnulls(investee_entity_id,investee_asset_id) = 1),
  CHECK (holder_entity_id IS DISTINCT FROM investee_entity_id),
  CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from)
);
CREATE INDEX IF NOT EXISTS idx_pc13b_portfolio_holder ON public.pc_company_portfolio_positions(holder_entity_id,position_status,valid_from DESC);
CREATE INDEX IF NOT EXISTS idx_pc13b_portfolio_investee ON public.pc_company_portfolio_positions(investee_entity_id,position_status);
CREATE INDEX IF NOT EXISTS idx_pc13b_portfolio_asset ON public.pc_company_portfolio_positions(investee_asset_id);

-- 5. Historical operating relationships to fleets and physical assets. A charter
--    does not imply ownership; source backed where feasible.
CREATE TABLE IF NOT EXISTS public.pc_company_asset_roles (
  company_asset_role_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  entity_id text NOT NULL REFERENCES public.pc_entities(entity_id),
  asset_id text REFERENCES public.pc_assets(asset_id),
  mobile_asset_id text REFERENCES public.pc_mobile_assets(mobile_asset_id),
  asset_role text NOT NULL CHECK (asset_role IN
    ('legal_owner','beneficial_owner','operator','manager','charterer',
     'lessee','concessionaire','builder','service_provider','other')),
  role_status text NOT NULL DEFAULT 'reported'
    CHECK (role_status IN ('reported','active','former','announced','unverified')),
  valid_from date,
  valid_to date,
  as_of date,
  source_id text REFERENCES public.pc_sources(source_id),
  research_claim_id uuid REFERENCES public.pc_research_claims(research_claim_id),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (num_nonnulls(asset_id,mobile_asset_id) = 1),
  CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from)
);
CREATE INDEX IF NOT EXISTS idx_pc13b_assetroles_company ON public.pc_company_asset_roles(entity_id,asset_role,role_status);
CREATE INDEX IF NOT EXISTS idx_pc13b_assetroles_mobile ON public.pc_company_asset_roles(mobile_asset_id,valid_from DESC);
CREATE INDEX IF NOT EXISTS idx_pc13b_assetroles_fixed ON public.pc_company_asset_roles(asset_id,valid_from DESC);

-- 6. Company milestones connect chronology to source evidence and existing events.
CREATE TABLE IF NOT EXISTS public.pc_company_milestones (
  company_milestone_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  entity_id text NOT NULL REFERENCES public.pc_entities(entity_id),
  milestone_type text NOT NULL CHECK (milestone_type IN
    ('founded','predecessor_founded','rebranded','leadership_change','office_opened',
     'market_entry','market_exit','service_launched','fleet_addition','fleet_disposal',
     'acquisition','disposal','capital_raise','project_started','project_completed',
     'financial_result','restructuring','other')),
  title text NOT NULL,
  summary text,
  milestone_date date,
  date_precision text NOT NULL DEFAULT 'day'
    CHECK (date_precision IN ('day','month','year','approximate','unknown')),
  reported_at timestamptz,
  event_id text REFERENCES public.pc_events(event_id),
  transaction_id text REFERENCES public.pc_transactions(transaction_id),
  related_entity_id text REFERENCES public.pc_entities(entity_id),
  related_asset_id text REFERENCES public.pc_assets(asset_id),
  milestone_status text NOT NULL DEFAULT 'reported'
    CHECK (milestone_status IN ('reported','confirmed','disputed','corrected','superseded')),
  source_id text REFERENCES public.pc_sources(source_id),
  research_claim_id uuid REFERENCES public.pc_research_claims(research_claim_id),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_pc13b_milestone_entity_date ON public.pc_company_milestones(entity_id,milestone_date DESC);
CREATE INDEX IF NOT EXISTS idx_pc13b_milestone_event ON public.pc_company_milestones(event_id);

-- 7. Company-to-corridor link, separating participation from conjectured exposure.
CREATE TABLE IF NOT EXISTS public.pc_company_corridor_roles (
  company_corridor_role_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  entity_id text NOT NULL REFERENCES public.pc_entities(entity_id),
  corridor_key text NOT NULL REFERENCES public.pc_trade_corridors(corridor_key),
  transport_service_id text REFERENCES public.pc_transport_services(transport_service_id),
  corridor_role text NOT NULL CHECK (corridor_role IN
    ('operator','infrastructure_owner','concessionaire','investor','carrier',
     'trader','shipper','offtaker','logistics_provider','customer','other')),
  role_status text NOT NULL DEFAULT 'reported'
    CHECK (role_status IN ('reported','active','former','proposed','disputed')),
  valid_from date,
  valid_to date,
  as_of date,
  source_id text REFERENCES public.pc_sources(source_id),
  research_claim_id uuid REFERENCES public.pc_research_claims(research_claim_id),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from)
);
CREATE INDEX IF NOT EXISTS idx_pc13b_company_corridor ON public.pc_company_corridor_roles(entity_id,corridor_key,role_status);
CREATE INDEX IF NOT EXISTS idx_pc13b_corridor_companies ON public.pc_company_corridor_roles(corridor_key,corridor_role);

-- 8. Analyst-reviewed effect assertions; no automatic inference that events CAUSED growth.
CREATE TABLE IF NOT EXISTS public.pc_company_event_effects (
  company_event_effect_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  entity_id text NOT NULL REFERENCES public.pc_entities(entity_id),
  event_id text NOT NULL REFERENCES public.pc_events(event_id),
  corridor_key text REFERENCES public.pc_trade_corridors(corridor_key),
  effect_type text NOT NULL CHECK (effect_type IN
    ('operational_disruption','commercial_impact','security_exposure','regulatory_exposure',
     'route_change','investment_response','growth_context','research_context','other')),
  causal_status text NOT NULL DEFAULT 'temporal_association'
    CHECK (causal_status IN ('temporal_association','reported_link','evidenced_link','hypothesis','refuted')),
  observed_effect text,
  start_at timestamptz,
  end_at timestamptz,
  source_id text REFERENCES public.pc_sources(source_id),
  research_claim_id uuid REFERENCES public.pc_research_claims(research_claim_id),
  verification_status text NOT NULL DEFAULT 'pending'
    CHECK (verification_status IN ('pending','verified','contested','refuted')),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (end_at IS NULL OR start_at IS NULL OR end_at >= start_at)
);
CREATE INDEX IF NOT EXISTS idx_pc13b_company_event ON public.pc_company_event_effects(entity_id,event_id);
CREATE INDEX IF NOT EXISTS idx_pc13b_event_company ON public.pc_company_event_effects(event_id,effect_type);

-- 9. Explicit legacy-ID redirects and ambiguity decisions. NO automatic migrations.
--    Staged loader must consult only approval_status='approved' AND match_status='same_entity'.
CREATE TABLE IF NOT EXISTS public.pc_canonical_identity_decisions (
  identity_decision_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_entity_id text NOT NULL REFERENCES public.pc_entities(entity_id),
  canonical_entity_id text REFERENCES public.pc_entities(entity_id),
  match_status text NOT NULL CHECK (match_status IN
    ('same_entity','related_distinct','ambiguous','rejected')),
  approval_status text NOT NULL DEFAULT 'pending'
    CHECK (approval_status IN ('pending','approved','rejected','superseded')),
  decision_reason text,
  reviewed_by_label text,
  reviewed_at timestamptz,
  source_id text REFERENCES public.pc_sources(source_id),
  research_claim_id uuid REFERENCES public.pc_research_claims(research_claim_id),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (canonical_entity_id IS NULL OR canonical_entity_id <> source_entity_id),
  CHECK (approval_status <> 'approved' OR reviewed_at IS NOT NULL),
  CHECK (match_status <> 'same_entity' OR canonical_entity_id IS NOT NULL),
  CHECK (match_status <> 'ambiguous' OR canonical_entity_id IS NULL)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_pc13b_approved_redirect
 ON public.pc_canonical_identity_decisions(source_entity_id)
 WHERE match_status='same_entity' AND approval_status='approved';
CREATE INDEX IF NOT EXISTS idx_pc13b_identity_target ON public.pc_canonical_identity_decisions(canonical_entity_id,approval_status);

-- Scope permissions on NEW tables only; do not modify existing RLS/views.
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'pc_company_offices','pc_people','pc_company_people_roles',
    'pc_company_portfolio_positions','pc_company_asset_roles',
    'pc_company_milestones','pc_company_corridor_roles',
    'pc_company_event_effects','pc_canonical_identity_decisions'
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
      EXECUTE format('GRANT SELECT,INSERT,UPDATE,DELETE ON public.%I TO service_role',t);
    END IF;
  END LOOP;
END $$;
COMMIT;

-- Verify structural installation: expect 9 rows; no fabricated company data inserted.
SELECT c.relname AS table_name,c.relrowsecurity AS rls_enabled
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='public' AND c.relkind='r' AND c.relname IN (
 'pc_company_offices','pc_people','pc_company_people_roles',
 'pc_company_portfolio_positions','pc_company_asset_roles',
 'pc_company_milestones','pc_company_corridor_roles',
 'pc_company_event_effects','pc_canonical_identity_decisions')
ORDER BY c.relname;
