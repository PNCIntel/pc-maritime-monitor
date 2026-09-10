from pathlib import Path
import os
import re
import json
import html as html_lib
import xml.etree.ElementTree as ET
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from collections import defaultdict
import pandas as pd
import streamlit as st

APP_TITLE = "P&C Trade System"
APP_VERSION = "v2.7.0"
RELEASE_NAME = "Navigation, Watch Areas & Persistent Live Data"
DATA_DIR = Path(__file__).parent / "data"

st.set_page_config(page_title=f"{APP_TITLE} {APP_VERSION}", page_icon="◈", layout="wide", initial_sidebar_state="expanded")

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

/* v2.6 workspace navigation */
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
}

@st.cache_data(show_spinner=False)
def workbook_sheets(label):
    path = DATA_DIR / WORKBOOKS[label]
    if not path.exists(): return []
    try: return pd.ExcelFile(path).sheet_names
    except Exception: return []

@st.cache_data(show_spinner=False)
def load_sheet(label, sheet):
    path = DATA_DIR / WORKBOOKS[label]
    if not path.exists(): return pd.DataFrame()
    try: return pd.read_excel(path, sheet_name=sheet, dtype=str).fillna("")
    except Exception: return pd.DataFrame()

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
        req = Request(url, headers={"User-Agent":"PC-Trade-System/2.7"})
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
        req=Request(url,headers={"User-Agent":"PC-Trade-System/2.7"})
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
        req=Request(NEWSDATA_LATEST_URL+"?"+urlencode(params),headers={"User-Agent":"PC-Trade-System/2.7"})
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
        req=Request(AISHUB_URL+"?"+urlencode(params),headers={"User-Agent":"PC-Trade-System/2.7"})
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
    req = Request(url, headers={"User-Agent":"PC-Trade-System/2.7"})
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

@st.cache_data(show_spinner=False)
def all_tables():
    out={}
    for wb_label in WORKBOOKS:
        for sheet in workbook_sheets(wb_label):
            df=load_sheet(wb_label,sheet)
            if not df.empty: out[(wb_label,sheet)] = df
    return out

TABLES=all_tables()

# Fail clearly when a deployment is incomplete. Previous builds silently loaded an
# empty interface when the workbooks were placed in the repository root or carried
# browser-added suffixes such as "(1)".
MISSING_WORKBOOKS = [filename for filename in WORKBOOKS.values() if not (DATA_DIR / filename).exists()]
if MISSING_WORKBOOKS:
    st.error("This deployment is missing required data workbooks: " + ", ".join(MISSING_WORKBOOKS))
    st.info("Place the 14 canonical XLSX files in the data/ directory using the filenames shown above.")
    st.stop()

ID_RE=re.compile(r"(^|\s)(id|entity id|company id|programme id|program id|yard id|vessel id|facility id|source id|relationship id|contract id|route id|news id|event id|port id|terminal id|asset id|link id|event link id|news link id|location record|status record|chain id|impact id|observation id|canonical event id|external event id|approval id|status history id|control record id)(\s|$)",re.I)

# Internal IDs are required for joins, but never need to be the normal user interface.
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

def _friendly_col_name(c):
    c=str(c)
    if c in ID_FRIENDLY_NAMES: return ID_FRIENDLY_NAMES[c]
    if ID_RE.search(c):
        s=re.sub(r"\bID\b","",c,flags=re.I).strip(" /_-")
        return s or "Entity"
    return c

