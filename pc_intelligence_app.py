import streamlit as st
import os, sys
import io
import textwrap
import pandas as pd
import re
try:
    import altair as alt
except Exception:
    alt = None
try:
    import pydeck as pdk
except Exception:
    pdk = None

# Publication renderer dependencies. Matplotlib is required for PNG/PDF export.
# Basemap is optional; when unavailable the renderer uses a geographic grid fallback.
try:
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch, ConnectionPatch
    import matplotlib.image as mpimg
except Exception:
    plt = None
    FancyBboxPatch = None
    ConnectionPatch = None
    mpimg = None

try:
    from mpl_toolkits.basemap import Basemap
except Exception:
    Basemap = None
from pathlib import Path
from datetime import datetime

SHARED_DIR = Path(__file__).resolve().parent / "shared"
if str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))
from pc_data_bridge import load_sheet as bridge_load_sheet, backend_status
from pc_workspace import save_query as save_workspace_query
from pc_db import client as pc_db_client, safe_rows as pc_safe_rows
from pc_drilldown import render_sidebar_search as pc_render_drilldown_search, render_active_drilldown as pc_render_active_drilldown, drilldown_button as pc_drilldown_button, set_drilldown as pc_set_drilldown
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


def event_card(row,key_prefix="event"):
    title = clean_display_text(row.get("Title", "Untitled event"))
    date = clean_display_text(row.get("Start Date", row.get("Date", "")))
    etype = clean_display_text(row.get("Event Type", row.get("Event Family", "Event")))
    sev = clean_display_text(row.get("Severity", ""))
    loc = clean_display_text(row.get("Location", row.get("Country / Countries", "")))
    body = clean_display_text(row.get("Description", ""))
    impact = clean_display_text(row.get("Operational Impact", ""))
    st.markdown(
        f'''<div class="pc-card pc-card-priority">
        <div class="pc-card-meta">{date} · {etype} · {sev} · {loc}</div>
        <div class="pc-card-title">{title}</div>
        <div class="pc-card-body">{body}</div>
        <div class="pc-card-impact"><b>Operational impact:</b> {impact}</div>
        </div>''',
        unsafe_allow_html=True,
    )

    eid = str(row.get("Event ID", row.get("event_id", "")) or "").strip()
    if eid:
        pc_drilldown_button(
            "event",
            eid,
            "Open full event context",
            key=f"{key_prefix}_event_card_dd_{eid}",
            use_container_width=True,
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

            aid = clean_display_text(r.get("Asset ID", ""))
            if aid:
                pc_drilldown_button("asset", aid, "Open asset", key=f"intel_asset_dd_{eid}_{aid}", use_container_width=True)

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

            if cid:
                pc_drilldown_button("entity", cid, "Open company", key=f"intel_company_dd_{eid}_{cid}", use_container_width=True)

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


# Canonical Actors & Networks layer from Supabase.
@st.cache_data(show_spinner=False, ttl=60)
def _canonical_db_actor_frames():
    actors = pd.DataFrame()
    links = pd.DataFrame()
    relationships = pd.DataFrame()
    designations = pd.DataFrame()
    try:
        sb = pc_db_client(service=True)
        if sb is None:
            return actors, links, relationships, designations

        arows = pc_safe_rows(
            sb, "v_pc_actor_directory",
            "actor_id,legacy_actor_id,canonical_name,short_name,actor_class,actor_subtype,status,primary_country,countries,description,confidence,designation_count,designations,linked_events,latest_event_date,high_critical_events,distinct_roles,roles_seen",
            5000, order="canonical_name",
        )
        if not arows:
            arows = pc_safe_rows(
                sb, "pc_actors",
                "actor_id,legacy_actor_id,canonical_name,short_name,actor_class,actor_subtype,status,primary_country,countries,description,confidence,designation_summary,metadata",
                5000, order="canonical_name",
            )
        if arows:
            actors = pd.DataFrame(arows)

        lrows = pc_safe_rows(
            sb, "pc_event_actor_links",
            "event_actor_link_id,event_id,actor_id,actor_role,attribution_status,confidence,link_basis,source_id,analyst_reviewed,metadata,created_at,updated_at",
            10000,
        )
        if lrows:
            links = pd.DataFrame(lrows)

        rrows = pc_safe_rows(
            sb, "pc_actor_relationships",
            "actor_relationship_id,from_actor_id,to_actor_id,relationship_type,relationship_class,status,confidence,basis,source_id,start_date,end_date,metadata",
            10000,
        )
        if rrows:
            relationships = pd.DataFrame(rrows)

        drows = pc_safe_rows(
            sb, "pc_actor_designations",
            "actor_designation_id,actor_id,authority,designation_name,designation_type,programme,effective_date,end_date,status,source_id,source_url,notes,confidence,metadata",
            10000,
        )
        if drows:
            designations = pd.DataFrame(drows)

        return actors, links, relationships, designations
    except Exception:
        return actors, links, relationships, designations


actor_directory, event_actor_links, actor_relationships, actor_designations = _canonical_db_actor_frames()


def _actor_list_text(v):
    if isinstance(v, (list, tuple, set)):
        return ", ".join([clean_display_text(x) for x in v if clean_display_text(x)])
    return clean_display_text(v)


def _actor_event_frame(actor_id):
    if event_actor_links.empty or hazard_events_raw.empty:
        return pd.DataFrame()
    links = event_actor_links[event_actor_links["actor_id"].astype(str).eq(str(actor_id))].copy()
    if links.empty or "Event ID" not in hazard_events_raw.columns:
        return pd.DataFrame()
    ev = hazard_events_raw.copy()
    ev["_event_id_join"] = ev["Event ID"].astype(str)
    links["_event_id_join"] = links["event_id"].astype(str)
    return links.merge(ev, on="_event_id_join", how="left", suffixes=("_link",""))


def _actor_relationship_frame(actor_id):
    if actor_relationships.empty or actor_directory.empty:
        return pd.DataFrame()
    aid = str(actor_id)
    rel = actor_relationships[
        actor_relationships["from_actor_id"].astype(str).eq(aid)
        | actor_relationships["to_actor_id"].astype(str).eq(aid)
    ].copy()
    if rel.empty:
        return rel
    names = dict(zip(actor_directory["actor_id"].astype(str), actor_directory["canonical_name"].astype(str)))
    rel["From Actor"] = rel["from_actor_id"].astype(str).map(names)
    rel["To Actor"] = rel["to_actor_id"].astype(str).map(names)
    rel["Relationship"] = rel["relationship_type"].map(humanize_relationship)
    rel["Class"] = rel.get("relationship_class", pd.Series(index=rel.index, dtype=object)).map(humanize_relationship)
    rel["Status"] = rel.get("status", pd.Series(index=rel.index, dtype=object))
    rel["Confidence"] = rel.get("confidence", pd.Series(index=rel.index, dtype=object))
    rel["Basis"] = rel.get("basis", pd.Series(index=rel.index, dtype=object))
    return rel


def _actor_designation_frame(actor_id):
    if actor_designations.empty:
        return pd.DataFrame()
    return actor_designations[actor_designations["actor_id"].astype(str).eq(str(actor_id))].copy()


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
    "INTELLIGENCE DESK": ["Operating Picture", "Intelligence Analytics", "Regional Maps", "Alerts & Incidents"],
    "PUBLICATIONS": ["Intelligence Brief Builder"],
    "ACTORS & NETWORKS": ["Actors & Networks"],
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
st.sidebar.caption(f"v3.3 actors · {_bst.get('mode','excel').title()} backend · shared canonical model")

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

pc_render_drilldown_search()

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


# Extend the Intelligence map selector beyond the original six theatres so
# Regional Maps provides the same all-region navigation concept as Trade.
REGIONAL_SECURITY_AREAS.update({
    "Global": {
        "center": (18.0, 12.0), "zoom": 1.1,
        "phrases": [],
    },
    "Africa": {
        "center": (2.0, 20.0), "zoom": 2.1,
        "phrases": ["africa","somalia","djibouti","gulf of guinea","nigeria","south africa","mozambique","egypt","libya","morocco"],
    },
    "Europe": {
        "center": (52.0, 12.0), "zoom": 2.7,
        "phrases": ["europe","united kingdom","france","germany","netherlands","belgium","spain","italy","poland","romania","bulgaria"],
    },
    "North America": {
        "center": (42.0, -101.0), "zoom": 2.5,
        "phrases": ["united states","usa","canada","mexico","great lakes","st lawrence","gulf coast","los angeles","long beach"],
    },
    "Central America & Caribbean": {
        "center": (18.0, -78.0), "zoom": 3.0,
        "phrases": ["panama","panama canal","haiti","jamaica","dominican republic","caribbean","cuba","bahamas"],
    },
    "South America": {
        "center": (-18.0, -60.0), "zoom": 2.5,
        "phrases": ["brazil","argentina","chile","colombia","peru","ecuador","venezuela","guyana","suriname"],
    },
    "South Asia": {
        "center": (21.0, 78.0), "zoom": 3.0,
        "phrases": ["india","pakistan","bangladesh","sri lanka","arabian sea","bay of bengal"],
    },
    "Central Asia": {
        "center": (43.0, 66.0), "zoom": 3.2,
        "phrases": ["kazakhstan","uzbekistan","turkmenistan","kyrgyzstan","tajikistan","caspian","middle corridor"],
    },
    "Arctic": {
        "center": (70.0, 10.0), "zoom": 2.1,
        "phrases": ["arctic","northern sea route","murmansk","arkhangelsk","churchill","svalbard","barents"],
    },
})


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


def _intel_focus_config(region,focus):
    areas=MAP_FOCUS_AREAS.get(region) or MAP_FOCUS_AREAS.get("Global",{})
    return areas.get(focus) or next(iter(areas.values()))

def _intel_focus_filter(df,focus_cfg):
    if df is None or df.empty:
        return df.copy() if df is not None else pd.DataFrame()
    phrases=focus_cfg.get("phrases") or []
    if not phrases:
        return df.copy()
    blob=_regional_blob(df)
    pattern="|".join(re.escape(x.casefold()) for x in phrases)
    return df[blob.str.contains(pattern,regex=True,na=False)].copy()


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
    if phrases:
        region_pattern="|".join(re.escape(p.casefold()) for p in phrases)
        mask=blob.str.contains(region_pattern,regex=True,na=False)
    else:
        mask=pd.Series(True,index=df.index)

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

def render_regional_incident_map(region_name, events, focus_cfg=None):
    """Interactive incident map with hover details and a safe fallback."""
    pts=regional_event_map_points(events)

    st.markdown("### Incident map")
    if pts.empty:
        st.caption("No mapped coordinates are currently available for events in this regional view.")
        return pts

    cfg=focus_cfg or REGIONAL_SECURITY_AREAS[region_name]

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
        event_card(row,key_prefix=f"event_detail_{eid}")
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



@st.cache_data(show_spinner=False,ttl=300)
def canonical_pgsa_vessels():
    """Return the PGSA canonical event that actually owns the linked-vessel set.

    Older PGSA event records can coexist with the newer canonical list event. Do
    not simply choose the newest/title match: choose the candidate with the
    strongest mobile-asset linkage so the 77-vessel list remains visible.
    """
    try:
        sb=pc_db_client(service=True)
    except Exception:
        return {},pd.DataFrame()

    candidates=[]
    seen=set()

    def add_candidates(rows):
        for r in rows or []:
            eid=str(r.get("event_id") or "").strip()
            if not eid or eid in seen:
                continue
            seen.add(eid)
            candidates.append(r)

    # Structured event type created by the canonical Hormuz package.
    try:
        add_candidates(
            sb.table("pc_events")
              .select("event_id,title,start_date,event_type,severity,status,location,description,operational_impact,commercial_impact")
              .eq("event_type","VESSEL_COMPLIANCE_LIST_UPDATE")
              .order("start_date",desc=True)
              .limit(20)
              .execute().data or []
        )
    except Exception:
        pass

    # Historical/duplicate PGSA titles may still exist, so gather all plausible
    # siblings and then choose the one with actual vessel links.
    for term in ["%PGSA%","%non-compliant%","%77 vessels%","%compliance list%"]:
        try:
            add_candidates(
                sb.table("pc_events")
                  .select("event_id,title,start_date,event_type,severity,status,location,description,operational_impact,commercial_impact")
                  .ilike("title",term)
                  .order("start_date",desc=True)
                  .limit(20)
                  .execute().data or []
            )
        except Exception:
            pass

    if not candidates:
        return {},pd.DataFrame()

    best_event={}
    best_links=[]
    for candidate in candidates:
        eid=str(candidate.get("event_id") or "")
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
            best_event=candidate
            best_links=links

    # If none have links, return the newest candidate for visibility/debugging.
    if not best_event:
        best_event=candidates[0]
        best_links=[]

    ids=[]
    seen_ids=set()
    for link in best_links:
        lid=str(link.get("linked_id") or "").strip()
        if lid and lid not in seen_ids:
            seen_ids.add(lid)
            ids.append(lid)

    if not ids:
        return best_event,pd.DataFrame()

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
            # Fallback for backends/adapters that do not expose .in_ consistently.
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
        df=df.drop_duplicates(subset=["Canonical ID"]).sort_values(["Vessel","IMO"],na_position="last").reset_index(drop=True)
    return best_event,df

def _is_compliance_watchlist_event(df):
    """Events that belong in compliance/watchlists rather than the lead operating picture."""
    if df is None or df.empty:
        return pd.Series(dtype=bool)
    combined=pd.Series("",index=df.index,dtype=str)
    for c in ["Event Type","Event Family","Title","Description"]:
        if c in df.columns:
            combined=combined.str.cat(df[c].fillna("").astype(str),sep=" ")
    return combined.str.contains(
        r"PGSA|COMPLIANCE_LIST|WATCHLIST|DESIGNATION|NON[- ]?COMPLIANT|SANCTION",
        case=False,regex=True,na=False
    )

def ranked_operating_picture(df,limit=5):
    """Rank current operational intelligence without allowing bulk watchlists to dominate."""
    if df is None or df.empty:
        return df
    x=df.copy()
    x["_date"]=pd.to_datetime(x.get("Start Date"),errors="coerce")
    severity=text_col(x,"Severity").str.casefold()
    sev_score=severity.map({
        "critical":40,"severe":35,"high":30,"medium":18,"moderate":15,"low":5
    }).fillna(10)

    # Recent first, but not merely newest.
    now=pd.Timestamp.now(tz=None).normalize()
    age=(now-x["_date"].dt.tz_localize(None)).dt.days
    recency=(25-age.clip(lower=0,upper=25)).fillna(0)

    impact=pd.Series(0,index=x.index,dtype=float)
    for c in ["Operational Impact","Trade / Commercial Impact","Description"]:
        if c in x.columns:
            present=x[c].fillna("").astype(str).str.strip().ne("")
            impact += present.astype(int)*3

    compliance=_is_compliance_watchlist_event(x)
    x["_priority_score"]=sev_score+recency+impact-(compliance.astype(int)*100)
    x=x.sort_values(["_priority_score","_date"],ascending=[False,False])
    return x.head(limit)


# -----------------------------------------------------------------------------
# Intelligence analytics helpers
# -----------------------------------------------------------------------------

COUNTRY_REGION_MAP = {
    # Middle East / Gulf
    "united arab emirates":"Middle East / Gulf","uae":"Middle East / Gulf","saudi arabia":"Middle East / Gulf",
    "iran":"Middle East / Gulf","iraq":"Middle East / Gulf","oman":"Middle East / Gulf","qatar":"Middle East / Gulf",
    "kuwait":"Middle East / Gulf","bahrain":"Middle East / Gulf","yemen":"Middle East / Gulf","israel":"Middle East / Gulf",
    "jordan":"Middle East / Gulf","lebanon":"Middle East / Gulf","syria":"Middle East / Gulf","palestine":"Middle East / Gulf",
    # Europe
    "united kingdom":"Europe","uk":"Europe","ireland":"Europe","france":"Europe","germany":"Europe","netherlands":"Europe",
    "belgium":"Europe","spain":"Europe","portugal":"Europe","italy":"Europe","greece":"Europe","turkey":"Europe","türkiye":"Europe",
    "poland":"Europe","romania":"Europe","bulgaria":"Europe","ukraine":"Europe","russia":"Europe","estonia":"Europe","latvia":"Europe",
    "lithuania":"Europe","finland":"Europe","sweden":"Europe","norway":"Europe","denmark":"Europe","iceland":"Europe","croatia":"Europe",
    "slovenia":"Europe","albania":"Europe","montenegro":"Europe","georgia":"Europe","cyprus":"Europe","malta":"Europe",
    # Asia-Pacific
    "china":"Asia-Pacific","japan":"Asia-Pacific","south korea":"Asia-Pacific","north korea":"Asia-Pacific","taiwan":"Asia-Pacific",
    "philippines":"Asia-Pacific","indonesia":"Asia-Pacific","malaysia":"Asia-Pacific","singapore":"Asia-Pacific","vietnam":"Asia-Pacific",
    "thailand":"Asia-Pacific","cambodia":"Asia-Pacific","myanmar":"Asia-Pacific","australia":"Asia-Pacific","new zealand":"Asia-Pacific",
    "papua new guinea":"Asia-Pacific","fiji":"Asia-Pacific","solomon islands":"Asia-Pacific","hong kong":"Asia-Pacific",
    # South Asia
    "india":"South Asia","pakistan":"South Asia","bangladesh":"South Asia","sri lanka":"South Asia","nepal":"South Asia","maldives":"South Asia",
    # Africa
    "egypt":"Africa","libya":"Africa","tunisia":"Africa","algeria":"Africa","morocco":"Africa","somalia":"Africa","djibouti":"Africa",
    "eritrea":"Africa","ethiopia":"Africa","kenya":"Africa","tanzania":"Africa","mozambique":"Africa","south africa":"Africa","namibia":"Africa",
    "angola":"Africa","nigeria":"Africa","ghana":"Africa","togo":"Africa","benin":"Africa","cameroon":"Africa","senegal":"Africa","sudan":"Africa",
    # North America
    "united states":"North America","usa":"North America","us":"North America","canada":"North America","mexico":"North America",
    # Central America & Caribbean
    "panama":"Central America & Caribbean","costa rica":"Central America & Caribbean","guatemala":"Central America & Caribbean",
    "honduras":"Central America & Caribbean","nicaragua":"Central America & Caribbean","belize":"Central America & Caribbean",
    "haiti":"Central America & Caribbean","jamaica":"Central America & Caribbean","cuba":"Central America & Caribbean",
    "dominican republic":"Central America & Caribbean","bahamas":"Central America & Caribbean","trinidad and tobago":"Central America & Caribbean",
    # South America
    "brazil":"South America","argentina":"South America","chile":"South America","colombia":"South America","peru":"South America",
    "ecuador":"South America","venezuela":"South America","guyana":"South America","suriname":"South America","uruguay":"South America",
    # Central Asia
    "kazakhstan":"Central Asia","uzbekistan":"Central Asia","turkmenistan":"Central Asia","kyrgyzstan":"Central Asia","tajikistan":"Central Asia",
}


def _analytics_country_tokens(v):
    """Normalize country/countries into displayable country tokens without exposing IDs."""
    s = clean_display_text(v)
    if not s:
        return []
    s = re.sub(r"[\[\]{}()\"']", "", s)
    parts = re.split(r"\s*[;,|]+\s*", s)
    out=[]
    for part in parts:
        part=part.strip()
        if not part:
            continue
        # Preserve country names containing spaces; slash is usually a geography separator.
        subparts=[x.strip() for x in re.split(r"\s+/\s+",part) if x.strip()]
        for x in subparts:
            if x and x.casefold() not in {y.casefold() for y in out}:
                out.append(x)
    return out


def _analytics_region_for_country(country):
    c=clean_display_text(country).casefold()
    if not c:
        return "Unspecified"
    if c in COUNTRY_REGION_MAP:
        return COUNTRY_REGION_MAP[c]
    # Conservative alias matching only after exact lookup.
    for key,region in COUNTRY_REGION_MAP.items():
        if len(key) >= 5 and (c == key or c.startswith(key+" ")):
            return region
    return "Other / Unclassified"


def _analytics_prepare_events(df):
    if df is None or df.empty:
        return pd.DataFrame()
    x=df.copy()
    x["_date"]=pd.to_datetime(x.get("Start Date"),errors="coerce",utc=True).dt.tz_convert(None)
    if "Country / Countries" in x.columns:
        x["_countries"]=x["Country / Countries"].map(_analytics_country_tokens)
    else:
        x["_countries"]=[[] for _ in range(len(x))]
    x["_primary_country"]=x["_countries"].map(lambda z: z[0] if z else "Unspecified")
    x["_regions"]=x["_countries"].map(lambda z: sorted(set(_analytics_region_for_country(c) for c in z)) if z else ["Unspecified"])
    x["_primary_region"]=x["_regions"].map(lambda z: z[0] if z else "Unspecified")
    return x


def _analytics_explode_geo(df, level="country"):
    if df is None or df.empty:
        return pd.DataFrame()
    x=df.copy()
    if level == "region":
        x["Breakdown"] = x["_regions"]
    else:
        x["Breakdown"] = x["_countries"]
    x=x.explode("Breakdown", ignore_index=True)
    x["Breakdown"]=x["Breakdown"].fillna("Unspecified").astype(str).replace("","Unspecified")
    if "Event ID" in x.columns:
        x=x.drop_duplicates(subset=["Event ID","Breakdown"])
    # Geo explosion can create repeated source indexes.  Always return a clean
    # RangeIndex because pandas.crosstab aligns Series on their index and newer
    # pandas versions reject duplicate labels during that alignment.
    return x.reset_index(drop=True)


def _analytics_severity_bucket(v):
    s=clean_display_text(v).casefold()
    if "critical" in s or "severe" in s:
        return "Critical / Severe"
    if "high" in s:
        return "High"
    if "medium" in s or "moderate" in s:
        return "Medium"
    if "low" in s:
        return "Low"
    return "Unspecified"


def _analytics_period_filter(df, period, custom_start=None, custom_end=None):
    if df is None or df.empty or "_date" not in df.columns:
        return df, None, None
    now=pd.Timestamp.now().normalize()
    if period == "24 hours":
        start=pd.Timestamp.now()-pd.Timedelta(hours=24); end=pd.Timestamp.now()
    elif period == "7 days":
        start=now-pd.Timedelta(days=6); end=pd.Timestamp.now()
    elif period == "30 days":
        start=now-pd.Timedelta(days=29); end=pd.Timestamp.now()
    elif period == "90 days":
        start=now-pd.Timedelta(days=89); end=pd.Timestamp.now()
    elif period == "Year to date":
        start=pd.Timestamp(year=now.year,month=1,day=1); end=pd.Timestamp.now()
    elif period == "Custom" and custom_start is not None and custom_end is not None:
        start=pd.Timestamp(custom_start); end=pd.Timestamp(custom_end)+pd.Timedelta(days=1)-pd.Timedelta(microseconds=1)
    else:
        return df.copy(), None, None
    return df[df["_date"].between(start,end,inclusive="both")].copy(),start,end


def _analytics_breakdown(df, level):
    if df is None or df.empty:
        return pd.DataFrame()
    if level in {"Region","Country"}:
        x=_analytics_explode_geo(df,"region" if level == "Region" else "country")
        grp_col="Breakdown"
    elif level == "Actor":
        x=df.explode("_actors").copy()
        x["Breakdown"]=x["_actors"].fillna("Unspecified").astype(str).replace("","Unspecified")
        grp_col="Breakdown"
    elif level == "Actor Role":
        x=df.explode("_actor_roles").copy()
        x["Breakdown"]=x["_actor_roles"].fillna("Unspecified").astype(str).replace("","Unspecified")
        grp_col="Breakdown"
    else:
        field={
            "Event Type":"Event Type","Event Family":"Event Family","Severity":"Severity",
            "Domain":"Event Domain","Mode":"Mode","Status":"Status"
        }.get(level,level)
        x=df.copy()
        if field not in x.columns:
            return pd.DataFrame()
        x["Breakdown"]=x[field].fillna("Unspecified").astype(str).replace("","Unspecified")
        grp_col="Breakdown"

    # Crosstab aligns its input Series by index.  Normalise the index here as
    # well so all grouping modes (including exploded geography) are safe on
    # pandas 2.x/3.x.
    x=x.reset_index(drop=True)
    if "Severity" in x.columns:
        x["_severity_bucket"]=x["Severity"].fillna("").map(_analytics_severity_bucket)
    else:
        x["_severity_bucket"]="Unspecified"
    if "Event ID" in x.columns:
        counts=x.groupby(grp_col)["Event ID"].nunique().rename("Count")
    else:
        counts=x.groupby(grp_col).size().rename("Count")
    sev=pd.crosstab(x[grp_col],x["_severity_bucket"])
    out=counts.to_frame().join(sev,how="left").reset_index().rename(columns={grp_col:level})
    total=max(int(out["Count"].sum()),1)
    out["% of breakdown"]=(out["Count"]/total*100).round(1)
    for c in ["Critical / Severe","High","Medium","Low","Unspecified"]:
        if c not in out.columns: out[c]=0
    return out.sort_values(["Count",level],ascending=[False,True]).reset_index(drop=True)


def _analytics_render_chart(df, chart_type, group_by, time_grain="Daily", top_n=15):
    if df is None or df.empty:
        st.info("No events match the current analytical filters.")
        return
    breakdown=_analytics_breakdown(df,group_by)
    if breakdown.empty:
        st.info("The selected grouping is not available in the current event model.")
        return

    if chart_type == "Line":
        x=df.dropna(subset=["_date"]).copy()
        if x.empty:
            st.info("Matching events do not contain usable dates for a time-series chart.")
            return
        if time_grain == "Daily":
            x["Period"]=x["_date"].dt.floor("D")
        elif time_grain == "Weekly":
            x["Period"]=x["_date"].dt.to_period("W").apply(lambda p:p.start_time)
        else:
            x["Period"]=x["_date"].dt.to_period("M").dt.to_timestamp()

        # Build series categories using same analytical grouping.
        if group_by == "Region":
            x=_analytics_explode_geo(x,"region").rename(columns={"Breakdown":"Series"})
        elif group_by == "Country":
            x=_analytics_explode_geo(x,"country").rename(columns={"Breakdown":"Series"})
        elif group_by == "Actor":
            x=x.explode("_actors").copy()
            x["Series"]=x["_actors"].fillna("Unspecified").astype(str).replace("","Unspecified")
        elif group_by == "Actor Role":
            x=x.explode("_actor_roles").copy()
            x["Series"]=x["_actor_roles"].fillna("Unspecified").astype(str).replace("","Unspecified")
        else:
            field={"Event Type":"Event Type","Event Family":"Event Family","Severity":"Severity","Domain":"Event Domain","Mode":"Mode","Status":"Status"}.get(group_by,group_by)
            x["Series"]=x[field].fillna("Unspecified").astype(str) if field in x.columns else "All events"
        top=x["Series"].value_counts().head(max(1,top_n)).index
        x=x[x["Series"].isin(top)]
        if "Event ID" in x.columns:
            chart_df=x.groupby(["Period","Series"])["Event ID"].nunique().reset_index(name="Count")
        else:
            chart_df=x.groupby(["Period","Series"]).size().reset_index(name="Count")
        if alt is None:
            pivot=chart_df.pivot(index="Period",columns="Series",values="Count").fillna(0)
            st.line_chart(pivot,use_container_width=True)
        else:
            chart=(alt.Chart(chart_df).mark_line(point=True).encode(
                x=alt.X("Period:T",title=None),y=alt.Y("Count:Q",title="Event count"),
                color=alt.Color("Series:N",title=group_by),
                tooltip=[alt.Tooltip("Period:T",title="Period"),alt.Tooltip("Series:N",title=group_by),alt.Tooltip("Count:Q",format=",d")]
            ).properties(height=420).interactive())
            st.altair_chart(chart,use_container_width=True)
        return

    plot_df=breakdown.head(max(1,top_n)).copy()
    category=group_by
    if chart_type == "Bar":
        if alt is None:
            st.bar_chart(plot_df.set_index(category)["Count"],use_container_width=True)
        else:
            chart=(alt.Chart(plot_df).mark_bar().encode(
                x=alt.X("Count:Q",title="Event count"),
                y=alt.Y(f"{category}:N",sort="-x",title=None),
                tooltip=[alt.Tooltip(f"{category}:N",title=category),alt.Tooltip("Count:Q",format=",d"),alt.Tooltip("% of breakdown:Q",format=".1f")]
            ).properties(height=max(320,min(620,45*len(plot_df)))))
            st.altair_chart(chart,use_container_width=True)
    else:  # Pie
        pie_df=plot_df.copy()
        if len(breakdown) > top_n:
            other=int(breakdown.iloc[top_n:]["Count"].sum())
            if other:
                pie_df=pd.concat([pie_df,pd.DataFrame([{category:"Other", "Count":other, "% of breakdown":round(other/max(int(breakdown["Count"].sum()),1)*100,1)}])],ignore_index=True)
        if alt is None:
            st.dataframe(pie_df[[category,"Count","% of breakdown"]],use_container_width=True,hide_index=True)
        else:
            chart=(alt.Chart(pie_df).mark_arc(innerRadius=70).encode(
                theta=alt.Theta("Count:Q"),color=alt.Color(f"{category}:N",title=group_by),
                tooltip=[alt.Tooltip(f"{category}:N",title=group_by),alt.Tooltip("Count:Q",format=",d"),alt.Tooltip("% of breakdown:Q",format=".1f")]
            ).properties(height=430))
            st.altair_chart(chart,use_container_width=True)


# -----------------------------------------------------------------------------
# Publication builder helpers
# -----------------------------------------------------------------------------
PUBLICATION_REGIONS = {
    "Global": {
        "phrases": [],
        "bounds": (-170, 170, -58, 78),
    },
    "GCC": {
        "phrases": [
            "united arab emirates", "uae", "saudi arabia", "oman", "qatar",
            "bahrain", "kuwait", "abu dhabi", "dubai", "fujairah", "jeddah",
            "jazan", "jizan", "yanbu", "doha", "muscat", "manama"
        ],
        "bounds": (32, 61, 12, 33),
    },
    "Middle East": {
        "phrases": [
            "united arab emirates", "uae", "saudi arabia", "oman", "qatar", "bahrain",
            "kuwait", "iran", "iraq", "yemen", "israel", "palestine", "gaza",
            "jordan", "lebanon", "syria", "red sea", "gulf of oman", "hormuz",
            "arabian gulf", "persian gulf", "bab el-mandeb"
        ],
        "bounds": (28, 64, 10, 39),
    },
    "Red Sea / Bab el-Mandeb": {
        "phrases": [
            "red sea", "bab el-mandeb", "yemen", "houthi", "jeddah", "yanbu", "jazan",
            "jizan", "djibouti", "eritrea", "sudan", "suez", "aqaba", "mocha"
        ],
        "bounds": (30, 47, 8, 31),
    },
    "Black Sea": {
        "phrases": [
            "black sea", "sea of azov", "ukraine", "russia", "crimea", "odesa", "odessa",
            "sevastopol", "novorossiysk", "constanta", "constanța", "varna", "burgas",
            "bosporus", "bosphorus", "danube delta", "turkish coast"
        ],
        "bounds": (26, 44, 39, 48.8),
    },
    "Mediterranean": {
        "phrases": [
            "mediterranean", "ionian", "adriatic", "aegean", "crete", "cyprus", "malta",
            "libya", "tunisia", "algeria", "italy", "sicily", "greece", "lebanon",
            "israel", "syria", "gibraltar", "marseille", "barcelona"
        ],
        "bounds": (-7, 39, 29, 47),
    },
    "Europe": {
        "phrases": [
            "europe", "united kingdom", "uk", "france", "germany", "netherlands", "belgium",
            "spain", "italy", "poland", "romania", "bulgaria", "greece", "norway", "sweden",
            "finland", "denmark", "baltic", "black sea", "mediterranean", "ukraine"
        ],
        "bounds": (-13, 42, 33, 72),
    },
    "Africa": {
        "phrases": [
            "africa", "egypt", "libya", "tunisia", "algeria", "morocco", "sudan", "djibouti",
            "eritrea", "ethiopia", "somalia", "kenya", "tanzania", "mozambique", "south africa",
            "nigeria", "ghana", "angola", "congo"
        ],
        "bounds": (-20, 55, -38, 38),
    },
    "Asia-Pacific": {
        "phrases": [
            "china", "japan", "taiwan", "south korea", "north korea", "philippines", "indonesia",
            "malaysia", "singapore", "vietnam", "thailand", "australia", "new zealand", "hong kong",
            "south china sea", "east china sea", "asia-pacific", "asia pacific"
        ],
        "bounds": (88, 180, -48, 55),
    },
    "North America": {
        "phrases": [
            "united states", "usa", "u.s.", "canada", "mexico", "alaska", "great lakes",
            "gulf of mexico", "panama canal"
        ],
        "bounds": (-170, -52, 8, 76),
    },
    "South America": {
        "phrases": [
            "south america", "brazil", "argentina", "chile", "peru", "ecuador", "colombia",
            "venezuela", "uruguay", "paraguay", "bolivia", "guyana", "suriname"
        ],
        "bounds": (-84, -32, -57, 14),
    },
}


def _publication_blob(df):
    if df is None or df.empty:
        return pd.Series(dtype="string")
    blob = pd.Series("", index=df.index, dtype="string")
    for c in [
        "Country / Countries", "Location", "Title", "Description", "Event Family", "Event Type",
        "Mode", "Operational Impact", "Trade / Commercial Impact"
    ]:
        if c in df.columns:
            blob = blob.str.cat(text_col(df, c), sep=" ")
    return blob.str.casefold()


def publication_region_events(region_name):
    """Return P&C Intelligence-routed events for the selected publication geography."""
    if hazard_events is None or hazard_events.empty:
        return pd.DataFrame()
    df = hazard_events.copy()
    cfg = PUBLICATION_REGIONS.get(region_name, PUBLICATION_REGIONS["Global"])
    phrases = cfg.get("phrases") or []
    if phrases:
        blob = _publication_blob(df)
        pattern = "|".join(re.escape(str(p).casefold()) for p in phrases)
        df = df[blob.str.contains(pattern, regex=True, na=False)].copy()
    if "Start Date" in df.columns:
        df["_publication_date"] = pd.to_datetime(df["Start Date"], errors="coerce", utc=True).dt.tz_convert(None)
        df = df.sort_values("_publication_date", ascending=False)
    return df


def _meta_value(row, keys):
    meta = row.get("Metadata", {}) if hasattr(row, "get") else {}
    if not isinstance(meta, dict):
        return ""
    # Support both flat and nested enrichment payloads without binding the UI to one loader version.
    pools = [meta]
    for nested_key in ["ai_enrichment", "enrichment", "publication", "analysis"]:
        nested = meta.get(nested_key)
        if isinstance(nested, dict):
            pools.append(nested)
    for pool in pools:
        for key in keys:
            v = pool.get(key)
            if v not in (None, "", [], {}):
                return clean_display_text(v)
    return ""


def publication_summary(row):
    """Prefer the loader's 60–90 word enrichment; use sourced event text only as a fallback."""
    for c in [
        "Brief 75", "Brief 60-90", "AI Summary 60-90", "Summary 60-90",
        "Publication Summary", "Intelligence Summary"
    ]:
        if c in row.index:
            v = clean_display_text(row.get(c, ""))
            if v:
                return v
    v = _meta_value(row, [
        "brief_75", "brief75", "summary_60_90", "summary_60-90", "ai_summary_60_90",
        "publication_summary", "intelligence_summary"
    ])
    if v:
        return v

    # Backward-compatible fallback for records ingested before narrative enrichment became mandatory.
    pieces = []
    for c in ["Description", "Operational Impact", "Trade / Commercial Impact"]:
        val = clean_display_text(row.get(c, ""))
        if val and val not in pieces:
            pieces.append(val)
    text = " ".join(pieces).strip()
    if not text:
        return "No 60–90 word publication summary has been loaded for this event."
    words = text.split()
    return " ".join(words[:90])


def publication_summary_word_count(row):
    return len(publication_summary(row).split())


def publication_event_point(event_id):
    if event_locations is None or event_locations.empty or not event_id:
        return None
    locs = event_locations[text_col(event_locations, "Event ID").eq(str(event_id))].copy()
    if locs.empty:
        return None
    locs["Latitude"] = pd.to_numeric(locs.get("Latitude"), errors="coerce")
    locs["Longitude"] = pd.to_numeric(locs.get("Longitude"), errors="coerce")
    locs = locs[locs["Latitude"].notna() & locs["Longitude"].notna()]
    if locs.empty:
        return None
    r = locs.iloc[0]
    return float(r["Latitude"]), float(r["Longitude"]), clean_display_text(r.get("Location", ""))


def _publication_logo_path():
    candidates = [
        ROOT / "assets" / "power-corridors-logo-dark-matched-transparent.png",
        ROOT / "assets" / "power-corridors-logo-light-matched-transparent.png",
        ROOT / "assets" / "power-corridors-logo-dark-matched-transparent(1).png",
        ROOT / "assets" / "power-corridors-logo-light-matched-transparent(3).png",
        ROOT / "power-corridors-logo-dark-matched-transparent.png",
        ROOT / "power-corridors-logo-light-matched-transparent.png",
    ]
    for p in candidates:
        if p.exists():
            return p
    for base in [ROOT / "assets", ROOT]:
        if base.exists():
            hits = sorted(base.glob("power*corridors*logo*.png"))
            if hits:
                return hits[0]
    return None


def _wrapped(text, width):
    return "\n".join(textwrap.wrap(clean_display_text(text), width=width, break_long_words=False, break_on_hyphens=False))


def render_intelligence_brief(selected_rows, region_name, publication_date, output_format="png"):
    """Render one landscape P&C Intelligence brief. Returns PNG/PDF bytes."""
    if plt is None:
        raise RuntimeError("Matplotlib is required for publication export.")
    rows = [r for r in selected_rows]
    if len(rows) != 4:
        raise ValueError("Exactly four stories are required for this publication format.")

    bg = "#081018"
    panel = "#101922"
    line = "#30404d"
    ivory = "#f1ede3"
    muted = "#aeb6bb"
    gold = "#d4af57"
    cyan = "#1888b4"

    fig = plt.figure(figsize=(16, 9), facecolor=bg)
    canvas = fig.add_axes([0, 0, 1, 1])
    canvas.set_xlim(0, 1); canvas.set_ylim(0, 1); canvas.axis("off")

    # Header / brand
    logo = _publication_logo_path()
    if logo is not None and mpimg is not None:
        try:
            ax_logo = fig.add_axes([0.035, 0.878, 0.265, 0.095])
            ax_logo.imshow(mpimg.imread(str(logo)))
            ax_logo.axis("off")
        except Exception:
            pass
    canvas.text(0.50, 0.945, "P&C INTELLIGENCE", ha="center", va="center", color=ivory,
                fontsize=24, fontweight="bold")
    canvas.text(0.50, 0.908, region_name.upper(), ha="center", va="center", color=gold,
                fontsize=15, fontweight="bold")
    canvas.text(0.965, 0.945, pd.to_datetime(publication_date).strftime("%d %B %Y"),
                ha="right", va="center", color=muted, fontsize=10)
    canvas.plot([0.035, 0.965], [0.865, 0.865], color=line, lw=1)

    # Map occupies centre 44% of the page.
    map_ax = fig.add_axes([0.285, 0.19, 0.43, 0.62], facecolor=bg)
    lon_min, lon_max, lat_min, lat_max = PUBLICATION_REGIONS[region_name]["bounds"]
    map_ax.set_xlim(lon_min, lon_max); map_ax.set_ylim(lat_min, lat_max)
    map_ax.set_facecolor(bg)
    for sp in map_ax.spines.values():
        sp.set_edgecolor(line)
    map_ax.tick_params(colors=muted, labelsize=6)

    m = None
    if Basemap is not None:
        try:
            m = Basemap(
                projection="cyl", llcrnrlon=lon_min, urcrnrlon=lon_max,
                llcrnrlat=lat_min, urcrnrlat=lat_max, resolution="c", ax=map_ax
            )
            m.drawmapboundary(fill_color=bg, color=line, linewidth=0.7)
            m.fillcontinents(color="#122a37", lake_color=bg, zorder=1)
            m.drawcoastlines(color="#4e7487", linewidth=0.55, zorder=2)
            m.drawcountries(color="#355262", linewidth=0.35, zorder=2)
        except Exception:
            m = None
    if m is None:
        map_ax.grid(color=line, alpha=.35, linewidth=.5)
        map_ax.set_xlabel("Longitude", color=muted, fontsize=7)
        map_ax.set_ylabel("Latitude", color=muted, fontsize=7)

    # Four story cards: two left, two right. Each card gets a line from its mapped event point.
    card_specs = [
        (0.035, 0.56, 0.225, 0.27),
        (0.035, 0.23, 0.225, 0.27),
        (0.74, 0.56, 0.225, 0.27),
        (0.74, 0.23, 0.225, 0.27),
    ]
    card_targets = [
        (0.26, 0.695), (0.26, 0.365), (0.74, 0.695), (0.74, 0.365)
    ]

    for idx, (row, spec) in enumerate(zip(rows, card_specs), start=1):
        x, y, w, h = spec
        patch = FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0.006,rounding_size=0.008",
            transform=canvas.transAxes, facecolor=panel, edgecolor=line, linewidth=0.8
        )
        canvas.add_patch(patch)

        title = clean_display_text(row.get("Title", "Untitled event"))
        country = clean_display_text(row.get("Country / Countries", ""))
        etype = clean_display_text(row.get("Event Type", row.get("Event Family", "Event")))
        severity = clean_display_text(row.get("Severity", ""))
        summary = publication_summary(row)

        canvas.text(x + 0.012, y + h - 0.026, f"{country or region_name} · {etype}".upper(),
                    transform=canvas.transAxes, ha="left", va="top", color=gold,
                    fontsize=7.5, fontweight="bold")
        canvas.text(x + 0.012, y + h - 0.060, _wrapped(title, 33),
                    transform=canvas.transAxes, ha="left", va="top", color=ivory,
                    fontsize=10.5, fontweight="bold", linespacing=1.08)
        canvas.text(x + 0.012, y + h - 0.115, _wrapped(summary, 43),
                    transform=canvas.transAxes, ha="left", va="top", color=muted,
                    fontsize=7.45, linespacing=1.18)
        if severity:
            canvas.text(x + w - 0.012, y + 0.014, severity.upper(),
                        transform=canvas.transAxes, ha="right", va="bottom", color=cyan,
                        fontsize=7, fontweight="bold")

        point = publication_event_point(row.get("Event ID", ""))
        if point:
            lat, lon, _ = point
            if lon_min <= lon <= lon_max and lat_min <= lat <= lat_max:
                map_ax.scatter([lon], [lat], s=42, c=gold, edgecolors=ivory, linewidths=.65, zorder=5)
                # Connect map data coordinates to figure-relative card edge.
                target = card_targets[idx-1]
                con = ConnectionPatch(
                    xyA=(lon, lat), coordsA=map_ax.transData,
                    xyB=target, coordsB=canvas.transAxes,
                    arrowstyle="->", shrinkA=4, shrinkB=3,
                    mutation_scale=9, linewidth=0.75, color="#89a8b7", alpha=.9
                )
                fig.add_artist(con)
                map_ax.text(lon, lat, str(idx), color=bg, fontsize=6.5,
                            ha="center", va="center", fontweight="bold", zorder=6)

    canvas.text(0.035, 0.105, "POWER & CORRIDORS · INTELLIGENCE",
                transform=canvas.transAxes, color=gold, fontsize=8, fontweight="bold")
    canvas.text(0.035, 0.075,
                "Four selected intelligence events · map points use canonical event coordinates where available.",
                transform=canvas.transAxes, color=muted, fontsize=7.2)
    canvas.text(0.965, 0.075, "powerncorridors.com", transform=canvas.transAxes,
                ha="right", color=muted, fontsize=7.2)

    bio = io.BytesIO()
    if output_format.lower() == "pdf":
        fig.savefig(bio, format="pdf", facecolor=fig.get_facecolor(), bbox_inches="tight", pad_inches=0.08)
    else:
        fig.savefig(bio, format="png", dpi=180, facecolor=fig.get_facecolor(), bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    bio.seek(0)
    return bio.getvalue()


def _publication_story_label(row):
    date = clean_display_text(row.get("Start Date", ""))[:10]
    title = clean_display_text(row.get("Title", "Untitled event"))
    loc = clean_display_text(row.get("Country / Countries", row.get("Location", "")))
    return f"{date} · {loc} · {title}" if loc else f"{date} · {title}"



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

    section("Latest intelligence", "Latest intelligence", "Newest reporting and assessed incidents in the intelligence base — surfaced first, not buried in a register.")
    latest = hazard_events.copy()
    if not latest.empty:
        if "Start Date" in latest.columns:
            latest["_date"]=pd.to_datetime(latest["Start Date"],errors="coerce")
            latest=latest.sort_values("_date",ascending=False,na_position="last")
        latest_non_compliance=latest[~_is_compliance_watchlist_event(latest)].copy()
        if latest_non_compliance.empty:
            latest_non_compliance=latest
        cols=st.columns(3)
        for i,(_,r) in enumerate(latest_non_compliance.head(3).iterrows()):
            with cols[i]:
                event_card(r,key_prefix=f"latest_{i}")
        if len(latest_non_compliance)>3:
            with st.expander(f"More latest intelligence ({min(len(latest_non_compliance)-3,12)})",expanded=False):
                for j,(_,r) in enumerate(latest_non_compliance.iloc[3:15].iterrows(),start=3):
                    event_card(r,key_prefix=f"latest_more_{j}")
    else:
        st.markdown('<div class="pc-empty">No event records available.</div>', unsafe_allow_html=True)

    # When the user explicitly opens an event/object, show the complete canonical
    # context immediately here. The close control in the drill-down returns to
    # the operating picture without hiding the rest of the page.
    if st.session_state.get("pc_drilldown_id"):
        st.markdown("### Selected intelligence context")
        pc_render_active_drilldown(location="top",expanded=True)

    pgsa_event_live,pgsa_vessels_live=canonical_pgsa_vessels()
    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("Active Monitors", len(active_mon))
    c2.metric("High / Severe Events", len(high_events))
    c3.metric("Security / MARSEC Events", len(sec_events))
    c4.metric("PGSA vessels", len(pgsa_vessels_live) if pgsa_event_live else len(pgsa))
    c5.metric("Official MARSEC Feeds", len(marsec_feeds))

    left, right = st.columns([1.55,1.0],gap="large")
    with left:
        section("01 · Immediate", "Priority operating picture", "What matters now — ranked by severity, recency and operational consequence.")
        priority=ranked_operating_picture(hazard_events.copy(),5) if not hazard_events.empty else pd.DataFrame()
        if not priority.empty:
            for j,(_,r) in enumerate(priority.iterrows()):
                event_card(r,key_prefix=f"priority_{j}")
        else:
            st.markdown('<div class="pc-empty">No priority events available.</div>', unsafe_allow_html=True)

    with right:
        section("04 · Forward", "Active monitoring", "What could change next: monitors, triggers, time horizons and decision points.")
        if not active_mon.empty:
            for _, r in active_mon.head(6).iterrows():
                st.markdown(
                    "<div class='pc-card'>"
                    f"<div class='pc-card-meta'>{r.get('Family','')} · {r.get('Geography','')}</div>"
                    f"<div class='pc-card-title'>{r.get('Title','')}</div>"
                    f"<div class='pc-card-body'><b>Monitoring:</b> {r.get('What Is Being Monitored','')}</div>"
                    f"<div class='pc-card-impact'><b>Trigger:</b> {r.get('Trigger / Threshold','')}</div>"
                    "</div>",
                    unsafe_allow_html=True
                )
        else:
            st.markdown('<div class="pc-empty">No active monitoring records.</div>', unsafe_allow_html=True)

    section("03 · Theatre picture", "Key theatres & corridors", "Where current security pressure is concentrating across the trade network.")
    theatre_defs=[
        ("Strait of Hormuz",["hormuz","gulf of oman","musandam","khasab"]),
        ("Red Sea / Bab el-Mandeb",["red sea","bab el-mandeb","hodeidah","hudaydah","yemen"]),
        ("Black Sea",["black sea","odesa","odessa","novorossiysk","crimea","kerch"]),
        ("Panama Canal",["panama canal","panama"]),
        ("Baltic",["baltic","gulf of finland","gdansk","klaipeda"]),
        ("Asia-Pacific",["south china sea","taiwan strait","malacca","singapore","philippines"]),
    ]
    theatre_rows=[]
    for theatre,terms in theatre_defs:
        if hazard_events.empty:
            hits=pd.DataFrame()
        else:
            hits=hazard_events[contains_any(
                hazard_events,
                ["Country / Countries","Location","Title","Description","Operational Impact","Trade / Commercial Impact"],
                terms
            )].copy()
        high=0
        latest_title=""
        latest_date=""
        if not hits.empty:
            sev=text_col(hits,"Severity")
            high=int(sev.str.contains("High|Severe|Critical",case=False,regex=True,na=False).sum())
            if "Start Date" in hits.columns:
                hits["_d"]=pd.to_datetime(hits["Start Date"],errors="coerce")
                hits=hits.sort_values("_d",ascending=False,na_position="last")
            latest_title=clean_display_text(hits.iloc[0].get("Title",""))
            latest_date=clean_display_text(hits.iloc[0].get("Start Date",""))
        theatre_rows.append({
            "Theatre / corridor":theatre,
            "Current events":len(hits),
            "Critical / high":high,
            "Latest":latest_date,
            "Latest development":latest_title,
        })
    show_df(pd.DataFrame(theatre_rows),["Theatre / corridor","Current events","Critical / high","Latest","Latest development"],300)

    section("02 · Situational", "What changed", "Recent developments that materially alter the operating environment.")
    if not latest.empty:
        changed=latest[~_is_compliance_watchlist_event(latest)].head(8).copy()
        cols=[c for c in ["Start Date","Severity","Event Type","Title","Location","Operational Impact","Trade / Commercial Impact"] if c in changed.columns]
        show_df(changed,cols,360)
    else:
        st.caption("No recent developments available.")

    compliance_now=hazard_events[_is_compliance_watchlist_event(hazard_events)].copy() if not hazard_events.empty else pd.DataFrame()
    if not compliance_now.empty:
        with st.expander(f"Compliance / watchlist updates ({len(compliance_now)})",expanded=False):
            cols=[c for c in ["Start Date","Severity","Title","Location","Status"] if c in compliance_now.columns]
            show_df(compliance_now,cols,260)
            st.caption("Full vessel lists and drill-through are under Sanctions & Compliance → PGSA / Compliance.")

    section("05 · Judgement", "What would change the picture?", "Explicit triggers from active monitoring that would materially alter current assessments.")
    if not active_mon.empty:
        trig_cols=[c for c in ["Geography","Title","Time Horizon","Trigger / Threshold","Next Review / Milestone","Confidence"] if c in active_mon.columns]
        show_df(active_mon.head(10),trig_cols,320)
    else:
        st.caption("No active monitoring triggers are currently structured.")

    section("Coverage", "Security domains in the current model")
    st.markdown(
        "<span class='pc-badge'>Maritime Security</span>"
        "<span class='pc-badge'>Ports & Chokepoints</span>"
        "<span class='pc-badge'>Aviation & Movement</span>"
        "<span class='pc-badge'>Sanctions & Compliance</span>"
        "<span class='pc-badge'>Weather & Natural Hazards</span>"
        "<span class='pc-badge'>Labour & Civil Disruption</span>"
        "<span class='pc-badge'>Conflict Escalation</span>"
        "<span class='pc-badge'>Critical Infrastructure</span>",
        unsafe_allow_html=True
    )

# -----------------------------------------------------------------------------
# 2. INTELLIGENCE ANALYTICS
# -----------------------------------------------------------------------------
elif page == "Intelligence Analytics":
    section(
        "Analytical workspace",
        "Intelligence Analytics",
        "Interrogate the P&C intelligence event layer by geography, event type, severity, domain and time. Every visual resolves back to the underlying event records."
    )

    adf=_analytics_prepare_events(hazard_events)
    if not adf.empty and not event_actor_links.empty and not actor_directory.empty and "Event ID" in adf.columns:
        _al = event_actor_links.copy()
        _an = actor_directory[["actor_id","canonical_name"]].copy()
        _al = _al.merge(_an, on="actor_id", how="left")
        _al["_event_id_join"] = _al["event_id"].astype(str)
        _actor_names = _al.groupby("_event_id_join")["canonical_name"].apply(
            lambda s: sorted({clean_display_text(x) for x in s if clean_display_text(x)})
        ).to_dict()
        _actor_roles = _al.groupby("_event_id_join")["actor_role"].apply(
            lambda s: sorted({clean_display_text(x) for x in s if clean_display_text(x)})
        ).to_dict()
        adf["_actors"] = adf["Event ID"].astype(str).map(_actor_names).map(lambda x: x if isinstance(x,list) else [])
        adf["_actor_roles"] = adf["Event ID"].astype(str).map(_actor_roles).map(lambda x: x if isinstance(x,list) else [])
    else:
        adf["_actors"] = [[] for _ in range(len(adf))]
        adf["_actor_roles"] = [[] for _ in range(len(adf))]
    if adf.empty:
        st.info("No intelligence-routed events are currently available for analysis.")
    else:
        st.markdown("### Analytical filters")
        f1,f2,f3,f4=st.columns(4)
        period=f1.selectbox(
            "Period",
            ["24 hours","7 days","30 days","90 days","Year to date","All available","Custom"],
            index=2,
            key="intel_analytics_period"
        )
        geo_mode=f2.selectbox("Geography",["Global","Region","Country"],key="intel_analytics_geo_mode")

        custom_start=custom_end=None
        if period == "Custom":
            valid_dates=adf["_date"].dropna()
            min_d=(valid_dates.min().date() if not valid_dates.empty else pd.Timestamp.now().date())
            max_d=(valid_dates.max().date() if not valid_dates.empty else pd.Timestamp.now().date())
            custom_start=f3.date_input("From",value=min_d,key="intel_analytics_custom_start")
            custom_end=f4.date_input("To",value=max_d,key="intel_analytics_custom_end")
        else:
            f3.caption("Scope")
            f3.markdown("**Intelligence-routed events only**")
            f4.caption("Source layer")
            f4.markdown("**Canonical events**")

        df,start_dt,end_dt=_analytics_period_filter(adf,period,custom_start,custom_end)

        # Geographic filtering uses all countries attached to an event, not only the first.
        selected_geo="Global"
        if geo_mode == "Region":
            regions=sorted({r for rs in df.get("_regions",pd.Series(dtype=object)) for r in (rs if isinstance(rs,list) else []) if r})
            regions=[r for r in regions if r != "Unspecified"] or ["Unspecified"]
            selected_geo=st.selectbox("Region",regions,key="intel_analytics_region")
            df=df[df["_regions"].map(lambda rs:selected_geo in rs if isinstance(rs,list) else False)].copy()
        elif geo_mode == "Country":
            countries=sorted({c for cs in df.get("_countries",pd.Series(dtype=object)) for c in (cs if isinstance(cs,list) else []) if c})
            countries=countries or ["Unspecified"]
            selected_geo=st.selectbox("Country",countries,key="intel_analytics_country")
            df=df[df["_countries"].map(lambda cs:selected_geo in cs if isinstance(cs,list) else False)].copy()

        # Event dimensions.
        d1,d2,d3,d4=st.columns(4)
        type_options=["All"]+sorted([x for x in text_col(df,"Event Type").unique() if clean_display_text(x)])
        severity_options=["All"]+sorted([x for x in text_col(df,"Severity").unique() if clean_display_text(x)])
        domain_options=["All"]+sorted([x for x in text_col(df,"Event Domain").unique() if clean_display_text(x)])
        family_options=["All"]+sorted([x for x in text_col(df,"Event Family").unique() if clean_display_text(x)])
        event_type=d1.selectbox("Event type",type_options,key="intel_analytics_event_type")
        severity=d2.selectbox("Severity",severity_options,key="intel_analytics_severity")
        domain=d3.selectbox("Domain",domain_options,key="intel_analytics_domain")
        family=d4.selectbox("Event family",family_options,key="intel_analytics_family")
        if event_type != "All": df=df[text_col(df,"Event Type").eq(event_type)].copy()
        if severity != "All": df=df[text_col(df,"Severity").eq(severity)].copy()
        if domain != "All": df=df[text_col(df,"Event Domain").eq(domain)].copy()
        if family != "All": df=df[text_col(df,"Event Family").eq(family)].copy()

        af1,af2=st.columns(2)
        actor_options=["All"]+sorted({a for xs in df.get("_actors",pd.Series(dtype=object)) for a in (xs if isinstance(xs,list) else []) if a})
        role_options=["All"]+sorted({r for xs in df.get("_actor_roles",pd.Series(dtype=object)) for r in (xs if isinstance(xs,list) else []) if r})
        actor_filter=af1.selectbox("Actor",actor_options,key="intel_analytics_actor")
        role_filter=af2.selectbox("Actor role",role_options,key="intel_analytics_actor_role")
        if actor_filter != "All":
            df=df[df["_actors"].map(lambda xs: actor_filter in xs if isinstance(xs,list) else False)].copy()
        if role_filter != "All":
            df=df[df["_actor_roles"].map(lambda xs: role_filter in xs if isinstance(xs,list) else False)].copy()

        # Headline metrics.
        event_count=(df["Event ID"].nunique() if "Event ID" in df.columns else len(df))
        sev_series=text_col(df,"Severity")
        high_critical=int(sev_series.str.contains("High|Severe|Critical",case=False,regex=True,na=False).sum())
        country_count=len({c for cs in df.get("_countries",pd.Series(dtype=object)) for c in (cs if isinstance(cs,list) else []) if c})
        mapped_locations=0
        if not event_locations.empty and "Event ID" in event_locations.columns and "Event ID" in df.columns:
            ids=set(df["Event ID"].dropna().astype(str))
            loc=event_locations[text_col(event_locations,"Event ID").isin(ids)].copy()
            if "Latitude" in loc.columns and "Longitude" in loc.columns:
                lat=pd.to_numeric(loc["Latitude"],errors="coerce")
                lon=pd.to_numeric(loc["Longitude"],errors="coerce")
                mapped_locations=int((lat.notna() & lon.notna()).sum())

        # Period-on-period comparison only when the current window is bounded.
        delta_text=None
        if start_dt is not None and end_dt is not None and period != "Custom":
            span=end_dt-start_dt
            prev_end=start_dt-pd.Timedelta(microseconds=1)
            prev_start=prev_end-span
            prev=adf[adf["_date"].between(prev_start,prev_end,inclusive="both")].copy()
            if geo_mode == "Region":
                prev=prev[prev["_regions"].map(lambda rs:selected_geo in rs if isinstance(rs,list) else False)]
            elif geo_mode == "Country":
                prev=prev[prev["_countries"].map(lambda cs:selected_geo in cs if isinstance(cs,list) else False)]
            if event_type != "All": prev=prev[text_col(prev,"Event Type").eq(event_type)]
            if severity != "All": prev=prev[text_col(prev,"Severity").eq(severity)]
            if domain != "All": prev=prev[text_col(prev,"Event Domain").eq(domain)]
            if family != "All": prev=prev[text_col(prev,"Event Family").eq(family)]
            prev_count=(prev["Event ID"].nunique() if "Event ID" in prev.columns else len(prev))
            if prev_count > 0:
                pct=(event_count-prev_count)/prev_count*100
                delta_text=f"{pct:+.0f}% vs prior period"
            elif event_count > 0:
                delta_text="New vs prior period"

        m1,m2,m3,m4=st.columns(4)
        m1.metric("Matching events",f"{event_count:,}",delta_text)
        m2.metric("High / critical",f"{high_critical:,}")
        m3.metric("Countries affected",f"{country_count:,}")
        m4.metric("Mapped locations",f"{mapped_locations:,}")

        st.markdown("### Visual analysis")
        c1,c2,c3,c4=st.columns([1,1.15,1,1])
        chart_type=c1.selectbox("Chart",["Line","Bar","Pie"],key="intel_analytics_chart")
        group_options=["Event Type","Region","Country","Severity","Event Family","Domain","Mode","Status","Actor","Actor Role"]
        default_group=1 if geo_mode == "Global" else (2 if geo_mode == "Region" else 0)
        group_by=c2.selectbox("Group by",group_options,index=default_group,key="intel_analytics_group")
        time_grain=c3.selectbox("Time grain",["Daily","Weekly","Monthly"],index=1,key="intel_analytics_grain",disabled=(chart_type != "Line"))
        top_n=c4.selectbox("Show",[5,10,15,20,25],index=2,key="intel_analytics_topn")

        scope_label=("Global" if geo_mode == "Global" else selected_geo)
        st.caption(f"{scope_label} · {period} · {event_count:,} matching intelligence events")
        _analytics_render_chart(df,chart_type,group_by,time_grain,top_n)

        # Geographic drill-down table changes with analytical scope.
        st.markdown("### Geographic breakdown")
        if geo_mode == "Global":
            breakdown_level="Region"
        elif geo_mode == "Region":
            breakdown_level="Country"
        else:
            breakdown_level="Event Type"
        breakdown=_analytics_breakdown(df,breakdown_level)
        if breakdown.empty:
            st.caption("No breakdown is available for the current selection.")
        else:
            display_cols=[breakdown_level,"Count","% of breakdown","Critical / Severe","High","Medium","Low"]
            show_df(breakdown,display_cols,min(520,90+34*len(breakdown)))

        if group_by != breakdown_level:
            with st.expander(f"Breakdown by {group_by}",expanded=False):
                secondary=_analytics_breakdown(df,group_by)
                if not secondary.empty:
                    show_df(secondary,[group_by,"Count","% of breakdown","Critical / Severe","High","Medium","Low"],min(480,90+34*len(secondary)))

        st.markdown("### Supporting events")
        st.caption("These are the event records producing the counts above. Open any event in the canonical drill-down for the full connected context.")
        events_view=df.copy()
        if "_date" in events_view.columns:
            events_view=events_view.sort_values("_date",ascending=False,na_position="last")
        show_df(
            events_view,
            ["Start Date","Event Type","Event Family","Severity","Event Domain","Country / Countries","Location","Title","Operational Impact","Confidence"],
            430
        )

        if not events_view.empty and "Event ID" in events_view.columns:
            choices=events_view.reset_index(drop=True)
            pick=st.selectbox(
                "Open matching event",
                range(len(choices)),
                format_func=lambda i: (
                    f"{clean_display_text(choices.iloc[i].get('Start Date',''))} · "
                    f"{clean_display_text(choices.iloc[i].get('Title','Untitled event'))}"
                ),
                key="intel_analytics_open_event"
            )
            erow=choices.iloc[pick]
            eid=clean_display_text(erow.get("Event ID",""))
            if eid:
                pc_drilldown_button(
                    "event",eid,"Open full event context",
                    key=f"intel_analytics_dd_{eid}",use_container_width=True
                )

        csv_cols=[c for c in ["Event ID","Start Date","Event Type","Event Family","Severity","Event Domain","Country / Countries","Location","Title","Operational Impact","Confidence"] if c in events_view.columns]
        if csv_cols:
            csv_data=events_view[csv_cols].to_csv(index=False).encode("utf-8")
            st.download_button(
                "Download filtered event set (CSV)",
                data=csv_data,
                file_name="pc_intelligence_analytics_filtered_events.csv",
                mime="text/csv",
                use_container_width=True,
                key="intel_analytics_download"
            )


# -----------------------------------------------------------------------------
# 3. ACTORS & NETWORKS
# -----------------------------------------------------------------------------
elif page == "Actors & Networks":
    section(
        "Actor intelligence",
        "Actors & Networks",
        "Canonical organisations, armed groups, state-security actors and networks connected to the P&C event layer. Actor identity, operational role and attribution are kept separate."
    )

    if actor_directory.empty:
        st.warning("The canonical actor registry is not currently available from Supabase.")
    else:
        ad = actor_directory.copy()
        for c in ["canonical_name","short_name","actor_class","actor_subtype","status","primary_country","confidence","roles_seen"]:
            if c in ad.columns:
                ad[c] = ad[c].map(clean_display_text)
        for c in ["linked_events","high_critical_events","distinct_roles","designation_count"]:
            if c in ad.columns:
                ad[c] = pd.to_numeric(ad[c], errors="coerce").fillna(0).astype(int)

        total_actors=len(ad)
        active_with_events=int((ad["linked_events"]>0).sum()) if "linked_events" in ad.columns else 0
        linked_events_total=int(event_actor_links["event_id"].astype(str).nunique()) if not event_actor_links.empty else 0
        high_critical_total=int(ad["high_critical_events"].sum()) if "high_critical_events" in ad.columns else 0

        m1,m2,m3,m4=st.columns(4)
        m1.metric("Canonical actors",f"{total_actors:,}")
        m2.metric("Actors with linked events",f"{active_with_events:,}")
        m3.metric("Linked intelligence events",f"{linked_events_total:,}")
        m4.metric("High / critical actor-events",f"{high_critical_total:,}")

        st.markdown("### Actor directory")
        f1,f2,f3,f4=st.columns([1.3,1,1,1])
        search_actor=f1.text_input("Search",placeholder="Actor, short name, country or subtype",key="actor_directory_search")
        classes=["All"]+sorted([x for x in ad.get("actor_class",pd.Series(dtype=str)).unique() if clean_display_text(x)])
        countries=["All"]+sorted([x for x in ad.get("primary_country",pd.Series(dtype=str)).unique() if clean_display_text(x)])
        actor_class=f2.selectbox("Actor class",classes,key="actor_class_filter")
        actor_country=f3.selectbox("Primary country",countries,key="actor_country_filter")
        activity_mode=f4.selectbox("Activity",["All actors","Linked events only","No linked events"],key="actor_activity_mode")

        filtered=ad.copy()
        if actor_class!="All":
            filtered=filtered[filtered["actor_class"].eq(actor_class)]
        if actor_country!="All":
            filtered=filtered[filtered["primary_country"].eq(actor_country)]
        if activity_mode=="Linked events only" and "linked_events" in filtered.columns:
            filtered=filtered[filtered["linked_events"]>0]
        elif activity_mode=="No linked events" and "linked_events" in filtered.columns:
            filtered=filtered[filtered["linked_events"]==0]
        if search_actor.strip():
            q=search_actor.strip().lower()
            blob=(
                filtered.get("canonical_name",pd.Series("",index=filtered.index)).astype(str)+" "+
                filtered.get("short_name",pd.Series("",index=filtered.index)).astype(str)+" "+
                filtered.get("actor_subtype",pd.Series("",index=filtered.index)).astype(str)+" "+
                filtered.get("primary_country",pd.Series("",index=filtered.index)).astype(str)+" "+
                filtered.get("countries",pd.Series("",index=filtered.index)).map(_actor_list_text)
            ).str.lower()
            filtered=filtered[blob.str.contains(re.escape(q),regex=True,na=False)]

        dv=filtered.rename(columns={
            "canonical_name":"Actor","short_name":"Short Name","actor_class":"Class",
            "actor_subtype":"Subtype","status":"Status","primary_country":"Primary Country",
            "linked_events":"Linked Events","high_critical_events":"High / Critical","roles_seen":"Roles Seen"
        })
        show_df(dv,["Actor","Short Name","Class","Subtype","Status","Primary Country","Linked Events","High / Critical","Roles Seen"],
                min(520,120+max(1,len(dv))*32))

        if filtered.empty:
            st.info("No actors match the current filters.")
        else:
            st.markdown("### Actor profile")
            choices=filtered.sort_values(
                ["linked_events","canonical_name"] if "linked_events" in filtered.columns else ["canonical_name"],
                ascending=[False,True] if "linked_events" in filtered.columns else [True]
            ).reset_index(drop=True)
            selected_idx=st.selectbox(
                "Select actor",range(len(choices)),
                format_func=lambda i: (
                    f"{clean_display_text(choices.iloc[i].get('canonical_name',''))}"
                    + (f" ({clean_display_text(choices.iloc[i].get('short_name',''))})"
                       if clean_display_text(choices.iloc[i].get('short_name',''))
                       and clean_display_text(choices.iloc[i].get('short_name','')) != clean_display_text(choices.iloc[i].get('canonical_name',''))
                       else "")
                ),
                key="actor_profile_select"
            )
            actor=choices.iloc[selected_idx]
            actor_id=clean_display_text(actor.get("actor_id",""))
            actor_name=clean_display_text(actor.get("canonical_name",""))

            st.markdown(f"## {actor_name}")
            subtitle=[
                humanize_relationship(actor.get("actor_class","")),
                clean_display_text(actor.get("actor_subtype","")),
                clean_display_text(actor.get("primary_country","")),
                clean_display_text(actor.get("status","")),
            ]
            st.caption(" · ".join([x for x in subtitle if x]))

            p1,p2,p3,p4=st.columns(4)
            p1.metric("Linked events",f"{int(actor.get('linked_events',0) or 0):,}")
            p2.metric("High / critical",f"{int(actor.get('high_critical_events',0) or 0):,}")
            p3.metric("Distinct roles",f"{int(actor.get('distinct_roles',0) or 0):,}")
            latest=clean_display_text(actor.get("latest_event_date",""))
            p4.metric("Latest event",latest[:10] if latest else "—")

            desc=clean_display_text(actor.get("description",""))
            if desc:
                st.markdown(desc)

            c1,c2=st.columns([1,1])
            with c1:
                st.markdown("**Actor details**")
                details=pd.DataFrame([
                    ["Short name",clean_display_text(actor.get("short_name",""))],
                    ["Class",humanize_relationship(actor.get("actor_class",""))],
                    ["Subtype",clean_display_text(actor.get("actor_subtype",""))],
                    ["Status",clean_display_text(actor.get("status",""))],
                    ["Primary country",clean_display_text(actor.get("primary_country",""))],
                    ["Countries",_actor_list_text(actor.get("countries",""))],
                    ["Confidence",clean_display_text(actor.get("confidence",""))],
                ],columns=["Field","Value"])
                show_df(details,["Field","Value"],295)
            with c2:
                st.markdown("**Observed roles**")
                roles=clean_display_text(actor.get("roles_seen",""))
                st.markdown(
                    f"<div class='pc-card'><div class='pc-card-title'>{roles or 'No event roles yet'}</div>"
                    f"<div class='pc-card-meta'>Derived from event-actor links; role is not the same as actor identity.</div></div>",
                    unsafe_allow_html=True
                )
                st.markdown("**Designations**")
                ddf=_actor_designation_frame(actor_id)
                if ddf.empty:
                    st.caption("No structured designation records have been added yet.")
                else:
                    show_df(ddf,["authority","designation_name","designation_type","programme","effective_date","status","confidence"],210)

            st.markdown("### Event activity")
            ev=_actor_event_frame(actor_id)
            if ev.empty:
                st.caption("No linked intelligence events for this actor.")
            else:
                if "Start Date" in ev.columns:
                    ev["_date"]=pd.to_datetime(ev["Start Date"],errors="coerce")
                    ev=ev.sort_values("_date",ascending=False,na_position="last")
                role_counts=ev["actor_role"].fillna("Unspecified").astype(str).value_counts().reset_index()
                role_counts.columns=["Actor Role","Count"]

                a1,a2=st.columns([1.35,1])
                with a1:
                    if alt is not None and "_date" in ev.columns:
                        chart_df=ev.dropna(subset=["_date"]).copy()
                        if not chart_df.empty:
                            chart_df["Month"]=chart_df["_date"].dt.to_period("M").dt.to_timestamp()
                            month_role=chart_df.groupby(["Month","actor_role"],dropna=False).size().reset_index(name="Events")
                            month_role["actor_role"]=month_role["actor_role"].fillna("Unspecified")
                            chart=alt.Chart(month_role).mark_bar().encode(
                                x=alt.X("Month:T",title="Month"),
                                y=alt.Y("Events:Q",title="Linked events"),
                                color=alt.Color("actor_role:N",title="Actor role"),
                                tooltip=["Month:T","actor_role:N","Events:Q"]
                            ).properties(height=300)
                            st.altair_chart(chart,use_container_width=True)
                        else:
                            st.caption("No dated events available for trend analysis.")
                    else:
                        st.caption("Charting unavailable.")
                with a2:
                    show_df(role_counts,["Actor Role","Count"],300)

                show_df(ev,["Start Date","Event Type","Severity","actor_role","attribution_status","confidence","Title","Operational Impact"],430)
                event_choices=ev.reset_index(drop=True)
                open_idx=st.selectbox(
                    "Open linked event",range(len(event_choices)),
                    format_func=lambda i: (
                        f"{clean_display_text(event_choices.iloc[i].get('Start Date',''))} · "
                        f"{clean_display_text(event_choices.iloc[i].get('Title','Untitled event'))}"
                    ),
                    key=f"actor_open_event_{actor_id}"
                )
                event_id=clean_display_text(event_choices.iloc[open_idx].get("event_id",""))
                if not event_id:
                    event_id=clean_display_text(event_choices.iloc[open_idx].get("Event ID",""))
                if event_id:
                    pc_drilldown_button("event",event_id,"Open full event context",
                                        key=f"actor_event_dd_{actor_id}_{event_id}",use_container_width=True)

            st.markdown("### Network relationships")
            rdf=_actor_relationship_frame(actor_id)
            if rdf.empty:
                st.caption("No structured actor relationships are currently recorded for this actor.")
            else:
                show_df(rdf,["From Actor","Relationship","To Actor","Class","Status","Confidence","Basis"],330)

            with st.expander("Analyst / data-quality status",expanded=False):
                pending=event_actor_links[event_actor_links["actor_id"].astype(str).eq(str(actor_id))].copy() if not event_actor_links.empty else pd.DataFrame()
                if pending.empty:
                    st.caption("No event-actor links.")
                else:
                    reviewed=int(pending.get("analyst_reviewed",pd.Series(False,index=pending.index)).fillna(False).astype(bool).sum())
                    st.caption(f"{reviewed:,} of {len(pending):,} event-actor links marked analyst reviewed.")
                    show_df(pending,["event_id","actor_role","attribution_status","confidence","analyst_reviewed","link_basis"],260)


# -----------------------------------------------------------------------------
# 3. ALERTS & INCIDENTS
# -----------------------------------------------------------------------------
elif page == "Intelligence Brief Builder":
    section(
        "Publications",
        "P&C Intelligence Brief Builder",
        "Select a geography and four intelligence stories, preview the mapped publication, then export a one-page PDF."
    )
    st.caption(
        "This first publication template uses the P&C Intelligence event layer. The region name is printed on the image, "
        "and map arrows use canonical event coordinates where available."
    )

    c1, c2, c3 = st.columns([1.05, 1, 1])
    region_name = c1.selectbox("Publication geography", list(PUBLICATION_REGIONS.keys()), key="pc_pub_region")
    pub_date = c2.date_input("Publication date", value=datetime.now().date(), key="pc_pub_date")
    lookback = c3.selectbox("Story window", ["7 days", "14 days", "30 days", "90 days", "All loaded"], index=2, key="pc_pub_lookback")

    candidates = publication_region_events(region_name)
    if not candidates.empty and lookback != "All loaded" and "Start Date" in candidates.columns:
        days = int(lookback.split()[0])
        cutoff = pd.Timestamp(pub_date) - pd.Timedelta(days=days)
        dates = pd.to_datetime(candidates["Start Date"], errors="coerce", utc=True).dt.tz_convert(None)
        candidates = candidates[(dates >= cutoff) & (dates <= pd.Timestamp(pub_date) + pd.Timedelta(days=1))].copy()

    if candidates.empty:
        st.warning("No P&C Intelligence events match this geography and time window.")
    else:
        candidates = candidates.reset_index(drop=True)
        option_ids = list(range(len(candidates)))
        default_ids = option_ids[:4]
        selected = st.multiselect(
            "Select exactly four stories",
            option_ids,
            default=default_ids,
            max_selections=4,
            format_func=lambda i: _publication_story_label(candidates.iloc[i]),
            key="pc_pub_story_selection"
        )

        ready_count = 0
        if selected:
            st.markdown("### Selected story readiness")
            readiness_rows = []
            for i in selected:
                r = candidates.iloc[i]
                wc = publication_summary_word_count(r)
                point = publication_event_point(r.get("Event ID", ""))
                enriched = 60 <= wc <= 90
                if enriched:
                    ready_count += 1
                readiness_rows.append({
                    "Story": clean_display_text(r.get("Title", "")),
                    "Summary words": wc,
                    "60–90 word load": "Ready" if enriched else "Needs enrichment",
                    "Mapped": "Yes" if point else "No",
                    "Location": point[2] if point else clean_display_text(r.get("Location", "")),
                })
            show_df(pd.DataFrame(readiness_rows), height=190)
            if ready_count < len(selected):
                st.info(
                    "Older records may fall back to Description / impact text. New AI-loader events should arrive with a "
                    "dedicated 60–90 word publication summary so the renderer does not need to rewrite them."
                )

        if len(selected) == 4:
            rows = [candidates.iloc[i] for i in selected]
            try:
                with st.spinner("Rendering P&C Intelligence publication…"):
                    png_bytes = render_intelligence_brief(rows, region_name, pub_date, "png")
                    pdf_bytes = render_intelligence_brief(rows, region_name, pub_date, "pdf")
                st.markdown("### Preview")
                st.image(png_bytes, use_container_width=True)

                safe_region = re.sub(r"[^A-Za-z0-9]+", "-", region_name).strip("-").lower()
                date_slug = pd.to_datetime(pub_date).strftime("%Y-%m-%d")
                d1, d2 = st.columns(2)
                d1.download_button(
                    "Download PDF",
                    data=pdf_bytes,
                    file_name=f"pc-intelligence-{safe_region}-{date_slug}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    type="primary",
                    key="pc_pub_download_pdf"
                )
                d2.download_button(
                    "Download PNG",
                    data=png_bytes,
                    file_name=f"pc-intelligence-{safe_region}-{date_slug}.png",
                    mime="image/png",
                    use_container_width=True,
                    key="pc_pub_download_png"
                )
            except Exception as exc:
                st.error(f"Publication renderer error: {exc}")
                st.caption("PDF/PNG export requires matplotlib. Basemap is optional but recommended for coastlines and country outlines.")
        else:
            st.info(f"Select exactly four stories to build the publication. Current selection: {len(selected)}.")


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
            eid = str(row.get("Event ID", row.get("event_id", "")) or "").strip()
            a,b = st.columns([1.2,1])
            with a:
                event_card(row,key_prefix=f"alerts_detail_{eid or 'selected'}")
            with b:
                links = event_asset_links[text_col(event_asset_links,"Event ID").eq(eid)] if (eid and not event_asset_links.empty) else event_asset_links.iloc[0:0] if not event_asset_links.empty else event_asset_links
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
        "Map-first theatre views across all regions, with a second selector for P&C key focus areas."
    )
    st.caption(
        "Choose the wider region first, then narrow to a key focus area such as Hormuz, "
        "Odesa/Chornomorsk, Panama Canal, Malacca/Singapore or the Northern Sea Route. "
        "Only events with supported coordinates are plotted."
    )

    _r1,_r2=st.columns(2)
    with _r1:
        _region_name=st.selectbox(
            "Region",
            list(REGIONAL_SECURITY_AREAS.keys()),
            key="intel_regional_map_region"
        )
    _focus_options=list((MAP_FOCUS_AREAS.get(_region_name) or {"All regional activity":{}}).keys())
    with _r2:
        _focus_name=st.selectbox(
            "Key focus area",
            _focus_options,
            key="intel_regional_map_focus"
        )

    _focus_cfg=_intel_focus_config(_region_name,_focus_name)

    _events=regional_events(_region_name,operational_only=True)
    _events=_intel_focus_filter(_events,_focus_cfg)
    _mapped=regional_event_map_points(_events)

    _m1,_m2,_m3,_m4=st.columns(4)
    _m1.metric("Regional events",len(_events))
    _m2.metric("Mapped points",len(_mapped))
    if not _events.empty and not _mapped.empty and "Event ID" in _mapped.columns:
        _mapped_events=_mapped["Event ID"].fillna("").astype(str).nunique()
    else:
        _mapped_events=0
    _m3.metric("Events without map point",max(len(_events)-_mapped_events,0))
    _m4.metric("Focus",_focus_name)

    st.caption(f"Region: {_region_name} · Key focus: {_focus_name}")

    render_regional_incident_map(_region_name,_events,focus_cfg=_focus_cfg)

    tabs=st.tabs(["Incident register","Key focus summary","Unmapped events"])
    with tabs[0]:
        if not _mapped.empty:
            _cols=[c for c in [
                "Start Date","Date","Title","Incident","Mapped Location",
                "Severity","Severity Label","Status","Operational",
                "Commercial","Map Accuracy"
            ] if c in _mapped.columns]
            if _cols:
                show_df(_mapped,_cols,400)
        elif not _events.empty:
            st.info("Regional incidents are loaded, but none currently have supported coordinates.")
        else:
            st.info("No qualifying operational incidents are currently loaded for this selection.")

    with tabs[1]:
        st.markdown(f"### {_focus_name}")
        if _focus_cfg.get("phrases"):
            st.caption("Focus terms: " + " · ".join(_focus_cfg["phrases"][:10]))
        if _events.empty:
            st.caption("No matching operational events.")
        else:
            ev=_events.copy()
            if "Start Date" in ev.columns:
                ev["_d"]=pd.to_datetime(ev["Start Date"],errors="coerce")
                ev=ev.sort_values("_d",ascending=False)
            _cols=[c for c in [
                "Start Date","Severity","Status","Event Type","Title",
                "Location","Operational Impact","Trade / Commercial Impact"
            ] if c in ev.columns]
            show_df(ev,_cols,420)

    with tabs[2]:
        if _events.empty:
            st.caption("No events in this selection.")
        else:
            mapped_ids=set(_mapped["Event ID"].fillna("").astype(str)) if not _mapped.empty and "Event ID" in _mapped.columns else set()
            if "Event ID" in _events.columns:
                unmapped=_events[~_events["Event ID"].fillna("").astype(str).isin(mapped_ids)].copy()
            else:
                unmapped=_events.copy()
            _cols=[c for c in [
                "Start Date","Severity","Title","Country / Countries",
                "Location","Operational Impact"
            ] if c in unmapped.columns]
            show_df(unmapped,_cols,360)


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
                event_card(row,key_prefix=f"marsec_detail_{eid}")
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
                event_card(row,key_prefix=f"ports_detail_{eid}")
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

        pgsa_event,pgsa_vessels=canonical_pgsa_vessels()
        if pgsa_event:
            st.markdown("### PGSA vessel list")
            p1,p2,p3=st.columns(3)
            p1.metric("Canonical listed vessels",len(pgsa_vessels))
            p2.metric("Event date",str(pgsa_event.get("start_date") or "")[:10])
            p3.metric("Status",str(pgsa_event.get("status") or ""))
            st.markdown(f"**{pgsa_event.get('title','PGSA compliance-list update')}**")
            if pgsa_event.get("operational_impact"):
                st.write(pgsa_event.get("operational_impact"))

            if not pgsa_vessels.empty:
                q=st.text_input("Filter PGSA vessels",placeholder="vessel name, IMO, flag, type…",key="pgsa_vessel_filter")
                view=pgsa_vessels.copy()
                if q.strip():
                    mask=view.astype(str).apply(
                        lambda c:c.str.contains(q.strip(),case=False,na=False,regex=False)
                    ).any(axis=1)
                    view=view[mask].copy()

                show_df(view,["Vessel","IMO","MMSI","Flag","Vessel Type","Status","Relationship"],560)

                if not view.empty:
                    choices=view.to_dict("records")
                    pick=st.selectbox(
                        "Open vessel profile",
                        range(len(choices)),
                        format_func=lambda i:
                            f"{choices[i].get('Vessel','')}"
                            + (f" · IMO {choices[i].get('IMO')}" if choices[i].get("IMO") else "")
                            + (f" · {choices[i].get('Flag')}" if choices[i].get("Flag") else ""),
                        key="pgsa_open_vessel_pick"
                    )
                    vessel=choices[pick]
                    if st.button(
                        f"Open {vessel.get('Vessel','vessel')} in canonical drill-down",
                        type="primary",
                        use_container_width=True,
                        key=f"pgsa_open_vessel_{vessel.get('Canonical ID')}"
                    ):
                        pc_set_drilldown("mobile_asset",vessel.get("Canonical ID"),vessel.get("Vessel"))
            else:
                st.warning("The PGSA canonical event was found, but no linked mobile assets were returned.")
        else:
            st.info("No canonical PGSA vessel-list event is currently available.")

        st.markdown("### Compliance registry")
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

