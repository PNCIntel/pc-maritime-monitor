"""P&C v1.9 - one-action intelligence population pipeline.

This module closes the gap between Universal Intake and the canonical shared
Trade/Intelligence database. The operator approves one load; the app processes
its queue, researches only unresolved staged objects, repairs staging, resolves
canonical identities, publishes eligible records with existing backup-first
RPCs, then syncs graph links and agreements. Exceptions remain staged.
"""
from __future__ import annotations
import os
import streamlit as st


def _queue_counts(sb, job):
    out={}
    for status in ('queued','processing','staged','failed'):
        q=(sb.table('pc_v07_queue').select('queue_id',count='exact',head=True)
           .eq('ingestion_job_id',job).eq('status',status).execute())
        out[status]=q.count or 0
    return out


def _candidate_unresolved(staged, ready, followers, pub):
    done=set(pub)
    done.update(str(r['staged_record_id']) for r,_,_ in ready)
    done.update(str(r['staged_record_id']) for r,_ in followers)
    return [r for r in staged if r.get('target_table') in {'pc_entities','pc_assets','pc_mobile_assets','pc_events'}
            and str(r['staged_record_id']) not in done]


def render_intelligence_pipeline(sb, job, reviewer='DCM'):
    from pc_v15_bulk_replay import (_process_job_queue,_all_staged,_plan,_publish_ready,
        _canon_registry,_identity_candidates)
    from pc_v16_research import (enqueue_research,status_counts,process_research_batch,
        recover_incomplete_research,recover_saved_repair_holds,recover_unchanged_holds,
        link_researched_events)

    st.divider()
    st.subheader('Populate shared P&C database')
    st.caption('One approval: process → research unresolved records → repair → canonical resolve → '
               'backup + publish eligible records → sync relationships and assessments. '
               'Only genuine evidence/identity conflicts remain as exceptions.')

    counts=_queue_counts(sb,job)
    c1,c2,c3,c4=st.columns(4)
    c1.metric('Queued',counts['queued']); c2.metric('Staged',counts['staged'])
    c3.metric('Failed',counts['failed']); c4.metric('Job',str(job)[:8])

    run_key='pc_v19_run_'+str(job)
    state_key='pc_v19_state_'+str(job)
    report_key='pc_v19_report_'+str(job)

    if not st.session_state.get(run_key):
        if st.button('Research, resolve & POPULATE DATABASE',type='primary',use_container_width=True,
                     key='pc_v19_start_'+str(job)):
            st.session_state[run_key]=True
            st.session_state[state_key]='queue'
            st.session_state.pop(report_key,None)
            st.rerun()
        return

    stage=st.session_state.get(state_key,'queue')
    st.info('Automatic load is running. Completed work is persisted in Supabase; a restart can resume the same job.')

    try:
        if stage=='queue':
            if counts['queued']:
                with st.spinner('Processing queued records into durable staging...'):
                    _process_job_queue(sb,job,batch=50,max_batches=40)
                st.rerun()
            if counts['processing']:
                st.warning('Some queue rows are still marked processing. Wait briefly or use Jobs & history recovery.')
                return
            if counts['failed']:
                st.warning(f"{counts['failed']} queue rows failed and will remain exceptions; continuing with staged records.")
            st.session_state[state_key]='plan'
            st.rerun()

        if stage=='plan':
            staged=_all_staged(sb,job)
            if not staged:
                raise RuntimeError('No staged records exist for this job')
            ready,followers,exceptions,pub=_plan(sb,job,staged)
            unresolved=_candidate_unresolved(staged,ready,followers,pub)
            if unresolved:
                registry=_canon_registry(sb,{'pc_entities','pc_assets','pc_mobile_assets'})
                enqueue_research(sb,job,unresolved,registry,all_records=True)
                st.session_state[state_key]='research'
                st.rerun()
            st.session_state[state_key]='publish'
            st.rerun()

        if stage=='research':
            rs=status_counts(sb,job)
            r1,r2,r3,r4=st.columns(4)
            r1.metric('AI pending',rs['pending']);r2.metric('Repaired',rs['applied'])
            r3.metric('Evidence holds',rs['held']);r4.metric('Failed',rs['failed'])
            if rs['running']:
                recover_incomplete_research(sb,job)
                rs=status_counts(sb,job)
            if rs['pending']:
                api_key=(st.secrets.get('OPENAI_API_KEY') or st.secrets.get('OPENAI_KEY')
                         or os.environ.get('OPENAI_API_KEY'))
                if not api_key: raise RuntimeError('OPENAI_API_KEY is not configured')
                with st.spinner('AI is researching unresolved identities, classifications and missing facts...'):
                    registry=_canon_registry(sb,{'pc_entities','pc_assets','pc_mobile_assets'})
                    process_research_batch(sb,job,api_key,registry,batch_size=5)
                st.rerun()
            # Reuse already-paid findings before accepting holds.
            recover_saved_repair_holds(sb,job)
            recover_unchanged_holds(sb,job)
            st.session_state[state_key]='publish'
            st.rerun()

        if stage=='publish':
            staged=_all_staged(sb,job)
            ready,followers,exceptions,pub=_plan(sb,job,staged)
            with st.spinner(f'Publishing {len(ready)+len(followers)} eligible records with immutable backups...'):
                results,follow_count,failures=_publish_ready(sb,job,ready,followers,reviewer or 'DCM') if ready else ([],0,[])
                graph=sb.rpc('pc_v12_sync_published_links',{'p_job':job}).execute().data
                agreements={}
                try:
                    from pc_v14_agreement_sync import sync_published_job
                    agreements=sync_published_job(sb,job,limit=1000,reviewer=reviewer or 'DCM')
                except Exception as exc:
                    agreements={'warning':str(exc)}
                registry=_canon_registry(sb,{'pc_entities','pc_assets','pc_mobile_assets'})
                researched_links=link_researched_events(sb,job,registry,_identity_candidates)
            # Re-plan after publication to report true remaining holds.
            staged2=_all_staged(sb,job)
            ready2,followers2,exceptions2,pub2=_plan(sb,job,staged2)
            report={
                'job_id':job,
                'published_items_now':len(ready)+follow_count-len(failures),
                'publication_failures':failures,
                'remaining_exceptions':exceptions2,
                'remaining_exception_count':len(exceptions2),
                'published_stage_count':len(pub2),
                'graph_sync':graph,
                'researched_relationships':researched_links,
                'agreements':agreements,
                'assessment_note':'Event assessment sidecars already stored in pc_v08_trade_content / v1.6 sidecars are retained and published with their developments.'
            }
            st.session_state[report_key]=report
            st.session_state[state_key]='done'
            st.rerun()

        if stage=='done':
            report=st.session_state.get(report_key,{})
            st.success('Database population pass complete. Trade and Intelligence read the same canonical database.')
            a,b,c=st.columns(3)
            a.metric('Published stages',report.get('published_stage_count',0))
            b.metric('Remaining exceptions',report.get('remaining_exception_count',0))
            c.metric('Publication failures',len(report.get('publication_failures') or []))
            if report.get('remaining_exceptions'):
                with st.expander('Only remaining exceptions',expanded=False):
                    import pandas as pd
                    st.dataframe(pd.DataFrame(report['remaining_exceptions']),hide_index=True,use_container_width=True)
            with st.expander('Population report'):
                st.json(report,expanded=False)
            if st.button('Run reconciliation again after resolving exceptions',key='pc_v19_again_'+str(job)):
                st.session_state[state_key]='plan';st.rerun()
    except Exception as exc:
        st.error('Automatic population stopped safely: '+str(exc))
        st.caption('The job and completed work remain persisted. Fix the reported issue and click Resume.')
        if st.button('Resume this load',key='pc_v19_resume_'+str(job)):
            st.rerun()
