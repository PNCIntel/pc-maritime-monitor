"""Reusable presentation-friendly company network; no company-specific identities."""
from __future__ import annotations

import html
import math
import re
from urllib.parse import urlparse

import pandas as pd
import streamlit as st


def _s(value):
    return str(value) if value is not None else ""


def _urls(value):
    if isinstance(value, str):
        return [value] if value.startswith(("https://", "http://")) else []
    if isinstance(value, list):
        result = []
        for item in value:
            result += _urls(item)
        return result
    if isinstance(value, dict):
        result = []
        for key in ("evidence_url", "source_url", "url", "research_sources", "source_urls"):
            result += _urls(value.get(key))
        return result
    return []


def _category(relation, target_type):
    if target_type in ("asset", "mobile_asset"):
        return "Physical assets"
    label = _s(relation).lower().replace("_", " ")
    if re.search(r"owns|owned|equity|share|subsidiary|parent|control|majority|minority|stake", label):
        return "Corporate structure"
    if re.search(r"business unit|part of|operat|manag|charter|service|joint venture|partnership", label):
        return "Operating connections"
    return "Other connections"


def _network_svg(root_id, root_name, entries):
    """Static SVG is safe in st.html; node navigation is handled by Streamlit below."""
    nodes = {root_id: {"name": root_name, "type": "root"}}
    for e in entries:
        nodes[e["ID"]] = {"name": e["Connected record"] or e["ID"], "type": e["Type"]}
    peers = sorted((nid for nid in nodes if nid != root_id),
                   key=lambda nid: (nodes[nid]["type"] != "entity", nodes[nid]["name"].casefold()))
    width = 1100
    height = max(630, 540 + (len(peers) // 16) * 160)
    cx, cy = width / 2, height / 2
    radius = min(245, height * .36)
    positions = {root_id: (cx, cy)}
    # Max 28 visible nodes; the full network remains available in the register.
    shown = peers[:28]
    for i, nid in enumerate(shown):
        theta = -math.pi / 2 + 2 * math.pi * i / max(1, len(shown))
        positions[nid] = (cx + radius * math.cos(theta), cy + radius * math.sin(theta))
    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Network of {html.escape(root_name)}" '
             'style="width:100%;height:auto;display:block" xmlns="http://www.w3.org/2000/svg">',
             f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="none" stroke="#DCE4ED" stroke-dasharray="3 7"/>']
    for e in entries:
        nid = e["ID"]
        if nid not in positions:
            continue
        x, y = positions[nid]
        color = {"Corporate structure": "#AD843D", "Operating connections": "#397F9A",
                 "Physical assets": "#4E987B", "Other connections": "#8793A4"}[e["Category"]]
        dash = ' stroke-dasharray="5 5"' if e["Category"] != "Corporate structure" else ""
        parts.append(f'<line x1="{cx}" y1="{cy}" x2="{x}" y2="{y}" stroke="{color}" '
                     f'stroke-width="1.5" opacity=".52"{dash}/>')
    for nid in shown:
        x, y = positions[nid]
        item = nodes[nid]
        is_company = item["type"] == "entity"
        fill = "#EFF4FA" if is_company else "#EAF5EF"
        stroke = "#6688A4" if is_company else "#4E987B"
        label = html.escape(item["name"][:25] + ("…" if len(item["name"]) > 25 else ""))
        parts += [f'<circle cx="{x}" cy="{y}" r="30" fill="{fill}" stroke="{stroke}" stroke-width="1.6"/>',
                  f'<text x="{x}" y="{y+44}" text-anchor="middle" font-size="11" fill="#27374B" '
                  f'font-family="Arial,sans-serif">{label}</text>']
    parts += [f'<circle cx="{cx}" cy="{cy}" r="52" fill="#FBF1DE" stroke="#AD843D" stroke-width="2.5"/>',
              f'<text x="{cx}" y="{cy+4}" text-anchor="middle" font-size="13" font-weight="bold" '
              f'fill="#453719" font-family="Arial,sans-serif">{html.escape(root_name[:21])}</text>', '</svg>']
    return ('<div style="background:#fff;border:1px solid #d9e2ec;border-radius:12px;'
            'padding:14px;"><div style="font:12px Arial;color:#526171">'
            'Gold: corporate · Blue: operational · Green: assets · dashed: non-ownership'
            '</div>' + "".join(parts) + '</div>')


def render_company_network(entity_id: str, rec: dict) -> None:
    import pc_terminal as core
    eid = str(entity_id)
    company_name = _s(rec.get("name")) or core._object_name("entity", eid)
    st.markdown("### Connected Network")
    st.caption("Explore the organisation's recorded relationships, businesses and infrastructure. "
               "Only directly connected records are included here; operating involvement is not necessarily ownership.")
    graph = core._entity_graph_neighborhood(eid, depth=1)
    graph_nodes = {(n.get("type"), _s(n.get("id"))): n for n in graph.get("nodes") or []}
    rows = []
    seen = set()

    def add(other_id, other_type, other_name, relation, direction, confidence, provenance, metadata=None, source_id=""):
        other_id = _s(other_id)
        if not other_id or other_id == eid:
            return
        other_type = _s(other_type).lower()
        category = _category(relation, other_type)
        link_urls = _urls(provenance) + _urls(metadata)
        if source_id and not link_urls:
            source_rows = core._filtered_rows("pc_sources", "source_id", source_id, 1)
            for source in source_rows:
                link_urls += _urls(source)
        url = next((u for u in link_urls if urlparse(u).scheme in ("http", "https")), "")
        item = {"Connected record": _s(other_name) or other_id, "ID": other_id, "Type": other_type,
                "Relationship": _s(relation).replace("_", " ").strip().title(), "Category": category,
                "Direction": direction, "Status": _s(confidence), "Source": url}
        key = (other_id, other_type, item["Relationship"], direction)
        if key not in seen:
            seen.add(key)
            rows.append(item)

    for edge in graph.get("edges") or []:
        src, dst = _s(edge.get("source_id")), _s(edge.get("target_id"))
        if eid not in (src, dst):
            continue
        forward = src == eid
        typ = edge.get("target_type") if forward else edge.get("source_type")
        oid = dst if forward else src
        name = edge.get("target_name") if forward else edge.get("source_name")
        if not name:
            name = (graph_nodes.get((typ, oid)) or {}).get("name", "")
        metadata = edge.get("metadata") or {}
        add(oid, typ, name, edge.get("relationship"),
            "From selected organisation" if forward else "To selected organisation",
            edge.get("confidence"), edge.get("evidence_url"), metadata,
            _s(metadata.get("evidence_source_id") or metadata.get("source_id")) if isinstance(metadata, dict) else "")

    for col, role in (("operator_entity_id", "Recorded operator"), ("owner_entity_id", "Recorded owner")):
        for asset in core._filtered_rows("pc_assets", col, eid, 1000):
            add(asset.get("asset_id"), "asset", asset.get("name"), role,
                "From selected organisation", asset.get("record_status"), asset,
                asset.get("metadata"), asset.get("source_id"))

    company_ids = {r["ID"] for r in rows if r["Type"] == "entity"}
    asset_ids = {(r["Type"], r["ID"]) for r in rows if r["Type"] in ("asset", "mobile_asset")}
    sourced = {r["Source"] for r in rows if r["Source"]}
    metrics = st.columns(4)
    metrics[0].metric("Connected organisations", len(company_ids))
    metrics[1].metric("Linked assets", len(asset_ids))
    metrics[2].metric("Recorded connections", len(rows))
    metrics[3].metric("Connections with source URL", sum(bool(r["Source"]) for r in rows))
    st.caption("Counts describe direct relationships for the selected record, not the complete consolidated group. "
               "A missing link or source URL means the current view has not resolved it.")

    available = ["Corporate structure", "Operating connections", "Physical assets", "Other connections"]
    selected = st.multiselect("Show network layers", available, default=available[:3],
                              key=f"network_layers_{core._norm(eid)}")
    filtered = [r for r in rows if r["Category"] in selected]
    focus = {}
    for r in filtered:
        focus.setdefault(r["ID"], r)
    graph_col, side_col = st.columns([2.1, 1], gap="large")
    with graph_col:
        st.markdown("#### Relationship map")
        if focus:
            st.html(_network_svg(eid, company_name, list(focus.values())))
            if len(focus) > 28:
                st.caption(f"Showing 28 of {len(focus)} connected records in the diagram. All records remain below.")
        else:
            st.info("No direct links in the selected layers.")
    with side_col:
        st.markdown("#### Explore a connection")
        options = list(sorted(focus.values(), key=lambda r: (r["Category"], r["Connected record"].casefold())))
        labels = [f'{r["Connected record"]} · {r["Category"]} · {r["ID"]}' for r in options]
        choice = st.selectbox("Connected record", [""] + labels, key=f"network_choice_{core._norm(eid)}")
        if choice:
            item = options[labels.index(choice)]
            obj_type = item["Type"]
            if obj_type in ("entity", "asset", "mobile_asset"):
                st.button("Open dossier", key=f"network_go_{core._norm(eid)}",
                          on_click=core._set_context,
                          args=(obj_type, item["ID"], item["Connected record"]), use_container_width=True)
            st.write("**Relationship:** " + item["Relationship"])
            st.write("**Recorded status:** " + (item["Status"] or "Not supplied"))
            if item["Source"]:
                st.link_button("Open source", item["Source"], use_container_width=True)
            else:
                st.caption("No source URL resolved for this connection.")

    st.markdown("#### Connection register")
    st.caption("Detailed traceability is available below the map, including distinct relationship observations.")
    if filtered:
        frame = pd.DataFrame(filtered)
        st.dataframe(frame.drop(columns=["ID"]).rename(columns={"Source":"Source URL"}),
                     hide_index=True, use_container_width=True,
                     column_config={"Source URL": st.column_config.LinkColumn("Source URL")})
        st.download_button("Export filtered connections (CSV)",
                           frame.to_csv(index=False).encode("utf-8"),
                           file_name=f"company_network_{core._norm(eid).replace(' ', '_')}.csv",
                           mime="text/csv", key=f"network_export_{core._norm(eid)}")
    else:
        st.caption("No connections to export for the selected layers.")
