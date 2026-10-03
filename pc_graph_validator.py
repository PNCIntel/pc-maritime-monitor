"""Deterministic validation/repair gate for P&C research dossiers.

Runs AFTER AI research/graph synthesis and BEFORE database mapping.
No network calls, no database IDs, no AI. The goal is to prevent uncertain
research wording from becoming stronger canonical facts during publication.
"""
from __future__ import annotations
import copy, re
from datetime import datetime

_VALID_CONF = {"high", "medium", "low"}
_UNCERTAIN_CLAIM = {"unconfirmed", "allegation", "alleged", "reported", "partially confirmed", "contested", "hypothesis"}


def _clean_date(v):
    if v is None:
        return None
    s = str(v).strip()
    if not s or s.casefold() in {"unknown", "none", "null", "n/a", "na", "tbd"}:
        return None
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return None
    try:
        datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        return None
    return s


def _norm(v):
    return " ".join(re.findall(r"[a-z0-9]+", str(v or "").casefold()))


def _valid_imo(v):
    s = str(v or "").strip()
    if not re.fullmatch(r"\d{7}", s):
        return False
    d = [int(x) for x in s]
    return sum(d[i] * (7 - i) for i in range(6)) % 10 == d[6]


def _source_urls(obj):
    vals = obj.get("source_urls") if isinstance(obj, dict) else []
    return [u for u in (vals or []) if isinstance(u, str) and u.startswith(("http://", "https://"))]


def _add(report, bucket, path, reason, before=None, after=None):
    item = {"path": path, "reason": reason}
    if before is not None:
        item["before"] = before
    if after is not None:
        item["after"] = after
    report[bucket].append(item)


def _neutral_event_title(event, graph):
    et = _norm(event.get("event_type"))
    nature = _norm(event.get("event_nature"))
    primary = graph.get("primary_subject") or {}
    subject = str(primary.get("name") or "vessel").strip()
    loc = str(event.get("location") or "").strip()
    if any(x in et or x in nature for x in ("missile", "projectile", "strike", "attack")):
        where = f" in {loc}" if loc else ""
        return f"Projectile strike on {subject}{where}"
    return str(event.get("title") or "Reported incident").strip()


def _has_uncertain_attack_claim(graph):
    for c in graph.get("claims") or []:
        if not isinstance(c, dict):
            continue
        status = _norm(c.get("status"))
        text = _norm(c.get("claim"))
        if status in {_norm(x) for x in _UNCERTAIN_CLAIM} and any(k in text for k in ("missile", "attack", "marines", "projectile", "injured")):
            return True
    return False


