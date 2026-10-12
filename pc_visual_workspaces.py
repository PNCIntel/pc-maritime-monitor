"""P&C Trade/Security customer workspaces v4. Read-only Supabase access.

Uses LIVE SQL delivery views; avoids fixed initial-window filtering and bulk button rendering.
No hypothetical threat ratings, vessel locations, or geographic event pins.
"""
from __future__ import annotations
import datetime as dt
from html import escape
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
        elif operator == 'ilike': q = q.ilike(column, value)
        elif operator == 'in': q = q.in_(column, list(value))
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
        q = q.order(column, desc=descending, nullsfirst=False)
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
        st.subheader('Commercial developments')
        st.caption('Follow infrastructure investment, shipping transactions and changes to operating capacity.')
        find,scope_col,period_col=st.columns([2,2,1])
        term=find.text_input('Find developments',key='v4_developments_search',placeholder='Paranagua, methanol, Star Bulk…')
        coverage=scope_col.selectbox('Coverage',['Commercial & infrastructure','All trade developments','Upcoming milestones'],key='pc_trade_feed_scope')
        period=period_col.selectbox('Time window',['Last 30 days','Last 7 days','Last 12 months','All history'],key='pc_trade_feed_period')
        now=dt.datetime.now(dt.timezone.utc)
        filters=[('trade_visible','eq',True)]
        if coverage=='Upcoming milestones':
            filters.extend([('start_date','gte',now.isoformat()),('start_date','lte',(now+dt.timedelta(days=90)).isoformat())])
        else:
            filters.append(('start_date','lte',now.isoformat()))
            days={'Last 30 days':30,'Last 7 days':7,'Last 12 months':365}.get(period)
            if days:filters.append(('start_date','gte',(now-dt.timedelta(days=days)).isoformat()))
            if coverage=='Commercial & infrastructure':filters.append(('event_type','eq','commercial_development'))
        signature=(term,coverage,period)
        if st.session_state.get('pc_trade_feed_signature')!=signature:
            st.session_state['pc_trade_feed_page']=1
            st.session_state['pc_trade_feed_signature']=signature
        page=st.number_input('Developments page',min_value=1,max_value=100000,key='pc_trade_feed_page')
        updates,err=_load(db,'pc_events',filters=tuple(filters),search=term,
            search_columns=('title','description','location','countries'),limit=PAGE_SIZE+1,offset=(page-1)*PAGE_SIZE,
            order=(('start_date',coverage!='Upcoming milestones'),('event_id',False)))
        if err:st.error('Commercial developments could not be loaded.');st.caption(err);return
        has_more=len(updates)>PAGE_SIZE
        updates=list({r['event_id']:r for r in updates[:PAGE_SIZE] if r.get('event_id')}.values())
        ids=tuple(r['event_id'] for r in updates)
        evidence=[];vessels=[];company_links=[];companies=[]
        if ids:
            evidence,eerr=_load(db,'pc_event_evidence',filters=(('event_id','in',ids),),limit=300)
            vessels,verr=_load(db,'pc_v_event_vessel_links',filters=(('event_id','in',ids),),limit=100)
            company_links,cerr=_load(db,'pc_event_entity_links',filters=(('event_id','in',ids),),limit=300)
            company_ids=tuple({x['entity_id'] for x in company_links if x.get('entity_id')})
            if company_ids:companies,nerr=_load(db,'pc_entities',columns='entity_id,name',filters=(('entity_id','in',company_ids),),limit=300)
            if eerr or verr or cerr:st.caption('Some supporting details could not be retrieved.')
        names={r['entity_id']:r.get('name') for r in companies}
        x,y,z=st.columns(3)
        x.metric('Developments on page',len(updates))
        y.metric('Linked companies',len(names))
        z.metric('Linked vessels',len({v.get('mobile_asset_id') for v in vessels if v.get('mobile_asset_id')}))
        if coverage=='Upcoming milestones':st.caption('Scheduled dates over the next 90 days. These are future milestones, not completed developments; the time-window selector applies to historical coverage.')
        else:st.caption('Current and historical developments through today. Future calendar dates are available under Upcoming milestones.')
        if not updates:st.info('No developments match this selection. Try All trade developments or a wider time window.')
        for i in range(0,len(updates),2):
            cells=st.columns(2)
            for cell,row in zip(cells,updates[i:i+2]):
                eid=row['event_id'];meta=row.get('metadata') or {}
                with cell:
                    with st.container(border=True):
                        stamp=pd.to_datetime(row.get('start_date'),utc=True,errors='coerce')
                        date=stamp.tz_convert('Asia/Dubai').strftime('%d %b %Y') if not pd.isna(stamp) else 'Date unrecorded'
                        stage=meta.get('stage') or row.get('status')
                        st.caption(date+(' · '+_business_label(stage) if stage else ''))
                        st.markdown('### '+str(row.get('title') or 'Development'))
                        if row.get('description'):st.write(row['description'])
                        impact=row.get('commercial_impact') or row.get('operational_impact')
                        st.markdown('**Why it matters**')
                        st.write(impact or 'Commercial implications have not yet been assessed.')
                        linked_names=list(dict.fromkeys(names[x['entity_id']] for x in company_links if x.get('event_id')==eid and names.get(x.get('entity_id'))))
                        if linked_names:st.markdown('**Companies:** '+', '.join(linked_names))
                        linked_vessels=[v for v in vessels if v.get('event_id')==eid]
                        for v in linked_vessels:
                            st.caption('Vessel: '+str(v.get('vessel_name') or 'Name unavailable')+' · IMO '+str(v.get('imo') or 'Unrecorded'))
                        st.caption('Evidence: '+_business_label(row.get('verification_status')))
                        observations=[e for e in evidence if e.get('event_id')==eid]
                        urls=list(dict.fromkeys(str(e['original_url']) for e in observations if str(e.get('original_url') or '').startswith(('http://','https://'))))
                        if not urls and str(meta.get('source_url') or '').startswith(('http://','https://')):urls=[meta['source_url']]
                        if urls:st.link_button('Read principal source',urls[0])
                        with st.expander('Evidence and additional sources'):
                            for e in observations:
                                st.write(e.get('claim') or '')
                                st.caption(_business_label(e.get('verification_status')))
                            for j,url in enumerate(urls[1:]):st.link_button('Additional source '+str(j+1),url)
                            if not observations:st.write('No separate evidence observations recorded.')
                        if st.button('Explore development below',key='v4_dev_'+str(eid)):_open_below('event',eid,row.get('title'))
        if has_more:st.caption('More developments available on the next page.')
        _render_related_below(db,core)


