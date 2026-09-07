import streamlit as st
import pandas as pd
from pathlib import Path


def format_dates_for_display(df):
    """Return a display-safe copy with all known date fields formatted DD Mon YYYY."""
    out = df.copy()
    for c in (
        "Date", "date", "Source Date", "Published",
        "Departure Date", "Arrival Date",
        "2026 Event Date", "Original Contract / Decision Date",
        "Period Start", "Period End", "As Of", "Verified As Of"
    ):
        if c in out.columns:
            parsed = pd.to_datetime(out[c], errors="coerce")
            mask = parsed.notna()
            if mask.any():
                formatted = parsed.dt.strftime("%d %b %Y")
                out[c] = out[c].astype("object")
                out.loc[mask, c] = formatted.loc[mask]
    return out

import re

st.set_page_config(
    page_title="P&C Intelligence Platform",
    page_icon="◼",
    layout="wide",
    initial_sidebar_state="expanded",
)

BASE = Path(__file__).parent
DATA = BASE / "data"

# ---------------- Brand ----------------
st.markdown("""
<style>
:root {
  --pc-navy:#07111f;
  --pc-navy2:#0c1c30;
  --pc-gold:#c7a45a;
  --pc-cream:#f5f1e8;
  --pc-muted:#9ca8b7;
}
.stApp {background:#07111f; color:#eef2f6;}
[data-testid="stSidebar"] {background:#0a1727; border-right:1px solid #26364b;}
[data-testid="stSidebar"] * {color:#e8edf3;}
.pc-masthead {
  border-top:3px solid var(--pc-gold);
  border-bottom:1px solid #2a3b52;
  padding:18px 4px 16px 4px;
  margin-bottom:14px;
}
.pc-kicker {
  color:var(--pc-gold); font-size:.78rem; letter-spacing:.18em;
  font-weight:700; text-transform:uppercase;
}
.pc-title {font-size:2rem; font-weight:700; margin:.2rem 0 .1rem 0; color:#fff;}
.pc-dek {color:#aeb9c7; max-width:950px; font-size:1rem;}
.pc-card {
  background:#0c1c30; border:1px solid #26364b; border-top:2px solid var(--pc-gold);
  padding:16px 18px; border-radius:6px; min-height:115px;
}
.pc-card .label {font-size:.73rem; color:#aeb9c7; letter-spacing:.11em; text-transform:uppercase;}
.pc-card .value {font-size:1.75rem; font-weight:700; color:#fff; margin-top:6px;}
.pc-card .note {font-size:.82rem; color:#8fa0b3; margin-top:4px;}
.pc-section {
  color:#fff; border-bottom:1px solid #26364b; padding-bottom:7px; margin-top:18px;
}
.pc-badge {
  display:inline-block; padding:3px 8px; border:1px solid #40536c; border-radius:99px;
  font-size:.72rem; margin-right:5px; color:#dbe3ec;
}
a {color:#d2b66f !important;}
div[data-testid="stMetric"] {
  background:#0c1c30;
  border:1px solid #26364b;
  padding:10px 14px;
  border-radius:6px;
}

/* ---------- Streamlit native-widget contrast ---------- */

/* Metrics */
div[data-testid="stMetricLabel"],
div[data-testid="stMetricLabel"] *,
div[data-testid="stMetricValue"],
div[data-testid="stMetricValue"] * {
  opacity:1 !important;
}
div[data-testid="stMetricLabel"],
div[data-testid="stMetricLabel"] * {
  color:#cbd5df !important;
}
div[data-testid="stMetricValue"],
div[data-testid="stMetricValue"] * {
  color:#ffffff !important;
  font-weight:700 !important;
}

/* Widget labels */
div[data-testid="stWidgetLabel"],
div[data-testid="stWidgetLabel"] *,
label[data-testid="stWidgetLabel"],
label[data-testid="stWidgetLabel"] * {
  color:#d9e2ea !important;
  opacity:1 !important;
  font-weight:600 !important;
}

/* Tabs */
button[data-baseweb="tab"] {
  color:#aebbc9 !important;
  opacity:1 !important;
  font-weight:600 !important;
}
button[data-baseweb="tab"][aria-selected="true"] {
  color:#d8b86c !important;
  font-weight:700 !important;
}
button[data-baseweb="tab"] p,
button[data-baseweb="tab"] span {
  color:inherit !important;
  opacity:1 !important;
}
div[data-baseweb="tab-highlight"] {
  background-color:#c7a45a !important;
}
div[data-baseweb="tab-border"] {
  background-color:#26364b !important;
}

/* Selectbox / multiselect */
div[data-baseweb="select"] > div {
  background:#f4f7fa !important;
  border-color:#7d8b99 !important;
  color:#172437 !important;
}
div[data-baseweb="select"] span,
div[data-baseweb="select"] div,
div[data-baseweb="select"] input {
  color:#172437 !important;
  opacity:1 !important;
}
div[data-baseweb="select"] svg {
  fill:#172437 !important;
}

/* Dropdown popup options */
ul[role="listbox"],
div[role="listbox"] {
  background:#ffffff !important;
}
li[role="option"],
li[role="option"] *,
div[role="option"],
div[role="option"] * {
  color:#172437 !important;
  opacity:1 !important;
}
li[role="option"]:hover,
div[role="option"]:hover {
  background:#e8edf2 !important;
}

/* Text inputs */
div[data-testid="stTextInput"] input,
div[data-testid="stNumberInput"] input {
  background:#f4f7fa !important;
  color:#172437 !important;
  caret-color:#172437 !important;
  border-color:#7d8b99 !important;
}
div[data-testid="stTextInput"] input::placeholder,
div[data-testid="stNumberInput"] input::placeholder {
  color:#68788a !important;
  opacity:1 !important;
}

/* Buttons */
.stButton > button {
  background:#10243a !important;
  color:#f2f6f9 !important;
  border:1px solid #53667c !important;
  font-weight:650 !important;
}
.stButton > button:hover {
  border-color:#c7a45a !important;
  color:#d8b86c !important;
}
.stButton > button p,
.stButton > button span {
  color:inherit !important;
  opacity:1 !important;
}

/* Captions, helper text, markdown and alerts */
[data-testid="stCaptionContainer"],
[data-testid="stCaptionContainer"] *,
div[data-testid="stMarkdownContainer"] p,
div[data-testid="stMarkdownContainer"] li {
  color:#c7d1db;
}
div[data-testid="stAlert"] * {
  opacity:1 !important;
}

/* Dataframe / data editor wrapper */
div[data-testid="stDataFrame"],
div[data-testid="stDataEditor"] {
  border:1px solid #344861;
  border-radius:6px;
  overflow:hidden;
}

/* Sidebar radio/navigation */
[data-testid="stSidebar"] div[role="radiogroup"] label,
[data-testid="stSidebar"] div[role="radiogroup"] label * {
  color:#e8edf3 !important;
  opacity:1 !important;
}
[data-testid="stSidebar"] div[role="radiogroup"] label:hover * {
  color:#d8b86c !important;
}

/* Expander headings and generic secondary text */
details summary,
details summary * {
  color:#eef2f6 !important;
  opacity:1 !important;
}

/* Keep disabled controls legible without looking active */
button:disabled,
input:disabled,
[aria-disabled="true"] {
  opacity:.72 !important;
}
</style>
""", unsafe_allow_html=True)

def masthead(title, dek):
    st.markdown(f"""
    <div class="pc-masthead">
      <div class="pc-kicker">Power & Corridors · Intelligence</div>
      <div class="pc-title">{title}</div>
      <div class="pc-dek">{dek}</div>
    </div>
    """, unsafe_allow_html=True)

@st.cache_data(show_spinner=False)
def load(name):
    p = DATA / name
    df = pd.read_csv(p, low_memory=False, encoding="utf-8-sig")
    # Normalize headers so older snake_case datasets and newer editorial headers
    # can be used interchangeably.
    df.columns = [str(c).replace("\ufeff", "").strip() for c in df.columns]

    aliases = {
        "id": "ID",
        "date": "Date",
        "region": "Region",
        "country": "Country",
        "port_location": "Port / Location",
        "port_side_or_near_port": "Port-Side or Near-Port",
        "incident_category": "Incident Category",
        "incident_sub_type": "Incident Sub-Type",
        "conflict_related": "Conflict-Related",
        "vessel_asset": "Vessel / Asset",
        "operator_authority": "Operator / Authority",
        "event_summary": "Event Summary",
        "fatalities": "Fatalities",
        "injuries": "Injuries",
        "containers_lost_damaged": "Containers Lost / Damaged",
        "pollution_environmental_impact": "Pollution / Environmental Impact",
        "port_operational_impact": "Port / Operational Impact",
        "damage_loss_estimate": "Damage / Loss Estimate",
        "cause_attribution": "Cause / Attribution",
        "investigation_status": "Investigation / Status",
        "severity": "Severity",
        "confidence": "Confidence",
        "primary_source": "Primary Source",
        "secondary_source": "Secondary Source",
        "notes_intelligence_relevance": "Notes / Intelligence Relevance",
    }
    rename = {c: aliases[c] for c in df.columns if c in aliases}
    if rename:
        df = df.rename(columns=rename)
    return df

def sort_latest(df, preferred=("Date", "date", "Source Date", "Departure Date")):
    """Sort newest-first when a usable date column exists; otherwise return unchanged."""
    for c in preferred:
        if c in df.columns:
            tmp = df.copy()
            tmp[c] = pd.to_datetime(tmp[c], errors="coerce")
            return tmp.sort_values(c, ascending=False, na_position="last")
    return df



def dates(df, *cols):
    x = df.copy()
    for c in cols:
        if c in x.columns:
            x[c] = pd.to_datetime(x[c], errors="coerce")
    return x

def card(label, value, note=""):
    st.markdown(f'<div class="pc-card"><div class="label">{label}</div><div class="value">{value}</div><div class="note">{note}</div></div>', unsafe_allow_html=True)

def fmt_money(v):
    try:
        v=float(v)
        if v >= 1e9: return f"${v/1e9:,.1f}B"
        if v >= 1e6: return f"${v/1e6:,.0f}M"
        return f"${v:,.0f}"
    except: return "—"

def filter_select(df, col, label):
    if col not in df.columns: return df
    vals = sorted([str(v) for v in df[col].dropna().unique() if str(v).strip()])
    sel = st.multiselect(label, vals)
    if sel: return df[df[col].astype(str).isin(sel)]
    return df

def text_search(df, q):
    if not q.strip(): return df
    q = q.strip().lower()
    mask = pd.Series(False, index=df.index)
    for c in df.columns:
        if df[c].dtype == "object":
            mask |= df[c].astype(str).str.lower().str.contains(re.escape(q), na=False)
    return df[mask]


STOPWORDS = {
    "a","an","and","are","as","at","be","been","by","can","could","did","do","does",
    "for","from","had","has","have","how","i","in","into","is","it","me","of","on",
    "or","our","show","that","the","their","them","there","these","this","to","was",
    "were","what","when","where","which","who","with","would","all","any","please",
    "find","give","tell","list","records","record","data","dataset","datasets","2026"
}

def query_terms(q):
    """Turn a natural-language question into useful retrieval terms."""
    q = str(q or "").strip()
    phrases = re.findall(r'"([^"]+)"', q)
    cleaned = re.sub(r"[^A-Za-z0-9À-ÿ/_ -]+", " ", q.lower())
    words = [w for w in cleaned.split() if len(w) >= 3 and w not in STOPWORDS]
    seen = set()
    terms = []
    for t in phrases + words:
        tl = t.lower().strip()
        if tl and tl not in seen:
            seen.add(tl)
            terms.append(tl)
    return terms[:12]

def searchable_text(df):
    """Build one normalized text field per row across every column."""
    if df.empty:
        return pd.Series(dtype="object", index=df.index)
    return df.fillna("").astype(str).agg(" | ".join, axis=1).str.lower()

def smart_text_search(df, q, require_all=False, limit=250):
    """Rank natural-language matches instead of requiring an exact sentence match."""
    if df is None or df.empty or not str(q).strip():
        return df.head(0).copy() if df is not None else pd.DataFrame()

    terms = query_terms(q)
    if not terms:
        return text_search(df, q).head(limit)

    blob = searchable_text(df)
    score = pd.Series(0, index=df.index, dtype="int64")
    matched = pd.Series(0, index=df.index, dtype="int64")

    for term in terms:
        hit = blob.str.contains(re.escape(term), na=False)
        matched += hit.astype(int)
        score += hit.astype(int) * (2 if len(term) >= 6 else 1)

    needed = len(terms) if require_all else max(1, min(2, len(terms)))
    mask = matched >= needed
    result = df.loc[mask].copy()

    if result.empty and needed > 1:
        mask = matched >= 1
        result = df.loc[mask].copy()

    if result.empty:
        return result

    result["_pc_score"] = score.loc[result.index]
    result["_pc_terms"] = matched.loc[result.index]
    return result.sort_values(["_pc_score", "_pc_terms"], ascending=False).head(limit)

def extract_imo(q):
    m = re.search(r"\b(?:imo\s*[:#-]?\s*)?(\d{7})\b", str(q), flags=re.I)
    return m.group(1) if m else None

def likely_query_mode(q):
    ql = str(q).lower()
    if extract_imo(q) or any(k in ql for k in ["vessel", "ship", "tanker", "bulk carrier", "imo"]):
        return "Vessel / IMO lookup"
    if any(k in ql for k in ["sanction", "blacklist", "watchlist", "ofac", "fcdo", "cross-match", "cross match", "connected", "also appear"]):
        return "Cross-dataset intelligence"
    if any(k in ql for k in ["pattern", "trend", "emerging", "assessment", "what does", "why", "compare", "risk", "implication"]):
        return "Analytical question"
    return "Search records"

