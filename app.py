from pathlib import Path
import sys
import os
import re
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
from pc_trade_system import render_energy_industry, render_trade_flows_supply, render_country_macro, render_market_instruments
try:
    from pc_auth import require_login
except Exception:
    require_login = None

APP_TITLE = "P&C Trade System"
APP_VERSION = "v3.3.7-compact-multimodal-ui"
RELEASE_NAME = "Global Trade-System Intelligence Graph · Legacy Excel + Research Reference + Supabase Bridge"
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
    "Sources": "10_sources_evidence.xlsx",
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

@st.cache_data(show_spinner=False, ttl=3600)
def load_newsdata_articles(query, api_key, language="en", size=10):
    """NewsData.io discovery feed. Results remain open-source signals until corroborated."""
    if not api_key:
        return pd.DataFrame(), "NewsData.io API key not configured"
    params={"apikey":api_key,"q":query,"language":language,"size":min(int(size),10)}
    try:
        req=Request(NEWSDATA_LATEST_URL+"?"+urlencode(params),headers={"User-Agent":"PC-Trade-System/2.9"})
        with urlopen(req,timeout=12) as response:
            payload=json.loads(response.read().decode("utf-8"))
        if str(payload.get("status","")).lower() not in {"success",""}:
            return pd.DataFrame(), str(payload.get("message") or "NewsData request failed")
        return pd.DataFrame(payload.get("results") or []), ""
    except HTTPError as exc:
        return pd.DataFrame(), f"HTTP {exc.code}"
    except (URLError,TimeoutError,ValueError,OSError) as exc:
        return pd.DataFrame(), str(exc)

# ---------- optional live transport feeds ----------
def _secret(name, default=""):
    try:
        return str(st.secrets.get(name, default) or default)
    except Exception:
        return str(os.environ.get(name, default) or default)

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

def unified_ports_with_reference(ports):
    """Canonical ports plus geocoded reference-only seeds, so the explorer starts with port name + location and can be enriched later."""
    canonical=enrich_ports_from_reference(ports)
    ref=global_port_reference_view()
    if ref.empty: return canonical
    existing=set()
    if not canonical.empty:
        for _,r in canonical.iterrows():
            existing.add((_port_match_key(r.get("Port / Facility","")),_port_match_key(r.get("Country",""))))
    rows=[]
    for _,r in ref.iterrows():
        key=(_port_match_key(r.get("Port Name","")),_port_match_key(r.get("Country Name","")))
        if key in existing: continue
        rows.append({
            "Port ID":f"REF_{r.get('id','')}","Port / Facility":r.get("Port Name",""),"Country":r.get("Country Name",""),
            "Latitude":r.get("Latitude",""),"Longitude":r.get("Longitude",""),"Operator Company ID":"","Operator":"",
            "Facility Type":"Reference port seed","Key Role":"Global trade / port reference",
            "Coverage Note":"Geocoded reference seed — canonical operator, terminal and ownership enrichment pending.",
            "Source ID":"GLOBAL_PORT_REFERENCE","Geo Source":"Global Port Reference"
        })
    if rows:
        canonical=pd.concat([canonical,pd.DataFrame(rows)],ignore_index=True,sort=False)
    return canonical

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
        "Url":"Source","Urls":"Sources","URL":"Source","URLs":"Sources",
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
            return pretty_relationship(s) if cstr.lower().replace("_"," ") in {"relationship","link type","relationship type"} else pretty_enum(s)
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
    cfg={}
    for c in show.columns:
        if "url" in str(c).lower():
            cfg[c]=st.column_config.LinkColumn(str(c).replace("URLs","Sources").replace("URL","Source"),display_text="Open")
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

def label(x):
    s=str(x).strip(); return LABELS.get(s,s)

def pretty_enum(v):
    """Turn implementation taxonomies/codes into ordinary English for the UI."""
    s=str(v).strip()
    if not s or s.lower()=="nan":
        return ""
    if s.startswith("http://") or s.startswith("https://"):
        return s
    if s in LABELS:
        return LABELS[s]

    # Common booleans / compact status values.
    exact={
        "Y":"Yes","N":"No","YES":"Yes","NO":"No","TRUE":"Yes","FALSE":"No",
        "UNK":"Unknown","UNKNOWN":"Unknown","N/A":"Not applicable","NA":"Not applicable",
        "TBD":"To be determined","TBC":"To be confirmed",
    }
    if s.upper() in exact:
        return exact[s.upper()]

    # Translate code-like snake_case / kebab-case / ALL_CAPS values while leaving prose alone.
    code_like=("_" in s or ("-" in s and " " not in s) or (s.isupper() and len(s)>3))
    if code_like and not re.fullmatch(r"[A-Z]{2,4}-?\d+",s):
        x=s.replace("_"," ").replace("-"," ")
        x=re.sub(r"\s+"," ",x).strip()
        keep={"MRO","JV","UAE","US","USA","UK","EU","IMO","MMSI","AIS","OPV","LNG","TEU","CG","SAR","RFI","RFP","HS","UN","OFAC","NATO"}
        words=[]
        for w in x.split():
            wu=w.upper()
            words.append(wu if wu in keep else w.lower())
        if words:
            words[0]=words[0] if words[0] in keep else words[0].capitalize()
        return " ".join(words)
    return s

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
    skip={"Data Dictionary","Runtime Table Crosswalk","Research Queue","Overview","Sources","Source Feeds"}
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
    ownership_terms=("OWNS","PARENT","CONTROLS","CONTROLLED","SUBSIDIARY","JV_PARTNER","OWNS_51","OWNS_49")
    frontier={str(entity_id)}
    for _ in range(max_depth):
        nxt=set()
        for src in frontier:
            rows=rel[rel.get("Source Entity",pd.Series(dtype=str)).astype(str).eq(src)]
            for _,r in rows.iterrows():
                relationship=str(r.get("Relationship","")).upper()
                tgt=str(r.get("Target Entity","")).strip()
                if tgt and any(term in relationship for term in ownership_terms):
                    if tgt not in scope:
                        scope.add(tgt); nxt.add(tgt)
            # Group operating-ecosystem links are deliberately traversable in
            # reverse so a Noatum Maritime profile can surface SAFEEN service
            # craft without claiming those sister businesses are subsidiaries.
            inbound=rel[rel.get("Target Entity",pd.Series(dtype=str)).astype(str).eq(src)]
            for _,r in inbound.iterrows():
                relationship=str(r.get("Relationship","")).upper()
                source_entity=str(r.get("Source Entity","")).strip()
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