def _assessment_freshness(row):
    """Expiry is not evidence of improvement or service resumption."""
    try:
        expiry=dt.datetime.fromisoformat(str(row.get('valid_until')).replace('Z','+00:00'))
        if expiry.tzinfo is None: expiry=expiry.replace(tzinfo=dt.timezone.utc)
        return 'REVIEW DUE' if expiry <= dt.datetime.now(dt.timezone.utc) else 'CURRENT'
    except (ValueError,TypeError):
        return 'VALIDITY UNRECORDED'


def _airport_display(value):
    names={
        'OERK':'Riyadh — King Khalid International Airport',
        'OEDF':'Dammam — King Fahd International Airport',
        'OEJN':'Jeddah — King Abdulaziz International Airport',
        'OEAB':'Abha International Airport',
        'OEGN':'Jazan — King Abdullah bin Abdulaziz Airport',
        'OENG':'Najran Airport',
        'OEKM':'Khamis Mushait — King Khalid Air Base',
        'OETF':'Taif International Airport',
        'OEYN':'Yanbu — Prince Abdul Mohsin bin Abdulaziz Airport',
        'OYAA':'Aden International Airport',
        'OMAA':'Abu Dhabi — Zayed International Airport',
        'LLBG':'Tel Aviv — Ben Gurion Airport',
    }
    return names.get(str(value or '').upper(),'Airport name unavailable')

def _business_label(value):
    return str(value or 'Not recorded').replace('_',' ').strip().capitalize()