def humanize_df(df, keep_urls=True, show_internal_ids=False):
    """Resolve internal keys to English names before presentation."""
    if df is None or df.empty: return pd.DataFrame()
    out=pd.DataFrame(index=df.index)
    for c in df.columns:
        cstr=str(c)
        if not keep_urls and "url" in cstr.lower():
            continue
        vals=df[c].copy()

        # Resolve ID-bearing fields into canonical English labels.
        is_id_col=bool(ID_RE.search(cstr) or cstr in ID_FRIENDLY_NAMES)
        if is_id_col:
            friendly=_friendly_col_name(cstr)
            resolved=vals.astype(str).map(label)
            # Suppress raw source/news/etc IDs if they cannot be translated to something human.
            unresolved=resolved.eq(vals.astype(str))
            technical_prefix=vals.astype(str).str.match(r"^(SRC|REL|NEWS|NL|OWN|BERTH|EQ|PRICE|FIN|CON|SALE|ANN|FAC|LNK|CM|INT|GOV|TEST|SYS|PORT|TERM|COMP|DEF|YARD|PROG|VES|ASSET|WATER|RAIL|CORR)_?",case=False,na=False)
            if technical_prefix.all() and unresolved.all() and not show_internal_ids:
                continue
            if friendly in out.columns:
                # avoid duplicate English columns such as Primary Operator ID + Primary Operator
                if out[friendly].astype(str).str.strip().eq("").all():
                    out[friendly]=resolved
                continue
            out[friendly]=resolved
            if show_internal_ids and friendly != cstr:
                out[cstr]=vals
        else:
            # Also translate exact entity-key values that happen to live in non-ID columns.
            def trans(v):
                s=str(v).strip()
                if s in LABELS:
                    return label(s)
                if cstr.lower() in {"relationship","link type","capability","event type","event family","asset type","control type","status","yard model"}:
                    return pretty_relationship(s) if cstr.lower() in {"relationship","link type"} else pretty_enum(s)
                return pretty_enum(s)
            out[cstr]=vals.map(trans)

    # Prefer populated human-readable columns and drop duplicate column names.
    out=out.loc[:,~out.columns.duplicated()].copy()
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
    """Turn implementation taxonomy into ordinary English for the UI."""
    s=str(v).strip()
    if not s:
        return ""
    # Do not touch URLs or normal prose.
    if s.startswith("http://") or s.startswith("https://"):
        return s
    # Resolve canonical IDs first.
    if s in LABELS:
        return LABELS[s]
    # ALL_CAPS_ENUM / SNAKE_CASE_ENUM -> title-like English.
    if "_" in s and re.fullmatch(r"[A-Z0-9_ /+-]+",s):
        s=s.replace("_"," ").strip()
        # Preserve common acronyms.
        words=[]
        keep={"MRO","JV","UAE","US","USA","UK","EU","IMO","OPV","LNG","TEU","CG","SAR","RFI","RFP"}
        for w in s.split():
            words.append(w if w in keep else w.lower())
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

def render_event_cards(events,max_items=40):
    if events is None or events.empty:
        st.info("No linked events.")
        return
    e=events.copy()
    if "Start Date" in e.columns:
        e["_dt"]=pd.to_datetime(e["Start Date"],errors="coerce")
        e=e.sort_values("_dt",ascending=False)
    show_named_list(e,"Title",["Start Date","Event Family","Event Type","Severity","Status","Location"],source_col="Primary Source URL",max_items=max_items)

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

def vessel_profile_data(vessel_id, vessel_name):
    commercial=TABLES.get(("Maritime","Vessels"),pd.DataFrame())
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
                    "Date":str(ur.get("Date","")).strip(),
                    "Event Type":str(ur.get("Event Family","")).strip() or str(ur.get("Event Type","")).strip(),
                    "Subject Entity ID":str(vessel_id),
                    "Location":str(ur.get("Location","")).strip(),
                    "Title":str(ur.get("Title","")).strip(),
                    "Description":str(ur.get("Description","")).strip(),
                    "Operational Impact":str(ur.get("Direct Impact","")).strip(),
                    "Financial / Strategic Impact":str(ur.get("Strategic / Commercial Outcome","")).strip(),
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

    with tabs[3]:
        render_vessel_incident_cards(events,news)

    with tabs[4]:
        if not news.empty:
            show_named_list(news,"Headline",["Published Date","Publisher","Region","Event Type"],source_col="URL",max_items=100)
        else:
            st.info("No linked news reporting.")

    with tabs[5]:
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

# ---------- workspace navigation ----------
st.sidebar.markdown("<div class='pc-kicker'>Power & Corridors Intelligence</div>",unsafe_allow_html=True)
st.sidebar.markdown("### Trade System")
st.sidebar.caption(f"{APP_VERSION} · Excel-backed test")

NAV_GROUPS={
    "Command Center":["Overview","Search"],
    "Network":["Companies","Ports","Vessels","Corridors & Systems","Cruise & Service Craft","Shipyards"],
    "Operations":["Watch Areas","Port Activity","Hormuz Monitor","Live Feeds"],
    "Markets & Policy":["Sanctions","Trade Policy","Contracts"],
    "Intelligence":["News & Signals","News & Events"],
    "Data":["Data"],
}
PAGE_WORKSPACE={p:w for w,items in NAV_GROUPS.items() for p in items}
# Cross-page buttons queue navigation for the next rerun so sidebar widgets are not mutated after instantiation.
if "nav_request" in st.session_state:
    requested=st.session_state.pop("nav_request")
    target_workspace=PAGE_WORKSPACE.get(requested)
    if target_workspace:
        st.session_state["workspace_nav"]=target_workspace
        st.session_state[f"view_nav_{target_workspace}"]=requested
