import asyncio
import io
import json
import urllib.request
import urllib.parse
import re
from pathlib import Path
import pandas as pd
import streamlit as st

from your_module import CanonicalGraphLoader, INGESTION_ORDER, APPLY_CONFLICT_KEYS

st.set_page_config(page_title="P&C Intelligent Intake Workspace", page_icon="◈", layout="wide")

st.markdown("""
<style>
:root { --bg: #07111f; --panel: #0d1a2b; --line: #28415f; --text: #f3f6fa; --gold: #d7b66a }
.stApp { background: var(--bg); color: var(--text); }
.pc-card { background: var(--panel); border: 1px solid var(--line); border-radius: 10px; padding: 16px; margin-bottom: 12px; }
.pc-gold-header { color: var(--gold); font-size: 0.82rem; letter-spacing: 0.12em; text-transform: uppercase; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# Secure Dashboard Parameter Controls
DB_DSN = st.sidebar.text_input("Supabase Database URL (DSN)", value="postgresql://postgres:secret_pass@localhost:5432/supabase_db", type="password")
OPENAI_KEY = st.sidebar.text_input("OpenAI API Intelligence Key", value="", type="password")
loader = CanonicalGraphLoader(dsn=DB_DSN)

st.markdown("<div class='pc-gold-header'>Power & Corridors Graph Extraction Workspace</div>", unsafe_allow_html=True)
st.title("◈ Universal AI Ingestion & Deduplication Portal")

if "active_package" not in st.session_state: st.session_state["active_package"] = []
if "deduped_package" not in st.session_state: st.session_state["deduped_package"] = []

# ===============================================================
# COMPONENT 1: INTEL EXTRACTOR PIPELINE
# ===============================================================
st.markdown("### 🤖 Phase 1: Intelligent Document Fact Extraction")
with st.container():
    st.markdown("<div class='pc-card'>", unsafe_allow_html=True)
    input_type = st.radio("Intelligence Input Medium", ["Scrape Public Article URL", "Analyze Custom Text Block"], horizontal=True)
    
    source_data = ""
    source_reference_url = "https://research.pipeline"
    
    if input_type == "Scrape Public Article URL":
        target_url = st.text_input("Target Intelligence Link URL", placeholder="https://seatrade-maritime.com...")
        if target_url.strip():
            source_reference_url = target_url.strip()
            if st.button("Fetch and Extract Article"):
                try:
                    reader_endpoint = f"https://jina.ai{urllib.parse.quote(target_url.strip())}"
                    req = urllib.request.Request(reader_endpoint, headers={"User-Agent": "Mozilla/5.0 P&CLoader"})
                    with urllib.request.urlopen(req, timeout=15) as response:
                        source_data = response.read().decode('utf-8')
                    st.success("Successfully fetched clean text layers from target url.")
                except Exception as e:
                    st.error(f"Proxy retrieval rejected target endpoint: {e}")
    else:
        source_data = st.text_area("Paste News Brief / Intelligence Report Text Here", height=150)

    if source_data.strip():
        if st.button("◈ Run AI Multi-Domain Extraction Pattern", type="primary", use_container_width=True):
            if not OPENAI_KEY.strip():
                st.error("Please supply a valid OpenAI API key in the sidebar configuration deck.")
            else:
                with st.spinner("Extracting schema-compliant graph network segments via LLM..."):
                    try:
                        prompt = f"""
                        Analyze this text and extract entities, locations, vessels, and associations.
                        Return ONLY a valid JSON object matching this contract signature, containing no markdown wrappers:
                        {{
                          "records": [
                            {{
                              "table": "pc_entities",
                              "natural_key": "unique_string_name",
                              "payload": {{"name": "Legal String Name", "entity_type": "Company|Government entity|Port authority", "hq_country": "2-letter code"}}
                            }},
                            {{
                              "table": "pc_mobile_assets",
                              "natural_key": "vessel_name",
                              "payload": {{"name": "Vessel Name String", "asset_type": "vessel", "imo": "7-digit-string"}}
                            }},
                            {{
                              "table": "pc_assets",
                              "natural_key": "port_or_terminal_name",
                              "payload": {{"name": "Infrastructure Name", "asset_type": "Port|Container terminal|Logistics park", "country": "2-letter-code"}}
                            }},
                            {{
                              "table": "pc_events",
                              "natural_key": "event_reference",
                              "payload": {{"title": "Summary Headline", "start_date": "YYYY-MM-DD", "event_nature": "OPERATIONAL|SECURITY"}}
                            }}
                          ]
                        }}
                        Ensure payload attributes match valid database columns exactly. Source evidence URL: {source_reference_url}
                        Source text:
                        {source_data}
                        """
                        api_req = urllib.request.Request(
                            "https://openai.com",
                            data=json.dumps({
                                "model": "gpt-4o",
                                "messages": [{"role": "user", "content": prompt}],
                                "temperature": 0.1,
                                "response_format": {"type": "json_object"}
                            }).encode('utf-8'),
                            headers={"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"}
                        )
                        with urllib.request.urlopen(api_req, timeout=45) as resp:
                            res_json = json.loads(resp.read().decode('utf-8'))
                            ai_content = res_json['choices']['message']['content']
                            extracted_package = json.loads(ai_content)
                            
                            for r in extracted_package.get('records', []):
                                if 'payload' in r:
                                    r['payload']['metadata'] = {"source_url": source_reference_url}
                            
                            st.session_state["active_package"] = extracted_package.get('records', [])
                            st.success(f"AI Fact Engine generated {len(st.session_state['active_package'])} normalized domain rows.")
                    except Exception as ai_fault:
                        st.error(f"Intelligence pipeline parsing fault: {ai_fault}")
    st.markdown("</div>", unsafe_allow_html=True)

# ===============================================================
# COMPONENT 2: FUZZY IDENTITY AUDITOR
# ===============================================================
def compute_normalized_token_ratio(str_a: str, str_b: str) -> float:
    def tokenize(txt: str) -> list: 
        return re.sub(r"[^\w]+", " ", txt.lower()).split()
    tokens_a, tokens_b = set(tokenize(str_a)), set(tokenize(str_b))
    intersection, union = tokens_a.intersection(tokens_b), tokens_a.union(tokens_b)
    return float(len(intersection)) / len(union) if union else 0.0

if st.session_state["active_package"]:
    st.divider()
    st.markdown("### 🔍 Phase 2: Preflight Fuzzy Identity Reconciliation")
    
    identity_tables_to_dedupe = {"pc_entities", "pc_assets", "pc_mobile_assets"}
    package_records = list(st.session_state["active_package"])
    reconciliation_logs, deduped_package = [], []

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    with st.spinner("Downloading live canonical match indexes from production registers..."):
        canonical_indexes = {t: loop.run_until_complete(loader.fetch_existing_identities(t)) for t in identity_tables_to_dedupe}

    for item in package_records:
        table, payload = item['table'], item.get('payload', {})
        name_val = payload.get('name') or payload.get('title', '')
        
        if table not in identity_tables_to_dedupe or not name_val:
            deduped_package.append(item)
            continue

        existing_cluster = canonical_indexes.get(table, [])
        match_found, highest_score, matched_canonical_row = False, 0.0, None

        if table == "pc_mobile_assets" and payload.get('imo'):
            target_imo = str(payload['imo']).strip()
            for c_id, c_name, c_imo in existing_cluster:
                if c_imo and str(c_imo).strip() == target_imo:
                    match_found, matched_canonical_row, highest_score = True, (c_id, c_name), 1.0
                    break

        if not match_found:
            for c_id, c_name, c_imo in existing_cluster:
                score = compute_normalized_token_ratio(name_val, c_name)
                if score > highest_score:
                    highest_score, matched_canonical_row = score, (c_id, c_name)

        if highest_score >= 0.85 and matched_canonical_row:
            c_id, c_name = matched_canonical_row
            reconciliation_logs.append({
                "Target Table": table, 
                "Package Name": name_val, 
                "Match Status": "COLLISION / REMAP", 
                "Canonical Match": f"{c_name} ({c_id})", 
                "Confidence Score": f"{highest_score*100:.1f}%", 
                "Operational Action": f"Pruned candidate generation. Bound reference to: {c_id}"
            })
            pk_col = APPLY_CONFLICT_KEYS.get(table, 'id')
            payload[pk_col] = c_id
