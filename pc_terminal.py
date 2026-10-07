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
from pc_corporate_network import render_network

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


@st.cache_data(ttl=120, show_spinner=False)
def _asset_dossier_rpc(asset_id: str, max_depth: int = 4, max_nodes: int = 250) -> dict:
    """Fast database-side infrastructure dossier.

    The RPC resolves the shared physical ecosystem and its commercial/strategic
    records once in PostgreSQL.  Keep a graceful fallback while deployments catch up.
    """
    sb=_sb()
    if sb is None or not asset_id:
        return {}
    try:
        data=sb.rpc("pc_terminal_asset_dossier",{
            "p_asset_id":str(asset_id),
            "p_max_depth":int(max_depth),
            "p_max_nodes":int(max_nodes),
        }).execute().data
        return data if isinstance(data,dict) else {}
    except Exception:
        return {}


def _dossier_local(dossier: dict) -> list[dict]:
    """Adapt RPC asset rows to the legacy local-infrastructure card shape."""
    out=[]
    for a in (dossier or {}).get("assets") or []:
        if _clean(a.get("scope_kind"))=="root" or int(a.get("depth") or 0)==0:
            continue
        out.append({
            "type":"asset",
            "id":_clean(a.get("asset_id")),
            "name":_clean(a.get("name")) or _clean(a.get("asset_id")),
            "relationship":(_clean(a.get("scope_relationship")) or "contained infrastructure").replace("_"," "),
            "asset_type":a.get("asset_type"),
            "subtype":a.get("subtype"),
            "region":a.get("region_city"),
            "country":a.get("country"),
            "depth":int(a.get("depth") or 0),
        })
    return out


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

def _graph_neighborhood(typ: str, oid: str, depth: int=2, max_nodes: int=500) -> dict:
    """Walk the terminal relationship index from one canonical object."""
    start=(typ,str(oid))
    nodes={start:{"type":typ,"id":str(oid),"name":str(oid)}}
    edges=[]
    frontier=[start]
    seen_edges=set()
    for hop in range(max(1,min(depth,3))):
        next_frontier=[]
        for ntyp,nid in frontier:
            for l in _indexed_links(ntyp,nid,1200):
                lk=_clean(l.get("link_key")) or repr((l.get("source_type"),l.get("source_id"),l.get("relation_type"),l.get("target_type"),l.get("target_id")))
                if lk in seen_edges:
                    continue
                seen_edges.add(lk)
                is_src=_clean(l.get("source_type"))==ntyp and _clean(l.get("source_id"))==nid
                otyp=_clean(l.get("target_type") if is_src else l.get("source_type")).casefold()
                oid2=_clean(l.get("target_id") if is_src else l.get("source_id"))
                oname=_clean(l.get("target_name") if is_src else l.get("source_name"))
                if not otyp or not oid2:
                    continue
                if otyp=="vessel":
                    otyp="mobile_asset"
                node_key=(otyp,oid2)
                if node_key not in nodes:
                    nodes[node_key]={"type":otyp,"id":oid2,"name":oname or oid2}
                    if len(nodes)<max_nodes:
                        next_frontier.append(node_key)
                edges.append({
                    "source_type":_clean(l.get("source_type")),
                    "source_id":_clean(l.get("source_id")),
                    "source_name":_clean(l.get("source_name")),
                    "target_type":_clean(l.get("target_type")),
                    "target_id":_clean(l.get("target_id")),
                    "target_name":_clean(l.get("target_name")),
                    "relationship":_clean(l.get("relation_type")),
                    "family":_clean(l.get("relation_family")),
                    "source_table":_clean(l.get("source_table")),
                    "source_record_id":_clean(l.get("source_record_id")),
                    "event_id":_clean(l.get("event_id")),
                    "confidence":_clean(l.get("confidence")),
                    "evidence_url":_clean(l.get("evidence_url")),
                    "metadata":l.get("metadata") or {},
                    "hop":hop+1,
                })
        frontier=next_frontier
        if not frontier or len(nodes)>=max_nodes:
            break
    return {"nodes":list(nodes.values()),"edges":edges}


def _entity_graph_neighborhood(entity_id: str, depth: int=2) -> dict:
    """Canonical entity graph built from live relationship tables first.

    pc_terminal_link_index remains an accelerator, but canonical relationship tables
    are the source of truth so a stale/incomplete terminal index cannot make a company
    appear empty.
    """
    bundle=_entity_identity_bundle(str(entity_id))
    entity_ids=bundle.get("ids") or [str(entity_id)]

    nodes={}
    edges=[]
    seen_edges=set()

    def add_node(typ: str, oid: str, name: str=""):
        typ=_clean(typ).casefold()
        if typ=="vessel": typ="mobile_asset"
        oid=_clean(oid)
        if not typ or not oid:
            return
        key=(typ,oid)
        if key not in nodes:
            nm=_clean(name)
            if not nm:
                try:
                    nm=_object_name(typ,oid) if typ in OBJECTS or typ=="corridor" else oid
                except Exception:
                    nm=oid
            nodes[key]={"type":typ,"id":oid,"name":nm or oid}

    def add_edge(source_type,source_id,target_type,target_id,relationship,
                 family="",source_table="",source_record_id="",event_id="",
                 confidence="",evidence_url="",metadata=None):
        styp=_clean(source_type).casefold()
        ttyp=_clean(target_type).casefold()
        if styp=="vessel": styp="mobile_asset"
        if ttyp=="vessel": ttyp="mobile_asset"
        sid=_clean(source_id); tid=_clean(target_id)
        if not styp or not ttyp or not sid or not tid:
            return
        rel=_clean(relationship) or "related_to"
        key=(styp,sid,rel,ttyp,tid,_clean(source_table),_clean(source_record_id))
        if key in seen_edges:
            return
        seen_edges.add(key)
        add_node(styp,sid)
        add_node(ttyp,tid)
        edges.append({
            "source_type":styp,"source_id":sid,
            "source_name":nodes.get((styp,sid),{}).get("name",""),
            "target_type":ttyp,"target_id":tid,
            "target_name":nodes.get((ttyp,tid),{}).get("name",""),
            "relationship":rel,
            "family":_clean(family),
            "source_table":_clean(source_table),
            "source_record_id":_clean(source_record_id),
            "event_id":_clean(event_id),
            "confidence":_clean(confidence),
            "evidence_url":_clean(evidence_url),
            "metadata":metadata or {},
        })

    for eid in entity_ids:
        add_node("entity",eid,_object_name("entity",eid))

    # 1) Generic canonical graph edges.
    for eid in entity_ids:
        for side in ("source","target"):
            for r in _filtered_rows("pc_relationships",f"{side}_id",eid,1000):
                add_edge(
                    r.get("source_type"),r.get("source_id"),
                    r.get("target_type"),r.get("target_id"),
                    r.get("relationship_type"),
                    "relationship","pc_relationships",r.get("relationship_id"),
                    confidence=r.get("confidence"),
                    evidence_url=r.get("source_url"),
                    metadata=r,
                )

    # 2) Company -> fixed/mobile assets.
    for eid in entity_ids:
        for r in _filtered_rows("pc_company_asset_roles","entity_id",eid,1000):
            aid=_clean(r.get("mobile_asset_id") or r.get("asset_id"))
            typ="mobile_asset" if r.get("mobile_asset_id") else "asset"
            add_edge(
                "entity",eid,typ,aid,r.get("asset_role"),
                "asset_role","pc_company_asset_roles",
                r.get("company_asset_role_id") or r.get("id"),
                confidence=r.get("confidence"),
                evidence_url=r.get("source_url"),
                metadata=r,
            )

    # 3) Company -> corridors.
    for eid in entity_ids:
        for r in _filtered_rows("pc_company_corridor_roles","entity_id",eid,1000):
            add_edge(
                "entity",eid,"corridor",r.get("corridor_key"),r.get("corridor_role"),
                "corridor_role","pc_company_corridor_roles",
                r.get("company_corridor_role_id") or r.get("id"),
                confidence=r.get("confidence"),
                evidence_url=r.get("source_url"),
                metadata=r,
            )

    # 4) Portfolio/investment relationships.
    for eid in entity_ids:
        for r in _filtered_rows("pc_company_portfolio_positions","holder_entity_id",eid,1000):
            if r.get("investee_entity_id"):
                add_edge(
                    "entity",eid,"entity",r.get("investee_entity_id"),r.get("position_type"),
                    "portfolio","pc_company_portfolio_positions",r.get("portfolio_position_id"),
                    confidence=r.get("position_status"),metadata=r,
                )
            elif r.get("investee_asset_id"):
                add_edge(
                    "entity",eid,"asset",r.get("investee_asset_id"),r.get("position_type"),
                    "portfolio","pc_company_portfolio_positions",r.get("portfolio_position_id"),
                    confidence=r.get("position_status"),metadata=r,
                )
        # Reverse investee relationships also matter for ownership/control context.
        for r in _filtered_rows("pc_company_portfolio_positions","investee_entity_id",eid,1000):
            add_edge(
                "entity",r.get("holder_entity_id"),"entity",eid,r.get("position_type"),
                "portfolio","pc_company_portfolio_positions",r.get("portfolio_position_id"),
                confidence=r.get("position_status"),metadata=r,
            )

    # 5) Explicit event links only — no company-name substring matching.
    for eid in entity_ids:
        for r in _filtered_rows("pc_event_links","linked_id",eid,1500):
            linked_type=_clean(r.get("linked_type")).casefold()
            if linked_type not in {"entity","company","organisation","organization"}:
                continue
            add_edge(
                "event",r.get("event_id"),"entity",eid,r.get("relationship"),
                "event_context","pc_event_links",r.get("event_link_id") or r.get("id"),
                event_id=r.get("event_id"),confidence=r.get("confidence"),
                evidence_url=r.get("source_url"),metadata=r,
            )

    # 6) Documents explicitly linked to the entity.
    for eid in entity_ids:
        for r in _filtered_rows("pc_document_entity_links","entity_id",eid,1000):
            add_edge(
                "entity",eid,"document",r.get("document_id"),r.get("relationship"),
                "evidence","pc_document_entity_links",r.get("document_entity_link_id") or r.get("id"),
                confidence=r.get("confidence"),evidence_url=r.get("source_url"),metadata=r,
            )

    # 7) Sanctions explicitly linked to the entity.
    for eid in entity_ids:
        for r in _filtered_rows("pc_sanctions_designations","entity_id",eid,1000):
            sid=_clean(r.get("sanctions_designation_id"))
            add_edge(
                "sanction",sid,"entity",eid,"designates",
                "sanctions","pc_sanctions_designations",sid,
                confidence=r.get("confidence"),evidence_url=r.get("source_url"),metadata=r,
            )

    # 8) Defence programmes: customer, lead contractor, participants, shipyards.
    programme_ids=set()
    for eid in entity_ids:
        for col,role in (("lead_contractor_entity_id","lead_contractor"),
                         ("customer_entity_id","customer")):
            for r in _filtered_rows("pc_defence_programmes",col,eid,1000):
                pid=_clean(r.get("defence_programme_id"))
                if pid:
                    programme_ids.add(pid)
                    add_edge(
                        "programme",pid,"entity",eid,role,
                        "strategic_industry","pc_defence_programmes",pid,
                        confidence=r.get("verification_status"),
                        evidence_url=r.get("source_url"),metadata=r,
                    )
        for r in _filtered_rows("pc_defence_programme_participants","entity_id",eid,1500):
            pid=_clean(r.get("defence_programme_id"))
            if pid:
                programme_ids.add(pid)
                add_edge(
                    "programme",pid,"entity",eid,r.get("participant_role"),
                    "strategic_industry","pc_defence_programme_participants",
                    r.get("programme_participant_id") or r.get("id"),
                    confidence=r.get("verification_status"),
                    evidence_url=r.get("source_url"),metadata=r,
                )
            if r.get("shipyard_asset_id"):
                add_edge(
                    "entity",eid,"asset",r.get("shipyard_asset_id"),
                    r.get("participant_role") or "shipyard",
                    "strategic_industry","pc_defence_programme_participants",
                    r.get("programme_participant_id") or r.get("id"),
                    confidence=r.get("verification_status"),
                    evidence_url=r.get("source_url"),metadata=r,
                )

    # 9) Shipbuilding production/capacity direct company links.
    for eid in entity_ids:
        for r in _filtered_rows("pc_shipbuilding_production_tasks","builder_entity_id",eid,2000):
            if r.get("shipyard_asset_id"):
                add_edge(
                    "entity",eid,"asset",r.get("shipyard_asset_id"),
                    r.get("task_type") or "builder_at",
                    "shipbuilding_production","pc_shipbuilding_production_tasks",
                    r.get("production_task_id"),
                    confidence=r.get("verification_status"),
                    evidence_url=r.get("source_url"),metadata=r,
                )
            pid=_clean(r.get("defence_programme_id"))
            if pid:
                programme_ids.add(pid)
                add_edge(
                    "entity",eid,"programme",pid,r.get("task_type") or "production_for",
                    "shipbuilding_production","pc_shipbuilding_production_tasks",
                    r.get("production_task_id"),
                    confidence=r.get("verification_status"),
                    evidence_url=r.get("source_url"),metadata=r,
                )

        for r in _filtered_rows("pc_shipyard_capacity_history","operator_entity_id",eid,1500):
            add_edge(
                "entity",eid,"asset",r.get("shipyard_asset_id"),"operates_shipyard",
                "shipyard_capacity","pc_shipyard_capacity_history",
                r.get("shipyard_capacity_history_id"),
                confidence=r.get("verification_status"),
                evidence_url=r.get("source_url"),metadata=r,
            )

    # 10) Security operations.
    for eid in entity_ids:
        for r in _filtered_rows("pc_security_operations","lead_entity_id",eid,1000):
            add_edge(
                "security_operation",r.get("security_operation_id"),"entity",eid,"lead_entity",
                "security_operation","pc_security_operations",r.get("security_operation_id"),
                confidence=r.get("verification_status"),
                evidence_url=r.get("source_url"),metadata=r,
            )
        for r in _filtered_rows("pc_security_operation_participants","entity_id",eid,1000):
            add_edge(
                "security_operation",r.get("security_operation_id"),"entity",eid,r.get("participant_role"),
                "security_operation","pc_security_operation_participants",
                r.get("security_operation_participant_id") or r.get("id"),
                confidence=r.get("verification_status"),
                evidence_url=r.get("source_url"),metadata=r,
            )

    # 11) Company milestones, where relationships are explicit.
    for eid in entity_ids:
        for r in _filtered_rows("pc_company_milestones","entity_id",eid,1000):
            if r.get("event_id"):
                add_edge(
                    "entity",eid,"event",r.get("event_id"),r.get("milestone_type"),
                    "company_milestone","pc_company_milestones",r.get("company_milestone_id"),
                    event_id=r.get("event_id"),confidence=r.get("milestone_status"),
                    evidence_url=r.get("source_url"),metadata=r,
                )
            if r.get("related_asset_id"):
                add_edge(
                    "entity",eid,"asset",r.get("related_asset_id"),r.get("milestone_type"),
                    "company_milestone","pc_company_milestones",r.get("company_milestone_id"),
                    confidence=r.get("milestone_status"),
                    evidence_url=r.get("source_url"),metadata=r,
                )
            if r.get("related_entity_id"):
                add_edge(
                    "entity",eid,"entity",r.get("related_entity_id"),r.get("milestone_type"),
                    "company_milestone","pc_company_milestones",r.get("company_milestone_id"),
                    confidence=r.get("milestone_status"),
                    evidence_url=r.get("source_url"),metadata=r,
                )

    # 12) Union indexed graph for any relationship families added elsewhere.
    for eid in entity_ids:
        g=_graph_neighborhood("entity",eid,depth=max(1,min(depth,3)),max_nodes=500)
        for n in g.get("nodes") or []:
            add_node(n.get("type"),n.get("id"),n.get("name"))
        for e in g.get("edges") or []:
            add_edge(
                e.get("source_type"),e.get("source_id"),
                e.get("target_type"),e.get("target_id"),
                e.get("relationship"),e.get("family"),
                e.get("source_table"),e.get("source_record_id"),
                e.get("event_id"),e.get("confidence"),
                e.get("evidence_url"),e.get("metadata"),
            )

    return {"nodes":list(nodes.values()),"edges":edges}



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
    # Keep a lightweight dossier history so every arrow/open action is reversible.
    prev_typ=st.session_state.get("pc_terminal_type")
    prev_id=st.session_state.get("pc_terminal_id")
    if prev_typ and prev_id and (str(prev_typ),str(prev_id)) != (str(typ),str(oid)):
        history=st.session_state.setdefault("pc_terminal_history",[])
        history.append({
            "type":str(prev_typ),
            "id":str(prev_id),
            "name":st.session_state.get("pc_terminal_name") or object_label(prev_typ,prev_id),
        })
        if len(history)>40:
            del history[:-40]
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


