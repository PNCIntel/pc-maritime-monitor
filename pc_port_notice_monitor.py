from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup

# Official starter registry. These are INDEX pages, not inferred vessel restrictions.
# Collection discovers source records first; publication into the wider knowledge graph
# remains a separate reviewed step.
STARTER_SOURCES = [
    dict(source_key="uae_rak_agents", source_name="RAK Ports Agents Notifications",
         authority_name="RAK Ports", country_code="AE", country_name="United Arab Emirates",
         region="Gulf", port_name="Ras Al Khaimah", authority_type="PORT_AUTHORITY",
         source_type="AGENTS_NOTIFICATION", source_url="https://www.rakports.ae/marine/",
         parser_kind="GENERIC_LINK_INDEX", notice_classes=["port_entry_restriction","vessel_ban","security","documentation","insurance","operations"], priority=1, poll_minutes=360),
    dict(source_key="uae_fujairah_ntm", source_name="Port of Fujairah Notice to Mariner",
         authority_name="Port of Fujairah", country_code="AE", country_name="United Arab Emirates",
         region="Gulf", port_name="Fujairah", authority_type="PORT_AUTHORITY",
         source_type="NOTICE_TO_MARINER", source_url="https://fujairahport.ae/marine-centre/notice-to-mariner/",
         parser_kind="GENERIC_LINK_INDEX", notice_classes=["navigation","port_entry_restriction","vessel_ban","operations"], priority=1, poll_minutes=360),
    dict(source_key="sg_mpa_media", source_name="MPA Singapore Circulars and Notices",
         authority_name="Maritime and Port Authority of Singapore", country_code="SG", country_name="Singapore",
         region="Southeast Asia", port_name="Singapore", authority_type="MARITIME_PORT_AUTHORITY",
         source_type="MULTI_NOTICE_INDEX", source_url="https://www.mpa.gov.sg/media-centre",
         parser_kind="GENERIC_LINK_INDEX", notice_classes=["port_marine_circular","port_marine_notice","shipping_circular","maritime_security","notice_to_mariners"], priority=1, poll_minutes=360),
    dict(source_key="nl_rotterdam_pin", source_name="Port of Rotterdam Information Notices",
         authority_name="Port of Rotterdam Authority", country_code="NL", country_name="Netherlands",
         region="Europe", port_name="Rotterdam", authority_type="PORT_AUTHORITY",
         source_type="PORT_INFORMATION_NOTICE", source_url="https://pin.portofrotterdam.com/announcements/list",
         parser_kind="ROTTERDAM_PIN", notice_classes=["navigation","infrastructure_outage","pilotage","tug_service","operations"], priority=1, poll_minutes=180),
    dict(source_key="eg_suez_navigation", source_name="Suez Canal Navigation Circulars",
         authority_name="Suez Canal Authority", country_code="EG", country_name="Egypt",
         region="Middle East / North Africa", port_name="Suez Canal", authority_type="CANAL_AUTHORITY",
         source_type="NAVIGATION_CIRCULAR", source_url="https://www.suezcanal.gov.eg/English/Navigation/NavigationCirculars/Pages/default.aspx",
         parser_kind="GENERIC_LINK_INDEX", notice_classes=["canal_transit","tariff","navigation","vessel_requirement"], priority=1, poll_minutes=720),
    dict(source_key="pa_canal_notices", source_name="Panama Canal Notices to Shipping",
         authority_name="Panama Canal Authority", country_code="PA", country_name="Panama",
         region="Central America", port_name="Panama Canal", authority_type="CANAL_AUTHORITY",
         source_type="NOTICE_TO_SHIPPING", source_url="https://pancanal.com/en/maritime-services/notices-to-shipping/",
         parser_kind="GENERIC_LINK_INDEX", notice_classes=["canal_transit","vessel_requirement","operations","security"], priority=1, poll_minutes=720),
    dict(source_key="pa_canal_advisories", source_name="Panama Canal Advisories to Shipping",
         authority_name="Panama Canal Authority", country_code="PA", country_name="Panama",
         region="Central America", port_name="Panama Canal", authority_type="CANAL_AUTHORITY",
         source_type="ADVISORY_TO_SHIPPING", source_url="https://pancanal.com/en/advisories-to-shipping/",
         parser_kind="GENERIC_LINK_INDEX", notice_classes=["canal_transit","booking","tariff","operations"], priority=1, poll_minutes=720),
    dict(source_key="au_amsa_marine_notices", source_name="AMSA Marine Notices",
         authority_name="Australian Maritime Safety Authority", country_code="AU", country_name="Australia",
         region="Oceania", authority_type="NATIONAL_MARITIME_AUTHORITY",
         source_type="MARINE_NOTICE", source_url="https://www.amsa.gov.au/about/regulations-and-standards/index-marine-notices",
         parser_kind="GENERIC_LINK_INDEX", notice_classes=["port_state_control","sanctions","safety","navigation","regulatory"], priority=2, poll_minutes=1440),
    dict(source_key="ca_tc_ship_safety", source_name="Transport Canada Ship Safety Bulletins",
         authority_name="Transport Canada", country_code="CA", country_name="Canada",
         region="North America", authority_type="NATIONAL_MARITIME_AUTHORITY",
         source_type="SHIP_SAFETY_BULLETIN", source_url="https://tc.canada.ca/en/marine-transportation/marine-safety/ship-safety-bulletins",
         parser_kind="GENERIC_LINK_INDEX", notice_classes=["safety","port_state_control","regulatory","navigation"], priority=2, poll_minutes=1440),
    dict(source_key="us_uscg_msib", source_name="USCG Marine Safety Information Bulletins",
         authority_name="United States Coast Guard", country_code="US", country_name="United States",
         region="North America", authority_type="COAST_GUARD",
         source_type="MARINE_SAFETY_INFORMATION_BULLETIN", source_url="https://www.news.uscg.mil/maritime-commons/Category/23890/marine-safety-information-bulletins/",
         parser_kind="GENERIC_LINK_INDEX", notice_classes=["safety","security","regulatory","port_operations"], priority=2, poll_minutes=720),
]

