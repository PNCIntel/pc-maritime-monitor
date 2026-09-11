from __future__ import annotations
from pathlib import Path
import os, sys, json, uuid
import pandas as pd
import streamlit as st

ROOT=Path(__file__).resolve().parent
SHARED=ROOT/"shared"
if str(SHARED) not in sys.path: sys.path.insert(0,str(SHARED))
from pc_auth import require_super_admin, service_client
from pc_db import count_rows, safe_rows
try:
    from pc_ai import research as ai_research, configured as ai_configured
except Exception:
    ai_research=None
    ai_configured=lambda: False

st.set_page_config(page_title="P&C Power Admin",page_icon="◈",layout="wide")
st.markdown("""
<style>
:root{--bg:#07111f;--panel:#0d1a2b;--line:#28415f;--text:#f3f6fa;--muted:#b8c5d4;--gold:#d7b66a}
.stApp{background:var(--bg);color:var(--text)} [data-testid="stSidebar"]{background:#091725!important}
h1,h2,h3,p,label{color:var(--text)!important}.pc-card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px;margin-bottom:10px}.pc-k{color:var(--gold);font-size:.72rem;letter-spacing:.12em;text-transform:uppercase}
</style>""",unsafe_allow_html=True)

if os.getenv("PC_REQUIRE_AUTH","false").lower()=="true":
    ctx=require_super_admin()
else:
    ctx={"global_role":"super_admin","email":"migration-local"}

sb=service_client()
st.sidebar.markdown("<div class='pc-k'>Power & Corridors</div>",unsafe_allow_html=True)
st.sidebar.markdown("## Power Admin")
PAGES=["Dashboard","Migration","Organizations","Users & Access","Research Jobs","Trade System Builder","Batch Staging","Review Queue","Market Data","Governance & Quality"]
page=st.sidebar.radio("Workspace",PAGES)

if sb is None:
    st.warning("Supabase service connection is not configured yet. The app is valid and can be deployed now; add SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY to secrets before using database actions.")


def dataframe(rows):
    st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True) if rows else st.caption("No records.")

def title(t,copy=""):
    st.markdown(f"<div class='pc-k'>P&C INTERNAL</div><h1>{t}</h1>",unsafe_allow_html=True)
    if copy: st.caption(copy)

if page=="Dashboard":
    title("Platform control","One canonical data model; Trade, Intelligence and NERAI product entitlements; tenant workspaces; AI staging and review.")
    tables=[("Organizations","pc_organizations"),("Users","pc_profiles"),("Entities","pc_entities"),("Assets","pc_assets"),("Vessels / mobile","pc_mobile_assets"),("Events","pc_events"),("Staged changes","pc_staged_records"),("Open DQ issues","pc_data_quality_issues")]
    cols=st.columns(4)
    for i,(label,table) in enumerate(tables):
        with cols[i%4]: st.metric(label,count_rows(sb,table) if sb else 0)
    st.markdown("### Migration-night order")
    st.code("1 SQL 001 → 002 → 003\n2 seed_legacy_from_excel.py\n3 normalize_core.py\n4 SQL 004 → 005\n5 cleanup_validate.py\n6 verify_migration.py\n7 switch PC_DATA_BACKEND=supabase\n8 keep Excel fallback on until verified")

elif page=="Migration":
    title("Migration status")
    checks=[]
    for t in ["pc_legacy_sheet_rows","pc_sources","pc_entities","pc_assets","pc_mobile_assets","pc_relationships","pc_events","pc_event_locations","pc_event_links","pc_governance_links"]:
        checks.append({"Table":t,"Rows":count_rows(sb,t) if sb else 0})
    dataframe(checks)
    if sb:
        leakage=count_rows(sb,"pc_events",{"intelligence_visible":True,"event_nature":"CORPORATE"})
        if leakage: st.error(f"{leakage} corporate events are leaking into P&C Intelligence.")
        else: st.success("No corporate-event leakage detected in P&C Intelligence routing.")

