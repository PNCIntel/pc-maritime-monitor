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


def render_infrastructure_market_lenses(oid: str, rec: dict, lens: str):
    """Public shared dossier entry used by pc_terminal for Trade/Strategic assets."""
    return _render_cross_market_infrastructure(oid, rec, lens)


def render_market_terminal(lens: str = "trade"):
    """Render the shared terminal with cross-market infrastructure lenses.

    No data is duplicated: the tabs are market-specific read views over the same
    canonical object, relationships, events, sanctions and strategic-industry tables.
    """
    core._render_infrastructure_terminal = _render_cross_market_infrastructure
    core._render_home = _render_market_home
    core.render_terminal(lens)


def _strategic_asset_rows() -> list[dict]:
    """Canonical strategic fixed assets, not a port-specific list."""
    out, seen = [], set()
    strategic_asset_ids = set()
    for r in core._rows("pc_shipyard_details", 5000):
        if r.get("asset_id"):
            strategic_asset_ids.add(_clean(r.get("asset_id")))
    for r in core._rows("pc_defence_programme_participants", 5000):
        if r.get("shipyard_asset_id"):
            strategic_asset_ids.add(_clean(r.get("shipyard_asset_id")))
    for a in core._rows("pc_assets", 10000):
        aid = _clean(a.get("asset_id"))
        blob = core._record_text(a)
        if aid in strategic_asset_ids or core.STRATEGIC_RX.search(blob):
            if aid and aid not in seen:
                seen.add(aid); out.append(a)
    return out


def _render_strategic_picture_home():
    """Market home for Strategic Industries over the shared canonical graph."""
    programmes = core._rows("pc_defence_programmes", 5000)
    participants = core._rows("pc_defence_programme_participants", 8000)
    contracts = core._rows("pc_contracts", 5000)
    orders = core._rows("pc_shipbuilding_orders", 5000)
    tasks = core._rows("pc_shipbuilding_production_tasks", 8000)
    milestones = core._rows("pc_defence_programme_milestones", 8000)
    capacity = core._rows("pc_shipyard_capacity_history", 8000)
    projects = core._rows("pc_project_details", 5000)
    assets = _strategic_asset_rows()
    events = sorted(
        [e for e in core._rows("pc_events", 4000) if core.STRATEGIC_RX.search(core._record_text(e))],
        key=lambda x: _clean(x.get("start_date")), reverse=True
    )
    active = [p for p in programmes if _clean(p.get("programme_status")).casefold()
              not in {"completed", "cancelled", "closed"}]

    core._dashboard_header(
        "P&C STRATEGIC INDUSTRIES · CONNECTED INDUSTRIAL BASE",
        "Strategic Industrial Picture",
        "Organisations, shipyards, facilities, programmes, contracts, platforms, investment and disruption — one connected industrial graph."
    )

    m = st.columns(6)
    m[0].metric("Strategic facilities", len(assets))
    m[1].metric("Active programmes", len(active))
    m[2].metric("Contracts", len(contracts))
    m[3].metric("Shipbuilding orders", len(orders))
    m[4].metric("Projects / investment", len(projects))
    m[5].metric("Programme participants", len(participants))

    left, right = st.columns([1.55, 1.0], gap="medium")
    with left:
        with st.container(border=True):
            core._panel_header(
                "Strategic Industrial Footprint",
                "Shipyards, naval/coast-guard facilities and strategic industrial nodes resolved from canonical records."
            )
            pts = []
            for a in assets:
                try:
                    lat, lon = float(a.get("latitude")), float(a.get("longitude"))
                except Exception:
                    continue
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    pts.append({"lat": lat, "lon": lon, "name": _clean(a.get("name")),
                                "type": _clean(a.get("asset_type") or a.get("subtype"))})
            if pts:
                st.map(pd.DataFrame(pts), latitude="lat", longitude="lon", size=30,
                       zoom=None, use_container_width=True)
                st.caption(f"{len(pts)} mapped strategic facilities · {len(assets)} strategic facilities resolved.")
            else:
                st.info("Strategic facilities are stored, but mapped coordinates have not yet resolved.")
    with right:
        with st.container(border=True):
            core._panel_header("Industrial Base", "Current structured production and delivery records.")
            core._html_rows([
                ("Strategic facilities", str(len(assets))),
                ("Capacity observations", str(len(capacity))),
                ("Production tasks", str(len(tasks))),
                ("Programme milestones", str(len(milestones))),
                ("Shipbuilding orders", str(len(orders))),
            ], 8)
        with st.container(border=True):
            core._panel_header("Investment & Build-out", "Capital projects attached to the same industrial graph.")
            strategic_projects = [
                p for p in projects
                if re.search(r"defen|naval|ship|dock|yard|military|coast guard|industrial",
                             core._record_text(p), re.I)
            ]
            core._html_rows([
                ("Strategic projects", str(len(strategic_projects))),
                ("All connected projects", str(len(projects))),
            ], 5)

    st.markdown("### Industrial Network")
    a, b, c = st.columns([1.0, 1.0, 1.15], gap="medium")
    with a:
        with st.container(border=True):
            core._panel_header("Active Programmes", "Procurement, fleet and industrial programmes.")
            rows = [(_clean(p.get("programme_name")) or "Unnamed programme",
                     _clean(p.get("programme_status")) or _clean(p.get("programme_type")))
                    for p in active[:10]]
            core._html_rows(rows, 10)
    with b:
        with st.container(border=True):
            core._panel_header("Contracts & Orders", "Contract and shipbuilding demand flowing into the industrial base.")
            recent_contracts = sorted(contracts, key=lambda x: _clean(x.get("announced_date")), reverse=True)
            rows = [(_clean(x.get("contract_name")) or "Contract",
                     _clean(x.get("status")) or _clean(x.get("contract_type")))
                    for x in recent_contracts[:6]]
            rows += [(_clean(x.get("order_name") or x.get("name")) or "Shipbuilding order",
                      _clean(x.get("status"))) for x in orders[:4]]
            core._html_rows(rows, 10)
    with c:
        with st.container(border=True):
            core._panel_header("Security & Disruptions",
                               "Industrial-security developments affecting facilities, programmes and supply chains.")
            security = [e for e in events if SECURITY_RX.search(core._record_text(e))]
            core._html_rows(core._recent_event_rows(security, 9), 9)

    st.markdown("### Reference Industrial Ecosystems")
    st.caption("The same canonical records can be entered through a company, shipyard, port, programme or platform.")
    core._featured_search_cards([
        ("EDGE", "EDGE"),
        ("Fincantieri", "Fincantieri"),
        ("Damen", "Damen"),
        ("Port of Rotterdam", "Port of Rotterdam"),
        ("Port of Antwerp-Bruges", "Port of Antwerp-Bruges"),
        ("Zeebrugge", "Zeebrugge"),
    ], "strategic")

    if events:
        with st.container(border=True):
            core._panel_header("Recent Strategic Developments",
                               "Defence-industrial, shipbuilding, programme, facility and industrial-security developments.")
            core._render_event_rows(events, "strategic_home_events", 10)


_ORIGINAL_HOME = core._render_home


def _render_market_home(lens: str):
    # Avoid the old double Strategic Industries header and replace its generic KPI
    # dashboard with the connected industrial-base picture.
    if lens == "strategic":
        _render_strategic_picture_home()
        return
    _ORIGINAL_HOME(lens)
