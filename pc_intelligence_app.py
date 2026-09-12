import streamlit as st
import pandas as pd
import re
import sys
from pathlib import Path
from datetime import datetime

st.set_page_config(
    page_title="P&C Intelligence",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
SHARED_DIR = ROOT / "shared"
if str(SHARED_DIR) not in sys.path:
    sys.path.insert(0,str(SHARED_DIR))
from pc_data_bridge import load_sheet as bridge_load_sheet
from pc_db import client as pc_db_client, safe_rows as pc_safe_rows

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
# Data helpers — live/canonical bridge first, workbook fallback during migration
# -----------------------------------------------------------------------------
@st.cache_data(show_spinner=False, ttl=300)
def xl(file_name: str, sheet: str) -> pd.DataFrame:
    try:
        df = bridge_load_sheet(DATA, file_name, sheet, dtype_str=True)
        return df.dropna(how="all") if df is not None else pd.DataFrame()
    except Exception:
        try:
            df = pd.read_excel(DATA / file_name, sheet_name=sheet)
            return df.dropna(how="all")
        except Exception:
            return pd.DataFrame()


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
        st.markdown('<div class="pc-empty">No matching records in the current canonical/migration data layer.</div>', unsafe_allow_html=True)
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
hazard_events = xl("13_events_hazards.xlsx", "Events")
event_locations = xl("13_events_hazards.xlsx", "Event Locations")
event_asset_links = xl("13_events_hazards.xlsx", "Event Asset Links")
event_company_links = xl("13_events_hazards.xlsx", "Event Company Links")
event_system_links = xl("13_events_hazards.xlsx", "Event System Links")
impact_chains = xl("13_events_hazards.xlsx", "Impact Chains")

# Sanctions / compliance
_legacy_sanctions_authorities = xl("14_trade_policy_compliance.xlsx", "Sanctions Authorities")
_legacy_sanctions_programmes = xl("14_trade_policy_compliance.xlsx", "Sanctions Programmes")
_legacy_sanctions_designations = xl("14_trade_policy_compliance.xlsx", "Sanctions Designations")
_legacy_sanctions_links = xl("14_trade_policy_compliance.xlsx", "Sanctions Entity Links")
_legacy_compliance_regimes = xl("14_trade_policy_compliance.xlsx", "Compliance Regimes")
_legacy_compliance_designations = xl("14_trade_policy_compliance.xlsx", "Compliance Designations")
_legacy_compliance_exposure = xl("14_trade_policy_compliance.xlsx", "Compliance Exposure")
_legacy_watchlist_taxonomy = xl("14_trade_policy_compliance.xlsx", "Watchlist Taxonomy")

sanctions_authorities,_src_auth=_policy_live_first(_legacy_sanctions_authorities,["pc_sanctions_authorities","sanctions_authorities"],["Authority ID"])
sanctions_programmes,_src_prog=_policy_live_first(_legacy_sanctions_programmes,["pc_sanctions_programmes","pc_sanctions_programs","sanctions_programmes"],["Programme ID"])
sanctions_designations,_src_des=_policy_live_first(_legacy_sanctions_designations,["pc_sanctions_designations","sanctions_designations"],["Designation ID"])
sanctions_links,_src_link=_policy_live_first(_legacy_sanctions_links,["pc_sanctions_entity_links","sanctions_entity_links"],["Designation ID","Entity ID"])
compliance_regimes,_src_reg=_policy_live_first(_legacy_compliance_regimes,["pc_compliance_regimes","compliance_regimes"],["Regime"])
compliance_designations,_src_cd=_policy_live_first(_legacy_compliance_designations,["pc_compliance_designations","compliance_designations"])
compliance_exposure,_src_ce=_policy_live_first(_legacy_compliance_exposure,["pc_compliance_exposure","compliance_exposure"])
watchlist_taxonomy,_src_watch=_policy_live_first(_legacy_watchlist_taxonomy,["pc_watchlist_taxonomy","watchlist_taxonomy"],["Class"])
POLICY_DATA_SOURCES={v for v in [_src_auth,_src_prog,_src_des,_src_link,_src_reg,_src_cd,_src_ce,_src_watch] if v}

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
    "DOMAIN INTELLIGENCE": ["Maritime Security", "Ports & Infrastructure", "Aviation & Movement", "Sanctions & Compliance"],
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
st.sidebar.caption("P&C canonical data · global regional maps · Supabase + migration fallback")

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


def _monitor_horizon_rank(v):
    """Sort monitoring horizons without inventing a probability."""
    s=clean_display_text(v).casefold()
    if not s:
        return 99
    if any(x in s for x in ["24h","24 h","24-hour","24 hour","immediate","today","hours"]):
        return 1
    if any(x in s for x in ["48h","48 h","48-hour","48 hour"]):
        return 2
    if any(x in s for x in ["72h","72 h","72-hour","72 hour","3 day","three day"]):
        return 3
    if any(x in s for x in ["7 day","one week","1 week","week"]):
        return 4
    if any(x in s for x in ["30 day","month"]):
        return 5
    return 10

def _monitor_status_rank(v):
    s=clean_display_text(v).casefold()
    if "active" in s:
        return 1
    if "develop" in s:
        return 2
    if "monitor" in s:
        return 3
    return 9

def _monitor_recent_activity_count(geography):
    ev=watch_area_events(geography)
    if ev is None or ev.empty:
        return 0
    if "Start Date" not in ev.columns:
        return len(ev)
    d=pd.to_datetime(ev["Start Date"],errors="coerce")
    latest=d.max()
    if pd.isna(latest):
        return len(ev)
    return int((d >= (latest-pd.Timedelta(days=7))).sum())

def _monitor_queue(df):
    if df is None or df.empty:
        return df
    x=df.copy()
    x["_status_rank"]=text_col(x,"Status").map(_monitor_status_rank)
    x["_horizon_rank"]=text_col(x,"Time Horizon").map(_monitor_horizon_rank)
    x["_review_sort"]=pd.to_datetime(x.get("Last Reviewed"),errors="coerce") if "Last Reviewed" in x.columns else pd.NaT
    x["_activity"]=x.get("Geography",pd.Series("",index=x.index)).map(_monitor_recent_activity_count)
    return x.sort_values(
        ["_status_rank","_horizon_rank","_activity","_review_sort"],
        ascending=[True,True,False,False],
        na_position="last"
    )

def _latest_intelligence_events(limit=8):
    if hazard_events is None or hazard_events.empty:
        return hazard_events
    x=hazard_events.copy()
    if "Start Date" in x.columns:
        x["_intel_date"]=pd.to_datetime(x["Start Date"],errors="coerce")
        x=x.sort_values("_intel_date",ascending=False,na_position="last")
    return x.head(limit)

def render_latest_intelligence_strip():
    latest=_latest_intelligence_events(6)
    section(
        "LATEST INTELLIGENCE",
        "Latest intelligence",
        "Newest reporting and assessed incidents in the P&C intelligence base — surfaced first, not buried in the event register."
    )
    if latest is None or latest.empty:
        st.markdown('<div class="pc-empty">No intelligence records available.</div>', unsafe_allow_html=True)
        return

    top=latest.head(3).reset_index(drop=True)
    cols=st.columns(3)
    for i,r in top.iterrows():
        with cols[i]:
            sev=clean_display_text(r.get("Severity","")) or "Unrated"
            dt=clean_display_text(r.get("Start Date","")) or "Date not recorded"
            geo=clean_display_text(r.get("Location","")) or clean_display_text(r.get("Country / Countries",""))
            impact=clean_display_text(r.get("Operational Impact","")) or clean_display_text(r.get("Trade / Commercial Impact",""))
            title=clean_display_text(r.get("Title","")) or "Untitled intelligence record"
            st.markdown(
                f"""<div class="pc-card" style="border-top:3px solid var(--accent);min-height:240px;">
                <div class="pc-label">{dt} · {sev}</div>
                <div class="pc-big">{title}</div>
                <div class="pc-card-meta" style="margin-top:8px;">{geo}</div>
                <div class="pc-search-details" style="margin-top:12px;">{impact[:360]}</div>
                </div>""",
                unsafe_allow_html=True
            )

    with st.expander("More latest intelligence",expanded=False):
        show_df(
            latest,
            ["Start Date","Event Family","Event Type","Severity","Status","Country / Countries",
             "Location","Title","Operational Impact","Trade / Commercial Impact","Confidence"],
            300
        )

    if st.button("Open full Alerts & Incidents register →",key="home_open_alerts"):
        st.session_state["pcintel_page"]="Alerts & Incidents"
        st.rerun()

def render_monitoring_command_view(df):
    if df is None or df.empty:
        st.info("No monitoring records available.")
        return

    active=df[text_col(df,"Status").str.contains("Active|Developing|Monitoring",case=False,regex=True,na=False)].copy()
    queue=_monitor_queue(active)

    urgent=0
    if not queue.empty:
        urgent=int(queue["_horizon_rank"].le(3).sum())

    reviewed=pd.to_datetime(queue.get("Last Reviewed"),errors="coerce") if (not queue.empty and "Last Reviewed" in queue.columns) else pd.Series(dtype="datetime64[ns]")
    stale=0
    if not reviewed.empty and reviewed.notna().any():
        ref=reviewed.max()
        stale=int((reviewed < (ref-pd.Timedelta(days=7))).sum())

    c1,c2,c3,c4=st.columns(4)
    c1.metric("Active monitors",len(queue))
    c2.metric("24–72h horizons",urgent)
    c3.metric("Recently active areas",int(queue["_activity"].gt(0).sum()) if not queue.empty else 0)
    c4.metric("Review lag >7 days",stale)

    st.markdown("### Priority monitoring queue")
    st.caption("Ordered by active status, time horizon, recent matching activity and review recency. No probability is inferred where the source record does not provide one.")

    if queue.empty:
        st.info("No active/developing monitoring records.")
        return

    qshow=queue.copy()
    qshow["Recent activity (7d)"]=qshow["_activity"]
    show_df(
        qshow,
        ["Title","Family","Geography","Status","Time Horizon","Confidence","Recent activity (7d)",
         "What Is Being Monitored","Trigger / Threshold","Last Reviewed","Next Review / Milestone"],
        420
    )

    choices=list(range(len(queue)))
    pick=st.selectbox(
        "Open monitoring assessment",
        choices,
        format_func=lambda i:(
            f"{clean_display_text(queue.iloc[i].get('Geography',''))} — "
            f"{clean_display_text(queue.iloc[i].get('Title','Monitoring'))}"
        ),
        key="pc_monitor_assessment"
    )
    r=queue.iloc[pick]

    st.markdown("### Current judgement & warning framework")
    a,b,c,d=st.columns(4)
    a.metric("Status",clean_display_text(r.get("Status","")) or "—")
    b.metric("Horizon",clean_display_text(r.get("Time Horizon","")) or "—")
    c.metric("Confidence",clean_display_text(r.get("Confidence","")) or "—")
    d.metric("Recent matched events",int(r.get("_activity",0)))

    judgement=clean_display_text(r.get("What Is Being Monitored",""))
    notes=clean_display_text(r.get("Notes",""))
    st.markdown(
        f"""<div class="pc-card">
        <div class="pc-label">CURRENT JUDGEMENT / MONITORING QUESTION</div>
        <div class="pc-big">{clean_display_text(r.get('Title',''))}</div>
        <div class="pc-search-details" style="margin-top:12px;">{judgement or 'No monitoring judgement has been recorded.'}</div>
        {f"<div class='pc-card-body' style='margin-top:10px;'>{notes}</div>" if notes else ""}
        </div>""",
        unsafe_allow_html=True
    )

    inds=_split_indicators(r.get("Key Indicators",""))
    l,rcol=st.columns([1.15,1])
    with l:
        st.markdown("#### Priority indicators")
        if inds:
            for n,item in enumerate(inds[:10],1):
                st.markdown(f"**{n}.** {item}")
        else:
            st.caption("No structured indicators recorded.")
    with rcol:
        st.markdown("#### Trigger / threshold")
        trig=clean_display_text(r.get("Trigger / Threshold",""))
        nxt=clean_display_text(r.get("Next Review / Milestone",""))
        st.markdown(
            f"""<div class="pc-card">
            <div class="pc-card-impact">{trig or 'No explicit threshold recorded.'}</div>
            <div class="pc-label" style="margin-top:14px;">NEXT REVIEW / MILESTONE</div>
            <div>{nxt or 'Not recorded.'}</div>
            </div>""",
            unsafe_allow_html=True
        )

    geo=clean_display_text(r.get("Geography",""))
    ev=watch_area_events(geo)
    st.markdown("#### Evidence / recent activity")
    if ev is None or ev.empty:
        st.caption("No matching event records currently support this monitoring area.")
    else:
        if "Start Date" in ev.columns:
            ev=ev.copy()
            ev["_d"]=pd.to_datetime(ev["Start Date"],errors="coerce")
            ev=ev.sort_values("_d",ascending=False)
        show_df(
            ev.head(12),
            ["Start Date","Event Type","Severity","Status","Location","Title",
             "Operational Impact","Trade / Commercial Impact","Confidence"],
            330
        )


# -----------------------------------------------------------------------------
# Regional map helpers
# -----------------------------------------------------------------------------
PC_MAP_REGIONS = {
    "Global": [],

    "Africa": [
        "africa","algeria","angola","benin","botswana","burkina faso","burundi","cameroon",
        "cape verde","central african republic","chad","comoros","congo","djibouti","egypt",
        "equatorial guinea","eritrea","eswatini","ethiopia","gabon","gambia","ghana","guinea",
        "guinea-bissau","ivory coast","cote d'ivoire","kenya","lesotho","liberia","libya",
        "madagascar","malawi","mali","mauritania","mauritius","morocco","mozambique","namibia",
        "niger","nigeria","rwanda","sao tome","senegal","seychelles","sierra leone","somalia",
        "south africa","south sudan","sudan","tanzania","togo","tunisia","uganda","zambia","zimbabwe",
        "gulf of guinea","horn of africa","sahel","cape of good hope","durban","mombasa","lagos",
        "maputo","dar es salaam","alexandria","port said"
    ],
    "Europe": [
        "europe","albania","andorra","austria","belarus","belgium","bosnia","bulgaria","croatia",
        "cyprus","czech","denmark","estonia","finland","france","germany","greece","hungary",
        "iceland","ireland","italy","kosovo","latvia","liechtenstein","lithuania","luxembourg",
        "malta","moldova","monaco","montenegro","netherlands","north macedonia","norway","poland",
        "portugal","romania","san marino","serbia","slovakia","slovenia","spain","sweden",
        "switzerland","ukraine","united kingdom","uk","britain","england","scotland","wales",
        "baltic","north sea","english channel","mediterranean","black sea","adriatic","aegean",
        "rotterdam","hamburg","antwerp","bremerhaven","piraeus","constanta","gdansk"
    ],
    "North America": [
        "north america","united states","usa","u.s.","canada","mexico","greenland",
        "alaska","hawaii","gulf of mexico","great lakes","atlantic coast","pacific coast",
        "los angeles","long beach","oakland","seattle","tacoma","vancouver","prince rupert",
        "new york","new jersey","savannah","houston","montreal","halifax","churchill"
    ],
    "South America": [
        "south america","argentina","bolivia","brazil","chile","colombia","ecuador","guyana",
        "paraguay","peru","suriname","uruguay","venezuela","amazon","patagonia",
        "santos","paranagua","rio de janeiro","buenos aires","montevideo","callao",
        "cartagena","guayaquil","valparaiso"
    ],
    "Central America & Caribbean": [
        "central america","caribbean","belize","costa rica","el salvador","guatemala","honduras",
        "nicaragua","panama","bahamas","barbados","cuba","dominican republic","haiti","jamaica",
        "trinidad","tobago","puerto rico","lesser antilles","greater antilles",
        "panama canal","colon","balboa","kingston","freeport"
    ],
    "Middle East": [
        "middle east","gulf","persian gulf","arabian gulf","strait of hormuz","hormuz",
        "gulf of oman","red sea","bab al-mandab","suez","iran","iraq","israel","jordan",
        "lebanon","oman","qatar","saudi arabia","syria","turkey","uae","united arab emirates",
        "yemen","bahrain","kuwait","abu dhabi","dubai","fujairah","jeddah","dammam","doha",
        "muscat","salalah","aqaba","hodeidah","hudaydah","mokha"
    ],
    "Asia": [
        "asia","china","india","japan","south korea","north korea","taiwan","mongolia",
        "pakistan","bangladesh","sri lanka","nepal","bhutan","maldives","myanmar","thailand",
        "vietnam","cambodia","laos","malaysia","singapore","indonesia","philippines","brunei",
        "timor-leste","kazakhstan","uzbekistan","turkmenistan","kyrgyzstan","tajikistan",
        "south china sea","east china sea","yellow sea","strait of malacca","bay of bengal",
        "arabian sea","singapore strait","taiwan strait","shanghai","shenzhen","ningbo",
        "busan","yokohama","mumbai","mundra","colombo","port klang","tanjung pelepas"
    ],
    "Oceania & Pacific": [
        "oceania","pacific","australia","new zealand","papua new guinea","fiji","solomon islands",
        "vanuatu","samoa","tonga","kiribati","tuvalu","nauru","palau","marshall islands",
        "micronesia","guam","new caledonia","tasmania","auckland","sydney","melbourne",
        "brisbane","fremantle","suva"
    ],
    "Arctic & High North": [
        "arctic","high north","barents","greenland","nunavut","svalbard","iceland","faroe",
        "churchill","murmansk","arkhangelsk","northern sea route","northwest passage",
        "bering sea","bering strait"
    ],

    "Gulf / Strait of Hormuz": [
        "hormuz","persian gulf","arabian gulf","gulf of oman","oman","uae","united arab emirates",
        "dubai","abu dhabi","iran","qeshm","musandam","khasab","fujairah","ras al khaimah"
    ],
    "Red Sea / Bab al-Mandab": [
        "red sea","bab al-mandab","yemen","hodeidah","hudaydah","mokha","djibouti","eritrea",
        "jeddah","suez","aqaba","southern red sea"
    ],
    "Black Sea": [
        "black sea","ukraine","russia","romania","bulgaria","turkey","istanbul","bosporus","bosphorus",
        "odessa","odesa","novorossiysk","constanta","crimea","danube"
    ],
    "Mediterranean": [
        "mediterranean","crete","libya","cyprus","greece","italy","malta","ionian","sicily","levant"
    ],
    "Baltic / North Sea": [
        "baltic","north sea","estonia","latvia","lithuania","finland","sweden","poland","denmark",
        "germany","netherlands","belgium","gdansk","klaipeda","riga","tallinn","gotland",
        "kaliningrad","rotterdam","hamburg","bremerhaven","antwerp"
    ],
    "Indo-Pacific Maritime": [
        "south china sea","east china sea","malacca","singapore","indonesia","philippines","malaysia",
        "taiwan","japan","korea","pacific","guam","hawaii","micronesia","australia"
    ],
}

def _pc_map_event_blob(df):
    if df is None or df.empty:
        return pd.Series(dtype="string")
    blob=pd.Series("",index=df.index,dtype="string")
    for c in ["Country / Countries","Location","Title","Description","Event Family","Event Type","Mode"]:
        if c in df.columns:
            blob=blob.str.cat(df[c].fillna("").astype(str),sep=" ")
    return blob.str.casefold()

def pc_region_events(region_name):
    base=hazard_events.copy()
    if base is None or base.empty or region_name=="Global":
        return base
    terms=PC_MAP_REGIONS.get(region_name,[])
    if not terms:
        return base
    blob=_pc_map_event_blob(base)
    pat="|".join(re.escape(x.casefold()) for x in terms)
    return base[blob.str.contains(pat,regex=True,na=False)].copy()

def pc_event_map_points(events):
    if events is None or events.empty or event_locations is None or event_locations.empty:
        return pd.DataFrame()
    if "Event ID" not in events.columns or "Event ID" not in event_locations.columns:
        return pd.DataFrame()

    loc=event_locations.copy()
    lat_col=next((c for c in ["Latitude","Lat","latitude","lat"] if c in loc.columns),None)
    lon_col=next((c for c in ["Longitude","Lon","Lng","longitude","lon","lng"] if c in loc.columns),None)
    if not lat_col or not lon_col:
        return pd.DataFrame()

    loc["latitude"]=pd.to_numeric(loc[lat_col],errors="coerce")
    loc["longitude"]=pd.to_numeric(loc[lon_col],errors="coerce")
    loc=loc[loc["latitude"].notna() & loc["longitude"].notna()].copy()
    if loc.empty:
        return loc

    keep=[c for c in ["Event ID","Start Date","Severity","Status","Event Family","Event Type","Title","Location","Country / Countries"] if c in events.columns]
    ev=events[keep].drop_duplicates(subset=["Event ID"])
    merged=loc.merge(ev,on="Event ID",how="inner",suffixes=("_map",""))
    return merged

# -----------------------------------------------------------------------------
# 1. OPERATING PICTURE
# -----------------------------------------------------------------------------
if page == "Operating Picture":
    render_latest_intelligence_strip()

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
# 2. REGIONAL MAPS
# -----------------------------------------------------------------------------
elif page == "Regional Maps":
    section(
        "Operating picture",
        "Regional Maps",
        "Map-first regional view of the shared event layer. Only supported coordinates are plotted."
    )

    region=st.selectbox("Region / theatre",list(PC_MAP_REGIONS.keys()),key="pcintel_map_region")
    ev=pc_region_events(region)
    pts=pc_event_map_points(ev)

    c1,c2,c3=st.columns(3)
    c1.metric("Regional events",len(ev))
    c2.metric("Mapped points",len(pts))
    mapped_event_count=pts["Event ID"].astype(str).nunique() if (not pts.empty and "Event ID" in pts.columns) else 0
    c3.metric("Events without mapped point",max(len(ev)-mapped_event_count,0))

    if not pts.empty:
        st.map(pts[["latitude","longitude"]],use_container_width=True)

        st.markdown("### Mapped incident register")
        display=pts.copy()
        cols=[c for c in [
            "Start Date","Event Family","Event Type","Severity","Status",
            "Country / Countries","Location","Title","Event ID"
        ] if c in display.columns]
        show_df(display,cols,420)
    elif not ev.empty:
        st.info("This region has events, but none currently have supported coordinates in Event Locations.")
    else:
        st.info("No qualifying events are currently loaded for this region.")

# -----------------------------------------------------------------------------
# 3. ALERTS & INCIDENTS
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
    section(
        "04 · Forward",
        "Monitoring & Indicators",
        "A warning framework rather than a flat register: prioritised monitors, current judgement, indicators, thresholds, evidence and review discipline."
    )

    df=monitoring.copy()
    if df.empty:
        st.info("No monitoring records available.")
    else:
        f1,f2,f3=st.columns(3)
        status_opts=["All"]+sorted([x for x in text_col(df,"Status").unique() if x])
        family_opts=["All"]+sorted([x for x in text_col(df,"Family").unique() if x])
        geo_opts=["All"]+sorted([x for x in text_col(df,"Geography").unique() if x])
        st_sel=f1.selectbox("Status",status_opts,key="monitor_status_filter")
        fam_sel=f2.selectbox("Family",family_opts,key="monitor_family_filter")
        geo_sel=f3.selectbox("Geography",geo_opts,key="monitor_geo_filter")
        if st_sel!="All":
            df=df[text_col(df,"Status").eq(st_sel)]
        if fam_sel!="All":
            df=df[text_col(df,"Family").eq(fam_sel)]
        if geo_sel!="All":
            df=df[text_col(df,"Geography").eq(geo_sel)]

        render_monitoring_command_view(df)

        with st.expander("Full monitoring register",expanded=False):
            show_df(
                df,
                ["Title","Family","Geography","Status","Start Date","Time Horizon",
                 "What Is Being Monitored","Key Indicators","Trigger / Threshold",
                 "Confidence","Last Reviewed","Next Review / Milestone","Notes"],
                500
            )

# -----------------------------------------------------------------------------
# 5. MARITIME SECURITY
# -----------------------------------------------------------------------------
elif page == "Maritime Security":
    section("Domain intelligence", "Maritime Security", "Vessel attacks, piracy, groundings, SAR, pollution, seizures, restrictions and official coast-guard reporting.")
    maritime_terms = ["Maritime","Vessel","Piracy","Ground","Collision","SAR","Pollution","Boarding","Seizure","Ship","Tanker","Container"]
    me = hazard_events[contains_any(hazard_events,["Event Family","Event Type","Mode","Title","Description"], maritime_terms)] if not hazard_events.empty else hazard_events
    f1,f2 = st.columns([1,1])
    with f1:
        st.metric("Maritime-relevant events", len(me))
    with f2:
        st.metric("Tracked vessel restrictions", len(vessel_restrictions))
    tab1,tab2,tab3 = st.tabs(["Incidents", "Vessels & Restrictions", "Official MARSEC Sources"])
    with tab1:
        show_df(me, ["Start Date","Event Type","Severity","Status","Country / Countries","Location","Title","Operational Impact","Trade / Commercial Impact","Confidence"], 500)
    with tab2:
        show_df(vessel_restrictions, ["Vessel Name","IMO","Authority / Regime","Restriction Type","Status","Effective Date","Direct / Indirect","Basis","Last Verified","Notes"], 360)
        if not vessels.empty and "Vessel Name" in vessels.columns:
            choices = sorted(vessels["Vessel Name"].dropna().astype(str).unique().tolist())
            vessel_name = st.selectbox("Open canonical vessel", choices)
            vr = vessels[text_col(vessels,"Vessel Name").eq(vessel_name)]
            show_df(vr, ["Vessel Name","IMO","Vessel Type","Subtype / Class","Flag","Year Built","DWT","Status","Registered Owner (Legal)","Technical / ISM Manager","Completeness Note"], 180)
            imo = normalize_imo(vr.iloc[0].get("IMO", "")) if not vr.empty else ""
            rr = vessel_restrictions[vessel_restrictions["IMO"].map(normalize_imo).eq(imo)] if imo and not vessel_restrictions.empty else pd.DataFrame()
            if not rr.empty:
                st.caption("Security & compliance attached to this canonical vessel")
                show_df(rr, ["Authority / Regime","Restriction Type","Status","Effective Date","Direct / Indirect","Basis","Last Verified","Notes"], 180)
    with tab3:
        sf = source_feeds[contains_any(source_feeds,["Source Name","Default Event Families","Coverage"], ["Coast Guard","Maritime","SAR","Grounding","Collision","Pollution","Rescue","UKMTO","ReCAAP"])] if not source_feeds.empty else source_feeds
        show_df(sf, ["Source Name","Coverage","Default Event Families","Priority","Active","Last Checked","Notes"], 430)

# -----------------------------------------------------------------------------
# 6. PORTS & INFRASTRUCTURE
# -----------------------------------------------------------------------------
elif page == "Ports & Infrastructure":
    section("Domain intelligence", "Ports & Critical Infrastructure", "Port incidents, attacks, explosions, weather, labour disruption and exposure across connected infrastructure.")
    port_terms = ["Port","Terminal","Infrastructure","Explosion","Strike","Closure","Drone","Missile","Weather","Flood","Fire","Low water"]
    pe = hazard_events[contains_any(hazard_events,["Event Family","Event Type","Mode","Title","Description"], port_terms)] if not hazard_events.empty else hazard_events
    c1,c2,c3 = st.columns(3)
    c1.metric("Tracked ports", len(ports))
    c2.metric("Infrastructure assets", len(infra_assets))
    c3.metric("Port / infrastructure events", len(pe))
    tab1,tab2,tab3 = st.tabs(["Events", "Port Drill-down", "Critical Infrastructure"])
    with tab1:
        show_df(pe, ["Start Date","Event Type","Severity","Country / Countries","Location","Title","Operational Impact","Trade / Commercial Impact","Confidence"], 470)
    with tab2:
        if not ports.empty:
            pnames = sorted(ports["Port / Facility"].dropna().astype(str).unique().tolist())
            pname = st.selectbox("Port / facility", pnames)
            pr = ports[text_col(ports,"Port / Facility").eq(pname)]
            show_df(pr, ["Port / Facility","Country","Operator","Facility Type","Key Role","Coverage Note"], 170)
            pid = str(pr.iloc[0].get("Port ID", "")) if not pr.empty else ""
            linked = event_asset_links[text_col(event_asset_links,"Asset ID").eq(pid)] if pid and not event_asset_links.empty else pd.DataFrame()
            if linked.empty:
                linked = event_asset_links[text_col(event_asset_links,"Asset").str.contains(pname, case=False, regex=False, na=False)] if not event_asset_links.empty else pd.DataFrame()
            show_df(linked, ["Event ID","Asset","Asset Type","Relationship","Confidence","Notes"], 220)
    with tab3:
        show_df(infra_assets, ["Asset","Asset Type","Location","Country","Role / Function","Primary Mode","Status","Ownership / Operating Interest"], 350)
        show_df(dry_ports, ["Hub Name","Country","City / Region","Hub Type","Status","Rail Access","Road Access","Air Access","Linked Seaports / Gateways"], 250)

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
    if POLICY_DATA_SOURCES:
        st.caption("Data bridge: " + " · ".join(sorted(POLICY_DATA_SOURCES)))
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
    section("Discovery", "Intelligence Search", "Search incidents, monitoring, vessels, ports, companies, sanctions/compliance and source feeds from the shared live canonical data layer.")
    q = st.text_input("Search the P&C intelligence base", placeholder="e.g. Hormuz, Mraweh, Rotterdam, PGSA, Japan Coast Guard, drone...")
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
st.markdown('<div class="small-note">P&C Intelligence · v3.6 · Live-canonical-first data bridge + latest intelligence + prioritised monitoring.</div>', unsafe_allow_html=True)