def _render_pc_assessments(db,core,term):
    st.subheader('P&C risk briefing')
    st.caption('Independent qualitative judgments. Assessment scope and validity are separate from the incident date filter.')
    rows,error=_load(db,'pc_v_security_pc_assessments',search=term,
        search_columns=('geography','headline','region_code','explanation'),
        order=(('as_known_at',True),('assessment_id',False)),limit=100)
    if error:
        st.warning('The P&C assessment feed is unavailable. Load the assessment SQL update and refresh the database.')
        with st.expander('Assessment connection details'): st.caption(error)
        return
    if not rows:
        st.info('No published P&C assessment matches this search.')
        return
    regions=list(dict.fromkeys(str(r.get('geography') or r.get('region_code')) for r in rows))
    area=st.selectbox('Assessment area',['All matching areas']+regions,key='pc_assessment_area')
    selected=[r for r in rows if area=='All matching areas' or str(r.get('geography') or r.get('region_code'))==area]
    st.markdown("""<style>
.pc-brief-hero{background:#142b42;color:#fff;padding:24px 28px;border-radius:12px;margin:12px 0 20px;border-left:5px solid #c9a461}
.pc-brief-hero h3,.pc-brief-hero h3 *{color:#fff!important;-webkit-text-fill-color:#fff!important;margin:0 0 8px}.pc-brief-hero p,.pc-brief-hero p *{color:#e0e8ef!important;-webkit-text-fill-color:#e0e8ef!important;margin:0}
.pc-risk-grid{width:100%;border-collapse:collapse;margin:12px 0 22px;font-size:.92rem}
.pc-risk-grid th{text-align:left;padding:12px;border-bottom:2px solid #c9a461}
.pc-risk-grid td{padding:12px;border-bottom:1px solid #8193a544;vertical-align:top}
.pc-pill{display:inline-block;padding:4px 9px;border-radius:5px;font-weight:700;font-size:.78rem;white-space:nowrap}
.pc-high{background:#fce8e6;color:#922b21}.pc-medium{background:#fff1d6;color:#805400}.pc-low{background:#e1f2ec;color:#17654a}.pc-unknown{background:#e7edf3;color:#40556a}
</style>""",unsafe_allow_html=True)
    st.markdown('<div class="pc-brief-hero"><h3>Operating risk briefing</h3><p>Read the judgments across locations, then explore the reasoning, commercial exposure and evidence behind each assessment.</p></div>',unsafe_allow_html=True)
    counts=st.columns(3)
    counts[0].metric('Published assessments',len(selected))
    counts[1].metric('Require review',sum(_assessment_freshness(r)!='CURRENT' for r in selected))
    counts[2].metric('Linked companies',len({c.get('entity_id') for r in selected for c in (r.get('company_exposure') or []) if c.get('entity_id')}))
    st.markdown('#### Risk at a glance')
    def badge(value):
        value=str(value or 'INSUFFICIENT EVIDENCE')
        tone={'HIGH':'high','SEVERE':'high','CRITICAL':'high','MODERATE':'medium','MEDIUM':'medium','LOW':'low'}.get(value.upper(),'unknown')
        return '<span class="pc-pill pc-'+tone+'">'+escape(value)+'</span>'
    table='<table class="pc-risk-grid"><thead><tr><th>Assessment</th><th>Risk / disruption</th><th>Direction</th><th>Confidence</th><th>Review status</th></tr></thead><tbody>'
    for r in selected:
        table+='<tr><td>'+escape(str(r.get('headline') or r.get('geography')))+'</td><td>'+badge(r.get('risk_level'))+'</td><td>'+escape(str(r.get('trend') or 'UNDETERMINED'))+'</td><td>'+escape(str(r.get('confidence') or 'Unassigned').capitalize())+'</td><td>'+escape(_assessment_freshness(r))+'</td></tr>'
    st.markdown(table+'</tbody></table>',unsafe_allow_html=True)
    st.caption('Qualitative judgments, not numerical probabilities. Undetermined direction and insufficient evidence remain explicit. Assessment dates are independent of incident filters.')
    with st.expander('Key judgments across this selection',expanded=True):
        for r in selected:
            st.markdown('**'+str(r.get('headline') or r.get('geography'))+'**')
            st.write(r.get('executive_summary') or r.get('explanation') or '')
    st.markdown('#### Explore an assessment')
    choices={str(r['assessment_id']):str(r.get('headline') or r.get('geography')) for r in selected}
    if st.session_state.get('pc_brief_detail') not in choices:
        st.session_state['pc_brief_detail']=next(iter(choices))
    chosen=st.selectbox('Detailed briefing',list(choices),format_func=lambda aid:choices[aid],key='pc_brief_detail')
    for row in [r for r in selected if str(r['assessment_id'])==chosen]:
        aid=str(row['assessment_id'])
        with st.container(border=True):
            st.markdown('#### '+str(row.get('headline') or row.get('geography')))
            st.caption('P&C analysis · '+str(row.get('assessment_date'))+' · '+_assessment_freshness(row))
            x,y,z=st.columns(3)
            x.metric('Risk / disruption',row.get('risk_level') or 'INSUFFICIENT EVIDENCE')
            y.metric('Trend',row.get('trend') or 'UNDETERMINED')
            z.metric('Confidence',str(row.get('confidence') or 'Unassigned').capitalize())
            st.write(row.get('executive_summary') or row.get('explanation') or '')
            st.caption('Valid until '+str(row.get('valid_until') or 'Unrecorded')+' · Coverage: '+str(row.get('coverage_status') or 'Unrecorded'))
            if _assessment_freshness(row)!='CURRENT':
                st.warning('Review due: this is an earlier assessment snapshot. It does not establish current conditions.')
            with st.expander('Reasoning, threat drivers and scope'):
                st.write(row.get('explanation') or '')
                for driver in row.get('threat_drivers') or []: st.markdown('- '+str(driver))
                st.caption(row.get('scope_note') or '')
                st.caption(row.get('methodology_notice') or '')
            with st.expander('Companies and operating exposure',expanded=True):
                companies=row.get('company_exposure') or []
                if not companies:
                    st.write('No airport-company links documented for this assessment scope.')
                else:
                    exposure=pd.DataFrame([{'Company':c.get('company'),'Airport':_airport_display(c.get('airport')),'Relationship':_business_label(c.get('role')),'Evidence status':_business_label(c.get('status'))} for c in companies]).drop_duplicates()
                    chart,listing=st.columns([1,2])
                    with chart:
                        st.markdown('**Documented relationships by role**')
                        role_counts=exposure.groupby('Relationship',dropna=False).size().rename('Relationships')
                        st.bar_chart(role_counts,color='#468c9b',horizontal=True)
                        st.caption('Counts of recorded links; they do not measure financial exposure.')
                    with listing:
                        st.dataframe(exposure,hide_index=True,use_container_width=True)
                        options=list(range(len(companies)))
                        idx=st.selectbox('Company dossier',options,format_func=lambda i:str(companies[i].get('company'))+' · '+_airport_display(companies[i].get('airport')),key='pc_company_select_'+aid)
                        c=companies[idx]
                        if st.button('Explore selected company',key='pc_company_open_'+aid):
                            _open_below('entity',c.get('entity_id'),c.get('company'))
                st.caption('A documented operating relationship establishes exposure; it does not establish company damage or financial loss.')
            with st.expander('Supporting chronology and sources'):
                for i,e in enumerate(row.get('evidence') or []):
                    st.write(str(e.get('title') or 'Supporting incident'))
                    url=e.get('source_url')
                    if isinstance(url,str) and url.startswith(('https://','http://')):
                        st.link_button('Supporting source',url)
                    if st.button('Open evidence dossier',key=f'pc_assess_event_{aid}_{i}'):
                        _open_below('event',e.get('event_id'),e.get('title'))
            with st.expander('Monitoring priorities and review triggers'):
                st.markdown('**Monitoring priorities**')
                for value in row.get('monitoring_priorities') or []: st.markdown('- '+str(value))
                st.markdown('**Review triggers**')
                for value in row.get('review_triggers') or []: st.markdown('- '+str(value))


