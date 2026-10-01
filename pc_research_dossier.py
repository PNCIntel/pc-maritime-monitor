"""P&C research-first source investigator.

The source is researched as a real-world subject before any P&C table mapping occurs.
This module intentionally knows nothing about canonical IDs. It returns core proposals
that the existing queue/resolver/publisher can process, while preserving a research
 dossier for analyst review and later connected enrichment.
"""
from __future__ import annotations
import json, re, urllib.request, time, random
from copy import deepcopy
from urllib.parse import urlsplit
from urllib.error import HTTPError, URLError

MODEL = "gpt-4.1-mini"


def _api(endpoint: str, api_key: str, payload: dict, timeout: int = 140, max_attempts: int = 5) -> dict:
    """Call OpenAI with bounded retry/backoff for transient rate limits/server errors.

    A 429 is common when a multi-source analyst batch launches several web-search
    calls close together. Respect Retry-After when present and otherwise back off
    exponentially. Permanent quota/auth errors surface with the response body so
    the UI can tell the analyst what actually failed.
    """
    url = "https://api.openai.com/v1/" + endpoint
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    last_error = None
    for attempt in range(max_attempts):
        req = urllib.request.Request(
            url, data=body,
            headers={"Authorization": "Bearer " + api_key.strip(), "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except HTTPError as exc:
            raw = ""
            try:
                raw = exc.read().decode("utf-8", errors="replace")[:1800]
            except Exception:
                pass
            detail = raw or str(exc)
            last_error = RuntimeError(f"OpenAI HTTP {exc.code}: {detail}")
            if exc.code not in {429, 500, 502, 503, 504} or attempt >= max_attempts - 1:
                raise last_error
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            try:
                delay = float(retry_after) if retry_after else min(45.0, 3.0 * (2 ** attempt))
            except (TypeError, ValueError):
                delay = min(45.0, 3.0 * (2 ** attempt))
            # tiny jitter prevents two sequential source jobs from re-colliding
            time.sleep(delay + random.uniform(0.2, 0.8))
        except (URLError, TimeoutError, OSError) as exc:
            last_error = RuntimeError(f"OpenAI transport error: {type(exc).__name__}: {exc}")
            if attempt >= max_attempts - 1:
                raise last_error
            time.sleep(min(20.0, 2.0 * (2 ** attempt)))
    raise last_error or RuntimeError("OpenAI request failed")


def _public_url(url: str) -> bool:
    if not isinstance(url, str) or len(url) > 2048:
        return False
    p = urlsplit(url)
    return p.scheme in {"http", "https"} and bool(p.hostname)


def _response_text_and_urls(response: dict) -> tuple[str, list[str]]:
    texts, urls = [], []
    for output in response.get("output", []) or []:
        if not isinstance(output, dict):
            continue
        for piece in output.get("content", []) or []:
            if not isinstance(piece, dict):
                continue
            if piece.get("type") in {"output_text", "text"} and piece.get("text"):
                texts.append(piece["text"])
            for ann in piece.get("annotations") or []:
                u = ann.get("url") if isinstance(ann, dict) else None
                if _public_url(u):
                    urls.append(u)
        for src in output.get("sources", []) or []:
            u = src.get("url") if isinstance(src, dict) else None
            if _public_url(u):
                urls.append(u)
    return "\n".join(texts), list(dict.fromkeys(urls))[:60]


def _json_chat(api_key: str, system: str, prompt: str, max_tokens: int = 5000) -> dict:
    r = _api("chat/completions", api_key, {
        "model": MODEL,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
    })
    return json.loads(r["choices"][0]["message"]["content"])


def investigate_source(source_text: str, source_url: str, focus: str, api_key: str,
                       max_questions: int = 7) -> dict:
    """Research a source before database mapping.

    Three bounded calls per source:
      1) broad web investigation
      2) targeted follow-up web investigation for unresolved questions
      3) synthesis into a real-world graph
    """
    text = (source_text or "")[:36000]
    broad_prompt = f"""
You are the senior research investigator for Power & Corridors.
Research the SOURCE as a real-world problem. Do NOT think about SQL, database tables or IDs.

SOURCE URL: {source_url or 'none'}
DOMAIN HINT: {focus}
SOURCE TEXT:\n{text}

Investigate beyond the supplied text when useful. Prefer primary/official/company/regulator/
registry sources, then strong specialist reporting. Follow identity clues and chronology.
Pay special attention to:
- companies, subsidiaries, parents, joint ventures and acquisitions
- vessels/aircraft/rail/road assets, former names, IMO/registration, owners/operators/managers/charterers
- ports, terminals, railways, airports, industrial and logistics assets
- contracts, investments, transactions, regulatory actions and sanctions
- incidents, protests, disruptions and security events
- dates, locations, corridors and historical changes
- disputed, attributed, unverified or contradictory claims

Do not collapse different roles (owner/operator/manager/charterer). Do not treat announced deals
as completed. A vessel rename is identity history, not a new physical vessel.
Return a concise evidence-led investigation with full public source URLs and clearly list unanswered
questions that materially affect identity, chronology or relationships.
"""
    broad = _api("responses", api_key, {
        "model": MODEL,
        "tools": [{"type": "web_search_preview"}],
        "input": broad_prompt,
        "max_output_tokens": 4200,
    }, timeout=150)
    broad_text, broad_urls = _response_text_and_urls(broad)
    if not broad_text:
        raise RuntimeError("Broad web investigation returned no usable research text")

    q = _json_chat(api_key,
        "You identify only material research gaps. Output JSON only.",
        f"""
From the source and research below, identify the remaining questions that must be answered before
we can build a reliable real-world graph. Return JSON with key `research_questions` containing at
most {max_questions} short, targeted web-search questions. Prioritize identity/history/ownership/
operator/transaction-status/event-attribution questions. Do not ask questions already answered.

SOURCE URL: {source_url or 'none'}
SOURCE TEXT:\n{text[:18000]}
BROAD RESEARCH:\n{broad_text[:26000]}
""", max_tokens=1800)
    questions = [str(x).strip() for x in (q.get("research_questions") or []) if str(x).strip()][:max_questions]

    follow_text, follow_urls = "", []
    if questions:
        follow_prompt = """
Research the following unresolved questions as one investigation. Prefer authoritative sources.
For every answer distinguish verified fact, attributed reporting, allegation and unresolved gaps.
Give full public URLs. If evidence conflicts, preserve the conflict instead of choosing silently.\n\n""" + "\n".join(f"{i+1}. {x}" for i, x in enumerate(questions))
        follow = _api("responses", api_key, {
            "model": MODEL,
            "tools": [{"type": "web_search_preview"}],
            "input": follow_prompt,
            "max_output_tokens": 4200,
        }, timeout=150)
        follow_text, follow_urls = _response_text_and_urls(follow)

    evidence_urls = list(dict.fromkeys(([source_url] if _public_url(source_url) else []) + broad_urls + follow_urls))[:80]
    graph = _json_chat(api_key,
        "You are a meticulous intelligence knowledge-graph analyst. Output JSON only. Never invent identifiers or certainty.",
        f"""
Build a real-world graph from this investigation. Do NOT map to database tables or invent database IDs.
Represent one physical object once. Preserve history instead of overwriting it.

Required JSON keys:
primary_subject {{name,type,summary}},
companies [{{name,entity_type,subtype,country,role,evidence_summary,source_urls,confidence}}],
people [{{name,position,organization,evidence_summary,source_urls,confidence}}],
mobile_assets [{{name,asset_type,subtype,imo,mmsi,registration,call_sign,flag,year_built,evidence_summary,source_urls,confidence}}],
physical_assets [{{name,asset_type,subtype,country,region_city,evidence_summary,source_urls,confidence}}],
identity_history [{{asset_name,imo,identifier_type,identifier_value,valid_from,valid_to,change_reason,source_urls,confidence}}],
events [{{title,start_date,event_nature,event_domain,event_type,location,description,why_it_matters,commercial_implications,assessment,monitoring_indicators,source_urls,confidence}}],
transactions [{{buyer_name,target_name,seller_name,transaction_type,status,announced_date,effective_date,equity_percent,value,currency,regulatory_status,evidence_summary,source_urls,confidence}}],
relationships [{{source_name,target_name,relationship,effective_from,effective_to,status,evidence_summary,source_urls,confidence}}],
projects [{{name,project_type,country,region_city,status,sponsor_name,developer_name,evidence_summary,source_urls,confidence}}],
contracts [{{provider_name,customer_name,contract_type,status,effective_from,effective_to,evidence_summary,source_urls,confidence}}],
locations [{{name,country,region,location_type,source_urls,confidence}}],
claims [{{claim,status,attributed_to,evidence_summary,source_urls}}],
timeline [{{date,description,status,source_urls}}],
research_gaps [strings].

Rules:
- valid IMO is exactly 7 digits; otherwise null.
- former vessel names go in identity_history and may also be the current mobile_assets name only if current.
- distinguish owner/operator/manager/charterer and parent/subsidiary/JV.
- proposed/pending transactions remain proposed/pending until evidence of closing.
- allegations/attribution must stay in claims or appropriately qualified events.
- source_urls on every substantive object must be drawn from the evidence set below.

SOURCE URL: {source_url or 'none'}
SOURCE TEXT:\n{text[:18000]}
BROAD RESEARCH:\n{broad_text[:24000]}
FOLLOW-UP RESEARCH:\n{follow_text[:24000]}
EVIDENCE URLS:\n{json.dumps(evidence_urls)}
""", max_tokens=6500)

    return {
        "version": "research-first-v3",
        "source_url": source_url or None,
        "focus": focus,
        "research_questions": questions,
        "broad_research": broad_text,
        "followup_research": follow_text,
        "evidence_urls": evidence_urls,
        "graph": graph,
    }


def _clean_urls(obj, fallback):
    urls = obj.get("source_urls") if isinstance(obj, dict) else []
    if not isinstance(urls, list):
        urls = []
    out = [u for u in urls if _public_url(u)]
    return list(dict.fromkeys(out + fallback))[:20]


def graph_to_core_records(dossier: dict, source_label: str = "") -> list[dict]:
    """Map a real-world graph to only the core proposal tables.

    Specialist history/transactions/relationships remain in metadata for the connected publisher;
    canonical IDs are resolved later by the existing P&C pipeline.
    """
    graph = dossier.get("graph") or {}
    fallback = ([dossier.get("source_url")] if _public_url(dossier.get("source_url")) else []) + (dossier.get("evidence_urls") or [])[:8]
    records = []

    def meta_for(obj, object_kind):
        return {
            "research_sources": _clean_urls(obj, fallback),
            "ingestion_mode": "AI_RESEARCH_DOSSIER_V3",
            "review_required": True,
            "source_label": source_label,
            "evidence_summary": obj.get("evidence_summary"),
            "research_object_kind": object_kind,
            "dossier_version": dossier.get("version"),
        }

    for c in graph.get("companies") or []:
        name = str(c.get("name") or "").strip()
        if not name: continue
        payload = {"name": name,
                   "entity_type": c.get("entity_type") or "company",
                   "subtype": c.get("subtype"),
                   "hq_country": c.get("country"),
                   "metadata": meta_for(c, "company")}
        records.append({"table":"pc_entities","natural_key":name,"payload":payload,"confidence":c.get("confidence")})

    for a in graph.get("physical_assets") or []:
        name = str(a.get("name") or "").strip()
        if not name: continue
        # Do not turn abstract fleets/teams/programmes into physical assets.
        kind = " ".join(str(a.get(k) or "") for k in ("asset_type","subtype","name")).casefold()
        if any(x in kind for x in ("fleet", "leadership", "commercial team", "regional team")):
            continue
        payload={"name":name,"asset_type":a.get("asset_type") or "infrastructure","subtype":a.get("subtype"),
                 "country":a.get("country"),"region_city":a.get("region_city"),"metadata":meta_for(a,"physical_asset")}
        records.append({"table":"pc_assets","natural_key":name,"payload":payload,"confidence":a.get("confidence")})

    for v in graph.get("mobile_assets") or []:
        name = str(v.get("name") or "").strip()
        if not name: continue
        imo = str(v.get("imo") or "").strip()
        if imo and not re.fullmatch(r"\d{7}", imo): imo = None
        payload={"name":name,"asset_type":v.get("asset_type") or "vessel","subtype":v.get("subtype"),
                 "imo":imo,"mmsi":v.get("mmsi"),"registration":v.get("registration"),"call_sign":v.get("call_sign"),
                 "flag":v.get("flag"),"year_built":v.get("year_built"),"metadata":meta_for(v,"mobile_asset")}
        # Carry only this vessel's identity history into metadata for the connected research/publisher.
        hist=[]
        for h in graph.get("identity_history") or []:
            if imo and str(h.get("imo") or "").strip()==imo:
                hist.append(h)
            elif str(h.get("asset_name") or "").strip().casefold()==name.casefold():
                hist.append(h)
        if hist: payload["metadata"]["identity_history"] = hist
        records.append({"table":"pc_mobile_assets","natural_key":imo or name,"payload":payload,"confidence":v.get("confidence")})

    for e in graph.get("events") or []:
        title=str(e.get("title") or "").strip()
        if not title: continue
        meta=meta_for(e,"event")
        for k in ("why_it_matters","commercial_implications","assessment","monitoring_indicators","verification_status"):
            if e.get(k) is not None: meta[k]=e.get(k)
        # Preserve discovered graph context for later relationship synthesis.
        meta["discovered_relationships"] = graph.get("relationships") or []
        meta["claims"] = graph.get("claims") or []
        meta["transactions"] = graph.get("transactions") or []
        meta["contracts"] = graph.get("contracts") or []
        payload={"title":title,"start_date":e.get("start_date"),"event_nature":e.get("event_nature"),
                 "event_domain":e.get("event_domain"),"event_type":e.get("event_type"),"location":e.get("location"),
                 "description":e.get("description"),"metadata":meta}
        records.append({"table":"pc_events","natural_key":title,"payload":payload,"confidence":e.get("confidence")})

    # Ensure a primary company/vessel is not lost when synthesis omitted it from arrays.
    primary=graph.get("primary_subject") or {}; pname=str(primary.get("name") or "").strip(); ptype=str(primary.get("type") or "").casefold()
    existing={(r["table"], str((r.get("payload") or {}).get("name") or "").casefold()) for r in records}
    if pname and "company" in ptype and ("pc_entities",pname.casefold()) not in existing:
        records.append({"table":"pc_entities","natural_key":pname,"payload":{"name":pname,"entity_type":"company",
            "metadata":{"research_sources":fallback[:20],"ingestion_mode":"AI_RESEARCH_DOSSIER_V3","review_required":True,
                        "source_label":source_label,"research_object_kind":"primary_company"}},"confidence":None})

    # Store graph-wide connected findings once on each primary/core record without creating pseudo-objects.
    compact_graph={k:graph.get(k) or [] for k in ("people","identity_history","transactions","relationships","projects","contracts","locations","claims","timeline","research_gaps","validator_holds")}
    compact_graph["validator_report"] = graph.get("validator_report") or {}
    for r in records:
        m=(r.get("payload") or {}).setdefault("metadata",{})
        m["research_dossier_connected_findings"] = compact_graph
    return records


def research_source_to_records(source_text: str, source_url: str, focus: str, api_key: str,
                               source_label: str = "") -> tuple[list[dict], dict]:
    dossier=investigate_source(source_text,source_url,focus,api_key)
    return graph_to_core_records(dossier,source_label=source_label), dossier