elif page=="Organizations":
    title("Organizations & subscriptions","P&C controls seat limits and product entitlements centrally.")
    orgs=safe_rows(sb,"pc_organizations","*",500) if sb else []
    dataframe(orgs)
    if sb:
        with st.expander("Create organization"):
            with st.form("new_org"):
                name=st.text_input("Organization name")
                slug=st.text_input("Slug")
                seats=st.number_input("Seat limit",min_value=1,value=5)
                if st.form_submit_button("Create") and name and slug:
                    sb.table("pc_organizations").insert({"name":name,"slug":slug,"seat_limit":int(seats)}).execute(); st.rerun()
        if orgs:
            labels={o['organization_id']:o['name'] for o in orgs}
            oid=st.selectbox("Manage organization",list(labels),format_func=lambda x:labels[x])
            org=next(o for o in orgs if o['organization_id']==oid)
            c1,c2=st.columns(2)
            with c1:
                seats=st.number_input("Seat limit",min_value=1,value=int(org.get('seat_limit') or 5),key="seat_edit")
                if st.button("Update seat limit"):
                    sb.table("pc_organizations").update({"seat_limit":int(seats)}).eq("organization_id",oid).execute(); st.rerun()
            with c2:
                ents=safe_rows(sb,"pc_organization_entitlements","*",100,{"organization_id":oid})
                dataframe(ents)
                product=st.selectbox("Product",["TRADE","INTELLIGENCE","NERAI"])
                tier=st.selectbox("Tier",["base","professional","enterprise","add-on"])
                active=st.checkbox("Active",True)
                if st.button("Set entitlement"):
                    sb.table("pc_organization_entitlements").upsert({"organization_id":oid,"product_code":product,"tier":tier,"active":active},on_conflict="organization_id,product_code").execute(); st.rerun()

elif page=="Users & Access":
    title("Users & access","P&C super-admin view across organizations, roles and product access.")
    profiles=safe_rows(sb,"pc_profiles","user_id,email,display_name,global_role,active",1000) if sb else []
    members=safe_rows(sb,"pc_organization_members","organization_id,user_id,role,active,joined_at",2000) if sb else []
    st.markdown("### Profiles"); dataframe(profiles)
    st.markdown("### Organization memberships"); dataframe(members)
    if sb and profiles:
        orgs=safe_rows(sb,"pc_organizations","organization_id,name,seat_limit",500)
        pmap={p['user_id']:(p.get('email') or p['user_id']) for p in profiles}; omap={o['organization_id']:o['name'] for o in orgs}
        with st.expander("Assign existing user to organization"):
            uid=st.selectbox("User",list(pmap),format_func=lambda x:pmap[x])
            oid=st.selectbox("Organization",list(omap),format_func=lambda x:omap[x])
            role=st.selectbox("Role",["org_admin","senior_analyst","analyst","executive","viewer"])
            if st.button("Assign / update role"):
                current=count_rows(sb,"pc_organization_members",{"organization_id":oid,"active":True})
                lim=next((int(o.get('seat_limit') or 0) for o in orgs if o['organization_id']==oid),0)
                exists=any(m['organization_id']==oid and m['user_id']==uid for m in members)
                if not exists and lim and current>=lim: st.error("Seat limit reached.")
                else:
                    sb.table("pc_organization_members").upsert({"organization_id":oid,"user_id":uid,"role":role,"active":True},on_conflict="organization_id,user_id").execute(); st.rerun()

