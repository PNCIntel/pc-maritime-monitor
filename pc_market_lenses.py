from __future__ import annotations

import re
from typing import Any

import pandas as pd
import streamlit as st

import pc_terminal as core

# One canonical database, several market lenses.  Keep the existing terminal renderer
# as the commercial/primary dossier and add cross-market views around the same object.
_ORIGINAL_INFRASTRUCTURE_TERMINAL = core._render_infrastructure_terminal

SECURITY_RX = re.compile(
    r"attack|drone|uas|missile|strike|protest|demonstration|labour|labor|strike|"
    r"sabotage|cyber|fire|explosion|collision|grounding|closure|disruption|security|"
    r"military|naval|terror|piracy|boarding|weather|storm|flood|accident|incident",
    re.I,
)


def _clean(v: Any) -> str:
    return core._clean(v)


def _scope(oid: str, rec: dict) -> tuple[set[str], list[dict]]:
    local = core._local_infrastructure(rec)
    ids = {str(oid)}
    ids.update(_clean(x.get("id")) for x in local if x.get("id"))
    return ids, local


def _rows_for_scope(table: str, columns: tuple[str, ...], ids: set[str], limit: int = 3000) -> list[dict]:
    out, seen = [], set()
    vals = tuple(sorted(ids))
    for col in columns:
        try:
            rows = core._rows_matching_ids(table, col, vals)
        except Exception:
            rows = []
        for r in rows[:limit]:
            key = repr(sorted((k, str(v)) for k, v in r.items() if k not in {"metadata", "updated_at"}))
            if key not in seen:
                seen.add(key)
                out.append(r)
    return out


def _source_button(row: dict, key: str):
    urls = core._event_source_urls(row)
    if not urls and row.get("source_id"):
        src = core._filtered_rows("pc_sources", "source_id", _clean(row.get("source_id")), 1)
        if src:
            urls = core._event_source_urls(src[0])
    if urls:
        st.link_button("Source", urls[0], key=key)