def build_company_profile(entity_id, entity_name):
    prof={}
    prof["company_id"]=entity_id
    prof["name"]=entity_name
    scope_ids=company_scope_ids(entity_id)
    investment_ids=company_investment_exposure_ids(scope_ids)
    asset_scope_ids=set(scope_ids) | set(investment_ids)

    prof["scope_ids"]=scope_ids
    prof["scope_names"]=company_scope_names(scope_ids)
    prof["investment_ids"]=investment_ids
    prof["investment_names"]=company_scope_names(investment_ids)
    prof["asset_scope_ids"]=asset_scope_ids

    # Corporate relationships
    rel=TABLES.get(("Core Entities","Relationships"),pd.DataFrame())
    if not rel.empty:
        m=pd.Series(False,index=rel.index)
        if "Source Entity" in rel.columns: m |= rel["Source Entity"].astype(str).isin(scope_ids)
        if "Target Entity" in rel.columns: m |= rel["Target Entity"].astype(str).isin(scope_ids)
        prof["relationships"]=rel[m].copy()
    else: prof["relationships"]=pd.DataFrame()

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
    if not vr.empty and "Company ID" in vr.columns:
        vrs=vr[vr["Company ID"].astype(str).isin(scope_ids)].copy()
        prof["vessel_relationships"]=vrs
        if "Vessel ID" in vrs.columns: related_vessel_ids.update(vrs["Vessel ID"].astype(str).tolist())
    else: prof["vessel_relationships"]=pd.DataFrame()
    if not v.empty and related_vessel_ids and "Vessel ID" in v.columns: vm |= v["Vessel ID"].astype(str).isin(related_vessel_ids)
    prof["maritime_vessels"]=v[vm].copy() if not v.empty else pd.DataFrame()

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

    # Infrastructure assets / facilities directly owned by company
    assets=TABLES.get(("Infrastructure","Assets"),pd.DataFrame())
    prof["assets"]=_match_any(assets,["Company ID"],scope_ids)
    infra_fac=TABLES.get(("Infrastructure","Facilities"),pd.DataFrame())
    prof["infrastructure_facilities"]=_match_any(infra_fac,["Owner / Operator Company ID"],scope_ids)

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

    # direct terminal operator rows
    tm=pd.Series(False,index=pt.index) if not pt.empty else pd.Series(dtype=bool)
    if not pt.empty:
        if "Primary Operator Company ID" in pt.columns:
            tm |= pt["Primary Operator Company ID"].astype(str).isin(asset_scope_ids)
        if "Operator / Network" in pt.columns:
            for nm in company_scope_names(asset_scope_ids):
                tm |= pt["Operator / Network"].astype(str).str.contains(re.escape(nm),case=False,na=False)
    direct_terms=pt[tm].copy() if not pt.empty else pd.DataFrame()

    # direct port operator/authority rows.
    # Some networks (e.g. Associated British Ports) are modelled at port level rather than terminal level.
    direct_ports=pd.DataFrame()
    if not ports.empty:
        pm=pd.Series(False,index=ports.index)
        if "Operator Company ID" in ports.columns:
            pm |= ports["Operator Company ID"].astype(str).isin(asset_scope_ids)
        if "Operator" in ports.columns:
            for nm in company_scope_names(asset_scope_ids):
                pm |= ports["Operator"].astype(str).str.contains(re.escape(nm),case=False,na=False)
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
        prof["port_terminals"]=pd.concat([direct_terms,extra_terms],ignore_index=True).drop_duplicates()
    else:
        prof["port_terminals"]=direct_terms

    # parent ports + ports directly administered/operated by the company/network
    port_ids=set()
    if not prof["port_terminals"].empty and "Port ID" in prof["port_terminals"].columns:
        port_ids.update(prof["port_terminals"]["Port ID"].astype(str).tolist())

    terminal_parent_ports=ports[ports["Port ID"].astype(str).isin(port_ids)].copy() if (not ports.empty and port_ids and "Port ID" in ports.columns) else pd.DataFrame()
    port_frames=[x for x in [direct_ports,terminal_parent_ports] if isinstance(x,pd.DataFrame) and not x.empty]
    if port_frames:
        prof["ports"]=pd.concat(port_frames,ignore_index=True).drop_duplicates()
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
        src_name=label(src)
        tgt_name=label(tgt)

        st.markdown(
            f"<div class='pc-rel'><b>{src_name}</b> → {rel} → <b>{tgt_name}</b></div>",
            unsafe_allow_html=True
        )

        render_relationship_actions(src,tgt,f"company_{entity_id}_{i}",current_entity_id=entity_id)

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
    eid=str(event_id or "")
    out=[]
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

        # Build a trade-facing event card: incident first, consequence second.
        card = [
            "<div class='pc-card'>",
            f"<div class='pc-search-details' style='color:#D8B45A; text-transform:uppercase; letter-spacing:.08em;'>{' · '.join(meta)}</div>",
            f"<div class='pc-big' style='margin-top:10px;'>{title}</div>",
        ]
        if description and description.lower() != "nan":
            card.append(f"<div class='pc-search-details' style='margin-top:10px;'>{description}</div>")
        if operational and operational.lower() != "nan":
            card.append(
                f"<div style='margin-top:12px;'><b>Operational impact:</b> {operational}</div>"
            )
        if commercial and commercial.lower() != "nan":
            card.append(
                f"<div style='margin-top:8px; padding-top:8px; border-top:1px solid #33414C;'>"
                f"<b style='color:#D8B45A;'>Trade / commercial impact:</b> {commercial}</div>"
            )
        card.append("</div>")
        st.markdown("".join(card), unsafe_allow_html=True)

        card_prefix = f"eventblock_{render_scope}_card_{idx}"

        # Commercially relevant linked network sits immediately beneath the event card.
        render_event_associations(eid, key_prefix=card_prefix)

        url = str(row.get("Primary Source URL", "")).strip()
        if url.startswith("http"):
            st.link_button("Open source ↗", url, key=f"{card_prefix}_{eid}_source")

        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)


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

