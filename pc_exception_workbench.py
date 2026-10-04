"""Shared multi-analyst exception workbench for Power Admin."""
from __future__ import annotations
import hashlib, json
from datetime import datetime, timezone
import pandas as pd
import streamlit as st


def _domain(row):
    table=str(row.get("Table") or row.get("target_table") or "")
    text=" ".join(str(row.get(k) or "") for k in ("Name","Reason","Table")).casefold()
    if any(x in text for x in ("sanction","ofac","designation","sdn","uk sanctions","eu sanctions")):
        return "sanctions"
    if table=="pc_events" or any(x in text for x in ("event","incident","attack","strike","security","intelligence")):
        return "intelligence"
    if table in {"pc_entities","pc_assets","pc_mobile_assets"}:
        return "trade"
    return "cross"


def _priority(reason):
    text=str(reason or "").casefold()
    if any(x in text for x in ("multiple canonical","conflict","duplicate imo","country differs")):
        return 90
    if any(x in text for x in ("fuzzy","classification","short-name","review")):
        return 70
    if any(x in text for x in ("no original source","no narrative","evidence")):
        return 60
    return 50


def sync_plan_exceptions(sb, job, exceptions):
    """Upsert current planner holds into the shared analyst queue.

    Existing claims are preserved. Open items that disappear from the current
    planner result are auto-cleared. Claimed items are never auto-closed.
    """
    current=set()
    for x in exceptions or []:
        sid=str(x.get("Staged record ID") or "").strip()
        if sid:
            key="core:"+sid
        else:
            raw="|".join(str(x.get(k) or "") for k in ("Table","Name","Reason"))
            key="corehash:"+hashlib.sha256(raw.encode()).hexdigest()[:32]
        current.add(key)
        record={
            "ingestion_job_id":job,
            "staged_record_id":sid or None,
            "exception_key":key,
            "workstream":_domain(x),
            "exception_type":"canonical_review",
            "target_table":x.get("Table"),
            "subject_name":x.get("Name"),
            "reason":str(x.get("Reason") or "Planner exception"),
            "priority":_priority(x.get("Reason")),
            "context":x,
            "updated_at":datetime.now(timezone.utc).isoformat(),
        }
        existing=(sb.table("pc_analyst_exceptions").select("exception_id,status")
                  .eq("ingestion_job_id",job).eq("exception_key",key).limit(1).execute().data or [])
        if existing:
            if existing[0].get("status") in {"open","claimed"}:
                sb.table("pc_analyst_exceptions").update({
                    k:v for k,v in record.items()
                    if k not in {"ingestion_job_id","exception_key"}
                }).eq("exception_id",existing[0]["exception_id"]).execute()
            elif existing[0].get("status") in {"resolved","dismissed"}:
                # If the planner still reports the problem after analyst resolution,
                # reopen it: the underlying condition was not actually cleared.
                sb.table("pc_analyst_exceptions").update({
                    **{k:v for k,v in record.items() if k not in {"ingestion_job_id","exception_key"}},
                    "status":"open","assigned_to":None,"assigned_name":None,
                    "claimed_at":None,"resolved_at":None,
                    "resolution":{},
                }).eq("exception_id",existing[0]["exception_id"]).execute()
        else:
            sb.table("pc_analyst_exceptions").insert(record).execute()

    active_rows=(sb.table("pc_analyst_exceptions")
                 .select("exception_id,exception_key,status,assigned_to,assigned_name,version")
                 .eq("ingestion_job_id",job)
                 .in_("status",["open","claimed"]).limit(5000).execute().data or [])
    for row in active_rows:
        if row.get("exception_key") not in current:
            # The canonical planner is authoritative for whether this exception
            # still exists. Once reconciliation clears it, close both open and
            # claimed workbench tickets so analysts do not see stale work.
            sb.table("pc_analyst_exceptions").update({
                "status":"resolved",
                "resolved_at":datetime.now(timezone.utc).isoformat(),
                "updated_at":datetime.now(timezone.utc).isoformat(),
                "resolution":{
                    "method":"auto_cleared_after_reconciliation",
                    "reason":"Canonical planner no longer reports this exception",
                    "previous_status":row.get("status"),
                    "previous_assignee":row.get("assigned_to"),
                },
                "version":int(row.get("version") or 1)+1,
            }).eq("exception_id",row["exception_id"]).execute()


