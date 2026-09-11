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

# ---------------------------------------------------------------------------
# Controlled AI staging + canonical apply helpers
# ---------------------------------------------------------------------------

AI_ALLOWED_TABLES = {
    "pc_entities",
    "pc_assets",
    "pc_mobile_assets",
    "pc_relationships",
    "pc_events",
    "pc_transactions",
    "pc_security_compliance",
    "pc_energy_assets",
    "pc_energy_asset_connections",
    "pc_industrial_assets",
    "pc_logistics_facilities",
    "pc_market_instruments",
    "pc_market_exposure_links",
    "pc_trade_flows",
    "pc_supply_series",
    "pc_port_metrics",
    "pc_port_capabilities",
    "pc_transport_routes",
    "pc_chokepoints",
    "pc_macro_indicators",
    "pc_observations",
}

# Conflict keys used only when a staged record has enough information to upsert safely.
APPLY_CONFLICT_KEYS = {
    "pc_entities": "entity_id",
    "pc_assets": "asset_id",
    "pc_mobile_assets": "mobile_asset_id",
    "pc_relationships": "relationship_id",
    "pc_events": "event_id",
    "pc_transactions": "transaction_id",
    "pc_security_compliance": "security_compliance_id",
    "pc_energy_assets": "asset_id",
    "pc_energy_asset_connections": "connection_id",
    "pc_industrial_assets": "asset_id",
    "pc_logistics_facilities": "asset_id",
    "pc_market_instruments": "market_instrument_id",
    "pc_market_exposure_links": "target_type,target_id,market_instrument_id,exposure_type",
    "pc_trade_flows": "trade_flow_id",
    "pc_supply_series": "supply_series_id",
    "pc_port_metrics": "port_metric_id",
    "pc_port_capabilities": "port_capability_id",
    "pc_transport_routes": "route_id",
    "pc_chokepoints": "chokepoint_id",
    "pc_macro_indicators": "macro_indicator_id",
    "pc_observations": "observation_id",
}

AI_CAMPAIGNS = {
    "African ports & terminals": (
        "Research major commercial ports, container terminals, dry ports and "
        "port-linked logistics zones across Africa. Prioritize operator, owner, "
        "terminal name, country, city, capacity where explicitly sourced, rail "
        "or road connectivity, recent investment, and source URLs. Propose only "
        "records supported by public evidence."
    ),
    "GCC & Red Sea refineries": (
        "Research operational refineries, LNG plants, gas-processing facilities, "
        "oil export terminals and major storage hubs in the GCC and Red Sea. "
        "Capture owner/operator, location, explicit capacity, operating status, "
        "port/pipeline connections and source URLs."
    ),
    "Mines & export chains": (
        "Research major global mines and export chains for iron ore, bauxite, "
        "copper, nickel, cobalt, lithium, manganese, phosphate and potash. Link "
        "mine or industrial asset to rail/road, export port and destination "
        "markets only where supported by evidence."
    ),
    "Logistics parks & inland hubs": (
        "Research major port-linked logistics parks, free zones, economic zones, "
        "warehouses and inland/intermodal terminals in Africa, the Gulf and Asia. "
        "Capture owner, operator, area/capacity where explicit, port/rail/road "
        "connections, investment values and source URLs."
    ),
    "Infrastructure investors": (
        "Research transport, port, terminal, rail, logistics, airport and related "
        "infrastructure acquisitions or investments by Brookfield, KKR, Macquarie, "
        "OMERS, GIP and other major infrastructure investors since 2018. Capture "
        "transaction date, target, stake, value, geography and evidence."
    ),
    "Custom research": "",
}

AI_OUTPUT_CONTRACT = """
Return JSON with this shape:
{
  "records": [
    {
      "target_table": "one allowed P&C table",
      "natural_key": "stable proposed natural key",
      "action": "REVIEW",
      "confidence": 0.0,
      "payload": {
        "...": "fields supported by evidence",
        "metadata": {
          "research_sources": [
            {"url": "...", "publisher": "...", "title": "..."}
          ]
        }
      }
    }
  ],
  "sources": [],
  "conflicts": [],
  "notes": []
}

Allowed target tables:
""" + ", ".join(sorted(AI_ALLOWED_TABLES))