NOTICE_HINTS = (
    "notice", "notification", "circular", "bulletin", "advisory", "shipping",
    "mariner", "marine", "navigation", "port", "vessel", "harbour", "harbor",
    "pilot", "closure", "restriction", "ban", "prohibit", "security", "safety",
)
IGNORE_HINTS = ("privacy", "cookie", "contact", "career", "login", "facebook", "linkedin", "instagram")


def _source_payload(row: dict) -> dict:
    out = dict(row)
    out["notice_classes"] = row.get("notice_classes") or []
    return out


def _tables_ready(sb) -> bool:
    try:
        sb.table("pc_maritime_notice_sources").select("source_id", count="exact").limit(1).execute()
        sb.table("pc_maritime_notices").select("notice_id", count="exact").limit(1).execute()
        return True
    except Exception:
        return False


def seed_sources(sb):
    rows = [_source_payload(x) for x in STARTER_SOURCES]
    return sb.table("pc_maritime_notice_sources").upsert(rows, on_conflict="source_key").execute().data or []


def _classify(title: str) -> str:
    s = (title or "").lower()
    tests = [
        ("VESSEL_BAN", ("banning", "banned vessel", "prohibited from", "prohibition of vessel")),
        ("PORT_ENTRY_RESTRICTION", ("entry restriction", "refusal of access", "port entry", "restricted entry")),
        ("SANCTIONS_ENFORCEMENT", ("sanction", "ofac", "asset freeze")),
        ("SECURITY", ("security", "marsec", "terror", "piracy", "armed robbery")),
        ("NAVIGATION_RESTRICTION", ("navigation", "notice to mariner", "notices to mariners", "obstruction", "closure")),
        ("INFRASTRUCTURE_OUTAGE", ("bridge", "lock", "outage", "disruption")),
        ("PILOTAGE", ("pilotage", "pilot service")),
        ("TARIFF_DUES", ("tariff", "dues", "toll")),
        ("SAFETY", ("safety", "accident", "hazard")),
        ("DOCUMENTATION", ("documentation", "certificate", "clearance document")),
        ("OPERATIONS", ("operation", "booking", "transit", "harbour", "harbor")),
    ]
    for category, words in tests:
        if any(w in s for w in words):
            return category
    return "OTHER"