def _back_context():
    history=st.session_state.get("pc_terminal_history") or []
    if not history:
        return
    prev=history.pop()
    st.session_state["pc_terminal_history"]=history
    # Restore directly rather than calling _set_context, which would push the
    # current dossier back onto the history stack.
    st.session_state["pc_document_browser"]=False
    st.session_state["pc_uae_ofac_overlap"]=False
    st.session_state["pc_terminal_type"]=prev["type"]
    st.session_state["pc_terminal_id"]=prev["id"]
    st.session_state["pc_terminal_name"]=prev.get("name") or object_label(prev["type"],prev["id"])
    try:
        st.query_params["pc_terminal_type"]=prev["type"]
        st.query_params["pc_terminal_id"]=prev["id"]
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
    st.session_state.pop("pc_terminal_history",None)
    for k in ("pc_terminal_type", "pc_terminal_id", "pc_terminal_name"):
        st.session_state.pop(k, None)
    try:
        for k in ("pc_terminal_type", "pc_terminal_id"):
            if k in st.query_params:
                del st.query_params[k]
    except Exception:
        pass


@st.cache_data(ttl=60, show_spinner=False)
def _entity_identity_bundle(entity_id: str) -> dict:
    """Resolve equivalent company/entity identities without ever crashing the terminal."""
    base=object_record("entity",entity_id) or {}
    base_name=_clean(base.get("name"))
    base_country=_clean(base.get("hq_country") or base.get("country")).casefold()

    def core(v):
        words=_norm(v).split()
        suffixes={"group","holding","holdings","company","co","corporation","corp",
                  "limited","ltd","llc","plc","pjsc","sak","sa","inc"}
        while words and words[-1] in suffixes:
            words.pop()
        return " ".join(words)

    try:
        aliases_by_id={}
        for a in _rows("pc_identity_aliases_v2",10000):
            typ=_clean(a.get("object_type")).casefold()
            if typ not in {"entity","company","organisation","organization"}:
                continue
            cid=_clean(a.get("canonical_id"))
            nm=_clean(a.get("alias_name"))
            if cid and nm:
                aliases_by_id.setdefault(cid,set()).add(nm)

        seed_names={base_name} | aliases_by_id.get(str(entity_id),set())
        seed_norm={_norm(x) for x in seed_names if _norm(x)}
        seed_core={core(x) for x in seed_names if core(x)}
        candidates=[]

        for r in _rows("pc_entities",10000):
            rid=_clean(r.get("entity_id"))
            if not rid:
                continue
            rcountry=_clean(r.get("hq_country") or r.get("country")).casefold()
            if base_country and rcountry and base_country!=rcountry:
                continue
            names={_clean(r.get("name"))} | aliases_by_id.get(rid,set())
            norms={_norm(x) for x in names if _norm(x)}
            cores={core(x) for x in names if core(x)}
            strong=bool(seed_norm & norms or seed_core & cores)
            if not strong:
                for a in seed_norm:
                    if any(len(a)>=7 and len(b)>=7 and (a in b or b in a) for b in norms):
                        strong=True
                        break
            if strong:
                candidates.append(r)

        if base and not any(_clean(x.get("entity_id"))==str(entity_id) for x in candidates):
            candidates.append(base)

        ranked=[]
        for r in candidates:
            rid=_clean(r.get("entity_id"))
            score=0
            if rid.startswith("COMP_"): score+=80
            if not any(x in rid.upper() for x in ("AUTO","_AI_")): score+=30
            for table,weight in (
                ("pc_company_profiles",30),
                ("pc_company_asset_roles",8),
                ("pc_company_corridor_roles",6),
                ("pc_event_links",3),
            ):
                try:
                    col="linked_id" if table=="pc_event_links" else "entity_id"
                    score+=len(_filtered_rows(table,col,rid,80))*weight
                except Exception:
                    pass
            ranked.append((score,rid,r))
        ranked.sort(key=lambda x:(x[0],x[1]),reverse=True)

        preferred_id=ranked[0][1] if ranked else str(entity_id)
        preferred_record=ranked[0][2] if ranked else base
        ids=[]; names=[]
        for _,rid,r in ranked:
            if rid not in ids: ids.append(rid)
            nm=_clean(r.get("name"))
            if nm and nm not in names: names.append(nm)
            for a in sorted(aliases_by_id.get(rid,set())):
                if a not in names: names.append(a)

        return {
            "preferred_id":preferred_id,
            "preferred_record":preferred_record,
            "ids":ids or [str(entity_id)],
            "names":names or ([base_name] if base_name else []),
        }
    except Exception:
        return {
            "preferred_id":str(entity_id),
            "preferred_record":base,
            "ids":[str(entity_id)],
            "names":[base_name] if base_name else [],
        }


@st.cache_data(ttl=60, show_spinner=False)
def _multi_filtered_rows(table: str, column: str, values: list[str], limit_each: int=500) -> list[dict]:
    out=[]; seen=set()
    for v in values or []:
        try:
            rows=_filtered_rows(table,column,str(v),limit_each)
        except Exception:
            rows=[]
        for r in rows:
            key=json.dumps(r,sort_keys=True,default=str)
            if key in seen: continue
            seen.add(key); out.append(r)
    return out


def _context_record():
    typ,oid=_get_context()
    if not typ or not oid:
        return None,None,None
    rec=object_record(typ,oid)
    if typ=="entity" and rec:
        try:
            bundle=_entity_identity_bundle(str(oid))
            return typ,bundle.get("preferred_id") or oid,bundle.get("preferred_record") or rec
        except Exception:
            return typ,oid,rec
    return typ,oid,rec


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
    for item in _linked_objects_from_relationships("asset",aid):
        if item.get("type")!="entity":
            continue
        role=_clean(item.get("relationship")).casefold()
        if role not in {"owns","owned by","operates","operated by","manages","managed by","controls","controlled by"}:
            continue
        eid=_clean(item.get("id"))
        if eid and eid not in seen:
            seen.add(eid)
            out.append({"id":eid,"name":item.get("name") or _object_name("entity",eid),"role":role})
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
        point=_coords_from_record(r)
        if point:
            evidence=_meta(r).get("spatial_evidence") or {}
            precision=evidence.get("precision") if evidence.get("applied") else "stored coordinate"
            pts.append({"lat":point[0],"lon":point[1],"name":label,"precision":precision})
    add(rec, _clean(rec.get("name")))
    connected=_local_infrastructure(rec)
    for item in connected:
        r=object_record("asset",item["id"]) or {}
        add(r,_clean(r.get("name")) or item["name"])
    if pts:
        st.map(pd.DataFrame(pts), latitude="lat", longitude="lon", size=40, zoom=None)
        st.caption(f"{len(pts)} mapped locations in the connected system. Address points locate buildings or entrances; they do not define facility boundaries.")
        with st.expander("Mapped locations & precision"):
            st.dataframe(pd.DataFrame(pts).rename(columns={"name":"Location","precision":"Precision","lat":"Latitude","lon":"Longitude"}),hide_index=True,use_container_width=True)
        if not _coords_from_record(rec):
            st.caption("The selected asset has no stored coordinate; the map shows its connected locations.")
    else:
        st.caption("No canonical coordinates are currently stored for this node or its local connected assets.")
    from urllib.parse import quote
    query=" ".join(_clean(rec.get(k)) for k in ("name","region_city","country") if rec.get(k))
    if query:
        st.link_button("Find this location on a map","https://www.google.com/maps/search/?api=1&query="+quote(query))


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


def _render_event_rows(events: list[dict], key_prefix: str, limit: int=10):
    """Readable event list with direct drill-down and source access."""
    if not events:
        st.caption("No linked canonical developments.")
        return
    for i,e in enumerate(events[:limit]):
        title=_clean(e.get("title")) or "Untitled development"
        dt=_clean(e.get("start_date"))[:10]
        etype=_clean(e.get("event_type") or e.get("event_nature")).replace("_"," ").title()
        loc=_event_region_label(e)
        cols=st.columns([4.0,1.0,1.0])
        with cols[0]:
            st.markdown(f"**{title}**")
            meta=" · ".join(x for x in [dt,etype,loc if loc!="Global / unspecified" else ""] if x)
            if meta: st.caption(meta)
        eid=_clean(e.get("event_id"))
        if eid:
            cols[1].button(
                "Open",
                key=f"{key_prefix}_open_{i}_{eid}",
                use_container_width=True,
                on_click=_set_context,
                args=("event",eid,title),
            )
        urls=_event_source_urls(e)
        if urls:
            cols[2].link_button("Source",urls[0],use_container_width=True)
        impact=_clean(e.get("commercial_impact") or e.get("operational_impact") or e.get("pc_assessment"))
        if impact:
            st.write(impact[:700])
        st.markdown("<div style='height:1px;background:var(--line);margin:.1rem 0 .45rem'></div>",unsafe_allow_html=True)


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
    loc=_display_location(e)
    if loc:
        return loc[:55] + ("…" if len(loc)>55 else "")
    for k in ("region","country","countries"):
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
                if st.button("→",key=f"featured_{lens}_{i}_{_norm(query)}",use_container_width=True):
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


def _event_source_urls(row: dict) -> list[str]:
    """Collect stored evidence URLs from events, sources, report stories and generic records."""
    if not isinstance(row,dict):
        return []
    urls=[]
    def add(v):
        if isinstance(v,str):
            v=v.strip()
            if v.startswith(("http://","https://")) and v not in urls:
                urls.append(v)

    for key in (
        "source_url","url","article_url","reference_url","original_url",
        "publication_url","document_url","evidence_url","source_link"
    ):
        add(row.get(key))

    meta=_meta(row)
    for namespace in ("rotterdam_history", "rotterdam_company_depth"):
        annotation=meta.get(namespace) or {}
        if isinstance(annotation,dict):
            evidence=annotation.get("evidence") or {}
            if isinstance(evidence,dict): add(evidence.get("url"))
    for key in (
        "source_url","url","article_url","reference_url","original_url",
        "publication_url","document_url","evidence_url","source_link"
    ):
        add(meta.get(key))

    # Common structured source containers used by the loader/research pipeline.
    for container_key in ("research_sources","sources","source_urls","evidence","references"):
        value=meta.get(container_key)
        if value in (None,"",[],{}):
            value=row.get(container_key)
        if isinstance(value,str):
            add(value)
        elif isinstance(value,list):
            for item in value:
                if isinstance(item,str):
                    add(item)
                elif isinstance(item,dict):
                    for key in ("url","source_url","article_url","reference_url","evidence_url","link"):
                        add(item.get(key))
        elif isinstance(value,dict):
            for item in value.values():
                if isinstance(item,str):
                    add(item)
                elif isinstance(item,dict):
                    for key in ("url","source_url","article_url","reference_url","evidence_url","link"):
                        add(item.get(key))

    return urls


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
                region_label=_display_location(r) or _event_region_label(r)
                st.caption(f"{d} · {r['_brief_kind']} · {region_label}")
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
    st.session_state[f"pc_terminal_nav_{lens}"]=(
        "Home" if lens=="trade" else
        "Operating Picture" if lens=="intelligence" else
        "Exposure Picture" if lens=="sanctions" else
        "Industrial Picture"
    )

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


def _terminal_self_check() -> list[str]:
    missing=[]
    for name in ("_context_record","_entity_identity_bundle","_event_source_urls"):
        if name not in globals():
            missing.append(name)
    return missing


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




def _display_location(row: dict) -> str:
    for k in ("region_city", "hq_city", "location", "country", "hq_country", "flag"):
        v = row.get(k)
        if isinstance(v, dict):
            v = v.get("name") or v.get("country") or v.get("region")
        if v:
            return _clean(v)
    return ""

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
    """Read canonical edges first; supplement them with specialist index links."""
    ids=_entity_identity_bundle(str(oid)).get("ids") if typ=="entity" else [str(oid)]
    ids={str(x) for x in (ids or [str(oid)])}
    out=[]
    canonical_ids=set()
    for side in ("source", "target"):
        for identity_id in sorted(ids):
            for r in _filtered_rows("pc_relationships", f"{side}_id", identity_id, 1000):
                if _clean(r.get(f"{side}_type")).casefold()!=typ:
                    continue
                out.append(r)
                canonical_ids.add(_clean(r.get("relationship_id")))
    for identity_id in sorted(ids):
        for r in _indexed_links(typ,identity_id,1000):
            # Generic indexed edges are copies of canonical rows. Keep the live
            # version, including its current endpoints and relationship name.
            if (_clean(r.get("source_table"))=="pc_relationships"
                    and _clean(r.get("source_record_id")) in canonical_ids):
                continue
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
    seen=set(); final=[]
    for r in out:
        key=(_clean(r.get("source_type")).casefold(),_clean(r.get("source_id")),
             _clean(r.get("relationship_type")).casefold(),
             _clean(r.get("target_type")).casefold(),_clean(r.get("target_id")))
        if key in seen:
            continue
        seen.add(key); final.append(r)
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

def _get_context():
    return st.session_state.get("pc_terminal_type"), st.session_state.get("pc_terminal_id")


def _company_profile_rows(entity_id: str) -> list[dict]:
    ids=_entity_identity_bundle(str(entity_id)).get("ids") or [str(entity_id)]
    return _multi_filtered_rows("pc_company_profiles","entity_id",ids,20)


def _company_display_value(*values):
    for v in values:
        if v not in (None,"",[],{}):
            return _clean(v)
    return ""


def _render_company_relationship_cards(rows: list[dict], key_prefix: str, limit: int=12):
    if not rows:
        st.caption("No linked corporate relationships recorded.")
        return
    for i,x in enumerate(rows[:limit]):
        cols=st.columns([3.2,1.4,1.0])
        cols[0].markdown(f"**{x.get('name') or 'Unnamed company'}**")
        cols[1].caption((_clean(x.get("relationship")) or "linked company").replace("_"," ").title())
        cols[2].button(
            "Open",
            key=f"{key_prefix}_{i}_{x.get('id')}",
            use_container_width=True,
            on_click=_set_context,
            args=("entity",x.get("id"),x.get("name") or ""),
        )
        st.markdown("<div style='height:1px;background:var(--line);margin:.12rem 0 .45rem'></div>",unsafe_allow_html=True)


def _render_company_asset_cards(rows: list[dict], key_prefix: str, limit: int=12):
    if not rows:
        st.caption("No linked operating assets recorded.")
        return
    for i,x in enumerate(rows[:limit]):
        cols=st.columns([3.0,1.4,1.0])
        cols[0].markdown(f"**{x.get('name') or 'Unnamed asset'}**")
        cols[1].caption((_clean(x.get("relationship")) or x.get("type") or "asset").replace("_"," ").title())
        cols[2].button(
            "Open",
            key=f"{key_prefix}_{i}_{x.get('id')}",
            use_container_width=True,
            on_click=_set_context,
            args=(x.get("type") or "asset",x.get("id"),x.get("name") or ""),
        )
        st.markdown("<div style='height:1px;background:var(--line);margin:.12rem 0 .45rem'></div>",unsafe_allow_html=True)


def _render_company_transaction_cards(tx: list[dict], limit: int=10):
    if not tx:
        st.caption("No related capital actions recorded.")
        return
    for r in tx[:limit]:
        d=_company_display_value(r.get("transaction_date"),r.get("effective_date"),r.get("announcement_date"))
        typ=_company_display_value(r.get("transaction_type"),"Capital action").replace("_"," ").title()
        headline=_company_display_value(r.get("title"),r.get("headline"),r.get("target_name"),r.get("description"))
        value=_company_display_value(r.get("deal_value"),r.get("value"),r.get("consideration"))
        currency=_company_display_value(r.get("currency"))
        status=_company_display_value(r.get("status"))
        st.markdown(f"**{headline or typ}**")
        bits=[x for x in [d,typ,(currency+" "+value).strip() if value else "",status] if x]
        if bits:
            st.caption(" · ".join(bits))
        desc=_clean(r.get("description"))
        if desc and desc!=headline:
            st.write(desc[:500])
        st.markdown("<div style='height:1px;background:var(--line);margin:.15rem 0 .5rem'></div>",unsafe_allow_html=True)