def _analyst_identity(ctx):
    email=(ctx or {}).get("email") or "staff"
    name=(ctx or {}).get("display_name") or email
    return str(email),str(name)


def _stage_evidence_urls(stage):
    p=(stage or {}).get("payload") or {}
    m=p.get("metadata") or {}
    vals=[]
    for raw in (m.get("research_sources"),m.get("source_urls"),m.get("source_url"),
                m.get("intake_source_url"),p.get("source_url")):
        for x in raw if isinstance(raw,list) else ([raw] if raw else []):
            u=x.get("url") if isinstance(x,dict) else x
            if isinstance(u,str) and u.startswith("https://") and u not in vals:
                vals.append(u)
    return vals


def _event_candidates(sb, stage):
    """Return a small, explainable candidate set for analyst review."""
    p=(stage or {}).get("payload") or {}
    title=str(p.get("title") or stage.get("natural_key") or "").strip()
    date=p.get("start_date")
    rows={}
    if title:
        for r in (sb.table("pc_events")
                  .select("event_id,title,start_date,event_type,location,description")
                  .eq("title",title).limit(50).execute().data or []):
            rows[str(r["event_id"])]=r
    if date:
        for r in (sb.table("pc_events")
                  .select("event_id,title,start_date,event_type,location,description")
                  .eq("start_date",date).limit(100).execute().data or []):
            rows[str(r["event_id"])]=r

    def score(r):
        s=0
        if str(r.get("title") or "").casefold()==title.casefold(): s+=100
        if date and str(r.get("start_date") or "")==str(date): s+=50
        if p.get("location") and str(r.get("location") or "").casefold()==str(p.get("location")).casefold(): s+=20
        if p.get("event_type") and str(r.get("event_type") or "").casefold()==str(p.get("event_type")).casefold(): s+=10
        return s

    return sorted(rows.values(),key=score,reverse=True)[:30]


def _apply_event_decision_and_reconcile(sb, item, analyst, analyst_name, decision, canonical_id=None):
    """Apply a reviewed event decision to staging and immediately reconcile."""
    from pc_reviewed_job_repair import apply_repair, fingerprint
    from pc_v15_bulk_replay import _all_staged, _plan, _publish_ready

    job=str(item["ingestion_job_id"])
    sid=str(item.get("staged_record_id") or "")
    rows=(sb.table("pc_staged_records").select("*")
          .eq("ingestion_job_id",job).eq("staged_record_id",sid)
          .limit(1).execute().data or [])
    if len(rows)!=1:
        raise ValueError("Staged event is no longer available")
    stage=rows[0]
    if stage.get("target_table")!="pc_events":
        raise ValueError("Direct resolution currently supports event exceptions only")

    evidence=_stage_evidence_urls(stage)
    if not evidence:
        raise ValueError("No HTTPS source evidence is attached to this staged event")

    reviewed_payload=json.loads(json.dumps(stage["payload"]))
    reviewed_meta=reviewed_payload.get("metadata") or {}
    reviewed_meta.pop("canonical_hold",None)
    reviewed_payload["metadata"]=reviewed_meta

    repair_item={
        "staged_record_id":sid,
        "expected_fingerprint":fingerprint({
            "payload":stage["payload"],
            "natural_key":stage["natural_key"]
        }),
        "payload":reviewed_payload,
        "natural_key":stage["natural_key"],
        "decision":decision,
        "evidence_urls":evidence,
        "reason":"Analyst workbench event identity decision; stale canonical hold cleared by explicit analyst resolution.",
    }
    if canonical_id:
        repair_item["canonical_id"]=canonical_id

    repair={
        "job_id":job,
        "reason":"Analyst workbench event resolution by "+analyst_name,
        "items":[repair_item],
    }
    repaired=apply_repair(sb,job,repair,analyst_name)

    staged=_all_staged(sb,job)
    ready,followers,exceptions,_=_plan(sb,job,staged)
    failures=[]
    published_now=0
    if ready:
        _,follow_count,failures=_publish_ready(sb,job,ready,followers,analyst_name)
        published_now=len(ready)+follow_count-len(failures)

    try:
        sb.rpc("pc_v12_sync_published_links",{"p_job":job}).execute()
    except Exception:
        pass

    staged2=_all_staged(sb,job)
    _,_,remaining,_=_plan(sb,job,staged2)
    sync_plan_exceptions(sb,job,remaining)

    return {
        "repair":repaired,
        "published_now":published_now,
        "publication_failures":failures,
        "remaining_exceptions":len(remaining),
    }


