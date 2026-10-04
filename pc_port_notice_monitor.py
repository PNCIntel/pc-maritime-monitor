from __future__ import annotations

import hashlib
import io
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


def _classify(text: str) -> str:
    s = (text or "").lower()
    tests = [
        ("VESSEL_BAN", ("banning of vessel", "banning of vessels", "banned vessel", "ban imposed on", "prohibit the vessel", "prohibiting the vessel")),
        ("BAN_LIFTED", ("lifting the ban", "lift the ban", "ban has been lifted", "cancellation of ban")),
        ("PORT_ENTRY_RESTRICTION", ("entry restriction", "refusal of access", "port entry", "restricted entry", "prohibited from entering")),
        ("SANCTIONS_ENFORCEMENT", ("sanction", "ofac", "asset freeze", "designated vessel")),
        ("SECURITY", ("security", "marsec", "terror", "piracy", "armed robbery", "isps")),
        ("NAVIGATION_RESTRICTION", ("navigation warning", "notice to mariner", "notices to mariners", "obstruction", "channel closure", "navigation restriction")),
        ("INFRASTRUCTURE_OUTAGE", ("bridge", "lock closure", "outage", "disruption", "dredging", "reclamation")),
        ("PILOTAGE", ("pilotage", "pilot service", "pilot boarding")),
        ("TARIFF_DUES", ("tariff", "dues", "toll", "charges")),
        ("ENVIRONMENTAL", ("oily residue", "oil pollution", "marpol", "waste reception", "ballast water", "pollution")),
        ("DOCUMENTATION", ("documentation", "certificate", "clearance document", "new forms", "declaration form")),
        ("VESSEL_REQUIREMENT", ("vessel requirement", "classification society", "p&i club", "insurance requirement", "condition of entry")),
        ("SAFETY", ("safety", "accident", "hazard", "dangerous goods", "fire")),
        ("OPERATIONS", ("operation", "booking", "transit", "harbour", "harbor", "anchorage", "berth", "tug")),
        ("REGULATORY", ("maritime law", "regulation", "circular", "legal requirement")),
    ]
    for category, words in tests:
        if any(w in s for w in words):
            return category
    return "OTHER"


def _notice_number(title: str):
    text = " ".join(str(title or "").split())
    patterns = [
        r"(?i)\bNTM\s*(?:NO\.?\s*)?([0-9]{1,4}(?:[-/]\d{2,4})?)\b",
        r"(?i)\bFMA\s+(?:CIR(?:CULAR)?\.?)\s*(?:NO\.?\s*)?\(?([0-9]{1,3})\)?\s*(?:OF\s*)?([0-9]{4})\b",
        r"(?i)\b(?:AGENTS?\s+NOTIFICATION|NOTIFICATION)\s*(?:NO\.?|NUMBER|#)?\s*([0-9]{1,3})\s*(?:OF|/|-)\s*([0-9]{4})\b",
        r"(?i)\b(?:CIRCULAR|BULLETIN|ADVISORY|MSIB|MSOB)\s*(?:NO\.?|NUMBER|#)?\s*\(?([A-Z]?[ -]?[0-9]{1,4}(?:[-/]\d{2,4})?)\)?",
        r"\b([AN]-\d{1,3}-\d{4})\b",
        r"\b(\d{1,3}/\d{4})\b",
    ]
    for idx, p in enumerate(patterns):
        m = re.search(p, text)
        if not m:
            continue
        if idx == 1 and len(m.groups()) >= 2:
            return f"FMA-{m.group(1)}-{m.group(2)}"
        if idx == 2 and len(m.groups()) >= 2:
            return f"AN-{int(m.group(1)):02d}-{m.group(2)}"
        value = m.group(1).strip()
        return ("NTM-" + value) if idx == 0 else value
    return None


def _imos(text: str):
    # Discovery-only extraction. Canonical resolution must still validate checksum downstream.
    vals = re.findall(r"(?<!\d)(\d{7})(?!\d)", text or "")
    return sorted(set(vals))


def _valid_imo(value: str) -> bool:
    value = str(value or "").strip()
    return bool(re.fullmatch(r"\d{7}", value) and
                sum(int(n) * w for n, w in zip(value[:6], range(7, 1, -1))) % 10 == int(value[-1]))


def _extract_valid_imos(text: str):
    return sorted({v for v in _imos(text) if _valid_imo(v)})


def _clean_notice_title(title: str) -> str:
    return " ".join(str(title or "").split()).strip(" -–—")


def _is_junk_candidate(title: str, href: str) -> bool:
    t = _clean_notice_title(title).casefold()
    # Generic attachment labels add no intelligence unless their parent notice is fetched.
    if re.fullmatch(r"attachment\s*\d+", t):
        return True
    if t in {"download", "view", "click here", "read more"}:
        return True
    return False