def render_company_profile(entity_id, entity_name):
    prof=build_company_profile(entity_id,entity_name)
    rec=company_record(entity_id)

    # Top summary
    st.markdown(f"## {entity_name}")
    if rec is not None:
        summary=[]
        for c in ["Entity Type","Industrial Model","HQ Country","Country / Geography","Business Segments","Markets","Ownership","Ownership / Role Note","Scale / Network Notes"]:
            if c in rec.index and str(rec.get(c,"")).strip():
                summary.append(f"**{c}:** {rec.get(c)}")
        if summary: st.markdown("  \n".join(summary[:6]))

    if len(prof.get("scope_ids",[]))>1:
        group_names=[x for x in prof.get("scope_names",[]) if x != entity_name]
        if group_names:
            st.markdown("**Included group / controlled entities:** " + " · ".join(group_names))

    investment_names=[x for x in prof.get("investment_names",[]) if x and x != entity_name]
    if investment_names:
        st.markdown("**Portfolio / investment exposure:** " + " · ".join(investment_names))

    c1,c2,c3,c4,c5,c6,c7=st.columns(7)
    c1.metric("Terminals",profile_count(prof,"port_terminals"))
    c2.metric("Ports",profile_count(prof,"ports"))
    c3.metric("Shipyards",profile_count(prof,"yards"))
    total_v=profile_count(prof,"defence_vessels")+profile_count(prof,"maritime_vessels")
    c4.metric("Linked vessels",total_v)
    c5.metric("Programmes",profile_count(prof,"programmes"))
    c6.metric("Events",profile_count(prof,"events"))
    c7.metric("News",profile_count(prof,"news")+profile_count(prof,"announcements")+profile_count(prof,"port_news")+profile_count(prof,"strategic_news"))

    company_view=st.selectbox(
        "Company section",
        ["Profile & Assets","Investments","Financials","Share Price","Security & Risk"],
        key=f"company_section_{entity_id}"
    )
    if company_view=="Investments":
        st.markdown("### Investment intelligence")
        render_investment_dashboard(company_id=entity_id)
        return
    if company_view=="Financials":
        render_company_financials(entity_id)
        return
    if company_view=="Share Price":
        st.markdown("### Share-price intelligence")
        render_share_price_history(entity_id)
        return
    if company_view=="Security & Risk":
        st.markdown("### Security & risk")
        render_company_security_risk(entity_id,entity_name)
        return

    tabs=st.tabs(["Overview","Port Assets","Shipyards & Facilities","Vessels","Programmes & Contracts","Sales Routes","Events & Impact","News","Relationships & Systems","Policy & Compliance","Evidence"])
    with tabs[0]:
        # Visual intelligence first
        if not prof["port_terminals"].empty or not prof["ports"].empty:
            render_port_visuals(prof)
        if not prof["yards"].empty:
            render_shipyard_visuals(prof)
        render_market_visuals(entity_id)
        if not prof["events"].empty:
            render_event_map(prof["events"],prof["event_locations"],"Linked events & announced activity")

        if not prof["ports"].empty:
            st.markdown("### Ports")
            show_named_list(prof["ports"],"Port / Facility",["Country","Operator","Facility Type","Key Role"])

        if not prof["port_terminals"].empty:
            st.markdown("### Port terminals / facilities")
            t=prof["port_terminals"].copy()
            show_named_list(t,"Terminal / Facility",["Parent Port","Country","City / Area","Primary Operator","Status","Ownership / Structure"])
        if not prof["yards"].empty:
            st.markdown("### Shipyards")
            y=prof["yards"].copy()
            if "Company Entity ID" in y.columns: y["Operating Company"]=y["Company Entity ID"].map(label)
            show_named_list(y,"Shipyard",["Operating Company","Country","Yard Model","Current / Representative Work"])
        if not prof["programmes"].empty:
            st.markdown("### Active / relevant programmes")
            show_named_list(prof["programmes"],"Programme",["Customer","Platform / Class","Status","Build / Sales Route"])

        # A profile should never hide relevant linked reporting merely because the
        # company is connected through a vessel, consortium or project entity.
        latest_frames=[]
        if not prof["news"].empty:
            x=prof["news"].copy()
            x["_source_kind"]="News"
            latest_frames.append(x)
        if not prof["strategic_news"].empty:
            x=prof["strategic_news"].copy()
            x["_source_kind"]="Strategic event"
            latest_frames.append(x)
        if latest_frames:
            latest=pd.concat(latest_frames,ignore_index=True,sort=False)
            date_col="Published Date" if "Published Date" in latest.columns else None
            if date_col:
                latest["_dt"]=pd.to_datetime(latest[date_col],errors="coerce")
                latest=latest.sort_values("_dt",ascending=False)
            st.markdown("### Latest linked reporting")
            show_named_list(latest.head(5),"Headline",["Published Date","Publisher","Event Type"],source_col="URL",max_items=5)

        if prof["port_terminals"].empty and prof["ports"].empty and prof["yards"].empty and prof["programmes"].empty:
            st.info("No mapped asset, shipyard or programme profile yet for this entity.")

    with tabs[1]:
        st.markdown("### Terminals / port facilities")
        if not prof["port_terminals"].empty:
            t=prof["port_terminals"].copy()
            display_df(t,250)
        else:
            st.info("No terminal assets currently linked.")
        if not prof["ports"].empty:
            st.markdown("### Parent ports")
            display_df(prof["ports"],150)
        if not prof["port_ownership"].empty:
            st.markdown("### Ownership / JV / operating-control relationships")
            display_df(prof["port_ownership"],250)
        if not prof["port_berths"].empty:
            st.markdown("### Berths / marine interfaces")
            display_df(prof["port_berths"],250)
        if not prof["port_equipment"].empty:
            st.markdown("### Terminal equipment")
            display_df(prof["port_equipment"],300)

    with tabs[2]:
        st.markdown("### Shipyards")
        y=prof["yards"].copy()
        if "Company Entity ID" in y.columns: y["Operating Company"]=y["Company Entity ID"].map(label)
        show_named_list(y,"Shipyard",["Operating Company","Location","Country","Yard Model","Status"])
        if not prof["yard_capabilities"].empty:
            st.markdown("### Yard capabilities")
            cap=prof["yard_capabilities"].copy()
            if "Yard ID" in cap.columns: cap["Shipyard"]=cap["Yard ID"].map(label)
            display_df(cap,100)
        if not prof["yard_facilities"].empty:
            st.markdown("### Yard facilities")
            fac=prof["yard_facilities"].copy()
            if "Yard ID" in fac.columns: fac["Shipyard"]=fac["Yard ID"].map(label)
            display_df(fac,100)
        if not prof["infrastructure_facilities"].empty:
            st.markdown("### Other infrastructure facilities")
            display_df(prof["infrastructure_facilities"],100)

    with tabs[3]:
        if not prof["defence_vessels"].empty:
            st.markdown("### Defence / Coast Guard / Government vessels")
            dv=prof["defence_vessels"].copy()
            if "Build Yard ID" in dv.columns: dv["Shipyard"]=dv["Build Yard ID"].map(label)
            display_df(dv,150)
        if not prof["maritime_vessels"].empty:
            st.markdown("### Commercial / maritime vessels")
            display_df(prof["maritime_vessels"],250)
        if not prof["vessel_build_records"].empty:
            st.markdown("### Vessel build records tied to these yards")
            display_df(prof["vessel_build_records"],150)
        if prof["defence_vessels"].empty and prof["maritime_vessels"].empty and prof["vessel_build_records"].empty:
            st.info("No vessel records currently linked to this entity. This is now shown explicitly rather than hidden in other tables.")

    with tabs[4]:
        st.markdown("### Programmes")
        pg=prof["programmes"].copy()
        if not pg.empty and "Prime / Lead Entity ID" in pg.columns:
            pg["Prime / Lead"]=pg["Prime / Lead Entity ID"].map(label)
        display_df(pg,150)
        if not prof["programme_participants"].empty:
            st.markdown("### Programme roles")
            display_df(prof["programme_participants"],100)
        st.markdown("### Contracts")
        display_df(prof["contracts"],150)

    with tabs[5]:
        display_df(prof["sales_routes"],150)

    with tabs[6]:
        render_event_map(prof["events"],prof["event_locations"],"Event / activity map")
        st.markdown("### Linked events")
        render_event_cards(prof["events"],50)
        if not prof["impact_chains"].empty:
            st.markdown("### Impact propagation")
            display_df(prof["impact_chains"],100)

        if not prof["events"].empty:
            event_ids=set(prof["events"]["Event ID"].astype(str).tolist())
            eal=TABLES.get(("Events & Hazards","Event Asset Links"),pd.DataFrame())
            if not eal.empty and "Event ID" in eal.columns:
                eal=eal[eal["Event ID"].astype(str).isin(event_ids)]
                if not eal.empty:
                    st.markdown("### Affected / connected assets")
                    render_linked_objects(eal,"Asset Type","Asset ID","Asset","Relationship","Confidence",100)

    with tabs[7]:
        if not prof["announcements"].empty:
            st.markdown("### Announced activity")
            show_named_list(prof["announcements"],"Headline",["Date","Event Type"])
        if not prof["news"].empty:
            st.markdown("### News")
            show_named_list(prof["news"],"Headline",["Published Date","Publisher","Country","Event Type"],source_col="URL")
        if not prof["port_news"].empty:
            st.markdown("### Port / terminal news")
            show_named_list(prof["port_news"],"Headline",["Date","Port","Terminal","Event Type"],source_col="URL")
        if not prof["strategic_news"].empty:
            st.markdown("### Strategic event / incident coverage")
            show_named_list(
                prof["strategic_news"],
                "Headline",
                ["Published Date","Publisher","Event Type","Region"],
                source_col="URL",
                max_items=100
            )
        if prof["announcements"].empty and prof["news"].empty and prof["port_news"].empty and prof["strategic_news"].empty:
            st.info("No linked news, announcements or canonical event coverage.")

    with tabs[8]:
        st.markdown("### Corporate relationships")
        readable_relationships(prof["relationships"],entity_id)
        if not prof["systems"].empty:
            st.markdown("### Trade systems / corridors")
            display_df(prof["systems"],50)

    with tabs[9]:
        if not prof["trade_agreements"].empty:
            st.markdown("### Trade agreements / market-access exposure")
            display_df(prof["trade_agreements"],100)
        if not prof["agreement_company_links"].empty:
            st.markdown("### Company exposure")
            display_df(prof["agreement_company_links"],100)
        if not prof["agreement_asset_links"].empty:
            st.markdown("### Asset / corridor exposure")
            display_df(prof["agreement_asset_links"],100)
        if not prof["sanctions_links"].empty:
            st.markdown("### Sanctions / designation-linked exposure")
            st.caption("A linked company may be an owner, operator or manager named in a designation record; this does not automatically mean every linked party is itself separately designated.")
            display_df(prof["sanctions_links"],100)
        if not prof["sanctions_designations"].empty:
            st.markdown("### Related government designation records")
            display_df(humanize_sanctions_df(prof["sanctions_designations"]),100)
        if prof["trade_agreements"].empty and prof["sanctions_designations"].empty and prof["sanctions_links"].empty:
            st.info("No direct trade-policy or sanctions link has been mapped for this entity yet.")

    with tabs[10]:
        if not prof["assets"].empty:
            st.markdown("### Direct assets")
            display_df(prof["assets"],100)
        rels=related_tables(entity_id,entity_name)
        for (wb_label,sheet),sub in rels:
            if sheet in {"Sources","Overview","Companies","Defence Companies","Shipyards","Programmes","Contracts","Sample Vessels","Announcements","News Registry","Relationships"}:
                continue
            with st.expander(f"{sheet} · {len(sub)} record(s)"):
                display_df(sub,100)

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
    et=str(entity_type).lower()
    eid=str(entity_id).strip()
    name=str(entity_name).strip()

    if "port" in et or eid.startswith("PORT"):
        return ("Ports","port_pick_id",eid)
    if "terminal" in et or eid.startswith("TERM"):
        # A terminal opens the Ports page; Ports will resolve its parent port.
        return ("Ports","terminal_pick_id",eid)
    if "shipyard" in et or eid.startswith("YARD"):
        return ("Shipyards","yard_pick_id",eid)
    if "company" in et or eid.startswith("COMP"):
        return ("Companies","company_pick_id",eid)
    if "system" in et or eid.startswith("SYS") or eid.startswith("CORR"):
        return ("Corridors & Systems","system_pick_id",eid)
    if "vessel" in et or eid.startswith("VESSEL") or eid.startswith("VES"):
        return ("Vessels","vessel_pick_id",eid)
    return (None,None,None)