def dataset_hint_score(name, q):
    ql = str(q).lower()
    name_l = name.lower()
    score = 0
    hints = {
        "port": ["port","terminal","harbour","harbor","fujairah","duqm","khalifa"],
        "ukmto": ["ukmto","warning"],
        "attack": ["attack","strike","drone","missile","war","conflict"],
        "piracy": ["piracy","pirate","armed robbery","hijack","boarding"],
        "investment": ["investment","tender","project","procurement","opportunity","capital"],
        "centcom": ["centcom","us navy","u.s. navy","marine","boarding","blockade","disabled","seized"],
        "imo": ["imo","merchant vessel","confirmed incident","gulf incident"],
        "shipbuilding": ["shipbuilding","frigate","icebreaker","patrol boat","coast guard","naval","warship","builder","shipyard","contract"],
        "shipyard": ["shipyard","yard","acquisition","modernization","modernisation","industrial capacity","davie","hanwha","rheinmetall"],
        "black sea": ["black sea","ukraine","russia","crimea","odesa","odessa","chornomorsk"],
        "vessel": ["vessel","ship","tanker","imo","flag","owner"],
        "sanction": ["sanction","watchlist","ofac","fcdo","uani","seco","mfat"],
        "recaap": ["recaap","strait of malacca","singapore strait","asia"],
        "iuu": ["iuu","illegal fishing","fishing"],
        "companies": ["company","owner","subsidiary","group","leadership","ceo","parent"],
        "fleet": ["fleet","vessel","ship","owned","operated","charter"],
        "orders": ["order","newbuild","delivery","shipyard","builder"],
        "event": ["weather","typhoon","earthquake","strike","protest","cyber","disruption","labour"],
        "corridor": ["suez","panama","hormuz","malacca","corridor","chokepoint"]
    }
    for key, words in hints.items():
        if key in name_l and any(w in ql for w in words):
            score += 3
    return score

def display_columns(df):
    preferred = [
        "Date","date","Source Date","Departure Date","Arrival Date",
        "IMO","imo","Vessel","Vessel Name","Vessel / Asset","Ship","Name",
        "Country","Region","Port / Location","Location","Theatre",
        "Incident Category","Category","UKMTO Classification","Analytical Classification",
        "Event Summary","Summary","Description","Severity","Confidence",
        "Port / Operational Impact","Notes / Intelligence Relevance",
        "Flag","Owner","Operator","ofac","fcdo","eu","uani","seco","mfat","un",
        "Primary Source","Secondary Source"
    ]
    cols = [c for c in preferred if c in df.columns]
    return cols if cols else [c for c in df.columns if not c.startswith("_pc_")][:18]

def crossmatch_sanctions(datasets, watch_df, q):
    outputs = []
    watch_imo_col = next((c for c in ["imo","IMO","Imo"] if c in watch_df.columns), None)
    if not watch_imo_col:
        return outputs

    w = watch_df.copy()
    w["_pc_imo"] = pd.to_numeric(w[watch_imo_col], errors="coerce").astype("Int64")

    ql = str(q).lower()
    if "ofac" in ql and "ofac" in w.columns:
        w = w[w["ofac"].notna() & (w["ofac"].astype(str).str.strip() != "")]
    elif "fcdo" in ql and "fcdo" in w.columns:
        w = w[w["fcdo"].notna() & (w["fcdo"].astype(str).str.strip() != "")]

    imo = extract_imo(q)
    if imo:
        w = w[w["_pc_imo"] == int(imo)]

    for name, df in datasets.items():
        if name == "Sanctions/watchlists" or df is None or df.empty:
            continue
        imo_col = next((c for c in ["IMO","imo","Imo"] if c in df.columns), None)
        if not imo_col:
            continue
        x = df.copy()
        x["_pc_imo"] = pd.to_numeric(x[imo_col], errors="coerce").astype("Int64")
        m = x.merge(w, on="_pc_imo", how="inner", suffixes=("_record","_watch"))
        if not m.empty:
            outputs.append((f"{name} × sanctions/watchlists", m))
    return outputs



# ---------------- Visual intelligence helpers ----------------

# Approximate reference coordinates for named locations in the source data.
# These are for situational visualization only; the source record remains authoritative.
LOCATION_COORDS = [
    ("port of odesa", 46.4825, 30.7233),
    ("odesa", 46.4825, 30.7233),
    ("odessa", 46.4825, 30.7233),
    ("chornomorsk", 46.3017, 30.6569),
    ("pivdennyi", 46.6200, 31.1010),
    ("izmail", 45.3500, 28.8375),
    ("novorossiysk", 44.7238, 37.7680),
    ("crimea", 45.3000, 34.0000),

    ("khasab", 26.1799, 56.2477),
    ("al khasab", 26.1799, 56.2477),
    ("kumzar", 26.3360, 56.4080),
    ("limah", 25.9370, 56.4580),
    ("lima, oman", 25.9370, 56.4580),
    ("musandam", 26.1000, 56.2500),
    ("dibba", 25.6196, 56.2729),
    ("khor fakkan", 25.3313, 56.3578),
    ("fujairah", 25.1288, 56.3265),
    ("mina saqr", 25.9825, 56.0500),
    ("ras al khaimah", 25.7895, 55.9432),
    ("dubai", 25.2048, 55.2708),
    ("jebel ali", 24.9857, 55.0273),
    ("zayed port", 24.5200, 54.3810),
    ("abu dhabi", 24.4539, 54.3773),
    ("sharjah", 25.3463, 55.4209),

    ("port of bahrain", 26.2000, 50.6000),
    ("muharraq", 26.2572, 50.6119),
    ("bahrain", 26.0667, 50.5577),

    ("mubarak al kabeer", 29.4200, 48.0000),
    ("iraqi ttw", 29.7000, 48.6500),
    ("al basrah", 30.5000, 47.8300),
    ("basrah", 30.5000, 47.8300),

    ("jubail", 27.0174, 49.6225),
    ("ras tanura", 26.6430, 50.1590),
    ("ras laffan", 25.9100, 51.5500),
    ("doha", 25.2854, 51.5310),

    ("duqm", 19.6610, 57.7030),
    ("salalah", 16.9498, 54.0030),
    ("sohar", 24.3475, 56.7077),
    ("shinas", 24.7433, 56.4660),
    ("masirah", 20.6500, 58.8900),
    ("gulf of oman", 24.0000, 58.0000),
    ("strait of hormuz", 26.5700, 56.2500),
    ("persian/arabian gulf", 26.0000, 52.0000),
    ("persian gulf", 26.0000, 52.0000),

    ("chabahar", 25.2919, 60.6430),
    ("jask", 25.6530, 57.7740),
    ("bushehr", 28.9234, 50.8203),
    ("kharg", 29.2330, 50.3130),

    ("gwadar", 25.1216, 62.3254),
    ("arabian sea", 18.0000, 64.0000),

    ("aden", 12.7855, 45.0187),
    ("al mukalla", 14.5425, 49.1242),
    ("mukalla", 14.5425, 49.1242),
    ("al hudaydah", 14.7979, 42.9545),
    ("hudaydah", 14.7979, 42.9545),
    ("balhaf", 13.9850, 48.1800),
    ("socotra", 12.4634, 53.8237),
    ("gulf of aden", 12.5000, 48.0000),
    ("bab el-mandeb", 12.5833, 43.3333),

    ("xaafuun", 10.4200, 51.2500),
    ("mareeyo", 11.8100, 51.2500),
    ("garacad", 6.9500, 49.3000),
    ("eyl", 7.9800, 49.8200),
    ("mogadishu", 2.0469, 45.3182),
    ("puntland", 8.4000, 49.0000),
    ("somalia", 5.0000, 46.0000),

    ("damietta", 31.4165, 31.8133),
    ("rotterdam", 51.9244, 4.4777),
    ("port of tyne", 55.0070, -1.4320),
    ("holyhead", 53.3090, -4.6330),
    ("mumbai", 18.9388, 72.8354),
    ("paradip", 20.2648, 86.6740),
    ("kolkata", 22.5726, 88.3639),
    ("charleston", 32.7765, -79.9311),
    ("woods hole", 41.5265, -70.6731),
    ("douala", 4.0511, 9.7679),
    ("onne", 4.6820, 7.1500),
    ("batam", 1.1301, 104.0529),
    ("singapore", 1.3521, 103.8198),
    ("penang", 5.4141, 100.3288),
    ("malacca", 2.1896, 102.2501),
    ("mackay", -21.1411, 149.1860),
    ("aleutian", 52.0000, -170.0000),
    ("long beach", 33.7701, -118.1937),
]

COUNTRY_CENTROIDS = {
    "Oman": (20.5937, 56.2719),
    "UAE": (23.4241, 53.8478),
    "United Arab Emirates": (23.4241, 53.8478),
    "Egypt": (26.8206, 30.8025),
    "Ukraine": (48.3794, 31.1656),
    "Netherlands": (52.1326, 5.2913),
    "United Kingdom": (55.3781, -3.4360),
    "India": (20.5937, 78.9629),
    "United States": (37.0902, -95.7129),
    "Cameroon": (7.3697, 12.3547),
    "Nigeria": (9.0820, 8.6753),
    "Indonesia": (-0.7893, 113.9213),
    "Malaysia": (4.2105, 101.9758),
    "Australia": (-25.2744, 133.7751),
    "Bahrain": (26.0667, 50.5577),
    "Saudi Arabia": (23.8859, 45.0792),
    "Iraq": (33.2232, 43.6793),
    "Qatar": (25.3548, 51.1839),
    "Brazil": (-14.2350, -51.9253),
    "Sweden": (60.1282, 18.6435),
    "Canada": (56.1304, -106.3468),
    "Vietnam": (14.0583, 108.2772),
    "France": (46.2276, 2.2137),
    "Germany": (51.1657, 10.4515),
    "Philippines": (12.8797, 121.7740),
    "Finland": (61.9241, 25.7482),
}

def resolve_coords(value, country=None):
    """Resolve a named source location to an approximate visualization point."""
    s = str(value or "").lower()
    for key, lat, lon in LOCATION_COORDS:
        if key in s:
            return lat, lon, "Named-location approximation"
    if country:
        c = str(country).strip()
        if c in COUNTRY_CENTROIDS:
            lat, lon = COUNTRY_CENTROIDS[c]
            return lat, lon, "Country-centroid approximation"
        # Handle combined country labels such as Kuwait / Iraq TTW.
        for name, (lat, lon) in COUNTRY_CENTROIDS.items():
            if name.lower() in c.lower():
                return lat, lon, "Country-centroid approximation"
    return None, None, None

def map_points(df, location_cols=("Location","Port / Location","Region / Port"), country_col="Country", layer=None):
    if df is None or df.empty:
        return pd.DataFrame(columns=["lat","lon","Location","Layer","Coordinate confidence"])
    out = []
    for _, row in df.iterrows():
        loc = ""
        for c in location_cols:
            if c in df.columns and pd.notna(row.get(c)):
                loc = str(row.get(c))
                if loc.strip():
                    break
        country = row.get(country_col) if country_col in df.columns else None
        lat, lon, confidence = resolve_coords(loc, country)
        if lat is None:
            continue
        rec = {
            "lat": lat,
            "lon": lon,
            "Location": loc or str(country or ""),
            "Layer": layer or "Record",
            "Coordinate confidence": confidence,
        }
        for c in ["Date","Vessel","IMO","Incident Category","Category","Outcome","Severity","Action Type"]:
            if c in df.columns:
                rec[c] = row.get(c)
        out.append(rec)
    return pd.DataFrame(out)

def render_map(df, location_cols=("Location","Port / Location","Region / Port"), country_col="Country", layer=None, caption=True):
    pts = map_points(df, location_cols=location_cols, country_col=country_col, layer=layer)
    if pts.empty:
        st.info("No map-ready locations are available for the current filter.")
        return pts
    st.map(pts, latitude="lat", longitude="lon", use_container_width=True)
    if caption:
        st.caption(
            f"Mapped {len(pts):,} records. Positions are approximate reference points derived from named locations; "
            "the evidence table and cited source remain authoritative."
        )
    return pts

def monthly_series(frames):
    """frames = [(label, dataframe, preferred date columns)]"""
    parts = []
    for label, df, cols in frames:
        date_col = next((c for c in cols if c in df.columns), None)
        if not date_col:
            continue
        d = pd.to_datetime(df[date_col], errors="coerce")
        x = pd.DataFrame({"Month": d.dt.to_period("M").dt.to_timestamp(), "Layer": label})
        x = x.dropna()
        parts.append(x)
    if not parts:
        return pd.DataFrame()
    z = pd.concat(parts, ignore_index=True)
    return z.groupby(["Month","Layer"]).size().unstack(fill_value=0).sort_index()

def render_monthly_chart(frames, title="Activity over time"):
    series = monthly_series(frames)
    if series.empty:
        return
    st.markdown(f"#### {title}")
    st.line_chart(series, use_container_width=True)

def render_count_chart(df, col, title, top=10):
    if col not in df.columns or df.empty:
        return
    counts = (
        df[col].fillna("Unknown").astype(str)
        .replace({"": "Unknown"})
        .value_counts()
        .head(top)
        .sort_values()
    )
    if counts.empty:
        return
    st.markdown(f"#### {title}")
    st.bar_chart(counts, use_container_width=True)

def render_evidence_table(df, expanded=True, preferred=("Date","date","Source Date","Departure Date","Arrival Date")):
    display_df = sort_latest(df, preferred=preferred).copy()

    # Format dates locally so the evidence renderer cannot fail because of helper ordering.
    for c in (
        "Date", "date", "Source Date", "Published",
        "Departure Date", "Arrival Date",
        "2026 Event Date", "Original Contract / Decision Date"
    ):
        if c in display_df.columns:
            parsed = pd.to_datetime(display_df[c], errors="coerce")
            mask = parsed.notna()
            if mask.any():
                display_df.loc[mask, c] = parsed.loc[mask].dt.strftime("%d %b %Y")

    with st.expander("Evidence table", expanded=expanded):
        st.dataframe(display_df, use_container_width=True, hide_index=True)

def result_visual_summary(results):
    """Visual layer for Ask P&C based only on retrieved evidence."""
    if not results:
        return
    st.markdown("### Visual summary")
    a, b = st.columns([1.2, 1])

    # Dataset coverage chart
    coverage = pd.Series({name: len(df) for name, df in results}).sort_values()
    with b:
        st.markdown("#### Evidence by dataset")
        st.bar_chart(coverage, use_container_width=True)

    # Aggregate map-ready rows
    points = []
    date_frames = []
    for name, df in results:
        p = map_points(df, layer=name)
        if not p.empty:
            points.append(p)
        date_frames.append((name, df, ("Date","date","Source Date","Published","Departure Date","2026 Event Date")))

    with a:
        if points:
            combined = pd.concat(points, ignore_index=True)
            st.markdown("#### Geographic evidence")
            st.map(combined, latitude="lat", longitude="lon", use_container_width=True)
            st.caption("Map positions are approximate reference points derived from named locations.")
        else:
            st.info("No map-ready locations were found in the retrieved evidence.")

    series = monthly_series(date_frames)
    if not series.empty:
        st.markdown("#### Retrieved activity over time")
        st.line_chart(series, use_container_width=True)


