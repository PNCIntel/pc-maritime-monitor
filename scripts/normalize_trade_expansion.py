#!/usr/bin/env python3
"""Normalize existing P&C Excel layers into the expanded Trade schema.

This is intentionally conservative: it maps existing canonical rows where identifiers are
already present and does not invent capacities, operators or ownership. External research
jobs can fill those gaps through staging later.
"""
from __future__ import annotations
from pathlib import Path
import sys, re
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'
SHARED=ROOT/'shared'
if str(SHARED) not in sys.path: sys.path.insert(0,str(SHARED))
from pc_db import client

ENERGY_PAT=re.compile(r'refin|lng|gas processing|oil field|gas field|oil pipeline|gas pipeline|petrochem|power plant|storage|tank farm|energy terminal',re.I)
INDUSTRIAL_PAT=re.compile(r'mine|smelter|steel|cement|fertiliz|chemical|factory|manufactur|automotive|semiconductor|battery|grain|silo|food processing|fabrication',re.I)
LOGISTICS_PAT=re.compile(r'warehouse|logistics park|free zone|economic zone|distribution|cold.?chain|real estate|inland logistics',re.I)


def df(book,sheet):
    try: return pd.read_excel(DATA/book,sheet_name=sheet,dtype=str).fillna('')
    except Exception: return pd.DataFrame()

def val(r,*names):
    for n in names:
        if n in r and str(r.get(n,'')).strip(): return str(r.get(n,'')).strip()
    return None

def num(v):
    try:
        s=str(v or '').replace(',','').strip()
        return float(s) if s else None
    except Exception:return None

def b(v):
    s=str(v or '').strip().lower()
    if s in {'yes','y','true','1','connected','available'}: return True
    if s in {'no','n','false','0','none'}: return False
    return None

def upsert_batches(sb,table,rows,on_conflict,chunk=200):
    if not rows: return 0
    for i in range(0,len(rows),chunk):
        sb.table(table).upsert(rows[i:i+chunk],on_conflict=on_conflict).execute()
    return len(rows)


def main():
    sb=client(service=True)
    if sb is None: raise SystemExit('Configure SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY first.')

    stats={}
    assets=df('06_infrastructure.xlsx','Assets')
    energy=[]; industrial=[]
    for _,r in assets.iterrows():
        aid=val(r,'Asset ID'); typ=val(r,'Asset Type') or ''; name=val(r,'Asset') or ''
        if not aid: continue
        hay=f'{typ} {name} {val(r,"Role / Function") or ""}'
        if ENERGY_PAT.search(hay):
            energy.append({'asset_id':aid,'energy_asset_type':typ or 'Energy infrastructure','operational_status':val(r,'Status'),'source_id':val(r,'Source ID'),'metadata':{'legacy_name':name}})
        if INDUSTRIAL_PAT.search(hay):
            industrial.append({'asset_id':aid,'industrial_asset_type':typ or 'Industrial asset','operational_status':val(r,'Status'),'source_id':val(r,'Source ID'),'metadata':{'legacy_name':name}})
    stats['energy_extensions']=upsert_batches(sb,'pc_energy_assets',energy,'asset_id')
    stats['industrial_extensions']=upsert_batches(sb,'pc_industrial_assets',industrial,'asset_id')

    # Logistics real estate and zones map only when an Asset ID already exists.
    logistics=[]
    for book,sheet,idcol,namecol,typecol,ownercol,opcol in [
        ('07_corporate_markets.xlsx','Logistics Real Estate','Asset ID','Asset / Portfolio','Asset Type','Investor / Owner Company IDs','Developer / Manager'),
        ('06_infrastructure.xlsx','Economic Zones','Asset ID','Zone Name','Zone Type','Parent / Owner Company ID','Operator Company ID'),
        ('06_infrastructure.xlsx','Dry Ports','Asset ID','Hub Name','Hub Type','Parent / Investor Company ID','Operator Company ID'),
    ]:
        d=df(book,sheet)
        for _,r in d.iterrows():
            aid=val(r,idcol)
            if not aid: continue
            facilities={
                'asset_id':aid,'facility_type':val(r,typecol) or 'Logistics facility',
                'owner_entity_id':val(r,ownercol) if ownercol in r and str(r.get(ownercol,'')).startswith('COMP_') else None,
                'operator_entity_id':val(r,opcol) if opcol in r and str(r.get(opcol,'')).startswith('COMP_') else None,
                'area_sqm':num(val(r,'Warehouse sqm','Warehouse / Built Logistics Area sqm','Reported Area')),
                'rail_connected':b(val(r,'Rail Access','Rail Connection')),
                'customs_bonded':b(val(r,'Customs / Bonded Status')),
                'source_id':val(r,'Source ID'),'metadata':{'legacy_name':val(r,namecol),'source_sheet':sheet}
            }
            logistics.append({k:v for k,v in facilities.items() if v is not None})
    stats['logistics_facilities']=upsert_batches(sb,'pc_logistics_facilities',logistics,'asset_id')

    # Company listings become market instruments (historical prices remain in pc_market_data).
    listings=df('07_corporate_markets.xlsx','Company Listings')
    instruments=[]; exposures=[]
    for _,r in listings.iterrows():
        cid=val(r,'Company ID'); ticker=val(r,'Ticker'); exch=val(r,'Exchange')
        if not cid or not ticker: continue
        mid=f"EQ_{re.sub(r'[^A-Z0-9]+','_', (exch or 'EX')+'_'+ticker).strip('_').upper()}"
        instruments.append({'market_instrument_id':mid,'name':val(r,'Company') or ticker,'symbol':ticker,'asset_class':'equity','exchange':exch,'currency':val(r,'Currency'),'source_id':val(r,'Source ID'),'metadata':{'company_id':cid}})
        exposures.append({'target_type':'ENTITY','target_id':cid,'market_instrument_id':mid,'exposure_type':'equity','direction':'direct','source_id':val(r,'Source ID')})
    stats['market_instruments']=upsert_batches(sb,'pc_market_instruments',instruments,'market_instrument_id')
    stats['market_exposure_links']=upsert_batches(sb,'pc_market_exposure_links',exposures,'target_type,target_id,market_instrument_id,exposure_type')

    # Rail networks become first-class transport routes.
    rail=df('03_rail.xlsx','Rail Networks')
    routes=[]
    for _,r in rail.iterrows():
        rid=val(r,'Rail Network ID')
        if not rid: continue
        countries=[x.strip() for x in re.split(r'[,;/|]',val(r,'Countries / Jurisdictions') or '') if x.strip()]
        freight=[x.strip() for x in re.split(r'[,;/|]',val(r,'Primary Cargo / Role') or '') if x.strip()]
        routes.append({'route_id':rid,'route_name':val(r,'Network / Corridor') or rid,'mode':'rail','operator_entity_id':val(r,'Lead Operator Company ID'),'origin_type':'TEXT','origin_id':val(r,'Start Node'),'destination_type':'TEXT','destination_id':val(r,'End Node'),'countries':countries or None,'gauge':val(r,'Gauge'),'electrification':val(r,'Electrification / Signalling'),'freight_types':freight or None,'current_status':val(r,'Status'),'source_id':val(r,'Source ID'),'metadata':{'length_scale':val(r,'Length / Scale'),'notes':val(r,'Notes')}})
    stats['transport_routes']=upsert_batches(sb,'pc_transport_routes',routes,'route_id')

    print('Trade expansion normalization complete:')
    for k,v in stats.items(): print(f'  {k}: {v}')

if __name__=='__main__': main()
