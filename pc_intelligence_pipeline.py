"""P&C v2.0 connected analyst loader pipeline.

Analyst workflow: queue source package -> one research/populate action -> review only
connected findings/true exceptions -> approve connected enrichment. No SQL/IDs in UI.
"""
from __future__ import annotations
import os, json, hashlib
import streamlit as st


def _queue_counts(sb, job):
    out={}
    for status in ('queued','processing','staged','failed'):
        q=(sb.table('pc_v07_queue').select('queue_id',count='exact',head=True)
           .eq('ingestion_job_id',job).eq('status',status).execute())
        out[status]=q.count or 0
    return out


def _candidate_research(staged, pub):
    """Research every unpublished core proposal, not just unresolved identities.

    Existing companies/vessels still need enrichment. This closes the Svitzer failure
    where a matched company skipped research and only shallow source extraction survived.
    """
    from pc_source_graph import is_dossier
    done=set(map(str,pub or []))
    return [r for r in staged if r.get('target_table') in {'pc_entities','pc_assets','pc_mobile_assets','pc_events'}
            and str(r.get('staged_record_id')) not in done and not is_dossier(r)]


def source_publication_report(staged,published,exceptions,failures,intake_report=None):
    """Per-input outcomes remain visible even when canonical proposals merge."""
    from pc_source_graph import source_key
    output={}; published_ids={str(x) for x in published}
    for row in staged:
        m=(row.get('payload') or {}).get('metadata') or {}
        views=m.get('source_proposals') or [row]
        sources={}
        for v in views:
            vm=(v.get('payload') or {}).get('metadata') or {}
            key=vm.get('intake_source_key') or m.get('intake_source_key') or 'legacy'
            sources[key]=vm.get('intake_source_url') or vm.get('source_label') or key
        for obs in m.get('source_observations') or []:
            if obs.get('source_key'): sources.setdefault(obs['source_key'],obs.get('source_url') or obs['source_key'])
        for key,label in sources.items():
            own=output.setdefault(key,{'source':label,'staged':0,'published':0,'held':0,'failures':0})
            own['staged']+=1
            if str(row['staged_record_id']) in published_ids: own['published']+=1
            elif any(x.get('Staged record ID')==row['staged_record_id'] or
                     (x.get('Table')==row['target_table'] and x.get('Name')==row['natural_key']) for x in exceptions): own['held']+=1
            if any(x.get('Staged record ID')==row['staged_record_id'] for x in failures): own['failures']+=1
    for err in (intake_report or {}).get('errors') or []:
        label=err.get('source') or 'unknown source'; key=source_key(label) if str(label).startswith('http') else source_key('',label)
        own=output.setdefault(key,{'source':label,'staged':0,'published':0,'held':0,'failures':0})
        own.setdefault('intake_errors',[]).append(err)
    return list(output.values())


def _api_key():
    return (st.secrets.get('OPENAI_API_KEY') or st.secrets.get('OPENAI_KEY') or os.environ.get('OPENAI_API_KEY'))


def _release_saved_dossier_tasks(sb, job):
    """Release redundant pending research tasks for already-curated dossier rows.

    No canonical or staged records are changed. Normal planner validation,
    duplicate checks and reviewed identity decisions still apply.
    """
    tasks=(sb.table('pc_v16_research_tasks').select('task_id,staged_record_id')
           .eq('ingestion_job_id',job).eq('status','pending').limit(5000).execute().data or [])
    released=0
    for task in tasks:
        rows=(sb.table('pc_staged_records').select('payload')
              .eq('staged_record_id',task['staged_record_id']).limit(1).execute().data or [])
        if len(rows)!=1:
            continue
        payload=rows[0].get('payload') or {}; meta=payload.get('metadata') or {}
        mode=str(meta.get('ingestion_mode') or '')
        dossier=str(meta.get('dossier_version') or '')
        urls=meta.get('research_sources') or []
        if not (mode.startswith('AI_RESEARCH_DOSSIER') or meta.get('validated_dossier_replay')):
            continue
        if not dossier and not meta.get('validated_dossier_replay'):
            continue
        if not urls:
            continue
        changed=(sb.table('pc_v16_research_tasks').update({
            'status':'applied',
            'result':{'status':'saved_dossier_reused',
                      'reason':'Persisted curated dossier evidence reused; canonical validation still applies.',
                      'replayed_from_saved_dossier':True},
            'error_text':None
        }).eq('task_id',task['task_id']).eq('status','pending').execute().data or [])
        if changed:
            released+=1
    return released