# ---------------- Data ----------------
recaap = dates(load("recaap_incidents_2024_2026.csv"), "date")
ports = dates(load("port_incidents_2026.csv"), "Date")
ukmto = dates(load("ukmto_warnings_2026.csv"), "Date")
attacks = dates(load("maritime_attacks_2026.csv"), "Date")
piracy = dates(load("piracy_2026.csv"), "Date")
invest = dates(load("port_investments_2026.csv"), "Source Date")
bs_voy = dates(load("blacksea_voyages_2026.csv"), "Departure Date", "Arrival Date")
bs_conflict = dates(load("blacksea_conflict_vessels_2026.csv"), "Date")
bs_ports = dates(load("blacksea_port_attacks_2026.csv"), "Date")
bs_profiles = load("blacksea_vessel_profiles.csv")
iuu = load("iuu_fishing_index_2019_2025.csv")
watch = load("vessel_watchlists.csv")
centcom = dates(load("centcom_maritime_actions_2026.csv"), "Date")
imo_gulf = dates(load("imo_gulf_confirmed_2026.csv"), "Date")
naval_build = dates(load("naval_shipbuilding_2026.csv"), "2026 Event Date", "Original Contract / Decision Date")
shipyard_moves = dates(load("shipyard_industrial_moves_2026.csv"), "Date")
bs_articles = dates(load("blacksea_article_index_2026.csv"), "Published")

# ---------------- Canonical trade-system model ----------------
entity_registry = load("entity_registry.csv")
companies = load("companies.csv")
people = load("people.csv")
leadership_roles = load("leadership_roles.csv")
model_assets = load("assets.csv")
model_ports = load("ports.csv")
model_vessels = load("vessels.csv")
fleet_portfolios = load("fleet_portfolios.csv")
fleet_orders = load("fleet_orders.csv")
model_aircraft = load("aircraft.csv")
model_shipyards = load("shipyards.csv")
model_investments = load("investments.csv")
infra_works = load("infrastructure_works.csv")
strategic_events = dates(load("strategic_events.csv"), "Date")
corridors = load("corridors.csv")
model_relationships = load("relationships.csv")
model_sources = load("sources.csv")
event_taxonomy = load("event_taxonomy.csv")
event_observations = dates(load("event_observations.csv"), "Date")
external_disruptions = dates(load("external_disruptions.csv"), "Date")
event_impacts = load("event_impacts.csv")
vessel_relationships = load("vessel_relationships.csv")
vessel_build_records = load("vessel_build_records.csv")
vessel_contracts = load("vessel_contracts.csv")
fleet_coverage = load("fleet_coverage.csv")
vessel_imo_verification = load("vessel_imo_verification.csv")
imo_coverage = load("imo_coverage.csv")
vessel_identifiers = load("vessel_identifiers.csv")
ferry_systems = load("ferry_systems.csv")
ferry_routes = load("ferry_routes.csv")
ferry_terminals = load("ferry_terminals.csv")
ferry_vessel_staging = load("ferry_vessel_staging.csv")
ferry_disruption_taxonomy = load("ferry_disruption_taxonomy.csv")
ferry_service_observations = dates(load("ferry_service_observations.csv"), "Date")
ferry_performance = dates(load("ferry_performance.csv"), "Period Start", "Period End")
ferry_fleet_status = dates(load("ferry_fleet_status.csv"), "As Of")
regional_systems = load("regional_systems.csv")
system_nodes = load("system_nodes.csv")
system_links = load("system_links.csv")
great_lakes_ports = load("great_lakes_ports.csv")
company_system_footprints = load("company_system_footprints.csv")
great_lakes_vessel_staging = load("great_lakes_vessel_staging.csv")
great_lakes_cargo_corridors = load("great_lakes_cargo_corridors.csv")
great_lakes_cruise = load("great_lakes_cruise.csv")
great_lakes_disruptions = load("great_lakes_disruptions.csv")
system_dependencies = load("system_dependencies.csv")
global_vessel_staging = load("global_vessel_staging.csv")
vessel_evidence = dates(load("vessel_evidence.csv"), "Checked As Of")
event_entity_links = load("event_entity_links.csv")
fleet_research_universe = load("fleet_research_universe.csv")
carrier_deployment_seeds = load("carrier_deployment_seeds.csv")
carrier_fleet_targets = load("carrier_fleet_targets.csv")
carrier_fleet_master = load("carrier_fleet_master.csv")
fleet_ranking_snapshots = load("fleet_ranking_snapshots.csv")
tanker_fleet_universe = load("tanker_fleet_universe.csv")
vessel_restrictions = load("vessel_restrictions.csv")
tradeability_assessments = load("tradeability_assessments.csv")
vessel_transactions = load("vessel_transactions.csv")
tanker_corridor_exposure = load("tanker_corridor_exposure.csv")
weather_labour_events = dates(load("weather_labour_events.csv"), "Date")
disruption_watch = dates(load("disruption_watch.csv"), "As Of", "Next Known Date")
infrastructure_investors = load("infrastructure_investors.csv")
infrastructure_holdings = dates(load("infrastructure_holdings.csv"), "Effective From", "Effective To")
infrastructure_deals = dates(load("infrastructure_deals.csv"), "Announced Date", "Completed / Effective Date")
economic_zones = load("economic_zones.csv")
logistics_real_estate = load("logistics_real_estate.csv")
dry_ports_inland_hubs = load("dry_ports_inland_hubs.csv")
infrastructure_connections = load("infrastructure_connections.csv")
integrated_logistics_networks = load("integrated_logistics_networks.csv")

COMPANY_NAME = dict(zip(companies.get("Company ID", pd.Series(dtype=str)).astype(str), companies.get("Company", pd.Series(dtype=str)).astype(str)))
PERSON_NAME = dict(zip(people.get("Person ID", pd.Series(dtype=str)).astype(str), people.get("Name", pd.Series(dtype=str)).astype(str)))

def with_company_name(df, id_col, out_col="Company"):
    x = df.copy()
    if id_col in x.columns:
        x[out_col] = x[id_col].astype(str).map(COMPANY_NAME).fillna(x[id_col].astype(str))
    return x

def entity_company_hits(company_id):
    rel = model_relationships.copy()
    if rel.empty:
        return rel
    return rel[(rel["Source Entity"].astype(str)==company_id) | (rel["Target Entity"].astype(str)==company_id)]

def normalize_pct_column(df, col):
    x = df.copy()
    if col in x.columns:
        x[col] = pd.to_numeric(x[col], errors="coerce")
    return x


# ---------------- Navigation ----------------
st.sidebar.markdown("### POWER & CORRIDORS")
st.sidebar.caption("INTELLIGENCE PLATFORM · OPERATING PICTURE")
page = st.sidebar.radio(
    "Navigate",
    [
        "Operating Picture",
        "Ask P&C",
        "Companies",
        "Integrated Logistics",
        "Leadership",
        "Vessels & Fleets",
        "Vehicle Logistics",
        "Ferry Systems",
        "Great Lakes System",
        "Tanker Intelligence",
        "Energy Shipping",
        "Ports & Terminals",
        "Infrastructure & Inland Logistics",
        "Shipyards & Orders",
        "Events & Disruptions",
        "Weather & Labour",
        "Corridors",
        "Maritime Attacks",
        "Piracy & Armed Robbery",
        "UKMTO Warnings",
        "Gulf Military Actions",
        "Port Incidents",
        "Port Investment",
        "Naval & Shipbuilding",
        "Black Sea",
        "Vessel Intelligence",
        "Sanctions & Watchlists",
        "IUU Fishing Risk",
        "ReCAAP Archive",
    ],
)
st.sidebar.divider()
st.sidebar.caption("From events to implications.")
st.sidebar.markdown("[powerncorridors.com](https://www.powerncorridors.com/)")

# ---------------- Operating Picture ----------------
if page == "Operating Picture":
    masthead(
        "P&C Trade System Intelligence",
        "A whole-system operating picture linking companies, vessels, ports, air cargo and integrated logistics, investors, economic zones, logistics real estate, inland hubs, shipyards, incidents, disruptions and strategic trade corridors."
    )

    c1,c2,c3,c4 = st.columns(4)
    with c1: card("Companies", f"{len(companies):,}", "Corporate and business-unit entities")
    with c2: card("Individual Vessels", f"{len(model_vessels):,}", "Normalized vessel records")
    with c3: card("Event Observations", f"{len(event_observations):,}", "Operational evidence across current feeds")
    with c4: card("Ports / Facilities", f"{len(model_ports):,}", "Canonical port and terminal records")

    d1,d2,d3,d4 = st.columns(4)
    with d1: card("Fleet Orders", f"{len(fleet_orders):,}", "Merchant, air and defence build/order records")
    with d2: card("Shipyards", f"{len(model_shipyards):,}", "Industrial build locations")
    with d3: card("Vessel Relationships", f"{len(vessel_relationships):,}", "Owner / operator / charter / cargo links")
    with d4: card("Event Families", f"{event_observations['Event Family'].nunique() if 'Event Family' in event_observations.columns else 0:,}", "Security, weather, labour, cyber and more")

    f1,f2,f3 = st.columns(3)
    f1.metric("Ferry systems", len(ferry_systems))
    f2.metric("Ferry route seeds", len(ferry_routes))
    f3.metric("Ferry terminals", len(ferry_terminals))

    g1,g2,g3 = st.columns(3)
    g1.metric("Great Lakes ports", len(great_lakes_ports))
    g2.metric("Great Lakes company footprints", len(company_system_footprints))
    g3.metric("Great Lakes system dependencies", len(system_dependencies))

    h1,h2,h3 = st.columns(3)
    h1.metric("Integrated logistics layers", len(integrated_logistics_networks))
    h2.metric("Aircraft / operator records", len(model_aircraft))
    h3.metric("Logistics real-estate records", len(logistics_real_estate))

    st.markdown("### Current operating picture")
    op_points = map_points(
        event_observations,
        location_cols=("Location",),
        country_col="Country",
        layer="Trade-system event observation"
    )
    if not op_points.empty:
        st.map(op_points, latitude="lat", longitude="lon", use_container_width=True)
        st.caption(f"{len(op_points):,} event observations could be mapped using named-location or country reference points. Source records remain authoritative.")
    else:
        st.info("No event observations could be resolved to the current approximate map dictionary.")

    left,right = st.columns(2)
    with left:
        render_monthly_chart([
            ("Event observations", event_observations, ("Date",)),
            ("Maritime attacks", attacks, ("Date",)),
            ("Port incidents", ports, ("Date",)),
            ("Piracy", piracy, ("Date",)),
        ], "Trade-system disruptions over time")
    with right:
        render_count_chart(event_observations, "Event Family", "Event observations by family", top=12)

    st.markdown("### Fleet & infrastructure build-out")
    a,b = st.columns(2)
    with a:
        if "Buyer / Operator Company ID" in fleet_orders.columns:
            fo = with_company_name(fleet_orders, "Buyer / Operator Company ID", "Buyer / Operator")
            render_count_chart(fo, "Buyer / Operator", "Fleet/order records by company", top=12)
    with b:
        if "Build Country" in fleet_orders.columns:
            render_count_chart(fleet_orders, "Build Country", "Build countries", top=12)

    st.markdown("### Latest cross-domain events")
    latest = sort_latest(event_observations, preferred=("Date",)).head(20)
    cols = [c for c in ["Date","Event Family","Event Type","Mode","Country","Location","Subject Name","Operational Impact","Trade Impact","Severity","Confidence"] if c in latest.columns]
    st.dataframe(format_dates_for_display(latest[cols]), use_container_width=True, hide_index=True)


