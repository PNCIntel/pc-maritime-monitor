"""P&C Sanctions query and report workspace.

Built on the shared terminal read model (migration 059) plus sanctions/screening tables.
"""
from __future__ import annotations

import html
import re
from datetime import date
from typing import Any

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components


REPORT_TYPES={
    "Sanctions Query Report":[
        "Executive Finding","Query Scope","Designation Status","Ownership / Control",
        "Vessel / Asset Exposure","Trade / Corridor Exposure","Linked Activity",
        "Evidence Assessment","Monitoring / Next Steps"
    ],
    "Counterparty Exposure Report":[
        "Executive Finding","Counterparty Identity","Designation / Screening Status",
        "Ownership / Control","Associated Companies / Assets","Trade Exposure",
        "Risk Assessment","Evidence","Recommended Follow-Up"
    ],
    "Vessel Sanctions Dossier":[
        "Executive Finding","Vessel Identity","Designation Status","Ownership / Management",
        "Flag / Registry / Aliases","Linked Activity","Port / Corridor Exposure",
        "Evidence","Monitoring / Next Steps"
    ],
    "Ownership & Control Assessment":[
        "Executive Finding","Subject Identity","Ownership Structure","Control Indicators",
        "Sanctioned / High-Risk Connections","Commercial Exposure","Evidence",
        "Assessment","Monitoring / Next Steps"
    ],
    "Regime / Jurisdiction Brief":[
        "Executive Finding","Regime / Authority","Current Designations","Affected Entities / Vessels",
        "Trade / Corridor Impact","Enforcement / Evasion Activity","Evidence","Monitoring / Next Steps"
    ],
}


def _clean(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v,(dict,list)):
        return str(v)
    return str(v).strip()


def _rpc_search(sb, q: str, limit: int=80) -> list[dict]:
    if not q.strip():
        return []
    try:
        rows=sb.rpc("pc_terminal_search",{"p_query":q.strip(),"p_limit":limit}).execute().data or []
    except Exception:
        return []
    # sanctions workbench still permits related trade/intelligence objects because exposure often
    # starts with a company/vessel/corridor rather than a designation record.
    allowed={"sanction","entity","mobile_asset","asset","event","corridor","document","programme","security_operation"}
    return [r for r in rows if _clean(r.get("object_type")) in allowed]


def _object_record(sb, typ: str, oid: str) -> dict:
    try:
        rows=(sb.table("pc_terminal_object_index").select("*")
              .eq("object_type",typ).eq("object_id",oid).limit(1).execute().data or [])
        return rows[0] if rows else {}
    except Exception:
        return {}


def _links(sb, typ: str, oid: str, limit: int=1000) -> list[dict]:
    out=[]
    try:
        out.extend((sb.table("pc_v_terminal_links").select("*")
                    .eq("source_type",typ).eq("source_id",oid).limit(limit).execute().data or []))
        out.extend((sb.table("pc_v_terminal_links").select("*")
                    .eq("target_type",typ).eq("target_id",oid).limit(limit).execute().data or []))
    except Exception:
        return []
    seen=set(); final=[]
    for r in out:
        k=_clean(r.get("link_key")) or repr(r)
        if k in seen: continue
        seen.add(k); final.append(r)
    return final


def _related_sanctions(sb, typ: str, oid: str, name: str="") -> list[dict]:
    rows=[]
    try:
        if typ=="sanction":
            rows=(sb.table("pc_sanctions_designations").select("*")
                  .eq("sanctions_designation_id",oid).limit(10).execute().data or [])
        elif typ=="entity":
            rows=(sb.table("pc_sanctions_designations").select("*")
                  .eq("entity_id",oid).limit(200).execute().data or [])
        elif typ=="mobile_asset":
            rows=(sb.table("pc_sanctions_designations").select("*")
                  .eq("mobile_asset_id",oid).limit(200).execute().data or [])
    except Exception:
        rows=[]
    if rows:
        return rows
    # fallback through 059 sanctions links
    out=[]
    for l in _links(sb,typ,oid):
        if _clean(l.get("relation_family"))!="sanctions":
            continue
        sid=_clean(l.get("source_id")) if _clean(l.get("source_type"))=="sanction" else _clean(l.get("target_id"))
        if sid:
            try:
                hit=(sb.table("pc_sanctions_designations").select("*")
                     .eq("sanctions_designation_id",sid).limit(5).execute().data or [])
                out.extend(hit)
            except Exception:
                pass
    seen=set(); final=[]
    for r in out:
        k=_clean(r.get("sanctions_designation_id")) or repr(r)
        if k in seen: continue
        seen.add(k); final.append(r)
    return final