def _strategic_company_bundle(oid: str, name: str) -> dict:
    """Resolve strategic-industry depth from canonical relationships first."""
    graph=_entity_graph_neighborhood(str(oid),depth=2)
    nodes=graph.get("nodes") or []
    edges=graph.get("edges") or []

    by_type={}
    for n in nodes:
        by_type.setdefault(n.get("type"),[]).append(n)

    programme_ids={n["id"] for n in by_type.get("programme",[]) if n.get("id")}
    shipyard_ids=set()
    asset_nodes=[]

    for n in by_type.get("asset",[]):
        rec=object_record("asset",n["id"]) or {}
        blob=" ".join([
            _clean(rec.get("name")),_clean(rec.get("asset_type")),
            _clean(rec.get("subtype")),_clean(rec.get("description"))
        ]).casefold()
        asset_nodes.append({
            "type":"asset",
            "id":n["id"],
            "name":_clean(rec.get("name")) or n.get("name") or n["id"],
            "relationship":"linked industrial asset",
        })
        if any(t in blob for t in ("shipyard","shipbuilding","yard","dockyard")):
            shipyard_ids.add(n["id"])

    rel_for={}
    for e in edges:
        rel=_clean(e.get("relationship")).replace("_"," ")
        rel_for.setdefault((e.get("source_type"),e.get("source_id")),rel)
        rel_for.setdefault((e.get("target_type"),e.get("target_id")),rel)
    for a in asset_nodes:
        a["relationship"]=rel_for.get(("asset",a["id"])) or "linked industrial asset"

    def dedupe(rows):
        out=[]; seen=set()
        for r in rows:
            k=json.dumps(r,sort_keys=True,default=str)
            if k not in seen:
                seen.add(k); out.append(r)
        return out

    def rows_by_ids(table, pk, ids):
        out=[]
        for rid in ids:
            try:
                out.extend(_filtered_rows(table,pk,rid,10))
            except Exception:
                pass
        return dedupe(out)

    programmes=rows_by_ids("pc_defence_programmes","defence_programme_id",programme_ids)

    participants=[]
    production=[]
    capacity=[]
    for pid in programme_ids:
        try:
            participants.extend(_filtered_rows("pc_defence_programme_participants","defence_programme_id",pid,200))
        except Exception:
            pass
        try:
            production.extend(_filtered_rows("pc_shipbuilding_production_tasks","defence_programme_id",pid,400))
        except Exception:
            pass

    for aid in shipyard_ids:
        try:
            participants.extend(_filtered_rows("pc_defence_programme_participants","shipyard_asset_id",aid,200))
        except Exception:
            pass
        try:
            production.extend(_filtered_rows("pc_shipbuilding_production_tasks","shipyard_asset_id",aid,400))
        except Exception:
            pass
        try:
            capacity.extend(_filtered_rows("pc_shipyard_capacity_history","shipyard_asset_id",aid,300))
        except Exception:
            pass

    orders=[]
    contracts=[]
    operations=[]
    operation_participants=[]
    docs=[]
    events=[]

    for e in edges:
        for typ2,id2 in (
            (e.get("source_type"),e.get("source_id")),
            (e.get("target_type"),e.get("target_id")),
        ):
            if typ2=="event" and id2:
                ev=object_record("event",id2)
                if ev:
                    events.append(ev)
            elif typ2=="document" and id2:
                try:
                    docs.extend(_filtered_rows("pc_documents","document_id",id2,2))
                except Exception:
                    pass
            elif typ2=="security_operation" and id2:
                try:
                    operations.extend(_filtered_rows("pc_security_operations","security_operation_id",id2,2))
                except Exception:
                    pass

        stbl=_clean(e.get("source_table"))
        srid=_clean(e.get("source_record_id"))

        if stbl=="pc_shipbuilding_orders" and srid:
            for pk in ("shipbuilding_order_id","order_id","id"):
                try:
                    rr=_filtered_rows(stbl,pk,srid,2)
                    if rr:
                        orders.extend(rr)
                        break
                except Exception:
                    pass

        if stbl=="pc_contracts" and srid:
            for pk in ("contract_id","id"):
                try:
                    rr=_filtered_rows(stbl,pk,srid,2)
                    if rr:
                        contracts.extend(rr)
                        break
                except Exception:
                    pass

        if stbl=="pc_security_operation_participants" and srid:
            for pk in ("security_operation_participant_id","id"):
                try:
                    rr=_filtered_rows(stbl,pk,srid,2)
                    if rr:
                        operation_participants.extend(rr)
                        break
                except Exception:
                    pass

    ids=_entity_identity_bundle(str(oid)).get("ids") or [str(oid)]
    for eid in ids:
        for table,col,target in (
            ("pc_defence_programmes","lead_contractor_entity_id",programmes),
            ("pc_defence_programme_participants","entity_id",participants),
            ("pc_shipbuilding_production_tasks","builder_entity_id",production),
            ("pc_shipyard_capacity_history","operator_entity_id",capacity),
            ("pc_security_operations","lead_entity_id",operations),
            ("pc_security_operation_participants","entity_id",operation_participants),
        ):
            try:
                target.extend(_filtered_rows(table,col,eid,500))
            except Exception:
                pass

    for r in participants+production+capacity:
        aid=_clean(r.get("shipyard_asset_id"))
        if not aid or aid in {x["id"] for x in asset_nodes}:
            continue
        arec=object_record("asset",aid) or {}
        asset_nodes.append({
            "type":"asset",
            "id":aid,
            "name":_clean(arec.get("name")) or _asset_chip(aid),
            "relationship":_clean(r.get("participant_role") or r.get("task_type") or "shipyard"),
        })

    return {
        "programmes":dedupe(programmes),
        "participants":dedupe(participants),
        "production":dedupe(production),
        "capacity":dedupe(capacity),
        "orders":dedupe(orders),
        "contracts":dedupe(contracts),
        "projects":[],
        "operations":dedupe(operations),
        "operation_participants":dedupe(operation_participants),
        "shipyards":asset_nodes,
        "events":dedupe(events),
        "documents":dedupe(docs),
        "graph":graph,
    }


def _render_strategic_company_activity(data: dict, oid: str):
    programmes=data.get("programmes") or []
    production=data.get("production") or []
    orders=data.get("orders") or []
    contracts=data.get("contracts") or []
    capacity=data.get("capacity") or []
    operations=data.get("operations") or []

    if not any((programmes,production,orders,contracts,capacity,operations)):
        return

    st.markdown("### Strategic Industrial Activity")
    st.caption("Defence, coast-guard, shipbuilding, production and industrial-capacity records tied to this company.")

    a,b=st.columns([1.1,1.0],gap="large")
    with a:
        with st.container(border=True):
            st.markdown("#### Programmes & Contracts")
            if programmes:
                for i,r in enumerate(programmes[:15]):
                    title=_company_display_value(r.get("programme_name"),"Unnamed programme")
                    ptype=_company_display_value(r.get("programme_type"))
                    status=_company_display_value(r.get("programme_status"),r.get("verification_status"))
                    qty=[]
                    if r.get("firm_quantity") not in (None,""): qty.append(f"{r.get('firm_quantity')} firm")
                    if r.get("option_quantity") not in (None,""): qty.append(f"{r.get('option_quantity')} options")
                    value=""
                    if r.get("announced_value") not in (None,""):
                        value=(str(r.get("currency") or "")+" "+str(r.get("announced_value"))).strip()
                    st.markdown(f"**{title}**")
                    st.caption(" · ".join(x for x in [ptype.replace("_"," ").title() if ptype else "",status,", ".join(qty),value] if x))
                    st.markdown("<div style='height:1px;background:var(--line);margin:.12rem 0 .45rem'></div>",unsafe_allow_html=True)
            elif contracts:
                for r in contracts[:12]:
                    title=_company_display_value(r.get("contract_name"),r.get("title"),r.get("description"),"Contract")
                    st.markdown(f"**{title}**")
                    st.caption(" · ".join(x for x in [_clean(r.get("status")),_clean(r.get("signed_date"))] if x))
            else:
                st.caption("No programme or contract records resolved.")

    with b:
        with st.container(border=True):
            st.markdown("#### Production & Capacity")
            if production:
                for r in production[:15]:
                    task=_company_display_value(r.get("task_type"),"production task").replace("_"," ").title()
                    yard=_asset_chip(_clean(r.get("shipyard_asset_id"))) if r.get("shipyard_asset_id") else ""
                    status=_company_display_value(r.get("task_status"))
                    dates=" → ".join(x for x in [
                        _clean(r.get("planned_start") or r.get("actual_start")),
                        _clean(r.get("planned_finish") or r.get("actual_finish"))
                    ] if x)
                    st.markdown(f"**{task}**")
                    st.caption(" · ".join(x for x in [yard,status,dates] if x))
                    st.markdown("<div style='height:1px;background:var(--line);margin:.12rem 0 .45rem'></div>",unsafe_allow_html=True)
            if capacity:
                with st.expander(f"Capacity observations ({len(capacity)})",expanded=not bool(production)):
                    for r in capacity[:20]:
                        metric=_company_display_value(r.get("metric_name"),"Capacity")
                        value=" ".join(x for x in [str(r.get("metric_value") or ""),_clean(r.get("metric_unit"))] if x).strip()
                        yard=_asset_chip(_clean(r.get("shipyard_asset_id"))) if r.get("shipyard_asset_id") else ""
                        st.markdown(f"**{metric}**")
                        st.caption(" · ".join(x for x in [yard,value,_clean(r.get("observed_date"))] if x))
            if not production and not capacity:
                st.caption("No production or capacity records resolved.")

    if orders:
        with st.container(border=True):
            st.markdown("#### Shipbuilding Orders / Industrial Pipeline")
            for r in orders[:15]:
                title=_company_display_value(
                    r.get("order_name"),r.get("programme_name"),r.get("vessel_class"),
                    r.get("description"),r.get("shipbuilding_order_id"),"Shipbuilding order"
                )
                status=_company_display_value(r.get("status"),r.get("order_status"))
                qty=_company_display_value(r.get("quantity"),r.get("firm_quantity"))
                delivery=_company_display_value(r.get("delivery_date"),r.get("expected_delivery"),r.get("delivery_year"))
                st.markdown(f"**{title}**")
                st.caption(" · ".join(x for x in [status,("Qty "+qty) if qty else "",delivery] if x))

    if operations:
        with st.container(border=True):
            st.markdown("#### Security / Operational Activity")
            for r in operations[:12]:
                title=_company_display_value(r.get("operation_name"),"Operation")
                typ=_company_display_value(r.get("operation_type")).replace("_"," ").title()
                status=_company_display_value(r.get("operation_status"))
                st.markdown(f"**{title}**")
                st.caption(" · ".join(x for x in [typ,status] if x))



# ---------------------------------------------------------------------
# Corporate tree / temporal group view
# ---------------------------------------------------------------------

_CORPORATE_TREE_RELATIONSHIPS = {
    "equity_owner",
    "owns_controls",
    "owns",
    "controls",
    "controlled_interest",
    "business_unit_parent",
    "parent_of",
    "parent of",
    "subsidiary",
    "subsidiary_of",
    "subsidiary of",
    "portfolio_company",
    "joint_venture",
}


def _company_relationship_neighborhood(entity_id: str, max_depth: int = 6, max_nodes: int = 250) -> tuple[set[str], list[dict]]:
    """Collect corporate relationships around an entity across time.

    pc_company_relationships is intentionally treated as a temporal edge table:
    we collect both current and historical rows here, then filter for the selected
    year in the renderer. This keeps the view generic for AD Ports, CMA CGM,
    DP World, ADQ, LIMAD and other complex groups.
    """
    root = str(entity_id)
    seen = {root}
    frontier = {root}
    edges: list[dict] = []
    edge_keys = set()

    for _ in range(max_depth):
        if not frontier or len(seen) >= max_nodes:
            break

        found: list[dict] = []
        for eid in tuple(frontier):
            for col in ("parent_company_key", "child_company_key"):
                try:
                    found.extend(_filtered_rows("pc_company_relationships", col, eid, 500))
                except Exception:
                    pass

        nxt = set()
        for r in found:
            parent = _clean(r.get("parent_company_key"))
            child = _clean(r.get("child_company_key"))
            if not parent or not child:
                continue

            key = (
                parent,
                child,
                _clean(r.get("relationship")),
                _clean(r.get("effective_from")),
                _clean(r.get("effective_to")),
                _clean(r.get("value")),
                _clean(r.get("unit")),
            )
            if key not in edge_keys:
                edge_keys.add(key)
                edges.append(r)

            if parent in frontier and child not in seen and len(seen) + len(nxt) < max_nodes:
                nxt.add(child)
            if child in frontier and parent not in seen and len(seen) + len(nxt) < max_nodes:
                nxt.add(parent)

        seen.update(nxt)
        frontier = nxt

    return seen, edges


def _company_relationship_active(row: dict, cutoff: pd.Timestamp) -> bool:
    start = pd.to_datetime(row.get("effective_from"), errors="coerce")
    end = pd.to_datetime(row.get("effective_to"), errors="coerce")
    if pd.notna(start) and start > cutoff:
        return False
    if pd.notna(end) and end < cutoff:
        return False
    return True


def _company_tree_edge_label(row: dict) -> str:
    rel = (_clean(row.get("relationship")) or "linked").replace("_", " ").title()
    value = row.get("value")
    unit = _clean(row.get("unit"))
    stake = ""
    if value not in (None, ""):
        try:
            fv = float(value)
            stake = f"{fv:g}{'%' if unit.casefold() in {'percent','%'} else (' '+unit if unit else '')}"
        except Exception:
            stake = f"{value}{(' '+unit) if unit else ''}"
    bits = [x for x in (rel, stake, _clean(row.get("effective_from"))) if x]
    return " · ".join(bits)


def _company_direct_asset_counts(entity_id: str) -> dict[str, int]:
    """Small, generic per-node footprint summary derived from existing graph data."""
    counts = {
        "vessels": 0,
        "aircraft": 0,
        "ports_terminals": 0,
        "shipyards": 0,
        "rail": 0,
        "warehouses": 0,
        "other_assets": 0,
    }
    mobile_seen, asset_seen = set(), set()

    try:
        roles = _company_asset_roles(entity_id)
    except Exception:
        roles = []

    for r in roles:
        mid = _clean(r.get("mobile_asset_id"))
        aid = _clean(r.get("asset_id"))

        if mid and mid not in mobile_seen:
            mobile_seen.add(mid)
            rec = object_record("mobile_asset", mid) or {}
            blob = " ".join([
                _clean(rec.get("asset_type")),
                _clean(rec.get("subtype")),
                _clean(rec.get("name")),
            ]).casefold()
            if "aircraft" in blob or "plane" in blob or "helicopter" in blob:
                counts["aircraft"] += 1
            else:
                counts["vessels"] += 1

        if aid and aid not in asset_seen:
            asset_seen.add(aid)
            rec = object_record("asset", aid) or {}
            blob = " ".join([
                _clean(rec.get("asset_type")),
                _clean(rec.get("subtype")),
                _clean(rec.get("name")),
            ]).casefold()
            if re.search(r"\bport\b|terminal|container depot|cruise|roro|ro-ro", blob):
                counts["ports_terminals"] += 1
            elif re.search(r"shipyard|dry ?dock|dockyard", blob):
                counts["shipyards"] += 1
            elif re.search(r"rail|intermodal|marshalling|freight line", blob):
                counts["rail"] += 1
            elif re.search(r"warehouse|distribution centre|distribution center|logistics centre|logistics center", blob):
                counts["warehouses"] += 1
            else:
                counts["other_assets"] += 1

    return counts


