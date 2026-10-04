"""Power & Corridors report/brief production workspace.

Reusable inside the shared terminal. Uses the persistent pc_reports schema and
keeps reports tied to canonical events and source evidence.
"""
from __future__ import annotations

import html
import os
import re
from datetime import date
from typing import Any

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components


PRODUCTS={
    "Alert":{
        "report_type":"alert",
        "sections":["Current Situation","What Happened","What Remains Unconfirmed",
                    "Operational Impact","Trade / Commercial Impact","Assessment","Indicators to Watch"],
    },
    "Assessment":{
        "report_type":"assessment",
        "sections":["Executive Judgement","Key Judgements","Context","Analysis",
                    "Operational / Commercial Impact","Scenarios",
                    "Indicators / What Would Change the Judgement"],
    },
    "Monitoring":{
        "report_type":"monitoring",
        "sections":["Current Judgement","Why We Are Monitoring","Priority Indicators","Baseline",
                    "Trigger / Threshold","Assessment Impact","Secondary Indicators",
                    "Structural Indicators","What Would Change the Judgement"],
    },
    "Situation Report":{
        "report_type":"situation_report",
        "sections":["Executive Summary","Current Situation","Key Developments","Operational Impact",
                    "Trade / Commercial Impact","Key Actors / Assets",
                    "Outlook / Next 24–72 Hours","Indicators to Watch"],
    },
    "Daily / Multi-Event Brief":{
        "report_type":"brief",
        "sections":["Executive Summary","Priority Developments","Operational Impact",
                    "Commercial Exposure","Monitoring & Indicators","Look Ahead"],
    },
}


def _clean(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v,(list,dict)):
        return str(v)
    return str(v).strip()


def _meta(r: dict) -> dict:
    return r.get("metadata") if isinstance(r.get("metadata"),dict) else {}


def _urls_from_record(r: dict) -> list[str]:
    out=[]
    for k in ("source_url","url","article_url","reference_url"):
        v=r.get(k)
        if isinstance(v,str) and v.startswith(("http://","https://")):
            out.append(v)
    m=_meta(r)
    for k in ("source_url","url","article_url"):
        v=m.get(k)
        if isinstance(v,str) and v.startswith(("http://","https://")):
            out.append(v)
    for x in m.get("research_sources") or []:
        u=x.get("url") if isinstance(x,dict) else x
        if isinstance(u,str) and u.startswith(("http://","https://")):
            out.append(u)
    return list(dict.fromkeys(out))


def _event_summary(e: dict) -> str:
    return _clean(
        e.get("description") or e.get("current_situation") or e.get("what_happened")
        or e.get("operational_impact") or e.get("commercial_impact")
    )


def _api_key() -> str:
    try:
        return (
            st.secrets.get("OPENAI_API_KEY")
            or st.secrets.get("OPENAI_KEY")
            or os.getenv("OPENAI_API_KEY")
            or ""
        )
    except Exception:
        return os.getenv("OPENAI_API_KEY") or ""


def _terminal_search(sb, q: str, limit: int=60) -> list[dict]:
    if not q.strip():
        return []
    try:
        return sb.rpc("pc_terminal_search",{"p_query":q.strip(),"p_limit":limit}).execute().data or []
    except Exception:
        return []


def _index_record(sb, typ: str, oid: str) -> dict:
    try:
        rows=(sb.table("pc_terminal_object_index").select("*")
              .eq("object_type",typ).eq("object_id",oid).limit(1).execute().data or [])
        return rows[0] if rows else {}
    except Exception:
        return {}


def _index_links(sb, typ: str, oid: str, limit: int=500) -> list[dict]:
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


def _query_label(r: dict) -> str:
    name=_clean(r.get("display_name") or r.get("object_id"))
    bits=[_clean(r.get("object_type")).replace("_"," ").title(),
          _clean(r.get("subtype")),_clean(r.get("country"))]
    bits=[x for x in bits if x]
    return name + (" · " + " · ".join(bits) if bits else "")