if st.session_state.get("workspace_nav") not in NAV_GROUPS:
    st.session_state["workspace_nav"]="Command Center"
workspace=st.sidebar.radio("Workspace",list(NAV_GROUPS),index=0,key="workspace_nav")
views=NAV_GROUPS[workspace]
if len(views)>1:
    page=st.sidebar.radio("View",views,index=0,key=f"view_nav_{workspace}")
else:
    page=views[0]

st.sidebar.markdown("---")
st.sidebar.markdown("<div class='pc-small'>QUICK ACCESS</div>",unsafe_allow_html=True)
qa1,qa2=st.sidebar.columns(2)
with qa1:
    if st.button("Vessels",use_container_width=True,key="qa_vessels"):
        request_nav("Vessels"); st.rerun()
    if st.button("Watch Areas",use_container_width=True,key="qa_watch"):
        request_nav("Watch Areas"); st.rerun()
with qa2:
    if st.button("Sanctions",use_container_width=True,key="qa_sanctions"):
        request_nav("Sanctions"); st.rerun()
    if st.button("Corridors",use_container_width=True,key="qa_corridors"):
        request_nav("Corridors & Systems"); st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("<div class='pc-small'>ACTIVE DATA LAYERS</div>",unsafe_allow_html=True)
st.sidebar.markdown("<span class='pc-feed-health'><span class='pc-dot pc-dot-live'></span> Excel model</span>",unsafe_allow_html=True)
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
        coverage_search("compliance","OFAC, sanctions, export controls, trade agreement...",["Sanctions Designations","Sanctions Entity Links","Watchlist Taxonomy","Trade Agreements","Trade Remedies & Restrictions","Customs & Procurement"],[("Sanctions","Sanctions"),("Trade policy","Trade Policy")])
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
                ("Trade policy & compliance",["Trade Agreements","Tariff Coverage","HS Product Tests","Rules of Origin","Customs & Procurement","Trade Remedies & Restrictions","Sanctions Designations"]),
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

elif page=="Ports":
    header("Ports","Port / terminal explorer with operators, facilities, geography and linked events.")
    ports=TABLES.get(("Maritime","Ports"),pd.DataFrame())
    terms=TABLES.get(("Maritime","Port Terminals"),pd.DataFrame())
    if ports.empty:
        st.info("Port data unavailable.")
    else:
        requested_port=st.session_state.pop("port_pick_id",None)
        if requested_port:
            st.session_state["port_search_text"]=""
        q=st.text_input("Find port",placeholder="Rotterdam, Shanghai, Odesa, Vancouver, Constanța...",key="port_search_text")
        p=ports.copy()

        requested_terminal=st.session_state.pop("terminal_pick_id",None)
        if requested_terminal:
            st.session_state["port_search_text"]=""
        if requested_terminal and not terms.empty and "Terminal ID" in terms.columns:
            tr=terms[terms["Terminal ID"].astype(str).eq(str(requested_terminal))]
            if not tr.empty and "Port ID" in tr.columns:
                requested_port=str(tr.iloc[0]["Port ID"])

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
            pt=terms[terms["Port ID"].astype(str).eq(pid)].copy() if not terms.empty and "Port ID" in terms.columns else pd.DataFrame()
            c1.metric("Terminals",len(pt))
            c2.markdown(f"<div class='pc-card'><div class='pc-label'>Country</div><div class='pc-big'>{row.get('Country','')}</div></div>",unsafe_allow_html=True)
            c3.markdown(f"<div class='pc-card'><div class='pc-label'>Operator</div><div class='pc-big'>{row.get('Operator','') or 'Multiple / authority-led'}</div></div>",unsafe_allow_html=True)
            xy=PORT_CITY_COORDS.get(pname)
            if xy:
                st.map(pd.DataFrame([{"name":pname,"lat":xy[0],"lon":xy[1]}]),latitude="lat",longitude="lon",size=100)
            ev,loc,chains=event_bundle_for_entities(asset_ids=[pid])
            if not ev.empty:
                render_event_map(ev,loc,"Events affecting this port")
            tabs=st.tabs(["Terminals","Events & Impact","Evidence"])
            with tabs[0]: display_df(pt,300)
            with tabs[1]:
                render_event_cards(ev,50)
                if not chains.empty: display_df(chains,100)
            with tabs[2]: display_df(pd.DataFrame([row]),20)

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
        display_df(_contains_any(disruption,[q]) if q.strip() and not disruption.empty else disruption,300)
    with wt3:
        q=st.text_input("Search weather / labour",placeholder="typhoon, earthquake, strike, protest...",key="watch_weather_q")
        display_df(_contains_any(weather,[q]) if q.strip() and not weather.empty else weather,300)
    with wt4:
        q=st.text_input("Search strategic events",placeholder="attack, closure, acquisition, sanctions...",key="watch_strategic_q")
        display_df(_contains_any(strategic,[q]) if q.strip() and not strategic.empty else strategic,300)
    if st.button("Open corridor context",key="watch_open_corridors"):
        request_nav("Corridors & Systems"); st.rerun()

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
        st.dataframe(show.sort_values("Port Calls",ascending=False) if "Port Calls" in show.columns else show,use_container_width=True,hide_index=True)

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
    commercial=TABLES.get(("Maritime","Vessels"),pd.DataFrame()).copy()
    defence=TABLES.get(("Defence & Shipbuilding","Sample Vessels"),pd.DataFrame()).copy()

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
        ["Commercial","Defence / Government"],
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

    else:
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