def _fetch_notice_text(url: str, timeout=45):
    headers = {"User-Agent": "PowerCorridors-NoticeMonitor/1.1 (+https://www.powerncorridors.com/)"}
    r = requests.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    content_type = (r.headers.get("content-type") or "").lower()
    final_url = r.url
    data = r.content
    if "pdf" in content_type or final_url.lower().split("?")[0].endswith(".pdf"):
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        parts = [(p.extract_text() or "") for p in reader.pages]
        text = "\n".join(parts)
        return {"text": text, "document_url": final_url, "content_type": "application/pdf",
                "page_count": len(parts), "needs_ocr": len(text.strip()) < 200}
    soup = BeautifulSoup(r.text, "html.parser")
    pdfs = []
    for a in soup.find_all("a", href=True):
        href = urljoin(final_url, a["href"])
        label = " ".join(a.get_text(" ", strip=True).split())
        if href.lower().split("?")[0].endswith(".pdf"):
            pdfs.append((label, href))
    text = soup.get_text("\n", strip=True)
    # Prefer an obvious notice/circular PDF when the index points to an HTML detail page.
    if len(pdfs) == 1:
        child = _fetch_notice_text(pdfs[0][1], timeout=timeout)
        child["html_page_url"] = final_url
        return child
    return {"text": text, "document_url": None, "content_type": content_type or "text/html",
            "page_count": None, "needs_ocr": False, "pdf_candidates": [x[1] for x in pdfs[:10]]}


def enrich_notice(sb, notice: dict):
    fetched = _fetch_notice_text(notice["source_page_url"])
    text = fetched.get("text") or ""
    title = notice.get("title") or ""
    number = notice.get("notice_number") or _notice_number(title) or _notice_number(text[:6000])
    category = _classify(title + "\n" + text[:12000])
    imos = _extract_valid_imos(text)
    status = "NEEDS_OCR" if fetched.get("needs_ocr") else "EXTRACTED"
    low = text.casefold()
    temporal = None
    if any(x in low for x in ("lifting the ban", "ban has been lifted", "lift the ban")):
        temporal = "LIFTED"
    elif any(x in low for x in ("cancelled", "canceled", "hereby cancelled", "superseded", "replaced by")):
        temporal = "SUPERSEDED_OR_CANCELLED"
    metadata = dict(notice.get("metadata") or {})
    metadata["document_fetch"] = {
        "content_type": fetched.get("content_type"),
        "page_count": fetched.get("page_count"),
        "needs_ocr": bool(fetched.get("needs_ocr")),
        "pdf_candidates": fetched.get("pdf_candidates") or [],
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "temporal_signal": temporal,
    }
    update = {
        "notice_number": number,
        "notice_category": category,
        "status": status,
        "document_url": fetched.get("document_url") or notice.get("document_url"),
        "extracted_imo_numbers": imos,
        "raw_excerpt": text[:12000] or notice.get("raw_excerpt"),
        "metadata": metadata,
        "last_seen_at": datetime.now(timezone.utc).isoformat(),
    }
    sb.table("pc_maritime_notices").update(update).eq("notice_id", notice["notice_id"]).execute()
    return {"title": title, "number": number, "category": category, "imos": len(imos),
            "status": status, "document_url": update["document_url"]}



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
        if _is_junk_candidate(title, href):
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
            "title": _clean_notice_title(title)[:1000],
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



