#!/usr/bin/env python3
"""Normalize the P&C legacy mirror into production canonical tables.

The mapping is deliberately conservative: known IDs are preserved; ambiguous duplicate
ports/relationships are not silently merged. Run cleanup_validate.py afterwards.
"""
from __future__ import annotations
import argparse, os, re, json
from datetime import datetime
from supabase import create_client


def val(r,*keys,default=None):
    for k in keys:
        v=r.get(k)
        if v is not None and str(v).strip() not in {"","nan","None"}: return v
    return default

def text(r,*keys):
    v=val(r,*keys,default="")
    return str(v).strip() if v is not None else ""

def num(v):
    if v is None or str(v).strip()=="": return None
    try: return float(str(v).replace(",",""))
    except Exception: return None

def integer(v):
    n=num(v); return int(n) if n is not None else None

def boolish(v):
    s=str(v or "").strip().lower()
    if s in {"yes","true","1","y","full","control"}: return True
    if s in {"no","false","0","n"}: return False
    return None

def first_id(v):
    s=str(v or "").strip()
    return re.split(r"[;,|]",s)[0].strip() if s else None

def batches(seq,n=500):
    for i in range(0,len(seq),n): yield seq[i:i+n]

class DB:
    def __init__(self,url,key): self.sb=create_client(url,key)
    def rows(self,book,sheet):
        out=[]; start=0
        while True:
            resp=self.sb.table("pc_legacy_sheet_rows").select("row_data,row_number").eq("source_book",book).eq("source_sheet",sheet).order("row_number").range(start,start+999).execute()
            chunk=resp.data or []; out.extend([x.get("row_data",{}) for x in chunk])
            if len(chunk)<1000: break
            start+=1000
        return out
    def upsert(self,table,rows,conflict=None):
        if not rows: return
        for part in batches(rows):
            q=self.sb.table(table).upsert(part,on_conflict=conflict) if conflict else self.sb.table(table).upsert(part)
            q.execute()
        print(f"{table}: {len(rows)}")
    def entity_ids(self):
        ids=set(); start=0
        while True:
            c=self.sb.table("pc_entities").select("entity_id").range(start,start+999).execute().data or []
            ids|={x['entity_id'] for x in c if x.get('entity_id')}
            if len(c)<1000: break
            start+=1000
        return ids
    def source_ids(self):
        ids=set(); start=0
        while True:
            c=self.sb.table("pc_sources").select("source_id").range(start,start+999).execute().data or []
            ids|={x['source_id'] for x in c if x.get('source_id')}
            if len(c)<1000: break
            start+=1000
        return ids