def _screening_rows(sb, typ: str, oid: str, name: str) -> tuple[list[dict],list[dict]]:
    cases=[]; matches=[]
    # tables vary across deployments; query conservatively and fall back silently.
    if name:
        for col in ("submitted_name","subject_name","name"):
            try:
                x=(sb.table("pc_screening_cases").select("*").ilike(col,f"%{name}%").limit(100).execute().data or [])
                if x:
                    cases=x;break
            except Exception:
                pass
    try:
        if cases:
            ids=[_clean(x.get("screening_case_id")) for x in cases if x.get("screening_case_id")]
            for cid in ids[:50]:
                matches.extend((sb.table("pc_screening_matches").select("*")
                                .eq("screening_case_id",cid).limit(100).execute().data or []))
    except Exception:
        pass
    return cases,matches


def _events_from_links(sb, typ: str, oid: str) -> list[dict]:
    ids=[]
    for l in _links(sb,typ,oid):
        if _clean(l.get("source_type"))=="event":
            ids.append(_clean(l.get("source_id")))
        elif _clean(l.get("target_type"))=="event":
            ids.append(_clean(l.get("target_id")))
        elif l.get("event_id"):
            ids.append(_clean(l.get("event_id")))
    ids=list(dict.fromkeys(x for x in ids if x))
    out=[]
    for eid in ids[:100]:
        try:
            x=(sb.table("pc_events").select("*").eq("event_id",eid).limit(1).execute().data or [])
            out.extend(x)
        except Exception:
            pass
    return sorted(out,key=lambda x:_clean(x.get("start_date")),reverse=True)


def _urls(row: dict) -> list[str]:
    out=[]
    for k in ("source_url","url","article_url","reference_url"):
        v=row.get(k)
        if isinstance(v,str) and v.startswith(("http://","https://")):
            out.append(v)
    m=row.get("metadata") if isinstance(row.get("metadata"),dict) else {}
    for x in m.get("research_sources") or []:
        u=x.get("url") if isinstance(x,dict) else x
        if isinstance(u,str) and u.startswith(("http://","https://")):
            out.append(u)
    return list(dict.fromkeys(out))


def _display_label(r: dict) -> str:
    typ=_clean(r.get("object_type"))
    name=_clean(r.get("display_name")) or _clean(r.get("object_id"))
    sub=_clean(r.get("subtype"))
    country=_clean(r.get("country"))
    bits=[x for x in [typ.replace("_"," ").title(),sub,country] if x]
    return f"{name} · " + " · ".join(bits)


def _bundle(sb, selected: list[dict]) -> dict:
    designations=[]; links=[]; events=[]; cases=[]; matches=[]; evidence=[]
    objs=[]
    for s in selected:
        typ=_clean(s.get("object_type")); oid=_clean(s.get("object_id")); name=_clean(s.get("display_name"))
        rec=_object_record(sb,typ,oid)
        objs.append(rec or s)
        designations.extend(_related_sanctions(sb,typ,oid,name))
        links.extend(_links(sb,typ,oid,600))
        events.extend(_events_from_links(sb,typ,oid))
        c,m=_screening_rows(sb,typ,oid,name)
        cases.extend(c); matches.extend(m)
        for row in [rec or s]:
            evidence.extend(_urls(row))
    for row in designations+events:
        evidence.extend(_urls(row))

    def dedupe(rows,key):
        seen=set(); out=[]
        for r in rows:
            k=_clean(r.get(key)) or repr(r)
            if k in seen: continue
            seen.add(k); out.append(r)
        return out

    return {
        "objects":objs,
        "designations":dedupe(designations,"sanctions_designation_id"),
        "links":dedupe(links,"link_key"),
        "events":dedupe(events,"event_id"),
        "cases":dedupe(cases,"screening_case_id"),
        "matches":dedupe(matches,"screening_match_id"),
        "evidence":list(dict.fromkeys(evidence)),
    }


