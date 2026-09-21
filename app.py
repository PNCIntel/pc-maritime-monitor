from pathlib import Path
import sys
import os
import re
import hashlib
from difflib import SequenceMatcher
import json
import html as html_lib
import xml.etree.ElementTree as ET
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from collections import defaultdict
import pandas as pd
import streamlit as st
try:
    import pydeck as pdk
except Exception:
    pdk = None

SHARED_DIR = Path(__file__).resolve().parent / "shared"
if str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))
from pc_data_bridge import load_sheet as bridge_load_sheet, workbook_sheets as bridge_workbook_sheets, backend_status
from pc_workspace import save_query as save_workspace_query
from pc_db import client as pc_db_client, safe_rows as pc_safe_rows
from pc_display import (
    clean_text as pc_clean_text,
    pretty_enum as pc_pretty_enum,
    pretty_countries as pc_pretty_countries,
    pretty_date as pc_pretty_date,
    display_value as pc_display_value,
    standardize_dataframe as pc_standardize_dataframe,
    standardize_event_dataframe as pc_standardize_event_dataframe,
    format_filter_option as pc_format_filter_option,
)
from pc_drilldown import render_sidebar_search as pc_render_drilldown_search, render_active_drilldown as pc_render_active_drilldown, drilldown_button as pc_drilldown_button, set_drilldown as pc_set_drilldown
from pc_trade_system import render_energy_industry, render_trade_flows_supply, render_country_macro, render_market_instruments
try:
    from pc_auth import require_login
except Exception:
    require_login = None

APP_TITLE = "P&C Trade System"
APP_VERSION = "v4.1.0-latest-reporting-nameerror-fix"
RELEASE_NAME = "End-to-End Logistics Operating Picture · Companies, Networks, Modes, Markets & Risk"
DATA_DIR = Path(__file__).parent / "data"

st.set_page_config(page_title=f"{APP_TITLE} {APP_VERSION}", page_icon="◈", layout="wide", initial_sidebar_state="expanded")

# Authentication is opt-in during migration. Set PC_REQUIRE_AUTH=true once tenant users are configured.
if os.getenv("PC_REQUIRE_AUTH", "false").lower() == "true" and require_login is not None:
    PC_USER_CONTEXT = require_login("TRADE", "P&C Trade")
else:
    PC_USER_CONTEXT = None

st.markdown("""
<style>
:root{--bg:#07111f;--panel:#0d1a2b;--panel2:#102238;--border:#28415f;--text:#f3f6fa;--muted:#b8c5d4;--gold:#d7b66a;--blue:#7bc3ef}
.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"]{background:var(--bg);color:var(--text)}
[data-testid="stSidebar"]{background:#091725!important;border-right:1px solid var(--border)}
h1,h2,h3,h4,h5,h6,p,li,span,label{color:var(--text)}
a{color:var(--blue)!important}
.pc-kicker{color:var(--gold);font-size:.76rem;letter-spacing:.14em;text-transform:uppercase;font-weight:700}.pc-title{font-size:2rem;font-weight:800}.pc-sub{color:var(--muted);margin:.2rem 0 1.2rem}.pc-card{background:linear-gradient(180deg,var(--panel),var(--panel2));border:1px solid var(--border);border-radius:12px;padding:14px 16px;margin-bottom:8px}.pc-label{font-size:.72rem;color:var(--muted);text-transform:uppercase;letter-spacing:.08em}.pc-big{font-size:1.3rem;font-weight:750}.pc-small{color:var(--muted);font-size:.88rem}.pc-rel{padding:8px 11px;border-left:3px solid var(--gold);background:var(--panel);margin:6px 0;border-radius:5px}.pc-chip{display:inline-block;border:1px solid var(--border);background:var(--panel);padding:3px 8px;border-radius:999px;font-size:.76rem;color:var(--muted);margin:2px 3px 2px 0}
.pc-source{margin-top:7px;font-size:.82rem}.pc-source a{color:var(--blue)!important;text-decoration:none;font-weight:650}
.pc-feed-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:10px;margin:.5rem 0 1rem}.pc-feed{background:linear-gradient(180deg,var(--panel),var(--panel2));border:1px solid var(--border);border-radius:12px;padding:14px 16px}.pc-feed-title{font-weight:760;font-size:1rem;margin-bottom:3px}.pc-feed-meta{font-size:.78rem;color:var(--muted);line-height:1.5}.pc-status{display:inline-block;border-radius:999px;padding:2px 8px;font-size:.7rem;font-weight:750;letter-spacing:.05em;text-transform:uppercase;margin-top:7px;border:1px solid var(--border)}.pc-status-live{color:#9ee6c1;border-color:#39775c}.pc-status-key{color:#f5d58a;border-color:#806b36}.pc-status-trial{color:#f2c17e;border-color:#815b2d}.pc-status-off{color:#c2cad4;border-color:#526071}
.pc-search-card{padding:16px 18px}.pc-search-details{margin-top:8px;line-height:1.65;color:var(--muted);font-size:.92rem}
.pc-object-card{margin-bottom:.35rem;min-height:72px}
.pc-bar-row{display:grid;grid-template-columns:minmax(220px,2fr) 5fr 52px;gap:12px;align-items:center;margin:8px 0}
.pc-bar-label{color:#f3f6fa;font-size:.88rem;white-space:normal}
.pc-bar-track{height:20px;background:#0d1a2b;border:1px solid #28415f;border-radius:5px;overflow:hidden}
.pc-bar-fill{height:100%;background:#2f6fb5}
.pc-bar-value{color:#d7b66a;font-weight:700;text-align:right}
.pc-detail-label{color:#d7b66a!important;font-weight:700}.pc-detail-value{color:#f3f6fa!important}.pc-sep{color:#6f849d!important;margin:0 .2rem}
/* top navigation */
div[role="radiogroup"]{gap:.35rem;flex-wrap:wrap}
div[role="radiogroup"] label{background:#0d1a2b;border:1px solid #28415f;border-radius:9px;padding:.35rem .75rem}
div[role="radiogroup"] label:has(input:checked){border-color:#d7b66a;background:#102238}
[data-baseweb="tab-list"]{gap:.25rem}[data-baseweb="tab"]{color:#f3f6fa!important}
[data-baseweb="select"]>div,[data-baseweb="input"]>div,.stTextInput input{background:var(--panel)!important;color:var(--text)!important;border-color:var(--border)!important}
.stDataFrame{border:1px solid var(--border);border-radius:8px}
/* Streamlit popovers, detail boxes, dialogs, expanders and tooltips must remain readable in dark mode */
[data-baseweb="popover"],[data-baseweb="popover"] *,
[data-baseweb="menu"],[data-baseweb="menu"] *,
[data-testid="stPopoverBody"],[data-testid="stPopoverBody"] *,
[data-testid="stDialog"],[data-testid="stDialog"] *,
[data-testid="stExpander"] details,[data-testid="stExpander"] summary,
div[role="dialog"],div[role="dialog"] *{
  color:#101820!important;
}
[data-baseweb="popover"],[data-baseweb="menu"],[data-testid="stPopoverBody"],[data-testid="stDialog"],div[role="dialog"]{
  background:#ffffff!important;
}
[data-baseweb="popover"] a,[data-baseweb="menu"] a,[data-testid="stPopoverBody"] a,div[role="dialog"] a{color:#145a8d!important}
[data-testid="stAlert"] p,[data-testid="stAlert"] span{color:inherit!important}
/* Streamlit Cloud / app chrome */
[data-testid="stHeader"],header[data-testid="stHeader"],[data-testid="stToolbar"],[data-testid="stDecoration"]{
  background:#07111f!important;
  color:#f3f6fa!important;
}
[data-testid="stHeader"] *,[data-testid="stToolbar"] *{
  color:#f3f6fa!important;
}
[data-testid="stHeader"] svg,[data-testid="stToolbar"] svg{
  fill:#f3f6fa!important;
  color:#f3f6fa!important;
}
[data-testid="stAppDeployButton"],[data-testid="stStatusWidget"]{
  background:#0d1a2b!important;
  color:#f3f6fa!important;
}
.stButton > button, .stDownloadButton > button{
  background:#102238!important;
  color:#f3f6fa!important;
  border:1px solid #28415f!important;
}
.stButton > button:hover, .stDownloadButton > button:hover{
  border-color:#d7b66a!important;
  color:#ffffff!important;
}
.stButton > button p, .stDownloadButton > button p{
  color:#f3f6fa!important;
}
/* White BaseWeb/Streamlit detail boxes get dark text */
[data-baseweb="popover"],[data-baseweb="popover"] *,
[data-baseweb="menu"],[data-baseweb="menu"] *,
[data-testid="stPopoverBody"],[data-testid="stPopoverBody"] *,
[data-testid="stDialog"],[data-testid="stDialog"] *,
div[role="dialog"],div[role="dialog"] *,
div[data-baseweb="tooltip"],div[data-baseweb="tooltip"] *{
  color:#101820!important;
}
[data-baseweb="popover"],[data-baseweb="menu"],[data-testid="stPopoverBody"],
[data-testid="stDialog"],div[role="dialog"],div[data-baseweb="tooltip"]{
  background:#ffffff!important;
}

/* v3.0 workspace navigation */
[data-testid="stSidebar"] [data-testid="stRadio"] label{
  border:0!important;background:transparent!important;border-radius:7px!important;
  padding:.34rem .45rem!important;margin:.05rem 0!important;
}
[data-testid="stSidebar"] [data-testid="stRadio"] label:hover{background:#102238!important}
[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked){
  background:#132944!important;border-left:3px solid #d7b66a!important;
}
.pc-breadcrumb{font-size:.78rem;color:#8ea1b7;margin:.1rem 0 .55rem}.pc-breadcrumb b{color:#d7b66a}
.pc-hero{background:linear-gradient(120deg,#0d1a2b,#102238);border:1px solid #28415f;border-radius:14px;padding:18px 20px;margin:.2rem 0 1rem}
.pc-hero-title{font-size:1.25rem;font-weight:780;margin-bottom:.25rem}.pc-hero-copy{color:#b8c5d4;line-height:1.55}
.pc-workspace-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px;margin:.7rem 0 1rem}
.pc-workspace-card{background:#0d1a2b;border:1px solid #28415f;border-radius:12px;padding:14px 16px;min-height:118px}
.pc-workspace-card b{font-size:1rem}.pc-workspace-card p{color:#b8c5d4;font-size:.86rem;line-height:1.45;margin:.35rem 0 0}
.pc-section-note{background:#0b1828;border-left:3px solid var(--gold);padding:9px 12px;border-radius:6px;margin:.4rem 0 .8rem;color:var(--muted);font-size:.87rem}
.pc-data-status{display:inline-flex;align-items:center;gap:6px;padding:4px 9px;border:1px solid var(--border);border-radius:999px;color:var(--muted);font-size:.75rem;margin-right:5px}
.pc-data-status-live{border-color:#39775c;color:#9ee6c1}.pc-data-status-stale{border-color:#806b36;color:#f5d58a}
.pc-feed-health{display:inline-flex;align-items:center;gap:6px;border:1px solid #28415f;border-radius:999px;padding:4px 9px;font-size:.74rem;color:#b8c5d4;margin:2px 0}
.pc-dot{width:7px;height:7px;border-radius:50%;background:#6a7c90;display:inline-block}.pc-dot-live{background:#75d6a4}.pc-dot-key{background:#d7b66a}.pc-dot-off{background:#7b8796}


/* Consistent dark external-link buttons */
a[data-testid="stLinkButton"],
div[data-testid="stLinkButton"] a,
div[data-testid="stLinkButton"] > a,
.stLinkButton a {
    background: #121A22 !important;
    color: #D8B45A !important;
    border: 1px solid #3A4650 !important;
    border-radius: 8px !important;
    box-shadow: none !important;
    text-decoration: none !important;
}
a[data-testid="stLinkButton"]:hover,
div[data-testid="stLinkButton"] a:hover,
.stLinkButton a:hover {
    background: #19232D !important;
    color: #F0D27A !important;
    border-color: #D8B45A !important;
}
a[data-testid="stLinkButton"]:visited,
div[data-testid="stLinkButton"] a:visited,
.stLinkButton a:visited {
    color: #D8B45A !important;
}

</style>
""", unsafe_allow_html=True)

if st.session_state.get("pc_trade_appearance","Dark") == "Light":
    st.markdown("""
    <style>
    :root{
      --bg:#f5f7fa;--panel:#ffffff;--panel2:#f0f3f7;--border:#cbd5e1;
      --text:#16202a;--muted:#5d6b7a;--gold:#9a7626;--blue:#176aa3
    }
    .stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"]{
      background:var(--bg)!important;color:var(--text)!important
    }
    [data-testid="stSidebar"]{
      background:#eef2f6!important;border-right:1px solid var(--border)!important
    }
    h1,h2,h3,h4,h5,h6,p,li,span,label{color:var(--text)!important}
    .pc-card,.pc-feed,.pc-object-card,.pc-workspace-card,.pc-rel{
      background:#ffffff!important;border-color:var(--border)!important
    }
    .pc-hero{background:linear-gradient(120deg,#ffffff,#eef3f8)!important;border-color:var(--border)!important}
    .pc-sub,.pc-small,.pc-label,.pc-feed-meta,.pc-search-details,.pc-workspace-card p,.pc-hero-copy{
      color:var(--muted)!important
    }
    div[role="radiogroup"] label{
      background:#ffffff!important;border-color:var(--border)!important
    }
    div[role="radiogroup"] label:has(input:checked){
      background:#e6edf5!important;border-color:#9a7626!important
    }
    [data-testid="stSidebar"] [data-testid="stRadio"] label:hover{background:#e4eaf1!important}
    [data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked){
      background:#dfe8f2!important;border-left:3px solid #9a7626!important
    }
    [data-baseweb="tab"]{color:#16202a!important}
    [data-baseweb="select"]>div,[data-baseweb="input"]>div,.stTextInput input{
      background:#ffffff!important;color:#16202a!important;border-color:#cbd5e1!important
    }
    .stButton > button,.stDownloadButton > button,
    a[data-testid="stLinkButton"],div[data-testid="stLinkButton"] a,.stLinkButton a{
      background:#ffffff!important;color:#29465f!important;border-color:#b8c3cf!important
    }
    .stButton > button p,.stDownloadButton > button p{color:#29465f!important}
    .stDataFrame{border-color:#cbd5e1!important}
    [data-testid="stHeader"],header[data-testid="stHeader"],[data-testid="stToolbar"],[data-testid="stDecoration"]{
      background:#f5f7fa!important;color:#16202a!important
    }
    [data-testid="stHeader"] *,[data-testid="stToolbar"] *{color:#16202a!important}
    [data-testid="stHeader"] svg,[data-testid="stToolbar"] svg{fill:#16202a!important;color:#16202a!important}
    .pc-bar-label,.pc-detail-value{color:#16202a!important}
    .pc-bar-track{background:#e9eef4!important;border-color:#cbd5e1!important}
    </style>
    """, unsafe_allow_html=True)

# ---------- workbook loading ----------
WORKBOOKS = {
    "Core Entities": "01_core_entities.xlsx",
    "Maritime": "02_maritime.xlsx",
    "Rail": "03_rail.xlsx",
    "Road & Trucking": "04_road_trucking.xlsx",
    "Aviation": "05_aviation.xlsx",
    "Infrastructure": "06_infrastructure.xlsx",
    "Corporate & Markets": "07_corporate_markets.xlsx",
    "Transactions": "08_transactions.xlsx",
    "Intelligence": "09_intelligence.xlsx",
    "Evidence & sources": "10_sources_evidence.xlsx",
    "Systems & Waterways": "11_systems_waterways_governance.xlsx",
    "Defence & Shipbuilding": "12_defence_shipbuilding.xlsx",
    "Events & Hazards": "13_events_hazards.xlsx",
    "Trade Policy & Compliance": "14_trade_policy_compliance.xlsx",
    "Market Intelligence Reference": "15_market_intelligence_reference.xlsx",
    "Global Ports Reference": "16_global_ports_reference.xlsx",
    "Trade Connectivity Reference": "17_trade_connectivity_reference.xlsx",
    "Official Maritime Security": "18_official_maritime_security.xlsx",
    "Risk Benchmarks": "19_risk_benchmarks.xlsx",
}

@st.cache_data(show_spinner=False, ttl=300)
def workbook_sheets(label):
    return bridge_workbook_sheets(DATA_DIR, label)

@st.cache_data(show_spinner=False, ttl=300)
def load_sheet(label, sheet):
    return bridge_load_sheet(DATA_DIR, label, sheet, dtype_str=True)


HORMUZ_API_BASE = "https://hormuz.data-tracking.net/api"
HORMUZ_API_PATHS = {"summary", "crossings/daily", "ships/by_zone"}

@st.cache_data(show_spinner=False, ttl=1800)
def load_hormuz_api(path, parameter_name="", parameter_value=""):
    """Read only documented, allow-listed public endpoints; fail without breaking the app."""
    if path not in HORMUZ_API_PATHS:
        return None, "Unsupported endpoint"
    url = f"{HORMUZ_API_BASE}/{path}"
    if parameter_name and parameter_value:
        url += f"?{parameter_name}={int(parameter_value)}"
    try:
        req = Request(url, headers={"User-Agent":"PC-Trade-System/2.9"})
        with urlopen(req, timeout=8) as response:
            return json.loads(response.read().decode("utf-8")), ""
    except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
        return None, str(exc)


# ---------- USCG CGMIX XML web services ----------
CGMIX_PSIX_URL = "https://cgmix.uscg.mil/xml/PSIXData.asmx"
CGMIX_IIR_URL = "https://cgmix.uscg.mil/xml/IIRData.asmx"


def _xml_local_name(tag):
    return str(tag).split("}")[-1]


def _cgmix_parse_rows(xml_text):
    """Parse the escaped XML dataset returned inside the CGMIX SOAP response."""
    if not xml_text:
        return []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    rows=[]
    for node in root.iter():
        children=list(node)
        if not children:
            continue
        # DataSet row nodes contain scalar child fields. Skip schema/diffgram wrappers.
        scalar=[c for c in children if len(list(c))==0]
        if scalar and len(scalar)==len(children):
            row={_xml_local_name(c.tag):(c.text or "") for c in children}
            if row and any(str(v).strip() for v in row.values()):
                rows.append(row)
    # Deduplicate identical rows introduced by nested dataset wrappers.
    out=[]; seen=set()
    for row in rows:
        key=tuple(sorted(row.items()))
        if key not in seen:
            seen.add(key); out.append(row)
    return out


def _cgmix_soap(endpoint, operation, namespace, params):
    fields="".join(f"<{k}>{html_lib.escape(str(v or ''))}</{k}>" for k,v in params.items())
    body=(
        '<?xml version="1.0" encoding="utf-8"?>'
        '<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xmlns:xsd="http://www.w3.org/2001/XMLSchema" '
        'xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">'
        f'<soap:Body><{operation} xmlns="{namespace}">{fields}</{operation}></soap:Body></soap:Envelope>'
    ).encode("utf-8")
    action=namespace.rstrip("/") + ("/" if not namespace.endswith("/") else "") + operation
    req=Request(endpoint,data=body,headers={
        "User-Agent":"PC-Trade-System/2.7",
        "Content-Type":"text/xml; charset=utf-8",
        "SOAPAction":f'"{action}"'
    },method="POST")
    with urlopen(req,timeout=15) as response:
        soap=response.read().decode("utf-8",errors="replace")
    root=ET.fromstring(soap)
    result=None
    target=operation+"Result"
    for node in root.iter():
        if _xml_local_name(node.tag)==target:
            result=node.text or ""
            break
    if result is None:
        raise ValueError("CGMIX returned no result payload")
    return _cgmix_parse_rows(html_lib.unescape(result))


@st.cache_data(show_spinner=False, ttl=1800)
def cgmix_psix_vessel_search(vessel_name="", imo_or_id="", flag="", service="ALL"):
    try:
        rows=_cgmix_soap(CGMIX_PSIX_URL,"getVesselSummaryXMLString","https://cgmix.uscg.mil",{
            "VesselID":"","VesselName":vessel_name,"CallSign":"","VIN":imo_or_id,"HIN":"",
            "Flag":flag,"Service":service or "ALL","BuildYear":""
        })
        return pd.DataFrame(rows),""
    except (HTTPError,URLError,TimeoutError,ValueError,OSError,ET.ParseError) as exc:
        return pd.DataFrame(),str(exc)


@st.cache_data(show_spinner=False, ttl=1800)
def cgmix_psix_cases(vessel_id):
    try:
        rows=_cgmix_soap(CGMIX_PSIX_URL,"getVesselCasesXMLString","https://cgmix.uscg.mil",{"VesselID":str(vessel_id),"MaxSearchDate":"","MinSearchDate":""})
        return pd.DataFrame(rows),""
    except (HTTPError,URLError,TimeoutError,ValueError,OSError,ET.ParseError) as exc:
        return pd.DataFrame(),str(exc)


@st.cache_data(show_spinner=False, ttl=1800)
def cgmix_psix_deficiencies(activity_id):
    try:
        rows=_cgmix_soap(CGMIX_PSIX_URL,"getVesselDeficienciesXMLString","https://cgmix.uscg.mil",{"ActivityNumber":str(activity_id)})
        return pd.DataFrame(rows),""
    except (HTTPError,URLError,TimeoutError,ValueError,OSError,ET.ParseError) as exc:
        return pd.DataFrame(),str(exc)


@st.cache_data(show_spinner=False, ttl=1800)
def cgmix_psix_controls(activity_id):
    try:
        rows=_cgmix_soap(CGMIX_PSIX_URL,"getOperationControlsXMLString","https://cgmix.uscg.mil",{"ActivityID":str(activity_id)})
        return pd.DataFrame(rows),""
    except (HTTPError,URLError,TimeoutError,ValueError,OSError,ET.ParseError) as exc:
        return pd.DataFrame(),str(exc)


@st.cache_data(show_spinner=False, ttl=1800)
def cgmix_iir_search(vessel_name="", org_name="", facility="", keyword=""):
    try:
        rows=_cgmix_soap(CGMIX_IIR_URL,"getIIRIncidentSearchXMLString","https://cgmix.uscg.mil/xml/",{
            "ActivityId":"0","VesselService":"","VesselName":vessel_name,"OrgName":org_name,
            "InvolvedFacility":facility,"KeyWord":keyword
        })
        return pd.DataFrame(rows),""
    except (HTTPError,URLError,TimeoutError,ValueError,OSError,ET.ParseError) as exc:
        return pd.DataFrame(),str(exc)


# ---------- GDELT DOC 2.0 global signals ----------
GDELT_DOC_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
GDELT_GEO_URL = "https://api.gdeltproject.org/api/v2/geo/geo"

@st.cache_data(show_spinner=False, ttl=900)
def load_gdelt_articles(query, timespan="24h", maxrecords=50):
    """Query GDELT DOC 2.0. Results are discovery signals, not verified P&C events."""
    params={"query":query,"mode":"ArtList","format":"json","sort":"DateDesc",
            "timespan":timespan,"maxrecords":max(1,min(int(maxrecords),250))}
    url=GDELT_DOC_URL+"?"+urlencode(params)
    try:
        req=Request(url,headers={"User-Agent":"PC-Trade-System/2.9"})
        with urlopen(req,timeout=20) as response:
            raw=response.read().decode("utf-8",errors="replace")
        try:
            payload=json.loads(raw)
        except json.JSONDecodeError:
            raise ValueError(raw.strip()[:300] or "GDELT returned a non-JSON response")
        arts=payload.get("articles",[]) if isinstance(payload,dict) else []
        df=pd.DataFrame(arts)
        if not df.empty and "seendate" in df.columns:
            df["Seen"] = pd.to_datetime(df["seendate"],format="%Y%m%dT%H%M%SZ",errors="coerce",utc=True)
        return df,""
    except (HTTPError,URLError,TimeoutError,ValueError,OSError) as exc:
        return pd.DataFrame(),str(exc)



# ---------- NewsData.io news & signal discovery ----------
NEWSDATA_LATEST_URL = "https://newsdata.io/api/1/latest"

@st.cache_data(show_spinner=False, ttl=900)
def load_newsdata_articles(query, api_key, language="en", size=10):
    """NewsData.io discovery feed with a compact-query retry for HTTP 422."""
    if not api_key:
        return pd.DataFrame(), "NewsData.io API key not configured"

    requested_size=max(1,min(int(size or 10),10))
    headers={"User-Agent":"Mozilla/5.0 Power-Corridors-Trade/3.4"}

    # NewsData can reject long Boolean queries with HTTP 422. Try a compact
    # high-value query first, then a general English latest feed.
    attempts=[
        str(query or "").strip()[:420],
        "shipping maritime port logistics trade energy security",
        "",
    ]

    last_error=""
    for q in attempts:
        params={"apikey":api_key,"language":language,"size":requested_size}
        if q:
            params["q"]=q
        try:
            req=Request(NEWSDATA_LATEST_URL+"?"+urlencode(params),headers=headers)
            with urlopen(req,timeout=12) as response:
                payload=json.loads(response.read().decode("utf-8",errors="replace"))
            if str(payload.get("status","")).lower() not in {"success",""}:
                last_error=str(payload.get("message") or "NewsData request failed")
                continue
            results=payload.get("results") or []
            if results:
                return pd.DataFrame(results), ""
            last_error="No results returned"
        except HTTPError as exc:
            body=""
            try:
                body=exc.read().decode("utf-8",errors="replace")[:500]
            except Exception:
                pass
            last_error=f"HTTP {exc.code}" + (f" · {body}" if body else "")
            if exc.code != 422:
                break
        except (URLError,TimeoutError,ValueError,OSError) as exc:
            last_error=str(exc)
            break

    return pd.DataFrame(), last_error or "NewsData request failed"


# ---------- optional live transport feeds ----------
def _secret(name, default=""):
    try:
        return str(st.secrets.get(name, default) or default)
    except Exception:
        return str(os.environ.get(name, default) or default)

def _newsdata_key():
    """Accept either NEWSDATA_API_KEY or grouped [newsdata] api_key secrets."""
    direct=_secret("NEWSDATA_API_KEY")
    if direct:
        return direct
    try:
        section=st.secrets.get("newsdata", {})
        if hasattr(section, "get"):
            return str(section.get("api_key", "") or "")
    except Exception:
        pass
    return str(os.environ.get("NEWSDATA_API_KEY", "") or "")

YAHOO_CHART_BASE="https://query1.finance.yahoo.com/v8/finance/chart"

@st.cache_data(show_spinner=False, ttl=300)
def load_yahoo_quote(symbol):
    """Small server-side market snapshot. Fails closed when the upstream quote is unavailable."""
    safe=str(symbol or "").strip()
    if not safe:
        return {}, "Missing symbol"
    from urllib.parse import quote as _urlquote
    url=f"{YAHOO_CHART_BASE}/{_urlquote(safe, safe='')}?interval=1d&range=5d"
    try:
        req=Request(url,headers={"User-Agent":"Mozilla/5.0 PC-Trade-System/3.3"})
        with urlopen(req,timeout=10) as response:
            payload=json.loads(response.read().decode("utf-8",errors="replace"))
        result=((payload.get("chart") or {}).get("result") or [None])[0]
        if not isinstance(result,dict):
            return {}, str(((payload.get("chart") or {}).get("error") or {}).get("description") or "No quote returned")
        meta=result.get("meta") or {}
        closes=(((result.get("indicators") or {}).get("quote") or [{}])[0].get("close") or [])
        vals=[float(x) for x in closes if x is not None]
        price=meta.get("regularMarketPrice")
        try: price=float(price) if price is not None else (vals[-1] if vals else None)
        except Exception: price=vals[-1] if vals else None
        prev=meta.get("chartPreviousClose") or meta.get("previousClose")
        try: prev=float(prev) if prev is not None else (vals[-2] if len(vals)>1 else None)
        except Exception: prev=vals[-2] if len(vals)>1 else None
        pct=((price-prev)/prev*100.0) if price is not None and prev not in (None,0) else None
        return {
            "symbol":safe,"price":price,"previous":prev,"change_pct":pct,
            "currency":str(meta.get("currency") or ""),"exchange":str(meta.get("exchangeName") or meta.get("fullExchangeName") or ""),
            "timestamp":meta.get("regularMarketTime"),
        }, ""
    except (HTTPError,URLError,TimeoutError,ValueError,OSError,TypeError) as exc:
        return {}, str(exc)

@st.cache_data(show_spinner=False, ttl=1800)
def load_fred_latest(series_id):
    """Latest non-empty FRED observation for slower official/reference series."""
    sid=str(series_id or "").strip()
    if not sid: return {}, "Missing series"
    url=f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"
    try:
        req=Request(url,headers={"User-Agent":"PC-Trade-System/3.3"})
        with urlopen(req,timeout=10) as response:
            raw=response.read().decode("utf-8",errors="replace")
        import io
        df=pd.read_csv(io.StringIO(raw))
        if df.empty or sid not in df.columns: return {}, "No observations"
        df[sid]=pd.to_numeric(df[sid],errors="coerce")
        df=df[df[sid].notna()]
        if df.empty: return {}, "No numeric observations"
        r=df.iloc[-1]
        prev=df.iloc[-2][sid] if len(df)>1 else None
        value=float(r[sid]); prev=float(prev) if prev is not None and pd.notna(prev) else None
        pct=((value-prev)/prev*100.0) if prev not in (None,0) else None
        return {"price":value,"previous":prev,"change_pct":pct,"date":str(r.iloc[0])}, ""
    except (HTTPError,URLError,TimeoutError,ValueError,OSError,TypeError) as exc:
        return {}, str(exc)

def _metric_price(value, kind="number"):
    if value is None or pd.isna(value): return "—"
    value=float(value)
    if kind=="fx": return f"{value:,.4f}"
    if abs(value)>=1000: return f"{value:,.0f}"
    return f"{value:,.2f}"

def render_live_market_dashboard(compact=False):
    """Readable live/delayed market context for the Trade overview."""
    indices=[
        ("S&P 500","^GSPC"),("NASDAQ Composite","^IXIC"),("FTSE 100","^FTSE"),("DAX","^GDAXI"),
        ("Nikkei 225","^N225"),("Hang Seng","^HSI"),("Tadawul All Share","^TASI.SR"),
    ]
    energy=[("Brent","BZ=F"),("WTI","CL=F"),("Henry Hub Gas","NG=F"),("Gold","GC=F"),("USD Index","DX-Y.NYB")]
    fx=[("EUR/USD","EURUSD=X"),("GBP/USD","GBPUSD=X"),("USD/JPY","JPY=X"),("USD/CNY","CNY=X"),("USD/INR","INR=X")]

    def _rows(items,kind="number"):
        rows=[]
        for label,symbol in items:
            q,err=load_yahoo_quote(symbol)
            if not q or q.get("price") is None:
                continue
            delta=q.get("change_pct")
            rows.append({
                "Market":label,
                "Last":_metric_price(q.get("price"),kind),
                "Change":("—" if delta is None else f"{delta:+.2f}%"),
            })
        return pd.DataFrame(rows)

    def _render_table(items,kind="number"):
        df=_rows(items,kind)
        if df.empty:
            st.caption("Live market feed is temporarily unavailable.")
            return
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Market":st.column_config.TextColumn("Market",width="medium"),
                "Last":st.column_config.TextColumn("Last",width="small"),
                "Change":st.column_config.TextColumn("1D",width="small"),
            },
        )

    if compact:
        tabs=st.tabs(["Bourses","Energy","FX"])
        with tabs[0]:
            _render_table(indices)
        with tabs[1]:
            _render_table(energy)
            dubai,derr=load_fred_latest("POILDUBUSDM")
            if dubai:
                ch=dubai.get("change_pct")
                change="" if ch is None else f" · {ch:+.2f}% vs prior observation"
                st.caption(f"Dubai crude · IMF/FRED monthly reference · ${dubai.get('price',0):,.2f}{change} · {dubai.get('date','')}")
        with tabs[2]:
            _render_table(fx,"fx")
    else:
        st.markdown("### Bourse indices")
        _render_table(indices)
        st.markdown("### Energy, commodities & USD")
        _render_table(energy)
        dubai,derr=load_fred_latest("POILDUBUSDM")
        if dubai:
            st.caption(f"Dubai crude reference (IMF/FRED monthly): ${dubai.get('price',0):,.2f} · observation {dubai.get('date','')} · slower reference series, not an intraday quote")
        st.markdown("### FX")
        _render_table(fx,"fx")


def _news_trade_relevant(row):
    """Keep the Overview feed focused on trade, business, conflict and geopolitics."""
    fields=["title","description","content","keywords","category","country","source_name"]
    text=" ".join(str(row.get(c) or "") for c in fields).casefold()

    # Strong exclusions. These should never lead the Trade overview unless a genuine
    # commercial/geopolitical term also appears in a clearly relevant context.
    excluded=[
        r"\bnfl\b",r"\bnba\b",r"\bmlb\b",r"\bnhl\b",r"\bncaa\b",r"football",r"basketball",r"baseball",
        r"soccer",r"tennis",r"golf",r"touchdown",r"halftime",r"quarterback",r"kentucky",r"alabama",
        r"celebrity",r"entertainment",r"movie",r"film festival",r"television series",r"music album",r"concert",
        r"fashion",r"recipe",r"dating",r"horoscope",r"wellness",r"fitness",r"travel tips",r"lottery"
    ]
    if any(re.search(p,text) for p in excluded):
        return False

    relevant=[
        r"shipping",r"maritime",r"port\b",r"terminal",r"container",r"freight",r"logistics",r"supply chain",
        r"trade\b",r"tariff",r"customs",r"sanction",r"export",r"import",r"corridor",r"rail",r"railway",
        r"aviation",r"airport",r"air cargo",r"infrastructure",r"investment",r"contract",r"acquisition",r"merger",
        r"oil\b",r"crude",r"gas\b",r"lng",r"refiner",r"pipeline",r"energy",r"commodity",r"minerals?",
        r"conflict",r"war\b",r"attack",r"drone",r"missile",r"military",r"defen[cs]e",r"naval",r"security",
        r"geopolit",r"government",r"election",r"diplomat",r"border",r"blockade",r"strait",r"canal",
        r"company",r"corporate",r"earnings",r"shares?",r"stock market",r"bourse",r"bank",r"finance",r"economy",
    ]
    return any(re.search(p,text) for p in relevant)


def render_overview_news():
    """Latest business/trade/geopolitical signals from NewsData.io."""
    api_key=_newsdata_key()
    st.markdown("### Latest news & signals")
    if not api_key:
        st.caption("NewsData.io is configured in code but no API key was found in Streamlit Secrets.")
        return

    # Query is deliberately narrow; a second local gate below rejects irrelevant syndication.
    query=(
        'shipping OR maritime OR port OR logistics OR freight OR "supply chain" OR trade OR tariff OR sanctions '
        'OR energy OR oil OR gas OR LNG OR rail OR aviation OR infrastructure OR investment OR defence '
        'OR conflict OR geopolitics OR military OR security'
    )
    df,err=load_newsdata_articles(query,api_key,"en",10)
    if err:
        st.caption(f"NewsData.io unavailable: {err}")
        return
    if df.empty:
        st.caption("No current news signals returned.")
        return

    df=df[df.apply(_news_trade_relevant,axis=1)].copy()
    if df.empty:
        st.caption("No current business, trade, conflict or geopolitical signals passed the relevance filter.")
        return

    # De-duplicate syndicated copies by normalized title.
    df["_title_key"]=df.get("title",pd.Series(index=df.index,dtype=str)).fillna("").astype(str).str.casefold().str.replace(r"[^a-z0-9]+"," ",regex=True).str.strip()
    df=df.drop_duplicates("_title_key").drop(columns=["_title_key"],errors="ignore")

    for _,row in df.head(8).iterrows():
        title=str(row.get("title") or "Untitled").strip()
        url=str(row.get("link") or "").strip()
        source=str(row.get("source_name") or row.get("source_id") or "").strip()
        pub=str(row.get("pubDate") or "").strip()
        desc=str(row.get("description") or "").strip()
        if url:
            st.markdown(f"**[{title}]({url})**")
        else:
            st.markdown(f"**{title}**")
        meta=" · ".join(x for x in [source,pub] if x)
        if meta: st.caption(meta)
        if desc: st.write(desc[:260] + ("…" if len(desc)>260 else ""))
        st.markdown("<span class='pc-chip'>OPEN SOURCE</span><span class='pc-chip'>TRADE / GEOPOLITICAL SIGNAL</span>",unsafe_allow_html=True)
    st.caption("NewsData.io discovery feed · business/trade/geopolitics relevance-gated · cached 10 minutes · corroborate before canonical promotion")

AISHUB_URL = "https://data.aishub.net/ws.php"
NAVITIA_BASE = "https://api.navitia.io/v1"

@st.cache_data(show_spinner=False, ttl=60)
def load_aishub(username, latmin=-90.0, latmax=90.0, lonmin=-180.0, lonmax=180.0, mmsi="", imo="", interval=30):
    if not str(username).strip():
        return pd.DataFrame(), "AISHub username is not configured."
    params={
        "username":str(username).strip(),"format":1,"output":"json","compress":0,
        "latmin":float(latmin),"latmax":float(latmax),"lonmin":float(lonmin),"lonmax":float(lonmax),
        "interval":max(1,min(int(interval),1440))
    }
    if str(mmsi).strip(): params["mmsi"]=str(mmsi).strip()
    if str(imo).strip(): params["imo"]=str(imo).strip()
    try:
        req=Request(AISHUB_URL+"?"+urlencode(params),headers={"User-Agent":"PC-Trade-System/2.9"})
        with urlopen(req,timeout=15) as response:
            payload=json.loads(response.read().decode("utf-8",errors="replace"))
        if isinstance(payload,list) and len(payload)>=2 and isinstance(payload[0],dict):
            if payload[0].get("ERROR"):
                return pd.DataFrame(), str(payload[0])
            df=pd.DataFrame(payload[1] or [])
        else:
            return pd.DataFrame(), "Unexpected AISHub response format."
        if not df.empty:
            for c in ["LATITUDE","LONGITUDE","SOG","COG","DRAUGHT"]:
                if c in df.columns: df[c]=pd.to_numeric(df[c],errors="coerce")
        return df,""
    except (HTTPError,URLError,TimeoutError,ValueError,OSError) as exc:
        return pd.DataFrame(),str(exc)

@st.cache_data(show_spinner=False, ttl=1800)
def navitia_get(token, path, params=None):
    if not str(token).strip():
        return None, "Navitia token is not configured."
    url=NAVITIA_BASE+path
    if params: url += "?"+urlencode(params,doseq=True)
    try:
        req=Request(url,headers={"Authorization":str(token).strip(),"User-Agent":"PC-Trade-System/2.7"})
        with urlopen(req,timeout=15) as response:
            return json.loads(response.read().decode("utf-8",errors="replace")),""
    except (HTTPError,URLError,TimeoutError,ValueError,OSError) as exc:
        return None,str(exc)

def _navitia_places_frame(payload):
    rows=[]
    for item in (payload or {}).get("places",[]):
        obj=item.get(item.get("embedded_type",""),{}) if isinstance(item,dict) else {}
        coord=(obj or {}).get("coord",{}) or {}
        rows.append({
            "Name":item.get("name","") if isinstance(item,dict) else "",
            "Type":item.get("embedded_type","") if isinstance(item,dict) else "",
            "ID":item.get("id","") if isinstance(item,dict) else "",
            "Latitude":pd.to_numeric(coord.get("lat"),errors="coerce"),
            "Longitude":pd.to_numeric(coord.get("lon"),errors="coerce")
        })
    return pd.DataFrame(rows)

def _navitia_disruptions_frame(payload):
    rows=[]
    for d in (payload or {}).get("disruptions",[]):
        sev=(d.get("severity") or {}) if isinstance(d,dict) else {}
        periods=d.get("application_periods") or [] if isinstance(d,dict) else []
        p0=periods[0] if periods else {}
        rows.append({
            "Disruption":d.get("disruption_id",d.get("id","")),
            "Severity":sev.get("name",sev.get("effect","")),
            "Effect":sev.get("effect",""),
            "Cause":d.get("cause",""),
            "Updated":d.get("updated_at",""),
            "Begins":p0.get("begin",""),
            "Ends":p0.get("end","")
        })
    return pd.DataFrame(rows)

# IMF PortWatch public ArcGIS Feature Service. The layer is capped at 1,000
# records per response, so latest-day retrieval is explicitly paginated.
PORTWATCH_QUERY_URL = "https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services/Daily_Ports_Data/FeatureServer/0/query"
PORTWATCH_PAGE_SIZE = 1000
PORTWATCH_FIELDS = [
    "date","year","month","day","portid","portname","country","ISO3",
    "portcalls_container","portcalls_dry_bulk","portcalls_general_cargo","portcalls_roro","portcalls_tanker","portcalls_cargo","portcalls",
    "import_container","import_dry_bulk","import_general_cargo","import_roro","import_tanker","import_cargo","import",
    "export_container","export_dry_bulk","export_general_cargo","export_roro","export_tanker","export_cargo","export","ObjectId"
]
PORTWATCH_NUMERIC = [c for c in PORTWATCH_FIELDS if c.startswith(("portcalls","import","export"))] + ["year","month","day","ObjectId"]

def _portwatch_request(params):
    url = PORTWATCH_QUERY_URL + "?" + urlencode(params)
    req = Request(url, headers={"User-Agent":"PC-Trade-System/2.9"})
    with urlopen(req, timeout=12) as response:
        payload=json.loads(response.read().decode("utf-8"))
    if "error" in payload:
        message=payload.get("error",{}).get("message","PortWatch API error")
        details=payload.get("error",{}).get("details",[])
        raise ValueError(message + (": " + "; ".join(details) if details else ""))
    return payload

def _portwatch_frame(features):
    rows=[f.get("attributes",{}) for f in features or []]
    df=pd.DataFrame(rows)
    if df.empty:
        return df
    for c in PORTWATCH_NUMERIC:
        if c in df.columns:
            df[c]=pd.to_numeric(df[c],errors="coerce")
    if {"year","month","day"}.issubset(df.columns):
        df["Date"]=pd.to_datetime(dict(year=df["year"],month=df["month"],day=df["day"]),errors="coerce")
    elif "date" in df.columns:
        df["Date"]=pd.to_datetime(df["date"],errors="coerce")
    return df

@st.cache_data(show_spinner=False, ttl=1800)
def load_portwatch_latest():
    """Return the newest complete PortWatch day available, with ArcGIS pagination."""
    try:
        newest=_portwatch_request({
            "where":"1=1",
            "outFields":"date,year,month,day,ObjectId",
            "orderByFields":"date DESC,ObjectId DESC",
            "resultRecordCount":1,
            "returnGeometry":"false",
            "f":"json",
        })
        features=newest.get("features",[])
        if not features:
            return pd.DataFrame(), "No PortWatch records returned", ""
        a=features[0].get("attributes",{})
        y,m,d=(int(a.get("year")),int(a.get("month")),int(a.get("day")))
        where=f"year={y} AND month={m} AND day={d}"
        all_features=[]
        offset=0
        while True:
            payload=_portwatch_request({
                "where":where,
                "outFields":",".join(PORTWATCH_FIELDS),
                "orderByFields":"ObjectId ASC",
                "resultOffset":offset,
                "resultRecordCount":PORTWATCH_PAGE_SIZE,
                "returnGeometry":"false",
                "f":"json",
            })
            batch=payload.get("features",[])
            all_features.extend(batch)
            exceeded=bool(payload.get("exceededTransferLimit",False))
            if len(batch) < PORTWATCH_PAGE_SIZE and not exceeded:
                break
            if not batch:
                break
            offset += len(batch)
            if offset >= 25000:
                raise ValueError("PortWatch pagination safety limit reached")
        return _portwatch_frame(all_features), "", f"{y:04d}-{m:02d}-{d:02d}"
    except (HTTPError, URLError, TimeoutError, ValueError, OSError, TypeError) as exc:
        return pd.DataFrame(), str(exc), ""

@st.cache_data(show_spinner=False, ttl=1800)
def load_portwatch_history(portid, observations=90):
    """Load recent daily observations for a single PortWatch port."""
    if not str(portid).strip():
        return pd.DataFrame(), "Missing port identifier"
    safe=str(portid).replace("'","''")
    try:
        payload=_portwatch_request({
            "where":f"portid='{safe}'",
            "outFields":",".join(PORTWATCH_FIELDS),
            "orderByFields":"date DESC,ObjectId DESC",
            "resultRecordCount":max(7,min(int(observations),365)),
            "returnGeometry":"false",
            "f":"json",
        })
        return _portwatch_frame(payload.get("features",[])), ""
    except (HTTPError, URLError, TimeoutError, ValueError, OSError, TypeError) as exc:
        return pd.DataFrame(), str(exc)


def _norm_place_name(v):
    s=str(v or "").strip().casefold()
    s=re.sub(r"\b(port of|port|harbour|harbor|terminal|terminals)\b"," ",s)
    s=s.replace("&"," and ")
    s=re.sub(r"[^a-z0-9]+"," ",s)
    return re.sub(r"\s+"," ",s).strip()

def match_portwatch_port(live, canonical_name, country=""):
    """Conservatively match a canonical P&C port to one PortWatch record."""
    if live is None or live.empty or "portname" not in live.columns:
        return pd.DataFrame(), 0.0
    cname=_norm_place_name(canonical_name)
    ccountry=str(country or "").strip().casefold()
    if not cname:
        return pd.DataFrame(), 0.0
    candidates=live.copy()
    if ccountry and "country" in candidates.columns:
        same=candidates[candidates["country"].astype(str).str.casefold().eq(ccountry)]
        if not same.empty:
            candidates=same
    scored=[]
    for idx,r in candidates.iterrows():
        pname=_norm_place_name(r.get("portname",""))
        if not pname:
            continue
        if pname == cname:
            score=1.0
        elif pname in cname or cname in pname:
            score=0.92
        else:
            score=SequenceMatcher(None,cname,pname).ratio()
        if ccountry and str(r.get("country","")).strip().casefold()==ccountry:
            score=min(1.0,score+0.04)
        scored.append((score,idx))
    if not scored:
        return pd.DataFrame(), 0.0
    score,idx=max(scored,key=lambda x:x[0])
    if score < 0.68:
        return pd.DataFrame(), score
    return live.loc[[idx]].copy(), score

def render_portwatch_port_snapshot(port_name, country):
    """Live PortWatch context embedded in the canonical Trade port page."""
    live,error,latest_date=load_portwatch_latest()
    status="live"
    if not error and not live.empty:
        st.session_state["portwatch_last_good"]=(live.copy(),latest_date)
    elif error and "portwatch_last_good" in st.session_state:
        live,latest_date=st.session_state["portwatch_last_good"]
        status="stale"

    st.markdown("### PortWatch · latest operational day")
    if live is None or live.empty:
        st.caption("Live PortWatch data is currently unavailable for this port.")
        return

    match,score=match_portwatch_port(live,port_name,country)
    if match.empty:
        st.caption(f"No confident PortWatch match for {port_name} on the latest available day ({latest_date or 'unknown'}).")
        return

    r=match.iloc[0]
    matched_name=str(r.get("portname","")).strip()
    status_text="live API" if status=="live" else "last successful snapshot"
    st.caption(f"IMF PortWatch · {latest_date} · {status_text} · matched to {matched_name} ({score:.0%})")

    def n(col):
        v=pd.to_numeric(pd.Series([r.get(col)]),errors="coerce").iloc[0]
        return None if pd.isna(v) else float(v)

    metrics=[
        ("Port calls",n("portcalls")),
        ("Container calls",n("portcalls_container")),
        ("Tanker calls",n("portcalls_tanker")),
        ("Imports",n("import")),
        ("Exports",n("export")),
    ]
    cols=st.columns(5)
    for c,(label,value) in zip(cols,metrics):
        c.metric(label,"—" if value is None else f"{value:,.0f}")

    portid=str(r.get("portid","")).strip()
    if portid:
        hist,herr=load_portwatch_history(portid,30)
        if not hist.empty and "Date" in hist.columns:
            h=hist.sort_values("Date").copy()
            use=[c for c in ["portcalls","import","export"] if c in h.columns]
            if use:
                st.caption("Recent PortWatch trend · 30 observations")
                chart=h.set_index("Date")[use].rename(columns={
                    "portcalls":"Port calls","import":"Imports","export":"Exports"
                })
                st.line_chart(chart,use_container_width=True)
        elif herr:
            st.caption("Recent PortWatch history is temporarily unavailable.")

def _trade_context_tokens(row):
    raw=" ".join(str(row.get(c,"") or "") for c in [
        "Country","Location / System","Issue","Potential Mode Impact","Potential Trade / Commercial Impact"
    ])
    words=re.findall(r"[A-Za-z0-9À-ÿ'-]+",raw.casefold())
    stop={"the","and","with","from","over","for","into","major","potential","current","system",
          "action","trade","commercial","impact","country","location","port","ports","airport",
          "airports","rail","week","weeks","days"}
    return [w for w in words if len(w)>=4 and w not in stop][:30]

def infer_trade_disruption_context(row):
    """Find canonical network objects that appear materially connected to a disruption watch."""
    tokens=_trade_context_tokens(row)
    location=str(row.get("Location / System","") or "")
    issue=str(row.get("Issue","") or "")
    hay=(location+" "+issue).casefold()

    out={}
    companies=TABLES.get(("Core Entities","Companies"),pd.DataFrame()).copy()
    ports=TABLES.get(("Maritime","Ports"),pd.DataFrame()).copy()
    corridors=TABLES.get(("Infrastructure","Corridors"),pd.DataFrame()).copy()
    railnets=TABLES.get(("Rail","Rail Networks"),pd.DataFrame()).copy()
    railnodes=TABLES.get(("Rail","Rail Nodes"),pd.DataFrame()).copy()

    if not companies.empty and "Company" in companies.columns:
        mask=pd.Series(False,index=companies.index)
        for i,nm in companies["Company"].fillna("").astype(str).items():
            n=nm.casefold().strip()
            if len(n)>=4 and n in hay:
                mask.loc[i]=True
        out["Companies"]=companies[mask].head(8)

    if not ports.empty and "Port / Facility" in ports.columns:
        mask=pd.Series(False,index=ports.index)
        normloc=_norm_place_name(location)
        for i,nm in ports["Port / Facility"].fillna("").astype(str).items():
            n=_norm_place_name(nm)
            if n and normloc and (n in normloc or normloc in n):
                mask.loc[i]=True
        out["Ports"]=ports[mask].head(8)

    def token_match(df,cols):
        if df.empty:
            return df
        mask=pd.Series(False,index=df.index)
        for c in cols:
            if c not in df.columns:
                continue
            s=df[c].fillna("").astype(str).str.casefold()
            for t in tokens:
                mask |= s.str.contains(re.escape(t),na=False)
        return df[mask].head(8)

    out["Corridors"]=token_match(corridors,["Corridor","Country / Region","Connects","Primary Traffic","Strategic Note"])
    out["Rail Networks"]=token_match(railnets,["Network / Corridor","Countries / Jurisdictions","Start Node","End Node","Primary Cargo / Role"])
    out["Rail Nodes"]=token_match(railnodes,["Node","Country","Node Type","Notes"])
    return out

def render_trade_disruption_brief(row):
    st.markdown("### Selected disruption")
    c1,c2,c3=st.columns(3)
    c1.metric("Status",str(row.get("Current Status","") or "—"))
    c2.metric("Probability / read",str(row.get("Probability / Read","") or "—"))
    c3.metric("Time horizon",str(row.get("Time Horizon","") or "—"))

    st.markdown(
        f"""<div class='pc-card'>
        <div class='pc-label'>{row.get('Family','')} · {row.get('Country','')}</div>
        <div class='pc-big'>{row.get('Location / System','')}</div>
        <div class='pc-search-details' style='margin-top:8px;'>{row.get('Issue','')}</div>
        <div style='margin-top:12px;'><b>Mode impact:</b> {row.get('Potential Mode Impact','')}</div>
        <div style='margin-top:8px;'><b style='color:#D8B45A;'>Trade / commercial impact:</b> {row.get('Potential Trade / Commercial Impact','')}</div>
        <div style='margin-top:8px;'><b>Trigger / threshold:</b> {row.get('Trigger / Threshold','')}</div>
        </div>""",
        unsafe_allow_html=True
    )

    ctx=infer_trade_disruption_context(row)
    nonempty={k:v for k,v in ctx.items() if isinstance(v,pd.DataFrame) and not v.empty}
    st.markdown("### Connected trade exposure")
    if not nonempty:
        st.caption("No canonical company, port, corridor or rail asset has been confidently linked to this watch yet.")
        return
    if "Companies" in nonempty:
        st.markdown("**Companies**")
        display_df(nonempty["Companies"],150)
    if "Ports" in nonempty:
        st.markdown("**Ports**")
        display_df(nonempty["Ports"],150)
    if "Corridors" in nonempty:
        st.markdown("**Corridors / systems**")
        display_df(nonempty["Corridors"],170)
    if "Rail Networks" in nonempty:
        st.markdown("**Rail networks**")
        display_df(nonempty["Rail Networks"],150)
    if "Rail Nodes" in nonempty:
        st.markdown("**Rail nodes**")
        display_df(nonempty["Rail Nodes"],150)

@st.cache_data(show_spinner=False)
def all_tables():
    out={}
    for wb_label in WORKBOOKS:
        for sheet in workbook_sheets(wb_label):
            df=load_sheet(wb_label,sheet)
            if not df.empty: out[(wb_label,sheet)] = df
    return out

TABLES=all_tables()

def _canonical_db_event_frames():
    """Return normalized Supabase events/locations in the legacy dataframe shape.

    Canonical normalized tables are authoritative when available. The existing
    workbook/legacy bridge remains a fallback if Supabase is unavailable.
    """
    try:
        sb = pc_db_client(service=True)
        if sb is None:
            return pd.DataFrame(), pd.DataFrame()

        erows = pc_safe_rows(
            sb,
            "pc_events",
            "event_id,start_date,end_date,event_nature,event_domain,event_family,event_type,severity,status,mode,countries,location,title,description,operational_impact,commercial_impact,confidence,trade_relevance,intelligence_relevance,trade_visible,intelligence_visible,alert_worthy,record_status,source_id,metadata,event_temporality,event_phase,event_category,event_subcategory,all_day,date_precision,expected_attendance,expected_disruption,impact_probability,impact_horizon,baseline_condition,trigger_threshold,recurrence_rule,parent_event_id,calendar_year,verification_status,last_verified_at",
            5000,
            order="start_date",
        )
        lrows = pc_safe_rows(
            sb,
            "pc_event_locations",
            "event_location_id,event_id,location_name,country,latitude,longitude,accuracy,notes",
            5000,
        )

        if not erows:
            return pd.DataFrame(), pd.DataFrame()

        events = pd.DataFrame(erows).rename(columns={
            "event_id":"Event ID",
            "start_date":"Start Date",
            "end_date":"End Date",
            "event_nature":"Event Nature",
            "event_domain":"Event Domain",
            "event_family":"Event Family",
            "event_type":"Event Type",
            "severity":"Severity",
            "status":"Status",
            "mode":"Mode",
            "countries":"Country / Countries",
            "location":"Location",
            "title":"Title",
            "description":"Description",
            "operational_impact":"Operational Impact",
            "commercial_impact":"Trade / Commercial Impact",
            "confidence":"Confidence",
            "trade_relevance":"Trade Relevance",
            "intelligence_relevance":"Intelligence Relevance",
            "trade_visible":"Trade Visible",
            "intelligence_visible":"Intelligence Visible",
            "alert_worthy":"Alert Worthy",
            "record_status":"Record Status",
            "source_id":"Source ID",
            "metadata":"Metadata",
            "event_temporality":"Event Temporality",
            "event_phase":"Event Phase",
            "event_category":"Event Category",
            "event_subcategory":"Event Subcategory",
            "all_day":"All Day",
            "date_precision":"Date Precision",
            "expected_attendance":"Expected Attendance",
            "expected_disruption":"Expected Disruption",
            "impact_probability":"Impact Probability",
            "impact_horizon":"Impact Horizon",
            "baseline_condition":"Baseline Condition",
            "trigger_threshold":"Trigger Threshold",
            "recurrence_rule":"Recurrence Rule",
            "parent_event_id":"Parent Event ID",
            "calendar_year":"Calendar Year",
            "verification_status":"Verification Status",
            "last_verified_at":"Last Verified At",
        })

        if lrows:
            locations = pd.DataFrame(lrows).rename(columns={
                "event_location_id":"Location Record",
                "event_id":"Event ID",
                "location_name":"Location",
                "country":"Country",
                "latitude":"Latitude",
                "longitude":"Longitude",
                "accuracy":"Accuracy",
                "notes":"Notes",
            })
        else:
            locations = pd.DataFrame()

        return events, locations
    except Exception:
        return pd.DataFrame(), pd.DataFrame()

# Normalized canonical event tables supersede the mirrored workbook event layer.
# This is what allows newly-promoted ReCAAP records (and future DB-native events)
# to appear immediately without rebuilding an Excel workbook.
_CANON_EVENTS, _CANON_EVENT_LOCS = _canonical_db_event_frames()
if not _CANON_EVENTS.empty:
    TABLES[("Events & Hazards","Events")] = _CANON_EVENTS
if not _CANON_EVENT_LOCS.empty:
    TABLES[("Events & Hazards","Event Locations")] = _CANON_EVENT_LOCS


@st.cache_data(show_spinner=False, ttl=60)
def _canonical_db_vessel_frames():
    """Load canonical Supabase vessels, vessel/company relationships and event links.

    The normalized database is authoritative for newly-created vessels.  Results are
    projected into the legacy dataframe column names so the existing Trade UI can use
    them without maintaining a second vessel implementation.
    """
    def _db_norm_imo(value):
        s = re.sub(r"[^0-9]", "", str(value or ""))
        return s if len(s) == 7 else s

    try:
        sb = pc_db_client(service=True)
        if sb is None:
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

        # Keep this projection deliberately limited to columns verified in the
        # canonical pc_mobile_assets schema. Earlier builds requested optional fields
        # such as capacity_value/dwt/data_quality; one absent field made PostgREST
        # return no rows and the entire Trade vessel universe appeared as zero.
        vrows = pc_safe_rows(
            sb,
            "pc_mobile_assets",
            "mobile_asset_id,name,asset_type,subtype,imo,status,record_status,metadata",
            10000,
            order="name",
        )
        erows = pc_safe_rows(
            sb,
            "pc_entities",
            "entity_id,name,entity_type,subtype,hq_city,hq_country,status,record_status,metadata",
            5000,
            order="name",
        )
        lrows = pc_safe_rows(
            sb,
            "pc_event_links",
            "event_link_id,event_id,linked_type,linked_id,linked_name,relationship,confidence,source_id,metadata",
            10000,
        )
        fleet_rel_rows = pc_safe_rows(
            sb,
            "pc_relationships",
            "relationship_id,source_type,source_id,relationship_type,target_type,target_id,confidence,record_status,evidence_source_id,metadata",
            20000,
        )

        if not vrows:
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

        entities = {str(r.get("entity_id") or ""): str(r.get("name") or "") for r in (erows or [])}

        # Canonical graph roles can exist even when owner/operator columns on pc_mobile_assets
        # have not been denormalized yet. Build a target-vessel role map from pc_relationships.
        fleet_roles = defaultdict(list)
        for rr in fleet_rel_rows or []:
            if str(rr.get("source_type") or "").casefold() != "entity":
                continue
            if str(rr.get("target_type") or "").casefold() not in {"mobile_asset","vessel"}:
                continue
            vid = str(rr.get("target_id") or "").strip()
            eid = str(rr.get("source_id") or "").strip()
            rel = str(rr.get("relationship_type") or "").strip().casefold().replace("-","_").replace(" ","_")
            if vid and eid:
                fleet_roles[vid].append((rel,eid,rr))

        vessels = []
        relationships = []

        for r in vrows:
            meta = r.get("metadata") if isinstance(r.get("metadata"), dict) else {}
            vessel_id = str(r.get("mobile_asset_id") or "").strip()
            owner_id = str(r.get("owner_entity_id") or "").strip()
            operator_id = str(r.get("operator_entity_id") or "").strip()
            manager_id = str(r.get("manager_entity_id") or "").strip()

            # Fill missing denormalized roles from canonical graph edges.
            for _rel,_eid,_rr in fleet_roles.get(vessel_id,[]):
                if _rel in {"owns","owner_of"} and not owner_id:
                    owner_id=_eid
                elif _rel in {"operates","operator_of"} and not operator_id:
                    operator_id=_eid
                elif _rel in {"manages","manager_of"} and not manager_id:
                    manager_id=_eid
                elif _rel=="charters" and not operator_id:
                    operator_id=_eid

            owner_name = entities.get(owner_id, owner_id)
            operator_name = entities.get(operator_id, operator_id)
            manager_name = entities.get(manager_id, manager_id)

            # Build a readable owner/operator line without duplicating the same company.
            oo = []
            for x in [owner_name, operator_name]:
                if x and x not in oo:
                    oo.append(x)
            owner_operator = " / ".join(oo)

            research = meta.get("research_attributes") if isinstance(meta.get("research_attributes"), dict) else {}
            vessels.append({
                "Vessel ID": str(r.get("mobile_asset_id") or "").strip(),
                "Vessel Name": str(r.get("name") or "").strip(),
                "IMO": _db_norm_imo(r.get("imo")),
                "MMSI": str(research.get("mmsi") or meta.get("mmsi") or "").strip(),
                "Call Sign": str(research.get("call_sign") or meta.get("call_sign") or "").strip(),
                "Flag": str(research.get("flag") or meta.get("flag") or "").strip(),
                "Vessel Type": str(r.get("asset_type") or "").strip(),
                "Subtype / Class": str(r.get("subtype") or "").strip(),
                "Year Built": research.get("year_built") or meta.get("year_built"),
                "DWT": research.get("dwt") or meta.get("dwt"),
                "Capacity": research.get("capacity") or research.get("capacity_value") or meta.get("capacity"),
                "Capacity Unit": str(research.get("capacity_unit") or meta.get("capacity_unit") or "").strip(),
                "Owner Company ID": owner_id,
                "Operator Company ID": operator_id,
                "Manager Company ID": manager_id,
                "Owner": owner_name,
                "Operator": operator_name,
                "Manager": manager_name,
                "Owner / Operator Text": owner_operator,
                "Status": str(r.get("status") or r.get("record_status") or "").strip(),
                "Record Status": str(r.get("record_status") or "").strip(),
                "Data Quality": str(research.get("data_quality") or meta.get("data_quality") or "").strip(),
                "Source ID": str(research.get("source_id") or meta.get("source_id") or "").strip(),
                "Notes": str(meta.get("note") or meta.get("notes") or "").strip(),
                "Completeness Note": (
                    "Canonical Supabase mobile-asset record."
                    if not str(meta.get("recaap_input_name") or "").strip()
                    else "Canonical Supabase vessel resolved from ReCAAP incident data."
                ),
                "Metadata": meta,
            })

            _seen_vroles=set()
            for role, eid, ename in [
                ("Owner", owner_id, owner_name),
                ("Operator", operator_id, operator_name),
                ("Manager", manager_id, manager_name),
            ]:
                if not eid:
                    continue
                _seen_vroles.add((role.casefold(),eid))
                relationships.append({
                    "Vessel ID": vessel_id,
                    "Vessel Name": str(r.get("name") or "").strip(),
                    "Company ID": eid,
                    "Company": ename,
                    "Relationship": role,
                    "Role": role,
                    "Source ID": str(r.get("source_id") or "").strip(),
                })

            for _rel,_eid,_rr in fleet_roles.get(vessel_id,[]):
                _pretty = pretty_relationship(_rel)
                _key=(_pretty.casefold(),_eid)
                if _key in _seen_vroles:
                    continue
                relationships.append({
                    "Vessel ID": vessel_id,
                    "Vessel Name": str(r.get("name") or "").strip(),
                    "Company ID": _eid,
                    "Company": entities.get(_eid,_eid),
                    "Relationship": _pretty,
                    "Role": _pretty,
                    "Source ID": str(_rr.get("evidence_source_id") or r.get("source_id") or "").strip(),
                })

        event_links = []
        for r in (lrows or []):
            linked_type = str(r.get("linked_type") or "").strip().casefold()
            if linked_type not in {"mobile_asset", "vessel"}:
                continue
            event_links.append({
                "Link ID": str(r.get("event_link_id") or "").strip(),
                "Event ID": str(r.get("event_id") or "").strip(),
                "Asset ID": str(r.get("linked_id") or "").strip(),
                "Asset": str(r.get("linked_name") or "").strip(),
                "Relationship": str(r.get("relationship") or "").strip(),
                "Confidence": str(r.get("confidence") or "").strip(),
                "Source ID": str(r.get("source_id") or "").strip(),
                "Metadata": r.get("metadata") or {},
            })

        return (
            pd.DataFrame(vessels),
            pd.DataFrame(relationships),
            pd.DataFrame(event_links),
        )
    except Exception:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()


def _merge_canonical_vessels(legacy, canonical):
    """Merge DB vessels into the legacy display frame, preferring DB rows by ID/IMO."""
    def _merge_merge_norm_imo(value):
        return re.sub(r"[^0-9]", "", str(value or ""))
    if canonical is None or canonical.empty:
        return legacy.copy() if isinstance(legacy, pd.DataFrame) else pd.DataFrame()
    if legacy is None or legacy.empty:
        return canonical.copy()

    old = legacy.copy()
    new = canonical.copy()

    # Remove legacy rows superseded by the canonical ID or IMO.
    canon_ids = set(new.get("Vessel ID", pd.Series(dtype=str)).fillna("").astype(str))
    canon_imos = set(new.get("IMO", pd.Series(dtype=str)).map(_merge_merge_norm_imo))
    canon_imos.discard("")

    keep = pd.Series(True, index=old.index)
    if "Vessel ID" in old.columns and canon_ids:
        keep &= ~old["Vessel ID"].fillna("").astype(str).isin(canon_ids)
    if "IMO" in old.columns and canon_imos:
        keep &= ~old["IMO"].map(_merge_merge_norm_imo).isin(canon_imos)

    return pd.concat([old[keep], new], ignore_index=True, sort=False)


_CANON_VESSELS, _CANON_VESSEL_RELS, _CANON_VESSEL_EVENT_LINKS = _canonical_db_vessel_frames()

if not _CANON_VESSELS.empty:
    TABLES[("Maritime","Vessels")] = _merge_canonical_vessels(
        TABLES.get(("Maritime","Vessels"), pd.DataFrame()),
        _CANON_VESSELS,
    )

if not _CANON_VESSEL_RELS.empty:
    _legacy_vrels = TABLES.get(("Maritime","Vessel Relationships"), pd.DataFrame())
    TABLES[("Maritime","Vessel Relationships")] = pd.concat(
        [_legacy_vrels, _CANON_VESSEL_RELS],
        ignore_index=True,
        sort=False,
    ).drop_duplicates(
        subset=[c for c in ["Vessel ID","Company ID","Relationship"] if c in pd.concat([_legacy_vrels, _CANON_VESSEL_RELS], ignore_index=True, sort=False).columns],
        keep="last",
    )

if not _CANON_VESSEL_EVENT_LINKS.empty:
    _legacy_eal = TABLES.get(("Events & Hazards","Event Asset Links"), pd.DataFrame())
    _combined_eal = pd.concat(
        [_legacy_eal, _CANON_VESSEL_EVENT_LINKS],
        ignore_index=True,
        sort=False,
    )
    _dedupe_cols = [c for c in ["Event ID","Asset ID","Relationship"] if c in _combined_eal.columns]
    TABLES[("Events & Hazards","Event Asset Links")] = (
        _combined_eal.drop_duplicates(subset=_dedupe_cols, keep="last")
        if _dedupe_cols else _combined_eal
    )


# ---------- v3.3.11 live canonical trade bridge ----------
def _merge_canonical_rows(legacy, canonical, id_col, name_col=None):
    """Merge canonical DB rows into a legacy display frame, preferring DB rows by ID/name."""
    if canonical is None or canonical.empty:
        return legacy.copy() if isinstance(legacy, pd.DataFrame) else pd.DataFrame()
    if legacy is None or legacy.empty:
        return canonical.copy()

    old = legacy.copy()
    new = canonical.copy()
    keep = pd.Series(True, index=old.index)

    if id_col in old.columns and id_col in new.columns:
        ids = set(new[id_col].fillna("").astype(str).str.strip())
        ids.discard("")
        if ids:
            keep &= ~old[id_col].fillna("").astype(str).str.strip().isin(ids)

    if name_col and name_col in old.columns and name_col in new.columns:
        names = set(new[name_col].fillna("").astype(str).str.strip().str.casefold())
        names.discard("")
        if names:
            keep &= ~old[name_col].fillna("").astype(str).str.strip().str.casefold().isin(names)

    return pd.concat([old[keep], new], ignore_index=True, sort=False)


def _canonical_relationship_role_maps(rels):
    """Return asset->company role maps from canonical pc_relationships."""
    operator = {}
    owner = {}
    all_roles = defaultdict(list)
    if rels is None or rels.empty:
        return operator, owner, all_roles

    for _, r in rels.iterrows():
        stype = str(r.get("source_type") or "").strip().casefold()
        ttype = str(r.get("target_type") or "").strip().casefold()
        if stype != "entity" or ttype != "asset":
            continue
        eid = str(r.get("source_id") or "").strip()
        aid = str(r.get("target_id") or "").strip()
        rel = str(r.get("relationship_type") or "").strip().casefold().replace("-", "_").replace(" ", "_")
        if not eid or not aid:
            continue
        all_roles[aid].append((rel, eid))
        if rel in {"operates", "manages", "operator_of", "concession_holder"} and aid not in operator:
            operator[aid] = eid
        if rel in {"owns", "controls", "owner_of", "parent_of"} and aid not in owner:
            owner[aid] = eid
    return operator, owner, all_roles


@st.cache_data(show_spinner=False, ttl=60)
def _canonical_db_core_trade_frames():
    """Project live canonical Supabase entities/assets/relationships/routes into legacy Trade UI shapes."""
    try:
        sb = pc_db_client(service=True)
        if sb is None:
            return tuple(pd.DataFrame() for _ in range(7))

        erows = pc_safe_rows(
            sb, "pc_entities",
            "entity_id,name,entity_type,subtype,hq_city,hq_country,status,record_status,metadata",
            10000, order="name"
        )
        arows = pc_safe_rows(
            sb, "pc_assets",
            "asset_id,name,asset_type,subtype,country,region_city,latitude,longitude,status,record_status,metadata",
            10000, order="name"
        )
        rrows = pc_safe_rows(
            sb, "pc_relationships",
            "relationship_id,source_type,source_id,relationship_type,target_type,target_id,ownership_percent,operating_control,valid_from,valid_to,confidence,record_status,evidence_source_id,notes,metadata",
            20000
        )
        # Keep route select to fields known to exist in the executable model registry.
        trrows = pc_safe_rows(
            sb, "pc_transport_routes",
            "route_id,route_name,mode,operator_entity_id",
            10000, order="route_name"
        )
        mrows = pc_safe_rows(
            sb, "pc_mobile_assets",
            "mobile_asset_id,name,asset_type,subtype,imo,status,record_status,metadata",
            10000, order="name"
        )

        entities_df = pd.DataFrame(erows or [])
        assets_df = pd.DataFrame(arows or [])
        rels_df = pd.DataFrame(rrows or [])
        routes_df = pd.DataFrame(trrows or [])

        # ---- Companies / entity registry ----
        companies = []
        entity_registry = []
        entity_names = {}
        for r in erows or []:
            eid = str(r.get("entity_id") or "").strip()
            name = str(r.get("name") or "").strip()
            meta = r.get("metadata") if isinstance(r.get("metadata"), dict) else {}
            research = meta.get("research_attributes") if isinstance(meta.get("research_attributes"), dict) else {}
            entity_names[eid] = name
            companies.append({
                "Company ID": eid,
                "Company": name,
                "Entity Type": str(r.get("entity_type") or "").strip(),
                "Subtype": str(r.get("subtype") or "").strip(),
                "HQ City": str(r.get("hq_city") or research.get("hq_city") or "").strip(),
                "HQ Country": str(r.get("hq_country") or research.get("country") or research.get("hq_country") or "").strip(),
                "Country / Geography": str(r.get("hq_country") or research.get("country") or "").strip(),
                "Status": str(r.get("status") or r.get("record_status") or "").strip(),
                "Record Status": str(r.get("record_status") or "").strip(),
                "Ownership": str(research.get("ownership") or "").strip(),
                "Business Segments": str(research.get("business_segments") or "").strip(),
                "Markets": str(research.get("markets") or "").strip(),
                "Scale / Network Notes": str(research.get("scale") or research.get("network_notes") or "").strip(),
                "Metadata": meta,
            })
            entity_registry.append({
                "Entity ID": eid,
                "Canonical Name": name,
                "Entity Type": str(r.get("entity_type") or "").strip(),
                "Subtype": str(r.get("subtype") or "").strip(),
                "Country": str(r.get("hq_country") or research.get("country") or "").strip(),
                "Status": str(r.get("status") or r.get("record_status") or "").strip(),
                "Metadata": meta,
            })

        companies = pd.DataFrame(companies)
        entity_registry = pd.DataFrame(entity_registry)

        # ---- Canonical entity/entity, entity/asset and entity/mobile-asset graph ----
        asset_names={str(r.get("asset_id") or "").strip():str(r.get("name") or "").strip() for r in (arows or [])}
        mobile_names={str(r.get("mobile_asset_id") or "").strip():str(r.get("name") or "").strip() for r in (mrows or [])}

        def _graph_name(kind, object_id):
            k=str(kind or "").casefold()
            if k=="entity":
                return entity_names.get(object_id,object_id)
            if k=="asset":
                return asset_names.get(object_id,object_id)
            if k in {"mobile_asset","vessel"}:
                return mobile_names.get(object_id,object_id)
            return object_id

        relationships = []
        for r in rrows or []:
            sid = str(r.get("source_id") or "").strip()
            tid = str(r.get("target_id") or "").strip()
            stype = str(r.get("source_type") or "").strip()
            ttype = str(r.get("target_type") or "").strip()
            relationships.append({
                "Relationship ID": str(r.get("relationship_id") or "").strip(),
                "Source Entity": sid,
                "Source": _graph_name(stype,sid),
                "Source Type": stype,
                "Relationship": str(r.get("relationship_type") or "").strip(),
                "Target Entity": tid,
                "Target": _graph_name(ttype,tid),
                "Target Type": ttype,
                "Ownership %": r.get("ownership_percent"),
                "Operating Control": r.get("operating_control"),
                "Confidence": r.get("confidence"),
                "Record Status": str(r.get("record_status") or "").strip(),
                "Source ID": str(r.get("evidence_source_id") or "").strip(),
                "Notes": str(r.get("notes") or "").strip(),
                "Metadata": r.get("metadata") or {},
            })
        relationships = pd.DataFrame(relationships)

        op_map, owner_map, role_map = _canonical_relationship_role_maps(rels_df)

        # ---- Infrastructure assets ----
        infra_assets = []
        port_rows = []
        terminal_rows = []
        for r in arows or []:
            aid = str(r.get("asset_id") or "").strip()
            name = str(r.get("name") or "").strip()
            atype = str(r.get("asset_type") or "").strip()
            subtype = str(r.get("subtype") or "").strip()
            kind = f"{atype} {subtype}".casefold()
            name_kind = f"{name} {atype} {subtype}".casefold()
            meta = r.get("metadata") if isinstance(r.get("metadata"), dict) else {}
            research = meta.get("research_attributes") if isinstance(meta.get("research_attributes"), dict) else {}

            operator_id = op_map.get(aid, "")
            owner_id = owner_map.get(aid, "")
            company_id = operator_id or owner_id
            company_name = entity_names.get(company_id, company_id)
            role_text = "; ".join(
                f"{rel}:{entity_names.get(eid,eid)}" for rel, eid in role_map.get(aid, [])
            )

            base = {
                "Asset ID": aid,
                "Asset": name,
                "Asset Type": atype,
                "Subtype": subtype,
                "Company ID": company_id,
                "Owner / Operator Company ID": company_id,
                "Company": company_name,
                "Country": str(r.get("country") or research.get("country") or "").strip(),
                "City / Area": str(r.get("region_city") or research.get("city") or research.get("region") or "").strip(),
                "Latitude": r.get("latitude"),
                "Longitude": r.get("longitude"),
                "Status": str(r.get("status") or r.get("record_status") or "").strip(),
                "Record Status": str(r.get("record_status") or "").strip(),
                "Relationship / Role": role_text,
                "Capacity": research.get("capacity") or research.get("capacity_teu") or research.get("capacity_teu_per_year") or "",
                "Metadata": meta,
            }
            infra_assets.append(base)

            # Port-level assets. Include explicit port names even when subtype metadata is generic.
            # A port can also contain/represent a terminal, so do not suppress an explicit "... Port" name.
            _explicit_port_name = any(tok in name.casefold() for tok in (" port","port ","harbour","harbor"))
            if ("port" in kind or "harbour" in kind or "harbor" in kind or _explicit_port_name):
                port_rows.append({
                    "Port ID": aid,
                    "Port / Facility": name,
                    "Country": base["Country"],
                    "City / Area": base["City / Area"],
                    "Facility Type": atype or subtype,
                    "Operator Company ID": operator_id,
                    "Operator": entity_names.get(operator_id, operator_id),
                    "Owner Company ID": owner_id,
                    "Status": base["Status"],
                    "Latitude": base["Latitude"],
                    "Longitude": base["Longitude"],
                    "Key Role": str(research.get("role") or research.get("strategic_role") or "").strip(),
                    "Metadata": meta,
                })

            # Terminal / depot / warehouse / logistics-facility assets.
            if any(term in name_kind for term in ("terminal", "depot", "warehouse", "logistics", "crossdock", "yard")):
                terminal_rows.append({
                    "Terminal ID": aid,
                    "Terminal / Facility": name,
                    "Port ID": str(research.get("parent_port_id") or "").strip(),
                    "Parent Port": str(research.get("parent_port") or "").strip(),
                    "Country": base["Country"],
                    "City / Area": base["City / Area"],
                    "Primary Operator Company ID": operator_id or company_id,
                    "Operator / Network": entity_names.get(operator_id or company_id, operator_id or company_id),
                    "Status": base["Status"],
                    "Ownership / Structure": role_text,
                    "Facility Type": atype or subtype,
                    "Latitude": base["Latitude"],
                    "Longitude": base["Longitude"],
                    "Metadata": meta,
                })

        infra_assets = pd.DataFrame(infra_assets)
        ports = pd.DataFrame(port_rows)
        terminals = pd.DataFrame(terminal_rows)

        # ---- Transport routes ----
        routes = []
        for r in trrows or []:
            oid = str(r.get("operator_entity_id") or "").strip()
            routes.append({
                "Route ID": str(r.get("route_id") or "").strip(),
                "Route": str(r.get("route_name") or "").strip(),
                "Route Name": str(r.get("route_name") or "").strip(),
                "Mode": str(r.get("mode") or "").strip(),
                "Operator Company ID": oid,
                "Operator": entity_names.get(oid, oid),
            })
        routes = pd.DataFrame(routes)

        return companies, entity_registry, relationships, infra_assets, ports, terminals, routes
    except Exception:
        return tuple(pd.DataFrame() for _ in range(7))


(
    _CANON_COMPANIES,
    _CANON_ENTITY_REGISTRY,
    _CANON_RELATIONSHIPS,
    _CANON_INFRA_ASSETS,
    _CANON_PORTS,
    _CANON_TERMINALS,
    _CANON_TRANSPORT_ROUTES,
) = _canonical_db_core_trade_frames()

if not _CANON_COMPANIES.empty:
    TABLES[("Core Entities","Companies")] = _merge_canonical_rows(
        TABLES.get(("Core Entities","Companies"), pd.DataFrame()),
        _CANON_COMPANIES,
        "Company ID",
        "Company",
    )

if not _CANON_ENTITY_REGISTRY.empty:
    TABLES[("Core Entities","Entity Registry")] = _merge_canonical_rows(
        TABLES.get(("Core Entities","Entity Registry"), pd.DataFrame()),
        _CANON_ENTITY_REGISTRY,
        "Entity ID",
        "Canonical Name",
    )

if not _CANON_RELATIONSHIPS.empty:
    TABLES[("Core Entities","Relationships")] = _merge_canonical_rows(
        TABLES.get(("Core Entities","Relationships"), pd.DataFrame()),
        _CANON_RELATIONSHIPS,
        "Relationship ID",
        None,
    )

if not _CANON_INFRA_ASSETS.empty:
    TABLES[("Infrastructure","Assets")] = _merge_canonical_rows(
        TABLES.get(("Infrastructure","Assets"), pd.DataFrame()),
        _CANON_INFRA_ASSETS,
        "Asset ID",
        "Asset",
    )

if not _CANON_PORTS.empty:
    TABLES[("Maritime","Ports")] = _merge_canonical_rows(
        TABLES.get(("Maritime","Ports"), pd.DataFrame()),
        _CANON_PORTS,
        "Port ID",
        "Port / Facility",
    )

if not _CANON_TERMINALS.empty:
    TABLES[("Maritime","Port Terminals")] = _merge_canonical_rows(
        TABLES.get(("Maritime","Port Terminals"), pd.DataFrame()),
        _CANON_TERMINALS,
        "Terminal ID",
        "Terminal / Facility",
    )

if not _CANON_TRANSPORT_ROUTES.empty:
    # Keep a DB-native route table while also making routes discoverable in the Data/related-table layer.
    TABLES[("Infrastructure","Transport Routes")] = _merge_canonical_rows(
        TABLES.get(("Infrastructure","Transport Routes"), pd.DataFrame()),
        _CANON_TRANSPORT_ROUTES,
        "Route ID",
        "Route",
    )



# ---------- v3.3.35 canonical transactions / investments bridge ----------
@st.cache_data(show_spinner=False, ttl=60)
def _canonical_db_transaction_frames():
    """Project pc_transactions into the existing commercial and investment UI shapes.

    pc_transactions is canonical.  The workbook-shaped frames below are presentation
    adapters only, allowing newly ingested transactions to appear immediately without
    rebuilding Excel files.
    """
    try:
        sb = pc_db_client(service=True)
        if sb is None:
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

        txrows = pc_safe_rows(
            sb,
            "pc_transactions",
            "transaction_id,announced_date,effective_date,buyer_entity_id,seller_name,target_entity_id,"
            "target_asset_id,target_name,asset_class,country_region,transaction_type,equity_percent,"
            "reported_value,currency,operating_control,status,regulatory_status,source_id,notes,metadata",
            10000,
            order="announced_date",
        ) or []
        if not txrows:
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

        erows = pc_safe_rows(
            sb, "pc_entities",
            "entity_id,name,entity_type,subtype,hq_country,status,record_status,metadata",
            15000, order="name"
        ) or []
        arows = pc_safe_rows(
            sb, "pc_assets",
            "asset_id,name,asset_type,subtype,country,region_city,status,record_status,metadata",
            20000, order="name"
        ) or []
        entities = {str(r.get("entity_id") or ""): str(r.get("name") or "") for r in erows}
        assets = {str(r.get("asset_id") or ""): str(r.get("name") or "") for r in arows}

        tx_display=[]
        infra_deals=[]
        investments=[]

        for r in txrows:
            meta = r.get("metadata") if isinstance(r.get("metadata"), dict) else {}
            tid = str(r.get("transaction_id") or "").strip()
            buyer_id = str(r.get("buyer_entity_id") or "").strip()
            target_entity_id = str(r.get("target_entity_id") or "").strip()
            target_asset_id = str(r.get("target_asset_id") or "").strip()
            buyer = entities.get(buyer_id, buyer_id)
            target_entity = entities.get(target_entity_id, target_entity_id)
            target_asset = assets.get(target_asset_id, target_asset_id)
            target_name = str(r.get("target_name") or target_asset or target_entity or "").strip()
            announced = r.get("announced_date") or r.get("effective_date")
            value = r.get("reported_value")
            currency = str(r.get("currency") or "").strip()
            tx_type = str(r.get("transaction_type") or "").strip()
            country_region = str(r.get("country_region") or "").strip()
            status = str(r.get("status") or "").strip()

            common={
                "Transaction ID": tid,
                "Announced Date": announced,
                "Effective Date": r.get("effective_date"),
                "Buyer Company ID": buyer_id,
                "Buyer": buyer,
                "Seller": str(r.get("seller_name") or "").strip(),
                "Target Company ID": target_entity_id,
                "Target Asset ID": target_asset_id,
                "Target Company": target_entity or target_name,
                "Target / Asset": target_name,
                "Asset Class": str(r.get("asset_class") or "").strip(),
                "Country / Region": country_region,
                "Transaction Type": tx_type,
                "Equity %": r.get("equity_percent"),
                "Reported Value": value,
                "Currency": currency,
                "Operating Control": r.get("operating_control"),
                "Status": status,
                "Regulatory Status": str(r.get("regulatory_status") or "").strip(),
                "Source ID": str(r.get("source_id") or "").strip(),
                "Notes": str(r.get("notes") or "").strip(),
                "Metadata": meta,
            }
            tx_display.append(common)

            # Infrastructure/commercial deal projection for the existing Contracts page.
            infra_deals.append({
                "Deal ID": tid,
                "Announced Date": announced,
                "Investor / Buyer IDs": buyer_id,
                "Investor / Buyer": buyer,
                "Target / Asset": target_name,
                "Deal Type": tx_type,
                "Asset Class": str(r.get("asset_class") or "").strip(),
                "Country / Region": country_region,
                "Reported Value": value,
                "Currency": currency,
                "Equity %": r.get("equity_percent"),
                "Status": status,
                "Regulatory Status": str(r.get("regulatory_status") or "").strip(),
                "Source ID": str(r.get("source_id") or "").strip(),
                "Notes": str(r.get("notes") or "").strip(),
                "Metadata": meta,
            })

            tnorm=tx_type.casefold().replace("_"," ").replace("-"," ")
            if any(x in tnorm for x in ("acquisition","stake","equity","sale")):
                spend_type="Acquisition / equity"
            elif any(x in tnorm for x in ("procurement","contract","equipment")):
                spend_type="Procurement / equipment"
            elif any(x in tnorm for x in ("lease","concession")):
                spend_type="Lease / concession"
            else:
                spend_type="Investment / transaction"

            fiscal_year=""
            try:
                fiscal_year=str(pd.to_datetime(announced,errors="coerce").year)
                if fiscal_year=="nan": fiscal_year=""
            except Exception:
                fiscal_year=""

            # The buyer is the primary investment actor where known.  Keep target IDs
            # separately so detail pages can later expose both sides without duplicating value.
            investments.append({
                "Transaction ID": tid,
                "Company ID": buyer_id or target_entity_id,
                "Counterparty / Target Company ID": target_entity_id,
                "Announced Date": announced,
                "Fiscal Year": fiscal_year,
                "Project": target_name or tx_type,
                "Country": country_region,
                "Region": country_region,
                "Asset / Location": target_name,
                "Investment Class": tx_type,
                "Spend Type": spend_type,
                "Reported Value": value,
                "Currency": currency,
                "USD Value if Reported": value if currency.upper()=="USD" else None,
                "Value Status": "Reported" if value is not None else "Undisclosed",
                "Status": status,
                "Investment Stage": status,
                "Capacity / Scope": str(meta.get("scope") or meta.get("capacity") or "").strip(),
                "Strategic Relevance": str(meta.get("strategic_relevance") or "").strip(),
                "Seller": str(r.get("seller_name") or "").strip(),
                "Equity %": r.get("equity_percent"),
                "Regulatory Status": str(r.get("regulatory_status") or "").strip(),
                "Source ID": str(r.get("source_id") or "").strip(),
                "Notes": str(r.get("notes") or "").strip(),
                "Metadata": meta,
            })

        return pd.DataFrame(tx_display), pd.DataFrame(infra_deals), pd.DataFrame(investments)
    except Exception:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()


_CANON_TRANSACTIONS, _CANON_INFRA_DEALS, _CANON_INVESTMENTS = _canonical_db_transaction_frames()

if not _CANON_TRANSACTIONS.empty:
    TABLES[("Transactions","Transactions V125")] = _merge_canonical_rows(
        TABLES.get(("Transactions","Transactions V125"), pd.DataFrame()),
        _CANON_TRANSACTIONS,
        "Transaction ID",
        None,
    )

if not _CANON_INFRA_DEALS.empty:
    TABLES[("Transactions","Infra Deals")] = _merge_canonical_rows(
        TABLES.get(("Transactions","Infra Deals"), pd.DataFrame()),
        _CANON_INFRA_DEALS,
        "Deal ID",
        None,
    )

if not _CANON_INVESTMENTS.empty:
    TABLES[("Corporate & Markets","Investments")] = _merge_canonical_rows(
        TABLES.get(("Corporate & Markets","Investments"), pd.DataFrame()),
        _CANON_INVESTMENTS,
        "Transaction ID",
        None,
    )

# ---------- v3.3.3 geographic + cruise integration ----------
def _ref_port_display_name(raw):
    raw=str(raw or "").strip()
    if "_" in raw:
        return raw.rsplit("_",1)[0].replace("_"," ").strip()
    return raw.replace("_"," ").strip()

def _ref_port_country(raw):
    raw=str(raw or "").strip()
    return raw.rsplit("_",1)[1].strip() if "_" in raw else ""

def _port_match_key(v):
    x=str(v or "").casefold().replace("&"," and ").replace("_"," ")
    x=re.sub(r"\b(port of|port|harbour|harbor|terminal|deep sea|sea port|seaport|international|container|dock|wharf|gang)\b"," ",x)
    x=re.sub(r"[^a-z0-9]+"," ",x)
    return " ".join(x.split())

@st.cache_data(show_spinner=False, ttl=300)
def global_port_reference_view():
    ref=TABLES.get(("Global Ports Reference","Global Port Reference"),pd.DataFrame()).copy()
    if ref.empty:
        return ref
    ref["Port Name"]=ref.get("name",pd.Series(index=ref.index,dtype=str)).map(_ref_port_display_name)
    ref["Country Name"]=ref.get("name",pd.Series(index=ref.index,dtype=str)).map(_ref_port_country)
    ref["Latitude"]=pd.to_numeric(ref.get("lat"),errors="coerce")
    ref["Longitude"]=pd.to_numeric(ref.get("lon"),errors="coerce")
    for c in ["export","import","trans","throughput"]:
        if c in ref.columns: ref[c]=pd.to_numeric(ref[c],errors="coerce")
    return ref[ref["Latitude"].notna() & ref["Longitude"].notna()].copy()

def enrich_ports_from_reference(ports):
    """Populate canonical port coordinates from the uploaded 1,377-port reference where names match safely."""
    if ports is None or ports.empty:
        return pd.DataFrame() if ports is None else ports.copy()
    out=ports.copy()
    # pandas 3.x is strict about writing floats into object/string-backed columns.
    # Normalize coordinates to numeric before enrichment so reference matches cannot crash the Ports page.
    if "Latitude" not in out.columns: out["Latitude"]=float("nan")
    if "Longitude" not in out.columns: out["Longitude"]=float("nan")
    out["Latitude"]=pd.to_numeric(out["Latitude"],errors="coerce")
    out["Longitude"]=pd.to_numeric(out["Longitude"],errors="coerce")
    if "Geo Source" not in out.columns: out["Geo Source"]=""
    out["Geo Source"]=out["Geo Source"].astype("object")
    ref=global_port_reference_view()
    if ref.empty: return out
    r=ref.copy(); r["_key"]=r["Port Name"].map(_port_match_key)
    # exact normalized-name matches only; avoids attaching a port to a wrong same-country facility.
    lookup={}
    for _,rr in r.iterrows():
        k=rr.get("_key","")
        if k and k not in lookup:
            lookup[k]=(rr["Latitude"],rr["Longitude"],rr["Port Name"],rr["Country Name"])
    for idx,row in out.iterrows():
        lat=pd.to_numeric(pd.Series([row.get("Latitude","")]),errors="coerce").iloc[0]
        lon=pd.to_numeric(pd.Series([row.get("Longitude","")]),errors="coerce").iloc[0]
        if pd.notna(lat) and pd.notna(lon): continue
        k=_port_match_key(row.get("Port / Facility",""))
        hit=lookup.get(k)
        if hit:
            out.at[idx,"Latitude"]=hit[0]; out.at[idx,"Longitude"]=hit[1]
            out.at[idx,"Geo Source"]="Global Port Reference (name match)"
    return out


@st.cache_data(show_spinner=False, ttl=60)
def live_canonical_port_view():
    """Project live pc_assets port records into the Trade port explorer schema.

    The canonical DB is authoritative. Exclude airports/airbases so the substring
    'port' in 'airport' never contaminates the port explorer.
    """
    try:
        sb=pc_db_client(service=True)
        if sb is None:
            return pd.DataFrame()

        rows=pc_safe_rows(
            sb,
            "pc_assets",
            "asset_id,name,asset_type,subtype,country,region_city,latitude,longitude,"
            "operator_entity_id,owner_entity_id,status,record_status,data_quality,source_id,metadata",
            50000
        )
        if not rows:
            return pd.DataFrame()

        df=pd.DataFrame(rows)

        def _is_portish(row):
            at=str(row.get("asset_type") or "").casefold()
            stp=str(row.get("subtype") or "").casefold()
            name=str(row.get("name") or "").casefold()

            # Explicitly exclude aviation contamination.
            bad=("airport","airbase","aviation","airfield","runway")
            if any(x in at or x in stp or x in name for x in bad):
                return False

            good_tokens=(
                "port","seaport","harbour","harbor","marine_terminal",
                "container_terminal","cruise_terminal","multipurpose_terminal",
                "dry_port","river_port","commercial_port"
            )
            return any(
                t in at or t in stp
                for t in good_tokens
            ) or (
                ("port" in name or "harbour" in name or "harbor" in name)
                and not any(x in name for x in bad)
            )

        df=df[df.apply(_is_portish,axis=1)].copy()

        # Canonical port explorer must not expose retired/merged aliases as
        # selectable live ports. Alias rows remain in pc_assets for provenance
        # and identity-resolution edges, but operational screens follow the
        # active canonical object.
        if not df.empty:
            _status=df.get("status",pd.Series(index=df.index,dtype=str)).fillna("").astype(str).str.casefold()
            _subtype=df.get("subtype",pd.Series(index=df.index,dtype=str)).fillna("").astype(str).str.casefold()
            df=df[
                ~_status.isin({
                    "legacy alias / merged",
                    "legacy alias / do not count",
                    "retired",
                    "inactive",
                })
                & ~_subtype.eq("port_alias")
            ].copy()

        if df.empty:
            return pd.DataFrame()

        # Resolve operator names when available.
        entity_ids=set(df.get("operator_entity_id",pd.Series(dtype=str)).dropna().astype(str))
        entity_ids |= set(df.get("owner_entity_id",pd.Series(dtype=str)).dropna().astype(str))
        emap={}
        if entity_ids:
            erows=pc_safe_rows(sb,"pc_entities","entity_id,name",50000)
            emap={str(r.get("entity_id")):r.get("name") for r in erows if r.get("entity_id")}

        out=pd.DataFrame({
            "Port ID":df["asset_id"].astype(str),
            "Port / Facility":df["name"].fillna("").astype(str),
            "Country":df.get("country",pd.Series(index=df.index,dtype=str)).fillna("").astype(str),
            "City / Area":df.get("region_city",pd.Series(index=df.index,dtype=str)).fillna("").astype(str),
            "Latitude":pd.to_numeric(df.get("latitude"),errors="coerce"),
            "Longitude":pd.to_numeric(df.get("longitude"),errors="coerce"),
            "Operator Company ID":df.get("operator_entity_id",pd.Series(index=df.index,dtype=str)).fillna("").astype(str),
            "Operator":df.get("operator_entity_id",pd.Series(index=df.index,dtype=str)).fillna("").astype(str).map(emap).fillna(""),
            "Owner Company ID":df.get("owner_entity_id",pd.Series(index=df.index,dtype=str)).fillna("").astype(str),
            "Owner":df.get("owner_entity_id",pd.Series(index=df.index,dtype=str)).fillna("").astype(str).map(emap).fillna(""),
            "Facility Type":df.get("subtype",pd.Series(index=df.index,dtype=str)).fillna(
                df.get("asset_type",pd.Series(index=df.index,dtype=str))
            ).astype(str),
            "Status":df.get("status",pd.Series(index=df.index,dtype=str)).fillna("").astype(str),
            "Record Status":df.get("record_status",pd.Series(index=df.index,dtype=str)).fillna("").astype(str),
            "Data Quality":df.get("data_quality",pd.Series(index=df.index,dtype=str)).fillna("").astype(str),
            "Source ID":df.get("source_id",pd.Series(index=df.index,dtype=str)).fillna("").astype(str),
            "Canonical Source":"pc_assets",
            "Metadata":df.get("metadata",pd.Series(index=df.index,dtype=object)),
        })
        return out
    except Exception:
        return pd.DataFrame()


def unified_ports_with_reference(ports):
    """Live canonical ports + legacy port rows + geocoded reference-only seeds.

    pc_assets is authoritative. Legacy/reference rows only fill genuine gaps.
    """
    legacy=enrich_ports_from_reference(ports)
    live=live_canonical_port_view()

    frames=[]
    if not live.empty:
        frames.append(live)
    if not legacy.empty:
        frames.append(legacy)

    if frames:
        canonical=pd.concat(frames,ignore_index=True,sort=False)
    else:
        canonical=pd.DataFrame()

    # Prefer the live canonical pc_assets row when a duplicate ID/name exists.
    if not canonical.empty:
        canonical["_priority"]=canonical.get(
            "Canonical Source",pd.Series(index=canonical.index,dtype=str)
        ).fillna("").astype(str).eq("pc_assets").astype(int)

        if "Port ID" in canonical.columns:
            canonical=canonical.sort_values("_priority",ascending=False).drop_duplicates(
                subset=["Port ID"],keep="first"
            )

        canonical["_name_key"]=canonical.get(
            "Port / Facility",pd.Series(index=canonical.index,dtype=str)
        ).map(_port_match_key)
        canonical["_country_key"]=canonical.get(
            "Country",pd.Series(index=canonical.index,dtype=str)
        ).map(_port_match_key)

        # Treat UAE and United Arab Emirates as the same country for dedupe.
        canonical["_country_key"]=canonical["_country_key"].replace({
            "uae":"united arab emirates"
        })

        canonical=canonical.sort_values("_priority",ascending=False).drop_duplicates(
            subset=["_name_key","_country_key"],keep="first"
        ).drop(columns=["_priority","_name_key","_country_key"],errors="ignore")

    ref=global_port_reference_view()
    if ref.empty:
        return canonical

    existing=set()
    if not canonical.empty:
        for _,r in canonical.iterrows():
            ck=_port_match_key(r.get("Country",""))
            if ck=="uae":
                ck="united arab emirates"
            existing.add((_port_match_key(r.get("Port / Facility","")),ck))

    rows=[]
    for _,r in ref.iterrows():
        ck=_port_match_key(r.get("Country Name",""))
        if ck=="uae":
            ck="united arab emirates"
        key=(_port_match_key(r.get("Port Name","")),ck)
        if key in existing:
            continue
        rows.append({
            "Port ID":f"REF_{r.get('id','')}",
            "Port / Facility":r.get("Port Name",""),
            "Country":r.get("Country Name",""),
            "Latitude":r.get("Latitude",""),
            "Longitude":r.get("Longitude",""),
            "Operator Company ID":"",
            "Operator":"",
            "Facility Type":"Reference port seed",
            "Key Role":"Global trade / port reference",
            "Coverage Note":"Geocoded reference seed — canonical operator, terminal and ownership enrichment pending.",
            "Source ID":"GLOBAL_PORT_REFERENCE",
            "Geo Source":"Global Port Reference"
        })
    if rows:
        canonical=pd.concat([canonical,pd.DataFrame(rows)],ignore_index=True,sort=False)

    return canonical


@st.cache_data(show_spinner=False, ttl=1800)
def join_portwatch_to_pc_ports(live, ports):
    """Join latest PortWatch activity onto canonical/reference P&C geography without replacing P&C coordinates."""
    if live is None or live.empty or ports is None or ports.empty:
        return pd.DataFrame()
    p=ports.copy()
    l=live.copy()
    p["_name_key"]=p.get("Port / Facility",pd.Series(index=p.index,dtype=str)).map(_port_match_key)
    p["_country_key"]=p.get("Country",pd.Series(index=p.index,dtype=str)).map(_port_match_key)
    l["_name_key"]=l.get("portname",pd.Series(index=l.index,dtype=str)).map(_port_match_key)
    l["_country_key"]=l.get("country",pd.Series(index=l.index,dtype=str)).map(_port_match_key)
    metrics=[c for c in ["portid","portname","country","ISO3","Date","portcalls","portcalls_container","portcalls_dry_bulk","portcalls_general_cargo","portcalls_roro","portcalls_tanker","import","export"] if c in l.columns]
    exact=p.merge(l[metrics+["_name_key","_country_key"]],on=["_name_key","_country_key"],how="inner",suffixes=("","_pw"))
    if not exact.empty:
        exact["PortWatch Match Confidence"]=1.0
        exact["PortWatch Match Method"]="normalized port + country"
    matched_p=set(exact.index.tolist()) if not exact.empty else set()
    # Name-only fallback is permitted only where the PortWatch name is unique globally.
    counts=l.groupby("_name_key").size() if "_name_key" in l.columns else pd.Series(dtype=int)
    unique_names=set(counts[counts==1].index)
    already_keys=set(zip(exact.get("Port ID",pd.Series(dtype=str)).astype(str),exact.get("portid",pd.Series(dtype=str)).astype(str))) if not exact.empty else set()
    fall=[]
    exact_port_ids=set(exact.get("Port ID",pd.Series(dtype=str)).astype(str)) if not exact.empty and "Port ID" in exact.columns else set()
    l_lookup={r["_name_key"]:r for _,r in l[l["_name_key"].isin(unique_names)].iterrows()}
    for _,pr in p.iterrows():
        if str(pr.get("Port ID","")) in exact_port_ids: continue
        k=pr.get("_name_key","")
        lr=l_lookup.get(k)
        if lr is None: continue
        row=pr.to_dict()
        for c in metrics: row[c]=lr.get(c)
        row["PortWatch Match Confidence"]=0.94
        row["PortWatch Match Method"]="unique normalized port name"
        fall.append(row)
    if fall:
        exact=pd.concat([exact,pd.DataFrame(fall)],ignore_index=True,sort=False)
    for c in ["Latitude","Longitude","portcalls","portcalls_container","portcalls_tanker","import","export"]:
        if c in exact.columns: exact[c]=pd.to_numeric(exact[c],errors="coerce")
    return exact.drop(columns=[c for c in ["_name_key","_country_key"] if c in exact.columns],errors="ignore")

def render_portwatch_operational_map(joined, height=470):
    if joined is None or joined.empty:
        st.caption("No PortWatch observations could be joined to mapped P&C ports on the latest available day.")
        return
    m=joined.copy()
    m=m[pd.to_numeric(m.get("Latitude"),errors="coerce").notna() & pd.to_numeric(m.get("Longitude"),errors="coerce").notna()].copy()
    if m.empty:
        st.caption("Joined PortWatch records do not yet have canonical/reference coordinates.")
        return
    m["Latitude"]=pd.to_numeric(m["Latitude"],errors="coerce"); m["Longitude"]=pd.to_numeric(m["Longitude"],errors="coerce")
    m["Port calls"]=pd.to_numeric(m.get("portcalls"),errors="coerce").fillna(0)
    m["Container calls"]=pd.to_numeric(m.get("portcalls_container"),errors="coerce").fillna(0)
    m["Tanker calls"]=pd.to_numeric(m.get("portcalls_tanker"),errors="coerce").fillna(0)
    m["Imports"]=pd.to_numeric(m.get("import"),errors="coerce").fillna(0)
    m["Exports"]=pd.to_numeric(m.get("export"),errors="coerce").fillna(0)
    m["Map Port"]=m.get("Port / Facility",m.get("portname","")).fillna("").astype(str)
    m["Map Country"]=m.get("Country",m.get("country","")).fillna("").astype(str)
    maxcalls=max(float(m["Port calls"].max()),1.0)
    m["radius"]=m["Port calls"].map(lambda x: 12000 + 52000*((max(float(x),0.0)/maxcalls)**0.5))
    if pdk is None:
        st.map(m,latitude="Latitude",longitude="Longitude",use_container_width=True)
        return
    layer=pdk.Layer("ScatterplotLayer",data=m,get_position="[Longitude, Latitude]",get_radius="radius",radius_min_pixels=3,radius_max_pixels=18,pickable=True,auto_highlight=True,get_fill_color=[216,180,90,175],get_line_color=[240,224,180,230],line_width_min_pixels=1)
    view=pdk.ViewState(latitude=float(m["Latitude"].mean()),longitude=float(m["Longitude"].mean()),zoom=1.05,pitch=0,bearing=0)
    tooltip={"html":"<b>{Map Port}</b><br/>{Map Country}<br/>Port calls: {Port calls}<br/>Container: {Container calls}<br/>Tankers: {Tanker calls}<br/>Imports: {Imports}<br/>Exports: {Exports}","style":{"backgroundColor":"#101820","color":"#F4EFE5","fontSize":"12px"}}
    st.pydeck_chart(pdk.Deck(layers=[layer],initial_view_state=view,tooltip=tooltip,map_style=None),use_container_width=True,height=height)

def render_overview_portwatch():
    st.markdown("### Global port activity · IMF PortWatch")
    live,error,latest_date=load_portwatch_latest()
    if not error and live is not None and not live.empty:
        st.session_state["portwatch_last_good"]=(live.copy(),latest_date)
    elif "portwatch_last_good" in st.session_state:
        live,latest_date=st.session_state["portwatch_last_good"]
    if live is None or live.empty:
        st.caption(f"PortWatch currently unavailable. {error}" if error else "No PortWatch observations returned.")
        return
    base=unified_ports_with_reference(TABLES.get(("Maritime","Ports"),pd.DataFrame()).copy())
    joined=join_portwatch_to_pc_ports(live,base)
    c1,c2,c3,c4=st.columns(4)
    c1.metric("PortWatch ports",f"{len(live):,}")
    c2.metric("Joined to P&C map",f"{len(joined):,}")
    c3.metric("Port calls",f"{pd.to_numeric(joined.get('portcalls'),errors='coerce').fillna(0).sum():,.0f}" if not joined.empty else "—")
    c4.metric("Observation",latest_date or "—")
    render_portwatch_operational_map(joined)
    if not joined.empty:
        cols=[c for c in ["Port / Facility","Country","portname","portid","portcalls","portcalls_container","portcalls_tanker","import","export","PortWatch Match Confidence","PortWatch Match Method"] if c in joined.columns]
        with st.expander("PortWatch ↔ P&C joined records",expanded=False):
            display_df(joined[cols].sort_values("portcalls",ascending=False) if "portcalls" in cols else joined[cols],500)
    st.caption("PortWatch supplies operational activity; P&C canonical/global reference records remain the geographic authority for port identity and coordinates.")

def render_named_port_map(df, height=480, radius=22000):
    if df is None or df.empty: return
    m=df.copy()
    latcol="Latitude" if "Latitude" in m.columns else "lat"
    loncol="Longitude" if "Longitude" in m.columns else "lon"
    namecol="Port Name" if "Port Name" in m.columns else ("Port / Facility" if "Port / Facility" in m.columns else "name")
    countrycol="Country Name" if "Country Name" in m.columns else ("Country" if "Country" in m.columns else None)
    m[latcol]=pd.to_numeric(m[latcol],errors="coerce"); m[loncol]=pd.to_numeric(m[loncol],errors="coerce")
    m=m[m[latcol].notna() & m[loncol].notna()].copy()
    if m.empty: return
    m["Map Port"]=m[namecol].fillna("").astype(str)
    m["Map Country"]=m[countrycol].fillna("").astype(str) if countrycol else ""
    if pdk is not None:
        layer=pdk.Layer("ScatterplotLayer",data=m,get_position=f"[{loncol}, {latcol}]",get_radius=radius,
                        radius_min_pixels=3,radius_max_pixels=11,pickable=True,auto_highlight=True,
                        get_fill_color=[216,180,90,175],get_line_color=[240,224,180,230],line_width_min_pixels=1)
        view=pdk.ViewState(latitude=float(m[latcol].mean()),longitude=float(m[loncol].mean()),zoom=1.2,pitch=0,bearing=0)
        tooltip={"html":"<b>{Map Port}</b><br/>{Map Country}","style":{"backgroundColor":"#101820","color":"#F4EFE5","fontSize":"12px"}}
        st.pydeck_chart(pdk.Deck(layers=[layer],initial_view_state=view,tooltip=tooltip,map_style=None),use_container_width=True,height=height)
    else:
        st.map(m.rename(columns={latcol:"lat",loncol:"lon"}),latitude="lat",longitude="lon",use_container_width=True)

def route_port_points(*texts):
    """Resolve ordered route/call text to known port coordinates without inventing locations."""
    ref=global_port_reference_view()
    if ref.empty:
        return pd.DataFrame()
    lookup={}
    for _,r in ref.iterrows():
        key=_port_match_key(r.get("Port Name",""))
        if key and key not in lookup:
            lookup[key]=r
    points=[]; seen=set()
    for text in texts:
        for raw in re.split(r";|\||→|>|,|\n",str(text or "")):
            name=raw.strip(" -–—")
            if not name: continue
            key=_port_match_key(name)
            hit=lookup.get(key)
            if hit is None:
                # conservative fallback to the curated city/port coordinate dictionary
                xy=PORT_CITY_COORDS.get(name) or PORT_CITY_COORDS.get("Port of "+name)
                if xy and key not in seen:
                    points.append({"Port / Facility":name,"Country":"","Latitude":xy[0],"Longitude":xy[1],"Sequence":len(points)+1})
                    seen.add(key)
                continue
            if key in seen: continue
            points.append({"Port / Facility":hit.get("Port Name",name),"Country":hit.get("Country Name",""),
                           "Latitude":hit.get("Latitude"),"Longitude":hit.get("Longitude"),"Sequence":len(points)+1})
            seen.add(key)
    return pd.DataFrame(points)

def render_route_port_map(points,title="Route geography",height=430):
    if points is None or points.empty:
        st.caption("No route-call coordinates have been resolved yet.")
        return
    m=points.copy()
    m["Latitude"]=pd.to_numeric(m["Latitude"],errors="coerce"); m["Longitude"]=pd.to_numeric(m["Longitude"],errors="coerce")
    m=m[m["Latitude"].notna() & m["Longitude"].notna()].copy()
    if m.empty: return
    st.markdown(f"#### {title}")
    if pdk is not None:
        scatter=pdk.Layer("ScatterplotLayer",data=m,get_position="[Longitude, Latitude]",get_radius=26000,
                          radius_min_pixels=4,radius_max_pixels=10,pickable=True,auto_highlight=True,
                          get_fill_color=[216,180,90,185],get_line_color=[240,224,180,235],line_width_min_pixels=1)
        layers=[scatter]
        if len(m)>1:
            path=[[float(r["Longitude"]),float(r["Latitude"])] for _,r in m.sort_values("Sequence").iterrows()]
            layers.insert(0,pdk.Layer("PathLayer",data=[{"path":path}],get_path="path",get_width=3,width_min_pixels=2,
                                      get_color=[145,168,190,190],pickable=False))
        view=pdk.ViewState(latitude=float(m["Latitude"].mean()),longitude=float(m["Longitude"].mean()),zoom=2.2,pitch=0,bearing=0)
        tooltip={"html":"<b>{Port / Facility}</b><br/>{Country}","style":{"backgroundColor":"#101820","color":"#F4EFE5","fontSize":"12px"}}
        st.pydeck_chart(pdk.Deck(layers=layers,initial_view_state=view,tooltip=tooltip,map_style=None),use_container_width=True,height=height)
    else:
        st.map(m.rename(columns={"Latitude":"lat","Longitude":"lon"}),latitude="lat",longitude="lon",use_container_width=True)
    st.caption("Route lines connect representative calls in listed order; they are not navigational tracks.")

def cruise_tables_with_fallbacks():
    """Restore Cruise even when the old workbook lacks the four dedicated cruise sheets."""
    lines=TABLES.get(("Maritime","Cruise Lines"),pd.DataFrame()).copy()
    ships=TABLES.get(("Maritime","Cruise Ships"),pd.DataFrame()).copy()
    destinations=TABLES.get(("Maritime","Cruise Destinations"),pd.DataFrame()).copy()
    routes=TABLES.get(("Maritime","Cruise Routes"),pd.DataFrame()).copy()
    gl=TABLES.get(("Maritime","Great Lakes Cruise"),pd.DataFrame()).copy()
    research=TABLES.get(("Maritime","Fleet Research Universe"),pd.DataFrame()).copy()
    companies=TABLES.get(("Core Entities","Companies"),pd.DataFrame()).copy()
    vessels=TABLES.get(("Maritime","Vessels"),pd.DataFrame()).copy()
    if lines.empty and not research.empty and "Segment" in research.columns:
        rc=research[research["Segment"].fillna("").astype(str).str.contains("Cruise",case=False,na=False)].copy()
        rows=[]
        for _,r in rc.iterrows():
            rows.append({
                "Company ID":r.get("Company ID",""),
                "Cruise Line / Brand":r.get("Company / Brand",""),
                "Parent Group":r.get("Parent / Strategic Link",""),
                "Market Segment":"Cruise",
                "Fleet Profile":r.get("Fleet Scope to Capture",""),
                "Primary Operating Regions":"",
                "Private / Controlled Destinations":"",
                "Route Pattern":"",
                "Status":r.get("Canonical Status","") or r.get("Research Status",""),
                "Notes":r.get("Why Included","") or r.get("Notes","")
            })
        if rows:
            lines=pd.DataFrame(rows).drop_duplicates(subset=["Cruise Line / Brand"],keep="first")
    if not companies.empty:
        blob=companies.astype(str).agg(" ".join,axis=1)
        mask=blob.str.contains("cruise",case=False,na=False)
        c=companies[mask].copy()
        rows=[]
        for _,r in c.iterrows():
            rows.append({"Company ID":r.get("Company ID",""),"Cruise Line / Brand":r.get("Company",""),
                         "Parent Group":"","Market Segment":r.get("Business Segments",""),"Fleet Profile":"",
                         "Primary Operating Regions":r.get("HQ Country",""),"Private / Controlled Destinations":"",
                         "Route Pattern":"","Status":r.get("Status","") or "Canonical company record",
                         "Notes":"Restored from canonical Companies because dedicated Cruise Lines sheet was absent."})
        if rows:
            cdf=pd.DataFrame(rows)
            lines=pd.concat([lines,cdf],ignore_index=True,sort=False) if not lines.empty else cdf
            lines=lines.drop_duplicates(subset=["Cruise Line / Brand"],keep="first")
    if ships.empty:
        rows=[]
        if not gl.empty:
            for _,r in gl.iterrows():
                rows.append({"Company ID":r.get("Company ID",""),"Vessel Name":r.get("Vessel Name",""),
                             "Ship Type / Class":r.get("Vessel / Service Type",""),"Flag":"","Year Built":"",
                             "Passenger Capacity":"","Primary Deployment":r.get("Operating Area",""),
                             "Home Port / Turnaround":r.get("Representative Ports / Infrastructure",""),
                             "Route / Product Role":r.get("Season",""),"Status":r.get("Status","")})
        if not vessels.empty:
            vm=vessels[vessels.astype(str).agg(" ".join,axis=1).str.contains("cruise",case=False,na=False)]
            for _,r in vm.iterrows():
                rows.append({"Company ID":"","Vessel Name":r.get("Vessel Name",""),"Ship Type / Class":r.get("Vessel Type",""),
                             "Flag":r.get("Flag",""),"Year Built":r.get("Year Built",""),"Passenger Capacity":"",
                             "Primary Deployment":"","Home Port / Turnaround":"","Route / Product Role":"","Status":r.get("Status","")})
        ships=pd.DataFrame(rows).drop_duplicates(subset=["Vessel Name"],keep="first") if rows else pd.DataFrame()
    if destinations.empty and not gl.empty:
        rows=[]
        for _,r in gl.iterrows():
            for dest in re.split(r";|,",str(r.get("Representative Ports / Infrastructure","") or "")):
                dest=dest.strip()
                if dest:
                    rows.append({"Destination":dest,"Country":"","Destination Type":"Port / infrastructure call",
                                 "Status":r.get("Status",""),"Region":r.get("Operating Area",""),
                                 "Typical Line / Brand Use":label(r.get("Company ID","")),"Investment / Operating Note":"",
                                 "Evidence Caveat":"Derived from Great Lakes Cruise deployment layer."})
        destinations=pd.DataFrame(rows).drop_duplicates(subset=["Destination","Region"],keep="first") if rows else pd.DataFrame()
    if routes.empty and not gl.empty:
        rows=[]
        for _,r in gl.iterrows():
            rows.append({"Route Family":r.get("Operating Area",""),"Turnaround Ports":r.get("Representative Ports / Infrastructure",""),
                         "Representative Calls":r.get("Representative Ports / Infrastructure",""),"Region":r.get("Operating Area",""),
                         "Typical Duration":"","Season":r.get("Season",""),"Strategic Role":r.get("Vessel / Service Type",""),
                         "Status":r.get("Status","")})
        routes=pd.DataFrame(rows).drop_duplicates(subset=["Route Family","Representative Calls"],keep="first")
    return lines,ships,destinations,routes,gl

# Fail clearly when a deployment is incomplete. Previous builds silently loaded an
# empty interface when the workbooks were placed in the repository root or carried
# browser-added suffixes such as "(1)".
MISSING_WORKBOOKS = [filename for filename in WORKBOOKS.values() if not (DATA_DIR / filename).exists()]
if MISSING_WORKBOOKS:
    st.error("This deployment is missing required data workbooks: " + ", ".join(MISSING_WORKBOOKS))
    st.info("Place the required Excel workbooks in the data/ directory using the filenames shown above.")
    st.stop()

# ---------- presentation cleanup ----------
# Keep internal join keys in the data model, but never expose them in the normal UI.
# Real-world identifiers (IMO, MMSI, call sign, registration number) remain visible.
INTERNAL_ID_EXCEPTIONS={"IMO","IMO Number","MMSI","Call Sign","Registration Number","Official Number","VIN","HIN","Activity Number"}

ID_RE=re.compile(
    r"(?:^|[ _/\\-])(id|ids|identifier|identifiers|internal key|record key)(?:$|[ _/\\-])"
    r"|(?:^|[ _/\\-])(entity|company|programme|program|yard|vessel|facility|source|relationship|contract|route|news|event|port|terminal|asset|link|observation|approval|control|status|chain)[ _/\\-]*id(?:$|[ _/\\-])",
    re.I,
)

ID_FRIENDLY_NAMES={
    "Company ID":"Company","Company Entity ID":"Company","Entity ID":"Entity",
    "Source Entity":"Source","Target Entity":"Target","Source Entity ID":"Source","Target Entity ID":"Target",
    "Programme ID":"Programme","Program ID":"Programme","Yard ID":"Shipyard","Build Yard ID":"Shipyard",
    "Vessel ID":"Vessel","Port ID":"Port","Terminal ID":"Terminal","Parent Entity ID":"Parent Entity",
    "Asset/Facility Entity ID":"Asset / Facility","Asset / Facility Entity ID":"Asset / Facility",
    "Prime / Lead Entity ID":"Prime / Lead","Contractor Entity ID":"Contractor",
    "Seller / Builder Entity ID":"Seller / Builder","Primary Entity ID":"Primary Entity",
    "Owner / Operator Company ID":"Owner / Operator","Primary Operator Company ID":"Primary Operator",
    "Operator Company ID":"Operator","Owner Company ID":"Owner",
}

COLUMN_ENGLISH={
    "ISO3":"Country Code","portname":"Port","country":"Country","portcalls":"Port Calls",
    "portcalls_container":"Container Calls","portcalls_dry_bulk":"Dry Bulk Calls",
    "portcalls_general_cargo":"General Cargo Calls","portcalls_roro":"Ro-Ro Calls",
    "portcalls_tanker":"Tanker Calls","import":"Imports","export":"Exports",
    "seendate":"Seen Date","pubDate":"Published","pubdate":"Published",
    "source_name":"Source","source_url":"Source","source_id":"Source",
    "image_url":"Image","article_id":"Article","disruption_id":"Disruption",
}

def _is_internal_id_col(c):
    c=str(c).strip()
    if c in INTERNAL_ID_EXCEPTIONS:
        return False
    if c in ID_FRIENDLY_NAMES:
        return True
    # catches Company_ID / companyId / Record ID / entity identifier without hiding IMO/MMSI
    normalized=re.sub(r"([a-z0-9])([A-Z])",r"\1 \2",c).replace("_"," ").replace("-"," ")
    normalized=re.sub(r"\s+"," ",normalized).strip()
    if normalized in INTERNAL_ID_EXCEPTIONS:
        return False
    return bool(ID_RE.search(normalized) or re.search(r"\bID$",normalized,re.I))

def english_header(c):
    c=str(c).strip()
    if c in COLUMN_ENGLISH:
        return COLUMN_ENGLISH[c]
    if c in ID_FRIENDLY_NAMES:
        return ID_FRIENDLY_NAMES[c]
    # snake_case / camelCase / technical headings -> normal English
    x=re.sub(r"([a-z0-9])([A-Z])",r"\1 \2",c)
    x=x.replace("_"," ").strip()
    x=re.sub(r"\s+"," ",x)
    replacements={
        "Url":"Source","Urls":"Evidence & sources","URL":"Source","URLs":"Evidence & sources",
        "Ro Ro":"Ro-Ro","Roro":"Ro-Ro","Iso3":"Country Code",
        "Jv":"JV","Imo":"IMO","Mmsi":"MMSI","Teu":"TEU","LNG":"LNG",
    }
    if x in replacements:
        return replacements[x]
    # Preserve standard acronyms but title-case technical lowercase headers.
    words=[]
    keep={"IMO","MMSI","AIS","API","US","USA","UK","UAE","EU","JV","MRO","LNG","TEU","SAR","RFI","RFP","HS","UN","OFAC"}
    for w in x.split():
        wu=w.upper()
        if wu in keep:
            words.append(wu)
        elif w.isupper() and len(w)<=4:
            words.append(w)
        else:
            words.append(w.capitalize())
    return " ".join(words)

def _friendly_col_name(c):
    c=str(c)
    if c in ID_FRIENDLY_NAMES:
        return ID_FRIENDLY_NAMES[c]
    if _is_internal_id_col(c):
        x=re.sub(r"\b(ids?|identifier|identifiers)\b","",english_header(c),flags=re.I).strip(" /_-")
        return x or "Entity"
    return english_header(c)

def humanize_df(df, keep_urls=True, show_internal_ids=False):
    """Convert data-model fields into ordinary English before presentation."""
    if df is None or df.empty:
        return pd.DataFrame()
    out=pd.DataFrame(index=df.index)
    for c in df.columns:
        cstr=str(c)
        if not keep_urls and "url" in cstr.lower():
            continue
        vals=df[c].copy()

        is_id_col=_is_internal_id_col(cstr)
        if is_id_col:
            friendly=_friendly_col_name(cstr)
            if show_internal_ids:
                out[english_header(cstr)]=vals
                continue
            # IDs are used only as lookup keys: show the resolved English entity name.
            resolved=vals.astype(str).map(label)
            unresolved=resolved.eq(vals.astype(str))
            # Never leak unresolved internal keys into the interface.
            resolved=resolved.mask(unresolved,"")
            if resolved.astype(str).str.strip().eq("").all():
                continue
            if friendly in out.columns:
                existing=out[friendly].astype(str).str.strip()
                out.loc[existing.eq(""),friendly]=resolved[existing.eq("")]
            else:
                out[friendly]=resolved
            continue

        friendly=english_header(cstr)
        def trans(v):
            s=str(v).strip()
            if not s or s.lower()=="nan":
                return ""
            if s in LABELS:
                return label(s)
            norm_col=cstr.lower().replace("_"," ")
            if norm_col in {"relationship","link type","relationship type"}:
                return pretty_relationship(s)
            return pc_display_value(s,cstr)
        converted=vals.map(trans)
        if friendly in out.columns:
            existing=out[friendly].astype(str).str.strip()
            out.loc[existing.eq(""),friendly]=converted[existing.eq("")]
        else:
            out[friendly]=converted

    out=out.loc[:,~out.columns.duplicated()].copy()
    # Remove columns that became entirely blank after internal-ID suppression.
    blank=[c for c in out.columns if out[c].astype(str).str.strip().eq("").all()]
    if blank:
        out=out.drop(columns=blank)
    return out

def hide_ids(df, keep_url=True):
    return humanize_df(df,keep_urls=keep_url,show_internal_ids=False)

def display_df(df, max_rows=150, show_ids=False):
    if df is None or df.empty:
        st.info("No matching records.")
        return
    show=humanize_df(df,show_internal_ids=show_ids).head(max_rows)
    show=pc_standardize_event_dataframe(show)
    cfg={}
    for c in show.columns:
        if "url" in str(c).lower():
            cfg[c]=st.column_config.LinkColumn(str(c).replace("URLs","Evidence & sources").replace("URL","Source"),display_text="Open")
    st.dataframe(show,use_container_width=True,hide_index=True,column_config=cfg)

def header(title,sub):
    st.markdown("<div class='pc-kicker'>Power & Corridors Intelligence</div>",unsafe_allow_html=True)
    st.markdown(f"<div class='pc-title'>{title}</div>",unsafe_allow_html=True)
    st.markdown(f"<div class='pc-sub'>{sub}</div>",unsafe_allow_html=True)

# ---------- ID label index ----------
@st.cache_data(show_spinner=False)
def build_label_index():
    idx={}
    candidates=[
        (("Core Entities","Entity Registry"),"Entity ID","Canonical Name"),
        (("Core Entities","Companies"),"Company ID","Company"),
        (("Systems & Waterways","System Entities"),"Entity ID","Entity"),
        (("Defence & Shipbuilding","Defence Companies"),"Entity ID","Entity"),
        (("Defence & Shipbuilding","Shipyards"),"Yard ID","Shipyard"),
        (("Defence & Shipbuilding","Programmes"),"Programme ID","Programme"),
        (("Defence & Shipbuilding","Sample Vessels"),"Vessel ID","Vessel"),
        (("Maritime","Ports"),"Port ID","Port / Facility"),
        (("Maritime","Port Terminals"),"Terminal ID","Terminal / Facility"),
        (("Maritime","Vessels"),"Vessel ID","Vessel Name"),
        (("Infrastructure","Assets"),"Asset ID","Asset"),
        (("Systems & Waterways","Systems"),"System ID","System"),
        (("Events & Hazards","Events"),"Event ID","Title"),
        (("Events & Hazards","Event Asset Links"),"Asset ID","Asset"),
        (("Events & Hazards","Event Company Links"),"Company ID","Company"),
        (("Events & Hazards","Event System Links"),"System ID","System"),
    ]
    for key,idc,namec in candidates:
        df=TABLES.get(key,pd.DataFrame())
        if idc in df.columns and namec in df.columns:
            for _,r in df.iterrows():
                if str(r[idc]).strip(): idx[str(r[idc]).strip()] = str(r[namec]).strip() or str(r[idc])
    return idx
LABELS=build_label_index()

@st.cache_data(show_spinner=False, ttl=60)
def _live_canonical_labels():
    idx={}
    try:
        sb=pc_db_client(service=True)
        if sb is None:
            return idx
        specs=[
            ("pc_entities","entity_id,name","entity_id","name"),
            ("pc_assets","asset_id,name","asset_id","name"),
            ("pc_mobile_assets","mobile_asset_id,name","mobile_asset_id","name"),
            ("pc_events","event_id,title","event_id","title"),
        ]
        for table,cols,idcol,namecol in specs:
            try:
                rows=pc_safe_rows(sb,table,cols,30000)
            except Exception:
                rows=[]
            for r in rows or []:
                oid=str(r.get(idcol) or "").strip()
                nm=str(r.get(namecol) or "").strip()
                if oid and nm:
                    idx[oid]=nm
    except Exception:
        pass
    return idx

def label(x):
    s=str(x or "").strip()
    if not s:
        return ""
    static=str(LABELS.get(s) or "").strip()
    if static and static != s:
        return static
    live=_live_canonical_labels()
    return str(live.get(s) or static or s).strip()


@st.cache_data(show_spinner=False, ttl=60)
def _live_entity_registry():
    out={}
    try:
        sb=pc_db_client(service=True)
        if sb is None: return out
        rows=pc_safe_rows(sb,"pc_entities","entity_id,name,entity_type,subtype,hq_country,status,record_status",50000,order="name")
        for r in rows or []:
            eid=str(r.get("entity_id") or "").strip()
            if eid:
                out[eid]={
                    "name":str(r.get("name") or "").strip(),
                    "entity_type":str(r.get("entity_type") or "").strip(),
                    "subtype":str(r.get("subtype") or "").strip(),
                    "hq_country":str(r.get("hq_country") or "").strip(),
                }
    except Exception:
        pass
    return out

def _canonical_entity_info(entity_id):
    return _live_entity_registry().get(str(entity_id or "").strip(),{})

def _entity_kind(entity_id, fallback_type=""):
    info=_canonical_entity_info(entity_id)
    raw=(info.get("entity_type") or fallback_type or "").strip().casefold()
    subtype=(info.get("subtype") or "").strip().casefold()
    joined=f"{raw} {subtype}"
    if any(k in joined for k in ("person","individual","executive","leader","director","officer")): return "person"
    if any(k in joined for k in ("company","corporation","business","operator","carrier","subsidiary","joint venture","jv")): return "company"
    if any(k in joined for k in ("government","authority","agency","ministry","regulator")): return "organisation"
    return raw or str(fallback_type or "").strip().casefold() or "entity"



def humanize_internal_object_id(value):
    """Last-resort UI fallback: never expose implementation IDs to end users."""
    s=str(value or "").strip()
    if not s:
        return ""

    # Strip known internal prefixes.  More-specific prefixes must come first.
    prefixes=(
        "VES_ADM_","VES_ATL_","VES_NMDC_","VES_","VESSEL_",
        "MOB_","MOBILE_","ASSET_","ENTITY_AI_","ENTITY_","ENT_","PERSON_AI_","PERSON_","COMP_","PORT_","TERM_","EVT_","EVENT_"
    )
    core=s
    matched=False
    for p in prefixes:
        if core.upper().startswith(p):
            core=core[len(p):]
            matched=True
            break

    if not matched:
        return s

    core=core.replace("_"," ").replace("-"," ")
    core=re.sub(r"\s+"," ",core).strip()
    if re.fullmatch(r"(?:AI\s+)?[A-F0-9]{12,}",core,re.I):
        return "Unresolved entity"

    # Preserve common acronyms while making identifiers human-readable.
    keep={"AD","UAE","UK","US","USA","MSC","CMA","CGM","NMDC","IMO","LNG","LPG","COSCO"}
    words=[]
    for w in core.split():
        wu=w.upper()
        words.append(wu if wu in keep else wu)
    return " ".join(words)


def relationship_endpoint_label(endpoint_id, endpoint_type=""):
    """Resolve relationship endpoints from the already-loaded canonical frames.

    Relationship rendering must use the same canonical object names as the Vessels,
    Assets and Companies pages.  This avoids migration-era Source/Target text leaking
    internal IDs such as VES_ADM_AL_ALIAH into the UI.
    """
    eid=str(endpoint_id or "").strip()
    et=str(endpoint_type or "").strip().casefold()

    if not eid:
        return ""

    info=_canonical_entity_info(eid)
    if info.get("name"):
        return str(info["name"]).strip()

    # 1) Canonical vessel/mobile-asset frame already loaded from Supabase.
    try:
        cv=_CANON_VESSELS
        if isinstance(cv,pd.DataFrame) and not cv.empty and "Vessel ID" in cv.columns:
            hit=cv[cv["Vessel ID"].fillna("").astype(str).eq(eid)]
            if not hit.empty:
                nm=str(hit.iloc[0].get("Vessel Name") or "").strip()
                if nm:
                    return nm
    except Exception:
        pass

    # 2) Current merged maritime vessel table.
    try:
        mv=TABLES.get(("Maritime","Vessels"),pd.DataFrame())
        if isinstance(mv,pd.DataFrame) and not mv.empty and "Vessel ID" in mv.columns:
            hit=mv[mv["Vessel ID"].fillna("").astype(str).eq(eid)]
            if not hit.empty:
                for nc in ("Vessel Name","Vessel","Name"):
                    if nc in hit.columns:
                        nm=str(hit.iloc[0].get(nc) or "").strip()
                        if nm and nm != eid:
                            return nm
    except Exception:
        pass

    # 3) Canonical company/entity catalogue.
    try:
        if et in {"entity","company","organisation","organization"} or eid.startswith(("ENTITY_","ENT_","COMP","PERSON_")):
            nm=label(eid)
            if nm and nm != eid:
                return nm
    except Exception:
        pass

    # 4) Fixed assets / ports / terminals.
    try:
        for key,id_col,name_cols in [
            (("Infrastructure","Assets"),"Asset ID",("Asset","Name")),
            (("Maritime","Ports"),"Port ID",("Port / Facility","Port","Name")),
            (("Maritime","Port Terminals"),"Terminal ID",("Terminal / Facility","Terminal","Name")),
        ]:
            df=TABLES.get(key,pd.DataFrame())
            if isinstance(df,pd.DataFrame) and not df.empty and id_col in df.columns:
                hit=df[df[id_col].fillna("").astype(str).eq(eid)]
                if not hit.empty:
                    for nc in name_cols:
                        if nc in hit.columns:
                            nm=str(hit.iloc[0].get(nc) or "").strip()
                            if nm and nm != eid:
                                return nm
    except Exception:
        pass

    # 5) Global live/static resolver as final named fallback.
    nm=label(eid)
    if nm and nm != eid and not str(nm).startswith(("VES_","VESSEL_","MOB_","MOBILE_","ASSET_","ENTITY_","ENT_","PERSON_","COMP_","PORT_","TERM_","EVT_")):
        return nm

    # Absolute UI safety net: internal IDs must never be visible.
    return humanize_internal_object_id(eid)


def pretty_enum(v):
    """Shared P&C display taxonomy renderer."""
    s=str(v or "").strip()
    if s in LABELS:
        return label(s)
    return pc_pretty_enum(v)

def pretty_relationship(v):
    s=pretty_enum(v)
    replacements={
        "Directly affected":"Directly affected",
        "Connected network":"Connected network",
        "Indirect hinterland impact":"Indirect hinterland impact",
        "Affected network":"Affected network",
        "Project milestone":"Project milestone",
        "Connected project":"Connected project",
        "Temporary alternative":"Temporary alternative",
        "Negotiation target":"Negotiation target",
        "Connected gateway":"Connected gateway",
        "Investment target":"Investment target",
        "Infrastructure event":"Infrastructure event",
        "Commercial event":"Commercial event",
        "Commissioning event":"Commissioning event",
        "Regional security context":"Regional security context",
    }
    return replacements.get(s,s)

# ---------- global search ----------
SEARCH_PRIORITY={
    "Companies":8,"Entity Registry":7,"Defence Companies":9,"Shipyards":10,"Programmes":10,"Contracts":9,
    "Sales & Delivery Routes":9,"Announcements":9,"News Registry":8,"System Entities":8,"Systems":8,"Facilities":7,
    "Yard Facilities":8,"Yard Capabilities":8,"Sample Vessels":12,"Platform Classes":10,"Vessel Status History":11,"System Links":7,"Relationships":7,
    "Events":14,"Strategic Events":14,"Event Asset Links":12,"Event Company Links":11,"Event System Links":12,"Impact Chains":13,
    "Trade Agreements":14,"Agreement Asset Links":12,"Agreement Company Links":12,"Tariff Coverage":13,"HS Product Tests":12,
    "Rules of Origin":11,"Customs & Procurement":11,"Trade Remedies & Restrictions":12,"Sanctions Designations":14,"Sanctions Entity Links":13,
    "Infra Deals":10,"Transactions V125":11,"Vessel Transactions":9,"Port Terminals":10,"Port Ownership":9,
}

@st.cache_data(show_spinner=False)
def search_index():
    rows=[]
    skip={"Data Dictionary","Runtime Table Crosswalk","Research Queue","Overview","Evidence & sources","Source Feeds"}
    for (wb_label,sheet),df in TABLES.items():
        if sheet in skip: continue
        for i,r in df.iterrows():
            vals=[str(v).strip() for v in r.tolist() if str(v).strip()]
            if not vals: continue
            txt=" | ".join(vals)
            # best readable title
            preferred=["Company","Entity","Canonical Name","Shipyard","Programme","Vessel","Headline","System","Port / Facility","Asset","Facility","Customer","Contract Type"]
            title=""
            for c in preferred:
                if c in r.index and str(r.get(c,"")).strip(): title=str(r[c]).strip(); break
            if not title:
                title=label(vals[0]) if vals[0] in LABELS else vals[0]
            rows.append({"wb":wb_label,"sheet":sheet,"row":int(i),"title":title,"text":txt})
    return pd.DataFrame(rows)
SINDEX=search_index()

def ranked_search(q, limit=80):
    if not q or SINDEX.empty: return pd.DataFrame()
    phrase=q.strip().lower(); tokens=[t for t in re.findall(r"[\w&+.-]+",phrase) if len(t)>1]
    scored=[]
    for _,r in SINDEX.iterrows():
        text=r.text.lower(); title=r.title.lower();
        matched=sum(1 for t in tokens if t in text)
        if matched==0: continue
        score=matched*10 + (30 if phrase in text else 0) + (20 if phrase in title else 0) + SEARCH_PRIORITY.get(r.sheet,3)
        if tokens and all(t in text for t in tokens): score+=20
        scored.append((score,r.wb,r.sheet,r.row,r.title))
    scored.sort(reverse=True,key=lambda x:x[0])
    return pd.DataFrame(scored[:limit],columns=["score","wb","sheet","row","title"])

def result_row(hit):
    return TABLES[(hit.wb,hit.sheet)].iloc[int(hit.row)]

def show_result_detail(hit):
    row=result_row(hit)
    st.markdown(f"### {hit.title}")
    st.caption(f"{hit.wb} · {hit.sheet}")
    pairs=[]
    for c,v in row.items():
        if ID_RE.search(str(c)) or not str(v).strip(): continue
        if "url" in str(c).lower(): continue
        pairs.append((str(c),str(v)))
    for c,v in pairs[:12]: st.markdown(f"**{c}:** {v}")
    urls=[str(v) for c,v in row.items() if "url" in str(c).lower() and str(v).startswith("http")]
    for u in urls[:3]: st.markdown(f"[Open source ↗]({u})")

# ---------- entity resolver ----------

# ---------- entity / relationship resolver ----------
@st.cache_data(show_spinner=False)
def entity_catalog():
    rows=[]
    specs=[
        (("Core Entities","Companies"),"Company ID","Company","Company"),
        (("Systems & Waterways","System Entities"),"Entity ID","Entity","System Entity"),
        (("Defence & Shipbuilding","Defence Companies"),"Entity ID","Entity","Defence / Shipbuilding"),
        (("Defence & Shipbuilding","Shipyards"),"Yard ID","Shipyard","Shipyard"),
        (("Defence & Shipbuilding","Programmes"),"Programme ID","Programme","Programme"),
        (("Defence & Shipbuilding","Sample Vessels"),"Vessel ID","Vessel","Vessel"),
    ]
    seen=set()
    for key,idc,namec,kind in specs:
        df=TABLES.get(key,pd.DataFrame())
        if idc not in df.columns or namec not in df.columns: continue
        for _,r in df.iterrows():
            eid=str(r.get(idc,"")).strip(); nm=str(r.get(namec,"")).strip()
            if eid and nm and eid not in seen:
                rows.append({"id":eid,"name":nm,"kind":kind}); seen.add(eid)
    return pd.DataFrame(rows)

ECAT=entity_catalog()

def _match_any(df, cols, values):
    if df is None or df.empty: return pd.DataFrame()
    values={str(v).strip() for v in values if str(v).strip()}
    if not values: return df.iloc[0:0].copy()
    mask=pd.Series(False,index=df.index)
    for c in cols:
        if c in df.columns:
            mask = mask | df[c].astype(str).isin(values)
    return df[mask].copy()

def _contains_any(df, values, cols=None):
    if df is None or df.empty: return pd.DataFrame()
    vals=[str(v).strip() for v in values if str(v).strip()]
    if not vals: return df.iloc[0:0].copy()
    use=df if cols is None else df[[c for c in cols if c in df.columns]]
    if use.empty: return df.iloc[0:0].copy()
    mask=pd.Series(False,index=df.index)
    for v in vals:
        mask = mask | use.astype(str).apply(lambda s:s.str.contains(re.escape(v),case=False,na=False)).any(axis=1)
    return df[mask].copy()

def related_tables(entity_id, entity_name):
    hits=[]
    needles=[entity_id,entity_name]
    for key,df in TABLES.items():
        if df.empty: continue
        sub=_contains_any(df,needles)
        if not sub.empty: hits.append((key,sub))
    return hits

def company_scope_ids(entity_id, max_depth=3):
    """Return the selected company plus controlled / owned subsidiaries and JVs.
    This is what makes an Inocea or EDGE profile expose the yards/programmes below it.
    """
    scope={str(entity_id)}
    rel=TABLES.get(("Core Entities","Relationships"),pd.DataFrame())
    if rel.empty: return scope
    downward_terms=(
        "OWNS","PARENT","CONTROLS","CONTROLLED","SUBSIDIARY","JV_PARTNER",
        "OWNS_51","OWNS_49","PARENT_OF","CONTROLS","CONSOLIDATES"
    )
    reverse_terms=("SUBSIDIARY_OF","OWNED_BY","CONTROLLED_BY","PART_OF","MEMBER_OF")
    frontier={str(entity_id)}
    for _ in range(max_depth):
        nxt=set()
        for src in frontier:
            rows=rel[rel.get("Source Entity",pd.Series(dtype=str)).astype(str).eq(src)]
            for _,r in rows.iterrows():
                relationship=str(r.get("Relationship","")).upper().replace(" ","_").replace("-","_")
                tgt=str(r.get("Target Entity","")).strip()
                if tgt and any(term in relationship for term in downward_terms):
                    if tgt not in scope:
                        scope.add(tgt); nxt.add(tgt)

                # Some legacy/canonical rows are written as child -> SUBSIDIARY_OF -> parent.
                # Do not traverse those forward when building a parent's operating scope.
                # They are handled through the inbound pass below.

            inbound=rel[rel.get("Target Entity",pd.Series(dtype=str)).astype(str).eq(src)]
            for _,r in inbound.iterrows():
                relationship=str(r.get("Relationship","")).upper().replace(" ","_").replace("-","_")
                source_entity=str(r.get("Source Entity","")).strip()

                if source_entity and any(term in relationship for term in reverse_terms):
                    if source_entity not in scope:
                        scope.add(source_entity); nxt.add(source_entity)

                # Group operating-ecosystem links are deliberately traversable in
                # reverse so group profiles can expose operating sister businesses.
                if source_entity and "GROUP_ECOSYSTEM_LINK" in relationship:
                    if source_entity not in scope:
                        scope.add(source_entity); nxt.add(source_entity)
        if not nxt: break
        frontier=nxt
    return scope

def company_scope_names(scope_ids):
    return [label(x) for x in scope_ids if label(x)!=x]

def company_investment_exposure_ids(scope_ids):
    """Return portfolio / investment targets without classifying them as controlled subsidiaries."""
    rel=TABLES.get(("Core Entities","Relationships"),pd.DataFrame())
    if rel.empty:
        return set()
    exposure_terms=("PORTFOLIO_INVESTMENT","MINORITY_INVESTMENT","STRATEGIC_INVESTMENT","CONSORTIUM_ACQUIRED")
    targets=set()
    if "Source Entity" not in rel.columns or "Target Entity" not in rel.columns:
        return targets
    rows=rel[rel["Source Entity"].astype(str).isin(set(str(x) for x in scope_ids))]
    for _,r in rows.iterrows():
        relationship=str(r.get("Relationship","")).upper()
        if any(term in relationship for term in exposure_terms):
            tgt=str(r.get("Target Entity","")).strip()
            if tgt:
                targets.add(tgt)
    return targets

def company_news_scope_ids(scope_ids):
    """Broaden news discovery through meaningful corporate/project relationships
    without changing ownership/control scope.
    Example: Fincantieri Infrastructure → participates in → PerGenova.
    """
    base=set(str(x) for x in scope_ids)
    rel=TABLES.get(("Core Entities","Relationships"),pd.DataFrame())
    if rel.empty or "Source Entity" not in rel.columns or "Target Entity" not in rel.columns:
        return base

    news_terms=(
        "PARTICIPATES_IN","LEADS_CONSORTIUM","JV_PARTICIPANT_IN","PARENT_OF","OWNS",
        "CONTROL","OPERATES","ADMINISTERS","COMMISSIONS","CONSTRUCTS","BUILDS",
        "PORTFOLIO_INVESTMENT","STRATEGIC_INVESTMENT"
    )
    expanded=set(base)
    for _,r in rel.iterrows():
        src=str(r.get("Source Entity","")).strip()
        tgt=str(r.get("Target Entity","")).strip()
        relationship=str(r.get("Relationship","")).upper()
        if not any(term in relationship for term in news_terms):
            continue
        if src in base and tgt:
            expanded.add(tgt)
        if tgt in base and src:
            expanded.add(src)
    return expanded

def company_record(entity_id):
    df=TABLES.get(("Core Entities","Companies"),pd.DataFrame())
    if "Company ID" in df.columns:
        x=df[df["Company ID"].astype(str)==str(entity_id)]
        if not x.empty: return x.iloc[0]
    d=TABLES.get(("Defence & Shipbuilding","Defence Companies"),pd.DataFrame())
    if "Entity ID" in d.columns:
        x=d[d["Entity ID"].astype(str)==str(entity_id)]
        if not x.empty: return x.iloc[0]
    return None

def _company_name_key(value):
    """Normalize company names for migration-era rollups."""
    s=str(value or "").casefold()
    s=re.sub(r"[^a-z0-9]+"," ",s).strip()
    parts=[p for p in s.split() if p]
    suffixes={
        "inc","incorporated","llc","ltd","limited","plc","corp","corporation",
        "company","co","holdings","holding","group","sa","ag","nv","bv"
    }
    while parts and parts[-1] in suffixes:
        parts.pop()
    return " ".join(parts)

def _company_name_matches(series, names):
    keys={_company_name_key(n) for n in names if _company_name_key(n)}
    vals=series.fillna("").astype(str).map(_company_name_key)
    mask=vals.isin(keys)
    for root in [k for k in keys if len(k)>=6]:
        mask |= vals.str.startswith(root+" ",na=False)
    return mask

@st.cache_data(show_spinner=False, ttl=30)
def _live_canonical_company_rollup(entity_id, entity_name):
    """Direct canonical company roll-up from Supabase.

    This intentionally bypasses the legacy workbook projection for company profiles.
    It uses the live pc_entities / pc_relationships / pc_assets / pc_mobile_assets tables
    so newly-applied assets and vessels become visible immediately.
    """
    empty = {
        "scope_ids": set(),
        "relationships": pd.DataFrame(),
        "assets": pd.DataFrame(),
        "ports": pd.DataFrame(),
        "terminals": pd.DataFrame(),
        "vessels": pd.DataFrame(),
        "vessel_relationships": pd.DataFrame(),
        "error": "",
    }
    try:
        sb = pc_db_client(service=True)
        if sb is None:
            empty["error"] = "No Supabase client"
            return empty

        erows = pc_safe_rows(
            sb, "pc_entities",
            "entity_id,name,entity_type,subtype,hq_city,hq_country,status,record_status,metadata",
            10000, order="name"
        )
        rrows = pc_safe_rows(
            sb, "pc_relationships",
            "relationship_id,source_type,source_id,relationship_type,target_type,target_id,"
            "ownership_percent,operating_control,confidence,record_status,evidence_source_id,notes,metadata",
            30000
        )
        arows = pc_safe_rows(
            sb, "pc_assets",
            "asset_id,name,asset_type,subtype,country,region_city,latitude,longitude,"
            "operator_entity_id,owner_entity_id,capacity_value,capacity_unit,status,record_status,"
            "data_quality,source_id,metadata",
            20000, order="name"
        )
        mrows = pc_safe_rows(
            sb, "pc_mobile_assets",
            "mobile_asset_id,name,asset_type,subtype,imo,mmsi,registration,call_sign,flag,"
            "year_built,dwt,capacity_value,capacity_unit,owner_entity_id,operator_entity_id,"
            "manager_entity_id,status,record_status,data_quality,source_id,metadata",
            20000, order="name"
        )

        entities = {str(r.get("entity_id") or "").strip(): str(r.get("name") or "").strip()
                    for r in (erows or [])}
        asset_names = {str(r.get("asset_id") or "").strip(): str(r.get("name") or "").strip()
                       for r in (arows or [])}
        mobile_names = {str(r.get("mobile_asset_id") or "").strip(): str(r.get("name") or "").strip()
                        for r in (mrows or [])}
        relationships = rrows or []

        # pc_relationships can grow well beyond the generic safe_rows window. Company
        # pages must not lose recently-loaded graph edges merely because they fall
        # outside that broad result set. Hydrate the selected company's relationship
        # neighbourhood directly from Supabase and merge it into the working graph.
        rel_columns = (
            "relationship_id,source_type,source_id,relationship_type,target_type,target_id,"
            "ownership_percent,operating_control,confidence,record_status,evidence_source_id,notes,metadata"
        )

        def _hydrate_relationship_neighbourhood(entity_ids):
            nonlocal relationships
            ids=[str(x).strip() for x in (entity_ids or []) if str(x).strip()]
            if not ids:
                return
            merged={str(r.get("relationship_id") or "").strip():r for r in relationships if str(r.get("relationship_id") or "").strip()}
            anonymous=[]
            for eid in ids:
                for field in ("source_id","target_id"):
                    try:
                        rows=(sb.table("pc_relationships")
                              .select(rel_columns)
                              .eq(field,eid)
                              .limit(5000)
                              .execute().data or [])
                    except Exception:
                        rows=[]
                    for rr in rows:
                        rid=str(rr.get("relationship_id") or "").strip()
                        if rid:
                            merged[rid]=rr
                        else:
                            anonymous.append(rr)
            relationships=list(merged.values())+anonymous

        def _endpoint_name(endpoint_type, endpoint_id):
            et=str(endpoint_type or "").strip().casefold()
            eid=str(endpoint_id or "").strip()
            if not eid:
                return ""
            if et in {"entity","company","organisation","organization"}:
                return entities.get(eid) or eid
            if et == "asset":
                return asset_names.get(eid) or eid
            if et in {"mobile_asset","vessel"}:
                return mobile_names.get(eid) or eid
            return label(eid) or eid

        # Bridge migration-era company IDs to the canonical entity graph by NAME.
        # A company profile may still be opened from a workbook COMP_* ID while the
        # normalized graph uses ENT_* IDs.  The canonical name is authoritative.
        requested_id=str(entity_id or "").strip()
        scope=set()
        if requested_id in entities:
            scope.add(requested_id)

        root=_company_name_key(entity_name)
        if root:
            exact_name_ids=[]
            branded_ids=[]
            for r in erows or []:
                eid=str(r.get("entity_id") or "").strip()
                nm=_company_name_key(r.get("name"))
                if not eid or not nm:
                    continue
                if nm == root:
                    exact_name_ids.append(eid)
                elif nm.startswith(root + " "):
                    branded_ids.append(eid)

            # Prefer exact canonical name matches, but retain branded variants for
            # group-level rollups such as AD Ports Group / DP World.
            scope.update(exact_name_ids)
            scope.update(branded_ids)

        # Last-resort fallback only when no canonical company could be resolved.
        if not scope and requested_id:
            scope.add(requested_id)

        # Preserve the initially-resolved company IDs so vessel rows can distinguish
        # direct links from links inherited through controlled subsidiaries.
        root_scope=set(scope)
        _hydrate_relationship_neighbourhood(scope)

        # Corporate/group scope includes both legal ownership and explicit operating
        # control/management relationships.  Do not require every terminal asset to
        # be denormalized directly onto the ultimate parent company: a parent -> local
        # operating/JV company -> physical terminal chain is the canonical model.
        down = {
            "owns","owns_group_company","parent_of","controls","controlled_entity",
            "subsidiary","subsidiary_of_group","consolidates","group_company",
            "owns_51_percent","owns_60_percent","owns_70_percent","owns_81_percent",
            "owns_controls","controls_operates","operates","manages",
            "operator_of","management_control","concession_operator",
        }
        reverse = {
            "subsidiary_of","owned_by","controlled_by","part_of","member_of",
            "operated_by","managed_by","concession_of",
        }

        # Traverse corporate hierarchy up to five levels. Re-hydrate after every
        # expansion so a child entity's vessel edges are available even when the
        # global relationship table is larger than the generic read window.
        for _ in range(5):
            _hydrate_relationship_neighbourhood(scope)
            added = set()
            for rr in relationships:
                st = str(rr.get("source_type") or "").casefold()
                tt = str(rr.get("target_type") or "").casefold()
                if st != "entity" or tt != "entity":
                    continue
                sid = str(rr.get("source_id") or "").strip()
                tid = str(rr.get("target_id") or "").strip()
                rel = str(rr.get("relationship_type") or "").strip().casefold().replace("-","_").replace(" ","_")

                if sid in scope:
                    if (
                        rel in down
                        or rel.startswith("owns_")
                        or rel.startswith("parent_")
                        or "group_company" in rel
                        or rel == "controls"
                    ):
                        if tid and tid not in scope:
                            added.add(tid)

                if tid in scope and rel in reverse:
                    if sid and sid not in scope:
                        added.add(sid)

            if not added:
                break
            scope.update(added)

        _hydrate_relationship_neighbourhood(scope)

        # Operational graph targets for this corporate scope.
        graph_assets = set()
        graph_vessels = set()
        rel_display = []
        vessel_rel_display = []

        for rr in relationships:
            sid = str(rr.get("source_id") or "").strip()
            tid = str(rr.get("target_id") or "").strip()
            st = str(rr.get("source_type") or "").strip().casefold()
            tt = str(rr.get("target_type") or "").strip().casefold()
            rel = str(rr.get("relationship_type") or "").strip()
            rel_norm = rel.casefold().replace("-","_").replace(" ","_")

            # Company profiles must include BOTH directions.  Canonical fleet rows
            # commonly use VESSEL -> OPERATED_BY -> COMPANY.
            if sid not in scope and tid not in scope:
                continue

            source_name=_endpoint_name(st,sid)
            target_name=_endpoint_name(tt,tid)

            # Company is source -> asset/vessel is target.
            if sid in scope:
                if tt == "asset" and rel_norm in {
                    "operates","owns","manages","controls","administers",
                    "concession_holder","invested_in","develops"
                }:
                    graph_assets.add(tid)

                elif tt in {"mobile_asset","vessel"} and rel_norm in {
                    "operates","owns","manages","charters","controls","fleet_of"
                }:
                    graph_vessels.add(tid)
                    vessel_rel_display.append({
                        "Vessel ID": tid,
                        "Vessel Name": target_name,
                        "Company ID": sid,
                        "Company": _endpoint_name(st,sid),
                        "Relationship": pretty_relationship(rel),
                        "Role": pretty_relationship(rel),
                        "Source ID": str(rr.get("evidence_source_id") or "").strip(),
                    })

            # Vessel/asset is source -> company is target.
            if tid in scope:
                if st == "asset" and rel_norm in {
                    "operated_by","owned_by","managed_by","controlled_by",
                    "administered_by","concession_of","developed_by"
                }:
                    graph_assets.add(sid)

                elif st in {"mobile_asset","vessel"} and rel_norm in {
                    "operated_by","owned_by","managed_by","chartered_by",
                    "controlled_by","fleet_of"
                }:
                    graph_vessels.add(sid)
                    vessel_rel_display.append({
                        "Vessel ID": sid,
                        "Vessel Name": source_name,
                        "Company ID": tid,
                        "Company": _endpoint_name(tt,tid),
                        "Relationship": pretty_relationship(rel),
                        "Role": pretty_relationship(rel),
                        "Source ID": str(rr.get("evidence_source_id") or "").strip(),
                    })

            rel_display.append({
                "Relationship ID": str(rr.get("relationship_id") or "").strip(),
                "Source Entity": sid,
                "Source": source_name,
                "Source Type": st,
                "Relationship": rel,
                "Target Entity": tid,
                "Target": target_name,
                "Target Type": tt,
                "Ownership %": rr.get("ownership_percent"),
                "Operating Control": rr.get("operating_control"),
                "Confidence": rr.get("confidence"),
                "Record Status": str(rr.get("record_status") or "").strip(),
                "Source ID": str(rr.get("evidence_source_id") or "").strip(),
                "Notes": str(rr.get("notes") or "").strip(),
                "Metadata": rr.get("metadata") or {},
            })

        # Direct owner/operator links in pc_assets are equally authoritative.
        live_assets = []
        ports = []
        terminals = []
        for a in arows or []:
            aid = str(a.get("asset_id") or "").strip()
            owner = str(a.get("owner_entity_id") or "").strip()
            operator = str(a.get("operator_entity_id") or "").strip()
            if aid not in graph_assets and owner not in scope and operator not in scope:
                continue

            meta = a.get("metadata") if isinstance(a.get("metadata"), dict) else {}
            research = meta.get("research_attributes") if isinstance(meta.get("research_attributes"), dict) else {}
            name = str(a.get("name") or "").strip()
            atype = str(a.get("asset_type") or "").strip()
            subtype = str(a.get("subtype") or "").strip()
            company_id = operator or owner
            company_name = entities.get(company_id, company_id)

            base = {
                "Asset ID": aid,
                "Asset": name,
                "Asset Type": atype,
                "Subtype": subtype,
                "Company ID": company_id,
                "Owner / Operator Company ID": company_id,
                "Company": company_name,
                "Country": str(a.get("country") or research.get("country") or "").strip(),
                "City / Area": str(a.get("region_city") or research.get("city_region") or research.get("city") or "").strip(),
                "Latitude": a.get("latitude"),
                "Longitude": a.get("longitude"),
                "Status": str(a.get("status") or a.get("record_status") or "").strip(),
                "Record Status": str(a.get("record_status") or "").strip(),
                "Relationship / Role": "",
                "Capacity": a.get("capacity_value") or research.get("capacity") or "",
                "Metadata": meta,
            }
            live_assets.append(base)

            nk = f"{name} {atype} {subtype}".casefold()
            explicit_port = any(x in nk for x in (" port","port ","harbour","harbor"))
            is_terminal = any(x in nk for x in ("terminal","depot","warehouse","logistics","yard","crossdock"))

            if explicit_port:
                ports.append({
                    "Port ID": aid,
                    "Port / Facility": name,
                    "Country": base["Country"],
                    "City / Area": base["City / Area"],
                    "Facility Type": atype or subtype,
                    "Operator Company ID": operator,
                    "Operator": entities.get(operator, operator),
                    "Owner Company ID": owner,
                    "Status": base["Status"],
                    "Latitude": base["Latitude"],
                    "Longitude": base["Longitude"],
                    "Key Role": str(research.get("operating_role") or research.get("strategic_role") or "").strip(),
                    "Metadata": meta,
                })

            if is_terminal:
                terminals.append({
                    "Terminal ID": aid,
                    "Terminal / Facility": name,
                    "Port ID": str(research.get("parent_port_id") or "").strip(),
                    "Parent Port": str(research.get("parent_port") or "").strip(),
                    "Country": base["Country"],
                    "City / Area": base["City / Area"],
                    "Primary Operator Company ID": operator or owner,
                    "Operator / Network": entities.get(operator or owner, operator or owner),
                    "Status": base["Status"],
                    "Ownership / Structure": "",
                    "Facility Type": atype or subtype,
                    "Latitude": base["Latitude"],
                    "Longitude": base["Longitude"],
                    "Metadata": meta,
                })

        # Direct owner/operator/manager links plus canonical graph vessel edges.
        # Build a readable role map so the company profile shows WHY each hull is
        # included and whether the link is direct or inherited through a subsidiary.
        vessel_role_map=defaultdict(list)
        for vr in vessel_rel_display:
            vid=str(vr.get("Vessel ID") or "").strip()
            cid=str(vr.get("Company ID") or "").strip()
            if not vid:
                continue
            vessel_role_map[vid].append({
                "company_id":cid,
                "company":str(vr.get("Company") or entities.get(cid,cid) or "").strip(),
                "relationship":str(vr.get("Relationship") or vr.get("Role") or "").strip(),
                "path":"Direct" if cid in root_scope else "Via subsidiary",
            })

        live_vessels = []
        for m in mrows or []:
            vid = str(m.get("mobile_asset_id") or "").strip()
            owner = str(m.get("owner_entity_id") or "").strip()
            operator = str(m.get("operator_entity_id") or "").strip()
            manager = str(m.get("manager_entity_id") or "").strip()
            if vid not in graph_vessels and owner not in scope and operator not in scope and manager not in scope:
                continue

            meta = m.get("metadata") if isinstance(m.get("metadata"), dict) else {}
            research = meta.get("research_attributes") if isinstance(meta.get("research_attributes"), dict) else {}
            cap = m.get("capacity_value")
            if cap in (None, ""):
                cap = research.get("capacity")
            roles=vessel_role_map.get(vid,[])
            role_companies=[]
            role_names=[]
            role_paths=[]
            for vr in roles:
                if vr.get("company") and vr["company"] not in role_companies:
                    role_companies.append(vr["company"])
                if vr.get("relationship") and vr["relationship"] not in role_names:
                    role_names.append(vr["relationship"])
                if vr.get("path") and vr["path"] not in role_paths:
                    role_paths.append(vr["path"])

            live_vessels.append({
                "Vessel ID": vid,
                "Vessel Name": str(m.get("name") or "").strip(),
                "IMO": str(m.get("imo") or "").strip(),
                "MMSI": str(m.get("mmsi") or "").strip(),
                "Call Sign": str(m.get("call_sign") or "").strip(),
                "Flag": str(m.get("flag") or "").strip(),
                "Vessel Type": str(m.get("asset_type") or "").strip(),
                "Subtype / Class": str(m.get("subtype") or "").strip(),
                "Year Built": m.get("year_built"),
                "DWT": m.get("dwt"),
                "Capacity": cap,
                "Capacity Unit": str(m.get("capacity_unit") or "").strip(),
                "Owner Company ID": owner,
                "Operator Company ID": operator,
                "Manager Company ID": manager,
                "Owner": entities.get(owner, owner),
                "Operator": entities.get(operator, operator),
                "Manager": entities.get(manager, manager),
                "Linked Company": " · ".join(role_companies),
                "Relationship / Role": " · ".join(role_names),
                "Link Path": " · ".join(role_paths),
                "Owner / Operator Text": " / ".join(
                    x for x in [entities.get(owner, owner), entities.get(operator, operator)] if x
                ),
                "Status": str(m.get("status") or m.get("record_status") or "").strip(),
                "Record Status": str(m.get("record_status") or "").strip(),
                "Data Quality": str(m.get("data_quality") or "").strip(),
                "Source ID": str(m.get("source_id") or "").strip(),
                "Notes": str(meta.get("notes") or "").strip(),
                "Metadata": meta,
            })

        return {
            "scope_ids": scope,
            "relationships": pd.DataFrame(rel_display),
            "assets": pd.DataFrame(live_assets),
            "ports": pd.DataFrame(ports),
            "terminals": pd.DataFrame(terminals),
            "vessels": pd.DataFrame(live_vessels),
            "vessel_relationships": pd.DataFrame(vessel_rel_display),
            "error": "",
        }

    except Exception as exc:
        empty["error"] = f"{type(exc).__name__}: {exc}"
        return empty


def _overlay_live_company_rollup(prof, entity_id, entity_name):
    live = _live_canonical_company_rollup(entity_id, entity_name)
    prof["live_rollup_error"] = live.get("error","")
    prof["live_scope_ids"] = live.get("scope_ids",set())

    def _merge(existing, incoming, keys):
        if incoming is None or incoming.empty:
            return existing
        if existing is None or existing.empty:
            return incoming.copy()
        combined = pd.concat([existing,incoming],ignore_index=True,sort=False)
        dk=[k for k in keys if k in combined.columns]
        return combined.drop_duplicates(subset=dk,keep="last") if dk else combined

    # Canonical normalized relationships are authoritative.
    # Do NOT merge migration-era / workbook relationship rows back into company
    # profiles once live canonical relationships are available; those legacy rows
    # can contain raw object IDs in display fields and duplicate canonical edges.
    _live_rels = live.get("relationships")
    if isinstance(_live_rels, pd.DataFrame) and not _live_rels.empty:
        prof["relationships"] = _live_rels.copy()
    else:
        prof["relationships"] = prof.get("relationships", pd.DataFrame())

    prof["assets"] = _merge(prof.get("assets"), live.get("assets"), ["Asset ID"])
    prof["ports"] = _merge(prof.get("ports"), live.get("ports"), ["Port ID"])
    prof["port_terminals"] = _merge(prof.get("port_terminals"), live.get("terminals"), ["Terminal ID"])
    prof["maritime_vessels"] = _merge(prof.get("maritime_vessels"), live.get("vessels"), ["Vessel ID"])

    # Same rule for the vessel/company relationship helper frame: canonical wins.
    _live_vessel_rels = live.get("vessel_relationships")
    if isinstance(_live_vessel_rels, pd.DataFrame) and not _live_vessel_rels.empty:
        prof["vessel_relationships"] = _live_vessel_rels.copy()
    else:
        prof["vessel_relationships"] = prof.get("vessel_relationships", pd.DataFrame())
    return prof


@st.cache_data(show_spinner=False, ttl=30)
def _live_entity_event_feed(entity_ids):
    """Read canonical event relationships directly from pc_entity_event_feed_v.

    This is the authoritative live bridge between a company/entity profile and
    pc_events via pc_event_links. It intentionally bypasses the legacy workbook
    Event Company Links projection so newly-linked events appear immediately.
    """
    ids = sorted({str(x).strip() for x in (entity_ids or []) if str(x).strip()})
    if not ids:
        return pd.DataFrame(), pd.DataFrame(), ""

    try:
        sb = pc_db_client(service=True)
        if sb is None:
            return pd.DataFrame(), pd.DataFrame(), "No Supabase client"

        # Query the view in modest chunks to avoid URL/query limits for large groups.
        rows = []
        for i in range(0, len(ids), 50):
            chunk = ids[i:i+50]
            q = (
                sb.table("pc_entity_event_feed_v")
                .select("*")
                .in_("entity_id", chunk)
                .order("start_date", desc=True)
                .limit(5000)
            )
            resp = q.execute()
            rows.extend(getattr(resp, "data", None) or [])

        if not rows:
            return pd.DataFrame(), pd.DataFrame(), ""

        raw = pd.DataFrame(rows)

        # Project live canonical column names into the names already consumed by
        # render_event_cards(), render_event_map(), and company profile metrics.
        rename = {
            "event_id": "Event ID",
            "start_date": "Start Date",
            "end_date": "End Date",
            "event_nature": "Event Nature",
            "event_domain": "Event Domain",
            "event_family": "Event Family",
            "event_type": "Event Type",
            "severity": "Severity",
            "status": "Status",
            "mode": "Mode",
            "countries": "Countries",
            "location": "Location",
            "title": "Title",
            "description": "Description",
            "operational_impact": "Operational Impact",
            "relationship": "Relationship",
            "link_confidence": "Link Confidence",
            "entity_id": "Linked Entity ID",
            "entity_name": "Linked Entity",
            "entity_type": "Linked Entity Type",
            "subtype": "Linked Entity Subtype",
        }
        events = raw.rename(columns=rename).copy()

        # One event may be linked to several entities in the selected corporate
        # group. Show the event once on the company page.
        if "Event ID" in events.columns:
            events = events.drop_duplicates(subset=["Event ID"], keep="first")

        # Pull canonical locations for those same events so the existing event map
        # also becomes live rather than remaining dependent on workbook projection.
        locations = pd.DataFrame()
        event_ids = [
            str(x).strip()
            for x in events.get("Event ID", pd.Series(dtype=str)).tolist()
            if str(x).strip()
        ]
        if event_ids:
            loc_rows = []
            for i in range(0, len(event_ids), 100):
                chunk = event_ids[i:i+100]
                resp = (
                    sb.table("pc_event_locations")
                    .select("event_id,location_name,country,latitude,longitude,accuracy,notes")
                    .in_("event_id", chunk)
                    .limit(5000)
                    .execute()
                )
                loc_rows.extend(getattr(resp, "data", None) or [])
            if loc_rows:
                locations = pd.DataFrame(loc_rows).rename(columns={
                    "event_id": "Event ID",
                    "location_name": "Location",
                    "country": "Country",
                    "latitude": "Latitude",
                    "longitude": "Longitude",
                    "accuracy": "Accuracy",
                    "notes": "Notes",
                })

        return events, locations, ""

    except Exception as exc:
        return pd.DataFrame(), pd.DataFrame(), str(exc)


def _overlay_live_company_events(prof, entity_id):
    """Merge canonical live event feed into the company profile."""
    scope = set(str(x) for x in prof.get("live_scope_ids", set()) if str(x))
    scope.update(str(x) for x in prof.get("asset_scope_ids", set()) if str(x))
    scope.add(str(entity_id))

    live_events, live_locations, error = _live_entity_event_feed(tuple(sorted(scope)))
    prof["live_event_feed_error"] = error

    if not live_events.empty:
        prof["canonical_live_events"] = live_events.copy()
        existing = prof.get("events", pd.DataFrame())
        if existing is None or existing.empty:
            prof["events"] = live_events.copy()
        else:
            combined = pd.concat([existing, live_events], ignore_index=True, sort=False)
            if "Event ID" in combined.columns:
                combined = combined.drop_duplicates(subset=["Event ID"], keep="last")
            prof["events"] = combined

        # The platform treats news/developments as events. Keep a news-shaped
        # projection so the existing News tab and metric can expose the same
        # canonical company-linked activity without a second relationship model.
        event_news = live_events.copy()
        event_news = event_news.rename(columns={
            "Start Date": "Published Date",
            "Title": "Headline",
            "Description": "Summary",
        })
        event_news["Publisher"] = "P&C canonical event"
        event_news["URL"] = ""
        event_news["Region"] = event_news.get("Location", "")
        event_news["Country"] = event_news.get("Countries", "")
        event_news["Verification Status"] = "Canonical event-linked"
        event_news["Notes"] = event_news.get("Operational Impact", "")
        prof["canonical_event_news"] = event_news
    else:
        prof["canonical_live_events"] = pd.DataFrame()
        prof["canonical_event_news"] = pd.DataFrame()

    if not live_locations.empty:
        existing_loc = prof.get("event_locations", pd.DataFrame())
        if existing_loc is None or existing_loc.empty:
            prof["event_locations"] = live_locations.copy()
        else:
            combined = pd.concat([existing_loc, live_locations], ignore_index=True, sort=False)
            keys = [c for c in ["Event ID", "Location", "Latitude", "Longitude"] if c in combined.columns]
            prof["event_locations"] = combined.drop_duplicates(subset=keys, keep="last") if keys else combined

    return prof


def build_company_profile(entity_id, entity_name):
    prof={}
    prof["company_id"]=entity_id
    prof["name"]=entity_name
    scope_ids=company_scope_ids(entity_id)

    # Expand a group profile with obvious canonical branded variants, then traverse
    # each variant's corporate graph. This is important for groups such as DP World,
    # AD Ports Group and Matson where ports/vessels may sit under regional/subsidiary IDs.
    _companies=TABLES.get(("Core Entities","Companies"),pd.DataFrame())
    _brand_ids=set()
    if not _companies.empty and "Company ID" in _companies.columns and "Company" in _companies.columns:
        _root=_company_name_key(entity_name)
        if _root:
            _brand_keys=_companies["Company"].fillna("").astype(str).map(_company_name_key)
            _brand_mask=_brand_keys.eq(_root) | _brand_keys.str.startswith(_root+" ",na=False)
            _brand_ids.update(
                x for x in _companies.loc[_brand_mask,"Company ID"].fillna("").astype(str).tolist()
                if x
            )

    # Include branded IDs and their controlled/subsidiary scope.
    for _cid in list(_brand_ids):
        scope_ids.add(_cid)
        try:
            scope_ids.update(company_scope_ids(_cid))
        except Exception:
            pass

    # IMPORTANT: compute investment/asset scope only AFTER group expansion.
    # Earlier builds calculated this before branded subsidiaries were added,
    # leaving DP World ports and vessels invisible even though they existed in data.
    investment_ids=company_investment_exposure_ids(scope_ids)
    asset_scope_ids=set(scope_ids) | set(investment_ids)

    prof["scope_ids"]=scope_ids
    prof["scope_names"]=company_scope_names(scope_ids)
    prof["investment_ids"]=investment_ids
    prof["investment_names"]=company_scope_names(investment_ids)
    prof["asset_scope_ids"]=asset_scope_ids
    prof["scope_debug"]={
        "group_scope_ids":len(scope_ids),
        "investment_scope_ids":len(investment_ids),
        "asset_scope_ids":len(asset_scope_ids),
        "branded_ids":len(_brand_ids),
    }

    # Corporate relationships
    rel=TABLES.get(("Core Entities","Relationships"),pd.DataFrame())
    if not rel.empty:
        m=pd.Series(False,index=rel.index)
        if "Source Entity" in rel.columns: m |= rel["Source Entity"].astype(str).isin(scope_ids)
        if "Target Entity" in rel.columns: m |= rel["Target Entity"].astype(str).isin(scope_ids)
        prof["relationships"]=rel[m].copy()
    else:
        prof["relationships"]=pd.DataFrame()

    # Canonical graph-derived operational targets.
    # These are authoritative when owner/operator IDs have not yet been denormalized
    # into pc_assets / pc_mobile_assets.
    graph_asset_ids=set()
    graph_vessel_ids=set()
    if not prof["relationships"].empty:
        _rr=prof["relationships"].copy()
        for _,_r in _rr.iterrows():
            _src=str(_r.get("Source Entity","")).strip()
            _tgt=str(_r.get("Target Entity","")).strip()
            _tt=str(_r.get("Target Type","")).strip().casefold()
            _rel=str(_r.get("Relationship","")).strip().casefold().replace("-","_").replace(" ","_")
            if _src not in scope_ids or not _tgt:
                continue
            if _tt=="asset" and _rel in {
                "operates","owns","manages","controls","administers",
                "concession_holder","invested_in","develops"
            }:
                graph_asset_ids.add(_tgt)
            if _tt in {"mobile_asset","vessel"} and _rel in {
                "operates","owns","manages","charters","controls"
            }:
                graph_vessel_ids.add(_tgt)

    prof["graph_asset_ids"]=graph_asset_ids
    prof["graph_vessel_ids"]=graph_vessel_ids

    # Shipyards owned / operated by this company
    yards=TABLES.get(("Defence & Shipbuilding","Shipyards"),pd.DataFrame())
    prof["yards"]=_match_any(yards,["Company Entity ID"],scope_ids)

    yard_ids=prof["yards"]["Yard ID"].astype(str).tolist() if not prof["yards"].empty and "Yard ID" in prof["yards"].columns else []
    yard_names=prof["yards"]["Shipyard"].astype(str).tolist() if not prof["yards"].empty and "Shipyard" in prof["yards"].columns else []

    # Programmes: direct lead + participant roles
    programmes=TABLES.get(("Defence & Shipbuilding","Programmes"),pd.DataFrame())
    pp=TABLES.get(("Defence & Shipbuilding","Programme Participants"),pd.DataFrame())
    direct=_match_any(programmes,["Prime / Lead Entity ID"],scope_ids)
    participant=_match_any(pp,["Entity ID"],scope_ids)
    pids=set(direct["Programme ID"].astype(str).tolist()) if not direct.empty and "Programme ID" in direct.columns else set()
    if not participant.empty and "Programme ID" in participant.columns: pids.update(participant["Programme ID"].astype(str).tolist())
    prof["programme_participants"]=participant
    prof["programmes"]=programmes[programmes["Programme ID"].astype(str).isin(pids)].copy() if pids and "Programme ID" in programmes.columns else direct
    pids=set(prof["programmes"]["Programme ID"].astype(str).tolist()) if not prof["programmes"].empty else set()

    # Sample defence / government vessels via programme and/or build yard
    sv=TABLES.get(("Defence & Shipbuilding","Sample Vessels"),pd.DataFrame())
    sm=pd.Series(False,index=sv.index) if not sv.empty else pd.Series(dtype=bool)
    if not sv.empty:
        if "Programme ID" in sv.columns and pids: sm |= sv["Programme ID"].astype(str).isin(pids)
        if "Build Yard ID" in sv.columns and yard_ids: sm |= sv["Build Yard ID"].astype(str).isin(yard_ids)
        prof["defence_vessels"]=sv[sm].copy()
    else: prof["defence_vessels"]=pd.DataFrame()

    # Commercial / broader maritime vessels in legacy maritime workbook.
    v=TABLES.get(("Maritime","Vessels"),pd.DataFrame())
    vr=TABLES.get(("Maritime","Vessel Relationships"),pd.DataFrame())
    vm=pd.Series(False,index=v.index) if not v.empty else pd.Series(dtype=bool)
    if not v.empty:
        for c in ["Owner Company ID","Operator Company ID"]:
            if c in v.columns: vm |= v[c].astype(str).isin(scope_ids)
    related_vessel_ids=set()
    if not vr.empty:
        _vrmask=pd.Series(False,index=vr.index)

        # Primary match: canonical company IDs in the current corporate scope.
        if "Company ID" in vr.columns:
            _vrmask |= vr["Company ID"].fillna("").astype(str).isin(scope_ids)

        # Name fallback is intentional. During staged/canonical migration a company
        # can exist under a second canonical ID while the graph edge has the correct
        # readable company name. Do not let that hide its vessels from the profile.
        _scope_company_names=set([entity_name] + company_scope_names(scope_ids))
        if "Company" in vr.columns:
            _vrmask |= _company_name_matches(vr["Company"],_scope_company_names)

        vrs=vr[_vrmask].copy()
        prof["vessel_relationships"]=vrs
        if "Vessel ID" in vrs.columns:
            related_vessel_ids.update(
                x for x in vrs["Vessel ID"].fillna("").astype(str).tolist() if x
            )
    else:
        prof["vessel_relationships"]=pd.DataFrame()

    # Direct vessel owner/operator IDs plus graph-linked vessel IDs.
    if not v.empty and "Vessel ID" in v.columns:
        if related_vessel_ids:
            vm |= v["Vessel ID"].fillna("").astype(str).isin(related_vessel_ids)
        if graph_vessel_ids:
            vm |= v["Vessel ID"].fillna("").astype(str).isin(graph_vessel_ids)

    # Final readable-name fallback for canonical graph rows whose vessel ID differs
    # from a duplicate/legacy registry row but whose vessel name is authoritative.
    if not v.empty and not prof["vessel_relationships"].empty and "Vessel Name" in v.columns:
        _linked_names=set(
            prof["vessel_relationships"].get("Vessel Name",pd.Series(dtype=str))
            .fillna("").astype(str).str.strip().str.casefold()
        )
        _linked_names.discard("")
        if _linked_names:
            vm |= v["Vessel Name"].fillna("").astype(str).str.strip().str.casefold().isin(_linked_names)

    prof["maritime_vessels"]=v[vm].copy() if not v.empty else pd.DataFrame()

    # De-duplicate the profile vessel list on the strongest available identity.
    if not prof["maritime_vessels"].empty:
        _mv=prof["maritime_vessels"].copy()
        _dedupe_cols=[c for c in ["Vessel ID","IMO"] if c in _mv.columns]
        if _dedupe_cols:
            prof["maritime_vessels"]=_mv.drop_duplicates(subset=_dedupe_cols,keep="last")
        elif "Vessel Name" in _mv.columns:
            prof["maritime_vessels"]=_mv.drop_duplicates(subset=["Vessel Name"],keep="last")

    # Vessel build records matching owned yards / sample defence vessels.
    builds=TABLES.get(("Maritime","Vessel Build Records"),pd.DataFrame())
    if not builds.empty:
        bm=pd.Series(False,index=builds.index)
        if "Shipyard" in builds.columns and yard_names:
            for yn in yard_names:
                bm |= builds["Shipyard"].astype(str).str.contains(re.escape(yn),case=False,na=False)
        prof["vessel_build_records"]=builds[bm].copy()
    else: prof["vessel_build_records"]=pd.DataFrame()

    # Contracts / sales routes
    contracts=TABLES.get(("Defence & Shipbuilding","Contracts"),pd.DataFrame())
    cm=pd.Series(False,index=contracts.index) if not contracts.empty else pd.Series(dtype=bool)
    if not contracts.empty:
        if "Contractor Entity ID" in contracts.columns: cm |= contracts["Contractor Entity ID"].astype(str).isin(scope_ids)
        if "Programme ID" in contracts.columns and pids: cm |= contracts["Programme ID"].astype(str).isin(pids)
    prof["contracts"]=contracts[cm].copy() if not contracts.empty else pd.DataFrame()

    routes=TABLES.get(("Defence & Shipbuilding","Sales & Delivery Routes"),pd.DataFrame())
    rm=pd.Series(False,index=routes.index) if not routes.empty else pd.Series(dtype=bool)
    if not routes.empty:
        if "Seller / Builder Entity ID" in routes.columns: rm |= routes["Seller / Builder Entity ID"].astype(str).isin(scope_ids)
        if "Programme ID" in routes.columns and pids: rm |= routes["Programme ID"].astype(str).isin(pids)
    prof["sales_routes"]=routes[rm].copy() if not routes.empty else pd.DataFrame()

    # Yard facilities and capabilities
    fac=TABLES.get(("Defence & Shipbuilding","Yard Facilities"),pd.DataFrame())
    prof["yard_facilities"]=_match_any(fac,["Yard ID"],yard_ids)
    caps=TABLES.get(("Defence & Shipbuilding","Yard Capabilities"),pd.DataFrame())
    prof["yard_capabilities"]=_match_any(caps,["Yard ID"],yard_ids)

    # Infrastructure assets / facilities linked to this company.
    # The database/legacy layers do not all use the same ownership/operator column,
    # so match every supported company-link field rather than only "Company ID".
    assets=TABLES.get(("Infrastructure","Assets"),pd.DataFrame())
    _asset_company_cols=[
        "Company ID",
        "Owner / Operator Company ID",
        "Operator Company ID",
        "Owner Company ID",
        "Primary Operator Company ID",
        "Entity ID",
    ]
    prof["assets"]=_match_any(assets,_asset_company_cols,asset_scope_ids)
    if not assets.empty and graph_asset_ids and "Asset ID" in assets.columns:
        _graph_assets=assets[assets["Asset ID"].fillna("").astype(str).isin(graph_asset_ids)].copy()
        if not _graph_assets.empty:
            _am=pd.concat([prof["assets"],_graph_assets],ignore_index=True,sort=False)
            _ad=[c for c in ["Asset ID","Asset"] if c in _am.columns]
            prof["assets"]=_am.drop_duplicates(subset=_ad,keep="last") if _ad else _am

    # Name fallback for legacy/backfill rows where only a readable owner/operator survived.
    if not assets.empty:
        _asset_name_mask=pd.Series(False,index=assets.index)
        _scope_names=set([entity_name] + company_scope_names(asset_scope_ids))
        for _c in ["Company","Owner / Operator","Operator","Owner","Operator / Network","Relationship / Role"]:
            if _c not in assets.columns:
                continue
            _asset_name_mask |= _company_name_matches(assets[_c],_scope_names)
        _asset_named=assets[_asset_name_mask].copy()
        if not _asset_named.empty:
            _am=pd.concat([prof["assets"],_asset_named],ignore_index=True,sort=False)
            _ad=[c for c in ["Asset ID","Asset"] if c in _am.columns]
            prof["assets"]=_am.drop_duplicates(subset=_ad,keep="last") if _ad else _am

    infra_fac=TABLES.get(("Infrastructure","Facilities"),pd.DataFrame())
    prof["infrastructure_facilities"]=_match_any(
        infra_fac,
        ["Owner / Operator Company ID","Company ID","Operator Company ID","Owner Company ID"],
        asset_scope_ids
    )

    # Announcements related directly or through programmes
    anns=TABLES.get(("Defence & Shipbuilding","Announcements"),pd.DataFrame())
    am=pd.Series(False,index=anns.index) if not anns.empty else pd.Series(dtype=bool)
    if not anns.empty:
        if "Primary Entity ID" in anns.columns: am |= anns["Primary Entity ID"].astype(str).isin(scope_ids)
        if "Programme ID" in anns.columns and pids: am |= anns["Programme ID"].astype(str).isin(pids)
        if "Linked Entities / Topics" in anns.columns:
            am |= anns["Linked Entities / Topics"].astype(str).str.contains(re.escape(entity_name),case=False,na=False)
    prof["announcements"]=anns[am].copy() if not anns.empty else pd.DataFrame()

    # News via explicit links, meaningful related entities, and fallback text match.
    news=TABLES.get(("Intelligence","News Registry"),pd.DataFrame())
    nel=TABLES.get(("Intelligence","News Entity Links"),pd.DataFrame())
    news_scope_ids=company_news_scope_ids(asset_scope_ids)
    prof["news_scope_ids"]=news_scope_ids

    nids=set()
    if not nel.empty and "Entity ID" in nel.columns:
        linkrows=nel[nel["Entity ID"].astype(str).isin(news_scope_ids)]
        if "News ID" in linkrows.columns:
            nids.update(linkrows["News ID"].astype(str).tolist())

    nm=pd.Series(False,index=news.index) if not news.empty else pd.Series(dtype=bool)
    if not news.empty:
        if nids and "News ID" in news.columns:
            nm |= news["News ID"].astype(str).isin(nids)
        # exact company/group names remain a useful fallback for unlinked legacy rows.
        for search_name in set([entity_name] + company_scope_names(news_scope_ids)):
            if not search_name:
                continue
            for c in ["Headline","Summary","Notes"]:
                if c in news.columns:
                    nm |= news[c].astype(str).str.contains(re.escape(search_name),case=False,na=False)
    prof["news"]=news[nm].copy() if not news.empty else pd.DataFrame()

    # Strategic event history can function as news/activity when a company is linked
    # through a vessel or another canonical event entity. This is important for GFS Galaxy.
    strategic=TABLES.get(("Intelligence","Strategic Events"),pd.DataFrame())
    event_links=TABLES.get(("Intelligence","Event Entity Links"),pd.DataFrame())
    observations=TABLES.get(("Intelligence","Event Observations"),pd.DataFrame())

    strategic_ids=set()
    observation_ids=set()

    # Company/group/event scope.
    event_asset_ids=set(news_scope_ids)
    for key,col in [
        ("maritime_vessels","Vessel ID"),
        ("defence_vessels","Vessel ID"),
        ("yards","Yard ID"),
        ("port_terminals","Terminal ID"),
        ("ports","Port ID"),
        ("assets","Asset ID")
    ]:
        df=prof.get(key,pd.DataFrame())
        if isinstance(df,pd.DataFrame) and not df.empty and col in df.columns:
            event_asset_ids.update(df[col].astype(str).tolist())

    if not event_links.empty and "Entity ID" in event_links.columns:
        el=event_links[event_links["Entity ID"].astype(str).isin(event_asset_ids)].copy()
        if "Canonical Event ID" in el.columns:
            strategic_ids.update(x for x in el["Canonical Event ID"].astype(str).tolist() if x and x!="nan")
        if "Observation ID" in el.columns:
            observation_ids.update(x for x in el["Observation ID"].astype(str).tolist() if x and x!="nan")

    # Strategic Events can also directly name a company or asset.
    if not strategic.empty and "Subject Entity ID" in strategic.columns:
        sd=strategic[strategic["Subject Entity ID"].astype(str).isin(event_asset_ids)]
        if "Event ID" in sd.columns:
            strategic_ids.update(sd["Event ID"].astype(str).tolist())

    se_rows=strategic[strategic["Event ID"].astype(str).isin(strategic_ids)].copy() if (strategic_ids and not strategic.empty and "Event ID" in strategic.columns) else pd.DataFrame()

    # Convert strategic events into a news-like dataframe for the normal News tab.
    strategic_news=[]
    for _,r in se_rows.iterrows():
        eid=str(r.get("Event ID","")).strip()
        url=""
        # Prefer a URL-bearing observation for the canonical event.
        if not observations.empty:
            om=pd.Series(False,index=observations.index)
            if "Canonical Event ID" in observations.columns:
                om |= observations["Canonical Event ID"].astype(str).eq(eid)
            if observation_ids and "Observation ID" in observations.columns:
                om |= observations["Observation ID"].astype(str).isin(observation_ids)
            ors=observations[om]
            if not ors.empty and "Source Reference" in ors.columns:
                for v in ors["Source Reference"].astype(str).tolist():
                    if v.startswith("http"):
                        url=v
                        break
        strategic_news.append({
            "Published Date":str(r.get("Date","")).strip(),
            "Headline":str(r.get("Title","")).strip(),
            "Publisher":"Strategic event record",
            "URL":url,
            "Summary":str(r.get("Description","")).strip(),
            "Region":str(r.get("Location","")).strip(),
            "Country":"",
            "Sector":"",
            "Event Type":str(r.get("Event Type","")).strip(),
            "Event Subtype":"",
            "Verification Status":"Canonical event-linked",
            "Notes":str(r.get("Financial / Strategic Impact","")).strip(),
            "Strategic Event ID":eid,
        })
    prof["strategic_news"]=pd.DataFrame(strategic_news)

    # Port / terminal assets from Maritime workbook
    pt=TABLES.get(("Maritime","Port Terminals"),pd.DataFrame())
    po=TABLES.get(("Maritime","Port Ownership"),pd.DataFrame())
    pb=TABLES.get(("Maritime","Port Berths"),pd.DataFrame())
    pe=TABLES.get(("Maritime","Port Equipment"),pd.DataFrame())
    pnews=TABLES.get(("Maritime","Port News"),pd.DataFrame())
    ports=TABLES.get(("Maritime","Ports"),pd.DataFrame())

    # direct terminal ownership/operator rows.
    # Support both canonical projections and older AD Ports / legacy workbook link columns.
    tm=pd.Series(False,index=pt.index) if not pt.empty else pd.Series(dtype=bool)
    _scope_names=set([entity_name] + company_scope_names(asset_scope_ids))
    if not pt.empty:
        for _c in [
            "Primary Operator Company ID","Operator Company ID","Owner Company ID",
            "Company ID","Owner / Operator Company ID"
        ]:
            if _c in pt.columns:
                tm |= pt[_c].astype(str).isin(asset_scope_ids)
        for _c in ["Operator / Network","Operator","Owner","Ownership / Structure","Company"]:
            if _c in pt.columns:
                tm |= _company_name_matches(pt[_c],_scope_names)
    if not pt.empty and graph_asset_ids and "Terminal ID" in pt.columns:
        tm |= pt["Terminal ID"].fillna("").astype(str).isin(graph_asset_ids)
    direct_terms=pt[tm].copy() if not pt.empty else pd.DataFrame()

    # direct port owner/operator/authority rows.
    direct_ports=pd.DataFrame()
    if not ports.empty:
        pm=pd.Series(False,index=ports.index)
        for _c in [
            "Operator Company ID","Owner Company ID","Company ID",
            "Owner / Operator Company ID","Primary Operator Company ID"
        ]:
            if _c in ports.columns:
                pm |= ports[_c].astype(str).isin(asset_scope_ids)
        for _c in ["Operator","Owner","Operator / Network","Company","Ownership / Structure"]:
            if _c in ports.columns:
                pm |= _company_name_matches(ports[_c],_scope_names)
        if graph_asset_ids and "Port ID" in ports.columns:
            pm |= ports["Port ID"].fillna("").astype(str).isin(graph_asset_ids)
        direct_ports=ports[pm].copy()

    # ownership / JV rows can surface terminals even where primary operator differs
    owned_term_ids=set()
    if not po.empty and "Company ID" in po.columns:
        porows=po[po["Company ID"].astype(str).isin(asset_scope_ids)].copy()
        prof["port_ownership"]=porows
        if "Terminal ID" in porows.columns:
            owned_term_ids.update(porows["Terminal ID"].astype(str).tolist())
    else:
        prof["port_ownership"]=pd.DataFrame()

    term_ids=set()
    if not direct_terms.empty and "Terminal ID" in direct_terms.columns:
        term_ids.update(direct_terms["Terminal ID"].astype(str).tolist())
    term_ids.update(owned_term_ids)

    if not pt.empty and term_ids and "Terminal ID" in pt.columns:
        extra_terms=pt[pt["Terminal ID"].astype(str).isin(term_ids)]
        _term_merge=pd.concat([direct_terms,extra_terms],ignore_index=True)
        _term_dedupe=[c for c in ["Terminal ID","Terminal / Facility","Port ID"] if c in _term_merge.columns]
        prof["port_terminals"]=(
            _term_merge.drop_duplicates(subset=_term_dedupe,keep="last")
            if _term_dedupe else _term_merge
        )
    else:
        prof["port_terminals"]=direct_terms

    # parent ports + ports directly administered/operated by the company/network
    port_ids=set()
    if not prof["port_terminals"].empty and "Port ID" in prof["port_terminals"].columns:
        port_ids.update(prof["port_terminals"]["Port ID"].astype(str).tolist())

    terminal_parent_ports=ports[ports["Port ID"].astype(str).isin(port_ids)].copy() if (not ports.empty and port_ids and "Port ID" in ports.columns) else pd.DataFrame()
    port_frames=[x for x in [direct_ports,terminal_parent_ports] if isinstance(x,pd.DataFrame) and not x.empty]
    if port_frames:
        _port_merge=pd.concat(port_frames,ignore_index=True)
        _port_dedupe=[c for c in ["Port ID","Port / Facility"] if c in _port_merge.columns]
        prof["ports"]=(
            _port_merge.drop_duplicates(subset=_port_dedupe,keep="last")
            if _port_dedupe else _port_merge
        )
    else:
        prof["ports"]=pd.DataFrame()

    # terminal-level child assets
    prof["port_berths"]=_match_any(pb,["Terminal ID"],term_ids)
    prof["port_equipment"]=_match_any(pe,["Terminal ID"],term_ids)

    # port/terminal news
    pnids=set(term_ids)
    pnm=pd.Series(False,index=pnews.index) if not pnews.empty else pd.Series(dtype=bool)
    if not pnews.empty:
        if "Terminal ID" in pnews.columns and pnids:
            pnm |= pnews["Terminal ID"].astype(str).isin(pnids)
        for nm in company_scope_names(asset_scope_ids):
            for c in ["Headline","Summary","Operator","Port","Terminal"]:
                if c in pnews.columns:
                    pnm |= pnews[c].astype(str).str.contains(re.escape(nm),case=False,na=False)
    prof["port_news"]=pnews[pnm].copy() if not pnews.empty else pd.DataFrame()

    # Systems
    se=TABLES.get(("Systems & Waterways","System Entities"),pd.DataFrame())
    system_ids=set()
    if not se.empty:
        sem=pd.Series(False,index=se.index)
        if "Entity ID" in se.columns: sem |= se["Entity ID"].astype(str).isin(asset_scope_ids)
        if "Entity" in se.columns: sem |= se["Entity"].astype(str).str.contains(re.escape(entity_name),case=False,na=False)
        serows=se[sem]
        if "System ID" in serows.columns: system_ids.update(serows["System ID"].astype(str).tolist())
    systems=TABLES.get(("Systems & Waterways","Systems"),pd.DataFrame())
    prof["systems"]=systems[systems["System ID"].astype(str).isin(system_ids)].copy() if system_ids and "System ID" in systems.columns else pd.DataFrame()

    # Unified events / hazards / project announcements
    event_assets=entity_asset_ids_from_profile(prof)
    ev,eloc,ech=event_bundle_for_entities(asset_scope_ids,event_assets,system_ids)
    prof["events"]=ev
    prof["event_locations"]=eloc
    prof["impact_chains"]=ech

    # Trade policy / sanctions exposure
    acl=TABLES.get(("Trade Policy & Compliance","Agreement Company Links"),pd.DataFrame())
    aal=TABLES.get(("Trade Policy & Compliance","Agreement Asset Links"),pd.DataFrame())
    agr=TABLES.get(("Trade Policy & Compliance","Trade Agreements"),pd.DataFrame())
    san=TABLES.get(("Trade Policy & Compliance","Sanctions Entity Links"),pd.DataFrame())
    des=TABLES.get(("Trade Policy & Compliance","Sanctions Designations"),pd.DataFrame())

    policy_ids=set()
    if not acl.empty and "Company ID" in acl.columns:
        pcl=acl[acl["Company ID"].astype(str).isin(asset_scope_ids)].copy()
        prof["agreement_company_links"]=pcl
        if "Agreement ID" in pcl.columns: policy_ids.update(pcl["Agreement ID"].astype(str))
    else:
        prof["agreement_company_links"]=pd.DataFrame()
    if not aal.empty and "Asset / Entity ID" in aal.columns:
        pal=aal[aal["Asset / Entity ID"].astype(str).isin(event_assets | asset_scope_ids)].copy()
        prof["agreement_asset_links"]=pal
        if "Agreement ID" in pal.columns: policy_ids.update(pal["Agreement ID"].astype(str))
    else:
        prof["agreement_asset_links"]=pd.DataFrame()
    prof["trade_agreements"]=agr[agr["Agreement ID"].astype(str).isin(policy_ids)].copy() if (policy_ids and not agr.empty and "Agreement ID" in agr.columns) else pd.DataFrame()

    sanc_ids=set()
    if not san.empty and "Canonical Entity ID" in san.columns:
        sl=san[san["Canonical Entity ID"].astype(str).isin(event_assets | asset_scope_ids)].copy()
        prof["sanctions_links"]=sl
        if "Designation ID" in sl.columns: sanc_ids.update(sl["Designation ID"].astype(str))
    else:
        prof["sanctions_links"]=pd.DataFrame()
    prof["sanctions_designations"]=des[des["Designation ID"].astype(str).isin(sanc_ids)].copy() if (sanc_ids and not des.empty and "Designation ID" in des.columns) else pd.DataFrame()

    # Final authoritative live overlays: canonical DB wins over workbook/migration projections.
    prof=_overlay_live_company_rollup(prof,entity_id,entity_name)
    prof=_overlay_live_company_events(prof,entity_id)
    return prof

def profile_count(prof,key):
    df=prof.get(key,pd.DataFrame())
    return len(df) if isinstance(df,pd.DataFrame) else 0

def readable_relationships(df, entity_id):
    if df is None or df.empty:
        st.info("No relationship records.")
        return

    for i,(_,r) in enumerate(df.iterrows()):
        src=str(r.get("Source Entity","")).strip()
        tgt=str(r.get("Target Entity","")).strip()
        rel=pretty_relationship(r.get("Relationship",""))
        src_type=str(r.get("Source Type","")).strip()
        tgt_type=str(r.get("Target Type","")).strip()

        # Canonical object registries are authoritative for endpoint display names.
        # Do not trust migration-era Source/Target display text.
        src_name=relationship_endpoint_label(src,src_type)
        tgt_name=relationship_endpoint_label(tgt,tgt_type)

        if str(src_name).startswith(("VES_","VESSEL_","MOB_","MOBILE_","ASSET_","ENTITY_","ENT_","PERSON_","COMP_","PORT_","TERM_","EVT_")):
            src_name=humanize_internal_object_id(src_name)
        if str(tgt_name).startswith(("VES_","VESSEL_","MOB_","MOBILE_","ASSET_","ENTITY_","ENT_","PERSON_","COMP_","PORT_","TERM_","EVT_")):
            tgt_name=humanize_internal_object_id(tgt_name)

        sk=_entity_kind(src,src_type) if str(src_type).casefold() in {"entity","company","person","individual","organisation","organization"} else pretty_enum(src_type)
        tk=_entity_kind(tgt,tgt_type) if str(tgt_type).casefold() in {"entity","company","person","individual","organisation","organization"} else pretty_enum(tgt_type)
        type_line=" · ".join(x for x in [pretty_enum(sk),pretty_enum(tk)] if x)
        st.markdown(
            f"<div class='pc-rel'><div class='pc-small'>{html_lib.escape(type_line)}</div>"
            f"<b>{html_lib.escape(str(src_name))}</b> → {html_lib.escape(str(rel))} → <b>{html_lib.escape(str(tgt_name))}</b></div>",
            unsafe_allow_html=True
        )

        render_relationship_actions(
            src,tgt,f"company_{entity_id}_{i}",
            current_entity_id=entity_id,
            source_name=src_name,
            target_name=tgt_name,
            source_type=src_type,
            target_type=tgt_type,
        )

def show_named_list(df, title_col, subtitle_cols=None, source_col="Source URL", max_items=100):
    """Readable cards with normal HTML links, never repeated Streamlit buttons."""
    if df is None or df.empty:
        st.info("No records.")
        return
    subtitle_cols=subtitle_cols or []
    for _,r in df.head(max_items).iterrows():
        title=str(r.get(title_col,"")).strip() or "Record"
        bits=[]
        for c in subtitle_cols:
            v=str(r.get(c,"")).strip()
            if v:
                bits.append(str(label(v)) if v in LABELS else v)
        sub=" · ".join(bits)
        u=str(r.get(source_col,"")).strip()
        source_html=""
        if u.startswith("http"):
            source_html=f"<div class='pc-source'><a href='{u}' target='_blank' rel='noopener noreferrer'>Open source ↗</a></div>"
        st.markdown(
            f"<div class='pc-card'><div class='pc-big'>{title}</div>"
            f"<div class='pc-small'>{sub}</div>{source_html}</div>",
            unsafe_allow_html=True
        )

def _numeric(s):
    return pd.to_numeric(s.astype(str).str.replace(",","",regex=False),errors="coerce")

PORT_CITY_COORDS={
    "Port of Rotterdam":(51.95,4.14),"Rotterdam":(51.95,4.14),
    "Port of Shanghai":(31.2304,121.4737),"Shanghai":(31.2304,121.4737),
    "Port of Genoa":(44.4056,8.9463),"Genoa":(44.4056,8.9463),
    "Port of Constanța":(44.1598,28.6348),"Constanța":(44.1598,28.6348),
    "Port of Odesa":(46.49,30.74),"Odesa":(46.49,30.74),
    "Zayed Port":(24.515,54.375),"Khalifa Port":(24.799,54.651),
    "Port of Poti":(42.15,41.67),"Poti":(42.15,41.67),
    "Port of Batumi":(41.65,41.64),"Batumi":(41.65,41.64),
    "Port of Itaqui":(-2.57,-44.37),"Itaqui":(-2.57,-44.37),
    "Port of Vancouver":(49.29,-123.11),"Vancouver":(49.29,-123.11),
    "Port of Prince Rupert":(54.31,-130.32),"Prince Rupert":(54.31,-130.32),
    "Port of Singapore":(1.264,103.84),"Singapore":(1.264,103.84),
    "Port of Gothenburg":(57.70,11.95),"Gothenburg":(57.70,11.95),
    "Port of Klaipėda":(55.70,21.13),"Klaipėda":(55.70,21.13),
    "Port of Gdańsk":(54.35,18.66),"Gdańsk":(54.35,18.66),
    "Port of South Louisiana":(30.05,-90.55),"Port of New Orleans":(29.95,-90.07),
    "Port of Thunder Bay":(48.38,-89.25),"Port of Duluth-Superior":(46.78,-92.10),
    "Port of Montreal":(45.50,-73.55),"Montréal / Contrecœur":(45.50,-73.55),
    "Port of Kuryk":(43.20,51.65),"Badagry Deep Sea Port":(6.415,2.886),
    "SimFer Morebaya Port":(9.45,-13.55)
}

YARD_CITY_COORDS={
    ("Abu Dhabi","UAE"):(24.4539,54.3773),
    ("Halifax, Nova Scotia","Canada"):(44.6488,-63.5752),
    ("North Vancouver, BC","Canada"):(49.3200,-123.0724),
    ("Victoria, BC","Canada"):(48.4284,-123.3656),
    ("Lévis, Québec","Canada"):(46.8033,-71.1779),
    ("Helsinki","Finland"):(60.1699,24.9384),
    ("Galveston, Texas","USA"):(29.3013,-94.7977),
    ("Port Arthur, Texas","USA"):(29.8849,-93.9399),
    ("Houma, Louisiana","USA"):(29.5958,-90.7195),
    ("Gulfport, Mississippi","USA"):(30.3674,-89.0928),
    ("Pascagoula, Mississippi","USA"):(30.3658,-88.5561),
    ("Rauma","Finland"):(61.1272,21.5113),
    ("Antalya","Turkey"):(36.8969,30.7133),
    ("Tuzla, Istanbul","Turkey"):(40.8167,29.3000),
    ("Altınova, Yalova","Turkey"):(40.6944,29.5097),
    ("La Spezia","Italy"):(44.1025,9.8241),
}

def shipyard_map_data(prof):
    yards=prof.get("yards",pd.DataFrame())
    if yards is None or yards.empty:
        return pd.DataFrame()
    rows=[]
    for _,r in yards.iterrows():
        loc=str(r.get("Location","")).strip()
        country=str(r.get("Country","")).strip()
        shipyard=str(r.get("Shipyard","")).strip()
        xy=YARD_CITY_COORDS.get((loc,country))
        if not xy:
            for (k_loc,k_country),coords in YARD_CITY_COORDS.items():
                if loc and (loc.lower()==k_loc.lower() or loc.lower() in k_loc.lower() or k_loc.lower() in loc.lower()):
                    xy=coords
                    break
        if xy:
            rows.append({"name":shipyard,"location":loc,"country":country,"lat":xy[0],"lon":xy[1]})
    return pd.DataFrame(rows)

def port_map_data(prof):
    """Canonical parent-port coordinates with stress-test fallback locations."""
    ports=prof.get("ports",pd.DataFrame()).copy()
    terms=prof.get("port_terminals",pd.DataFrame()).copy()
    rows=[]
    if not ports.empty:
        for _,r in ports.iterrows():
            nm=str(r.get("Port / Facility","")).strip()
            country=str(r.get("Country","")).strip()
            lat=pd.to_numeric(pd.Series([r.get("Latitude","")]),errors="coerce").iloc[0] if "Latitude" in ports.columns else None
            lon=pd.to_numeric(pd.Series([r.get("Longitude","")]),errors="coerce").iloc[0] if "Longitude" in ports.columns else None
            if pd.isna(lat) or pd.isna(lon):
                xy=PORT_CITY_COORDS.get(nm)
                if xy: lat,lon=xy
            if lat is not None and lon is not None and not pd.isna(lat) and not pd.isna(lon):
                rows.append({"name":nm,"country":country,"lat":float(lat),"lon":float(lon)})
    # fallback from parent-port names where canonical port rows are missing
    if not terms.empty:
        for _,r in terms.iterrows():
            nm=str(r.get("Parent Port","")).strip()
            if not nm: continue
            xy=PORT_CITY_COORDS.get(nm) or PORT_CITY_COORDS.get("Port of "+nm)
            if xy:
                rows.append({"name":nm,"country":str(r.get("Country","")).strip(),"lat":xy[0],"lon":xy[1]})
    if not rows: return pd.DataFrame()
    return pd.DataFrame(rows).drop_duplicates(subset=["name","lat","lon"])

def render_port_visuals(prof):
    terms=prof.get("port_terminals",pd.DataFrame())
    ports=prof.get("ports",pd.DataFrame())
    m=port_map_data(prof)
    if not m.empty:
        st.markdown("### Geographic footprint")
        st.map(m,latitude="lat",longitude="lon",size=70)

    # Direct port portfolios such as ABP should still produce a useful figure.
    if isinstance(ports,pd.DataFrame) and not ports.empty and "Country" in ports.columns:
        pc=ports["Country"].astype(str).replace("",pd.NA).dropna().value_counts().head(15)
        if not pc.empty:
            st.markdown("### Ports by country")
            st.bar_chart(pc,horizontal=True)

    if terms is None or terms.empty:
        return

    # Country footprint
    if "Country" in terms.columns:
        counts=terms["Country"].astype(str).replace("",pd.NA).dropna().value_counts().head(15)
        if not counts.empty:
            st.markdown("### Terminals by country")
            st.bar_chart(counts,horizontal=True)

    # Capacity where populated
    if "Container Capacity TEU/yr" in terms.columns:
        cap=terms[["Terminal / Facility","Container Capacity TEU/yr"]].copy()
        cap["Container Capacity TEU/yr"]=_numeric(cap["Container Capacity TEU/yr"])
        cap=cap.dropna().sort_values("Container Capacity TEU/yr",ascending=False).head(15)
        if not cap.empty:
            st.markdown("### Largest seeded terminal capacities")
            st.bar_chart(cap.set_index("Terminal / Facility")["Container Capacity TEU/yr"],horizontal=True)

def render_shipyard_visuals(prof):
    yards=prof.get("yards",pd.DataFrame())
    caps=prof.get("yard_capabilities",pd.DataFrame())
    sm=shipyard_map_data(prof)
    if not sm.empty:
        st.markdown("### Shipyard footprint")
        st.map(sm,latitude="lat",longitude="lon",size=85)
    if yards is not None and not yards.empty and "Country" in yards.columns:
        yc=yards["Country"].astype(str).replace("",pd.NA).dropna().value_counts()
        if not yc.empty:
            st.markdown("### Shipyards by country")
            st.bar_chart(yc,horizontal=True)
    if caps is not None and not caps.empty and "Capability" in caps.columns:
        cc=caps["Capability"].astype(str).replace("",pd.NA).dropna().value_counts().head(15)
        if not cc.empty:
            st.markdown("### Seeded yard capabilities")
            st.bar_chart(cc,horizontal=True)

def render_market_visuals(entity_id):
    prices=TABLES.get(("Corporate & Markets","Company Market Prices"),pd.DataFrame())
    if prices.empty or "Company ID" not in prices.columns:
        return
    scope=company_scope_ids(entity_id)
    p=prices[prices["Company ID"].astype(str).isin(scope)].copy()
    if p.empty or "Month End" not in p.columns or "Close" not in p.columns:
        return
    p["Date"]=pd.to_datetime(p["Month End"],errors="coerce")
    p["Close Numeric"]=_numeric(p["Close"])
    p=p.dropna(subset=["Date","Close Numeric"]).sort_values("Date")
    if len(p)>=3:
        st.markdown("### Market price")
        st.line_chart(p.set_index("Date")["Close Numeric"])


def event_bundle_for_entities(entity_ids=None, asset_ids=None, system_ids=None):
    entity_ids=set(str(x) for x in (entity_ids or []) if str(x))
    asset_ids=set(str(x) for x in (asset_ids or []) if str(x))
    system_ids=set(str(x) for x in (system_ids or []) if str(x))
    events=TABLES.get(("Events & Hazards","Events"),pd.DataFrame())
    ecl=TABLES.get(("Events & Hazards","Event Company Links"),pd.DataFrame())
    eal=TABLES.get(("Events & Hazards","Event Asset Links"),pd.DataFrame())
    esl=TABLES.get(("Events & Hazards","Event System Links"),pd.DataFrame())
    loc=TABLES.get(("Events & Hazards","Event Locations"),pd.DataFrame())
    chains=TABLES.get(("Events & Hazards","Impact Chains"),pd.DataFrame())
    ids=set()
    if entity_ids and not ecl.empty and "Company ID" in ecl.columns:
        x=ecl[ecl["Company ID"].astype(str).isin(entity_ids)]
        if "Event ID" in x.columns: ids.update(x["Event ID"].astype(str))
    if asset_ids and not eal.empty and "Asset ID" in eal.columns:
        x=eal[eal["Asset ID"].astype(str).isin(asset_ids)]
        if "Event ID" in x.columns: ids.update(x["Event ID"].astype(str))
    if system_ids and not esl.empty and "System ID" in esl.columns:
        x=esl[esl["System ID"].astype(str).isin(system_ids)]
        if "Event ID" in x.columns: ids.update(x["Event ID"].astype(str))
    ev=events[events["Event ID"].astype(str).isin(ids)].copy() if ids and not events.empty else pd.DataFrame()
    eloc=loc[loc["Event ID"].astype(str).isin(ids)].copy() if ids and not loc.empty else pd.DataFrame()
    ech=chains[chains["Event ID"].astype(str).isin(ids)].copy() if ids and not chains.empty else pd.DataFrame()
    return ev,eloc,ech

def render_event_map(events, locations, title="Event map"):
    if locations is None or locations.empty:
        st.info("No mapped event locations in this stress-test set.")
        return
    mp=locations.copy()
    mp["lat"]=_numeric(mp["Latitude"]); mp["lon"]=_numeric(mp["Longitude"])
    mp=mp.dropna(subset=["lat","lon"])
    if mp.empty:
        st.info("No mapped event locations.")
        return
    st.markdown(f"### {title}")
    st.map(mp,latitude="lat",longitude="lon",size=90)
    if events is not None and not events.empty and "Event Family" in events.columns:
        fam=events["Event Family"].astype(str).replace("",pd.NA).dropna().value_counts()
        if not fam.empty:
            st.markdown("### Event mix")
            st.bar_chart(fam,horizontal=True)

def resolve_event_link_target(link_type, link_id, link_name=""):
    """Resolve event-link aliases to canonical objects used by the Trade UI."""
    lt=str(link_type or "").lower(); lid=str(link_id or "").strip(); lname=str(link_name or "").strip()
    if "company" in lt:
        return ("Companies","company_pick_id",lid,lname)
    if "route" in lt:
        return (None,None,None,lname)
    if "system" in lt or lid.startswith("SYS") or lid.startswith("CORR"):
        return ("Corridors & Systems","system_pick_id",lid,lname)
    if "vessel" in lt or lid.startswith("VESSEL") or lid.startswith("VES_"):
        return ("Vessels","vessel_pick_id",lid,lname)
    # Asset links frequently came from legacy event IDs. Resolve ports by canonical name.
    ports=TABLES.get(("Maritime","Ports"),pd.DataFrame())
    if ("port" in lt or lid.startswith("PORT")) and not ports.empty:
        if "Port ID" in ports.columns and lid in set(ports["Port ID"].astype(str)):
            return ("Ports","port_pick_id",lid,lname)
        if lname and "Port / Facility" in ports.columns:
            exact=ports[ports["Port / Facility"].astype(str).str.casefold().eq(lname.casefold())]
            if exact.empty:
                exact=ports[ports["Port / Facility"].astype(str).str.contains(lname,case=False,regex=False,na=False)]
            if not exact.empty:
                return ("Ports","port_pick_id",str(exact.iloc[0].get("Port ID","")),str(exact.iloc[0].get("Port / Facility",lname)))
    return (None,None,None,lname)

def event_associations(event_id):
    """Return canonical event-object edges, querying live DB first so new loads surface immediately."""
    eid=str(event_id or "").strip()
    out=[]

    # Fresh canonical links first. This deliberately bypasses cached workbook-shaped
    # projections so a newly loaded event is visible on the next app rerun.
    if eid:
        try:
            sb=pc_db_client(service=True)
            if sb is not None:
                rows=(sb.table("pc_event_links")
                      .select("event_id,linked_type,linked_id,linked_name,relationship,confidence")
                      .eq("event_id",eid).limit(100).execute().data or [])
                for r in rows:
                    lt=str(r.get("linked_type") or "Asset")
                    lid=str(r.get("linked_id") or "")
                    lname=str(r.get("linked_name") or "")
                    rel=str(r.get("relationship") or "")
                    conf=str(r.get("confidence") or "")
                    out.append((lt,lid,lname,rel,conf))
        except Exception:
            pass

    if out:
        # Preserve one edge per canonical endpoint/relationship.
        seen=set(); dedup=[]
        for x in out:
            k=(x[0].casefold(),x[1],x[2].casefold(),x[3].casefold())
            if k in seen: continue
            seen.add(k); dedup.append(x)
        return dedup

    # Fallback to existing workbook-shaped projections.
    eal=TABLES.get(("Events & Hazards","Event Asset Links"),pd.DataFrame())
    ecl=TABLES.get(("Events & Hazards","Event Company Links"),pd.DataFrame())
    esl=TABLES.get(("Events & Hazards","Event System Links"),pd.DataFrame())
    if not eal.empty and "Event ID" in eal.columns:
        for _,r in eal[eal["Event ID"].astype(str).eq(eid)].iterrows():
            out.append((str(r.get("Asset Type","Asset")),str(r.get("Asset ID","")),str(r.get("Asset","")),str(r.get("Relationship","")),str(r.get("Confidence",""))))
    if not ecl.empty and "Event ID" in ecl.columns:
        for _,r in ecl[ecl["Event ID"].astype(str).eq(eid)].iterrows():
            out.append(("Company",str(r.get("Company ID","")),str(r.get("Company","")),str(r.get("Relationship","")),str(r.get("Confidence",""))))
    if not esl.empty and "Event ID" in esl.columns:
        for _,r in esl[esl["Event ID"].astype(str).eq(eid)].iterrows():
            out.append(("System",str(r.get("System ID","")),str(r.get("System","")),str(r.get("Relationship","")),str(r.get("Confidence",""))))
    return out

_EVENT_RENDER_SCOPE = 0

def _next_event_render_scope():
    global _EVENT_RENDER_SCOPE
    _EVENT_RENDER_SCOPE += 1
    return _EVENT_RENDER_SCOPE

def render_event_associations(event_id, key_prefix="event"):
    links=event_associations(event_id)
    if not links: return
    st.markdown("#### Commercially connected network")
    for i,(typ,lid,name,rel,conf) in enumerate(links[:12]):
        page,key,resolved_id,resolved_name=resolve_event_link_target(typ,lid,name)
        c1,c2=st.columns([4,1])
        with c1:
            st.markdown(f"**{resolved_name or name or lid}**  \n{pretty_enum(rel)}" + (f" · {conf}" if conf else ""))
        with c2:
            if page and resolved_id:
                widget_key = re.sub(r"[^A-Za-z0-9_.-]+", "_", f"{key_prefix}_{event_id}_{i}_{typ}_{resolved_id}_{rel}")
                if st.button("Open ↗",key=widget_key,use_container_width=True):
                    request_nav(page,key,resolved_id,resolved_name or name); st.rerun()

def _event_extended_context(row):
    """Expanded narrative fields stored by the canonical loader in event metadata."""
    meta = _pc_meta_dict(row.get("Metadata")) if hasattr(row, "get") else {}
    pools = [meta]
    for k in ["analysis", "ai_enrichment", "enrichment", "publication"]:
        v = meta.get(k) if isinstance(meta, dict) else None
        if isinstance(v, dict):
            pools.append(v)

    def pick(*keys):
        for pool in pools:
            for key in keys:
                v = pool.get(key) if isinstance(pool, dict) else None
                if v not in (None, "", [], {}):
                    return str(v).strip()
        return ""

    return {
        "analysis": pick("analysis_60_90", "analysis_60-90", "summary_60_90", "summary_60-90", "brief_75"),
        "why": pick("why_it_matters", "why_it_matters_60_90", "commercial_significance", "strategic_significance"),
        "means": pick("what_it_means", "implications", "assessment", "assessment_impact"),
        "monitoring": pick("monitoring_indicators", "monitoring", "indicators", "watch_items"),
    }


def _render_trade_event_inline_context(row, eid="", include_links=False):
    """Keep full event detail exactly where the user opened it."""
    ctx = _event_extended_context(row)
    description = str(row.get("Description", "") or "").strip()
    operational = str(row.get("Operational Impact", "") or "").strip()
    commercial = str(row.get("Trade / Commercial Impact", "") or "").strip()
    status = str(row.get("Status", "") or "").strip()
    confidence = str(row.get("Confidence", "") or "").strip()
    verification = str(row.get("Verification Status", "") or "").strip()

    if ctx["analysis"]:
        st.markdown("**Assessment · 60–90 words**")
        st.write(ctx["analysis"])
    if description:
        st.markdown("**What happened**")
        st.write(description)
    if ctx["why"]:
        st.markdown("**Why it matters**")
        st.write(ctx["why"])
    if ctx["means"]:
        st.markdown("**What it means**")
        st.write(ctx["means"])

    c1, c2 = st.columns(2)
    with c1:
        if operational:
            st.markdown("**Operational impact**")
            st.write(operational)
    with c2:
        if commercial:
            st.markdown("**Trade / commercial impact**")
            st.write(commercial)

    if ctx["monitoring"]:
        st.markdown("**Monitoring & indicators**")
        st.write(ctx["monitoring"])

    bits = [x for x in [
        f"Status: {status}" if status and status.lower() != "nan" else "",
        f"Verification: {verification}" if verification and verification.lower() != "nan" else "",
        f"Confidence: {confidence}" if confidence and confidence.lower() != "nan" else "",
    ] if x]
    if bits:
        st.caption(" · ".join(bits))

    if include_links and eid:
        render_event_associations(eid, key_prefix=f"inline_context_{eid}")


def render_event_cards(events,max_items=40):
    if events is None or events.empty:
        st.info("No linked events.")
        return

    render_scope = _next_event_render_scope()
    e = events.copy()

    if "Start Date" in e.columns:
        e["_dt"] = pd.to_datetime(e["Start Date"], errors="coerce")
        e = e.sort_values("_dt", ascending=False)

    for idx, (_, row) in enumerate(e.head(max_items).iterrows()):
        title = str(row.get("Title", "Event")).strip()
        eid = str(row.get("Event ID", "")).strip()

        meta = []
        for c in ["Start Date", "Event Type", "Severity", "Location"]:
            v = str(row.get(c, "")).strip()
            if v and v.lower() != "nan":
                meta.append(pretty_enum(v))

        description = str(row.get("Description", "")).strip()
        operational = str(row.get("Operational Impact", "")).strip()
        commercial = str(row.get("Trade / Commercial Impact", "")).strip()
        ext = _event_extended_context(row)
        lead_text = ext["analysis"] or description

        # Build a trade-facing event card: concise assessment first, consequence second.
        card = [
            "<div class='pc-card'>",
            f"<div class='pc-search-details' style='color:#D8B45A; text-transform:uppercase; letter-spacing:.08em;'>{html_lib.escape(' · '.join(meta))}</div>",
            f"<div class='pc-big' style='margin-top:10px;'>{html_lib.escape(title)}</div>",
        ]
        if lead_text and lead_text.lower() != "nan":
            card.append(f"<div class='pc-search-details' style='margin-top:10px;'>{html_lib.escape(lead_text)}</div>")
        if operational and operational.lower() != "nan":
            card.append(
                f"<div style='margin-top:12px;'><b>Operational impact:</b> {html_lib.escape(operational)}</div>"
            )
        if commercial and commercial.lower() != "nan":
            card.append(
                f"<div style='margin-top:8px; padding-top:8px; border-top:1px solid #33414C;'>"
                f"<b style='color:#D8B45A;'>Trade / commercial impact:</b> {html_lib.escape(commercial)}</div>"
            )
        card.append("</div>")
        st.markdown("".join(card), unsafe_allow_html=True)

        card_prefix = f"eventblock_{render_scope}_card_{idx}"

        with st.expander("Full event context", expanded=False):
            _render_trade_event_inline_context(row, eid=eid, include_links=False)

        # Commercially relevant linked network sits immediately beneath the event card.
        render_event_associations(eid, key_prefix=card_prefix)

        url = str(row.get("Primary Source URL", "")).strip()
        if url.startswith("http"):
            st.link_button("Open source ↗", url, key=f"{card_prefix}_{eid}_source")

        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)


def exclude_horizon_calendar_events(df: pd.DataFrame) -> pd.DataFrame:
    """Exclude scheduled/calendar records from live/latest reporting.

    This is intentionally conservative: election/holiday/anniversary/summit/calendar
    rows belong in Important dates / Trade Horizon, not in the current-reporting feed.
    """
    if df is None or df.empty:
        return pd.DataFrame() if df is None else df.copy()
    x=df.copy()
    blob=pd.Series("",index=x.index,dtype="string")
    for c in [
        "Event Nature","Event Domain","Event Family","Event Type",
        "Event Temporality","Event Phase","Event Category","Event Subcategory",
        "Mode","Title"
    ]:
        if c in x.columns:
            blob=blob.str.cat(x[c].fillna("").astype(str),sep=" ")
    pat=(
        r"\banniversar(?:y|ies)?\b|\bholiday\b|\bcommemorat(?:ion|ive)\b|"
        r"\belection\b|\breferendum\b|\bsummit\b|\bconference\b|"
        r"\bfestival\b|\bsporting event\b|\bhorizon calendar\b|"
        r"\bforward calendar\b|\bcalendar event\b"
    )
    is_horizon=blob.str.contains(pat,case=False,regex=True,na=False)
    if "Metadata" in x.columns:
        def _mh(v):
            m=_pc_meta_dict(v)
            h=m.get("horizon") if isinstance(m,dict) else {}
            return bool(h.get("show_in_trade_horizon")) if isinstance(h,dict) else False
        is_horizon |= x["Metadata"].map(_mh)
    return x[~is_horizon].copy()


def _live_trade_event_rows(limit=100):
    """Fresh canonical pc_events projection for home-page reporting.

    Avoids stale workbook/cache projections immediately after Power Admin loads.
    """
    try:
        sb=pc_db_client(service=True)
        if sb is None:
            return pd.DataFrame()
        cols=(
            "event_id,start_date,end_date,event_nature,event_domain,event_family,event_type,"
            "severity,status,mode,countries,location,title,description,operational_impact,"
            "commercial_impact,confidence,verification_status,metadata"
        )
        rows=(sb.table("pc_events").select(cols).order("start_date",desc=True).limit(max(20,int(limit))).execute().data or [])
        if not rows:
            return pd.DataFrame()
        df=pd.DataFrame(rows).rename(columns={
            "event_id":"Event ID","start_date":"Start Date","end_date":"End Date",
            "event_nature":"Event Nature","event_domain":"Event Domain","event_family":"Event Family",
            "event_type":"Event Type","severity":"Severity","status":"Status","mode":"Mode",
            "countries":"Country / Countries","location":"Location","title":"Title",
            "description":"Description","operational_impact":"Operational Impact",
            "commercial_impact":"Trade / Commercial Impact","confidence":"Confidence",
            "verification_status":"Verification Status","metadata":"Metadata"
        })
        return df
    except Exception:
        return pd.DataFrame()

def _clean_trade_text(value):
    """Return display-safe text; never leak pandas/DB null sentinels into cards."""
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    text=str(value).strip()
    return "" if text.casefold() in {"nan","none","null","nat","<na>"} else text


def _trade_consequence_text(row):
    """Best concise statement of what the development means for trade/business."""
    commercial=_clean_trade_text(row.get("Trade / Commercial Impact"))
    operational=_clean_trade_text(row.get("Operational Impact"))
    description=_clean_trade_text(row.get("Description"))

    # Prefer consequences. Description is only a fallback when the canonical record
    # lacks a separate impact field.
    text=commercial or operational or description
    if len(text)>360:
        text=text[:357].rstrip()+"…"
    return text


def _trade_home_eligible(row):
    """Whether a current event deserves scarce lead space on the Trade homepage.

    Security events must demonstrate an actual movement/capacity/cost/business consequence;
    severity by itself is never enough. Corporate/infrastructure/market developments can qualify
    when they materially change capacity, ownership, routes, contracts, rates or investment.
    """
    commercial=_clean_trade_text(row.get("Trade / Commercial Impact"))
    operational=_clean_trade_text(row.get("Operational Impact"))
    description=_clean_trade_text(row.get("Description"))
    title=_clean_trade_text(row.get("Title"))
    family=_clean_trade_text(row.get("Event Family"))
    etype=_clean_trade_text(row.get("Event Type"))
    domain=_clean_trade_text(row.get("Event Domain"))
    nature=_clean_trade_text(row.get("Event Nature"))
    blob=" ".join([title,family,etype,domain,nature,description,operational,commercial]).casefold()
    impact_blob=" ".join([commercial,operational]).casefold()

    consequence_terms=[
        "congestion","capacity","throughput","delay","closure","closed","disruption",
        "diversion","rerout","queue","storage","warehouse","terminal","berth","port",
        "rail","border","truck","trucking","customs","corridor","canal","chokepoint",
        "freight","rate","cost","demurrage","charter","tariff","sanction","compliance",
        "cargo","commodity","oil","gas","lng","refinery","pipeline","airport","air cargo",
        "supply chain","logistics","service launch","route launch","investment","capex",
        "contract","concession","acquisition","sale","newbuild","fleet","ipo","financing"
    ]
    meaningful_impact=len(commercial)>=35 or len(operational)>=35
    impact_signal=any(t in impact_blob for t in consequence_terms)

    # Security/incident records are only Trade leads when their canonical impact fields
    # explain the trade consequence. A dramatic title alone does not qualify.
    securityish=any(t in blob for t in [
        "attack","missile","drone","explosion","conflict","war","security","sabotage",
        "piracy","boarding","seizure","casualty"
    ])
    if securityish and not (meaningful_impact and impact_signal):
        return False

    # Generic political/civic calendar events and commentary do not lead Trade without
    # an explicit commercial/operational effect.
    generic=any(t in blob for t in [
        "independence day","national day","public holiday","election","referendum",
        "olympic","games","anniversary","commentary","opinion"
    ])
    if generic and not (meaningful_impact and impact_signal):
        return False

    # Everything else needs either a proper impact statement or a strong current
    # infrastructure/market/business signal in the record itself.
    strong_record=any(t in blob for t in consequence_terms)
    return bool(meaningful_impact or strong_record)


def _trade_priority_score(row, today=None):
    """Rank current Trade developments by real movement/capacity/cost/business consequence."""
    today=today or pd.Timestamp.utcnow().tz_localize(None).normalize()
    score=0.0

    d=pd.to_datetime(row.get("Start Date"),errors="coerce",utc=True)
    if pd.notna(d):
        d=d.tz_convert(None).normalize()
        age=max(0,(today-d).days)
        if age <= 1: score += 18
        elif age <= 3: score += 14
        elif age <= 7: score += 9
        elif age <= 30: score += 3

    commercial=_clean_trade_text(row.get("Trade / Commercial Impact"))
    operational=_clean_trade_text(row.get("Operational Impact"))
    if len(commercial)>=35: score += 32
    elif commercial: score += 14
    if len(operational)>=35: score += 24
    elif operational: score += 10

    blob=" ".join(_clean_trade_text(row.get(c)) for c in [
        "Title","Description","Event Nature","Event Domain","Event Family","Event Type",
        "Mode","Status","Location","Country / Countries","Operational Impact","Trade / Commercial Impact"
    ]).casefold()

    # Weight commercially useful signals more heavily than generic incident severity.
    weighted_terms={
        "congestion":8,"capacity":8,"throughput":8,"freight":8,"rate":8,
        "tariff":8,"sanction":7,"closure":7,"closed":7,"delay":7,"diversion":7,
        "rerout":7,"warehouse":6,"storage":6,"truck":6,"border":6,"customs":6,
        "corridor":7,"canal":7,"chokepoint":7,"cargo":5,"commodity":5,"oil":5,
        "gas":5,"lng":5,"refinery":6,"pipeline":6,"rail":6,"terminal":6,"port":5,
        "air cargo":6,"demurrage":8,"charter":6,"contract":5,"concession":6,
        "investment":5,"capex":5,"acquisition":4,"newbuild":3,"fleet":4,"financing":4
    }
    for term,w in weighted_terms.items():
        if term in blob:
            score += w
    score=min(score,150)

    # Severity is only a modest modifier; it cannot manufacture Trade relevance.
    severity=_clean_trade_text(row.get("Severity")).casefold()
    score += {"critical":8,"severe":7,"high":5,"medium":3,"moderate":3,"low":1}.get(severity,0)

    meta=_pc_meta_dict(row.get("Metadata"))
    story=meta.get("story") if isinstance(meta.get("story"),dict) else {}
    disruption=meta.get("disruption") if isinstance(meta.get("disruption"),dict) else {}
    if story.get("lead_story"): score += 10
    elif story.get("is_story"): score += 3
    if disruption.get("primary_disruption"): score += 10
    elif disruption.get("is_disruption"): score += 5

    return float(score)


def render_latest_reporting_trade(limit=4):
    """Priority current Trade intelligence; consequence first, chronology second."""
    events=_live_trade_event_rows(max(150,limit*30))
    if events.empty:
        events=TABLES.get(("Events & Hazards","Events"),pd.DataFrame()).copy()
    if events.empty:
        st.caption("No recent canonical reporting available.")
        return

    events=exclude_horizon_calendar_events(events)
    today=pd.Timestamp.utcnow().tz_localize(None).normalize()
    if "Start Date" in events.columns:
        events["_latest_dt"]=pd.to_datetime(events["Start Date"],errors="coerce",utc=True).dt.tz_convert(None)
        events=events[events["_latest_dt"].isna() | (events["_latest_dt"] < today + pd.Timedelta(days=1))].copy()

    # Sparse canonical events are useful elsewhere, but they do not belong in the
    # limited lead rail until they contain a real Trade consequence.
    eligible=events.apply(_trade_home_eligible,axis=1)
    events=events[eligible].copy()
    if events.empty:
        st.caption("No current developments yet have enough trade-impact context for the priority rail.")
        return

    events["_trade_priority"]=events.apply(lambda r:_trade_priority_score(r,today=today),axis=1)
    sort_cols=["_trade_priority"] + (["_latest_dt"] if "_latest_dt" in events.columns else [])
    events=events.sort_values(sort_cols,ascending=[False]*len(sort_cols),na_position="last").head(limit)

    for _,row in events.iterrows():
        title=_clean_trade_text(row.get("Title")) or "Trade development"
        date=pc_pretty_date(row.get("Start Date",""))
        etype=pretty_enum(_clean_trade_text(row.get("Event Type")) or "Development")
        location=_clean_trade_text(row.get("Location")) or _clean_trade_text(row.get("Country / Countries"))
        summary=_trade_consequence_text(row)

        st.markdown(
            "<div class='pc-card'>"
            f"<div class='pc-label'>{html_lib.escape(date)} · {html_lib.escape(etype)}</div>"
            f"<div class='pc-big' style='margin-top:5px'>{html_lib.escape(title)}</div>"
            + (f"<div class='pc-small' style='margin-top:4px'>{html_lib.escape(location)}</div>" if location else "")
            + (f"<div class='pc-search-details' style='margin-top:9px'>{html_lib.escape(summary)}</div>" if summary else "")
            + "</div>",unsafe_allow_html=True
        )
        eid=_clean_trade_text(row.get("Event ID"))
        with st.expander("Full event context",expanded=False):
            _render_trade_event_inline_context(row,eid=eid,include_links=True)


def render_trade_horizon_sidebar_compact(limit=4):
    """Homepage rail: genuinely future, materially trade-relevant dates only."""
    stories=_canonical_trade_story_frame()
    if stories is None or stories.empty:
        st.caption("No important dates currently classified.")
        return
    horizon=trade_horizon_events(stories)
    if horizon is None or horizon.empty:
        st.caption("No important dates currently classified.")
        return

    if "Start Date" in horizon.columns:
        horizon["_hdt"]=pd.to_datetime(horizon["Start Date"],errors="coerce",utc=True).dt.tz_convert(None)
        today=pd.Timestamp.utcnow().tz_localize(None).normalize()
        # Strictly future. Same-day announcements/orders are current reporting, not dates.
        horizon=horizon[horizon["_hdt"].notna() & (horizon["_hdt"] > today)].copy()

    if horizon.empty:
        st.caption("No upcoming important dates currently classified.")
        return

    def _homepage_date_relevant(r):
        title=_clean_trade_text(r.get("Title"))
        family=_clean_trade_text(r.get("Event Family"))
        etype=_clean_trade_text(r.get("Event Type"))
        commercial=_clean_trade_text(r.get("Trade / Commercial Impact"))
        operational=_clean_trade_text(r.get("Operational Impact"))
        htype=_clean_trade_text(r.get("Horizon Type"))
        blob=" ".join([title,family,etype,commercial,operational,htype]).casefold()

        # Exclude generic civic/holiday dates unless the record itself explains a
        # material trade consequence.
        generic=any(x in blob for x in [
            "independence day","national day","public holiday","bank holiday",
            "olympic","games","festival","anniversary"
        ])
        impact=" ".join([commercial,operational]).casefold()
        consequence=any(x in impact for x in [
            "closure","delay","capacity","cargo","port","rail","border","customs",
            "freight","rate","supply chain","logistics","terminal","airport","trade"
        ])
        if generic and not consequence:
            return False

        # Future announcements/newbuild orders are not dates simply because they were
        # classified broadly as Horizon. Require a scheduled milestone/watch/deadline.
        milestone=any(x in blob for x in [
            "deadline","opening","launch","service start","route launch","commission",
            "tender","award","auction","expiry","strike","vote","election","referendum",
            "season","monsoon","hurricane","cyclone","summit","conference","delivery",
            "completion","regulatory","review","decision","hearing","milestone"
        ])
        meta=_pc_meta_dict(r.get("Metadata"))
        h=meta.get("horizon") if isinstance(meta.get("horizon"),dict) else {}
        explicit=bool(h.get("show_in_trade_horizon")) and bool(
            h.get("next_milestone") or h.get("target_date") or h.get("window") or h.get("horizon_type")
        )
        return bool(milestone or explicit)

    horizon=horizon[horizon.apply(_homepage_date_relevant,axis=1)].copy()
    if horizon.empty:
        st.caption("No upcoming important dates currently classified.")
        return

    horizon=horizon.sort_values("_hdt",ascending=True,na_position="last")
    # Prevent duplicate cards for the same date/title/country.
    dedupe=[c for c in ["Start Date","Title","Country / Countries"] if c in horizon.columns]
    if dedupe:
        horizon=horizon.drop_duplicates(subset=dedupe)

    for _,r in horizon.head(limit).iterrows():
        date=pc_pretty_date(r.get("Start Date",""))
        title=_clean_trade_text(r.get("Title")) or "Upcoming trade milestone"
        country=_clean_trade_text(r.get("Country / Countries")) or _clean_trade_text(r.get("Location"))
        st.markdown(
            "<div class='pc-card' style='padding:10px 12px'>"
            f"<div class='pc-label'>{html_lib.escape(date)}</div>"
            f"<div class='pc-small' style='font-weight:700;margin-top:4px'>{html_lib.escape(title)}</div>"
            + (f"<div class='pc-small'>{html_lib.escape(country)}</div>" if country else "")
            + "</div>",
            unsafe_allow_html=True,
        )


def entity_asset_ids_from_profile(prof):
    ids=set()
    for key,col in [
        ("port_terminals","Terminal ID"),("ports","Port ID"),("yards","Yard ID"),
        ("assets","Asset ID"),("defence_vessels","Vessel ID"),("maritime_vessels","Vessel ID")
    ]:
        df=prof.get(key,pd.DataFrame())
        if isinstance(df,pd.DataFrame) and not df.empty and col in df.columns:
            ids.update(df[col].astype(str).tolist())
    return ids

def _num(v):
    try:
        if v is None or str(v).strip()=="": return None
        return float(str(v).replace(",",""))
    except Exception:
        return None

def _money(v,currency=""):
    n=_num(v)
    if n is None: return "Undisclosed"
    cur=str(currency or "").strip()
    a=abs(n)
    if a>=1_000_000_000: txt=f"{n/1_000_000_000:,.2f}bn"
    elif a>=1_000_000: txt=f"{n/1_000_000:,.1f}m"
    elif a>=1_000: txt=f"{n/1_000:,.1f}k"
    else: txt=f"{n:,.0f}"
    return f"{cur} {txt}".strip()

def _metric_value(row):
    v=_num(row.get("Value",""))
    unit=str(row.get("Unit","")).strip().lower()
    cur=str(row.get("Currency","")).strip()
    if v is None: return "—"
    if unit=="percent": return f"{v:,.1f}%"
    if unit=="multiple": return f"{v:,.1f}x"
    if unit=="currency": return _money(v,cur)
    return f"{v:,.1f} {row.get('Unit','')}".strip()

def _company_investments(entity_id):
    df=TABLES.get(("Corporate & Markets","Investments"),pd.DataFrame()).copy()
    if df.empty: return df
    scope=company_scope_ids(entity_id)
    if "Company ID" in df.columns:
        df=df[df["Company ID"].astype(str).isin(scope)]
    return df

def render_investment_dashboard(base_df=None, company_id=None, compact=False):
    df=(base_df.copy() if isinstance(base_df,pd.DataFrame) else TABLES.get(("Corporate & Markets","Investments"),pd.DataFrame()).copy())
    if df.empty:
        st.info("No structured investment records are available yet.")
        return
    if company_id and "Company ID" in df.columns:
        df=df[df["Company ID"].astype(str).isin(company_scope_ids(company_id))]
    if df.empty:
        st.info("No structured investment records are mapped to this company yet.")
        return
    if "Company ID" in df.columns:
        df["Company"]=df["Company ID"].map(label)
    if "Announced Date" in df.columns:
        df["_date"]=pd.to_datetime(df["Announced Date"],errors="coerce")
        if "Fiscal Year" not in df.columns: df["Fiscal Year"]=df["_date"].dt.year.astype("Int64").astype(str)
        df["Month"]=df["_date"].dt.to_period("M").astype(str)
    # Filters
    fc=st.columns(4 if company_id else 5)
    idx=0
    if not company_id:
        companies=["All"]+sorted([x for x in df.get("Company",pd.Series(dtype=str)).dropna().astype(str).unique() if x])
        co=fc[idx].selectbox("Company",companies,key="inv_company_filter"); idx+=1
        if co!="All": df=df[df["Company"].eq(co)]
    years=["All"]+sorted([str(x) for x in df.get("Fiscal Year",pd.Series(dtype=str)).dropna().astype(str).unique() if str(x).strip()],reverse=True)
    yr=fc[idx].selectbox("Year",years,key=f"inv_year_{company_id or 'global'}"); idx+=1
    if yr!="All": df=df[df["Fiscal Year"].astype(str).eq(yr)]
    regs=["All"]+sorted([x for x in df.get("Region",pd.Series(dtype=str)).dropna().astype(str).unique() if x])
    rg=fc[idx].selectbox("Region",regs,key=f"inv_region_{company_id or 'global'}"); idx+=1
    if rg!="All": df=df[df["Region"].eq(rg)]
    spends=["All"]+sorted([x for x in df.get("Spend Type",pd.Series(dtype=str)).dropna().astype(str).unique() if x])
    sp=fc[idx].selectbox("Spend type",spends,key=f"inv_spend_{company_id or 'global'}"); idx+=1
    if sp!="All": df=df[df["Spend Type"].eq(sp)]
    if not company_id:
        stages=["All"]+sorted([x for x in df.get("Investment Stage",pd.Series(dtype=str)).dropna().astype(str).unique() if x])
        sg=fc[idx].selectbox("Stage",stages,key="inv_stage_global")
        if sg!="All": df=df[df["Investment Stage"].eq(sg)]
    if df.empty:
        st.warning("No investments match those filters.")
        return
    # numeric fields
    df["_reported"]=pd.to_numeric(df.get("Reported Value",0),errors="coerce")
    df["_usd"]=pd.to_numeric(df.get("USD Value if Reported",0),errors="coerce")
    k1,k2,k3,k4,k5=st.columns(5)
    k1.metric("Records",f"{len(df):,}")
    k2.metric("Companies",f"{df['Company'].nunique():,}" if "Company" in df.columns else "—")
    k3.metric("Countries",f"{df.get('Country',pd.Series(dtype=str)).replace('',pd.NA).nunique():,}")
    k4.metric("Known USD value",_money(df["_usd"].sum(),"USD") if df["_usd"].notna().any() and df["_usd"].sum()>0 else "Not comparable")
    k5.metric("Undisclosed",f"{(df.get('Value Status','').astype(str).str.lower()=='undisclosed').sum():,}" if "Value Status" in df.columns else "—")
    st.caption("USD totals use only values explicitly reported in USD or with a source-reported USD equivalent. Native currencies are not silently converted, avoiding false precision.")

    # Currency totals and analytical charts
    native=df[df["_reported"].notna() & df.get("Currency",pd.Series(index=df.index,dtype=str)).astype(str).ne("")]
    if not native.empty:
        cur=native.groupby("Currency",dropna=False)["_reported"].sum().reset_index().rename(columns={"_reported":"Reported value"})
        cur["Reported value"]=cur.apply(lambda r:_money(r["Reported value"],r["Currency"]),axis=1)
        st.markdown("#### Reported investment value by currency")
        display_df(cur,20)
    c1,c2=st.columns(2)
    with c1:
        st.markdown("#### Investment activity by region")
        reg=df.groupby("Region",dropna=False).size().sort_values(ascending=False)
        st.bar_chart(reg)
    with c2:
        st.markdown("#### Investment activity by spend type")
        typ=df.groupby("Spend Type",dropna=False).size().sort_values(ascending=False)
        st.bar_chart(typ)
    if "Month" in df.columns and df["Month"].replace("NaT",pd.NA).notna().any():
        st.markdown("#### Activity through the year")
        monthly=df[df["Month"].ne("NaT")].groupby("Month").size().sort_index()
        st.bar_chart(monthly)

    st.markdown("#### Investment register")
    cols=[c for c in ["Announced Date","Company","Project","Country","Region","Asset / Location","Investment Class","Spend Type","Reported Value","Currency","Status","Investment Stage","Capacity / Scope","Strategic Relevance"] if c in df.columns]
    out=df[cols].copy()
    if "Reported Value" in out.columns:
        out["Reported Value"]=df.apply(lambda r:_money(r.get("Reported Value"),r.get("Currency","")),axis=1)
    display_df(out.sort_values("Announced Date",ascending=False) if "Announced Date" in out.columns else out,250)

def render_company_financials(entity_id):
    scope=company_scope_ids(entity_id)
    fin=TABLES.get(("Corporate & Markets","Company Financial Metrics"),pd.DataFrame()).copy()
    rep=TABLES.get(("Corporate & Markets","Company Reports"),pd.DataFrame()).copy()
    op=TABLES.get(("Corporate & Markets","Company Operating Metrics"),pd.DataFrame()).copy()
    if not fin.empty and "Company ID" in fin.columns: fin=fin[fin["Company ID"].astype(str).isin(scope)]
    if not rep.empty and "Company ID" in rep.columns: rep=rep[rep["Company ID"].astype(str).isin(scope)]
    if not op.empty and "Company ID" in op.columns: op=op[op["Company ID"].astype(str).isin(scope)]
    if fin.empty and rep.empty and op.empty:
        st.info("No public financial or operating metrics have been structured for this company yet. Private-company disclosure may be limited.")
        return
    if not fin.empty:
        fin["_dt"]=pd.to_datetime(fin.get("Period End",""),errors="coerce")
        periods=sorted([x for x in fin.get("Period End",pd.Series(dtype=str)).astype(str).unique() if x],reverse=True)
        selected=st.selectbox("Financial period",["Latest"]+periods,key=f"fin_period_{entity_id}")
        if selected=="Latest":
            latest=fin["_dt"].max()
            view=fin[fin["_dt"].eq(latest)] if pd.notna(latest) else fin
        else: view=fin[fin["Period End"].astype(str).eq(selected)]
        st.markdown("### Financial snapshot")
        metric_rows=view.head(8).to_dict("records")
        for start in range(0,len(metric_rows),4):
            boxes=st.columns(min(4,len(metric_rows)-start))
            for box,row in zip(boxes,metric_rows[start:start+4]):
                box.metric(pretty_enum(row.get("Metric","Metric")),_metric_value(row))
        hist=fin.copy()
        hist["Value"]=pd.to_numeric(hist["Value"],errors="coerce")
        currency_metrics=hist[hist.get("Unit","").astype(str).eq("currency")]
        if not currency_metrics.empty:
            st.markdown("### Financial history")
            pivot=currency_metrics.pivot_table(index="Metric",columns="Period End",values="Value",aggfunc="first")
            display_df(pivot.reset_index(),100)
        st.markdown("### Metric evidence")
        show=fin[[c for c in ["Period End","Metric","Value","Unit","Currency","Segment","Source URL","Notes"] if c in fin.columns]].copy()
        if "Value" in show.columns:
            show["Value"]=fin.apply(_metric_value,axis=1)
        display_df(show.sort_values("Period End",ascending=False),200)
    if not op.empty:
        st.markdown("### Operating metrics")
        display_df(op[[c for c in ["Period End","Metric","Value","Unit","Mode","Geography","Source URL","Notes"] if c in op.columns]],100)
    if not rep.empty:
        st.markdown("### Reports & filings")
        display_df(rep[[c for c in ["Report Type","Period","Publication Date","Document Title","Currency","Source URL","Status","Notes"] if c in rep.columns]],100)
    st.markdown("### Share-price history")
    render_share_price_history(entity_id)


def _company_live_logistics_bundle(entity_id, entity_name):
    """Live, cross-modal company intelligence from the expanded canonical schema.

    Company pages should describe the business that actually exists. A road carrier
    should lead with trucking, fleet, services and inland corridors; a rail operator
    should lead with networks/nodes; a port group should expose ports and terminals.
    Maritime is one mode in the logistics cycle, not the default company template.
    """
    live=_live_canonical_company_rollup(entity_id,entity_name)
    scope={str(x) for x in live.get("scope_ids",set()) if str(x)}
    if str(entity_id): scope.add(str(entity_id))

    # Resolve canonical IDs by name too, because migration-era workbook IDs can still
    # be used to open a profile while new enrichment lands under ENT_* identifiers.
    entities=_live_frame("pc_entities","entity_id,name,entity_type,subtype,hq_city,hq_country,status,record_status,metadata",25000)
    root=_company_name_key(entity_name)
    if not entities.empty and root:
        keys=entities.get("name",pd.Series(index=entities.index,dtype=str)).fillna("").astype(str).map(_company_name_key)
        mask=keys.eq(root) | keys.str.startswith(root+" ",na=False)
        scope.update(entities.loc[mask,"entity_id"].fillna("").astype(str).tolist())
    scope={x for x in scope if x}

    def by_entity(table, limit=20000):
        df=_live_frame(table,"*",limit)
        if df.empty or "entity_id" not in df.columns: return pd.DataFrame()
        return df[df["entity_id"].fillna("").astype(str).isin(scope)].copy()

    out={
        "scope_ids":scope,
        "profile":by_entity("pc_company_profiles",10000),
        "registrations":by_entity("pc_company_registrations",10000),
        "footprint":by_entity("pc_company_operating_footprint",20000),
        "trucking":by_entity("pc_trucking_company_details",5000),
        "rail_operator":by_entity("pc_rail_operator_details",5000),
        "financials":by_entity("pc_financial_records",20000),
        "live_assets":live.get("assets",pd.DataFrame()),
        "live_ports":live.get("ports",pd.DataFrame()),
        "live_terminals":live.get("terminals",pd.DataFrame()),
        "live_mobile":live.get("vessels",pd.DataFrame()),
        "live_relationships":live.get("relationships",pd.DataFrame()),
    }

    # Transport services are linked through operator rows, not inferred from mode names.
    ops=_live_frame("pc_transport_service_operators","*",30000)
    if not ops.empty and "entity_id" in ops.columns:
        ops=ops[ops["entity_id"].fillna("").astype(str).isin(scope)].copy()
    else: ops=pd.DataFrame()
    out["service_operators"]=ops
    sids=set(ops.get("transport_service_id",pd.Series(dtype=str)).dropna().astype(str)) if not ops.empty else set()
    services=_live_frame("pc_transport_services","*",50000,"effective_start")
    if not services.empty:
        smask=services.get("transport_service_id",pd.Series(index=services.index,dtype=str)).fillna("").astype(str).isin(sids)
        if "primary_operator_entity_id" in services.columns:
            smask |= services["primary_operator_entity_id"].fillna("").astype(str).isin(scope)
        services=services[smask].copy()
    else: services=pd.DataFrame()
    out["services"]=services
    service_ids=set(services.get("transport_service_id",pd.Series(dtype=str)).dropna().astype(str)) if not services.empty else set()
    stops=_live_frame("pc_transport_service_stops","*",60000)
    if service_ids and not stops.empty and "transport_service_id" in stops.columns:
        stops=stops[stops["transport_service_id"].fillna("").astype(str).isin(service_ids)].copy()
        if "asset_id" in stops.columns:
            stops["asset_name"]=stops["asset_id"].fillna("").astype(str).map(lambda x: relationship_endpoint_label(x,"asset"))
    else: stops=pd.DataFrame()
    out["service_stops"]=stops

    # Rail network hierarchy.
    rn=_live_frame("pc_rail_networks","*",10000)
    if not rn.empty:
        rm=pd.Series(False,index=rn.index)
        for c in ["owner_entity_id","operator_entity_id","authority_entity_id"]:
            if c in rn.columns: rm |= rn[c].fillna("").astype(str).isin(scope)
        rn=rn[rm].copy()
    out["rail_networks"]=rn
    rids=set(rn.get("rail_network_id",pd.Series(dtype=str)).dropna().astype(str)) if not rn.empty else set()
    nodes=_live_frame("pc_rail_nodes","*",20000)
    out["rail_nodes"]=nodes[nodes.get("rail_network_id",pd.Series(index=nodes.index,dtype=str)).astype(str).isin(rids)].copy() if rids and not nodes.empty else pd.DataFrame()
    links=_live_frame("pc_rail_links","*",25000)
    out["rail_links"]=links[links.get("rail_network_id",pd.Series(index=links.index,dtype=str)).astype(str).isin(rids)].copy() if rids and not links.empty else pd.DataFrame()

    # Road corridors can be linked through owned/operated physical assets or source metadata.
    road=_live_frame("pc_road_corridors","*",15000)
    asset_ids=set()
    if isinstance(out["live_assets"],pd.DataFrame) and not out["live_assets"].empty:
        asset_ids.update(out["live_assets"].get("Asset ID",pd.Series(dtype=str)).dropna().astype(str))
    if not road.empty:
        mask=pd.Series(False,index=road.index)
        for c in ["origin_asset_id","destination_asset_id"]:
            if c in road.columns and asset_ids:
                mask |= road[c].fillna("").astype(str).isin(asset_ids)
        # Retain explicit source metadata matches for carriers whose corridors have no terminal IDs.
        if entity_name:
            for c in ["metadata","corridor_name"]:
                if c in road.columns:
                    mask |= road[c].fillna("").astype(str).str.contains(str(entity_name),case=False,na=False,regex=False)
        road=road[mask].copy()
    out["road_corridors"]=road

    # Corporate transactions / projects / contracts / financing across the whole group scope.
    tx=_live_frame("pc_transactions","*",15000)
    if not tx.empty:
        mask=pd.Series(False,index=tx.index)
        for c in ["buyer_entity_id","seller_entity_id","target_entity_id"]:
            if c in tx.columns: mask |= tx[c].fillna("").astype(str).isin(scope)
        tx=tx[mask].copy()
    out["transactions"]=tx

    projects=_live_frame("pc_project_details","*",15000)
    if not projects.empty:
        mask=pd.Series(False,index=projects.index)
        for c in ["sponsor_entity_id","developer_entity_id","delivery_entity_id","operator_entity_id","owner_entity_id"]:
            if c in projects.columns: mask |= projects[c].fillna("").astype(str).isin(scope)
        projects=projects[mask].copy()
    out["projects"]=projects

    cp=_live_frame("pc_contract_participants","*",30000)
    if not cp.empty and "entity_id" in cp.columns: cp=cp[cp["entity_id"].fillna("").astype(str).isin(scope)].copy()
    cids=set(cp.get("contract_id",pd.Series(dtype=str)).dropna().astype(str)) if not cp.empty else set()
    contracts=_live_frame("pc_contracts","*",15000,"announced_date")
    out["contract_participants"]=cp
    out["contracts"]=contracts[contracts.get("contract_id",pd.Series(index=contracts.index,dtype=str)).astype(str).isin(cids)].copy() if cids and not contracts.empty else pd.DataFrame()

    fp=_live_frame("pc_financing_participants","*",30000)
    if not fp.empty and "entity_id" in fp.columns: fp=fp[fp["entity_id"].fillna("").astype(str).isin(scope)].copy()
    fids=set(fp.get("financing_id",pd.Series(dtype=str)).dropna().astype(str)) if not fp.empty else set()
    finance=_live_frame("pc_financing_facilities","*",15000,"announced_date")
    out["financing_participants"]=fp
    out["financing"]=finance[finance.get("financing_id",pd.Series(index=finance.index,dtype=str)).astype(str).isin(fids)].copy() if fids and not finance.empty else pd.DataFrame()

    # Compliance and security records can name the company even before canonical target_id is populated.
    sec=_live_frame("pc_security_compliance","*",20000)
    if not sec.empty:
        mask=pd.Series(False,index=sec.index)
        if "target_id" in sec.columns: mask |= sec["target_id"].fillna("").astype(str).isin(scope)
        if "target_name" in sec.columns and entity_name:
            mask |= sec["target_name"].fillna("").astype(str).map(_company_name_key).eq(root)
        sec=sec[mask].copy()
    out["security_compliance"]=sec

    # Direct entity-linked canonical events.
    event_frames=[]
    for sid in sorted(scope):
        ev=_live_related_events("entity",[sid],5000)
        if not ev.empty: event_frames.append(ev)
    if event_frames:
        ev=pd.concat(event_frames,ignore_index=True,sort=False)
        if "event_id" in ev.columns: ev=ev.drop_duplicates("event_id",keep="last")
    else: ev=pd.DataFrame()
    out["events"]=ev

    return out


def _company_mode_summary(bundle, prof):
    """Return relevant logistics modes for adaptive company presentation."""
    modes=set()
    trucking=bundle.get("trucking",pd.DataFrame())
    rail=bundle.get("rail_operator",pd.DataFrame())
    services=bundle.get("services",pd.DataFrame())
    assets=bundle.get("live_assets",pd.DataFrame())
    mobile=bundle.get("live_mobile",pd.DataFrame())
    if isinstance(trucking,pd.DataFrame) and not trucking.empty: modes.add("Road")
    if isinstance(rail,pd.DataFrame) and not rail.empty: modes.add("Rail")
    if isinstance(bundle.get("rail_networks"),pd.DataFrame) and not bundle["rail_networks"].empty: modes.add("Rail")
    if isinstance(services,pd.DataFrame) and not services.empty and "mode" in services.columns:
        for v in services["mode"].fillna("").astype(str):
            x=v.casefold()
            if "road" in x or "truck" in x: modes.add("Road")
            if "rail" in x: modes.add("Rail")
            if "sea" in x or "maritime" in x or "ocean" in x: modes.add("Maritime")
            if "air" in x or "aviation" in x: modes.add("Aviation")
            if "ferry" in x: modes.add("Ferry")
    if isinstance(assets,pd.DataFrame) and not assets.empty:
        txt=" ".join(assets.fillna("").astype(str).values.flatten()).casefold()
        if any(k in txt for k in ["warehouse","logistics facility","crossdock","depot","distribution"]): modes.add("Warehousing")
        if any(k in txt for k in ["port","terminal","berth"]): modes.add("Ports")
        if "airport" in txt: modes.add("Aviation")
    if profile_count(prof,"ports") or profile_count(prof,"port_terminals"): modes.add("Ports")
    if profile_count(prof,"maritime_vessels"): modes.add("Maritime")
    return sorted(modes,key=lambda x:["Road","Rail","Warehousing","Aviation","Maritime","Ports","Ferry"].index(x) if x in ["Road","Rail","Warehousing","Aviation","Maritime","Ports","Ferry"] else 99)



def _company_terminal_union(bundle, prof):
    """Return the company terminal set with live canonical rows taking precedence.

    The company page historically counted the workbook/profile projection
    (`prof["port_terminals"]`).  New canonical terminals can therefore exist in
    pc_assets / the live company roll-up without changing the displayed metric.

    Merge the two representations by normalized terminal name + country, keeping
    the live canonical row last.  This is generic across all operators.
    """
    frames=[]

    legacy=prof.get("port_terminals",pd.DataFrame()) if isinstance(prof,dict) else pd.DataFrame()
    live=bundle.get("live_terminals",pd.DataFrame()) if isinstance(bundle,dict) else pd.DataFrame()

    if isinstance(legacy,pd.DataFrame) and not legacy.empty:
        x=legacy.copy()
        x["_source_rank"]=0
        frames.append(x)

    if isinstance(live,pd.DataFrame) and not live.empty:
        x=live.copy()
        x["_source_rank"]=1
        frames.append(x)

    if not frames:
        return pd.DataFrame()

    df=pd.concat(frames,ignore_index=True,sort=False)

    # Normalize common display columns across legacy/live projections.
    if "Terminal / Facility" not in df.columns:
        for c in ["Terminal","Facility","Asset","Name"]:
            if c in df.columns:
                df["Terminal / Facility"]=df[c]
                break

    if "Country" not in df.columns:
        df["Country"]=""

    def _k(v):
        s=str(v or "").casefold()
        s=re.sub(r"[^a-z0-9]+"," ",s).strip()
        return s

    df["_terminal_key"]=df.get(
        "Terminal / Facility",
        pd.Series(index=df.index,dtype=str)
    ).fillna("").astype(str).map(_k)

    df["_country_key"]=df.get(
        "Country",
        pd.Series(index=df.index,dtype=str)
    ).fillna("").astype(str).map(_k)

    # If a name is blank, preserve by ID instead of collapsing unrelated rows.
    blank=df["_terminal_key"].eq("")
    if blank.any():
        fallback=pd.Series("",index=df.index,dtype=str)
        for c in ["Terminal ID","Asset ID"]:
            if c in df.columns:
                fallback=fallback.mask(fallback.eq(""),df[c].fillna("").astype(str))
        df.loc[blank,"_terminal_key"]=fallback.loc[blank].map(_k)

    df=df.sort_values("_source_rank").drop_duplicates(
        subset=["_terminal_key","_country_key"],
        keep="last"
    )

    return df.drop(columns=["_source_rank","_terminal_key","_country_key"],errors="ignore").reset_index(drop=True)


def render_company_profile(entity_id, entity_name):
    prof=build_company_profile(entity_id,entity_name)
    rec=company_record(entity_id)
    bundle=_company_live_logistics_bundle(entity_id,entity_name)
    terminal_union=_company_terminal_union(bundle,prof)
    modes=_company_mode_summary(bundle,prof)

    st.markdown(f"## {entity_name}")
    if modes:
        st.markdown(" ".join(f"<span class='pc-chip'>{html_lib.escape(m)}</span>" for m in modes),unsafe_allow_html=True)

    # Prefer the new canonical company profile over older workbook summary fields.
    live_profile=bundle.get("profile",pd.DataFrame())
    if isinstance(live_profile,pd.DataFrame) and not live_profile.empty:
        pr=live_profile.iloc[0]
        summary=[]
        for col,label_txt in [
            ("company_class","Company class"),("sector","Sector"),("industry","Industry"),
            ("incorporation_country","Incorporation"),("publicly_traded","Publicly traded"),
            ("business_description","Business"),("products_services","Products / services"),
            ("operating_countries","Operating countries")]:
            val=pr.get(col)
            if val not in (None,"",[],{}) and str(val).lower() not in {"nan","none"}:
                summary.append(f"**{label_txt}:** {pc_display_value(val)}")
        if summary: st.markdown("  \n".join(summary[:7]))
    elif rec is not None:
        summary=[]
        for c in ["Entity Type","Industrial Model","HQ Country","Country / Geography","Business Segments","Markets","Ownership","Scale / Network Notes"]:
            if c in rec.index and str(rec.get(c,"")).strip(): summary.append(f"**{c}:** {rec.get(c)}")
        if summary: st.markdown("  \n".join(summary[:6]))

    # Group scope remains visible, but not as a substitute for operational content.
    if len(prof.get("scope_ids",[]))>1:
        group_names=[x for x in prof.get("scope_names",[]) if x != entity_name]
        if group_names: st.caption("Included group / controlled entities: " + " · ".join(group_names[:20]))

    # Adaptive metrics: only show a mode when this company actually has that mode.
    metrics=[]
    trucking=bundle.get("trucking",pd.DataFrame())
    if isinstance(trucking,pd.DataFrame) and not trucking.empty:
        trucks=pd.to_numeric(trucking.get("fleet_size_power_units",pd.Series(dtype=float)),errors="coerce").max()
        trailers=pd.to_numeric(trucking.get("fleet_size_trailers",pd.Series(dtype=float)),errors="coerce").max()
        if pd.notna(trucks): metrics.append(("Trucks / power units",f"{int(trucks):,}"))
        if pd.notna(trailers): metrics.append(("Trailers",f"{int(trailers):,}"))
    if not bundle.get("rail_networks",pd.DataFrame()).empty: metrics.append(("Rail networks",len(bundle["rail_networks"])))
    if not bundle.get("rail_nodes",pd.DataFrame()).empty: metrics.append(("Rail nodes",len(bundle["rail_nodes"])))
    if not bundle.get("services",pd.DataFrame()).empty: metrics.append(("Services / routes",len(bundle["services"])))
    if not bundle.get("footprint",pd.DataFrame()).empty: metrics.append(("Operating footprint",len(bundle["footprint"])))
    if profile_count(prof,"ports"): metrics.append(("Ports",profile_count(prof,"ports")))
    if isinstance(terminal_union,pd.DataFrame) and not terminal_union.empty:
        metrics.append(("Terminals",len(terminal_union)))
    if profile_count(prof,"maritime_vessels"): metrics.append(("Vessels",profile_count(prof,"maritime_vessels")))
    if not bundle.get("events",pd.DataFrame()).empty or profile_count(prof,"events"):
        metrics.append(("Events",max(len(bundle.get("events",pd.DataFrame())),profile_count(prof,"events"))))
    metrics=metrics[:7]
    if metrics:
        cols=st.columns(len(metrics))
        for c,(lab,val) in zip(cols,metrics): c.metric(lab,val)

    company_view=st.selectbox(
        "Company section",
        ["Logistics Profile","Connected Network","Investments","Financials","Share Price","Security & Risk"],
        key=f"company_section_{entity_id}"
    )
    if company_view=="Connected Network":
        st.markdown("### Connected logistics network")
        render_company_connected_model(entity_id,entity_name)
        return
    if company_view=="Investments":
        st.markdown("### Investment intelligence")
        render_investment_dashboard(company_id=entity_id)
        return
    if company_view=="Financials":
        # New financial records first, then the legacy/market renderer.
        if not bundle.get("financials",pd.DataFrame()).empty:
            st.markdown("### Canonical financial records")
            display_df(bundle["financials"],420)
        render_company_financials(entity_id)
        return
    if company_view=="Share Price":
        st.markdown("### Share-price intelligence")
        render_share_price_history(entity_id)
        return
    if company_view=="Security & Risk":
        if not bundle.get("security_compliance",pd.DataFrame()).empty:
            st.markdown("### Security / compliance records")
            display_df(bundle["security_compliance"],360)
        render_company_security_risk(entity_id,entity_name)
        return

    tabs=st.tabs([
        "Overview","Operations & Footprint","Services & Routes","Assets & Fleet",
        "Projects / Contracts","Events & News","Corporate & Financial","Risk & Compliance",
        "Relationships","Evidence"
    ])

    with tabs[0]:
        st.markdown("### End-to-end operating picture")
        st.caption("This profile follows the company's actual logistics role. Maritime sections appear only when maritime assets or services are linked.")
        if not trucking.empty:
            st.markdown("#### Road / trucking")
            display_df(trucking,260)
        if not bundle.get("rail_operator",pd.DataFrame()).empty:
            st.markdown("#### Rail operator profile")
            display_df(bundle["rail_operator"],260)
        if not bundle.get("services",pd.DataFrame()).empty:
            st.markdown("#### Core transport services")
            display_df(bundle["services"].head(20),320)
        if not bundle.get("footprint",pd.DataFrame()).empty:
            st.markdown("#### Geographic operating footprint")
            display_df(bundle["footprint"].head(30),320)
        if not bundle.get("rail_networks",pd.DataFrame()).empty:
            st.markdown("#### Rail networks")
            display_df(bundle["rail_networks"].head(20),300)
        if not bundle.get("road_corridors",pd.DataFrame()).empty:
            st.markdown("#### Road corridors")
            display_df(bundle["road_corridors"].head(20),300)
        if not prof.get("ports",pd.DataFrame()).empty:
            st.markdown("#### Ports")
            show_named_list(prof["ports"],"Port / Facility",["Country","Operator","Facility Type","Key Role"])
        if not prof.get("maritime_vessels",pd.DataFrame()).empty:
            st.markdown("#### Maritime fleet")
            display_df(prof["maritime_vessels"].head(25),280)

        latest_frames=[]
        for key,kind in [("news","News"),("strategic_news","Strategic event"),("canonical_event_news","Canonical event")]:
            x=prof.get(key,pd.DataFrame())
            if isinstance(x,pd.DataFrame) and not x.empty:
                y=x.copy(); y["_source_kind"]=kind; latest_frames.append(y)
        if latest_frames:
            latest=pd.concat(latest_frames,ignore_index=True,sort=False)
            if "Published Date" in latest.columns:
                latest["_dt"]=pd.to_datetime(latest["Published Date"],errors="coerce")
                latest=latest.sort_values("_dt",ascending=False)
            st.markdown("#### Latest linked reporting")
            show_named_list(latest.head(8),"Headline",["Published Date","Publisher","Event Type"],source_col="URL",max_items=8)

    with tabs[1]:
        st.markdown("### Operating footprint")
        if not bundle.get("footprint",pd.DataFrame()).empty: display_df(bundle["footprint"],420)
        if not bundle.get("trucking",pd.DataFrame()).empty:
            st.markdown("#### Trucking operating profile")
            display_df(bundle["trucking"],300)
        if not bundle.get("rail_operator",pd.DataFrame()).empty:
            st.markdown("#### Rail operating profile")
            display_df(bundle["rail_operator"],300)
        assets=bundle.get("live_assets",pd.DataFrame())
        if isinstance(assets,pd.DataFrame) and not assets.empty:
            st.markdown("#### Physical facilities / infrastructure")
            display_df(assets,420)
        if isinstance(terminal_union,pd.DataFrame) and not terminal_union.empty:
            st.markdown("#### Port terminals / facilities")
            display_df(terminal_union,500)

    with tabs[2]:
        if not bundle.get("services",pd.DataFrame()).empty:
            st.markdown("### Transport services")
            display_df(bundle["services"],460)
            if not bundle.get("service_operators",pd.DataFrame()).empty:
                with st.expander("Service operator roles",expanded=False): display_df(bundle["service_operators"],300)
            if not bundle.get("service_stops",pd.DataFrame()).empty:
                st.markdown("### Service rotations / stops")
                display_df(bundle["service_stops"],700)
        if not bundle.get("road_corridors",pd.DataFrame()).empty:
            st.markdown("### Road corridors")
            display_df(bundle["road_corridors"],420)
        if not bundle.get("rail_networks",pd.DataFrame()).empty:
            st.markdown("### Rail networks")
            display_df(bundle["rail_networks"],360)
        if not bundle.get("rail_nodes",pd.DataFrame()).empty:
            st.markdown("### Rail terminals / nodes")
            display_df(bundle["rail_nodes"],420)
        if not bundle.get("rail_links",pd.DataFrame()).empty:
            st.markdown("### Rail links")
            display_df(bundle["rail_links"],420)
        if not prof.get("sales_routes",pd.DataFrame()).empty:
            st.markdown("### Commercial / sales routes")
            display_df(prof["sales_routes"],300)
        if (bundle.get("services",pd.DataFrame()).empty and bundle.get("road_corridors",pd.DataFrame()).empty
            and bundle.get("rail_networks",pd.DataFrame()).empty and prof.get("sales_routes",pd.DataFrame()).empty):
            st.info("No structured services or route records are linked yet.")

    with tabs[3]:
        mobile=bundle.get("live_mobile",pd.DataFrame())
        if isinstance(mobile,pd.DataFrame) and not mobile.empty:
            st.markdown("### Mobile assets / fleet")
            display_df(mobile,460)
        if not prof.get("defence_vessels",pd.DataFrame()).empty:
            st.markdown("### Defence / government vessels")
            display_df(prof["defence_vessels"],320)
        if not prof.get("maritime_vessels",pd.DataFrame()).empty:
            st.markdown("### Maritime vessels")
            display_df(prof["maritime_vessels"],420)
        assets=bundle.get("live_assets",pd.DataFrame())
        if isinstance(assets,pd.DataFrame) and not assets.empty:
            st.markdown("### Fixed assets")
            display_df(assets,420)
        if ((not isinstance(mobile,pd.DataFrame) or mobile.empty) and prof.get("maritime_vessels",pd.DataFrame()).empty
            and (not isinstance(assets,pd.DataFrame) or assets.empty)):
            st.info("No individual asset or fleet records linked yet. Aggregate fleet/network data may still appear under Operations & Footprint.")

    with tabs[4]:
        if not bundle.get("projects",pd.DataFrame()).empty:
            st.markdown("### Projects")
            display_df(bundle["projects"],400)
        if not bundle.get("contracts",pd.DataFrame()).empty:
            st.markdown("### Contracts")
            display_df(bundle["contracts"],400)
        if not bundle.get("financing",pd.DataFrame()).empty:
            st.markdown("### Financing")
            display_df(bundle["financing"],400)
        if not bundle.get("transactions",pd.DataFrame()).empty:
            st.markdown("### Transactions")
            display_df(bundle["transactions"],400)
        if not prof.get("programmes",pd.DataFrame()).empty:
            st.markdown("### Programmes")
            display_df(prof["programmes"],300)

    with tabs[5]:
        # Fresh canonical company-event feed is authoritative; bundle events can lag a new load.
        ev=prof.get("canonical_live_events",pd.DataFrame())
        if ev is None or ev.empty:
            ev=bundle.get("events",pd.DataFrame())
        if isinstance(ev,pd.DataFrame) and not ev.empty:
            st.markdown("### Canonical linked events")
            display_df(ev,460)
        if not prof.get("events",pd.DataFrame()).empty:
            st.markdown("### Event / operational activity")
            render_event_cards(prof["events"],60)
        if not prof.get("news",pd.DataFrame()).empty:
            st.markdown("### News")
            show_named_list(prof["news"],"Headline",["Published Date","Publisher","Country","Event Type"],source_col="URL")
        if not prof.get("strategic_news",pd.DataFrame()).empty:
            st.markdown("### Strategic developments")
            show_named_list(prof["strategic_news"],"Headline",["Published Date","Publisher","Event Type","Region"],source_col="URL",max_items=100)
        if not prof.get("canonical_event_news",pd.DataFrame()).empty:
            st.markdown("### Canonical company developments")
            show_named_list(prof["canonical_event_news"],"Headline",["Published Date","Event Type","Event Family","Region","Relationship"],source_col="URL",max_items=100)

    with tabs[6]:
        if not live_profile.empty:
            st.markdown("### Company profile")
            display_df(live_profile,300)
        if not bundle.get("registrations",pd.DataFrame()).empty:
            st.markdown("### Registrations / legal entities")
            display_df(bundle["registrations"],340)
        if not bundle.get("financials",pd.DataFrame()).empty:
            st.markdown("### Financial records")
            display_df(bundle["financials"],420)
        if not prof.get("announcements",pd.DataFrame()).empty:
            st.markdown("### Announcements")
            show_named_list(prof["announcements"],"Headline",["Date","Event Type"])

    with tabs[7]:
        if not bundle.get("security_compliance",pd.DataFrame()).empty:
            st.markdown("### Security / compliance")
            display_df(bundle["security_compliance"],420)
        if not prof.get("sanctions_links",pd.DataFrame()).empty:
            st.markdown("### Sanctions / designation-linked exposure")
            display_df(prof["sanctions_links"],350)
        if not prof.get("sanctions_designations",pd.DataFrame()).empty:
            st.markdown("### Related designation records")
            display_df(humanize_sanctions_df(prof["sanctions_designations"]),350)
        if not prof.get("trade_agreements",pd.DataFrame()).empty:
            st.markdown("### Trade agreements / market access")
            display_df(prof["trade_agreements"],320)

    with tabs[8]:
        st.markdown("### Corporate & operational relationships")
        readable_relationships(prof.get("relationships",pd.DataFrame()),entity_id)
        if not bundle.get("live_relationships",pd.DataFrame()).empty:
            with st.expander("Live canonical relationship rows",expanded=False):
                display_df(bundle["live_relationships"],420)
        if not prof.get("systems",pd.DataFrame()).empty:
            st.markdown("### Connected systems / corridors")
            display_df(prof["systems"],300)

    with tabs[9]:
        st.caption("Evidence and source-linked records across the company profile.")
        rels=related_tables(entity_id,entity_name)
        for (wb_label,sheet),sub in rels:
            if sheet in {"Overview","Companies","Defence Companies"}: continue
            with st.expander(f"{sheet} · {len(sub)} record(s)"):
                display_df(sub,120)

def entity_search_matches(q, limit=20):
    if ECAT.empty or not q: return pd.DataFrame()
    tokens=[t.lower() for t in re.findall(r"[\w&+.-]+",q) if len(t)>1]
    scores=[]
    for _,r in ECAT.iterrows():
        text=f"{r['name']} {r['kind']}".lower()
        s=sum(10 for t in tokens if t in text)
        if q.lower() in text: s+=30
        if s: scores.append((s,r["id"],r["name"],r["kind"]))
    scores.sort(reverse=True)
    return pd.DataFrame(scores[:limit],columns=["score","id","name","kind"])

def go_entity(eid):
    st.session_state["entity_pick"]=eid
    st.session_state["nav_page"]="Entity Explorer"


def _is_technical_value(v):
    s=str(v).strip()
    if not s:
        return True
    return bool(re.match(r"^(TXN|IDEAL|COMP|SRC|NEWS|REL|PROG|YARD|VESSEL|PORT|TERM|ASSET|EVENT|EVT|OBS|ELINK|NLINK|TALINK|APPROVAL|TXNST|VTX|CTRL)[_-]", s, re.I))

def _pretty_field_name(c):
    c=str(c)
    replacements={
        "Buyer Company":"Buyer",
        "Buyer Company ID":"Buyer",
        "Seller / Owner IDs":"Seller / Owner",
        "Investor / Buyer IDs":"Investor / Buyer",
        "Co-Investor / Partner IDs":"Co-Investor / Partner",
        "Target Company":"Target",
        "Target / Asset":"Target / Asset",
        "Announcement Date":"Announced",
        "Announced Date":"Announced",
        "Expected Close":"Expected close",
        "Actual Close":"Closed",
        "Completed / Effective Date":"Completed / effective",
        "Transaction Type":"Type",
        "Deal Type":"Type",
        "Enterprise Value":"Value",
        "Reported Value":"Value",
        "Regulatory Status":"Regulatory status",
        "Operating Control":"Operating control",
    }
    return replacements.get(c,c)

def _split_and_resolve_ids(v):
    """Resolve semicolon-delimited company/entity IDs into English labels."""
    s=str(v).strip()
    if not s: return ""
    parts=[x.strip() for x in re.split(r"[;|]",s) if x.strip()]
    if len(parts)>1:
        resolved=[label(x) if label(x)!=x else x for x in parts]
        return " · ".join(resolved)
    return label(s) if label(s)!=s else s

def readable_search_card(hit):
    row=result_row(hit)
    sheet=str(hit.sheet)

    # Select a human title by record type instead of falling back to the row ID.
    preferred_by_sheet={
        "Transactions V125":["Target Company","Transaction Type"],
        "Infra Deals":["Target / Asset","Deal Type"],
        "Contracts":["Contract Type","Programme","Customer"],
        "Sales & Delivery Routes":["Platform / Vessel","Programme","Customer"],
        "Vessel Transactions":["Vessel Name","Transaction Type"],
        "Events":["Title"],
        "News Registry":["Headline"],
        "Announcements":["Headline"],
        "Port Terminals":["Terminal / Facility"],
        "Ports":["Port / Facility"],
        "Shipyards":["Shipyard"],
        "Sample Vessels":["Vessel"],
        "Vessels":["Vessel Name"],
        "Systems":["System"],
    }
    title=""
    for c in preferred_by_sheet.get(sheet,[]):
        if c in row.index and str(row.get(c,"")).strip() and not _is_technical_value(row.get(c,"")):
            title=str(row.get(c)).strip()
            break
    if not title:
        title=label(str(hit.title)) if label(str(hit.title))!=str(hit.title) else str(hit.title)
    if _is_technical_value(title):
        # Last fallback: use first readable non-ID textual value.
        for c,v in row.items():
            if ID_RE.search(str(c)) or "url" in str(c).lower():
                continue
            sv=str(v).strip()
            if sv and not _is_technical_value(sv):
                title=sv
                break

    # Commercial-specific title enhancement.
    if sheet=="Transactions V125":
        buyer=_split_and_resolve_ids(row.get("Buyer Company ID",""))
        target=str(row.get("Target Company","")).strip()
        ttype=str(row.get("Transaction Type","")).strip()
        if buyer and target:
            title=f"{buyer} → {target}"
        elif target:
            title=target
        if ttype:
            subtitle=ttype
        else:
            subtitle="Corporate transaction"
    elif sheet=="Infra Deals":
        inv=_split_and_resolve_ids(row.get("Investor / Buyer IDs",""))
        target=str(row.get("Target / Asset","")).strip()
        dtype=str(row.get("Deal Type","")).strip()
        title=f"{inv} → {target}" if inv and target else (target or inv or title)
        subtitle=dtype or "Infrastructure deal"
    else:
        subtitle=sheet

    # Build concise, fully readable fields.
    pairs=[]
    priority=[
        "Buyer Company ID","Investor / Buyer IDs","Co-Investor / Partner IDs",
        "Seller / Owner IDs","Target Company","Target / Asset",
        "Transaction Type","Deal Type","Announcement Date","Announced Date",
        "Expected Close","Completed / Effective Date","Enterprise Value","Reported Value",
        "Currency","Stake %","Status","Regulatory Status","Operating Control",
        "Country / Region","Country","Customer","Contract Value","Contract Currency",
        "Programme","Platform / Vessel","Start Date","Event Family","Event Type",
        "Severity","Location"
    ]
    seen=set()
    for c in priority + list(row.index):
        if c in seen or c not in row.index:
            continue
        seen.add(c)
        if "url" in str(c).lower() or c in {"Transaction ID","Deal ID","Contract ID","Source ID","Event ID","News ID"}:
            continue
        v=str(row.get(c,"")).strip()
        if not v:
            continue
        if ID_RE.search(str(c)) or " IDs" in str(c):
            v=_split_and_resolve_ids(v)
            if not v or _is_technical_value(v):
                continue
        elif _is_technical_value(v):
            # raw implementation key in a non-ID field: omit
            continue
        fname=_pretty_field_name(c)
        if fname in {"Target"} and v==title:
            continue
        pairs.append((fname,v))
        if len(pairs)>=6:
            break

    # Clean HTML card; no markdown ** markers inside raw HTML.
    details="".join(
        f"<span class='pc-detail-label'>{c}:</span> <span class='pc-detail-value'>{v}</span>"
        + (" <span class='pc-sep'>·</span> " if i < len(pairs)-1 else "")
        for i,(c,v) in enumerate(pairs)
    )

    url=""
    for c,v in row.items():
        if "url" in str(c).lower() and str(v).strip().startswith("http"):
            url=str(v).strip().split("|")[0].strip()
            break
    source_html=f"<div class='pc-source'><a href='{url}' target='_blank' rel='noopener noreferrer'>Open source ↗</a></div>" if url else ""

    st.markdown(
        f"<div class='pc-card pc-search-card'>"
        f"<div class='pc-label'>{subtitle}</div>"
        f"<div class='pc-big'>{title}</div>"
        f"<div class='pc-search-details'>{details}</div>"
        f"{source_html}</div>",
        unsafe_allow_html=True
    )



def linked_company_button(company_id, key, label_text="Open company"):
    """Open a canonical company page when the referenced company exists."""
    cid=str(company_id or "").strip()
    if not cid:
        return
    companies=TABLES.get(("Core Entities","Companies"),pd.DataFrame())
    if companies.empty or "Company ID" not in companies.columns:
        return
    hit=companies[companies["Company ID"].astype(str).eq(cid)]
    if hit.empty:
        return
    if st.button(label_text,key=key,use_container_width=True):
        pc_set_drilldown("entity",cid,str(hit.iloc[0].get("Company","")),rerun=False)
        request_nav("Companies","company_pick_id",cid,str(hit.iloc[0].get("Company","")))
        st.rerun()

def clean_network_table(df, cols=None, height=280):
    """Human-readable table wrapper for Network pages."""
    if df is None or df.empty:
        st.info("No matching records.")
        return
    v=humanize_df(df.copy())
    if cols:
        cols=[c for c in cols if c in v.columns]
        if cols:
            v=v[cols]
    display_df(v,height)



def _norm_governance_name(v):
    s=str(v or "").strip().casefold()
    s=s.replace("&"," and ")
    s=re.sub(r"[^a-z0-9]+"," ",s)
    return re.sub(r"\s+"," ",s).strip()

def _resolve_entity_name(entity_id):
    eid=str(entity_id or "").strip()
    if not eid:
        return ""
    resolved=label(eid)
    if resolved and resolved != eid:
        return resolved
    # Fall back to System Entities, which includes authorities not yet promoted
    # into the core Companies table.
    se=TABLES.get(("Systems & Waterways","System Entities"),pd.DataFrame())
    if not se.empty and "Entity ID" in se.columns:
        hit=se[se["Entity ID"].astype(str).eq(eid)]
        if not hit.empty:
            return str(hit.iloc[0].get("Entity","") or eid)
    return eid

def _canonical_company_id_for_governance(entity_id, entity_name=""):
    """Return a core Company ID only when the governance entity is actually canonical there."""
    companies=TABLES.get(("Core Entities","Companies"),pd.DataFrame())
    if companies.empty or "Company ID" not in companies.columns:
        return ""
    eid=str(entity_id or "").strip()
    if eid and not companies[companies["Company ID"].astype(str).eq(eid)].empty:
        return eid
    name=_norm_governance_name(entity_name)
    if name and "Company" in companies.columns:
        for _,r in companies.iterrows():
            if _norm_governance_name(r.get("Company","")) == name:
                return str(r.get("Company ID","") or "")
    return ""

def port_governance_rows(port_row):
    """Resolve governance rows for the selected port without inventing authority relationships."""
    gov=TABLES.get(("Systems & Waterways","Port Governance"),pd.DataFrame()).copy()
    if gov.empty:
        return gov

    pid=str(port_row.get("Port ID","") or "").strip()
    pname=str(port_row.get("Port / Facility","") or "").strip()
    pnorm=_norm_governance_name(pname)

    # Match by direct ID first.
    mask=pd.Series(False,index=gov.index)
    if "Port/System Entity ID" in gov.columns and pid:
        mask |= gov["Port/System Entity ID"].astype(str).eq(pid)

    # Resolve legacy/system IDs through the label registry and System Entities.
    if "Port/System Entity ID" in gov.columns and pnorm:
        for idx,gid in gov["Port/System Entity ID"].fillna("").astype(str).items():
            if mask.loc[idx]:
                continue
            gname=_resolve_entity_name(gid)
            if _norm_governance_name(gname) == pnorm:
                mask.loc[idx]=True

    return gov[mask].copy()

def render_port_governance(port_row):
    """Trade-facing governance/authority layer for a canonical port."""
    st.markdown("### Governance & authority")
    gov=port_governance_rows(port_row)

    if gov.empty:
        st.caption("No dedicated governance/authority record has been mapped for this port yet.")
        return

    for n,(_,r) in enumerate(gov.iterrows()):
        aid=str(r.get("Authority/Governing Entity ID","") or "").strip()
        aname=_resolve_entity_name(aid)
        role=pretty_relationship(r.get("Governance Role",""))
        note=str(r.get("Model Note","") or "").strip()
        src=str(r.get("Source URL","") or "").strip()

        c1,c2=st.columns([5,1])
        with c1:
            st.markdown(f"**{aname}**")
            if role and role.lower()!="nan":
                st.caption(role)
            if note and note.lower()!="nan":
                st.caption(note)

        with c2:
            cid=_canonical_company_id_for_governance(aid,aname)
            if cid:
                if st.button("Open entity",key=f"portgov_{port_row.get('Port ID','')}_{aid}_{n}",use_container_width=True):
                    request_nav("Companies","company_pick_id",cid,aname)
                    st.rerun()

        if src.startswith("http"):
            st.link_button("Authority source ↗",src,key=f"portgovsrc_{port_row.get('Port ID','')}_{aid}_{n}")

def render_system_governance():
    """Expose authorities and governance models across ports/waterways/systems."""
    gov=TABLES.get(("Systems & Waterways","Port Governance"),pd.DataFrame()).copy()
    se=TABLES.get(("Systems & Waterways","System Entities"),pd.DataFrame()).copy()
    waterways=TABLES.get(("Systems & Waterways","Waterway Systems"),pd.DataFrame()).copy()
    locks=TABLES.get(("Systems & Waterways","Locks & Canals"),pd.DataFrame()).copy()

    tabs=st.tabs(["Authorities & governance","Waterways","Locks & canals"])
    with tabs[0]:
        if gov.empty:
            st.info("No governance records available.")
        else:
            v=gov.copy()
            if "Port/System Entity ID" in v.columns:
                v["Port / system"] = v["Port/System Entity ID"].map(_resolve_entity_name)
            if "Authority/Governing Entity ID" in v.columns:
                v["Authority / governing entity"] = v["Authority/Governing Entity ID"].map(_resolve_entity_name)
            if "Governance Role" in v.columns:
                v["Governance role"] = v["Governance Role"].map(pretty_relationship)
            cols=[c for c in ["Port / system","Authority / governing entity","Governance role","Model Note","Source URL"] if c in v.columns]
            display_df(v[cols] if cols else v,320)
    with tabs[1]:
        clean_network_table(waterways,["Waterway","Type","Trade Function"],260)
    with tabs[2]:
        clean_network_table(locks,["Waterway","Facility","Type","Country/Operator"],300)


def request_nav(page_name, object_key=None, object_id=None, object_name=None):
    """Defer a page/object jump until the next Streamlit rerun.
    Destination pages consume *_pick_id requests before their selector widget is created.
    """
    st.session_state["nav_request"]=page_name
    if object_key and object_id:
        # Never write directly into a selector widget key here.
        # Store the requested canonical object ID separately.
        st.session_state[object_key]=str(object_id)
    if object_name:
        st.session_state["object_name_hint"]=str(object_name)

def object_route(entity_type, entity_id, entity_name):
    et=str(entity_type or "").lower(); eid=str(entity_id or "").strip(); name=str(entity_name or "").strip()
    if et in {"entity","organisation","organization","company","person","individual"} or eid.startswith(("ENTITY_","ENT_","COMP","PERSON_")):
        if _entity_kind(eid,et)=="company": return ("Companies","company_pick_id",eid)
        return (None,None,None)
    if "port" in et or eid.startswith("PORT"): return ("Ports","port_pick_id",eid)
    if "terminal" in et or eid.startswith("TERM"): return ("Ports","terminal_pick_id",eid)
    if "shipyard" in et or eid.startswith("YARD"): return ("Shipyards","yard_pick_id",eid)
    if "system" in et or "corridor" in et or eid.startswith(("SYS","CORR")): return ("Corridors & Systems","system_pick_id",eid)
    if "rail" in et: return ("Rail","rail_pick_id",eid)
    if et=="asset" or eid.startswith("ASSET_"): return ("Infrastructure","asset_pick_id",eid)
    if "vessel" in et or "mobile_asset" in et or eid.startswith(("VESSEL","VES","MOBILE_","MOB_")): return ("Vessels","vessel_pick_id",eid)
    return (None,None,None)


def render_relationship_actions(
    source_id, target_id, row_key, current_entity_id=None,
    source_name=None, target_name=None, source_type=None, target_type=None
):
    actions=[]; seen=set()
    for endpoint_id,resolved_name,endpoint_type in [(source_id,source_name,source_type),(target_id,target_name,target_type)]:
        eid=str(endpoint_id or "").strip()
        if not eid or eid in seen or (current_entity_id and eid==str(current_entity_id)): continue
        seen.add(eid)
        name=relationship_endpoint_label(eid,endpoint_type)
        if not name or name=="Unresolved entity": continue
        page,key,route_id=object_route(endpoint_type or '',eid,name)
        if not page: continue
        if page=='Companies': kind='Company'
        elif page=='Ports' and ("terminal" in str(endpoint_type or '').lower() or eid.startswith('TERM')): kind='Terminal'
        elif page=='Ports': kind='Port'
        elif page=='Vessels': kind='Vessel'
        elif page=='Shipyards': kind='Shipyard'
        elif page=='Corridors & Systems': kind='System / corridor'
        elif page=='Rail': kind='Rail object'
        else: kind='Object'
        actions.append((f"View {kind}: {name}",page,key,route_id,name,eid))
    if actions:
        cols=st.columns(min(len(actions),3))
        for j,(caption,page,key,route_id,name,eid) in enumerate(actions):
            with cols[j % len(cols)]:
                if st.button(caption,key=f"rel_action_{row_key}_{j}_{eid}",use_container_width=True):
                    request_nav(page,key,route_id,name); st.rerun()


def render_linked_objects(df, object_type_col, object_id_col, object_name_col, relationship_col=None, confidence_col=None, max_items=100):
    """Render linked graph objects as readable, navigable cards instead of dead dataframe rows."""
    if df is None or df.empty:
        st.info("No linked objects.")
        return

    for i,(_,r) in enumerate(df.head(max_items).iterrows()):
        otype=str(r.get(object_type_col,"")).strip()
        oid=str(r.get(object_id_col,"")).strip()
        oname=str(r.get(object_name_col,"")).strip() or label(oid)
        rel=pretty_relationship(r.get(relationship_col,"")) if relationship_col else ""
        conf=str(r.get(confidence_col,"")).strip() if confidence_col else ""

        route_page,route_key,route_id=object_route(otype,oid,oname)
        meta=[x for x in [pretty_enum(otype),rel,(f"Confidence: {conf}" if conf else "")] if x]

        c1,c2=st.columns([5,1])
        with c1:
            st.markdown(
                f"<div class='pc-card pc-object-card'>"
                f"<div class='pc-label'>{' · '.join(meta)}</div>"
                f"<div class='pc-big'>{oname}</div>"
                f"</div>",
                unsafe_allow_html=True
            )
        with c2:
            if route_page:
                if st.button("Open",key=f"objopen_{route_page}_{oid}_{i}",use_container_width=True):
                    request_nav(route_page,route_key,route_id,oname)
                    st.rerun()
            else:
                st.caption("Linked object")

def safe_index_state(key, default_index, option_count):
    """Normalize stale Streamlit widget state from older app versions.
    Selectbox index widgets must always contain an int in range.
    """
    try:
        current=st.session_state.get(key,default_index)
        current=int(current)
    except (TypeError,ValueError):
        current=int(default_index)

    if current < 0 or current >= int(option_count):
        current=int(default_index)

    st.session_state[key]=current
    return current


def sanctions_lookup_maps():
    auth=TABLES.get(("Trade Policy & Compliance","Sanctions Authorities"),pd.DataFrame())
    prog=TABLES.get(("Trade Policy & Compliance","Sanctions Programmes"),pd.DataFrame())
    des=TABLES.get(("Trade Policy & Compliance","Sanctions Designations"),pd.DataFrame())

    auth_map={}
    prog_map={}
    des_map={}
    if not auth.empty:
        for _,r in auth.iterrows():
            aid=str(r.get("Authority ID","")).strip()
            if aid:
                auth_map[aid]=str(r.get("Authority","")).strip()
    if not prog.empty:
        for _,r in prog.iterrows():
            pid=str(r.get("Programme ID","")).strip()
            name=str(r.get("Programme","")).strip()
            legal=str(r.get("Legal Basis","")).strip()
            if pid:
                prog_map[pid]=f"{name} — {legal}" if legal else name
    if not des.empty:
        for _,r in des.iterrows():
            did=str(r.get("Designation ID","")).strip()
            target=str(r.get("Target Name","")).strip()
            if did:
                des_map[did]=target
    return auth_map,prog_map,des_map

SAN_AUTH_MAP,SAN_PROG_MAP,SAN_DES_MAP=sanctions_lookup_maps()

def humanize_sanctions_df(df):
    if df is None or df.empty:
        return pd.DataFrame()
    out=df.copy()

    if "Authority ID" in out.columns:
        out["Authority"]=out["Authority ID"].astype(str).map(lambda x:SAN_AUTH_MAP.get(x,x))
    if "Programme ID" in out.columns:
        out["Programme"]=out["Programme ID"].astype(str).map(lambda x:SAN_PROG_MAP.get(x,x))
    if "Designation ID" in out.columns and "Target Name" not in out.columns:
        out["Designation"]=out["Designation ID"].astype(str).map(lambda x:SAN_DES_MAP.get(x,x))

    for c in list(out.columns):
        if c in {"Status","Target Type","Entity Type","Coverage Status","Classification Rule","Legal / Analytical Effect","Authority Type","Class","Measure Type","Precedence"}:
            out[c]=out[c].map(pretty_enum)

    drop=[
        "Designation ID","Authority ID","Programme ID","Link ID","Watch ID","Rule ID",
        "Canonical Entity ID","Coverage ID","Measure ID","Party Link ID","Source ID"
    ]
    out=out.drop(columns=[c for c in drop if c in out.columns],errors="ignore")

    preferred=[
        "Designation Date","Target Type","Target Name","IMO / Identifier","Authority","Programme",
        "Regime / Linkage","Status","Designation Basis / Link","Model Coverage Status","Source URL",
        "Entity","Entity Type","Designation","Coverage Status","Confidence","Analytical Note",
        "Class","Example","Authority Type","Classification Rule","Legal / Analytical Effect"
    ]
    cols=[c for c in preferred if c in out.columns]+[c for c in out.columns if c not in preferred]
    return out[cols]

def sanctions_programme_counts(designations):
    if designations is None or designations.empty or "Programme ID" not in designations.columns:
        return pd.DataFrame()
    x=designations.copy()
    x["Programme"]=x["Programme ID"].astype(str).map(lambda p:SAN_PROG_MAP.get(p,p))
    return x["Programme"].value_counts().rename_axis("Programme").reset_index(name="Designations")

def render_dark_bar_list(df,label_col,value_col,title):
    st.markdown(f"### {title}")
    if df is None or df.empty:
        st.info("No records.")
        return
    maxv=max(float(pd.to_numeric(df[value_col],errors="coerce").fillna(0).max()),1.0)
    for _,r in df.iterrows():
        label_txt=str(r.get(label_col,""))
        try: val=float(r.get(value_col,0))
        except Exception: val=0.0
        pct=max(2,min(100,(val/maxv)*100))
        value_txt=str(int(val)) if float(val).is_integer() else str(val)
        st.markdown(
            f"<div class='pc-bar-row'>"
            f"<div class='pc-bar-label'>{label_txt}</div>"
            f"<div class='pc-bar-track'><div class='pc-bar-fill' style='width:{pct}%'></div></div>"
            f"<div class='pc-bar-value'>{value_txt}</div>"
            f"</div>",
            unsafe_allow_html=True
        )

def render_sanction_link_cards(df):
    if df is None or df.empty:
        st.info("No sanction-linked entities.")
        return
    for i,(_,r) in enumerate(df.iterrows()):
        entity=str(r.get("Entity","")).strip()
        etype=str(r.get("Entity Type","")).strip()
        canonical=str(r.get("Canonical Entity ID","")).strip()
        status=str(r.get("Coverage Status","")).strip()
        designation=str(r.get("Designation ID","")).strip()
        designation_name=SAN_DES_MAP.get(designation,designation)
        note=str(r.get("Analytical Note","")).strip()

        c1,c2=st.columns([5,1])
        with c1:
            st.markdown(
                f"<div class='pc-card pc-object-card'>"
                f"<div class='pc-label'>{pretty_enum(etype)} · linked to {designation_name}</div>"
                f"<div class='pc-big'>{entity}</div>"
                f"<div class='pc-small'>{status}{(' · '+note) if note else ''}</div>"
                f"</div>",
                unsafe_allow_html=True
            )
        with c2:
            if canonical:
                page,key,_=object_route(etype,canonical,entity)
                if page:
                    if st.button("Open",key=f"sanopen_{i}_{canonical}",use_container_width=True):
                        request_nav(page,key,canonical,entity)
                        st.rerun()
                else:
                    st.caption("Linked")
            else:
                st.caption("Not canonical")


def vessel_value(r, *cols):
    for c in cols:
        v=str(r.get(c,"")).strip()
        if v and v.lower() not in {"nan","none"}:
            return pretty_enum(v)
    return ""

def vessel_summary_cards(r):
    cards=[
        ("IMO",vessel_value(r,"IMO")),
        ("Type",vessel_value(r,"Vessel Type")),
        ("Flag",vessel_value(r,"Flag")),
        ("Built",vessel_value(r,"Year Built")),
        ("DWT",vessel_value(r,"DWT")),
        ("GT",vessel_value(r,"Gross Tonnage (GT)")),
    ]
    cols=st.columns(3)
    for i,(lab,val) in enumerate(cards):
        if not val:
            val="—"
        with cols[i%3]:
            st.markdown(
                f"<div class='pc-card'><div class='pc-label'>{lab}</div>"
                f"<div class='pc-big'>{val}</div></div>",
                unsafe_allow_html=True
            )

def render_vessel_relationship_cards(vessel_id,vessel_name,rel,key_scope):
    if rel is None or rel.empty:
        st.info("No linked owner/operator/manager records.")
        return
    for i,(_,rr) in enumerate(rel.iterrows()):
        cid=str(rr.get("Company ID","")).strip()
        cname=label(cid)
        relationship=pretty_relationship(rr.get("Relationship Type",""))
        notes=str(rr.get("Notes","")).strip()
        c1,c2=st.columns([5,1])
        with c1:
            st.markdown(
                f"<div class='pc-card pc-object-card'>"
                f"<div class='pc-label'>{relationship}</div>"
                f"<div class='pc-big'>{cname}</div>"
                f"<div class='pc-small'>{notes}</div>"
                f"</div>",
                unsafe_allow_html=True
            )
        with c2:
            if cid.startswith("COMP_"):
                if st.button(f"Open {cname}",key=f"vrel_open_{key_scope}_{vessel_id}_{i}_{cid}",use_container_width=True):
                    request_nav("Companies","company_pick_id",cid,cname)
                    st.rerun()

def render_vessel_incident_cards(events,news):
    frames=[]
    if events is not None and not events.empty:
        for _,r in events.iterrows():
            frames.append({
                "Date":str(r.get("Date","")).strip(),
                "Title":str(r.get("Title","")).strip(),
                "Type":str(r.get("Event Type","")).strip(),
                "Location":str(r.get("Location","")).strip(),
                "Impact":str(r.get("Operational Impact","")).strip(),
                "Source URL":"",
            })
    if news is not None and not news.empty:
        for _,r in news.iterrows():
            # Avoid duplicating a news story already represented by same headline/date.
            frames.append({
                "Date":str(r.get("Published Date","")).strip(),
                "Title":str(r.get("Headline","")).strip(),
                "Type":str(r.get("Event Type","")).strip(),
                "Location":str(r.get("Region","")).strip(),
                "Impact":str(r.get("Summary","")).strip(),
                "Source URL":str(r.get("URL","")).strip(),
            })
    if not frames:
        st.info("No linked incident or enforcement history.")
        return
    df=pd.DataFrame(frames)
    df["_dt"]=pd.to_datetime(df["Date"],errors="coerce")
    df=df.sort_values("_dt",ascending=False).drop_duplicates(subset=["Date","Title"])
    for i,(_,r) in enumerate(df.iterrows()):
        src=str(r.get("Source URL","")).strip()
        source_html=f"<div class='pc-source'><a href='{src}' target='_blank' rel='noopener noreferrer'>Open source ↗</a></div>" if src.startswith("http") else ""
        st.markdown(
            f"<div class='pc-card'>"
            f"<div class='pc-label'>{r.get('Date','')} · {pretty_enum(r.get('Type',''))} · {r.get('Location','')}</div>"
            f"<div class='pc-big'>{r.get('Title','')}</div>"
            f"<div class='pc-small'>{r.get('Impact','')}</div>"
            f"{source_html}</div>",
            unsafe_allow_html=True
        )

def _norm_imo(value):
    """Return a clean IMO string for matching across Excel and official-source tables."""
    txt=str(value or "").strip()
    if txt.endswith(".0"):
        txt=txt[:-2]
    digits="".join(ch for ch in txt if ch.isdigit())
    return digits


def official_maritime_incidents():
    return TABLES.get(("Official Maritime Security","IMO Middle East Incidents"),pd.DataFrame()).copy()


def canonical_vessel_id_for_official_incident(imo, vessel_name=""):
    vessels=TABLES.get(("Maritime","Vessels"),pd.DataFrame())
    imo_key=_norm_imo(imo)
    if not vessels.empty:
        if imo_key and "IMO" in vessels.columns:
            matches=vessels[vessels["IMO"].map(_norm_imo).eq(imo_key)]
            if not matches.empty and "Vessel ID" in matches.columns:
                return str(matches.iloc[0].get("Vessel ID","")).strip()
        if vessel_name and "Vessel Name" in vessels.columns:
            name_key=str(vessel_name).strip().casefold()
            matches=vessels[vessels["Vessel Name"].astype(str).str.strip().str.casefold().eq(name_key)]
            if not matches.empty and "Vessel ID" in matches.columns:
                return str(matches.iloc[0].get("Vessel ID","")).strip()
    if imo_key:
        return f"VES_IMO_{imo_key}"
    safe="_".join(str(vessel_name or "UNKNOWN").upper().split())
    return f"VES_IMO_SOURCE_{safe}"


def commercial_vessels_with_official_stubs():
    """Expose every IMO-confirmed vessel as a canonical-like object in the legacy Excel UI.

    Existing canonical vessels keep their IDs and metadata.  IMO-only vessels get a minimal
    in-memory stub so an official security record is always navigable to a vessel profile.
    """
    vessels=TABLES.get(("Maritime","Vessels"),pd.DataFrame()).copy()
    inc=official_maritime_incidents()
    if inc.empty:
        return vessels
    cols=list(vessels.columns) if not vessels.empty else ["Vessel ID","Vessel Name","IMO","Vessel Type","Status","Source ID","Completeness Note"]
    rows=[]
    existing_ids=set(vessels["Vessel ID"].astype(str)) if not vessels.empty and "Vessel ID" in vessels.columns else set()
    existing_imos=set(vessels["IMO"].map(_norm_imo)) if not vessels.empty and "IMO" in vessels.columns else set()
    for _,r in inc.iterrows():
        imo=_norm_imo(r.get("IMO",""))
        vid=canonical_vessel_id_for_official_incident(imo,r.get("Vessel",""))
        if vid in existing_ids or (imo and imo in existing_imos):
            continue
        item={c:"" for c in cols}
        item.update({
            "Vessel ID":vid,
            "Vessel Name":str(r.get("Vessel","")).strip(),
            "IMO":imo,
            "Status":"Official maritime-security incident record",
            "Source ID":"IMO_MIDDLE_EAST_CONFIRMED_INCIDENTS",
            "Completeness Note":"Minimal legacy-app vessel stub created from an IMO-confirmed incident; enrich owner/operator/type from canonical sources.",
        })
        rows.append(item)
        existing_ids.add(vid)
        if imo: existing_imos.add(imo)
    if rows:
        vessels=pd.concat([vessels,pd.DataFrame(rows)],ignore_index=True,sort=False)
    return vessels


def official_security_for_vessel(vessel_id, vessel_name="", imo=""):
    inc=official_maritime_incidents()
    if inc.empty:
        return inc
    imo_key=_norm_imo(imo)
    if not imo_key:
        vessels=commercial_vessels_with_official_stubs()
        if not vessels.empty and "Vessel ID" in vessels.columns:
            m=vessels[vessels["Vessel ID"].astype(str).eq(str(vessel_id))]
            if not m.empty:
                imo_key=_norm_imo(m.iloc[0].get("IMO",""))
                if not vessel_name:
                    vessel_name=str(m.iloc[0].get("Vessel Name",""))
    mask=pd.Series(False,index=inc.index)
    if imo_key and "IMO" in inc.columns:
        mask=mask | inc["IMO"].map(_norm_imo).eq(imo_key)
    if vessel_name and "Vessel" in inc.columns:
        mask=mask | inc["Vessel"].astype(str).str.strip().str.casefold().eq(str(vessel_name).strip().casefold())
    return inc[mask].copy()


def render_official_security_records(records, key_scope="official_security"):
    if records is None or records.empty:
        st.info("No IMO-confirmed maritime-security incident linked to this vessel.")
        return
    for i,(_,r) in enumerate(records.iterrows()):
        vessel=str(r.get("Vessel","")).strip()
        imo=_norm_imo(r.get("IMO",""))
        vid=canonical_vessel_id_for_official_incident(imo,vessel)
        date=str(r.get("Date (2026)","")).strip()
        location=str(r.get("Location","")).strip()
        desc=str(r.get("Description","")).strip()
        authority=str(r.get("Confirming Authority","International Maritime Organization")).strip()
        src=str(r.get("Source URL","")).strip()
        st.markdown(
            f"<div class='pc-card'><div class='pc-label'>{date} · {location}</div>"
            f"<div class='pc-big'>{vessel} · IMO {imo}</div>"
            f"<div class='pc-small'>{desc}</div>"
            f"<div class='pc-small'>Confirmed by {authority}</div></div>",
            unsafe_allow_html=True
        )
        c1,c2=st.columns([1,4])
        with c1:
            if st.button("Open vessel",key=f"{key_scope}_open_{vid}_{i}",use_container_width=True):
                st.session_state["vessel_pick_id"]=vid
                st.session_state["nav_request"]="Vessels"
                st.rerun()
        with c2:
            if src.startswith("http"):
                st.markdown(f"[IMO source ↗]({src})")


def vessel_profile_data(vessel_id, vessel_name):
    commercial=commercial_vessels_with_official_stubs()
    vrel=TABLES.get(("Maritime","Vessel Relationships"),pd.DataFrame())
    evid=TABLES.get(("Maritime","Vessel Evidence"),pd.DataFrame())
    build=TABLES.get(("Maritime","Vessel Build Records"),pd.DataFrame())
    news=TABLES.get(("Intelligence","News Registry"),pd.DataFrame())
    nlinks=TABLES.get(("Intelligence","News Entity Links"),pd.DataFrame())
    events=TABLES.get(("Intelligence","Strategic Events"),pd.DataFrame())
    sanctions=TABLES.get(("Trade Policy & Compliance","Sanctions Designations"),pd.DataFrame())

    row=commercial[commercial["Vessel ID"].astype(str).eq(str(vessel_id))].copy() if not commercial.empty and "Vessel ID" in commercial.columns else pd.DataFrame()
    rel=vrel[vrel["Vessel ID"].astype(str).eq(str(vessel_id))].copy() if not vrel.empty and "Vessel ID" in vrel.columns else pd.DataFrame()
    evd=evid[evid["Vessel ID"].astype(str).eq(str(vessel_id))].copy() if not evid.empty and "Vessel ID" in evid.columns else pd.DataFrame()
    bld=build[build["Vessel ID"].astype(str).eq(str(vessel_id))].copy() if not build.empty and "Vessel ID" in build.columns else pd.DataFrame()

    nids=set()
    if not nlinks.empty and "Entity ID" in nlinks.columns:
        nl=nlinks[nlinks["Entity ID"].astype(str).eq(str(vessel_id))]
        if "News ID" in nl.columns: nids.update(nl["News ID"].astype(str).tolist())
    n=news[news["News ID"].astype(str).isin(nids)].copy() if nids and not news.empty and "News ID" in news.columns else pd.DataFrame()

    # Strategic events can reach a vessel either as the primary subject OR through Event Entity Links.
    event_ids=set()
    if not events.empty and "Subject Entity ID" in events.columns and "Event ID" in events.columns:
        direct=events[events["Subject Entity ID"].astype(str).eq(str(vessel_id))]
        event_ids.update(direct["Event ID"].astype(str).tolist())

    intel_links=TABLES.get(("Intelligence","Event Entity Links"),pd.DataFrame())
    if not intel_links.empty and "Entity ID" in intel_links.columns:
        linked=intel_links[intel_links["Entity ID"].astype(str).eq(str(vessel_id))].copy()
        for c in ["Canonical Event ID","Event ID"]:
            if c in linked.columns:
                event_ids.update(x for x in linked[c].astype(str).tolist() if x and x!="nan")

    ev=events[events["Event ID"].astype(str).isin(event_ids)].copy() if event_ids and not events.empty and "Event ID" in events.columns else pd.DataFrame()

    # Unified Events & Hazards links are a second source of live-event attachment.
    unified_events=TABLES.get(("Events & Hazards","Events"),pd.DataFrame())
    unified_links=TABLES.get(("Events & Hazards","Event Asset Links"),pd.DataFrame())
    uids=set()
    if not unified_links.empty and "Asset ID" in unified_links.columns and "Event ID" in unified_links.columns:
        ul=unified_links[unified_links["Asset ID"].astype(str).eq(str(vessel_id))]
        uids.update(ul["Event ID"].astype(str).tolist())

    unified=pd.DataFrame()
    if uids and not unified_events.empty and "Event ID" in unified_events.columns:
        unified=unified_events[unified_events["Event ID"].astype(str).isin(uids)].copy()
        if not unified.empty:
            # Convert unified event rows into the Strategic Events shape used by the vessel UI.
            mapped=[]
            for _,ur in unified.iterrows():
                mapped.append({
                    "Event ID":str(ur.get("Event ID","")).strip(),
                    "Date":str(ur.get("Start Date",ur.get("Date",""))).strip(),
                    "Event Type":str(ur.get("Event Family","")).strip() or str(ur.get("Event Type","")).strip(),
                    "Subject Entity ID":str(vessel_id),
                    "Location":str(ur.get("Location","")).strip(),
                    "Title":str(ur.get("Title","")).strip(),
                    "Description":str(ur.get("Description","")).strip(),
                    "Operational Impact":str(ur.get("Operational Impact",ur.get("Direct Impact",""))).strip(),
                    "Financial / Strategic Impact":str(ur.get("Trade / Commercial Impact",ur.get("Strategic / Commercial Outcome",""))).strip(),
                    "Source ID":str(ur.get("Source ID","")).strip(),
                })
            unified=pd.DataFrame(mapped)

    if not unified.empty:
        ev=pd.concat([ev,unified],ignore_index=True,sort=False)
        if "Event ID" in ev.columns:
            ev=ev.drop_duplicates(subset=["Event ID"])

    san=sanctions[sanctions["Canonical Entity ID"].astype(str).eq(str(vessel_id))].copy() if not sanctions.empty and "Canonical Entity ID" in sanctions.columns else pd.DataFrame()

    return row,rel,evd,bld,n,ev,san

def render_vessel_profile(vessel_id,vessel_name):
    row,rel,evd,bld,news,events,san=vessel_profile_data(vessel_id,vessel_name)
    if row.empty:
        st.info("No canonical commercial-vessel record available.")
        return

    r=row.iloc[0]

    # Header
    st.markdown(f"## {vessel_name}")
    subtitle_bits=[]
    for c in ["Vessel Type","Subtype / Class","Flag","Status"]:
        v=vessel_value(r,c)
        if v: subtitle_bits.append(v)
    if subtitle_bits:
        st.caption(" · ".join(subtitle_bits))

    vessel_summary_cards(r)

    c1,c2,c3,c4,c5=st.columns(5)
    c1.metric("Sanctions",len(san))
    c2.metric("Incidents",len(events))
    c3.metric("News",len(news))
    c4.metric("Companies",rel["Company ID"].nunique() if not rel.empty and "Company ID" in rel.columns else 0)
    c5.metric("Evidence",len(evd))

    tabs=st.tabs([
        "Overview",
        "Ownership & Management",
        "Transport Services & Exposure",
        "Maritime Security & Compliance",
        "Sanctions",
        "Incidents",
        "News",
        "Evidence"
    ])

    with tabs[0]:
        st.markdown("### Vessel profile")
        fields=[
            ("IMO","IMO"),
            ("MMSI","MMSI"),
            ("Call sign","Call Sign"),
            ("Vessel type","Vessel Type"),
            ("Class / subtype","Subtype / Class"),
            ("Flag","Flag"),
            ("Year built","Year Built"),
            ("DWT","DWT"),
            ("Gross tonnage","Gross Tonnage (GT)"),
            ("Length","Length (m)"),
            ("Beam","Beam (m)"),
            ("Primary service","Primary Service"),
            ("Status","Status"),
            ("Owner / operator","Owner / Operator Text"),
            ("Notes","Notes"),
        ]
        rows=[]
        for lab,col in fields:
            val=vessel_value(r,col)
            if val:
                rows.append({"Field":lab,"Value":val})
        if rows:
            display_df(pd.DataFrame(rows),100)

        if not rel.empty:
            st.markdown("### Connected companies")
            render_vessel_relationship_cards(vessel_id,vessel_name,rel,"overview")

        if not san.empty:
            st.markdown("### Compliance flag")
            st.warning(f"{len(san)} government sanctions designation record(s) are linked to this vessel.")

        if not events.empty or not news.empty:
            st.markdown("### Latest incident / reporting")
            render_vessel_incident_cards(events.head(2) if not events.empty else events,
                                         news.head(2) if not news.empty else news)

        if not bld.empty:
            st.markdown("### Build record")
            display_df(bld,20)

    with tabs[1]:
        st.markdown("### Owner / operator / manager relationships")
        render_vessel_relationship_cards(vessel_id,vessel_name,rel,"ownership")

    with tabs[2]:
        render_vessel_connected_model(vessel_id)

    with tabs[3]:
        official=official_security_for_vessel(vessel_id,vessel_name,vessel_value(r,"IMO"))
        if not official.empty:
            st.markdown("### IMO-confirmed maritime-security incidents")
            render_official_security_records(official,f"vessel_security_{vessel_id}")
        sec=security_vessel_bundle(vessel_id,vessel_name,vessel_value(r,"IMO"))
        if sec["designations"].empty and sec["exposure"].empty and sec["restrictions"].empty:
            if official.empty:
                st.info("No operational compliance or maritime-security restriction is linked to this vessel.")
        else:
            if not sec["designations"].empty:
                st.markdown("### Compliance designations")
                display_df(sec["designations"],100)
            if not sec["exposure"].empty:
                st.markdown("### Secondary / counterparty exposure")
                display_df(sec["exposure"],100)
            if not sec["restrictions"].empty:
                st.markdown("### Vessel restriction records")
                display_df(sec["restrictions"],100)

    with tabs[4]:
        if san.empty:
            st.info("No government sanctions designation linked to this canonical vessel.")
        else:
            st.markdown("### Government designation records")
            display_df(humanize_sanctions_df(san),100)

            # Related sanction-linked companies / entities
            slinks=TABLES.get(("Trade Policy & Compliance","Sanctions Entity Links"),pd.DataFrame())
            if not slinks.empty and "Designation ID" in slinks.columns and "Designation ID" in san.columns:
                dids=set(san["Designation ID"].astype(str))
                linked=slinks[slinks["Designation ID"].astype(str).isin(dids)].copy()
                linked=linked[linked["Canonical Entity ID"].astype(str).ne(str(vessel_id))] if "Canonical Entity ID" in linked.columns else linked
                if not linked.empty:
                    st.markdown("### Related sanction-linked entities")
                    render_sanction_link_cards(linked)

    with tabs[5]:
        render_vessel_incident_cards(events,news)

    with tabs[6]:
        if not news.empty:
            show_named_list(news,"Headline",["Published Date","Publisher","Region","Event Type"],source_col="URL",max_items=100)
        else:
            st.info("No linked news reporting.")

    with tabs[7]:
        if not evd.empty:
            st.markdown("### Vessel evidence")
            display_df(evd,150)
        else:
            st.info("No vessel evidence records.")
        if not bld.empty:
            st.markdown("### Build evidence")
            display_df(bld,50)


def defence_vessel_profile_data(vessel_id):
    vessels=TABLES.get(("Defence & Shipbuilding","Sample Vessels"),pd.DataFrame())
    programmes=TABLES.get(("Defence & Shipbuilding","Programmes"),pd.DataFrame())
    participants=TABLES.get(("Defence & Shipbuilding","Programme Participants"),pd.DataFrame())
    contracts=TABLES.get(("Defence & Shipbuilding","Contracts"),pd.DataFrame())
    yards=TABLES.get(("Defence & Shipbuilding","Shipyards"),pd.DataFrame())
    announcements=TABLES.get(("Defence & Shipbuilding","Announcements"),pd.DataFrame())
    routes=TABLES.get(("Defence & Shipbuilding","Sales & Delivery Routes"),pd.DataFrame())
    classes=TABLES.get(("Defence & Shipbuilding","Platform Classes"),pd.DataFrame())
    history=TABLES.get(("Defence & Shipbuilding","Vessel Status History"),pd.DataFrame())

    row=vessels[vessels["Vessel ID"].astype(str).eq(str(vessel_id))].copy() if not vessels.empty and "Vessel ID" in vessels.columns else pd.DataFrame()
    if row.empty:
        return tuple(pd.DataFrame() for _ in range(9))

    pid=str(row.iloc[0].get("Programme ID","")).strip()
    yid=str(row.iloc[0].get("Build Yard ID","")).strip()

    pg=programmes[programmes["Programme ID"].astype(str).eq(pid)].copy() if pid and not programmes.empty and "Programme ID" in programmes.columns else pd.DataFrame()
    pp=participants[participants["Programme ID"].astype(str).eq(pid)].copy() if pid and not participants.empty and "Programme ID" in participants.columns else pd.DataFrame()
    con=contracts[contracts["Programme ID"].astype(str).eq(pid)].copy() if pid and not contracts.empty and "Programme ID" in contracts.columns else pd.DataFrame()
    yd=yards[yards["Yard ID"].astype(str).eq(yid)].copy() if yid and not yards.empty and "Yard ID" in yards.columns else pd.DataFrame()
    an=announcements[announcements["Programme ID"].astype(str).eq(pid)].copy() if pid and not announcements.empty and "Programme ID" in announcements.columns else pd.DataFrame()
    rt=routes[routes["Programme ID"].astype(str).eq(pid)].copy() if pid and not routes.empty and "Programme ID" in routes.columns else pd.DataFrame()
    cl=classes[classes["Programme ID"].astype(str).eq(pid)].copy() if pid and not classes.empty and "Programme ID" in classes.columns else pd.DataFrame()
    hs=history[history["Vessel ID"].astype(str).eq(str(vessel_id))].copy() if not history.empty and "Vessel ID" in history.columns else pd.DataFrame()
    return row,pg,pp,con,yd,an,rt,cl,hs

def render_defence_vessel_profile(vessel_id,vessel_name):
    row,pg,pp,con,yd,ann,rt,cl,hist=defence_vessel_profile_data(vessel_id)
    if row.empty:
        st.info("No defence / government vessel record.")
        return

    r=row.iloc[0]
    st.markdown(f"## {vessel_name}")
    bits=[str(r.get("Class / Type","")).strip(),str(r.get("Customer / Operator","")).strip(),str(r.get("Status","")).strip()]
    st.caption(" · ".join([pretty_enum(x) for x in bits if x]))

    c1,c2,c3,c4=st.columns(4)
    c1.metric("Programme",1 if not pg.empty else 0)
    c2.metric("Contracts",len(con))
    c3.metric("Milestones",len(hist))
    c4.metric("Announcements",len(ann))

    tabs=st.tabs(["Overview","Programme & Contract","Builder & Yard","Status History","News / Announcements","Evidence"])

    with tabs[0]:
        fields=[
            ("Class / type",r.get("Class / Type","")),
            ("Customer / operator",r.get("Customer / Operator","")),
            ("Status",r.get("Status","")),
            ("Build / delivery route",r.get("Build / Delivery Route","")),
        ]
        display_df(pd.DataFrame([{"Field":a,"Value":pretty_enum(b)} for a,b in fields if str(b).strip()]),50)
        if not cl.empty:
            st.markdown("### Platform class")
            display_df(cl,50)

    with tabs[1]:
        if not pg.empty:
            st.markdown("### Programme")
            display_df(pg,50)
        if not con.empty:
            st.markdown("### Contract")
            display_df(con,50)
        if not pp.empty:
            st.markdown("### Programme participants")
            for i,(_,pr) in enumerate(pp.iterrows()):
                eid=str(pr.get("Entity ID","")).strip()
                ename=label(eid)
                role=pretty_enum(pr.get("Role",""))
                notes=str(pr.get("Notes","")).strip()
                c1,c2=st.columns([5,1])
                with c1:
                    st.markdown(
                        f"<div class='pc-card pc-object-card'><div class='pc-label'>{role}</div>"
                        f"<div class='pc-big'>{ename}</div><div class='pc-small'>{notes}</div></div>",
                        unsafe_allow_html=True
                    )
                with c2:
                    if eid.startswith("COMP_"):
                        if st.button(f"Open {ename}",key=f"dvp_part_{vessel_id}_{i}_{eid}",use_container_width=True):
                            request_nav("Companies","company_pick_id",eid,ename)
                            st.rerun()

    with tabs[2]:
        if not yd.empty:
            yr=yd.iloc[0]
            st.markdown(f"### {yr.get('Shipyard','')}")
            st.caption(f"{yr.get('Location','')} · {yr.get('Country','')} · {yr.get('Yard Model','')}")
            if st.button("Open shipyard",key=f"dvp_yard_{vessel_id}",use_container_width=False):
                request_nav("Shipyards","yard_pick_id",str(yr.get("Yard ID","")),str(yr.get("Shipyard","")))
                st.rerun()
            display_df(yd,20)
        elif str(r.get("Build Yard ID","")).strip():
            st.info("Build yard ID exists but the yard record is not populated.")
        else:
            st.info("Build yard has not yet been assigned at individual-hull level.")

    with tabs[3]:
        if not hist.empty:
            h=hist.copy()
            if "Date" in h.columns:
                h["_dt"]=pd.to_datetime(h["Date"],errors="coerce")
                h=h.sort_values("_dt")
            display_df(h,100)
        else:
            st.info("No vessel-level milestone history has been populated yet.")

    with tabs[4]:
        if not ann.empty:
            show_named_list(ann,"Headline",["Date","Event Type","Linked Entities / Topics"],source_col="Source URL",max_items=100)
        else:
            st.info("No programme announcement linked.")

    with tabs[5]:
        src=str(r.get("Source URL","")).strip()
        if src.startswith("http"):
            st.markdown(f"[Open vessel / programme source ↗]({src})")
        if not rt.empty:
            st.markdown("### Sales / delivery route")
            display_df(rt,50)
        display_df(row,20)


def render_live_event_cluster(events, locations):
    if events is None or events.empty:
        return
    e=events.copy()
    if "Date" in e.columns:
        e["_dt"]=pd.to_datetime(e["Date"],errors="coerce")
        e=e.sort_values("_dt",ascending=False)

    # Treat active/developing/investigating and very recent severe incidents as live.
    live_mask=pd.Series(False,index=e.index)
    for c in ["Status","Status / Phase"]:
        if c in e.columns:
            live_mask |= e[c].astype(str).str.contains(
                r"active|developing|investigation|ongoing|occurred|damaged|disabled",
                case=False,na=False,regex=True
            )
    if "Severity" in e.columns:
        live_mask |= e["Severity"].astype(str).str.contains("severe|high",case=False,na=False)

    # Explicit Gulf cluster remains live while it is the current operational picture.
    if "Event ID" in e.columns:
        live_mask |= e["Event ID"].astype(str).str.startswith("EVT132_")

    live=e[live_mask].copy()
    if live.empty:
        return

    st.markdown("### Current / developing events")
    st.caption("Live operational picture. Events remain here while status, attribution or vessel-level details are still developing.")

    for i,(_,r) in enumerate(live.head(12).iterrows()):
        sev=str(r.get("Severity","")).strip()
        status=str(r.get("Status","")).strip() or str(r.get("Status / Phase","")).strip()
        date=str(r.get("Date","")).strip()
        title=str(r.get("Title","")).strip()
        loc=str(r.get("Location","")).strip()
        desc=str(r.get("Description","")).strip()
        direct=str(r.get("Direct Impact","")).strip()
        src=str(r.get("Source URL","")).strip()
        source_html=f"<div class='pc-source'><a href='{src}' target='_blank' rel='noopener noreferrer'>Open source ↗</a></div>" if src.startswith("http") else ""
        st.markdown(
            f"<div class='pc-card'>"
            f"<div class='pc-label'>{date} · {pretty_enum(sev)} · {pretty_enum(status)}</div>"
            f"<div class='pc-big'>{title}</div>"
            f"<div class='pc-small'>{loc}</div>"
            f"<div class='pc-small'>{desc}</div>"
            f"<div class='pc-small'><b>Direct impact:</b> {direct}</div>"
            f"{source_html}</div>",
            unsafe_allow_html=True
        )

# ---------- v3.0 security / compliance product lens ----------
def _first_existing(df, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    return None

def security_vessel_bundle(vessel_id="", vessel_name="", imo=""):
    restrictions=TABLES.get(("Maritime","Vessel Restrictions"),pd.DataFrame()).copy()
    designations=TABLES.get(("Trade Policy & Compliance","Compliance Designations"),pd.DataFrame()).copy()
    exposure=TABLES.get(("Trade Policy & Compliance","Compliance Exposure"),pd.DataFrame()).copy()
    out={"restrictions":pd.DataFrame(),"designations":pd.DataFrame(),"exposure":pd.DataFrame()}
    if not restrictions.empty:
        mask=pd.Series(False,index=restrictions.index)
        for col,val in [("Vessel ID",vessel_id),("IMO",imo),("Vessel Name",vessel_name)]:
            if val and col in restrictions.columns:
                mask=mask | restrictions[col].astype(str).str.strip().eq(str(val).strip())
        out["restrictions"]=restrictions[mask].copy()
    if not designations.empty:
        mask=pd.Series(False,index=designations.index)
        for col,val in [("Target ID",vessel_id),("IMO / Identifier",imo),("Target Name",vessel_name)]:
            if val and col in designations.columns:
                mask=mask | designations[col].astype(str).str.strip().eq(str(val).strip())
        out["designations"]=designations[mask].copy()
    if not exposure.empty:
        mask=pd.Series(False,index=exposure.index)
        for col,val in [("Source Vessel ID",vessel_id),("Source Vessel",vessel_name)]:
            if val and col in exposure.columns:
                mask=mask | exposure[col].astype(str).str.strip().eq(str(val).strip())
        out["exposure"]=exposure[mask].copy()
    return out

def render_share_price_history(entity_id):
    listings=TABLES.get(("Corporate & Markets","Company Listings"),pd.DataFrame()).copy()
    prices=TABLES.get(("Corporate & Markets","Company Market Prices"),pd.DataFrame()).copy()
    scope=company_scope_ids(entity_id)
    if not listings.empty and "Company ID" in listings.columns:
        listing=listings[listings["Company ID"].astype(str).isin(scope)].copy()
    else:
        listing=pd.DataFrame()
    if not listing.empty:
        r=listing.iloc[0]
        a,b,c=st.columns(3)
        a.metric("Ticker",str(r.get("Ticker","") or "—"))
        b.metric("Exchange",str(r.get("Exchange","") or "—"))
        c.metric("Currency",str(r.get("Currency","") or "—"))
        status=str(r.get("Listing Status","")).strip()
        if status: st.caption(status)
    if prices.empty or "Company ID" not in prices.columns:
        st.info("No structured share-price history for this company yet.")
        return
    p=prices[prices["Company ID"].astype(str).isin(scope)].copy()
    date_col=_first_existing(p,["Date","Month End","Trade Date"])
    close_col=_first_existing(p,["Close","Adjusted Close","Price"])
    if p.empty or not date_col or not close_col:
        st.info("No structured share-price history for this company yet.")
        return
    p["_date"]=pd.to_datetime(p[date_col],errors="coerce")
    p["_close"]=pd.to_numeric(p[close_col],errors="coerce")
    p=p.dropna(subset=["_date","_close"]).sort_values("_date")
    if p.empty:
        st.info("No usable price observations.")
        return
    ranges={"1M":31,"3M":93,"6M":186,"YTD":None,"1Y":366,"3Y":1096,"5Y":1827,"All":99999}
    period=st.radio("Price history",list(ranges),horizontal=True,key=f"price_range_{entity_id}")
    end=p["_date"].max()
    if period=="YTD":
        start=pd.Timestamp(year=end.year,month=1,day=1)
    else:
        start=end-pd.Timedelta(days=ranges[period])
    view=p[p["_date"].ge(start)].copy()
    if view.empty: view=p.copy()
    first=float(view.iloc[0]["_close"]); last=float(view.iloc[-1]["_close"])
    pct=((last/first)-1)*100 if first else None
    hi=float(view["_close"].max()); lo=float(view["_close"].min())
    a,b,c,d=st.columns(4)
    a.metric("Latest",f"{last:,.2f}")
    b.metric("Period change",f"{pct:+.1f}%" if pct is not None else "—")
    c.metric("Period high",f"{hi:,.2f}")
    d.metric("Period low",f"{lo:,.2f}")
    st.line_chart(view.set_index("_date")["_close"])
    cols=[c for c in [date_col,"Open","High","Low",close_col,"Volume","Currency","Source URL","Notes"] if c in p.columns]
    if cols: display_df(p[cols].sort_values(date_col,ascending=False),250)

def render_company_security_risk(entity_id, entity_name):
    scope=company_scope_ids(entity_id)
    vessels=TABLES.get(("Maritime","Vessels"),pd.DataFrame()).copy()
    vrel=TABLES.get(("Maritime","Vessel Relationships"),pd.DataFrame()).copy()
    comp_exp=TABLES.get(("Trade Policy & Compliance","Compliance Exposure"),pd.DataFrame()).copy()
    comp_des=TABLES.get(("Trade Policy & Compliance","Compliance Designations"),pd.DataFrame()).copy()
    monitoring=TABLES.get(("Intelligence","Monitoring"),pd.DataFrame()).copy()
    prof=build_company_profile(entity_id,entity_name)
    asset_ids=entity_asset_ids_from_profile(prof)
    ev,loc,chains=event_bundle_for_entities(entity_ids=scope,asset_ids=asset_ids)
    vids=set()
    if not vessels.empty:
        for c in ["Owner Company ID","Operator Company ID"]:
            if c in vessels.columns:
                vids.update(vessels[vessels[c].astype(str).isin(scope)]["Vessel ID"].astype(str).tolist())
    if not vrel.empty and "Company ID" in vrel.columns and "Vessel ID" in vrel.columns:
        vids.update(vrel[vrel["Company ID"].astype(str).isin(scope)]["Vessel ID"].astype(str).tolist())
    cv=vessels[vessels["Vessel ID"].astype(str).isin(vids)].copy() if vids and not vessels.empty else pd.DataFrame()
    d=pd.DataFrame()
    if not comp_des.empty and "Target ID" in comp_des.columns:
        d=comp_des[comp_des["Target ID"].astype(str).isin(vids)].copy()
    x=pd.DataFrame()
    if not comp_exp.empty and "Source Vessel ID" in comp_exp.columns:
        x=comp_exp[comp_exp["Source Vessel ID"].astype(str).isin(vids)].copy()
    a,b,c,dmetric=st.columns(4)
    a.metric("Linked vessels",len(cv))
    b.metric("Trade / business / security events",len(ev))
    c.metric("Compliance designations",len(d))
    dmetric.metric("Secondary exposures",len(x))
    if not d.empty:
        st.markdown("### Fleet compliance exposure")
        display_df(d[[c for c in ["Date","Target Name","IMO / Identifier","Status","Direct / Indirect","Reason / Basis","Verification","Notes"] if c in d.columns]],100)
    if not x.empty:
        st.markdown("### Secondary / counterparty exposure")
        display_df(x[[c for c in ["Source Vessel","Counterparty / Related Entity","Relationship","Event / Geography","Exposure Type","Status","Confidence","Analytical Note"] if c in x.columns]],100)
    if not ev.empty:
        st.markdown("### Asset and company security / disruption events")
        render_event_cards(ev,100)
        if not chains.empty:
            with st.expander("Impact chains"):
                display_df(chains,100)
    if not monitoring.empty:
        # broad matching on linked entity/vessel IDs for the Excel phase
        linked=[]
        ids=set(scope)|vids|set(asset_ids)
        for _,r in monitoring.iterrows():
            blob=" ".join(str(r.get(c,"")) for c in ["Linked Entity IDs","Linked Event IDs","Title","Geography"])
            if any(i and i in blob for i in ids): linked.append(r)
        if linked:
            st.markdown("### Active monitoring")
            display_df(pd.DataFrame(linked)[[c for c in ["Title","Family","Geography","Status","Time Horizon","What Is Being Monitored","Trigger / Threshold","Confidence"] if c in monitoring.columns]],100)
    if d.empty and x.empty and ev.empty:
        st.info("No structured security/compliance exposure has been linked to this company yet.")

def render_security_operating_picture():
    monitoring=TABLES.get(("Intelligence","Monitoring"),pd.DataFrame()).copy()
    events=TABLES.get(("Events & Hazards","Events"),pd.DataFrame()).copy()
    des=TABLES.get(("Trade Policy & Compliance","Compliance Designations"),pd.DataFrame()).copy()
    exposure=TABLES.get(("Trade Policy & Compliance","Compliance Exposure"),pd.DataFrame()).copy()
    feeds=TABLES.get(("Evidence & sources","Source Feeds"),pd.DataFrame()).copy()
    active=monitoring[monitoring.get("Status",pd.Series(dtype=str)).astype(str).str.contains("Active",case=False,na=False)] if not monitoring.empty else monitoring
    severe=events[events.get("Severity",pd.Series(dtype=str)).astype(str).str.lower().isin(["high","severe","critical"])] if not events.empty else events
    marsec=events[events.get("Event Family",pd.Series(dtype=str)).astype(str).str.contains("Maritime|Security|Conflict|Port",case=False,regex=True,na=False)] if not events.empty else events
    official=feeds[feeds.get("Feed ID",pd.Series(dtype=str)).astype(str).str.startswith("FEED_SEC")] if not feeds.empty else feeds
    cols=st.columns(5)
    vals=[("Active monitors",len(active)),("High/severe events",len(severe)),("MARSEC/security events",len(marsec)),("Compliance records",len(des)+len(exposure)),("Security feeds",len(official))]
    for c,(lab,val) in zip(cols,vals): c.metric(lab,f"{val:,}")
    if not active.empty:
        st.markdown("### Priority monitoring")
        display_df(active[[c for c in ["Title","Family","Geography","Status","Time Horizon","What Is Being Monitored","Trigger / Threshold","Confidence"] if c in active.columns]],100)
    if not severe.empty:
        st.markdown("### Latest high-severity events")
        render_event_cards(severe,20)


def _safe_filter_choices(df, column):
    """Return stable string choices even when a column contains lists/dicts/NaN/mixed types."""
    if df is None or df.empty or column not in df.columns:
        return []
    values=[]
    series=df[column]
    # Duplicate column names can return a DataFrame.
    if isinstance(series,pd.DataFrame):
        iterable=[]
        for c in series.columns:
            iterable.extend(series[c].tolist())
    else:
        iterable=series.tolist()

    for raw in iterable:
        if raw is None:
            continue
        try:
            if pd.isna(raw):
                continue
        except Exception:
            pass
        if isinstance(raw,(list,tuple,set)):
            parts=list(raw)
        elif isinstance(raw,dict):
            parts=list(raw.values())
        else:
            parts=[raw]
        for part in parts:
            if part is None:
                continue
            try:
                if pd.isna(part):
                    continue
            except Exception:
                pass
            s=str(part).strip()
            if not s or s.casefold() in {"nan","nat","none","null","<na>"}:
                continue
            values.append(s)
    return sorted(set(values),key=lambda x:x.casefold())

def _canonical_vessel_fallback():
    """Direct canonical vessel fallback when workbook/merged Maritime→Vessels is empty."""
    try:
        sb=pc_db_client(service=True)
        rows=(sb.table("pc_mobile_assets")
              .select("mobile_asset_id,name,imo,mmsi,flag,asset_type,subtype,status,owner_entity_id,operator_entity_id")
              .limit(5000)
              .execute().data or [])
    except Exception:
        rows=[]
    if not rows:
        return pd.DataFrame()
    df=pd.DataFrame(rows)
    return pd.DataFrame({
        "Vessel ID":df.get("mobile_asset_id"),
        "Vessel Name":df.get("name"),
        "IMO":df.get("imo"),
        "MMSI":df.get("mmsi"),
        "Flag":df.get("flag"),
        "Vessel Type":df.get("asset_type"),
        "Subtype / Class":df.get("subtype"),
        "Status":df.get("status"),
        "Owner Company ID":df.get("owner_entity_id"),
        "Operator Company ID":df.get("operator_entity_id"),
    })

def render_marsec_workspace():
    events=TABLES.get(("Events & Hazards","Events"),pd.DataFrame()).copy()
    feeds=TABLES.get(("Evidence & sources","Source Feeds"),pd.DataFrame()).copy()

    if not feeds.empty:
        feed_id=feeds.get("Feed ID")
        if isinstance(feed_id,pd.Series):
            sec=feeds[feed_id.fillna("").astype(str).str.startswith("FEED_SEC")].copy()
        else:
            sec=pd.DataFrame()
        if not sec.empty:
            with st.expander("Official MARSEC collection",expanded=False):
                display_df(sec[[c for c in ["Source Name","Coverage","Default Event Families","Priority","Active","Last Checked","Notes"] if c in sec.columns]],100)

    if events.empty:
        st.info("No event data loaded.")
        return

    fam=events.get("Event Family",pd.Series(index=events.index,dtype="string"))
    if isinstance(fam,pd.DataFrame):
        fam=fam.iloc[:,0]
    fam=fam.fillna("").astype(str)

    # Broader MARSEC capture so linked vessel/port incidents are not silently missed.
    blob=pd.Series("",index=events.index,dtype="string")
    for c in ["Event Family","Event Type","Mode","Title","Description","Operational Impact","Trade / Commercial Impact"]:
        if c in events.columns:
            col=events[c]
            if isinstance(col,pd.DataFrame):
                col=col.iloc[:,0]
            blob=blob.str.cat(col.fillna("").astype(str),sep=" ")

    mask=blob.str.contains(
        r"maritime|security|conflict|port|vessel|ship|tanker|cargo|piracy|ground|collision|allision|fire|explosion|sar|pollution|drone|missile|seizure|boarding|interdiction|navigation",
        case=False,regex=True,na=False
    )
    marsec=events[mask].copy()

    c1,c2=st.columns(2)
    with c1:
        families=_safe_filter_choices(marsec,"Event Type")
        et=st.selectbox("Incident type",["All"]+families,key="marsec_type_filter")
    with c2:
        countries=_safe_filter_choices(marsec,"Country / Countries")
        country=st.selectbox("Country / area",["All"]+countries,key="marsec_country_filter")

    if et!="All" and "Event Type" in marsec.columns:
        col=marsec["Event Type"]
        if isinstance(col,pd.DataFrame):
            col=col.iloc[:,0]
        marsec=marsec[col.fillna("").astype(str).eq(et)]

    if country!="All" and "Country / Countries" in marsec.columns:
        col=marsec["Country / Countries"]
        if isinstance(col,pd.DataFrame):
            col=col.iloc[:,0]
        # Country field can contain multi-country text; filter by containment.
        marsec=marsec[col.fillna("").astype(str).str.contains(re.escape(country),case=False,regex=True,na=False)]

    if "Start Date" in marsec.columns:
        marsec["_d"]=pd.to_datetime(marsec["Start Date"],errors="coerce")
        marsec=marsec.sort_values("_d",ascending=False,na_position="last")

    st.markdown("### Incident feed")
    st.caption(f"{len(marsec):,} maritime/security-relevant records match the current filters.")
    render_event_cards(marsec,100)

def render_compliance_exposure_workspace():
    regimes=TABLES.get(("Trade Policy & Compliance","Compliance Regimes"),pd.DataFrame()).copy()
    des=TABLES.get(("Trade Policy & Compliance","Compliance Designations"),pd.DataFrame()).copy()
    exp=TABLES.get(("Trade Policy & Compliance","Compliance Exposure"),pd.DataFrame()).copy()
    restrictions=TABLES.get(("Maritime","Vessel Restrictions"),pd.DataFrame()).copy()
    a,b,c=st.columns(3)
    a.metric("Compliance regimes",len(regimes))
    b.metric("Direct designations",len(des))
    c.metric("Exposure links",len(exp))
    if not regimes.empty:
        st.markdown("### Regimes")
        display_df(regimes,50)
    if not des.empty:
        st.markdown("### Designations")
        display_df(des[[c for c in ["Date","Target Type","Target Name","IMO / Identifier","Status","Direct / Indirect","Reason / Basis","Verification","Notes"] if c in des.columns]],200)
    if not exp.empty:
        st.markdown("### Secondary / counterparty exposure")
        display_df(exp[[c for c in ["Source Vessel","Counterparty / Related Entity","Related Entity Type","Relationship","Event / Geography","Exposure Type","Status","Confidence","Analytical Note"] if c in exp.columns]],200)
    if not restrictions.empty:
        with st.expander("Underlying vessel restriction records"):
            display_df(restrictions,200)



def _trade_alert_candidates():
    """Canonical disruption records first; legacy keyword inference only as fallback."""
    explicit=_canonical_trade_disruptions()
    if explicit is not None and not explicit.empty:
        return explicit.copy()

    events=TABLES.get(("Events & Hazards","Events"),pd.DataFrame()).copy()
    if events.empty:
        return events
    cols=[c for c in ["Event Family","Event Type","Title","Description","Operational Impact","Trade / Commercial Impact"] if c in events.columns]
    blob=pd.Series("",index=events.index,dtype="string")
    for c in cols:
        blob=blob.str.cat(events[c].fillna("").astype(str),sep=" ")
    include=r"strike|labour|weather|typhoon|cyclone|hurricane|flood|earthquake|wildfire|storm|closure|outage|disruption|grounding|collision|allision|capsize|sinking|fire|explosion|attack|missile|drone|piracy|seizure|interdiction|sanction|customs|tariff|border|canal|channel|low water|cyber|fraud|smuggl|crime"
    view=events[blob.str.contains(include,case=False,regex=True,na=False)].copy()
    if "Start Date" in view.columns:
        view["_dt"]=pd.to_datetime(view["Start Date"],errors="coerce")
        view=view.sort_values("_dt",ascending=False)
    return view


def render_trade_alerts_workspace():
    header("Alerts & Disruptions","Commercially relevant disruption across ports, rail, trucking, aviation, weather, labour, policy and security spillover. Routine corporate development is excluded.")
    ev=_trade_alert_candidates()
    if ev.empty:
        st.info("No trade-disruption alerts are currently classified.")
        return
    a,b,c,d=st.columns(4)
    a.metric("Active alerts",len(ev))
    fam=ev.get("Disruption Domains",ev.get("Event Family",pd.Series(dtype=str))).fillna("").astype(str)
    b.metric("Weather / natural",int(fam.str.contains("Weather|Natural",case=False,regex=True).sum()))
    c.metric("Labour / civil",int(fam.str.contains("Labour|Industrial|Civil",case=False,regex=True).sum()))
    d.metric("Security spillover",int(fam.str.contains("Security|Conflict|Maritime",case=False,regex=True).sum()))
    tabs=st.tabs(["All alerts","Weather & Natural Hazards","Labour & Logistics","Trade / Policy","Security Spillover"])
    filters=[None,"Weather|Natural|Storm|Flood|Typhoon|Cyclone|Earthquake|Wildfire","Labour|Industrial|Strike|Port|Rail|Road|Truck|Logistics","Trade|Policy|Customs|Tariff|Sanction|Border","Security|Conflict|Maritime|Attack|Piracy|Drone|Missile"]
    for tab,pat in zip(tabs,filters):
        with tab:
            if pat is None:
                view=ev
            else:
                blob=pd.Series("",index=ev.index,dtype="string")
                for col in ["Disruption Domains","Disruption Type","Event Family","Event Type","Title","Description","Operational Impact","Trade / Commercial Impact"]:
                    if col in ev.columns:
                        blob=blob.str.cat(ev[col].fillna("").astype(str),sep=" ")
                view=ev[blob.str.contains(pat,case=False,regex=True,na=False)]
            if view.empty: st.caption("No alerts in this category.")
            else: render_event_cards(view,60)



def _security_text(v):
    return str(v or "").strip()

def _security_norm(v):
    return re.sub(r"[^a-z0-9]+"," ",_security_text(v).casefold()).strip()

def _security_country_from_record(row):
    """Best available country label from canonical entity/asset metadata."""
    for key in ("hq_country","country","Country","HQ Country"):
        v=_security_text(row.get(key))
        if v:
            return v
    meta=row.get("metadata")
    if isinstance(meta,dict):
        for key in ("country","hq_country","jurisdiction"):
            v=_security_text(meta.get(key))
            if v:
                return v
        ra=meta.get("research_attributes")
        if isinstance(ra,dict):
            for key in ("country","hq_country","jurisdiction"):
                v=_security_text(ra.get(key))
                if v:
                    return v
    return ""

def _security_category(row):
    """Classify government/security entities without pretending commercial companies are state agencies."""
    blob=" ".join([
        _security_text(row.get("name")),
        _security_text(row.get("entity_type")),
        _security_text(row.get("subtype")),
    ]).casefold()

    if any(x in blob for x in ("coast guard","maritime safety agency","maritime security agency")):
        return "Coast Guard / Maritime Security"
    if any(x in blob for x in ("navy","naval force","naval forces","fleet command","marine corps")):
        return "Navy / Naval Forces"
    if any(x in blob for x in ("air force","air command","air defence","air defense")):
        return "Air Force / Air Defence"
    if any(x in blob for x in ("border guard","border force","customs","gendarmerie","maritime police","marine police")):
        return "Border / Customs / Gendarmerie"
    if any(x in blob for x in ("ministry of defence","ministry of defense","department of defense","department of defence","armed forces","joint forces","general staff")):
        return "Defence Ministry / Armed Forces"
    if any(x in blob for x in ("procurement","acquisition","materiel","armament","defence equipment","defense equipment")):
        return "Defence Procurement / Acquisition"
    if any(x in blob for x in ("operational command","area command","logistics center","logistics centre","support command")):
        return "Operational / Support Command"
    if any(x in blob for x in ("government","ministry","authority","agency","command")) and any(
        x in blob for x in ("security","defence","defense","military","maritime","naval","border")
    ):
        return "Government Security Organisation"
    return ""

def _security_vessel_service_hint(row):
    """Recover a government service/operator from canonical vessel metadata or naming."""
    vals=[]

    def add(v):
        s=_security_text(v)
        if s and s not in vals:
            vals.append(s)

    for k in ("service","operator","owner","manager","organisation","organization"):
        add(row.get(k))

    meta=row.get("metadata")
    if isinstance(meta,dict):
        for k in ("service","operator","owner","manager","organisation","organization"):
            add(meta.get(k))
        ra=meta.get("research_attributes")
        if isinstance(ra,dict):
            for k in ("service","operator","owner","manager","organisation","organization"):
                add(ra.get(k))

    name=_security_text(row.get("name"))
    n=name.casefold()
    if n.startswith("uscgc "):
        add("United States Coast Guard")
    if n.startswith("ccgs "):
        add("Canadian Coast Guard")
    if n.startswith("jcg "):
        add("Japan Coast Guard")
    if n.startswith("icgs "):
        add("Indian Coast Guard")

    return vals


def _match_security_org_ids(service_values, by_id, security_ids):
    """Match readable service/operator text to canonical government/security entities."""
    found=set()
    norms=[_security_norm(v) for v in service_values if _security_norm(v)]
    if not norms:
        return found

    aliases={
        "us coast guard":"united states coast guard",
        "u s coast guard":"united states coast guard",
        "uscg":"united states coast guard",
        "ccg":"canadian coast guard",
        "jcg":"japan coast guard",
        "icg":"indian coast guard",
    }
    norms=[aliases.get(n,n) for n in norms]

    for eid in security_ids:
        en=_security_norm(by_id.get(eid,{}).get("name"))
        if not en:
            continue
        for n in norms:
            if en==n or en in n or n in en:
                found.add(eid)
                break
    return found


@st.cache_data(show_spinner=False, ttl=45)
def _live_government_security_model():
    """Canonical government/security discovery layer from the live Supabase graph."""
    result={
        "entities":pd.DataFrame(),
        "relationships":pd.DataFrame(),
        "vessels":pd.DataFrame(),
        "assets":pd.DataFrame(),
        "error":"",
    }
    try:
        sb=pc_db_client(service=True)
        if sb is None:
            result["error"]="No Supabase client"
            return result

        erows=pc_safe_rows(
            sb,"pc_entities",
            "entity_id,name,entity_type,subtype,hq_city,hq_country,status,record_status,metadata",
            15000,order="name"
        ) or []
        rrows=pc_safe_rows(
            sb,"pc_relationships",
            "relationship_id,source_type,source_id,relationship_type,target_type,target_id,"
            "ownership_percent,operating_control,confidence,record_status,evidence_source_id,notes,metadata",
            40000
        ) or []
        mrows=pc_safe_rows(
            sb,"pc_mobile_assets",
            "mobile_asset_id,name,asset_type,subtype,imo,mmsi,registration,call_sign,flag,"
            "year_built,dwt,capacity_value,capacity_unit,owner_entity_id,operator_entity_id,"
            "manager_entity_id,status,record_status,data_quality,source_id,metadata",
            25000,order="name"
        ) or []
        arows=pc_safe_rows(
            sb,"pc_assets",
            "asset_id,name,asset_type,subtype,country,region_city,latitude,longitude,"
            "operator_entity_id,owner_entity_id,status,record_status,data_quality,source_id,metadata",
            25000,order="name"
        ) or []

        by_id={_security_text(x.get("entity_id")):x for x in erows if _security_text(x.get("entity_id"))}
        security_ids=set()
        categories={}
        countries={}

        # First pass: direct classification and direct country.
        for eid,row in by_id.items():
            cat=_security_category(row)
            if cat:
                security_ids.add(eid)
                categories[eid]=cat
            c=_security_country_from_record(row)
            if c:
                countries[eid]=c

        # Strong country hints for major state services where older rows lack hq_country.
        service_country_hints={
            "united states coast guard":"United States",
            "us coast guard":"United States",
            "u s coast guard":"United States",
            "canadian coast guard":"Canada",
            "royal canadian navy":"Canada",
            "united states navy":"United States",
            "u s navy":"United States",
            "royal navy":"United Kingdom",
            "royal australian navy":"Australia",
            "australian border force":"Australia",
            "japan coast guard":"Japan",
            "indian coast guard":"India",
            "indian navy":"India",
        }
        for eid,row in by_id.items():
            nm=_security_norm(row.get("name"))
            if not countries.get(eid):
                for key,country in service_country_hints.items():
                    if key in nm:
                        countries[eid]=country
                        break

        # Propagate category/country down government command hierarchies.
        hierarchy_rel={
            "parent_of","controls","includes","contains","commands","command_of",
            "subordinate_command","part_of","reports_to","component_of","under"
        }
        for _ in range(6):
            changed=False
            for rr in rrows:
                if _security_text(rr.get("source_type")).casefold()!="entity" or _security_text(rr.get("target_type")).casefold()!="entity":
                    continue
                sid=_security_text(rr.get("source_id")); tid=_security_text(rr.get("target_id"))
                rel=_security_text(rr.get("relationship_type")).casefold().replace("-","_").replace(" ","_")
                if sid not in by_id or tid not in by_id:
                    continue

                if sid in security_ids and (rel in hierarchy_rel or "parent" in rel or "command" in rel or "part_of" in rel):
                    if tid not in security_ids:
                        security_ids.add(tid)
                        categories[tid]=_security_category(by_id[tid]) or "Operational / Support Command"
                        changed=True
                    if countries.get(sid) and not countries.get(tid):
                        countries[tid]=countries[sid]; changed=True

                # Reverse-form relationship: child -> parent (PART_OF etc.).
                if tid in security_ids and rel in {"part_of","reports_to","component_of","under","subordinate_to"}:
                    if sid not in security_ids:
                        security_ids.add(sid)
                        categories[sid]=_security_category(by_id[sid]) or "Operational / Support Command"
                        changed=True
                    if countries.get(tid) and not countries.get(sid):
                        countries[sid]=countries[tid]; changed=True
            if not changed:
                break

        entity_rows=[]
        for eid in sorted(security_ids):
            row=by_id[eid]
            entity_rows.append({
                "Entity ID":eid,
                "Organisation":_security_text(row.get("name")),
                "Category":categories.get(eid) or _security_category(row) or "Government Security Organisation",
                "Country":countries.get(eid) or _security_country_from_record(row),
                "Entity Type":_security_text(row.get("entity_type")),
                "Subtype":_security_text(row.get("subtype")),
                "HQ City":_security_text(row.get("hq_city")),
                "Status":_security_text(row.get("status")),
                "Record Status":_security_text(row.get("record_status")),
                "Metadata":row.get("metadata") or {},
            })
        edf=pd.DataFrame(entity_rows)

        rel_rows=[]
        linked_vessel_ids=set()
        linked_asset_ids=set()

        for rr in rrows:
            sid=_security_text(rr.get("source_id")); tid=_security_text(rr.get("target_id"))
            st=_security_text(rr.get("source_type")).casefold()
            tt=_security_text(rr.get("target_type")).casefold()
            if sid not in security_ids and tid not in security_ids:
                continue
            if tt in {"mobile_asset","vessel"} and sid in security_ids:
                linked_vessel_ids.add(tid)
            if tt=="asset" and sid in security_ids:
                linked_asset_ids.add(tid)

            rel_rows.append({
                "Relationship ID":_security_text(rr.get("relationship_id")),
                "Source ID":sid,
                "Source":_security_text(by_id.get(sid,{}).get("name")) or sid,
                "Relationship":pretty_relationship(rr.get("relationship_type")),
                "Target Type":tt,
                "Target ID":tid,
                "Target":_security_text(by_id.get(tid,{}).get("name")) or tid,
                "Confidence":rr.get("confidence"),
                "Record Status":_security_text(rr.get("record_status")),
            })

        # Direct canonical owner/operator/manager IDs count, but many newly researched
        # government vessels intentionally arrive before those FK columns are populated.
        # Recover their service from metadata / vessel prefix as a safe discovery fallback.
        inferred_vessel_orgs={}
        for m in mrows:
            vid=_security_text(m.get("mobile_asset_id"))
            direct={
                _security_text(m.get(k))
                for k in ("owner_entity_id","operator_entity_id","manager_entity_id")
                if _security_text(m.get(k)) in security_ids
            }
            inferred=_match_security_org_ids(
                _security_vessel_service_hint(m),
                by_id,
                security_ids
            )
            orgs=direct | inferred
            if orgs:
                linked_vessel_ids.add(vid)
                inferred_vessel_orgs[vid]=orgs

        for a in arows:
            if any(_security_text(a.get(k)) in security_ids for k in ("owner_entity_id","operator_entity_id")):
                linked_asset_ids.add(_security_text(a.get("asset_id")))

        vessel_rows=[]
        for m in mrows:
            vid=_security_text(m.get("mobile_asset_id"))
            if vid not in linked_vessel_ids:
                continue
            linked_org_ids=set()
            for rr in rrows:
                if _security_text(rr.get("target_id"))==vid and _security_text(rr.get("source_id")) in security_ids:
                    linked_org_ids.add(_security_text(rr.get("source_id")))
            for k in ("owner_entity_id","operator_entity_id","manager_entity_id"):
                eid=_security_text(m.get(k))
                if eid in security_ids:
                    linked_org_ids.add(eid)
            linked_org_ids.update(inferred_vessel_orgs.get(vid,set()))
            linked_orgs=[_security_text(by_id.get(x,{}).get("name")) or x for x in sorted(linked_org_ids)]
            vcountries=[countries.get(x,"") for x in linked_org_ids if countries.get(x)]
            vessel_rows.append({
                "Vessel ID":vid,
                "Vessel":_security_text(m.get("name")),
                "IMO":_security_text(m.get("imo")),
                "Hull / Registration":_security_text(m.get("registration")),
                "Flag":_security_text(m.get("flag")),
                "Type":_security_text(m.get("asset_type")),
                "Subtype / Class":_security_text(m.get("subtype")),
                "Organisation":" · ".join(linked_orgs),
                "Country":vcountries[0] if vcountries else _security_text(m.get("flag")),
                "Status":_security_text(m.get("status")),
                "Record Status":_security_text(m.get("record_status")),
                "Metadata":m.get("metadata") or {},
            })

        asset_rows=[]
        for a in arows:
            aid=_security_text(a.get("asset_id"))
            if aid not in linked_asset_ids:
                continue
            linked_org_ids=set()
            for rr in rrows:
                if _security_text(rr.get("target_id"))==aid and _security_text(rr.get("source_id")) in security_ids:
                    linked_org_ids.add(_security_text(rr.get("source_id")))
            for k in ("owner_entity_id","operator_entity_id"):
                eid=_security_text(a.get(k))
                if eid in security_ids:
                    linked_org_ids.add(eid)
            linked_orgs=[_security_text(by_id.get(x,{}).get("name")) or x for x in sorted(linked_org_ids)]
            acountries=[countries.get(x,"") for x in linked_org_ids if countries.get(x)]
            asset_rows.append({
                "Asset ID":aid,
                "Facility / Base":_security_text(a.get("name")),
                "Type":_security_text(a.get("asset_type")),
                "Subtype":_security_text(a.get("subtype")),
                "Country":_security_text(a.get("country")) or (acountries[0] if acountries else ""),
                "City / Area":_security_text(a.get("region_city")),
                "Organisation":" · ".join(linked_orgs),
                "Status":_security_text(a.get("status")),
                "Record Status":_security_text(a.get("record_status")),
                "Latitude":a.get("latitude"),
                "Longitude":a.get("longitude"),
                "Metadata":a.get("metadata") or {},
            })

        result["entities"]=edf
        result["relationships"]=pd.DataFrame(rel_rows)
        result["vessels"]=pd.DataFrame(vessel_rows)
        result["assets"]=pd.DataFrame(asset_rows)
        return result
    except Exception as exc:
        result["error"]=f"{type(exc).__name__}: {exc}"
        return result


def render_government_vessel_detail(vrow, prefix="gov_vessel"):
    """Compact expandable vessel profile from the live government/security vessel layer."""
    if vrow is None:
        return

    name=_security_text(vrow.get("Vessel")) or "Unnamed vessel / platform"
    cls=_security_text(vrow.get("Subtype / Class"))
    typ=_security_text(vrow.get("Type"))
    org=_security_text(vrow.get("Organisation"))
    country=_security_text(vrow.get("Country"))
    flag=_security_text(vrow.get("Flag"))
    status=_security_text(vrow.get("Status"))
    imo=_security_text(vrow.get("IMO"))
    hull=_security_text(vrow.get("Hull / Registration"))
    rec=_security_text(vrow.get("Record Status"))
    meta=vrow.get("Metadata") if isinstance(vrow.get("Metadata"),dict) else {}
    ra=meta.get("research_attributes") if isinstance(meta.get("research_attributes"),dict) else {}

    st.markdown(f"### {name}")
    st.caption(" · ".join([x for x in [cls or typ,org,country,status] if x]))

    c1,c2,c3,c4=st.columns(4)
    c1.metric("Type",cls or typ or "—")
    c2.metric("Country",country or flag or "—")
    c3.metric("Status",status or "—")
    c4.metric("IMO / Hull",imo or hull or "—")

    fields=[
        ("Organisation / service",org),
        ("Flag",flag),
        ("Vessel type",typ),
        ("Class / subtype",cls),
        ("IMO",imo),
        ("Hull / registration",hull),
        ("Record status",rec),
        ("Homeport",_security_text(ra.get("homeport") or meta.get("homeport"))),
        ("Operating region",_security_text(ra.get("operating_region") or meta.get("operating_region"))),
        ("Builder",_security_text(ra.get("builder") or meta.get("builder"))),
        ("Shipyard",_security_text(ra.get("shipyard") or meta.get("shipyard"))),
        ("Programme",_security_text(ra.get("programme") or meta.get("programme"))),
        ("Commissioned",_security_text(ra.get("commissioned_date") or meta.get("commissioned_date"))),
        ("Expected delivery",_security_text(ra.get("expected_delivery") or meta.get("expected_delivery"))),
        ("Construction status",_security_text(ra.get("construction_status") or meta.get("construction_status"))),
        ("Role",_security_text(ra.get("role") or meta.get("role"))),
    ]
    rows=[{"Field":a,"Value":b} for a,b in fields if b]
    if rows:
        display_df(pd.DataFrame(rows),120)

    desc=_security_text(ra.get("description") or meta.get("description"))
    if desc:
        st.markdown("#### Notes")
        st.write(desc)

    sources=meta.get("research_sources")
    if isinstance(sources,list) and sources:
        with st.expander("Evidence & sources",expanded=False):
            for i,s in enumerate(sources,1):
                if isinstance(s,dict):
                    title=_security_text(s.get("title")) or f"Source {i}"
                    pub=_security_text(s.get("publisher"))
                    url=_security_text(s.get("url"))
                    if url:
                        st.markdown(f"{i}. [{title}]({url})" + (f" — {pub}" if pub else ""))
                    else:
                        st.write(f"{i}. {title}" + (f" — {pub}" if pub else ""))


def render_government_security():
    model=_live_government_security_model()
    if model.get("error"):
        st.warning("Live government/security layer could not be loaded: "+model["error"])

    entities=model.get("entities",pd.DataFrame()).copy()
    vessels=model.get("vessels",pd.DataFrame()).copy()
    assets=model.get("assets",pd.DataFrame()).copy()
    relationships=model.get("relationships",pd.DataFrame()).copy()

    if entities.empty:
        st.info("No canonical government/security organisations are currently classified.")
        return

    countries=sorted([x for x in entities.get("Country",pd.Series(dtype=str)).fillna("").astype(str).unique() if x.strip()])
    country=st.selectbox("Country",["All countries"]+countries,key="govsec_country")
    if country!="All countries":
        eview=entities[entities["Country"].astype(str).eq(country)].copy()
        ids=set(eview["Entity ID"].astype(str))
        vview=vessels[
            vessels.get("Country",pd.Series(index=vessels.index,dtype=str)).astype(str).eq(country)
            | vessels.get("Organisation",pd.Series(index=vessels.index,dtype=str)).astype(str).apply(
                lambda x:any(_security_text(entities.loc[entities["Entity ID"].astype(str).isin(ids),"Organisation"].astype(str).eq(org)).any() for org in x.split(" · ")) if x else False
            )
        ].copy() if not vessels.empty else vessels
        aview=assets[assets.get("Country",pd.Series(index=assets.index,dtype=str)).astype(str).eq(country)].copy() if not assets.empty else assets
        rview=relationships[
            relationships.get("Source ID",pd.Series(index=relationships.index,dtype=str)).astype(str).isin(ids)
            | relationships.get("Target ID",pd.Series(index=relationships.index,dtype=str)).astype(str).isin(ids)
        ].copy() if not relationships.empty else relationships
    else:
        eview=entities; vview=vessels; aview=assets; rview=relationships

    c1,c2,c3,c4=st.columns(4)
    c1.metric("Security organisations",len(eview))
    c2.metric("Coast Guard / maritime",int(eview["Category"].astype(str).str.contains("Coast Guard|Maritime Security",case=False,regex=True).sum()))
    c3.metric("Linked vessels / platforms",len(vview))
    c4.metric("Linked facilities / bases",len(aview))

    st.caption("This layer separates government/security organisations from commercial companies. It follows canonical entity relationships and direct owner/operator links rather than inferring state ownership from names alone.")

    tabs=st.tabs([
        "Directory",
        "Coast Guard & Maritime",
        "Defence / Navy",
        "Vessels & Platforms",
        "Bases & Facilities",
        "Relationship Graph",
    ])

    with tabs[0]:
        q=st.text_input("Find organisation",placeholder="United States Coast Guard, Royal Navy, border force...",key="govsec_org_q")
        x=eview.copy()
        if q.strip():
            x=_contains_any(x,[q],["Organisation","Category","Country","Entity Type","Subtype"])
        display_df(x[[c for c in ["Organisation","Category","Country","Entity Type","Subtype","HQ City","Status","Record Status"] if c in x.columns]],400)

    with tabs[1]:
        x=eview[eview["Category"].astype(str).str.contains("Coast Guard|Maritime Security|Border|Gendarmerie",case=False,regex=True,na=False)].copy()
        if x.empty:
            st.info("No coast guard / maritime-security organisations mapped for this selection.")
        else:
            display_df(x[[c for c in ["Organisation","Category","Country","Entity Type","Subtype","HQ City","Status"] if c in x.columns]],300)
            cgids=set(x["Entity ID"].astype(str))
            if not relationships.empty and not vessels.empty:
                vids=set(relationships[
                    relationships["Source ID"].astype(str).isin(cgids)
                    & relationships["Target Type"].astype(str).isin(["mobile_asset","vessel"])
                ]["Target ID"].astype(str))
                cv=vessels[vessels["Vessel ID"].astype(str).isin(vids)].copy()
                if not cv.empty:
                    st.markdown("### Linked cutters, icebreakers and other platforms")
                    cv=cv.sort_values(["Country","Organisation","Vessel"],na_position="last").reset_index(drop=True)
                    display_df(cv[[c for c in ["Vessel","Subtype / Class","Flag","Organisation","Country","Status","IMO","Hull / Registration"] if c in cv.columns]],400)

                    cg_pick=st.selectbox(
                        "Inspect cutter / platform",
                        range(len(cv)),
                        format_func=lambda i: " — ".join([
                            z for z in [
                                str(cv.iloc[i].get("Vessel","")).strip(),
                                str(cv.iloc[i].get("Country","")).strip(),
                                str(cv.iloc[i].get("Organisation","")).strip(),
                            ] if z
                        ]),
                        key="govsec_coastguard_vessel_pick"
                    )
                    render_government_vessel_detail(cv.iloc[cg_pick],prefix="coastguard")

    with tabs[2]:
        x=eview[eview["Category"].astype(str).str.contains("Defence|Navy|Naval|Air Force|Armed Forces|Procurement",case=False,regex=True,na=False)].copy()
        if x.empty:
            st.info("No defence/naval organisations mapped for this selection.")
        else:
            display_df(x[[c for c in ["Organisation","Category","Country","Entity Type","Subtype","HQ City","Status"] if c in x.columns]],300)

    with tabs[3]:
        q=st.text_input("Find vessel / platform",placeholder="USCGC Healy, CCGS Arpatuuq, cutter, icebreaker...",key="govsec_vessel_q")
        x=vview.copy()
        if q.strip() and not x.empty:
            x=_contains_any(x,[q],["Vessel","Subtype / Class","Flag","Organisation","Country","Status","IMO","Hull / Registration"])
        if x.empty:
            st.info("No linked government/security vessels are mapped for this selection.")
        else:
            x=x.sort_values(["Country","Organisation","Vessel"],na_position="last").reset_index(drop=True)
            display_df(x[[c for c in ["Vessel","Subtype / Class","Type","Organisation","Country","Flag","Status","IMO","Hull / Registration","Record Status"] if c in x.columns]],500)

            st.markdown("### Inspect a vessel")
            pick=st.selectbox(
                "Vessel / platform",
                range(len(x)),
                format_func=lambda i: " — ".join([
                    z for z in [
                        str(x.iloc[i].get("Vessel","")).strip(),
                        str(x.iloc[i].get("Country","")).strip(),
                        str(x.iloc[i].get("Organisation","")).strip(),
                    ] if z
                ]),
                key="govsec_vessel_detail_pick"
            )
            render_government_vessel_detail(x.iloc[pick],prefix="govsec")

    with tabs[4]:
        if aview.empty:
            st.info("No linked government/security facilities or bases are mapped for this selection yet.")
        else:
            display_df(aview[[c for c in ["Facility / Base","Type","Subtype","Organisation","Country","City / Area","Status","Record Status"] if c in aview.columns]],400)
            m=aview.copy()
            m["lat"]=pd.to_numeric(m.get("Latitude"),errors="coerce")
            m["lon"]=pd.to_numeric(m.get("Longitude"),errors="coerce")
            m=m.dropna(subset=["lat","lon"])
            if not m.empty:
                st.map(m[["lat","lon"]],use_container_width=True)

    with tabs[5]:
        if rview.empty:
            st.info("No canonical relationships mapped for this selection.")
        else:
            display_df(rview[[c for c in ["Source","Relationship","Target","Target Type","Confidence","Record Status"] if c in rview.columns]],600)



@st.cache_data(show_spinner=False, ttl=60)
def _live_policy_rows(table_candidates):
    """Return rows from the first available canonical policy/compliance table."""
    try:
        sb=pc_db_client(service=True)
        if sb is None:
            return pd.DataFrame(), ""
        for table in table_candidates:
            try:
                rows=pc_safe_rows(sb,table,"*",20000)
            except Exception:
                rows=[]
            if rows:
                return pd.DataFrame(rows), table
    except Exception:
        pass
    return pd.DataFrame(), ""

def _policy_title_columns(df):
    if df is None or df.empty:
        return pd.DataFrame()
    out=df.copy()
    rename={}
    special={
        "designation_id":"Designation ID","designation_date":"Designation Date",
        "target_type":"Target Type","target_name":"Target Name",
        "imo_identifier":"IMO / Identifier","imo_or_identifier":"IMO / Identifier",
        "identifier":"IMO / Identifier","regime_linkage":"Regime / Linkage",
        "designation_basis_link":"Designation Basis / Link",
        "model_coverage_status":"Model Coverage Status",
        "authority_id":"Authority ID","authority_name":"Authority",
        "programme_id":"Programme ID","program_id":"Programme ID",
        "programme_name":"Programme","program_name":"Programme",
        "authority_sponsor":"Authority / Sponsor",
        "jurisdiction_geography":"Jurisdiction / Geography",
        "regime_type":"Regime Type","effective_observed_from":"Effective / Observed From",
        "enforcement_mechanisms":"Enforcement Mechanisms",
        "legal_analytical_note":"Legal / Analytical Note",
        "direct_indirect":"Direct / Indirect","reason_basis":"Reason / Basis",
        "source_vessel":"Source Vessel","counterparty_related_entity":"Counterparty / Related Entity",
        "related_entity_type":"Related Entity Type","event_geography":"Event / Geography",
        "exposure_type":"Exposure Type","analytical_note":"Analytical Note",
        "classification_rule":"Classification Rule",
        "legal_analytical_effect":"Legal / Analytical Effect",
        "last_verified":"Last Verified","effective_date":"Effective Date",
        "restriction_type":"Restriction Type",
    }
    for c in out.columns:
        key=str(c).strip().casefold().replace(" ","_").replace("/","_").replace("-","_")
        key=re.sub(r"_+","_",key).strip("_")
        rename[c]=special.get(key," ".join(w.capitalize() for w in key.split("_")))
    return out.rename(columns=rename)

def _policy_live_first(legacy_df, table_candidates, dedupe_cols=None):
    """Canonical Supabase first; workbook rows are migration fallback only."""
    live,table=_live_policy_rows(table_candidates)
    live=_policy_title_columns(live)
    legacy=legacy_df.copy() if legacy_df is not None else pd.DataFrame()
    if live.empty:
        return legacy, "Legacy migration fallback"
    if legacy.empty:
        return live, f"Live canonical · {table}"
    combined=pd.concat([live,legacy],ignore_index=True,sort=False)
    keys=[c for c in (dedupe_cols or []) if c in combined.columns]
    if keys:
        combined=combined.drop_duplicates(subset=keys,keep="first")
    return combined, f"Live canonical · {table} + fallback"


def _security_business_event_frame():
    """Build the commercial-security layer from the shared live event tables."""
    candidates=[]
    for key in [
        ("Intelligence","Events"),
        ("Intelligence","Event Register"),
        ("Events","Events"),
        ("Maritime","Security Events"),
        ("Trade","Events"),
    ]:
        df=TABLES.get(key,pd.DataFrame())
        if df is not None and not df.empty:
            candidates.append(df.copy())

    # Fall back to any obvious event dataframe exposed by the app.
    for name in ("EVENTS","events","event_df","hazard_events"):
        obj=globals().get(name)
        if isinstance(obj,pd.DataFrame) and not obj.empty:
            candidates.append(obj.copy())

    if not candidates:
        return pd.DataFrame()

    df=pd.concat(candidates,ignore_index=True,sort=False)

    # Normalize a compact set of analytical columns without discarding source columns.
    def first_col(names):
        for n in names:
            if n in df.columns:
                return df[n]
        return pd.Series("",index=df.index)

    out=df.copy()
    out["Event Date"]=first_col(["Start Date","Date","Event Date","event_date","start_date"])
    out["Title"]=first_col(["Title","Event","Event Title","title","event_title"])
    out["Event Type"]=first_col(["Event Type","Type","Category","event_type","category"])
    out["Severity"]=first_col(["Severity","Risk","Risk Level","severity"])
    out["Status"]=first_col(["Status","Event Status","status"])
    out["Country"]=first_col(["Country / Countries","Country","country"])
    out["Location"]=first_col(["Location","Area","Region","location","region"])
    out["Operational Impact"]=first_col(["Operational Impact","Operational impact","operational_impact"])
    out["Trade / Commercial Impact"]=first_col([
        "Trade / Commercial Impact","Commercial Impact","Business Impact",
        "trade_commercial_impact","commercial_impact","business_impact"
    ])
    out["Confidence"]=first_col(["Confidence","confidence"])

    blob=(
        out["Event Type"].astype(str)+" "+
        out["Title"].astype(str)+" "+
        out["Operational Impact"].astype(str)+" "+
        out["Trade / Commercial Impact"].astype(str)
    ).str.casefold()

    security_terms = (
        "attack|strike|drone|missile|piracy|hijack|seizure|boarding|mine|explosion|"
        "conflict|war|security|military|naval|coast guard|interdiction|detention|"
        "sabotage|terror|armed|hostile|sanction|blockade|restricted zone|gps|jamming|spoof"
    )
    business_terms = (
        "port|terminal|shipping|vessel|tanker|container|cargo|trade|logistics|supply chain|"
        "freight|insurance|rate|delay|closure|disruption|export|import|energy|oil|gas|"
        "aviation|airspace|rail|road|warehouse|industrial|company|operator|crew"
    )

    sec=blob.str.contains(security_terms,regex=True,na=False)
    biz=blob.str.contains(business_terms,regex=True,na=False)

    # Keep clear security incidents, plus events explicitly carrying commercial impacts.
    commercial_text=out["Trade / Commercial Impact"].astype(str).str.strip()
    keep=sec & (biz | commercial_text.ne(""))
    filtered=out[keep].copy()
    dedupe_cols=[c for c in ["Event Date","Title","Event Type","Country","Location","Severity","Status"] if c in filtered.columns]
    if dedupe_cols:
        filtered=filtered.drop_duplicates(subset=dedupe_cols,keep="first")
    return filtered

def _sbr_priority_score(df):
    """Simple transparent display prioritisation; no hidden probability estimate."""
    if df.empty:
        return pd.Series(dtype=float)
    sev=df.get("Severity",pd.Series("",index=df.index)).astype(str).str.casefold()
    score=pd.Series(0,index=df.index,dtype=float)
    score += sev.map({
        "critical":5,"severe":5,"high":4,"elevated":3,"medium":2,"moderate":2,"low":1
    }).fillna(0)
    status=df.get("Status",pd.Series("",index=df.index)).astype(str).str.casefold()
    score += status.str.contains("active|ongoing|developing",regex=True,na=False).astype(int)*2
    impact=df.get("Trade / Commercial Impact",pd.Series("",index=df.index)).astype(str)
    score += impact.str.strip().ne("").astype(int)*2
    return score

def render_security_business_rail(limit=4):
    """Compact secondary security drawer for the Trade overview."""
    df=_security_business_event_frame()

    with st.expander("Security & disruption", expanded=False):
        st.caption("Secondary lens — only incidents with a clear trade or operational consequence.")

        if df is None or df.empty:
            st.caption("No current security-linked trade disruptions.")
            return

        x=df.copy()
        x["_priority"]=_sbr_priority_score(x)
        x["_date_sort"]=pd.to_datetime(x["Event Date"],errors="coerce")
        x=x.sort_values(["_priority","_date_sort"],ascending=[False,False],na_position="last").head(limit)

        for _,r in x.iterrows():
            title=str(r.get("Title","") or "Security-linked disruption").strip()
            sev=str(r.get("Severity","") or "Unrated").strip()
            loc=str(r.get("Location","") or r.get("Country","") or "").strip()
            impact=str(r.get("Trade / Commercial Impact","") or r.get("Operational Impact","") or "").strip()
            if len(impact) > 110:
                impact = impact[:107].rstrip() + "…"

            st.markdown(f"**{title}**")
            meta=" · ".join(z for z in [sev,loc] if z)
            if meta:
                st.caption(meta)
            if impact:
                st.write(impact)
            st.divider()

        if st.button("Open security-to-business view", use_container_width=True, key="overview_open_security_business"):
            request_nav("Security & Business Risk")
            st.rerun()

def render_security_business_risk():
    df=_security_business_event_frame()

    st.caption(
        "This page sits behind the main Trade view: security incidents are included only where they create "
        "a meaningful operational, commercial, corridor, infrastructure or company consequence."
    )

    if df.empty:
        st.info("No security-linked commercial events are available in the current canonical/migration layer.")
        return

    df=df.copy()
    df["_priority"]=_sbr_priority_score(df)
    df["_date_sort"]=pd.to_datetime(df["Event Date"],errors="coerce")
    df=df.sort_values(["_priority","_date_sort"],ascending=[False,False],na_position="last")

    c1,c2,c3,c4=st.columns(4)
    c1.metric("Security-linked events",len(df))
    c2.metric("High / severe",int(df["Severity"].astype(str).str.contains("High|Severe|Critical",case=False,regex=True,na=False).sum()))
    c3.metric("Active / developing",int(df["Status"].astype(str).str.contains("Active|Ongoing|Developing",case=False,regex=True,na=False).sum()))
    c4.metric("Commercial impact recorded",int(df["Trade / Commercial Impact"].astype(str).str.strip().ne("").sum()))

    st.markdown("### Priority security-to-business picture")
    st.caption(
        "Prioritised by reported severity, active status and whether a commercial impact has been recorded. "
        "This is a display order, not a forecast probability."
    )
    showcols=[
        "Event Date","Title","Event Type","Severity","Status","Country","Location",
        "Operational Impact","Trade / Commercial Impact","Confidence"
    ]
    display_df(df[[c for c in showcols if c in df.columns]].head(20),520)

    st.markdown("### Filter by consequence")
    f1,f2,f3=st.columns(3)
    q=f1.text_input("Search",placeholder="Hormuz, port strike, tanker, airspace...",key="sbr_search")
    countries=sorted([x for x in df["Country"].fillna("").astype(str).unique() if x.strip()])
    country=f2.selectbox("Country / geography",["All"]+countries,key="sbr_country")
    severity_opts=sorted([x for x in df["Severity"].fillna("").astype(str).unique() if x.strip()])
    sev=f3.selectbox("Severity",["All"]+severity_opts,key="sbr_severity",
                     format_func=lambda v:pc_format_filter_option(v,"Severity"))

    x=df.copy()
    if q.strip():
        mask=pd.Series(False,index=x.index)
        for c in ["Title","Event Type","Country","Location","Operational Impact","Trade / Commercial Impact"]:
            mask |= x[c].astype(str).str.contains(q,case=False,na=False,regex=False)
        x=x[mask]
    if country!="All":
        x=x[x["Country"].astype(str).eq(country)]
    if sev!="All":
        x=x[x["Severity"].astype(str).eq(sev)]

    tabs=st.tabs([
        "All security-business events",
        "Maritime & Ports",
        "Energy & Industry",
        "Aviation",
        "Supply Chain / Logistics",
    ])

    def subset_terms(frame,terms):
        if frame.empty:
            return frame
        blob=(
            frame["Title"].astype(str)+" "+
            frame["Event Type"].astype(str)+" "+
            frame["Operational Impact"].astype(str)+" "+
            frame["Trade / Commercial Impact"].astype(str)
        )
        return frame[blob.str.contains("|".join(terms),case=False,regex=True,na=False)]

    with tabs[0]:
        display_df(x[[c for c in showcols if c in x.columns]],600)

    with tabs[1]:
        y=subset_terms(x,["ship","vessel","port","terminal","tanker","container","maritime","strait","sea","piracy"])
        display_df(y[[c for c in showcols if c in y.columns]],500) if not y.empty else st.info("No matching maritime/port security-business events.")

    with tabs[2]:
        y=subset_terms(x,["oil","gas","lng","refinery","pipeline","energy","power","industrial","plant"])
        display_df(y[[c for c in showcols if c in y.columns]],500) if not y.empty else st.info("No matching energy/industry security-business events.")

    with tabs[3]:
        y=subset_terms(x,["airspace","airport","aviation","airline","flight","drone"])
        display_df(y[[c for c in showcols if c in y.columns]],500) if not y.empty else st.info("No matching aviation security-business events.")

    with tabs[4]:
        y=subset_terms(x,["logistics","supply chain","freight","warehouse","rail","road","truck","cargo","delay","closure","disruption"])
        display_df(y[[c for c in showcols if c in y.columns]],500) if not y.empty else st.info("No matching logistics/supply-chain security-business events.")

    st.markdown("### Why it matters")
    st.caption(
        "The Trade app should not duplicate the Intelligence app. This layer translates security reporting into "
        "business consequences: operational disruption, corridor exposure, port/terminal effects, vessel risk, "
        "insurance/freight implications, infrastructure exposure and company impacts."
    )


def _market_db_rows(table, columns="*", limit=2000, order=None):
    """Read the normalized market layer when Supabase is configured."""
    try:
        sb=pc_db_client(service=True)
        return pc_safe_rows(sb,table,columns,limit,order=order) if sb else []
    except Exception:
        return []


def _live_frame(table, columns="*", limit=5000, order=None):
    """Read a live canonical/domain table as a DataFrame without breaking the app."""
    rows=_market_db_rows(table,columns,limit,order)
    return pd.DataFrame(rows or [])


def _filter_frame_any(df, query):
    if df is None or df.empty or not str(query or "").strip():
        return df.copy() if isinstance(df,pd.DataFrame) else pd.DataFrame()
    q=str(query).strip()
    mask=pd.Series(False,index=df.index)
    for c in df.columns:
        try:
            mask |= df[c].fillna("").astype(str).str.contains(q,case=False,na=False,regex=False)
        except Exception:
            pass
    return df[mask].copy()


def _entity_name_map():
    df=_live_frame("pc_entities","entity_id,name,entity_type,hq_country",20000)
    return dict(zip(df.get("entity_id",pd.Series(dtype=str)).astype(str),
                    df.get("name",pd.Series(dtype=str)).astype(str))) if not df.empty else {}


def _asset_name_map():
    df=_live_frame("pc_assets","asset_id,name,asset_type,subtype,country,region_city",30000)
    return dict(zip(df.get("asset_id",pd.Series(dtype=str)).astype(str),
                    df.get("name",pd.Series(dtype=str)).astype(str))) if not df.empty else {}


def _mobile_name_map():
    df=_live_frame("pc_mobile_assets","mobile_asset_id,name,asset_type,subtype,imo,flag",30000)
    return dict(zip(df.get("mobile_asset_id",pd.Series(dtype=str)).astype(str),
                    df.get("name",pd.Series(dtype=str)).astype(str))) if not df.empty else {}


def _render_connected_model_search(query):
    """Live-schema search across model areas added in the 2026 expansion."""
    if not str(query or "").strip():
        return 0

    specs=[
        # Core canonical objects first so newly loaded events/vessels/assets/companies
        # are immediately searchable without waiting for the legacy workbook index.
        ("Events","pc_events",
         "event_id,start_date,event_type,event_family,status,countries,location,title,description,operational_impact,commercial_impact,confidence,verification_status"),
        ("Vessels / mobile assets","pc_mobile_assets",
         "mobile_asset_id,name,asset_type,subtype,imo,mmsi,flag,status,metadata"),
        ("Assets","pc_assets",
         "asset_id,name,asset_type,subtype,country,region_city,status,record_status,metadata"),
        ("Companies / entities","pc_entities",
         "entity_id,name,entity_type,subtype,hq_city,hq_country,status,record_status,metadata"),
        ("Routes / corridors","pc_transport_routes",
         "route_id,route_name,mode,countries,current_status,operator_entity_id,origin_type,origin_id,destination_type,destination_id,metadata"),
        ("Transport services","pc_transport_services",
         "transport_service_id,service_name,service_code,mode,service_type,trade_lane,status,effective_start,effective_end,source_url"),
        ("Projects","pc_project_details","*"),
        ("Financing","pc_financing_facilities","*"),
        ("Contracts","pc_contracts","*"),
        ("Shipbuilding orders","pc_shipbuilding_orders","*"),
        ("Vessel designs","pc_vessel_designs","*"),
        ("Sanctions designations","pc_sanctions_designations","*"),
        ("Sanctions links","pc_sanctions_links","*"),
        ("Trade restrictions","pc_trade_restrictions","*"),
        ("Screening results","pc_screening_results","*"),
    ]
    total=0
    for title,table,cols in specs:
        df=_live_frame(table,cols,5000)
        if df.empty:
            continue
        x=_filter_frame_any(df,query)
        if x.empty:
            continue
        total+=len(x)
        with st.expander(f"{title} · {len(x)} live result(s)", expanded=title in {"Transport services","Projects","Financing","Contracts"}):
            display_df(x.head(250),420)
    return total



def _live_related_events(linked_type, linked_ids, limit=5000):
    """Fresh canonical event lookup for an entity/asset/mobile object.

    Company/asset profiles should reflect a load immediately, not wait for the
    general cached live-frame TTL.
    """
    ids={str(x) for x in linked_ids if x not in (None,"")}
    if not ids:
        return pd.DataFrame()
    try:
        sb=pc_db_client(service=True)
        if sb is not None:
            link_rows=[]
            # Small scope sets are normal on a company page; query each ID to avoid
            # backend-specific array-filter quirks.
            for lid in sorted(ids):
                rows=(sb.table("pc_event_links")
                      .select("event_id,linked_type,linked_id,linked_name,relationship,confidence")
                      .eq("linked_type",str(linked_type))
                      .eq("linked_id",lid).limit(5000).execute().data or [])
                link_rows.extend(rows)
            event_ids=sorted({str(r.get("event_id")) for r in link_rows if r.get("event_id")})
            if event_ids:
                ev_rows=[]
                for eid in event_ids:
                    rows=(sb.table("pc_events").select("*").eq("event_id",eid).limit(1).execute().data or [])
                    ev_rows.extend(rows)
                if ev_rows:
                    return pd.DataFrame(ev_rows)
    except Exception:
        pass

    links=_live_frame("pc_event_links","event_id,linked_type,linked_id,linked_name,relationship,confidence",25000)
    if links.empty:
        return pd.DataFrame()
    mask=(
        links.get("linked_type",pd.Series(index=links.index,dtype=str)).fillna("").astype(str).str.casefold().eq(str(linked_type).casefold())
        & links.get("linked_id",pd.Series(index=links.index,dtype=str)).fillna("").astype(str).isin(ids)
    )
    event_ids=set(links.loc[mask,"event_id"].dropna().astype(str))
    events=_live_frame("pc_events","*",limit,"start_date")
    if not event_ids or events.empty or "event_id" not in events.columns:
        return pd.DataFrame()
    return events[events["event_id"].astype(str).isin(event_ids)].copy()


def _linked_contracts_for_objects(object_pairs):
    links=_live_frame("pc_contract_links","*",30000)
    contracts=_live_frame("pc_contracts","*",15000,"announced_date")
    if links.empty or contracts.empty:
        return contracts.iloc[0:0].copy()
    mask=pd.Series(False,index=links.index)
    for typ,ids in object_pairs:
        ids={str(x) for x in ids if x not in (None,"")}
        if not ids:
            continue
        mask |= (
            links.get("linked_type",pd.Series(index=links.index,dtype=str)).astype(str).str.casefold().eq(str(typ).casefold())
            & links.get("linked_id",pd.Series(index=links.index,dtype=str)).astype(str).isin(ids)
        )
    cids=set(links.loc[mask,"contract_id"].dropna().astype(str))
    if not cids or "contract_id" not in contracts.columns:
        return contracts.iloc[0:0].copy()
    return contracts[contracts["contract_id"].astype(str).isin(cids)].copy()


def _linked_financing_for_objects(object_pairs):
    links=_live_frame("pc_financing_links","*",30000)
    finance=_live_frame("pc_financing_facilities","*",15000,"announced_date")
    if links.empty or finance.empty:
        return finance.iloc[0:0].copy()
    mask=pd.Series(False,index=links.index)
    for typ,ids in object_pairs:
        ids={str(x) for x in ids if x not in (None,"")}
        if not ids:
            continue
        mask |= (
            links.get("linked_type",pd.Series(index=links.index,dtype=str)).astype(str).str.casefold().eq(str(typ).casefold())
            & links.get("linked_id",pd.Series(index=links.index,dtype=str)).astype(str).isin(ids)
        )
    fids=set(links.loc[mask,"financing_id"].dropna().astype(str))
    if not fids or "financing_id" not in finance.columns:
        return finance.iloc[0:0].copy()
    return finance[finance["financing_id"].astype(str).isin(fids)].copy()


def render_connected_domain_context(domain_name, modes=(), keywords=()):
    """Shared connected-model panel used by every industry workspace."""
    modes={str(x).casefold() for x in modes}
    keywords=[str(x) for x in keywords if str(x).strip()]

    assets=_live_frame("pc_assets","*",30000)
    services=_live_frame("pc_transport_services","*",15000,"effective_start")
    projects=_live_frame("pc_project_details","*",12000,"announced_date")
    contracts=_live_frame("pc_contracts","*",12000,"announced_date")
    finance=_live_frame("pc_financing_facilities","*",12000,"announced_date")
    events=_live_frame("pc_events","*",12000,"start_date")

    if modes and not services.empty and "mode" in services.columns:
        services=services[
            services["mode"].fillna("").astype(str).str.casefold().isin(modes)
        ].copy()

    def kw_filter(df):
        if df.empty or not keywords:
            return df
        mask=pd.Series(False,index=df.index)
        for c in df.columns:
            try:
                s=df[c].fillna("").astype(str)
                for k in keywords:
                    mask |= s.str.contains(k,case=False,na=False,regex=False)
            except Exception:
                pass
        return df[mask].copy()

    domain_assets=kw_filter(assets)
    domain_projects=kw_filter(projects)
    domain_contracts=kw_filter(contracts)
    domain_finance=kw_filter(finance)

    if not events.empty:
        emask=pd.Series(False,index=events.index)
        for c in ["mode","event_domain","event_family","event_type","title","description","commercial_impact","operational_impact"]:
            if c not in events.columns:
                continue
            s=events[c].fillna("").astype(str)
            for m in modes:
                emask |= s.str.contains(m,case=False,na=False,regex=False)
            for k in keywords:
                emask |= s.str.contains(k,case=False,na=False,regex=False)
        domain_events=events[emask].copy()
    else:
        domain_events=events

    st.markdown("### Connected model")
    st.caption(
        f"{domain_name} is treated as a connected operating system: assets, services, projects, "
        "contracts, financing and disruptions share the same canonical model."
    )

    m1,m2,m3,m4,m5=st.columns(5)
    m1.metric("Assets",len(domain_assets))
    m2.metric("Services",len(services))
    m3.metric("Projects",len(domain_projects))
    m4.metric("Contracts / financing",len(domain_contracts)+len(domain_finance))
    m5.metric("Events",len(domain_events))

    tabs=st.tabs(["Assets","Services & Routes","Projects","Contracts & Financing","Events & Disruption"])
    with tabs[0]:
        display_df(domain_assets.head(500),420)
    with tabs[1]:
        display_df(services.head(500),420)
    with tabs[2]:
        display_df(domain_projects.head(500),380)
    with tabs[3]:
        display_df(domain_contracts.head(300),320)
        if not domain_finance.empty:
            st.markdown("#### Financing")
            display_df(domain_finance.head(300),320)
    with tabs[4]:
        display_df(domain_events.head(500),460)


def render_company_operating_footprint(entity_id):
    """Cross-industry group footprint for AD Ports, DP World, Maersk, CMA CGM, etc."""
    eid=str(entity_id)
    assets=_live_frame("pc_assets","*",30000)
    mobile=_live_frame("pc_mobile_assets","*",30000)

    if not assets.empty:
        mask=pd.Series(False,index=assets.index)
        for c in ["owner_entity_id","operator_entity_id"]:
            if c in assets.columns:
                mask |= assets[c].fillna("").astype(str).eq(eid)
        assets=assets[mask].copy()

    if not mobile.empty:
        mask=pd.Series(False,index=mobile.index)
        for c in ["owner_entity_id","operator_entity_id","manager_entity_id"]:
            if c in mobile.columns:
                mask |= mobile[c].fillna("").astype(str).eq(eid)
        mobile=mobile[mask].copy()

    rail=_live_frame("pc_rail_operator_details","*",5000)
    rail=rail[rail.get("entity_id",pd.Series(index=rail.index,dtype=str)).astype(str).eq(eid)].copy() if not rail.empty else pd.DataFrame()

    trucking=_live_frame("pc_trucking_company_details","*",5000)
    trucking=trucking[trucking.get("entity_id",pd.Series(index=trucking.index,dtype=str)).astype(str).eq(eid)].copy() if not trucking.empty else pd.DataFrame()

    ferry=_live_frame("pc_ferry_operator_details","*",5000)
    ferry=ferry[ferry.get("entity_id",pd.Series(index=ferry.index,dtype=str)).astype(str).eq(eid)].copy() if not ferry.empty else pd.DataFrame()

    aircraft=_live_frame("pc_aircraft_details","*",15000)
    if not aircraft.empty:
        mask=pd.Series(False,index=aircraft.index)
        for c in ["owner_entity_id","operator_entity_id","lessor_entity_id"]:
            if c in aircraft.columns:
                mask |= aircraft[c].fillna("").astype(str).eq(eid)
        aircraft=aircraft[mask].copy()

    footprint=_live_frame("pc_company_operating_footprint","*",10000)
    footprint=footprint[
        footprint.get("entity_id",pd.Series(index=footprint.index,dtype=str)).astype(str).eq(eid)
    ].copy() if not footprint.empty else pd.DataFrame()

    counts={}
    if not assets.empty and "asset_type" in assets.columns:
        counts=assets["asset_type"].fillna("Other").astype(str).value_counts().to_dict()

    cards=[
        ("Ports / terminals",sum(v for k,v in counts.items() if "port" in k.casefold() or "terminal" in k.casefold())),
        ("Rail",len(rail)+sum(v for k,v in counts.items() if "rail" in k.casefold())),
        ("Trucking / road",len(trucking)+sum(v for k,v in counts.items() if "road" in k.casefold() or "truck" in k.casefold())),
        ("Aircraft",len(aircraft)),
        ("Ferry",len(ferry)),
        ("Mobile assets",len(mobile)),
    ]
    cols=st.columns(len(cards))
    for c,(lab,val) in zip(cols,cards):
        c.metric(lab,int(val))

    tabs=st.tabs(["Physical Assets","Mobile Assets","Rail","Trucking","Aviation","Ferry","Operating Footprint"])
    with tabs[0]: display_df(assets,420)
    with tabs[1]: display_df(mobile,420)
    with tabs[2]: display_df(rail,300)
    with tabs[3]: display_df(trucking,300)
    with tabs[4]: display_df(aircraft,340)
    with tabs[5]: display_df(ferry,300)
    with tabs[6]: display_df(footprint,380)



def _port_event_bundle_live(port_id, terminal_ids, port_name, country=""):
    """Resolve port events across canonical links, locations and explicit port mentions.

    Direct canonical links are preferred.  Name/location fallback is intentionally
    conservative: it requires the port/city name, not merely the country.
    """
    pid=str(port_id or "").strip()
    tids={str(x).strip() for x in (terminal_ids or []) if str(x).strip()}
    relevant_ids={pid}|tids if pid else tids

    # Start with existing/legacy linked events so nothing regresses.
    legacy_ev,legacy_loc,legacy_ch=event_bundle_for_entities(
        asset_ids=list(relevant_ids)
    )

    events=_CANON_EVENTS.copy() if isinstance(_CANON_EVENTS,pd.DataFrame) else pd.DataFrame()
    locs=_CANON_EVENT_LOCS.copy() if isinstance(_CANON_EVENT_LOCS,pd.DataFrame) else pd.DataFrame()
    if events.empty:
        events,_loc=_canonical_db_event_frames()
        if locs.empty:
            locs=_loc

    ids=set()
    reasons={}

    def add_event(eid, reason):
        eid=str(eid or "").strip()
        if not eid:
            return
        ids.add(eid)
        reasons.setdefault(eid,[]).append(reason)

    # 1) Canonical event links by port / terminal canonical IDs.
    live_links=_live_frame(
        "pc_event_links",
        "event_id,linked_type,linked_id,linked_name,relationship,confidence",
        50000
    )
    if not live_links.empty:
        lid=live_links.get("linked_id",pd.Series(index=live_links.index,dtype=str)).fillna("").astype(str)
        exact=live_links[lid.isin(relevant_ids)]
        for _,r in exact.iterrows():
            add_event(r.get("event_id"),f"canonical {r.get('relationship') or 'asset'} link")

    # Build conservative name aliases.  "Port of Rotterdam" -> Rotterdam.
    aliases=set()
    p=str(port_name or "").strip()
    if p:
        aliases.add(p)
        short=re.sub(r"(?i)^port of\\s+","",p).strip()
        short=re.sub(r"(?i)\\s+port$","",short).strip()
        if len(short)>=4:
            aliases.add(short)

    # Add canonical terminal names as aliases too.
    assets=_live_frame("pc_assets","asset_id,name,asset_type,subtype,country,region_city",30000)
    if not assets.empty and tids:
        term_names=assets[
            assets.get("asset_id",pd.Series(index=assets.index,dtype=str)).astype(str).isin(tids)
        ].get("name",pd.Series(dtype=str)).dropna().astype(str).tolist()
        for n in term_names:
            n=n.strip()
            if len(n)>=4:
                aliases.add(n)

    # 2) Canonical event links whose linked_name explicitly names the port/terminal.
    if not live_links.empty and aliases and "linked_name" in live_links.columns:
        nm=live_links["linked_name"].fillna("").astype(str)
        name_mask=pd.Series(False,index=live_links.index)
        for a in aliases:
            name_mask |= nm.str.contains(re.escape(a),case=False,na=False,regex=True)
        for _,r in live_links[name_mask].iterrows():
            add_event(r.get("event_id"),"canonical linked-name match")

    # 3) Canonical event-location records naming the port/city.
    if not locs.empty and aliases:
        lmask=pd.Series(False,index=locs.index)
        for c in ["Location","location_name"]:
            if c in locs.columns:
                s=locs[c].fillna("").astype(str)
                for a in aliases:
                    lmask |= s.str.contains(re.escape(a),case=False,na=False,regex=True)
        for _,r in locs[lmask].iterrows():
            add_event(r.get("Event ID") or r.get("event_id"),"event-location match")

    # 4) Explicit event text mention.  This catches correctly-ingested Rotterdam
    # strikes/fires that were not yet linked to the canonical port asset.
    if not events.empty and aliases:
        search_cols=[
            c for c in [
                "Title","Description","Location","Operational Impact",
                "Trade / Commercial Impact","Event Type","Event Family"
            ] if c in events.columns
        ]
        tmask=pd.Series(False,index=events.index)
        for c in search_cols:
            s=events[c].fillna("").astype(str)
            for a in aliases:
                tmask |= s.str.contains(re.escape(a),case=False,na=False,regex=True)

        # If country is known, use it as a disambiguator, not as a primary match.
        if country and "Country / Countries" in events.columns:
            cmask=events["Country / Countries"].fillna("").astype(str).str.contains(
                re.escape(str(country)),case=False,na=False,regex=True
            )
            tmask &= cmask | ~cmask  # preserve explicit name match; country remains informational

        for _,r in events[tmask].iterrows():
            add_event(r.get("Event ID"),"explicit port/location mention")

    # Merge legacy event IDs.
    if isinstance(legacy_ev,pd.DataFrame) and not legacy_ev.empty and "Event ID" in legacy_ev.columns:
        for eid in legacy_ev["Event ID"].dropna().astype(str):
            add_event(eid,"legacy asset link")

    if not ids or events.empty or "Event ID" not in events.columns:
        return legacy_ev,legacy_loc,legacy_ch,pd.DataFrame()

    ev=events[events["Event ID"].astype(str).isin(ids)].copy()
    if "Start Date" in ev.columns:
        ev["_sort_date"]=pd.to_datetime(ev["Start Date"],errors="coerce",utc=True)
        ev=ev.sort_values("_sort_date",ascending=False).drop(columns=["_sort_date"])

    # Locations for all resolved events.
    if not locs.empty and "Event ID" in locs.columns:
        eloc=locs[locs["Event ID"].astype(str).isin(ids)].copy()
    else:
        eloc=legacy_loc

    # Existing impact-chain frame where available.
    chains=TABLES.get(("Events & Hazards","Impact Chains"),pd.DataFrame())
    if not chains.empty and "Event ID" in chains.columns:
        ech=chains[chains["Event ID"].astype(str).isin(ids)].copy()
    else:
        ech=legacy_ch

    reason_rows=[]
    for eid in sorted(ids):
        reason_rows.append({
            "Event ID":eid,
            "Why linked":"; ".join(dict.fromkeys(reasons.get(eid,[])))
        })
    audit=pd.DataFrame(reason_rows)
    return ev,eloc,ech,audit


def render_port_connected_dossier(port_row, terminals):
    """Selected port as a connected commercial / operational dossier."""
    raw_pid=str(port_row.get("Port ID") or port_row.get("asset_id") or "")
    pid=_canonical_live_asset_id(raw_pid) if raw_pid and not raw_pid.startswith("REF_") else raw_pid
    pname=str(port_row.get("Port / Facility") or port_row.get("name") or "")
    country=str(port_row.get("Country") or port_row.get("country") or "")

    terminal_details=_live_frame("pc_terminal_details","*",10000)
    asset_rows=_live_frame("pc_assets","*",30000)

    live_t=terminal_details[
        terminal_details.get("parent_port_asset_id",pd.Series(index=terminal_details.index,dtype=str)).astype(str).eq(pid)
    ].copy() if not terminal_details.empty else pd.DataFrame()

    terminal_ids=set(live_t.get("asset_id",pd.Series(dtype=str)).dropna().astype(str))
    if not terminals.empty and "Terminal ID" in terminals.columns:
        terminal_ids |= set(terminals["Terminal ID"].dropna().astype(str))

    if not live_t.empty and not asset_rows.empty and "asset_id" in asset_rows.columns:
        amap=dict(zip(asset_rows["asset_id"].astype(str),asset_rows["name"].astype(str)))
        live_t["Terminal"]=live_t["asset_id"].astype(str).map(amap).fillna(live_t["asset_id"].astype(str))

    berths=_live_frame("pc_berth_details","*",15000)
    if not berths.empty and "terminal_asset_id" in berths.columns:
        berths=berths[berths["terminal_asset_id"].astype(str).isin(terminal_ids)].copy()

    if not berths.empty and not asset_rows.empty and "asset_id" in asset_rows.columns:
        bnames=dict(zip(asset_rows["asset_id"].astype(str),asset_rows["name"].astype(str)))
        berths["Berth"]=berths["asset_id"].astype(str).map(bnames).fillna(berths["asset_id"].astype(str))
        if "terminal_asset_id" in berths.columns:
            berths["Terminal"]=berths["terminal_asset_id"].astype(str).map(bnames).fillna("")

    capabilities=_live_frame("pc_port_capabilities","*",5000)
    if not capabilities.empty and "port_asset_id" in capabilities.columns:
        capabilities=capabilities[capabilities["port_asset_id"].astype(str).eq(pid)].copy()

    port_metrics=_live_frame("pc_port_metrics","*",20000,"observation_date")
    if not port_metrics.empty and "port_asset_id" in port_metrics.columns:
        port_metrics=port_metrics[port_metrics["port_asset_id"].astype(str).eq(pid)].copy()
        if "observation_date" in port_metrics.columns:
            port_metrics=port_metrics.sort_values("observation_date",ascending=False)

    scenario_metrics=_live_frame("pc_port_scenario_metrics","*",10000)
    if not scenario_metrics.empty and "canonical_port_id" in scenario_metrics.columns:
        scenario_metrics=scenario_metrics[scenario_metrics["canonical_port_id"].astype(str).eq(pid)].copy()

    stops=_live_frame("pc_transport_service_stops","*",50000)
    if not stops.empty:
        smask=stops.get("asset_id",pd.Series(index=stops.index,dtype=str)).astype(str).eq(pid)
        if "terminal_asset_id" in stops.columns and terminal_ids:
            smask |= stops["terminal_asset_id"].astype(str).isin(terminal_ids)
        pstops=stops[smask].copy()
        service_ids=set(pstops.get("transport_service_id",pd.Series(dtype=str)).dropna().astype(str))
    else:
        pstops=pd.DataFrame()
        service_ids=set()

    services=_live_frame("pc_transport_services","*",15000,"effective_start")
    pservices=services[
        services.get("transport_service_id",pd.Series(index=services.index,dtype=str)).astype(str).isin(service_ids)
    ].copy() if service_ids and not services.empty else pd.DataFrame()

    contracts=_linked_contracts_for_objects([("asset",{pid}|terminal_ids)])
    finance=_linked_financing_for_objects([("asset",{pid}|terminal_ids)])

    tx=_live_frame("pc_transactions","*",15000,"announced_date")
    if not tx.empty and "target_asset_id" in tx.columns:
        tx=tx[tx["target_asset_id"].astype(str).isin({pid}|terminal_ids)].copy()

    calls=_live_frame("pc_port_calls","*",20000,"arrival_at")
    if not calls.empty:
        cmask=calls.get("port_asset_id",pd.Series(index=calls.index,dtype=str)).astype(str).eq(pid)
        if "terminal_asset_id" in calls.columns and terminal_ids:
            cmask |= calls["terminal_asset_id"].astype(str).isin(terminal_ids)
        calls=calls[cmask].copy()

    mobile=_live_frame("pc_mobile_assets","mobile_asset_id,name,imo,flag,asset_type,subtype,status",30000)
    if not calls.empty and not mobile.empty and "mobile_asset_id" in calls.columns:
        mmap=dict(zip(mobile["mobile_asset_id"].astype(str),mobile["name"].astype(str)))
        calls["Vessel / Mobile Asset"]=calls["mobile_asset_id"].astype(str).map(mmap).fillna(calls["mobile_asset_id"].astype(str))

    ev,loc,chains,event_link_audit=_port_event_bundle_live(
        pid,terminal_ids,pname,country
    )

    projects=_live_frame("pc_project_details","*",12000,"announced_date")
    relationships=_live_frame("pc_relationships","*",30000)
    project_ids=set()
    if not relationships.empty:
        relevant={pid}|terminal_ids
        for _,r in relationships.iterrows():
            src_t=str(r.get("source_type") or "").casefold()
            tgt_t=str(r.get("target_type") or "").casefold()
            src=str(r.get("source_id") or "")
            tgt=str(r.get("target_id") or "")
            if src_t=="asset" and src in relevant and tgt_t=="asset":
                project_ids.add(tgt)
            if tgt_t=="asset" and tgt in relevant and src_t=="asset":
                project_ids.add(src)
    if not projects.empty and project_ids and "asset_id" in projects.columns:
        projects=projects[projects["asset_id"].astype(str).isin(project_ids)].copy()
    elif not projects.empty:
        projects=_filter_frame_any(projects,pname)

    ref=global_port_reference_view()
    ref_match=pd.DataFrame()
    if not ref.empty:
        cols=[c for c in ["Port Name","name","Country Name"] if c in ref.columns]
        if cols:
            ref_match=_contains_any(ref,[pname],cols)
            if country and not ref_match.empty and "Country Name" in ref_match.columns:
                exact=ref_match[ref_match["Country Name"].astype(str).str.contains(country,case=False,na=False,regex=False)]
                if not exact.empty:
                    ref_match=exact

    tabs=st.tabs([
        "Overview & Site",
        "Terminals & Berths",
        "Services & Routes",
        "Events & Strikes",
        "Projects & Development",
        "Contracts & Financing",
        "Commercial & Ownership",
        "Port Calls & Vessels",
        "Evidence"
    ])

    with tabs[0]:
        s1,s2,s3,s4=st.columns(4)
        s1.metric("Terminals",len(live_t) if not live_t.empty else len(terminals))
        s2.metric("Berths",len(berths))
        berth_total=None
        if not live_t.empty and "berth_count" in live_t.columns:
            berth_total=pd.to_numeric(live_t["berth_count"],errors="coerce").sum(min_count=1)
        if pd.notna(berth_total) if berth_total is not None else False:
            s2.caption(f"Terminal-reported berth count: {int(berth_total)}")
        s3.metric("Services",len(pservices))
        s4.metric("Port calls",len(calls))

        display_df(pd.DataFrame([port_row]),140)

        if not capabilities.empty:
            st.markdown("#### Port capabilities")
            display_df(capabilities,260)

        if not port_metrics.empty:
            st.markdown("#### Latest port metrics")
            display_df(port_metrics.head(30),300)

        if not ref_match.empty:
            st.markdown("#### Port reference / site information")
            display_df(ref_match.head(10),220)

        render_portwatch_port_snapshot(pname,country)

    with tabs[1]:
        if not live_t.empty:
            st.markdown("#### Canonical terminal detail")
            display_df(live_t,360)
        elif not terminals.empty:
            st.markdown("#### Terminal register")
            display_df(terminals,320)

        if not berths.empty:
            st.markdown("#### Canonical berths")
            display_cols=[
                c for c in [
                    "Berth","Terminal","berth_code","berth_type","length_m",
                    "depth_m","max_vessel_length_m","status","source_id"
                ] if c in berths.columns
            ]
            display_df(berths[display_cols] if display_cols else berths,360)
        else:
            st.info(
                "No berth-level records are loaded for the canonical terminals yet. "
                "Use Port Enrichment in Power Admin to research and stage berth details."
            )

    with tabs[2]:
        display_df(pservices,420)
        if not pstops.empty:
            st.markdown("#### Calls in service rotations")
            display_df(pstops,360)

    with tabs[3]:
        if ev.empty:
            st.info(
                "No port-specific events were resolved through canonical links, "
                "event locations or explicit port-name mentions."
            )
        else:
            c1,c2,c3=st.columns(3)
            c1.metric("Linked events",len(ev))
            if "Event Family" in ev.columns:
                c2.metric("Event families",ev["Event Family"].fillna("").astype(str).replace("",pd.NA).dropna().nunique())
            else:
                c2.metric("Event families",0)
            if "Severity" in ev.columns:
                c3.metric("High / critical",int(ev["Severity"].fillna("").astype(str).str.casefold().isin(["high","critical"]).sum()))
            else:
                c3.metric("High / critical",0)

            render_event_cards(ev,60)
            if not loc.empty:
                render_event_map(ev,loc,f"Events affecting {pname}")

            if isinstance(event_link_audit,pd.DataFrame) and not event_link_audit.empty:
                with st.expander("Why these events are linked to this port"):
                    display_df(event_link_audit,260)

    with tabs[4]:
        display_df(projects,420)

    with tabs[5]:
        display_df(contracts,360)
        if not finance.empty:
            st.markdown("#### Financing")
            display_df(finance,340)

    with tabs[6]:
        display_df(tx,360)
        render_port_commercial_network(port_row,terminals)
        render_port_governance(port_row)

    with tabs[7]:
        display_df(calls,420)

    with tabs[8]:
        if not chains.empty:
            st.markdown("#### Impact chains")
            display_df(chains,260)
        if isinstance(event_link_audit,pd.DataFrame) and not event_link_audit.empty:
            st.markdown("#### Event-link resolution")
            display_df(event_link_audit,260)
        if not scenario_metrics.empty:
            st.markdown("#### Port scenario metrics")
            display_df(scenario_metrics,280)
        st.markdown("#### Port source record")
        display_df(pd.DataFrame([port_row]),160)


def render_transport_services_workspace():
    header(
        "Services & Routes",
        "Scheduled maritime, ferry, rail, aviation, road and intermodal services connected to canonical companies, ports, terminals, mobile assets and network exposure."
    )

    services=_live_frame("pc_transport_services","*",10000,"effective_start")
    operators=_live_frame("pc_transport_service_operators","*",20000)
    stops=_live_frame("pc_transport_service_stops","*",50000)
    schedules=_live_frame("pc_transport_service_schedules","*",20000)
    transit=_live_frame("pc_transport_service_transit_times","*",50000)
    mobile=_live_frame("pc_transport_service_mobile_assets","*",20000)
    network=_live_frame("pc_transport_service_network_links","*",50000)
    changes=_live_frame("pc_transport_service_changes","*",20000,"effective_date")
    sources=_live_frame("pc_transport_service_sources","*",20000,"published_at")
    connections=_live_frame("pc_transport_service_connections","*",20000)

    if services.empty:
        st.info("No canonical transport-service records are loaded yet.")
        return

    entity_names=_entity_name_map()
    asset_names=_asset_name_map()
    mobile_names=_mobile_name_map()

    s=services.copy()
    if "primary_operator_entity_id" in s.columns:
        s["Primary Operator"]=s["primary_operator_entity_id"].astype(str).map(entity_names).fillna("")
    if "origin_asset_id" in s.columns:
        s["Origin"]=s["origin_asset_id"].astype(str).map(asset_names).fillna("")
    if "destination_asset_id" in s.columns:
        s["Destination"]=s["destination_asset_id"].astype(str).map(asset_names).fillna("")

    f1,f2,f3=st.columns([1.8,1,1])
    q=f1.text_input("Find service / code / operator / trade lane",placeholder="GEX3, OOCL, Montreal, Mediterranean...",key="service_search")
    modes=["All"]+sorted([x for x in s.get("mode",pd.Series(dtype=str)).dropna().astype(str).unique() if x])
    statuses=["All"]+sorted([x for x in s.get("status",pd.Series(dtype=str)).dropna().astype(str).unique() if x])
    mode=f2.selectbox("Mode",modes,format_func=lambda v:"All" if v=="All" else pretty_enum(v),key="service_mode")
    status=f3.selectbox("Status",statuses,format_func=lambda v:"All" if v=="All" else pretty_enum(v),key="service_status")

    view=_filter_frame_any(s,q) if q else s.copy()
    if mode!="All" and "mode" in view.columns:
        view=view[view["mode"].astype(str).eq(mode)]
    if status!="All" and "status" in view.columns:
        view=view[view["status"].astype(str).eq(status)]

    m1,m2,m3,m4=st.columns(4)
    m1.metric("Services",len(view))
    m2.metric("Operators",operators["entity_id"].nunique() if not operators.empty and "entity_id" in operators.columns else 0)
    m3.metric("Scheduled stops",len(stops))
    m4.metric("Service changes",len(changes))

    display_cols=[
        "service_name","service_code","mode","service_type","trade_lane",
        "Primary Operator","Origin","Destination","frequency_value","frequency_unit",
        "status","announced_date","effective_start","effective_end"
    ]
    display_df(view[[c for c in display_cols if c in view.columns]],420)

    if view.empty:
        return
    pick=st.selectbox(
        "Open service",
        range(len(view.reset_index(drop=True))),
        format_func=lambda i:(
            f"{view.reset_index(drop=True).iloc[i].get('service_name','')}"
            + (f" · {view.reset_index(drop=True).iloc[i].get('service_code')}" if view.reset_index(drop=True).iloc[i].get("service_code") else "")
            + (f" · {pretty_enum(view.reset_index(drop=True).iloc[i].get('mode'))}" if view.reset_index(drop=True).iloc[i].get("mode") else "")
        ),
        key="transport_service_pick"
    )
    sr=view.reset_index(drop=True).iloc[pick]
    sid=str(sr.get("transport_service_id",""))
    st.markdown(f"## {sr.get('service_name','Transport service')}")
    st.caption(" · ".join([x for x in [
        pretty_enum(sr.get("mode")),
        pretty_enum(sr.get("service_type")),
        str(sr.get("trade_lane") or ""),
        pretty_enum(sr.get("status"))
    ] if x]))

    sop=operators[operators["transport_service_id"].astype(str).eq(sid)].copy() if not operators.empty and "transport_service_id" in operators.columns else pd.DataFrame()
    sst=stops[stops["transport_service_id"].astype(str).eq(sid)].copy() if not stops.empty and "transport_service_id" in stops.columns else pd.DataFrame()
    ssc=schedules[schedules["transport_service_id"].astype(str).eq(sid)].copy() if not schedules.empty and "transport_service_id" in schedules.columns else pd.DataFrame()
    strans=transit[transit["transport_service_id"].astype(str).eq(sid)].copy() if not transit.empty and "transport_service_id" in transit.columns else pd.DataFrame()
    sma=mobile[mobile["transport_service_id"].astype(str).eq(sid)].copy() if not mobile.empty and "transport_service_id" in mobile.columns else pd.DataFrame()
    snet=network[network["transport_service_id"].astype(str).eq(sid)].copy() if not network.empty and "transport_service_id" in network.columns else pd.DataFrame()
    sch=changes[changes["transport_service_id"].astype(str).eq(sid)].copy() if not changes.empty and "transport_service_id" in changes.columns else pd.DataFrame()
    ssrc=sources[sources["transport_service_id"].astype(str).eq(sid)].copy() if not sources.empty and "transport_service_id" in sources.columns else pd.DataFrame()
    scon=connections[
        connections.get("from_transport_service_id",pd.Series(index=connections.index,dtype=str)).astype(str).eq(sid)
        | connections.get("to_transport_service_id",pd.Series(index=connections.index,dtype=str)).astype(str).eq(sid)
    ].copy() if not connections.empty else pd.DataFrame()

    if not sop.empty and "entity_id" in sop.columns:
        sop["Operator"]=sop["entity_id"].astype(str).map(entity_names).fillna(sop["entity_id"].astype(str))
    if not sst.empty:
        if "asset_id" in sst.columns:
            sst["Stop"]=sst["asset_id"].astype(str).map(asset_names).fillna(sst["asset_id"].astype(str))
        if "terminal_asset_id" in sst.columns:
            sst["Terminal"]=sst["terminal_asset_id"].astype(str).map(asset_names).fillna("")
        if "sequence_no" in sst.columns:
            sst=sst.sort_values(["direction","sequence_no"] if "direction" in sst.columns else ["sequence_no"])
    if not sma.empty and "mobile_asset_id" in sma.columns:
        sma["Mobile Asset"]=sma["mobile_asset_id"].astype(str).map(mobile_names).fillna(sma["mobile_asset_id"].astype(str))
    if not snet.empty and "asset_id" in snet.columns:
        snet["Network / Asset"]=snet["asset_id"].astype(str).map(asset_names).fillna(snet["asset_id"].astype(str))

    tabs=st.tabs(["Rotation","Operators","Schedule & Transit","Assigned Assets","Network Exposure","Changes","Connections & Sources"])
    with tabs[0]:
        display_df(sst[[c for c in ["direction","sequence_no","Stop","Terminal","call_type","arrival_day_offset","departure_day_offset","is_origin","is_destination","is_transshipment","valid_from","valid_to"] if c in sst.columns]],520)
    with tabs[1]:
        display_df(sop[[c for c in ["Operator","operator_role","marketing_code","capacity_share_percent","valid_from","valid_to","is_current"] if c in sop.columns]],320)
    with tabs[2]:
        display_df(ssc,260)
        if not strans.empty:
            st.markdown("### Transit times")
            if "from_asset_id" in strans.columns: strans["From"]=strans["from_asset_id"].astype(str).map(asset_names).fillna("")
            if "to_asset_id" in strans.columns: strans["To"]=strans["to_asset_id"].astype(str).map(asset_names).fillna("")
            display_df(strans[[c for c in ["direction","From","To","transit_hours","transit_days","distance_km","valid_from","valid_to"] if c in strans.columns]],360)
    with tabs[3]:
        display_df(sma[[c for c in ["Mobile Asset","service_role","voyage_number","valid_from","valid_to","is_current"] if c in sma.columns]],360)
    with tabs[4]:
        display_df(snet[[c for c in ["Network / Asset","relationship_type","direction","sequence_no","exposure_required"] if c in snet.columns]],420)
    with tabs[5]:
        display_df(sch[[c for c in ["change_type","announced_date","effective_date","effective_end_date","title","summary","confidence","source_url"] if c in sch.columns]],420)
    with tabs[6]:
        if not scon.empty:
            display_df(scon,260)
        display_df(ssrc[[c for c in ["source_type","source_title","source_url","published_at","is_primary","supports_current_rotation"] if c in ssrc.columns]],320)


def render_deals_projects_contracts_workspace():
    header(
        "Deals, Projects & Contracts",
        "Transactions, infrastructure projects, financing facilities, commercial contracts and shipbuilding orders from the connected P&C model."
    )

    tx=_live_frame("pc_transactions","*",10000,"announced_date")
    projects=_live_frame("pc_project_details","*",10000,"announced_date")
    assets=_live_frame("pc_assets","asset_id,name,asset_type,subtype,country,region_city,status",30000)
    finance=_live_frame("pc_financing_facilities","*",10000,"announced_date")
    fparts=_live_frame("pc_financing_participants","*",20000)
    flinks=_live_frame("pc_financing_links","*",20000)
    contracts=_live_frame("pc_contracts","*",10000,"announced_date")
    cparts=_live_frame("pc_contract_participants","*",20000)
    clinks=_live_frame("pc_contract_links","*",20000)
    designs=_live_frame("pc_vessel_designs","*",10000)
    orders=_live_frame("pc_shipbuilding_orders","*",10000,"announced_date")
    units=_live_frame("pc_shipbuilding_order_units","*",20000)

    q=st.text_input("Search deals / projects / financing / contracts / shipbuilding",placeholder="Mobile, TIFIA, AD Ports, CU Lines, Hudong-Zhonghua...",key="deal_model_search")
    frames={
        "Transactions":_filter_frame_any(tx,q) if q else tx,
        "Projects":_filter_frame_any(projects,q) if q else projects,
        "Financing":_filter_frame_any(finance,q) if q else finance,
        "Contracts":_filter_frame_any(contracts,q) if q else contracts,
        "Shipbuilding":_filter_frame_any(orders,q) if q else orders,
    }

    m1,m2,m3,m4,m5=st.columns(5)
    m1.metric("Transactions",len(frames["Transactions"]))
    m2.metric("Projects",len(frames["Projects"]))
    m3.metric("Financing",len(frames["Financing"]))
    m4.metric("Contracts",len(frames["Contracts"]))
    m5.metric("Ship orders",len(frames["Shipbuilding"]))

    tabs=st.tabs(["Transactions","Projects","Financing","Contracts","Shipbuilding Orders"])
    with tabs[0]:
        display_df(frames["Transactions"],500)
    with tabs[1]:
        p=frames["Projects"].copy()
        if not p.empty and "asset_id" in p.columns and not assets.empty:
            amap=dict(zip(assets["asset_id"].astype(str),assets["name"].astype(str)))
            p["Project"]=p["asset_id"].astype(str).map(amap).fillna(p["asset_id"].astype(str))
        display_df(p,500)
    with tabs[2]:
        display_df(frames["Financing"],420)
        if not fparts.empty:
            st.markdown("### Financing participants")
            display_df(_filter_frame_any(fparts,q) if q else fparts,320)
        if not flinks.empty:
            st.markdown("### Financing links")
            display_df(_filter_frame_any(flinks,q) if q else flinks,320)
    with tabs[3]:
        display_df(frames["Contracts"],420)
        if not cparts.empty:
            st.markdown("### Contract participants")
            display_df(_filter_frame_any(cparts,q) if q else cparts,300)
        if not clinks.empty:
            st.markdown("### Contract links")
            display_df(_filter_frame_any(clinks,q) if q else clinks,300)
    with tabs[4]:
        display_df(frames["Shipbuilding"],420)
        if not designs.empty:
            st.markdown("### Vessel designs")
            display_df(_filter_frame_any(designs,q) if q else designs,320)
        if not units.empty:
            st.markdown("### Ordered units / hulls")
            display_df(_filter_frame_any(units,q) if q else units,360)


def render_canonical_sanctions_model():
    """Canonical government sanctions, restrictions and screening layer."""
    des=_live_frame("pc_sanctions_designations","*",15000)
    links=_live_frame("pc_sanctions_links","*",30000)
    changes=_live_frame("pc_sanctions_changes","*",20000)
    restrictions=_live_frame("pc_trade_restrictions","*",15000)
    rlinks=_live_frame("pc_trade_restriction_links","*",30000)
    screening=_live_frame("pc_screening_results","*",30000)
    runs=_live_frame("pc_screening_runs","*",5000)
    if all(x.empty for x in [des,links,changes,restrictions,screening]):
        return False

    st.markdown("### Canonical sanctions & exposure model")
    c1,c2,c3,c4=st.columns(4)
    c1.metric("Designations",len(des))
    c2.metric("Designation links",len(links))
    c3.metric("Trade restrictions",len(restrictions))
    c4.metric("Screening results",len(screening))

    tabs=st.tabs(["Direct Designations","Exposure Links","Changes","Trade Restrictions","Screening"])
    with tabs[0]: display_df(des,420)
    with tabs[1]: display_df(links,420)
    with tabs[2]: display_df(changes,360)
    with tabs[3]:
        display_df(restrictions,340)
        if not rlinks.empty:
            st.markdown("#### Restriction links")
            display_df(rlinks,320)
    with tabs[4]:
        display_df(screening,420)
        if not runs.empty:
            st.markdown("#### Screening runs")
            display_df(runs,260)
    st.markdown("---")
    return True


def render_company_connected_model(entity_id,entity_name):
    bundle=_company_live_logistics_bundle(entity_id,entity_name)
    scope={str(x) for x in bundle.get("scope_ids",set()) if str(x)}; eid=str(entity_id); scope.add(eid)
    st.caption("Connected Network shows how the company sits inside the logistics cycle: ownership and leadership, operating companies, services and routes, physical infrastructure, projects/contracts/finance, events and risk. It is mode-neutral.")
    relationships=bundle.get("live_relationships",pd.DataFrame()); services=bundle.get("services",pd.DataFrame()); stops=bundle.get("service_stops",pd.DataFrame()); footprint=bundle.get("footprint",pd.DataFrame()); assets=bundle.get("live_assets",pd.DataFrame()); events=bundle.get("events",pd.DataFrame())
    metrics=[]
    for lab,df in [("Relationships",relationships),("Services / routes",services),("Service stops",stops),("Footprint records",footprint),("Physical assets",assets),("Linked events",events)]:
        if isinstance(df,pd.DataFrame) and not df.empty: metrics.append((lab,len(df)))
    if metrics:
        cols=st.columns(min(len(metrics),6))
        for c,(lab,val) in zip(cols,metrics[:6]): c.metric(lab,val)
    tabs=st.tabs(["Relationships","Services & Routes","Operating Network","Deals / Projects / Finance","Events & Disruptions","Sanctions & Exposure"])
    with tabs[0]:
        st.markdown("### Corporate, leadership & operating relationships"); readable_relationships(relationships,eid)
        if isinstance(relationships,pd.DataFrame) and not relationships.empty:
            with st.expander("Canonical relationship rows",expanded=False): display_df(relationships,600)
    with tabs[1]:
        if isinstance(services,pd.DataFrame) and not services.empty: st.markdown("### Transport services"); display_df(services,700)
        else: st.info("No canonical service records are linked to this company yet.")
        if isinstance(stops,pd.DataFrame) and not stops.empty: st.markdown("### Rotations / stops"); display_df(stops,1200)
        ops=bundle.get("service_operators",pd.DataFrame())
        if isinstance(ops,pd.DataFrame) and not ops.empty:
            with st.expander("Operator / partner roles",expanded=False): display_df(ops,500)
    with tabs[2]:
        render_company_operating_footprint(eid)
        if isinstance(assets,pd.DataFrame) and not assets.empty: st.markdown("### Physical infrastructure"); display_df(assets,700)
        for title,key in [("Road corridors","road_corridors"),("Rail networks","rail_networks"),("Rail nodes","rail_nodes"),("Rail links","rail_links")]:
            df=bundle.get(key,pd.DataFrame())
            if isinstance(df,pd.DataFrame) and not df.empty: st.markdown(f"### {title}"); display_df(df,700)
    with tabs[3]:
        any_rows=False
        for title,key in [("Transactions","transactions"),("Projects","projects"),("Financing","financing"),("Contracts","contracts")]:
            df=bundle.get(key,pd.DataFrame())
            if isinstance(df,pd.DataFrame) and not df.empty: any_rows=True; st.markdown(f"### {title}"); display_df(df,600)
        if not any_rows: st.info("No linked deal, project, financing or contract records yet.")
    with tabs[4]:
        display_df(events,800) if isinstance(events,pd.DataFrame) and not events.empty else st.info("No canonical linked events yet.")
    with tabs[5]:
        slinks=_live_frame("pc_sanctions_links","*",30000)
        if not slinks.empty:
            slinks=slinks[slinks.get("linked_type",pd.Series(index=slinks.index,dtype=str)).astype(str).str.casefold().eq("entity") & slinks.get("linked_id",pd.Series(index=slinks.index,dtype=str)).astype(str).isin(scope)].copy()
        display_df(slinks,600)


def render_vessel_connected_model(vessel_id):
    vid=str(vessel_id)
    assignments=_live_frame("pc_transport_service_mobile_assets","*",20000)
    services=_live_frame("pc_transport_services","*",10000)
    assignments=assignments[assignments.get("mobile_asset_id",pd.Series(index=assignments.index,dtype=str)).astype(str).eq(vid)].copy() if not assignments.empty else pd.DataFrame()
    sids=set(assignments.get("transport_service_id",pd.Series(dtype=str)).astype(str)) if not assignments.empty else set()
    services=services[services.get("transport_service_id",pd.Series(index=services.index,dtype=str)).astype(str).isin(sids)].copy() if sids and not services.empty else pd.DataFrame()

    slinks=_live_frame("pc_sanctions_links","*",30000)
    slinks=slinks[
        slinks.get("linked_type",pd.Series(index=slinks.index,dtype=str)).astype(str).str.casefold().eq("mobile_asset")
        & slinks.get("linked_id",pd.Series(index=slinks.index,dtype=str)).astype(str).eq(vid)
    ].copy() if not slinks.empty else pd.DataFrame()
    screening=_live_frame("pc_screening_results","*",30000)
    if not screening.empty and {"linked_type","linked_id"}.issubset(screening.columns):
        screening=screening[
            screening["linked_type"].astype(str).str.casefold().eq("mobile_asset")
            & screening["linked_id"].astype(str).eq(vid)
        ].copy()

    t1,t2=st.tabs(["Transport Services","Sanctions / Screening"])
    with t1:
        display_df(services,320)
        if not assignments.empty:
            display_df(assignments,260)
    with t2:
        display_df(slinks,320)
        if not screening.empty:
            st.markdown("#### Screening results")
            display_df(screening,320)


def render_freight_commodity_markets():
    header(
        "Freight & Commodity Markets",
        "Attributed freight, fleet-supply, congestion, commodity-flow and asset-market observations connected to the wider P&C network."
    )
    reports=_market_db_rows(
        "pc_trade_market_reports",
        "market_report_id,provider,report_family,report_title,report_date,week_number,market_scope,source_url,source_methodology",
        1000,"report_date"
    )
    obs=_market_db_rows(
        "pc_trade_market_observations",
        "market_observation_id,market_report_id,observation_date,market,vessel_class,route_code,route_description,origin_text,destination_text,commodity,metric_family,metric_name,value_numeric,value_text,unit,currency,change_wow,change_yoy,benchmark,pc_market_signal,pc_direction,pc_driver,confidence,provider,report_family,report_title,report_date,week_number,report_url",
        5000,"observation_date"
    )
    # Legacy Excel fallback: lets the old Streamlit platform test the market layer before Supabase is populated.
    if not obs:
        _excel_market=TABLES.get(("Market Intelligence Reference","Signal Market Observations"),pd.DataFrame()).copy()
        if not _excel_market.empty:
            obs=_excel_market.to_dict("records")
    if not reports and obs:
        _tmp=pd.DataFrame(obs)
        _report_cols=[c for c in ["provider","report_family","report_title","report_date","week_number","source_url"] if c in _tmp.columns]
        if _report_cols:
            rdf0=_tmp[_report_cols].drop_duplicates().copy()
            if "source_url" in rdf0.columns: rdf0=rdf0.rename(columns={"source_url":"source_url"})
            reports=rdf0.to_dict("records")
    if not reports and not obs:
        st.info("No market observations are loaded. Add approved Supabase observations or use the bundled Excel reference layer.")
        return

    rdf=pd.DataFrame(reports)
    df=pd.DataFrame(obs)
    if not df.empty:
        df["observation_date"]=pd.to_datetime(df.get("observation_date"),errors="coerce")
        df=df.sort_values("observation_date",ascending=False)

    c1,c2,c3,c4=st.columns(4)
    c1.metric("Approved observations",len(df))
    c2.metric("Source reports",len(rdf))
    c3.metric("Routes",int(df["route_code"].fillna("").astype(str).replace("",pd.NA).dropna().nunique()) if not df.empty and "route_code" in df else 0)
    c4.metric("Commodities",int(df["commodity"].fillna("").astype(str).replace("",pd.NA).dropna().nunique()) if not df.empty and "commodity" in df else 0)

    st.caption("Reported values remain attributed to their source. P&C signals/direction are analytical metadata layered on top of the reported observation.")
    tabs=st.tabs(["Market Overview","Freight Rates","Fleet & Supply","Commodity Flows","Ports & Congestion","Asset Values","Source Reports"])

    def filt(pattern):
        if df.empty: return df
        return df[df["metric_family"].fillna("").astype(str).str.contains(pattern,case=False,regex=True,na=False)].copy()

    def market_table(view,height=360):
        if view.empty:
            st.caption("No approved observations in this category yet.")
            return
        cols=[c for c in ["observation_date","market","vessel_class","route_code","route_description","origin_text","destination_text","commodity","metric_name","value_numeric","value_text","unit","currency","change_wow","change_yoy","pc_market_signal","pc_direction","confidence","provider"] if c in view.columns]
        display_df(view[cols],height)

    with tabs[0]:
        if df.empty:
            st.caption("No approved observations yet.")
        else:
            a,b=st.columns([1,1])
            with a:
                st.markdown("### Latest observations")
                market_table(df.head(40),380)
            with b:
                st.markdown("### Observation mix")
                if "metric_family" in df:
                    mix=df["metric_family"].fillna("Unknown").astype(str).value_counts().rename_axis("Metric family").reset_index(name="Observations")
                    display_df(mix,300)
            st.markdown("### Historical series")
            candidates=df[(df["value_numeric"].notna()) & (df["observation_date"].notna())].copy() if "value_numeric" in df else pd.DataFrame()
            if not candidates.empty:
                candidates["series_label"]=(candidates["route_code"].fillna("").astype(str)+" · "+candidates["metric_name"].fillna("").astype(str)+" · "+candidates["vessel_class"].fillna("").astype(str)).str.strip(" ·")
                labels=sorted([x for x in candidates["series_label"].unique() if x])
                if labels:
                    pick=st.selectbox("Series",labels,key="market_series_pick")
                    series=candidates[candidates["series_label"].eq(pick)][["observation_date","value_numeric"]].dropna().sort_values("observation_date")
                    if len(series)>=2:
                        st.line_chart(series.set_index("observation_date"),use_container_width=True)
                    else:
                        st.caption("This series currently has only one approved observation; it will chart as the historical backfill grows.")

    with tabs[1]: market_table(filt("FREIGHT_RATE|MARKET_INDEX"))
    with tabs[2]: market_table(filt("FLEET_SUPPLY|SUPPLY_DEMAND|SECURITY_MARKET"))
    with tabs[3]: market_table(filt("COMMODITY_FLOW"))
    with tabs[4]: market_table(filt("PORT_CONDITION"))
    with tabs[5]: market_table(filt("ASSET_VALUE"))
    with tabs[6]:
        if rdf.empty:
            st.caption("No source reports approved yet.")
        else:
            cols=[c for c in ["report_date","report_family","report_title","provider","week_number","source_url","source_methodology"] if c in rdf.columns]
            display_df(rdf[cols],380)


# ---------- regional trade-map helpers ----------
TRADE_REGIONS = {
    "Global": {"center": (15.0, 10.0), "zoom": 1.0, "countries": []},
    "Middle East": {"center": (25.0, 47.0), "zoom": 3.2, "countries": ["United Arab Emirates","Saudi Arabia","Oman","Qatar","Bahrain","Kuwait","Iraq","Iran","Yemen","Jordan","Lebanon","Israel","Syria"]},
    "Africa": {"center": (2.0, 20.0), "zoom": 2.1, "countries": ["Morocco","Algeria","Tunisia","Libya","Egypt","Senegal","Ghana","Nigeria","Cameroon","Kenya","Tanzania","Mozambique","South Africa","Namibia","Angola","Djibouti","Somalia","Ethiopia","Guinea","Republic of the Congo","Democratic Republic of the Congo"]},
    "Europe": {"center": (52.0, 12.0), "zoom": 2.7, "countries": ["United Kingdom","Ireland","France","Germany","Netherlands","Belgium","Spain","Portugal","Italy","Greece","Poland","Lithuania","Latvia","Estonia","Finland","Sweden","Norway","Denmark","Romania","Bulgaria","Ukraine","Georgia","Türkiye","Turkey"]},
    "North America": {"center": (42.0, -101.0), "zoom": 2.5, "countries": ["United States","Canada","Mexico"]},
    "Central America & Caribbean": {"center": (18.0, -78.0), "zoom": 3.0, "countries": ["Panama","Costa Rica","Guatemala","Honduras","El Salvador","Nicaragua","Belize","Bahamas","Haiti","Jamaica","Dominican Republic","Cuba","Trinidad and Tobago"]},
    "South America": {"center": (-18.0, -60.0), "zoom": 2.5, "countries": ["Brazil","Argentina","Chile","Uruguay","Colombia","Ecuador","Peru","Venezuela","Guyana","Suriname","Paraguay","Bolivia"]},
    "South Asia": {"center": (21.0, 78.0), "zoom": 3.0, "countries": ["India","Pakistan","Bangladesh","Sri Lanka","Nepal","Maldives"]},
    "Asia-Pacific": {"center": (16.0, 116.0), "zoom": 2.4, "countries": ["China","Japan","South Korea","Taiwan","Philippines","Indonesia","Malaysia","Singapore","Vietnam","Thailand","Australia","New Zealand","Papua New Guinea","South China Sea"]},
    "Central Asia": {"center": (43.0, 66.0), "zoom": 3.2, "countries": ["Kazakhstan","Uzbekistan","Turkmenistan","Kyrgyzstan","Tajikistan","Azerbaijan"]},
    "Arctic": {"center": (70.0, 10.0), "zoom": 2.1, "countries": ["Canada","United States","Russia","Norway","Finland","Sweden","Denmark","Iceland"]},
}


MAP_FOCUS_AREAS = {
    "Global": {
        "All activity": {"phrases": [], "center": (18.0, 12.0), "zoom": 1.1},
        "Strait of Hormuz": {"phrases": ["hormuz","khasab","musandam","fujairah","gulf of oman"], "center": (26.2, 56.3), "zoom": 5.0},
        "Red Sea / Bab el-Mandeb": {"phrases": ["red sea","bab el-mandeb","hodeidah","hudaydah","mocha","jeddah","yanbu"], "center": (17.0, 41.8), "zoom": 3.7},
        "Black Sea": {"phrases": ["black sea","odesa","odessa","novorossiysk","crimea","kerch","chornomorsk","samsun","şile","sile"], "center": (43.2, 34.0), "zoom": 4.0},
        "Panama Canal": {"phrases": ["panama canal","panama","balboa","colon","colón"], "center": (9.1, -79.7), "zoom": 6.0},
        "Malacca / Singapore": {"phrases": ["malacca","singapore strait","singapore","batam","johor"], "center": (1.6, 103.6), "zoom": 5.0},
        "South China Sea": {"phrases": ["south china sea","spratly","paracel","philippines","vietnam"], "center": (13.0, 114.0), "zoom": 3.7},
        "Baltic / Gulf of Finland": {"phrases": ["baltic","gulf of finland","tallinn","helsinki","klaipeda","gdansk","gotland"], "center": (58.0, 21.0), "zoom": 4.0},
        "Arctic / Northern Sea Route": {"phrases": ["arctic","northern sea route","murmansk","arkhangelsk","churchill","svalbard"], "center": (70.0, 35.0), "zoom": 2.4},
    },
    "Middle East": {
        "All regional activity": {"phrases": [], "center": (25.0, 47.0), "zoom": 3.2},
        "Strait of Hormuz": {"phrases": ["hormuz","khasab","musandam","fujairah","gulf of oman"], "center": (26.2, 56.3), "zoom": 5.0},
        "Northern Gulf / Iraq": {"phrases": ["basra","umm qasr","al-faw","iraq","kuwait","kharg"], "center": (29.5, 48.6), "zoom": 4.6},
        "UAE / Oman logistics": {"phrases": ["dubai","abu dhabi","jebel ali","khalifa port","fujairah","sohar","salalah","muscat"], "center": (24.0, 55.5), "zoom": 4.3},
        "Saudi Red Sea / Jazan": {"phrases": ["jazan","jizan","jeddah","yanbu","saudi red sea"], "center": (20.0, 40.0), "zoom": 4.0},
        "Red Sea / Bab el-Mandeb": {"phrases": ["red sea","bab el-mandeb","hodeidah","hudaydah","mocha"], "center": (15.0, 42.7), "zoom": 4.2},
    },
    "Middle East / Gulf": {
        "All regional activity": {"phrases": [], "center": (25.2, 51.5), "zoom": 4.0},
        "Strait of Hormuz": {"phrases": ["hormuz","khasab","musandam","fujairah","gulf of oman"], "center": (26.2, 56.3), "zoom": 5.0},
        "Northern Gulf / Iraq": {"phrases": ["basra","umm qasr","al-faw","iraq","kuwait","kharg"], "center": (29.5, 48.6), "zoom": 4.6},
        "UAE / Oman": {"phrases": ["dubai","abu dhabi","fujairah","sohar","salalah","muscat"], "center": (24.0, 55.5), "zoom": 4.3},
        "Saudi / Jazan": {"phrases": ["jazan","jizan","jeddah","yanbu","saudi"], "center": (22.5, 43.5), "zoom": 3.8},
        "Red Sea / Bab el-Mandeb": {"phrases": ["red sea","bab el-mandeb","hodeidah","hudaydah","mocha"], "center": (15.0, 42.7), "zoom": 4.2},
    },
    "Black Sea": {
        "All regional activity": {"phrases": [], "center": (43.1, 34.0), "zoom": 4.1},
        "Odesa / Chornomorsk": {"phrases": ["odesa","odessa","chornomorsk","ukraine maritime corridor"], "center": (46.3, 30.7), "zoom": 5.4},
        "Novorossiysk / CPC": {"phrases": ["novorossiysk","cpc","caspian pipeline consortium"], "center": (44.7, 37.8), "zoom": 5.2},
        "Sea of Azov / Kerch": {"phrases": ["sea of azov","azov","kerch","taganrog","mariupol","berdyansk"], "center": (46.0, 37.0), "zoom": 4.5},
        "Turkish Black Sea coast": {"phrases": ["samsun","sinop","şile","sile","turkish coast","türkiye"], "center": (41.4, 35.0), "zoom": 4.6},
        "Danube approaches": {"phrases": ["danube","constanta","constanța","sulina","izmail","reni"], "center": (45.2, 29.3), "zoom": 5.0},
    },
    "Mediterranean": {
        "All regional activity": {"phrases": [], "center": (35.5, 18.0), "zoom": 3.4},
        "Eastern Mediterranean": {"phrases": ["crete","cyprus","levant","israel","lebanon","syria","libya"], "center": (34.5, 27.5), "zoom": 4.0},
        "Suez approaches": {"phrases": ["suez","port said","alexandria","eastern mediterranean"], "center": (31.0, 31.5), "zoom": 4.6},
        "Adriatic / Aegean": {"phrases": ["adriatic","aegean","trieste","taranto","greece"], "center": (39.5, 20.0), "zoom": 4.0},
        "Gibraltar / Western Med": {"phrases": ["gibraltar","algeciras","tangier","tanger med","western mediterranean"], "center": (36.0, -4.0), "zoom": 4.4},
    },
    "Baltic": {
        "All regional activity": {"phrases": [], "center": (57.0, 19.0), "zoom": 4.0},
        "Gulf of Finland": {"phrases": ["gulf of finland","helsinki","tallinn","st petersburg","primorsk","ust-luga"], "center": (59.5, 25.0), "zoom": 5.0},
        "Poland / Baltic gateways": {"phrases": ["gdansk","gdańsk","gdynia","poland"], "center": (54.5, 18.7), "zoom": 5.2},
        "Danish Straits": {"phrases": ["danish straits","kattegat","oresund","øresund","great belt"], "center": (56.3, 11.5), "zoom": 5.0},
        "Gotland / central Baltic": {"phrases": ["gotland","central baltic","sweden"], "center": (57.5, 19.0), "zoom": 5.0},
    },
    "Caribbean": {
        "All regional activity": {"phrases": [], "center": (18.0, -72.0), "zoom": 3.8},
        "Panama Canal": {"phrases": ["panama canal","panama","balboa","colon","colón"], "center": (9.1, -79.7), "zoom": 6.0},
        "Haiti / Windward Passage": {"phrases": ["haiti","port-au-prince","windward passage"], "center": (19.0, -72.8), "zoom": 5.0},
        "Caribbean transshipment": {"phrases": ["kingston","freeport","caucedo","cartagena","caribbean"], "center": (18.0, -76.0), "zoom": 3.8},
    },
    "Central America & Caribbean": {
        "All regional activity": {"phrases": [], "center": (18.0, -78.0), "zoom": 3.0},
        "Panama Canal": {"phrases": ["panama canal","panama","balboa","colon","colón"], "center": (9.1, -79.7), "zoom": 6.0},
        "Haiti / Windward Passage": {"phrases": ["haiti","port-au-prince","windward passage"], "center": (19.0, -72.8), "zoom": 5.0},
        "Caribbean transshipment": {"phrases": ["kingston","freeport","caucedo","cartagena","caribbean"], "center": (18.0, -76.0), "zoom": 3.8},
    },
    "Asia-Pacific": {
        "All regional activity": {"phrases": [], "center": (16.0, 116.0), "zoom": 2.6},
        "Malacca / Singapore": {"phrases": ["malacca","singapore strait","singapore","batam","johor"], "center": (1.6, 103.6), "zoom": 5.0},
        "South China Sea": {"phrases": ["south china sea","spratly","paracel","philippines","vietnam"], "center": (13.0, 114.0), "zoom": 3.7},
        "Taiwan Strait": {"phrases": ["taiwan strait","taiwan","fujian"], "center": (24.2, 120.0), "zoom": 4.4},
        "East China Sea": {"phrases": ["east china sea","okinawa","zhejiang","japan"], "center": (28.0, 127.0), "zoom": 3.7},
        "Philippine Sea": {"phrases": ["philippine sea","manila","luzon","philippines"], "center": (15.0, 126.0), "zoom": 3.5},
    },
    "Africa": {
        "All regional activity": {"phrases": [], "center": (2.0, 20.0), "zoom": 2.1},
        "Horn of Africa / Somali Basin": {"phrases": ["somalia","somali basin","djibouti","gulf of aden"], "center": (8.0, 48.0), "zoom": 4.0},
        "Gulf of Guinea": {"phrases": ["gulf of guinea","nigeria","ghana","togo","benin","cameroon"], "center": (2.0, 5.0), "zoom": 4.0},
        "Southern Africa corridors": {"phrases": ["south africa","durban","cape town","maputo","walvis bay"], "center": (-26.0, 24.0), "zoom": 3.5},
        "North Africa / Suez": {"phrases": ["egypt","suez","libya","tunisia","algeria","morocco"], "center": (28.0, 15.0), "zoom": 3.3},
    },
    "Europe": {
        "All regional activity": {"phrases": [], "center": (52.0, 12.0), "zoom": 2.7},
        "Black Sea / Danube": {"phrases": ["black sea","odesa","danube","romania","bulgaria","ukraine"], "center": (45.0, 30.0), "zoom": 4.0},
        "North Sea gateways": {"phrases": ["rotterdam","antwerp","hamburg","bremerhaven","north sea"], "center": (53.0, 5.0), "zoom": 4.3},
        "Baltic gateways": {"phrases": ["baltic","gdansk","klaipeda","riga","tallinn"], "center": (57.0, 20.0), "zoom": 4.0},
        "UK / English Channel": {"phrases": ["united kingdom","uk","english channel","dover","felixstowe","southampton"], "center": (51.0, 0.0), "zoom": 4.2},
    },
    "North America": {
        "All regional activity": {"phrases": [], "center": (42.0, -101.0), "zoom": 2.5},
        "Great Lakes / St Lawrence": {"phrases": ["great lakes","st lawrence","detroit","duluth","montreal","thunder bay"], "center": (44.5, -82.0), "zoom": 3.6},
        "US Gulf": {"phrases": ["houston","new orleans","gulf coast","port arthur","mobile"], "center": (28.5, -91.0), "zoom": 4.0},
        "US West Coast": {"phrases": ["los angeles","long beach","oakland","seattle","tacoma","west coast"], "center": (37.0, -122.0), "zoom": 3.2},
        "Atlantic Canada": {"phrases": ["halifax","saint john","atlantic canada"], "center": (45.0, -63.0), "zoom": 4.3},
    },
    "South America": {
        "All regional activity": {"phrases": [], "center": (-18.0, -60.0), "zoom": 2.5},
        "Brazil ports": {"phrases": ["brazil","santos","paranagua","rio de janeiro"], "center": (-23.0, -46.0), "zoom": 3.8},
        "Pacific coast": {"phrases": ["chile","peru","callao","valparaiso","guayaquil"], "center": (-15.0, -76.0), "zoom": 3.2},
        "Caribbean north coast": {"phrases": ["colombia","venezuela","cartagena","barranquilla"], "center": (8.0, -72.0), "zoom": 3.8},
    },
    "South Asia": {
        "All regional activity": {"phrases": [], "center": (21.0, 78.0), "zoom": 3.0},
        "India west coast": {"phrases": ["mumbai","mundra","jnpt","nhava sheva","kochi"], "center": (18.0, 73.0), "zoom": 4.0},
        "Bay of Bengal": {"phrases": ["bay of bengal","chennai","kolkata","bangladesh","chittagong"], "center": (17.0, 87.0), "zoom": 3.8},
        "Sri Lanka": {"phrases": ["sri lanka","colombo","hambantota","trincomalee"], "center": (7.5, 80.7), "zoom": 5.0},
        "Arabian Sea": {"phrases": ["arabian sea","karachi","gwadar","mumbai"], "center": (20.0, 65.0), "zoom": 3.6},
    },
    "Central Asia": {
        "All regional activity": {"phrases": [], "center": (43.0, 66.0), "zoom": 3.2},
        "Caspian / Middle Corridor": {"phrases": ["caspian","aktau","baku","middle corridor","trans-caspian"], "center": (42.0, 51.0), "zoom": 4.0},
        "Kazakhstan export routes": {"phrases": ["kazakhstan","aktau","atyrau","cpc"], "center": (46.0, 58.0), "zoom": 3.8},
    },
    "Arctic": {
        "All regional activity": {"phrases": [], "center": (70.0, 10.0), "zoom": 2.1},
        "Northern Sea Route": {"phrases": ["northern sea route","murmansk","arkhangelsk","nsr"], "center": (72.0, 60.0), "zoom": 2.4},
        "Canadian Arctic / Churchill": {"phrases": ["churchill","hudson bay","nunavut","canadian arctic"], "center": (63.0, -85.0), "zoom": 3.0},
        "Nordic Arctic": {"phrases": ["svalbard","norway","barents","tromso","tromsø"], "center": (72.0, 20.0), "zoom": 3.0},
    },
}


def _map_focus_config(region, focus):
    areas=MAP_FOCUS_AREAS.get(region) or MAP_FOCUS_AREAS.get("Global",{})
    return areas.get(focus) or next(iter(areas.values()))

def _focus_filter(df, focus_cfg, cols):
    if df is None or df.empty:
        return df.copy() if df is not None else pd.DataFrame()
    phrases=focus_cfg.get("phrases") or []
    if not phrases:
        return df.copy()
    blob=pd.Series("",index=df.index,dtype="string")
    for c in cols:
        if c in df.columns:
            blob=blob.str.cat(df[c].fillna("").astype(str),sep=" ")
    pattern="|".join(re.escape(x) for x in phrases)
    return df[blob.str.contains(pattern,case=False,regex=True,na=False)].copy()


def _trade_region_filter(df, region, country_cols):
    if df is None or df.empty or region=="Global":
        return df.copy() if df is not None else pd.DataFrame()
    countries=TRADE_REGIONS.get(region,{}).get("countries",[])
    if not countries: return df.copy()
    blob=pd.Series("",index=df.index,dtype="string")
    for c in country_cols:
        if c in df.columns: blob=blob.str.cat(df[c].fillna("").astype(str),sep=" ")
    pattern="|".join(re.escape(x) for x in countries)
    return df[blob.str.contains(pattern,case=False,regex=True,na=False)].copy()


def _trade_recaap_projection():
    """Legacy ReCAAP projection fallback.

    When canonical DB ReCAAP events exist, do not project the same observations
    from Excel again.
    """
    canonical = TABLES.get(("Events & Hazards","Events"), pd.DataFrame())
    if not canonical.empty and "Event ID" in canonical.columns:
        if canonical["Event ID"].fillna("").astype(str).str.startswith("EVT_RECAAP_").any():
            return pd.DataFrame(), pd.DataFrame()
    obs=TABLES.get(("Intelligence","Event Observations"),pd.DataFrame()).copy()
    if obs.empty or "Source Dataset" not in obs.columns:
        return pd.DataFrame(),pd.DataFrame()
    r=obs[obs["Source Dataset"].fillna("").astype(str).str.casefold().eq("recaap_incidents_2024_2026")].copy()
    if r.empty:
        return pd.DataFrame(),pd.DataFrame()

    def _clean(v):
        if pd.isna(v): return ""
        return str(v).strip()
    def _country(row):
        c=_clean(row.get("Country",""))
        if c: return c
        t=_clean(row.get("Region / Theatre", ""))
        tl=t.casefold()
        for name in ["Bangladesh","India","Indonesia","Malaysia","Philippines","Singapore","Vietnam"]:
            if name.casefold() in tl: return name
        if "malacca" in tl or "singapore" in tl: return "Singapore / Malaysia / Indonesia"
        if "south china sea" in tl: return "South China Sea"
        return t

    erows=[]; lrows=[]
    for _,row in r.iterrows():
        oid=_clean(row.get("Observation ID","")) or _clean(row.get("Source Record ID",""))
        if not oid: continue
        eid=f"RECAAP_{oid}"
        vessel=_clean(row.get("Subject Name","")); raw_type=_clean(row.get("Event Type",""))
        title=f"ReCAAP: {raw_type or 'Piracy / armed robbery'}" + (f" — {vessel}" if vessel else "")
        country=_country(row); loc=_clean(row.get("Location",""))
        normalized_type="Attempted piracy / armed robbery" if "attempt" in raw_type.casefold() else "Piracy / armed robbery"
        erows.append({
            "Event ID":eid,"Start Date":row.get("Date",""),"End Date":"","Event Family":"Maritime Crime",
            "Event Type":normalized_type,"Severity":_clean(row.get("Severity","")),"Status":"Recorded","Mode":"Maritime",
            "Country / Countries":country,"Location":loc,"Title":title,"Description":_clean(row.get("Description","")),
            "Operational Impact":_clean(row.get("Operational Impact","")),"Trade / Commercial Impact":_clean(row.get("Trade Impact","")),
            "Confidence":_clean(row.get("Confidence","")),"Source Record":oid,"Primary Source URL":_clean(row.get("Source Reference",""))
        })
        lat=pd.to_numeric(pd.Series([row.get("Latitude")]),errors="coerce").iloc[0]
        lon=pd.to_numeric(pd.Series([row.get("Longitude")]),errors="coerce").iloc[0]
        if pd.notna(lat) and pd.notna(lon):
            lrows.append({"Location Record":f"RECAAP_LOC_{oid}","Event ID":eid,"Location":loc,"Country":country,
                          "Latitude":float(lat),"Longitude":float(lon),"Accuracy":"ReCAAP reported coordinates",
                          "Notes":f"ReCAAP category: {_clean(row.get('Subtype',''))}"})
    return pd.DataFrame(erows),pd.DataFrame(lrows)

def render_trade_regional_maps():
    header(
        "Regional Maps",
        "Map-first views across the global trade network. Choose a region, then narrow to a key focus area without losing the wider regional picture."
    )

    top1,top2=st.columns([1,1])
    with top1:
        region=st.selectbox(
            "Region",
            list(TRADE_REGIONS.keys()),
            key="trade_region_map"
        )
    focus_options=list((MAP_FOCUS_AREAS.get(region) or {"All regional activity":{}}).keys())
    with top2:
        focus=st.selectbox(
            "Key focus area",
            focus_options,
            key="trade_region_focus"
        )

    focus_cfg=_map_focus_config(region,focus)

    events=TABLES.get(("Events & Hazards","Events"),pd.DataFrame()).copy()
    locs=TABLES.get(("Events & Hazards","Event Locations"),pd.DataFrame()).copy()
    recaap_events,recaap_locs=_trade_recaap_projection()
    if not recaap_events.empty:
        events=pd.concat([events,recaap_events],ignore_index=True,sort=False)
    if not recaap_locs.empty:
        locs=pd.concat([locs,recaap_locs],ignore_index=True,sort=False)

    ports_df=TABLES.get(("Maritime","Ports"),pd.DataFrame()).copy()

    events=_trade_region_filter(events,region,["Country / Countries","Location","Title","Description","Event Family","Event Type"])
    ports_view=_trade_region_filter(ports_df,region,["Country","Port / Facility","Operator","Key Role","Coverage Note"])

    events=_focus_filter(
        events,focus_cfg,
        ["Country / Countries","Location","Title","Description","Event Family","Event Type","Operational Impact","Trade / Commercial Impact"]
    )
    ports_view=_focus_filter(
        ports_view,focus_cfg,
        ["Country","Port / Facility","Operator","Key Role","Coverage Note","City / Region"]
    )

    ctl1,ctl2=st.columns([1.2,1.8])
    with ctl1:
        mode=st.radio(
            "Layer",
            ["All","Incidents & disruptions","Ports"],
            horizontal=True,
            key="trade_region_layer"
        )
    with ctl2:
        severity=st.multiselect(
            "Severity",
            ["Critical","Severe","High","Medium","Moderate","Low"],
            default=[],
            key="trade_region_severity"
        )

    if severity and not events.empty and "Severity" in events.columns:
        events=events[events["Severity"].fillna("").astype(str).isin(severity)]

    points=[]
    if mode in ["All","Incidents & disruptions"] and not events.empty and not locs.empty and "Event ID" in events and "Event ID" in locs:
        lp=locs.copy()
        lp["Latitude"]=pd.to_numeric(lp.get("Latitude"),errors="coerce")
        lp["Longitude"]=pd.to_numeric(lp.get("Longitude"),errors="coerce")
        lp=lp.dropna(subset=["Latitude","Longitude"])
        evcols=[c for c in [
            "Event ID","Start Date","Title","Severity","Mode",
            "Operational Impact","Trade / Commercial Impact"
        ] if c in events.columns]
        ep=lp.merge(events[evcols],on="Event ID",how="inner")
        for _,r in ep.iterrows():
            detail=str(r.get("Trade / Commercial Impact","") or r.get("Operational Impact","") or "")
            points.append({
                "lat":r["Latitude"],"lon":r["Longitude"],
                "name":str(r.get("Title","Event")),
                "kind":"Event","detail":detail,
                "severity":str(r.get("Severity",""))
            })

    if mode in ["All","Ports"] and not ports_view.empty:
        p=ports_view.copy()
        p["Latitude"]=pd.to_numeric(p.get("Latitude"),errors="coerce")
        p["Longitude"]=pd.to_numeric(p.get("Longitude"),errors="coerce")
        p=p.dropna(subset=["Latitude","Longitude"])
        for _,r in p.iterrows():
            points.append({
                "lat":r["Latitude"],"lon":r["Longitude"],
                "name":str(r.get("Port / Facility","Port")),
                "kind":"Port","detail":str(r.get("Key Role","") or ""),
                "severity":""
            })

    mp=pd.DataFrame(points)

    m1,m2,m3,m4=st.columns(4)
    m1.metric("Mapped points",len(mp))
    m2.metric("Regional events",len(events))
    m3.metric("Ports",len(ports_view))
    m4.metric("Focus",focus)

    st.caption(
        f"Region: {region} · Key focus: {focus}. "
        "Only supported coordinates are plotted; unmapped records remain in the registers below."
    )

    if mp.empty:
        st.info("No mapped records are available for the current region / focus / layer selection.")
    elif pdk is not None:
        layers=[]
        evp=mp[mp["kind"].eq("Event")]
        pp=mp[mp["kind"].eq("Port")]
        if not pp.empty:
            layers.append(
                pdk.Layer(
                    "ScatterplotLayer",pp,
                    get_position="[lon, lat]",
                    get_radius=25000,
                    radius_min_pixels=3,
                    radius_max_pixels=9,
                    get_fill_color=[79,145,205,170],
                    pickable=True
                )
            )
        if not evp.empty:
            layers.append(
                pdk.Layer(
                    "ScatterplotLayer",evp,
                    get_position="[lon, lat]",
                    get_radius=40000,
                    radius_min_pixels=5,
                    radius_max_pixels=14,
                    get_fill_color=[230,93,93,210],
                    pickable=True
                )
            )
        st.pydeck_chart(
            pdk.Deck(
                layers=layers,
                initial_view_state=pdk.ViewState(
                    latitude=focus_cfg["center"][0],
                    longitude=focus_cfg["center"][1],
                    zoom=focus_cfg["zoom"]
                ),
                tooltip={"html":"<b>{name}</b><br>{kind}<br>{detail}"},
                map_style=None
            ),
            use_container_width=True,
            height=540
        )
    else:
        st.map(mp,latitude="lat",longitude="lon",use_container_width=True)

    tabs=st.tabs(["Events & impact","Ports","Key focus summary"])
    with tabs[0]:
        cols=[c for c in [
            "Start Date","Event Family","Event Type","Severity","Status","Mode",
            "Country / Countries","Location","Title","Operational Impact",
            "Trade / Commercial Impact"
        ] if c in events.columns]
        display_df(events[cols] if cols else events,380)

    with tabs[1]:
        cols=[c for c in [
            "Port / Facility","Country","Operator","Facility Type",
            "Key Role","Coverage Note"
        ] if c in ports_view.columns]
        display_df(ports_view[cols] if cols else ports_view,380)

    with tabs[2]:
        st.markdown(f"### {focus}")
        if focus_cfg.get("phrases"):
            st.caption("Focus terms: " + " · ".join(focus_cfg["phrases"][:10]))
        c1,c2=st.columns(2)
        with c1:
            st.markdown("**Recent / priority events**")
            if not events.empty:
                ev=events.copy()
                if "Start Date" in ev.columns:
                    ev["_d"]=pd.to_datetime(ev["Start Date"],errors="coerce")
                    ev=ev.sort_values("_d",ascending=False)
                cols=[c for c in ["Start Date","Severity","Title","Location"] if c in ev.columns]
                display_df(ev[cols].head(12) if cols else ev.head(12),320)
            else:
                st.caption("No qualifying events.")
        with c2:
            st.markdown("**Exposed ports / gateways**")
            cols=[c for c in ["Port / Facility","Country","Operator","Key Role"] if c in ports_view.columns]
            display_df(ports_view[cols].head(12) if cols else ports_view.head(12),320)


# ---------- workspace navigation ----------
st.sidebar.markdown("<div class='pc-kicker'>Power & Corridors Intelligence</div>",unsafe_allow_html=True)
st.sidebar.markdown("### Trade System")
st.sidebar.markdown("### Controls")
st.sidebar.radio(
    "Appearance",
    ["Dark","Light"],
    horizontal=True,
    key="pc_trade_appearance",
)
if st.sidebar.button("↻ Refresh database", use_container_width=True, key="pc_trade_refresh_database"):
    st.cache_data.clear()
    try:
        st.cache_resource.clear()
    except Exception:
        pass
    st.rerun()
st.sidebar.caption("Refresh after applying records or relationships in Power Admin.")

_bst=backend_status()
st.sidebar.caption(f"{APP_VERSION} · {_bst.get('mode','excel').title()} backend")

NAV_SECTIONS={
    "OPERATING PICTURE":["Overview","Trade Horizon","Regional Maps","Alerts & Disruptions","Watch Areas"],
    "LOGISTICS NETWORK":["Companies","Services & Routes","Corridors & Systems","Trucking","Rail","Aviation","Maritime","Ports & Terminals","Vessels"],
    "BUSINESS & INFRASTRUCTURE":["Investments","Deals, Projects & Contracts","Energy & Industry","Defence & Shipbuilding"],
    "MARKETS & POLICY":["Freight & Commodity Markets","Market Instruments","Trade Flows & Supply","Country & Macro","Sanctions & Compliance","Trade Policy"],
    "MONITORING & TOOLS":["Government & Security","Port Activity","Hormuz Monitor","Live Feeds","News & Developments","Search","Reference & Benchmarks","Data"],
}
VISIBLE_PAGES=[p for items in NAV_SECTIONS.values() for p in items]
HIDDEN_ROUTES={"Ports","Shipyards","Network Map","News & Events","Reference Library","Ferries","Cruise","Maritime Security","Maritime Disruptions","Security & Business Risk","Contracts"}
# Deep links from the separate P&C Intelligence app.
try:
    _qp=st.query_params
    if _qp.get("company",None):
        st.session_state["company_pick_id"]=str(_qp.get("company")); st.session_state["nav_request"]="Companies"
    elif _qp.get("port",None):
        st.session_state["port_pick_id"]=str(_qp.get("port")); st.session_state["nav_request"]="Ports"
    elif _qp.get("vessel",None):
        st.session_state["vessel_pick_id"]=str(_qp.get("vessel")); st.session_state["nav_request"]="Vessels"
except Exception:
    pass

if "pc_trade_page" not in st.session_state:
    st.session_state["pc_trade_page"]="Overview"
if "nav_request" in st.session_state:
    st.session_state["pc_trade_page"]=st.session_state.pop("nav_request")

page=st.session_state.get("pc_trade_page","Overview")
st.sidebar.markdown("<div class='pc-small' style='margin:4px 0 8px'>CURRENT</div>",unsafe_allow_html=True)
st.sidebar.markdown(f"<div class='pc-card' style='padding:9px 11px'><b>{html_lib.escape(str(page))}</b></div>",unsafe_allow_html=True)

for section,items in NAV_SECTIONS.items():
    st.sidebar.markdown(f"<div class='pc-small' style='margin-top:12px;letter-spacing:.08em'>{section}</div>",unsafe_allow_html=True)
    for item in items:
        label_txt=("● " if page==item else "")+item
        if st.sidebar.button(label_txt,key=f"navflat_{section}_{item}",use_container_width=True):
            st.session_state["pc_trade_page"]=item
            st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("<div class='pc-small'>QUICK ACCESS</div>",unsafe_allow_html=True)
qa1,qa2=st.sidebar.columns(2)
with qa1:
    if st.button("Companies",use_container_width=True,key="qa_companies"):
        request_nav("Companies"); st.rerun()
    if st.button("Alerts",use_container_width=True,key="qa_alerts"):
        request_nav("Alerts & Disruptions"); st.rerun()
with qa2:
    if st.button("Services",use_container_width=True,key="qa_services"):
        request_nav("Services & Routes"); st.rerun()
    if st.button("Corridors",use_container_width=True,key="qa_corridors"):
        request_nav("Corridors & Systems"); st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("<div class='pc-small'>ACTIVE DATA LAYERS</div>",unsafe_allow_html=True)
st.sidebar.markdown("<span class='pc-feed-health'><span class='pc-dot pc-dot-live'></span> Shared data model</span>",unsafe_allow_html=True)
st.sidebar.markdown("<span class='pc-feed-health'><span class='pc-dot pc-dot-live'></span> PortWatch</span>",unsafe_allow_html=True)
st.sidebar.markdown("<span class='pc-feed-health'><span class='pc-dot pc-dot-live'></span> Hormuz</span>",unsafe_allow_html=True)
news_key_present=bool(_newsdata_key())
news_class="pc-dot-live" if news_key_present else "pc-dot-key"
news_label="NewsData" if news_key_present else "NewsData · key needed"
st.sidebar.markdown(f"<span class='pc-feed-health'><span class='pc-dot {news_class}'></span> {news_label}</span>",unsafe_allow_html=True)
st.sidebar.caption("CGMIX and GDELT remain deferred. Live API views keep the last successful session result if a refresh fails.")

pc_render_drilldown_search()

# Resolve workspace label safely before breadcrumb rendering.
workspace = globals().get("workspace")
if not workspace:
    _section_map = globals().get("NAV_SECTIONS", {})
    if isinstance(_section_map, dict):
        workspace = next(
            (section for section, items in _section_map.items() if page in items),
            "Trade System"
        )
    else:
        workspace = "Trade System"

st.markdown(
    f"<div class='pc-breadcrumb'><b>{workspace}</b> &nbsp;/&nbsp; {page}</div>",
    unsafe_allow_html=True
)

# Canonical context opens at the top of every Trade workspace.
pc_render_active_drilldown(location="top",expanded=True)

def page_company_selector():
    companies=TABLES.get(("Core Entities","Companies"),pd.DataFrame())
    if companies.empty: return None,None
    opts=companies[["Company ID","Company"]].drop_duplicates().sort_values("Company").to_dict("records")
    q=st.text_input("Find company",placeholder="APM Terminals, AD Ports, Inocea, Seaspan, Fincantieri, EDGE...")
    if q:
        opts=[x for x in opts if q.lower() in str(x["Company"]).lower()]
    if not opts:
        st.warning("No matching company.")
        return None,None
    pick=st.selectbox("Company",range(len(opts)),format_func=lambda i:opts[i]["Company"])
    return opts[pick]["Company ID"],opts[pick]["Company"]




def filter_distinct_port_terminals(port_row, port_terminals):
    """Exclude port-level coverage rows that merely repeat the parent port as a terminal."""
    if port_terminals is None or port_terminals.empty:
        return pd.DataFrame() if port_terminals is None else port_terminals.copy()

    df = port_terminals.copy()
    port_name = str(port_row.get("Port / Facility", "") or "").strip()

    def norm(v):
        s = str(v or "").strip().casefold()
        s = s.replace("&", " and ")
        s = re.sub(r"[^a-z0-9]+", " ", s)
        return re.sub(r"\s+", " ", s).strip()

    pnorm = norm(port_name)
    keep = pd.Series(True, index=df.index)

    for idx, row in df.iterrows():
        terminal_name = norm(row.get("Terminal / Facility", ""))
        terminal_short = norm(row.get("Terminal", ""))
        parent_name = norm(row.get("Parent Port", ""))
        port_col = norm(row.get("Port", ""))

        # A terminal row is a self-reference when its facility name is the same
        # canonical place as the selected parent port. Keep genuinely distinct
        # subordinate facilities such as Abu Dhabi Cruise Terminal.
        self_ref = bool(pnorm) and (
            terminal_name == pnorm
            or terminal_short == pnorm
        )

        # Reinforce only when the row itself also identifies the same parent port.
        same_parent = (
            not parent_name or parent_name == pnorm
        ) and (
            not port_col or port_col == pnorm
        )

        if self_ref and same_parent:
            keep.loc[idx] = False

    return df[keep].copy()



def _canonical_live_asset_id(asset_id):
    """Resolve retired alias/merged asset IDs to the active canonical asset.

    Identity-resolution edges intentionally keep the historical alias as the
    source (alias_of / merged_into / duplicate_of / superseded_by). Operational
    screens, however, must query the canonical target so terminals/events are
    not stranded behind an old ID.
    """
    aid=str(asset_id or "").strip()
    if not aid:
        return aid
    try:
        sb=pc_db_client(service=True)
    except Exception:
        sb=None
    if sb is None:
        return aid
    seen=set()
    current=aid
    for _ in range(6):
        if current in seen:
            break
        seen.add(current)
        try:
            rows=(sb.table("pc_relationships")
                  .select("source_id,relationship_type,target_id,record_status")
                  .eq("source_type","asset")
                  .eq("source_id",current)
                  .eq("target_type","asset")
                  .limit(100).execute().data or [])
        except Exception:
            rows=[]
        nxt=None
        for r in rows:
            rt=str(r.get("relationship_type") or "").strip().casefold()
            if rt in {"alias_of","merged_into","duplicate_of","superseded_by"}:
                tid=str(r.get("target_id") or "").strip()
                if tid and tid != current:
                    nxt=tid
                    break
        if not nxt:
            break
        current=nxt
    return current


def live_db_terminals_for_port(port_row):
    """Resolve canonical terminals using pc_terminal_details first.

    pc_terminal_details.parent_port_asset_id is now the authoritative port→terminal
    structure. Legacy pc_relationships terminal_of edges remain a fallback only.
    """
    try:
        sb=pc_db_client(service=True)
    except Exception:
        sb=None
    if sb is None:
        return pd.DataFrame(), "Supabase client unavailable"

    pname=str(port_row.get("Port / Facility","") or "").strip()
    pcountry=str(port_row.get("Country","") or "").strip()
    requested_pid=str(port_row.get("Port ID","") or port_row.get("asset_id","") or "").strip()
    canonical_pid=_canonical_live_asset_id(requested_pid) if requested_pid and not requested_pid.startswith("REF_") else requested_pid
    if not pname:
        return pd.DataFrame(), "Selected port has no name"

    try:
        # Prefer the selected canonical ID. Name matching remains a fallback for
        # legacy/reference rows that do not carry a canonical pc_assets ID.
        parents=[]
        if canonical_pid and not canonical_pid.startswith("REF_"):
            parents=(sb.table("pc_assets")
                     .select("asset_id,name,asset_type,subtype,country,region_city,status,metadata")
                     .eq("asset_id",canonical_pid).limit(1).execute().data or [])
        if not parents:
            parents=(sb.table("pc_assets")
                     .select("asset_id,name,asset_type,subtype,country,region_city,status,metadata")
                     .eq("name",pname).limit(20).execute().data or [])

        if pcountry:
            same=[
                p for p in parents
                if not p.get("country")
                or str(p.get("country","")).strip().casefold()==pcountry.casefold()
            ]
            if same:
                parents=same

        if not parents:
            cand=(sb.table("pc_assets")
                  .select("asset_id,name,asset_type,subtype,country,region_city,status,metadata")
                  .limit(5000).execute().data or [])

            def _norm(v):
                s=str(v or "").strip().casefold().replace("&"," and ")
                s=re.sub(r"\\b(port of|port|harbour|harbor)\\b"," ",s)
                s=re.sub(r"[^a-z0-9]+"," ",s)
                return re.sub(r"\\s+"," ",s).strip()

            pk=_norm(pname)
            parents=[
                p for p in cand
                if _norm(p.get("name"))==pk
                and (
                    not pcountry
                    or not p.get("country")
                    or str(p.get("country","")).strip().casefold()==pcountry.casefold()
                )
            ]

        if not parents:
            return pd.DataFrame(), f"No canonical pc_assets parent matched {pname}"

        parent_ids=[str(p.get("asset_id")) for p in parents if p.get("asset_id")]
        if not parent_ids:
            return pd.DataFrame(), "Matched parent has no asset_id"

        # CURRENT MODEL: pc_terminal_details is authoritative.
        detail_rows=[]
        for pid in parent_ids:
            detail_rows.extend(
                sb.table("pc_terminal_details").select("*")
                .eq("parent_port_asset_id",pid).limit(2000).execute().data or []
            )

        if detail_rows:
            entity_ids=set()
            child_ids=set()
            for d in detail_rows:
                child_ids.add(str(d.get("asset_id") or ""))
                for c in ["owner_entity_id","operator_entity_id","concession_holder_entity_id"]:
                    if d.get(c):
                        entity_ids.add(str(d[c]))

            assets={}
            for cid in child_ids:
                if not cid:
                    continue
                rows=(sb.table("pc_assets")
                      .select("asset_id,name,asset_type,subtype,country,region_city,status,metadata")
                      .eq("asset_id",cid).limit(1).execute().data or [])
                if rows:
                    assets[cid]=rows[0]

            entities={}
            for eid in entity_ids:
                rows=(sb.table("pc_entities").select("entity_id,name")
                      .eq("entity_id",eid).limit(1).execute().data or [])
                if rows:
                    entities[eid]=rows[0].get("name") or eid

            rows=[]
            for d in detail_rows:
                cid=str(d.get("asset_id") or "")
                a=assets.get(cid,{})
                rows.append({
                    "Terminal ID":cid,
                    "Terminal / Facility":a.get("name") or cid,
                    "Terminal":a.get("name") or cid,
                    "Parent Port":pname,
                    "Port":pname,
                    "Country":a.get("country") or pcountry,
                    "City / Area":a.get("region_city") or "",
                    "Terminal Type":d.get("terminal_type") or a.get("subtype") or "",
                    "Terminal Code":d.get("terminal_code") or "",
                    "Primary Operator Company ID":d.get("operator_entity_id") or "",
                    "Primary Operator":entities.get(str(d.get("operator_entity_id") or ""),""),
                    "Owner Company ID":d.get("owner_entity_id") or "",
                    "Owner":entities.get(str(d.get("owner_entity_id") or ""),""),
                    "Concession Holder":entities.get(str(d.get("concession_holder_entity_id") or ""),""),
                    "Concession Start":d.get("concession_start"),
                    "Concession End":d.get("concession_end"),
                    "Berth Count":d.get("berth_count"),
                    "Quay Length M":d.get("quay_length_m"),
                    "Max Draught M":d.get("max_draught_m"),
                    "Capacity":d.get("capacity"),
                    "Equipment":d.get("equipment"),
                    "Status":a.get("status") or "",
                    "Last Verified":d.get("last_verified"),
                    "Source ID":d.get("source_id") or "",
                    "Data Status":"Canonical pc_terminal_details",
                })
            return pd.DataFrame(rows), f"{len(rows)} canonical terminal(s) from pc_terminal_details"

        # FALLBACK ONLY: legacy relationship edges.
        rels=[]
        for pid in parent_ids:
            rels.extend(
                sb.table("pc_relationships")
                .select("relationship_id,source_type,source_id,relationship_type,target_type,target_id,record_status")
                .eq("target_id",pid)
                .eq("target_type","asset")
                .limit(1000).execute().data or []
            )
        rels=[
            r for r in rels
            if str(r.get("relationship_type") or "").strip().casefold().replace("-","_").replace(" ","_")=="terminal_of"
            and str(r.get("source_type") or "").strip().casefold()=="asset"
        ]
        if not rels:
            return pd.DataFrame(), (
                f"Canonical parent found ({', '.join(parent_ids)}), "
                "but no pc_terminal_details children are loaded yet"
            )

        child_ids=sorted({str(r.get("source_id")) for r in rels if r.get("source_id")})
        rows=[]
        for cid in child_ids:
            child=(sb.table("pc_assets")
                   .select("asset_id,name,asset_type,subtype,country,region_city,status,metadata")
                   .eq("asset_id",cid).limit(1).execute().data or [])
            if child:
                a=child[0]
                rows.append({
                    "Terminal ID":cid,
                    "Terminal / Facility":a.get("name") or cid,
                    "Terminal":a.get("name") or cid,
                    "Parent Port":pname,
                    "Port":pname,
                    "Country":a.get("country") or pcountry,
                    "City / Area":a.get("region_city") or "",
                    "Terminal Type":a.get("subtype") or "",
                    "Status":a.get("status") or "",
                    "Data Status":"Legacy terminal_of relationship fallback",
                })
        return pd.DataFrame(rows), f"{len(rows)} legacy terminal relationship(s)"

    except Exception as exc:
        return pd.DataFrame(), f"Supabase terminal query failed: {exc}"


def render_port_commercial_network(port_row, port_terminals):
    """Render the canonical ownership/operator network for one port."""
    pid=str(port_row.get("Port ID","") or "").strip()
    port_operator_id=str(port_row.get("Operator Company ID","") or "").strip()
    port_operator_name=str(port_row.get("Operator","") or "").strip()
    ownership=TABLES.get(("Maritime","Port Ownership"),pd.DataFrame()).copy()

    st.markdown("### Ownership & operations")

    if port_operator_name or port_operator_id:
        st.markdown("**Port operator / authority**")
        c1,c2=st.columns([5,1])
        with c1:
            name=port_operator_name or label(port_operator_id)
            st.markdown(f"**{name}**")
            st.caption("Operates / administers this port")
        with c2:
            if port_operator_id and port_operator_id.startswith("COMP"):
                if st.button("Open company",key=f"portop_{pid}_{port_operator_id}",use_container_width=True):
                    request_nav("Companies","company_pick_id",port_operator_id,name)
                    st.rerun()

    operator_rows=[]
    if port_terminals is not None and not port_terminals.empty:
        seen=set()
        for _,tr in port_terminals.iterrows():
            cid=str(tr.get("Primary Operator Company ID","") or "").strip()
            name=str(tr.get("Primary Operator","") or tr.get("Operator / Network","") or "").strip()
            tid=str(tr.get("Terminal ID","") or "").strip()
            tname=str(tr.get("Terminal / Facility","") or "").strip()
            key=(cid,name)
            if (cid or name) and key not in seen:
                seen.add(key)
                operator_rows.append((cid,name,tid,tname))

    if operator_rows:
        st.markdown("**Terminal operators**")
        for n,(cid,name,tid,tname) in enumerate(operator_rows):
            c1,c2=st.columns([5,1])
            with c1:
                st.markdown(f"**{name or label(cid)}**")
                if tname:
                    st.caption(f"Operates {tname}")
            with c2:
                if cid and cid.startswith("COMP"):
                    if st.button("Open company",key=f"termop_{pid}_{tid}_{cid}_{n}",use_container_width=True):
                        request_nav("Companies","company_pick_id",cid,name or label(cid))
                        st.rerun()

    if ownership is not None and not ownership.empty and port_terminals is not None and not port_terminals.empty and "Terminal ID" in ownership.columns:
        tids=set(port_terminals.get("Terminal ID",pd.Series(dtype=str)).dropna().astype(str).tolist())
        own=ownership[ownership["Terminal ID"].astype(str).isin(tids)].copy()
        if not own.empty:
            st.markdown("**Owners, investors & concession partners**")
            for n,(_,r) in enumerate(own.iterrows()):
                cid=str(r.get("Company ID","") or "").strip()
                cname=str(r.get("Company / Partner","") or "").strip() or label(cid)
                tid=str(r.get("Terminal ID","") or "").strip()
                rel=pretty_relationship(r.get("Relationship",""))
                eq=str(r.get("Equity %","") or "").strip()
                ctl=str(r.get("Operating Control","") or "").strip()
                status=str(r.get("Status","") or "").strip()
                tmatch=port_terminals[port_terminals.get("Terminal ID",pd.Series(index=port_terminals.index,dtype=str)).astype(str).eq(tid)]
                tname=str(tmatch.iloc[0].get("Terminal / Facility","")) if not tmatch.empty else tid
                meta=[]
                if rel and rel.lower()!='nan': meta.append(rel)
                if eq and eq.lower()!='nan': meta.append(f"Equity: {eq}%")
                if ctl and ctl.lower()!='nan': meta.append(f"Operating control: {ctl}")
                if status and status.lower()!='nan': meta.append(status)
                c1,c2=st.columns([5,1])
                with c1:
                    st.markdown(f"**{cname}**")
                    detail=tname
                    if meta: detail += " · " + " · ".join(meta)
                    st.caption(detail)
                with c2:
                    if cid and cid.startswith("COMP"):
                        if st.button("Open company",key=f"portown_{pid}_{tid}_{cid}_{n}",use_container_width=True):
                            request_nav("Companies","company_pick_id",cid,cname)
                            st.rerun()


def render_port_terminal_cards(port_id, port_terminals):
    """Trade-facing terminal view with direct navigation to canonical operators/owners."""
    if port_terminals is None or port_terminals.empty:
        st.info("No terminal records linked to this port yet.")
        return
    ownership=TABLES.get(("Maritime","Port Ownership"),pd.DataFrame()).copy()
    for n,(_,tr) in enumerate(port_terminals.iterrows()):
        tid=str(tr.get("Terminal ID","") or "").strip()
        tname=str(tr.get("Terminal / Facility","") or "Terminal").strip()
        operator_id=str(tr.get("Primary Operator Company ID","") or "").strip()
        operator=str(tr.get("Primary Operator","") or tr.get("Operator / Network","") or "").strip()
        cargo=str(tr.get("Cargo Profile","") or "").strip()
        status=str(tr.get("Status","") or "").strip()
        capacity=str(tr.get("Container Capacity TEU/yr","") or "").strip()
        ownership_structure=str(tr.get("Ownership / Structure","") or "").strip()

        st.markdown(f"#### {tname}")
        bits=[]
        if cargo and cargo.lower()!='nan': bits.append(cargo)
        if status and status.lower()!='nan': bits.append(status)
        if capacity and capacity.lower()!='nan': bits.append(f"Capacity: {capacity} TEU/yr")
        if bits: st.caption(" · ".join(bits))

        if operator or operator_id:
            c1,c2=st.columns([5,1])
            with c1:
                st.markdown(f"**Operated by:** {operator or label(operator_id)}")
            with c2:
                if operator_id and operator_id.startswith("COMP"):
                    if st.button("Open company",key=f"terminal_operator_{port_id}_{tid}_{operator_id}_{n}",use_container_width=True):
                        request_nav("Companies","company_pick_id",operator_id,operator or label(operator_id))
                        st.rerun()

        if ownership_structure and ownership_structure.lower()!='nan':
            st.caption(f"Ownership / structure: {ownership_structure}")

        if not ownership.empty and "Terminal ID" in ownership.columns:
            own=ownership[ownership["Terminal ID"].astype(str).eq(tid)]
            if not own.empty:
                for j,(_,r) in enumerate(own.iterrows()):
                    cid=str(r.get("Company ID","") or "").strip()
                    cname=str(r.get("Company / Partner","") or "").strip() or label(cid)
                    rel=pretty_relationship(r.get("Relationship",""))
                    eq=str(r.get("Equity %","") or "").strip()
                    ctl=str(r.get("Operating Control","") or "").strip()
                    details=[x for x in [rel, (f"Equity: {eq}%" if eq and eq.lower()!='nan' else ''), (f"Operating control: {ctl}" if ctl and ctl.lower()!='nan' else '')] if x]
                    c1,c2=st.columns([5,1])
                    with c1:
                        st.markdown(f"**{cname}**")
                        if details: st.caption(" · ".join(details))
                    with c2:
                        if cid and cid.startswith("COMP"):
                            if st.button("Open company",key=f"terminal_owner_{port_id}_{tid}_{cid}_{n}_{j}",use_container_width=True):
                                request_nav("Companies","company_pick_id",cid,cname)
                                st.rerun()
        st.markdown("<div style='height:8px'></div>",unsafe_allow_html=True)


def _first_existing_col(df, names):
    for c in names:
        if c in df.columns:
            return c
    return None

def _compact_trade_table(df, preferred_cols, height=260):
    if df is None or df.empty:
        st.caption("No records available.")
        return
    cols=[c for c in preferred_cols if c in df.columns]
    if not cols:
        cols=list(df.columns[:8])
    display_df(df[cols],height)

def _recent_commercial_records():
    """Commercial/deal/contract/investment records for the Trade homepage."""
    frames=[]

    # Current canonical / app-facing locations first.
    sources=[
        (("Transactions","Transactions V125"),"Transaction"),
        (("Transactions","Infra Deals"),"Infrastructure deal"),
        (("Defence & Shipbuilding","Contracts"),"Contract"),
        (("Corporate & Markets","Investments"),"Investment"),
        (("Commercial","Transactions V125"),"Transaction"),
        (("Commercial","Infra Deals"),"Infrastructure deal"),
        (("Commercial","Contracts"),"Contract"),
        (("Trade & Commercial","Transactions V125"),"Transaction"),
        (("Trade & Commercial","Infra Deals"),"Infrastructure deal"),
        (("Trade & Commercial","Contracts"),"Contract"),
        (("Commercial Activity","Infra Deals"),"Infrastructure deal"),
        (("Commercial Activity","Contracts"),"Contract"),
    ]

    seen_keys=set()
    for key,label_name in sources:
        df=TABLES.get(key,pd.DataFrame())
        if df is None or df.empty:
            continue
        sig=(key[0],key[1])
        if sig in seen_keys:
            continue
        seen_keys.add(sig)
        x=df.copy()
        x["_source_type"]=label_name
        x["_source_group"]=key[0]
        x["_source_sheet"]=key[1]
        frames.append(x)

    # Fallback: capture any loaded sheet whose name is clearly commercial.
    wanted={"Infra Deals","Transactions V125","Contracts","Investments","Vessel Transactions"}
    for key,df in TABLES.items():
        if df is None or df.empty:
            continue
        sheet=str(key[1]) if isinstance(key,tuple) and len(key)>1 else str(key)
        group=str(key[0]) if isinstance(key,tuple) and len(key)>0 else ""
        if sheet not in wanted:
            continue
        sig=(group,sheet)
        if sig in seen_keys:
            continue
        x=df.copy()
        x["_source_type"]=sheet.rstrip("s")
        x["_source_group"]=group
        x["_source_sheet"]=sheet
        frames.append(x)
        seen_keys.add(sig)

    if not frames:
        return pd.DataFrame()

    allc=pd.concat(frames,ignore_index=True,sort=False)

    # Sort using all date spellings used by canonical transaction/contract adapters.
    date_col=_first_existing_col(allc,[
        "Date","Announcement Date","Announced Date","Transaction Date","Contract Date",
        "Start Date","Effective Date","Completed / Effective Date","as_of","As Of"
    ])
    if date_col:
        allc["_trade_date"]=pd.to_datetime(allc[date_col],errors="coerce")
        allc=allc.sort_values("_trade_date",ascending=False,na_position="last")

    # Remove obvious duplicate projections of the same canonical transaction.
    dedupe_cols=[c for c in [
        "Transaction ID","Deal ID","Contract ID","Title","Target / Asset",
        "Target Company","Customer","Announced Date","Announcement Date"
    ] if c in allc.columns]
    if dedupe_cols:
        try:
            allc=allc.drop_duplicates(subset=dedupe_cols,keep="first")
        except Exception:
            pass

    return allc

def _trade_network_snapshot():
    companies=TABLES.get(("Core Entities","Companies"),pd.DataFrame())
    ports=TABLES.get(("Maritime","Ports"),pd.DataFrame())
    terminals=TABLES.get(("Maritime","Port Terminals"),pd.DataFrame())
    vessels=TABLES.get(("Maritime","Vessels"),pd.DataFrame())
    rail=TABLES.get(("Rail","Rail Networks"),pd.DataFrame())
    systems=TABLES.get(("Systems & Waterways","Systems"),pd.DataFrame())
    routes=TABLES.get(("Infrastructure","Transport Routes"),pd.DataFrame())
    return {
        "Companies":len(companies),
        "Ports":len(ports),
        "Terminals":len(terminals),
        "Vessels":len(vessels),
        "Rail networks":len(rail),
        "Corridors / systems":max(len(systems),len(routes)),
    }

def _render_trade_pulse():
    records=_recent_commercial_records()
    st.markdown("### Commercial pulse")
    st.caption("Named contracts, transactions and investment — company/asset first, value second.")

    if records.empty:
        st.info("No commercial contracts, transactions or investment records are available in the current data layer.")
        return

    def clean(v):
        return _display_text(v)

    def resolve_id(raw):
        raw=clean(raw)
        if not raw:
            return ""
        try:
            resolved=clean(label(raw))
            return resolved or raw
        except Exception:
            return raw

    def first_value(row,names,resolve=False):
        for c in names:
            if c in records.columns:
                v=clean(row.get(c))
                if v:
                    return resolve_id(v) if resolve else v
        return ""

    rows=[]
    hidden=0

    for _,r in records.head(250).iterrows():
        date=_display_date(first_value(r,[
            "Date","Announcement Date","Announced Date","Transaction Date",
            "Contract Date","Start Date","Effective Date","Completed / Effective Date","As Of"
        ]))

        activity=first_value(r,[
            "Title","Deal","Transaction","Contract","Activity","Project",
            "Programme","Transaction Type","Deal Type","Contract Type","Investment Class",
            "Name","Event"
        ])

        # Named parties from canonical transaction/deal/contract adapters.
        primary=first_value(r,[
            "Buyer","Investor / Buyer","Customer","Client","Awarding Authority",
            "Contracting Authority","Company","Company Name","Contractor",
            "Prime / Lead","Investor","Acquirer"
        ])
        if not primary:
            primary=first_value(r,[
                "Buyer Company ID","Investor / Buyer IDs","Company ID",
                "Contractor Entity ID","Prime / Lead Entity ID"
            ],resolve=True)

        secondary=first_value(r,[
            "Seller","Supplier","Awardee","Target Company","Target / Asset",
            "Counterparty","Partner","Vendor","Developer","Platform / Vessel"
        ])
        if not secondary:
            secondary=first_value(r,[
                "Target Company ID","Target Asset ID","Seller / Owner IDs",
                "Counterparty ID","Target Entity ID"
            ],resolve=True)

        asset=first_value(r,[
            "Target / Asset","Asset / Location","Port / Facility","Terminal / Facility",
            "Project","Programme","Platform / Vessel","Route","Corridor"
        ])

        value=first_value(r,[
            "Value","Deal Value","Transaction Value","Contract Value","Enterprise Value",
            "Reported Value","CAPEX","Capex","Investment","USD Value if Reported"
        ])
        currency=first_value(r,["Currency","Contract Currency"])
        if value and currency and currency.casefold() not in value.casefold():
            value=f"{currency} {value}"

        market=first_value(r,[
            "Market","Country / Region","Country","Geography","Region","Location"
        ])
        status=first_value(r,[
            "Status","Deal Status","Contract Status","Transaction Status",
            "Regulatory Status","Investment Stage"
        ])
        typ=first_value(r,[
            "Transaction Type","Deal Type","Contract Type","Investment Class","_source_type"
        ])

        # A commercial item is only useful if we can say who/what it concerns.
        who_parts=[]
        for x in [primary,secondary]:
            if x and x not in who_parts:
                who_parts.append(x)
        who=" ↔ ".join(who_parts)
        subject=who or asset

        if not subject:
            hidden+=1
            continue

        if not activity:
            activity=typ or "Commercial activity"

        rows.append({
            "Date":date,
            "Activity":activity,
            "Who / Asset":subject,
            "Value / CAPEX":value,
            "Market":market,
            "Status":status,
        })

    if not rows:
        st.info(
            "Commercial records exist, but none currently resolve to a named company, counterparty or asset. "
            "The pulse is intentionally hiding value-only rows."
        )
        return

    pulse=pd.DataFrame(rows)
    pulse["_date"]=pd.to_datetime(pulse["Date"],errors="coerce")
    pulse["_quality"]=(
        pulse["Who / Asset"].ne("").astype(int)*4
        + pulse["Activity"].ne("").astype(int)*2
        + pulse["Value / CAPEX"].ne("").astype(int)
        + pulse["Market"].ne("").astype(int)
    )
    pulse=pulse.sort_values(["_date","_quality"],ascending=[False,False],na_position="last")
    pulse=pulse.drop(columns=["_date","_quality"]).drop_duplicates().head(15)

    display_df(pulse,380)

    if hidden:
        st.caption(
            f"{hidden} incomplete commercial record{'s' if hidden != 1 else ''} hidden because "
            "no company, counterparty or asset could be resolved."
        )

def _render_recent_additions():
    st.markdown("### What changed")
    st.caption("Recent additions translated into trade-network meaning rather than a raw database change log.")

    blocks=[]
    candidates=[
        ("Company",TABLES.get(("Core Entities","Companies"),pd.DataFrame()),["Company","Company Name","Name"],["updated_at","created_at","As Of","as_of"],["Country","HQ Country","Sector","Status"]),
        ("Infrastructure",TABLES.get(("Infrastructure","Assets"),pd.DataFrame()),["Asset","Name","Port / Facility","Terminal / Facility"],["updated_at","created_at","As Of","as_of"],["Country","Asset Type","Facility Type","Status"]),
        ("Vessel",TABLES.get(("Maritime","Vessels"),pd.DataFrame()),["Vessel Name","Name"],["updated_at","created_at","As Of","as_of"],["IMO","Vessel Type","Flag","Status"]),
        ("Defence",TABLES.get(("Defence & Shipbuilding","Defence Vessels"),pd.DataFrame()),["Vessel","Programme","Contract"],["updated_at","created_at","Date","As Of"],["Customer / Operator","Builder","Status","Delivery"]),
        ("Corridor",TABLES.get(("Infrastructure","Transport Routes"),pd.DataFrame()),["Route","Corridor","Name"],["updated_at","created_at","As Of","as_of"],["Mode","Region","Origin","Destination","Status"]),
    ]

    for label,df,ncands,dcands,context_cols in candidates:
        if df is None or df.empty:
            continue
        nc=_first_existing_col(df,ncands)
        dc=_first_existing_col(df,dcands)
        x=df.copy()
        if dc:
            x["_d"]=pd.to_datetime(x[dc],errors="coerce")
            x=x.sort_values("_d",ascending=False,na_position="last")
        for _,r in x.head(3).iterrows():
            name=_display_text(r.get(nc) if nc else None)
            if not name:
                continue
            ctx=[]
            for c in context_cols:
                if c in x.columns:
                    val=_display_text(r.get(c))
                    if val and val not in ctx:
                        ctx.append(val)
            blocks.append({
                "Area":label,
                "Record":name,
                "Why it matters":" · ".join(ctx[:3]) if ctx else "Newly added or materially refreshed network record.",
                "Updated":_display_date(r.get(dc)) if dc else "",
            })

    if not blocks:
        st.info("No recent network changes are available in the current data layer.")
        return

    recent=pd.DataFrame(blocks)
    recent["_d"]=pd.to_datetime(recent["Updated"],errors="coerce")
    recent=recent.sort_values("_d",ascending=False,na_position="last").drop(columns=["_d"])

    for _,r in recent.head(9).iterrows():
        st.markdown(
            f"<div class='pc-card' style='padding:12px 14px;margin-bottom:9px;'>"
            f"<div class='pc-label'>{html_lib.escape(str(r['Area']))} · {html_lib.escape(str(r['Updated']))}</div>"
            f"<div style='font-weight:700;font-size:0.98rem;margin:4px 0;'>{html_lib.escape(str(r['Record']))}</div>"
            f"<div class='pc-card-body'>{html_lib.escape(str(r['Why it matters']))}</div>"
            f"</div>",
            unsafe_allow_html=True
        )

def _trade_exposure_snapshot():
    st.markdown("### Network exposure & watch")
    st.caption("Where commercial activity and operational risk are intersecting now.")

    events=TABLES.get(("Events & Hazards","Events"),pd.DataFrame()).copy()
    if events.empty:
        st.info("No current event layer available.")
        return

    dcol=_first_existing_col(events,["Date","Start Date","Event Date"])
    if dcol:
        events["_d"]=pd.to_datetime(events[dcol],errors="coerce")
        events=events.sort_values("_d",ascending=False,na_position="last")

    sevcol=_first_existing_col(events,["Severity","Risk","Risk Level"])
    titlecol=_first_existing_col(events,["Title","Event","Event Title"])
    loccol=_first_existing_col(events,["Location","Region","Country","Country / Countries"])
    impactcol=_first_existing_col(events,["Trade / Commercial Impact","Commercial Impact","Operational Impact"])
    famcol=_first_existing_col(events,["Event Family","Event Type","Category"])

    if sevcol:
        hot=events[events[sevcol].fillna("").astype(str).str.contains("Critical|Severe|High",case=False,regex=True,na=False)].copy()
        if hot.empty:
            hot=events.head(12).copy()
    else:
        hot=events.head(12).copy()

    if impactcol:
        sig=hot[hot[impactcol].apply(_display_text).ne("")]
        if not sig.empty:
            hot=sig

    for _,r in hot.head(6).iterrows():
        title=_display_text(r.get(titlecol) if titlecol else None,"Operational development")
        meta=" · ".join(x for x in [
            _display_date(r.get(dcol) if dcol else None),
            _display_text(r.get(sevcol) if sevcol else None),
            _display_text(r.get(famcol) if famcol else None),
            _display_text(r.get(loccol) if loccol else None),
        ] if x)
        impact=_display_text(r.get(impactcol) if impactcol else None,"Commercial implications are still being assessed.")
        st.markdown(
            f"<div class='pc-card' style='padding:12px 14px;margin-bottom:9px;'>"
            f"<div class='pc-label'>{html_lib.escape(meta)}</div>"
            f"<div style='font-weight:700;font-size:0.98rem;margin:4px 0;'>{html_lib.escape(title)}</div>"
            f"<div class='pc-card-body'>{html_lib.escape(impact[:220])}</div>"
            f"</div>",
            unsafe_allow_html=True
        )

    c1,c2=st.columns(2)
    if c1.button("Open alerts & disruptions",key="overview_exposure_alerts",use_container_width=True):
        request_nav("Alerts & Disruptions")
        st.rerun()
    if c2.button("Open regional maps",key="overview_exposure_maps",use_container_width=True):
        request_nav("Regional Maps")
        st.rerun()


def _render_business_infrastructure():
    st.markdown("### Network moves")
    st.caption("Commercial and infrastructure changes that alter capacity, ownership, access or corridor position.")

    companies=TABLES.get(("Core Entities","Companies"),pd.DataFrame())
    assets=TABLES.get(("Infrastructure","Assets"),pd.DataFrame())
    ports=TABLES.get(("Maritime","Ports"),pd.DataFrame())
    vessels=TABLES.get(("Maritime","Vessels"),pd.DataFrame())
    routes=TABLES.get(("Infrastructure","Transport Routes"),pd.DataFrame())

    n1,n2,n3,n4,n5=st.columns(5)
    n1.metric("Companies",len(companies))
    n2.metric("Infrastructure",len(assets))
    n3.metric("Ports",len(ports))
    n4.metric("Vessels",len(vessels))
    n5.metric("Corridors",len(routes))

    tabs=st.tabs(["Companies in motion","Infrastructure changes","Fleet changes","Corridor changes"])
    with tabs[0]:
        if companies.empty:
            st.caption("No company records.")
        else:
            cols=[c for c in ["Company","Company Name","Name","HQ Country","Country","Sector","Business Segments","Status","As Of"] if c in companies.columns]
            x=companies.copy()
            dc=_first_existing_col(x,["updated_at","created_at","As Of","as_of"])
            if dc:
                x["_d"]=pd.to_datetime(x[dc],errors="coerce")
                x=x.sort_values("_d",ascending=False,na_position="last")
            _compact_trade_table(x,cols,300)

    with tabs[1]:
        frames=[]
        if not ports.empty:
            p=ports.copy()
            p["_kind"]="Port"
            frames.append(p)
        if not assets.empty:
            a=assets.copy()
            a["_kind"]="Infrastructure"
            frames.append(a)
        if frames:
            st.caption("Newest/updated ports, terminals and infrastructure — ownership, location and role first.")
            df=pd.concat(frames,ignore_index=True,sort=False)
            cols=[c for c in ["_kind","Port / Facility","Asset","Name","Country","City / Area","Operator","Operator / Network","Asset Type","Facility Type","Key Role","Status"] if c in df.columns]
            _compact_trade_table(df,cols,320)
        else:
            st.caption("No infrastructure records.")

    with tabs[2]:
        if vessels.empty:
            st.caption("No vessel records.")
        else:
            cols=[c for c in ["Vessel Name","Name","IMO","Vessel Type","Subtype / Class","Flag","Owner","Operator","Status"] if c in vessels.columns]
            _compact_trade_table(vessels,cols,320)

    with tabs[3]:
        if routes.empty:
            st.caption("No corridor records.")
        else:
            cols=[c for c in ["Route","Corridor","Name","Mode","Region","Origin","Destination","Status"] if c in routes.columns]
            _compact_trade_table(routes,cols,320)

def _render_quick_access():
    st.markdown("### Quick access")
    for label,target in [("Companies","Companies"),("Ports & terminals","Ports"),("Vessels","Vessels"),("Corridors","Corridors & Systems"),("Defence","Defence & Shipbuilding"),("Regional maps","Regional Maps")]:
        if st.button(label,use_container_width=True,key='homequick_'+label.replace(' ','_')):
            request_nav(target); st.rerun()



def _display_text(value, default=""):
    """Safe UI text: never render pandas NaN/NaT/None as literal text."""
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass
    s=str(value).strip()
    if not s or s.casefold() in {"nan","nat","none","null","<na>"}:
        return default
    return s

def _display_date(value):
    if value is None:
        return ""
    try:
        dt=pd.to_datetime(value,errors="coerce")
        if pd.notna(dt):
            return dt.strftime("%Y-%m-%d")
    except Exception:
        pass
    return _display_text(value)

def _render_operational_brief():
    st.markdown("### Operational brief")
    st.caption("Four concise trade-impact items. Full incident detail stays in Intelligence.")

    events=TABLES.get(("Events & Hazards","Events"),pd.DataFrame()).copy()
    if events.empty:
        st.caption("No current operational records.")
        return

    date_col=_first_existing_col(events,["Date","Start Date","Event Date"])
    if date_col:
        events["_d"]=pd.to_datetime(events[date_col],errors="coerce")
        events=events.sort_values("_d",ascending=False,na_position="last")

    title_col=_first_existing_col(events,["Title","Event","Event Title"])
    impact_col=_first_existing_col(events,["Trade / Commercial Impact","Commercial Impact","Operational Impact"])
    location_col=_first_existing_col(events,["Location","Region","Country"])
    status_col=_first_existing_col(events,["Status","Event Status"])
    severity_col=_first_existing_col(events,["Severity","Risk","Risk Level"])

    # Prefer rows that actually contain a business/commercial consequence.
    if impact_col:
        impact_series=events[impact_col].apply(_display_text)
        impacted=events[impact_series.ne("")]
        if not impacted.empty:
            events=impacted

    for _,r in events.head(4).iterrows():
        title=_display_text(r.get(title_col) if title_col else None,"Operational issue")
        impact=_display_text(r.get(impact_col) if impact_col else None)
        location=_display_text(r.get(location_col) if location_col else None)
        status=_display_text(r.get(status_col) if status_col else None)
        severity=_display_text(r.get(severity_col) if severity_col else None)
        date=_display_date(r.get(date_col) if date_col else None)

        if len(title) > 92:
            title=title[:89].rstrip()+"…"
        if len(impact) > 145:
            impact=impact[:142].rstrip()+"…"

        meta=" · ".join(x for x in [date,severity,status,location] if x)

        body_html=(
            f'<div class="pc-card-body" style="font-size:0.9rem;line-height:1.4;">'
            f'{html_lib.escape(impact)}</div>'
            if impact else
            '<div class="pc-card-body" style="font-size:0.9rem;line-height:1.4;opacity:.72;">'
            'No separate trade-impact note recorded.</div>'
        )

        st.markdown(
            f"""<div class="pc-card" style="padding:12px 14px;margin-bottom:10px;">
            <div class="pc-label">{html_lib.escape(meta)}</div>
            <div style="font-weight:700;font-size:0.98rem;line-height:1.35;margin:5px 0 6px;">
                {html_lib.escape(title)}
            </div>
            {body_html}
            </div>""",
            unsafe_allow_html=True
        )

    if st.button("Open operational events",use_container_width=True,key="home_operational_events"):
        request_nav("Alerts & Disruptions")
        st.rerun()



@st.cache_data(show_spinner=False,ttl=300)
def canonical_pgsa_vessels_trade():
    """Find the canonical PGSA compliance event carrying the largest linked-vessel set."""
    try:
        sb=pc_db_client(service=True)
    except Exception:
        return {},pd.DataFrame()

    candidates=[]
    try:
        candidates=(sb.table("pc_events")
                    .select("event_id,title,start_date,event_type,severity,status,location,description,operational_impact,commercial_impact")
                    .eq("event_type","VESSEL_COMPLIANCE_LIST_UPDATE")
                    .order("start_date",desc=True)
                    .limit(20)
                    .execute().data or [])
    except Exception:
        candidates=[]

    if not candidates:
        for term in ["%PGSA%","%non-compliant%","%77 vessels%"]:
            try:
                candidates=(sb.table("pc_events")
                            .select("event_id,title,start_date,event_type,severity,status,location,description,operational_impact,commercial_impact")
                            .ilike("title",term)
                            .order("start_date",desc=True)
                            .limit(20)
                            .execute().data or [])
            except Exception:
                candidates=[]
            if candidates:
                break

    best_event={}
    best_links=[]
    for event in candidates:
        eid=event.get("event_id")
        if not eid:
            continue
        try:
            links=(sb.table("pc_event_links")
                   .select("linked_id,linked_type,relationship")
                   .eq("event_id",eid)
                   .eq("linked_type","mobile_asset")
                   .limit(500)
                   .execute().data or [])
        except Exception:
            links=[]
        if len(links)>len(best_links):
            best_event=event
            best_links=links

    if not best_event or not best_links:
        return best_event,pd.DataFrame()

    ids=[str(x.get("linked_id")) for x in best_links if x.get("linked_id")]
    assets=[]
    for i in range(0,len(ids),100):
        batch=ids[i:i+100]
        try:
            assets.extend(
                sb.table("pc_mobile_assets")
                  .select("mobile_asset_id,name,imo,mmsi,flag,asset_type,subtype,status,owner_entity_id,operator_entity_id")
                  .in_("mobile_asset_id",batch)
                  .execute().data or []
            )
        except Exception:
            for oid in batch:
                try:
                    assets.extend(
                        sb.table("pc_mobile_assets")
                          .select("mobile_asset_id,name,imo,mmsi,flag,asset_type,subtype,status,owner_entity_id,operator_entity_id")
                          .eq("mobile_asset_id",oid)
                          .limit(1)
                          .execute().data or []
                    )
                except Exception:
                    pass

    rel_by_id={str(x.get("linked_id")):x.get("relationship") for x in best_links}
    rows=[]
    for r in assets:
        oid=str(r.get("mobile_asset_id") or "")
        rows.append({
            "Vessel":r.get("name"),
            "IMO":r.get("imo"),
            "MMSI":r.get("mmsi"),
            "Flag":r.get("flag"),
            "Vessel Type":r.get("subtype") or r.get("asset_type"),
            "Status":r.get("status"),
            "Relationship":rel_by_id.get(oid),
            "Canonical ID":oid,
        })
    df=pd.DataFrame(rows)
    if not df.empty:
        df=df.sort_values(["Vessel","IMO"],na_position="last").reset_index(drop=True)
    return best_event,df




def _pc_meta_dict(value):
    """Normalize JSON/dict metadata from Supabase or legacy bridge."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed=json.loads(value)
            return parsed if isinstance(parsed,dict) else {}
        except Exception:
            return {}
    return {}


def trade_horizon_events(df=None):
    """Canonical Trade Horizon.

    Explicit metadata.horizon rows are authoritative. We also infer clearly
    forward-looking trade events for backward compatibility. Crucially, horizon
    rows without a precise Start Date are retained rather than silently dropped.
    """
    if df is None or df.empty:
        df=TABLES.get(("Events & Hazards","Events"),pd.DataFrame()).copy()
    if df is None or df.empty:
        return pd.DataFrame()

    out=df.copy()
    meta_series=out.get("Metadata",pd.Series([{}]*len(out),index=out.index))

    def _h(v):
        m=_pc_meta_dict(v)
        h=m.get("horizon")
        return h if isinstance(h,dict) else {}

    hmeta=meta_series.apply(_h)
    explicit=hmeta.apply(lambda h: bool(h.get("show_in_trade_horizon")))

    blob=pd.Series("",index=out.index,dtype="string")
    for c in [
        "Event Nature","Event Domain","Event Family","Event Type","Title","Description",
        "Operational Impact","Trade / Commercial Impact","Country / Countries",
        "Location","Mode","Status"
    ]:
        if c in out.columns:
            blob=blob.str.cat(out[c].fillna("").astype(str),sep=" ")

    meta_text=hmeta.apply(
        lambda h:" ".join(str(x) for x in [
            h.get("horizon_type"),h.get("next_milestone"),h.get("date_precision"),
            h.get("target_year"),h.get("target_date"),h.get("window")
        ] if x not in (None,""))
    ).astype("string")

    inferred=blob.str.cat(meta_text,sep=" ").str.contains(
        r"scheduled|forecast|recurring|seasonal|upcoming|planned|deadline|ballot|"
        r"milestone|opening|tender|award|approval|expiry|strike vote|possible strike|"
        r"monsoon|hurricane season|cyclone season|chokepoint watch|developing risk|"
        r"project milestone|capacity addition|service launch|route launch",
        case=False,regex=True,na=False
    )
    inferred &= blob.str.contains(
        r"port|maritime|shipping|aviation|airport|air cargo|rail|road|truck|border|"
        r"customs|energy|oil|gas|lng|trade|logistics|supply|business|terminal|"
        r"corridor|canal|sanction|tariff|compliance",
        case=False,regex=True,na=False
    )

    result=out[explicit | inferred].copy()
    if result.empty:
        return result

    result["Horizon Type"]=hmeta.loc[result.index].apply(lambda h:str(h.get("horizon_type") or ""))
    result["Next Milestone"]=hmeta.loc[result.index].apply(lambda h:str(h.get("next_milestone") or ""))
    result["Target Year"]=hmeta.loc[result.index].apply(lambda h:str(h.get("target_year") or ""))
    result["Date Precision"]=hmeta.loc[result.index].apply(lambda h:str(h.get("date_precision") or ""))
    result["Explicit Horizon"]=explicit.loc[result.index].astype(bool)

    if "Start Date" in result.columns:
        result["_horizon_date"]=pd.to_datetime(result["Start Date"],errors="coerce",utc=True).dt.tz_convert(None)
    else:
        result["_horizon_date"]=pd.NaT

    # Future project target_year is useful even when start_date is the announcement date.
    def _effective_date(row):
        d=row.get("_horizon_date")
        try:
            if pd.notna(d):
                return d
        except Exception:
            pass
        yr=str(row.get("Target Year") or "").strip()
        if yr.isdigit() and len(yr)==4:
            return pd.Timestamp(f"{yr}-01-01")
        return pd.NaT
    result["_effective_horizon_date"]=result.apply(_effective_date,axis=1)

    # Keep explicit items first, then dated future items, then undated developing risks.
    result["_explicit_rank"]=result["Explicit Horizon"].astype(int)
    result=result.sort_values(
        ["_explicit_rank","_effective_horizon_date"],
        ascending=[False,True],
        na_position="last"
    )
    return result


def _trade_horizon_bucket(row, today=None):
    today=today or pd.Timestamp.utcnow().tz_localize(None).normalize()
    htype=str(row.get("Horizon Type") or "").casefold()
    status=str(row.get("Status") or "").casefold()
    d=row.get("_effective_horizon_date")
    if "project" in htype or str(row.get("Target Year") or "").strip():
        return "Projects & milestones"
    if any(x in htype for x in ["risk","watch","develop"]) or any(x in status for x in ["monitor","develop","pending"]):
        return "Developing risks"
    try:
        if pd.notna(d) and d >= today:
            return "Upcoming"
    except Exception:
        pass
    return "Other horizon"


def render_trade_horizon_workspace():
    """Live canonical Trade Horizon with future, undated and long-dated items."""
    header(
        "Trade Horizon",
        "Upcoming milestones, developing risks, project openings, regulatory deadlines and seasonal trade events. Explicit canonical horizon metadata is authoritative."
    )

    # Always use the canonical event table that was loaded from Supabase into TABLES.
    canonical_events=TABLES.get(("Events & Hazards","Events"),pd.DataFrame()).copy()
    fdf=trade_horizon_events(canonical_events)

    if fdf.empty:
        st.info(
            "No Trade Horizon items are currently classified. "
            "Canonical events need metadata.horizon.show_in_trade_horizon=true, "
            "or a clearly forward-looking trade classification."
        )
        return

    today=pd.Timestamp.utcnow().tz_localize(None).normalize()

    # Debug/health strip makes it obvious whether horizon metadata is arriving from DB.
    explicit_count=int(fdf.get("Explicit Horizon",pd.Series(False,index=fdf.index)).fillna(False).sum())
    dated_count=int(fdf.get("_effective_horizon_date",pd.Series(pd.NaT,index=fdf.index)).notna().sum())
    m1,m2,m3,m4=st.columns(4)
    m1.metric("Horizon items",len(fdf))
    m2.metric("Explicit canonical",explicit_count)
    m3.metric("Dated / year-targeted",dated_count)
    m4.metric("Developing / undated",len(fdf)-dated_count)

    c1,c2,c3=st.columns(3)
    window=c1.selectbox(
        "Window",
        ["All horizon","Next 30 days","Next 90 days","Next 12 months","Long-term projects"],
        index=0,
        key="trade_horizon_window_v342"
    )
    mode_values=["All"]+sorted(
        [x for x in fdf.get("Mode",pd.Series(dtype=str)).fillna("").astype(str).unique() if x]
    )
    from pc_display import country_tokens as _pc_country_tokens
    country_values=["All"]+sorted({
        c for raw in fdf.get("Country / Countries",pd.Series(dtype=str)).fillna("").astype(str)
        for c in _pc_country_tokens(raw) if c
    })
    mode=c2.selectbox("Mode",mode_values,key="trade_horizon_mode_v342",
                      format_func=lambda v:pc_format_filter_option(v,"Mode"))
    country=c3.selectbox("Country / region",country_values,key="trade_horizon_country_v342")

    view=fdf.copy()
    d=view["_effective_horizon_date"]

    if window=="Next 30 days":
        upper=today+pd.Timedelta(days=30)
        # Retain explicit undated developing risks; they are horizon items too.
        view=view[(d.isna() & view["Explicit Horizon"]) | ((d>=today)&(d<=upper))]
    elif window=="Next 90 days":
        upper=today+pd.Timedelta(days=90)
        view=view[(d.isna() & view["Explicit Horizon"]) | ((d>=today)&(d<=upper))]
    elif window=="Next 12 months":
        upper=today+pd.Timedelta(days=365)
        view=view[(d.isna() & view["Explicit Horizon"]) | ((d>=today)&(d<=upper))]
    elif window=="Long-term projects":
        view=view[
            view["Horizon Type"].fillna("").astype(str).str.contains("project|milestone",case=False,regex=True,na=False)
            | view["Target Year"].fillna("").astype(str).ne("")
        ]

    if mode!="All" and "Mode" in view.columns:
        view=view[view["Mode"].fillna("").astype(str).eq(mode)]
    if country!="All" and "Country / Countries" in view.columns:
        view=view[view["Country / Countries"].fillna("").astype(str).map(
            lambda raw: country in _pc_country_tokens(raw)
        )]

    if view.empty:
        st.warning("No Horizon items match this filter window. Try **All horizon**.")
        return

    view["Horizon Bucket"]=view.apply(lambda r:_trade_horizon_bucket(r,today),axis=1)

    # Present as cards so each item opens the same database graph drilldown as stories.
    tabs=st.tabs(["All","Upcoming","Developing risks","Projects & milestones"])
    bucket_defs=[
        ("All",None),
        ("Upcoming","Upcoming"),
        ("Developing risks","Developing risks"),
        ("Projects & milestones","Projects & milestones"),
    ]
    for tab,(label_txt,bucket) in zip(tabs,bucket_defs):
        with tab:
            sub=view if bucket is None else view[view["Horizon Bucket"].eq(bucket)]
            if sub.empty:
                st.caption(f"No {label_txt.lower()} items in the selected window.")
                continue

            # Reuse story graph enrichment if available; otherwise construct display columns.
            story_frame=_canonical_trade_story_frame()
            if not story_frame.empty and "Event ID" in story_frame.columns:
                ids=set(sub["Event ID"].astype(str)) if "Event ID" in sub.columns else set()
                cards=story_frame[story_frame["Event ID"].astype(str).isin(ids)].copy()
                if not cards.empty:
                    # Preserve horizon ordering.
                    order={str(eid):i for i,eid in enumerate(sub["Event ID"].astype(str).tolist())}
                    cards["_hor_order"]=cards["Event ID"].astype(str).map(order)
                    cards=cards.sort_values("_hor_order")
                    _render_trade_story_cards(cards,50,show_why=True,key_prefix=f"horizon_{bucket or 'all'}")
                    continue

            # Fallback if story projection isn't available.
            cols=[c for c in [
                "Start Date","Horizon Type","Next Milestone","Target Year",
                "Country / Countries","Location","Event Family","Event Type",
                "Title","Severity","Status","Mode","Operational Impact",
                "Trade / Commercial Impact","Confidence"
            ] if c in sub.columns]
            display_df(sub[cols],620)

    with st.expander("Horizon classification diagnostics",expanded=False):
        diag_cols=[c for c in [
            "Event ID","Title","Start Date","Horizon Type","Next Milestone",
            "Target Year","Date Precision","Explicit Horizon","Status","Mode"
        ] if c in fdf.columns]
        display_df(fdf[diag_cols],420)



@st.cache_data(show_spinner=False, ttl=60)
def _canonical_trade_link_labels():
    """Resolve canonical event links to readable company/asset/vessel/route labels."""
    try:
        sb=pc_db_client(service=True)
        if sb is None:
            return {}
        links=pc_safe_rows(
            sb,"pc_event_links",
            "event_id,linked_type,linked_id,linked_name,relationship,confidence,metadata",
            30000
        ) or []
        if not links:
            return {}

        entities=pc_safe_rows(sb,"pc_entities","entity_id,name",20000) or []
        assets=pc_safe_rows(sb,"pc_assets","asset_id,name",30000) or []
        mobile=pc_safe_rows(sb,"pc_mobile_assets","mobile_asset_id,name,imo",30000) or []
        routes=pc_safe_rows(sb,"pc_transport_routes","route_id,route_name",20000) or []

        names={}
        names.update({("entity",str(r.get("entity_id") or "")):str(r.get("name") or "") for r in entities})
        names.update({("asset",str(r.get("asset_id") or "")):str(r.get("name") or "") for r in assets})
        names.update({("mobile_asset",str(r.get("mobile_asset_id") or "")):str(r.get("name") or "") for r in mobile})
        names.update({("route",str(r.get("route_id") or "")):str(r.get("route_name") or "") for r in routes})

        out=defaultdict(list)
        for r in links:
            eid=str(r.get("event_id") or "").strip()
            typ=str(r.get("linked_type") or "").strip().casefold()
            lid=str(r.get("linked_id") or "").strip()
            if not eid or not lid:
                continue
            norm=typ
            if typ in {"company","organisation","organization"}: norm="entity"
            elif typ in {"vessel","ship","aircraft"}: norm="mobile_asset"
            elif typ in {"port","terminal","facility","infrastructure"}: norm="asset"
            elif typ in {"transport_route","corridor","network"}: norm="route"
            label_txt=str(r.get("linked_name") or names.get((norm,lid)) or lid).strip()
            rel=str(r.get("relationship") or "").strip()
            out[eid].append({
                "type":norm,"id":lid,"label":label_txt,"relationship":rel,
                "confidence":r.get("confidence")
            })
        return dict(out)
    except Exception:
        return {}


def _canonical_trade_story_frame():
    """Presentation view over canonical pc_events; no duplicate news universe."""
    ev=TABLES.get(("Events & Hazards","Events"),pd.DataFrame()).copy()
    if ev.empty:
        return ev

    links=_canonical_trade_link_labels()
    rows=[]
    for _,r in ev.iterrows():
        m=_pc_meta_dict(r.get("Metadata"))
        story=m.get("story") if isinstance(m.get("story"),dict) else {}
        disruption=m.get("disruption") if isinstance(m.get("disruption"),dict) else {}
        horizon=m.get("horizon") if isinstance(m.get("horizon"),dict) else {}
        eid=str(r.get("Event ID") or "")
        linkrows=links.get(eid,[])
        labels=[x.get("label") for x in linkrows if x.get("label")]
        entity_labels=[x.get("label") for x in linkrows if x.get("type")=="entity" and x.get("label")]
        asset_labels=[x.get("label") for x in linkrows if x.get("type") in {"asset","mobile_asset"} and x.get("label")]
        route_labels=[x.get("label") for x in linkrows if x.get("type")=="route" and x.get("label")]

        sources=m.get("research_sources") or []
        if isinstance(sources,str):
            sources=[sources]

        item=dict(r)
        item.update({
            "Is Story":bool(story.get("is_story")),
            "Lead Story":bool(story.get("lead_story")),
            "Story Category":str(story.get("story_category") or r.get("Event Family") or ""),
            "Card Title":str(story.get("card_title") or r.get("Title") or ""),
            "Card Deck":str(story.get("card_deck") or r.get("Description") or ""),
            "Why It Matters":str(story.get("why_it_matters") or r.get("Trade / Commercial Impact") or r.get("Operational Impact") or ""),
            "Linked Objects":" · ".join(dict.fromkeys(labels)),
            "Linked Companies":" · ".join(dict.fromkeys(entity_labels)),
            "Linked Assets":" · ".join(dict.fromkeys(asset_labels)),
            "Linked Routes":" · ".join(dict.fromkeys(route_labels)),
            "Is Disruption":bool(disruption.get("is_disruption")),
            "Primary Disruption":bool(disruption.get("primary_disruption")),
            "Disruption Domains":", ".join(str(x) for x in (disruption.get("disruption_domains") or [])),
            "Disruption Type":str(disruption.get("disruption_type") or ""),
            "Disruption Status":str(disruption.get("status") or ""),
            "Horizon":bool(horizon.get("show_in_trade_horizon")),
            "Horizon Type":str(horizon.get("horizon_type") or ""),
            "Next Milestone":str(horizon.get("next_milestone") or ""),
            "Research Sources":sources,
        })
        rows.append(item)

    out=pd.DataFrame(rows)
    if "Start Date" in out.columns:
        out["_dt"]=pd.to_datetime(out["Start Date"],errors="coerce",utc=True).dt.tz_convert(None)
        out=out.sort_values("_dt",ascending=False,na_position="last")
    return out



@st.cache_data(show_spinner=False, ttl=60)
def _load_trade_event_database_context(event_id):
    """Return the full canonical database context behind one Trade story/event."""
    eid=str(event_id or "").strip()
    if not eid:
        return {}
    try:
        sb=pc_db_client(service=True)
        if sb is None:
            return {}

        event_rows=(sb.table("pc_events").select("*").eq("event_id",eid).limit(1).execute().data or [])
        if not event_rows:
            return {}
        event=event_rows[0]

        try:
            locations=(sb.table("pc_event_locations").select("*").eq("event_id",eid).execute().data or [])
        except Exception:
            locations=[]

        try:
            links=(sb.table("pc_event_links").select("*").eq("event_id",eid).execute().data or [])
        except Exception:
            links=[]

        entity_ids=[]; asset_ids=[]; mobile_ids=[]; route_ids=[]
        for l in links:
            typ=str(l.get("linked_type") or "").strip().casefold()
            lid=str(l.get("linked_id") or "").strip()
            if not lid:
                continue
            if typ in {"entity","company","organisation","organization"}:
                entity_ids.append(lid)
            elif typ in {"asset","port","terminal","facility","infrastructure"}:
                asset_ids.append(lid)
            elif typ in {"mobile_asset","vessel","ship","aircraft"}:
                mobile_ids.append(lid)
            elif typ in {"route","transport_route","corridor","network"}:
                route_ids.append(lid)

        def rows_for(table,key,ids):
            if not ids:
                return []
            try:
                return (sb.table(table).select("*").in_(key,list(dict.fromkeys(ids))).execute().data or [])
            except Exception:
                return []

        entities=rows_for("pc_entities","entity_id",entity_ids)
        assets=rows_for("pc_assets","asset_id",asset_ids)
        mobile=rows_for("pc_mobile_assets","mobile_asset_id",mobile_ids)
        routes=rows_for("pc_transport_routes","route_id",route_ids)

        # Graph relationships touching any object linked to this event.
        rels=[]
        endpoint_ids=list(dict.fromkeys(entity_ids+asset_ids+mobile_ids+route_ids))
        if endpoint_ids:
            try:
                src=(sb.table("pc_relationships").select("*").in_("source_id",endpoint_ids).execute().data or [])
            except Exception:
                src=[]
            try:
                tgt=(sb.table("pc_relationships").select("*").in_("target_id",endpoint_ids).execute().data or [])
            except Exception:
                tgt=[]
            seen=set()
            for rr in src+tgt:
                rid=str(rr.get("relationship_id") or "")
                if rid and rid not in seen:
                    seen.add(rid); rels.append(rr)

        # Sanctions context for any linked entities.
        sanctions_links=[]
        sanctions=[]
        if entity_ids:
            try:
                sanctions_links=(sb.table("pc_sanctions_entity_links").select("*")
                                 .in_("entity_id",list(dict.fromkeys(entity_ids))).execute().data or [])
            except Exception:
                sanctions_links=[]
            designation_ids=[
                str(x.get("designation_id") or "").strip()
                for x in sanctions_links if x.get("designation_id")
            ]
            if designation_ids:
                try:
                    sanctions=(sb.table("pc_sanctions_designations").select("*")
                               .in_("designation_id",list(dict.fromkeys(designation_ids))).execute().data or [])
                except Exception:
                    sanctions=[]

        # Resolve the event source row as well as URL-bearing metadata.
        source_rows=[]
        source_id=str(event.get("source_id") or "").strip()
        if source_id:
            try:
                source_rows=(sb.table("pc_sources").select("*").eq("source_id",source_id).limit(3).execute().data or [])
            except Exception:
                source_rows=[]

        return {
            "event":event,
            "locations":locations,
            "links":links,
            "entities":entities,
            "assets":assets,
            "mobile_assets":mobile,
            "routes":routes,
            "relationships":rels,
            "sanctions_links":sanctions_links,
            "sanctions":sanctions,
            "sources":source_rows,
        }
    except Exception:
        return {}


def _pretty_json_value(v):
    if isinstance(v,(dict,list)):
        try:
            return json.dumps(v,ensure_ascii=False,indent=2,default=str)
        except Exception:
            return str(v)
    return "" if v is None else str(v)


def _human_record_table(rows, preferred=None):
    if not rows:
        return pd.DataFrame()
    df=pd.DataFrame(rows)
    if preferred:
        cols=[c for c in preferred if c in df.columns]
        rest=[c for c in df.columns if c not in cols and c not in {"created_at","updated_at"}]
        df=df[cols+rest]
    return df


def _event_source_urls(ctx):
    urls=[]
    ev=(ctx or {}).get("event") or {}
    meta=_pc_meta_dict(ev.get("metadata"))
    for key in ["research_sources","sources"]:
        vals=meta.get(key) or []
        if isinstance(vals,str): vals=[vals]
        if isinstance(vals,list):
            for x in vals:
                if isinstance(x,str) and x.startswith(("http://","https://")):
                    urls.append(x)
                elif isinstance(x,dict):
                    u=str(x.get("url") or x.get("source_url") or "")
                    if u.startswith(("http://","https://")):
                        urls.append(u)
    for s in (ctx or {}).get("sources") or []:
        for k in ["url","source_url"]:
            u=str(s.get(k) or "")
            if u.startswith(("http://","https://")):
                urls.append(u)
    return list(dict.fromkeys(urls))


def render_selected_trade_story_context():
    """Full connected trade-intelligence view for the selected canonical Trade story."""
    eid=str(st.session_state.get("trade_story_event_id") or "").strip()
    if not eid:
        return

    ctx=_load_trade_event_database_context(eid)
    ev=ctx.get("event") or {}
    if not ev:
        st.warning("The selected event is no longer available in the connected trade model.")
        if st.button("Close story context",key="close_missing_trade_story"):
            st.session_state.pop("trade_story_event_id",None)
            st.rerun()
        return

    meta=_pc_meta_dict(ev.get("metadata"))
    story=meta.get("story") if isinstance(meta.get("story"),dict) else {}
    disruption=meta.get("disruption") if isinstance(meta.get("disruption"),dict) else {}
    horizon=meta.get("horizon") if isinstance(meta.get("horizon"),dict) else {}

    title=str(story.get("card_title") or ev.get("title") or "Selected trade development")
    deck=str(story.get("card_deck") or ev.get("description") or "")
    why=str(story.get("why_it_matters") or ev.get("commercial_impact") or ev.get("operational_impact") or "")

    st.markdown("---")
    cclose,ctitle=st.columns([0.18,0.82])
    with cclose:
        if st.button("← Close",key=f"close_trade_story_{eid}",use_container_width=True):
            st.session_state.pop("trade_story_event_id",None)
            st.rerun()
    with ctitle:
        st.markdown("### Connected trade intelligence")

    st.markdown(
        f"""<div class='pc-hero'>
        <div class='pc-label'>{html_lib.escape(str(ev.get('event_family') or 'TRADE DEVELOPMENT'))}</div>
        <div class='pc-hero-title'>{html_lib.escape(title)}</div>
        <div class='pc-hero-copy'>{html_lib.escape(deck)}</div>
        </div>""",
        unsafe_allow_html=True
    )

    m1,m2,m3,m4,m5=st.columns(5)
    m1.metric("Severity",str(ev.get("severity") or "—"))
    m2.metric("Status",str(ev.get("status") or "—"))
    m3.metric("Domain",str(ev.get("event_domain") or ev.get("mode") or "—"))
    m4.metric("Confidence",str(ev.get("confidence") or "—"))
    m5.metric("Linked objects",len(ctx.get("links") or []))

    # The value layer: effects and implications first.
    st.markdown("#### Effects & implications")
    e1,e2=st.columns(2,gap="large")
    with e1:
        st.markdown(
            f"""<div class='pc-card'>
            <div class='pc-label'>Operational effect</div>
            <div class='pc-search-details'>{html_lib.escape(str(ev.get('operational_impact') or disruption.get('operational_effect') or 'Not yet assessed.'))}</div>
            </div>""",unsafe_allow_html=True
        )
        if disruption:
            st.markdown(
                f"""<div class='pc-card'>
                <div class='pc-label'>Disruption classification</div>
                <div><b>Type:</b> {html_lib.escape(str(disruption.get('disruption_type') or '—'))}</div>
                <div><b>Status:</b> {html_lib.escape(str(disruption.get('status') or '—'))}</div>
                <div><b>Domains:</b> {html_lib.escape(', '.join(str(x) for x in (disruption.get('disruption_domains') or [])) or '—')}</div>
                </div>""",unsafe_allow_html=True
            )
    with e2:
        st.markdown(
            f"""<div class='pc-card'>
            <div class='pc-label'>Commercial / trade effect</div>
            <div class='pc-search-details'>{html_lib.escape(str(ev.get('commercial_impact') or disruption.get('commercial_effect') or why or 'Not yet assessed.'))}</div>
            </div>""",unsafe_allow_html=True
        )
        if horizon:
            st.markdown(
                f"""<div class='pc-card'>
                <div class='pc-label'>Trade Horizon</div>
                <div><b>Type:</b> {html_lib.escape(str(horizon.get('horizon_type') or '—'))}</div>
                <div><b>Next milestone:</b> {html_lib.escape(str(horizon.get('next_milestone') or '—'))}</div>
                </div>""",unsafe_allow_html=True
            )

    tabs=st.tabs([
        "Connected companies & infrastructure",
        "Event & impact",
        "Ownership & network",
        "Affected locations",
        "Sanctions & compliance",
        "Evidence & sources"
    ])

    with tabs[0]:
        groups=[
            ("Companies / entities",ctx.get("entities") or [],["entity_id","name","entity_type","subtype","hq_country","status","description"]),
            ("Fixed assets",ctx.get("assets") or [],["asset_id","name","asset_type","subtype","country","region_city","status"]),
            ("Vessels / mobile assets",ctx.get("mobile_assets") or [],["mobile_asset_id","name","asset_type","subtype","imo","mmsi","flag","status"]),
            ("Routes / corridors",ctx.get("routes") or [],["route_id","route_name","mode","origin_name","destination_name","status"]),
        ]
        any_rows=False
        for label_txt,rows,pref in groups:
            if rows:
                any_rows=True
                st.markdown(f"**{label_txt}**")
                display_df(_human_record_table(rows,pref),240)
        if not any_rows:
            st.caption("No linked canonical objects were returned for this event.")

        links=ctx.get("links") or []
        if links:
            st.markdown("**Event-link semantics**")
            ldf=_human_record_table(
                links,
                ["event_link_id","linked_type","linked_id","linked_name","relationship","confidence"]
            )
            display_df(ldf,260)

    with tabs[1]:
        # Human-readable first, complete raw canonical row second.
        fields=[
            ("Event ID","event_id"),("Start","start_date"),("End","end_date"),
            ("Nature","event_nature"),("Domain","event_domain"),("Family","event_family"),
            ("Type","event_type"),("Severity","severity"),("Status","status"),
            ("Mode","mode"),("Countries","countries"),("Location","location"),
            ("Trade relevance","trade_relevance"),("Intelligence relevance","intelligence_relevance"),
            ("Trade visible","trade_visible"),("Intelligence visible","intelligence_visible"),
            ("Alert worthy","alert_worthy"),("Record status","record_status")
        ]
        rows=[{"Field":label_txt,"Value":_pretty_json_value(ev.get(key))} for label_txt,key in fields if ev.get(key) not in (None,"")]
        display_df(pd.DataFrame(rows),380)
        with st.expander("Raw canonical event metadata",expanded=False):
            st.json(meta)

    with tabs[2]:
        rels=ctx.get("relationships") or []
        if rels:
            display_df(
                _human_record_table(
                    rels,
                    ["relationship_id","source_type","source_id","relationship_type","target_type","target_id","confidence","record_status"]
                ),
                360
            )
        else:
            st.caption("No additional canonical relationships touch the linked objects.")

    with tabs[3]:
        locs=ctx.get("locations") or []
        if locs:
            display_df(
                _human_record_table(
                    locs,
                    ["event_location_id","location_name","country","latitude","longitude","accuracy","notes"]
                ),
                280
            )
        else:
            st.caption("No canonical event-location rows are attached.")

    with tabs[4]:
        sanc=ctx.get("sanctions") or []
        slinks=ctx.get("sanctions_links") or []
        if sanc:
            st.markdown("**Sanctions designations affecting linked entities**")
            display_df(_human_record_table(sanc,["designation_id","designation_date","target_type","target_name","regime_linkage","record_status","source_url"]),320)
            if slinks:
                st.markdown("**Sanctions entity links**")
                display_df(_human_record_table(slinks,["designation_id","entity_id","relationship","confidence","record_status"]),220)
        else:
            st.caption("No sanctions designation is currently linked to this event's canonical entities.")

    with tabs[5]:
        urls=_event_source_urls(ctx)
        if urls:
            for i,u in enumerate(urls,1):
                st.markdown(f"**Source {i}:** [{u}]({u})")
        else:
            st.caption("No source URL was found in the event/source metadata.")
        if ctx.get("sources"):
            st.markdown("**Canonical source records**")
            display_df(_human_record_table(ctx["sources"]),260)

    st.markdown("---")



def _render_inline_trade_story_context(event_id, key_prefix="storyctx"):
    """Render connected canonical context inline beneath a Trade story.

    The Trade home should not force the analyst to jump to a page-level context block.
    Linked canonical objects remain actionable through the shared drill-down panel.
    """
    eid=str(event_id or "").strip()
    if not eid:
        st.caption("No canonical event ID is attached to this story.")
        return

    ctx=_load_trade_event_database_context(eid)
    ev=ctx.get("event") or {}
    if not ev:
        st.caption("No connected canonical context was returned for this event.")
        return

    meta=_pc_meta_dict(ev.get("metadata"))
    story=meta.get("story") if isinstance(meta.get("story"),dict) else {}
    disruption=meta.get("disruption") if isinstance(meta.get("disruption"),dict) else {}
    horizon=meta.get("horizon") if isinstance(meta.get("horizon"),dict) else {}

    def _clean_ctx(v):
        try:
            if pd.isna(v):
                return ""
        except Exception:
            pass
        txt=str(v or "").strip()
        return "" if txt.casefold() in {"nan","none","null","nat"} else txt

    title=_clean_ctx(story.get("card_title") or ev.get("title")) or "Selected trade development"
    deck=_clean_ctx(story.get("card_deck") or ev.get("description"))
    operational=_clean_ctx(ev.get("operational_impact") or disruption.get("operational_effect"))
    commercial=_clean_ctx(ev.get("commercial_impact") or disruption.get("commercial_effect") or story.get("why_it_matters"))

    st.markdown(f"**{html_lib.escape(title)}**")
    if deck:
        st.caption(deck)

    c1,c2=st.columns(2,gap="large")
    with c1:
        if operational:
            st.markdown("**Operational effect**")
            st.write(operational)
    with c2:
        if commercial:
            st.markdown("**Trade / commercial effect**")
            st.write(commercial)

    linked_tabs=st.tabs(["Connected network","Event details","Evidence"])

    with linked_tabs[0]:
        groups=[
            ("Companies / entities","entity",ctx.get("entities") or [],"entity_id","name"),
            ("Infrastructure / assets","asset",ctx.get("assets") or [],"asset_id","name"),
            ("Vessels / mobile assets","mobile_asset",ctx.get("mobile_assets") or [],"mobile_asset_id","name"),
            ("Routes / corridors","route",ctx.get("routes") or [],"route_id","route_name"),
        ]
        any_rows=False
        for group_label,obj_type,rows,id_key,name_key in groups:
            if not rows:
                continue
            any_rows=True
            st.markdown(f"**{group_label}**")
            for i,rec in enumerate(rows):
                oid=_clean_ctx(rec.get(id_key))
                name=_clean_ctx(rec.get(name_key)) or oid
                # Short human-readable object summary before the action.
                bits=[]
                for field in ["entity_type","subtype","hq_country","country","region_city","mode","origin_name","destination_name","imo","flag","status"]:
                    val=_clean_ctx(rec.get(field))
                    if val and val not in bits:
                        bits.append(val)
                st.markdown(f"**{html_lib.escape(name)}**" + (f" · {html_lib.escape(' · '.join(bits[:4]))}" if bits else ""))
                if oid:
                    pc_drilldown_button(
                        obj_type,
                        oid,
                        f"Open { {'entity':'company','asset':'asset','mobile_asset':'vessel / mobile asset','route':'route'}[obj_type] }",
                        key=f"{key_prefix}_{eid}_{obj_type}_{oid}_{i}",
                        use_container_width=True,
                    )

        if not any_rows:
            st.caption("No linked canonical objects were returned for this event.")

        links=ctx.get("links") or []
        if links:
            with st.expander("Relationship detail",expanded=False):
                ldf=_human_record_table(
                    links,
                    ["linked_type","linked_name","relationship","confidence","linked_id"]
                )
                display_df(ldf,240)

        rels=ctx.get("relationships") or []
        if rels:
            with st.expander("Ownership & operating relationships",expanded=False):
                display_df(
                    _human_record_table(
                        rels,
                        ["source_name","source_type","relationship_type","target_name","target_type","confidence"]
                    ),
                    260,
                )

    with linked_tabs[1]:
        fields=[
            ("Start", "start_date"),("End", "end_date"),("Nature", "event_nature"),
            ("Domain", "event_domain"),("Family", "event_family"),("Type", "event_type"),
            ("Status", "status"),("Mode", "mode"),("Countries", "countries"),
            ("Location", "location"),("Confidence", "confidence"),
        ]
        rows=[]
        for label_txt,key in fields:
            val=_clean_ctx(ev.get(key))
            if val:
                rows.append({"Field":label_txt,"Value":val})
        if rows:
            display_df(pd.DataFrame(rows),260)
        locs=ctx.get("locations") or []
        if locs:
            st.markdown("**Affected locations**")
            display_df(_human_record_table(locs,["location_name","country","accuracy","notes"]),220)
        if horizon:
            hm=[]
            for label_txt,key in [("Horizon type","horizon_type"),("Next milestone","next_milestone")]:
                val=_clean_ctx(horizon.get(key))
                if val:
                    hm.append({"Field":label_txt,"Value":val})
            if hm:
                st.markdown("**Forward context**")
                display_df(pd.DataFrame(hm),160)

    with linked_tabs[2]:
        urls=_event_source_urls(ctx)
        if urls:
            for i,u in enumerate(urls,1):
                st.markdown(f"**Source {i}:** [{u}]({u})")
        else:
            st.caption("No source URL was found in the event/source metadata.")


def _render_trade_story_cards(df,max_items=8,show_why=True,key_prefix="story"):
    if df is None or df.empty:
        st.caption("No canonical developments in this view.")
        return
    for card_i,(_,r) in enumerate(df.head(max_items).iterrows()):
        eid=str(r.get("Event ID") or r.get("event_id") or "").strip()
        title=html_lib.escape(str(r.get("Card Title") or r.get("Title") or "Untitled"))
        cat=html_lib.escape(str(r.get("Story Category") or r.get("Event Family") or "Development"))
        date=str(r.get("Start Date") or "")[:10]
        status=html_lib.escape(str(r.get("Status") or ""))
        deck=html_lib.escape(str(r.get("Card Deck") or r.get("Description") or ""))
        why=html_lib.escape(str(r.get("Why It Matters") or ""))
        linked=html_lib.escape(str(r.get("Linked Objects") or ""))
        dis=bool(r.get("Is Disruption"))
        horizon=bool(r.get("Horizon"))
        chips=[cat]
        if dis: chips.append("DISRUPTION")
        if horizon: chips.append("TRADE HORIZON")
        if status: chips.append(status.upper())
        chip_html="".join(f"<span class='pc-chip'>{html_lib.escape(str(x))}</span>" for x in chips if x)

        # Card shows the value proposition before the user opens the full graph.
        body=f"""
        <div class='pc-card'>
          <div class='pc-label'>{html_lib.escape(date)}</div>
          <div class='pc-big' style='margin-top:3px'>{title}</div>
          <div style='margin-top:7px'>{chip_html}</div>
          <div class='pc-search-details'>{deck}</div>
        """
        if show_why and why:
            body += f"<div style='margin-top:9px'><b style='color:#D8B45A'>Why it matters:</b> {why}</div>"
        if linked:
            body += f"<div class='pc-small' style='margin-top:8px'><b>Connected:</b> {linked}</div>"
        body += "</div>"
        st.markdown(body,unsafe_allow_html=True)

        if eid:
            with st.expander("Connected context",expanded=False):
                _render_inline_trade_story_context(eid,key_prefix=f"{key_prefix}_ctx_{card_i}")
        sources=r.get("Research Sources") or []
        if isinstance(sources,list) and sources:
            good=[str(x) for x in sources if str(x).startswith(("http://","https://"))]
            if good:
                st.link_button("Primary source ↗",good[0],use_container_width=True)
                if len(good)>1:
                    st.caption("Additional sources are available inside Connected context.")


def _canonical_trade_disruptions():
    """Explicit disruption-tagged canonical events only."""
    stories=_canonical_trade_story_frame()
    if stories.empty:
        return stories
    return stories[stories["Is Disruption"].fillna(False)].copy() if "Is Disruption" in stories.columns else pd.DataFrame()


def _canonical_trade_active_monitoring():
    """Live monitors derived from canonical events so the view updates with ingestion."""
    stories=_canonical_trade_story_frame()
    if stories.empty:
        return stories
    status=stories.get("Status",pd.Series(index=stories.index,dtype=str)).fillna("").astype(str)
    horizon=stories.get("Horizon",pd.Series(False,index=stories.index)).fillna(False)
    disrupt=stories.get("Is Disruption",pd.Series(False,index=stories.index)).fillna(False)
    phase=status.str.contains(r"monitor|ongoing|develop|watch|active|pending",case=False,regex=True,na=False)
    out=stories[phase | horizon | disrupt].copy()
    return out


def render_trade_developments_home():
    """Editorial hierarchy for Trade Home, driven by canonical data."""
    stories=_canonical_trade_story_frame()
    if stories.empty:
        st.info("No canonical trade developments are currently available.")
        return

    story_rows=stories[stories.get("Is Story",False).fillna(False)].copy() if "Is Story" in stories.columns else stories.copy()
    # A home-page lead should be current. Keep future/horizon records in the
    # Important dates rail and sort observed developments newest-first.
    if "Horizon" in story_rows.columns:
        story_rows=story_rows[~story_rows["Horizon"].fillna(False)].copy()
    if "Start Date" in story_rows.columns:
        story_rows["_lead_dt"]=pd.to_datetime(story_rows["Start Date"],errors="coerce",utc=True).dt.tz_convert(None)
        today=pd.Timestamp.utcnow().tz_localize(None).normalize()
        story_rows=story_rows[story_rows["_lead_dt"].isna() | (story_rows["_lead_dt"]<=today)]
        story_rows=story_rows.sort_values("_lead_dt",ascending=False,na_position="last")
    leads=story_rows.head(5)

    st.markdown("### Current trade developments")
    _render_trade_story_cards(leads,5,key_prefix='overview_lead')

    companies=story_rows[
        story_rows.get("Linked Companies",pd.Series(index=story_rows.index,dtype=str)).fillna("").astype(str).str.len().gt(0)
    ].copy()
    if not companies.empty:
        st.markdown("### Company & network stories")
        _render_trade_story_cards(companies[~companies["Event ID"].isin(set(leads.get("Event ID",[])))],6,show_why=False,key_prefix='overview_company')

    c1,c2=st.columns(2,gap="large")
    with c1:
        st.markdown("### Disruptions")
        disruptions=_canonical_trade_disruptions()
        _render_trade_story_cards(disruptions,4,key_prefix='overview_disruption')
    with c2:
        st.markdown("### Trade Horizon")
        horizon=trade_horizon_events(stories)
        _render_trade_story_cards(horizon,4,show_why=False,key_prefix='overview_horizon')

    market_pat=r"performance|throughput|market|volume|capacity|reliability|forecast|fleet"
    mask=story_rows.get("Story Category",pd.Series(index=story_rows.index,dtype=str)).fillna("").astype(str).str.contains(
        market_pat,case=False,regex=True,na=False
    )
    observations=story_rows[mask].copy()
    if not observations.empty:
        st.markdown("### Market & throughput observations")
        _render_trade_story_cards(observations,5,show_why=False,key_prefix='overview_market')



if page=="Overview":
    header("Trade System","End-to-end logistics intelligence across companies, road, rail, maritime, aviation, facilities, corridors, markets, infrastructure and disruption.")

    latest_col, dates_col = st.columns([2.7,1.0], gap="large")
    with latest_col:
        st.markdown("### Priority developments")
        st.caption("Developments with a demonstrated effect on movement, capacity, cost, infrastructure or commercial exposure — ranked by consequence, then recency.")
        render_latest_reporting_trade(5)
    with dates_col:
        st.markdown("### Important dates")
        st.caption("Upcoming Trade Horizon dates are kept separate from live reporting.")
        render_trade_horizon_sidebar_compact(4)

    st.markdown("---")

    # Canonical developments lead the Trade app. Open-source discovery is supporting evidence,
    # not the primary operating picture.
    render_trade_developments_home()

    st.markdown("---")
    op_left,op_right=st.columns([1.2,1.0],gap="large")
    with op_left:
        _render_operational_brief()
    with op_right:
        st.markdown("### Markets now")
        render_live_market_dashboard(compact=True)

    st.markdown("---")
    q=st.text_input("Search the trade system",placeholder="Company, trucking fleet, rail network, warehouse, port, vessel, air cargo, corridor, contract, project...",key="trade_home_search_top")
    if q.strip():
        hits=ranked_search(q.strip(),limit=25)
        if not hits.empty:
            for _,h in hits.head(10).iterrows(): readable_search_card(h)
        # Always search the live canonical database as well. This is what makes
        # newly loaded incidents such as the Singapore collision discoverable
        # immediately by title, vessel name, IMO, location or linked object.
        live_hits=_render_connected_model_search(q.strip())
        if hits.empty and live_hits==0:
            st.info("No matching records.")

    st.markdown("---")
    left,right=st.columns([1.55,1.0],gap="large")
    with left:
        _render_trade_pulse()
    with right:
        _trade_exposure_snapshot()

    st.markdown("---")
    left,right=st.columns([1.45,1.0],gap="large")
    with left:
        _render_recent_additions()
    with right:
        _render_quick_access()
        st.markdown("---")
        render_security_business_rail(4)

    st.markdown("---")
    _render_business_infrastructure()

    with st.expander("Open-source discovery feed",expanded=False):
        render_overview_news()

    with st.expander("Recent operational events — full context",expanded=False):
        events=TABLES.get(("Events & Hazards","Events"),pd.DataFrame()).copy()
        if not events.empty:
            dc=_first_existing_col(events,["Date","Start Date","Event Date"])
            if dc:
                events['_dt']=pd.to_datetime(events[dc],errors='coerce')
                events=events.sort_values('_dt',ascending=False,na_position='last')
            render_event_cards(events,10)
        else:
            st.info("No recent operational events.")


elif page in {"Forward Calendar","Trade Horizon"}:
    render_trade_horizon_workspace()


elif page=="Search":
    header("Search P&C","One query across companies, trucking, rail, aviation, maritime, facilities, corridors, contracts, transactions, news, events and systems.")
    q=st.text_input("Query",placeholder="Try: Girteka Poland, Etihad Rail freight, CMA CGM service, AD Ports Black Sea, Rotterdam strike")
    if q and PC_USER_CONTEXT:
        if st.button("Save query to my workspace",key="save_trade_query"):
            ok,msg=save_workspace_query(PC_USER_CONTEXT,"TRADE",q[:100],q,"search")
            (st.success if ok else st.warning)(msg)
    if q:
        em=entity_search_matches(q,20)
        if not em.empty:
            st.markdown("### Best entity matches")
            cols=st.columns(3)
            for n,(_,r) in enumerate(em.head(9).iterrows()):
                with cols[n%3]:
                    st.markdown(f"<div class='pc-card'><div class='pc-label'>{r['kind']}</div><div class='pc-big'>{r['name']}</div></div>",unsafe_allow_html=True)
                    if st.button("Open",key=f"topopen_{r['id']}_{n}"):
                        eid=str(r["id"])
                        kind=str(r["kind"])
                        route_page,route_key,route_id=object_route(kind,eid,str(r["name"]))
                        if route_page:
                            request_nav(route_page,route_key,route_id,str(r["name"]))
                        else:
                            request_nav("Companies","company_pick_id",eid,str(r["name"]))
                        st.rerun()

        hits=ranked_search(q,limit=100)
        if not hits.empty:
            groups=[
                ("Commercial / contracts",["Contracts","Infra Deals","Transactions V125","Sales & Delivery Routes","Vessel Transactions"]),
                ("Assets",["Port Terminals","Ports","Shipyards","Yard Facilities","Sample Vessels","Platform Classes","Vessel Status History","Vessels","Assets"]),
                ("Cruise & service craft",["Cruise Lines","Cruise Ships","Cruise Destinations","Cruise Routes","Service Craft"]),
                ("Trade policy & compliance",["Trade Agreements","Tariff Coverage","HS Product Tests","Rules of Origin","Customs & Procurement","Trade Remedies & Restrictions","Sanctions Designations","Compliance Regimes","Compliance Designations","Compliance Exposure"]),
                ("News & events",["Events","Strategic Events","Announcements","News Registry","Impact Chains"]),
                ("Systems & relationships",["Systems","System Entities","System Links","Relationships","Port Ownership"]),
            ]
            for title,sheets in groups:
                sub=hits[hits["sheet"].isin(sheets)].head(20)
                if sub.empty: continue
                st.markdown(f"### {title}")
                for _,h in sub.iterrows():
                    readable_search_card(h)

        st.markdown("### Connected model")
        live_hits=_render_connected_model_search(q)
        if em.empty and hits.empty and live_hits==0:
            st.warning("No matching records found.")

elif page=="Regional Maps":
    header(
        "Regional Maps",
        "Regional business, infrastructure, corridor and security exposure — with trade and commercial activity as the primary lens."
    )
    render_trade_regional_maps()

elif page=="Alerts & Disruptions":
    render_trade_alerts_workspace()

elif page=="Maritime":
    header("Maritime","Vessels, incidents, disruptions, piracy, port exposure and navigation risk in one maritime workspace.")
    tabs=st.tabs(["Overview","Incidents","Disruptions","Vessels","Ports","Ferries","Cruise","Navigation & Compliance"])
    with tabs[0]:
        v=TABLES.get(("Maritime","Vessels"),pd.DataFrame()).copy()
        if v.empty:
            v=_canonical_vessel_fallback()
        p=TABLES.get(("Maritime","Ports"),pd.DataFrame()).copy()
        ev=TABLES.get(("Events & Hazards","Events"),pd.DataFrame()).copy()
        m1,m2,m3,m4=st.columns(4)
        m1.metric("Vessels",len(v))
        m2.metric("Ports",len(p))
        if not ev.empty:
            mev=_contains_any(ev,["maritime","port","vessel","piracy","shipping"],["Mode","Event Family","Event Type","Title","Description"])
        else:
            mev=pd.DataFrame()
        m3.metric("Linked events",len(mev))
        m4.metric("Critical / high",int(mev.get("Severity",pd.Series(dtype=str)).isin(["Critical","Severe","High"]).sum()) if not mev.empty else 0)
        st.caption("Use the tabs for incidents, disruptions, fleets, ports, ferries, cruise and navigation/compliance.")
    with tabs[1]:
        inc=official_maritime_incidents()
        st.caption("Official and vessel-linked maritime incidents.")
        render_official_security_records(inc,"maritime_unified_incidents")
    with tabs[2]:
        render_marsec_workspace()
    with tabs[3]:
        v=TABLES.get(("Maritime","Vessels"),pd.DataFrame()).copy()
        if v.empty:
            v=_canonical_vessel_fallback()
        if v.empty:
            st.info("No canonical vessel records are available.")
        else:
            display_df(v[[c for c in ["Vessel Name","IMO","MMSI","Vessel Type","Subtype / Class","Flag","Status","Primary Service","Owner Company ID","Operator Company ID"] if c in v.columns]],420)
    with tabs[4]:
        p=TABLES.get(("Maritime","Ports"),pd.DataFrame()).copy()
        display_df(p[[c for c in ["Port / Facility","Country","Operator","Facility Type","Key Role","Coverage Note"] if c in p.columns]],420)
    with tabs[5]:
        systems=TABLES.get(("Maritime","Ferry Systems"),pd.DataFrame()).copy()
        routes=TABLES.get(("Maritime","Ferry Routes"),pd.DataFrame()).copy()
        c1,c2=st.columns(2)
        with c1:
            st.markdown("### Ferry systems")
            display_df(systems,220)
        with c2:
            st.markdown("### Ferry routes")
            display_df(routes,220)
    with tabs[6]:
        cruise=TABLES.get(("Maritime","Great Lakes Cruise"),pd.DataFrame()).copy()
        research=TABLES.get(("Maritime","Fleet Research Universe"),pd.DataFrame()).copy()
        st.markdown("### Cruise / passenger maritime")
        if not cruise.empty:
            display_df(cruise,220)
        else:
            cview=_contains_any(research,["cruise"],research.columns.tolist()) if not research.empty else pd.DataFrame()
            display_df(cview,220)
    with tabs[7]:
        ev=TABLES.get(("Events & Hazards","Events"),pd.DataFrame()).copy()
        if not ev.empty:
            ev=_contains_any(ev,["GPS","GNSS","AIS","sanction","seizure","interdiction","piracy","navigation"],["Event Family","Event Type","Title","Description","Trade / Commercial Impact"])
        render_event_cards(ev,50)

    render_connected_domain_context(
        "Maritime",
        modes=("maritime","ferry"),
        keywords=("maritime","shipping","port","terminal","ferry","cruise")
    )

elif page=="Maritime Disruptions":
    header("Maritime Disruptions","Operational maritime casualties, groundings, SAR, pollution, attacks and official-source MARSEC reporting that can affect trade flows, vessels, ports and corridors.")
    render_marsec_workspace()

elif page=="Aviation":
    header("Aviation","Aircraft, carrier deployment and aviation-linked operational/security data from the shared model.")
    aircraft=TABLES.get(("Aviation","Aircraft"),pd.DataFrame()).copy()
    registry=TABLES.get(("Aviation","Aircraft Registry"),pd.DataFrame()).copy()
    rel=TABLES.get(("Aviation","Aircraft Relationships"),pd.DataFrame()).copy()
    if aircraft.empty:
        st.info("No aviation records loaded.")
    else:
        q=st.text_input("Filter aviation",placeholder="CMA CGM Air Cargo, Cargolux, registration, aircraft type...")
        view=aircraft.copy()
        if q:
            mask=pd.Series(False,index=view.index)
            for c in view.columns:
                mask=mask | view[c].astype(str).str.contains(q,case=False,na=False)
            view=view[mask]
        tabs=st.tabs(["Aircraft","Disruptions & Incidents","Relationships"])
        with tabs[0]: display_df(view,300)
        with tabs[1]:
            ad=TABLES.get(("Aviation","Aviation Disruptions"),pd.DataFrame()).copy()
            hev=TABLES.get(("Events & Hazards","Events"),pd.DataFrame()).copy()
            if not hev.empty: hev=_contains_any(hev,["aviation","airport","air cargo","air traffic","aircraft"],["Mode","Event Family","Event Type","Title","Description"])
            if not ad.empty: display_df(ad,260)
            render_event_cards(hev,35)
        with tabs[2]:
            if not rel.empty: display_df(rel,300)

    render_connected_domain_context(
        "Aviation",
        modes=("aviation",),
        keywords=("aviation","airport","air cargo","aircraft")
    )

elif page=="Rail":
    header("Rail","Freight and passenger operators, national networks, terminals, intermodal nodes, rolling stock, projects and disruption.")

    ent_names=_entity_name_map()
    live_ops=_live_frame("pc_rail_operator_details","*",10000)
    if not live_ops.empty:
        live_ops["Company"]=live_ops.get("entity_id",pd.Series(index=live_ops.index,dtype=str)).astype(str).map(ent_names)
    live_networks=_live_frame("pc_rail_networks","*",15000)
    live_nodes=_live_frame("pc_rail_nodes","*",25000)
    live_links=_live_frame("pc_rail_links","*",30000)
    live_rolling=_live_frame("pc_rolling_stock_details","*",20000)
    live_assets=_live_frame("pc_assets","*",30000)

    # Legacy workbook data remains useful during migration, but live canonical rows lead.
    old_ops=TABLES.get(("Rail","Rail Operators"),pd.DataFrame()).copy()
    old_networks=TABLES.get(("Rail","Rail Networks"),pd.DataFrame()).copy()
    old_nodes=TABLES.get(("Rail","Rail Nodes"),pd.DataFrame()).copy()
    news=TABLES.get(("Rail","Rail News"),pd.DataFrame()).copy()

    m1,m2,m3,m4=st.columns(4)
    m1.metric("Operators",len(live_ops) if not live_ops.empty else len(old_ops))
    m2.metric("Networks",len(live_networks) if not live_networks.empty else len(old_networks))
    m3.metric("Rail nodes",len(live_nodes) if not live_nodes.empty else len(old_nodes))
    m4.metric("Rolling-stock records",len(live_rolling))

    q=st.text_input("Search rail network",placeholder="Etihad Rail, Hafeet Rail, freight terminal, passenger station, locomotive, intermodal...")
    if q:
        live_ops=_filter_frame_any(live_ops,q); live_networks=_filter_frame_any(live_networks,q)
        live_nodes=_filter_frame_any(live_nodes,q); live_links=_filter_frame_any(live_links,q)
        live_rolling=_filter_frame_any(live_rolling,q); old_ops=_filter_frame_any(old_ops,q)
        old_networks=_filter_frame_any(old_networks,q); old_nodes=_filter_frame_any(old_nodes,q); news=_filter_frame_any(news,q)

    tabs=st.tabs(["Operators","Networks","Nodes & Terminals","Links & Corridors","Rolling Stock","Projects & Contracts","Events & News"])
    with tabs[0]:
        if not live_ops.empty:
            display_df(live_ops,420)
            if "Company" in live_ops.columns:
                opts=live_ops[live_ops["Company"].fillna("").astype(str).ne("")]
                if not opts.empty:
                    i=st.selectbox("Open rail company",range(len(opts)),format_func=lambda n:str(opts.iloc[n].get("Company","")),key="rail_live_company_pick")
                    linked_company_button(opts.iloc[i].get("entity_id",""),f"rail_live_company_{i}")
        else:
            clean_network_table(old_ops,["Operator","Operator Type","Jurisdiction","Role","Network Scale","Gauge","Electrification / Signalling","Status","Notes"],280)
    with tabs[1]:
        display_df(live_networks,460) if not live_networks.empty else clean_network_table(old_networks,["Network / Corridor","Countries / Jurisdictions","Start Node","End Node","Length / Scale","Gauge","Status","Primary Cargo / Role","Notes"],320)
    with tabs[2]:
        display_df(live_nodes,460) if not live_nodes.empty else clean_network_table(old_nodes,["Node","Country","Node Type","Status","Notes"],320)
        if not live_assets.empty:
            rail_fac=_filter_frame_any(live_assets,"rail")
            if not rail_fac.empty:
                st.markdown("#### Rail-linked physical assets")
                display_df(rail_fac.head(500),360)
    with tabs[3]:
        display_df(live_links,460)
    with tabs[4]:
        display_df(live_rolling,460)
    with tabs[5]:
        render_connected_domain_context("Rail",modes=("rail",),keywords=("rail","railway","intermodal","locomotive","freight terminal","passenger station"))
    with tabs[6]:
        rail_events=_live_frame("pc_events","*",15000,"start_date")
        if not rail_events.empty: rail_events=_filter_frame_any(rail_events,"rail")
        display_df(rail_events.head(500),420)
        if not news.empty:
            st.markdown("#### Rail news")
            clean_network_table(news,["Date","Event Type","Headline","Summary"],260)

elif page=="Trucking":
    header("Trucking","Road freight operators, fleet scale, corridors, depots, warehouses, cross-border operations and intermodal services.")

    ent_names=_entity_name_map()
    live_trucking=_live_frame("pc_trucking_company_details","*",10000)
    if not live_trucking.empty:
        live_trucking["Company"]=live_trucking.get("entity_id",pd.Series(index=live_trucking.index,dtype=str)).astype(str).map(ent_names)
    road_corridors=_live_frame("pc_road_corridors","*",20000)
    road_vehicle=_live_frame("pc_road_vehicle_details","*",25000)
    footprint=_live_frame("pc_company_operating_footprint","*",25000)
    assets_live=_live_frame("pc_assets","*",30000)
    service_ops=_live_frame("pc_transport_service_operators","*",30000)
    services_live=_live_frame("pc_transport_services","*",25000)
    if not services_live.empty and "mode" in services_live.columns:
        services_live=services_live[services_live["mode"].fillna("").astype(str).str.contains("road|truck|intermodal",case=False,na=False,regex=True)].copy()

    old_ops=TABLES.get(("Road & Trucking","Trucking Companies"),pd.DataFrame()).copy()
    old_assets=TABLES.get(("Road & Trucking","Trucking Assets"),pd.DataFrame()).copy()
    old_rels=TABLES.get(("Road & Trucking","Trucking Relationships"),pd.DataFrame()).copy()

    trucks=pd.to_numeric(live_trucking.get("fleet_size_power_units",pd.Series(dtype=float)),errors="coerce").fillna(0).sum() if not live_trucking.empty else 0
    trailers=pd.to_numeric(live_trucking.get("fleet_size_trailers",pd.Series(dtype=float)),errors="coerce").fillna(0).sum() if not live_trucking.empty else 0
    m1,m2,m3,m4=st.columns(4)
    m1.metric("Road operators",len(live_trucking) if not live_trucking.empty else len(old_ops))
    m2.metric("Power units",f"{int(trucks):,}" if trucks else "—")
    m3.metric("Trailers",f"{int(trailers):,}" if trailers else "—")
    m4.metric("Road corridors",len(road_corridors))

    q=st.text_input("Search road logistics",placeholder="Girteka, TFI, Canpar, Qube, reefer, FTL, Poland, cross-border, warehouse...")
    if q:
        live_trucking=_filter_frame_any(live_trucking,q); road_corridors=_filter_frame_any(road_corridors,q)
        road_vehicle=_filter_frame_any(road_vehicle,q); footprint=_filter_frame_any(footprint,q)
        assets_live=_filter_frame_any(assets_live,q); services_live=_filter_frame_any(services_live,q)
        old_ops=_filter_frame_any(old_ops,q); old_assets=_filter_frame_any(old_assets,q); old_rels=_filter_frame_any(old_rels,q)

    tabs=st.tabs(["Operators","Fleet","Services","Road Corridors","Facilities & Footprint","Events & Risk","Relationships"])
    with tabs[0]:
        if not live_trucking.empty:
            display_df(live_trucking,460)
            opts=live_trucking[live_trucking.get("Company",pd.Series(index=live_trucking.index,dtype=str)).fillna("").astype(str).ne("")]
            if not opts.empty:
                i=st.selectbox("Open trucking company",range(len(opts)),format_func=lambda n:str(opts.iloc[n].get("Company","")),key="truck_live_company_pick")
                linked_company_button(opts.iloc[i].get("entity_id",""),f"truck_live_company_{i}")
        else:
            clean_network_table(old_ops,["Company","Road Segment","Primary Geography","Fleet / Network Notes","Public / Private","Status"],300)
    with tabs[1]:
        display_df(road_vehicle,460)
        if road_vehicle.empty and not live_trucking.empty:
            st.caption("Aggregate fleet figures are held at company level when individual vehicles are not identified.")
            display_df(live_trucking,320)
    with tabs[2]:
        display_df(services_live,460)
    with tabs[3]:
        display_df(road_corridors,460)
    with tabs[4]:
        if not footprint.empty:
            display_df(footprint,420)
        # Road companies often operate depots/warehouses rather than ports.
        if not assets_live.empty:
            road_fac=pd.concat([
                _filter_frame_any(assets_live,"warehouse"),
                _filter_frame_any(assets_live,"depot"),
                _filter_frame_any(assets_live,"logistics"),
                _filter_frame_any(assets_live,"crossdock")
            ],ignore_index=True,sort=False)
            if not road_fac.empty:
                _dedupe_col="asset_id" if "asset_id" in road_fac.columns else ("name" if "name" in road_fac.columns else None)
                if _dedupe_col: road_fac=road_fac.drop_duplicates(subset=[_dedupe_col],keep="first")
            if not road_fac.empty:
                st.markdown("#### Depots / warehouses / logistics facilities")
                display_df(road_fac,420)
        if not old_assets.empty:
            with st.expander("Legacy road/logistics asset records",expanded=False): clean_network_table(old_assets,["Asset / Network","Asset Type","Country / Region","Location","Intermodal Links","Status","Notes"],300)
    with tabs[5]:
        events=_live_frame("pc_events","*",15000,"start_date")
        if not events.empty:
            events=_filter_frame_any(events,"road")
            if events.empty: events=_filter_frame_any(_live_frame("pc_events","*",15000,"start_date"),"truck")
        display_df(events.head(500),430)
    with tabs[6]:
        clean_network_table(old_rels,["Relationship","Effective From","Effective To","Status","Confidence","Notes"],240)

    render_connected_domain_context(
        "Trucking & Road Freight",
        modes=("road","intermodal"),
        keywords=("trucking","road freight","truck","cross-dock","warehouse","drayage","reefer","FTL")
    )

elif page=="Ferries":
    header("Ferries","Scheduled passenger, vehicle and freight ferry systems, their routes, terminals, vessels, performance and disruption.")
    systems=TABLES.get(("Maritime","Ferry Systems"),pd.DataFrame()).copy()
    routes=TABLES.get(("Maritime","Ferry Routes"),pd.DataFrame()).copy()
    terminals=TABLES.get(("Maritime","Ferry Terminals"),pd.DataFrame()).copy()
    status=TABLES.get(("Maritime","Ferry Fleet Status"),pd.DataFrame()).copy()
    perf=TABLES.get(("Maritime","Ferry Performance"),pd.DataFrame()).copy()
    obs=TABLES.get(("Maritime","Ferry Service Observations"),pd.DataFrame()).copy()
    staging=TABLES.get(("Maritime","Ferry Vessel Staging"),pd.DataFrame()).copy()

    # Build human-readable system lookup while retaining internal IDs only for joins.
    sys_name={}
    if not systems.empty and {"System ID","System Name"}.issubset(systems.columns):
        sys_name=dict(zip(systems["System ID"].astype(str),systems["System Name"].astype(str)))

    m1,m2,m3,m4=st.columns(4)
    m1.metric("Ferry systems",len(systems))
    m2.metric("Routes",len(routes))
    m3.metric("Terminals",len(terminals))
    m4.metric("Fleet / service records",len(status)+len(staging))

    q=st.text_input("Search ferry network",placeholder="BC Ferries, Washington State, Alaska, Auckland, Manila, freight, terminal...")
    if q:
        systems=_contains_any(systems,[q]); routes=_contains_any(routes,[q])
        terminals=_contains_any(terminals,[q]); status=_contains_any(status,[q])
        perf=_contains_any(perf,[q]); obs=_contains_any(obs,[q]); staging=_contains_any(staging,[q])

    tabs=st.tabs(["Systems & Routes","All Routes","Terminals","Fleet","Performance & Disruption"])

    with tabs[0]:
        if systems.empty:
            st.info("No matching ferry systems.")
        else:
            systems=systems.reset_index(drop=True)
            pick=st.selectbox(
                "Ferry system",
                range(len(systems)),
                format_func=lambda i:str(systems.iloc[i].get("System Name","")),
                key="ferry_system_pick"
            )
            rr=systems.iloc[pick]
            sid=str(rr.get("System ID","")).strip()
            selected_ferry_system_name=str(rr.get("System Name","") or "")
            st.session_state["selected_ferry_system_id"]=sid
            st.session_state["selected_ferry_system_name"]=selected_ferry_system_name

            st.markdown(f"## {selected_ferry_system_name}")
            c1,c2,c3=st.columns(3)
            c1.metric("Jurisdiction",str(rr.get("Country / Jurisdiction","") or "—"))
            c2.metric("Service model",str(rr.get("Service Model","") or "—"))
            c3.metric("Network type",str(rr.get("Network Type","") or "—"))

            linked_company_button(rr.get("Operator Company ID",""),f"ferry_company_{pick}","Open operator company")

            system_routes=routes[routes["System ID"].astype(str).eq(sid)].copy() if sid and not routes.empty and "System ID" in routes.columns else pd.DataFrame()
            system_terms=terminals[terminals["System ID"].astype(str).eq(sid)].copy() if sid and not terminals.empty and "System ID" in terminals.columns else pd.DataFrame()
            system_fleet=staging[staging["System ID"].astype(str).eq(sid)].copy() if sid and not staging.empty and "System ID" in staging.columns else pd.DataFrame()

            a,b,c=st.columns(3)
            a.metric("Routes",len(system_routes))
            b.metric("Terminals",len(system_terms))
            c.metric("Fleet records",len(system_fleet))

            st.markdown("### Routes")
            if system_routes.empty:
                st.caption("No routes are currently mapped to this ferry system.")
            else:
                system_routes=system_routes.reset_index(drop=True)
                for n,(_,route) in enumerate(system_routes.iterrows()):
                    route_name=str(route.get("Route Name","") or f"{route.get('Origin Terminal','')} – {route.get('Destination Terminal','')}")
                    origin=str(route.get("Origin Terminal","") or "—")
                    destination=str(route.get("Destination Terminal","") or "—")
                    status_text=str(route.get("Route Status","") or "—")
                    service=str(route.get("Service Type","") or "—")
                    cadence=str(route.get("Frequency / Cadence","") or "—")
                    duration=str(route.get("Typical Duration","") or "—")
                    season=str(route.get("Seasonality","") or "—")
                    cross=str(route.get("Cross-Border","") or "—")
                    notes=str(route.get("Intermediate Stops / Corridor Notes","") or "").strip()

                    notes_html = (
                        f"<div style='margin-top:8px;'>{notes}</div>"
                        if notes and notes.lower()!="nan" else ""
                    )
                    route_html = (
                        "<div class='pc-card'>"
                        f"<div class='pc-label'>{status_text} · {service}</div>"
                        f"<div class='pc-big'>{route_name}</div>"
                        f"<div style='margin-top:10px;'><b>{origin}</b> → <b>{destination}</b></div>"
                        f"<div class='pc-search-details' style='margin-top:8px;'>{cadence} · {duration} · {season} · Cross-border: {cross}</div>"
                        f"{notes_html}"
                        "</div>"
                    )
                    st.markdown(route_html, unsafe_allow_html=True)

            with st.expander("System record"):
                clean_network_table(pd.DataFrame([rr]),[
                    "System Name","Parent / Public Owner","Region","Country / Jurisdiction",
                    "Service Model","Passenger Service","Vehicle / Freight Service",
                    "Network Type","Fleet Status Tracking","Alerts / Performance Data",
                    "Research Status","Source URL"
                ],180)

    with tabs[1]:
        st.markdown("### Ferry route network")
        route_view=routes.copy()
        if route_view.empty:
            st.info("No ferry routes available.")
        else:
            # Add system names for readable filtering/display; never expose System ID.
            if "System ID" in route_view.columns:
                route_view["Ferry System"]=route_view["System ID"].astype(str).map(sys_name).fillna("")

            system_options=["All"]
            if "Ferry System" in route_view.columns:
                system_options += sorted([x for x in route_view["Ferry System"].dropna().astype(str).unique() if x])
            selected_system=st.selectbox("Filter by ferry system",system_options,key="ferry_route_system_filter")
            if selected_system!="All":
                route_view=route_view[route_view["Ferry System"].eq(selected_system)].copy()

            r1,r2=st.columns(2)
            country_opts=["All"]
            if "Country 1" in route_view.columns:
                country_opts += sorted([x for x in route_view["Country 1"].dropna().astype(str).unique() if x])
            country_pick=r1.selectbox("Country",country_opts,key="ferry_route_country_filter")
            cross_pick=r2.selectbox("Cross-border",["All","Yes","No"],key="ferry_route_cross_filter")
            if country_pick!="All":
                route_view=route_view[
                    route_view.get("Country 1",pd.Series(index=route_view.index,dtype=str)).astype(str).eq(country_pick)
                    | route_view.get("Country 2",pd.Series(index=route_view.index,dtype=str)).astype(str).eq(country_pick)
                ].copy()
            if cross_pick!="All" and "Cross-Border" in route_view.columns:
                route_view=route_view[route_view["Cross-Border"].astype(str).str.casefold().eq(cross_pick.casefold())].copy()

            st.caption(f"{len(route_view)} route records")
            clean_network_table(route_view,[
                "Ferry System","Route Name","Origin Terminal","Destination Terminal",
                "Country 1","Country 2","Cross-Border","Service Type","Vehicle / Freight",
                "Typical Duration","Frequency / Cadence","Seasonality",
                "Reservation / Booking","Route Status","Intermediate Stops / Corridor Notes"
            ],420)

            if not route_view.empty:
                detail=route_view.reset_index(drop=True)
                rp=st.selectbox(
                    "Inspect route",
                    range(len(detail)),
                    format_func=lambda i:f"{detail.iloc[i].get('Route Name','')} — {detail.iloc[i].get('Ferry System','')}",
                    key="ferry_route_pick"
                )
                r=detail.iloc[rp]
                st.markdown(f"### {r.get('Route Name','')}")
                st.markdown(f"**{r.get('Origin Terminal','')} → {r.get('Destination Terminal','')}**")
                c1,c2,c3,c4=st.columns(4)
                c1.metric("Status",str(r.get("Route Status","") or "—"))
                c2.metric("Frequency",str(r.get("Frequency / Cadence","") or "—"))
                c3.metric("Duration",str(r.get("Typical Duration","") or "—"))
                c4.metric("Season",str(r.get("Seasonality","") or "—"))
                if str(r.get("Intermediate Stops / Corridor Notes","")).strip():
                    st.markdown("**Intermediate stops / corridor context**")
                    st.write(r.get("Intermediate Stops / Corridor Notes",""))

    with tabs[2]:
        term_view=terminals.copy()
        selected_sid=str(st.session_state.get("selected_ferry_system_id","") or "")
        selected_sname=str(st.session_state.get("selected_ferry_system_name","") or "")

        if not term_view.empty and "System ID" in term_view.columns:
            term_view["Ferry System"]=term_view["System ID"].astype(str).map(sys_name).fillna("")

        show_all_terms=st.checkbox(
            "Show terminals for all ferry systems",
            value=False,
            key="ferry_show_all_terminals"
        )
        if not show_all_terms and selected_sid and not term_view.empty and "System ID" in term_view.columns:
            term_view=term_view[term_view["System ID"].astype(str).eq(selected_sid)].copy()

        if selected_sname and not show_all_terms:
            st.markdown(f"### {selected_sname} terminals")

        clean_network_table(term_view,[
            "Ferry System","Terminal Name","Port / Harbour","City / Area","Country",
            "Owner / Authority","Vehicle Staging","Freight / DG Capability",
            "Customs / Border","Road / Rail / Bus Connection","Status","Notes"
        ],420)

    with tabs[3]:
        selected_sid=str(st.session_state.get("selected_ferry_system_id","") or "")
        selected_sname=str(st.session_state.get("selected_ferry_system_name","") or "")

        fleet_view=staging.copy()
        if not fleet_view.empty and "System ID" in fleet_view.columns:
            fleet_view["Ferry System"]=fleet_view["System ID"].astype(str).map(sys_name).fillna("")

        show_all_fleets=st.checkbox(
            "Show all ferry systems",
            value=False,
            key="ferry_show_all_fleets"
        )

        if not show_all_fleets and selected_sid and not fleet_view.empty and "System ID" in fleet_view.columns:
            fleet_view=fleet_view[fleet_view["System ID"].astype(str).eq(selected_sid)].copy()

        if selected_sname and not show_all_fleets:
            st.markdown(f"### {selected_sname} fleet")
        else:
            st.markdown("### Ferry fleet")

        if fleet_view.empty:
            st.info("No fleet records are currently mapped to this ferry system.")
        else:
            clean_network_table(fleet_view,[
                "Ferry System","Vessel Name","IMO","Vessel Type","Subtype / Class","Flag",
                "Passenger Capacity","Vehicle Capacity","Freight / Lane Metres","Year Built",
                "Propulsion / Fuel","Current Status","Primary Route","Data Status"
            ],420)

        # Filter current/recent status rows by vessel names in the selected fleet
        # because this sheet may not carry System ID directly.
        status_view=status.copy()
        if not show_all_fleets and not fleet_view.empty and not status_view.empty:
            vessel_col = "Vessel Name" if "Vessel Name" in fleet_view.columns else None
            if vessel_col and "Vessel Name" in status_view.columns:
                selected_vessels=set(
                    fleet_view[vessel_col].dropna().astype(str).str.strip()
                )
                status_view=status_view[
                    status_view["Vessel Name"].astype(str).str.strip().isin(selected_vessels)
                ].copy()

        if not status_view.empty:
            st.markdown("**Current / recent fleet status**")
            clean_network_table(
                status_view,
                ["As Of","Vessel Name","Fleet Status","Assignment / Location","Notes"],
                220
            )

    with tabs[4]:
        if not perf.empty:
            st.markdown("**Performance**")
            clean_network_table(perf,[
                "Period Type","Period Start","Period End","Scheduled Sailings","Completed Sailings",
                "Completion %","Cancelled Sailings","Weather","Mechanical / Vessel","Crew",
                "Terminal","Ridership","Vehicle Traffic","On-Time %","Capacity Utilization %","Notes"
            ],300)
        if not obs.empty:
            st.markdown("**Service observations / disruption**")
            clean_network_table(obs,[
                "Date","Vessel Name","Origin Terminal","Destination Terminal","Service Status",
                "Delay Minutes","Trips / Sailings Affected","Cause Family","Cause Detail",
                "Service Impact","Capacity / Wait Impact","Alternate Service / Response",
                "Severity","Confidence","Notes"
            ],340)

elif page=="Cruise":
    header("Cruise","Global cruise operators, ships, destinations, routes and Great Lakes deployment as a dedicated passenger-shipping network.")
    lines,ships,destinations,routes,gl=cruise_tables_with_fallbacks()

    m1,m2,m3,m4=st.columns(4)
    m1.metric("Cruise brands",len(lines))
    m2.metric("Cruise ships",len(ships))
    m3.metric("Destinations",len(destinations))
    m4.metric("Great Lakes records",len(gl))

    q=st.text_input("Search cruise coverage",placeholder="Great Lakes, Germany, Caribbean, Alaska, Viking, MSC, AIDA...")
    if q:
        lines=_contains_any(lines,[q]); ships=_contains_any(ships,[q])
        destinations=_contains_any(destinations,[q]); routes=_contains_any(routes,[q]); gl=_contains_any(gl,[q])

    tabs=st.tabs(["Cruise Lines","Ships","Destinations","Routes","Great Lakes"])
    with tabs[0]:
        clean_network_table(lines,["Cruise Line / Brand","Parent Group","Market Segment","Fleet Profile","Primary Operating Regions","Private / Controlled Destinations","Route Pattern","Status","Notes"],320)
        if not lines.empty:
            pick=st.selectbox("Inspect cruise line",range(len(lines)),format_func=lambda i:str(lines.iloc[i].get("Cruise Line / Brand","")),key="cruise_line_pick")
            rr=lines.iloc[pick]
            st.markdown(f"### {rr.get('Cruise Line / Brand','')}")
            st.caption(f"{rr.get('Market Segment','')} · {rr.get('Primary Operating Regions','')}")
            linked_company_button(rr.get("Company ID",""),f"cruise_company_{pick}","Open cruise company")
            parent=str(rr.get("Parent Group","")).strip()
            if parent.startswith("COMP_"):
                st.markdown("**Parent group**")
                st.write(label(parent))
                linked_company_button(parent,f"cruise_parent_{pick}","Open parent group")
    with tabs[1]:
        clean_network_table(ships,["Vessel Name","Ship Type / Class","Flag","Year Built","Passenger Capacity","Primary Deployment","Home Port / Turnaround","Route / Product Role","Status"],320)
    with tabs[2]:
        clean_network_table(destinations,["Destination","Country","Destination Type","Status","Region","Typical Line / Brand Use","Investment / Operating Note","Evidence Caveat"],300)
    with tabs[3]:
        clean_network_table(routes,["Route Family","Turnaround Ports","Representative Calls","Region","Typical Duration","Season","Strategic Role","Status"],280)
        if not routes.empty:
            ridx=st.selectbox("Map cruise route",range(len(routes)),format_func=lambda i:str(routes.iloc[i].get("Route Family","") or routes.iloc[i].get("Representative Calls","")),key="cruise_route_map_pick")
            rr=routes.iloc[ridx]
            pts=route_port_points(rr.get("Turnaround Ports",""),rr.get("Representative Calls",""))
            render_route_port_map(pts,"Representative cruise calls")
    with tabs[4]:
        st.caption("Great Lakes cruise is kept as a geographic deployment layer so operators, vessels, ports and locks can connect back into the wider Great Lakes system.")
        clean_network_table(gl,["Vessel Name","Operating Area","Representative Ports / Infrastructure","Vessel / Service Type","Season","Status","Notes"],320)
        if not gl.empty:
            all_pts=[]
            for _,gr in gl.iterrows():
                gp=route_port_points(gr.get("Representative Ports / Infrastructure",""))
                if not gp.empty: all_pts.append(gp)
            if all_pts:
                pts=pd.concat(all_pts,ignore_index=True).drop_duplicates(subset=["Port / Facility"],keep="first").reset_index(drop=True)
                pts["Sequence"]=range(1,len(pts)+1)
                render_route_port_map(pts,"Great Lakes cruise port network")


elif page=="Freight & Commodity Markets":
    render_freight_commodity_markets()

elif page=="Market Instruments":
    header("Market Instruments","Canonical commodity, equity, freight, FX and energy benchmarks connected to companies and physical assets.")
    render_market_instruments()

elif page=="Trade Flows & Supply":
    header("Trade Flows & Supply","Physical trade flows, production, inventories and supply-series context across commodities and corridors.")
    render_trade_flows_supply()

elif page=="Country & Macro":
    header("Country & Macro","Macro, logistics and chokepoint context for trade and investment exposure.")
    render_country_macro()

elif page=="Energy & Industry":
    header("Energy & Industry","Refineries, LNG, pipelines, mines, smelters, factories and logistics infrastructure as connected trade-system assets.")
    render_energy_industry()
    render_connected_domain_context(
        "Energy & Industry",
        modes=(),
        keywords=("energy","refinery","lng","pipeline","industrial","manufacturing","oil","gas")
    )

elif page=="Investments":
    header("Investments","Track capital deployment, acquisitions, equity investments and infrastructure commitments across companies, regions and years.")
    st.markdown("<div class='pc-section-note'>The register separates reported values, currencies and spend classes. Undisclosed transactions remain visible without inventing a value.</div>",unsafe_allow_html=True)
    render_investment_dashboard()

elif page=="Companies":
    header("Companies","Company-first view across assets, ports, shipyards, vessels, commercial relationships, programmes and events.")
    # honor direct navigation from Search
    companies=TABLES.get(("Core Entities","Companies"),pd.DataFrame())
    opts=companies[["Company ID","Company"]].drop_duplicates().sort_values("Company").to_dict("records") if not companies.empty else []

    # A cross-object jump should not be blocked by a stale search filter.
    requested_company=st.session_state.pop("company_pick_id",None)
    if requested_company:
        st.session_state["company_search_text"]=""

    q=st.text_input(
        "Find company",
        placeholder="APM Terminals, AD Ports, Inocea, Seaspan...",
        key="company_search_text"
    )
    if q:
        opts=[x for x in opts if q.lower() in x["Company"].lower()]

    if opts:
        requested_index=None
        if requested_company:
            for i,x in enumerate(opts):
                if x["Company ID"]==str(requested_company):
                    requested_index=i
                    break

        # Also honor prior selected canonical company if still available.
        prior_id=st.session_state.get("entity_pick","")
        prior_index=None
        if prior_id:
            for i,x in enumerate(opts):
                if x["Company ID"]==prior_id:
                    prior_index=i
                    break

        desired_index = requested_index if requested_index is not None else (prior_index if prior_index is not None else 0)

        # Critical: apply selection BEFORE keyed selectbox creation.
        if requested_index is not None:
            st.session_state["company_select_idx"]=int(desired_index)
        else:
            safe_index_state("company_select_idx",int(desired_index),len(opts))

        pick=st.selectbox(
            "Company",
            range(len(opts)),
            format_func=lambda i:opts[i]["Company"],
            key="company_select_idx"
        )
        ent=opts[pick]
        st.session_state["entity_pick"]=ent["Company ID"]
        render_company_profile(ent["Company ID"],ent["Company"])

elif page=="Network Map":
    header("Trade Network Map","Commercial geography across canonical and reference ports. Intelligence events remain on P&C Intelligence unless they affect a selected trade asset.")
    ref=global_port_reference_view()
    canonical=enrich_ports_from_reference(TABLES.get(("Maritime","Ports"),pd.DataFrame()))
    t1,t2=st.tabs(["Global Ports","Canonical P&C Ports"])
    with t1:
        st.caption(f"{len(ref):,} geocoded ports from the global reference layer." if not ref.empty else "Global port reference unavailable.")
        render_named_port_map(ref,height=610,radius=16000)
    with t2:
        geo=canonical.copy()
        if not geo.empty:
            geo=geo[pd.to_numeric(geo.get("Latitude"),errors="coerce").notna() & pd.to_numeric(geo.get("Longitude"),errors="coerce").notna()]
        st.caption(f"{len(geo):,} canonical ports currently resolve to coordinates.")
        render_named_port_map(geo,height=610,radius=22000)

elif page=="Services & Routes":
    render_transport_services_workspace()

elif page in ["Ports","Ports & Terminals"]:
    header("Ports","Port / terminal explorer with operators, facilities, geography and linked events.")
    ports=unified_ports_with_reference(TABLES.get(("Maritime","Ports"),pd.DataFrame()))
    terms=TABLES.get(("Maritime","Port Terminals"),pd.DataFrame())
    if ports.empty:
        st.info("Port data unavailable.")
    else:
        # Resolve incoming relationship navigation BEFORE creating keyed widgets.
        # Streamlit does not allow session_state for a widget key to be mutated
        # after that widget has been instantiated in the same run.
        requested_port=st.session_state.pop("port_pick_id",None)
        requested_terminal=st.session_state.pop("terminal_pick_id",None)

        if requested_terminal and not terms.empty and "Terminal ID" in terms.columns:
            tr=terms[terms["Terminal ID"].astype(str).eq(str(requested_terminal))]
            if not tr.empty and "Port ID" in tr.columns:
                requested_port=str(tr.iloc[0]["Port ID"])

        # Clear any previous text filter before the text_input exists so a
        # relationship link can land directly on the requested port/terminal.
        if requested_port or requested_terminal:
            st.session_state["port_search_text"]=""

        q=st.text_input("Find port",placeholder="Rotterdam, Shanghai, Odesa, Vancouver, Constanța...",key="port_search_text")
        p=ports.copy()

        if q:
            p=_contains_any(
                p,[q],
                [c for c in [
                    "Port / Facility","Country","City / Area","Operator",
                    "Owner","Facility Type","Port ID"
                ] if c in p.columns]
            )
        p=p.sort_values("Port / Facility").reset_index(drop=True)
        if p.empty:
            st.warning("No matching port.")
        else:
            default_port=0
            if requested_port and "Port ID" in p.columns:
                match_idx=p.index[p["Port ID"].astype(str).eq(str(requested_port))].tolist()
                if match_idx: default_port=int(match_idx[0])

            if requested_port:
                st.session_state["port_select_idx"]=int(default_port)
            else:
                safe_index_state("port_select_idx",int(default_port),len(p))

            pick=st.selectbox(
                "Port",
                range(len(p)),
                format_func=lambda i:f"{p.iloc[i].get('Port / Facility','')} — {p.iloc[i].get('Country','')}",
                key="port_select_idx"
            )
            row=p.iloc[pick]; raw_pid=str(row.get("Port ID","")); pid=_canonical_live_asset_id(raw_pid) if raw_pid and not raw_pid.startswith("REF_") else raw_pid; pname=str(row.get("Port / Facility",""))
            st.markdown(f"## {pname}")
            if raw_pid and pid and raw_pid != pid:
                st.caption(f"Resolved legacy alias `{raw_pid}` → canonical asset `{pid}`")
            if str(row.get("Canonical Source",""))=="pc_assets":
                st.caption(f"Canonical live asset · `{pid}`")
            elif str(pid).startswith("REF_"):
                st.caption("Reference-only port seed · canonical enrichment pending")
            c1,c2,c3=st.columns(3)
            pt_raw=terms[terms["Port ID"].astype(str).eq(pid)].copy() if not terms.empty and "Port ID" in terms.columns else pd.DataFrame()

            # Pull canonical terminal_of relationships live from Supabase.
            live_terms, live_term_status = live_db_terminals_for_port(row)
            if not live_terms.empty:
                pt_raw=pd.concat([pt_raw,live_terms],ignore_index=True,sort=False)
                if "Terminal ID" in pt_raw.columns:
                    pt_raw=pt_raw.drop_duplicates(subset=["Terminal ID"],keep="last")
            pt=filter_distinct_port_terminals(row,pt_raw)
            c1.metric("Terminals",len(pt))
            if live_term_status:
                if live_terms.empty:
                    st.caption(f"Terminal link status: {live_term_status}")
                else:
                    st.success(f"Terminal link status: {live_term_status}")
            c2.markdown(f"<div class='pc-card'><div class='pc-label'>Country</div><div class='pc-big'>{row.get('Country','')}</div></div>",unsafe_allow_html=True)
            c3.markdown(f"<div class='pc-card'><div class='pc-label'>Operator</div><div class='pc-big'>{row.get('Operator','') or 'Multiple / authority-led'}</div></div>",unsafe_allow_html=True)
            lat=pd.to_numeric(pd.Series([row.get("Latitude","")]),errors="coerce").iloc[0]
            lon=pd.to_numeric(pd.Series([row.get("Longitude","")]),errors="coerce").iloc[0]
            if pd.notna(lat) and pd.notna(lon):
                render_named_port_map(
                    pd.DataFrame([{
                        "Port / Facility":pname,
                        "Country":row.get("Country",""),
                        "Latitude":lat,
                        "Longitude":lon
                    }]),
                    height=300,
                    radius=50000
                )
            render_port_connected_dossier(row,pt)

elif page=="Watch Areas":
    header("Watch Areas","Live canonical monitoring, disruption watch, weather/labour observations and strategic events in one operational workspace.")

    canonical_monitor=_canonical_trade_active_monitoring()
    legacy_monitor=TABLES.get(("Intelligence","Monitoring"),pd.DataFrame()).copy()
    disruption=TABLES.get(("Intelligence","Disruption Watch"),pd.DataFrame()).copy()
    weather=TABLES.get(("Intelligence","Weather Labour Events"),pd.DataFrame()).copy()
    strategic=TABLES.get(("Intelligence","Strategic Events"),pd.DataFrame()).copy()
    corridors=TABLES.get(("Infrastructure","Corridors"),pd.DataFrame()).copy()

    m1,m2,m3,m4=st.columns(4)
    m1.metric("Live monitors",f"{len(canonical_monitor):,}")
    m2.metric("Canonical disruptions",f"{len(_canonical_trade_disruptions()):,}")
    m3.metric("Weather / labour",f"{len(weather):,}")
    m4.metric("Corridors",f"{len(corridors):,}")

    wt1,wt2,wt3,wt4=st.tabs(["Active monitoring","Disruption watch","Weather & labour","Strategic events"])
    with wt1:
        q=st.text_input("Search monitoring",placeholder="Hormuz, Black Sea, Red Sea, port strike, Suez, Panama...",key="watch_monitor_q")
        view=canonical_monitor.copy()
        if q.strip() and not view.empty:
            view=_contains_any(view,[q])
        if view.empty:
            st.caption("No live canonical monitoring records matched.")
            if not legacy_monitor.empty:
                st.markdown("#### Legacy monitoring reference")
                display_df(_contains_any(legacy_monitor,[q]) if q.strip() else legacy_monitor,180)
        else:
            cols=[c for c in ["Start Date","Status","Story Category","Title","Next Milestone","Disruption Domains","Linked Companies","Linked Assets","Linked Routes","Why It Matters"] if c in view.columns]
            display_df(view[cols] if cols else view,300)

    with wt2:
        q=st.text_input("Search disruption watch",placeholder="port, rail, aviation, weather, conflict...",key="watch_disruption_q")
        dev=_canonical_trade_disruptions()
        if q.strip() and not dev.empty:
            dev=_contains_any(dev,[q])
        _render_trade_story_cards(dev,20,key_prefix='watch_disruption')

        if not disruption.empty:
            with st.expander("Legacy disruption-watch reference",expanded=False):
                display_df(_contains_any(disruption,[q]) if q.strip() else disruption,200)

    with wt3:
        q=st.text_input("Search weather / labour",placeholder="storm, strike, typhoon, rail...",key="watch_weather_q")
        display_df(_contains_any(weather,[q]) if q.strip() and not weather.empty else weather,300)

    with wt4:
        q=st.text_input("Search strategic events",placeholder="sanctions, conflict, corridor, policy...",key="watch_strategic_q")
        live=_canonical_trade_story_frame()
        if not live.empty:
            mask=live.get("Story Category",pd.Series(index=live.index,dtype=str)).fillna("").astype(str).str.contains(
                r"sanction|regulatory|routing|corridor|security|policy|compliance",case=False,regex=True,na=False
            )
            lv=live[mask].copy()
            if q.strip(): lv=_contains_any(lv,[q])
            _render_trade_story_cards(lv,20,key_prefix='watch_strategic')
        if not strategic.empty:
            with st.expander("Legacy strategic-event reference",expanded=False):
                display_df(_contains_any(strategic,[q]) if q.strip() else strategic,200)


elif page=="Port Activity":
    header(
        "Global Port Activity",
        "Live daily port calls, imports and exports from IMF PortWatch. This operational layer is queried on demand and is not stored in the canonical XLSX model."
    )
    st.caption("Source: IMF PortWatch Daily Ports Data · public ArcGIS Feature Service · cached in-app for 30 minutes")
    live,error,latest_date=load_portwatch_latest()
    live_status="live"
    if not error and not live.empty:
        st.session_state["portwatch_last_good"]=(live.copy(),latest_date)
    elif error and "portwatch_last_good" in st.session_state:
        live,latest_date=st.session_state["portwatch_last_good"]
        live_status="stale"
        st.warning(f"PortWatch refresh failed; showing the last successful session snapshot. {error}")
    if error and live_status=="live":
        st.warning(f"PortWatch is temporarily unavailable. Canonical P&C port data remains available under Ports. {error}")
    elif live.empty:
        st.info("PortWatch returned no current observations.")
    else:
        status_label="LIVE API" if live_status=="live" else "LAST SUCCESSFUL SNAPSHOT"
        status_cls="live" if live_status=="live" else "stale"
        st.markdown(f"<span class='pc-data-status pc-data-status-{status_cls}'>{status_label}</span>",unsafe_allow_html=True)
        countries=sorted(x for x in live.get("country",pd.Series(dtype=str)).dropna().astype(str).unique() if x.strip())
        c1,c2=st.columns([1,2])
        with c1:
            selected_country=st.selectbox("Country",["All"]+countries,key="portwatch_country")
        scoped=live.copy()
        if selected_country!="All":
            scoped=scoped[scoped["country"].astype(str).eq(selected_country)]
        with c2:
            port_search=st.text_input("Filter ports",placeholder="Jebel Ali, Rotterdam, Singapore, Shanghai...",key="portwatch_search")
        if port_search:
            scoped=scoped[scoped["portname"].astype(str).str.contains(port_search,case=False,na=False)]

        total_calls=pd.to_numeric(scoped.get("portcalls",pd.Series(dtype=float)),errors="coerce").sum()
        total_imports=pd.to_numeric(scoped.get("import",pd.Series(dtype=float)),errors="coerce").sum()
        total_exports=pd.to_numeric(scoped.get("export",pd.Series(dtype=float)),errors="coerce").sum()
        m1,m2,m3,m4=st.columns(4)
        m1.metric("Latest observation",latest_date)
        m2.metric("Ports in view",f"{len(scoped):,}")
        m3.metric("Port calls",f"{int(total_calls):,}")
        m4.metric("Imports / exports",f"{int(total_imports):,} / {int(total_exports):,}")

        metric_choice=st.radio(
            "Rank by",
            ["Port calls","Container calls","Tanker calls","Imports","Exports"],
            horizontal=True,
            key="portwatch_metric"
        )
        metric_map={
            "Port calls":"portcalls",
            "Container calls":"portcalls_container",
            "Tanker calls":"portcalls_tanker",
            "Imports":"import",
            "Exports":"export",
        }
        metric_col=metric_map[metric_choice]
        ranking=scoped[["portname","country",metric_col]].copy() if metric_col in scoped.columns else pd.DataFrame()
        if not ranking.empty:
            ranking[metric_col]=pd.to_numeric(ranking[metric_col],errors="coerce").fillna(0)
            ranking=ranking.sort_values(metric_col,ascending=False).head(20)
            ranking["Port / Country"]=ranking["portname"].astype(str)+" — "+ranking["country"].astype(str)
            st.markdown(f"### Top ports by {metric_choice.lower()}")
            st.bar_chart(ranking.set_index("Port / Country")[metric_col],horizontal=True)

        show_cols=[
            "Date","portname","country","ISO3","portcalls","portcalls_container","portcalls_dry_bulk",
            "portcalls_general_cargo","portcalls_roro","portcalls_tanker","import","export"
        ]
        show=scoped[[c for c in show_cols if c in scoped.columns]].copy()
        show=show.rename(columns={
            "portname":"Port","country":"Country","ISO3":"ISO3","portcalls":"Port Calls",
            "portcalls_container":"Container Calls","portcalls_dry_bulk":"Dry Bulk Calls",
            "portcalls_general_cargo":"General Cargo Calls","portcalls_roro":"Ro-Ro Calls",
            "portcalls_tanker":"Tanker Calls","import":"Imports","export":"Exports"
        })
        st.markdown("### Latest daily observations")
        display_df(show.sort_values("Port Calls",ascending=False) if "Port Calls" in show.columns else show, max_rows=500)

        port_options=scoped[["portid","portname","country"]].dropna(subset=["portid"]).drop_duplicates().sort_values(["portname","country"]).to_dict("records")
        if port_options:
            st.markdown("### Port trend")
            pick=st.selectbox(
                "Port for recent history",
                range(len(port_options)),
                format_func=lambda i:f"{port_options[i]['portname']} — {port_options[i]['country']}",
                key="portwatch_history_port"
            )
            days=st.select_slider("Observations",options=[30,60,90,180,365],value=90,key="portwatch_history_days")
            hist_key=f"portwatch_history_{port_options[pick]['portid']}_{days}"
            hist,hist_error=load_portwatch_history(port_options[pick]["portid"],days)
            if not hist_error and not hist.empty:
                st.session_state[hist_key]=hist.copy()
            elif hist_error and hist_key in st.session_state:
                hist=st.session_state[hist_key]
                st.warning(f"History refresh failed; showing the last successful session result. {hist_error}")
                hist_error=""
            if hist_error:
                st.warning(f"Recent history could not be loaded. {hist_error}")
            elif not hist.empty:
                hist=hist.sort_values("Date")
                series_cols=[c for c in ["portcalls","portcalls_container","portcalls_tanker","import","export"] if c in hist.columns]
                if series_cols:
                    st.line_chart(hist.set_index("Date")[series_cols])
                st.caption("PortWatch measures observed daily shipping activity. Use it as an operational signal alongside P&C ownership, corridor, event and compliance data—not as a substitute for the canonical port record.")


elif page=="Live Feeds":
    header(
        "Live Feeds",
        "Operational and mobility APIs shown as separate evidence layers. Credentials, licensing and persistence are visible so the interface never implies that every feed is equally authoritative or permanently free."
    )
    aishub_user=_secret("AISHUB_USERNAME")
    navitia_token=_secret("NAVITIA_TOKEN")
    tabs=st.tabs(["Maritime AIS","Intermodal Mobility","API Catalog"])

    with tabs[0]:
        st.markdown("### AISHub · live vessel positions")
        st.caption("Contributor-access feed · minimum one-minute polling interval · live observations are not persisted in this Excel test build")
        if not aishub_user:
            st.info("AISHub is wired but not activated. Add `AISHUB_USERNAME` to Streamlit secrets after joining AISHub as a data contributor.")
        areas={
            "Strait of Hormuz":(23.0,27.5,54.0,58.5),
            "Dubai / Jebel Ali":(24.5,25.8,54.3,56.2),
            "Singapore Strait":(0.7,1.7,103.2,104.6),
            "Rotterdam / North Sea":(51.5,52.5,3.2,5.4),
            "Custom":None
        }
        c1,c2,c3=st.columns([1.4,1,1])
        with c1: area=st.selectbox("Area",list(areas),key="ais_area")
        with c2: imo=st.text_input("IMO filter",key="ais_imo",placeholder="e.g. 9220641")
        with c3: mmsi=st.text_input("MMSI filter",key="ais_mmsi")
        if area=="Custom":
            c1,c2,c3,c4=st.columns(4)
            latmin=c1.number_input("South",-90.0,90.0,20.0,key="ais_latmin")
            latmax=c2.number_input("North",-90.0,90.0,30.0,key="ais_latmax")
            lonmin=c3.number_input("West",-180.0,180.0,50.0,key="ais_lonmin")
            lonmax=c4.number_input("East",-180.0,180.0,60.0,key="ais_lonmax")
        else:
            latmin,latmax,lonmin,lonmax=areas[area]
        if st.button("Load live AIS",key="ais_load",disabled=not bool(aishub_user)):
            adf,aerr=load_aishub(aishub_user,latmin,latmax,lonmin,lonmax,mmsi,imo,30)
            st.session_state["aishub_results"]=(adf,aerr)
        adf,aerr=st.session_state.get("aishub_results",(pd.DataFrame(),""))
        if aerr: st.warning(aerr)
        elif not adf.empty:
            m1,m2,m3,m4=st.columns(4)
            m1.metric("Vessels in view",f"{len(adf):,}")
            m2.metric("With IMO",f"{adf.get('IMO',pd.Series(dtype=str)).astype(str).replace('0','').ne('').sum():,}")
            m3.metric("Underway >1 kn",f"{pd.to_numeric(adf.get('SOG',pd.Series(dtype=float)),errors='coerce').gt(1).sum():,}")
            m4.metric("Unique destinations",f"{adf.get('DEST',pd.Series(dtype=str)).replace('',pd.NA).dropna().nunique():,}")
            mapdf=adf.rename(columns={"LATITUDE":"lat","LONGITUDE":"lon"})
            if {"lat","lon"}.issubset(mapdf.columns):
                st.map(mapdf.dropna(subset=["lat","lon"])[["lat","lon"]],use_container_width=True)
            cols=[c for c in ["NAME","IMO","MMSI","TYPE","SOG","COG","DRAUGHT","DEST","ETA","TIME"] if c in adf.columns]
            display_df(adf[cols] if cols else adf,200,show_ids=True)
            st.caption("Visual rule: the map is situational awareness; the table is the auditable observation. AIS data should be linked to the canonical vessel only after IMO/MMSI resolution.")

    with tabs[1]:
        st.markdown("### Navitia · intermodal mobility & disruption")
        st.caption("Token-authenticated public transport API · useful around rail stations, ferry interfaces, airport access and urban disruption near logistics nodes")
        if not navitia_token:
            st.info("Navitia is wired but inactive. Add `NAVITIA_TOKEN` to Streamlit secrets to use real-world coverage.")
        if navitia_token:
            cov,cerr=navitia_get(navitia_token,"/coverage",{"count":200})
            if cerr:
                st.warning(cerr); coverage_ids=[]
            else:
                coverage_ids=[r.get("id","") for r in (cov or {}).get("regions",[]) if r.get("id")]
            if coverage_ids:
                region=st.selectbox("Coverage",coverage_ids,key="nav_region")
                n1,n2=st.tabs(["Stops / places","Disruptions"])
                with n1:
                    q=st.text_input("Find a station, stop or place",placeholder="Rotterdam Centraal",key="nav_q")
                    if st.button("Search mobility layer",key="nav_place_go") and q.strip():
                        pp,pe=navitia_get(navitia_token,f"/coverage/{region}/places",{"q":q.strip(),"count":50})
                        st.session_state["nav_places"]=(pp,pe)
                    pp,pe=st.session_state.get("nav_places",(None,""))
                    if pe: st.warning(pe)
                    elif pp:
                        pdf=_navitia_places_frame(pp)
                        if not pdf.empty:
                            m=pdf.rename(columns={"Latitude":"lat","Longitude":"lon"})
                            if {"lat","lon"}.issubset(m.columns): st.map(m.dropna(subset=["lat","lon"])[["lat","lon"]],use_container_width=True)
                            display_df(pdf,100,show_ids=True)
                with n2:
                    if st.button("Load current disruptions",key="nav_disrupt_go"):
                        dd,de=navitia_get(navitia_token,f"/coverage/{region}/disruptions",{"count":100})
                        st.session_state["nav_disrupt"]=(dd,de)
                    dd,de=st.session_state.get("nav_disrupt",(None,""))
                    if de: st.warning(de)
                    elif dd:
                        ddf=_navitia_disruptions_frame(dd)
                        if not ddf.empty:
                            c1,c2,c3=st.columns(3)
                            c1.metric("Active records",f"{len(ddf):,}")
                            c2.metric("No-service",f"{ddf['Effect'].astype(str).eq('NO_SERVICE').sum():,}")
                            c3.metric("Unique causes",f"{ddf['Cause'].replace('',pd.NA).dropna().nunique():,}")
                            display_df(ddf,150,show_ids=True)
                        else: st.info("No disruption records returned for this coverage.")
        st.caption("Visual rule: Navitia is contextual. It sits beside our canonical rail/intermodal network; it does not overwrite freight-network entities in Excel.")

    with tabs[2]:
        st.markdown("### API catalog · access and role")
        reg_path=Path(__file__).parent/"api_sources.json"
        try: registry=json.loads(reg_path.read_text())
        except Exception: registry={"sources":[]}
        sources=[dict(x) for x in registry.get("sources",[])]
        # Reflect actual runtime credential state rather than only the static registry label.
        runtime_enabled={
            "newsdata_io_latest": bool(_secret("NEWSDATA_API_KEY")),
            "aishub_live_ais": bool(aishub_user),
            "navitia_mobility": bool(navitia_token),
        }
        for x in sources:
            sid=str(x.get("id",""))
            if sid in runtime_enabled:
                x["status"]="enabled" if runtime_enabled[sid] else "credential_required"
        counts=defaultdict(int)
        for x in sources: counts[str(x.get("status","unknown"))]+=1
        c1,c2,c3,c4=st.columns(4)
        c1.metric("Registered feeds",len(sources))
        c2.metric("Enabled",counts.get("enabled",0))
        c3.metric("Credential-gated",counts.get("credential_required",0))
        c4.metric("Deferred / excluded",counts.get("deferred",0)+counts.get("excluded",0)+counts.get("registered",0))
        cards=[]
        for x in sources:
            status=str(x.get("status","registered"))
            cls="live" if status=="enabled" else "key" if status=="credential_required" else "trial" if status=="deferred" else "off"
            cards.append(f"<div class='pc-feed'><div class='pc-feed-title'>{html_lib.escape(str(x.get('name','')))}</div><div class='pc-feed-meta'>{html_lib.escape(str(x.get('domain','')))} · {html_lib.escape(str(x.get('access_model',x.get('cost',''))))}<br>{html_lib.escape(str(x.get('ui_role',x.get('implementation',''))))}</div><span class='pc-status pc-status-{cls}'>{html_lib.escape(status.replace('_',' '))}</span></div>")
        st.markdown("<div class='pc-feed-grid'>"+"".join(cards)+"</div>",unsafe_allow_html=True)
        catalog=pd.DataFrame(sources)
        showcols=[c for c in ["name","domain","access_model","status","authentication","persistence","ui_role"] if c in catalog.columns]
        display_df(catalog[showcols] if showcols else catalog,100,show_ids=True)
        st.caption("Design rule: green = immediately usable, amber = credential/contributor gated, trial = not a production dependency, grey = registered/deferred/excluded.")


elif page=="Government & Security":
    header(
        "Government & Security",
        "Country-first directory for defence ministries, armed forces, navies, coast guards, border organisations, operational commands, vessels and linked facilities."
    )
    render_government_security()



elif page=="Security & Business Risk":
    header(
        "Security & Business Risk",
        "A secondary drill-down for security incidents that materially affect trade, infrastructure, transport corridors or companies."
    )
    render_security_business_risk()


elif page=="Defence & Shipbuilding":
    header("Defence & Shipbuilding","Shipyards, government procurement, naval and research-vessel programmes, contracts, delivery routes and industrial capacity.")
    dcos=TABLES.get(("Defence & Shipbuilding","Defence Companies"),pd.DataFrame()).copy()
    yards=TABLES.get(("Defence & Shipbuilding","Shipyards"),pd.DataFrame()).copy()
    programmes=TABLES.get(("Defence & Shipbuilding","Programmes"),pd.DataFrame()).copy()
    participants=TABLES.get(("Defence & Shipbuilding","Programme Participants"),pd.DataFrame()).copy()
    vessels=TABLES.get(("Defence & Shipbuilding","Sample Vessels"),pd.DataFrame()).copy()
    contracts=TABLES.get(("Defence & Shipbuilding","Contracts"),pd.DataFrame()).copy()
    announcements=TABLES.get(("Defence & Shipbuilding","Announcements"),pd.DataFrame()).copy()
    routes=TABLES.get(("Defence & Shipbuilding","Sales & Delivery Routes"),pd.DataFrame()).copy()
    events=TABLES.get(("Events & Hazards","Events"),pd.DataFrame()).copy()

    k1,k2,k3,k4,k5=st.columns(5)
    k1.metric("Companies",len(dcos))
    k2.metric("Shipyards",len(yards))
    k3.metric("Programmes",len(programmes))
    k4.metric("Vessels",len(vessels))
    k5.metric("Contracts",len(contracts))

    q=st.text_input("Search defence & shipbuilding",placeholder="GRSE, NCPOR, ADSB, Fincantieri, Davie, icebreaker, research vessel...")
    if q:
        dcos=_contains_any(dcos,[q]); yards=_contains_any(yards,[q]); programmes=_contains_any(programmes,[q])
        vessels=_contains_any(vessels,[q]); contracts=_contains_any(contracts,[q]); announcements=_contains_any(announcements,[q]); routes=_contains_any(routes,[q])

    tabs=st.tabs(["Overview","Programmes","Shipyards","Vessels","Contracts","Events & Announcements","Delivery Routes"])
    with tabs[0]:
        st.markdown("### Industrial base")
        display_df(dcos[[c for c in ["Entity","Industrial Model","Country / Geography","Markets","Ownership / Role Note","Status"] if c in dcos.columns]],220)
        if not events.empty:
            devents=_contains_any(events,["defence","shipbuilding","naval","coast guard","research vessel","shipyard"],["Event Family","Event Type","Mode","Title","Description","Trade / Commercial Impact"])
            st.markdown("### Recent linked events")
            render_event_cards(devents,20)
    with tabs[1]:
        display_df(programmes[[c for c in ["Programme","Customer Type","Customer","Quantity","Platform / Class","Contract Value","Status","Build / Sales Route"] if c in programmes.columns]],260)
        if not participants.empty:
            with st.expander("Programme participants"):
                display_df(participants,260)
    with tabs[2]:
        display_df(yards[[c for c in ["Shipyard","Location","Country","Yard Model","Current / Representative Work","Status"] if c in yards.columns]],260)
        if not yards.empty and "Yard ID" in yards.columns:
            pick=st.selectbox("Inspect shipyard",range(len(yards)),format_func=lambda i:f"{yards.iloc[i].get('Shipyard','')} — {yards.iloc[i].get('Country','')}",key="defence_yard_pick")
            if st.button("Open detailed shipyard",key="defence_open_yard"):
                request_nav("Shipyards","yard_pick_id",yards.iloc[pick].get("Yard ID",""),yards.iloc[pick].get("Shipyard",""))
                st.rerun()
    with tabs[3]:
        if vessels.empty:
            st.info("No defence / government vessels are available.")
        else:
            vv=vessels.copy()
            # Country is not guaranteed on every legacy defence vessel row, so expose whatever geography exists.
            sort_cols=[c for c in ["Customer / Operator","Vessel"] if c in vv.columns]
            if sort_cols:
                vv=vv.sort_values(sort_cols,na_position="last")
            vv=vv.reset_index(drop=True)

            display_df(vv[[c for c in ["Vessel","Class / Type","Customer / Operator","Build Yard ID","Status","Build / Delivery Route"] if c in vv.columns]],300)

            st.markdown("### Inspect a vessel")
            dpick=st.selectbox(
                "Defence / government vessel",
                range(len(vv)),
                format_func=lambda i: " — ".join([
                    z for z in [
                        str(vv.iloc[i].get("Vessel","")).strip(),
                        str(vv.iloc[i].get("Class / Type","")).strip(),
                        str(vv.iloc[i].get("Customer / Operator","")).strip(),
                    ] if z
                ]),
                key="defence_vessel_detail_pick"
            )
            dr=vv.iloc[dpick]
            did=str(dr.get("Vessel ID","")).strip()
            dname=str(dr.get("Vessel","")).strip() or did
            if did:
                render_defence_vessel_profile(did,dname)
            else:
                st.markdown(f"### {dname}")
                display_df(
                    pd.DataFrame([
                        {"Field":c,"Value":dr.get(c,"")}
                        for c in ["Class / Type","Customer / Operator","Build Yard ID","Status","Build / Delivery Route"]
                        if str(dr.get(c,"")).strip()
                    ]),
                    50
                )
    with tabs[4]:
        display_df(contracts[[c for c in ["Date","Customer","Contractor Entity ID","Value","Scope","Contract Type","Status / Evidence Note"] if c in contracts.columns]],260)
    with tabs[5]:
        if not announcements.empty:
            display_df(announcements[[c for c in ["Date","Headline","Primary Entity ID","Programme ID","Event Type","Linked Entities / Topics"] if c in announcements.columns]],260)
        if not events.empty:
            devents=_contains_any(events,["defence","shipbuilding","naval","coast guard","research vessel","shipyard"],["Event Family","Event Type","Mode","Title","Description"])
            render_event_cards(devents,35)
    with tabs[6]:
        display_df(routes,220)
    render_connected_domain_context(
        "Defence & Shipbuilding",
        modes=("maritime",),
        keywords=("defence","defense","shipbuilding","shipyard","naval","coast guard")
    )

elif page=="Shipyards":
    header("Shipyards","Physical shipyard assets: ownership, capabilities, facilities, programmes, vessels and events.")
    yards=TABLES.get(("Defence & Shipbuilding","Shipyards"),pd.DataFrame())
    if yards.empty:
        st.info("Shipyard data unavailable.")
    else:
        requested_yard=st.session_state.pop("yard_pick_id",None)
        if requested_yard:
            st.session_state["yard_search_text"]=""
        q=st.text_input("Find shipyard / country / company",placeholder="Lévis, Rauma, Antalya, Bollinger, Inocea...",key="yard_search_text")
        y=yards.copy()
        if q: y=_contains_any(y,[q],["Shipyard","Location","Country","Yard Model","Current / Representative Work"])
        y=y.sort_values("Shipyard").reset_index(drop=True)
        default_yard=0
        if requested_yard and "Yard ID" in y.columns:
            mi=y.index[y["Yard ID"].astype(str).eq(str(requested_yard))].tolist()
            if mi: default_yard=int(mi[0])

        if requested_yard:
            st.session_state["yard_select_idx"]=int(default_yard)
        else:
            safe_index_state("yard_select_idx",int(default_yard),len(y))

        pick=st.selectbox(
            "Shipyard",
            range(len(y)),
            format_func=lambda i:f"{y.iloc[i]['Shipyard']} — {y.iloc[i]['Country']}",
            key="yard_select_idx"
        )
        r=y.iloc[pick]; yid=str(r["Yard ID"]); cid=str(r["Company Entity ID"])
        st.markdown(f"## {r['Shipyard']}")
        st.caption(f"{label(cid)} · {r.get('Location','')} · {r.get('Yard Model','')}")
        sm=shipyard_map_data({"yards":pd.DataFrame([r])})
        if not sm.empty: st.map(sm,latitude="lat",longitude="lon",size=100)
        fac=TABLES.get(("Defence & Shipbuilding","Yard Facilities"),pd.DataFrame())
        caps=TABLES.get(("Defence & Shipbuilding","Yard Capabilities"),pd.DataFrame())
        vessels=TABLES.get(("Defence & Shipbuilding","Sample Vessels"),pd.DataFrame())
        yf=_match_any(fac,["Yard ID"],[yid]); yc=_match_any(caps,["Yard ID"],[yid]); yv=_match_any(vessels,["Build Yard ID"],[yid])
        ev,loc,chains=event_bundle_for_entities([cid],[yid],[])
        tabs=st.tabs(["Facilities","Capabilities","Vessels","Events","Evidence"])
        with tabs[0]: display_df(yf,150)
        with tabs[1]: display_df(yc,150)
        with tabs[2]: display_df(yv,150)
        with tabs[3]:
            render_event_map(ev,loc,"Shipyard-linked events")
            render_event_cards(ev,50)
        with tabs[4]: display_df(pd.DataFrame([r]),20)

elif page=="Vessels":
    header("Vessels","Commercial, naval, Coast Guard and government vessels as linked intelligence objects.")
    commercial=commercial_vessels_with_official_stubs().copy()
    defence=TABLES.get(("Defence & Shipbuilding","Sample Vessels"),pd.DataFrame()).copy()
    service=TABLES.get(("Maritime","Service Craft"),pd.DataFrame()).copy()

    requested_vessel=st.session_state.pop("vessel_pick_id",None)
    requested_domain=None
    if requested_vessel:
        if not defence.empty and "Vessel ID" in defence.columns and defence["Vessel ID"].astype(str).eq(str(requested_vessel)).any():
            requested_domain="Defence / Government"
        elif not commercial.empty and "Vessel ID" in commercial.columns and commercial["Vessel ID"].astype(str).eq(str(requested_vessel)).any():
            requested_domain="Commercial"
        st.session_state["vessel_search_text"]=label(requested_vessel)
        if requested_domain:
            st.session_state["vessel_domain"]=requested_domain

    domain=st.radio(
        "Fleet domain",
        ["Commercial","Defence / Government","Service Craft"],
        horizontal=True,
        key="vessel_domain"
    )

    q=st.text_input(
        "Find vessel / IMO / owner / customer / class / programme",
        placeholder="HMCS Harry DeWolf, ALTAF, Bani Yas, P51MR, LADY MARIIA...",
        key="vessel_search_text"
    )

    if domain=="Commercial":
        c=commercial.copy()
        if q: c=_contains_any(c,[q])
        c=c.reset_index(drop=True)
        if c.empty:
            st.info("No matching canonical commercial vessel.")
        else:
            requested_index=0
            if requested_vessel and "Vessel ID" in c.columns:
                mi=c.index[c["Vessel ID"].astype(str).eq(str(requested_vessel))].tolist()
                if mi: requested_index=int(mi[0])
            if requested_vessel and requested_domain=="Commercial":
                st.session_state["vessel_select_idx"]=requested_index
            else:
                safe_index_state("vessel_select_idx",requested_index,len(c))

            pick=st.selectbox(
                "Commercial vessel",
                range(len(c)),
                format_func=lambda i:f"{c.iloc[i].get('Vessel Name','')} — IMO {c.iloc[i].get('IMO','')}",
                key="vessel_select_idx"
            )
            vr=c.iloc[pick]
            render_vessel_profile(str(vr.get("Vessel ID","")),str(vr.get("Vessel Name","")))

    elif domain=="Defence / Government":
        d=defence.copy()
        if q: d=_contains_any(d,[q])
        d=d.reset_index(drop=True)
        if d.empty:
            st.info("No matching defence / government vessel.")
        else:
            requested_index=0
            if requested_vessel and "Vessel ID" in d.columns:
                mi=d.index[d["Vessel ID"].astype(str).eq(str(requested_vessel))].tolist()
                if mi: requested_index=int(mi[0])
            if requested_vessel and requested_domain=="Defence / Government":
                st.session_state["defence_vessel_select_idx"]=requested_index
            else:
                safe_index_state("defence_vessel_select_idx",requested_index,len(d))

            pick=st.selectbox(
                "Defence / government vessel",
                range(len(d)),
                format_func=lambda i:f"{d.iloc[i].get('Vessel','')} — {d.iloc[i].get('Class / Type','')} — {d.iloc[i].get('Customer / Operator','')}",
                key="defence_vessel_select_idx"
            )
            vr=d.iloc[pick]
            render_defence_vessel_profile(str(vr.get("Vessel ID","")),str(vr.get("Vessel","")))


    else:
        s=service.copy()
        if q:
            s=_contains_any(s,[q])
        s=s.reset_index(drop=True)
        if s.empty:
            st.info("No matching service craft.")
        else:
            pick=st.selectbox(
                "Service craft",
                range(len(s)),
                format_func=lambda i:f"{s.iloc[i].get('Vessel Name','')} — {s.iloc[i].get('Craft Segment','')}",
                key="service_craft_select_idx"
            )
            vr=s.iloc[pick]
            st.markdown(f"## {vr.get('Vessel Name','')}")
            c1,c2,c3=st.columns(3)
            c1.markdown(f"<div class='pc-card'><div class='pc-label'>Segment</div><div class='pc-big'>{vr.get('Craft Segment','')}</div></div>",unsafe_allow_html=True)
            c2.markdown(f"<div class='pc-card'><div class='pc-label'>Subtype / class</div><div class='pc-big'>{vr.get('Subtype / Class','')}</div></div>",unsafe_allow_html=True)
            c3.markdown(f"<div class='pc-card'><div class='pc-label'>Home port</div><div class='pc-big'>{vr.get('Home Port','') or '—'}</div></div>",unsafe_allow_html=True)
            op=str(vr.get("Operator Company ID","")).strip()
            if op:
                st.markdown("### Operator")
                st.write(label(op))
                linked_company_button(op,f"service_company_{pick}")
            clean_network_table(pd.DataFrame([vr]),["Vessel Name","IMO","Flag","Year Built","DWT","Capacity / Scale","Primary Service","Fuel / Propulsion","Status","Completeness Note"],160)


elif page in ["Deals, Projects & Contracts","Contracts"]:
    render_deals_projects_contracts_workspace()

elif page=="Trade Policy":
    header("Trade Policy & Market Access","CEPAs, FTAs, customs unions, tariffs, rules of origin, procurement and trade remedies tied back to P&C assets and companies.")
    agreements=TABLES.get(("Trade Policy & Compliance","Trade Agreements"),pd.DataFrame()).copy()
    if agreements.empty:
        st.info("Trade-policy workbook not available.")
    else:
        q=st.text_input("Find agreement / country / corridor",placeholder="Georgia, Azerbaijan, Congo, DRC, Türkiye, Middle Corridor...")
        statuses=sorted([x for x in agreements["Status"].astype(str).unique().tolist() if x.strip()]) if "Status" in agreements.columns else []
        status_sel=st.multiselect("Status",statuses,default=[])
        a=agreements.copy()
        if q: a=_contains_any(a,[q])
        if status_sel: a=a[a["Status"].isin(status_sel)]

        c1,c2=st.columns(2)
        with c1:
            if not a.empty and "Status" in a.columns:
                st.markdown("### Agreements by status")
                st.bar_chart(a["Status"].value_counts(),horizontal=True)
        with c2:
            if not a.empty and "Agreement Type" in a.columns:
                st.markdown("### Agreement types")
                st.bar_chart(a["Agreement Type"].value_counts(),horizontal=True)

        opts=a.sort_values("Agreement").reset_index(drop=True)
        if opts.empty:
            st.warning("No matching agreements.")
        else:
            pick=st.selectbox("Agreement",range(len(opts)),format_func=lambda i:f"{opts.iloc[i]['Agreement']} — {opts.iloc[i]['Status']}")
            r=opts.iloc[pick]; aid=str(r["Agreement ID"])
            st.markdown(f"## {r['Agreement']}")
            st.caption(f"{r.get('Status','')} · {r.get('Strategic Geography','')}")
            st.markdown(f"**Tariff coverage:** {r.get('Tariff Coverage Summary','')}  ")
            st.markdown(f"**P&C relevance:** {r.get('P&C Relevance','')}")
            src=str(r.get("Source URL","")).strip()
            if src.startswith("http"): st.markdown(f"[Open official / primary source ↗]({src})")

            aal=TABLES.get(("Trade Policy & Compliance","Agreement Asset Links"),pd.DataFrame())
            acl=TABLES.get(("Trade Policy & Compliance","Agreement Company Links"),pd.DataFrame())
            tc=TABLES.get(("Trade Policy & Compliance","Tariff Coverage"),pd.DataFrame())
            hs=TABLES.get(("Trade Policy & Compliance","HS Product Tests"),pd.DataFrame())
            roo=TABLES.get(("Trade Policy & Compliance","Rules of Origin"),pd.DataFrame())
            cp=TABLES.get(("Trade Policy & Compliance","Customs & Procurement"),pd.DataFrame())
            tr=TABLES.get(("Trade Policy & Compliance","Trade Remedies & Restrictions"),pd.DataFrame())
            filt=lambda df: df[df["Agreement ID"].astype(str).eq(aid)].copy() if (not df.empty and "Agreement ID" in df.columns) else pd.DataFrame()
            tabs=st.tabs(["Linked Assets","Companies","Tariffs / HS Tests","Origin & Customs","Remedies / Restrictions"])
            with tabs[0]: display_df(filt(aal),200)
            with tabs[1]: display_df(filt(acl),200)
            with tabs[2]:
                display_df(filt(tc),100)
                display_df(filt(hs),150)
            with tabs[3]:
                display_df(filt(roo),100)
                display_df(filt(cp),100)
            with tabs[4]:
                # include global interaction rules as well
                x=filt(tr)
                global_rows=tr[tr.get("Agreement ID / Scope",pd.Series(dtype=str)).astype(str).eq("GLOBAL_RULE")].copy() if not tr.empty else pd.DataFrame()
                display_df(pd.concat([x,global_rows],ignore_index=True) if not global_rows.empty else x,100)

elif page=="Sanctions & Compliance":
    header(
        "Sanctions & Compliance",
        "Direct government designations, ownership/control and counterparty exposure, trade restrictions, screening results and operational compliance."
    )
    render_canonical_sanctions_model()
    des,des_source=_policy_live_first(TABLES.get(("Trade Policy & Compliance","Sanctions Designations"),pd.DataFrame()),["pc_sanctions_designations","sanctions_designations"],["Designation ID"])
    auth,auth_source=_policy_live_first(TABLES.get(("Trade Policy & Compliance","Sanctions Authorities"),pd.DataFrame()),["pc_sanctions_authorities","sanctions_authorities"],["Authority ID"])
    progs,progs_source=_policy_live_first(TABLES.get(("Trade Policy & Compliance","Sanctions Programmes"),pd.DataFrame()),["pc_sanctions_programmes","pc_sanctions_programs","sanctions_programmes"],["Programme ID"])
    links,links_source=_policy_live_first(TABLES.get(("Trade Policy & Compliance","Sanctions Entity Links"),pd.DataFrame()),["pc_sanctions_entity_links","sanctions_entity_links"],["Designation ID","Entity ID"])
    watch,watch_source=_policy_live_first(TABLES.get(("Trade Policy & Compliance","Watchlist Taxonomy"),pd.DataFrame()),["pc_watchlist_taxonomy","watchlist_taxonomy"],["Class"])
    rules,rules_source=_policy_live_first(TABLES.get(("Trade Policy & Compliance","Policy Interaction Rules"),pd.DataFrame()),["pc_policy_interaction_rules","policy_interaction_rules"])
    compliance_regimes,regime_source=_policy_live_first(TABLES.get(("Trade Policy & Compliance","Compliance Regimes"),pd.DataFrame()),["pc_compliance_regimes","compliance_regimes"],["Regime"])
    compliance_designations,compdes_source=_policy_live_first(TABLES.get(("Trade Policy & Compliance","Compliance Designations"),pd.DataFrame()),["pc_compliance_designations","compliance_designations"])
    compliance_exposure,exposure_source=_policy_live_first(TABLES.get(("Trade Policy & Compliance","Compliance Exposure"),pd.DataFrame()),["pc_compliance_exposure","compliance_exposure"])
    _policy_sources={x for x in [des_source,auth_source,progs_source,links_source,watch_source,rules_source,regime_source,compdes_source,exposure_source] if x}
    st.caption("Data bridge: " + " · ".join(sorted(_policy_sources)))

    if des.empty and compliance_designations.empty:
        st.info("Sanctions data unavailable.")
    else:
        q=st.text_input(
            "Find vessel / company / IMO / authority / programme",
            placeholder="LADY MARIIA, SUN, 9220641, OFAC, Iran, Russia..."
        )

        # Search raw data so IDs/names/programmes all remain discoverable,
        # but never expose implementation IDs in the normal presentation.
        d=des.copy()
        l=links.copy()
        if q:
            d=_contains_any(d,[q])
            l=_contains_any(l,[q])

            # If the query matches an entity-link record, include its designation.
            if not l.empty and "Designation ID" in l.columns and "Designation ID" in des.columns:
                linked_ids=set(l["Designation ID"].astype(str))
                extra=des[des["Designation ID"].astype(str).isin(linked_ids)]
                d=pd.concat([d,extra],ignore_index=True).drop_duplicates()

            # If the query matches a designation, include its entity link.
            if not d.empty and "Designation ID" in d.columns and "Designation ID" in links.columns:
                dids=set(d["Designation ID"].astype(str))
                extra_links=links[links["Designation ID"].astype(str).isin(dids)]
                l=pd.concat([l,extra_links],ignore_index=True).drop_duplicates()

        # Compact headline metrics.
        m1,m2,m3,m4=st.columns(4)
        m1.metric("Designations",len(d))
        m2.metric("Vessels",int((d.get("Target Type",pd.Series(dtype=str)).astype(str).str.lower()=="vessel").sum()) if not d.empty else 0)
        m3.metric("Authorities",d["Authority ID"].nunique() if not d.empty and "Authority ID" in d.columns else 0)
        m4.metric("Programmes",d["Programme ID"].nunique() if not d.empty and "Programme ID" in d.columns else 0)

        counts=sanctions_programme_counts(d)
        if not counts.empty:
            render_dark_bar_list(counts,"Programme","Designations","Designations by programme")

        tabs=st.tabs([
            "Government Sanctions",
            "Operational Compliance",
            "Exposure & Counterparties",
            "Linked Entities",
            "Authorities & Programmes",
            "Watchlists",
            "Policy Precedence"
        ])

        with tabs[0]:
            st.markdown("### Government sanctions designations")
            display_df(humanize_sanctions_df(d),250)

        with tabs[1]:
            st.markdown("### Operational compliance regimes")
            st.caption("PGSA and other operational regimes remain analytically distinct from OFAC, EU, UK, UN and other government sanctions authorities.")

            pgsa_event,pgsa_vessels=canonical_pgsa_vessels_trade()
            if pgsa_event:
                st.markdown("#### PGSA vessel list")
                p1,p2,p3=st.columns(3)
                p1.metric("Canonical listed vessels",len(pgsa_vessels))
                p2.metric("Event date",str(pgsa_event.get("start_date") or "")[:10])
                p3.metric("Status",str(pgsa_event.get("status") or ""))
                st.markdown(f"**{pgsa_event.get('title','PGSA compliance-list update')}**")
                if pgsa_event.get("operational_impact"):
                    st.write(pgsa_event.get("operational_impact"))

                if not pgsa_vessels.empty:
                    qpg=st.text_input(
                        "Filter PGSA vessels",
                        placeholder="vessel name, IMO, flag, type…",
                        key="trade_pgsa_vessel_filter"
                    )
                    view=pgsa_vessels.copy()
                    if qpg.strip():
                        mask=view.astype(str).apply(
                            lambda c:c.str.contains(qpg.strip(),case=False,na=False,regex=False)
                        ).any(axis=1)
                        view=view[mask].copy()

                    display_df(
                        view[[c for c in ["Vessel","IMO","MMSI","Flag","Vessel Type","Status","Relationship"] if c in view.columns]],
                        520
                    )

                    if not view.empty:
                        choices=view.to_dict("records")
                        pick=st.selectbox(
                            "Open vessel profile",
                            range(len(choices)),
                            format_func=lambda i:
                                f"{choices[i].get('Vessel','')}"
                                + (f" · IMO {choices[i].get('IMO')}" if choices[i].get("IMO") else "")
                                + (f" · {choices[i].get('Flag')}" if choices[i].get("Flag") else ""),
                            key="trade_pgsa_open_vessel_pick"
                        )
                        vessel=choices[pick]
                        if st.button(
                            f"Open {vessel.get('Vessel','vessel')} in canonical drill-down",
                            type="primary",
                            use_container_width=True,
                            key=f"trade_pgsa_open_vessel_{vessel.get('Canonical ID')}"
                        ):
                            pc_set_drilldown("mobile_asset",vessel.get("Canonical ID"),vessel.get("Vessel"))
                else:
                    st.warning("A PGSA canonical event was found, but no linked mobile assets were returned.")
            else:
                st.info("No canonical PGSA vessel-list event is currently available.")

            st.markdown("#### Other operational compliance records")
            if compliance_regimes.empty and compliance_designations.empty:
                st.caption("No additional operational compliance records loaded.")
            else:
                if not compliance_regimes.empty:
                    display_df(compliance_regimes,100)
                if not compliance_designations.empty:
                    st.markdown("##### Designations / restrictions")
                    display_df(compliance_designations,200)

        with tabs[2]:
            st.markdown("### Secondary exposure & counterparties")
            if compliance_exposure.empty:
                st.info("No counterparty exposure records loaded.")
            else:
                display_df(compliance_exposure,200)

        with tabs[3]:
            st.markdown("### Designated / linked entities")
            if l.empty:
                st.info("No linked entities for this filter.")
            else:
                render_sanction_link_cards(l)

        with tabs[4]:
            a=auth.copy()
            if not a.empty:
                # Authority IDs are backend keys; show names and jurisdiction.
                a=a.drop(columns=[c for c in ["Authority ID"] if c in a.columns],errors="ignore")
                st.markdown("### Authorities")
                display_df(a,100)
            if not progs.empty:
                pp=progs.copy()
                if "Authority ID" in pp.columns:
                    pp["Authority"]=pp["Authority ID"].astype(str).map(lambda x:SAN_AUTH_MAP.get(x,x))
                pp=pp.drop(columns=[c for c in ["Programme ID","Authority ID"] if c in pp.columns],errors="ignore")
                st.markdown("### Programmes")
                display_df(pp,100)

        with tabs[5]:
            st.markdown("### Watchlist taxonomy")
            st.caption("These categories are intentionally separate: a security advisory, shadow-fleet flag or IUU listing is not automatically a government sanctions designation.")
            display_df(humanize_sanctions_df(watch),100)

        with tabs[6]:
            st.markdown("### Policy precedence")
            st.caption("Trade preferences never override sanctions, prohibitions or export-control requirements.")
            rr=rules.copy()
            rr=rr.drop(columns=[c for c in ["Rule ID"] if c in rr.columns],errors="ignore")
            display_df(rr,100)

elif page=="__DEFERRED_USCG_SAFETY_COMPLIANCE__":
    header(
        "USCG Safety & Compliance",
        "Live CGMIX/PSIX and Incident Investigation Report lookups. This is an external evidence layer and is not written into the canonical data model."
    )
    st.caption("Source: U.S. Coast Guard CGMIX · PSIX is a weekly FOIA/MISLE snapshot · live requests cached for 30 minutes")
    t1,t2=st.tabs(["PSIX Vessel / Inspection Search","Incident Investigations"])
    with t1:
        c1,c2,c3=st.columns([2,1.2,1.2])
        with c1:
            vessel_name=st.text_input("Vessel name",placeholder="EVER GIVEN, MAERSK, tanker name...",key="cgmix_vessel_name")
        with c2:
            imo=st.text_input("IMO / primary ID",placeholder="IMO number",key="cgmix_imo")
        with c3:
            service=st.selectbox("Service",["ALL","Freight Ship","Tank Ship","Passenger (Inspected)","Towing Vessel","Offshore Supply Vessel","Commercial Fishing Vessel"],key="cgmix_service")
        if st.button("Search USCG PSIX",key="cgmix_psix_go",use_container_width=False):
            if not vessel_name.strip() and not imo.strip():
                st.warning("Enter a vessel name or IMO / primary identification number.")
            else:
                results,error=cgmix_psix_vessel_search(vessel_name.strip(),imo.strip(),"",service)
                st.session_state["cgmix_psix_results"]=(results,error)
        results,error=st.session_state.get("cgmix_psix_results",(pd.DataFrame(),""))
        if error:
            st.warning(f"CGMIX PSIX is temporarily unavailable. {error}")
        elif not results.empty:
            st.markdown(f"### Vessel matches · {len(results):,}")
            show=results.copy()
            display_df(show,100)
            if "VesselID" in results.columns:
                options=results.to_dict("records")
                selected=st.selectbox("Inspect USCG contacts / cases",range(len(options)),format_func=lambda i:f"{options[i].get('VesselName','')} — {options[i].get('Identification','')} — {options[i].get('CountryLookupName','')}",key="cgmix_psix_pick")
                vid=options[selected].get("VesselID","")
                cases,cerr=cgmix_psix_cases(vid)
                if cerr:
                    st.info(f"Vessel cases could not be loaded. {cerr}")
                elif cases.empty:
                    st.info("No published USCG vessel cases returned for this vessel.")
                else:
                    st.markdown("### USCG contacts / vessel cases")
                    display_df(cases.sort_values("StartDtTm",ascending=False) if "StartDtTm" in cases.columns else cases,200)
                    if "ActivityID" in cases.columns:
                        acts=cases.to_dict("records")
                        ai=st.selectbox("Case / activity details",range(len(acts)),format_func=lambda i:f"{acts[i].get('StartDtTm','')} · {acts[i].get('TypeLookupName','')} · {acts[i].get('USCGZonePort','')}",key="cgmix_activity_pick")
                        aid=acts[ai].get("ActivityID","")
                        ddf,derr=cgmix_psix_deficiencies(aid)
                        odf,oerr=cgmix_psix_controls(aid)
                        a,b=st.columns(2)
                        with a:
                            st.markdown("#### Deficiencies")
                            if derr: st.caption(derr)
                            elif ddf.empty: st.caption("None returned.")
                            else: display_df(ddf,150)
                        with b:
                            st.markdown("#### Operational controls")
                            if oerr: st.caption(oerr)
                            elif odf.empty: st.caption("None returned.")
                            else: display_df(odf,150)
        else:
            st.info("Search CGMIX by vessel name or IMO to retrieve live USCG records.")

    with t2:
        st.caption("Published IIR records cover reportable marine casualties investigated by the USCG. Search results are source evidence; they are not automatically promoted to canonical P&C events.")
        c1,c2=st.columns(2)
        with c1:
            iv=st.text_input("Vessel",placeholder="Vessel name",key="iir_vessel")
            io=st.text_input("Organisation",placeholder="Operator, owner, facility company...",key="iir_org")
        with c2:
            iff=st.text_input("Facility",placeholder="Terminal / facility",key="iir_facility")
            ik=st.text_input("Keyword",placeholder="collision, grounding, fire, allision...",key="iir_keyword")
        if st.button("Search incident investigations",key="iir_go"):
            if not any([iv.strip(),io.strip(),iff.strip(),ik.strip()]):
                st.warning("Enter at least one incident search term.")
            else:
                irr,ier=cgmix_iir_search(iv.strip(),io.strip(),iff.strip(),ik.strip())
                st.session_state["cgmix_iir_results"]=(irr,ier)
        irr,ier=st.session_state.get("cgmix_iir_results",(pd.DataFrame(),""))
        if ier:
            st.warning(f"CGMIX IIR is temporarily unavailable. {ier}")
        elif not irr.empty:
            if "StartDtTm" in irr.columns:
                irr=irr.sort_values("StartDtTm",ascending=False)
            st.markdown(f"### Published investigations · {len(irr):,}")
            display_df(irr,250)

elif page=="News & Events":
    header("News & Events","Map assets and systems affected by war, weather, natural hazards, labour, operational incidents and announced commercial activity.")
    events=TABLES.get(("Events & Hazards","Events"),pd.DataFrame()).copy()
    locations=TABLES.get(("Events & Hazards","Event Locations"),pd.DataFrame()).copy()
    q=st.text_input("Search events / location / company / system",placeholder="Rotterdam, strike, Black Sea, AD Ports, typhoon, Genoa...")
    families=sorted([x for x in events.get("Event Family",pd.Series(dtype=str)).unique().tolist() if str(x).strip()])
    selected=st.multiselect("Event families",families,default=[])
    e=events
    if q:
        e=_contains_any(e,[q])
        # also expand through company/asset/system link names
        ids=set(e["Event ID"].astype(str).tolist()) if not e.empty else set()
        for key in [("Events & Hazards","Event Company Links"),("Events & Hazards","Event Asset Links"),("Events & Hazards","Event System Links")]:
            df=TABLES.get(key,pd.DataFrame())
            if not df.empty:
                m=_contains_any(df,[q])
                if "Event ID" in m.columns: ids.update(m["Event ID"].astype(str).tolist())
        e=events[events["Event ID"].astype(str).isin(ids)] if ids else events.iloc[0:0]
    if selected:
        e=e[e["Event Family"].isin(selected)]
    ids=set(e["Event ID"].astype(str)) if not e.empty else set()
    loc=locations[locations["Event ID"].astype(str).isin(ids)] if ids else locations.iloc[0:0]

    render_live_event_cluster(e,loc)
    render_event_map(e,loc,"Event & activity map")
    # severity / family figures
    if not e.empty:
        c1,c2=st.columns(2)
        with c1:
            fam=e["Event Family"].value_counts()
            if not fam.empty:
                st.markdown("### Events by family"); st.bar_chart(fam,horizontal=True)
        with c2:
            sev=e["Severity"].value_counts()
            if not sev.empty:
                st.markdown("### Events by severity"); st.bar_chart(sev,horizontal=True)
    t1,t2,t3=st.tabs(["Event Feed","Impact Chains","Linked Assets / Companies"])
    with t1:
        feed=e.copy()
        if not feed.empty and "Date" in feed.columns:
            feed["_dt"]=pd.to_datetime(feed["Date"],errors="coerce")
            feed=feed.sort_values("_dt",ascending=False)
        render_event_cards(feed,100)
    with t2:
        chains=TABLES.get(("Events & Hazards","Impact Chains"),pd.DataFrame())
        if ids: chains=chains[chains["Event ID"].astype(str).isin(ids)]
        display_df(chains,200)
    with t3:
        al=TABLES.get(("Events & Hazards","Event Asset Links"),pd.DataFrame())
        cl=TABLES.get(("Events & Hazards","Event Company Links"),pd.DataFrame())
        sl=TABLES.get(("Events & Hazards","Event System Links"),pd.DataFrame())
        if ids:
            al=al[al["Event ID"].astype(str).isin(ids)]
            cl=cl[cl["Event ID"].astype(str).isin(ids)]
            sl=sl[sl["Event ID"].astype(str).isin(ids)]
        a,b,c=st.tabs(["Assets","Companies","Systems"])
        with a:
            render_linked_objects(
                al,
                object_type_col="Asset Type",
                object_id_col="Asset ID",
                object_name_col="Asset",
                relationship_col="Relationship",
                confidence_col="Confidence",
                max_items=200
            )
        with b:
            render_linked_objects(
                cl,
                object_type_col="Relationship",
                object_id_col="Company ID",
                object_name_col="Company",
                relationship_col="Relationship",
                confidence_col="Confidence",
                max_items=200
            )
        with c:
            render_linked_objects(
                sl,
                object_type_col="Relationship",
                object_id_col="System ID",
                object_name_col="System",
                relationship_col="Relationship",
                confidence_col="Confidence",
                max_items=200
            )

elif page in {"News & Signals","News & Developments"}:
    header(
        "News & Developments",
        "Canonical company, network, disruption and sanctions developments lead this workspace. Open-source feeds remain a discovery layer for promotion into the canonical model."
    )

    stories=_canonical_trade_story_frame()
    tabs=st.tabs(["Lead Developments","Company & Network","Disruptions","Sanctions & Compliance","Open-source Discovery"])

    with tabs[0]:
        if stories.empty:
            st.info("No canonical developments are currently available.")
        else:
            lead=stories[stories.get("Lead Story",pd.Series(False,index=stories.index)).fillna(False)]
            if lead.empty:
                lead=stories[stories.get("Is Story",pd.Series(True,index=stories.index)).fillna(True)].head(20)
            _render_trade_story_cards(lead,20,key_prefix='news_lead')

    with tabs[1]:
        if stories.empty:
            st.info("No company-linked canonical developments.")
        else:
            company=stories[
                stories.get("Linked Companies",pd.Series(index=stories.index,dtype=str)).fillna("").astype(str).str.len().gt(0)
            ]
            q=st.text_input("Filter company / network developments",placeholder="DP World, AD Ports, Noatum, Hapag-Lloyd...",key="canonical_company_story_q")
            if q.strip() and not company.empty:
                company=_contains_any(company,[q])
            _render_trade_story_cards(company,40,key_prefix='news_company')

    with tabs[2]:
        dis=_canonical_trade_disruptions()
        q=st.text_input("Filter disruptions",placeholder="Panama, Rhine, rail, port, aviation...",key="canonical_disruption_story_q")
        if q.strip() and not dis.empty:
            dis=_contains_any(dis,[q])
        _render_trade_story_cards(dis,40,key_prefix='news_disruption')

    with tabs[3]:
        st.markdown("### Canonical sanctions designations")
        try:
            sb=pc_db_client(service=True)
            srows=pc_safe_rows(sb,"pc_sanctions_designations","*",5000,order="designation_date") if sb else []
            slinks=pc_safe_rows(sb,"pc_sanctions_entity_links","*",10000) if sb else []
        except Exception:
            srows=[]; slinks=[]
        if srows:
            sdf=pd.DataFrame(srows)
            if "designation_date" in sdf.columns:
                sdf["_dt"]=pd.to_datetime(sdf["designation_date"],errors="coerce")
                sdf=sdf.sort_values("_dt",ascending=False,na_position="last")
            display_df(sdf.drop(columns=["_dt"],errors="ignore"),250)
        else:
            st.caption("No live canonical sanctions rows returned; use Sanctions & Compliance for the full policy workspace.")
        if slinks:
            with st.expander("Sanctions entity links",expanded=False):
                display_df(pd.DataFrame(slinks),250)
        if not stories.empty:
            sanc=stories[
                stories.get("Story Category",pd.Series(index=stories.index,dtype=str)).fillna("").astype(str).str.contains(
                    r"sanction|compliance|regulatory",case=False,regex=True,na=False
                )
            ]
            if not sanc.empty:
                st.markdown("### Related developments")
                _render_trade_story_cards(sanc,20,key_prefix='news_sanctions')

    with tabs[4]:
        api_key=_newsdata_key()
        if not api_key:
            st.markdown("<div class='pc-hero'><div class='pc-hero-title'>NewsData.io connector ready</div><div class='pc-hero-copy'>Add <b>NEWSDATA_API_KEY</b> or grouped <b>[newsdata] api_key</b> to Streamlit Secrets to activate this discovery workspace.</div></div>",unsafe_allow_html=True)
        else:
            st.caption("Source: NewsData.io · cached for 10 minutes · discovery layer only · relevance-gated")
        presets={
            "Business & trade":"trade business company investment contract acquisition infrastructure logistics shipping freight",
            "Conflict & geopolitics":"conflict geopolitics war military security sanctions blockade border strait",
            "Maritime security":"ship vessel tanker attack drone missile seizure piracy maritime security",
            "Ports & terminals":"port terminal strike closure disruption congestion concession investment",
            "Logistics & supply chain":"logistics shipping freight supply chain disruption congestion delay shortage",
            "Energy & commodities":"oil gas LNG refinery pipeline energy commodity crude",
            "Rail & intermodal":"rail railway freight intermodal derailment strike disruption infrastructure",
            "Aviation & air cargo":"airport aviation air cargo disruption closure strike logistics",
            "Trade & sanctions":"trade sanctions export controls customs tariff shipping compliance",
            "Infrastructure & deals":"port terminal logistics railway acquisition investment concession contract capex",
            "Custom":""
        }
        c1,c2=st.columns([1.2,2.8])
        with c1: family=st.selectbox("Signal family",list(presets),key="newsdata_family")
        with c2: query=st.text_input("Search terms",value=presets[family],placeholder="Rotterdam port strike",key="newsdata_query")
        if st.button("Search open-source signals",type="primary",disabled=not bool(api_key),key="newsdata_go"):
            if len(query.strip())<3:
                st.warning("Enter a more specific search.")
            else:
                ndf,nerr=load_newsdata_articles(query.strip(),api_key,"en",10)
                st.session_state["newsdata_results"]=(ndf,nerr,query.strip())

        ndf,nerr,lastq=st.session_state.get("newsdata_results",(pd.DataFrame(),"",""))
        if not ndf.empty:
            ndf=ndf[ndf.apply(_news_trade_relevant,axis=1)].copy()
            if not ndf.empty:
                ndf["_title_key"]=ndf.get("title",pd.Series(index=ndf.index,dtype=str)).fillna("").astype(str).str.casefold().str.replace(r"[^a-z0-9]+"," ",regex=True).str.strip()
                ndf=ndf.drop_duplicates("_title_key").drop(columns=["_title_key"],errors="ignore")
        if nerr:
            st.warning(f"NewsData.io is temporarily unavailable. {nerr}")
        elif not ndf.empty:
            for _,row in ndf.head(50).iterrows():
                title=str(row.get("title","") or "Untitled")
                url=str(row.get("link","") or "")
                desc=str(row.get("description","") or "")
                source=str(row.get("source_name",row.get("source_id","")) or "")
                pub=str(row.get("pubDate","") or "")
                if url: st.markdown(f"**[{title}]({url})**")
                else: st.markdown(f"**{title}**")
                if source or pub: st.caption(" · ".join(x for x in [source,pub] if x))
                if desc: st.write(desc[:650] + ("…" if len(desc)>650 else ""))
                st.markdown("<span class='pc-chip'>OPEN SOURCE</span><span class='pc-chip'>UNVERIFIED SIGNAL</span>",unsafe_allow_html=True)
                st.markdown("---")
            st.caption("Corroborate and resolve entities before promotion into the canonical event model.")
        elif api_key:
            st.info("Choose a signal family or enter search terms.")


elif page=="Hormuz Monitor":
    header(
        "Strait of Hormuz Monitor",
        "AIS-derived traffic, tanker movements and energy-flow indicators. Counts are conservative lower bounds during wartime AIS disruption; the current month is partial."
    )
    monthly=TABLES.get(("Systems & Waterways","Hormuz Traffic Monthly"),pd.DataFrame()).copy()
    endpoints=TABLES.get(("Systems & Waterways","Hormuz API Endpoints"),pd.DataFrame()).copy()
    rates=TABLES.get(("Maritime","Tanker Rate Observations"),pd.DataFrame()).copy()

    if monthly.empty:
        st.info("Hormuz traffic snapshot is not available in this deployment.")
    else:
        for c in ["Crossings","Inbound","Outbound","Oil Tankers Outbound","Estimated Oil (M bbl)"]:
            if c in monthly.columns:
                monthly[c]=pd.to_numeric(monthly[c],errors="coerce")
        current=monthly.iloc[-1]
        complete=monthly[~monthly["Data Status"].astype(str).str.contains("partial",case=False,na=False)]
        prior=complete.iloc[-1] if not complete.empty else current
        m1,m2,m3,m4=st.columns(4)
        m1.metric(f"{current.get('Month','')} crossings",int(current.get("Crossings",0)),help="Current month; partial")
        m2.metric("Inbound / outbound",f"{int(current.get('Inbound',0))} / {int(current.get('Outbound',0))}",help="Current month; partial")
        m3.metric("Outbound oil tankers",int(current.get("Oil Tankers Outbound",0)),help="Current month; partial")
        m4.metric(f"Last complete month ({prior.get('Month','')})",int(prior.get("Crossings",0)))
        st.warning("Interpret direction and trend, not exact totals: AIS jamming and upstream coverage gaps can suppress observed traffic.")

        chart=monthly.set_index("Month")[["Crossings","Inbound","Outbound","Oil Tankers Outbound"]]
        st.markdown("### Monthly traffic snapshot")
        st.line_chart(chart)

        t1,t2,t3=st.tabs(["Monthly Data","Tanker Economics","API & Live Summary"])
        with t1:
            display_df(monthly,100)
            st.caption("Monitoring began 8 March 2026. September 2026 is an in-progress month and should not be compared with completed months.")
        with t2:
            if rates.empty:
                st.info("No tanker-rate observations loaded.")
            else:
                display_df(rates,100)
                st.caption("Rate observations are point-in-time market assessments, not a continuous freight index.")
        with t3:
            st.markdown("### Documented public endpoints")
            display_df(endpoints,100)
            st.markdown("[Open traffic statistics](https://hormuz.data-tracking.net/stats) · [Open API documentation](https://hormuz.data-tracking.net/api-docs)")
            if st.toggle("Load live 24-hour API summary",value=False,key="hormuz_live_summary"):
                payload,error=load_hormuz_api("summary","hours",24)
                if not error and payload is not None:
                    st.session_state["hormuz_last_good_summary"]=payload
                elif error and "hormuz_last_good_summary" in st.session_state:
                    payload=st.session_state["hormuz_last_good_summary"]
                    st.warning(f"Live refresh failed; showing the last successful session response. {error}")
                    error=""
                if error:
                    st.warning(f"Live API unavailable; the stored monthly snapshot remains usable. {error}")
                elif payload is not None:
                    st.caption("Live public API response · cached for 30 minutes · retained for this session")
                    st.json(payload,expanded=False)

elif page=="Corridors & Systems":
    header("Corridors & Systems","Canonical trade corridors, connected systems, waterways and route exposure in one network view.")
    with st.expander("Governance & authorities",expanded=False):
        render_system_governance()
    corridors=TABLES.get(("Infrastructure","Corridors"),pd.DataFrame()).copy()
    waterways=TABLES.get(("Systems & Waterways","Waterway Systems"),pd.DataFrame()).copy()
    tanker_corr=TABLES.get(("Maritime","Tanker Corridor Exposure"),pd.DataFrame()).copy()
    gl_corr=TABLES.get(("Maritime","Great Lakes Cargo Corridors"),pd.DataFrame()).copy()
    delivery=TABLES.get(("Defence & Shipbuilding","Sales & Delivery Routes"),pd.DataFrame()).copy()
    systems=TABLES.get(("Systems & Waterways","Systems"),pd.DataFrame()).copy()
    ct1,ct2,ct3,ct4=st.tabs(["Corridors","Connected systems","Waterways","Exposure & routes"])
    with ct1:
        cq=st.text_input("Find corridor",placeholder="Middle Corridor, Great Lakes, Hormuz, Arctic...",key="corridor_search")
        display_df(_contains_any(corridors,[cq]) if cq.strip() and not corridors.empty else corridors,250)
    with ct3:
        wq=st.text_input("Find waterway",placeholder="Suez, Panama, Bosporus, St Lawrence...",key="waterway_search")
        display_df(_contains_any(waterways,[wq]) if wq.strip() and not waterways.empty else waterways,250)
    with ct4:
        et1,et2,et3=st.tabs(["Tanker exposure","Great Lakes cargo","Defence delivery routes"])
        with et1: display_df(tanker_corr,250)
        with et2:
            display_df(gl_corr,250)
            if not gl_corr.empty:
                gidx=st.selectbox("Map Great Lakes corridor",range(len(gl_corr)),
                                  format_func=lambda i:" · ".join(str(v) for v in gl_corr.iloc[i].tolist()[:3] if str(v).strip() and str(v).lower()!="nan")[:140],
                                  key="great_lakes_corridor_map_pick")
                grow=gl_corr.iloc[gidx]
                texts=[grow.get(c,"") for c in gl_corr.columns]
                gpts=route_port_points(*texts)
                render_route_port_map(gpts,"Great Lakes corridor ports")
        with et3: display_df(delivery,250)
    with ct2:
        if systems.empty:
            st.info("Systems workbook not available.")
        else:
            systems=systems.reset_index(drop=True)
            requested_system=st.session_state.pop("system_pick_id",None)
            default_system=0
            if requested_system and "System ID" in systems.columns:
                mi=systems.index[systems["System ID"].astype(str).eq(str(requested_system))].tolist()
                if mi: default_system=int(mi[0])

            names=systems["System"].tolist()
            if requested_system:
                st.session_state["system_select_name"]=names[default_system]
            else:
                current_system=st.session_state.get("system_select_name",names[default_system])
                if not isinstance(current_system,str) or current_system not in names:
                    st.session_state["system_select_name"]=names[default_system]

            name=st.selectbox("System",names,key="system_select_name")
            srow=systems[systems["System"]==name].iloc[0]; sid=srow["System ID"]
            st.markdown(f"## {name}")
            st.caption(f"{srow.get('Geography','')} · {srow.get('Archetype','')}")
            se=TABLES.get(("Systems & Waterways","System Entities"),pd.DataFrame())
            sl=TABLES.get(("Systems & Waterways","System Links"),pd.DataFrame())
            sf=TABLES.get(("Systems & Waterways","Facilities"),pd.DataFrame())
            si=TABLES.get(("Systems & Waterways","Network Interfaces"),pd.DataFrame())
            sube=se[se["System ID"].astype(str).eq(str(sid))] if "System ID" in se.columns else pd.DataFrame()
            subs=sl[sl["System ID"].astype(str).eq(str(sid))] if "System ID" in sl.columns else pd.DataFrame()
            subf=sf[sf["System ID"].astype(str).eq(str(sid))] if "System ID" in sf.columns else pd.DataFrame()
            subi=si[si["System ID"].astype(str).eq(str(sid))] if "System ID" in si.columns else pd.DataFrame()
            ev,loc,chains=event_bundle_for_entities(system_ids=[sid])
            if not ev.empty: render_event_map(ev,loc,"System events")
            tabs=st.tabs(["Entities","Relationships","Facilities","Interfaces","Events"])
            with tabs[0]: display_df(sube,200)
            with tabs[1]:
                for ri,(_,r) in enumerate(subs.iterrows()):
                    src_id=str(r.get("Source Entity ID","")).strip()
                    tgt_id=str(r.get("Target Entity ID","")).strip()
                    rel_txt=pretty_relationship(r.get("Relationship",""))
                    st.markdown(
                        f"<div class='pc-rel'><b>{label(src_id)}</b> → {rel_txt} → <b>{label(tgt_id)}</b></div>",
                        unsafe_allow_html=True
                    )
                    render_relationship_actions(src_id,tgt_id,f"system_{sid}_{ri}")
            with tabs[2]: display_df(subf,200)
            with tabs[3]: display_df(subi,200)
            with tabs[4]:
                render_event_cards(ev,50)
                if not chains.empty: display_df(chains,100)


elif page=="Maritime Security":
    header("Maritime Security","Official confirmation, vessel-linked incidents, theatre baselines, operational measures and chokepoint governance in one maritime-security workspace.")
    inc=official_maritime_incidents()
    theatre=TABLES.get(("Official Maritime Security","Theatre Baselines"),pd.DataFrame()).copy()
    measures=TABLES.get(("Official Maritime Security","Operational Measures"),pd.DataFrame()).copy()
    governance=TABLES.get(("Official Maritime Security","Chokepoint Governance"),pd.DataFrame()).copy()

    a,b,c,d=st.columns(4)
    a.metric("Confirmed incidents",len(inc))
    b.metric("Named vessels",inc["Vessel"].nunique() if not inc.empty and "Vessel" in inc else 0)
    linked=0
    if not inc.empty:
        linked=sum(1 for _,r in inc.iterrows() if canonical_vessel_id_for_official_incident(r.get("IMO",""),r.get("Vessel","")))
    c.metric("Vessel-linked records",linked)
    d.metric("Theatre baselines",len(theatre))

    q=st.text_input("Search maritime security",placeholder="Hercules Star, IMO 9916135, Hormuz, Red Sea, Black Sea...")
    if q and not inc.empty:
        inc=_contains_any(inc,[q])

    tabs=st.tabs(["Vessel Incidents","Theatre Baselines","Operational Measures","Chokepoints"])
    with tabs[0]:
        st.caption("Every confirmed record resolves to the vessel profile. The IMO register is a confirmation layer; the vessel remains the canonical intelligence object.")
        render_official_security_records(inc,"maritime_security")
    with tabs[1]:
        display_df(theatre,360)
    with tabs[2]:
        display_df(measures,360)
    with tabs[3]:
        display_df(governance,360)

elif page=="Reference & Benchmarks":
    header("Reference & Benchmarks","Historical accident distributions, port/corridor reference data and market-transmission context for interpreting live intelligence.")
    tabs=st.tabs(["Accident Types","Ship Types","Human Consequences","Port Reference","Trade Connectivity"])
    with tabs[0]: display_df(TABLES.get(("Risk Benchmarks","Accident Casualty Type"),pd.DataFrame()),320)
    with tabs[1]: display_df(TABLES.get(("Risk Benchmarks","Accident Ship Type"),pd.DataFrame()),320)
    with tabs[2]: display_df(TABLES.get(("Risk Benchmarks","Human Consequences"),pd.DataFrame()),320)
    with tabs[3]: display_df(TABLES.get(("Global Ports Reference","Top Throughput Ports"),pd.DataFrame()),420)
    with tabs[4]: display_df(TABLES.get(("Trade Connectivity Reference","Priority Corridor Seeds"),pd.DataFrame()),420)

elif page=="Reference Library":
    header("Reference Library","Research-scale datasets are catalogued separately from live events and canonical entities; large source tables are lazy-loaded from external_data.")
    registries=[]
    for key in [("Global Ports Reference","Source Registry"),("Trade Connectivity Reference","Reference Datasets"),("Risk Benchmarks","Source Register")]:
        d=TABLES.get(key,pd.DataFrame())
        if not d.empty: registries.append(d)
    if registries:
        display_df(pd.concat(registries,ignore_index=True,sort=False),520)
    else:
        st.caption("Reference registries not loaded.")

elif page=="Data":
    header("Data Explorer","Raw evidence and debugging tables. Internal IDs remain hidden unless explicitly enabled.")
    wb_label=st.selectbox("Workbook",list(WORKBOOKS.keys()))
    sheet=st.selectbox("Sheet",workbook_sheets(wb_label))
    df=load_sheet(wb_label,sheet)
    q=st.text_input("Filter this table")
    if q: df=_contains_any(df,[q])
    show_debug_ids=st.toggle("Show internal database IDs",value=False)
    display_df(df,600,show_ids=show_debug_ids)

st.sidebar.markdown("---")
st.sidebar.caption(f"{len(TABLES):,} tables loaded · {RELEASE_NAME}")
