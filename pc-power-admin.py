from __future__ import annotations
from pathlib import Path
import os, sys, json, uuid, hashlib, re
import pandas as pd
import streamlit as st

ROOT=Path(__file__).resolve().parent
SHARED=ROOT/"shared"
if str(SHARED) not in sys.path: sys.path.insert(0,str(SHARED))
from pc_auth import require_super_admin, service_client
from pc_db import count_rows, safe_rows
try:
    from pc_ai import research as ai_research, configured as ai_configured
except Exception:
    ai_research=None
    ai_configured=lambda: False

st.set_page_config(page_title="P&C Power Admin",page_icon="◈",layout="wide")
st.markdown("""
<style>
:root{--bg:#07111f;--panel:#0d1a2b;--line:#28415f;--text:#f3f6fa;--muted:#b8c5d4;--gold:#d7b66a}
.stApp{background:var(--bg);color:var(--text)} [data-testid="stSidebar"]{background:#091725!important}
h1,h2,h3,p,label{color:var(--text)!important}.pc-card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px;margin-bottom:10px}.pc-k{color:var(--gold);font-size:.72rem;letter-spacing:.12em;text-transform:uppercase}
</style>""",unsafe_allow_html=True)

if os.getenv("PC_REQUIRE_AUTH","false").lower()=="true":
    ctx=require_super_admin()
else:
    ctx={"global_role":"super_admin","email":"migration-local"}

sb=service_client()
st.sidebar.markdown("<div class='pc-k'>Power & Corridors</div>",unsafe_allow_html=True)
st.sidebar.markdown("## Power Admin")
PAGES=["Dashboard","Migration","Organizations","Users & Access","Research Jobs","Trade System Builder","Batch Staging","Review Queue","Market Data","Governance & Quality"]

# ---------------------------------------------------------------------------
# Bulk review / validation helpers
# ---------------------------------------------------------------------------

REQUIRED_BY_TABLE = {
    "pc_entities": ["entity_id","name","entity_type"],
    "pc_assets": ["asset_id","name","asset_type"],
    "pc_mobile_assets": ["mobile_asset_id","name","mobile_type"],
    "pc_relationships": ["relationship_id","source_type","source_id","relationship_type","target_type","target_id"],
    "pc_events": ["event_id","event_type"],
    "pc_transactions": ["transaction_id"],
    "pc_energy_assets": ["asset_id"],
    "pc_industrial_assets": ["asset_id"],
    "pc_logistics_facilities": ["asset_id"],
    "pc_market_instruments": ["market_instrument_id","name"],
    "pc_market_exposure_links": ["target_type","target_id","market_instrument_id","exposure_type"],
    "pc_trade_flows": ["trade_flow_id"],
    "pc_supply_series": ["supply_series_id"],
    "pc_transport_routes": ["route_id","route_name","mode"],
    "pc_chokepoints": ["chokepoint_id","name"],
}

FK_RULES = {
    "pc_logistics_facilities": [
        ("owner_entity_id","pc_entities","entity_id"),
        ("operator_entity_id","pc_entities","entity_id"),
    ],
    "pc_energy_assets": [
        ("operator_entity_id","pc_entities","entity_id"),
        ("owner_entity_id","pc_entities","entity_id"),
    ],
    "pc_industrial_assets": [
        ("operator_entity_id","pc_entities","entity_id"),
        ("owner_entity_id","pc_entities","entity_id"),
    ],
    "pc_transport_routes": [
        ("operator_entity_id","pc_entities","entity_id"),
    ],
    "pc_market_exposure_links": [
        ("market_instrument_id","pc_market_instruments","market_instrument_id"),
    ],
}

def _source_count(payload):
    if not isinstance(payload,dict): return 0
    count=0
    meta=payload.get("metadata") or {}
    if isinstance(meta,dict):
        for key in ("research_sources","sources"):
            seq=meta.get(key) or []
            if isinstance(seq,list):
                count += sum(1 for s in seq if isinstance(s,dict) and (s.get("url") or s.get("source_url")))
    seq=payload.get("sources") or []
    if isinstance(seq,list):
        count += sum(1 for s in seq if isinstance(s,dict) and (s.get("url") or s.get("source_url")))
    if payload.get("source_url"):
        count += 1
    return count

def _schema_valid(table,payload):
    if table not in AI_ALLOWED_TABLES or not isinstance(payload,dict):
        return False, ["invalid target/payload"]
    missing=[k for k in REQUIRED_BY_TABLE.get(table,[]) if payload.get(k) in (None,"")]
    return len(missing)==0, missing

def _fk_valid(sb,table,payload):
    problems=[]
    for field,ref_table,ref_col in FK_RULES.get(table,[]):
        value=payload.get(field)
        if value in (None,""):
            continue
        try:
            hit=(sb.table(ref_table).select(ref_col).eq(ref_col,value).limit(1).execute().data or [])
            if not hit:
                problems.append(f"{field}→{ref_table}.{ref_col} missing")
        except Exception:
            problems.append(f"{field} FK check failed")
    return len(problems)==0,problems

def _duplicate_check(sb,table,payload):
    """Conservative exact duplicate check on canonical identifiers and names."""
    try:
        conflict=APPLY_CONFLICT_KEYS.get(table)
        if conflict:
            keys=[x.strip() for x in conflict.split(",")]
            if all(payload.get(k) not in (None,"") for k in keys):
                q=sb.table(table).select("*")
                for k in keys:
                    q=q.eq(k,payload[k])
                hit=q.limit(1).execute().data or []
                if hit:
                    return True,"conflict-key match"

        if table in {"pc_entities","pc_assets","pc_mobile_assets"} and payload.get("name"):
            hit=sb.table(table).select("*").eq("name",payload["name"]).limit(1).execute().data or []
            if hit:
                return True,"exact-name match"
    except Exception:
        pass
    return False,""


def _slug(value):
    s=re.sub(r"[^A-Z0-9]+","_",str(value or "").upper()).strip("_")
    return s[:48] or "UNNAMED"

def _deterministic_asset_id(name,country="",asset_type=""):
    raw=f"{name}|{country}|{asset_type}".encode("utf-8")
    digest=hashlib.sha1(raw).hexdigest()[:10].upper()
    return f"ASSET_AI_{_slug(name)[:28]}_{digest}"

def _name_from_staged(row,payload):
    if isinstance(payload,dict):
        for key in ("name","asset_name","facility_name","terminal_name","port_name","hub_name","route_name","title"):
            if payload.get(key):
                return str(payload[key]).strip()
    nk=str(row.get("natural_key") or "").strip()
    if " - " in nk:
        return nk.rsplit(" - ",1)[0].strip()
    return nk or "Unnamed asset"

def _country_from_staged(row,payload):
    if isinstance(payload,dict) and payload.get("country"):
        return str(payload["country"]).strip()
    nk=str(row.get("natural_key") or "")
    if " - " in nk:
        return nk.rsplit(" - ",1)[-1].strip()
    return None

