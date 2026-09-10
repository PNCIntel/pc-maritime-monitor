import streamlit as st
import pandas as pd
from pathlib import Path

st.set_page_config(page_title="P&C Intelligence — Excel v3.0", layout="wide")

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"

st.markdown("""
<style>
.stApp { background: #101417; color: #E8E4DA; }
h1,h2,h3 { color: #E8E4DA; }
[data-testid="stMetricValue"] { color: #D8B45A; }
div[data-testid="stTabs"] button { color: #D8B45A; }
.pc-card { border:1px solid #343C42; padding:14px 16px; border-radius:8px; background:#151B1F; margin-bottom:10px; }
.small { color:#AAB2B8; font-size:0.9rem; }
</style>
""", unsafe_allow_html=True)

@st.cache_data
def xl(file_name, sheet):
    return pd.read_excel(DATA / file_name, sheet_name=sheet)

vessels = xl("02_maritime.xlsx", "Vessels")
restr = xl("02_maritime.xlsx", "Vessel Restrictions")
monitor = xl("09_intelligence.xlsx", "Monitoring")
events = xl("13_events_hazards.xlsx", "Events")
feeds = xl("10_sources_evidence.xlsx", "Source Feeds")
comp_des = xl("14_trade_policy_compliance.xlsx", "Compliance Designations")
comp_exp = xl("14_trade_policy_compliance.xlsx", "Compliance Exposure")

st.title("P&C Intelligence")
st.caption("Excel-backed v3.0 product lens — same canonical P&C data, security-focused presentation")

tab1, tab2, tab3, tab4 = st.tabs(["Operating Picture", "PGSA Compliance", "MARSEC Sources", "Events"])

with tab1:
    a,b,c,d = st.columns(4)
    a.metric("Active Security Monitors", int(monitor["Monitoring ID"].astype(str).str.startswith("MON_SEC").sum()))
    b.metric("PGSA Sample Vessels", int(comp_des["Regime ID"].eq("REGIME_PGSA").sum()))
    c.metric("Official MARSEC Feeds", int(feeds["Feed ID"].astype(str).str.startswith("FEED_SEC").sum() - 1))
    d.metric("Seeded MARSEC Events", int(events["Event ID"].astype(str).str.startswith("EVT_SEC").sum()))
    st.subheader("Active Monitoring")
    cols = ["Title","Geography","Status","Time Horizon","What Is Being Monitored","Trigger / Threshold","Confidence"]
    st.dataframe(monitor[monitor["Monitoring ID"].astype(str).str.startswith("MON_SEC")][cols], use_container_width=True, hide_index=True)

with tab2:
    st.subheader("PGSA Maritime Compliance")
    pg = comp_des[comp_des["Regime ID"].eq("REGIME_PGSA")].copy()
    st.dataframe(pg[["Target Name","IMO / Identifier","Status","Direct / Indirect","Verification","Notes"]], use_container_width=True, hide_index=True)
    st.subheader("Secondary Exposure / STS")
    st.dataframe(comp_exp[["Source Vessel","Counterparty / Related Entity","Relationship","Event / Geography","Exposure Type","Status","Confidence"]], use_container_width=True, hide_index=True)
    st.subheader("Canonical Vessel Drill-down")
    chosen = st.selectbox("Vessel", pg["Target Name"].dropna().tolist())
    row = pg[pg["Target Name"].eq(chosen)].iloc[0]
    vr = vessels[vessels["IMO"].astype(str).str.replace(".0","", regex=False).eq(str(row["IMO / Identifier"]).replace(".0",""))]
    if not vr.empty:
        display_cols = ["Vessel Name","IMO","Vessel Type","Flag","Year Built","DWT","Gross Tonnage (GT)","Owner Company ID","Operator Company ID","Registered Owner (Legal)","Technical / ISM Manager"]
        st.dataframe(vr[display_cols], use_container_width=True, hide_index=True)
    else:
        st.info("Canonical vessel record not yet populated — this is exactly the gap the enrichment workflow should flag.")

with tab3:
    st.subheader("Official MARSEC Collection")
    sec = feeds[feeds["Feed ID"].astype(str).str.startswith("FEED_SEC")]
    st.dataframe(sec[["Source Name","Coverage","Default Event Families","Priority","Active","Notes"]], use_container_width=True, hide_index=True)

with tab4:
    st.subheader("Official-source MARSEC Events")
    se = events[events["Event ID"].astype(str).str.startswith("EVT_SEC")]
    st.dataframe(se[["Start Date","Country / Countries","Event Type","Severity","Status","Title","Operational Impact","Trade / Commercial Impact","Confidence"]], use_container_width=True, hide_index=True)
