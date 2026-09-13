from __future__ import annotations

from pathlib import Path
import os
import sys
import json
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
SHARED = ROOT / "shared"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

from pc_auth import require_super_admin, service_client

st.set_page_config(
    page_title="P&C Ingestion Console",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
:root{
  --pc-bg:#07111f;
  --pc-panel:#0c1827;
  --pc-panel2:#101f31;
  --pc-line:#223a55;
  --pc-text:#f4f7fb;
  --pc-muted:#aebdcb;
  --pc-gold:#d9b86c;
  --pc-good:#6fcf97;
  --pc-warn:#f2c66d;
  --pc-bad:#ef8d8d;
}
.stApp{background:var(--pc-bg);color:var(--pc-text)}
[data-testid="stSidebar"]{background:#081522!important;border-right:1px solid var(--pc-line)}
[data-testid="stSidebar"] *{color:var(--pc-text)!important}
h1,h2,h3,p,label,span{color:var(--pc-text)}
.block-container{padding-top:1.35rem;max-width:1450px}
.pc-eyebrow{color:var(--pc-gold);font-size:.72rem;letter-spacing:.14em;text-transform:uppercase;margin-bottom:.2rem}
.pc-sub{color:var(--pc-muted);font-size:.94rem;margin-top:-.35rem;margin-bottom:1.2rem}
.pc-card{background:var(--pc-panel);border:1px solid var(--pc-line);border-radius:12px;padding:14px 16px;margin-bottom:10px}
.pc-card h4{margin:0 0 4px 0;color:var(--pc-text)}
.pc-muted{color:var(--pc-muted)}
.pc-clean{color:var(--pc-good);font-weight:650}
.pc-review{color:var(--pc-warn);font-weight:650}
.pc-bad{color:var(--pc-bad);font-weight:650}
[data-testid="stMetric"]{background:var(--pc-panel);border:1px solid var(--pc-line);border-radius:11px;padding:10px 12px}
[data-testid="stMetricLabel"]{color:var(--pc-muted)!important}
[data-testid="stMetricValue"]{color:var(--pc-text)!important}
button[kind="primary"]{border:1px solid #d6b363!important}
.stDataFrame{border:1px solid var(--pc-line);border-radius:10px;overflow:hidden}
div[data-baseweb="select"] > div{background:var(--pc-panel2)!important;color:var(--pc-text)!important;border-color:var(--pc-line)!important}
</style>
""",
    unsafe_allow_html=True,
)

if os.getenv("PC_REQUIRE_AUTH", "false").lower() == "true":
    ctx = require_super_admin()
else:
    ctx = {"global_role": "super_admin", "email": "migration-local"}

sb = service_client()


def _rows(table: str, select: str = "*", limit: int = 5000, order: str | None = None, desc: bool = False):
    try:
        q = sb.table(table).select(select).limit(limit)
        if order:
            q = q.order(order, desc=desc)
        return q.execute().data or []
    except Exception:
        return []


def _job_rows():
    return _rows("pc_ingestion_jobs", "*", 300, "created_at", True)


def _short(value, n=82):
    s = str(value or "").strip().replace("\n", " ")
    return s if len(s) <= n else s[: n - 1] + "…"


def _job_label(row: dict) -> str:
    jid = row.get("ingestion_job_id", "")
    created = str(row.get("created_at") or "")[:16].replace("T", " ")
    status = str(row.get("status") or "unknown").upper()
    query = row.get("research_query") or row.get("query") or row.get("job_name") or row.get("description") or ""
    return f"{created}  ·  {status}  ·  {_short(query, 64)}  ·  {str(jid)[:8]}"


def _staging(job_id: str):
    try:
        return (
            sb.table("pc_staged_records")
            .select(
                "staged_record_id,target_table,natural_key,resolution_status,review_status,"
                "validation_status,resolution_method,payload,created_at"
            )
            .eq("ingestion_job_id", job_id)
            .limit(10000)
            .execute()
            .data
            or []
        )
    except Exception:
        return []


def _exceptions(job_id: str):
    try:
        return (
            sb.table("pc_v_ingestion_operator_exceptions")
            .select("*")
            .eq("ingestion_job_id", job_id)
            .order("created_at")
            .limit(10000)
            .execute()
            .data
            or []
        )
    except Exception:
        rows = _staging(job_id)
        out = []
        for r in rows:
            rs = str(r.get("resolution_status") or "")
            review = str(r.get("review_status") or "pending")
            if review != "applied" or rs in {"PARTIAL", "AMBIGUOUS", "BROKEN_REFERENCE", "INVALID", "UNRESOLVED"}:
                if rs == "AMBIGUOUS":
                    et = "TRUE_AMBIGUITY"
                elif rs == "PARTIAL":
                    et = "MISSING_ENDPOINT"
                elif rs == "BROKEN_REFERENCE":
                    et = "BROKEN_REFERENCE"
                elif rs == "INVALID":
                    et = "UNSUPPORTED_MAPPING"
                else:
                    et = "REVIEW"
                rr = dict(r)
                rr["exception_type"] = et
                out.append(rr)
        return out


def _rpc(name: str, params: dict):
    return sb.rpc(name, params).execute().data


def _status_counts(rows: list[dict]):
    total = len(rows)
    applied = sum(1 for r in rows if r.get("review_status") == "applied" and r.get("validation_status") == "validated")
    ready = sum(1 for r in rows if r.get("resolution_status") == "READY")
    partial = sum(1 for r in rows if r.get("resolution_status") == "PARTIAL")
    ambiguous = sum(1 for r in rows if r.get("resolution_status") == "AMBIGUOUS")
    invalid = sum(1 for r in rows if r.get("resolution_status") in {"INVALID", "BROKEN_REFERENCE"})
    return total, applied, ready, partial, ambiguous, invalid


def _simple_exception_frame(rows: list[dict]) -> pd.DataFrame:
    data = []
    for r in rows:
        p = r.get("payload") or {}
        data.append(
            {
                "Type": r.get("exception_type"),
                "Table": r.get("target_table"),
                "Natural key": r.get("natural_key"),
                "Status": r.get("resolution_status"),
                "Source": p.get("source_name") or p.get("linked_name") or p.get("name"),
                "Target": p.get("target_name"),
                "Relationship": p.get("relationship_type") or p.get("relationship"),
                "Method": r.get("resolution_method"),
            }
        )
    return pd.DataFrame(data)


st.sidebar.markdown("<div class='pc-eyebrow'>Power & Corridors</div>", unsafe_allow_html=True)
st.sidebar.markdown("### Ingestion Console")
st.sidebar.caption("Simple operations first. Legacy admin stays separate.")
PAGE = st.sidebar.radio("", ["Operations", "Exceptions", "Advanced"], label_visibility="collapsed")

jobs = _job_rows()
if not jobs:
    st.error("No ingestion jobs are available, or the database connection failed.")
    st.stop()

labels = {_job_label(j): j for j in jobs}
selected_label = st.sidebar.selectbox("Ingestion job", list(labels.keys()), index=0)
job = labels[selected_label]
job_id = str(job.get("ingestion_job_id"))

st.sidebar.caption(f"Job ID\n{job_id}")

rows = _staging(job_id)
exceptions = _exceptions(job_id)
total, applied, ready, partial, ambiguous, invalid = _status_counts(rows)

if PAGE == "Operations":
    st.markdown("<div class='pc-eyebrow'>Operator workflow</div>", unsafe_allow_html=True)
    st.title("Ingestion")
    st.markdown(
        "<div class='pc-sub'>Run the dependency engine, then look only at genuine exceptions. "
        "The system should create source-backed missing companies, facilities and other safe dependencies automatically.</div>",
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Staged", total)
    c2.metric("Applied", applied)
    c3.metric("Ready", ready)
    c4.metric("Missing endpoint", partial)
    c5.metric("Human review", ambiguous + invalid)

    a, b, c = st.columns([1.25, 1, 3.5])
    with a:
        if st.button("Run auto reconcile", type="primary", use_container_width=True):
            try:
                result = _rpc("pc_reconcile_ingestion_job_v2", {"p_ingestion_job_id": job_id})
                st.success("Reconciliation finished.")
                st.json(result, expanded=False)
                st.rerun()
            except Exception as e:
                st.error(f"Auto reconcile failed: {e}")
    with b:
        if st.button("Apply ready", use_container_width=True):
            result = {}
            try:
                result["generic"] = _rpc("pc_apply_ready_generic_relationships", {"p_ingestion_job_id": job_id})
            except Exception as e:
                result["generic_error"] = str(e)
            try:
                result["event_links"] = _rpc("pc_apply_ready_event_relationships", {"p_ingestion_job_id": job_id})
            except Exception as e:
                result["event_link_error"] = str(e)
            st.json(result, expanded=False)
            st.rerun()
    with c:
        if len(exceptions) == 0:
            st.markdown("<div class='pc-card'><span class='pc-clean'>Clean job.</span> No operator exceptions remain.</div>", unsafe_allow_html=True)
        else:
            st.markdown(
                f"<div class='pc-card'><span class='pc-review'>{len(exceptions)} item(s) need attention.</span> "
                "Only these should require a person.</div>",
                unsafe_allow_html=True,
            )

    st.subheader("Needs attention")
    if not exceptions:
        st.success("Nothing to review.")
    else:
        frame = _simple_exception_frame(exceptions)
        st.dataframe(frame, use_container_width=True, hide_index=True, height=min(520, 90 + 36 * len(frame)))

    with st.expander("Job detail", expanded=False):
        st.json(job, expanded=False)
        if rows:
            raw = pd.DataFrame(
                [
                    {
                        "table": r.get("target_table"),
                        "natural_key": r.get("natural_key"),
                        "resolution": r.get("resolution_status"),
                        "review": r.get("review_status"),
                        "validation": r.get("validation_status"),
                        "method": r.get("resolution_method"),
                    }
                    for r in rows
                ]
            )
            st.dataframe(raw, use_container_width=True, hide_index=True)

elif PAGE == "Exceptions":
    st.markdown("<div class='pc-eyebrow'>Human review only</div>", unsafe_allow_html=True)
    st.title("Exceptions")
    st.markdown(
        "<div class='pc-sub'>Ambiguity, conflicting evidence, unsupported mapping or broken references belong here. "
        "Routine missing endpoints should disappear after auto reconcile.</div>",
        unsafe_allow_html=True,
    )

    if not exceptions:
        st.success("No exceptions for this job.")
    else:
        groups: dict[str, list[dict]] = {}
        for r in exceptions:
            groups.setdefault(str(r.get("exception_type") or "REVIEW"), []).append(r)

        for key in ["TRUE_AMBIGUITY", "BROKEN_REFERENCE", "UNSUPPORTED_MAPPING", "MISSING_ENDPOINT", "PENDING_CANONICAL", "REVIEW"]:
            items = groups.get(key, [])
            if not items:
                continue
            st.markdown(f"### {key.replace('_', ' ').title()}  ·  {len(items)}")
            for r in items:
                p = r.get("payload") or {}
                title = r.get("natural_key") or r.get("staged_record_id")
                with st.expander(_short(title, 110), expanded=False):
                    c1, c2 = st.columns([2, 1])
                    with c1:
                        st.write(f"**Table:** {r.get('target_table')}")
                        st.write(f"**Resolution:** {r.get('resolution_status')} — {r.get('resolution_method')}")
                        if p.get("source_name") or p.get("target_name"):
                            st.write(f"**Edge:** {p.get('source_name')} → {p.get('target_name')}")
                        if r.get("suggested_action"):
                            st.info(r.get("suggested_action"))
                    with c2:
                        st.write(f"**Review:** {r.get('review_status')}")
                        st.write(f"**Validation:** {r.get('validation_status')}")
                    st.json(p, expanded=False)

elif PAGE == "Advanced":
    st.markdown("<div class='pc-eyebrow'>Fallback tools</div>", unsafe_allow_html=True)
    st.title("Advanced")
    st.markdown(
        "<div class='pc-sub'>This page is intentionally small. The previous full Power Admin should remain as "
        "<code>pc-power-admin-legacy.py</code> for migrations and specialist maintenance, not day-to-day ingestion.</div>",
        unsafe_allow_html=True,
    )

    st.subheader("Safe maintenance")
    x, y = st.columns(2)
    with x:
        if st.button("Run legacy reconciliation", use_container_width=True):
            try:
                st.json(_rpc("pc_reconcile_ingestion_job", {"p_ingestion_job_id": job_id}), expanded=False)
                st.rerun()
            except Exception as e:
                st.error(str(e))
    with y:
        if st.button("Normalize applied staging", use_container_width=True):
            try:
                st.json(_rpc("pc_normalize_applied_staging", {"p_ingestion_job_id": job_id}), expanded=False)
                st.rerun()
            except Exception as e:
                st.error(str(e))

    st.subheader("Quality summary")
    try:
        st.json(_rpc("pc_ingestion_quality_summary", {"p_ingestion_job_id": job_id}), expanded=False)
    except Exception:
        st.caption("Install SQL 034 to enable the compact quality summary.")

    st.subheader("Recent ingestion jobs")
    recent = []
    for j in jobs[:30]:
        recent.append(
            {
                "created_at": j.get("created_at"),
                "status": j.get("status"),
                "job": _short(j.get("research_query") or j.get("query") or j.get("job_name") or j.get("description"), 90),
                "ingestion_job_id": j.get("ingestion_job_id"),
            }
        )
    st.dataframe(pd.DataFrame(recent), use_container_width=True, hide_index=True)
