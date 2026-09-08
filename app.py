from pathlib import Path
import re
import pandas as pd
import streamlit as st

APP_TITLE = "P&C Trade System"
APP_VERSION = "v1.20"
DATA_DIR = Path(__file__).parent / "data"

st.set_page_config(
    page_title=f"{APP_TITLE} {APP_VERSION}",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------- Theme ----------
st.markdown("""
<style>
:root {
  --pc-bg:#07111f;
  --pc-panel:#0d1a2b;
  --pc-panel2:#101f33;
  --pc-border:#2a415e;
  --pc-text:#f2f5f9;
  --pc-muted:#b7c4d3;
  --pc-gold:#d7b66a;
  --pc-blue:#76bde8;
  --pc-sidebar:#091725;
}

/* App surfaces */
.stApp { background:var(--pc-bg); color:var(--pc-text); }
[data-testid="stAppViewContainer"], [data-testid="stMain"] { background:var(--pc-bg); }
[data-testid="stSidebar"] {
  background:var(--pc-sidebar) !important;
  border-right:1px solid var(--pc-border);
}
[data-testid="stSidebar"] > div { background:var(--pc-sidebar) !important; }

/* Force readable text in the dark theme, especially after Streamlit upgrades */
h1,h2,h3,h4,h5,h6,p,li,span,label { color:var(--pc-text); }
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] div { color:var(--pc-text) !important; }
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p,
[data-testid="stSidebar"] small { color:var(--pc-muted) !important; }
[data-testid="stSidebar"] [role="radiogroup"] label p { color:var(--pc-text) !important; }
[data-testid="stSidebar"] [role="radiogroup"] label { opacity:1 !important; }
[data-testid="stSidebar"] input[type="radio"] { accent-color:var(--pc-gold); }
/* Streamlit/BaseWeb radio markup can override inherited colors; target every text layer. */
[data-testid="stSidebar"] [role="radiogroup"] * { color:var(--pc-text) !important; }
[data-testid="stSidebar"] [role="radiogroup"] [data-testid="stMarkdownContainer"] p {
  color:var(--pc-text) !important; opacity:1 !important; font-weight:500;
}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h3 {
  color:#ffffff !important; opacity:1 !important;
}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] { opacity:1 !important; }
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p { color:#c8d4e3 !important; }

/* Widget labels and controls */
[data-testid="stWidgetLabel"] p,
[data-testid="stSelectbox"] label,
[data-testid="stMultiSelect"] label,
[data-testid="stTextInput"] label,
[data-testid="stNumberInput"] label,
[data-testid="stCheckbox"] label,
[data-testid="stRadio"] label { color:var(--pc-text) !important; }
[data-baseweb="select"] > div,
[data-baseweb="input"] > div,
.stTextInput input,
.stNumberInput input {
  background:var(--pc-panel) !important;
  color:var(--pc-text) !important;
  border-color:var(--pc-border) !important;
}

.pc-kicker { color:var(--pc-gold); font-size:.78rem; letter-spacing:.14em; text-transform:uppercase; font-weight:700; }
.pc-title { color:var(--pc-text); font-size:2rem; font-weight:800; margin:.2rem 0 .1rem; }
.pc-sub { color:var(--pc-muted); margin-bottom:1.1rem; }
.pc-card {
  background:linear-gradient(180deg,var(--pc-panel),var(--pc-panel2));
  border:1px solid var(--pc-border);
  border-radius:12px; padding:15px 17px; min-height:104px;
}
.pc-label { color:var(--pc-muted); font-size:.75rem; text-transform:uppercase; letter-spacing:.07em; }
.pc-value { color:var(--pc-text); font-size:1.45rem; font-weight:760; margin-top:3px; }
.pc-small { color:var(--pc-muted); font-size:.84rem; line-height:1.35; }
.pc-rule { border-top:1px solid var(--pc-border); margin:1rem 0; }

div[data-testid="stMetric"] {
  background:var(--pc-panel); border:1px solid var(--pc-border);
  border-radius:10px; padding:10px 13px;
}
.stDataFrame { border:1px solid var(--pc-border); border-radius:9px; }
a { color:var(--pc-blue) !important; }

/* Keep tables and cards inside the available width */
[data-testid="stHorizontalBlock"] { gap:.75rem; }
[data-testid="column"] { min-width:0; }

/* Better contrast for tabs and expanders */
button[data-baseweb="tab"] p { color:var(--pc-muted) !important; }
button[data-baseweb="tab"][aria-selected="true"] p { color:var(--pc-text) !important; }
[data-testid="stExpander"] summary p { color:var(--pc-text) !important; }
</style>
""", unsafe_allow_html=True)

# ---------- Data helpers ----------
@st.cache_data(show_spinner=False)
def load_csv(name):
    path = DATA_DIR / name
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str, keep_default_na=False)
    except Exception:
        return pd.DataFrame()

TABLES = {
    "companies": "companies.csv",
    "relationships": "relationships.csv",
    "entity_registry": "entity_registry.csv",
    "corridors": "corridors.csv",
    "system_nodes": "system_nodes.csv",
    "system_links": "system_links.csv",
    "ports": "ports.csv",
    "terminals": "port_terminals.csv",
    "port_operator_coverage": "port_operator_coverage.csv",
    "berths": "port_berths.csv",
    "equipment": "port_equipment.csv",
    "ownership": "port_ownership.csv",
    "port_news": "port_news.csv",
    "vessels": "vessels.csv",
    "vessel_relationships": "vessel_relationships.csv",
    "fleet_portfolios": "fleet_portfolios.csv",
    "fleet_orders": "fleet_orders.csv",
    "aircraft": "aircraft_registry.csv",
    "aircraft_relationships": "aircraft_relationships.csv",
    "aviation_summary": "aviation_fleet_summary.csv",
    "assets": "assets.csv",
    "shipyards": "shipyards.csv",
    "infra_works": "infrastructure_works.csv",
    "infra_deals": "infrastructure_deals.csv",
    "infra_investors": "infrastructure_investors.csv",
    "infra_holdings": "infrastructure_holdings.csv",
    "connections": "infrastructure_connections.csv",
    "logistics_networks": "integrated_logistics_networks.csv",
    "rail_operators": "rail_operators.csv",
    "rail_networks": "rail_networks.csv",
    "rail_nodes": "rail_nodes.csv",
    "rail_links": "rail_links.csv",
    "rail_relationships": "rail_relationships.csv",
    "rail_fleet": "rail_fleet.csv",
    "rail_connections": "rail_connections.csv",
    "rail_news": "rail_news.csv",
    "events": "strategic_events.csv",
    "event_observations": "event_observations.csv",
    "event_links": "event_entity_links.csv",
    "news": "news_registry.csv",
    "news_links": "news_entity_links.csv",
    "monitoring": "monitoring.csv",
    "monitoring_links": "monitoring_event_links.csv",
    "transaction_links": "transaction_asset_links.csv",
    "asset_constraints": "asset_constraints.csv",
    "asset_control": "asset_control_history.csv",
    "sources": "sources.csv",
    "ferry_systems": "ferry_systems.csv",
    "ferry_routes": "ferry_routes.csv",
    "ferry_terminals": "ferry_terminals.csv",
    "ferry_status": "ferry_fleet_status.csv",
    "ferry_performance": "ferry_performance.csv",
    "great_lakes_ports": "great_lakes_ports.csv",
    "great_lakes_vessels": "great_lakes_vessel_staging.csv",
    "great_lakes_corridors": "great_lakes_cargo_corridors.csv",
    "great_lakes_cruise": "great_lakes_cruise.csv",
    "great_lakes_disruptions": "great_lakes_disruptions.csv",
}

D = {k: load_csv(v) for k, v in TABLES.items()}

