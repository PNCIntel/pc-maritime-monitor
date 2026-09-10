-- Run after 001_core_schema.sql from the package root using psql.
-- Supabase dashboard users can also upload CSVs table-by-table.
\copy sources(source_id,publisher,source_type,coverage,url,checked_as_of,reliability,ingestion_method,active,notes) FROM 'seed/11_sources_observations.csv' CSV HEADER;
\copy entities FROM 'seed/01_entities.csv' CSV HEADER;
\copy assets FROM 'seed/02_assets_infrastructure.csv' CSV HEADER;
\copy mobile_assets FROM 'seed/03_mobile_assets.csv' CSV HEADER;
\copy relationships FROM 'seed/04_relationships.csv' CSV HEADER;
\copy geographies(geo_id,name,geo_type,parent_geo_id,countries,geometry_status,watch_status,risk_level,record_status,source_id,notes) FROM 'seed/05_geography_corridors.csv' CSV HEADER;
\copy events FROM 'seed/06_events.csv' CSV HEADER;
\copy event_links FROM 'seed/06b_event_links.csv' CSV HEADER;
\copy security_compliance(security_record_id,record_type,regime,event_date,target_type,target_id,target_name,identifier,status,exposure_type,related_target,relationship,confidence,record_status,source_id,notes) FROM 'seed/07_security_compliance.csv' CSV HEADER;
\copy financial_investment FROM 'seed/08_financial_investment.csv' CSV HEADER;
\copy market_data(market_record_id,entity_id,exchange,ticker,trade_date,open,high,low,close,volume,currency,record_type,record_status,source_id,notes) FROM 'seed/09_market_data.csv' CSV HEADER;
\copy intelligence_analysis FROM 'seed/10_intelligence_analysis.csv' CSV HEADER;