def _extension_parent_plan(row):
    """Return parent-asset plan for extension tables that require pc_assets.asset_id."""
    table=row.get("target_table")
    payload=row.get("payload") or {}
    if table not in {"pc_logistics_facilities","pc_energy_assets","pc_industrial_assets"}:
        return None
    if payload.get("asset_id"):
        return None

    name=_name_from_staged(row,payload)
    country=_country_from_staged(row,payload)
    if table=="pc_logistics_facilities":
        asset_type="Logistics facility"
    elif table=="pc_energy_assets":
        asset_type="Energy infrastructure"
    else:
        asset_type="Industrial asset"

    return {
        "asset_id":_deterministic_asset_id(name,country or "",asset_type),
        "name":name,
        "asset_type":asset_type,
        "country":country,
        "status":payload.get("operational_status") or payload.get("status"),
        "record_status":"verified",
        "metadata":{
            "created_from_staged_record":row.get("staged_record_id"),
            "ai_canonicalization":True,
            "natural_key":row.get("natural_key"),
        },
    }

def _ensure_parent_asset(sb,row,payload):
    """Create/link a pc_assets parent for extension records that need asset_id."""
    plan=_extension_parent_plan(row)
    if not plan:
        return payload,False

    # Exact-name/country duplicate check first.
    q=sb.table("pc_assets").select("asset_id,name,country,asset_type").eq("name",plan["name"])
    hits=q.limit(10).execute().data or []
    if plan.get("country"):
        country=str(plan["country"]).strip().casefold()
        same=[x for x in hits if not x.get("country") or str(x.get("country")).strip().casefold()==country]
        if same:
            plan["asset_id"]=same[0]["asset_id"]
    elif hits:
        plan["asset_id"]=hits[0]["asset_id"]

    # Upsert parent canonical asset, preserving any existing exact-ID record.
    sb.table("pc_assets").upsert(plan,on_conflict="asset_id").execute()

    payload=dict(payload)
    payload["asset_id"]=plan["asset_id"]
    meta=payload.get("metadata") or {}
    if not isinstance(meta,dict):
        meta={}
    meta["canonical_parent_asset_id"]=plan["asset_id"]
    payload["metadata"]=meta
    return payload,True

def validate_staged_for_bulk(sb,row):
    payload=row.get("payload") or {}
    table=row.get("target_table")
    confidence=row.get("confidence")
    try: confidence=float(confidence)
    except Exception: confidence=0.0

    schema_ok,missing=_schema_valid(table,payload)
    parent_plan=_extension_parent_plan(row)

    # For extension tables, a missing asset_id can be resolved safely by creating/linking
    # the canonical pc_assets parent during apply.
    parent_needed=False
    if parent_plan and missing==["asset_id"]:
        schema_ok=True
        missing=[]
        parent_needed=True

    fk_ok,fk_problems=_fk_valid(sb,table,payload)
    duplicate,dup_reason=_duplicate_check(sb,table,payload)
    sources=_source_count(payload)

    safe=(
        confidence >= 0.90
        and schema_ok
        and fk_ok
        and not duplicate
        and sources >= 1
        and table in APPLY_CONFLICT_KEYS
    )

    risk=[]
    if confidence < 0.90: risk.append("confidence<0.90")
    if not schema_ok: risk.append("missing:"+",".join(missing))
    if not fk_ok: risk.extend(fk_problems)
    if duplicate: risk.append("duplicate:"+dup_reason)
    if sources < 1: risk.append("no source URL")
    if table not in APPLY_CONFLICT_KEYS: risk.append("no configured apply key")
    if parent_needed: risk.append("will create/link parent asset")

    return {
        "safe":safe,
        "schema_ok":schema_ok,
        "fk_ok":fk_ok,
        "duplicate":duplicate,
        "sources":sources,
        "confidence":confidence,
        "parent_needed":parent_needed,
        "risk":"; ".join(risk) if risk else "safe",
    }

page=st.sidebar.radio("Workspace",PAGES)

if sb is None:
    st.warning("Supabase service connection is not configured yet. The app is valid and can be deployed now; add SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY to secrets before using database actions.")


def dataframe(rows):
    st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True) if rows else st.caption("No records.")

def title(t,copy=""):
    st.markdown(f"<div class='pc-k'>P&C INTERNAL</div><h1>{t}</h1>",unsafe_allow_html=True)
    if copy: st.caption(copy)

# ---------------------------------------------------------------------------
# Controlled AI staging + canonical apply helpers
# ---------------------------------------------------------------------------

AI_ALLOWED_TABLES = {
    "pc_entities",
    "pc_assets",
    "pc_mobile_assets",
    "pc_relationships",
    "pc_events",
    "pc_transactions",
    "pc_security_compliance",
    "pc_energy_assets",
    "pc_energy_asset_connections",
    "pc_industrial_assets",
    "pc_logistics_facilities",
    "pc_market_instruments",
    "pc_market_exposure_links",
    "pc_trade_flows",
    "pc_supply_series",
    "pc_port_metrics",
    "pc_port_capabilities",
    "pc_transport_routes",
    "pc_chokepoints",
    "pc_macro_indicators",
    "pc_observations",
}

# Conflict keys used only when a staged record has enough information to upsert safely.
APPLY_CONFLICT_KEYS = {
    "pc_entities": "entity_id",
    "pc_assets": "asset_id",
    "pc_mobile_assets": "mobile_asset_id",
    "pc_relationships": "relationship_id",
    "pc_events": "event_id",
    "pc_transactions": "transaction_id",
    "pc_security_compliance": "security_compliance_id",
    "pc_energy_assets": "asset_id",
    "pc_energy_asset_connections": "connection_id",
    "pc_industrial_assets": "asset_id",
    "pc_logistics_facilities": "asset_id",
    "pc_market_instruments": "market_instrument_id",
    "pc_market_exposure_links": "target_type,target_id,market_instrument_id,exposure_type",
    "pc_trade_flows": "trade_flow_id",
    "pc_supply_series": "supply_series_id",
    "pc_port_metrics": "port_metric_id",
    "pc_port_capabilities": "port_capability_id",
    "pc_transport_routes": "route_id",
    "pc_chokepoints": "chokepoint_id",
    "pc_macro_indicators": "macro_indicator_id",
    "pc_observations": "observation_id",
}

