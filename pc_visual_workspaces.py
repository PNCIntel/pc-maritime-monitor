"""Map-first, bounded P&C Trade and Intelligence workspaces.
Only reads prepared delivery views and fixed-asset coordinates; never modifies Supabase.
"""
from __future__ import annotations
import html
import pandas as pd
import streamlit as st

@st.cache_data(ttl=90,show_spinner=False)
def _data(_db,table,columns='*',limit=1500,offset=0,where=None):
    q=_db.table(table).select(columns)
    for key,val in (where or {}).items(): q=q.eq(key,val)
    return q.range(offset,offset+limit-1).execute().data or []

def _load(db,table,**kw):
    try:return _data(db,table,**kw),None
    except Exception as e:return [],str(e)

def _coords(r,lat='latitude',lon='longitude'):
    try:
        a,b=float(r.get(lat)),float(r.get(lon))
        if -90<=a<=90 and -180<=b<=180 and not (a==0 and b==0):return a,b
    except(TypeError,ValueError):pass
    return None

def _map(rows,lat='latitude',lon='longitude',height=570):
    points=[{'latitude':xy[0],'longitude':xy[1]} for r in rows if (xy:=_coords(r,lat,lon))]
    if points:st.map(pd.DataFrame(points),latitude='latitude',longitude='longitude',height=height,use_container_width=True)
    else:st.info('Verified coordinates are not available for this selection. Try including mapped facilities.')
    return len(points)

def _open(core,typ,oid,name):
    core._set_context(str(typ),str(oid),str(name));st.rerun()

def _title(kicker,title,subtitle):
    st.caption(kicker.upper());st.title(title);st.caption(subtitle)