def mark_notice_process_error(sb, notice: dict, exc: Exception):
    metadata = dict(notice.get("metadata") or {})
    metadata["process_error"] = {
        "message": str(exc)[:3000],
        "failed_at": datetime.now(timezone.utc).isoformat(),
    }
    sb.table("pc_maritime_notices").update({
        "status": "PROCESS_ERROR",
        "metadata": metadata,
        "last_seen_at": datetime.now(timezone.utc).isoformat(),
    }).eq("notice_id", notice["notice_id"]).execute()


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

    st.subheader("Notice processing")
    all_notices = (sb.table("pc_maritime_notices")
               .select("notice_id,source_id,notice_number,title,notice_category,status,jurisdiction,port_name,source_page_url,document_url,extracted_imo_numbers,metadata,discovered_at,last_seen_at")
               .order("discovered_at", desc=True).limit(1000).execute().data or [])
    if not all_notices:
        st.info("No notices discovered yet. Select sources above and run a check.")
        return

    source_names = {s["source_id"]: s["source_name"] for s in sources}
    total = len(all_notices)
    extracted = sum(1 for n in all_notices if n.get("status") == "EXTRACTED")
    needs_ocr = sum(1 for n in all_notices if n.get("status") == "NEEDS_OCR")
    process_errors = sum(1 for n in all_notices if n.get("status") == "PROCESS_ERROR")
    with_imos = sum(1 for n in all_notices if n.get("extracted_imo_numbers"))
    other = sum(1 for n in all_notices if n.get("notice_category") == "OTHER")
    a,b,c1,d,e,fm = st.columns(6)
    a.metric("Notices", total)
    b.metric("Processed", extracted)
    c1.metric("Needs OCR", needs_ocr)
    d.metric("Process errors", process_errors)
    e.metric("With IMOs", with_imos)
    fm.metric("Unclassified", other)

    st.caption("Discovery finds the official notice. Processing opens the notice/PDF, extracts text and valid IMOs, improves classification and flags documents needing OCR.")

    processable = [n for n in all_notices if n.get("status") in ("DISCOVERED","NEEDS_OCR","PROCESS_ERROR")]
    source_options = sorted({source_names.get(n["source_id"], "") for n in processable if source_names.get(n["source_id"])})
    category_options = sorted({str(n.get("notice_category") or "OTHER") for n in processable})
    fc1, fc2, fc3 = st.columns([2,2,1])
    with fc1:
        process_source = st.selectbox("Processing source", ["All sources"] + source_options, index=0)
    with fc2:
        process_category = st.selectbox("Processing category", ["All categories"] + category_options, index=0)
    with fc3:
        batch_size = st.number_input("Batch size", min_value=1, max_value=50, value=20, step=1)

    queue = [n for n in processable
             if (process_source == "All sources" or source_names.get(n["source_id"], "") == process_source)
             and (process_category == "All categories" or str(n.get("notice_category") or "OTHER") == process_category)]
    queue = queue[:int(batch_size)]
    st.caption(f"{len(queue)} notice(s) queued from the current filters.")

    b1,b2 = st.columns([1,1])
    with b1:
        if st.button("Process next batch", type="primary", disabled=not queue, use_container_width=True):
            progress = st.progress(0.0)
            results=[]
            for i,notice in enumerate(queue,1):
                try:
                    results.append(enrich_notice(sb, notice))
                except Exception as exc:
                    try:
                        mark_notice_process_error(sb, notice, exc)
                    except Exception:
                        pass
                    results.append({"title": notice.get("title"), "status": "PROCESS_ERROR", "error": str(exc)[:300]})
                progress.progress(i/max(len(queue),1))
            st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)
            st.rerun()
    with b2:
        st.info("Use Source + Category to run focused batches, e.g. Fujairah + VESSEL_BAN.")

    with st.expander("Manual notice selection"):
        proc_labels = {n["notice_id"]: f'{source_names.get(n["source_id"], "")} · {n.get("title")}' for n in processable}
        selected_notices = st.multiselect("Select specific notices", options=list(proc_labels),
                                          default=[], format_func=lambda x: proc_labels[x],
                                          max_selections=50)
        if st.button("Process selected notices", disabled=not selected_notices):
            progress = st.progress(0.0)
            results=[]
            rows={n["notice_id"]:n for n in processable}
            for i,nid in enumerate(selected_notices,1):
                try:
                    results.append(enrich_notice(sb, rows[nid]))
                except Exception as exc:
                    try:
                        mark_notice_process_error(sb, rows[nid], exc)
                    except Exception:
                        pass
                    results.append({"title": rows[nid].get("title"), "status": "PROCESS_ERROR", "error": str(exc)[:300]})
                progress.progress(i/max(len(selected_notices),1))
            st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)
            st.rerun()

    st.subheader("Recent discoveries")
    status_filter = st.multiselect("Status", sorted({str(n.get("status") or "") for n in all_notices}),
                                   default=[])
    cat_filter = st.multiselect("Category", sorted({str(n.get("notice_category") or "") for n in all_notices}),
                                default=[])
    filtered = [n for n in all_notices
                if (not status_filter or n.get("status") in status_filter)
                and (not cat_filter or n.get("notice_category") in cat_filter)]
    ndf = pd.DataFrame(filtered[:500])
    ndf.insert(1, "source", ndf["source_id"].map(source_names))
    ndf["imo_count"] = ndf["extracted_imo_numbers"].apply(lambda x: len(x or []))
    display_cols = [c for c in ["discovered_at","source","notice_number","title","notice_category","status","jurisdiction","port_name","imo_count","source_page_url","document_url"] if c in ndf.columns]
    st.dataframe(ndf[display_cols], use_container_width=True, hide_index=True,
                 column_config={
                     "source_page_url": st.column_config.LinkColumn("Official source"),
                     "document_url": st.column_config.LinkColumn("Document"),
                 })

    st.caption("Next: promote processed notices into pc_documents and resolve IMO/company/port links only after the source document is successfully extracted.")

