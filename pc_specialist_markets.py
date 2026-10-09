"""Three P&C market dashboards. Read-only views over the existing Supabase model.
No new schema, no inferred ownership, dates, costs, rates or commodity quantities.
"""
from __future__ import annotations
import re
from typing import Any
import pandas as pd
import streamlit as st
from pc_portfolio import MARKETS

# Re-use the application's established Supabase client and object lookup.
try:
    from shared.pc_db import client as _client_factory
except ImportError:
    from pc_db import client as _client_factory

APP = {
    'capital': ('Capital & Ownership', 'Explore investments, shareholders, acquisitions, concessions and financing relationships.', 'Investment & Ownership'),
    'commodities': ('Commodities & Resources', 'Follow energy, food and raw materials through production, infrastructure and commercial networks.', 'Resources & Supply Chains'),
    'markets': ('Markets & Freight', 'Compare reported freight indicators, transport services and capacity observations.', 'Freight & Market Intelligence'),
}

# No required write permissions; run with the database's existing RLS policies.
def _db():
    try:
        return _client_factory(service=False)
    except Exception:
        try:
            return _client_factory()
        except Exception:
            return None

@st.cache_data(ttl=90, show_spinner=False)
def _fetch(table: str, *, field: str | None = None, value: Any = None, limit: int = 500) -> tuple[list[dict], str]:
    sb=_db()
    if sb is None:
        return [], 'Database connection unavailable.'
    try:
        q=sb.table(table).select('*')
        if field and value is not None:
            q=q.eq(field,value)
        return q.limit(limit).execute().data or [], ''
    except Exception as e:
        # Some installations do not yet have all specialist tables or RLS grants.
        return [], f'{table}: {type(e).__name__} — {e}'

def _clean(v):
    if v is None: return ''
    if isinstance(v,(list,dict)): return str(v)
    return str(v)

def _label(key: str):
    names={'entity_id':'Organisation','parent_company_key':'Investor / parent','child_company_key':'Investee / subsidiary',
           'relationship':'Relationship','value':'Reported interest','unit':'Unit','effective_from':'Effective from',
           'effective_to':'Effective to','source_url':'Source','announced_date':'Announced',
           'contract_name':'Agreement','contract_type':'Agreement type','status':'Status',
           'scope_summary':'Scope','reported_value':'Reported value','currency':'Currency',
           'quantity':'Quantity','quantity_unit':'Unit','name':'Name','asset_type':'Facility type',
           'country':'Country','operator_entity_id':'Operator','owner_entity_id':'Owner',
           'metric_name':'Indicator','metric_value':'Value','metric_unit':'Unit','observed_date':'Observed',
           'start_date':'Date','title':'Development','description':'Description',
           'source_id':'Evidence reference','capacity_value':'Capacity','capacity_unit':'Capacity unit',
           'valid_from':'From','valid_to':'To','mode':'Transport mode','commodity':'Commodity',
           'commodity_name':'Commodity','project_stage':'Project stage','estimated_cost':'Estimated cost',
           'contract_id':'Agreement reference'}
    return names.get(key,key.replace('_',' ').capitalize())

def _table(rows, fields, *, label='No recorded entries in this view.', key=None):
    if not rows:
        st.caption(label)
        return
    chosen=[f for f in fields if any(r.get(f) not in (None,'') for r in rows)]
    if not chosen:
        st.caption('Records exist, but these fields are not available in the current dataset.')
        return
    df=pd.DataFrame([{_label(f):r.get(f) for f in chosen} for r in rows])
    st.dataframe(df, use_container_width=True, hide_index=True, key=key)

def _name_index(table, id_col, search):
    entries,_=_fetch(table,limit=2000)
    q=search.casefold().strip()
    found=[r for r in entries if q in _clean(r.get('name') or r.get('contract_name') or r.get('title')).casefold()]
    return found[:60]

def _context_search(prefix):
    with st.expander('Search companies, facilities and fleets', expanded=False):
        query=st.text_input('Search the P&C network',placeholder='ADNOC, Fujairah, Rotterdam, Maersk…', key=f'{prefix}_search')
        if len(query.strip()) < 2: return
        for table,typ in [('pc_entities','Companies & organisations'),('pc_assets','Infrastructure & facilities'),('pc_mobile_assets','Vessels & aircraft')]:
            matches=_name_index(table,'',query)
            if matches:
                st.markdown('**'+typ+'**')
                _table(matches,['name','country','asset_type','subtype','imo'],key=f'{prefix}_{table}')

