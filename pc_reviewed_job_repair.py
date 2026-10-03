"""Reviewable, job-scoped repairs of saved proposals; no AI or new job."""
import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def export_job(sb, job):
    from pc_v15_bulk_replay import _all_staged, _published, _canon_registry
    stages = _all_staged(sb, job)
    return {'job_id': job, 'stages': stages,
            'publications': list(_published(sb, [r['staged_record_id'] for r in stages]).values()),
            'registry': _canon_registry(sb, {'pc_entities', 'pc_assets', 'pc_mobile_assets', 'pc_events'})}


def preview_repair(sb, job, repair):
    from pc_v15_bulk_replay import _all_staged, _published, ID_TABLES, _validation_issue, _type_conflict, _norm
    if repair.get('job_id') != job or not repair.get('reason'):
        raise ValueError('Repair must identify this job and give its evidence-based reason')
    stages = {str(r['staged_record_id']): r for r in _all_staged(sb, job)}
    pubs = _published(sb, list(stages))
    items = repair.get('items') or []
    if not items or len(items) > 200 or len({str(i['staged_record_id']) for i in items}) != len(items):
        raise ValueError('Select 1–200 distinct saved stages')
    checked = []
    for item in items:
        sid = str(item['staged_record_id']); old = stages.get(sid)
        if not old or old['target_table'] not in ID_TABLES:
            raise ValueError('Stage is absent or unsupported: ' + sid)
        after = deepcopy(old); after['payload'] = item.get('payload', old['payload'])
        after['natural_key'] = item.get('natural_key', old['natural_key'])
        before_hash = fingerprint({'payload': old['payload'], 'natural_key': old['natural_key']})
        after_hash = fingerprint({'payload': after['payload'], 'natural_key': after['natural_key']})
        if before_hash not in (item.get('expected_fingerprint'), after_hash):
            raise ValueError('Saved stage changed since export: ' + sid)
        if _validation_issue(after):
            raise ValueError(_validation_issue(after))
        evidence = item.get('evidence_urls') or []
        if not evidence or not all(str(u).startswith('https://') for u in evidence):
            raise ValueError('Each repair needs cited HTTPS evidence')
        decision = item.get('decision'); cid = item.get('canonical_id')
        canonical = None
        if decision == 'match_existing':
            table = old['target_table']; pk = ID_TABLES[table]
            hits = sb.table(table).select('*').eq(pk, cid).limit(2).execute().data or []
            if len(hits) != 1: raise ValueError('Selected canonical record is absent or ambiguous')
            hit = hits[0]; typecol = {'pc_entities':'entity_type','pc_assets':'asset_type'}.get(table)
            country = {'pc_entities':'hq_country','pc_assets':'country'}.get(table)
            p = after['payload']
            if typecol and _type_conflict(table, p.get(typecol), hit.get(typecol)):
                raise ValueError('Canonical type conflicts with reviewed proposal')
            if country and p.get(country) and hit.get(country) and _norm(p[country]) != _norm(hit[country]):
                raise ValueError('Canonical country conflicts with reviewed proposal')
            if table == 'pc_mobile_assets' and p.get('imo') and hit.get('imo') and str(p['imo']) != str(hit['imo']):
                raise ValueError('Canonical IMO conflicts with reviewed proposal')
        elif decision not in (None, 'create_new'):
            raise ValueError('Unsupported identity decision')
        if sid in pubs and (decision or item.get('repair_published_event')):
            if decision: raise ValueError('Published identities cannot be rebound')
            if old['target_table'] != 'pc_events': raise ValueError('Only published event text repair is supported')
            cid = pubs[sid]['canonical_id']
            hits = sb.table('pc_events').select('*').eq('event_id', cid).limit(2).execute().data or []
            if len(hits) != 1: raise ValueError('Published event is absent')
            canonical = hits[0]
            from pc_source_graph import event_day
            if event_day(canonical.get('start_date')) != event_day(after['payload'].get('start_date')):
                raise ValueError('Published event date differs; identity review required')
        checked.append({'item':item, 'before':old, 'after':after, 'canonical_before':canonical,
                        'canonical_id':cid, 'after_fingerprint':after_hash})
    return checked


