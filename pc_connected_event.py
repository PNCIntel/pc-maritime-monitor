"""Connected Intelligence event dossier using existing P&C canonical records.

No invented geographic point or inferred causal relationship. The event relationship
table is queried in both directions; all source claims retain their review states.
"""
from __future__ import annotations

import streamlit as st


def _get(sb, table, column, value, limit=150):
    try:
        return sb.table(table).select("*").eq(column, value).limit(limit).execute().data or []
    except Exception:
        return []


def _one(sb, table, column, value):
    rows = _get(sb, table, column, value, 1)
    return rows[0] if rows else {}


def _date(value):
    return str(value or "")[:10] or "Date not established"


def _label(value):
    return str(value or "not established").replace("_", " ").strip()


def _meta(record):
    value = (record or {}).get("metadata") or {}
    return value if isinstance(value, dict) else {}



def _update_date_label(update: dict, event: dict) -> str:
    """Preserve the distinction between when something happened and when it was reported."""
    for field, suffix in (
        ("occurred_at", "occurred"),
        ("reported_at", "reported"),
        ("published_at", "published"),
    ):
        value = update.get(field)
        if value:
            return f"{_date(value)} ({suffix})"
    metadata = _meta(update)
    for field in ("observation_date", "report_date", "publication_date"):
        if metadata.get(field):
            return f"{_date(metadata[field])} ({field.replace('_', ' ')})"
    if event.get("start_date"):
        return f"Event date: {_date(event['start_date'])} · update date unrecorded"
    return "Update date not recorded"