def _company_group_asset_summary(entity_ids: set[str]) -> dict[str, int]:
    total = {
        "vessels": 0,
        "aircraft": 0,
        "ports_terminals": 0,
        "shipyards": 0,
        "rail": 0,
        "warehouses": 0,
        "other_assets": 0,
    }
    # Avoid double counting shared assets across operating entities.
    mobile_ids, asset_ids = set(), set()

    for eid in entity_ids:
        try:
            roles = _company_asset_roles(eid)
        except Exception:
            roles = []
        for r in roles:
            mid = _clean(r.get("mobile_asset_id"))
            aid = _clean(r.get("asset_id"))
            if mid:
                mobile_ids.add(mid)
            if aid:
                asset_ids.add(aid)

    for mid in mobile_ids:
        rec = object_record("mobile_asset", mid) or {}
        blob = " ".join([
            _clean(rec.get("asset_type")),
            _clean(rec.get("subtype")),
            _clean(rec.get("name")),
        ]).casefold()
        if "aircraft" in blob or "plane" in blob or "helicopter" in blob:
            total["aircraft"] += 1
        else:
            total["vessels"] += 1

    for aid in asset_ids:
        rec = object_record("asset", aid) or {}
        blob = " ".join([
            _clean(rec.get("asset_type")),
            _clean(rec.get("subtype")),
            _clean(rec.get("name")),
        ]).casefold()
        if re.search(r"\bport\b|terminal|container depot|cruise|roro|ro-ro", blob):
            total["ports_terminals"] += 1
        elif re.search(r"shipyard|dry ?dock|dockyard", blob):
            total["shipyards"] += 1
        elif re.search(r"rail|intermodal|marshalling|freight line", blob):
            total["rail"] += 1
        elif re.search(r"warehouse|distribution centre|distribution center|logistics centre|logistics center", blob):
            total["warehouses"] += 1
        else:
            total["other_assets"] += 1

    return total



def _company_network_payload(root_id: str, children: dict[str, list[dict]], include_assets: bool=False, max_nodes: int=90):
    nodes=[]; edges=[]; seen={str(root_id)}; queue=[(str(root_id),0)]; depth_by={str(root_id):0}
    while queue and len(seen)<max_nodes:
        parent,depth=queue.pop(0)
        for edge in children.get(parent,[]):
            child=_clean(edge.get("child_company_key"))
            if not child:
                continue
            edges.append({"source":parent,"target":child,"label":_company_tree_edge_label(edge),"kind":"corporate"})
            if child not in seen and depth<7:
                seen.add(child); depth_by[child]=depth+1; queue.append((child,depth+1))

    for eid in seen:
        erec=object_record("entity",eid) or {}
        direct=_company_direct_asset_counts(eid)
        metrics=[]
        if direct["vessels"]: metrics.append(f"{direct['vessels']} vessels")
        if direct["aircraft"]: metrics.append(f"{direct['aircraft']} aircraft")
        if direct["ports_terminals"]: metrics.append(f"{direct['ports_terminals']} ports/terminals")
        if direct["shipyards"]: metrics.append(f"{direct['shipyards']} shipyards")
        if direct["rail"] or direct["warehouses"]:
            metrics.append(f"{direct['rail']+direct['warehouses']} rail/logistics")
        nodes.append({
            "id":eid,
            "name":_object_name("entity",eid),
            "depth":depth_by.get(eid,0),
            "kind":"company",
            "subtype":_company_display_value(erec.get("subtype"),erec.get("entity_type")),
            "metrics":" · ".join(metrics[:2]),
        })

    if include_assets:
        for eid in list(seen):
            if len(nodes)>=max_nodes: break
            try:
                roles=_company_asset_roles(eid)
            except Exception:
                roles=[]
            for r in roles:
                if len(nodes)>=max_nodes: break
                aid=_clean(r.get("asset_id")); mid=_clean(r.get("mobile_asset_id"))
                obj_type="asset" if aid else ("mobile_asset" if mid else "")
                obj_id=aid or mid
                if not obj_type or not obj_id: continue
                nid=f"{obj_type}:{obj_id}"
                if any(n["id"]==nid for n in nodes): continue
                arec=object_record(obj_type,obj_id) or {}
                nodes.append({
                    "id":nid,
                    "name":_object_name(obj_type,obj_id),
                    "depth":depth_by.get(eid,0)+1,
                    "kind":"asset",
                    "subtype":_company_display_value(arec.get("subtype"),arec.get("asset_type")),
                    "metrics":"",
                })
                edges.append({
                    "source":eid,
                    "target":nid,
                    "label":(_clean(r.get("asset_role")) or "linked asset").replace("_"," ").title(),
                    "kind":"asset",
                })
    return nodes,edges

def _render_company_tree_view(oid: str, rec: dict, tx: list[dict] | None = None):
    all_nodes, all_edges = _company_relationship_neighborhood(oid)

    if not all_edges:
        st.info("No temporal corporate relationships are currently recorded for this entity.")
        return

    years = []
    for r in all_edges:
        for k in ("effective_from", "effective_to"):
            d = pd.to_datetime(r.get(k), errors="coerce")
            if pd.notna(d):
                years.append(int(d.year))

    now = pd.Timestamp.now()
    current_year = int(now.year)
    min_year = min(years) if years else current_year
    min_year = max(1980, min_year)
    max_year = max([current_year] + years) if years else current_year

    st.markdown("### Corporate Tree")
    st.caption(
        "Ownership, control, business units and portfolio relationships reconstructed from temporal corporate edges. "
        "Change the year to see how the group evolved."
    )

    control_left, control_right = st.columns([2.0, 1.0], gap="large")
    with control_left:
        year = st.slider(
            "Structure as of year",
            min_value=min_year,
            max_value=max_year,
            value=current_year,
            step=1,
            key=f"company_tree_year_{_norm(oid)}",
        )
    with control_right:
        st.metric("Known corporate nodes", max(1, len(all_nodes)))

    cutoff = now if year == current_year else pd.Timestamp(year=year, month=12, day=31)

    active_edges = [r for r in all_edges if _company_relationship_active(r, cutoff)]

    # Hierarchy edges are kept separate from operational affiliations so the
    # corporate tree remains an ownership/control view rather than a hairball.
    hierarchy_edges = []
    affiliation_edges = []
    for r in active_edges:
        rel = (_clean(r.get("relationship")) or "").casefold()
        rel_norm = rel.replace("_", " ")
        accepted = rel in _CORPORATE_TREE_RELATIONSHIPS or rel_norm in {
            x.replace("_", " ") for x in _CORPORATE_TREE_RELATIONSHIPS
        }
        if accepted:
            hierarchy_edges.append(r)
        else:
            affiliation_edges.append(r)

    # Build descendants from the selected company. If this entity is a lower
    # level operating company, also retain its immediate parent context.
    children: dict[str, list[dict]] = {}
    parents: dict[str, list[dict]] = {}
    for r in hierarchy_edges:
        p = _clean(r.get("parent_company_key"))
        c = _clean(r.get("child_company_key"))
        if not p or not c:
            continue
        children.setdefault(p, []).append(r)
        parents.setdefault(c, []).append(r)

    descendant_ids = {str(oid)}
    frontier = {str(oid)}
    for _ in range(8):
        nxt = set()
        for p in frontier:
            for r in children.get(p, []):
                c = _clean(r.get("child_company_key"))
                if c and c not in descendant_ids:
                    nxt.add(c)
        if not nxt:
            break
        descendant_ids.update(nxt)
        frontier = nxt

    summary = _company_group_asset_summary(descendant_ids)
    k = st.columns(6)
    k[0].metric("Companies / JVs", max(0, len(descendant_ids) - 1))
    k[1].metric("Vessels", summary["vessels"])
    k[2].metric("Aircraft", summary["aircraft"])
    k[3].metric("Ports / terminals", summary["ports_terminals"])
    k[4].metric("Shipyards", summary["shipyards"])
    k[5].metric("Rail / logistics", summary["rail"] + summary["warehouses"])

    # Parent context for lower-level entities.
    root_parents = parents.get(str(oid), [])
    if root_parents:
        with st.container(border=True):
            st.markdown("#### Parent / ownership context")
            for i, r in enumerate(root_parents[:8]):
                pid = _clean(r.get("parent_company_key"))
                pname = _object_name("entity", pid)
                cols = st.columns([3.5, 2.2, 1.0])
                cols[0].markdown(f"**{pname}**")
                cols[1].caption(_company_tree_edge_label(r))
                cols[2].button(
                    "Open",
                    key=f"tree_parent_{_norm(oid)}_{i}_{_norm(pid)}",
                    use_container_width=True,
                    on_click=_set_context,
                    args=("entity", pid, pname),
                )

    hierarchy_tab, network_tab = st.tabs(["Hierarchy", "Network"])

    with hierarchy_tab:
        with st.container(border=True):
            st.markdown(f"#### Structure in {year}")

            def render_node(eid: str, depth: int, visited: set[str]):
                if eid in visited or depth > 8:
                    return
                visited = set(visited)
                visited.add(eid)

                name = _object_name("entity", eid)
                erec = object_record("entity", eid) or {}
                subtype = _company_display_value(erec.get("subtype"), erec.get("entity_type"))
                direct = _company_direct_asset_counts(eid)
                bits = []
                if direct["vessels"]:
                    bits.append(f"{direct['vessels']} vessels")
                if direct["aircraft"]:
                    bits.append(f"{direct['aircraft']} aircraft")
                if direct["ports_terminals"]:
                    bits.append(f"{direct['ports_terminals']} ports/terminals")
                if direct["shipyards"]:
                    bits.append(f"{direct['shipyards']} shipyards")
                if direct["rail"] or direct["warehouses"]:
                    bits.append(f"{direct['rail'] + direct['warehouses']} rail/logistics assets")

                if depth == 0:
                    edge_text = "Selected company"
                else:
                    edge_text = ""

                row = st.columns([0.16 * depth + 0.02, 4.8, 1.05])
                row[0].markdown("")
                with row[1]:
                    st.markdown(f"**{name}**")
                    meta = " · ".join(x for x in [subtype, edge_text, ", ".join(bits)] if x)
                    if meta:
                        st.caption(meta)
                if eid != str(oid):
                    row[2].button(
                        "Open",
                        key=f"tree_open_{_norm(oid)}_{depth}_{_norm(eid)}",
                        use_container_width=True,
                        on_click=_set_context,
                        args=("entity", eid, name),
                    )

                for j, edge in enumerate(sorted(
                    children.get(eid, []),
                    key=lambda x: (_clean(x.get("child_company_key")), _clean(x.get("relationship")))
                )):
                    child = _clean(edge.get("child_company_key"))
                    if not child or child in visited:
                        continue
                    indent = st.columns([0.16 * (depth + 1) + 0.02, 4.8, 1.05])
                    indent[0].markdown("")
                    indent[1].caption("↳ " + _company_tree_edge_label(edge))
                    render_node(child, depth + 1, visited)

            render_node(str(oid), 0, set())


    with network_tab:
        network_mode = st.radio(
            "Network detail",
            ["Companies only", "Companies + assets"],
            horizontal=True,
            key=f"company_network_mode_{_norm(oid)}",
        )
        st.caption("Visual view of the same year-filtered corporate graph.")
        network_nodes, network_edges = _company_network_payload(
            str(oid), children,
            include_assets=(network_mode == "Companies + assets"),
            max_nodes=90,
        )
        render_network(
            network_nodes,
            network_edges,
            root_id=str(oid),
            key_prefix=f"corp_network_{_norm(oid)}",
            open_callback=_set_context,
            include_assets=(network_mode == "Companies + assets"),
        )

    if affiliation_edges:
        with st.expander(f"Operational / affiliated relationships ({len(affiliation_edges)})"):
            for i, r in enumerate(affiliation_edges[:40]):
                p = _clean(r.get("parent_company_key"))
                c = _clean(r.get("child_company_key"))
                st.markdown(f"**{_object_name('entity', p)} → {_object_name('entity', c)}**")
                st.caption(_company_tree_edge_label(r))
                url = _clean(r.get("source_url"))
                if url:
                    st.link_button("Source", url, key=f"tree_aff_src_{_norm(oid)}_{i}")

    # Temporal change log / acquisition timeline.
    timeline = sorted(
        [r for r in all_edges if _clean(r.get("effective_from"))],
        key=lambda x: _clean(x.get("effective_from")),
        reverse=True,
    )
    st.markdown("### Acquisition & Structure Timeline")
    st.caption("Dated ownership changes, acquisitions, restructurings and other recorded corporate changes.")
    if timeline:
        for i, r in enumerate(timeline[:40]):
            parent = _object_name("entity", _clean(r.get("parent_company_key")))
            child = _object_name("entity", _clean(r.get("child_company_key")))
            st.markdown(f"**{_clean(r.get('effective_from'))} · {parent} → {child}**")
            st.caption(_company_tree_edge_label(r))
            notes = _clean(r.get("notes"))
            if notes:
                st.write(notes[:420])
            url = _clean(r.get("source_url"))
            if url:
                st.link_button("Source", url, key=f"tree_timeline_src_{_norm(oid)}_{i}")
            st.markdown("<div style='height:1px;background:var(--line);margin:.12rem 0 .5rem'></div>", unsafe_allow_html=True)
    else:
        st.caption("No dated corporate changes recorded yet.")


