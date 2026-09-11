#!/usr/bin/env python3
"""Load selected World Bank macro indicators directly into pc_macro_indicators.
Official API values are stored with source attribution. Use --countries all or ISO3 codes.
"""
from __future__ import annotations
from pathlib import Path
import argparse, sys, requests
from datetime import date
ROOT=Path(__file__).resolve().parents[1]; SHARED=ROOT/'shared'
if str(SHARED) not in sys.path: sys.path.insert(0,str(SHARED))
from pc_db import client

DEFAULT_INDICATORS={
    'NY.GDP.MKTP.CD':'GDP (current US$)',
    'NY.GDP.MKTP.KD.ZG':'GDP growth (annual %)',
    'FP.CPI.TOTL.ZG':'Inflation, consumer prices (annual %)',
    'FI.RES.TOTL.CD':'Total reserves (current US$)',
    'NE.TRD.GNFS.ZS':'Trade (% of GDP)',
}

def fetch(country,indicator,start,end):
    url=f'https://api.worldbank.org/v2/country/{country}/indicator/{indicator}'
    r=requests.get(url,params={'format':'json','per_page':20000,'date':f'{start}:{end}'},timeout=45)
    r.raise_for_status(); data=r.json()
    return data[1] if isinstance(data,list) and len(data)>1 and data[1] else []

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--countries',default='ARE;SAU;CHN;USA;GBR;DEU;IND;KEN;ZAF;BRA')
    ap.add_argument('--start',type=int,default=2016); ap.add_argument('--end',type=int,default=date.today().year)
    ap.add_argument('--indicators',default=';'.join(DEFAULT_INDICATORS)); args=ap.parse_args()
    sb=client(service=True)
    if sb is None: raise SystemExit('Configure Supabase first.')
    countries='all' if args.countries.lower()=='all' else args.countries
    rows=[]
    for ind in [x.strip() for x in args.indicators.split(';') if x.strip()]:
        for rec in fetch(countries,ind,args.start,args.end):
            if rec.get('value') is None: continue
            year=str(rec.get('date',''))
            if not year.isdigit(): continue
            rows.append({'country':rec.get('country',{}).get('value'),'indicator_code':ind,'indicator_name':DEFAULT_INDICATORS.get(ind,ind),'observation_date':f'{year}-12-31','period_start':f'{year}-01-01','period_end':f'{year}-12-31','value':rec.get('value'),'source_id':'SRC_OPEN_WB','metadata':{'country_id':rec.get('countryiso3code')}})
    for i in range(0,len(rows),500): sb.table('pc_macro_indicators').insert(rows[i:i+500]).execute()
    print(f'Inserted {len(rows)} World Bank macro observations.')
if __name__=='__main__': main()