def _auto_sections(report_type: str, query: str, bundle: dict) -> dict:
    fields={k:"" for k in REPORT_TYPES[report_type]}
    objs=bundle["objects"]; des=bundle["designations"]; links=bundle["links"]; events=bundle["events"]
    names=[_clean(x.get("display_name") or (x.get("record_data") or {}).get("name") or x.get("object_id")) for x in objs]
    names=[x for x in names if x]

    finding=f"Query '{query}' returned {len(objs)} selected canonical object(s), {len(des)} designation record(s), {len(links)} linked relationship(s), and {len(events)} linked event(s)."
    fields["Executive Finding"]=finding

    if "Query Scope" in fields:
        fields["Query Scope"]="Selected objects: " + (", ".join(names) if names else "None")
    if "Subject Identity" in fields:
        fields["Subject Identity"]=", ".join(names)
    if "Counterparty Identity" in fields:
        fields["Counterparty Identity"]=", ".join(names)
    if "Vessel Identity" in fields:
        fields["Vessel Identity"]=", ".join(names)

    if des:
        lines=[]
        for d in des[:30]:
            lines.append(" · ".join(x for x in [
                _clean(d.get("designated_name") or d.get("subject_name") or d.get("name")),
                _clean(d.get("program") or d.get("regime")),
                _clean(d.get("authority")),
                _clean(d.get("designation_date")),
                _clean(d.get("status") or d.get("designation_status")),
            ] if x))
        txt="\n".join(lines)
        for k in ("Designation Status","Designation / Screening Status","Current Designations"):
            if k in fields: fields[k]=txt

    if links:
        own=[]
        trade=[]
        for l in links:
            fam=_clean(l.get("relation_family"))
            line=f"{_clean(l.get('source_name'))} — {_clean(l.get('relation_type'))} → {_clean(l.get('target_name'))}"
            if fam in {"relationship","portfolio","asset_role","sanctions"}:
                own.append(line)
            if fam in {"corridor_role","asset_role","event_context"}:
                trade.append(line)
        own_txt="\n".join(dict.fromkeys(own[:40]))
        trade_txt="\n".join(dict.fromkeys(trade[:40]))
        for k in ("Ownership / Control","Ownership Structure","Associated Companies / Assets","Ownership / Management"):
            if k in fields and own_txt: fields[k]=own_txt
        for k in ("Trade / Corridor Exposure","Trade Exposure","Commercial Exposure","Port / Corridor Exposure"):
            if k in fields and trade_txt: fields[k]=trade_txt

    if events:
        evtxt="\n\n".join(
            f"{_clean(e.get('start_date'))[:10]} · {_clean(e.get('title'))}: {_clean(e.get('description') or e.get('operational_impact') or e.get('commercial_impact'))}"
            for e in events[:20]
        )
        for k in ("Linked Activity","Enforcement / Evasion Activity"):
            if k in fields: fields[k]=evtxt

    return fields


def _build_html(report_type: str,title: str,report_date: date,query: str,summary: str,
                fields: dict,sources: list[str]) -> str:
    gold="#9b7a2c"; navy="#10213a"; line="#dfe6ef"; muted="#718096"
    parts=[f"""<div style="max-width:860px;margin:auto;background:#fff;color:#172033;font-family:Arial,Helvetica,sans-serif;line-height:1.55">
<div style="border-top:5px solid {gold};padding:24px 8px 15px">
<div style="font-size:11px;letter-spacing:2px;color:{gold};font-weight:700">POWER &amp; CORRIDORS SANCTIONS INTELLIGENCE</div>
<h1 style="font-size:30px;color:{navy};margin:8px 0">{html.escape(title)}</h1>
<div style="font-size:13px;color:{muted}">{html.escape(str(report_date))} · {html.escape(report_type)}</div>
<div style="font-size:13px;color:{muted};margin-top:4px"><b>Query:</b> {html.escape(query)}</div>
</div>"""]
    if summary:
        parts.append(f"<div style='padding:12px 14px;margin:8px;background:#f6f8fb;border:1px solid {line}'><b>Executive finding:</b> {html.escape(summary)}</div>")
    for name,val in fields.items():
        if not _clean(val): continue
        body="<br>".join(html.escape(x) for x in str(val).splitlines() if x.strip())
        parts.append(f"<section style='padding:9px 8px 14px;border-bottom:1px solid {line}'><h2 style='font-size:18px;color:{navy}'>{html.escape(name)}</h2><div>{body}</div></section>")
    if sources:
        parts.append("<section style='padding:12px 8px'><h2 style='font-size:18px;color:#10213a'>Sources</h2><ol>")
        for u in sources:
            parts.append(f"<li><a href='{html.escape(u)}'>{html.escape(u)}</a></li>")
        parts.append("</ol></section>")
    parts.append("</div>")
    return "".join(parts)


