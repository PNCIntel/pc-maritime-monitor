from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
SHARED = ROOT / "shared"
if str(ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(ROOT))
if str(SHARED) not in os.sys.path:
    os.sys.path.insert(0, str(SHARED))

try:
    from shared.pc_db import client as pc_db_client
except Exception:
    from pc_db import client as pc_db_client

from pc_drilldown import object_record, object_label, preferred_entity_id

LENS = {
    "trade": {
        "brand": "P&C Trade",
        "title": "Trade Intelligence Terminal",
        "deck": "Infrastructure, operators, corridors, capital, capacity and commercial change.",
        "layer2": "Operations & Infrastructure",
        "layer3": "Corporate, Assets & Capital",
        "layer4": "Intelligence & Evidence",
    },
    "intelligence": {
        "brand": "P&C Intelligence",
        "title": "Intelligence Operating Terminal",
        "deck": "Events, actors, infrastructure exposure, monitoring and evidence in one connected workspace.",
        "layer2": "Operating Environment",
        "layer3": "Actors, Assets & Exposure",
        "layer4": "Intelligence & Evidence",
    },
    "sanctions": {
        "brand": "P&C Sanctions",
        "title": "Sanctions & Exposure Terminal",
        "deck": "Identity, ownership, vessels, designations, activity and evidence against the canonical graph.",
        "layer2": "Assets & Activity",
        "layer3": "Ownership & Exposure",
        "layer4": "Designations & Evidence",
    },
    "strategic": {
        "brand": "P&C Strategic Industries",
        "title": "Strategic Industries Terminal",
        "deck": "Defence, coast guard, shipyards, programmes, fleets, contracts and industrial capacity.",
        "layer2": "Facilities & Fleets",
        "layer3": "Programmes & Industrial Capacity",
        "layer4": "Strategic Intelligence & Evidence",
    },
}

OBJECTS = {
    "entity": ("pc_entities", "entity_id", "name", "Company / Organisation"),
    "asset": ("pc_assets", "asset_id", "name", "Infrastructure Node"),
    "mobile_asset": ("pc_mobile_assets", "mobile_asset_id", "name", "Mobile Asset"),
    "event": ("pc_events", "event_id", "title", "Development"),
    "corridor": ("pc_trade_corridors", "corridor_key", "corridor_name", "Corridor"),
}

STRATEGIC_RX = re.compile(
    r"defen|defence|military|navy|naval|coast guard|shipbuild|shipyard|aerospace|"
    r"patrol|frigate|corvette|submarine|icebreaker|security cutter|government programme",
    re.I,
)
SANCTIONS_RX = re.compile(
    r"sanction|ofac|sdn|designation|blocked|dark fleet|shadow fleet|evasion|"
    r"export control|embargo|seizure|intercept",
    re.I,
)
TRADE_RX = re.compile(
    r"port|terminal|rail|airport|cargo|freight|logistics|shipping|container|tanker|"
    r"corridor|capacity|acquisition|investment|berth|service|route|warehouse|dry port",
    re.I,
)


def _sb():
    try:
        return pc_db_client(service=True)
    except Exception:
        return None


def _clean(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, (dict, list)):
        try:
            return json.dumps(v, ensure_ascii=False)
        except Exception:
            return str(v)
    return str(v)


def _norm(v: Any) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", _clean(v).casefold()))


def _meta(row: dict) -> dict:
    m = row.get("metadata")
    if isinstance(m, dict):
        return m
    if isinstance(m, str):
        try:
            x = json.loads(m)
            return x if isinstance(x, dict) else {}
        except Exception:
            return {}
    return {}


@st.cache_data(ttl=60, show_spinner=False)
def _rows(table: str, limit: int = 3000) -> list[dict]:
    sb = _sb()
    if sb is None:
        return []
    try:
        return sb.table(table).select("*").limit(limit).execute().data or []
    except Exception:
        return []


@st.cache_data(ttl=60, show_spinner=False)
def _filtered_rows(table: str, column: str, value: str, limit: int = 500) -> list[dict]:
    sb = _sb()
    if sb is None:
        return []
    try:
        return sb.table(table).select("*").eq(column, value).limit(limit).execute().data or []
    except Exception:
        return []


@st.cache_data(ttl=45, show_spinner=False)
def _terminal_index_ready() -> bool:
    sb=_sb()
    if sb is None:
        return False
    try:
        sb.table("pc_terminal_object_index").select("object_type").limit(1).execute()
        return True
    except Exception:
        return False

@st.cache_data(ttl=45, show_spinner=False)
def _indexed_search(q: str, limit: int=60) -> list[dict]:
    sb=_sb()
    if sb is None or not q.strip():
        return []
    try:
        rows=sb.rpc("pc_terminal_search",{"p_query":q.strip(),"p_limit":limit}).execute().data or []
    except Exception:
        return []
    out=[]
    for r in rows:
        typ=_clean(r.get("object_type"))
        oid=_clean(r.get("object_id"))
        if not typ or not oid:
            continue
        out.append({
            "type":typ,
            "id":oid,
            "name":_clean(r.get("display_name")) or oid,
            "kind":OBJECTS.get(typ,(None,None,None,typ.replace("_"," ").title()))[3] if typ in OBJECTS else typ.replace("_"," ").title(),
            "country":_clean(r.get("country")),
            "subtype":_clean(r.get("subtype")),
            "score":float(r.get("rank_score") or 0),
            "match_reason":"terminal index",
        })
    return out

@st.cache_data(ttl=45, show_spinner=False)
def _indexed_links(typ: str, oid: str, limit: int=1000) -> list[dict]:
    sb=_sb()
    if sb is None:
        return []
    try:
        a=(sb.table("pc_v_terminal_links").select("*")
           .eq("source_type",typ).eq("source_id",str(oid)).limit(limit).execute().data or [])
        b=(sb.table("pc_v_terminal_links").select("*")
           .eq("target_type",typ).eq("target_id",str(oid)).limit(limit).execute().data or [])
    except Exception:
        return []
    seen=set(); out=[]
    for r in a+b:
        k=_clean(r.get("link_key")) or repr(r)
        if k in seen: continue
        seen.add(k); out.append(r)
    return out

def _record_text(row: dict) -> str:
    return " ".join(_clean(v) for v in row.values())


def _company_core_name(value: Any) -> str:
    words=_norm(value).split()
    suffixes={
        "group","holding","holdings","company","co","corporation","corp",
        "limited","ltd","llc","plc","pjsc","sak","sa","inc"
    }
    while words and words[-1] in suffixes:
        words.pop()
    return " ".join(words)

@st.cache_data(ttl=60, show_spinner=False)
def _identity_alias_index() -> dict:
    out={}
    for r in _rows("pc_identity_aliases_v2",10000):
        typ=_clean(r.get("object_type")).casefold()
        if typ=="vessel": typ="mobile_asset"
        cid=_clean(r.get("canonical_id"))
        alias=_clean(r.get("alias_name"))
        if typ in OBJECTS and cid and alias:
            out.setdefault((typ,cid),[]).append(alias)
    return out

def _token_match(query_tokens: list[str], text: str) -> bool:
    tokens=set(_norm(text).split())
    return all(t in tokens for t in query_tokens)

def _search_objects(q: str, lens: str, limit: int = 80) -> list[dict]:
    indexed=_indexed_search(q,limit)
    if indexed:
        # Lens weighting without destroying shared index ranking.
        for x in indexed:
            blob=" ".join([x.get("name",""),x.get("subtype",""),x.get("country","")])
            if lens=="strategic" and STRATEGIC_RX.search(blob): x["score"]+=35
            elif lens=="sanctions" and SANCTIONS_RX.search(blob): x["score"]+=35
            elif lens=="trade" and TRADE_RX.search(blob): x["score"]+=20
        indexed.sort(key=lambda x:(x.get("score",0),x.get("name","")),reverse=True)
        return indexed[:limit]
    qn=_norm(q)
    if len(qn)<2:
        return []
    qtokens=qn.split()
    qcore=_company_core_name(q)
    aliases=_identity_alias_index()
    out=[]

    for typ,(table,pk,name_col,label) in OBJECTS.items():
        rows=_rows(table,5000 if typ in {"entity","asset","mobile_asset"} else 2500)
        for r in rows:
            oid=_clean(r.get(pk))
            if not oid:
                continue
            name=_clean(r.get(name_col)) or oid
            nk=_norm(name)
            core=_company_core_name(name) if typ=="entity" else nk
            alias_list=aliases.get((typ,oid),[])
            alias_norm=[_norm(a) for a in alias_list]

            score=0
            match_reason=""

            # 1) Canonical identity/name matching always wins.
            if nk==qn:
                score=500; match_reason="exact canonical name"
            elif typ=="entity" and qcore and core==qcore:
                score=460; match_reason="same canonical company name"
            elif qn in alias_norm:
                score=440; match_reason="exact canonical alias"
            elif nk.startswith(qn):
                score=400; match_reason="canonical name prefix"
            elif any(a.startswith(qn) for a in alias_norm):
                score=380; match_reason="alias prefix"
            elif _token_match(qtokens,name):
                score=340; match_reason="canonical name terms"
            elif any(_token_match(qtokens,a) for a in alias_list):
                score=320; match_reason="alias terms"
            else:
                # 2) Only then search the wider record. Use token matching rather
                # than substring matching so a query such as 'AD Ports Group'
                # cannot match arbitrary letters inside unrelated metadata.
                blob=_record_text(r)
                if not _token_match(qtokens,blob):
                    continue
                score=80; match_reason="record content"

            blob=_record_text(r)
            if lens=="strategic" and STRATEGIC_RX.search(blob):
                score+=30
            elif lens=="sanctions" and SANCTIONS_RX.search(blob):
                score+=30
            elif lens=="trade" and TRADE_RX.search(blob):
                score+=20

            # Established canonical IDs beat auto/AI shells at equal identity score.
            upper=oid.upper()
            if not any(x in upper for x in ("_AUTO_","ENTITY_AUTO","ASSET_AUTO","MOBILE_AUTO","_AI_")):
                score+=15

            out.append({
                "type":typ,
                "id":oid,
                "name":name,
                "kind":label,
                "country":_clean(r.get("hq_country") or r.get("country") or r.get("flag")),
                "subtype":_clean(r.get("entity_type") or r.get("asset_type") or r.get("event_type") or r.get("corridor_type")),
                "score":score,
                "match_reason":match_reason,
            })

    out.sort(key=lambda x:(x["score"],x["name"]),reverse=True)
    seen=set(); final=[]
    # Hide duplicate company shells with the same normalized/core display identity.
    seen_display=set()
    for x in out:
        k=(x["type"],x["id"])
        if k in seen:
            continue
        display_key=(x["type"],_company_core_name(x["name"]) if x["type"]=="entity" else _norm(x["name"]),x["country"].casefold())
        if display_key in seen_display:
            continue
        seen.add(k); seen_display.add(display_key)
        final.append(x)
        if len(final)>=limit:
            break
    return final

def _set_context(typ: str, oid: str, name: str = ""):
    if typ == "entity":
        try:
            oid2, rec = preferred_entity_id(oid)
            if oid2:
                oid = oid2
                if rec:
                    name = _clean(rec.get("name")) or name
        except Exception:
            pass
    st.session_state["pc_document_browser"] = False
    st.session_state["pc_uae_ofac_overlap"] = False
    st.session_state["pc_terminal_type"] = typ
    st.session_state["pc_terminal_id"] = str(oid)
    st.session_state["pc_terminal_name"] = name or object_label(typ, oid)
    try:
        st.query_params["pc_terminal_type"] = typ
        st.query_params["pc_terminal_id"] = str(oid)
    except Exception:
        pass


def _restore_context():
    if st.session_state.get("pc_terminal_id"):
        return
    try:
        typ = st.query_params.get("pc_terminal_type")
        oid = st.query_params.get("pc_terminal_id")
        if typ and oid:
            _set_context(str(typ), str(oid))
    except Exception:
        pass


def _clear_context():
    for k in ("pc_terminal_type", "pc_terminal_id", "pc_terminal_name"):
        st.session_state.pop(k, None)
    try:
        for k in ("pc_terminal_type", "pc_terminal_id"):
            if k in st.query_params:
                del st.query_params[k]
    except Exception:
        pass


def _context_record():
    typ = st.session_state.get("pc_terminal_type")
    oid = st.session_state.get("pc_terminal_id")
    if not typ or not oid:
        return None, None, None
    if typ == "document":
        rows = _filtered_rows("pc_documents", "document_id", str(oid), 1)
        return typ, oid, rows[0] if rows else None
    if typ == "corridor":
        table, pk, _, _ = OBJECTS[typ]
        rows = _filtered_rows(table, pk, str(oid), 3)
        return typ, oid, rows[0] if rows else None
    if typ=="entity":
        bundle=_entity_identity_bundle(str(oid))
        pid=bundle.get("preferred_id") or str(oid)
        prec=bundle.get("preferred_record") or object_record("entity",pid)
        if pid!=str(oid):
            st.session_state["pc_terminal_id"]=pid
            st.session_state["pc_terminal_name"]=_clean((prec or {}).get("name"))
        return typ,pid,prec
    return typ, oid, object_record(typ, oid)


def _display_location(row: dict) -> str:
    for k in ("region_city", "hq_city", "location", "country", "hq_country", "flag"):
        v = row.get(k)
        if isinstance(v, dict):
            v = v.get("name") or v.get("country") or v.get("region")
        if v:
            return _clean(v)
    return ""