def _linked_event_records(sb, links: list[dict]) -> list[dict]:
    ids=[]
    for l in links:
        if _clean(l.get("source_type"))=="event":
            ids.append(_clean(l.get("source_id")))
        elif _clean(l.get("target_type"))=="event":
            ids.append(_clean(l.get("target_id")))
        elif l.get("event_id"):
            ids.append(_clean(l.get("event_id")))
    ids=list(dict.fromkeys(x for x in ids if x))
    out=[]
    for eid in ids[:80]:
        try:
            rows=(sb.table("pc_events").select("*").eq("event_id",eid).limit(1).execute().data or [])
            out.extend(rows)
        except Exception:
            pass
    return out


def _ai_context_bundle(sb, lens: str, query: str, selected_objects: list[dict],
                       selected_events: list[dict], context: tuple[str,str,dict] | None) -> dict:
    objects=[]; links=[]; evidence=[]; linked_events=[]
    seeds=[]

    if context:
        typ,oid,rec=context
        seeds.append({"object_type":typ,"object_id":oid,"display_name":_clean(rec.get("name") or rec.get("title") or rec.get("corridor_name"))})

    seeds.extend(selected_objects)

    seen=set()
    for s in seeds:
        typ=_clean(s.get("object_type")); oid=_clean(s.get("object_id"))
        if not typ or not oid or (typ,oid) in seen:
            continue
        seen.add((typ,oid))
        rec=_index_record(sb,typ,oid)
        objects.append({
            "object_type":typ,
            "object_id":oid,
            "display_name":_clean(rec.get("display_name") or s.get("display_name") or oid),
            "subtype":_clean(rec.get("subtype") or s.get("subtype")),
            "country":_clean(rec.get("country") or s.get("country")),
            "region":_clean(rec.get("region")),
            "status":_clean(rec.get("status")),
            "record_data":rec.get("record_data") or {},
        })
        ls=_index_links(sb,typ,oid,500)
        links.extend(ls)
        rd=rec.get("record_data") or {}
        evidence.extend(_urls_from_record(rd))

    # linked events supplement manually selected canonical developments
    linked_events=_linked_event_records(sb,links)
    event_map={}
    for e in selected_events+linked_events:
        eid=_clean(e.get("event_id"))
        key=eid or (_clean(e.get("title"))+"|"+_clean(e.get("start_date")))
        if key and key not in event_map:
            event_map[key]=e
        evidence.extend(_urls_from_record(e))

    # Compact relationship representation to keep prompts useful.
    link_view=[]
    for l in links[:350]:
        link_view.append({
            "source":_clean(l.get("source_name") or l.get("source_id")),
            "source_type":_clean(l.get("source_type")),
            "relationship":_clean(l.get("relation_type")),
            "family":_clean(l.get("relation_family")),
            "target":_clean(l.get("target_name") or l.get("target_id")),
            "target_type":_clean(l.get("target_type")),
            "confidence":_clean(l.get("confidence")),
            "evidence_url":_clean(l.get("evidence_url")),
        })
        if _clean(l.get("evidence_url")).startswith(("http://","https://")):
            evidence.append(_clean(l.get("evidence_url")))

    event_view=[]
    for e in list(event_map.values())[:60]:
        event_view.append({
            "event_id":_clean(e.get("event_id")),
            "date":_clean(e.get("start_date")),
            "title":_clean(e.get("title")),
            "type":_clean(e.get("event_type") or e.get("event_nature")),
            "location":e.get("location"),
            "description":_clean(e.get("description")),
            "operational_impact":_clean(e.get("operational_impact")),
            "commercial_impact":_clean(e.get("commercial_impact")),
            "sources":_urls_from_record(e),
        })

    return {
        "lens":lens,
        "query":query,
        "objects":objects,
        "relationships":link_view,
        "events":event_view,
        "evidence_urls":list(dict.fromkeys(evidence))[:120],
    }


def _context_seed(context: tuple[str,str,dict] | None) -> dict:
    if not context:
        return {}
    typ,oid,rec=context
    if not typ or not oid or not rec:
        return {}
    title=_clean(rec.get("title") or rec.get("name") or rec.get("corridor_name"))
    region=_clean(rec.get("region") or rec.get("location") or rec.get("country") or rec.get("hq_country"))
    if isinstance(rec.get("location"),dict):
        region=_clean(rec["location"].get("name") or rec["location"].get("country") or rec["location"].get("region"))
    return {"type":typ,"id":oid,"title":title,"region":region,"record":rec}


def _recent_events(sb, limit=250):
    try:
        return (sb.table("pc_events").select("*").order("start_date",desc=True).limit(limit).execute().data or [])
    except Exception:
        return []


