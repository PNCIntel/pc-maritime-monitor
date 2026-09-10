import streamlit as st
import pandas as pd
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
</style>
""",
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# Data helpers — all reads are from the same Excel-backed P&C model
# -----------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def xl(file_name: str, sheet: str) -> pd.DataFrame:
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


def show_df(df, cols=None, height=420):
    if df is None or df.empty:
        st.markdown('<div class="pc-empty">No matching records in the current Excel model.</div>', unsafe_allow_html=True)
        return
    if cols:
        cols = [c for c in cols if c in df.columns]
        df = df[cols]
    st.dataframe(df, use_container_width=True, hide_index=True, height=height)


def section(kicker, title, copy=None):
    st.markdown(f'<div class="pc-section-kicker">{kicker}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="pc-section-title">{title}</div>', unsafe_allow_html=True)
    if copy:
        st.markdown(f'<div class="pc-section-copy">{copy}</div>', unsafe_allow_html=True)


def event_card(row):
    title = str(row.get("Title", "Untitled event"))
    date = row.get("Start Date", row.get("Date", ""))
    etype = row.get("Event Type", row.get("Event Family", "Event"))
    sev = str(row.get("Severity", ""))
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
    eid=str(event_id or "")
    links=event_asset_links[text_col(event_asset_links,"Event ID").eq(eid)] if not event_asset_links.empty else pd.DataFrame()
    clinks=event_company_links[text_col(event_company_links,"Event ID").eq(eid)] if not event_company_links.empty else pd.DataFrame()
    slinks=event_system_links[text_col(event_system_links,"Event ID").eq(eid)] if not event_system_links.empty else pd.DataFrame()

    if links.empty and clinks.empty and slinks.empty:
        st.markdown('<div class="pc-empty">No connected canonical coverage has been mapped yet.</div>', unsafe_allow_html=True)
        return

    if not links.empty:
        st.markdown("**Associated assets / ports**")
        for _,r in links.iterrows():
            name=str(r.get("Asset",""))
            typ=str(r.get("Asset Type","Asset"))
            rel=str(r.get("Relationship",""))
            st.markdown(f"**{name}** · {typ}  \\n{rel}")
            pid=canonical_port_id(r.get("Asset ID",""),name)
            if pid:
                pr=ports[text_col(ports,"Port ID").eq(pid)]
                if not pr.empty:
                    rr=pr.iloc[0]
                    bits=[]
                    for c in ["Country","Operator","Facility Type","Key Role"]:
                        v=str(rr.get(c,"")).strip()
                        if v and v.lower() != "nan":
                            bits.append(f"{c}: {v}")
                    if bits:
                        st.caption(" · ".join(bits[:4]))

    if not clinks.empty:
        st.markdown("**Associated companies**")
        for _,r in clinks.iterrows():
            cid=str(r.get("Company ID",""))
            name=str(r.get("Company",""))
            rel=str(r.get("Relationship",""))
            st.markdown(f"**{name}**  \\n{rel}")
            if cid and not companies.empty and "Company ID" in companies.columns:
                cr=companies[text_col(companies,"Company ID").eq(cid)]
                if not cr.empty:
                    rr=cr.iloc[0]
                    bits=[]
                    for c in ["HQ Country","Ownership","Business Segments","Status"]:
                        v=str(rr.get(c,"")).strip()
                        if v and v.lower() != "nan":
                            bits.append(f"{c}: {v}")
                    if bits:
                        st.caption(" · ".join(bits[:4]))

    if not slinks.empty:
        st.markdown("**Related systems / corridors**")
        show_df(slinks,["System","Relationship","Confidence"],180)


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

NAV = {
    "INTELLIGENCE DESK": ["Operating Picture", "Alerts & Incidents"],
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
st.sidebar.caption("Excel-backed v3.0 · shared P&C canonical data")

# Header
st.markdown('<div class="pc-kicker">Power & Corridors Intelligence</div>', unsafe_allow_html=True)
st.markdown(f'<div class="pc-title">{page}</div>', unsafe_allow_html=True)
st.markdown('<div class="pc-deck">Decision-useful intelligence on geopolitical disruption, maritime security, trade corridors, aviation, sanctions, critical infrastructure and operational risk.</div>', unsafe_allow_html=True)
st.markdown('<div class="pc-rule"></div>', unsafe_allow_html=True)

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
# 3. WATCH AREAS
# -----------------------------------------------------------------------------
elif page == "Watch Areas":
    section("04 · Forward", "Watch Areas", "Geographic or system-level monitoring built from active monitoring, disruption watch and hazard records.")
    mons = monitoring.copy()
    if not mons.empty:
        mons = mons[text_col(mons,"Status").str.contains("Active|Monitoring|Developing", case=False, regex=True, na=False)]
        geos = sorted([x for x in text_col(mons,"Geography").unique() if x])
        selected = st.selectbox("Watch area", ["All"] + geos)
        if selected != "All": mons = mons[text_col(mons,"Geography").eq(selected)]
        show_df(mons, ["Title","Family","Geography","Status","Time Horizon","What Is Being Monitored","Key Indicators","Trigger / Threshold","Confidence","Last Reviewed"], 420)
    section("Disruption layer", "Current disruption watches")
    show_df(disruption, ["As Of","Family","Country","Location / System","Issue","Current Status","Trigger / Threshold","Potential Mode Impact","Potential Trade / Commercial Impact","Probability / Read","Time Horizon","Confidence"], 400)

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