def _render_company_terminal(oid: str, rec: dict, lens: str):
    name=_object_name("entity",oid)
    bundle=_entity_identity_bundle(str(oid))
    ids=bundle.get("ids") or [str(oid)]
    profiles=_company_profile_rows(oid)
    p=profiles[0] if profiles else {}

    rels=_linked_objects_from_relationships("entity",oid)
    corporate=[x for x in rels if x.get("type")=="entity"]
    roles=_company_asset_roles(oid)
    assets=[]
    for r in roles:
        aid=_clean(r.get("asset_id"))
        mid=_clean(r.get("mobile_asset_id"))
        if aid:
            assets.append({"type":"asset","id":aid,"name":_asset_chip(aid),"relationship":_clean(r.get("asset_role"))})
        elif mid:
            assets.append({"type":"mobile_asset","id":mid,"name":_object_name("mobile_asset",mid),"relationship":_clean(r.get("asset_role"))})

    corridors=_company_corridors(oid)
    portfolio=_portfolio(oid)
    tx=_related_table("pc_transactions",oid,name,150)
    events=_events_for_object("entity",oid)
    strategic_data=_strategic_company_bundle(oid,name)
    strategic_events=strategic_data.get("events") or []
    seen_event_ids={_clean(x.get("event_id")) for x in events if x.get("event_id")}
    for e in strategic_events:
        eid=_clean(e.get("event_id"))
        if eid and eid not in seen_event_ids:
            events.append(e); seen_event_ids.add(eid)
    events=sorted(events,key=lambda x:_clean(x.get("start_date")),reverse=True)
    strategic_assets=strategic_data.get("shipyards") or []
    existing_asset_ids={x.get("id") for x in assets}
    for x in strategic_assets:
        if x.get("id") not in existing_asset_ids:
            assets.append(x)
            existing_asset_ids.add(x.get("id"))
    docs=_documents_for_entity(oid)
    graph_docs=strategic_data.get("documents") or []
    seen_doc_ids={_clean(x.get("document_id")) for x in docs if x.get("document_id")}
    for d in graph_docs:
        did=_clean(d.get("document_id"))
        if did and did not in seen_doc_ids:
            docs.append(d)
            seen_doc_ids.add(did)

    sector=_company_display_value(p.get("sector"),rec.get("sector"),rec.get("entity_type"))
    hq=_company_display_value(rec.get("hq_city"),rec.get("region_city"))
    country=_company_display_value(rec.get("hq_country"),rec.get("country"))
    location=", ".join(x for x in [hq,country] if x)
    website=_company_display_value(p.get("website_url"),rec.get("website_url"))
    description=_company_display_value(p.get("business_description"),rec.get("description"),rec.get("business_description"))

    # Company-level navigation. Corporate Tree is a graph view of the same
    # canonical records, not a separate dataset.
    company_view = st.radio(
        "Company view",
        ["Overview", "Corporate Tree"],
        horizontal=True,
        label_visibility="collapsed",
        key=f"company_view_{_norm(oid)}",
    )
    if company_view == "Corporate Tree":
        _render_company_tree_view(oid, rec, tx)
        return

    # Executive company strip.
    m=st.columns(6)
    m[0].metric("Linked companies",len(corporate))
    m[1].metric("Operating assets",len(assets))
    m[2].metric("Corridors",len(corridors))
    if any(strategic_data.get(k) for k in ("programmes","production","orders")):
        m[3].metric("Programmes / orders",len(strategic_data.get("programmes") or [])+len(strategic_data.get("orders") or []))
        m[4].metric("Production tasks",len(strategic_data.get("production") or []))
    else:
        m[3].metric("Portfolio positions",len(portfolio))
        m[4].metric("Capital actions",len(tx))
    m[5].metric("Developments",len(events))

    top_left,top_right=st.columns([1.55,1.0],gap="large")
    with top_left:
        with st.container(border=True):
            st.markdown("### Company Profile")
            if description:
                st.write(description)
            facts=[]
            if sector: facts.append(("Sector / role",sector))
            if location: facts.append(("Headquarters",location))
            products=_company_display_value(p.get("products_services"))
            countries=_company_display_value(p.get("operating_countries"))
            if products: facts.append(("Products / services",products))
            if countries: facts.append(("Operating countries",countries))
            if website: facts.append(("Website",website))
            if facts:
                for label,value in facts:
                    st.markdown(f"<div class='pc-row'><span class='pc-row-label'>{label}</span><span class='pc-row-meta' style='white-space:normal;text-align:right'>{value}</span></div>",unsafe_allow_html=True)
            if len(ids)>1:
                st.caption(f"{len(ids)} canonical/legacy identity records are consolidated into this dossier.")
    with top_right:
        with st.container(border=True):
            st.markdown("### Current Intelligence")
            if events:
                _render_event_rows(events,"company_current_"+_norm(oid),5)
            else:
                st.caption("No linked developments recorded yet.")

    left,right=st.columns([1.0,1.35],gap="large")
    with left:
        with st.container(border=True):
            st.markdown("### Corporate Network")
            st.caption("Ownership, subsidiaries, counterparties and affiliated companies.")
            _render_company_relationship_cards(corporate,f"company_network_{_norm(oid)}",12)
            if len(corporate)>12:
                with st.expander(f"Show {len(corporate)-12} more relationships"):
                    _render_company_relationship_cards(corporate[12:],f"company_network_more_{_norm(oid)}",30)

        with st.container(border=True):
            st.markdown("### Capital & Portfolio")
            if portfolio:
                for i,r in enumerate(portfolio[:10]):
                    investee=_entity_chip(_clean(r.get("investee_entity_id"))) or _asset_chip(_clean(r.get("investee_asset_id")))
                    stake=_company_display_value(r.get("ownership_pct"),r.get("stake_pct"),r.get("position_type"),r.get("role"))
                    status=_company_display_value(r.get("status"))
                    effective=_company_display_value(r.get("effective_date"),r.get("valid_from"))
                    st.markdown(f"**{investee or 'Portfolio position'}**")
                    st.caption(" · ".join(x for x in [stake,status,effective] if x))
                    st.markdown("<div style='height:1px;background:var(--line);margin:.12rem 0 .4rem'></div>",unsafe_allow_html=True)
            else:
                st.caption("No structured portfolio positions recorded.")
    with right:
        with st.container(border=True):
            st.markdown("### Operating Footprint")
            mapped=[]
            for n in assets:
                if n.get("type")=="asset":
                    pnt=_asset_point(n.get("id"))
                    if pnt: mapped.append(pnt)
            if mapped:
                st.map(pd.DataFrame(mapped),latitude="lat",longitude="lon",size=44,zoom=None,use_container_width=True)
            _render_company_asset_cards(assets,f"company_assets_{_norm(oid)}",10)

        if corridors:
            with st.container(border=True):
                st.markdown("### Corridor Exposure")
                for i,r in enumerate(corridors[:10]):
                    ck=_clean(r.get("corridor_key"))
                    nm=_object_name("corridor",ck)
                    role=_clean(r.get("corridor_role")).replace("_"," ").title()
                    cols=st.columns([3.3,1.3,1.0])
                    cols[0].markdown(f"**{nm}**")
                    cols[1].caption(role or "Connected")
                    cols[2].button("→",key=f"company_corr_{_norm(oid)}_{i}",use_container_width=True,
                                   on_click=_set_context,args=("corridor",ck,nm))

    _render_strategic_company_activity(strategic_data,oid)

    low_left,low_right=st.columns([1.0,1.15],gap="large")
    with low_left:
        with st.container(border=True):
            st.markdown("### Capital Actions & Transactions")
            _render_company_transaction_cards(tx,10)
            if len(tx)>10:
                with st.expander(f"Show {len(tx)-10} more capital actions"):
                    _render_company_transaction_cards(tx[10:],30)
    with low_right:
        with st.container(border=True):
            st.markdown("### Evidence & Documents")
            st.caption("Primary sources, filings, documents and supporting evidence.")
            shown=0
            for d in docs[:12]:
                title=_clean(d.get("title")) or "Untitled document"
                source=_company_display_value(d.get("source_name"),d.get("document_type"),d.get("_relationship"))
                st.markdown(f"**{title}**")
                if source: st.caption(source)
                urls=_event_source_urls(d)
                if urls:
                    st.link_button("Open source",urls[0],key=f"company_doc_link_{_norm(oid)}_{shown}")
                shown+=1
                st.markdown("<div style='height:1px;background:var(--line);margin:.12rem 0 .4rem'></div>",unsafe_allow_html=True)
            if not docs:
                st.caption("No linked documents recorded yet.")

    st.markdown("### Company Development Timeline")
    st.caption("Announcements, acquisitions, projects, operational changes and intelligence linked to this company.")
    if events:
        _render_event_rows(events,"company_timeline_"+_norm(oid),15)
    else:
        st.caption("No linked chronological developments yet.")

    with st.expander("Structured data / developer view"):
        st.caption("Secondary diagnostic view. The company dossier above is the primary analyst interface.")
        tabs=st.tabs(["Canonical record","Relationships","Assets","Transactions"])
        with tabs[0]:
            st.json(rec)
        with tabs[1]:
            if corporate:
                st.dataframe(pd.DataFrame([{"Company":x["name"],"Relationship":x["relationship"]} for x in corporate]),hide_index=True,use_container_width=True)
        with tabs[2]:
            if assets:
                st.dataframe(pd.DataFrame([{"Asset":x["name"],"Role":x["relationship"]} for x in assets]),hide_index=True,use_container_width=True)
        with tabs[3]:
            if tx:
                st.dataframe(pd.DataFrame(tx),hide_index=True,use_container_width=True)


def _is_port_operator_entity(rec: dict) -> bool:
    blob=" ".join([
        _clean(rec.get("entity_type")),_clean(rec.get("sector")),_clean(rec.get("subtype")),
        _clean(rec.get("name")),_clean(rec.get("description")),
        _clean((_meta(rec) or {}).get("business_segments")),
    ]).casefold()
    commercial=(
        "port operator","terminal operator","terminal concession","concessionaire",
        "ports group","port services","stevedoring","marine terminal",
        "gateway terminal","inland terminal operator"
    )
    institutional=(
        "port authority","maritime authority","transport authority","ministry",
        "administration","agency","regulator","commission"
    )
    return any(t in blob for t in commercial) and not any(t in blob for t in institutional)


def _mobile_identity_facts(rec: dict) -> list[tuple[str,str]]:
    fields=[
        ("Asset class",_company_display_value(rec.get("asset_type"),rec.get("subtype"))),
        ("IMO",rec.get("imo")),("MMSI",rec.get("mmsi")),
        ("Call sign / registration",_company_display_value(rec.get("call_sign"),rec.get("call_sign_or_registration"),rec.get("registration"))),
        ("Flag",rec.get("flag")),("Build year",_company_display_value(rec.get("build_year"),rec.get("year_built"))),
        ("Builder / shipyard",_company_display_value(rec.get("builder"),rec.get("shipyard"))),
        ("DWT",rec.get("dwt")),("GT",_company_display_value(rec.get("gross_tonnage"),rec.get("gt"))),
        ("TEU",_company_display_value(rec.get("teu_capacity"),rec.get("teu"))),
        ("Length",_company_display_value(rec.get("length_m"),rec.get("length"))),
        ("Beam",_company_display_value(rec.get("beam_m"),rec.get("beam"))),
        ("Status",rec.get("status")),
    ]
    return [(k,_clean(v)) for k,v in fields if v not in (None,"",[],{})]


def _mobile_role_rows(oid: str, rec: dict) -> list[dict]:
    """Resolve all current company roles on a mobile asset, preserving role detail."""
    out=[]; seen=set()

    # Authoritative role table first.
    try:
        rows=_filtered_rows("pc_company_asset_roles","mobile_asset_id",str(oid),500)
    except Exception:
        rows=[]
    for r in rows:
        if r.get("valid_to") not in (None,""):
            continue
        eid=_clean(r.get("entity_id"))
        role=_clean(r.get("asset_role")) or "linked"
        meta=r.get("metadata") if isinstance(r.get("metadata"),dict) else {}
        detail=_clean(meta.get("role_detail"))
        key=(eid,role,detail)
        if eid and key not in seen:
            seen.add(key)
            out.append({
                "entity_id":eid,
                "name":_object_name("entity",eid),
                "role":role,
                "role_detail":detail,
                "as_of":_clean(r.get("as_of")),
                "source_id":_clean(r.get("source_id")),
                "metadata":meta,
            })

    # Summary pointers are useful fallbacks but must not erase detailed roles.
    for col,role in (
        ("owner_entity_id","legal_owner"),
        ("operator_entity_id","operator"),
        ("manager_entity_id","manager"),
    ):
        eid=_clean(rec.get(col))
        key=(eid,role,"")
        if eid and not any(x["entity_id"]==eid and x["role"]==role for x in out):
            out.append({
                "entity_id":eid,
                "name":_object_name("entity",eid),
                "role":role,
                "role_detail":"",
                "as_of":"",
                "source_id":"",
                "metadata":{},
            })
    return out


def _current_parent_edge(entity_id: str) -> dict | None:
    """Return one current ownership/control parent edge for a corporate path."""
    try:
        rows=_filtered_rows("pc_company_relationships","child_company_key",str(entity_id),200)
    except Exception:
        rows=[]
    now=pd.Timestamp.now()
    candidates=[]
    priority={
        "equity_owner":0,"owns_controls":1,"owns":2,"controls":3,
        "controlled_interest":4,"business_unit_parent":5,"parent_of":6,
        "subsidiary":7,"portfolio_company":8,"joint_venture":9,
    }
    for r in rows:
        if not _company_relationship_active(r,now):
            continue
        rel=_clean(r.get("relationship")).casefold()
        rel_norm=rel.replace("_"," ")
        if rel not in _CORPORATE_TREE_RELATIONSHIPS and rel_norm not in {
            x.replace("_"," ") for x in _CORPORATE_TREE_RELATIONSHIPS
        }:
            continue
        candidates.append((priority.get(rel,99),r))
    if not candidates:
        return None
    candidates.sort(key=lambda x:(x[0],_clean(x[1].get("effective_from"))),reverse=False)
    return candidates[0][1]


def _mobile_corporate_path(role_rows: list[dict], max_depth: int=5) -> list[dict]:
    """Build a compact parent -> ... -> direct owner path from the legal owner."""
    owner=None
    for r in role_rows:
        if r.get("role")=="legal_owner":
            owner=r.get("entity_id"); break
    if not owner:
        for r in role_rows:
            if r.get("role")=="owner":
                owner=r.get("entity_id"); break
    if not owner:
        return []

    chain=[{"id":owner,"name":_object_name("entity",owner)}]
    current=owner
    seen={owner}
    for _ in range(max_depth):
        edge=_current_parent_edge(current)
        if not edge:
            break
        parent=_clean(edge.get("parent_company_key"))
        if not parent or parent in seen:
            break
        chain.append({"id":parent,"name":_object_name("entity",parent),"edge":edge})
        seen.add(parent); current=parent
    return list(reversed(chain))


def _mobile_siblings(role_rows: list[dict], oid: str, limit: int=12) -> list[dict]:
    owner=None
    for r in role_rows:
        if r.get("role")=="legal_owner":
            owner=r.get("entity_id"); break
    if not owner:
        return []
    try:
        rows=_filtered_rows("pc_company_asset_roles","entity_id",owner,500)
    except Exception:
        return []
    out=[]; seen=set()
    for r in rows:
        if _clean(r.get("asset_role"))!="legal_owner" or r.get("valid_to") not in (None,""):
            continue
        mid=_clean(r.get("mobile_asset_id"))
        if not mid or mid==str(oid) or mid in seen:
            continue
        seen.add(mid)
        out.append({"id":mid,"name":_object_name("mobile_asset",mid)})
        if len(out)>=limit:
            break
    return out


def _render_mobile_role_stack(role_rows: list[dict], key_prefix: str):
    if not role_rows:
        st.caption("No current ownership / operating roles resolved.")
        return
    role_order={
        "legal_owner":0,"owner":1,"operator":2,"manager":3,"service_provider":4,"other":5
    }
    rows=sorted(role_rows,key=lambda r:(role_order.get(r.get("role"),9),r.get("name","")))
    for i,r in enumerate(rows):
        role=(_clean(r.get("role")) or "linked").replace("_"," ").title()
        detail=(_clean(r.get("role_detail")) or "").replace("_"," ").title()
        cols=st.columns([2.8,2.0,1.0])
        cols[0].markdown(f"**{r.get('name') or r.get('entity_id')}**")
        cols[1].caption(" · ".join(x for x in [role,detail] if x))
        cols[2].button(
            "Open",
            key=f"{key_prefix}_{i}_{_norm(r.get('entity_id'))}",
            use_container_width=True,
            on_click=_set_context,
            args=("entity",r.get("entity_id"),r.get("name") or ""),
        )
        st.markdown("<div style='height:1px;background:var(--line);margin:.12rem 0 .42rem'></div>",unsafe_allow_html=True)


