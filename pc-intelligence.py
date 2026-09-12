import streamlit as st
import os, sys
import pandas as pd
import re
try:
    import pydeck as pdk
except Exception:
    pdk = None
from pathlib import Path
from datetime import datetime

SHARED_DIR = Path(__file__).resolve().parent / "shared"
if str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))
from pc_data_bridge import load_sheet as bridge_load_sheet, backend_status
from pc_workspace import save_query as save_workspace_query
from pc_db import client as pc_db_client, safe_rows as pc_safe_rows
try:
    from pc_auth import require_login
except Exception:
    require_login = None

st.set_page_config(
    page_title="P&C Intelligence",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)

if os.getenv("PC_REQUIRE_AUTH", "false").lower() == "true" and require_login is not None:
    PC_USER_CONTEXT = require_login("INTELLIGENCE", "P&C Intelligence")
else:
    PC_USER_CONTEXT = None

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"

# -----------------------------------------------------------------------------
# P&C Intelligence visual system
# -----------------------------------------------------------------------------
st.markdown(
    """
<style>
:root {
  --pc-bg: #0d1114;
  --pc-panel: #13191d;
  --pc-panel-2: #171e23;
  --pc-line: #2b343b;
  --pc-ivory: #f1ede3;
  --pc-muted: #aeb6bb;
  --pc-gold: #d4af57;
  --pc-gold-soft: #b99545;
  --pc-red: #b65f56;
  --pc-orange: #bf8b55;
  --pc-green: #5e8b74;
}

.stApp { background: var(--pc-bg); color: var(--pc-ivory); }
[data-testid="stSidebar"] { background: #0a0e11; border-right: 1px solid var(--pc-line); }
[data-testid="stSidebar"] * { color: var(--pc-ivory); }
.block-container { padding-top: 1.6rem; padding-bottom: 3rem; max-width: 1500px; }

h1, h2, h3, h4 { color: var(--pc-ivory) !important; letter-spacing: -0.015em; }
h1 { font-size: 2.25rem !important; font-weight: 650 !important; }
h2 { font-size: 1.45rem !important; margin-top: 1.1rem !important; }
h3 { font-size: 1.05rem !important; }
p, li, label { color: var(--pc-ivory); }

.pc-kicker { color: var(--pc-gold); text-transform: uppercase; letter-spacing: .15em; font-size: .72rem; font-weight: 700; }
.pc-title { font-size: 2.25rem; line-height: 1.05; font-weight: 650; color: var(--pc-ivory); margin-top: .25rem; }
.pc-deck { color: var(--pc-muted); max-width: 900px; font-size: 1.02rem; margin-top: .45rem; }
.pc-rule { height: 1px; background: var(--pc-line); margin: 1rem 0 1.25rem 0; }
.pc-section-kicker { color: var(--pc-gold); font-size: .70rem; text-transform: uppercase; letter-spacing: .13em; font-weight: 700; margin-bottom: .25rem; }
.pc-section-title { color: var(--pc-ivory); font-size: 1.35rem; font-weight: 650; margin-bottom: .25rem; }
.pc-section-copy { color: var(--pc-muted); margin-bottom: .8rem; }

.pc-card { background: var(--pc-panel); border: 1px solid var(--pc-line); border-radius: 5px; padding: 1rem 1.05rem; margin-bottom: .75rem; }
.pc-card-priority { border-top: 2px solid var(--pc-gold); }
.pc-card-title { color: var(--pc-ivory); font-size: 1.02rem; font-weight: 650; margin-bottom: .25rem; }
.pc-card-meta { color: var(--pc-gold); font-size: .72rem; text-transform: uppercase; letter-spacing: .08em; margin-bottom: .45rem; }
.pc-card-body { color: var(--pc-muted); font-size: .90rem; line-height: 1.45; }
.pc-card-impact { color: var(--pc-ivory); font-size: .88rem; margin-top: .5rem; }

.pc-badge { display:inline-block; border:1px solid var(--pc-line); padding:.15rem .45rem; border-radius:2px; margin-right:.28rem; font-size:.68rem; text-transform:uppercase; letter-spacing:.05em; color:var(--pc-muted); }
.pc-badge-high { border-color:#75504b; color:#d78b82; }
.pc-badge-watch { border-color:#6f613b; color:#d8bd72; }
.pc-badge-active { border-color:#3f6553; color:#82b79d; }

[data-testid="stMetric"] { background: var(--pc-panel); border: 1px solid var(--pc-line); border-top: 2px solid var(--pc-gold); padding: .8rem 1rem; border-radius: 4px; }
[data-testid="stMetricLabel"] { color: var(--pc-muted) !important; }
[data-testid="stMetricValue"] { color: var(--pc-ivory) !important; }
[data-testid="stMetricDelta"] { color: var(--pc-gold) !important; }

.stTabs [data-baseweb="tab-list"] { gap: .35rem; border-bottom:1px solid var(--pc-line); }
.stTabs [data-baseweb="tab"] { background:transparent; color:var(--pc-muted); border-radius:0; padding-left:.65rem; padding-right:.65rem; }
.stTabs [aria-selected="true"] { color:var(--pc-gold) !important; border-bottom:2px solid var(--pc-gold); }

[data-testid="stDataFrame"] { border:1px solid var(--pc-line); border-radius:4px; }
[data-testid="stExpander"] { border:1px solid var(--pc-line); background:var(--pc-panel); }

div.stButton > button { background:transparent; color:var(--pc-gold); border:1px solid var(--pc-gold-soft); border-radius:3px; }
div.stButton > button:hover { border-color:var(--pc-gold); color:var(--pc-ivory); background:#181c18; }

.pc-sidebar-brand { padding:.2rem 0 1rem 0; }
.pc-sidebar-brand .brand { color:var(--pc-gold); text-transform:uppercase; letter-spacing:.15em; font-size:.69rem; font-weight:700; }
.pc-sidebar-brand .name { color:var(--pc-ivory); font-size:1.15rem; font-weight:650; margin-top:.15rem; }
.pc-sidebar-brand .tag { color:var(--pc-muted); font-size:.75rem; margin-top:.2rem; }

.pc-empty { border:1px dashed var(--pc-line); padding:1rem; color:var(--pc-muted); border-radius:4px; }
.small-note { color:var(--pc-muted); font-size:.78rem; }

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
""",
    unsafe_allow_html=True,
)

