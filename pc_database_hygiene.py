import re
import pandas as pd
import streamlit as st

def _norm(v):
    return " ".join(re.findall(r"[a-z0-9]+", str(v or "").casefold()))

def _generated(v):
    s=str(v or "").upper()
    return any(x in s for x in ("_AUTO_","ENTITY_AUTO","ASSET_AUTO","MOBILE_AUTO","ENTITY_AI_","ASSET_AI_","MOBILE_AI_"))

def _safe_rows(sb, view):
    try:
        return sb.table(view).select("*").limit(1000).execute().data or []
    except Exception:
        return []

def _candidate_rows(sb):
    out=[]
    for view,obj in [
        ("pc_v_duplicate_entity_candidates","entity"),
        ("pc_v_duplicate_asset_candidates","asset"),
        ("pc_v_duplicate_mobile_asset_candidates","mobile_asset"),
    ]:
        for r in _safe_rows(sb,view):
            ids=list(r.get("canonical_ids") or [])
            names=list(r.get("names") or [])
            if len(ids)<2:
                continue
            # Conservative survivor preference: established IDs beat generated IDs.
            established=[x for x in ids if not _generated(x)]
            if len(established)==1:
                survivor=established[0]
                duplicates=[x for x in ids if x!=survivor]
            else:
                survivor=ids[0]
                duplicates=ids[1:]
            for dup in duplicates:
                out.append({
                    "object_type":obj,
                    "survivor_id":str(survivor),
                    "duplicate_id":str(dup),
                    "name":" / ".join(str(x) for x in names if x)[:250],
                    "reason":"exact duplicate candidate",
                    "safe":bool(len(established)==1 or obj=="mobile_asset"),
                })
    return out

def _event_candidates(sb):
    try:
        rows=(sb.table("pc_events").select("event_id,title,start_date,event_type,location")
              .order("start_date",desc=True).limit(3000).execute().data or [])
    except Exception:
        return []
    groups={}
    for r in rows:
        key=(
            str(r.get("start_date") or "")[:10],
            _norm(r.get("title")),
            _norm(r.get("event_type")),
            _norm(r.get("location")),
        )
        if not key[1]:
            continue
        groups.setdefault(key,[]).append(r)
    out=[]
    for _,members in groups.items():
        if len(members)<2:
            continue
        survivor=sorted(members,key=lambda x:(not _generated(x.get("event_id")), str(x.get("event_id"))),reverse=True)[0]
        for dup in members:
            if dup.get("event_id")==survivor.get("event_id"):
                continue
            out.append({
                "object_type":"event",
                "survivor_id":str(survivor.get("event_id")),
                "duplicate_id":str(dup.get("event_id")),
                "name":str(survivor.get("title") or ""),
                "reason":"exact date/title/type/location duplicate",
                "safe":True,
            })
    return out

def _merge(sb,row):
    return sb.rpc("pc_merge_canonical_object",{
        "p_object_type":row["object_type"],
        "p_survivor_id":row["survivor_id"],
        "p_duplicate_id":row["duplicate_id"],
        "p_delete_duplicate":True,
        "p_notes":"Power Admin canonical hygiene cleanup"
    }).execute().data

def render_database_hygiene(sb):
    st.title("Database hygiene")
    st.caption("Canonical duplicate cleanup. Safe candidates can be merged; ambiguous identities stay for analyst review.")

    try:
        summary=sb.table("pc_v_identity_hygiene_summary").select("*").execute().data or []
    except Exception:
        summary=[]
    if summary:
        st.subheader("Identity hygiene summary")
        st.dataframe(pd.DataFrame(summary),hide_index=True,use_container_width=True)

    candidates=_candidate_rows(sb)+_event_candidates(sb)
    safe=[x for x in candidates if x.get("safe")]
    review=[x for x in candidates if not x.get("safe")]

    c1,c2,c3=st.columns(3)
    c1.metric("Safe merge candidates",len(safe))
    c2.metric("Review-only candidates",len(review))
    c3.metric("Total candidates",len(candidates))

    if safe:
        st.subheader("Safe merge preview")
        st.dataframe(pd.DataFrame(safe),hide_index=True,use_container_width=True)
        confirm=st.checkbox("I understand these merges rewire references and delete duplicate canonical shells.")
        if st.button("Apply safe canonical cleanup",type="primary",disabled=not confirm,use_container_width=True):
            results=[]
            progress=st.progress(0.0)
            for i,row in enumerate(safe):
                try:
                    results.append(_merge(sb,row))
                except Exception as exc:
                    results.append({"status":"HELD","object_type":row["object_type"],
                                    "duplicate_id":row["duplicate_id"],"error":str(exc)})
                progress.progress((i+1)/len(safe))
            st.session_state["pc_hygiene_results"]=results
            st.cache_data.clear()
            st.rerun()
    else:
        st.success("No safe duplicate candidates found.")

    if st.session_state.get("pc_hygiene_results"):
        st.subheader("Last cleanup run")
        results=st.session_state["pc_hygiene_results"]
        st.dataframe(pd.DataFrame(results),hide_index=True,use_container_width=True)

    if review:
        st.subheader("Needs analyst review")
        st.caption("These are deliberately not auto-merged.")
        st.dataframe(pd.DataFrame(review),hide_index=True,use_container_width=True)

    st.divider()
    st.subheader("Merge audit")
    try:
        audit=(sb.table("pc_canonical_merge_audit").select("*")
               .order("merged_at",desc=True).limit(100).execute().data or [])
    except Exception as exc:
        audit=[]
        st.caption("Merge audit unavailable. Apply migrations 043 and 044 if they are not installed.")
    if audit:
        st.dataframe(pd.DataFrame(audit),hide_index=True,use_container_width=True)
