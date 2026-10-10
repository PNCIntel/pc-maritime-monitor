"""Universal, lazy company network view over existing canonical records.

No company-specific IDs or research-count overrides; all queries use the selected
entity ID and existing core helpers. Directory leads are not physical assets.
"""
from __future__ import annotations
import pandas as pd
import streamlit as st


def render_company_network(entity_id: str, rec: dict) -> None:
    import pc_terminal as core
    eid = str(entity_id)
    st.markdown("### Network & Evidence")
    st.caption("Recorded relationships and physical assets for this canonical organisation. "
               "Roles and evidence are shown as stored; a connection is not necessarily legal ownership.")
    # Query only on selection, never during the Overview first paint.
    graph = core._entity_graph_neighborhood(eid, depth=1)
    edges = graph.get("edges") or []
    nodes = graph.get("nodes") or []
    companies = {n["id"]: n for n in nodes if n.get("type") == "entity" and n.get("id") != eid}
    asset_ids = {n["id"] for n in nodes if n.get("type") in ("asset", "mobile_asset")}
    link_rows = []
    for edge in edges:
        src = str(edge.get("source_id") or "")
        dst = str(edge.get("target_id") or "")
        if eid not in (src, dst):
            continue
        other = dst if src == eid else src
        direction = "Outbound" if src == eid else "Inbound"
        link_rows.append({
            "Connected record": edge.get("target_name") if src == eid else edge.get("source_name"),
            "ID": other,
            "Type": edge.get("target_type") if src == eid else edge.get("source_type"),
            "Relationship": edge.get("relationship"),
            "Direction": direction,
            "Confidence": edge.get("confidence"),
            "Source table": edge.get("source_table"),
            "Evidence URL": edge.get("evidence_url"),
        })
    # Direct operator/owner references often exist without corresponding graph edges.
    direct_assets = {}
    for col, role in (("operator_entity_id", "Recorded operator"), ("owner_entity_id", "Recorded owner")):
        for asset in core._filtered_rows("pc_assets", col, eid, 1000):
            aid = str(asset.get("asset_id") or "")
            if aid:
                direct_assets[aid] = asset
                asset_ids.add(aid)
                link_rows.append({"Connected record": asset.get("name"), "ID": aid,
                                  "Type": "asset", "Relationship": role,
                                  "Direction": "Outbound", "Confidence": asset.get("record_status"),
                                  "Source table": "pc_assets", "Evidence URL": ""})
    cols = st.columns(4)
    cols[0].metric("Connected companies", len(companies))
    cols[1].metric("Distinct linked assets", len(asset_ids))
    cols[2].metric("Direct observations", len(link_rows))
    cols[3].metric("Source references", len({str(x.get("Evidence URL")) for x in link_rows if x.get("Evidence URL")}))
    if link_rows:
        # Observations can overlap; never present the row count as distinct assets.
        st.dataframe(pd.DataFrame(link_rows).drop_duplicates(), hide_index=True,
                     use_container_width=True, column_config={
                         "Evidence URL": st.column_config.LinkColumn("Evidence URL")})
    else:
        st.info("No direct canonical connections returned for this identity. "
                "This does not establish that the wider group has no assets.")
    if companies:
        st.markdown("#### Open connected organisations")
        for cid, c in sorted(companies.items(), key=lambda x: str(x[1].get("name") or x[0]).lower()):
            left, right = st.columns([5, 1])
            left.write(c.get("name") or cid)
            if right.button("Open", key=f"network_entity_{core._norm(eid)}_{core._norm(cid)}"):
                core._set_context("entity", cid, c.get("name") or cid)
    if asset_ids:
        st.markdown("#### Open linked assets")
        for typ in ("asset", "mobile_asset"):
            for node in sorted((n for n in nodes if n.get("type") == typ and n.get("id") in asset_ids),
                               key=lambda n: str(n.get("name") or "").lower()):
                aid = str(node["id"])
                left, right = st.columns([5, 1])
                left.write(node.get("name") or aid)
                if right.button("Open", key=f"network_asset_{core._norm(eid)}_{core._norm(typ)}_{core._norm(aid)}"):
                    core._set_context(typ, aid, node.get("name") or aid)