def _jsonable(v):
    if isinstance(v, dict):
        return {k:_jsonable(x) for k,x in v.items()}
    if isinstance(v, list):
        return [_jsonable(x) for x in v]
    if pd.isna(v) if not isinstance(v,(dict,list,str,bool)) else False:
        return None
    return v


def _record_key(payload, natural_key=""):
    if natural_key:
        return str(natural_key)
    if isinstance(payload,dict):
        for k in (
            "entity_id","asset_id","mobile_asset_id","relationship_id","event_id",
            "transaction_id","route_id","chokepoint_id","market_instrument_id",
            "trade_flow_id","supply_series_id","observation_id"
        ):
            if payload.get(k):
                return str(payload[k])
        for k in ("name","title","route_name"):
            if payload.get(k):
                return str(payload[k])
    return str(uuid.uuid4())


def stage_ai_result(sb, job_id, result):
    """Stage structured AI result. Returns (staged_count, rejected_count)."""
    records=(result or {}).get("records") or []
    staged=[]
    rejected=0

    for rec in records:
        if not isinstance(rec,dict):
            rejected+=1
            continue

        table=str(rec.get("target_table") or "").strip()
        payload=rec.get("payload")

        if table not in AI_ALLOWED_TABLES or not isinstance(payload,dict):
            rejected+=1
            continue

        staged.append({
            "ingestion_job_id":job_id,
            "target_table":table,
            "natural_key":_record_key(payload,rec.get("natural_key") or ""),
            "action":"REVIEW",
            "payload":_jsonable(payload),
            "confidence":rec.get("confidence"),
            "validation_status":"pending",
            "review_status":"pending",
        })

    for i in range(0,len(staged),100):
        sb.table("pc_staged_records").insert(staged[i:i+100]).execute()

    return len(staged),rejected


