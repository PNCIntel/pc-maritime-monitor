#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import os, sys
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
SHARED=ROOT/'shared'
if str(SHARED) not in sys.path: sys.path.insert(0,str(SHARED))
from pc_db import client

CSV_PATH=ROOT/'data_seed'/'open_source_registry.csv'


def clean(v):
    if pd.isna(v): return None
    s=str(v).strip()
    return s or None


def main():
    sb=client(service=True)
    if sb is None:
        raise SystemExit('Configure SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY first.')
    df=pd.read_csv(CSV_PATH,dtype=str).fillna('')
    rows=[]
    for _,r in df.iterrows():
        rows.append({
            'source_id':clean(r['source_id']), 'publisher':clean(r['publisher']), 'source_name':clean(r['source_name']),
            'source_type':clean(r['source_type']), 'coverage':clean(r['coverage']), 'url':clean(r['url']),
            'ingestion_method':clean(r['ingestion_method']), 'license_name':clean(r['license_name']),
            'redistribution_status':clean(r['redistribution_status']),
            'attribution_required':str(r['attribution_required']).lower() in {'1','true','yes','y'},
            'notes':clean(r['notes']), 'active':True,
        })
    for i in range(0,len(rows),100):
        sb.table('pc_sources').upsert(rows[i:i+100],on_conflict='source_id').execute()
    print(f'Upserted {len(rows)} source-registry records.')

if __name__=='__main__': main()