def _open_below(typ,oid,title):
    current=st.session_state.get('pc_brief_related')
    if current and (current['type'],current['id'])!=(str(typ),str(oid)):
        history=st.session_state.setdefault('pc_brief_related_history',[])
        history.append(current)
        del history[:-30]
    st.session_state['pc_brief_related']={'type':str(typ),'id':str(oid),'title':str(title or 'Related record')}
    st.rerun()


def _render_airport_infrastructure(db,oid):
    airports,error=_load(db,'pc_airports',filters=(('asset_id','eq',oid),),limit=1)
    if error or not airports:return
    ap=airports[0]
    st.markdown('#### Airport infrastructure')
    st.caption('Published physical infrastructure is separate from current runway availability and flight status.')
    x,y,z=st.columns(3)
    x.metric('IATA / ICAO',str(ap.get('iata_code') or '—')+' / '+str(ap.get('icao_code') or '—'))
    y.metric('Published runway count',ap.get('runway_count') if ap.get('runway_count') is not None else 'Unrecorded')
    z.metric('Elevation (ft)',ap.get('elevation_ft') if ap.get('elevation_ft') is not None else 'Unrecorded')
    runways,err=_load(db,'pc_airport_runways',filters=(('airport_id','eq',oid),),order=(('runway_ident',False),),limit=50)
    if err:st.warning('Runway records could not be loaded.')
    elif runways:
        table=[]
        for rw in runways:
            table.append({'Runway':rw.get('runway_ident'),'Length (m)':rw.get('length_m'),
                'Width (m)':rw.get('width_m'),'Surface':_business_label(rw.get('surface')),
                'Pavement classification':rw.get('pavement_classification') or 'Not recorded'})
        st.dataframe(pd.DataFrame(table),hide_index=True,use_container_width=True)
        with st.expander('Runway ends and declared distances'):
            ends=[];distances=[];source_urls=set()
            for rw in runways:
                for side in ('le','he'):
                    ends.append({'Runway end':rw.get(side+'_ident'),'True heading':rw.get(side+'_heading_deg_true'),
                        'Latitude':rw.get(side+'_latitude'),'Longitude':rw.get(side+'_longitude'),'Elevation (ft)':rw.get(side+'_elevation_ft')})
                published=rw.get('declared_distances') or {}
                if isinstance(published,dict):
                    for end,vals in published.items():
                        if isinstance(vals,dict):
                            distances.append({'Runway end':end,'TORA (m)':vals.get('tora_m'),
                                'TODA (m)':vals.get('toda_m'),'ASDA (m)':vals.get('asda_m'),'LDA (m)':vals.get('lda_m')})
                meta=rw.get('metadata') or {}
                for value in meta.values():
                    if isinstance(value,dict) and value.get('source_url'):source_urls.add(value['source_url'])
            st.dataframe(pd.DataFrame(ends),hide_index=True,use_container_width=True)
            if distances:st.dataframe(pd.DataFrame(distances),hide_index=True,use_container_width=True)
            st.caption('TORA: takeoff run; TODA: takeoff distance; ASDA: accelerate-stop distance; LDA: landing distance. Publication snapshots do not confirm present availability.')
            for url in sorted(source_urls):
                if str(url).startswith(('https://','http://')):st.link_button('Published aeronautical source',url)
    else:st.info('No runway records are available for this airport.')
    facilities,ferr=_load(db,'pc_airport_facilities',filters=(('airport_id','eq',oid),),limit=100)
    if facilities:
        st.markdown('#### Terminals and facilities')
        st.dataframe(pd.DataFrame([{'Facility':f.get('facility_name'),'Type':_business_label(f.get('facility_type')),
            'Recorded status':_business_label(f.get('status')),'Warehouse area (m²)':f.get('warehouse_area_sqm'),
            'Annual capacity (tonnes)':f.get('annual_capacity_tonnes')} for f in facilities]),hide_index=True,use_container_width=True)
    if ferr:st.caption('Facility records are temporarily unavailable.')
    services,serr=_load(db,'pc_air_services',filters=(('destination_airport_key','eq',oid),),
        order=(('observed_at',True),),limit=100)
    if services:
        st.markdown('#### Airline and cargo observations')
        st.dataframe(pd.DataFrame([{'Service / observation':v.get('service_name'),
            'Recorded status':_business_label(v.get('route_status')),'Observed':str(v.get('observed_at') or '')[:10]} for v in services]),hide_index=True,use_container_width=True)
        st.caption('Dated observations may describe cancellations or restrictions; they do not establish a complete current timetable.')
    if serr:st.caption('Air service observations are temporarily unavailable.')

