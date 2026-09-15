from __future__ import annotations
from pathlib import Path
import os, sys, json, uuid, hashlib, re, io, zipfile, mimetypes
from datetime import date, datetime
from decimal import Decimal
import pandas as pd
import xml.etree.ElementTree as ET
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

st.set_page_config(page_title="P&C Canonical Admin",page_icon="◈",layout="wide",initial_sidebar_state="expanded")

# Match the Trade/Intelligence apps: dark by default, with a persistent light/dark toggle.
appearance = st.session_state.get("pc_admin_appearance", "Dark")

st.markdown("""
<style>
:root{--bg:#07111f;--panel:#0d1a2b;--panel2:#102238;--line:#28415f;--text:#f3f6fa;--muted:#b8c5d4;--gold:#d7b66a}
.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"]{background:var(--bg);color:var(--text)}
[data-testid="stSidebar"]{background:#091725!important;border-right:1px solid var(--line)!important}
h1,h2,h3,h4,h5,h6,p,label,li,span{color:var(--text)!important}
.pc-card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px;margin-bottom:10px}
.pc-k{color:var(--gold);font-size:.72rem;letter-spacing:.12em;text-transform:uppercase}
[data-baseweb="select"]>div,[data-baseweb="input"]>div,.stTextInput input{background:var(--panel)!important;color:var(--text)!important;border-color:var(--line)!important}
textarea,[data-baseweb="textarea"] textarea,[data-testid="stTextArea"] textarea{
  background:#f4f7fb!important;color:#111827!important;-webkit-text-fill-color:#111827!important;caret-color:#111827!important;
  font-family:Consolas,"SFMono-Regular",Menlo,Monaco,monospace!important;
}
[data-testid="stTextArea"]>div,[data-testid="stTextArea"] [data-baseweb="textarea"]{background:#f4f7fb!important}
.stButton>button,.stDownloadButton>button{background:var(--panel2)!important;color:var(--text)!important;border:1px solid var(--line)!important}
.stButton>button:hover,.stDownloadButton>button:hover{border-color:var(--gold)!important;color:#fff!important}
.stDataFrame{border:1px solid var(--line);border-radius:8px}
</style>""",unsafe_allow_html=True)

if appearance == "Light":
    st.markdown("""
    <style>
    :root{--bg:#f5f7fa;--panel:#ffffff;--panel2:#f0f3f7;--line:#cbd5e1;--text:#16202a;--muted:#5d6b7a;--gold:#9a7626}
    .stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"]{background:var(--bg)!important;color:var(--text)!important}
    [data-testid="stSidebar"]{background:#eef2f6!important;border-right:1px solid var(--line)!important}
    h1,h2,h3,h4,h5,h6,p,label,li,span{color:var(--text)!important}
    .pc-card{background:#ffffff!important;border-color:var(--line)!important}
    .pc-k{color:var(--gold)!important}
    [data-baseweb="select"]>div,[data-baseweb="input"]>div,.stTextInput input{background:#ffffff!important;color:#16202a!important;border-color:var(--line)!important}
    textarea,[data-baseweb="textarea"] textarea,[data-testid="stTextArea"] textarea{background:#ffffff!important;color:#111827!important;-webkit-text-fill-color:#111827!important}
    [data-testid="stTextArea"]>div,[data-testid="stTextArea"] [data-baseweb="textarea"]{background:#ffffff!important}
    .stButton>button,.stDownloadButton>button{background:#ffffff!important;color:#29465f!important;border-color:#b8c3cf!important}
    .stButton>button p,.stDownloadButton>button p{color:#29465f!important}
    .stDataFrame{border-color:#cbd5e1!important}
    [data-testid="stHeader"],[data-testid="stToolbar"]{background:#f5f7fa!important;color:#16202a!important}
    [data-testid="stHeader"] *,[data-testid="stToolbar"] *{color:#16202a!important}
    </style>
    """,unsafe_allow_html=True)

if os.getenv("PC_REQUIRE_AUTH","false").lower()=="true":
    ctx=require_super_admin()
else:
    ctx={"global_role":"super_admin","email":"migration-local"}

sb=service_client()
st.sidebar.markdown("<div class='pc-k'>Power & Corridors</div>",unsafe_allow_html=True)
st.sidebar.markdown("## Canonical Admin")
st.sidebar.caption("Resolve or create canonical objects first. Then write relationships and event links. Review only genuine ambiguity.")
st.sidebar.radio(
    "Appearance",
    ["Dark","Light"],
    horizontal=True,
    key="pc_admin_appearance",
)
NAV = {
    "Home": "Canonical Home",
    "Canonical Loader": "Canonical Loader",
    "Identity Hygiene": "Identity Hygiene",
    "Review Queue": "Canonical Review",
    "AI Research": "AI Research Workflow",
    "Documents": "Document Loader",
    "Email & Distribution": "Distribution Lists",
    "System": "Governance & Quality",
}
PAGES=list(NAV.keys())

# ---------------------------------------------------------------------------
# Bulk review / validation helpers
# ---------------------------------------------------------------------------