def _save(sb,report_type,title,report_date,query,summary,fields,bundle,status):
    row={
        "report_type":"sanctions_report",
        "report_title":title,
        "publication_date":str(report_date),
        "status":status,
        "template_key":report_type.lower().replace(" ","_").replace("/","_"),
        "executive_summary":summary or fields.get("Executive Finding") or None,
        "metadata":{
            "sanctions_report_type":report_type,
            "query":query,
            "selected_objects":[
                {"object_type":_clean(x.get("object_type")),"object_id":_clean(x.get("object_id")),"display_name":_clean(x.get("display_name"))}
                for x in bundle["objects"]
            ],
            "designation_count":len(bundle["designations"]),
            "link_count":len(bundle["links"]),
            "screening_case_count":len(bundle["cases"]),
            "screening_match_count":len(bundle["matches"]),
        },
    }
    rid=sb.table("pc_reports").insert(row).execute().data[0]["report_id"]
    for i,(name,val) in enumerate(fields.items(),1):
        if not _clean(val): continue
        sb.table("pc_report_sections").insert({
            "report_id":rid,
            "section_key":re.sub(r"[^a-z0-9]+","_",name.casefold()).strip("_"),
            "section_title":name,
            "sort_order":i,
            "section_summary":val,
            "metadata":{"sanctions_query":query},
        }).execute()

    # Preserve linked events as report stories and their sources.
    for i,e in enumerate(bundle["events"],1):
        story=sb.table("pc_report_stories").insert({
            "report_id":rid,
            "event_id":_clean(e.get("event_id")) or None,
            "headline":_clean(e.get("title")) or "Linked activity",
            "situation_update":_clean(e.get("description")) or None,
            "business_implications":_clean(e.get("commercial_impact")) or None,
            "assessment_impact":_clean(e.get("operational_impact")) or None,
            "sort_order":i,
            "ai_generated":False,
            "analyst_approved":False,
            "metadata":{"sanctions_query":query},
        }).execute().data[0]
        sid=story.get("report_story_id")
        if sid:
            for n,u in enumerate(_urls(e),1):
                sb.table("pc_report_story_sources").insert({
                    "report_story_id":sid,"source_url":u,"source_reference_number":n
                }).execute()
    return rid