def _render_related_below(db,core):
    current=st.session_state.get('pc_brief_related')
    if not current:return
    st.divider()
    st.subheader('Explore below the briefing')
    back,close=st.columns(2)
    if back.button('← Back',key='pc_related_back'):
        history=st.session_state.get('pc_brief_related_history') or []
        st.session_state['pc_brief_related']=history.pop() if history else None
        st.session_state['pc_brief_related_history']=history
        st.rerun()
    if close.button('Close details · return to briefing',key='pc_related_close'):
        st.session_state.pop('pc_brief_related',None)
        st.session_state.pop('pc_brief_related_history',None)
        st.rerun()
    typ,oid=current['type'],current['id']
    rec=core.object_record(typ,oid) or {}
    st.markdown('### '+str(rec.get('name') or rec.get('title') or current['title']))
    st.caption('Your briefing and assessment selection remain above.')
    overview,related=st.tabs(['Overview','Connected records'])
    with overview:
        text=rec.get('description') or rec.get('summary') or rec.get('notes')
        if text:st.write(text)
        facts=[]
        for key,label in [('country','Country'),('hq_country','Headquarters country'),('region_city','Location'),('entity_type','Organisation type'),('asset_type','Infrastructure type'),('status','Status')]:
            if rec.get(key):facts.append({'Detail':label,'Value':_business_label(rec[key]) if key.endswith('_type') or key=='status' else str(rec[key])})
        if facts:st.dataframe(pd.DataFrame(facts),hide_index=True,use_container_width=True)
        if typ=='asset':_render_airport_infrastructure(db,oid)
        if not rec:st.info('The overview record could not be retrieved. The full dossier may have additional detail.')
        url=rec.get('website') or rec.get('source_url')
        if isinstance(url,str) and url.startswith(('https://','http://')):st.link_button('Visit supporting website',url)
        if st.button('Open full dossier',key='pc_related_full'):
            _open(core,typ,oid,current['title'])
    with related:
        links=core._relationships(typ,oid)
        choices=[]
        seen=set()
        for link in links:
            side='target' if str(link.get('source_id'))==oid else 'source'
            other_id=link.get(side+'_id');other_type=link.get(side+'_type')
            if not other_id or not other_type or (other_type,other_id) in seen:continue
            seen.add((other_type,other_id))
            name=link.get(side+'_name') or core._object_name(other_type,other_id)
            if not name or str(name)==str(other_id):name='Related '+_business_label(other_type).lower()
            choices.append({'id':other_id,'type':other_type,'name':name,'relationship':_business_label(link.get('relationship_type'))})
        if not choices:st.info('No connected records are available in this relationship view. Use the full dossier for specialist services and facilities.')
        else:
            st.dataframe(pd.DataFrame([{'Name':x['name'],'Relationship':x['relationship']} for x in choices]),hide_index=True,use_container_width=True)
            signature=(typ,oid)
            if st.session_state.get('pc_related_signature')!=signature:
                st.session_state['pc_related_choice']=0
                st.session_state['pc_related_signature']=signature
            idx=st.selectbox('Explore another connected record',list(range(len(choices))),format_func=lambda i:choices[i]['name'],key='pc_related_choice')
            if st.button('Show connected record below',key='pc_related_next'):
                x=choices[idx];_open_below(x['type'],x['id'],x['name'])


def _weekly_frame(rows):
    unique={str(r['event_id']):r for r in rows if r.get('event_id')}
    records=[]
    for r in unique.values():
        when=pd.to_datetime(r.get('start_date'),utc=True,errors='coerce')
        if pd.isna(when):continue
        status=str(r.get('verification_status') or 'unrecorded').lower()
        evidence={'verified':'Verified in database','confirmed':'Confirmed in database','reported':'Reported','claimed':'Claimed','unverified':'Unverified'}.get(status,'Other / unrecorded')
        records.append({'Date':when.date(),'Development':str(r.get('title') or 'Development'),
            'Category':_business_label(r.get('event_type')),'Evidence':evidence,
            'event_id':str(r['event_id']),'description':str(r.get('description') or '')})
    return pd.DataFrame(records,columns=['Date','Development','Category','Evidence','event_id','description'])