def apply_staged_record(sb, row, edited_payload=None):
    """Apply one approved staged record to a canonical table.

    Safety properties:
    - target table must be allow-listed
    - record must already be approved
    - payload must be a JSON object
    - upsert is used only when all configured conflict keys exist
    - failed canonical writes do not mark the staged record as applied
    """
    if row.get("review_status")!="approved":
        raise ValueError("Record must be approved before apply.")

    table=str(row.get("target_table") or "").strip()
    if table not in AI_ALLOWED_TABLES:
        raise ValueError(f"Target table is not allowed for canonical apply: {table}")

    payload=edited_payload if edited_payload is not None else row.get("payload")
    if not isinstance(payload,dict) or not payload:
        raise ValueError("Canonical payload must be a non-empty JSON object.")

    payload=_jsonable(payload)
    conflict=APPLY_CONFLICT_KEYS.get(table)
    keys=[x.strip() for x in conflict.split(",")] if conflict else []
    can_upsert=bool(keys) and all(payload.get(k) not in (None,"") for k in keys)

    # Store the analyst-edited payload back into staging before canonical apply,
    # so the reviewed proposal and the applied proposal remain identical.
    if edited_payload is not None:
        sb.table("pc_staged_records").update({"payload":payload}).eq(
            "staged_record_id",row["staged_record_id"]
        ).execute()

    if can_upsert:
        result=sb.table(table).upsert(payload,on_conflict=conflict).execute()
        write_mode="upsert"
    else:
        result=sb.table(table).insert(payload).execute()
        write_mode="insert"

    # Only reached when canonical write succeeded.
    sb.table("pc_staged_records").update({
        "review_status":"applied",
        "validation_status":"validated",
    }).eq("staged_record_id",row["staged_record_id"]).execute()

    # Audit log is best-effort because some deployments may require a user id
    # under stricter auth. Failure here must not undo a successful canonical write.
    try:
        object_id=None
        for k in keys:
            if payload.get(k):
                object_id=str(payload[k])
                break
        sb.table("pc_audit_log").insert({
            "action":f"STAGED_{write_mode.upper()}",
            "object_type":table,
            "object_id":object_id or row.get("natural_key"),
            "after_data":payload,
        }).execute()
    except Exception:
        pass

    return result,write_mode

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
    title(
        "AI research & enrichment",
        "Launch controlled research from the interface. AI proposals are staged for analyst review and never write directly to canonical tables."
    )

    if not sb:
        st.error("Supabase service connection required.")
    else:
        jobs=safe_rows(
            sb,
            "pc_ingestion_jobs",
            "ingestion_job_id,job_type,title,query_text,status,stats,error_text,created_at,started_at,completed_at",
            200,
            order="created_at"
        )
        st.markdown("### Recent research jobs")
        dataframe(jobs[:50])

        st.markdown("### Launch research")
        campaign=st.selectbox("Campaign",list(AI_CAMPAIGNS))
        seed_prompt=AI_CAMPAIGNS[campaign]

        prompt=st.text_area(
            "Research query",
            value=seed_prompt,
            placeholder="Describe exactly what you want the AI researcher to find, verify and stage.",
            height=180
        )
        c1,c2,c3=st.columns(3)
        with c1:
            context=st.selectbox("Product context",["TRADE","INTELLIGENCE"],index=0)
        with c2:
            use_web=st.checkbox("Use current web research",True)
        with c3:
            st.metric("Pending staged",count_rows(sb,"pc_staged_records",{"review_status":"pending"}))

        st.caption(
            "The AI researcher must provide source URLs and confidence. "
            "All output goes to pc_staged_records for review before canonical apply."
        )

        if st.button("Run AI research job",type="primary",disabled=not bool(prompt.strip())):
            if not ai_configured():
                st.error("Configure OPENAI_API_KEY and OPENAI_MODEL.")
            else:
                job=sb.table("pc_ingestion_jobs").insert({
                    "job_type":"AI_RESEARCH",
                    "title":campaign if campaign!="Custom research" else prompt[:100],
                    "query_text":prompt,
                    "source_scope":{"product":context,"web_search":use_web,"campaign":campaign},
                    "status":"running",
                }).execute().data[0]

                job_id=job["ingestion_job_id"]

                try:
                    with st.status("Running AI research...",expanded=True) as status:
                        st.write("Sending research brief to OpenAI...")
                        result=ai_research(
                            prompt,
                            context,
                            use_web,
                            output_contract=AI_OUTPUT_CONTRACT
                        )

                        st.write("Research returned. Validating structured proposals...")
                        staged,rejected=stage_ai_result(sb,job_id,result)

                        # If the model returned raw/unstructured output, preserve it
                        # as a research bundle rather than losing the result.
                        if staged==0 and result:
                            sb.table("pc_staged_records").insert({
                                "ingestion_job_id":job_id,
                                "target_table":"research_bundle",
                                "natural_key":str(job_id),
                                "action":"REVIEW",
                                "payload":result,
                                "confidence":0.5,
                                "validation_status":"needs_structuring",
                                "review_status":"pending",
                            }).execute()
                            staged=1

                        sb.table("pc_ingestion_jobs").update({
                            "status":"completed",
                            "stats":{
                                "staged_records":staged,
                                "discarded_invalid_records":rejected,
                                "campaign":campaign,
                                "product":context,
                            }
                        }).eq("ingestion_job_id",job_id).execute()

                        status.update(
                            label=f"Research complete — {staged} staged record(s)",
                            state="complete",
                            expanded=False
                        )

                    st.success(f"Research complete. {staged} proposal(s) sent to Review Queue.")
                    st.rerun()

                except Exception as exc:
                    sb.table("pc_ingestion_jobs").update({
                        "status":"failed",
                        "error_text":str(exc)
                    }).eq("ingestion_job_id",job_id).execute()
                    st.error(str(exc))

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
    title(
        "Review & apply queue",
        "Review AI/batch proposals, approve them, then explicitly apply approved records to the canonical database."
    )

    if not sb:
        st.error("Supabase is required for review and apply.")
    else:
        tabs=st.tabs(["Pending review","Approved — apply","History"])

        # ---------------------------------------------------------------
        # Pending review
        # ---------------------------------------------------------------
        with tabs[0]:
            rows=safe_rows(
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
                review_df=pd.DataFrame(rows)
                summary_cols=[
                    c for c in [
                        "target_table","natural_key","action","confidence",
                        "validation_status","source_id","created_at"
                    ] if c in review_df.columns
                ]
                st.caption(f"{len(rows):,} pending record(s)")
                st.dataframe(
                    review_df[summary_cols] if summary_cols else review_df,
                    use_container_width=True,
                    hide_index=True,
                    height=min(420,55+34*len(rows))
                )

                def _label(r):
                    conf=r.get("confidence")
                    try: conf=f"{float(conf):.2f}"
                    except Exception: conf="n/a"
                    return f"{r.get('target_table')} | {r.get('natural_key')} | confidence {conf}"

                labels=[_label(r) for r in rows]
                chosen=st.selectbox("Open staged record",labels,key="pending_record")
                row=rows[labels.index(chosen)]
                payload=row.get("payload") or {}

                st.markdown("### Proposed record")
                h1,h2,h3,h4=st.columns(4)
                h1.metric("Target",row.get("target_table") or "—")
                h2.metric("Action",row.get("action") or "—")
                h3.metric("Confidence",row.get("confidence") if row.get("confidence") is not None else "—")
                h4.metric("Validation",row.get("validation_status") or "pending")

                left,right=st.columns([1.2,0.8])

                with left:
                    st.markdown("#### Payload")
                    if isinstance(payload,dict):
                        payload_rows=[]
                        for k,v in payload.items():
                            payload_rows.append({
                                "Field":k,
                                "Proposed value":json.dumps(v,ensure_ascii=False,indent=2) if isinstance(v,(dict,list)) else v
                            })
                        st.dataframe(pd.DataFrame(payload_rows),use_container_width=True,hide_index=True)
                    else:
                        st.code(str(payload))

                    st.markdown("#### Research sources")
                    source_rows=[]
                    if isinstance(payload,dict):
                        meta=payload.get("metadata") or {}
                        for s in (meta.get("research_sources") or []) if isinstance(meta,dict) else []:
                            if isinstance(s,dict) and s.get("url"): source_rows.append(s)
                        for s in payload.get("sources") or []:
                            if isinstance(s,dict) and s.get("url"): source_rows.append(s)

                    if source_rows:
                        for i,s in enumerate(source_rows,1):
                            label=s.get("title") or s.get("publisher") or f"Source {i}"
                            st.markdown(f"{i}. [{label}]({s['url']})")
                            if s.get("publisher") and s.get("publisher")!=label:
                                st.caption(s["publisher"])
                    else:
                        st.info("No embedded source URLs in this proposal.")

                with right:
                    st.markdown("#### Reviewer decision")
                    note=st.text_area(
                        "Reviewer note",
                        key=f"pending_note_{row['staged_record_id']}",
                        placeholder="Optional reason, correction or instruction."
                    )
                    c1,c2,c3=st.columns(3)

                    if c1.button("Approve",type="primary",key=f"approve_{row['staged_record_id']}"):
                        update={"review_status":"approved","validation_status":"reviewed"}
                        if note and isinstance(payload,dict):
                            meta=payload.get("metadata") or {}
                            if not isinstance(meta,dict): meta={}
                            meta["review_note"]=note
                            payload["metadata"]=meta
                            update["payload"]=payload
                        sb.table("pc_staged_records").update(update).eq(
                            "staged_record_id",row["staged_record_id"]
                        ).execute()
                        st.success("Approved. Record moved to the Apply tab.")
                        st.rerun()

                    if c2.button("Needs changes",key=f"changes_{row['staged_record_id']}"):
                        update={"review_status":"needs_changes"}
                        if note and isinstance(payload,dict):
                            meta=payload.get("metadata") or {}
                            if not isinstance(meta,dict): meta={}
                            meta["review_note"]=note
                            payload["metadata"]=meta
                            update["payload"]=payload
                        sb.table("pc_staged_records").update(update).eq(
                            "staged_record_id",row["staged_record_id"]
                        ).execute()
                        st.rerun()

                    if c3.button("Reject",key=f"reject_{row['staged_record_id']}"):
                        update={"review_status":"rejected"}
                        if note and isinstance(payload,dict):
                            meta=payload.get("metadata") or {}
                            if not isinstance(meta,dict): meta={}
                            meta["review_note"]=note
                            payload["metadata"]=meta
                            update["payload"]=payload
                        sb.table("pc_staged_records").update(update).eq(
                            "staged_record_id",row["staged_record_id"]
                        ).execute()
                        st.rerun()

                    st.markdown("#### Safety")
                    st.caption(
                        "Approve does not write to production. Approved records must be "
                        "explicitly applied from the next tab."
                    )

        # ---------------------------------------------------------------
        # Approved apply queue
        # ---------------------------------------------------------------
        with tabs[1]:
            approved=safe_rows(
                sb,
                "pc_staged_records",
                "staged_record_id,ingestion_job_id,target_table,natural_key,action,confidence,validation_status,review_status,payload,current_record,source_id,created_at",
                500,
                {"review_status":"approved"},
                "created_at"
            )

            if not approved:
                st.info("No approved records waiting to be applied.")
            else:
                st.warning(
                    f"{len(approved)} approved record(s) are waiting for canonical apply. "
                    "Apply one at a time until the workflow is fully proven."
                )

                labels=[
                    f"{r.get('target_table')} | {r.get('natural_key')} | {r.get('confidence')}"
                    for r in approved
                ]
                chosen=st.selectbox("Approved record",labels,key="approved_record")
                row=approved[labels.index(chosen)]
                payload=row.get("payload") or {}

                st.markdown("### Canonical apply")
                a,b,c=st.columns(3)
                a.metric("Target table",row.get("target_table") or "—")
                b.metric("Natural key",row.get("natural_key") or "—")
                c.metric("Confidence",row.get("confidence") if row.get("confidence") is not None else "—")

                st.caption(
                    "You may edit the JSON before apply. The edited payload is saved back "
                    "to staging so the audit trail matches what was written."
                )

                initial_json=json.dumps(payload,ensure_ascii=False,indent=2)
                edited=st.text_area(
                    "Canonical JSON payload",
                    value=initial_json,
                    height=440,
                    key=f"apply_json_{row['staged_record_id']}"
                )

                try:
                    edited_payload=json.loads(edited)
                    if not isinstance(edited_payload,dict):
                        st.error("Canonical payload must be a JSON object.")
                        edited_payload=None
                    else:
                        st.success("JSON is valid.")
                except Exception as exc:
                    st.error(f"Invalid JSON: {exc}")
                    edited_payload=None

                conflict=APPLY_CONFLICT_KEYS.get(row.get("target_table"))
                if conflict:
                    st.caption(f"Configured conflict key: `{conflict}`")
                else:
                    st.caption("No configured conflict key: apply will use INSERT.")

                confirm=st.checkbox(
                    "I reviewed this payload and authorize a canonical database write.",
                    key=f"confirm_apply_{row['staged_record_id']}"
                )

                if st.button(
                    "Apply approved record",
                    type="primary",
                    disabled=not (confirm and edited_payload),
                    key=f"apply_{row['staged_record_id']}"
                ):
                    try:
                        with st.spinner("Writing canonical record..."):
                            result,mode=apply_staged_record(sb,row,edited_payload)
                        st.success(
                            f"Canonical {mode} succeeded. Staged record marked as applied."
                        )
                        st.rerun()
                    except Exception as exc:
                        st.error("Canonical write failed. The record remains approved and can be corrected/retried.")
                        st.exception(exc)

        # ---------------------------------------------------------------
        # History
        # ---------------------------------------------------------------
        with tabs[2]:
            history=[]
            for status in ["applied","rejected","needs_changes"]:
                history.extend(
                    safe_rows(
                        sb,
                        "pc_staged_records",
                        "staged_record_id,target_table,natural_key,action,confidence,validation_status,review_status,created_at",
                        250,
                        {"review_status":status},
                        "created_at"
                    )
                )
            if history:
                history=sorted(history,key=lambda x:str(x.get("created_at") or ""),reverse=True)
                dataframe(history[:500])
            else:
                st.caption("No completed review history yet.")

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
