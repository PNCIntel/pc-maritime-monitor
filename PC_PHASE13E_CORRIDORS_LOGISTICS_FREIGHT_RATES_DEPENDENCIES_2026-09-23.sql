-- POWER & CORRIDORS | PHASE 13E | CORRIDORS, LOGISTICS, FREIGHT RATES & DEPENDENCIES
-- Run in order AFTER 13A and 13B. Public schema only.
-- Additive structural tables; does not backfill data or modify existing views/RLS.
-- All facts require explicit source provenance; no speculative seed entities.
BEGIN;
DO $$ DECLARE t text; BEGIN
  FOREACH t IN ARRAY ARRAY['pc_entities','pc_assets','pc_mobile_assets','pc_sources','pc_events','pc_trade_corridors','pc_research_claims','pc_transport_services','pc_contracts','pc_market_observations','pc_rail_links','pc_road_corridors'] LOOP
    IF to_regclass(format('public.%I',t)) IS NULL THEN RAISE EXCEPTION 'Missing prerequisite table %',t; END IF;
  END LOOP;
END $$;

CREATE TABLE public.pc_logistics_shipments (
  logistics_shipment_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  shipment_reference text, shipment_type text NOT NULL DEFAULT 'modelled' CHECK (shipment_type IN ('actual','aggregate','modelled','historical')),
  commodity_code text, cargo_description text, quantity numeric CHECK (quantity>=0),
  quantity_unit text, origin_asset_id text REFERENCES public.pc_assets(asset_id),
  destination_asset_id text REFERENCES public.pc_assets(asset_id),
  shipper_entity_id text REFERENCES public.pc_entities(entity_id),
  consignee_entity_id text REFERENCES public.pc_entities(entity_id),
  corridor_key text REFERENCES public.pc_trade_corridors(corridor_key),
  departure_at timestamptz, expected_arrival_at timestamptz, actual_arrival_at timestamptz,
  shipment_status text NOT NULL DEFAULT 'reported', confidentiality_class text NOT NULL DEFAULT 'public',  source_id text REFERENCES public.pc_sources(source_id),
  research_claim_id uuid REFERENCES public.pc_research_claims(research_claim_id),
  verification_status text NOT NULL DEFAULT 'reported' CHECK (verification_status IN ('reported','verified','contested','refuted','hypothesis')),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_logistics_shipments_1 ON public.pc_logistics_shipments(corridor_key,departure_at DESC);
CREATE INDEX idx_logistics_shipments_2 ON public.pc_logistics_shipments(shipper_entity_id);

CREATE TABLE public.pc_logistics_shipment_legs (
  shipment_leg_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  logistics_shipment_id uuid NOT NULL REFERENCES public.pc_logistics_shipments(logistics_shipment_id),
  leg_no integer NOT NULL CHECK (leg_no>0),
  mode text NOT NULL CHECK (mode IN ('maritime','cruise','ferry','inland_waterway','rail','road','air','pipeline','intermodal','other')),
  transport_service_id text REFERENCES public.pc_transport_services(transport_service_id),
  operator_entity_id text REFERENCES public.pc_entities(entity_id),
  mobile_asset_id text REFERENCES public.pc_mobile_assets(mobile_asset_id),
  from_asset_id text REFERENCES public.pc_assets(asset_id),
  to_asset_id text REFERENCES public.pc_assets(asset_id),
  planned_start_at timestamptz, actual_start_at timestamptz,
  planned_end_at timestamptz, actual_end_at timestamptz,
  cost_amount numeric, cost_currency text,
  leg_status text DEFAULT 'planned',  source_id text REFERENCES public.pc_sources(source_id),
  research_claim_id uuid REFERENCES public.pc_research_claims(research_claim_id),
  verification_status text NOT NULL DEFAULT 'reported' CHECK (verification_status IN ('reported','verified','contested','refuted','hypothesis')),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (logistics_shipment_id,leg_no)
);
CREATE INDEX idx_logistics_shipment_legs_1 ON public.pc_logistics_shipment_legs(transport_service_id);
CREATE INDEX idx_logistics_shipment_legs_2 ON public.pc_logistics_shipment_legs(operator_entity_id);

CREATE TABLE public.pc_logistics_service_agreements (
  logistics_service_agreement_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  contract_id text REFERENCES public.pc_contracts(contract_id),
  customer_entity_id text REFERENCES public.pc_entities(entity_id),
  provider_entity_id text REFERENCES public.pc_entities(entity_id),
  agent_entity_id text REFERENCES public.pc_entities(entity_id),
  corridor_key text REFERENCES public.pc_trade_corridors(corridor_key),
  transport_service_id text REFERENCES public.pc_transport_services(transport_service_id),
  service_type text NOT NULL, commodity text,
  minimum_volume numeric, volume_unit text,
  announced_at timestamptz, valid_from date, valid_to date,
  agreement_status text DEFAULT 'reported',  source_id text REFERENCES public.pc_sources(source_id),
  research_claim_id uuid REFERENCES public.pc_research_claims(research_claim_id),
  verification_status text NOT NULL DEFAULT 'reported' CHECK (verification_status IN ('reported','verified','contested','refuted','hypothesis')),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to>=valid_from)
);
CREATE INDEX idx_logistics_service_agreements_1 ON public.pc_logistics_service_agreements(provider_entity_id,customer_entity_id);
CREATE INDEX idx_logistics_service_agreements_2 ON public.pc_logistics_service_agreements(corridor_key);

