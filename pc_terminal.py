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
    if typ == "corridor":
        table, pk, _, _ = OBJECTS[typ]
        rows = _filtered_rows(table, pk, str(oid), 3)
        return typ, oid, rows[0] if rows else None
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
        p = "--bg:#f5f7fa;--panel:#fff;--panel2:#f8fafc;--line:#d7dee8;--text:#182230;--muted:#667383;--gold:#977421;--blue:#315e9c;--red:#b2564d;--green:#427d61"
    else:
        p = "--bg:#09111d;--panel:#101927;--panel2:#0d1623;--line:#26364a;--text:#edf2f7;--muted:#9facbd;--gold:#d1ad59;--blue:#6699e8;--red:#d37a72;--green:#72a78c"
    st.markdown(f"""
    <style>
    :root{{{p}}}
    .stApp{{background:var(--bg);color:var(--text)}}
    [data-testid="stSidebar"]{{background:var(--panel2)!important;border-right:1px solid var(--line)}}
    [data-testid="stSidebar"] *{{color:var(--text)!important}}
    .block-container{{max-width:1780px;padding-top:1rem;padding-bottom:3rem}}
    h1,h2,h3,h4,p,label,span,li{{color:var(--text)!important}}
    .pc-k{{color:var(--gold);font-size:.68rem;font-weight:750;letter-spacing:.14em;text-transform:uppercase}}
    .pc-sub{{color:var(--muted);font-size:.9rem}}
    .pc-command{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:.8rem 1rem;margin:.5rem 0 1rem}}
    .pc-context{{background:var(--panel);border:1px solid var(--line);border-left:4px solid var(--gold);border-radius:9px;padding:.9rem 1rem;margin:.4rem 0 1rem}}
    .pc-card{{background:var(--panel);border:1px solid var(--line);border-radius:9px;padding:.85rem 1rem;min-height:115px}}
    .pc-muted{{color:var(--muted);font-size:.82rem}}
    [data-testid="stMetric"]{{background:var(--panel);border:1px solid var(--line);border-top:2px solid var(--gold);padding:.55rem .7rem;border-radius:7px}}
    [data-testid="stDataFrame"]{{border:1px solid var(--line);border-radius:7px}}
    [data-testid="stExpander"]{{background:var(--panel);border:1px solid var(--line);border-radius:7px}}
    div.stButton>button{{border:1px solid #806b38;color:var(--gold);background:var(--panel);border-radius:7px}}
    [data-baseweb="input"]>div,[data-baseweb="select"]>div,input{{background:var(--panel)!important;color:var(--text)!important}}
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
    out = []
    for side in ("source", "target"):
        out.extend(_filtered_rows("pc_relationships", f"{side}_id", str(oid), 500))
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
    return _filtered_rows("pc_company_asset_roles", "entity_id", str(entity_id), 500)


def _company_corridors(entity_id: str) -> list[dict]:
    return _filtered_rows("pc_company_corridor_roles", "entity_id", str(entity_id), 500)


def _portfolio(entity_id: str) -> list[dict]:
    return _filtered_rows("pc_company_portfolio_positions", "holder_entity_id", str(entity_id), 500)


def _documents_for_entity(entity_id: str) -> list[dict]:
    links = _filtered_rows("pc_document_entity_links", "entity_id", str(entity_id), 500)
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
        if ot not in OBJECTS:
            continue
        out.append({
            "type": ot,
            "id": oi,
            "name": _object_name(ot, oi),
            "relationship": _clean(r.get("relationship_type")).replace("_", " "),
        })
    return out


def _local_infrastructure(asset: dict, limit: int = 80) -> list[dict]:
    """Return nearby/same-system canonical infrastructure using stored geography.

    This is a discovery lens, not an inferred ownership relationship.
    """
    aid=_clean(asset.get("asset_id"))
    country=_clean(asset.get("country")).casefold()
    region=_clean(asset.get("region_city")).casefold()
    name=_clean(asset.get("name")).casefold()
    out=[]
    seen={aid}
    for r in _rows("pc_assets",5000):
        rid=_clean(r.get("asset_id"))
        if not rid or rid in seen:
            continue
        rc=_clean(r.get("country")).casefold()
        rr=_clean(r.get("region_city")).casefold()
        rn=_clean(r.get("name")).casefold()
        score=0
        if country and rc==country: score+=10
        if region and rr:
            if rr==region: score+=40
            elif region in rr or rr in region: score+=25
        if name and rn and (name in rn or rn in name): score+=15
        if score>=25:
            seen.add(rid)
            out.append((score,{
                "type":"asset","id":rid,"name":_clean(r.get("name")),
                "relationship":"same local infrastructure system",
                "asset_type":_clean(r.get("asset_type")),
                "region":_clean(r.get("region_city")),
                "country":_clean(r.get("country")),
            }))
    out.sort(key=lambda x:(x[0],x[1]["name"]),reverse=True)
    return [x[1] for x in out[:limit]]

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
        links=_event_links("event",oid)
        objs=[]
        for l in links:
            lt=_clean(l.get("linked_type")).casefold()
            if lt=="vessel": lt="mobile_asset"
            lid=_clean(l.get("linked_id"))
            if lt in OBJECTS and lid:
                objs.append({"type":lt,"id":lid,"name":_object_name(lt,lid),"relationship":_clean(l.get("relationship"))})
        if objs:
            st.dataframe(pd.DataFrame([{"Object":x["name"],"Relationship":x["relationship"]} for x in objs]),
                         hide_index=True,use_container_width=True)
            _open_selector(objs,f"spatial_event_{oid}")


def _render_evidence_pane(typ: str, oid: str, rec: dict, lens: str):
    st.markdown("### Intelligence / Evidence")
    st.caption("Developments, documents, filings, sanctions and source provenance.")

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

    if lens == "sanctions":
        st.markdown("#### Sanctions / exposure")
        sanctions = _related_table("pc_sanctions_designations", oid, _object_name(typ, oid), 100)
        links = _related_table("pc_sanctions_links", oid, _object_name(typ, oid), 100)
        screening = _related_table("pc_screening_results", oid, _object_name(typ, oid), 100)
        if sanctions:
            st.dataframe(pd.DataFrame(sanctions), hide_index=True, use_container_width=True)
        if links:
            st.markdown("**Ownership / designation network**")
            st.dataframe(pd.DataFrame(links), hide_index=True, use_container_width=True)
        if screening:
            st.markdown("**Screening / review**")
            st.dataframe(pd.DataFrame(screening), hide_index=True, use_container_width=True)
        if not (sanctions or links or screening):
            st.caption("No sanctions/designation record is currently linked to this canonical context.")

    if lens == "strategic":
        st.markdown("#### Strategic programmes / capacity")
        found = False
        for title, table in (("Programmes / projects","pc_project_details"),("Contracts","pc_contracts"),("Shipbuilding orders","pc_shipbuilding_orders")):
            x = _related_table(table, oid, _object_name(typ, oid), 120)
            if x:
                found = True
                st.markdown("**" + title + "**")
                st.dataframe(pd.DataFrame(x), hide_index=True, use_container_width=True)
        if not found:
            st.caption("No strategic programme, contract or order is currently linked to this context.")


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


def _render_home(lens: str):
    cfg = LENS[lens]
    st.markdown(f"<div class='pc-k'>{cfg['brand']} · terminal</div>", unsafe_allow_html=True)
    st.title(cfg["title"])
    st.markdown(f"<div class='pc-sub'>{cfg['deck']}</div>", unsafe_allow_html=True)

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
                c1.markdown(
                    f"**{x['name']}**  
"
                    + " · ".join(v for v in [x.get("kind"),x.get("subtype"),x.get("country")] if v)
                )
                with c2:
                    st.button(
                        "Open",
                        key=f"pc_terminal_more_{lens}_{j}_{x['type']}_{x['id']}",
                        use_container_width=True,
                        on_click=_open_search_result,
                        args=(lens,x["type"],x["id"],x["name"]),
                    )

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
        if st.button("Home / clear selection", use_container_width=True):
            _clear_context()
            st.rerun()
        if st.button("Refresh database", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    _style(theme)
    _restore_context()

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
