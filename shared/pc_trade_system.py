"""Expanded P&C Trade System workspaces over normalized Supabase tables.

Canonical Supabase tables are authoritative.  This module keeps presentation thin and
joins specialization tables back to pc_assets so newly ingested records are immediately
readable in the Streamlit Trade application.
"""
from __future__ import annotations
import pandas as pd
import streamlit as st
from pc_db import client, safe_rows


def _rows(table, columns='*', limit=3000, order=None, filters=None):
    sb = client(service=True)
    return safe_rows(sb, table, columns, limit, filters=filters, order=order) if sb else []


def _df(table, columns='*', limit=3000, order=None, filters=None):
    return pd.DataFrame(_rows(table, columns, limit, order, filters))


def _show(df, height=360):
    if df is None or df.empty:
        st.caption('No normalized records loaded yet.')
    else:
        st.dataframe(df, use_container_width=True, hide_index=True, height=height)


def _asset_index(limit=20000):
    """Canonical asset lookup used to make specialization tables human-readable."""
    assets = _df(
        'pc_assets',
        'asset_id,name,asset_type,subtype,country,region_city,latitude,longitude,status,record_status,metadata',
        limit,
        'name',
    )
    return assets


def _join_assets(df, asset_col='asset_id'):
    if df is None or df.empty or asset_col not in df.columns:
        return df
    assets = _asset_index()
    if assets.empty:
        return df
    rename = {
        'name': 'name',
        'asset_type': 'canonical_asset_type',
        'subtype': 'canonical_subtype',
        'country': 'country',
        'region_city': 'region_city',
        'latitude': 'latitude',
        'longitude': 'longitude',
        'status': 'canonical_status',
        'record_status': 'canonical_record_status',
        'metadata': 'asset_metadata',
    }
    cols = ['asset_id'] + [c for c in rename if c in assets.columns]
    a = assets[cols].rename(columns=rename)
    return df.merge(a, how='left', left_on=asset_col, right_on='asset_id', suffixes=('', '_asset'))


def render_energy_industry():
    st.caption('Refineries, LNG, pipelines, mines, smelters, factories, logistics facilities and the physical connections that turn assets into trade systems.')

    # Canonical specialization table names.  Older builds incorrectly queried
    # pc_trade_energy_assets / pc_trade_industrial_assets.
    energy = _join_assets(_df('pc_energy_assets', '*', 3000))
    industrial = _join_assets(_df('pc_industrial_assets', '*', 3000))
    logistics = _join_assets(_df('pc_logistics_facilities', '*', 3000))
    links = _df('pc_energy_asset_connections', '*', 5000)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric('Energy assets', len(energy))
    c2.metric('Industrial assets', len(industrial))
    c3.metric('Logistics facilities', len(logistics))
    c4.metric('System links', len(links))

    tabs = st.tabs(['Energy infrastructure', 'Industrial assets', 'Logistics / free zones', 'Connections'])
    with tabs[0]:
        if not energy.empty:
            typ = st.selectbox(
                'Energy asset type',
                ['All'] + sorted(x for x in energy.get('energy_asset_type', pd.Series(dtype=str)).dropna().astype(str).unique() if x),
                key='energy_type_filter',
            )
            view = energy if typ == 'All' else energy[energy['energy_asset_type'].astype(str).eq(typ)]
            cols = [c for c in [
                'name','energy_asset_type','country','region_city','capacity_value','capacity_unit',
                'crude_distillation_bpd','operational_status','security_risk','last_incident_date','last_verified'
            ] if c in view.columns]
            _show(view[cols] if cols else view)
        else:
            st.info('No canonical energy specialization records are loaded yet.')
    with tabs[1]:
        cols = [c for c in [
            'name','industrial_asset_type','country','region_city','commodity_or_product','annual_capacity',
            'capacity_unit','annual_production','production_unit','rail_linked','road_linked','pipeline_linked',
            'operational_status','last_verified'
        ] if c in industrial.columns]
        _show(industrial[cols] if cols else industrial)
    with tabs[2]:
        cols = [c for c in [
            'name','facility_type','country','region_city','owner_entity_id','operator_entity_id','area_sqm',
            'rail_connected','customs_bonded','canonical_status'
        ] if c in logistics.columns]
        _show(logistics[cols] if cols else logistics)
    with tabs[3]:
        _show(links)