if st.session_state.get("pc_intel_appearance","Dark") == "Light":
    st.markdown("""
    <style>
    :root{
      --pc-bg:#f5f7fa;--pc-panel:#ffffff;--pc-panel-2:#eef2f6;--pc-line:#cbd5e1;
      --pc-ivory:#16202a;--pc-muted:#5d6b7a;--pc-gold:#9a7626;--pc-gold-soft:#b08a34
    }
    .stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"]{background:#f5f7fa!important;color:#16202a!important}
    [data-testid="stSidebar"]{background:#eef2f6!important;border-right:1px solid #cbd5e1!important}
    [data-testid="stSidebar"] *{color:#16202a!important}
    h1,h2,h3,h4,p,li,label,span{color:#16202a!important}
    .pc-card,[data-testid="stMetric"],[data-testid="stExpander"]{background:#ffffff!important;border-color:#cbd5e1!important}
    [data-testid="stMetricLabel"],.pc-card-body,.pc-section-copy,.small-note{color:#5d6b7a!important}
    [data-testid="stMetricValue"]{color:#16202a!important}
    [data-baseweb="select"]>div,[data-baseweb="input"]>div,input,textarea{background:#ffffff!important;color:#16202a!important}
    .stButton>button{background:#ffffff!important;color:#29465f!important;border-color:#b8c3cf!important}
    [data-testid="stHeader"],[data-testid="stToolbar"]{background:#f5f7fa!important;color:#16202a!important}
    </style>
    """,unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Data helpers — all reads are from the same Excel-backed P&C model
# -----------------------------------------------------------------------------
@st.cache_data(show_spinner=False, ttl=300)
def xl(file_name: str, sheet: str) -> pd.DataFrame:
    return bridge_load_sheet(DATA, file_name, sheet, dtype_str=False)


def data_file_status(file_name: str) -> dict:
    path = DATA / file_name
    if not path.exists():
        return {"file": file_name, "exists": False, "size": 0, "modified": ""}
    stat = path.stat()
    return {
        "file": file_name,
        "exists": True,
        "size": stat.st_size,
        "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
    }


def text_col(df, col):
    if df.empty or col not in df.columns:
        return pd.Series(dtype="string")
    return df[col].fillna("").astype(str)


def contains_any(df, columns, terms):
    if df.empty:
        return pd.Series(False, index=df.index)
    blob = pd.Series("", index=df.index, dtype="string")
    for c in columns:
        if c in df.columns:
            blob = blob.str.cat(text_col(df, c), sep=" ")
    pattern = "|".join([str(t) for t in terms])
    return blob.str.contains(pattern, case=False, regex=True, na=False)


def normalize_imo(v):
    if pd.isna(v):
        return ""
    s = str(v).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s




def intelligence_event_filter(df: pd.DataFrame) -> pd.DataFrame:
    """Strict P&C Intelligence gate.

    Include operational/security events: weather/natural hazards, fraud/crime,
    smuggling/illicit trade, conflict/war, labour/civil unrest, casualties,
    infrastructure/transport disruption, cyber, sanctions/enforcement.
    Exclude routine corporate development such as new terminals, cranes,
    investments, vessel orders and service launches unless the same record also
    contains an independent disruption/security trigger.
    """
    if df is None or df.empty:
        return pd.DataFrame() if df is None else df.copy()
    blob=pd.Series("",index=df.index,dtype="string")
    for c in ["Event Family","Event Type","Mode","Title","Description","Operational Impact","Trade / Commercial Impact"]:
        if c in df.columns:
            blob=blob.str.cat(df[c].fillna("").astype(str),sep=" ")
    include=(
        r"war|conflict|attack|missile|drone|piracy|hijack|boarding|seizure|interdiction|"
        r"smuggl|traffick|fraud|crime|theft|terror|sabotage|mine|sanction|enforcement|"
        r"weather|typhoon|hurricane|cyclone|flood|earthquake|wildfire|storm|low water|"
        r"grounding|collision|allision|capsize|sinking|fire|explosion|pollution|sar|"
        r"labour|industrial action|strike|protest|riot|civil unrest|closure|outage|"
        r"disruption|border closure|customs restriction|airspace closure|cyber|ransomware"
    )
    corporate=(
        r"new terminal|terminal opening|commissioning|new crane|crane order|equipment order|"
        r"vessel order|fleet order|acquisition|investment|capex announcement|earnings|"
        r"dividend|share buyback|service launch|office opening|warehouse opening"
    )
    hard_disruption=(
        r"attack|missile|drone|piracy|seizure|smuggl|fraud|crime|weather|typhoon|flood|"
        r"earthquake|grounding|collision|fire|explosion|strike|protest|closure|outage|"
        r"disruption|sanction|cyber|interdiction"
    )
    inc=blob.str.contains(include,case=False,regex=True,na=False)
    corp=blob.str.contains(corporate,case=False,regex=True,na=False)
    override=blob.str.contains(hard_disruption,case=False,regex=True,na=False)
    return df[inc & (~corp | override)].copy()

def clean_display_text(v):
    """Clean transport/database formatting before anything reaches the UI."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    s = str(v)
    # Remove both escaped and real line breaks/tabs used by source data or earlier renderers.
    s = s.replace("\\r\\n", " ").replace("\\n", " ").replace("\\r", " ").replace("\\t", " ")
    s = s.replace("\r\n", " ").replace("\n", " ").replace("\r", " ").replace("\t", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return "" if s.lower() in {"nan", "none", "<na>"} else s


RELATIONSHIP_LABELS = {
    "REGIONAL_SECURITY_EXPOSURE": "Regional security exposure",
    "NORTHERN_GULF_EXPOSURE": "Northern Gulf exposure",
    "DIRECT_SYSTEM_IMPACT": "Direct system impact",
    "REGIONAL_ESCALATION": "Regional escalation",
    "SECURITY_ADVISORY": "Security advisory",
    "RATE / ROUTE-RISK TRANSMISSION": "Rate / route-risk transmission",
    "AFFECTED_ASSET": "Affected asset",
    "AFFECTED_VESSEL": "Affected vessel",
    "OCCURRED_IN": "Occurred in",
    "DIRECTLY_AFFECTED": "Directly affected",
    "EXPOSED": "Exposed",
    "RELATED": "Related",
}


def humanize_relationship(v):
    s = clean_display_text(v)
    if not s:
        return ""
    if s in RELATIONSHIP_LABELS:
        return RELATIONSHIP_LABELS[s]
    # Internal enums become normal English while preserving slash/hyphen meaning.
    if re.fullmatch(r"[A-Z0-9_ /-]+", s):
        s = s.replace("_", " ").lower()
        return s[:1].upper() + s[1:]
    return s


def show_df(df, cols=None, height=420):
    if df is None or df.empty:
        st.markdown('<div class="pc-empty">No matching records in the current Excel model.</div>', unsafe_allow_html=True)
        return
    view = df.copy()
    if cols:
        cols = [c for c in cols if c in view.columns]
        view = view[cols]
    for c in view.columns:
        if str(c).lower() in {"relationship", "relationship type", "link type"}:
            view[c] = view[c].map(humanize_relationship)
        elif view[c].dtype == object:
            view[c] = view[c].map(clean_display_text)
    st.dataframe(view, use_container_width=True, hide_index=True, height=height)


def section(kicker, title, copy=None):
    st.markdown(f'<div class="pc-section-kicker">{kicker}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="pc-section-title">{title}</div>', unsafe_allow_html=True)
    if copy:
        st.markdown(f'<div class="pc-section-copy">{copy}</div>', unsafe_allow_html=True)


def event_card(row):
    title = clean_display_text(row.get("Title", "Untitled event"))
    date = row.get("Start Date", row.get("Date", ""))
    etype = row.get("Event Type", row.get("Event Family", "Event"))
    sev = clean_display_text(row.get("Severity", ""))
    loc = row.get("Location", row.get("Country / Countries", ""))
    body = row.get("Description", "")
    impact = row.get("Operational Impact", "")
    st.markdown(
        f'''<div class="pc-card pc-card-priority">
        <div class="pc-card-meta">{date} · {etype} · {sev} · {loc}</div>
        <div class="pc-card-title">{title}</div>
        <div class="pc-card-body">{body}</div>
        <div class="pc-card-impact"><b>Operational impact:</b> {impact}</div>
        </div>''',
        unsafe_allow_html=True,
    )


def canonical_port_id(link_id, link_name):
    lid=str(link_id or "").strip(); name=str(link_name or "").strip()
    if not ports.empty and "Port ID" in ports.columns:
        hit=ports[text_col(ports,"Port ID").eq(lid)]
        if hit.empty and name:
            hit=ports[text_col(ports,"Port / Facility").str.casefold().eq(name.casefold())]
        if hit.empty and name:
            hit=ports[text_col(ports,"Port / Facility").str.contains(name,case=False,regex=False,na=False)]
        if not hit.empty: return str(hit.iloc[0].get("Port ID",""))
    return ""

def render_connected_context(event_id):
    eid = str(event_id or "")
    links = event_asset_links[text_col(event_asset_links, "Event ID").eq(eid)] if not event_asset_links.empty else pd.DataFrame()
    clinks = event_company_links[text_col(event_company_links, "Event ID").eq(eid)] if not event_company_links.empty else pd.DataFrame()
    slinks = event_system_links[text_col(event_system_links, "Event ID").eq(eid)] if not event_system_links.empty else pd.DataFrame()

    if links.empty and clinks.empty and slinks.empty:
        st.markdown('<div class="pc-empty">No connected canonical coverage has been mapped yet.</div>', unsafe_allow_html=True)
        return

    if not links.empty:
        st.markdown("**Associated assets / ports**")
        for _, r in links.iterrows():
            name = clean_display_text(r.get("Asset", ""))
            typ = clean_display_text(r.get("Asset Type", "Asset")) or "Asset"
            rel = humanize_relationship(r.get("Relationship", ""))

            st.markdown(f"**{name}** · {typ}")
            if rel:
                st.caption(rel)

            pid = canonical_port_id(r.get("Asset ID", ""), name)
            if pid:
                pr = ports[text_col(ports, "Port ID").eq(pid)]
                if not pr.empty:
                    rr = pr.iloc[0]
                    bits = []
                    for c in ["Country", "Operator", "Facility Type", "Key Role"]:
                        v = clean_display_text(rr.get(c, ""))
                        if v:
                            bits.append(f"{c}: {v}")
                    if bits:
                        st.caption(" · ".join(bits[:4]))

    if not clinks.empty:
        st.markdown("**Associated companies**")
        for _, r in clinks.iterrows():
            cid = clean_display_text(r.get("Company ID", ""))
            name = clean_display_text(r.get("Company", ""))
            rel = humanize_relationship(r.get("Relationship", ""))

            st.markdown(f"**{name}**")
            if rel:
                st.caption(rel)

            if cid and not companies.empty and "Company ID" in companies.columns:
                cr = companies[text_col(companies, "Company ID").eq(cid)]
                if not cr.empty:
                    rr = cr.iloc[0]
                    bits = []
                    for c in ["HQ Country", "Ownership", "Business Segments", "Status"]:
                        v = clean_display_text(rr.get(c, ""))
                        if v:
                            bits.append(f"{c}: {v}")
                    if bits:
                        st.caption(" · ".join(bits[:4]))

    if not slinks.empty:
        st.markdown("**Related systems / corridors**")
        view = slinks.copy()
        if "Relationship" in view.columns:
            view["Relationship"] = view["Relationship"].map(humanize_relationship)
        show_df(view, ["System", "Relationship", "Confidence"], 180)



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
            "event_id,start_date,end_date,event_nature,event_domain,event_family,event_type,severity,status,mode,countries,location,title,description,operational_impact,commercial_impact,confidence,trade_relevance,intelligence_relevance,trade_visible,intelligence_visible,alert_worthy,record_status,source_id,metadata",
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

# Canonical vessel registry from Supabase.
@st.cache_data(show_spinner=False, ttl=60)
def _canonical_db_vessels():
    try:
        sb = pc_db_client(service=True)
        if sb is None:
            return pd.DataFrame()

        rows = pc_safe_rows(
            sb,
            "pc_mobile_assets",
            "mobile_asset_id,name,asset_type,subtype,imo,status,record_status,metadata",
            10000,
            order="name",
        )
        if not rows:
            return pd.DataFrame()

        out=[]
        for r in rows:
            meta=r.get("metadata") if isinstance(r.get("metadata"),dict) else {}
            research=meta.get("research_attributes") if isinstance(meta.get("research_attributes"),dict) else {}
            out.append({
                "Vessel ID":str(r.get("mobile_asset_id") or "").strip(),
                "Vessel Name":str(r.get("name") or "").strip(),
                "IMO":str(r.get("imo") or "").strip(),
                "Vessel Type":str(r.get("asset_type") or "").strip(),
                "Subtype / Class":str(r.get("subtype") or "").strip(),
                "Flag":str(research.get("flag") or meta.get("flag") or "").strip(),
                "Status":str(r.get("status") or r.get("record_status") or "").strip(),
                "Record Status":str(r.get("record_status") or "").strip(),
                "Metadata":meta,
            })
        return pd.DataFrame(out)
    except Exception:
        return pd.DataFrame()


# Core canonical datasets
companies = xl("01_core_entities.xlsx", "Companies")
ports = xl("02_maritime.xlsx", "Ports")
_legacy_vessels = xl("02_maritime.xlsx", "Vessels")
_db_vessels = _canonical_db_vessels()
if not _db_vessels.empty:
    if _legacy_vessels is None or _legacy_vessels.empty:
        vessels = _db_vessels
    else:
        _old=_legacy_vessels.copy()
        _new=_db_vessels.copy()
        _ids=set(_new["Vessel ID"].fillna("").astype(str)) if "Vessel ID" in _new.columns else set()
        _imos=set(_new["IMO"].fillna("").astype(str)) if "IMO" in _new.columns else set()
        _keep=pd.Series(True,index=_old.index)
        if "Vessel ID" in _old.columns and _ids:
            _keep &= ~_old["Vessel ID"].fillna("").astype(str).isin(_ids)
        if "IMO" in _old.columns and _imos:
            _keep &= ~_old["IMO"].fillna("").astype(str).isin(_imos)
        vessels=pd.concat([_old[_keep],_new],ignore_index=True,sort=False)
else:
    vessels=_legacy_vessels
vessel_restrictions = xl("02_maritime.xlsx", "Vessel Restrictions")
aircraft = xl("05_aviation.xlsx", "Aircraft Registry")
infra_assets = xl("06_infrastructure.xlsx", "Assets")
dry_ports = xl("06_infrastructure.xlsx", "Dry Ports")
economic_zones = xl("06_infrastructure.xlsx", "Economic Zones")

# Intelligence/event layer
news = xl("09_intelligence.xlsx", "News Registry")
strategic_events = xl("09_intelligence.xlsx", "Strategic Events")
observations = xl("09_intelligence.xlsx", "Event Observations")
monitoring = xl("09_intelligence.xlsx", "Monitoring")
disruption = xl("09_intelligence.xlsx", "Disruption Watch")
weather_labour = xl("09_intelligence.xlsx", "Weather Labour Events")
security_view = xl("09_intelligence.xlsx", "Security Product View")

# Sources/evidence
sources = xl("10_sources_evidence.xlsx", "Sources")
source_feeds = xl("10_sources_evidence.xlsx", "Source Feeds")

# Canonical events/hazards
# Normalized Supabase is authoritative; workbook-shaped data is fallback only.
_db_events, _db_event_locations = _canonical_db_event_frames()
if not _db_events.empty:
    hazard_events_raw = _db_events
else:
    hazard_events_raw = xl("13_events_hazards.xlsx", "Events")
hazard_events = intelligence_event_filter(hazard_events_raw)

if not _db_event_locations.empty:
    event_locations = _db_event_locations
else:
    event_locations = xl("13_events_hazards.xlsx", "Event Locations")
event_asset_links = xl("13_events_hazards.xlsx", "Event Asset Links")
event_company_links = xl("13_events_hazards.xlsx", "Event Company Links")
event_system_links = xl("13_events_hazards.xlsx", "Event System Links")
impact_chains = xl("13_events_hazards.xlsx", "Impact Chains")

# Sanctions / compliance
sanctions_authorities = xl("14_trade_policy_compliance.xlsx", "Sanctions Authorities")
sanctions_programmes = xl("14_trade_policy_compliance.xlsx", "Sanctions Programmes")
sanctions_designations = xl("14_trade_policy_compliance.xlsx", "Sanctions Designations")
sanctions_links = xl("14_trade_policy_compliance.xlsx", "Sanctions Entity Links")
compliance_regimes = xl("14_trade_policy_compliance.xlsx", "Compliance Regimes")
compliance_designations = xl("14_trade_policy_compliance.xlsx", "Compliance Designations")
compliance_exposure = xl("14_trade_policy_compliance.xlsx", "Compliance Exposure")
watchlist_taxonomy = xl("14_trade_policy_compliance.xlsx", "Watchlist Taxonomy")

# -----------------------------------------------------------------------------
# Sidebar architecture
# -----------------------------------------------------------------------------
st.sidebar.markdown(
    '''<div class="pc-sidebar-brand">
    <div class="brand">Power & Corridors Intelligence</div>
    <div class="name">P&C Intelligence</div>
    <div class="tag">From events to implications.</div>
    </div>''', unsafe_allow_html=True
)

st.sidebar.markdown("### Controls")
st.sidebar.radio(
    "Appearance",
    ["Dark","Light"],
    horizontal=True,
    key="pc_intel_appearance",
)
if st.sidebar.button("↻ Refresh database",use_container_width=True,key="pc_intel_refresh_database"):
    st.cache_data.clear()
    try:
        st.cache_resource.clear()
    except Exception:
        pass
    st.rerun()
st.sidebar.caption("Refresh after Power Admin applies new events, vessels, assets or relationships.")
st.sidebar.markdown("<div class='pc-rule'></div>", unsafe_allow_html=True)

NAV = {
    "INTELLIGENCE DESK": ["Operating Picture", "Regional Maps", "Alerts & Incidents"],
    "FORWARD MONITORING": ["Watch Areas", "Monitoring & Indicators"],
    "DOMAIN INTELLIGENCE": ["Regional Security", "Maritime Security", "Ports & Infrastructure", "Aviation & Movement", "Sanctions & Compliance"],
    "DISCOVERY": ["Intelligence Search", "Source Monitor"],
}

flat = [x for group in NAV.values() for x in group]
for group, items in NAV.items():
    st.sidebar.markdown(f"<div class='pc-section-kicker' style='margin-top:.8rem'>{group}</div>", unsafe_allow_html=True)
    for item in items:
        if st.sidebar.button(item, key=f"nav_{item}", use_container_width=True):
            st.session_state["pcintel_page"] = item

page = st.session_state.get("pcintel_page", "Operating Picture")
st.sidebar.markdown("<div class='pc-rule'></div>", unsafe_allow_html=True)
_bst=backend_status()
st.sidebar.caption(f"v3.1 migration · {_bst.get('mode','excel').title()} backend · shared canonical model")

with st.sidebar.expander("Data status", expanded=False):
    _hazard_status = data_file_status("13_events_hazards.xlsx")
    _intel_status = data_file_status("09_intelligence.xlsx")

    if _hazard_status["exists"] or _bst.get("mode")=="supabase":
        st.caption(f"Raw event universe: {len(hazard_events_raw):,}")
        st.caption(f"P&C Intelligence routed events: {len(hazard_events):,}")
        if _hazard_status["exists"]:
            st.caption(f"Workbook: {_hazard_status['size'] / 1024:.1f} KB · modified {_hazard_status['modified']}")
        if not hazard_events_raw.empty and "Start Date" in hazard_events_raw.columns:
            _latest_dt = pd.to_datetime(hazard_events_raw["Start Date"], errors="coerce").max()
            if pd.notna(_latest_dt):
                st.caption(f"Latest raw event date: {_latest_dt.strftime('%Y-%m-%d')}")
        corporate_leak = len(hazard_events[
            contains_any(hazard_events,["Event Family","Event Type","Title"],["new terminal","new crane","acquisition","investment","vessel order"])
        ]) if not hazard_events.empty else 0
        if corporate_leak:
            st.warning(f"{corporate_leak} possible corporate-development records still require classification review.")
        else:
            st.success("Strict Intelligence event gate active; routine corporate development excluded.")
    else:
        st.error("13_events_hazards.xlsx is missing from /data and Supabase is not serving the legacy mirror.")

    if _intel_status["exists"]:
        st.caption(f"Intelligence workbook: {_intel_status['size'] / 1024:.1f} KB")
    else:
        st.error("09_intelligence.xlsx is missing from /data.")

    if st.button("Refresh database", key="refresh_excel_data"):
        st.cache_data.clear()
        st.rerun()

# Header
st.markdown('<div class="pc-kicker">Power & Corridors Intelligence</div>', unsafe_allow_html=True)
st.markdown(f'<div class="pc-title">{page}</div>', unsafe_allow_html=True)
st.markdown('<div class="pc-deck">Decision-useful intelligence on geopolitical disruption, maritime security, trade corridors, aviation, sanctions, critical infrastructure and operational risk.</div>', unsafe_allow_html=True)
st.markdown('<div class="pc-rule"></div>', unsafe_allow_html=True)


def _watch_tokens(v):
    s=str(v or "").casefold()
    words=re.findall(r"[a-z0-9]+",s)
    stop={"and","the","of","to","in","for","with","from","area","region","ports","port","sea","gulf"}
    return [w for w in words if len(w)>=4 and w not in stop]

def watch_area_events(geography):
    if hazard_events.empty:
        return hazard_events
    toks=_watch_tokens(geography)
    if not toks:
        return hazard_events.iloc[0:0]
    mask=pd.Series(False,index=hazard_events.index)
    for c in ["Country / Countries","Location","Title","Description","Operational Impact","Trade / Commercial Impact"]:
        if c not in hazard_events.columns:
            continue
        s=hazard_events[c].fillna("").astype(str).str.casefold()
        for t in toks:
            mask |= s.str.contains(re.escape(t),na=False)
    return hazard_events[mask].copy()

def watch_area_related_assets(geography):
    toks=_watch_tokens(geography)
    out={}
    for label,df,cols in [
        ("Ports",ports,["Port / Facility","Country","Operator","Key Role"]),
        ("Dry ports",dry_ports,["Hub Name","Country","City / Region","Linked Seaports / Gateways"]),
    ]:
        if df is None or df.empty:
            continue
        mask=pd.Series(False,index=df.index)
        for c in cols:
            if c not in df.columns:
                continue
            s=df[c].fillna("").astype(str).str.casefold()
            for t in toks:
                mask |= s.str.contains(re.escape(t),na=False)
        hit=df[mask].head(12)
        if not hit.empty:
            out[label]=hit
    return out

def _split_indicators(v):
    s=clean_display_text(v)
    if not s:
        return []
    parts=re.split(r"[;•|]+",s)
    return [p.strip(" -") for p in parts if p.strip(" -")]

def render_watch_area_brief(rows,geography):
    if rows.empty:
        st.info("No active monitoring record for this area.")
        return

    rows=rows.reset_index(drop=True)
    if len(rows)>1:
        pick=st.selectbox(
            "Monitoring lens",range(len(rows)),
            format_func=lambda i:clean_display_text(rows.iloc[i].get("Title","Monitoring")),
            key="intel_watch_lens"
        )
        r=rows.iloc[pick]
    else:
        r=rows.iloc[0]

    st.markdown(f"## {clean_display_text(geography)}")
    c1,c2,c3,c4=st.columns(4)
    c1.metric("Status",clean_display_text(r.get("Status","")) or "—")
    c2.metric("Confidence",clean_display_text(r.get("Confidence","")) or "—")
    c3.metric("Horizon",clean_display_text(r.get("Time Horizon","")) or "—")
    c4.metric("Last reviewed",clean_display_text(r.get("Last Reviewed","")) or "—")

    focus=clean_display_text(r.get("What Is Being Monitored",""))
    notes=clean_display_text(r.get("Notes",""))
    trigger=clean_display_text(r.get("Trigger / Threshold",""))
    next_review=clean_display_text(r.get("Next Review / Milestone",""))

    st.markdown("### Current picture")
    extra=f"<div style='margin-top:10px;'>{notes}</div>" if notes else ""
    current_picture_html = (
        "<div class='pc-card'>"
        f"<div class='pc-label'>{clean_display_text(r.get('Family',''))}</div>"
        f"<div class='pc-big'>{clean_display_text(r.get('Title',''))}</div>"
        f"<div class='pc-search-details' style='margin-top:10px;'>{focus}</div>"
        f"{extra}"
        "</div>"
    )
    st.markdown(current_picture_html, unsafe_allow_html=True)

    indicators=_split_indicators(r.get("Key Indicators",""))
    lcol,rcol=st.columns([1.15,1])
    with lcol:
        st.markdown("### Priority indicators")
        if indicators:
            for n,item in enumerate(indicators[:8],1):
                st.markdown(f"**{n}. {item}**")
        else:
            st.caption("No priority indicators have been structured yet.")
    with rcol:
        st.markdown("### What would change the judgement?")
        review=f"<div class='pc-label' style='margin-top:12px;'>Next review</div><div>{next_review}</div>" if next_review else ""
        judgement_html = (
            "<div class='pc-card'>"
            "<div class='pc-label'>Trigger / threshold</div>"
            f"<div>{trigger or 'No explicit threshold has been recorded yet.'}</div>"
            f"{review}"
            "</div>"
        )
        st.markdown(judgement_html, unsafe_allow_html=True)

    ev=watch_area_events(geography)
    st.markdown("### Recent activity")
    if ev.empty:
        st.caption("No recent event records currently match this watch area.")
    else:
        if "Start Date" in ev.columns:
            ev=ev.sort_values("Start Date",ascending=False)
        show_df(ev,["Start Date","Event Type","Severity","Status","Location","Title","Operational Impact","Trade / Commercial Impact","Confidence"],300)

    related=watch_area_related_assets(geography)
    st.markdown("### Exposed / related coverage")
    if not related:
        st.caption("No canonical ports or inland hubs are yet mapped directly to this watch area.")
    else:
        if "Ports" in related:
            st.markdown("**Ports**")
            show_df(related["Ports"],["Port / Facility","Country","Operator","Facility Type","Key Role"],220)
        if "Dry ports" in related:
            st.markdown("**Dry ports / inland hubs**")
            show_df(related["Dry ports"],["Hub Name","Country","City / Region","Status","Linked Seaports / Gateways"],180)


# -----------------------------------------------------------------------------
# Regional security workspace helpers
# -----------------------------------------------------------------------------
REGIONAL_SECURITY_AREAS = {
    "Middle East / Gulf": {
        "center": (25.2, 51.5), "zoom": 4.2,
        "phrases": [
            "united arab emirates","uae","iran","iraq","saudi arabia","bahrain",
            "qatar","kuwait","oman","persian gulf","arabian gulf","gulf of oman",
            "strait of hormuz","hormuz","kharg","al-faw","dubai","abu dhabi",
            "fujairah","doha","muscat","ras tanura","jazan","jizan","red sea","bab el-mandeb","mocha","jeddah","yanbu"
        ],
    },
    "Black Sea": {
        "center": (43.1, 34.0), "zoom": 4.3,
        "phrases": [
            "black sea","sea of azov","azov","ukraine","russia","azerbaijan",
            "odesa","odessa","crimea","sevastopol","constanța","constanta",
            "varna","burgas","novorossiysk","kerch","taganrog","mariupol",
            "berdyansk","bosporus","bosphorus","turkish coast","danube delta"
        ],
    },
    "Mediterranean": {
        "center": (35.5, 18.0), "zoom": 3.4,
        "phrases": [
            "mediterranean","ionian","adriatic","aegean","crete","cyprus",
            "malta","libya","tunisia","algeria","italy","genoa","sicily",
            "greece","lebanon","israel","syria","levant","gibraltar",
            "balearic","marseille","barcelona","taranto","trieste"
        ],
    },
    "Baltic": {
        "center": (57.0, 19.0), "zoom": 4.0,
        "phrases": [
            "baltic sea","baltic","estonia","latvia","lithuania","tallinn",
            "riga","klaipeda","klaipėda","gdańsk","gdansk","gdynia",
            "kiel","gotland","gulf of finland","gulf of riga","kaliningrad"
        ],
    },
    "Caribbean": {
        "center": (18.0, -72.0), "zoom": 3.8,
        "phrases": [
            "caribbean","bahamas","haiti","jamaica","dominican republic",
            "puerto rico","cuba","trinidad","tobago","barbados","grenada",
            "martinique","guadeloupe","aruba","curaçao","curacao",
            "port-au-prince","varreux"
        ],
    },
    "Asia-Pacific": {
        "center": (18.0, 116.0), "zoom": 2.7,
        "phrases": [
            "asia-pacific","asia pacific","china","japan","taiwan","south korea",
            "north korea","philippines","indonesia","malaysia","singapore",
            "vietnam","thailand","australia","new zealand","hong kong",
            "okinawa","shanghai","zhejiang","taiwan strait","incheon",
            "sunda strait","jakarta","lampung","manila","south china sea",
            "east china sea"
        ],
    },
}

REGIONAL_OPERATIONAL_TERMS = [
    "security","conflict","attack","strike","drone","missile","mine","piracy",
    "armed robbery","seizure","boarding","interdiction","detention","explosion",
    "fire","casualty","grounding","collision","allision","capsiz","sinking",
    "navigation","hazard","weather","typhoon","storm","earthquake","volcano",
    "labour","industrial action","strike","closure","disruption","pollution",
    "spill","sar","rescue","disabled","disabling fire","port incident",
    "infrastructure incident","maritime"
]

def _regional_blob(df):
    if df is None or df.empty:
        return pd.Series(dtype="string")
    blob = pd.Series("", index=df.index, dtype="string")
    for c in [
        "Country / Countries","Location","Title","Description","Event Family",
        "Event Type","Mode","Operational Impact","Trade / Commercial Impact"
    ]:
        if c in df.columns:
            blob = blob.str.cat(text_col(df,c), sep=" ")
    return blob.str.casefold()

def regional_events(region_name, operational_only=True):
    """Return events relevant to a regional security theatre."""
    if hazard_events.empty or region_name not in REGIONAL_SECURITY_AREAS:
        return hazard_events.iloc[0:0].copy()
    df=hazard_events.copy()
    blob=_regional_blob(df)
    phrases=REGIONAL_SECURITY_AREAS[region_name]["phrases"]
    region_pattern="|".join(re.escape(p.casefold()) for p in phrases)
    mask=blob.str.contains(region_pattern,regex=True,na=False)

    if operational_only:
        op_pattern="|".join(re.escape(t.casefold()) for t in REGIONAL_OPERATIONAL_TERMS)
        mask &= blob.str.contains(op_pattern,regex=True,na=False)

    return df[mask].copy()

def regional_event_map_points(events):
    """Join the regional event set to canonical Event Locations for map rendering."""
    if events is None or events.empty or event_locations.empty:
        return pd.DataFrame()

    if "Event ID" not in events.columns or "Event ID" not in event_locations.columns:
        return pd.DataFrame()

    loc=event_locations.copy()
    loc["Latitude"]=pd.to_numeric(loc.get("Latitude"),errors="coerce")
    loc["Longitude"]=pd.to_numeric(loc.get("Longitude"),errors="coerce")
    loc=loc[loc["Latitude"].notna() & loc["Longitude"].notna()].copy()
    if loc.empty:
        return pd.DataFrame()

    cols=[
        c for c in [
            "Event ID","Start Date","Severity","Status","Event Family","Event Type",
            "Title","Operational Impact","Trade / Commercial Impact","Confidence"
        ] if c in events.columns
    ]
    pts=loc.merge(events[cols],on="Event ID",how="inner")
    if pts.empty:
        return pts

    pts["Incident"]=pts.get("Title","").map(clean_display_text)
    pts["Date"]=pts.get("Start Date","").astype(str).str[:10]
    pts["Mapped Location"]=pts.get("Location","").map(clean_display_text)
    pts["Severity Label"]=pts.get("Severity","").map(clean_display_text)
    pts["Operational"]=pts.get("Operational Impact","").map(clean_display_text)
    pts["Commercial"]=pts.get("Trade / Commercial Impact","").map(clean_display_text)
    pts["Map Accuracy"]=pts.get("Accuracy","").map(clean_display_text)
    return pts

def render_regional_incident_map(region_name, events):
    """Interactive incident map with hover details and a safe fallback."""
    pts=regional_event_map_points(events)

    st.markdown("### Incident map")
    if pts.empty:
        st.caption("No mapped coordinates are currently available for events in this regional view.")
        return pts

    cfg=REGIONAL_SECURITY_AREAS[region_name]

    # Fit the regional map to the actual plotted incidents rather than relying
    # on a fixed theatre centre. This prevents western Saudi / Red Sea points
    # such as Jazan from falling outside a Gulf-centred viewport.
    lat_min=float(pts["Latitude"].min())
    lat_max=float(pts["Latitude"].max())
    lon_min=float(pts["Longitude"].min())
    lon_max=float(pts["Longitude"].max())

    lat0=(lat_min+lat_max)/2
    lon0=(lon_min+lon_max)/2

    lat_span=max(lat_max-lat_min,0.8)
    lon_span=max(lon_max-lon_min,0.8)
    span=max(lat_span,lon_span)

    # Conservative zoom heuristic for a 500px-high regional map.
    if span >= 50:
        auto_zoom=2.0
    elif span >= 30:
        auto_zoom=2.5
    elif span >= 18:
        auto_zoom=3.0
    elif span >= 10:
        auto_zoom=3.6
    elif span >= 6:
        auto_zoom=4.1
    elif span >= 3:
        auto_zoom=4.8
    else:
        auto_zoom=5.6

    # Keep the theatre defaults as a ceiling only; never zoom in so far that
    # mapped incidents disappear from the initial frame.
    auto_zoom=min(auto_zoom,float(cfg["zoom"]))

    if pdk is not None:
        layer=pdk.Layer(
            "ScatterplotLayer",
            data=pts,
            get_position="[Longitude, Latitude]",
            get_radius=45000,
            radius_min_pixels=5,
            radius_max_pixels=16,
            pickable=True,
            auto_highlight=True,
            get_fill_color=[216,180,90,190],
            get_line_color=[240,224,180,255],
            line_width_min_pixels=1,
        )
        view=pdk.ViewState(
            latitude=lat0,
            longitude=lon0,
            zoom=auto_zoom,
            pitch=0,
            bearing=0,
        )
        tooltip={
            "html": (
                "<div style='max-width:360px;'>"
                "<b>{Incident}</b><br/>"
                "{Date} · {Severity Label}<br/>"
                "<b>Location:</b> {Mapped Location}<br/>"
                "<b>Operational impact:</b> {Operational}<br/>"
                "<span style='opacity:.75'>Map accuracy: {Map Accuracy}</span>"
                "</div>"
            ),
            "style":{
                "backgroundColor":"#101820",
                "color":"#F4EFE5",
                "fontSize":"12px"
            }
        }
        deck=pdk.Deck(
            layers=[layer],
            initial_view_state=view,
            tooltip=tooltip,
            map_style=None,
        )
        st.pydeck_chart(deck,use_container_width=True,height=500)
    else:
        # Streamlit's native map is less descriptive but keeps coordinates visible.
        fallback=pts.rename(columns={"Latitude":"lat","Longitude":"lon"})
        st.map(fallback[["lat","lon"]],latitude="lat",longitude="lon",use_container_width=True)

    st.caption(
        f"{len(pts)} mapped incident point{'s' if len(pts)!=1 else ''}. "
        "Map view automatically fits all plotted incidents in this regional tab. "
        "Hover over a point for incident details."
    )
    return pts

def render_regional_event_workspace(region_name):
    events=regional_events(region_name,operational_only=True)

    c1,c2,c3,c4=st.columns(4)
    c1.metric("Regional events",len(events))
    severe=events[text_col(events,"Severity").str.contains("High|Severe|Critical",case=False,regex=True,na=False)] if not events.empty else events
    c2.metric("High / severe",len(severe))
    active=events[text_col(events,"Status").str.contains("Active|Developing|Ongoing|Warning",case=False,regex=True,na=False)] if not events.empty else events
    c3.metric("Active / developing",len(active))
    mapped=regional_event_map_points(events)
    c4.metric("Mapped points",len(mapped))

    mapped_pts=render_regional_incident_map(region_name,events)

    st.markdown("### Regional incident record")
    if events.empty:
        st.markdown('<div class="pc-empty">No operational/security events currently match this regional theatre.</div>',unsafe_allow_html=True)
        return

    events=events.copy()
    if "Start Date" in events.columns:
        events["_regional_sort"]=pd.to_datetime(events["Start Date"],errors="coerce")
        events=events.sort_values("_regional_sort",ascending=False)

    q=st.text_input(
        "Search this region",
        placeholder="vessel, port, drone, piracy, grounding, sanctions...",
        key=f"regional_search_{region_name}"
    )
    if q.strip():
        mask=contains_any(
            events,
            ["Title","Description","Location","Country / Countries","Event Family","Event Type",
             "Operational Impact","Trade / Commercial Impact"],
            [re.escape(q.strip())]
        )
        events=events[mask].copy()

    show_df(
        events,
        ["Start Date","Event Family","Event Type","Severity","Status","Country / Countries",
         "Location","Title","Operational Impact","Confidence"],
        320
    )

    if events.empty:
        return

    detail=events.reset_index(drop=True)
    pick=st.selectbox(
        "Open regional incident",
        range(len(detail)),
        format_func=lambda i:f"{detail.iloc[i].get('Start Date','')} · {detail.iloc[i].get('Title','')}",
        key=f"regional_event_pick_{region_name}"
    )
    row=detail.iloc[pick]
    eid=str(row.get("Event ID","") or "")

    left,right=st.columns([1.15,1])
    with left:
        event_card(row)
        locs=event_locations[text_col(event_locations,"Event ID").eq(eid)] if not event_locations.empty else event_locations
        if not locs.empty:
            st.markdown("**Mapped location detail**")
            show_df(locs,["Location","Country","Latitude","Longitude","Accuracy","Notes"],180)

    with right:
        section("Connected coverage","Entities, assets, systems & impact chain")
        render_connected_context(eid)
        chains=impact_chains[text_col(impact_chains,"Event ID").eq(eid)] if not impact_chains.empty else impact_chains
        if not chains.empty:
            st.markdown("**Impact chain**")
            show_df(chains,["Step","Trigger","Direct Impact","Secondary Impact","Tertiary Impact","Strategic / Commercial Outcome"],220)

    # Preserve events with no coordinates: they remain visible in the incident record.
    mapped_ids=set(mapped_pts["Event ID"].astype(str)) if not mapped_pts.empty and "Event ID" in mapped_pts.columns else set()
    unmapped=events[~events["Event ID"].astype(str).isin(mapped_ids)].copy() if "Event ID" in events.columns else pd.DataFrame()
    if not unmapped.empty:
        with st.expander(f"Events without mapped coordinates ({len(unmapped)})"):
            show_df(unmapped,["Start Date","Severity","Country / Countries","Location","Title","Operational Impact"],240)


# -----------------------------------------------------------------------------
# 1. OPERATING PICTURE
# -----------------------------------------------------------------------------
if page == "Operating Picture":
    active_mon = monitoring[text_col(monitoring, "Status").str.contains("Active", case=False, na=False)] if not monitoring.empty else monitoring
    security_terms = ["Security", "Conflict", "Maritime", "Piracy", "Attack", "Ground", "Explosion", "SAR", "Pollution", "Drone", "Missile", "Seizure", "Boarding"]
    sec_events = hazard_events[contains_any(hazard_events, ["Event Family", "Event Type", "Mode", "Title"], security_terms)] if not hazard_events.empty else hazard_events
    high_events = hazard_events[text_col(hazard_events, "Severity").str.contains("High|Severe|Critical", case=False, regex=True, na=False)] if not hazard_events.empty else hazard_events
    pgsa = compliance_designations[text_col(compliance_designations, "Regime ID").eq("REGIME_PGSA")] if not compliance_designations.empty else compliance_designations
    marsec_feeds = source_feeds[text_col(source_feeds, "Default Event Families").str.contains("ground|collision|sar|pollution|casualty|maritime|fire|rescue", case=False, regex=True, na=False)] if not source_feeds.empty else source_feeds

    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("Active Monitors", len(active_mon))
    c2.metric("High / Severe Events", len(high_events))
    c3.metric("Security / MARSEC Events", len(sec_events))
    c4.metric("PGSA Designations", len(pgsa))
    c5.metric("Official MARSEC Feeds", len(marsec_feeds))

    left, right = st.columns([1.5,1])
    with left:
        section("01 · Immediate", "Priority operating picture", "Recent high-severity or security-relevant events from the shared event layer.")
        latest = hazard_events.copy()
        if not latest.empty and "Start Date" in latest.columns:
            latest["_date"] = pd.to_datetime(latest["Start Date"], errors="coerce")
            latest = latest.sort_values("_date", ascending=False)
            priority = latest[text_col(latest,"Severity").str.contains("High|Severe|Critical", case=False, regex=True, na=False)].head(5)
            if priority.empty:
                priority = latest.head(5)
            for _, r in priority.iterrows():
                event_card(r)
        else:
            st.markdown('<div class="pc-empty">No event records available.</div>', unsafe_allow_html=True)

    with right:
        section("04 · Forward", "Active monitoring", "What could change next: monitors, triggers and time horizons.")
        if not active_mon.empty:
            for _, r in active_mon.head(6).iterrows():
                st.markdown(
                    f'''<div class="pc-card">
                    <div class="pc-card-meta">{r.get('Family','')} · {r.get('Geography','')}</div>
                    <div class="pc-card-title">{r.get('Title','')}</div>
                    <div class="pc-card-body"><b>Monitoring:</b> {r.get('What Is Being Monitored','')}</div>
                    <div class="pc-card-impact"><b>Trigger:</b> {r.get('Trigger / Threshold','')}</div>
                    </div>''', unsafe_allow_html=True)
        else:
            st.markdown('<div class="pc-empty">No active monitoring records.</div>', unsafe_allow_html=True)

    section("Coverage", "Security domains in the current model")
    st.markdown("""
    <span class='pc-badge'>Maritime Security</span><span class='pc-badge'>Ports & Chokepoints</span>
    <span class='pc-badge'>Aviation & Movement</span><span class='pc-badge'>Sanctions & Compliance</span>
    <span class='pc-badge'>Weather & Natural Hazards</span><span class='pc-badge'>Labour & Civil Disruption</span>
    <span class='pc-badge'>Conflict Escalation</span><span class='pc-badge'>Critical Infrastructure</span>
    """, unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. ALERTS & INCIDENTS
# -----------------------------------------------------------------------------
elif page == "Alerts & Incidents":
    section("01 · Immediate", "Alerts & incidents", "Filter the event layer by severity, geography, mode and event family.")
    df = hazard_events.copy()
    if df.empty:
        show_df(df)
    else:
        f1,f2,f3,f4 = st.columns(4)
        families = ["All"] + sorted([x for x in text_col(df,"Event Family").unique() if x])
        severities = ["All"] + sorted([x for x in text_col(df,"Severity").unique() if x])
        countries = ["All"] + sorted([x for x in text_col(df,"Country / Countries").unique() if x])
        modes = ["All"] + sorted([x for x in text_col(df,"Mode").unique() if x])
        fam = f1.selectbox("Event family", families)
        sev = f2.selectbox("Severity", severities)
        country = f3.selectbox("Country / region", countries)
        mode = f4.selectbox("Mode", modes)
        if fam != "All": df = df[text_col(df,"Event Family").eq(fam)]
        if sev != "All": df = df[text_col(df,"Severity").eq(sev)]
        if country != "All": df = df[text_col(df,"Country / Countries").eq(country)]
        if mode != "All": df = df[text_col(df,"Mode").eq(mode)]
        if "Start Date" in df.columns:
            df["_sort"] = pd.to_datetime(df["Start Date"], errors="coerce")
            df = df.sort_values("_sort", ascending=False)
        show_df(df, ["Start Date","Event Family","Event Type","Severity","Status","Country / Countries","Location","Title","Operational Impact","Trade / Commercial Impact","Confidence"], 540)

        st.subheader("Selected incident")
        options = df["Title"].dropna().astype(str).tolist() if "Title" in df.columns else []
        if options:
            chosen = st.selectbox("Open event", options)
            row = df[df["Title"].astype(str).eq(chosen)].iloc[0]
            a,b = st.columns([1.2,1])
            with a:
                event_card(row)
            with b:
                eid = str(row.get("Event ID", ""))
                links = event_asset_links[text_col(event_asset_links,"Event ID").eq(eid)] if not event_asset_links.empty else event_asset_links
                clinks = event_company_links[text_col(event_company_links,"Event ID").eq(eid)] if not event_company_links.empty else event_company_links
                chains = impact_chains[text_col(impact_chains,"Event ID").eq(eid)] if not impact_chains.empty else impact_chains
                section("Connected coverage", "Linked entities & impact chain")
                render_connected_context(eid)
                if not chains.empty:
                    st.markdown("**Impact chain**")
                    show_df(chains, ["Step","Trigger","Direct Impact","Secondary Impact","Tertiary Impact","Strategic / Commercial Outcome"], 220)

# -----------------------------------------------------------------------------
# REGIONAL MAPS
# -----------------------------------------------------------------------------
elif page == "Regional Maps":
    section(
        "Operating picture",
        "Regional Maps",
        "Map-first theatre views using the shared canonical event and event-location layers."
    )
    st.caption(
        "Only events with supported coordinates are plotted. Unmapped incidents remain available "
        "in Regional Security rather than being assigned invented coordinates."
    )

    _region_names=list(REGIONAL_SECURITY_AREAS.keys())
    _map_tabs=st.tabs(_region_names)

    for _tab,_region_name in zip(_map_tabs,_region_names):
        with _tab:
            _events=regional_events(_region_name,operational_only=True)
            _mapped=regional_event_map_points(_events)

            _m1,_m2,_m3=st.columns(3)
            _m1.metric("Regional events",len(_events))
            _m2.metric("Mapped points",len(_mapped))
            if not _events.empty and not _mapped.empty and "Event ID" in _mapped.columns:
                _mapped_events=_mapped["Event ID"].fillna("").astype(str).nunique()
            else:
                _mapped_events=0
            _m3.metric("Events without map point",max(len(_events)-_mapped_events,0))

            render_regional_incident_map(_region_name,_events)

            if not _mapped.empty:
                st.markdown("### Mapped incident register")
                _cols=[c for c in [
                    "Start Date","Date","Title","Incident","Mapped Location",
                    "Severity","Severity Label","Status","Operational",
                    "Commercial","Map Accuracy"
                ] if c in _mapped.columns]
                if _cols:
                    show_df(_mapped,_cols,380)
            elif not _events.empty:
                st.info("Regional incidents are loaded, but none currently have supported coordinates.")
            else:
                st.info("No qualifying operational incidents are currently loaded for this theatre.")

# -----------------------------------------------------------------------------
# REGIONAL SECURITY
# -----------------------------------------------------------------------------
elif page == "Regional Security":
    section(
        "Regional Security",
        "Security theatres",
        "Regional operating picture built from the shared event, location, entity and impact-chain layers."
    )
    st.caption(
        "Mapped points use known event coordinates from Event Locations. "
        "Events without coordinates remain in the regional incident record below the map."
    )

    _jazan_loaded = (
        not hazard_events.empty
        and contains_any(
            hazard_events,
            ["Title", "Location", "Description"],
            ["Jazan", "Jizan", "Saudi Aramco"]
        ).any()
    )
    if _jazan_loaded:
        st.success("Latest Gulf dataset detected · Jazan refinery incident loaded.")
    else:
        st.warning(
            "Latest Gulf dataset not detected. Replace /data/13_events_hazards.xlsx "
            "with the latest workbook and use Data status → Refresh database."
        )

    region_names=list(REGIONAL_SECURITY_AREAS.keys())

    _black_sea_count = len(regional_events("Black Sea", operational_only=True))
    if _black_sea_count == 0:
        st.warning(
            "No Black Sea security records are currently loaded. The latest dataset should include "
            "Odesa, Natra/Zirkon in the Sea of Azov, and the Novorossiysk strike."
        )

    region_tabs=st.tabs(region_names)
    for tab,region_name in zip(region_tabs,region_names):
        with tab:
            render_regional_event_workspace(region_name)

# -----------------------------------------------------------------------------
# 3. WATCH AREAS
# -----------------------------------------------------------------------------
elif page == "Watch Areas":
    section("04 · Forward", "Watch Areas", "Area-based intelligence: current picture, priority indicators, thresholds, recent activity and exposed infrastructure.")
    mons=monitoring.copy()
    if mons.empty:
        st.info("No monitoring records available.")
    else:
        mons=mons[text_col(mons,"Status").str.contains("Active|Monitoring|Developing",case=False,regex=True,na=False)]
        geos=sorted([x for x in text_col(mons,"Geography").unique() if x])
        if not geos:
            st.info("No active watch areas are currently defined.")
        else:
            selected=st.selectbox("Watch area",geos,key="intel_watch_area")
            area_rows=mons[text_col(mons,"Geography").eq(selected)].copy()
            render_watch_area_brief(area_rows,selected)

            toks=_watch_tokens(selected)
            if not disruption.empty and toks:
                mask=pd.Series(False,index=disruption.index)
                for c in ["Country","Location / System","Issue","Potential Mode Impact","Potential Trade / Commercial Impact"]:
                    if c not in disruption.columns:
                        continue
                    s=disruption[c].fillna("").astype(str).str.casefold()
                    for t in toks:
                        mask |= s.str.contains(re.escape(t),na=False)
                darea=disruption[mask].copy()
                if not darea.empty:
                    st.markdown("### Active disruption watches in this area")
                    show_df(darea,["As Of","Family","Country","Location / System","Issue","Current Status","Potential Mode Impact","Potential Trade / Commercial Impact","Probability / Read","Time Horizon","Confidence"],260)

# -----------------------------------------------------------------------------
# 4. MONITORING & INDICATORS
# -----------------------------------------------------------------------------
elif page == "Monitoring & Indicators":
    section("04 · Forward", "Monitoring & Indicators", "Baselines, indicators and triggers that would strengthen, weaken or change the current judgement.")
    active_only = st.toggle("Active monitoring only", value=True)
    df = monitoring.copy()
    if active_only and not df.empty:
        df = df[text_col(df,"Status").str.contains("Active|Developing|Monitoring", case=False, regex=True, na=False)]
    show_df(df, ["Title","Family","Geography","Status","Start Date","Time Horizon","What Is Being Monitored","Key Indicators","Trigger / Threshold","Confidence","Last Reviewed","Next Review / Milestone"], 560)

# -----------------------------------------------------------------------------
# 5. MARITIME SECURITY
# -----------------------------------------------------------------------------
elif page == "Maritime Security":
    section(
        "Domain intelligence",
        "Maritime Security",
        "Operational picture of attacks, casualties, piracy, interdictions, navigation hazards and other incidents affecting commercial shipping."
    )

    maritime_terms = [
        "Maritime","Vessel","Piracy","Ground","Collision","Allision","SAR",
        "Pollution","Boarding","Seizure","Ship","Tanker","Container","Drone",
        "Missile","Mine","Capsiz","Sinking","Fire","Disabled"
    ]
    me = (
        hazard_events[
            contains_any(
                hazard_events,
                ["Event Family","Event Type","Mode","Title","Description"],
                maritime_terms
            )
        ].copy()
        if not hazard_events.empty else hazard_events.copy()
    )

    if not me.empty and "Start Date" in me.columns:
        me["_sort_date"] = pd.to_datetime(me["Start Date"], errors="coerce")
        me = me.sort_values("_sort_date", ascending=False)

    # Never treat workbook scaffolding/template rows as live intelligence.
    live_restrictions = vessel_restrictions.copy()
    if not live_restrictions.empty:
        template_mask = contains_any(
            live_restrictions,
            ["Restriction ID","Status","Vessel Name","IMO","Notes"],
            ["template","populate one row","none"]
        )
        live_restrictions = live_restrictions[~template_mask].copy()

    # Direct vessel exposure comes from actual event-to-asset relationships,
    # not from browsing the entire canonical vessel registry.
    vessel_event_links = event_asset_links.copy()
    if not vessel_event_links.empty:
        vessel_mask = (
            text_col(vessel_event_links,"Asset Type").str.contains("vessel|ship|tanker|carrier",case=False,regex=True,na=False)
            | text_col(vessel_event_links,"Asset ID").str.startswith("VESSEL",na=False)
        )
        vessel_event_links = vessel_event_links[vessel_mask].copy()

    exposed_event_ids = set(vessel_event_links["Event ID"].dropna().astype(str)) if not vessel_event_links.empty and "Event ID" in vessel_event_links.columns else set()
    exposed_vessel_names = set(vessel_event_links["Asset"].dropna().astype(str)) if not vessel_event_links.empty and "Asset" in vessel_event_links.columns else set()

    active_mask = (
        text_col(me,"Status").str.contains("active|developing|ongoing|warning|investigation",case=False,regex=True,na=False)
        if not me.empty else pd.Series(dtype=bool)
    )
    severe_mask = (
        text_col(me,"Severity").str.contains("critical|severe|high",case=False,regex=True,na=False)
        if not me.empty else pd.Series(dtype=bool)
    )

    m1,m2,m3,m4 = st.columns(4)
    m1.metric("Maritime incidents", len(me))
    m2.metric("Active / developing", int(active_mask.sum()) if len(active_mask) else 0)
    m3.metric("High / critical", int(severe_mask.sum()) if len(severe_mask) else 0)
    m4.metric("Named vessels affected", len(exposed_vessel_names))

    tabs = st.tabs([
        "Threat Picture",
        "Incidents",
        "Vessel Exposure",
        "Official Warnings & Sources"
    ])

    with tabs[0]:
        st.markdown("### Current maritime threat picture")
        if me.empty:
            st.info("No maritime-security incidents are currently loaded.")
        else:
            current = me[
                text_col(me,"Status").str.contains(
                    "active|developing|ongoing|warning|investigation|damaged|casualty",
                    case=False,regex=True,na=False
                )
            ].copy()
            if current.empty:
                current = me.head(8).copy()
            else:
                current = current.head(8)

            for idx, (_, row) in enumerate(current.iterrows()):
                title = clean_display_text(row.get("Title","")) or clean_display_text(row.get("Event Type",""))
                date = str(row.get("Start Date",""))[:10]
                severity = clean_display_text(row.get("Severity","")) or "—"
                status = clean_display_text(row.get("Status","")) or "—"
                location = clean_display_text(row.get("Location","")) or clean_display_text(row.get("Country / Countries","")) or "Location not specified"
                impact = clean_display_text(row.get("Operational Impact","")) or clean_display_text(row.get("Description",""))
                st.markdown(
                    (
                        "<div class='pc-card'>"
                        f"<div class='pc-label'>{date} · {severity} · {status}</div>"
                        f"<div class='pc-big'>{title}</div>"
                        f"<div style='margin-top:8px;'><b>{location}</b></div>"
                        f"<div class='pc-search-details' style='margin-top:8px;'>{impact}</div>"
                        "</div>"
                    ),
                    unsafe_allow_html=True
                )

            # Compact pattern read by event type / geography.
            c1,c2 = st.columns(2)
            with c1:
                st.markdown("#### Leading incident types")
                if "Event Type" in me.columns:
                    t = (
                        me["Event Type"].dropna().astype(str)
                        .value_counts().head(8).rename_axis("Incident Type").reset_index(name="Events")
                    )
                    show_df(t, ["Incident Type","Events"], 260)
            with c2:
                st.markdown("#### Leading operating areas")
                geo_col = "Country / Countries" if "Country / Countries" in me.columns else "Location"
                if geo_col in me.columns:
                    g = (
                        me[geo_col].dropna().astype(str)
                        .value_counts().head(8).rename_axis("Area").reset_index(name="Events")
                    )
                    show_df(g, ["Area","Events"], 260)

    with tabs[1]:
        st.markdown("### Incident record")
        q = st.text_input(
            "Search maritime incidents",
            placeholder="vessel, port, piracy, drone, grounding, tanker...",
            key="maritime_incident_search"
        )
        incident_view = me.copy()
        if q.strip() and not incident_view.empty:
            incident_view = incident_view[
                contains_any(
                    incident_view,
                    ["Title","Description","Event Type","Country / Countries","Location","Operational Impact"],
                    [q.strip()]
                )
            ].copy()

        show_df(
            incident_view,
            ["Start Date","Severity","Status","Event Type","Country / Countries",
             "Location","Title","Operational Impact","Confidence"],
            360
        )

        if not incident_view.empty:
            detail = incident_view.reset_index(drop=True)
            pick = st.selectbox(
                "Open incident",
                range(len(detail)),
                format_func=lambda i: f"{str(detail.iloc[i].get('Start Date',''))[:10]} · {detail.iloc[i].get('Title','')}",
                key="maritime_incident_pick"
            )
            row = detail.iloc[pick]
            eid = str(row.get("Event ID","") or "")
            left,right = st.columns([1.15,1])
            with left:
                event_card(row)
            with right:
                section("Connected coverage","Vessels, assets, companies & systems")
                render_connected_context(eid)
                chains = impact_chains[text_col(impact_chains,"Event ID").eq(eid)] if not impact_chains.empty else impact_chains
                if not chains.empty:
                    st.markdown("**Impact chain**")
                    show_df(
                        chains,
                        ["Trigger","Direct Impact","Secondary Impact","Tertiary Impact","Strategic / Commercial Outcome"],
                        220
                    )

    with tabs[2]:
        st.markdown("### Vessels exposed to maritime-security events")
        st.caption(
            "This is not the full vessel database. It shows vessels that are directly linked "
            "to security incidents or have a real live restriction/compliance record."
        )

        exposure_rows = []
        if not vessel_event_links.empty:
            event_lookup = (
                me.set_index("Event ID").to_dict("index")
                if not me.empty and "Event ID" in me.columns else {}
            )
            for _, link in vessel_event_links.iterrows():
                eid = str(link.get("Event ID","") or "")
                er = event_lookup.get(eid,{})
                exposure_rows.append({
                    "Vessel": clean_display_text(link.get("Asset","")),
                    "Relationship": clean_display_text(link.get("Relationship","")),
                    "Incident": clean_display_text(er.get("Title","")),
                    "Date": str(er.get("Start Date",""))[:10],
                    "Severity": clean_display_text(er.get("Severity","")),
                    "Status": clean_display_text(er.get("Status","")),
                    "Location": clean_display_text(er.get("Location","")),
                    "Event ID": eid,
                })

        exposure = pd.DataFrame(exposure_rows)
        if not exposure.empty:
            exposure = exposure.drop_duplicates(
                subset=["Vessel","Incident","Date"],keep="first"
            )
            show_df(
                exposure,
                ["Vessel","Date","Severity","Status","Relationship","Location","Incident"],
                340
            )
        else:
            st.info("No named vessels are directly linked to maritime-security incidents.")

        if not live_restrictions.empty:
            st.markdown("### Live vessel restrictions")
            show_df(
                live_restrictions,
                ["Vessel Name","IMO","Authority / Regime","Restriction Type",
                 "Status","Effective Date","Direct / Indirect","Basis","Last Verified"],
                260
            )
        else:
            st.caption(
                "No live vessel-restriction records are currently populated. "
                "Template rows are intentionally hidden. Sanctions and compliance designations "
                "are handled on the Sanctions & Compliance page."
            )

        vessel_choices = sorted(
            set(exposure["Vessel"].dropna().astype(str).tolist()) if not exposure.empty else set()
            | set(live_restrictions["Vessel Name"].dropna().astype(str).tolist()) if not live_restrictions.empty and "Vessel Name" in live_restrictions.columns else set()
        )
        vessel_choices = [x for x in vessel_choices if x and x.lower() not in {"none","nan"}]

        if vessel_choices:
            selected = st.selectbox(
                "Inspect exposed vessel",
                vessel_choices,
                key="maritime_exposed_vessel"
            )
            canonical = vessels[text_col(vessels,"Vessel Name").str.casefold().eq(selected.casefold())] if not vessels.empty else pd.DataFrame()
            if not canonical.empty:
                st.markdown("**Canonical vessel record**")
                show_df(
                    canonical,
                    ["Vessel Name","IMO","Vessel Type","Subtype / Class","Flag","Year Built",
                     "DWT","Status","Registered Owner (Legal)","Technical / ISM Manager","Completeness Note"],
                    180
                )
            if not exposure.empty:
                hist = exposure[exposure["Vessel"].str.casefold().eq(selected.casefold())]
                if not hist.empty:
                    st.markdown("**Security incident history**")
                    show_df(hist,["Date","Severity","Status","Location","Incident","Relationship"],220)

    with tabs[3]:
        st.markdown("### Official maritime-security reporting")
        sf = (
            source_feeds[
                contains_any(
                    source_feeds,
                    ["Source Name","Default Event Families","Coverage","Notes"],
                    ["Coast Guard","Maritime","SAR","Grounding","Collision","Pollution",
                     "Rescue","UKMTO","ReCAAP","Navy","Hydrographic","Navigation"]
                )
            ].copy()
            if not source_feeds.empty else source_feeds.copy()
        )

        if sf.empty:
            st.info("No official maritime-security source feeds are currently configured.")
        else:
            active_sources = sf[
                text_col(sf,"Active").str.contains("yes|true|active",case=False,regex=True,na=False)
            ] if "Active" in sf.columns else sf
            s1,s2 = st.columns(2)
            s1.metric("Configured sources",len(sf))
            s2.metric("Active sources",len(active_sources))
            show_df(
                sf,
                ["Source Name","Coverage","Default Event Families","Priority","Active","Last Checked","Notes"],
                430
            )

        st.caption(
            "This tab is the provenance/collection layer. Incident analysis belongs in the "
            "Threat Picture and Incidents tabs rather than being mixed with the source registry."
        )

# -----------------------------------------------------------------------------
# 6. PORTS & INFRASTRUCTURE
# -----------------------------------------------------------------------------
elif page == "Ports & Infrastructure":
    section(
        "Domain intelligence",
        "Ports & Critical Infrastructure",
        "Security and disruption picture for ports, terminals, energy nodes, logistics hubs and connected critical infrastructure."
    )

    port_terms = [
        "Port","Terminal","Infrastructure","Explosion","Strike","Closure","Drone",
        "Missile","Weather","Flood","Fire","Low water","Refinery","Pipeline",
        "Tank farm","Berth","Channel","Anchorage","Labour","Power outage","Collision",
        "Allision","Grounding"
    ]

    pe = (
        hazard_events[
            contains_any(
                hazard_events,
                ["Event Family","Event Type","Mode","Title","Description","Operational Impact"],
                port_terms
            )
        ].copy()
        if not hazard_events.empty else hazard_events.copy()
    )

    if not pe.empty and "Start Date" in pe.columns:
        pe["_sort_date"] = pd.to_datetime(pe["Start Date"], errors="coerce")
        pe = pe.sort_values("_sort_date", ascending=False)

    # Infrastructure exposure should be driven by actual event links, not by
    # dumping the whole asset registry into the intelligence product.
    infra_links = event_asset_links.copy()
    if not infra_links.empty:
        infra_mask = (
            text_col(infra_links,"Asset Type").str.contains(
                "port|terminal|infrastructure|refinery|pipeline|tank|hub|airport|rail|energy",
                case=False, regex=True, na=False
            )
            | text_col(infra_links,"Asset ID").str.startswith("PORT", na=False)
            | text_col(infra_links,"Asset ID").str.startswith("ASSET", na=False)
        )
        infra_links = infra_links[infra_mask].copy()

    active = (
        text_col(pe,"Status").str.contains(
            "active|developing|ongoing|warning|investigation|constrained|damaged|closed",
            case=False, regex=True, na=False
        )
        if not pe.empty else pd.Series(dtype=bool)
    )
    severe = (
        text_col(pe,"Severity").str.contains(
            "critical|severe|high", case=False, regex=True, na=False
        )
        if not pe.empty else pd.Series(dtype=bool)
    )

    linked_asset_names = (
        set(infra_links["Asset"].dropna().astype(str))
        if not infra_links.empty and "Asset" in infra_links.columns else set()
    )

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Infrastructure incidents", len(pe))
    c2.metric("Active / developing", int(active.sum()) if len(active) else 0)
    c3.metric("High / critical", int(severe.sum()) if len(severe) else 0)
    c4.metric("Named assets affected", len(linked_asset_names))

    tabs = st.tabs([
        "Threat Picture",
        "Incidents",
        "Asset Exposure",
        "Port Drill-down"
    ])

    with tabs[0]:
        st.markdown("### Current infrastructure threat picture")

        current = pe[
            text_col(pe,"Status").str.contains(
                "active|developing|ongoing|warning|investigation|damaged|constrained|closed",
                case=False, regex=True, na=False
            )
        ].copy() if not pe.empty else pe

        if current.empty and not pe.empty:
            current = pe.head(8).copy()
        elif not current.empty:
            current = current.head(8)

        if current.empty:
            st.info("No active port or infrastructure-security events are currently loaded.")
        else:
            for _, row in current.iterrows():
                title = clean_display_text(row.get("Title","")) or clean_display_text(row.get("Event Type",""))
                date = str(row.get("Start Date",""))[:10]
                severity = clean_display_text(row.get("Severity","")) or "—"
                status = clean_display_text(row.get("Status","")) or "—"
                location = clean_display_text(row.get("Location","")) or clean_display_text(row.get("Country / Countries","")) or "Location not specified"
                impact = clean_display_text(row.get("Operational Impact","")) or clean_display_text(row.get("Description",""))

                card = (
                    "<div class='pc-card'>"
                    f"<div class='pc-label'>{date} · {severity} · {status}</div>"
                    f"<div class='pc-big'>{title}</div>"
                    f"<div style='margin-top:8px;'><b>{location}</b></div>"
                    f"<div class='pc-search-details' style='margin-top:8px;'>{impact}</div>"
                    "</div>"
                )
                st.markdown(card, unsafe_allow_html=True)

        a,b = st.columns(2)
        with a:
            st.markdown("#### Leading incident types")
            if not pe.empty and "Event Type" in pe.columns:
                types = (
                    pe["Event Type"].dropna().astype(str)
                    .value_counts().head(8)
                    .rename_axis("Incident Type").reset_index(name="Events")
                )
                show_df(types, ["Incident Type","Events"], 250)

        with b:
            st.markdown("#### Leading affected areas")
            if not pe.empty and "Country / Countries" in pe.columns:
                areas = (
                    pe["Country / Countries"].dropna().astype(str)
                    .value_counts().head(8)
                    .rename_axis("Area").reset_index(name="Events")
                )
                show_df(areas, ["Area","Events"], 250)

    with tabs[1]:
        st.markdown("### Port & infrastructure incident record")
        q = st.text_input(
            "Search infrastructure incidents",
            placeholder="port, refinery, terminal, explosion, labour, weather...",
            key="infra_incident_search"
        )

        incident_view = pe.copy()
        if q.strip() and not incident_view.empty:
            incident_view = incident_view[
                contains_any(
                    incident_view,
                    ["Title","Description","Event Type","Country / Countries","Location","Operational Impact"],
                    [q.strip()]
                )
            ].copy()

        show_df(
            incident_view,
            ["Start Date","Severity","Status","Event Type","Country / Countries",
             "Location","Title","Operational Impact","Confidence"],
            360
        )

        if not incident_view.empty:
            detail = incident_view.reset_index(drop=True)
            pick = st.selectbox(
                "Open infrastructure incident",
                range(len(detail)),
                format_func=lambda i: f"{str(detail.iloc[i].get('Start Date',''))[:10]} · {detail.iloc[i].get('Title','')}",
                key="infra_incident_pick"
            )

            row = detail.iloc[pick]
            eid = str(row.get("Event ID","") or "")

            left,right = st.columns([1.15,1])
            with left:
                event_card(row)
            with right:
                section("Connected coverage","Ports, terminals, companies, systems & impact chain")
                render_connected_context(eid)

                chains = (
                    impact_chains[text_col(impact_chains,"Event ID").eq(eid)]
                    if not impact_chains.empty else impact_chains
                )
                if not chains.empty:
                    st.markdown("**Impact chain**")
                    show_df(
                        chains,
                        ["Trigger","Direct Impact","Secondary Impact",
                         "Tertiary Impact","Strategic / Commercial Outcome"],
                        220
                    )

    with tabs[2]:
        st.markdown("### Infrastructure exposed to security events")
        st.caption(
            "This view is event-driven. It shows infrastructure actually connected to a "
            "security/disruption event rather than the full infrastructure inventory."
        )

        event_lookup = (
            pe.set_index("Event ID").to_dict("index")
            if not pe.empty and "Event ID" in pe.columns else {}
        )

        exposure_rows = []
        if not infra_links.empty:
            for _, link in infra_links.iterrows():
                eid = str(link.get("Event ID","") or "")
                er = event_lookup.get(eid,{})
                if not er:
                    continue

                exposure_rows.append({
                    "Asset": clean_display_text(link.get("Asset","")),
                    "Asset Type": clean_display_text(link.get("Asset Type","")),
                    "Relationship": clean_display_text(link.get("Relationship","")),
                    "Date": str(er.get("Start Date",""))[:10],
                    "Severity": clean_display_text(er.get("Severity","")),
                    "Status": clean_display_text(er.get("Status","")),
                    "Location": clean_display_text(er.get("Location","")),
                    "Incident": clean_display_text(er.get("Title","")),
                })

        exposure = pd.DataFrame(exposure_rows)

        if exposure.empty:
            st.info("No infrastructure assets are directly linked to current security events.")
        else:
            exposure = exposure.drop_duplicates(
                subset=["Asset","Incident","Date"], keep="first"
            )

            show_df(
                exposure,
                ["Asset","Asset Type","Date","Severity","Status",
                 "Relationship","Location","Incident"],
                360
            )

            choices = sorted([
                x for x in exposure["Asset"].dropna().astype(str).unique()
                if x and x.lower() not in {"none","nan"}
            ])
            if choices:
                chosen = st.selectbox(
                    "Inspect exposed asset",
                    choices,
                    key="infra_exposed_asset"
                )
                hist = exposure[exposure["Asset"].eq(chosen)].copy()
                st.markdown(f"### {chosen}")
                show_df(
                    hist,
                    ["Date","Severity","Status","Location","Incident","Relationship"],
                    220
                )

    with tabs[3]:
        st.markdown("### Port drill-down")
        st.caption(
            "Local security context only. Deep commercial ownership, capacity and investment "
            "analysis remains in P&C Trade."
        )

        if ports.empty or "Port / Facility" not in ports.columns:
            st.info("No port records are currently loaded.")
        else:
            pnames = sorted(
                ports["Port / Facility"].dropna().astype(str).unique().tolist()
            )
            pname = st.selectbox(
                "Port / facility",
                pnames,
                key="intel_port_drilldown"
            )

            pr = ports[text_col(ports,"Port / Facility").eq(pname)].copy()
            show_df(
                pr,
                ["Port / Facility","Country","Operator","Facility Type",
                 "Key Role","Coverage Note"],
                170
            )

            pid = str(pr.iloc[0].get("Port ID","")) if not pr.empty else ""

            linked_terminals = (
                port_terminals[text_col(port_terminals,"Port ID").eq(pid)].copy()
                if pid and not port_terminals.empty else pd.DataFrame()
            )
            if not linked_terminals.empty:
                st.markdown("**Linked terminals**")
                show_df(
                    linked_terminals,
                    ["Terminal / Facility","City / Area","Asset Type","Cargo Profile",
                     "Primary Operator","Status","Confidence","Notes"],
                    220
                )

            related_ids = set()
            if pid and not event_asset_links.empty:
                related_ids |= set(
                    event_asset_links[
                        text_col(event_asset_links,"Asset ID").eq(pid)
                    ]["Event ID"].dropna().astype(str)
                )

            if pname and not pe.empty:
                name_hits = pe[
                    contains_any(
                        pe,
                        ["Location","Title","Description"],
                        [pname]
                    )
                ]
                if "Event ID" in name_hits.columns:
                    related_ids |= set(name_hits["Event ID"].dropna().astype(str))

            related = (
                pe[pe["Event ID"].astype(str).isin(related_ids)].copy()
                if related_ids and not pe.empty and "Event ID" in pe.columns
                else pd.DataFrame()
            )

            st.markdown("**Security & disruption history**")
            if related.empty:
                st.caption("No directly related security/disruption events are currently mapped to this port.")
            else:
                show_df(
                    related,
                    ["Start Date","Severity","Status","Event Type","Title","Operational Impact"],
                    260
                )

# -----------------------------------------------------------------------------
# 7. AVIATION & MOVEMENT
# -----------------------------------------------------------------------------
elif page == "Aviation & Movement":
    section("Domain intelligence", "Aviation & Movement", "Aircraft, carrier exposure, airspace/airport disruption and multimodal movement events from the same event model.")
    aviation_terms = ["Aviation","Airport","Aircraft","Airspace","Flight","UAV","Drone","GNSS","GPS","Typhoon","Volcanic","Ash"]
    ae = hazard_events[contains_any(hazard_events,["Event Family","Event Type","Mode","Title","Description","Operational Impact"], aviation_terms)] if not hazard_events.empty else hazard_events
    c1,c2 = st.columns(2)
    c1.metric("Aircraft registry records", len(aircraft))
    c2.metric("Aviation / movement events", len(ae))
    tab1,tab2 = st.tabs(["Operating Events", "Aircraft & Operators"])
    with tab1:
        show_df(ae, ["Start Date","Event Family","Event Type","Severity","Country / Countries","Location","Title","Operational Impact","Trade / Commercial Impact","Confidence"], 480)
    with tab2:
        show_df(aircraft, ["Registration","Aircraft Type","Variant","Role","Hub / Base","Country of Registration","Status","Owner / Lessor","Identity Confidence","Operator Confidence"], 500)

# -----------------------------------------------------------------------------
# 8. SANCTIONS & COMPLIANCE
# -----------------------------------------------------------------------------
elif page == "Sanctions & Compliance":
    section("Economic security", "Sanctions & Compliance", "Government sanctions remain distinct from operational compliance regimes such as PGSA, while both can be analysed against the same canonical vessels and companies.")
    t1,t2,t3,t4 = st.tabs(["Government Sanctions", "PGSA / Compliance", "Secondary Exposure", "Taxonomy"])
    with t1:
        c1,c2,c3 = st.columns(3)
        c1.metric("Authorities", len(sanctions_authorities))
        c2.metric("Programmes", len(sanctions_programmes))
        c3.metric("Designations", len(sanctions_designations))
        show_df(sanctions_designations, ["Designation Date","Target Type","Target Name","IMO / Identifier","Regime / Linkage","Status","Designation Basis / Link","Model Coverage Status"], 470)
    with t2:
        show_df(compliance_regimes, ["Regime","Authority / Sponsor","Jurisdiction / Geography","Regime Type","Status","Effective / Observed From","Enforcement Mechanisms","Legal / Analytical Note"], 230)
        show_df(compliance_designations, ["Date","Target Type","Target Name","IMO / Identifier","Status","Direct / Indirect","Reason / Basis","Verification","Notes"], 360)
    with t3:
        show_df(compliance_exposure, ["Source Vessel","Counterparty / Related Entity","Related Entity Type","Relationship","Event / Geography","Exposure Type","Status","Confidence","Analytical Note"], 500)
    with t4:
        show_df(watchlist_taxonomy, ["Class","Example","Authority Type","Classification Rule","Legal / Analytical Effect","Confidence"], 340)

# -----------------------------------------------------------------------------
# 9. INTELLIGENCE SEARCH
# -----------------------------------------------------------------------------
elif page == "Intelligence Search":
    section("Discovery", "Intelligence Search", "Search incidents, monitoring, vessels, ports, companies, sanctions/compliance and source feeds from the shared Excel model.")
    q = st.text_input("Search the P&C intelligence base", placeholder="e.g. Hormuz, Mraweh, Rotterdam, PGSA, Japan Coast Guard, drone...")
    if q and PC_USER_CONTEXT:
        if st.button("Save query to my workspace",key="save_intel_query"):
            ok,msg=save_workspace_query(PC_USER_CONTEXT,"INTELLIGENCE",q[:100],q,"search")
            (st.success if ok else st.warning)(msg)
    if q:
        datasets = [
            ("Events", hazard_events, ["Title","Description","Location","Country / Countries","Event Family","Event Type"]),
            ("Monitoring", monitoring, ["Title","Geography","What Is Being Monitored","Key Indicators","Trigger / Threshold"]),
            ("Vessels", vessels, ["Vessel Name","IMO","Vessel Type","Flag","Registered Owner (Legal)","Technical / ISM Manager"]),
            ("Ports", ports, ["Port / Facility","Country","Operator","Key Role"]),
            ("Companies", companies, ["Company","HQ Country","Ownership","Business Segments","Scale / Network Notes"]),
            ("Sanctions", sanctions_designations, ["Target Name","IMO / Identifier","Regime / Linkage","Designation Basis / Link"]),
            ("Compliance", compliance_designations, ["Target Name","IMO / Identifier","Reason / Basis","Notes"]),
            ("Compliance Exposure", compliance_exposure, ["Source Vessel","Counterparty / Related Entity","Exposure Type","Analytical Note"]),
            ("Sources", source_feeds, ["Source Name","Coverage","Default Event Families","Notes"]),
        ]
        found = 0
        for name, df, cols in datasets:
            if df.empty: continue
            mask = contains_any(df, cols, [q.replace("|", "\\|")])
            res = df[mask]
            if not res.empty:
                found += len(res)
                with st.expander(f"{name} · {len(res)} result(s)", expanded=name in ["Events","Monitoring"]):
                    show_df(res, cols, min(420, 80 + 36*len(res)))
        if found == 0:
            st.markdown('<div class="pc-empty">No matching records found.</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="pc-empty">Search across the intelligence base. Raw IDs remain internal; results are displayed using human-readable fields.</div>', unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 10. SOURCE MONITOR
# -----------------------------------------------------------------------------
elif page == "Source Monitor":
    section("Collection", "Source Monitor", "Official, commercial, media and OSINT collection sources feeding the intelligence cycle.")
    c1,c2,c3 = st.columns(3)
    c1.metric("Registered sources", len(sources))
    c2.metric("Monitored feeds", len(source_feeds))
    official = source_feeds[contains_any(source_feeds,["Source Name","Notes"],["Coast Guard","Official","DG Shipping","UKMTO","ReCAAP"])] if not source_feeds.empty else source_feeds
    c3.metric("Official / specialist MARSEC feeds", len(official))
    tab1,tab2 = st.tabs(["Collection Feeds", "Source Registry"])
    with tab1:
        show_df(source_feeds, ["Source Name","Coverage","Default Event Families","Priority","Active","Last Checked","Deduplication Rule","Notes"], 560)
    with tab2:
        show_df(sources, ["Publisher","Source Note","URL","Checked As Of","Source Type"], 560)

# Footer
st.markdown('<div class="pc-rule"></div>', unsafe_allow_html=True)
st.markdown('<div class="small-note">P&C Intelligence · Shared P&C data model · Dedicated security and operational intelligence interface.</div>', unsafe_allow_html=True)