def _source_note():
    st.caption('Source-backed records only. Reported ownership is not assumed to be current without effective dates; missing rates are not represented as zero. Figures retain their original units.')

def _header(kind):
    title,subtitle,_=APP[kind]
    st.title(title)
    st.caption('POWER & CORRIDORS  /  '+subtitle)
    with st.sidebar:
        st.markdown('### Power & Corridors')
        st.markdown(f'**{title}**')
        st.caption('One database · Seven markets')
        st.divider()
        st.caption('Global records · Multimodal intelligence')

def _pick_entity(key):
    entities,error=_fetch('pc_entities',limit=3000)
    if error: st.warning('Company directory is not accessible with the current database credentials.')
    if not entities: return None,[],{}
    lookup={_clean(x.get('entity_id')):x for x in entities if x.get('entity_id')}
    choices=sorted(lookup, key=lambda i:_clean(lookup[i].get('name')).casefold())
    choice=st.selectbox('Company or investor',options=['']+choices,
        format_func=lambda i: 'Select a company or investor' if not i else _clean(lookup[i].get('name')),
        key=f'{key}_entity')
    return choice, entities, lookup

def capital():
    st.markdown('### Ownership, investment and transactions')
    a,b,c=_fetch('pc_company_relationships',limit=1500)[0],_fetch('pc_company_portfolio_positions',limit=1500)[0],_fetch('pc_contracts',limit=1500)[0]
    d=_fetch('pc_project_details',limit=1200)[0]
    m=st.columns(4)
    for col,title,records in zip(m,['Company relationships','Portfolio positions','Commercial agreements','Investment projects'],[a,b,c,d]):
        col.metric(title,f'{len(records):,}' if len(records)<1500 else '1,500+')
    st.caption('Counts are retrieved records, not guaranteed totals.')
    eid,entities,lookup=_pick_entity('capital')
    if eid:
        st.subheader(_clean(lookup[eid].get('name')))
        # Includes both directions; no guessed beneficial-ownership paths.
        relevant=[r for r in a if eid in (_clean(r.get('parent_company_key')),_clean(r.get('child_company_key')))]
        portfolio=[r for r in b if eid in (_clean(r.get('holder_entity_id')),_clean(r.get('investee_entity_id')))]
        st.markdown('#### Ownership & corporate relationships')
        _table(relevant,['parent_company_key','relationship','child_company_key','value','unit','effective_from','effective_to','source_url'],key='cap_rels')
        st.markdown('#### Portfolio & investments')
        _table(portfolio,['holder_entity_id','investee_entity_id','investee_asset_id','position_type','position_status','source_url'],key='cap_positions')
        participants=_fetch('pc_contract_participants',field='entity_id',value=eid,limit=400)[0]
        contract_ids={_clean(p.get('contract_id')) for p in participants}
        related=[r for r in c if _clean(r.get('contract_id')) in contract_ids]
        st.markdown('#### Commercial agreements & transactions')
        _table(related,['contract_name','contract_type','announced_date','reported_value','currency','scope_summary','source_url'],key='cap_contracts')
    else:
        st.markdown('#### Recent recorded commercial agreements')
        _table(sorted(c,key=lambda r:_clean(r.get('announced_date')),reverse=True)[:35],
               ['contract_name','contract_type','announced_date','reported_value','currency','status'],key='cap_recent')
        st.markdown('#### Ownership relationships')
        _table(a[:50],['parent_company_key','relationship','child_company_key','value','unit','effective_from','effective_to'],key='cap_all')
    _context_search('capital')
    _source_note()