elif page=="Research Jobs":
    title("AI research & enrichment","Natural-language research jobs stage proposed data; they do not write directly to canonical tables.")
    jobs=safe_rows(sb,"pc_ingestion_jobs","*",200,order="created_at") if sb else []
    dataframe(jobs)
    prompt=st.text_area("Research query",placeholder="Research all African ports and propose missing ports, operators, terminals, rail links and authoritative sources.",height=130)
    context=st.selectbox("Product context",["TRADE","INTELLIGENCE","NERAI"])
    use_web=st.checkbox("Use current web research",True)
    if st.button("Run AI research job",disabled=not bool(prompt)):
        if not sb: st.error("Supabase service connection required.")
        elif not ai_configured(): st.error("Configure OPENAI_API_KEY and OPENAI_MODEL.")
        else:
            job=sb.table("pc_ingestion_jobs").insert({"job_type":"AI_RESEARCH","title":prompt[:100],"query_text":prompt,"status":"running","requested_by":None}).execute().data[0]
            try:
                result=ai_research(prompt,context,use_web)
                sb.table("pc_staged_records").insert({"ingestion_job_id":job['ingestion_job_id'],"target_table":"research_bundle","natural_key":str(job['ingestion_job_id']),"action":"REVIEW","payload":result,"confidence":0.7,"validation_status":"pending","review_status":"pending"}).execute()
                sb.table("pc_ingestion_jobs").update({"status":"completed","stats":{"research_bundle":1}}).eq("ingestion_job_id",job['ingestion_job_id']).execute(); st.success("Research staged for review.")
            except Exception as exc:
                sb.table("pc_ingestion_jobs").update({"status":"failed","error_text":str(exc)}).eq("ingestion_job_id",job['ingestion_job_id']).execute(); st.error(str(exc))

elif page=="Trade System Builder":
    title("Trade system builder","Build the global trade-system graph in controlled research campaigns: energy, industrial assets, flows, markets, ports, corridors and macro layers.")
    if not sb:
        st.info("Configure Supabase before running builder operations.")
    else:
        tables=[
            ("Energy assets","pc_energy_assets"),("Industrial assets","pc_industrial_assets"),("Logistics facilities","pc_logistics_facilities"),
            ("Market instruments","pc_market_instruments"),("Market prices","pc_market_prices"),("Trade flows","pc_trade_flows"),
            ("Supply series","pc_supply_series"),("Port metrics","pc_port_metrics"),("Transport routes","pc_transport_routes"),
            ("Chokepoints","pc_chokepoints"),("Macro indicators","pc_macro_indicators"),("Provenance observations","pc_observations")
        ]
        cols=st.columns(4)
        for i,(label,table) in enumerate(tables):
            with cols[i%4]: st.metric(label,count_rows(sb,table))
        tabs=st.tabs(["Research campaigns","Current normalization","Source registry","Build order"])
        with tabs[0]:
            st.markdown("### One-command research campaigns")
            examples=[
                "Research all African ports and create proposed port, terminal, governance, rail, road, free-zone and major commodity-flow records with authoritative sources.",
                "Research all refineries in the GCC and Red Sea region. Link owners, operators, capacities, products, ports, terminals, pipelines, storage and relevant market benchmarks.",
                "Research Brookfield, OMERS and Macquarie transport and logistics investments from 2016 to present. Stage acquisitions, stakes, assets, values and ownership/control relationships.",
                "Research major global mines and export chains for iron ore, bauxite, copper, nickel, cobalt, lithium, manganese, phosphate and potash. Link mine to rail, port and destination markets.",
                "Research all major port-linked logistics parks, free zones and inland terminals in Africa and the Gulf. Stage operator, owner, capacity and connectivity relationships."
            ]
            for e in examples: st.code(e)
            st.caption("Use Research Jobs to run these through the AI staging workflow. Nothing is written directly to canonical production tables.")
        with tabs[1]:
            st.markdown("### Normalize the data we already have")
            st.code("python scripts/normalize_trade_expansion.py")
            st.caption("This conservatively maps existing infrastructure, logistics-real-estate, company-listing and rail-network records into the expanded schema without inventing missing fields.")
        with tabs[2]:
            st.markdown("### Seed the open-source registry")
            st.code("python scripts/seed_open_source_registry.py")
            dataframe(safe_rows(sb,"pc_sources","source_id,publisher,source_name,source_type,coverage,url,license_name,redistribution_status,attribution_required,active",500,order="updated_at"))
        with tabs[3]:
            st.code("""1. Run sql/009_trade_system_expansion.sql
2. python scripts/seed_open_source_registry.py
3. python scripts/seed_market_instruments.py
4. python scripts/normalize_trade_expansion.py
5. Optional: python scripts/ingest_world_bank_macro.py --start 2016
6. Optional: python scripts/stage_ourairports.py
7. Run source-specific research/ingestion jobs
8. Review staged enrichments
9. Approve canonical writes
10. Verify client views""")