# ---------------- Ask P&C ----------------
elif page == "Ask P&C":
    masthead(
        "Ask P&C",
        "Search the P&C trade-system knowledge base across companies, leadership, fleets, ports, shipyards, investment, incidents, weather, labour disruption, sanctions and corridors."
    )

    st.markdown("#### Start with a question")
    ex1, ex2, ex3 = st.columns(3)
    with ex1:
        if st.button("Black Sea sanctioned vessels", use_container_width=True):
            st.session_state["ask_pc_query"] = "Which sanctioned vessels also appear in Black Sea voyage or conflict reporting?"
    with ex2:
        if st.button("2026 port attacks", use_container_width=True):
            st.session_state["ask_pc_query"] = "Show port attacks and conflict-related port incidents in 2026"
    with ex3:
        if st.button("Piracy patterns", use_container_width=True):
            st.session_state["ask_pc_query"] = "What patterns are emerging in piracy and armed robbery incidents?"

    q = st.text_input(
        "Ask P&C",
        key="ask_pc_query",
        placeholder="e.g. Which sanctioned vessels also appear in Black Sea voyage data?"
    )

    datasets = {
        "Port incidents": ports,
        "UKMTO warnings": ukmto,
        "Maritime attacks": attacks,
        "Piracy": piracy,
        "CENTCOM maritime actions": centcom,
        "IMO Gulf confirmed incidents": imo_gulf,
        "Port investment": invest,
        "Naval & coast guard shipbuilding": naval_build,
        "Shipyard industrial moves": shipyard_moves,
        "Black Sea source index": bs_articles,
        "Black Sea voyages": bs_voy,
        "Black Sea conflict vessels": bs_conflict,
        "Black Sea port attacks": bs_ports,
        "Vessel profiles": bs_profiles,
        "Sanctions/watchlists": watch,
        "IUU fishing risk": iuu,
        "ReCAAP": recaap,
        "Companies": companies,
        "Integrated logistics networks": integrated_logistics_networks,
        "Leadership roles": leadership_roles,
        "Trade-system assets": model_assets,
        "Ports and terminals": model_ports,
        "Vessels": model_vessels,
        "Fleet portfolios": fleet_portfolios,
        "Fleet orders": fleet_orders,
        "Aircraft": model_aircraft,
        "Shipyards": model_shipyards,
        "Corporate investments": model_investments,
        "Infrastructure works": infra_works,
        "Strategic events": strategic_events,
        "Corridors": corridors,
        "Corporate relationships": model_relationships,
        "Event observations": event_observations,
        "External disruptions": external_disruptions,
        "Event impacts": event_impacts,
        "Vessel relationships": vessel_relationships,
        "Vessel build records": vessel_build_records,
        "Vessel contracts": vessel_contracts,
        "Fleet coverage": fleet_coverage,
        "Vessel identifiers": vessel_identifiers,
        "Ferry systems": ferry_systems,
        "Ferry routes": ferry_routes,
        "Ferry terminals": ferry_terminals,
        "Ferry vessel staging": ferry_vessel_staging,
        "Ferry service observations": ferry_service_observations,
        "Ferry performance": ferry_performance,
        "Ferry fleet status": ferry_fleet_status,
        "Ferry disruption taxonomy": ferry_disruption_taxonomy,
        "Regional systems": regional_systems,
        "System nodes": system_nodes,
        "System links": system_links,
        "Great Lakes ports": great_lakes_ports,
        "Company system footprints": company_system_footprints,
        "Great Lakes vessel staging": great_lakes_vessel_staging,
        "Great Lakes cargo corridors": great_lakes_cargo_corridors,
        "Great Lakes cruise": great_lakes_cruise,
        "Great Lakes disruptions": great_lakes_disruptions,
        "System dependencies": system_dependencies,
        "Global vessel staging": global_vessel_staging,
        "Vessel evidence": vessel_evidence,
        "Event entity links": event_entity_links,
        "Fleet research universe": fleet_research_universe,
        "Carrier deployment seeds": carrier_deployment_seeds,
        "Carrier fleet targets": carrier_fleet_targets,
        "Carrier fleet master": carrier_fleet_master,
        "Fleet ranking snapshots": fleet_ranking_snapshots,
        "Tanker fleet universe": tanker_fleet_universe,
        "Vessel restrictions": vessel_restrictions,
        "Tradeability assessments": tradeability_assessments,
        "Vessel transactions": vessel_transactions,
        "Tanker corridor exposure": tanker_corridor_exposure,
        "Weather labour events": weather_labour_events,
        "Disruption watch": disruption_watch,
        "Infrastructure investors": infrastructure_investors,
        "Infrastructure holdings": infrastructure_holdings,
        "Infrastructure deals": infrastructure_deals,
        "Economic and free zones": economic_zones,
        "Logistics real estate": logistics_real_estate,
        "Dry ports and inland hubs": dry_ports_inland_hubs,
        "Infrastructure connections": infrastructure_connections,
    }

    mode_options = [
        "Auto",
        "Search records",
        "Vessel / IMO lookup",
        "Cross-dataset intelligence",
        "Analytical question",
    ]
    selected_mode = st.selectbox(
        "Query mode",
        mode_options,
        index=0,
        help="Auto usually works best. Choose a mode when you want to constrain how Ask P&C interprets the question."
    )

    if q:
        mode = likely_query_mode(q) if selected_mode == "Auto" else selected_mode
        st.caption(f"Interpreting this as: **{mode}**")

        results = []
        imo = extract_imo(q)

        if mode == "Vessel / IMO lookup":
            vessel_sets = {
                "Black Sea voyages": bs_voy,
                "Black Sea conflict vessels": bs_conflict,
                "Vessel profiles": bs_profiles,
                "Sanctions/watchlists": watch,
                "Maritime attacks": attacks,
                "Piracy": piracy,
                "UKMTO warnings": ukmto,
                "CENTCOM maritime actions": centcom,
                "IMO Gulf confirmed incidents": imo_gulf,
                "Port incidents": ports,
                "Canonical vessels": model_vessels,
                "Vessel identifiers": vessel_identifiers,
                "Ferry vessel staging": ferry_vessel_staging,
                "Ferry fleet status": ferry_fleet_status,
                "Great Lakes vessel staging": great_lakes_vessel_staging,
                "Great Lakes cruise": great_lakes_cruise,
                "Global vessel staging": global_vessel_staging,
                "Vessel evidence": vessel_evidence,
                "Vessel relationships": vessel_relationships,
                "Vessel build records": vessel_build_records,
                "Vessel contracts": vessel_contracts,
                "Event entity links": event_entity_links,
            }
            search_q = imo if imo else q
            for name, df in vessel_sets.items():
                hit = smart_text_search(df, search_q, require_all=False)
                if not hit.empty:
                    results.append((name, hit))

        elif mode == "Cross-dataset intelligence":
            ql = q.lower()
            if any(k in ql for k in ["sanction", "blacklist", "watchlist", "ofac", "fcdo"]):
                results.extend(crossmatch_sanctions(datasets, watch, q))

            for name, df in datasets.items():
                hit = smart_text_search(df, q, require_all=False)
                if not hit.empty:
                    results.append((name, hit))

        else:
            ranked = []
            for name, df in datasets.items():
                hit = smart_text_search(df, q, require_all=False)
                if not hit.empty:
                    ranked.append((dataset_hint_score(name, q), name, hit))
            ranked.sort(key=lambda x: (x[0], len(x[2])), reverse=True)
            results = [(name, hit) for _, name, hit in ranked]

        seen_names = set()
        deduped = []
        for name, df in results:
            if name in seen_names:
                continue
            seen_names.add(name)
            deduped.append((name, df))
        results = deduped

        if not results:
            st.warning(
                "No matching evidence was found in the current P&C datasets. "
                "Try a vessel name or IMO, port, country, incident type, sanctions source, or a shorter question."
            )
        else:
            total = sum(len(df) for _, df in results)
            st.success(f"Found {total:,} relevant records across {len(results)} dataset(s).")

            result_visual_summary(results)

            st.markdown("### Evidence found")
            evidence_summary = pd.DataFrame({
                "Dataset": [name for name, _ in results],
                "Matched records": [len(df) for _, df in results],
            })
            st.dataframe(evidence_summary, use_container_width=True, hide_index=True)

            evidence_chunks = []
            max_groups = 8 if mode != "Analytical question" else 10

            for name, df in results[:max_groups]:
                st.markdown(f"#### {name} — {len(df):,} relevant records")
                show = df.drop(columns=[c for c in ["_pc_score","_pc_terms","_pc_imo"] if c in df.columns], errors="ignore")
                cols = display_columns(show)
                st.dataframe(format_dates_for_display(show[cols].head(75)), use_container_width=True, hide_index=True)

                ai_show = show[cols].head(25)
                evidence_chunks.append(
                    f"\nDATASET: {name}\nMATCHED RECORDS: {len(df)}\n{ai_show.to_csv(index=False)}"
                )

            st.markdown("### P&C retrieval assessment")
            if mode == "Vessel / IMO lookup":
                st.write(
                    f"The query is supported by **{len(results)} dataset(s)**. "
                    "Review the evidence above for vessel identity, movement, incident and sanctions/watchlist overlap."
                )
            elif mode == "Cross-dataset intelligence":
                cross_groups = [name for name, _ in results if "× sanctions/watchlists" in name]
                if cross_groups:
                    st.write(
                        f"Cross-dataset links were found in **{len(cross_groups)} dataset(s)** using IMO matching. "
                        "These are stronger links than ordinary keyword matches because the records share a vessel identifier."
                    )
                else:
                    st.write(
                        "Relevant records were found across multiple datasets, but no direct IMO-based sanctions/watchlist "
                        "cross-match was established by the local retrieval layer."
                    )
            elif mode == "Analytical question":
                st.write(
                    "The evidence above is the factual base for an assessment. "
                    "Use AI synthesis below, when enabled, to identify patterns while keeping facts separate from inference."
                )
            else:
                st.write(
                    f"Relevant evidence was found across **{len(results)} dataset(s)**. "
                    "Results are ranked from the natural-language terms in your question rather than an exact sentence match."
                )

            api_key = None
            try:
                api_key = st.secrets.get("OPENAI_API_KEY")
            except Exception:
                api_key = None

            if api_key:
                if st.button("Generate evidence-based P&C assessment", type="primary"):
                    try:
                        from openai import OpenAI
                        client = OpenAI(api_key=api_key)

                        prompt = f"""
You are the analytical layer for Power & Corridors, a maritime, trade-corridor and geopolitical intelligence platform.

USER QUESTION:
{q}

QUERY MODE:
{mode}

RULES:
- Answer only from the retrieved evidence supplied below.
- Never invent a vessel relationship, event, sanction, ownership link, date, location or causal claim.
- Separate confirmed database evidence from analytical inference.
- If the evidence is insufficient, say so explicitly.
- Distinguish government sanctions from non-government analytical/watchlist sources.
- For pattern questions, state the pattern, the evidence supporting it, and important exceptions.
- Use this exact structure:

ANSWER
A concise direct answer to the user's question.

EVIDENCE
The strongest supporting records and cross-dataset links.

ASSESSMENT
What the evidence may mean. Clearly label inference.

CONFIDENCE & GAPS
State confidence and missing or conflicting information.

DATASETS USED
List only the supplied datasets actually used.

RETRIEVED EVIDENCE:
{''.join(evidence_chunks)[:70000]}
"""
                        resp = client.responses.create(
                            model="gpt-5.6",
                            input=prompt,
                        )
                        st.markdown("### P&C AI assessment")
                        st.write(resp.output_text)
                        st.caption(
                            "AI synthesis is constrained to the retrieved P&C records shown above. "
                            "It does not independently verify external facts."
                        )
                    except Exception as e:
                        st.error(f"AI synthesis could not run: {e}")
            else:
                st.info(
                    "AI synthesis is not enabled yet. The structured evidence retrieval and cross-dataset matching above "
                    "work without an API key. Add OPENAI_API_KEY in Streamlit → App settings → Secrets when ready."
                )



# ---------------- Companies ----------------
elif page == "Companies":
    masthead("Company Intelligence", "Explore corporate ecosystems, ownership relationships, leadership, assets, fleets, orders, investment and exposure to trade-system events.")
    company_list = companies.sort_values("Company")["Company"].dropna().astype(str).tolist()
    selected_name = st.selectbox("Company", company_list)
    row = companies[companies["Company"].astype(str)==selected_name].iloc[0]
    cid = str(row["Company ID"])

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("HQ", f"{row.get('HQ City','')}, {row.get('HQ Country','')}".strip(', '))
    c2.metric("Entity type", row.get("Entity Type","—"))
    owned_vessels = model_vessels[(model_vessels.get("Owner Company ID", pd.Series(dtype=str)).astype(str)==cid) | (model_vessels.get("Operator Company ID", pd.Series(dtype=str)).astype(str)==cid)]
    c3.metric("Individual vessel records", len(owned_vessels))
    c4.metric("Relationship edges", len(entity_company_hits(cid)))
    st.markdown(f"**Ownership:** {row.get('Ownership','')}  \n**Business segments:** {row.get('Business Segments','')}  \n**Scale / network:** {row.get('Scale / Network Notes','')}")

    tabs = st.tabs(["Leadership","Relationships","Fleet","Assets","Orders & Investment","Events","Integrated Network"])
    with tabs[0]:
        lr = leadership_roles[leadership_roles["Company ID"].astype(str)==cid].copy()
        if not lr.empty:
            lr["Person"] = lr["Person ID"].astype(str).map(PERSON_NAME)
            cols=[c for c in ["Person","Title","Scope","Status","Effective From","Effective To","Source ID"] if c in lr.columns]
            st.dataframe(format_dates_for_display(lr[cols]), use_container_width=True, hide_index=True)
        else: st.info("No leadership roles are captured yet for this entity.")
    with tabs[1]:
        rel = entity_company_hits(cid)
        st.dataframe(rel, use_container_width=True, hide_index=True) if not rel.empty else st.info("No relationship edges captured yet.")
    with tabs[2]:
        fp = fleet_portfolios[fleet_portfolios["Company ID"].astype(str)==cid]
        if not fp.empty:
            st.markdown("#### Fleet portfolios")
            st.dataframe(fp, use_container_width=True, hide_index=True)
        if not owned_vessels.empty:
            st.markdown("#### Individual vessels")
            cols=[c for c in ["Vessel Name","IMO","Vessel Type","Subtype / Class","Flag","Year Built","DWT","Capacity","Fuel / Propulsion","Status","Completeness Note"] if c in owned_vessels.columns]
            st.dataframe(owned_vessels[cols],use_container_width=True,hide_index=True)
        cov=fleet_coverage[fleet_coverage["Company ID"].astype(str)==cid]
        if not cov.empty:
            st.markdown("#### Coverage")
            st.dataframe(cov,use_container_width=True,hide_index=True)
    with tabs[3]:
        aa=model_assets[model_assets["Company ID"].astype(str)==cid]
        st.dataframe(aa,use_container_width=True,hide_index=True) if not aa.empty else st.info("No canonical asset records captured yet.")
    with tabs[4]:
        fo=fleet_orders[fleet_orders["Buyer / Operator Company ID"].astype(str)==cid]
        inv=model_investments[model_investments["Company ID"].astype(str)==cid]
        if not fo.empty:
            st.markdown("#### Fleet / build orders")
            st.dataframe(format_dates_for_display(fo),use_container_width=True,hide_index=True)
        if not inv.empty:
            st.markdown("#### Investment")
            st.dataframe(format_dates_for_display(inv),use_container_width=True,hide_index=True)
        if fo.empty and inv.empty: st.info("No order or investment records captured yet.")
    with tabs[5]:
        ev=event_observations[event_observations.fillna("").astype(str).agg(" | ".join,axis=1).str.contains(re.escape(selected_name),case=False,na=False)]
        st.dataframe(format_dates_for_display(sort_latest(ev)),use_container_width=True,hide_index=True) if not ev.empty else st.info("No event observations directly reference this company name yet.")
    with tabs[6]:
        net = integrated_logistics_networks[
            (integrated_logistics_networks["Parent Company ID"].fillna("").astype(str)==cid) |
            (integrated_logistics_networks["Platform / Division Company ID"].fillna("").astype(str)==cid)
        ].copy()
        if not net.empty:
            st.dataframe(net, use_container_width=True, hide_index=True)
        else:
            st.info("No integrated-logistics network rows are captured yet for this entity.")