def _notice_number(title: str):
    patterns = [
        r"(?i)\b(?:agents?\s+notification|notification|notice|circular|bulletin|advisory|periodical|MSIB|MSOB)\s*(?:no\.?|number|#)?\s*([A-Z]?[- ]?\d{1,3}(?:[-/]\d{2,4})?)",
        r"\b([AN]-\d{1,3}-\d{4})\b",
        r"\b(\d{1,3}/\d{4})\b",
    ]
    for p in patterns:
        m = re.search(p, title or "")
        if m:
            return m.group(1).strip()
    return None


def _imos(text: str):
    # Discovery-only extraction. Canonical resolution must still validate checksum downstream.
    vals = re.findall(r"(?<!\d)(\d{7})(?!\d)", text or "")
    return sorted(set(vals))


def _candidate_key(url: str, title: str) -> str:
    return hashlib.sha256((url.strip() + "|" + title.strip()).encode("utf-8")).hexdigest()[:40]


def discover_index(source: dict, timeout=35):
    headers = {"User-Agent": "PowerCorridors-NoticeMonitor/1.0 (+https://www.powerncorridors.com/)"}
    r = requests.get(source["source_url"], headers=headers, timeout=timeout)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    base_host = urlparse(source["source_url"]).netloc.lower().replace("www.", "")
    seen = set()
    out = []
    for a in soup.find_all("a", href=True):
        title = " ".join(a.get_text(" ", strip=True).split())
        href = urljoin(source["source_url"], a.get("href", "").strip())
        if not title or len(title) < 8 or href.startswith(("mailto:", "javascript:")):
            continue
        low = (title + " " + href).lower()
        if any(x in low for x in IGNORE_HINTS):
            continue
        if not any(x in low for x in NOTICE_HINTS):
            continue
        host = urlparse(href).netloc.lower().replace("www.", "")
        if host and base_host and host != base_host and not host.endswith("." + base_host):
            # Keep attached PDFs/CDN documents only when the anchor itself is clearly a notice.
            if not href.lower().endswith(".pdf"):
                continue
        sig = (title.lower(), href)
        if sig in seen:
            continue
        seen.add(sig)
        out.append({
            "source_notice_key": _candidate_key(href, title),
            "notice_number": _notice_number(title),
            "title": title[:1000],
            "notice_category": _classify(title),
            "status": "DISCOVERED",
            "jurisdiction": source.get("country_name"),
            "port_name": source.get("port_name"),
            "source_page_url": href,
            "document_url": href if href.lower().split("?")[0].endswith(".pdf") else None,
            "raw_excerpt": title[:3000],
            "extracted_imo_numbers": _imos(title),
            "metadata": {"index_source_url": source["source_url"], "parser_kind": source.get("parser_kind")},
        })
    return out


def poll_source(sb, source: dict):
    now = datetime.now(timezone.utc).isoformat()
    try:
        candidates = discover_index(source)
        inserted = 0
        for c in candidates:
            c["source_id"] = source["source_id"]
            existing = (sb.table("pc_maritime_notices")
                        .select("notice_id")
                        .eq("source_id", source["source_id"])
                        .eq("source_notice_key", c["source_notice_key"])
                        .limit(1).execute().data or [])
            if existing:
                sb.table("pc_maritime_notices").update({"last_seen_at": now}).eq("notice_id", existing[0]["notice_id"]).execute()
            else:
                sb.table("pc_maritime_notices").insert(c).execute()
                inserted += 1
        sb.table("pc_maritime_notice_sources").update({
            "last_checked_at": now, "last_success_at": now, "last_error": None,
        }).eq("source_id", source["source_id"]).execute()
        return {"source": source["source_name"], "found": len(candidates), "new": inserted, "error": None}
    except Exception as exc:
        sb.table("pc_maritime_notice_sources").update({
            "last_checked_at": now, "last_error": str(exc)[:2000],
        }).eq("source_id", source["source_id"]).execute()
        return {"source": source["source_name"], "found": 0, "new": 0, "error": str(exc)}