elif page=="Batch Staging":
    title("Batch staging","Upload structured CSV/JSON for AI-assisted or deterministic review before canonical writes.")
    target=st.selectbox("Target table",["pc_entities","pc_assets","pc_mobile_assets","pc_relationships","pc_events","pc_transactions","pc_security_compliance","pc_energy_assets","pc_industrial_assets","pc_logistics_facilities","pc_market_instruments","pc_market_prices","pc_trade_flows","pc_supply_series","pc_port_metrics","pc_port_capabilities","pc_transport_routes","pc_chokepoints","pc_macro_indicators","pc_observations","pc_market_reports","pc_market_observations"])
    up=st.file_uploader("CSV or JSON",type=["csv","json"])
    if up:
        if up.name.lower().endswith('.csv'): rows=pd.read_csv(up).fillna('').to_dict('records')
        else:
            obj=json.load(up); rows=obj if isinstance(obj,list) else obj.get('records',[obj])
        st.caption(f"{len(rows)} incoming rows")
        st.dataframe(pd.DataFrame(rows).head(50),use_container_width=True)
        if st.button("Stage batch"):
            if not sb: st.error("Supabase required.")
            else:
                job=sb.table("pc_ingestion_jobs").insert({"job_type":"BATCH_IMPORT","title":up.name,"status":"running"}).execute().data[0]
                payloads=[{"ingestion_job_id":job['ingestion_job_id'],"target_table":target,"natural_key":str(i),"action":"REVIEW","payload":r,"confidence":1.0,"validation_status":"pending","review_status":"pending"} for i,r in enumerate(rows,1)]
                for i in range(0,len(payloads),250): sb.table("pc_staged_records").insert(payloads[i:i+250]).execute()
                sb.table("pc_ingestion_jobs").update({"status":"completed","stats":{"rows":len(rows)}}).eq("ingestion_job_id",job['ingestion_job_id']).execute(); st.success("Batch staged.")

