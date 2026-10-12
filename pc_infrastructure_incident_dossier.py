"""P&C shared airport/port chronology. Read-only canonical event graph; no inferred impacts."""
import streamlit as st

DIRECT = {'directly_affected', 'targeted'}
CONTEXT = {'nearby', 'exposed', 'operator_asset', 'origin', 'destination', 'route_node', 'other'}

def _classification(e, link):
    meta = e.get('metadata') if isinstance(e.get('metadata'), dict) else {}
    label = str(meta.get('intelligence_subcategory') or meta.get('infrastructure_incident_category') or '').lower()
    typ = str(e.get('event_type') or '').lower()
    specific = str((link.get('metadata') or {}).get('specific_relationship') or '') if isinstance(link.get('metadata'), dict) else ''
    # Prefer structured category/type; headline is fallback for older unclassified records only.
    text = ' '.join((label, typ, specific.lower())) or str(e.get('title') or '').lower()
    # Explicit context/advisory wins over mentions of an attack in advisory headlines.
    if any(t in text for t in ('advisory','travel advice','embassy','fcdo','risk warning')): return 'Advisories'
    if any(t in text for t in ('notam','runway','taxiway','berth restriction','stand limitation','construction','maintenance','closure notice')): return 'Operational restrictions'
    if any(t in text for t in ('cargo disruption','cancellation','booking suspension','service disruption','diversion','port congestion','vessel waiting')): return 'Transport & cargo effects'
    if any(t in text for t in ('missile','drone','attack','strike','explosion','projectile','interception','reported threat')): return 'Attacks & threats'
    return 'Other developments'

def _relation(link):
    r = str(link.get('relation_type') or 'other').lower()
    metadata = link.get('metadata') if isinstance(link.get('metadata'), dict) else {}
    specific = metadata.get('specific_relationship') or metadata.get('relationship_detail')
    if r == 'directly_affected': label = 'Direct operational/incident link — impact detail requires evidence'
    elif r == 'targeted': label = 'Reported target — not necessarily hit'
    elif r == 'nearby': label = 'Nearby — no direct impact implied'
    elif r == 'exposed': label = 'Exposed / operational context — no damage implied'
    else: label = r.replace('_', ' ').capitalize() + ' — relationship, not proof of damage'
    return label, specific