elif page=="Cruise & Service Craft":
    header("Cruise & Service Craft","Cruise brands, ships, destinations and route families alongside tug, OSV and offshore-construction fleets.")
    lines=TABLES.get(("Maritime","Cruise Lines"),pd.DataFrame()).copy()
    ships=TABLES.get(("Maritime","Cruise Ships"),pd.DataFrame()).copy()
    destinations=TABLES.get(("Maritime","Cruise Destinations"),pd.DataFrame()).copy()
    routes=TABLES.get(("Maritime","Cruise Routes"),pd.DataFrame()).copy()
    craft=TABLES.get(("Maritime","Service Craft"),pd.DataFrame()).copy()

    m1,m2,m3,m4,m5=st.columns(5)
    m1.metric("Cruise brands",len(lines))
    m2.metric("Cruise ships",len(ships))
    m3.metric("Private / controlled destinations",len(destinations))
    m4.metric("Route families",len(routes))
    m5.metric("Service craft",len(craft))

    q=st.text_input("Search cruise and service-craft coverage",placeholder="CocoCay, Great Lakes, SAFEEN, tug, offshore support...")
    if q:
        lines=_contains_any(lines,[q]); ships=_contains_any(ships,[q])
        destinations=_contains_any(destinations,[q]); routes=_contains_any(routes,[q]); craft=_contains_any(craft,[q])

    tabs=st.tabs(["Cruise Lines","Cruise Ships","Destinations","Routes","Tugs / OSVs / Service Craft"])
    with tabs[0]:
        st.caption("Brand and parent-group structure is separated so fleet and destination exposure can roll up without losing the operating line.")
        display_df(humanize_df(lines),200)
    with tabs[1]:
        st.caption("Sector-specific cruise detail links back to the canonical vessel registry.")
        display_df(humanize_df(ships),300)
    with tabs[2]:
        st.caption("Destination type distinguishes private islands, leased destinations, resort calls and partner beach clubs. Legal land ownership is not inferred.")
        display_df(humanize_df(destinations),200)
    with tabs[3]:
        st.caption("Route families are representative operating patterns, not live sailing schedules.")
        display_df(humanize_df(routes),200)
    with tabs[4]:
        segments=sorted([x for x in craft.get("Craft Segment",pd.Series(dtype=str)).unique().tolist() if str(x).strip()])
        selected=st.multiselect("Craft segment",segments,default=[])
        shown=craft[craft["Craft Segment"].isin(selected)] if selected else craft
        st.caption("SAFEEN assets are connected through the AD Ports / Noatum group ecosystem; direct legal ownership is only shown when supported.")
        display_df(humanize_df(shown),300)

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

elif page=="Sanctions":
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

    if des.empty:
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
            "Designations",
            "Linked Entities",
            "Authorities & Programmes",
            "Watchlists",
            "Policy Precedence"
        ])

        with tabs[0]:
            st.markdown("### Government sanctions designations")
            display_df(humanize_sanctions_df(d),250)

        with tabs[1]:
            st.markdown("### Designated / linked entities")
            if l.empty:
                st.info("No linked entities for this filter.")
            else:
                render_sanction_link_cards(l)

        with tabs[2]:
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

        with tabs[3]:
            st.markdown("### Watchlist taxonomy")
            st.caption("These categories are intentionally separate: a security advisory, shadow-fleet flag or IUU listing is not automatically a government sanctions designation.")
            display_df(humanize_sanctions_df(watch),100)

        with tabs[4]:
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
        with et2: display_df(gl_corr,250)
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