# ---------------- Integrated Logistics ----------------
elif page == "Integrated Logistics":
    masthead(
        "Integrated Logistics Networks",
        "Follow the companies and operating platforms that connect ocean, air, rail, road, warehousing, free zones and final distribution into one trade system."
    )

    net = integrated_logistics_networks.copy()
    net["Group ID"] = net["Parent Company ID"].fillna("").astype(str).str.strip()
    standalone = net["Group ID"].eq("")
    net.loc[standalone, "Group ID"] = net.loc[standalone, "Platform / Division Company ID"].fillna("").astype(str)
    net["Group"] = net["Group ID"].map(COMPANY_NAME).fillna(net["Group ID"])
    groups = sorted([x for x in net["Group"].dropna().astype(str).unique() if x.strip()])
    selected_group = st.selectbox("Group / standalone network", groups)
    x = net[net["Group"].astype(str)==selected_group].copy()

    selected_ids = set(x["Group ID"].dropna().astype(str))
    selected_ids.update(x["Parent Company ID"].dropna().astype(str))
    selected_ids.update(x["Platform / Division Company ID"].dropna().astype(str))
    selected_ids.discard("")

    modes = set()
    for value in x.get("Modes", pd.Series(dtype=str)).fillna("").astype(str):
        modes.update([m.strip() for m in value.split(";") if m.strip()])
    assets_x = model_assets[model_assets["Company ID"].fillna("").astype(str).isin(selected_ids)].copy()
    fleets_x = fleet_portfolios[fleet_portfolios["Company ID"].fillna("").astype(str).isin(selected_ids)].copy()
    aircraft_x = model_aircraft[model_aircraft["Operator Company ID"].fillna("").astype(str).isin(selected_ids)].copy()

    a,b,c,d = st.columns(4)
    a.metric("Network layers", len(x))
    b.metric("Transport / logistics modes", len(modes))
    c.metric("Canonical assets / hubs", len(assets_x))
    d.metric("Fleet / capacity rows", len(fleets_x) + len(aircraft_x))

    st.caption(
        "The model preserves ownership, legal entity, operating platform, asset operator, carrier and cargo-principal roles separately. "
        "Network totals do not imply individual vehicle or aircraft capture."
    )

    tab1,tab2,tab3,tab4,tab5 = st.tabs(["Network Footprint","Assets & Hubs","Fleet & Capacity","Investment & Events","Relationships"])
    with tab1:
        show = x.copy()
        show["Parent"] = show["Parent Company ID"].map(COMPANY_NAME).fillna(show["Parent Company ID"])
        show["Platform"] = show["Platform / Division Company ID"].map(COMPANY_NAME).fillna(show["Platform / Division"])
        cols=[c for c in ["Parent","Platform","Network Role","Modes","Asset Model","Reported Scale","Key Hubs / Nodes","Geographic Footprint","External Customer Offering","Strategic / Market Signal","Status","As Of","Source ID"] if c in show.columns]
        st.dataframe(format_dates_for_display(show[cols]),use_container_width=True,hide_index=True)
    with tab2:
        if not assets_x.empty:
            st.markdown("#### Canonical assets / hubs")
            st.dataframe(assets_x,use_container_width=True,hide_index=True)
        lre_asset_ids=set(assets_x.get("Asset ID",pd.Series(dtype=str)).dropna().astype(str))
        lre_x=logistics_real_estate[logistics_real_estate["Asset ID"].fillna("").astype(str).isin(lre_asset_ids)].copy()
        if not lre_x.empty:
            st.markdown("#### Logistics real estate")
            st.dataframe(lre_x,use_container_width=True,hide_index=True)
        conn_x=infrastructure_connections[infrastructure_connections["Source Asset ID"].fillna("").astype(str).isin(lre_asset_ids)].copy()
        if not conn_x.empty:
            st.markdown("#### Infrastructure connections")
            st.dataframe(conn_x,use_container_width=True,hide_index=True)
        if assets_x.empty and lre_x.empty and conn_x.empty:
            st.info("No physical asset records are captured yet for this group.")
    with tab3:
        if not fleets_x.empty:
            st.markdown("#### Fleet / network portfolio")
            st.dataframe(fleets_x,use_container_width=True,hide_index=True)
        if not aircraft_x.empty:
            st.markdown("#### Aircraft")
            st.dataframe(aircraft_x,use_container_width=True,hide_index=True)
        cov_x=fleet_coverage[fleet_coverage["Company ID"].fillna("").astype(str).isin(selected_ids)].copy()
        if not cov_x.empty:
            st.markdown("#### Coverage & gaps")
            st.dataframe(cov_x,use_container_width=True,hide_index=True)
    with tab4:
        inv_x=model_investments[model_investments["Company ID"].fillna("").astype(str).isin(selected_ids)].copy()
        ev_x=strategic_events[strategic_events["Subject Entity ID"].fillna("").astype(str).isin(selected_ids)].copy()
        if not inv_x.empty:
            st.markdown("#### Investment / capex")
            st.dataframe(format_dates_for_display(inv_x),use_container_width=True,hide_index=True)
        if not ev_x.empty:
            st.markdown("#### Strategic events")
            st.dataframe(format_dates_for_display(sort_latest(ev_x)),use_container_width=True,hide_index=True)
        if inv_x.empty and ev_x.empty:
            st.info("No investment or strategic-event rows are captured yet for this group.")
    with tab5:
        rel_x=model_relationships[
            model_relationships["Source Entity"].fillna("").astype(str).isin(selected_ids) |
            model_relationships["Target Entity"].fillna("").astype(str).isin(selected_ids)
        ].copy()
        if not rel_x.empty:
            rel_x["Source"] = rel_x["Source Entity"].map(COMPANY_NAME).fillna(rel_x["Source Entity"])
            rel_x["Target"] = rel_x["Target Entity"].map(COMPANY_NAME).fillna(rel_x["Target Entity"])
            cols=[c for c in ["Source","Relationship","Target","As Of","Confidence","Source ID"] if c in rel_x.columns]
            st.dataframe(format_dates_for_display(rel_x[cols]),use_container_width=True,hide_index=True)
        else:
            st.info("No corporate relationship edges are captured yet for this group.")

# ---------------- Leadership ----------------
elif page == "Leadership":
    masthead("Leadership & People", "Current and historical leadership roles across the companies in the P&C trade-system model.")
    lr=leadership_roles.copy()
    lr["Person"] = lr["Person ID"].astype(str).map(PERSON_NAME)
    lr["Company"] = lr["Company ID"].astype(str).map(COMPANY_NAME)
    c1,c2,c3=st.columns(3)
    with c1: lr=filter_select(lr,"Company","Company")
    with c2: lr=filter_select(lr,"Status","Status")
    with c3: lr=filter_select(lr,"Scope","Scope")
    st.metric("Leadership roles",len(lr))
    cols=[c for c in ["Person","Company","Title","Scope","Status","Effective From","Effective To","Source ID"] if c in lr.columns]
    st.dataframe(format_dates_for_display(lr[cols]),use_container_width=True,hide_index=True)

# ---------------- Vessels & Fleets ----------------
elif page == "Vessels & Fleets":
    masthead("Vessels & Fleet Intelligence", "Individual vessels, fleet summaries, ownership/operator relationships, charter exposure, newbuilds and coverage completeness.")
    x=model_vessels.copy()
    x["Owner"] = x["Owner Company ID"].astype(str).map(COMPANY_NAME).fillna(x["Owner Company ID"].astype(str))
    x["Operator"] = x["Operator Company ID"].astype(str).map(COMPANY_NAME).fillna(x["Operator Company ID"].astype(str))
    q=st.text_input("Search vessel / IMO / company",placeholder="NAVIG8 MESSI, BYD Shenzhen, 9993963, Bahri...")
    if q: x=smart_text_search(x,q,require_all=False,limit=1000).drop(columns=["_pc_score","_pc_terms"],errors="ignore")
    c1,c2,c3,c4=st.columns(4)
    with c1: x=filter_select(x,"Vessel Type","Vessel type")
    with c2: x=filter_select(x,"Owner","Owner")
    with c3: x=filter_select(x,"Operator","Operator")
    with c4: x=filter_select(x,"Status","Status")
    imo_count=int(x["IMO"].fillna("").astype(str).str.strip().ne("").sum()) if "IMO" in x.columns else 0
    imo_pct=(imo_count/len(x)*100) if len(x) else 0
    a,b,c,d,e=st.columns(5)
    a.metric("Individual records",len(x))
    b.metric("With IMO",imo_count)
    c.metric("IMO coverage",f"{imo_pct:.1f}%")
    d.metric("Owners represented",x["Owner"].replace("nan",pd.NA).dropna().nunique())
    e.metric("Vessel types",x["Vessel Type"].nunique() if "Vessel Type" in x.columns else 0)
    cols=[c for c in ["Vessel Name","IMO","Owner","Operator","Vessel Type","Subtype / Class","Flag","Year Built","DWT","Capacity","Fuel / Propulsion","Status","Completeness Note"] if c in x.columns]
    st.dataframe(x[cols],use_container_width=True,hide_index=True)

    st.markdown("### Fleet coverage")
    cov=fleet_coverage.copy(); cov["Company"]=cov["Company ID"].astype(str).map(COMPANY_NAME)
    st.dataframe(cov,use_container_width=True,hide_index=True)
    with st.expander("IMO coverage by owner",expanded=False):
        st.dataframe(imo_coverage,use_container_width=True,hide_index=True)
    with st.expander("Cross-regional fleet discovery / staging",expanded=False):
        st.dataframe(global_vessel_staging,use_container_width=True,hide_index=True)

    vessel_options=x["Vessel Name"].dropna().astype(str).tolist()[:2000]
    if vessel_options:
        selected=st.selectbox("Inspect vessel relationships / build history",[""]+vessel_options)
        if selected:
            vid=str(x[x["Vessel Name"].astype(str)==selected].iloc[0]["Vessel ID"])
            vi=vessel_identifiers[vessel_identifiers["Vessel ID"].astype(str)==vid].copy()
            if not vi.empty:
                st.markdown("#### Vessel identifiers")
                st.dataframe(vi,use_container_width=True,hide_index=True)
            iv=vessel_imo_verification[vessel_imo_verification["Vessel ID"].astype(str)==vid].copy()
            if not iv.empty:
                st.markdown("#### IMO verification")
                st.dataframe(iv[[c for c in ["Vessel Name","IMO","Verification Status","Confidence","Verified As Of","IMO Verification URL","Notes"] if c in iv.columns]],use_container_width=True,hide_index=True)
            ve=vessel_evidence[vessel_evidence["Vessel ID"].astype(str)==vid].copy()
            if not ve.empty:
                st.markdown("#### Evidence & freshness")
                st.dataframe(format_dates_for_display(ve),use_container_width=True,hide_index=True)
            vr=vessel_relationships[vessel_relationships["Vessel ID"].astype(str)==vid].copy()
            if not vr.empty:
                vr["Company"]=vr["Company ID"].astype(str).map(COMPANY_NAME)
                st.markdown("#### Commercial relationships"); st.dataframe(vr,use_container_width=True,hide_index=True)
            vb=vessel_build_records[vessel_build_records["Vessel ID"].astype(str)==vid]
            if not vb.empty:
                st.markdown("#### Build record"); st.dataframe(format_dates_for_display(vb),use_container_width=True,hide_index=True)
            vc=vessel_contracts[vessel_contracts["Vessel ID"].astype(str)==vid]
            if not vc.empty:
                st.markdown("#### Contracts / charter exposure"); st.dataframe(vc,use_container_width=True,hide_index=True)

# ---------------- Vehicle Logistics ----------------
elif page == "Vehicle Logistics":
    masthead("Vehicle Logistics & Car Carriers", "Automaker-controlled export fleets, PCTCs, Ro-Ro capacity, charter relationships, shipyards and vehicle-logistics exposure.")
    vehicle_mask = model_vessels["Vessel Type"].astype(str).str.contains("PCTC|Ro-Ro|RoCon|car carrier",case=False,na=False,regex=True)
    vx=model_vessels[vehicle_mask].copy()
    vx["Owner"]=vx["Owner Company ID"].astype(str).map(COMPANY_NAME).fillna(vx["Owner Company ID"].astype(str))
    vx["Operator"]=vx["Operator Company ID"].astype(str).map(COMPANY_NAME).fillna(vx["Operator Company ID"].astype(str))
    a,b,c=st.columns(3); a.metric("Individual vehicle/Ro-Ro vessels",len(vx)); b.metric("BYD dedicated fleet",int(vx["Vessel Name"].astype(str).str.startswith("BYD ").sum())); c.metric("Vehicle/Ro-Ro companies",pd.concat([vx["Owner"],vx["Operator"]]).replace("nan",pd.NA).dropna().nunique())
    st.dataframe(vx[[c for c in ["Vessel Name","IMO","Owner","Operator","Vessel Type","Capacity","Year Built","Fuel / Propulsion","Status"] if c in vx.columns]],use_container_width=True,hide_index=True)
    st.markdown("### Vehicle-related orders / build records")
    vo=fleet_orders[fleet_orders["Asset / Vessel Type"].astype(str).str.contains("PCTC|RoCon|Ro-Ro|car",case=False,na=False,regex=True)]
    st.dataframe(format_dates_for_display(vo),use_container_width=True,hide_index=True)

# ---------------- Ferry Systems ----------------
elif page == "Ferry Systems":
    masthead(
        "Global Ferry Systems",
        "Passenger, vehicle and freight ferry networks as operating ecosystems — operator, vessel, route, terminal, reliability, delays, cancellations and wider corridor impacts."
    )

    fs=ferry_systems.copy()
    r1,r2=st.columns(2)
    with r1: fs=filter_select(fs,"Region","Region")
    with r2: fs=filter_select(fs,"Country / Jurisdiction","Country / jurisdiction")

    visible_ids=set(fs["System ID"].astype(str)) if "System ID" in fs.columns else set()
    fr=ferry_routes[ferry_routes["System ID"].astype(str).isin(visible_ids)].copy()
    ft=ferry_terminals[ferry_terminals["System ID"].astype(str).isin(visible_ids)].copy()
    fv=ferry_vessel_staging[ferry_vessel_staging["System ID"].astype(str).isin(visible_ids)].copy()
    fo=ferry_service_observations[ferry_service_observations["System ID"].astype(str).isin(visible_ids)].copy()
    fp=ferry_performance[ferry_performance["System ID"].astype(str).isin(visible_ids)].copy()
    fstat=ferry_fleet_status[ferry_fleet_status["System ID"].astype(str).isin(visible_ids)].copy()

    system_name=dict(zip(ferry_systems["System ID"].astype(str),ferry_systems["System Name"].astype(str)))
    for dfx in [fr,ft,fv,fo,fp,fstat]:
        if "System ID" in dfx.columns:
            dfx["System"]=dfx["System ID"].astype(str).map(system_name).fillna(dfx["System ID"].astype(str))

    a,b,c,d=st.columns(4)
    a.metric("Systems",len(fs))
    b.metric("Route seeds",len(fr))
    c.metric("Terminals",len(ft))
    d.metric("Vessel staging records",len(fv))

    st.caption("Ferry-vessel staging is deliberately separate from the canonical vessel register until IMO / national identifiers are resolved. Domestic ferry fleets may require USCG, Canadian or national registry numbers in addition to IMO.")

    tabs=st.tabs(["Systems","Routes & Terminals","Vessels & IDs","Reliability & Disruptions","Fleet Status"])
    with tabs[0]:
        st.dataframe(fs,use_container_width=True,hide_index=True)
    with tabs[1]:
        st.markdown("#### Ferry routes")
        st.dataframe(fr,use_container_width=True,hide_index=True)
        st.markdown("#### Ferry terminals")
        st.dataframe(ft,use_container_width=True,hide_index=True)
    with tabs[2]:
        st.markdown("#### Ferry vessel research staging")
        st.dataframe(fv,use_container_width=True,hide_index=True)
        st.markdown("#### Canonical vessel identifier schema")
        id_cols=[c for c in ["Vessel Name","IMO","MMSI","USCG Official Number","Canadian Official Number","National Registry Number","Call Sign","Flag","Identifier Status"] if c in vessel_identifiers.columns]
        st.dataframe(vessel_identifiers[id_cols].head(500),use_container_width=True,hide_index=True)
    with tabs[3]:
        st.markdown("#### Sailing / service observations")
        st.dataframe(format_dates_for_display(fo),use_container_width=True,hide_index=True)
        st.markdown("#### Reliability / performance")
        st.dataframe(format_dates_for_display(fp),use_container_width=True,hide_index=True)
        with st.expander("Delay / cancellation cause taxonomy",expanded=False):
            st.dataframe(ferry_disruption_taxonomy,use_container_width=True,hide_index=True)
    with tabs[4]:
        st.dataframe(format_dates_for_display(fstat),use_container_width=True,hide_index=True)