def _style(theme: str):
    if theme == "Light":
        p = "--bg:#f4f7fb;--panel:#ffffff;--panel2:#f7f9fc;--line:#dfe6ef;--text:#10213a;--muted:#718096;--gold:#9b7a2c;--blue:#2563eb;--red:#d94841;--green:#149563;--orange:#e58a16;--purple:#7057d9"
    else:
        p = "--bg:#08111e;--panel:#101a29;--panel2:#0c1522;--line:#26364a;--text:#eef4fb;--muted:#9aabc0;--gold:#d0ad59;--blue:#6ea0ff;--red:#df7770;--green:#66b98c;--orange:#eba34b;--purple:#a994ff"
    st.markdown(f"""
    <style>
    :root{{{p}}}
    .stApp{{background:var(--bg);color:var(--text)}}
    [data-testid="stSidebar"]{{background:var(--panel2)!important;border-right:1px solid var(--line);min-width:225px!important}}
    [data-testid="stSidebar"] *{{color:var(--text)!important}}
    .block-container{{max-width:1540px;padding-top:.65rem;padding-bottom:2.5rem}}
    h1{{font-size:2.15rem!important;letter-spacing:-.035em;margin-bottom:.15rem!important}}
    h2{{font-size:1.35rem!important;letter-spacing:-.02em}}
    h3{{font-size:1.05rem!important}}
    h1,h2,h3,h4,p,label,span,li{{color:var(--text)!important}}
    .pc-k{{color:var(--gold);font-size:.66rem;font-weight:800;letter-spacing:.16em;text-transform:uppercase}}
    .pc-sub{{color:var(--muted);font-size:.91rem;margin-bottom:.45rem}}
    .pc-command{{background:var(--panel);border:1px solid var(--line);border-radius:9px;padding:.55rem .8rem;margin:.15rem 0 .8rem;box-shadow:0 1px 3px rgba(18,38,63,.03)}}
    .pc-context{{background:var(--panel);border:1px solid var(--line);border-left:4px solid var(--gold);border-radius:9px;padding:.85rem 1rem;margin:.4rem 0 .8rem}}
    .pc-card{{background:var(--panel);border:1px solid var(--line);border-radius:9px;padding:.8rem .9rem;min-height:110px;box-shadow:0 1px 4px rgba(18,38,63,.035)}}
    .pc-panel-title{{font-size:1.03rem;font-weight:750;margin-bottom:.05rem}}
    .pc-panel-sub{{color:var(--muted);font-size:.76rem;margin-bottom:.45rem}}
    .pc-row{{display:flex;justify-content:space-between;gap:.8rem;padding:.48rem .1rem;border-bottom:1px solid var(--line);font-size:.84rem}}
    .pc-row:last-child{{border-bottom:none}}
    .pc-row-label{{font-weight:650}}
    .pc-row-meta{{color:var(--muted);white-space:nowrap}}
    .pc-tag{{display:inline-block;border-radius:999px;padding:.18rem .46rem;font-size:.68rem;font-weight:700;background:var(--panel2);border:1px solid var(--line);margin-right:.25rem}}
    .pc-muted{{color:var(--muted);font-size:.8rem}}
    [data-testid="stMetric"]{{background:var(--panel);border:1px solid var(--line);padding:.7rem .8rem;border-radius:9px;box-shadow:0 1px 4px rgba(18,38,63,.035);min-height:92px}}
    [data-testid="stMetric"] label{{font-size:.75rem!important;color:var(--muted)!important}}
    [data-testid="stMetricValue"]{{font-size:1.65rem!important;font-weight:760!important}}
    [data-testid="stDataFrame"]{{border:1px solid var(--line);border-radius:8px;overflow:hidden}}
    [data-testid="stExpander"]{{background:var(--panel);border:1px solid var(--line);border-radius:8px}}
    [data-testid="stVerticalBlockBorderWrapper"]{{background:var(--panel);border-color:var(--line)!important;border-radius:9px!important;box-shadow:0 1px 4px rgba(18,38,63,.03)}}
    div.stButton>button{{border:1px solid #b8a16b;color:var(--text);background:var(--panel);border-radius:7px;min-height:2.25rem}}
    div.stButton>button:hover{{border-color:var(--blue);color:var(--blue)}}
    [data-baseweb="input"]>div,[data-baseweb="select"]>div,input{{background:var(--panel)!important;color:var(--text)!important}}
    hr{{border-color:var(--line)!important}}
    </style>
    """, unsafe_allow_html=True)


def _event_links(typ: str, oid: str) -> list[dict]:
    linked_type = "mobile_asset" if typ == "mobile_asset" else typ
    if typ == "event":
        return _filtered_rows("pc_event_links", "event_id", str(oid), 500)
    return _filtered_rows("pc_event_links", "linked_id", str(oid), 500)


def _events_for_object(typ: str, oid: str) -> list[dict]:
    if typ == "event":
        rec = object_record("event", oid)
        return [rec] if rec else []
    if typ=="entity":
        bundle=_entity_identity_bundle(str(oid))
        links=[]
        seen_links=set()
        for eid in bundle.get("ids") or [str(oid)]:
            for l in _event_links("entity",eid):
                lk=_clean(l.get("event_link_id")) or repr((l.get("event_id"),l.get("linked_id"),l.get("relationship")))
                if lk not in seen_links:
                    seen_links.add(lk); links.append(l)
    else:
        links = _event_links(typ, oid)
    out = []
    seen = set()
    for l in links:
        if _norm(l.get("linked_type")) not in {_norm(typ), "vessel" if typ == "mobile_asset" else _norm(typ)}:
            continue
        eid = _clean(l.get("event_id"))
        if not eid or eid in seen:
            continue
        seen.add(eid)
        ev = object_record("event", eid)
        if ev:
            e = dict(ev)
            e["_relationship"] = l.get("relationship")
            out.append(e)
    return sorted(out, key=lambda x: _clean(x.get("start_date")), reverse=True)


def _relationships(typ: str, oid: str) -> list[dict]:
    indexed=_indexed_links(typ,str(oid),1000)
    if indexed:
        out=[]
        for r in indexed:
            is_src=_clean(r.get("source_type"))==typ and _clean(r.get("source_id"))==str(oid)
            out.append({
                "relationship_id":_clean(r.get("link_key")),
                "source_type":_clean(r.get("source_type")),
                "source_id":_clean(r.get("source_id")),
                "target_type":_clean(r.get("target_type")),
                "target_id":_clean(r.get("target_id")),
                "relationship_type":_clean(r.get("relation_type")),
                "relation_family":_clean(r.get("relation_family")),
                "source_name":_clean(r.get("source_name")),
                "target_name":_clean(r.get("target_name")),
                "confidence":_clean(r.get("confidence")),
                "source_table":_clean(r.get("source_table")),
                "event_id":_clean(r.get("event_id")),
                "metadata":r.get("metadata") or {},
            })
        return out

    out = []
    ids=_entity_identity_bundle(str(oid)).get("ids") if typ=="entity" else [str(oid)]
    for side in ("source", "target"):
        for identity_id in (ids or [str(oid)]):
            out.extend(_filtered_rows("pc_relationships", f"{side}_id", str(identity_id), 500))
    seen = set()
    final = []
    for r in out:
        k = _clean(r.get("relationship_id")) or repr((r.get("source_id"), r.get("relationship_type"), r.get("target_id")))
        if k in seen:
            continue
        seen.add(k)
        final.append(r)
    return final


def _company_asset_roles(entity_id: str) -> list[dict]:
    ids=_entity_identity_bundle(str(entity_id)).get("ids") or [str(entity_id)]
    return _multi_filtered_rows("pc_company_asset_roles","entity_id",ids,500)


def _company_corridors(entity_id: str) -> list[dict]:
    ids=_entity_identity_bundle(str(entity_id)).get("ids") or [str(entity_id)]
    return _multi_filtered_rows("pc_company_corridor_roles","entity_id",ids,500)


def _portfolio(entity_id: str) -> list[dict]:
    ids=_entity_identity_bundle(str(entity_id)).get("ids") or [str(entity_id)]
    return _multi_filtered_rows("pc_company_portfolio_positions","holder_entity_id",ids,500)


def _documents_for_entity(entity_id: str) -> list[dict]:
    ids=_entity_identity_bundle(str(entity_id)).get("ids") or [str(entity_id)]
    links=_multi_filtered_rows("pc_document_entity_links","entity_id",ids,500)
    docs = []
    seen = set()
    for l in links:
        did = _clean(l.get("document_id"))
        if not did or did in seen:
            continue
        seen.add(did)
        rows = _filtered_rows("pc_documents", "document_id", did, 2)
        if rows:
            d = dict(rows[0])
            d["_relationship"] = l.get("relationship")
            docs.append(d)
    return docs


def _documents_by_name(name: str, limit: int = 30) -> list[dict]:
    if not name:
        return []
    n = name.casefold()
    docs = []
    for d in _rows("pc_documents", 1500):
        blob = _record_text(d).casefold()
        if n in blob:
            docs.append(d)
            if len(docs) >= limit:
                break
    return docs


def _related_table(table: str, oid: str, name: str = "", limit: int = 120) -> list[dict]:
    rows = _rows(table, 2500)
    o = str(oid).casefold()
    n = name.casefold().strip()
    out = []
    for r in rows:
        blob = _record_text(r).casefold()
        if o and o in blob or (n and len(n) >= 5 and n in blob):
            out.append(r)
            if len(out) >= limit:
                break
    return out


def _object_name(typ: str, oid: str) -> str:
    if typ == "corridor":
        rows = _filtered_rows("pc_trade_corridors", "corridor_key", str(oid), 2)
        return _clean(rows[0].get("corridor_name")) if rows else str(oid)
    return object_label(typ, oid)


def _linked_objects_from_relationships(typ: str, oid: str) -> list[dict]:
    out = []
    for r in _relationships(typ, oid):
        src = _clean(r.get("source_id"))
        is_src = src == str(oid)
        ot = _clean(r.get("target_type") if is_src else r.get("source_type")).casefold()
        oi = _clean(r.get("target_id") if is_src else r.get("source_id"))
        if ot == "vessel":
            ot = "mobile_asset"
        if not ot or not oi:
            continue
        nm=_clean(r.get("target_name") if is_src else r.get("source_name"))
        if not nm and ot in OBJECTS:
            nm=_object_name(ot,oi)
        if not nm:
            nm=oi
        out.append({
            "type": ot,
            "id": oi,
            "name": nm,
            "relationship": _clean(r.get("relationship_type") or r.get("relation_type")).replace("_", " "),
            "family": _clean(r.get("relation_family")),
        })
    return out


def _asset_companies(asset: dict) -> list[dict]:
    aid = _clean(asset.get("asset_id"))
    seen = set()
    out = []
    for col, role in (("owner_entity_id", "owner"), ("operator_entity_id", "operator")):
        eid = _clean(asset.get(col))
        if eid and eid not in seen:
            seen.add(eid)
            out.append({"id": eid, "name": _object_name("entity", eid), "role": role})
    for r in _filtered_rows("pc_company_asset_roles", "asset_id", aid, 500):
        eid = _clean(r.get("entity_id"))
        if eid and eid not in seen:
            seen.add(eid)
            out.append({"id": eid, "name": _object_name("entity", eid), "role": _clean(r.get("asset_role"))})
    return out


def _mobile_companies(rec: dict) -> list[dict]:
    seen = set()
    out = []
    for col, role in (("owner_entity_id", "owner"), ("operator_entity_id", "operator"), ("manager_entity_id", "manager")):
        eid = _clean(rec.get(col))
        if eid and eid not in seen:
            seen.add(eid)
            out.append({"id": eid, "name": _object_name("entity", eid), "role": role})
    return out


def _coords_from_record(rec: dict) -> tuple[float,float] | None:
    candidates=[rec,_meta(rec)]
    for src in candidates:
        if not isinstance(src,dict):
            continue
        pairs=[
            ("latitude","longitude"),("lat","lon"),("lat","lng"),
            ("event_latitude","event_longitude"),("location_latitude","location_longitude"),
        ]
        for a,b in pairs:
            try:
                lat=float(src.get(a)); lon=float(src.get(b))
                if -90<=lat<=90 and -180<=lon<=180:
                    return lat,lon
            except Exception:
                pass
        loc=src.get("location")
        if isinstance(loc,dict):
            try:
                lat=float(loc.get("latitude") or loc.get("lat"))
                lon=float(loc.get("longitude") or loc.get("lon") or loc.get("lng"))
                if -90<=lat<=90 and -180<=lon<=180:
                    return lat,lon
            except Exception:
                pass
    return None

def _asset_point(asset_id: str) -> dict | None:
    rec=object_record("asset",asset_id) or {}
    xy=_coords_from_record(rec)
    if not xy:
        return None
    return {
        "lat":xy[0],"lon":xy[1],
        "name":_clean(rec.get("name")) or asset_id,
        "type":_clean(rec.get("asset_type")),
        "id":asset_id,
    }

