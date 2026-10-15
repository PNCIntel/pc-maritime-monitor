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
    outlooks = _get(sb, "pc_event_intelligence_outlooks", "event_id", event_id, 30)
    outlooks = [o for o in outlooks if str(o.get("publication_status") or "") == "published"]
    outlooks.sort(key=lambda o: str(o.get("assessed_at") or ""), reverse=True)
    outlook = outlooks[0] if outlooks else {}
    st.markdown("## Intelligence assessment")
    st.caption("Global, multimodal P&C dossier · event facts, analysis and forward outlook are distinct.")
    risk_value = outlook.get("current_risk")
    confidence = outlook.get("confidence")
    x, y, z = st.columns(3)
    x.metric("Current Risk", str(risk_value or "Pending assessment"))
    y.metric("Confidence", str(confidence or "Not assigned"))
    z.metric("Source records", len(evidence))
    st.caption("Event verification: "+_label(record.get("verification_status"))+
               " · Last assessed: "+_date(outlook.get("assessed_at") or assessment.get("updated_at"))+
               " · An incident severity is not a regional risk rating.")
    st.markdown("#### P&C assessment")
    st.write(outlook.get("pc_assessment") or assessment.get("pc_assessment") or
             assessment.get("what_it_means") or meta.get("pc_assessment") or meta.get("executive_summary") or
             record.get("description") or "Assessment pending source review.")
    if not outlook and not assessment:
        st.caption("Event narrative / existing editorial context; not a separately approved risk rating.")
    st.markdown("#### Risk Outlook")
    st.write(outlook.get("risk_outlook") or meta.get("risk_outlook") or
             "Outlook pending evidence-backed publication.")
    if not outlook: st.caption("Provisional monitoring interpretation; no separately published outlook or rating.")
    st.markdown("#### Monitoring Indicators")
    indicators = outlook.get("monitoring_indicators") or assessment.get("monitoring_indicators") or meta.get("monitoring_indicators") or []
    if isinstance(indicators, str):
        indicators = [indicators]
    if isinstance(indicators, dict):
        indicators = [str(k)+": "+str(v) for k,v in indicators.items()]
    if indicators:
        for indicator in indicators: st.markdown("- "+str(indicator))
    else:
        st.caption("No reviewed monitoring indicators published.")
    st.markdown("#### Spatial context and connected infrastructure")
    points, asset_table = [], []
    for link in asset_links:
        aid = str(link.get("asset_id") or "")
        asset = assets.get(aid) or {}
        relation = str(link.get("relation_type") or link.get("role") or "linked context")
        if not asset: continue
        asset_table.append({"Infrastructure":asset.get("name") or aid,
                            "Mode / type":asset.get("asset_type") or "Not classified",
                            "Recorded relationship":_label(relation),
                            "Impact status":link.get("impact_status") or "Direct impact not established"})
        try:
            lat, lon = float(asset.get("latitude")), float(asset.get("longitude"))
            if -90 <= lat <= 90 and -180 <= lon <= 180 and (lat,lon)!=(0,0):
                points.append({"lat":lat,"lon":lon,"name":asset.get("name") or aid})
        except (ValueError,TypeError): pass
    if points:
        import pandas as pd
        st.map(pd.DataFrame(points),latitude="lat",longitude="lon",use_container_width=True)
        st.caption("Stored coordinates of explicitly linked infrastructure, NOT incident coordinates or evidence of damage.")
    else:
        st.caption("No source-linked facility coordinates available; exact incident coordinates are not inferred.")
    if asset_table:
        import pandas as pd
        st.dataframe(pd.DataFrame(asset_table).drop_duplicates(),hide_index=True,use_container_width=True)
    else:
        st.caption("No explicitly linked infrastructure yet. Relevant facilities require documented contextual or direct event links.")
    st.markdown("#### Evidence and provenance")
    if evidence:
        for i, ev in enumerate(evidence):
            with st.expander(str(ev.get("document_title") or ev.get("notice_reference") or ev.get("source_name") or "Evidence observation")+" · "+_date(ev.get("published_at"))):
                st.caption("Claim status: "+_label(ev.get("verification_status"))+
                           " · observed: "+_date(ev.get("observed_at")))
                st.write(ev.get("claim") or "Claim not transcribed.")
                source = ev.get("original_url") or ev.get("source_url")
                if isinstance(source,str) and source.startswith(("https://","http://")):
                    st.link_button("Read source ↗",source,key="pc_exec_evidence_"+event_id+"_"+str(i))
    else:
        principal = _one(sb, "pc_sources", "source_id", record.get("source_id")) if record.get("source_id") else {}
        source_url = principal.get("url") or meta.get("source_url")
        if principal or source_url:
            st.caption("Principal event source (not a substitute for claim-level evidence observations).")
            st.write(principal.get("source_name") or principal.get("publisher") or "Source linked in event record")
            if isinstance(source_url,str) and source_url.startswith(("https://","http://")):
                st.link_button("Read principal source ↗",source_url,key="pc_exec_principal_"+event_id)
        st.warning("No separate evidence observations recorded. Source provenance and claim-level review require completion.")
    if related:
        st.markdown("#### Connected developments")
        for link, other in related[:8]:
            st.write(_date(other.get("start_date"))+" · "+str(other.get("title") or other.get("event_id"))+
                     " · "+_label(link.get("relationship_type")))
        st.caption("Only recorded event-to-event associations; no causal inference.")
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