def commodities():
    st.markdown('### Energy, food, minerals and industrial materials')
    categories={'Energy & fuels':r'oil|petrol|gas|lng|lpg|crude|refiner|energy|fuel|hydrogen|pipeline|tank',
                'Food & agriculture':r'grain|wheat|corn|soy|sugar|food|farm|agri|fertiliz|rice|silo',
                'Minerals & metals':r'iron|steel|copper|bauxite|alum|mine|mineral|ore|nickel|lithium|coal|phosphate',
                'Industrial materials':r'cement|chemical|polymer|sulphur|sulfur|construction|timber|wood|industrial'}
    pick=st.selectbox('Resource sector',list(categories),key='commodity_sector')
    rx=re.compile(categories[pick],re.I)
    assets,_=_fetch('pc_assets',limit=4000)
    companies,_=_fetch('pc_entities',limit=4000)
    projects,_=_fetch('pc_project_details',limit=2500)
    events,_=_fetch('pc_events',limit=2500)
    def matches(r,keys):return rx.search(' '.join(_clean(r.get(k)) for k in keys)) is not None
    facilities=[r for r in assets if matches(r,['name','asset_type','subtype'])]
    firms=[r for r in companies if matches(r,['name','description','sector','industry'])]
    developments=[r for r in events if matches(r,['title','description','event_type'])]
    buildouts=[r for r in projects if matches(r,['project_type','scope_description','project_stage'])]
    metrics=st.columns(4)
    for col,title,rows in zip(metrics,['Relevant facilities','Companies','Recorded developments','Related projects'],[facilities,firms,developments,buildouts]):
        col.metric(title,len(rows))
    st.caption('These are text-matched discovery counts, not verified commodity-flow volumes or global inventory totals.')
    tab1,tab2,tab3,tab4=st.tabs(['Facilities & capacity','Companies','Developments','Projects & investment'])
    with tab1:
        _table(facilities[:100],['name','asset_type','subtype','country','capacity','capacity_unit','operator_entity_id'],key='com_fac')
        coords=[]
        for r in facilities:
            try:
                lat,lon=float(r['latitude']),float(r['longitude'])
                if -90<=lat<=90 and -180<=lon<=180:coords.append({'lat':lat,'lon':lon,'Name':r.get('name')})
            except (TypeError,ValueError,KeyError):pass
        if coords:st.map(pd.DataFrame(coords),latitude='lat',longitude='lon',use_container_width=True)
    with tab2:_table(firms[:100],['name','country','sector','industry'],key='com_firms')
    with tab3:_table(sorted(developments,key=lambda r:_clean(r.get('start_date')),reverse=True)[:70],['start_date','title','event_type','country','description'],key='com_events')
    with tab4:_table(buildouts[:80],['project_type','project_stage','estimated_cost','currency','scope_description','source_url'],key='com_projects')
    _context_search('commodities')
    _source_note()

def markets():
    st.markdown('### Freight, capacity and transport markets')
    # The metrics schema varies: inspect actual columns; never treat an arbitrary
    # metric value as a freight price or combine incompatible units.
    port_metrics,e1=_fetch('pc_port_metrics',limit=3000)
    services,e2=_fetch('pc_transport_services',limit=2500)
    events,_=_fetch('pc_events',limit=1800)
    m=st.columns(3)
    m[0].metric('Port indicator records',len(port_metrics))
    m[1].metric('Transport service records',len(services))
    m[2].metric('Recent developments',len(events))
    st.caption('Counts show the records returned by the current connection, not live freight market prices.')
    tabs=st.tabs(['Market indicators','Services & routes','Capacity & infrastructure','Developments'])
    with tabs[0]:
        st.subheader('Reported indicators')
        _table(port_metrics[:150],['observed_date','metric_name','metric_value','metric_unit','asset_id','period_start','period_end','source_url'],
               label='No structured port metrics available to this dashboard.',key='freight_metrics')
        st.info('Freight-rate series require verified rate observations, including lane, vessel/transport class, currency, unit, observation time and source. The application will not invent spot rates.')
    with tabs[1]:
        st.subheader('Transport services')
        _table(services[:130],['service_name','name','mode','operator_entity_id','origin_asset_id','destination_asset_id','valid_from','valid_to','status'],
               label='No accessible service records.',key='freight_services')
    with tabs[2]:
        st.subheader('Infrastructure capacity')
        assets,_=_fetch('pc_assets',limit=2500)
        capacity=[r for r in assets if r.get('capacity') is not None or r.get('capacity_value') is not None]
        _table(capacity[:120],['name','asset_type','country','capacity','capacity_value','capacity_unit','unit'],key='freight_capacity')
    with tabs[3]:
        sorted_events=sorted(events,key=lambda r:_clean(r.get('start_date')),reverse=True)
        _table(sorted_events[:60],['start_date','title','event_type','description'],key='freight_events')
    _context_search('markets')
    _source_note()

def render(market: str):
    if market not in APP:raise ValueError(f'Unknown dashboard: {market}')
    _header(market)
    if _db() is None:
        st.warning('The shared Supabase database connection is unavailable. Configure the existing pc_db client and Streamlit secrets before deploying.')
        return
    # Specialist customers see the product, not a database inspection mode.
    {'capital':capital,'commodities':commodities,'markets':markets}[market]()
