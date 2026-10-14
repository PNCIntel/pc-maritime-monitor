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
    for x in (m.get("research_sources") or []) + (m.get("source_urls") or []) + (m.get("sources") or []):
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
    seeds.extend({"object_type":"event","object_id":_clean(e.get("event_id")),"display_name":_clean(e.get("title"))} for e in selected_events if e.get("event_id"))

    seen=set()
    for s in seeds:
        typ=_clean(s.get("object_type")); oid=_clean(s.get("object_id"))
        if not typ or not oid or (typ,oid) in seen:
            continue
        seen.add((typ,oid))
        rec=_index_record(sb,typ,oid) or s
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


def _assemble_evidence(sb, lens, selected_events, selected_objects, context):
    """Build traceable factual blocks before asking AI for prose; no invented graph edges."""
    events={e["event_id"]:e for e in selected_events if e.get("event_id")}
    objects={}
    for o in selected_objects:
        typ=_clean(o.get("object_type")); oid=_clean(o.get("object_id"))
        if typ and oid: objects[(typ,oid)]=o
    if context and context[0]!="event":
        typ,oid,rec=context
        objects[(typ,oid)]={"object_type":typ,"object_id":oid,"record_data":rec}
    issues=[]; sources=[]
    def fetch(table, column, value, limit=200):
        try:
            return sb.table(table).select("*").eq(column,value).limit(limit).execute().data or []
        except Exception as exc:
            issues.append(table+": "+str(exc)[:130])
            return []
    def add_object(typ,oid):
        if not oid or (typ,oid) in objects: return
        tables={"mobile_asset":("pc_mobile_assets","mobile_asset_id"),
                "entity":("pc_entities","entity_id"),"asset":("pc_assets","asset_id")}
        if typ not in tables:return
        table,key=tables[typ]
        result=fetch(table,key,oid,1)
        if result:objects[(typ,oid)]={"object_type":typ,"object_id":oid,"record_data":result[0]}
    # Intelligence is event-led: resolve explicitly linked objects first.
    if lens=="intelligence":
        for eid,e in list(events.items()):
            sources.extend(_urls_from_record(e))
            for l in fetch("pc_event_entity_links","event_id",eid):
                add_object("entity",l.get("entity_id"))
            for l in fetch("pc_event_asset_links","event_id",eid):
                add_object("asset",l.get("asset_id"))
            # Current event IDs may carry canonical vessel identities in structured metadata.
            for key in ("mobile_asset_id","vessel_id","linked_mobile_asset_id"):
                if _meta(e).get(key):add_object("mobile_asset",_meta(e)[key])
            for l in fetch("pc_event_links","event_id",eid):
                typ=_clean(l.get("linked_type")).lower()
                if typ=="vessel":typ="mobile_asset"
                add_object(typ,l.get("linked_id"))
            # Resolve a named vessel in the incident title when its IMO was omitted.
            # This is a candidate identity match, never evidence of ownership.
            title=_clean(e.get("title"))
            for vessel_name in re.findall(r"\\b(?:DF PEAK)\\b",title,flags=re.I):
                try:
                    candidates=(sb.table("pc_mobile_assets").select("*").ilike("name",vessel_name).limit(10).execute().data or [])
                    if len(candidates)==1:add_object("mobile_asset",candidates[0]["mobile_asset_id"])
                    elif len(candidates)>1:issues.append("Ambiguous vessel name in event: "+vessel_name)
                except Exception as exc:issues.append("vessel name lookup: "+str(exc)[:130])
            # IMO evidence fallback is an identity lookup, not an inferred relationship.
            blob=str(_meta(e))+" "+_clean(e.get("description"))+" "+_clean(e.get("title"))
            for imo in set(re.findall(r"(?<!\d)\d{7}(?!\d)",blob)):
                for r in fetch("pc_mobile_assets","imo",imo,10):
                    add_object("mobile_asset",r.get("mobile_asset_id"))
    else:
        # Trade is object-led; include linked production events as developments.
        for typ,oid in list(objects):
            for l in _index_links(sb,typ,oid):
                other_typ=other_id=None
                if l.get("source_type")==typ and l.get("source_id")==oid:
                    other_typ,other_id=l.get("target_type"),l.get("target_id")
                elif l.get("target_type")==typ and l.get("target_id")==oid:
                    other_typ,other_id=l.get("source_type"),l.get("source_id")
                if other_typ=="event" and other_id:
                    for e in fetch("pc_events","event_id",other_id,1):
                        if not _horizon_event(e):events[e["event_id"]]=e
                elif other_typ in ("mobile_asset","asset","entity"):add_object(other_typ,other_id)
    blocks=[]; vessel_rows=[]; history_rows=[]; corporate_rows=[]; sanctions_rows=[]
    for (typ,oid),o in list(objects.items())[:100]:
        rec=o.get("record_data") or {}
        if not rec:
            table,key={"mobile_asset":("pc_mobile_assets","mobile_asset_id"),
                "entity":("pc_entities","entity_id"),"asset":("pc_assets","asset_id")}.get(typ,(None,None))
            if table:
                rows=fetch(table,key,oid,1)
                rec=rows[0] if rows else {}
        sources.extend(_urls_from_record(rec))
        if typ=="mobile_asset" and rec:
            vessel_rows.append({"Name":_clean(rec.get("name")),"IMO":_clean(rec.get("imo")),
                "Flag":_clean(rec.get("flag")),"Registered owner":_clean(rec.get("owner_entity_id")),
                "ISM manager":_clean(rec.get("manager_entity_id")),"Status":_clean(rec.get("status"))})
            meta=_meta(rec)
            for u in meta.get("identity_sources",[]) if isinstance(meta.get("identity_sources"),list) else []:
                if isinstance(u,str) and u.startswith(("https://","http://")):sources.append(u)
            histories=meta.get("identity_history") or meta.get("name_history") or []
            for h in histories if isinstance(histories,list) else []:
                if isinstance(h,dict):
                    history_rows.append({"Date":_clean(h.get("date") or h.get("valid_from") or h.get("date_precision")),
                        "Development":_clean(h.get("name"))+" — "+_clean(h.get("role")),
                        "Record":oid,"Source":_clean(h.get("source"))})
            for role,col in (("Registered owner","owner_entity_id"),("Operator","operator_entity_id"),("Manager","manager_entity_id")):
                if rec.get(col):
                    corporate_rows.append({"Record":_clean(rec.get("name")),"Role":role,
                        "Linked ID":_clean(rec.get(col)),"Date":_clean(rec.get("as_of")),"Evidence":"Current vessel record"})
            for l in fetch("pc_sanctions_links","linked_id",oid):
                if l.get("linked_type")!="mobile_asset":continue
                did=l.get("sanctions_designation_id")
                for d in fetch("pc_sanctions_designations","sanctions_designation_id",did,1) if did else []:
                    sanctions_rows.append({"Authority":_clean(d.get("authority") or d.get("jurisdiction")),
                        "Designation":_clean(d.get("source_external_id") or did),
                        "Date":_clean(d.get("effective_date") or d.get("designation_date")),
                        "Status":_clean(d.get("status")),"Record":oid})
    exposure_rows=[]
    for (typ,oid),o in list(objects.items())[:100]:
        rec=o.get("record_data") or {}
        if typ not in ("asset","entity") or not rec:continue
        exposure_rows.append({"Name":_clean(rec.get("name")),"Type":_clean(rec.get("asset_type") or rec.get("entity_type")),
          "Location":_clean(rec.get("region_city") or rec.get("country") or rec.get("hq_country")),
          "Record":oid,"Record status":_clean(rec.get("record_status"))})
    contested_rows=[]
    for eid,e in events.items():
        value=_clean(e.get("verification_status") or _meta(e).get("claim_status")).casefold()
        if any(x in value for x in ("reported","unconfirmed","disputed","claimed","unknown")):
            contested_rows.append({"Date":_clean(e.get("start_date"))[:10],"Claim":_clean(e.get("title")),
                "Verification":value,"Event ID":eid,"Sources":"; ".join(_urls_from_record(e))})
    def table(title,preset,rows,cols=None):
        if rows:
            b=_new_block("Asset table",title,rows=rows,preset=preset)
            if cols:b["columns"]=cols
            blocks.append(b)
    timeline=[{"Date":_clean(e.get("start_date"))[:10],"Development":_clean(e.get("title")),
               "Record":_clean(eid),"Source":"; ".join(_urls_from_record(e))} for eid,e in events.items()]
    timeline.extend(history_rows)
    timeline.sort(key=lambda r:r["Date"] or "0000")
    table("Connected events and history","Custom",timeline,["Date","Development","Record","Source"])
    table("Vessels linked to developments","Vessels",vessel_rows)
    table("Recorded corporate roles","Custom",corporate_rows,["Record","Role","Linked ID","Date","Evidence"])
    table("Official sanctions records","Custom",sanctions_rows,["Authority","Designation","Date","Status","Record"])
    if lens=="intelligence":
        table("Connected facilities and organisations","Custom",exposure_rows,["Name","Type","Location","Record","Record status"])
        table("Reported or contested developments","Custom",contested_rows,["Date","Claim","Verification","Event ID","Sources"])
    sources.extend(u for e in events.values() for u in _urls_from_record(e))
    return {"blocks":blocks,"events":list(events.values()),"objects":list(objects.values()),
            "counts":{"events":len(events),"objects":len(objects),"vessels":len(vessel_rows),
                      "history":len(history_rows),"corporate_roles":len(corporate_rows),
                      "sanctions":len(sanctions_rows),"exposure":len(exposure_rows),
                      "contested":len(contested_rows),"sources":len(set(sources))},
            "sources":list(dict.fromkeys(sources)),"issues":list(dict.fromkeys(issues))}


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



