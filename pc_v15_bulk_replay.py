"""P&C v1.5 — fresh replay + bulk connected publication.

Analyst workflow: extract files/URLs in Universal intake -> open this page ->
queue fresh replay -> process to staging -> auto-resolve safe identities -> publish
eligible canonical objects -> sync event graph -> sync agreements. Ambiguities are
held as exceptions; no manual DB IDs are required.
"""
from __future__ import annotations
import hashlib, json, uuid
from datetime import datetime, timezone
from collections import defaultdict, Counter
import streamlit as st
import pandas as pd

ID_TABLES={'pc_entities':'entity_id','pc_assets':'asset_id','pc_mobile_assets':'mobile_asset_id','pc_events':'event_id'}
NAME_COL={'pc_entities':'name','pc_assets':'name','pc_mobile_assets':'name','pc_events':'title'}


def _norm(x): return ' '.join(str(x or '').strip().casefold().split())

def _urls(row):
    p=row.get('payload') or {}; m=p.get('metadata') or {}; d=row.get('resolution_details') or {}
    vals=[]
    for v in (d.get('source_urls'),m.get('research_sources'),m.get('source_urls'),m.get('source_url')):
        for x in v if isinstance(v,list) else ([v] if v else []):
            u=x.get('url') if isinstance(x,dict) else x
            if isinstance(u,str) and u.startswith(('http://','https://')) and u not in vals: vals.append(u)
    return vals

def _all_staged(sb,job):
    out=[]
    for start in range(0,5000,500):
        b=(sb.table('pc_staged_records').select('*').eq('ingestion_job_id',job)
           .order('source_record_key').range(start,start+499).execute().data or [])
        out.extend(b)
        if len(b)<500: break
    return out

def _published(sb,ids):
    out={}
    for start in range(0,len(ids),100):
        chunk=ids[start:start+100]
        if not chunk: continue
        rows=(sb.table('pc_v10_publication_items').select('staged_record_id,canonical_table,canonical_id')
              .in_('staged_record_id',chunk).execute().data or [])
        out.update({r['staged_record_id']:r for r in rows})
    return out

def _content_keys(sb,job,keys):
    found=set()
    for start in range(0,len(keys),100):
        chunk=keys[start:start+100]
        if chunk:
            rows=(sb.table('pc_v08_trade_content').select('source_record_key')
                  .eq('ingestion_job_id',job).in_('source_record_key',chunk).execute().data or [])
            found.update(r['source_record_key'] for r in rows)
    return found

def _canon_hits(sb,table,rows):
    """Unique exact-name/date or IMO matches. Never full-registry scans."""
    by={}
    if table=='pc_mobile_assets':
        imos=sorted({str((r.get('payload') or {}).get('imo') or '').strip() for r in rows if str((r.get('payload') or {}).get('imo') or '').strip()})
        for start in range(0,len(imos),25):
            chunk=imos[start:start+25]
            if chunk:
                for x in (sb.table(table).select('mobile_asset_id,name,imo,flag').in_('imo',chunk).limit(500).execute().data or []):
                    by.setdefault(('imo',str(x.get('imo') or '')),[]).append(x)
    names=sorted({_norm((r.get('payload') or {}).get(NAME_COL[table]) or r.get('natural_key')) for r in rows})
    raw_names=[str((r.get('payload') or {}).get(NAME_COL[table]) or r.get('natural_key') or '').strip() for r in rows]
    for start in range(0,len(raw_names),25):
        chunk=list(dict.fromkeys(raw_names[start:start+25]))
        if not chunk: continue
        cols=ID_TABLES[table]+','+NAME_COL[table]
        if table=='pc_entities': cols+=',entity_type,hq_country'
        elif table=='pc_assets': cols+=',asset_type,country'
        elif table=='pc_mobile_assets': cols+=',imo,flag'
        else: cols+=',start_date'
        q=sb.table(table).select(cols).in_(NAME_COL[table],chunk).limit(1000)
        for x in (q.execute().data or []):
            by.setdefault(('name',_norm(x.get(NAME_COL[table]))),[]).append(x)
    return by