def render_relationship_actions(source_id, target_id, row_key, current_entity_id=None):
    """Show contextual drill-down buttons beneath a readable relationship line.

    Only endpoints with a canonical destination page are rendered. Terminal links route
    through Ports and resolve the parent port there. This keeps relationship chains
    readable while making the graph directly navigable.
    """
    actions=[]
    seen=set()
    for endpoint_id in [source_id,target_id]:
        eid=str(endpoint_id).strip()
        if not eid or eid in seen or (current_entity_id and eid==str(current_entity_id)):
            continue
        seen.add(eid)
        name=label(eid)
        page,key,route_id=object_route('',eid,name)
        if not page:
            continue
        if page=='Companies': kind='Company'
        elif page=='Ports' and eid.startswith('TERM'): kind='Terminal'
        elif page=='Ports': kind='Port'
        elif page=='Vessels': kind='Vessel'
        elif page=='Shipyards': kind='Shipyard'
        elif page=='Corridors & Systems': kind='System'
        else: kind='Entity'
        actions.append((f"View {kind}: {name}",page,key,route_id,name,eid))

    if actions:
        cols=st.columns(min(len(actions),3))
        for j,(caption,page,key,route_id,name,eid) in enumerate(actions):
            with cols[j % len(cols)]:
                if st.button(caption,key=f"rel_action_{row_key}_{j}_{eid}",use_container_width=True):
                    request_nav(page,key,route_id,name)
                    st.rerun()


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

    with tabs[3]:
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

    with tabs[4]:
        render_vessel_incident_cards(events,news)

    with tabs[5]:
        if not news.empty:
            show_named_list(news,"Headline",["Published Date","Publisher","Region","Event Type"],source_col="URL",max_items=100)
        else:
            st.info("No linked news reporting.")

    with tabs[6]:
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
    b.metric("Security / disruption events",len(ev))
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
    feeds=TABLES.get(("Sources","Source Feeds"),pd.DataFrame()).copy()
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

def render_marsec_workspace():
    events=TABLES.get(("Events & Hazards","Events"),pd.DataFrame()).copy()
    feeds=TABLES.get(("Sources","Source Feeds"),pd.DataFrame()).copy()
    if not feeds.empty:
        sec=feeds[feeds.get("Feed ID",pd.Series(dtype=str)).astype(str).str.startswith("FEED_SEC")].copy()
        if not sec.empty:
            st.markdown("### Official MARSEC collection")
            display_df(sec[[c for c in ["Source Name","Coverage","Default Event Families","Priority","Active","Last Checked","Notes"] if c in sec.columns]],100)
    if events.empty:
        st.info("No event data loaded."); return
    mask=events.get("Event Family",pd.Series(index=events.index,dtype=str)).astype(str).str.contains("Maritime|Security|Conflict|Port",case=False,regex=True,na=False)
    marsec=events[mask].copy()
    c1,c2=st.columns(2)
    with c1:
        families=sorted([x for x in marsec.get("Event Type",pd.Series(dtype=str)).astype(str).unique() if x])
        et=st.selectbox("Incident type",["All"]+families,key="marsec_type_filter")
    with c2:
        countries=sorted([x for x in marsec.get("Country / Countries",pd.Series(dtype=str)).astype(str).unique() if x])
        country=st.selectbox("Country / area",["All"]+countries,key="marsec_country_filter")
    if et!="All": marsec=marsec[marsec["Event Type"].astype(str).eq(et)]
    if country!="All": marsec=marsec[marsec["Country / Countries"].astype(str).eq(country)]
    st.markdown("### Incident feed")
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
    """Return commercial/operational alerts, excluding routine corporate development."""
    events=TABLES.get(("Events & Hazards","Events"),pd.DataFrame()).copy()
    if events.empty:
        return events
    cols=[c for c in ["Event Family","Event Type","Title","Description","Operational Impact","Trade / Commercial Impact"] if c in events.columns]
    blob=pd.Series("",index=events.index,dtype="string")
    for c in cols:
        blob=blob.str.cat(events[c].fillna("").astype(str),sep=" ")
    include=r"strike|labour|weather|typhoon|cyclone|hurricane|flood|earthquake|wildfire|storm|closure|outage|disruption|grounding|collision|allision|capsize|sinking|fire|explosion|attack|missile|drone|piracy|seizure|interdiction|sanction|customs|tariff|border|canal|channel|low water|cyber|fraud|smuggl|crime"
    corporate=r"new terminal|terminal opening|commissioning|new crane|crane order|equipment order|vessel order|fleet order|acquisition|investment|capex announcement|earnings|dividend|share buyback|service launch|office opening"
    inc=blob.str.contains(include,case=False,regex=True,na=False)
    corp=blob.str.contains(corporate,case=False,regex=True,na=False)
    # A corporate story can still become an alert only when it independently contains disruption language.
    view=events[inc & (~corp | blob.str.contains(r"closure|outage|strike|attack|weather|fire|explosion|disruption|sanction",case=False,regex=True,na=False))].copy()
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
    fam=ev.get("Event Family",pd.Series(dtype=str)).fillna("").astype(str)
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
                for col in ["Event Family","Event Type","Title","Description","Operational Impact","Trade / Commercial Impact"]:
                    if col in ev.columns:
                        blob=blob.str.cat(ev[col].fillna("").astype(str),sep=" ")
                view=ev[blob.str.contains(pat,case=False,regex=True,na=False)]
            if view.empty: st.caption("No alerts in this category.")
            else: render_event_cards(view,60)


def _market_db_rows(table, columns="*", limit=2000, order=None):
    """Read the normalized market layer when Supabase is configured."""
    try:
        sb=pc_db_client(service=True)
        return pc_safe_rows(sb,table,columns,limit,order=order) if sb else []
    except Exception:
        return []


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
    "Asia-Pacific": {"center": (16.0, 116.0), "zoom": 2.4, "countries": ["China","Japan","South Korea","Taiwan","Philippines","Indonesia","Malaysia","Singapore","Vietnam","Thailand","Australia","New Zealand","Papua New Guinea"]},
    "Central Asia": {"center": (43.0, 66.0), "zoom": 3.2, "countries": ["Kazakhstan","Uzbekistan","Turkmenistan","Kyrgyzstan","Tajikistan","Azerbaijan"]},
    "Arctic": {"center": (70.0, 10.0), "zoom": 2.1, "countries": ["Canada","United States","Russia","Norway","Finland","Sweden","Denmark","Iceland"]},
}

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