def _query_discovery(sb, query: str) -> tuple[list[dict], list[dict]]:
    """Production event and named-object lookup, independent of the terminal index."""
    normalized=query.casefold().replace("réunion","reunion").replace("french","france")
    terms=[t for t in re.findall(r"[A-Za-zÀ-ÿ0-9_]+",normalized) if len(t)>=2
           and t not in {"and","the","with","about","report","story","stories","of","in"}][:8]
    events={}; objects={}
    for term in terms:
        aliases={"reunion":["reunion","réunion"],"france":["france","french"],"panama":["panama","panamanian"],"df":["df peak"]}
        search_terms=aliases.get(term,[term])
        for safe in search_terms:
            for col in ("event_id","title","description"):
                try:
                    rows=(sb.table("pc_events").select("*").ilike(col,"%"+safe+"%")
                          .order("start_date",desc=True).limit(100).execute().data or [])
                    for e in rows:
                        if e.get("event_id") and not _horizon_event(e): events[e["event_id"]]=e
                except Exception:
                    pass
        for table,typ,pk in (("pc_mobile_assets","mobile_asset","mobile_asset_id"),
                              ("pc_assets","asset","asset_id"),
                              ("pc_entities","entity","entity_id")):
            try:
                rows=(sb.table(table).select("*").ilike("name","%"+safe+"%").limit(25).execute().data or [])
                for r in rows:
                    if r.get(pk):
                        oid=str(r[pk])
                        objects[(typ,oid)]={"object_type":typ,"object_id":oid,
                          "display_name":_clean(r.get("name")),"subtype":_clean(r.get("subtype")),
                          "country":_clean(r.get("country") or r.get("flag") or r.get("hq_country")),
                          "record_data":r}
            except Exception:
                pass
    ranked=sorted(events.values(),key=lambda e:(
        sum(t in (" ".join([_clean(e.get("event_id")),_clean(e.get("title")),
                           _clean(e.get("description"))]).casefold()) for t in terms),
        _clean(e.get("start_date"))),reverse=True)
    return ranked[:180],list(objects.values())[:100]


