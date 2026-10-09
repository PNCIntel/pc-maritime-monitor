"""Global Security risk workspace: live, source-attributed, no synthetic scores.

Reusable across geographical scopes; Hormuz is only a selectable example.
All Supabase access is read-only and respects existing client permissions.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st


@st.cache_data(ttl=90, show_spinner=False)
def _read(_db, table: str, columns="*", limit=1000):
    return _db.table(table).select(columns).limit(limit).execute().data or []


def _frame(rows):
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _details(assessment):
    st.markdown("#### Assessment evidence and rationale")
    st.write(assessment.get("explanation") or "No explanation recorded.")
    st.caption(
        "Provider: {provider} · methodology: {method} · mode: {mode} · "
        "confidence: {confidence} · approval: {approval} · coverage: {coverage}".format(
            provider=assessment.get("provider") or "Unknown",
            method=assessment.get("methodology_id") or "Unknown",
            mode=assessment.get("calculation_mode") or "Unknown",
            confidence=assessment.get("confidence") or "Unspecified",
            approval=assessment.get("approval_status") or "Unspecified",
            coverage=assessment.get("coverage_status") or "Unspecified",
        )
    )


# Global event contracts; Hormuz is a regression case, not a regional data model.
HORMUZ_TEST_EVENTS = {
    "EVT_UAE_20260303_FOIZ_FIRE", "EVT_UAE_20260306_FOIZ_FIRE",
    "EVT_UAE_20260314_FOIZ_FIRE", "EVT_UAE_20260316_FOIZ_LOADING",
    "EVT_UAE_20260317_FOIZ_DRONE_FIRE", "EVT_UAE_20260504_FOIZ_FIRE",
    "EVT_PC_B9129B2E020309238049", "EVT_PC_325039DD8077B8D56471",
    "EVT_PC_443D3255C9EF186E2496", "EVT_PC_7F937F2DD46439FA434D",
    "EVT_PC_C25E3439971AF3BC7668",
}


def render_hormuz_case_study(db):
    """Editorial case-study card, not the global geographic data model."""
    st.subheader("Hormuz and Gulf of Oman")
    st.caption("Regional case study · connected maritime and energy-infrastructure exposure")
    try:
        cases = _read(db, "pc_v_security_hormuz_stories", "*", 150)
    except Exception:
        st.info("The editorial evidence view is not installed yet. Run the Security editorial SQL migration.")
        return
    if not cases:
        st.info("No reviewed case-study evidence was returned.")
        return
    try:
        notes = _read(db, "pc_v_security_editorial_latest", "*", 100)
        owned = [r for r in notes if r.get("region_code") == "HORMUZ_GULF_OF_OMAN"]
    except Exception:
        owned = []
    if owned:
        last = owned[0]
        with st.container(border=True):
            st.caption("P&C INTELLIGENCE | INDEPENDENT ANALYST NOTE")
            st.markdown("### " + str(last.get("headline") or "Regional assessment"))
            st.write(last.get("executive_summary") or "")
            st.caption(str(last.get("observation_label") or "Unscored draft") +
                       " · Cut-off: " + str(last.get("cut_off_date") or "unknown"))
            with st.expander("Analyst's reasoning and evidence basis"):
                st.write(last.get("analysis") or "")
                st.caption(last.get("source_basis") or "")
    else:
        st.warning("P&C editorial analysis is not loaded. External ratings below are not independent P&C scores.")

    df = pd.DataFrame(cases)
    m = (df["category"] == "Maritime security").sum()
    i = (df["category"] == "Energy infrastructure").sum()
    c1, c2, c3 = st.columns(3)
    c1.metric("Maritime incident records", int(m))
    c2.metric("Energy infrastructure reports", int(i))
    c3.metric("Selected evidence records", len(df))
    st.caption("Selected source records, not the total number of unique regional attacks.")
    date_values = pd.to_datetime(df["occurred_on"], errors="coerce")
    months = date_values.dt.strftime("%Y-%m")
    timeline = pd.DataFrame({"Month": months, "Type": df["category"]})
    timeline = timeline.dropna()
    if not timeline.empty:
        counts = timeline.groupby(["Month", "Type"]).size().unstack(fill_value=0)
        st.bar_chart(counts, y_label="Published incident/evidence records")
    categories = ["All", "Maritime security", "Energy infrastructure"]
    pick = st.segmented_control("Explore incidents", categories, default="All",
                                key="hormuz_editorial_category")
    visible = df if pick == "All" else df[df["category"] == pick]
    for _, r in visible.sort_values("occurred_on", ascending=False).iterrows():
        with st.container(border=True):
            st.markdown("**" + str(r.get("headline") or "Regional development") + "**")
            st.caption(" · ".join(str(v) for v in (
                r.get("occurred_on"), r.get("geographical_area"), r.get("category")
            ) if pd.notna(v)))
            st.write(str(r.get("operational_effect") or "Details under review"))
            st.caption(str(r.get("evidence_label") or "") + " · " +
                       str(r.get("geographical_precision") or ""))
            if r.get("supporting_source") and pd.notna(r.get("supporting_source")):
                st.link_button("Read source", str(r["supporting_source"]))
            with st.expander("Evidence and relationships"):
                st.write("Vessel: " + str(r.get("vessel") or "Not identified"))
                st.write("Company: " + str(r.get("company") or "Not yet linked"))
                st.caption("Canonical record: " + str(r.get("event_id") or ""))
    st.caption("The current map only shows supported coordinate links. No location is invented for these events.")

def render_global_security_risk(db, *, key="global_security_risk"):
    """Render existing risk assessments, timelines and scored components.

    No score is inferred from incident counts or draft methodology thresholds.
    Missing data is shown explicitly. Assessments are grouped by provider and
    domain so third-party ratings cannot silently become P&C independent ratings.
    """
    if not st.toggle("Load regional case study and 30-day intelligence", value=False, key=key+"_load_cases"):
        st.caption("Open this section when needed; the incident map above remains available without these extra database queries.")
    else:
        render_hormuz_case_study(db)
        _render_rolling_30day(db, key)
    st.subheader("Recorded risk assessments")
    st.caption("Rolling time window across all regions and transport modes. Counts are records, not independent attacks.")
    try:
        recent = _read(db, "pc_v_security_30day_feed", "*", 5000)
        recent_df = pd.DataFrame(recent)
        if not recent_df.empty:
            places = ["All locations"] + sorted(set(
                str(v) for v in recent_df["recorded_region"].dropna() if str(v).strip()
            ))
            location = st.selectbox("Recorded region (optional)", places,
                                    key=key+"_rolling_region")
            if location != "All locations":
                recent_df = recent_df[recent_df["recorded_region"] == location]
            st.metric("Developments in selected window", len(recent_df))
            if not recent_df.empty:
                st.bar_chart(
                    recent_df.groupby(["event_date", "editorial_section"]).size()
                    .unstack(fill_value=0),
                    y_label="Event records"
                )
                for _, row in recent_df.sort_values("event_date", ascending=False).head(15).iterrows():
                    with st.container(border=True):
                        st.markdown("**" + str(row.get("headline") or "Development") + "**")
                        st.caption(str(row.get("event_date")) + " · " +
                                   str(row.get("location_label")) + " · " +
                                   str(row.get("editorial_section")))
                        st.write(row.get("operational_effect") or "Operational implications under review.")
                        if row.get("supporting_source"):
                            st.link_button("Supporting source", row["supporting_source"])
            else:
                st.info("No events have this recorded region code in the rolling feed.")
        else:
            st.info("No recent event records available in the rolling window.")
    except Exception as exc:
        st.info("Rolling 30-day feed is not ready. Apply the v3 SQL migration.")
        st.caption(str(exc))

    st.subheader("External and recorded risk assessments")
    if not st.toggle("Load assessment history and components", value=False, key=key+"_load_assessments"):
        st.caption("Load on demand to avoid querying the full risk history at every page refresh.")
        return
    st.caption("These ratings are displayed as attributed source material; a P&C editorial note is not a calibrated score.")
    st.caption(
        "Global risk engine · independent and third-party ratings shown separately. "
        "Incident counts do not constitute a risk rating."
    )
    try:
        raw = _read(
            db,
            "pc_risk_assessments",
            "assessment_id,methodology_id,provider,region_code,domain,"
            "assessment_date,as_known_at,calculation_mode,score,risk_level,"
            "trend,coverage_status,confidence,explanation,approval_status,"
            "superseded_at",
            5000,
        )
    except Exception as exc:
        st.warning("Risk assessments are not accessible with this database connection.")
        st.caption(str(exc))
        return

    assessments = _frame(raw)
    if assessments.empty:
        st.info("No existing risk assessments are available to this application.")
        return

    assessments["region_code"] = assessments["region_code"].fillna("Unassigned").astype(str)
    assessments["provider"] = assessments["provider"].fillna("Unknown").astype(str)
    assessments["domain"] = assessments["domain"].fillna("Unspecified").astype(str)

    regions = sorted(assessments["region_code"].unique(),\n                     key=lambda v: (v != "HORMUZ_GULF_OF_OMAN", v))
    default = next((i for i, v in enumerate(regions) if v == "HORMUZ_GULF_OF_OMAN"), 0)
    col1, col2, col3 = st.columns([2, 1, 1])
    region = col1.selectbox("Assessment geography", regions, index=default, key=key+"_region")
    scoped = assessments[assessments["region_code"] == region].copy()
    # Keep proprietary assessments distinct from imported GSA/provider material.
    pc_mask = scoped["provider"].str.contains(r"(?i)^(P&C|PC|Power.*Corridors)$", regex=True, na=False)
    own_count = int(pc_mask.sum())
    st.caption(
        f"P&C-labelled assessments for this geography: {own_count}. "
        f"Third-party/provider assessments: {len(scoped) - own_count}. "
        "A provider rating is not an independently calculated P&C score."
    )
    providers = sorted(scoped["provider"].unique(),
                       key=lambda p: (not bool(__import__("re").match(r"(?i)^(P&C|PC|Power.*Corridors)$", p)), p))

    provider = col2.selectbox("Assessment provider", providers, key=key+"_provider")
    scoped = scoped[scoped["provider"] == provider].copy()
    domains = sorted(scoped["domain"].unique())
    domain = col3.selectbox("Risk domain", domains, key=key+"_domain")
    scoped = scoped[scoped["domain"] == domain].copy()
    scoped["assessment_date"] = pd.to_datetime(scoped["assessment_date"], errors="coerce")
    scoped = scoped.sort_values(["assessment_date", "assessment_id"])

    if scoped.empty:
        st.info("No assessments match the selected geography, provider and domain.")
        return

    dated = scoped.dropna(subset=["assessment_date"])
    latest = dated.iloc[-1].to_dict() if not dated.empty else scoped.iloc[-1].to_dict()
    cols = st.columns(4)
    cols[0].metric("Latest recorded level", str(latest.get("risk_level") or "Not rated"))
    score = latest.get("score")
    cols[1].metric("Stored score", str(score) if pd.notna(score) else "Not scored")
    cols[2].metric("Trend", str(latest.get("trend") or "Not assessed"))
    cols[3].metric("Assessment date", str(latest.get("assessment_date") or "")[:10] or "Unknown")
    _details(latest)

    st.markdown("#### Historical risk timeline")
    plot = dated.copy()
    plot["score"] = pd.to_numeric(plot["score"], errors="coerce")
    plot = plot.dropna(subset=["score"])
    if not plot.empty:
        st.line_chart(plot.set_index("assessment_date")[["score"]], y_label="Recorded score (not recalculated)")
    else:
        st.info("No numeric scores are recorded for these historical assessments.")

    with st.expander("Historical ratings and provenance"):
        show = [
            "assessment_date", "assessment_id", "risk_level", "score", "trend",
            "confidence", "coverage_status", "approval_status", "methodology_id", "calculation_mode",
        ]
        st.dataframe(scoped[show].sort_values("assessment_date", ascending=False),
                     hide_index=True, use_container_width=True)

    try:
        comp_raw = db.table("pc_risk_assessment_components").select(
            "assessment_id,component,component_score,rationale"
        ).eq("assessment_id", int(latest["assessment_id"])).limit(100).execute().data or []
        comps = _frame(comp_raw)
        if not comps.empty:
            comps = comps[comps["assessment_id"].astype(str) == str(latest["assessment_id"])]
        st.markdown("#### Recorded risk drivers")
        if comps.empty:
            st.info("No scored components linked to the selected assessment.")
        else:
            comps = comps.copy()
            comps["component_score"] = pd.to_numeric(comps["component_score"], errors="coerce")
            st.bar_chart(comps.set_index("component")[["component_score"]],
                         y_label="Recorded component score")
            st.dataframe(comps[["component", "component_score", "rationale"]],
                         hide_index=True, use_container_width=True)
    except Exception as exc:
        st.caption("Risk component data unavailable: " + str(exc))

    try:
        link_rows = db.table("pc_risk_assessment_events").select(
            "assessment_id,event_id,relevance,weight,rationale"
        ).eq("assessment_id", int(latest["assessment_id"])).limit(500).execute().data or []
        linked = [r for r in link_rows if str(r.get("assessment_id")) == str(latest["assessment_id"])]
        with st.expander(f"Linked event evidence ({len(linked)})"):
            if linked:
                st.dataframe(pd.DataFrame(linked), hide_index=True, use_container_width=True)
            else:
                st.info("No explicit event links recorded for this assessment.")
    except Exception as exc:
        st.caption("Assessment-event links unavailable: " + str(exc))

    try:
        methodologies = _read(db, "pc_risk_methodologies",
                             "methodology_id,version,description,status,weights,thresholds", 100)
        match = [m for m in methodologies
                 if m.get("methodology_id") == latest.get("methodology_id")]
        if match:
            with st.expander("Methodology and calibration"):
                for method in match:
                    st.write(method.get("description") or "")
                    st.caption("Version: {} · status: {}".format(
                        method.get("version"), method.get("status")))
                    st.json({"weights": method.get("weights"),
                             "thresholds": method.get("thresholds")})
                    if str(method.get("status", "")).lower() == "draft":
                        st.warning("Draft methodology: displayed as configured; no automatic rating is generated.")
    except Exception:
        pass

    st.caption(
        "Only database-stored assessments are displayed. Missing ratings are never "
        "inferred from event frequency. Geographic scope selection uses recorded "
        "region codes, not substring matching of incident narratives."
    )