def _render_mobile_asset_terminal(oid: str, rec: dict, lens: str):
    name=_object_name("mobile_asset",oid)
    role_rows=_mobile_role_rows(oid,rec)
    linked=_linked_objects_from_relationships("mobile_asset",oid)
    events=_events_for_object("mobile_asset",oid)
    sanctions=_filtered_rows("pc_sanctions_designations","mobile_asset_id",str(oid),200)
    docs=[]
    try:
        from pc_document_vessels import documents_for_vessel
        for did in documents_for_vessel(_sb(),oid)[:30]:
            rows=_filtered_rows("pc_documents","document_id",str(did),2)
            if rows: docs.append(rows[0])
    except Exception:
        pass
    if not docs:
        docs=_documents_by_name(name,20)

    infra=[x for x in linked if x.get("type")=="asset"]
    corridors=[x for x in linked if x.get("type")=="corridor"]
    corporate_path=_mobile_corporate_path(role_rows)
    siblings=_mobile_siblings(role_rows,oid,12)

    # ------------------------------------------------------------------
    # Executive vessel strip
    # ------------------------------------------------------------------
    subtype=_company_display_value(rec.get("subtype"),rec.get("asset_type")).replace("_"," ").title()
    status=_company_display_value(rec.get("status"),"Unknown")
    st.markdown(f"### {name}")
    headline_bits=[
        f"IMO {_clean(rec.get('imo'))}" if rec.get("imo") else "",
        subtype,
        status.title() if status else "",
    ]
    st.caption(" · ".join(x for x in headline_bits if x))

    top=st.columns(6)
    top[0].metric("IMO",_clean(rec.get("imo")) or "—")
    top[1].metric("Built",_company_display_value(rec.get("year_built"),rec.get("build_year")) or "—")
    top[2].metric("DWT",_clean(rec.get("dwt")) or "—")
    top[3].metric("TEU",_company_display_value(rec.get("capacity_value") if _clean(rec.get("capacity_unit")).casefold()=="teu" else None,rec.get("teu_capacity"),rec.get("teu")) or "—")
    top[4].metric("Flag",_clean(rec.get("flag")) or "—")
    top[5].metric("Events",len(events))

    if corporate_path:
        with st.container(border=True):
            st.markdown("#### Corporate path")
            path_text=" → ".join(x["name"] for x in corporate_path) + f" → {name}"
            st.markdown(f"**{path_text}**")
            st.caption("Current corporate ownership/control path reconstructed from company relationships.")

    tabs=st.tabs([
        "Overview",
        "Ownership & Management",
        "Activity",
        "Routes & Locations",
        "Sanctions",
        "Evidence",
    ])

    # ------------------------------------------------------------------
    # Overview
    # ------------------------------------------------------------------
    with tabs[0]:
        left,right=st.columns([1.0,1.25],gap="large")
        with left:
            with st.container(border=True):
                st.markdown("#### Vessel Identity")
                for label,value in _mobile_identity_facts(rec):
                    st.markdown(
                        f"<div class='pc-row'><span class='pc-row-label'>{label}</span>"
                        f"<span class='pc-row-meta' style='white-space:normal;text-align:right'>{value}</span></div>",
                        unsafe_allow_html=True
                    )
        with right:
            with st.container(border=True):
                st.markdown("#### Current Roles")
                _render_mobile_role_stack(role_rows,f"mobile_roles_overview_{_norm(oid)}")

            if siblings:
                with st.container(border=True):
                    st.markdown("#### Other vessels under the same legal owner")
                    for i,x in enumerate(siblings):
                        cols=st.columns([4.0,1.0])
                        cols[0].markdown(f"**{x['name']}**")
                        cols[1].button(
                            "Open",
                            key=f"mobile_sibling_{_norm(oid)}_{i}",
                            use_container_width=True,
                            on_click=_set_context,
                            args=("mobile_asset",x["id"],x["name"]),
                        )

    # ------------------------------------------------------------------
    # Ownership & management
    # ------------------------------------------------------------------
    with tabs[1]:
        st.markdown("### Ownership, Operation & Management")
        st.caption("Legal owner, operator, commercial/ISM management and other current company roles are kept separately.")
        _render_mobile_role_stack(role_rows,f"mobile_roles_{_norm(oid)}")
        if corporate_path:
            st.markdown("#### Ownership chain")
            for i,x in enumerate(corporate_path):
                cols=st.columns([4.0,1.0])
                cols[0].markdown(f"**{'↳ ' if i else ''}{x['name']}**")
                cols[1].button(
                    "Open",
                    key=f"mobile_path_{_norm(oid)}_{i}",
                    use_container_width=True,
                    on_click=_set_context,
                    args=("entity",x["id"],x["name"]),
                )

    # ------------------------------------------------------------------
    # Activity
    # ------------------------------------------------------------------
    with tabs[2]:
        st.markdown("### Recent Activity & Intelligence")
        _render_event_rows(events,"mobile_events_"+_norm(oid),18)
        st.markdown("### Asset Timeline")
        _render_event_rows(events,"mobile_timeline_"+_norm(oid),30)

    # ------------------------------------------------------------------
    # Routes & locations
    # ------------------------------------------------------------------
    with tabs[3]:
        left,right=st.columns([1.35,1.0],gap="large")
        with left:
            with st.container(border=True):
                st.markdown("#### Operational / Geographic Context")
                points=[]
                xy=_coords_from_record(rec)
                if xy: points.append({"lat":xy[0],"lon":xy[1],"name":name,"type":"mobile asset"})
                for x in infra[:30]:
                    p=_asset_point(x.get("id"))
                    if p: points.append(p)
                if points:
                    st.map(pd.DataFrame(points),latitude="lat",longitude="lon",size=46,zoom=None,use_container_width=True)
                else:
                    st.caption("No current coordinate or linked mapped infrastructure is stored yet. Live AIS/ADS-B can be layered here later.")
        with right:
            with st.container(border=True):
                st.markdown("#### Linked ports / terminals / infrastructure")
                if infra:
                    _render_company_asset_cards(infra,f"mobile_infra_{_norm(oid)}",15)
                else:
                    st.caption("No linked fixed infrastructure recorded yet.")
        if corridors:
            with st.container(border=True):
                st.markdown("#### Corridor / Route Exposure")
                for i,x in enumerate(corridors[:20]):
                    cols=st.columns([3.2,1.4,1.0])
                    cols[0].markdown(f"**{x.get('name')}**")
                    cols[1].caption((_clean(x.get("relationship")) or "connected").replace("_"," ").title())
                    cols[2].button(
                        "Open",
                        key=f"mobile_corr_{_norm(oid)}_{i}",
                        use_container_width=True,
                        on_click=_set_context,
                        args=("corridor",x.get("id"),x.get("name") or ""),
                    )

    # ------------------------------------------------------------------
    # Sanctions
    # ------------------------------------------------------------------
    with tabs[4]:
        st.markdown("### Sanctions / Restrictions")
        if sanctions:
            for s in sanctions[:40]:
                title=_company_display_value(s.get("designated_name"),s.get("subject_name"),s.get("name"),"Designation")
                regime=_company_display_value(s.get("program"),s.get("regime"),s.get("authority"))
                status2=_company_display_value(s.get("status"),s.get("designation_status"))
                st.markdown(f"**{title}**")
                st.caption(" · ".join(x for x in [regime,status2,_clean(s.get("designation_date"))] if x))
        else:
            st.caption("No sanctions/designation records linked to this vessel.")

    # ------------------------------------------------------------------
    # Evidence
    # ------------------------------------------------------------------
    with tabs[5]:
        st.markdown("### Source Evidence")
        if docs:
            for i,d in enumerate(docs[:30]):
                title=_clean(d.get("title")) or "Source document"
                st.markdown(f"**{title}**")
                src=_company_display_value(d.get("source_name"),d.get("publisher"),d.get("document_type"))
                if src: st.caption(src)
                urls=_event_source_urls(d)
                if urls:
                    st.link_button("Open source",urls[0],key=f"mobile_doc_{_norm(oid)}_{i}")
                st.markdown("<div style='height:1px;background:var(--line);margin:.12rem 0 .45rem'></div>",unsafe_allow_html=True)
        else:
            st.caption("No linked source documents recorded yet.")

        with st.expander("Identity history / structured data"):
            history=[]
            for table in ("pc_mobile_asset_name_history","pc_mobile_asset_identity_history","pc_vessel_identifiers"):
                history.extend(_related_table(table,oid,name,100))
            if history:
                st.dataframe(pd.DataFrame(history),hide_index=True,use_container_width=True)
            st.json(rec)

def _render_port_operator_terminal(oid: str, rec: dict, lens: str):
    name=_object_name("entity",oid)
    profiles=_company_profile_rows(oid)
    p=profiles[0] if profiles else {}
    roles=_company_asset_roles(oid)
    footprint=[]
    for r in roles:
        aid=_clean(r.get("asset_id"))
        if not aid: continue
        arec=object_record("asset",aid) or {}
        blob=" ".join([_clean(arec.get("asset_type")),_clean(arec.get("subtype")),_clean(arec.get("name"))]).casefold()
        if any(t in blob for t in ("port","terminal","berth","dry port","container","harbour","harbor","jetty","wharf")):
            footprint.append({
                "type":"asset","id":aid,"name":_asset_chip(aid),
                "relationship":_clean(r.get("asset_role")),
                "country":_clean(arec.get("country")),"region":_clean(arec.get("region_city")),
            })
    corporate=[x for x in _linked_objects_from_relationships("entity",oid) if x.get("type")=="entity"]
    corridors=_company_corridors(oid)
    portfolio=_portfolio(oid)
    tx=_related_table("pc_transactions",oid,name,150)
    events=_events_for_object("entity",oid)
    docs=_documents_for_entity(oid) or _documents_by_name(name,25)
    countries=sorted(set(x.get("country") for x in footprint if x.get("country")))

    # Corporate Tree is available on specialised operator dossiers too.
    # This is essential for diversified groups such as AD Ports and DP World,
    # which are routed through the port-operator renderer rather than the
    # generic company renderer.
    company_view = st.radio(
        "Company view",
        ["Overview", "Corporate Tree"],
        horizontal=True,
        label_visibility="collapsed",
        key=f"company_view_{_norm(oid)}",
    )
    if company_view == "Corporate Tree":
        _render_company_tree_view(oid, rec, tx)
        return

    m=st.columns(6)
    m[0].metric("Ports / terminals",len(footprint))
    m[1].metric("Countries",len(countries))
    m[2].metric("Corridors",len(corridors))
    m[3].metric("Portfolio positions",len(portfolio))
    m[4].metric("Capital actions",len(tx))
    m[5].metric("Developments",len(events))

    left,right=st.columns([1.0,1.45],gap="large")
    with left:
        with st.container(border=True):
            st.markdown("### Operator Profile")
            desc=_company_display_value(p.get("business_description"),rec.get("description"))
            if desc: st.write(desc)
            facts=[
                ("Sector / role",_company_display_value(p.get("sector"),rec.get("sector"),rec.get("entity_type"))),
                ("Headquarters",", ".join(x for x in [_clean(rec.get("hq_city")),_clean(rec.get("hq_country"))] if x)),
                ("Countries in mapped footprint",", ".join(countries[:12])),
                ("Website",_company_display_value(p.get("website_url"),rec.get("website_url"))),
            ]
            for label,value in facts:
                if value:
                    st.markdown(
                        f"<div class='pc-row'><span class='pc-row-label'>{label}</span>"
                        f"<span class='pc-row-meta' style='white-space:normal;text-align:right'>{value}</span></div>",
                        unsafe_allow_html=True
                    )
        with st.container(border=True):
            st.markdown("### Corporate / Concession Network")
            _render_company_relationship_cards(corporate,f"portop_network_{_norm(oid)}",12)

    with right:
        with st.container(border=True):
            st.markdown("### Port & Terminal Footprint")
            mapped=[]
            for x in footprint:
                pnt=_asset_point(x.get("id"))
                if pnt: mapped.append(pnt)
            if mapped:
                st.map(pd.DataFrame(mapped),latitude="lat",longitude="lon",size=44,zoom=None,use_container_width=True)
            _render_company_asset_cards(footprint,f"portop_assets_{_norm(oid)}",14)

        if corridors:
            with st.container(border=True):
                st.markdown("### Corridor Exposure")
                for i,r in enumerate(corridors[:12]):
                    ck=_clean(r.get("corridor_key")); nm=_object_name("corridor",ck)
                    cols=st.columns([3.2,1.4,1.0])
                    cols[0].markdown(f"**{nm}**")
                    cols[1].caption((_clean(r.get("corridor_role")) or "connected").replace("_"," ").title())
                    cols[2].button("→",key=f"portop_corr_{_norm(oid)}_{i}",use_container_width=True,
                                   on_click=_set_context,args=("corridor",ck,nm))

    low1,low2=st.columns([1.0,1.25],gap="large")
    with low1:
        with st.container(border=True):
            st.markdown("### Investment, Transactions & Portfolio")
            _render_company_transaction_cards(tx,10)
            if portfolio:
                with st.expander(f"Portfolio positions ({len(portfolio)})"):
                    st.dataframe(pd.DataFrame(portfolio),hide_index=True,use_container_width=True)
    with low2:
        with st.container(border=True):
            st.markdown("### Current Developments")
            _render_event_rows(events,"portop_events_"+_norm(oid),10)

    with st.container(border=True):
        st.markdown("### Filings, Concessions & Evidence")
        if docs:
            for i,d in enumerate(docs[:15]):
                st.markdown(f"**{_clean(d.get('title')) or 'Untitled document'}**")
                src=_company_display_value(d.get("source_name"),d.get("document_type"),d.get("_relationship"))
                if src: st.caption(src)
                urls=_event_source_urls(d)
                if urls: st.link_button("Open source",urls[0],key=f"portop_doc_{_norm(oid)}_{i}")
        else:
            st.caption("No linked documents recorded yet.")

    st.markdown("### Operator Development Timeline")
    _render_event_rows(events,"portop_timeline_"+_norm(oid),15)

    with st.expander("Structured data / developer view"):
        st.json(rec)


def _is_institutional_entity(rec: dict) -> bool:
    blob=" ".join([
        _clean(rec.get("entity_type")),
        _clean(rec.get("sector")),
        _clean(rec.get("subtype")),
        _clean(rec.get("name")),
        _clean(rec.get("description")),
    ]).casefold()
    terms=(
        "authority","agency","administration","ministry","regulator","commission",
        "coast guard","navy","customs","border guard","port authority","maritime authority",
        "transport authority","civil aviation","aviation authority","railway authority"
    )
    return any(t in blob for t in terms)


def _asset_fact_pairs(rec: dict) -> list[tuple[str,str]]:
    fields=[
        ("Asset type",rec.get("asset_type")),
        ("Subtype",rec.get("subtype")),
        ("Status",rec.get("status")),
        ("Country",rec.get("country")),
        ("City / region",rec.get("region_city")),
        ("Annual capacity",rec.get("annual_capacity")),
        ("TEU capacity",rec.get("teu_capacity")),
        ("Cargo capacity",rec.get("capacity")),
        ("Land area (ha)",rec.get("land_area_ha")),
        ("Berths",rec.get("berth_count")),
        ("Depth (m)",rec.get("depth_m")),
        ("Runways",rec.get("runway_count")),
        ("Rail sidings",rec.get("rail_siding_count")),
        ("Operator",_object_name("entity",_clean(rec.get("operator_entity_id"))) if rec.get("operator_entity_id") else ""),
        ("Owner",_object_name("entity",_clean(rec.get("owner_entity_id"))) if rec.get("owner_entity_id") else ""),
    ]
    return [(k,_clean(v)) for k,v in fields if v not in (None,"",[],{})]


def _facility_fact_rows(rec: dict) -> list[dict]:
    """Expose dated source observations without treating proposals as operating capacity."""
    depth=_meta(rec).get("rotterdam_company_depth") or {}
    out=[]
    if not isinstance(depth,dict): return out
    def flatten(value, prefix=""):
        if isinstance(value,dict):
            return [pair for key,item in value.items() for pair in flatten(item,(prefix+" / " if prefix else "")+key.replace("_"," "))]
        if isinstance(value,list):
            if all(not isinstance(x,(dict,list)) for x in value):
                return [(prefix,", ".join(_clean(x) for x in value))]
            return [pair for i,item in enumerate(value,1) for pair in flatten(item,f"{prefix} {i}")]
        return [(prefix,_clean(value))] if value is not None else []
    for observation in depth.get("observations") or []:
        if not isinstance(observation,dict): continue
        for label,value in flatten({k:v for k,v in observation.items() if k not in {"source_key","source_url","checked_on"}}):
            out.append({"Observation":label.capitalize(),"Reported value":value,
                        "Checked":observation.get("checked_on") or depth.get("checked_on"),
                        "Source":observation.get("source_url") or ""})
    return out


def _render_infrastructure_history(oid: str, rec: dict, events: list[dict]):
    st.markdown("### History & Throughput")
    observations=(_meta(rec).get("rotterdam_history") or {}).get("annual_observations") or []
    if observations:
        st.caption("Throughput is measured cargo, not terminal capacity. Full-year and half-year periods are labelled separately.")
        st.dataframe([{"Period":str(x.get("period_start",""))+" – "+str(x.get("period_end","")),
                       "Coverage":_clean(x.get("period_kind")).replace("_"," "),
                       "Cargo (million tonnes)":x.get("total_cargo_million_tonnes"),
                       "Change (%)":x.get("yoy_percent"),"Reported":x.get("report_date"),
                       "Source":x.get("source_url")} for x in observations],hide_index=True,use_container_width=True)
    if not events:
        st.caption("No linked history recorded yet.")
        return
    years=sorted({_clean(e.get("start_date"))[:4] for e in events if e.get("start_date")},reverse=True)
    year=st.selectbox("History year",["All years"]+years,key="infra_history_year_"+_norm(oid))
    selected=[e for e in events if year=="All years" or _clean(e.get("start_date")).startswith(year)]
    st.caption(f"{len(selected)} linked developments · newest first")
    for i,e in enumerate(selected):
        annotation=_meta(e).get("rotterdam_history") or {}
        with st.expander(_clean(e.get("start_date"))[:10]+" · "+(_clean(e.get("title")) or "Development")):
            facts=annotation.get("description") or e.get("description")
            if facts: st.write(facts)
            analysis=annotation.get("analysis") or e.get("commercial_impact") or e.get("operational_impact")
            if analysis:
                st.caption("Analyst implication")
                st.write(analysis)
            _render_event_rows([e],f"infra_history_{_norm(oid)}_{i}",1)