# ---------------- Great Lakes System ----------------
elif page == "Great Lakes System":
    masthead(
        "Great Lakes–St. Lawrence System",
        "A regional operating system linking companies, lakers, ocean carriers, ports, locks, channels, rail, commodity corridors, cruise traffic and disruption dependencies."
    )

    sys_id="SYS_GLSS"
    rs=regional_systems[regional_systems["System ID"].astype(str)==sys_id].copy()
    gp=great_lakes_ports[great_lakes_ports["System ID"].astype(str)==sys_id].copy()
    cf=company_system_footprints[company_system_footprints["System ID"].astype(str)==sys_id].copy()
    sn=system_nodes[system_nodes["System ID"].astype(str)==sys_id].copy()
    sl=system_links[system_links["System ID"].astype(str)==sys_id].copy()
    gv=great_lakes_vessel_staging.copy()
    gc=great_lakes_cargo_corridors[great_lakes_cargo_corridors["System ID"].astype(str)==sys_id].copy()
    cr=great_lakes_cruise.copy()
    dep=system_dependencies[system_dependencies["System ID"].astype(str)==sys_id].copy()

    comp_name=dict(zip(companies["Company ID"].astype(str),companies["Company"].astype(str)))
    if "Company ID" in cf.columns:
        cf["Company"]=cf["Company ID"].astype(str).map(comp_name).fillna(cf["Company ID"].astype(str))
    if "Company ID" in gv.columns:
        gv["Company"]=gv["Company ID"].astype(str).map(comp_name).fillna(gv["Company ID"].astype(str))
    if "Company ID" in cr.columns:
        cr["Company"]=cr["Company ID"].astype(str).map(comp_name).fillna(cr["Company ID"].astype(str))

    a,b,c,d=st.columns(4)
    a.metric("Core port seeds",len(gp))
    b.metric("Company footprints",len(cf))
    c.metric("Critical nodes",len(sn))
    d.metric("Cruise ships (2026 seed)",len(cr))

    st.caption("This is the architecture pass before automated data collection. Staging tables remain separate from canonical entities until identifiers and ownership are resolved.")

    tabs=st.tabs(["System","Companies","Ports","Locks & Channels","Cargo Corridors","Vessels","Cruise","Dependencies & Risks"])

    with tabs[0]:
        st.dataframe(rs,use_container_width=True,hide_index=True)
        st.markdown("#### System links")
        st.dataframe(sl,use_container_width=True,hide_index=True)

    with tabs[1]:
        st.markdown("#### Company footprints")
        st.dataframe(cf,use_container_width=True,hide_index=True)
        st.caption("Cross-regional footprints are intentional: for example, CSL's Great Lakes division remains connected to CSL Australia/Asia and the wider CSL Group.")

    with tabs[2]:
        q=st.text_input("Filter Great Lakes / St. Lawrence ports",key="gl_port_search")
        show=gp.copy()
        if q:
            mask=show.astype(str).apply(lambda col: col.str.contains(q,case=False,na=False)).any(axis=1)
            show=show[mask]
        st.dataframe(show,use_container_width=True,hide_index=True)

    with tabs[3]:
        st.markdown("#### Critical navigation nodes")
        st.dataframe(sn,use_container_width=True,hide_index=True)
        st.markdown("#### Navigation disruption taxonomy")
        st.dataframe(great_lakes_disruptions,use_container_width=True,hide_index=True)

    with tabs[4]:
        st.dataframe(gc,use_container_width=True,hide_index=True)

    with tabs[5]:
        st.dataframe(gv,use_container_width=True,hide_index=True)
        st.caption("Great Lakes vessel staging is promoted into the canonical Vessels table only after IMO / USCG / Canadian official identifiers are resolved. Historical regulator identities remain visibly marked until current operating status is refreshed.")
        with st.expander("Cross-regional vessel discovery",expanded=False):
            st.dataframe(global_vessel_staging,use_container_width=True,hide_index=True)

    with tabs[6]:
        st.dataframe(cr,use_container_width=True,hide_index=True)

    with tabs[7]:
        st.markdown("#### Explicit dependency edges")
        st.dataframe(dep,use_container_width=True,hide_index=True)
        st.markdown("#### Research / collection priorities")
        rq_gl=research_queue[
            research_queue.astype(str).apply(
                lambda col: col.str.contains("Great Lakes|CSL Group|CSL Canada|Algoma|Interlake|locks / canals / channels",case=False,na=False)
            ).any(axis=1)
        ].copy()
        st.dataframe(rq_gl,use_container_width=True,hide_index=True)

# ---------------- Tanker Intelligence ----------------
elif page == "Tanker Intelligence":
    masthead(
        "Tanker & VLCC Intelligence",
        "Ownership, beneficial control, operating fleets, sanctions/restrictions, tradeability, fleet transactions and corridor exposure."
    )

    tf=tanker_fleet_universe.copy()
    rk=fleet_ranking_snapshots.copy()
    vrx=vessel_restrictions.copy()
    tax=tradeability_assessments.copy()
    vtx=vessel_transactions.copy()
    tcx=tanker_corridor_exposure.copy()

    # Hide schema/template rows from operating views.
    if "Restriction ID" in vrx.columns:
        vrx=vrx[vrx["Restriction ID"].astype(str)!="VR_TEMPLATE"]
    if "Assessment ID" in tax.columns:
        tax=tax[tax["Assessment ID"].astype(str)!="TA_TEMPLATE"]
    if "Transaction ID" in vtx.columns:
        vtx=vtx[vtx["Transaction ID"].astype(str)!="VTX_TEMPLATE"]

    a,b,c,d=st.columns(4)
    a.metric("Tanker fleet universes",len(tf))
    b.metric("VLCC ranking entries",len(rk))
    c.metric("Restriction records",len(vrx))
    d.metric("Corridor exposure records",len(tcx))

    st.caption(
        "Fleet rankings are time- and methodology-bounded. Owned, operated, beneficially controlled, managed, chartered and commercially deployed tonnage remain separate relationships."
    )

    tabs=st.tabs(["VLCC Rankings","Fleet Universe","Restrictions","Tradeability","Transactions","Corridor Exposure","Research Coverage"])
    with tabs[0]:
        show=rk.copy()
        if "Published Rank" in show.columns:
            show["Published Rank"]=pd.to_numeric(show["Published Rank"],errors="coerce")
            show=show.sort_values("Published Rank",na_position="last")
        st.dataframe(show,use_container_width=True,hide_index=True)
    with tabs[1]:
        st.dataframe(tf,use_container_width=True,hide_index=True)
    with tabs[2]:
        st.dataframe(vrx,use_container_width=True,hide_index=True)
    with tabs[3]:
        st.dataframe(tax,use_container_width=True,hide_index=True)
    with tabs[4]:
        st.dataframe(vtx,use_container_width=True,hide_index=True)
    with tabs[5]:
        st.dataframe(tcx,use_container_width=True,hide_index=True)
    with tabs[6]:
        tq=research_queue[
            research_queue.astype(str).apply(
                lambda col: col.str.contains("VLCC|tanker|tradeability|sanctions / restrictions|vessel transactions|corridor exposure",case=False,na=False)
            ).any(axis=1)
        ].copy()
        st.dataframe(tq,use_container_width=True,hide_index=True)

# ---------------- Energy Shipping ----------------
elif page == "Energy Shipping":
    masthead("Energy Shipping", "LNG, LPG, crude, product and chemical shipping across Gulf national champions, Qatar LNG, and global energy-major charter networks.")
    energy_ids=["COMP_ADNOC_LS","COMP_NAVIG8","COMP_AW_SHIPPING","COMP_BAHRI","COMP_NAKILAT","COMP_MILAHA","COMP_QATARENERGY","COMP_BP_SHIPPING","COMP_CHEVRON_SHIPPING","COMP_EXXON","COMP_SEARIVER","COMP_SINOKOR","COMP_CMES","COMP_COSCO_ENERGY","COMP_FRONTLINE","COMP_MARAN_TANKERS","COMP_MOL","COMP_DHT","COMP_NYK","COMP_ASYAD_SHIPPING","COMP_NITC"]
    energy_names=[COMPANY_NAME.get(i,i) for i in energy_ids]
    selected=st.selectbox("Energy shipping ecosystem",["All"]+energy_names)
    ids=energy_ids if selected=="All" else [energy_ids[energy_names.index(selected)]]
    ev=model_vessels[model_vessels["Owner Company ID"].astype(str).isin(ids) | model_vessels["Operator Company ID"].astype(str).isin(ids)].copy()
    ev["Owner"]=ev["Owner Company ID"].astype(str).map(COMPANY_NAME).fillna(ev["Owner Company ID"].astype(str)); ev["Operator"]=ev["Operator Company ID"].astype(str).map(COMPANY_NAME).fillna(ev["Operator Company ID"].astype(str))
    fp=fleet_portfolios[fleet_portfolios["Company ID"].astype(str).isin(ids)].copy(); fp["Company"]=fp["Company ID"].astype(str).map(COMPANY_NAME)
    fo=fleet_orders[fleet_orders["Buyer / Operator Company ID"].astype(str).isin(ids)].copy(); fo["Company"]=fo["Buyer / Operator Company ID"].astype(str).map(COMPANY_NAME)
    a,b,c,d=st.columns(4); a.metric("Individual vessels",len(ev)); b.metric("Fleet summary rows",len(fp)); c.metric("Order / build rows",len(fo)); d.metric("Companies",len(ids))
    tabs=st.tabs(["Fleet","Orders","Contracts","Coverage"])
    with tabs[0]:
        st.dataframe(fp,use_container_width=True,hide_index=True)
        st.dataframe(ev[[c for c in ["Vessel Name","IMO","Owner","Operator","Vessel Type","DWT","Capacity","Fuel / Propulsion","Status"] if c in ev.columns]],use_container_width=True,hide_index=True)
    with tabs[1]: st.dataframe(format_dates_for_display(fo),use_container_width=True,hide_index=True)
    with tabs[2]:
        vc=vessel_contracts[vessel_contracts["Company ID"].astype(str).isin(ids)]
        st.dataframe(vc,use_container_width=True,hide_index=True)
    with tabs[3]:
        fc=fleet_coverage[fleet_coverage["Company ID"].astype(str).isin(ids)].copy(); fc["Company"]=fc["Company ID"].astype(str).map(COMPANY_NAME)
        st.dataframe(fc,use_container_width=True,hide_index=True)

# ---------------- Ports & Terminals ----------------
elif page == "Ports & Terminals":
    masthead("Ports, Terminals & Infrastructure", "Canonical port/operator records combined with terminal assets, investment and infrastructure works.")
    p=model_ports.copy(); a=model_assets.copy()
    c1,c2=st.columns(2)
    with c1: p=filter_select(p,"Country","Country")
    with c2: p=filter_select(p,"Operator","Operator")
    st.metric("Port / facility records",len(p))
    mp=map_points(p,location_cols=("Port / Facility",),country_col="Country",layer="Port / facility")
    if not mp.empty: st.map(mp,latitude="lat",longitude="lon",use_container_width=True)
    st.dataframe(p,use_container_width=True,hide_index=True)
    st.markdown("### Infrastructure and investment")
    t1,t2,t3=st.tabs(["Assets","Investments","Infrastructure works"])
    with t1: st.dataframe(a,use_container_width=True,hide_index=True)
    with t2: st.dataframe(format_dates_for_display(model_investments),use_container_width=True,hide_index=True)
    with t3: st.dataframe(format_dates_for_display(infra_works),use_container_width=True,hide_index=True)

