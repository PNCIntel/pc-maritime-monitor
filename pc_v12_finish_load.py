"""P&C v1.2 admin-only completion workbench.

Reuses the EXISTING staged job, v0.8 source sidecars, v1.0 transactional
backup/publisher. Requires explicit approval; never guesses identities or
publishes unresolved relationships. Run behind require_super_admin().
"""
from __future__ import annotations
import hashlib
import json
import re
import streamlit as st
import pandas as pd

KEYS = {'pc_entities': 'entity_id', 'pc_assets': 'asset_id',
        'pc_mobile_assets': 'mobile_asset_id', 'pc_events': 'event_id'}
SOURCE_JOB = '8b1ce7e5-cd67-4be8-af3d-95dd788739d9'


def read_all(sb, table, columns, job, order='source_record_key', limit=3000):
    result = []
    for start in range(0,limit,500):
        q = (sb.table(table).select(columns).eq('ingestion_job_id',job)
             .order(order).range(start,start+499))
        batch = q.execute().data or []
        result.extend(batch)
        if len(batch)<500:break
    return result


def has_source(row):
    p=row.get('payload') or {}
    m=p.get('metadata') or {}
    rd=row.get('resolution_details') or {}
    refs=rd.get('source_urls') or m.get('research_sources') or m.get('source_urls') or []
    return any(isinstance(x,str) and x.startswith(('http://','https://'))
               or isinstance(x,dict) and str(x.get('url','')).startswith(('http://','https://'))
               for x in refs)


def exact_lookup(sb, rows):
    """Small, indexed, exact-name batches; no entire-registry downloads."""
    grouped={}
    for r in rows:
        table=r['target_table'];p=r.get('payload') or {}
        name=p.get('title') if table=='pc_events' else p.get('name')
        name=str(name or r['natural_key']).strip()
        grouped.setdefault(table,set()).add(name)
    matches={}
    for table,names in grouped.items():
        col='title' if table=='pc_events' else 'name'
        pk=KEYS[table]
        cols=f'{pk},{col}'
        if table=='pc_entities':cols+=',entity_type,hq_country,subtype'
        if table=='pc_assets':cols+=',asset_type,country'
        if table=='pc_mobile_assets':cols+=',imo,flag'
        if table=='pc_events':cols+=',start_date'
        gathered=[]
        unique=sorted(names)
        for start in range(0,len(unique),25):
            chunk=unique[start:start+25]
            gathered += sb.table(table).select(cols).in_(col,chunk).limit(1000).execute().data or []
        for name in names:
            found=[r for r in gathered if str(r.get(col) or '').strip().casefold()==name.casefold()]
            matches[(table,name.casefold())]=found
    return matches


def candidate_label(table,c):
    pk=KEYS[table]
    extra=[]
    for k in ('entity_type','subtype','hq_country','asset_type','country','imo','start_date'):
        if c.get(k):extra.append(str(c[k]))
    return str(c.get(pk))+' · '+str(c.get('title') or c.get('name'))+(' · '+' · '.join(extra) if extra else '')


def group_rows(sb,job):
    data=read_all(sb,'pc_staged_records',
        'staged_record_id,ingestion_job_id,target_table,source_record_key,natural_key,payload,resolution_details,resolution_status,review_status',job)
    ids=[r['staged_record_id'] for r in data]
    published=set()
    for n in range(0,len(ids),100):
        if ids[n:n+100]:
            found=(sb.table('pc_v10_publication_items').select('staged_record_id')
                  .in_('staged_record_id',ids[n:n+100]).execute().data or [])
            published.update(x['staged_record_id'] for x in found)
    return data,published


def source_context(sb,job,keys):
    found=set()
    for start in range(0,len(keys),100):
        if keys[start:start+100]:
            rows=(sb.table('pc_v08_news_items').select('source_record_key')
                  .eq('ingestion_job_id',job).in_('source_record_key',keys[start:start+100]).execute().data or [])
            found.update(x['source_record_key'] for x in rows)
    return found


