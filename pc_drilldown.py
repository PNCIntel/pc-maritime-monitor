
from __future__ import annotations
from pathlib import Path
import sys, json, html
import pandas as pd
import streamlit as st

SHARED_DIR = Path(__file__).resolve().parent
if str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))
from pc_db import client as pc_db_client

OBJECTS = {
    "entity": {"table":"pc_entities","id":"entity_id","name":"name","label":"Entity / Company"},
    "asset": {"table":"pc_assets","id":"asset_id","name":"name","label":"Asset / Infrastructure"},
    "mobile_asset": {"table":"pc_mobile_assets","id":"mobile_asset_id","name":"name","label":"Mobile Asset / Vessel"},
    "vessel": {"table":"pc_mobile_assets","id":"mobile_asset_id","name":"name","label":"Mobile Asset / Vessel"},
    "event": {"table":"pc_events","id":"event_id","name":"title","label":"Event"},
}

VISIBLE_KEYS = {
    "entity":["name","entity_type","subtype","hq_country","hq_location","country","status","record_status","data_quality","notes"],
    "asset":["name","asset_type","subtype","country","region_city","status","confidence","owner_entity_id","operator_entity_id","notes"],
    "mobile_asset":["name","asset_type","subtype","imo","mmsi","call_sign_or_registration","flag","build_year","gross_tonnage","dwt","length_m","beam_m","owner_entity_id","operator_entity_id","manager_entity_id","status","notes"],
    "event":["title","start_date","end_date","event_nature","event_domain","event_family","event_type","severity","status","mode","countries","location","description","operational_impact","commercial_impact","confidence","trade_relevance","intelligence_relevance","alert_worthy"],
}

def _sb():
    try:
        return pc_db_client(service=True)
    except Exception:
        return None

def _rows(table, filters=None, limit=500):
    sb=_sb()
    if not sb:
        return []
    try:
        q=sb.table(table).select("*")
        for k,v in (filters or {}).items():
            q=q.eq(k,v)
        return q.limit(limit).execute().data or []
    except Exception:
        return []

def _one(table,id_col,object_id):
    x=_rows(table,{id_col:str(object_id)},5)
    return x[0] if x else None

def _clean(v):
    if v is None:
        return ""
    if isinstance(v,(dict,list)):
        return json.dumps(v,ensure_ascii=False)
    return str(v)

def _type(v):
    t=str(v or "").strip().lower()
    if t=="vessel": return "mobile_asset"
    if t in OBJECTS: return t
    if t in {"company","organization","organisation"}: return "entity"
    if t in {"port","terminal","infrastructure","facility"}: return "asset"
    return t

def object_record(object_type,object_id):
    typ=_type(object_type)
    cfg=OBJECTS.get(typ)
    return _one(cfg["table"],cfg["id"],object_id) if cfg else None

def object_label(object_type,object_id):
    typ=_type(object_type)
    cfg=OBJECTS.get(typ)
    rec=object_record(typ,object_id) if cfg else None
    if rec:
        return _clean(rec.get(cfg["name"])) or str(object_id)
    return str(object_id)

def _relationship_rows(object_type,object_id):
    typ=_type(object_type); oid=str(object_id)
    rels=[]
    for side in ("source","target"):
        rels.extend(_rows("pc_relationships",{f"{side}_type":typ,f"{side}_id":oid},500))
    seen=set(); out=[]
    for r in rels:
        k=str(r.get("relationship_id") or (r.get("source_id"),r.get("relationship_type"),r.get("target_id")))
        if k in seen: continue
        seen.add(k); out.append(r)
    return out

def _event_links_for_object(object_type,object_id):
    return _rows("pc_event_links",{"linked_type":_type(object_type),"linked_id":str(object_id)},500)

def _event_links_for_event(event_id):
    return _rows("pc_event_links",{"event_id":str(event_id)},500)

def _event_rows_for_object(object_type,object_id):
    out=[]
    for link in _event_links_for_object(object_type,object_id)[:100]:
        ev=object_record("event",link.get("event_id"))
        if ev:
            e=dict(ev); e["_relationship"]=link.get("relationship"); out.append(e)
    return out

def set_drilldown(object_type,object_id,label=None,rerun=True):
    typ=_type(object_type)
    st.session_state["pc_drilldown_type"]=typ
    st.session_state["pc_drilldown_id"]=str(object_id)
    if label: st.session_state["pc_drilldown_label"]=str(label)
    try:
        st.query_params["pc_object_type"]=typ
        st.query_params["pc_object_id"]=str(object_id)
    except Exception:
        pass
    if rerun: st.rerun()

def clear_drilldown(rerun=True):
    for k in ["pc_drilldown_type","pc_drilldown_id","pc_drilldown_label"]:
        st.session_state.pop(k,None)
    try:
        for k in ["pc_object_type","pc_object_id"]:
            if k in st.query_params: del st.query_params[k]
    except Exception:
        pass
    if rerun: st.rerun()