def apply_repair(sb, job, repair, reviewer):
    from pc_connected_research import _load_scope, _save_scope
    if not reviewer.strip(): raise ValueError('Reviewer required')
    checked = preview_repair(sb, job, repair)
    ids = [c['before']['staged_record_id'] for c in checked]
    backup = sb.rpc('pc_v10_backup_staged', {'p_job':job,'p_stage_ids':ids,'p_reviewer':reviewer}).execute().data
    scope = _load_scope(sb, job)
    journal = {'repair_hash':fingerprint(repair),'reason':repair['reason'],'reviewer':reviewer,
               'reviewed_at':datetime.now(timezone.utc).isoformat(),'backup_id':backup,
               'before':checked,'status':'applying'}
    scope.setdefault('reviewed_repair_journal', []).append(journal)
    _save_scope(sb, job, scope)  # Preserve canonical and staged originals before any write.
    for c in checked:
        sid = c['before']['staged_record_id']; item = c['item']; after = c['after']
        sb.table('pc_staged_records').update({'payload':after['payload'],'natural_key':after['natural_key']}).eq('ingestion_job_id',job).eq('staged_record_id',sid).execute()
        if item.get('decision'):
            scope.setdefault('reviewed_identity_decisions', {})[str(sid)] = {
                'decision':item['decision'],'canonical_id':item.get('canonical_id'),
                'fingerprint':c['after_fingerprint'],'evidence_urls':item['evidence_urls'],
                'reviewer':reviewer,'reason':item.get('reason') or repair['reason']}
        if c['canonical_before']:
            p = after['payload']
            changes = {k:p[k] for k in ('title','description','event_type') if k in p}
            sb.table('pc_events').update(changes).eq('event_id',c['canonical_id']).execute()
            sb.table('pc_v10_published_content').update({k:v for k,v in changes.items() if k in ('title','description')}).eq('staged_record_id',sid).execute()
    journal['status'] = 'applied'
    _save_scope(sb, job, scope)
    return {'job_id':job,'repaired_stages':len(checked),'backup_id':backup}


def render_job_repair(sb, job, reviewer):
    import streamlit as st
    with st.expander('Review saved-job identity and event repairs'):
        st.caption('Export saved proposals and current canonical identities; review a cited repair file, then apply it to this same job. Original staging is backed up and event originals are journalled. No AI calls.')
        export_button_key='repair_export_button_'+job
        export_state_key='repair_export_data_'+job
        if st.button('Prepare saved-job export', key=export_button_key):
            st.session_state[export_state_key] = export_job(sb, job)
        export = st.session_state.get(export_state_key)
        if export:
            st.download_button('Download saved-job records and identities', json.dumps(export, ensure_ascii=False, indent=2, default=str), 'saved_job_'+job+'.json', 'application/json')
        uploaded = st.file_uploader('Reviewed saved-job repair JSON', type=['json'], key='repair_upload_'+job)
        if uploaded:
            try:
                repair = json.loads(uploaded.getvalue())
                checked = preview_repair(sb, job, repair)
                st.dataframe([{'Table':c['before']['target_table'],'Before':c['before']['natural_key'],
                               'After':c['after']['natural_key'],'Decision':c['item'].get('decision') or 'correct source text',
                               'Canonical ID':c['canonical_id'],'Reason':c['item'].get('reason') or repair['reason']} for c in checked])
                st.write(repair['reason'])
                if st.button('Apply reviewed repair to saved job', key='repair_apply_'+job):
                    st.success(str(apply_repair(sb, job, repair, reviewer)))
                    st.session_state.pop('v15_plan', None)
            except Exception as exc: st.error('Repair held: '+str(exc))
