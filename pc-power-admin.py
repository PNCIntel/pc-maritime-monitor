from __future__ import annotations
from datetime import datetime, date, timedelta
from pathlib import Path
import os, sys, json, uuid, hashlib, re, io, zipfile, mimetypes, urllib.parse, urllib.request, urllib.error, html
import uuid
from datetime import date, datetime
from decimal import Decimal
import pandas as pd
import xml.etree.ElementTree as ET
import streamlit as st

LOADER_BUILD = "501-sanctions-bulk-load-dedupe-fix-2026-09-19"


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

# v11: FK-safe direct-table staging for transaction participants
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
    "Review Queue": "Review Queue",
    "Canonical Exceptions": "Canonical Review",
    "AI Research": "AI Research Workflow",
    "Content Intake": "Universal Content Intake",
    "Sanctions Bulk Load": "Sanctions Bulk Load",
    "Port Enrichment": "Port Enrichment",
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
    "pc_transaction_participants": ["participant_id","transaction_id","role"],
    "pc_energy_assets": ["asset_id"],
    "pc_industrial_assets": ["asset_id"],
    "pc_logistics_facilities": ["asset_id"],
    "pc_market_instruments": ["market_instrument_id","name"],
    "pc_market_exposure_links": ["target_type","target_id","market_instrument_id","exposure_type"],
    "pc_trade_flows": ["trade_flow_id"],
    "pc_supply_series": ["supply_series_id"],
    "pc_transport_routes": ["route_id","route_name","mode"],
    "pc_chokepoints": ["chokepoint_id","name"],

    # Port / terminal / berth layer
    "pc_port_capabilities": ["port_asset_id"],
    "pc_port_metrics": ["port_metric_id","port_asset_id","metric_name"],
    "pc_terminal_details": ["asset_id"],
    "pc_berth_details": ["asset_id"],
    "pc_port_calls": ["port_call_id","mobile_asset_id","port_asset_id"],

    # Transport-service layer
    "pc_transport_services": ["transport_service_id","service_name","mode"],
    "pc_transport_service_aliases": ["transport_service_id","alias","alias_type"],
    "pc_transport_service_operators": ["transport_service_id","entity_id","operator_role"],
    "pc_transport_service_stops": ["transport_service_id","direction","sequence_no","asset_id"],
    "pc_transport_service_schedules": ["service_schedule_id","transport_service_id"],
    "pc_transport_service_transit_times": ["transport_service_id","direction","from_asset_id","to_asset_id"],
    "pc_transport_service_mobile_assets": ["transport_service_id","mobile_asset_id","service_role"],
    "pc_transport_service_network_links": ["transport_service_id","asset_id","relationship_type"],
    "pc_transport_service_connections": ["from_transport_service_id","to_transport_service_id","connection_type"],
    "pc_transport_service_changes": ["service_change_id","transport_service_id","change_type"],
    "pc_transport_service_sources": ["transport_service_id","source_url"],

    # Universal fact/domain extensions
    "pc_project_details": ["asset_id"],
    "pc_financing_facilities": ["financing_id","financing_type"],
    "pc_financing_participants": ["financing_id","role"],
    "pc_financing_links": ["financing_id","linked_type","linked_id","relationship_type"],
    "pc_contracts": ["contract_id","contract_type"],
    "pc_contract_participants": ["contract_id","role"],
    "pc_contract_links": ["contract_id","linked_type","linked_id","relationship_type"],
    "pc_vessel_designs": ["vessel_design_id"],
    "pc_shipbuilding_orders": ["shipbuilding_order_id"],
    "pc_shipbuilding_order_units": ["shipbuilding_order_unit_id","shipbuilding_order_id","unit_number"],
}

FK_RULES = {
    "pc_event_links": [
        ("event_id","pc_events","event_id"),
    ],
    "pc_transaction_participants": [
        ("transaction_id","pc_transactions","transaction_id"),
        ("entity_id","pc_entities","entity_id"),
        ("role","pc_meta_transaction_participant_roles","role"),
        ("source_id","pc_sources","source_id"),
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

    "pc_port_capabilities": [
        ("port_asset_id","pc_assets","asset_id"),
        ("source_id","pc_sources","source_id"),
    ],
    "pc_port_metrics": [
        ("port_asset_id","pc_assets","asset_id"),
        ("source_id","pc_sources","source_id"),
        ("observation_id","pc_observations","observation_id"),
    ],
    "pc_terminal_details": [
        ("asset_id","pc_assets","asset_id"),
        ("parent_port_asset_id","pc_assets","asset_id"),
        ("owner_entity_id","pc_entities","entity_id"),
        ("operator_entity_id","pc_entities","entity_id"),
        ("concession_holder_entity_id","pc_entities","entity_id"),
        ("source_id","pc_sources","source_id"),
    ],
    "pc_berth_details": [
        ("asset_id","pc_assets","asset_id"),
        ("terminal_asset_id","pc_terminal_details","asset_id"),
        ("source_id","pc_sources","source_id"),
    ],
    "pc_port_calls": [
        ("mobile_asset_id","pc_mobile_assets","mobile_asset_id"),
        ("port_asset_id","pc_assets","asset_id"),
        ("terminal_asset_id","pc_terminal_details","asset_id"),
        ("berth_asset_id","pc_berth_details","asset_id"),
        ("source_id","pc_sources","source_id"),
    ],
    "pc_project_details": [
        ("asset_id","pc_assets","asset_id"),
        ("sponsor_entity_id","pc_entities","entity_id"),
        ("developer_entity_id","pc_entities","entity_id"),
        ("delivery_entity_id","pc_entities","entity_id"),
        ("source_id","pc_sources","source_id"),
    ],
    "pc_financing_participants": [
        ("financing_id","pc_financing_facilities","financing_id"),
        ("entity_id","pc_entities","entity_id"),
        ("source_id","pc_sources","source_id"),
    ],
    "pc_financing_links": [
        ("financing_id","pc_financing_facilities","financing_id"),
        ("source_id","pc_sources","source_id"),
    ],
    "pc_contract_participants": [
        ("contract_id","pc_contracts","contract_id"),
        ("entity_id","pc_entities","entity_id"),
        ("source_id","pc_sources","source_id"),
    ],
    "pc_contract_links": [
        ("contract_id","pc_contracts","contract_id"),
        ("source_id","pc_sources","source_id"),
    ],
    "pc_vessel_designs": [
        ("designer_entity_id","pc_entities","entity_id"),
        ("builder_entity_id","pc_entities","entity_id"),
        ("source_id","pc_sources","source_id"),
    ],
    "pc_shipbuilding_orders": [
        ("contract_id","pc_contracts","contract_id"),
        ("buyer_entity_id","pc_entities","entity_id"),
        ("builder_entity_id","pc_entities","entity_id"),
        ("shipyard_asset_id","pc_assets","asset_id"),
        ("vessel_design_id","pc_vessel_designs","vessel_design_id"),
        ("source_id","pc_sources","source_id"),
    ],
    "pc_shipbuilding_order_units": [
        ("shipbuilding_order_id","pc_shipbuilding_orders","shipbuilding_order_id"),
        ("mobile_asset_id","pc_mobile_assets","mobile_asset_id"),
        ("vessel_design_id","pc_vessel_designs","vessel_design_id"),
        ("source_id","pc_sources","source_id"),
    ],
    "pc_transport_services": [
        ("origin_asset_id","pc_assets","asset_id"),
        ("destination_asset_id","pc_assets","asset_id"),
        ("primary_operator_entity_id","pc_entities","entity_id"),
        ("alliance_entity_id","pc_entities","entity_id"),
        ("source_id","pc_sources","source_id"),
    ],
    "pc_transport_service_aliases": [
        ("transport_service_id","pc_transport_services","transport_service_id"),
        ("operator_entity_id","pc_entities","entity_id"),
        ("source_id","pc_sources","source_id"),
    ],
    "pc_transport_service_operators": [
        ("transport_service_id","pc_transport_services","transport_service_id"),
        ("entity_id","pc_entities","entity_id"),
        ("source_id","pc_sources","source_id"),
    ],
    "pc_transport_service_stops": [
        ("transport_service_id","pc_transport_services","transport_service_id"),
        ("asset_id","pc_assets","asset_id"),
        ("terminal_asset_id","pc_assets","asset_id"),
        ("source_id","pc_sources","source_id"),
    ],
    "pc_transport_service_schedules": [
        ("transport_service_id","pc_transport_services","transport_service_id"),
        ("source_id","pc_sources","source_id"),
    ],
    "pc_transport_service_transit_times": [
        ("transport_service_id","pc_transport_services","transport_service_id"),
        ("from_asset_id","pc_assets","asset_id"),
        ("to_asset_id","pc_assets","asset_id"),
        ("source_id","pc_sources","source_id"),
    ],
    "pc_transport_service_mobile_assets": [
        ("transport_service_id","pc_transport_services","transport_service_id"),
        ("mobile_asset_id","pc_mobile_assets","mobile_asset_id"),
        ("source_id","pc_sources","source_id"),
    ],
    "pc_transport_service_network_links": [
        ("transport_service_id","pc_transport_services","transport_service_id"),
        ("asset_id","pc_assets","asset_id"),
        ("source_id","pc_sources","source_id"),
    ],
    "pc_transport_service_connections": [
        ("from_transport_service_id","pc_transport_services","transport_service_id"),
        ("to_transport_service_id","pc_transport_services","transport_service_id"),
        ("connection_asset_id","pc_assets","asset_id"),
        ("source_id","pc_sources","source_id"),
    ],
    "pc_transport_service_changes": [
        ("transport_service_id","pc_transport_services","transport_service_id"),
        ("event_id","pc_events","event_id"),
        ("source_id","pc_sources","source_id"),
    ],
    "pc_transport_service_sources": [
        ("transport_service_id","pc_transport_services","transport_service_id"),
        ("source_id","pc_sources","source_id"),
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

    # Corporate packages may link an event directly to its canonical transaction.
    # pc_event_links.linked_id is polymorphic, so validate the transaction endpoint here.
    if table=="pc_event_links" and str(payload.get("linked_type") or "").lower() in {"transaction","deal"}:
        value=payload.get("linked_id")
        if value not in (None,""):
            try:
                hit=(sb.table("pc_transactions").select("transaction_id").eq(
                    "transaction_id",value
                ).limit(1).execute().data or [])
                if not hit:
                    problems.append("linked_id→pc_transactions.transaction_id missing")
            except Exception:
                problems.append("linked_id transaction FK check failed")
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
    "pc_transaction_participants": ("participant_id","TXNP_",20),
    "pc_transport_routes": ("route_id","ROUTE_",20),
    "pc_chokepoints": ("chokepoint_id","CHOKE_",20),
    "pc_market_instruments": ("market_instrument_id","MKT_",20),
    "pc_trade_flows": ("trade_flow_id","FLOW_",20),
    "pc_supply_series": ("supply_series_id","SUPPLY_",20),
    "pc_observations": ("observation_id","OBS_",20),

    "pc_transport_services": ("transport_service_id","SERVICE_",20),
    "pc_financing_facilities": ("financing_id","FIN_",20),
    "pc_contracts": ("contract_id","CONTRACT_",20),
    "pc_vessel_designs": ("vessel_design_id","VDESIGN_",20),
    "pc_shipbuilding_orders": ("shipbuilding_order_id","SHIPORDER_",20),
    "pc_shipbuilding_order_units": ("shipbuilding_order_unit_id","SHIPUNIT_",20),
}

UUID_ID_FIELDS = {
    "pc_port_metrics":"port_metric_id",
    "pc_port_calls":"port_call_id",
    "pc_transport_service_aliases":"service_alias_id",
    "pc_transport_service_operators":"service_operator_id",
    "pc_transport_service_stops":"service_stop_id",
    "pc_transport_service_schedules":"service_schedule_id",
    "pc_transport_service_transit_times":"service_transit_time_id",
    "pc_transport_service_mobile_assets":"service_mobile_asset_id",
    "pc_transport_service_network_links":"service_network_link_id",
    "pc_transport_service_connections":"service_connection_id",
    "pc_transport_service_changes":"service_change_id",
    "pc_transport_service_sources":"service_source_id",
    "pc_financing_participants":"financing_participant_id",
    "pc_financing_links":"financing_link_id",
    "pc_contract_participants":"contract_participant_id",
    "pc_contract_links":"contract_link_id",
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
        "pc_transaction_participants":["participant_id","transaction_id","entity_id","participant_name","role","ownership_percent","lead_participant","valid_from","valid_to","source_id"],
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
        "transaction_id","participant_id","route_id","chokepoint_id","market_instrument_id","trade_flow_id",
        "supply_series_id","observation_id","transport_service_id","financing_id","contract_id","vessel_design_id","shipbuilding_order_id","shipbuilding_order_unit_id","service_alias_id","service_operator_id","service_stop_id","service_schedule_id","service_transit_time_id","service_mobile_asset_id","service_network_link_id","service_connection_id","service_change_id","service_source_id","imo","mmsi","name","title","route_name","service_name","financing_name","contract_name","design_name"
    ):
        if payload.get(key):
            return str(payload[key])
    return f"{target_table}:{index}"

def _fill_staging_key(payload,target_table,natural_key):
    """Fill stable text or UUID primary keys for staged records when omitted."""
    payload=dict(payload or {})

    spec=ID_FIELDS.get(target_table)
    if spec:
        field,prefix,n=spec
        if not payload.get(field):
            digest=hashlib.sha256(f"{target_table}|{natural_key}".encode("utf-8")).hexdigest().upper()[:n]
            payload[field]=prefix+digest
        return payload

    uuid_field=UUID_ID_FIELDS.get(target_table)
    if uuid_field and not payload.get(uuid_field):
        payload[uuid_field]=str(uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"power-corridors|{target_table}|{natural_key}"
        ))
    return payload

def _parse_multitable_upload(upload):
    """Parse flat workbooks/CSVs plus loader-native JSON/JSONL packages.

    Loader-native records may use:
      {"target_table": "pc_entities", "natural_key": "...", "payload": {...}}
    They are grouped by target_table and the nested payload is preserved for the
    canonical V5 processor rather than flattened or remapped by the UI.
    """
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

    elif name.endswith((".jsonl",".ndjson")):
        records=[]
        for line_no,line in enumerate(raw.decode("utf-8-sig").splitlines(),1):
            line=line.strip()
            if not line:
                continue
            try:
                obj=json.loads(line)
            except Exception as exc:
                raise ValueError(f"Invalid JSONL on line {line_no}: {exc}") from exc
            if not isinstance(obj,dict):
                raise ValueError(f"JSONL line {line_no} must be an object")
            records.append(obj)
        df=pd.DataFrame(records)
        if "target_table" in df.columns:
            for table,g in df.groupby("target_table",dropna=False):
                sections[str(table or "records")]=g.drop(columns=["target_table"]).reset_index(drop=True)
        else:
            sections[Path(upload.name).stem]=df

    else:
        obj=json.loads(raw.decode("utf-8-sig"))
        if isinstance(obj,list):
            records=obj
        elif isinstance(obj,dict) and isinstance(obj.get("records"),list):
            records=obj.get("records")
        elif isinstance(obj,dict) and isinstance(obj.get("package"),list):
            records=obj.get("package")
        else:
            records=[obj]
        df=pd.DataFrame(records)
        if "target_table" in df.columns:
            for table,g in df.groupby("target_table",dropna=False):
                sections[str(table or "records")]=g.drop(columns=["target_table"]).reset_index(drop=True)
        else:
            sections[Path(upload.name).stem]=df

    return sections, hashlib.sha256(raw).hexdigest()


def _loader_native_section(df):
    """True when rows are already in pc_staged_records-style package shape."""
    if df is None or df.empty or "payload" not in df.columns:
        return False
    sample=None
    for v in df["payload"].tolist():
        if v is None or (isinstance(v,float) and pd.isna(v)):
            continue
        sample=v
        break
    if sample is None:
        return False
    parsed=_jsonish(sample)
    return isinstance(parsed,dict)


def _suggest_target_table(section,df):
    n=_norm_field(section)
    aliases={
        "companies":"pc_entities","entities":"pc_entities","organisations":"pc_entities","organizations":"pc_entities",
        "assets":"pc_assets","ports":"pc_assets","terminals":"pc_assets","infrastructure":"pc_assets",
        "vessels":"pc_mobile_assets","ships":"pc_mobile_assets","mobile_assets":"pc_mobile_assets",
        "relationships":"pc_relationships","relations":"pc_relationships",
        "events":"pc_events","incidents":"pc_events","event_links":"pc_event_links",
        "transactions":"pc_transactions","deals":"pc_transactions",
        "transaction_participants":"pc_transaction_participants","deal_participants":"pc_transaction_participants",
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
        "mobile_asset":("pc_mobile_assets","mobile_asset_id,name,asset_type,imo,mmsi,flag","name"),
        "event":("pc_events","event_id,title,event_type,start_date","title"),
        "transport_service":("pc_transport_services","transport_service_id,service_name,service_code,mode,service_type,status","service_name"),
    }
    if kind not in config:
        return []
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
st.sidebar.caption("Ingest → extract facts → resolve/link → review → apply")

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
    "pc_transaction_participants",
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
    "pc_terminal_details",
    "pc_berth_details",
    "pc_port_calls",
    "pc_transport_routes",
    "pc_chokepoints",
    "pc_macro_indicators",
    "pc_observations",

    # Transport services / routes
    "pc_transport_services",
    "pc_transport_service_aliases",
    "pc_transport_service_operators",
    "pc_transport_service_stops",
    "pc_transport_service_schedules",
    "pc_transport_service_transit_times",
    "pc_transport_service_mobile_assets",
    "pc_transport_service_network_links",
    "pc_transport_service_connections",
    "pc_transport_service_changes",
    "pc_transport_service_sources",

    # Universal content-derived domain records
    "pc_project_details",
    "pc_financing_facilities",
    "pc_financing_participants",
    "pc_financing_links",
    "pc_contracts",
    "pc_contract_participants",
    "pc_contract_links",
    "pc_vessel_designs",
    "pc_shipbuilding_orders",
    "pc_shipbuilding_order_units",
}

DIRECT_DOMAIN_TABLES = {
    "pc_port_capabilities",
    "pc_port_metrics",
    "pc_terminal_details",
    "pc_berth_details",
    "pc_port_calls",
    "pc_transport_services",
    "pc_transport_service_aliases",
    "pc_transport_service_operators",
    "pc_transport_service_stops",
    "pc_transport_service_schedules",
    "pc_transport_service_transit_times",
    "pc_transport_service_mobile_assets",
    "pc_transport_service_network_links",
    "pc_transport_service_connections",
    "pc_transport_service_changes",
    "pc_transport_service_sources",
    "pc_project_details",
    "pc_financing_facilities",
    "pc_financing_participants",
    "pc_financing_links",
    "pc_contracts",
    "pc_contract_participants",
    "pc_contract_links",
    "pc_vessel_designs",
    "pc_shipbuilding_orders",
    "pc_shipbuilding_order_units",
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
    "pc_transaction_participants": "participant_id",
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
    "pc_port_capabilities": "port_asset_id",
    "pc_terminal_details": "asset_id",
    "pc_berth_details": "asset_id",
    "pc_port_calls": "port_call_id",
    "pc_transport_routes": "route_id",
    "pc_chokepoints": "chokepoint_id",
    "pc_macro_indicators": "macro_indicator_id",
    "pc_observations": "observation_id",

    "pc_transport_services": "transport_service_id",
    "pc_transport_service_aliases": "transport_service_id,alias,alias_type",
    "pc_transport_service_operators": "service_operator_id",
    "pc_transport_service_stops": "transport_service_id,direction,sequence_no",
    "pc_transport_service_schedules": "service_schedule_id",
    "pc_transport_service_transit_times": "service_transit_time_id",
    "pc_transport_service_mobile_assets": "service_mobile_asset_id",
    "pc_transport_service_network_links": "service_network_link_id",
    "pc_transport_service_connections": "service_connection_id",
    "pc_transport_service_changes": "service_change_id",
    "pc_transport_service_sources": "transport_service_id,source_url",

    "pc_project_details": "asset_id",
    "pc_financing_facilities": "financing_id",
    "pc_financing_participants": "financing_participant_id",
    "pc_financing_links": "financing_link_id",
    "pc_contracts": "contract_id",
    "pc_contract_participants": "contract_participant_id",
    "pc_contract_links": "contract_link_id",
    "pc_vessel_designs": "vessel_design_id",
    "pc_shipbuilding_orders": "shipbuilding_order_id",
    "pc_shipbuilding_order_units": "shipbuilding_order_unit_id",
}

AI_CAMPAIGNS = {
    "Article / URL fact extraction": (
        "Research the supplied article(s) and extract all material structured facts: "
        "companies, assets, ownership, transactions, financing, contracts, projects, "
        "shipbuilding, transport services/routes, sanctions and operational events. "
        "Locate authoritative primary sources, preserve provenance and do not reduce "
        "the result to a news summary."
    ),
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


FACT_TYPES = {
    "entity_identity","asset_identity","mobile_asset_identity","relationship",
    "event","transaction","ownership_change","project","financing","contract",
    "shipbuilding_order","vessel_design","transport_service","service_change",
    "route","capacity","financial_metric","schedule","regulatory","sanctions",
    "security_incident","operational_status","source_reference","other"
}

UNIVERSAL_CONTENT_OUTPUT_CONTRACT = """
Return one JSON object with this shape:
{
  "facts": [
    {
      "fact_type": "one allowed fact type",
      "fact_key": "short stable key",
      "subject_type": "entity|asset|mobile_asset|service|project|contract|financing|other",
      "subject_name": "...",
      "subject_identifier": "... or null",
      "predicate": "atomic relationship or property",
      "object_type": "... or null",
      "object_name": "... or null",
      "object_identifier": "... or null",
      "value_text": "... or null",
      "value_numeric": null,
      "value_boolean": null,
      "unit": "... or null",
      "currency": "... or null",
      "effective_date": "YYYY-MM-DD or null",
      "start_date": "YYYY-MM-DD or null",
      "end_date": "YYYY-MM-DD or null",
      "location_text": "... or null",
      "country": "... or null",
      "evidence_text": "short source-supported evidence excerpt/paraphrase",
      "confidence": 0.0,
      "primary_source_url": "... or null",
      "metadata": {}
    }
  ],
  "records": [
    {
      "target_table": "one allowed P&C canonical/domain table",
      "natural_key": "stable key",
      "action": "REVIEW",
      "confidence": 0.0,
      "payload": {
        "...": "schema-supported fields only",
        "metadata": {
          "research_sources": [
            {"url": "...", "publisher": "...", "title": "..."}
          ]
        }
      }
    }
  ],
  "primary_sources": [
    {
      "url": "...",
      "title": "...",
      "publisher": "...",
      "relationship_type": "primary_supports_secondary",
      "confidence": 0.0
    }
  ],
  "conflicts": [],
  "notes": []
}

Allowed fact types:
""" + ", ".join(sorted(FACT_TYPES)) + """

Allowed target tables:
""" + ", ".join(sorted(AI_ALLOWED_TABLES)) + """

Rules:
1. Extract atomic facts from the supplied article/document, not merely a summary.
2. One article may create many records across entities, assets, mobile assets,
   events, transactions, projects, financing, contracts, shipbuilding and
   transport-service tables.
3. Reuse canonical IDs supplied in database context only when deterministic.
4. Do not invent IDs for unknown existing canonical records. The loader fills
   missing internal IDs deterministically during staging.
5. Every proposed record must preserve source provenance under
   metadata.research_sources. Include the input URL.
6. When the article cites an official/company/regulatory source, locate and
   return it under primary_sources when web research is enabled.
7. Distinguish the secondary article from the underlying canonical fact.
8. For transport services, create the service plus operators/stops/changes only
   when the article supports them. Ordered calls belong in
   pc_transport_service_stops.
9. For financing, separate the facility from participants and target links.
10. For shipbuilding, separate generic contract, vessel design, order and order
    units where supported.
11. Do not guess missing vessel IMO numbers, ownership, stakes, dates, values or
    route calls.
"""

def _normalize_content_url(value):
    """Normalize a URL for dedupe while preserving the retrievable destination."""
    s=str(value or "").strip()
    if not s:
        return None
    if not re.match(r"^https?://",s,re.I):
        s="https://"+s
    try:
        p=urllib.parse.urlsplit(s)
        if not p.netloc:
            return None
        q=urllib.parse.parse_qsl(p.query,keep_blank_values=True)
        drop_prefixes=("utm_","fbclid","gclid","mc_cid","mc_eid")
        q=[(k,v) for k,v in q if not any(k.lower().startswith(x) for x in drop_prefixes)]
        query=urllib.parse.urlencode(q,doseq=True)
        return urllib.parse.urlunsplit((
            p.scheme.lower(),
            p.netloc.lower(),
            p.path or "/",
            query,
            ""
        ))
    except Exception:
        return None

def _extract_urls_from_text(value):
    text=str(value or "")
    hits=re.findall(r'https?://[^\s<>"\'\]\)]+',text,re.I)
    out=[]
    seen=set()
    for u in hits:
        u=u.rstrip(".,;:!?")
        n=_normalize_content_url(u)
        if n and n not in seen:
            seen.add(n)
            out.append(u)
    return out

def _extract_urls_from_upload(upload):
    """Extract URL candidates from TXT/MD/CSV/XLSX/DOCX/PDF documents."""
    lname=upload.name.lower()
    raw=upload.getvalue()
    urls=[]

    if lname.endswith((".xlsx",".xls")):
        xf=pd.ExcelFile(io.BytesIO(raw))
        for sheet in xf.sheet_names:
            df=pd.read_excel(io.BytesIO(raw),sheet_name=sheet,dtype=object)
            for col in df.columns:
                for v in df[col].tolist():
                    urls.extend(_extract_urls_from_text(v))
    elif lname.endswith(".csv"):
        text=raw.decode("utf-8-sig",errors="replace")
        urls.extend(_extract_urls_from_text(text))
    else:
        text=_extract_document_text(upload)
        urls.extend(_extract_urls_from_text(text))

    dedup=[]
    seen=set()
    for u in urls:
        n=_normalize_content_url(u)
        if n and n not in seen:
            seen.add(n)
            dedup.append(u)
    return dedup

def _strip_html_to_text(raw_html):
    """Article-friendly HTML text extraction with an optional BeautifulSoup path."""
    try:
        from bs4 import BeautifulSoup
        soup=BeautifulSoup(raw_html,"html.parser")
        for tag in soup(["script","style","noscript","svg","nav","footer"]):
            tag.decompose()
        title=None
        if soup.title and soup.title.string:
            title=" ".join(soup.title.string.split())
        og=soup.find("meta",attrs={"property":"og:title"})
        if og and og.get("content"):
            title=str(og.get("content")).strip()
        site=soup.find("meta",attrs={"property":"og:site_name"})
        publisher=str(site.get("content")).strip() if site and site.get("content") else None
        pub=soup.find("meta",attrs={"property":"article:published_time"})
        published=str(pub.get("content")).strip() if pub and pub.get("content") else None
        text="\n".join(x.strip() for x in soup.stripped_strings if x.strip())
        return text,title,publisher,published
    except Exception:
        cleaned=re.sub(r"(?is)<(script|style|noscript|svg|nav|footer).*?>.*?</\1>"," ",raw_html)
        mt=re.search(r"(?is)<title[^>]*>(.*?)</title>",raw_html)
        title=html.unescape(re.sub(r"<[^>]+>"," ",mt.group(1))).strip() if mt else None
        cleaned=re.sub(r"(?s)<[^>]+>"," ",cleaned)
        cleaned=html.unescape(cleaned)
        cleaned=re.sub(r"[ \t\r\f\v]+"," ",cleaned)
        cleaned=re.sub(r"\n\s*\n+","\n",cleaned)
        return cleaned.strip(),title,None,None

def _fetch_content_url(url, timeout=30, max_bytes=6_000_000):
    """Fetch a public URL and return article/document text plus basic metadata."""
    req=urllib.request.Request(
        url,
        headers={
            "User-Agent":"PowerAndCorridorsResearch/1.0 (+https://www.powerncorridors.com)",
            "Accept":"text/html,application/xhtml+xml,application/pdf,text/plain;q=0.9,*/*;q=0.7",
        }
    )
    with urllib.request.urlopen(req,timeout=timeout) as resp:
        status=getattr(resp,"status",200)
        ctype=(resp.headers.get("Content-Type") or "").lower()
        final_url=resp.geturl()
        raw=resp.read(max_bytes+1)
        if len(raw)>max_bytes:
            raw=raw[:max_bytes]
        mime=ctype.split(";",1)[0].strip() or None

    if "pdf" in ctype or final_url.lower().endswith(".pdf"):
        text=_extract_pdf_text(raw)
        return {
            "url":final_url,"status":status,"mime_type":"application/pdf",
            "raw_text":None,"extracted_text":text,"title":Path(urllib.parse.urlsplit(final_url).path).name or None,
            "publisher":urllib.parse.urlsplit(final_url).netloc,"publication_date":None,
            "content_hash":hashlib.sha256(raw).hexdigest()
        }

    charset="utf-8"
    cm=re.search(r"charset=([A-Za-z0-9._-]+)",ctype)
    if cm:
        charset=cm.group(1)
    raw_text=raw.decode(charset,errors="replace")

    if "html" in ctype or "<html" in raw_text[:1000].lower():
        text,title,publisher,published=_strip_html_to_text(raw_text)
    else:
        text=raw_text
        title=Path(urllib.parse.urlsplit(final_url).path).name or None
        publisher=urllib.parse.urlsplit(final_url).netloc
        published=None

    pub_date=None
    if published:
        try:
            pub_date=str(pd.to_datetime(published,utc=True).date())
        except Exception:
            pub_date=None

    return {
        "url":final_url,"status":status,"mime_type":mime,
        "raw_text":raw_text[:250000],
        "extracted_text":text[:500000],
        "title":title,
        "publisher":publisher or urllib.parse.urlsplit(final_url).netloc,
        "publication_date":pub_date,
        "content_hash":hashlib.sha256(raw).hexdigest()
    }

def _create_content_batch(input_mode,batch_name=None,product_context=None,research_mode=None,item_count=0,metadata=None):
    payload={
        "input_mode":input_mode,
        "batch_name":batch_name or f"Content intake {pd.Timestamp.utcnow().strftime('%Y-%m-%d %H:%M')}",
        "product_context":product_context,
        "research_mode":research_mode,
        "status":"running",
        "item_count":int(item_count or 0),
        "started_at":pd.Timestamp.utcnow().isoformat(),
        "metadata":metadata or {},
    }
    return sb.table("pc_content_ingest_batches").insert(payload).execute().data[0]

def _upsert_content_url_item(batch_id,url,document_id=None,discovery_method="manual_url"):
    normalized=_normalize_content_url(url)
    if not normalized:
        raise ValueError(f"Invalid URL: {url}")
    existing=(sb.table("pc_content_ingest_items")
              .select("*").eq("normalized_url",normalized).limit(1).execute().data or [])
    base_patch={
        "content_batch_id":batch_id,
        "input_type":"url",
        "source_url":url,
        "normalized_url":normalized,
        "document_id":document_id,
        "discovery_method":discovery_method,
        "updated_at":pd.Timestamp.utcnow().isoformat(),
    }
    base_patch={k:v for k,v in base_patch.items() if v is not None}
    if existing:
        # Critical idempotency rule: re-adding the same URL must NOT reset a
        # completed item to pending. That was causing repeated extraction and
        # fact growth on every workflow click/reload.
        item_id=existing[0]["content_item_id"]
        sb.table("pc_content_ingest_items").update(base_patch).eq("content_item_id",item_id).execute()
        return {**existing[0],**base_patch}

    insert_patch={
        **base_patch,
        "fetch_status":"pending",
        "extraction_status":"pending",
        "resolution_status":"pending",
    }
    return sb.table("pc_content_ingest_items").insert(insert_patch).execute().data[0]

def _save_url_manifest_document(upload,urls):
    """Preserve an uploaded URL-list document in pc_documents when available."""
    if not _table_exists("pc_documents"):
        return None
    raw=upload.getvalue()
    sha=hashlib.sha256(raw).hexdigest()
    existing=(sb.table("pc_documents").select("document_id").eq("file_sha256",sha).limit(1).execute().data or [])
    payload={
        "title":Path(upload.name).stem,
        "document_type":"url_list",
        "file_name":upload.name,
        "file_sha256":sha,
        "mime_type":mimetypes.guess_type(upload.name)[0],
        "extracted_text":"\n".join(urls),
        "extraction_status":"completed",
        "metadata":{"url_count":len(urls),"ingested_via":"UNIVERSAL_CONTENT_INTAKE"}
    }
    if existing:
        doc_id=existing[0]["document_id"]
        sb.table("pc_documents").update(payload).eq("document_id",doc_id).execute()
        return doc_id
    return sb.table("pc_documents").insert(payload).execute().data[0]["document_id"]


def _fact_sig_norm(v):
    if v is None:
        return ""
    try:
        if pd.isna(v):
            return ""
    except Exception:
        pass
    if isinstance(v,(dict,list,tuple)):
        try:
            return json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(",",":"))
        except Exception:
            return str(v)
    s=str(v).strip().casefold()
    s=re.sub(r"\s+"," ",s)
    return s


def _fact_signature(f):
    """Stable semantic fact signature.

    Deliberately excludes confidence/evidence/primary-source URL so a second
    extraction of the same semantic fact enriches/reuses the original row
    instead of appending another fact.
    """
    keys=[
        "fact_type",
        "subject_type","subject_name","subject_identifier",
        "predicate",
        "object_type","object_name","object_identifier",
        "value_text","value_numeric","value_boolean",
        "unit","currency",
        "effective_date","start_date","end_date",
        "location_text","country",
    ]
    raw="|".join(_fact_sig_norm(f.get(k)) for k in keys)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _mark_duplicate_content_facts(limit=10000):
    """Mark repeated semantic facts as duplicates without deleting audit rows."""
    rows=(sb.table("pc_extracted_facts").select(
        "fact_id,content_item_id,fact_type,subject_type,subject_name,subject_identifier,"
        "predicate,object_type,object_name,object_identifier,value_text,value_numeric,"
        "value_boolean,unit,currency,effective_date,start_date,end_date,location_text,"
        "country,review_status,resolution_status,created_at"
    ).order("created_at",desc=False).limit(int(limit)).execute().data or [])

    seen={}
    duplicates=[]
    for r in rows:
        cid=str(r.get("content_item_id") or "")
        sig=_fact_signature(r)
        key=(cid,sig)
        if key not in seen:
            seen[key]=r.get("fact_id")
        else:
            duplicates.append((r.get("fact_id"),seen[key]))

    for fact_id,keep_id in duplicates:
        if not fact_id:
            continue
        current=(sb.table("pc_extracted_facts")
                 .select("metadata")
                 .eq("fact_id",fact_id)
                 .limit(1).execute().data or [])
        md=(current[0].get("metadata") if current else {}) or {}
        md.update({
            "audit_duplicate":True,
            "duplicate_of_fact_id":str(keep_id),
            "deduped_by":LOADER_BUILD
        })
        sb.table("pc_extracted_facts").update({
            "metadata":md
        }).eq("fact_id",fact_id).execute()

    try:
        _content_review_data.clear()
    except Exception:
        pass
    return {"scanned":len(rows),"duplicates_marked":len(duplicates),"unique_facts":len(rows)-len(duplicates)}