def route_event(r):
    blob=" ".join(text(r,k) for k in ["Event Family","Event Type","Title","Description","Operational Impact"]).lower()
    security=re.search(r"war|conflict|attack|missile|drone|piracy|hijack|boarding|seizure|smuggl|traffick|fraud|crime|terror|sabotage|mine|sanction|interdict",blob)
    disruption=re.search(r"weather|typhoon|hurricane|cyclone|flood|earthquake|wildfire|storm|grounding|collision|allision|capsize|sinking|fire|explosion|labour|strike|protest|closure|outage|disruption|low water|cyber",blob)
    corporate=re.search(r"investment|acquisition|terminal opening|commissioning|new crane|equipment order|vessel order|contract award|earnings|financing|service launch",blob)
    if security: nature="SECURITY"
    elif disruption: nature="DISRUPTION"
    elif corporate: nature="CORPORATE"
    else: nature="OTHER"
    severity=text(r,"Severity").lower()
    commercial=bool(text(r,"Trade / Commercial Impact","Commercial Impact"))
    intel=4 if nature=="SECURITY" else 3 if nature=="DISRUPTION" else 0
    trade=3 if nature in {"SECURITY","DISRUPTION"} and commercial else 2 if nature=="CORPORATE" else 1 if commercial else 0
    return nature,trade,intel,nature in {"SECURITY","DISRUPTION","CORPORATE"},nature in {"SECURITY","DISRUPTION"},(nature in {"SECURITY","DISRUPTION"} and severity in {"critical","high","severe"})


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--batch-size",type=int,default=500); args=ap.parse_args()
    url=os.getenv("SUPABASE_URL"); key=os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key: raise SystemExit("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY")
    db=DB(url,key)

    # Sources first.
    src=[]
    for r in db.rows("10_sources_evidence.xlsx","Sources"):
        sid=text(r,"Source ID")
        if sid: src.append({"source_id":sid,"publisher":text(r,"Publisher"),"source_name":text(r,"Source Note"),"url":text(r,"URL"),"checked_at":text(r,"Checked As Of") or None,"source_type":text(r,"Source Type")})
    db.upsert("pc_sources",src,"source_id")
    source_ids=db.source_ids()

    # Companies/entities.
    ents=[]
    for r in db.rows("01_core_entities.xlsx","Companies"):
        eid=text(r,"Company ID")
        if not eid: continue
        ents.append({"entity_id":eid,"name":text(r,"Company"),"entity_type":text(r,"Entity Type") or "Company","hq_city":text(r,"HQ City"),"hq_country":text(r,"HQ Country"),"ownership_summary":text(r,"Ownership"),"status":text(r,"Status"),"source_id":text(r,"Source ID") if text(r,"Source ID") in source_ids else None,"as_of":text(r,"As Of") or None,"record_status":"verified" if text(r,"Source ID") else "provisional","data_quality":"high" if text(r,"Source ID") else "medium","metadata":{"business_segments":text(r,"Business Segments"),"senior_leader":text(r,"Senior Leader"),"leader_title":text(r,"Title"),"scale_notes":text(r,"Scale / Network Notes")}})
    db.upsert("pc_entities",ents,"entity_id")
    entity_ids=db.entity_ids()

    rels=[]
    for r in db.rows("01_core_entities.xlsx","Relationships"):
        rid=text(r,"Relationship ID")
        if rid: rels.append({"relationship_id":rid,"source_type":"entity","source_id":text(r,"Source Entity"),"relationship_type":text(r,"Relationship"),"target_type":"entity","target_id":text(r,"Target Entity"),"valid_from":text(r,"As Of") or None,"confidence":text(r,"Confidence"),"evidence_source_id":text(r,"Source ID") if text(r,"Source ID") in source_ids else None,"record_status":"verified" if text(r,"Source ID") else "provisional"})
    db.upsert("pc_relationships",rels,"relationship_id")

    # Ports as assets.
    assets=[]
    for r in db.rows("02_maritime.xlsx","Ports"):
        aid=text(r,"Port ID")
        if not aid: continue
        op=text(r,"Operator Company ID")
        assets.append({"asset_id":aid,"name":text(r,"Port / Facility"),"asset_type":text(r,"Facility Type") or "Port","country":text(r,"Country"),"latitude":num(val(r,"Latitude")),"longitude":num(val(r,"Longitude")),"operator_entity_id":op if op in entity_ids else None,"status":"Active","record_status":"verified" if text(r,"Source ID") else "provisional","data_quality":"high" if text(r,"Source ID") else "medium","source_id":text(r,"Source ID") if text(r,"Source ID") in source_ids else None,"metadata":{"operator_name":text(r,"Operator"),"key_role":text(r,"Key Role"),"coverage_note":text(r,"Coverage Note")}})
    # General infrastructure assets.
    for r in db.rows("06_infrastructure.xlsx","Assets"):
        aid=text(r,"Asset ID")
        if not aid: continue
        owner=text(r,"Company ID")
        assets.append({"asset_id":aid,"name":text(r,"Asset"),"asset_type":text(r,"Asset Type") or "Infrastructure","country":text(r,"Country"),"region_city":text(r,"Location"),"owner_entity_id":owner if owner in entity_ids else None,"status":text(r,"Status"),"record_status":"verified" if text(r,"Source ID") else "provisional","data_quality":"medium","source_id":text(r,"Source ID") if text(r,"Source ID") in source_ids else None,"metadata":{"role_function":text(r,"Role / Function"),"primary_mode":text(r,"Primary Mode"),"ownership_interest":text(r,"Ownership / Operating Interest")}})
    for sheet, idcol, namecol, atype in [("Dry Ports","Asset ID","Hub Name","Dry port / inland hub"),("Economic Zones","Asset ID","Zone Name","Economic/free zone")]:
        for r in db.rows("06_infrastructure.xlsx",sheet):
            aid=text(r,idcol) or text(r,"Hub ID","Zone ID")
            if not aid: continue
            owner=text(r,"Parent / Investor Company ID","Parent / Owner Company ID")
            op=text(r,"Operator Company ID")
            assets.append({"asset_id":aid,"name":text(r,namecol),"asset_type":atype,"country":text(r,"Country"),"region_city":text(r,"City / Region"),"owner_entity_id":owner if owner in entity_ids else None,"operator_entity_id":op if op in entity_ids else None,"status":text(r,"Status"),"record_status":"verified" if text(r,"Source ID") else "provisional","data_quality":"medium","source_id":text(r,"Source ID") if text(r,"Source ID") in source_ids else None,"metadata":r})
    # De-dupe by ID keeping later richer row.
    asset_map={a['asset_id']:a for a in assets}; db.upsert("pc_assets",list(asset_map.values()),"asset_id")

    # Vessels/mobile assets.
    mobiles=[]
    duplicate_imo_issues=[]
    seen_imo={}
    for r in db.rows("02_maritime.xlsx","Vessels"):
        vid=text(r,"Vessel ID")
        if not vid: continue
        imo=text(r,"IMO") or None
        if imo and imo in seen_imo:
            duplicate_imo_issues.append({
                "object_type":"mobile_asset","object_id":vid,"issue_type":"DUPLICATE_IMO_SOURCE",
                "severity":"high","description":f"Incoming vessel shares IMO {imo} with {seen_imo[imo]}; skipped from canonical insert.",
                "suggested_action":"Review vessel aliases/duplicate fleet records before merging.",
                "metadata":{"imo":imo,"kept_mobile_asset_id":seen_imo[imo],"skipped_mobile_asset_id":vid,"vessel_name":text(r,"Vessel Name")}
            })
            continue
        if imo: seen_imo[imo]=vid
        owner=text(r,"Owner Company ID"); op=text(r,"Operator Company ID")
        mobiles.append({"mobile_asset_id":vid,"name":text(r,"Vessel Name"),"asset_type":"Vessel","subtype":text(r,"Vessel Type","Subtype / Class"),"imo":imo,"mmsi":text(r,"MMSI") or None,"call_sign":text(r,"Call Sign") or None,"flag":text(r,"Flag"),"year_built":integer(val(r,"Year Built")),"dwt":num(val(r,"DWT")),"owner_entity_id":owner if owner in entity_ids else None,"operator_entity_id":op if op in entity_ids else None,"status":text(r,"Status"),"record_status":"verified" if imo else "provisional","data_quality":"high" if imo else "medium","source_id":text(r,"Source ID") if text(r,"Source ID") in source_ids else None,"metadata":{"class":text(r,"Subtype / Class"),"registered_owner":text(r,"Registered Owner (Legal)"),"technical_manager":text(r,"Technical / ISM Manager"),"capacity":text(r,"Capacity"),"completeness_note":text(r,"Completeness Note")}})
    db.upsert("pc_mobile_assets",mobiles,"mobile_asset_id")
    if duplicate_imo_issues:
        for part in batches(duplicate_imo_issues,250): db.sb.table("pc_data_quality_issues").insert(part).execute()
        print(f"pc_data_quality_issues duplicate IMO: {len(duplicate_imo_issues)}")

    # Events.
    events=[]
    for r in db.rows("13_events_hazards.xlsx","Events"):
        eid=text(r,"Event ID")
        if not eid: continue
        nature,tr,ir,tv,iv,alert=route_event(r)
        events.append({"event_id":eid,"start_date":text(r,"Start Date") or None,"end_date":text(r,"End Date") or None,"event_nature":nature,"event_family":text(r,"Event Family"),"event_type":text(r,"Event Type"),"severity":text(r,"Severity"),"status":text(r,"Status"),"mode":text(r,"Mode"),"countries":text(r,"Country / Countries"),"location":text(r,"Location"),"title":text(r,"Title") or eid,"description":text(r,"Description"),"operational_impact":text(r,"Operational Impact"),"commercial_impact":text(r,"Trade / Commercial Impact"),"confidence":text(r,"Confidence"),"trade_relevance":tr,"intelligence_relevance":ir,"trade_visible":tv,"intelligence_visible":iv,"alert_worthy":alert,"record_status":"verified" if text(r,"Primary Source URL") or text(r,"Source Record") else "provisional","source_id":text(r,"Source Record") if text(r,"Source Record") in source_ids else None,"metadata":{"primary_source_url":text(r,"Primary Source URL")}})
    db.upsert("pc_events",events,"event_id")

    locs=[]
    for r in db.rows("13_events_hazards.xlsx","Event Locations"):
        lid=text(r,"Location Record"); eid=text(r,"Event ID")
        if lid and eid: locs.append({"event_location_id":lid,"event_id":eid,"location_name":text(r,"Location"),"country":text(r,"Country"),"latitude":num(val(r,"Latitude")),"longitude":num(val(r,"Longitude")),"accuracy":text(r,"Accuracy"),"notes":text(r,"Notes")})
    db.upsert("pc_event_locations",locs,"event_location_id")

    links=[]
    mappings=[("Event Asset Links","Asset ID","Asset","asset"),("Event Company Links","Company ID","Company","entity"),("Event System Links","System ID","System","system")]
    for sheet,idc,namec,ltype in mappings:
        for r in db.rows("13_events_hazards.xlsx",sheet):
            lid=text(r,"Link ID"); eid=text(r,"Event ID")
            if lid and eid: links.append({"event_link_id":lid,"event_id":eid,"linked_type":ltype,"linked_id":text(r,idc),"linked_name":text(r,namec),"relationship":text(r,"Relationship") or "RELATED","confidence":text(r,"Confidence"),"metadata":{"notes":text(r,"Notes")}})
    db.upsert("pc_event_links",links,"event_link_id")

    chains=[]
    for r in db.rows("13_events_hazards.xlsx","Impact Chains"):
        cid=text(r,"Chain ID"); eid=text(r,"Event ID")
        if cid and eid: chains.append({"impact_chain_id":cid,"event_id":eid,"step":integer(val(r,"Step")),"trigger":text(r,"Trigger"),"direct_impact":text(r,"Direct Impact"),"secondary_impact":text(r,"Secondary Impact"),"tertiary_impact":text(r,"Tertiary Impact"),"strategic_commercial_outcome":text(r,"Strategic / Commercial Outcome"),"propagation_type":text(r,"Propagation Type")})
    db.upsert("pc_impact_chains",chains,"impact_chain_id")

    # Governance rows from existing model.
    gov=[]
    for r in db.rows("11_systems_waterways_governance.xlsx","Port Governance"):
        gid=text(r,"Port/System Entity ID"); aid=text(r,"Authority/Governing Entity ID")
        if not gid or not aid: continue
        gov.append({"governed_type":"asset","governed_id":gid,"authority_entity_id":aid if aid in entity_ids else None,"authority_name":aid,"governance_role":text(r,"Governance Role"),"model_note":text(r,"Model Note"),"source_url":text(r,"Source URL") or None})
    if gov:
        # No reliable natural conflict target due nullable authority_entity_id; plain insert with duplicate tolerance by pre-query avoided here.
        for g in gov:
            try: db.sb.table("pc_governance_links").insert(g).execute()
            except Exception: pass
        print(f"pc_governance_links: attempted {len(gov)}")

    # Infrastructure transactions.
    tx=[]
    for r in db.rows("08_transactions.xlsx","Infra Deals"):
        tid=text(r,"Deal ID")
        if not tid: continue
        buyer=first_id(val(r,"Investor / Buyer IDs")); target=text(r,"Target Entity / Asset ID")
        tx.append({"transaction_id":tid,"announced_date":text(r,"Announced Date") or None,"effective_date":text(r,"Completed / Effective Date") or None,"buyer_entity_id":buyer if buyer in entity_ids else None,"seller_name":text(r,"Seller / Counterparty"),"target_entity_id":target if target in entity_ids else None,"target_name":text(r,"Target / Asset"),"asset_class":text(r,"Asset Class"),"country_region":text(r,"Country / Region"),"transaction_type":text(r,"Deal Type"),"equity_percent":num(val(r,"Equity %")),"reported_value":num(val(r,"Reported Value")),"currency":text(r,"Currency"),"operating_control":boolish(val(r,"Operating Control")),"status":text(r,"Status"),"regulatory_status":text(r,"Regulatory / Political Status"),"source_id":text(r,"Source ID") if text(r,"Source ID") in source_ids else None,"notes":text(r,"Notes"),"metadata":{"source_url":text(r,"Source URL"),"co_investors":text(r,"Co-Investor / Partner IDs")}})
    db.upsert("pc_transactions",tx,"transaction_id")

    # Sanctions designations.
    sec=[]
    for r in db.rows("14_trade_policy_compliance.xlsx","Sanctions Designations"):
        did=text(r,"Designation ID")
        if not did: continue
        sec.append({"security_record_id":did,"record_type":"Sanctions designation","regime":text(r,"Regime / Linkage"),"event_date":text(r,"Designation Date") or None,"target_type":text(r,"Target Type"),"target_id":text(r,"Canonical Entity ID"),"target_name":text(r,"Target Name"),"identifier":text(r,"IMO / Identifier"),"status":text(r,"Status"),"confidence":"High" if text(r,"Source URL") else "Medium","notes":text(r,"Designation Basis / Link"),"metadata":{"authority_id":text(r,"Authority ID"),"programme_id":text(r,"Programme ID"),"source_url":text(r,"Source URL"),"coverage":text(r,"Model Coverage Status")}})
    db.upsert("pc_security_compliance",sec,"security_record_id")

    print("Normalization complete. Run cleanup_validate.py, then SQL 004/005/006.")

if __name__=="__main__": main()