def restore_drilldown_from_query():
    if st.session_state.get("pc_drilldown_id"): return
    try:
        typ=st.query_params.get("pc_object_type")
        oid=st.query_params.get("pc_object_id")
        if typ and oid:
            st.session_state["pc_drilldown_type"]=_type(typ)
            st.session_state["pc_drilldown_id"]=str(oid)
    except Exception:
        pass

def drilldown_button(object_type,object_id,label="Open details",key=None,use_container_width=False,key_prefix=""):
    if not object_id:
        return False
    typ=_type(object_type)
    prefix=f"{key_prefix}_" if key_prefix else ""
    final_key=key or f"{prefix}dd_{typ}_{object_id}"
    if st.button(label,key=final_key,use_container_width=use_container_width):
        set_drilldown(typ,object_id,rerun=True)
        return True
    return False

def _record_summary(rec,typ):
    rows=[]
    for k in VISIBLE_KEYS.get(typ,[]):
        v=rec.get(k)
        if v in (None,"",[],{}): continue
        rows.append({"Field":k.replace("_"," ").title(),"Value":_clean(v)})
    return rows

def _render_overview(rec,typ):
    cfg=OBJECTS[typ]
    title=_clean(rec.get(cfg["name"])) or _clean(rec.get(cfg["id"]))
    st.markdown(f"### {html.escape(title)}")
    st.caption(f"{cfg['label']} · {_clean(rec.get(cfg['id']))}")
    rows=_record_summary(rec,typ)
    if rows:
        st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
    urls=[]
    for k,v in rec.items():
        if "url" in str(k).lower() and isinstance(v,str) and v.startswith("http"):
            urls.append((k,v))
    md=rec.get("metadata")
    if isinstance(md,str):
        try: md=json.loads(md)
        except Exception: md=None
    if isinstance(md,dict):
        for u in md.get("research_sources") or []:
            if isinstance(u,str) and u.startswith("http"): urls.append(("research source",u))
    if urls:
        st.markdown("#### Sources")
        seen=set()
        for label,url in urls:
            if url in seen: continue
            seen.add(url)
            st.link_button(str(label).replace("_"," ").title(),url,use_container_width=True)

def _render_relationships(typ,oid,key_prefix="main"):
    rows=_relationship_rows(typ,oid)
    if not rows:
        st.caption("No canonical relationships recorded."); return
    for i,r in enumerate(rows):
        is_source=_type(r.get("source_type"))==typ and str(r.get("source_id"))==str(oid)
        other_type=_type(r.get("target_type") if is_source else r.get("source_type"))
        other_id=r.get("target_id") if is_source else r.get("source_id")
        rel=_clean(r.get("relationship_type")).replace("_"," ").title()
        st.markdown(f"**{'→' if is_source else '←'} {rel}** · {object_label(other_type,other_id)}")
        if other_id and other_type in OBJECTS:
            drilldown_button(
                other_type,other_id,"Open linked object",
                key=f"{key_prefix}_ddrel_{oid}_{i}_{other_id}",
                use_container_width=True,
                key_prefix=key_prefix
            )