def render_intelligence_pipeline(sb, job, reviewer='DCM'):
    from pc_v15_bulk_replay import (_process_job_queue,_all_staged,_plan,_publish_ready,
        _canon_registry,_identity_candidates,_identity_indexes)
    from pc_v16_research import (enqueue_research,status_counts,process_research_batch,
        recover_incomplete_research,recover_saved_repair_holds,recover_unchanged_holds,
        link_researched_events)
    from pc_connected_research import init_job_connected, process_next_job_subject, publish_job_connected

    st.divider()
    st.subheader('Research, resolve & publish')
    st.caption('Production loader v4.0 · straight-through publication with exception holds')
    st.caption('Source research → classification repair → canonical resolution → core publication → '
               'connected company/vessel research → specialist tables. Analysts review names and evidence, not database IDs.')

    counts=_queue_counts(sb,job)
    stages_for_count = _all_staged(sb, job)
    source_ids = set()
    for r in stages_for_count:
        m = (r.get('payload') or {}).get('metadata') or {}
        if m.get('intake_source_key'): source_ids.add(m['intake_source_key'])
        for obs in m.get('source_observations') or []:
            if obs.get('source_key'): source_ids.add(obs['source_key'])
    c1,c2,c3,c4,c5=st.columns(5)
    c1.metric('Intake sources',len(source_ids) if source_ids else 'legacy / unknown')
    c2.metric('Queued objects',counts['queued'])
    c3.metric('Staged objects',len(stages_for_count))
    c4.metric('Failed queue rows',counts['failed']); c5.metric('Job',str(job)[:8])
    st.caption(f"Processed queue rows: {counts['staged']}. Research citations do not count as intake sources.")
    if stages_for_count:
        from collections import Counter
        totals=Counter(r.get('target_table') for r in stages_for_count)
        labels={'pc_entities':'Companies / organisations','pc_assets':'Physical assets',
                'pc_mobile_assets':'Mobile assets','pc_events':'Events','pc_event_links':'Event links',
                'pc_relationships':'Relationships'}
        with st.expander('Staged object breakdown'):
            st.dataframe([{'Object type':labels.get(k,k),'Objects':v} for k,v in totals.items()],
                         hide_index=True,use_container_width=True)

    run_key='pc_v20_run_'+str(job); state_key='pc_v20_state_'+str(job); report_key='pc_v20_report_'+str(job)
    # Recover connected-research progress from Postgres after logout/reboot.
    if not st.session_state.get(run_key):
        try:
            from pc_connected_research import _load_scope
            _cs=(_load_scope(sb,job).get('connected_research') or {})
            _status=_cs.get('status')
            if _status in {'researching','review','published','published_partial'}:
                st.session_state[run_key]=True
                st.session_state[state_key]={'researching':'connected_research','review':'connected_review',
                                             'published':'done','published_partial':'done'}[_status]
        except Exception:
            pass
    if not st.session_state.get(run_key):
        if st.button('Research, resolve & POPULATE DATABASE',type='primary',use_container_width=True,key='pc_v20_start_'+str(job)):
            st.session_state[run_key]=True; st.session_state[state_key]='queue'; st.session_state.pop(report_key,None); st.rerun()
        return

    stage=st.session_state.get(state_key,'queue')
    st.info('Work is persisted in Supabase. If Streamlit restarts, reopen this job and resume.')

    try:
        if stage=='queue':
            if counts['queued']:
                with st.spinner('Processing queued records into durable staging...'):
                    _process_job_queue(sb,job,batch=50,max_batches=40)
                st.rerun()
            if counts['processing']:
                st.warning('Some queue rows are still marked processing. Wait briefly or use Jobs & history recovery.'); return
            if counts['failed']:
                st.warning(f"{counts['failed']} queue rows failed and remain exceptions; continuing with staged records.")
            st.session_state[state_key]='plan'; st.rerun()

        if stage=='plan':
            staged=_all_staged(sb,job)
            if not staged: raise RuntimeError('No staged records exist for this job')
            _release_saved_dossier_tasks(sb,job)
            ready,followers,exceptions,pub=_plan(sb,job,staged)
            research_rows=_candidate_research(staged,pub)
            if research_rows:
                registry=_canon_registry(sb,{'pc_entities','pc_assets','pc_mobile_assets'})
                enqueue_research(sb,job,research_rows,registry,all_records=True)
                st.session_state[state_key]='research'; st.rerun()
            st.session_state[state_key]='publish'; st.rerun()

        if stage=='research':
            _release_saved_dossier_tasks(sb,job)
            rs=status_counts(sb,job)
            r1,r2,r3,r4=st.columns(4)
            r1.metric('Research pending',rs['pending']); r2.metric('Repaired',rs['applied'])
            r3.metric('Evidence holds',rs['held']); r4.metric('Failed',rs['failed'])
            if rs['running']:
                recover_incomplete_research(sb,job); rs=status_counts(sb,job)
            if rs['pending']:
                key=_api_key()
                if not key: raise RuntimeError('OPENAI_API_KEY is not configured')
                with st.spinner('Researching identities, classification, relationships and missing facts...'):
                    registry=_canon_registry(sb,{'pc_entities','pc_assets','pc_mobile_assets'})
                    process_research_batch(sb,job,key,registry,batch_size=5)
                st.rerun()
            recover_saved_repair_holds(sb,job); recover_unchanged_holds(sb,job)
            st.session_state[state_key]='publish'; st.rerun()

        if stage=='publish':
            staged=_all_staged(sb,job); ready,followers,exceptions,pub=_plan(sb,job,staged)
            with st.spinner(f'Publishing {len(ready)+len(followers)} eligible core records and graph links...'):
                results,follow_count,failures=_publish_ready(sb,job,ready,followers,reviewer or 'Analyst') if ready else ([],0,[])
                graph=sb.rpc('pc_v12_sync_published_links',{'p_job':job}).execute().data
                agreements={}
                try:
                    from pc_v14_agreement_sync import sync_published_job
                    agreements=sync_published_job(sb,job,limit=1000,reviewer=reviewer or 'Analyst')
                except Exception as exc: agreements={'warning':str(exc)}
                registry=_canon_registry(sb,{'pc_entities','pc_assets','pc_mobile_assets'}); idx=_identity_indexes(registry)
                researched_links=link_researched_events(sb,job,registry,
                    lambda table,name,payload,reg:_identity_candidates(table,name,payload,idx,reg))
            staged2=_all_staged(sb,job); _,_,exceptions2,pub2=_plan(sb,job,staged2)
            try:
                from pc_exception_workbench import sync_plan_exceptions
                queue_exceptions=list(exceptions2)
                for failure in failures or []:
                    if isinstance(failure,dict):
                        queue_exceptions.append({
                            'Table':failure.get('Table') or failure.get('table') or failure.get('target_table'),
                            'Name':failure.get('Name') or failure.get('name') or failure.get('natural_key') or 'Publication failure',
                            'Reason':'Publication failure: '+str(failure.get('Reason') or failure.get('error') or failure),
                            'Staged record ID':failure.get('Staged record ID') or failure.get('staged_record_id'),
                        })
                sync_plan_exceptions(sb,job,queue_exceptions)
            except Exception as exc:
                st.warning('Shared analyst exception queue sync unavailable: '+str(exc))
            report={'job_id':job,'published_items_now':len(ready)+follow_count-len(failures),
                    'publication_failures':failures,'retained_research_holds':[{'name':r['natural_key'],'reason':r.get('retained_research_hold')} for r,_,_ in ready if r.get('identity_only_match')],'remaining_exceptions':exceptions2,
                    'remaining_exception_count':len(exceptions2),'published_stage_count':len(pub2),
                    'graph_sync':graph,'researched_relationships':researched_links,'agreements':agreements}
            st.session_state[report_key]=report
            from pc_connected_research import _load_scope, _save_scope
            saved_scope=_load_scope(sb,job)
            report['source_results']=source_publication_report(staged2,pub2,exceptions2,failures,saved_scope.get('intake_report'))
            saved_scope['loader_publication_report']=report
            _save_scope(sb,job,saved_scope)
            # Connected enrichment starts only after canonical core identities exist.
            state=init_job_connected(sb,job,retry=True)
            if state.get('status')=='review' and state.get('plans'):
                st.session_state[state_key]='connected_publish'
            elif state.get('subjects'):
                st.session_state[state_key]='connected_research'
            else:
                st.session_state[state_key]='done'
            st.rerun()

        if stage=='connected_research':
            key=_api_key()
            if not key: raise RuntimeError('OPENAI_API_KEY is not configured')
            from pc_connected_research import _load_scope
            state=(_load_scope(sb,job).get('connected_research') or {})
            subjects=state.get('subjects') or []; idx=int(state.get('next_index') or 0)
            st.subheader('Connected research')
            st.caption('Researching directly loaded companies and vessels one evidence-backed hop deeper: leadership, offices, subsidiaries, ownership, assets, contracts and vessel histories.')
            st.progress(idx/max(len(subjects),1),text=f'{idx}/{len(subjects)} connected subjects researched')
            if idx < len(subjects):
                with st.spinner('Researching '+subjects[idx]['name']+'...'):
                    process_next_job_subject(sb,job,key)
                st.rerun()
            st.session_state[state_key]='connected_publish'; st.rerun()

        if stage=='connected_publish':
            with st.spinner('Publishing source-backed connected enrichment; ambiguous findings remain held...'):
                creport=publish_job_connected(sb,job)
            rep=st.session_state.get(report_key,{}) or {}
            rep['connected_enrichment']=creport
            st.session_state[report_key]=rep
            st.session_state[state_key]='done'
            st.rerun()

        if stage=='connected_review':
            # Reconcile persisted review plans before displaying or approving them.
            state=init_job_connected(sb,job)
            plans=state.get('plans') or []
            st.subheader('Review connected findings')
            if st.button('Reconcile canonical records from saved staging',key='pc_v20_review_reconcile_'+str(job)):
                st.session_state[state_key]='plan'
                st.session_state.pop(report_key,None)
                st.rerun()
                return
            st.caption('Use reconciliation to retry core publication before approving enrichment. Saved dossier staging is reused.')
            if state.get('replayed_without_ai'):
                st.info('These connected findings were replayed from the validated saved dossier; no additional OpenAI/web research call was made.')
            contexts={p.get('source_context_reference'):p.get('source_context') for p in plans if p.get('source_context')}
            if contexts:
                st.caption('Source context is shared. Subject rows count only findings attached to that subject; vessel history is not repeated as company history.')
                st.dataframe([{'Source dossier':str(key)[:12],
                    'Source events':len(context.get('events') or []),
                    'Source claims':len(context.get('claims') or []),
                    'Source holds':len(context.get('validator_holds') or []),
                    'Source gaps':len(context.get('research_gaps') or [])} for key,context in contexts.items()],
                    hide_index=True,use_container_width=True)
                with st.expander('Shared source context and evidence'):
                    st.json(list(contexts.values()),expanded=False)
            rows=[]
            for p in plans:
                vessel_count=len(p.get('vessels') or []) or (1 if p.get('vessel') else 0)
                rows.append({'Subject':p.get('subject_name'),'Type':p.get('subject_type'),
                    'Vessels':vessel_count,'Name / identity history':len(p.get('identity_history') or []),
                    'Relationships':len(p.get('relationships') or []),'Events':len(p.get('events') or []),
                    'Claims':len(p.get('claims') or []),'Transactions':len(p.get('transactions') or []),
                    'Validator holds':len(p.get('validator_holds') or []),'Research gaps':len(p.get('research_gaps') or []),
                    'Dependent findings held':len(p.get('research_dependent_findings') or []),
                    'Source observations':len(p.get('source_observations') or []),
                    'Conflicting fields':len(p.get('field_conflicts') or [])})
            if rows:
                import pandas as pd
                st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)

            # For replayed dossiers, show the exact connected graph in analyst language before
            # approval. IDs and SQL remain hidden; evidence and uncertainty stay visible.
            if state.get('replayed_without_ai') and plans:
                for i,p in enumerate(plans):
                    st.markdown('#### '+str(p.get('subject_name') or 'Connected subject'))
                    v=p.get('vessel') or {}
                    if v:
                        st.caption('Canonical vessel candidate · IMO '+str(v.get('imo') or 'unverified'))
                    tabs=st.tabs(['Identity history','Relationships','Event & claims','Holds / gaps','Raw dossier'])
                    with tabs[0]:
                        hist=p.get('identity_history') or []
                        st.dataframe(pd.DataFrame(hist),hide_index=True,use_container_width=True) if hist else st.info('No identity-history rows in the validated dossier.')
                    with tabs[1]:
                        rels=p.get('relationships') or []
                        st.dataframe(pd.DataFrame(rels),hide_index=True,use_container_width=True) if rels else st.info('No publishable relationships; ambiguous roles may be held below.')
                    with tabs[2]:
                        ev=p.get('events') or []; cl=p.get('claims') or []
                        if ev:
                            st.markdown('**Verified/neutral event record**')
                            st.dataframe(pd.DataFrame(ev),hide_index=True,use_container_width=True)
                        if cl:
                            st.markdown('**Attributed or unresolved claims — not promoted to event fact**')
                            st.dataframe(pd.DataFrame(cl),hide_index=True,use_container_width=True)
                        if not ev and not cl: st.info('No event or claim rows.')
                    with tabs[3]:
                        holds=(p.get('validator_holds') or []) + (p.get('research_dependent_findings') or []) + (p.get('field_conflicts') or []); gaps=p.get('research_gaps') or []
                        if holds:
                            st.markdown('**Validator holds**')
                            st.dataframe(pd.DataFrame(holds),hide_index=True,use_container_width=True)
                        if gaps:
                            st.markdown('**Research gaps**')
                            st.dataframe(pd.DataFrame({'Research gap':gaps}),hide_index=True,use_container_width=True)
                        if not holds and not gaps: st.success('No validator holds or research gaps.')
                    with tabs[4]:
                        st.json(p,expanded=False)
            else:
                with st.expander('Evidence-backed connected research details'):
                    st.json(plans,expanded=False)
            st.warning('Approval writes only source-backed findings. Ambiguous identities and vessels without verified IMO remain held automatically.')
            review_revision=hashlib.sha256(json.dumps(plans,sort_keys=True,default=str).encode()).hexdigest()[:16]
            approve=st.checkbox('I reviewed the connected findings and approve publication of unambiguous source-backed records',key='pc_v20_connected_approve_'+str(job)+'_'+review_revision)
            if st.button('Approve connected enrichment & finish',type='primary',disabled=not approve,key='pc_v20_connected_publish_'+str(job)):
                with st.spinner('Updating specialist company, vessel, transaction, contract and project tables...'):
                    creport=publish_job_connected(sb,job)
                rep=st.session_state.get(report_key,{}) or {}; rep['connected_enrichment']=creport
                st.session_state[report_key]=rep; st.session_state[state_key]='done'; st.rerun()
            return

        if stage=='done':
            from pc_connected_research import _load_scope
            saved_scope=_load_scope(sb,job)
            report=st.session_state.get(report_key) or saved_scope.get('loader_publication_report') or {}
            if 'connected_enrichment' not in report:
                report['connected_enrichment']=(saved_scope.get('connected_research') or {}).get('publication_report') or {}
            connected=report.get('connected_enrichment') or {}
            holds=(connected.get('holds') if isinstance(connected,dict) else 0) or 0
            if report.get('remaining_exception_count') or report.get('publication_failures') or holds or report.get('retained_research_holds'):
                st.warning('Population pass completed with held items. Published records are available; held identities/evidence remain for analyst review.')
            else:
                st.success('Population pass completed with no reported core or connected holds.')
            a,b,c,d=st.columns(4)
            a.metric('Published stages',report.get('published_stage_count',0))
            b.metric('Core exceptions',report.get('remaining_exception_count',0))
            c.metric('Publication failures',len(report.get('publication_failures') or []))
            d.metric('Connected holds',holds)
            if report.get('source_results'):
                with st.expander('Results by input source',expanded=True):
                    st.dataframe(report['source_results'],hide_index=True,use_container_width=True)
            if report.get('retained_research_holds'):
                with st.expander('Research holds retained after identity-only matching'):
                    st.dataframe(report['retained_research_holds'],hide_index=True,use_container_width=True)
            if report.get('remaining_exceptions'):
                with st.expander('Remaining core exceptions'):
                    import pandas as pd
                    st.dataframe(pd.DataFrame(report['remaining_exceptions']),hide_index=True,use_container_width=True)
            st.download_button(
                'Download complete population report (JSON)',
                data=json.dumps(report,indent=2,ensure_ascii=False,default=str),
                file_name='pc_population_report_'+str(job)+'.json',
                mime='application/json',key='pc_v20_report_download_'+str(job))
            with st.expander('Population report'):
                st.json(report,expanded=False)
            if st.button('Run reconciliation again after resolving exceptions',key='pc_v20_again_'+str(job)):
                st.session_state[state_key]='plan'; st.rerun()

    except Exception as exc:
        st.error('Automatic population stopped safely: '+str(exc))
        st.caption('Completed work remains persisted. Fix the reported issue and click Resume.')
        if st.button('Resume this load',key='pc_v20_resume_'+str(job)): st.rerun()
