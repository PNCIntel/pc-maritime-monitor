"""Admin-only manual first-wave publisher. Requires the separate v1.0 SQL RPC migration.
Keep the multi-file/URL intake unchanged; staging is never deleted.
"""
import json
from datetime import datetime, timezone
import streamlit as st
import pandas as pd

ALLOWED = {'pc_entities','pc_assets','pc_mobile_assets','pc_events'}
PK = {'pc_entities':'entity_id','pc_assets':'asset_id','pc_mobile_assets':'mobile_asset_id','pc_events':'event_id'}


def page_rows(sb,job_id,page=1,page_size=50):
    return (sb.table('pc_staged_records')
            .select('staged_record_id,ingestion_job_id,source_record_key,target_table,natural_key,payload,resolution_status,resolved_entity_id,review_status,validation_status,resolution_details')
            .eq('ingestion_job_id',job_id).order('source_record_key')
            .range((page-1)*page_size,page*page_size-1).execute().data or [])


def make_approval(row,decision,canonical_id,source_verified,event_checked,content_reviewed,client_visible,reviewer):
    if row['target_table'] not in ALLOWED:raise ValueError('Graph links are not in the first publication wave')
    if not source_verified:raise ValueError('Verify sources before approval')
    if row['target_table']=='pc_events' and not event_checked:raise ValueError('Check event duplicates before approval')
    if decision=='match_existing' and not str(canonical_id or '').strip():raise ValueError('Canonical ID is required for a match')
    if client_visible and not content_reviewed:raise ValueError('Client-visible text requires editorial review')
    if not str(reviewer).strip():raise ValueError('Reviewer name required')
    return {'staged_record_id':row['staged_record_id'],'ingestion_job_id':row['ingestion_job_id'],
            'decision':decision,'canonical_id':str(canonical_id).strip() if decision=='match_existing' else None,
            'source_verified':True,'event_duplicate_checked':bool(event_checked),
            'content_reviewed':bool(content_reviewed),'client_visible':bool(client_visible),
            'approved_by':reviewer.strip(),'reviewed_at':datetime.now(timezone.utc).isoformat()}


def staged_export(rows):
    """Portable backup; the database RPC saves complete staged rows + matching sidecars."""
    return json.dumps({'exported_at':datetime.now(timezone.utc).isoformat(),
        'kind':'review-stage backup (not proof of canonical publication)','staged_records':rows},
        ensure_ascii=False,indent=2,default=str)