def _persist_extracted_facts(content_item_id,extraction_run_id,result,source_url,document_id=None):
    """Persist only new semantic facts for a content item.

    Re-extraction of the same article may return a different order or slightly
    different evidence/confidence. Existing semantic facts are reused/enriched
    rather than appended.
    """
    facts=(result or {}).get("facts") or []

    existing=(sb.table("pc_extracted_facts").select(
        "fact_id,content_item_id,fact_type,subject_type,subject_name,subject_identifier,"
        "predicate,object_type,object_name,object_identifier,value_text,value_numeric,"
        "value_boolean,unit,currency,effective_date,start_date,end_date,location_text,"
        "country,primary_source_url,verification_status,review_status,resolution_status,metadata"
    ).eq("content_item_id",content_item_id).limit(10000).execute().data or [])

    existing_by_sig={}
    for r in existing:
        md=r.get("metadata") if isinstance(r.get("metadata"),dict) else {}
        if bool((md or {}).get("audit_duplicate")):
            continue
        existing_by_sig.setdefault(_fact_signature(r),r)

    rows=[]
    reused=[]
    for idx,f in enumerate(facts):
        if not isinstance(f,dict) or not f.get("predicate"):
            continue

        fact_type=str(f.get("fact_type") or "other").strip()
        if fact_type not in FACT_TYPES:
            fact_type="other"
        f=dict(f)
        f["fact_type"]=fact_type
        sig=_fact_signature(f)

        try:
            conf=float(f.get("confidence") if f.get("confidence") is not None else 0.70)
        except Exception:
            conf=0.70
        conf=max(0.0,min(1.0,conf))
        primary=f.get("primary_source_url")

        if sig in existing_by_sig:
            old=existing_by_sig[sig]
            patch={}
            # Enrich the retained fact when a later pass finds better sourcing.
            if primary and not old.get("primary_source_url"):
                patch["primary_source_url"]=primary
                patch["verification_status"]="primary_source_supported"
            if patch:
                sb.table("pc_extracted_facts").update(patch).eq("fact_id",old["fact_id"]).execute()
            reused.append(old)
            continue

        row={
            "extraction_run_id":extraction_run_id,
            "content_item_id":content_item_id,
            "document_id":document_id,
            "fact_type":fact_type,
            "fact_key":f.get("fact_key") or f"{fact_type}:{sig[:16]}",
            "subject_type":f.get("subject_type"),
            "subject_name":f.get("subject_name"),
            "subject_identifier":f.get("subject_identifier"),
            "predicate":str(f.get("predicate")),
            "object_type":f.get("object_type"),
            "object_name":f.get("object_name"),
            "object_identifier":f.get("object_identifier"),
            "value_text":f.get("value_text"),
            "value_numeric":f.get("value_numeric"),
            "value_boolean":f.get("value_boolean"),
            "unit":f.get("unit"),
            "currency":f.get("currency"),
            "effective_date":f.get("effective_date"),
            "start_date":f.get("start_date"),
            "end_date":f.get("end_date"),
            "location_text":f.get("location_text"),
            "country":f.get("country"),
            "evidence_text":f.get("evidence_text"),
            "source_url":source_url,
            "primary_source_url":primary,
            "confidence":conf,
            "verification_status":"primary_source_supported" if primary else "secondary_source",
            "review_status":"pending",
            "resolution_status":"unresolved",
            "metadata":{
                **(f.get("metadata") if isinstance(f.get("metadata"),dict) else {}),
                "semantic_fact_signature":sig,
            },
        }
        row={k:v for k,v in row.items() if v is not None}
        rows.append(row)
        existing_by_sig[sig]=row

    inserted=[]
    for i in range(0,len(rows),100):
        inserted.extend(sb.table("pc_extracted_facts").insert(rows[i:i+100]).execute().data or [])

    # Return retained + newly inserted facts so callers have the true active set
    # from this extraction without creating duplicates.
    return inserted + reused

def _prepare_universal_records(result,input_url,publisher=None,title=None):
    """Attach source provenance and stable IDs to canonical/domain proposals."""
    result=dict(result or {})
    records=[]
    for rec in result.get("records") or []:
        if not isinstance(rec,dict):
            continue
        table=str(rec.get("target_table") or "")
        payload=rec.get("payload") if isinstance(rec.get("payload"),dict) else {}
        if table not in AI_ALLOWED_TABLES:
            continue
        meta=payload.get("metadata") if isinstance(payload.get("metadata"),dict) else {}
        sources=meta.get("research_sources") if isinstance(meta.get("research_sources"),list) else []
        if not any((isinstance(x,str) and x==input_url) or (isinstance(x,dict) and x.get("url")==input_url) for x in sources):
            sources.insert(0,{
                "url":input_url,
                "publisher":publisher,
                "title":title,
                "source_role":"input_article"
            })
        meta["research_sources"]=sources
        meta.setdefault("ingested_via","UNIVERSAL_CONTENT_INTAKE")
        payload["metadata"]=meta
        if "source_url" not in payload:
            payload["source_url"]=input_url
        nk=str(rec.get("natural_key") or _record_key(payload,""))
        payload=_fill_staging_key(payload,table,nk)
        rec=dict(rec)
        rec["payload"]=payload
        rec["natural_key"]=nk
        records.append(rec)
    result["records"]=records
    return result

def _persist_primary_source_relationships(source_item_id,primary_sources,batch_id):
    created=0
    for p in primary_sources or []:
        if not isinstance(p,dict) or not p.get("url"):
            continue
        try:
            related=_upsert_content_url_item(
                batch_id,p["url"],None,"ai_primary_source_discovery"
            )
            sb.table("pc_content_ingest_items").update({
                "title":p.get("title"),
                "publisher":p.get("publisher"),
                "primary_source_candidate":True,
                "updated_at":pd.Timestamp.utcnow().isoformat()
            }).eq("content_item_id",related["content_item_id"]).execute()
            sb.table("pc_content_source_relationships").upsert({
                "source_content_item_id":source_item_id,
                "related_content_item_id":related["content_item_id"],
                "relationship_type":p.get("relationship_type") or "primary_supports_secondary",
                "confidence":p.get("confidence") or 0.85,
                "metadata":{"discovered_by":"AI_RESEARCH"}
            },on_conflict="source_content_item_id,related_content_item_id,relationship_type").execute()
            created+=1
        except Exception:
            pass
    return created


def _fact_norm(value):
    s=str(value or "").strip().casefold()
    s=re.sub(r"&"," and ",s)
    s=re.sub(r"[^a-z0-9]+"," ",s)
    return re.sub(r"\s+"," ",s).strip()


def _fact_object_kind(value):
    raw=_fact_norm(value).replace(" ","_")
    aliases={
        "company":"entity","organisation":"entity","organization":"entity",
        "authority":"entity","government":"entity","operator":"entity","owner":"entity",
        "shipyard_company":"entity","builder":"entity","designer":"entity",
        "port":"asset","terminal":"asset","airport":"asset","facility":"asset",
        "project":"asset","infrastructure":"asset","rail_node":"asset",
        "vessel":"mobile_asset","ship":"mobile_asset","aircraft":"mobile_asset",
        "truck":"mobile_asset","rolling_stock":"mobile_asset",
        "service":"transport_service","transport_service":"transport_service",
        "liner_service":"transport_service","shipping_service":"transport_service",
        "route":"route","corridor":"route",
    }
    return aliases.get(raw,raw)


@st.cache_data(show_spinner=False, ttl=60)
def _fact_resolution_indexes():
    """Small live indexes used to resolve extracted fact subjects/objects."""
    out={
        "entity":{"by_id":{},"by_name":{}},
        "asset":{"by_id":{},"by_name":{}},
        "mobile_asset":{"by_id":{},"by_name":{},"by_imo":{},"by_mmsi":{}},
        "transport_service":{"by_id":{},"by_name":{},"by_code":{}},
        "route":{"by_id":{},"by_name":{}},
    }
    if not sb:
        return out

    try:
        rows=safe_rows(sb,"pc_entities","entity_id,name,entity_type,hq_country",30000)
        for r in rows:
            rid=str(r.get("entity_id") or "")
            nm=_fact_norm(r.get("name"))
            if rid: out["entity"]["by_id"][rid]=r
            if nm: out["entity"]["by_name"].setdefault(nm,[]).append(r)

        aliases=safe_rows(sb,"pc_entity_aliases","entity_id,alias,alias_type",50000)
        for a in aliases:
            eid=str(a.get("entity_id") or "")
            alias=_fact_norm(a.get("alias"))
            row=out["entity"]["by_id"].get(eid)
            if row and alias:
                out["entity"]["by_name"].setdefault(alias,[]).append(row)

        identifiers=safe_rows(
            sb,"pc_entity_identifiers",
            "entity_id,identifier_type,identifier_value,normalized_value,is_primary",
            50000
        )
        out["entity"]["by_identifier"]={}
        for ident in identifiers:
            eid=str(ident.get("entity_id") or "")
            row=out["entity"]["by_id"].get(eid)
            if not row:
                continue
            for raw in [ident.get("normalized_value"),ident.get("identifier_value")]:
                key=_fact_norm(raw)
                if key:
                    out["entity"]["by_identifier"].setdefault(key,[]).append(row)
    except Exception:
        pass

    try:
        rows=safe_rows(sb,"pc_assets","asset_id,name,asset_type,subtype,country,region_city",50000)
        for r in rows:
            rid=str(r.get("asset_id") or "")
            nm=_fact_norm(r.get("name"))
            if rid: out["asset"]["by_id"][rid]=r
            if nm: out["asset"]["by_name"].setdefault(nm,[]).append(r)
    except Exception:
        pass

    try:
        rows=safe_rows(sb,"pc_mobile_assets","mobile_asset_id,name,asset_type,subtype,imo,mmsi,flag",50000)
        for r in rows:
            rid=str(r.get("mobile_asset_id") or "")
            nm=_fact_norm(r.get("name"))
            imo=re.sub(r"\\D","",str(r.get("imo") or ""))
            mmsi=re.sub(r"\\D","",str(r.get("mmsi") or ""))
            if rid: out["mobile_asset"]["by_id"][rid]=r
            if nm: out["mobile_asset"]["by_name"].setdefault(nm,[]).append(r)
            if imo: out["mobile_asset"]["by_imo"].setdefault(imo,[]).append(r)
            if mmsi: out["mobile_asset"]["by_mmsi"].setdefault(mmsi,[]).append(r)
    except Exception:
        pass

    try:
        rows=safe_rows(sb,"pc_transport_services","transport_service_id,service_name,service_code,mode,service_type,status",20000)
        for r in rows:
            rid=str(r.get("transport_service_id") or "")
            nm=_fact_norm(r.get("service_name"))
            code=_fact_norm(r.get("service_code"))
            if rid: out["transport_service"]["by_id"][rid]=r
            if nm: out["transport_service"]["by_name"].setdefault(nm,[]).append(r)
            if code: out["transport_service"]["by_code"].setdefault(code,[]).append(r)

        aliases=safe_rows(
            sb,"pc_transport_service_aliases",
            "transport_service_id,alias,alias_type,operator_entity_id",
            30000
        )
        for a in aliases:
            sid=str(a.get("transport_service_id") or "")
            alias=_fact_norm(a.get("alias"))
            row=out["transport_service"]["by_id"].get(sid)
            if row and alias:
                out["transport_service"]["by_name"].setdefault(alias,[]).append(row)
    except Exception:
        pass

    try:
        rows=safe_rows(sb,"pc_transport_routes","route_id,route_name,mode,current_status",20000)
        for r in rows:
            rid=str(r.get("route_id") or "")
            nm=_fact_norm(r.get("route_name"))
            if rid: out["route"]["by_id"][rid]=r
            if nm: out["route"]["by_name"].setdefault(nm,[]).append(r)
    except Exception:
        pass

    return out


def _resolve_fact_reference(kind,name=None,identifier=None):
    """Deterministic exact resolution only. Ambiguity remains reviewable."""
    kind=_fact_object_kind(kind)
    indexes=_fact_resolution_indexes()
    idx=indexes.get(kind)
    if not idx:
        return {"status":"unsupported","kind":kind,"matches":[]}

    ident=str(identifier or "").strip()
    name_key=_fact_norm(name)

    # Canonical ID first.
    if ident and ident in idx.get("by_id",{}):
        return {"status":"matched","kind":kind,"match":idx["by_id"][ident],"method":"canonical_id","confidence":1.0}

    if kind=="entity" and ident:
        hits=idx.get("by_identifier",{}).get(_fact_norm(ident),[])
        if len(hits)==1:
            return {"status":"matched","kind":kind,"match":hits[0],"method":"registered_identifier","confidence":0.99}
        if len(hits)>1:
            return {"status":"ambiguous","kind":kind,"matches":hits,"method":"registered_identifier"}

    # Strong identifiers for mobile assets.
    if kind=="mobile_asset" and ident:
        digits=re.sub(r"\\D","",ident)
        if len(digits)==7:
            hits=idx.get("by_imo",{}).get(digits,[])
            if len(hits)==1:
                return {"status":"matched","kind":kind,"match":hits[0],"method":"imo","confidence":1.0}
            if len(hits)>1:
                return {"status":"ambiguous","kind":kind,"matches":hits,"method":"imo"}
        if len(digits)==9:
            hits=idx.get("by_mmsi",{}).get(digits,[])
            if len(hits)==1:
                return {"status":"matched","kind":kind,"match":hits[0],"method":"mmsi","confidence":0.99}
            if len(hits)>1:
                return {"status":"ambiguous","kind":kind,"matches":hits,"method":"mmsi"}

    # Service code can be stronger than service name.
    if kind=="transport_service" and ident:
        hits=idx.get("by_code",{}).get(_fact_norm(ident),[])
        if len(hits)==1:
            return {"status":"matched","kind":kind,"match":hits[0],"method":"service_code","confidence":0.99}
        if len(hits)>1:
            return {"status":"ambiguous","kind":kind,"matches":hits,"method":"service_code"}

    if name_key:
        hits=idx.get("by_name",{}).get(name_key,[])
        if len(hits)==1:
            return {"status":"matched","kind":kind,"match":hits[0],"method":"exact_normalized_name","confidence":0.96}
        if len(hits)>1:
            return {"status":"ambiguous","kind":kind,"matches":hits,"method":"exact_normalized_name"}

    return {"status":"unresolved","kind":kind,"matches":[]}


def _fact_match_id(kind,row):
    kind=_fact_object_kind(kind)
    if kind=="entity": return row.get("entity_id")
    if kind=="asset": return row.get("asset_id")
    if kind=="mobile_asset": return row.get("mobile_asset_id")
    if kind=="transport_service": return row.get("transport_service_id")
    if kind=="route": return row.get("route_id")
    return None


def _fact_match_name(kind,row):
    kind=_fact_object_kind(kind)
    if kind=="transport_service": return row.get("service_name")
    if kind=="route": return row.get("route_name")
    return row.get("name")


_FACT_TABLE_HINTS={
    "entity_identity":{"pc_entities"},
    "asset_identity":{"pc_assets"},
    "mobile_asset_identity":{"pc_mobile_assets"},
    "relationship":{"pc_relationships"},
    "event":{"pc_events"},
    "security_incident":{"pc_events"},
    "transaction":{"pc_transactions"},
    "ownership_change":{"pc_transactions","pc_relationships"},
    "project":{"pc_assets","pc_project_details"},
    "financing":{"pc_financing_facilities","pc_financing_participants","pc_financing_links"},
    "contract":{"pc_contracts","pc_contract_participants","pc_contract_links"},
    "shipbuilding_order":{"pc_shipbuilding_orders","pc_shipbuilding_order_units","pc_contracts"},
    "vessel_design":{"pc_vessel_designs"},
    "transport_service":{"pc_transport_services","pc_transport_service_operators","pc_transport_service_stops","pc_transport_service_sources"},
    "service_change":{"pc_transport_service_changes","pc_transport_services"},
    "route":{"pc_transport_routes","pc_transport_service_network_links"},
    "sanctions":{"pc_sanctions_designations","pc_sanctions_links","pc_trade_restrictions"},
}


def _payload_blob(payload):
    try:
        return _fact_norm(json.dumps(payload or {},ensure_ascii=False,default=str))
    except Exception:
        return _fact_norm(payload)


def _backfill_fact_promotions(content_item_id, extraction_run_id=None, ingestion_job_id=None):
    """Attach extracted facts to already-staged proposals for the same extraction job."""
    if not sb:
        return 0
    if not ingestion_job_id and extraction_run_id:
        run=(sb.table("pc_extraction_runs")
             .select("ingestion_job_id")
             .eq("extraction_run_id",extraction_run_id).limit(1).execute().data or [])
        if run:
            ingestion_job_id=run[0].get("ingestion_job_id")
    if not ingestion_job_id:
        return 0

    facts=(sb.table("pc_extracted_facts").select("*")
           .eq("content_item_id",content_item_id).limit(5000).execute().data or [])
    staged=(sb.table("pc_staged_records")
            .select("staged_record_id,target_table,natural_key,payload,resolution_status,review_status")
            .eq("ingestion_job_id",str(ingestion_job_id)).limit(5000).execute().data or [])
    if not facts or not staged:
        return 0

    created=0
    for f in facts:
        fact_id=f.get("fact_id")
        ftype=str(f.get("fact_type") or "other")
        hinted=_FACT_TABLE_HINTS.get(ftype,set())
        subj=_fact_norm(f.get("subject_name"))
        obj=_fact_norm(f.get("object_name"))
        pred=_fact_norm(f.get("predicate"))

        candidates=[]
        for sr in staged:
            table=str(sr.get("target_table") or "")
            payload=sr.get("payload") if isinstance(sr.get("payload"),dict) else {}
            blob=_payload_blob(payload)
            score=0
            if table in hinted: score+=5
            if subj and subj in blob: score+=3
            if obj and obj in blob: score+=2
            if pred and pred in blob: score+=1
            if score>0:
                candidates.append((score,sr))

        if not candidates:
            continue

        best=max(x[0] for x in candidates)
        # Keep all equally strong specialist rows, e.g. order + unit/design rows.
        for score,sr in candidates:
            if score < best:
                continue
            row={
                "fact_id":fact_id,
                "ingestion_job_id":str(ingestion_job_id),
                "staged_record_id":sr.get("staged_record_id"),
                "target_table":sr.get("target_table"),
                "target_record_id":None,
                "promotion_action":"stage",
                "status":"staged",
                "promoted_at":pd.Timestamp.utcnow().isoformat(),
                "metadata":{
                    "match_score":score,
                    "natural_key":sr.get("natural_key"),
                    "staged_resolution_status":sr.get("resolution_status"),
                    "staged_review_status":sr.get("review_status"),
                }
            }
            try:
                exists=(sb.table("pc_extracted_fact_promotions")
                        .select("fact_promotion_id")
                        .eq("fact_id",fact_id)
                        .eq("staged_record_id",str(sr.get("staged_record_id")))
                        .limit(1).execute().data or [])
                if not exists:
                    sb.table("pc_extracted_fact_promotions").insert(row).execute()
                    created+=1
            except Exception:
                pass
    return created


def _resolve_content_item_facts(content_item_id, extraction_run_id=None, ingestion_job_id=None):
    """Resolve fact subjects/objects, link canonical matches and classify readiness."""
    if not sb:
        return {"facts":0,"matched":0,"ready":0,"partial":0,"ambiguous":0,"unresolved":0,"links":0,"promotions":0}

    _fact_resolution_indexes.clear()

    if not extraction_run_id:
        runs=(sb.table("pc_extraction_runs")
              .select("extraction_run_id,ingestion_job_id,started_at")
              .eq("content_item_id",content_item_id)
              .order("started_at",desc=True).limit(1).execute().data or [])
        if runs:
            extraction_run_id=runs[0].get("extraction_run_id")
            ingestion_job_id=ingestion_job_id or runs[0].get("ingestion_job_id")

    promotions=_backfill_fact_promotions(
        content_item_id,
        extraction_run_id=extraction_run_id,
        ingestion_job_id=ingestion_job_id
    )

    facts=(sb.table("pc_extracted_facts").select("*")
           .eq("content_item_id",content_item_id).limit(5000).execute().data or [])
    stats={"facts":len(facts),"matched":0,"ready":0,"partial":0,"ambiguous":0,"unresolved":0,"links":0,"promotions":promotions}

    for f in facts:
        fid=f.get("fact_id")
        refs=[]
        ambiguous=False
        unresolved_named=False
        named_slots=0

        for role,tcol,ncol,icol in [
            ("subject","subject_type","subject_name","subject_identifier"),
            ("object","object_type","object_name","object_identifier"),
        ]:
            typ=f.get(tcol)
            name=f.get(ncol)
            ident=f.get(icol)
            if not typ or (not name and not ident):
                continue
            named_slots+=1
            res=_resolve_fact_reference(typ,name,ident)
            if res.get("status")=="matched":
                row=res["match"]
                kind=res["kind"]
                linked_id=_fact_match_id(kind,row)
                linked_name=_fact_match_name(kind,row) or name
                if linked_id:
                    refs.append({
                        "fact_id":fid,
                        "linked_type":kind,
                        "linked_id":str(linked_id),
                        "linked_name":linked_name,
                        "role":role,
                        "match_method":res.get("method"),
                        "confidence":res.get("confidence") or 0.95,
                        "analyst_reviewed":False,
                        "metadata":{"input_name":name,"input_identifier":ident},
                    })
            elif res.get("status")=="ambiguous":
                ambiguous=True
            else:
                unresolved_named=True

        for link in refs:
            try:
                sb.table("pc_extracted_fact_links").upsert(
                    link,on_conflict="fact_id,linked_type,linked_id,role"
                ).execute()
                stats["links"]+=1
            except Exception:
                pass

        try:
            promo_rows=(sb.table("pc_extracted_fact_promotions")
                        .select("fact_promotion_id,status,target_table,staged_record_id")
                        .eq("fact_id",fid).limit(100).execute().data or [])
        except Exception:
            promo_rows=[]

        matched_count=len(refs)
        if ambiguous:
            status="ambiguous"
        elif promo_rows:
            status="ready"
        elif named_slots and matched_count==named_slots:
            status="matched"
        elif matched_count>0:
            status="partial"
        else:
            status="unresolved"

        stats[status]=stats.get(status,0)+1

        try:
            sb.table("pc_extracted_facts").update({
                "resolution_status":status,
                "updated_at":pd.Timestamp.utcnow().isoformat(),
                "metadata":{
                    **(f.get("metadata") if isinstance(f.get("metadata"),dict) else {}),
                    "resolution":{
                        "canonical_links":matched_count,
                        "named_slots":named_slots,
                        "has_staged_promotion":bool(promo_rows),
                        "resolved_at":pd.Timestamp.utcnow().isoformat(),
                    }
                }
            }).eq("fact_id",fid).execute()
        except Exception:
            pass

    # Overall content item status
    if stats["facts"]==0:
        overall="unresolved"
    elif stats["unresolved"]==0 and stats["ambiguous"]==0 and stats["partial"]==0:
        overall="ready"
    elif stats["ready"] or stats["matched"]:
        overall="partial"
    else:
        overall="unresolved"

    try:
        sb.table("pc_content_ingest_items").update({
            "resolution_status":overall,
            "updated_at":pd.Timestamp.utcnow().isoformat()
        }).eq("content_item_id",content_item_id).execute()
    except Exception:
        pass

    return stats



def _latest_content_extraction_run(content_item_id):
    rows=(sb.table("pc_extraction_runs")
          .select("extraction_run_id,ingestion_job_id,status,started_at,metadata")
          .eq("content_item_id",content_item_id)
          .order("started_at",desc=True).limit(1).execute().data or [])
    return rows[0] if rows else {}


def _fact_prompt_rows(content_item_id, limit=400):
    return (sb.table("pc_extracted_facts").select(
        "fact_id,fact_type,fact_key,subject_type,subject_name,subject_identifier,"
        "predicate,object_type,object_name,object_identifier,value_text,value_numeric,"
        "unit,currency,effective_date,start_date,end_date,location_text,country,"
        "evidence_text,source_url,primary_source_url,confidence,verification_status"
    ).eq("content_item_id",content_item_id).limit(int(limit)).execute().data or [])


def _create_content_promotion_job(item, product_context="TRADE"):
    return sb.table("pc_ingestion_jobs").insert({
        "job_type":"CONTENT_FACT_PROMOTION",
        "title":f"Promote extracted facts · {item.get('title') or item.get('source_url') or item.get('content_item_id')}",
        "query_text":"Build canonical/domain staged proposals from preserved extracted facts.",
        "source_scope":{
            "content_item_id":item.get("content_item_id"),
            "source_url":item.get("source_url"),
            "product_context":product_context,
            "loader_build":LOADER_BUILD,
        },
        "status":"running",
    }).execute().data[0]


def _build_staged_proposals_from_content_item(
    content_item_id,
    product_context="TRADE",
    use_web=False,
    force=False
):
    """Second pass: turn preserved atomic facts into normal staged P&C records."""
    if not ai_configured():
        raise RuntimeError("AI research is not configured.")

    items=(sb.table("pc_content_ingest_items").select("*")
           .eq("content_item_id",content_item_id).limit(1).execute().data or [])
    if not items:
        raise RuntimeError(f"Content item not found: {content_item_id}")
    item=items[0]
    facts=_fact_prompt_rows(content_item_id)
    if not facts:
        return {"content_item_id":content_item_id,"facts":0,"staged":0,"message":"No extracted facts"}

    run=_latest_content_extraction_run(content_item_id)
    prior_job=run.get("ingestion_job_id")
    if prior_job and not force:
        prior=(sb.table("pc_staged_records").select("staged_record_id")
               .eq("ingestion_job_id",str(prior_job)).limit(1).execute().data or [])
        if prior:
            stats=_resolve_content_item_facts(
                content_item_id,
                extraction_run_id=run.get("extraction_run_id"),
                ingestion_job_id=prior_job
            )
            return {
                "content_item_id":content_item_id,
                "title":item.get("title"),
                "facts":len(facts),
                "staged":0,
                "staged_existing":True,
                "job_id":prior_job,
                "fact_resolution":stats,
            }

    job=_create_content_promotion_job(item,product_context)
    job_id=job["ingestion_job_id"]

    compact=[
        {k:v for k,v in f.items() if v not in (None,"",[],{})}
        for f in facts
    ]

    prompt=f"""
SECOND-PASS STRUCTURED PROMOTION FOR POWER & CORRIDORS.

The source has already been fetched and fact-extracted. Do not summarize it.
Build the reviewable canonical/domain `records` needed to represent the facts.

SOURCE
Title: {item.get('title') or ''}
Publisher: {item.get('publisher') or ''}
Publication date: {item.get('publication_date') or ''}
Source URL: {item.get('source_url') or ''}

RULES
- Return records for every supported structural fact.
- Preserve the source URL in metadata.research_sources.
- Separate entities/assets/mobile assets from relationships/events.
- Use the specialist tables for transport services, projects, financing,
  contracts, shipbuilding orders/designs and sanctions when supported.
- Do not invent internal IDs; omit them when unknown and let the loader fill them.
- Do not invent IMO numbers, company registrations, amounts, dates, stakes,
  port calls, route stops, ownership or operators.
- Prefer structured child/link records over burying useful data in metadata.
- You may return `facts: []`; the preserved fact layer already exists.

PRESERVED FACTS
{json.dumps(compact,ensure_ascii=False,default=str,indent=2)}
"""

    result=ai_research(
        prompt,
        product_context,
        bool(use_web),
        output_contract=UNIVERSAL_CONTENT_OUTPUT_CONTRACT
    )
    result=_prepare_universal_records(
        result,
        item.get("source_url"),
        item.get("publisher"),
        item.get("title")
    )
    result["facts"]=[]

    staged,rejected,resolution=stage_ai_result(sb,job_id,result)

    if run.get("extraction_run_id"):
        meta=run.get("metadata") if isinstance(run.get("metadata"),dict) else {}
        meta=dict(meta)
        meta["promotion_job_id"]=str(job_id)
        meta["promotion_records_staged"]=staged
        sb.table("pc_extraction_runs").update({
            "ingestion_job_id":job_id,
            "records_proposed":staged,
            "metadata":meta
        }).eq("extraction_run_id",run["extraction_run_id"]).execute()

    fact_resolution=_resolve_content_item_facts(
        content_item_id,
        extraction_run_id=run.get("extraction_run_id"),
        ingestion_job_id=job_id
    )

    sb.table("pc_ingestion_jobs").update({
        "status":"completed",
        "completed_at":pd.Timestamp.utcnow().isoformat(),
        "stats":{
            "facts_basis":len(facts),
            "staged_records":staged,
            "rejected_records":rejected,
            "resolution":resolution,
            "fact_resolution":fact_resolution,
        }
    }).eq("ingestion_job_id",job_id).execute()

    return {
        "content_item_id":content_item_id,
        "title":item.get("title"),
        "facts":len(facts),
        "staged":staged,
        "rejected":rejected,
        "job_id":job_id,
        "fact_resolution":fact_resolution,
    }


def _build_proposals_for_fact_queue(limit_items=50, product_context="TRADE"):
    items=(sb.table("pc_content_ingest_items")
           .select("content_item_id,title,source_url,resolution_status,created_at")
           .order("created_at",desc=True).limit(int(limit_items)).execute().data or [])
    report=[]
    for item in items:
        cid=item.get("content_item_id")
        count=(sb.table("pc_extracted_facts").select("fact_id",count="exact")
               .eq("content_item_id",cid).limit(1).execute().count or 0)
        if not count:
            continue
        try:
            report.append(_build_staged_proposals_from_content_item(
                cid,product_context=product_context,use_web=False,force=False
            ))
        except Exception as exc:
            report.append({
                "content_item_id":cid,
                "title":item.get("title"),
                "error":str(exc)
            })
    return report


def _resolve_all_pending_content_facts(limit_items=100):
    """Backfill the current unresolved queue after deploying Loader v4.1."""
    items=(sb.table("pc_content_ingest_items")
           .select("content_item_id,title,source_url,resolution_status,created_at")
           .order("created_at",desc=True).limit(int(limit_items)).execute().data or [])
    report=[]
    for item in items:
        cid=item.get("content_item_id")
        try:
            stats=_resolve_content_item_facts(cid)
            report.append({"content_item_id":cid,"title":item.get("title"),**stats})
        except Exception as exc:
            report.append({"content_item_id":cid,"title":item.get("title"),"error":str(exc)})
    return report


@st.cache_data(show_spinner=False, ttl=20)
def _content_review_data(limit=5000):
    """Return content items, facts, links and promotions for analyst review.

    Cached briefly so ordinary Streamlit clicks do not re-scan the fact/link
    tables on every rerun. Mutating workflows clear this cache explicitly.
    """
    items=(sb.table("pc_content_ingest_items").select(
        "content_item_id,title,publisher,publication_date,source_url,primary_source_candidate,primary_source_verified,fetch_status,extraction_status,resolution_status,created_at"
    ).order("created_at",desc=True).limit(1000).execute().data or [])

    facts=(sb.table("pc_extracted_facts").select(
        "fact_id,content_item_id,fact_type,subject_type,subject_name,subject_identifier,predicate,object_type,object_name,object_identifier,value_text,value_numeric,unit,currency,effective_date,source_url,primary_source_url,confidence,verification_status,review_status,resolution_status,metadata,created_at"
    ).order("created_at",desc=True).limit(int(limit)).execute().data or [])
    facts=[
        x for x in facts
        if not bool((x.get("metadata") or {}).get("audit_duplicate"))
    ]

    active_fact_ids={str(x.get("fact_id")) for x in facts if x.get("fact_id")}

    links=(sb.table("pc_extracted_fact_links").select(
        "fact_id,linked_type,linked_id,linked_name,role,match_method,confidence,analyst_reviewed"
    ).limit(int(limit)*2).execute().data or [])
    links=[x for x in links if str(x.get("fact_id")) in active_fact_ids]

    promotions=(sb.table("pc_extracted_fact_promotions").select(
        "fact_id,target_table,staged_record_id,target_record_id,promotion_action,status,promoted_at"
    ).limit(int(limit)*2).execute().data or [])
    promotions=[x for x in promotions if str(x.get("fact_id")) in active_fact_ids]

    return items,facts,links,promotions


def _review_article_summary(item,fact_rows,link_rows,promo_rows):
    """Render one analyst-friendly article review block."""

    def _safe_display(v):
        if v is None:
            return ""
        try:
            if pd.isna(v):
                return ""
        except Exception:
            pass
        s=str(v).strip()
        return "" if s.casefold() in {"nan","none","<na>","nat","null"} else s

    title_txt=_safe_display(item.get("title")) or _safe_display(item.get("source_url")) or "Untitled source"
    publisher=_safe_display(item.get("publisher"))
    pubdate=_safe_display(item.get("publication_date"))
    source_url=_safe_display(item.get("source_url"))

    st.markdown(f"### {title_txt}")
    meta=" · ".join(x for x in [publisher,pubdate] if x)
    if meta:
        st.caption(meta)
    if source_url:
        st.markdown(f"[Open source article]({source_url})")

    facts_df=pd.DataFrame(fact_rows)
    links_df=pd.DataFrame(link_rows)
    promo_df=pd.DataFrame(promo_rows)

    c1,c2,c3,c4=st.columns(4)
    c1.metric("Facts",len(facts_df))
    c2.metric("Canonical links",len(links_df))
    c3.metric("Staged proposals",len(promo_df))
    verified=0
    if not facts_df.empty and "verification_status" in facts_df.columns:
        verified=int(facts_df["verification_status"].astype(str).isin(["primary_source_supported","corroborated"]).sum())
    c4.metric("Primary-source supported",verified)

    if facts_df.empty:
        st.caption("No extracted facts.")
        return

    for _,f in facts_df.head(80).iterrows():
        left=_safe_display(f.get("subject_name")) or _safe_display(f.get("subject_identifier")) or "Fact"
        predicate=_safe_display(f.get("predicate"))
        right=_safe_display(f.get("object_name")) or _safe_display(f.get("value_text"))
        if not right and pd.notna(f.get("value_numeric")):
            right=f"{f.get('value_numeric')} {f.get('unit') or ''}".strip()
        status=str(f.get("resolution_status") or "unresolved")
        conf=f.get("confidence")
        try:
            conf_txt=f"{float(conf)*100:.0f}%"
        except Exception:
            conf_txt=""

        flinks=links_df[links_df["fact_id"].astype(str).eq(str(f.get("fact_id")))] if not links_df.empty else pd.DataFrame()
        fp=promo_df[promo_df["fact_id"].astype(str).eq(str(f.get("fact_id")))] if not promo_df.empty else pd.DataFrame()

        icon={"ready":"✓","matched":"✓","partial":"◐","ambiguous":"?","unresolved":"○"}.get(status,"○")
        st.markdown(f"**{icon} {left} — {predicate} → {right or '—'}**")
        detail=[]
        if conf_txt: detail.append(f"Confidence {conf_txt}")
        detail.append(f"Status {status}")
        if not flinks.empty:
            names=[str(x) for x in flinks.get("linked_name",pd.Series(dtype=str)).dropna().tolist() if str(x)]
            if names: detail.append("Matched: "+", ".join(dict.fromkeys(names)))
        if not fp.empty:
            tables=[str(x) for x in fp.get("target_table",pd.Series(dtype=str)).dropna().tolist() if str(x)]
            if tables: detail.append("Staged: "+", ".join(dict.fromkeys(tables)))
        st.caption(" · ".join(detail))
        ps=_safe_display(f.get("primary_source_url"))
        if ps:
            st.markdown(f"[Primary source]({ps})")
        st.markdown("")