def _event_spatial_context(rec: dict, oid: str) -> tuple[list[dict],list[dict]]:
    """Resolve an event into mapped points and connected spatial objects."""
    pts=[]; objs=[]; seen=set()

    xy=_coords_from_record(rec)
    if xy:
        pts.append({"lat":xy[0],"lon":xy[1],"name":_clean(rec.get("title")) or "Event location","type":"event"})

    # First: explicit 059/event links.
    for l in _indexed_links("event",str(oid),500) or []:
        is_src=_clean(l.get("source_type"))=="event" and _clean(l.get("source_id"))==str(oid)
        typ=_clean(l.get("target_type") if is_src else l.get("source_type")).casefold()
        lid=_clean(l.get("target_id") if is_src else l.get("source_id"))
        name=_clean(l.get("target_name") if is_src else l.get("source_name"))
        if not typ or not lid:
            continue
        k=(typ,lid)
        if k not in seen:
            seen.add(k)
            objs.append({"type":typ,"id":lid,"name":name or lid,"relationship":_clean(l.get("relation_type"))})
        if typ=="asset":
            p=_asset_point(lid)
            if p: pts.append(p)
        elif typ=="corridor":
            # Pull mapped assets connected to the corridor through the shared link index.
            for cl in _indexed_links("corridor",lid,300):
                cs=_clean(cl.get("source_type"))=="corridor" and _clean(cl.get("source_id"))==lid
                ct=_clean(cl.get("target_type") if cs else cl.get("source_type")).casefold()
                ci=_clean(cl.get("target_id") if cs else cl.get("source_id"))
                if ct=="asset" and ci:
                    p=_asset_point(ci)
                    if p: pts.append(p)

    # Second: event location/title terms against terminal index.
    loc=_display_location(rec)
    title=_clean(rec.get("title"))
    searches=[]
    if loc: searches.append(loc)
    # Useful geographic fragments; avoid treating the whole article headline as a place.
    for textv in (loc,title):
        if not textv: continue
        for token in re.split(r"[,;/]|\bat\b|\bin\b|\bnear\b|\boff\b",textv,flags=re.I):
            token=token.strip()
            if 4<=len(token)<=80 and token.casefold() not in {"germany","united states","united arab emirates"}:
                searches.append(token)
    checked=set()
    for q in searches[:8]:
        nq=_norm(q)
        if not nq or nq in checked: continue
        checked.add(nq)
        for x in _indexed_search(q,12):
            if x.get("type") not in {"asset","corridor"}:
                continue
            k=(x.get("type"),x.get("id"))
            if k in seen: continue
            seen.add(k); objs.append({**x,"relationship":"location/system match"})
            if x.get("type")=="asset":
                p=_asset_point(x.get("id"))
                if p: pts.append(p)
            elif x.get("type")=="corridor":
                for cl in _indexed_links("corridor",x.get("id"),200):
                    cs=_clean(cl.get("source_type"))=="corridor" and _clean(cl.get("source_id"))==x.get("id")
                    ct=_clean(cl.get("target_type") if cs else cl.get("source_type")).casefold()
                    ci=_clean(cl.get("target_id") if cs else cl.get("source_id"))
                    if ct=="asset" and ci:
                        p=_asset_point(ci)
                        if p: pts.append(p)

    # De-dupe coordinates/ids.
    final=[]; pseen=set()
    for p in pts:
        key=(round(float(p["lat"]),5),round(float(p["lon"]),5),p.get("name"))
        if key in pseen: continue
        pseen.add(key); final.append(p)
    return final,objs

def _render_event_system_map(rec: dict, oid: str):
    pts,objs=_event_spatial_context(rec,oid)
    loc=_display_location(rec)
    if pts:
        st.map(pd.DataFrame(pts),latitude="lat",longitude="lon",size=48,zoom=None,use_container_width=True)
        if loc:
            st.caption("Location: "+loc)
    elif loc:
        st.markdown("##### Geographic context")
        st.write(loc)
        st.caption("The event has a named location, but no mapped coordinate or connected mapped node is stored yet.")
    else:
        st.caption("No geographic context has been resolved for this event yet.")

    spatial=[x for x in objs if x.get("type") in {"asset","corridor"}]
    if spatial:
        st.markdown("##### Connected geography / infrastructure")
        view=pd.DataFrame([{
            "Object":x.get("name"),
            "Type":x.get("type"),
            "Relationship":x.get("relationship") or x.get("match_reason"),
        } for x in spatial[:20]])
        st.dataframe(view,hide_index=True,use_container_width=True,height=min(360,100+28*len(view)))
        _open_selector(spatial[:30],f"event_spatial_{oid}","Open mapped / connected object")

def _render_map_for_asset(rec: dict):
    pts = []
    def add(r, label):
        try:
            lat = float(r.get("latitude"))
            lon = float(r.get("longitude"))
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                pts.append({"lat": lat, "lon": lon, "name": label})
        except Exception:
            pass
    add(rec, _clean(rec.get("name")))
    country = _clean(rec.get("country"))
    region = _clean(rec.get("region_city"))
    for r in _rows("pc_assets", 4000):
        if _clean(r.get("asset_id")) == _clean(rec.get("asset_id")):
            continue
        if country and _clean(r.get("country")).casefold() != country.casefold():
            continue
        if region and _clean(r.get("region_city")) and _clean(r.get("region_city")).casefold() != region.casefold():
            continue
        add(r, _clean(r.get("name")))
        if len(pts) >= 40:
            break
    if pts:
        st.map(pd.DataFrame(pts), latitude="lat", longitude="lon", size=40, zoom=None)
    else:
        st.caption("No canonical coordinates are currently stored for this node or its local connected assets.")


def _render_context_header(typ: str, oid: str, rec: dict, lens: str):
    cfg = LENS[lens]
    name = _object_name(typ, oid)
    subtype = _clean(rec.get("entity_type") or rec.get("asset_type") or rec.get("event_type") or rec.get("corridor_type"))
    loc = _display_location(rec)
    st.markdown(
        f"<div class='pc-context'><div class='pc-k'>{cfg['brand']} · selected canonical context</div>"
        f"<h2 style='margin:.15rem 0'>{name}</h2>"
        f"<div class='pc-muted'>{OBJECTS[typ][3]}{(' · '+subtype) if subtype else ''}{(' · '+loc) if loc else ''}</div></div>",
        unsafe_allow_html=True,
    )


def _open_selector(rows: list[dict], key: str, label: str = "Open connected object"):
    if not rows:
        return
    choices = [x for x in rows if x.get("type") in OBJECTS and x.get("id")]
    if not choices:
        return
    pick = st.selectbox(
        label,
        range(len(choices)),
        format_func=lambda i: f"{choices[i].get('name')} · {choices[i].get('relationship') or choices[i].get('type')}",
        key=key,
    )
    if st.button("Open in terminal", key=key + "_open", use_container_width=True):
        x = choices[pick]
        _set_context(x["type"], x["id"], x.get("name"))
        st.rerun()


def _humanize_identifier(value: Any) -> str:
    s=_clean(value)
    if not s:
        return ""
    if s.startswith(("COMP_","ENTITY_","ASSET_","MOBILE_","EVT_","IDEAL_","PROJ_","CONTRACT_")):
        return ""
    return s.replace("_"," ")

def _entity_chip(eid: str) -> str:
    return _object_name("entity",eid) if eid else ""

def _asset_chip(aid: str) -> str:
    return _object_name("asset",aid) if aid else ""

def _render_dossier_pane(typ: str, oid: str, rec: dict, lens: str):
    st.markdown("### Dossier & Ownership")
    st.caption("Canonical identity, control, portfolio and commercial structure.")

    name=_object_name(typ,oid)
    st.markdown(f"#### {name}")
    kind=_clean(rec.get("entity_type") or rec.get("asset_type") or rec.get("event_type") or rec.get("corridor_type"))
    loc=_display_location(rec)
    if kind or loc:
        st.caption(" · ".join(x for x in [kind,loc] if x))

    if typ=="entity":
        prof=_filtered_rows("pc_company_profiles","entity_id",str(oid),5)
        if prof:
            p=prof[0]
            if p.get("business_description"):
                st.write(p.get("business_description"))
            facts=[]
            for k in ("sector","website_url","products_services","operating_countries"):
                if p.get(k) not in (None,"",[],{}):
                    facts.append({"Field":k.replace("_"," ").title(),"Value":_clean(p.get(k))})
            if facts:
                st.dataframe(pd.DataFrame(facts),hide_index=True,use_container_width=True)

        rels=_linked_objects_from_relationships("entity",oid)
        corporate=[x for x in rels if x.get("type")=="entity"]
        if corporate:
            st.markdown("##### Corporate network")
            st.dataframe(pd.DataFrame([{"Company":x["name"],"Relationship":x["relationship"]} for x in corporate]),
                         hide_index=True,use_container_width=True,height=min(320,100+28*len(corporate)))
            _open_selector(corporate,f"dossier_corp_{oid}","Open company")

        portfolio=_portfolio(oid)
        if portfolio:
            st.markdown("##### Portfolio / equity / concessions")
            readable=[]
            for r in portfolio:
                readable.append({
                    "Investee company":_entity_chip(_clean(r.get("investee_entity_id"))),
                    "Investee asset":_asset_chip(_clean(r.get("investee_asset_id"))),
                    "Stake / role":_clean(r.get("position_type") or r.get("ownership_pct") or r.get("stake_pct") or r.get("role")),
                    "Status":_clean(r.get("status")),
                    "Effective":_clean(r.get("effective_date") or r.get("valid_from")),
                })
            st.dataframe(pd.DataFrame(readable),hide_index=True,use_container_width=True)

        tx=_related_table("pc_transactions",oid,name,100)
        if tx:
            st.markdown("##### Transactions / capital actions")
            # Prefer descriptive columns; suppress raw IDs from analyst view.
            cols=[x for x in ("transaction_date","transaction_type","title","headline","description",
                              "deal_value","value","currency","status","buyer_name","seller_name","target_name")
                  if any(x in r for r in tx)]
            view=pd.DataFrame(tx)
            if cols:
                view=view[[x for x in cols if x in view.columns]]
            st.dataframe(view,hide_index=True,use_container_width=True,height=min(360,120+28*len(view)))

    elif typ=="asset":
        companies=_asset_companies(rec)
        if companies:
            st.markdown("##### Ownership / operation")
            st.dataframe(pd.DataFrame(companies),hide_index=True,use_container_width=True)
            _open_selector([{"type":"entity","id":x["id"],"name":x["name"],"relationship":x["role"]} for x in companies],
                           f"dossier_asset_comp_{oid}","Open company")
        facts=[]
        for k in ("status","confidence","subtype","country","region_city","capacity","annual_capacity","teu_capacity",
                  "land_area_ha","depth_m","berth_count"):
            if rec.get(k) not in (None,"",[],{}):
                facts.append({"Field":k.replace("_"," ").title(),"Value":_clean(rec.get(k))})
        if facts:
            st.dataframe(pd.DataFrame(facts),hide_index=True,use_container_width=True)

    elif typ=="mobile_asset":
        companies=_mobile_companies(rec)
        if companies:
            st.markdown("##### Ownership / management")
            st.dataframe(pd.DataFrame(companies),hide_index=True,use_container_width=True)
        facts=[]
        for k in ("imo","mmsi","flag","asset_type","subtype","build_year","dwt","gross_tonnage","length_m","beam_m","status"):
            if rec.get(k) not in (None,"",[],{}):
                facts.append({"Field":k.replace("_"," ").upper() if k in {"imo","mmsi"} else k.replace("_"," ").title(),
                              "Value":_clean(rec.get(k))})
        if facts:
            st.dataframe(pd.DataFrame(facts),hide_index=True,use_container_width=True)

    elif typ=="corridor":
        st.markdown("##### Corridor definition")
        st.write(_clean(rec.get("description") or rec.get("geography") or rec.get("corridor_name")))
        roles=_filtered_rows("pc_company_corridor_roles","corridor_key",str(oid),500)
        if roles:
            rows=[]
            for r in roles:
                eid=_clean(r.get("entity_id"))
                rows.append({"Company":_entity_chip(eid),"Role":_clean(r.get("corridor_role"))})
            st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)

    elif typ=="event":
        if rec.get("description"):
            st.write(rec.get("description"))
        for k in ("operational_impact","commercial_impact","what_it_means","pc_assessment"):
            if rec.get(k):
                st.markdown("**"+k.replace("_"," ").title()+"**")
                st.write(rec.get(k))


def _render_spatial_pane(typ: str, oid: str, rec: dict, lens: str):
    st.markdown("### Spatial / System Context")
    st.caption("Infrastructure, corridors, routes and connected nodes.")

    if typ=="asset":
        _render_map_for_asset(rec)
        local=_local_infrastructure(rec)
        if local:
            st.markdown("##### Local infrastructure system")
            view=pd.DataFrame([{
                "Node":x["name"],
                "Type":x.get("asset_type"),
                "Region":x.get("region"),
                "Country":x.get("country")
            } for x in local])
            st.dataframe(view,hide_index=True,use_container_width=True,height=min(360,100+28*min(len(view),9)))
            _open_selector(local,f"spatial_local_{oid}","Open connected node")

        connected=_linked_objects_from_relationships("asset",oid)
        if connected:
            st.markdown("##### Network connections")
            st.dataframe(pd.DataFrame([{"Object":x["name"],"Relationship":x["relationship"]} for x in connected]),
                         hide_index=True,use_container_width=True)
            _open_selector(connected,f"spatial_links_{oid}")

        # Name/location-based route & corridor discovery while graph edges are still being completed.
        for title,table in (("Routes / services","pc_transport_routes"),("Corridors","pc_trade_corridors")):
            rows=_related_table(table,oid,_clean(rec.get("name")),100)
            if rows:
                st.markdown("##### "+title)
                st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True,height=min(360,100+28*len(rows)))

    elif typ=="entity":
        roles=_company_asset_roles(oid)
        nodes=[]
        for r in roles:
            aid=_clean(r.get("asset_id"))
            mid=_clean(r.get("mobile_asset_id"))
            if aid:
                nodes.append({"type":"asset","id":aid,"name":_asset_chip(aid),"relationship":_clean(r.get("asset_role"))})
            elif mid:
                nodes.append({"type":"mobile_asset","id":mid,"name":_object_name("mobile_asset",mid),"relationship":_clean(r.get("asset_role"))})
        if nodes:
            mapped=[]
            for n in nodes:
                if n.get("type")=="asset":
                    p=_asset_point(n.get("id"))
                    if p: mapped.append(p)
            if mapped:
                st.map(pd.DataFrame(mapped),latitude="lat",longitude="lon",size=44,zoom=None,use_container_width=True)
            st.markdown("##### Operating footprint")
            st.dataframe(pd.DataFrame([{"Asset":x["name"],"Role":x["relationship"]} for x in nodes]),
                         hide_index=True,use_container_width=True,height=min(420,100+28*min(len(nodes),12)))
            _open_selector(nodes,f"spatial_entity_nodes_{oid}")

        cr=_company_corridors(oid)
        if cr:
            st.markdown("##### Corridor exposure")
            rows=[]
            opens=[]
            for r in cr:
                ck=_clean(r.get("corridor_key"))
                nm=_object_name("corridor",ck)
                rows.append({"Corridor":nm,"Role":_clean(r.get("corridor_role"))})
                opens.append({"type":"corridor","id":ck,"name":nm,"relationship":_clean(r.get("corridor_role"))})
            st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
            _open_selector(opens,f"spatial_entity_corr_{oid}","Open corridor")

    elif typ=="mobile_asset":
        st.caption("Live AIS is not yet connected. Showing canonical ownership, linked events and infrastructure context from current evidence.")
        events=_events_for_object("mobile_asset",oid)
        ports=[]
        for e in events:
            loc=_clean(e.get("location"))
            if loc:
                ports.append({"Date":_clean(e.get("start_date"))[:10],"Location":loc,"Development":_clean(e.get("title"))})
        if ports:
            st.dataframe(pd.DataFrame(ports),hide_index=True,use_container_width=True)

    elif typ=="corridor":
        st.markdown("##### Corridor geography")
        st.write(_clean(rec.get("geography") or rec.get("description") or rec.get("corridor_name")))
        routes=_related_table("pc_transport_routes",oid,_clean(rec.get("corridor_name")),120)
        if routes:
            st.markdown("##### Routes / services")
            st.dataframe(pd.DataFrame(routes),hide_index=True,use_container_width=True)

    elif typ=="event":
        _render_event_system_map(rec,oid)
        # Non-spatial linked actors/assets remain available below the map.
        links=_linked_objects_from_relationships("event",oid)
        nonspatial=[x for x in links if x.get("type") not in {"asset","corridor"}]
        if nonspatial:
            st.markdown("##### Connected actors / assets")
            st.dataframe(pd.DataFrame([{"Object":x["name"],"Type":x["type"],"Relationship":x["relationship"]} for x in nonspatial[:25]]),
                         hide_index=True,use_container_width=True,height=min(360,100+28*len(nonspatial[:25])))
            _open_selector(nonspatial[:30],f"spatial_event_actor_{oid}")


