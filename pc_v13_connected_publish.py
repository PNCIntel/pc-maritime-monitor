"""v1.3: one-development dependency-aware canonical publisher; staff only.
Uses existing v1.0 backup/publish RPC and v1.2 link synchronizer.
No client-visible writes until analyst confirms the grouped source-backed package.
"""
from __future__ import annotations
import hashlib
import json
import streamlit as st

TYPE_TO_TABLE={'entity':'pc_entities','asset':'pc_assets','mobile_asset':'pc_mobile_assets'}
PRIMARY={'pc_entities':'entity_id','pc_assets':'asset_id','pc_mobile_assets':'mobile_asset_id','pc_events':'event_id'}


def source_urls(row):
    p=row.get('payload') or {};m=p.get('metadata') or {};rd=row.get('resolution_details') or {}
    out=[]
    for v in (m.get('source_url'),rd.get('source_urls'),m.get('research_sources'),m.get('source_urls')):
        for x in v if isinstance(v,list) else ([v] if v else []):
            u=x.get('url') if isinstance(x,dict) else x
            if isinstance(u,str) and u.startswith(('https://','http://')) and u not in out:out.append(u)
    return out


def build_dependencies(event,staged,published):
    evkey=(event.get('payload') or {}).get('event_id')
    parent={}
    for x in staged:
        pk=PRIMARY.get(x['target_table'])
        if pk and x['target_table']!='pc_events':
            key=(x['target_table'],str((x.get('payload') or {}).get(pk) or ''))
            if key[1] and (key not in parent or x['staged_record_id'] in published):parent[key]=x
    entries={};exceptions=[]
    for x in staged:
        if x['target_table']!='pc_event_links':continue
        p=x.get('payload') or {}
        if p.get('event_id')!=evkey:continue
        table=TYPE_TO_TABLE.get(p.get('linked_type'))
        name=str(p.get('linked_name') or '').strip();orig=str(p.get('linked_id') or '').strip()
        if not table or not orig or not name:
            exceptions.append({'Name':name,'Reason':'Unsupported or incomplete endpoint'});continue
        related=parent.get((table,orig));refs=source_urls(related) if related else source_urls(x)
        if not refs:
            exceptions.append({'Name':name,'Reason':'No source URL'});continue
        key=(table,orig)
        if key not in entries:
            entries[key]={'table':table,'name':name,'original':orig,'stage':related,
                          'published':bool(related and related['staged_record_id'] in published),
                          'sources':refs,'links':[x]}
        else:entries[key]['links'].append(x)
    return list(entries.values()),exceptions


def lookup(sb,items):
    """Targeted exact-name queries only; never scan entire entity registries."""
    groups={}
    for item in items:
        if not item['published']:groups.setdefault(item['table'],set()).add(item['name'])
    found={}
    for table,names in groups.items():
        pk=PRIMARY[table]
        cols=pk+',name'+(',entity_type,hq_country,subtype' if table=='pc_entities' else ',asset_type,country' if table=='pc_assets' else ',imo,flag')
        allrows=[];names=sorted(names)
        for start in range(0,len(names),20):
            allrows.extend(sb.table(table).select(cols).in_('name',names[start:start+20]).limit(250).execute().data or [])
        for name in names:
            found[table,name.casefold()]=[r for r in allrows if str(r.get('name') or '').casefold()==name.casefold()]
    return found


