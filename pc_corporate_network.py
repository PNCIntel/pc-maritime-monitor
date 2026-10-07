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

    node_w, node_h, col_w, x_gap, y_gap, margin = 205, 68, 255, 42, 28, 28
    max_depth = max(by_depth) if by_depth else 0
    max_rows = max(len(v) for v in by_depth.values()) if by_depth else 1
    width = max(980, margin * 2 + (max_depth + 1) * (col_w + x_gap))
    height = max(420, margin * 2 + max_rows * (node_h + y_gap))

    positions = {}
    for depth, items in by_depth.items():
        items = sorted(items, key=lambda x: (x.get("kind") != "company", x.get("name", "")))
        total = len(items) * (node_h + y_gap) - y_gap
        y0 = max(margin, (height - total) / 2)
        x = margin + depth * (col_w + x_gap)
        for i, n in enumerate(items):
            positions[str(n["id"])] = (x, y0 + i * (node_h + y_gap))

    edge_parts = []
    for e in edges:
        source = str(e.get("source") or "")
        target = str(e.get("target") or "")
        if source not in positions or target not in positions:
            continue
        sx, sy = positions[source]
        tx, ty = positions[target]
        x1, y1 = sx + node_w, sy + node_h / 2
        x2, y2 = tx, ty + node_h / 2
        mid = (x1 + x2) / 2
        dash = ' stroke-dasharray="6 5"' if e.get("kind") == "asset" else ""
        edge_parts.append(
            f'<path d="M{x1:.1f},{y1:.1f} C{mid:.1f},{y1:.1f} {mid:.1f},{y2:.1f} {x2:.1f},{y2:.1f}" '
            f'stroke="#9aa4b2" stroke-width="1.4" fill="none"{dash}/>'
        )
        label = html.escape(str(e.get("label") or ""))
        if label:
            edge_parts.append(
                f'<text x="{mid:.1f}" y="{((y1+y2)/2-4):.1f}" text-anchor="middle" '
                f'font-size="10" fill="#6b7280">{label[:48]}</text>'
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
        'Solid lines = ownership/control/business-unit relationships'
        + (' · Dashed lines = linked assets' if include_assets else '')
    )
    st.html(
        f'<div style="overflow-x:auto;border:1px solid #e5e7eb;border-radius:10px;padding:8px;background:white;">'
        f'<div style="font-size:12px;color:#6b7280;margin:.15rem 0 .5rem 0;">{legend}</div>'
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">'
        f'{"".join(edge_parts)}{"".join(node_parts)}</svg></div>'
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
