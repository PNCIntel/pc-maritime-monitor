"""Map-led P&C Trade / Security homes backed by live PostgreSQL delivery views.
Read-only. No inferred risk, asset ownership, or incident exposure.
"""
from __future__ import annotations
import html
import pandas as pd
import streamlit as st


def _fetch(db, view, *, limit=1200, order=None):
    try:
        q=db.table(view).select('*')
        if order:
            q=q.order(order,desc=True)
        return (q.limit(limit).execute().data or []), None
    except Exception as exc:
        return [], str(exc)


def _point(r, lat='latitude', lon='longitude'):
    try:
        a,b=float(r.get(lat)),float(r.get(lon))
        if -90<=a<=90 and -180<=b<=180: return a,b
    except (TypeError,ValueError):
        pass
    return None


def _geo(rows, *, lat='latitude', lon='longitude', name='name', height=510):
    pts=[]
    for r in rows:
        xy=_point(r,lat,lon)
        if xy: pts.append({'latitude':xy[0],'longitude':xy[1], 'label':str(r.get(name) or '')})
    if pts:
        st.map(pd.DataFrame(pts),latitude='latitude',longitude='longitude',height=height,use_container_width=True)
        st.caption(f'{len(pts):,} verified mapped locations. Additional records without coordinates remain searchable.')
    else:
        st.info('No recorded coordinates for these filters. Records are still available below.')


def _header(kicker,title,description):
    st.markdown(f"<div style='letter-spacing:.14em;font-size:.72rem;color:#a18434;font-weight:700'>{html.escape(kicker)}</div>",unsafe_allow_html=True)
    st.title(title)
    st.caption(description)


def _nav_choice(core, typ, oid, label):
    """Use the working object-context navigation from the existing terminal."""
    record=core.object_record(typ,oid)
    if record:
        core._set_context(typ,oid,label)
        st.rerun()


def _trade(db, core):
    _header('P&C TRADE & LOGISTICS','Global Trade Network',
            'Explore connected infrastructure, transport, industrial capacity and the companies that operate it.')
    rows,err=_fetch(db,'pc_intel_trade_picture',limit=5000)
    if err:
        st.warning('Prepared Trade data is unavailable. Existing operational dashboard shown instead.')
        core._render_trade_home()
        return
    searchable=[r for r in rows if r.get('object_id') and r.get('name')]
    sidebar, mapcol=st.columns([1.0,2.5],gap='large')
    with sidebar:
        search=st.text_input('Find companies, infrastructure and fleets',placeholder='Rotterdam, Fujairah, railway, airport…',key='pc_v2_trade_find')
        types=sorted({str(r.get('section') or 'Other') for r in searchable})
        selected=st.multiselect('Explore by category',types,default=types,key='pc_v2_trade_cat')
        country_options=sorted({str(r.get('country')) for r in searchable if r.get('country')})
        country=st.selectbox('Country', ['All countries']+country_options,key='pc_v2_trade_country')
        subset=[r for r in searchable if str(r.get('section') or 'Other') in selected
                and (country=='All countries' or r.get('country')==country)
                and (not search or search.casefold() in str(r.get('name','')).casefold())]
        st.metric('Matching records',f'{len(subset):,}')
        st.caption('Select a result to open its full commercial profile.')
        display=subset[:35]
        for i,r in enumerate(display):
            if st.button(str(r.get('name'))[:80],key=f'trade_obj_{i}_{r.get("object_id")}',use_container_width=True):
                _nav_choice(core, str(r.get('object_type') or 'asset'),str(r['object_id']),str(r['name']))
        if len(subset)>35: st.caption(f'Showing 35 of {len(subset):,}; narrow your search to explore more.')
    with mapcol:
        st.subheader('Infrastructure & transport map')
        _geo(subset,height=520)
        a,b,c=st.columns(3)
        a.metric('Mapped locations',sum(bool(_point(r)) for r in subset))
        b.metric('Companies',sum(r.get('object_type')=='entity' for r in subset))
        c.metric('Facilities',sum(r.get('object_type')=='asset' for r in subset))
    st.divider()
    st.subheader('Commercial developments')
    events,event_err=_fetch(db,'pc_intel_trade_developments',limit=250,order='occurred_at')
    if event_err:
        st.caption('Developments data temporarily unavailable.')
    else:
        seen=set()
        shown=0
        for ev in events:
            eid=ev.get('event_id')
            if not eid or eid in seen:continue
            seen.add(eid)
            with st.container(border=True):
                st.markdown('**'+str(ev.get('title') or 'Commercial development')+'**')
                st.caption(' · '.join(x for x in [str(ev.get('occurred_at') or '')[:10],str(ev.get('event_family') or '').replace('_',' ')] if x))
                if ev.get('narrative'): st.write(str(ev['narrative'])[:700])
                if st.button('Read development',key='tv2_event_'+str(eid)):
                    _nav_choice(core,'event',str(eid),str(ev.get('title') or eid))
            shown+=1
            if shown>=8:break