def _render_evidence_pane(typ: str, oid: str, rec: dict, lens: str):
    st.markdown("### Intelligence / Evidence")
    st.caption("Developments, documents, filings, sanctions and source provenance.")

    if typ == 'mobile_asset':
        from pc_document_vessels import documents_for_vessel
        try:
            linked_documents = documents_for_vessel(_sb(), oid)
            observations = _sb().table('pc_v_document_vessel_access').select('*').eq('mobile_asset_id', oid).execute().data or []
            for observation in observations:
                raw = observation['raw_record']
                if observation.get('scope_text'):
                    st.markdown('**Documented access restriction:** ' + observation['scope_text'])
                    st.caption(str(observation.get('authority_name') or '') + ' · ' + str(observation.get('circular_reference') or ''))
                st.caption('Source page ' + str(observation['page_number']) + ' · Listed name: ' + str(raw.get('name') or '') +
                           ' · Listed flag: ' + str(raw.get('flag') or 'unknown'))
                with st.expander('Source row and ownership research gaps', expanded=False):
                    st.write({k: v for k, v in raw.items() if k not in ('identity_status', 'page_number') and v})
            for did in linked_documents:
                docs = _filtered_rows('pc_documents', 'document_id', did, 1)
                if docs:
                    st.button('Open source: ' + str(docs[0]['title']), key=f'vessel_doc_{oid}_{did}',
                              on_click=_set_context, args=('document', did, docs[0]['title']))
        except Exception as exc:
            st.caption('Linked document evidence unavailable: ' + str(exc)[:140])

    if typ in ('mobile_asset', 'entity'):
        try:
            direct_links = _sb().table('pc_sanctions_links').select('sanctions_designation_id').eq('linked_type', typ).eq('linked_id', oid).execute().data or []
            ids = list(dict.fromkeys(r['sanctions_designation_id'] for r in direct_links))
            if ids:
                designations = _sb().table('pc_sanctions_designations').select('primary_name,designation_date,status,metadata,source_url').in_('sanctions_designation_id', ids).execute().data or []
                st.markdown('##### Linked sanctions designations')
                for designation in designations:
                    st.markdown('**' + designation['primary_name'] + '**')
                    st.caption(' · '.join(str(v) for v in [designation.get('designation_date'),designation.get('status'),
                        ', '.join((designation.get('metadata') or {}).get('all_programme_codes') or [])] if v))
        except Exception as exc:
            st.caption('Sanctions links unavailable: ' + str(exc)[:140])

    events=_events_for_object(typ,oid)
    if lens=="strategic":
        events=[e for e in events if STRATEGIC_RX.search(_record_text(e))] or events
    elif lens=="sanctions":
        events=[e for e in events if SANCTIONS_RX.search(_record_text(e))] or events
    _render_event_cards(events,f"evidence_{lens}_{typ}_{oid}",8)

    docs=_documents_for_entity(oid) if typ=="entity" else _documents_by_name(_object_name(typ,oid),30)
    if docs:
        st.markdown("##### Documents / filings / research")
        rows=[]
        for d in docs[:40]:
            rows.append({
                "Date":_clean(d.get("published_date")),
                "Title":_clean(d.get("title")),
                "Type":_clean(d.get("document_type")),
                "Source":_clean(d.get("source_name")),
                "Relationship":_clean(d.get("_relationship")),
            })
        st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True,height=min(420,110+28*len(rows)))

    if lens=="sanctions":
        san=_related_table("pc_sanctions_designations",oid,_object_name(typ,oid),120)
        if san:
            st.markdown("##### Designations / regulatory")
            st.dataframe(pd.DataFrame(san),hide_index=True,use_container_width=True)

    sources=[]
    for x in (_meta(rec).get("research_sources") or []):
        u=x.get("url") if isinstance(x,dict) else x
        if isinstance(u,str) and u.startswith(("http://","https://")):
            sources.append(u)
    if sources:
        st.markdown("##### Source evidence")
        for u in list(dict.fromkeys(sources))[:20]:
            st.markdown("- "+u)


def _render_timeline(typ: str, oid: str):
    events=_events_for_object(typ,oid)
    if not events:
        st.caption("No linked chronological developments yet.")
        return
    rows=[]
    for e in events[:80]:
        rows.append({
            "Date":_clean(e.get("start_date"))[:10],
            "Development":_clean(e.get("title")),
            "Type":_clean(e.get("event_type")).replace("_"," "),
            "Relationship":_clean(e.get("_relationship")).replace("_"," "),
        })
    st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True,height=min(420,110+28*min(len(rows),10)))


def _render_layer2(typ: str, oid: str, rec: dict, lens: str):
    st.markdown(f"### {LENS[lens]['layer2']}")
    if typ == "asset":
        _render_map_for_asset(rec)
        st.markdown("#### Node profile")
        facts = []
        for k in ("asset_type", "subtype", "country", "region_city", "latitude", "longitude", "status", "confidence"):
            if rec.get(k) not in (None, "", [], {}):
                facts.append({"Field": k.replace("_", " ").title(), "Value": _clean(rec.get(k))})
        if facts:
            st.dataframe(pd.DataFrame(facts), hide_index=True, use_container_width=True)
        companies = _asset_companies(rec)
        if companies:
            st.markdown("#### Operators / owners / companies")
            st.dataframe(pd.DataFrame(companies), hide_index=True, use_container_width=True)
            _open_selector([{"type":"entity","id":x["id"],"name":x["name"],"relationship":x["role"]} for x in companies],
                           f"l2_asset_companies_{oid}")
        connected = _linked_objects_from_relationships("asset", oid)
        if connected:
            st.markdown("#### Connected infrastructure / network")
            st.dataframe(pd.DataFrame(connected), hide_index=True, use_container_width=True)
            _open_selector(connected, f"l2_asset_links_{oid}")

        local=_local_infrastructure(rec)
        if local:
            st.markdown("#### Local infrastructure system")
            st.caption("Canonical assets sharing the stored local geography. Discovery only; this does not infer ownership.")
            st.dataframe(
                pd.DataFrame([{k:v for k,v in x.items() if k not in ("type","id","relationship")} for x in local]),
                hide_index=True,use_container_width=True,height=min(420,100+28*min(len(local),10))
            )
            _open_selector(local,f"l2_asset_local_{oid}","Open local infrastructure")
    elif typ == "entity":
        roles = _company_asset_roles(oid)
        rows = []
        for r in roles:
            at = "mobile_asset" if r.get("mobile_asset_id") else "asset"
            aid = _clean(r.get("mobile_asset_id") or r.get("asset_id"))
            if aid:
                rows.append({"type":at,"id":aid,"name":_object_name(at,aid),"relationship":_clean(r.get("asset_role"))})
        if rows:
            st.markdown("#### Operating footprint / assets")
            st.dataframe(pd.DataFrame([{k:v for k,v in x.items() if k not in ("type","id")} for x in rows]),
                         hide_index=True, use_container_width=True)
            _open_selector(rows, f"l2_entity_assets_{oid}")
        corridors = _company_corridors(oid)
        if corridors:
            st.markdown("#### Corridors / systems")
            display = []
            opens = []
            for r in corridors:
                ck = _clean(r.get("corridor_key"))
                display.append({"Corridor":_object_name("corridor",ck),"Role":_clean(r.get("corridor_role")),"Status":_clean(r.get("role_status"))})
                opens.append({"type":"corridor","id":ck,"name":_object_name("corridor",ck),"relationship":_clean(r.get("corridor_role"))})
            st.dataframe(pd.DataFrame(display), hide_index=True, use_container_width=True)
            _open_selector(opens, f"l2_entity_corridors_{oid}")
    elif typ == "mobile_asset":
        facts = []
        for k in ("imo","mmsi","registration","call_sign","flag","year_built","dwt","gross_tonnage","length_m","beam_m","asset_type","subtype"):
            if rec.get(k) not in (None,"",[],{}):
                facts.append({"Field":k.replace("_"," ").upper() if k in {"imo","mmsi"} else k.replace("_"," ").title(),"Value":_clean(rec.get(k))})
        if facts:
            st.dataframe(pd.DataFrame(facts), hide_index=True, use_container_width=True)
        companies = _mobile_companies(rec)
        if companies:
            st.markdown("#### Owner / operator / manager")
            st.dataframe(pd.DataFrame(companies), hide_index=True, use_container_width=True)
            _open_selector([{"type":"entity","id":x["id"],"name":x["name"],"relationship":x["role"]} for x in companies],
                           f"l2_mobile_companies_{oid}")
    elif typ == "corridor":
        st.markdown("#### Corridor definition")
        st.dataframe(pd.DataFrame([{
            "Name": rec.get("corridor_name"), "Type": rec.get("corridor_type"),
            "Origin": rec.get("origin_region"), "Destination": rec.get("destination_region"),
            "Geography": _clean(rec.get("geography"))
        }]), hide_index=True, use_container_width=True)
        roles = _filtered_rows("pc_company_corridor_roles", "corridor_key", str(oid), 500)
        if roles:
            rows = []
            for r in roles:
                eid = _clean(r.get("entity_id"))
                rows.append({"type":"entity","id":eid,"name":_object_name("entity",eid),"relationship":_clean(r.get("corridor_role"))})
            st.markdown("#### Companies / operators")
            st.dataframe(pd.DataFrame([{k:v for k,v in x.items() if k not in ("type","id")} for x in rows]), hide_index=True, use_container_width=True)
            _open_selector(rows, f"l2_corridor_companies_{oid}")
    elif typ == "event":
        links = _event_links("event", oid)
        rows = []
        for l in links:
            lt = _clean(l.get("linked_type")).casefold()
            if lt == "vessel":
                lt = "mobile_asset"
            lid = _clean(l.get("linked_id"))
            if lt in OBJECTS and lid:
                rows.append({"type":lt,"id":lid,"name":_object_name(lt,lid),"relationship":_clean(l.get("relationship"))})
        if rows:
            st.markdown("#### Affected / involved objects")
            st.dataframe(pd.DataFrame([{k:v for k,v in x.items() if k not in ("type","id")} for x in rows]), hide_index=True, use_container_width=True)
            _open_selector(rows, f"l2_event_links_{oid}")
        else:
            st.caption("No canonical object links are recorded for this event yet.")