def render_publish_panel(sb):
    st.header('Move staged → Trade')
    st.info('Pilot: companies, physical assets, vessels and events only. Backups are immutable; original staging rows remain untouched. '
            'Graph links and corridors stay in review until their endpoints have been verified.')
    jobs=(sb.table('pc_ingestion_jobs').select('ingestion_job_id,title,status,created_at')
          .order('created_at',desc=True).limit(75).execute().data or [])
    if not jobs:st.warning('No staged jobs found.');return
    selected_job=st.selectbox('Staged batch',jobs,key='v10_job',format_func=lambda j:f"{j.get('title') or 'Batch'} — {j['ingestion_job_id'][:8]} — {j.get('status')}")
    job=selected_job['ingestion_job_id']
    page=st.number_input('Page (50 records per page)',min_value=1,step=1,value=1,key='v10_page')
    with st.expander('Backup the entire staged job — including graph links',expanded=False):
        st.caption('Creates permanent database snapshots in blocks of 200. No canonical changes. '
                   'For very large jobs, use the backup in separate windows to avoid Streamlit request timeouts.')
        offset=st.number_input('Backup starting offset',min_value=0,value=0,step=200,key='v10_backup_offset')
        backup_name=st.text_input('Backup operator name',key='v10_backup_name')
        if st.button('Back up next 1,000 staged records',key='v10_full_backup'):
            try:
                name=st.session_state.get('v10_reviewer') or backup_name
                if not str(name or '').strip():raise ValueError('Enter your analyst name in the reviewer field below and retry')
                snapshots=[]
                progress=st.progress(0)
                for n in range(5):
                    start=int(offset)+n*200
                    block=(sb.table('pc_staged_records').select('staged_record_id')
                        .eq('ingestion_job_id',job).order('source_record_key')
                        .range(start,start+199).execute().data or [])
                    if not block:break
                    bid=sb.rpc('pc_v10_backup_staged',{'p_job':job,
                        'p_stage_ids':[x['staged_record_id'] for x in block],
                        'p_reviewer':name.strip()}).execute().data
                    snapshots.append((bid,len(block)))
                    progress.progress((n+1)/5)
                    if len(block)<200:break
                if snapshots:st.success(f'Backed up {sum(c for _,c in snapshots)} staged rows in {len(snapshots)} immutable snapshots. Backup IDs: '+', '.join(str(x) for x,_ in snapshots))
                else:st.info('No records in this offset range.')
            except Exception as exc:st.error(f'Full-job backup stopped: {exc}. Earlier completed backup blocks remain saved.')
    rows=page_rows(sb,job,page)
    if not rows:st.info('No more staged records on this page.');return
    st.dataframe(pd.DataFrame([{'Name':r['natural_key'],'Table':r['target_table'],
         'Identity':r.get('resolution_status'),'Original review':r.get('review_status')}
         for r in rows]),hide_index=True,use_container_width=True)
    st.download_button('Download this page of staged records (portable backup)',staged_export(rows),
        file_name=f'pc_stage_{job[:8]}_page_{page}.json',mime='application/json',key='v10_download')
    eligible=[r for r in rows if r['target_table'] in ALLOWED]
    ignored=len(rows)-len(eligible)
    if ignored:st.warning(f'{ignored} corridor/relationship/source records on this page remain staged; not silently discarded.')
    if not eligible:return
    ids=[r['staged_record_id'] for r in eligible]
    published=(sb.table('pc_v10_publication_items').select('staged_record_id,canonical_id')
       .in_('staged_record_id',ids).execute().data or [])
    published_ids={r['staged_record_id'] for r in published}
    remaining=[r for r in eligible if r['staged_record_id'] not in published_ids]
    if published:st.success(f'{len(published)} already moved on this page; staging originals retained.')
    if not remaining:return
    approvals=(sb.table('pc_v10_approvals').select('*').in_('staged_record_id',[r['staged_record_id'] for r in remaining]).execute().data or [])
    approved={r['staged_record_id']:r for r in approvals}
    reviewer=st.text_input('Analyst name for the audit trail',key='v10_reviewer')
    choices=st.multiselect('Choose records to approve / move (up to 50)',remaining,
       format_func=lambda r:f"{r['target_table']} — {r['natural_key']} [{r.get('resolution_status')}]",
       key=f'v10_selection_{job}_{page}')
    if not choices:return
    if len(choices)>50:st.error('Choose at most 50 records.');return
    prepared=[]
    for r in choices:
        sid=r['staged_record_id'];previous=approved.get(sid,{})
        with st.expander(f"{r['target_table']} — {r['natural_key']}",expanded=len(choices)<4):
            st.caption('Existing approved identity is separate from unverified AI name matches.')
            match_id=previous.get('canonical_id') or r.get('resolved_entity_id') or ''
            default_decision=previous.get('decision') or ('match_existing' if match_id else 'create_new')
            decision=st.radio('Identity decision',['match_existing','create_new'],
                index=0 if default_decision=='match_existing' else 1,horizontal=True,key=f'v10_decision_{sid}')
            canonical_id=st.text_input('Verified canonical ID',value=match_id,key=f'v10_match_{sid}') if decision=='match_existing' else None
            if decision=='create_new' and r.get('resolution_status') in ('UNRESOLVED','AMBIGUOUS'):
                st.warning('Explicit NEW decision on unresolved record: verify authoritative sources and inspect existing names first.')
            source_verified=st.checkbox('I verified identity, provenance and sources',value=previous.get('source_verified',False),key=f'v10_source_{sid}')
            event_checked=(st.checkbox('I checked for duplicate events, date and asset identities',
               value=previous.get('event_duplicate_checked',False),key=f'v10_duplicate_{sid}')
               if r['target_table']=='pc_events' else False)
            content_reviewed=st.checkbox('I reviewed the descriptive / analytical text and news links',
                value=previous.get('content_reviewed',False),key=f'v10_text_{sid}')
            client_visible=st.checkbox('Make reviewed narrative visible in Trade (subject to app authorization)',
                value=previous.get('client_visible',False),key=f'v10_visible_{sid}',disabled=not content_reviewed)
            prepared.append((r,decision,canonical_id,source_verified,event_checked,content_reviewed,client_visible))
    col1,col2=st.columns(2)
    with col1:
        if st.button('Save explicit approvals',key='v10_save',type='secondary'):
            try:
                batch=[make_approval(*args,reviewer) for args in prepared]
                sb.table('pc_v10_approvals').upsert(batch,on_conflict='staged_record_id').execute()
                st.success(f'Saved {len(batch)} approvals. No canonical records changed.')
            except Exception as exc:st.error(f'Approval failed: {exc}')
    with col2:
        if st.button('Back up selected staged records (no publish)',key='v10_backup'):
            try:
                if not reviewer.strip():raise ValueError('Reviewer name required')
                result=sb.rpc('pc_v10_backup_staged',{'p_job':job,'p_stage_ids':[r['staged_record_id'] for r in choices],
                    'p_reviewer':reviewer.strip()}).execute().data
                st.success(f'Immutable database backup saved: {result}. Nothing published.')
            except Exception as exc:st.error(f'Backup failed: {exc}')
    st.divider()
    confirm=st.checkbox('I understand this will INSERT genuinely new canonical records or MATCH existing IDs. '
       'Staging remains intact; unsupported links remain in review.',key='v10_confirm')
    if st.button('Move approved staged → Trade (BACKUP FIRST)',disabled=not confirm or not reviewer.strip(),type='primary',key='v10_move'):
        try:
            chosen=[r['staged_record_id'] for r in choices]
            current=(sb.table('pc_v10_approvals').select('*').in_('staged_record_id',chosen).execute().data or [])
            valid={a['staged_record_id'] for a in current if a.get('approved_by')==reviewer.strip() and a.get('source_verified')}
            if set(chosen)!=valid:raise ValueError('Save verified approvals for each selected record first')
            snapshot=sb.rpc('pc_v10_backup_staged',{'p_job':job,'p_stage_ids':chosen,
                'p_reviewer':reviewer.strip()}).execute().data
            st.info(f'Immutable pre-publication backup saved: {snapshot}')
            # Separate transaction: even if publication fails, the backup exists.
            result=sb.rpc('pc_v10_publish_approved',{'p_job':job,'p_stage_ids':chosen,
                'p_backup':snapshot,'p_reviewer':reviewer.strip()}).execute().data
            st.success(f"Moved {result['published']} records: {result['inserted']} new, {result['matched']} matched. "
                f"Publication {result['publication_id']}. Original staging retained.")
        except Exception as exc:
            st.error(f'Publication did NOT complete: {exc}. Check backups and publication log before retrying.')
    with st.expander('Recent backups and publication log'):
        backups=(sb.table('pc_v10_stage_backups').select('backup_id,record_count,backed_up_by,created_at')
          .eq('ingestion_job_id',job).order('created_at',desc=True).limit(20).execute().data or [])
        st.dataframe(backups,hide_index=True,use_container_width=True)
        if backups:
            pick_backup=st.selectbox('Download immutable backup snapshot',backups,
                format_func=lambda x:f"{x['created_at']} — {x['record_count']} records — {x['backup_id'][:8]}",
                key='v10_backup_pick')
            if st.button('Load backup JSON for download',key='v10_backup_load'):
                backup_detail=(sb.table('pc_v10_stage_backups').select('backup_id,snapshot,snapshot_md5')
                    .eq('backup_id',pick_backup['backup_id']).limit(1).execute().data or [])
                if backup_detail:
                    st.download_button('Download complete immutable backup JSON',
                        json.dumps(backup_detail[0],ensure_ascii=False,indent=2,default=str),
                        f"pc_immutable_backup_{pick_backup['backup_id']}.json",'application/json',
                        key='v10_full_snapshot_download')
        pubs=(sb.table('pc_v10_publications').select('publication_id,backup_id,item_count,published_by,published_at')
          .eq('ingestion_job_id',job).order('published_at',desc=True).limit(20).execute().data or [])
        st.dataframe(pubs,hide_index=True,use_container_width=True)
