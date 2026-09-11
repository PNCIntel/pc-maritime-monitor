#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import sys
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
SHARED=ROOT/'shared'
if str(SHARED) not in sys.path: sys.path.insert(0,str(SHARED))
from pc_db import client


def main():
    sb=client(service=True)
    if sb is None: raise SystemExit('Configure Supabase first.')
    df=pd.read_csv(ROOT/'data_seed'/'market_instruments_seed.csv',dtype=str).fillna('')
    rows=[]
    for _,r in df.iterrows():
        d={k:(str(v).strip() or None) for k,v in r.items()}
        d['attribution_required']=str(r.get('attribution_required','')).lower() in {'1','true','yes','y'}
        rows.append(d)
    sb.table('pc_market_instruments').upsert(rows,on_conflict='market_instrument_id').execute()
    print(f'Upserted {len(rows)} market instruments.')
if __name__=='__main__': main()