AI_CAMPAIGNS = {
    "African ports & terminals": (
        "Research major commercial ports, container terminals, dry ports and "
        "port-linked logistics zones across Africa. Prioritize operator, owner, "
        "terminal name, country, city, capacity where explicitly sourced, rail "
        "or road connectivity, recent investment, and source URLs. Propose only "
        "records supported by public evidence."
    ),
    "GCC & Red Sea refineries": (
        "Research operational refineries, LNG plants, gas-processing facilities, "
        "oil export terminals and major storage hubs in the GCC and Red Sea. "
        "Capture owner/operator, location, explicit capacity, operating status, "
        "port/pipeline connections and source URLs."
    ),
    "Mines & export chains": (
        "Research major global mines and export chains for iron ore, bauxite, "
        "copper, nickel, cobalt, lithium, manganese, phosphate and potash. Link "
        "mine or industrial asset to rail/road, export port and destination "
        "markets only where supported by evidence."
    ),
    "Logistics parks & inland hubs": (
        "Research major port-linked logistics parks, free zones, economic zones, "
        "warehouses and inland/intermodal terminals in Africa, the Gulf and Asia. "
        "Capture owner, operator, area/capacity where explicit, port/rail/road "
        "connections, investment values and source URLs."
    ),
    "Infrastructure investors": (
        "Research transport, port, terminal, rail, logistics, airport and related "
        "infrastructure acquisitions or investments by Brookfield, KKR, Macquarie, "
        "OMERS, GIP and other major infrastructure investors since 2018. Capture "
        "transaction date, target, stake, value, geography and evidence."
    ),
    "Custom research": "",
}

AI_OUTPUT_CONTRACT = """
Return JSON with this shape:
{
  "records": [
    {
      "target_table": "one allowed P&C table",
      "natural_key": "stable proposed natural key",
      "action": "REVIEW",
      "confidence": 0.0,
      "payload": {
        "...": "fields supported by evidence",
        "metadata": {
          "research_sources": [
            {"url": "...", "publisher": "...", "title": "..."}
          ]
        }
      }
    }
  ],
  "sources": [],
  "conflicts": [],
  "notes": []
}

Allowed target tables:
""" + ", ".join(sorted(AI_ALLOWED_TABLES))


def _jsonable(v):
    if isinstance(v, dict):
        return {k:_jsonable(x) for k,x in v.items()}
    if isinstance(v, list):
        return [_jsonable(x) for x in v]
    if pd.isna(v) if not isinstance(v,(dict,list,str,bool)) else False:
        return None
    return v


def _record_key(payload, natural_key=""):
    if natural_key:
        return str(natural_key)
    if isinstance(payload,dict):
        for k in (
            "entity_id","asset_id","mobile_asset_id","relationship_id","event_id",
            "transaction_id","route_id","chokepoint_id","market_instrument_id",
            "trade_flow_id","supply_series_id","observation_id"
        ):
            if payload.get(k):
                return str(payload[k])
        for k in ("name","title","route_name"):
            if payload.get(k):
                return str(payload[k])
    return str(uuid.uuid4())


def stage_ai_result(sb, job_id, result):
    """Stage structured AI result. Returns (staged_count, rejected_count)."""
    records=(result or {}).get("records") or []
    staged=[]
    rejected=0

    for rec in records:
        if not isinstance(rec,dict):
            rejected+=1
            continue

        table=str(rec.get("target_table") or "").strip()
        payload=rec.get("payload")

        if table not in AI_ALLOWED_TABLES or not isinstance(payload,dict):
            rejected+=1
            continue

        staged.append({
            "ingestion_job_id":job_id,
            "target_table":table,
            "natural_key":_record_key(payload,rec.get("natural_key") or ""),
            "action":"REVIEW",
            "payload":_jsonable(payload),
            "confidence":rec.get("confidence"),
            "validation_status":"pending",
            "review_status":"pending",
        })

    for i in range(0,len(staged),100):
        sb.table("pc_staged_records").insert(staged[i:i+100]).execute()

    return len(staged),rejected


def apply_staged_record(sb, row, edited_payload=None):
    """Apply one approved staged record to a canonical table.

    Safety properties:
    - target table must be allow-listed
    - record must already be approved
    - payload must be a JSON object
    - upsert is used only when all configured conflict keys exist
    - failed canonical writes do not mark the staged record as applied
    """
    if row.get("review_status")!="approved":
        raise ValueError("Record must be approved before apply.")

    table=str(row.get("target_table") or "").strip()
    if table not in AI_ALLOWED_TABLES:
        raise ValueError(f"Target table is not allowed for canonical apply: {table}")

    payload=edited_payload if edited_payload is not None else row.get("payload")
    if not isinstance(payload,dict) or not payload:
        raise ValueError("Canonical payload must be a non-empty JSON object.")

    payload=_jsonable(payload)

    # Extension records such as logistics/energy/industrial rows require a canonical
    # pc_assets parent. Create or link that parent automatically when asset_id is absent.
    payload,parent_created=_ensure_parent_asset(sb,row,payload)

    conflict=APPLY_CONFLICT_KEYS.get(table)
    keys=[x.strip() for x in conflict.split(",")] if conflict else []
    can_upsert=bool(keys) and all(payload.get(k) not in (None,"") for k in keys)

    # Store the analyst-edited payload back into staging before canonical apply,
    # so the reviewed proposal and the applied proposal remain identical.
    if edited_payload is not None:
        sb.table("pc_staged_records").update({"payload":payload}).eq(
            "staged_record_id",row["staged_record_id"]
        ).execute()

    if can_upsert:
        result=sb.table(table).upsert(payload,on_conflict=conflict).execute()
        write_mode="upsert"
    else:
        result=sb.table(table).insert(payload).execute()
        write_mode="insert"

    # Only reached when canonical write succeeded.
    sb.table("pc_staged_records").update({
        "review_status":"applied",
        "validation_status":"validated",
    }).eq("staged_record_id",row["staged_record_id"]).execute()

    # Audit log is best-effort because some deployments may require a user id
    # under stricter auth. Failure here must not undo a successful canonical write.
    try:
        object_id=None
        for k in keys:
            if payload.get(k):
                object_id=str(payload[k])
                break
        sb.table("pc_audit_log").insert({
            "action":f"STAGED_{write_mode.upper()}",
            "object_type":table,
            "object_id":object_id or row.get("natural_key"),
            "after_data":payload,
        }).execute()
    except Exception:
        pass

    return result,write_mode

if page=="Dashboard":
    title("Platform control","One canonical data model; Trade, Intelligence and NERAI product entitlements; tenant workspaces; AI staging and review.")
    tables=[("Organizations","pc_organizations"),("Users","pc_profiles"),("Entities","pc_entities"),("Assets","pc_assets"),("Vessels / mobile","pc_mobile_assets"),("Events","pc_events"),("Staged changes","pc_staged_records"),("Open DQ issues","pc_data_quality_issues")]
    cols=st.columns(4)
    for i,(label,table) in enumerate(tables):
        with cols[i%4]: st.metric(label,count_rows(sb,table) if sb else 0)
    st.markdown("### Migration-night order")
    st.code("1 SQL 001 → 002 → 003\n2 seed_legacy_from_excel.py\n3 normalize_core.py\n4 SQL 004 → 005\n5 cleanup_validate.py\n6 verify_migration.py\n7 switch PC_DATA_BACKEND=supabase\n8 keep Excel fallback on until verified")

