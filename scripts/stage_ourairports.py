#!/usr/bin/env python3
"""Stage OurAirports airport records for canonical review.
Does not write directly to pc_assets. Large/medium airports are default to avoid loading every local airfield.
"""
from __future__ import annotations
from pathlib import Path
import argparse, sys, re, requests, io
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]; SHARED=ROOT/'shared'
if str(SHARED) not in sys.path: sys.path.insert(0,str(SHARED))
from pc_db import client
URL='https://davidmegginson.github.io/ourairports-data/airports.csv'

def safeid(s): return re.sub(r'[^A-Z0-9]+','_',str(s).upper()).strip('_')

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--types',default='large_airport,medium_airport'); ap.add_argument('--country',default=''); args=ap.parse_args()
    sb=client(service=True)
    if sb is None: raise SystemExit('Configure Supabase first.')
    r=requests.get(URL,timeout=60); r.raise_for_status(); df=pd.read_csv(io.BytesIO(r.content)).fillna('')
    types={x.strip() for x in args.types.split(',') if x.strip()}; df=df[df['type'].isin(types)]
    if args.country: df=df[df['iso_country'].astype(str).str.upper().eq(args.country.upper())]
    job=sb.table('pc_ingestion_jobs').insert({'job_type':'OPEN_DATA_STAGE','title':'OurAirports airport seed','query_text':f'types={args.types}; country={args.country or "all"}','status':'running','source_scope':{'provider':'OurAirports','url':URL}}).execute().data[0]
    rows=[]
    for _,x in df.iterrows():
        ident=str(x.get('ident') or x.get('gps_code') or x.get('iata_code') or x.get('id'))
        aid='AIRPORT_'+safeid(ident)
        payload={'asset_id':aid,'name':x.get('name'),'asset_type':'Airport','subtype':x.get('type'),'country':x.get('iso_country'),'region_city':x.get('municipality'),'latitude':float(x['latitude_deg']) if str(x.get('latitude_deg','')).strip() else None,'longitude':float(x['longitude_deg']) if str(x.get('longitude_deg','')).strip() else None,'status':'Active' if str(x.get('scheduled_service','')).lower()=='yes' else None,'record_status':'provisional','data_quality':'medium','source_id':'SRC_OPEN_OURAIRPORTS','metadata':{'ident':ident,'iata_code':x.get('iata_code'),'gps_code':x.get('gps_code'),'home_link':x.get('home_link'),'wikipedia_link':x.get('wikipedia_link')}}
        rows.append({'ingestion_job_id':job['ingestion_job_id'],'target_table':'pc_assets','natural_key':aid,'action':'REVIEW','payload':payload,'confidence':0.95,'validation_status':'pending','review_status':'pending','source_id':'SRC_OPEN_OURAIRPORTS'})
    for i in range(0,len(rows),250): sb.table('pc_staged_records').insert(rows[i:i+250]).execute()
    sb.table('pc_ingestion_jobs').update({'status':'completed','stats':{'rows':len(rows)}}).eq('ingestion_job_id',job['ingestion_job_id']).execute()
    print(f'Staged {len(rows)} airport records for review.')
if __name__=='__main__': main()
