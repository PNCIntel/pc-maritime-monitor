#!/usr/bin/env python3
from __future__ import annotations
import os, json, sys
from supabase import create_client
url=os.getenv("SUPABASE_URL"); key=os.getenv("SUPABASE_SERVICE_ROLE_KEY")
if not url or not key: raise SystemExit("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY")
sb=create_client(url,key)

def count(table,filters=None):
    q=sb.table(table).select("*",count="exact").limit(1)
    for k,v in (filters or {}).items(): q=q.eq(k,v)
    r=q.execute(); return r.count or 0
checks={t:count(t) for t in [
    "pc_sources","pc_entities","pc_assets","pc_mobile_assets","pc_relationships","pc_events","pc_event_locations","pc_event_links","pc_legacy_sheet_rows",
    "pc_energy_assets","pc_industrial_assets","pc_logistics_facilities","pc_market_instruments","pc_market_prices","pc_trade_flows","pc_supply_series",
    "pc_port_metrics","pc_transport_routes","pc_chokepoints","pc_macro_indicators","pc_observations"
]}
checks["intelligence_corporate_leakage"]=count("pc_events",{"intelligence_visible":True,"event_nature":"CORPORATE"})
checks["open_quality_issues"]=count("pc_data_quality_issues",{"status":"open"})
print(json.dumps(checks,indent=2))
required=["pc_entities","pc_assets","pc_mobile_assets","pc_events","pc_legacy_sheet_rows"]
if any(checks[x]==0 for x in required):
    print("FAIL: one or more required core tables are empty",file=sys.stderr); sys.exit(2)
if checks["intelligence_corporate_leakage"]:
    print("WARN: corporate records still leak into Intelligence",file=sys.stderr); sys.exit(3)
print("PASS: core migration populated and Intelligence routing leakage check is zero")
print("Expansion tables may initially be sparse; populate them with seed_open_source_registry.py, normalize_trade_expansion.py and source-specific research/ingestion jobs.")