def _horizon_event(e: dict) -> bool:
    """Forward-looking horizon/watch observations are not historical report developments."""
    values=[e.get("event_nature"),e.get("event_family"),e.get("event_type"),
            e.get("record_status"),_meta(e).get("source_table"),_meta(e).get("record_kind")]
    return any("horizon" in _clean(v).casefold() for v in values)


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


BLOCK_TYPES=("Narrative","Asset table","Chronology","Analysis","Monitoring","References")
TABLE_PRESETS={
    "Vessels":["Name","IMO","Flag","Registered owner","ISM manager","Status"],
    "Aviation":["Name","Identifier","Operator","Country","Status"],
    "Cyber":["Incident","Affected entity","System","Date","Status"],
    "Infrastructure":["Facility","Type","Operator","Location","Status"],
    "Investment":["Investor","Company / asset","Relationship","Date","Status"],
    "Custom":["Item","Identifier","Owner / operator","Location","Status"],
}

def _new_block(kind="Narrative",title="",body="",rows=None,preset="Custom"):
    import uuid
    return {"id":uuid.uuid4().hex[:12],"kind":kind,"title":title or kind,
            "body":body,"preset":preset,"rows":rows or []}

def _asset_table_rows(objects, preset):
    records=[o.get("record_data") or {} for o in objects]
    rows=[]
    for r in records:
        typ=_clean(r.get("asset_type")).casefold()
        if preset=="Vessels" and not (r.get("imo") or typ in ("vessel","ship","tanker")):
            continue
        if preset=="Vessels":
            rows.append({"Name":_clean(r.get("name")),"IMO":_clean(r.get("imo")),
              "Flag":_clean(r.get("flag")),"Registered owner":_clean(r.get("owner_name") or r.get("owner_entity_id")),
              "ISM manager":_clean(r.get("manager_name") or r.get("manager_entity_id")),
              "Status":_clean(r.get("status"))})
        elif preset=="Infrastructure":
            rows.append({"Facility":_clean(r.get("name")),"Type":_clean(r.get("asset_type")),
             "Operator":_clean(r.get("operator_name") or r.get("operator_entity_id")),
             "Location":_clean(r.get("region_city") or r.get("country")),"Status":_clean(r.get("status"))})
    return rows

def _vessels_for_report(sb, events):
    imos=set()
    for e in events:
        imos.update(re.findall(r"(?<!\d)\d{7}(?!\d)",str(_meta(e))+" "+_clean(e.get("description"))))
    rows=[]
    for imo in sorted(imos):
        try:
            rows.extend(sb.table("pc_mobile_assets").select("*").eq("imo",imo).execute().data or [])
        except Exception: pass
    ids={r.get(k) for r in rows for k in ("owner_entity_id","manager_entity_id") if r.get(k)}
    names={}
    if ids:
        try:
            names={r["entity_id"]:r["name"] for r in (sb.table("pc_entities").select("entity_id,name").in_("entity_id",list(ids)).execute().data or [])}
        except Exception: pass
    return [{"Name":_clean(r.get("name")),"IMO":_clean(r.get("imo")),"Flag":_clean(r.get("flag")),
      "Registered owner":names.get(r.get("owner_entity_id"),"Not established"),
      "ISM manager":names.get(r.get("manager_entity_id"),"Not established"),
      "Status":_clean(r.get("status"))} for r in rows]


def _render_blocks(blocks, sources, gold="#a58028", navy="#10213a", line="#dce3ec"):
    parts=[]
    for b in blocks:
        title=html.escape(_clean(b.get("title")))
        if b.get("kind")=="Asset table":
            preset=b.get("preset") if b.get("preset") in TABLE_PRESETS else "Custom"
            columns=b.get("columns") or TABLE_PRESETS[preset]
            rows=b.get("rows") or []
            table="<table style='border-collapse:collapse;width:100%;font-size:13px'><thead><tr>"
            table+="".join("<th style='text-align:left;border-bottom:2px solid #a58028;padding:7px'>"+html.escape(c)+"</th>" for c in columns)
            table+="</tr></thead><tbody>"
            for row in rows:
                table+="<tr>"+"".join("<td style='vertical-align:top;border-bottom:1px solid #dce3ec;padding:7px'>"+html.escape(_clean(row.get(c)) or "Not established")+"</td>" for c in columns)+"</tr>"
            table+="</tbody></table>"
            body=table if rows else "<p>No verified records added to this table.</p>"
        else:
            body="".join("<p style='margin:0 0 13px'>"+html.escape(p.strip())+"</p>" for p in re.split(r"\\n\\s*\\n",_clean(b.get("body"))) if p.strip())
            for n in range(len(sources),0,-1):
                body=body.replace("["+str(n)+"]","<sup><a href='#ref-"+str(n)+"'>["+str(n)+"]</a></sup>")
        parts.append("<section style='padding:10px;border-bottom:1px solid "+line+"'><h2 style='font-size:18px;color:"+navy+"'>"+title+"</h2>"+body+"</section>")
    return "".join(parts)


