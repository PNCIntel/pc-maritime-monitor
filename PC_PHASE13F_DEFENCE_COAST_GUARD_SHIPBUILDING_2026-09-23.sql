-- POWER & CORRIDORS | PHASE 13F | DEFENCE, COAST GUARD & SHIPBUILDING
-- Run in order AFTER 13A and 13B. Public schema only.
-- Additive structural tables; does not backfill data or modify existing views/RLS.
-- All facts require explicit source provenance; no speculative seed entities.
BEGIN;
DO $$ DECLARE t text; BEGIN
  FOREACH t IN ARRAY ARRAY['pc_entities','pc_assets','pc_mobile_assets','pc_sources','pc_events','pc_trade_corridors','pc_research_claims','pc_shipbuilding_orders','pc_shipbuilding_order_units','pc_contracts'] LOOP
    IF to_regclass(format('public.%I',t)) IS NULL THEN RAISE EXCEPTION 'Missing prerequisite table %',t; END IF;
  END LOOP;
END $$;

CREATE TABLE public.pc_defence_organisations (
  entity_id text PRIMARY KEY REFERENCES public.pc_entities(entity_id),
  organisation_type text NOT NULL CHECK (organisation_type IN ('navy','coast_guard','air_force','army','joint_command','border_force','police','government','multinational','security_provider','defence_industry','other')),
  parent_entity_id text REFERENCES public.pc_entities(entity_id),
  jurisdiction text, public_mandate text, establishment_date date,
  organisation_status text DEFAULT 'reported',  source_id text REFERENCES public.pc_sources(source_id),
  research_claim_id uuid REFERENCES public.pc_research_claims(research_claim_id),
  verification_status text NOT NULL DEFAULT 'reported' CHECK (verification_status IN ('reported','verified','contested','refuted','hypothesis')),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_defence_organisations_1 ON public.pc_defence_organisations(organisation_type,jurisdiction);

CREATE TABLE public.pc_defence_programmes (
  defence_programme_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  programme_name text NOT NULL,
  customer_entity_id text REFERENCES public.pc_entities(entity_id),
  lead_contractor_entity_id text REFERENCES public.pc_entities(entity_id),
  shipbuilding_order_id text REFERENCES public.pc_shipbuilding_orders(shipbuilding_order_id),
  contract_id text REFERENCES public.pc_contracts(contract_id),
  programme_type text NOT NULL CHECK (programme_type IN ('naval_shipbuilding','coast_guard','aviation','unmanned','land','sensors','infrastructure','maintenance','other')),
  programme_status text DEFAULT 'reported', announced_date date,
  firm_quantity integer CHECK (firm_quantity>=0), option_quantity integer CHECK (option_quantity>=0),
  announced_value numeric, currency text, expected_completion_date date,  source_id text REFERENCES public.pc_sources(source_id),
  research_claim_id uuid REFERENCES public.pc_research_claims(research_claim_id),
  verification_status text NOT NULL DEFAULT 'reported' CHECK (verification_status IN ('reported','verified','contested','refuted','hypothesis')),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_defence_programmes_1 ON public.pc_defence_programmes(customer_entity_id,programme_status);
CREATE INDEX idx_defence_programmes_2 ON public.pc_defence_programmes(shipbuilding_order_id);

CREATE TABLE public.pc_defence_programme_participants (
  programme_participant_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  defence_programme_id uuid NOT NULL REFERENCES public.pc_defence_programmes(defence_programme_id),
  entity_id text NOT NULL REFERENCES public.pc_entities(entity_id),
  shipyard_asset_id text REFERENCES public.pc_assets(asset_id),
  participant_role text NOT NULL CHECK (participant_role IN ('customer','prime','subcontractor','designer','builder','fabricator','integrator','supplier','maintenance','financier','other')),
  valid_from date, valid_to date, participation_status text DEFAULT 'reported',  source_id text REFERENCES public.pc_sources(source_id),
  research_claim_id uuid REFERENCES public.pc_research_claims(research_claim_id),
  verification_status text NOT NULL DEFAULT 'reported' CHECK (verification_status IN ('reported','verified','contested','refuted','hypothesis')),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to>=valid_from)
);
CREATE INDEX idx_defence_programme_participants_1 ON public.pc_defence_programme_participants(defence_programme_id,participant_role);
CREATE INDEX idx_defence_programme_participants_2 ON public.pc_defence_programme_participants(entity_id);

CREATE TABLE public.pc_shipbuilding_production_tasks (
  production_task_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  shipbuilding_order_id text REFERENCES public.pc_shipbuilding_orders(shipbuilding_order_id),
  shipbuilding_order_unit_id text REFERENCES public.pc_shipbuilding_order_units(shipbuilding_order_unit_id),
  defence_programme_id uuid REFERENCES public.pc_defence_programmes(defence_programme_id),
  shipyard_asset_id text NOT NULL REFERENCES public.pc_assets(asset_id),
  builder_entity_id text REFERENCES public.pc_entities(entity_id),
  task_type text NOT NULL CHECK (task_type IN ('design','steel_cut','block_fabrication','hull','superstructure','outfitting','propulsion','integration','sea_trials','maintenance','refit','other')),
  task_status text DEFAULT 'reported', planned_start date, actual_start date,
  planned_finish date, actual_finish date, workshare_percent numeric CHECK (workshare_percent BETWEEN 0 AND 100),  source_id text REFERENCES public.pc_sources(source_id),
  research_claim_id uuid REFERENCES public.pc_research_claims(research_claim_id),
  verification_status text NOT NULL DEFAULT 'reported' CHECK (verification_status IN ('reported','verified','contested','refuted','hypothesis')),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (num_nonnulls(shipbuilding_order_id,shipbuilding_order_unit_id,defence_programme_id)>=1)
);
CREATE INDEX idx_shipbuilding_production_tasks_1 ON public.pc_shipbuilding_production_tasks(shipyard_asset_id,task_type);
CREATE INDEX idx_shipbuilding_production_tasks_2 ON public.pc_shipbuilding_production_tasks(shipbuilding_order_unit_id);

CREATE TABLE public.pc_defence_programme_milestones (
  defence_milestone_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  defence_programme_id uuid NOT NULL REFERENCES public.pc_defence_programmes(defence_programme_id),
  shipbuilding_order_unit_id text REFERENCES public.pc_shipbuilding_order_units(shipbuilding_order_unit_id),
  event_id text REFERENCES public.pc_events(event_id),
  milestone_type text NOT NULL, planned_date date, actual_date date,
  milestone_status text DEFAULT 'reported', date_precision text DEFAULT 'day',
  public_description text,  source_id text REFERENCES public.pc_sources(source_id),
  research_claim_id uuid REFERENCES public.pc_research_claims(research_claim_id),
  verification_status text NOT NULL DEFAULT 'reported' CHECK (verification_status IN ('reported','verified','contested','refuted','hypothesis')),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_defence_programme_milestones_1 ON public.pc_defence_programme_milestones(defence_programme_id,planned_date);
CREATE INDEX idx_defence_programme_milestones_2 ON public.pc_defence_programme_milestones(shipbuilding_order_unit_id);

CREATE TABLE public.pc_shipyard_capacity_history (
  shipyard_capacity_history_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  shipyard_asset_id text NOT NULL REFERENCES public.pc_assets(asset_id),
  operator_entity_id text REFERENCES public.pc_entities(entity_id),
  observed_date date NOT NULL, metric_name text NOT NULL,
  metric_value numeric, metric_unit text, capacity_basis text,
  reported_backlog_quantity integer, planned_or_actual text DEFAULT 'reported',  source_id text REFERENCES public.pc_sources(source_id),
  research_claim_id uuid REFERENCES public.pc_research_claims(research_claim_id),
  verification_status text NOT NULL DEFAULT 'reported' CHECK (verification_status IN ('reported','verified','contested','refuted','hypothesis')),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_shipyard_capacity_history_1 ON public.pc_shipyard_capacity_history(shipyard_asset_id,observed_date DESC);

CREATE TABLE public.pc_security_operations (
  security_operation_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  operation_name text NOT NULL, lead_entity_id text REFERENCES public.pc_entities(entity_id),
  operating_area jsonb NOT NULL DEFAULT '{}'::jsonb,
  operation_type text NOT NULL CHECK (operation_type IN ('naval_patrol','coast_guard_patrol','counter_piracy','search_and_rescue','interdiction','escort','border_security','infrastructure_security','exercise','other')),
  publicly_reported_start date, publicly_reported_end date, operation_status text DEFAULT 'reported',  source_id text REFERENCES public.pc_sources(source_id),
  research_claim_id uuid REFERENCES public.pc_research_claims(research_claim_id),
  verification_status text NOT NULL DEFAULT 'reported' CHECK (verification_status IN ('reported','verified','contested','refuted','hypothesis')),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_security_operations_1 ON public.pc_security_operations(lead_entity_id,operation_type);

CREATE TABLE public.pc_security_operation_participants (
  security_operation_participant_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  security_operation_id uuid NOT NULL REFERENCES public.pc_security_operations(security_operation_id),
  entity_id text REFERENCES public.pc_entities(entity_id),
  mobile_asset_id text REFERENCES public.pc_mobile_assets(mobile_asset_id),
  participant_role text NOT NULL, valid_from date, valid_to date,  source_id text REFERENCES public.pc_sources(source_id),
  research_claim_id uuid REFERENCES public.pc_research_claims(research_claim_id),
  verification_status text NOT NULL DEFAULT 'reported' CHECK (verification_status IN ('reported','verified','contested','refuted','hypothesis')),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (num_nonnulls(entity_id,mobile_asset_id)>=1 AND (valid_to IS NULL OR valid_from IS NULL OR valid_to>=valid_from))
);
CREATE INDEX idx_security_operation_participants_1 ON public.pc_security_operation_participants(security_operation_id,participant_role);

CREATE TABLE public.pc_security_attribution_claims (
  attribution_claim_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id text NOT NULL REFERENCES public.pc_events(event_id),
  claimed_actor_entity_id text REFERENCES public.pc_entities(entity_id),
  claimed_actor_label text, attribution_kind text NOT NULL CHECK (attribution_kind IN ('official_allegation','claimed_responsibility','independent_assessment','witness','unverified','correction')),
  reported_at timestamptz, claim_summary text NOT NULL,
  verification_state text NOT NULL DEFAULT 'reported' CHECK (verification_state IN ('reported','corroborated','disputed','refuted','withdrawn')),  source_id text REFERENCES public.pc_sources(source_id),
  research_claim_id uuid REFERENCES public.pc_research_claims(research_claim_id),
  verification_status text NOT NULL DEFAULT 'reported' CHECK (verification_status IN ('reported','verified','contested','refuted','hypothesis')),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (num_nonnulls(claimed_actor_entity_id,claimed_actor_label)>=1)
);
CREATE INDEX idx_security_attribution_claims_1 ON public.pc_security_attribution_claims(event_id,reported_at DESC);

-- Restrict NEW tables to service_role pending specialist-app policies.
DO $$ DECLARE t text; BEGIN
  FOREACH t IN ARRAY ARRAY['pc_defence_organisations','pc_defence_programmes','pc_defence_programme_participants','pc_shipbuilding_production_tasks','pc_defence_programme_milestones','pc_shipyard_capacity_history','pc_security_operations','pc_security_operation_participants','pc_security_attribution_claims'] LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY',t);
    EXECUTE format('REVOKE ALL ON public.%I FROM PUBLIC',t);
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='anon') THEN EXECUTE format('REVOKE ALL ON public.%I FROM anon',t); END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN EXECUTE format('REVOKE ALL ON public.%I FROM authenticated',t); END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='service_role') THEN EXECUTE format('GRANT SELECT,INSERT,UPDATE,DELETE ON public.%I TO service_role',t); END IF;
  END LOOP;
END $$;
COMMIT;

-- Verification: expected 9 tables, each rls_enabled=true.
SELECT c.relname AS table_name,c.relrowsecurity AS rls_enabled FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind='r' AND c.relname IN ('pc_defence_organisations','pc_defence_programmes','pc_defence_programme_participants','pc_shipbuilding_production_tasks','pc_defence_programme_milestones','pc_shipyard_capacity_history','pc_security_operations','pc_security_operation_participants','pc_security_attribution_claims') ORDER BY c.relname;
