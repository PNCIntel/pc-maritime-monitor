"""Company operating network with source-backed relationships and navigable dossiers."""
from __future__ import annotations
import pandas as pd
import streamlit as st
from pc_company_footprint import collect_network, render_graph

def render_company_network(entity_id,rec):
    import pc_terminal as core
    root=str(entity_id);name=rec.get('name') or core._object_name('entity',root)
    st.markdown('### Company operating network')
    st.caption('Follow connections from the group through its businesses to ports, facilities and vessels. An operating link does not necessarily mean ownership.')
    graph=collect_network(core,root)
    nodes=graph['nodes'];edges=graph['edges'];records=graph['records'];by_id={n['id']:n for n in nodes}
    metrics=st.columns(4)
    metrics[0].metric('Group companies',max(0,len(graph['members'])-1))
    metrics[1].metric('Linked infrastructure',sum(n['type']=='asset' for n in nodes))
    metrics[2].metric('Linked vessels',sum(n['type']=='mobile_asset' for n in nodes))
    metrics[3].metric('Recorded relationships',len(edges))
    if graph['truncated']:st.warning('The group traversal reached its limit. These counts may be incomplete.')
    layers=st.multiselect('Show in the network',['Companies','Infrastructure','Vessels'],default=['Companies','Infrastructure','Vessels'],key='company_network_layers_'+root)
    types={'Companies':'entity','Infrastructure':'asset','Vessels':'mobile_asset'}
    allowed={types[x] for x in layers}
    visible=[n for n in nodes if n['type'] in allowed or n['id']==root]
    limit=st.slider('Maximum nodes in diagram',20,150,80,step=10,key='company_network_limit_'+root)
    # Preserve company hubs so displayed assets stay attached to their real operating entities.
    visible=sorted(visible,key=lambda n:(n['id']!=root,n['type']!='entity',n['type']=='mobile_asset',n.get('depth',0),n['name']))
    shown=visible[:limit];ids={n['id'] for n in shown};shown_edges=[e for e in edges if e['source'] in ids and e['target'] in ids]
    st.markdown('#### Explore the network')
    if shown:
        render_graph(shown,shown_edges,root)
        st.caption(f'{len(shown)} of {len(visible)} matching records shown. The list below contains all matching records.')
    else:st.info('No linked records match the selected layers.')
    options=sorted([n for n in visible if n['id']!=root],key=lambda n:(n['type'],n['name']))
    if options:
        choice=st.selectbox('Open a company, facility or vessel',range(len(options)),
            format_func=lambda i:options[i]['name']+' · '+{'entity':'Company','asset':'Infrastructure','mobile_asset':'Vessel'}[options[i]['type']],key='company_network_record_'+root)
        selected=options[choice]
        if st.button('Open selected dossier',key='company_network_go_'+root):
            core._set_context(selected['type'],selected['id'],selected['name']);st.rerun()
        related=[e for e in edges if selected['id'] in (e['source'],e['target'])]
        with st.expander('Connections and sources for '+selected['name']):
            for i,e in enumerate(related):
                st.write(by_id[e['source']]['name']+' → '+e['label'].replace('_',' ')+' → '+by_id[e['target']]['name'])
                url=e.get('source_url') or (e.get('metadata') or {}).get('source_url')
                if not url and e.get('source_id'):
                    sources=core._filtered_rows('pc_sources','source_id',e['source_id'],1)
                    url=sources[0].get('url') if sources else None
                if isinstance(url,str) and url.startswith(('https://','http://')):st.link_button('Read source',url,key=f'network_source_{root}_{i}')
                if e.get('confidence'):st.caption('Evidence confidence: '+str(e['confidence']).capitalize())
    st.markdown('#### All connections')
    matching={n['id'] for n in visible}
    rows=[{'From':by_id[e['source']]['name'],'Connection':e['label'].replace('_',' '),'To':by_id[e['target']]['name'],
           'Evidence confidence':e.get('confidence') or 'Not recorded','Source':e.get('source_url') or ''}
          for e in edges if e['source'] in matching and e['target'] in matching]
    if rows:
        df=pd.DataFrame(rows).drop_duplicates()
        st.dataframe(df,hide_index=True,use_container_width=True,column_config={'Source':st.column_config.LinkColumn('Source')})
        st.download_button('Download connections',df.to_csv(index=False).encode(),file_name='company_connections.csv',mime='text/csv',key='company_network_csv_'+root)
    else:st.info('No connections in the selected layers.')
