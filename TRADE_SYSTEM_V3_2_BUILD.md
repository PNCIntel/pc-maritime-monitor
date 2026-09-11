# P&C Trade System v3.2 — Global Trade-System Expansion

This build adds the normalized foundation for the broader P&C Trade model: energy, industrial assets, logistics facilities, markets, physical trade flows, supply/production, port economics, inland transport, chokepoints and macro context.

## New SQL

`sql/009_trade_system_expansion.sql`

Key tables:

- `pc_observations`
- `pc_energy_assets`
- `pc_energy_asset_connections`
- `pc_industrial_assets`
- `pc_logistics_facilities`
- `pc_market_instruments`
- `pc_market_prices`
- `pc_market_exposure_links`
- `pc_trade_flows`
- `pc_supply_series`
- `pc_port_metrics`
- `pc_port_capabilities`
- `pc_transport_routes`
- `pc_transport_route_status`
- `pc_chokepoints`
- `pc_chokepoint_status`
- `pc_macro_indicators`

## Canonical rule

Companies and physical objects still live once in `pc_entities` / `pc_assets`. The new tables are extensions and time-series/relationship layers, not duplicate entity stores.

## New Trade pages

- Energy & Industry
- Market Instruments
- Trade Flows & Supply
- Country & Macro

## New Power Admin workspace

**Trade System Builder** provides research-campaign prompts, source registry status, normalization commands and build order.

## New seed / ingestion tools

- `seed_open_source_registry.py`
- `seed_market_instruments.py`
- `normalize_trade_expansion.py`
- `ingest_world_bank_macro.py`
- `stage_ourairports.py`

## Source registry

The first registry includes EIA, JODI, Global Energy Monitor, Energy Institute, IMF, World Bank, UNCTAD, WTO, UN Comtrade, FAOSTAT, SEC EDGAR, OpenStreetMap, OurAirports and The Signal Group. Licence and redistribution metadata is retained because public availability does not automatically mean client redistribution is permitted.

## Validation

All Python files in the kit compile successfully after this expansion. Live Supabase runtime validation still requires the project URL and service-role credentials.