def col(df, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    return None

def _build_name_maps():
    """Build lookup maps so internal join keys never have to be shown to users."""
    maps = {}

    def add_map(df_key, id_cols, name_cols):
        df = D.get(df_key, pd.DataFrame())
        if df.empty:
            return
        ic = col(df, id_cols)
        nc = col(df, name_cols)
        if not ic or not nc:
            return
        vals = {
            str(r[ic]).strip(): str(r[nc]).strip()
            for _, r in df[[ic, nc]].iterrows()
            if str(r.get(ic, '')).strip() and str(r.get(nc, '')).strip()
        }
        if vals:
            maps.update(vals)

    # Canonical organizations and generic registry first.
    add_map('companies', ['Company ID'], ['Company', 'Company Name'])
    add_map('entity_registry', ['Entity ID'], ['Canonical Name'])
    add_map('ports', ['Port ID'], ['Port / Facility', 'Port'])
    add_map('terminals', ['Terminal ID'], ['Terminal / Facility', 'Terminal'])
    add_map('vessels', ['Vessel ID'], ['Vessel Name'])
    add_map('assets', ['Asset ID'], ['Asset'])
    add_map('shipyards', ['Shipyard ID'], ['Shipyard'])
    add_map('corridors', ['Corridor ID'], ['Corridor'])
    add_map('rail_networks', ['Rail Network ID'], ['Network / Corridor'])
    add_map('rail_nodes', ['Rail Node ID'], ['Node'])
    add_map('rail_operators', ['Rail Operator ID'], ['Operator'])
    add_map('ferry_systems', ['System ID'], ['System Name'])
    add_map('ferry_routes', ['Route ID'], ['Route Name'])
    add_map('ferry_terminals', ['Terminal ID'], ['Terminal Name'])
    add_map('monitoring', ['Monitoring ID'], ['Title'])
    add_map('news', ['News ID'], ['Headline'])
    add_map('events', ['Event ID'], ['Title'])

    # Aircraft are best represented by registration, falling back to type.
    adf = D.get('aircraft', pd.DataFrame())
    if not adf.empty and 'Aircraft ID' in adf.columns:
        for _, r in adf.iterrows():
            aid = str(r.get('Aircraft ID', '')).strip()
            if not aid:
                continue
            reg = str(r.get('Registration', '')).strip()
            typ = str(r.get('Aircraft Type', '')).strip()
            maps[aid] = reg or typ or aid

    return maps

NAME_MAP = _build_name_maps()

# Source keys get a readable publisher/source label when useful.
SOURCE_NAME_MAP = {}
if not D.get('sources', pd.DataFrame()).empty:
    sdf = D['sources']
    if 'Source ID' in sdf.columns:
        for _, r in sdf.iterrows():
            sid = str(r.get('Source ID', '')).strip()
            label = str(r.get('Publisher', '')).strip() or str(r.get('Source Note', '')).strip()
            if sid and label:
                SOURCE_NAME_MAP[sid] = label

_INTERNAL_ID_COLUMNS = {
    'Relationship ID','Aircraft Relationship ID','Rail Relationship ID','Vessel Relationship ID',
    'Ownership ID','Observation ID','Canonical Event ID','Source Record ID','News ID',
    'Monitoring ID','Deal ID','Work ID','Shipyard ID','Equipment Record ID','Event Link ID',
    'News Link ID','Transaction Link ID','Control Record ID','Constraint ID','Program ID',
    'Footprint ID','Coverage ID','Order ID','Fleet ID','Staging ID','Status ID','Performance ID',
    'Impact ID','External Event ID','Research ID','Feed ID','Build Record ID','Contract ID',
    'Evidence ID','Restriction ID','Transaction ID','Assessment ID','Dependency ID','Link ID',
    'Node ID','Rail Link ID','Rail Connection ID','Rail Fleet Record ID','Rail News ID',
}

# ID columns that are foreign keys and should become readable names instead of disappearing.
_FOREIGN_ID_LABELS = {
    'Company ID': 'Company',
    'Owner Company ID': 'Owner',
    'Operator Company ID': 'Operator',
    'Primary Operator Company ID': 'Primary Operator',
    'Lead Operator Company ID': 'Lead Operator',
    'Primary Company ID': 'Primary Company',
    'Network Customer Company ID': 'Network Customer',
    'Buyer / Operator Company ID': 'Buyer / Operator',
    'Buyer Company ID': 'Buyer',
    'Seller Company ID': 'Seller',
    'Investor / Buyer IDs': 'Investor / Buyer',
    'Co-Investor / Partner IDs': 'Co-Investor / Partner',
    'Investor / Owner Company IDs': 'Investor / Owner',
    'Parent / Investor Company ID': 'Parent / Investor',
    'Parent / Owner Company ID': 'Parent / Owner',
    'Controller Entity ID': 'Controller',
    'Subject Entity ID': 'Subject',
    'Parent Entity ID': 'Parent Entity',
    'Entity ID': 'Entity',
    'Source Entity': 'Source',
    'Target Entity': 'Target',
    'Target Entity / Asset ID': 'Target / Asset',
    'Entity / Asset ID': 'Entity / Asset',
    'Asset / Port ID': 'Asset / Port',
    'Asset ID': 'Asset',
    'Port ID': 'Port',
    'Linked Port ID': 'Linked Port',
    'Terminal ID': 'Terminal',
    'Linked Terminal ID': 'Linked Terminal',
    'Vessel ID': 'Vessel',
    'Canonical Vessel ID': 'Vessel',
    'Aircraft ID': 'Aircraft',
    'Rail Network ID': 'Rail Network',
    'Rail Node ID': 'Rail Node',
    'Origin Rail Node ID': 'Origin Rail Node',
    'Destination Rail Node ID': 'Destination Rail Node',
    'System ID': 'System',
    'Route ID': 'Route',
    'Origin Terminal ID': 'Origin Terminal',
    'Destination Terminal ID': 'Destination Terminal',
    'Corridor ID': 'Corridor',
    'Connected Entity ID': 'Connected Entity',
    'Subject ID': 'Subject',
}

_ACRONYMS = {
    'JV':'JV','IMO':'IMO','ISM':'ISM','AIS':'AIS','LNG':'LNG','LPG':'LPG','TEU':'TEU',
    'UAE':'UAE','UK':'UK','US':'US','EU':'EU','P&I':'P&I','M&A':'M&A','DG':'DG'
}

def _human_code(value):
    """Turn model enums such as PART_OF or OWNER_OPERATOR into readable English."""
    v = str(value).strip()
    if not v:
        return v
    # Only normalize code-like enums. Natural prose and identifiers are left untouched.
    if not re.fullmatch(r'[A-Z0-9_&/+ -]+', v):
        return v
    words = []
    for token in v.split('_'):
        if token in _ACRONYMS:
            words.append(_ACRONYMS[token])
        elif token:
            words.append(token.lower())
    if not words:
        return v
    words[0] = words[0] if words[0] in _ACRONYMS.values() else words[0].capitalize()
    return ' '.join(words)

def _resolve_key_token(token, source=False):
    t = str(token).strip()
    if not t:
        return ''
    if source:
        return SOURCE_NAME_MAP.get(t, t)
    return NAME_MAP.get(t, t)

def _resolve_key_value(value, source=False):
    """Resolve one or many semicolon/pipe-separated model keys to display names."""
    v = str(value).strip()
    if not v:
        return v
    # Keep human prose intact; split only the separators used by model key lists.
    if ';' in v:
        return '; '.join(_resolve_key_token(x, source=source) for x in v.split(';') if str(x).strip())
    return _resolve_key_token(v, source=source)

def prepare_display(df):
    """Create a user-facing dataframe while preserving canonical IDs underneath the app."""
    if df.empty:
        return df
    out = df.copy()
    display = pd.DataFrame(index=out.index)

    for c in out.columns:
        # Hide record-management keys completely.
        if c in _INTERNAL_ID_COLUMNS:
            continue

        # Source IDs are implementation keys; expose publisher names only if there is no
        # already-visible source/publisher field that makes them redundant.
        if c in {'Source ID','Primary Source ID','Source IDs','Source ID / Notes'}:
            existing_source_cols = {'Source','Publisher','Primary Source','Source Name','Source URL','URL'} & set(out.columns)
            if existing_source_cols:
                continue
            label = 'Source'
            vals = out[c].map(lambda x: _resolve_key_value(x, source=True))
            if label not in display.columns:
                display[label] = vals
            continue

        if c in _FOREIGN_ID_LABELS:
            label = _FOREIGN_ID_LABELS[c]
            vals = out[c].map(_resolve_key_value)
            # If the source table already has a clean human-name column with the same label,
            # prefer it and suppress the internal-key derivative.
            if label in out.columns and label != c:
                continue
            if label not in display.columns:
                display[label] = vals
            continue

        # Generic foreign-key columns not explicitly listed: resolve if possible, otherwise hide.
        if c.endswith(' ID') or c.endswith(' IDs') or c.lower().endswith('_id'):
            vals = out[c].map(_resolve_key_value)
            changed = (vals.astype(str) != out[c].astype(str)) & (out[c].astype(str).str.strip() != '')
            if changed.any():
                label = re.sub(r'\s+IDs?$', '', c).strip()
                if label not in display.columns and label not in out.columns:
                    display[label] = vals
            continue

        vals = out[c].copy()
        lc = c.lower()
        if any(k in lc for k in ['relationship','link type','role in system','control type']):
            vals = vals.map(_human_code)
        display[c] = vals

    # Avoid duplicated human columns created from a foreign key and an existing descriptive field.
    display = display.loc[:, ~display.columns.duplicated()]
    return display

def clean(df):
    # Backwards-compatible alias used throughout the existing app.
    return prepare_display(df)

def text_search(df, q):
    if df.empty or not q:
        return df
    mask = df.astype(str).apply(
        lambda s: s.str.contains(re.escape(q), case=False, na=False)
    ).any(axis=1)
    return df[mask]

def safe_display(df, max_rows=250):
    """Display a bounded dataframe without passing an explicit height.

    Streamlit Cloud versions validate dataframe height strictly. Historically the
    app used the second positional argument as a row limit (for example 12), and
    an earlier helper accidentally forwarded that value as a pixel height. Keeping
    this helper height-free removes that failure mode entirely.
    """
    if df.empty:
        st.info("No matching records in the current model.")
        return
    show = clean(df).head(max_rows)
    cfg = {}
    for c in show.columns:
        lc = c.lower()
        if lc in {"url","source url","feed url","source reference"} or "url" in lc:
            cfg[c] = st.column_config.LinkColumn(c, display_text="Open")
    st.dataframe(
        show,
        use_container_width=True,
        hide_index=True,
        column_config=cfg,
    )

def entity_news(entity_id):
    nl = D["news_links"]
    n = D["news"]
    if not entity_id or nl.empty or n.empty:
        return pd.DataFrame()
    eid = col(nl, ["Entity ID"])
    nid = col(nl, ["News ID"])
    nnid = col(n, ["News ID"])
    if not all([eid,nid,nnid]):
        return pd.DataFrame()
    links = nl[nl[eid] == entity_id]
    if links.empty:
        return pd.DataFrame()
    return n[n[nnid].isin(links[nid].tolist())].copy()

def event_news(event_id):
    n = D["news"]
    if n.empty or "Canonical Event ID" not in n.columns:
        return pd.DataFrame()
    return n[n["Canonical Event ID"] == event_id].copy()

def entity_events(entity_id):
    el = D["event_links"]
    eo = D["event_observations"]
    if not entity_id or el.empty or eo.empty:
        return pd.DataFrame()
    eid = col(el, ["Entity ID"])
    oid = col(el, ["Observation ID"])
    eoid = col(eo, ["Observation ID"])
    if not all([eid,oid,eoid]):
        return pd.DataFrame()
    hits = el[el[eid] == entity_id]
    return eo[eo[eoid].isin(hits[oid].tolist())].copy() if not hits.empty else pd.DataFrame()

def profile_pairs(row, fields):
    items = []
    for label, key in fields:
        if key in row and str(row[key]).strip():
            items.append((label, row[key]))
    return items

def render_pairs(items, cols=4):
    if not items:
        return
    containers = st.columns(cols)
    for i,(label,value) in enumerate(items):
        containers[i % cols].markdown(
            f"<div class='pc-card'><div class='pc-label'>{label}</div>"
            f"<div class='pc-small'>{value}</div></div>",
            unsafe_allow_html=True
        )

def metric_card(label, value, note=""):
    st.markdown(
        f"<div class='pc-card'><div class='pc-label'>{label}</div>"
        f"<div class='pc-value'>{value}</div><div class='pc-small'>{note}</div></div>",
        unsafe_allow_html=True
    )

def page_header(title, sub):
    st.markdown("<div class='pc-kicker'>Power & Corridors Intelligence</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='pc-title'>{title}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='pc-sub'>{sub}</div>", unsafe_allow_html=True)


# ---------- Relationship graph / watch-area helpers ----------
def _first_existing(row, names, default=""):
    for name in names:
        if name in row and str(row.get(name, "")).strip():
            return str(row.get(name, "")).strip()
    return default

@st.cache_data(show_spinner=False)
def build_entity_index():
    """Return canonical label/type metadata for graph rendering."""
    idx = {}
    er = D.get("entity_registry", pd.DataFrame())
    if not er.empty:
        for _, r in er.iterrows():
            eid = str(r.get("Entity ID", "")).strip()
            if eid:
                idx[eid] = {
                    "label": str(r.get("Canonical Name", eid)).strip() or eid,
                    "type": str(r.get("Entity Type", "Entity")).strip() or "Entity",
                    "country": str(r.get("Country", "")).strip(),
                }

    specs = [
        ("companies", "Company ID", ["Company", "Company Name"], "Company", ["HQ Country"]),
        ("ports", "Port ID", ["Port / Facility", "Port"], "Port", ["Country"]),
        ("terminals", "Terminal ID", ["Terminal / Facility"], "Terminal", ["Country"]),
        ("vessels", "Vessel ID", ["Vessel Name"], "Vessel", ["Flag"]),
        ("assets", "Asset ID", ["Asset", "Asset Name"], "Asset", ["Country"]),
        ("rail_networks", "Rail Network ID", ["Rail Network / Corridor", "Rail Network", "Network / Corridor", "Name"], "Rail Network", ["Countries / Jurisdictions", "Country / Geography", "Country"]),
        ("rail_nodes", "Rail Node ID", ["Node", "Rail Node"], "Rail Node", ["Country"]),
        ("corridors", "Corridor ID", ["Corridor"], "Corridor", ["Country / Region"]),
        ("ferry_systems", "System ID", ["System Name", "Ferry System", "System"], "Ferry System", ["Country / Jurisdiction", "Country"]),
    ]
    for key, idc, names, etype, countries in specs:
        df = D.get(key, pd.DataFrame())
        if df.empty or idc not in df.columns:
            continue
        for _, r in df.iterrows():
            eid = str(r.get(idc, "")).strip()
            if not eid:
                continue
            label = _first_existing(r, names, eid)
            country = _first_existing(r, countries, "")
            prior = idx.get(eid, {})
            idx[eid] = {
                "label": prior.get("label") or label,
                "type": prior.get("type") or etype,
                "country": prior.get("country") or country,
            }
    return idx

@st.cache_data(show_spinner=False)
def build_graph_edges():
    """Normalize relationship-bearing tables into one graph edge list."""
    edges = []
    def add(src, dst, rel, category, source=""):
        src, dst = str(src).strip(), str(dst).strip()
        if src and dst and src != dst:
            edges.append({"source":src, "target":dst, "relationship":str(rel).strip() or "related to", "category":category, "source_table":source})

    rel = D.get("relationships", pd.DataFrame())
    if not rel.empty:
        for _, r in rel.iterrows():
            add(r.get("Source Entity",""), r.get("Target Entity",""), r.get("Relationship","related to"), "Corporate", "relationships")

    vr = D.get("vessel_relationships", pd.DataFrame())
    if not vr.empty:
        for _, r in vr.iterrows():
            add(r.get("Company ID",""), r.get("Vessel ID",""), r.get("Relationship Type", r.get("Relationship","vessel relationship")), "Vessels", "vessel_relationships")

    vessels = D.get("vessels", pd.DataFrame())
    if not vessels.empty:
        for _, r in vessels.iterrows():
            vid = r.get("Vessel ID","")
            add(r.get("Owner Company ID",""), vid, "owns", "Vessels", "vessels")
            add(r.get("Operator Company ID",""), vid, "operates", "Vessels", "vessels")

    terms = D.get("terminals", pd.DataFrame())
    if not terms.empty:
        for _, r in terms.iterrows():
            tid = r.get("Terminal ID","")
            add(r.get("Primary Operator Company ID",""), tid, "operates", "Ports & Terminals", "port_terminals")
            add(r.get("Port ID",""), tid, "contains", "Ports & Terminals", "port_terminals")

    ports = D.get("ports", pd.DataFrame())
    if not ports.empty:
        for _, r in ports.iterrows():
            add(r.get("Operator Company ID",""), r.get("Port ID",""), "operates", "Ports & Terminals", "ports")

    own = D.get("ownership", pd.DataFrame())
    if not own.empty:
        for _, r in own.iterrows():
            add(r.get("Company ID",""), r.get("Terminal ID",""), r.get("Relationship","owns / controls"), "Ownership", "port_ownership")

    rr = D.get("rail_relationships", pd.DataFrame())
    if not rr.empty:
        for _, r in rr.iterrows():
            add(r.get("Company ID",""), r.get("Rail Network ID",""), r.get("Relationship Type","rail relationship"), "Rail", "rail_relationships")

    rn = D.get("rail_nodes", pd.DataFrame())
    if not rn.empty:
        for _, r in rn.iterrows():
            nid = r.get("Rail Node ID","")
            add(r.get("Primary Company ID",""), nid, "operates / controls", "Rail", "rail_nodes")
            add(nid, r.get("Linked Port ID",""), "connects to port", "Rail", "rail_nodes")
            add(nid, r.get("Linked Terminal ID",""), "connects to terminal", "Rail", "rail_nodes")

    rc = D.get("rail_connections", pd.DataFrame())
    if not rc.empty:
        for _, r in rc.iterrows():
            add(r.get("Rail Node ID",""), r.get("Connected Entity ID",""), "rail connection", "Rail", "rail_connections")

    ic = D.get("connections", pd.DataFrame())
    if not ic.empty:
        for _, r in ic.iterrows():
            add(r.get("Source Asset ID",""), r.get("Target Entity / Asset ID",""), r.get("Relationship","connected to"), "Infrastructure", "infrastructure_connections")
            cid = r.get("Corridor ID","")
            if cid:
                add(cid, r.get("Source Asset ID",""), "includes / serves", "Corridors", "infrastructure_connections")
                add(cid, r.get("Target Entity / Asset ID",""), "includes / serves", "Corridors", "infrastructure_connections")

    al = D.get("aircraft_relationships", pd.DataFrame())
    if not al.empty:
        # Aircraft relationship schemas vary; resolve common identifiers conservatively.
        for _, r in al.iterrows():
            aid = _first_existing(r, ["Aircraft ID","Registration","Aircraft Registry ID"], "")
            cid = _first_existing(r, ["Company ID","Operator Company ID","Network Customer Company ID"], "")
            add(cid, aid, _first_existing(r,["Relationship Type","Relationship"],"aircraft relationship"), "Aviation", "aircraft_relationships")

    df = pd.DataFrame(edges)
    if df.empty:
        return df
    return df.drop_duplicates(subset=["source","target","relationship","category"]).reset_index(drop=True)

ENTITY_INDEX = build_entity_index()
GRAPH_EDGES = build_graph_edges()

def entity_label(entity_id):
    meta = ENTITY_INDEX.get(str(entity_id), {})
    return meta.get("label", str(entity_id))

def entity_type(entity_id):
    return ENTITY_INDEX.get(str(entity_id), {}).get("type", "Entity")

def graph_subgraph(root_id, depth=1, categories=None, max_nodes=60):
    if GRAPH_EDGES.empty or not root_id:
        return pd.DataFrame(), set()
    allowed = set(categories or GRAPH_EDGES["category"].unique().tolist())
    edges = GRAPH_EDGES[GRAPH_EDGES["category"].isin(allowed)].copy()
    visited = {str(root_id)}
    frontier = {str(root_id)}
    selected = []
    for _ in range(max(1, int(depth))):
        if not frontier or len(visited) >= max_nodes:
            break
        hit = edges[edges["source"].isin(frontier) | edges["target"].isin(frontier)]
        if hit.empty:
            break
        selected.append(hit)
        neighbors = set(hit["source"]).union(set(hit["target"])) - visited
        room = max_nodes - len(visited)
        neighbors = set(list(sorted(neighbors))[:max(0, room)])
        visited |= neighbors
        frontier = neighbors
    out = pd.concat(selected, ignore_index=True).drop_duplicates() if selected else pd.DataFrame(columns=GRAPH_EDGES.columns)
    out = out[out["source"].isin(visited) & out["target"].isin(visited)]
    return out, visited

def dot_escape(value):
    return str(value).replace("\\", "\\\\").replace('"','\\"').replace("\n", " ")

def graph_dot(edges, root_id=None, title="Relationship graph"):
    if edges.empty:
        return ""
    nodes = sorted(set(edges["source"]).union(set(edges["target"])))
    type_style = {
        "Company": ("box", "#18314f"),
        "Port": ("component", "#17433b"),
        "Terminal": ("folder", "#234b3d"),
        "Vessel": ("ellipse", "#243b63"),
        "Rail Network": ("hexagon", "#4a3920"),
        "Rail Node": ("diamond", "#4a3920"),
        "Corridor": ("octagon", "#4a2d46"),
        "Asset": ("box3d", "#374151"),
        "Entity": ("box", "#374151"),
    }
    lines = [
        "digraph G {",
        'graph [bgcolor="transparent", rankdir="LR", pad="0.35", nodesep="0.45", ranksep="0.75", splines="spline", overlap="false"];',
        'node [fontname="Arial", fontsize="10", fontcolor="#eef4fb", style="rounded,filled", color="#57708d", penwidth="1.1", margin="0.12,0.08"];',
        'edge [fontname="Arial", fontsize="8", fontcolor="#aebed0", color="#70859c", arrowsize="0.65", penwidth="1.0"];',
    ]
    for nid in nodes:
        typ = entity_type(nid)
        shape, fill = type_style.get(typ, type_style["Entity"])
        label = entity_label(nid)
        if len(label) > 42:
            label = label[:39] + "…"
        pen = "2.3" if str(nid) == str(root_id) else "1.1"
        color = "#c8a45b" if str(nid) == str(root_id) else "#57708d"
        lines.append(f'"{dot_escape(nid)}" [label="{dot_escape(label)}", shape="{shape}", fillcolor="{fill}", color="{color}", penwidth="{pen}"];')
    for _, r in edges.iterrows():
        rel = str(r.get("relationship","related to")).replace("_"," ").lower()
        if len(rel) > 28:
            rel = rel[:25] + "…"
        lines.append(f'"{dot_escape(r["source"])}" -> "{dot_escape(r["target"])}" [label="{dot_escape(rel)}"];')
    lines.append("}")
    return "\n".join(lines)

def render_relationship_graph(root_id, key_prefix="graph", default_depth=1, max_nodes_default=55):
    if not root_id:
        st.info("No canonical entity ID is available for this record.")
        return
    cats = sorted(GRAPH_EDGES["category"].unique().tolist()) if not GRAPH_EDGES.empty else []
    a,b,c = st.columns([2,1,1])
    with a:
        selected_cats = st.multiselect("Relationship layers", cats, default=cats, key=f"{key_prefix}_cats")
    with b:
        depth = st.selectbox("Graph depth", [1,2,3], index=max(0,default_depth-1), key=f"{key_prefix}_depth")
    with c:
        max_nodes = st.selectbox("Max nodes", [25,40,55,75,100], index=[25,40,55,75,100].index(max_nodes_default) if max_nodes_default in [25,40,55,75,100] else 2, key=f"{key_prefix}_max")
    edges, nodes = graph_subgraph(root_id, depth=depth, categories=selected_cats, max_nodes=max_nodes)
    if edges.empty:
        st.info("No graph relationships are currently linked to this entity.")
        return
    st.caption(f"{len(nodes)} nodes • {len(edges)} relationship edges • centred on {entity_label(root_id)}")
    st.graphviz_chart(graph_dot(edges, root_id), use_container_width=True)
    with st.expander("Relationship evidence"):
        evidence = edges.copy()
        evidence.insert(0,"Source Name", evidence["source"].map(entity_label))
        evidence.insert(2,"Target Name", evidence["target"].map(entity_label))
        safe_display(evidence, 300)

def watch_area_bundle(corridor_id):
    corridors = D.get("corridors", pd.DataFrame())
    if corridors.empty or "Corridor ID" not in corridors.columns:
        return {}, pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    hit = corridors[corridors["Corridor ID"] == corridor_id]
    if hit.empty:
        return {}, pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    row = hit.iloc[0].to_dict()
    name = str(row.get("Corridor", ""))
    geo = str(row.get("Country / Region", ""))
    # For a country-defined chokepoint, use canonical Country columns to avoid substring errors (e.g. Panama vs Panamax).
    ports = D.get("ports", pd.DataFrame()).copy()
    if not ports.empty and geo and "Country" in ports.columns and "/" not in geo:
        country_terms = [x.strip() for x in re.split(r"[,;]", geo) if x.strip()]
        pmask = pd.Series(False, index=ports.index)
        for term in country_terms:
            pmask |= ports["Country"].str.fullmatch(re.escape(term), case=False, na=False)
        p_hits = ports[pmask]
    else:
        p_hits = text_search(ports, name) if not ports.empty else pd.DataFrame()
    terminals = D.get("terminals", pd.DataFrame())
    t_hits = pd.DataFrame()
    if not p_hits.empty and not terminals.empty and "Port ID" in p_hits.columns and "Port ID" in terminals.columns:
        t_hits = terminals[terminals["Port ID"].isin(p_hits["Port ID"].tolist())]
    connections = D.get("connections", pd.DataFrame())
    c_hits = connections[connections.get("Corridor ID", pd.Series(dtype=str)) == corridor_id] if not connections.empty and "Corridor ID" in connections.columns else pd.DataFrame()
    # Event/news evidence uses corridor name plus geography; this is intentionally evidence-bound.
    events = D.get("event_observations", pd.DataFrame())
    news = D.get("news", pd.DataFrame())
    e_hits = text_search(events, name) if not events.empty else pd.DataFrame()
    n_hits = text_search(news, name) if not news.empty else pd.DataFrame()
    if geo:
        if e_hits.empty and not events.empty: e_hits = text_search(events, geo)
        if n_hits.empty and not news.empty: n_hits = text_search(news, geo)
    return row, p_hits, t_hits, c_hits, pd.concat([e_hits.assign(_kind="Event"), n_hits.assign(_kind="News")], ignore_index=True, sort=False)

# ---------- Sidebar ----------
st.sidebar.markdown("### P&C Trade System")
st.sidebar.caption("Intelligence Model v1.17 • App v1.21")
st.sidebar.markdown("<div style=\"color:#d7b66a;font-weight:700;font-size:.78rem;letter-spacing:.08em;margin:.15rem 0 .8rem;\">APP BUILD v1.21</div>", unsafe_allow_html=True)
page = st.sidebar.radio(
    "Navigate",
    [
        "Operating Picture",
        "Companies",
        "Ports & Terminals",
        "Vessels",
        "Air Cargo",
        "News & Events",
        "Monitoring",
        "Transactions & Projects",
        "Infrastructure",
        "Rail Networks",
        "Ferry Systems",
        "Great Lakes",
        "Entity Explorer",
        "Watch Areas",
        "Ask P&C",
    ],
)
st.sidebar.markdown("---")
st.sidebar.caption("Trade infrastructure • fleets • rail • corridors • entity graphs • watch areas • intelligence")

# ---------- Pages ----------
if page == "Operating Picture":
    page_header("Operating Picture", "A cross-domain view of companies, assets, ports, fleets, events and developing situations.")
    vals = [
        ("Companies", len(D["companies"]), "canonical organizations"),
        ("Ports", len(D["ports"]), "canonical port/facility records"),
        ("Vessels", len(D["vessels"]), "canonical vessel records"),
        ("Aircraft", len(D["aircraft"]), "registration-level identities"),
        ("Rail", len(D["rail_networks"]), "canonical networks / corridors"),
        ("News", len(D["news"]), "entity-linked current stories"),
        ("Monitoring", len(D["monitoring"]), "active analytical watches"),
    ]
    # Two rows stay readable on normal laptop widths; seven equal columns forced labels to wrap vertically.
    for row_vals in (vals[:4], vals[4:]):
        c = st.columns(len(row_vals))
        for x,(label,val,note) in zip(c, row_vals):
            with x:
                metric_card(label, f"{val:,}", note)

    st.markdown("### Latest news")
    news = D["news"].copy()
    dc = col(news, ["Published Date","Date"])
    if dc:
        news = news.sort_values(dc, ascending=False)
    safe_display(news.head(12), max_rows=12)

    a,b = st.columns(2)
    with a:
        st.markdown("### Latest event observations")
        eo = D["event_observations"].copy()
        dc = col(eo, ["Date"])
        if dc:
            eo = eo.sort_values(dc, ascending=False)
        safe_display(eo.head(12), max_rows=12)
    with b:
        st.markdown("### Active monitoring")
        safe_display(D["monitoring"], max_rows=20)

elif page == "Companies":
    page_header("Companies", "Corporate ecosystems, ownership, assets, fleets, transactions and related reporting.")
    df = D["companies"]
    if df.empty:
        st.warning("companies.csv is missing.")
        st.stop()
    namec = col(df, ["Company","Company Name"])
    options = sorted([x for x in df[namec].unique() if x]) if namec else []
    selected = st.selectbox("Company", options)
    row = df[df[namec] == selected].iloc[0]
    cid = row.get("Company ID","")

    render_pairs(profile_pairs(row, [
        ("Entity type","Entity Type"),("HQ","HQ City"),("Country","HQ Country"),
        ("Ownership","Ownership"),("Business segments","Business Segments"),
        ("Senior leader","Senior Leader"),("Title","Title"),("Status","Status"),
        ("Scale / network","Scale / Network Notes"),
    ]), 3)

    tabs = st.tabs(["Relationship Graph","Relationships","Assets","Fleet","Transactions","Events","News"])
    with tabs[0]:
        render_relationship_graph(cid, key_prefix=f"company_{cid}", default_depth=2, max_nodes_default=55)
    with tabs[1]:
        rel = D["relationships"]
        if not rel.empty:
            mask = (rel.get("Source Entity","") == cid) | (rel.get("Target Entity","") == cid)
            safe_display(rel[mask])
        else: st.info("No relationship table.")
    with tabs[2]:
        assets = D["assets"]
        safe_display(assets[assets.get("Company ID","") == cid] if not assets.empty else assets)
        ptc = D["terminals"]
        if not ptc.empty and "Primary Operator Company ID" in ptc.columns:
            linked_t = ptc[ptc["Primary Operator Company ID"].astype(str) == cid]
            if not linked_t.empty:
                st.markdown("#### Port / terminal assets")
                safe_display(linked_t)
        ftc = D["ferry_terminals"]
        if not ftc.empty and "Operator Company ID" in ftc.columns:
            linked_ft = ftc[ftc["Operator Company ID"].astype(str) == cid]
            if not linked_ft.empty:
                st.markdown("#### Ferry terminals")
                safe_display(linked_ft)
        rr = D["rail_relationships"]
        rn = D["rail_networks"]
        if not rr.empty and "Company ID" in rr.columns and "Rail Network ID" in rr.columns:
            rids = rr[rr["Company ID"].astype(str) == cid]["Rail Network ID"].dropna().astype(str).unique().tolist()
            linked_rn = rn[rn["Rail Network ID"].isin(rids)] if not rn.empty and "Rail Network ID" in rn.columns else pd.DataFrame()
            if not linked_rn.empty:
                st.markdown("#### Rail networks / corridors")
                safe_display(linked_rn)
        rnodes = D["rail_nodes"]
        if not rnodes.empty and "Primary Company ID" in rnodes.columns:
            linked_nodes = rnodes[rnodes["Primary Company ID"].astype(str) == cid]
            if not linked_nodes.empty:
                st.markdown("#### Rail terminals / nodes")
                safe_display(linked_nodes)
    with tabs[3]:
        vessel_rel = D["vessel_relationships"]
        vessels = D["vessels"]
        direct = vessels[
            (vessels.get("Owner Company ID","") == cid) |
            (vessels.get("Operator Company ID","") == cid)
        ] if not vessels.empty else vessels
        if not vessel_rel.empty and "Company ID" in vessel_rel.columns and "Vessel ID" in vessel_rel.columns:
            ids = vessel_rel[vessel_rel["Company ID"] == cid]["Vessel ID"].unique().tolist()
            extra = vessels[vessels["Vessel ID"].isin(ids)] if not vessels.empty and "Vessel ID" in vessels.columns else pd.DataFrame()
            direct = pd.concat([direct, extra]).drop_duplicates(subset=["Vessel ID"]) if not extra.empty else direct
        safe_display(direct)
        # Canonical aircraft linked by operator or network customer
        ac = D["aircraft"]
        if not ac.empty:
            amask = pd.Series(False, index=ac.index)
            for cc in ["Operator Company ID","Network Customer Company ID"]:
                if cc in ac.columns:
                    amask = amask | (ac[cc].astype(str) == cid)
            av = ac[amask]
            if not av.empty:
                st.markdown("#### Individual aircraft")
                safe_display(av)
        # Ferry-system overlay stays visible, but vessels remain canonical Vessels above
        fs = D["ferry_systems"]
        if not fs.empty and "Operator Company ID" in fs.columns:
            fsv = fs[fs["Operator Company ID"].astype(str) == cid]
            if not fsv.empty:
                st.markdown("#### Ferry systems")
                safe_display(fsv)
        rf = D["rail_fleet"]
        if not rf.empty and "Company ID" in rf.columns:
            rv = rf[rf["Company ID"].astype(str) == cid]
            if not rv.empty:
                st.markdown("#### Rail fleet / rolling stock")
                safe_display(rv)
    with tabs[4]:
        deals = D["infra_deals"]
        tl = D["transaction_links"]
        if not deals.empty:
            mask = deals.astype(str).apply(lambda s: s.str.contains(re.escape(cid), case=False, na=False)).any(axis=1)
            linked_deals = deals[mask]
            if not tl.empty and "Entity / Asset ID" in tl.columns and "Deal ID" in tl.columns and "Deal ID" in deals.columns:
                d_ids = tl[tl["Entity / Asset ID"] == cid]["Deal ID"].unique().tolist()
                linked_deals = pd.concat([linked_deals, deals[deals["Deal ID"].isin(d_ids)]]).drop_duplicates()
            safe_display(linked_deals)
    with tabs[5]:
        safe_display(entity_events(cid))
    with tabs[6]:
        safe_display(entity_news(cid))

elif page == "Ports & Terminals":
    page_header("Ports & Terminals", "Canonical port profiles with terminals, berths, equipment, ownership, projects, incidents and news.")
    ports = D["ports"]
    namec = col(ports, ["Port / Facility","Port"])
    pview = ports.copy()
    terminals_all = D["terminals"]
    # Filter from the canonical terminal layer so shared ports and operator networks resolve correctly.
    if not terminals_all.empty and "Primary Operator" in terminals_all.columns:
        opvals = sorted([x for x in terminals_all["Primary Operator"].dropna().astype(str).unique() if x.strip()])
        opopts = ["All operators"] + opvals
        opick = st.selectbox("Operator / network", opopts)
        if opick != "All operators":
            tids = terminals_all[terminals_all["Primary Operator"].astype(str) == opick]["Port ID"].dropna().astype(str).unique().tolist()
            if "Port ID" in pview.columns:
                pview = pview[pview["Port ID"].astype(str).isin(tids)]
    coverage = D.get("port_operator_coverage", pd.DataFrame())
    if not coverage.empty:
        with st.expander("Operator network coverage"):
            safe_display(coverage)
    options = sorted([x for x in pview[namec].unique() if x]) if not pview.empty and namec else []
    selected = st.selectbox("Port", options)
    row = pview[pview[namec] == selected].iloc[0]
    pid = row.get("Port ID","")

    render_pairs(profile_pairs(row, [
        ("Country","Country"),("Facility type","Facility Type"),("Operator","Operator"),
        ("Key role","Key Role"),("Coverage","Coverage Note"),
    ]), 3)
    with st.expander("System relationship graph", expanded=False):
        render_relationship_graph(pid, key_prefix=f"port_{pid}", default_depth=2, max_nodes_default=40)

    tabs = st.tabs(["Terminals","Berths & Equipment","Ownership","Rail","Projects & Constraints","Events","News"])
    terminals = D["terminals"]
    pt = terminals[terminals.get("Port ID","") == pid] if not terminals.empty else terminals
    with tabs[0]:
        safe_display(pt)
    with tabs[1]:
        if pt.empty or "Terminal ID" not in pt.columns:
            st.info("No terminal detail.")
        else:
            tids = pt["Terminal ID"].tolist()
            a,b = st.columns(2)
            with a:
                st.markdown("#### Berths")
                safe_display(D["berths"][D["berths"].get("Terminal ID","").isin(tids)] if not D["berths"].empty else D["berths"])
            with b:
                st.markdown("#### Equipment")
                safe_display(D["equipment"][D["equipment"].get("Terminal ID","").isin(tids)] if not D["equipment"].empty else D["equipment"])
    with tabs[2]:
        if pt.empty or "Terminal ID" not in pt.columns:
            st.info("No terminal ownership detail.")
        else:
            tids = pt["Terminal ID"].tolist()
            own = D["ownership"]
            safe_display(own[own.get("Terminal ID","").isin(tids)] if not own.empty else own)
    with tabs[3]:
        rc = D["rail_connections"]
        rn = D["rail_nodes"]
        phits = rc[rc["Connected Entity ID"].astype(str) == pid] if not rc.empty and "Connected Entity ID" in rc.columns else pd.DataFrame()
        if not pt.empty and "Terminal ID" in pt.columns and not rc.empty and "Connected Entity ID" in rc.columns:
            thits = rc[rc["Connected Entity ID"].astype(str).isin(pt["Terminal ID"].astype(str).tolist())]
            phits = pd.concat([phits, thits]).drop_duplicates() if not thits.empty else phits
        if phits.empty:
            st.info("No canonical rail connection captured for this port yet.")
        else:
            safe_display(phits)
            if "Rail Node ID" in phits.columns and not rn.empty:
                nids=phits["Rail Node ID"].dropna().astype(str).unique().tolist()
                linked_nodes=rn[rn["Rail Node ID"].isin(nids)] if "Rail Node ID" in rn.columns else pd.DataFrame()
                if not linked_nodes.empty:
                    st.markdown("#### Connected rail nodes")
                    safe_display(linked_nodes)
    with tabs[4]:
        works = D["infra_works"]
        hits = text_search(works, selected)
        safe_display(hits)
        cons = D["asset_constraints"]
        c_hits = text_search(cons, selected)
        if not c_hits.empty:
            st.markdown("#### Asset constraints")
            safe_display(c_hits)
    with tabs[5]:
        safe_display(entity_events(pid))
    with tabs[6]:
        n1 = entity_news(pid)
        # add terminal-linked news too
        if not pt.empty and "Terminal ID" in pt.columns and not D["port_news"].empty:
            pn = D["port_news"]
            pn = pn[pn.get("Terminal ID","").isin(pt["Terminal ID"].tolist())]
        else:
            pn = pd.DataFrame()
        if not n1.empty:
            safe_display(n1)
        if not pn.empty:
            st.markdown("#### Terminal-linked developments")
            safe_display(pn)

elif page == "Vessels":
    page_header("Vessels", "Individual vessels with IMO, ownership/operator relationships, incidents and linked reporting.")
    df = D["vessels"]
    q = st.text_input("Search vessel name or IMO")
    view = text_search(df, q) if q else df
    if view.empty:
        st.info("No vessel match.")
    else:
        namec = col(view, ["Vessel Name"])
        labels = []
        for _,r in view.head(500).iterrows():
            imo = r.get("IMO","")
            labels.append(f"{r.get(namec,'')} — IMO {imo}" if imo else r.get(namec,""))
        pick = st.selectbox("Vessel", labels)
        idx = labels.index(pick)
        row = view.head(500).iloc[idx]
        vid = row.get("Vessel ID","")
        render_pairs(profile_pairs(row, [
            ("IMO","IMO"),("Type","Vessel Type"),("Subtype / class","Subtype / Class"),
            ("Flag","Flag"),("Built","Year Built"),("DWT","DWT"),("Capacity","Capacity"),
            ("Primary service","Primary Service"),("Status","Status"),
            ("Registered owner","Registered Owner (Legal)"),("Manager","Technical / ISM Manager"),
        ]), 3)
        with st.expander("Ownership / operating network", expanded=False):
            render_relationship_graph(vid, key_prefix=f"vessel_{vid}", default_depth=2, max_nodes_default=40)
        tabs = st.tabs(["Relationships","Events","News"])
        with tabs[0]:
            vr = D["vessel_relationships"]
            safe_display(vr[vr.get("Vessel ID","") == vid] if not vr.empty else vr)
        with tabs[1]:
            safe_display(entity_events(vid))
        with tabs[2]:
            safe_display(entity_news(vid))

elif page == "Air Cargo":
    page_header("Air Cargo", "Registration-level aircraft identities, operator/network relationships and portfolio coverage.")
    a,b,c = st.columns(3)
    with a: metric_card("Aircraft identities", f"{len(D['aircraft']):,}", "physical aircraft rows")
    with b: metric_card("Relationship edges", f"{len(D['aircraft_relationships']):,}", "operator / network / ownership links")
    with c: metric_card("Portfolio programs", f"{len(D['aviation_summary']):,}", "official fleet denominator snapshots")
    q = st.text_input("Search airline, registration, MSN or aircraft type")
    safe_display(text_search(D["aircraft"], q) if q else D["aviation_summary"], 300)

elif page == "News & Events":
    page_header("News & Events", "Reporting is kept separate from the underlying canonical event, then linked back to affected entities.")
    tab1,tab2 = st.tabs(["News","Canonical / observed events"])
    with tab1:
        n = D["news"].copy()
        c1,c2 = st.columns(2)
        with c1:
            q = st.text_input("Search news", key="newsq")
        with c2:
            event_type = st.selectbox("Event type", ["All"] + sorted([x for x in n.get("Event Type",pd.Series(dtype=str)).unique() if x]))
        if q:
            n = text_search(n,q)
        if event_type != "All" and "Event Type" in n.columns:
            n = n[n["Event Type"] == event_type]
        dc = col(n,["Published Date","Date"])
        if dc: n = n.sort_values(dc, ascending=False)
        safe_display(n,500)
    with tab2:
        eo = D["event_observations"].copy()
        q2 = st.text_input("Search event observations", key="eventq")
        if q2: eo = text_search(eo,q2)
        dc = col(eo,["Date"])
        if dc: eo = eo.sort_values(dc, ascending=False)
        safe_display(eo,500)

elif page == "Monitoring":
    page_header("Monitoring", "Active watch objects aggregate developing events, indicators, thresholds and next milestones.")
    m = D["monitoring"].copy()
    if m.empty:
        st.info("No monitoring records.")
    else:
        titles = m.get("Title", pd.Series(dtype=str)).tolist()
        sel = st.selectbox("Monitoring topic", titles)
        row = m[m["Title"] == sel].iloc[0]
        render_pairs(profile_pairs(row, [
            ("Family","Family"),("Geography","Geography"),("Status","Status"),
            ("Time horizon","Time Horizon"),("Confidence","Confidence"),
            ("Last reviewed","Last Reviewed"),("Next milestone","Next Review / Milestone"),
        ]),3)
        st.markdown("#### What is being monitored")
        st.write(row.get("What Is Being Monitored",""))
        st.markdown("#### Key indicators")
        st.write(row.get("Key Indicators",""))
        st.markdown("#### Trigger / threshold")
        st.write(row.get("Trigger / Threshold",""))
        mid = row.get("Monitoring ID","")
        ml = D["monitoring_links"]
        events = D["events"]
        if not ml.empty and "Monitoring ID" in ml.columns and "Canonical Event ID" in ml.columns and "Event ID" in events.columns:
            eids = ml[ml["Monitoring ID"] == mid]["Canonical Event ID"].tolist()
            linked = events[events["Event ID"].isin(eids)]
            if not linked.empty:
                st.markdown("#### Linked canonical events")
                safe_display(linked)

elif page == "Transactions & Projects":
    page_header("Transactions & Projects", "M&A, strategic bids, port/terminal investment and the physical assets affected.")
    t1,t2 = st.tabs(["Transactions","Projects / works"])
    with t1:
        deals = D["infra_deals"].copy()
        q = st.text_input("Search transactions", key="dealq")
        if q: deals = text_search(deals,q)
        safe_display(deals,500)
    with t2:
        works = D["infra_works"].copy()
        q = st.text_input("Search projects", key="workq")
        if q: works = text_search(works,q)
        safe_display(works,500)

elif page == "Infrastructure":
    page_header("Infrastructure", "Ports, rail, dry ports, economic zones, logistics real estate, shipyards and system connections.")
    tabs = st.tabs(["Assets","Shipyards","Connections","Investors / holdings","Control & constraints"])
    with tabs[0]:
        q=st.text_input("Search infrastructure assets",key="assetq")
        safe_display(text_search(D["assets"],q) if q else D["assets"],500)
    with tabs[1]:
        safe_display(D["shipyards"],500)
    with tabs[2]:
        safe_display(D["connections"],500)
    with tabs[3]:
        safe_display(D["infra_investors"],300)
        if not D["infra_holdings"].empty:
            st.markdown("#### Holdings")
            safe_display(D["infra_holdings"],500)
    with tabs[4]:
        a,b=st.columns(2)
        with a:
            st.markdown("#### Asset control history")
            safe_display(D["asset_control"])
        with b:
            st.markdown("#### Asset constraints")
            safe_display(D["asset_constraints"])

elif page == "Rail Networks":
    page_header("Rail Networks", "Companies, corridors, origin/destination nodes, port and dry-port connections, rolling stock and rail developments.")
    a,b,c,d = st.columns(4)
    with a: metric_card("Rail operators", f"{len(D['rail_operators']):,}", "company-linked operators / authorities")
    with b: metric_card("Networks", f"{len(D['rail_networks']):,}", "named corridors / systems")
    with c: metric_card("Physical nodes", f"{len(D['rail_nodes']):,}", "ports, dry ports, borders, hubs")
    with d: metric_card("Movement links", f"{len(D['rail_links']):,}", "origin → destination edges")
    if not D["rail_networks"].empty and "Rail Network ID" in D["rail_networks"].columns:
        rn_name = col(D["rail_networks"], ["Network / Corridor","Rail Network / Corridor","Rail Network","Name"])
        if rn_name:
            with st.expander("Rail network relationship graph", expanded=False):
                rlabels = {f"{r[rn_name]} — {r['Rail Network ID']}":r['Rail Network ID'] for _,r in D["rail_networks"].iterrows()}
                rpick = st.selectbox("Network / corridor", sorted(rlabels.keys()), key="rail_graph_pick")
                render_relationship_graph(rlabels[rpick], key_prefix=f"rail_{rlabels[rpick]}", default_depth=2, max_nodes_default=55)
    tabs=st.tabs(["Networks","Nodes","Links","Operators","Fleet","Port / asset connections","News"])
    with tabs[0]:
        q=st.text_input("Search rail network / corridor",key="railnetq")
        safe_display(text_search(D["rail_networks"],q) if q else D["rail_networks"],500)
    with tabs[1]:
        q=st.text_input("Search rail node / terminal / port",key="railnodeq")
        safe_display(text_search(D["rail_nodes"],q) if q else D["rail_nodes"],500)
    with tabs[2]:
        q=st.text_input("Search origin, destination or corridor",key="raillinkq")
        safe_display(text_search(D["rail_links"],q) if q else D["rail_links"],500)
    with tabs[3]:
        safe_display(D["rail_operators"],300)
        st.markdown("#### Network ownership / operating relationships")
        safe_display(D["rail_relationships"],500)
    with tabs[4]:
        safe_display(D["rail_fleet"],300)
    with tabs[5]:
        safe_display(D["rail_connections"],500)
    with tabs[6]:
        rn=D["rail_news"].copy()
        if not rn.empty and "Date" in rn.columns: rn=rn.sort_values("Date",ascending=False)
        safe_display(rn,300)

elif page == "Ferry Systems":
    page_header("Ferry Systems", "Systems, routes, terminals, fleet status and service-performance observations.")
    tabs=st.tabs(["Systems","Routes","Terminals","Fleet status","Performance"])
    with tabs[0]: safe_display(D["ferry_systems"],200)
    with tabs[1]: safe_display(D["ferry_routes"],500)
    with tabs[2]: safe_display(D["ferry_terminals"],500)
    with tabs[3]: safe_display(D["ferry_status"],300)
    with tabs[4]: safe_display(D["ferry_performance"],300)

elif page == "Great Lakes":
    page_header("Great Lakes", "Ports, vessel staging, cargo corridors, cruise and disruption coverage.")
    tabs=st.tabs(["Ports","Vessels","Cargo corridors","Cruise","Disruptions"])
    with tabs[0]: safe_display(D["great_lakes_ports"],300)
    with tabs[1]: safe_display(D["great_lakes_vessels"],300)
    with tabs[2]: safe_display(D["great_lakes_corridors"],300)
    with tabs[3]: safe_display(D["great_lakes_cruise"],300)
    with tabs[4]: safe_display(D["great_lakes_disruptions"],300)

elif page == "Entity Explorer":
    page_header("Entity Explorer", "Visualize corporate, asset, fleet, port, rail and corridor relationships from the canonical model.")
    if not ENTITY_INDEX:
        st.info("No canonical entity registry is available.")
    else:
        type_options = sorted(set(v.get("type","Entity") for v in ENTITY_INDEX.values()))
        c1,c2 = st.columns([1,2])
        with c1:
            typ = st.selectbox("Entity type", ["All"] + type_options)
        candidates = [(eid,meta) for eid,meta in ENTITY_INDEX.items() if typ == "All" or meta.get("type") == typ]
        labels = {f'{meta.get("label",eid)} [{meta.get("type","Entity")}] — {eid}':eid for eid,meta in candidates}
        with c2:
            query = st.text_input("Filter entities", placeholder="e.g. MSC, Tbilisi, Panama Canal, Etihad Rail")
        if query:
            ql=query.lower()
            labels={k:v for k,v in labels.items() if ql in k.lower()}
        if not labels:
            st.info("No matching canonical entity.")
        else:
            pick = st.selectbox("Focus entity", sorted(labels.keys()))
            root = labels[pick]
            meta = ENTITY_INDEX.get(root,{})
            render_pairs([
                ("Canonical entity", meta.get("label",root)),
                ("Entity type", meta.get("type","Entity")),
                ("Country / geography", meta.get("country","")),
                ("Canonical ID", root),
            ], 4)
            st.markdown("### Relationship graph")
            render_relationship_graph(root, key_prefix=f"entity_{root}", default_depth=2, max_nodes_default=55)
            a,b = st.columns(2)
            with a:
                st.markdown("### Linked events")
                safe_display(entity_events(root), 100)
            with b:
                st.markdown("### Linked news")
                safe_display(entity_news(root), 100)

elif page == "Watch Areas":
    page_header("Watch Areas", "Operational watch zones combine chokepoints, gateway ports, terminals, companies, corridors and current intelligence evidence.")
    corridors = D.get("corridors", pd.DataFrame())
    if corridors.empty:
        st.info("No corridor registry is available.")
    else:
        namec = col(corridors,["Corridor"])
        options = sorted([x for x in corridors[namec].unique() if x]) if namec else []
        chosen = st.selectbox("Watch area / corridor", options)
        crow = corridors[corridors[namec] == chosen].iloc[0]
        cid = crow.get("Corridor ID","")
        row, ports_w, terms_w, connections_w, evidence_w = watch_area_bundle(cid)
        render_pairs([
            ("Type", row.get("Type","")),
            ("Geography", row.get("Country / Region","")),
            ("Connects", row.get("Connects","")),
            ("Primary traffic", row.get("Primary Traffic","")),
            ("Status", row.get("Status","")),
            ("Strategic note", row.get("Strategic Note","")),
        ], 3)
        # Build a watch-area graph from the corridor plus discovered gateway assets.
        watch_edges = []
        if cid:
            if not ports_w.empty and "Port ID" in ports_w.columns:
                for _,r in ports_w.iterrows():
                    watch_edges.append({"source":cid,"target":r.get("Port ID",""),"relationship":"gateway / watch-area port","category":"Watch Area","source_table":"ports"})
            if not terms_w.empty:
                for _,r in terms_w.iterrows():
                    watch_edges.append({"source":r.get("Port ID",""),"target":r.get("Terminal ID",""),"relationship":"contains","category":"Watch Area","source_table":"port_terminals"})
                    if r.get("Primary Operator Company ID",""):
                        watch_edges.append({"source":r.get("Primary Operator Company ID",""),"target":r.get("Terminal ID",""),"relationship":"operates","category":"Watch Area","source_table":"port_terminals"})
            if not connections_w.empty:
                for _,r in connections_w.iterrows():
                    if r.get("Source Asset ID","") and r.get("Target Entity / Asset ID",""):
                        watch_edges.append({"source":r.get("Source Asset ID",""),"target":r.get("Target Entity / Asset ID",""),"relationship":r.get("Relationship","connected to"),"category":"Watch Area","source_table":"infrastructure_connections"})
        wedge = pd.DataFrame(watch_edges)
        tabs = st.tabs(["System View","Gateway Ports & Terminals","Connections","Intelligence Evidence","What to Monitor"])
        with tabs[0]:
            if wedge.empty:
                # Fall back to canonical graph relationships around the corridor.
                gedges,_ = graph_subgraph(cid, depth=2, categories=None, max_nodes=55)
                wedge = gedges
            if wedge.empty:
                st.info("The watch area exists in the corridor registry, but its asset links have not yet been fully populated.")
            else:
                st.graphviz_chart(graph_dot(wedge, cid), use_container_width=True)
                st.caption("The system view is assembled from canonical corridor, port, terminal, company and infrastructure relationships already in the model.")
        with tabs[1]:
            st.markdown("#### Gateway ports")
            safe_display(ports_w, 200)
            st.markdown("#### Terminals")
            safe_display(terms_w, 300)
        with tabs[2]:
            safe_display(connections_w, 300)
        with tabs[3]:
            if evidence_w.empty:
                st.info("No corridor-specific event/news evidence is currently linked or text-matched in the local model.")
            else:
                safe_display(evidence_w, 300)
        with tabs[4]:
            st.markdown("""
            **Operational indicators:** chokepoint restrictions, draft/slot changes, closures, congestion, queues, lock/bridge outages and navigation warnings.  
            **Gateway indicators:** berth/crane outages, terminal congestion, labour action, customs delays, landside access and intermodal disruption.  
            **Security indicators:** attacks, sabotage, cyber events, protests, sanctions/enforcement activity and military restrictions.  
            **Network indicators:** rail/road outages, alternate-gateway use, rerouting, carrier schedule changes and material changes in tradeability.
            """)

elif page == "Ask P&C":
    page_header("Ask P&C", "Local evidence search across the normalized model. It works without an external AI API.")
    q = st.text_input("Ask or search", placeholder="e.g. Yemen ports tanker enforcement, ICTSI TLG, Oakland turning basin")
    if q:
        search_tables = {
            "Companies":D["companies"],"Ports":D["ports"],"Terminals":D["terminals"],
            "Vessels":D["vessels"],"Aircraft":D["aircraft"],"News":D["news"],
            "Events":D["event_observations"],"Monitoring":D["monitoring"],
            "Transactions":D["infra_deals"],"Projects":D["infra_works"],
            "Assets":D["assets"],"Shipyards":D["shipyards"],
            "Rail networks":D["rail_networks"],"Rail nodes":D["rail_nodes"],"Rail links":D["rail_links"],"Rail news":D["rail_news"],
        }
        total=0
        for title,df in search_tables.items():
            hits=text_search(df,q)
            if not hits.empty:
                total += len(hits)
                with st.expander(f"{title} — {len(hits)} match(es)", expanded=(title in {"News","Events","Companies","Ports","Vessels"})):
                    safe_display(hits,100)
        if total==0:
            # Token fallback for natural-language queries.
            tokens=[t for t in re.findall(r"[A-Za-z0-9\-]+",q) if len(t)>3]
            for title,df in search_tables.items():
                if df.empty: continue
                mask=pd.Series(False,index=df.index)
                for tok in tokens:
                    mask |= df.astype(str).apply(lambda s:s.str.contains(re.escape(tok),case=False,na=False)).any(axis=1)
                hits=df[mask]
                if not hits.empty:
                    total += len(hits)
                    with st.expander(f"{title} — {len(hits)} related match(es)"):
                        safe_display(hits,100)
        if total==0:
            st.info("No evidence match found in the current local model.")
    else:
        st.caption("This page is deliberately evidence-bound. An LLM layer can be added later without changing the underlying entity graph.")
