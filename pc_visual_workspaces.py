"""P&C Trade/Security customer workspaces v4. Read-only Supabase access.

Uses LIVE SQL delivery views; avoids fixed initial-window filtering and bulk button rendering.
No hypothetical threat ratings, vessel locations, or geographic event pins.
"""
from __future__ import annotations
import datetime as dt
import pandas as pd
import streamlit as st

PAGE_SIZE = 12

@st.cache_data(ttl=75, show_spinner=False)
def _fetch(_db, table, *, columns='*', filters=(), search='', search_columns=('name',), limit=300, offset=0, order=(), layer_terms=()):
    q = _db.table(table).select(columns)
    for column, operator, value in filters:
        if operator == 'eq': q = q.eq(column, value)
        elif operator == 'gte': q = q.gte(column, value)
        elif operator == 'lte': q = q.lte(column, value)
    clauses=[]
    if layer_terms:
        clauses.append(','.join(f'{col}.ilike.%{word}%' for word in layer_terms for col in ('category', 'subtype')))
    if search:
        term = search.replace('%', '').replace(',', ' ').strip()
        if term: clauses.append(','.join(f'{col}.ilike.%{term}%' for col in search_columns))
    if clauses:
        expression=clauses[0] if len(clauses)==1 else 'and('+','.join('or('+clause+')' for clause in clauses)+')'
        q=q.or_(expression)
    for column, descending in order:
        q = q.order(column, desc=descending)
    return q.range(offset, offset+limit-1).execute().data or []

def _load(db, table, **kwargs):
    try: return _fetch(db, table, **kwargs), None
    except Exception as error: return [], str(error)

def _open(core, typ, oid, title):
    core._set_context(str(typ), str(oid), str(title)); st.rerun()

def _coordinate(row):
    try:
        lat, lon = float(row.get('latitude')), float(row.get('longitude'))
        if -90 <= lat <= 90 and -180 <= lon <= 180 and (lat, lon) != (0, 0): return lat, lon
    except (ValueError, TypeError): pass
    return None

def _geo_map(rows, *, label_key='name', height=520):
    mapped=[]
    for r in rows:
        xy = _coordinate(r)
        if xy: mapped.append({'lat':xy[0], 'lon':xy[1], 'label':str(r.get(label_key) or '')})
    if mapped:
        st.map(pd.DataFrame(mapped), latitude='lat', longitude='lon', height=height, size=100, use_container_width=True)
    else:
        st.info('No verified map coordinates for this selection. Records remain available below.')
    return len(mapped)

