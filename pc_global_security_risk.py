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


def render_global_security_risk(db, *, key="global_security_risk"):
    """Render existing risk assessments, timelines and scored components.

    No score is inferred from incident counts or draft methodology thresholds.
    Missing data is shown explicitly. Assessments are grouped by provider and
    domain so third-party ratings cannot silently become P&C independent ratings.
    """
    st.subheader("Regional risk assessments")
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
    providers = sorted(scoped["provider"].unique())
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