def _render_layer3(typ: str, oid: str, rec: dict, lens: str):
    st.markdown(f"### {LENS[lens]['layer3']}")
    if typ == "entity":
        profiles = _filtered_rows("pc_company_profiles", "entity_id", str(oid), 5)
        if profiles:
            p = profiles[0]
            st.markdown("#### Company profile")
            if p.get("business_description"):
                st.write(p.get("business_description"))
            fields = []
            for k in ("sector","website_url","products_services","operating_countries"):
                if p.get(k) not in (None,"",[],{}):
                    fields.append({"Field":k.replace("_"," ").title(),"Value":_clean(p.get(k))})
            if fields:
                st.dataframe(pd.DataFrame(fields), hide_index=True, use_container_width=True)
        port = _portfolio(oid)
        if port:
            st.markdown("#### Portfolio / investments / concessions")
            st.dataframe(pd.DataFrame(port), hide_index=True, use_container_width=True, height=min(420, 100+28*len(port)))
        for title, table in (
            ("Transactions", "pc_transactions"),
            ("Projects", "pc_project_details"),
            ("Contracts", "pc_contracts"),
            ("Shipbuilding / platform orders", "pc_shipbuilding_orders"),
        ):
            x = _related_table(table, oid, _clean(rec.get("name")), 80)
            if x:
                st.markdown("#### " + title)
                st.dataframe(pd.DataFrame(x), hide_index=True, use_container_width=True, height=min(380,100+28*len(x)))
    elif typ == "asset":
        companies = _asset_companies(rec)
        if companies:
            st.markdown("#### Commercial / institutional control")
            st.dataframe(pd.DataFrame(companies), hide_index=True, use_container_width=True)
        for title, table in (("Projects / expansion", "pc_project_details"), ("Contracts", "pc_contracts")):
            x = _related_table(table, oid, _clean(rec.get("name")), 80)
            if x:
                st.markdown("#### " + title)
                st.dataframe(pd.DataFrame(x), hide_index=True, use_container_width=True)
    elif typ == "mobile_asset":
        for title, table in (("Shipbuilding / orderbook", "pc_shipbuilding_orders"), ("Contracts / programmes", "pc_contracts")):
            x = _related_table(table, oid, _clean(rec.get("name")), 80)
            if x:
                st.markdown("#### " + title)
                st.dataframe(pd.DataFrame(x), hide_index=True, use_container_width=True)
    elif typ == "corridor":
        routes = _related_table("pc_transport_routes", oid, _clean(rec.get("corridor_name")), 100)
        if routes:
            st.markdown("#### Services / routes")
            st.dataframe(pd.DataFrame(routes), hide_index=True, use_container_width=True)
        rates = _related_table("pc_freight_rate_observations", oid, _clean(rec.get("corridor_name")), 100)
        if rates:
            st.markdown("#### Freight / market observations")
            st.dataframe(pd.DataFrame(rates), hide_index=True, use_container_width=True)
    elif typ == "event":
        st.markdown("#### Event assessment")
        rows = []
        for k in ("description","operational_impact","commercial_impact","what_it_means","pc_assessment"):
            if rec.get(k):
                rows.append({"Field":k.replace("_"," ").title(),"Value":_clean(rec.get(k))})
        if rows:
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    if lens == "trade":
        strategic_hits=[]
        for title,table in (
            ("Strategic programmes","pc_defence_programmes"),
            ("Shipbuilding orders","pc_shipbuilding_orders"),
            ("Shipyard capacity","pc_shipyard_capacity_history"),
            ("Security / coast guard operations","pc_security_operations"),
        ):
            x=_related_table(table,oid,_object_name(typ,oid),80)
            if x:
                strategic_hits.append((title,x))
        if strategic_hits:
            st.markdown("#### Strategic industrial / security exposure")
            for title,x in strategic_hits:
                st.markdown("**"+title+"**")
                st.dataframe(pd.DataFrame(x),hide_index=True,use_container_width=True,height=min(320,100+28*min(len(x),8)))

    if lens == "sanctions":
        st.markdown("#### Sanctions / exposure")
        sanctions=_related_table("pc_sanctions_designations",oid,_object_name(typ,oid),120)
        links=_related_table("pc_sanctions_links",oid,_object_name(typ,oid),120)
        cases=_related_table("pc_screening_cases",oid,_object_name(typ,oid),120)
        matches=_related_table("pc_screening_matches",oid,_object_name(typ,oid),120)
        if sanctions:
            st.markdown("**Legal designations**")
            st.dataframe(pd.DataFrame(sanctions),hide_index=True,use_container_width=True)
        if links:
            st.markdown("**Ownership / control / designation network**")
            st.dataframe(pd.DataFrame(links),hide_index=True,use_container_width=True)
        if cases:
            st.markdown("**Screening cases**")
            st.dataframe(pd.DataFrame(cases),hide_index=True,use_container_width=True)
        if matches:
            st.markdown("**Candidate / confirmed matches**")
            st.dataframe(pd.DataFrame(matches),hide_index=True,use_container_width=True)
        if not (sanctions or links or cases or matches):
            st.caption("No sanctions/designation or screening record is currently linked to this canonical context.")

    if lens == "strategic":
        st.markdown("#### Strategic programmes / capacity")
        found=False
        for title,table in (
            ("Defence programmes","pc_defence_programmes"),
            ("Programme participation","pc_defence_programme_participants"),
            ("Shipbuilding / production tasks","pc_shipbuilding_production_tasks"),
            ("Programme milestones","pc_defence_programme_milestones"),
            ("Shipyard capacity history","pc_shipyard_capacity_history"),
            ("Security operations","pc_security_operations"),
            ("Shipbuilding orders","pc_shipbuilding_orders"),
            ("Contracts","pc_contracts"),
            ("Projects","pc_project_details"),
        ):
            x=_related_table(table,oid,_object_name(typ,oid),120)
            if x:
                found=True
                st.markdown("**"+title+"**")
                st.dataframe(pd.DataFrame(x),hide_index=True,use_container_width=True,height=min(400,110+28*min(len(x),10)))
        if not found:
            st.caption("No strategic programme, contract, production or security-operation record is currently linked to this context.")


def _render_event_cards(events: list[dict], key_prefix: str, limit: int = 15):
    if not events:
        st.caption("No linked canonical developments.")
        return
    for i, e in enumerate(events[:limit]):
        title = _clean(e.get("title")) or "Untitled development"
        date = _clean(e.get("start_date"))[:10]
        with st.expander(f"{date} · {title}" if date else title):
            if e.get("description"):
                st.write(e.get("description"))
            impact = e.get("operational_impact") or e.get("commercial_impact")
            if impact:
                st.markdown("**Impact**")
                st.write(impact)
            eid = _clean(e.get("event_id"))
            if eid and st.button("Open development in terminal", key=f"{key_prefix}_{i}_{eid}", use_container_width=True):
                _set_context("event", eid, title)
                st.rerun()


def _render_layer4(typ: str, oid: str, rec: dict, lens: str):
    st.markdown(f"### {LENS[lens]['layer4']}")
    events = _events_for_object(typ, oid)
    if lens == "strategic":
        events = [e for e in events if STRATEGIC_RX.search(_record_text(e))] or events
    elif lens == "sanctions":
        events = [e for e in events if SANCTIONS_RX.search(_record_text(e))] or events
    st.markdown("#### Developments")
    _render_event_cards(events, f"l4_{lens}_{typ}_{oid}", 12)

    docs = _documents_for_entity(oid) if typ == "entity" else _documents_by_name(_object_name(typ, oid), 25)
    if docs:
        st.markdown("#### Documents / filings / research")
        drows = []
        for d in docs[:40]:
            drows.append({
                "Date": _clean(d.get("published_date")),
                "Title": _clean(d.get("title")),
                "Type": _clean(d.get("document_type")),
                "Source": _clean(d.get("source_name")),
                "Relationship": _clean(d.get("_relationship")),
                "URL": _clean(d.get("source_url")),
            })
        st.dataframe(pd.DataFrame(drows), hide_index=True, use_container_width=True)

    sources = []
    meta = _meta(rec)
    for x in meta.get("research_sources") or []:
        if isinstance(x, dict):
            u = x.get("url")
        else:
            u = x
        if isinstance(u, str) and u.startswith(("http://","https://")):
            sources.append(u)
    if sources:
        st.markdown("#### Source evidence")
        for u in list(dict.fromkeys(sources))[:20]:
            st.markdown(f"- {u}")


def _event_theme(e: dict) -> str:
    blob=_record_text(e).casefold()
    if any(x in blob for x in ("attack","strike","missile","drone","piracy","boarding","intercept","seizure","military","naval","security","war risk")):
        return "Security / conflict"
    if any(x in blob for x in ("sanction","ofac","sdn","export control","embargo","dark fleet","shadow fleet","evasion")):
        return "Sanctions / compliance"
    if any(x in blob for x in ("strike action","labour","labor","collision","grounding","fire","outage","closure","disruption","congestion","drought","low water")):
        return "Operational disruption"
    if any(x in blob for x in ("acquisition","investment","capex","expansion","terminal","berth","rail","airport","shipyard","orderbook")):
        return "Infrastructure / capacity"
    if any(x in blob for x in ("election","government","policy","agreement","diplomatic","state","corridor","trade route")):
        return "Statecraft / policy"
    return "Other intelligence"

def _event_priority(e: dict) -> int:
    score=0
    sev=_clean(e.get("severity")).casefold()
    if sev in {"critical","severe","high"}: score+=40
    if str(e.get("alert_worthy") or "").casefold() in {"true","1","yes"}: score+=30
    if str(e.get("intelligence_relevance") or "").casefold() in {"high","critical","true","1","yes"}: score+=20
    theme=_event_theme(e)
    if theme in {"Security / conflict","Sanctions / compliance","Operational disruption"}: score+=20
    blob=_record_text(e).casefold()
    if any(x in blob for x in ("hormuz","red sea","suez","black sea","panama canal","bab el mandeb","gulf of aden")):
        score+=15
    if e.get("operational_impact") or e.get("commercial_impact"): score+=10
    return score

def _event_region_label(e: dict) -> str:
    for k in ("region","country","countries","location"):
        v=e.get(k)
        if isinstance(v,dict):
            v=v.get("name") or v.get("country") or v.get("region")
        if isinstance(v,list):
            v=", ".join(str(x) for x in v[:2])
        if v:
            s=_clean(v)
            if len(s)>55: s=s[:52]+"…"
            return s
    return "Global / unspecified"

def _render_intelligence_home():
    events=sorted(_rows("pc_events",2500),key=lambda x:_clean(x.get("start_date")),reverse=True)
    priority=sorted(events,key=lambda x:(_event_priority(x),_clean(x.get("start_date"))),reverse=True)
    security=[e for e in events if _event_theme(e)=="Security / conflict"]
    sanctions=[e for e in events if _event_theme(e)=="Sanctions / compliance"]
    disruptions=[e for e in events if _event_theme(e)=="Operational disruption"]
    corridors=_rows("pc_trade_corridors",5000)

    _dashboard_header("P&C INTELLIGENCE · OPERATING PICTURE",
                      "Intelligence Operating Terminal",
                      "Events, actors, infrastructure exposure, security, statecraft, monitoring and evidence in one connected workspace.")

    m=st.columns(6)
    m[0].metric("Priority intelligence",sum(1 for e in events if _event_priority(e)>=40))
    m[1].metric("Security / conflict",len(security))
    m[2].metric("Operational disruptions",len(disruptions))
    m[3].metric("Sanctions / compliance",len(sanctions))
    m[4].metric("Corridors monitored",len(corridors))
    m[5].metric("Events indexed",_index_count("event"))

    left,mid,right=st.columns([1.6,1.0,1.0],gap="medium")
    with left:
        with st.container(border=True):
            _panel_header("Global Intelligence Picture","Infrastructure and geographic context for current developments.")
            _dashboard_map_assets("trade")
    with mid:
        with st.container(border=True):
            _panel_header("Priority Intelligence","Highest-value developments first.")
            _html_rows(_recent_event_rows(priority,8),8)
    with right:
        with st.container(border=True):
            _panel_header("Monitoring Desk","Active themes, disruptions and sanctions exposure.")
            _html_rows([
                ("Security / conflict",str(len(security))),
                ("Operational disruption",str(len(disruptions))),
                ("Sanctions / compliance",str(len(sanctions))),
                ("Statecraft / policy",str(sum(1 for e in events if _event_theme(e)=="Statecraft / policy"))),
                ("Infrastructure / capacity",str(sum(1 for e in events if _event_theme(e)=="Infrastructure / capacity"))),
            ],7)

    c1,c2,c3=st.columns([1.0,1.0,1.2],gap="medium")
    with c1:
        with st.container(border=True):
            _panel_header("Security & Maritime","Conflict, attacks, boardings, naval activity and maritime security.")
            _html_rows(_recent_event_rows(security,7),7)
    with c2:
        with st.container(border=True):
            _panel_header("Disruptions & Chokepoints","Operational disruption affecting ports, corridors and trade.")
            _html_rows(_recent_event_rows(disruptions,7),7)
    with c3:
        with st.container(border=True):
            _panel_header("Recent Intelligence","Latest developments across the monitoring picture.")
            _html_rows(_recent_event_rows(priority,7),7)

    st.markdown("### Featured Intelligence Objects")
    _featured_search_cards([
        ("Strait of Hormuz","Hormuz"),
        ("Red Sea","Red Sea"),
        ("Black Sea","Black Sea"),
        ("Panama Canal","Panama Canal"),
        ("Middle Corridor","Middle Corridor"),
        ("Dark Fleet","dark fleet"),
    ],"intelligence")


def _safe_df(rows: list[dict], preferred: list[str] | None = None, max_rows: int = 100):
    if not rows:
        return None
    df=pd.DataFrame(rows[:max_rows])
    if preferred:
        cols=[x for x in preferred if x in df.columns]
        if cols:
            df=df[cols]
    return df

def _dashboard_header(kicker: str, title: str, subtitle: str):
    st.markdown(f"<div class='pc-k'>{kicker}</div>",unsafe_allow_html=True)
    st.title(title)
    st.markdown(f"<div class='pc-sub'>{subtitle}</div>",unsafe_allow_html=True)

def _panel_header(title: str, subtitle: str=""):
    st.markdown(f"<div class='pc-panel-title'>{title}</div>",unsafe_allow_html=True)
    if subtitle:
        st.markdown(f"<div class='pc-panel-sub'>{subtitle}</div>",unsafe_allow_html=True)

def _html_rows(rows: list[tuple[str,str]], limit: int=8):
    if not rows:
        st.caption("No records available.")
        return
    html=""
    for a,b in rows[:limit]:
        html += f"<div class='pc-row'><span class='pc-row-label'>{a}</span><span class='pc-row-meta'>{b}</span></div>"
    st.markdown(html,unsafe_allow_html=True)

def _recent_event_rows(events: list[dict], limit: int=7) -> list[tuple[str,str]]:
    out=[]
    for e in events[:limit]:
        title=_clean(e.get("title")) or "Untitled development"
        dt=_clean(e.get("start_date"))[:10]
        out.append((title,dt))
    return out

def _dashboard_map_assets(lens: str, limit: int=300):
    rows=[]
    for a in _rows("pc_assets",5000):
        try:
            lat=float(a.get("latitude")); lon=float(a.get("longitude"))
        except Exception:
            continue
        if not (-90<=lat<=90 and -180<=lon<=180):
            continue
        blob=_record_text(a)
        if lens=="strategic" and not STRATEGIC_RX.search(blob):
            continue
        rows.append({"lat":lat,"lon":lon,"name":_clean(a.get("name")),"type":_clean(a.get("asset_type"))})
        if len(rows)>=limit: break
    if rows:
        st.map(pd.DataFrame(rows),latitude="lat",longitude="lon",size=24,zoom=None,use_container_width=True)
    else:
        st.info("Mapped canonical coordinates will appear here as infrastructure nodes are enriched.")

def _index_count(object_type: str) -> int:
    if _terminal_index_ready():
        sb=_sb()
        try:
            data=(sb.table("pc_terminal_object_index").select("object_id",count="exact")
                  .eq("object_type",object_type).limit(1).execute())
            if data.count is not None:
                return int(data.count)
        except Exception:
            pass
    fallback={
        "entity":("pc_entities",10000),"asset":("pc_assets",10000),
        "mobile_asset":("pc_mobile_assets",10000),"event":("pc_events",5000),
        "corridor":("pc_trade_corridors",5000),"sanction":("pc_sanctions_designations",5000),
        "programme":("pc_defence_programmes",5000),"document":("pc_documents",5000),
    }
    t=fallback.get(object_type)
    return len(_rows(t[0],t[1])) if t else 0

