import streamlit as st
import pandas as pd

st.set_page_config(page_title="P&C Maritime Security Monitor", page_icon="⚓", layout="wide")

@st.cache_data
def load_data():
    df = pd.read_csv("data/incidents.csv")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["category"] = df["category"].astype(str).str.replace(".0", "", regex=False)
    return df

df = load_data()

st.title("⚓ P&C Maritime Security Monitor")
st.caption("ReCAAP incident data | 2024–2026 starter dashboard")

with st.sidebar:
    st.header("Filters")
    years = sorted(df["year"].dropna().astype(int).unique(), reverse=True)
    selected_years = st.multiselect("Year", years, default=years)
    selected_areas = st.multiselect("Area", sorted(df["area"].dropna().unique()))
    selected_vessels = st.multiselect("Vessel type", sorted(df["ship_type"].dropna().unique()))
    selected_categories = st.multiselect("Category", sorted(df["category"].dropna().unique()))
    selected_activities = st.multiselect("Ship activity", sorted(df["ship_activity"].dropna().unique()))

filtered = df.copy()
if selected_years: filtered = filtered[filtered["year"].isin(selected_years)]
if selected_areas: filtered = filtered[filtered["area"].isin(selected_areas)]
if selected_vessels: filtered = filtered[filtered["ship_type"].isin(selected_vessels)]
if selected_categories: filtered = filtered[filtered["category"].isin(selected_categories)]
if selected_activities: filtered = filtered[filtered["ship_activity"].isin(selected_activities)]

m1,m2,m3,m4 = st.columns(4)
m1.metric("Incidents", f"{len(filtered):,}")
m2.metric("CAT 2 / CAT 3", f"{filtered['category'].isin(['2','3']).sum():,}")
m3.metric("Malacca & Singapore", f"{filtered['area'].str.contains('Malacca|Singapore', case=False, na=False).sum():,}")
m4.metric("While sailing", f"{filtered['ship_activity'].str.contains('Sailing', case=False, na=False).sum():,}")

st.divider()
tab1,tab2,tab3 = st.tabs(["Map","Trends","Incident database"])

with tab1:
    st.subheader("Incident map")
    map_df = filtered.dropna(subset=["latitude_decimal","longitude_decimal"])
    if map_df.empty: st.info("No mapped incidents match the current filters.")
    else:
        st.map(map_df, latitude="latitude_decimal", longitude="longitude_decimal")
        st.caption(f"Showing {len(map_df):,} geolocated incidents.")

with tab2:
    c1,c2=st.columns(2)
    with c1:
        st.subheader("Incidents by category")
        st.bar_chart(filtered["category"].value_counts().rename_axis("Category").to_frame("Incidents"))
    with c2:
        st.subheader("Incidents by vessel type")
        st.bar_chart(filtered["ship_type"].value_counts().head(10).rename_axis("Vessel type").to_frame("Incidents"))
    st.subheader("Incidents over time")
    monthly = filtered.dropna(subset=["date"]).set_index("date").resample("ME").size().rename("Incidents")
    st.line_chart(monthly)

with tab3:
    st.subheader("Incident database")
    cols=["date","ship_name","incident_type","area","area_description","ship_type","ship_activity","category"]
    display=filtered.sort_values("date",ascending=False)[cols].copy(); display["date"]=display["date"].dt.date
    st.dataframe(display,use_container_width=True,hide_index=True)
    st.download_button("Download filtered CSV", filtered.to_csv(index=False).encode("utf-8"), "pc_maritime_incidents_filtered.csv", "text/csv")
    st.subheader("Incident detail")
    if filtered.empty: st.info("No incidents match the current filters.")
    else:
        choices=filtered.sort_values("date",ascending=False).copy()
        choices["label"]=choices.apply(lambda r:f"{r['date'].date() if pd.notna(r['date']) else 'Unknown date'} — {r['ship_name']} — {r['area_description']}",axis=1)
        label=st.selectbox("Select an incident",choices["label"].tolist())
        row=choices.loc[choices["label"]==label].iloc[0]
        st.markdown(f"**Vessel:** {row['ship_name']}  ")
        st.markdown(f"**Flag / type:** {row['flag']} / {row['ship_type']}  ")
        st.markdown(f"**Location:** {row['area_description']}  ")
        st.markdown(f"**Activity:** {row['ship_activity']}  ")
        st.markdown(f"**Category:** {row['category']}  ")
        st.write(row["description"])
        st.caption(f"Source: ReCAAP annual incident list, {int(row['year'])}, page {int(row['source_page'])}.")

st.divider()
st.caption("Starter dashboard for analytical use. Source data: ReCAAP Information Sharing Centre incident lists.")
