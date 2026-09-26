"""Verified published Trade intelligence. No unapproved staging data shown here.
Staff-only by default; reuse P&C pc_auth.require_super_admin authentication.
"""
from __future__ import annotations
from urllib.parse import urlsplit
import json
import streamlit as st
import pandas as pd


def _obj(v):
    if isinstance(v,dict):return v
    if isinstance(v,str):
        try:return json.loads(v)
        except (TypeError,ValueError):pass
    return {}


def _list(v):
    if isinstance(v,list):return v
    if isinstance(v,dict):return [v]
    if isinstance(v,str):
        try:
            x=json.loads(v)
            if isinstance(x,list):return x
            if isinstance(x,dict):return [x]
        except (TypeError,ValueError):pass
        return [a.strip(' -•') for a in v.split('\n') if a.strip(' -•')]
    return []


def _link(u):
    s=str(u or '').strip(); p=urlsplit(s)
    return s if p.scheme in {'http','https'} and p.netloc else ''


def _paragraph(label,value):
    s=str(value or '').strip()
    st.markdown('**'+label+'**')
    if s and s.casefold() not in {'not assessed','none','null','[]','{}'}:st.write(s)
    else:st.caption('Analysis pending — do not infer an impact from an announcement.')


def render_live_trade(sb,compact=False):
    """Call only after require_super_admin; no client-facing RLS bypass."""
    if not compact:
        st.header('Live Trade intelligence')
        st.caption('Only verified, transactionally published canonical events. Drafts remain in review; verified links are persistent.')
    search=st.text_input('Search live developments',key='pc_v12_live_search',
        placeholder='Ogun, Canaveral, Etihad Rail…')
    page=st.number_input('Live page',1,1000,1,key='pc_v12_live_page')
    try:
        q=sb.table('pc_v12_live_developments').select('*').order('published_at',desc=True)
        if search.strip():q=q.ilike('title','%'+search.strip().replace('%','')+'%')
        rows=q.range((page-1)*20,page*20-1).execute().data or []
    except Exception as exc:
        st.error('Live database view unavailable: '+str(exc)+' — run 04_SUPABASE_V12_GRAPH.sql first.')
        return
    if not rows:
        st.info('No canonical developments published in this view yet. Use Power Admin → Finish Trade load to approve and publish the existing batch.');return
    st.dataframe(pd.DataFrame([{'Date':r.get('start_date'),'Development':r.get('title'),
        'Domain':r.get('event_domain'),'Published':r.get('published_at'),
        'Reviewed content':bool(r.get('description'))} for r in rows]),
        hide_index=True,use_container_width=True)
    target=st.session_state.pop('pc_v12_live_target',None)
    default=next((i for i,r in enumerate(rows) if r['event_id']==target),0)
    chosen=st.selectbox('Open live development',rows,index=default,format_func=lambda r:r.get('title') or r['event_id'],key='pc_v12_live_pick')
    st.subheader(chosen.get('title') or 'Untitled development')
    st.caption('Canonical event '+str(chosen['event_id'])+' · Published · Source job '+str(chosen['ingestion_job_id'])[:8])
    for label,key in [('What happened','description'),('Why it matters','what_it_means'),
        ('Operational implications','operational_impact'),('Commercial implications','commercial_implications'),
        ('P&C assessment','pc_assessment')]:_paragraph(label,chosen.get(key))
    st.markdown('**Monitoring indicators**')
    indicators=_list(chosen.get('monitoring_indicators'))
    if indicators:
        for i in indicators:
            val=i.get('indicator') or i.get('text') if isinstance(i,dict) else i
            if val:st.markdown('- '+str(val))
    else:st.caption('Monitoring criteria pending.')
    try:
        links=(sb.table('pc_v12_published_links').select('linked_type,linked_id,linked_name,relationship')
            .eq('event_id',chosen['event_id']).order('linked_name').limit(100).execute().data or [])
    except Exception as exc:
        links=[];st.warning('Verified graph links unavailable: '+str(exc))
    st.markdown('### Verified connected objects')
    if not links:st.caption('No verified canonical relationships published yet; staging mentions are not ownership evidence.')
    for n,e in enumerate(links):
        with st.container(border=True):
            st.markdown('**'+str(e['linked_name'])+'** · '+str(e['relationship']).replace('_',' '))
            st.caption('Verified '+e['linked_type']+' · '+str(e['linked_id']))
            route={'entity':('Companies','company_pick_id'),'asset':('Ports','port_pick_id'),
                'mobile_asset':('Vessels','vessel_pick_id')}.get(e['linked_type'])
            if route and st.button('Open canonical profile',key='v12_jump_'+str(chosen['event_id'])+'_'+str(n)):
                st.session_state[route[1]]=e['linked_id']
                st.session_state['nav_request']=route[0]
                st.rerun()
    st.markdown('### Original articles and source evidence')
    raw=[]
    for item in _list(chosen.get('source_evidence')):
        if isinstance(item,dict):raw.append((item.get('url') or item.get('source_url'),item.get('title') or item.get('headline')))
        else:raw.append((item,None))
    try:
        observed=(sb.table('pc_v08_news_items').select('source_url,headline,publisher')
            .eq('ingestion_job_id',chosen['ingestion_job_id'])
            .eq('source_record_key',chosen['source_record_key']).limit(100).execute().data or [])
        raw.extend((n['source_url'],n.get('headline') or n.get('publisher')) for n in observed)
    except Exception as exc:st.caption('Supplementary news unavailable: '+str(exc))
    seen=set()
    for url,label in raw:
        good=_link(url)
        if good and good not in seen:
            seen.add(good);st.markdown('- ['+str(label or urlsplit(good).netloc).replace(']','')+']('+good+')')
    if not seen:st.warning('Published story has no linked source URL. Flag for editorial correction.')


def render_live_company_links(sb, canonical_id):
    """Published relationships on real canonical company pages, not source mentions."""
    try:
        links=(sb.table('pc_v12_published_links').select('event_id,relationship')
            .eq('linked_type','entity').eq('linked_id',canonical_id).limit(100).execute().data or [])
        if not links:return
        ids=sorted({x['event_id'] for x in links})
        events=(sb.table('pc_v12_live_developments').select('event_id,title,start_date')
            .in_('event_id',ids).limit(100).execute().data or [])
        titles={e['event_id']:e for e in events}
        if not titles:return
        st.subheader('Verified related Trade developments')
        for idx,link in enumerate(links):
            ev=titles.get(link['event_id'])
            if not ev:continue
            st.write(str(ev.get('start_date') or '')+' · '+str(ev.get('title') or '')+' · '+str(link['relationship']))
            if st.button('Open published development',key='v12_company_link_'+str(canonical_id)+'_'+str(idx)):
                st.session_state['pc_v12_live_target']=link['event_id']
                st.session_state['nav_request']='Connected developments'
                st.rerun()
    except Exception as exc:st.caption('Published graph unavailable: '+str(exc))