def _render_event_linked_objects(event_id,key_prefix="top"):
    links=_event_links_for_event(event_id)
    if not links:
        st.caption("No canonical event links recorded.")
        return

    enriched=[]
    for r in links:
        lt=_type(r.get("linked_type"))
        lid=r.get("linked_id")
        rec=object_record(lt,lid) if lt in OBJECTS else None
        enriched.append({
            "type":lt,
            "id":lid,
            "name":object_label(lt,lid),
            "relationship":_clean(r.get("relationship")).replace("_"," ").title(),
            "record":rec or {},
        })

    vessels=[x for x in enriched if x["type"]=="mobile_asset"]
    others=[x for x in enriched if x["type"]!="mobile_asset"]

    c1,c2,c3=st.columns(3)
    c1.metric("Linked objects",len(enriched))
    c2.metric("Vessels",len(vessels))
    c3.metric("Other objects",len(others))

    if vessels:
        vessel_tab, other_tab = st.tabs([
            f"Vessels ({len(vessels)})",
            f"Other linked objects ({len(others)})",
        ])

        with vessel_tab:
            vessel_rows=[]
            for x in vessels:
                r=x["record"]
                vessel_rows.append({
                    "Vessel":x["name"],
                    "IMO":_clean(r.get("imo")),
                    "MMSI":_clean(r.get("mmsi")),
                    "Flag":_clean(r.get("flag")),
                    "Type":_clean(r.get("subtype") or r.get("asset_type")).replace("_"," ").title(),
                    "Relationship":x["relationship"],
                    "Canonical ID":x["id"],
                })
            vdf=pd.DataFrame(vessel_rows)
            q=st.text_input(
                "Filter vessels",
                placeholder="name, IMO, flag, type…",
                key=f"{key_prefix}_vessel_filter_{event_id}",
            )
            if q.strip():
                mask=vdf.astype(str).apply(
                    lambda col: col.str.contains(q.strip(),case=False,na=False,regex=False)
                ).any(axis=1)
                vdf=vdf[mask].copy()

            st.dataframe(
                vdf,
                use_container_width=True,
                hide_index=True,
                height=min(650,120+35*min(len(vdf),15)),
            )

            if not vdf.empty:
                display_records=vdf.to_dict("records")
                pick=st.selectbox(
                    "Open vessel",
                    list(range(len(display_records))),
                    format_func=lambda i:
                        f"{display_records[i]['Vessel']}"
                        + (f" · IMO {display_records[i]['IMO']}" if display_records[i]["IMO"] else "")
                        + (f" · {display_records[i]['Flag']}" if display_records[i]["Flag"] else ""),
                    key=f"{key_prefix}_vessel_pick_{event_id}",
                )
                selected=display_records[pick]
                if st.button(
                    f"Open {selected['Vessel']} vessel profile",
                    key=f"{key_prefix}_vessel_open_{event_id}_{selected['Canonical ID']}",
                    type="primary",
                    use_container_width=True,
                ):
                    set_drilldown("mobile_asset",selected["Canonical ID"],selected["Vessel"])

        with other_tab:
            if not others:
                st.caption("No non-vessel objects linked to this event.")
            else:
                rows=[]
                for x in others:
                    r=x["record"]
                    rows.append({
                        "Type":OBJECTS.get(x["type"],{}).get("label",x["type"].replace("_"," ").title()),
                        "Name":x["name"],
                        "Relationship":x["relationship"],
                        "Country":_clean(r.get("hq_country") or r.get("country")),
                        "Canonical ID":x["id"],
                    })
                odf=pd.DataFrame(rows)
                st.dataframe(odf,use_container_width=True,hide_index=True)
                choices=[x for x in others if x["type"] in OBJECTS and x["id"]]
                if choices:
                    pick=st.selectbox(
                        "Open other linked object",
                        list(range(len(choices))),
                        format_func=lambda i:f"{choices[i]['name']} · {choices[i]['relationship']}",
                        key=f"{key_prefix}_other_pick_{event_id}",
                    )
                    selected=choices[pick]
                    if st.button(
                        f"Open {selected['name']}",
                        key=f"{key_prefix}_other_open_{event_id}_{selected['id']}",
                        use_container_width=True,
                    ):
                        set_drilldown(selected["type"],selected["id"],selected["name"])
    else:
        # No vessels: render the normal linked-object list.
        rows=[]
        for x in others:
            r=x["record"]
            rows.append({
                "Type":OBJECTS.get(x["type"],{}).get("label",x["type"].replace("_"," ").title()),
                "Name":x["name"],
                "Relationship":x["relationship"],
                "Country":_clean(r.get("hq_country") or r.get("country")),
                "Canonical ID":x["id"],
            })
        st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
        choices=[x for x in others if x["type"] in OBJECTS and x["id"]]
        if choices:
            pick=st.selectbox(
                "Open linked object",
                list(range(len(choices))),
                format_func=lambda i:f"{choices[i]['name']} · {choices[i]['relationship']}",
                key=f"{key_prefix}_linked_object_pick_{event_id}",
            )
            selected=choices[pick]
            if st.button(
                f"Open {selected['name']}",
                key=f"{key_prefix}_linked_object_open_{event_id}_{selected['id']}",
                use_container_width=True,
            ):
                set_drilldown(selected["type"],selected["id"],selected["name"])


def _render_events(typ,oid,key_prefix="top"):
    if typ=="event":
        _render_event_linked_objects(oid,key_prefix=key_prefix)
        return

    events=_event_rows_for_object(typ,oid)
    if not events:
        st.caption("No linked canonical events recorded.")
        return
    events=sorted(events,key=lambda x:str(x.get("start_date") or ""),reverse=True)

    # Table gives fast scan; selector/button gives drill-through without dozens of controls.
    table=[]
    for e in events[:100]:
        table.append({
            "Date":_clean(e.get("start_date")),
            "Severity":_clean(e.get("severity")),
            "Type":_clean(e.get("event_type")).replace("_"," ").title(),
            "Title":_clean(e.get("title")),
            "Relationship":_clean(e.get("_relationship")).replace("_"," ").title(),
            "Event ID":e.get("event_id"),
        })
    st.dataframe(pd.DataFrame(table),use_container_width=True,hide_index=True,height=min(520,90+35*min(len(table),12)))

    choices=[e for e in events[:100] if e.get("event_id")]
    if choices:
        pick=st.selectbox(
            "Open linked event",
            list(range(len(choices))),
            format_func=lambda i:f"{_clean(choices[i].get('start_date'))} · {_clean(choices[i].get('title'))}",
            key=f"{key_prefix}_event_pick_{oid}",
        )
        ev=choices[pick]
        if st.button(
            "Open selected event",
            key=f"{key_prefix}_event_open_{oid}_{ev.get('event_id')}",
            use_container_width=True,
        ):
            set_drilldown("event",ev.get("event_id"),ev.get("title"))


