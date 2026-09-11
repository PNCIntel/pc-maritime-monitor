"""Expanded P&C Trade System workspaces over normalized Supabase tables."""
from __future__ import annotations
import pandas as pd
import streamlit as st
from pc_db import client, safe_rows


def _rows(table,columns='*',limit=3000,order=None,filters=None):
    sb=client(service=True)
    return safe_rows(sb,table,columns,limit,filters=filters,order=order) if sb else []


def _df(table,columns='*',limit=3000,order=None,filters=None):
    return pd.DataFrame(_rows(table,columns,limit,order,filters))


def _show(df,height=360):
    if df is None or df.empty:
        st.caption('No normalized records loaded yet.')
    else:
        st.dataframe(df,use_container_width=True,hide_index=True,height=height)


def render_energy_industry():
    st.caption('Refineries, LNG, pipelines, mines, smelters, factories, logistics facilities and the physical connections that turn assets into trade systems.')
    energy=_df('pc_trade_energy_assets','*',3000)
    industrial=_df('pc_trade_industrial_assets','*',3000)
    logistics=_df('pc_logistics_facilities','*',3000)
    links=_df('pc_energy_asset_connections','*',5000)
    c1,c2,c3,c4=st.columns(4)
    c1.metric('Energy assets',len(energy)); c2.metric('Industrial assets',len(industrial)); c3.metric('Logistics facilities',len(logistics)); c4.metric('System links',len(links))
    tabs=st.tabs(['Energy infrastructure','Industrial assets','Logistics / free zones','Connections'])
    with tabs[0]:
        if not energy.empty:
            typ=st.selectbox('Energy asset type',['All']+sorted(x for x in energy.get('energy_asset_type',pd.Series(dtype=str)).dropna().astype(str).unique() if x),key='energy_type_filter')
            view=energy if typ=='All' else energy[energy['energy_asset_type'].astype(str).eq(typ)]
            cols=[c for c in ['name','energy_asset_type','country','region_city','capacity_value','capacity_unit','crude_distillation_bpd','operational_status','security_risk','last_incident_date','last_verified'] if c in view]
            _show(view[cols] if cols else view)
        else: st.info('Run SQL 009 and normalize_trade_expansion.py to seed the current infrastructure model into this layer.')
    with tabs[1]:
        cols=[c for c in ['name','industrial_asset_type','country','region_city','commodity_or_product','annual_capacity','capacity_unit','annual_production','production_unit','rail_linked','road_linked','pipeline_linked','operational_status'] if c in industrial]
        _show(industrial[cols] if cols else industrial)
    with tabs[2]:
        _show(logistics)
    with tabs[3]:
        _show(links)


def render_trade_flows_supply():
    st.caption('Physical origin–destination flows, production, inventories and agricultural/mineral/energy supply series. Every datapoint retains source and methodology provenance.')
    flows=_df('pc_trade_flows','*',5000,'period_end')
    supply=_df('pc_supply_series','*',5000,'period_end')
    obs=_df('pc_observations','observation_id,source_id,source_name,source_url,source_type,retrieved_at,published_at,observation_date,license_name,redistribution_status,attribution_required,methodology,confidence,review_status,record_status',1000,'observation_date')
    c1,c2,c3=st.columns(3); c1.metric('Trade-flow records',len(flows)); c2.metric('Supply records',len(supply)); c3.metric('Provenance records',len(obs))
    tabs=st.tabs(['Physical trade flows','Production & supply','Provenance'])
    with tabs[0]:
        if not flows.empty:
            q=st.text_input('Filter flows',placeholder='iron ore, China, Brazil, wheat, UAE...',key='trade_flow_filter')
            view=flows
            if q:
                blob=view.astype(str).agg(' '.join,axis=1)
                view=view[blob.str.contains(q,case=False,regex=False,na=False)]
            cols=[c for c in ['period_start','period_end','origin_country','destination_country','commodity','hs_code','quantity','quantity_unit','trade_value_usd','transport_mode','corridor_id','confidence'] if c in view]
            _show(view[cols] if cols else view,420)
        else: st.info('No flow dataset has been loaded yet. The schema is ready for UN Comtrade/WTO/UNCTAD/JODI/FAOSTAT ingestion jobs.')
    with tabs[1]:
        _show(supply,420)
    with tabs[2]:
        _show(obs,420)


def render_country_macro():
    st.caption('Country-level macro, logistics and commodity-dependence indicators for contextualizing trade, infrastructure and investment exposure.')
    macro=_df('pc_macro_indicators','*',5000,'period_end')
    chok=_df('pc_chokepoints','*',1500)
    status=_df('pc_chokepoint_status','*',3000,'observation_timestamp')
    c1,c2,c3=st.columns(3); c1.metric('Macro observations',len(macro)); c2.metric('Chokepoints / crossings',len(chok)); c3.metric('Status observations',len(status))
    tabs=st.tabs(['Macro indicators','Borders & chokepoints','Current status'])
    with tabs[0]:
        if not macro.empty:
            countries=sorted(x for x in macro.get('country',pd.Series(dtype=str)).dropna().astype(str).unique() if x)
            chosen=st.selectbox('Country',['All']+countries,key='macro_country') if countries else 'All'
            view=macro if chosen=='All' else macro[macro['country'].astype(str).eq(chosen)]
            _show(view,420)
        else: st.info('No macro series loaded yet. IMF and World Bank ingestion can populate this layer after migration.')
    with tabs[1]: _show(chok,420)
    with tabs[2]: _show(status,420)


def render_market_instruments():
    st.caption('Canonical commodity, equity, freight, FX and energy benchmarks linked to companies and physical assets.')
    ins=_df('pc_market_instruments','*',3000)
    prices=_df('pc_market_prices','*',5000,'observation_timestamp')
    exp=_df('pc_market_exposure_links','*',5000)
    c1,c2,c3=st.columns(3); c1.metric('Instruments',len(ins)); c2.metric('Price observations',len(prices)); c3.metric('Exposure links',len(exp))
    tabs=st.tabs(['Instruments','Prices','Exposure links'])
    with tabs[0]: _show(ins,420)
    with tabs[1]:
        if prices.empty: st.caption('No normalized price series loaded yet.')
        else:
            _show(prices,420)
    with tabs[2]: _show(exp,420)