def _render_weekly(db,core):
    st.subheader('Weekly developments & escalation')
    st.caption('Compare recorded activity, operational restrictions and warning changes across two equal seven-day windows.')
    a,b=st.columns([1,2])
    today=dt.datetime.now(dt.timezone(dt.timedelta(hours=4))).date()
    end=a.date_input('Week ending',value=today,key='pc_week_end')
    scope=b.selectbox('Weekly coverage',['Saudi airports & Yemen campaign research','All published intelligence'],key='pc_week_scope')
    term=st.text_input('Filter the weekly timeline',placeholder='Optional: Riyadh, Abha, airline…',key='pc_week_search')
    start=end-dt.timedelta(days=6)
    previous=start-dt.timedelta(days=7)
    filters=[('intelligence_visible','eq',True),('start_date','gte',previous.isoformat()+'T00:00:00+04:00'),
        ('start_date','lte',end.isoformat()+'T23:59:59.999999+04:00')]
    if scope=='Saudi airports & Yemen campaign research':
        filters.append(('metadata->>research_package','in',('saudi_aviation_20261011','saudi_aviation_live02_20261011','saudi_aviation_update04_20261012')))
    rows=[]
    for offset in range(0,5000,500):
        batch,error=_load(db,'pc_events',columns='event_id,title,start_date,event_type,verification_status,description',
            filters=tuple(filters),search=term,search_columns=('title','description'),
            order=(('start_date',False),('event_id',False)),limit=500,offset=offset)
        if error:
            st.warning('The weekly event feed could not be loaded.')
            with st.expander('Weekly connection details'):st.caption(error)
            return
        rows.extend(batch)
        if len(batch)<500:break
    if len(rows)>=5000:st.warning('The comparison is limited to 5,000 records. Narrow the selection for complete totals.')
    frame=_weekly_frame(rows)
    # Display calendar dates in the same UAE timezone as the query windows.
    dates={str(r['event_id']):pd.to_datetime(r['start_date'],utc=True).tz_convert('Asia/Dubai').date() for r in rows if r.get('event_id') and r.get('start_date')}
    if not frame.empty:frame['Date']=frame['event_id'].map(dates)
    current=frame[(frame['Date']>=start)&(frame['Date']<=end)]
    prior=frame[(frame['Date']>=previous)&(frame['Date']<start)]
    st.caption(f'Current: {start:%d %b}–{end:%d %b %Y} · Comparison: {previous:%d %b}–{(start-dt.timedelta(days=1)):%d %b %Y} · UAE calendar dates')
    x,y,z=st.columns(3)
    x.metric('Recorded developments this week',len(current),delta=f'{len(current)-len(prior):+d} versus previous week',delta_color='off')
    y.metric('Previous week',len(prior))
    z.metric('Active reporting days',current['Date'].nunique())
    st.info('These are counts of database event records, not attacks or munitions. A warning, cancellation notice or multi-airport report is one record. More reporting alone does not establish escalation. Verification of an event does not confirm attribution.')
    if current.empty:st.info('No recorded developments in this week and selection.');return
    chart,context=st.columns([2,1])
    with chart:
        st.markdown('#### Daily developments by category')
        daily=current.groupby(['Date','Category']).size().unstack(fill_value=0)
        daily=daily.reindex([start+dt.timedelta(days=i) for i in range(7)],fill_value=0)
        st.bar_chart(daily)
    with context:
        st.markdown('#### Evidence status this week')
        st.bar_chart(current.groupby('Evidence').size().rename('Records'),horizontal=True,color='#468c9b')
    st.markdown('#### What changed between the weeks')
    comparison=pd.concat([prior.groupby('Category').size().rename('Previous week'),
        current.groupby('Category').size().rename('This week')],axis=1).fillna(0).astype(int)
    comparison['Change in records']=comparison['This week']-comparison['Previous week']
    st.dataframe(comparison.reset_index(),hide_index=True,use_container_width=True)
    st.caption('Assess escalation through consequences and geography as well as frequency: casualties, damage, new targets, wider restrictions and official warning changes. Current P&C judgments are in Risk briefing; these charts do not generate a risk score.')
    st.markdown('#### Weekly chronology')
    include_previous=st.checkbox('Include the previous week in the chronology',value=True,key='pc_week_include_previous')
    timeline=(frame if include_previous else current).sort_values(['Date','event_id'],ascending=[False,False])
    st.dataframe(timeline[['Date','Development','Category','Evidence']],hide_index=True,use_container_width=True)
    options=timeline.to_dict('records')
    signature=(str(end),scope,term)
    if st.session_state.get('pc_week_signature')!=signature:
        st.session_state['pc_week_evidence_choice']=0
        st.session_state['pc_week_signature']=signature
    idx=st.selectbox('Read a development',list(range(len(options))),format_func=lambda i:str(options[i]['Date'])+' · '+options[i]['Development'],key='pc_week_evidence_choice')
    item=options[idx]
    if item['description']:st.write(item['description'])
    if st.button('Show evidence below briefing',key='pc_week_open'):
        _open_below('event',item['event_id'],item['Development'])

def _airport_choices(rows, airport_details):
    """Collapse display duplicates; preserve distinct ICAO identities and all database records."""
    codes={str(r.get('asset_id')):str(r.get('icao_code') or '').strip().upper() for r in airport_details}
    grouped={}
    for row in rows:
        meta=row.get('metadata') or {}
        canonical=meta.get('canonicalization') or {}
        if canonical.get('action') in ('merged_alias','merged','alias'):continue
        if canonical.get('canonical_asset_id') and str(canonical['canonical_asset_id'])!=str(row.get('asset_id')):continue
        code=codes.get(str(row.get('asset_id'))) or str(meta.get('icao_code') or '').strip().upper()
        name=''.join(c for c in str(row.get('name') or '').casefold() if c.isalnum())
        key=('icao',code) if code else ('name',str(row.get('country') or '').casefold(),name)
        rank=(canonical.get('action')=='survivor',_coordinate(row) is not None,
              row.get('record_status')=='approved',bool(code),bool(row.get('source_id')))
        candidate=dict(row,icao_code=code)
        existing=grouped.get(key)
        if existing is None or rank>existing[0]:grouped[key]=(rank,candidate)
    return [value[1] for value in grouped.values()]