def _render_strategic_lens(oid: str, rec: dict):
    ids, local = _scope(oid, rec)
    shipyards = _rows_for_scope("pc_shipyard_details", ("asset_id",), ids)
    capacity = _rows_for_scope("pc_shipyard_capacity_history", ("shipyard_asset_id",), ids)
    participants = _rows_for_scope("pc_defence_programme_participants", ("shipyard_asset_id",), ids)

    programme_ids = {_clean(x.get("defence_programme_id")) for x in participants if x.get("defence_programme_id")}
    programmes = []
    for pid in sorted(programme_ids):
        programmes += core._filtered_rows("pc_defence_programmes", "defence_programme_id", pid, 5)

    # Programme/customer/contract records can also resolve by connected companies and names.
    companies = core._asset_companies(rec)
    entity_ids = {_clean(x.get("id")) for x in companies if x.get("id")}
    for item in local:
        arec = core.object_record("asset", item.get("id")) or {}
        for x in core._asset_companies(arec):
            if x.get("id"):
                entity_ids.add(_clean(x.get("id")))
    for eid in sorted(entity_ids):
        programmes += core._filtered_rows("pc_defence_programmes", "lead_contractor_entity_id", eid, 100)
        programmes += core._filtered_rows("pc_defence_programmes", "customer_entity_id", eid, 100)
        participants += core._filtered_rows("pc_defence_programme_participants", "entity_id", eid, 200)

    # De-duplicate programmes.
    pseen, pdedup = set(), []
    for p in programmes:
        k = _clean(p.get("defence_programme_id")) or repr(p)
        if k not in pseen:
            pseen.add(k); pdedup.append(p)
    programmes = pdedup

    contracts = []
    for p in programmes:
        cid = _clean(p.get("contract_id"))
        if cid:
            contracts += core._filtered_rows("pc_contracts", "contract_id", cid, 5)
    for eid in sorted(entity_ids):
        contracts += core._related_table("pc_contracts", eid, core._object_name("entity", eid), 100)

    projects = core._infrastructure_projects(oid, local)

    st.markdown("### Strategic Industry")
    st.caption("Defence, shipbuilding, naval/coast-guard infrastructure, programmes, contracts, suppliers and industrial capacity connected to this same canonical ecosystem.")
    m = st.columns(5)
    m[0].metric("Shipyard / industrial facilities", len(shipyards))
    m[1].metric("Defence programmes", len(programmes))
    m[2].metric("Programme participants", len(participants))
    m[3].metric("Contracts", len(contracts))
    m[4].metric("Capacity observations", len(capacity))

    left, right = st.columns([1.1, 1.0], gap="large")
    with left:
        with st.container(border=True):
            st.markdown("#### Programmes & Contracts")
            if programmes:
                for i, p in enumerate(programmes[:20]):
                    st.markdown("**" + (_clean(p.get("programme_name")) or "Unnamed programme") + "**")
                    bits = [
                        _clean(p.get("programme_type")).replace("_", " ").title(),
                        _clean(p.get("programme_status")),
                        (str(p.get("firm_quantity")) + " firm") if p.get("firm_quantity") not in (None, "") else "",
                        _clean(p.get("expected_completion_date")),
                    ]
                    st.caption(" · ".join(x for x in bits if x))
                    _source_button(p, f"market_strat_prog_{core._norm(oid)}_{i}")
            else:
                st.caption("No defence/strategic programme is currently resolved to this ecosystem.")
            if contracts:
                with st.expander(f"Contracts ({len(contracts)})", expanded=not bool(programmes)):
                    for i, c in enumerate(contracts[:25]):
                        st.markdown("**" + (_clean(c.get("contract_name")) or "Contract") + "**")
                        st.caption(" · ".join(x for x in [_clean(c.get("contract_type")), _clean(c.get("status")), _clean(c.get("announced_date"))] if x))
                        _source_button(c, f"market_strat_contract_{core._norm(oid)}_{i}")

    with right:
        with st.container(border=True):
            st.markdown("#### Facilities & Industrial Capacity")
            strategic_assets = [x for x in local if core._infrastructure_group(x) in {"Marine Services", "Industrial", "Port Infrastructure"}]
            if strategic_assets:
                core._render_company_asset_cards(strategic_assets, f"market_strat_assets_{core._norm(oid)}", 25)
            if shipyards:
                with st.expander(f"Shipyard details ({len(shipyards)})", expanded=True):
                    st.dataframe(pd.DataFrame(shipyards), hide_index=True, use_container_width=True)
            if capacity:
                with st.expander(f"Capacity history ({len(capacity)})"):
                    view = pd.DataFrame(capacity)
                    cols = [x for x in ("observed_date", "metric_name", "metric_value", "metric_unit", "capacity_basis", "reported_backlog_quantity", "planned_or_actual") if x in view.columns]
                    st.dataframe(view[cols] if cols else view, hide_index=True, use_container_width=True)
            if not strategic_assets and not shipyards and not capacity:
                st.caption("No strategic industrial facility/capacity record is currently linked.")

    if participants:
        with st.container(border=True):
            st.markdown("#### Industrial Supply Chain / Programme Participants")
            rows = []
            for r in participants[:60]:
                eid = _clean(r.get("entity_id"))
                rows.append({
                    "Organisation": core._object_name("entity", eid) if eid else "",
                    "Role": _clean(r.get("participant_role")).replace("_", " ").title(),
                    "Status": _clean(r.get("participation_status")),
                    "Programme": next(( _clean(p.get("programme_name")) for p in programmes if _clean(p.get("defence_programme_id")) == _clean(r.get("defence_programme_id")) ), ""),
                })
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    strategic_projects = [p for p in projects if re.search(r"defen|naval|ship|dock|security|military|coast guard", " ".join(_clean(p.get(k)) for k in ("_project_name", "project_type", "scope_description")), re.I)]
    if strategic_projects:
        with st.container(border=True):
            st.markdown("#### Strategic Projects & Investment")
            for i, p in enumerate(strategic_projects[:20]):
                st.markdown("**" + (_clean(p.get("_project_name")) or "Project") + "**")
                st.caption(" · ".join(x for x in [_clean(p.get("project_stage")), _clean(p.get("expected_completion_date"))] if x))
                if p.get("scope_description"):
                    st.write(p.get("scope_description"))
                _source_button(p, f"market_strat_project_{core._norm(oid)}_{i}")