def _featured_search_cards(items: list[tuple[str,str]], lens: str):
    cols=st.columns(min(len(items),6))
    for i,(label,query) in enumerate(items[:6]):
        with cols[i]:
            with st.container(border=True):
                st.markdown(f"**{label}**")
                st.caption("Open in terminal")
                if st.button("Open",key=f"featured_{lens}_{i}_{_norm(query)}",use_container_width=True):
                    results=_search_objects(query,lens,10)
                    if results:
                        x=results[0]
                        _set_context(x["type"],x["id"],x["name"])
                        st.rerun()

def _render_trade_home():
    events=sorted(_rows("pc_events",2500),key=lambda x:_clean(x.get("start_date")),reverse=True)
    trade_events=[x for x in events if TRADE_RX.search(_record_text(x))]
    disruptions=[x for x in events if _event_theme(x)=="Operational disruption"]
    strategic=[x for x in events if STRATEGIC_RX.search(_record_text(x))]
    sanctions=[x for x in events if SANCTIONS_RX.search(_record_text(x))]
    corridors=_rows("pc_trade_corridors",5000)
    projects=_rows("pc_project_details",3000)
    rates=_rows("pc_freight_rate_observations",3000)
    tx=_rows("pc_transactions",3000)

    _dashboard_header("P&C TRADE · GLOBAL OPERATING TERMINAL",
                      "Global Trade & Infrastructure Terminal",
                      "Infrastructure, operators, corridors, markets, capital, sanctions and strategic industrial capacity in one connected workspace.")

    m=st.columns(6)
    m[0].metric("Companies",_index_count("entity"))
    m[1].metric("Infrastructure nodes",_index_count("asset"))
    m[2].metric("Corridors",_index_count("corridor"))
    m[3].metric("Vessels / mobile assets",_index_count("mobile_asset"))
    m[4].metric("Active projects",len(projects))
    m[5].metric("Sanctions records",_index_count("sanction"))

    left,mid,right=st.columns([1.65,1.05,1.08],gap="medium")
    with left:
        with st.container(border=True):
            _panel_header("Global Trade Infrastructure","Ports, terminals, dry ports, rail nodes, airports, shipyards and logistics infrastructure.")
            _dashboard_map_assets("trade")
    with mid:
        with st.container(border=True):
            _panel_header("Key Corridors","Major trade systems and monitored route structures.")
            rows=[]
            for x in corridors[:8]:
                nm=_clean(x.get("corridor_name")) or _clean(x.get("corridor_key"))
                typ=_clean(x.get("corridor_type"))
                rows.append((nm,typ or "corridor"))
            _html_rows(rows,8)
        with st.container(border=True):
            _panel_header("Sanctions & Compliance","Trade exposure to designations, screening and restricted counterparties.")
            _html_rows([
                ("Designation records",str(_index_count("sanction"))),
                ("Sanctions-related events",str(len(sanctions))),
                ("Screening cases",str(len(_rows("pc_screening_cases",3000)))),
                ("Candidate matches",str(len(_rows("pc_screening_matches",5000)))),
            ],6)
    with right:
        with st.container(border=True):
            _panel_header("Strategic Industrial Capacity","Shipyards, defence/coast guard programmes and security-linked industrial capacity.")
            _html_rows([
                ("Strategic programmes",str(_index_count("programme"))),
                ("Shipbuilding orders",str(len(_rows("pc_shipbuilding_orders",3000)))),
                ("Production tasks",str(len(_rows("pc_shipbuilding_production_tasks",5000)))),
                ("Security operations",str(len(_rows("pc_security_operations",3000)))),
                ("Strategic developments",str(len(strategic))),
            ],7)

    c1,c2,c3=st.columns([1.05,1.05,1.25],gap="medium")
    with c1:
        with st.container(border=True):
            _panel_header("Companies & Capital","Operators, investment, transactions, projects and portfolio change.")
            _html_rows([
                ("Recent transactions",str(len(tx))),
                ("Active projects",str(len(projects))),
                ("Portfolio positions",str(len(_rows("pc_company_portfolio_positions",4000)))),
                ("Company–asset roles",str(len(_rows("pc_company_asset_roles",5000)))),
            ],6)
    with c2:
        with st.container(border=True):
            _panel_header("Markets & Freight","Freight observations, routes, corridors and operating disruption.")
            _html_rows([
                ("Freight observations",str(len(rates))),
                ("Transport routes",str(len(_rows("pc_transport_routes",3000)))),
                ("Corridors",str(len(corridors))),
                ("Operational disruptions",str(len(disruptions))),
            ],6)
    with c3:
        with st.container(border=True):
            _panel_header("Recent Developments","Latest high-value trade, infrastructure and strategic-industry developments.")
            priority=sorted(trade_events,key=lambda x:(_event_priority(x),_clean(x.get("start_date"))),reverse=True)
            _html_rows(_recent_event_rows(priority,7),7)

    st.markdown("### Featured Objects")
    st.caption("Quick pivots into companies, infrastructure, corridors and strategic industry.")
    _featured_search_cards([
        ("AD Ports Group","AD Ports Group"),
        ("Port of Rotterdam","Rotterdam"),
        ("Tbilisi Dry Port","Tbilisi Dry Port"),
        ("Middle Corridor","Middle Corridor"),
        ("Irving Shipbuilding","Irving"),
        ("Canadian Coast Guard","Canadian Coast Guard"),
    ],"trade")


def _render_sanctions_home():
    designations=_rows("pc_sanctions_designations",5000)
    cases=_rows("pc_screening_cases",3000)
    matches=_rows("pc_screening_matches",5000)
    links=_rows("pc_sanctions_links",5000)
    events=sorted([e for e in _rows("pc_events",2500) if SANCTIONS_RX.search(_record_text(e))],
                  key=lambda x:_clean(x.get("start_date")),reverse=True)
    confirmed=[x for x in matches if _clean(x.get("match_status")).casefold()=="confirmed"]
    review=[x for x in matches if _clean(x.get("match_status")).casefold() in {"candidate","needs_review","inconclusive"}]

    _dashboard_header("P&C SANCTIONS · EXPOSURE TERMINAL",
                      "Sanctions & Exposure Terminal",
                      "Designations, ownership/control, vessels, screening, jurisdictions and linked trade exposure.")

    m=st.columns(6)
    m[0].metric("Designations",len(designations))
    m[1].metric("Confirmed matches",len(confirmed))
    m[2].metric("Needs review",len(review))
    m[3].metric("Screening cases",len(cases))
    m[4].metric("Network links",len(links))
    m[5].metric("Sanctions events",len(events))

    left,mid,right=st.columns([1.6,1.0,1.0],gap="medium")
    with left:
        with st.container(border=True):
            _panel_header("Exposure Map","Canonical infrastructure and assets associated with sanctions/compliance context.")
            _dashboard_map_assets("trade")
    with mid:
        with st.container(border=True):
            _panel_header("Designation Regimes","Authorities, programmes and jurisdictions represented in the database.")
            regimes={}
            for d in designations:
                k=_clean(d.get("program") or d.get("regime") or d.get("authority") or "Unspecified")
                regimes[k]=regimes.get(k,0)+1
            _html_rows(sorted(regimes.items(),key=lambda x:x[1],reverse=True),8)
    with right:
        with st.container(border=True):
            _panel_header("Screening Desk","Candidate and confirmed identity matches requiring analyst attention.")
            _html_rows([
                ("Confirmed",str(len(confirmed))),
                ("Candidate / review",str(len(review))),
                ("Open cases",str(sum(1 for x in cases if _clean(x.get("case_status")).casefold() not in {"closed","cleared"}))),
                ("Ownership/control links",str(len(links))),
            ],7)

    c1,c2,c3=st.columns([1.0,1.0,1.2],gap="medium")
    with c1:
        with st.container(border=True):
            _panel_header("Ownership & Control","Sanctions-network relationships and beneficial-control exposure.")
            _html_rows([
                ("Sanctions links",str(len(links))),
                ("Entity designations",str(sum(1 for d in designations if d.get("entity_id")))),
                ("Vessel designations",str(sum(1 for d in designations if d.get("mobile_asset_id")))),
            ],6)
    with c2:
        with st.container(border=True):
            _panel_header("Trade Exposure","Sanctions as a commercial constraint across vessels, counterparties and routes.")
            _html_rows([
                ("Sanctions-linked events",str(len(events))),
                ("Corridors monitored",str(_index_count("corridor"))),
                ("Vessels indexed",str(_index_count("mobile_asset"))),
                ("Companies indexed",str(_index_count("entity"))),
            ],6)
    with c3:
        with st.container(border=True):
            _panel_header("Recent Sanctions Activity","Latest sanctions, enforcement and evasion-related developments.")
            _html_rows(_recent_event_rows(events,7),7)

    st.markdown("### Featured Sanctions Objects")
    _featured_search_cards([
        ("Dark Fleet","dark fleet"),
        ("Shadow Fleet","shadow fleet"),
        ("OFAC","OFAC"),
        ("Iran","Iran"),
        ("Russia","Russia"),
        ("Vessel / IMO","IMO"),
    ],"sanctions")


def _render_strategic_home():
    orgs=_rows("pc_defence_organisations",3000)
    programmes=_rows("pc_defence_programmes",3000)
    tasks=_rows("pc_shipbuilding_production_tasks",5000)
    milestones=_rows("pc_defence_programme_milestones",5000)
    capacity=_rows("pc_shipyard_capacity_history",5000)
    operations=_rows("pc_security_operations",3000)
    orders=_rows("pc_shipbuilding_orders",3000)
    events=sorted([e for e in _rows("pc_events",2500) if STRATEGIC_RX.search(_record_text(e))],
                  key=lambda x:_clean(x.get("start_date")),reverse=True)
    active=[x for x in programmes if _clean(x.get("programme_status")).casefold() not in {"completed","cancelled","closed"}]

    _dashboard_header("P&C STRATEGIC INDUSTRIES · INDUSTRIAL CAPACITY TERMINAL",
                      "Strategic Industries Terminal",
                      "Defence, coast guard, shipyards, programmes, fleets, contracts, production and industrial capacity.")

    m=st.columns(6)
    m[0].metric("Defence / security orgs",len(orgs))
    m[1].metric("Active programmes",len(active))
    m[2].metric("Shipbuilding orders",len(orders))
    m[3].metric("Production tasks",len(tasks))
    m[4].metric("Security operations",len(operations))
    m[5].metric("Industrial nodes",len(capacity))

    left,mid,right=st.columns([1.6,1.0,1.0],gap="medium")
    with left:
        with st.container(border=True):
            _panel_header("Strategic Industrial Footprint","Shipyards, naval/coast guard facilities and related industrial infrastructure.")
            _dashboard_map_assets("strategic")
    with mid:
        with st.container(border=True):
            _panel_header("Active Programmes","Defence and coast guard procurement / fleet programmes.")
            rows=[]
            for p in active[:8]:
                rows.append((_clean(p.get("programme_name")) or "Unnamed programme",
                             _clean(p.get("programme_status")) or _clean(p.get("programme_type"))))
            _html_rows(rows,8)
    with right:
        with st.container(border=True):
            _panel_header("Industrial Capacity","Orders, production tasks, milestones and yard capacity.")
            _html_rows([
                ("Shipbuilding orders",str(len(orders))),
                ("Production tasks",str(len(tasks))),
                ("Programme milestones",str(len(milestones))),
                ("Capacity observations",str(len(capacity))),
                ("Security operations",str(len(operations))),
            ],7)

    c1,c2,c3=st.columns([1.0,1.0,1.2],gap="medium")
    with c1:
        with st.container(border=True):
            _panel_header("Defence & Coast Guard","Organisations, customers and security operators.")
            types={}
            for o in orgs:
                k=_clean(o.get("organisation_type") or "Other")
                types[k]=types.get(k,0)+1
            _html_rows(sorted(types.items(),key=lambda x:x[1],reverse=True),8)
    with c2:
        with st.container(border=True):
            _panel_header("Production & Delivery","Current build pipeline and delivery milestones.")
            _html_rows([
                ("Active programmes",str(len(active))),
                ("Orders",str(len(orders))),
                ("Production tasks",str(len(tasks))),
                ("Milestones",str(len(milestones))),
            ],6)
    with c3:
        with st.container(border=True):
            _panel_header("Recent Strategic Developments","Latest defence, shipbuilding, coast guard and industrial-capacity developments.")
            _html_rows(_recent_event_rows(events,7),7)

    st.markdown("### Featured Strategic Objects")
    _featured_search_cards([
        ("Irving Shipbuilding","Irving"),
        ("Seaspan","Seaspan"),
        ("Fincantieri","Fincantieri"),
        ("Bollinger Shipyards","Bollinger"),
        ("Canadian Coast Guard","Canadian Coast Guard"),
        ("US Coast Guard","US Coast Guard"),
    ],"strategic")


def _render_home(lens: str):
    cfg = LENS[lens]
    st.markdown(f"<div class='pc-k'>{cfg['brand']} · terminal</div>", unsafe_allow_html=True)
    st.title(cfg["title"])
    st.markdown(f"<div class='pc-sub'>{cfg['deck']}</div>", unsafe_allow_html=True)

    if lens=="trade":
        _render_trade_home()
        return
    if lens=="intelligence":
        _render_intelligence_home()
        return
    if lens=="sanctions":
        _render_sanctions_home()
        return
    if lens=="strategic":
        _render_strategic_home()
        return

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Companies / organisations", len(_rows("pc_entities", 10000)))
    c2.metric("Infrastructure nodes", len(_rows("pc_assets", 10000)))
    c3.metric("Mobile assets", len(_rows("pc_mobile_assets", 10000)))
    c4.metric("Corridors", len(_rows("pc_trade_corridors", 5000)))

    st.markdown("### Recent developments")
    events = _rows("pc_events", 1200)
    if lens == "trade":
        filtered = [e for e in events if TRADE_RX.search(_record_text(e))]
    elif lens == "sanctions":
        filtered = [e for e in events if SANCTIONS_RX.search(_record_text(e))]
    elif lens == "strategic":
        filtered = [e for e in events if STRATEGIC_RX.search(_record_text(e))]
    else:
        filtered = events
    filtered = sorted(filtered, key=lambda x: _clean(x.get("start_date")), reverse=True)
    _render_event_cards(filtered, f"home_{lens}", 12)