@st.cache_data(ttl=60, show_spinner=False)
@st.cache_data(ttl=60, show_spinner=False)
def _rows_matching_ids(table: str, column: str, values: tuple[str, ...]) -> list[dict]:
    """Fetch scoped records with pagination instead of scanning a truncated global table.

    Cached because one dossier/lens resolves the same ecosystem IDs repeatedly across
    relationships, routes, projects and market views.
    """
    sb=_sb()
    if sb is None or not values: return []
    out=[]
    try:
        for offset in range(0,len(values),100):
            page_start=0
            while True:
                page=(sb.table(table).select("*").in_(column,list(values[offset:offset+100]))
                      .range(page_start,page_start+499).execute().data or [])
                out.extend(page)
                if len(page)<500: break
                page_start+=500
    except Exception:
        return []
    return out


def _infrastructure_service_scope(oid: str) -> set[str]:
    """Explicit aliases and contained facilities used for route/service resolution."""
    scope={str(oid)}; frontier=scope.copy()
    for _ in range(4):
        added=set()
        for side in ("source","target"):
            for r in _rows_matching_ids("pc_relationships",side+"_id",tuple(sorted(frontier))):
                if _clean(r.get("source_type")).casefold()!="asset" or _clean(r.get("target_type")).casefold()!="asset": continue
                source=_clean(r.get("source_id"));target=_clean(r.get("target_id"))
                relation=_norm(r.get("relationship_type"))
                if relation in {"alias of","same as"}:
                    if source in frontier: added.add(target)
                    if target in frontier: added.add(source)
                elif relation in {"located in","part of","terminal of","facility of"} and target in frontier:
                    added.add(source)
        frontier=added-scope
        scope.update(frontier)
        if not frontier: break
    return scope


def _infrastructure_routes(oid: str) -> list[dict]:
    scope=_infrastructure_service_scope(oid)
    values=tuple(sorted(scope));records={};matches={}
    def note(kind,rid,aid):
        if rid and aid in scope: matches.setdefault((kind,rid),set()).add(aid)
    def endpoints(kind,table,pk,columns,typed=False):
        for column in columns:
            for r in _rows_matching_ids(table,column,values):
                if typed and _norm(r.get(column.replace("_id","_type"))) not in {"asset","port","terminal","facility","airport","rail node","rail terminal","infrastructure"}: continue
                rid=_clean(r.get(pk))
                if rid:
                    records[(kind,rid)]=r
                    note(kind,rid,_clean(r.get(column)))
    endpoints("service","pc_transport_services","transport_service_id",("origin_asset_id","destination_asset_id"))
    for table,columns in (("pc_transport_service_stops",("asset_id","terminal_asset_id")),
                          ("pc_transport_service_network_links",("asset_id",))):
        for column in columns:
            for r in _rows_matching_ids(table,column,values):
                note("service",_clean(r.get("transport_service_id")),_clean(r.get(column)))
    service_ids=tuple(sorted(rid for kind,rid in matches if kind=="service"))
    for r in _rows_matching_ids("pc_transport_services","transport_service_id",service_ids):
        records[("service",_clean(r.get("transport_service_id")))]=r
    endpoints("route","pc_transport_routes","route_id",("origin_id","destination_id"),typed=True)
    endpoints("ferry","pc_ferry_routes","ferry_route_id",("origin_asset_id","destination_asset_id"))
    for r in _rows_matching_ids("pc_ferry_route_stops","stop_asset_id",values):
        note("ferry",_clean(r.get("ferry_route_id")),_clean(r.get("stop_asset_id")))
    ferry_ids=tuple(sorted(rid for kind,rid in matches if kind=="ferry"))
    for r in _rows_matching_ids("pc_ferry_routes","ferry_route_id",ferry_ids):
        records[("ferry",_clean(r.get("ferry_route_id")))]=r
    out=[]
    for (kind,rid),row in records.items():
        if (kind,rid) not in matches: continue
        out.append(dict(row,_route_kind=kind,_route_id=rid,_matched_asset_ids=sorted(matches[(kind,rid)])))
    return sorted(out,key=lambda r:_clean(r.get("service_name") or r.get("route_name")).casefold())


def _render_infrastructure_routes(routes: list[dict], oid: str):
    st.caption("Explicit endpoints, service calls and network links, including contained terminals and stored aliases. Status and dates reflect the stored record.")
    for i,r in enumerate(routes):
        title=_company_display_value(r.get("service_name"),r.get("route_name"),"Transport connection")
        status=_company_display_value(r.get("status"),r.get("current_status"),"Status not recorded")
        mode=_clean(r.get("mode")) or ("ferry" if r["_route_kind"]=="ferry" else "Mode not recorded")
        with st.expander(title+" · "+mode+" · "+status):
            labels=[_object_name("asset",aid) for aid in r["_matched_asset_ids"]]
            st.caption("Linked at: "+", ".join(labels))
            for label,columns in (("Service code",("service_code",)),("Type",("service_type",)),
                 ("Frequency",("frequency_value","frequency_unit")),("Effective from",("effective_start",)),
                 ("Effective to",("effective_end",)),("Trade lane",("trade_lane",)),
                 ("Description",("description",)),("Transit hours",("average_transit_time_hours",))):
                value=" ".join(_clean(r.get(c)) for c in columns if r.get(c) is not None)
                if value: st.write(label+": "+value)
            operator=_clean(r.get("primary_operator_entity_id") or r.get("operator_entity_id"))
            if operator:
                name=_object_name("entity",operator)
                st.button("Open operator: "+name,key=f"infra_route_operator_{_norm(oid)}_{i}",on_click=_set_context,args=("entity",operator,name))
            stops=[]; kind=r["_route_kind"];rid=r["_route_id"]
            if kind=="service":
                stops=_filtered_rows("pc_transport_service_stops","transport_service_id",rid,1000)
                schedules=_filtered_rows("pc_transport_service_schedules","transport_service_id",rid,100)
                if schedules:
                    st.dataframe([{k:s.get(k) for k in ("direction","frequency_value","frequency_unit","departure_local_time","timezone","valid_from","valid_to")} for s in schedules],hide_index=True,use_container_width=True)
            elif kind=="ferry": stops=_filtered_rows("pc_ferry_route_stops","ferry_route_id",rid,1000)
            if stops:
                stops.sort(key=lambda s:(_clean(s.get("direction")),int(s.get("sequence_no") or 0)))
                st.markdown("**Stored rotation / stops**")
                st.dataframe([{"Direction":s.get("direction"),"Sequence":s.get("sequence_no"),
                    "Stop":_object_name("asset",_clean(s.get("asset_id") or s.get("stop_asset_id"))),
                    "Terminal":_object_name("asset",_clean(s.get("terminal_asset_id"))) if s.get("terminal_asset_id") else "",
                    "Call":s.get("call_type") or s.get("stop_role"),"Valid from":s.get("valid_from"),"Valid to":s.get("valid_to")} for s in stops],hide_index=True,use_container_width=True)
                _open_selector([{"type":"asset","id":aid,"name":_object_name("asset",aid)} for s in stops for aid in [s.get("terminal_asset_id") or s.get("asset_id") or s.get("stop_asset_id")] if aid],f"infra_route_stops_{_norm(oid)}_{i}")
            urls=_event_source_urls(r)
            if r.get("source_id"):
                for source in _filtered_rows("pc_sources","source_id",_clean(r.get("source_id")),1):
                    urls+=_event_source_urls(source)
            if kind=="service":
                for source in _filtered_rows("pc_transport_service_sources","transport_service_id",rid,100):
                    urls+=_event_source_urls(source)
            for url in dict.fromkeys(urls): st.link_button("Source",url)


def _infrastructure_projects(oid: str, local: list[dict]) -> list[dict]:
    """Project-detail rows attached to the selected infrastructure ecosystem.

    pc_project_details is the canonical project extension table.  Project assets can
    sit anywhere beneath the selected port/system, so resolve against the recursively
    traversed local asset scope rather than relying on the deprecated pc_projects path.
    """
    scope={str(oid)}
    scope.update(_clean(x.get("id")) for x in (local or []) if x.get("id"))
    rows=_rows_matching_ids("pc_project_details","asset_id",tuple(sorted(scope)))
    out=[]
    for r in rows:
        aid=_clean(r.get("asset_id"))
        asset=object_record("asset",aid) or {}
        out.append({
            **r,
            "_project_name":_clean(asset.get("name")) or aid,
            "_project_status":_clean(asset.get("status") or r.get("project_stage")),
            "_project_region":_clean(asset.get("region_city")),
        })
    return sorted(
        out,
        key=lambda r: (
            _clean(r.get("announced_date") or r.get("construction_start_date") or r.get("expected_completion_date")),
            _clean(r.get("_project_name")),
        ),
        reverse=True,
    )


def _render_infrastructure_terminal(oid: str, rec: dict, lens: str):
    name=_object_name("asset",oid)
    dossier=_asset_dossier_rpc(oid)
    local=_dossier_local(dossier) if dossier else _local_infrastructure(rec)
    # The commercial dossier now reuses database-side entities/projects/events where
    # available; relationship-index calls remain only for corridors/service companies.
    companies=[]
    seen_company_ids=set()
    for e in (dossier.get("entities") or []) if dossier else []:
        eid=_clean(e.get("entity_id"))
        if eid and eid not in seen_company_ids:
            seen_company_ids.add(eid)
            companies.append({"id":eid,"name":_clean(e.get("name")) or eid,"role":"connected"})
    if not companies:
        companies=_asset_companies(rec)
    linked=_linked_objects_from_relationships("asset",oid)
    corridors=[x for x in linked if x.get("type")=="corridor"]
    company_ids={x["id"] for x in companies}
    service_companies=[x for x in linked if x.get("type")=="entity" and x.get("id") not in company_ids]
    events=(dossier.get("events") or []) if dossier else _events_for_object("asset",oid)
    docs=_related_table("pc_documents",oid,name,40)
    routes=_infrastructure_routes(oid)
    projects=(dossier.get("projects") or []) if dossier else _infrastructure_projects(oid,local)
    if dossier:
        # Preserve the display fields expected by the commercial project renderer.
        asset_names={_clean(a.get("asset_id")):_clean(a.get("name")) for a in dossier.get("assets") or []}
        projects=[{**p,
                   "_project_name":asset_names.get(_clean(p.get("asset_id")), _clean(p.get("asset_id"))),
                   "_project_status":_clean(p.get("project_stage"))} for p in projects]

    # Compact operational strip.  "Ecosystem nodes" is the recursively resolved
    # physical/system scope, not merely first-hop asset relationships.
    groups={}
    for x in local:
        groups[_infrastructure_group(x)]=groups.get(_infrastructure_group(x),0)+1
    m=st.columns(6)
    m[0].metric("Operators / owners",len(companies))
    m[1].metric("Ecosystem nodes",len(local))
    m[2].metric("Industrial / energy",groups.get("Industrial",0)+groups.get("Energy & Utilities",0))
    m[3].metric("Routes / services",len(routes))
    m[4].metric("Projects",len(projects))
    m[5].metric("Developments",len(events))

    left,right=st.columns([1.0,1.4],gap="large")
    with left:
        with st.container(border=True):
            st.markdown("### Node Profile")
            desc=_company_display_value(rec.get("description"),rec.get("notes"),rec.get("strategic_role"))
            if desc:
                st.write(desc)
            for label,value in _asset_fact_pairs(rec):
                st.markdown(
                    f"<div class='pc-row'><span class='pc-row-label'>{label}</span>"
                    f"<span class='pc-row-meta' style='white-space:normal;text-align:right'>{value}</span></div>",
                    unsafe_allow_html=True
                )

        with st.container(border=True):
            st.markdown("### Operators, Owners & Authorities")
            if companies:
                for i,x in enumerate(companies[:15]):
                    cols=st.columns([3.2,1.3,1.0])
                    cols[0].markdown(f"**{x['name']}**")
                    cols[1].caption((_clean(x.get("role")) or "linked").replace("_"," ").title())
                    cols[2].button("→",key=f"infra_comp_{_norm(oid)}_{i}",use_container_width=True,
                                   on_click=_set_context,args=("entity",x["id"],x["name"]))
            else:
                st.caption("No structured owner/operator relationships recorded.")

        if service_companies:
            with st.container(border=True):
                st.markdown("### Connected Companies & Services")
                _render_company_relationship_cards(service_companies,f"infra_services_{_norm(oid)}",15)

    with right:
        with st.container(border=True):
            st.markdown("### Spatial & Local System")
            _render_map_for_asset(rec)
            if local:
                st.markdown(f"#### Connected infrastructure ecosystem ({len(local)})")
                st.caption("Recursive explicit graph traversal: contained port complexes, zones, docks, terminals and facilities, plus one-hop rail/pipeline/utility system links.")
                grouped={}
                for item in local:
                    grouped.setdefault(_infrastructure_group(item),[]).append(item)
                for group_name in ("Terminals","Industrial","Energy & Utilities","Rail & Intermodal",
                                   "Marine Services","Port Infrastructure","Ro-Ro / Cruise","Other Infrastructure"):
                    rows=grouped.get(group_name) or []
                    if not rows:
                        continue
                    with st.expander(f"{group_name} ({len(rows)})", expanded=group_name in {"Terminals","Industrial"}):
                        _render_company_asset_cards(rows,f"infra_local_{_norm(oid)}_{_norm(group_name)}",30)
            elif not _coords_from_record(rec):
                st.caption("No mapped local network is currently stored for this node.")

        if corridors or routes:
            with st.container(border=True):
                st.markdown("### Corridors, Routes & Services")
                if corridors:
                    for i,x in enumerate(corridors[:10]):
                        cols=st.columns([3.2,1.4,1.0])
                        cols[0].markdown(f"**{x['name']}**")
                        cols[1].caption((_clean(x.get("relationship")) or "connected").title())
                        cols[2].button("→",key=f"infra_corr_{_norm(oid)}_{i}",use_container_width=True,
                                       on_click=_set_context,args=("corridor",x["id"],x["name"]))
                if routes:
                    st.markdown(f"#### Routes / services ({len(routes)})")
                    _render_infrastructure_routes(routes,oid)

    low1,low2=st.columns([1.0,1.25],gap="large")
    with low1:
        with st.container(border=True):
            st.markdown("### Capacity, Projects & Investment")
            facts=_facility_fact_rows(rec)
            if facts:
                st.dataframe(facts,hide_index=True,use_container_width=True)
            if projects:
                for i,p in enumerate(projects[:18]):
                    title=_company_display_value(p.get("_project_name"),p.get("scope_description"),"Project")
                    status=_company_display_value(p.get("_project_status"),p.get("project_stage"))
                    value=p.get("estimated_cost")
                    currency=_company_display_value(p.get("currency"))
                    st.markdown(f"**{title}**")
                    bits=[]
                    if status: bits.append(status.replace("_"," ").title())
                    if value not in (None,""):
                        try:
                            amount=float(value)
                            if amount>=1_000_000_000:
                                vtxt=f"{amount/1_000_000_000:.2f}bn"
                            elif amount>=1_000_000:
                                vtxt=f"{amount/1_000_000:.1f}m"
                            else:
                                vtxt=f"{amount:,.0f}"
                            bits.append(((currency+" ") if currency else "")+vtxt)
                        except Exception:
                            bits.append(((currency+" ") if currency else "")+_clean(value))
                    dates=[]
                    if p.get("announced_date"): dates.append("announced "+_clean(p.get("announced_date"))[:10])
                    if p.get("construction_start_date"): dates.append("start "+_clean(p.get("construction_start_date"))[:10])
                    if p.get("expected_completion_date"): dates.append("target "+_clean(p.get("expected_completion_date"))[:10])
                    if dates: bits.append(" · ".join(dates))
                    if bits: st.caption(" · ".join(bits))
                    if p.get("scope_description"): st.write(p.get("scope_description"))
                    src=_clean(p.get("source_url"))
                    if not src and p.get("source_id"):
                        ss=_filtered_rows("pc_sources","source_id",_clean(p.get("source_id")),1)
                        if ss: src=_clean(ss[0].get("url"))
                    if src:
                        st.link_button("Source",src,key=f"infra_project_src_{_norm(oid)}_{i}")
            elif not facts:
                st.caption("No structured projects or investment records linked yet.")

            investment_events=[
                e for e in events
                if "investment" in _norm(e.get("event_type"))
                or "investment" in _norm(e.get("event_family"))
                or "capital" in _norm(e.get("event_category"))
            ]
            if investment_events:
                st.markdown("#### Investment history")
                hist=[]
                for e in sorted(investment_events,key=lambda x:_clean(x.get("start_date")),reverse=True)[:12]:
                    m=_meta(e)
                    hist.append({
                        "Date":_clean(e.get("start_date"))[:10],
                        "Investment":_clean(e.get("title")),
                        "Value":_clean(m.get("investment_value_display") or m.get("investment_value_eur")),
                    })
                st.dataframe(pd.DataFrame(hist),hide_index=True,use_container_width=True)

    with low2:
        with st.container(border=True):
            st.markdown("### Current Developments")
            if events:
                _render_event_rows(events,"infra_events_"+_norm(oid),10)
            else:
                st.caption("No linked developments recorded.")

    with st.container(border=True):
        st.markdown("### Evidence & Documents")
        if docs:
            for i,d in enumerate(docs[:12]):
                title=_clean(d.get("title")) or "Untitled document"
                st.markdown(f"**{title}**")
                src=_company_display_value(d.get("source_name"),d.get("document_type"))
                if src: st.caption(src)
                urls=_event_source_urls(d)
                if urls:
                    st.link_button("Open source",urls[0],key=f"infra_doc_{_norm(oid)}_{i}")
        else:
            st.caption("No linked documents recorded yet.")

    with st.container(border=True):
        _render_infrastructure_history(oid,rec,events)

    if local:
        with st.expander("Facility capacity, investment & operating details"):
            stored=0
            for item in local:
                facility=object_record("asset",item["id"]) or {}
                facts=_facility_fact_rows(facility)
                if facts:
                    stored+=1
                    st.markdown("#### "+(_clean(facility.get("name")) or item["name"]))
                    st.dataframe(facts,hide_index=True,use_container_width=True)
            if not stored: st.caption("No sourced facility observations recorded for connected infrastructure yet.")

    with st.expander("Structured data / developer view"):
        st.json(rec)


