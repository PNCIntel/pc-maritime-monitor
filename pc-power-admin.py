import os
import re
import json
import urllib.request
import urllib.parse
import pandas as pd
import streamlit as st
import psycopg

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

default_dsn = (
    st.secrets.get("SUPABASE_DSN") 
    or st.secrets.get("DB_DSN") 
    or os.getenv("SUPABASE_DSN") 
    or ""
)
DB_DSN = st.sidebar.text_input("Database DSN", value=default_dsn, type="password")

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


from your_auth_module import service_client  # Or your standard sb client initialization

def fetch_database_identities_via_client(sb, table: str) -> list:
    """Uses your existing Supabase URL and service_role/anon secret key instead of a DB password."""
    pk = APPLY_CONFLICT_KEYS.get(table, "id")
    name_col = "title" if table == "pc_events" else "name"
    cols = f"{pk},{name_col}" + (",imo" if table == "pc_mobile_assets" else "")
    
    try:
        response = sb.table(table).select(cols).not_.is_(name_col, "null").limit(5000).execute()
        rows = response.data or []
        results = []
        for r in rows:
            imo = r.get("imo") if table == "pc_mobile_assets" else None
            results.append((str(r.get(pk)), str(r.get(name_col)), imo))
        return results
    except Exception as e:
        st.warning(f"Could not pull {table} registry: {e}")
        return []

# -----------------------------------------------------------------------------
# 4. VIEW: MAIN WORKSPACE
# -----------------------------------------------------------------------------
st.title("Universal Intake & Reconciliation Engine")
st.caption("Stage 1 Document Fact Harvester → Preflight Canonical Deduplication")

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
                        st.session_state["audit_logs"] = []
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
        if not DB_DSN:
            st.error("A valid Database DSN is required to perform production registry matching.")
        else:
            with st.spinner("Comparing against canonical identity registers..."):
                audit_logs = []
                deduped_package = []
                tables_to_check = {"pc_entities", "pc_assets", "pc_mobile_assets"}
                
                # Fetch reference indexes
                indexes = {tbl: fetch_database_identities(DB_DSN, tbl) for tbl in tables_to_check}
                
                for item in active_rows:
                    tbl = item.get("table")
                    payload = item.get("payload", {})
                    name_val = payload.get("name") or payload.get("title")
                    
                    if tbl not in tables_to_check or not name_val:
                        deduped_package.append(item)
                        continue
                    
                    candidates = indexes.get(tbl, [])
                    matched_id = None
                    matched_name = None
                    best_score = 0.0
                    
                    # 1. Exact IMO match for vessels
                    if tbl == "pc_mobile_assets" and payload.get("imo"):
                        target_imo = str(payload["imo"]).strip()
                        for c_id, c_name, c_imo in candidates:
                            if c_imo and str(c_imo).strip() == target_imo:
                                matched_id, matched_name, best_score = c_id, c_name, 1.0
                                break
                    
                    # 2. Token similarity fallback
                    if not matched_id:
                        for c_id, c_name, _ in candidates:
                            score = compute_token_ratio(name_val, c_name)
                            if score > best_score:
                                best_score, matched_id, matched_name = score, c_id, c_name
                    
                    # 3. Collision Action Threshold
                    if best_score >= 0.85 and matched_id:
                        pk_col = APPLY_CONFLICT_KEYS.get(tbl, "id")
                        payload[pk_col] = matched_id
                        audit_logs.append({
                            "Status": "REMAP",
                            "Table": tbl,
                            "Incoming Name": name_val,
                            "Canonical Match": f"{matched_name} ({matched_id})",
                            "Score": f"{best_score * 100:.1f}%",
                            "Action": f"Pruned candidate. Bound {pk_col} -> {matched_id}"
                        })
                    else:
                        audit_logs.append({
                            "Status": "NEW",
                            "Table": tbl,
                            "Incoming Name": name_val,
                            "Canonical Match": "None",
                            "Score": f"{best_score * 100:.1f}%",
                            "Action": "Kept as new insertion candidate"
                        })
                    
                    deduped_package.append(item)
                
                st.session_state["active_package"] = deduped_package
                st.session_state["audit_logs"] = audit_logs
    
    if st.session_state["audit_logs"]:
        st.markdown("##### Preflight Identity Audit Results")
        st.dataframe(pd.DataFrame(st.session_state["audit_logs"]), use_container_width=True, hide_index=True)
    
    st.markdown("</div>", unsafe_allow_html=True)