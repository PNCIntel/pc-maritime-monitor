-- POWER & CORRIDORS | PHASE 13D | RAIL, ROAD, TRUCKING & AVIATION
-- Run in order AFTER 13A and 13B. Public schema only.
-- Additive structural tables; does not backfill data or modify existing views/RLS.
-- All facts require explicit source provenance; no speculative seed entities.
BEGIN;
DO $$ DECLARE t text; BEGIN
  FOREACH t IN ARRAY ARRAY['pc_entities','pc_assets','pc_mobile_assets','pc_sources','pc_events','pc_trade_corridors','pc_research_claims','pc_rail_networks','pc_rail_links','pc_road_corridors','pc_transport_services'] LOOP
    IF to_regclass(format('public.%I',t)) IS NULL THEN RAISE EXCEPTION 'Missing prerequisite table %',t; END IF;
  END LOOP;
END $$;

CREATE TABLE public.pc_rail_rolling_stock_units (
  rolling_stock_unit_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  mobile_asset_id text REFERENCES public.pc_mobile_assets(mobile_asset_id),
  rail_network_id text REFERENCES public.pc_rail_networks(rail_network_id),
  owner_entity_id text REFERENCES public.pc_entities(entity_id),
  operator_entity_id text REFERENCES public.pc_entities(entity_id),
  unit_identifier text NOT NULL, rolling_stock_type text NOT NULL,
  build_year integer CHECK (build_year BETWEEN 1850 AND 2150),
  gauge_mm integer CHECK (gauge_mm>0), axle_load_tonnes numeric,
  payload_tonnes numeric, traction_type text,
  operational_status text DEFAULT 'reported', valid_from date, valid_to date,  source_id text REFERENCES public.pc_sources(source_id),
  research_claim_id uuid REFERENCES public.pc_research_claims(research_claim_id),
  verification_status text NOT NULL DEFAULT 'reported' CHECK (verification_status IN ('reported','verified','contested','refuted','hypothesis')),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to>=valid_from)
);
CREATE INDEX idx_rail_rolling_stock_units_1 ON public.pc_rail_rolling_stock_units(rail_network_id,operational_status);
CREATE INDEX idx_rail_rolling_stock_units_2 ON public.pc_rail_rolling_stock_units(operator_entity_id);

CREATE TABLE public.pc_rail_service_runs (
  rail_service_run_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  transport_service_id text REFERENCES public.pc_transport_services(transport_service_id),
  rail_network_id text REFERENCES public.pc_rail_networks(rail_network_id),
  operator_entity_id text REFERENCES public.pc_entities(entity_id),
  origin_asset_id text REFERENCES public.pc_assets(asset_id),
  destination_asset_id text REFERENCES public.pc_assets(asset_id),
  scheduled_departure_at timestamptz, actual_departure_at timestamptz,
  scheduled_arrival_at timestamptz, actual_arrival_at timestamptz,
  service_status text NOT NULL DEFAULT 'planned',
  container_teu numeric, gross_tonnes numeric,
  linked_event_id text REFERENCES public.pc_events(event_id),  source_id text REFERENCES public.pc_sources(source_id),
  research_claim_id uuid REFERENCES public.pc_research_claims(research_claim_id),
  verification_status text NOT NULL DEFAULT 'reported' CHECK (verification_status IN ('reported','verified','contested','refuted','hypothesis')),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_rail_service_runs_1 ON public.pc_rail_service_runs(transport_service_id,scheduled_departure_at DESC);
CREATE INDEX idx_rail_service_runs_2 ON public.pc_rail_service_runs(linked_event_id);

CREATE TABLE public.pc_rail_network_disruptions (
  rail_disruption_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id text NOT NULL REFERENCES public.pc_events(event_id),
  rail_network_id text REFERENCES public.pc_rail_networks(rail_network_id),
  rail_link_id text REFERENCES public.pc_rail_links(rail_link_id),
  node_asset_id text REFERENCES public.pc_assets(asset_id),
  disruption_type text NOT NULL CHECK (disruption_type IN ('strike','sabotage','derailment','flood','fire','power','infrastructure','security','capacity','other')),
  start_at timestamptz, expected_restoration_at timestamptz, actual_restoration_at timestamptz,
  estimated_capacity_reduction_percent numeric CHECK (estimated_capacity_reduction_percent BETWEEN 0 AND 100),
  service_effect text,  source_id text REFERENCES public.pc_sources(source_id),
  research_claim_id uuid REFERENCES public.pc_research_claims(research_claim_id),
  verification_status text NOT NULL DEFAULT 'reported' CHECK (verification_status IN ('reported','verified','contested','refuted','hypothesis')),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (num_nonnulls(rail_network_id,rail_link_id,node_asset_id)>=1)
);
CREATE INDEX idx_rail_network_disruptions_1 ON public.pc_rail_network_disruptions(event_id);
CREATE INDEX idx_rail_network_disruptions_2 ON public.pc_rail_network_disruptions(rail_link_id);

CREATE TABLE public.pc_road_network_links (
  road_network_link_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  road_corridor_id text REFERENCES public.pc_road_corridors(road_corridor_id),
  from_asset_id text REFERENCES public.pc_assets(asset_id),
  to_asset_id text REFERENCES public.pc_assets(asset_id),
  route_number text, link_name text, country text, length_km numeric,
  weight_limit_tonnes numeric, height_limit_m numeric,
  hazmat_allowed boolean, status text DEFAULT 'reported', valid_from date, valid_to date,  source_id text REFERENCES public.pc_sources(source_id),
  research_claim_id uuid REFERENCES public.pc_research_claims(research_claim_id),
  verification_status text NOT NULL DEFAULT 'reported' CHECK (verification_status IN ('reported','verified','contested','refuted','hypothesis')),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to>=valid_from)
);
CREATE INDEX idx_road_network_links_1 ON public.pc_road_network_links(road_corridor_id,status);