# ---------------- Infrastructure & Inland Logistics ----------------
elif page == "Infrastructure & Inland Logistics":
    masthead(
        "Infrastructure Capital & Inland Logistics",
        "Who owns, finances, develops and connects ports, economic zones, logistics real estate, dry ports and inland trade infrastructure."
    )

    invu=infrastructure_investors.copy()
    hold=infrastructure_holdings.copy()
    deals=infrastructure_deals.copy()
    zones=economic_zones.copy()
    lre=logistics_real_estate.copy()
    hubs=dry_ports_inland_hubs.copy()
    conns=infrastructure_connections.copy()

    c1,c2,c3,c4=st.columns(4)
    with c1:
        if "Investor Type" in invu.columns:
            invu=filter_select(invu,"Investor Type","Investor type")
    with c2:
        if "Canonical Status" in invu.columns:
            invu=filter_select(invu,"Canonical Status","Investor status")
    with c3:
        if "Asset Class" in deals.columns:
            deals=filter_select(deals,"Asset Class","Deal asset class")
    with c4:
        if "Country / Region" in deals.columns:
            deals=filter_select(deals,"Country / Region","Deal geography")

    a,b,c,d,e=st.columns(5)
    a.metric("Investor universe",len(invu))
    b.metric("Holdings",len(hold))
    c.metric("Deals",len(deals))
    d.metric("Economic / free zones",len(zones))
    e.metric("Dry / inland hubs",len(hubs))

    st.caption(
        "Financial ownership, economic interest, operating control, concessions, fund/platform ownership and corridor connectivity are modeled separately. Proposed or failed deals do not become current holdings."
    )

    tabs=st.tabs([
        "Investors",
        "Holdings",
        "Deals",
        "Economic Zones",
        "Logistics Real Estate",
        "Dry Ports / Inland Hubs",
        "Connections",
    ])

    with tabs[0]:
        cols=[c for c in [
            "Investor / Platform","Investor Type","Parent / Manager","HQ Country","Core Strategies",
            "Port / Terminal Exposure","Logistics Real Estate Exposure","Economic Zone / Inland Exposure",
            "Current Scale / Notes","Canonical Status","Research Priority","Verified As Of"
        ] if c in invu.columns]
        st.dataframe(invu[cols] if cols else invu,use_container_width=True,hide_index=True)

    with tabs[1]:
        h=hold.copy()
        if "Status" in h.columns:
            h=sort_latest(h,("Effective From",))
        st.dataframe(format_dates_for_display(h),use_container_width=True,hide_index=True)

    with tabs[2]:
        d=deals.copy()
        if "Reported Value" in d.columns:
            d["Reported Value"]=pd.to_numeric(d["Reported Value"],errors="coerce")
        show_cols=[c for c in [
            "Announced Date","Completed / Effective Date","Investor / Buyer IDs","Co-Investor / Partner IDs",
            "Target / Asset","Asset Class","Country / Region","Deal Type","Equity %","Reported Value","Currency",
            "Operating Control","Status","Regulatory / Political Status","Source URL"
        ] if c in d.columns]
        st.dataframe(format_dates_for_display(sort_latest(d,("Completed / Effective Date","Announced Date"))[show_cols]),use_container_width=True,hide_index=True)

    with tabs[3]:
        st.dataframe(zones,use_container_width=True,hide_index=True)

    with tabs[4]:
        st.dataframe(lre,use_container_width=True,hide_index=True)

    with tabs[5]:
        hc=hubs.copy()
        c1,c2,c3=st.columns(3)
        with c1:
            if "Country" in hc.columns:
                hc=filter_select(hc,"Country","Hub country")
        with c2:
            if "Hub Type" in hc.columns:
                hc=filter_select(hc,"Hub Type","Hub type")
        with c3:
            if "Status" in hc.columns:
                hc=filter_select(hc,"Status","Hub status")
        st.dataframe(hc,use_container_width=True,hide_index=True)

    with tabs[6]:
        st.dataframe(conns,use_container_width=True,hide_index=True)

# ---------------- Shipyards & Orders ----------------
elif page == "Shipyards & Orders":
    masthead("Shipyards & Fleet Orders", "Where merchant, automotive, energy and naval fleets are being built — by company, yard, country and delivery window.")
    fo=fleet_orders.copy(); fo["Buyer / Operator"]=fo["Buyer / Operator Company ID"].astype(str).map(COMPANY_NAME).fillna(fo["Buyer / Operator Company ID"].astype(str))
    c1,c2,c3=st.columns(3)
    with c1: fo=filter_select(fo,"Buyer / Operator","Buyer / operator")
    with c2: fo=filter_select(fo,"Build Country","Build country")
    with c3: fo=filter_select(fo,"Status","Status")
    a,b,c=st.columns(3); a.metric("Order / build records",len(fo)); b.metric("Shipyards",model_shipyards["Shipyard"].nunique()); c.metric("Build countries",fo["Build Country"].replace("",pd.NA).dropna().nunique())
    left,right=st.columns(2)
    with left: render_count_chart(fo,"Buyer / Operator","Orders by buyer/operator",top=12)
    with right: render_count_chart(fo,"Build Country","Orders by build country",top=12)
    st.dataframe(format_dates_for_display(fo),use_container_width=True,hide_index=True)
    st.markdown("### Shipyard registry")
    st.dataframe(model_shipyards,use_container_width=True,hide_index=True)

# ---------------- Events & Disruptions ----------------
elif page == "Events & Disruptions":
    masthead("Events & Disruptions", "One cross-domain event layer for conflict, piracy, port incidents, weather, natural hazards, labour action, protest, civil unrest, cyber and transport accidents.")
    x=event_observations.copy()
    c1,c2,c3,c4=st.columns(4)
    with c1: x=filter_select(x,"Event Family","Event family")
    with c2: x=filter_select(x,"Mode","Mode")
    with c3: x=filter_select(x,"Country","Country")
    with c4: x=filter_select(x,"Severity","Severity")
    a,b,c,d=st.columns(4); a.metric("Observations",len(x)); b.metric("Event families",x["Event Family"].nunique()); c.metric("Countries",x["Country"].replace("",pd.NA).dropna().nunique()); d.metric("Linked entity records",len(event_entity_links))
    mp=map_points(x,location_cols=("Location",),country_col="Country",layer="Event")
    if not mp.empty: st.map(mp,latitude="lat",longitude="lon",use_container_width=True)
    render_monthly_chart([("Events",x,("Date",))],"Events over time")
    render_count_chart(x,"Event Family","Event families",top=15)
    cols=[c for c in ["Date","Event Family","Event Type","Mode","Country","Location","Subject Name","Actor / Attribution","Operational Impact","Trade Impact","Severity","Confidence","Source Dataset"] if c in x.columns]
    st.dataframe(format_dates_for_display(sort_latest(x)[cols]),use_container_width=True,hide_index=True)
    with st.expander("Cross-domain operational disruptions",expanded=False): st.dataframe(format_dates_for_display(external_disruptions),use_container_width=True,hide_index=True)

# ---------------- Weather & Labour ----------------
elif page == "Weather & Labour":
    masthead(
        "Weather, Labour & Protest Disruptions",
        "Operationally significant weather, natural hazards, strikes, work-to-rule actions, protests and civil disruption affecting trade and movement."
    )
    x=weather_labour_events.copy()
    c1,c2,c3,c4=st.columns(4)
    with c1: x=filter_select(x,"Event Family","Event family")
    with c2: x=filter_select(x,"Mode","Mode")
    with c3: x=filter_select(x,"Country / Countries","Country / geography")
    with c4: x=filter_select(x,"Severity","Severity")

    weather_mask=x["Event Family"].astype(str).isin(["Weather","Natural Hazard"]) if "Event Family" in x.columns else pd.Series(False,index=x.index)
    labour_mask=x["Event Family"].astype(str).isin(["Labour / Industrial Action","Protest / Labour"]) if "Event Family" in x.columns else pd.Series(False,index=x.index)
    a,b,c,d=st.columns(4)
    a.metric("Focused events",len(x))
    b.metric("Weather / natural",int(weather_mask.sum()))
    c.metric("Labour / protest",int(labour_mask.sum()))
    d.metric("Forward watches",len(disruption_watch))

    st.caption("Inclusion requires an operational effect on ports, shipping, inland waterways, aviation, rail, ferries, borders, industrial production or cargo movement. Threatened action stays in the watch table until it occurs.")

    tabs=st.tabs(["Observed Events","Forward Watch","Impacts"])
    with tabs[0]:
        render_count_chart(x,"Event Family","Disruptions by family",top=10)
        render_monthly_chart([("Weather/Labour",x,("Date",))],"Disruptions over time")
        cols=[c for c in ["Date","Event Family","Event Type","Mode","Country / Countries","Location","Title","Status","Severity","Time Horizon","Operational Impact","Trade / Commercial Impact","Primary Source URL"] if c in x.columns]
        st.dataframe(format_dates_for_display(sort_latest(x)[cols]),use_container_width=True,hide_index=True)
    with tabs[1]:
        st.dataframe(format_dates_for_display(disruption_watch),use_container_width=True,hide_index=True)
    with tabs[2]:
        ids=set(x["External Event ID"].astype(str)) if "External Event ID" in x.columns else set()
        imp=event_impacts[event_impacts["External Event ID"].astype(str).isin(ids)].copy() if "External Event ID" in event_impacts.columns else event_impacts.iloc[0:0].copy()
        st.dataframe(imp,use_container_width=True,hide_index=True)

# ---------------- Corridors ----------------
elif page == "Corridors":
    masthead("Trade Corridors & Chokepoints", "Strategic movement systems linked to companies, vessels, ports, historical events and current disruption.")
    st.dataframe(corridors,use_container_width=True,hide_index=True)
    st.markdown("### Strategic corridor history")
    se=strategic_events.copy()
    st.dataframe(format_dates_for_display(sort_latest(se)),use_container_width=True,hide_index=True)


# ---------------- Maritime Attacks ----------------
elif page == "Maritime Attacks":
    masthead("Maritime Attacks 2026", "Conflict attacks and security incidents affecting merchant shipping across the Gulf, Red Sea and western Indian Ocean.")
    x = attacks.copy()
    c1,c2,c3,c4 = st.columns(4)
    with c1: x = filter_select(x, "Theatre", "Theatre")
    with c2: x = filter_select(x, "Category", "Category")
    with c3: x = filter_select(x, "Vessel Type", "Vessel type")
    with c4: x = filter_select(x, "Flag", "Flag")

    a,b,c,d = st.columns(4)
    a.metric("Matched records", len(x))
    b.metric("Fatalities", int(pd.to_numeric(x.get("Fatalities"), errors="coerce").fillna(0).sum()) if "Fatalities" in x.columns else "—")
    c.metric("Injured", int(pd.to_numeric(x.get("Injured"), errors="coerce").fillna(0).sum()) if "Injured" in x.columns else "—")
    d.metric("Vessels with IMO", int(x["IMO"].fillna("").astype(str).str.strip().ne("").sum()) if "IMO" in x.columns else "—")

    left,right = st.columns([1.35,1])
    with left:
        st.markdown("#### Incident geography")
        render_map(x, location_cols=("Location",), layer="Maritime attack")
    with right:
        render_count_chart(x, "Theatre", "By theatre", top=8)
        render_count_chart(x, "Outcome", "By outcome", top=8)

    render_monthly_chart([("Maritime attacks", x, ("Date",))], "Attacks over time")
    render_evidence_table(x)

# ---------------- Piracy ----------------
elif page == "Piracy & Armed Robbery":
    masthead("Piracy & Armed Robbery 2026", "Hijackings, attempted boardings, suspicious approaches and armed robbery within the 2026 maritime-security picture.")
    x = piracy.copy()
    c1,c2,c3 = st.columns(3)
    with c1: x = filter_select(x, "Theatre", "Theatre")
    with c2: x = filter_select(x, "Outcome", "Outcome")
    with c3: x = filter_select(x, "Confidence", "Confidence")

    a,b,c = st.columns(3)
    a.metric("Matched records", len(x))
    b.metric("Hijacked / captured", int(x["Outcome"].astype(str).str.contains("hijack|capture|held", case=False, na=False, regex=True).sum()) if "Outcome" in x.columns else "—")
    c.metric("Mapped records", len(map_points(x, location_cols=("Location",))))

    left,right = st.columns([1.35,1])
    with left:
        st.markdown("#### Incident geography")
        render_map(x, location_cols=("Location",), layer="Piracy / armed robbery")
    with right:
        render_count_chart(x, "Outcome", "Incident outcome", top=8)
        render_count_chart(x, "Vessel Type", "Vessel types affected", top=8)

    render_monthly_chart([("Piracy / armed robbery", x, ("Date",))], "Piracy activity over time")
    render_evidence_table(x)

# ---------------- UKMTO ----------------
elif page == "UKMTO Warnings":
    masthead("UKMTO Warnings 2026", "Official warning records separated from P&C analytical classification and port relevance.")
    x = ukmto.copy()
    c1,c2,c3 = st.columns(3)
    with c1: x = filter_select(x, "UKMTO Classification", "UKMTO classification")
    with c2: x = filter_select(x, "Analytical Classification", "P&C analytical classification")
    with c3: x = filter_select(x, "Port Relevance", "Port relevance")

    a,b,c = st.columns(3)
    a.metric("Warnings", len(x))
    b.metric("With updates", int(x["Has Update"].astype(str).str.lower().eq("yes").sum()) if "Has Update" in x.columns else "—")
    c.metric("High confidence", int(x["Confidence"].astype(str).str.contains("high", case=False, na=False).sum()) if "Confidence" in x.columns else "—")

    left,right = st.columns(2)
    with left:
        render_count_chart(x, "UKMTO Classification", "Official classifications", top=8)
    with right:
        render_count_chart(x, "Port Relevance", "Operational geography", top=8)

    render_monthly_chart([("UKMTO warnings", x, ("Date",))], "Warnings over time")
    render_evidence_table(x)

# ---------------- Gulf Military Actions ----------------
elif page == "Gulf Military Actions":
    masthead(
        "Gulf Military Maritime Actions 2026",
        "U.S. CENTCOM vessel actions and IMO-confirmed merchant-vessel incidents shown as separate evidence layers within the same operating environment."
    )

    tab1, tab2, tab3 = st.tabs(["Operating picture", "CENTCOM actions", "IMO Gulf incidents"])

    with tab1:
        gulf_pts = []
        for label, frame in [("CENTCOM action", centcom), ("IMO Gulf incident", imo_gulf)]:
            p = map_points(frame, location_cols=("Location",), layer=label)
            if not p.empty:
                gulf_pts.append(p)
        if gulf_pts:
            gp = pd.concat(gulf_pts, ignore_index=True)
            st.map(gp, latitude="lat", longitude="lon", use_container_width=True)
            st.caption("CENTCOM actions and IMO-confirmed merchant-vessel incidents are displayed as separate evidence layers. Map positions are approximate named-location references.")
        render_monthly_chart([
            ("CENTCOM actions", centcom, ("Date",)),
            ("IMO Gulf incidents", imo_gulf, ("Date",)),
        ], "Gulf maritime events over time")

        a,b = st.columns(2)
        with a: render_count_chart(centcom, "Action Type", "CENTCOM action types", top=10)
        with b: render_count_chart(imo_gulf, "Event Class", "IMO event classes", top=10)

    with tab2:
        x = centcom.copy()
        c1,c2,c3 = st.columns(3)
        with c1: x = filter_select(x, "Action Type", "Action type")
        with c2: x = filter_select(x, "Blockade Phase", "Blockade phase")
        with c3: x = filter_select(x, "Flag", "Flag")
        a,b,c = st.columns(3)
        a.metric("Recorded actions", len(x))
        b.metric("Disabled / destroyed", int(x["Outcome"].astype(str).str.contains("disabled|destroyed", case=False, na=False, regex=True).sum()) if "Outcome" in x.columns else "—")
        c.metric("Boarding / custody events", int(x["Action Type"].astype(str).str.contains("board|search|seiz", case=False, na=False, regex=True).sum()) if "Action Type" in x.columns else "—")
        st.markdown("#### Geography")
        render_map(x, location_cols=("Location",), layer="CENTCOM action")
        render_evidence_table(x)

    with tab3:
        y = imo_gulf.copy()
        c1,c2 = st.columns(2)
        with c1: y = filter_select(y, "Event Class", "Event class")
        with c2: y = filter_select(y, "Known / Assessed Actor", "Known / assessed actor")
        st.metric("IMO-confirmed records", len(y))
        st.markdown("#### Geography")
        render_map(y, location_cols=("Location",), layer="IMO Gulf incident")
        render_evidence_table(y)
        st.caption("IMO incident descriptions are kept separate from actor attribution. Assessed-actor fields are analytical context, not IMO attribution.")