def render_trade_flows_supply():
    st.caption('Physical origin–destination flows, production, inventories and agricultural/mineral/energy supply series. Every datapoint retains source and methodology provenance.')
    flows = _df('pc_trade_flows', '*', 5000, 'period_end')
    supply = _df('pc_supply_series', '*', 5000, 'period_end')

    # pc_observations currently has no record_status column; selecting it caused the
    # provenance frame to disappear in prior builds.
    obs = _df(
        'pc_observations',
        'observation_id,source_id,source_name,source_url,source_type,retrieved_at,published_at,observation_date,'
        'license_name,redistribution_status,attribution_required,raw_value,derived_value,methodology,confidence,review_status',
        3000,
        'observation_date',
    )

    # Resolve canonical asset names for trade-flow endpoints while preserving IDs in the
    # data model.  This makes records such as Khalifa Port -> EGA Al Taweelah readable.
    if not flows.empty:
        assets = _asset_index()
        if not assets.empty:
            name_map = dict(zip(assets['asset_id'].astype(str), assets['name'].astype(str)))
            if 'origin_asset_id' in flows.columns:
                flows['Origin Asset'] = flows['origin_asset_id'].astype(str).map(name_map).fillna('')
            if 'destination_asset_id' in flows.columns:
                flows['Destination Asset'] = flows['destination_asset_id'].astype(str).map(name_map).fillna('')
        if 'metadata' in flows.columns:
            def _meta_value(v, key):
                return v.get(key, '') if isinstance(v, dict) else ''
            if 'Origin Asset' not in flows.columns:
                flows['Origin Asset'] = ''
            if 'Destination Asset' not in flows.columns:
                flows['Destination Asset'] = ''
            flows['Origin Asset'] = flows.apply(
                lambda r: r.get('Origin Asset') or _meta_value(r.get('metadata'), 'origin_node'), axis=1
            )
            flows['Destination Asset'] = flows.apply(
                lambda r: r.get('Destination Asset') or _meta_value(r.get('metadata'), 'destination_node'), axis=1
            )

    c1, c2, c3 = st.columns(3)
    c1.metric('Trade-flow records', len(flows))
    c2.metric('Supply records', len(supply))
    c3.metric('Provenance records', len(obs))

    tabs = st.tabs(['Physical trade flows', 'Production & supply', 'Provenance'])
    with tabs[0]:
        if not flows.empty:
            q = st.text_input('Filter flows', placeholder='bauxite, Khalifa Port, iron ore, China, Brazil, wheat, UAE...', key='trade_flow_filter')
            view = flows.copy()
            if q:
                blob = view.astype(str).agg(' '.join, axis=1)
                view = view[blob.str.contains(q, case=False, regex=False, na=False)]
            cols = [c for c in [
                'observation_date','period_start','period_end','origin_country','Origin Asset','destination_country',
                'Destination Asset','commodity','hs_code','quantity','quantity_unit','trade_value_usd','transport_mode',
                'corridor_id','confidence','methodology'
            ] if c in view.columns]
            _show(view[cols] if cols else view, 420)
        else:
            st.info('No flow dataset has been loaded yet. The schema is ready for canonical and external trade-flow ingestion jobs.')
    with tabs[1]:
        _show(supply, 420)
    with tabs[2]:
        _show(obs, 420)


def render_country_macro():
    st.caption('Country-level macro, logistics and commodity-dependence indicators for contextualizing trade, infrastructure and investment exposure.')
    macro = _df('pc_macro_indicators', '*', 5000, 'period_end')
    chok = _df('pc_chokepoints', '*', 1500)
    status = _df('pc_chokepoint_status', '*', 3000, 'observation_timestamp')
    c1, c2, c3 = st.columns(3)
    c1.metric('Macro observations', len(macro)); c2.metric('Chokepoints / crossings', len(chok)); c3.metric('Status observations', len(status))
    tabs = st.tabs(['Macro indicators', 'Borders & chokepoints', 'Current status'])
    with tabs[0]:
        if not macro.empty:
            countries = sorted(x for x in macro.get('country', pd.Series(dtype=str)).dropna().astype(str).unique() if x)
            chosen = st.selectbox('Country', ['All'] + countries, key='macro_country') if countries else 'All'
            view = macro if chosen == 'All' else macro[macro['country'].astype(str).eq(chosen)]
            _show(view, 420)
        else:
            st.info('No macro series loaded yet. IMF and World Bank ingestion can populate this layer after migration.')
    with tabs[1]:
        _show(chok, 420)
    with tabs[2]:
        _show(status, 420)


def render_market_instruments():
    st.caption('Canonical commodity, equity, freight, FX and energy benchmarks linked to companies and physical assets.')
    ins = _df('pc_market_instruments', '*', 3000)
    prices = _df('pc_market_prices', '*', 5000, 'observation_timestamp')
    exp = _df('pc_market_exposure_links', '*', 5000)
    c1, c2, c3 = st.columns(3)
    c1.metric('Instruments', len(ins)); c2.metric('Price observations', len(prices)); c3.metric('Exposure links', len(exp))
    tabs = st.tabs(['Instruments', 'Prices', 'Exposure links'])
    with tabs[0]:
        _show(ins, 420)
    with tabs[1]:
        if prices.empty:
            st.caption('No normalized price series loaded yet.')
        else:
            _show(prices, 420)
    with tabs[2]:
        _show(exp, 420)