def _queue_content_urls(
    urls,
    input_mode,
    product_context="TRADE",
    manifest_document_id=None,
    batch_name=None,
    discovery_method="pasted_url",
):
    """Persist URL items without fetching or invoking AI. Intended to be near-instant."""
    batch=_create_content_batch(
        input_mode=input_mode,
        batch_name=batch_name or f"Queued URL intake · {len(urls)} source(s)",
        product_context=product_context,
        research_mode="queued",
        item_count=len(urls),
        metadata={
            "manifest_document_id":str(manifest_document_id) if manifest_document_id else None,
            "loader_build":LOADER_BUILD,
            "queued_only":True,
        }
    )
    bid=batch["content_batch_id"]
    items=[]
    failures=[]
    for u in urls:
        try:
            items.append(_upsert_content_url_item(
                bid,u,manifest_document_id,discovery_method
            ))
        except Exception as exc:
            failures.append({"url":u,"error":str(exc)})

    sb.table("pc_content_ingest_batches").update({
        "status":"queued" if not failures else "queued_with_errors",
        "processed_count":0,
        "failed_count":len(failures),
        "updated_at":pd.Timestamp.utcnow().isoformat(),
        "metadata":{
            "manifest_document_id":str(manifest_document_id) if manifest_document_id else None,
            "loader_build":LOADER_BUILD,
            "queued_only":True,
            "failures":failures[:100],
        }
    }).eq("content_batch_id",bid).execute()

    try:
        _content_review_data.clear()
    except Exception:
        pass
    return batch,items,failures


def _direct_apply_content_result(res):
    """Immediately promote safe staged records into canonical tables.

    Facts remain provenance only. Missing deterministic dependencies are created/upserted
    by the canonical job processor. Only genuine ambiguity remains for analyst review.
    """
    job_id=(res or {}).get("job_id")
    if not job_id:
        return {"applied":0,"blocked":0,"job_id":None}
    report=_process_job_automatically(str(job_id))
    try:
        candidates,blocked=_job_apply_candidates(str(job_id))
    except Exception:
        blocked=[]
    applied=int((report or {}).get("total_applied_this_run",0) or 0)
    return {
        "job_id":str(job_id),
        "applied":applied,
        "blocked":len(blocked),
        "report":report,
    }


def _load_content_item_to_canonical(batch_id,item,product_context="TRADE",use_web=False):
    """One-pass source -> canonical load. No fact-review gate."""
    res=_run_content_item_extraction(
        batch_id,
        item,
        use_web=bool(use_web),
        product_context=product_context,
        extract_only=False,
        resolve_after=False,
    )
    direct=_direct_apply_content_result(res)
    res["canonical_applied"]=direct.get("applied",0)
    res["canonical_blocked"]=direct.get("blocked",0)
    res["canonical_apply_report"]=direct.get("report")
    try:
        sb.table("pc_content_ingest_items").update({
            "resolution_status":(
                "loaded" if int(direct.get("blocked",0) or 0)==0
                else "loaded_with_exceptions"
            ),
            "updated_at":pd.Timestamp.utcnow().isoformat(),
        }).eq("content_item_id",item.get("content_item_id")).execute()
    except Exception:
        pass
    return res


def _process_queued_content_items(limit_items=10, product_context="TRADE", deep=False):
    """Load queued URLs directly into canonical tables.

    `deep=True` adds web verification, but both modes write safe canonical records
    immediately. Review is reserved for genuine ambiguity.
    """
    rows=(sb.table("pc_content_ingest_items")
          .select("*")
          .in_("extraction_status",["pending","failed"])
          .order("created_at",desc=False)
          .limit(int(limit_items)).execute().data or [])
    results=[]
    failures=[]
    for item in rows:
        try:
            res=_load_content_item_to_canonical(
                item.get("content_batch_id"),
                item,
                product_context=product_context,
                use_web=bool(deep),
            )
            results.append(res)
        except Exception as exc:
            failures.append({
                "content_item_id":item.get("content_item_id"),
                "url":item.get("source_url"),
                "error":str(exc)
            })
            try:
                sb.table("pc_content_ingest_items").update({
                    "extraction_status":"failed",
                    "extraction_error":str(exc),
                    "updated_at":pd.Timestamp.utcnow().isoformat()
                }).eq("content_item_id",item.get("content_item_id")).execute()
            except Exception:
                pass
    try:
        _content_review_data.clear()
    except Exception:
        pass
    return results,failures


def _run_content_item_extraction(
    batch_id,
    item,
    use_web=False,
    product_context="TRADE",
    extract_only=False,
    resolve_after=True
):
    """Fetch one URL and extract structured content.

    Fast mode (`extract_only=True`) preserves atomic facts only and deliberately
    defers staging/resolution to the batch promotion step. This is materially
    faster than doing web research + staging + canonical resolution per URL.
    """
    item_id=item["content_item_id"]
    url=item.get("source_url") or item.get("normalized_url")
    fetched=None
    try:
        fetched=_fetch_content_url(url)
        sb.table("pc_content_ingest_items").update({
            "source_url":fetched.get("url") or url,
            "title":fetched.get("title"),
            "publisher":fetched.get("publisher"),
            "publication_date":fetched.get("publication_date"),
            "retrieved_at":pd.Timestamp.utcnow().isoformat(),
            "raw_text":fetched.get("raw_text"),
            "extracted_text":fetched.get("extracted_text"),
            "content_hash":fetched.get("content_hash"),
            "mime_type":fetched.get("mime_type"),
            "http_status":fetched.get("status"),
            "fetch_status":"completed",
            "extraction_status":"running",
            "updated_at":pd.Timestamp.utcnow().isoformat(),
        }).eq("content_item_id",item_id).execute()
    except Exception as exc:
        sb.table("pc_content_ingest_items").update({
            "fetch_status":"failed",
            "fetch_error":str(exc),
            "extraction_status":"running",
            "updated_at":pd.Timestamp.utcnow().isoformat(),
        }).eq("content_item_id",item_id).execute()
        fetched={
            "url":url,"title":None,
            "publisher":urllib.parse.urlsplit(url).netloc,
            "extracted_text":"",
            "publication_date":None
        }

    # Idempotent short-circuit: if this URL's fetched content has not changed
    # and we already extracted facts, do not call AI again.
    prior_hash=str(item.get("content_hash") or "")
    new_hash=str((fetched or {}).get("content_hash") or "")
    if prior_hash and new_hash and prior_hash==new_hash:
        existing_count=(sb.table("pc_extracted_facts")
            .select("fact_id",count="exact")
            .eq("content_item_id",item_id)
            .limit(10000).execute().data or [])
        existing_count=sum(
            1 for x in existing_rows
            if not bool((x.get("metadata") or {}).get("audit_duplicate"))
        )
        if existing_count:
            runs=(sb.table("pc_extraction_runs")
                .select("extraction_run_id,ingestion_job_id,status,created_at")
                .eq("content_item_id",item_id)
                .order("created_at",desc=True)
                .limit(1).execute().data or [])
            if runs and runs[0].get("ingestion_job_id"):
                job_id=runs[0]["ingestion_job_id"]
                staged_count=(sb.table("pc_staged_records")
                    .select("staged_record_id",count="exact")
                    .eq("ingestion_job_id",job_id)
                    .limit(1).execute().count or 0)
                try:
                    _content_review_data.clear()
                except Exception:
                    pass
                return {
                    "content_item_id":item_id,
                    "url":url,
                    "title":fetched.get("title") or item.get("title"),
                    "facts":int(existing_count),
                    "staged":int(staged_count or 0),
                    "rejected":0,
                    "primary_sources":0,
                    "job_id":job_id,
                    "resolution":{"mode":"reused_unchanged_content"},
                    "fact_resolution":{"reused":True,"facts":int(existing_count)},
                    "reused_unchanged_content":True,
                }

    job=sb.table("pc_ingestion_jobs").insert({
        "job_type":"CONTENT_INGEST",
        "title":fetched.get("title") or url,
        "query_text":"Universal URL/article fact extraction",
        "source_scope":{
            "content_batch_id":batch_id,
            "content_item_id":item_id,
            "source_url":url,
            "product_context":product_context
        },
        "status":"running",
    }).execute().data[0]
    job_id=job["ingestion_job_id"]

    sb.table("pc_content_ingest_batches").update({
        "ingestion_job_id":job_id,
        "updated_at":pd.Timestamp.utcnow().isoformat()
    }).eq("content_batch_id",batch_id).execute()

    extraction_run=sb.table("pc_extraction_runs").insert({
        "content_item_id":item_id,
        "ingestion_job_id":job_id,
        "extraction_type":"article_fact_extraction",
        "status":"running",
        "prompt_version":"universal-v4",
        "metadata":{"source_url":url}
    }).execute().data[0]

    article_text=(fetched.get("extracted_text") or "")[:80000]
    prompt=f"""
Analyze this source for Power & Corridors. Extract ALL material structured facts
supported by the source: entities, ownership/control, transactions, financing,
contracts, infrastructure projects, ports/terminals, vessels, shipbuilding,
scheduled transport services/routes, sanctions, security incidents, operational
changes, dates, monetary values, quantities and specifications.

INPUT URL: {url}
TITLE: {fetched.get('title') or ''}
PUBLISHER: {fetched.get('publisher') or ''}
PUBLICATION DATE: {fetched.get('publication_date') or ''}

If current web research is enabled, verify material facts and locate the most
authoritative primary sources (company release, exchange filing, regulator,
government source, shipyard/carrier release, etc.). Do not overwrite the
secondary article: return the primary source separately and preserve both.

Do not create a generic news/event record merely because an article exists.
Create pc_events only when the article describes a real event/milestone/
disruption/announcement that belongs in the event layer.

{"FAST EXTRACTION MODE: Return atomic facts only. Set records=[] and primary_sources=[] unless the source text itself explicitly contains an authoritative primary-source URL. Do not spend tokens constructing staged records in this pass." if extract_only else "FULL EXTRACTION MODE: Return facts and supported canonical/domain record proposals."}

SOURCE TEXT:
{article_text}
"""
    if not ai_configured():
        raise RuntimeError("AI research is not configured.")

    result=ai_research(
        prompt,
        product_context,
        bool(use_web),
        output_contract=UNIVERSAL_CONTENT_OUTPUT_CONTRACT
    )
    result=_prepare_universal_records(
        result,url,fetched.get("publisher"),fetched.get("title")
    )

    facts=_persist_extracted_facts(
        item_id,
        extraction_run["extraction_run_id"],
        result,
        url,
        item.get("document_id")
    )
    primary_count=_persist_primary_source_relationships(
        item_id,
        (result or {}).get("primary_sources") or [],
        batch_id
    )

    if extract_only:
        staged=0
        rejected=0
        resolution={"mode":"deferred_fast_extract"}
        fact_resolution={
            "facts":len(facts),
            "matched":0,
            "ready":0,
            "partial":0,
            "ambiguous":0,
            "unresolved":len(facts),
            "links":0,
            "promotions":0,
            "deferred":True,
        }
    else:
        staged,rejected,resolution=stage_ai_result(sb,job_id,result)
        if resolve_after:
            fact_resolution=_resolve_content_item_facts(
                item_id,
                extraction_run_id=extraction_run["extraction_run_id"],
                ingestion_job_id=job_id
            )
        else:
            fact_resolution={
                "facts":len(facts),
                "matched":0,
                "ready":0,
                "partial":0,
                "ambiguous":0,
                "unresolved":len(facts),
                "links":0,
                "promotions":0,
                "deferred":True,
            }

    sb.table("pc_extraction_runs").update({
        "status":"completed",
        "facts_extracted":len(facts),
        "records_proposed":staged,
        "conflicts_count":len((result or {}).get("conflicts") or []),
        "completed_at":pd.Timestamp.utcnow().isoformat(),
        "metadata":{
            "source_url":url,
            "primary_sources_discovered":primary_count,
            "rejected_records":rejected,
            "fact_resolution":fact_resolution
        }
    }).eq("extraction_run_id",extraction_run["extraction_run_id"]).execute()

    sb.table("pc_content_ingest_items").update({
        "extraction_status":"completed",
        "resolution_status":(
            "facts_only" if extract_only
            else "ready" if fact_resolution.get("unresolved",0)==0 and fact_resolution.get("ambiguous",0)==0 and fact_resolution.get("partial",0)==0
            else "partial" if (fact_resolution.get("ready",0) or fact_resolution.get("matched",0))
            else "unresolved"
        ),
        "updated_at":pd.Timestamp.utcnow().isoformat()
    }).eq("content_item_id",item_id).execute()

    sb.table("pc_ingestion_jobs").update({
        "status":"completed",
        "completed_at":pd.Timestamp.utcnow().isoformat(),
        "stats":{
            "content_item_id":item_id,
            "facts":len(facts),
            "staged_records":staged,
            "rejected_records":rejected,
            "primary_sources":primary_count,
            "resolution":resolution
        }
    }).eq("ingestion_job_id",job_id).execute()

    try:
        _content_review_data.clear()
    except Exception:
        pass

    return {
        "content_item_id":item_id,
        "url":url,
        "title":fetched.get("title"),
        "facts":len(facts),
        "staged":staged,
        "rejected":rejected,
        "primary_sources":primary_count,
        "job_id":job_id,
        "resolution":resolution,
        "fact_resolution":fact_resolution,
    }


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



def _simple_hash_id(prefix, *parts):
    raw="|".join(str(x or "").strip() for x in parts).encode("utf-8")
    return f"{prefix}_{hashlib.sha1(raw).hexdigest()[:20].upper()}"


def _simple_clean_name(v):
    return re.sub(r"\s+"," ",str(v or "").strip())


def _simple_source_id(sb, payload):
    """Resolve/create a canonical pc_sources row from source URL when possible."""
    sid=str(payload.get("source_id") or "").strip()
    if sid:
        return sid
    url=str(payload.get("source_url") or payload.get("url") or "").strip()
    if not url:
        return None
    try:
        hit=(sb.table("pc_sources").select("source_id").eq("url",url).limit(1).execute().data or [])
        if hit:
            return hit[0]["source_id"]
    except Exception:
        pass
    sid=_simple_hash_id("SRC_WEB",url)
    source_name=url
    try:
        source_name=urlparse(url).netloc or url
    except Exception:
        pass
    row={
        "source_id":sid,
        "source_name":source_name,
        "publisher":payload.get("publisher") or source_name,
        "source_type":"web",
        "url":url,
        "active":True,
    }
    try:
        writable=set(_table_write_columns_live(sb,"pc_sources"))
        row={k:v for k,v in row.items() if k in writable and v not in (None,"")}
        sb.table("pc_sources").upsert(row,on_conflict="source_id").execute()
    except Exception:
        # Source creation should not block the fact record.
        return None
    return sid


def _simple_ensure_entity(sb, name, country=None, entity_type="company", source_id=None, extra=None):
    """Exact canonical entity lookup; create a minimal source-backed entity if absent."""
    name=_simple_clean_name(name)
    if not name:
        return None
    try:
        hits=(sb.table("pc_entities").select("entity_id,name,hq_country,entity_type")
              .ilike("name",name).limit(25).execute().data or [])
        if country:
            ck=str(country).strip().casefold()
            same=[x for x in hits if not x.get("hq_country") or str(x.get("hq_country")).strip().casefold()==ck]
            if same: hits=same
        if hits:
            eid=hits[0]["entity_id"]
            patch={}
            if source_id and not hits[0].get("source_id"): patch["source_id"]=source_id
            if patch:
                try: sb.table("pc_entities").update(patch).eq("entity_id",eid).execute()
                except Exception: pass
            return eid
    except Exception:
        pass
    eid=_simple_hash_id("ENTITY_AI",name,country or "",entity_type or "entity")
    row={
        "entity_id":eid,
        "name":name,
        "entity_type":entity_type or "company",
        "hq_country":country,
        "record_status":"provisional",
        "data_quality":"medium",
        "source_id":source_id,
        "metadata":{"created_by":"simple_key_first_loader"},
    }
    if isinstance(extra,dict):
        for k,v in extra.items():
            if v not in (None,""): row[k]=v
    writable=set(_table_write_columns_live(sb,"pc_entities"))
    row={k:v for k,v in row.items() if k in writable and v not in (None,"")}
    sb.table("pc_entities").upsert(row,on_conflict="entity_id").execute()
    return eid


def _simple_ensure_asset(sb, name, country=None, asset_type="asset", subtype=None, source_id=None, operator_entity_id=None, owner_entity_id=None):
    """Exact canonical asset lookup; create the key when the object is genuinely new."""
    name=_simple_clean_name(name)
    if not name:
        return None
    try:
        hits=(sb.table("pc_assets").select("asset_id,name,country,asset_type,subtype")
              .ilike("name",name).limit(25).execute().data or [])
        if country:
            ck=str(country).strip().casefold()
            same=[x for x in hits if not x.get("country") or str(x.get("country")).strip().casefold()==ck]
            if same: hits=same
        if hits:
            return hits[0]["asset_id"]
    except Exception:
        pass
    aid=_deterministic_asset_id(name,country or "",asset_type or "asset")
    row={
        "asset_id":aid,
        "name":name,
        "asset_type":asset_type or "asset",
        "subtype":subtype,
        "country":country,
        "operator_entity_id":operator_entity_id,
        "owner_entity_id":owner_entity_id,
        "record_status":"provisional",
        "data_quality":"medium",
        "source_id":source_id,
        "metadata":{"created_by":"simple_key_first_loader"},
    }
    writable=set(_table_write_columns_live(sb,"pc_assets"))
    row={k:v for k,v in row.items() if k in writable and v not in (None,"")}
    sb.table("pc_assets").upsert(row,on_conflict="asset_id").execute()
    return aid


def _simple_ensure_mobile_asset(sb, name=None, imo=None, mmsi=None, flag=None, subtype=None, source_id=None):
    """IMO -> MMSI -> exact name/flag lookup; otherwise create canonical mobile asset."""
    name=_simple_clean_name(name)
    imo=str(imo or "").strip()
    mmsi=str(mmsi or "").strip()
    try:
        if imo:
            hit=(sb.table("pc_mobile_assets").select("mobile_asset_id").eq("imo",imo).limit(1).execute().data or [])
            if hit: return hit[0]["mobile_asset_id"]
        if mmsi:
            hit=(sb.table("pc_mobile_assets").select("mobile_asset_id").eq("mmsi",mmsi).limit(1).execute().data or [])
            if hit: return hit[0]["mobile_asset_id"]
        if name:
            hits=(sb.table("pc_mobile_assets").select("mobile_asset_id,name,flag").ilike("name",name).limit(25).execute().data or [])
            if flag:
                fk=str(flag).strip().casefold()
                same=[x for x in hits if not x.get("flag") or str(x.get("flag")).strip().casefold()==fk]
                if same: hits=same
            if hits: return hits[0]["mobile_asset_id"]
    except Exception:
        pass
    if not (name or imo or mmsi):
        return None
    mid=_simple_hash_id("MOBILE_AI",imo or mmsi or name,flag or "")
    row={
        "mobile_asset_id":mid,
        "name":name or (f"IMO {imo}" if imo else f"MMSI {mmsi}"),
        "asset_type":"vessel",
        "subtype":subtype,
        "imo":imo or None,
        "mmsi":mmsi or None,
        "flag":flag,
        "record_status":"provisional",
        "data_quality":"medium",
        "source_id":source_id,
        "metadata":{"created_by":"simple_key_first_loader"},
    }
    writable=set(_table_write_columns_live(sb,"pc_mobile_assets"))
    row={k:v for k,v in row.items() if k in writable and v not in (None,"")}
    sb.table("pc_mobile_assets").upsert(row,on_conflict="mobile_asset_id").execute()
    return mid


_SIMPLE_ENTITY_REFS = {
    "owner_entity_name":"owner_entity_id",
    "operator_entity_name":"operator_entity_id",
    "manager_entity_name":"manager_entity_id",
    "buyer_entity_name":"buyer_entity_id",
    "seller_entity_name":"seller_entity_id",
    "target_entity_name":"target_entity_id",
    "participant_entity_name":"entity_id",
    "entity_name":"entity_id",
    "authority_entity_name":"authority_entity_id",
    "company_name":"entity_id",
}

_SIMPLE_ASSET_REFS = {
    "asset_name":"asset_id",
    "port_name":"port_asset_id",
    "parent_port_name":"parent_port_asset_id",
    "terminal_name":"terminal_asset_id",
    "berth_name":"berth_asset_id",
    "target_asset_name":"target_asset_id",
    "facility_name":"asset_id",
}


def _simple_primary_id(table, payload, natural_key):
    """Fill missing record IDs deterministically from natural key/source-backed content."""
    conflict=APPLY_CONFLICT_KEYS.get(table)
    if not conflict or "," in conflict:
        return payload
    key=conflict.strip()
    if payload.get(key) not in (None,""):
        return payload
    # Extension tables keyed directly by an existing asset/entity should not invent a second key.
    if key in {"asset_id","entity_id","mobile_asset_id"}:
        return payload
    prefix={
        "event_id":"EVENT_AI","event_link_id":"EVLINK_AI","relationship_id":"REL_AI",
        "transaction_id":"TX_AI","participant_id":"PART_AI","route_id":"ROUTE_AI",
        "port_metric_id":"PORTMET_AI","port_call_id":"PORTCALL_AI","observation_id":"OBS_AI",
        "transport_service_id":"SERVICE_AI","service_operator_id":"SVCOP_AI",
        "service_schedule_id":"SVCSCH_AI","service_transit_time_id":"SVCTT_AI",
        "service_mobile_asset_id":"SVCMA_AI","service_network_link_id":"SVCNET_AI",
        "service_connection_id":"SVCCON_AI","service_change_id":"SVCCHG_AI",
        "financing_id":"FIN_AI","financing_participant_id":"FINPART_AI","financing_link_id":"FINLINK_AI",
        "contract_id":"CONTRACT_AI","contract_participant_id":"CONPART_AI","contract_link_id":"CONLINK_AI",
        "vessel_design_id":"VDESIGN_AI","shipbuilding_order_id":"SHIPORD_AI","shipbuilding_order_unit_id":"SHIPUNIT_AI",
    }.get(key,key.upper())
    payload[key]=_simple_hash_id(prefix,natural_key or _record_key(payload,""),table)
    return payload


def _simple_prepare_payload(sb, table, payload, natural_key):
    """Key-first canonical preparation. Create missing dependency objects, bind IDs, then return schema-safe payload."""
    p=dict(payload or {})
    sid=_simple_source_id(sb,p)
    if sid and not p.get("source_id"):
        p["source_id"]=sid

    country=p.get("country") or p.get("hq_country") or p.get("jurisdiction")

    # Entity dependencies.
    for name_field,id_field in _SIMPLE_ENTITY_REFS.items():
        if p.get(id_field) in (None,"") and p.get(name_field):
            etype="company"
            if "authority" in name_field: etype="government_agency"
            p[id_field]=_simple_ensure_entity(sb,p.get(name_field),country,etype,sid)

    # Core entity record itself.
    if table=="pc_entities":
        if not p.get("entity_id"):
            p["entity_id"]=_simple_ensure_entity(
                sb,p.get("name"),p.get("hq_country") or country,p.get("entity_type") or "company",sid,
                extra={k:v for k,v in p.items() if k not in {"entity_id","name"}}
            )

    # Asset dependencies and specialist asset rows.
    for name_field,id_field in _SIMPLE_ASSET_REFS.items():
        if p.get(id_field) in (None,"") and p.get(name_field):
            atype=(
                "port" if "port" in name_field else
                "terminal" if "terminal" in name_field else
                "berth" if "berth" in name_field else
                p.get("asset_type") or "asset"
            )
            p[id_field]=_simple_ensure_asset(
                sb,p.get(name_field),country,atype,p.get("subtype"),sid,
                p.get("operator_entity_id"),p.get("owner_entity_id")
            )

    if table=="pc_assets" and not p.get("asset_id"):
        p["asset_id"]=_simple_ensure_asset(
            sb,p.get("name") or p.get("asset_name") or p.get("facility_name"),country,
            p.get("asset_type") or "asset",p.get("subtype"),sid,
            p.get("operator_entity_id"),p.get("owner_entity_id")
        )

    if table=="pc_terminal_details" and not p.get("asset_id"):
        tname=p.get("terminal_name") or p.get("name")
        p["asset_id"]=_simple_ensure_asset(sb,tname,country,"terminal",p.get("terminal_type") or p.get("subtype"),sid,p.get("operator_entity_id"),p.get("owner_entity_id"))
    if table=="pc_berth_details" and not p.get("asset_id"):
        bname=p.get("berth_name") or p.get("name") or natural_key
        p["asset_id"]=_simple_ensure_asset(sb,bname,country,"berth",p.get("berth_type"),sid)

    # Mobile-asset dependencies / vessel identity.
    if p.get("mobile_asset_id") in (None,"") and any(p.get(k) for k in ("vessel_name","mobile_asset_name","imo","mmsi")):
        p["mobile_asset_id"]=_simple_ensure_mobile_asset(
            sb,p.get("vessel_name") or p.get("mobile_asset_name") or p.get("name"),
            p.get("imo"),p.get("mmsi"),p.get("flag"),p.get("subtype"),sid
        )
    if table=="pc_mobile_assets" and not p.get("mobile_asset_id"):
        p["mobile_asset_id"]=_simple_ensure_mobile_asset(sb,p.get("name"),p.get("imo"),p.get("mmsi"),p.get("flag"),p.get("subtype"),sid)

    # Polymorphic event links: resolve linked_id directly from linked_type + linked_name.
    if table=="pc_event_links" and not p.get("linked_id") and p.get("linked_name"):
        lt=str(p.get("linked_type") or "").casefold()
        if lt in {"entity","company","organization","actor"}:
            p["linked_type"]="entity"
            p["linked_id"]=_simple_ensure_entity(sb,p.get("linked_name"),country,"company",sid)
        elif lt in {"mobile_asset","vessel","ship","aircraft"}:
            p["linked_type"]="mobile_asset"
            p["linked_id"]=_simple_ensure_mobile_asset(sb,p.get("linked_name"),p.get("imo"),p.get("mmsi"),p.get("flag"),p.get("subtype"),sid)
        else:
            p["linked_type"]="asset"
            p["linked_id"]=_simple_ensure_asset(sb,p.get("linked_name"),country,p.get("asset_type") or "asset",p.get("subtype"),sid)

    p=_simple_primary_id(table,p,natural_key)

    # Keep only writable fields; helper names that are not real columns go to metadata.
    try:
        writable=set(_table_write_columns_live(sb,table))
        overflow={k:v for k,v in p.items() if k not in writable and v not in (None,"")}
        clean={k:v for k,v in p.items() if k in writable and v not in (None,"")}
        if overflow and "metadata" in writable:
            meta=clean.get("metadata") if isinstance(clean.get("metadata"),dict) else {}
            meta=dict(meta)
            meta.setdefault("loader_reference_context",{}).update(_jsonable(overflow))
            clean["metadata"]=meta
        p=clean
    except Exception:
        pass
    return p


def stage_ai_result(sb, job_id, result):
    """Simple key-first loader.

    Every record follows one rule:
      resolve/create canonical dependencies -> bind keys -> stage READY.
    Complex candidate-resolution workflows are reserved only for genuinely
    ambiguous identities; normal document/article loads do not depend on them.
    """
    records=(result or {}).get("records") or []
    staged=[]
    rejected=0
    errors=[]
    meta_map=_meta_table_map(sb)

    # Dependency-first ordering: identity objects before facts that reference them.
    priority={
        "pc_entities":10,"pc_assets":20,"pc_mobile_assets":30,
        "pc_events":40,"pc_transport_services":45,
        "pc_terminal_details":50,"pc_berth_details":55,
        "pc_relationships":70,"pc_event_links":75,
    }
    records=sorted(
        [r for r in records if isinstance(r,dict)],
        key=lambda r: priority.get(str(r.get("target_table") or ""),60)
    )

    for rec in records:
        table=str(rec.get("target_table") or "").strip()
        payload=rec.get("payload")
        if table not in AI_ALLOWED_TABLES or not isinstance(payload,dict):
            rejected+=1
            continue

        natural_key=_record_key(payload,rec.get("natural_key") or "")
        try:
            payload=_simple_prepare_payload(sb,table,payload,natural_key)
            payload=_fill_staging_key(payload,table,natural_key)
        except Exception as exc:
            errors.append({"table":table,"natural_key":natural_key,"error":str(exc)})
            rejected+=1
            continue

        meta=meta_map.get(table) or {}
        logical=meta.get("entity_type")
        if not logical and table=="pc_event_links": logical="event_link"
        elif not logical and table=="pc_relationships": logical="relationship"

        conflict=APPLY_CONFLICT_KEYS.get(table)
        conflict_keys=[x.strip() for x in conflict.split(",")] if conflict else []
        key_ready=not conflict_keys or all(payload.get(k) not in (None,"") for k in conflict_keys)

        staged.append({
            "ingestion_job_id":job_id,
            "target_entity_type":logical or "domain_record",
            "target_table":table,
            "source_record_key":natural_key,
            "natural_key":natural_key,
            "action":"UPSERT",
            "payload":_jsonable(payload),
            "confidence":rec.get("confidence"),
            "validation_status":"pending" if key_ready else "needs_review",
            "review_status":"pending",
            "resolution_status":"READY" if key_ready else "UNRESOLVED",
            "resolution_method":"simple_key_first" if key_ready else "missing_required_key",
        })

    for i in range(0,len(staged),100):
        sb.table("pc_staged_records").insert(staged[i:i+100]).execute()

    return len(staged),rejected,{
        "mode":"simple_key_first",
        "ready":sum(1 for x in staged if x.get("resolution_status")=="READY"),
        "unresolved":sum(1 for x in staged if x.get("resolution_status")!="READY"),
        "dependency_autocreate":True,
        "errors":errors[:100],
    }


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

        "pc_port_capabilities":32,
        "pc_port_metrics":34,
        "pc_terminal_details":34,
        "pc_berth_details":36,
        "pc_transport_services":35,
        "pc_port_calls":58,
        "pc_transactions":40,
        "pc_financing_facilities":40,
        "pc_contracts":40,
        "pc_vessel_designs":40,
        "pc_shipbuilding_orders":45,
        "pc_transport_routes":45,
        "pc_project_details":45,

        "pc_transaction_participants":50,
        "pc_financing_participants":50,
        "pc_contract_participants":50,
        "pc_shipbuilding_order_units":50,
        "pc_transport_service_aliases":50,
        "pc_transport_service_operators":50,
        "pc_transport_service_stops":52,
        "pc_transport_service_schedules":52,
        "pc_transport_service_transit_times":54,
        "pc_transport_service_mobile_assets":54,
        "pc_transport_service_network_links":55,
        "pc_transport_service_connections":55,
        "pc_transport_service_sources":56,
        "pc_transport_service_changes":58,
        "pc_financing_links":60,
        "pc_contract_links":60,

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
        "pc_transport_services":["transport_service_id","service_name","service_code","mode","service_type","trade_lane","status","announced_date","effective_start","effective_end","primary_operator_entity_id","source_id","source_url"],
        "pc_financing_facilities":["financing_id","financing_name","financing_type","announced_date","amount","currency","programme_name","facility_status","source_id","source_url","primary_source_url"],
        "pc_contracts":["contract_id","contract_name","contract_type","announced_date","status","reported_value","currency","quantity","quantity_unit","source_id","source_url","primary_source_url"],
        "pc_vessel_designs":["vessel_design_id","design_name","designer_entity_id","builder_entity_id","vessel_type","teu_capacity","dwt","loa_m","beam_m","depth_m","draft_m","design_speed_knots","source_id","source_url"],
        "pc_shipbuilding_orders":["shipbuilding_order_id","contract_id","buyer_entity_id","builder_entity_id","shipyard_asset_id","vessel_design_id","order_date","announced_date","firm_quantity","option_quantity","vessel_type","teu_capacity_each","status","source_id","source_url","primary_source_url"],
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
    "pc_transaction_participants",
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

# Internal staging-only targets. They deliberately bypass SQL V5 object resolution
# because they are child/fact/semantic bridge rows, not canonical identity objects.
MODEL_DIRECT_PARTICIPANT_TARGET = "pc__direct_transaction_participant"
MODEL_EVENT_TRANSACTION_BRIDGE_TARGET = "pc__event_transaction_bridge"

# V19: graph/child rows are deliberately NOT exposed to SQL V5 until all
# canonical parent objects have been resolved. They are staged/applied afterwards
# by the Python dependency engine using a package-local -> canonical ID map.
CANONICAL_DEFERRED_TABLES = {
    "pc_relationships",
    "pc_event_links",
    "pc_transaction_participants",
}

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


CORE_CANONICAL_STAGE_TYPES = {
    "pc_entities":"entity",
    "pc_assets":"asset",
    "pc_mobile_assets":"mobile_asset",
    "pc_events":"event",
    "pc_relationships":"relationship",
    "pc_event_links":"event_link",
}

def _canonical_registered_table_map():
    """Return target_table -> metadata row where available.

    Core canonical tables use the established FK-safe entity_type values above.
    Optional tables still require explicit metadata registration.
    """
    rows=_meta_entity_types(sb) if sb else []
    reg={
        str(r.get("table_name")):r
        for r in rows
        if r.get("table_name") and r.get("entity_type")
    }
    for table_name,entity_type in CORE_CANONICAL_STAGE_TYPES.items():
        reg.setdefault(table_name,{
            "table_name":table_name,
            "entity_type":entity_type,
            "_core_builtin":True,
        })
    return reg

def _canonical_registered_tables():
    reg=_canonical_registered_table_map()
    # Keep stable user-facing order. Core identity/edge tables require metadata-backed
    # logical types, while direct child/fact tables may be staged with target_entity_type=NULL.
    # pc_transaction_participants is deliberately direct: it FK-links to pc_transactions
    # and pc_entities but is not itself a canonical entity type.
    return [
        t for t in CANONICAL_LOAD_TABLES
        if t in reg or t in CANONICAL_DIRECT_TABLES
    ]