def _stage_for_exception(sb,item):
    sid=str(item.get("staged_record_id") or "").strip()
    job=str(item.get("ingestion_job_id") or "")
    if sid:
        rows=(sb.table("pc_staged_records").select("*")
              .eq("ingestion_job_id",job).eq("staged_record_id",sid)
              .limit(2).execute().data or [])
        return rows[0] if len(rows)==1 else None
    table=str(item.get("target_table") or "")
    name=str(item.get("subject_name") or "").strip()
    if not table or not name:
        return None
    rows=(sb.table("pc_staged_records").select("*")
          .eq("ingestion_job_id",job).eq("target_table",table)
          .eq("natural_key",name).limit(5).execute().data or [])
    return rows[0] if len(rows)==1 else None


def _identity_candidates(sb,stage):
    table=stage.get("target_table")
    p=stage.get("payload") or {}
    name=str(p.get("name") or stage.get("natural_key") or "").strip()
    cfg={
        "pc_entities":("entity_id","name","entity_type,hq_country"),
        "pc_assets":("asset_id","name","asset_type,country"),
        "pc_mobile_assets":("mobile_asset_id","name","asset_type,imo,flag"),
    }.get(table)
    if not cfg or not name:
        return [],None
    pk,name_col,extra=cfg
    cols=pk+","+name_col+","+extra
    rows=[]
    seen=set()
    try:
        exact=(sb.table(table).select(cols).eq(name_col,name).limit(50).execute().data or [])
    except Exception:
        exact=[]
    try:
        near=(sb.table(table).select(cols).ilike(name_col,"%"+name.replace("%","")+"%")
              .limit(50).execute().data or [])
    except Exception:
        near=[]
    for r in exact+near:
        rid=str(r.get(pk) or "")
        if rid and rid not in seen:
            seen.add(rid); rows.append(r)
    return rows[:30],pk


def _apply_identity_decision_and_reconcile(sb,item,analyst_name,decision,canonical_id=None):
    from pc_reviewed_job_repair import apply_repair, fingerprint
    from pc_v15_bulk_replay import _all_staged, _plan, _publish_ready

    stage=_stage_for_exception(sb,item)
    if not stage:
        raise ValueError("Could not uniquely locate the staged record for this exception")
    table=stage.get("target_table")
    if table not in {"pc_entities","pc_assets","pc_mobile_assets","pc_events"}:
        raise ValueError("This exception type is not directly resolvable yet")

    evidence=_stage_evidence_urls(stage)
    if not evidence:
        raise ValueError("No HTTPS source evidence is attached to this staged record")

    reviewed_payload=json.loads(json.dumps(stage.get("payload") or {}))
    reviewed_meta=reviewed_payload.get("metadata") or {}
    reviewed_meta.pop("canonical_hold",None)
    reviewed_payload["metadata"]=reviewed_meta

    repair_item={
        "staged_record_id":str(stage["staged_record_id"]),
        "expected_fingerprint":fingerprint({
            "payload":stage["payload"],
            "natural_key":stage["natural_key"]
        }),
        "payload":reviewed_payload,
        "natural_key":stage["natural_key"],
        "decision":decision,
        "evidence_urls":evidence,
        "reason":"Analyst workbench canonical identity decision",
    }
    if canonical_id:
        repair_item["canonical_id"]=canonical_id

    job=str(item["ingestion_job_id"])
    repaired=apply_repair(sb,job,{
        "job_id":job,
        "reason":"Analyst workbench identity resolution by "+analyst_name,
        "items":[repair_item],
    },analyst_name)

    staged=_all_staged(sb,job)
    ready,followers,exceptions,_=_plan(sb,job,staged)
    failures=[]; published_now=0
    if ready:
        _,follow_count,failures=_publish_ready(sb,job,ready,followers,analyst_name)
        published_now=len(ready)+follow_count-len(failures)
    try:
        sb.rpc("pc_v12_sync_published_links",{"p_job":job}).execute()
    except Exception:
        pass
    staged2=_all_staged(sb,job)
    _,_,remaining,_=_plan(sb,job,staged2)
    sync_plan_exceptions(sb,job,remaining)
    return {
        "repair":repaired,
        "published_now":published_now,
        "publication_failures":failures,
        "remaining_exceptions":len(remaining),
    }