def _plan(sb,job,staged):
    candidates=[r for r in staged if r['target_table'] in ID_TABLES]
    content=_content_keys(sb,job,[r['source_record_key'] for r in candidates])
    pub=_published(sb,[r['staged_record_id'] for r in candidates])
    hits={}
    for table in ID_TABLES:
        rows=[r for r in candidates if r['target_table']==table and r['staged_record_id'] not in pub]
        if rows: hits[table]=_canon_hits(sb,table,rows)
    # Group package duplicates so only one NEW leader is created; followers match leader after publication.
    groups=defaultdict(list)
    for r in candidates:
        if r['staged_record_id'] in pub: continue
        p=r.get('payload') or {}; table=r['target_table']
        if table=='pc_mobile_assets' and p.get('imo'): g=(table,'imo:'+str(p['imo']).strip())
        elif table=='pc_events': g=(table,_norm(p.get('title') or r['natural_key'])+'|'+str(p.get('start_date') or ''))
        else: g=(table,_norm(p.get(NAME_COL[table]) or r['natural_key']))
        groups[g].append(r)
    ready=[]; followers=[]; exceptions=[]
    for g,rows in groups.items():
        leader=rows[0]; table=leader['target_table']; p=leader.get('payload') or {}
        name=str(p.get(NAME_COL[table]) or leader['natural_key']).strip(); source=bool(_urls(leader))
        matched=[]
        if table=='pc_mobile_assets' and p.get('imo'):
            matched=hits.get(table,{}).get(('imo',str(p.get('imo')).strip()),[])
        if not matched:
            matched=hits.get(table,{}).get(('name',_norm(name)),[])
            if table=='pc_events' and matched:
                date=str(p.get('start_date') or '')
                matched=[x for x in matched if str(x.get('start_date') or '')==date]
        # de-dup canonical hits by ID
        pk=ID_TABLES[table]; uniq={str(x.get(pk)):x for x in matched if x.get(pk)}; matched=list(uniq.values())
        if len(matched)>1:
            exceptions.append({'Table':table,'Name':name,'Reason':'multiple canonical matches','Candidates':', '.join(uniq)})
            continue
        if len(matched)==1:
            cid=str(matched[0][pk])
            for r in rows: ready.append((r,'match_existing',cid))
            continue
        # Safe new requires original evidence; events additionally need stored narrative.
        if not source:
            exceptions.append({'Table':table,'Name':name,'Reason':'no source URL'})
            continue
        if table=='pc_events' and leader['source_record_key'] not in content:
            exceptions.append({'Table':table,'Name':name,'Reason':'no narrative/assessment sidecar'})
            continue
        ready.append((leader,'create_new',None))
        for r in rows[1:]: followers.append((r,leader['staged_record_id']))
    return ready,followers,exceptions,pub

def _approval(row,decision,cid,reviewer,visible):
    return {'staged_record_id':row['staged_record_id'],'ingestion_job_id':row['ingestion_job_id'],
      'decision':decision,'canonical_id':cid,'source_verified':True,
      'event_duplicate_checked':row['target_table']=='pc_events','content_reviewed':True,
      'client_visible':bool(visible and row['target_table']=='pc_events'),'approved_by':reviewer,
      'reviewed_at':datetime.now(timezone.utc).isoformat()}

def _publish_chunk(sb,job,items,reviewer):
    if not items:return []
    approvals=[_approval(r,d,c,reviewer,True) for r,d,c in items]
    sb.table('pc_v10_approvals').upsert(approvals,on_conflict='staged_record_id').execute()
    ids=[r['staged_record_id'] for r,_,_ in items]
    backup=sb.rpc('pc_v10_backup_staged',{'p_job':job,'p_stage_ids':ids,'p_reviewer':reviewer}).execute().data
    result=sb.rpc('pc_v10_publish_approved',{'p_job':job,'p_stage_ids':ids,'p_backup':backup,'p_reviewer':reviewer}).execute().data
    return [{'backup':backup,'result':result}]

def _publish_ready(sb,job,ready,followers,reviewer):
    results=[]
    # First publish all matches and NEW leaders, max 40 to leave RPC headroom.
    for start in range(0,len(ready),40): results += _publish_chunk(sb,job,ready[start:start+40],reviewer)
    # Map new leaders -> canonical IDs, then publish package-duplicate followers as matches.
    leader_ids=[leader for _,leader in followers]
    leader_map={}
    if leader_ids:
        for start in range(0,len(leader_ids),100):
            rows=(sb.table('pc_v10_publication_items').select('staged_record_id,canonical_id')
                  .in_('staged_record_id',leader_ids[start:start+100]).execute().data or [])
            leader_map.update({r['staged_record_id']:r['canonical_id'] for r in rows})
    follow_ready=[]
    for row,leader in followers:
        cid=leader_map.get(leader)
        if cid: follow_ready.append((row,'match_existing',cid))
    for start in range(0,len(follow_ready),40): results += _publish_chunk(sb,job,follow_ready[start:start+40],reviewer)
    return results,len(follow_ready)

def _process_job_queue(sb,job,batch=50,max_batches=30):
    from pc_bulk_worker import process_batch, update_job_summary
    worker='pc-v15-'+uuid.uuid4().hex[:12];total=Counter();claimed=0
    for _ in range(max_batches):
        rows=sb.rpc('pc_v15_claim_job_queue',{'p_job':job,'p_worker':worker,'p_limit':batch}).execute().data or []
        if not rows:break
        claimed+=len(rows);total.update(process_batch(sb,rows,worker))
    update_job_summary(sb,job)
    return claimed,dict(total)