elif page=="Migration":
    title("Migration status")
    checks=[]
    for t in ["pc_legacy_sheet_rows","pc_sources","pc_entities","pc_assets","pc_mobile_assets","pc_relationships","pc_events","pc_event_locations","pc_event_links","pc_governance_links"]:
        checks.append({"Table":t,"Rows":count_rows(sb,t) if sb else 0})
    dataframe(checks)
    if sb:
        leakage=count_rows(sb,"pc_events",{"intelligence_visible":True,"event_nature":"CORPORATE"})
        if leakage: st.error(f"{leakage} corporate events are leaking into P&C Intelligence.")
        else: st.success("No corporate-event leakage detected in P&C Intelligence routing.")

elif page=="Organizations":
    title("Organizations & subscriptions","P&C controls seat limits and product entitlements centrally.")
    orgs=safe_rows(sb,"pc_organizations","*",500) if sb else []
    dataframe(orgs)
    if sb:
        with st.expander("Create organization"):
            with st.form("new_org"):
                name=st.text_input("Organization name")
                slug=st.text_input("Slug")
                seats=st.number_input("Seat limit",min_value=1,value=5)
                if st.form_submit_button("Create") and name and slug:
                    sb.table("pc_organizations").insert({"name":name,"slug":slug,"seat_limit":int(seats)}).execute(); st.rerun()
        if orgs:
            labels={o['organization_id']:o['name'] for o in orgs}
            oid=st.selectbox("Manage organization",list(labels),format_func=lambda x:labels[x])
            org=next(o for o in orgs if o['organization_id']==oid)
            c1,c2=st.columns(2)
            with c1:
                seats=st.number_input("Seat limit",min_value=1,value=int(org.get('seat_limit') or 5),key="seat_edit")
                if st.button("Update seat limit"):
                    sb.table("pc_organizations").update({"seat_limit":int(seats)}).eq("organization_id",oid).execute(); st.rerun()
            with c2:
                ents=safe_rows(sb,"pc_organization_entitlements","*",100,{"organization_id":oid})
                dataframe(ents)
                product=st.selectbox("Product",["TRADE","INTELLIGENCE","NERAI"])
                tier=st.selectbox("Tier",["base","professional","enterprise","add-on"])
                active=st.checkbox("Active",True)
                if st.button("Set entitlement"):
                    sb.table("pc_organization_entitlements").upsert({"organization_id":oid,"product_code":product,"tier":tier,"active":active},on_conflict="organization_id,product_code").execute(); st.rerun()

elif page=="Users & Access":
    title("Users & access","P&C super-admin view across organizations, roles and product access.")
    profiles=safe_rows(sb,"pc_profiles","user_id,email,display_name,global_role,active",1000) if sb else []
    members=safe_rows(sb,"pc_organization_members","organization_id,user_id,role,active,joined_at",2000) if sb else []
    st.markdown("### Profiles"); dataframe(profiles)
    st.markdown("### Organization memberships"); dataframe(members)
    if sb and profiles:
        orgs=safe_rows(sb,"pc_organizations","organization_id,name,seat_limit",500)
        pmap={p['user_id']:(p.get('email') or p['user_id']) for p in profiles}; omap={o['organization_id']:o['name'] for o in orgs}
        with st.expander("Assign existing user to organization"):
            uid=st.selectbox("User",list(pmap),format_func=lambda x:pmap[x])
            oid=st.selectbox("Organization",list(omap),format_func=lambda x:omap[x])
            role=st.selectbox("Role",["org_admin","senior_analyst","analyst","executive","viewer"])
            if st.button("Assign / update role"):
                current=count_rows(sb,"pc_organization_members",{"organization_id":oid,"active":True})
                lim=next((int(o.get('seat_limit') or 0) for o in orgs if o['organization_id']==oid),0)
                exists=any(m['organization_id']==oid and m['user_id']==uid for m in members)
                if not exists and lim and current>=lim: st.error("Seat limit reached.")
                else:
                    sb.table("pc_organization_members").upsert({"organization_id":oid,"user_id":uid,"role":role,"active":True},on_conflict="organization_id,user_id").execute(); st.rerun()

elif page=="Research Jobs":
    title(
        "AI research & enrichment",
        "Launch controlled research from the interface. AI proposals are staged for analyst review and never write directly to canonical tables."
    )

    if not sb:
        st.error("Supabase service connection required.")
    else:
        jobs=safe_rows(
            sb,
            "pc_ingestion_jobs",
            "ingestion_job_id,job_type,title,query_text,status,stats,error_text,created_at,started_at,completed_at",
            200,
            order="created_at"
        )
        st.markdown("### Recent research jobs")
        dataframe(jobs[:50])

        st.markdown("### Launch research")
        campaign=st.selectbox("Campaign",list(AI_CAMPAIGNS))
        seed_prompt=AI_CAMPAIGNS[campaign]

        prompt=st.text_area(
            "Research query",
            value=seed_prompt,
            placeholder="Describe exactly what you want the AI researcher to find, verify and stage.",
            height=180
        )
        c1,c2,c3=st.columns(3)
        with c1:
            context=st.selectbox("Product context",["TRADE","INTELLIGENCE"],index=0)
        with c2:
            use_web=st.checkbox("Use current web research",True)
        with c3:
            st.metric("Pending staged",count_rows(sb,"pc_staged_records",{"review_status":"pending"}))

        st.caption(
            "The AI researcher must provide source URLs and confidence. "
            "All output goes to pc_staged_records for review before canonical apply."
        )

        if st.button("Run AI research job",type="primary",disabled=not bool(prompt.strip())):
            if not ai_configured():
                st.error("Configure OPENAI_API_KEY and OPENAI_MODEL.")
            else:
                job=sb.table("pc_ingestion_jobs").insert({
                    "job_type":"AI_RESEARCH",
                    "title":campaign if campaign!="Custom research" else prompt[:100],
                    "query_text":prompt,
                    "source_scope":{"product":context,"web_search":use_web,"campaign":campaign},
                    "status":"running",
                }).execute().data[0]

                job_id=job["ingestion_job_id"]

                try:
                    with st.status("Running AI research...",expanded=True) as status:
                        st.write("Sending research brief to OpenAI...")
                        result=ai_research(
                            prompt,
                            context,
                            use_web,
                            output_contract=AI_OUTPUT_CONTRACT
                        )

                        st.write("Research returned. Validating structured proposals...")
                        staged,rejected=stage_ai_result(sb,job_id,result)

                        # If the model returned raw/unstructured output, preserve it
                        # as a research bundle rather than losing the result.
                        if staged==0 and result:
                            sb.table("pc_staged_records").insert({
                                "ingestion_job_id":job_id,
                                "target_table":"research_bundle",
                                "natural_key":str(job_id),
                                "action":"REVIEW",
                                "payload":result,
                                "confidence":0.5,
                                "validation_status":"needs_structuring",
                                "review_status":"pending",
                            }).execute()
                            staged=1

                        sb.table("pc_ingestion_jobs").update({
                            "status":"completed",
                            "stats":{
                                "staged_records":staged,
                                "discarded_invalid_records":rejected,
                                "campaign":campaign,
                                "product":context,
                            }
                        }).eq("ingestion_job_id",job_id).execute()

                        status.update(
                            label=f"Research complete — {staged} staged record(s)",
                            state="complete",
                            expanded=False
                        )

                    st.success(f"Research complete. {staged} proposal(s) sent to Review Queue.")
                    st.rerun()

                except Exception as exc:
                    sb.table("pc_ingestion_jobs").update({
                        "status":"failed",
                        "error_text":str(exc)
                    }).eq("ingestion_job_id",job_id).execute()
                    st.error(str(exc))

