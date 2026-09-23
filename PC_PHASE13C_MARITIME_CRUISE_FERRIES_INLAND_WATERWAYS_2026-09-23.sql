-- POWER & CORRIDORS | PHASE 13C | MARITIME, CRUISE, FERRIES & INLAND WATERWAYS
-- Run in order AFTER 13A and 13B. Public schema only.
-- Additive structural tables; does not backfill data or modify existing views/RLS.
-- All facts require explicit source provenance; no speculative seed entities.
BEGIN;
DO $$ DECLARE t text; BEGIN
  FOREACH t IN ARRAY ARRAY['pc_entities','pc_assets','pc_mobile_assets','pc_sources','pc_events','pc_trade_corridors','pc_research_claims','pc_cruise_itineraries','pc_ferry_routes','pc_transport_services'] LOOP
    IF to_regclass(format('public.%I',t)) IS NULL THEN RAISE EXCEPTION 'Missing prerequisite table %',t; END IF;
  END LOOP;
END $$;

CREATE TABLE public.pc_vessel_identity_history (
  vessel_identity_history_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  mobile_asset_id text NOT NULL REFERENCES public.pc_mobile_assets(mobile_asset_id),
  identifier_type text NOT NULL CHECK (identifier_type IN ('name','imo','mmsi','call_sign','flag','registration','pennant','other')),
  identifier_value text NOT NULL, valid_from date, valid_to date,
  jurisdiction text, change_reason text,  source_id text REFERENCES public.pc_sources(source_id),
  research_claim_id uuid REFERENCES public.pc_research_claims(research_claim_id),
  verification_status text NOT NULL DEFAULT 'reported' CHECK (verification_status IN ('reported','verified','contested','refuted','hypothesis')),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from)
);
CREATE INDEX idx_vessel_identity_history_1 ON public.pc_vessel_identity_history(mobile_asset_id,identifier_type,valid_from DESC);

CREATE TABLE public.pc_cruise_voyages (
  cruise_voyage_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  cruise_itinerary_id text REFERENCES public.pc_cruise_itineraries(cruise_itinerary_id),
  mobile_asset_id text NOT NULL REFERENCES public.pc_mobile_assets(mobile_asset_id),
  cruise_line_entity_id text REFERENCES public.pc_entities(entity_id),
  voyage_number text, voyage_name text, departure_at timestamptz, expected_return_at timestamptz,
  actual_return_at timestamptz, homeport_asset_id text REFERENCES public.pc_assets(asset_id),
  operational_status text NOT NULL DEFAULT 'scheduled' CHECK (operational_status IN ('planned','scheduled','underway','completed','delayed','diverted','cancelled','suspended','unknown')),
  passengers_reported integer CHECK (passengers_reported >= 0),  source_id text REFERENCES public.pc_sources(source_id),
  research_claim_id uuid REFERENCES public.pc_research_claims(research_claim_id),
  verification_status text NOT NULL DEFAULT 'reported' CHECK (verification_status IN ('reported','verified','contested','refuted','hypothesis')),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_cruise_voyages_1 ON public.pc_cruise_voyages(mobile_asset_id,departure_at DESC);
CREATE INDEX idx_cruise_voyages_2 ON public.pc_cruise_voyages(cruise_itinerary_id);

CREATE TABLE public.pc_cruise_voyage_calls (
  cruise_voyage_call_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  cruise_voyage_id uuid NOT NULL REFERENCES public.pc_cruise_voyages(cruise_voyage_id),
  port_asset_id text NOT NULL REFERENCES public.pc_assets(asset_id),
  sequence_no integer NOT NULL CHECK (sequence_no>0),
  scheduled_arrival_at timestamptz, actual_arrival_at timestamptz,
  scheduled_departure_at timestamptz, actual_departure_at timestamptz,
  call_status text NOT NULL DEFAULT 'scheduled' CHECK (call_status IN ('scheduled','arrived','completed','delayed','skipped','substituted','cancelled','unknown')),
  reported_delay_minutes integer CHECK (reported_delay_minutes>=0),
  related_event_id text REFERENCES public.pc_events(event_id),
  original_port_asset_id text REFERENCES public.pc_assets(asset_id),  source_id text REFERENCES public.pc_sources(source_id),
  research_claim_id uuid REFERENCES public.pc_research_claims(research_claim_id),
  verification_status text NOT NULL DEFAULT 'reported' CHECK (verification_status IN ('reported','verified','contested','refuted','hypothesis')),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (cruise_voyage_id,sequence_no)
);
CREATE INDEX idx_cruise_voyage_calls_1 ON public.pc_cruise_voyage_calls(port_asset_id,scheduled_arrival_at DESC);
CREATE INDEX idx_cruise_voyage_calls_2 ON public.pc_cruise_voyage_calls(related_event_id);

CREATE TABLE public.pc_passenger_incident_impacts (
  passenger_incident_impact_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id text NOT NULL REFERENCES public.pc_events(event_id),
  mobile_asset_id text REFERENCES public.pc_mobile_assets(mobile_asset_id),
  cruise_voyage_id uuid REFERENCES public.pc_cruise_voyages(cruise_voyage_id),
  ferry_route_id text REFERENCES public.pc_ferry_routes(ferry_route_id),
  impact_type text NOT NULL CHECK (impact_type IN ('delay','cancellation','diversion','medical_evacuation','security_threat','fire','mechanical','rescue','passenger_transfer','missed_call','other')),
  affected_passengers integer CHECK (affected_passengers>=0),
  affected_crew integer CHECK (affected_crew>=0),
  delay_minutes integer CHECK (delay_minutes>=0),
  reported_at timestamptz, operational_effect text,  source_id text REFERENCES public.pc_sources(source_id),
  research_claim_id uuid REFERENCES public.pc_research_claims(research_claim_id),
  verification_status text NOT NULL DEFAULT 'reported' CHECK (verification_status IN ('reported','verified','contested','refuted','hypothesis')),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (num_nonnulls(mobile_asset_id,cruise_voyage_id,ferry_route_id)>=1)
);
CREATE INDEX idx_passenger_incident_impacts_1 ON public.pc_passenger_incident_impacts(event_id,impact_type);
CREATE INDEX idx_passenger_incident_impacts_2 ON public.pc_passenger_incident_impacts(mobile_asset_id);

CREATE TABLE public.pc_vessel_deployments (
  vessel_deployment_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  mobile_asset_id text NOT NULL REFERENCES public.pc_mobile_assets(mobile_asset_id),
  operator_entity_id text REFERENCES public.pc_entities(entity_id),
  transport_service_id text REFERENCES public.pc_transport_services(transport_service_id),
  corridor_key text REFERENCES public.pc_trade_corridors(corridor_key),
  deployment_type text NOT NULL CHECK (deployment_type IN ('liner','tramp','cruise','ferry','charter','offshore','government','naval','coast_guard','other')),
  valid_from date, valid_to date, deployment_status text DEFAULT 'reported',  source_id text REFERENCES public.pc_sources(source_id),
  research_claim_id uuid REFERENCES public.pc_research_claims(research_claim_id),
  verification_status text NOT NULL DEFAULT 'reported' CHECK (verification_status IN ('reported','verified','contested','refuted','hypothesis')),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to>=valid_from)
);
CREATE INDEX idx_vessel_deployments_1 ON public.pc_vessel_deployments(mobile_asset_id,valid_from DESC);
CREATE INDEX idx_vessel_deployments_2 ON public.pc_vessel_deployments(corridor_key,valid_from DESC);