def render_bulk_replay(sb,active_package):
    st.header('Reload & republish — end-to-end')
    st.caption('Fresh source package → stage → canonical identities → developments → verified graph → agreements. Only genuine ambiguities are held for review.')
    if active_package:
        st.success(f'{len(active_package):,} extracted records are in memory from Universal intake.')
    else:
        st.info('First open Universal intake, add your files / URLs and run extraction. Then return here. The extracted package stays in this Streamlit session.')
    reviewer=st.text_input('Audit name',value='DCM',key='v15_reviewer')
    title=st.text_input('Fresh replay job name',value='P&C fresh reload and republish',key='v15_title')
    c1,c2=st.columns(2)
    with c1:
        if st.button('1 · Queue FRESH replay from current extracted package',type='primary',disabled=not active_package):
            try:
                from pc_v07_core import enqueue
                # Timestamp in title makes the replay intentionally fresh rather than reusing old fingerprint title semantics.
                fresh_title=title+' · '+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
                job,count,reused=enqueue(sb,active_package,title=fresh_title,ai_research=False)
                st.session_state['v15_job']=job
                st.success(f'Fresh replay job {job} queued with {count:,} records.')
            except Exception as exc:st.error('Could not queue fresh replay: '+str(exc))
    job=st.text_input('Replay job ID',value=st.session_state.get('v15_job',''),key='v15_job_box')
    if job: st.session_state['v15_job']=job.strip()
    if not job:return
    try:
        stats={}
        for s in ('queued','processing','staged','failed'):
            q=sb.table('pc_v07_queue').select('queue_id',count='exact',head=True).eq('ingestion_job_id',job).eq('status',s).execute();stats[s]=q.count or 0
        a,b,c,d=st.columns(4);a.metric('Queued',stats['queued']);b.metric('Processing',stats['processing']);c.metric('Staged',stats['staged']);d.metric('Failed',stats['failed'])
    except Exception as exc:st.error('Cannot read replay job: '+str(exc));return
    with c2:
        if st.button('2 · Process ALL queued records in Streamlit',disabled=stats['queued']==0):
            try:
                claimed,counts=_process_job_queue(sb,job,batch=50,max_batches=40)
                st.success(f'Processed {claimed:,} queue rows. Result: {counts}.')
                st.rerun()
            except Exception as exc:st.error('Queue processing stopped: '+str(exc))
    if stats['queued'] or stats['processing']:
        st.warning('Finish queue processing before canonical publication.');return
    staged=_all_staged(sb,job)
    if not staged:st.warning('No staged rows found yet.');return
    if st.button('3 · Analyse entire staged batch for automatic publication'):
        try:
            ready,followers,exceptions,pub=_plan(sb,job,staged)
            st.session_state['v15_plan']={'job':job,'ready':ready,'followers':followers,'exceptions':exceptions}
        except Exception as exc:st.error('Batch analysis failed: '+str(exc))
    plan=st.session_state.get('v15_plan')
    if not plan or plan.get('job')!=job:return
    ready=plan['ready'];followers=plan['followers'];exceptions=plan['exceptions']
    e1,e2,e3=st.columns(3);e1.metric('Auto-publish eligible',len(ready)+len(followers));e2.metric('Package duplicate followers',len(followers));e3.metric('Exceptions',len(exceptions))
    if exceptions:
        with st.expander('Exceptions requiring analyst review',expanded=False):st.dataframe(pd.DataFrame(exceptions),hide_index=True,use_container_width=True)
    with st.expander('Eligible sample',expanded=False):
        st.dataframe(pd.DataFrame([{'Table':r['target_table'],'Name':r['natural_key'],'Decision':d,'Canonical':c or 'NEW'} for r,d,c in ready[:200]]),hide_index=True,use_container_width=True)
    confirm=st.checkbox('I approve automatic publication of source-backed, unambiguous records; hold all exceptions.',key='v15_confirm')
    if st.button('4 · BACKUP + PUBLISH ELIGIBLE BATCH + SYNC GRAPH',type='primary',disabled=not confirm):
        try:
            results,follow_count=_publish_ready(sb,job,ready,followers,reviewer.strip() or 'DCM')
            graph=sb.rpc('pc_v12_sync_published_links',{'p_job':job}).execute().data
            agreements={}
            try:
                from pc_v14_agreement_sync import sync_published_job
                agreements=sync_published_job(sb,job,limit=500,reviewer=reviewer.strip() or 'DCM')
            except Exception as exc: agreements={'warning':str(exc)}
            st.session_state['v15_result']={'publication_batches':results,'duplicate_followers':follow_count,'graph':graph,'agreements':agreements,'exceptions':exceptions}
            st.success('Fresh replay publication completed. Open the report below and then check LIVE Trade.')
        except Exception as exc:st.error('Publication stopped safely: '+str(exc))
    result=st.session_state.get('v15_result')
    if result:
        st.subheader('Replay & republish report')
        st.json(result,expanded=False)
        st.download_button('Download complete replay report',json.dumps(result,indent=2,default=str),file_name='pc_v15_replay_report.json',mime='application/json')
        st.info('Now open the Trade app → Connected developments → LIVE. Published companies/assets are reusable across all developments; unresolved exceptions remain staged.')