def prepare_missing(sb,job,item):
    """Create idempotent SOURCE-BACKED staged proposal; never create a bare canonical object."""
    token=hashlib.sha256((item['table']+'|'+item['original']).encode()).hexdigest()[:24]
    sourcekey='v13:dependency:'+token
    exists=(sb.table('pc_staged_records').select('staged_record_id').eq('ingestion_job_id',job)
            .eq('source_record_key',sourcekey).limit(1).execute().data or [])
    if exists:return exists[0]['staged_record_id']
    name=item['name'];n=name.casefold();table=item['table'];pk=PRIMARY[table]
    p={'name':name,pk:item['original'],'record_status':'provisional'}
    metadata={'research_sources':[{'url':u} for u in item['sources']],
              'source_limitations':'Source establishes the named object or its mention; ownership/operating rights are not inferred.',
              'original_package_id':item['original'],'generated_from_event_link':True}
    if table=='pc_entities':
        p['entity_type']='government' if 'government' in n else 'government_agency' if 'authority' in n else 'company'
    elif table=='pc_assets':
        p['asset_type']='special_economic_zone' if 'sez' in n or 'economic zone' in n else 'berth' if 'berth' in n else 'port' if 'port' in n else 'infrastructure'
        if 'sez' in n or 'economic zone' in n or 'proposed' in n:metadata['development_status']='proposed'
    else:p['asset_type']='vessel'
    p['metadata']=metadata
    inserted=sb.table('pc_staged_records').insert({'ingestion_job_id':job,'target_table':table,
      'source_record_key':sourcekey,'natural_key':name,'payload':p,'action':'REVIEW',
      'review_status':'pending','validation_status':'pending','resolution_status':'UNRESOLVED',
      'resolution_method':'source-backed event dependency',
      'resolution_details':{'source_urls':item['sources'],'package_original_id':item['original']}}).execute().data or []
    if not inserted:raise RuntimeError('Cannot stage '+name)
    return inserted[0]['staged_record_id']