def _render_institution_terminal(oid: str, rec: dict, lens: str):
    name=_object_name("entity",oid)
    profiles=_company_profile_rows(oid)
    p=profiles[0] if profiles else {}
    rels=_linked_objects_from_relationships("entity",oid)
    entities=[x for x in rels if x.get("type")=="entity"]
    roles=_company_asset_roles(oid)
    assets=[]
    for r in roles:
        aid=_clean(r.get("asset_id"))
        mid=_clean(r.get("mobile_asset_id"))
        if aid:
            assets.append({"type":"asset","id":aid,"name":_asset_chip(aid),"relationship":_clean(r.get("asset_role"))})
        elif mid:
            assets.append({"type":"mobile_asset","id":mid,"name":_object_name("mobile_asset",mid),"relationship":_clean(r.get("asset_role"))})
    corridors=_company_corridors(oid)
    events=_events_for_object("entity",oid)
    docs=_documents_for_entity(oid) or _documents_by_name(name,30)
    programmes=_related_table("pc_programmes",oid,name,100)
    operations=_related_table("pc_security_operations",oid,name,100)

    # Investment platforms / institutional entities (for example ADQ or LIMAD)
    # use their own dossier renderer, but should expose the same temporal
    # corporate-tree view as operating companies.
    company_view = st.radio(
        "Company view",
        ["Overview", "Corporate Tree"],
        horizontal=True,
        label_visibility="collapsed",
        key=f"company_view_{_norm(oid)}",
    )
    if company_view == "Corporate Tree":
        _render_company_tree_view(oid, rec, None)
        return

    m=st.columns(6)
    m[0].metric("Linked organisations",len(entities))
    m[1].metric("Assets / facilities",len(assets))
    m[2].metric("Corridors / systems",len(corridors))
    m[3].metric("Programmes",len(programmes))
    m[4].metric("Operations",len(operations))
    m[5].metric("Developments",len(events))

    left,right=st.columns([1.0,1.35],gap="large")
    with left:
        with st.container(border=True):
            st.markdown("### Institutional Profile")
            desc=_company_display_value(p.get("business_description"),rec.get("description"),rec.get("business_description"))
            if desc: st.write(desc)
            facts=[
                ("Institution type",_company_display_value(rec.get("entity_type"),rec.get("subtype"))),
                ("Jurisdiction",_company_display_value(rec.get("hq_country"),rec.get("country"))),
                ("Headquarters",_company_display_value(rec.get("hq_city"),rec.get("region_city"))),
                ("Mandate / sector",_company_display_value(p.get("sector"),rec.get("sector"))),
                ("Website",_company_display_value(p.get("website_url"),rec.get("website_url"))),
            ]
            for label,value in facts:
                if value:
                    st.markdown(
                        f"<div class='pc-row'><span class='pc-row-label'>{label}</span>"
                        f"<span class='pc-row-meta' style='white-space:normal;text-align:right'>{value}</span></div>",
                        unsafe_allow_html=True
                    )

        with st.container(border=True):
            st.markdown("### Institutional Network")
            _render_company_relationship_cards(entities,f"inst_network_{_norm(oid)}",15)

    with right:
        with st.container(border=True):
            st.markdown("### Assets, Facilities & Operating Footprint")
            mapped=[]
            for n in assets:
                if n.get("type")=="asset":
                    pnt=_asset_point(n.get("id"))
                    if pnt: mapped.append(pnt)
            if mapped:
                st.map(pd.DataFrame(mapped),latitude="lat",longitude="lon",size=44,zoom=None,use_container_width=True)
            _render_company_asset_cards(assets,f"inst_assets_{_norm(oid)}",12)

        if corridors:
            with st.container(border=True):
                st.markdown("### Corridors / Systems Under Exposure")
                for i,r in enumerate(corridors[:12]):
                    ck=_clean(r.get("corridor_key"))
                    nm=_object_name("corridor",ck)
                    role=_clean(r.get("corridor_role")).replace("_"," ").title()
                    cols=st.columns([3.2,1.4,1.0])
                    cols[0].markdown(f"**{nm}**")
                    cols[1].caption(role or "Connected")
                    cols[2].button("→",key=f"inst_corr_{_norm(oid)}_{i}",use_container_width=True,
                                   on_click=_set_context,args=("corridor",ck,nm))

    low1,low2=st.columns([1.0,1.25],gap="large")
    with low1:
        with st.container(border=True):
            st.markdown("### Programmes / Operations")
            rows=[]
            for pgr in programmes[:10]:
                rows.append(_company_display_value(pgr.get("programme_name"),pgr.get("name"),pgr.get("title")))
            for op in operations[:10]:
                rows.append(_company_display_value(op.get("operation_name"),op.get("name"),op.get("title")))
            rows=[x for x in rows if x]
            if rows:
                for x in rows: st.markdown("• "+x)
            else:
                st.caption("No structured programmes or operations linked yet.")

    with low2:
        with st.container(border=True):
            st.markdown("### Current Developments")
            if events:
                _render_event_rows(events,"inst_events_"+_norm(oid),10)
            else:
                st.caption("No linked developments recorded.")

    with st.container(border=True):
        st.markdown("### Directives, Circulars, Evidence & Documents")
        if docs:
            for i,d in enumerate(docs[:15]):
                title=_clean(d.get("title")) or "Untitled document"
                st.markdown(f"**{title}**")
                source=_company_display_value(d.get("source_name"),d.get("document_type"),d.get("_relationship"))
                if source: st.caption(source)
                urls=_event_source_urls(d)
                if urls:
                    st.link_button("Open source",urls[0],key=f"inst_doc_{_norm(oid)}_{i}")
        else:
            st.caption("No linked documents recorded yet.")

    st.markdown("### Institutional Timeline")
    if events:
        _render_event_rows(events,"inst_timeline_"+_norm(oid),15)
    else:
        st.caption("No linked chronological developments yet.")

    with st.expander("Structured data / developer view"):
        st.json(rec)


def _local_infrastructure(rec: dict, max_depth: int = 4, max_nodes: int = 250):
    """Return the explicit infrastructure ecosystem beneath/around an asset.

    Structural containment is traversed recursively so a port-system dossier can see
    port complexes -> zones/docks -> terminals/facilities -> sub-facilities. Explicit
    lateral infrastructure links are then added one hop from that structural scope.
    No proximity, operator-portfolio or same-region inference is used.
    """
    root = str(rec.get("asset_id") or "")
    if not root:
        return []

    structural = {"located in", "part of", "terminal of", "facility of", "alias of", "same as"}
    lateral = {
        "connected to", "connects to", "rail connected to", "pipeline connected to",
        "feeds", "serves", "uses", "co located with", "integrated with",
        "receives feedstock from", "supplies steam to", "planned connection to"
    }

    depth_by_id = {root: 0}
    rel_by_id = {}
    frontier = {root}

    # Descendants/aliases: recurse only through explicit structural relationships.
    for depth in range(max(1, min(max_depth, 6))):
        if not frontier or len(depth_by_id) >= max_nodes:
            break
        next_frontier = set()
        for side in ("source", "target"):
            for r in _rows_matching_ids("pc_relationships", side + "_id", tuple(sorted(frontier))):
                if _clean(r.get("source_type")).casefold() != "asset" or _clean(r.get("target_type")).casefold() != "asset":
                    continue
                source = _clean(r.get("source_id"))
                target = _clean(r.get("target_id"))
                relation = _norm(r.get("relationship_type"))
                child = None

                if relation in {"alias of", "same as"}:
                    if source in frontier:
                        child = target
                    elif target in frontier:
                        child = source
                elif relation in structural and target in frontier:
                    # Canonical direction: child/facility -> relation -> parent/system.
                    child = source

                if child and child not in depth_by_id and len(depth_by_id) < max_nodes:
                    depth_by_id[child] = depth + 1
                    rel_by_id[child] = relation
                    next_frontier.add(child)
        frontier = next_frontier

    structural_ids = set(depth_by_id)

    # One-hop explicit system connections from any structural node.  Do not recurse
    # these, otherwise a rail/pipeline connection can fan out into a remote network.
    for side in ("source", "target"):
        for r in _rows_matching_ids("pc_relationships", side + "_id", tuple(sorted(structural_ids))):
            if _clean(r.get("source_type")).casefold() != "asset" or _clean(r.get("target_type")).casefold() != "asset":
                continue
            relation = _norm(r.get("relationship_type"))
            if relation not in lateral:
                continue
            source = _clean(r.get("source_id"))
            target = _clean(r.get("target_id"))
            if source in structural_ids:
                other = target
            elif target in structural_ids:
                other = source
            else:
                continue
            if other and other != root and other not in depth_by_id and len(depth_by_id) < max_nodes:
                depth_by_id[other] = min(max_depth + 1, 7)
                rel_by_id[other] = relation

    out = []
    for aid, depth in sorted(depth_by_id.items(), key=lambda kv: (kv[1], kv[0])):
        if aid == root:
            continue
        row = object_record("asset", aid) or {}
        if not row:
            continue
        out.append({
            "type": "asset",
            "id": aid,
            "name": _clean(row.get("name")) or aid,
            "relationship": rel_by_id.get(aid, "contained infrastructure").replace("_", " "),
            "asset_type": row.get("asset_type"),
            "subtype": row.get("subtype"),
            "region": row.get("region_city"),
            "country": row.get("country"),
            "depth": depth,
        })
    return out


def _infrastructure_group(item: dict) -> str:
    """Stable analyst-facing grouping for port/infrastructure ecosystem nodes."""
    text = " ".join([
        _clean(item.get("asset_type")),
        _clean(item.get("subtype")),
        _clean(item.get("name")),
    ]).casefold()
    if re.search(r"rail|intermodal|marshalling|line 11|freight line", text):
        return "Rail & Intermodal"
    if re.search(r"pipeline|hydrogen|co2|steam|utility|energy|lng|ammonia|shore power", text):
        return "Energy & Utilities"
    if re.search(r"refiner|chemical|industrial|plant|complex|verbund|polymer|olefin|phenol", text):
        return "Industrial"
    if re.search(r"shipyard|dry ?dock|towage|tug|vessel traffic|vts|marine maintenance|crane", text):
        return "Marine Services"
    if re.search(r"lock|dock|bridge|port zone|outer port|left bank|right bank|harbour", text):
        return "Port Infrastructure"
    if re.search(r"cruise|roro|ro-ro|ferry|automotive", text):
        return "Ro-Ro / Cruise"
    if re.search(r"terminal|container depot|breakbulk|bulk|tank", text):
        return "Terminals"
    return "Other Infrastructure"


def render_terminal(lens: str = "trade"):
    lens = lens if lens in LENS else "trade"
    cfg = LENS[lens]
    sb = _sb()
    if sb is None:
        st.error("P&C database connection is not configured.")
        st.stop()

    # Restore deep-link context before drawing navigation so Home is never shown
    # as active while an object dossier is open.
    _restore_context()

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
        default_nav=("Home" if lens=="trade" else
                     "Operating Picture" if lens=="intelligence" else
                     "Exposure Picture" if lens=="sanctions" else "Industrial Picture")
        has_context=bool(st.session_state.get("pc_terminal_id") and st.session_state.get("pc_terminal_type"))
        current="__selected_object__" if has_context else st.session_state.get(f"pc_terminal_nav_{lens}",default_nav)

        if has_context:
            selected_name=st.session_state.get("pc_terminal_name") or object_label(
                st.session_state.get("pc_terminal_type"),
                st.session_state.get("pc_terminal_id"),
            )
            st.markdown("<div class='pc-k'>VIEWING DOSSIER</div>",unsafe_allow_html=True)
            st.markdown("**"+_clean(selected_name)+"**")
            st.caption((_clean(st.session_state.get("pc_terminal_type")) or "object").replace("_"," ").title())
            if st.session_state.get("pc_terminal_history"):
                st.button("← Back",key=f"pc_back_{lens}",use_container_width=True,on_click=_back_context)
            st.divider()

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
            _home_nav(lens)
            st.rerun()
        if st.button("Refresh database", use_container_width=True):
            refresh_errors=[]
            try:
                sb.rpc("pc_refresh_terminal_indexes").execute()
            except Exception as exc:
                refresh_errors.append("core graph: "+str(exc)[:180])
            try:
                sb.rpc("pc_refresh_terminal_industrial_links").execute()
            except Exception as exc:
                # 062 may not be installed yet; keep core refresh usable.
                if "Could not find the function" not in str(exc) and "PGRST202" not in str(exc):
                    refresh_errors.append("industrial graph: "+str(exc)[:180])
            st.cache_data.clear()
            if refresh_errors:
                st.warning("Database refreshed with warnings: "+"; ".join(refresh_errors))
            else:
                st.success("Canonical terminal relationship graph refreshed.")
            st.rerun()
        st.caption("Terminal index: " + ("active" if _terminal_index_ready() else "legacy fallback"))

    _style(theme)
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

    # Entity and infrastructure objects use purpose-built dossiers rather than raw record panes.
    if typ=="entity":
        if _is_institutional_entity(rec):
            _render_institution_terminal(oid,rec,lens)
        elif _is_port_operator_entity(rec):
            _render_port_operator_terminal(oid,rec,lens)
        else:
            _render_company_terminal(oid,rec,lens)
        return
    if typ=="asset":
        # Lazy import prevents circular startup imports while guaranteeing that Trade
        # and Strategic Industries both get the shared cross-market dossier tabs even
        # when the deployment entry point imports pc_terminal directly.
        if lens in {"trade", "strategic"}:
            try:
                from pc_market_lenses import render_infrastructure_market_lenses
                render_infrastructure_market_lenses(oid, rec, lens)
                return
            except Exception as exc:
                st.warning("Cross-market lenses unavailable; showing core infrastructure dossier. " + str(exc)[:180])
        _render_infrastructure_terminal(oid,rec,lens)
        return
    if typ=="mobile_asset":
        _render_mobile_asset_terminal(oid,rec,lens)
        return

    # Persistent tactical workspace for corridors and events.
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
