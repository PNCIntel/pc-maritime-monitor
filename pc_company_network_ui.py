"""Global company operating-network explorer. Drop-in replacement for pc_company_network_ui.py.

Uses canonical collect_network output; no regional views or data mutations.
"""
from __future__ import annotations

import html
import json
from collections import Counter, defaultdict, deque

import pandas as pd
import streamlit as st
from pc_company_footprint import collect_network

LABELS = {"entity": "Company", "asset": "Infrastructure", "mobile_asset": "Vessel / mobile asset"}
COLORS = {"entity": "#C58B28", "asset": "#278C70", "mobile_asset": "#387DBA"}


def _s(value):
    return "" if value is None else str(value)


def _kind(node):
    t = _s(node.get("type")).lower()
    return "mobile_asset" if t == "vessel" else t


def _url(edge):
    meta = edge.get("metadata") or {}
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except (ValueError, TypeError):
            meta = {}
    val = edge.get("source_url") or (meta.get("source_url") if isinstance(meta, dict) else None)
    return val if isinstance(val, str) and val.startswith(("https://", "http://")) else None


def _relation(edge):
    return _s(edge.get("label") or edge.get("relationship") or "related to").replace("_", " ")


def _graph_dot(focus, nodes, edges, max_neighbours):
    """Render the actual direct-edge neighbourhood, grouped and labelled; never synthesize links."""
    node_map = {n["id"]: n for n in nodes}
    connected = [e for e in edges if focus in (e.get("source"), e.get("target"))
                 and e.get("source") in node_map and e.get("target") in node_map]
    weight = Counter(x for e in connected for x in (e["source"], e["target"]) if x != focus)
    ids = [focus] + sorted(weight, key=lambda x: (-weight[x], _kind(node_map[x]), node_map[x].get("name", "")))[:max_neighbours]
    chosen = set(ids)
    shown_edges = [e for e in connected if e["source"] in chosen and e["target"] in chosen]
    def q(v):
        return json.dumps(_s(v), ensure_ascii=False)
    def label(n):
        name = _s(n.get("name") or n.get("id"))
        return name if len(name) <= 48 else name[:45] + "…"
    lines = [
        'digraph P {', 'graph [rankdir=LR, bgcolor="transparent", pad="0.32", nodesep="0.42", ranksep="1.05", splines=polyline, outputorder=edgesfirst];',
        'node [shape=box, style="rounded,filled", fontname="Arial", fontsize=13, margin="0.20,0.13", color="#8191A5", penwidth=1.3];',
        'edge [color="#8B98AA", fontname="Arial", fontsize=9, fontcolor="#566579", arrowsize=0.62, penwidth=1.45];'
    ]
    for t in ("entity", "asset", "mobile_asset"):
        group = [i for i in ids if i != focus and _kind(node_map[i]) == t]
        if not group:
            continue
        lines.append('subgraph cluster_' + t + ' {')
        lines.append('label=' + q(LABELS[t] + ' (' + str(len(group)) + ')') + '; style="rounded"; color="#AAB5C3"; fontname="Arial"; fontsize=12; fontcolor="#536278";')
        for i in group:
            lines.append(q(i) + ' [label=' + q(label(node_map[i])) + ', fillcolor=' + q(COLORS[t]) + ', fontcolor="white", color=' + q(COLORS[t]) + '];')
        lines.append('}')
    root_node = node_map[focus]
    lines.append(q(focus) + ' [label=' + q(label(root_node)) + ', fillcolor="#172B49", color="#172B49", fontcolor="white", fontsize=17, penwidth=2.4];')
    dedup = set()
    for e in shown_edges:
        k = (e["source"], e["target"], _relation(e))
        if k in dedup:
            continue
        dedup.add(k)
        lines.append(q(e["source"]) + ' -> ' + q(e["target"]) + ' [label=' + q(_relation(e)[:32]) + '];')
    lines.append('}')
    return '\n'.join(lines), len(weight), len(chosen) - 1


