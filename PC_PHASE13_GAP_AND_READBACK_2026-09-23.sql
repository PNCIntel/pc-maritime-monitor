-- Run BEFORE each migration and AFTER structural rollout. Read only.
-- Avoid duplicate creation if prior migrations already ran.
WITH expected(phase,table_name) AS (VALUES
 ('13C','pc_vessel_identity_history'),
 ('13C','pc_cruise_voyages'),
 ('13C','pc_cruise_voyage_calls'),
 ('13C','pc_passenger_incident_impacts'),
 ('13C','pc_vessel_deployments'),
 ('13C','pc_port_service_disruptions'),
 ('13C','pc_inland_waterway_status'),
 ('13D','pc_rail_rolling_stock_units'),
 ('13D','pc_rail_service_runs'),
 ('13D','pc_rail_network_disruptions'),
 ('13D','pc_road_network_links'),
 ('13D','pc_trucking_fleet_assignments'),
 ('13D','pc_road_border_observations'),
 ('13D','pc_road_disruptions'),
 ('13D','pc_air_service_movements'),
 ('13D','pc_airspace_disruptions'),
 ('13E','pc_logistics_shipments'),
 ('13E','pc_logistics_shipment_legs'),
 ('13E','pc_logistics_service_agreements'),
 ('13E','pc_corridor_mode_connections'),
 ('13E','pc_freight_rate_assessments'),
 ('13E','pc_supply_chain_dependencies'),
 ('13E','pc_logistics_event_impacts'),
 ('13F','pc_defence_organisations'),
 ('13F','pc_defence_programmes'),
 ('13F','pc_defence_programme_participants'),
 ('13F','pc_shipbuilding_production_tasks'),
 ('13F','pc_defence_programme_milestones'),
 ('13F','pc_shipyard_capacity_history'),
 ('13F','pc_security_operations'),
 ('13F','pc_security_operation_participants'),
 ('13F','pc_security_attribution_claims'))
SELECT e.phase,e.table_name,
 CASE WHEN c.oid IS NULL THEN 'MISSING' ELSE 'PRESENT' END AS actual_status,
 COALESCE(c.relrowsecurity,false) AS rls_enabled,
 (SELECT COUNT(*) FROM pg_attribute a WHERE a.attrelid=c.oid AND a.attnum>0 AND NOT a.attisdropped) AS column_count
FROM expected e LEFT JOIN pg_namespace n ON n.nspname='public'
LEFT JOIN pg_class c ON c.relnamespace=n.oid AND c.relname=e.table_name AND c.relkind='r'
ORDER BY phase,table_name;