def render_exception_workbench(sb, ctx):
    analyst, analyst_name=_analyst_identity(ctx)
    st.title("Analyst Exception Workbench")
    st.caption("Shared Trade · Intelligence · Sanctions review queue. Claims are atomic, so analysts can work concurrently without taking the same item.")

    try:
        rows=(sb.table("pc_analyst_exceptions").select("*")
              .in_("status",["open","claimed"]).order("priority",desc=True)
              .order("created_at").limit(2000).execute().data or [])
    except Exception as exc:
        st.error("Multi-analyst queue is not available yet. Apply 058_multi_analyst_exception_workbench.sql to Supabase, then refresh.")
        st.caption(str(exc))
        return

    job_filter=str(st.session_state.get("pc_exception_job_filter") or "").strip()
    core_only=bool(st.session_state.get("pc_exception_core_only"))
    if job_filter:
        rows=[r for r in rows if str(r.get("ingestion_job_id") or "")==job_filter]
        st.info("Showing blocking exceptions for the current load.")
        if st.button("Show all active exceptions",key="pc_clear_exception_job_filter"):
            st.session_state.pop("pc_exception_job_filter",None)
            st.session_state.pop("pc_exception_core_only",None)
            st.rerun()
    if core_only:
        rows=[r for r in rows if r.get("staged_record_id") or r.get("target_table") in {"pc_entities","pc_assets","pc_mobile_assets","pc_events"}]

    open_count=sum(1 for r in rows if r.get("status")=="open")
    mine=sum(1 for r in rows if r.get("status")=="claimed" and r.get("assigned_to")==analyst)
    claimed=sum(1 for r in rows if r.get("status")=="claimed")
    high=sum(1 for r in rows if int(r.get("priority") or 0)>=80)
    a,b,c,d=st.columns(4)
    a.metric("Unassigned",open_count); b.metric("Mine",mine); c.metric("Claimed by team",claimed); d.metric("High priority",high)

    c1,c2=st.columns([2,1])
    with c1:
        workstreams=st.multiselect("Workstreams",["trade","intelligence","sanctions","cross"],
                                   default=["trade","intelligence","sanctions","cross"])
    with c2:
        view=st.selectbox("View",["My queue","Unassigned","All active"])

    if st.button("Claim next highest-priority item",type="primary",disabled=not workstreams):
        result=sb.rpc("pc_claim_next_exception",{
            "p_analyst":analyst,"p_analyst_name":analyst_name,"p_workstreams":workstreams
        }).execute().data or []
        if result:
            st.success("Claimed "+str(result[0].get("subject_name") or result[0].get("exception_type")))
        else:
            st.info("No unassigned exception matches those workstreams.")
        st.rerun()

    filtered=[r for r in rows if r.get("workstream") in workstreams]
    if view=="My queue":
        filtered=[r for r in filtered if r.get("status")=="claimed" and r.get("assigned_to")==analyst]
    elif view=="Unassigned":
        filtered=[r for r in filtered if r.get("status")=="open"]

    if not filtered:
        st.success("No exceptions in this view.")
        return

    display=pd.DataFrame([{
        "Priority":r.get("priority"),"Workstream":r.get("workstream"),
        "Subject":r.get("subject_name"),"Type":r.get("exception_type"),
        "Reason":r.get("reason"),"Status":r.get("status"),
        "Assigned":r.get("assigned_name") or r.get("assigned_to") or "—",
        "Age":r.get("created_at"),
        "ID":r.get("exception_id")
    } for r in filtered])
    st.dataframe(display,hide_index=True,use_container_width=True)

    choices={str(r["exception_id"]):r for r in filtered}
    selected_id=st.selectbox("Open exception",list(choices),
        format_func=lambda x:f"{choices[x].get('priority')} · {choices[x].get('workstream')} · {choices[x].get('subject_name') or choices[x].get('exception_type')}")
    item=choices[selected_id]
    st.markdown("### "+str(item.get("subject_name") or "Exception"))
    st.write(item.get("reason"))
    with st.expander("Evidence / planner context",expanded=True):
        st.json(item.get("context") or {},expanded=False)

    is_mine=item.get("status")=="claimed" and item.get("assigned_to")==analyst
    if item.get("status")=="open":
        if st.button("Claim this item"):
            got=sb.rpc("pc_claim_exception",{
                "p_exception":item["exception_id"],
                "p_analyst":analyst,
                "p_analyst_name":analyst_name
            }).execute().data or []
            if not got:
                st.warning("Another analyst claimed this item first.")
            st.rerun()
        return

    if not is_mine:
        st.info("This item is being worked by "+str(item.get("assigned_name") or item.get("assigned_to")))
        return

    if item.get("target_table")=="pc_events" and item.get("staged_record_id"):
        stages=(sb.table("pc_staged_records").select("*")
                .eq("staged_record_id",item["staged_record_id"])
                .limit(1).execute().data or [])
        if stages:
            stage=stages[0]
            p=stage.get("payload") or {}

            st.markdown("#### Staged event")
            st.dataframe(pd.DataFrame([{
                "Title":p.get("title") or stage.get("natural_key"),
                "Date":p.get("start_date"),
                "Type":p.get("event_type"),
                "Location":p.get("location"),
                "Description":p.get("description")
            }]),hide_index=True,use_container_width=True)

            candidates=_event_candidates(sb,stage)
            st.markdown("#### Canonical candidates")
            if candidates:
                st.dataframe(pd.DataFrame(candidates),hide_index=True,use_container_width=True)
                candidate_map={str(r["event_id"]):r for r in candidates}
                selected_canonical=st.selectbox(
                    "Existing event to match",
                    list(candidate_map),
                    key="event_candidate_"+selected_id,
                    format_func=lambda x:(candidate_map[x].get("title") or x)+" · "+
                                         str(candidate_map[x].get("start_date") or "date unknown"))
            else:
                selected_canonical=None
                st.info("No exact-title or same-date canonical event candidate was found.")

            st.caption("Choose the identity action. The decision is backed up, journalled, applied to this saved job and reconciled immediately.")
            a1,a2,a3=st.columns(3)

            with a1:
                if st.button("Match selected existing event",type="primary",
                             disabled=not selected_canonical,key="match_event_"+selected_id):
                    try:
                        result=_apply_event_decision_and_reconcile(
                            sb,item,analyst,analyst_name,"match_existing",selected_canonical)
                        st.success("Decision applied and job reconciled: "+str(result))
                        st.rerun()
                    except Exception as exc:
                        st.error("Event match held: "+str(exc))

            with a2:
                if st.button("Create as distinct event",key="new_event_"+selected_id):
                    try:
                        result=_apply_event_decision_and_reconcile(
                            sb,item,analyst,analyst_name,"create_new")
                        st.success("Decision applied and job reconciled: "+str(result))
                        st.rerun()
                    except Exception as exc:
                        st.error("Distinct-event decision held: "+str(exc))

            with a3:
                if st.button("Release to queue",key="release_event_"+selected_id):
                    ok=sb.rpc("pc_release_exception",{
                        "p_exception":item["exception_id"],
                        "p_analyst":analyst,
                        "p_version":item["version"]
                    }).execute().data
                    if not ok:
                        st.warning("Item changed since you opened it; refresh.")
                    st.rerun()
            return

    if item.get("target_table") in {"pc_entities","pc_assets","pc_mobile_assets"}:
        stage=_stage_for_exception(sb,item)
        if stage:
            p=stage.get("payload") or {}
            st.markdown("#### Staged identity")
            st.dataframe(pd.DataFrame([{
                "Name":p.get("name") or stage.get("natural_key"),
                "Type":p.get("entity_type") or p.get("asset_type") or p.get("subtype"),
                "Country":p.get("hq_country") or p.get("country"),
                "IMO":p.get("imo"),
            }]),hide_index=True,use_container_width=True)

            candidates,pk=_identity_candidates(sb,stage)
            st.markdown("#### Canonical candidates")
            selected_canonical=None
            if candidates and pk:
                st.dataframe(pd.DataFrame(candidates),hide_index=True,use_container_width=True)
                cmap={str(r[pk]):r for r in candidates if r.get(pk)}
                if cmap:
                    selected_canonical=st.selectbox(
                        "Existing record to match",
                        list(cmap),
                        key="identity_candidate_"+selected_id,
                        format_func=lambda x:
                            str(cmap[x].get("name") or x)+" · "+
                            str(cmap[x].get("hq_country") or cmap[x].get("country") or cmap[x].get("imo") or "")
                    )
            else:
                st.info("No exact or close canonical name candidate found.")

            st.caption("Choose the identity action. The saved job is repaired and reconciled immediately.")
            a1,a2,a3=st.columns(3)
            with a1:
                if st.button("Match selected existing",type="primary",
                             disabled=not selected_canonical,key="match_identity_"+selected_id):
                    try:
                        result=_apply_identity_decision_and_reconcile(
                            sb,item,analyst_name,"match_existing",selected_canonical)
                        st.success("Decision applied and job reconciled: "+str(result))
                        st.rerun()
                    except Exception as exc:
                        st.error("Identity match held: "+str(exc))
            with a2:
                if st.button("Create as distinct record",key="new_identity_"+selected_id):
                    try:
                        result=_apply_identity_decision_and_reconcile(
                            sb,item,analyst_name,"create_new")
                        st.success("Decision applied and job reconciled: "+str(result))
                        st.rerun()
                    except Exception as exc:
                        st.error("Create-new decision held: "+str(exc))
            with a3:
                if st.button("Release to queue",key="release_identity_"+selected_id):
                    ok=sb.rpc("pc_release_exception",{
                        "p_exception":item["exception_id"],
                        "p_analyst":analyst,
                        "p_version":item["version"]
                    }).execute().data
                    if not ok:
                        st.warning("Item changed since you opened it; refresh.")
                    st.rerun()
            return

    note=st.text_area("Resolution note / analyst decision",key="exception_note_"+selected_id,
                      placeholder="Record the evidence checked and the action taken.")
    x,y,z=st.columns(3)
    with x:
        if st.button("Release to queue"):
            ok=sb.rpc("pc_release_exception",{
                "p_exception":item["exception_id"],
                "p_analyst":analyst,
                "p_version":item["version"]
            }).execute().data
            if not ok:
                st.warning("Item changed since you opened it; refresh.")
            st.rerun()
    with y:
        if st.button("Resolve",type="primary",disabled=not note.strip()):
            ok=sb.rpc("pc_resolve_exception",{
                "p_exception":item["exception_id"],
                "p_analyst":analyst,
                "p_version":item["version"],
                "p_resolution":{"note":note.strip(),"analyst":analyst,
                                "resolved_at":datetime.now(timezone.utc).isoformat()},
                "p_dismiss":False
            }).execute().data
            if not ok:
                st.warning("Item changed since you opened it; refresh.")
            st.rerun()
    with z:
        if st.button("Dismiss as not actionable",disabled=not note.strip()):
            ok=sb.rpc("pc_resolve_exception",{
                "p_exception":item["exception_id"],
                "p_analyst":analyst,
                "p_version":item["version"],
                "p_resolution":{"note":note.strip(),"analyst":analyst,
                                "dismissed_at":datetime.now(timezone.utc).isoformat()},
                "p_dismiss":True
            }).execute().data
            if not ok:
                st.warning("Item changed since you opened it; refresh.")
            st.rerun()