def render_connected_event(sb, record: dict, event_id: str, navigate, go_back=None, go_home=None):
    """Render one event's evidence-linked neighbours before any raw record displays."""
    nav_back, nav_home, _ = st.columns([1, 1, 4])
    with nav_back:
        if st.session_state.get("pc_terminal_history") and go_back:
            st.button("← Back", key="pc_connected_back", on_click=go_back, use_container_width=True)
        elif go_home:
            st.button("← Operating Picture", key="pc_connected_back_home", on_click=go_home,
                      args=("intelligence",), use_container_width=True)
    with nav_home:
        if go_home:
            st.button("Home", key="pc_connected_home", on_click=go_home,
                      args=("intelligence",), use_container_width=True)
    event_id = str(event_id)
    meta = _meta(record)
    # Event links are authoritative for attached vessels, including reported-name aliases.
    linked_vessels = [x for x in _get(sb, "pc_event_links", "event_id", event_id, 150)
                      if str(x.get("linked_type") or "").lower() in ("mobile_asset", "vessel")]
    vessel_id = str(meta.get("canonical_mobile_asset_id") or "")
    if not vessel_id and linked_vessels:
        identifiers = {str(x.get("linked_id")) for x in linked_vessels if x.get("linked_id")}
        if len(identifiers) == 1:
            vessel_id = next(iter(identifiers))
    vessel = _one(sb, "pc_mobile_assets", "mobile_asset_id", vessel_id) if vessel_id else {}
    if not vessel and meta.get("canonical_vessel_imo"):
        vessel = _one(sb, "pc_mobile_assets", "imo", str(meta["canonical_vessel_imo"]))
    vessel_id = str(vessel.get("mobile_asset_id") or "")
    vessel_meta = _meta(vessel)
    # PGSA research queue is a reported maritime non-compliance roster, not a
    # legal designation. Only an exact IMO match can surface it here.
    vessel_imo = str(vessel.get("imo") or "").strip()
    pgsa_queue = []
    if vessel_imo:
        pgsa_queue = [q for q in _get(sb, "pc_sanctions_import_queue",
                                      "subject_identifier", vessel_imo, 100)
                      if str(q.get("authority_code") or "").upper() == "PGSA"]
    # Published sanctions use the canonical designation/link model independently.
    designation_links = []
    if vessel_id:
        designation_links = [q for q in _get(sb, "pc_sanctions_links", "linked_id",
                                              vessel_id, 100)
                             if str(q.get("linked_type") or "").lower() in ("mobile_asset", "vessel")]
    published = []
    for link in designation_links:
        designation = _one(sb, "pc_sanctions_designations", "sanctions_designation_id",
                           link.get("sanctions_designation_id"))
        if designation:
            published.append((link, designation))

    outgoing = _get(sb, "pc_event_relationships", "from_event_id", event_id)
    incoming = _get(sb, "pc_event_relationships", "to_event_id", event_id)
    seen = set()
    related = []
    for link in outgoing + incoming:
        rid = link.get("relationship_id")
        if rid in seen:
            continue
        seen.add(rid)
        other_id = link.get("to_event_id") if link.get("from_event_id") == event_id else link.get("from_event_id")
        other = _one(sb, "pc_events", "event_id", other_id)
        if other:
            related.append((link, other))
    related.sort(key=lambda item: str(item[1].get("start_date") or ""), reverse=True)

    company_roles = []
    if vessel_id:
        roles = _get(sb, "pc_relationships", "target_id", vessel_id, 200)
        for role in roles:
            if str(role.get("source_type") or "").lower() not in ("entity", "company") or str(role.get("target_type") or "").lower() not in ("mobile_asset", "vessel"):
                continue
            company = _one(sb, "pc_entities", "entity_id", role.get("source_id"))
            company_roles.append((role, company))
    company_roles.sort(key=lambda item: str(item[0].get("valid_from") or ""), reverse=True)

    # Multimodal infrastructure: source-backed event asset links and rail-specific
    # service/disruption records exist independently of vessel metadata.
    asset_links = _get(sb, "pc_event_asset_links", "event_id", event_id, 150)
    # Canonical event graph is shared across modes. Specialist link tables are
    # complementary, not the sole source for aviation/port/rail infrastructure.
    canonical_event_links = _get(sb, "pc_event_links", "event_id", event_id, 500)
    existing_asset_ids = {str(x.get("asset_id")) for x in asset_links}
    graph_event_neighbours = []
    for gl in canonical_event_links:
        kind = str(gl.get("linked_type") or "").lower()
        gid = str(gl.get("linked_id") or "")
        if kind in ("asset", "port", "airport", "terminal", "facility", "rail_node") and gid:
            if gid not in existing_asset_ids:
                asset_links.append({"asset_id":gid,"relation_type":gl.get("relationship"),
                                    "role":gl.get("relationship"),"_graph_only":True})
                existing_asset_ids.add(gid)
        elif kind == "event" and gid and gid != event_id:
            graph_event_neighbours.append(gl)

    related_ids = {str(other.get("event_id")) for _,other in related}
    for gl in graph_event_neighbours:
        other_id = str(gl.get("linked_id") or "")
        if other_id in related_ids: continue
        other = _one(sb, "pc_events", "event_id", other_id)
        if other:
            related.append(({"relationship_type":gl.get("relationship"),"claim_status":"linked",
                             "rationale":_meta(gl).get("rationale") or "Source-recorded event association"},other))
            related_ids.add(other_id)
    # Explicit editorial situation links, resolved to real event IDs at read time.
    # These links describe context only; they do not attribute an attack or assert causation.
    for candidate in meta.get("curated_related_events") or []:
        if not isinstance(candidate,dict): continue
        other_id=str(candidate.get("event_id") or "")
        if not other_id or other_id==event_id or other_id in related_ids: continue
        other=_one(sb,"pc_events","event_id",other_id)
        if not other: continue
        related.append(({"relationship_type":candidate.get("relationship") or "wider escalation context",
                         "claim_status":"editorial context, not causal attribution",
                         "rationale":candidate.get("rationale") or "",
                         "metadata":{"causation_established":False}},other))
        related_ids.add(other_id)
    related.sort(key=lambda item: str(item[1].get("start_date") or ""), reverse=True)
    rail_disruptions = _get(sb, "pc_rail_network_disruptions", "event_id", event_id, 100)
    rail_runs = _get(sb, "pc_rail_service_runs", "linked_event_id", event_id, 100)
    assets = {}
    networks = {}
    for link in asset_links:
        aid = str(link.get("asset_id") or "")
        if aid:
            assets[aid] = _one(sb, "pc_assets", "asset_id", aid)
    for disruption in rail_disruptions:
        nid = str(disruption.get("rail_network_id") or "")
        aid = str(disruption.get("node_asset_id") or "")
        if nid and nid not in networks:
            networks[nid] = _one(sb, "pc_rail_networks", "rail_network_id", nid)
        if aid and aid not in assets:
            assets[aid] = _one(sb, "pc_assets", "asset_id", aid)
    for run in rail_runs:
        nid = str(run.get("rail_network_id") or "")
        if nid and nid not in networks:
            networks[nid] = _one(sb, "pc_rail_networks", "rail_network_id", nid)
        for field in ("origin_asset_id", "destination_asset_id"):
            aid = str(run.get(field) or "")
            if aid and aid not in assets:
                assets[aid] = _one(sb, "pc_assets", "asset_id", aid)
    entity_links = _get(sb, "pc_event_entity_links", "event_id", event_id, 200)
    # Show actual group/banner connections around directly linked organisations.
    # The partner endpoint may be a corporate parent that is not itself an incident actor.
    entity_ids = {str(link.get("entity_id")) for link in entity_links if link.get("entity_id")}
    corporate_edges = []
    edge_seen = set()
    for eid in sorted(entity_ids):
        for side in ("source_id", "target_id"):
            for edge in _get(sb, "pc_relationships", side, eid, 150):
                if str(edge.get("source_type") or "").lower() != "entity" or str(edge.get("target_type") or "").lower() != "entity":
                    continue
                edge_id = str(edge.get("relationship_id") or "")
                if edge_id in edge_seen:
                    continue
                edge_seen.add(edge_id)
                parent = _one(sb, "pc_entities", "entity_id", edge.get("source_id"))
                child = _one(sb, "pc_entities", "entity_id", edge.get("target_id"))
                if parent and child:
                    corporate_edges.append((edge, parent, child))
    # Keep historical observations, but display only the preferred equivalent edge.
    preferred_ids={str(e.get("relationship_id")) for e,_,_ in corporate_edges
                   if _meta(e).get("intel_display_preferred") is True}
    corporate_edges=[item for item in corporate_edges
                     if _meta(item[0]).get("intel_display_preferred") is not False
                     and str(_meta(item[0]).get("display_equivalent_to") or "") not in preferred_ids]
    corporate_edges.sort(key=lambda item: (str(item[1].get("name")), str(item[2].get("name"))))
    evidence = _get(sb, "pc_event_evidence", "event_id", event_id, 300)
    evidence.sort(key=lambda e: str(e.get("published_at") or ""))
    updates = _get(sb, "pc_event_updates", "event_id", event_id, 200)
    updates.sort(key=lambda u: str(u.get("occurred_at") or u.get("reported_at") or ""))

    if vessel_imo and (pgsa_queue or published):
        st.markdown("### Vessel compliance & sanctions exposure")
        if pgsa_queue:
            st.markdown("**PGSA — reported Hormuz non-compliance listing**")
            st.caption("Exact IMO match to P&C's recovered PGSA research roster. This is not by itself an OFAC, UN, EU or UK designation.")
            for q in pgsa_queue:
                st.write(str(q.get("reported_name") or vessel.get("name") or vessel_imo)
                         + " · IMO " + vessel_imo)
                st.caption("Research status: " + _label(q.get("research_status")))
                source=str(q.get("source_url") or "")
                if source.startswith(("https://","http://")):
                    st.link_button("PGSA roster source ↗",source)
        for link,designation in published:
            st.markdown("**Published designation record**")
            st.write(str(designation.get("primary_name") or vessel.get("name") or vessel_imo)
                     + " · " + _label(designation.get("source_list")))
            st.caption("Designation status: " + _label(designation.get("status"))
                       + " · link review: " + _label(link.get("review_status"))
                       + " · direct designation: " + str(link.get("is_direct_designation")))
            url=str(designation.get("source_url") or "")
            if url.startswith(("https://","http://")):
                st.link_button("Designation source ↗",url)
        st.caption("A vessel's involvement in an incident does not establish listing, designation or liability.")

    # Intelligence-first executive dossier; built from existing canonical records.
    # Never convert nearby infrastructure or incident severity into confirmed impact/risk.
    assessments = _get(sb, "pc_v07_event_assessments", "event_id", event_id, 100)
    assessments.sort(key=lambda a: (str(a.get("version") or ""), str(a.get("assessment_id") or "")), reverse=True)
    approved = [a for a in assessments if str(a.get("assessment_status") or "").lower() in
                ("published", "approved", "reviewed")]
    assessment = approved[0] if approved else {}
    if not assessment and assessments:
        st.caption("An event analysis exists in draft; it is not presented as an approved P&C judgment.")
    # Existing approved operational judgment takes precedence over the optional new publication table.
    judgments = _get(sb, "pc_event_assessment_judgments", "event_id", event_id, 20)
    judgments = [j for j in judgments if str(j.get("judgment_status") or "").lower()=="published"]
    judgments.sort(key=lambda j: str(j.get("assessed_at") or ""), reverse=True)
    judgment = judgments[0] if judgments else {}
    outlooks = _get(sb, "pc_event_intelligence_outlooks", "event_id", event_id, 30)
    outlooks = [o for o in outlooks if str(o.get("publication_status") or "") == "published"]
    outlooks.sort(key=lambda o: str(o.get("assessed_at") or ""), reverse=True)
    outlook = outlooks[0] if outlooks else {}
    if judgment and (not outlook or str(judgment.get("assessed_at") or "") >= str(outlook.get("assessed_at") or "")):
        outlook = {**outlook, **{"current_risk":judgment.get("risk_level") or judgment.get("current_risk"),
          "confidence":judgment.get("confidence"),"pc_assessment":judgment.get("risk_rationale") or judgment.get("current_risk"),
          "risk_outlook":judgment.get("risk_outlook"),"monitoring_indicators":judgment.get("monitoring_indicators"),
          "assessed_at":judgment.get("assessed_at"),"valid_until":judgment.get("valid_until")}}
    # Export the same approved narrative and evidence as a dated, branded client PDF.
    try:
        from pc_event_pdf import create_incident_brief
        export_assets=[]
        for link in asset_links:
            asset=assets.get(str(link.get("asset_id") or "")) or {}
            if asset:
                export_assets.append({"name":asset.get("name"),"mode":asset.get("asset_type"),
                    "relationship":link.get("relation_type") or link.get("role"),
                    "impact_status":link.get("impact_status") or "Not established"})
        if not export_assets:
            export_assets=[v for v in meta.get("infrastructure_context",[]) if isinstance(v,dict)]
        from pc_geographic_context import named_place_point, locality_point
        pdf_place=None
        geo=meta.get("geographic_reference") or {}
        if isinstance(geo,dict) and geo.get("source_url"):
            try:
                lat,lon=float(geo["latitude"]),float(geo["longitude"])
                if -85<=lat<=85 and -180<=lon<=180:
                    pdf_place={"name":geo.get("label") or "Sourced geographic reference",
                               "lat":lat,"lon":lon,"source":geo["source_url"],"zoom":8}
            except (ValueError,KeyError,TypeError): pass
        if not pdf_place:
            for name in (meta.get("geographic_scope"),record.get("location_name"),
                         record.get("location_name"),record.get("location_label"),meta.get("location_name"),record.get("country")):
                if isinstance(name,str) and name.strip():
                    pdf_place=named_place_point(name)
                    if pdf_place: break
        if not pdf_place:
            pdf_place=locality_point(str(record.get("title") or ""))
        from pc_publication_context import build_context
        publication_context=build_context(
            record,vessel=vessel,company_roles=company_roles,designations=published,
            pgsa_queue=pgsa_queue,related=related,assets=export_assets,
            updates=updates,corporate_edges=corporate_edges)
        st.caption("Publication context: "+str(len(publication_context["company_history"]))+
                   " vessel-company roles · "+str(len(publication_context["published_sanctions"]))+
                   " linked designations · "+str(len(publication_context["related_developments"]))+
                   " connected developments. Missing coverage is not a negative finding.")
        with st.expander("Publication context and gaps",expanded=False):
            st.json(publication_context,expanded=False)
        # AI is opt-in and creates an editable draft, never an automatically published judgment.
        draft_key="pc_editorial_draft_"+event_id
        approved_key="pc_editorial_approved_"+event_id
        with st.expander("Improve brief writing with AI · review before export",expanded=False):
            st.caption("Rewrites supported analysis in plain language. Sources, statuses and event links stay canonical.")
            if st.button("Generate editorial draft",key="pc_draft_btn_"+event_id):
                try:
                    import os
                    from pc_event_editorial import draft_event_brief
                    key=os.environ.get("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY","")
                    st.session_state[draft_key]=draft_event_brief(key,record,assessment,outlook,evidence,related,export_assets,meta,publication_context=publication_context)
                    st.session_state[approved_key]=False
                except Exception as draft_exc:
                    st.error("Editorial draft unavailable: "+str(draft_exc))
            if st.session_state.get(draft_key):
                import json
                revised=st.text_area("Edit the draft JSON before approval",
                    value=json.dumps(st.session_state[draft_key],ensure_ascii=False,indent=2),
                    height=370,key="pc_editorial_text_"+event_id)
                if st.button("Approve edited narrative for PDF",key="pc_approve_"+event_id):
                    try:
                        edited=json.loads(revised)
                        if not isinstance(edited,dict): raise ValueError("Expected a JSON object")
                        st.session_state[draft_key]=edited
                        st.session_state[approved_key]=True
                        st.success("Approved for this session's PDF export; canonical records unchanged.")
                    except (ValueError,TypeError) as parse_exc:
                        st.error("Please correct the draft JSON: "+str(parse_exc))
            if st.session_state.get(approved_key):
                st.caption("Export below will use the approved editorial narrative.")
        approved_editorial=st.session_state.get(draft_key) if st.session_state.get(approved_key) else None
        pdf_bytes=create_incident_brief(record,assessment,outlook,evidence,related,export_assets,meta,pdf_place,editorial=approved_editorial)
        st.download_button("↓ Export Intelligence Brief · PDF",data=pdf_bytes,
            file_name="PC_Incident_Brief_"+str(event_id).replace("/","_")+".pdf",
            mime="application/pdf",key="export_incident_pdf_"+event_id,
            use_container_width=False)
    except Exception as exc:
        st.error("PDF export failed: "+type(exc).__name__+" — "+str(exc))

    # Editorial questions precede visual evidence. Graphs must be earned by actual data.
    st.markdown("## Intelligence dossier")
    st.caption(_date(record.get("start_date"))+" · "+_label(record.get("verification_status"))+
               " · Source-qualified analysis; context is not confirmed impact.")
    left,right=st.columns([1.35,1],gap="large")
    with left:
        a,b,c=st.columns(3)
        a.metric("Current Risk",str(outlook.get("current_risk") or "Not rated"))
        b.metric("Confidence",str(outlook.get("confidence") or "Unassigned"))
        c.metric("Assessed",_date(outlook.get("assessed_at") or assessment.get("updated_at")))
        if outlook.get("valid_until"):
            import datetime as dt
            try:
                expires=dt.datetime.fromisoformat(str(outlook["valid_until"]).replace("Z","+00:00"))
                if expires.tzinfo is None: expires=expires.replace(tzinfo=dt.timezone.utc)
                if expires <= dt.datetime.now(dt.timezone.utc):
                    st.warning("Historical assessment: last assessed "+_date(outlook.get("assessed_at"))+
                               ". Current conditions require revalidation.")
            except (TypeError,ValueError): pass
        st.markdown("### What happened?")
        st.write(assessment.get("what_happened") or record.get("description") or
                 "An adequately sourced incident narrative has not yet been recorded.")
        st.markdown("### What does it mean?")
        st.write(outlook.get("pc_assessment") or assessment.get("pc_assessment") or
                 assessment.get("what_it_means") or meta.get("pc_assessment") or
                 "An approved analytical judgment has not yet been recorded.")
        st.markdown("### What could happen next?")
        st.write(outlook.get("risk_outlook") or meta.get("risk_outlook") or
                 "An evidence-backed outlook has not yet been published.")
        st.markdown("### What are we monitoring, and why?")
        indicators=outlook.get("monitoring_indicators") or assessment.get("monitoring_indicators") or meta.get("monitoring_indicators") or []
        if isinstance(indicators,dict): indicators=[str(k)+": "+str(v) for k,v in indicators.items()]
        if isinstance(indicators,str): indicators=[indicators]
        if isinstance(indicators,list) and indicators:
            for item in indicators: st.markdown("- "+str(item))
        else: st.caption("No published monitoring indicators.")
        if assessment.get("operational_impact") or assessment.get("commercial_impact"):
            with st.expander("Operational and commercial implications"):
                if assessment.get("operational_impact"): st.write(assessment["operational_impact"])
                if assessment.get("commercial_impact"): st.write(assessment["commercial_impact"])
    with right:
        st.markdown("### Geographic context")
        import pandas as pd
        points=[]
        # Facility pins represent known infrastructure, never inferred incident coordinates.
        facility_rows=[]
        for link in asset_links:
            asset=assets.get(str(link.get("asset_id") or "")) or {}
            if not asset: continue
            facility_rows.append({"Asset":asset.get("name") or link.get("asset_id"),
                "Mode":asset.get("asset_type") or "Other",
                "Relationship":_label(link.get("relation_type") or link.get("role")),
                "Impact":link.get("impact_status") or "Not established"})
            try:
                lat,lon=float(asset.get("latitude")),float(asset.get("longitude"))
                if -90<=lat<=90 and -180<=lon<=180 and (lat,lon)!=(0,0):
                    points.append({"lat":lat,"lon":lon,"name":asset.get("name") or str(link.get("asset_id"))})
            except (ValueError,TypeError): pass
        # Prefer exact recorded facility geometry; otherwise map the named locality.
        # A place-name pin is a geographic reference, never a claimed incident point.
        mapped=False
        if points:
            st.map(pd.DataFrame(points).drop_duplicates(),latitude="lat",longitude="lon",use_container_width=True)
            st.caption("Recorded linked facility locations · contextual exposure, not event coordinates or damage.")
            mapped=True
        if not mapped:
            geographic=meta.get("geographic_reference") or {}
            if isinstance(geographic,dict) and geographic.get("source_url"):
                try:
                    lat,lon=float(geographic["latitude"]),float(geographic["longitude"])
                    if -90<=lat<=90 and -180<=lon<=180:
                        st.map(pd.DataFrame([{"lat":lat,"lon":lon}]),latitude="lat",longitude="lon",use_container_width=True)
                        st.caption("Sourced regional reference: "+str(geographic.get("label") or "named area")+" · not the incident point.")
                        mapped=True
                except (KeyError,ValueError,TypeError): pass
        if not mapped:
            from pc_geographic_context import named_place_point
            names=[meta.get("geographic_scope"),record.get("location_name"),record.get("location_label"),
                   record.get("country"),meta.get("location_name"),meta.get("location_label")]
            # Headline is a last resort only when no specific locality was recorded.
            names=[str(n).strip() for n in names if isinstance(n,str) and n.strip()]
            if not names:
                from pc_geographic_context import locality_point
                known=locality_point(record.get("title"))
                if known: names=[known["name"]]
            place=next((p for n in names if (p:=named_place_point(n))),None)
            if place:
                st.map(pd.DataFrame([{"lat":place["lat"],"lon":place["lon"]}]),latitude="lat",longitude="lon",use_container_width=True)
                st.caption("Approximate named-place map: "+place["name"]+" · "+place["precision"]+". Not a verified incident position.")
                st.link_button("Map reference ↗",place["source"],key="geo_ref_"+event_id)
            else:
                st.info("No resolvable named location for a regional reference map; incident position is not inferred.")
        st.markdown("### Connected infrastructure")
        if facility_rows:
            st.dataframe(pd.DataFrame(facility_rows).drop_duplicates(),hide_index=True,use_container_width=True)
        elif isinstance(meta.get("infrastructure_context"),list) and meta["infrastructure_context"]:
            st.caption("Documented contextual network, not verified direct impact.")
            for item in meta["infrastructure_context"]:
                if isinstance(item,dict):
                    st.markdown("**"+str(item.get("name") or "Infrastructure")+"** · "+
                                str(item.get("mode") or "Context"))
                    st.caption(str(item.get("relationship") or item.get("role") or "")+
                               " · "+str(item.get("status") or "Direct impact not established"))
        else: st.caption("No infrastructure relationship recorded.")
    st.divider()
    evidence_tab,network_tab,history_tab=st.tabs(["Evidence & sources","Connected developments","Figures & chronology"])
    with evidence_tab:
        claims=evidence if evidence else [v for v in (meta.get("source_claims") or []) if isinstance(v,dict)]
        st.caption(str(len(claims))+" attributed source records; editorial metadata references are not independent claim-level verification.")
        if not claims: st.info("No source claims have been attached to this record.")
        for i,ev in enumerate(claims):
            publisher=ev.get("publisher") or ev.get("source_name") or ev.get("document_title") or "Source"
            st.markdown("**"+str(publisher)+"**")
            st.write(ev.get("claim") or "Claim details not recorded.")
            st.caption("Source status: "+_label(ev.get("verification_status") or ev.get("verification"))+
                       " · Publication: "+_date(ev.get("published_at")))
            url=ev.get("original_url") or ev.get("source_url") or ev.get("url")
            if isinstance(url,str) and url.startswith(("https://","http://")):
                st.link_button("Read original source ↗",url,key="dossier_source_"+event_id+"_"+str(i))
            st.divider()
    with network_tab:
        if related:
            st.caption("Documented editorial or graph relationships. No shared perpetrator or causation inferred.")
            for i,(link,other) in enumerate(related):
                with st.container(border=True):
                    st.caption(_date(other.get("start_date"))+" · "+_label(other.get("verification_status"))+
                               " · "+_label(link.get("relationship_type")))
                    st.markdown("**"+str(other.get("title") or other.get("event_id"))+"**")
                    if link.get("rationale"): st.write(link["rationale"])
                    st.button("Open dossier →",key="related_dossier_"+event_id+"_"+str(i),
                              on_click=navigate,args=("event",str(other["event_id"]),str(other.get("title") or "")))
        else: st.caption("No explicitly related developments recorded.")
    with history_tab:
        # Only generate a figure when records support it; avoid decorative or fabricated charts.
        dated=[{"Date":_date(u.get("occurred_at") or u.get("reported_at")),
                "Development":u.get("summary") or u.get("update_type") or "Update"} for u in updates]
        if dated:
            st.dataframe(pd.DataFrame(dated),hide_index=True,use_container_width=True)
        elif related:
            st.dataframe(pd.DataFrame([{"Date":_date(o.get("start_date")),
                "Development":o.get("title"),"Relationship":_label(l.get("relationship_type"))}
                for l,o in related]),hide_index=True,use_container_width=True)
        else: st.caption("No additional dated observations available for a timeline.")
        types=[str((assets.get(str(l.get("asset_id") or "")) or {}).get("asset_type") or "")
               for l in asset_links]
        types=[t for t in types if t]
        if len(types)>=2 and len(set(types))>=2:
            st.markdown("**Linked infrastructure by mode**")
            st.bar_chart(pd.Series(types).value_counts())
            st.caption("Recorded link counts only; not damage, traffic or financial exposure.")
    st.divider()
    if st.toggle("Show underlying record, chronology and specialist links", value=False, key="pc_full_dossier_"+event_id):

            # Shared production graph navigation across Intelligence and Trade.
        # Coordinates are not inferred from related airport or facility identities.
        from pc_event_navigation import render_event_connections
        st.markdown("### Recorded event facts")
        st.write({
            "Event date": _date(record.get("start_date")),
            "Classification": _label(record.get("event_type") or record.get("event_family")),
            "Severity": _label(record.get("severity") or "Not classified"),
            "Verification": _label(record.get("verification_status")),
        })
        st.markdown("### Connected organisations and infrastructure")
        render_event_connections(sb, event_id, navigate,
                                 key_prefix="intel_connected_"+event_id, compact=False)

        st.markdown("### Intelligence finding")
        headline = str(meta.get("executive_summary") or record.get("description") or "").strip()
        if headline:
            st.write(headline)
        if related and vessel:
            strongest = related[0][1]
            st.info(
                f"**Connected finding:** {vessel.get('name') or vessel_id} "
                f"(IMO {vessel.get('imo') or 'unresolved'}) also appears in "
                f"**{strongest.get('title') or strongest.get('event_id')}** "
                f"({_date(strongest.get('start_date'))}). "
                "Shared vessel identity does not establish that one action caused another."
            )
        elif related:
            st.caption(f"{len(related)} linked developments are available below; their relationship basis is shown individually.")
        st.caption(
            f"Event verification: {_label(record.get('verification_status'))} · "
            f"Record status: {_label(record.get('record_status'))} · "
            "Source and claim review are distinct from identity resolution."
        )

        left, right = st.columns([1.2, 1], gap="large")
        with left:
            if related:
                st.markdown("#### Related developments")
                for i, (link, other) in enumerate(related):
                    with st.container(border=True):
                        st.caption(f"{_date(other.get('start_date'))} · {_label(link.get('relationship_type'))} · {_label(link.get('claim_status'))}")
                        st.markdown(f"**{other.get('title') or other.get('event_id')}**")
                        rationale = str(link.get("rationale") or "").strip()
                        if rationale:
                            st.write(rationale)
                        lm = _meta(link)
                        if lm.get("causation_established") is False:
                            st.caption("Shared identity/association only; causation NOT established.")
                        st.button("Open connected event →", key=f"connected_event_{event_id}_{i}", on_click=navigate,
                                  args=("event", str(other["event_id"]), str(other.get("title") or "")))

            st.markdown("#### Development timeline")
            if updates:
                for i, update in enumerate(updates):
                    with st.container(border=True):
                        st.caption(f"{_update_date_label(update, record)} · {_label(update.get('update_type'))} · Review: {_label(update.get('review_status'))}")
                        st.write(update.get("summary") or "No summary recorded")
            else:
                # A dated source observation is still a useful timeline entry.
                timeline=[]
                for ev in evidence:
                    when=ev.get("observed_at") or ev.get("published_at")
                    if when:
                        timeline.append((str(when),str(ev.get("document_title") or ev.get("notice_reference") or "Source observation"),
                                         str(ev.get("claim") or ""),str(ev.get("verification_status") or "pending")))
                timeline.append((str(record.get("start_date") or ""),str(record.get("title") or "Incident"),
                                 str(record.get("description") or ""),str(record.get("verification_status") or "unrecorded")))
                for link, other in related:
                    timeline.append((str(other.get("start_date") or ""),str(other.get("title") or "Related development"),
                                     str(link.get("rationale") or ""),str(link.get("claim_status") or "proposed")))
                seen_timeline=set()
                for when,title,detail,status in sorted(timeline,key=lambda x:x[0]):
                    key=(when,title,detail)
                    if key in seen_timeline:continue
                    seen_timeline.add(key)
                    with st.container(border=True):
                        st.caption(_date(when)+" · "+_label(status))
                        st.markdown("**"+title+"**")
                        if detail:st.write(detail)
                if not seen_timeline:st.caption("No dated source observations recorded.")

            if record.get("operational_impact"):
                st.markdown("#### Operational implications")
                st.write(record["operational_impact"])
            if record.get("commercial_impact"):
                st.markdown("#### Commercial implications")
                st.write(record["commercial_impact"])

        with right:
            if vessel:
                asset_kind = str(vessel.get("asset_type") or vessel.get("subtype") or "").lower()
                if "aircraft" in asset_kind or "aviation" in asset_kind:
                    identity_heading = "Aircraft identity"
                elif any(token in asset_kind for token in ("truck", "road", "vehicle", "train", "locomotive", "wagon", "rail")):
                    identity_heading = "Vehicle identity"
                elif vessel.get("imo") or any(token in asset_kind for token in ("ship", "vessel", "tanker", "marine")):
                    identity_heading = "Vessel identity"
                else:
                    identity_heading = "Asset identity"
                st.markdown("#### " + identity_heading)
                with st.container(border=True):
                    identity_detail = (" · IMO " + str(vessel["imo"])) if vessel.get("imo") else ""
                    st.markdown(f"**{vessel.get('name') or vessel_id}**" + identity_detail)
                    names = vessel_meta.get("former_names") or []
                    if names:
                        st.caption("Former names: " + " → ".join(map(str, names)))
                    st.caption("Record status: " + _label(vessel.get("record_status")))
                    if vessel.get("imo"):
                        st.caption("Flag: " + str(vessel.get("flag") or "not independently resolved"))
                    st.button("Open asset →", key=f"connected_vessel_{event_id}", on_click=navigate,
                              args=("mobile_asset", vessel_id, str(vessel.get("name") or "")))
                    if company_roles:
                        st.markdown("**Dated company roles**")
                        for i, (role, company) in enumerate(company_roles):
                            rm = _meta(role)
                            st.markdown(f"**{company.get('name') or role.get('source_id')}** · {_label(role.get('relationship_type'))}")
                            st.caption(f"As observed {_date(rm.get('observation_date') or role.get('valid_from'))} · "
                                       f"{_label(role.get('confidence'))} confidence")
                            if rm.get("not_a_current_role_assertion") or rm.get("temporal_semantics") == "as_of_snapshot":
                                st.caption("Historical snapshot—not evidence of current ownership.")
                            if rm.get("source_url"):
                                st.markdown(f"[Role source]({rm['source_url']})")
                            if company.get("entity_id"):
                                st.button("Open organisation →", key=f"connected_company_{event_id}_{i}",
                                          on_click=navigate, args=("entity", str(company["entity_id"]), str(company.get("name") or "")))

            if asset_links or rail_disruptions or rail_runs:
                st.markdown("#### Affected infrastructure & services")
            for i, link in enumerate(asset_links):
                aid = str(link.get("asset_id") or "")
                asset = assets.get(aid) or {}
                st.write(f"**{asset.get('name') or aid}** — {_label(link.get('relation_type') or link.get('role') or 'linked asset')}")
                if aid and asset:
                    st.button("Open facility →", key=f"connected_asset_{event_id}_{i}",
                              on_click=navigate, args=("asset", aid, str(asset.get("name") or aid)))
            for i, disruption in enumerate(rail_disruptions):
                nid = str(disruption.get("rail_network_id") or "")
                network = networks.get(nid) or {}
                aid = str(disruption.get("node_asset_id") or "")
                node = assets.get(aid) or {}
                st.markdown(f"**Rail disruption:** {_label(disruption.get('disruption_type'))}")
                if network:
                    st.write("Network: " + str(network.get("network_name") or nid))
                if aid:
                    st.write("Affected node: " + str(node.get("name") or aid))
                    if node:
                        st.button("Open affected rail node →", key=f"connected_rail_node_{event_id}_{i}",
                                  on_click=navigate, args=("asset", aid, str(node.get("name") or aid)))
                if disruption.get("service_effect"):
                    st.write(disruption["service_effect"])
                st.caption("Disruption verification: " + _label(disruption.get("verification_status")))
            for i, run in enumerate(rail_runs):
                service_id = str(run.get("transport_service_id") or "")
                service = _one(sb, "pc_transport_services", "service_id", service_id) if service_id else {}
                service_meta = _meta(run)
                display_service = (service.get("service_name") or service.get("name") or service_meta.get("service_name") or service_meta.get("train_name") or "")
                st.markdown("**Affected rail service:** " + str(display_service or "Recorded passenger or freight service"))
                if not display_service and service_id:
                    st.caption("Service record: " + service_id)
                st.caption("Run status: " + _label(run.get("service_status")) + " · Verification: " + _label(run.get("verification_status")))
                origin = assets.get(str(run.get("origin_asset_id") or "")) or {}
                destination = assets.get(str(run.get("destination_asset_id") or "")) or {}
                if origin or destination:
                    st.write("Recorded service endpoints: " + str(origin.get("name") or "unresolved") +
                             " → " + str(destination.get("name") or "unresolved"))
                    st.caption("Service endpoints are not the derailment location.")
            if networks and not rail_disruptions:
                for nid, network in networks.items():
                    st.write("Associated railway network: " + str(network.get("network_name") or nid))

            if corporate_edges:
                st.markdown("#### Connected business network")
                st.caption("Recorded group and commercial-banner relationships; not a list of individually affected sites.")
                for i, (edge, parent, child) in enumerate(corporate_edges):
                    with st.container(border=True):
                        st.markdown(f"**{parent.get('name')} → {child.get('name')}**")
                        pct=edge.get("ownership_percent")
                        relation=(str(pct)+"% ownership") if pct is not None else _label(edge.get("relationship_type"))
                        st.caption(relation + " · " + _label(edge.get("record_status")))
                        source = _meta(edge).get("source_url") or edge.get("source_url")
                        if isinstance(source, str) and source.startswith(("http://", "https://")):
                            st.link_button("Relationship source ↗", source)
                        x, y = st.columns(2)
                        with x:
                            st.button("Open group →", key=f"business_group_{event_id}_{i}",
                                      on_click=navigate, args=("entity", str(parent["entity_id"]), str(parent.get("name") or "")))
                        with y:
                            st.button("Open business →", key=f"business_banner_{event_id}_{i}",
                                      on_click=navigate, args=("entity", str(child["entity_id"]), str(child.get("name") or "")))

            if entity_links:
                st.markdown("#### Organisations involved")
                for i, link in enumerate(entity_links):
                    entity = _one(sb, "pc_entities", "entity_id", link.get("entity_id"))
                    st.write(f"**{entity.get('name') or link.get('entity_id')}** — {_label(link.get('role'))}")
                    st.caption(f"Attribution: {_label(link.get('attribution_status'))}; {_meta(link).get('role_detail') or 'specific role pending review'}")
                    if entity.get("entity_id"):
                        st.button("Open organisation →", key=f"connected_incident_org_{event_id}_{i}",
                                  on_click=navigate, args=("entity", str(entity["entity_id"]), str(entity.get("name") or "")))

            st.markdown("#### Location & confidence")
            if meta.get("location_basis", {}).get("exact_coordinates_confirmed") is False:
                st.caption(str(record.get("location") or "Area only") + " — no verified incident coordinates. No map pin has been inferred.")
            else:
                st.caption(str(record.get("location") or "Exact location not established"))

        # Display source-attributed cyber enrichment on the existing incident dossier.
        cyber = meta.get("n0n_enrichment_20261015") or {}
        if isinstance(cyber, dict) and cyber:
            st.markdown("### Cyber extortion intelligence")
            st.caption("Attacker leak-site allegations; inclusion does not establish a breach or operational outage.")
            a, b, c = st.columns(3)
            a.metric("Organisations named", cyber.get("alleged_organisations_count") or "—")
            b.metric("Countries", cyber.get("countries_count") or "—")
            c.metric("Threatened release (UTC)", str(cyber.get("publication_threat_at_utc") or "Not established").replace("T", " ")[:16])
            demands = cyber.get("specific_reported_demands") or []
            if isinstance(demands, list) and demands:
                st.markdown("#### Reported ransom demands")
                import pandas as pd
                st.dataframe(pd.DataFrame([{
                    "Organisation": d.get("name"), "Demand (USD)": d.get("amount_usd"),
                    "Negotiation entry (%)": d.get("negotiation_entry_percent"),
                    "Claimed files": d.get("claimed_file_count"),
                    "Claimed MB": d.get("claimed_data_mb"), "Claimed GB": d.get("claimed_data_gb"),
                } for d in demands]), hide_index=True, use_container_width=True)
            names = cyber.get("listed_organisations") or []
            if isinstance(names, list) and names:
                with st.expander(f"Organisations named in claim ({len(names)})", expanded=True):
                    st.write(", ".join(str(n) for n in names))
            extra = cyber.get("additional_reported_datasets") or []
            if isinstance(extra, list) and extra:
                with st.expander("Additional claimed datasets"):
                    st.dataframe(pd.DataFrame(extra), hide_index=True, use_container_width=True)
            categories = cyber.get("claimed_data_categories") or []
            if categories:
                st.caption("Claimed data categories: " + ", ".join(map(str, categories)))
            st.caption(str(cyber.get("cyberlogitec_connection") or "Supplier involvement not confirmed"))
            for label, key in (("SOCRadar", "source_socradar"), ("Splash247", "source_splash247")):
                url = cyber.get(key)
                if isinstance(url, str) and url.startswith(("https://", "http://")):
                    st.link_button(label + " source ↗", url)

        # Some sourced company relationships are stored in pc_event_links rather than
        # pc_event_entity_links. Show actual canonical links, never infer compromise.
        graph_links = [x for x in _get(sb, "pc_event_links", "event_id", event_id, 500)
                       if str(x.get("linked_type") or "").lower() in ("entity", "company", "organisation", "organization")]
        if graph_links:
            st.markdown("#### Connected organisations — specific reported roles")
            for i, link in enumerate(graph_links):
                name = str(link.get("linked_name") or link.get("linked_id") or "Unknown organisation")
                st.markdown("**" + name + "** — " + _label(link.get("relationship")))
                lm = _meta(link)
                if lm.get("compromise_status"):
                    st.caption("Compromise status: " + _label(lm["compromise_status"]))
                linked_id = str(link.get("linked_id") or "")
                if linked_id and _one(sb, "pc_entities", "entity_id", linked_id):
                    st.button("Open organisation →", key=f"cyber_graph_org_{event_id}_{i}",
                              on_click=navigate, args=("entity", linked_id, name))

        st.markdown("#### Evidence by source purpose")
        groups = {}
        for ev in evidence:
            m = _meta(ev)
            kind = m.get("source_role") or ("Contemporary reporting" if m.get("publisher") else "Research / source document")
            groups.setdefault(kind, []).append(ev)
        if not groups:
            st.caption("No evidence records found.")
        for purpose, records in groups.items():
            with st.expander(f"{_label(purpose)} ({len(records)})", expanded=purpose in ("official_judicial_statement_reproduced", "official_sanctions_policy")):
                for e in records:
                    m = _meta(e)
                    st.markdown(f"**{e.get('document_title') or m.get('publisher') or 'Source'}** · {_date(e.get('published_at'))}")
                    st.write(e.get("claim") or "Claim not transcribed")
                    st.caption("Claim review: " + _label(e.get("verification_status")))
                    url = str(e.get("original_url") or "")
                    if url.startswith(("https://", "http://")):
                        st.link_button("Open source ↗", url)
                    st.divider()