def render_port_notice_monitor(sb):
    st.title("Port & Maritime Notice Monitor")
    st.caption("Official port, harbour-master, canal, coast-guard and maritime-regulator notices. Discovery is source-backed; canonical publication remains reviewed.")

    if not _tables_ready(sb):
        st.error("Port-notice tables are not installed yet.")
        st.code("Run sql/20261004_port_notice_monitor.sql in Supabase SQL Editor, then reload this page.", language="text")
        return

    c1, c2 = st.columns([1, 2])
    with c1:
        if st.button("Seed / refresh official starter registry", type="primary", use_container_width=True):
            rows = seed_sources(sb)
            st.success(f"Registry seeded/refreshed: {len(rows) or len(STARTER_SOURCES)} official sources.")
            st.rerun()
    with c2:
        st.info("Starter set covers UAE, Singapore, Rotterdam, Suez, Panama, Australia, Canada and USCG. Add local harbour-master sources through the table below.")

    sources = (sb.table("pc_maritime_notice_sources").select("*")
               .order("priority").order("source_name").execute().data or [])
    if not sources:
        st.warning("No notice sources yet. Seed the official starter registry.")
        return

    src_df = pd.DataFrame(sources)
    st.subheader("Source registry")
    show_cols = [c for c in ["source_name","authority_name","country_name","port_name","source_type","priority","poll_minutes","active","last_success_at","last_error"] if c in src_df.columns]
    st.dataframe(src_df[show_cols], use_container_width=True, hide_index=True)

    active = [s for s in sources if s.get("active")]
    labels = {s["source_id"]: f'{s["source_name"]} · {s.get("country_name") or ""}' for s in active}
    selected = st.multiselect("Sources to check now", options=list(labels), default=list(labels), format_func=lambda x: labels[x])
    if st.button("Check selected official sources now", type="primary", disabled=not selected):
        progress = st.progress(0.0)
        results = []
        selected_rows = [s for s in active if s["source_id"] in selected]
        for i, source in enumerate(selected_rows, 1):
            results.append(poll_source(sb, source))
            progress.progress(i / max(len(selected_rows), 1))
        rdf = pd.DataFrame(results)
        st.dataframe(rdf, use_container_width=True, hide_index=True)
        st.success(f"Check complete: {int(rdf['new'].sum()) if not rdf.empty else 0} new notice candidates.")
        st.rerun()

    st.subheader("Recent discoveries")
    notices = (sb.table("pc_maritime_notices")
               .select("notice_id,source_id,notice_number,title,notice_category,status,jurisdiction,port_name,source_page_url,document_url,extracted_imo_numbers,discovered_at,last_seen_at")
               .order("discovered_at", desc=True).limit(250).execute().data or [])
    if not notices:
        st.info("No notices discovered yet. Select sources above and run a check.")
        return
    ndf = pd.DataFrame(notices)
    source_names = {s["source_id"]: s["source_name"] for s in sources}
    ndf.insert(1, "source", ndf["source_id"].map(source_names))
    display_cols = [c for c in ["discovered_at","source","notice_number","title","notice_category","status","jurisdiction","port_name","extracted_imo_numbers","source_page_url"] if c in ndf.columns]
    st.dataframe(ndf[display_cols], use_container_width=True, hide_index=True,
                 column_config={"source_page_url": st.column_config.LinkColumn("Official source")})

    st.caption("Next layer: document download/storage, full-text extraction, supersession detection and canonical IMO/company/port linking. The schema already preserves those fields so the collector can extend without another data-model reset.")