REQUIRED_BY_TABLE = {
    "pc_entities": ["entity_id","name","entity_type"],
    "pc_assets": ["asset_id","name","asset_type"],
    "pc_mobile_assets": ["mobile_asset_id","name","asset_type"],
    "pc_relationships": ["relationship_id","source_type","source_id","relationship_type","target_type","target_id"],
    "pc_events": ["event_id","event_type"],
    "pc_event_links": ["event_link_id","event_id","linked_type","linked_id","relationship"],
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
    "pc_event_links": [
        ("event_id","pc_events","event_id"),
    ],
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
    """Count source URLs in the common payload shapes accepted by Batch Staging."""
    if not isinstance(payload,dict):
        return 0

    def _count_seq(seq):
        if not isinstance(seq,list):
            return 0
        n=0
        for s in seq:
            if isinstance(s,str) and s.strip().lower().startswith(("http://","https://")):
                n += 1
            elif isinstance(s,dict) and (s.get("url") or s.get("source_url")):
                n += 1
        return n

    count=0
    meta=payload.get("metadata") or {}
    if isinstance(meta,str):
        parsed=_jsonish(meta)
        meta=parsed if isinstance(parsed,dict) else {}
    if isinstance(meta,dict):
        count += _count_seq(meta.get("research_sources") or [])
        count += _count_seq(meta.get("sources") or [])
        if meta.get("source_url"):
            count += 1

    count += _count_seq(payload.get("sources") or [])
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

    # pc_event_links uses a polymorphic linked_id. Validate vessel links explicitly.
    if table=="pc_event_links" and str(payload.get("linked_type") or "").lower() in {"mobile_asset","vessel"}:
        value=payload.get("linked_id")
        if value not in (None,""):
            try:
                hit=(sb.table("pc_mobile_assets").select("mobile_asset_id").eq(
                    "mobile_asset_id",value
                ).limit(1).execute().data or [])
                if not hit:
                    problems.append("linked_id→pc_mobile_assets.mobile_asset_id missing")
            except Exception:
                problems.append("linked_id vessel FK check failed")
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

    # A staged record can be source-backed through its own source_id. For
    # relational event links, the canonical parent event source also counts
    # as provenance; a separate URL on every link is not required.
    if sources < 1 and row.get("source_id") not in (None, ""):
        sources = 1
    if sources < 1 and table == "pc_event_links" and payload.get("event_id"):
        try:
            parent = (sb.table("pc_events")
                      .select("source_id")
                      .eq("event_id", payload["event_id"])
                      .limit(1).execute().data or [])
            if parent and parent[0].get("source_id") not in (None, ""):
                sources = 1
        except Exception:
            pass

    relationship_ok=True
    relationship_status=str(row.get("resolution_status") or "").upper()
    if table=="pc_event_links":
        relationship_ok=relationship_status=="READY"

    # Canonical identity rows must have been through metadata resolution. NEW means
    # no canonical match was found; MATCHED means the database supplied the existing
    # canonical ID for an enrichment/update. An exact duplicate is expected for MATCHED.
    resolution_status=str(row.get("resolution_status") or "UNRESOLVED").upper()
    identity_table=table in {"pc_entities","pc_assets","pc_mobile_assets","pc_events"}
    identity_resolution_ok=(not identity_table) or resolution_status in {"NEW","MATCHED"}
    if identity_table and resolution_status=="MATCHED" and row.get("resolved_entity_id"):
        duplicate=False
        dup_reason="matched canonical identity"

    safe=(
        confidence >= 0.90
        and schema_ok
        and fk_ok
        and not duplicate
        and sources >= 1
        and table in APPLY_CONFLICT_KEYS
        and relationship_ok
        and identity_resolution_ok
    )

    risk=[]
    if confidence < 0.90: risk.append("confidence<0.90")
    if not schema_ok: risk.append("missing:"+",".join(missing))
    if not fk_ok: risk.extend(fk_problems)
    if duplicate: risk.append("duplicate:"+dup_reason)
    if sources < 1: risk.append("no source URL")
    if table not in APPLY_CONFLICT_KEYS: risk.append("no configured apply key")
    if table=="pc_event_links" and not relationship_ok: risk.append("relationship:"+(relationship_status or "UNRESOLVED"))
    if identity_table and not identity_resolution_ok: risk.append("identity-resolution:"+resolution_status)
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


def _set_action_feedback(kind, message, details=None):
    st.session_state["_pc_action_feedback"] = {
        "kind": kind,
        "message": message,
        "details": details or [],
    }

def _show_action_feedback():
    fb = st.session_state.get("_pc_action_feedback")
    if not fb:
        return
    kind = fb.get("kind","info")
    msg = fb.get("message","")
    if kind=="success":
        st.success(msg)
    elif kind=="error":
        st.error(msg)
    elif kind=="warning":
        st.warning(msg)
    else:
        st.info(msg)
    details = fb.get("details") or []
    if details:
        with st.expander("Operation details", expanded=(kind!="success")):
            for item in details:
                st.write(item)


# ---------------------------------------------------------------------------
# ReCAAP observation -> canonical security event promotion
# ---------------------------------------------------------------------------

def _recaap_obs_identity(obs):
    raw = obs.get("raw_value") or {}
    meta = obs.get("metadata") or {}
    for key in ("source_record_id","observation_id","canonical_event_id"):
        if isinstance(raw,dict) and raw.get(key):
            return str(raw[key])
    for key in ("source_record_id","legacy_observation_id"):
        if isinstance(meta,dict) and meta.get(key):
            return str(meta[key])
    return str(obs.get("observation_id") or uuid.uuid4())


def _recaap_event_id(obs):
    ident = _recaap_obs_identity(obs)
    digest = hashlib.sha1(ident.encode("utf-8")).hexdigest()[:16].upper()
    return f"EVT_RECAAP_{digest}"


def _recaap_location_id(event_id):
    return f"LOC_{event_id}"


def _recaap_event_payload(obs):
    raw = obs.get("raw_value") or {}
    der = obs.get("derived_value") or {}
    meta = obs.get("metadata") or {}

    if not isinstance(raw,dict): raw={}
    if not isinstance(der,dict): der={}
    if not isinstance(meta,dict): meta={}

    event_id = _recaap_event_id(obs)
    vessel = (
        der.get("vessel_name")
        or raw.get("subject_name")
        or meta.get("vessel_name")
        or "Unknown vessel"
    )
    source_type = str(raw.get("event_type") or der.get("event_type") or "").strip().lower()
    is_attempt = "attempt" in source_type or str(der.get("event_type") or "").lower().startswith("attempted")

    event_type = "Attempted Piracy / Armed Robbery" if is_attempt else "Piracy / Armed Robbery"
    location = der.get("location_name") or raw.get("location") or meta.get("location")
    country = der.get("country") or raw.get("country") or meta.get("country_inferred_for_display")
    display_region = der.get("display_region") or meta.get("display_region") or raw.get("region_theatre")

    desc = raw.get("description") or ""
    outcome = raw.get("outcome_damage")
    if outcome:
        desc = (desc + " Outcome: " + str(outcome)).strip()

    title = f"ReCAAP: {event_type} — {vessel}"
    start_date = obs.get("observation_date") or raw.get("date")

    event = {
        "event_id": event_id,
        "start_date": start_date,
        "event_nature": "SECURITY",
        "event_domain": "maritime",
        "event_family": "Maritime Crime",
        "event_type": event_type,
        "severity": raw.get("severity"),
        "status": "Recorded",
        "mode": "Maritime",
        "countries": country,
        "location": location,
        "title": title,
        "description": desc or None,
        "operational_impact": raw.get("operational_impact"),
        "commercial_impact": raw.get("trade_impact"),
        "confidence": obs.get("confidence") or raw.get("confidence") or "high",
        "trade_relevance": 2,
        "intelligence_relevance": 4,
        "trade_visible": True,
        "intelligence_visible": True,
        "alert_worthy": False,
        "record_status": "verified" if obs.get("review_status")=="approved" else "provisional",
        "source_id": obs.get("source_id") or "SRC_OPEN_RECAAP_ISC",
        "metadata": {
            "source_dataset": raw.get("source_dataset") or meta.get("dataset") or "recaap_incidents_2024_2026",
            "source_record_id": raw.get("source_record_id") or meta.get("source_record_id"),
            "observation_id": obs.get("observation_id"),
            "recaap_category": der.get("recaap_category") or meta.get("recaap_category"),
            "display_region": display_region,
            "vessel_name": vessel,
            "asset_type": der.get("asset_type") or raw.get("asset_type"),
            "promoted_from_observation": True,
        },
    }
    event = {k:v for k,v in event.items() if v is not None}

    lat = der.get("latitude")
    lon = der.get("longitude")
    if lat is None: lat = raw.get("latitude")
    if lon is None: lon = raw.get("longitude")

    location_row = None
    if lat is not None and lon is not None:
        location_row = {
            "event_location_id": _recaap_location_id(event_id),
            "event_id": event_id,
            "location_name": location,
            "country": country,
            "latitude": lat,
            "longitude": lon,
            "accuracy": "ReCAAP reported coordinates",
            "notes": f"Promoted from pc_observations; dataset={event['metadata']['source_dataset']}",
        }
        location_row = {k:v for k,v in location_row.items() if v is not None}

    return event, location_row


def promote_recaap_observations(sb):
    """Promote approved ReCAAP observations into canonical pc_events / pc_event_locations.

    Idempotent: deterministic IDs and upsert mean the action can be run again safely.
    """
    rows = safe_rows(
        sb,
        "pc_observations",
        "observation_id,source_id,source_name,source_url,source_type,observation_date,raw_value,derived_value,confidence,review_status,record_status,metadata",
        5000,
        {"source_id":"SRC_OPEN_RECAAP_ISC"},
        "observation_date"
    )

    if not rows:
        return {"observations":0,"events":0,"locations":0,"skipped":0,"failures":[]}

    event_rows=[]
    location_rows=[]
    skipped=0
    failures=[]

    for obs in rows:
        # These rows are already canonical pc_observations records. Earlier batch
        # imports preserved payload.review_status="pending" even after the staged
        # proposal itself was explicitly approved/applied. For the curated ReCAAP
        # source, canonical presence + source_id is sufficient for this deterministic
        # promotion. Normalize the observation review status to approved here.
        try:
            if str(obs.get("review_status") or "").lower() != "approved":
                sb.table("pc_observations").update({
                    "review_status":"approved",
                    "record_status":"verified"
                }).eq("observation_id",obs["observation_id"]).execute()
                obs["review_status"]="approved"
                obs["record_status"]="verified"

            event, loc = _recaap_event_payload(obs)
            event_rows.append(event)
            if loc:
                location_rows.append(loc)
        except Exception as exc:
            failures.append(f"{obs.get('observation_id')}: {exc}")

    # Upsert events first because locations FK to them.
    for i in range(0,len(event_rows),100):
        sb.table("pc_events").upsert(event_rows[i:i+100],on_conflict="event_id").execute()

    for i in range(0,len(location_rows),100):
        sb.table("pc_event_locations").upsert(location_rows[i:i+100],on_conflict="event_location_id").execute()

    return {
        "observations":len(rows),
        "events":len(event_rows),
        "locations":len(location_rows),
        "skipped":skipped,
        "failures":failures,
    }



# ---------------------------------------------------------------------------
# ReCAAP vessel resolution helpers
# ---------------------------------------------------------------------------

def _norm_vessel_name(value):
    s=str(value or "").upper().strip()
    s=re.sub(r"\b(MV|M/V|MT|M/T|MV\.|MT\.)\b"," ",s)
    s=re.sub(r"[^A-Z0-9]+"," ",s)
    return re.sub(r"\s+"," ",s).strip()


def _recaap_events_for_resolution(sb):
    rows=safe_rows(
        sb,
        "pc_events",
        "event_id,start_date,title,event_type,source_id,metadata",
        5000,
        {"source_id":"SRC_OPEN_RECAAP_ISC"},
        "start_date"
    )
    out=[]
    for r in rows:
        meta=r.get("metadata") or {}
        if not isinstance(meta,dict):
            meta={}
        vessel=meta.get("vessel_name")
        if not vessel:
            title=str(r.get("title") or "")
            vessel=title.split("—",1)[-1].strip() if "—" in title else None
        if vessel:
            rr=dict(r)
            rr["_vessel_name"]=vessel
            rr["_norm_name"]=_norm_vessel_name(vessel)
            out.append(rr)
    return out


def _canonical_vessels_for_resolution(sb):
    rows=safe_rows(
        sb,
        "pc_mobile_assets",
        "mobile_asset_id,name,asset_type,subtype,imo,mmsi,registration,call_sign,flag,year_built,dwt,owner_entity_id,operator_entity_id,manager_entity_id,status,record_status,data_quality,source_id,metadata",
        10000
    )
    for r in rows:
        r["_norm_name"]=_norm_vessel_name(r.get("name"))
    return rows


def _existing_event_vessel_links(sb):
    rows=safe_rows(sb,"pc_event_links","event_link_id,event_id,linked_type,linked_id,linked_name,relationship,confidence,source_id,metadata",10000)
    return {
        r.get("event_id"):r for r in rows
        if str(r.get("linked_type") or "").lower() in {"mobile_asset","vessel"}
    }


def _link_id(event_id,mobile_asset_id):
    digest=hashlib.sha1(f"{event_id}|{mobile_asset_id}".encode("utf-8")).hexdigest()[:14].upper()
    return f"EVLINK_RECAAP_{digest}"


def stage_recaap_exact_vessel_links(sb):
    """Stage exact canonical vessel-name matches for ReCAAP events."""
    events=_recaap_events_for_resolution(sb)
    vessels=_canonical_vessels_for_resolution(sb)
    existing=_existing_event_vessel_links(sb)

    by_name={}
    for v in vessels:
        n=v.get("_norm_name")
        if n:
            by_name.setdefault(n,[]).append(v)

    proposals=[]
    unresolved=[]
    ambiguous=[]
    already=0

    job=None
    for e in events:
        if e["event_id"] in existing:
            already+=1
            continue
        matches=by_name.get(e.get("_norm_name") or "",[])
        if len(matches)==1:
            v=matches[0]
            payload={
                "event_link_id":_link_id(e["event_id"],v["mobile_asset_id"]),
                "event_id":e["event_id"],
                "linked_type":"mobile_asset",
                "linked_id":v["mobile_asset_id"],
                "linked_name":v.get("name"),
                "relationship":"involved vessel",
                "confidence":"high",
                "source_id":"SRC_OPEN_RECAAP_ISC",
                "metadata":{
                    "resolution_method":"normalized exact vessel-name match",
                    "recaap_vessel_name":e.get("_vessel_name"),
                    "imo":v.get("imo"),
                }
            }
            proposals.append({
                "target_table":"pc_event_links",
                "natural_key":payload["event_link_id"],
                "payload":payload,
                "confidence":0.99,
            })
        elif len(matches)>1:
            ambiguous.append({
                "event_id":e["event_id"],
                "vessel_name":e.get("_vessel_name"),
                "candidate_count":len(matches),
                "candidates":" | ".join(f"{x.get('name')} IMO {x.get('imo') or '—'}" for x in matches[:5]),
            })
        else:
            unresolved.append({
                "event_id":e["event_id"],
                "vessel_name":e.get("_vessel_name"),
                "event_date":e.get("start_date"),
                "event_type":e.get("event_type"),
            })

    if proposals:
        job=sb.table("pc_ingestion_jobs").insert({
            "job_type":"DETERMINISTIC_ENTITY_RESOLUTION",
            "title":"ReCAAP exact vessel-link resolution",
            "query_text":"Exact normalized vessel-name resolution against pc_mobile_assets.",
            "source_scope":{"dataset":"ReCAAP","target_table":"pc_event_links"},
            "status":"running",
        }).execute().data[0]
        job_id=job["ingestion_job_id"]

        staged=[]
        for p in proposals:
            staged.append({
                "ingestion_job_id":job_id,
                "target_table":"pc_event_links",
                "natural_key":p["natural_key"],
                "action":"REVIEW",
                "payload":p["payload"],
                "confidence":p["confidence"],
                "validation_status":"pending",
                "review_status":"pending",
            })
        for i in range(0,len(staged),250):
            sb.table("pc_staged_records").insert(staged[i:i+250]).execute()
        sb.table("pc_ingestion_jobs").update({
            "status":"completed",
            "stats":{
                "staged_exact_links":len(staged),
                "unresolved":len(unresolved),
                "ambiguous":len(ambiguous),
                "already_linked":already,
            }
        }).eq("ingestion_job_id",job_id).execute()

    return {
        "events":len(events),
        "staged":len(proposals),
        "unresolved":unresolved,
        "ambiguous":ambiguous,
        "already":already,
    }


RECAAP_AI_RESOLVER_PROMPT = """Resolve unresolved ReCAAP maritime-security event vessel identities.

Rules:
1. Match by IMO when an IMO is established by an authoritative or reliable maritime source.
2. Otherwise resolve the exact vessel identity conservatively using vessel name, incident date, vessel type, flag, operator/owner and event geography.
3. Never guess between same-name vessels.
4. If the vessel already exists in the supplied canonical P&C vessel candidates, propose ONLY a pc_event_links record.
5. If the vessel is demonstrably missing from the canonical vessel registry, propose a pc_mobile_assets record with a stable mobile_asset_id, name, asset_type, subtype where useful, IMO where verified, flag, status, source_id where available, and metadata containing research_sources; then also propose its pc_event_links record.
6. pc_event_links must use linked_type='mobile_asset', relationship='involved vessel', and the exact ReCAAP event_id supplied.
7. Every proposed new vessel must have at least one source URL. Prefer IMO/GISIS/equivalent official records, classification/flag/owner sources, ReCAAP, and reputable maritime databases or reporting.
8. Return unresolved/ambiguous cases in conflicts rather than inventing an identity.
9. Do not create duplicate canonical vessels.
"""



# ---------------------------------------------------------------------------
# Workflow / multi-table / document / distribution helpers
# ---------------------------------------------------------------------------

WORKFLOW_STAGES = {
    "AI_RESEARCH": [
        "RESEARCH","STAGE","PREPARE_IDS","RECONCILE","RELATIONSHIPS","REVIEW","APPLY","QA","COMPLETE"
    ],
    "BULK_IMPORT": [
        "UPLOAD","MAP_TABLES","MAP_FIELDS","FILL_KEYS","STAGE","RECONCILE","REVIEW","APPLY","QA","COMPLETE"
    ],
    "DOCUMENT_INGEST": [
        "UPLOAD","EXTRACT","LINK","STRUCTURE","STAGE","RECONCILE","REVIEW","APPLY","COMPLETE"
    ],
}

ID_FIELDS = {
    "pc_entities": ("entity_id","ENTITY_",16),
    "pc_assets": ("asset_id","ASSET_",16),
    "pc_mobile_assets": ("mobile_asset_id","MOBILE_",16),
    "pc_relationships": ("relationship_id","REL_",24),
    "pc_events": ("event_id","EVENT_",20),
    "pc_event_links": ("event_link_id","EVLINK_",20),
    "pc_transactions": ("transaction_id","TXN_",20),
    "pc_transport_routes": ("route_id","ROUTE_",20),
    "pc_chokepoints": ("chokepoint_id","CHOKE_",20),
    "pc_market_instruments": ("market_instrument_id","MKT_",20),
    "pc_trade_flows": ("trade_flow_id","FLOW_",20),
    "pc_supply_series": ("supply_series_id","SUPPLY_",20),
    "pc_observations": ("observation_id","OBS_",20),
}

FIELD_ALIASES = {
    "canonical_name":"name","entity_name":"name","company_name":"name","vessel_name":"name",
    "asset_name":"name","display_name":"name","organisation_name":"name","organization_name":"name",
    "imo_number":"imo","imo_no":"imo","imo_no.":"imo",
    "country_name":"country","city":"region_city","region":"region_city",
    "operator_id":"operator_entity_id","owner_id":"owner_entity_id","manager_id":"manager_entity_id",
    "source_url":"source_url",
}

def _norm_field(v):
    return re.sub(r"[^a-z0-9]+","_",str(v or "").strip().casefold()).strip("_")

def _table_write_columns_live(sb, table):
    """Return writable columns plus critical canonical fields needed by staging.

    Some deployments of pc_get_table_write_columns omit fields that the staging
    validator/reconciler still requires (for example entity_type) or provenance
    fields we preserve in metadata. Always union the RPC result with the canonical
    staging field set instead of trusting the RPC list as exhaustive.
    """
    base=set(REQUIRED_BY_TABLE.get(table,[])) | set(ID_FIELDS.get(table,("", "", 0))[:1]) | {
        "name","title","entity_type","asset_type","event_type","subtype","status","country","region_city",
        "imo","mmsi","flag","owner_entity_id","operator_entity_id","manager_entity_id","source_id",
        "source_url","metadata"
    }
    try:
        r=sb.rpc("pc_get_table_write_columns",{"p_table_name":table}).execute().data
        if isinstance(r,list):
            base.update(str(x) for x in r if x)
    except Exception:
        pass
    return sorted(base)

def _auto_column_mapping(source_columns, target_columns):
    targets={_norm_field(x):x for x in target_columns}
    rows=[]
    for src in source_columns:
        n=_norm_field(src)
        alias=FIELD_ALIASES.get(n)
        target=targets.get(_norm_field(alias)) if alias else targets.get(n)
        rows.append({"Include":bool(target),"Source Column":src,"Canonical Field":target or ""})
    return pd.DataFrame(rows)

def _clean_upload_scalar(v):
    if v is None:
        return None
    if isinstance(v,float) and pd.isna(v):
        return None
    s=str(v).strip()
    if not s or s.casefold()=="nan":
        return None
    return v

def _jsonish(v):
    if isinstance(v,(dict,list)) or v is None:
        return v
    s=str(v).strip()
    if not s:
        return None
    if (s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]")):
        try: return json.loads(s)
        except Exception: return v
    return v

def _payload_from_mapping(row, mapping_df, target_table):
    payload={}
    for _,m in mapping_df.iterrows():
        if not bool(m.get("Include")):
            continue
        src=str(m.get("Source Column") or "")
        dst=str(m.get("Canonical Field") or "").strip()
        if not src or not dst or src not in row:
            continue
        val=_clean_upload_scalar(row.get(src))
        if val is None:
            continue
        if dst in {"metadata","raw_value","derived_value","source_scope","stats"}:
            val=_jsonish(val)
        payload[dst]=val

    # Keep unmapped source fields in metadata.source_payload rather than discarding them.
    source_payload={}
    mapped_sources=set(mapping_df.loc[mapping_df["Include"]==True,"Source Column"].astype(str)) if not mapping_df.empty else set()
    for k,v in row.items():
        if k in mapped_sources:
            continue
        val=_clean_upload_scalar(v)
        if val is not None:
            source_payload[str(k)]=_jsonable(val)
    if source_payload:
        meta=payload.get("metadata") if isinstance(payload.get("metadata"),dict) else {}
        meta=dict(meta)
        meta.setdefault("source_payload",{}).update(source_payload)
        payload["metadata"]=meta

    # Preserve provenance even when source_url / research_sources are not physical
    # columns on the canonical table. The validator accepts metadata provenance.
    meta=payload.get("metadata") if isinstance(payload.get("metadata"),dict) else {}
    meta=dict(meta)

    src_url=_clean_upload_scalar(row.get("source_url")) if isinstance(row,dict) else None
    if src_url:
        payload.setdefault("source_url",src_url)
        meta.setdefault("source_url",src_url)

    rs=_clean_upload_scalar(row.get("research_sources")) if isinstance(row,dict) else None
    if rs:
        parsed=_jsonish(rs)
        if isinstance(parsed,list):
            vals=parsed
        elif isinstance(parsed,str):
            vals=[x.strip() for x in re.split(r"\s*[;|]\s*",parsed) if x.strip()]
        else:
            vals=[parsed]
        current=meta.get("research_sources") if isinstance(meta.get("research_sources"),list) else []
        for u in vals:
            if u and u not in current:
                current.append(u)
        meta["research_sources"]=current

    # Recover critical canonical fields from original row even if UI mapping missed them.
    critical_by_table={
        "pc_entities":["entity_id","name","entity_type","subtype","country"],
        "pc_assets":["asset_id","name","asset_type","subtype","country","region_city"],
        "pc_mobile_assets":["mobile_asset_id","name","asset_type","subtype","imo","mmsi","flag"],
        "pc_events":["event_id","event_type","event_domain","event_family","title","severity","status"],
        "pc_event_links":["event_link_id","event_id","linked_type","linked_id","relationship"],
        "pc_relationships":["relationship_id","source_type","source_id","relationship_type","target_type","target_id"],
    }
    for field in critical_by_table.get(target_table,[]):
        if payload.get(field) in (None,""):
            val=_clean_upload_scalar(row.get(field)) if isinstance(row,dict) else None
            if val is not None:
                payload[field]=val

    if meta:
        payload["metadata"]=meta

    return payload

def _natural_key_global(payload,target_table,index):
    for key in (
        "entity_id","asset_id","mobile_asset_id","relationship_id","event_id","event_link_id",
        "transaction_id","route_id","chokepoint_id","market_instrument_id","trade_flow_id",
        "supply_series_id","observation_id","imo","mmsi","name","title","route_name"
    ):
        if payload.get(key):
            return str(payload[key])
    return f"{target_table}:{index}"

def _fill_staging_key(payload,target_table,natural_key):
    payload=dict(payload or {})
    spec=ID_FIELDS.get(target_table)
    if not spec:
        return payload
    field,prefix,n=spec
    if payload.get(field):
        return payload
    digest=hashlib.sha256(f"{target_table}|{natural_key}".encode("utf-8")).hexdigest().upper()[:n]
    payload[field]=prefix+digest
    return payload

def _parse_multitable_upload(upload):
    raw=upload.getvalue()
    name=upload.name.lower()
    sections={}
    if name.endswith((".xlsx",".xls")):
        xf=pd.ExcelFile(io.BytesIO(raw))
        for sheet in xf.sheet_names:
            sections[sheet]=pd.read_excel(io.BytesIO(raw),sheet_name=sheet,dtype=object)
    elif name.endswith(".csv"):
        df=pd.read_csv(io.BytesIO(raw),dtype=object)
        if "target_table" in df.columns:
            for table,g in df.groupby("target_table",dropna=False):
                sections[str(table or "records")]=g.drop(columns=["target_table"]).reset_index(drop=True)
        else:
            sections[Path(upload.name).stem]=df
    else:
        obj=json.loads(raw.decode("utf-8-sig"))
        records=obj if isinstance(obj,list) else obj.get("records",[obj])
        df=pd.DataFrame(records)
        if "target_table" in df.columns:
            for table,g in df.groupby("target_table",dropna=False):
                sections[str(table or "records")]=g.drop(columns=["target_table"]).reset_index(drop=True)
        else:
            sections[Path(upload.name).stem]=df
    return sections, hashlib.sha256(raw).hexdigest()

def _suggest_target_table(section,df):
    n=_norm_field(section)
    aliases={
        "companies":"pc_entities","entities":"pc_entities","organisations":"pc_entities","organizations":"pc_entities",
        "assets":"pc_assets","ports":"pc_assets","terminals":"pc_assets","infrastructure":"pc_assets",
        "vessels":"pc_mobile_assets","ships":"pc_mobile_assets","mobile_assets":"pc_mobile_assets",
        "relationships":"pc_relationships","relations":"pc_relationships",
        "events":"pc_events","incidents":"pc_events","event_links":"pc_event_links",
        "transactions":"pc_transactions","deals":"pc_transactions",
        "routes":"pc_transport_routes","corridors":"pc_transport_routes",
        "chokepoints":"pc_chokepoints","observations":"pc_observations",
    }
    if n in aliases:
        return aliases[n]
    cols={_norm_field(c) for c in df.columns}
    if "imo" in cols or "vessel_name" in cols:
        return "pc_mobile_assets"
    if "relationship_type" in cols and ("source_id" in cols or "source_name" in cols):
        return "pc_relationships"
    if "event_type" in cols:
        return "pc_events"
    if "entity_type" in cols or "company_name" in cols:
        return "pc_entities"
    if "asset_type" in cols:
        return "pc_assets"
    return "pc_entities"

def _workflow_upsert(job_id, workflow_type, title, stage, order, status="running", stats=None, metadata=None):
    if not sb:
        return None
    try:
        hit=(sb.table("pc_workflow_runs").select("*").eq("ingestion_job_id",job_id).limit(1).execute().data or [])
        patch={
            "workflow_type":workflow_type,"title":title,"current_stage":stage,"stage_order":order,
            "status":status,"updated_at":pd.Timestamp.utcnow().isoformat(),
            "stats":stats or {},"metadata":metadata or {}
        }
        if hit:
            wid=hit[0]["workflow_run_id"]
            # Workflow progression is monotonic. A later refresh/reconcile pass must
            # never send a job backwards from APPLY/QA to RECONCILE/RELATIONSHIPS.
            current_order=int(hit[0].get("stage_order") or 0)
            incoming_order=int(order or 0)
            if incoming_order < current_order:
                patch["current_stage"]=hit[0].get("current_stage")
                patch["stage_order"]=current_order
                # Preserve completed/success state when a lower-order diagnostic pass runs.
                if str(hit[0].get("status") or "").lower() in {"completed","complete","success","succeeded"}:
                    patch["status"]=hit[0].get("status")
            sb.table("pc_workflow_runs").update(patch).eq("workflow_run_id",wid).execute()
        else:
            patch["ingestion_job_id"]=job_id
            wid=sb.table("pc_workflow_runs").insert(patch).execute().data[0]["workflow_run_id"]
        try:
            sb.table("pc_workflow_stage_events").insert({
                "workflow_run_id":wid,"stage_name":stage,"stage_order":order,
                "stage_status":status,"stats":stats or {}
            }).execute()
        except Exception:
            pass
        return wid
    except Exception:
        return None

def _workflow_job_rows(job_type=None,limit=100):
    """Return ingestion jobs used by the workflow UI.

    pc_ingestion_jobs does not have an updated_at column in the current schema.
    The previous projection requested updated_at, causing PostgREST to reject the
    whole query and making Run & reconcile / Workflow Center appear permanently empty.
    Keep this projection to columns that actually exist on pc_ingestion_jobs.
    """
    if not sb:
        return []
    cols=(
        "ingestion_job_id,job_type,title,query_text,status,stats,error_text,"
        "created_at,started_at,completed_at,source_scope"
    )
    q=sb.table("pc_ingestion_jobs").select(cols).order("created_at",desc=True).limit(limit)
    if job_type:
        q=q.eq("job_type",job_type)
    try:
        return q.execute().data or []
    except Exception as exc:
        # Do not silently turn a schema/query error into an apparently empty workflow.
        try:
            st.warning(f"Could not load workflow jobs from pc_ingestion_jobs: {exc}")
        except Exception:
            pass
        return []

def _staging_summary(job_id):
    if not sb: return {}
    try:
        rows=(sb.table("pc_staged_records").select(
            "staged_record_id,target_table,resolution_status,review_status,validation_status,payload"
        ).eq("ingestion_job_id",job_id).limit(10000).execute().data or [])
    except Exception:
        rows=[]
    out={
        "total":len(rows),"pending":0,"approved":0,"applied":0,
        "unresolved":0,"ambiguous":0,"partial":0,"ready":0,"missing_name":0,
        # Mutually-exclusive workflow buckets used by the operator UI.
        "wf_applied":0,"wf_approved":0,"wf_exceptions":0,"wf_ready":0,"wf_other":0
    }
    for r in rows:
        rv=str(r.get("review_status") or "pending").lower()
        out[rv]=out.get(rv,0)+1
        rs=str(r.get("resolution_status") or "UNRESOLVED").upper()
        if rs=="UNRESOLVED": out["unresolved"]+=1
        if rs=="AMBIGUOUS": out["ambiguous"]+=1
        if rs=="PARTIAL": out["partial"]+=1
        if rs in {"READY","MATCHED","NEW"}: out["ready"]+=1

        # Exclusive workflow classification. This avoids misleading overlaps such
        # as a row being counted in both Ready and Applied.
        if rv=="applied":
            out["wf_applied"]+=1
        elif rv=="approved":
            out["wf_approved"]+=1
        elif rs in {"UNRESOLVED","AMBIGUOUS","PARTIAL"}:
            out["wf_exceptions"]+=1
        elif rs in {"READY","MATCHED","NEW"}:
            out["wf_ready"]+=1
        else:
            out["wf_other"]+=1

        p=r.get("payload") if isinstance(r.get("payload"),dict) else {}
        if r.get("target_table") in {"pc_entities","pc_assets","pc_mobile_assets"} and not p.get("name"):
            out["missing_name"]+=1
    return out


def _audit_bulk_jobs(limit=250):
    """Cross-check bulk/research ingestion jobs against pc_staged_records.

    This catches the failure mode where pc_ingestion_jobs.stats reports imported
    rows but the staging rows are missing, only partially staged, or attached to
    a different ingestion_job_id.
    """
    if not sb:
        return []
    jobs = _workflow_job_rows(None, limit) or []

    # Optional workflow-state lookup. This is diagnostic only.
    workflow_map = {}
    try:
        wrs = (sb.table("pc_workflow_runs")
               .select("ingestion_job_id,workflow_type,current_stage,status,updated_at,completed_at")
               .order("updated_at", desc=True)
               .limit(limit * 3).execute().data or [])
        for w in wrs:
            jid = str(w.get("ingestion_job_id") or "").strip()
            if jid and jid not in workflow_map:
                workflow_map[jid] = w
    except Exception:
        workflow_map = {}

    out = []
    for j in jobs:
        jt = str(j.get("job_type") or "").upper()
        if jt not in {"BATCH_IMPORT","AI_RESEARCH"}:
            continue
        jid = str(j.get("ingestion_job_id") or "").strip()
        if not jid:
            continue

        stats = j.get("stats") if isinstance(j.get("stats"), dict) else {}
        reported_rows = stats.get("rows")
        if reported_rows is None:
            reported_rows = stats.get("staged")
        try:
            reported_rows = int(reported_rows or 0)
        except Exception:
            reported_rows = 0

        table_stats = stats.get("tables") if isinstance(stats.get("tables"), dict) else {}
        if not reported_rows and table_stats:
            try:
                reported_rows = sum(int(v or 0) for v in table_stats.values())
            except Exception:
                reported_rows = 0

        summ = _staging_summary(jid)
        staged = int(summ.get("total",0) or 0)
        applied = int(summ.get("applied",0) or 0)
        pending = int(summ.get("pending",0) or 0)
        approved = int(summ.get("approved",0) or 0)
        unresolved = int(summ.get("unresolved",0) or 0)
        ambiguous = int(summ.get("ambiguous",0) or 0)
        partial = int(summ.get("partial",0) or 0)
        ready = int(summ.get("ready",0) or 0)

        if reported_rows > 0 and staged == 0:
            health = "CHECK — stats rows but no staging rows"
        elif reported_rows > 0 and staged < reported_rows:
            health = "CHECK — partial staging"
        elif reported_rows > 0 and staged > reported_rows:
            health = "CHECK — staging exceeds job stats"
        elif staged and (unresolved or ambiguous or partial):
            health = "REVIEW — reconciliation exceptions"
        elif staged and applied == staged:
            health = "APPLIED"
        elif staged:
            health = "STAGED / IN WORKFLOW"
        elif str(j.get("status") or "").lower() == "failed":
            health = "FAILED"
        else:
            health = "NO DATA"

        wf = workflow_map.get(jid,{})
        out.append({
            "ingestion_job_id": jid,
            "job_type": jt,
            "title": j.get("title"),
            "job_status": j.get("status"),
            "reported_rows": reported_rows,
            "staged_rows": staged,
            "difference": staged - reported_rows if reported_rows else staged,
            "pending": pending,
            "approved": approved,
            "applied": applied,
            "ready": ready,
            "unresolved": unresolved,
            "ambiguous": ambiguous,
            "partial": partial,
            "workflow_stage": wf.get("current_stage"),
            "workflow_status": wf.get("status"),
            "workflow_updated_at": wf.get("updated_at"),
            "created_at": j.get("created_at"),
            "completed_at": j.get("completed_at"),
            "health": health,
            "error_text": j.get("error_text"),
            "reported_tables": table_stats,
        })
    return out


def _snapshot_applied_staging(job_id):
    if not sb or not job_id:
        return {}
    try:
        rows=(sb.table("pc_staged_records")
              .select("staged_record_id,review_status,resolution_status,validation_status,resolved_entity_id,resolution_method,resolution_confidence,candidate_count")
              .eq("ingestion_job_id",str(job_id))
              .eq("review_status","applied")
              .limit(10000).execute().data or [])
        return {str(r["staged_record_id"]):r for r in rows if r.get("staged_record_id")}
    except Exception:
        return {}


def _restore_applied_staging(snapshot):
    """Applied rows are terminal and must not be downgraded by reconciliation RPCs."""
    restored=0
    errors=[]
    for sid,r in (snapshot or {}).items():
        patch={
            "review_status":"applied",
            "resolution_status":r.get("resolution_status"),
            "validation_status":r.get("validation_status"),
            "resolved_entity_id":r.get("resolved_entity_id"),
            "resolution_method":r.get("resolution_method"),
            "resolution_confidence":r.get("resolution_confidence"),
            "candidate_count":r.get("candidate_count"),
        }
        patch={k:v for k,v in patch.items() if v is not None or k=="review_status"}
        try:
            sb.table("pc_staged_records").update(patch).eq("staged_record_id",sid).execute()
            restored+=1
        except Exception as exc:
            errors.append(f"{sid}: {exc}")
    return {"restored":restored,"errors":errors}


def _run_reconciliation(job_id):
    """Run reconciliation without ever downgrading rows already applied canonically."""
    applied_snapshot=_snapshot_applied_staging(job_id)
    result=None
    try:
        try:
            result=sb.rpc("pc_reconcile_ingestion_job_v2",{"p_ingestion_job_id":str(job_id)}).execute().data
        except Exception as v2_exc:
            try:
                result=sb.rpc("pc_run_standard_reconciliation",{"p_job_id":job_id}).execute().data
            except Exception:
                result={"v2_error":str(v2_exc)}
                try: result["prepare"]=_prepare_canonical_candidates(sb,job_id)
                except Exception as exc: result["prepare_error"]=str(exc)
                try: result["repair"]=sb.rpc("pc_repair_unresolved_identity_candidates",{"p_job_id":job_id}).execute().data
                except Exception as exc: result["repair_error"]=str(exc)
                try: result["event_relationships"]=_process_relationship_backlog(sb,job_id)
                except Exception as exc: result["event_relationships_error"]=str(exc)
                try: result["generic_relationships"]=_process_generic_relationship_backlog(sb,job_id)
                except Exception as exc: result["generic_relationships_error"]=str(exc)
        return result
    finally:
        restore=_restore_applied_staging(applied_snapshot)
        if isinstance(result,dict):
            result["applied_state_restore"]=restore

def _docx_text(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        xml=z.read("word/document.xml")
    root=ET.fromstring(xml)
    ns="{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    lines=[]
    for p in root.iter(ns+"p"):
        text="".join((n.text or "") for n in p.iter(ns+"t"))
        if text.strip():
            lines.append(text.strip())
    return "\n".join(lines)

def _extract_pdf_text(raw):
    """Extract PDF text using whichever parser is available in the deployment.

    pypdf is preferred, but older deployments may already have PyPDF2,
    pdfplumber or PyMuPDF installed.  We deliberately try all of them so a
    missing optional package does not crash the entire AI Research page.
    """
    errors=[]

    try:
        from pypdf import PdfReader
        reader=PdfReader(io.BytesIO(raw))
        text="\n".join((p.extract_text() or "") for p in reader.pages)
        if text.strip():
            return text
        errors.append("pypdf returned no extractable text")
    except Exception as exc:
        errors.append(f"pypdf: {exc}")

    try:
        from PyPDF2 import PdfReader
        reader=PdfReader(io.BytesIO(raw))
        text="\n".join((p.extract_text() or "") for p in reader.pages)
        if text.strip():
            return text
        errors.append("PyPDF2 returned no extractable text")
    except Exception as exc:
        errors.append(f"PyPDF2: {exc}")

    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(raw)) as pdf:
            text="\n".join((p.extract_text() or "") for p in pdf.pages)
        if text.strip():
            return text
        errors.append("pdfplumber returned no extractable text")
    except Exception as exc:
        errors.append(f"pdfplumber: {exc}")

    try:
        import fitz  # PyMuPDF
        pdf=fitz.open(stream=raw,filetype="pdf")
        try:
            text="\n".join(page.get_text("text") or "" for page in pdf)
        finally:
            pdf.close()
        if text.strip():
            return text
        errors.append("PyMuPDF returned no extractable text")
    except Exception as exc:
        errors.append(f"PyMuPDF: {exc}")

    raise RuntimeError(
        "No usable PDF text parser is installed (or the PDF contains no "
        "extractable text). Add `pypdf>=5.0` to requirements.txt. Details: "
        + " | ".join(errors)
    )

def _extract_document_text(upload):
    raw=upload.getvalue()
    lname=upload.name.lower()
    if lname.endswith(".docx"):
        return _docx_text(raw)
    if lname.endswith((".txt",".md",".csv")):
        return raw.decode("utf-8-sig",errors="replace")
    if lname.endswith(".pdf"):
        return _extract_pdf_text(raw)
    raise RuntimeError("Supported document types: DOCX, PDF, TXT, MD.")

def _canonical_link_candidates(kind, query="",limit=100):
    config={
        "entity":("pc_entities","entity_id,name,entity_type,hq_country","name"),
        "asset":("pc_assets","asset_id,name,asset_type,country","name"),
        "mobile_asset":("pc_mobile_assets","mobile_asset_id,name,asset_type,imo,flag","name"),
        "event":("pc_events","event_id,title,event_type,start_date","title"),
    }
    table,cols,display=config[kind]
    try:
        q=sb.table(table).select(cols).limit(limit)
        if query.strip():
            q=q.ilike(display,f"%{query.strip()}%")
        return q.execute().data or []
    except Exception:
        return []

def _table_exists(name):
    if not sb: return False
    try:
        sb.table(name).select("*").limit(1).execute()
        return True
    except Exception:
        return False


selected_page=st.sidebar.radio("",PAGES,label_visibility="collapsed")
page=NAV[selected_page]
st.sidebar.caption("Ingest → resolve/upsert objects → link graph → QA")

if sb is None:
    st.warning("Supabase service connection is not configured yet. The app is valid and can be deployed now; add SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY to secrets before using database actions.")


def dataframe(rows):
    """Render rows without letting Streamlit's magic renderer display the returned DataframeInteractor."""
    if rows:
        _df = pd.DataFrame(rows)
        _rendered = st.dataframe(
            _df,
            use_container_width=True,
            hide_index=True,
        )
        # Intentionally do not leave st.dataframe(...) as the value of an
        # expression statement: newer Streamlit builds can magic-render the
        # returned DataframeInteractor object below the table.
        return None
    st.caption("No records.")
    return None

def title(t,copy=""):
    st.markdown(f"<div class='pc-k'>P&C INTERNAL</div><h1>{t}</h1>",unsafe_allow_html=True)
    if copy: st.caption(copy)

# ---------------------------------------------------------------------------
# SQL 010 metadata-driven model / staging helpers
# ---------------------------------------------------------------------------

def _rpc_data(sb, function_name, params=None):
    """Call a Supabase RPC and return its data payload."""
    return sb.rpc(function_name, params or {}).execute().data

def _meta_entity_types(sb):
    try:
        return (
            sb.table("pc_meta_entity_types")
            .select("entity_type,table_name,primary_key_column,display_name_column,id_prefix,canonical,active,allow_insert,allow_update,description")
            .eq("active", True)
            .order("entity_type")
            .execute().data or []
        )
    except Exception:
        return []

def _meta_table_map(sb):
    return {r.get("table_name"):r for r in _meta_entity_types(sb) if r.get("table_name")}

def _resolution_rows(sb, limit=1000, filters=None):
    try:
        q=sb.table("pc_v_staging_resolution").select("*")
        for k,v in (filters or {}).items():
            q=q.eq(k,v)
        return q.order("created_at",desc=True).limit(limit).execute().data or []
    except Exception:
        return []

def _process_job_resolution(sb, job_id):
    data=_rpc_data(sb,"pc_process_ingestion_job",{"p_ingestion_job_id":str(job_id)})
    return data or {}


def _prepare_canonical_candidates(sb, job_id):
    """SQL 016: resolve entity rows and assign/reuse canonical IDs in staging only."""
    data=_rpc_data(sb,"pc_prepare_canonical_candidates",{"p_ingestion_job_id":str(job_id)})
    return data or {}


# ---------------------------------------------------------------------------
# Semantic completion helpers
# ---------------------------------------------------------------------------
SEMANTIC_REQUIRED_FIELDS = {
    "pc_entities": "entity_type",
    "pc_assets": "asset_type",
    "pc_mobile_assets": "asset_type",
    "pc_events": "event_type",
}

def _semantic_suggestion(table, payload, natural_key=""):
    """Conservative stage-only suggestion for a required semantic classifier.

    Suggestions are never auto-applied. They exist to speed analyst review and are
    deliberately broad when the research payload does not already contain a type.
    """
    payload = payload if isinstance(payload, dict) else {}
    text = " ".join(str(x or "") for x in [natural_key, payload.get("name"), payload.get("subtype"), payload.get("description")]).casefold()
    if table == "pc_entities":
        # Research populations in pc_entities represent organizations/companies unless
        # the analyst chooses a more specific value. Keep the suggestion broad.
        if any(k in text for k in ["authority", "ministry", "government"]):
            return "Government entity"
        if any(k in text for k in ["port authority", "ports authority"]):
            return "Port authority"
        return "Company"
    if table == "pc_assets":
        if "inland" in text and "depot" in text:
            return "Inland container depot"
        if "logistics park" in text or "logistics_park" in text:
            return "Logistics park"
        if "corridor" in text:
            return "Trade corridor"
        if "terminal" in text:
            return "Container terminal"
        if "port" in text:
            return "Port"
        if "feeder service" in text or "feeder_service" in text:
            return "Maritime service"
        return "Logistics facility"
    if table == "pc_mobile_assets":
        return payload.get("subtype") or "Vessel"
    if table == "pc_events":
        return payload.get("event_domain") or "Research event"
    return ""

def _semantic_gap_rows(rows, job_id=None):
    gaps=[]
    for r in rows or []:
        if job_id and str(r.get("ingestion_job_id")) != str(job_id):
            continue
        table=str(r.get("target_table") or "")
        field=SEMANTIC_REQUIRED_FIELDS.get(table)
        if not field:
            continue
        payload=r.get("payload") if isinstance(r.get("payload"),dict) else {}
        if payload.get(field) not in (None,""):
            continue
        gaps.append({
            "Apply?": True,
            "Record": r.get("natural_key"),
            "Table": table,
            "Name": payload.get("name") or payload.get("title") or r.get("natural_key"),
            "Required field": field,
            "Suggested value": _semantic_suggestion(table,payload,r.get("natural_key") or ""),
            "Value": _semantic_suggestion(table,payload,r.get("natural_key") or ""),
            "_id": r.get("staged_record_id"),
        })
    return gaps

def _save_semantic_completions(sb, rows, pending_by_id):
    saved=0
    skipped=0
    for item in rows or []:
        if not item.get("Apply?"):
            continue
        sid=item.get("_id")
        field=str(item.get("Required field") or "").strip()
        value=str(item.get("Value") or "").strip()
        original=pending_by_id.get(str(sid)) or {}
        if not sid or not field or not value or not original:
            skipped+=1
            continue
        payload=dict(original.get("payload") or {})
        payload[field]=value
        md=dict(payload.get("metadata") or {})
        md["semantic_completion"]={
            "field":field,
            "value":value,
            "method":"analyst_review",
        }
        payload["metadata"]=md
        sb.table("pc_staged_records").update({
            "payload":payload,
            "validation_status":"pending",
        }).eq("staged_record_id",sid).execute()
        try:
            _rpc_data(sb,"pc_expand_staged_payload",{"p_staged_record_id":str(sid)})
        except Exception:
            pass
        saved+=1
    return {"saved":saved,"skipped":skipped}


def _relationship_resolution_rows(sb, limit=2000, filters=None):
    """SQL 011 staged relationship decisions."""
    try:
        q=sb.table("pc_v_relationship_resolution").select("*")
        for k,v in (filters or {}).items():
            q=q.eq(k,v)
        return q.order("created_at",desc=True).limit(limit).execute().data or []
    except Exception:
        return []

def _process_relationship_backlog(sb, job_id=None):
    applied_snapshot=_snapshot_applied_staging(job_id) if job_id else {}
    try:
        params={"p_ingestion_job_id":str(job_id)} if job_id else {}
        data=_rpc_data(sb,"pc_process_relationship_backlog",params)
        return data or {}
    finally:
        if applied_snapshot:
            _restore_applied_staging(applied_snapshot)


def _apply_ready_event_relationships(sb, job_id=None):
    """SQL 012: promote revalidated READY event relationships into canonical pc_event_links."""
    params={"p_ingestion_job_id":str(job_id)} if job_id else {}
    data=_rpc_data(sb,"pc_apply_ready_event_relationships",params)
    return data or {}

def _generic_relationship_resolution_rows(sb, limit=5000, filters=None):
    """SQL 013 generic company/asset/entity relationship decisions."""
    try:
        q=sb.table("pc_v_generic_relationship_resolution").select("*")
        for k,v in (filters or {}).items():
            q=q.eq(k,v)
        return q.order("created_at",desc=True).limit(limit).execute().data or []
    except Exception:
        return []

def _process_generic_relationship_backlog(sb, job_id=None):
    applied_snapshot=_snapshot_applied_staging(job_id) if job_id else {}
    try:
        params={"p_ingestion_job_id":str(job_id)} if job_id else {}
        data=_rpc_data(sb,"pc_process_generic_relationship_backlog",params)
        return data or {}
    finally:
        if applied_snapshot:
            _restore_applied_staging(applied_snapshot)

def _apply_ready_generic_relationships(sb, job_id=None):
    params={"p_ingestion_job_id":str(job_id)} if job_id else {}
    data=_rpc_data(sb,"pc_apply_ready_generic_relationships",params)
    return data or {}

def _canonical_event_vessel_links(sb, limit=5000):
    try:
        return sb.table("pc_v_event_vessel_links").select("*").order("event_date",desc=True).limit(limit).execute().data or []
    except Exception:
        return []

# ---------------------------------------------------------------------------
# Existing-data completion / deterministic repair helpers
# ---------------------------------------------------------------------------

def _all_rows(sb, table, columns="*", limit=10000):
    try:
        return safe_rows(sb, table, columns, limit)
    except Exception:
        return []


def _blank(v):
    return v is None or (isinstance(v,str) and not v.strip())


def _is_vessel_row(r):
    text=" ".join(str(r.get(k) or "") for k in ("asset_type","mobile_type","subtype","name")).casefold()
    return any(x in text for x in ("vessel","ship","tanker","carrier","bulker","ro-ro","roro","containership","container ship","lng","lpg","ferry","cruise"))


def _is_portish_row(r):
    text=" ".join(str(r.get(k) or "") for k in ("asset_type","subtype","name","region_city")).casefold()
    return any(x in text for x in ("port","terminal","harbour","harbor","anchorage","jetty","quay","dry port"))


def _completion_inventory(sb):
    vessels=_all_rows(sb,"pc_mobile_assets","*",10000)
    assets=_all_rows(sb,"pc_assets","*",10000)
    events=_all_rows(sb,"pc_events","*",10000)
    links=_all_rows(sb,"pc_event_links","*",20000)
    locations=_all_rows(sb,"pc_event_locations","*",20000)
    staged=_all_rows(sb,"pc_v_staging_resolution","*",10000)
    relationships=_all_rows(sb,"pc_v_relationship_resolution","*",20000)
    issues=_all_rows(sb,"pc_data_quality_issues","*",10000)

    vessel_rows=[r for r in vessels if _is_vessel_row(r)]
    vessel_identity=[r for r in vessel_rows if _blank(r.get("imo"))]
    vessel_relationship=[r for r in vessel_rows if _blank(r.get("owner_entity_id")) or _blank(r.get("operator_entity_id"))]
    vessel_provenance=[r for r in vessel_rows if _blank(r.get("source_id")) or str(r.get("record_status") or "").casefold()=="provisional" or str(r.get("data_quality") or "").casefold() in {"low","medium"}]

    port_assets=[r for r in assets if _is_portish_row(r)]
    asset_geo=[r for r in port_assets if r.get("latitude") is None or r.get("longitude") is None]
    asset_relationship=[r for r in assets if _blank(r.get("owner_entity_id")) or _blank(r.get("operator_entity_id"))]
    asset_provenance=[r for r in assets if _blank(r.get("source_id")) or str(r.get("record_status") or "").casefold()=="provisional" or str(r.get("data_quality") or "").casefold() in {"low","medium"}]

    linked_event_ids={str(r.get("event_id")) for r in links if r.get("event_id")}
    located_event_ids={str(r.get("event_id")) for r in locations if r.get("event_id") and r.get("latitude") is not None and r.get("longitude") is not None}
    event_links=[r for r in events if str(r.get("event_id")) not in linked_event_ids]
    event_geo=[r for r in events if str(r.get("event_id")) not in located_event_ids]
    event_provenance=[r for r in events if _blank(r.get("source_id")) or str(r.get("record_status") or "").casefold()=="provisional"]

    backlog=[r for r in staged if str(r.get("resolution_status") or "UNRESOLVED").upper() in {"UNRESOLVED","NEW","AMBIGUOUS","CONFLICT","INVALID","PARTIAL","BROKEN_REFERENCE"}]
    relationship_backlog=[r for r in relationships if str(r.get("resolution_status") or "UNRESOLVED").upper() in {"UNRESOLVED","AMBIGUOUS","PARTIAL","BROKEN_REFERENCE","INVALID"}]
    relationship_ready=[r for r in relationships if str(r.get("resolution_status") or "").upper()=="READY" and str(r.get("apply_status") or "PENDING").upper() not in {"APPLIED","SKIPPED_EXISTS"}]
    relationship_existing=[r for r in relationships if str(r.get("resolution_status") or "").upper()=="ALREADY_EXISTS"]
    open_issues=[r for r in issues if str(r.get("status") or "open").casefold()=="open"]
    return {
        "vessels":vessel_rows,"assets":assets,"events":events,"links":links,"locations":locations,
        "vessel_identity":vessel_identity,"vessel_relationship":vessel_relationship,"vessel_provenance":vessel_provenance,
        "asset_geo":asset_geo,"asset_relationship":asset_relationship,"asset_provenance":asset_provenance,
        "event_links":event_links,"event_geo":event_geo,"event_provenance":event_provenance,
        "staging_backlog":backlog,"relationship_resolution":relationships,"relationship_backlog":relationship_backlog,
        "relationship_ready":relationship_ready,"relationship_existing":relationship_existing,"open_issues":open_issues,
    }


def _event_vessel_candidates(inv):
    """High-confidence internal candidates only: IMO in event text, or unique vessel name phrase."""
    vessels=inv.get("vessels") or []
    links=inv.get("links") or []
    events=inv.get("events") or []
    already={(str(r.get("event_id")),str(r.get("linked_id"))) for r in links if str(r.get("linked_type") or "").casefold() in {"mobile_asset","vessel"}}
    imo_map={str(r.get("imo")).strip():r for r in vessels if not _blank(r.get("imo"))}
    name_map={}
    for r in vessels:
        name=str(r.get("name") or "").strip()
        if len(name)>=5:
            key=re.sub(r"\s+"," ",name.casefold())
            name_map.setdefault(key,[]).append(r)
    unique_names={k:v[0] for k,v in name_map.items() if len(v)==1}
    out=[]
    for e in events:
        eid=str(e.get("event_id") or "")
        if not eid: continue
        domain=str(e.get("event_domain") or "").casefold()
        text=" ".join(str(e.get(k) or "") for k in ("title","description","location","operational_impact","commercial_impact"))
        if e.get("metadata"):
            try: text += " " + json.dumps(e.get("metadata"),ensure_ascii=False)
            except Exception: pass
        tcf=re.sub(r"\s+"," ",text.casefold())
        seen=set()
        for imo in set(re.findall(r"(?<!\d)(\d{7})(?!\d)",text)):
            v=imo_map.get(imo)
            if v and (eid,str(v.get("mobile_asset_id"))) not in already:
                key=(eid,str(v.get("mobile_asset_id")))
                if key not in seen:
                    seen.add(key); out.append({"event_id":eid,"event_title":e.get("title"),"mobile_asset_id":v.get("mobile_asset_id"),"vessel_name":v.get("name"),"imo":imo,"match_method":"IMO_IN_EVENT_TEXT","confidence":1.0,"source_id":e.get("source_id")})
        if "maritime" in domain or any(w in tcf for w in ("vessel","ship","tanker","carrier","merchant")):
            for n,v in unique_names.items():
                if len(n)<6 or n in {"freedom","victory","prosperity","harmony","fortune"}: continue
                if n in tcf and (eid,str(v.get("mobile_asset_id"))) not in already:
                    key=(eid,str(v.get("mobile_asset_id")))
                    if key not in seen:
                        seen.add(key); out.append({"event_id":eid,"event_title":e.get("title"),"mobile_asset_id":v.get("mobile_asset_id"),"vessel_name":v.get("name"),"imo":v.get("imo"),"match_method":"UNIQUE_NAME_IN_EVENT_TEXT","confidence":0.98,"source_id":e.get("source_id")})
    return out


def _stage_event_vessel_repairs(sb, candidates):
    if not candidates: return {"staged":0,"job_id":None}
    job=sb.table("pc_ingestion_jobs").insert({
        "job_type":"DATA_COMPLETION",
        "title":"Internal deterministic event-vessel repair",
        "status":"running",
        "source_scope":{"method":"existing_database_only","candidate_count":len(candidates)}
    }).execute().data[0]
    rows=[]
    for c in candidates:
        raw=f"{c['event_id']}|{c['mobile_asset_id']}|involved vessel".encode("utf-8")
        link_id="ELINK_AUTO_"+hashlib.sha1(raw).hexdigest()[:20].upper()
        payload={
            "event_link_id":link_id,
            "event_id":c["event_id"],
            "linked_type":"mobile_asset",
            "linked_id":c["mobile_asset_id"],
            "linked_name":c.get("vessel_name"),
            "relationship":"involved vessel",
            "confidence":"high",
            "source_id":c.get("source_id"),
            "metadata":{"completion_method":c.get("match_method"),"completion_confidence":c.get("confidence"),"existing_database_only":True,"imo":c.get("imo")}
        }
        rows.append({"ingestion_job_id":job["ingestion_job_id"],"target_entity_type":"event_link","target_table":"pc_event_links","source_record_key":link_id,"natural_key":link_id,"action":"REVIEW","payload":payload,"current_record":None,"confidence":c.get("confidence"),"validation_status":"pending","review_status":"pending","resolution_status":"NEW","source_id":c.get("source_id")})
    for i in range(0,len(rows),250): sb.table("pc_staged_records").insert(rows[i:i+250]).execute()
    try: _process_relationship_backlog(sb,job["ingestion_job_id"])
    except Exception: pass
    sb.table("pc_ingestion_jobs").update({"status":"completed","completed_at":pd.Timestamp.utcnow().isoformat(),"stats":{"staged":len(rows)}}).eq("ingestion_job_id",job["ingestion_job_id"]).execute()
    return {"staged":len(rows),"job_id":job["ingestion_job_id"]}



# ---------------------------------------------------------------------------
# Canonical context for AI research
# ---------------------------------------------------------------------------

_CANONICAL_CONTEXT_STOPWORDS = {
    "about","above","across","after","against","also","another","assets","before","build","business",
    "canonical","capture","company","companies","controlled","create","current","database","dates","every",
    "existing","fields","global","grouped","identify","include","infrastructure","investment","investments",
    "link","linked","logistics","major","managed","management","model","name","owned","owner","operator",
    "portfolio","prefer","primary","proposed","record","records","registry","relationship","relationships",
    "research","return","source","sources","stage","staging","structured","supported","table","tables",
    "terminal","terminals","trade","through","valid","value","where","which","with","without","within",
    "pc_entities","pc_assets","pc_relationships","pc_sources","json","review","exact","normalized","public"
}

def _canonical_context_terms(prompt, max_terms=32):
    """Extract useful search terms from a research brief without assuming entity identities."""
    words=re.findall(r"[A-Za-z0-9][A-Za-z0-9&.'/-]{2,}", str(prompt or ""))
    out=[]
    for w in words:
        t=w.strip(".,:;()[]{}\"'").casefold()
        if len(t)<4 or t in _CANONICAL_CONTEXT_STOPWORDS or t.startswith("http"):
            continue
        if t not in out:
            out.append(t)
        if len(out)>=max_terms:
            break
    return out

def _row_context_score(row, terms):
    name=str(row.get("name") or row.get("title") or row.get("route_name") or "")
    fields=[name,row.get("country"),row.get("region_city"),row.get("entity_type"),row.get("asset_type"),row.get("subtype"),row.get("imo"),row.get("mmsi")]
    hay=" ".join(str(x or "") for x in fields).casefold()
    score=0
    matched=[]
    for t in terms:
        if t in hay:
            score += 5 if t in name.casefold() else 1
            matched.append(t)
    return score, matched

def build_canonical_research_context(sb, prompt, per_type_limit=40):
    """Return a compact snapshot of likely canonical candidates for an AI research job.

    This is candidate context, not external evidence. The model must still use source URLs
    for researched facts and must not force a match when the supplied candidates are not exact.
    """
    terms=_canonical_context_terms(prompt)
    specs=[
        ("entities","pc_entities","entity_id,name,entity_type,country,hq_location,status,record_status,data_quality,source_id,metadata",5000),
        ("assets","pc_assets","asset_id,name,asset_type,subtype,country,region_city,latitude,longitude,owner_entity_id,operator_entity_id,status,record_status,data_quality,source_id,metadata",5000),
        ("mobile_assets","pc_mobile_assets","mobile_asset_id,name,asset_type,subtype,imo,mmsi,call_sign,flag,owner_entity_id,operator_entity_id,status,record_status,data_quality,source_id,metadata",5000),
    ]
    context={"search_terms":terms,"entities":[],"assets":[],"mobile_assets":[],"identifiers":[],"relationships":[]}
    candidate_ids=set()
    for label,table,columns,limit in specs:
        rows=safe_rows(sb,table,columns,limit)
        ranked=[]
        for r in rows:
            score,matched=_row_context_score(r,terms)
            if score>0:
                x=dict(r)
                x["_context_score"]=score
                x["_matched_terms"]=matched
                ranked.append(x)
        ranked.sort(key=lambda x:(-int(x.get("_context_score") or 0),str(x.get("name") or "")))
        selected=ranked[:per_type_limit]
        context[label]=selected
        idkey={"entities":"entity_id","assets":"asset_id","mobile_assets":"mobile_asset_id"}[label]
        candidate_ids.update(str(x.get(idkey)) for x in selected if x.get(idkey))

    # Include identifier mappings only for candidates supplied to the model.
    try:
        ids=safe_rows(sb,"pc_entity_identifiers","entity_type,entity_id,identifier_type,identifier_value,normalized_value,is_primary,confidence,source_id",5000)
        context["identifiers"]=[x for x in ids if str(x.get("entity_id") or "") in candidate_ids][:250]
    except Exception:
        pass

    # Supply graph edges touching supplied candidates, allowing research to reuse existing links.
    try:
        rels=safe_rows(sb,"pc_relationships","relationship_id,source_type,source_id,relationship_type,target_type,target_id,valid_from,valid_to,confidence,source_record_id,metadata",5000)
        context["relationships"]=[x for x in rels if str(x.get("source_id") or "") in candidate_ids or str(x.get("target_id") or "") in candidate_ids][:300]
    except Exception:
        pass

    context["candidate_counts"]={k:len(context[k]) for k in ("entities","assets","mobile_assets","identifiers","relationships")}
    return context

def canonical_context_prompt_block(context):
    if not context:
        return ""
    return """

CANONICAL P&C DATABASE CONTEXT
The following is a current internal candidate snapshot from the canonical P&C Supabase database.
It is NOT external source evidence. Use a supplied canonical ID only when the researched object is a deterministic match.
Do not force a match. If no supplied candidate is the same object, propose a NEW staged record without inventing a canonical ID.
If a supplied record is the same object, preserve its canonical ID and propose only supported enrichment/relationships rather than a duplicate.

""" + json.dumps(context,indent=2,default=str)

# ---------------------------------------------------------------------------
# Controlled AI staging + canonical apply helpers
# ---------------------------------------------------------------------------

AI_ALLOWED_TABLES = {
    "pc_entities",
    "pc_assets",
    "pc_mobile_assets",
    "pc_relationships",
    "pc_events",
    "pc_event_links",
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
    "pc_event_links": "event_link_id",
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
    "Resolve ReCAAP vessel links": (
        "Resolve the supplied unresolved ReCAAP event vessel identities. Link events to existing "
        "pc_mobile_assets when confidently matched; create missing vessel records only with reliable "
        "source evidence; stage pc_event_links using linked_type=mobile_asset and relationship=involved vessel. "
        "Do not guess ambiguous vessel identities."
    ),
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
""" + ", ".join(sorted(AI_ALLOWED_TABLES)) + """

For canonical identity records, ALWAYS include the required semantic classifier:
- pc_entities: entity_type (for example Company, Port authority, Government entity)
- pc_assets: asset_type (for example Port, Container terminal, Inland container depot, Logistics park)
- pc_mobile_assets: asset_type
- pc_events: event_type
Do not omit these semantic fields merely because an internal P&C ID is unknown. Internal IDs are resolved/generated by staging.

For pc_relationships records specifically, ALWAYS include human-readable endpoint labels as well as types:
- source_type: logical endpoint type (entity, asset, mobile_asset, geography, event)
- source_name: researched/canonical human-readable source name
- source_id: canonical P&C ID only when supplied in canonical context and deterministically matched; otherwise omit/null
- relationship_type: e.g. operates, owns, invested_in, manages, controls
- target_type: logical endpoint type
- target_name: researched/canonical human-readable target name
- target_id: canonical P&C ID only when supplied in canonical context and deterministically matched; otherwise omit/null
Do not return a pc_relationships proposal without source_name and target_name.
"""


def _jsonable(v):
    """Convert pandas / Excel / Python values into PostgREST-safe JSON values."""
    if isinstance(v, dict):
        return {str(k): _jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple, set)):
        return [_jsonable(x) for x in v]

    if isinstance(v, pd.Timestamp):
        return None if pd.isna(v) else v.isoformat()
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)

    if hasattr(v, "item") and not isinstance(v, (str, bytes, bytearray)):
        try:
            item = v.item()
            if item is not v:
                return _jsonable(item)
        except Exception:
            pass

    try:
        if pd.isna(v):
            return None
    except Exception:
        pass

    return v


def _record_key(payload, natural_key=""):
    if natural_key:
        return str(natural_key)
    if isinstance(payload,dict):
        for k in (
            "entity_id","asset_id","mobile_asset_id","relationship_id","event_id","event_link_id",
            "transaction_id","route_id","chokepoint_id","market_instrument_id",
            "trade_flow_id","supply_series_id","observation_id"
        ):
            if payload.get(k):
                return str(payload[k])
        for k in ("name","title","route_name"):
            if payload.get(k):
                return str(payload[k])
    return str(uuid.uuid4())


def _prepare_staged_job_for_resolution(sb, job_id):
    """Backfill logical entity type/source key on staged rows before SQL 010 resolution.

    AI research historically staged target_table but not target_entity_type. SQL 010
    requires the logical entity type to choose match rules. This helper repairs both
    new and already-staged jobs using pc_meta_entity_types without touching canonical data.
    Relationship rows remain relationship proposals and are not forced through entity resolution.
    """
    meta_map=_meta_table_map(sb)
    try:
        rows=(sb.table("pc_staged_records")
              .select("staged_record_id,target_table,target_entity_type,source_record_key,natural_key")
              .eq("ingestion_job_id",str(job_id)).limit(5000).execute().data or [])
    except Exception:
        return {"updated":0,"resolvable":0,"relationship_rows":0}

    updated=0
    resolvable=0
    relationship_rows=0
    for row in rows:
        table=row.get("target_table")
        meta=meta_map.get(table) or {}
        logical=meta.get("entity_type")
        patch={}
        if logical:
            resolvable+=1
            if not row.get("target_entity_type"):
                patch["target_entity_type"]=logical
        elif table in {"pc_relationships","pc_event_links"}:
            relationship_rows+=1
            if not row.get("target_entity_type"):
                patch["target_entity_type"]="relationship" if table=="pc_relationships" else "event_link"
        if not row.get("source_record_key"):
            patch["source_record_key"]=row.get("natural_key") or str(row.get("staged_record_id"))
        if patch:
            sb.table("pc_staged_records").update(patch).eq("staged_record_id",row["staged_record_id"]).execute()
            updated+=1
    return {"updated":updated,"resolvable":resolvable,"relationship_rows":relationship_rows}


def stage_ai_result(sb, job_id, result):
    """Stage structured AI result, attach model metadata, and resolve registered entities."""
    records=(result or {}).get("records") or []
    staged=[]
    rejected=0
    meta_map=_meta_table_map(sb)

    for rec in records:
        if not isinstance(rec,dict):
            rejected+=1
            continue

        table=str(rec.get("target_table") or "").strip()
        payload=rec.get("payload")

        if table not in AI_ALLOWED_TABLES or not isinstance(payload,dict):
            rejected+=1
            continue

        meta=meta_map.get(table) or {}
        logical=meta.get("entity_type")
        if not logical and table=="pc_event_links":
            logical="event_link"
        elif not logical and table=="pc_relationships":
            logical="relationship"

        natural_key=_record_key(payload,rec.get("natural_key") or "")
        staged.append({
            "ingestion_job_id":job_id,
            "target_entity_type":logical,
            "target_table":table,
            "source_record_key":natural_key,
            "natural_key":natural_key,
            "action":"REVIEW",
            "payload":_jsonable(payload),
            "confidence":rec.get("confidence"),
            "validation_status":"pending",
            "review_status":"pending",
            "resolution_status":"UNRESOLVED",
        })

    for i in range(0,len(staged),100):
        sb.table("pc_staged_records").insert(staged[i:i+100]).execute()

    resolution={}
    if staged:
        prep=_prepare_staged_job_for_resolution(sb,job_id)
        resolution["prepared"]=prep
        # SQL 010 handles registered canonical entity tables.
        if prep.get("resolvable"):
            try:
                resolution["entities"]=_process_job_resolution(sb,job_id)
            except Exception as exc:
                resolution["entity_resolution_error"]=str(exc)
        # SQL 011/012 currently specializes event-link relationships.
        if any(r.get("target_table")=="pc_event_links" for r in staged):
            try:
                resolution["event_relationships"]=_process_relationship_backlog(sb,job_id)
            except Exception as exc:
                resolution["relationship_resolution_error"]=str(exc)

    return len(staged),rejected,resolution


# Canonical columns that this admin is allowed to send to selected tables.
# Unknown AI/research fields are preserved in metadata instead of being sent
# as non-existent PostgREST columns.
TABLE_WRITE_COLUMNS = {
    "pc_logistics_facilities": {
        "asset_id","facility_type","owner_entity_id","operator_entity_id",
        "area_sqm","rail_connected","customs_bonded","source_id","metadata"
    },
    "pc_energy_assets": {
        "asset_id","energy_asset_type","operator_entity_id","owner_entity_id",
        "operational_status","source_id","metadata"
    },
    "pc_industrial_assets": {
        "asset_id","industrial_asset_type","operator_entity_id","owner_entity_id",
        "operational_status","source_id","metadata"
    },
}

PARENT_ASSET_FIELDS = {
    "name","asset_name","facility_name","terminal_name","port_name","hub_name",
    "country","city","region_city","latitude","longitude","status","operational_status"
}

def _canonicalize_extension_payload(row, payload):
    """Split AI research payload into parent-asset fields and extension fields.

    Non-schema research fields are retained in extension metadata so no evidence
    is lost and PostgREST never receives unknown columns such as `capacity`
    or `city` for pc_logistics_facilities.
    """
    table = str(row.get("target_table") or "")
    if table not in TABLE_WRITE_COLUMNS or not isinstance(payload, dict):
        return payload, {}

    allowed = TABLE_WRITE_COLUMNS[table]
    clean = {}
    overflow = {}
    parent = {}

    existing_meta = payload.get("metadata")
    if isinstance(existing_meta, dict):
        clean["metadata"] = dict(existing_meta)
    else:
        clean["metadata"] = {}

    for key, value in payload.items():
        if key == "metadata":
            continue

        if key in allowed:
            clean[key] = value
        elif key in PARENT_ASSET_FIELDS:
            parent[key] = value
        else:
            overflow[key] = value

    # Preserve every unsupported research field instead of dropping it.
    if overflow:
        clean["metadata"].setdefault("research_attributes", {}).update(overflow)

    if parent:
        clean["metadata"].setdefault("parent_asset_attributes", {}).update(parent)

    return clean, parent


def _parent_asset_from_payload(row, payload):
    """Build a parent pc_assets record using research fields when available."""
    table = row.get("target_table")
    if table not in {"pc_logistics_facilities","pc_energy_assets","pc_industrial_assets"}:
        return None

    clean, parent = _canonicalize_extension_payload(row, payload)
    if clean.get("asset_id"):
        return None

    name = (
        parent.get("name")
        or parent.get("asset_name")
        or parent.get("facility_name")
        or parent.get("terminal_name")
        or parent.get("port_name")
        or parent.get("hub_name")
        or _name_from_staged(row, payload)
    )
    country = parent.get("country") or _country_from_staged(row, payload)
    city = parent.get("city") or parent.get("region_city")

    if table == "pc_logistics_facilities":
        asset_type = "Logistics facility"
    elif table == "pc_energy_assets":
        asset_type = "Energy infrastructure"
    else:
        asset_type = "Industrial asset"

    plan = {
        "asset_id": _deterministic_asset_id(name, country or "", asset_type),
        "name": name,
        "asset_type": asset_type,
        "country": country,
        "region_city": city,
        "status": parent.get("status") or parent.get("operational_status"),
        "record_status": "verified",
        "metadata": {
            "created_from_staged_record": row.get("staged_record_id"),
            "ai_canonicalization": True,
            "natural_key": row.get("natural_key"),
        },
    }

    # Keep only non-empty values so we don't overwrite good canonical data with nulls.
    return {k:v for k,v in plan.items() if v not in (None,"")}


def _ensure_parent_asset_schema_safe(sb, row, payload):
    """Create/link the parent asset and return a schema-safe extension payload."""
    clean, parent_attrs = _canonicalize_extension_payload(row, payload)
    plan = _parent_asset_from_payload(row, payload)

    if not plan:
        return clean, False

    # Reuse an existing exact-name asset where sensible.
    try:
        hits = (
            sb.table("pc_assets")
            .select("asset_id,name,country,region_city,asset_type")
            .eq("name", plan["name"])
            .limit(20)
            .execute()
            .data or []
        )
        if plan.get("country"):
            country = str(plan["country"]).strip().casefold()
            same = [
                x for x in hits
                if not x.get("country")
                or str(x.get("country")).strip().casefold() == country
            ]
            if same:
                plan["asset_id"] = same[0]["asset_id"]
        elif hits:
            plan["asset_id"] = hits[0]["asset_id"]
    except Exception:
        pass

    sb.table("pc_assets").upsert(plan, on_conflict="asset_id").execute()

    clean["asset_id"] = plan["asset_id"]
    clean.setdefault("metadata", {})
    clean["metadata"]["canonical_parent_asset_id"] = plan["asset_id"]

    return clean, True
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

    # For extension tables, first separate parent-asset attributes from extension
    # attributes and move unsupported research fields into metadata. This prevents
    # PostgREST errors such as "column capacity/city not found".
    if table in TABLE_WRITE_COLUMNS:
        payload,parent_created=_ensure_parent_asset_schema_safe(sb,row,payload)
    else:
        parent_created=False

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


def _job_control_panel(job, key_prefix="jobctl"):
    """Compact recovery controls for an ingestion job."""
    if not job:
        return
    jid=str(job.get("ingestion_job_id") or "").strip()
    if not jid:
        return

    summ=_staging_summary(jid)
    stats=job.get("stats") if isinstance(job.get("stats"),dict) else {}
    reported=stats.get("rows")
    if reported is None and isinstance(stats.get("tables"),dict):
        try:
            reported=sum(int(v or 0) for v in stats["tables"].values())
        except Exception:
            reported="—"

    st.markdown(f"#### {job.get('title') or jid}")
    c1,c2,c3,c4,c5=st.columns(5)
    c1.metric("Reported",reported if reported is not None else "—")
    c2.metric("Staged",summ.get("total",0))
    c3.metric("Ready",summ.get("ready",0))
    c4.metric("Applied",summ.get("applied",0))
    c5.metric("Exceptions",(summ.get("unresolved",0) or 0)+(summ.get("ambiguous",0) or 0)+(summ.get("partial",0) or 0))

    b1,b2,b3,b4,b5=st.columns(5)

    if b1.button("Open job",key=f"{key_prefix}_open_{jid}"):
        st.session_state["selected_ingestion_job_id"]=jid
        st.session_state["selected_ingestion_job_title"]=job.get("title")
        st.success(f"Selected job {jid}. Open AI Research → Run & reconcile.")

    if b2.button("Open staging rows",key=f"{key_prefix}_stage_{jid}"):
        try:
            rows=(sb.table("pc_staged_records")
                  .select("*")
                  .eq("ingestion_job_id",jid)
                  .order("created_at",desc=False)
                  .limit(5000).execute().data or [])
            st.session_state[f"{key_prefix}_staging_rows_{jid}"]=rows
        except Exception as exc:
            st.error(f"Could not load staging rows: {exc}")

    if b3.button("Run reconciliation",key=f"{key_prefix}_recon_{jid}"):
        try:
            result=_run_reconciliation(jid)
            st.success("Reconciliation completed.")
            if result is not None:
                st.write(result)
        except Exception as exc:
            st.error(f"Reconciliation failed: {exc}")

    if b4.button("Retry staging",key=f"{key_prefix}_retry_{jid}"):
        st.session_state["retry_staging_job_id"]=jid
        st.warning(
            "Retry staging selected. Power Admin will only restage if the original import "
            "payload/source is still available. No staging rows are fabricated."
        )
        st.json({
            "ingestion_job_id":jid,
            "source_scope":job.get("source_scope"),
            "stats":stats,
        })

    if b5.button("Mark failed",key=f"{key_prefix}_fail_{jid}"):
        st.session_state[f"{key_prefix}_confirm_fail_{jid}"]=True

    if st.session_state.get(f"{key_prefix}_confirm_fail_{jid}"):
        st.warning("Mark this job failed? This does not delete staged or applied records.")
        y,n=st.columns(2)
        if y.button("Yes, mark failed",key=f"{key_prefix}_fail_yes_{jid}"):
            try:
                sb.table("pc_ingestion_jobs").update({
                    "status":"failed",
                    "error_text":"Marked failed manually from Power Admin recovery console"
                }).eq("ingestion_job_id",jid).execute()
                try:
                    sb.table("pc_workflow_runs").update({
                        "status":"failed"
                    }).eq("ingestion_job_id",jid).execute()
                except Exception:
                    pass
                st.session_state[f"{key_prefix}_confirm_fail_{jid}"]=False
                st.success("Job marked failed.")
            except Exception as exc:
                st.error(f"Could not mark job failed: {exc}")
        if n.button("Cancel",key=f"{key_prefix}_fail_no_{jid}"):
            st.session_state[f"{key_prefix}_confirm_fail_{jid}"]=False

    sk=f"{key_prefix}_staging_rows_{jid}"
    if sk in st.session_state:
        rows=st.session_state[sk]
        st.caption(f"Showing {len(rows)} staged row(s).")
        dataframe(rows)


def _job_apply_candidates(job_id):
    """Return job-scoped staged rows that are resolution-ready and safe to apply."""
    if not sb or not job_id:
        return [], []
    try:
        rows=(sb.table("pc_staged_records")
              .select("staged_record_id,ingestion_job_id,target_entity_type,target_table,natural_key,source_record_key,action,confidence,validation_status,review_status,resolution_status,resolved_entity_id,resolution_method,resolution_confidence,candidate_count,payload,current_record,source_id,created_at")
              .eq("ingestion_job_id",job_id)
              .limit(10000).execute().data or [])
    except Exception as exc:
        return [], [{"record":"<query>","error":str(exc)}]

    candidates=[]
    blocked=[]
    for r in rows:
        review=str(r.get("review_status") or "pending").lower()
        if review in {"applied","rejected","needs_changes"}:
            continue
        resolution=str(r.get("resolution_status") or "UNRESOLVED").upper()
        if resolution not in {"READY","MATCHED","NEW"}:
            blocked.append({
                "record":r.get("natural_key"),
                "table":r.get("target_table"),
                "resolution_status":resolution,
                "reason":"not resolution-ready",
            })
            continue
        try:
            v=validate_staged_for_bulk(sb,r)
        except Exception as exc:
            blocked.append({
                "record":r.get("natural_key"),
                "table":r.get("target_table"),
                "resolution_status":resolution,
                "reason":f"validation error: {exc}",
            })
            continue
        if v.get("safe"):
            candidates.append((r,v))
        else:
            blocked.append({
                "record":r.get("natural_key"),
                "table":r.get("target_table"),
                "resolution_status":resolution,
                "reason":v.get("risk") or "not safe",
            })
    return candidates, blocked


def _approve_and_apply_job_safe(job_id):
    """Approve then apply all safe, resolution-ready staged rows for one job."""
    candidates, blocked=_job_apply_candidates(job_id)
    applied=0
    approved=0
    failed=[]
    for r,v in candidates:
        try:
            if str(r.get("review_status") or "pending").lower()!="approved":
                sb.table("pc_staged_records").update({
                    "review_status":"approved",
                    "validation_status":"reviewed",
                }).eq("staged_record_id",r["staged_record_id"]).execute()
                r["review_status"]="approved"
                approved+=1
            apply_staged_record(sb,r,r.get("payload") or {})
            applied+=1
        except Exception as exc:
            failed.append({
                "record":r.get("natural_key"),
                "table":r.get("target_table"),
                "error":str(exc),
            })
    return {
        "safe_candidates":len(candidates),
        "approved_now":approved,
        "applied":applied,
        "failed":len(failed),
        "blocked":len(blocked),
        "failures":failed,
        "blocked_rows":blocked,
    }



def _finalize_already_exists_rows(job_id):
    """Treat ALREADY_EXISTS as a successful no-op rather than a blocked record."""
    if not sb or not job_id:
        return 0
    try:
        rows=(sb.table("pc_staged_records")
              .select("staged_record_id,resolution_status,review_status")
              .eq("ingestion_job_id",job_id)
              .eq("resolution_status","ALREADY_EXISTS")
              .limit(10000).execute().data or [])
        count=0
        for r in rows:
            if str(r.get("review_status") or "").lower()=="applied":
                continue
            sb.table("pc_staged_records").update({
                "review_status":"applied",
                "validation_status":"reviewed",
            }).eq("staged_record_id",r["staged_record_id"]).execute()
            count+=1
        return count
    except Exception:
        return 0


def _apply_safe_candidates_priority(job_id):
    """Apply safe rows in dependency order: parents before relationships/event-links."""
    candidates,blocked=_job_apply_candidates(job_id)
    priority={
        "pc_entities":10,
        "pc_assets":20,
        "pc_mobile_assets":20,
        "pc_events":30,
        "pc_transactions":40,
        "pc_transport_routes":45,
        "pc_relationships":80,
        "pc_event_links":90,
    }
    candidates=sorted(candidates,key=lambda rv:(priority.get(str(rv[0].get("target_table") or ""),60),str(rv[0].get("natural_key") or "")))
    applied=approved=0
    failed=[]
    for r,v in candidates:
        try:
            if str(r.get("review_status") or "pending").lower()!="approved":
                sb.table("pc_staged_records").update({
                    "review_status":"approved",
                    "validation_status":"reviewed",
                }).eq("staged_record_id",r["staged_record_id"]).execute()
                r["review_status"]="approved"
                approved+=1
            apply_staged_record(sb,r,r.get("payload") or {})
            applied+=1
        except Exception as exc:
            failed.append({
                "record":r.get("natural_key"),
                "table":r.get("target_table"),
                "error":str(exc),
            })
    return {
        "safe_candidates":len(candidates),
        "approved_now":approved,
        "applied":applied,
        "failed":len(failed),
        "failures":failed,
        "blocked_before_apply":len(blocked),
    }


def _try_sql_ingestion_repairs(job_id):
    """Use migration 037 helpers when installed; gracefully fall back otherwise."""
    out={}
    for name in (
        "pc_repair_staged_payload_v2",
        "pc_normalize_event_dependencies_v3",
        "pc_rewrite_dependency_endpoints_v4",
        "pc_finalize_already_exists_v2",
        "pc_requeue_resolved_event_links_v2",
    ):
        try:
            out[name]=sb.rpc(name,{"p_job_id":str(job_id)}).execute().data
        except Exception as exc:
            out[name+"_unavailable"]=str(exc)
    return out


def _process_job_automatically(job_id,max_passes=8):
    """Run ingestion in dependency-safe order until no further progress is possible.

    Critical ordering rule:
      generic reconcile -> repair/normalize identity states -> APPLY PARENTS ->
      resolve relationships -> normalize/requeue children -> APPLY CHILDREN.

    Never run a generic reconciliation between the final event normalization and
    parent apply, because older reconciliation SQL can reclassify a valid staged
    pc_events row back to INVALID.
    """
    report={"job_id":str(job_id),"passes":[],"total_applied_this_run":0}
    last_signature=None

    for pass_no in range(1,max_passes+1):
        step={"pass":pass_no}

        # A) Repair field mapping/provenance first.
        try:
            step["field_repair"]=_repair_staged_payloads_from_source(job_id)
        except Exception as exc:
            step["field_repair_error"]=str(exc)

        # B) Prepare canonical IDs before matching.
        try:
            step["prepare_ids"]=_prepare_canonical_candidates(sb,job_id)
        except Exception as exc:
            step["prepare_ids_error"]=str(exc)

        # C) Run the legacy/general resolver ONCE early in the pass.
        try:
            step["reconcile_early"]=_run_reconciliation(job_id)
        except Exception as exc:
            step["reconcile_early_error"]=str(exc)

        # D) IMPORTANT: normalize/repair identity state AFTER general reconcile.
        # Nothing that can downgrade pc_events runs between here and parent apply.
        try:
            step["sql_normalize_before_parent_apply"]=_try_sql_ingestion_repairs(job_id)
        except Exception as exc:
            step["sql_normalize_before_parent_apply_error"]=str(exc)
        try:
            step["identity_repair_before_parent_apply"]=_repair_identity_resolution_states(job_id)
        except Exception as exc:
            step["identity_repair_before_parent_apply_error"]=str(exc)
        step["already_exists_finalized_before_parent_apply"]=_finalize_already_exists_rows(job_id)

        # E) Apply all currently-safe records in parent-first priority order.
        parent_apply=_apply_safe_candidates_priority(job_id)
        step["parent_apply"]=parent_apply
        report["total_applied_this_run"]+=int(parent_apply.get("applied",0) or 0)

        # F) Parent writes may unlock event links and graph relationships.
        # First normalize dependencies against the canonical parents that now exist.
        try:
            step["sql_normalize_after_parent_apply"]=_try_sql_ingestion_repairs(job_id)
        except Exception as exc:
            step["sql_normalize_after_parent_apply_error"]=str(exc)

        try:
            step["event_links"]=_process_relationship_backlog(sb,job_id)
        except Exception as exc:
            step["event_links_error"]=str(exc)
        try:
            step["relationships"]=_process_generic_relationship_backlog(sb,job_id)
        except Exception as exc:
            step["relationships_error"]=str(exc)

        # G) Re-run dependency normalizers AFTER relationship processors because
        # those processors can leave children BROKEN_REFERENCE/PARTIAL.
        # Do NOT call the generic reconciliation RPC here.
        try:
            step["sql_normalize_children"]=_try_sql_ingestion_repairs(job_id)
        except Exception as exc:
            step["sql_normalize_children_error"]=str(exc)
        step["already_exists_finalized_children"]=_finalize_already_exists_rows(job_id)

        # H) Apply newly-safe child links/relationships.
        child_apply=_apply_safe_candidates_priority(job_id)
        step["child_apply"]=child_apply
        report["total_applied_this_run"]+=int(child_apply.get("applied",0) or 0)

        # I) Final normalization only. Again, no generic reconcile at the tail.
        try:
            step["sql_normalize_final"]=_try_sql_ingestion_repairs(job_id)
        except Exception as exc:
            step["sql_normalize_final_error"]=str(exc)
        step["already_exists_finalized_final"]=_finalize_already_exists_rows(job_id)

        safe_after,blocked_after=_job_apply_candidates(job_id)
        summ=_staging_summary(job_id)
        step["summary"]={
            "staged":summ.get("total",0),
            "applied":summ.get("wf_applied",summ.get("applied",0)),
            "safe_now":len(safe_after),
            "blocked_now":len(blocked_after),
            "exceptions":summ.get("wf_exceptions",(summ.get("partial",0) or 0)+(summ.get("unresolved",0) or 0)+(summ.get("ambiguous",0) or 0)),
        }
        report["passes"].append(step)

        signature=(
            int(step["summary"]["applied"] or 0),
            int(step["summary"]["safe_now"] or 0),
            int(step["summary"]["blocked_now"] or 0),
            int(step["summary"]["exceptions"] or 0),
        )

        # Stop if finished or if this pass made no state progress.
        if step["summary"]["safe_now"]==0 and step["summary"]["blocked_now"]==0 and step["summary"]["exceptions"]==0:
            report["outcome"]="complete"
            break

        applied_this_pass=(
            int((parent_apply or {}).get("applied",0) or 0)
            + int((child_apply or {}).get("applied",0) or 0)
        )
        finalized_this_pass=(
            int(step.get("already_exists_finalized_before_parent_apply",0) or 0)
            + int(step.get("already_exists_finalized_children",0) or 0)
            + int(step.get("already_exists_finalized_final",0) or 0)
        )
        step["progress"]={
            "applied_this_pass":applied_this_pass,
            "already_exists_finalized_this_pass":finalized_this_pass,
        }

        if signature==last_signature and applied_this_pass==0 and finalized_this_pass==0:
            report["outcome"]="manual_review_required"
            break
        last_signature=signature
    else:
        report["outcome"]="max_passes_reached"

    report["final_summary"]=_staging_summary(job_id)
    safe_final,blocked_final=_job_apply_candidates(job_id)
    report["safe_remaining"]=len(safe_final)
    report["blocked_remaining"]=len(blocked_final)
    report["blocked_rows"]=blocked_final[:500]
    return report


def _qa_applied_job(job_id):
    """Check that applied staging rows can be found in their canonical tables."""
    if not sb or not job_id:
        return {"checked":0,"found":0,"missing":0,"errors":[]}
    try:
        rows=(sb.table("pc_staged_records")
              .select("staged_record_id,target_table,natural_key,payload,review_status")
              .eq("ingestion_job_id",job_id)
              .eq("review_status","applied")
              .limit(10000).execute().data or [])
    except Exception as exc:
        return {"checked":0,"found":0,"missing":0,"errors":[str(exc)]}

    found=0
    missing=[]
    errors=[]
    for r in rows:
        table=str(r.get("target_table") or "")
        payload=r.get("payload") if isinstance(r.get("payload"),dict) else {}
        conflict=APPLY_CONFLICT_KEYS.get(table)
        keys=[x.strip() for x in conflict.split(",")] if conflict else []
        filters={k:payload.get(k) for k in keys if payload.get(k) not in (None,"")}
        if not table or not filters or len(filters)!=len(keys):
            errors.append(f"{r.get('natural_key')}: no complete apply/conflict key")
            continue
        try:
            q=sb.table(table).select(",".join(keys)).limit(1)
            for k,v in filters.items():
                q=q.eq(k,v)
            hit=q.execute().data or []
            if hit:
                found+=1
            else:
                missing.append({
                    "record":r.get("natural_key"),
                    "table":table,
                    "key":filters,
                })
        except Exception as exc:
            errors.append(f"{r.get('natural_key')}: {exc}")
    return {
        "checked":len(rows),
        "found":found,
        "missing":len(missing),
        "missing_rows":missing,
        "errors":errors,
    }


def _workflow_step_header(step_no, title, state="pending", detail=None):
    """Render a visual workflow step header with clear completion state."""
    state=str(state or "pending").lower()
    if state=="complete":
        icon="✅"
        label="COMPLETED"
        tone="success"
    elif state=="active":
        icon="🟢"
        label="READY"
        tone="success"
    elif state=="warning":
        icon="🟠"
        label="REVIEW"
        tone="warning"
    elif state=="blocked":
        icon="⛔"
        label="BLOCKED"
        tone="error"
    else:
        icon="⚪"
        label="PENDING"
        tone="info"

    st.markdown(f"### {icon} {step_no}. {title}")
    msg=f"{label}"
    if detail:
        msg += f" · {detail}"
    if tone=="success":
        st.success(msg)
    elif tone=="warning":
        st.warning(msg)
    elif tone=="error":
        st.error(msg)
    else:
        st.info(msg)


def _repair_staged_payloads_from_source(job_id):
    """Repair already-staged bulk rows whose important fields were stranded in metadata.source_payload."""
    if not sb or not job_id:
        return {"checked":0,"updated":0,"unchanged":0,"errors":[]}
    try:
        rows=(sb.table("pc_staged_records")
              .select("staged_record_id,target_table,payload")
              .eq("ingestion_job_id",job_id)
              .limit(10000).execute().data or [])
    except Exception as exc:
        return {"checked":0,"updated":0,"unchanged":0,"errors":[str(exc)]}

    updated=0
    unchanged=0
    errors=[]
    fields_by_table={
        "pc_entities":["entity_id","name","entity_type","subtype","country","hq_country","hq_location","status","source_url","notes"],
        "pc_assets":["asset_id","name","asset_type","subtype","country","region_city","owner_entity_id","operator_entity_id","status","source_url","notes"],
        "pc_mobile_assets":["mobile_asset_id","name","asset_type","subtype","imo","mmsi","call_sign","flag","build_year","owner_entity_id","operator_entity_id","manager_entity_id","status","source_url","notes"],
        "pc_events":["event_id","event_type","event_domain","event_family","severity","status","mode","countries","location","title","description","operational_impact","commercial_impact","confidence","source_url"],
        "pc_event_links":["event_link_id","event_id","linked_type","linked_id","relationship","source_url"],
        "pc_relationships":["relationship_id","source_type","source_id","relationship_type","target_type","target_id","confidence","source_url","notes"],
    }

    for r in rows:
        payload=r.get("payload") if isinstance(r.get("payload"),dict) else {}

        raw_meta=payload.get("metadata")
        if isinstance(raw_meta,dict):
            meta=dict(raw_meta)
        elif isinstance(raw_meta,str):
            parsed=_jsonish(raw_meta)
            meta=dict(parsed) if isinstance(parsed,dict) else {}
        else:
            meta={}

        raw_source_payload=meta.get("source_payload")
        if isinstance(raw_source_payload,dict):
            source_payload=dict(raw_source_payload)
        elif isinstance(raw_source_payload,str):
            parsed=_jsonish(raw_source_payload)
            source_payload=dict(parsed) if isinstance(parsed,dict) else {}
        else:
            source_payload={}

        changed=False

        for f in fields_by_table.get(str(r.get("target_table") or ""),[]):
            if payload.get(f) in (None,"") and source_payload.get(f) not in (None,""):
                payload[f]=source_payload.get(f)
                changed=True

        # Promote source provenance.
        src=payload.get("source_url") or source_payload.get("source_url") or meta.get("source_url")
        if src:
            if payload.get("source_url") in (None,""):
                payload["source_url"]=src
                changed=True
            if meta.get("source_url") in (None,""):
                meta["source_url"]=src
                changed=True

        rs=source_payload.get("research_sources")
        if rs:
            parsed=_jsonish(rs)
            if isinstance(parsed,list):
                vals=parsed
            elif isinstance(parsed,str):
                vals=[x.strip() for x in re.split(r"\\s*[;|]\\s*",parsed) if x.strip()]
            else:
                vals=[parsed]
            current=meta.get("research_sources") if isinstance(meta.get("research_sources"),list) else []
            before=len(current)
            for u in vals:
                if u and u not in current:
                    current.append(u)
            if len(current)!=before:
                meta["research_sources"]=current
                changed=True

        # Recover source provenance from metadata for older staged rows.
        if payload.get("source_url") in (None,""):
            rs=meta.get("research_sources")
            if isinstance(rs,list):
                first_url=next(
                    (x for x in rs if isinstance(x,str) and x.strip().lower().startswith(("http://","https://"))),
                    None
                )
                if first_url:
                    payload["source_url"]=first_url
                    meta.setdefault("source_url",first_url)
                    changed=True

        # Conservative required-type recovery.
        table=str(r.get("target_table") or "")
        if table=="pc_entities" and payload.get("entity_type") in (None,""):
            subtype=str(payload.get("subtype") or source_payload.get("subtype") or "").casefold()
            if any(k in subtype for k in ["government","municipality","authority","agency"]):
                payload["entity_type"]="government_entity"
            elif any(k in subtype for k in ["institutional_investor","pension_fund"]):
                payload["entity_type"]="institutional_investor"
            else:
                payload["entity_type"]="company"
            changed=True

        if table=="pc_assets" and payload.get("asset_type") in (None,""):
            subtype=str(payload.get("subtype") or source_payload.get("subtype") or "").casefold()
            if "terminal" in subtype:
                payload["asset_type"]="terminal"
            elif "port" in subtype:
                payload["asset_type"]="port"
            elif "rail" in subtype or "yard" in subtype:
                payload["asset_type"]="rail_asset"
            else:
                payload["asset_type"]="infrastructure_asset"
            changed=True

        if table=="pc_mobile_assets" and payload.get("asset_type") in (None,""):
            payload["asset_type"]="vessel"
            changed=True

        if meta:
            payload["metadata"]=meta

        if changed:
            try:
                sb.table("pc_staged_records").update({
                    "payload":_jsonable(payload),
                    "validation_status":"pending",
                }).eq("staged_record_id",r["staged_record_id"]).execute()
                updated+=1
            except Exception as exc:
                errors.append(f"{r.get('staged_record_id')}: {exc}")
        else:
            unchanged+=1


    return {"checked":len(rows),"updated":updated,"unchanged":unchanged,"errors":errors}


def _repair_identity_resolution_states(job_id):
    """Restore obvious identity rows to MATCHED or NEW without canonical writes."""
    if not sb or not job_id:
        return {"checked":0,"updated":0,"matched":0,"new":0,"skipped":0,"errors":[]}

    identity_tables={"pc_entities","pc_assets","pc_mobile_assets","pc_events"}
    try:
        rows=(sb.table("pc_staged_records")
              .select("staged_record_id,target_table,payload,resolution_status,review_status")
              .eq("ingestion_job_id",job_id)
              .limit(10000).execute().data or [])
    except Exception as exc:
        return {"checked":0,"updated":0,"matched":0,"new":0,"skipped":0,"errors":[str(exc)]}

    checked=updated=matched=new_count=skipped=0
    errors=[]
    for r in rows:
        table=str(r.get("target_table") or "")
        if table not in identity_tables:
            continue
        if str(r.get("review_status") or "").lower()=="applied":
            continue
        status=str(r.get("resolution_status") or "UNRESOLVED").upper()
        if status not in {"INVALID","UNRESOLVED","PARTIAL","BROKEN_REFERENCE"}:
            continue

        checked+=1
        payload=r.get("payload") if isinstance(r.get("payload"),dict) else {}
        schema_ok,_missing=_schema_valid(table,payload)
        if not schema_ok or _source_count(payload)<1:
            skipped+=1
            continue

        conflict=APPLY_CONFLICT_KEYS.get(table)
        keys=[x.strip() for x in conflict.split(",")] if conflict else []
        if not keys or not all(payload.get(k) not in (None,"") for k in keys):
            skipped+=1
            continue

        try:
            q=sb.table(table).select(",".join(keys)).limit(1)
            for k in keys:
                q=q.eq(k,payload[k])
            hit=q.execute().data or []

            update={
                "review_status":"pending",
                "validation_status":"pending",
                "resolution_confidence":1.0,
                "candidate_count":1 if hit else 0,
            }
            if hit:
                update.update({
                    "resolution_status":"MATCHED",
                    "resolution_method":"exact_conflict_key",
                    "resolved_entity_id":str(payload[keys[0]]),
                })
                matched+=1
            else:
                update.update({
                    "resolution_status":"NEW",
                    "resolution_method":"explicit_id_new",
                    "resolved_entity_id":None,
                })
                new_count+=1

            sb.table("pc_staged_records").update(update).eq(
                "staged_record_id",r["staged_record_id"]
            ).execute()
            updated+=1
        except Exception as exc:
            errors.append(f"{r.get('staged_record_id')}: {exc}")

    return {
        "checked":checked,"updated":updated,"matched":matched,
        "new":new_count,"skipped":skipped,"errors":errors
    }


def _repair_obvious_job_blockers(job_id):
    """Repair legacy mapping/provenance/type issues and preserve repaired identity states.

    Important ordering: the database reconciliation RPC can classify pc_events as INVALID
    even when the staged event is schema-complete and source-backed. Therefore run the
    general reconciliation first, then perform the conservative exact-ID identity repair
    last. This keeps valid NEW/MATCHED parent identities/events available for safe apply.
    Child event_links are resolved only after their parent event has been applied canonically.
    """
    result={"field_repair":_repair_staged_payloads_from_source(job_id)}

    try:
        result["reconcile"]=_run_reconciliation(job_id)
    except Exception as exc:
        result["reconcile_error"]=str(exc)

    # Run this AFTER the generic reconciliation so repaired NEW/MATCHED states are not
    # immediately overwritten back to INVALID by the RPC.
    result["identity_repair"]=_repair_identity_resolution_states(job_id)

    # Do not force child links READY before their canonical parents exist. The normal
    # Refresh action will resolve these after the parent identities/events are applied.
    return result


def _blocked_reason_summary(blocked_rows):
    by_reason={}
    by_table={}
    for r in blocked_rows or []:
        reason=str(r.get("reason") or "unknown").strip()
        table=str(r.get("table") or "unknown").strip()
        by_reason[reason]=by_reason.get(reason,0)+1
        by_table[table]=by_table.get(table,0)+1
    reason_rows=[{"reason":k,"count":v} for k,v in sorted(by_reason.items(),key=lambda x:(-x[1],x[0]))]
    table_rows=[{"table":k,"count":v} for k,v in sorted(by_table.items(),key=lambda x:(-x[1],x[0]))]
    return reason_rows,table_rows



def _apply_safe_parent_records(job_id):
    """Apply only safe parent records before retrying dependent child links."""
    safe, blocked=_job_apply_candidates(job_id)
    parent_tables={"pc_entities","pc_assets","pc_mobile_assets","pc_events"}
    parents=[item for item in safe if str(item[0].get("target_table") or "") in parent_tables]
    applied=0
    failed=[]
    for r,v in parents:
        try:
            if str(r.get("review_status") or "pending").lower()!="approved":
                sb.table("pc_staged_records").update({
                    "review_status":"approved",
                    "validation_status":"reviewed",
                }).eq("staged_record_id",r["staged_record_id"]).execute()
                r["review_status"]="approved"
            apply_staged_record(sb,r,r.get("payload") or {})
            applied+=1
        except Exception as exc:
            failed.append({
                "record":r.get("natural_key"),
                "table":r.get("target_table"),
                "error":str(exc),
            })
    return {
        "safe_parent_candidates":len(parents),
        "applied":applied,
        "failed":len(failed),
        "failures":failed,
    }


def _resolve_missing_parent_dependencies(job_id):
    """Apply safe parents first, then rerun dependency normalization/resolution."""
    result={}
    result["parent_apply"]=_apply_safe_parent_records(job_id)

    # After parent canonical writes, rerun SQL normalizers and relationship processors.
    try:
        result["sql_repairs"]=_try_sql_ingestion_repairs(job_id)
    except Exception as exc:
        result["sql_repairs_error"]=str(exc)
    try:
        result["event_links"]=_process_relationship_backlog(sb,job_id)
    except Exception as exc:
        result["event_links_error"]=str(exc)
    try:
        result["relationships"]=_process_generic_relationship_backlog(sb,job_id)
    except Exception as exc:
        result["relationships_error"]=str(exc)
    try:
        result["sql_repairs_after_relationships"]=_try_sql_ingestion_repairs(job_id)
    except Exception as exc:
        result["sql_repairs_after_relationships_error"]=str(exc)

    # Apply children that became safe.
    child_apply=_apply_safe_candidates_priority(job_id)
    result["child_apply"]=child_apply
    return result


# ===========================================================================
# Canonical ingestion v2 helpers
# ===========================================================================

CANONICAL_OBJECT_TABLES = {
    "pc_entities",
    "pc_assets",
    "pc_mobile_assets",
    "pc_events",
}
CANONICAL_EDGE_TABLES = {
    "pc_relationships",
    "pc_event_links",
}
CANONICAL_DIRECT_TABLES = {
    "pc_transactions",
    "pc_transport_routes",
    "pc_chokepoints",
    "pc_market_instruments",
    "pc_trade_flows",
    "pc_supply_series",
    "pc_observations",
}
CANONICAL_LOAD_TABLES = sorted(
    CANONICAL_OBJECT_TABLES | CANONICAL_EDGE_TABLES | CANONICAL_DIRECT_TABLES
)

CANONICAL_LOGICAL_TYPE = {
    "pc_entities":"entity",
    "pc_assets":"asset",
    "pc_mobile_assets":"mobile_asset",
    "pc_events":"event",
    "pc_relationships":"relationship",
    "pc_event_links":"event_link",
    "pc_transactions":"transaction",
    "pc_transport_routes":"route",
    "pc_chokepoints":"chokepoint",
    "pc_market_instruments":"market_instrument",
    "pc_trade_flows":"trade_flow",
    "pc_supply_series":"supply_series",
    "pc_observations":"observation",
}

def _canonical_processor_available():
    if not sb:
        return False
    try:
        # Calling with a random UUID is not safe because it mutates the job if present;
        # use pg function presence indirectly through a harmless RPC failure check only
        # when needed in the UI. The loader itself reports a clear RPC error.
        sb.table("pc_ingestion_jobs").select("ingestion_job_id").limit(1).execute()
        return True
    except Exception:
        return False

def _canonical_job_summary(job_id):
    rows=[]
    try:
        rows=(sb.table("pc_staged_records")
              .select("staged_record_id,target_table,resolution_status,review_status,resolution_method,resolved_entity_id,validation_status")
              .eq("ingestion_job_id",str(job_id))
              .limit(5000)
              .execute().data or [])
    except Exception:
        return {"total":0,"applied":0,"review":0,"invalid":0,"broken":0,"by_table":[]}, []

    total=len(rows)
    applied=sum(1 for r in rows if str(r.get("review_status") or "").lower()=="applied")
    review=sum(1 for r in rows if str(r.get("review_status") or "").lower()!="applied")
    invalid=sum(1 for r in rows if str(r.get("resolution_status") or "").upper()=="INVALID")
    broken=sum(1 for r in rows if str(r.get("resolution_status") or "").upper()=="BROKEN_REFERENCE")

    counts={}
    for r in rows:
        key=(r.get("target_table") or "unknown",
             r.get("resolution_status") or "PENDING",
             r.get("review_status") or "pending")
        counts[key]=counts.get(key,0)+1
    by_table=[
        {"target_table":k[0],"resolution_status":k[1],"review_status":k[2],"count":v}
        for k,v in sorted(counts.items())
    ]
    return {
        "total":total,
        "applied":applied,
        "review":review,
        "invalid":invalid,
        "broken":broken,
        "complete": total>0 and applied==total,
    }, by_table

def _canonical_process_job(job_id):
    """Single database entry point for the new ingestion architecture."""
    result=(sb.rpc(
        "pc_process_ingestion_job_v5",
        {"p_ingestion_job_id":str(job_id)}
    ).execute().data or {})
    return result

def _canonical_create_job(title, source_scope):
    payload={
        "job_type":"BATCH_IMPORT",
        "title":title,
        "source_scope":_jsonable(source_scope),
        "status":"running",
        "started_at":pd.Timestamp.utcnow().isoformat(),
        "stats":{"architecture":"canonical_upsert_v2"},
    }
    return sb.table("pc_ingestion_jobs").insert(payload).execute().data[0]

def _canonical_stage_records(job_id, sections_config):
    """Stage a whole workbook as one package.

    Workbook IDs remain package-local source keys. The database resolver decides
    whether each object maps to an existing canonical ID or requires creation.
    """
    staged=[]
    table_counts={}
    skipped_sections=[]

    for section,cfg in sections_config.items():
        if not cfg.get("include",True):
            skipped_sections.append(section)
            continue
        target=cfg["target"]
        df=cfg["df"]
        mapping=cfg["mapping"]
        logical=CANONICAL_LOGICAL_TYPE.get(target,target)

        for row_no,row in enumerate(df.to_dict("records"),1):
            payload=_payload_from_mapping(row,mapping,target)

            # DO NOT manufacture a canonical object ID here.
            # Existing workbook IDs are source/package keys only.
            nk=_natural_key_global(payload,target,row_no)

            staged.append({
                "ingestion_job_id":str(job_id),
                "target_entity_type":logical,
                "target_table":target,
                "source_record_key":f"{section}:{nk}",
                "natural_key":str(nk),
                "action":"UPSERT",
                "payload":_jsonable(payload),
                "resolution_status":"PENDING",
                "validation_status":"pending",
                "review_status":"pending",
            })
            table_counts[target]=table_counts.get(target,0)+1

    for i in range(0,len(staged),250):
        sb.table("pc_staged_records").insert(_jsonable(staged[i:i+250])).execute()

    return {
        "rows":len(staged),
        "tables":table_counts,
        "skipped_sections":skipped_sections,
    }

def _canonical_jobs(limit=100):
    try:
        return (sb.table("pc_ingestion_jobs")
                .select("ingestion_job_id,job_type,title,status,stats,error_text,source_scope,created_at,started_at,completed_at")
                .order("created_at",desc=True)
                .limit(limit)
                .execute().data or [])
    except Exception:
        return []

def _identity_hygiene_view(view_name,limit=500):
    try:
        return sb.table(view_name).select("*").limit(limit).execute().data or []
    except Exception as exc:
        return [{"error":str(exc),"view":view_name}]

def _pre_reload_gate():
    try:
        return sb.table("pc_v_pre_reload_gate").select("*").execute().data or []
    except Exception:
        return []

def _canonical_review_rows(job_id=None,limit=1000):
    try:
        q=(sb.table("pc_staged_records")
           .select("staged_record_id,ingestion_job_id,target_table,natural_key,resolution_status,resolution_method,candidate_count,resolved_entity_id,review_status,validation_status,payload,created_at")
           .neq("review_status","applied")
           .limit(limit))
        if job_id:
            q=q.eq("ingestion_job_id",str(job_id))
        return q.execute().data or []
    except Exception:
        return []

def _merge_canonical_object(object_type,survivor_id,duplicate_id,notes=""):
    return (sb.rpc(
        "pc_merge_canonical_object",
        {
            "p_object_type":object_type,
            "p_survivor_id":str(survivor_id).strip(),
            "p_duplicate_id":str(duplicate_id).strip(),
            "p_delete_duplicate":True,
            "p_notes":notes or "Confirmed duplicate merged in Power Admin",
        }
    ).execute().data or {})

def _suggest_canonical_table(section,df):
    target=_suggest_target_table(section,df)
    return target if target in CANONICAL_LOAD_TABLES else "pc_entities"



if page=="Canonical Home":
    title(
        "Canonical admin",
        "The normal path is now simple: ingest package → resolve/upsert canonical objects → write relationships/event links → QA."
    )
    if not sb:
        st.error("Supabase service connection required.")
    else:
        gate=_pre_reload_gate()
        blocking=sum(int(x.get("issue_count") or 0) for x in gate if x.get("severity")=="BLOCK")
        jobs=_canonical_jobs(100)
        review_jobs=[j for j in jobs if str(j.get("status") or "").lower()=="review"]

        c1,c2,c3,c4=st.columns(4)
        try: c1.metric("Entities",count_rows(sb,"pc_entities"))
        except Exception: c1.metric("Entities","—")
        try: c2.metric("Assets",count_rows(sb,"pc_assets"))
        except Exception: c2.metric("Assets","—")
        try: c3.metric("Mobile assets",count_rows(sb,"pc_mobile_assets"))
        except Exception: c3.metric("Mobile assets","—")
        c4.metric("Jobs needing review",len(review_jobs))

        if gate:
            if blocking:
                st.warning(
                    f"Canonical hygiene gate currently has {blocking} blocking issue(s). "
                    "Clean duplicate strong identifiers/fixed assets before the large workbook reload."
                )
            else:
                st.success("No blocking canonical-hygiene checks are currently reported.")
            dataframe(gate)
        else:
            st.info(
                "Pre-reload gate is not installed yet. Run migrations 043 v2, 044, 041 v2 and 045."
            )

        st.markdown("### Normal operating model")
        st.markdown(
            """
            **1. Objects first.** Companies, fixed assets, vessels/mobile assets and events are resolved against the canonical registry.

            **2. Existing means upsert.** Existing canonical objects are enriched; they are not recreated.

            **3. New means create once.** A new canonical ID is generated only when the object is genuinely absent and has enough identity evidence.

            **4. Graph second.** `pc_relationships` and `pc_event_links` are written only after their endpoints exist canonically.

            **5. Review is exceptional.** Only real ambiguity, insufficient identity, or an unsupported endpoint should remain for an analyst.
            """
        )

elif page=="Canonical Loader":
    title(
        "Canonical loader",
        "Load a workbook as one package. Workbook IDs are package-local keys; the database decides the canonical identity."
    )
    if not sb:
        st.error("Supabase service connection required.")
    else:
        gate=_pre_reload_gate()
        blockers=[x for x in gate if x.get("severity")=="BLOCK" and int(x.get("issue_count") or 0)>0]
        if blockers:
            st.warning(
                "The canonical registry currently has blocking hygiene issues. "
                "Small test packages can still be run, but clean these before large reloads."
            )
            dataframe(blockers)

        up=st.file_uploader(
            "Workbook / CSV / JSON",
            type=["xlsx","xls","csv","json"],
            key="canonical_loader_upload"
        )

        if up:
            try:
                sections,file_hash=_parse_multitable_upload(up)
                # README/instruction sheets are not data.
                sections={
                    k:v for k,v in sections.items()
                    if _norm_field(k) not in {"readme","instructions","instruction","notes"}
                    and not v.empty
                }
                st.caption(f"{len(sections)} data section(s) · SHA-256 {file_hash[:16]}…")

                configs={}
                for idx,(section,df) in enumerate(sections.items()):
                    with st.expander(f"{section} · {len(df):,} rows",expanded=True):
                        suggested=_suggest_canonical_table(section,df)
                        include=st.checkbox(
                            "Include this section",
                            value=True,
                            key=f"canon_include_{idx}"
                        )
                        target=st.selectbox(
                            "Canonical target",
                            CANONICAL_LOAD_TABLES,
                            index=CANONICAL_LOAD_TABLES.index(suggested),
                            key=f"canon_target_{idx}"
                        )
                        cols=_table_write_columns_live(sb,target)
                        mapping=_auto_column_mapping(list(df.columns),cols)
                        edited=st.data_editor(
                            mapping,
                            use_container_width=True,
                            hide_index=True,
                            column_config={
                                "Include":st.column_config.CheckboxColumn(),
                                "Canonical Field":st.column_config.SelectboxColumn(options=[""]+cols),
                            },
                            key=f"canon_map_{idx}"
                        )
                        st.caption("Preview")
                        dataframe(df.head(6).to_dict("records"))
                        configs[section]={
                            "include":include,
                            "target":target,
                            "df":df,
                            "mapping":edited,
                        }

                st.markdown("### What happens when you load")
                st.caption(
                    "The whole package is staged, then one canonical processor resolves/upserts objects first "
                    "and writes relationships/event links second. There is no manual reconcile/apply sequence."
                )

                if st.button(
                    "▶ Load and process canonical package",
                    type="primary",
                    use_container_width=True,
                    key="canonical_load_process"
                ):
                    with st.status("Loading package into the canonical ingestion engine…",expanded=True) as status:
                        job=_canonical_create_job(
                            up.name,
                            {
                                "architecture":"canonical_upsert_v2",
                                "file_sha256":file_hash,
                                "sections":{
                                    k:{
                                        "included":bool(v["include"]),
                                        "target_table":v["target"],
                                        "rows":len(v["df"]),
                                    }
                                    for k,v in configs.items()
                                },
                            }
                        )
                        jid=job["ingestion_job_id"]
                        staged=_canonical_stage_records(jid,configs)
                        st.write("Staged package",staged)

                        try:
                            result=_canonical_process_job(jid)
                            st.write("Canonical processor",result)
                            summary,by_table=_canonical_job_summary(jid)

                            if summary.get("complete"):
                                status.update(
                                    label=f"Package complete — {summary['applied']}/{summary['total']} records applied",
                                    state="complete",
                                    expanded=False
                                )
                            else:
                                status.update(
                                    label=(
                                        f"Package processed — {summary['applied']}/{summary['total']} applied; "
                                        f"{summary['review']} require review"
                                    ),
                                    state="complete",
                                    expanded=True
                                )
                            st.session_state["canonical_last_job"]=str(jid)
                            st.session_state[f"canonical_result_{jid}"]=result
                        except Exception as exc:
                            sb.table("pc_ingestion_jobs").update({
                                "status":"failed",
                                "completed_at":pd.Timestamp.utcnow().isoformat(),
                                "error_text":str(exc),
                            }).eq("ingestion_job_id",str(jid)).execute()
                            status.update(label="Canonical processor failed",state="error",expanded=True)
                            st.exception(exc)

                last=st.session_state.get("canonical_last_job")
                if last:
                    st.markdown("### Last package")
                    summ,by_table=_canonical_job_summary(last)
                    m1,m2,m3,m4=st.columns(4)
                    m1.metric("Total",summ.get("total",0))
                    m2.metric("Applied",summ.get("applied",0))
                    m3.metric("Review",summ.get("review",0))
                    m4.metric("Broken refs",summ.get("broken",0))
                    dataframe(by_table)

            except Exception as exc:
                st.exception(exc)

elif page=="Identity Hygiene":
    title(
        "Identity hygiene",
        "Audit canonical identity before high-volume reloads. Merge confirmed duplicates; keep spelling variants as aliases."
    )
    if not sb:
        st.error("Supabase service connection required.")
    else:
        gate=_pre_reload_gate()
        if gate:
            st.markdown("### Pre-reload gate")
            dataframe(gate)
        else:
            st.warning("Migration 045 is not installed or the gate view is unavailable.")

        tabs=st.tabs([
            "Fixed assets / ports",
            "Entities",
            "Vessels / mobile assets",
            "Merge confirmed duplicate",
            "Merge audit",
        ])

        with tabs[0]:
            st.markdown("#### Exact duplicate asset groups")
            dataframe(_identity_hygiene_view("pc_v_duplicate_asset_candidates",500))
            st.markdown("#### Fuzzy asset-name candidates")
            st.caption("Use this to find spelling variants such as Zayed / Zayad Port. Fuzzy matches are never auto-merged.")
            fuzzy=_identity_hygiene_view("pc_v_fuzzy_asset_name_candidates",1000)
            search=st.text_input("Filter asset-name candidates",value="zay",key="hygiene_asset_filter")
            if search.strip() and fuzzy and "error" not in fuzzy[0]:
                q=search.casefold()
                fuzzy=[
                    r for r in fuzzy
                    if q in str(r.get("name_a") or "").casefold()
                    or q in str(r.get("name_b") or "").casefold()
                ]
            dataframe(fuzzy)

        with tabs[1]:
            dataframe(_identity_hygiene_view("pc_v_duplicate_entity_candidates",500))

        with tabs[2]:
            st.markdown("#### Duplicate strong identifiers")
            dataframe(_identity_hygiene_view("pc_v_duplicate_mobile_asset_identifiers",500))
            st.markdown("#### Duplicate normalized mobile-asset names")
            dataframe(_identity_hygiene_view("pc_v_duplicate_mobile_asset_candidates",500))
            st.caption("Canonical maritime vessel display names are uppercase; aliases preserve incoming/source variants.")

        with tabs[3]:
            st.warning(
                "Merge only after confirming both IDs represent the same real-world object. "
                "The duplicate ID will be deleted after graph references are rewritten."
            )
            obj_type=st.selectbox(
                "Object type",
                ["asset","entity","mobile_asset","event"],
                key="merge_object_type"
            )
            survivor=st.text_input("Survivor canonical ID",key="merge_survivor")
            duplicate=st.text_input("Duplicate canonical ID",key="merge_duplicate")
            notes=st.text_area("Merge note",key="merge_note")
            confirm=st.checkbox(
                "I have confirmed these are the same real-world object",
                key="merge_confirm"
            )
            if st.button(
                "Merge duplicate into survivor",
                type="primary",
                disabled=not(confirm and survivor.strip() and duplicate.strip()),
                use_container_width=True
            ):
                try:
                    result=_merge_canonical_object(obj_type,survivor,duplicate,notes)
                    st.success("Canonical merge completed.")
                    st.json(result)
                except Exception as exc:
                    st.exception(exc)

        with tabs[4]:
            try:
                rows=(sb.table("pc_canonical_merge_audit")
                      .select("*")
                      .order("merged_at",desc=True)
                      .limit(500)
                      .execute().data or [])
            except Exception as exc:
                rows=[{"error":str(exc)}]
            dataframe(rows)

elif page=="Canonical Review":
    title(
        "Canonical review queue",
        "Only records the canonical processor could not resolve safely should appear here."
    )
    if not sb:
        st.error("Supabase service connection required.")
    else:
        jobs=_canonical_jobs(200)
        review_jobs=[
            j for j in jobs
            if str(j.get("status") or "").lower() in {"review","failed","running"}
        ]
        labels=["All review jobs"]+[
            f"{j.get('title') or j.get('job_type')} | {j.get('status')} | {j.get('ingestion_job_id')}"
            for j in review_jobs
        ]
        choice=st.selectbox("Job",labels,key="canonical_review_job")
        jid=None
        if choice!="All review jobs":
            jid=review_jobs[labels.index(choice)-1]["ingestion_job_id"]

        rows=_canonical_review_rows(jid,1500)
        if rows:
            reason_counts={}
            for r in rows:
                reason=str(r.get("resolution_method") or r.get("resolution_status") or "UNKNOWN")
                reason_counts[reason]=reason_counts.get(reason,0)+1

            c1,c2=st.columns([1,2])
            c1.metric("Records requiring review",len(rows))
            c2.caption(
                "Expected reasons are genuine ambiguity, insufficient identity, or a missing canonical endpoint."
            )
            dataframe([
                {"reason":k,"count":v}
                for k,v in sorted(reason_counts.items(),key=lambda x:(-x[1],x[0]))
            ])
            with st.expander("Show review records",expanded=True):
                dataframe(rows)

            if jid and st.button(
                "↻ Retry this job after corrections",
                type="primary",
                use_container_width=True,
                key=f"retry_canonical_{jid}"
            ):
                try:
                    result=_canonical_process_job(jid)
                    st.json(result)
                    st.rerun()
                except Exception as exc:
                    st.exception(exc)
        else:
            st.success("No unresolved canonical-ingestion records in the selected scope.")


elif page=="Dashboard":
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


elif page=="Database Coverage":
    title(
        "Database coverage",
        "Search the live Supabase canonical database to confirm whether ports, terminals, vessels, companies and events actually migrated."
    )

    if not sb:
        st.error("Supabase service connection required.")
    else:
        st.markdown("### Canonical database lookup")
        st.caption(
            "This searches canonical production tables, not Excel and not staging. "
            "Use it to verify that migrated records are genuinely present in Supabase."
        )

        c1,c2,c3 = st.columns([2,1,1])
        with c1:
            q = st.text_input(
                "Search name / title / IMO",
                placeholder="e.g. Beirut, Itaqui, Nador West Med, Montevideo, MSC NITA, 9084607"
            ).strip()
        with c2:
            scope = st.selectbox(
                "Coverage",
                ["All","Ports & assets","Companies","Vessels","Events"]
            )
        with c3:
            max_rows = st.selectbox("Max results", [25,50,100,250], index=1)

        def _contains(value, needle):
            return needle.casefold() in str(value or "").casefold()

        def _safe_query_rows(table, columns="*", limit=1000):
            try:
                return safe_rows(sb, table, columns, limit)
            except Exception:
                return []

        def _asset_is_portish(r):
            txt = " ".join(str(r.get(k) or "") for k in ("asset_type","subtype","name","region_city"))
            t = txt.casefold()
            return any(x in t for x in ("port","terminal","harbour","harbor","anchorage","jetty","quay"))

        if q:
            needle = q.casefold()
            asset_rows=[]
            entity_rows=[]
            vessel_rows=[]
            event_rows=[]

            if scope in ("All","Ports & assets"):
                rows = _safe_query_rows(
                    "pc_assets",
                    "asset_id,name,asset_type,subtype,country,region_city,latitude,longitude,owner_entity_id,operator_entity_id,status,record_status,data_quality,source_id,metadata",
                    3000
                )
                asset_rows = [
                    r for r in rows
                    if (_contains(r.get("name"), needle)
                        or _contains(r.get("country"), needle)
                        or _contains(r.get("region_city"), needle)
                        or _contains(r.get("asset_type"), needle)
                        or _contains(r.get("subtype"), needle))
                ]
                if scope=="Ports & assets":
                    # Keep non-port infrastructure if the user explicitly searched it;
                    # otherwise favor port-like results first.
                    asset_rows = sorted(asset_rows, key=lambda r: (not _asset_is_portish(r), str(r.get("name") or "")))

            if scope in ("All","Companies"):
                rows = _safe_query_rows(
                    "pc_entities",
                    "entity_id,name,entity_type,country,headquarters,parent_entity_id,status,record_status,source_id,metadata",
                    3000
                )
                entity_rows = [
                    r for r in rows
                    if (_contains(r.get("name"), needle)
                        or _contains(r.get("country"), needle)
                        or _contains(r.get("entity_type"), needle)
                        or _contains(r.get("headquarters"), needle))
                ]

            if scope in ("All","Vessels"):
                rows = _safe_query_rows(
                    "pc_mobile_assets",
                    "mobile_asset_id,name,mobile_type,imo,mmsi,flag,country,owner_entity_id,operator_entity_id,status,record_status,source_id,metadata",
                    5000
                )
                vessel_rows = [
                    r for r in rows
                    if (_contains(r.get("name"), needle)
                        or _contains(r.get("imo"), needle)
                        or _contains(r.get("mmsi"), needle)
                        or _contains(r.get("flag"), needle)
                        or _contains(r.get("mobile_type"), needle))
                ]

            if scope in ("All","Events"):
                rows = _safe_query_rows(
                    "pc_events",
                    "event_id,start_date,end_date,event_nature,event_domain,event_family,event_type,severity,status,mode,countries,location,title,description,trade_relevance,intelligence_relevance,trade_visible,intelligence_visible,alert_worthy,record_status,source_id,metadata",
                    5000
                )
                event_rows = [
                    r for r in rows
                    if (_contains(r.get("title"), needle)
                        or _contains(r.get("location"), needle)
                        or _contains(r.get("countries"), needle)
                        or _contains(r.get("event_type"), needle)
                        or _contains(r.get("description"), needle))
                ]

            total = len(asset_rows)+len(entity_rows)+len(vessel_rows)+len(event_rows)
            st.markdown("### Results")
            m1,m2,m3,m4,m5 = st.columns(5)
            m1.metric("Total matches", total)
            m2.metric("Assets / ports", len(asset_rows))
            m3.metric("Companies", len(entity_rows))
            m4.metric("Vessels", len(vessel_rows))
            m5.metric("Events", len(event_rows))

            if total == 0:
                st.warning(
                    "No canonical database match found. If the record exists only in an Excel workbook or staging queue, "
                    "it has not yet been migrated/applied to the live canonical database."
                )

            if asset_rows:
                st.markdown("#### Assets / ports")
                df = pd.DataFrame(asset_rows[:max_rows])
                preferred = [
                    "name","asset_type","subtype","country","region_city","latitude","longitude",
                    "status","record_status","data_quality","source_id","asset_id"
                ]
                cols=[c for c in preferred if c in df.columns]
                st.dataframe(df[cols], use_container_width=True, hide_index=True)

                selected_asset = st.selectbox(
                    "Open asset / port",
                    list(range(len(asset_rows[:max_rows]))),
                    format_func=lambda i: f"{asset_rows[i].get('name','')} · {asset_rows[i].get('country','')} · {asset_rows[i].get('asset_type','')}",
                    key="coverage_asset_select"
                )
                arow = asset_rows[selected_asset]
                with st.expander("Asset detail", expanded=False):
                    st.json(arow)

                aid=arow.get("asset_id")
                if aid:
                    st.markdown("##### Connected records")
                    cc1,cc2,cc3 = st.columns(3)

                    terminals=[]
                    try:
                        # Some terminal models are still represented as pc_assets; this looks for linked
                        # extension/logistics rows and event links conservatively.
                        terminals = safe_rows(sb,"pc_logistics_facilities","*",500,{"asset_id":aid})
                    except Exception:
                        terminals=[]

                    try:
                        links = safe_rows(sb,"pc_event_links","*",500,{"linked_id":aid})
                    except Exception:
                        links=[]

                    try:
                        gov = safe_rows(sb,"pc_governance_links","*",500,{"governed_id":aid})
                    except Exception:
                        gov=[]

                    cc1.metric("Logistics extensions",len(terminals))
                    cc2.metric("Event links",len(links))
                    cc3.metric("Governance links",len(gov))

                    if terminals:
                        st.markdown("**Logistics / terminal extensions**")
                        dataframe(terminals)
                    if links:
                        st.markdown("**Event links**")
                        dataframe(links)
                    if gov:
                        st.markdown("**Governance links**")
                        dataframe(gov)

            if entity_rows:
                st.markdown("#### Companies / entities")
                df=pd.DataFrame(entity_rows[:max_rows])
                preferred=["name","entity_type","country","headquarters","status","record_status","source_id","entity_id"]
                cols=[c for c in preferred if c in df.columns]
                st.dataframe(df[cols],use_container_width=True,hide_index=True)

            if vessel_rows:
                st.markdown("#### Vessels / mobile assets")
                df=pd.DataFrame(vessel_rows[:max_rows])
                preferred=["name","mobile_type","imo","mmsi","flag","status","record_status","source_id","mobile_asset_id"]
                cols=[c for c in preferred if c in df.columns]
                st.dataframe(df[cols],use_container_width=True,hide_index=True)

            if event_rows:
                st.markdown("#### Events")
                df=pd.DataFrame(event_rows[:max_rows])
                preferred=[
                    "start_date","title","event_nature","event_domain","event_family","event_type",
                    "location","countries","severity","trade_visible","intelligence_visible","event_id"
                ]
                cols=[c for c in preferred if c in df.columns]
                st.dataframe(df[cols],use_container_width=True,hide_index=True)

        else:
            st.info("Enter a name, place, vessel, IMO or event above to search the live database.")

        st.divider()
        st.markdown("### Migration coverage snapshot")

        def _count_like(table, field, tokens):
            rows=_safe_query_rows(table,"*",5000)
            total=0
            for r in rows:
                s=str(r.get(field) or "").casefold()
                if any(t in s for t in tokens):
                    total += 1
            return total

        try:
            assets_total=count_rows(sb,"pc_assets")
            vessels_total=count_rows(sb,"pc_mobile_assets")
            entities_total=count_rows(sb,"pc_entities")
            events_total=count_rows(sb,"pc_events")
            locations_total=count_rows(sb,"pc_event_locations")
            observations_total=count_rows(sb,"pc_observations")
            staged_pending=count_rows(sb,"pc_staged_records",{"review_status":"pending"})
            staged_approved=count_rows(sb,"pc_staged_records",{"review_status":"approved"})
        except Exception:
            assets_total=vessels_total=entities_total=events_total=locations_total=observations_total=staged_pending=staged_approved=0

        s1,s2,s3,s4 = st.columns(4)
        s1.metric("Canonical assets",assets_total)
        s2.metric("Canonical vessels",vessels_total)
        s3.metric("Canonical entities",entities_total)
        s4.metric("Canonical events",events_total)

        s5,s6,s7,s8 = st.columns(4)
        s5.metric("Event locations",locations_total)
        s6.metric("Observations",observations_total)
        s7.metric("Staged pending",staged_pending)
        s8.metric("Approved waiting apply",staged_approved)


        st.divider()
        st.markdown("### ReCAAP canonical promotion")
        st.caption(
            "ReCAAP observations can exist in pc_observations without appearing on maps. "
            "This action normalizes the 277 canonical ReCAAP observations as approved, then promotes them "
            "into canonical security events and event locations. It is idempotent and can be re-run safely."
        )

        try:
            recaap_obs_count = count_rows(sb,"pc_observations",{"source_id":"SRC_OPEN_RECAAP_ISC"})
        except Exception:
            recaap_obs_count = 0

        rc1,rc2,rc3 = st.columns(3)
        rc1.metric("ReCAAP observations",recaap_obs_count)
        rc2.metric("Canonical events now",events_total)
        rc3.metric("Event locations now",locations_total)

        if recaap_obs_count:
            confirm_recaap = st.checkbox(
                "I understand this will create/update canonical ReCAAP security events and map locations.",
                key="confirm_recaap_promote"
            )
            if st.button(
                "Promote ReCAAP observations",
                type="primary",
                disabled=not confirm_recaap,
                key="promote_recaap_button"
            ):
                try:
                    with st.status("Promoting ReCAAP observations...",expanded=True) as status:
                        result = promote_recaap_observations(sb)
                        st.write(f"Observations found: {result['observations']}")
                        st.write(f"Canonical events written: {result['events']}")
                        st.write(f"Event locations written: {result['locations']}")
                        st.write(f"Skipped: {result['skipped']}")
                        if result["failures"]:
                            for item in result["failures"][:25]:
                                st.write(item)
                            status.update(
                                label=f"Promotion completed with {len(result['failures'])} warning(s)",
                                state="error",
                                expanded=True
                            )
                        else:
                            status.update(
                                label="ReCAAP promotion complete",
                                state="complete",
                                expanded=False
                            )
                    if result["failures"]:
                        st.warning(
                            f"Promotion finished: {result['events']} events and {result['locations']} locations written; "
                            f"{len(result['failures'])} failures."
                        )
                    else:
                        st.success(
                            f"Promotion complete — {result['events']} canonical events and "
                            f"{result['locations']} event locations written."
                        )
                    st.rerun()
                except Exception as exc:
                    st.exception(exc)
        else:
            st.info("No canonical ReCAAP observations found yet.")


        st.caption(
            "A record appearing here is in Supabase. A record that exists only in Excel or Batch Staging "
            "has not yet reached the canonical database."
        )



elif page=="ReCAAP Vessel Resolver":
    title(
        "ReCAAP vessel resolver",
        "Link canonical ReCAAP security events to canonical vessel records; stage safe matches first and route unresolved identities to AI research."
    )
    if not sb:
        st.error("Supabase service connection required.")
    else:
        events=_recaap_events_for_resolution(sb)
        vessels=_canonical_vessels_for_resolution(sb)
        existing=_existing_event_vessel_links(sb)

        c1,c2,c3=st.columns(3)
        c1.metric("ReCAAP events with vessel names",len(events))
        c2.metric("Canonical vessels",len(vessels))
        c3.metric("Already vessel-linked",sum(1 for e in events if e["event_id"] in existing))

        if not vessels:
            st.error(
                "Canonical vessel query returned 0 rows. The resolver will not run AI research until "
                "pc_mobile_assets is readable, because doing so would waste research calls and risk duplicates."
            )
        else:
            st.success(f"Canonical vessel registry loaded: {len(vessels):,} records.")

        st.markdown("### Step 1 · Stage deterministic matches")
        st.caption(
            "This does not use AI. It matches normalized vessel names against the canonical vessel registry "
            "and stages only unique exact matches into pc_event_links for normal Review Queue approval."
        )
        if st.button("Stage exact vessel matches",type="primary",disabled=not bool(vessels)):
            with st.status("Resolving exact vessel matches...",expanded=True) as status:
                result=stage_recaap_exact_vessel_links(sb)
                st.write(f"ReCAAP events examined: {result['events']}")
                st.write(f"Exact links staged: {result['staged']}")
                st.write(f"Already linked: {result['already']}")
                st.write(f"Unresolved: {len(result['unresolved'])}")
                st.write(f"Ambiguous: {len(result['ambiguous'])}")
                status.update(label="Exact-match resolution complete",state="complete",expanded=False)

            st.session_state["_recaap_unresolved"]=result["unresolved"]
            st.session_state["_recaap_ambiguous"]=result["ambiguous"]
            st.success(
                f"{result['staged']} exact vessel link(s) sent to Review Queue. "
                "Approve + apply those before using AI for unresolved vessels."
            )

        unresolved=st.session_state.get("_recaap_unresolved")
        ambiguous=st.session_state.get("_recaap_ambiguous")
        if unresolved is not None:
            st.markdown("### Unresolved after exact matching")
            if unresolved:
                st.dataframe(pd.DataFrame(unresolved),use_container_width=True,hide_index=True)
            else:
                st.success("No unresolved ReCAAP vessel names.")
            if ambiguous:
                st.markdown("### Ambiguous names")
                st.dataframe(pd.DataFrame(ambiguous),use_container_width=True,hide_index=True)

        st.markdown("### Step 2 · AI research for unresolved identities")
        st.caption(
            "After applying the exact links in Review Queue, use Research Jobs for the remaining vessels. "
            "The prompt below instructs AI to stage either a missing canonical vessel + event link, or just the event link."
        )

        unresolved_now=[]
        existing_now=_existing_event_vessel_links(sb)
        for e in _recaap_events_for_resolution(sb):
            if e["event_id"] not in existing_now:
                unresolved_now.append({
                    "event_id":e["event_id"],
                    "vessel_name":e.get("_vessel_name"),
                    "event_date":e.get("start_date"),
                    "event_type":e.get("event_type"),
                })

        st.metric("Currently unresolved / unlinked",len(unresolved_now))

        batch_size=st.selectbox("AI research batch size",[10,20,30,50],index=1)
        start=st.number_input("Start at unresolved record",min_value=0,max_value=max(0,len(unresolved_now)-1),value=0,step=batch_size)
        batch=unresolved_now[int(start):int(start)+int(batch_size)]

        prompt=RECAAP_AI_RESOLVER_PROMPT + "\n\nUnresolved ReCAAP events for this batch:\n" + json.dumps(batch,indent=2,default=str)
        st.text_area("AI resolver prompt",value=prompt,height=360,key="recaap_ai_prompt")

        st.info(
            "Copy this prompt into Research Jobs → Custom research with 'Use current web research' enabled. "
            "AI proposals will return to Review Queue; they still require approval before canonical writes."
        )


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


elif page=="Workflow Center":
    title("Workflow center","One place to see what is running, what needs reconciliation, what is ready for review, and what is complete.")
    if not sb:
        st.error("Supabase service connection required.")
    else:
        ai=_workflow_job_rows("AI_RESEARCH",60)
        bulk=_workflow_job_rows("BATCH_IMPORT",60)
        docs=_workflow_job_rows("DOCUMENT_INGEST",60)
        all_jobs=ai+bulk+docs
        running=sum(1 for j in all_jobs if j.get("status")=="running")
        completed=sum(1 for j in all_jobs if j.get("status")=="completed")
        failed=sum(1 for j in all_jobs if j.get("status")=="failed")
        pending=count_rows(sb,"pc_staged_records",{"review_status":"pending"})
        c1,c2,c3,c4=st.columns(4)
        c1.metric("Running",running)
        c2.metric("Completed",completed)
        c3.metric("Failed",failed)
        c4.metric("Pending staged",pending)

        tabs=st.tabs(["AI research","Bulk imports","Documents","Stale / attention"])
        with tabs[0]:
            rows=[]
            for j in ai:
                s=_staging_summary(j["ingestion_job_id"])
                rows.append({
                    "Job":j.get("title"),"Status":j.get("status"),"Created":j.get("created_at"),
                    "Staged":s.get("total",0),"Ready":s.get("ready",0),"Unresolved":s.get("unresolved",0),
                    "Partial":s.get("partial",0),"Applied":s.get("applied",0),"Job ID":j.get("ingestion_job_id")
                })
            dataframe(rows)
        with tabs[1]:
            rows=[]
            for j in bulk:
                s=_staging_summary(j["ingestion_job_id"])
                rows.append({
                    "Job":j.get("title"),"Status":j.get("status"),"Created":j.get("created_at"),
                    "Staged":s.get("total",0),"Ready":s.get("ready",0),"Unresolved":s.get("unresolved",0),
                    "Partial":s.get("partial",0),"Applied":s.get("applied",0),"Job ID":j.get("ingestion_job_id")
                })
            dataframe(rows)
        with tabs[2]:
            if _table_exists("pc_documents"):
                docs_rows=safe_rows(sb,"pc_documents","document_id,title,document_type,file_name,publisher,publication_date,extraction_status,created_at",250,order="created_at")
                dataframe(docs_rows)
            else:
                st.info("Run SQL 028_document_ingestion.sql to enable document records.")
        with tabs[3]:
            try:
                stale=safe_rows(sb,"pc_v_stale_ingestion_jobs","*",250,order="updated_at")
            except Exception:
                stale=[]
            if stale:
                dataframe(stale)
            else:
                # Compatibility calculation.
                calc=[]
                now=pd.Timestamp.utcnow()
                for j in all_jobs:
                    if j.get("status")!="running": continue
                    d=pd.to_datetime(j.get("updated_at") or j.get("created_at"),utc=True,errors="coerce")
                    if pd.notna(d) and now-d>pd.Timedelta(minutes=45):
                        calc.append({**j,"time_since_update":str(now-d)})
                dataframe(calc)

elif page=="AI Research Workflow":
    title(
        "AI research workflow",
        "Create research here, then stage → auto-resolve → review exceptions → apply → QA. No separate Research Jobs page is required."
    )

    if not sb:
        st.error("Supabase service connection required.")
    else:
        launch_tab, manage_tab, history_tab = st.tabs(["Launch research","Run & reconcile","Recent jobs"])

        with launch_tab:
            st.markdown("### New AI research job")
            campaign=st.selectbox("Campaign",list(AI_CAMPAIGNS),key="aiwf_campaign")
            seed_prompt=AI_CAMPAIGNS[campaign]
            prompt=st.text_area(
                "Research query",
                value=seed_prompt,
                placeholder="Describe exactly what you want the AI researcher to find, verify and stage.",
                height=190,
                key="aiwf_prompt"
            )

            research_docs=st.file_uploader(
                "Attach source documents (optional)",
                type=["pdf","docx","txt","md"],
                accept_multiple_files=True,
                key="aiwf_documents",
                help="Documents are read before web research. Their extracted text is passed to the researcher and, when the Documents tables are installed, preserved in pc_documents."
            )
            if research_docs:
                st.caption(f"{len(research_docs)} document(s) attached. The researcher will read these before outward web research.")
                with st.expander("Attached document preview"):
                    for _doc in research_docs:
                        try:
                            _txt=_extract_document_text(_doc)
                            st.markdown(f"**{_doc.name}** · {len(_txt):,} extracted characters")
                            st.text(_txt[:2500] + ("\n…" if len(_txt)>2500 else ""))
                        except Exception as _exc:
                            st.warning(f"{_doc.name}: {_exc}")

            c1,c2,c3=st.columns(3)
            with c1:
                context=st.selectbox("Product context",["TRADE","INTELLIGENCE"],index=0,key="aiwf_context")
            with c2:
                use_web=st.checkbox("Use current web research",True,key="aiwf_web")
                use_canonical_context=st.checkbox(
                    "Use canonical database context",True,
                    help="Pass likely matching companies/assets/vessels and existing graph links from Supabase to the researcher before web research.",
                    key="aiwf_canonical"
                )
            with c3:
                st.metric("Pending staged",count_rows(sb,"pc_staged_records",{"review_status":"pending"}))

            canonical_context={}
            if use_canonical_context and prompt.strip():
                try:
                    canonical_context=build_canonical_research_context(sb,prompt)
                    cc=canonical_context.get("candidate_counts",{})
                    st.caption(
                        f"Canonical pre-check: {cc.get('entities',0)} companies/entities · "
                        f"{cc.get('assets',0)} assets · {cc.get('mobile_assets',0)} vessels · "
                        f"{cc.get('relationships',0)} existing relationships."
                    )
                    with st.expander("Preview canonical candidates sent to the researcher"):
                        st.json(canonical_context)
                except Exception as exc:
                    st.warning(f"Canonical context pre-check failed; research can still run through normal staging: {exc}")
                    canonical_context={}

            st.caption(
                "Research output is staged first. The dependency engine can create missing source-backed companies, facilities, vessels and other endpoints before relationships are applied."
            )

            if st.button("Run AI research job",type="primary",disabled=not bool(prompt.strip()),key="aiwf_run"):
                if not ai_configured():
                    st.error("Configure OPENAI_API_KEY and OPENAI_MODEL in Streamlit secrets.")
                else:
                    effective_prompt=prompt
                    document_manifest=[]
                    document_blocks=[]
                    total_document_chars=0
                    max_total_document_chars=120000
                    max_document_chars=60000

                    document_failures=[]
                    for _doc in (research_docs or []):
                        _raw=_doc.getvalue()
                        _hash=hashlib.sha256(_raw).hexdigest()
                        try:
                            _text=_extract_document_text(_doc)
                        except Exception as _doc_parse_exc:
                            document_failures.append({
                                "file_name":_doc.name,
                                "error":str(_doc_parse_exc),
                            })
                            st.warning(
                                f"Could not extract {_doc.name}; this file will be skipped rather than aborting the research job. "
                                f"{_doc_parse_exc}"
                            )
                            continue
                        _usable=_text[:max_document_chars]
                        remaining=max_total_document_chars-total_document_chars
                        if remaining <= 0:
                            _usable=""
                        elif len(_usable)>remaining:
                            _usable=_usable[:remaining]
                        total_document_chars += len(_usable)

                        _doc_id=None
                        if _table_exists("pc_documents"):
                            try:
                                _existing=(sb.table("pc_documents").select("document_id").eq("file_sha256",_hash).limit(1).execute().data or [])
                                _payload={
                                    "title":Path(_doc.name).stem,
                                    "document_type":"research_source",
                                    "file_name":_doc.name,
                                    "file_sha256":_hash,
                                    "mime_type":mimetypes.guess_type(_doc.name)[0],
                                    "extracted_text":_text,
                                    "metadata":{
                                        "original_size_bytes":len(_raw),
                                        "ingested_via":"AI_RESEARCH_WORKFLOW"
                                    }
                                }
                                if _existing:
                                    _doc_id=_existing[0]["document_id"]
                                    sb.table("pc_documents").update(_payload).eq("document_id",_doc_id).execute()
                                else:
                                    _doc_id=sb.table("pc_documents").insert(_payload).execute().data[0]["document_id"]
                            except Exception as _doc_exc:
                                st.warning(f"Could not preserve {_doc.name} in pc_documents; research will still use its extracted text: {_doc_exc}")

                        document_manifest.append({
                            "file_name":_doc.name,
                            "sha256":_hash,
                            "document_id":_doc_id,
                            "extracted_chars":len(_text),
                            "chars_sent_to_researcher":len(_usable),
                            "truncated":len(_usable)<len(_text),
                        })
                        if _usable:
                            document_blocks.append(
                                "\n\n===== SOURCE DOCUMENT: " + _doc.name + " =====\n" +
                                _usable +
                                "\n===== END SOURCE DOCUMENT: " + _doc.name + " ====="
                            )

                    if document_blocks:
                        effective_prompt += (
                            "\n\nDOCUMENT-FIRST INSTRUCTION: Read the attached source documents below before web research. "
                            "Treat them as seed evidence, verify material facts outward where requested, preserve provenance, "
                            "deduplicate overlapping stories, and do not invent facts.\n" + "".join(document_blocks)
                        )

                    if use_canonical_context and canonical_context:
                        effective_prompt += canonical_context_prompt_block(canonical_context)

                    job=sb.table("pc_ingestion_jobs").insert({
                        "job_type":"AI_RESEARCH",
                        "title":campaign if campaign!="Custom research" else prompt[:100],
                        "query_text":prompt,
                        "source_scope":{
                            "product":context,
                            "web_search":use_web,
                            "campaign":campaign,
                            "canonical_context":bool(use_canonical_context),
                            "canonical_candidate_counts":(canonical_context or {}).get("candidate_counts",{}),
                            "documents":document_manifest,
                            "document_count":len(document_manifest),
                        },
                        "status":"running",
                    }).execute().data[0]
                    job_id=job["ingestion_job_id"]
                    _workflow_upsert(job_id,"AI_RESEARCH",job.get("title") or "AI research","RESEARCH",1)

                    try:
                        with st.status("Running AI research...",expanded=True) as status:
                            st.write("Sending research brief to OpenAI...")
                            result=ai_research(
                                effective_prompt,
                                context,
                                use_web,
                                output_contract=AI_OUTPUT_CONTRACT
                            )
                            st.write("Research returned. Validating and staging structured proposals...")
                            staged,rejected,resolution=stage_ai_result(sb,job_id,result)

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

                            auto_result={}
                            if staged:
                                st.write("Running dependency-aware auto reconciliation...")
                                auto_result=_run_reconciliation(job_id)

                            stats={
                                "staged_records":staged,
                                "discarded_invalid_records":rejected,
                                "campaign":campaign,
                                "product":context,
                                "resolution":resolution,
                                "auto_reconcile":auto_result,
                                "documents":document_manifest,
                            }
                            sb.table("pc_ingestion_jobs").update({"status":"completed","stats":stats}).eq("ingestion_job_id",job_id).execute()
                            _workflow_upsert(job_id,"AI_RESEARCH",job.get("title") or "AI research","RECONCILE",4,stats=stats)
                            status.update(label=f"Research complete — {staged} staged record(s)",state="complete",expanded=False)

                        st.success(f"Research complete. {staged} proposal(s) staged and auto-reconciled.")
                        st.session_state["aiwf_last_job_id"]=job_id
                        st.rerun()
                    except Exception as exc:
                        sb.table("pc_ingestion_jobs").update({"status":"failed","error_text":str(exc)}).eq("ingestion_job_id",job_id).execute()
                        st.error(str(exc))

        with manage_tab:
            selected_job_id=st.session_state.get("selected_ingestion_job_id")
            if selected_job_id:
                st.info(
                    f"Selected from recovery console: "
                    f"{st.session_state.get('selected_ingestion_job_title') or selected_job_id} "
                    f"({selected_job_id})"
                )
            all_jobs=_workflow_job_rows(None,200)
            jobs=[j for j in all_jobs if str(j.get("job_type") or "").upper() in {"AI_RESEARCH","BATCH_IMPORT"}]
            if not jobs:
                st.info("No research or structured bulk-import jobs yet. Launch research above or use Bulk Load.")
            else:
                labels=[
                    f"{'AI research' if str(j.get('job_type') or '').upper()=='AI_RESEARCH' else 'Bulk research import'}"
                    f" · {j.get('title') or 'Untitled'} | {j.get('status')} | {j.get('ingestion_job_id')}"
                    for j in jobs
                ]
                default_idx=0
                last=str(st.session_state.get("aiwf_last_job_id") or "")
                if last:
                    for i,j in enumerate(jobs):
                        if str(j.get("ingestion_job_id"))==last:
                            default_idx=i; break
                choice=st.selectbox("Research / import job",labels,index=default_idx,key="aiwf_job_select")
                job=jobs[labels.index(choice)]
                jid=job["ingestion_job_id"]
                workflow_type="AI_RESEARCH" if str(job.get("job_type") or "").upper()=="AI_RESEARCH" else "BULK_IMPORT"
                workflow_label="AI research" if workflow_type=="AI_RESEARCH" else "Bulk research import"
                summ=_staging_summary(jid)
                stages=WORKFLOW_STAGES[workflow_type]
                st.caption(" → ".join(stages))
                st.caption(
                    f"Job status: {job.get('status') or '—'} · "
                    f"Created: {job.get('created_at') or '—'} · "
                    f"Job ID: {jid}"
                )
                # Complete status picture — do not hide buckets.
                c1,c2,c3,c4,c5,c6=st.columns(6)
                c1.metric("Staged",summ.get("total",0))
                c2.metric("Ready",summ.get("wf_ready",0))
                c3.metric("Exceptions",summ.get("wf_exceptions",0))
                c4.metric("Approved",summ.get("wf_approved",0))
                c5.metric("Applied",summ.get("wf_applied",0))
                c6.metric("Other",summ.get("wf_other",0))
                st.caption(
                    "These workflow counters are mutually exclusive: "
                    "Ready + Exceptions + Approved + Applied + Other = Staged. "
                    "Resolution diagnostics remain available under Refresh / raw workflow status."
                )

                st.markdown("## Workflow")
                st.caption("Run the steps in order. Completed steps turn green with a check mark; amber means analyst review is still required.")

                # Load the workflow-run state for this selected ingestion job.
                # Earlier builds referenced `wf` before it had been defined, which caused
                # the NameError seen in Streamlit.
                wf={}
                try:
                    wf_rows=(sb.table("pc_workflow_runs")
                             .select("workflow_run_id,workflow_type,current_stage,stage_order,status,updated_at,completed_at,stats,metadata")
                             .eq("ingestion_job_id",jid)
                             .order("updated_at",desc=True)
                             .limit(1).execute().data or [])
                    if wf_rows:
                        wf=wf_rows[0]
                except Exception:
                    wf={}

                # Visual progress summary
                stage_rank={"UPLOAD":1,"MAP_TABLES":1,"MAP_FIELDS":1,"FILL_KEYS":1,"STAGE":1,
                            "PREPARE_IDS":2,"RECONCILE":3,"RELATIONSHIPS":4,"REVIEW":4,
                            "APPLY":5,"QA":6,"COMPLETE":6}
                current_rank=stage_rank.get(str((wf or {}).get("current_stage") or "").upper(),1)
                pct=min(100,max(0,int((current_rank/6)*100)))
                st.progress(pct/100.0,text=f"Workflow progress: step {current_rank} of 6")

                # Determine completion state from actual database/workflow status.
                wf_stage=str((wf or {}).get("current_stage") or "").upper() if isinstance(wf,dict) else ""
                wf_status=str((wf or {}).get("status") or "").lower() if isinstance(wf,dict) else ""
                exceptions=int(summ.get("partial",0) or 0)+int(summ.get("unresolved",0) or 0)+int(summ.get("ambiguous",0) or 0)

                # STEP 0 — repair legacy/staged mapping issues before doing anything else.
                st.markdown("### 🛠️ Repair imported fields")
                st.caption(
                    "Use this when rows show missing required fields or 'no source URL' even though "
                    "those values were present in the uploaded workbook. It promotes fields stranded "
                    "in metadata.source_payload back into the staged payload."
                )
                if st.button("Repair staged fields for this job",key=f"aiwf_repair_{jid}",use_container_width=True):
                    with st.spinner("Repairing staged payloads from original source fields..."):
                        repair=_repair_staged_payloads_from_source(jid)
                    st.success(
                        f"Repair checked {repair.get('checked',0)} row(s) and updated {repair.get('updated',0)}."
                    )
                    if repair.get("errors"):
                        st.warning(f"{len(repair['errors'])} row(s) could not be repaired.")
                        st.write(repair["errors"])
                    # Re-run reconciliation after repair so status counters update.
                    try:
                        _run_reconciliation(jid)
                    except Exception:
                        pass
                    st.rerun()

                # STEP 1
                step1_done = wf_stage in {"PREPARE_IDS","RECONCILE","RELATIONSHIPS","REVIEW","APPLY","QA","COMPLETE"} or int(summ.get("ready",0) or 0)>0 or int(summ.get("applied",0) or 0)>0
                _workflow_step_header(
                    1,"Prepare canonical IDs",
                    "complete" if step1_done else "active",
                    "Canonical IDs prepared" if step1_done else "Run this first"
                )
                st.caption("Assign/reuse canonical IDs for NEW and MATCHED companies, assets, vessels and events before relationships are resolved.")
                if not step1_done:
                    if st.button("1 · Prepare IDs",key="aiwf_prepare",use_container_width=True):
                        with st.spinner("Preparing canonical candidates..."):
                            res=_prepare_canonical_candidates(sb,jid)
                        _workflow_upsert(jid,workflow_type,job.get("title") or workflow_label,"PREPARE_IDS",3,stats={"prepare":res})
                        st.success("ID preparation complete.")
                        st.json(res)
                        st.rerun()
                else:
                    st.caption("No action needed unless you intentionally want to rerun ID preparation.")

                # STEP 2
                step2_done = wf_stage in {"RECONCILE","RELATIONSHIPS","REVIEW","APPLY","QA","COMPLETE"} or int(summ.get("ready",0) or 0)>0 or int(summ.get("applied",0) or 0)>0
                _workflow_step_header(
                    2,"Reconcile identities",
                    "complete" if step2_done else ("active" if step1_done else "blocked"),
                    f"{summ.get('ready',0)} ready"
                )
                st.caption("Match staged records to existing canonical records and classify NEW / MATCHED / READY / PARTIAL / AMBIGUOUS.")
                if not step2_done and step1_done:
                    if st.button("2 · Auto reconcile",type="primary",key="aiwf_reconcile",use_container_width=True):
                        with st.spinner("Resolving dependencies and identities..."):
                            res=_run_reconciliation(jid)
                        _workflow_upsert(jid,workflow_type,job.get("title") or workflow_label,"RECONCILE",4,stats={"reconcile":res})
                        st.success("Dependency-aware reconciliation complete.")
                        st.json(res)
                        st.rerun()

                # STEP 3
                step3_done = wf_stage in {"RELATIONSHIPS","REVIEW","APPLY","QA","COMPLETE"} or (int(summ.get("ready",0) or 0)>0 and int(summ.get("unresolved",0) or 0)==0)
                _workflow_step_header(
                    3,"Resolve relationship endpoints",
                    "complete" if step3_done else ("active" if step2_done else "blocked"),
                    "Relationship pass completed" if step3_done else "Resolve event/entity/asset links"
                )
                st.caption("Resolve event links, ownership, operator/manager and other graph edges to canonical IDs.")
                if not step3_done and step2_done:
                    if st.button("3 · Resolve relationships",key="aiwf_relationships",use_container_width=True):
                        out={}
                        try: out["event_links"]=_process_relationship_backlog(sb,jid)
                        except Exception as exc: out["event_links_error"]=str(exc)
                        try: out["relationships"]=_process_generic_relationship_backlog(sb,jid)
                        except Exception as exc: out["relationships_error"]=str(exc)
                        _workflow_upsert(jid,workflow_type,job.get("title") or workflow_label,"RELATIONSHIPS",5,stats=out)
                        st.success("Relationship resolution pass complete.")
                        st.json(out)
                        st.rerun()

                # STEP 4
                step4_done = step3_done and exceptions==0
                _workflow_step_header(
                    4,"Review only the exceptions",
                    "complete" if step4_done else ("warning" if exceptions else ("active" if step3_done else "blocked")),
                    "No exceptions remain" if step4_done else (
                        f"{exceptions} exception(s) need review" if exceptions else "Waiting for relationship resolution"
                    )
                )
                if exceptions:
                    st.warning(
                        f"{exceptions} exception(s) still need analyst review "
                        f"({summ.get('partial',0)} partial, {summ.get('unresolved',0)} unresolved, "
                        f"{summ.get('ambiguous',0)} ambiguous)."
                    )
                    st.caption(
                        "You do not need to hold the rest of the job. Apply the safe rows in Step 5 first, "
                        "then return to Reconcile & Review for only the remaining exceptions."
                    )
                elif step3_done:
                    st.success("No reconciliation exceptions remain.")

                # STEP 5 — iterative apply-and-refresh for this job.
                # Safe rows can be promoted immediately even while other rows remain partial/blocked.
                safe_candidates, blocked_rows=_job_apply_candidates(jid)
                step5_done = (
                    int(summ.get("wf_applied",0) or 0)>0
                    and len(safe_candidates)==0
                    and len(blocked_rows)==0
                    and exceptions==0
                )
                step5_state = (
                    "complete" if step5_done
                    else "active" if safe_candidates
                    else "warning" if (blocked_rows or exceptions)
                    else "pending"
                )
                _workflow_step_header(
                    5,"Apply fixed / safe records",
                    step5_state,
                    f"{summ.get('wf_applied',0)} applied · {len(safe_candidates)} safe now · {len(blocked_rows)} remain blocked"
                )
                st.caption(
                    "Apply the records that are already resolved and safe now. The page will refresh immediately "
                    "afterward so you can continue working only the smaller remaining exception set."
                )

                if safe_candidates:
                    st.success(
                        f"{len(safe_candidates)} record(s) are already safe to promote. "
                        "Applying them will not wait for the remaining partial/blocked rows."
                    )
                    c_apply,c_refresh=st.columns([3,1])
                    if c_apply.button(
                        f"Apply {len(safe_candidates)} Safe Records Now",
                        type="primary",
                        key=f"aiwf_apply_safe_now_{jid}",
                        use_container_width=True
                    ):
                        with st.status("Applying resolved safe records...",expanded=True) as status:
                            result=_approve_and_apply_job_safe(jid)
                            st.write(
                                f"Applied {result.get('applied',0)} / {result.get('safe_candidates',0)} safe candidate(s)."
                            )
                            if result.get("failures"):
                                st.write(result["failures"])
                            status.update(
                                label=(
                                    f"Applied {result.get('applied',0)} safe record(s) — refreshing remaining queue"
                                    if not result.get("failed")
                                    else f"Applied {result.get('applied',0)}; {result.get('failed',0)} failed"
                                ),
                                state="complete" if not result.get("failed") else "error",
                                expanded=bool(result.get("failed"))
                            )
                        _workflow_upsert(
                            jid,workflow_type,job.get("title") or workflow_label,
                            "APPLY",7,stats={"apply":result}
                        )
                        st.rerun()
                    if c_refresh.button(
                        "Refresh",
                        key=f"aiwf_refresh_after_apply_{jid}",
                        use_container_width=True
                    ):
                        st.rerun()
                else:
                    st.info("No additional safe rows are waiting to apply right now.")

                # Make the remaining work explicit and smaller.
                remaining_count=len(blocked_rows)
                if remaining_count:
                    st.warning(
                        f"After safe rows are applied, only {remaining_count} blocked/review row(s) remain in this job."
                    )
                    with st.expander(f"Work remaining: {remaining_count} blocked row(s)", expanded=False):
                        dataframe(blocked_rows)
                elif exceptions:
                    st.warning(f"{exceptions} reconciliation exception(s) remain for analyst review.")

                # STEP 6
                step6_done = wf_stage in {"QA","COMPLETE"} and wf_status in {"completed","complete","success","succeeded"}
                qa_ready = (
                    int(summ.get("wf_applied",0) or 0)>0
                    and len(safe_candidates)==0
                    and len(blocked_rows)==0
                    and exceptions==0
                )
                _workflow_step_header(
                    6,"QA canonical writes",
                    "complete" if step6_done else ("active" if qa_ready else ("blocked" if (blocked_rows or exceptions or safe_candidates) else "pending")),
                    "QA completed" if step6_done else (
                        "Ready to verify applied rows" if qa_ready
                        else "Finish review/apply before QA"
                    )
                )
                st.caption("Verify that records marked applied are actually present in their canonical destination tables.")
                if not step6_done and st.button("6 · Run QA",key=f"aiwf_qa_{jid}",use_container_width=True):
                    with st.spinner("Checking canonical tables..."):
                        qa=_qa_applied_job(jid)
                    _workflow_upsert(
                        jid,workflow_type,job.get("title") or workflow_label,
                        "QA",8,stats={"qa":qa}
                    )
                    if qa.get("missing",0)==0 and not qa.get("errors"):
                        st.success(f"QA passed: {qa.get('found',0)} canonical record(s) verified.")
                        st.caption("Applied rows are now terminal and will not be downgraded by later Refresh/Reconcile passes.")
                    else:
                        st.warning(
                            f"QA checked {qa.get('checked',0)} applied rows: "
                            f"{qa.get('found',0)} found, {qa.get('missing',0)} missing, "
                            f"{len(qa.get('errors') or [])} check error(s)."
                        )
                    st.json(qa)

                with st.expander("Refresh / raw workflow status"):
                    if st.button("Refresh status",key="aiwf_refresh"):
                        st.json(_staging_summary(jid))
                    st.json({
                        "job_id":jid,
                        "job_status":job.get("status"),
                        "staging_summary":summ,
                        "safe_apply_candidates":len(safe_candidates),
                        "blocked_rows":len(blocked_rows),
                    })

                st.markdown("#### What to do now")
                if int(summ.get("total",0) or 0)==0:
                    stats=job.get("stats") if isinstance(job.get("stats"),dict) else {}
                    table_stats=stats.get("tables") if isinstance(stats.get("tables"),dict) else {}
                    if table_stats:
                        st.error(
                            "This job reports imported rows but has no staging rows attached. "
                            "Use Recent jobs → recovery controls to inspect/retry the load."
                        )
                        st.json({"reported_tables":table_stats,"job_stats":stats})
                    else:
                        st.info("No staged rows were found for this job.")
                elif safe_candidates:
                    st.success(
                        f"Apply the {len(safe_candidates)} safe record(s) now. The job will refresh and leave only the smaller review set."
                    )
                elif exceptions or blocked_rows:
                    st.warning(
                        f"Only the remaining exception set needs work now: {exceptions} reconciliation exception(s), "
                        f"{len(blocked_rows)} blocked row(s). Resolve/match those, then apply again."
                    )
                else:
                    st.success("All staged rows are accounted for and nothing remains to apply. Run Step 6 QA.")

        with history_tab:
            jobs=safe_rows(
                sb,"pc_ingestion_jobs",
                "ingestion_job_id,job_type,title,query_text,status,stats,error_text,created_at,started_at,completed_at",
                100,order="created_at"
            )
            workflow_jobs=[
                j for j in jobs
                if str(j.get("job_type") or "").upper() in {"AI_RESEARCH","BATCH_IMPORT"}
            ]
            dataframe(workflow_jobs)

            st.markdown("### Bulk / research load audit")
            st.caption(
                "Cross-checks each completed import's reported row counts against the rows actually "
                "attached to that ingestion_job_id in pc_staged_records."
            )
            audit_rows=_audit_bulk_jobs(250)
            if audit_rows:
                problems=[r for r in audit_rows if str(r.get("health") or "").startswith(("CHECK","FAILED","REVIEW"))]
                c1,c2,c3,c4=st.columns(4)
                c1.metric("Audited jobs",len(audit_rows))
                c2.metric("Needs checking",len([r for r in audit_rows if str(r.get("health") or "").startswith("CHECK")]))
                c3.metric("Reconciliation review",len([r for r in audit_rows if str(r.get("health") or "").startswith("REVIEW")]))
                c4.metric("Applied",len([r for r in audit_rows if r.get("health")=="APPLIED"]))
                if problems:
                    st.warning(
                        "Some jobs need checking. A completed job with reported rows but zero staged rows "
                        "is the same failure pattern that previously made the workflow appear empty."
                    )
                    dataframe(problems)
                    st.markdown("#### Recovery controls")
                    job_lookup={str(j.get("ingestion_job_id") or ""):j for j in workflow_jobs}
                    for p in problems[:20]:
                        jid=str(p.get("ingestion_job_id") or "")
                        job=job_lookup.get(jid)
                        if job:
                            with st.expander(f"{p.get('health')} · {job.get('title') or jid}",expanded=False):
                                _job_control_panel(job,key_prefix="audit")
                with st.expander("Show all audited bulk / research jobs",expanded=False):
                    dataframe(audit_rows)
            else:
                st.info("No BATCH_IMPORT or AI_RESEARCH jobs were available to audit.")

elif page=="Bulk Import Workflow":
    title("Bulk import workflow","Ordered bulk path: upload → map tables → map fields → fill IDs → stage → reconcile → review → apply → QA.")
    jobs=_workflow_job_rows("BATCH_IMPORT",100)
    c1,c2=st.columns([1,2])
    c1.metric("Bulk jobs",len(jobs))
    c2.caption("Create new multi-table imports in Multi-Table Bulk Loader; use this page to advance existing imports.")
    if jobs:
        labels=[f"{j.get('title') or 'Batch'} | {j.get('status')} | {j.get('ingestion_job_id')}" for j in jobs]
        choice=st.selectbox("Bulk job",labels)
        job=jobs[labels.index(choice)]; jid=job["ingestion_job_id"]
        summ=_staging_summary(jid)
        st.caption(" → ".join(WORKFLOW_STAGES["BULK_IMPORT"]))
        k1,k2,k3,k4=st.columns(4)
        k1.metric("Staged",summ.get("total",0)); k2.metric("Ready",summ.get("ready",0))
        k3.metric("Needs cleanup",summ.get("unresolved",0)+summ.get("ambiguous",0)+summ.get("partial",0))
        k4.metric("Applied",summ.get("applied",0))
        b1,b2,b3=st.columns(3)
        if b1.button("Run reconciliation",type="primary"):
            res=_run_reconciliation(jid)
            _workflow_upsert(jid,"BULK_IMPORT",job.get("title") or "Bulk import","RECONCILE",6,stats={"reconcile":res})
            st.json(res); st.rerun()
        if b2.button("Resolve relationships"):
            out={}
            try: out["event_links"]=_process_relationship_backlog(sb,jid)
            except Exception as exc: out["event_links_error"]=str(exc)
            try: out["relationships"]=_process_generic_relationship_backlog(sb,jid)
            except Exception as exc: out["relationships_error"]=str(exc)
            st.json(out); st.rerun()
        if b3.button("Refresh status"):
            st.json(_staging_summary(jid))


    st.markdown("---")
    st.markdown("### All bulk-load integrity audit")
    st.caption(
        "Use this before relying on Trade. It compares each import job's stats with the rows "
        "actually present under the same ingestion_job_id in staging."
    )
    audit_rows=_audit_bulk_jobs(250)
    bulk_audit_rows=[r for r in audit_rows if r.get("job_type")=="BATCH_IMPORT"]
    if bulk_audit_rows:
        problems=[r for r in bulk_audit_rows if str(r.get("health") or "").startswith(("CHECK","FAILED","REVIEW"))]
        if problems:
            st.warning(f"{len(problems)} bulk-load job(s) require checking.")
            dataframe(problems)
            st.markdown("#### Bulk-load recovery controls")
            jobs_now=_workflow_job_rows(None,250)
            job_lookup={str(j.get("ingestion_job_id") or ""):j for j in jobs_now}
            for p in problems[:20]:
                jid=str(p.get("ingestion_job_id") or "")
                job=job_lookup.get(jid)
                if job:
                    with st.expander(f"{p.get('health')} · {job.get('title') or jid}",expanded=False):
                        _job_control_panel(job,key_prefix="bulk")
        else:
            st.success("No bulk-load integrity mismatches detected.")
        with st.expander("Show all bulk-load jobs",expanded=False):
            dataframe(bulk_audit_rows)

elif page=="Multi-Table Bulk Loader":
    title("Multi-table bulk loader","Load one workbook/file into several canonical tables. Map sections and fields, fill staging keys, then resolve everything as one controlled job.")
    if not sb:
        st.error("Supabase service connection required.")
    else:
        up=st.file_uploader("Workbook / CSV / JSON",type=["xlsx","xls","csv","json"],key="multitable_bulk")
        if up:
            try:
                sections,file_hash=_parse_multitable_upload(up)
                st.caption(f"{len(sections)} source section(s) · SHA-256 {file_hash[:16]}…")
                meta_map=_meta_table_map(sb)
                allowed=sorted(AI_ALLOWED_TABLES)
                configs={}
                for idx,(section,df) in enumerate(sections.items()):
                    with st.expander(f"{section} · {len(df):,} rows",expanded=True):
                        suggested=_suggest_target_table(section,df)
                        default_i=allowed.index(suggested) if suggested in allowed else 0
                        target=st.selectbox("Target canonical table",allowed,index=default_i,key=f"mt_target_{idx}")
                        cols=_table_write_columns_live(sb,target)
                        mapping=_auto_column_mapping(list(df.columns),cols)
                        edited=st.data_editor(
                            mapping,
                            use_container_width=True,
                            hide_index=True,
                            column_config={
                                "Include":st.column_config.CheckboxColumn(),
                                "Canonical Field":st.column_config.SelectboxColumn(options=[""]+cols)
                            },
                            key=f"mt_map_{idx}"
                        )
                        st.dataframe(df.head(8),use_container_width=True,hide_index=True)
                        configs[section]={"df":df,"target":target,"mapping":edited}

                auto_resolve=st.checkbox("Run reconciliation after staging",value=True)
                if st.button("Stage all selected tables",type="primary"):
                    job=sb.table("pc_ingestion_jobs").insert({
                        "job_type":"BATCH_IMPORT",
                        "title":up.name,
                        "source_scope":{
                            "multi_table":True,"file_sha256":file_hash,
                            "sections":{k:{"target_table":v["target"],"rows":len(v["df"])} for k,v in configs.items()}
                        },
                        "status":"running",
                        "started_at":pd.Timestamp.utcnow().isoformat()
                    }).execute().data[0]
                    jid=job["ingestion_job_id"]
                    wid=_workflow_upsert(jid,"BULK_IMPORT",up.name,"STAGE",5,metadata={"file_sha256":file_hash})

                    all_payloads=[]
                    table_counts={}
                    meta_map=_meta_table_map(sb)
                    for section,cfg in configs.items():
                        target=cfg["target"]; df=cfg["df"]; mapping=cfg["mapping"]
                        logical=(meta_map.get(target) or {}).get("entity_type")
                        if not logical and target=="pc_relationships": logical="relationship"
                        if not logical and target=="pc_event_links": logical="event_link"
                        for i,row in enumerate(df.to_dict("records"),1):
                            payload=_payload_from_mapping(row,mapping,target)
                            nk=_natural_key_global(payload,target,i)
                            payload=_fill_staging_key(payload,target,nk)
                            all_payloads.append({
                                "ingestion_job_id":jid,
                                "target_entity_type":logical,
                                "target_table":target,
                                "source_record_key":f"{section}:{nk}",
                                "natural_key":nk,
                                "action":"REVIEW",
                                "payload":_jsonable(payload),
                                "confidence":1.0,
                                "validation_status":"pending",
                                "review_status":"pending",
                                "resolution_status":"UNRESOLVED"
                            })
                            table_counts[target]=table_counts.get(target,0)+1

                    for i in range(0,len(all_payloads),250):
                        batch=_jsonable(all_payloads[i:i+250])
                        sb.table("pc_staged_records").insert(batch).execute()

                    result={}
                    if auto_resolve:
                        result=_run_reconciliation(jid)
                    sb.table("pc_ingestion_jobs").update({
                        "status":"completed","completed_at":pd.Timestamp.utcnow().isoformat(),
                        "stats":{"rows":len(all_payloads),"tables":table_counts,"reconciliation":result}
                    }).eq("ingestion_job_id",jid).execute()
                    _workflow_upsert(jid,"BULK_IMPORT",up.name,"RECONCILE" if auto_resolve else "STAGE",6 if auto_resolve else 5,stats={"rows":len(all_payloads),"tables":table_counts})
                    st.success(
                        f"Staged {len(all_payloads):,} rows across {len(table_counts)} canonical tables. "
                        "This job is now available under AI Research → Run & reconcile and Reconcile & Review."
                    )
                    st.session_state["aiwf_last_job_id"]=jid
                    st.json({"job_id":jid,"tables":table_counts,"reconciliation":result})
            except Exception as exc:
                try:
                    if "jid" in locals() and jid:
                        sb.table("pc_ingestion_jobs").update({
                            "status":"failed",
                            "completed_at":pd.Timestamp.utcnow().isoformat(),
                            "error_text":str(exc)
                        }).eq("ingestion_job_id",jid).execute()
                        _workflow_upsert(
                            jid,"BULK_IMPORT",
                            up.name if "up" in locals() and up else "Bulk import",
                            "STAGE",5,status="failed",
                            metadata={"failure_reason":str(exc)}
                        )
                except Exception:
                    pass
                st.exception(exc)

elif page=="Reconciliation Center":
    title("Reconcile & review","One-click dependency creation and matching first; people review only genuine ambiguity, conflicts, or unsupported structures.")
    if not sb:
        st.error("Supabase required.")
    else:
        jobs=_workflow_job_rows(None,200)
        labels=[f"{j.get('title') or j.get('job_type')} | {j.get('status')} | {j.get('ingestion_job_id')}" for j in jobs]
        selected=st.selectbox("Ingestion job",["All jobs"]+labels)
        jid=None if selected=="All jobs" else jobs[labels.index(selected)]["ingestion_job_id"]
        if jid:
            st.json(_staging_summary(jid))
        tabs=st.tabs(["Queue","Safe apply & diagnostics","Manual matching","One-click cleanup","Relationships","Stale jobs","SQL pack"])
        with tabs[0]:
            try:
                q=sb.table("pc_v_reconciliation_queue").select("*").limit(1000)
                if jid: q=q.eq("ingestion_job_id",jid)
                rows=q.execute().data or []
            except Exception:
                q=sb.table("pc_staged_records").select(
                    "staged_record_id,ingestion_job_id,target_table,natural_key,resolution_status,resolved_entity_id,resolution_method,confidence,review_status,payload,created_at"
                ).limit(1000)
                if jid: q=q.eq("ingestion_job_id",jid)
                rows=q.execute().data or []
            dataframe(rows)
        with tabs[1]:
            if not jid:
                st.info("Select one ingestion job to review safe/apply status.")
            else:
                st.markdown("#### Safe apply & diagnostics")
                st.caption(
                    "Resolution-ready is not the same as safe-to-apply. This screen separates records "
                    "that can be promoted now from rows blocked by schema, provenance, dependencies or relationships."
                )

                summ=_staging_summary(jid)
                safe_candidates,blocked_rows=_job_apply_candidates(jid)
                reason_rows,table_rows=_blocked_reason_summary(blocked_rows)

                c1,c2,c3,c4,c5=st.columns(5)
                c1.metric("Staged",summ.get("total",0))
                c2.metric("Safe to apply now",len(safe_candidates))
                c3.metric("Blocked",len(blocked_rows))
                c4.metric("Exceptions",summ.get("wf_exceptions",summ.get("partial",0)+summ.get("unresolved",0)+summ.get("ambiguous",0)))
                c5.metric("Applied",summ.get("wf_applied",summ.get("applied",0)))

                st.markdown("### Normal workflow")
                st.caption(
                    "For routine imports, use one button. Power Admin will repair obvious mapping/provenance issues, "
                    "resolve identities, apply safe parent records first, retry dependent relationships, apply newly-safe "
                    "children, and stop only when the job is complete or genuine analyst review is required."
                )
                if st.button(
                    "▶ Process this job automatically",
                    type="primary",
                    key=f"diag_auto_process_{jid}",
                    use_container_width=True
                ):
                    with st.status("Processing ingestion job end-to-end...",expanded=True) as status:
                        auto=_process_job_automatically(jid)
                        st.session_state[f"auto_process_result_{jid}"]=auto
                        for p in auto.get("passes",[]):
                            s=p.get("summary") or {}
                            st.write(
                                f"Pass {p.get('pass')}: applied {((p.get('parent_apply') or {}).get('applied',0) + (p.get('child_apply') or {}).get('applied',0))} · "
                                f"total applied {s.get('applied',0)} · safe {s.get('safe_now',0)} · "
                                f"blocked {s.get('blocked_now',0)} · exceptions {s.get('exceptions',0)}"
                            )
                        outcome=auto.get("outcome")
                        if outcome=="complete":
                            status.update(label="Job processed completely",state="complete",expanded=False)
                        elif outcome=="manual_review_required":
                            status.update(label="Automatic processing finished — genuine review remains",state="complete",expanded=True)
                        else:
                            status.update(label=f"Automatic processing stopped: {outcome}",state="complete",expanded=True)
                    st.rerun()

                auto_result=st.session_state.get(f"auto_process_result_{jid}")
                if auto_result:
                    if auto_result.get("outcome")=="complete":
                        st.success(
                            f"Automatic processing completed. {auto_result.get('total_applied_this_run',0)} record(s) "
                            "were applied during this run."
                        )
                    elif auto_result.get("outcome")=="manual_review_required":
                        st.warning(
                            f"Automatic processing applied {auto_result.get('total_applied_this_run',0)} record(s). "
                            f"Only {auto_result.get('blocked_remaining',0)} blocked row(s) now need attention. "
                            "Use Manual matching only for genuine ambiguity; dependency/schema reasons remain listed below."
                        )

                st.markdown("### Advanced / manual controls")

                if safe_candidates:
                    st.success(
                        f"{len(safe_candidates)} record(s) pass every safe-apply check. "
                        "Apply them now; the page will refresh and leave only the smaller remainder."
                    )
                    if st.button(
                        f"✅ Apply {len(safe_candidates)} safe records now",
                        type="primary",
                        key=f"diag_apply_safe_{jid}",
                        use_container_width=True
                    ):
                        with st.status("Applying safe records...",expanded=True) as status:
                            result=_approve_and_apply_job_safe(jid)
                            st.write({
                                "safe_candidates":result.get("safe_candidates",0),
                                "applied":result.get("applied",0),
                                "failed":result.get("failed",0),
                                "blocked":result.get("blocked",0),
                            })
                            if result.get("failures"):
                                st.write(result["failures"])
                            status.update(
                                label=f"Applied {result.get('applied',0)} safe record(s) — refreshing",
                                state="complete" if not result.get("failed") else "error",
                                expanded=bool(result.get("failed"))
                            )
                        try:
                            _run_reconciliation(jid)
                            _process_relationship_backlog(sb,jid)
                            _process_generic_relationship_backlog(sb,jid)
                        except Exception:
                            pass
                        st.rerun()
                else:
                    st.info("No records currently pass every safe-apply check.")

                b1,b2=st.columns(2)
                if b1.button("Refresh safe/apply status",key=f"diag_refresh_{jid}",use_container_width=True):
                    try:
                        _run_reconciliation(jid)
                        _process_relationship_backlog(sb,jid)
                        _process_generic_relationship_backlog(sb,jid)
                    except Exception:
                        pass
                    st.rerun()

                if b2.button("🛠 Fix obvious blockers + refresh",key=f"diag_repair_{jid}",use_container_width=True):
                    with st.status("Repairing obvious blockers...",expanded=True) as status:
                        repair=_repair_obvious_job_blockers(jid)
                        st.session_state[f"diag_repair_result_{jid}"]=repair
                        st.write("Field repair",repair.get("field_repair"))
                        st.write("Identity-state repair",repair.get("identity_repair"))
                        status.update(label="Parent repair complete — checking for safe parent rows",state="complete",expanded=False)
                    st.rerun()

                repair=st.session_state.get(f"diag_repair_result_{jid}")
                if repair:
                    fr=repair.get("field_repair") or {}
                    ir=repair.get("identity_repair") or {}
                    st.caption(
                        f"Last repair: {fr.get('updated',0)} payload(s) repaired; "
                        f"{ir.get('updated',0)} identity state(s) restored "
                        f"({ir.get('matched',0)} matched, {ir.get('new',0)} new)."
                    )

                st.markdown("##### Why records are blocked")
                if blocked_rows:
                    st.warning(f"{len(blocked_rows)} staged row(s) are not safe to apply yet.")
                    d1,d2=st.columns(2)
                    with d1:
                        st.markdown("**By failure reason**")
                        dataframe(reason_rows)
                    with d2:
                        st.markdown("**By target table**")
                        dataframe(table_rows)

                    with st.expander(f"Show all {len(blocked_rows)} blocked rows"):
                        dataframe(blocked_rows)

                    if reason_rows:
                        reason=st.selectbox(
                            "Inspect one blocker category",
                            [r["reason"] for r in reason_rows],
                            key=f"diag_reason_{jid}"
                        )
                        dataframe([r for r in blocked_rows if str(r.get("reason") or "unknown").strip()==reason])
                else:
                    st.success("No blocked rows remain.")

                if any(str(r.get("resolution_status") or "").upper()=="BROKEN_REFERENCE" for r in blocked_rows):
                    st.info(
                        "BROKEN_REFERENCE is now shown with endpoint-level diagnostics below. "
                        "This tells us whether the event is missing, the linked endpoint is missing, "
                        "the staged parent has a different canonical ID, or the resolver state is simply stale."
                    )

                    if st.button(
                        "🔎 Run dependency diagnostics",
                        key=f"diag_dependencies_{jid}",
                        use_container_width=True
                    ):
                        try:
                            diag=(sb.rpc(
                                "pc_debug_ingestion_dependencies",
                                {"p_ingestion_job_id":str(jid)}
                            ).execute().data or [])
                            st.session_state[f"dependency_diag_{jid}"]=diag
                        except Exception as exc:
                            st.error(
                                "Dependency diagnostics RPC is unavailable. Install migration 040 first. "
                                f"Database response: {exc}"
                            )

                    diag=st.session_state.get(f"dependency_diag_{jid}") or []
                    if diag:
                        st.markdown("##### Exact broken-reference diagnostics")
                        dataframe(diag)
                        diag_counts={}
                        for d in diag:
                            k=str(d.get("diagnostic") or "UNKNOWN")
                            diag_counts[k]=diag_counts.get(k,0)+1
                        dataframe([
                            {"diagnostic":k,"count":v}
                            for k,v in sorted(diag_counts.items(),key=lambda x:(-x[1],x[0]))
                        ])

                        if diag_counts.get("PARENT_EVENT_MISSING",0):
                            st.warning(
                                f"{diag_counts.get('PARENT_EVENT_MISSING',0)} child link(s) are waiting for a parent event "
                                "that is not yet canonical. Apply the safe parent event first, then retry the children."
                            )
                            if st.button(
                                "▶ Apply missing parent(s) + retry child links",
                                type="primary",
                                key=f"resolve_missing_parent_{jid}",
                                use_container_width=True
                            ):
                                with st.status("Applying safe parent records and retrying dependencies...",expanded=True) as status:
                                    dep_result=_resolve_missing_parent_dependencies(jid)
                                    st.session_state[f"dependency_recovery_{jid}"]=dep_result
                                    st.write("Parent apply",dep_result.get("parent_apply"))
                                    st.write("Child apply",dep_result.get("child_apply"))
                                    status.update(
                                        label="Dependency recovery pass complete — refreshing",
                                        state="complete",
                                        expanded=False
                                    )
                                st.rerun()

                        dep_result=st.session_state.get(f"dependency_recovery_{jid}")
                        if dep_result:
                            pa=dep_result.get("parent_apply") or {}
                            ca=dep_result.get("child_apply") or {}
                            st.caption(
                                f"Last dependency recovery: {pa.get('applied',0)} parent(s) applied; "
                                f"{ca.get('applied',0)} newly-safe child record(s) applied."
                            )

                raw_ready=int(summ.get("ready",0) or 0)
                if raw_ready != len(safe_candidates):
                    st.caption(
                        f"Resolution-ready: {raw_ready}. Safe-to-apply: {len(safe_candidates)}. "
                        "The difference is the validation/dependency layer above."
                    )

        with tabs[2]:
            if not jid:
                st.info("Select one ingestion job to match records manually.")
            else:
                st.markdown("#### Manual canonical matching")
                st.caption(
                    "Use this only for genuine exceptions. Apply all safe rows first, then match the smaller "
                    "remaining set here. Matching updates the staged row only; it does not overwrite canonical data."
                )
                try:
                    ex_rows=(sb.table("pc_staged_records")
                             .select("staged_record_id,target_table,natural_key,resolution_status,resolved_entity_id,resolution_method,candidate_count,payload,review_status,confidence")
                             .eq("ingestion_job_id",jid)
                             .in_("resolution_status",["UNRESOLVED","AMBIGUOUS","PARTIAL"])
                             .limit(1000).execute().data or [])
                except Exception as exc:
                    ex_rows=[]
                    st.error(f"Could not load exception rows: {exc}")

                identity_tables={"pc_entities":"entity","pc_assets":"asset","pc_mobile_assets":"mobile_asset","pc_events":"event"}
                identity_ex=[r for r in ex_rows if str(r.get("target_table") or "") in identity_tables]
                relationship_ex=[r for r in ex_rows if str(r.get("target_table") or "") in {"pc_event_links","pc_relationships"}]

                c1,c2,c3=st.columns(3)
                c1.metric("Identity exceptions",len(identity_ex))
                c2.metric("Relationship exceptions",len(relationship_ex))
                c3.metric("Total exceptions",len(ex_rows))

                if identity_ex:
                    def _ex_label(r):
                        p=r.get("payload") if isinstance(r.get("payload"),dict) else {}
                        nm=p.get("name") or p.get("title") or r.get("natural_key") or r.get("staged_record_id")
                        return f"{nm} | {r.get('target_table')} | {r.get('resolution_status')}"
                    labels=[_ex_label(r) for r in identity_ex]
                    chosen=st.selectbox("Exception to match",labels,key="manual_match_exception")
                    row=identity_ex[labels.index(chosen)]
                    kind=identity_tables[str(row.get("target_table"))]
                    payload=row.get("payload") if isinstance(row.get("payload"),dict) else {}
                    default_query=str(payload.get("name") or payload.get("title") or "").strip()
                    search=st.text_input("Search canonical registry",value=default_query,key="manual_match_search")
                    candidates=_canonical_link_candidates(kind,search,100) if search.strip() else []

                    if candidates:
                        idfield={"entity":"entity_id","asset":"asset_id","mobile_asset":"mobile_asset_id","event":"event_id"}[kind]
                        def _cand_label(r):
                            rid=r.get(idfield)
                            nm=r.get("name") or r.get("title") or rid
                            extra=[]
                            if kind=="mobile_asset" and r.get("imo"): extra.append(f"IMO {r.get('imo')}")
                            if r.get("country"): extra.append(str(r.get("country")))
                            return f"{nm} | {rid}" + (f" | {' · '.join(extra)}" if extra else "")
                        cand_labels=[_cand_label(r) for r in candidates]
                        cand_choice=st.selectbox("Canonical match",cand_labels,key="manual_match_candidate")
                        candidate=candidates[cand_labels.index(cand_choice)]
                        resolved_id=candidate.get(idfield)

                        st.json({
                            "staged_record":row.get("natural_key"),
                            "resolution_status":row.get("resolution_status"),
                            "proposed_match_id":resolved_id,
                            "proposed_match":candidate.get("name") or candidate.get("title"),
                        })

                        if st.button("Match selected staged record",type="primary",key="manual_match_apply"):
                            try:
                                sb.table("pc_staged_records").update({
                                    "resolved_entity_id":resolved_id,
                                    "resolution_status":"MATCHED",
                                    "resolution_method":"manual_match",
                                    "resolution_confidence":1.0,
                                    "candidate_count":len(candidates),
                                    "review_status":"pending",
                                    "validation_status":"pending",
                                }).eq("staged_record_id",row["staged_record_id"]).execute()
                                st.success(f"Matched to {resolved_id}. Re-running reconciliation...")
                                try:
                                    _run_reconciliation(jid)
                                except Exception:
                                    pass
                                st.rerun()
                            except Exception as exc:
                                st.error(f"Could not save manual match: {exc}")
                    else:
                        st.info("No canonical candidates found. Refine the search or treat this as a NEW record.")

                    if st.button("Treat selected record as NEW",key="manual_match_new"):
                        try:
                            # NEW keeps the prepared canonical ID in the payload and removes a forced match.
                            sb.table("pc_staged_records").update({
                                "resolved_entity_id":None,
                                "resolution_status":"NEW",
                                "resolution_method":"manual_new",
                                "resolution_confidence":1.0,
                                "candidate_count":0,
                                "review_status":"pending",
                                "validation_status":"pending",
                            }).eq("staged_record_id",row["staged_record_id"]).execute()
                            st.success("Marked as NEW. Re-running reconciliation...")
                            try:
                                _run_reconciliation(jid)
                            except Exception:
                                pass
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Could not mark NEW: {exc}")
                else:
                    st.success("No identity exceptions remain for manual matching.")

                if relationship_ex:
                    st.warning(
                        f"{len(relationship_ex)} relationship/event-link exception(s) remain. "
                        "Use the Relationships tab to resolve their endpoints after identity matching."
                    )

        with tabs[3]:
            if not jid:
                st.info("Select one ingestion job to run cleanup safely.")
            else:
                st.markdown("#### Standard cleanup order")
                st.code("Normalize → create safe missing dependencies → resolve aliases/endpoints → apply safe relationships → normalize staging → QA")
                if st.button("Run auto reconcile",type="primary"):
                    with st.spinner("Reconciling staged data..."):
                        res=_run_reconciliation(jid)
                    st.success("Reconciliation completed.")
                    st.json(res)
                    st.rerun()
        with tabs[4]:
            if jid:
                c1,c2=st.columns(2)
                if c1.button("Resolve event links"):
                    st.json(_process_relationship_backlog(sb,jid)); st.rerun()
                if c2.button("Resolve generic graph relationships"):
                    st.json(_process_generic_relationship_backlog(sb,jid)); st.rerun()
            else:
                st.info("Select a job.")
        with tabs[5]:
            try:
                stale=sb.table("pc_v_stale_ingestion_jobs").select("*").limit(250).execute().data or []
            except Exception:
                stale=[]
            dataframe(stale)
        with tabs[6]:
            st.markdown("Install these SQL migrations in order:")
            st.code("027_workflow_orchestration.sql\n028_document_ingestion.sql\n029_intelligence_authoring.sql\n030_distribution_lists.sql\n031_reconciliation_cleanup.sql\n032_event_first_dependency_engine.sql\n033_dependency_autocreate_engine.sql\n034_ingestion_quality_checks.sql\n035_dependency_regression_checks.sql\n036_compact_workflow_views.sql")
            st.caption("The cleanup functions are job-scoped and operate on staging before canonical apply.")

elif page=="Document Loader":
    title("Document / report loader","Upload a source document, link it to a company/event/vessel/asset, preserve extracted text, and optionally stage AI-extracted facts.")
    if not sb:
        st.error("Supabase required.")
    elif not _table_exists("pc_documents"):
        st.error("Run 028_document_ingestion.sql first.")
    else:
        up=st.file_uploader("DOCX, PDF, TXT or MD",type=["docx","pdf","txt","md"],key="document_loader")
        if up:
            try:
                text=_extract_document_text(up)
                file_hash=hashlib.sha256(up.getvalue()).hexdigest()
                st.caption(f"Extracted {len(text):,} characters · SHA-256 {file_hash[:16]}…")
                with st.expander("Preview extracted text"):
                    st.text(text[:12000])
                c1,c2=st.columns(2)
                doc_title=c1.text_input("Document title",value=Path(up.name).stem)
                doc_type=c2.selectbox("Document type",["company_report","annual_report","contract","government_notice","intelligence_source","research_report","presentation","other"])
                c3,c4,c5=st.columns(3)
                publisher=c3.text_input("Publisher / issuer")
                pub_date=c4.date_input("Publication date",value=None)
                source_url=c5.text_input("Source URL (optional)")

                st.markdown("#### Link document")
                l1,l2=st.columns([1,2])
                kind=l1.selectbox("Linked object type",["entity","asset","mobile_asset","event"])
                search=l2.text_input("Find canonical object",placeholder="DP World, Jebel Ali, USCGC Healy, event title...")
                candidates=_canonical_link_candidates(kind,search,100) if search.strip() else []
                selected_id=None
                if candidates:
                    def _cand_label(r):
                        rid=r.get({"entity":"entity_id","asset":"asset_id","mobile_asset":"mobile_asset_id","event":"event_id"}[kind])
                        nm=r.get("name") or r.get("title") or rid
                        return f"{nm} | {rid}"
                    labels=[_cand_label(r) for r in candidates]
                    chosen=st.selectbox("Canonical match",labels)
                    selected_id=candidates[labels.index(chosen)].get({"entity":"entity_id","asset":"asset_id","mobile_asset":"mobile_asset_id","event":"event_id"}[kind])

                if st.button("Save document",type="primary"):
                    existing=(sb.table("pc_documents").select("document_id").eq("file_sha256",file_hash).limit(1).execute().data or [])
                    payload={
                        "title":doc_title,"document_type":doc_type,"file_name":up.name,
                        "file_sha256":file_hash,"mime_type":mimetypes.guess_type(up.name)[0],
                        "publisher":publisher or None,"publication_date":str(pub_date) if pub_date else None,
                        "source_url":source_url or None,"extracted_text":text,
                        "metadata":{"original_size_bytes":len(up.getvalue())}
                    }
                    if existing:
                        doc_id=existing[0]["document_id"]
                        sb.table("pc_documents").update(payload).eq("document_id",doc_id).execute()
                    else:
                        doc_id=sb.table("pc_documents").insert(payload).execute().data[0]["document_id"]
                    if selected_id:
                        sb.table("pc_document_links").insert({
                            "document_id":doc_id,"linked_type":kind,"linked_id":selected_id,"relationship":"source_for"
                        }).execute()
                    st.success(f"Document saved: {doc_id}")
                    st.session_state["_last_document_id"]=doc_id

                doc_id=st.session_state.get("_last_document_id")
                if doc_id:
                    st.markdown("#### AI fact extraction to staging")
                    extraction_prompt=st.text_area(
                        "Extraction instruction",
                        value="Extract only facts supported by this document into the P&C canonical staging schema. Preserve source-document provenance. Do not invent facts.",
                        height=110
                    )
                    if st.button("Extract document facts → staging"):
                        if not ai_configured():
                            st.error("Configure OPENAI_API_KEY and OPENAI_MODEL.")
                        else:
                            job=sb.table("pc_ingestion_jobs").insert({
                                "job_type":"DOCUMENT_INGEST","title":doc_title,
                                "query_text":extraction_prompt,
                                "source_scope":{"document_id":doc_id,"file_name":up.name},
                                "status":"running"
                            }).execute().data[0]
                            prompt=extraction_prompt + "\n\nSOURCE DOCUMENT:\n" + text[:60000]
                            result=ai_research(prompt,"DOCUMENT",False,output_contract=AI_OUTPUT_CONTRACT)
                            staged,rejected,resolution=stage_ai_result(sb,job["ingestion_job_id"],result)
                            auto_result=_run_reconciliation(job["ingestion_job_id"]) if staged else {}
                            sb.table("pc_ingestion_jobs").update({
                                "status":"completed","completed_at":pd.Timestamp.utcnow().isoformat(),
                                "stats":{"document_id":doc_id,"staged_records":staged,"rejected":rejected,"resolution":resolution,"auto_reconcile":auto_result}
                            }).eq("ingestion_job_id",job["ingestion_job_id"]).execute()
                            st.success(f"{staged} proposal(s) staged and auto-reconciled from the document.")
                            st.json(auto_result,expanded=False)
            except Exception as exc:
                st.exception(exc)

elif page=="Distribution Lists":
    title("Email lists & distribution","Load contacts and maintain product distribution lists without mixing recipient data into the trade entity model.")
    if not sb:
        st.error("Supabase required.")
    elif not _table_exists("pc_contacts"):
        st.error("Run 030_distribution_lists.sql first.")
    else:
        tabs=st.tabs(["Lists","Contacts","Bulk loader"])
        with tabs[0]:
            lists=safe_rows(sb,"pc_distribution_lists","*",250,order="name")
            dataframe(lists)
            with st.form("new_dist_list"):
                n=st.text_input("List name")
                d=st.text_input("Description")
                scope=st.text_input("Product scope",placeholder="GCC Weekly / Black Sea / Alerts / Clients")
                if st.form_submit_button("Create list") and n.strip():
                    sb.table("pc_distribution_lists").insert({"name":n.strip(),"description":d or None,"product_scope":scope or None}).execute()
                    st.rerun()
        with tabs[1]:
            contacts=safe_rows(sb,"pc_contacts","contact_id,name,email,organisation,role_title,country,subscription_status,source,updated_at",500,order="updated_at")
            dataframe(contacts)
        with tabs[2]:
            up=st.file_uploader("CSV / XLSX email list",type=["csv","xlsx"],key="email_bulk")
            lists=safe_rows(sb,"pc_distribution_lists","distribution_list_id,name,active",250,order="name")
            list_map={r["name"]:r["distribution_list_id"] for r in lists if r.get("active",True)}
            target_list=st.selectbox("Default distribution list",["None"]+sorted(list_map))
            if up:
                df=pd.read_csv(up,dtype=object) if up.name.lower().endswith(".csv") else pd.read_excel(up,dtype=object)
                cols=list(df.columns)
                def pick(label,candidates):
                    default=0
                    for i,c in enumerate([""]+cols):
                        if _norm_field(c) in candidates:
                            default=i; break
                    return st.selectbox(label,[""]+cols,index=default,key=f"emailmap_{label}")
                c1,c2,c3=st.columns(3)
                email_col=c1.selectbox("Email column",cols,index=next((i for i,c in enumerate(cols) if _norm_field(c) in {"email","email_address","e_mail"}),0))
                name_col=c2.selectbox("Name column",[""]+cols,index=next((i+1 for i,c in enumerate(cols) if _norm_field(c) in {"name","full_name","contact_name"}),0))
                org_col=c3.selectbox("Organisation column",[""]+cols,index=next((i+1 for i,c in enumerate(cols) if _norm_field(c) in {"organisation","organization","company"}),0))
                r1,r2=st.columns(2)
                role_col=r1.selectbox("Role column",[""]+cols,index=next((i+1 for i,c in enumerate(cols) if _norm_field(c) in {"role","title","job_title"}),0))
                country_col=r2.selectbox("Country column",[""]+cols,index=next((i+1 for i,c in enumerate(cols) if _norm_field(c)=="country"),0))
                st.dataframe(df.head(20),use_container_width=True,hide_index=True)

                if st.button("Import contacts",type="primary"):
                    upserted=members=0; errors=[]
                    for _,r in df.iterrows():
                        email=str(r.get(email_col) or "").strip().lower()
                        if not email or "@" not in email:
                            continue
                        payload={
                            "email":email,
                            "name":str(r.get(name_col) or "").strip() if name_col else None,
                            "organisation":str(r.get(org_col) or "").strip() if org_col else None,
                            "role_title":str(r.get(role_col) or "").strip() if role_col else None,
                            "country":str(r.get(country_col) or "").strip() if country_col else None,
                            "source":up.name
                        }
                        try:
                            hit=(sb.table("pc_contacts").select("contact_id").ilike("email",email).limit(1).execute().data or [])
                            if hit:
                                cid=hit[0]["contact_id"]
                                sb.table("pc_contacts").update(payload).eq("contact_id",cid).execute()
                            else:
                                cid=sb.table("pc_contacts").insert(payload).execute().data[0]["contact_id"]
                            upserted+=1
                            if target_list!="None":
                                try:
                                    sb.table("pc_distribution_memberships").upsert({
                                        "distribution_list_id":list_map[target_list],"contact_id":cid,"status":"active"
                                    },on_conflict="distribution_list_id,contact_id").execute()
                                    members+=1
                                except Exception as exc:
                                    errors.append(str(exc))
                        except Exception as exc:
                            errors.append(f"{email}: {exc}")
                    sb.table("pc_email_import_jobs").insert({
                        "file_name":up.name,"rows_seen":len(df),"contacts_upserted":upserted,
                        "memberships_upserted":members,"errors":errors
                    }).execute()
                    st.success(f"Imported/updated {upserted} contact(s); {members} membership(s).")
                    if errors: st.warning(f"{len(errors)} row/membership error(s).")


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
            use_canonical_context=st.checkbox(
                "Use canonical database context",True,
                help="Pass likely matching companies/assets/vessels and existing graph links from Supabase to the researcher before web research."
            )
        with c3:
            st.metric("Pending staged",count_rows(sb,"pc_staged_records",{"review_status":"pending"}))

        canonical_context={}
        if use_canonical_context and prompt.strip():
            try:
                canonical_context=build_canonical_research_context(sb,prompt)
                cc=canonical_context.get("candidate_counts",{})
                st.caption(
                    f"Canonical pre-check: {cc.get('entities',0)} companies/entities · "
                    f"{cc.get('assets',0)} assets · {cc.get('mobile_assets',0)} vessels · "
                    f"{cc.get('relationships',0)} existing relationships."
                )
                with st.expander("Preview canonical candidates sent to the researcher"):
                    st.json(canonical_context)
            except Exception as exc:
                st.warning(f"Canonical context pre-check failed; research can still run through normal staging: {exc}")
                canonical_context={}

        st.caption(
            "The AI researcher must provide source URLs and confidence. "
            "All output goes to pc_staged_records for review before canonical apply."
        )

        if st.button("Run AI research job",type="primary",disabled=not bool(prompt.strip())):
            if not ai_configured():
                st.error("Configure OPENAI_API_KEY and OPENAI_MODEL.")
            else:
                effective_prompt=prompt
                if use_canonical_context and canonical_context:
                    effective_prompt += canonical_context_prompt_block(canonical_context)

                job=sb.table("pc_ingestion_jobs").insert({
                    "job_type":"AI_RESEARCH",
                    "title":campaign if campaign!="Custom research" else prompt[:100],
                    "query_text":prompt,
                    "source_scope":{
                        "product":context,
                        "web_search":use_web,
                        "campaign":campaign,
                        "canonical_context":bool(use_canonical_context),
                        "canonical_candidate_counts":(canonical_context or {}).get("candidate_counts",{}),
                    },
                    "status":"running",
                }).execute().data[0]

                job_id=job["ingestion_job_id"]

                try:
                    with st.status("Running AI research...",expanded=True) as status:
                        if use_canonical_context and canonical_context:
                            cc=canonical_context.get("candidate_counts",{})
                            st.write(
                                "Canonical pre-check attached: "
                                f"{cc.get('entities',0)} entities, {cc.get('assets',0)} assets, "
                                f"{cc.get('mobile_assets',0)} vessels, {cc.get('relationships',0)} relationships."
                            )
                        st.write("Sending research brief to OpenAI...")
                        result=ai_research(
                            effective_prompt,
                            context,
                            use_web,
                            output_contract=AI_OUTPUT_CONTRACT
                        )

                        st.write("Research returned. Validating structured proposals...")
                        staged,rejected,resolution=stage_ai_result(sb,job_id,result)

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
                                "resolution":resolution,
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

elif page=="Data Completion":
    title(
        "Data completion",
        "Turn gaps already present in Supabase into a controlled enrichment queue. Internal deterministic repairs are staged for review; nothing writes directly to canonical tables."
    )
    if not sb:
        st.error("Supabase service connection required.")
    else:
        with st.spinner("Scanning canonical and staging tables for incomplete records..."):
            inv=_completion_inventory(sb)

        m1,m2,m3,m4,m5,m6,m7=st.columns(7)
        m1.metric("Vessels missing IMO",len(inv["vessel_identity"]))
        m2.metric("Vessel owner/operator gaps",len(inv["vessel_relationship"]))
        m3.metric("Ports missing coordinates",len(inv["asset_geo"]))
        m4.metric("Events missing links",len(inv["event_links"]))
        m5.metric("Events missing mapped location",len(inv["event_geo"]))
        m6.metric("Relationship backlog",len(inv["relationship_backlog"]))
        m7.metric("Relationships ready",len(inv["relationship_ready"]))

        st.caption("Counts are live from the canonical Supabase database. A record can appear in more than one gap category.")
        tabs=st.tabs(["Priority queue","Vessels","Assets & ports","Events","Resolution backlog","Relationship backlog","Deterministic repairs","Open DQ issues"])

        with tabs[0]:
            summary=[
                {"Priority":1,"Workstream":"Vessel identity","Records":len(inv["vessel_identity"]),"Why":"IMO is the strongest vessel identity key."},
                {"Priority":2,"Workstream":"Staged relationship resolution","Records":len(inv["relationship_backlog"]),"Why":"Existing event/vessel/company link proposals should be resolved before new research."},
                {"Priority":3,"Workstream":"Events without entity links","Records":len(inv["event_links"]),"Why":"Unlinked incidents cannot roll up to vessel/company/asset pages."},
                {"Priority":4,"Workstream":"Ports without coordinates","Records":len(inv["asset_geo"]),"Why":"Prevents reliable mapping and geographic event correlation."},
                {"Priority":5,"Workstream":"Vessel owner/operator","Records":len(inv["vessel_relationship"]),"Why":"Breaks company-fleet and exposure relationships."},
                {"Priority":6,"Workstream":"Events without mapped location","Records":len(inv["event_geo"]),"Why":"Limits Intelligence map coverage."},
                {"Priority":7,"Workstream":"Record identity backlog","Records":len(inv["staging_backlog"]),"Why":"Already-collected records are waiting for identity decisions."},
            ]
            st.dataframe(pd.DataFrame(summary),use_container_width=True,hide_index=True)
            st.info("Start with deterministic internal repairs first. Only genuine gaps should be sent to external/AI research afterward.")

        with tabs[1]:
            vt=st.tabs(["Missing IMO","Missing owner/operator","Provenance / quality"])
            with vt[0]:
                rows=inv["vessel_identity"]
                st.caption(f"{len(rows):,} vessel record(s) have no IMO in canonical pc_mobile_assets.")
                if rows:
                    df=pd.DataFrame(rows)
                    cols=[c for c in ["name","mobile_asset_id","asset_type","subtype","mmsi","flag","owner_entity_id","operator_entity_id","source_id","record_status","data_quality"] if c in df.columns]
                    st.dataframe(df[cols],use_container_width=True,hide_index=True)
            with vt[1]:
                rows=inv["vessel_relationship"]
                if rows:
                    df=pd.DataFrame(rows); cols=[c for c in ["name","mobile_asset_id","imo","flag","owner_entity_id","operator_entity_id","manager_entity_id","source_id"] if c in df.columns]
                    st.dataframe(df[cols],use_container_width=True,hide_index=True)
                else: st.success("No vessel owner/operator gaps detected.")
            with vt[2]:
                rows=inv["vessel_provenance"]
                if rows:
                    df=pd.DataFrame(rows); cols=[c for c in ["name","mobile_asset_id","imo","source_id","record_status","data_quality"] if c in df.columns]
                    st.dataframe(df[cols],use_container_width=True,hide_index=True)
                else: st.success("No vessel provenance/quality gaps detected.")

        with tabs[2]:
            at=st.tabs(["Ports missing coordinates","Owner/operator gaps","Provenance / quality"])
            with at[0]:
                rows=inv["asset_geo"]
                if rows:
                    df=pd.DataFrame(rows); cols=[c for c in ["name","asset_id","asset_type","subtype","country","region_city","latitude","longitude","owner_entity_id","operator_entity_id","source_id"] if c in df.columns]
                    st.dataframe(df[cols],use_container_width=True,hide_index=True)
                else: st.success("All detected port/terminal assets have coordinates.")
            with at[1]:
                rows=inv["asset_relationship"]
                if rows:
                    df=pd.DataFrame(rows); cols=[c for c in ["name","asset_id","asset_type","country","owner_entity_id","operator_entity_id","source_id"] if c in df.columns]
                    st.dataframe(df[cols],use_container_width=True,hide_index=True)
            with at[2]:
                rows=inv["asset_provenance"]
                if rows:
                    df=pd.DataFrame(rows); cols=[c for c in ["name","asset_id","asset_type","country","source_id","record_status","data_quality"] if c in df.columns]
                    st.dataframe(df[cols],use_container_width=True,hide_index=True)

        with tabs[3]:
            et=st.tabs(["Missing links","Missing mapped location","Provenance"])
            with et[0]:
                rows=inv["event_links"]
                if rows:
                    df=pd.DataFrame(rows); cols=[c for c in ["start_date","title","event_id","event_domain","event_type","location","source_id","record_status"] if c in df.columns]
                    st.dataframe(df[cols],use_container_width=True,hide_index=True)
                else: st.success("Every canonical event has at least one linked object.")
            with et[1]:
                rows=inv["event_geo"]
                if rows:
                    df=pd.DataFrame(rows); cols=[c for c in ["start_date","title","event_id","event_domain","location","countries","source_id"] if c in df.columns]
                    st.dataframe(df[cols],use_container_width=True,hide_index=True)
                else: st.success("Every canonical event has a mapped event location.")
            with et[2]:
                rows=inv["event_provenance"]
                if rows:
                    df=pd.DataFrame(rows); cols=[c for c in ["start_date","title","event_id","source_id","record_status","confidence"] if c in df.columns]
                    st.dataframe(df[cols],use_container_width=True,hide_index=True)

        with tabs[4]:
            rows=inv["staging_backlog"]
            if not rows:
                st.success("No unresolved metadata-driven staging backlog.")
            else:
                df=pd.DataFrame(rows)
                cols=[c for c in ["created_at","target_entity_type","target_table","natural_key","resolution_status","resolution_method","resolution_confidence","candidate_count","review_status","validation_status","staged_record_id"] if c in df.columns]
                st.dataframe(df[cols],use_container_width=True,hide_index=True)
                st.caption("Use Staging Resolution for record-level identity review and Review Queue for canonical approval/apply.")

        with tabs[5]:
            st.markdown("### Staged relationship resolution")
            st.caption("SQL 011 resolves both endpoints of staged pc_event_links. READY can proceed to review; PARTIAL needs a missing target resolved or created; AMBIGUOUS requires analyst choice; BROKEN_REFERENCE means the parent/source endpoint is missing.")
            rels=inv.get("relationship_resolution") or []
            if rels:
                rdf=pd.DataFrame(rels)
                statuses=rdf["resolution_status"].fillna("UNRESOLVED") if "resolution_status" in rdf.columns else pd.Series([],dtype=str)
                rc1,rc2,rc3,rc4,rc5=st.columns(5)
                rc1.metric("Ready",int((statuses=="READY").sum()))
                rc2.metric("Already exists",int((statuses=="ALREADY_EXISTS").sum()))
                rc3.metric("Partial",int((statuses=="PARTIAL").sum()))
                rc4.metric("Ambiguous",int((statuses=="AMBIGUOUS").sum()))
                rc5.metric("Broken",int((statuses=="BROKEN_REFERENCE").sum()))
                rcols=[c for c in ["created_at","natural_key","relationship_type","from_source_key","resolved_from_entity_id","to_name","to_identifier_type","to_identifier_value","to_source_key","resolved_to_entity_id","resolution_status","to_resolution_method","to_candidate_count","existing_relationship_id","staged_record_id"] if c in rdf.columns]
                st.dataframe(rdf[rcols],use_container_width=True,hide_index=True)
            else:
                st.info("No SQL 011 relationship-resolution rows are available yet.")
            if st.button("Resolve all pending event-link relationships",type="primary",key="completion_resolve_relationships"):
                try:
                    result=_process_relationship_backlog(sb)
                    st.success(f"Relationship resolution complete: {result}")
                    st.rerun()
                except Exception as exc:
                    st.exception(exc)

        with tabs[6]:
            st.markdown("### Existing-database event → vessel repair")
            st.caption("This uses no AI and no web research. It looks only for an IMO explicitly present in event text or a unique canonical vessel name explicitly present in a maritime event. Candidates are staged as pc_event_links for normal review.")
            candidates=_event_vessel_candidates(inv)
            st.metric("High-confidence internal candidates",len(candidates))
            if candidates:
                cdf=pd.DataFrame(candidates)
                edited=st.data_editor(
                    cdf.assign(**{"Stage?":True})[["Stage?","event_title","event_id","vessel_name","imo","mobile_asset_id","match_method","confidence"]],
                    use_container_width=True,hide_index=True,
                    disabled=["event_title","event_id","vessel_name","imo","mobile_asset_id","match_method","confidence"],
                    key="completion_event_vessel_candidates"
                )
                chosen=[candidates[i] for i,val in enumerate(edited["Stage?"].tolist()) if bool(val)]
                if st.button("Stage selected deterministic links",type="primary",disabled=not bool(chosen)):
                    with st.spinner("Staging deterministic event-vessel links..."):
                        result=_stage_event_vessel_repairs(sb,chosen)
                    st.success(f"Staged {result['staged']} event-vessel link proposal(s). Review them in Staging Resolution / Review Queue before canonical apply.")
                    st.rerun()
            else:
                st.info("No new high-confidence event-vessel links can be derived from the existing database at this time.")

        with tabs[7]:
            rows=inv["open_issues"]
            if rows: dataframe(rows)
            else: st.success("No open data-quality issues.")

elif page=="Model Registry":
    title(
        "Model registry",
        "Executable metadata for the canonical P&C model: entity types, keys, columns, identifiers, relationships and match rules."
    )
    if not sb:
        st.error("Supabase service connection required.")
    else:
        c1,c2,c3,c4=st.columns(4)
        entities=safe_rows(sb,"pc_meta_entity_types","*",500)
        columns=safe_rows(sb,"pc_meta_columns","*",5000)
        reltypes=safe_rows(sb,"pc_meta_relationship_types","*",1000)
        rules=safe_rows(sb,"pc_meta_match_rules","*",2000)
        c1.metric("Entity types",len(entities))
        c2.metric("Registered columns",len(columns))
        c3.metric("Relationship types",len(reltypes))
        c4.metric("Match rules",len(rules))

        top1,top2=st.columns([1,3])
        if top1.button("Refresh model registry",type="primary"):
            with st.spinner("Refreshing PostgreSQL model metadata..."):
                try:
                    result=_rpc_data(sb,"pc_refresh_model_registry")
                    st.success(f"Model registry refreshed{f': {result}' if result is not None else '.'}")
                    st.rerun()
                except Exception as exc:
                    st.exception(exc)
        top2.caption("Refresh introspects the canonical PostgreSQL tables defined in pc_meta_entity_types; it does not alter canonical business data.")

        tabs=st.tabs(["Entity types","Columns & keys","Match rules","Relationships","Identifier registry"])
        with tabs[0]:
            dataframe(sorted(entities,key=lambda x:str(x.get("entity_type") or "")))
        with tabs[1]:
            if columns:
                df=pd.DataFrame(columns)
                preferred=[c for c in ["entity_type","table_name","ordinal_position","column_name","data_type","required","is_primary_key","is_natural_key","identifier_type","match_priority","reference_entity_type","reference_column","allow_stage","allow_update"] if c in df.columns]
                st.dataframe(df[preferred],use_container_width=True,hide_index=True)
            else:
                st.caption("No registered columns. Run Refresh model registry.")
        with tabs[2]:
            dataframe(sorted(rules,key=lambda x:(str(x.get("entity_type") or ""),int(x.get("priority") or 9999))))
        with tabs[3]:
            dataframe(reltypes)
        with tabs[4]:
            ids=safe_rows(sb,"pc_entity_identifiers","*",2000)
            dataframe(ids)

elif page=="Batch Staging":
    title(
        "Metadata-driven batch staging",
        "Upload CSV/JSON into the controlled staging gateway. SQL 010 expands fields, resolves canonical identities, and leaves ambiguous records for review."
    )

    meta_entities=_meta_entity_types(sb) if sb else []
    meta_by_table={r["table_name"]:r for r in meta_entities if r.get("table_name")}

    legacy_targets=[
        "pc_transactions","pc_security_compliance","pc_energy_assets","pc_energy_asset_connections",
        "pc_industrial_assets","pc_logistics_facilities","pc_market_instruments","pc_market_prices",
        "pc_market_exposure_links","pc_trade_flows","pc_supply_series","pc_port_metrics",
        "pc_port_capabilities","pc_macro_indicators","pc_observations","pc_market_reports",
        "pc_market_observations"
    ]
    registered_targets=[r.get("table_name") for r in meta_entities if r.get("table_name")]
    all_targets=list(dict.fromkeys(registered_targets+legacy_targets))

    if meta_entities:
        st.success(f"SQL 010 metadata layer detected: {len(meta_entities)} active entity type(s).")
    else:
        st.warning("Metadata registry is not readable. Batch staging will use compatibility mode until pc_meta_entity_types is available.")

    def _target_label(table):
        m=meta_by_table.get(table)
        if m:
            return f"{m.get('entity_type')}  →  {table}"
        return f"legacy / extension  →  {table}"

    target=st.selectbox("Target logical entity / table",all_targets,format_func=_target_label)
    target_meta=meta_by_table.get(target) or {}
    target_entity_type=target_meta.get("entity_type")

    if target_meta:
        a,b,c=st.columns(3)
        a.metric("Entity type",target_entity_type or "—")
        b.metric("Primary key",target_meta.get("primary_key_column") or "—")
        c.metric("Display field",target_meta.get("display_name_column") or "—")

        try:
            rules=(sb.table("pc_meta_match_rules").select("priority,rule_name,match_type,source_column,identifier_type,minimum_score")
                   .eq("entity_type",target_entity_type).eq("active",True).order("priority").execute().data or [])
        except Exception:
            rules=[]
        if rules:
            with st.expander("Resolution rules for this entity type"):
                st.dataframe(pd.DataFrame(rules),use_container_width=True,hide_index=True)

    up=st.file_uploader("CSV or JSON",type=["csv","json"])

    def _parse_jsonish(v):
        if isinstance(v,(dict,list)) or v is None:
            return v
        ss=str(v).strip()
        if not ss:
            return None
        if (ss.startswith("{") and ss.endswith("}")) or (ss.startswith("[") and ss.endswith("]")):
            try:
                return json.loads(ss)
            except Exception:
                return v
        return v

    def _clean_scalar(v):
        if v is None:
            return None
        if isinstance(v,float) and pd.isna(v):
            return None
        ss=str(v).strip()
        return None if ss=="" or ss.lower()=="nan" else v

    def _normalize_incoming_row(r,target_table):
        row={k:_clean_scalar(v) for k,v in dict(r).items()}
        for col in ("raw_value","derived_value","metadata","source_scope","stats","payload","current_record"):
            if col in row:
                row[col]=_parse_jsonish(row[col])
        for col in ("attribution_required","active"):
            if col in row and row[col] is not None and not isinstance(row[col],bool):
                row[col]=str(row[col]).strip().lower() in {"1","true","yes","y"}
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
                    if raw.get(k): return str(raw[k])
            if isinstance(meta,dict):
                for k in ("source_record_id","legacy_observation_id"):
                    if meta.get(k): return str(meta[k])
        for key in ("entity_id","asset_id","mobile_asset_id","relationship_id","event_id","event_link_id",
                    "transaction_id","route_id","chokepoint_id","market_instrument_id","trade_flow_id",
                    "supply_series_id","observation_id","imo","mmsi","name","title","route_name"):
            if r.get(key): return str(r[key])
        return str(index)

    if up:
        try:
            if up.name.lower().endswith(".csv"):
                rows=pd.read_csv(up,dtype=object).to_dict("records")
            else:
                obj=json.load(up)
                rows=obj if isinstance(obj,list) else obj.get("records",[obj])

            rows=[_normalize_incoming_row(r,target) for r in rows]
            st.caption(f"{len(rows):,} incoming row(s)")
            st.dataframe(pd.DataFrame(rows[:50]),use_container_width=True,hide_index=True)

            auto_resolve=st.checkbox(
                "Run metadata-driven resolution after staging",
                value=bool(target_entity_type),
                disabled=not bool(target_entity_type),
                help="Uses pc_process_ingestion_job. Resolution never writes directly to canonical tables."
            )

            if st.button("Stage & resolve batch" if auto_resolve else "Stage batch",type="primary"):
                if not sb:
                    st.error("Supabase required.")
                else:
                    if target=="pc_observations" and any(r.get("source_id")=="SRC_OPEN_RECAAP_ISC" for r in rows):
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
                        "source_scope":{
                            "target_table":target,
                            "target_entity_type":target_entity_type,
                            "rows":len(rows),
                            "metadata_driven":bool(target_entity_type)
                        },
                        "status":"running"
                    }).execute().data[0]

                    payloads=[]
                    for i,r in enumerate(rows,1):
                        payloads.append({
                            "ingestion_job_id":job["ingestion_job_id"],
                            "target_entity_type":target_entity_type,
                            "target_table":target,
                            "source_record_key":_natural_key_for_row(r,target,i),
                            "natural_key":_natural_key_for_row(r,target,i),
                            "action":"REVIEW",
                            "payload":r,
                            "confidence":1.0,
                            "validation_status":"pending",
                            "review_status":"pending",
                            "resolution_status":"UNRESOLVED"
                        })

                    total_batches=max(1,(len(payloads)+249)//250)
                    progress=st.progress(0.0,text="Staging batch...")
                    for batch_no,i in enumerate(range(0,len(payloads),250),start=1):
                        sb.table("pc_staged_records").insert(payloads[i:i+250]).execute()
                        progress.progress(batch_no/total_batches,text=f"Staging batch {batch_no}/{total_batches}")

                    resolution=None
                    if auto_resolve and target_entity_type:
                        if target=="pc_event_links":
                            progress.progress(0.95,text="Resolving relationship endpoints...")
                            resolution=_process_relationship_backlog(sb,job["ingestion_job_id"])
                        else:
                            progress.progress(0.95,text="Resolving canonical identities...")
                            resolution=_process_job_resolution(sb,job["ingestion_job_id"])

                    sb.table("pc_ingestion_jobs").update({
                        "status":"completed",
                        "completed_at":pd.Timestamp.utcnow().isoformat(),
                    }).eq("ingestion_job_id",job["ingestion_job_id"]).execute()
                    progress.progress(1.0,text="Batch staged and processed.")

                    if resolution:
                        if target=="pc_event_links":
                            st.success(
                                f"Staged {len(rows):,} relationship row(s): {resolution.get('ready',0)} ready, "
                                f"{resolution.get('already_exists',0)} already exist, {resolution.get('partial',0)} partial, "
                                f"{resolution.get('ambiguous',0)} ambiguous, {resolution.get('broken_reference',0)} broken."
                            )
                        else:
                            st.success(
                                f"Staged {len(rows):,} row(s): {resolution.get('matched',0)} matched, "
                                f"{resolution.get('new',0)} new, {resolution.get('ambiguous',0)} ambiguous, "
                                f"{resolution.get('invalid',0)} invalid."
                            )
                    else:
                        st.success(f"Staged {len(rows):,} row(s).")
                    st.info("Next: open Staging Resolution to inspect identity decisions, then Review Queue for canonical approval/apply.")

        except Exception as exc:
            st.exception(exc)


elif page=="Staging Resolution":
    title(
        "Staging resolution",
        "Resolve canonical identities and relationship endpoints before canonical apply. Entity records use MATCHED/NEW/AMBIGUOUS; relationships use READY/PARTIAL/AMBIGUOUS/BROKEN_REFERENCE/ALREADY_EXISTS."
    )
    if not sb:
        st.error("Supabase service connection required.")
    else:
        entity_tab,relationship_tab=st.tabs(["Entity / record resolution","Relationship resolution"])

        with entity_tab:
            rows=[r for r in _resolution_rows(sb,3000) if r.get("target_table") not in {"pc_event_links","pc_relationships","research_bundle"} and r.get("target_entity_type") not in {"event_link","relationship"}]
            if not rows:
                st.info("No metadata-driven entity/record resolution rows are available yet.")
            else:
                df=pd.DataFrame(rows)
                statuses=df["resolution_status"].fillna("UNRESOLVED") if "resolution_status" in df.columns else pd.Series([],dtype=str)
                c1,c2,c3,c4,c5=st.columns(5)
                c1.metric("Total",len(df))
                c2.metric("Matched",int((statuses=="MATCHED").sum()))
                c3.metric("New",int((statuses=="NEW").sum()))
                c4.metric("Ambiguous",int((statuses=="AMBIGUOUS").sum()))
                c5.metric("Invalid / unresolved",int(statuses.isin(["INVALID","UNRESOLVED"]).sum()))

                options=["ALL"]+sorted(str(x) for x in df["resolution_status"].dropna().unique()) if "resolution_status" in df.columns else ["ALL"]
                status_filter=st.selectbox("Entity resolution status",options,key="entity_resolution_status")
                view=df if status_filter=="ALL" else df[df["resolution_status"]==status_filter]
                preferred=[c for c in ["created_at","target_entity_type","target_table","natural_key","resolution_status","resolved_entity_id","resolution_method","resolution_confidence","candidate_count","staged_value_count","validation_status","review_status","staged_record_id"] if c in view.columns]
                st.dataframe(view[preferred],use_container_width=True,hide_index=True)

            st.markdown("### Re-run entity resolution")
            try:
                jobs=(sb.table("pc_ingestion_jobs").select("ingestion_job_id,title,status,created_at,stats").order("created_at",desc=True).limit(100).execute().data or [])
            except Exception:
                jobs=[]
            if jobs:
                labels=[f"{j.get('title') or 'Untitled'} | {j.get('ingestion_job_id')}" for j in jobs]
                chosen=st.selectbox("Ingestion job",labels,key="entity_resolution_job")
                job=jobs[labels.index(chosen)]
                if st.button("Prepare + resolve entity records in this job",key="rerun_entity_resolution"):
                    try:
                        result=_rpc_data(sb,"pc_prepare_and_resolve_entity_job",{"p_ingestion_job_id":str(job["ingestion_job_id"])}) or {}
                        st.success(
                            f"Prepared {result.get('prepared',0)} row(s); resolved {result.get('total',0)} entity record(s): "
                            f"{result.get('matched',0)} matched, {result.get('new',0)} new, "
                            f"{result.get('ambiguous',0)} ambiguous, {result.get('invalid',0)} invalid."
                        )
                        st.rerun()
                    except Exception as exc:
                        st.exception(exc)

        with relationship_tab:
            rels=[r for r in _relationship_resolution_rows(sb,10000) if r.get("target_table")=="pc_event_links"]
            if not rels:
                st.warning("No relationship-resolution rows are visible. Run SQL 011 first; it backfills the existing pc_event_links staging backlog without writing canonical data.")
            else:
                rdf=pd.DataFrame(rels)
                statuses=rdf["resolution_status"].fillna("UNRESOLVED") if "resolution_status" in rdf.columns else pd.Series([],dtype=str)
                r1,r2,r3,r4,r5,r6=st.columns(6)
                r1.metric("Total",len(rdf))
                r2.metric("Ready",int((statuses=="READY").sum()))
                r3.metric("Already exists",int((statuses=="ALREADY_EXISTS").sum()))
                r4.metric("Partial",int((statuses=="PARTIAL").sum()))
                r5.metric("Ambiguous",int((statuses=="AMBIGUOUS").sum()))
                r6.metric("Broken",int((statuses=="BROKEN_REFERENCE").sum()))

                roptions=["ALL"]+sorted(str(x) for x in rdf["resolution_status"].dropna().unique())
                rstatus=st.selectbox("Relationship status",roptions,key="relationship_resolution_status")
                rview=rdf if rstatus=="ALL" else rdf[rdf["resolution_status"]==rstatus]
                rcols=[c for c in ["created_at","natural_key","relationship_type","from_entity_type","from_source_key","resolved_from_entity_id","from_resolution_method","to_entity_type","to_name","to_identifier_type","to_identifier_value","to_source_key","resolved_to_entity_id","to_resolution_method","to_candidate_count","resolution_status","apply_status","canonical_relationship_id","applied_at","existing_relationship_id","review_status","staged_record_id"] if c in rview.columns]
                st.dataframe(rview[rcols],use_container_width=True,hide_index=True)

                pending_ready=int(((statuses=="READY") & (~rdf.get("apply_status",pd.Series(["PENDING"]*len(rdf))).fillna("PENDING").isin(["APPLIED","SKIPPED_EXISTS"]))).sum()) if len(rdf) else 0
                st.markdown("### Canonical vessel → event apply")
                st.caption(
                    "SQL 011 resolved the endpoints; SQL 012 performs the missing final step: it writes the resolved vessel as a canonical pc_event_links row for the event. "
                    "Every relationship is re-resolved immediately before insert, duplicates are skipped, and the write is audited."
                )
                a1,a2,a3=st.columns(3)
                a1.metric("READY awaiting apply",pending_ready)
                applied_count=int((rdf.get("apply_status",pd.Series([],dtype=str)).fillna("")=="APPLIED").sum()) if "apply_status" in rdf.columns else 0
                a2.metric("Applied",applied_count)
                a3.metric("Canonical event-vessel links",len(_canonical_event_vessel_links(sb,10000)))

                confirm_apply=st.checkbox(
                    "I confirm: promote all currently READY event relationships to canonical pc_event_links",
                    key="confirm_ready_relationship_apply"
                )
                if st.button(
                    f"Link READY vessels to events ({pending_ready})",
                    type="primary",
                    disabled=(not confirm_apply or pending_ready==0),
                    key="apply_ready_event_relationships"
                ):
                    try:
                        with st.spinner("Revalidating endpoints and linking vessels to canonical events..."):
                            result=_apply_ready_event_relationships(sb)
                        st.success(
                            f"Canonical linking complete — {result.get('applied',0)} applied, "
                            f"{result.get('already_exists',0)} already existed, {result.get('blocked',0)} blocked, "
                            f"{result.get('errors',0)} errors."
                        )
                        st.rerun()
                    except Exception as exc:
                        st.exception(exc)

                with st.expander("Verify canonical vessel-to-event links"):
                    verified=_canonical_event_vessel_links(sb,5000)
                    if verified:
                        vdf=pd.DataFrame(verified)
                        vcols=[c for c in ["event_date","event_id","event_title","mobile_asset_id","vessel_name","imo","mmsi","flag","vessel_type","relationship","confidence","event_link_id"] if c in vdf.columns]
                        st.dataframe(vdf[vcols],use_container_width=True,hide_index=True)
                    else:
                        st.info("No canonical event-vessel links are visible through pc_v_event_vessel_links yet. Run SQL 012, then apply READY relationships.")

            st.divider()
            st.markdown("## Generic graph relationships")
            st.caption(
                "SQL 013 resolves ordinary P&C graph edges such as company → operates → terminal, "
                "company → owns → company, and entity → operates → vessel. Endpoints are resolved against "
                "the canonical registry before anything can be written to pc_relationships."
            )
            grels=_generic_relationship_resolution_rows(sb,10000)

            staged_graph_preview=[]
            if not grels:
                try:
                    staged_rel_rows=(sb.table("pc_staged_records")
                        .select("staged_record_id,ingestion_job_id,natural_key,payload,review_status,created_at")
                        .eq("target_table","pc_relationships")
                        .order("created_at",desc=True)
                        .limit(500)
                        .execute().data or [])
                    for sr in staged_rel_rows:
                        pld=sr.get("payload") or {}
                        meta=pld.get("metadata") if isinstance(pld.get("metadata"),dict) else {}
                        staged_graph_preview.append({
                            "created_at":sr.get("created_at"),
                            "natural_key":sr.get("natural_key"),
                            "relationship_type":pld.get("relationship_type") or pld.get("relationship") or meta.get("relationship_type") or "related_to",
                            "from_name":pld.get("source_name") or pld.get("from_name") or meta.get("source_name") or meta.get("from_name") or pld.get("source_id") or "Source",
                            "from_source_key":pld.get("source_id"),
                            "to_name":pld.get("target_name") or pld.get("to_name") or meta.get("target_name") or meta.get("to_name") or pld.get("target_id") or "Target",
                            "to_source_key":pld.get("target_id"),
                            "resolution_status":"STAGED",
                            "review_status":sr.get("review_status"),
                            "staged_record_id":sr.get("staged_record_id"),
                        })
                except Exception as exc:
                    st.warning(f"Could not load staged graph fallback: {exc}")

            if grels:
                gdf=pd.DataFrame(grels)
                gstatuses=gdf["resolution_status"].fillna("UNRESOLVED") if "resolution_status" in gdf.columns else pd.Series([],dtype=str)
                g1,g2,g3,g4,g5,g6=st.columns(6)
                g1.metric("Total",len(gdf))
                g2.metric("Ready",int((gstatuses=="READY").sum()))
                g3.metric("Already exists",int((gstatuses=="ALREADY_EXISTS").sum()))
                g4.metric("Partial",int((gstatuses=="PARTIAL").sum()))
                g5.metric("Ambiguous",int((gstatuses=="AMBIGUOUS").sum()))
                g6.metric("Broken",int((gstatuses=="BROKEN_REFERENCE").sum()))
                missing_endpoint_labels=int(((gdf.get("from_name").isna() if "from_name" in gdf.columns else pd.Series([True]*len(gdf))) | (gdf.get("to_name").isna() if "to_name" in gdf.columns else pd.Series([True]*len(gdf)))).sum())
                if missing_endpoint_labels:
                    st.warning(f"{missing_endpoint_labels} relationship row(s) are missing endpoint names. Run SQL 014 endpoint recovery, then re-resolve this job. The visual graph will keep unresolved endpoints separate until repaired.")

                goptions=["ALL"]+sorted(str(x) for x in gdf["resolution_status"].dropna().unique())
                gstatus=st.selectbox("Generic relationship status",goptions,key="generic_relationship_resolution_status")
                gview=gdf if gstatus=="ALL" else gdf[gdf["resolution_status"]==gstatus]
                gcols=[c for c in [
                    "created_at","natural_key","relationship_type",
                    "from_entity_type","from_name","from_source_key","resolved_from_entity_id","from_resolution_method",
                    "to_entity_type","to_name","to_source_key","resolved_to_entity_id","to_resolution_method",
                    "resolution_status","apply_status","canonical_relationship_id","existing_relationship_id",
                    "review_status","staged_record_id"
                ] if c in gview.columns]
                st.dataframe(gview[gcols],use_container_width=True,hide_index=True)

                # Visual relationship network preview. This is deliberately driven by
                # the currently filtered staged relationship set, not by invented data.
                st.markdown("### Relationship network preview")
                st.caption("Visual preview of the currently filtered graph edges. Limit is 60 edges for readability; use the table above for the complete set.")
                preview=gview.head(60)
                if not preview.empty:
                    def _dot_escape(v):
                        return str(v or "").replace("\\","\\\\").replace('"','\\"').replace("\n"," ")
                    dot=[
                        'digraph PCGraph {',
                        'rankdir=LR;',
                        'graph [bgcolor="transparent", pad="0.25", nodesep="0.35", ranksep="0.6"];',
                        'node [shape=box, style="rounded,filled", fillcolor="#111827", fontcolor="white", color="#4b5563", fontname="Arial", fontsize=10];',
                        'edge [color="#9ca3af", fontcolor="#d1d5db", fontname="Arial", fontsize=9];'
                    ]
                    seen=set()
                    for rownum,(_,gr) in enumerate(preview.iterrows(),start=1):
                        # Never collapse missing endpoints onto one generic Source/Target node.
                        # SQL 014 recovers labels for older staged research; until then, keep
                        # unresolved rows distinct and visibly marked rather than drawing giant self-loops.
                        natural=str(gr.get("natural_key") or "")
                        rel=str(gr.get("relationship_type") or "related to")
                        flabel=gr.get("from_name") or gr.get("resolved_from_entity_id") or gr.get("from_source_key")
                        tlabel=gr.get("to_name") or gr.get("resolved_to_entity_id") or gr.get("to_source_key")
                        if not flabel:
                            flabel=f"Unresolved source {rownum}"
                        if not tlabel:
                            tlabel=f"Unresolved target {rownum}"
                        fid=str(gr.get("resolved_from_entity_id") or gr.get("from_source_key") or f"unresolved-from-{rownum}-{natural}")
                        tid=str(gr.get("resolved_to_entity_id") or gr.get("to_source_key") or f"unresolved-to-{rownum}-{natural}")
                        fn="n"+hashlib.sha1(fid.encode("utf-8")).hexdigest()[:12]
                        tn="n"+hashlib.sha1(tid.encode("utf-8")).hexdigest()[:12]
                        if fn not in seen:
                            dot.append(f'{fn} [label="{_dot_escape(flabel)}"];')
                            seen.add(fn)
                        if tn not in seen:
                            dot.append(f'{tn} [label="{_dot_escape(tlabel)}"];')
                            seen.add(tn)
                        dot.append(f'{fn} -> {tn} [label="{_dot_escape(rel)}"];')
                    dot.append('}')
                    st.graphviz_chart("\n".join(dot),use_container_width=True)
                else:
                    st.info("No relationship edges are available for the current filter.")

                gapplied=gdf.get("apply_status",pd.Series(["PENDING"]*len(gdf))).fillna("PENDING")
                gpending=int(((gstatuses=="READY") & (~gapplied.isin(["APPLIED","SKIPPED_EXISTS"]))).sum())
                gg1,gg2,gg3=st.columns(3)
                gg1.metric("READY awaiting apply",gpending)
                gg2.metric("Applied",int((gapplied=="APPLIED").sum()))
                gg3.metric("Canonical graph relationships",count_rows(sb,"pc_relationships"))

                gconfirm=st.checkbox(
                    "I confirm: promote all currently READY generic relationships to canonical pc_relationships",
                    key="confirm_ready_generic_relationship_apply"
                )
                if st.button(
                    f"Apply READY graph relationships ({gpending})",
                    type="primary",
                    disabled=(not gconfirm or gpending==0),
                    key="apply_ready_generic_relationships"
                ):
                    try:
                        with st.spinner("Revalidating relationship endpoints and writing canonical graph edges..."):
                            result=_apply_ready_generic_relationships(sb)
                        st.success(
                            f"Graph apply complete — {result.get('applied',0)} applied, "
                            f"{result.get('already_exists',0)} already existed, {result.get('blocked',0)} blocked, "
                            f"{result.get('errors',0)} errors."
                        )
                        st.rerun()
                    except Exception as exc:
                        st.exception(exc)
            else:
                st.warning("No SQL 013 relationship-resolution rows are visible yet. Showing raw staged relationship proposals so the graph does not disappear.")
                if staged_graph_preview:
                    sdf=pd.DataFrame(staged_graph_preview)
                    st.metric("Staged graph edges",len(sdf))
                    st.dataframe(sdf[[c for c in ["created_at","natural_key","relationship_type","from_name","to_name","review_status"] if c in sdf.columns]],use_container_width=True,hide_index=True)
                    st.markdown("### Relationship network preview")
                    st.caption("Fallback preview built directly from staged pc_relationships proposals. These edges are not canonical until resolved and applied.")
                    preview=sdf.head(60)
                    def _dot_escape(v):
                        return str(v or "").replace("\\","\\\\").replace('"','\\"').replace("\n"," ")
                    dot=[
                        'digraph PCGraph {',
                        'rankdir=LR;',
                        'graph [bgcolor="transparent", pad="0.25", nodesep="0.35", ranksep="0.6"];',
                        'node [shape=box, style="rounded,filled", fillcolor="#111827", fontcolor="white", color="#4b5563", fontname="Arial", fontsize=10];',
                        'edge [color="#9ca3af", fontcolor="#d1d5db", fontname="Arial", fontsize=9];'
                    ]
                    seen=set()
                    for _,gr in preview.iterrows():
                        fid=str(gr.get("from_source_key") or gr.get("from_name") or "source")
                        tid=str(gr.get("to_source_key") or gr.get("to_name") or "target")
                        flabel=str(gr.get("from_name") or "Source")
                        tlabel=str(gr.get("to_name") or "Target")
                        rel=str(gr.get("relationship_type") or "related to")
                        fn="n"+hashlib.sha1(fid.encode("utf-8")).hexdigest()[:12]
                        tn="n"+hashlib.sha1(tid.encode("utf-8")).hexdigest()[:12]
                        if fn not in seen:
                            dot.append(f'{fn} [label="{_dot_escape(flabel)}"];')
                            seen.add(fn)
                        if tn not in seen:
                            dot.append(f'{tn} [label="{_dot_escape(tlabel)}"];')
                            seen.add(tn)
                        dot.append(f'{fn} -> {tn} [label="{_dot_escape(rel)}"];')
                    dot.append('}')
                    try:
                        st.graphviz_chart("\n".join(dot),use_container_width=True)
                    except Exception as exc:
                        st.error(f"Graph rendering failed: {exc}")
                        st.code("\n".join(dot),language="dot")
                else:
                    st.info("No staged pc_relationships proposals are present, so there are no graph edges to draw yet.")

            try:
                gjobs=(sb.table("pc_ingestion_jobs").select("ingestion_job_id,title,status,created_at,stats").order("created_at",desc=True).limit(100).execute().data or [])
            except Exception:
                gjobs=[]
            if gjobs:
                glabels=[f"{j.get('title') or 'Untitled'} | {j.get('ingestion_job_id')}" for j in gjobs]
                gchosen=st.selectbox("Generic relationship ingestion job",glabels,key="generic_relationship_job")
                gjob=gjobs[glabels.index(gchosen)]
                if st.button("Prepare + resolve generic relationships in this job",key="resolve_generic_relationship_job"):
                    try:
                        result=_process_generic_relationship_backlog(sb,gjob["ingestion_job_id"])
                        st.success(f"Generic relationship resolution complete: {result}")
                        st.rerun()
                    except Exception as exc:
                        st.exception(exc)

            c1,c2=st.columns(2)
            if c1.button("Resolve all pending event-link relationships",type="primary",key="resolve_relationship_backlog"):
                try:
                    result=_process_relationship_backlog(sb)
                    st.success(f"Relationship resolution complete: {result}")
                    st.rerun()
                except Exception as exc:
                    st.exception(exc)

            try:
                rel_jobs=(sb.table("pc_ingestion_jobs").select("ingestion_job_id,title,status,created_at").order("created_at",desc=True).limit(100).execute().data or [])
            except Exception:
                rel_jobs=[]
            if rel_jobs:
                labels=[f"{j.get('title') or 'Untitled'} | {j.get('ingestion_job_id')}" for j in rel_jobs]
                chosen=st.selectbox("Relationship ingestion job",labels,key="relationship_resolution_job")
                job=rel_jobs[labels.index(chosen)]
                if c2.button("Resolve selected job relationships",key="resolve_selected_relationship_job"):
                    try:
                        result=_process_relationship_backlog(sb,job["ingestion_job_id"])
                        st.success(f"Relationship resolution complete: {result}")
                        st.rerun()
                    except Exception as exc:
                        st.exception(exc)

elif page=="Review Queue":
    title(
        "Review & apply queue",
        "Bulk-review safe records; route ambiguous records to manual review. JSON is available only when you need to edit it."
    )

    _show_action_feedback()
    if st.session_state.get("_pc_action_feedback"):
        if st.button("Dismiss last operation message", key="dismiss_pc_feedback"):
            st.session_state.pop("_pc_action_feedback", None)
            st.rerun()

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
                "staged_record_id,ingestion_job_id,target_entity_type,target_table,natural_key,source_record_key,action,confidence,validation_status,review_status,resolution_status,resolved_entity_id,resolution_method,resolution_confidence,candidate_count,payload,current_record,source_id,created_at",
                500,
                {"review_status":"pending"},
                "created_at"
            )

            if not pending:
                st.success("No pending records.")
            else:
                st.markdown("### Automated validation")
                st.caption(
                    "Safe = confidence ≥ 0.90, source-backed, valid FKs, metadata-resolved identity, no unexpected duplicate, and a configured apply key. "
                    "NEW entity/asset records receive canonical IDs in staging before apply; MATCHED records reuse the resolved canonical ID."
                )

                # SQL 016 preparation is job-scoped and mutates staging only. It resolves
                # identities, reuses MATCHED IDs, and assigns deterministic IDs to NEW rows.
                pending_jobs={}
                for _r in pending:
                    _jid=_r.get("ingestion_job_id")
                    if _jid:
                        pending_jobs.setdefault(str(_jid), str(_jid))
                if pending_jobs:
                    try:
                        _jobs=(sb.table("pc_ingestion_jobs").select("ingestion_job_id,title,created_at")
                               .in_("ingestion_job_id",list(pending_jobs.keys())).execute().data or [])
                        _job_by_id={str(j.get("ingestion_job_id")):j for j in _jobs}
                    except Exception:
                        _job_by_id={}
                    _job_ids=list(pending_jobs.keys())
                    _prep_choice=st.selectbox(
                        "Prepare staged entity candidates for ingestion job",
                        _job_ids,
                        format_func=lambda jid: f"{(_job_by_id.get(jid) or {}).get('title') or 'Ingestion job'} | {jid}",
                        key="review_prepare_candidate_job"
                    )
                    if st.button("Prepare canonical IDs + resolve candidates",key="review_prepare_candidates"):
                        try:
                            _prep_result=_prepare_canonical_candidates(sb,_prep_choice)
                            st.success(f"Candidate preparation complete: {_prep_result}")
                            st.rerun()
                        except Exception as exc:
                            st.exception(exc)

                    # Semantic completion is analyst-controlled. Suggestions are stage-only
                    # and no classifier is written unless the analyst confirms it.
                    _semantic_gaps=_semantic_gap_rows(pending,_prep_choice)
                    if _semantic_gaps:
                        st.markdown("### Semantic completion")
                        st.caption(
                            "These staged identity records have a canonical ID path but are missing a required semantic classifier. "
                            "Review the suggested values, edit where needed, then save to staging and re-run candidate resolution."
                        )
                        _sem_df=pd.DataFrame(_semantic_gaps)
                        _sem_edit=st.data_editor(
                            _sem_df[["Apply?","Record","Table","Name","Required field","Suggested value","Value","_id"]],
                            use_container_width=True,
                            hide_index=True,
                            disabled=["Record","Table","Name","Required field","Suggested value","_id"],
                            column_config={"_id":None},
                            key=f"semantic_completion_{_prep_choice}",
                        )
                        _sc1,_sc2=st.columns([1,2])
                        if _sc1.button("Save semantic completion + re-resolve",key=f"save_semantic_{_prep_choice}",type="primary"):
                            try:
                                _pending_by_id={str(r.get("staged_record_id")):r for r in pending}
                                _saved=_save_semantic_completions(sb,_sem_edit.to_dict("records"),_pending_by_id)
                                _prep_result=_prepare_canonical_candidates(sb,_prep_choice)
                                st.success(f"Semantic completion saved: {_saved}. Candidate resolution: {_prep_result}")
                                st.rerun()
                            except Exception as exc:
                                st.exception(exc)
                        _sc2.caption(
                            "Suggestions are not auto-applied. Leave Apply? unchecked for anything that should be remapped or researched further."
                        )

                validated=[]
                with st.spinner("Validating staged records..."):
                    for r in pending:
                        v=validate_staged_for_bulk(sb,r)
                        validated.append({
                            "Apply?": bool(v["safe"]),
                            "Record": r.get("natural_key"),
                            "Table": r.get("target_table"),
                            "Resolution": r.get("resolution_status") or "UNRESOLVED",
                            "Resolved ID": r.get("resolved_entity_id"),
                            "Match": r.get("resolution_method"),
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

                # Streamlit data_editor persists its own widget state. The previous
                # "Select all safe" button only displayed an info message, so it could
                # not restore checkboxes after a user changed them. Rotate the editor
                # key when a bulk selection command is requested so the new defaults
                # are actually applied.
                if "_bulk_review_editor_version" not in st.session_state:
                    st.session_state["_bulk_review_editor_version"] = 0
                if "_bulk_review_selection_mode" not in st.session_state:
                    st.session_state["_bulk_review_selection_mode"] = "safe"

                sel1,sel2,_sel_spacer=st.columns([1,1,3])
                if sel1.button("Select all safe", key="bulk_select_all_safe"):
                    st.session_state["_bulk_review_selection_mode"] = "safe"
                    st.session_state["_bulk_review_editor_version"] += 1
                    st.rerun()
                if sel2.button("Clear selection", key="bulk_clear_selection"):
                    st.session_state["_bulk_review_selection_mode"] = "none"
                    st.session_state["_bulk_review_editor_version"] += 1
                    st.rerun()

                edit_df=pd.DataFrame(validated)
                mode=st.session_state.get("_bulk_review_selection_mode","safe")
                if mode == "none":
                    edit_df["Apply?"] = False
                else:
                    edit_df["Apply?"] = edit_df["_safe"].astype(bool)

                visible_cols=["Apply?","Record","Table","Resolution","Resolved ID","Match","Confidence","Sources","Schema","FKs","Duplicate","Parent","Risk"]
                editor_key=f"bulk_review_editor_{st.session_state['_bulk_review_editor_version']}"

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
                    key=editor_key
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

                c1,c2=st.columns(2)

                if c1.button("Approve selected safe",type="primary",disabled=not selected):
                    approved=0
                    skipped=0
                    safe_selected=[x for x in selected if x["_safe"]]
                    total=max(1,len(safe_selected))
                    with st.status("Approving selected records...",expanded=True) as status:
                        progress=st.progress(0.0,text=f"0/{total} approved")
                        for idx,x in enumerate(selected, start=1):
                            if not x["_safe"]:
                                skipped+=1
                                continue
                            st.write(f"Approving: {x['Record']}")
                            sb.table("pc_staged_records").update({
                                "review_status":"approved",
                                "validation_status":"validated"
                            }).eq("staged_record_id",x["_id"]).execute()
                            approved+=1
                            progress.progress(
                                approved/total,
                                text=f"{approved}/{total} approved"
                            )
                        status.update(
                            label=f"Approval complete — {approved} approved, {skipped} skipped",
                            state="complete",
                            expanded=False
                        )
                    _set_action_feedback(
                        "success",
                        f"Approval complete — {approved} record(s) approved; {skipped} skipped.",
                        ["Approved records are now available under the 'Approved — apply' tab."]
                    )
                    st.rerun()

                if c2.button("Approve + apply selected safe",disabled=not selected):
                    applied=0
                    failures=[]
                    safe_selected=[x for x in selected if x["_safe"]]
                    total=max(1,len(safe_selected))
                    with st.status("Approving and applying selected records...",expanded=True) as status:
                        progress=st.progress(0.0,text=f"0/{total} applied")
                        for idx,x in enumerate(safe_selected, start=1):
                            row=x["_row"]
                            st.write(f"{idx}/{total}: {row.get('natural_key')}")
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
                            progress.progress(
                                idx/total,
                                text=f"{idx}/{total} processed · {applied} applied"
                            )
                        if failures:
                            status.update(
                                label=f"Completed with warnings — {applied} applied, {len(failures)} failed",
                                state="error",
                                expanded=True
                            )
                        else:
                            status.update(
                                label=f"Complete — {applied} record(s) applied",
                                state="complete",
                                expanded=False
                            )
                    if failures:
                        _set_action_feedback(
                            "warning",
                            f"Bulk operation finished — {applied} applied, {len(failures)} failed.",
                            failures
                        )
                    else:
                        _set_action_feedback(
                            "success",
                            f"Bulk operation complete — {applied} record(s) approved and applied."
                        )
                    st.rerun()

                with st.expander("Bulk policy"):
                    st.code(
                        "confidence >= 0.90\n"
                        "source-backed provenance >= 1\n"
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
                "staged_record_id,ingestion_job_id,target_entity_type,target_table,natural_key,source_record_key,action,confidence,validation_status,review_status,resolution_status,resolved_entity_id,resolution_method,resolution_confidence,candidate_count,payload,current_record,source_id,created_at",
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
                    with st.spinner("Approving record..."):
                        update={"review_status":"approved","validation_status":"reviewed"}
                        if edited_payload is not None:
                            update["payload"]=edited_payload
                        sb.table("pc_staged_records").update(update).eq(
                            "staged_record_id",row["staged_record_id"]
                        ).execute()
                    _set_action_feedback("success","Record approved and moved to 'Approved — apply'.")
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
                "staged_record_id,ingestion_job_id,target_entity_type,target_table,natural_key,source_record_key,action,confidence,validation_status,review_status,resolution_status,resolved_entity_id,resolution_method,resolution_confidence,candidate_count,payload,current_record,source_id,created_at",
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
                    safe_selected=[x for x in selected if x["_safe"]]
                    applied=0
                    failed=[]
                    total=max(1,len(safe_selected))
                    with st.status("Applying approved records to canonical tables...",expanded=True) as status:
                        progress=st.progress(0.0,text=f"0/{total} applied")
                        for idx,x in enumerate(safe_selected,start=1):
                            name=x["_row"].get("natural_key")
                            table=x["_row"].get("target_table")
                            st.write(f"{idx}/{total}: {name} → {table}")
                            try:
                                apply_staged_record(sb,x["_row"],x["_row"].get("payload") or {})
                                applied+=1
                            except Exception as exc:
                                failed.append(f"{name}: {exc}")
                            progress.progress(
                                idx/total,
                                text=f"{idx}/{total} processed · {applied} applied"
                            )
                        if failed:
                            status.update(
                                label=f"Apply finished with warnings — {applied} applied, {len(failed)} failed",
                                state="error",
                                expanded=True
                            )
                        else:
                            status.update(
                                label=f"Apply complete — {applied} record(s) written",
                                state="complete",
                                expanded=False
                            )
                    if failed:
                        _set_action_feedback(
                            "warning",
                            f"Apply finished — {applied} written, {len(failed)} failed.",
                            failed
                        )
                    else:
                        _set_action_feedback(
                            "success",
                            f"Apply complete — {applied} record(s) written to canonical tables and moved to History."
                        )
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
                            with st.status("Applying record...",expanded=True) as status:
                                st.write("Validating payload...")
                                st.write(f"Writing to {row.get('target_table')}...")
                                apply_staged_record(sb,row,edited_payload)
                                status.update(
                                    label="Canonical write complete",
                                    state="complete",
                                    expanded=False
                                )
                            _set_action_feedback(
                                "success",
                                f"Record applied successfully to {row.get('target_table')} and moved to History."
                            )
                            st.rerun()
                        except Exception as exc:
                            _set_action_feedback(
                                "error",
                                "Apply failed. The record remains approved and can be retried.",
                                [str(exc)]
                            )
                            st.rerun()

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
                st.caption(f"{len(history):,} completed review record(s)")
                _history_df=pd.DataFrame(history[:500])
                _history_widget=st.dataframe(
                    _history_df,
                    use_container_width=True,
                    hide_index=True,
                    height=min(520, 60 + 34 * max(1, len(_history_df))),
                )
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
