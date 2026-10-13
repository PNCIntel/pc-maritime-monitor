"""Customer-facing presentation of PostgreSQL intelligence delivery views.

Read-only; no implied risk ratings, positions, sanctions, or regional impacts.
Requires SQL 20261009_intelligence_layer.sql.
"""
from __future__ import annotations
import re
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


def _airport_coordinates(rec):
    """Use stored airport ARP/profile coordinates; never geocode or invent points."""
    meta=rec.get('metadata') or {}
    sources=[rec,meta]
    for key in ('pc_uae_facilities_20261012','saudi_aviation_update04_20261012','pc_aviation_profile_20261013'):
        part=meta.get(key)
        if isinstance(part,dict):
            sources.append(part)
            if isinstance(part.get('metadata'),dict):
                sources.append(part['metadata'])
    for part in sources:
        if not isinstance(part,dict):
            continue
        for latkey,lonkey in (('latitude','longitude'),('lat','lon'),('lat','lng')):
            lat=_number(part.get(latkey));lon=_number(part.get(lonkey))
            if lat is not None and lon is not None and -90<=lat<=90:
                return lat,lon
        arp=part.get('published_arp')
        if isinstance(arp,(list,tuple)) and len(arp)==2:
            lat=_number(arp[0]);lon=_number(arp[1])
            if lat is not None and lon is not None and -90<=lat<=90:
                return lat,lon
    return None


def _event_airport_context(db,event_id):
    links,err=_query(db,'pc_event_asset_links',eq={'event_id':event_id},limit=200)
    airports=[]
    seen=set()
    for link in links:
        aid=link.get('asset_id')
        if not aid or aid in seen:
            continue
        rows,_=_query(db,'pc_assets',eq={'asset_id':aid},limit=1)
        if not rows or rows[0].get('asset_type')!='airport':
            continue
        seen.add(aid)
        rec=rows[0]
        meta=link.get('metadata') or {}
        airports.append({
            'id':aid,'name':rec.get('name') or aid,
            'iata':meta.get('iata') or (rec.get('metadata') or {}).get('iata') or '',
            'role':meta.get('aviation_role') or link.get('relation_type') or 'associated',
            'impact':link.get('impact_status') or 'not assessed',
            'coordinates':_airport_coordinates(rec)
        })
    priority={'origin_airport':0,'scheduled_destination':1,'diversion_airport':2}
    airports.sort(key=lambda a:priority.get(a['role'],3))
    return airports,err


def render_event_profile(db, event_id: str, product: str) -> bool:
    """Source-aware event dossier. No inferred flight path or physical impact."""
    rows,err=_query(db,'pc_intel_event_details',eq={'event_id':event_id},limit=1)
    if err or not rows:
        return False
    e=rows[0]
    canonical,_=_query(db,'pc_events',eq={'event_id':event_id},limit=1)
    base=canonical[0] if canonical else {}
    st.caption('SECURITY & DISRUPTIONS' if product=='intelligence' else 'DEVELOPMENT & OPERATIONAL CONTEXT')
    st.title(e.get('title') or 'Development')
    metrics=st.columns(4)
    metrics[0].metric('Event date',str(e.get('occurred_at') or base.get('start_date') or 'Not recorded')[:10])
    metrics[1].metric('Classification',str(e.get('event_family') or 'Not classified').replace('_',' '))
    metrics[2].metric('Severity',str(base.get('severity') or 'Not classified').replace('_',' ').title())
    metrics[3].metric('Verification',str(base.get('verification_status') or 'Pending').replace('_',' ').title())
    risk=e.get('source_risk_level');trend=e.get('source_risk_trend')
    if risk or trend:
        st.info('Recorded assessment: '+' · '.join(x for x in [f'Risk: {risk}' if risk else '', f'Trend: {trend}' if trend else ''] if x))
    else:
        st.caption('Severity is the recorded incident classification, not a completed analyst threat assessment.')
    st.subheader('What happened')
    narrative=e.get('narrative')
    if narrative:
        st.write(narrative)
    else:
        st.info('Narrative not returned by the delivery view; the canonical record remains available.')

    st.subheader('Location and operational context')
    airports,airport_error=_event_airport_context(db,event_id)
    mapped=[{'lat':a['coordinates'][0],'lon':a['coordinates'][1],'name':a['name']}
            for a in airports if a['coordinates']]
    if mapped:
        st.map(pd.DataFrame(mapped),latitude='lat',longitude='lon',use_container_width=True)
        st.caption('Airport reference points from stored records. Pins indicate connected infrastructure, not the actual flight track, impact coordinates or airport damage.')
    else:
        _map([e],latitude='latitude_text',longitude='longitude_text')
    if airports:
        st.dataframe(pd.DataFrame([{
            'Airport':a['name'],'IATA':a['iata'],
            'Event role':a['role'].replace('_',' ').title(),
            'Relationship status':a['impact'],
            'Mapped ARP':'Yes' if a['coordinates'] else 'Coordinates pending'
        } for a in airports]),hide_index=True,use_container_width=True)
    elif airport_error:
        st.caption('Canonical airport relationships are temporarily unavailable.')
    if e.get('location_label'):
        st.caption('Recorded event location: '+str(e['location_label']))

    from pc_event_navigation import render_event_connections
    from pc_terminal import _set_context
    def open_dossier(typ, oid, title):
        _set_context(typ, oid, title)
        st.rerun()
    st.subheader('Connected organisations and infrastructure')
    render_event_connections(db,event_id,open_dossier,key_prefix='event_profile',compact=False)

    evidence=e.get('evidence') or []
    st.subheader('Sources and evidence')
    if evidence:
        seen=set()
        for i,ev in enumerate(evidence):
            url=ev.get('url')
            key=url if url else (ev.get('claim'),ev.get('verification'))
            if key in seen:
                continue
            seen.add(key)
            publisher=ev.get('publisher') or ev.get('source_name') or 'Source record'
            st.markdown('**'+str(publisher)+'**')
            st.caption('Verification: '+str(ev.get('verification') or 'Pending'))
            claim=ev.get('claim')
            if claim and claim!=narrative:
                st.write(claim)
            elif claim:
                st.caption('Source-linked event summary; source-specific claims await review.')
            if isinstance(url,str) and url.startswith(('https://','http://')):
                st.link_button('Read original source',url,key=f'pc_profile_source_{i}')
    else:
        source_id=base.get('source_id')
        sources,_=_query(db,'pc_sources',eq={'source_id':source_id},limit=1) if source_id else ([],None)
        if sources:
            source=sources[0]
            st.write(source.get('source_name') or source.get('publisher') or 'Original source')
            url=source.get('url')
            if isinstance(url,str) and url.startswith(('https://','http://')):
                st.link_button('Read original source',url)
        else:
            st.caption('Source details are unavailable for this event.')
    try:
        from pc_event_dual_lens import render_event_lens
        render_event_lens(db,event_id,product)
    except ImportError:
        pass
    return True
