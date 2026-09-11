#!/usr/bin/env python3
"""Non-destructive P&C post-normalization checks and issue staging."""
from __future__ import annotations
import os, re, json
from collections import defaultdict
from supabase import create_client

url=os.getenv("SUPABASE_URL"); key=os.getenv("SUPABASE_SERVICE_ROLE_KEY")
if not url or not key: raise SystemExit("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY")
sb=create_client(url,key)

def all_rows(table,cols="*"):
    out=[]; start=0
    while True:
        c=sb.table(table).select(cols).range(start,start+999).execute().data or []
        out+=c
        if len(c)<1000: return out
        start+=1000

def norm_port(name):
    s=re.sub(r"^port of\s+","",str(name or "").strip().lower())
    s=re.sub(r"[^a-z0-9]+"," ",s)
    return " ".join(s.split())

issues=[]
assets=all_rows("pc_assets","asset_id,name,asset_type,country")
groups=defaultdict(list)
for a in assets:
    if "port" in str(a.get("asset_type","")).lower():
        groups[(norm_port(a.get("name")),str(a.get("country") or "").lower())].append(a)
for (name,country),rows in groups.items():
    if name and len(rows)>1:
        issues.append({"object_type":"asset","object_id":rows[0]['asset_id'],"issue_type":"POSSIBLE_DUPLICATE_PORT","severity":"medium","description":f"{len(rows)} port records normalize to {name} / {country}.","suggested_action":"Review before merging; retain aliases and terminal parent links.","metadata":{"asset_ids":[r['asset_id'] for r in rows],"names":[r['name'] for r in rows]}})

# Flag IMO duplicates defensively (DB unique index should normally prevent them).
mob=all_rows("pc_mobile_assets","mobile_asset_id,name,imo")
imos=defaultdict(list)
for v in mob:
    imo=str(v.get('imo') or '').strip()
    if imo: imos[imo].append(v)
for imo,rows in imos.items():
    if len(rows)>1:
        issues.append({"object_type":"mobile_asset","object_id":rows[0]['mobile_asset_id'],"issue_type":"DUPLICATE_IMO","severity":"high","description":f"IMO {imo} is attached to multiple mobile assets.","suggested_action":"Resolve to one canonical vessel.","metadata":{"records":rows}})

# Intelligence corporate leakage must be zero.
events=all_rows("pc_events","event_id,title,event_nature,intelligence_visible,intelligence_relevance")
for e in events:
    if e.get('intelligence_visible') and e.get('event_nature')=='CORPORATE':
        issues.append({"object_type":"event","object_id":e['event_id'],"issue_type":"INTELLIGENCE_CORPORATE_LEAKAGE","severity":"high","description":"Corporate development is visible in P&C Intelligence.","suggested_action":"Set intelligence_visible=false unless there is a separate disruption/security event.","metadata":{"title":e.get('title')}})

if issues:
    for i in range(0,len(issues),250): sb.table("pc_data_quality_issues").insert(issues[i:i+250]).execute()
print(json.dumps({"issues_staged":len(issues),"duplicate_port_groups":sum(1 for x in issues if x['issue_type']=='POSSIBLE_DUPLICATE_PORT'),"intel_corporate_leakage":sum(1 for x in issues if x['issue_type']=='INTELLIGENCE_CORPORATE_LEAKAGE')},indent=2))