def render_trade_regional_maps():
    header("Regional Maps","A shared regional operating picture across ports, disruptions and trade exposure. Use the filters to move from geography to mode and event impact.")
    region=st.selectbox("Region",list(TRADE_REGIONS),key="trade_region_map")
    events=TABLES.get(("Events & Hazards","Events"),pd.DataFrame()).copy()
    locs=TABLES.get(("Events & Hazards","Event Locations"),pd.DataFrame()).copy()
    ports_df=TABLES.get(("Maritime","Ports"),pd.DataFrame()).copy()
    events=_trade_region_filter(events,region,["Country / Countries","Location","Title"])
    ports_view=_trade_region_filter(ports_df,region,["Country","Port / Facility"])

    mode=st.radio("Layer",["All","Incidents & disruptions","Ports"],horizontal=True,key="trade_region_layer")
    severity=st.multiselect("Severity",["Critical","Severe","High","Medium","Moderate","Low"],default=[],key="trade_region_severity")
    if severity and not events.empty and "Severity" in events.columns:
        events=events[events["Severity"].fillna("").astype(str).isin(severity)]

    points=[]
    if mode in ["All","Incidents & disruptions"] and not events.empty and not locs.empty and "Event ID" in events and "Event ID" in locs:
        lp=locs.copy(); lp["Latitude"]=pd.to_numeric(lp.get("Latitude"),errors="coerce"); lp["Longitude"]=pd.to_numeric(lp.get("Longitude"),errors="coerce")
        lp=lp.dropna(subset=["Latitude","Longitude"])
        evcols=[c for c in ["Event ID","Start Date","Title","Severity","Mode","Trade / Commercial Impact"] if c in events.columns]
        ep=lp.merge(events[evcols],on="Event ID",how="inner")
        for _,r in ep.iterrows():
            points.append({"lat":r["Latitude"],"lon":r["Longitude"],"name":str(r.get("Title","Event")),"kind":"Event","detail":str(r.get("Trade / Commercial Impact","")),"severity":str(r.get("Severity",""))})
    if mode in ["All","Ports"] and not ports_view.empty:
        p=ports_view.copy(); p["Latitude"]=pd.to_numeric(p.get("Latitude"),errors="coerce"); p["Longitude"]=pd.to_numeric(p.get("Longitude"),errors="coerce"); p=p.dropna(subset=["Latitude","Longitude"])
        for _,r in p.iterrows():
            points.append({"lat":r["Latitude"],"lon":r["Longitude"],"name":str(r.get("Port / Facility","Port")),"kind":"Port","detail":str(r.get("Key Role","")),"severity":""})
    mp=pd.DataFrame(points)
    c1,c2,c3=st.columns(3); c1.metric("Mapped points",len(mp)); c2.metric("Regional events",len(events)); c3.metric("Ports",len(ports_view))
    if mp.empty:
        st.info("No mapped records are available for the current regional/layer selection.")
    elif pdk is not None:
        cfg=TRADE_REGIONS[region]
        layers=[]
        evp=mp[mp["kind"].eq("Event")]
        pp=mp[mp["kind"].eq("Port")]
        if not pp.empty:
            layers.append(pdk.Layer("ScatterplotLayer",pp,get_position="[lon, lat]",get_radius=25000,radius_min_pixels=3,radius_max_pixels=9,get_fill_color=[79,145,205,170],pickable=True))
        if not evp.empty:
            layers.append(pdk.Layer("ScatterplotLayer",evp,get_position="[lon, lat]",get_radius=40000,radius_min_pixels=5,radius_max_pixels=14,get_fill_color=[230,93,93,210],pickable=True))
        st.pydeck_chart(pdk.Deck(layers=layers,initial_view_state=pdk.ViewState(latitude=cfg["center"][0],longitude=cfg["center"][1],zoom=cfg["zoom"]),tooltip={"html":"<b>{name}</b><br>{kind}<br>{detail}"},map_style=None),use_container_width=True,height=520)
    else:
        st.map(mp,latitude="lat",longitude="lon",use_container_width=True)
    tabs=st.tabs(["Events & impact","Ports"])
    with tabs[0]:
        cols=[c for c in ["Start Date","Event Family","Event Type","Severity","Status","Mode","Country / Countries","Location","Title","Trade / Commercial Impact"] if c in events.columns]
        display_df(events[cols] if cols else events,360)
    with tabs[1]:
        cols=[c for c in ["Port / Facility","Country","Operator","Facility Type","Key Role","Coverage Note"] if c in ports_view.columns]
        display_df(ports_view[cols] if cols else ports_view,360)

# ---------- workspace navigation ----------
st.sidebar.markdown("<div class='pc-kicker'>Power & Corridors Intelligence</div>",unsafe_allow_html=True)
st.sidebar.markdown("### Trade System")
_bst=backend_status()
st.sidebar.caption(f"{APP_VERSION} · {_bst.get('mode','excel').title()} backend")

NAV_SECTIONS={
    "OPERATING PICTURE":["Overview","Regional Maps","Alerts & Disruptions","Watch Areas"],
    "DOMAINS":["Maritime","Rail","Aviation","Trucking","Defence & Shipbuilding","Energy & Industry"],
    "TRADE NETWORK":["Ports & Terminals","Corridors & Systems","Companies","Vessels","Investments"],
    "MARKETS & POLICY":["Freight & Commodity Markets","Market Instruments","Trade Flows & Supply","Country & Macro","Sanctions & Compliance","Trade Policy","Contracts"],
    "MONITORING & TOOLS":["Hormuz Monitor","Live Feeds","News & Signals","Search","Reference & Benchmarks","Data"],
}
VISIBLE_PAGES=[p for items in NAV_SECTIONS.values() for p in items]
HIDDEN_ROUTES={"Ports","Shipyards","Network Map","News & Events","Reference Library","Ferries","Cruise","Maritime Security","Maritime Disruptions","Port Activity"}
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
    if st.button("Vessels",use_container_width=True,key="qa_vessels"):
        request_nav("Vessels"); st.rerun()
    if st.button("Watch Areas",use_container_width=True,key="qa_watch"):
        request_nav("Watch Areas"); st.rerun()
with qa2:
    if st.button("Investments",use_container_width=True,key="qa_investments"):
        request_nav("Investments"); st.rerun()
    if st.button("Corridors",use_container_width=True,key="qa_corridors"):
        request_nav("Corridors & Systems"); st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("<div class='pc-small'>ACTIVE DATA LAYERS</div>",unsafe_allow_html=True)
st.sidebar.markdown("<span class='pc-feed-health'><span class='pc-dot pc-dot-live'></span> Shared data model</span>",unsafe_allow_html=True)
st.sidebar.markdown("<span class='pc-feed-health'><span class='pc-dot pc-dot-live'></span> PortWatch</span>",unsafe_allow_html=True)
st.sidebar.markdown("<span class='pc-feed-health'><span class='pc-dot pc-dot-live'></span> Hormuz</span>",unsafe_allow_html=True)
news_key_present=bool(_secret("NEWSDATA_API_KEY"))
news_class="pc-dot-live" if news_key_present else "pc-dot-key"
news_label="NewsData" if news_key_present else "NewsData · key needed"
st.sidebar.markdown(f"<span class='pc-feed-health'><span class='pc-dot {news_class}'></span> {news_label}</span>",unsafe_allow_html=True)
st.sidebar.caption("CGMIX and GDELT remain deferred. Live API views keep the last successful session result if a refresh fails.")

st.markdown(f"<div class='pc-breadcrumb'><b>{workspace}</b> &nbsp;/&nbsp; {page}</div>",unsafe_allow_html=True)

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