def _event_options(events: list[dict]) -> dict[str,dict]:
    out={}
    for e in events:
        eid=_clean(e.get("event_id"))
        if not eid:
            continue
        label=f"{_clean(e.get('start_date'))[:10]} · {_clean(e.get('title')) or eid}"
        out[label]=e
    return out


def _prefill_from_context(product: str, seed: dict, selected_events: list[dict]) -> dict:
    spec=PRODUCTS[product]
    fields={k:"" for k in spec["sections"]}
    all_events=list(selected_events)
    if seed.get("type")=="event":
        rec=seed.get("record") or {}
        if not any(_clean(x.get("event_id"))==seed.get("id") for x in all_events):
            all_events.insert(0,rec)

    if all_events:
        bullets=[]
        impacts=[]
        indicators=[]
        for e in all_events:
            title=_clean(e.get("title"))
            desc=_event_summary(e)
            if title:
                bullets.append(f"{title}: {desc}" if desc else title)
            impact=_clean(e.get("operational_impact") or e.get("commercial_impact"))
            if impact:
                impacts.append(impact)
            watch=_clean(e.get("monitoring_indicators") or e.get("indicators_to_watch"))
            if watch:
                indicators.append(watch)

        joined="\n\n".join(bullets[:12])
        impact_text="\n\n".join(dict.fromkeys(impacts))[:12000]
        indicator_text="\n\n".join(dict.fromkeys(indicators))[:12000]

        mapping={
            "Alert":{"Current Situation":joined,"What Happened":joined,
                     "Operational Impact":impact_text,"Indicators to Watch":indicator_text},
            "Assessment":{"Context":joined,"Operational / Commercial Impact":impact_text,
                          "Indicators / What Would Change the Judgement":indicator_text},
            "Monitoring":{"Why We Are Monitoring":joined,"Priority Indicators":indicator_text,
                          "Assessment Impact":impact_text},
            "Situation Report":{"Current Situation":joined,"Key Developments":joined,
                                "Operational Impact":impact_text,"Indicators to Watch":indicator_text},
            "Daily / Multi-Event Brief":{"Priority Developments":joined,"Operational Impact":impact_text,
                                         "Monitoring & Indicators":indicator_text},
        }
        for k,v in mapping.get(product,{}).items():
            if k in fields and v:
                fields[k]=v

    if seed and seed.get("type")!="event":
        context_line=f"Selected canonical context: {seed.get('title')} ({seed.get('type')})."
        for k in ("Context","Current Situation","Why We Are Monitoring","Executive Summary"):
            if k in fields and not fields[k]:
                fields[k]=context_line

    return fields


def _build_html(product: str,title: str,report_date: date,region: str,confidence: str,
                summary: str,fields: dict,sources: list[str]) -> str:
    gold="#a58028"; navy="#10213a"; line="#dce3ec"; muted="#66758a"
    parts=[f"""<div style="max-width:820px;margin:0 auto;background:#fff;color:#172033;font-family:Arial,Helvetica,sans-serif;line-height:1.58">
<div style="border-top:5px solid {gold};padding:25px 10px 16px">
<div style="font-size:11px;letter-spacing:2px;color:{gold};font-weight:700">POWER &amp; CORRIDORS INTELLIGENCE</div>
<h1 style="font-size:31px;line-height:1.15;color:{navy};margin:8px 0">{html.escape(title)}</h1>
<div style="font-size:13px;color:{muted}">{html.escape(str(report_date))} · {html.escape(region or 'Global')} · {html.escape(product)} · Confidence: {html.escape(confidence or 'Not stated')}</div>
</div>"""]
    if summary:
        parts.append(f"<div style='margin:8px 10px 20px;padding:13px 15px;background:#f6f8fb;border:1px solid {line}'><b>Executive line:</b> {html.escape(summary)}</div>")
    for name,value in fields.items():
        if not _clean(value):
            continue
        paras="".join(f"<p style='margin:0 0 10px'>{html.escape(p.strip())}</p>" for p in re.split(r"\n\s*\n",str(value)) if p.strip())
        parts.append(f"<section style='padding:7px 10px 15px;border-bottom:1px solid {line}'><h2 style='font-size:18px;color:{navy};margin:8px 0'>{html.escape(name)}</h2>{paras}</section>")
    if sources:
        parts.append("<section style='padding:14px 10px'><h2 style='font-size:18px;color:#10213a'>Sources</h2><ol>")
        for u in sources:
            parts.append(f"<li style='margin:0 0 6px'><a href='{html.escape(u)}'>{html.escape(u)}</a></li>")
        parts.append("</ol></section>")
    parts.append("</div>")
    return "".join(parts)


