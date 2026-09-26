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
    render_agreements_for_event(sb,chosen['event_id'])
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
    """Published relationships and first-class agreements on canonical company pages."""
    render_live_company_agreements(sb,canonical_id)
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


def _agreement_name_rows(sb, links, kind):
    ids=[x['entity_id' if kind=='entity' else 'asset_id'] for x in links]
    if not ids:return {}
    table='pc_entities' if kind=='entity' else 'pc_assets'
    pk='entity_id' if kind=='entity' else 'asset_id'
    result=[]
    for n in range(0,len(ids),50):
        result += (sb.table(table).select(pk+',name').in_(pk,ids[n:n+50]).limit(50).execute().data or [])
    return {x[pk]:x['name'] for x in result}


def _show_agreement(sb, agreement, key_prefix):
    """Staff-only display; only DB-persisted canonical endpoints are shown."""
    aid=agreement['agreement_id']
    st.markdown('**'+str(agreement.get('title') or 'Agreement')+'**')
    st.caption('Instrument: '+str(agreement.get('instrument_type') or 'Agreement').replace('_',' ') +
      ' · Status: '+str(agreement.get('agreement_status') or 'Not confirmed')+
      ' · Announced: '+str(agreement.get('announced_date') or 'date unconfirmed'))
    if agreement.get('summary'):st.write(agreement['summary'])
    if not agreement.get('official_document_available'):
        st.caption('Source is an announcement; signed agreement text has not been provided.')
    parties=(sb.table('pc_v14_agreement_parties').select('entity_id,role')
             .eq('agreement_id',aid).limit(100).execute().data or [])
    projects=(sb.table('pc_v14_agreement_projects').select('asset_id,relationship')
              .eq('agreement_id',aid).limit(100).execute().data or [])
    party_names=_agreement_name_rows(sb,parties,'entity')
    project_names=_agreement_name_rows(sb,projects,'asset')
    if parties:
        st.markdown('**Parties and organisations**')
        for i,p in enumerate(parties):
            label=party_names.get(p['entity_id'],p['entity_id'])
            st.write(label+' · '+p.get('role','').replace('_',' '))
            if st.button('Open '+label, key=key_prefix+'_party_'+aid+'_'+str(i)):
                st.session_state['company_pick_id']=p['entity_id']
                st.session_state['nav_request']='Companies';st.rerun()
    if projects:
        st.markdown('**Referenced projects and infrastructure**')
        for i,project in enumerate(projects):
            label=project_names.get(project['asset_id'],project['asset_id'])
            st.write(label+' · '+project.get('relationship','').replace('_',' '))
            if st.button('Open '+label,key=key_prefix+'_asset_'+aid+'_'+str(i)):
                st.session_state['port_pick_id']=project['asset_id']
                st.session_state['nav_request']='Ports';st.rerun()
    evidence=agreement.get('evidence') or []
    if isinstance(evidence,str):
        try:evidence=json.loads(evidence)
        except ValueError:evidence=[]
    for index,item in enumerate(evidence):
        url=item.get('url') if isinstance(item,dict) else item
        safe=_link(url)
        if safe:st.markdown('- [Original supporting source '+str(index+1)+']('+safe+')')


def render_agreements_for_event(sb,event_id):
    try:
        rows=(sb.table('pc_v14_agreements').select('*').eq('event_id',event_id).limit(10).execute().data or [])
        for idx,a in enumerate(rows):
            with st.expander('Agreement / MoU: '+str(a['title']),expanded=True):
                _show_agreement(sb,a,'v14_event_'+str(idx))
    except Exception as exc:st.caption('Agreement registry not available: '+str(exc))


def render_live_company_agreements(sb,entity_id):
    try:
        assoc=(sb.table('pc_v14_agreement_parties').select('agreement_id,role')
               .eq('entity_id',entity_id).limit(50).execute().data or [])
        if not assoc:return
        ids=[x['agreement_id'] for x in assoc]
        rows=(sb.table('pc_v14_agreements').select('*').in_('agreement_id',ids)
              .order('announced_date',desc=True).limit(50).execute().data or [])
        if not rows:return
        st.subheader('Agreements & MoUs')
        for i,r in enumerate(rows):
            with st.expander(str(r['title']),expanded=i==0):_show_agreement(sb,r,'v14_company_'+entity_id+'_'+str(i))
    except Exception as exc:st.caption('Agreements unavailable: '+str(exc))


def render_live_asset_agreements(sb,asset_id):
    try:
        assoc=(sb.table('pc_v14_agreement_projects').select('agreement_id').eq('asset_id',asset_id).limit(50).execute().data or [])
        if not assoc:return
        rows=(sb.table('pc_v14_agreements').select('*').in_('agreement_id',[x['agreement_id'] for x in assoc])
              .order('announced_date',desc=True).limit(50).execute().data or [])
        if not rows:return
        st.subheader('Agreements & MoUs')
        for i,r in enumerate(rows):
            with st.expander(str(r['title']),expanded=i==0):_show_agreement(sb,r,'v14_asset_'+asset_id+'_'+str(i))
    except Exception as exc:st.caption('Asset agreements unavailable: '+str(exc))