def render_drilldown(object_type,object_id,key_prefix="top"):
    typ=_type(object_type)
    rec=object_record(typ,object_id)
    if not rec:
        st.warning(f"No canonical {typ} record found for {object_id}.")
        return

    third_label="Linked Vessels & Objects" if typ=="event" else "Events & Intelligence"
    tabs=st.tabs(["Overview","Relationships",third_label,"Raw / Provenance"])
    with tabs[0]:
        _render_overview(rec,typ)
    with tabs[1]:
        _render_relationships(typ,object_id,key_prefix=key_prefix)
    with tabs[2]:
        _render_events(typ,object_id,key_prefix=key_prefix)
    with tabs[3]:
        st.json(rec)


def render_active_drilldown(location="top",expanded=True):
    restore_drilldown_from_query()
    typ=st.session_state.get("pc_drilldown_type")
    oid=st.session_state.get("pc_drilldown_id")
    if not typ or not oid:
        return False

    label=object_label(typ,oid)

    if location=="sidebar":
        with st.sidebar.expander(f"Selected · {label}",expanded=expanded):
            st.caption(f"{OBJECTS.get(typ,{}).get('label',typ)} · {oid}")
            c1,c2=st.columns(2)
            if c1.button("Trade",key=f"sidebar_dd_trade_{oid}",use_container_width=True):
                try: st.query_params["product"]="trade"
                except Exception: pass
                st.rerun()
            if c2.button("Intelligence",key=f"sidebar_dd_intel_{oid}",use_container_width=True):
                try: st.query_params["product"]="intelligence"
                except Exception: pass
                st.rerun()
            if st.button("Clear",key=f"sidebar_dd_clear_{oid}",use_container_width=True):
                clear_drilldown()
            st.caption("Full context opens at the top of the main workspace.")
        return True

    # Main/top workspace: this is deliberately rendered near the page header,
    # not at the bottom after the page's normal content.
    with st.container(border=True):
        top1,top2,top3,top4=st.columns([5,1,1,1])
        top1.markdown(f"### {html.escape(label)}")
        top1.caption(f"{OBJECTS.get(typ,{}).get('label',typ)} · canonical drill-down")
        if top2.button("Trade",key=f"top_dd_trade_{oid}",use_container_width=True):
            try: st.query_params["product"]="trade"
            except Exception: pass
            st.rerun()
        if top3.button("Intelligence",key=f"top_dd_intel_{oid}",use_container_width=True):
            try: st.query_params["product"]="intelligence"
            except Exception: pass
            st.rerun()
        if top4.button("✕ Close",key=f"top_dd_close_{oid}",use_container_width=True):
            clear_drilldown()
        render_drilldown(typ,oid,key_prefix="top")
    return True


def render_sidebar_search():
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Open canonical object")
    typ=st.sidebar.selectbox("Object type",["entity","asset","mobile_asset","event"],format_func=lambda x:OBJECTS[x]["label"],key="pc_dd_search_type")
    q=st.sidebar.text_input("Find by name / ID",key="pc_dd_search_text")
    if q.strip():
        cfg=OBJECTS[typ]; sb=_sb(); matches=[]
        if sb:
            try:
                matches=sb.table(cfg["table"]).select("*").eq(cfg["id"],q.strip()).limit(5).execute().data or []
            except Exception:
                matches=[]
            if not matches:
                try:
                    matches=sb.table(cfg["table"]).select("*").ilike(cfg["name"],f"%{q.strip()}%").limit(20).execute().data or []
                except Exception:
                    matches=[]
        if matches:
            idx=st.sidebar.selectbox("Matches",list(range(len(matches))),format_func=lambda i:f"{_clean(matches[i].get(cfg['name']))} · {_clean(matches[i].get(cfg['id']))}",key="pc_dd_match_pick")
            picked=matches[idx]
            if st.sidebar.button("Open drill-down",key="sidebar_pc_dd_open_search",use_container_width=True):
                set_drilldown(typ,picked.get(cfg["id"]),picked.get(cfg["name"]))
        else:
            st.sidebar.caption("No canonical match.")
    render_active_drilldown(location="sidebar",expanded=False)