if page=="Overview":
    header("Trade System Overview","A connected operational picture across companies, infrastructure, movement systems, commercial activity and risk.")

    companies=TABLES.get(("Core Entities","Companies"),pd.DataFrame())
    ports=TABLES.get(("Maritime","Ports"),pd.DataFrame())
    vessels=TABLES.get(("Maritime","Vessels"),pd.DataFrame())
    systems=TABLES.get(("Systems & Waterways","Systems"),pd.DataFrame())
    events=TABLES.get(("Events & Hazards","Events"),pd.DataFrame())
    sanctions=TABLES.get(("Trade Policy & Compliance","Sanctions Designations"),pd.DataFrame())

    metrics=st.columns(6)
    for box,(title,value) in zip(metrics,[
        ("Companies",len(companies)),("Ports",len(ports)),("Vessels",len(vessels)),
        ("Systems",len(systems)),("Events",len(events)),("Sanctions",len(sanctions))
    ]):
        box.metric(title,f"{value:,}")

    st.markdown("### Risk & disruption snapshot")
    compliance=TABLES.get(("Trade Policy & Compliance","Compliance Designations"),pd.DataFrame()).copy()
    restrictions=TABLES.get(("Maritime","Vessel Restrictions"),pd.DataFrame()).copy()
    monitoring=TABLES.get(("Intelligence","Monitoring"),pd.DataFrame()).copy()
    security_events=events.copy()
    if not security_events.empty and "Event Family" in security_events.columns:
        security_events=security_events[security_events["Event Family"].astype(str).str.contains(
            "Security|Conflict|Maritime|Port|Weather|Natural|Labour|Civil|Cyber",case=False,regex=True,na=False
        )]
    r1,r2,r3,r4=st.columns(4)
    r1.metric("Security / disruption events",len(security_events))
    r2.metric("Active monitoring",int(monitoring.get("Status",pd.Series(dtype=str)).astype(str).str.contains("Active",case=False,na=False).sum()) if not monitoring.empty else 0)
    r3.metric("Vessel restrictions",len(restrictions))
    r4.metric("Operational compliance",len(compliance))
    st.caption("Security is shown here as trade exposure: disrupted assets, restricted vessels, watch areas and operational consequences. The dedicated P&C Intelligence app provides the deeper security workflow.")

    st.markdown("### Connected coverage")
    st.markdown("<div class='pc-section-note'>These are working entry points, not description cards. Search within a coverage family or open its full workspace.</div>",unsafe_allow_html=True)
    cov_tabs=st.tabs(["Commercial networks","Movement systems","Infrastructure","Intelligence","Compliance","Defence & shipbuilding"])

    def coverage_search(tab_key, placeholder, sheets, launches):
        q=st.text_input("Search this coverage",placeholder=placeholder,key=f"coverage_{tab_key}")
        bcols=st.columns(max(1,len(launches)))
        for i,(label_txt,target) in enumerate(launches):
            with bcols[i]:
                if st.button(label_txt,use_container_width=True,key=f"coverage_launch_{tab_key}_{i}"):
                    request_nav(target); st.rerun()
        if q.strip():
            hits=ranked_search(q.strip(),limit=80)
            sub=hits[hits["sheet"].isin(sheets)].head(12) if not hits.empty else pd.DataFrame()
            if sub.empty: st.info("No matching records in this coverage area.")
            else:
                for _,h in sub.iterrows(): readable_search_card(h)
        else:
            st.caption("Search here, or use the buttons above to open the full view.")

    with cov_tabs[0]:
        coverage_search("commercial","DP World, APM Terminals, KKR, Brookfield, acquisition...",["Companies","Relationships","Infra Deals","Transactions V125","Port Ownership"],[("Companies","Companies"),("Contracts & deals","Contracts")])
    with cov_tabs[1]:
        coverage_search("movement","Jebel Ali, Maersk vessel, ferry, rail, airport...",["Ports","Port Terminals","Vessels","Rail Networks","Rail Nodes","Ferry Routes","Cruise Routes","Aircraft"],[("Ports","Ports"),("Vessels","Vessels"),("Corridors","Corridors & Systems")])
    with cov_tabs[2]:
        coverage_search("infrastructure","Middle Corridor, dry port, free zone, waterway...",["Corridors","Regional Systems","System Nodes","System Links","System Dependencies","Assets","Facilities","Waterway Systems"],[("Corridors & systems","Corridors & Systems"),("Ports","Ports")])
    with cov_tabs[3]:
        coverage_search("intelligence","Rotterdam strike, typhoon, attack, disruption...",["Events","Strategic Events","Monitoring","Disruption Watch","Weather Labour Events","Impact Chains"],[("Watch Areas","Watch Areas"),("News & events","News & Events"),("News & signals","News & Signals")])
    with cov_tabs[4]:
        coverage_search("compliance","OFAC, sanctions, export controls, trade agreement...",["Sanctions Designations","Sanctions Entity Links","Compliance Regimes","Compliance Designations","Compliance Exposure","Watchlist Taxonomy","Trade Agreements","Trade Remedies & Restrictions","Customs & Procurement"],[("Sanctions & compliance","Sanctions & Compliance"),("Trade policy","Trade Policy")])
    with cov_tabs[5]:
        coverage_search("defence","Seaspan, Fincantieri, shipyard, submarine, delivery...",["Shipyards","Programmes","Contracts","Sales & Delivery Routes","Vessel Build Records","Fleet Orders"],[("Shipyards","Shipyards"),("Contracts","Contracts")])

    st.markdown("### Latest recorded events")
    latest=events.copy()
    if not latest.empty and "Date" in latest.columns:
        latest["_dt"]=pd.to_datetime(latest["Date"],errors="coerce")
        latest=latest.sort_values("_dt",ascending=False)
    render_event_cards(latest,12)

elif page=="Search":
    header("Search P&C","One query across companies, ports, shipyards, vessels, contracts, transactions, news, events and systems.")
    q=st.text_input("Query",placeholder="Try: APM Africa terminals, Seaspan US Coast Guard, AD Ports Black Sea, Rotterdam strike, Fincantieri UAE contracts")
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
        if em.empty and hits.empty:
            st.warning("No matching records found.")

elif page=="Regional Maps":
    render_trade_regional_maps()

elif page=="Alerts & Disruptions":
    render_trade_alerts_workspace()

elif page=="Maritime":
    header("Maritime","Vessels, incidents, disruptions, piracy, port exposure and navigation risk in one maritime workspace.")
    tabs=st.tabs(["Overview","Incidents","Disruptions","Vessels","Ports","Ferries","Cruise","Navigation & Compliance"])
    with tabs[0]:
        v=TABLES.get(("Maritime","Vessels"),pd.DataFrame()).copy()
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
        display_df(v[[c for c in ["Vessel Name","IMO","Vessel Type","Subtype / Class","Flag","Status","Primary Service","Owner Company ID","Operator Company ID"] if c in v.columns]],420)
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


elif page=="Rail":
    header("Rail","Operators, networks, terminals, intermodal nodes, fleet and port connections as a first-class trade infrastructure layer.")
    operators=TABLES.get(("Rail","Rail Operators"),pd.DataFrame()).copy()
    networks=TABLES.get(("Rail","Rail Networks"),pd.DataFrame()).copy()
    nodes=TABLES.get(("Rail","Rail Nodes"),pd.DataFrame()).copy()
    links=TABLES.get(("Rail","Rail Links"),pd.DataFrame()).copy()
    rels=TABLES.get(("Rail","Rail Relationships"),pd.DataFrame()).copy()
    fleet=TABLES.get(("Rail","Rail Fleet"),pd.DataFrame()).copy()
    connections=TABLES.get(("Rail","Rail Connections"),pd.DataFrame()).copy()
    news=TABLES.get(("Rail","Rail News"),pd.DataFrame()).copy()

    m1,m2,m3,m4=st.columns(4)
    m1.metric("Operators",len(operators))
    m2.metric("Networks / corridors",len(networks))
    m3.metric("Rail nodes",len(nodes))
    m4.metric("Port / intermodal links",len(connections))

    q=st.text_input("Search rail network",placeholder="Etihad Rail, Hafeet Rail, CPKC, Georgia, Khalifa Port, intermodal...")
    if q:
        operators=_contains_any(operators,[q]); networks=_contains_any(networks,[q])
        nodes=_contains_any(nodes,[q]); links=_contains_any(links,[q])
        fleet=_contains_any(fleet,[q]); connections=_contains_any(connections,[q]); news=_contains_any(news,[q])

    tabs=st.tabs(["Operators","Networks & Corridors","Nodes / Terminals","Port & Intermodal Connections","Fleet","Security & Disruption","News & Events"])
    with tabs[0]:
        clean_network_table(operators,["Operator","Operator Type","Jurisdiction","Role","Network Scale","Gauge","Electrification / Signalling","Status","Notes"],280)
        if not operators.empty and "Operator" in operators.columns:
            pick=st.selectbox("Inspect rail operator",range(len(operators)),format_func=lambda i:str(operators.iloc[i].get("Operator","")),key="rail_operator_pick")
            rr=operators.iloc[pick]
            linked_company_button(rr.get("Company ID",""),f"railop_company_{pick}")
    with tabs[1]:
        clean_network_table(networks,["Network / Corridor","Countries / Jurisdictions","Start Node","End Node","Length / Scale","Gauge","Status","Primary Cargo / Role","Notes"],320)
    with tabs[2]:
        clean_network_table(nodes,["Node","Country","Node Type","Status","Notes"],320)
    with tabs[3]:
        clean_network_table(connections,["Connected Entity Type","Connected Entity Name","Status","Notes"],320)
        st.caption("These records connect rail nodes back to canonical ports, terminals, dry ports and other infrastructure in the Trade System.")
    with tabs[4]:
        clean_network_table(fleet,["Fleet Type","Count","Composition / Capacity","Status","Notes"],220)
    with tabs[5]:
        hev=TABLES.get(("Events & Hazards","Events"),pd.DataFrame()).copy()
        if not hev.empty: hev=_contains_any(hev,["rail","locomotive","railway","train","depot"],["Mode","Event Family","Event Type","Title","Description","Trade / Commercial Impact"])
        render_event_cards(hev,40)
    with tabs[6]:
        clean_network_table(news,["Date","Event Type","Headline","Summary"],260)