def render_sanctions_report_area(sb, context=None):
    st.markdown("<div class='pc-k'>P&C SANCTIONS · QUERY & REPORT WORKSPACE</div>",unsafe_allow_html=True)
    st.markdown("## Sanctions Query & Report Studio")
    st.caption("Query the connected sanctions/trade graph, assemble exposure context, and produce a structured sanctions report.")

    seed_name=""
    if context and context[2]:
        rec=context[2]
        seed_name=_clean(rec.get("name") or rec.get("title") or rec.get("corridor_name"))

    q=st.text_input(
        "Query",
        value=seed_name,
        placeholder="IMO 9286281, Samadha, DP World, Russia, OFAC, Iran, dark fleet, UAE manager, Red Sea…",
        key="pc_sanctions_report_query"
    )

    c1,c2=st.columns([1.2,1.0])
    report_type=c1.selectbox("Report type",list(REPORT_TYPES),key="pc_sanctions_report_type")
    include_related=c2.checkbox("Include related trade / event context",value=True,key="pc_sanctions_include_related")

    results=_rpc_search(sb,q,100) if q.strip() else []
    if results:
        labels={_display_label(r):r for r in results}
        defaults=list(labels)[:1]
        selected_labels=st.multiselect("Query results to include",list(labels),default=defaults,key="pc_sanctions_query_results")
        selected=[labels[x] for x in selected_labels]
    else:
        selected=[]
        if q.strip():
            st.info("No indexed object matched this query.")

    bundle=_bundle(sb,selected) if selected else {"objects":[],"designations":[],"links":[],"events":[],"cases":[],"matches":[],"evidence":[]}

    if selected:
        m=st.columns(6)
        m[0].metric("Selected objects",len(bundle["objects"]))
        m[1].metric("Designations",len(bundle["designations"]))
        m[2].metric("Network links",len(bundle["links"]))
        m[3].metric("Linked events",len(bundle["events"]))
        m[4].metric("Screening cases",len(bundle["cases"]))
        m[5].metric("Screening matches",len(bundle["matches"]))

        tabs=st.tabs(["Designation / Network","Linked Activity","Screening","Evidence"])
        with tabs[0]:
            if bundle["designations"]:
                st.dataframe(pd.DataFrame(bundle["designations"]),hide_index=True,use_container_width=True,height=330)
            if bundle["links"]:
                view=pd.DataFrame([{
                    "Source":_clean(x.get("source_name")),
                    "Relationship":_clean(x.get("relation_type")),
                    "Target":_clean(x.get("target_name")),
                    "Family":_clean(x.get("relation_family")),
                    "Confidence":_clean(x.get("confidence")),
                } for x in bundle["links"]])
                st.dataframe(view,hide_index=True,use_container_width=True,height=360)
        with tabs[1]:
            if bundle["events"]:
                st.dataframe(pd.DataFrame([{
                    "Date":_clean(x.get("start_date"))[:10],
                    "Development":_clean(x.get("title")),
                    "Type":_clean(x.get("event_type")),
                    "Location":_clean(x.get("location")),
                } for x in bundle["events"]]),hide_index=True,use_container_width=True,height=360)
        with tabs[2]:
            if bundle["cases"]:
                st.dataframe(pd.DataFrame(bundle["cases"]),hide_index=True,use_container_width=True,height=300)
            if bundle["matches"]:
                st.dataframe(pd.DataFrame(bundle["matches"]),hide_index=True,use_container_width=True,height=300)
        with tabs[3]:
            for u in bundle["evidence"]:
                st.markdown("- "+u)

    auto_key=f"pc_sanctions_auto_{report_type}"
    if st.button("Build report from query",type="primary",disabled=not bool(selected),key="pc_sanctions_build"):
        vals=_auto_sections(report_type,q,bundle)
        for k,v in vals.items():
            if v:
                st.session_state[f"pc_sanctions_field_{report_type}_{k}"]=v
        if not st.session_state.get("pc_sanctions_report_title"):
            names=[_clean(x.get("display_name")) for x in selected if x.get("display_name")]
            st.session_state["pc_sanctions_report_title"]=f"{report_type}: " + (", ".join(names[:3]) or q)
        st.rerun()

    st.divider()
    st.markdown("### Report")
    c1,c2=st.columns([2.4,1.0])
    title=c1.text_input("Title",key="pc_sanctions_report_title")
    report_date=c2.date_input("Date",value=date.today(),key="pc_sanctions_report_date")
    summary=st.text_input("Executive finding / summary",key="pc_sanctions_report_summary")

    fields={}
    for field in REPORT_TYPES[report_type]:
        fields[field]=st.text_area(field,key=f"pc_sanctions_field_{report_type}_{field}",height=125)

    source_text=st.text_area("Sources",value="\n".join(bundle["evidence"]),key="pc_sanctions_report_sources",height=110)
    sources=[x.strip() for x in source_text.splitlines() if x.strip().startswith(("http://","https://"))]

    report_html=_build_html(report_type,title,report_date,q,summary,fields,sources)
    p1,p2=st.tabs(["Preview","HTML"])
    with p1:
        components.html(report_html,height=850,scrolling=True)
    with p2:
        st.code(report_html,language="html")
        st.download_button("Download sanctions report HTML",report_html,file_name="pc-sanctions-report.html",mime="text/html")

    a,b=st.columns(2)
    if a.button("Save draft",disabled=not bool(title.strip()),key="pc_sanctions_save_draft"):
        try:
            rid=_save(sb,report_type,title,report_date,q,summary,fields,bundle,"draft")
            st.success(f"Sanctions report saved: {rid}")
        except Exception as exc:
            st.error(f"Could not save sanctions report: {exc}")
    if b.button("Save for review",disabled=not bool(title.strip()),key="pc_sanctions_save_review"):
        try:
            rid=_save(sb,report_type,title,report_date,q,summary,fields,bundle,"review")
            st.success(f"Sanctions report sent to review: {rid}")
        except Exception as exc:
            st.error(f"Could not save sanctions report: {exc}")