CREATE TABLE public.pc_corridor_mode_connections (
  corridor_mode_connection_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  corridor_key text NOT NULL REFERENCES public.pc_trade_corridors(corridor_key),
  from_asset_id text NOT NULL REFERENCES public.pc_assets(asset_id),
  to_asset_id text NOT NULL REFERENCES public.pc_assets(asset_id),
  mode text NOT NULL CHECK (mode IN ('maritime','cruise','ferry','inland_waterway','rail','road','air','pipeline','intermodal','other')),
  rail_link_id text REFERENCES public.pc_rail_links(rail_link_id),
  road_corridor_id text REFERENCES public.pc_road_corridors(road_corridor_id),
  transport_service_id text REFERENCES public.pc_transport_services(transport_service_id),
  transfer_capacity numeric, transfer_unit text,
  transfer_time_hours numeric,
  status text DEFAULT 'reported', valid_from date, valid_to date,  source_id text REFERENCES public.pc_sources(source_id),
  research_claim_id uuid REFERENCES public.pc_research_claims(research_claim_id),
  verification_status text NOT NULL DEFAULT 'reported' CHECK (verification_status IN ('reported','verified','contested','refuted','hypothesis')),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to>=valid_from)
);
CREATE INDEX idx_corridor_mode_connections_1 ON public.pc_corridor_mode_connections(corridor_key,mode);
CREATE INDEX idx_corridor_mode_connections_2 ON public.pc_corridor_mode_connections(from_asset_id,to_asset_id);

