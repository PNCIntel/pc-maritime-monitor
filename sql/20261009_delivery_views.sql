-- P&C Data Delivery Layer v1: additive, read-only, live views.
-- Run once in Supabase SQL editor. No canonical data is modified.
-- PostgREST must expose public schema; existing access policies still apply.
BEGIN;
CREATE OR REPLACE VIEW public.pc_delivery_objects AS
SELECT 'entity'::text AS object_type, e.entity_id::text AS object_id,
 e.name::text AS name, 'company'::text AS category,
 NULL::text AS subtype, NULL::text AS country,
 NULL::double precision AS latitude, NULL::double precision AS longitude,
 to_jsonb(e) AS payload
FROM public.pc_entities e
UNION ALL SELECT 'asset', a.asset_id::text, a.name::text,
 coalesce(nullif(a.asset_type::text,''),'infrastructure'), a.subtype::text,
 a.country::text, a.latitude::double precision, a.longitude::double precision, to_jsonb(a)
FROM public.pc_assets a
UNION ALL SELECT 'mobile_asset', m.mobile_asset_id::text, m.name::text,
 coalesce(nullif(m.asset_type::text,''),'mobile_asset'), m.subtype::text,
 coalesce(to_jsonb(m)->>'flag',''), NULL::double precision,NULL::double precision,to_jsonb(m)
FROM public.pc_mobile_assets m
UNION ALL SELECT 'event', ev.event_id::text, ev.title::text,
 coalesce(to_jsonb(ev)->>'event_type','development'),
 to_jsonb(ev)->>'event_family', to_jsonb(ev)->>'country',
 NULL::double precision,NULL::double precision,to_jsonb(ev)
FROM public.pc_events ev;

-- One view feeds all business-specific menus. Every record retains its source row
-- and object ID. The classification is UI routing, not an assertion of exposure.
CREATE OR REPLACE VIEW public.pc_delivery_catalog AS
SELECT d.*,
 CASE WHEN object_type='entity' THEN 'companies'
 WHEN object_type='mobile_asset' THEN 'fleets'
 WHEN object_type='event' THEN 'developments'
 WHEN category ~* 'airport|aviation|air_cargo|aircraft' OR subtype ~* 'airport|air.cargo' THEN 'aviation'
 WHEN category ~* 'rail|intermodal' OR subtype ~* 'rail|intermodal' THEN 'rail'
 WHEN category ~* 'road|truck|warehouse|logistics|distribution|border' OR subtype ~* 'road|truck|warehouse|logistics|distribution' THEN 'land_logistics'
 WHEN category ~* 'refiner|oil|gas|energy|lng|power|pipeline|petrochemical|industrial|manufactur|shipyard|factory' OR subtype ~* 'refiner|oil|gas|energy|lng|power|pipeline|industrial|shipyard' THEN 'industry_energy'
 WHEN category ~* 'port|terminal|harbour|marine|berth' OR subtype ~* 'port|terminal|harbour|marine|berth' THEN 'ports_terminals'
 ELSE 'other_infrastructure' END AS trade_section
FROM public.pc_delivery_objects d;

-- Product-level views retain everything relevant for first-pass, unfiltered
-- discovery. A record appearing in two products does not imply an incident link.
CREATE OR REPLACE VIEW public.pc_app_trade_records AS
 SELECT *, trade_section AS section FROM public.pc_delivery_catalog;
CREATE OR REPLACE VIEW public.pc_app_security_records AS
 SELECT *, CASE WHEN object_type='event' THEN 'incidents'
 WHEN object_type='mobile_asset' THEN 'exposed_fleets'
 WHEN object_type='entity' THEN 'organisations'
 ELSE 'infrastructure' END AS section FROM public.pc_delivery_catalog;
CREATE OR REPLACE VIEW public.pc_app_strategic_records AS
 SELECT *, CASE WHEN trade_section='industry_energy' THEN 'industry'
 WHEN object_type='mobile_asset' THEN 'platforms'
 WHEN object_type='entity' THEN 'organisations'
 WHEN object_type='event' THEN 'developments' ELSE 'facilities' END AS section FROM public.pc_delivery_catalog;
CREATE OR REPLACE VIEW public.pc_app_sanctions_records AS
 SELECT *, CASE WHEN object_type='mobile_asset' THEN 'vessels'
 WHEN object_type='entity' THEN 'entities'
 WHEN object_type='event' THEN 'developments' ELSE 'infrastructure' END AS section FROM public.pc_delivery_catalog;
CREATE OR REPLACE VIEW public.pc_app_capital_records AS
 SELECT *, CASE WHEN object_type='entity' THEN 'companies'
 WHEN object_type='asset' THEN 'infrastructure'
 WHEN object_type='event' THEN 'transactions_and_news' ELSE 'fleets' END AS section FROM public.pc_delivery_catalog;
CREATE OR REPLACE VIEW public.pc_app_commodities_records AS
 SELECT *, CASE WHEN trade_section='industry_energy' THEN 'energy_industry'
 WHEN trade_section IN ('ports_terminals','rail','land_logistics') THEN 'supply_chain'
 WHEN object_type='event' THEN 'developments' ELSE 'organisations_assets' END AS section FROM public.pc_delivery_catalog;
CREATE OR REPLACE VIEW public.pc_app_markets_records AS
 SELECT *, CASE WHEN object_type='event' THEN 'market_developments'
 WHEN trade_section='ports_terminals' THEN 'ports_capacity'
 WHEN trade_section='fleets' THEN 'fleet_supply' ELSE 'transport_network' END AS section FROM public.pc_delivery_catalog;

-- Explicit incident links: direct links only. No city/name/ownership inference.
CREATE OR REPLACE VIEW public.pc_delivery_direct_incidents AS
SELECT DISTINCT 'asset'::text AS object_type, l.asset_id::text AS object_id,
 l.event_id::text AS event_id, 'pc_event_asset_links'::text AS link_source
FROM public.pc_event_asset_links l
UNION
SELECT DISTINCT CASE WHEN lower(l.linked_type::text) IN ('vessel','aircraft') THEN 'mobile_asset'
 WHEN lower(l.linked_type::text) IN ('company','organisation','organization') THEN 'entity'
 ELSE lower(l.linked_type::text) END,
 l.linked_id::text, l.event_id::text, 'pc_event_links'
FROM public.pc_event_links l
WHERE lower(l.linked_type::text) IN ('asset','infrastructure','entity','company','organisation','organization','mobile_asset','vessel','aircraft')
UNION
SELECT DISTINCT 'mobile_asset', v.mobile_asset_id::text,v.event_id::text,'pc_v_event_vessel_links'
FROM public.pc_v_event_vessel_links v WHERE v.mobile_asset_id IS NOT NULL;

-- Specialist parent-child relationship with explicit verified keys.
CREATE OR REPLACE VIEW public.pc_delivery_facility_children AS
SELECT t.parent_port_asset_id::text AS parent_object_id,
 t.asset_id::text AS child_object_id,
 'parent_port'::text AS relationship_basis
FROM public.pc_terminal_details t
WHERE t.parent_port_asset_id IS NOT NULL AND t.asset_id IS NOT NULL;
COMMIT;

-- Verification:
-- SELECT section,count(*) FROM public.pc_app_trade_records GROUP BY section ORDER BY section;
-- SELECT * FROM public.pc_delivery_facility_children WHERE parent_object_id='PORT_UAE_PORT_OF_FUJAIRAH';
-- SELECT * FROM public.pc_delivery_direct_incidents WHERE object_id='VESSEL_00092';