elif page=="Trade System Builder":
    title("Trade system builder","Build the global trade-system graph in controlled research campaigns: energy, industrial assets, flows, markets, ports, corridors and macro layers.")
    if not sb:
        st.info("Configure Supabase before running builder operations.")
    else:
        tables=[
            ("Energy assets","pc_energy_assets"),("Industrial assets","pc_industrial_assets"),("Logistics facilities","pc_logistics_facilities"),
            ("Market instruments","pc_market_instruments"),("Market prices","pc_market_prices"),("Trade flows","pc_trade_flows"),
            ("Supply series","pc_supply_series"),("Port metrics","pc_port_metrics"),("Transport routes","pc_transport_routes"),
            ("Chokepoints","pc_chokepoints"),("Macro indicators","pc_macro_indicators"),("Provenance observations","pc_observations")
        ]
        cols=st.columns(4)
        for i,(label,table) in enumerate(tables):
            with cols[i%4]: st.metric(label,count_rows(sb,table))
        tabs=st.tabs(["Research campaigns","Current normalization","Source registry","Build order"])
        with tabs[0]:
            st.markdown("### One-command research campaigns")
            examples=[
                "Research all African ports and create proposed port, terminal, governance, rail, road, free-zone and major commodity-flow records with authoritative sources.",
                "Research all refineries in the GCC and Red Sea region. Link owners, operators, capacities, products, ports, terminals, pipelines, storage and relevant market benchmarks.",
                "Research Brookfield, OMERS and Macquarie transport and logistics investments from 2016 to present. Stage acquisitions, stakes, assets, values and ownership/control relationships.",
                "Research major global mines and export chains for iron ore, bauxite, copper, nickel, cobalt, lithium, manganese, phosphate and potash. Link mine to rail, port and destination markets.",
                "Research all major port-linked logistics parks, free zones and inland terminals in Africa and the Gulf. Stage operator, owner, capacity and connectivity relationships."
            ]
            for e in examples: st.code(e)
            st.caption("Use Research Jobs to run these through the AI staging workflow. Nothing is written directly to canonical production tables.")
        with tabs[1]:
            st.markdown("### Normalize the data we already have")
            st.code("python scripts/normalize_trade_expansion.py")
            st.caption("This conservatively maps existing infrastructure, logistics-real-estate, company-listing and rail-network records into the expanded schema without inventing missing fields.")
        with tabs[2]:
            st.markdown("### Seed the open-source registry")
            st.code("python scripts/seed_open_source_registry.py")
            dataframe(safe_rows(sb,"pc_sources","source_id,publisher,source_name,source_type,coverage,url,license_name,redistribution_status,attribution_required,active",500,order="updated_at"))
        with tabs[3]:
            st.code("""1. Run sql/009_trade_system_expansion.sql
2. python scripts/seed_open_source_registry.py
3. python scripts/seed_market_instruments.py
4. python scripts/normalize_trade_expansion.py
5. Optional: python scripts/ingest_world_bank_macro.py --start 2016
6. Optional: python scripts/stage_ourairports.py
7. Run source-specific research/ingestion jobs
8. Review staged enrichments
9. Approve canonical writes
10. Verify client views""")