CREATE TABLE public.pc_trucking_fleet_assignments (
  trucking_fleet_assignment_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  entity_id text NOT NULL REFERENCES public.pc_entities(entity_id),
  mobile_asset_id text NOT NULL REFERENCES public.pc_mobile_assets(mobile_asset_id),
  depot_asset_id text REFERENCES public.pc_assets(asset_id),
  transport_service_id text REFERENCES public.pc_transport_services(transport_service_id),
  relationship_type text NOT NULL CHECK (relationship_type IN ('owned','leased','operated','subcontracted','managed','other')),
  assignment_from date, assignment_to date, operating_region text,  source_id text REFERENCES public.pc_sources(source_id),
  research_claim_id uuid REFERENCES public.pc_research_claims(research_claim_id),
  verification_status text NOT NULL DEFAULT 'reported' CHECK (verification_status IN ('reported','verified','contested','refuted','hypothesis')),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (assignment_to IS NULL OR assignment_from IS NULL OR assignment_to>=assignment_from)
);
CREATE INDEX idx_trucking_fleet_assignments_1 ON public.pc_trucking_fleet_assignments(entity_id,assignment_from DESC);
CREATE INDEX idx_trucking_fleet_assignments_2 ON public.pc_trucking_fleet_assignments(mobile_asset_id);

