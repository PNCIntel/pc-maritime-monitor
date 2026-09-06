import streamlit as st
import pandas as pd
from pathlib import Path
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
        "iuu": ["iuu","illegal fishing","fishing"]
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

# ---------------- Navigation ----------------
st.sidebar.markdown("### POWER & CORRIDORS")
st.sidebar.caption("INTELLIGENCE PLATFORM · DATA DESK")
page = st.sidebar.radio(
    "Navigate",
    [
        "Overview",
        "Ask P&C",
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

# ---------------- Overview ----------------
if page == "Overview":
    masthead("P&C Intelligence Platform", "A cross-dataset operating picture of maritime security, port disruption, military maritime actions, vessel activity, sanctions/watchlists, shipbuilding, IUU risk and infrastructure investment.")
    c1,c2,c3,c4 = st.columns(4)
    with c1: card("2026 Maritime Attacks", f"{len(attacks):,}", "Conflict, piracy and maritime-security records")
    with c2: card("Port Incidents", f"{len(ports):,}", "Global port and terminal events")
    with c3: card("UKMTO Warnings", f"{len(ukmto):,}", "Warnings reviewed in the source log")
    with c4: card("Port Opportunities", f"{len(invest):,}", "Investment and commercial opportunities")

    d1,d2,d3,d4 = st.columns(4)
    with d1: card("CENTCOM Maritime Actions", f"{len(centcom):,}", "Boardings, disabling strikes and vessel interdictions")
    with d2: card("IMO Gulf Confirmed", f"{len(imo_gulf):,}", "IMO-recorded merchant vessel incidents")
    with d3: card("Naval / CG Programs", f"{len(naval_build):,}", "2026 shipbuilding, transfer and industrial events")
    with d4: card("Shipyard Moves", f"{len(shipyard_moves):,}", "Acquisitions, bids and industrial capacity shifts")

    st.markdown("### Intelligence layers", unsafe_allow_html=True)
    a,b,c = st.columns(3)
    with a:
        st.markdown("#### Security")
        st.write("Maritime attacks, piracy/armed robbery, UKMTO warnings, CENTCOM maritime actions, IMO-confirmed Gulf incidents, ReCAAP and Black Sea conflict-vessel reporting.")
    with b:
        st.markdown("#### Vessels & illicit activity")
        st.write("Black Sea voyages, vessel profiles, sanctions/watchlists and the IUU Fishing Risk Index.")
    with c:
        st.markdown("#### Ports & capital")
        st.write("Port/terminal incidents, operational impacts, infrastructure investment, naval/coast-guard shipbuilding and shipyard industrial moves.")

    st.markdown("### Recent port incidents")
    recent = sort_latest(ports).head(12).copy()
    if "Date" in recent.columns:
        recent["Date"] = pd.to_datetime(recent["Date"], errors="coerce").dt.strftime("%d %b %Y")
    cols=[c for c in ["Date","Country","Port / Location","Incident Category","Severity","Event Summary"] if c in recent.columns]
    if cols:
        st.dataframe(recent[cols], use_container_width=True, hide_index=True)
    else:
        st.dataframe(recent, use_container_width=True, hide_index=True)

# ---------------- Ask P&C ----------------
elif page == "Ask P&C":
    masthead(
        "Ask P&C",
        "Search and analyse the P&C maritime intelligence datasets. Ask about incidents, vessels, ports, sanctions, Black Sea activity, piracy, investment and operational risk."
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
                st.dataframe(show[cols].head(75), use_container_width=True, hide_index=True)

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


# ---------------- Maritime Attacks ----------------
elif page == "Maritime Attacks":
    masthead("Maritime Attacks 2026", "Conflict-related and other maritime-security incidents from the 2026 master dataset.")
    x=attacks.copy()
    c1,c2,c3 = st.columns(3)
    with c1: x=filter_select(x,"Theatre","Theatre")
    with c2: x=filter_select(x,"Category","Category")
    with c3: x=filter_select(x,"Vessel Type","Vessel type")
    st.metric("Records",len(x))
    st.dataframe(sort_latest(x), use_container_width=True, hide_index=True)

# ---------------- Piracy ----------------
elif page == "Piracy & Armed Robbery":
    masthead("Piracy & Armed Robbery", "Piracy-specific records are separated from wider conflict attacks to preserve analytical clarity.")
    x=piracy.copy()
    c1,c2,c3=st.columns(3)
    with c1: x=filter_select(x,"Theatre","Theatre")
    with c2: x=filter_select(x,"Category","Category")
    with c3: x=filter_select(x,"Confidence","Confidence")
    st.metric("Piracy / armed-robbery records",len(x))
    st.dataframe(sort_latest(x),use_container_width=True,hide_index=True)

# ---------------- UKMTO ----------------
elif page == "UKMTO Warnings":
    masthead("UKMTO Warning Monitor", "Tracks warning classification, analytical classification, port relevance and update status.")
    x=ukmto.copy()
    c1,c2,c3=st.columns(3)
    with c1: x=filter_select(x,"UKMTO Classification","UKMTO classification")
    with c2: x=filter_select(x,"Analytical Classification","Analytical classification")
    with c3: x=filter_select(x,"Port Relevance","Port relevance")
    a,b,c,d=st.columns(4)
    a.metric("Warnings",len(x))
    if "Has Update" in x.columns: b.metric("With updates",int(x["Has Update"].astype(str).str.lower().eq("yes").sum()))
    if "UKMTO Classification" in x.columns: c.metric("Attacks",int(x["UKMTO Classification"].astype(str).str.lower().eq("attack").sum()))
    if "Port Relevance" in x.columns: d.metric("Port-side / near-port",int(x["Port Relevance"].astype(str).str.contains("port",case=False,na=False).sum()))
    st.dataframe(sort_latest(x),use_container_width=True,hide_index=True)


# ---------------- Gulf Military Actions ----------------
elif page == "Gulf Military Actions":
    masthead(
        "Gulf Military Maritime Actions 2026",
        "Tracks U.S. CENTCOM vessel boardings, disabling strikes and seizures alongside IMO-confirmed merchant-vessel incidents in the Gulf operating environment."
    )
    tab1, tab2 = st.tabs(["U.S. CENTCOM maritime actions", "IMO Gulf confirmed incidents"])

    with tab1:
        x = centcom.copy()
        c1,c2,c3 = st.columns(3)
        with c1: x = filter_select(x, "Action Type", "Action type")
        with c2: x = filter_select(x, "Blockade Phase", "Blockade phase")
        with c3: x = filter_select(x, "Flag", "Flag")
        a,b,c = st.columns(3)
        a.metric("Recorded actions", len(x))
        if "Outcome" in x.columns:
            b.metric("Disabled / destroyed", int(x["Outcome"].astype(str).str.contains("disabled|destroyed", case=False, na=False, regex=True).sum()))
        if "Custody / Disposition" in x.columns:
            c.metric("Boarded / custody-related", int(x["Custody / Disposition"].astype(str).str.contains("board|custody|search", case=False, na=False, regex=True).sum()))
        st.dataframe(sort_latest(x), use_container_width=True, hide_index=True)

    with tab2:
        y = imo_gulf.copy()
        c1,c2 = st.columns(2)
        with c1: y = filter_select(y, "Event Class", "Event class")
        with c2: y = filter_select(y, "Known / Assessed Actor", "Known / assessed actor")
        st.metric("IMO-confirmed records", len(y))
        st.dataframe(sort_latest(y), use_container_width=True, hide_index=True)
        st.caption("IMO-confirmed incident descriptions are kept separate from actor attribution. Assessed-actor fields should be read as analytical context, not as IMO attribution.")

# ---------------- Port Incidents ----------------
elif page == "Port Incidents":
    masthead("Global Port & Terminal Incidents 2026", "Operational, accident, conflict and infrastructure events affecting ports and terminals.")
    x=ports.copy()
    c1,c2,c3,c4=st.columns(4)
    with c1: x=filter_select(x,"Region","Region")
    with c2: x=filter_select(x,"Country","Country")
    with c3: x=filter_select(x,"Incident Category","Category")
    with c4: x=filter_select(x,"Severity","Severity")
    a,b,c,d=st.columns(4)
    a.metric("Incidents",len(x))
    if "Conflict-Related" in x.columns: b.metric("Conflict-related",int(x["Conflict-Related"].astype(str).str.lower().eq("yes").sum()))
    if "Fatalities" in x.columns: c.metric("Fatalities",int(pd.to_numeric(x["Fatalities"],errors="coerce").fillna(0).sum()))
    if "Injuries" in x.columns: d.metric("Injuries",int(pd.to_numeric(x["Injuries"],errors="coerce").fillna(0).sum()))
    st.dataframe(sort_latest(x),use_container_width=True,hide_index=True)

# ---------------- Port Investment ----------------
elif page == "Port Investment":
    masthead("Port Investment & Commercial Opportunities 2026", "Tracks capital deployment, project stage and procurement/entry points across global port infrastructure.")
    x=invest.copy()
    c1,c2,c3=st.columns(3)
    with c1: x=filter_select(x,"Region","Region")
    with c2: x=filter_select(x,"Country","Country")
    with c3: x=filter_select(x,"Project / Tender Stage","Stage")
    value=pd.to_numeric(x.get("Converted Value (USD)"),errors="coerce") if "Converted Value (USD)" in x.columns else pd.Series(dtype=float)
    a,b,c=st.columns(3)
    a.metric("Opportunities",len(x))
    b.metric("Disclosed value",fmt_money(value.sum()))
    c.metric("Countries",x["Country"].nunique() if "Country" in x.columns else "—")
    st.dataframe(x,use_container_width=True,hide_index=True)


# ---------------- Naval & Shipbuilding ----------------
elif page == "Naval & Shipbuilding":
    masthead(
        "Naval, Coast Guard & Shipbuilding Intelligence 2026",
        "Tracks naval and coast-guard vessel contracts, transfers, deliveries, shipyard acquisitions and industrial-capacity moves with commercial and strategic relevance."
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
        high = pd.to_numeric(x.get("USD Value High"), errors="coerce") if "USD Value High" in x.columns else pd.Series(dtype=float)
        qty = pd.to_numeric(x.get("Quantity"), errors="coerce") if "Quantity" in x.columns else pd.Series(dtype=float)

        a,b,c,d = st.columns(4)
        a.metric("Tracked events", len(x))
        b.metric("Vessels / assets", int(qty.fillna(0).sum()) if len(qty) else "—")
        c.metric("Disclosed low value", fmt_money(low.sum()) if len(low) else "—")
        d.metric("Countries", x["Customer Country"].nunique() if "Customer Country" in x.columns else "—")

        show_cols = [c for c in [
            "2026 Event Date","Customer Country","Customer / Service","Vessel / Program",
            "Transaction / Event Type","New / Used","Quantity","Builder / Seller / Partner",
            "Shipyard / Build Location","Build Country","USD Value Low","USD Value High",
            "2026 Status / Milestone","Expected Delivery / Completion",
            "Industrial / Strategic Relevance","Source URL","Secondary Source"
        ] if c in x.columns]
        st.dataframe(sort_latest(x, preferred=("2026 Event Date","Original Contract / Decision Date"))[show_cols], use_container_width=True, hide_index=True)

    with tab2:
        y = shipyard_moves.copy()
        c1,c2 = st.columns(2)
        with c1: y = filter_select(y, "Country", "Country")
        with c2: y = filter_select(y, "Move Type", "Move type")
        st.metric("Industrial moves", len(y))
        st.dataframe(sort_latest(y), use_container_width=True, hide_index=True)

# ---------------- Black Sea ----------------
elif page == "Black Sea":
    masthead("Black Sea Maritime Database", "Voyages, conflict-affected vessels, port attacks and vessel profiles extracted from the BlackSeaNews maritime database.")
    tab0,tab1,tab2,tab3,tab4=st.tabs(["Source index","Vessel voyages","Conflict vessels","Port attacks","Vessel profiles"])
    with tab0:
        st.dataframe(sort_latest(bs_articles, preferred=("Published",)), use_container_width=True, hide_index=True)
    with tab1:
        q=st.text_input("Search voyages",key="bsvq")
        st.dataframe(text_search(bs_voy,q),use_container_width=True,hide_index=True)
    with tab2:
        st.dataframe(sort_latest(bs_conflict),use_container_width=True,hide_index=True)
    with tab3:
        st.dataframe(sort_latest(bs_ports),use_container_width=True,hide_index=True)
    with tab4:
        st.dataframe(bs_profiles,use_container_width=True,hide_index=True)

# ---------------- Vessel Intelligence ----------------
elif page == "Vessel Intelligence":
    masthead("Vessel Intelligence", "Search across Black Sea voyages, vessel profiles and sanctions/watchlists using vessel name or IMO.")
    q=st.text_input("Vessel name or IMO",placeholder="ETHERA or 9387279")
    if q:
        v1=text_search(bs_voy,q)
        v2=text_search(bs_profiles,q)
        v3=text_search(watch,q)
        v4=text_search(centcom,q)
        v5=text_search(imo_gulf,q)
        if len(v1):
            st.markdown("#### Black Sea voyages")
            st.dataframe(v1,use_container_width=True,hide_index=True)
        if len(v2):
            st.markdown("#### Vessel profiles")
            st.dataframe(v2,use_container_width=True,hide_index=True)
        if len(v3):
            st.markdown("#### Sanctions / watchlists")
            st.dataframe(v3,use_container_width=True,hide_index=True)
        if len(v4):
            st.markdown("#### CENTCOM maritime actions")
            st.dataframe(sort_latest(v4),use_container_width=True,hide_index=True)
        if len(v5):
            st.markdown("#### IMO Gulf confirmed incidents")
            st.dataframe(sort_latest(v5),use_container_width=True,hide_index=True)
        if not len(v1) and not len(v2) and not len(v3) and not len(v4) and not len(v5):
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
    st.dataframe(x,use_container_width=True,hide_index=True)
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
    st.dataframe(x,use_container_width=True,hide_index=True)
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
    st.dataframe(sort_latest(x),use_container_width=True,hide_index=True)