def _trade(db, core):
    st.caption('POWER & CORRIDORS  /  TRADE & LOGISTICS')
    st.title('Global Trade Network')
    st.caption('Explore operating infrastructure, transport connections, companies and commercial developments.')
    tabs = st.tabs(['Latest developments', 'Infrastructure map', 'Companies & operations'])
    with tabs[1]:
        a,b,c=st.columns([2,1,1])
        term=a.text_input('Search places and facilities', placeholder='Fujairah, Khalifa, Rotterdam, airport…', key='v4_t_search')
        country=b.text_input('Country (blank = all)',placeholder='Enter a country',key='v4_t_country').strip()
        layer=c.selectbox('Infrastructure layer',['All facilities','Ports & terminals','Airports','Rail & intermodal','Road & logistics','Energy & industry'],key='v4_t_layer')
        signature=(term.strip(), country, layer)
        if st.session_state.get('v4_t_filter_signature') != signature:
            st.session_state['v4_t_page']=1
            st.session_state['v4_t_cards']=1
            st.session_state['v4_t_filter_signature']=signature
        st.caption('Country: '+(country or 'All countries')+' · '+layer)
        page=st.number_input('Map results page',min_value=1,max_value=100000,value=1,key='v4_t_page')
        f=[]
        if country: f.append(('country','eq',country))
        names={'Ports & terminals':'port,terminal,harbour,berth','Airports':'airport,aviation','Rail & intermodal':'rail,intermodal,dry port','Road & logistics':'road,warehouse,logistics','Energy & industry':'oil,gas,refin,industrial,energy,pipeline'}
        # All category filters are applied server side, not after fetching the first 1,500 rows.
        rows,err=_load(db,'pc_v4_trade_facilities',filters=tuple(f),search=term,
                       search_columns=('name','category','subtype'),limit=250,offset=(page-1)*250,
                       order=(('is_mapped',True),('name',False),('object_id',False)),
                       layer_terms=tuple(names[layer].split(',')) if layer != 'All facilities' else ())
        if err:
            st.error('The Trade delivery view is unavailable. Apply the v4 SQL migration and verify database permissions.');st.caption(err);return
        st.subheader('Infrastructure & transport map')
        mapped=_geo_map(rows,height=580)
        x,y,z=st.columns(3)
        x.metric('Facilities on page',len(rows));y.metric('Mapped facilities',mapped);z.metric('Countries represented',len({r.get('country') for r in rows if r.get('country')}))
        st.subheader('Explore the network')
        if not rows:st.info('No facilities match these filters. Try a broader search or country name.')
        card_signature=(signature,page)
        if st.session_state.get('v4_t_card_signature') != card_signature:
            st.session_state['v4_t_cards']=1
            st.session_state['v4_t_card_signature']=card_signature
        card_page=st.number_input('Facility cards page',min_value=1,max_value=max(1,(len(rows)+PAGE_SIZE-1)//PAGE_SIZE),key='v4_t_cards')
        card_start=(card_page-1)*PAGE_SIZE
        for i in range(card_start,min(len(rows),card_start+PAGE_SIZE),3):
            cells=st.columns(3)
            for col,r in zip(cells,rows[i:i+3]):
                with col:
                    with st.container(border=True):
                        st.markdown('**'+str(r.get('name') or 'Facility')+'**')
                        st.caption(' · '.join(str(v) for v in (r.get('category'),r.get('country')) if v))
                        if r.get('operator_name'): st.caption('Operated by '+str(r['operator_name']))
                        if st.button('Explore facility',key=f'v4_fac_{page}_{i}_{r.get("object_id")}'):
                            _open(core,'asset',r.get('object_id'),r.get('name'))
        if rows:st.caption(f'Showing facilities {card_start+1}–{min(len(rows),card_start+PAGE_SIZE)} of {len(rows)} on map page {page}.')
    with tabs[2]:
        st.subheader('Companies & operating networks')
        name=st.text_input('Find a company',key='v4_company_search',placeholder='AD Ports Group, DP World, Vopak…')
        if len(name.strip())<2:st.info('Search for a company to explore its operating footprint and corporate relationships.')
        else:
            companies,err=_load(db,'pc_delivery_objects',filters=(('object_type','eq','entity'),),
                                search=name,search_columns=('name',),limit=15)
            if err:st.warning('Company search temporarily unavailable.')
            for r in companies:
                left,right=st.columns([5,1]);left.write('**'+str(r.get('name'))+'**')
                if right.button('Explore',key='v4_company_'+str(r.get('object_id'))):_open(core,'entity',r.get('object_id'),r.get('name'))
    with tabs[0]:
        st.subheader('Latest trade developments')
        st.caption('Production events, newest first. Includes historical developments and links to their full dossiers.')
        term=st.text_input('Find developments',key='v4_developments_search')
        updates,err=_load(db,'pc_events',filters=(('trade_visible','eq',True),),search=term,
                          search_columns=('title','description'),limit=30,
                          order=(('start_date',True),('event_id',False)))
        if err:
            st.error('Recent developments could not be loaded.');st.caption(err)
        elif not updates:
            st.info('No visible production events match this search.')
        seen=set()
        for row in updates:
            eid=row.get('event_id')
            if not eid or eid in seen:continue
            seen.add(eid)
            with st.container(border=True):
                st.markdown('**'+str(row.get('title') or 'Development')+'**')
                st.caption(str(row.get('start_date') or '')[:10])
                if row.get('description'):st.write(str(row['description'])[:550])
                st.caption(' · '.join(str(row.get(k)) for k in ('event_domain','event_type','status') if row.get(k)))
                if st.button('Read development',key='v4_dev_'+str(eid)):_open(core,'event',eid,row.get('title'))

def _security(db,core):
    st.caption('POWER & CORRIDORS  /  SECURITY & DISRUPTIONS')
    st.title('Global Operating Picture')
    st.caption('Historical incidents, mapped exposure, available risk assessments and source-backed narratives.')
    a,b,c=st.columns([2,1,1])
    term=a.text_input('Search incidents, locations and actors',placeholder='Hormuz, ReCAAP, port attack…',key='v4_s_search')
    period=b.selectbox('Period',['All history','Today','Last 7 days','Last 30 days','Last 12 months','Custom dates'],key='v4_s_period')
    category=c.text_input('Incident type (optional)',placeholder='e.g. maritime',key='v4_s_category')
    filters=[]
    now=dt.datetime.now(dt.timezone.utc)
    days={'Today':1,'Last 7 days':7,'Last 30 days':30,'Last 12 months':365}.get(period)
    if days:filters.append(('occurred_at','gte',(now-dt.timedelta(days=days)).isoformat()))
    elif period=='Custom dates':
        d1,d2=st.columns(2)
        start=d1.date_input('From',value=dt.date(2024,1,1),key='v4_start')
        end=d2.date_input('To',value=now.date(),key='v4_end')
        if start>end:st.error('Start date must be before end date.');return
        filters += [('occurred_at','gte',start.isoformat()),('occurred_at','lte',end.isoformat()+'T23:59:59+00:00')]
    # Retrieve events server-side (date/search filters before LIMIT); no fixed first-2,500 global slice.
    page=st.number_input('Incident results page',min_value=1,max_value=100000,value=1,key='v4_s_page')
    incidents,err=_load(db,'pc_v4_security_geo',filters=tuple(filters),search=term,
                  search_columns=('title','narrative','location_label','event_type'),limit=250,offset=(page-1)*250)
    if err:st.error('Security delivery view unavailable. Apply the v4 SQL migration.');st.caption(err);return
    if category: incidents=[r for r in incidents if category.casefold() in str(r.get('event_type') or '').casefold()]
    unique={r.get('event_id'):r for r in incidents if r.get('event_id')}
    incidents=list(unique.values())
    k1,k2,k3=st.columns(3)
    k1.metric('Developments on page',len(incidents))
    k2.metric('Mapped locations',sum(_coordinate(r) is not None for r in incidents))
    k3.metric('Recorded risk assessments',sum(bool(r.get('source_risk_level') or r.get('source_risk_trend')) for r in incidents))
    st.subheader('Incident & exposure map')
    _geo_map(incidents,label_key='title',height=580)
    approx=sum(r.get('map_precision')=='linked_facility_context' and _coordinate(r) is not None for r in incidents)
    if approx:st.caption(f'{approx} markers show the location of an explicitly linked facility, not verified incident coordinates.')
    t1,t2=st.tabs(['Incidents & developments','Risk, trends & evidence'])
    with t1:
        for r in incidents[:PAGE_SIZE]:
            with st.container(border=True):
                st.markdown('**'+str(r.get('title') or 'Incident')+'**')
                st.caption(' · '.join(str(v) for v in (str(r.get('occurred_at') or '')[:10],r.get('location_label'),r.get('event_type')) if v))
                if r.get('narrative'):st.write(str(r['narrative'])[:650])
                if r.get('map_precision')=='linked_facility_context':st.caption('Map location: linked facility context')
                if st.button('Open full incident',key='v4_event_'+str(r.get('event_id'))):_open(core,'event',r.get('event_id'),r.get('title'))
        if len(incidents)>PAGE_SIZE:st.caption('Showing 12 incident cards. Narrow the search or select another result page.')
    with t2:
        assessed=[r for r in incidents if r.get('source_risk_level') or r.get('source_risk_trend')]
        if not assessed:st.info('No recorded risk/trend assessment for this selection. Incident count alone does not establish HIGH or INCREASING.')
        for r in assessed[:20]:
            st.markdown('**'+str(r.get('location_label') or r.get('title'))+'**')
            st.write('Risk: '+str(r.get('source_risk_level') or 'Not assessed')+' · Trend: '+str(r.get('source_risk_trend') or 'Not assessed'))
            st.caption('Assessment fields are shown as stored; check provenance in the full incident dossier.')

def render_home(db,core,lens):
    if db is None:
        st.error('Supabase connection unavailable. Check the configured database client.');return
    if lens=='trade':return _trade(db,core)
    if lens=='intelligence':return _security(db,core)
    raise ValueError('Unsupported P&C workspace '+str(lens))