def _security(db,core):
    st.caption('POWER & CORRIDORS  /  SECURITY & DISRUPTIONS')
    st.title('Global Operating Picture')
    st.caption('Published intelligence, operational consequences and supporting evidence. Recent developments appear first.')
    a,b,c=st.columns([2,1,1])
    term=a.text_input('Search incidents, locations and actors',placeholder='Hormuz, ReCAAP, port attack…',key='v4_s_search')
    if not st.session_state.get('pc_current_feed_v2'):
        st.session_state['v4_s_period']='Last 7 days'
        st.session_state['pc_current_feed_v2']=True
    period=b.selectbox('Period',['Last 7 days','Today','Last 30 days','Last 12 months','All history','Custom dates'],key='v4_s_period')
    category=c.text_input('Incident type (optional)',placeholder='e.g. maritime',key='v4_s_category')
    now=dt.datetime.now(dt.timezone.utc)
    filters=[('intelligence_visible','eq',True),('start_date','lte',now.isoformat())]
    days={'Today':1,'Last 7 days':7,'Last 30 days':30,'Last 12 months':365}.get(period)
    if days:
        boundary=(now.astimezone(dt.timezone(dt.timedelta(hours=4))).replace(hour=0,minute=0,second=0,microsecond=0)
                  if period=='Today' else now-dt.timedelta(days=days))
        filters.append(('start_date','gte',boundary.isoformat()))
    elif period=='Custom dates':
        d1,d2=st.columns(2)
        start=d1.date_input('From',value=dt.date(2024,1,1),key='v4_start')
        end=d2.date_input('To',value=now.date(),key='v4_end')
        if start>end:st.error('Start date must be before end date.');return
        filters += [('start_date','gte',start.isoformat()+'T00:00:00+04:00'),('start_date','lte',end.isoformat()+'T23:59:59.999999+04:00')]
    if category.strip():
        filters.append(('event_type','ilike','%'+category.strip().replace('%','').replace('_','\\_')+'%'))
    # Reset pagination when the selection changes, before creating the page widget.
    selection=(term,period,category,str(start) if period=='Custom dates' else '',
               str(end) if period=='Custom dates' else '')
    if st.session_state.get('v4_s_selection') != selection:
        st.session_state['v4_s_page']=1
        st.session_state['v4_s_selection']=selection
    # Fetch one card page plus a lookahead, with stable newest-first ordering.
    page=st.number_input('Incident results page',min_value=1,max_value=100000,value=1,key='v4_s_page')
    incidents,err=_load(db,'pc_events',filters=tuple(filters),search=term,
                  search_columns=('title','description','location','countries','event_type'),
                  order=(('start_date',True),('event_id',False)),
                  limit=PAGE_SIZE+1,offset=(page-1)*PAGE_SIZE)
    if err:st.error('Published intelligence could not be loaded.');st.caption(err);return
    has_more=len(incidents)>PAGE_SIZE
    incidents=incidents[:PAGE_SIZE]
    unique={r.get('event_id'):r for r in incidents if r.get('event_id')}
    incidents=list(unique.values())
    event_ids=tuple(str(r['event_id']) for r in incidents)
    evidence=[]; vessel_links=[]
    if event_ids:
        geo,geo_error=_load(db,'pc_v4_security_geo',filters=(('event_id','in',event_ids),),limit=100)
        geo_by_id={r['event_id']:r for r in geo}
        evidence,evidence_error=_load(db,'pc_event_evidence',filters=(('event_id','in',event_ids),),limit=300)
        vessel_links,vessel_error=_load(db,'pc_v_event_vessel_links',filters=(('event_id','in',event_ids),),limit=100)
        if geo_error:st.caption('Incident coordinates are temporarily unavailable.')
        if evidence_error:st.caption('Supporting evidence is temporarily unavailable.')
        if vessel_error:st.caption('Vessel associations are temporarily unavailable.')
        incidents=[dict(geo_by_id.get(r['event_id'],{}),**r,occurred_at=r.get('start_date'),
            narrative=r.get('description'),location_label=r.get('location') or r.get('countries')) for r in incidents]
    k1,k2,k3=st.columns(3)
    k1.metric('Developments on page',len(incidents))
    k2.metric('Mapped incident locations on page',sum(_coordinate(r) is not None for r in incidents))
    k3.metric('Linked vessels on page',len({r.get('mobile_asset_id') for r in vessel_links if r.get('mobile_asset_id')}))
    t2,tweek,t1,tmap=st.tabs(['Risk briefing','Weekly escalation','Incidents & developments','Incident map'])
    with tweek:
        _render_weekly(db,core)
    with tmap:
        st.subheader('Incident & exposure map')
        airport_term=st.text_input('Find airport infrastructure',value='Riyadh',placeholder='Riyadh, King Khalid, Abha…',key='pc_map_airport_search')
        airports,airport_error=_load(db,'pc_assets',search=airport_term,
            search_columns=('name','region_city','subtype'),
            filters=(('asset_type','ilike','%airport%'),),
            order=(('name',False),('asset_id',False)),limit=100)
        loaded_airports=len(airports)
        airport_ids=tuple(str(r['asset_id']) for r in airports if r.get('asset_id'))
        details=[]
        if airport_ids:
            details,detail_error=_load(db,'pc_airports',columns='asset_id,icao_code',filters=(('asset_id','in',airport_ids),),limit=100)
        airports=[dict(r,object_id=r.get('asset_id')) for r in _airport_choices(airports,details)]
        if airport_error:
            st.warning('Airport infrastructure could not be loaded.')
            with st.expander('Airport connection details'): st.caption(airport_error)
        points=[]
        for r in incidents:
            xy=_coordinate(r)
            if xy:
                points.append({'latitude':xy[0],'longitude':xy[1],'name':r.get('title'),
                    'layer':'Linked facility context' if r.get('map_precision')=='linked_facility_context' else 'Incident location','colour':'#cf594e'})
        for r in airports:
            xy=_coordinate(r)
            if xy:
                points.append({'latitude':xy[0],'longitude':xy[1],'name':r.get('name'),'layer':'Airport infrastructure','colour':'#468c9b'})
        if points:
            st.map(pd.DataFrame(points),latitude='latitude',longitude='longitude',color='colour',size=120,height=580,use_container_width=True)
            st.dataframe(pd.DataFrame(points)[['name','layer']],hide_index=True,use_container_width=True)
        else:
            st.info('No usable coordinates in these incident or airport results. Try another airport search.')
        st.caption('Teal: airport infrastructure matching the airport search. Red: incident locations or linked facility context on the current incident page. Infrastructure markers do not establish an exact strike location.')
        st.caption(f'{len(airports)} distinct airports · {sum(_coordinate(r) is not None for r in airports)} with coordinates. Airport search is independent of incident pagination.')
        if airports:
            choices={str(r['object_id']):r for r in airports if r.get('object_id')}
            if choices:
                if st.session_state.get('pc_map_airport_choice') not in choices:
                    st.session_state['pc_map_airport_choice']=next(iter(choices))
                chosen=st.selectbox('Airport dossier',list(choices),format_func=lambda key:str(choices[key].get('name'))+(' · '+choices[key]['icao_code'] if choices[key].get('icao_code') else ''),key='pc_map_airport_choice')
                if st.button('Explore airport',key='pc_map_open_airport'):
                    _open_below('asset',chosen,choices[chosen].get('name'))

    with t1:
        st.caption('Published intelligence through the present. Future calendar entries are excluded. Dates are shown in UAE time.')
        for r in incidents[:PAGE_SIZE]:
            with st.container(border=True):
                st.markdown('**'+str(r.get('title') or 'Incident')+'**')
                stamp=pd.to_datetime(r.get('start_date'),utc=True,errors='coerce')
                shown_date=stamp.tz_convert('Asia/Dubai').strftime('%d %b %Y') if not pd.isna(stamp) else 'Date unrecorded'
                st.caption(' · '.join(str(v) for v in (shown_date,r.get('location_label'),_business_label(r.get('event_type'))) if v))
                st.caption('Evidence: '+_business_label(r.get('verification_status'))+' · Confidence: '+_business_label(r.get('confidence')))
                if r.get('narrative'):st.write(str(r['narrative']))
                impact=r.get('operational_impact') or r.get('commercial_impact') or r.get('expected_disruption')
                if impact:st.markdown('**Operational consequence:** '+str(impact))
                else:st.caption('Operational consequence has not yet been assessed for this record.')
                linked=[v for v in vessel_links if v.get('event_id')==r['event_id']]
                for v in linked:
                    st.markdown('**Vessel:** '+str(v.get('vessel_name') or 'Name unavailable')+' · IMO '+str(v.get('imo') or 'Unrecorded')+' · '+_business_label(v.get('vessel_type')))
                sources=[e for e in evidence if e.get('event_id')==r['event_id']]
                urls=list(dict.fromkeys(str(e['original_url']) for e in sources if str(e.get('original_url') or '').startswith(('http://','https://'))))
                source_url=(r.get('metadata') or {}).get('source_url')
                if isinstance(source_url,str) and source_url.startswith(('http://','https://')) and source_url not in urls:urls.append(source_url)
                with st.expander('Evidence and source links · '+str(len(sources))+' observations'):
                    for e in sources:
                        st.write(e.get('claim') or '')
                        st.caption(_business_label(e.get('verification_status'))+' · Published '+str(e.get('published_at') or 'date unrecorded')[:10])
                    for i,url in enumerate(urls):st.link_button('Read source '+str(i+1),url)
                    if not sources and not urls:st.write('No supporting evidence is linked yet.')
                if r.get('map_precision')=='linked_facility_context':st.caption('Map location: linked facility context')
                if st.button('Explore development below',key='v4_event_'+str(r.get('event_id'))):_open_below('event',r.get('event_id'),r.get('title'))
        if has_more:st.caption('More incidents available — increase Incident results page to continue.')
        elif incidents:st.caption('End of matching results.')
        else:st.info('No incidents on this page. Return to page 1 or change the filters.')
    with t2:
        _render_pc_assessments(db,core,term)
        st.subheader('Outside assessments recorded on incident cards')
        assessed=[r for r in incidents if r.get('source_risk_level') or r.get('source_risk_trend')]
        if not assessed:st.info('No outside risk/trend fields on this incident page. P&C assessments are shown separately above.')
        for r in assessed[:20]:
            st.markdown('**'+str(r.get('location_label') or r.get('title'))+'**')
            st.write('Risk: '+str(r.get('source_risk_level') or 'Not assessed')+' · Trend: '+str(r.get('source_risk_trend') or 'Not assessed'))
            st.caption('Assessment fields are shown as stored; check provenance in the full incident dossier.')

    _render_related_below(db,core)

def render_home(db,core,lens):
    if db is None:
        st.error('Supabase connection unavailable. Check the configured database client.');return
    if lens=='trade':return _trade(db,core)
    if lens=='intelligence':return _security(db,core)
    raise ValueError('Unsupported P&C workspace '+str(lens))