# ---------------- Port Incidents ----------------
elif page == "Port Incidents":
    masthead("Global Port & Terminal Incidents 2026", "Operational, accident, conflict and infrastructure events affecting ports and terminals.")
    x = ports.copy()
    c1,c2,c3,c4 = st.columns(4)
    with c1: x = filter_select(x,"Region","Region")
    with c2: x = filter_select(x,"Country","Country")
    with c3: x = filter_select(x,"Incident Category","Category")
    with c4: x = filter_select(x,"Severity","Severity")

    a,b,c,d = st.columns(4)
    a.metric("Incidents",len(x))
    b.metric("Conflict-related",int(x["Conflict-Related"].astype(str).str.lower().eq("yes").sum()) if "Conflict-Related" in x.columns else "—")
    c.metric("Fatalities",int(pd.to_numeric(x["Fatalities"],errors="coerce").fillna(0).sum()) if "Fatalities" in x.columns else "—")
    d.metric("Injuries",int(pd.to_numeric(x["Injuries"],errors="coerce").fillna(0).sum()) if "Injuries" in x.columns else "—")

    left,right = st.columns([1.35,1])
    with left:
        st.markdown("#### Port incident geography")
        render_map(x, location_cols=("Port / Location",), country_col="Country", layer="Port incident")
    with right:
        render_count_chart(x, "Incident Category", "Incident categories", top=10)
        render_count_chart(x, "Country", "Countries with most records", top=10)

    render_monthly_chart([("Port incidents", x, ("Date",))], "Port incidents over time")
    render_evidence_table(x)

# ---------------- Port Investment ----------------
elif page == "Port Investment":
    masthead("Port Investment & Commercial Opportunities 2026", "Capital deployment, project stage and procurement or entry points across global port infrastructure.")
    x = invest.copy()
    c1,c2,c3 = st.columns(3)
    with c1: x = filter_select(x,"Region","Region")
    with c2: x = filter_select(x,"Country","Country")
    with c3: x = filter_select(x,"Project / Tender Stage","Stage")

    value = pd.to_numeric(x.get("Converted Value (USD)"),errors="coerce") if "Converted Value (USD)" in x.columns else pd.Series(dtype=float)
    a,b,c = st.columns(3)
    a.metric("Opportunities",len(x))
    b.metric("Disclosed value",fmt_money(value.sum()))
    c.metric("Countries",x["Country"].nunique() if "Country" in x.columns else "—")

    left,right = st.columns([1.2,1])
    with left:
        st.markdown("#### Investment geography")
        render_map(x, location_cols=("Port / Location",), country_col="Country", layer="Port investment")
    with right:
        if "Country" in x.columns and "Converted Value (USD)" in x.columns:
            by_country = x.assign(_value=pd.to_numeric(x["Converted Value (USD)"], errors="coerce")).groupby("Country")["_value"].sum().dropna().sort_values().tail(10)
            if not by_country.empty:
                st.markdown("#### Disclosed value by country")
                st.bar_chart(by_country, use_container_width=True)
        render_count_chart(x, "Project / Tender Stage", "Project stage", top=10)

    render_evidence_table(x, preferred=("Source Date",))

# ---------------- Naval & Shipbuilding ----------------
elif page == "Naval & Shipbuilding":
    masthead(
        "Naval, Coast Guard & Shipbuilding Intelligence 2026",
        "Naval and coast-guard vessel contracts, transfers, deliveries, shipyard acquisitions and industrial-capacity moves with commercial and strategic relevance."
    )

    tab1, tab2 = st.tabs(["Shipbuilding & fleet programs", "Shipyard industrial moves"])

    with tab1:
        x = naval_build.copy()
        c1,c2,c3,c4 = st.columns(4)
        with c1: x = filter_select(x, "Customer Country", "Customer country")
        with c2: x = filter_select(x, "Transaction / Event Type", "Event type")
        with c3: x = filter_select(x, "New / Used", "New / used")
        with c4: x = filter_select(x, "Build Country", "Build country")

        low = pd.to_numeric(x.get("USD Value Low"), errors="coerce") if "USD Value Low" in x.columns else pd.Series(dtype=float)
        qty = pd.to_numeric(x.get("Quantity"), errors="coerce") if "Quantity" in x.columns else pd.Series(dtype=float)

        a,b,c,d = st.columns(4)
        a.metric("Tracked events", len(x))
        b.metric("Vessels / assets", int(qty.fillna(0).sum()) if len(qty) else "—")
        c.metric("Disclosed low value", fmt_money(low.sum()) if len(low) else "—")
        d.metric("Customer countries", x["Customer Country"].nunique() if "Customer Country" in x.columns else "—")

        left,right = st.columns(2)
        with left:
            if "Customer Country" in x.columns and "USD Value Low" in x.columns:
                country_value = x.assign(_value=pd.to_numeric(x["USD Value Low"], errors="coerce")).groupby("Customer Country")["_value"].sum().dropna().sort_values().tail(12)
                if not country_value.empty:
                    st.markdown("#### Programme value by customer country")
                    st.bar_chart(country_value, use_container_width=True)
            render_count_chart(x, "Transaction / Event Type", "Event types", top=10)

        with right:
            if "Customer Country" in x.columns and "Quantity" in x.columns:
                country_qty = x.assign(_qty=pd.to_numeric(x["Quantity"], errors="coerce")).groupby("Customer Country")["_qty"].sum().dropna().sort_values().tail(12)
                if not country_qty.empty:
                    st.markdown("#### Vessels / assets by customer country")
                    st.bar_chart(country_qty, use_container_width=True)
            render_count_chart(x, "Build Country", "Build countries", top=10)

        render_monthly_chart([("Shipbuilding / industrial events", x, ("2026 Event Date",))], "2026 programme milestones")

        show_cols = [c for c in [
            "2026 Event Date","Original Contract / Decision Date","Customer Country","Customer / Service","Vessel / Program",
            "Transaction / Event Type","New / Used","Quantity","Builder / Seller / Partner",
            "Shipyard / Build Location","Build Country","USD Value Low","USD Value High",
            "2026 Status / Milestone","Expected Delivery / Completion",
            "Industrial / Strategic Relevance","Source URL","Secondary Source"
        ] if c in x.columns]
        with st.expander("Evidence table", expanded=True):
            st.dataframe(format_dates_for_display(sort_latest(x, preferred=("2026 Event Date","Original Contract / Decision Date"))[show_cols]), use_container_width=True, hide_index=True)

    with tab2:
        y = shipyard_moves.copy()
        c1,c2 = st.columns(2)
        with c1: y = filter_select(y, "Country", "Country")
        with c2: y = filter_select(y, "Move Type", "Move type")
        st.metric("Industrial moves", len(y))
        render_count_chart(y, "Country", "Industrial moves by country", top=10)
        render_evidence_table(y)

# ---------------- Black Sea ----------------
elif page == "Black Sea":
    masthead("Black Sea Maritime Database", "Voyages, conflict-affected vessels, port attacks and vessel profiles extracted from the BlackSeaNews maritime database.")

    st.markdown("### Operating picture")
    bs_map = []
    for label, frame, cols in [
        ("Conflict vessel", bs_conflict, ("Location / Port",)),
        ("Port attack", bs_ports, ("Region / Port",)),
    ]:
        p = map_points(frame, location_cols=cols, layer=label)
        if not p.empty:
            bs_map.append(p)
    if bs_map:
        bp = pd.concat(bs_map, ignore_index=True)
        st.map(bp, latitude="lat", longitude="lon", use_container_width=True)
        st.caption("Black Sea positions are approximate port or named-location references; the source records remain authoritative.")

    render_monthly_chart([
        ("Conflict vessels", bs_conflict, ("Date",)),
        ("Port attacks", bs_ports, ("Date",)),
    ], "Black Sea attacks over time")

    left,right = st.columns(2)
    with left: render_count_chart(bs_conflict, "Attack Method", "Vessel attack methods", top=10)
    with right: render_count_chart(bs_ports, "Region / Port", "Port attack concentration", top=10)

    tab0,tab1,tab2,tab3,tab4 = st.tabs(["Source index","Vessel voyages","Conflict vessels","Port attacks","Vessel profiles"])
    with tab0:
        st.dataframe(format_dates_for_display(sort_latest(bs_articles, preferred=("Published",))), use_container_width=True, hide_index=True)
    with tab1:
        q = st.text_input("Search voyages",key="bsvq")
        st.dataframe(format_dates_for_display(text_search(bs_voy,q)),use_container_width=True,hide_index=True)
    with tab2:
        st.dataframe(format_dates_for_display(sort_latest(bs_conflict)),use_container_width=True,hide_index=True)
    with tab3:
        st.dataframe(format_dates_for_display(sort_latest(bs_ports)),use_container_width=True,hide_index=True)
    with tab4:
        st.dataframe(bs_profiles,use_container_width=True,hide_index=True)

# ---------------- Vessel Intelligence ----------------
elif page == "Vessel Intelligence":
    masthead("Vessel Intelligence", "Search operational evidence and the canonical fleet model by vessel name or IMO.")
    q=st.text_input("Vessel name or IMO",placeholder="ETHERA or 9387279")
    if q:
        v0=text_search(model_vessels,q)
        v1=text_search(bs_voy,q)
        v2=text_search(bs_profiles,q)
        v3=text_search(watch,q)
        v4=text_search(centcom,q)
        v5=text_search(imo_gulf,q)
        if len(v0):
            st.markdown("#### Canonical vessel model")
            st.dataframe(v0,use_container_width=True,hide_index=True)
        if len(v1):
            st.markdown("#### Black Sea voyages")
            st.dataframe(format_dates_for_display(v1),use_container_width=True,hide_index=True)
        if len(v2):
            st.markdown("#### Vessel profiles")
            st.dataframe(v2,use_container_width=True,hide_index=True)
        if len(v3):
            st.markdown("#### Sanctions / watchlists")
            st.dataframe(v3,use_container_width=True,hide_index=True)
        if len(v4):
            st.markdown("#### CENTCOM maritime actions")
            st.dataframe(format_dates_for_display(sort_latest(v4)),use_container_width=True,hide_index=True)
        if len(v5):
            st.markdown("#### IMO Gulf confirmed incidents")
            st.dataframe(format_dates_for_display(sort_latest(v5)),use_container_width=True,hide_index=True)
        if not len(v0) and not len(v1) and not len(v2) and not len(v3) and not len(v4) and not len(v5):
            st.warning("No vessel match found.")
    else:
        st.info("Enter a vessel name or IMO number.")

# ---------------- Sanctions ----------------
elif page == "Sanctions & Watchlists":
    masthead("Sanctions & Watchlists", "Vessel-level screening across government sanctions fields and analytical watchlists. EU data remains present only where supplied in the existing aggregator; the app is not built around a separate EU official feed.")
    x=watch.copy()
    q=st.text_input("Search vessel / IMO / flag")
    x=text_search(x,q)
    source=st.selectbox("Listing source",["All","OFAC","FCDO","UANI","SECO","MFAT","UN","EU (aggregator only)"])
    colmap={"OFAC":"ofac","FCDO":"fcdo","UANI":"uani","SECO":"seco","MFAT":"mfat","UN":"un","EU (aggregator only)":"eu"}
    if source!="All":
        c=colmap[source]
        x=x[x[c].notna() & (x[c].astype(str).str.strip()!="")]
    st.metric("Matched vessels",len(x))
    st.dataframe(format_dates_for_display(x),use_container_width=True,hide_index=True)
    st.caption("Government listings and non-government analytical watchlists are not legally equivalent. UANI and similar fields should be treated as analytical/watchlist sources, not government sanctions.")

# ---------------- IUU ----------------
elif page == "IUU Fishing Risk":
    masthead("IUU Fishing Risk Index", "Structural country-level indicators from the 2019–2025 IUU Fishing Risk Index dataset. This is not a real-time incident feed.")
    x=iuu.copy()
    c1,c2,c3,c4=st.columns(4)
    with c1: x=filter_select(x,"Year","Year")
    with c2: x=filter_select(x,"Region","Region")
    with c3: x=filter_select(x,"Resp","Responsibility")
    with c4: x=filter_select(x,"Type","Indicator type")
    st.metric("Indicator records",len(x))
    if "Score" in x.columns:
        st.metric("Average score",f"{pd.to_numeric(x['Score'],errors='coerce').mean():.2f}")
    st.dataframe(format_dates_for_display(x),use_container_width=True,hide_index=True)
    st.caption("The uploaded IUU vessel list is retained in the repository as a raw .xls reference. It can be normalized into the vessel-search layer in a later update.")

# ---------------- ReCAAP ----------------
elif page == "ReCAAP Archive":
    masthead("ReCAAP Incident Archive", "Structured piracy and armed-robbery incidents from the uploaded 2024–2026 ReCAAP annual incident lists.")
    x=recaap.copy()
    c1,c2,c3,c4=st.columns(4)
    with c1: x=filter_select(x,"year","Year")
    with c2: x=filter_select(x,"area","Area")
    with c3: x=filter_select(x,"ship_type","Vessel type")
    with c4: x=filter_select(x,"category","Category")
    st.metric("Incidents",len(x))
    if {"latitude_decimal","longitude_decimal"}.issubset(x.columns):
        m=x.dropna(subset=["latitude_decimal","longitude_decimal"])
        if len(m):
            st.map(m,latitude="latitude_decimal",longitude="longitude_decimal")
    st.dataframe(format_dates_for_display(sort_latest(x)),use_container_width=True,hide_index=True)