CREATE TABLE public.pc_road_border_observations (
  road_border_observation_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  border_asset_id text NOT NULL REFERENCES public.pc_assets(asset_id),
  road_corridor_id text REFERENCES public.pc_road_corridors(road_corridor_id),
  observed_at timestamptz NOT NULL,
  crossing_direction text, wait_hours numeric CHECK (wait_hours>=0),
  queue_vehicles integer CHECK (queue_vehicles>=0),
  restriction_type text, status text,
  related_event_id text REFERENCES public.pc_events(event_id),  source_id text REFERENCES public.pc_sources(source_id),
  research_claim_id uuid REFERENCES public.pc_research_claims(research_claim_id),
  verification_status text NOT NULL DEFAULT 'reported' CHECK (verification_status IN ('reported','verified','contested','refuted','hypothesis')),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_road_border_observations_1 ON public.pc_road_border_observations(border_asset_id,observed_at DESC);
CREATE INDEX idx_road_border_observations_2 ON public.pc_road_border_observations(road_corridor_id);

CREATE TABLE public.pc_road_disruptions (
  road_disruption_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id text NOT NULL REFERENCES public.pc_events(event_id),
  road_corridor_id text REFERENCES public.pc_road_corridors(road_corridor_id),
  road_network_link_id uuid REFERENCES public.pc_road_network_links(road_network_link_id),
  border_asset_id text REFERENCES public.pc_assets(asset_id),
  disruption_type text NOT NULL CHECK (disruption_type IN ('accident','strike','protest','blockade','weather','flood','security','border_restriction','road_damage','other')),
  start_at timestamptz, expected_reopening_at timestamptz, reopened_at timestamptz,
  estimated_delay_hours numeric CHECK (estimated_delay_hours>=0),  source_id text REFERENCES public.pc_sources(source_id),
  research_claim_id uuid REFERENCES public.pc_research_claims(research_claim_id),
  verification_status text NOT NULL DEFAULT 'reported' CHECK (verification_status IN ('reported','verified','contested','refuted','hypothesis')),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (num_nonnulls(road_corridor_id,road_network_link_id,border_asset_id)>=1)
);
CREATE INDEX idx_road_disruptions_1 ON public.pc_road_disruptions(event_id);
CREATE INDEX idx_road_disruptions_2 ON public.pc_road_disruptions(road_corridor_id);

CREATE TABLE public.pc_air_service_movements (
  air_service_movement_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  transport_service_id text REFERENCES public.pc_transport_services(transport_service_id),
  mobile_asset_id text REFERENCES public.pc_mobile_assets(mobile_asset_id),
  operator_entity_id text REFERENCES public.pc_entities(entity_id),
  departure_airport_asset_id text REFERENCES public.pc_assets(asset_id),
  arrival_airport_asset_id text REFERENCES public.pc_assets(asset_id),
  flight_number text, scheduled_departure_at timestamptz, actual_departure_at timestamptz,
  scheduled_arrival_at timestamptz, actual_arrival_at timestamptz,
  movement_status text DEFAULT 'scheduled', cargo_tonnes numeric, passenger_count integer,
  related_event_id text REFERENCES public.pc_events(event_id),  source_id text REFERENCES public.pc_sources(source_id),
  research_claim_id uuid REFERENCES public.pc_research_claims(research_claim_id),
  verification_status text NOT NULL DEFAULT 'reported' CHECK (verification_status IN ('reported','verified','contested','refuted','hypothesis')),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_air_service_movements_1 ON public.pc_air_service_movements(mobile_asset_id,scheduled_departure_at DESC);
CREATE INDEX idx_air_service_movements_2 ON public.pc_air_service_movements(related_event_id);

CREATE TABLE public.pc_airspace_disruptions (
  airspace_disruption_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id text NOT NULL REFERENCES public.pc_events(event_id),
  issuing_authority_entity_id text REFERENCES public.pc_entities(entity_id),
  affected_airport_asset_id text REFERENCES public.pc_assets(asset_id),
  fir_code text, notam_reference text, restriction_type text,
  restriction_start_at timestamptz, restriction_end_at timestamptz,
  status text DEFAULT 'reported', geographical_scope jsonb NOT NULL DEFAULT '{}'::jsonb,  source_id text REFERENCES public.pc_sources(source_id),
  research_claim_id uuid REFERENCES public.pc_research_claims(research_claim_id),
  verification_status text NOT NULL DEFAULT 'reported' CHECK (verification_status IN ('reported','verified','contested','refuted','hypothesis')),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_airspace_disruptions_1 ON public.pc_airspace_disruptions(event_id);
CREATE INDEX idx_airspace_disruptions_2 ON public.pc_airspace_disruptions(fir_code,restriction_start_at DESC);

-- Restrict NEW tables to service_role pending specialist-app policies.
DO $$ DECLARE t text; BEGIN
  FOREACH t IN ARRAY ARRAY['pc_rail_rolling_stock_units','pc_rail_service_runs','pc_rail_network_disruptions','pc_road_network_links','pc_trucking_fleet_assignments','pc_road_border_observations','pc_road_disruptions','pc_air_service_movements','pc_airspace_disruptions'] LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY',t);
    EXECUTE format('REVOKE ALL ON public.%I FROM PUBLIC',t);
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='anon') THEN EXECUTE format('REVOKE ALL ON public.%I FROM anon',t); END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN EXECUTE format('REVOKE ALL ON public.%I FROM authenticated',t); END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='service_role') THEN EXECUTE format('GRANT SELECT,INSERT,UPDATE,DELETE ON public.%I TO service_role',t); END IF;
  END LOOP;
END $$;
COMMIT;

-- Verification: expected 9 tables, each rls_enabled=true.
SELECT c.relname AS table_name,c.relrowsecurity AS rls_enabled FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind='r' AND c.relname IN ('pc_rail_rolling_stock_units','pc_rail_service_runs','pc_rail_network_disruptions','pc_road_network_links','pc_trucking_fleet_assignments','pc_road_border_observations','pc_road_disruptions','pc_air_service_movements','pc_airspace_disruptions') ORDER BY c.relname;
