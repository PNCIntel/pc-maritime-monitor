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

    open_rows=(sb.table("pc_analyst_exceptions").select("exception_id,exception_key,status")
               .eq("ingestion_job_id",job).eq("status","open").limit(5000).execute().data or [])
    for row in open_rows:
        if row.get("exception_key") not in current:
            sb.table("pc_analyst_exceptions").update({
                "status":"resolved",
                "resolved_at":datetime.now(timezone.utc).isoformat(),
                "updated_at":datetime.now(timezone.utc).isoformat(),
                "resolution":{"method":"auto_cleared","reason":"Planner no longer reports this exception"},
                "version":1,
            }).eq("exception_id",row["exception_id"]).execute()


def _analyst_identity(ctx):
    email=(ctx or {}).get("email") or "staff"
    name=(ctx or {}).get("display_name") or email
    return str(email),str(name)


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
                "p_exception":item["exception_id"],"p_analyst":analyst,"p_analyst_name":analyst_name
            }).execute().data or []
            if not got:
                st.warning("Another analyst claimed this item first.")
            st.rerun()
        return

    if not is_mine:
        st.info("This item is being worked by "+str(item.get("assigned_name") or item.get("assigned_to")))
        return

    note=st.text_area("Resolution note / analyst decision",key="exception_note_"+selected_id,
                      placeholder="Record the evidence checked and the action taken.")
    x,y,z=st.columns(3)
    with x:
        if st.button("Release to queue"):
            ok=sb.rpc("pc_release_exception",{
                "p_exception":item["exception_id"],"p_analyst":analyst,"p_version":item["version"]
            }).execute().data
            if not ok: st.warning("Item changed since you opened it; refresh.")
            st.rerun()
    with y:
        if st.button("Resolve",type="primary",disabled=not note.strip()):
            ok=sb.rpc("pc_resolve_exception",{
                "p_exception":item["exception_id"],"p_analyst":analyst,"p_version":item["version"],
                "p_resolution":{"note":note.strip(),"analyst":analyst,"resolved_at":datetime.now(timezone.utc).isoformat()},
                "p_dismiss":False
            }).execute().data
            if not ok: st.warning("Item changed since you opened it; refresh.")
            st.rerun()
    with z:
        if st.button("Dismiss as not actionable",disabled=not note.strip()):
            ok=sb.rpc("pc_resolve_exception",{
                "p_exception":item["exception_id"],"p_analyst":analyst,"p_version":item["version"],
                "p_resolution":{"note":note.strip(),"analyst":analyst,"dismissed_at":datetime.now(timezone.utc).isoformat()},
                "p_dismiss":True
            }).execute().data
            if not ok: st.warning("Item changed since you opened it; refresh.")
            st.rerun()
