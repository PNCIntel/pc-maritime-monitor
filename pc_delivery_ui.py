"""Read-only P&C application delivery interface. Live SQL views, not cached copies."""
from __future__ import annotations
import streamlit as st
import pandas as pd

PRODUCT_VIEWS = {
    'trade': 'pc_app_trade_records',
    'intelligence': 'pc_app_security_records',
    'strategic': 'pc_app_strategic_records',
    'sanctions': 'pc_app_sanctions_records',
    'capital': 'pc_app_capital_records',
    'commodities': 'pc_app_commodities_records',
    'markets': 'pc_app_markets_records',
}
SECTIONS = {
 'trade': [('Overview',None),('Companies & Operators','companies'),('Ports & Terminals','ports_terminals'),('Airports & Air Cargo','aviation'),('Rail & Intermodal','rail'),('Road & Distribution','land_logistics'),('Vessels & Fleets','fleets'),('Energy & Industry','industry_energy'),('Other Infrastructure','other_infrastructure'),('Trade Developments','developments')],
 'intelligence': [('Operational Overview',None),('Incidents & Developments','incidents'),('Infrastructure Exposure','infrastructure'),('Organisations','organisations'),('Vessels & Aircraft','exposed_fleets')],
 'strategic': [('Industrial Overview',None),('Industry & Energy','industry'),('Industrial Facilities','facilities'),('Organisations','organisations'),('Fleets & Platforms','platforms'),('Developments','developments')],
 'sanctions': [('Compliance Overview',None),('Entities','entities'),('Vessels','vessels'),('Infrastructure','infrastructure'),('Developments','developments')],
 'capital': [('Investment Overview',None),('Companies','companies'),('Infrastructure Investments','infrastructure'),('Transactions & Developments','transactions_and_news'),('Fleet Investments','fleets')],
 'commodities': [('Resources Overview',None),('Energy & Industry','energy_industry'),('Supply Chain','supply_chain'),('Organisations & Assets','organisations_assets'),('Developments','developments')],
 'markets': [('Market Overview',None),('Transport Networks','transport_network'),('Fleet Supply','fleet_supply'),('Port Capacity','ports_capacity'),('Market Developments','market_developments')],
}

def fetch(db, table, *, section=None, query=None, country=None, limit=250):
    """Separate query errors from legitimately empty results."""
    try:
        req=db.table(table).select('object_type,object_id,name,category,subtype,country,latitude,longitude,section')
        if section: req=req.eq('section',section)
        if country: req=req.eq('country',country)
        if query: req=req.ilike('name','%'+query.replace('%','\\%').replace('_','\\_')+'%')
        return req.limit(limit).execute().data or [], None
    except Exception as exc:
        return [], str(exc)

def sidebar(product):
    """Returns chosen dataset section; caller renders regular app outside this function."""
    choices=SECTIONS[product]
    with st.sidebar:
        st.caption('EXPLORE DATA')
        selection=st.radio('Workspace', [label for label,_ in choices], key='pc_delivery_nav_'+product,
                           label_visibility='collapsed')
    return next(code for label,code in choices if label==selection)

def render(db, product, section, *, heading=True):
    if product not in PRODUCT_VIEWS: raise ValueError('Unsupported product')
    table=PRODUCT_VIEWS[product]
    label=next((label for label,key in SECTIONS[product] if key==section),'Overview')
    if heading: st.subheader(label)
    st.caption('Verified database records where available. Search and classification do not imply ownership, incident exposure or current sanctions status.')
    a,b=st.columns([3,1])
    with a: q=st.text_input('Find a record',key='pc_delivery_q_'+product,placeholder='Company, facility, vessel, location…')
    with b: limit=st.selectbox('Results', [50,150,300,500],index=1,key='pc_delivery_limit_'+product)
    rows,error=fetch(db,table,section=section,query=q or None,limit=limit)
    if error:
        st.error('Data view unavailable. Apply the SQL migration and confirm database permissions.')
        with st.expander('Technical details'): st.code(error)
        return
    if not rows:
        st.info('No matching records in the current published view. This is not proof the underlying database is empty.')
        return
    st.caption(f'{len(rows)} records displayed (up to {limit}; additional results may exist).')
    df=pd.DataFrame(rows)
    names=['name','object_type','category','subtype','country']
    st.dataframe(df[[c for c in names if c in df.columns]].rename(columns={'name':'Name','object_type':'Record type','category':'Activity','subtype':'Category','country':'Country'}),use_container_width=True,hide_index=True)
    options={f"{r['name']} — {r['object_type']} / {r['object_id']}":r for r in rows}
    selected=st.selectbox('Inspect record', ['Choose a record…']+list(options),key='pc_delivery_pick_'+product)
    if selected in options:
        item=options[selected]
        st.markdown(f"**{item['name']}**")
        st.caption(f"Record type: {item['object_type']}")
        if item['object_type'] in ('asset','entity','mobile_asset'):
            _connections(db,item)

def _connections(db,item):
    oid=item['object_id']; typ=item['object_type']
    try:
        links=db.table('pc_delivery_direct_incidents').select('event_id,link_source').eq('object_type',typ).eq('object_id',oid).limit(100).execute().data or []
        st.markdown('**Directly linked incidents**')
        if links: st.dataframe(pd.DataFrame(links),hide_index=True,use_container_width=True)
        else: st.caption('No verified direct event links returned.')
    except Exception as exc: st.warning('Incident link view unavailable: '+str(exc)[:140])
    if typ=='asset':
        try:
            children=db.table('pc_delivery_facility_children').select('child_object_id').eq('parent_object_id',oid).limit(250).execute().data or []
            st.markdown('**Contained facilities**')
            if children: st.dataframe(pd.DataFrame(children),hide_index=True,use_container_width=True)
            else: st.caption('No directly recorded terminal children.')
        except Exception as exc: st.warning('Facility connection view unavailable: '+str(exc)[:140])
