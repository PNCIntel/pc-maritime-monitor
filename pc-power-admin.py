import os
import hashlib
from datetime import datetime, timezone
import re
import json
import urllib.request
import urllib.parse
import pandas as pd
import streamlit as st
import sys
from pathlib import Path
from copy import deepcopy
from urllib.parse import urlparse

# Reuse the existing P&C Supabase client; no PostgreSQL DSN required.
ROOT = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
SHARED = ROOT / "shared"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))
from pc_auth import service_client, require_super_admin

# -----------------------------------------------------------------------------
# 1. PAGE SETUP & MODERN COLOR PALETTE
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="P&C Intake & Deduplication Portal",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Refined palette: Deep Slate (#0f172a), Card Surface (#1e293b), 
# Border Line (#334155), Indigo Accent (#6366f1), Emerald (#10b981), Amber (#f59e0b)
st.markdown("""
<style>
:root {
    --bg-main: #0b1120;
    --card-bg: #131d31;
    --card-inner: #1a2744;
    --border-color: #243554;
    --text-primary: #f8fafc;
    --text-muted: #94a3b8;
    --accent-indigo: #6366f1;
    --accent-emerald: #10b981;
    --accent-amber: #f59e0b;
}

.stApp {
    background-color: var(--bg-main);
    color: var(--text-primary);
}

[data-testid="stSidebar"] {
    background-color: #080d19 !important;
    border-right: 1px solid var(--border-color) !important;
}

.pc-card {
    background: var(--card-bg);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 1.25rem;
    margin-bottom: 1rem;
}

.pc-badge {
    display: inline-block;
    padding: 0.2rem 0.6rem;
    border-radius: 9999px;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.05em;
    text-transform: uppercase;
}
.pc-badge-indigo { background: rgba(99, 102, 241, 0.15); color: #818cf8; border: 1px solid rgba(99, 102, 241, 0.3); }
.pc-badge-emerald { background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); }
.pc-badge-amber { background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); }

/* Text Area and Input Overrides */
[data-baseweb="input"] > div, 
[data-baseweb="textarea"] > div, 
.stTextInput input {
    background-color: var(--card-inner) !important;
    color: var(--text-primary) !important;
    border-color: var(--border-color) !important;
}

.stButton > button {
    border-radius: 6px;
    font-weight: 500;
}
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. CONFIGURATION & CREDENTIALS
# -----------------------------------------------------------------------------
st.sidebar.markdown("### ◈ P&C Admin Deck")
st.sidebar.caption("Universal Multi-Domain Extractor & Fuzzy Auditor")

# A service-role connection must only be exposed to authorized admins.
if os.getenv("PC_REQUIRE_AUTH", "true").lower() == "true":
    require_super_admin()

try:
    sb = service_client()
except Exception as exc:
    st.error("Could not initialize the existing P&C Supabase client.")
    st.stop()
if sb is None:
    st.error("P&C Supabase connection is not configured. Check your existing Streamlit secrets.")
    st.stop()
st.sidebar.success("Using existing P&C Supabase connection")

default_openai_key = (
    st.secrets.get("OPENAI_API_KEY") 
    or st.secrets.get("OPENAI_KEY") 
    or os.getenv("OPENAI_API_KEY") 
    or ""
)
OPENAI_KEY = st.sidebar.text_input("OpenAI Key", value=default_openai_key, type="password")

if "active_package" not in st.session_state:
    st.session_state["active_package"] = []
if "audit_logs" not in st.session_state:
    st.session_state["audit_logs"] = []
if "deduped_package" not in st.session_state:
    st.session_state["deduped_package"] = []

# -----------------------------------------------------------------------------
# 3. HELPER FUNCTIONS: LLM EXTRACTION & FUZZY DEDUPE
# -----------------------------------------------------------------------------
APPLY_CONFLICT_KEYS = {
    "pc_entities": "entity_id",
    "pc_assets": "asset_id",
    "pc_mobile_assets": "mobile_asset_id",
    "pc_relationships": "relationship_id",
    "pc_events": "event_id",
    "pc_trade_corridors": "corridor_key",
}

def call_openai_extraction(text: str, api_key: str, source_url: str) -> list:
    """Calls OpenAI chat completions using the standard endpoint with clean JSON response."""
    endpoint = "https://api.openai.com/v1/chat/completions"
    
    prompt = f"""
    Analyze the intelligence document text and extract material domain entities, assets, vessels, and events.
    Return ONLY a single valid JSON object in this exact schema without markdown backticks:
    {{
      "records": [
        {{
          "table": "pc_entities",
          "natural_key": "unique_string_name",
          "payload": {{"name": "Legal Name", "entity_type": "Company|Government entity|Port authority", "hq_country": "US"}}
        }},
        {{
          "table": "pc_mobile_assets",
          "natural_key": "vessel_name",
          "payload": {{"name": "Vessel Name", "asset_type": "vessel", "imo": "7_digit_imo_or_null"}}
        }},
        {{
          "table": "pc_assets",
          "natural_key": "port_or_terminal_name",
          "payload": {{"name": "Asset Name", "asset_type": "Port|Container terminal|Logistics park", "country": "US"}}
        }},
        {{
          "table": "pc_events",
          "natural_key": "event_reference",
          "payload": {{"title": "Headline", "start_date": "YYYY-MM-DD", "event_nature": "OPERATIONAL|SECURITY"}}
        }}
      ]
    }}
    
    Rules:
    - Omit unknown attributes rather than inventing data.
    - IMO must be exactly 7 digits if verified, otherwise null.
    
    Source Text:
    {text[:20000]}
    """
    
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "response_format": {"type": "json_object"}
    }
    
    req = urllib.request.Request(endpoint, data=json.dumps(payload).encode("utf-8"), headers=headers)
    with urllib.request.urlopen(req, timeout=60) as resp:
        res_data = json.loads(resp.read().decode("utf-8"))
        content = res_data["choices"][0]["message"]["content"]
        extracted = json.loads(content)
        
        records = extracted.get("records", [])
        for r in records:
            if "payload" in r and isinstance(r["payload"], dict):
                r["payload"]["metadata"] = {"source_url": source_url}
        return records


def compute_token_ratio(str_a: str, str_b: str) -> float:
    """Computes Jaccard word token similarity."""
    def tokenize(txt: str):
        return set(re.sub(r"[^\w]+", " ", str(txt).lower()).split())
    tokens_a, tokens_b = tokenize(str_a), tokenize(str_b)
    if not tokens_a or not tokens_b:
        return 0.0
    return float(len(tokens_a & tokens_b)) / float(len(tokens_a | tokens_b))


IDENTITY_COLUMNS = {
    "pc_entities": ("entity_id", "name"),
    "pc_assets": ("asset_id", "name"),
    "pc_mobile_assets": ("mobile_asset_id", "name"),
}


def fetch_database_identities_via_client(sb, table: str, page_size: int = 500) -> list:
    """Read the complete canonical identity registry with stable pagination.

    Any API/database failure raises: a failed lookup is NEVER an empty registry.
    """
    if table not in IDENTITY_COLUMNS:
        raise ValueError(f"Unsupported identity table: {table}")
    pk, name_col = IDENTITY_COLUMNS[table]
    projection = f"{pk},{name_col}" + (",imo" if table == "pc_mobile_assets" else "")
    output = []
    offset = 0
    while True:
        response = (
            sb.table(table).select(projection)
            .not_.is_(name_col, "null")
            .order(pk)
            .range(offset, offset + page_size - 1)
            .execute()
        )
        rows = response.data or []
        for row in rows:
            if not row.get(pk) or not row.get(name_col):
                continue
            output.append((str(row[pk]), str(row[name_col]), row.get("imo")))
        if len(rows) < page_size:
            break
        offset += page_size
    return output


def audit_identities(package: list, registry: dict) -> tuple[list, list]:
    """Build a non-mutating match review. Do not overwrite IDs based on fuzzy names."""
    logs, proposals = [], deepcopy(package)
    for item in proposals:
        table = item.get("table")
        payload = item.get("payload") or {}
        if table not in IDENTITY_COLUMNS or not payload.get("name"):
            continue
        name = str(payload["name"])
        pk = IDENTITY_COLUMNS[table][0]
        candidates = registry.get(table, [])
        exact_imo = []
        imo = str(payload.get("imo") or "").strip()
        if table == "pc_mobile_assets" and re.fullmatch(r"\d{7}", imo):
            exact_imo = [(cid, cname) for cid, cname, cimo in candidates if str(cimo or "").strip() == imo]
        if len(exact_imo) == 1:
            status, candidate_id, candidate_name, score = "IMO MATCH", exact_imo[0][0], exact_imo[0][1], 1.0
        elif len(exact_imo) > 1:
            status, candidate_id, candidate_name, score = "AMBIGUOUS IMO", None, None, 1.0
        else:
            exact_name = [(cid, cname) for cid, cname, _ in candidates if cname.strip().casefold() == name.strip().casefold()]
            if len(exact_name) == 1:
                status, candidate_id, candidate_name, score = "EXACT NAME — REVIEW", exact_name[0][0], exact_name[0][1], 1.0
            elif len(exact_name) > 1:
                status, candidate_id, candidate_name, score = "AMBIGUOUS NAME", None, None, 1.0
            else:
                ranked = sorted(((compute_token_ratio(name, cname), cid, cname) for cid, cname, _ in candidates), reverse=True)
                score, candidate_id, candidate_name = ranked[0] if ranked else (0.0, None, None)
                if score >= 0.65:
                    status = "POSSIBLE MATCH — REVIEW"
                else:
                    status = "NEW CANDIDATE"
                    candidate_id, candidate_name = None, None
        # Proposed remaps are display-only, never silently applied to the package.
        logs.append({
            "Status": status, "Table": table, "Incoming Name": name,
            "Canonical Match": f"{candidate_name} ({candidate_id})" if candidate_id else "None",
            "Score": f"{score * 100:.1f}%",
            "Action": "Review proposed identity; source IDs unchanged" if candidate_id else "Hold for evidence-backed creation or manual review",
            "Proposed Canonical ID": candidate_id or "",
            "Source Package ID": payload.get(pk, ""),
        })
    return logs, proposals

# -----------------------------------------------------------------------------
# 4. VIEW: MAIN WORKSPACE
# -----------------------------------------------------------------------------
st.title("Universal Intake & Reconciliation Engine")
st.caption("Extract → reconcile → review → stage. Staging is not canonical publishing.")

# PHASE 1: FACT HARVESTING
st.markdown("#### Phase 1: Document Fact Extraction")
with st.container():
    st.markdown("<div class='pc-card'>", unsafe_allow_html=True)
    input_mode = st.radio("Input Source", ["Public Web Article", "Paste Text"], horizontal=True)
    
    source_url = "https://internal.pipeline"
    raw_text = ""
    
    if input_mode == "Public Web Article":
        target_url = st.text_input("Article URL", placeholder="https://example.com/shipping-report")
        if target_url.strip():
            source_url = target_url.strip()
            if st.button("Fetch Article Content"):
                with st.spinner("Fetching clear-text snapshot..."):
                    try:
                        reader_endpoint = f"https://r.jina.ai/{urllib.parse.quote(source_url, safe=':/?=')}"
                        req = urllib.request.Request(
                            reader_endpoint, 
                            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
                        )
                        with urllib.request.urlopen(req, timeout=20) as resp:
                            raw_text = resp.read().decode("utf-8", errors="replace")
                        st.session_state["fetched_text"] = raw_text
                        st.success("Successfully fetched clean layer.")
                    except Exception as e:
                        st.error(f"Failed to fetch remote document: {e}")
        raw_text = st.session_state.get("fetched_text", "")
    else:
        raw_text = st.text_area("Paste Raw News / Intelligence Brief", height=160)

    if raw_text.strip():
        if st.button("Run AI Multi-Domain Extraction", type="primary", use_container_width=True):
            if not OPENAI_KEY.strip():
                st.error("OpenAI API Key required. Provide it in the sidebar.")
            else:
                with st.spinner("Extracting structured canonical domain records..."):
                    try:
                        extracted = call_openai_extraction(raw_text, OPENAI_KEY, source_url)
                        st.session_state["active_package"] = extracted
                        st.session_state["source_reference"] = source_url
                        st.session_state["audit_logs"] = []
                        st.session_state["deduped_package"] = []
                        st.session_state["match_confirmations"] = {}
                        st.success(f"Harvested {len(extracted)} valid domain objects.")
                    except Exception as err:
                        st.error(f"Extraction failed: {err}")
    st.markdown("</div>", unsafe_allow_html=True)

# PHASE 2: PREFLIGHT DEDUPLICATION & RECONCILIATION
if st.session_state["active_package"]:
    st.markdown("#### Phase 2: Fuzzy Deduplication & Identity Alignment")
    st.markdown("<div class='pc-card'>", unsafe_allow_html=True)
    
    active_rows = st.session_state["active_package"]
    st.write(f"**Loaded in Memory:** {len(active_rows)} records")
    
    st.dataframe(
        pd.DataFrame([
            {
                "Table": r.get("table"),
                "Natural Key": r.get("natural_key"),
                "Display Name": r.get("payload", {}).get("name") or r.get("payload", {}).get("title"),
                "Identifier": r.get("payload", {}).get("imo") or "—"
            }
            for r in active_rows
        ]),
        use_container_width=True,
        hide_index=True
    )
    
    col1, col2 = st.columns([1, 4])
    with col1:
        run_dedupe = st.button("Run Identity Match", use_container_width=True)
    
    if run_dedupe:
        with st.spinner("Comparing against existing canonical identities..."):
            needed = {r.get("table") for r in active_rows} & set(IDENTITY_COLUMNS)
            # A failed query aborts the ENTIRE audit; never show false NEW records.
            try:
                indexes = {table: fetch_database_identities_via_client(sb, table) for table in sorted(needed)}
            except Exception as exc:
                st.session_state["audit_logs"] = []
                st.session_state["deduped_package"] = []
                st.error(f"Identity audit stopped. Database lookup failed: {exc}")
                st.warning("No identity decisions were made. Check the existing Supabase URL/key and retry.")
            else:
                audit_logs, candidate_package = audit_identities(active_rows, indexes)
                st.session_state["audit_logs"] = audit_logs
                st.session_state["deduped_package"] = candidate_package
                st.session_state["match_confirmations"] = {}
                st.success(f"Lookup completed for {len(needed)} registries; {len(audit_logs)} identities reviewed. No records were written.")

    if st.session_state["audit_logs"]:
        st.markdown("##### Preflight Identity Audit Results")
        st.dataframe(pd.DataFrame(st.session_state["audit_logs"]), use_container_width=True, hide_index=True)
    
    st.markdown("</div>", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# PHASE 3: BATCH-SAFE REVIEW STAGING (NEVER WRITES CANONICAL TABLES)
# -----------------------------------------------------------------------------
# This section deliberately does NOT perform automatic name-based remapping.
# An exact name is a candidate, not proof of a shared legal identity.
STAGEABLE = {"pc_entities", "pc_assets", "pc_mobile_assets", "pc_events",
             "pc_relationships", "pc_event_links", "pc_trade_corridors",
             "pc_corridor_nodes", "pc_corridor_route_references",
             "pc_event_corridor_links", "pc_transport_routes"}
PKS = {**APPLY_CONFLICT_KEYS, "pc_event_links": "event_link_id",
       "pc_transport_routes": "route_id", "pc_corridor_nodes": "corridor_node_key"}
REF_FIELDS = {
    "event_id": "pc_events", "entity_id": "pc_entities",
    "mobile_asset_id": "pc_mobile_assets", "asset_id": "pc_assets",
    "corridor_key": "pc_trade_corridors", "route_id": "pc_transport_routes",
}

def _fingerprint(package):
    return hashlib.sha256(json.dumps(package, sort_keys=True, ensure_ascii=False,
                                      default=str, separators=(",", ":")).encode()).hexdigest()

def _source_urls(payload):
    meta = payload.get("metadata") or {}
    if not isinstance(meta, dict):
        meta = {}
    urls = []
    for item in (meta.get("research_sources") or []):
        if isinstance(item, str): urls.append(item)
        elif isinstance(item, dict) and item.get("url"): urls.append(item["url"])
    for item in (meta.get("source_url"), payload.get("source_url")):
        if isinstance(item, str): urls.append(item)
    return list(dict.fromkeys(u for u in urls if u.startswith(("https://", "http://"))))

def _audit_key(log):
    return (log.get("Table"), log.get("Incoming Name"), log.get("Source Package ID"))

def _propose_stage(package, audit, confirms):
    """Pure planning function; returns rows only, does not change original package."""
    logs = {_audit_key(l): l for l in audit}
    planned = []
    # A mapping is valid only after explicit approval or verified exact IMO.
    confirmed_ids = {}
    for log in audit:
        key = _audit_key(log)
        status = log.get("Status", "")
        candidate = log.get("Proposed Canonical ID")
        approved = status == "IMO MATCH" or confirms.get(key, False)
        if candidate and approved and status in {"IMO MATCH", "EXACT NAME — REVIEW"}:
            old = str(log.get("Source Package ID") or "")
            if old:
                confirmed_ids[(log["Table"], old)] = str(candidate)
    for index, original in enumerate(package):
        table = original.get("table")
        payload = deepcopy(original.get("payload") or {})
        name = payload.get("name") or payload.get("title") or ""
        pk = PKS.get(table)
        audit_log = logs.get((table, name, str(payload.get(pk, ""))))
        status = audit_log.get("Status") if audit_log else "NOT_AUDITED"
        candidate = (audit_log or {}).get("Proposed Canonical ID") or None
        match_approved = (status == "IMO MATCH" or confirms.get(_audit_key(audit_log), False)) if audit_log else False
        confirmed = bool(candidate and match_approved and status in {"IMO MATCH", "EXACT NAME — REVIEW"})
        if confirmed and pk:
            payload[pk] = candidate
        # Only propagate IDs where the source package explicitly identified
        # the endpoint. Never guess relationships from names or proximity.
        unresolved_refs = []
        if table in {"pc_event_links", "pc_relationships", "pc_event_corridor_links",
                     "pc_corridor_route_references"}:
            for field, ref_table in REF_FIELDS.items():
                if payload.get(field):
                    old = str(payload[field])
                    if (ref_table, old) in confirmed_ids:
                        payload[field] = confirmed_ids[(ref_table, old)]
            if table == "pc_event_links":
                linked_type = str(payload.get("linked_type") or "").lower()
                linked_to = {"entity":"pc_entities", "company":"pc_entities",
                             "asset":"pc_assets", "mobile_asset":"pc_mobile_assets",
                             "vessel":"pc_mobile_assets", "corridor":"pc_trade_corridors"}.get(linked_type)
                old = str(payload.get("linked_id") or "")
                if linked_to and (linked_to, old) in confirmed_ids:
                    payload["linked_id"] = confirmed_ids[(linked_to, old)]
                elif linked_to and old and any(
                    r.get("table") == linked_to and str((r.get("payload") or {}).get(PKS.get(linked_to), "")) == old
                    for r in package
                ):
                    unresolved_refs.append(f"linked_id:{old}")
            # If references still point to unconfirmed package-only IDs,
            # the relationship must remain unresolved until review.
            for field, ref_table in REF_FIELDS.items():
                old = str(payload.get(field) or "")
                if old and any(r.get("table") == ref_table and
                               str((r.get("payload") or {}).get(PKS.get(ref_table), "")) == old
                               for r in package) and (ref_table, old) not in confirmed_ids:
                    unresolved_refs.append(f"{field}:{old}")
        if table not in STAGEABLE:
            resolution = "UNRESOLVED"
            reason = "unsupported target table"
        elif confirmed:
            resolution = "MATCHED"
            reason = "verified IMO" if status == "IMO MATCH" else "human-confirmed exact name"
        elif status in {"AMBIGUOUS NAME", "AMBIGUOUS IMO", "POSSIBLE MATCH — REVIEW", "EXACT NAME — REVIEW"}:
            resolution = "UNRESOLVED"
            reason = "identity requires analyst review"
        elif unresolved_refs:
            resolution = "UNRESOLVED"
            reason = "unresolved package references"
        elif status == "NEW CANDIDATE":
            resolution = "NEW"
            reason = "candidate; external verification still required"
        elif table in {"pc_relationships", "pc_event_links", "pc_event_corridor_links",
                       "pc_corridor_route_references"}:
            resolution = "UNRESOLVED"
            reason = "relationship endpoints require verification"
        else:
            resolution = "UNRESOLVED"
            reason = "not identity-audited"
        evidence = _source_urls(payload)
        confidence = original.get("confidence")
        try: confidence = float(confidence) if confidence is not None else None
        except (TypeError, ValueError): confidence = None
        if confidence is not None and not 0 <= confidence <= 1: confidence = None
        details = {"input_index": index, "resolution_reason": reason,
                   "audit_status": status, "source_urls": evidence,
                   "original_payload": original.get("payload") or {},
                   "unresolved_references": unresolved_refs,
                   "package_original_id": (original.get("payload") or {}).get(pk) if pk else None}
        planned.append({"target_table": table, "natural_key": str(original.get("natural_key") or name or index),
                        "action": "REVIEW", "payload": payload, "confidence": confidence,
                        "validation_status": "pending", "review_status": "pending",
                        "resolution_status": resolution,
                        "resolved_entity_id": candidate if confirmed else None,
                        "resolution_method": reason,
                        "resolution_confidence": 1.0 if confirmed and status == "IMO MATCH" else None,
                        "resolution_details": details,
                        "source_record_key": f"input:{index}"})
    return planned

def stage_review_package(sb, package, audit, confirms, source_ref):
    """Idempotent per payload fingerprint. Partial errors are retained for retry."""
    planned = _propose_stage(package, audit, confirms)
    if not planned:
        raise ValueError("No records to stage")
    if any(row["target_table"] not in STAGEABLE for row in planned):
        raise ValueError("Package contains unsupported tables; no records staged")
    digest = _fingerprint({"package": package, "confirmations": [str(k) for k, v in confirms.items() if v]})
    existing = (sb.table("pc_ingestion_jobs").select("ingestion_job_id,status")
                .contains("source_scope", {"package_sha256": digest}).limit(2).execute().data or [])
    if len(existing) > 1:
        raise RuntimeError("Duplicate ingestion jobs detected for this package; review manually")
    if existing:
        job_id, state = existing[0]["ingestion_job_id"], existing[0]["status"]
        if state == "completed":
            return job_id, len(planned), True
        sb.table("pc_ingestion_jobs").update({"status": "running", "error_text": None}) \
          .eq("ingestion_job_id", job_id).execute()
    else:
        response = sb.table("pc_ingestion_jobs").insert({
            "job_type": "PORTAL_EXTRACTION", "title": "Universal Portal Review Staging",
            "status": "running", "started_at": datetime.now(timezone.utc).isoformat(),
            "source_scope": {"source_url": source_ref if source_ref.startswith("http") else None,
                             "package_sha256": digest, "workflow": "review_only"},
            "stats": {"expected_records": len(planned)}}).execute()
        if not response.data:
            raise RuntimeError("Ingestion job was not created")
        job_id = response.data[0]["ingestion_job_id"]
    try:
        # No full-table scans: only staged rows belonging to this particular job.
        prior = (sb.table("pc_staged_records").select("source_record_key")
                 .eq("ingestion_job_id", job_id).range(0, 9999).execute().data or [])
        completed_keys = {row["source_record_key"] for row in prior if row.get("source_record_key")}
        pending = [{"ingestion_job_id": job_id, **row} for row in planned
                   if row["source_record_key"] not in completed_keys]
        for start in range(0, len(pending), 100):
            sb.table("pc_staged_records").insert(pending[start:start + 100]).execute()
        # Confirm count by job; never claim completion on a partial insert.
        actual = (sb.table("pc_staged_records").select("staged_record_id", count="exact")
                  .eq("ingestion_job_id", job_id).limit(1).execute())
        n = actual.count
        if n != len(planned):
            raise RuntimeError(f"Staged count {n} != expected {len(planned)}")
        sb.table("pc_ingestion_jobs").update({"status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "stats": {"expected_records": len(planned), "staged_records": n}}) \
          .eq("ingestion_job_id", job_id).execute()
        return job_id, n, False
    except Exception as exc:
        try:
            sb.table("pc_ingestion_jobs").update({"status": "failed",
                "error_text": str(exc)[:700]}).eq("ingestion_job_id", job_id).execute()
        except Exception:
            pass
        raise

if st.session_state.get("audit_logs") and st.session_state.get("deduped_package"):
    st.divider()
    st.markdown("#### Phase 3: Review and stage (not canonical publish)")
    st.info("Exact name matches require your approval. Ambiguous names remain unresolved. "
            "Staging creates review proposals; it cannot publish canonical records.")
    logs = st.session_state["audit_logs"]
    confirms = st.session_state.setdefault("match_confirmations", {})
    for log in logs:
        if log.get("Status") == "EXACT NAME — REVIEW" and log.get("Proposed Canonical ID"):
            label = f"Confirm {log['Incoming Name']} = {log['Canonical Match']}"
            key = _audit_key(log)
            confirms[key] = st.checkbox(label, value=confirms.get(key, False),
                                        key="confirm_" + hashlib.sha256(repr(key).encode()).hexdigest()[:12])
    preview = _propose_stage(st.session_state["deduped_package"], logs, confirms)
    counts = {k: sum(r["resolution_status"] == k for r in preview)
              for k in ("MATCHED", "NEW", "UNRESOLVED")}
    st.caption(f"Proposals: {len(preview)} · Matched: {counts['MATCHED']} · "
               f"New candidates: {counts['NEW']} · Unresolved: {counts['UNRESOLVED']}")
    st.dataframe(pd.DataFrame([{"Table": r["target_table"], "Name": r["natural_key"],
                                "Resolution": r["resolution_status"],
                                "Reason": r["resolution_method"]} for r in preview]),
                 use_container_width=True, hide_index=True)
    if st.button("Commit review-stage proposals", type="primary", use_container_width=True):
        try:
            job_id, count, already = stage_review_package(
                sb, st.session_state["deduped_package"], logs, confirms,
                st.session_state.get("source_reference", ""))
            if already:
                st.info(f"Package already staged under job {job_id}; no duplicate write.")
            else:
                st.success(f"Staged {count} review proposals in job {job_id}. Canonical tables unchanged.")
        except Exception as exc:
            st.error(f"Review staging failed: {exc}. Check the ingestion job before retrying.")

