"""Customer-facing presentation of PostgreSQL intelligence delivery views.

Read-only; no implied risk ratings, positions, sanctions, or regional impacts.
Requires SQL 20261009_intelligence_layer.sql.
"""
from __future__ import annotations
import pandas as pd
import streamlit as st


def _query(db, table: str, columns='*', *, eq=None, limit=150, order=None):
    if db is None:
        return [], 'Database unavailable'
    try:
        q=db.table(table).select(columns)
        for key, val in (eq or {}).items():
            q=q.eq(key, val)
        if order:
            q=q.order(order,desc=True)
        return q.limit(limit).execute().data or [],None
    except Exception as exc:
        return [], str(exc)


def _number(v):
    try:
        n=float(v)
        return n if -180<=n<=180 else None
    except (TypeError,ValueError):
        return None


def _map(rows, *, latitude='latitude', longitude='longitude', label='title'):
    points=[]
    for r in rows:
        lat=_number(r.get(latitude));lon=_number(r.get(longitude))
        if lat is None or lon is None or not -90<=lat<=90:
            continue
        points.append({'lat':lat,'lon':lon,'name':r.get(label,'')})
    if points:
        st.map(pd.DataFrame(points),latitude='lat',longitude='lon',use_container_width=True)
        st.caption(f'{len(points)} mapped records with stored coordinates; unmapped records remain accessible below.')
    else:
        st.caption('No verified coordinates available for the selected records.')


def render_market_highlights(db, product):
    """Supplement existing home; never replace its established maps and navigation."""
    if product not in ('trade','intelligence'):
        return
    with st.expander('Latest verified-data picture', expanded=False):
        if product == 'intelligence':
            data,err=_query(db,'pc_intel_security_picture',
                'event_id,title,event_type,event_family,occurred_at,recorded_severity,source_risk_level,source_risk_trend,latitude_text,longitude_text',
                order='occurred_at',limit=180)
            if err:
                st.warning('Current intelligence picture unavailable; the previous operating picture remains accessible.')
                return
            if not data:
                st.info('No published events found in this view.')
                return
            family=sorted({str(r.get('event_family') or 'Other') for r in data})
            selected=st.multiselect('Incident categories',family,default=family,key='pc_intel_family_filter')
            show=[r for r in data if str(r.get('event_family') or 'Other') in selected]
            _map(show,latitude='latitude_text',longitude='longitude_text')
            for row in show[:12]:
                when=str(row.get('occurred_at') or '')[:10]
                st.markdown(f"**{row.get('title') or 'Development'}** · {when}")
                details=[row.get('event_type'),row.get('source_risk_level'),row.get('source_risk_trend')]
                st.caption(' · '.join(str(x).replace('_',' ') for x in details if x))
        else:
            data,err=_query(db,'pc_intel_trade_picture',
                'object_id,name,section,category,country,latitude,longitude',limit=750)
            if err:
                st.warning('Infrastructure delivery view unavailable; existing maps and profiles are unaffected.')
                return
            choices=sorted({r.get('section') for r in data if r.get('section')})
            selected=st.multiselect('Infrastructure and activity',choices,default=choices,key='pc_trade_map_types')
            selected_rows=[r for r in data if r.get('section') in selected]
            _map(selected_rows,label='name')


def render_event_profile(db, event_id: str, product: str) -> bool:
    """Present full source-backed event profile in the existing application."""
    rows,err=_query(db,'pc_intel_event_details',eq={'event_id':event_id},limit=1)
    if err or not rows:
        return False  # Preserve existing working fallback.
    e=rows[0]
    st.caption('SECURITY & DISRUPTIONS' if product=='intelligence' else 'DEVELOPMENT & OPERATIONAL CONTEXT')
    st.title(e.get('title') or 'Development')
    c1,c2,c3=st.columns(3)
    c1.metric('Reported date',str(e.get('occurred_at') or 'Not recorded')[:10])
    c2.metric('Classification',str(e.get('event_family') or 'Not classified').replace('_',' '))
    c3.metric('Record status',str(e.get('record_status') or 'Not specified').replace('_',' ').title())
    risk=e.get('source_risk_level');trend=e.get('source_risk_trend')
    if risk or trend:
        st.info('Recorded assessment: '+' · '.join(x for x in [f'Risk: {risk}' if risk else '', f'Trend: {trend}' if trend else ''] if x))
    st.subheader('What happened')
    narrative=e.get('narrative')
    if narrative:
        st.write(narrative)
    else:
        st.info('A narrative has not been returned by the delivery view. The original record remains available for review.')
    st.subheader('Location and operational context')
    _map([e],latitude='latitude_text',longitude='longitude_text')
    if e.get('location_label'):
        st.caption('Recorded location: '+str(e['location_label']))
    links,_=_query(db,'pc_intel_object_events', 'object_type,object_id,link_sources',eq={'event_id':event_id},limit=100)
    if links:
        st.subheader('Affected or associated assets')
        st.caption('Explicit record links only; relationship roles and exposure require verification.')
        # Display types but never call every linked record 'affected'.
        for x in links[:25]:
            st.write(f"{str(x.get('object_type') or '').replace('_',' ').title()}: {x.get('object_id')}")
    evidence=e.get('evidence') or []
    st.subheader('Sources and evidence')
    if evidence:
        for ev in evidence:
            st.write(ev.get('claim') or 'Source entry')
            st.caption('Verification: '+str(ev.get('verification') or 'Not classified'))
            url=ev.get('url')
            if isinstance(url,str) and url.startswith(('https://','http://')):
                st.link_button('Read original source',url)
    else:
        st.caption('No event evidence rows returned. This does not establish that no source exists.')
    # Optional prepared intelligence / trade layer; existing event dossier stays primary.
    try:
        from pc_event_dual_lens import render_event_lens
        render_event_lens(db, event_id, product)
    except ImportError:
        pass
    return True