CREATE TABLE public.pc_port_service_disruptions (
  port_service_disruption_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id text NOT NULL REFERENCES public.pc_events(event_id),
  port_asset_id text NOT NULL REFERENCES public.pc_assets(asset_id),
  terminal_asset_id text REFERENCES public.pc_assets(asset_id),
  transport_service_id text REFERENCES public.pc_transport_services(transport_service_id),
  disruption_type text NOT NULL CHECK (disruption_type IN ('closure','strike','protest','weather','security','equipment','congestion','navigation','cyber','other')),
  began_at timestamptz, estimated_restoration_at timestamptz, restored_at timestamptz,
  capacity_reduction_percent numeric CHECK (capacity_reduction_percent BETWEEN 0 AND 100),
  vessels_affected integer CHECK (vessels_affected>=0),
  reported_delay_hours numeric CHECK (reported_delay_hours>=0),  source_id text REFERENCES public.pc_sources(source_id),
  research_claim_id uuid REFERENCES public.pc_research_claims(research_claim_id),
  verification_status text NOT NULL DEFAULT 'reported' CHECK (verification_status IN ('reported','verified','contested','refuted','hypothesis')),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_port_service_disruptions_1 ON public.pc_port_service_disruptions(event_id);
CREATE INDEX idx_port_service_disruptions_2 ON public.pc_port_service_disruptions(port_asset_id,began_at DESC);

CREATE TABLE public.pc_inland_waterway_status (
  waterway_status_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  corridor_key text REFERENCES public.pc_trade_corridors(corridor_key),
  waterway_asset_id text REFERENCES public.pc_assets(asset_id),
  observed_at timestamptz NOT NULL, level_m numeric, minimum_depth_m numeric,
  maximum_draft_m numeric, lock_status text, ice_condition text,
  restriction_status text, restriction_start_at timestamptz, restriction_end_at timestamptz,
  related_event_id text REFERENCES public.pc_events(event_id),  source_id text REFERENCES public.pc_sources(source_id),
  research_claim_id uuid REFERENCES public.pc_research_claims(research_claim_id),
  verification_status text NOT NULL DEFAULT 'reported' CHECK (verification_status IN ('reported','verified','contested','refuted','hypothesis')),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (num_nonnulls(corridor_key,waterway_asset_id)>=1)
);
CREATE INDEX idx_inland_waterway_status_1 ON public.pc_inland_waterway_status(corridor_key,observed_at DESC);

-- Restrict NEW tables to service_role pending specialist-app policies.
DO $$ DECLARE t text; BEGIN
  FOREACH t IN ARRAY ARRAY['pc_vessel_identity_history','pc_cruise_voyages','pc_cruise_voyage_calls','pc_passenger_incident_impacts','pc_vessel_deployments','pc_port_service_disruptions','pc_inland_waterway_status'] LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY',t);
    EXECUTE format('REVOKE ALL ON public.%I FROM PUBLIC',t);
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='anon') THEN EXECUTE format('REVOKE ALL ON public.%I FROM anon',t); END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN EXECUTE format('REVOKE ALL ON public.%I FROM authenticated',t); END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='service_role') THEN EXECUTE format('GRANT SELECT,INSERT,UPDATE,DELETE ON public.%I TO service_role',t); END IF;
  END LOOP;
END $$;
COMMIT;

-- Verification: expected 7 tables, each rls_enabled=true.
SELECT c.relname AS table_name,c.relrowsecurity AS rls_enabled FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind='r' AND c.relname IN ('pc_vessel_identity_history','pc_cruise_voyages','pc_cruise_voyage_calls','pc_passenger_incident_impacts','pc_vessel_deployments','pc_port_service_disruptions','pc_inland_waterway_status') ORDER BY c.relname;