elif page=="Review Queue":
    title("Review queue","Analyst review of AI-assisted and batch-staged proposals before any canonical write.")

    if not sb:
        st.error("Supabase is required for the review queue.")
    else:
        rows = safe_rows(
            sb,
            "pc_staged_records",
            "staged_record_id,ingestion_job_id,target_table,natural_key,action,confidence,validation_status,review_status,payload,current_record,source_id,created_at",
            500,
            {"review_status":"pending"},
            "created_at"
        )

        if not rows:
            st.success("No pending staged records.")
        else:
            import pandas as _pd
            import json as _json

            review_df = _pd.DataFrame(rows)

            # Compact reviewer-facing summary table.
            summary_cols = [
                c for c in [
                    "target_table",
                    "natural_key",
                    "action",
                    "confidence",
                    "validation_status",
                    "review_status",
                    "source_id",
                    "created_at",
                ] if c in review_df.columns
            ]

            st.caption(f"{len(review_df):,} pending staged records")
            st.dataframe(
                review_df[summary_cols] if summary_cols else review_df,
                use_container_width=True,
                hide_index=True,
                height=min(420, 40 + 35 * max(1, len(review_df))),
            )

            # Friendly selector text rather than UUID-only selection.
            def _record_label(r):
                nk = r.get("natural_key") or "(no natural key)"
                tt = r.get("target_table") or "(no table)"
                conf = r.get("confidence")
                conf_txt = f"{float(conf):.2f}" if conf not in (None, "") else "n/a"
                return f"{tt} | {nk} | confidence {conf_txt}"

            labels = [_record_label(r) for r in rows]
            selected_label = st.selectbox("Open staged record", labels, index=0)
            row = rows[labels.index(selected_label)]

            payload = row.get("payload") or {}
            current_record = row.get("current_record") or {}

            # Detail header
            st.markdown("### Record review")
            a,b,c,d = st.columns(4)
            a.metric("Target table", row.get("target_table") or "—")
            b.metric("Action", row.get("action") or "—")
            c.metric("Confidence", row.get("confidence") if row.get("confidence") is not None else "—")
            d.metric("Validation", row.get("validation_status") or "pending")

            st.caption(
                f"Natural key: {row.get('natural_key') or '—'}  ·  "
                f"Created: {row.get('created_at') or '—'}  ·  "
                f"Staged record: {row.get('staged_record_id')}"
            )

            left,right = st.columns([1.15,0.85])

            with left:
                st.markdown("#### Proposed payload")

                # Render payload as readable field/value rows.
                if isinstance(payload, dict):
                    flat_rows=[]
                    for k,v in payload.items():
                        if isinstance(v,(dict,list)):
                            display=_json.dumps(v,ensure_ascii=False,indent=2)
                        else:
                            display=v
                        flat_rows.append({"Field":k,"Proposed value":display})
                    st.dataframe(
                        _pd.DataFrame(flat_rows),
                        use_container_width=True,
                        hide_index=True,
                        height=min(600, 60 + 34 * max(1, len(flat_rows))),
                    )
                else:
                    st.code(str(payload))

                # Extract source links from common payload/metadata structures.
                st.markdown("#### Sources")
                source_rows=[]

                def _add_source(obj):
                    if not isinstance(obj,dict):
                        return
                    url=obj.get("url") or obj.get("source_url")
                    if not url:
                        return
                    source_rows.append({
                        "Publisher": obj.get("publisher") or obj.get("source_name") or "",
                        "Title": obj.get("title") or obj.get("source_title") or "",
                        "URL": url,
                    })

                if isinstance(payload,dict):
                    meta=payload.get("metadata") or {}
                    if isinstance(meta,dict):
                        for s in meta.get("research_sources") or []:
                            _add_source(s)
                        for s in meta.get("sources") or []:
                            _add_source(s)
                    for s in payload.get("sources") or []:
                        _add_source(s)

                if source_rows:
                    for i,s in enumerate(source_rows,1):
                        label = s["Title"] or s["Publisher"] or f"Source {i}"
                        st.markdown(f"{i}. [{label}]({s['URL']})")
                        if s["Publisher"] and s["Publisher"] != label:
                            st.caption(s["Publisher"])
                else:
                    st.info("No source URLs were embedded in this staged payload.")

            with right:
                st.markdown("#### Existing canonical context")

                # Query likely duplicate/current candidates conservatively.
                target_table = row.get("target_table")
                natural_key = row.get("natural_key")
                candidates=[]

                try:
                    if target_table=="pc_entities":
                        name = payload.get("name") if isinstance(payload,dict) else None
                        if name:
                            candidates = safe_rows(sb,"pc_entities","entity_id,name,entity_type,country,record_status",20)
                            candidates = [x for x in candidates if str(x.get("name","")).strip().casefold()==str(name).strip().casefold()]
                    elif target_table=="pc_assets":
                        name = payload.get("name") if isinstance(payload,dict) else None
                        country = payload.get("country") if isinstance(payload,dict) else None
                        candidates = safe_rows(sb,"pc_assets","asset_id,name,asset_type,subtype,country,region_city,status,record_status",100)
                        if name:
                            nn=str(name).strip().casefold()
                            candidates=[x for x in candidates if str(x.get("name","")).strip().casefold()==nn]
                        if country and candidates:
                            cc=str(country).strip().casefold()
                            candidates=[x for x in candidates if not x.get("country") or str(x.get("country","")).strip().casefold()==cc]
                    elif target_table=="pc_mobile_assets":
                        imo = payload.get("imo") if isinstance(payload,dict) else None
                        name = payload.get("name") if isinstance(payload,dict) else None
                        candidates = safe_rows(sb,"pc_mobile_assets","mobile_asset_id,name,imo,mobile_type,flag,status,record_status",100)
                        if imo:
                            candidates=[x for x in candidates if str(x.get("imo","")).strip()==str(imo).strip()]
                        elif name:
                            nn=str(name).strip().casefold()
                            candidates=[x for x in candidates if str(x.get("name","")).strip().casefold()==nn]
                    elif target_table=="pc_transport_routes":
                        rid = payload.get("route_id") if isinstance(payload,dict) else None
                        if rid:
                            candidates = safe_rows(sb,"pc_transport_routes","route_id,route_name,mode,current_status",50,{"route_id":rid})
                except Exception:
                    candidates=[]

                if current_record:
                    st.caption("Current record supplied by staging process")
                    st.json(current_record)

                if candidates:
                    st.warning(f"Potential existing canonical match{'es' if len(candidates)!=1 else ''}: {len(candidates)}")
                    st.dataframe(_pd.DataFrame(candidates),use_container_width=True,hide_index=True)
                else:
                    st.success("No obvious exact canonical match detected by the review UI.")

                st.markdown("#### Reviewer decision")

                notes = st.text_area(
                    "Reviewer note",
                    placeholder="Reason for approval, rejection, or requested changes.",
                    key=f"note_{row['staged_record_id']}"
                )

                c1,c2,c3 = st.columns(3)

                if c1.button("Approve", type="primary", key=f"approve_{row['staged_record_id']}"):
                    sb.table("pc_staged_records").update({
                        "review_status":"approved",
                        "reviewed_at":"now()"
                    }).eq("staged_record_id",row["staged_record_id"]).execute()
                    st.success("Record approved for apply.")
                    st.rerun()

                if c2.button("Needs changes", key=f"changes_{row['staged_record_id']}"):
                    payload_update = payload if isinstance(payload,dict) else {"raw_payload":payload}
                    if notes:
                        meta = payload_update.get("metadata") or {}
                        if not isinstance(meta,dict):
                            meta={}
                        meta["review_note"]=notes
                        payload_update["metadata"]=meta
                    sb.table("pc_staged_records").update({
                        "review_status":"needs_changes",
                        "payload":payload_update,
                        "reviewed_at":"now()"
                    }).eq("staged_record_id",row["staged_record_id"]).execute()
                    st.warning("Record marked as needing changes.")
                    st.rerun()

                if c3.button("Reject", key=f"reject_{row['staged_record_id']}"):
                    payload_update = payload if isinstance(payload,dict) else {"raw_payload":payload}
                    if notes:
                        meta = payload_update.get("metadata") or {}
                        if not isinstance(meta,dict):
                            meta={}
                        meta["review_note"]=notes
                        payload_update["metadata"]=meta
                    sb.table("pc_staged_records").update({
                        "review_status":"rejected",
                        "payload":payload_update,
                        "reviewed_at":"now()"
                    }).eq("staged_record_id",row["staged_record_id"]).execute()
                    st.error("Record rejected.")
                    st.rerun()

                st.markdown("---")
                st.markdown("#### Apply control")
                st.caption(
                    "Approval and application remain separate. This protects the canonical database "
                    "from accidental AI writes."
                )

                if row.get("review_status")=="approved":
                    st.info("This record is approved. Use the canonical apply workflow to write it.")
                else:
                    st.caption("Approve the record first; canonical apply remains intentionally disabled here.")