def _build_html(product: str,title: str,report_date: date,region: str,confidence: str,
                summary: str,fields: dict,sources: list[str],blocks=None) -> str:
    gold="#a58028"; navy="#10213a"; line="#dce3ec"; muted="#66758a"
    parts=[f"""<div style="max-width:820px;margin:0 auto;background:#fff;color:#172033;font-family:Arial,Helvetica,sans-serif;line-height:1.58">
<div style="border-top:5px solid {gold};padding:25px 10px 16px">
<div style="font-size:11px;letter-spacing:2px;color:{gold};font-weight:700">POWER &amp; CORRIDORS INTELLIGENCE</div>
<h1 style="font-size:31px;line-height:1.15;color:{navy};margin:8px 0">{html.escape(title)}</h1>
<div style="font-size:13px;color:{muted}">{html.escape(str(report_date))} · {html.escape(region or 'Global')} · {html.escape(product)} · Confidence: {html.escape(confidence or 'Not stated')}</div>
</div>"""]
    if summary:
        parts.append(f"<div style='margin:8px 10px 20px;padding:13px 15px;background:#f6f8fb;border:1px solid {line}'><b>Executive line:</b> {html.escape(summary)}</div>")
    def _render_citations(raw: str) -> str:
        escaped=html.escape(raw)
        def cite(m):
            n=int(m.group(1))
            if not 1 <= n <= len(sources):
                return html.escape(m.group(0))
            return "<sup><a href='#ref-"+str(n)+"'>["+str(n)+"]</a></sup>"
        return re.sub(r"\[(\d{1,3})\]",cite,escaped)

    if blocks:
        parts.append(_render_blocks(blocks,sources))
    for name,value in ({} if blocks else fields).items():
        if not _clean(value):
            continue
        paras="".join("<p style='margin:0 0 13px'>"+_render_citations(p.strip()).replace("\n","<span style='display:block;height:5px'></span>")+"</p>" for p in re.split(r"\n\s*\n",str(value)) if p.strip())
        parts.append(f"<section style='padding:7px 10px 15px;border-bottom:1px solid {line}'><h2 style='font-size:18px;color:{navy};margin:8px 0'>{html.escape(name)}</h2>{paras}</section>")
    if sources:
        parts.append("<section style='padding:14px 10px'><h2 style='font-size:18px;color:#10213a'>Sources</h2><ol>")
        for n,u in enumerate(sources,1):
            parts.append(f"<li id='ref-{n}' style='margin:0 0 9px'><a href='{html.escape(u,quote=True)}' target='_blank' rel='noopener noreferrer'>{html.escape(u)}</a></li>")
        parts.append("</ol></section>")
    parts.append("</div>")
    return "".join(parts)


def _save_report(sb, product: str, title: str, report_date: date, region: str,
                 summary: str,fields: dict,events: list[dict],sources: list[str],
                 status: str, context: tuple[str,str,dict] | None, blocks=None):
    spec=PRODUCTS[product]
    metadata={"product":product,"confidence":st.session_state.get("pc_report_confidence") or None}
    if blocks is not None:
        metadata["editor_blocks"]=blocks
        metadata["editor_version"]=2
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
    save_fields=({b.get("title") or b.get("kind"): (b.get("body") if b.get("kind")!="Asset table" else str(b.get("rows") or [])) for b in blocks} if blocks else fields)
    for i,(name,value) in enumerate(save_fields.items(),1):
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