def _open_search_result(lens: str, typ: str, oid: str, name: str):
    _set_context(typ, oid, name)
    # Callback executes before the rerun, so it is safe to clear the search widget.
    st.session_state[f"pc_terminal_search_{lens}"] = ""

def _render_search_results(results: list[dict], lens: str):
    st.markdown("#### Best matches")
    shown=results[:8]
    cols=st.columns(2, gap="medium")
    for i,x in enumerate(shown):
        with cols[i % 2]:
            with st.container(border=True):
                st.markdown(f"**{x['name']}**")
                meta=[x.get("kind"),x.get("subtype"),x.get("country")]
                st.caption(" · ".join(v for v in meta if v))
                if x.get("match_reason"):
                    st.caption("Matched by: "+x["match_reason"])
                st.button(
                    "Open",
                    key=f"pc_terminal_result_{lens}_{i}_{x['type']}_{x['id']}",
                    use_container_width=True,
                    type="primary" if i==0 else "secondary",
                    on_click=_open_search_result,
                    args=(lens,x["type"],x["id"],x["name"]),
                )
    if len(results)>len(shown):
        with st.expander(f"More results ({len(results)-len(shown)})"):
            more=results[len(shown):30]
            for j,x in enumerate(more):
                c1,c2=st.columns([5,1])
                label_bits=[v for v in [x.get("kind"),x.get("subtype"),x.get("country")] if v]
                c1.markdown("**" + x["name"] + "** — " + " · ".join(label_bits))
                with c2:
                    st.button(
                        "Open",
                        key=f"pc_terminal_more_{lens}_{j}_{x['type']}_{x['id']}",
                        use_container_width=True,
                        on_click=_open_search_result,
                        args=(lens,x["type"],x["id"],x["name"]),
                    )


def _daily_nav(lens: str):
    _clear_context()
    st.session_state['pc_document_browser'] = False
    st.session_state['pc_uae_ofac_overlap'] = False
    st.session_state[f"pc_terminal_search_{lens}"] = ""
    st.session_state[f"pc_terminal_nav_{lens}"] = "Daily Brief"


@st.cache_data(ttl=60, show_spinner=False)
def _daily_events() -> list[dict]:
    # Page the canonical event table; do not silently accept PostgREST's row cap.
    sb = _sb()
    if sb is None:
        raise RuntimeError("Database connection unavailable")
    rows = []
    offset = 0
    while True:
        page = (sb.table("pc_events").select("*").order("event_id")
                .range(offset, offset + 499).execute().data or [])
        rows.extend(page)
        if len(page) < 500:
            return rows
        offset += len(page)


def _daily_open(lens: str, event_id: str, title: str):
    st.session_state[f"pc_terminal_nav_{lens}"] = "Development"
    _set_context("event", event_id, title)


def _daily_value(row, *keys):
    containers = [row, _meta(row)]
    for name in ('fields', 'analysis', 'assessment', 'extracted_data'):
        value = _meta(row).get(name)
        if isinstance(value, dict): containers.append(value)
    values = []
    for container in containers:
        for key in keys:
            value = container.get(key)
            if value not in (None, '', [], {}):
                text = _daily_text(value)
                if text and text not in values: values.append(text)
    return '\n\n'.join(values)


def _daily_text(value):
    if isinstance(value, list):
        return '\n'.join('• ' + _daily_text(v) for v in value)
    if isinstance(value, dict):
        return '\n'.join(f"{str(k).replace('_', ' ').title()}: {_daily_text(v)}" for k, v in value.items()
                        if v not in (None, '', [], {}))
    return str(value) if value is not None else ''


@st.cache_data(ttl=60, show_spinner=False)
def _daily_table(table, key):
    sb = _sb()
    if sb is None: raise RuntimeError('Database connection unavailable')
    out = []; offset = 0
    while True:
        page = sb.table(table).select('*').order(key).range(offset, offset + 499).execute().data or []
        out.extend(page)
        if len(page) < 500: return out
        offset += len(page)


def _daily_horizon(row):
    value = ' '.join(str(row.get(k) or _meta(row).get(k) or '').lower()
                     for k in ('event_temporality', 'event_phase', 'status'))
    return bool(re.search(r'\b(scheduled|forecast|recurring|seasonal|upcoming|planned|proposed)\b', value))


def _daily_relevant(row, lens):
    def truth(key):
        return str(row.get(key) or _meta(row).get(key) or '').lower() in {'true', '1', 'yes', 'high', 'critical', 'medium'}
    blob = _record_text(row)
    if lens == 'trade': return truth('trade_relevance') or bool(TRADE_RX.search(blob)) or bool(row.get('commercial_impact') or row.get('operational_impact'))
    if lens == 'sanctions': return bool(SANCTIONS_RX.search(blob)) or row.get('_brief_kind') == 'Designation'
    if lens == 'strategic': return bool(STRATEGIC_RX.search(blob))
    return truth('intelligence_relevance') or truth('alert_worthy') or row.get('_brief_kind', 'Development') == 'Development' or bool(re.search(r'conflict|security|policy|regulat|sanction|disrupt|energy|strategic', blob, re.I))


def _daily_candidates(lens):
    specs = [('pc_events', 'event_id', ('start_date',), 'Development')]
    if lens in {'trade', 'strategic'}:
        specs += [('pc_transactions', 'transaction_id', ('announced_date', 'effective_date'), 'Transaction'),
                  ('pc_contracts', 'contract_id', ('announced_date', 'signed_date'), 'Contract')]
    if lens == 'trade':
        specs += [('pc_trade_market_observations', 'market_observation_id', ('observation_date',), 'Market observation')]
    if lens == 'sanctions':
        specs += [('pc_sanctions_designations', 'sanctions_designation_id', ('last_updated_date', 'designation_date'), 'Designation')]
    out = []; failures = []
    for table, key, datekeys, kind in specs:
        try: rows = _daily_table(table, key)
        except Exception:
            failures.append(table); continue
        for original in rows:
            row = dict(original)
            if str(row.get('record_status') or row.get('review_status') or '').lower() in {'rejected', 'draft', 'staged', 'pending_review'}: continue
            row['_brief_kind'] = kind; row['_brief_table'] = table; row['_brief_id'] = row.get(key)
            row['_brief_date'] = next((row.get(k) for k in datekeys if row.get(k)), None)
            row['title'] = row.get('title') or row.get('contract_name') or row.get('target_name') or row.get('primary_name') or ' · '.join(str(row.get(k) or '') for k in ('route_code', 'metric_name')).strip(' ·') or kind
            if _daily_relevant(row, lens): out.append(row)
    return out, failures


def _daily_details(row, lens):
    eid = str(row.get('event_id') or '')
    merged = dict(row)
    links = _filtered_rows('pc_event_links', 'event_id', eid, 500) if eid else []
    impacts = _filtered_rows('pc_event_impacts', 'event_id', eid, 100) if eid else []
    updates = _filtered_rows('pc_event_updates', 'event_id', eid, 100) if eid else []
    stories = _filtered_rows('pc_report_stories', 'event_id', eid, 50) if eid else []
    # Latest substantive updates lead; preserve the underlying event description.
    updates.sort(key=lambda x: str(x.get('occurred_at') or x.get('reported_at') or x.get('published_at') or ''), reverse=True)
    sections = [('What changed', _daily_value(row, 'description', 'summary', 'situation_update', 'scope_summary', 'notes', 'remarks'))]
    if updates:
        sections.append(('Latest recorded updates', '\n\n'.join(_daily_value(u, 'summary', 'new_claims') for u in updates[:3])))
    lenskeys = {
        'trade': ('commercial_impact', 'operational_impact', 'business_implications', 'what_it_means', 'pc_assessment', 'pc_driver', 'pc_market_signal'),
        'intelligence': ('pc_assessment', 'intelligence_assessment', 'assessment_impact', 'what_it_means', 'operational_impact', 'commercial_impact'),
        'sanctions': ('sanctions_impact', 'compliance_impact', 'designation_summary', 'remarks', 'what_it_means', 'pc_assessment', 'commercial_impact'),
        'strategic': ('strategic_impact', 'industrial_impact', 'capacity_impact', 'pc_assessment', 'what_it_means', 'commercial_impact', 'operational_impact')}
    assessment = _daily_value(row, *lenskeys[lens])
    for story in stories:
        text = _daily_value(story, *lenskeys[lens])
        if text and text not in assessment: assessment += '\n\n' + text
    if assessment.strip(): sections.append(({'trade':'Trade implications', 'intelligence':'Intelligence assessment', 'sanctions':'Sanctions / compliance implications', 'strategic':'Industrial / programme implications'}[lens], assessment.strip()))
    impact_text = '\n\n'.join(' · '.join(filter(None, [str(x.get('impact_domain') or ''), str(x.get('impact_level') or ''), _daily_value(x, 'description'), 'Expected' if x.get('expected') else 'Recorded'])) for x in impacts)
    if impact_text: sections.append(('Recorded cross-domain impacts', impact_text))
    indicators = _daily_value(row, 'monitoring_indicators', 'indicators', 'monitoring', 'trigger_threshold', 'baseline_condition', 'expected_disruption', 'impact_probability', 'impact_horizon')
    if indicators: sections.append(('Monitoring, triggers & outlook', indicators))
    facts = []
    for key in ('transaction_type','transaction_stage','regulatory_status','reported_value','currency','equity_percent','operating_control','quantity','quantity_unit','duration_years','route_code','route_description','commodity','value_numeric','value_text','unit','change_wow','change_yoy','pc_direction','designation_date','last_updated_date','delisted_date','source_list','listed_entity_type','status','confidence','verification_status'):
        if row.get(key) not in (None, '', [], {}): facts.append(f"{key.replace('_',' ').title()}: {_daily_text(row[key])}")
    if facts: sections.append(('Key recorded facts', '\n'.join(facts)))
    exposure = []; urls = _event_source_urls(row)
    for link in links:
        typ = str(link.get('linked_type') or ''); oid = str(link.get('linked_id') or '')
        if typ == 'vessel': typ = 'mobile_asset'
        if typ not in OBJECTS or not oid: continue
        record = object_record(typ, oid) or {}
        name = record.get('name') or record.get('corridor_name') or link.get('linked_name')
        if not name: continue
        pieces = [str(name), str(link.get('relationship') or '').replace('_',' ')]
        for key in ('imo', 'flag', 'asset_type', 'country', 'capacity_value', 'capacity_unit'):
            if record.get(key) not in (None, ''): pieces.append(f"{key.replace('_',' ').title()}: {record[key]}")
        if typ == 'mobile_asset':
            for c in _mobile_companies(record): pieces.append(f"{c['role']}: {c['name']}")
        elif typ == 'asset':
            for c in _asset_companies(record): pieces.append(f"{c['role']}: {c['name']}")
        exposure.append(' · '.join(filter(None, pieces)))
    for key, typ in [('buyer_entity_id','entity'), ('seller_entity_id','entity'), ('target_entity_id','entity'), ('target_asset_id','asset'), ('target_mobile_asset_id','mobile_asset')]:
        if row.get(key): exposure.append(key.replace('_id','').replace('_',' ').title() + ': ' + _object_name(typ, str(row[key])))
    if exposure: sections.append(('Linked assets, companies & exposure', '\n\n'.join(dict.fromkeys(exposure))))
    sources = [row] + impacts + updates + stories
    for item in sources:
        urls += _event_source_urls(item)
        if item.get('source_id'):
            for source in _filtered_rows('pc_sources', 'source_id', str(item['source_id']), 3): urls += _event_source_urls(source)
    for story in stories:
        if story.get('report_story_id'):
            for source in _filtered_rows('pc_report_story_sources', 'report_story_id', str(story['report_story_id']), 30): urls += _event_source_urls(source)
    return [(label, text) for label, text in sections if text.strip()], list(dict.fromkeys(urls))