def _canonical_target_entity_type(target_table):
    if target_table in CORE_CANONICAL_STAGE_TYPES:
        return CORE_CANONICAL_STAGE_TYPES[target_table]
    row=_canonical_registered_table_map().get(target_table)
    return (row or {}).get("entity_type")


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
        display_table=r.get("target_table") or "unknown"
        if display_table==MODEL_DIRECT_PARTICIPANT_TARGET:
            display_table="pc_transaction_participants"
        elif display_table==MODEL_EVENT_TRANSACTION_BRIDGE_TARGET:
            display_table="pc_event_links"
        key=(display_table,
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


def _norm_vocab_token(value):
    return re.sub(r"[^a-z0-9]+","_",str(value or "").strip().casefold()).strip("_")


def _ensure_transaction_role_vocab():
    """Ensure baseline transaction participant roles exist and verify them.

    These are controlled metadata rows required by the live FK from
    pc_transaction_participants.role. They are model vocabulary, not business data.
    """
    defaults=[
        {"role":"buyer","display_name":"Buyer / Acquirer","role_group":"acquirer","description":"Purchasing or acquiring party","active":True},
        {"role":"seller","display_name":"Seller / Disposing Party","role_group":"seller","description":"Selling or disposing party","active":True},
        {"role":"target","display_name":"Target","role_group":"target","description":"Company, asset or business that is the subject of the transaction","active":True},
        {"role":"offeror","display_name":"Offeror","role_group":"acquirer","description":"Party making a tender or takeover offer","active":True},
        {"role":"shareholder","display_name":"Shareholder","role_group":"shareholder","description":"Shareholder participating in or affected by the transaction","active":True},
        {"role":"sponsor","display_name":"Sponsor / Parent","role_group":"sponsor","description":"Parent, sponsor or controlling party backing the transaction","active":True},
        {"role":"advisor","display_name":"Advisor","role_group":"advisor","description":"Financial, legal or other transaction advisor","active":True},
        {"role":"financier","display_name":"Financier","role_group":"financier","description":"Debt or equity financing provider","active":True},
    ]
    result={"attempted":len(defaults),"verified":[],"errors":[]}
    for row in defaults:
        try:
            existing=(sb.table("pc_meta_transaction_participant_roles")
                      .select("role").eq("role",row["role"]).limit(1).execute().data or [])
            if not existing:
                sb.table("pc_meta_transaction_participant_roles").insert(
                    {**row,"metadata":{"system_baseline":True,"installed_by":"canonical_loader_v17"}}
                ).execute()
            check=(sb.table("pc_meta_transaction_participant_roles")
                   .select("role").eq("role",row["role"]).limit(1).execute().data or [])
            if check:
                result["verified"].append(row["role"])
            else:
                result["errors"].append(f"{row['role']}: insert returned no readable row")
        except Exception as exc:
            result["errors"].append(f"{row['role']}: {exc}")
    return result


def _load_transaction_vocab():
    """Read the live transaction vocabularies from the model.

    The loader should conform incoming packages to the database model, not require
    spreadsheet authors to know internal enum keys.
    """
    role_install=_ensure_transaction_role_vocab()
    vocab={"types":[],"stages":[],"roles":[],"categories":[],"role_install":role_install}
    try:
        vocab["types"]=(sb.table("pc_meta_transaction_types")
            .select("transaction_type,transaction_category,display_name,active")
            .eq("active",True).limit(1000).execute().data or [])
    except Exception:
        pass
    try:
        vocab["stages"]=(sb.table("pc_meta_transaction_stages")
            .select("transaction_stage,display_name,stage_order,active")
            .eq("active",True).limit(1000).execute().data or [])
    except Exception:
        pass
    try:
        vocab["roles"]=(sb.table("pc_meta_transaction_participant_roles")
            .select("*").limit(1000).execute().data or [])
    except Exception:
        pass
    try:
        vocab["categories"]=(sb.table("pc_meta_transaction_categories")
            .select("transaction_category,display_name,active")
            .eq("active",True).limit(1000).execute().data or [])
    except Exception:
        pass
    return vocab


def _vocab_match(value, rows, key_field, display_field="display_name"):
    if value in (None,""):
        return None
    wanted=_norm_vocab_token(value)
    for r in rows or []:
        key=r.get(key_field)
        if key and _norm_vocab_token(key)==wanted:
            return key
        disp=r.get(display_field)
        if disp and _norm_vocab_token(disp)==wanted:
            return key
    return None


def _normalize_transaction_payload_to_model(payload, vocab):
    """Normalize transaction controlled fields against live metadata.

    Unsupported optional vocabulary values are preserved in metadata and omitted
    from constrained columns rather than causing the entire canonical package to fail.
    """
    p=dict(payload or {})
    meta=p.get("metadata") if isinstance(p.get("metadata"),dict) else {}
    meta=dict(meta)

    raw_type=p.get("transaction_type")
    raw_cat=p.get("transaction_category")
    raw_stage=p.get("transaction_stage")

    matched_type=_vocab_match(raw_type,vocab.get("types"),"transaction_type")
    type_row=None
    if matched_type:
        type_row=next((r for r in vocab.get("types",[]) if r.get("transaction_type")==matched_type),None)
        p["transaction_type"]=matched_type
        if type_row and type_row.get("transaction_category"):
            p["transaction_category"]=type_row["transaction_category"]
    elif raw_type not in (None,""):
        meta["source_transaction_type"]=raw_type
        p.pop("transaction_type",None)

    if not p.get("transaction_category") and raw_cat not in (None,""):
        matched_cat=_vocab_match(raw_cat,vocab.get("categories"),"transaction_category")
        if matched_cat:
            p["transaction_category"]=matched_cat
        else:
            meta["source_transaction_category"]=raw_cat
            p.pop("transaction_category",None)

    if raw_stage not in (None,""):
        matched_stage=_vocab_match(raw_stage,vocab.get("stages"),"transaction_stage")
        if matched_stage:
            p["transaction_stage"]=matched_stage
        else:
            meta["source_transaction_stage"]=raw_stage
            p.pop("transaction_stage",None)

    if meta:
        p["metadata"]=meta
    return p


def _participant_role_to_model(role, vocab):
    """Resolve a package role to the live FK-controlled role vocabulary."""
    if role in (None,""):
        return None
    wanted=_norm_vocab_token(role)
    rows=vocab.get("roles") or []

    # Exact key/display match.
    for r in rows:
        key=r.get("role")
        if key and _norm_vocab_token(key)==wanted:
            return key
        for fld in ("display_name","role_display","description"):
            if r.get(fld) and _norm_vocab_token(r.get(fld))==wanted:
                return key

    aliases={
        "buyer_offeror":["buyer","offeror","acquirer"],
        "offeror":["offeror","buyer","acquirer"],
        "acquirer":["buyer","acquirer","offeror"],
        "seller_tendering_shareholders":["seller","shareholder"],
        "tendering_shareholders":["seller","shareholder"],
        "target_company":["target"],
        "ultimate_parent_sponsor":["sponsor"],
    }

    # Match aliases to either role key OR role_group in the live metadata.
    candidates=[wanted] + aliases.get(wanted,[])
    for candidate in candidates:
        cn=_norm_vocab_token(candidate)
        for r in rows:
            if _norm_vocab_token(r.get("role"))==cn or _norm_vocab_token(r.get("role_group"))==cn:
                return r.get("role")

    # Last safe fallback for the three universal deal roles:
    # ensure the FK row directly, then return it.
    if wanted in {"buyer","seller","target","offeror","shareholder","sponsor","advisor","financier"}:
        defaults={
            "buyer":("Buyer / Acquirer","acquirer"),
            "seller":("Seller / Disposing Party","seller"),
            "target":("Target","target"),
            "offeror":("Offeror","acquirer"),
            "shareholder":("Shareholder","shareholder"),
            "sponsor":("Sponsor / Parent","sponsor"),
            "advisor":("Advisor","advisor"),
            "financier":("Financier","financier"),
        }
        display,group=defaults[wanted]
        try:
            sb.table("pc_meta_transaction_participant_roles").upsert({
                "role":wanted,
                "display_name":display,
                "role_group":group,
                "description":f"Canonical transaction participant role: {display}",
                "active":True,
                "metadata":{"system_baseline":True,"installed_by":"canonical_loader_v17"},
            },on_conflict="role").execute()
            check=(sb.table("pc_meta_transaction_participant_roles")
                   .select("role").eq("role",wanted).limit(1).execute().data or [])
            if check:
                return wanted
        except Exception:
            pass
    return None


def _canonical_apply_model_direct_rows(job_id):
    """Model-aware pre-apply for direct transaction-family tables.

    This is deliberately based on the live schema/model:
      * pc_transactions is a direct fact table with only transaction_id required.
      * transaction type/category/stage are nullable FK-controlled vocabularies.
      * pc_transaction_participants is a child table FK-linked to pc_transactions,
        optional pc_entities, role metadata and pc_sources.

    Parents are written before children. SQL V5 remains responsible for canonical
    identity objects and supported graph edges.
    """
    report={
        "transactions_applied":0,
        "participants_applied":0,
        "participants_review":0,
        "errors":[]
    }
    try:
        rows=(sb.table("pc_staged_records")
              .select("staged_record_id,target_table,payload,review_status,resolution_status,natural_key")
              .eq("ingestion_job_id",str(job_id))
              .limit(10000).execute().data or [])
    except Exception as exc:
        report["errors"].append(f"staging read: {exc}")
        return report

    vocab=_load_transaction_vocab()
    for err in (vocab.get("role_install") or {}).get("errors",[]):
        report["errors"].append(f"role metadata install: {err}")

    def mark_applied(row,payload,method):
        details={"canonical_target_table":"pc_transaction_participants"} if row.get("target_table")==MODEL_DIRECT_PARTICIPANT_TARGET else {}
        sb.table("pc_staged_records").update({
            "payload":payload,
            "review_status":"applied",
            "validation_status":"reviewed",
            "resolution_status":"READY",
            "resolution_method":method,
            "resolution_confidence":1.0,
            "candidate_count":1,
            "resolution_details":details,
        }).eq("staged_record_id",row["staged_record_id"]).execute()

    def mark_review(row,reason,method):
        try:
            sb.table("pc_staged_records").update({
                "review_status":"pending",
                "validation_status":"needs_review",
                "resolution_status":"BROKEN_REFERENCE",
                "resolution_method":method,
                "resolution_details":{"reason":str(reason)[:1500],"handler":method},
            }).eq("staged_record_id",row["staged_record_id"]).execute()
        except Exception:
            pass
        report["errors"].append(f"{row.get('natural_key')}: {reason}")

    # 1. Direct parent transactions first.
    for row in rows:
        if row.get("target_table")!="pc_transactions":
            continue
        payload=row.get("payload") if isinstance(row.get("payload"),dict) else {}
        txid=payload.get("transaction_id")
        if not txid:
            mark_review(row,"transaction_id is required","model_direct_transaction_guard")
            continue

        p=_normalize_transaction_payload_to_model(payload,vocab)

        # Drop unresolved optional FK ids rather than blocking a source-backed transaction.
        # Preserve them in metadata so they can be reconciled later.
        meta=p.get("metadata") if isinstance(p.get("metadata"),dict) else {}
        meta=dict(meta)
        for fld,table,col in (
            ("buyer_entity_id","pc_entities","entity_id"),
            ("seller_entity_id","pc_entities","entity_id"),
            ("target_entity_id","pc_entities","entity_id"),
            ("target_asset_id","pc_assets","asset_id"),
            ("target_mobile_asset_id","pc_mobile_assets","mobile_asset_id"),
            ("source_id","pc_sources","source_id"),
        ):
            val=p.get(fld)
            if val in (None,""):
                continue
            try:
                hit=(sb.table(table).select(col).eq(col,val).limit(1).execute().data or [])
            except Exception:
                hit=[]
            if not hit:
                meta[f"unresolved_{fld}"]=val
                p.pop(fld,None)
        p["metadata"]=meta

        try:
            sb.table("pc_transactions").upsert(p,on_conflict="transaction_id").execute()
            mark_applied(row,p,"model_direct_transaction_upsert")
            report["transactions_applied"]+=1
        except Exception as exc:
            mark_review(row,f"transaction upsert failed: {exc}","model_direct_transaction_guard")

    # 2. Child participants after parent transactions exist.
    for row in rows:
        if row.get("target_table") not in {"pc_transaction_participants",MODEL_DIRECT_PARTICIPANT_TARGET}:
            continue
        payload=row.get("payload") if isinstance(row.get("payload"),dict) else {}
        p=dict(payload)
        pid=p.get("participant_id")
        txid=p.get("transaction_id")
        if not pid:
            mark_review(row,"participant_id is required","model_transaction_participant_guard")
            report["participants_review"]+=1
            continue
        if not txid:
            mark_review(row,"transaction_id is required","model_transaction_participant_guard")
            report["participants_review"]+=1
            continue

        try:
            txhit=(sb.table("pc_transactions").select("transaction_id")
                   .eq("transaction_id",txid).limit(1).execute().data or [])
        except Exception:
            txhit=[]
        if not txhit:
            mark_review(row,f"transaction_id {txid!r} does not resolve after parent apply",
                        "model_transaction_participant_guard")
            report["participants_review"]+=1
            continue

        role=_participant_role_to_model(p.get("role"),vocab)
        if not role:
            live_roles=[
                {"role":r.get("role"),"display_name":r.get("display_name"),"role_group":r.get("role_group")}
                for r in (vocab.get("roles") or [])
            ]
            install_errors=(vocab.get("role_install") or {}).get("errors",[])
            mark_review(
                row,
                f"participant role {p.get('role')!r} cannot resolve. "
                f"Live roles={live_roles}. Role-install errors={install_errors}",
                "model_transaction_participant_guard"
            )
            report["participants_review"]+=1
            continue
        p["role"]=role

        # Optional entity FK. Unresolved named participants are allowed by the schema.
        eid=p.get("entity_id")
        if eid not in (None,""):
            try:
                ehit=(sb.table("pc_entities").select("entity_id")
                      .eq("entity_id",eid).limit(1).execute().data or [])
            except Exception:
                ehit=[]
            if not ehit:
                meta=p.get("metadata") if isinstance(p.get("metadata"),dict) else {}
                meta=dict(meta)
                meta["unresolved_entity_id"]=eid
                p["metadata"]=meta
                p.pop("entity_id",None)

        # Source FK is optional. Keep provenance URLs in metadata if source_id is absent.
        sid=p.get("source_id")
        if sid not in (None,""):
            try:
                shit=(sb.table("pc_sources").select("source_id")
                      .eq("source_id",sid).limit(1).execute().data or [])
            except Exception:
                shit=[]
            if not shit:
                meta=p.get("metadata") if isinstance(p.get("metadata"),dict) else {}
                meta=dict(meta); meta["unresolved_source_id"]=sid
                p["metadata"]=meta
                p.pop("source_id",None)

        try:
            sb.table("pc_transaction_participants").upsert(p,on_conflict="participant_id").execute()
            mark_applied(row,p,"model_transaction_participant_upsert")
            report["participants_applied"]+=1
        except Exception as exc:
            mark_review(row,f"participant upsert failed: {exc}",
                        "model_transaction_participant_guard")
            report["participants_review"]+=1

    return report


def _canonical_apply_model_post_rows(job_id):
    """Apply semantic links that the current SQL event-link processor cannot represent.

    pc_event_links is retained for supported canonical object types. Event↔transaction
    association is preserved bidirectionally in event/transaction metadata until the
    database gets a dedicated transaction-link table or transaction endpoint support.
    """
    report={"transaction_links_applied":0,"review":0,"errors":[]}
    try:
        rows=(sb.table("pc_staged_records")
              .select("staged_record_id,target_table,payload,review_status,resolution_status,natural_key")
              .eq("ingestion_job_id",str(job_id))
              .limit(10000).execute().data or [])
    except Exception as exc:
        report["errors"].append(f"event-link read: {exc}")
        return report

    def mark_review(row,reason):
        report["review"]+=1
        try:
            sb.table("pc_staged_records").update({
                "review_status":"pending",
                "validation_status":"needs_review",
                "resolution_status":"BROKEN_REFERENCE",
                "resolution_method":"model_event_transaction_bridge_guard",
                "resolution_details":{"reason":str(reason)[:1500]},
            }).eq("staged_record_id",row["staged_record_id"]).execute()
        except Exception:
            pass
        report["errors"].append(f"{row.get('natural_key')}: {reason}")

    for row in rows:
        payload=row.get("payload") if isinstance(row.get("payload"),dict) else {}
        if row.get("target_table") not in {"pc_event_links",MODEL_EVENT_TRANSACTION_BRIDGE_TARGET}:
            continue
        if str(payload.get("linked_type") or "").casefold() not in {"transaction","deal"}:
            continue
        if str(row.get("review_status") or "").lower()=="applied":
            continue

        eid=payload.get("event_id")
        txid=payload.get("linked_id")

        # First try canonical parents.
        try:
            evs=(sb.table("pc_events").select("event_id,metadata")
                 .eq("event_id",eid).limit(1).execute().data or [])
            txs=(sb.table("pc_transactions").select("transaction_id,metadata")
                 .eq("transaction_id",txid).limit(1).execute().data or [])
        except Exception as exc:
            evs=[]; txs=[]
            report["errors"].append(f"parent lookup initial: {exc}")

        # If either parent is not immediately visible, recover the exact parent payload
        # from this ingestion package and idempotently seed it.
        if not evs or not txs:
            try:
                pkg=(sb.table("pc_staged_records")
                     .select("target_table,payload")
                     .eq("ingestion_job_id",str(job_id))
                     .limit(10000).execute().data or [])
            except Exception:
                pkg=[]

            if not txs:
                tx_payload=next((
                    r.get("payload") for r in pkg
                    if r.get("target_table")=="pc_transactions"
                    and isinstance(r.get("payload"),dict)
                    and str(r["payload"].get("transaction_id") or "")==str(txid or "")
                ),None)
                if isinstance(tx_payload,dict):
                    try:
                        tx_payload=_normalize_transaction_payload_to_model(
                            tx_payload,_load_transaction_vocab()
                        )
                        sb.table("pc_transactions").upsert(
                            tx_payload,on_conflict="transaction_id"
                        ).execute()
                    except Exception as exc:
                        report["errors"].append(f"bridge transaction seed: {exc}")

            if not evs:
                ev_payload=next((
                    r.get("payload") for r in pkg
                    if r.get("target_table")=="pc_events"
                    and isinstance(r.get("payload"),dict)
                    and str(r["payload"].get("event_id") or "")==str(eid or "")
                ),None)
                if isinstance(ev_payload,dict):
                    try:
                        sb.table("pc_events").upsert(
                            ev_payload,on_conflict="event_id"
                        ).execute()
                    except Exception as exc:
                        report["errors"].append(f"bridge event seed: {exc}")

            try:
                evs=(sb.table("pc_events").select("event_id,metadata")
                     .eq("event_id",eid).limit(1).execute().data or [])
                txs=(sb.table("pc_transactions").select("transaction_id,metadata")
                     .eq("transaction_id",txid).limit(1).execute().data or [])
            except Exception as exc:
                mark_review(row,f"parent lookup failed after package recovery: {exc}")
                continue

        if not evs:
            mark_review(row,f"event_id {eid!r} is not canonical after package recovery")
            continue
        if not txs:
            mark_review(row,f"transaction_id {txid!r} is not canonical after package recovery")
            continue

        try:
            ev=evs[0]; tx=txs[0]
            evm=ev.get("metadata") if isinstance(ev.get("metadata"),dict) else {}
            txm=tx.get("metadata") if isinstance(tx.get("metadata"),dict) else {}
            evm=dict(evm); txm=dict(txm)
            evlinks=evm.get("linked_transaction_ids") if isinstance(evm.get("linked_transaction_ids"),list) else []
            txlinks=txm.get("linked_event_ids") if isinstance(txm.get("linked_event_ids"),list) else []
            if txid not in evlinks: evlinks.append(txid)
            if eid not in txlinks: txlinks.append(eid)
            evm["linked_transaction_ids"]=evlinks
            txm["linked_event_ids"]=txlinks
            evm["transaction_link_method"]="canonical_metadata_bridge"
            txm["event_link_method"]="canonical_metadata_bridge"
            sb.table("pc_events").update({"metadata":evm}).eq("event_id",eid).execute()
            sb.table("pc_transactions").update({"metadata":txm}).eq("transaction_id",txid).execute()
            sb.table("pc_staged_records").update({
                "review_status":"applied",
                "validation_status":"reviewed",
                "resolution_status":"READY",
                "resolution_method":"model_event_transaction_metadata_bridge",
                "resolution_confidence":1.0,
                "candidate_count":1,
                "resolution_details":{
                    "event_id":eid,
                    "transaction_id":txid,
                    "note":"semantic bridge stored in parent metadata; pc_event_links transaction endpoint unsupported",
                    "canonical_target_table":"pc_event_links"
                },
            }).eq("staged_record_id",row["staged_record_id"]).execute()
            report["transaction_links_applied"]+=1
        except Exception as exc:
            mark_review(row,f"event→transaction bridge failed: {exc}")

    return report



def _canonical_finalize_existing_rows(job_id):
    """ALREADY_EXISTS is a successful idempotent outcome, not analyst review."""
    report={"applied_existing":0,"errors":[]}
    try:
        rows=(sb.table("pc_staged_records")
              .select("staged_record_id,resolution_status,review_status,target_table,resolved_entity_id,resolution_method,resolution_details")
              .eq("ingestion_job_id",str(job_id))
              .limit(10000).execute().data or [])
    except Exception as exc:
        report["errors"].append(str(exc))
        return report

    for row in rows:
        if str(row.get("resolution_status") or "").upper()!="ALREADY_EXISTS":
            continue
        if str(row.get("review_status") or "").lower()=="applied":
            continue
        try:
            details=row.get("resolution_details") if isinstance(row.get("resolution_details"),dict) else {}
            details=dict(details)
            details["idempotent_existing"]=True
            sb.table("pc_staged_records").update({
                "review_status":"applied",
                "validation_status":"reviewed",
                "resolution_details":details,
            }).eq("staged_record_id",row["staged_record_id"]).execute()
            report["applied_existing"]+=1
        except Exception as exc:
            report["errors"].append(f"{row.get('staged_record_id')}: {exc}")
    return report



def _canonical_object_spec(object_type):
    kind=str(object_type or "").casefold()
    aliases={
        "company":"entity","organisation":"entity","organization":"entity",
        "vessel":"mobile_asset","ship":"mobile_asset","aircraft":"mobile_asset",
        "transport_route":"route","corridor":"route","network":"route",
        "deal":"transaction",
    }
    kind=aliases.get(kind,kind)
    return {
        "entity":("pc_entities","entity_id"),
        "asset":("pc_assets","asset_id"),
        "mobile_asset":("pc_mobile_assets","mobile_asset_id"),
        "event":("pc_events","event_id"),
        "route":("pc_transport_routes","route_id"),
        "transaction":("pc_transactions","transaction_id"),
    }.get(kind)


def _canonical_row_exists(object_type, object_id):
    spec=_canonical_object_spec(object_type)
    if not spec or object_id in (None,""):
        return False
    table,key=spec
    try:
        return bool((sb.table(table).select(key).eq(key,object_id).limit(1).execute().data or []))
    except Exception:
        return False


def _resolve_package_object_id(target_table,payload,resolved_id=None):
    """Return the canonical ID for one staged package object.

    Strong-key rules:
      mobile asset -> IMO first
      entity       -> resolver result, then exact canonical ID, then unique exact name
      asset/event  -> resolver result, then exact canonical ID
      transaction  -> exact transaction_id
    """
    payload=payload if isinstance(payload,dict) else {}
    if resolved_id not in (None,""):
        return str(resolved_id)

    if target_table=="pc_mobile_assets":
        imo=str(payload.get("imo") or "").strip()
        if imo:
            try:
                hits=(sb.table("pc_mobile_assets").select("mobile_asset_id,imo")
                      .eq("imo",imo).limit(3).execute().data or [])
                if len(hits)==1:
                    return str(hits[0]["mobile_asset_id"])
            except Exception:
                pass
        mid=payload.get("mobile_asset_id")
        if mid and _canonical_row_exists("mobile_asset",mid):
            return str(mid)

    elif target_table=="pc_entities":
        eid=payload.get("entity_id")
        if eid and _canonical_row_exists("entity",eid):
            return str(eid)
        name=str(payload.get("name") or "").strip()
        if name:
            try:
                hits=(sb.table("pc_entities").select("entity_id,name")
                      .eq("name",name).limit(3).execute().data or [])
                if len(hits)==1:
                    return str(hits[0]["entity_id"])
            except Exception:
                pass

    elif target_table=="pc_assets":
        aid=payload.get("asset_id")
        if aid and _canonical_row_exists("asset",aid):
            return str(aid)

    elif target_table=="pc_events":
        eid=payload.get("event_id")
        if eid and _canonical_row_exists("event",eid):
            return str(eid)

    elif target_table=="pc_transport_routes":
        rid=payload.get("route_id")
        if rid and _canonical_row_exists("route",rid):
            return str(rid)
        name=str(payload.get("route_name") or payload.get("name") or "").strip()
        if name:
            try:
                hits=(sb.table("pc_transport_routes").select("route_id,route_name")
                      .eq("route_name",name).limit(3).execute().data or [])
                if len(hits)==1:
                    return str(hits[0]["route_id"])
            except Exception:
                pass

    elif target_table=="pc_transactions":
        tid=payload.get("transaction_id")
        if tid and _canonical_row_exists("transaction",tid):
            return str(tid)

    return None


def _build_package_id_map(job_id):
    """Map every package-local object ID to the final canonical ID."""
    mapping={}
    diagnostics=[]
    try:
        rows=(sb.table("pc_staged_records")
              .select("target_table,payload,resolved_entity_id,resolution_status,review_status,natural_key")
              .eq("ingestion_job_id",str(job_id))
              .limit(10000).execute().data or [])
    except Exception as exc:
        return {},[f"staging map read failed: {exc}"]

    id_field={
        "pc_entities":"entity_id",
        "pc_assets":"asset_id",
        "pc_mobile_assets":"mobile_asset_id",
        "pc_events":"event_id",
        "pc_transport_routes":"route_id",
        "pc_transactions":"transaction_id",
    }
    for r in rows:
        table=r.get("target_table")
        field=id_field.get(table)
        if not field:
            continue
        payload=r.get("payload") if isinstance(r.get("payload"),dict) else {}
        local_id=payload.get(field)
        canonical=_resolve_package_object_id(table,payload,r.get("resolved_entity_id"))
        if local_id and canonical:
            mapping[str(local_id)]=str(canonical)
            mapping[str(canonical)]=str(canonical)
        elif local_id:
            diagnostics.append(
                f"{table} {local_id}: no canonical ID after object phase "
                f"(resolution={r.get('resolution_status')}, review={r.get('review_status')})"
            )
    return mapping,diagnostics


def _ensure_relationship_metadata_type(relationship_type, source_type, target_type):
    """Ensure graph semantics used by a package are visible to the model registry."""
    if not relationship_type:
        return
    try:
        hit=(sb.table("pc_meta_relationship_types").select("relationship_type")
             .eq("relationship_type",relationship_type).limit(1).execute().data or [])
        if hit:
            return
    except Exception:
        return
    try:
        sb.table("pc_meta_relationship_types").insert({
            "relationship_type":relationship_type,
            "from_entity_type":source_type or "entity",
            "to_entity_type":target_type or "entity",
            "relationship_table":"pc_relationships",
            "from_key_column":"source_id",
            "to_key_column":"target_id",
            "relationship_type_column":"relationship_type",
            "cardinality":"many_to_many",
            "active":True,
            "description":f"Canonical graph relationship: {relationship_type}",
            "metadata":{"installed_by":"canonical_loader_v19","system_baseline":True},
        }).execute()
    except Exception:
        # pc_relationships itself does not FK relationship_type to this registry;
        # registry enrichment must never block a valid canonical graph edge.
        pass


def _canonical_semantic_relationship_id(payload):
    src_type=str(payload.get("source_type") or "")
    src_id=str(payload.get("source_id") or "")
    rel=str(payload.get("relationship_type") or "")
    tgt_type=str(payload.get("target_type") or "")
    tgt_id=str(payload.get("target_id") or "")
    digest=hashlib.sha256(
        f"{src_type}|{src_id}|{rel}|{tgt_type}|{tgt_id}".encode("utf-8")
    ).hexdigest().upper()[:24]
    return "REL_"+digest


def _stage_one_deferred(row):
    clean=dict(row)
    clean.pop("target_entity_type",None)
    data=(sb.table("pc_staged_records").insert(_jsonable(clean)).execute().data or [])
    return data[0] if data else clean


def _mark_deferred_applied(staged_record_id, method, details=None, resolved_id=None):
    upd={
        "review_status":"applied",
        "validation_status":"reviewed",
        "resolution_status":"READY",
        "resolution_method":method,
        "resolution_confidence":1.0,
        "candidate_count":1,
        "resolution_details":details or {},
    }
    if resolved_id not in (None,""):
        upd["resolved_entity_id"]=str(resolved_id)
    sb.table("pc_staged_records").update(upd).eq(
        "staged_record_id",staged_record_id
    ).execute()


def _mark_deferred_review(staged_record_id, method, reason, details=None):
    d=dict(details or {})
    d["reason"]=str(reason)[:1800]
    sb.table("pc_staged_records").update({
        "review_status":"pending",
        "validation_status":"needs_review",
        "resolution_status":"BROKEN_REFERENCE",
        "resolution_method":method,
        "resolution_details":d,
    }).eq("staged_record_id",staged_record_id).execute()





def _v31_resolve_parent_stage_row(r):
    """Resolve one staged parent/object row even if resolved_entity_id is blank.

    This is deliberately independent of prior loader status. It derives the canonical
    endpoint from the staged payload itself: entity name/alias, asset name+country,
    vessel IMO/name, route name, or event ID.
    """
    table=str(r.get("target_table") or "").strip()
    p=r.get("payload") if isinstance(r.get("payload"),dict) else {}
    existing=str(r.get("resolved_entity_id") or "").strip()
    if existing:
        return existing

    try:
        if table=="pc_entities":
            eid=str(p.get("entity_id") or "").strip()
            if eid:
                hit=(sb.table("pc_entities").select("entity_id").eq("entity_id",eid).limit(1).execute().data or [])
                if hit: return str(hit[0]["entity_id"])
            name=str(p.get("name") or "").strip()
            if name:
                idx=_canonical_entity_index()
                hits=idx.get(_canon_name_key(name),[])
                if len(hits)==1:
                    return str(hits[0]["entity_id"])

        elif table=="pc_assets":
            aid=str(p.get("asset_id") or "").strip()
            if aid:
                hit=(sb.table("pc_assets").select("asset_id").eq("asset_id",aid).limit(1).execute().data or [])
                if hit: return str(hit[0]["asset_id"])
            name=str(p.get("name") or "").strip()
            country=str(p.get("country") or "").strip()
            if name:
                q=sb.table("pc_assets").select("asset_id,name,country").eq("name",name).limit(20)
                hits=(q.execute().data or [])
                if country:
                    narrowed=[h for h in hits if str(h.get("country") or "").strip().casefold()==country.casefold()]
                    if narrowed: hits=narrowed
                ids={str(h.get("asset_id") or ""):h for h in hits if h.get("asset_id")}
                if len(ids)==1:
                    return next(iter(ids))

        elif table=="pc_mobile_assets":
            mid=str(p.get("mobile_asset_id") or "").strip()
            if mid:
                hit=(sb.table("pc_mobile_assets").select("mobile_asset_id").eq("mobile_asset_id",mid).limit(1).execute().data or [])
                if hit: return str(hit[0]["mobile_asset_id"])
            imo=str(p.get("imo") or "").strip()
            if imo:
                hits=(sb.table("pc_mobile_assets").select("mobile_asset_id,imo,name").eq("imo",imo).limit(2).execute().data or [])
                if len(hits)==1: return str(hits[0]["mobile_asset_id"])
            name=str(p.get("name") or "").strip()
            if name:
                hits=(sb.table("pc_mobile_assets").select("mobile_asset_id,name").eq("name",name).limit(3).execute().data or [])
                ids={str(h.get("mobile_asset_id") or ""):h for h in hits if h.get("mobile_asset_id")}
                if len(ids)==1: return next(iter(ids))

        elif table=="pc_transport_routes":
            rid=str(p.get("route_id") or "").strip()
            if rid:
                hit=(sb.table("pc_transport_routes").select("route_id").eq("route_id",rid).limit(1).execute().data or [])
                if hit: return str(hit[0]["route_id"])
            name=str(p.get("route_name") or "").strip()
            if name:
                hits=(sb.table("pc_transport_routes").select("route_id,route_name").eq("route_name",name).limit(3).execute().data or [])
                ids={str(h.get("route_id") or ""):h for h in hits if h.get("route_id")}
                if len(ids)==1: return next(iter(ids))

        elif table=="pc_events":
            eid=str(p.get("event_id") or "").strip()
            if eid:
                hit=(sb.table("pc_events").select("event_id").eq("event_id",eid).limit(1).execute().data or [])
                if hit: return str(hit[0]["event_id"])
    except Exception:
        return None
    return None


def _v31_package_local_endpoint_map(job_id):
    """Reconstruct package-local/source ID -> live canonical ID from staged parents.

    Unlike V29 this works even if the earlier processor applied/created the parent
    but never wrote resolved_entity_id back to the staged row.
    """
    mapping={}
    try:
        rows=(sb.table("pc_staged_records")
              .select("staged_record_id,target_table,source_record_key,natural_key,payload,resolved_entity_id,review_status,resolution_status")
              .eq("ingestion_job_id",str(job_id))
              .in_("target_table",["pc_entities","pc_assets","pc_mobile_assets","pc_events","pc_transport_routes"])
              .limit(30000).execute().data or [])
    except Exception:
        return mapping

    id_fields={
        "pc_entities":"entity_id",
        "pc_assets":"asset_id",
        "pc_mobile_assets":"mobile_asset_id",
        "pc_events":"event_id",
        "pc_transport_routes":"route_id",
    }

    for r in rows:
        canonical=_v31_resolve_parent_stage_row(r)
        if not canonical:
            continue
        table=str(r.get("target_table") or "")
        p=r.get("payload") if isinstance(r.get("payload"),dict) else {}
        md=p.get("metadata") if isinstance(p.get("metadata"),dict) else {}
        candidates=[
            r.get("source_record_key"), r.get("natural_key"),
            p.get(id_fields.get(table,"")) if id_fields.get(table) else None,
            md.get("package_local_entity_id"), md.get("package_local_asset_id"),
            md.get("package_local_mobile_asset_id"), md.get("package_local_route_id"),
        ]
        for c in candidates:
            c=str(c or "").strip()
            if c:
                mapping[c]=canonical

        # Heal the staged parent row so subsequent retries become trivial.
        try:
            sb.table("pc_staged_records").update({
                "resolved_entity_id":canonical
            }).eq("staged_record_id",r["staged_record_id"]).execute()
        except Exception:
            pass
    return mapping


def _v29_unique_name_hit(table, id_col, name_col, name, country=None, extra_select=None):
    """Resolve an endpoint conservatively by exact human-readable name.

    Auto-resolve only when one canonical row remains. Country is used only as a
    narrowing hint when the target table exposes it.
    """
    name=str(name or "").strip()
    if not name:
        return None
    cols=[id_col,name_col]
    if country:
        cols.append("country")
    if extra_select:
        cols += list(extra_select)
    # preserve order while removing duplicates
    sel=",".join(dict.fromkeys(cols))
    hits=[]
    try:
        hits=(sb.table(table).select(sel).eq(name_col,name).limit(20).execute().data or [])
    except Exception:
        hits=[]
    if not hits:
        try:
            hits=(sb.table(table).select(sel).ilike(name_col,name).limit(20).execute().data or [])
        except Exception:
            hits=[]
    if country and hits:
        c=str(country).strip().casefold()
        narrowed=[
            h for h in hits
            if not h.get("country") or str(h.get("country")).strip().casefold()==c
        ]
        if narrowed:
            hits=narrowed
    # one distinct canonical ID only
    by_id={str(h.get(id_col) or ""):h for h in hits if h.get(id_col)}
    if len(by_id)==1:
        return next(iter(by_id.values()))
    return None


def _v29_resolve_graph_endpoint(job_id, endpoint_type, endpoint_id, endpoint_name=None, metadata=None):
    """Resolve entity/asset/mobile asset/route/event endpoint to a canonical ID."""
    et=str(endpoint_type or "").strip().casefold()
    raw_id=str(endpoint_id or "").strip()
    name=str(endpoint_name or "").strip()
    metadata=metadata if isinstance(metadata,dict) else {}

    # 1) package-local -> canonical map from this exact ingestion job.
    local_map=_v31_package_local_endpoint_map(job_id)
    mapped=local_map.get(raw_id)
    if mapped:
        return mapped, "package_local_map", name

    try:
        if et in {"mobile_asset","vessel","ship","aircraft"}:
            if raw_id:
                hit=(sb.table("pc_mobile_assets")
                     .select("mobile_asset_id,imo,name")
                     .eq("mobile_asset_id",raw_id).limit(1).execute().data or [])
                if hit:
                    return str(hit[0]["mobile_asset_id"]), "exact_id", name or str(hit[0].get("name") or "")
            imo=str(metadata.get("imo") or "").strip()
            if imo:
                hit=(sb.table("pc_mobile_assets")
                     .select("mobile_asset_id,imo,name")
                     .eq("imo",imo).limit(2).execute().data or [])
                if len(hit)==1:
                    return str(hit[0]["mobile_asset_id"]), "imo_exact", name or str(hit[0].get("name") or "")
            h=_v29_unique_name_hit("pc_mobile_assets","mobile_asset_id","name",name,extra_select=["imo"])
            if h:
                return str(h["mobile_asset_id"]), "unique_name", name or str(h.get("name") or "")

        elif et in {"entity","company","organisation","organization"}:
            if raw_id:
                hit=(sb.table("pc_entities").select("entity_id,name")
                     .eq("entity_id",raw_id).limit(1).execute().data or [])
                if hit:
                    return str(hit[0]["entity_id"]), "exact_id", name or str(hit[0].get("name") or "")
            h=_v29_unique_name_hit("pc_entities","entity_id","name",name)
            if h:
                return str(h["entity_id"]), "unique_name", name or str(h.get("name") or "")

        elif et in {"asset","port","terminal","facility","infrastructure"}:
            if raw_id:
                hit=(sb.table("pc_assets").select("asset_id,name,country")
                     .eq("asset_id",raw_id).limit(1).execute().data or [])
                if hit:
                    return str(hit[0]["asset_id"]), "exact_id", name or str(hit[0].get("name") or "")
            country=metadata.get("country") or metadata.get("linked_country")
            h=_v29_unique_name_hit("pc_assets","asset_id","name",name,country=country)
            if h:
                return str(h["asset_id"]), "unique_name", name or str(h.get("name") or "")

        elif et in {"route","transport_route","corridor","network"}:
            if raw_id:
                hit=(sb.table("pc_transport_routes").select("route_id,route_name")
                     .eq("route_id",raw_id).limit(1).execute().data or [])
                if hit:
                    return str(hit[0]["route_id"]), "exact_id", name or str(hit[0].get("route_name") or "")
            h=_v29_unique_name_hit("pc_transport_routes","route_id","route_name",name)
            if h:
                return str(h["route_id"]), "unique_name", name or str(h.get("route_name") or "")

        elif et=="event":
            if raw_id:
                hit=(sb.table("pc_events").select("event_id,title")
                     .eq("event_id",raw_id).limit(1).execute().data or [])
                if hit:
                    return str(hit[0]["event_id"]), "exact_id", name or str(hit[0].get("title") or "")
    except Exception:
        pass
    return None, "unresolved", name



def _v34_staged_parent_payload(job_id, endpoint_type, endpoint_id):
    """Find the staged parent row corresponding to a package-local graph endpoint."""
    et=str(endpoint_type or "").strip().casefold()
    table={
        "entity":"pc_entities","company":"pc_entities","organisation":"pc_entities","organization":"pc_entities",
        "asset":"pc_assets","port":"pc_assets","terminal":"pc_assets","facility":"pc_assets","infrastructure":"pc_assets",
        "mobile_asset":"pc_mobile_assets","vessel":"pc_mobile_assets","ship":"pc_mobile_assets","aircraft":"pc_mobile_assets",
        "route":"pc_transport_routes","transport_route":"pc_transport_routes","corridor":"pc_transport_routes","network":"pc_transport_routes",
        "event":"pc_events",
    }.get(et)
    if not table:
        return None
    id_field={
        "pc_entities":"entity_id","pc_assets":"asset_id","pc_mobile_assets":"mobile_asset_id",
        "pc_transport_routes":"route_id","pc_events":"event_id"
    }[table]
    try:
        rows=(sb.table("pc_staged_records")
              .select("staged_record_id,target_table,source_record_key,natural_key,payload,resolved_entity_id,review_status,resolution_status")
              .eq("ingestion_job_id",str(job_id))
              .eq("target_table",table)
              .limit(30000).execute().data or [])
    except Exception:
        return None
    raw=str(endpoint_id or "").strip()
    for r in rows:
        p=r.get("payload") if isinstance(r.get("payload"),dict) else {}
        candidates={
            str(r.get("source_record_key") or "").strip(),
            str(r.get("natural_key") or "").strip(),
            str(p.get(id_field) or "").strip(),
        }
        if raw and raw in candidates:
            return r
    return None


def _v34_resolve_graph_endpoint(job_id, endpoint_type, endpoint_id, endpoint_name=None, metadata=None):
    """V34 closure resolver: live canonical -> package map -> staged-parent payload -> unique name."""
    cid,method,name=_v29_resolve_graph_endpoint(
        job_id,endpoint_type,endpoint_id,endpoint_name,metadata
    )
    if cid:
        return cid,method,name

    staged=_v34_staged_parent_payload(job_id,endpoint_type,endpoint_id)
    if staged:
        canonical=_v31_resolve_parent_stage_row(staged)
        p=staged.get("payload") if isinstance(staged.get("payload"),dict) else {}
        display=(
            p.get("name") or p.get("route_name") or p.get("title") or
            endpoint_name or endpoint_id
        )
        if canonical:
            try:
                sb.table("pc_staged_records").update({
                    "resolved_entity_id":canonical
                }).eq("staged_record_id",staged["staged_record_id"]).execute()
            except Exception:
                pass
            return str(canonical),"staged_parent_closure",str(display or "")

        # Parent may have been canonicalized under another ID but staged row did not
        # capture it. Reuse the richer staged name for one final safe unique-name lookup.
        et=str(endpoint_type or "").strip().casefold()
        try:
            if et in {"entity","company","organisation","organization"}:
                h=_v29_unique_name_hit("pc_entities","entity_id","name",p.get("name"))
                if h: return str(h["entity_id"]),"staged_unique_name",str(h.get("name") or "")
            elif et in {"asset","port","terminal","facility","infrastructure"}:
                h=_v29_unique_name_hit("pc_assets","asset_id","name",p.get("name"),country=p.get("country"))
                if h: return str(h["asset_id"]),"staged_unique_name",str(h.get("name") or "")
            elif et in {"route","transport_route","corridor","network"}:
                h=_v29_unique_name_hit("pc_transport_routes","route_id","route_name",p.get("route_name"))
                if h: return str(h["route_id"]),"staged_unique_name",str(h.get("route_name") or "")
            elif et in {"mobile_asset","vessel","ship","aircraft"}:
                imo=str(p.get("imo") or "").strip()
                if imo:
                    hits=(sb.table("pc_mobile_assets").select("mobile_asset_id,name,imo").eq("imo",imo).limit(2).execute().data or [])
                    if len(hits)==1:
                        return str(hits[0]["mobile_asset_id"]),"staged_imo",str(hits[0].get("name") or "")
                h=_v29_unique_name_hit("pc_mobile_assets","mobile_asset_id","name",p.get("name"))
                if h: return str(h["mobile_asset_id"]),"staged_unique_name",str(h.get("name") or "")
        except Exception:
            pass
    return None,"unresolved",str(endpoint_name or "")


def _v34_resolve_event_parent(job_id, submitted_event_id):
    """Resolve a staged package event to the live canonical event ID."""
    raw=str(submitted_event_id or "").strip()
    if not raw:
        return None,"missing_event_id"

    # Package-local mapping can differ from submitted event_id after canonical merge.
    local=_v31_package_local_endpoint_map(job_id)
    if local.get(raw):
        return str(local[raw]),"package_local_event_map"

    try:
        hit=(sb.table("pc_events").select("event_id,title").eq("event_id",raw).limit(1).execute().data or [])
        if hit:
            return str(hit[0]["event_id"]),"exact_event_id"
    except Exception:
        pass

    staged=_v34_staged_parent_payload(job_id,"event",raw)
    if staged:
        canonical=_v31_resolve_parent_stage_row(staged)
        if canonical:
            return str(canonical),"staged_event_closure"
        p=staged.get("payload") if isinstance(staged.get("payload"),dict) else {}
        title=str(p.get("title") or "").strip()
        if title:
            try:
                hits=(sb.table("pc_events").select("event_id,title").eq("title",title).limit(10).execute().data or [])
                ids={str(h.get("event_id")) for h in hits if h.get("event_id")}
                if len(ids)==1:
                    return next(iter(ids)),"unique_event_title"
            except Exception:
                pass
    return None,"unresolved_event_parent"


def _v34_mark_graph_pending(staged_record_id, reason, details):
    """Persist an exact reason instead of leaving a generic PENDING row."""
    try:
        sb.table("pc_staged_records").update({
            "resolution_status":"REVIEW",
            "resolution_method":"v34_graph_closure_pending",
            "resolution_confidence":0.0,
            "validation_status":"needs_review",
            "resolution_details":{"reason":reason,**(details or {})}
        }).eq("staged_record_id",staged_record_id).execute()
    except Exception:
        pass


def _v29_apply_relationships_direct(job_id):
    """Repair/apply staged canonical relationships after parent objects are resolved.

    This is intentionally analogous to the event-link fast path. It makes Retry
    useful for existing jobs whose package-local entity/asset/route IDs were
    canonicalized during Phase 1.
    """
    report={"scanned":0,"applied":0,"already_applied":0,"unresolved":0,"errors":[]}
    try:
        rows=(sb.table("pc_staged_records")
              .select("staged_record_id,target_table,payload,review_status,source_id")
              .eq("ingestion_job_id",str(job_id))
              .eq("target_table","pc_relationships")
              .limit(20000).execute().data or [])
    except Exception as exc:
        report["errors"].append(f"relationship staging read: {exc}")
        return report

    try:
        writable=set(_table_write_columns_live(sb,"pc_relationships"))
    except Exception:
        writable={
            "relationship_id","source_type","source_id","relationship_type",
            "target_type","target_id","ownership_percent","operating_control",
            "valid_from","valid_to","confidence","record_status",
            "evidence_source_id","notes","source_url","metadata"
        }

    for r in rows:
        if str(r.get("review_status") or "").lower()=="applied":
            report["already_applied"]+=1
            continue
        report["scanned"]+=1
        p=dict(r.get("payload") if isinstance(r.get("payload"),dict) else {})
        meta=p.get("metadata") if isinstance(p.get("metadata"),dict) else {}
        sid,smethod,sname=_v34_resolve_graph_endpoint(
            job_id,p.get("source_type"),p.get("source_id"),p.get("source_name"),meta
        )
        tid,tmethod,tname=_v34_resolve_graph_endpoint(
            job_id,p.get("target_type"),p.get("target_id"),p.get("target_name"),meta
        )
        if not sid or not tid or not p.get("relationship_type"):
            report["unresolved"]+=1
            _v34_mark_graph_pending(
                r["staged_record_id"],
                "relationship_endpoint_unresolved",
                {
                    "submitted_source_type":p.get("source_type"),
                    "submitted_source_id":p.get("source_id"),
                    "submitted_source_name":p.get("source_name"),
                    "source_resolution":smethod,
                    "submitted_target_type":p.get("target_type"),
                    "submitted_target_id":p.get("target_id"),
                    "submitted_target_name":p.get("target_name"),
                    "target_resolution":tmethod,
                    "relationship_type":p.get("relationship_type"),
                }
            )
            continue

        p["source_id"]=sid
        p["target_id"]=tid
        p["relationship_id"]=_canonical_semantic_relationship_id(p)
        p.setdefault("record_status","active")
        p.setdefault("confidence","high")
        # provenance stays in metadata/evidence_source_id, never overwrites graph source_id
        if r.get("source_id") and not p.get("evidence_source_id"):
            p["evidence_source_id"]=r.get("source_id")

        row={k:v for k,v in p.items() if k in writable and v is not None}
        try:
            sb.table("pc_relationships").upsert(
                _jsonable(row),on_conflict="relationship_id"
            ).execute()
            _mark_deferred_applied(
                r["staged_record_id"],
                "v29_direct_relationship_apply",
                {
                    "source_id":sid,"target_id":tid,
                    "source_resolution":smethod,"target_resolution":tmethod,
                    "source_name":sname,"target_name":tname
                },
                p["relationship_id"]
            )
            report["applied"]+=1
        except Exception as exc:
            report["errors"].append(f"{r.get('staged_record_id')}: direct relationship upsert failed: {exc}")
    return report


def _v28_apply_event_links_direct(job_id):
    """Apply canonical event links directly when both endpoints already exist.

    This bypasses the deferred SQL resolver for straightforward links. Event-link
    source_id remains provenance. The graph identity lives in event_id + linked_type +
    linked_id + relationship.
    """
    report={"scanned":0,"applied":0,"already_applied":0,"unresolved":0,"errors":[]}

    try:
        rows=(sb.table("pc_staged_records")
              .select("staged_record_id,target_table,payload,review_status,resolution_status,source_id")
              .eq("ingestion_job_id",str(job_id))
              .eq("target_table","pc_event_links")
              .limit(20000).execute().data or [])
    except Exception as exc:
        report["errors"].append(f"event-link staging read: {exc}")
        return report

    try:
        writable=set(_table_write_columns_live(sb,"pc_event_links"))
    except Exception:
        writable={
            "event_link_id","event_id","linked_type","linked_id","linked_name",
            "relationship","confidence","source_id","metadata"
        }

    for r in rows:
        if str(r.get("review_status") or "").lower()=="applied":
            report["already_applied"]+=1
            continue

        report["scanned"]+=1
        p=r.get("payload") if isinstance(r.get("payload"),dict) else {}
        p=dict(p)
        event_id=str(p.get("event_id") or "").strip()
        linked_type=str(p.get("linked_type") or "").strip().casefold()
        linked_id=str(p.get("linked_id") or "").strip()

        if not event_id or not linked_type or not linked_id:
            report["unresolved"]+=1
            continue

        # V34: the event itself may have been merged/canonicalized under another ID.
        canonical_event_id,event_method=_v34_resolve_event_parent(job_id,event_id)
        if not canonical_event_id:
            report["unresolved"]+=1
            _v34_mark_graph_pending(
                r["staged_record_id"],
                "event_parent_unresolved",
                {"submitted_event_id":event_id,"event_resolution":event_method}
            )
            continue
        p["event_id"]=canonical_event_id

        # Resolve exact IDs, package-local IDs, staged parent payloads, IMO, unique names and routes.
        meta=p.get("metadata") if isinstance(p.get("metadata"),dict) else {}
        canonical_linked_id, endpoint_method, resolved_name = _v34_resolve_graph_endpoint(
            job_id, linked_type, linked_id, p.get("linked_name"), meta
        )
        if not canonical_linked_id:
            report["unresolved"]+=1
            _v34_mark_graph_pending(
                r["staged_record_id"],
                "event_link_endpoint_unresolved",
                {
                    "submitted_event_id":event_id,
                    "canonical_event_id":canonical_event_id,
                    "event_resolution":event_method,
                    "linked_type":linked_type,
                    "submitted_linked_id":linked_id,
                    "linked_name":p.get("linked_name"),
                    "endpoint_resolution":endpoint_method,
                    "event_resolution":event_method,
                }
            )
            continue

        event_id=canonical_event_id
        p["linked_id"]=canonical_linked_id
        if resolved_name and not p.get("linked_name"):
            p["linked_name"]=resolved_name

        # Deterministic event-link id if the package did not supply one.
        if not p.get("event_link_id"):
            digest=hashlib.sha256(
                f"{event_id}|{linked_type}|{canonical_linked_id}|{p.get('relationship') or 'related'}".encode("utf-8")
            ).hexdigest().upper()[:24]
            p["event_link_id"]="EVLINK_"+digest

        # Provenance source_id is valid on pc_event_links.
        if not p.get("source_id") and r.get("source_id"):
            p["source_id"]=r.get("source_id")

        row={k:v for k,v in p.items() if k in writable and v is not None}
        try:
            sb.table("pc_event_links").upsert(
                _jsonable(row),
                on_conflict="event_link_id"
            ).execute()

            sb.table("pc_staged_records").update({
                "resolved_entity_id":str(p["event_link_id"]),
                "resolution_status":"READY",
                "resolution_method":"v28_direct_event_link_apply",
                "resolution_confidence":1.0,
                "candidate_count":1,
                "validation_status":"reviewed",
                "review_status":"applied",
                "resolution_details":{
                    "event_id":event_id,
                    "linked_type":linked_type,
                    "submitted_linked_id":linked_id,
                    "canonical_linked_id":canonical_linked_id,
                    "linked_name":p.get("linked_name"),
                    "endpoint_resolution":endpoint_method,
                }
            }).eq("staged_record_id",r["staged_record_id"]).execute()
            report["applied"]+=1
        except Exception as exc:
            report["errors"].append(f"{r.get('staged_record_id')}: direct event-link upsert failed: {exc}")

    return report


def _apply_deferred_package_rows(job_id, deferred_rows):
    """Stage deferred child/graph rows, then let the SECURITY DEFINER RPC apply them.

    Direct browser/service-client upserts are deliberately avoided here because
    child tables may be protected by RLS. The database owns FK ordering,
    package-local -> canonical ID resolution, and final writes.
    """
    report={
        "received":len(deferred_rows or []),
        "staged":0,
        "rpc":None,
        "errors":[],
    }

    for raw in deferred_rows or []:
        try:
            _stage_one_deferred(raw)
            report["staged"]+=1
        except Exception as exc:
            report["errors"].append(f"deferred staging failed: {exc}")

    # V29: repair graph rows directly after parent canonicalization.
    report["event_link_fast_path"]=_v28_apply_event_links_direct(job_id)
    report["relationship_fast_path"]=_v29_apply_relationships_direct(job_id)

    # V33: graph edges are handled above in Python. Do not send them back through
    # the older SQL v21 polymorphic resolver, which is the source of the
    # sql_v21_deferred_apply_error seen in the Trade package.
    specialist=[
        r for r in (deferred_rows or [])
        if str(r.get("target_table") or "") not in {"pc_event_links","pc_relationships"}
    ]
    if specialist:
        try:
            report["rpc"]=(sb.rpc(
                "pc_apply_deferred_canonical_job_v1",
                {"p_ingestion_job_id":str(job_id)}
            ).execute().data or {})
        except Exception as exc:
            report["errors"].append(f"pc_apply_deferred_canonical_job_v1: {exc}")
    else:
        report["rpc"]={
            "skipped":True,
            "reason":"Graph-only deferred package; event links and relationships applied directly by V33."
        }

    return report



def _collect_legacy_internal_deferred(job_id):
    """Recover unresolved rows created by v16-v18 so Retry can repair them too."""
    try:
        rows=(sb.table("pc_staged_records")
              .select("staged_record_id,target_table,source_record_key,natural_key,action,payload,confidence,source_id")
              .eq("ingestion_job_id",str(job_id))
              .in_("target_table",[MODEL_DIRECT_PARTICIPANT_TARGET,MODEL_EVENT_TRANSACTION_BRIDGE_TARGET])
              .limit(10000).execute().data or [])
    except Exception:
        rows=[]
    out=[]
    for r in rows:
        target=r.get("target_table")
        if target==MODEL_DIRECT_PARTICIPANT_TARGET:
            target="pc_transaction_participants"
        elif target==MODEL_EVENT_TRANSACTION_BRIDGE_TARGET:
            target="pc_event_links"
        out.append({
            "ingestion_job_id":str(job_id),
            "target_table":target,
            "source_record_key":r.get("source_record_key"),
            "natural_key":r.get("natural_key"),
            "action":r.get("action") or "UPSERT",
            "payload":r.get("payload") or {},
            "confidence":r.get("confidence") or 1.0,
            "source_id":r.get("source_id"),
            "resolution_status":"PENDING",
            "validation_status":"pending",
            "review_status":"pending",
        })
        try:
            sb.table("pc_staged_records").delete().eq(
                "staged_record_id",r["staged_record_id"]
            ).execute()
        except Exception:
            pass
    return out



def _v25_apply_existing_imo_rows(job_id):
    """Apply existing vessel enrichments directly by exact IMO.

    This is the fast path for fleet cleanup. If exactly one canonical mobile asset
    already has the incoming IMO, update that row in place and mark staging applied.
    V5 is left for genuinely new/ambiguous identities only.
    """
    report={"scanned":0,"matched_by_imo":0,"applied":0,"not_found":0,"ambiguous":0,"errors":[]}

    try:
        rows=(sb.table("pc_staged_records")
              .select("staged_record_id,target_table,payload,review_status,resolution_status")
              .eq("ingestion_job_id",str(job_id))
              .eq("target_table","pc_mobile_assets")
              .limit(20000).execute().data or [])
    except Exception as exc:
        report["errors"].append(f"staging read: {exc}")
        return report

    writable=set(_table_write_columns_live(sb,"pc_mobile_assets"))

    for r in rows:
        if str(r.get("review_status") or "").lower()=="applied":
            continue

        report["scanned"]+=1
        p=r.get("payload") if isinstance(r.get("payload"),dict) else {}
        imo=str(p.get("imo") or "").strip()
        if not imo:
            report["not_found"]+=1
            continue

        try:
            hits=(sb.table("pc_mobile_assets")
                  .select("mobile_asset_id,name,imo")
                  .eq("imo",imo)
                  .limit(3).execute().data or [])
        except Exception as exc:
            report["errors"].append(f"IMO {imo}: lookup failed: {exc}")
            continue

        if len(hits)==0:
            report["not_found"]+=1
            continue
        if len(hits)>1:
            report["ambiguous"]+=1
            try:
                sb.table("pc_staged_records").update({
                    "resolution_status":"AMBIGUOUS",
                    "resolution_method":"imo_exact_duplicate_collision",
                    "candidate_count":len(hits),
                    "validation_status":"needs_review",
                    "review_status":"pending",
                    "resolution_details":{
                        "imo":imo,
                        "candidate_ids":[x.get("mobile_asset_id") for x in hits],
                    }
                }).eq("staged_record_id",r["staged_record_id"]).execute()
            except Exception:
                pass
            continue

        canonical_id=str(hits[0]["mobile_asset_id"])
        report["matched_by_imo"]+=1

        update=dict(p)
        update["mobile_asset_id"]=canonical_id

        # Helper/package-only fields must never hit canonical table.
        for k in (
            "company_name","company_relationship","owner_name","operator_name","manager_name",
            "source_url","research_sources"
        ):
            if k not in writable:
                update.pop(k,None)

        update={k:v for k,v in update.items() if k in writable and v is not None}

        # Do not erase existing canonical data with blanks.
        update={k:v for k,v in update.items() if v not in ("",[],{}) or k=="metadata"}

        try:
            sb.table("pc_mobile_assets").upsert(
                _jsonable(update),
                on_conflict="mobile_asset_id"
            ).execute()

            details={
                "imo":imo,
                "canonical_mobile_asset_id":canonical_id,
                "incoming_name":p.get("name"),
                "previous_name":hits[0].get("name"),
                "method":"exact IMO update-in-place",
            }
            sb.table("pc_staged_records").update({
                "resolved_entity_id":canonical_id,
                "resolution_status":"MATCHED",
                "resolution_method":"exact_imo_direct_update",
                "resolution_confidence":1.0,
                "candidate_count":1,
                "validation_status":"reviewed",
                "review_status":"applied",
                "resolution_details":details,
            }).eq("staged_record_id",r["staged_record_id"]).execute()

            report["applied"]+=1
        except Exception as exc:
            report["errors"].append(f"IMO {imo}: update failed: {exc}")
            try:
                sb.table("pc_staged_records").update({
                    "resolution_status":"BROKEN_REFERENCE",
                    "resolution_method":"exact_imo_direct_update_error",
                    "validation_status":"needs_review",
                    "review_status":"pending",
                    "resolution_details":{"imo":imo,"reason":str(exc)[:1500]},
                }).eq("staged_record_id",r["staged_record_id"]).execute()
            except Exception:
                pass

    return report



def _v27_repair_relationship_source_endpoints(job_id):
    """Repair staged pc_relationships where provenance accidentally overwrote source_id.

    For relationship rows, payload.source_id is the graph endpoint. If source_name is
    present, resolve/create the canonical entity by exact normalized name and restore
    payload.source_id. Any SRC_* value is retained only as provenance metadata.
    """
    report={"scanned":0,"repaired":0,"already_valid":0,"errors":[]}
    entity_index=_canonical_entity_index()

    try:
        rows=(sb.table("pc_staged_records")
              .select("staged_record_id,target_table,payload,review_status")
              .eq("ingestion_job_id",str(job_id))
              .eq("target_table","pc_relationships")
              .limit(20000).execute().data or [])
    except Exception as exc:
        report["errors"].append(f"relationship staging read: {exc}")
        return report

    for r in rows:
        report["scanned"] += 1
        p=r.get("payload") if isinstance(r.get("payload"),dict) else {}
        p=dict(p)
        src_type=str(p.get("source_type") or "").casefold()
        src_id=str(p.get("source_id") or "").strip()
        src_name=str(p.get("source_name") or "").strip()

        if src_type!="entity" or not src_name:
            continue

        # If source_id already resolves to a canonical entity, leave it alone.
        valid=False
        if src_id and not src_id.startswith("SRC_"):
            try:
                valid=bool((sb.table("pc_entities")
                            .select("entity_id")
                            .eq("entity_id",src_id)
                            .limit(1).execute().data or []))
            except Exception:
                valid=False
        if valid:
            report["already_valid"] += 1
            continue

        eid=_ensure_exact_company_entity(
            src_name,
            entity_type="company",
            metadata=p.get("metadata") if isinstance(p.get("metadata"),dict) else {},
            entity_index=entity_index,
        )
        if not eid:
            report["errors"].append(f"{r.get('staged_record_id')}: could not resolve entity {src_name!r}")
            continue

        meta=p.get("metadata") if isinstance(p.get("metadata"),dict) else {}
        meta=dict(meta)
        if src_id.startswith("SRC_") and not meta.get("provenance_source_id"):
            meta["provenance_source_id"]=src_id

        p["source_id"]=eid
        p["metadata"]=meta

        # Recompute deterministic relationship id after endpoint repair.
        if all(p.get(k) for k in ("source_type","source_id","relationship_type","target_type","target_id")):
            p["relationship_id"]=_canonical_semantic_relationship_id(p)

        try:
            sb.table("pc_staged_records").update({
                "payload":_jsonable(p),
                "resolution_status":"PENDING",
                "resolution_method":"v27_relationship_source_endpoint_repaired",
                "validation_status":"pending",
                "review_status":"pending",
            }).eq("staged_record_id",r["staged_record_id"]).execute()
            report["repaired"] += 1
        except Exception as exc:
            report["errors"].append(f"{r.get('staged_record_id')}: {exc}")

    return report




def _v32_graph_support_preflight():
    """Explain whether database-side polymorphic helpers understand route endpoints."""
    report={"route_table":False,"route_count":0,"pc_object_exists_route":None,"errors":[]}
    try:
        rows=(sb.table("pc_transport_routes").select("route_id").limit(1).execute().data or [])
        report["route_table"]=True
        report["route_count"]=len(rows)
        if rows:
            rid=str(rows[0].get("route_id") or "")
            try:
                # postgrest RPC positional names depend on SQL signature.
                val=sb.rpc("pc_object_exists",{"p_object_type":"route","p_id":rid}).execute().data
                report["pc_object_exists_route"]=bool(val)
            except Exception as exc:
                report["pc_object_exists_route"]=False
                report["errors"].append(
                    "Database helper pc_object_exists does not support route endpoints yet: "+str(exc)
                )
    except Exception as exc:
        report["errors"].append("pc_transport_routes preflight failed: "+str(exc))
    return report


def _v32_mark_graph_resolution_failure(staged_record_id, method, reason, details=None):
    try:
        payload={"reason":str(reason)[:1800]}
        if isinstance(details,dict):
            payload.update(details)
        sb.table("pc_staged_records").update({
            "resolution_status":"BROKEN_REFERENCE",
            "resolution_method":method,
            "validation_status":"needs_review",
            "review_status":"pending",
            "resolution_details":payload,
        }).eq("staged_record_id",staged_record_id).execute()
    except Exception:
        pass



def _v33_repair_pending_observations(job_id):
    """Repair already-staged pc_observations whose primary key was supplied as text."""
    report={"scanned":0,"applied":0,"already_applied":0,"errors":[],"id_map":{}}
    try:
        rows=(sb.table("pc_staged_records")
              .select("staged_record_id,payload,review_status,resolution_status,natural_key")
              .eq("ingestion_job_id",str(job_id))
              .eq("target_table","pc_observations")
              .limit(10000).execute().data or [])
    except Exception as exc:
        report["errors"].append(f"staging read failed: {exc}")
        return report

    try:
        writable=set(_table_write_columns_live(sb,"pc_observations"))
    except Exception:
        writable={
            "observation_id","source_id","source_name","source_url","source_type",
            "retrieved_at","published_at","observation_date","license_name",
            "redistribution_status","attribution_required","raw_value","derived_value",
            "methodology","confidence","review_status","record_status","metadata"
        }

    for r in rows:
        if str(r.get("review_status") or "").lower()=="applied":
            report["already_applied"]+=1
            continue
        report["scanned"]+=1
        p=dict(r.get("payload") if isinstance(r.get("payload"),dict) else {})
        submitted=str(p.get("observation_id") or r.get("natural_key") or "").strip()
        canonical=_v33_observation_uuid(submitted)
        p["observation_id"]=canonical
        # Canonical DB row should be approved/verified if package says so.
        p.setdefault("review_status","approved")
        p.setdefault("record_status","verified")
        row={k:v for k,v in p.items() if k in writable and v is not None}
        try:
            sb.table("pc_observations").upsert(
                _jsonable(row),on_conflict="observation_id"
            ).execute()
            # Heal staged payload so future retries are clean.
            sb.table("pc_staged_records").update({
                "payload":_jsonable(p),
                "resolved_entity_id":canonical,
                "resolution_status":"READY",
                "resolution_method":"v33_observation_uuid_repair",
                "resolution_confidence":1.0,
                "candidate_count":1,
                "validation_status":"reviewed",
                "review_status":"applied",
                "resolution_details":{
                    "submitted_observation_id":submitted,
                    "canonical_observation_id":canonical
                }
            }).eq("staged_record_id",r["staged_record_id"]).execute()
            report["id_map"][submitted]=canonical
            report["applied"]+=1
        except Exception as exc:
            report["errors"].append(f"{r.get('staged_record_id')}: {exc}")
    return report


def _v33_pending_non_graph_deferred(job_id):
    """Return pending deferred rows other than event-links / generic relationships."""
    try:
        rows=(sb.table("pc_staged_records")
              .select("target_table,review_status")
              .eq("ingestion_job_id",str(job_id))
              .limit(30000).execute().data or [])
    except Exception:
        return []
    return [
        r for r in rows
        if str(r.get("review_status") or "").lower()!="applied"
        and str(r.get("target_table") or "") not in {"pc_event_links","pc_relationships"}
        and str(r.get("target_table") or "") in {"pc_transaction_participants"}
    ]


def _v33_repair_existing_job(job_id):
    """Repair the exact failure pattern visible in the current Trade package.

    1) fixes text observation IDs -> deterministic UUIDs;
    2) reconstructs parent canonical mappings;
    3) applies event links and relationships directly;
    4) does NOT send graph rows back through the legacy SQL v21 deferred resolver.
    """
    result={
        "loader_build":LOADER_BUILD,
        "job_id":str(job_id),
        "observations":None,
        "endpoint_map_size":0,
        "event_links":None,
        "relationships":None,
        "specialist_deferred_rpc":"skipped",
        "final_summary":None,
    }
    result["observations"]=_v33_repair_pending_observations(job_id)

    endpoint_map=_v31_package_local_endpoint_map(job_id)
    result["endpoint_map_size"]=len(endpoint_map)

    result["event_links"]=_v28_apply_event_links_direct(job_id)
    result["relationships"]=_v29_apply_relationships_direct(job_id)
    result["graph_closure_retry"]={
        "event_links":_v28_apply_event_links_direct(job_id),
        "relationships":_v29_apply_relationships_direct(job_id),
    }

    specialist=_v33_pending_non_graph_deferred(job_id)
    if specialist:
        try:
            result["specialist_deferred_rpc"]=(sb.rpc(
                "pc_apply_deferred_canonical_job_v1",
                {"p_ingestion_job_id":str(job_id)}
            ).execute().data or {})
        except Exception as exc:
            result["specialist_deferred_rpc"]={"error":str(exc)}
    else:
        result["specialist_deferred_rpc"]={
            "skipped":True,
            "reason":"No specialist deferred rows remain; graph rows were handled directly."
        }

    try:
        _canonical_finalize_existing_rows(job_id)
    except Exception:
        pass

    try:
        summ,by=_canonical_job_summary(job_id)
        result["final_summary"]=summ
        result["by_table"]=by
    except Exception as exc:
        result["final_summary"]={"error":str(exc)}
    return result


def _v32_repair_existing_graph_rows(job_id):
    """Repair unresolved graph rows directly and preserve visible diagnostics.

    Important: do NOT call the legacy deferred SQL resolver when its object helper
    does not understand route endpoints, because that RPC re-stamps successfully
    recoverable rows with EDGE_PROCESS_ERROR / sql_v21_deferred_apply_error.
    """
    result={
        "loader_build":LOADER_BUILD,
        "job_id":str(job_id),
        "preflight":_v32_graph_support_preflight(),
        "endpoint_map_size":0,
        "event_links":None,
        "relationships":None,
        "deferred_rpc":"skipped",
        "final_summary":None,
    }

    endpoint_map=_v31_package_local_endpoint_map(job_id)
    result["endpoint_map_size"]=len(endpoint_map)

    result["event_links"]=_v28_apply_event_links_direct(job_id)
    result["relationships"]=_v29_apply_relationships_direct(job_id)

    # Run legacy deferred SQL only if database route support is actually installed.
    # Otherwise it is known to reject target_type='route'.
    if result["preflight"].get("pc_object_exists_route") is True:
        try:
            result["deferred_rpc"]=(sb.rpc(
                "pc_apply_deferred_canonical_job_v1",
                {"p_ingestion_job_id":str(job_id)}
            ).execute().data or {})
        except Exception as exc:
            result["deferred_rpc"]={"error":str(exc)}
    else:
        result["deferred_rpc"]={
            "skipped":True,
            "reason":"Database pc_object_exists/pc_object_name route support is not installed. Apply migration 054_route_graph_endpoint_support.sql."
        }

    try:
        _canonical_finalize_existing_rows(job_id)
    except Exception:
        pass

    try:
        summ,by=_canonical_job_summary(job_id)
        result["final_summary"]=summ
        result["by_table"]=by
    except Exception as exc:
        result["final_summary"]={"error":str(exc)}
    return result



def _canonical_process_job(job_id, deferred_rows=None):
    """V19 model-first dependency engine.

    SQL V5 sees only canonical parent/object rows.
    Child/edge rows are introduced only after parents resolve, then package-local
    endpoint IDs are rewritten to canonical IDs and written directly.
    """
    deferred=list(deferred_rows or [])

    # Support Retry on jobs created by v16-v18.
    deferred.extend(_collect_legacy_internal_deferred(job_id))

    # V22/V27: provenance is a parent dependency too, but must never overwrite
    # pc_relationships.payload.source_id (the graph endpoint).
    sources_first=_v22_sources_first_for_job(job_id)
    relationship_source_repair=_v27_repair_relationship_source_endpoints(job_id)
    event_link_fast_path_before_v5=_v28_apply_event_links_direct(job_id)

    # V25: exact IMO means "update this vessel now", not "send it through
    # another identity-resolution queue".
    imo_fast_path=_v25_apply_existing_imo_rows(job_id)

    # Transactions are direct parent rows; normalize/apply them before V5.
    pre=_canonical_apply_model_direct_rows(job_id)

    try:
        processor=(sb.rpc(
            "pc_process_ingestion_job_v5",
            {"p_ingestion_job_id":str(job_id)}
        ).execute().data or {})
    except Exception as exc:
        processor={"error":str(exc)}

    # V26: V5 may reclassify staged identity rows after the pre-pass.
    # Exact IMO is authoritative for this cleanup, so finalize those rows AGAIN
    # after V5 and before graph/deferred application.
    imo_finalize_after_v5=_v25_apply_existing_imo_rows(job_id)
    event_link_fast_path_after_v5=_v28_apply_event_links_direct(job_id)

    # Finalize existing canonical objects as successful no-ops before graph phase.
    finalized_before=_canonical_finalize_existing_rows(job_id)

    # Apply newly deferred children/graph; when retrying an existing job, the RPC
    # also processes any already-staged pending child/edge rows.
    deferred_result=_apply_deferred_package_rows(job_id,deferred)
    # V33: only call legacy deferred RPC when a specialist child row actually remains.
    # Generic graph edges are resolved/applied directly and must not be re-stamped
    # with sql_v21_deferred_apply_error.
    if _v33_pending_non_graph_deferred(job_id):
        try:
            retry_pending_rpc=(sb.rpc(
                "pc_apply_deferred_canonical_job_v1",
                {"p_ingestion_job_id":str(job_id)}
            ).execute().data or {})
        except Exception as exc:
            retry_pending_rpc={"error":str(exc)}
    else:
        retry_pending_rpc={"skipped":True,"reason":"No specialist deferred rows remain."}

    finalized_after=_canonical_finalize_existing_rows(job_id)

    # V34: one final graph-closure pass after all parents have been finalized.
    # This catches edges whose parent was canonicalized/merged during the same run.
    graph_closure={
        "event_links":_v28_apply_event_links_direct(job_id),
        "relationships":_v29_apply_relationships_direct(job_id),
    }

    return {
        "loader_build":LOADER_BUILD,
        "sources_first":sources_first,
        "relationship_source_repair":relationship_source_repair,
        "event_link_fast_path_before_v5":event_link_fast_path_before_v5,
        "imo_fast_path_before_v5":imo_fast_path,
        "model_preapply":pre,
        "processor":processor,
        "imo_finalize_after_v5":imo_finalize_after_v5,
        "event_link_fast_path_after_v5":event_link_fast_path_after_v5,
        "idempotent_finalize_before_graph":finalized_before,
        "deferred_dependency_apply":deferred_result,
        "deferred_retry_rpc":retry_pending_rpc,
        "idempotent_finalize_after_graph":finalized_after,
    }



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


def _normalize_excel_serial_date_value(value):
    """Convert Excel serial dates to ISO YYYY-MM-DD for canonical date fields."""
    if value is None or value == "":
        return value
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value,(int,float)) and not isinstance(value,bool):
        try:
            n=float(value)
            if 20000 <= n <= 60000:
                return (date(1899,12,30)+timedelta(days=int(n))).isoformat()
        except Exception:
            pass
    s=str(value).strip()
    try:
        n=float(s)
        if 20000 <= n <= 60000:
            return (date(1899,12,30)+timedelta(days=int(n))).isoformat()
    except Exception:
        pass
    return value