def _save_report(sb, product: str, title: str, report_date: date, region: str,
                 summary: str,fields: dict,events: list[dict],sources: list[str],
                 status: str, context: tuple[str,str,dict] | None):
    spec=PRODUCTS[product]
    metadata={"product":product,"confidence":st.session_state.get("pc_report_confidence") or None}
    if context:
        metadata["canonical_context"]={"type":context[0],"id":context[1]}
    row={
        "report_type":spec["report_type"],
        "report_title":title,
        "geography":region or None,
        "publication_date":str(report_date),
        "status":status,
        "template_key":product.lower().replace(" ","_").replace("/","_"),
        "executive_summary":summary or fields.get("Executive Summary") or fields.get("Executive Judgement") or None,
        "analyst_notes":None,
        "metadata":metadata,
    }
    rid=sb.table("pc_reports").insert(row).execute().data[0]["report_id"]

    section_ids={}
    for i,(name,value) in enumerate(fields.items(),1):
        if not _clean(value):
            continue
        sr=sb.table("pc_report_sections").insert({
            "report_id":rid,"section_key":re.sub(r"[^a-z0-9]+","_",name.casefold()).strip("_"),
            "section_title":name,"sort_order":i,"section_summary":value,
            "metadata":{"generated_from_terminal":True}
        }).execute().data[0]
        section_ids[name]=sr.get("report_section_id")

    event_story_ids=[]
    for i,e in enumerate(events,1):
        title_e=_clean(e.get("title")) or "Development"
        sid=section_ids.get("Priority Developments") or section_ids.get("Key Developments") or section_ids.get("Current Situation")
        story=sb.table("pc_report_stories").insert({
            "report_id":rid,"report_section_id":sid,
            "event_id":_clean(e.get("event_id")) or None,
            "headline":title_e,"situation_update":_event_summary(e) or None,
            "business_implications":_clean(e.get("commercial_impact")) or None,
            "assessment_impact":_clean(e.get("operational_impact")) or None,
            "sort_order":i,"ai_generated":False,"analyst_approved":status in {"approved","published"},
            "metadata":{"source":"terminal_report_studio"}
        }).execute().data[0]
        story_id=story.get("report_story_id")
        if story_id:
            event_story_ids.append((story_id,e))

    # Attach event-specific sources first.
    used=set()
    for story_id,e in event_story_ids:
        for n,u in enumerate(_urls_from_record(e),1):
            if (story_id,u) in used: continue
            used.add((story_id,u))
            sb.table("pc_report_story_sources").insert({
                "report_story_id":story_id,"source_url":u,"source_reference_number":n
            }).execute()

    # If the report has general sources but no event stories, create one report-level story.
    if sources and not event_story_ids:
        story=sb.table("pc_report_stories").insert({
            "report_id":rid,"headline":title,"situation_update":summary or None,
            "sort_order":1,"ai_generated":False,"analyst_approved":False,
            "metadata":{"source":"terminal_report_studio","general_source_story":True}
        }).execute().data[0]
        sid=story.get("report_story_id")
        if sid:
            for n,u in enumerate(sources,1):
                sb.table("pc_report_story_sources").insert({
                    "report_story_id":sid,"source_url":u,"source_reference_number":n
                }).execute()
    return rid


