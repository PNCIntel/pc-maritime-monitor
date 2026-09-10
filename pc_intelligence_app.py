import streamlit as st
import pandas as pd
import re
try:
    import pydeck as pdk
except Exception:
    pdk = None
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

# -----------------------------------------------------------------------------
# Data helpers — all reads are from the same Excel-backed P&C model
# -----------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def _xl_cached(file_name: str, sheet: str, modified_ns: int, file_size: int) -> pd.DataFrame:
    """Read one Excel sheet. File fingerprint is part of the Streamlit cache key."""
    path = DATA / file_name
    df = pd.read_excel(path, sheet_name=sheet)
    return df.dropna(how="all")


def xl(file_name: str, sheet: str) -> pd.DataFrame:
    """
    Read a shared-model workbook and invalidate cached data whenever the underlying
    Excel file changes, even when the filename is unchanged.
    """
    path = DATA / file_name
    if not path.exists():
        return pd.DataFrame()
    try:
        stat = path.stat()
        return _xl_cached(file_name, sheet, stat.st_mtime_ns, stat.st_size)
    except Exception:
        return pd.DataFrame()


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


# Core canonical datasets
companies = xl("01_core_entities.xlsx", "Companies")
ports = xl("02_maritime.xlsx", "Ports")
vessels = xl("02_maritime.xlsx", "Vessels")
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
security_view = pd.DataFrame()  # optional view not present in current workbook

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
sanctions_authorities = xl("14_trade_policy_compliance.xlsx", "Sanctions Authorities")
sanctions_programmes = xl("14_trade_policy_compliance.xlsx", "Sanctions Programmes")
sanctions_designations = xl("14_trade_policy_compliance.xlsx", "Sanctions Designations")
sanctions_links = xl("14_trade_policy_compliance.xlsx", "Sanctions Entity Links")
compliance_regimes = pd.DataFrame()  # optional future normalized table
compliance_designations = pd.DataFrame()  # optional future normalized table
compliance_exposure = pd.DataFrame()  # optional future normalized table
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

NAV = {
    "INTELLIGENCE DESK": ["Operating Picture", "Alerts & Incidents"],
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
st.sidebar.caption("Excel-backed v3.0 · shared P&C canonical data")

with st.sidebar.expander("Data status", expanded=False):
    _required_files = [
        "01_core_entities.xlsx",
        "02_maritime.xlsx",
        "05_aviation.xlsx",
        "06_infrastructure.xlsx",
        "09_intelligence.xlsx",
        "10_sources_evidence.xlsx",
        "13_events_hazards.xlsx",
        "14_trade_policy_compliance.xlsx",
    ]

    _missing_files = []
    for _fn in _required_files:
        _fs = data_file_status(_fn)
        if _fs["exists"]:
            st.caption(f"✓ {_fn} · {_fs['size'] / 1024:.1f} KB")
        else:
            st.error(f"✗ {_fn} missing")
            _missing_files.append(_fn)

    st.markdown("---")
    if not hazard_events.empty:
        st.caption(f"Events loaded: {len(hazard_events):,}")
        st.caption(f"Mapped location records: {len(event_locations):,}")
        if "Start Date" in hazard_events.columns:
            _latest_dt = pd.to_datetime(hazard_events["Start Date"], errors="coerce").max()
            if pd.notna(_latest_dt):
                st.caption(f"Latest event date: {_latest_dt.strftime('%Y-%m-%d')}")
        if len(hazard_events) == 45:
            st.success("Current 10 Sep security dataset loaded.")
        else:
            st.warning(
                f"Expected 45 event records in the current deployment package; "
                f"this app has loaded {len(hazard_events)}."
            )
    else:
        st.error("Events sheet did not load.")

    if st.button("Refresh Excel data", key="refresh_excel_data"):
        st.cache_data.clear()
        st.rerun()


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
            "with the latest workbook and use Data status → Refresh Excel data."
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
st.markdown('<div class="small-note">P&C Intelligence · Excel-backed v3.0 · Dedicated security and operational intelligence interface.</div>', unsafe_allow_html=True)