def _v33_observation_uuid(value):
    """Return a deterministic UUID for pc_observations primary keys."""
    raw=str(value or "").strip()
    if not raw:
        return str(uuid.uuid4())
    try:
        return str(uuid.UUID(raw))
    except Exception:
        # Stable across reloads/retries for the same source key.
        return str(uuid.uuid5(uuid.UUID("6f39df76-7d4c-4d70-a92e-7ca37f72fa31"),raw))


def _normalize_canonical_payload_dates(payload,target_table):
    payload=dict(payload or {})
    if target_table=="pc_events":
        for fld in ("start_date","end_date","event_date","latest_update_time"):
            if fld in payload:
                payload[fld]=_normalize_excel_serial_date_value(payload.get(fld))
    elif target_table in {"pc_relationships","pc_transaction_participants"}:
        for fld in ("valid_from","valid_to"):
            if fld in payload:
                payload[fld]=_normalize_excel_serial_date_value(payload.get(fld))
    elif target_table=="pc_observations":
        payload["observation_id"]=_v33_observation_uuid(payload.get("observation_id"))
    return payload


# ---------------------------------------------------------------------------
# V21: IMO-first vessel enrichment + automatic company linking
# ---------------------------------------------------------------------------

def _canon_name_key(value):
    """Stable comparison key for company/entity names; no fuzzy collapsing."""
    s=str(value or "").strip().casefold()
    s=re.sub(r"[^\w]+"," ",s,flags=re.UNICODE)
    return re.sub(r"\s+"," ",s).strip()