def validate_dossier(dossier: dict) -> tuple[dict, dict]:
    """Return (validated_dossier, report).

    Repairs are deterministic. Items with unresolved semantic role conflicts are
    held in validator_holds and are not silently converted into canonical facts.
    """
    out = copy.deepcopy(dossier or {})
    graph = out.setdefault("graph", {})
    report = {"version": "graph-validator-v1", "repairs": [], "holds": [], "dropped": [], "warnings": []}

    # 1) Normalize dates everywhere we know date semantics.
    date_fields = {
        "identity_history": ("valid_from", "valid_to"),
        "events": ("start_date",),
        "transactions": ("announced_date", "effective_date"),
        "relationships": ("effective_from", "effective_to"),
        "projects": ("announced_date", "expected_completion_date"),
        "contracts": ("effective_from", "effective_to", "announced_date", "signed_date", "expiry_date"),
        "timeline": ("date",),
    }
    for section, fields in date_fields.items():
        for i, item in enumerate(graph.get(section) or []):
            if not isinstance(item, dict):
                continue
            for field in fields:
                if field not in item:
                    continue
                before = item.get(field)
                after = _clean_date(before)
                if before != after:
                    item[field] = after
                    _add(report, "repairs", f"graph.{section}[{i}].{field}", "Invalid/unknown date normalized to NULL", before, after)

    # 2) One verified IMO = one vessel; invalid IMO is held, not silently published.
    seen_imo = {}
    kept_mobile = []
    for i, v in enumerate(graph.get("mobile_assets") or []):
        if not isinstance(v, dict):
            continue
        imo = str(v.get("imo") or "").strip()
        if imo and not _valid_imo(imo):
            held = copy.deepcopy(v)
            held["validator_reason"] = "Invalid IMO check digit/format"
            report["holds"].append({"path": f"graph.mobile_assets[{i}]", "reason": held["validator_reason"], "item": held})
            continue
        if imo and imo in seen_imo:
            _add(report, "dropped", f"graph.mobile_assets[{i}]", f"Duplicate physical vessel for IMO {imo}; preserve one canonical vessel")
            continue
        if imo:
            seen_imo[imo] = v.get("name")
        kept_mobile.append(v)
    graph["mobile_assets"] = kept_mobile

    # 3) Former names are identity history, not extra physical vessels. History must have evidence.
    hist = []
    for i, h in enumerate(graph.get("identity_history") or []):
        if not isinstance(h, dict):
            continue
        if not _source_urls(h):
            report["holds"].append({"path": f"graph.identity_history[{i}]", "reason": "No source URL for identity-history claim", "item": h})
            continue
        if h.get("identifier_type") == "name" and not h.get("identifier_value"):
            report["holds"].append({"path": f"graph.identity_history[{i}]", "reason": "Name-history row has no name value", "item": h})
            continue
        hist.append(h)
    graph["identity_history"] = hist

    # 4) Slash-combined legal/operational roles are ambiguous. Hold instead of guessing.
    rels = []
    for i, r in enumerate(graph.get("relationships") or []):
        if not isinstance(r, dict):
            continue
        role = str(r.get("relationship") or "").strip()
        if "/" in role or " and " in role.casefold():
            report["holds"].append({"path": f"graph.relationships[{i}]", "reason": f"Combined relationship role must be resolved before publication: {role}", "item": r})
            continue
        if not _source_urls(r):
            report["holds"].append({"path": f"graph.relationships[{i}]", "reason": "Relationship has no source URL", "item": r})
            continue
        rels.append(r)
    graph["relationships"] = rels

    # 5) Charter is a relationship/service arrangement, not an acquisition transaction.
    txs = []
    for i, t in enumerate(graph.get("transactions") or []):
        if not isinstance(t, dict):
            continue
        typ = _norm(t.get("transaction_type"))
        # Ownership/acquisition-style transactions need at least one identified counterparty.
        if any(k in typ for k in ("sale", "acquisition", "purchase", "merger")) and not (t.get("buyer_name") or t.get("seller_name")):
            report["holds"].append({"path": f"graph.transactions[{i}]", "reason": "Ownership transaction lacks identified buyer/seller; held from canonical transaction publication", "item": t})
            continue
        if "charter" in typ:
            rel = {
                "source_name": t.get("buyer_name"),
                "target_name": t.get("target_name"),
                "relationship": "charterer",
                "effective_from": _clean_date(t.get("effective_date") or t.get("announced_date")),
                "effective_to": None,
                "status": t.get("status"),
                "evidence_summary": t.get("evidence_summary"),
                "source_urls": t.get("source_urls") or [],
                "confidence": t.get("confidence"),
            }
            if rel["source_name"] and rel["target_name"] and _source_urls(rel):
                graph.setdefault("relationships", []).append(rel)
                _add(report, "repairs", f"graph.transactions[{i}]", "Charter converted from acquisition-style transaction to relationship", t, rel)
            else:
                report["holds"].append({"path": f"graph.transactions[{i}]", "reason": "Charter lacks sufficient parties/evidence", "item": t})
            continue
        txs.append(t)
    graph["transactions"] = txs

    # 6) Do not infer an ownership end date from the start of a charter/operating relationship.
    charter_starts = {
        (_norm(r.get("target_name")), r.get("effective_from"))
        for r in graph.get("relationships") or [] if _norm(r.get("relationship")) in {"charterer", "operator", "manager"}
    }
    for i, r in enumerate(graph.get("relationships") or []):
        if not isinstance(r, dict):
            continue
        if _norm(r.get("relationship")) == "owner" and r.get("effective_to"):
            key = (_norm(r.get("target_name")), r.get("effective_to"))
            if key in charter_starts:
                before = r.get("effective_to")
                r["effective_to"] = None
                _add(report, "repairs", f"graph.relationships[{i}].effective_to", "Ownership end date matched a charter/operator start and was not independently evidenced; cleared", before, None)

    # 7) Keep authors/journalists/commentators as source context, not operational graph people.
    people = []
    for i, p in enumerate(graph.get("people") or []):
        if not isinstance(p, dict):
            continue
        pos = _norm(p.get("position"))
        if any(k in pos for k in ("writer", "journalist", "reporter", "correspondent", "investigator", "expert")):
            _add(report, "dropped", f"graph.people[{i}]", "Source author/commentator retained in dossier context but excluded from operational graph")
            continue
        people.append(p)
    graph["people"] = people

    # 8) Security events with uncertain attribution/effects are neutralized structurally.
    uncertain = _has_uncertain_attack_claim(graph)
    for i, e in enumerate(graph.get("events") or []):
        if not isinstance(e, dict):
            continue
        conf = _norm(e.get("confidence"))
        securityish = any(k in _norm(e.get("event_type")) + " " + _norm(e.get("event_nature")) for k in ("attack", "missile", "strike", "projectile"))
        if securityish and (uncertain or conf in {"medium", "low"}):
            before_title = e.get("title")
            neutral = _neutral_event_title(e, graph)
            if neutral and neutral != before_title:
                e["title"] = neutral
                _add(report, "repairs", f"graph.events[{i}].title", "Unconfirmed attribution removed from canonical event title", before_title, neutral)
            before_desc = e.get("description")
            loc = str(e.get("location") or "the reported location")
            date = str(e.get("start_date") or "the reported date")
            e["description"] = (
                f"A vessel was reported struck by a projectile at {loc} on {date}. "
                "Attribution, the vessel identity and reported personnel effects remain subject to verification; "
                "see linked claims and source evidence."
            )
            if before_desc != e["description"]:
                _add(report, "repairs", f"graph.events[{i}].description", "Unconfirmed attribution/personnel effects moved out of factual event description", before_desc, e["description"])
            e["verification_status"] = "reported"

    # 9) Evidence gate on substantive objects.
    for section in ("companies", "mobile_assets", "physical_assets", "events", "transactions", "projects", "contracts", "relationships", "identity_history"):
        cleaned = []
        for i, item in enumerate(graph.get(section) or []):
            if not isinstance(item, dict):
                continue
            if not _source_urls(item):
                report["holds"].append({"path": f"graph.{section}[{i}]", "reason": "No source URL; held from publication", "item": item})
                continue
            cleaned.append(item)
        graph[section] = cleaned

    # 10) Persist validator result and explicit unresolved items in dossier.
    from pc_source_graph import unique
    report["holds"] = unique((graph.get("validator_holds") or []) + report["holds"])
    graph["validator_holds"] = copy.deepcopy(report["holds"])
    graph["validator_report"] = {k: v for k, v in report.items() if k != "holds"}
    out["validated_version"] = "research-first-v3.4"
    out["validation_report"] = report
    return out, report