def render_report_studio(sb, context: tuple[str,str,dict] | None=None, mode: str="studio", lens_override: str | None=None):
    seed=_context_seed(context)
    if st.session_state.get(f"pc_report_fresh_{mode}"):
        seed={}
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

    lens=lens_override if lens_override in ("trade","intelligence") else ("trade" if mode=="brief" else "intelligence")
    query=st.text_input(
        "Query / analytical question",
        value=seed.get("title","") if seed else "",
        placeholder=("AD Ports Brazil acquisition, Middle Corridor capacity, freight disruption..." if lens=="trade"
                     else "Hormuz escalation, Red Sea shipping risk, regional disruption, actor network..."),
        key=f"pc_report_query_{mode}"
    )
    discovered_events, discovered_objects = _query_discovery(sb, query) if query.strip() else ([], [])
    query_results=_terminal_search(sb,query,80) if query.strip() else []
    seen_objects={(_clean(r.get("object_type")),_clean(r.get("object_id"))) for r in query_results}
    query_results += [r for r in discovered_objects
                      if (_clean(r.get("object_type")),_clean(r.get("object_id"))) not in seen_objects]
    selected_objects=[]
    if query_results:
        labels={_query_label(r):r for r in query_results}
        default_labels=list(labels)[:1] if len(labels)==1 else []
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

    if lens=="intelligence":
        with st.expander("Daily Brief — select and review developments",expanded=bool(st.session_state.pop("pc_report_daily_entry_intelligence",False))):
            from datetime import timedelta
            from zoneinfo import ZoneInfo
            from datetime import datetime
            day=st.date_input("Brief date (UAE)",datetime.now(ZoneInfo("Asia/Dubai")).date(),key=f"pc_studio_daily_date_{mode}")
            days=st.selectbox("Evidence window",["Selected day","Last 7 days"],key=f"pc_studio_daily_window_{mode}")
            start=day-timedelta(days=6 if days=="Last 7 days" else 0)
            try:
                candidates=(sb.table("pc_events").select("*").gte("start_date",str(start))
                            .lt("start_date",str(day+timedelta(days=1))).order("start_date",desc=True).limit(500).execute().data or [])
            except Exception as exc:
                st.warning("Daily candidate retrieval incomplete: "+str(exc)[:180])
                candidates=[]
            def security_rank(e):
                words=("attack","strike","missile","intercept","threat","injur","damage","board","seiz",
                       "sanction","conflict","airport","security","suspend","disrupt","evacuat","houthi","drone","cyber")
                blob=(" ".join(_clean(e.get(k)) for k in ("title","description","event_type","event_family"))).casefold()
                return (sum(1 for w in words if w in blob),_clean(e.get("start_date")))
            candidates=[e for e in candidates if not _horizon_event(e) and e.get("intelligence_visible") is not False]
            candidates.sort(key=security_rank,reverse=True)
            st.caption(f"{len(candidates)} candidate events. Security relevance is a sorting aid, not an AI risk rating.")
            st.dataframe(pd.DataFrame([{"Date":_clean(e.get("start_date"))[:10],"Development":_clean(e.get("title")),
                "Verification":_clean(e.get("verification_status")),"Sources":len(_urls_from_record(e))} for e in candidates[:35]]),
                hide_index=True,use_container_width=True)
            if st.button("Add security-priority candidates to report",key=f"pc_daily_select_{mode}"):
                ids=[e["event_id"] for e in candidates if security_rank(e)[0]>0][:12]
                if not ids:
                    st.warning("No security-priority events found in this period. Select suitable developments manually below.")
                else:
                    old=st.session_state.get(f"pc_report_selected_ids_{mode}",[])
                    st.session_state[f"pc_report_selected_ids_{mode}"]=list(dict.fromkeys(old+ids))
                    st.session_state[f"pc_report_product_{mode}"]="Daily / Multi-Event Brief"
                    st.rerun()
            st.caption("Review the selection below, assemble evidence, then draft and export using the normal Report Studio workflow.")

    research_tab, editorial_tab, publication_tab = st.tabs(["1 · Research & evidence", "2 · Generate & review", "3 · Publication"])
    with research_tab:
        st.caption("Select the relevant developments, then inspect and approve connected evidence.")
        st.markdown("#### Development library")
        st.caption("Search across verified production developments. Filter by purpose; combine Trade and Security whenever needed.")
        qcol,scope_col,date_col=st.columns([3,1.4,1.3])
        event_find=qcol.text_input("Find developments",placeholder="Panama tanker, DF Peak, Réunion...",
                                  key=f"pc_report_find_events_{mode}")
        scope=scope_col.selectbox("Coverage",["All developments","Security & disruption","Trade & commercial"],
                                  key=f"pc_report_scope_{mode}")
        period=date_col.selectbox("Period",["Last 30 days","Last 90 days","All dates"],
                                  key=f"pc_report_find_period_{mode}")
        lookup=event_find.strip()
        found,_=_query_discovery(sb,lookup) if lookup else ([],[])
        recent=[e for e in _recent_events(sb,300) if not _horizon_event(e)] if not lookup else []
        event_map={str(e.get("event_id")):e for e in found+recent if e.get("event_id") and not _horizon_event(e)}
        if period!="All dates":
            from datetime import timedelta
            cutoff=(date.today()-timedelta(days=30 if period=="Last 30 days" else 90)).isoformat()
            event_map={k:e for k,e in event_map.items() if _clean(e.get("start_date"))[:10]>=cutoff}
        if scope=="Security & disruption":
            event_map={k:e for k,e in event_map.items() if e.get("intelligence_visible") is True}
        elif scope=="Trade & commercial":
            event_map={k:e for k,e in event_map.items() if e.get("trade_visible") is True}
        picked_key=f"pc_report_selected_ids_{mode}"
        selected_ids=list(st.session_state.get(picked_key,[]))
        if not st.session_state.get(f"pc_report_fresh_{mode}") and seed.get("type")=="event" and seed.get("id") and seed["id"] not in selected_ids:
            selected_ids.append(seed["id"])
        ordered=sorted(event_map.items(),key=lambda pair:_clean(pair[1].get("start_date")),reverse=True)
        st.caption(f"{len(ordered)} matching developments · showing up to 15 per page")
        page_key=f"pc_report_results_page_{mode}"
        max_page=max(1,(len(ordered)+14)//15)
        page=st.number_input("Results page",min_value=1,max_value=max_page,value=1,
                             key=page_key) if max_page>1 else 1
        for eid,e in ordered[(page-1)*15:page*15]:
            title=_clean(e.get("title") or "Untitled development")
            date_str=_clean(e.get("start_date"))[:10]
            c1,c2=st.columns([6,1])
            c1.markdown(f"**{title}** · {date_str}")
            summary=_event_summary(e)
            if summary: c1.caption(summary[:165]+("…" if len(summary)>165 else ""))
            if c2.button("✓ Added" if eid in selected_ids else "Add +",
                         disabled=eid in selected_ids,key=f"pc_story_add_{mode}_{eid}",
                         use_container_width=True):
                selected_ids.append(eid)
                st.session_state[picked_key]=list(dict.fromkeys(selected_ids))
                st.rerun()
        if lookup and not ordered:
            st.info("No matching production developments under these filters. Try All developments or a shorter search.")
        st.markdown("**Selected for this report**")
        selected=[]
        for eid in list(dict.fromkeys(selected_ids)):
            e=event_map.get(eid)
            if not e:
                try:
                    rows=(sb.table("pc_events").select("*").eq("event_id",eid).limit(1).execute().data or [])
                    e=rows[0] if rows else None
                except Exception: e=None
            if not e or _horizon_event(e): continue
            selected.append(e)
            c1,c2=st.columns([6,1])
            c1.write(_clean(e.get("title"))+" · "+_clean(e.get("start_date"))[:10])
            if c2.button("Remove",key=f"pc_story_remove_{mode}_{eid}"):
                st.session_state[picked_key]=[x for x in selected_ids if x!=eid]
                st.rerun()
        st.session_state[picked_key]=[e["event_id"] for e in selected]
        if selected: st.caption("These developments and their linked records form the AI draft context.")
        if seed:
            st.info(f"Current terminal context: {seed.get('title')} · {seed.get('type')}")

        st.markdown("#### Connected evidence")
        if lens=="intelligence":
            st.caption("Select incidents first. Review grounded factual components before adding them to the report.")
        else:
            st.caption("Start with a canonical organisation or asset, then include related developments.")
        if st.button("Assemble evidence for review",key=f"pc_assemble_{mode}"):
            assembled=_assemble_evidence(sb,lens,selected,selected_objects,None if st.session_state.get(f"pc_report_fresh_{mode}") else context)
            st.session_state[f"pc_assembled_{mode}"]=assembled
            st.session_state.pop(f"pc_assemble_choices_{mode}",None)
            st.rerun()
        assembled=st.session_state.get(f"pc_assembled_{mode}") or {}
        if assembled:
            counts=assembled["counts"]
            st.caption("Retrieved: "+", ".join(str(v)+" "+k.replace("_"," ") for k,v in counts.items()))
            if assembled["issues"]:
                with st.expander("Retrieval warnings — records may be incomplete"):
                    for issue in assembled["issues"]:st.write(issue)
            if not assembled["blocks"]:
                st.warning("No structured component has sufficient retrieved records. Check selected events and retrieval warnings.")
            else:
                st.markdown("**Choose evidence components for the editorial canvas**")
                choices_key=f"pc_assemble_choices_{mode}"
                if choices_key not in st.session_state:
                    st.session_state[choices_key]=[b["id"] for b in assembled["blocks"]]
                choices=st.multiselect("Include",options=[b["id"] for b in assembled["blocks"]],
                     format_func=lambda bid:next((b["title"]+" ("+str(len(b.get("rows") or []))+" rows)" for b in assembled["blocks"] if b["id"]==bid),bid),
                     key=choices_key)
                for block in assembled["blocks"]:
                    with st.expander(block["title"]+" · "+str(len(block.get("rows") or []))+" records"):
                        st.dataframe(pd.DataFrame(block.get("rows") or []),hide_index=True,use_container_width=True)
                if st.button("Add selected components to report",disabled=not choices,key=f"pc_assemble_apply_{mode}"):
                    current=st.session_state.get(f"pc_editor_blocks_{mode}") or []
                    additions=[dict(b) for b in assembled["blocks"] if b["id"] in choices]
                    existing_ids={b["id"] for b in current}
                    additions=[b for b in additions if b["id"] not in existing_ids]
                    st.session_state[f"pc_editor_blocks_{mode}"]=current+additions
                    st.session_state[f"pc_assemble_added_{mode}"]=len(additions)
                    st.rerun()
                if f"pc_assemble_added_{mode}" in st.session_state:
                    st.success(str(st.session_state.pop(f"pc_assemble_added_{mode}"))+" evidence blocks added; existing narrative preserved.")
            st.caption("No inferred exposure, numerical trend or legal designation is generated without supporting records.")

    with editorial_tab:
        st.caption("Generate the intelligence article and review the proposed text before acceptance.")
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

        if cauto2.button("Generate full analytical first draft",type="primary",key=f"pc_report_ai_draft_{mode}",use_container_width=True):
            try:
                from pc_report_ai import draft_report
                bundle=_ai_context_bundle(sb,lens,query,selected_objects,selected,context)
                if assembled:
                    bundle["assembled_evidence"]={"counts":assembled["counts"],"blocks":assembled["blocks"],"issues":assembled["issues"]}
                    bundle["evidence_urls"]=list(dict.fromkeys(bundle.get("evidence_urls",[])+assembled["sources"]))
                result=draft_report(
                    _api_key(),lens,product,spec["sections"],query,bundle,
                    title_hint=seed.get("title","")
                )
                narrative = {k:_clean(v) for k,v in (result.get("sections") or {}).items()
                             if k in spec["sections"] and _clean(v)}
                if not narrative:
                    raise ValueError("The drafting service returned no usable narrative. The editor was not changed.")
                if not assembled or not assembled.get("counts",{}).get("events"):
                    st.warning("Draft generated without assembled incident evidence; verify coverage before acceptance.")
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
                proposed=[_new_block("Narrative",name,_clean(value)) for name,value in (result.get("sections") or {}).items() if _clean(value)]
                current=st.session_state.get(f"pc_editor_blocks_{mode}") or []
                if proposed and not any(_clean(b.get("body")) or b.get("rows") for b in current):
                    st.session_state[f"pc_editor_blocks_{mode}"]=proposed
                    st.session_state.pop(f"pc_editor_proposal_{mode}",None)
                else:
                    factual=[dict(b) for b in current if b.get("kind")=="Asset table" and b.get("rows")]
                    st.session_state[f"pc_editor_proposal_{mode}"]=proposed+factual
                st.rerun()
            except Exception as exc:
                st.error(f"AI drafting failed: {exc}")

        proposal=st.session_state.get(f"pc_editor_proposal_{mode}")
        if proposal is not None:
            st.info("AI proposed an editable draft. Accept or discard it; your current work is unchanged.")
            yes,no=st.columns(2)
            st.caption(f"{len(proposal)} proposed content blocks; "+str(sum(bool(_clean(b.get("body"))) for b in proposal))+" contain narrative text.")
            with st.expander("Read proposed analytical draft before accepting", expanded=True):
                for draft_block in proposal:
                    if draft_block.get("kind")=="Narrative" and _clean(draft_block.get("body")):
                        st.markdown("#### "+_clean(draft_block.get("title")))
                        st.markdown(_clean(draft_block.get("body")))
                st.caption("Evidence tables remain separate and must be supported by retrieved records.")

            if yes.button("Accept AI draft",key=f"pc_accept_{mode}",disabled=not bool(proposal)):
                # Clear old canvas widget state before installing the proposal. Streamlit
                # widget keys otherwise take precedence over the new block defaults.
                for key in list(st.session_state):
                    if key.startswith((f"pc_title_block_{mode}_",f"pc_body_{mode}_",
                                       f"pc_preset_{mode}_",f"pc_edit_table_{mode}_")):
                        del st.session_state[key]
                installed=[dict(b) for b in proposal]
                for block in installed:
                    bid=block["id"]
                    st.session_state[f"pc_title_block_{mode}_{bid}"]=block.get("title","")
                    if block.get("kind")!="Asset table":
                        st.session_state[f"pc_body_{mode}_{bid}"]=block.get("body","")
                st.session_state[f"pc_editor_blocks_{mode}"]=installed
                del st.session_state[f"pc_editor_proposal_{mode}"]
                st.rerun()
            if no.button("Discard AI draft",key=f"pc_discard_{mode}"):
                del st.session_state[f"pc_editor_proposal_{mode}"]
                st.rerun()
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

        st.markdown("### Editorial canvas")
        canvas_key=f"pc_editor_blocks_{mode}"
        if canvas_key not in st.session_state:
            st.session_state[canvas_key]=[_new_block("Narrative",name) for name in spec["sections"]]
        blocks=st.session_state[canvas_key]
        ckind,cadd=st.columns([3,1])
        kind=ckind.selectbox("New content block",BLOCK_TYPES,key=f"pc_kind_{mode}")
        if cadd.button("Add block",key=f"pc_add_{mode}"):
            new_block=_new_block(kind,preset="Vessels" if kind=="Asset table" else "Custom")
            # Place new work at the top, not after seven lengthy template sections.
            blocks.insert(0,new_block)
            st.session_state[canvas_key]=blocks
            st.session_state[f"pc_editor_notice_{mode}"]=new_block["id"]
            st.rerun()
        if st.session_state.get(f"pc_editor_notice_{mode}"):
            st.success("New block added at the top of the canvas. Edit its heading and content below.")
            st.session_state.pop(f"pc_editor_notice_{mode}",None)
        st.caption(f"{len(blocks)} editable blocks in this report.")
        # Intelligence uses a manuscript-first editor. Evidence tables stay as structured
        # blocks, and the legacy block editor remains available for other lenses.
        document_first = lens == "intelligence" and st.toggle(
            "Continuous document editor", value=True, key=f"pc_document_first_{mode}",
            help="Edit report prose as one manuscript rather than filling individual section boxes.")
        if document_first:
            import hashlib
            from pc_report_document import manuscript_from_blocks, apply_manuscript
            manuscript = manuscript_from_blocks(blocks)
            revision = hashlib.sha256(manuscript.encode("utf-8")).hexdigest()[:12]
            st.caption("Write and reorganise the report naturally using ## headings. Evidence tables remain linked and are not replaced by manuscript edits.")
            with st.form(key=f"pc_manuscript_form_{mode}_{revision}"):
                edited_manuscript = st.text_area(
                    "Report manuscript (Markdown)", value=manuscript, height=650,
                    key=f"pc_manuscript_{mode}_{revision}",
                    help="Use ## for section headings. Citation markers such as [1] are retained.")
                apply_document = st.form_submit_button("Apply manuscript edits",type="primary",use_container_width=True)
            if apply_document:
                revised, error = apply_manuscript(blocks, edited_manuscript)
                if error:
                    st.error(error)
                else:
                    st.session_state[canvas_key] = revised
                    st.success("Manuscript applied. Structured evidence tables and existing source records are preserved.")
                    st.rerun()
            with st.expander("Connected evidence tables in this report", expanded=False):
                tables=[b for b in blocks if b.get("kind")=="Asset table"]
                if not tables:
                    st.caption("No evidence tables added yet. Select them in Connected evidence above.")
                for b in tables:
                    st.markdown("**"+_clean(b.get("title"))+"** · "+str(len(b.get("rows") or []))+" records")
                    st.dataframe(pd.DataFrame(b.get("rows") or []),hide_index=True,use_container_width=True)
            st.caption("Apply manuscript edits before using other controls. Report preview and export use the applied version.")
        fields={}
        if not document_first:
            for i,block in enumerate(list(blocks)):
                bid=block["id"]
                with st.container(border=True):
                    top,up,down,delete=st.columns([6,1,1,1])
                    block["title"]=top.text_input("Heading",value=block.get("title",""),key=f"pc_title_block_{mode}_{bid}")
                    if up.button("↑",key=f"pc_up_{mode}_{bid}",disabled=i==0):
                        blocks[i-1],blocks[i]=blocks[i],blocks[i-1]
                        st.rerun()
                    if down.button("↓",key=f"pc_down_{mode}_{bid}",disabled=i==len(blocks)-1):
                        blocks[i+1],blocks[i]=blocks[i],blocks[i+1]
                        st.rerun()
                    if delete.button("×",key=f"pc_del_{mode}_{bid}"):
                        blocks.pop(i)
                        st.rerun()
                    if block["kind"]=="Asset table":
                        choices=list(TABLE_PRESETS)
                        preset=st.selectbox("Table layout",choices,index=choices.index(block.get("preset")) if block.get("preset") in choices else choices.index("Custom"),key=f"pc_preset_{mode}_{bid}")
                        if preset!=block.get("preset"):
                            block["preset"]=preset
                            block["rows"]=[]
                        if st.button("Populate from connected records",key=f"pc_pop_table_{mode}_{bid}"):
                            bundle=_ai_context_bundle(sb,lens,query,selected_objects,selected,context)
                            block["rows"]=_vessels_for_report(sb,selected) if preset=="Vessels" else _asset_table_rows(bundle.get("objects") or [],preset)
                            st.session_state.pop(f"pc_edit_table_{mode}_{bid}",None)
                            st.session_state[f"pc_table_count_{mode}_{bid}"]=len(block["rows"])
                            st.rerun()
                        if f"pc_table_count_{mode}_{bid}" in st.session_state:
                            count=st.session_state.pop(f"pc_table_count_{mode}_{bid}")
                            st.info(f"{count} canonical records found; if zero, no verified matching vessel records were found.")
                        frame=pd.DataFrame(block.get("rows") or [],columns=block.get("columns") or TABLE_PRESETS[preset])
                        edited=st.data_editor(frame,num_rows="dynamic",hide_index=True,use_container_width=True,key=f"pc_edit_table_{mode}_{bid}")
                        block["rows"]=edited.fillna("").to_dict("records")
                    elif block["kind"]=="References":
                        st.caption("References are collected automatically in the evidence panel below.")
                    else:
                        block["body"]=st.text_area("Text",value=block.get("body",""),height=190,key=f"pc_body_{mode}_{bid}")
                        instruction=st.text_input("AI assistance for this block",placeholder="Expand, rewrite, compare, or add supported references",
                            key=f"pc_assist_instruction_{mode}_{bid}")
                        if st.button("AI suggest edit",key=f"pc_assist_{mode}_{bid}"):
                            if not instruction.strip():
                                st.warning("Enter an instruction first.")
                            else:
                                try:
                                    from pc_report_ai import assist_block
                                    bundle=_ai_context_bundle(sb,lens,query,selected_objects,selected,context)
                                    st.session_state[f"pc_assist_proposal_{mode}_{bid}"]=assist_block(_api_key(),instruction,block,bundle)
                                    st.rerun()
                                except Exception as exc:
                                    st.error(f"AI edit failed: {exc}")
                        proposed=st.session_state.get(f"pc_assist_proposal_{mode}_{bid}")
                        if proposed:
                            st.markdown("**Suggested replacement (not yet applied)**")
                            st.write(_clean(proposed.get("body")))
                            ac,dc=st.columns(2)
                            if ac.button("Accept edit",key=f"pc_assist_accept_{mode}_{bid}"):
                                block["body"]=_clean(proposed.get("body"))
                                block["title"]=_clean(proposed.get("title")) or block["title"]
                                st.session_state.pop(f"pc_body_{mode}_{bid}",None)
                                st.session_state.pop(f"pc_title_block_{mode}_{bid}",None)
                                del st.session_state[f"pc_assist_proposal_{mode}_{bid}"]
                                st.rerun()
                            if dc.button("Discard edit",key=f"pc_assist_discard_{mode}_{bid}"):
                                del st.session_state[f"pc_assist_proposal_{mode}_{bid}"]
                                st.rerun()
                        fields[block["title"]]=block["body"]
        blocks=st.session_state[canvas_key] if document_first else blocks
        st.session_state[canvas_key]=blocks
        if not blocks:
            st.info("Canvas is empty. Add a block or generate an AI draft.")

    with publication_tab:
        st.caption("Read the publication, inspect source coverage and save or export the reviewed edition.")
        source_urls=[]
        for e in selected:
            source_urls.extend(_urls_from_record(e))
        if seed.get("type")=="event":
            source_urls.extend(_urls_from_record(seed.get("record") or {}))
        ai_bundle=st.session_state.get(f"pc_report_ai_bundle_{mode}") or {}
        source_urls.extend(ai_bundle.get("evidence_urls") or [])
        source_urls.extend((st.session_state.get(f"pc_assembled_{mode}") or {}).get("sources") or [])
        source_urls=list(dict.fromkeys(source_urls))

        st.markdown("### Evidence")
        evidence_key=f"pc_report_sources_{mode}"
        prior=st.session_state.get(evidence_key,"")
        prior_urls=[x.strip() for x in prior.splitlines() if x.strip().startswith(("http://","https://"))]
        st.session_state[evidence_key]="\n".join(dict.fromkeys(prior_urls+source_urls))
        source_text=st.text_area("Source URLs — automatically collected from selected incidents",
                                 key=evidence_key,height=145)
        sources=list(dict.fromkeys(x.strip() for x in source_text.splitlines()
                                   if x.strip().startswith(("http://","https://"))))
        if not sources:
            st.warning("No evidence URLs yet: attach sources before publishing.")

        if lens == "intelligence":
            from pc_intelligence_publication import render_publication, evidence_audit
            publication_events=[{"sources":_urls_from_record(e)} for e in selected]
            coverage=evidence_audit(publication_events)
            if coverage["missing"]:
                st.warning(f"Source coverage: {coverage['sourced']}/{coverage['total']} selected incidents have linked URLs. Review unsupported claims and confidence before distributing.")
            web_html=render_publication(report_title,report_date,region,product,summary,blocks,sources,publication_events)
        else:
            web_html=_build_html(product,report_title,report_date,region,confidence,summary,fields,sources,blocks)
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
                rid=_save_report(sb,product,report_title,report_date,region,summary,fields,selected,sources,"draft",context,blocks)
                st.success(f"Draft saved: {rid}")
            except Exception as exc:
                st.error(f"Could not save report: {exc}")

        if b.button("Save for review",disabled=not bool(report_title.strip()),key=f"pc_report_save_review_{mode}"):
            try:
                rid=_save_report(sb,product,report_title,report_date,region,summary,fields,selected,sources,"review",context,blocks)
                st.success(f"Saved for review: {rid}")
            except Exception as exc:
                st.error(f"Could not save report: {exc}")

        if c.button("New report — clear workspace",key=f"pc_report_clear_{mode}"):
            # Clear every report-specific control, not merely the text fields.
            # Saved reports in pc_reports are unaffected.
            prefixes=(
                f"pc_report_field_{mode}_",f"pc_report_title_{mode}",
                f"pc_report_date_{mode}",f"pc_report_region_{mode}",
                f"pc_report_summary_{mode}",f"pc_report_sources_{mode}",
                f"pc_report_events_{mode}",f"pc_report_query_{mode}",
                f"pc_report_query_objects_{mode}",f"pc_report_ai_gaps_{mode}",
                f"pc_report_ai_bundle_{mode}",f"pc_report_product_{mode}",
                f"pc_report_find_events_{mode}",f"pc_report_scope_{mode}",
                f"pc_report_find_period_{mode}",f"pc_report_selected_ids_{mode}",
                f"pc_report_results_page_{mode}",f"pc_report_prefill_{mode}_",
                f"pc_editor_blocks_{mode}",f"pc_editor_proposal_{mode}",
                f"pc_editor_notice_{mode}",f"pc_kind_{mode}",
                f"pc_title_block_{mode}_",f"pc_body_{mode}_",
                f"pc_preset_{mode}_",f"pc_edit_table_{mode}_",
                f"pc_table_count_{mode}_",f"pc_assist_instruction_{mode}_",
                f"pc_assist_proposal_{mode}_",f"pc_assembled_{mode}",
                f"pc_assemble_choices_{mode}",f"pc_assemble_added_{mode}",
            )
            for key in list(st.session_state):
                if any(key.startswith(prefix) for prefix in prefixes):
                    del st.session_state[key]
            # Opening a report from an event must not silently reattach that event.
            st.session_state[f"pc_report_fresh_{mode}"]=True
            st.rerun()