def _canonical_entity_index():
    """Load exact canonical entity-name/alias index once per package.

    Matching is deliberately exact after normalization. Similar-but-different legal
    names are NOT collapsed; if no exact normalized canonical/alias match exists,
    the loader creates a distinct canonical entity.
    """
    by_name={}
    rows=[]
    try:
        rows=(sb.table("pc_entities")
              .select("entity_id,name,entity_type,subtype,hq_country")
              .limit(10000).execute().data or [])
    except Exception:
        rows=[]
    for r in rows:
        k=_canon_name_key(r.get("name"))
        if k:
            by_name.setdefault(k,[]).append(r)

    try:
        aliases=(sb.table("pc_entity_aliases")
                 .select("entity_id,alias")
                 .limit(10000).execute().data or [])
    except Exception:
        aliases=[]
    row_by_id={str(r.get("entity_id")):r for r in rows if r.get("entity_id")}
    for a in aliases:
        k=_canon_name_key(a.get("alias"))
        eid=str(a.get("entity_id") or "")
        if k and eid and eid in row_by_id:
            by_name.setdefault(k,[]).append(row_by_id[eid])

    for k,vals in list(by_name.items()):
        seen=set(); uniq=[]
        for v in vals:
            eid=str(v.get("entity_id") or "")
            if eid and eid not in seen:
                seen.add(eid); uniq.append(v)
        by_name[k]=uniq
    return by_name


def _canonical_vessel_imo_index():
    """Return unique IMO -> canonical vessel row."""
    try:
        rows=(sb.table("pc_mobile_assets")
              .select("mobile_asset_id,name,imo")
              .not_.is_("imo","null")
              .limit(20000).execute().data or [])
    except Exception:
        rows=[]
    tmp={}
    for r in rows:
        imo=str(r.get("imo") or "").strip()
        if imo:
            tmp.setdefault(imo,[]).append(r)
    return {imo:vals[0] for imo,vals in tmp.items() if len(vals)==1}


def _auto_entity_id(name):
    digest=hashlib.sha1(_canon_name_key(name).encode("utf-8")).hexdigest()[:20].upper()
    return f"ENTITY_AUTO_{digest}"


def _ensure_exact_company_entity(name, entity_type="company", subtype=None, hq_country=None,
                                 metadata=None, entity_index=None):
    """Resolve exact normalized company/entity name or alias; otherwise create once."""
    name=str(name or "").strip()
    if not name:
        return None
    entity_index = entity_index if entity_index is not None else _canonical_entity_index()
    k=_canon_name_key(name)
    hits=entity_index.get(k,[])
    if len(hits)==1:
        return str(hits[0]["entity_id"])
    if len(hits)>1:
        return None

    eid=_auto_entity_id(name)
    row={
        "entity_id":eid,
        "name":name,
        "entity_type":entity_type or "company",
        "subtype":subtype,
        "hq_country":hq_country,
        "record_status":"verified",
        "data_quality":"high",
        "metadata":dict(metadata or {}),
    }
    row["metadata"].setdefault("created_by","canonical_loader_v21_exact_name")
    row={k:v for k,v in row.items() if v not in (None,"")}
    try:
        writable=set(_table_write_columns_live(sb,"pc_entities"))
        row={k:v for k,v in row.items() if k in writable}
        sb.table("pc_entities").upsert(row,on_conflict="entity_id").execute()
        entity_index.setdefault(k,[]).append(row)
        return eid
    except Exception:
        return None



def _research_url(value):
    """Extract a URL from either a plain string or AI research-source object."""
    if isinstance(value,str):
        u=value.strip()
        return u if u.lower().startswith(("http://","https://")) else None
    if isinstance(value,dict):
        u=str(value.get("url") or value.get("source_url") or "").strip()
        return u if u.lower().startswith(("http://","https://")) else None
    return None


def _source_id_for_url(url):
    digest=hashlib.sha1(str(url).strip().encode("utf-8")).hexdigest()[:20].upper()
    return f"SRC_WEB_{digest}"


def _source_name_from_url(url):
    try:
        host=urllib.parse.urlparse(url).netloc.casefold()
        host=host[4:] if host.startswith("www.") else host
        return host or "Web research source"
    except Exception:
        return "Web research source"


def _ensure_research_source(url):
    """Ensure one research URL has a canonical pc_sources record and return source_id."""
    url=_research_url(url)
    if not url:
        return None
    sid=_source_id_for_url(url)
    try:
        hit=(sb.table("pc_sources").select("source_id,url")
             .eq("url",url).limit(1).execute().data or [])
        if hit:
            return str(hit[0]["source_id"])
    except Exception:
        pass

    name=_source_name_from_url(url)
    row={
        "source_id":sid,
        "publisher":name,
        "source_name":name,
        "source_type":"web_research",
        "coverage":"Canonical vessel/company identity and relationship research",
        "url":url,
        "reliability":"medium",
        "ingestion_method":"canonical_loader_research",
        "redistribution_status":"link_only",
        "attribution_required":True,
        "active":True,
        "notes":"Automatically registered from metadata.research_sources by canonical loader V22."
    }
    try:
        # Use only live writable columns if the helper/RPC is available.
        try:
            writable=set(_table_write_columns_live(sb,"pc_sources"))
            row={k:v for k,v in row.items() if k in writable}
        except Exception:
            pass
        sb.table("pc_sources").upsert(row,on_conflict="source_id").execute()
        return sid
    except Exception:
        # Fall back to a minimal shape known to be used by this app.
        minimal={
            "source_id":sid,
            "source_name":name,
            "source_type":"web_research",
            "url":url,
            "active":True,
        }
        try:
            sb.table("pc_sources").upsert(minimal,on_conflict="source_id").execute()
            return sid
        except Exception:
            return None


def _primary_source_id_from_metadata(metadata):
    """Register all research URLs and return the first canonical source_id."""
    if not isinstance(metadata,dict):
        return None
    vals=[]
    for key in ("research_sources","sources"):
        v=metadata.get(key)
        if isinstance(v,list):
            vals.extend(v)
    if metadata.get("source_url"):
        vals.insert(0,metadata.get("source_url"))

    primary=None
    for item in vals:
        url=_research_url(item)
        if not url:
            continue
        sid=_ensure_research_source(url)
        if sid and primary is None:
            primary=sid
    return primary


def _v22_sources_first_for_job(job_id):
    """Backfill canonical pc_sources BEFORE any deferred graph apply.

    This also repairs already-staged V21 jobs: research_sources -> pc_sources,
    then payload.source_id + pc_staged_records.source_id are populated before retry.
    """
    report={"rows_scanned":0,"rows_with_sources":0,"sources_registered":0,"rows_updated":0,"errors":[]}
    try:
        rows=(sb.table("pc_staged_records")
              .select("staged_record_id,target_table,payload,source_id,review_status")
              .eq("ingestion_job_id",str(job_id))
              .limit(20000).execute().data or [])
    except Exception as exc:
        report["errors"].append(f"staging read: {exc}")
        return report

    seen_source_ids=set()
    for r in rows:
        report["rows_scanned"]+=1
        p=r.get("payload") if isinstance(r.get("payload"),dict) else {}
        meta=p.get("metadata") if isinstance(p.get("metadata"),dict) else {}
        if not meta:
            continue

        urls=[]
        for key in ("research_sources","sources"):
            vals=meta.get(key)
            if isinstance(vals,list):
                urls.extend(vals)
        if meta.get("source_url"):
            urls.insert(0,meta.get("source_url"))
        if not any(_research_url(x) for x in urls):
            continue

        report["rows_with_sources"]+=1
        source_ids=[]
        for item in urls:
            url=_research_url(item)
            if not url:
                continue
            sid=_ensure_research_source(url)
            if sid:
                source_ids.append(sid)
                if sid not in seen_source_ids:
                    seen_source_ids.add(sid)
                    report["sources_registered"]+=1

        if not source_ids:
            continue

        primary=source_ids[0]
        changed=False
        p=dict(p)
        meta=dict(meta)

        # CRITICAL SEMANTICS:
        # pc_relationships.payload.source_id is the GRAPH SOURCE ENDPOINT (entity/asset/etc),
        # NOT a provenance source FK. Provenance belongs in staged_record.source_id and metadata.
        if str(r.get("target_table") or "") != "pc_relationships":
            if not p.get("source_id"):
                p["source_id"]=primary
                changed=True
        else:
            if meta.get("provenance_source_id") != primary:
                meta["provenance_source_id"]=primary
                changed=True

        if meta.get("canonical_source_ids") != source_ids:
            meta["canonical_source_ids"]=source_ids
            changed=True

        if changed:
            p["metadata"]=meta

        if changed or not r.get("source_id"):
            patch={"payload":_jsonable(p),"source_id":primary}
            try:
                sb.table("pc_staged_records").update(patch).eq(
                    "staged_record_id",r["staged_record_id"]
                ).execute()
                report["rows_updated"]+=1
            except Exception as exc:
                # Some deployments may not expose staged source_id; payload source_id is still useful.
                try:
                    sb.table("pc_staged_records").update({"payload":_jsonable(p)}).eq(
                        "staged_record_id",r["staged_record_id"]
                    ).execute()
                    report["rows_updated"]+=1
                except Exception as exc2:
                    report["errors"].append(
                        f"{r.get('staged_record_id')}: {exc2}"
                    )
    return report


def _relationship_row(job_id, source_id, relationship_type, target_id,
                      source_name=None, target_name=None, confidence=0.99,
                      research_sources=None, source_record_key=None):
    primary_source_id=None
    for _src in (research_sources or []):
        primary_source_id=_ensure_research_source(_src)
        if primary_source_id:
            break

    rel_payload={
        "relationship_id":_canonical_semantic_relationship_id({
            "source_type":"entity","source_id":source_id,
            "relationship_type":relationship_type,
            "target_type":"mobile_asset","target_id":target_id,
        }),
        "source_type":"entity",
        "source_id":source_id,
        "source_name":source_name,
        "relationship_type":relationship_type,
        "target_type":"mobile_asset",
        "target_id":target_id,
        "target_name":target_name,
        "confidence":confidence,
        "record_status":"verified",
        "metadata":{
            "auto_linked_by":"canonical_loader_v26",
            "research_sources":research_sources or [],
            "provenance_source_id":primary_source_id,
        }
    }
    return {
        "ingestion_job_id":str(job_id),
        "target_table":"pc_relationships",
        "source_record_key":source_record_key or rel_payload["relationship_id"],
        "natural_key":rel_payload["relationship_id"],
        "action":"UPSERT",
        "payload":_jsonable({k:v for k,v in rel_payload.items() if v not in (None,"")}),
        "confidence":confidence,
        "resolution_status":"PENDING",
        "validation_status":"pending",
        "review_status":"pending",
    }


def _v21_prepare_native_package(job_id, sections_config):
    """Normalize native packages before staging.

    Existing IMO -> existing canonical vessel.
    Exact company name/alias -> existing canonical company.
    No exact company -> create once as a distinct canonical entity.
    Relationship endpoints are rewritten automatically.
    Vessel rows may include company_name/company_relationship or
    owner_name/operator_name/manager_name to auto-create graph edges.
    """
    entity_index=_canonical_entity_index()
    imo_index=_canonical_vessel_imo_index()
    local_to_canonical={}
    generated_relationships=[]

    for section,cfg in sections_config.items():
        if not cfg.get("include",True):
            continue
        df=cfg.get("df")
        target=cfg.get("target")
        native=bool(cfg.get("native")) or _loader_native_section(df)
        if not native or df is None or df.empty:
            continue

        out=[]
        for row in df.to_dict("records"):
            row=dict(row)
            payload=_jsonish(row.get("payload"))
            if not isinstance(payload,dict):
                out.append(row); continue
            payload=dict(payload)

            if target=="pc_entities":
                local_id=str(payload.get("entity_id") or "").strip() or None
                name=str(payload.get("name") or "").strip()
                if name:
                    eid=_ensure_exact_company_entity(
                        name,
                        entity_type=payload.get("entity_type") or "company",
                        subtype=payload.get("subtype"),
                        hq_country=payload.get("hq_country") or payload.get("country"),
                        metadata=payload.get("metadata") if isinstance(payload.get("metadata"),dict) else {},
                        entity_index=entity_index,
                    )
                    if eid:
                        if local_id:
                            local_to_canonical[local_id]=eid
                        payload["entity_id"]=eid

            elif target=="pc_mobile_assets":
                local_id=str(payload.get("mobile_asset_id") or "").strip() or None
                imo=str(payload.get("imo") or "").strip()
                if imo and imo in imo_index:
                    canonical=str(imo_index[imo]["mobile_asset_id"])
                    if local_id:
                        local_to_canonical[local_id]=canonical
                    payload["mobile_asset_id"]=canonical
                    md=payload.get("metadata") if isinstance(payload.get("metadata"),dict) else {}
                    md=dict(md)
                    if local_id and local_id != canonical:
                        md.setdefault("package_local_mobile_asset_id",local_id)
                    md["imo_first_existing_match"]=True
                    payload["metadata"]=md

                link_specs=[]
                helper_company=str(payload.pop("company_name", "") or "").strip()
                helper_rel=str(payload.pop("company_relationship", "") or "").strip()
                if helper_company:
                    link_specs.append((helper_company, helper_rel or "commercially_operates","company",None))
                for field,rel,subtype in (
                    ("owner_name","owns","shipowner"),
                    ("operator_name","commercially_operates","shipping_company"),
                    ("manager_name","technically_manages","ship_management_company"),
                ):
                    nm=str(payload.pop(field, "") or "").strip()
                    if nm:
                        link_specs.append((nm,rel,"company",subtype))

                vessel_id=str(payload.get("mobile_asset_id") or local_id or "").strip()
                research_sources=[]
                md=payload.get("metadata") if isinstance(payload.get("metadata"),dict) else {}
                if isinstance(md.get("research_sources"),list):
                    research_sources=md.get("research_sources")

                # Sources are canonical parents too: register them before vessel/graph writes.
                primary_source_id=None
                for _src in research_sources:
                    primary_source_id=_ensure_research_source(_src)
                    if primary_source_id:
                        break
                if primary_source_id and not payload.get("source_id"):
                    payload["source_id"]=primary_source_id
                for company_name,rel,etype,subtype in link_specs:
                    eid=_ensure_exact_company_entity(
                        company_name,entity_type=etype,subtype=subtype,
                        metadata={"research_sources":research_sources},
                        entity_index=entity_index,
                    )
                    if eid and vessel_id:
                        generated_relationships.append(
                            _relationship_row(
                                job_id,eid,rel,vessel_id,
                                source_name=company_name,
                                target_name=payload.get("name"),
                                confidence=float(row.get("confidence") or 0.99),
                                research_sources=research_sources,
                                source_record_key=f"auto:{imo or vessel_id}:{rel}:{eid}",
                            )
                        )

            row["payload"]=payload
            out.append(row)
        cfg["df"]=pd.DataFrame(out)

    for section,cfg in sections_config.items():
        if not cfg.get("include",True) or cfg.get("target")!="pc_relationships":
            continue
        df=cfg.get("df")
        native=bool(cfg.get("native")) or _loader_native_section(df)
        if not native or df is None or df.empty:
            continue
        out=[]
        for row in df.to_dict("records"):
            row=dict(row)
            payload=_jsonish(row.get("payload"))
            if not isinstance(payload,dict):
                out.append(row); continue
            payload=dict(payload)
            sid=str(payload.get("source_id") or "")
            tid=str(payload.get("target_id") or "")
            if sid in local_to_canonical:
                payload["source_id"]=local_to_canonical[sid]
            if tid in local_to_canonical:
                payload["target_id"]=local_to_canonical[tid]

            if str(payload.get("source_type") or "").casefold()=="entity":
                sname=str(payload.get("source_name") or "").strip()
                if sname and (not payload.get("source_id") or str(payload.get("source_id")).startswith("PKG_")):
                    eid=_ensure_exact_company_entity(
                        sname,entity_type="company",
                        metadata=payload.get("metadata") if isinstance(payload.get("metadata"),dict) else {},
                        entity_index=entity_index,
                    )
                    if eid:
                        payload["source_id"]=eid

            if str(payload.get("target_type") or "").casefold() in {"mobile_asset","vessel"}:
                meta=payload.get("metadata") if isinstance(payload.get("metadata"),dict) else {}
                imo=str(meta.get("imo") or payload.get("imo") or "").strip()
                if imo and imo in imo_index:
                    payload["target_id"]=str(imo_index[imo]["mobile_asset_id"])

            if all(payload.get(k) for k in ("source_type","source_id","relationship_type","target_type","target_id")):
                payload["relationship_id"]=_canonical_semantic_relationship_id(payload)
            row["payload"]=payload
            out.append(row)
        cfg["df"]=pd.DataFrame(out)

    return {
        "local_to_canonical":local_to_canonical,
        "generated_relationships":generated_relationships,
    }