CREATE TABLE public.pc_freight_rate_assessments (
  freight_rate_assessment_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  market_observation_id uuid REFERENCES public.pc_market_observations(market_observation_id),
  corridor_key text REFERENCES public.pc_trade_corridors(corridor_key),
  transport_service_id text REFERENCES public.pc_transport_services(transport_service_id),
  mode text NOT NULL CHECK (mode IN ('maritime','rail','road','air','inland_waterway','pipeline','other')),
  origin_asset_id text REFERENCES public.pc_assets(asset_id),
  destination_asset_id text REFERENCES public.pc_assets(asset_id),
  rate_category text NOT NULL, vessel_class text,
  observed_date date NOT NULL, rate_value numeric, rate_currency text, rate_unit text,
  assessment_kind text NOT NULL CHECK (assessment_kind IN ('index','assessment','fixture','quote','contract','model','other')),
  publication_at timestamptz, licence_scope text,  source_id text REFERENCES public.pc_sources(source_id),
  research_claim_id uuid REFERENCES public.pc_research_claims(research_claim_id),
  verification_status text NOT NULL DEFAULT 'reported' CHECK (verification_status IN ('reported','verified','contested','refuted','hypothesis')),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_freight_rate_assessments_1 ON public.pc_freight_rate_assessments(corridor_key,observed_date DESC);
CREATE INDEX idx_freight_rate_assessments_2 ON public.pc_freight_rate_assessments(mode,rate_category,observed_date DESC);

CREATE TABLE public.pc_supply_chain_dependencies (
  supply_chain_dependency_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  dependent_entity_id text REFERENCES public.pc_entities(entity_id),
  dependent_asset_id text REFERENCES public.pc_assets(asset_id),
  dependent_corridor_key text REFERENCES public.pc_trade_corridors(corridor_key),
  provider_entity_id text REFERENCES public.pc_entities(entity_id),
  provider_asset_id text REFERENCES public.pc_assets(asset_id),
  provider_corridor_key text REFERENCES public.pc_trade_corridors(corridor_key),
  dependency_type text NOT NULL, criticality text DEFAULT 'unassessed',
  substitute_available boolean, documented_basis text,
  valid_from date, valid_to date,  source_id text REFERENCES public.pc_sources(source_id),
  research_claim_id uuid REFERENCES public.pc_research_claims(research_claim_id),
  verification_status text NOT NULL DEFAULT 'reported' CHECK (verification_status IN ('reported','verified','contested','refuted','hypothesis')),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (num_nonnulls(dependent_entity_id,dependent_asset_id,dependent_corridor_key)=1 AND num_nonnulls(provider_entity_id,provider_asset_id,provider_corridor_key)=1)
);
CREATE INDEX idx_supply_chain_dependencies_1 ON public.pc_supply_chain_dependencies(dependent_entity_id);
CREATE INDEX idx_supply_chain_dependencies_2 ON public.pc_supply_chain_dependencies(dependent_corridor_key);
CREATE INDEX idx_supply_chain_dependencies_3 ON public.pc_supply_chain_dependencies(provider_entity_id);

CREATE TABLE public.pc_logistics_event_impacts (
  logistics_event_impact_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id text NOT NULL REFERENCES public.pc_events(event_id),
  logistics_shipment_id uuid REFERENCES public.pc_logistics_shipments(logistics_shipment_id),
  shipment_leg_id uuid REFERENCES public.pc_logistics_shipment_legs(shipment_leg_id),
  transport_service_id text REFERENCES public.pc_transport_services(transport_service_id),
  corridor_key text REFERENCES public.pc_trade_corridors(corridor_key),
  impact_type text NOT NULL, status text DEFAULT 'reported',
  measured_delay_hours numeric, estimated_additional_cost numeric,
  cost_currency text, measured_at timestamptz,
  causal_status text NOT NULL DEFAULT 'reported' CHECK (causal_status IN ('reported','evidenced','modelled','hypothetical','refuted')),  source_id text REFERENCES public.pc_sources(source_id),
  research_claim_id uuid REFERENCES public.pc_research_claims(research_claim_id),
  verification_status text NOT NULL DEFAULT 'reported' CHECK (verification_status IN ('reported','verified','contested','refuted','hypothesis')),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (num_nonnulls(logistics_shipment_id,shipment_leg_id,transport_service_id,corridor_key)>=1)
);
CREATE INDEX idx_logistics_event_impacts_1 ON public.pc_logistics_event_impacts(event_id,impact_type);
CREATE INDEX idx_logistics_event_impacts_2 ON public.pc_logistics_event_impacts(corridor_key);

-- Restrict NEW tables to service_role pending specialist-app policies.
DO $$ DECLARE t text; BEGIN
  FOREACH t IN ARRAY ARRAY['pc_logistics_shipments','pc_logistics_shipment_legs','pc_logistics_service_agreements','pc_corridor_mode_connections','pc_freight_rate_assessments','pc_supply_chain_dependencies','pc_logistics_event_impacts'] LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY',t);
    EXECUTE format('REVOKE ALL ON public.%I FROM PUBLIC',t);
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='anon') THEN EXECUTE format('REVOKE ALL ON public.%I FROM anon',t); END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN EXECUTE format('REVOKE ALL ON public.%I FROM authenticated',t); END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='service_role') THEN EXECUTE format('GRANT SELECT,INSERT,UPDATE,DELETE ON public.%I TO service_role',t); END IF;
  END LOOP;
END $$;
COMMIT;

-- Verification: expected 7 tables, each rls_enabled=true.
SELECT c.relname AS table_name,c.relrowsecurity AS rls_enabled FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind='r' AND c.relname IN ('pc_logistics_shipments','pc_logistics_shipment_legs','pc_logistics_service_agreements','pc_corridor_mode_connections','pc_freight_rate_assessments','pc_supply_chain_dependencies','pc_logistics_event_impacts') ORDER BY c.relname;
