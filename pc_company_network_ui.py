"""Reusable canonical company network view. No company names/IDs hardcoded.
Only existing recorded links are shown. Evidence is not conflated with ownership.
"""
import pandas as pd
import streamlit as st


def _s(v):
    return '' if v is None else str(v)


def render_company_network(core, entity_id, record):
    st.markdown('### Company Network & Evidence')
    st.caption('Live canonical links for the selected organisation. Relationship labels retain their recorded meaning; an operational link is not proof of legal ownership.')
    try:
        graph = core._entity_graph_neighborhood(str(entity_id), depth=1) or {}
    except Exception as exc:
        st.error(f'Unable to read company network: {exc}')
        return
    edges = graph.get('edges') or []
    nodes = graph.get('nodes') or []
    # Direct links only; the root is selected by its canonical ID. This prevents
    # accidentally assigning another group's global totals to the current entity.
    direct = [e for e in edges if (_s(e.get('source_type')) == 'entity' and _s(e.get('source_id')) == str(entity_id))
              or (_s(e.get('target_type')) == 'entity' and _s(e.get('target_id')) == str(entity_id))]
    assets = sorted({(_s(e.get('target_id')) if _s(e.get('source_id')) == str(entity_id) else _s(e.get('source_id')))
                     for e in direct if ((_s(e.get('source_type')) == 'asset' and _s(e.get('target_type')) == 'entity')
                                          or (_s(e.get('target_type')) == 'asset' and _s(e.get('source_type')) == 'entity'))})
    companies = sorted({(_s(e.get('target_id')) if _s(e.get('source_id')) == str(entity_id) else _s(e.get('source_id')))
                        for e in direct if _s(e.get('source_type')) == 'entity' and _s(e.get('target_type')) == 'entity'
                        and _s(e.get('source_id')) != _s(e.get('target_id'))})
    cols=st.columns(4)
    cols[0].metric('Connected companies',len(companies))
    cols[1].metric('Distinct linked assets',len(assets))
    cols[2].metric('Direct link observations',len(direct))
    cols[3].metric('Network nodes returned',len(nodes))
    if not direct:
        st.info('No direct canonical links returned for this record. This is a coverage gap, not proof the organisation has no network.')
        return
    names={(_s(n.get('type')),_s(n.get('id'))):_s(n.get('name')) for n in nodes}
    section=st.segmented_control('Explore',['Relationships','Assets','Connected companies','Evidence'],default='Relationships',key='pc_generic_network_section_'+core._norm(entity_id))
    if section=='Relationships':
        rows=[{'From':names.get((_s(e.get('source_type')),_s(e.get('source_id'))),_s(e.get('source_name') or e.get('source_id'))),
               'Relationship (recorded)':e.get('relationship'),'To':names.get((_s(e.get('target_type')),_s(e.get('target_id'))),_s(e.get('target_name') or e.get('target_id'))),
               'Family':e.get('family'),'Confidence':e.get('confidence'),'Source table':e.get('source_table'),'Evidence URL':e.get('evidence_url')} for e in direct]
        st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True,column_config={'Evidence URL':st.column_config.LinkColumn('Evidence URL')})
    elif section=='Assets':
        for aid in assets:
            row=core.object_record('asset',aid) or {}
            a,b=st.columns([5,1]); a.markdown('**'+_s(row.get('name') or aid)+'**'); a.caption(' · '.join(x for x in [_s(row.get('asset_type')),_s(row.get('country')),_s(row.get('record_status'))] if x))
            b.button('Open',key='pc_generic_asset_'+core._norm(entity_id)+'_'+core._norm(aid),on_click=core._set_context,args=('asset',aid,row.get('name') or aid),use_container_width=True)
        st.caption('Counts are based on direct recorded links, not unsourced directory leads.')
    elif section=='Connected companies':
        for eid in companies:
            row=core.object_record('entity',eid) or {}
            a,b=st.columns([5,1]); a.markdown('**'+_s(row.get('name') or eid)+'**'); a.caption(_s(row.get('record_status') or ''))
            b.button('Open',key='pc_generic_entity_'+core._norm(entity_id)+'_'+core._norm(eid),on_click=core._set_context,args=('entity',eid,row.get('name') or eid),use_container_width=True)
    else:
        sourced=[e for e in direct if e.get('evidence_url') or e.get('source_record_id')]
        if sourced:
            st.dataframe(pd.DataFrame([{'Relationship':e.get('relationship'),'Source table':e.get('source_table'),'Source record':e.get('source_record_id'),'Evidence URL':e.get('evidence_url'),'Confidence':e.get('confidence')} for e in sourced]),hide_index=True,use_container_width=True,column_config={'Evidence URL':st.column_config.LinkColumn('Evidence URL')})
        else: st.info('No explicit source pointer was returned for these links.')
        st.caption('Research-only facts and unresolved facilities are intentionally not promoted into canonical assets or legal ownership here.')
