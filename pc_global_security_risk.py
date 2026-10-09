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
    """Case-study verification independent of the incident text-search filter."""
    st.subheader("Hormuz + Fujairah | linked evidence")
    st.caption("Cross-geography regression test. FOIZ is outside the Strait but within the Gulf of Oman operating system.")
    try:
        # Existing validated, read-only delivery view, not a new database model.
        rows = _read(db, "pc_v_hormuz_security_evidence", "*", 150)
    except Exception:
        try:
            rows = db.table("pc_events").select(
                "event_id,title,start_date,location,verification_status,record_status,metadata"
            ).in_("event_id", sorted(HORMUZ_TEST_EVENTS)).execute().data or []
        except Exception as exc:
            st.warning("Regional case-study evidence is inaccessible.")
            st.caption(str(exc))
            return
    if not rows:
        st.warning("No case-study records returned. Verify delivery-view permissions and the canonical events.")
        return
    # Restrict the fallback and view to the validated 11-event case study.
    rows = [r for r in rows if r.get("event_id") in HORMUZ_TEST_EVENTS]
    for r in rows:
        if not r.get("exposure_dimension"):
            r["exposure_dimension"] = (
                "energy_infrastructure" if r["event_id"].startswith("EVT_UAE_")
                else "maritime_incident"
            )
    data = pd.DataFrame(rows)
    c1, c2, c3 = st.columns(3)
    c1.metric("Case-study event records", len(data))
    c2.metric("Fujairah observations", int((data["exposure_dimension"] == "energy_infrastructure").sum()))
    c3.metric("Vessel incidents", int((data["exposure_dimension"] == "maritime_incident").sum()))
    st.info(
        "Map limitation: FOIZ and Strait records currently identify a geographic area/corridor, "
        "not verified incident coordinates. They are retained in this evidence view rather "
        "than given invented map pins."
    )
    dates = pd.to_datetime(
        data["start_date"] if "start_date" in data else data.get("uae_date"),
        errors="coerce", utc=True
    )
    chart = pd.DataFrame({
        "month": dates.dt.strftime("%Y-%m").fillna("Unknown"),
        "dimension": data["exposure_dimension"],
    })
    if not chart.empty:
        counts = chart.groupby(["month", "dimension"]).size().unstack(fill_value=0)
        st.bar_chart(counts, y_label="Evidence records (not unique verified attacks)")
    columns = [c for c in (
        "event_id", "start_date", "uae_date", "title", "exposure_dimension",
        "verification_status", "record_status", "imo", "vessel_name",
        "owner_name", "deduplication_status", "map_precision_status"
    ) if c in data.columns]
    st.dataframe(data[columns], hide_index=True, use_container_width=True)
    st.caption(
        "March FOIZ observations need source and consequence reconciliation; "
        "five named vessel incidents have IMO corroboration. "
        "These counts are not P&C risk scores."
    )


def render_global_security_risk(db, *, key="global_security_risk"):
    """Render existing risk assessments, timelines and scored components.

    No score is inferred from incident counts or draft methodology thresholds.
    Missing data is shown explicitly. Assessments are grouped by provider and
    domain so third-party ratings cannot silently become P&C independent ratings.
    """
    render_hormuz_case_study(db)\n    st.subheader("Regional risk assessments")
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

    regions = sorted(assessments["region_code"].unique())
    default = next((i for i, v in enumerate(regions) if "hormuz" in v.lower()), 0)
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
        comp_raw = _read(db, "pc_risk_assessment_components",
                         "assessment_id,component,component_score,rationale", 10000)
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
        link_rows = _read(db, "pc_risk_assessment_events",
                          "assessment_id,event_id,relevance,weight,rationale", 10000)
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