def render_infrastructure_incident_dossier(db, asset_id, asset_name=None, navigate=None):
    if not db or not asset_id: return
    try:
        links = db.table('pc_event_asset_links').select('*').eq('asset_id', asset_id).limit(500).execute().data or []
    except Exception as exc:
        st.warning('Infrastructure graph relationships could not be loaded.'); st.caption(str(exc)); return
    if not links:
        st.info('No event-to-infrastructure links have been recorded for this asset.'); return
    ids = list(dict.fromkeys(str(l.get('event_id')) for l in links if l.get('event_id')))
    events = []
    try:
        for start in range(0, len(ids), 100):
            events += db.table('pc_events').select('*').in_('event_id', ids[start:start+100]).limit(100).execute().data or []
    except Exception as exc:
        st.warning('Event chronology could not be loaded.'); st.caption(str(exc)); return
    by_id = {str(e['event_id']): e for e in events if e.get('event_id')}
    # One event can have several link rows: retain them, show the strongest without inflating event counts.
    grouped = {}
    for l in links:
        eid = str(l.get('event_id') or '')
        if eid in by_id: grouped.setdefault(eid, []).append(l)
    rank = {'directly_affected': 0, 'targeted': 1, 'exposed': 2, 'nearby': 3}
    items = []
    for eid, event_links in grouped.items():
        best = sorted(event_links, key=lambda l: rank.get(l.get('relation_type'), 4))[0]
        items.append((by_id[eid], best, event_links))
    items.sort(key=lambda x: (str(x[0].get('start_date') or ''), str(x[0].get('event_id') or '')), reverse=True)
    st.markdown('#### Infrastructure incident and operational history')
    st.caption('Same source-linked chronology for ports and airports. Direct effects, exposure and advisories are separate; linked records are not all attacks.')
    latest = str(items[0][0].get('start_date') or '')[:10] or 'Not dated'
    c1,c2,c3 = st.columns(3)
    c1.metric('Dated / linked records', len(items))
    c2.metric('Direct / targeted event links', sum(any(l.get('relation_type') in DIRECT for l in ll) for _,_,ll in items))
    c3.metric('Most recent event date', latest)
    st.caption('Relationship counts are not a count of strikes or confirmed damage. Separate restrictions, advisories and events remain distinct.')
    category_choices = ['All categories', 'Attacks & threats', 'Operational restrictions', 'Transport & cargo effects', 'Advisories', 'Other developments']
    filter_col,rel_col = st.columns(2)
    selected = filter_col.selectbox('Development category', category_choices, key='pc_infra_cat_'+str(asset_id))
    relation = rel_col.selectbox('Relationship evidence', ['All relationships', 'Direct / targeted', 'Exposure / contextual'], key='pc_infra_rel_'+str(asset_id))
    displayed = 0
    for i,(e,l,all_links) in enumerate(items):
        cat = _classification(e,l)
        is_direct = any(x.get('relation_type') in DIRECT for x in all_links)
        if selected!='All categories' and cat!=selected: continue
        if relation=='Direct / targeted' and not is_direct: continue
        if relation=='Exposure / contextual' and is_direct: continue
        displayed += 1
        date = str(e.get('start_date') or '')[:16].replace('T',' ') or 'Undated'
        label, specific = _relation(l)
        status = e.get('verification_status') or e.get('record_status') or 'Not classified'
        with st.expander(f'{date} · {cat} · {e.get("title") or e.get("event_id")}', expanded=False):
            st.caption(f'Relationship: {label} | Evidence status: {status} | Event: {e.get("event_id")}')
            if specific: st.write('Specific relationship: '+str(specific).replace('_',' '))
            if e.get('description'): st.write(e.get('description'))
            meta=e.get('metadata') if isinstance(e.get('metadata'),dict) else {}
            u=meta.get('gsa_update10_20261012') if isinstance(meta.get('gsa_update10_20261012'),dict) else {}
            if u:
                st.markdown('**Dated reporting — not a live facility-status feed**')
                if u.get('gaca_riyadh_suspension_extended'): st.write('Suspension extension reported; confirmed reopening date not established.')
                if u.get('notam_end_reported_utc'): st.write('NOTAM expiry reported: '+str(u['notam_end_reported_utc'])+' (not a confirmed reopening).')
                if u.get('cirium_reported_saudi_cancellations_pct') is not None: st.write('Saudi-wide scheduled-flight cancellations reported: '+str(u['cirium_reported_saudi_cancellations_pct'])+'% (not facility-specific).')
                if u.get('etihad_abu_dhabi_riyadh_cancellations_through_reported'): st.write('Etihad AUH–RUH cancellations reported through: '+str(u['etihad_abu_dhabi_riyadh_cancellations_through_reported']))
                st.caption('Attribution: '+str(u.get('attribution') or 'See source record'))
            if navigate is not None and st.button('Open event dossier',key='pc_shared_infra_evt_'+str(asset_id)+'_'+str(i)):
                navigate('event',str(e['event_id']),str(e.get('title') or e['event_id']))
    if displayed == 0:
        st.info('No records match these filters. Switch back to All categories or All relationships.')
    with st.expander('Data coverage and limitations'):
        st.write('Only explicit pc_event_asset_links relationships are shown. No keyword- or proximity-derived damage. Unlinked events are not silently added to this asset. Categories are for reading the chronology, not new event types in the database.')
        st.write('Current open/closed status must be confirmed from current competent-authority notices. Historical restrictions and NOTAM expiry dates are not live operational status.')