def render_connected_publish(sb,job,staged,published):
    st.subheader('Publish the complete development')
    st.caption('Automatically match existing companies and assets, prepare missing source-backed objects, '
               'back up and publish the approved package, and connect verified endpoints. No manual IDs.')
    events=[x for x in staged if x['target_table']=='pc_events' and (x.get('payload') or {}).get('event_id')]
    if not events:st.info('No staged events available.');return
    search=st.text_input('Find development',value='Ogun',key='v13_lookup_'+job)
    matching=[x for x in events if search.casefold() in x['natural_key'].casefold()] if search else events
    if not matching:st.info('No matching developments.');return
    event=st.selectbox('Development',matching,format_func=lambda x:x['natural_key'],key='v13_event_'+job)
    deps,exceptions=build_dependencies(event,staged,published)
    already=event['staged_record_id'] in published
    try:
        candidates=lookup(sb,deps)
        content=(sb.table('pc_v08_trade_content').select('description,pc_assessment,editorial_status')
                 .eq('ingestion_job_id',job).eq('source_record_key',event['source_record_key'])
                 .order('version',desc=True).limit(1).execute().data or [])
    except Exception as ex:st.error('Research/registry query failed: '+str(ex));return
    latest=content[0] if content else {}
    if not latest.get('description'):
        st.error('Development has no descriptive sidecar. Complete it in the existing assessment editor first.');return
    st.write('**Extracted account:** '+str(latest['description'])[:800])
    st.caption(str(len(deps))+' unique source-linked objects · '+str(len(exceptions))+' exceptions · '
               +('event already published' if already else 'event awaiting publication'))
    if exceptions:
        with st.expander('Unresolved source/relationship exceptions'):
            st.dataframe(exceptions,hide_index=True,use_container_width=True)
    with st.form('v13_one_'+event['staged_record_id']):
        decisions=[]
        for i,item in enumerate(deps):
            st.markdown('**'+item['name']+'** · '+item['table'] + (' · PUBLISHED' if item['published'] else ''))
            if item['published']:continue
            st.caption('Evidence: '+', '.join(item['sources'][:2]))
            hits=candidates.get((item['table'],item['name'].casefold()),[])
            choices=['HOLD']+[h[PRIMARY[item['table']]] for h in hits]+(['NEW'] if not hits else [])
            def label(x):
                if x=='HOLD':return 'Hold — identity/evidence unclear'
                if x=='NEW':return 'Create missing source-backed object'
                r=next(h for h in hits if h[PRIMARY[item['table']]]==x)
                return 'Existing: '+str(r.get('name'))+' · '+str(x)+' · '+str(r.get('hq_country') or r.get('country') or '')
            decision=st.selectbox('Identity for '+item['name'],choices,format_func=label,
                 index=0 if len(hits)>1 else 1,key='v13_node_'+event['staged_record_id']+'_'+str(i))
            decisions.append((item,decision))
        if not already:
            # Recheck same-title AND event date, rather than blindly creating duplicates.
            p=event.get('payload') or {};title=str(p.get('title') or event['natural_key']);date=p.get('start_date')
            try:
                q=sb.table('pc_events').select('event_id,title,start_date').eq('title',title)
                if date:q=q.eq('start_date',date)
                hits=q.limit(10).execute().data or []
            except Exception as exc:st.error('Event duplicate check unavailable: '+str(exc));return
            opts=['HOLD']+[h['event_id'] for h in hits]+(['NEW'] if not hits else [])
            event_choice=st.selectbox('Development identity',opts,index=0 if len(hits)>1 else 1,
                 format_func=lambda x:'Hold for duplicate review' if x=='HOLD' else 'Create event' if x=='NEW' else 'Match existing event · '+x)
        else:event_choice='PUBLISHED'
        reviewed=st.checkbox('I checked source evidence, all proposed identities, event date and the latest assessment')
        authorised=st.checkbox('Approve automatic backup, canonical publication and verified mention links')
        reviewer=st.text_input('Audit name',value='DCM')
        go=st.form_submit_button('BACKUP + PUBLISH CONNECTED DEVELOPMENT',type='primary')
    if not go:return
    if not reviewed or not authorised or not reviewer.strip():st.error('Review and approval required. No write performed.');return
    if event_choice=='HOLD':st.warning('Resolve the development identity before publishing.');return
    selected=[(e,v) for e,v in decisions if v!='HOLD']
    if already and not selected:st.warning('No new objects selected; use Rebuild links for published records.');return
    if len(selected)+(not already)>40:st.error('More than 40 records selected; split this package into smaller groups.');return
    # Prevent publishing source-less events. This guard precedes ANY database writes.
    if not already and not source_urls(event):
        sourced=(sb.table('pc_v08_news_items').select('source_url').eq('ingestion_job_id',job)
                 .eq('source_record_key',event['source_record_key']).limit(1).execute().data or [])
        if not any(str(x.get('source_url') or '').startswith(('http://','https://')) for x in sourced):
            st.error('Missing original source link on the development. Attach evidence before publication.');return
    try:
        approvals=[]
        for item,decision in selected:
            sid=item['stage']['staged_record_id'] if item['stage'] else prepare_missing(sb,job,item)
            if sid in published:continue
            approvals.append({'staged_record_id':sid,'ingestion_job_id':job,
              'decision':'create_new' if decision=='NEW' else 'match_existing',
              'canonical_id':None if decision=='NEW' else decision,'source_verified':True,
              'content_reviewed':True,'client_visible':True,'event_duplicate_checked':False,
              'approved_by':reviewer.strip()})
        if not already:approvals.append({'staged_record_id':event['staged_record_id'],
           'ingestion_job_id':job,'decision':'create_new' if event_choice=='NEW' else 'match_existing',
           'canonical_id':None if event_choice=='NEW' else event_choice,'source_verified':True,
           'content_reviewed':True,'client_visible':True,'event_duplicate_checked':True,
           'approved_by':reviewer.strip()})
        ids=list(dict.fromkeys(x['staged_record_id'] for x in approvals))
        if len(ids)!=len(approvals):raise ValueError('Duplicate staged parent in batch; fix before publishing')
        if not ids:st.warning('All selected records already published.');return
        sb.table('pc_v10_approvals').upsert(approvals,on_conflict='staged_record_id').execute()
        backup=sb.rpc('pc_v10_backup_staged',{'p_job':job,'p_stage_ids':ids,'p_reviewer':reviewer.strip()}).execute().data
        st.info('Immutable backup: '+str(backup))
        out=sb.rpc('pc_v10_publish_approved',{'p_job':job,'p_stage_ids':ids,'p_backup':backup,'p_reviewer':reviewer.strip()}).execute().data
        st.success('Published: '+json.dumps(out))
        try:
            sync=sb.rpc('pc_v12_sync_published_links',{'p_job':job}).execute().data or {}
            st.success('Verified links: '+json.dumps(sync))
            if sync.get('exceptions'):st.warning(str(sync['exceptions'])+' links retained for source/identity review.')
        except Exception as ex:st.warning('Publication succeeded, but graph sync failed; retry the existing Rebuild links action: '+str(ex))
    except Exception as ex:
        st.error('Stopped; inspect publication log before retry: '+str(ex))