elif page=="Trucking":
    header("Trucking","Road operators, fleets/networks and intermodal relationships connecting ports, rail, warehouses and inland markets.")
    operators=TABLES.get(("Road & Trucking","Trucking Companies"),pd.DataFrame()).copy()
    assets=TABLES.get(("Road & Trucking","Trucking Assets"),pd.DataFrame()).copy()
    rels=TABLES.get(("Road & Trucking","Trucking Relationships"),pd.DataFrame()).copy()

    m1,m2,m3=st.columns(3)
    m1.metric("Operators",len(operators))
    m2.metric("Road / logistics assets",len(assets))
    m3.metric("Corporate / operating links",len(rels))

    q=st.text_input("Search trucking",placeholder="TFI, Canpar, Qube, Canada, Australia, intermodal...")
    if q:
        operators=_contains_any(operators,[q]); assets=_contains_any(assets,[q]); rels=_contains_any(rels,[q])

    tabs=st.tabs(["Operators","Assets & Networks","Ownership & Relationships"])
    with tabs[0]:
        clean_network_table(operators,["Company","Road Segment","Primary Geography","Fleet / Network Notes","Public / Private","Status"],260)
        if not operators.empty:
            pick=st.selectbox("Inspect trucking operator",range(len(operators)),format_func=lambda i:str(operators.iloc[i].get("Company","")),key="truck_operator_pick")
            rr=operators.iloc[pick]
            st.markdown(f"### {rr.get('Company','')}")
            st.caption(f"{rr.get('Road Segment','')} · {rr.get('Primary Geography','')}")
            linked_company_button(rr.get("Company ID",""),f"truck_company_{pick}")
            parent=str(rr.get("Parent Company ID","")).strip()
            if parent:
                st.markdown("**Parent company**")
                st.write(label(parent))
                linked_company_button(parent,f"truck_parent_{pick}","Open parent company")
    with tabs[1]:
        clean_network_table(assets,["Asset / Network","Asset Type","Country / Region","Location","Intermodal Links","Status","Notes"],300)
    with tabs[2]:
        clean_network_table(rels,["Relationship","Effective From","Effective To","Status","Confidence","Notes"],240)

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

elif page in ["Ports","Ports & Terminals"]:
    header("Ports","Port / terminal explorer with operators, facilities, geography and linked events.")
    ports=unified_ports_with_reference(TABLES.get(("Maritime","Ports"),pd.DataFrame()))
    terms=TABLES.get(("Maritime","Port Terminals"),pd.DataFrame())
    if ports.empty:
        st.info("Port data unavailable.")
    else:
        ref_ports=global_port_reference_view()
        if not ref_ports.empty:
            st.markdown("### Global port geography")
            st.caption(f"{len(ref_ports):,} geocoded port locations from the uploaded global reference dataset. Hover a point to see the port name.")
            render_named_port_map(ref_ports,height=500,radius=18000)
            with st.expander("Search global port reference"):
                rq=st.text_input("Reference port search",placeholder="Ningbo, Qingdao, Singapore, Rotterdam...",key="global_port_reference_q")
                rv=ref_ports.copy()
                if rq.strip(): rv=_contains_any(rv,[rq],["Port Name","Country Name","name","iso3"])
                display_df(rv[[c for c in ["Port Name","Country Name","Latitude","Longitude","throughput","export","import","trans"] if c in rv.columns]].head(250),300)
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

        if q: p=_contains_any(p,[q],["Port / Facility","Country","Operator"])
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
            row=p.iloc[pick]; pid=str(row.get("Port ID","")); pname=str(row.get("Port / Facility",""))
            st.markdown(f"## {pname}")
            c1,c2,c3=st.columns(3)
            pt_raw=terms[terms["Port ID"].astype(str).eq(pid)].copy() if not terms.empty and "Port ID" in terms.columns else pd.DataFrame()
            pt=filter_distinct_port_terminals(row,pt_raw)
            c1.metric("Terminals",len(pt))
            c2.markdown(f"<div class='pc-card'><div class='pc-label'>Country</div><div class='pc-big'>{row.get('Country','')}</div></div>",unsafe_allow_html=True)
            c3.markdown(f"<div class='pc-card'><div class='pc-label'>Operator</div><div class='pc-big'>{row.get('Operator','') or 'Multiple / authority-led'}</div></div>",unsafe_allow_html=True)
            render_port_commercial_network(row,pt)
            render_port_governance(row)
            render_portwatch_port_snapshot(pname,row.get("Country",""))
            lat=pd.to_numeric(pd.Series([row.get("Latitude","")]),errors="coerce").iloc[0]
            lon=pd.to_numeric(pd.Series([row.get("Longitude","")]),errors="coerce").iloc[0]
            if pd.notna(lat) and pd.notna(lon):
                render_named_port_map(pd.DataFrame([{"Port / Facility":pname,"Country":row.get("Country",""),"Latitude":lat,"Longitude":lon}]),height=320,radius=50000)
                if row.get("Geo Source",""):
                    st.caption(f"Location source: {row.get('Geo Source','')}")
            else:
                xy=PORT_CITY_COORDS.get(pname)
                if xy:
                    render_named_port_map(pd.DataFrame([{"Port / Facility":pname,"Country":row.get("Country",""),"Latitude":xy[0],"Longitude":xy[1]}]),height=320,radius=50000)
            ev,loc,chains=event_bundle_for_entities(asset_ids=[pid])
            if not ev.empty:
                render_event_map(ev,loc,"Events affecting this port")
            tabs=st.tabs(["Terminals","Governance","Security & Disruption","Events & Impact","Evidence"])
            with tabs[0]:
                if not pt_raw.empty and len(pt) < len(pt_raw):
                    st.caption("Port-level coverage rows are excluded here so the terminal view shows only distinct subordinate facilities.")
                render_port_terminal_cards(pid,pt)
                with st.expander("View terminal data table"):
                    display_df(pt,300)
            with tabs[1]:
                gov=port_governance_rows(row)
                if gov.empty:
                    st.info("No dedicated port-governance record has been mapped yet.")
                else:
                    v=gov.copy()
                    v["Authority / governing entity"]=v["Authority/Governing Entity ID"].map(_resolve_entity_name)
                    v["Governance role"]=v["Governance Role"].map(pretty_relationship)
                    display_df(v[["Authority / governing entity","Governance role","Model Note","Source URL"]],220)
            with tabs[2]:
                if ev.empty:
                    st.info("No linked security/disruption events for this port yet.")
                else:
                    security_mask=ev.get("Event Family",pd.Series(index=ev.index,dtype=str)).astype(str).str.contains("Security|Conflict|Maritime|Port|Weather|Natural|Labour|Civil|Cyber",case=False,regex=True,na=False)
                    sev=ev[security_mask].copy()
                    render_event_cards(sev,50)
                    if sev.empty: st.info("No events currently classified into the security/disruption view.")
            with tabs[3]:
                render_event_cards(ev,50)
                if not chains.empty: display_df(chains,100)
            with tabs[4]: display_df(pd.DataFrame([row]),20)

elif page=="Watch Areas":
    header("Watch Areas","Active monitoring, disruption watchlists, weather/labour observations and strategic events in one operational workspace.")
    monitoring=TABLES.get(("Intelligence","Monitoring"),pd.DataFrame()).copy()
    disruption=TABLES.get(("Intelligence","Disruption Watch"),pd.DataFrame()).copy()
    weather=TABLES.get(("Intelligence","Weather Labour Events"),pd.DataFrame()).copy()
    strategic=TABLES.get(("Intelligence","Strategic Events"),pd.DataFrame()).copy()
    corridors=TABLES.get(("Infrastructure","Corridors"),pd.DataFrame()).copy()
    m1,m2,m3,m4=st.columns(4)
    m1.metric("Monitoring",f"{len(monitoring):,}")
    m2.metric("Disruption watch",f"{len(disruption):,}")
    m3.metric("Weather / labour",f"{len(weather):,}")
    m4.metric("Corridors",f"{len(corridors):,}")
    wt1,wt2,wt3,wt4=st.tabs(["Active monitoring","Disruption watch","Weather & labour","Strategic events"])
    with wt1:
        q=st.text_input("Search monitoring",placeholder="Hormuz, Black Sea, Red Sea, port strike...",key="watch_monitor_q")
        display_df(_contains_any(monitoring,[q]) if q.strip() and not monitoring.empty else monitoring,300)
    with wt2:
        q=st.text_input("Search disruption watch",placeholder="port, rail, aviation, weather, conflict...",key="watch_disrupt_q")
        dview=_contains_any(disruption,[q]) if q.strip() and not disruption.empty else disruption
        display_df(dview,300)
        if not dview.empty:
            dview=dview.reset_index(drop=True)
            labels=[f"{r.get('Location / System','')} — {r.get('Issue','')}" for _,r in dview.iterrows()]
            dpick=st.selectbox("Inspect disruption",range(len(labels)),format_func=lambda i:labels[i],key="watch_disruption_pick")
            render_trade_disruption_brief(dview.iloc[dpick])
    with wt3:
        q=st.text_input("Search weather / labour",placeholder="typhoon, earthquake, strike, protest...",key="watch_weather_q")
        display_df(_contains_any(weather,[q]) if q.strip() and not weather.empty else weather,300)
    with wt4:
        q=st.text_input("Search strategic events",placeholder="attack, closure, acquisition, sanctions...",key="watch_strategic_q")
        display_df(_contains_any(strategic,[q]) if q.strip() and not strategic.empty else strategic,300)
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
        display_df(vessels[[c for c in ["Vessel","Class / Type","Customer / Operator","Build Yard ID","Status","Build / Delivery Route"] if c in vessels.columns]],300)
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