def _canonical_stage_records(job_id, sections_config):
    """Stage a whole package in dependency-safe phases.

    Phase 1 (inserted immediately):
      canonical identity objects + direct parent/fact tables.

    Phase 2 (held in memory until Phase 1 is resolved/applied):
      pc_transaction_participants, pc_relationships, pc_event_links.

    This is the core V19 rule: the loader reads the model/dependencies first and
    never asks a child/edge row to resolve before its parent endpoints exist.
    """
    staged=[]
    deferred=[]
    table_counts={}
    skipped_sections=[]
    native_rows=0

    # V21: automatic vessel/company canonicalization before normal staging.
    v21=_v21_prepare_native_package(job_id,sections_config)
    deferred.extend(v21.get("generated_relationships") or [])

    for section,cfg in sections_config.items():
        if not cfg.get("include",True):
            skipped_sections.append(section)
            continue
        target=cfg["target"]
        df=cfg["df"]
        mapping=cfg.get("mapping")
        native=bool(cfg.get("native")) or _loader_native_section(df)

        logical=_canonical_target_entity_type(target)
        if not logical and target not in CANONICAL_DIRECT_TABLES and target not in CANONICAL_DEFERRED_TABLES:
            raise ValueError(
                f"{target} is not registered in pc_meta_entity_types and is not a supported direct/deferred table."
            )

        for row_no,row in enumerate(df.to_dict("records"),1):
            if native:
                payload=_jsonish(row.get("payload"))
                if not isinstance(payload,dict):
                    raise ValueError(f"{section} row {row_no}: payload must be a JSON object")
                payload=_normalize_canonical_payload_dates(payload,target)
                native_rows += 1
            else:
                payload=_payload_from_mapping(row,mapping,target)
                payload=_normalize_canonical_payload_dates(payload,target)

            meaningful={k:v for k,v in (payload or {}).items() if v not in (None,"",[],{})}
            if not meaningful:
                continue

            supplied_nk=_clean_upload_scalar(row.get("natural_key")) if isinstance(row,dict) else None
            nk=str(supplied_nk or _natural_key_global(payload,target,row_no))
            source_record_key=_clean_upload_scalar(row.get("source_record_key")) if isinstance(row,dict) else None
            source_action=str(_clean_upload_scalar(row.get("action")) or "UPSERT").upper()
            confidence=_clean_upload_scalar(row.get("confidence")) if isinstance(row,dict) else None
            try:
                confidence=float(confidence) if confidence is not None else 1.0
            except Exception:
                confidence=1.0

            # In a canonical-loader package, REVIEW means "resolve against the
            # canonical registry and only stop if ambiguity remains", not
            # "force analyst interaction before matching".
            action=source_action
            if native and source_action=="REVIEW":
                action="UPSERT"
                md=payload.get("metadata") if isinstance(payload.get("metadata"),dict) else {}
                md=dict(md)
                md.setdefault("source_package_action","REVIEW")
                payload["metadata"]=md

            staged_row={
                "ingestion_job_id":str(job_id),
                "target_table":target,
                "source_record_key":str(source_record_key or f"{section}:{nk}"),
                "natural_key":nk,
                "action":action,
                "payload":_jsonable(payload),
                "confidence":confidence,
                "resolution_status":"PENDING",
                "validation_status":"pending",
                "review_status":"pending",
            }
            if logical:
                staged_row["target_entity_type"]=logical
            if isinstance(row,dict) and _clean_upload_scalar(row.get("source_id")) is not None:
                staged_row["source_id"]=str(_clean_upload_scalar(row.get("source_id")))

            if target in CANONICAL_DEFERRED_TABLES:
                # Do not insert yet. SQL V5 must never see graph/child rows before
                # their canonical parents have been resolved.
                staged_row.pop("target_entity_type",None)
                deferred.append(staged_row)
            else:
                staged.append(staged_row)

            table_counts[target]=table_counts.get(target,0)+1

    for i in range(0,len(staged),250):
        sb.table("pc_staged_records").insert(_jsonable(staged[i:i+250])).execute()

    return {
        "rows":len(staged)+len(deferred),
        "phase1_rows":len(staged),
        "deferred_rows":len(deferred),
        "native_rows":native_rows,
        "tables":table_counts,
        "skipped_sections":skipped_sections,
        "v21_canonical_rewrites":len(v21.get("local_to_canonical") or {}),
        "v21_generated_relationships":len(v21.get("generated_relationships") or []),
        "_deferred_records":deferred,
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

def _canonical_section_target(section,df):
    """Return (target_table, include_by_default, reason).

    Unknown/reference sheets never fall back to pc_entities.
    The six core canonical graph tables are always loadable using their established FK-safe staging types.\n    Optional tables require pc_meta_entity_types registration.
    """
    s=_norm_field(section)

    explicit={
        "pc_entities":"pc_entities",
        "pc_assets":"pc_assets",
        "pc_mobile_assets":"pc_mobile_assets",
        "pc_events":"pc_events",
        "pc_event_links":"pc_event_links",
        "pc_relationships":"pc_relationships",
        "pc_transactions":"pc_transactions",
        "pc_transaction_participants":"pc_transaction_participants",
        "pc_transport_routes":"pc_transport_routes",
        "pc_chokepoints":"pc_chokepoints",
        "pc_market_instruments":"pc_market_instruments",
        "pc_trade_flows":"pc_trade_flows",
        "pc_supply_series":"pc_supply_series",
        "pc_observations":"pc_observations",
        "entities":"pc_entities",
        "new_entities":"pc_entities",
        "entity":"pc_entities",
        "assets":"pc_assets",
        "new_assets":"pc_assets",
        "fixed_assets":"pc_assets",
        "mobile_assets":"pc_mobile_assets",
        "new_mobile_assets":"pc_mobile_assets",
        "vessels":"pc_mobile_assets",
        "events":"pc_events",
        "event_output_template":"pc_events",
        "event_links":"pc_event_links",
        "relationships":"pc_relationships",
        "transactions":"pc_transactions",
        "transaction_participants":"pc_transaction_participants",
        "deal_participants":"pc_transaction_participants",
        "routes":"pc_transport_routes",
        "transport_routes":"pc_transport_routes",
        "chokepoints":"pc_chokepoints",
        "market_instruments":"pc_market_instruments",
        "trade_flows":"pc_trade_flows",
        "supply_series":"pc_supply_series",
        "observations":"pc_observations",
    }

    ignore_tokens=(
        "readme","instruction","research_query","incident_categories",
        "priority_geographies","source_hierarchy","database_mapping",
        "severity_rules","comparison_checklist","unresolved_review",
        "research_run_summary","lookup","reference","definitions"
    )
    if any(tok in s for tok in ignore_tokens):
        return None,False,"reference/control sheet"

    registered=_canonical_registered_table_map()

    if s in explicit:
        target=explicit[s]
        if target in registered:
            et=registered[target].get("entity_type")
            return target,True,f"recognized data sheet · registered type: {et}"
        if target in CANONICAL_DIRECT_TABLES:
            return target,True,"recognized direct child/fact table · staged without target_entity_type"
        return target,False,(
            f"recognized data sheet, but {target} is not registered in pc_meta_entity_types; "
            "excluded until metadata is registered"
        )

    guessed=_suggest_target_table(section,df)
    if guessed in CANONICAL_LOAD_TABLES and guessed in registered:
        et=registered[guessed].get("entity_type")
        return guessed,False,f"unrecognized sheet — verify before including · registered type: {et}"

    if guessed in CANONICAL_LOAD_TABLES:
        return guessed,False,(
            f"unrecognized sheet and {guessed} is not registered in pc_meta_entity_types — excluded"
        )

    return None,False,"unrecognized sheet — excluded"



# ===========================================================================
# SANCTIONS BULK LOADER — V50
# ===========================================================================

SANCTIONS_SOURCE_CATALOG = {
    "OFAC SDN": {
        "authority_code":"OFAC",
        "authority_name":"U.S. Office of Foreign Assets Control",
        "jurisdiction":"United States",
        "source_list":"SDN",
        "source_id":"SAN-OFAC-SDN",
        "official_page":"https://ofac.treasury.gov/sanctions-list-service",
        "preferred":"XML (legacy or advanced); CSV also supported",
        "formats":["xml","csv","zip"],
    },
    "OFAC Non-SDN Consolidated": {
        "authority_code":"OFAC",
        "authority_name":"U.S. Office of Foreign Assets Control",
        "jurisdiction":"United States",
        "source_list":"NON-SDN",
        "source_id":"SAN-OFAC-CONS",
        "official_page":"https://ofac.treasury.gov/sanctions-list-service",
        "preferred":"XML (legacy or advanced); CSV also supported",
        "formats":["xml","csv","zip"],
    },
    "UK Sanctions List": {
        "authority_code":"UK",
        "authority_name":"UK Foreign, Commonwealth & Development Office",
        "jurisdiction":"United Kingdom",
        "source_list":"UKSL",
        "source_id":"SAN-UK",
        "official_page":"https://www.gov.uk/government/publications/the-uk-sanctions-list",
        "preferred":"CSV or XML",
        "formats":["csv","xml","ods","txt","zip"],
    },
    "EU Consolidated Financial Sanctions": {
        "authority_code":"EU",
        "authority_name":"European Union",
        "jurisdiction":"European Union",
        "source_list":"EU-FSF",
        "source_id":"SAN-EU",
        "official_page":"https://data.europa.eu/data/datasets/consolidated-list-of-persons-groups-and-entities-subject-to-eu-financial-sanctions",
        "preferred":"CSV 1.1 or XML 1.1",
        "formats":["csv","xml","zip"],
    },
    "UN Security Council Consolidated": {
        "authority_code":"UNSC",
        "authority_name":"United Nations Security Council",
        "jurisdiction":"United Nations",
        "source_list":"UNSC-CONSOLIDATED",
        "source_id":"SAN-UNSC",
        "official_page":"https://main.un.org/securitycouncil/en/content/un-sc-consolidated-list",
        "preferred":"XML",
        "formats":["xml","csv","zip"],
    },
    "UN 1718 DPRK": {
        "authority_code":"UNSC",
        "authority_name":"United Nations Security Council",
        "jurisdiction":"United Nations",
        "source_list":"UNSC-1718",
        "source_id":"SAN-UNSC-1718",
        "official_page":"https://main.un.org/securitycouncil/en/sanctions/1718/materials",
        "preferred":"XML",
        "formats":["xml","csv","zip"],
    },
    "PGSA / Internal": {
        "authority_code":"PGSA",
        "authority_name":"Persian Gulf Strait Authority",
        "jurisdiction":"Persian Gulf / Strait of Hormuz",
        "source_list":"PGSA",
        "source_id":"SAN-PGSA",
        "official_page":None,
        "preferred":"CSV / XLSX / XML",
        "formats":["csv","xlsx","xml","zip"],
    },
}


def _sx_local(tag):
    return str(tag or "").split("}")[-1].split(":")[-1]


def _sx_text(el):
    return " ".join(" ".join(el.itertext()).split()) if el is not None else ""


def _sx_norm_col(v):
    return re.sub(r"[^a-z0-9]+","_",str(v or "").strip().casefold()).strip("_")


def _sx_first(d,*keys):
    nd={_sx_norm_col(k):v for k,v in d.items()}
    for k in keys:
        v=nd.get(_sx_norm_col(k))
        if v not in (None,"") and not (isinstance(v,float) and pd.isna(v)):
            return str(v).strip()
    return None


def _sx_split_values(v):
    if v in (None,""):
        return []
    if isinstance(v,list):
        return [str(x).strip() for x in v if str(x).strip()]
    s=str(v).strip()
    if not s:
        return []
    return [x.strip() for x in re.split(r"\s*[;|]\s*",s) if x.strip()]


def _sx_date(v):
    if not v:
        return None
    try:
        x=pd.to_datetime(v,errors="coerce",dayfirst=True)
        if pd.isna(x):
            return None
        return x.date().isoformat()
    except Exception:
        return None


def _sx_entity_type(v):
    s=str(v or "").strip().casefold()
    if any(x in s for x in ("ship","vessel")):
        return "vessel"
    if any(x in s for x in ("individual","person")):
        return "individual"
    if any(x in s for x in ("aircraft","plane")):
        return "aircraft"
    return "entity"


def _sx_id_type(v):
    s=_sx_norm_col(v)
    mapping={
        "imo_number":"IMO","imo":"IMO","mmsi":"MMSI","call_sign":"CALLSIGN",
        "passport_number":"PASSPORT","passport":"PASSPORT",
        "national_identifier_number":"NATIONAL_ID","national_id":"NATIONAL_ID",
        "business_registration_number_s":"REGISTRATION","registration_number":"REGISTRATION",
        "tax_id":"TAX_ID","lei":"LEI","un_reference_number":"UN_REFERENCE"
    }
    return mapping.get(s, str(v or "").strip().upper().replace(" ","_")[:80])


def _sx_authority(cfg):
    hit=(sb.table("pc_sanctions_authorities")
         .select("sanctions_authority_id")
         .eq("authority_code",cfg["authority_code"])
         .limit(1).execute().data or [])
    if hit:
        return hit[0]["sanctions_authority_id"]
    row={
        "authority_code":cfg["authority_code"],
        "authority_name":cfg["authority_name"],
        "jurisdiction":cfg["jurisdiction"],
        "official_url":cfg.get("official_page"),
        "active":True,
        "metadata":{"created_by":LOADER_BUILD},
    }
    return sb.table("pc_sanctions_authorities").insert(row).execute().data[0]["sanctions_authority_id"]


def _sx_programme(authority_id, code_value, official_url=None):
    code_value=str(code_value or "UNSPECIFIED").strip()[:250]
    hit=(sb.table("pc_sanctions_programmes")
         .select("sanctions_programme_id")
         .eq("sanctions_authority_id",authority_id)
         .eq("programme_code",code_value)
         .limit(1).execute().data or [])
    if hit:
        return hit[0]["sanctions_programme_id"]
    row={
        "sanctions_authority_id":authority_id,
        "programme_code":code_value,
        "programme_name":code_value,
        "regime_name":code_value,
        "official_url":official_url,
        "active":True,
        "metadata":{"created_by":LOADER_BUILD},
    }
    return sb.table("pc_sanctions_programmes").insert(row).execute().data[0]["sanctions_programme_id"]


def _sx_source(cfg):
    sid=cfg["source_id"]
    try:
        hit=(sb.table("pc_sources").select("source_id").eq("source_id",sid).limit(1).execute().data or [])
        if hit:
            return sid
    except Exception:
        pass
    row={
        "source_id":sid,
        "source_name":cfg["authority_name"]+" "+cfg["source_list"],
        "publisher":cfg["authority_name"],
        "source_type":"official_sanctions_list",
        "coverage":"Sanctions designations and identifiers",
        "url":cfg.get("official_page"),
        "reliability":"high",
        "active":True,
        "metadata":{"created_by":LOADER_BUILD},
    }
    try:
        writable=set(_table_write_columns_live(sb,"pc_sources"))
        row={k:v for k,v in row.items() if k in writable}
    except Exception:
        pass
    sb.table("pc_sources").upsert(row,on_conflict="source_id").execute()
    return sid


def _sx_mobile_index():
    rows=(sb.table("pc_mobile_assets")
          .select("mobile_asset_id,name,imo,mmsi,call_sign,asset_type,flag")
          .limit(50000).execute().data or [])
    by_imo={}
    by_mmsi={}
    by_name={}
    for r in rows:
        imo=re.sub(r"\D","",str(r.get("imo") or ""))
        mmsi=re.sub(r"\D","",str(r.get("mmsi") or ""))
        nk=_canon_name_key(r.get("name"))
        if len(imo)==7: by_imo.setdefault(imo,[]).append(r)
        if len(mmsi)==9: by_mmsi.setdefault(mmsi,[]).append(r)
        if nk: by_name.setdefault(nk,[]).append(r)
    return by_imo,by_mmsi,by_name


def _sx_ensure_vessel(rec, source_id, indexes):
    by_imo,by_mmsi,by_name=indexes
    ids={str(x.get("type") or "").upper():str(x.get("value") or "") for x in rec.get("identifiers",[])}
    imo=re.sub(r"\D","",ids.get("IMO",""))
    mmsi=re.sub(r"\D","",ids.get("MMSI",""))
    name=rec["primary_name"]
    if len(imo)==7 and len(by_imo.get(imo,[]))==1:
        return "mobile_asset",by_imo[imo][0]["mobile_asset_id"],"IMO_EXACT",1.0
    if len(mmsi)==9 and len(by_mmsi.get(mmsi,[]))==1:
        return "mobile_asset",by_mmsi[mmsi][0]["mobile_asset_id"],"MMSI_EXACT",0.99
    nk=_canon_name_key(name)
    if nk and len(by_name.get(nk,[]))==1:
        return "mobile_asset",by_name[nk][0]["mobile_asset_id"],"NAME_EXACT",0.95

    key_source=imo or mmsi or nk
    mid="MOBILE_SAN_"+hashlib.sha1(str(key_source).encode()).hexdigest()[:20].upper()
    row={
        "mobile_asset_id":mid,
        "name":name,
        "asset_type":"vessel",
        "subtype":rec.get("subtype") or "sanctions_listed_vessel",
        "imo":imo if len(imo)==7 else None,
        "mmsi":mmsi if len(mmsi)==9 else None,
        "call_sign":ids.get("CALLSIGN") or None,
        "flag":rec.get("flag"),
        "record_status":"verified",
        "data_quality":"high",
        "source_id":source_id,
        "metadata":{"created_from_sanctions":True,"source_external_id":rec.get("external_id")},
    }
    writable=set(_table_write_columns_live(sb,"pc_mobile_assets"))
    row={k:v for k,v in row.items() if k in writable and v is not None}
    sb.table("pc_mobile_assets").upsert(row,on_conflict="mobile_asset_id").execute()
    by_name.setdefault(nk,[]).append(row)
    if len(imo)==7: by_imo.setdefault(imo,[]).append(row)
    if len(mmsi)==9: by_mmsi.setdefault(mmsi,[]).append(row)
    return "mobile_asset",mid,"CREATED_SANCTIONS_KEY",1.0


def _sx_ensure_entity(rec, source_id, entity_index):
    et="person" if rec.get("listed_entity_type")=="individual" else "organization"
    eid=_ensure_exact_company_entity(
        rec["primary_name"],
        entity_type=et,
        subtype="sanctions_listed_"+rec.get("listed_entity_type","entity"),
        hq_country=rec.get("country"),
        metadata={
            "created_from_sanctions":True,
            "source_external_id":rec.get("external_id"),
            "source_id":source_id,
        },
        entity_index=entity_index
    )
    return ("entity",eid,"NAME_EXACT_OR_CREATED",1.0) if eid else (None,None,"AMBIGUOUS_NAME",0.0)


def _sx_parse_ofac_xml(data, source_list):
    root=ET.fromstring(data)
    records=[]
    legacy=[e for e in root.iter() if _sx_local(e.tag)=="sdnEntry"]
    if legacy:
        for e in legacy:
            uid=next((_sx_text(x) for x in e if _sx_local(x.tag)=="uid"),None)
            first=next((_sx_text(x) for x in e if _sx_local(x.tag)=="firstName"),"")
            last=next((_sx_text(x) for x in e if _sx_local(x.tag)=="lastName"),"")
            name=(" ".join([first,last])).strip()
            typ=next((_sx_text(x) for x in e if _sx_local(x.tag)=="sdnType"),"entity")
            rec={
                "external_id":uid,
                "primary_name":name or uid or "Unnamed OFAC record",
                "listed_entity_type":_sx_entity_type(typ),
                "programmes":[],
                "aliases":[],
                "identifiers":[],
                "addresses":[],
                "remarks":None,
                "source_list":source_list,
                "raw_record":{"xml_tag":"sdnEntry"},
            }
            for x in e.iter():
                ln=_sx_local(x.tag)
                if ln=="program" and _sx_text(x):
                    rec["programmes"].append(_sx_text(x))
                elif ln=="aka":
                    af=next((_sx_text(y) for y in x if _sx_local(y.tag)=="firstName"),"")
                    al=next((_sx_text(y) for y in x if _sx_local(y.tag)=="lastName"),"")
                    av=(" ".join([af,al])).strip()
                    at=next((_sx_text(y) for y in x if _sx_local(y.tag)=="type"),None)
                    if av: rec["aliases"].append({"alias":av,"alias_type":at})
                elif ln=="id":
                    it=next((_sx_text(y) for y in x if _sx_local(y.tag)=="idType"),None)
                    iv=next((_sx_text(y) for y in x if _sx_local(y.tag)=="idNumber"),None)
                    ic=next((_sx_text(y) for y in x if _sx_local(y.tag)=="idCountry"),None)
                    if it and iv: rec["identifiers"].append({"type":_sx_id_type(it),"value":iv,"country":ic})
                elif ln=="address":
                    vals={_sx_local(y.tag):_sx_text(y) for y in x}
                    if any(vals.values()):
                        rec["addresses"].append({
                            "line1":vals.get("address1"),"line2":vals.get("address2"),
                            "city":vals.get("city"),"region":vals.get("stateOrProvince"),
                            "postal_code":vals.get("postalCode"),"country":vals.get("country")
                        })
                elif ln=="remarks" and _sx_text(x):
                    rec["remarks"]=_sx_text(x)
                elif ln=="vesselInfo":
                    vals={_sx_local(y.tag):_sx_text(y) for y in x}
                    rec["flag"]=vals.get("vesselFlag")
                    rec["subtype"]=vals.get("vesselType")
                    if vals.get("callSign"):
                        rec["identifiers"].append({"type":"CALLSIGN","value":vals["callSign"]})
            records.append(rec)
        return records

    # Generic advanced XML fallback. OFAC's advanced model uses repeated party/profile
    # records; this captures IDs, aliases and document-style identifiers by local names.
    candidates=[e for e in root.iter() if _sx_local(e.tag).casefold() in {"distinctparty","entity","profile"}]
    seen=set()
    for e in candidates:
        ext=e.attrib.get("FixedRef") or e.attrib.get("ID") or e.attrib.get("id")
        vals=[_sx_text(x) for x in e.iter() if _sx_local(x.tag).casefold() in {"namepartvalue","formattedfullname","fullname"} and _sx_text(x)]
        name=vals[0] if vals else None
        if not name:
            continue
        key=(ext,name)
        if key in seen: continue
        seen.add(key)
        aliases=[]
        ids=[]
        for x in e.iter():
            ln=_sx_local(x.tag).casefold()
            txt=_sx_text(x)
            if ln in {"alias","namepartvalue"} and txt and txt!=name:
                aliases.append({"alias":txt,"alias_type":"alias"})
            if ln in {"documentnumber","documentnumbertext","idnumber"} and txt:
                ids.append({"type":"OTHER_ID","value":txt})
        records.append({
            "external_id":ext or hashlib.sha1(name.encode()).hexdigest()[:20],
            "primary_name":name,
            "listed_entity_type":"entity",
            "programmes":[],
            "aliases":aliases,
            "identifiers":ids,
            "addresses":[],
            "remarks":None,
            "source_list":source_list,
            "raw_record":{"xml_tag":_sx_local(e.tag),"advanced_fallback":True},
        })
    return records


def _sx_parse_un_xml(data, source_list):
    root=ET.fromstring(data)
    records=[]
    for e in root.iter():
        ln=_sx_local(e.tag)
        if ln not in {"INDIVIDUAL","ENTITY"}:
            continue
        vals={}
        for x in e.iter():
            vals.setdefault(_sx_local(x.tag),[])
            t=_sx_text(x)
            if t: vals[_sx_local(x.tag)].append(t)
        if ln=="INDIVIDUAL":
            parts=[(vals.get(k) or [""])[0] for k in ("FIRST_NAME","SECOND_NAME","THIRD_NAME","FOURTH_NAME")]
            name=" ".join(x for x in parts if x).strip()
            typ="individual"
        else:
            name=(vals.get("FIRST_NAME") or vals.get("NAME") or [""])[0]
            typ="entity"
        ext=(vals.get("REFERENCE_NUMBER") or vals.get("DATAID") or [""])[0]
        rec={
            "external_id":ext or hashlib.sha1(name.encode()).hexdigest()[:20],
            "primary_name":name,
            "listed_entity_type":typ,
            "programmes":_sx_split_values((vals.get("UN_LIST_TYPE") or [""])[0]),
            "aliases":[],
            "identifiers":[],
            "addresses":[],
            "remarks":(vals.get("COMMENTS1") or [None])[0],
            "source_list":source_list,
            "designation_date":_sx_date((vals.get("LISTED_ON") or [None])[0]),
            "last_updated_date":_sx_date((vals.get("LAST_DAY_UPDATED") or [None])[0]),
            "raw_record":{"xml_tag":ln},
        }
        for a in e.iter():
            aln=_sx_local(a.tag)
            if aln in {"INDIVIDUAL_ALIAS","ENTITY_ALIAS"}:
                av=next((_sx_text(y) for y in a if _sx_local(y.tag)=="ALIAS_NAME"),None)
                aq=next((_sx_text(y) for y in a if _sx_local(y.tag)=="QUALITY"),None)
                if av: rec["aliases"].append({"alias":av,"alias_type":aq})
            elif aln in {"INDIVIDUAL_ADDRESS","ENTITY_ADDRESS"}:
                ad={_sx_local(y.tag):_sx_text(y) for y in a}
                rec["addresses"].append({
                    "line1":ad.get("STREET"),"city":ad.get("CITY"),"region":ad.get("STATE_PROVINCE"),
                    "postal_code":ad.get("ZIP_CODE"),"country":ad.get("COUNTRY")
                })
        if name:
            records.append(rec)
    return records


def _sx_parse_csv(data, source_key):
    df=pd.read_csv(io.BytesIO(data),dtype=object,keep_default_na=False)
    recs=[]
    cols={_sx_norm_col(c):c for c in df.columns}
    if source_key=="UK Sanctions List":
        groups={}
        for _,r in df.iterrows():
            d=r.to_dict()
            ext=_sx_first(d,"Unique ID","UK Sanctions List Ref") or hashlib.sha1(json.dumps(d,sort_keys=True,default=str).encode()).hexdigest()[:20]
            groups.setdefault(ext,[]).append(d)
        for ext,rows in groups.items():
            prim=next((x for x in rows if str(_sx_first(x,"Name type") or "").casefold()=="primary name"),rows[0])
            typ=_sx_entity_type(_sx_first(prim,"Individual, Entity, Ship","Group Type"))
            def nm(d):
                parts=[_sx_first(d,f"Name {i}") for i in range(1,7)]
                return " ".join(x for x in parts if x).strip()
            name=nm(prim)
            rec={
                "external_id":ext,"primary_name":name or ext,"listed_entity_type":typ,
                "programmes":list(dict.fromkeys(x for x in [_sx_first(q,"Regime Name","Regime") for q in rows] if x)),
                "aliases":[],"identifiers":[],"addresses":[],"remarks":_sx_first(prim,"Other Information","UK Statement of Reasons"),
                "source_list":"UKSL","designation_date":_sx_date(_sx_first(prim,"Date Designated")),
                "last_updated_date":_sx_date(_sx_first(prim,"Last Updated")),"raw_record":prim,
            }
            for q in rows:
                n=nm(q)
                nt=str(_sx_first(q,"Name type") or "").casefold()
                if n and n!=name and nt in {"alias","primary name variation"}:
                    rec["aliases"].append({"alias":n,"alias_type":nt})
            for field,itype in [("IMO number","IMO"),("Passport number","PASSPORT"),("National Identifier number","NATIONAL_ID"),("Business registration number (s)","REGISTRATION"),("UN Reference Number","UN_REFERENCE")]:
                for v in _sx_split_values(_sx_first(prim,field)):
                    rec["identifiers"].append({"type":itype,"value":v})
            addr=[_sx_first(prim,f"Address Line {i}") for i in range(1,7)]
            if any(addr) or _sx_first(prim,"Address Country"):
                rec["addresses"].append({"line1":"; ".join(x for x in addr[:3] if x),"line2":"; ".join(x for x in addr[3:] if x),
                    "postal_code":_sx_first(prim,"Address Postal Code"),"country":_sx_first(prim,"Address Country")})
            rec["flag"]=_sx_first(prim,"Current believed flag of ship")
            rec["subtype"]=_sx_first(prim,"Type of ship")
            recs.append(rec)
        return recs

    # OFAC legacy CSV primary-name files.
    if source_key.startswith("OFAC"):
        for _,r in df.iterrows():
            d=r.to_dict()
            ext=_sx_first(d,"uid","ent_num","id","unique_id") or str(r.name)
            name=_sx_first(d,"sdn_name","name","primary_name")
            typ=_sx_entity_type(_sx_first(d,"sdn_type","type"))
            prog=_sx_first(d,"program","programs","program_name")
            remarks=_sx_first(d,"remarks","comments")
            if not name: continue
            recs.append({
                "external_id":ext,"primary_name":name,"listed_entity_type":typ,
                "programmes":_sx_split_values(prog),"aliases":[],"identifiers":[],
                "addresses":[],"remarks":remarks,"source_list":"SDN" if source_key=="OFAC SDN" else "NON-SDN",
                "raw_record":d,
            })
        return recs

    # EU / generic sanctions CSV mapper.
    for _,r in df.iterrows():
        d=r.to_dict()
        ext=_sx_first(d,"logical_id","entity_logical_id","eu_reference_number","reference_number","id","unique_id")
        name=_sx_first(d,"name_whole_name","whole_name","name","full_name","primary_name")
        if not name:
            # try assembling common name-part fields
            parts=[_sx_first(d,x) for x in ("name_first_name","name_middle_name","name_last_name")]
            name=" ".join(x for x in parts if x).strip()
        if not name: continue
        typ=_sx_entity_type(_sx_first(d,"subject_type","entity_type","type","individual_entity_ship"))
        prog=_sx_first(d,"regulation_programme","programme","program","regime","regime_name")
        rec={
            "external_id":ext or hashlib.sha1((name+"|"+str(prog)).encode()).hexdigest()[:20],
            "primary_name":name,"listed_entity_type":typ,
            "programmes":_sx_split_values(prog),"aliases":[],"identifiers":[],"addresses":[],
            "remarks":_sx_first(d,"remark","remarks","other_information"),
            "source_list":"EU-FSF" if source_key.startswith("EU") else source_key,
            "designation_date":_sx_date(_sx_first(d,"listing_date","date_designated","listed_on")),
            "last_updated_date":_sx_date(_sx_first(d,"last_updated","last_day_updated")),
            "raw_record":d,
        }
        imo=_sx_first(d,"imo_number","imo")
        if imo: rec["identifiers"].append({"type":"IMO","value":imo})
        recs.append(rec)
    return recs


def _sx_parse_xml(data, source_key, cfg):
    if source_key.startswith("OFAC"):
        return _sx_parse_ofac_xml(data,cfg["source_list"])
    if source_key.startswith("UN "):
        return _sx_parse_un_xml(data,cfg["source_list"])
    # UK/EU XML: flatten repeating likely record elements; UK is better via CSV.
    root=ET.fromstring(data)
    records=[]
    candidates=[e for e in root.iter() if _sx_local(e.tag).casefold() in {"designation","designatedperson","sanctionentity","entity","record"}]
    for e in candidates:
        flat={}
        for x in e.iter():
            t=_sx_text(x)
            if t and len(list(x))==0:
                flat.setdefault(_sx_local(x.tag),t)
        name=_sx_first(flat,"Name 6","WholeName","wholeName","Name","FullName","primary_name")
        if not name: continue
        ext=_sx_first(flat,"Unique ID","logicalId","LogicalId","ReferenceNumber","ID") or hashlib.sha1(name.encode()).hexdigest()[:20]
        typ=_sx_entity_type(_sx_first(flat,"Individual, Entity, Ship","subjectType","EntityType","Type"))
        records.append({
            "external_id":ext,"primary_name":name,"listed_entity_type":typ,
            "programmes":_sx_split_values(_sx_first(flat,"Regime Name","programme","Program")),
            "aliases":[],"identifiers":[],"addresses":[],"remarks":_sx_first(flat,"Other Information","Remark"),
            "source_list":cfg["source_list"],"raw_record":flat,
        })
    return records


def _sx_parse_upload(upload, source_key):
    cfg=SANCTIONS_SOURCE_CATALOG[source_key]
    data=upload.getvalue()
    name=upload.name.lower()
    if name.endswith(".zip"):
        out=[]
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for n in z.namelist():
                if n.lower().endswith((".xml",".csv")):
                    fake=type("Upload",(),{"name":n,"getvalue":lambda self,nn=n: z.read(nn)})()
                    out.extend(_sx_parse_upload(fake,source_key))
        return out
    if name.endswith(".xml"):
        return _sx_parse_xml(data,source_key,cfg)
    if name.endswith(".csv"):
        return _sx_parse_csv(data,source_key)
    if name.endswith(".ods"):
        df=pd.read_excel(io.BytesIO(data),engine="odf",dtype=object)
        b=df.to_csv(index=False).encode("utf-8")
        fake=type("Upload",(),{"name":"converted.csv","getvalue":lambda self:b})()
        return _sx_parse_csv(b,source_key)
    if name.endswith(".xlsx"):
        df=pd.read_excel(io.BytesIO(data),dtype=object)
        b=df.to_csv(index=False).encode("utf-8")
        return _sx_parse_csv(b,source_key)
    raise ValueError(f"Unsupported bulk sanctions format: {upload.name}")


def _sx_load_records(source_key, records):
    cfg=SANCTIONS_SOURCE_CATALOG[source_key]
    authority_id=_sx_authority(cfg)
    source_id=_sx_source(cfg)
    eindex=_canonical_entity_index()
    vindex=_sx_mobile_index()

    stats={"records":0,"designations_upserted":0,"canonical_created_or_linked":0,
           "identifiers":0,"aliases":0,"addresses":0,"links":0,"exceptions":0,"errors":[]}

    for rec in records:
        try:
            stats["records"]+=1
            programmes=rec.get("programmes") or ["UNSPECIFIED"]
            programme_id=_sx_programme(authority_id,programmes[0],cfg.get("official_page"))
            ext=str(rec.get("external_id") or "").strip()
            if not ext:
                ext=hashlib.sha1((rec["primary_name"]+"|"+cfg["source_list"]).encode()).hexdigest()[:24]

            existing=(sb.table("pc_sanctions_designations")
                      .select("sanctions_designation_id")
                      .eq("sanctions_authority_id",authority_id)
                      .eq("source_list",cfg["source_list"])
                      .eq("source_external_id",ext)
                      .limit(1).execute().data or [])

            drow={
                "sanctions_authority_id":authority_id,
                "sanctions_programme_id":programme_id,
                "source_id":source_id,
                "source_list":cfg["source_list"],
                "source_external_id":ext,
                "listed_entity_type":rec.get("listed_entity_type") or "entity",
                "primary_name":rec["primary_name"],
                "normalized_name":_canon_name_key(rec["primary_name"]),
                "designation_date":rec.get("designation_date"),
                "last_updated_date":rec.get("last_updated_date"),
                "status":"active",
                "remarks":rec.get("remarks"),
                "source_url":cfg.get("official_page"),
                "raw_record":rec.get("raw_record") or {},
                "last_seen_at":pd.Timestamp.utcnow().isoformat(),
                "metadata":{"programmes":programmes,"loader_build":LOADER_BUILD},
            }
            drow={k:v for k,v in drow.items() if v is not None}
            if existing:
                did=existing[0]["sanctions_designation_id"]
                sb.table("pc_sanctions_designations").update(drow).eq("sanctions_designation_id",did).execute()
            else:
                did=sb.table("pc_sanctions_designations").insert(drow).execute().data[0]["sanctions_designation_id"]
            stats["designations_upserted"]+=1

            for p in programmes[1:]:
                _sx_programme(authority_id,p,cfg.get("official_page"))

            for ident in rec.get("identifiers") or []:
                iv=str(ident.get("value") or "").strip()
                if not iv: continue
                it=_sx_id_type(ident.get("type"))
                row={"sanctions_designation_id":did,"identifier_type":it,"identifier_value":iv,
                     "country":ident.get("country"),"issuing_authority":ident.get("issuing_authority"),
                     "is_primary":it in {"IMO","MMSI","UN_REFERENCE"},
                     "metadata":{"loader_build":LOADER_BUILD}}
                row={k:v for k,v in row.items() if v is not None}
                sb.table("pc_sanctions_identifiers").upsert(
                    row,on_conflict="sanctions_designation_id,identifier_type,identifier_value"
                ).execute()
                stats["identifiers"]+=1

            for a in rec.get("aliases") or []:
                av=str(a.get("alias") or "").strip()
                if not av: continue
                hit=(sb.table("pc_sanctions_aliases").select("sanctions_alias_id")
                     .eq("sanctions_designation_id",did).eq("alias",av).limit(1).execute().data or [])
                if not hit:
                    sb.table("pc_sanctions_aliases").insert({
                        "sanctions_designation_id":did,"alias":av,
                        "normalized_alias":_canon_name_key(av),"alias_type":a.get("alias_type"),
                        "metadata":{"loader_build":LOADER_BUILD}
                    }).execute()
                    stats["aliases"]+=1

            for ad in rec.get("addresses") or []:
                sig="|".join(str(ad.get(k) or "").strip() for k in ("line1","line2","city","region","postal_code","country"))
                if not sig.replace("|",""): continue
                hit=(sb.table("pc_sanctions_addresses").select("sanctions_address_id,metadata")
                     .eq("sanctions_designation_id",did).limit(200).execute().data or [])
                if not any((x.get("metadata") or {}).get("address_signature")==sig for x in hit):
                    row={"sanctions_designation_id":did,**{k:ad.get(k) for k in ("line1","line2","city","region","postal_code","country")},
                         "metadata":{"address_signature":sig,"loader_build":LOADER_BUILD}}
                    sb.table("pc_sanctions_addresses").insert(row).execute()
                    stats["addresses"]+=1

            if rec.get("listed_entity_type")=="vessel":
                ltype,lid,mm,conf=_sx_ensure_vessel(rec,source_id,vindex)
            else:
                ltype,lid,mm,conf=_sx_ensure_entity(rec,source_id,eindex)

            if lid:
                stats["canonical_created_or_linked"]+=1
                hit=(sb.table("pc_sanctions_links").select("sanctions_link_id")
                     .eq("sanctions_designation_id",did)
                     .eq("linked_type",ltype).eq("linked_id",lid)
                     .limit(1).execute().data or [])
                linkrow={
                    "sanctions_designation_id":did,"linked_type":ltype,"linked_id":lid,
                    "linked_name":rec["primary_name"],"relationship_type":"direct_designation",
                    "is_direct_designation":True,"match_method":mm,"match_confidence":conf,
                    "review_status":"confirmed","source_id":source_id,
                    "metadata":{"loader_build":LOADER_BUILD},
                }
                if hit:
                    sb.table("pc_sanctions_links").update(linkrow).eq("sanctions_link_id",hit[0]["sanctions_link_id"]).execute()
                else:
                    sb.table("pc_sanctions_links").insert(linkrow).execute()
                    stats["links"]+=1
            else:
                stats["exceptions"]+=1
        except Exception as exc:
            stats["exceptions"]+=1
            stats["errors"].append({"name":rec.get("primary_name"),"error":str(exc)})
    return stats


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
        "Load a package once. Existing vessels resolve by IMO, existing companies by exact name/alias, missing companies are created once, and vessel-company graph links follow automatically."
    )
    st.caption(f"Loader build: `{LOADER_BUILD}`")
    st.success("V34: graph-closure repair. Event parents can resolve through package-local canonical mappings, graph endpoints can close through their staged parent payloads, and unresolved graph rows record an exact endpoint reason instead of remaining opaque PENDING rows.")
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


        # ------------------------------------------------------------------
        # V30 — persistent job recovery. This panel is intentionally ABOVE
        # the uploader so a Streamlit reboot never forces a package re-upload.
        # Jobs/staged rows live in Supabase, not Streamlit session state.
        # ------------------------------------------------------------------
        st.markdown("### Resume an existing ingestion job")
        st.caption(
            "Recent canonical jobs are stored in Supabase. Select a job below to inspect or retry it "
            "without uploading the original package again."
        )

        _recent_jobs=_canonical_jobs(50)
        if _recent_jobs:
            _job_options=[]
            _job_summaries={}
            _first_unresolved_idx=None

            for _i,_j in enumerate(_recent_jobs):
                _jid=str(_j.get("ingestion_job_id") or "")
                _summ,_by=_canonical_job_summary(_jid)
                _job_summaries[_jid]=(_summ,_by)
                _created=str(_j.get("created_at") or "")[:19].replace("T"," ")
                _title=str(_j.get("title") or _j.get("job_type") or "Canonical ingestion")
                _status=str(_j.get("status") or "unknown")
                _label=(
                    f"{_created} · {_title} · {_status} · "
                    f"{_summ.get('applied',0)}/{_summ.get('total',0)} applied · "
                    f"{_summ.get('review',0)} review"
                )
                _job_options.append((_label,_jid))
                if _first_unresolved_idx is None and int(_summ.get("review") or 0)>0:
                    _first_unresolved_idx=_i

            # Default to the newest job that still needs work; otherwise newest job.
            _default_idx=_first_unresolved_idx if _first_unresolved_idx is not None else 0
            _selected_label=st.selectbox(
                "Recent ingestion job",
                [x[0] for x in _job_options],
                index=_default_idx,
                key="canonical_resume_job_selector_v30"
            )
            _selected_jid=dict(_job_options).get(_selected_label)
            _selected_job=next(
                (x for x in _recent_jobs if str(x.get("ingestion_job_id") or "")==str(_selected_jid)),
                {}
            )
            _selected_summary,_selected_by_table=_job_summaries.get(
                str(_selected_jid),
                ({"total":0,"applied":0,"review":0,"invalid":0,"broken":0},[])
            )

            _c1,_c2,_c3,_c4=st.columns(4)
            _c1.metric("Total",_selected_summary.get("total",0))
            _c2.metric("Applied",_selected_summary.get("applied",0))
            _c3.metric("Review",_selected_summary.get("review",0))
            _c4.metric("Broken refs",_selected_summary.get("broken",0))

            if _selected_by_table:
                with st.expander("Job table/status breakdown",expanded=False):
                    dataframe(_selected_by_table)

            _resume_review=_canonical_review_rows(_selected_jid,3000)
            if _resume_review:
                _reason_counts={}
                for _rr in _resume_review:
                    _reason=str(
                        _rr.get("resolution_method")
                        or _rr.get("resolution_status")
                        or "UNKNOWN"
                    )
                    _key=(_rr.get("target_table") or "unknown",_reason)
                    _reason_counts[_key]=_reason_counts.get(_key,0)+1

                with st.expander("Unresolved reasons / records",expanded=False):
                    dataframe([
                        {"target_table":k[0],"reason":k[1],"count":v}
                        for k,v in sorted(
                            _reason_counts.items(),
                            key=lambda x:(x[0][0],-x[1],x[0][1])
                        )
                    ])
                    dataframe(_resume_review)

                if st.button(
                    "🛠 Repair unresolved rows in selected job",
                    type="primary",
                    use_container_width=True,
                    key=f"canonical_resume_retry_v30_{_selected_jid}"
                ):
                    try:
                        with st.status(
                            "Repairing observation IDs, event links and relationships in the existing job…",
                            expanded=True
                        ) as _status:
                            _result=_v33_repair_existing_job(_selected_jid)
                            st.session_state[f"graph_repair_result_{_selected_jid}"]=_result
                            st.write(_result)
                            _status.update(
                                label="Graph repair complete",
                                state="complete",
                                expanded=True
                            )
                    except Exception as _exc:
                        st.exception(_exc)
            _last_repair=st.session_state.get(f"graph_repair_result_{_selected_jid}")
            if _last_repair:
                st.markdown("#### Last graph-repair diagnostics")
                st.json(_last_repair)
                _pf=_last_repair.get("preflight") if isinstance(_last_repair,dict) else {}
                if isinstance(_pf,dict) and _pf.get("pc_object_exists_route") is False:
                    st.warning(
                        "Database route endpoint support is still missing. "
                        "Run migration `054_route_graph_endpoint_support.sql`, then run graph repair again."
                    )

            with st.expander("Selected job metadata",expanded=False):
                st.json(_selected_job)
        else:
            st.info("No canonical ingestion jobs are currently stored in Supabase.")

        st.divider()
        st.markdown("### Load a new package")

        up=st.file_uploader(
            "Canonical package — Excel / CSV / JSON / JSONL",
            type=None,
            key="canonical_loader_upload_v20",
            help="Accepted extensions: .xlsx, .xls, .csv, .json, .jsonl, .ndjson"
        )

        if up:
            try:
                supported_ext=(".xlsx",".xls",".csv",".json",".jsonl",".ndjson")
                if not str(up.name).lower().endswith(supported_ext):
                    st.error("Unsupported file type. Use Excel, CSV, JSON, JSONL or NDJSON.")
                    st.stop()
                sections,file_hash=_parse_multitable_upload(up)
                sections={k:v for k,v in sections.items() if not v.empty}

                # V23: bind the result panel to the CURRENT upload, not a prior job
                # left in Streamlit session state.
                current_hash=str(file_hash)
                previous_hash=str(st.session_state.get("canonical_current_upload_hash") or "")
                if previous_hash != current_hash:
                    st.session_state["canonical_current_upload_hash"]=current_hash
                    st.session_state.pop("canonical_last_job",None)
                    st.session_state.pop("canonical_last_job_hash",None)
                    st.session_state.pop("canonical_last_load_error",None)

                recognized=[]
                ignored=[]
                for section,df in sections.items():
                    target,include_default,reason=_canonical_section_target(section,df)
                    if include_default:
                        recognized.append(section)
                    else:
                        ignored.append({"sheet":section,"rows":len(df),"reason":reason})

                st.caption(
                    f"{len(recognized)} recognized data section(s) · "
                    f"{len(ignored)} excluded/reference section(s) · SHA-256 {file_hash[:16]}…"
                )
                if ignored:
                    with st.expander("Excluded/reference sheets",expanded=False):
                        dataframe(ignored)

                registered_tables=_canonical_registered_tables()
                if not registered_tables:
                    st.error(
                        "No canonical loader target tables are registered in pc_meta_entity_types. "
                        "Check System metadata before loading."
                    )
                    st.stop()

                configs={}
                # IMPORTANT: widget keys include the uploaded file hash + sheet name.
                # Reusing numeric keys across different workbooks caused Streamlit
                # session state to retain the PREVIOUS workbook's target-table choice.
                # That could shift sheets one position, e.g. assets -> mobile_assets,
                # mobile_assets -> events, events -> event_links.
                file_key=str(file_hash)[:16]
                for idx,(section,df) in enumerate(sections.items()):
                    suggested,include_default,reason=_canonical_section_target(section,df)
                    section_key=re.sub(r"[^a-zA-Z0-9_]+","_",str(section)).strip("_") or f"sheet_{idx}"
                    widget_ns=f"{file_key}_{section_key}"
                    with st.expander(
                        f"{section} · {len(df):,} rows · {'DATA' if include_default else 'EXCLUDED'}",
                        expanded=include_default
                    ):
                        if suggested not in registered_tables:
                            include_default=False

                        include=st.checkbox(
                            "Include this section",
                            value=include_default,
                            key=f"canon_include_{widget_ns}"
                        )

                        default_target=suggested if suggested in registered_tables else registered_tables[0]
                        target=st.selectbox(
                            "Canonical target",
                            registered_tables,
                            index=registered_tables.index(default_target),
                            key=f"canon_target_{widget_ns}",
                            disabled=not include,
                        )

                        registered_type=_canonical_target_entity_type(target)
                        st.caption(
                            f"{reason} · staging type: {registered_type}"
                            if include else reason
                        )
                        native=_loader_native_section(df)
                        if native:
                            edited=None
                            st.success(
                                "Loader-native package detected. Nested payload objects will be staged exactly as supplied; "
                                "natural_key/source_record_key/action/confidence are treated as staging controls."
                            )
                            preview=[]
                            for rr in df.head(6).to_dict("records"):
                                pv=dict(rr)
                                pv["payload"]=_jsonish(pv.get("payload"))
                                preview.append(pv)
                            st.caption("Native package preview")
                            dataframe(preview)
                        else:
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
                                key=f"canon_map_{widget_ns}"
                            )
                            st.caption("Preview")
                            dataframe(df.head(6).to_dict("records"))
                        configs[section]={
                            "include":include,
                            "target":target,
                            "df":df,
                            "mapping":edited,
                            "native":native,
                        }

                included_plan=[
                    {
                        "sheet":k,
                        "target_table":v["target"],
                        "rows":len(v["df"]),
                        "mode":"loader-native" if v.get("native") else "mapped-flat",
                    }
                    for k,v in configs.items()
                    if v.get("include")
                ]
                if included_plan:
                    st.markdown("### Package plan")
                    dataframe(included_plan)
                    planned_rows=sum(x["rows"] for x in included_plan)
                    st.caption(
                        f"{planned_rows:,} source rows selected across "
                        f"{len(included_plan)} sheet(s)."
                    )

                    # Sanity check: the target should normally correspond to the
                    # recognized sheet type. This catches accidental manual remapping.
                    suspicious=[]
                    for sheet_name,cfg in configs.items():
                        if not cfg.get("include"):
                            continue
                        expected,_,_= _canonical_section_target(sheet_name,cfg["df"])
                        if expected and expected != cfg.get("target"):
                            suspicious.append({
                                "sheet":sheet_name,
                                "expected_target":expected,
                                "selected_target":cfg.get("target"),
                                "rows":len(cfg["df"]),
                            })
                    if suspicious:
                        st.error(
                            "One or more sheets are mapped to an unexpected canonical table. "
                            "Correct these mappings before loading."
                        )
                        dataframe(suspicious)
                else:
                    st.warning("No data sheets are selected for this package.")

                st.markdown("### What happens when you load")
                st.caption(
                    "The loader reads the package dependency path first. Canonical parent objects are resolved/upserted "
                    "before child rows and graph edges are introduced. Package-local IDs are then rewritten to canonical IDs "
                    "and relationships/event links are applied automatically."
                )
                st.info(
                    "AI/research packages can now be supplied directly as JSON/JSONL records with target_table, "
                    "natural_key and payload. This is the preferred path for company/fleet packages such as NORDEN: "
                    "entities and vessels resolve first, then owner/operator/manager/charter relationships use the "
                    "same package-local IDs and are mapped by the V5 processor."
                )
                st.info(
                    "The seven core canonical sheets — entities, assets, mobile assets, events, relationships, transaction participants and "
                    "event links — are always supported with their established FK-safe staging types. "
                    "Optional tables such as transactions/routes still require explicit metadata registration."
                )

                has_suspicious=bool(locals().get("suspicious",[]))
                if st.button(
                    "▶ Load and process canonical package",
                    type="primary",
                    use_container_width=True,
                    key=f"canonical_load_process_{str(file_hash)[:16]}",
                    disabled=has_suspicious
                ):
                    with st.status("Loading package into the canonical ingestion engine…",expanded=True) as status:
                        job=None
                        jid=None
                        try:
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

                            # Bind UI immediately to this job, even if staging later fails.
                            st.session_state["canonical_last_job"]=str(jid)
                            st.session_state["canonical_last_job_hash"]=str(file_hash)
                            st.session_state.pop("canonical_last_load_error",None)

                            staged=_canonical_stage_records(jid,configs)
                            deferred_records=staged.pop("_deferred_records",[])
                            st.write("Staged package",staged)

                            # Explicit guard: a non-empty selected package must never
                            # silently proceed with zero staged/deferred rows.
                            expected_rows=sum(
                                len(v["df"]) for v in configs.values() if v.get("include")
                            )
                            actual_rows=int(staged.get("rows",0) or 0)
                            if expected_rows > 0 and actual_rows == 0:
                                raise RuntimeError(
                                    f"Current upload selected {expected_rows} row(s) but staged 0. "
                                    "The loader stopped before processing so the prior job cannot be mistaken for this upload."
                                )

                            result=_canonical_process_job(jid,deferred_records)
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
                            err=str(exc)
                            st.session_state["canonical_last_load_error"]=err
                            if jid:
                                try:
                                    sb.table("pc_ingestion_jobs").update({
                                        "status":"failed",
                                        "completed_at":pd.Timestamp.utcnow().isoformat(),
                                        "error_text":err,
                                    }).eq("ingestion_job_id",str(jid)).execute()
                                except Exception:
                                    pass
                            status.update(
                                label="Current upload failed before completion",
                                state="error",
                                expanded=True
                            )
                            st.error("This error belongs to the CURRENT upload; the previous load is not being displayed as its result.")
                            st.exception(exc)

                last=st.session_state.get("canonical_last_job")
                last_hash=str(st.session_state.get("canonical_last_job_hash") or "")
                current_hash=str(file_hash)

                if last and last_hash == current_hash:
                    st.markdown("### Current upload result")
                    summ,by_table=_canonical_job_summary(last)
                    m1,m2,m3,m4=st.columns(4)
                    m1.metric("Total",summ.get("total",0))
                    m2.metric("Applied",summ.get("applied",0))
                    m3.metric("Review",summ.get("review",0))
                    m4.metric("Broken refs",summ.get("broken",0))
                    dataframe(by_table)

                    if summ.get("review",0):
                        review_rows=_canonical_review_rows(last,2000)
                        reason_counts={}
                        for rr in review_rows:
                            reason=str(
                                rr.get("resolution_method")
                                or rr.get("resolution_status")
                                or "UNKNOWN"
                            )
                            key=(rr.get("target_table") or "unknown",reason)
                            reason_counts[key]=reason_counts.get(key,0)+1

                        st.markdown("#### Exact unresolved reasons")
                        dataframe([
                            {
                                "target_table":k[0],
                                "reason":k[1],
                                "count":v,
                            }
                            for k,v in sorted(
                                reason_counts.items(),
                                key=lambda x:(x[0][0],-x[1],x[0][1])
                            )
                        ])

                        with st.expander("Inspect unresolved records",expanded=False):
                            dataframe(review_rows)

                        if st.button(
                            "↻ Retry unresolved rows in this package",
                            type="primary",
                            use_container_width=True,
                            key=f"retry_last_canonical_{last}"
                        ):
                            try:
                                with st.status(
                                    "Retrying unresolved canonical objects and dependent graph edges…",
                                    expanded=True
                                ) as status:
                                    result=_v33_repair_existing_job(last)
                                    st.write(result)
                                    status.update(
                                        label="Retry complete — refreshing",
                                        state="complete",
                                        expanded=False
                                    )
                                st.rerun()
                            except Exception as exc:
                                st.exception(exc)

                elif up:
                    st.info("No result exists yet for this current upload. The loader will not show an older job here.")
                    if st.session_state.get("canonical_last_load_error"):
                        st.error(st.session_state["canonical_last_load_error"])

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
        "Canonical exceptions",
        "Only records the canonical identity processor could not resolve safely appear here. "
        "For normal staged records, approvals and apply actions, use Review Queue."
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