def _security(db,core):
    _header('P&C SECURITY & DISRUPTIONS','Global Operating Picture',
            'Mapped incidents, reported effects and recorded assessments across maritime, aviation, land and industry.')
    events,err=_fetch(db,'pc_intel_security_picture',limit=5000,order='occurred_at')
    if err:
        st.warning('Prepared Security data is unavailable. Existing operating picture shown instead.')
        core._render_intelligence_home()
        return
    categories=sorted({str(r.get('event_family') or 'Other') for r in events})
    left,right=st.columns([1.0,2.5],gap='large')
    with left:
        lookback=st.selectbox('Reporting period',['All recorded','Last 7 days','Last 30 days','Last 90 days'],key='pc_v2_security_period')
        selected=st.multiselect('Incident categories',categories,default=categories,key='pc_v2_security_types')
        search=st.text_input('Search incidents and locations',key='pc_v2_security_find')
        after={'Last 7 days':7,'Last 30 days':30,'Last 90 days':90}.get(lookback)
        cutoff=(pd.Timestamp.now(tz='UTC')-pd.Timedelta(days=after)) if after else None
        filtered=[]
        for r in events:
            if str(r.get('event_family') or 'Other') not in selected:continue
            if search and search.casefold() not in (' '.join(str(r.get(x) or '') for x in ('title','narrative','location_label','event_type'))).casefold():continue
            if cutoff is not None:
                dt=pd.to_datetime(r.get('occurred_at'),errors='coerce',utc=True)
                if pd.isna(dt) or dt<cutoff:continue
            filtered.append(r)
        st.metric('Reported developments',f'{len(filtered):,}')
        assessed=sum(bool(r.get('source_risk_level')) for r in filtered)
        st.caption(f'{assessed:,} records contain a source risk assessment; unassessed records are not assigned ratings.')
        st.subheader('Priority developments')
        for i,e in enumerate(filtered[:16]):
            with st.container(border=True):
                st.markdown('**'+str(e.get('title') or 'Incident')+'**')
                st.caption(str(e.get('occurred_at') or '')[:10]+' · '+str(e.get('event_family') or 'Development'))
                if e.get('source_risk_level') or e.get('source_risk_trend'):
                    st.caption('Recorded risk: '+str(e.get('source_risk_level') or 'Unrated')+' · Trend: '+str(e.get('source_risk_trend') or 'Not assessed'))
                if st.button('Open incident',key=f'sv2_{i}_{e.get("event_id")}'):
                    _nav_choice(core,'event',str(e['event_id']),str(e.get('title') or 'Incident'))
    with right:
        st.subheader('Incident & disruption map')
        _geo(filtered,lat='latitude_text',lon='longitude_text',name='title',height=560)
        st.subheader('Recorded assessments')
        rated=[r for r in filtered if r.get('source_risk_level') or r.get('source_risk_trend')]
        if rated:
            st.dataframe(pd.DataFrame([{'Development':e.get('title'),'Risk':e.get('source_risk_level') or 'Unrated',
                'Trend':e.get('source_risk_trend') or 'Not assessed','Date':str(e.get('occurred_at') or '')[:10]} for e in rated[:30]]),
                hide_index=True,use_container_width=True)
        else:st.info('No source-backed risk or trend assessments in this selection; incident counts alone do not establish HIGH or INCREASING.')
    st.divider()
    st.subheader('Incident narratives & evidence')
    for e in filtered[:8]:
        with st.expander(str(e.get('title') or 'Incident')):
            st.write(e.get('narrative') or 'No narrative returned by the prepared view.')
            st.caption('Classification: '+str(e.get('event_type') or 'Unspecified')+' · '+str(e.get('record_status') or 'Unspecified'))
            if st.button('Full incident dossier',key='sv2_detail_'+str(e.get('event_id'))):
                _nav_choice(core,'event',str(e['event_id']),str(e.get('title') or 'Incident'))


def render_home(db,core,lens):
    if lens=='trade':_trade(db,core)
    elif lens=='intelligence':_security(db,core)
    else:raise ValueError('Unsupported product: '+str(lens))
