"""Read-only, globally reusable airport event dossier from canonical graph links."""
import streamlit as st
import pandas as pd

def _rows(db, table, field, value, limit=300):
    try:
        return db.table(table).select('*').eq(field, value).limit(limit).execute().data or [], None
    except Exception as exc:
        return [], str(exc)

def render_airport_event_dossier(db, airport_id, navigate=None):
    if not db or not airport_id:
        return
    links, error = _rows(db, 'pc_event_asset_links', 'asset_id', airport_id)
    if error:
        st.warning('Airport event graph is temporarily unavailable.'); return
    event_ids = list(dict.fromkeys(str(x.get('event_id')) for x in links if x.get('event_id')))
    if not event_ids:
        st.info('No dated airport event relationships recorded.'); return
    try:
        events = db.table('pc_events').select('*').in_('event_id',event_ids[:250]).limit(250).execute().data or []
    except Exception:
        st.warning('Airport event records could not be loaded.'); return
    byid = {str(e.get('event_id')):e for e in events}
    items=[]
    for link in links:
        e=byid.get(str(link.get('event_id')))
        if e:
            items.append((e,link))
    items.sort(key=lambda p:str(p[0].get('start_date') or ''),reverse=True)
    st.markdown('#### Dated operational and security developments')
    st.caption('Linked records include incidents, NOTAM/work restrictions, advisories and downstream exposure. They are not all attacks. Reported expiry dates are not confirmed reopening times.')
    eventtypes={}
    for e,_ in items:
        cat=str(e.get('event_type') or 'Unclassified').replace('_',' ').title()
        eventtypes[cat]=eventtypes.get(cat,0)+1
    cols=st.columns(3)
    cols[0].metric('Linked event records',len(items))
    cols[1].metric('Different event types',len(eventtypes))
    cols[2].metric('Last recorded',str(items[0][0].get('start_date') or '')[:10] if items else '—')
    options=['All records','Attacks and threats','Operations and restrictions','Advisories and exposure']
    chosen=st.selectbox('Airport event lens',options,key='pc_airport_dossier_filter_'+str(airport_id))
    def bucket(e,link):
        typ=' '.join(str(e.get(k) or '') for k in ('event_type','event_category','event_nature')).lower()
        title=str(e.get('title') or '').lower()
        rel=str(link.get('relation_type') or '').lower()
        if any(w in typ+' '+title for w in ('attack','strike','missile','drone','threat','intercept','projectile')):return 'Attacks and threats'
        if any(w in typ+' '+title for w in ('notam','closure','runway','taxiway','stand ','construction','cancellation','airline','cargo','restriction','operational','service')):return 'Operations and restrictions'
        if rel=='exposed' or any(w in typ+' '+title for w in ('advice','advisory','warning','embassy','fcdo','travel')):return 'Advisories and exposure'
        return 'Operations and restrictions'
    for i,(e,link) in enumerate(items):
        if chosen!='All records' and bucket(e,link)!=chosen: continue
        meta=e.get('metadata') if isinstance(e.get('metadata'),dict) else {}
        update=meta.get('gsa_update10_20261012') if isinstance(meta.get('gsa_update10_20261012'),dict) else {}
        when=str(e.get('start_date') or '')[:16].replace('T',' ')
        with st.expander(f"{when} · {e.get('title') or e.get('event_id')}",expanded=False):
            st.caption(f"Type: {str(e.get('event_type') or 'not classified').replace('_',' ')} · Asset relationship: {str(link.get('relation_type') or 'unknown').replace('_',' ')} · Verification: {e.get('verification_status') or e.get('record_status') or 'unclassified'}")
            if e.get('description'):st.write(e['description'])
            if update:
                st.markdown('**Latest sourced operational observation**')
                if update.get('gaca_riyadh_suspension_extended') or update.get('gaca_suspension_extended_reported'):
                    st.write('GACA suspension extension: reported; official reopening date not established.')
                if update.get('notam_end_reported_utc') or update.get('reported_notam_end_utc'):
                    st.write('Reported NOTAM end: '+str(update.get('notam_end_reported_utc') or update.get('reported_notam_end_utc'))+' — not guaranteed reopening; independently verified: '+str(bool(update.get('notam_verified_against_primary_bulletin') or update.get('notam_independently_checked'))))
                if update.get('cirium_reported_saudi_cancellations_pct') is not None:
                    st.write('Reported Saudi-wide flight cancellations: '+str(update['cirium_reported_saudi_cancellations_pct'])+'% (not an airport-specific figure).')
                if update.get('etihad_abu_dhabi_riyadh_cancellations_through_reported'):
                    st.write('Etihad Abu Dhabi–Riyadh cancellations reported through '+str(update['etihad_abu_dhabi_riyadh_cancellations_through_reported']))
                st.caption('Secondary-source attribution: '+str(update.get('attribution') or update.get('source_classification') or 'See source record'))
            if navigate is not None and st.button('Open complete event dossier',key='pc_airport_event_open_'+str(airport_id)+'_'+str(i)):
                navigate('event',str(e['event_id']),str(e.get('title') or e['event_id']))
    with st.expander('Underlying event type breakdown'):
        st.dataframe(pd.DataFrame([{'Type':k,'Records':v} for k,v in sorted(eventtypes.items())]),hide_index=True,use_container_width=True)
