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


def render_connected_event(sb, record: dict, event_id: str, navigate):
    """Render one event's evidence-linked neighbours before any raw record displays."""
    event_id = str(event_id)
    meta = _meta(record)
    vessel_id = str(meta.get("canonical_mobile_asset_id") or "")
    vessel = _one(sb, "pc_mobile_assets", "mobile_asset_id", vessel_id) if vessel_id else {}
    if not vessel and meta.get("canonical_vessel_imo"):
        vessel = _one(sb, "pc_mobile_assets", "imo", str(meta["canonical_vessel_imo"]))
    vessel_id = str(vessel.get("mobile_asset_id") or "")
    vessel_meta = _meta(vessel)

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

    entity_links = _get(sb, "pc_event_entity_links", "event_id", event_id, 200)
    evidence = _get(sb, "pc_event_evidence", "event_id", event_id, 300)
    evidence.sort(key=lambda e: str(e.get("published_at") or ""))
    updates = _get(sb, "pc_event_updates", "event_id", event_id, 200)
    updates.sort(key=lambda u: str(u.get("occurred_at") or u.get("reported_at") or ""))

    st.markdown("### Connected intelligence")
    headline = str(record.get("description") or "").strip()
    if related and vessel:
        strongest = related[0][1]
        st.info(
            f"**Cross-event finding:** {vessel.get('name') or vessel_id} "
            f"(IMO {vessel.get('imo') or 'unresolved'}) also appears in "
            f"**{strongest.get('title') or strongest.get('event_id')}** "
            f"({_date(strongest.get('start_date'))}). "
            "This is an established database connection, not evidence that one action caused another."
        )
    elif headline:
        st.write(headline)
    st.caption(
        f"Event verification: {_label(record.get('verification_status'))} · "
        f"Canonical status: {_label(record.get('record_status'))} · "
        "Source and claim review are distinct from identity resolution."
    )

    left, right = st.columns([1.2, 1], gap="large")
    with left:
        st.markdown("#### Connected history")
        if related:
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
        else:
            st.caption("No canonical event-to-event links recorded yet.")

        st.markdown("#### Development timeline")
        if updates:
            for i, update in enumerate(updates):
                with st.container(border=True):
                    st.caption(f"{_date(update.get('occurred_at') or update.get('reported_at'))} · {_label(update.get('update_type'))} · Review: {_label(update.get('review_status'))}")
                    st.write(update.get("summary") or "No summary recorded")
        else:
            st.caption("No dated updates yet.")

        if record.get("operational_impact"):
            st.markdown("#### Operational implications")
            st.write(record["operational_impact"])
        if record.get("commercial_impact"):
            st.markdown("#### Commercial implications")
            st.write(record["commercial_impact"])

    with right:
        st.markdown("#### Canonical vessel")
        if vessel:
            with st.container(border=True):
                st.markdown(f"**{vessel.get('name') or vessel_id}** · IMO {vessel.get('imo') or 'unresolved'}")
                names = vessel_meta.get("former_names") or []
                if names:
                    st.caption("Former names: " + " → ".join(map(str, names)))
                st.caption(f"Identity: {_label(vessel.get('record_status'))} · "
                           f"Flag: {vessel.get('flag') or 'not independently resolved'}")
                st.button("Open vessel →", key=f"connected_vessel_{event_id}", on_click=navigate,
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
        else:
            st.caption("No canonical mobile asset ID linked; no vessel identity inferred.")

        st.markdown("#### Linked organisations")
        if entity_links:
            for i, link in enumerate(entity_links):
                entity = _one(sb, "pc_entities", "entity_id", link.get("entity_id"))
                st.write(f"**{entity.get('name') or link.get('entity_id')}** — {_label(link.get('role'))}")
                st.caption(f"Attribution: {_label(link.get('attribution_status'))}; {_meta(link).get('role_detail') or 'specific role pending review'}")
                if entity.get("entity_id"):
                    st.button("Open organisation →", key=f"connected_incident_org_{event_id}_{i}",
                              on_click=navigate, args=("entity", str(entity["entity_id"]), str(entity.get("name") or "")))
        else:
            st.caption("No direct event-organisation links. Historical vessel-company roles are shown separately.")

        st.markdown("#### Spatial confidence")
        if meta.get("location_basis", {}).get("exact_coordinates_confirmed") is False:
            st.caption(str(record.get("location") or "Area only") + " — no verified incident coordinates. No map pin has been inferred.")
        else:
            st.caption(str(record.get("location") or "Exact location not established"))

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