def _render_daily_brief(lens: str):
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    titles = {'trade':'What Changed in Trade, Logistics & Markets', 'intelligence':'Developments, Assessments & Operational Exposure', 'sanctions':'Designations, Enforcement & Ownership Exposure', 'strategic':'Programmes, Contracts & Industrial Capacity'}
    st.title(LENS[lens]['brand'] + ' — Daily Brief')
    st.markdown('### ' + titles[lens])
    day = st.date_input('Brief date (UAE)', datetime.now(ZoneInfo('Asia/Dubai')).date(), key=f'pc_daily_date_{lens}')
    mode = st.radio('Coverage', ['Selected day', 'Last 7 days', 'Latest available sample'], horizontal=True, key=f'pc_daily_coverage_{lens}')
    with st.spinner('Reading developments and supporting records…'):
        records, failures = _daily_candidates(lens)
    if failures: st.warning('Some record collections could not be read: ' + ', '.join(failures) + '. Coverage is incomplete.')
    dated = []; horizon = []
    for row in records:
        stamp = pd.to_datetime(row.get('_brief_date'), utc=True, errors='coerce')
        if pd.isna(stamp): continue
        d = stamp.tz_convert('Asia/Dubai').date()
        if _daily_horizon(row) or d > day:
            if day <= d <= day + timedelta(days=30): horizon.append((d, row))
            continue
        dated.append((d, row))
    start = day - timedelta(days=6 if mode == 'Last 7 days' else 0)
    chosen = [(d,r) for d,r in dated if start <= d <= day]
    if mode == 'Latest available sample':
        # Recency first: severity cannot pull old records over recent developments.
        chosen = sorted([(d,r) for d,r in dated if d <= day], key=lambda x:(x[0], str(x[1].get('_brief_id'))), reverse=True)[:80]
        st.warning('Historical sample of latest available records relevant to this app; not a current-day brief.')
    def rank(item):
        d,r = item
        severity = {'critical':4,'severe':4,'high':3,'medium':2,'moderate':2,'low':1}.get(str(r.get('severity') or '').lower(),0)
        richness = bool(_daily_value(r,'commercial_impact','operational_impact','pc_assessment','what_it_means','notes','remarks'))
        return d, severity, richness, str(r.get('_brief_id'))
    unique = []; seen = set()
    for item in sorted(chosen,key=rank,reverse=True):
        d,r = item; signature = (_norm(r.get('title')), d)
        if signature in seen: continue
        seen.add(signature); unique.append(item)
    # Round-robin across record families so an event-heavy table cannot suppress markets or transactions.
    buckets = {}
    for item in unique: buckets.setdefault(item[1]['_brief_kind'], []).append(item)
    picked = []
    while buckets and len(picked) < 8:
        for kind in list(buckets):
            picked.append(buckets[kind].pop(0))
            if not buckets[kind]: del buckets[kind]
            if len(picked) == 8: break
    export = ['# ' + LENS[lens]['brand'] + ' — Daily Brief', '## ' + titles[lens], f'{day} · {mode}', '']
    if not picked:
        st.info('No current developments relevant to this app in the selected period. Choose Latest available sample to inspect existing records.')
    else:
        st.caption(f'{len(unique)} relevant records · {len(picked)} selected · dates {min(d for d,_ in chosen)} to {max(d for d,_ in chosen)}')
        st.markdown('#### At a glance')
        for _,r in picked[:5]:
            takeaway = _daily_value(r,'commercial_impact' if lens=='trade' else 'pc_assessment','what_it_means','summary')
            st.write('• ' + str(r['title']) + (' — ' + takeaway[:240] if takeaway else ''))
        for i,(d,r) in enumerate(picked,1):
            with st.container(border=True):
                st.markdown(f"### {i:02d} — {r['title']}")
                st.caption(f"{d} · {r['_brief_kind']} · {_event_region_label(r)}")
                sections, urls = _daily_details(r,lens)
                export.extend([f"### {i:02d} — {r['title']}",f"{d} · {r['_brief_kind']}"])
                for label,text in sections:
                    st.markdown('**' + label + '**'); st.write(text)
                    export.extend(['**'+label+'**',text])
                if not sections: st.caption('Supporting narrative is not recorded; open the source record for review.')
                for url in urls:
                    st.link_button('Source evidence',url); export.append(url)
                if not urls: st.caption('Source evidence link missing from the stored record.')
                if r.get('event_id'):
                    st.button('Open development and evidence',key=f"pc_daily_open_{lens}_{i}_{r['event_id']}",on_click=_daily_open,args=(lens,str(r['event_id']),str(r['title'])))
                else:
                    with st.expander('Supporting record'):
                        safe = {k:v for k,v in r.items() if not k.startswith('_') and not k.endswith('_id') and k not in {'raw_record','metadata'}}
                        st.write(_daily_text(safe))
                export.append('')
    if horizon:
        with st.expander('Look ahead — scheduled and expected items (next 30 days)'):
            for d,r in sorted(horizon,key=lambda x:x[0])[:6]:
                st.markdown(f"**{d} — {r['title']}**")
                text = _daily_value(r,'expected_disruption','trigger_threshold','commercial_impact','operational_impact')
                if text: st.write(text)
        export.append('## Look ahead')
        for d,r in sorted(horizon,key=lambda x:x[0])[:6]: export.append(f"{d} — {r['title']}")
    if picked or horizon:
        st.download_button('Download brief','\n'.join(export),file_name=f'PC_{lens}_Daily_{day}.md',mime='text/markdown')


def _sidebar_nav(lens: str, label: str, query: str=""):
    _clear_context()
    st.session_state['pc_document_browser'] = False
    st.session_state['pc_uae_ofac_overlap'] = False
    st.session_state[f"pc_terminal_workspace_{lens}"]=""
    st.session_state[f"pc_terminal_search_{lens}"]=query
    st.session_state[f"pc_terminal_nav_{lens}"]=label

def _home_nav(lens: str):
    _clear_context()
    st.session_state['pc_document_browser'] = False
    st.session_state['pc_uae_ofac_overlap'] = False
    st.session_state[f"pc_terminal_workspace_{lens}"]=""
    st.session_state[f"pc_terminal_search_{lens}"]=""
    st.session_state[f"pc_terminal_nav_{lens}"]="Home"

def _render_publication_workspace(sb, lens: str, mode: str):
    try:
        from pc_report_studio import render_report_studio
    except Exception as exc:
        st.error(f"Report workspace could not load: {exc}")
        return
    typ,oid,rec=_context_record()
    context=(typ,oid,rec) if typ and oid and rec else None
    render_report_studio(sb,context=context,mode=mode)

def _render_sanctions_query_report(sb):
    try:
        from pc_sanctions_report import render_sanctions_report_area
    except Exception as exc:
        st.error(f"Sanctions report workspace could not load: {exc}")
        return
    typ,oid,rec=_context_record()
    context=(typ,oid,rec) if typ and oid and rec else None
    render_sanctions_report_area(sb,context=context)


def render_terminal(lens: str = "trade"):
    lens = lens if lens in LENS else "trade"
    cfg = LENS[lens]
    sb = _sb()
    if sb is None:
        st.error("P&C database connection is not configured.")
        st.stop()

    with st.sidebar:
        st.markdown("<div class='pc-k'>POWER & CORRIDORS INTELLIGENCE</div>", unsafe_allow_html=True)
        st.markdown("### " + cfg["brand"])
        st.caption("Shared canonical terminal · " + cfg["deck"])
        theme = st.radio("Appearance", ["Light", "Dark"], horizontal=True,
                         index=0 if st.session_state.get("pc_terminal_theme","Light")=="Light" else 1,
                         key="pc_terminal_theme")
        st.divider()
        st.button("Daily Brief", key=f"pc_daily_sidebar_{lens}", use_container_width=True,
                  on_click=_daily_nav, args=(lens,))
        navs={
            "trade":[
                ("Home",""),("Companies","company"),("Infrastructure","port"),
                ("Vessels","vessel"),("Corridors","corridor"),("Markets","freight"),
                ("Sanctions & Compliance","sanction"),("Strategic Industries","shipyard"),
                ("Events","event"),("Brief Builder","__brief_builder__"),
                ("Report Library","__report_library__"),("Documents","document")
            ],
            "intelligence":[
                ("Operating Picture",""),("Priority Intelligence","security"),
                ("Regional / Chokepoints","corridor"),("Security & Maritime","maritime security"),
                ("Disruptions","disruption"),("Sanctions","sanction"),
                ("Monitoring & Indicators","monitoring"),
                ("Report Studio","__report_studio__"),
                ("Brief Builder","__brief_builder__"),
                ("Report Library","__report_library__"),
                ("Documents","document")
            ],
            "sanctions":[
                ("Exposure Picture",""),("Designations","sanction"),("Screening","screening"),
                ("Ownership & Control","ownership"),("Vessels","vessel"),
                ("Jurisdictions / Regimes","OFAC"),("Events","sanction"),
                ("Query & Report Studio","__sanctions_report__"),
                ("Report Library","__report_library__"),("Evidence","document")
            ],
            "strategic":[
                ("Industrial Picture",""),("Organisations","coast guard"),("Shipyards","shipyard"),
                ("Programmes","programme"),("Production","shipbuilding"),("Fleets / Platforms","vessel"),
                ("Security Operations","security operation"),("Documents","document")
            ],
        }
        current=st.session_state.get(f"pc_terminal_nav_{lens}",
                                     "Home" if lens=="trade" else
                                     "Operating Picture" if lens=="intelligence" else
                                     "Exposure Picture" if lens=="sanctions" else "Industrial Picture")
        for i,(label,query) in enumerate(navs.get(lens,[])):
            if query.startswith("__"):
                def _set_workspace(_lens=lens,_label=label,_mode=query):
                    _clear_context()
                    st.session_state[f"pc_terminal_nav_{_lens}"]=_label
                    st.session_state[f"pc_terminal_workspace_{_lens}"]=_mode
                    st.session_state[f"pc_terminal_search_{_lens}"]=""
                cb=_set_workspace
                args=()
            else:
                cb=_home_nav if not query else _sidebar_nav
                args=(lens,) if not query else (lens,label,query)
            st.button(
                ("● " if label==current else "")+label,
                key=f"pc_nav_{lens}_{i}",
                use_container_width=True,
                on_click=cb,
                args=args,
            )
        st.divider()
        if lens in ('sanctions','trade','intelligence') and st.button('UAE / OFAC vessel overlap', use_container_width=True):
            _clear_context()
            st.session_state['pc_document_browser'] = False
            st.session_state['pc_uae_ofac_overlap'] = True
            st.rerun()
        if st.button("Documents & vessel restrictions", use_container_width=True):
            _clear_context()
            st.session_state['pc_uae_ofac_overlap'] = False
            st.session_state['pc_document_browser'] = True
            st.rerun()
        if st.button("Home / clear selection", use_container_width=True):
            st.session_state['pc_document_browser'] = False
            st.session_state['pc_uae_ofac_overlap'] = False
            _clear_context()
            st.rerun()
        if st.button("Refresh database", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
        st.caption("Terminal index: " + ("active" if _terminal_index_ready() else "legacy fallback"))

    _style(theme)
    _restore_context()
    if st.session_state.get('pc_uae_ofac_overlap'):
        st.markdown('### UAE / OFAC vessel overlap')
        st.caption('Shared hulls matched by IMO. UAE entry restrictions and OFAC designations retain separate authorities, dates and source records.')
        try:
            rows=[]; offset=0
            while True:
                page=sb.table('pc_v_uae_ofac_vessel_overlap').select('*').order('imo').range(offset,offset+499).execute().data or []
                rows.extend(page)
                if len(page)<500: break
                offset+=500
            if rows:
                st.dataframe([{'Vessel':r['name'],'IMO':r['imo'],'UAE listed flag':r['uae_listed_flag'],
                    'UAE circular':r['circular_reference'],'OFAC listed name':r['ofac_name'],
                    'OFAC designation date':r['designation_date'],'OFAC programmes':', '.join(r.get('ofac_programmes') or [])} for r in rows],
                    hide_index=True,use_container_width=True)
                _open_selector([{'type':'mobile_asset','id':r['mobile_asset_id'],'name':r['name'],'relationship':'UAE / OFAC source overlap'} for r in rows],
                    'pc_overlap_vessels','Open vessel evidence')
            else:
                st.info('No overlap stored yet. Import both source files and resolve their vessel identifiers.')
        except Exception as exc:
            st.warning('UAE / OFAC overlap unavailable: '+str(exc)[:200])
        return
    if st.session_state.get('pc_document_browser'):
        from pc_document_vessels import render_document_evidence
        st.markdown('### Documents & vessel restrictions')
        query = st.text_input('Find a document by title', key='pc_doc_title_search')
        request = sb.table('pc_documents').select('document_id,title').order('created_at', desc=True).limit(100)
        if query.strip():
            request = request.ilike('title', '%' + query.strip() + '%')
        docs = request.execute().data or []
        if docs:
            choices = {d['document_id']: d for d in docs}
            selected = st.selectbox('Source document', list(choices), format_func=lambda k: choices[k]['title'])
            try:
                render_document_evidence(sb, selected, _set_context)
            except Exception as exc:
                st.warning('Document evidence unavailable: ' + str(exc)[:180])
        else:
            st.info('No matching documents.')
        return
    st.button("Daily Brief", key=f"pc_daily_top_{lens}", on_click=_daily_nav, args=(lens,))
    if st.session_state.get(f"pc_terminal_nav_{lens}") == "Daily Brief":
        _render_daily_brief(lens)
        return

    workspace=st.session_state.get(f"pc_terminal_workspace_{lens}","")
    if workspace:
        if workspace=="__report_studio__":
            _render_publication_workspace(sb,lens,"studio")
        elif workspace=="__brief_builder__":
            _render_publication_workspace(sb,lens,"brief")
        elif workspace=="__report_library__":
            _render_publication_workspace(sb,lens,"library")
        elif workspace=="__sanctions_report__":
            _render_sanctions_query_report(sb)
        return

    st.markdown("<div class='pc-command'><div class='pc-k'>GLOBAL COMMAND BAR</div>", unsafe_allow_html=True)
    q = st.text_input(
        "Search company, vessel / IMO, port, terminal, airport, dry port, rail node, corridor, event or sanction",
        placeholder="AD Ports, Rotterdam, Jebel Ali, IMO 9251822, Tbilisi Dry Port, Hormuz…",
        key=f"pc_terminal_search_{lens}",
    )
    st.markdown("</div>", unsafe_allow_html=True)

    if q.strip():
        results = _search_objects(q, lens, 80)
        if results:
            _render_search_results(results, lens)
        else:
            st.info("No canonical object matched that search.")

    typ, oid, rec = _context_record()
    if not typ or not oid or not rec:
        _render_home(lens)
        return

    if typ == 'document':
        from pc_document_vessels import render_document_evidence
        render_document_evidence(sb, oid, _set_context)
        return
    _render_context_header(typ, oid, rec, lens)

    # Persistent tactical workspace: dossier left, spatial/system center, evidence right.
    left, center, right = st.columns([1.0, 1.25, 1.0], gap="large")
    with left:
        with st.container(border=True):
            _render_dossier_pane(typ,oid,rec,lens)
    with center:
        with st.container(border=True):
            _render_spatial_pane(typ,oid,rec,lens)
    with right:
        with st.container(border=True):
            _render_evidence_pane(typ,oid,rec,lens)

    st.divider()
    st.markdown("### Chronological Development & Event Ticker")
    _render_timeline(typ,oid)

    with st.expander("Developer / raw canonical record"):
        st.caption("Internal diagnostic view. Normal analyst workflow should not require raw IDs or JSON.")
        st.json(rec)