elif page=="Batch Staging":
    title(
        "Batch staging",
        "Upload structured CSV/JSON into the controlled staging queue. Known JSON fields are normalized before review."
    )

    target=st.selectbox(
        "Target table",
        [
            "pc_entities","pc_assets","pc_mobile_assets","pc_relationships","pc_events",
            "pc_transactions","pc_security_compliance","pc_energy_assets",
            "pc_industrial_assets","pc_logistics_facilities","pc_market_instruments",
            "pc_market_prices","pc_trade_flows","pc_supply_series","pc_port_metrics",
            "pc_port_capabilities","pc_transport_routes","pc_chokepoints",
            "pc_macro_indicators","pc_observations","pc_market_reports",
            "pc_market_observations"
        ]
    )

    up=st.file_uploader("CSV or JSON",type=["csv","json"])

    def _parse_jsonish(v):
        if isinstance(v,(dict,list)) or v is None:
            return v
        s=str(v).strip()
        if not s:
            return None
        if (s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]")):
            try:
                return json.loads(s)
            except Exception:
                return v
        return v

    def _clean_scalar(v):
        if v is None:
            return None
        if isinstance(v,float) and pd.isna(v):
            return None
        s=str(v).strip()
        return None if s=="" or s.lower()=="nan" else v

    def _normalize_incoming_row(r,target_table):
        row={k:_clean_scalar(v) for k,v in dict(r).items()}

        # JSONB-like fields commonly used by the canonical model.
        for col in ("raw_value","derived_value","metadata","source_scope","stats","payload","current_record"):
            if col in row:
                row[col]=_parse_jsonish(row[col])

        # Normalize booleans from CSV.
        for col in ("attribution_required","active"):
            if col in row and row[col] is not None and not isinstance(row[col],bool):
                row[col]=str(row[col]).strip().lower() in {"1","true","yes","y"}

        # ReCAAP observation convenience mapping.
        if target_table=="pc_observations":
            src_name=str(row.get("source_name") or "").lower()
            src_url=str(row.get("source_url") or "").lower()
            if "recaap" in src_name or "recaap" in src_url:
                row["source_id"]=row.get("source_id") or "SRC_OPEN_RECAAP_ISC"
                row["source_name"]=row.get("source_name") or "ReCAAP Information Sharing Centre"
                row["source_type"]=row.get("source_type") or "official_maritime_security"
                row["redistribution_status"]=row.get("redistribution_status") or "attribution_required"
                row["attribution_required"]=True

        return {k:v for k,v in row.items() if v is not None}

    def _natural_key_for_row(r,target_table,index):
        if target_table=="pc_observations":
            raw=r.get("raw_value")
            meta=r.get("metadata")
            if isinstance(raw,dict):
                for k in ("observation_id","source_record_id","canonical_event_id"):
                    if raw.get(k):
                        return str(raw[k])
            if isinstance(meta,dict):
                for k in ("source_record_id","legacy_observation_id"):
                    if meta.get(k):
                        return str(meta[k])

        for key in (
            "entity_id","asset_id","mobile_asset_id","relationship_id","event_id",
            "transaction_id","route_id","chokepoint_id","market_instrument_id",
            "trade_flow_id","supply_series_id","observation_id","name","title"
        ):
            if r.get(key):
                return str(r[key])

        return str(index)

    if up:
        try:
            if up.name.lower().endswith(".csv"):
                incoming=pd.read_csv(up,dtype=object)
                rows=incoming.to_dict("records")
            else:
                obj=json.load(up)
                rows=obj if isinstance(obj,list) else obj.get("records",[obj])

            rows=[_normalize_incoming_row(r,target) for r in rows]

            st.caption(f"{len(rows):,} incoming rows")
            preview=pd.DataFrame(rows[:50])
            st.dataframe(preview,use_container_width=True,hide_index=True)

            # Helpful ReCAAP summary.
            if target=="pc_observations" and rows:
                recaap_count=sum(
                    1 for r in rows
                    if r.get("source_id")=="SRC_OPEN_RECAAP_ISC"
                )
                if recaap_count:
                    st.info(
                        f"Recognized {recaap_count:,} ReCAAP observation row(s). "
                        "JSON fields will be stored as objects and source_id will be normalized."
                    )

            if st.button("Stage batch",type="primary"):
                if not sb:
                    st.error("Supabase required.")
                else:
                    # Ensure canonical ReCAAP source exists if this is a ReCAAP batch.
                    if target=="pc_observations" and any(
                        r.get("source_id")=="SRC_OPEN_RECAAP_ISC" for r in rows
                    ):
                        sb.table("pc_sources").upsert({
                            "source_id":"SRC_OPEN_RECAAP_ISC",
                            "publisher":"ReCAAP Information Sharing Centre",
                            "source_name":"ReCAAP ISC",
                            "source_type":"official_maritime_security",
                            "coverage":"Piracy and armed robbery against ships in Asia-Pacific waters",
                            "url":"https://www.recaap.org/alerts",
                            "reliability":"high",
                            "ingestion_method":"curated structured import",
                            "redistribution_status":"attribution_required",
                            "attribution_required":True,
                            "active":True,
                            "notes":"Canonical source record for ReCAAP ISC structured observations."
                        },on_conflict="source_id").execute()

                    job=sb.table("pc_ingestion_jobs").insert({
                        "job_type":"BATCH_IMPORT",
                        "title":up.name,
                        "source_scope":{"target_table":target,"rows":len(rows)},
                        "status":"running"
                    }).execute().data[0]

                    payloads=[]
                    for i,r in enumerate(rows,1):
                        payloads.append({
                            "ingestion_job_id":job["ingestion_job_id"],
                            "target_table":target,
                            "natural_key":_natural_key_for_row(r,target,i),
                            "action":"REVIEW",
                            "payload":r,
                            "confidence":1.0,
                            "validation_status":"pending",
                            "review_status":"pending"
                        })

                    total_batches=max(1,(len(payloads)+249)//250)
                    progress=st.progress(0.0,text="Staging batch...")
                    for batch_no,i in enumerate(range(0,len(payloads),250),start=1):
                        sb.table("pc_staged_records").insert(payloads[i:i+250]).execute()
                        progress.progress(
                            batch_no/total_batches,
                            text=f"Staging batch {batch_no}/{total_batches}"
                        )

                    sb.table("pc_ingestion_jobs").update({
                        "status":"completed",
                        "stats":{"rows":len(rows),"target_table":target}
                    }).eq("ingestion_job_id",job["ingestion_job_id"]).execute()

                    progress.progress(1.0,text="Batch staged.")
                    st.success(
                        f"Staged {len(rows):,} row(s). Go to Review Queue → Bulk review."
                    )

        except Exception as exc:
            st.exception(exc)

elif page=="Review Queue":
    title(
        "Review & apply queue",
        "Bulk-review safe records; route ambiguous records to manual review. JSON is available only when you need to edit it."
    )

    if not sb:
        st.error("Supabase is required for review and apply.")
    else:
        tabs=st.tabs(["Bulk review","Manual review","Approved — apply","History"])

        # ---------------------------------------------------------------
        # BULK REVIEW
        # ---------------------------------------------------------------
        with tabs[0]:
            pending=safe_rows(
                sb,
                "pc_staged_records",
                "staged_record_id,ingestion_job_id,target_table,natural_key,action,confidence,validation_status,review_status,payload,current_record,source_id,created_at",
                500,
                {"review_status":"pending"},
                "created_at"
            )

            if not pending:
                st.success("No pending records.")
            else:
                st.markdown("### Automated validation")
                st.caption(
                    "Safe = confidence ≥ 0.90, source-backed, valid FKs, no exact duplicate, and a configured apply key. "
                    "For logistics/energy/industrial extensions, a missing asset_id is resolved automatically by creating or linking the parent canonical asset."
                )

                validated=[]
                with st.spinner("Validating staged records..."):
                    for r in pending:
                        v=validate_staged_for_bulk(sb,r)
                        validated.append({
                            "Apply?": bool(v["safe"]),
                            "Record": r.get("natural_key"),
                            "Table": r.get("target_table"),
                            "Confidence": round(v["confidence"],2),
                            "Sources": v["sources"],
                            "Schema": "✓" if v["schema_ok"] else "✗",
                            "FKs": "✓" if v["fk_ok"] else "✗",
                            "Duplicate": "Yes" if v["duplicate"] else "No",
                            "Parent": "Create/link" if v.get("parent_needed") else "Ready",
                            "Risk": v["risk"],
                            "_id": r.get("staged_record_id"),
                            "_row": r,
                            "_safe": v["safe"],
                        })

                safe_count=sum(1 for x in validated if x["_safe"])
                st.info(f"{safe_count} of {len(validated)} record(s) currently qualify as bulk-safe.")

                edit_df=pd.DataFrame(validated)
                visible_cols=["Apply?","Record","Table","Confidence","Sources","Schema","FKs","Duplicate","Parent","Risk"]

                edited=st.data_editor(
                    edit_df[visible_cols],
                    use_container_width=True,
                    hide_index=True,
                    disabled=[c for c in visible_cols if c!="Apply?"],
                    column_config={
                        "Apply?": st.column_config.CheckboxColumn(
                            "Apply?",
                            help="Select records to approve/apply."
                        ),
                        "Confidence": st.column_config.NumberColumn(format="%.2f"),
                    },
                    key="bulk_review_editor"
                )

                # Restore IDs by row order
                selected_idx=[i for i,v in enumerate(edited["Apply?"].tolist()) if bool(v)]
                selected=[validated[i] for i in selected_idx]

                unsafe_selected=[x for x in selected if not x["_safe"]]
                if unsafe_selected:
                    st.warning(
                        f"{len(unsafe_selected)} selected record(s) are not classified as bulk-safe. "
                        "They will not be bulk-applied; use Manual review."
                    )

                c1,c2,c3=st.columns(3)

                if c1.button("Approve selected safe",type="primary",disabled=not selected):
                    approved=0
                    skipped=0
                    for x in selected:
                        if not x["_safe"]:
                            skipped+=1
                            continue
                        sb.table("pc_staged_records").update({
                            "review_status":"approved",
                            "validation_status":"validated"
                        }).eq("staged_record_id",x["_id"]).execute()
                        approved+=1
                    st.success(f"Approved {approved} safe record(s). Skipped {skipped}.")
                    st.rerun()

                if c2.button("Approve + apply selected safe",disabled=not selected):
                    applied=0
                    failures=[]
                    for x in selected:
                        if not x["_safe"]:
                            continue
                        row=x["_row"]
                        try:
                            sb.table("pc_staged_records").update({
                                "review_status":"approved",
                                "validation_status":"validated"
                            }).eq("staged_record_id",x["_id"]).execute()
                            row["review_status"]="approved"
                            apply_staged_record(sb,row,row.get("payload") or {})
                            applied+=1
                        except Exception as exc:
                            failures.append(f"{row.get('natural_key')}: {exc}")
                    if applied:
                        st.success(f"Approved and applied {applied} safe record(s).")
                    if failures:
                        st.error(f"{len(failures)} record(s) failed and remain reviewable.")
                        with st.expander("Failure details"):
                            for f in failures: st.write(f)
                    st.rerun()

                if c3.button("Select all safe"):
                    st.info("All currently safe records are already pre-selected in the table above.")

                with st.expander("Bulk policy"):
                    st.code(
                        "confidence >= 0.90\n"
                        "source URLs >= 1\n"
                        "required schema fields present\n"
                        "foreign keys resolve\n"
                        "no exact duplicate\n"
                        "configured canonical apply key"
                    )

        # ---------------------------------------------------------------
        # MANUAL REVIEW
        # ---------------------------------------------------------------
        with tabs[1]:
            rows=safe_rows(
                sb,
                "pc_staged_records",
                "staged_record_id,ingestion_job_id,target_table,natural_key,action,confidence,validation_status,review_status,payload,current_record,source_id,created_at",
                500,
                {"review_status":"pending"},
                "created_at"
            )

            if not rows:
                st.success("No pending staged records.")
            else:
                def _label(r):
                    try: conf=f"{float(r.get('confidence')):.2f}"
                    except Exception: conf="n/a"
                    return f"{r.get('target_table')} | {r.get('natural_key')} | {conf}"

                labels=[_label(r) for r in rows]
                chosen=st.selectbox("Record",labels,key="manual_record")
                row=rows[labels.index(chosen)]
                payload=row.get("payload") or {}
                v=validate_staged_for_bulk(sb,row)

                st.markdown(f"### {row.get('natural_key') or 'Staged record'}")
                m1,m2,m3,m4,m5=st.columns(5)
                m1.metric("Confidence",f"{v['confidence']:.2f}")
                m2.metric("Sources",v["sources"])
                m3.metric("Schema","✓" if v["schema_ok"] else "✗")
                m4.metric("FKs","✓" if v["fk_ok"] else "✗")
                m5.metric("Duplicate","Yes" if v["duplicate"] else "No")

                if v["safe"]:
                    st.success("This record meets the current bulk-safe policy.")
                else:
                    st.warning(v["risk"])

                # Human-readable card
                if isinstance(payload,dict):
                    card_rows=[]
                    for k,vv in payload.items():
                        if k=="metadata": continue
                        if isinstance(vv,(dict,list)):
                            vv=json.dumps(vv,ensure_ascii=False)
                        card_rows.append({"Field":k.replace("_"," ").title(),"Value":vv})
                    st.dataframe(pd.DataFrame(card_rows),use_container_width=True,hide_index=True)

                    meta=payload.get("metadata") or {}
                    sources=[]
                    if isinstance(meta,dict):
                        sources.extend(meta.get("research_sources") or [])
                        sources.extend(meta.get("sources") or [])
                    sources.extend(payload.get("sources") or [])

                    if sources:
                        st.markdown("#### Sources")
                        for i,s in enumerate(sources,1):
                            if isinstance(s,dict) and (s.get("url") or s.get("source_url")):
                                url=s.get("url") or s.get("source_url")
                                label=s.get("title") or s.get("publisher") or f"Source {i}"
                                st.markdown(f"{i}. [{label}]({url})")

                with st.expander("Advanced: view/edit JSON"):
                    raw=json.dumps(payload,ensure_ascii=False,indent=2)
                    edited=st.text_area(
                        "Payload JSON",
                        value=raw,
                        height=360,
                        key=f"manual_json_{row['staged_record_id']}"
                    )
                    try:
                        edited_payload=json.loads(edited)
                    except Exception as exc:
                        edited_payload=None
                        st.error(f"Invalid JSON: {exc}")

                note=st.text_area(
                    "Reviewer note",
                    key=f"manual_note_{row['staged_record_id']}"
                )
                c1,c2,c3=st.columns(3)

                if c1.button("Approve",type="primary",key=f"m_approve_{row['staged_record_id']}"):
                    update={"review_status":"approved","validation_status":"reviewed"}
                    if edited_payload is not None:
                        update["payload"]=edited_payload
                    sb.table("pc_staged_records").update(update).eq(
                        "staged_record_id",row["staged_record_id"]
                    ).execute()
                    st.rerun()

                if c2.button("Needs changes",key=f"m_changes_{row['staged_record_id']}"):
                    update={"review_status":"needs_changes"}
                    if edited_payload is not None:
                        update["payload"]=edited_payload
                    sb.table("pc_staged_records").update(update).eq(
                        "staged_record_id",row["staged_record_id"]
                    ).execute()
                    st.rerun()

                if c3.button("Reject",key=f"m_reject_{row['staged_record_id']}"):
                    sb.table("pc_staged_records").update({
                        "review_status":"rejected"
                    }).eq("staged_record_id",row["staged_record_id"]).execute()
                    st.rerun()

        # ---------------------------------------------------------------
        # APPROVED APPLY
        # ---------------------------------------------------------------
        with tabs[2]:
            approved=safe_rows(
                sb,
                "pc_staged_records",
                "staged_record_id,ingestion_job_id,target_table,natural_key,action,confidence,validation_status,review_status,payload,current_record,source_id,created_at",
                500,
                {"review_status":"approved"},
                "created_at"
            )

            if not approved:
                st.info("No approved records waiting for apply.")
            else:
                st.caption(f"{len(approved)} approved record(s) waiting.")

                rows=[]
                for r in approved:
                    v=validate_staged_for_bulk(sb,r)
                    rows.append({
                        "Apply?":bool(v["safe"]),
                        "Record":r.get("natural_key"),
                        "Table":r.get("target_table"),
                        "Confidence":round(v["confidence"],2),
                        "Sources":v["sources"],
                        "Schema":"✓" if v["schema_ok"] else "✗",
                        "FKs":"✓" if v["fk_ok"] else "✗",
                        "Duplicate":"Yes" if v["duplicate"] else "No",
                        "Parent":"Create/link" if v.get("parent_needed") else "Ready",
                        "Risk":v["risk"],
                        "_row":r,
                        "_safe":v["safe"],
                    })

                frame=pd.DataFrame(rows)
                cols=["Apply?","Record","Table","Confidence","Sources","Schema","FKs","Duplicate","Parent","Risk"]
                edited=st.data_editor(
                    frame[cols],
                    use_container_width=True,
                    hide_index=True,
                    disabled=[c for c in cols if c!="Apply?"],
                    key="approved_apply_editor"
                )

                selected=[rows[i] for i,x in enumerate(edited["Apply?"].tolist()) if bool(x)]

                if st.button("Apply selected safe records",type="primary",disabled=not selected):
                    applied=0
                    failed=[]
                    for x in selected:
                        if not x["_safe"]:
                            continue
                        try:
                            apply_staged_record(sb,x["_row"],x["_row"].get("payload") or {})
                            applied+=1
                        except Exception as exc:
                            failed.append(f"{x['_row'].get('natural_key')}: {exc}")
                    st.success(f"Applied {applied} record(s).")
                    if failed:
                        st.error(f"{len(failed)} failed.")
                        with st.expander("Failure details"):
                            for f in failed: st.write(f)
                    st.rerun()

                st.markdown("### Single-record advanced apply")
                labels=[f"{r.get('target_table')} | {r.get('natural_key')}" for r in approved]
                chosen=st.selectbox("Approved record",labels,key="single_approved")
                row=approved[labels.index(chosen)]
                with st.expander("Edit canonical JSON before apply"):
                    edited_json=st.text_area(
                        "Canonical JSON",
                        value=json.dumps(row.get("payload") or {},ensure_ascii=False,indent=2),
                        height=360,
                        key=f"approved_json_{row['staged_record_id']}"
                    )
                    try:
                        edited_payload=json.loads(edited_json)
                    except Exception as exc:
                        edited_payload=None
                        st.error(str(exc))
                    confirm=st.checkbox(
                        "I authorize this canonical write.",
                        key=f"confirm_{row['staged_record_id']}"
                    )
                    if st.button(
                        "Apply this record",
                        disabled=not (confirm and isinstance(edited_payload,dict)),
                        key=f"apply_one_{row['staged_record_id']}"
                    ):
                        try:
                            apply_staged_record(sb,row,edited_payload)
                            st.success("Applied.")
                            st.rerun()
                        except Exception as exc:
                            st.exception(exc)

        # ---------------------------------------------------------------
        # HISTORY
        # ---------------------------------------------------------------
        with tabs[3]:
            history=[]
            for status in ["applied","rejected","needs_changes"]:
                history.extend(
                    safe_rows(
                        sb,
                        "pc_staged_records",
                        "staged_record_id,target_table,natural_key,action,confidence,validation_status,review_status,created_at",
                        250,
                        {"review_status":status},
                        "created_at"
                    )
                )
            if history:
                history=sorted(history,key=lambda x:str(x.get("created_at") or ""),reverse=True)
                dataframe(history[:500])
            else:
                st.caption("No completed review history yet.")

elif page=="Market Data":
    title("Freight & commodity market data","Attributed public-source market observations, initially seeded from The Signal Group Weekly Market Monitor. Nothing is client-visible until approved.")
    if not sb:
        st.info("Configure Supabase to manage market data.")
    else:
        reports=safe_rows(sb,"pc_market_reports","market_report_id,provider,report_family,report_title,report_date,week_number,source_url,review_status,client_visible,ingested_at",500,order="report_date")
        obs=safe_rows(sb,"pc_market_observations","market_observation_id,market_report_id,observation_date,market,vessel_class,route_code,commodity,metric_family,metric_name,value_numeric,value_text,unit,currency,change_wow,change_yoy,pc_market_signal,pc_direction,confidence,review_status,client_visible",1000,order="observation_date")
        c1,c2,c3,c4=st.columns(4)
        c1.metric("Reports",len(reports)); c2.metric("Observations",len(obs))
        c3.metric("Pending review",sum(1 for r in obs if r.get("review_status")=="pending"))
        c4.metric("Client-visible",sum(1 for r in obs if r.get("client_visible")))
        tabs=st.tabs(["Reports","Observation review","Ingestion commands"])
        with tabs[0]:
            dataframe(reports)
        with tabs[1]:
            pending=[r for r in obs if r.get("review_status")=="pending"]
            dataframe(pending[:250])
            if pending:
                oid=st.selectbox("Open market observation",[r['market_observation_id'] for r in pending],format_func=lambda x: next((f"{r.get('observation_date','')} · {r.get('route_code') or r.get('vessel_class') or r.get('commodity') or r.get('market','')} · {r.get('metric_name','')}" for r in pending if r['market_observation_id']==x),x))
                row=next(r for r in pending if r['market_observation_id']==oid)
                st.json(row)
                c1,c2,c3=st.columns(3)
                if c1.button("Approve + publish to Trade"):
                    sb.table("pc_market_observations").update({"review_status":"approved","client_visible":True}).eq("market_observation_id",oid).execute()
                    sb.table("pc_market_reports").update({"review_status":"approved","client_visible":True}).eq("market_report_id",row['market_report_id']).execute(); st.rerun()
                if c2.button("Approve internal only"):
                    sb.table("pc_market_observations").update({"review_status":"approved","client_visible":False}).eq("market_observation_id",oid).execute(); st.rerun()
                if c3.button("Reject market observation"):
                    sb.table("pc_market_observations").update({"review_status":"rejected","client_visible":False}).eq("market_observation_id",oid).execute(); st.rerun()
        with tabs[2]:
            st.markdown("#### Initial attributed seed")
            st.code("python scripts/seed_market_sample.py")
            st.markdown("#### Research the 2026 dry-bulk + tanker archive")
            st.code("python scripts/ingest_signal_group.py --year 2026 --families dry,tanker --weeks 1-36")
            st.caption("The crawler uses only publicly accessible pages, stores attribution and structured facts rather than article copies, and leaves extracted observations pending until analyst approval.")

elif page=="Governance & Quality":
    title("Governance & data quality")
    tabs=st.tabs(["Port governance","Quality issues"])
    with tabs[0]:
        gov=safe_rows(sb,"pc_governance_links","*",500) if sb else []; dataframe(gov)
        if sb:
            st.markdown("#### Add governance link")
            with st.form("gov_link"):
                governed_id=st.text_input("Port / asset ID",placeholder="PORTG0225")
                authority=st.text_input("Authority entity ID",placeholder="COMP_BUSAN_PA")
                role=st.text_input("Governance role",value="PORT AUTHORITY")
                note=st.text_input("Model note")
                if st.form_submit_button("Add") and governed_id and authority:
                    sb.table("pc_governance_links").insert({"governed_type":"asset","governed_id":governed_id,"authority_entity_id":authority,"authority_name":authority,"governance_role":role,"model_note":note}).execute(); st.rerun()
    with tabs[1]:
        issues=safe_rows(sb,"pc_data_quality_issues","*",500,{"status":"open"},"created_at") if sb else []; dataframe(issues)