def choose_missing_nodes(graph):
    """Propose, never fabricate identities, for source-backed missing endpoints."""
    objects=set()
    for r in graph:
        kind=r['target_table'];p=r.get('payload') or {}
        pk=KEYS.get(kind)
        if pk:objects.add((kind,str(p.get(pk) or '')))
    proposed={}
    for r in graph:
        if r['target_table']!='pc_event_links':continue
        p=r.get('payload') or {}
        linked=str(p.get('linked_type') or '')
        table={'entity':'pc_entities','asset':'pc_assets','mobile_asset':'pc_mobile_assets'}.get(linked)
        if not table:continue
        original=str(p.get('linked_id') or '')
        name=str(p.get('linked_name') or '').strip()
        if not name or (table,original) in objects:continue
        source=(p.get('metadata') or {}).get('source_url') or ''
        if not str(source).startswith(('http://','https://')):continue
        proposed.setdefault((table,name.casefold()),{'table':table,'name':name,'source':source,'original':original})
    return list(proposed.values())


def render_finish_load(sb):
    st.header('Finish Trade load')
    st.caption('Existing 252-record batch → review genuine exceptions → immutable backup → canonical publication → linked Trade records. No re-upload required.')
    jobs=(sb.table('pc_ingestion_jobs').select('ingestion_job_id,title,status,created_at')
          .order('created_at',desc=True).limit(80).execute().data or [])
    if not jobs:st.error('No ingestion jobs found.');return
    options=[j['ingestion_job_id'] for j in jobs]
    idx=options.index(SOURCE_JOB) if SOURCE_JOB in options else 0
    job=st.selectbox('Existing batch',options,index=idx,
        format_func=lambda j:next((x['title']+' · '+x['status']+' · '+j[:8] for x in jobs if x['ingestion_job_id']==j),j))
    if st.button('Refresh staged batch'):
        st.cache_data.clear();st.rerun()
    try:rows,published=group_rows(sb,job)
    except Exception as exc:st.error('Cannot read staged records: '+str(exc));return
    by_type={t:[r for r in rows if r['target_table']==t and r['staged_record_id'] not in published] for t in KEYS}
    x1,x2,x3,x4=st.columns(4)
    x1.metric('Existing staged',len(rows));x2.metric('Already published',len(published))
    x3.metric('Ready to inspect',sum(map(len,by_type.values())))
    x4.metric('Relationship rows',sum(r['target_table']=='pc_event_links' for r in rows))
    with st.expander('Where the Ogun / Port Canaveral objects are',expanded=False):
        names=['Ogun','DP World','Gateway','Blue Marine','GT USA','Canaveral','Berth 6']
        filtered=[r for r in rows if any(x.casefold() in str(r['natural_key']).casefold() for x in names)]
        st.dataframe(pd.DataFrame([{'Record':r['natural_key'],'Table':r['target_table'],
          'State':'Published' if r['staged_record_id'] in published else 'Staged',
          'Has source':has_source(r)} for r in filtered]),hide_index=True,use_container_width=True)
    st.info('Only original source-backed records are eligible. Repeated coverage enriches existing identities; a matching name never proves ownership, concession or operating status.')
    label={'pc_entities':'Companies & government agencies','pc_assets':'Ports, SEZs & infrastructure',
           'pc_mobile_assets':'Vessels','pc_events':'Developments with full analysis'}
    target=st.selectbox('Publish in dependency order',list(KEYS),format_func=lambda x:label[x])
    available=by_type[target]
    search=st.text_input('Search these records',placeholder='Ogun, GT USA, DP World…')
    if search:available=[r for r in available if search.casefold() in r['natural_key'].casefold()]
    page=st.number_input('Page (20 per page)',1,max(1,(len(available)+19)//20),1,step=1)
    shown=available[(page-1)*20:page*20]
    if not shown:
        st.success('No unpublished records in this view.');return
    try:
        matches=exact_lookup(sb,shown)
        news_keys=source_context(sb,job,[r['source_record_key'] for r in shown])
    except Exception as exc:st.error('Canonical/news lookup failed: '+str(exc));return
    table=[]
    for r in shown:
        p=r.get('payload') or {}
        name=str(p.get('title') if target=='pc_events' else p.get('name') or r['natural_key']).strip()
        options=matches.get((target,name.casefold()),[])
        if target=='pc_events':
            d=p.get('start_date')
            options=[x for x in options if str(x.get('start_date') or '')==str(d or '')]
        table.append({'r':r,'name':name,'candidates':options,'has_source':has_source(r) or r['source_record_key'] in news_keys})
    st.dataframe(pd.DataFrame([{'Name':x['name'],'Existing exact matches':len(x['candidates']),
        'Source available':x['has_source'],
        'Status':'Ambiguous — choose ID' if len(x['candidates'])>1 else 'Exact match' if x['candidates'] else 'New candidate'} for x in table]),
        hide_index=True,use_container_width=True)
    if target=='pc_events':
        with st.expander('Improve the full commercial assessment BEFORE approving',expanded=False):
            opts=[x['r'] for x in table]
            chosen=st.selectbox('Development to edit',opts,
                format_func=lambda r:r.get('natural_key') or 'Untitled',key='v12_edit_event')
            found=(sb.table('pc_v08_trade_content').select('*')
                .eq('ingestion_job_id',job).eq('source_record_key',chosen['source_record_key'])
                .order('version',desc=True).limit(1).execute().data or [])
            old=found[0] if found else {}
            payload=chosen.get('payload') or {};meta=payload.get('metadata') or {}
            with st.form('v12_analysis_revision_'+str(chosen['staged_record_id'])):
                happened=st.text_area('What happened — sourced facts',value=str(old.get('description') or payload.get('description') or ''),height=110)
                matters=st.text_area('Why it matters for trade and logistics',value=str(old.get('what_it_means') or meta.get('why_it_matters') or ''),height=100)
                operational=st.text_area('Operational implications — distinguish observed from possible',value=str(old.get('operational_impact') or ''),height=90)
                commercial=st.text_area('Commercial implications and business exposure',value=str(old.get('commercial_implications') or meta.get('commercial_implications') or ''),height=110)
                assessment=st.text_area('P&C assessment — evidence, uncertainty and scenarios',value=str(old.get('pc_assessment') or meta.get('assessment') or ''),height=130)
                raw_mon=old.get('monitoring_indicators') or meta.get('monitoring_indicators') or []
                mon=st.text_area('Monitoring indicators — one per line',value='\n'.join(str(x.get('indicator') or x.get('text') or '') if isinstance(x,dict) else str(x) for x in raw_mon),height=100)
                analyst_reviewed=st.checkbox('I have checked these statements against the linked original evidence')
                submit_revision=st.form_submit_button('Save versioned assessment',type='secondary')
            if submit_revision:
                if not analyst_reviewed or not (happened.strip() and assessment.strip()):
                    st.error('Source review, a factual description and an assessment are required.')
                else:
                    v=(int(old.get('version') or 0)+1)
                    record={'ingestion_job_id':job,'source_record_key':chosen['source_record_key'],
                        'target_table':'pc_events','target_key':old.get('target_key') or payload.get('event_id') or chosen['natural_key'],
                        'title':old.get('title') or payload.get('title') or chosen['natural_key'],
                        'description':happened,'what_it_means':matters,'operational_impact':operational,
                        'commercial_implications':commercial,'pc_assessment':assessment,
                        'monitoring_indicators':[x.strip() for x in mon.splitlines() if x.strip()],
                        'research_gaps':old.get('research_gaps') or meta.get('research_gaps') or [],
                        'source_evidence':old.get('source_evidence') or meta.get('research_sources') or [],
                        'text_origin':'analyst_revision','editorial_status':'reviewed','version':v}
                    try:
                        sb.table('pc_v08_trade_content').insert(record).execute()
                        st.success(f'Assessment version {v} saved. Original source version preserved.')
                    except Exception as exc:st.error('Could not save revision: '+str(exc))
    choices=st.multiselect('Select records to move (20 maximum)',list(range(len(table))),
      format_func=lambda i:table[i]['name']+' · '+str(len(table[i]['candidates']))+' existing',key='v12_picks_'+job+'_'+target+'_'+str(page))
    if not choices:return
    choices=choices[:20]
    with st.form('v12_approve_'+job+target+str(page)):
        decisions=[]
        for n in choices:
            entry=table[n];r=entry['r']; candidates=entry['candidates']
            st.markdown('**'+entry['name']+'**')
            if not entry['has_source']:
                st.error('Missing source URL in this record. Remove it from selection until evidence is attached.')
            if candidates:
                opts=['Hold for review']+[c[KEYS[target]] for c in candidates]
                pick=st.selectbox('Existing record',opts,
                    format_func=lambda x:'Hold for review' if x=='Hold for review' else candidate_label(target,next(c for c in candidates if c[KEYS[target]]==x)),
                    key='v12_existing_'+str(r['staged_record_id']),index=1 if len(candidates)==1 else 0)
                decision='match_existing' if pick!='Hold for review' else None
                chosen_id=pick if decision else None
            else:
                decision='create_new' if st.checkbox('Create a NEW canonical record after evidence review',
                    value=False,key='v12_new_'+str(r['staged_record_id'])) else None
                chosen_id=None
            decisions.append((r,decision,chosen_id,entry['has_source']))
        verified=st.checkbox('I inspected the source evidence and the identity choices above',value=False)
        reviewed=st.checkbox('I reviewed descriptions, operational/commercial implications, monitoring and original news links',value=False)
        if target=='pc_events':
            duplicates=st.checkbox('I checked the event dates, names and duplication against the existing event register',value=False)
        else:duplicates=True
        visible=st.checkbox('Make reviewed narrative available in Trade (subject to access controls)',value=True)
        operator=st.text_input('Analyst / audit name',value='DCM')
        submit=st.form_submit_button('BACKUP + publish selected records',type='primary')
    if submit:
        eligible=[x for x in decisions if x[1] and x[3]]
        if not verified or not reviewed or not duplicates or not operator.strip():
            st.error('Review confirmations and analyst name are required. Nothing published.');return
        if len(eligible)!=len(decisions):
            st.error('One or more records have no verified source or approved identity decision. Nothing published.');return
        prepared=[]
        for r,decision,cid,_ in eligible:
            prepared.append({'staged_record_id':r['staged_record_id'],'ingestion_job_id':job,
                'decision':decision,'canonical_id':cid,'source_verified':True,
                'event_duplicate_checked':bool(duplicates and target=='pc_events'),
                'content_reviewed':True,'client_visible':bool(visible),
                'approved_by':operator.strip()})
        try:
            ids=[r['staged_record_id'] for r,_,_,_ in eligible]
            sb.table('pc_v10_approvals').upsert(prepared,on_conflict='staged_record_id').execute()
            backup=sb.rpc('pc_v10_backup_staged',{'p_job':job,'p_stage_ids':ids,
                'p_reviewer':operator.strip()}).execute().data
            st.info('Immutable backup created: '+str(backup))
            result=sb.rpc('pc_v10_publish_approved',{'p_job':job,'p_stage_ids':ids,
                'p_backup':backup,'p_reviewer':operator.strip()}).execute().data
            st.success('Canonical publication completed: '+json.dumps(result))
            try:
                edges=sb.rpc('pc_v12_sync_published_links',{'p_job':job}).execute().data
                st.success('Verified links materialized: '+json.dumps(edges))
            except Exception as exc:st.warning('Published records retained; graph sync can be retried: '+str(exc))
            st.cache_data.clear()
        except Exception as exc:
            st.error('Publication stopped. Backup retained; do not click again until checking publication items: '+str(exc))
    st.divider()
    if st.button('Rebuild links for ALREADY published records (safe to repeat)',key='v12_sync_'+job):
        try:st.success(sb.rpc('pc_v12_sync_published_links',{'p_job':job}).execute().data)
        except Exception as exc:st.error(str(exc))
    with st.expander('Source-mentioned entities missing from this staging package'):
        missing=choose_missing_nodes(rows)
        st.dataframe(pd.DataFrame(missing),hide_index=True,use_container_width=True)
        st.caption('Requires source-backed candidate staging and identity review. No new company, agency, SEZ or vessel is created by a mere article mention.')