def render_company_network(entity_id, rec):
    import pc_terminal as core
    root = _s(entity_id)
    graph = collect_network(core, root)
    raw_nodes = graph.get("nodes") or []
    nodes = list({n.get("id"): n for n in raw_nodes if n.get("id")}.values())
    if root not in {n["id"] for n in nodes}:
        nodes.insert(0, {"id": root, "type": "entity", "name": rec.get("name") or root})
    by_id = {n["id"]: n for n in nodes}
    edges = [e for e in (graph.get("edges") or []) if e.get("source") in by_id and e.get("target") in by_id]
    adjacency = defaultdict(set)
    for e in edges:
        adjacency[e["source"]].add(e["target"])
        adjacency[e["target"]].add(e["source"])

    st.markdown('### Company operating network')
    st.caption('Explore documented corporate, operating and fleet relationships. An operating or management link does not imply ownership.')
    m = st.columns(4)
    m[0].metric('Group companies', max(0, len(graph.get('members') or []) - 1))
    m[1].metric('Infrastructure', sum(_kind(n) == 'asset' for n in nodes))
    m[2].metric('Vessels / mobile assets', sum(_kind(n) == 'mobile_asset' for n in nodes))
    m[3].metric('Recorded links', len(edges))
    if graph.get('truncated'):
        st.warning('The underlying network collection reached its limit. Counts and neighbourhoods may be incomplete.')

    search_col, layer_col = st.columns([1.25, 1])
    with search_col:
        search = st.text_input('Find within this network', placeholder='Company, port, terminal or vessel', key='pc_net_search_' + root)
    with layer_col:
        layers = st.multiselect('Include record types', list(LABELS.values()), default=list(LABELS.values()), key='pc_net_layers_' + root)
    types = {k for k, v in LABELS.items() if v in layers}
    candidates = [n for n in nodes if (n['id'] == root or _kind(n) in types)
                  and (not search or search.casefold() in _s(n.get('name')).casefold() or search.casefold() in n['id'].casefold())]
    candidates.sort(key=lambda n: (n['id'] != root, _kind(n) != 'entity', _s(n.get('name')).casefold()))
    if not candidates:
        st.info('No records match your search and filters.')
        return

    left, right = st.columns([1.9, 1], gap='large')
    with left:
        st.markdown('#### Relationship explorer')
        focus_options = [n['id'] for n in candidates]
        focus = st.selectbox('Focus on a company, asset or vessel', focus_options,
            format_func=lambda i: _s(by_id[i].get('name') or i) + ' · ' + LABELS.get(_kind(by_id[i]), 'Record'),
            key='pc_net_focus_' + root)
        count = st.slider('Connections to display', 8, 48, 24, 4, key='pc_net_count_' + root)
        dot, total, shown = _graph_dot(focus, [n for n in nodes if n['id'] == focus or _kind(n) in types], edges, count)
        if total:
            st.graphviz_chart(dot, use_container_width=True)
            st.caption(f'Direct documented links for selected record: {shown} of {total} connected records displayed. Select another record to expand its neighbourhood.')
        else:
            st.info('No direct relationships for this record in the selected layers.')
        st.caption('Gold: companies · Green: infrastructure · Blue: vessels/mobile assets. Arrows preserve stored relationship direction.')
    with right:
        selected = by_id[focus]
        st.markdown('#### Selected record')
        st.markdown('**' + html.escape(_s(selected.get('name') or focus)) + '**')
        st.caption(LABELS.get(_kind(selected), _kind(selected).replace('_', ' ').title()))
        st.metric('Connected records', len(adjacency[focus]))
        if st.button('Open full dossier', type='primary', use_container_width=True, key='pc_net_open_' + root):
            core._set_context(_kind(selected), selected['id'], selected.get('name') or selected['id'])
            st.rerun()
        direct = [e for e in edges if focus in (e['source'], e['target'])]
        if direct:
            st.markdown('**Direct relationships**')
            limit_details = st.select_slider('Show relationships', options=[10, 25, 50, 100, 250], value=25,
                                            key='pc_net_detail_limit_' + root)
            for i, e in enumerate(direct[:limit_details]):
                other = e['target'] if e['source'] == focus else e['source']
                with st.container(border=True):
                    st.write('**' + _s(by_id[other].get('name') or other) + '**')
                    st.caption(('→ ' if e['source'] == focus else '← ') + _relation(e))
                    if e.get('confidence'):
                        st.caption('Confidence: ' + _s(e['confidence']))
                    url = _url(e)
                    if not url and e.get('source_id'):
                        src = core._filtered_rows('pc_sources', 'source_id', e['source_id'], 1)
                        if src:
                            url = src[0].get('url')
                    if isinstance(url, str) and url.startswith(('https://', 'http://')):
                        st.link_button('Evidence', url, use_container_width=True)
            if len(direct) > limit_details:
                st.caption(f'{len(direct) - limit_details} further direct relationships available in the complete table below.')

    st.markdown('#### Connected record directory')
    directory = [{"Name": n.get('name') or n['id'], "Category": LABELS.get(_kind(n), _kind(n)),
                  "Direct connections": len(adjacency[n['id']]), "Canonical ID": n['id']}
                 for n in candidates]
    st.dataframe(pd.DataFrame(directory), hide_index=True, use_container_width=True, height=320)
    st.markdown('#### All recorded relationships')
    valid = {n['id'] for n in candidates}
    rows = [{"From": by_id[e['source']].get('name') or e['source'], "Relationship": _relation(e),
             "To": by_id[e['target']].get('name') or e['target'],
             "Evidence confidence": e.get('confidence') or 'Not recorded', "Source": _url(e) or ''}
            for e in edges if e['source'] in valid and e['target'] in valid]
    if rows:
        df = pd.DataFrame(rows).drop_duplicates()
        st.dataframe(df, hide_index=True, use_container_width=True,
                     column_config={'Source': st.column_config.LinkColumn('Source')}, height=380)
        st.download_button('Export relationships (CSV)', df.to_csv(index=False).encode('utf-8'),
                           file_name='company_network_relationships.csv', mime='text/csv', key='pc_net_export_' + root)
    else:
        st.info('No relationship records match the current filters.')
