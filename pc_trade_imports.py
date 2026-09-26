"""Staff-only, read-only view of previously ingested Trade intelligence.

This module deliberately DOES NOT publish, approve or expose draft tables to clients.
Call render_imported_intelligence() from Trade. Authentication is enforced HERE,
even if the host Trade app has PC_REQUIRE_AUTH=false during migration.
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

import streamlit as st


@st.cache_data(ttl=45, show_spinner=False)
def _fetch_jobs(_sb):
    return (_sb.table('pc_ingestion_jobs')
            .select('ingestion_job_id,title,status,created_at')
            .order('created_at', desc=True).limit(75).execute().data or [])


def _count(sb, table, job_id=None):
    query = sb.table(table).select('*', count='exact', head=True)
    if job_id:
        query = query.eq('ingestion_job_id', job_id)
    resp = query.execute()
    return resp.count if resp.count is not None else 0


def _rows(sb, table, job, columns, page, size=30, *, order='content_id', search=None):
    q = sb.table(table).select(columns).eq('ingestion_job_id', job)
    if search:
        # Search title only; source investigation is available in the full record.
        term = re.sub(r'[%_,()]', ' ', str(search)).strip()[:100]
        if term:
            q = q.ilike('title', '%' + term + '%')
    return (q.order(order, desc=True).range((page-1)*size, page*size-1)
            .execute().data or [])


def _s(value):
    if value is None:
        return ''
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _items(value):
    if not value:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value]
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
            if isinstance(decoded, list):
                return decoded
            if isinstance(decoded, dict):
                return [decoded]
        except (ValueError, TypeError):
            pass
        return [part.strip(' •-') for part in value.split('\n') if part.strip(' •-')]
    return []


def _text_section(title, value):
    text = _s(value)
    if text and text.casefold() not in ('not assessed', 'none', 'null', '[]', '{}'):
        st.markdown('#### ' + title)
        st.write(text)


def _bullets(title, value):
    values = _items(value)
    if not values:
        return
    st.markdown('#### ' + title)
    for item in values:
        if isinstance(item, dict):
            text = (item.get('indicator') or item.get('text') or
                    item.get('description') or item.get('question') or _s(item))
        else:
            text = str(item)
        if text.strip():
            st.markdown('- ' + text.strip())


def _safe_url(url):
    url = str(url or '').strip()
    parts = urlsplit(url)
    return url if parts.scheme in ('https', 'http') and parts.netloc else None


def _render_sources(sb, rec, job):
    news = (sb.table('pc_v08_news_items')
            .select('source_url,publisher,headline,published_at,source_role')
            .eq('ingestion_job_id', job)
            .eq('source_record_key', rec['source_record_key'])
            .limit(70).execute().data or [])
    seen = set()
    st.markdown('#### Original articles and evidence')
    for item in news:
        url = _safe_url(item.get('source_url'))
        if not url or url in seen:
            continue
        seen.add(url)
        label = item.get('headline') or item.get('publisher') or urlsplit(url).netloc
        st.markdown('- [' + str(label).replace(']', '') + '](' + url + ')')
        st.caption(' · '.join(str(v) for v in
                            [item.get('publisher'), item.get('published_at'), item.get('source_role')] if v))
    for item in _items(rec.get('source_evidence')):
        url = _safe_url(item.get('url') if isinstance(item, dict) else item)
        if url and url not in seen:
            seen.add(url)
            st.markdown('- [' + urlsplit(url).netloc + '](' + url + ')')
    if not seen:
        st.warning('No source URL connected to this narrative. Keep it in editorial review.')
    return len(seen)


def render_imported_intelligence():
    """Staff-only visualisation. Do not reuse the service client for a client page."""
    shared = Path(__file__).resolve().parent / 'shared'
    if str(shared) not in sys.path:
        sys.path.insert(0, str(shared))
    from pc_auth import require_super_admin, service_client
    require_super_admin()  # Always enforce, regardless of host app's PC_REQUIRE_AUTH.
    sb = service_client()
    if sb is None:
        st.error('Service-role connection unavailable; configure Streamlit server secrets.')
        return
    st.header('Imported Trade intelligence')
    st.caption('STAFF PREVIEW · Already stored in Supabase · No re-import and no canonical publication')
    if st.button('Refresh imported records', key='pc_imports_refresh'):
        _fetch_jobs.clear()
        st.rerun()
    try:
        jobs = _fetch_jobs(sb)
    except Exception as exc:
        st.error('Could not read ingestion jobs: ' + str(exc))
        return
    if not jobs:
        st.info('No saved ingestion jobs are accessible.')
        return
    opts = [j['ingestion_job_id'] for j in jobs]
    # Prefer the finished September pilot when present, not merely the most recent older job.
    preferred = next((i for i, val in enumerate(opts)
                      if val == '8b1ce7e5-cd67-4be8-af3d-95dd788739d9'), 0)
    selected_job = st.selectbox('Research batch', opts, index=preferred,
                               format_func=lambda v: next((str(j['title']) + ' · ' + str(j['status'])
                                                           for j in jobs if j['ingestion_job_id'] == v), v),
                               key='pc_imports_job')
    try:
        metrics = [(label, _count(sb, table, selected_job)) for label, table in (
            ('Staged proposals', 'pc_staged_records'),
            ('Narratives', 'pc_v08_trade_content'),
            ('News observations', 'pc_v08_news_items'),
            ('Event assessments', 'pc_v07_event_assessments'))]
    except Exception as exc:
        st.error('Ingestion tables unavailable: ' + str(exc))
        return
    a,b,c,d = st.columns(4)
    for col, (label, value) in zip((a,b,c,d), metrics):
        col.metric(label, value)
    st.info('These are saved editorial records. Unapproved identities, event links and corridors remain in review; this screen never changes canonical tables.')
    tab_dev, tab_other, tab_audit = st.tabs(['Developments and analysis', 'Companies and assets', 'Review status'])
    with tab_dev:
        _render_narratives(sb, selected_job, domain='pc_events', prefix='event')
    with tab_other:
        _render_narratives(sb, selected_job, domain=None, prefix='other')
    with tab_audit:
        st.subheader('What has and has not been published')
        st.caption('The staging status does not prove a successful canonical move.')
        try:
            rows = (sb.table('pc_staged_records')
                    .select('target_table,natural_key,resolution_status,review_status,validation_status')
                    .eq('ingestion_job_id',selected_job).limit(100).execute().data or [])
            if rows:
                import pandas as pd
                st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
            else:
                st.info('No staging proposals found for this job.')
        except Exception as exc:
            st.warning('Staging review unavailable: ' + str(exc))


def _render_narratives(sb, job, domain, prefix):
    kinds = {'All': None, 'Companies': 'pc_entities', 'Infrastructure': 'pc_assets',
             'Vessels': 'pc_mobile_assets', 'Corridors': 'pc_trade_corridors',
             'Routes': 'pc_transport_routes', 'Services': 'pc_transport_services'}
    if domain:
        table_filter = domain
        st.subheader('Developments already extracted')
    else:
        label = st.selectbox('Record type', list(kinds), key=f'pc_imports_type_{prefix}')
        table_filter = kinds[label]
    keyword = st.text_input('Search headings', key=f'pc_imports_search_{prefix}')
    page = st.number_input('Page', min_value=1, value=1, step=1, key=f'pc_imports_page_{prefix}')
    columns = ('content_id,ingestion_job_id,source_record_key,target_table,target_key,canonical_id,'
               'title,description,what_it_means,operational_impact,commercial_implications,'
               'pc_assessment,monitoring_indicators,research_gaps,source_evidence,text_origin,editorial_status')
    try:
        q = sb.table('pc_v08_trade_content').select(columns).eq('ingestion_job_id',job)
        if table_filter:
            q=q.eq('target_table',table_filter)
        elif not domain:
            q=q.neq('target_table','pc_events')
        if keyword.strip():
            term=re.sub(r'[%_,()]', ' ', keyword).strip()[:100]
            if term:
                q=q.ilike('title','%'+term+'%')
        records=(q.order('content_id',desc=True).range((page-1)*25,page*25-1).execute().data or [])
    except Exception as exc:
        st.error('Cannot read saved narratives: ' + str(exc))
        return
    if not records:
        st.info('No records on this page. Try page 1 or a different category.')
        return
    selected=st.selectbox('Inspect full record', list(range(len(records))),
                          format_func=lambda idx: records[idx].get('title') or records[idx].get('target_key') or 'Untitled',
                          key=f'pc_imports_select_{prefix}')
    rec=records[selected]
    st.markdown('### ' + str(rec.get('title') or 'Untitled development'))
    label=(rec.get('editorial_status') or 'draft').upper()
    st.caption(' · '.join([label, rec.get('target_table') or '',
                          'Linked to canonical ID' if rec.get('canonical_id') else 'Canonical linkage pending']))
    _text_section('What happened / description', rec.get('description'))
    _text_section('Why it matters',rec.get('what_it_means'))
    _text_section('Operational impact',rec.get('operational_impact'))
    _text_section('Commercial implications',rec.get('commercial_implications'))
    _text_section('P&C assessment',rec.get('pc_assessment'))
    _bullets('Monitoring indicators',rec.get('monitoring_indicators'))
    _bullets('Research gaps',rec.get('research_gaps'))
    try:
        _render_sources(sb,rec,job)
    except Exception as exc:
        st.warning('Sources could not be loaded: '+str(exc))
    if not any([rec.get('what_it_means'),rec.get('operational_impact'),rec.get('commercial_implications')]):
        st.warning('Analytical content incomplete; review before canonical publication.')
    if rec.get('canonical_id') and rec.get('target_table')=='pc_entities':
        if st.button('Open canonical company page',key='pc_imports_company_link_'+prefix):
            st.session_state['company_pick_id']=rec['canonical_id']
            st.session_state['nav_request']='Companies'
            st.rerun()