def _render_sanctions_lens(oid: str, rec: dict):
    ids, local = _scope(oid, rec)
    names = [core._object_name("asset", x) for x in ids]
    companies = core._asset_companies(rec)
    entity_ids = {_clean(x.get("id")) for x in companies if x.get("id")}
    for item in local:
        arec = core.object_record("asset", item.get("id")) or {}
        for x in core._asset_companies(arec):
            if x.get("id"):
                entity_ids.add(_clean(x.get("id")))

    designations, links, cases, matches = [], [], [], []
    for eid in sorted(entity_ids):
        nm = core._object_name("entity", eid)
        designations += core._related_table("pc_sanctions_designations", eid, nm, 200)
        links += core._related_table("pc_sanctions_links", eid, nm, 200)
        cases += core._related_table("pc_screening_cases", eid, nm, 100)
        matches += core._related_table("pc_screening_matches", eid, nm, 200)
    for aid, nm in zip(sorted(ids), names):
        designations += core._related_table("pc_sanctions_designations", aid, nm, 100)
        links += core._related_table("pc_sanctions_links", aid, nm, 100)

    st.markdown("### Sanctions & Compliance")
    st.caption("Designations, ownership/control exposure, screening and restrictions resolved against the same infrastructure/company graph.")
    m = st.columns(4)
    m[0].metric("Designations", len(designations))
    m[1].metric("Exposure links", len(links))
    m[2].metric("Screening cases", len(cases))
    m[3].metric("Matches", len(matches))
    if designations:
        st.markdown("#### Legal designations")
        st.dataframe(pd.DataFrame(designations), hide_index=True, use_container_width=True)
    if links:
        st.markdown("#### Ownership / control / designation network")
        st.dataframe(pd.DataFrame(links), hide_index=True, use_container_width=True)
    if cases or matches:
        a, b = st.columns(2)
        if cases:
            a.dataframe(pd.DataFrame(cases), hide_index=True, use_container_width=True)
        if matches:
            b.dataframe(pd.DataFrame(matches), hide_index=True, use_container_width=True)
    if not (designations or links or cases or matches):
        st.info("No sanctions, restriction or screening record is currently resolved to this ecosystem. This is not a clearance determination.")


def _render_security_lens(oid: str, rec: dict):
    ids, local = _scope(oid, rec)
    events = []
    for aid in sorted(ids):
        events += core._events_for_object("asset", aid)
    # De-duplicate and keep disruptions/security events only.
    seen, filtered = set(), []
    for e in events:
        eid = _clean(e.get("event_id")) or repr(e)
        if eid in seen:
            continue
        seen.add(eid)
        blob = " ".join(_clean(e.get(k)) for k in ("title", "description", "event_type", "event_family", "event_category", "operational_impact"))
        if SECURITY_RX.search(blob):
            filtered.append(e)
    filtered.sort(key=lambda x: _clean(x.get("start_date")), reverse=True)

    operations = []
    for aid in sorted(ids):
        operations += core._related_table("pc_security_operations", aid, core._object_name("asset", aid), 100)

    st.markdown("### Security & Disruptions")
    st.caption("Protests, strikes, drones/UAS, attacks, sabotage, cyber, accidents, fires, closures, weather and security activity affecting this site or its connected infrastructure.")
    m = st.columns(4)
    m[0].metric("Linked disruptions", len(filtered))
    m[1].metric("Security operations", len(operations))
    m[2].metric("Mapped ecosystem nodes", len(local))
    recent = [e for e in filtered if _clean(e.get("start_date"))]
    m[3].metric("Most recent", _clean(recent[0].get("start_date"))[:10] if recent else "—")

    if filtered:
        core._render_event_rows(filtered, "market_security_" + core._norm(oid), 25)
    else:
        st.info("No linked security/disruption event is currently stored for this ecosystem.")
    if operations:
        with st.expander(f"Security operations ({len(operations)})"):
            st.dataframe(pd.DataFrame(operations), hide_index=True, use_container_width=True)


def _render_cross_market_infrastructure(oid: str, rec: dict, lens: str):
    if lens == "trade":
        commercial, strategic, sanctions, security = st.tabs([
            "Commercial", "Strategic Industry", "Sanctions", "Security & Disruptions"
        ])
        with commercial:
            _ORIGINAL_INFRASTRUCTURE_TERMINAL(oid, rec, lens)
        with strategic:
            _render_strategic_lens(oid, rec)
        with sanctions:
            _render_sanctions_lens(oid, rec)
        with security:
            _render_security_lens(oid, rec)
        return

    if lens == "strategic":
        strategic, commercial, security, sanctions = st.tabs([
            "Strategic Industry", "Commercial Context", "Security & Disruptions", "Sanctions"
        ])
        with strategic:
            _render_strategic_lens(oid, rec)
        with commercial:
            _ORIGINAL_INFRASTRUCTURE_TERMINAL(oid, rec, "trade")
        with security:
            _render_security_lens(oid, rec)
        with sanctions:
            _render_sanctions_lens(oid, rec)
        return

    _ORIGINAL_INFRASTRUCTURE_TERMINAL(oid, rec, lens)


def render_market_terminal(lens: str = "trade"):
    """Render the shared terminal with cross-market infrastructure lenses.

    No data is duplicated: the tabs are market-specific read views over the same
    canonical object, relationships, events, sanctions and strategic-industry tables.
    """
    core._render_infrastructure_terminal = _render_cross_market_infrastructure
    core.render_terminal(lens)