def render_report_studio(sb, context: tuple[str,str,dict] | None=None, mode: str="studio"):
    seed=_context_seed(context)
    if mode=="library":
        st.markdown("## Report Library")
        st.caption("Structured P&C reports saved in the persistent reporting layer.")
        try:
            rows=(sb.table("pc_reports").select("*").order("updated_at",desc=True).limit(300).execute().data or [])
        except Exception as exc:
            st.error(f"Report library unavailable: {exc}")
            return
        if rows:
            view=pd.DataFrame(rows)
            cols=[x for x in ["publication_date","report_type","report_title","geography","status","updated_at","report_id"] if x in view.columns]
            st.dataframe(view[cols],hide_index=True,use_container_width=True,height=520)
        else:
            st.info("No saved reports yet.")
        return

    title_text="Intelligence Brief Builder" if mode=="brief" else "Report Studio"
    st.markdown("<div class='pc-k'>P&C INTELLIGENCE · PUBLICATION WORKSPACE</div>",unsafe_allow_html=True)
    st.markdown("## "+title_text)
    st.caption("Build from canonical database context, preserve evidence, and save the finished product back into the reporting graph.")

    lens="trade" if mode=="brief" else "intelligence"
    query=st.text_input(
        "Query / analytical question",
        value=seed.get("title","") if seed else "",
        placeholder=("AD Ports Brazil acquisition, Middle Corridor capacity, freight disruption..." if lens=="trade"
                     else "Hormuz escalation, Red Sea shipping risk, regional disruption, actor network..."),
        key=f"pc_report_query_{mode}"
    )
    query_results=_terminal_search(sb,query,80) if query.strip() else []
    selected_objects=[]
    if query_results:
        labels={_query_label(r):r for r in query_results}
        default_labels=list(labels)[:1]
        picked=st.multiselect(
            "Canonical objects from query",
            list(labels),
            default=default_labels,
            key=f"pc_report_query_objects_{mode}",
            help="Selected objects feed their linked companies, assets, corridors, events and evidence into the draft."
        )
        selected_objects=[labels[x] for x in picked]

    product_options=list(PRODUCTS)
    default_idx=product_options.index("Daily / Multi-Event Brief") if mode=="brief" else 0
    product=st.selectbox("Product",product_options,index=default_idx,key=f"pc_report_product_{mode}")
    spec=PRODUCTS[product]

    events=_recent_events(sb,300)
    opts=_event_options(events)

    seed_event_labels=[]
    if seed.get("type")=="event":
        for label,e in opts.items():
            if _clean(e.get("event_id"))==seed.get("id"):
                seed_event_labels=[label];break

    selected_labels=st.multiselect(
        "Canonical developments to include",
        list(opts),
        default=seed_event_labels,
        key=f"pc_report_events_{mode}",
        help="These remain linked to the saved report as canonical event IDs."
    )
    selected=[opts[x] for x in selected_labels]

    if seed:
        st.info(f"Current terminal context: {seed.get('title')} · {seed.get('type')}")

    prefill_key=f"pc_report_prefill_{mode}_{product}"
    cauto1,cauto2=st.columns(2)
    if cauto1.button("Populate facts from selected data",key=f"pc_report_populate_{mode}",use_container_width=True):
        vals=_prefill_from_context(product,seed,selected)
        for k,v in vals.items():
            if v:
                st.session_state[f"pc_report_field_{mode}_{product}_{k}"]=v
        if seed.get("title") and not st.session_state.get(f"pc_report_title_{mode}"):
            st.session_state[f"pc_report_title_{mode}"]=seed["title"]
        if seed.get("region") and not st.session_state.get(f"pc_report_region_{mode}"):
            st.session_state[f"pc_report_region_{mode}"]=seed["region"]
        st.rerun()

    if cauto2.button("AI draft from connected data",type="primary",key=f"pc_report_ai_draft_{mode}",use_container_width=True):
        try:
            from pc_report_ai import draft_report
            bundle=_ai_context_bundle(sb,lens,query,selected_objects,selected,context)
            result=draft_report(
                _api_key(),lens,product,spec["sections"],query,bundle,
                title_hint=seed.get("title","")
            )
            if result.get("title"):
                st.session_state[f"pc_report_title_{mode}"]=result["title"]
            if result.get("executive_line"):
                st.session_state[f"pc_report_summary_{mode}"]=result["executive_line"]
            if result.get("confidence") in {"Low","Medium","Moderate","High"}:
                st.session_state["pc_report_confidence"]=result["confidence"]
            for k,v in (result.get("sections") or {}).items():
                if k in spec["sections"] and _clean(v):
                    st.session_state[f"pc_report_field_{mode}_{product}_{k}"]=_clean(v)
            st.session_state[f"pc_report_ai_gaps_{mode}"]=result.get("gaps") or []
            st.session_state[f"pc_report_ai_bundle_{mode}"]=bundle
            st.rerun()
        except Exception as exc:
            st.error(f"AI drafting failed: {exc}")

    gaps=st.session_state.get(f"pc_report_ai_gaps_{mode}") or []
    if gaps:
        with st.expander("AI-identified gaps / unconfirmed points"):
            for g in gaps:
                st.markdown("- "+_clean(g))

    c1,c2,c3,c4=st.columns([2.3,1.0,1.0,1.0])
    report_title=c1.text_input("Headline",value=seed.get("title",""),key=f"pc_report_title_{mode}")
    report_date=c2.date_input("Date",value=date.today(),key=f"pc_report_date_{mode}")
    region=c3.text_input("Geography",value=seed.get("region",""),key=f"pc_report_region_{mode}")
    confidence=c4.selectbox("Confidence",["","Low","Medium","Moderate","High"],key="pc_report_confidence")

    summary=st.text_input("Executive line / 14-word summary",key=f"pc_report_summary_{mode}")

    st.markdown("### Structured analysis")
    fields={}
    for field in spec["sections"]:
        fields[field]=st.text_area(
            field,
            key=f"pc_report_field_{mode}_{product}_{field}",
            height=120 if field not in {"Analysis","Key Developments","Priority Developments"} else 170
        )

    source_urls=[]
    for e in selected:
        source_urls.extend(_urls_from_record(e))
    if seed.get("type")=="event":
        source_urls.extend(_urls_from_record(seed.get("record") or {}))
    ai_bundle=st.session_state.get(f"pc_report_ai_bundle_{mode}") or {}
    source_urls.extend(ai_bundle.get("evidence_urls") or [])
    source_urls=list(dict.fromkeys(source_urls))

    st.markdown("### Evidence")
    default_sources="\n".join(source_urls)
    source_text=st.text_area("Source URLs — canonical event evidence is preloaded when available",
                             value=default_sources,key=f"pc_report_sources_{mode}",height=110)
    sources=[x.strip() for x in source_text.splitlines() if x.strip().startswith(("http://","https://"))]

    web_html=_build_html(product,report_title,report_date,region,confidence,summary,fields,sources)
    tabs=st.tabs(["Preview","HTML","Evidence / linked events"])
    with tabs[0]:
        components.html(web_html,height=850,scrolling=True)
    with tabs[1]:
        st.code(web_html,language="html")
        st.download_button("Download HTML",web_html,file_name=f"pc-{spec['report_type']}.html",mime="text/html",
                           key=f"pc_report_download_{mode}")
    with tabs[2]:
        if selected:
            st.dataframe(pd.DataFrame([{
                "Date":_clean(x.get("start_date"))[:10],"Development":_clean(x.get("title")),
                "Event ID":_clean(x.get("event_id")),"Sources":len(_urls_from_record(x))
            } for x in selected]),hide_index=True,use_container_width=True)
        if sources:
            for u in sources:
                st.markdown("- "+u)

    a,b,c=st.columns(3)
    if a.button("Save draft",type="primary",disabled=not bool(report_title.strip()),key=f"pc_report_save_draft_{mode}"):
        try:
            rid=_save_report(sb,product,report_title,report_date,region,summary,fields,selected,sources,"draft",context)
            st.success(f"Draft saved: {rid}")
        except Exception as exc:
            st.error(f"Could not save report: {exc}")

    if b.button("Save for review",disabled=not bool(report_title.strip()),key=f"pc_report_save_review_{mode}"):
        try:
            rid=_save_report(sb,product,report_title,report_date,region,summary,fields,selected,sources,"review",context)
            st.success(f"Saved for review: {rid}")
        except Exception as exc:
            st.error(f"Could not save report: {exc}")

    if c.button("Clear report form",key=f"pc_report_clear_{mode}"):
        prefixes=(f"pc_report_field_{mode}_",f"pc_report_title_{mode}",f"pc_report_region_{mode}",
                  f"pc_report_summary_{mode}",f"pc_report_sources_{mode}",f"pc_report_events_{mode}",
                  f"pc_report_query_{mode}",f"pc_report_query_objects_{mode}",f"pc_report_ai_gaps_{mode}",
                  f"pc_report_ai_bundle_{mode}")
        for k in list(st.session_state):
            if any(k.startswith(p) for p in prefixes):
                del st.session_state[k]
        st.rerun()