elif page=="Contracts":
    header("Contracts & Commercial","Government procurement, commercial transactions, infrastructure deals, vessel sales and delivery routes.")
    q=st.text_input("Filter",placeholder="AD Ports, UAE, Coast Guard, CLI, port terminals, icebreakers...")
    defence=TABLES.get(("Defence & Shipbuilding","Contracts"),pd.DataFrame())
    tx=TABLES.get(("Transactions","Transactions V125"),pd.DataFrame())
    deals=TABLES.get(("Transactions","Infra Deals"),pd.DataFrame())
    routes=TABLES.get(("Defence & Shipbuilding","Sales & Delivery Routes"),pd.DataFrame())
    if q:
        defence=_contains_any(defence,[q]); tx=_contains_any(tx,[q]); deals=_contains_any(deals,[q]); routes=_contains_any(routes,[q])
    # simple commercial composition figure
    counts=pd.Series({"Defence / government":len(defence),"Corporate transactions":len(tx),"Infrastructure deals":len(deals),"Sales / delivery routes":len(routes)})
    st.bar_chart(counts,horizontal=True)
    t1,t2,t3,t4=st.tabs([f"Defence / Government · {len(defence)}",f"Transactions · {len(tx)}",f"Infrastructure Deals · {len(deals)}",f"Sales / Delivery · {len(routes)}"])
    with t1: display_df(defence,250)
    with t2: display_df(tx,250)
    with t3: display_df(deals,250)
    with t4: display_df(routes,250)

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
        "Government sanctions, programmes and designations. Government sanctions remain separate from analytical and operational watchlists."
    )
    des=TABLES.get(("Trade Policy & Compliance","Sanctions Designations"),pd.DataFrame()).copy()
    auth=TABLES.get(("Trade Policy & Compliance","Sanctions Authorities"),pd.DataFrame()).copy()
    progs=TABLES.get(("Trade Policy & Compliance","Sanctions Programmes"),pd.DataFrame()).copy()
    links=TABLES.get(("Trade Policy & Compliance","Sanctions Entity Links"),pd.DataFrame()).copy()
    watch=TABLES.get(("Trade Policy & Compliance","Watchlist Taxonomy"),pd.DataFrame()).copy()
    rules=TABLES.get(("Trade Policy & Compliance","Policy Interaction Rules"),pd.DataFrame()).copy()
    compliance_regimes=TABLES.get(("Trade Policy & Compliance","Compliance Regimes"),pd.DataFrame()).copy()
    compliance_designations=TABLES.get(("Trade Policy & Compliance","Compliance Designations"),pd.DataFrame()).copy()
    compliance_exposure=TABLES.get(("Trade Policy & Compliance","Compliance Exposure"),pd.DataFrame()).copy()

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
            if compliance_regimes.empty and compliance_designations.empty:
                st.info("No operational compliance records loaded.")
            else:
                if not compliance_regimes.empty:
                    display_df(compliance_regimes,100)
                if not compliance_designations.empty:
                    st.markdown("#### Designations / restrictions")
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
        "Live CGMIX/PSIX and Incident Investigation Report lookups. This is an external evidence layer and is not written into the canonical Excel model."
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

elif page=="News & Signals":
    header(
        "News & Signals",
        "Open-source discovery across trade, ports, logistics, maritime, rail, aviation and infrastructure. Results remain leads for verification and entity matching."
    )
    api_key=_secret("NEWSDATA_API_KEY")
    if not api_key:
        st.markdown("<div class='pc-hero'><div class='pc-hero-title'>NewsData.io connector ready</div><div class='pc-hero-copy'>Add <b>NEWSDATA_API_KEY</b> to Streamlit Secrets to activate this workspace. No external requests are made until the key is present.</div></div>",unsafe_allow_html=True)
    else:
        st.caption("Source: NewsData.io · cached for 60 minutes · discovery layer only")
    presets={
        "Maritime security":"ship vessel tanker attack drone missile seizure piracy",
        "Ports & terminals":"port terminal strike closure disruption explosion congestion",
        "Logistics & supply chain":"logistics shipping freight disruption congestion delay shortage",
        "Rail & intermodal":"rail railway freight intermodal derailment strike disruption",
        "Aviation & air cargo":"airport aviation air cargo disruption closure strike",
        "Trade & sanctions":"trade sanctions export controls shipping compliance",
        "Infrastructure & deals":"port terminal logistics railway acquisition investment concession contract",
        "Custom":""
    }
    c1,c2=st.columns([1.2,2.8])
    with c1: family=st.selectbox("Signal family",list(presets),key="newsdata_family")
    with c2: query=st.text_input("Search terms",value=presets[family],placeholder="Rotterdam port strike",key="newsdata_query")
    if st.button("Search news & signals",type="primary",disabled=not bool(api_key),key="newsdata_go"):
        if len(query.strip())<3:
            st.warning("Enter a more specific search.")
        else:
            ndf,nerr=load_newsdata_articles(query.strip(),api_key,"en",10)
            st.session_state["newsdata_results"]=(ndf,nerr,query.strip())
    ndf,nerr,lastq=st.session_state.get("newsdata_results",(pd.DataFrame(),"",""))
    if nerr:
        st.warning(f"NewsData.io is temporarily unavailable. {nerr}")
    elif not ndf.empty:
        m1,m2,m3=st.columns(3)
        m1.metric("Signals",f"{len(ndf):,}")
        source_col="source_name" if "source_name" in ndf.columns else ("source_id" if "source_id" in ndf.columns else None)
        m2.metric("Sources",f"{ndf[source_col].nunique():,}" if source_col else "—")
        countries=set()
        if "country" in ndf.columns:
            for x in ndf["country"].tolist():
                if isinstance(x,list): countries.update(str(v) for v in x)
                elif x: countries.add(str(x))
        m3.metric("Countries",f"{len(countries):,}" if countries else "—")
        st.markdown(f"### Results for `{lastq}`")
        for _,row in ndf.head(50).iterrows():
            title=str(row.get("title","") or "Untitled")
            url=str(row.get("link","") or "")
            desc=str(row.get("description","") or "")
            source=str(row.get("source_name",row.get("source_id","")) or "")
            pub=str(row.get("pubDate","") or "")
            country=row.get("country","")
            if isinstance(country,list): country=", ".join(map(str,country))
            if url: st.markdown(f"**[{title}]({url})**")
            else: st.markdown(f"**{title}**")
            meta=" · ".join(x for x in [source,str(country),pub] if str(x).strip())
            if meta: st.caption(meta)
            if desc: st.write(desc[:650] + ("…" if len(desc)>650 else ""))
            st.markdown("<span class='pc-chip'>OPEN SOURCE</span><span class='pc-chip'>UNVERIFIED SIGNAL</span>",unsafe_allow_html=True)
            st.markdown("---")
        st.caption("Corroborate and resolve entities before promoting a signal into the canonical event model.")
    elif api_key:
        st.info("Choose a signal family or enter search terms to scan the latest news feed.")

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