def _trade(db,core):
    _title('P&C • Trade & Logistics','Global Trade Network','Explore infrastructure, operators, transport connections and commercial developments.')
    # Geographic points MUST come from real fixed infrastructure, not company HQ.
    filters=st.columns([2,1,1])
    term=filters[0].text_input('Find a place, operator or facility',placeholder='Rotterdam, Fujairah, railway, airport…')
    country=filters[1].text_input('Country filter',placeholder='e.g. Netherlands')
    categories=['All infrastructure','Ports & terminals','Airports','Rail & intermodal','Road & logistics','Energy & industry']
    selected=filters[2].selectbox('Map layers',categories)
    rows,err=_load(db,'pc_intel_trade_picture',limit=1500)
    if err:st.warning('Prepared Trade dataset unavailable; check the delivery-view migration.');return
    # Use facility rows preferentially, with a fallback to the canonical fixed-asset table.
    assets=[r for r in rows if r.get('object_type')=='asset']
    if not assets or not any(_coords(r) for r in assets):
        fallback,_=_load(db,'pc_assets',columns='asset_id,name,asset_type,subtype,country,latitude,longitude',limit=1500)
        if fallback: assets=[{**r,'object_id':r.get('asset_id'),'object_type':'asset','category':r.get('asset_type')} for r in fallback]
    def fits(r):
        blob=' '.join(str(r.get(k)or'') for k in ('name','category','subtype')).casefold()
        kind=blob
        if term and term.casefold() not in blob:return False
        if country and country.casefold() not in str(r.get('country') or '').casefold():return False
        keys={'Ports & terminals':('port','terminal','harbour','berth'), 'Airports':('airport','aviation','air cargo'), 'Rail & intermodal':('rail','dry port','intermodal'), 'Road & logistics':('road','warehouse','logistics','distribution'), 'Energy & industry':('refiner','oil','gas','lng','industrial','pipeline','power')}
        return selected=='All infrastructure' or any(x in kind for x in keys[selected])
    visible=[r for r in assets if fits(r)]
    stats=st.columns(4)
    stats[0].metric('Facilities in view',f'{len(visible):,}')
    stats[1].metric('Mapped locations',sum(bool(_coords(r)) for r in visible))
    stats[2].metric('Countries represented',len({str(r.get('country')) for r in visible if r.get('country')}))
    stats[3].metric('Transport & industrial layers',len(categories)-1)
    st.subheader('Infrastructure & transport map')
    _map(visible,height=570)
    below=st.columns([1.35,1],gap='large')
    with below[0]:
        st.subheader('Explore facilities')
        st.caption('Filter the map, then open a business profile. Only a small result page is drawn.')
        page=st.number_input('Page',min_value=1,max_value=max(1,(len(visible)+19)//20),value=1,step=1,key='trade_map_page')
        for i,r in enumerate(visible[(page-1)*20:page*20]):
            name=str(r.get('name') or r.get('object_id'))
            a,b=st.columns([4,1]);a.write('**'+name+'**');a.caption(' · '.join(str(x) for x in [r.get('category'),r.get('country')] if x))
            if b.button('Explore',key=f'tm_{page}_{i}'):_open(core,'asset',r.get('object_id'),name)
    with below[1]:
        st.subheader('Commercial developments')
        updates,_=_load(db,'pc_intel_trade_developments',limit=80)
        seen=set();n=0
        for r in sorted(updates,key=lambda r:str(r.get('occurred_at') or ''),reverse=True):
            eid=r.get('event_id')
            if not eid or eid in seen:continue
            seen.add(eid);n+=1
            with st.container(border=True):
                st.write('**'+str(r.get('title') or 'Development')+'**')
                st.caption(str(r.get('occurred_at') or '')[:10])
                if r.get('narrative'):st.write(str(r['narrative'])[:240])
                if st.button('Read more',key=f'tev_{n}'):_open(core,'event',eid,r.get('title'))
            if n>=5:break

def _security(db,core):
    _title('P&C • Security & Disruptions','Global Operating Picture','Reported incidents, geographic exposure, historical developments and supported assessments.')
    rows,err=_load(db,'pc_intel_security_picture',limit=2500)
    if err:st.warning('Prepared Security dataset unavailable; check the intelligence views.');return
    cols=st.columns([1.5,1,1])
    search=cols[0].text_input('Search incidents, locations and actors',placeholder='Hormuz, ReCAAP, UAE…')
    period=cols[1].selectbox('Reporting period',['Last 30 days','Last 90 days','All recorded','Last 7 days'],index=0)
    groups=sorted({str(r.get('event_family') or 'Other') for r in rows})
    family=cols[2].selectbox('Incident category',['All categories']+groups)
    days={'Last 7 days':7,'Last 30 days':30,'Last 90 days':90}.get(period)
    cutoff=pd.Timestamp.now(tz='UTC')-pd.Timedelta(days=days) if days else None
    filtered=[]
    for r in rows:
        if family!='All categories' and str(r.get('event_family')or'Other')!=family:continue
        if search and search.casefold() not in ' '.join(str(r.get(k) or '') for k in ('title','location_label','narrative','event_type')).casefold():continue
        if cutoff is not None:
            dt=pd.to_datetime(r.get('occurred_at'),utc=True,errors='coerce')
            if pd.isna(dt) or dt<cutoff:continue
        filtered.append(r)
    # Deduplicate joined/prepared records by event ID.
    unique={str(r.get('event_id')):r for r in filtered if r.get('event_id')}
    incidents=sorted(unique.values(),key=lambda r:str(r.get('occurred_at')or''),reverse=True)
    k=st.columns(3)
    k[0].metric('Reported developments',len(incidents))
    k[1].metric('Mapped incidents',sum(bool(_coords(r,'latitude_text','longitude_text')) for r in incidents))
    k[2].metric('Records with assessments',sum(bool(r.get('source_risk_level') or r.get('source_risk_trend')) for r in incidents))
    st.subheader('Incident & exposure map')
    _map(incidents,'latitude_text','longitude_text',height=580)
    body=st.columns([1.4,1],gap='large')
    with body[0]:
        st.subheader('Recent & significant developments')
        page=st.number_input('Incident page',min_value=1,max_value=max(1,(len(incidents)+11)//12),value=1,step=1)
        for i,r in enumerate(incidents[(page-1)*12:page*12]):
            with st.container(border=True):
                st.write('**'+str(r.get('title') or 'Incident')+'**')
                st.caption(' · '.join(str(x) for x in [str(r.get('occurred_at')or'')[:10],r.get('location_label'),r.get('event_family')] if x))
                if r.get('narrative'):st.write(str(r['narrative'])[:450])
                if st.button('Open incident',key=f'sec_{page}_{i}'):_open(core,'event',r.get('event_id'),r.get('title'))
    with body[1]:
        st.subheader('Recorded risk & trend assessments')
        assessed=[r for r in incidents if r.get('source_risk_level') or r.get('source_risk_trend')]
        if assessed:
            for r in assessed[:12]:
                st.write('**'+str(r.get('location_label') or r.get('title'))+'**')
                st.caption('Risk: '+str(r.get('source_risk_level') or 'Not assessed')+' · Trend: '+str(r.get('source_risk_trend') or 'Not assessed'))
        else:st.info('No approved risk or trend ratings in this selection. Event counts alone do not establish HIGH or INCREASING.')
        st.subheader('Monitoring context')
        st.caption('Use recorded event evidence and dated assessments to interpret changes. Unverified narratives remain distinguishable from confirmed effects.')

def render_home(db,core,lens):
    if lens=='trade':return _trade(db,core)
    if lens=='intelligence':return _security(db,core)
    raise ValueError('Unsupported workspace '+str(lens))
