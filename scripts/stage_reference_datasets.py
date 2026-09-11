"""Validate/stage the v3.3 research reference layer for later Supabase ingestion.
Runs without database credentials and never mutates the canonical Excel workbooks.
"""
from pathlib import Path
import json
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
NORMALIZED=ROOT/'external_data'/'normalized'
OUT=ROOT/'staging'
OUT.mkdir(exist_ok=True)

FILES={
    'global_ports':'global_port_reference.csv',
    'port_fuel_2050':'port_fuel_demand_2050.csv',
    'accuracy_stock':'accuracy_ns_stock_data.csv',
}
summary={}
for key,name in FILES.items():
    p=NORMALIZED/name
    if not p.exists():
        summary[key]={'status':'missing','path':str(p.relative_to(ROOT))}
        continue
    df=pd.read_csv(p,low_memory=False)
    summary[key]={
        'status':'ready','path':str(p.relative_to(ROOT)),
        'rows':int(len(df)),'columns':list(df.columns),'bytes':p.stat().st_size
    }

(OUT/'reference_staging_manifest.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps(summary,indent=2))
