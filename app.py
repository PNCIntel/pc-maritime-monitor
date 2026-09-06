import streamlit as st
import pandas as pd
from pathlib import Path

st.set_page_config(
    page_title="P&C Intelligence Monitor",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -----------------------------
# Power & Corridors visual system
# -----------------------------
st.markdown(
    """
    <style>
    :root {
        --pc-navy: #0b1f33;
        --pc-navy-2: #132c46;
        --pc-gold: #c6a15b;
        --pc-gold-soft: #ead9b8;
        --pc-ink: #171a1f;
        --pc-muted: #66717d;
        --pc-paper: #f7f5f0;
        --pc-line: #d9d5cc;
    }

    .stApp {
        background: #fbfaf7;
        color: var(--pc-ink);
    }

    [data-testid="stSidebar"] {
        background: var(--pc-navy);
    }
    [data-testid="stSidebar"] * {
        color: #f8f7f3;
    }
    [data-testid="stSidebar"] .stRadio label,
    [data-testid="stSidebar"] .stMultiSelect label,
    [data-testid="stSidebar"] .stSelectbox label {
        color: #f8f7f3 !important;
    }

    .pc-masthead {
        background: linear-gradient(120deg, #0b1f33 0%, #132c46 100%);
        border-top: 4px solid var(--pc-gold);
        padding: 28px 32px 24px 32px;
        margin: -1rem 0 1.5rem 0;
        color: white;
    }
    .pc-kicker {
        font-size: 0.78rem;
        letter-spacing: 0.18em;
        text-transform: uppercase;
        color: var(--pc-gold-soft);
        font-weight: 700;
        margin-bottom: 8px;
    }
    .pc-title {
        font-family: Georgia, 'Times New Roman', serif;
        font-size: 2.35rem;
        line-height: 1.05;
        font-weight: 700;
        margin: 0;
    }
    .pc-subtitle {
        font-size: 1rem;
        margin-top: 10px;
        color: #e8edf2;
        max-width: 900px;
    }
    .pc-section-label {
        font-size: .76rem;
        letter-spacing: .14em;
        text-transform: uppercase;
        font-weight: 800;
        color: #8a6a2f;
        margin: 0 0 .25rem 0;
    }
    .pc-callout {
        background: #f3eee3;
        border-left: 4px solid var(--pc-gold);
        padding: 14px 18px;
        margin: 10px 0 18px 0;
    }
    .pc-footer {
        border-top: 1px solid var(--pc-line);
        padding-top: 14px;
        color: var(--pc-muted);
        font-size: .82rem;
        margin-top: 28px;
    }
    h1, h2, h3 {
        color: var(--pc-navy);
    }
    [data-testid="stMetric"] {
        background: white;
        border: 1px solid #e0ddd6;
        border-top: 3px solid var(--pc-gold);
        padding: 14px 16px;
    }
    [data-testid="stMetricLabel"] {
        color: var(--pc-muted);
    }
    div[data-testid="stDataFrame"] {
        border: 1px solid #e2ded6;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        border-bottom: 1px solid #ddd8cf;
    }
    .stTabs [data-baseweb="tab"] {
        background: #f4f1ea;
        border-radius: 0;
        padding-left: 18px;
        padding-right: 18px;
    }
    .stTabs [aria-selected="true"] {
        border-bottom: 3px solid var(--pc-gold) !important;
        color: var(--pc-navy) !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

DATA = Path("data")

@st.cache_data
def load_recaap():
    df = pd.read_csv(DATA / "incidents.csv")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["category"] = df["category"].astype(str).str.replace(".0", "", regex=False)
    return df

@st.cache_data
def load_port_incidents():
    df = pd.read_csv(DATA / "port_incidents_2026.csv")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    for col in ["fatalities", "injuries", "containers_lost_damaged", "damage_loss_estimate"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df

@st.cache_data
def load_investments():
    df = pd.read_csv(DATA / "port_investment_opportunities_2026.csv")
    df["source_date"] = pd.to_datetime(df["source_date"], errors="coerce")
    for col in ["reported_amount", "usd_per_local_unit", "converted_value_usd"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df

recaap = load_recaap()
ports = load_port_incidents()
invest = load_investments()


def masthead(title, subtitle):
    st.markdown(
        f"""
        <div class="pc-masthead">
            <div class="pc-kicker">POWER &amp; CORRIDORS · INTELLIGENCE</div>
            <div class="pc-title">{title}</div>
            <div class="pc-subtitle">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def fmt_usd(v):
    if pd.isna(v):
        return "—"
    if abs(v) >= 1_000_000_000:
        return f"${v/1_000_000_000:.2f}bn"
    if abs(v) >= 1_000_000:
        return f"${v/1_000_000:.1f}m"
    return f"${v:,.0f}"


def unique_sorted(series):
    return sorted(series.dropna().astype(str).unique().tolist())

with st.sidebar:
    st.markdown("### POWER & CORRIDORS")
    st.caption("INTELLIGENCE MONITOR")
    section = st.radio(
        "Desk",
        ["Overview", "Maritime Security", "Port Incidents", "Port Investment"],
        label_visibility="collapsed",
    )
    st.divider()
    st.caption("From events to implications.")
    st.markdown("[powerncorridors.com](https://www.powerncorridors.com/)")

# ============================================================
# OVERVIEW
# ============================================================
if section == "Overview":
    masthead(
        "P&C Intelligence Monitor",
        "A combined operating picture of maritime security incidents, port disruption and global port investment opportunities.",
    )

    st.markdown('<div class="pc-section-label">Operating picture</div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("ReCAAP incidents", f"{len(recaap):,}", "2024–2026")
    c2.metric("2026 port incidents", f"{len(ports):,}")
    c3.metric("Port opportunities", f"{len(invest):,}")
    c4.metric("Disclosed opportunity value", fmt_usd(invest["converted_value_usd"].sum(skipna=True)))

    st.markdown(
        """
        <div class="pc-callout"><b>Analytical purpose.</b> The monitor keeps security events, port-side disruption and commercial investment in separate datasets, while allowing them to be read as one movement-and-infrastructure picture.</div>
        """,
        unsafe_allow_html=True,
    )

    left, right = st.columns(2)
    with left:
        st.subheader("2026 port incidents by region")
        st.bar_chart(ports["region"].value_counts().rename("Incidents"))
    with right:
        st.subheader("Port opportunities by region")
        st.bar_chart(invest["region"].value_counts().rename("Opportunities"))

    left, right = st.columns(2)
    with left:
        st.subheader("Latest port incidents")
        latest = ports.sort_values("date", ascending=False)[
            ["date", "country", "port_location", "incident_category", "severity"]
        ].head(8).copy()
        latest["date"] = latest["date"].dt.date
        st.dataframe(latest, use_container_width=True, hide_index=True)
    with right:
        st.subheader("Largest disclosed port opportunities")
        largest = invest.sort_values("converted_value_usd", ascending=False)[
            ["country", "port_location", "project_asset", "primary_company_authority", "converted_value_usd"]
        ].head(8).copy()
        largest["converted_value_usd"] = largest["converted_value_usd"].map(fmt_usd)
        st.dataframe(largest, use_container_width=True, hide_index=True)

# ============================================================
# MARITIME SECURITY / RECAAP
# ============================================================
elif section == "Maritime Security":
    masthead(
        "Maritime Security Monitor",
        "ReCAAP piracy and armed-robbery incident records, mapped and filtered across 2024–2026.",
    )

    with st.sidebar:
        st.markdown("#### Maritime filters")
        years = sorted(recaap["year"].dropna().astype(int).unique(), reverse=True)
        selected_years = st.multiselect("Year", years, default=years)
        selected_areas = st.multiselect("Area", unique_sorted(recaap["area"]))
        selected_vessels = st.multiselect("Vessel type", unique_sorted(recaap["ship_type"]))
        selected_categories = st.multiselect("Category", unique_sorted(recaap["category"]))
        selected_activities = st.multiselect("Ship activity", unique_sorted(recaap["ship_activity"]))

    filtered = recaap.copy()
    if selected_years:
        filtered = filtered[filtered["year"].isin(selected_years)]
    if selected_areas:
        filtered = filtered[filtered["area"].isin(selected_areas)]
    if selected_vessels:
        filtered = filtered[filtered["ship_type"].isin(selected_vessels)]
    if selected_categories:
        filtered = filtered[filtered["category"].isin(selected_categories)]
    if selected_activities:
        filtered = filtered[filtered["ship_activity"].isin(selected_activities)]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Incidents", f"{len(filtered):,}")
    m2.metric("CAT 2 / CAT 3", f"{filtered['category'].isin(['2','3']).sum():,}")
    m3.metric("Malacca & Singapore", f"{filtered['area'].str.contains('Malacca|Singapore', case=False, na=False).sum():,}")
    m4.metric("While sailing", f"{filtered['ship_activity'].str.contains('Sailing', case=False, na=False).sum():,}")

    tab1, tab2, tab3 = st.tabs(["Map", "Trends", "Incident database"])
    with tab1:
        st.subheader("Incident map")
        map_df = filtered.dropna(subset=["latitude_decimal", "longitude_decimal"])
        if map_df.empty:
            st.info("No mapped incidents match the current filters.")
        else:
            st.map(map_df, latitude="latitude_decimal", longitude="longitude_decimal")
            st.caption(f"Showing {len(map_df):,} geolocated incidents.")

    with tab2:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Incidents by category")
            st.bar_chart(filtered["category"].value_counts().rename("Incidents"))
        with c2:
            st.subheader("Incidents by vessel type")
            st.bar_chart(filtered["ship_type"].value_counts().head(10).rename("Incidents"))
        st.subheader("Incidents over time")
        monthly = filtered.dropna(subset=["date"]).set_index("date").resample("ME").size().rename("Incidents")
        st.line_chart(monthly)

    with tab3:
        st.subheader("Incident database")
        cols = ["date", "ship_name", "incident_type", "area", "area_description", "ship_type", "ship_activity", "category"]
        display = filtered.sort_values("date", ascending=False)[cols].copy()
        display["date"] = display["date"].dt.date
        st.dataframe(display, use_container_width=True, hide_index=True)
        st.download_button(
            "Download filtered CSV",
            filtered.to_csv(index=False).encode("utf-8"),
            "pc_maritime_security_filtered.csv",
            "text/csv",
        )
        st.subheader("Incident detail")
        if not filtered.empty:
            choices = filtered.sort_values("date", ascending=False).copy()
            choices["label"] = choices.apply(
                lambda r: f"{r['date'].date() if pd.notna(r['date']) else 'Unknown date'} — {r['ship_name']} — {r['area_description']}",
                axis=1,
            )
            label = st.selectbox("Select an incident", choices["label"].tolist())
            row = choices.loc[choices["label"] == label].iloc[0]
            st.markdown(f"**Vessel:** {row['ship_name']}  ")
            st.markdown(f"**Flag / type:** {row['flag']} / {row['ship_type']}  ")
            st.markdown(f"**Location:** {row['area_description']}  ")
            st.markdown(f"**Activity:** {row['ship_activity']}  ")
            st.markdown(f"**Category:** {row['category']}  ")
            st.write(row["description"])
            st.caption(f"Source: ReCAAP annual incident list, {int(row['year'])}, page {int(row['source_page'])}.")
        else:
            st.info("No incidents match the current filters.")

# ============================================================
# PORT INCIDENTS
# ============================================================
elif section == "Port Incidents":
    masthead(
        "Global Port & Terminal Incidents",
        "2026 port-side, near-port and port-linked incidents: conflict, collisions, groundings, fires, cargo loss and infrastructure accidents.",
    )

    with st.sidebar:
        st.markdown("#### Port incident filters")
        f_region = st.multiselect("Region", unique_sorted(ports["region"]))
        f_country = st.multiselect("Country", unique_sorted(ports["country"]))
        f_category = st.multiselect("Incident category", unique_sorted(ports["incident_category"]))
        f_severity = st.multiselect("Severity", unique_sorted(ports["severity"]))
        f_conflict = st.multiselect("Conflict-related", unique_sorted(ports["conflict_related"]))

    p = ports.copy()
    if f_region: p = p[p["region"].isin(f_region)]
    if f_country: p = p[p["country"].isin(f_country)]
    if f_category: p = p[p["incident_category"].isin(f_category)]
    if f_severity: p = p[p["severity"].isin(f_severity)]
    if f_conflict: p = p[p["conflict_related"].isin(f_conflict)]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Incidents", f"{len(p):,}")
    m2.metric("Conflict-related", f"{p['conflict_related'].astype(str).str.lower().eq('yes').sum():,}")
    m3.metric("Fatalities", f"{int(p['fatalities'].sum(skipna=True)):,}")
    m4.metric("High severity", f"{p['severity'].astype(str).str.lower().eq('high').sum():,}")

    tab1, tab2, tab3 = st.tabs(["Patterns", "Incident database", "Incident detail"])
    with tab1:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Incidents by region")
            st.bar_chart(p["region"].value_counts().rename("Incidents"))
        with c2:
            st.subheader("Incidents by category")
            st.bar_chart(p["incident_category"].value_counts().rename("Incidents"))
        st.subheader("2026 incident timeline")
        monthly = p.dropna(subset=["date"]).set_index("date").resample("ME").size().rename("Incidents")
        st.line_chart(monthly)

    with tab2:
        show = p.sort_values("date", ascending=False)[
            ["date", "region", "country", "port_location", "incident_category", "incident_sub_type", "severity", "confidence", "primary_source"]
        ].copy()
        show["date"] = show["date"].dt.date
        st.dataframe(
            show,
            use_container_width=True,
            hide_index=True,
            column_config={"primary_source": st.column_config.LinkColumn("Source")},
        )
        st.download_button(
            "Download filtered CSV",
            p.to_csv(index=False).encode("utf-8"),
            "pc_port_incidents_2026_filtered.csv",
            "text/csv",
        )

    with tab3:
        if p.empty:
            st.info("No incidents match the current filters.")
        else:
            opts = p.sort_values("date", ascending=False).copy()
            opts["label"] = opts.apply(lambda r: f"{r['date'].date()} — {r['port_location']} — {r['incident_category']}", axis=1)
            label = st.selectbox("Select a port incident", opts["label"].tolist())
            row = opts.loc[opts["label"] == label].iloc[0]
            st.markdown(f"### {row['port_location']}")
            a, b, c = st.columns(3)
            a.metric("Severity", row["severity"])
            b.metric("Confidence", row["confidence"])
            c.metric("Conflict-related", row["conflict_related"])
            st.markdown(f"**Asset / vessel:** {row['vessel_asset']}  ")
            st.markdown(f"**Operator / authority:** {row['operator_authority']}  ")
            st.markdown("**Event summary**")
            st.write(row["event_summary"])
            st.markdown("**Operational impact**")
            st.write(row["port_operational_impact"])
            st.markdown("**Cause / attribution**")
            st.write(row["cause_attribution"])
            st.markdown("**Intelligence relevance**")
            st.write(row["notes_intelligence_relevance"])
            if pd.notna(row.get("primary_source")):
                st.markdown(f"[Primary source]({row['primary_source']})")
            if pd.notna(row.get("secondary_source")) and str(row.get("secondary_source")).strip():
                st.markdown(f"[Secondary source]({row['secondary_source']})")

# ============================================================
# PORT INVESTMENT
# ============================================================
else:
    masthead(
        "Global Port Investment & Commercial Opportunities",
        "A 2026 tracker of port investment, concessions, terminal development, procurement entry points and disclosed project values.",
    )

    with st.sidebar:
        st.markdown("#### Investment filters")
        i_region = st.multiselect("Region", unique_sorted(invest["region"]))
        i_country = st.multiselect("Country", unique_sorted(invest["country"]))
        i_company = st.multiselect("Company / authority", unique_sorted(invest["primary_company_authority"]))
        i_type = st.multiselect("Opportunity type", unique_sorted(invest["opportunity_type"]))
        i_stage = st.multiselect("Project / tender stage", unique_sorted(invest["project_tender_stage"]))
        i_cargo = st.multiselect("Cargo / infrastructure", unique_sorted(invest["cargo_infrastructure"]))

    q = invest.copy()
    if i_region: q = q[q["region"].isin(i_region)]
    if i_country: q = q[q["country"].isin(i_country)]
    if i_company: q = q[q["primary_company_authority"].isin(i_company)]
    if i_type: q = q[q["opportunity_type"].isin(i_type)]
    if i_stage: q = q[q["project_tender_stage"].isin(i_stage)]
    if i_cargo: q = q[q["cargo_infrastructure"].isin(i_cargo)]

    total_value = q["converted_value_usd"].sum(skipna=True)
    disclosed = q["converted_value_usd"].notna().sum()
    undisclosed = len(q) - disclosed
    countries = q["country"].nunique()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Opportunities", f"{len(q):,}")
    m2.metric("Disclosed value", fmt_usd(total_value))
    m3.metric("Countries", f"{countries:,}")
    m4.metric("Undisclosed value", f"{undisclosed:,} projects")

    tab1, tab2, tab3 = st.tabs(["Commercial picture", "Opportunity database", "Opportunity detail"])
    with tab1:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Opportunities by region")
            st.bar_chart(q["region"].value_counts().rename("Opportunities"))
        with c2:
            st.subheader("Top companies / authorities")
            st.bar_chart(q["primary_company_authority"].value_counts().head(10).rename("Opportunities"))

        st.subheader("Largest disclosed values")
        value_chart = q.dropna(subset=["converted_value_usd"]).nlargest(12, "converted_value_usd").copy()
        if not value_chart.empty:
            value_chart["label"] = value_chart["project_asset"] + " — " + value_chart["country"]
            st.bar_chart(value_chart.set_index("label")["converted_value_usd"])

    with tab2:
        show = q.sort_values(["converted_value_usd", "country"], ascending=[False, True])[
            ["region", "country", "port_location", "project_asset", "primary_company_authority", "project_tender_stage", "local_currency", "reported_amount", "converted_value_usd", "deadline_timing", "source_url"]
        ].copy()
        st.dataframe(
            show,
            use_container_width=True,
            hide_index=True,
            column_config={
                "reported_amount": st.column_config.NumberColumn("Reported amount", format="%.0f"),
                "converted_value_usd": st.column_config.NumberColumn("Converted value (USD)", format="$%.0f"),
                "source_url": st.column_config.LinkColumn("Source"),
            },
        )
        st.download_button(
            "Download filtered CSV",
            q.to_csv(index=False).encode("utf-8"),
            "pc_port_investment_2026_filtered.csv",
            "text/csv",
        )

    with tab3:
        if q.empty:
            st.info("No opportunities match the current filters.")
        else:
            opts = q.copy()
            opts["label"] = opts.apply(lambda r: f"{r['country']} — {r['project_asset']} — {r['primary_company_authority']}", axis=1)
            label = st.selectbox("Select an opportunity", opts["label"].tolist())
            row = opts.loc[opts["label"] == label].iloc[0]
            st.markdown(f"### {row['project_asset']}")
            a, b, c = st.columns(3)
            a.metric("Converted value", fmt_usd(row["converted_value_usd"]))
            b.metric("Confidence", row["confidence"])
            c.metric("Region", row["region"])
            st.markdown(f"**Location:** {row['port_location']}, {row['country']}  ")
            st.markdown(f"**Primary company / authority:** {row['primary_company_authority']}  ")
            st.markdown(f"**Other parties:** {row['other_parties']}  ")
            st.markdown(f"**Opportunity type:** {row['opportunity_type']}  ")
            st.markdown(f"**Stage:** {row['project_tender_stage']}  ")
            st.markdown("**2026 development / status**")
            st.write(row["2026_development_status"])
            st.markdown("**Commercial opportunity**")
            st.write(row["commercial_opportunity"])
            st.markdown("**Next procurement / entry point**")
            st.write(row["next_procurement_entry_point"])
            st.markdown(f"**Deadline / timing:** {row['deadline_timing']}  ")
            st.markdown(f"**Strategic theme:** {row['strategic_theme']}  ")
            if pd.notna(row.get("source_url")):
                st.markdown(f"[Source]({row['source_url']})")

st.markdown(
    """
    <div class="pc-footer">
    Power &amp; Corridors Intelligence · Analytical dashboard prototype · Source datasets remain distinct and retain their original source links.
    </div>
    """,
    unsafe_allow_html=True,
)
