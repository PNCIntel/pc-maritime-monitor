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
div[data-testid="stMetric"] {background:#0c1c30; border:1px solid #26364b; padding:10px 14px; border-radius:6px;}
div[data-testid="stMetricLabel"] {color:#9eacbc;}
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
    return pd.read_csv(p, low_memory=False)

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

# ---------------- Navigation ----------------
st.sidebar.markdown("### POWER & CORRIDORS")
st.sidebar.caption("INTELLIGENCE PLATFORM")
page = st.sidebar.radio(
    "Navigate",
    [
        "Overview",
        "Ask P&C",
        "Maritime Attacks",
        "Piracy & Armed Robbery",
        "UKMTO Warnings",
        "Port Incidents",
        "Port Investment",
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
    masthead("P&C Intelligence Platform", "A cross-dataset operating picture of maritime security, port disruption, vessel activity, sanctions/watchlists, IUU risk and infrastructure investment.")
    c1,c2,c3,c4 = st.columns(4)
    with c1: card("2026 Maritime Attacks", f"{len(attacks):,}", "Conflict, piracy and maritime-security records")
    with c2: card("Port Incidents", f"{len(ports):,}", "Global port and terminal events")
    with c3: card("UKMTO Warnings", f"{len(ukmto):,}", "Warnings reviewed in the source log")
    with c4: card("Port Opportunities", f"{len(invest):,}", "Investment and commercial opportunities")

    st.markdown("### Intelligence layers", unsafe_allow_html=True)
    a,b,c = st.columns(3)
    with a:
        st.markdown("#### Security")
        st.write("Maritime attacks, piracy/armed robbery, UKMTO warnings, ReCAAP incidents and Black Sea conflict-vessel reporting.")
    with b:
        st.markdown("#### Vessels & illicit activity")
        st.write("Black Sea voyages, vessel profiles, sanctions/watchlists and the IUU Fishing Risk Index.")
    with c:
        st.markdown("#### Ports & capital")
        st.write("Port/terminal incidents, operational impacts, infrastructure investment and procurement entry points.")

    st.markdown("### Recent port incidents")
    cols=[c for c in ["Date","Country","Port / Location","Incident Category","Severity","Event Summary"] if c in ports.columns]
    st.dataframe(ports.sort_values("Date", ascending=False)[cols].head(12), use_container_width=True, hide_index=True)

# ---------------- Ask P&C ----------------
elif page == "Ask P&C":
    masthead("Ask P&C", "Query the platform across multiple datasets. Local evidence retrieval works without an API key; optional AI synthesis is enabled when OPENAI_API_KEY is added to Streamlit Secrets.")
    q = st.text_input("Ask a question", placeholder="e.g. Which blacklisted vessels appear in the Black Sea voyage data?")
    st.caption("Examples: “Fujairah”, “Ust-Luga”, “OFAC vessels”, “CAT 2 bulk carriers”, “Chornomorsk attacks”, “drone port attacks”")

    datasets = {
        "Port incidents": ports,
        "UKMTO warnings": ukmto,
        "Maritime attacks": attacks,
        "Piracy": piracy,
        "Port investment": invest,
        "Black Sea voyages": bs_voy,
        "Black Sea conflict vessels": bs_conflict,
        "Black Sea port attacks": bs_ports,
        "Vessel profiles": bs_profiles,
        "Sanctions/watchlists": watch,
        "ReCAAP": recaap,
    }

    if q:
        ql = q.lower()
        results = []
        # IMO/name cross-match mode
        if ("black sea" in ql or "voyage" in ql) and ("sanction" in ql or "blacklist" in ql or "ofac" in ql):
            if "IMO" in bs_voy.columns and "imo" in watch.columns:
                a = bs_voy.copy()
                b = watch.copy()
                a["_imo"] = pd.to_numeric(a["IMO"], errors="coerce").astype("Int64")
                b["_imo"] = pd.to_numeric(b["imo"], errors="coerce").astype("Int64")
                m = a.merge(b, on="_imo", how="inner", suffixes=("_voyage","_watch"))
                if "ofac" in ql and "ofac" in m.columns:
                    m = m[m["ofac"].notna() & (m["ofac"].astype(str).str.strip()!="")]
                results.append(("Cross-match: Black Sea voyages × vessel watchlists", m))
        else:
            # keyword retrieval across text fields
            for name, df in datasets.items():
                hit = text_search(df, q)
                if len(hit):
                    results.append((name, hit))

        if not results:
            st.warning("No direct matches found. Try a vessel name, IMO, port, country, classification or shorter phrase.")
        else:
            total = sum(len(df) for _,df in results)
            st.success(f"{total:,} matched records across {len(results)} dataset(s).")
            evidence_chunks = []
            for name, df in results[:8]:
                st.markdown(f"#### {name} — {len(df):,} matches")
                show = df.head(100)
                st.dataframe(show, use_container_width=True, hide_index=True)
                evidence_chunks.append(f"\nDATASET: {name}\n{show.head(20).to_csv(index=False)}")

            # Optional OpenAI synthesis
            api_key = None
            try:
                api_key = st.secrets.get("OPENAI_API_KEY")
            except Exception:
                api_key = None

            if api_key:
                if st.button("Generate AI assessment", type="primary"):
                    try:
                        from openai import OpenAI
                        client = OpenAI(api_key=api_key)
                        prompt = """You are the analytical layer for Power & Corridors. Answer only from the supplied retrieved records.
Separate facts from inference. Identify data gaps and conflicting records. Do not invent relationships.
Question: """ + q + "\n\nRetrieved evidence:\n" + "\n".join(evidence_chunks)[:70000]
                        resp = client.responses.create(
                            model="gpt-5.6",
                            input=prompt,
                        )
                        st.markdown("### AI assessment")
                        st.write(resp.output_text)
                        st.caption("AI synthesis is based only on the retrieved records shown above.")
                    except Exception as e:
                        st.error(f"AI synthesis could not run: {e}")
            else:
                st.info("AI synthesis is not yet enabled. Add OPENAI_API_KEY in Streamlit → App settings → Secrets. The evidence search above remains fully functional.")

# ---------------- Maritime Attacks ----------------
elif page == "Maritime Attacks":
    masthead("Maritime Attacks 2026", "Conflict-related and other maritime-security incidents from the 2026 master dataset.")
    x=attacks.copy()
    c1,c2,c3 = st.columns(3)
    with c1: x=filter_select(x,"Theatre","Theatre")
    with c2: x=filter_select(x,"Category","Category")
    with c3: x=filter_select(x,"Vessel Type","Vessel type")
    st.metric("Records",len(x))
    st.dataframe(x.sort_values("Date",ascending=False), use_container_width=True, hide_index=True)

# ---------------- Piracy ----------------
elif page == "Piracy & Armed Robbery":
    masthead("Piracy & Armed Robbery", "Piracy-specific records are separated from wider conflict attacks to preserve analytical clarity.")
    x=piracy.copy()
    c1,c2,c3=st.columns(3)
    with c1: x=filter_select(x,"Theatre","Theatre")
    with c2: x=filter_select(x,"Category","Category")
    with c3: x=filter_select(x,"Confidence","Confidence")
    st.metric("Piracy / armed-robbery records",len(x))
    st.dataframe(x.sort_values("Date",ascending=False),use_container_width=True,hide_index=True)

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
    st.dataframe(x.sort_values("Date",ascending=False),use_container_width=True,hide_index=True)

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
    st.dataframe(x.sort_values("Date",ascending=False),use_container_width=True,hide_index=True)

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

# ---------------- Black Sea ----------------
elif page == "Black Sea":
    masthead("Black Sea Maritime Database", "Voyages, conflict-affected vessels, port attacks and vessel profiles extracted from the BlackSeaNews maritime database.")
    tab1,tab2,tab3,tab4=st.tabs(["Vessel voyages","Conflict vessels","Port attacks","Vessel profiles"])
    with tab1:
        q=st.text_input("Search voyages",key="bsvq")
        st.dataframe(text_search(bs_voy,q),use_container_width=True,hide_index=True)
    with tab2:
        st.dataframe(bs_conflict.sort_values("Date",ascending=False),use_container_width=True,hide_index=True)
    with tab3:
        st.dataframe(bs_ports.sort_values("Date",ascending=False),use_container_width=True,hide_index=True)
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
        if len(v1):
            st.markdown("#### Black Sea voyages")
            st.dataframe(v1,use_container_width=True,hide_index=True)
        if len(v2):
            st.markdown("#### Vessel profiles")
            st.dataframe(v2,use_container_width=True,hide_index=True)
        if len(v3):
            st.markdown("#### Sanctions / watchlists")
            st.dataframe(v3,use_container_width=True,hide_index=True)
        if not len(v1) and not len(v2) and not len(v3):
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
    st.dataframe(x.sort_values("date",ascending=False),use_container_width=True,hide_index=True)