elif page=="Market Data":
    title("Freight & commodity market data","Attributed public-source market observations, initially seeded from The Signal Group Weekly Market Monitor. Nothing is client-visible until approved.")
    if not sb:
        st.info("Configure Supabase to manage market data.")
    else:
        reports=safe_rows(sb,"pc_market_reports","market_report_id,provider,report_family,report_title,report_date,week_number,source_url,review_status,client_visible,ingested_at",500,order="report_date")
        obs=safe_rows(sb,"pc_market_observations","market_observation_id,market_report_id,observation_date,market,vessel_class,route_code,commodity,metric_family,metric_name,value_numeric,value_text,unit,currency,change_wow,change_yoy,pc_market_signal,pc_direction,confidence,review_status,client_visible",1000,order="observation_date")
        c1,c2,c3,c4=st.columns(4)
        c1.metric("Reports",len(reports)); c2.metric("Observations",len(obs))
        c3.metric("Pending review",sum(1 for r in obs if r.get("review_status")=="pending"))
        c4.metric("Client-visible",sum(1 for r in obs if r.get("client_visible")))
        tabs=st.tabs(["Reports","Observation review","Ingestion commands"])
        with tabs[0]:
            dataframe(reports)
        with tabs[1]:
            pending=[r for r in obs if r.get("review_status")=="pending"]
            dataframe(pending[:250])
            if pending:
                oid=st.selectbox("Open market observation",[r['market_observation_id'] for r in pending],format_func=lambda x: next((f"{r.get('observation_date','')} · {r.get('route_code') or r.get('vessel_class') or r.get('commodity') or r.get('market','')} · {r.get('metric_name','')}" for r in pending if r['market_observation_id']==x),x))
                row=next(r for r in pending if r['market_observation_id']==oid)
                st.json(row)
                c1,c2,c3=st.columns(3)
                if c1.button("Approve + publish to Trade"):
                    sb.table("pc_market_observations").update({"review_status":"approved","client_visible":True}).eq("market_observation_id",oid).execute()
                    sb.table("pc_market_reports").update({"review_status":"approved","client_visible":True}).eq("market_report_id",row['market_report_id']).execute(); st.rerun()
                if c2.button("Approve internal only"):
                    sb.table("pc_market_observations").update({"review_status":"approved","client_visible":False}).eq("market_observation_id",oid).execute(); st.rerun()
                if c3.button("Reject market observation"):
                    sb.table("pc_market_observations").update({"review_status":"rejected","client_visible":False}).eq("market_observation_id",oid).execute(); st.rerun()
        with tabs[2]:
            st.markdown("#### Initial attributed seed")
            st.code("python scripts/seed_market_sample.py")
            st.markdown("#### Research the 2026 dry-bulk + tanker archive")
            st.code("python scripts/ingest_signal_group.py --year 2026 --families dry,tanker --weeks 1-36")
            st.caption("The crawler uses only publicly accessible pages, stores attribution and structured facts rather than article copies, and leaves extracted observations pending until analyst approval.")

elif page=="Governance & Quality":
    title("Governance & data quality")
    tabs=st.tabs(["Port governance","Quality issues"])
    with tabs[0]:
        gov=safe_rows(sb,"pc_governance_links","*",500) if sb else []; dataframe(gov)
        if sb:
            st.markdown("#### Add governance link")
            with st.form("gov_link"):
                governed_id=st.text_input("Port / asset ID",placeholder="PORTG0225")
                authority=st.text_input("Authority entity ID",placeholder="COMP_BUSAN_PA")
                role=st.text_input("Governance role",value="PORT AUTHORITY")
                note=st.text_input("Model note")
                if st.form_submit_button("Add") and governed_id and authority:
                    sb.table("pc_governance_links").insert({"governed_type":"asset","governed_id":governed_id,"authority_entity_id":authority,"authority_name":authority,"governance_role":role,"model_note":note}).execute(); st.rerun()
    with tabs[1]:
        issues=safe_rows(sb,"pc_data_quality_issues","*",500,{"status":"open"},"created_at") if sb else []; dataframe(issues)