elif page=="Sanctions Bulk Load":
    title(
        "Sanctions bulk load",
        "Load official sanctions files directly into the canonical model. Existing companies/vessels are reused; missing canonical keys are created; only genuine identity collisions are held as exceptions."
    )
    if not sb:
        st.error("Supabase service connection required.")
    else:
        st.markdown("### Official source catalogue")
        cat_rows=[]
        for k,v in SANCTIONS_SOURCE_CATALOG.items():
            cat_rows.append({
                "Source":k,
                "Preferred machine format":v["preferred"],
                "Accepted by loader":", ".join(x.upper() for x in v["formats"]),
                "Official page":v.get("official_page") or "",
            })
        dataframe(cat_rows)

        st.info(
            "Recommended: use **XML** for OFAC and UN when possible, **CSV or XML** for the UK, "
            "and **CSV 1.1 or XML 1.1** for the EU. PDF is for human reference and is intentionally "
            "not used as a bulk machine-load format."
        )

        source_key=st.selectbox("Sanctions source / list",list(SANCTIONS_SOURCE_CATALOG.keys()))
        cfg=SANCTIONS_SOURCE_CATALOG[source_key]
        st.caption(f"Canonical source: `{cfg['source_id']}` · list: `{cfg['source_list']}`")

        uploads=st.file_uploader(
            "Official sanctions file(s)",
            type=["xml","csv","zip","ods","xlsx"],
            accept_multiple_files=True,
            key="sanctions_bulk_files",
            help="For OFAC CSV packages you may upload multiple related CSV files or a ZIP. XML is preferred because it preserves richer aliases/identifiers in one file."
        )

        preview_records=[]
        parse_errors=[]
        if uploads:
            for up in uploads:
                try:
                    preview_records.extend(_sx_parse_upload(up,source_key))
                except Exception as exc:
                    parse_errors.append({"file":up.name,"error":str(exc)})

            c1,c2,c3,c4=st.columns(4)
            c1.metric("Files",len(uploads))
            c2.metric("Parsed records",len(preview_records))
            c3.metric("Vessels",sum(1 for r in preview_records if r.get("listed_entity_type")=="vessel"))
            c4.metric("Parse errors",len(parse_errors))

            if preview_records:
                dataframe([{
                    "external_id":r.get("external_id"),
                    "name":r.get("primary_name"),
                    "type":r.get("listed_entity_type"),
                    "programmes":"; ".join(r.get("programmes") or []),
                    "identifiers":len(r.get("identifiers") or []),
                    "aliases":len(r.get("aliases") or []),
                } for r in preview_records[:250]])

            if parse_errors:
                st.warning("Some files could not be parsed.")
                dataframe(parse_errors)

            if preview_records and st.button(
                f"Load {len(preview_records):,} sanctions record(s) → canonical model",
                type="primary",
                use_container_width=True,
                key="sanctions_bulk_apply"
            ):
                with st.spinner("Loading sanctions designations and canonical links..."):
                    rep=_sx_load_records(source_key,preview_records)
                st.success(
                    f"Processed {rep['records']:,} designation record(s) · "
                    f"{rep['designations_upserted']:,} designation upsert(s) · "
                    f"{rep['canonical_created_or_linked']:,} canonical object(s) linked/created · "
                    f"{rep['links']:,} new sanctions link(s) · "
                    f"{rep['exceptions']:,} exception(s)."
                )
                c1,c2,c3,c4=st.columns(4)
                c1.metric("Identifiers",rep["identifiers"])
                c2.metric("Aliases",rep["aliases"])
                c3.metric("Addresses",rep["addresses"])
                c4.metric("Exceptions",rep["exceptions"])
                if rep["errors"]:
                    st.markdown("#### Exceptions")
                    dataframe(rep["errors"][:500])

        st.markdown("### What the loader does")
        st.code(
            "designation file → canonical company/person/vessel key → sanctions designation "
            "→ identifiers / aliases / addresses → direct-designation link → provenance",
            language="text"
        )
        st.caption(
            "Idempotent rule: the same authority + source list + external ID updates the existing designation. "
            "Vessels are matched IMO → MMSI → exact name; other targets use exact canonical/alias name. "
            "If no canonical object exists, one is created."
        )

elif page=="Port Enrichment":
    title(
        "Port enrichment",
        "Research and stage a connected port update: canonical port attributes, terminals, berths, capabilities, throughput, projects, contracts, financing, services and evidence."
    )
    st.caption(f"Loader build: `{LOADER_BUILD}`")

    if not sb:
        st.error("Supabase service connection required.")
    else:
        try:
            ports=safe_rows(
                sb,"pc_assets",
                "asset_id,name,asset_type,subtype,country,region_city,status,source_id,metadata",
                20000
            )
        except Exception:
            ports=[]

        pdf=pd.DataFrame(ports)
        if not pdf.empty:
            mask=(
                pdf.get("asset_type",pd.Series(index=pdf.index,dtype=str)).fillna("").astype(str).str.contains("port",case=False,na=False)
                | pdf.get("subtype",pd.Series(index=pdf.index,dtype=str)).fillna("").astype(str).str.contains("port|harbour|harbor|seaport",case=False,na=False,regex=True)
            )
            pdf=pdf[mask].copy()

        if pdf.empty:
            st.info("No canonical port assets found.")
        else:
            q=st.text_input("Find port",placeholder="Rotterdam, Montreal, Jebel Ali...",key="port_enrichment_q")
            pview=pdf.copy()
            if q.strip():
                m=pd.Series(False,index=pview.index)
                for c in ["name","country","region_city","asset_id"]:
                    if c in pview.columns:
                        m |= pview[c].fillna("").astype(str).str.contains(q,case=False,na=False,regex=False)
                pview=pview[m].copy()

            options=pview.reset_index(drop=True)
            pick=st.selectbox(
                "Canonical port",
                range(len(options)),
                format_func=lambda i:(
                    f"{options.iloc[i].get('name','')} · "
                    f"{options.iloc[i].get('country','')} · "
                    f"{options.iloc[i].get('asset_id','')}"
                ),
                key="port_enrichment_pick"
            )
            port=options.iloc[pick].to_dict()
            pid=str(port.get("asset_id") or "")
            pname=str(port.get("name") or "")
            pcountry=str(port.get("country") or "")

            # Existing connected records.
            existing_terminals=safe_rows(
                sb,"pc_terminal_details","*",5000
            )
            tdf=pd.DataFrame(existing_terminals)
            if not tdf.empty and "parent_port_asset_id" in tdf.columns:
                tdf=tdf[tdf["parent_port_asset_id"].astype(str).eq(pid)].copy()

            tids=set(tdf.get("asset_id",pd.Series(dtype=str)).dropna().astype(str))
            bdf=pd.DataFrame(safe_rows(sb,"pc_berth_details","*",10000))
            if not bdf.empty and "terminal_asset_id" in bdf.columns and tids:
                bdf=bdf[bdf["terminal_asset_id"].astype(str).isin(tids)].copy()
            else:
                bdf=bdf.iloc[0:0].copy()

            cap=pd.DataFrame(safe_rows(sb,"pc_port_capabilities","*",2000))
            if not cap.empty and "port_asset_id" in cap.columns:
                cap=cap[cap["port_asset_id"].astype(str).eq(pid)].copy()

            metrics=pd.DataFrame(safe_rows(sb,"pc_port_metrics","*",10000))
            if not metrics.empty and "port_asset_id" in metrics.columns:
                metrics=metrics[metrics["port_asset_id"].astype(str).eq(pid)].copy()

            st.markdown(f"### {pname}")
            st.caption(f"{pcountry} · `{pid}`")

            c1,c2,c3,c4=st.columns(4)
            c1.metric("Known terminals",len(tdf))
            c2.metric("Known berths",len(bdf))
            c3.metric("Capability records",len(cap))
            c4.metric("Port metrics",len(metrics))

            official_urls=st.text_area(
                "Official / authoritative URLs",
                placeholder=(
                    "Paste port authority website, terminal map/factsheet, annual report, "
                    "operator pages, statistics pages, project/tender pages — one URL per line."
                ),
                height=130,
                key="port_enrichment_urls"
            )
            url_list=_extract_urls_from_text(official_urls)

            research_scope=st.multiselect(
                "Update scope",
                [
                    "Port capabilities",
                    "Terminals",
                    "Berths",
                    "Throughput / metrics",
                    "Projects & development",
                    "Contracts / concessions",
                    "Financing",
                    "Transport services / routes",
                    "Operators / ownership",
                ],
                default=[
                    "Port capabilities","Terminals","Berths","Throughput / metrics",
                    "Projects & development","Contracts / concessions","Operators / ownership"
                ],
                key="port_enrichment_scope"
            )

            with st.expander("Existing canonical port data"):
                st.markdown("#### Port asset")
                dataframe([port])
                if not cap.empty:
                    st.markdown("#### Capabilities")
                    dataframe(cap.to_dict("records"))
                if not tdf.empty:
                    st.markdown("#### Terminals")
                    dataframe(tdf.to_dict("records"))
                if not bdf.empty:
                    st.markdown("#### Berths")
                    dataframe(bdf.to_dict("records"))

            if st.button(
                "Research port → build staged update",
                type="primary",
                use_container_width=True,
                key="port_enrichment_run"
            ):
                if not ai_configured():
                    st.error("Configure OPENAI_API_KEY and OPENAI_MODEL first.")
                else:
                    job=sb.table("pc_ingestion_jobs").insert({
                        "job_type":"PORT_ENRICHMENT",
                        "title":f"Port enrichment · {pname}",
                        "query_text":"Connected port/terminal/berth enrichment",
                        "source_scope":{
                            "port_asset_id":pid,
                            "port_name":pname,
                            "country":pcountry,
                            "scope":research_scope,
                            "seed_urls":url_list,
                        },
                        "status":"running",
                    }).execute().data[0]
                    jid=job["ingestion_job_id"]

                    canonical_context={
                        "port":port,
                        "terminals":tdf.to_dict("records") if not tdf.empty else [],
                        "berths":bdf.to_dict("records") if not bdf.empty else [],
                        "capabilities":cap.to_dict("records") if not cap.empty else [],
                        "metrics":metrics.tail(50).to_dict("records") if not metrics.empty else [],
                    }

                    prompt=f"""
Perform a connected PORT UPDATE for Power & Corridors.

CANONICAL PORT
asset_id: {pid}
name: {pname}
country: {pcountry}

REQUESTED SCOPE
{json.dumps(research_scope,ensure_ascii=False)}

SEED / OFFICIAL URLS
{json.dumps(url_list,ensure_ascii=False)}

CURRENT CANONICAL CONTEXT
{json.dumps(canonical_context,ensure_ascii=False,default=str,indent=2)}

Use current authoritative web research. Prefer the port authority, terminal
operators, government/municipal authorities, official annual/statistical reports,
tender/concession documents, terminal maps/factsheets and official carrier/service
announcements.

Build reviewable records for supported facts using:
- pc_assets for any genuinely missing terminal or berth identities;
- pc_port_capabilities for port-wide capacity/connectivity/commodity attributes;
- pc_terminal_details for terminal type/code, owner/operator/concession,
  berth_count, quay length, max draught, capacity and equipment;
- pc_berth_details for named/numbered berth length, depth, max vessel length and status;
- pc_port_metrics for dated throughput/cargo/container statistics;
- pc_project_details for port/terminal expansion or development projects;
- pc_contracts / pc_contract_participants / pc_contract_links for concessions,
  construction, dredging, cranes/equipment and service awards;
- pc_financing_* for loans, grants and project financing;
- pc_transport_services / operators / stops / changes only when authoritative
  service information supports them;
- pc_relationships for ownership/operator/terminal relationships when useful.

IMPORTANT
1. Preserve the canonical parent port ID `{pid}`. Do not create another port.
2. Do not create duplicate terminals/berths when the canonical context already
   contains the same facility.
3. Every new terminal/berth must have a pc_assets parent identity as well as its
   specialist detail record.
4. pc_terminal_details.parent_port_asset_id must be `{pid}`.
5. For a NEW terminal or berth, give the pc_assets proposal and its specialist
   detail proposal the SAME exact `natural_key` under
   metadata.asset_natural_key so the loader can bind them after staging.
6. For a berth, include metadata.terminal_name and/or terminal_asset_id only when
   the terminal match is deterministic.
7. Do not fabricate berth counts, depths, capacities, quay lengths, operators,
   concessions or throughput figures. Leave unsupported fields blank.
8. Port calls belong in pc_port_calls only when the source reports a specific
   vessel call; do not infer calls from route/service membership.
9. Do not write to pc_port_reference; it remains a source-reference layer.
10. Preserve research sources on every proposal.

Return the normal universal JSON contract with records and source provenance.
"""

                    with st.spinner(f"Researching {pname} and building staged records..."):
                        result=ai_research(
                            prompt,
                            "TRADE",
                            True,
                            output_contract=UNIVERSAL_CONTENT_OUTPUT_CONTRACT
                        )
                        result=_prepare_universal_records(
                            result,
                            url_list[0] if url_list else "",
                            None,
                            f"Port enrichment · {pname}"
                        )
                        staged,rejected,resolution=stage_ai_result(sb,jid,result)

                    sb.table("pc_ingestion_jobs").update({
                        "status":"completed",
                        "completed_at":pd.Timestamp.utcnow().isoformat(),
                        "stats":{
                            "staged_records":staged,
                            "rejected_records":rejected,
                            "resolution":resolution,
                            "port_asset_id":pid,
                        }
                    }).eq("ingestion_job_id",jid).execute()

                    st.success(
                        f"Port update staged: {staged} proposal(s), {rejected} rejected. "
                        "Next: open Review Queue → reconcile → approve READY records → apply."
                    )
                    st.session_state["pc_last_port_enrichment_job"]=str(jid)

            last_job=st.session_state.get("pc_last_port_enrichment_job")
            if last_job:
                st.info(f"Latest port enrichment job: `{last_job}`")

elif page=="Universal Content Intake":
    title(
        "Universal content intake",
        "Paste article URLs, a URL list, or a file containing URLs. Each source is preserved, resolved against canonical keys, and loaded directly into the P&C model. Facts remain provenance; only genuine ambiguity goes to review."
    )
    st.caption(f"Loader build: `{LOADER_BUILD}`")

    if not sb:
        st.error("Supabase service connection required.")
    elif not _table_exists("pc_content_ingest_items"):
        st.error("Run the Universal Content / Fact Extraction Foundation SQL first.")
    else:
        intake_tab, queue_tab, facts_tab = st.tabs(
            ["Add URLs / URL-list document","Content queue","Facts / audit trail"]
        )

        with intake_tab:
            st.markdown("### Add source material")
            mode=st.radio(
                "Input",
                ["Paste URL(s)","Upload file containing URLs"],
                horizontal=True,
                key="content_intake_mode"
            )

            urls=[]
            manifest_document_id=None
            manifest_upload=None

            if mode=="Paste URL(s)":
                raw_urls=st.text_area(
                    "URL or URL list",
                    height=180,
                    placeholder=(
                        "https://www.porttechnology.org/...\n"
                        "https://gulfnews.com/...\n"
                        "https://www.seatrade-maritime.com/..."
                    ),
                    key="content_url_text"
                )
                urls=_extract_urls_from_text(raw_urls)
            else:
                manifest_upload=st.file_uploader(
                    "Upload TXT, MD, CSV, XLSX, DOCX or PDF containing URLs",
                    type=["txt","md","csv","xlsx","xls","docx","pdf"],
                    key="content_url_manifest"
                )
                if manifest_upload:
                    try:
                        urls=_extract_urls_from_upload(manifest_upload)
                    except Exception as exc:
                        st.error(f"Could not read URL list: {exc}")

            # Manual URLs without protocol can be entered one per line.
            if mode=="Paste URL(s)" and not urls:
                for line in (st.session_state.get("content_url_text") or "").splitlines():
                    line=line.strip()
                    if line and "." in line and " " not in line:
                        n=_normalize_content_url(line)
                        if n:
                            urls.append(line)

            # Dedupe preview.
            dedup=[]
            seen=set()
            for u in urls:
                n=_normalize_content_url(u)
                if n and n not in seen:
                    seen.add(n)
                    dedup.append(u)
            urls=dedup

            c1,c2,c3=st.columns([1,1.5,1])
            product_context=c1.selectbox(
                "Product context",
                ["TRADE","INTELLIGENCE"],
                key="content_product_context"
            )
            processing_mode=c2.selectbox(
                "Processing mode",
                [
                    "Load to canonical — recommended",
                    "Queue only — instant",
                    "Research + load — web verification"
                ],
                index=0,
                key="content_processing_mode",
                help=(
                    "Load to canonical reads each source once, resolves or creates canonical keys, upserts safe records, "
                    "and leaves only genuine ambiguity for review. Queue only stores URLs. Research + load adds web verification."
                )
            )
            max_items=c3.number_input(
                "Max URLs this run",
                min_value=1,max_value=100,value=25,step=1,
                key="content_max_items"
            )

            use_web=processing_mode.startswith("Research")

            st.caption(
                f"{len(urls)} unique URL(s) detected. "
                "The source article remains evidence; structured facts are routed separately."
            )
            if urls:
                with st.expander("URL preview",expanded=False):
                    for u in urls[:100]:
                        st.write(u)

            action_label=(
                "Queue URLs now"
                if processing_mode.startswith("Queue")
                else "Load URLs to canonical model"
                if processing_mode.startswith("Load")
                else "Research + load to canonical model"
            )
            if st.button(
                action_label,
                type="primary",
                disabled=not bool(urls),
                use_container_width=True,
                key="content_ingest_run"
            ):
                if not ai_configured():
                    st.error("Configure OPENAI_API_KEY and OPENAI_MODEL first.")
                else:
                    selected=urls[:int(max_items)]
                    if manifest_upload:
                        try:
                            manifest_document_id=_save_url_manifest_document(
                                manifest_upload,selected
                            )
                        except Exception as exc:
                            st.warning(f"URL-list file could not be preserved in pc_documents: {exc}")

                    input_mode="document_url_list" if manifest_upload else (
                        "single_url" if len(selected)==1 else "url_list"
                    )

                    batch_name=(
                        Path(manifest_upload.name).stem
                        if manifest_upload
                        else f"URL intake · {len(selected)} source(s)"
                    )

                    if processing_mode.startswith("Queue"):
                        batch,items,failures=_queue_content_urls(
                            selected,
                            input_mode=input_mode,
                            product_context=product_context,
                            manifest_document_id=manifest_document_id,
                            batch_name=batch_name,
                            discovery_method="uploaded_url_list" if manifest_upload else "pasted_url",
                        )
                        results=[]
                        st.success(
                            f"Queued {len(items)} URL(s) immediately. "
                            "Open Content queue and process them in a batch when convenient."
                        )
                    else:
                        batch=_create_content_batch(
                            input_mode=input_mode,
                            batch_name=batch_name,
                            product_context=product_context,
                            research_mode=(
                                "web_enriched_direct_load" if processing_mode.startswith("Research")
                                else "direct_canonical_load"
                            ),
                            item_count=len(selected),
                            metadata={
                                "manifest_document_id":str(manifest_document_id) if manifest_document_id else None,
                                "loader_build":LOADER_BUILD,
                                "processing_mode":processing_mode,
                            }
                        )
                        batch_id=batch["content_batch_id"]
                        results=[]
                        failures=[]

                        research_mode=processing_mode.startswith("Research")
                        progress=st.progress(0.0)
                        with st.status(
                            f"{'Researching and loading' if research_mode else 'Loading'} {len(selected)} source URL(s) to canonical model…",
                            expanded=False
                        ) as status_box:
                            for num,u in enumerate(selected,1):
                                try:
                                    item=_upsert_content_url_item(
                                        batch_id,u,manifest_document_id,
                                        "uploaded_url_list" if manifest_upload else "pasted_url"
                                    )
                                    res=_load_content_item_to_canonical(
                                        batch_id,
                                        item,
                                        product_context=product_context,
                                        use_web=research_mode,
                                    )
                                    results.append(res)
                                except Exception as exc:
                                    failures.append({"url":u,"error":str(exc)})
                                    try:
                                        n=_normalize_content_url(u)
                                        if n:
                                            existing=(sb.table("pc_content_ingest_items")
                                                      .select("content_item_id")
                                                      .eq("normalized_url",n).limit(1).execute().data or [])
                                            if existing:
                                                sb.table("pc_content_ingest_items").update({
                                                    "extraction_status":"failed",
                                                    "extraction_error":str(exc),
                                                    "updated_at":pd.Timestamp.utcnow().isoformat()
                                                }).eq("content_item_id",existing[0]["content_item_id"]).execute()
                                    except Exception:
                                        pass
                                progress.progress(num/max(1,len(selected)))

                            sb.table("pc_content_ingest_batches").update({
                                "status":"completed" if not failures else "completed_with_errors",
                                "processed_count":len(results),
                                "failed_count":len(failures),
                                "completed_at":pd.Timestamp.utcnow().isoformat(),
                                "updated_at":pd.Timestamp.utcnow().isoformat(),
                                "metadata":{
                                    "manifest_document_id":str(manifest_document_id) if manifest_document_id else None,
                                    "loader_build":LOADER_BUILD,
                                    "processing_mode":processing_mode,
                                    "failures":failures[:100],
                                }
                            }).eq("content_batch_id",batch_id).execute()

                            status_box.update(
                                label=(
                                    f"{'Research + load' if research_mode else 'Canonical load'} complete · "
                                    f"{len(results)} processed"
                                    + (f" · {len(failures)} failed" if failures else "")
                                ),
                                state="complete" if not failures else "error"
                            )
                        progress.empty()

                    if results:
                        applied_total=sum(int(x.get('canonical_applied') or 0) for x in results)
                        blocked_total=sum(int(x.get('canonical_blocked') or 0) for x in results)
                        st.success(
                            f"Loaded {len(results)} source(s) · {applied_total} canonical record(s) created/updated"
                            + (f" · {blocked_total} genuine exception(s) need review" if blocked_total else " · no blocking exceptions")
                            + ". Facts were retained as provenance and do not block the load."
                        )
                        dataframe([{
                            "source":x.get("title") or x.get("content_item_id"),
                            "canonical_applied":x.get("canonical_applied",0),
                            "exceptions":x.get("canonical_blocked",0),
                            "job_id":x.get("job_id"),
                        } for x in results])
                    if failures:
                        st.warning(f"{len(failures)} source(s) need attention.")
                        dataframe(failures)

        with queue_tab:
            st.markdown("### Content ingestion queue")
            st.caption(
                "Queue URLs instantly, then load them directly into the canonical model in one action. "
                "Facts remain provenance; only genuine identity ambiguity is held for review."
            )
            q1,q2,q3=st.columns([1,1,1.4])
            queued_limit=q1.number_input(
                "Process next",
                min_value=1,max_value=50,value=10,step=1,
                key="queued_process_limit"
            )
            queued_context=q2.selectbox(
                "Context",
                ["TRADE","INTELLIGENCE"],
                key="queued_process_context"
            )
            queued_mode=q3.selectbox(
                "Batch mode",
                ["Load canonical","Research + load"],
                index=0,
                key="queued_process_mode"
            )
            if st.button(
                "Process queued URLs",
                type="primary",
                use_container_width=True,
                key="process_queued_urls"
            ):
                if not ai_configured():
                    st.error("Configure OPENAI_API_KEY and OPENAI_MODEL first.")
                else:
                    with st.spinner(
                        "Loading queued sources to canonical model..."
                        if queued_mode=="Load canonical"
                        else "Researching and loading queued sources..."
                    ):
                        qr,qf=_process_queued_content_items(
                            int(queued_limit),
                            product_context=queued_context,
                            deep=(queued_mode=="Research + load")
                        )
                    if qr:
                        st.success(
                            f"Loaded {len(qr)} queued source(s); "
                            f"{sum(int(x.get('canonical_applied') or 0) for x in qr)} canonical record(s) created/updated; "
                            f"{sum(int(x.get('canonical_blocked') or 0) for x in qr)} exception(s) remain."
                        )
                    if qf:
                        st.warning(f"{len(qf)} queued source(s) failed.")
                        dataframe(qf)

            try:
                rows=safe_rows(
                    sb,"pc_v_content_ingest_queue","*",500,order="created_at"
                )
            except Exception:
                rows=safe_rows(
                    sb,"pc_content_ingest_items",
                    "content_item_id,content_batch_id,input_type,title,publisher,publication_date,source_url,fetch_status,extraction_status,resolution_status,fetch_error,extraction_error,created_at",
                    500,order="created_at"
                )
            dataframe(rows)

        with facts_tab:
            st.markdown("### Extracted fact review")
            st.caption(
                "Facts are preserved as provenance only. Normal ingestion writes deterministic records directly "
                "to canonical tables; this page is for audit/debugging and genuine exceptions."
            )

            a1,a2=st.columns([1.5,1])
            with a1:
                if st.button(
                    "Clean duplicate audit facts",
                    type="secondary",
                    use_container_width=True,
                    key="dedupe_content_fact_queue"
                ):
                    with st.spinner("Collapsing repeated semantic facts..."):
                        rep=_mark_duplicate_content_facts(10000)
                    st.success(
                        f"Scanned {rep['scanned']} audit fact row(s); "
                        f"marked {rep['duplicates_marked']} duplicate(s). "
                        f"{rep['unique_facts']} unique fact row(s) remain."
                    )
                    st.rerun()
            with a2:
                review_limit=st.selectbox(
                    "Audit window",
                    [500,1000,2500,5000],
                    index=1,
                    key="content_fact_review_limit"
                )

            st.info(
                "This page is now an **audit/provenance view only**. "
                "Normal URL/document loads write safe records directly to canonical tables. "
                "No proposal-building or canonical-link refresh is required here."
            )

            try:
                items,facts,links,promotions=_content_review_data(int(review_limit))
            except Exception as exc:
                st.error(f"Could not load content review data: {exc}")
                items=[]; facts=[]; links=[]; promotions=[]

            idf=pd.DataFrame(items)
            fdf=pd.DataFrame(facts)
            ldf=pd.DataFrame(links)
            pdf=pd.DataFrame(promotions)

            if fdf.empty:
                st.info("No extracted facts yet.")
            else:
                # Headline analyst metrics.
                m1,m2,m3,m4,m5,m6=st.columns(6)
                m1.metric("Sources",fdf["content_item_id"].nunique() if "content_item_id" in fdf.columns else 0)
                m2.metric("Audit facts",len(fdf))
                verified=(
                    fdf["verification_status"].astype(str).isin(["primary_source_supported","corroborated"]).sum()
                    if "verification_status" in fdf.columns else 0
                )
                m3.metric("Primary supported",int(verified))
                m4.metric("Canonical links",len(ldf))
                m5.metric("Promotions",len(pdf))
                needs=(
                    fdf["resolution_status"].astype(str).isin(
                        ["ambiguous","partial","broken_reference","invalid"]
                    ).sum()
                    if "resolution_status" in fdf.columns else 0
                )
                m6.metric("True exceptions",int(needs))

                by_article,needs_tab,ready_tab,raw_tab=st.tabs([
                    "By Article",
                    "True Exceptions",
                    "Linked / Promoted",
                    "Raw Audit Facts"
                ])

                with by_article:
                    if idf.empty:
                        st.info("No source-item metadata available.")
                    else:
                        # Only show source items represented in the fact window.
                        represented=set(fdf["content_item_id"].astype(str)) if "content_item_id" in fdf.columns else set()
                        articles=idf[idf["content_item_id"].astype(str).isin(represented)].copy()
                        for _,itemrow in articles.head(100).iterrows():
                            cid=str(itemrow.get("content_item_id"))
                            ff=fdf[fdf["content_item_id"].astype(str).eq(cid)].copy()
                            fact_ids=set(ff["fact_id"].astype(str)) if not ff.empty else set()
                            ll=ldf[ldf["fact_id"].astype(str).isin(fact_ids)].copy() if not ldf.empty else pd.DataFrame()
                            pp=pdf[pdf["fact_id"].astype(str).isin(fact_ids)].copy() if not pdf.empty else pd.DataFrame()
                            raw_title=itemrow.get("title")
                            try:
                                bad_title=pd.isna(raw_title)
                            except Exception:
                                bad_title=False
                            display_title=(
                                itemrow.get("source_url") or "Untitled source"
                                if bad_title or not str(raw_title or "").strip() or str(raw_title).strip().casefold()=="nan"
                                else str(raw_title).strip()
                            )
                            with st.expander(
                                f"{display_title} · {len(ff)} audit fact(s)",
                                expanded=False
                            ):
                                _review_article_summary(
                                    itemrow.to_dict(),
                                    ff.to_dict("records"),
                                    ll.to_dict("records"),
                                    pp.to_dict("records")
                                )
                                st.caption(
                                    "Audit only — canonical loading happens during source/document ingestion."
                                )

                with needs_tab:
                    need=fdf[
                        fdf["resolution_status"].astype(str).isin(
                            ["ambiguous","partial","broken_reference","invalid"]
                        )
                    ].copy()
                    if need.empty:
                        st.success("No true canonical exceptions in the current audit window.")
                    else:
                        showcols=[
                            "fact_type","subject_name","subject_identifier","predicate",
                            "object_name","object_identifier","value_text","value_numeric",
                            "unit","currency","effective_date","confidence",
                            "verification_status","resolution_status","source_url"
                        ]
                        dataframe(need[[c for c in showcols if c in need.columns]].to_dict("records"))

                with ready_tab:
                    ready=fdf[
                        fdf["resolution_status"].astype(str).isin(["ready","matched"])
                    ].copy()
                    if ready.empty:
                        st.info("No facts are currently classified as ready/matched.")
                    else:
                        showcols=[
                            "fact_type","subject_name","predicate","object_name",
                            "value_text","value_numeric","unit","currency","effective_date",
                            "confidence","verification_status","resolution_status","primary_source_url"
                        ]
                        dataframe(ready[[c for c in showcols if c in ready.columns]].to_dict("records"))
                        st.caption(
                            "Ready facts with staged promotions are already in the normal Review Queue. "
                            "Approve/apply them there; this fact layer remains the provenance/audit trail."
                        )

                with raw_tab:
                    st.caption("Administrative/debug view.")
                    dataframe(fdf.to_dict("records"))

elif page=="Document Loader":
    title("Document / report loader","Upload and preserve a source document. For documents containing lists of article URLs, use Universal Content Intake so every URL is fetched, fact-extracted and routed.")
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
                    st.markdown("#### Load document into canonical model")
                    extraction_prompt=st.text_area(
                        "Extraction instruction",
                        value="Extract only facts supported by this document into the P&C canonical staging schema. Preserve source-document provenance. Do not invent facts.",
                        height=110
                    )
                    if st.button("Load document → canonical model",type="primary"):
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
                            auto_result=_process_job_automatically(job["ingestion_job_id"]) if staged else {"total_applied_this_run":0}
                            applied=int((auto_result or {}).get("total_applied_this_run",0) or 0)
                            try:
                                _,blocked=_job_apply_candidates(job["ingestion_job_id"])
                            except Exception:
                                blocked=[]
                            sb.table("pc_ingestion_jobs").update({
                                "status":"completed","completed_at":pd.Timestamp.utcnow().isoformat(),
                                "stats":{
                                    "document_id":doc_id,
                                    "staged_records":staged,
                                    "canonical_applied":applied,
                                    "exceptions":len(blocked),
                                    "rejected":rejected,
                                    "resolution":resolution,
                                    "auto_apply":auto_result
                                }
                            }).eq("ingestion_job_id",job["ingestion_job_id"]).execute()
                            st.success(
                                f"Document loaded: {applied} canonical record(s) created/updated"
                                + (f" · {len(blocked)} genuine exception(s) remain." if blocked else " · no blocking exceptions.")
                            )
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
                    "supply_series_id","observation_id","transport_service_id","financing_id","contract_id","vessel_design_id","shipbuilding_order_id","shipbuilding_order_unit_id","service_alias_id","service_operator_id","service_stop_id","service_schedule_id","service_transit_time_id","service_mobile_asset_id","service_network_link_id","service_connection_id","service_change_id","service_source_id","imo","mmsi","name","title","route_name","service_name","financing_name","contract_name","design_name"):
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
        "Review the staged records produced by AI Research, Universal Content Intake, Port Enrichment and bulk loaders. "
        "Approve safe records here, then apply them to the canonical database."
    )
    st.info(
        "This is the normal workflow queue. **Bulk review** contains pending staged proposals; "
        "**Manual review** handles exceptions; **Approved — apply** writes approved records to canonical tables."
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
