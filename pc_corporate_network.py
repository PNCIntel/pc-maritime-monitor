from __future__ import annotations

import html
import streamlit as st


def render_network(nodes, edges, root_id: str, key_prefix: str, open_callback=None, include_assets: bool=False):
    if not nodes:
        st.caption("No network nodes available.")
        return

    by_depth = {}
    for n in nodes:
        by_depth.setdefault(int(n.get("depth", 0)), []).append(n)

    # Spiderweb / radial layout: selected company at the centre, each
    # relationship depth on a ring. This reads like a network rather than an
    # org-chart column layout.
    node_w, node_h = 190, 60
    max_depth = max(by_depth) if by_depth else 0
    width = 1180
    height = max(720, 660 + max_depth * 70)
    cx, cy = width / 2, height / 2

    positions = {}
    for depth, items in by_depth.items():
        items = sorted(items, key=lambda x: (x.get("kind") != "company", x.get("name", "")))
        if depth == 0:
            for n in items:
                positions[str(n["id"])] = (cx - node_w / 2, cy - node_h / 2)
            continue

        radius = min(min(width, height) * 0.43, 150 + depth * 125)
        count = max(1, len(items))
        angle_offset = -1.57079632679 + (0.18 if depth % 2 else 0)
        for i, n in enumerate(items):
            angle = angle_offset + (6.28318530718 * i / count)
            nx = cx + radius * __import__("math").cos(angle) - node_w / 2
            ny = cy + radius * __import__("math").sin(angle) - node_h / 2
            positions[str(n["id"])] = (nx, ny)

    edge_parts = []
    for e in edges:
        source = str(e.get("source") or "")
        target = str(e.get("target") or "")
        if source not in positions or target not in positions:
            continue
        sx, sy = positions[source]
        tx, ty = positions[target]
        x1, y1 = sx + node_w / 2, sy + node_h / 2
        x2, y2 = tx + node_w / 2, ty + node_h / 2
        midx, midy = (x1 + x2) / 2, (y1 + y2) / 2
        dash = ' stroke-dasharray="6 5"' if e.get("kind") in {"asset", "affiliation"} else ""
        edge_parts.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="#98a2b3" stroke-width="1.35" opacity="0.78"{dash}/>'
        )
        label = html.escape(str(e.get("label") or ""))
        if label:
            edge_parts.append(
                f'<text x="{midx:.1f}" y="{(midy-4):.1f}" text-anchor="middle" '
                f'font-size="9" fill="#667085" paint-order="stroke" stroke="#ffffff" stroke-width="3">{label[:42]}</text>'
            )

    node_parts = []
    for n in nodes:
        nid = str(n["id"])
        x, y = positions[nid]
        is_root = nid == str(root_id)
        is_asset = n.get("kind") == "asset"
        fill = "#fff7ed" if is_root else ("#f8fafc" if not is_asset else "#f3f4f6")
        stroke = "#b8892f" if is_root else ("#cbd5e1" if not is_asset else "#d1d5db")
        name = html.escape(str(n.get("name") or "Unnamed"))
        subtype = html.escape(str(n.get("subtype") or ""))
        metrics = html.escape(str(n.get("metrics") or ""))
        node_parts.append(
            f'<rect x="{x}" y="{y}" rx="8" ry="8" width="{node_w}" height="{node_h}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{2 if is_root else 1.2}"/>'
        )
        node_parts.append(
            f'<text x="{x+10}" y="{y+21}" font-size="12" font-weight="600" fill="#111827">{name[:30]}</text>'
        )
        if subtype:
            node_parts.append(
                f'<text x="{x+10}" y="{y+39}" font-size="10" fill="#6b7280">{subtype[:34]}</text>'
            )
        if metrics:
            node_parts.append(
                f'<text x="{x+10}" y="{y+56}" font-size="10" fill="#374151">{metrics[:40]}</text>'
            )

    legend = (
        'Spiderweb view · solid lines = ownership/control/business-unit relationships'
        + (' · dashed lines = operating/asset links' if include_assets else '')
    )

    ring_parts = []
    for depth in range(1, max_depth + 1):
        radius = min(min(width, height) * 0.43, 150 + depth * 125)
        ring_parts.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{radius:.1f}" '
            f'fill="none" stroke="#eef1f5" stroke-width="1"/>'
        )

    st.html(
        f'<div style="overflow:auto;border:1px solid #e5e7eb;border-radius:10px;padding:8px;background:white;">'
        f'<div style="font-size:12px;color:#6b7280;margin:.15rem 0 .5rem 0;">{legend}</div>'
        f'<svg width="100%" height="{height}" viewBox="0 0 {width} {height}" preserveAspectRatio="xMidYMid meet" '
        f'xmlns="http://www.w3.org/2000/svg">{"".join(ring_parts)}{"".join(edge_parts)}{"".join(node_parts)}</svg></div>'
    )

    if open_callback:
        company_nodes = [n for n in nodes if n.get("kind") == "company" and str(n["id"]) != str(root_id)]
        if company_nodes:
            labels = {f"{n['name']} · {n.get('subtype') or 'company'}": str(n["id"]) for n in company_nodes}
            selected = st.selectbox("Open company from visual network", [""] + list(labels.keys()), key=f"{key_prefix}_select")
            if selected:
                target = labels[selected]
                target_node = next(n for n in company_nodes if str(n["id"]) == target)
                st.button(
                    "Open selected company",
                    key=f"{key_prefix}_open_{target}",
                    on_click=open_callback,
                    args=("entity", target, target_node.get("name") or target),
                )
