#!/usr/bin/env python3
"""Deployment integrity checks for P&C Trade System App v4.8 / Model v1.12."""
from __future__ import annotations
import csv, re, sys
from pathlib import Path

BASE=Path(__file__).resolve().parent
DATA=BASE/'data'
APP=BASE/'app.py'
errors=[]; notes=[]

def read_root(name):
    with (DATA/name).open('r',encoding='utf-8-sig',newline='') as f:
        return list(csv.DictReader(f))
def nonblank(v): return v is not None and str(v).strip()!=''
def tokens(v,prefix):
    if not nonblank(v): return []
    return re.findall(rf'{re.escape(prefix)}[A-Za-z0-9_\-]+',str(v))

for name in ['app.py','requirements.txt','manifest.json','PC_Trade_System_Intelligence_Model_v1_12_MASTER.xlsx']:
    if not (BASE/name).exists(): errors.append(f'Missing required root file: {name}')
if not DATA.is_dir(): errors.append('Missing data/ directory')

try:
    compile(APP.read_text(encoding='utf-8'),str(APP),'exec'); notes.append('app.py syntax: PASS')
except Exception as exc: errors.append(f'app.py syntax error: {exc}')

app_text=APP.read_text(encoding='utf-8')
referenced=sorted(set(re.findall(r'[A-Za-z0-9_\-]+\.csv',app_text)))
missing_app=[n for n in referenced if not (DATA/n).exists()]
if missing_app: errors.append('Missing app-referenced CSVs: '+', '.join(missing_app))
notes.append(f'app-referenced CSV files: {len(referenced)}; missing: {len(missing_app)}')

all_csv=sorted(DATA.rglob('*.csv'))
root_csv=sorted(DATA.glob('*.csv'))
for path in all_csv:
    try:
        with path.open('r',encoding='utf-8-sig',newline='') as f:
            r=csv.reader(f); header=next(r,None)
            if not header: errors.append(f'CSV has no header: {path.relative_to(BASE)}')
            for _ in r: pass
    except Exception as exc: errors.append(f'CSV parse failure {path.relative_to(BASE)}: {exc}')
notes.append(f'packaged CSV files (recursive): {len(all_csv)}')
notes.append(f'root runtime CSV files: {len(root_csv)}')

companies=read_root('companies.csv'); sources=read_root('sources.csv'); assets=read_root('assets.csv'); people=read_root('people.csv'); vessels=read_root('vessels.csv')
company_ids={r['Company ID'].strip() for r in companies if nonblank(r.get('Company ID'))}
source_ids={r['Source ID'].strip() for r in sources if nonblank(r.get('Source ID'))}
asset_ids={r['Asset ID'].strip() for r in assets if nonblank(r.get('Asset ID'))}
person_ids={r['Person ID'].strip() for r in people if nonblank(r.get('Person ID'))}
vessel_ids={r['Vessel ID'].strip() for r in vessels if nonblank(r.get('Vessel ID'))}

primary={'companies.csv':'Company ID','sources.csv':'Source ID','assets.csv':'Asset ID','people.csv':'Person ID','leadership_roles.csv':'Role ID','relationships.csv':'Relationship ID','fleet_portfolios.csv':'Fleet ID','aircraft.csv':'Aircraft ID','fleet_orders.csv':'Order ID','investments.csv':'Investment ID','strategic_events.csv':'Event ID','logistics_real_estate.csv':'LRE ID','infrastructure_connections.csv':'Connection ID','integrated_logistics_networks.csv':'Network ID'}
for fn,key in primary.items():
    rows=read_root(fn); vals=[str(r.get(key,'')).strip() for r in rows if nonblank(r.get(key))]
    seen=set(); dup=set()
    for x in vals:
        if x in seen: dup.add(x)
        seen.add(x)
    if dup: errors.append(f'Duplicate {key} in {fn}: '+', '.join(sorted(dup)[:10]))

missing_company=set(); missing_source=set(); missing_asset=set(); missing_person=set(); missing_vessel=set()
for path in root_csv:
    with path.open('r',encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
    if not rows: continue
    headers=rows[0].keys()
    for row in rows:
        for h in headers:
            val=row.get(h,'')
            if 'Company ID' in h or 'Company IDs' in h:
                for t in tokens(val,'COMP_'):
                    if t not in company_ids: missing_company.add((path.name,h,t))
            if h in {'Source Entity','Target Entity','Subject Entity ID','Parent Entity ID','Target Entity / Asset ID'}:
                for t in tokens(val,'COMP_'):
                    if t not in company_ids: missing_company.add((path.name,h,t))
                for t in tokens(val,'ASSET'):
                    if t not in asset_ids: missing_asset.add((path.name,t))
            if 'Source ID' in h:
                for t in tokens(val,'SRC_'):
                    if t not in source_ids: missing_source.add((path.name,t))
            if h in {'Asset ID','Source Asset ID'}:
                for t in tokens(val,'ASSET'):
                    if t not in asset_ids: missing_asset.add((path.name,t))
            if h=='Person ID':
                for t in tokens(val,'PERSON_'):
                    if t not in person_ids: missing_person.add((path.name,t))
            if h in {'Vessel ID','Canonical Vessel ID'}:
                for t in tokens(val,'VESSEL_'):
                    if t not in vessel_ids: missing_vessel.add((path.name,t))
if missing_company: errors.append('Missing company references: '+'; '.join(f'{a}:{b}:{c}' for a,b,c in sorted(missing_company)[:20]))
if missing_source: errors.append('Missing source references: '+'; '.join(f'{a}:{b}' for a,b in sorted(missing_source)[:20]))
if missing_asset: errors.append('Missing asset references: '+'; '.join(f'{a}:{b}' for a,b in sorted(missing_asset)[:20]))
if missing_person: errors.append('Missing person references: '+'; '.join(f'{a}:{b}' for a,b in sorted(missing_person)[:20]))
if missing_vessel: errors.append('Missing vessel references: '+'; '.join(f'{a}:{b}' for a,b in sorted(missing_vessel)[:20]))

imos=[r['IMO'].strip() for r in vessels if nonblank(r.get('IMO'))]
seen=set(); dup=set()
for x in imos:
    if x in seen: dup.add(x)
    seen.add(x)
if dup: errors.append('Duplicate nonblank canonical IMO values: '+', '.join(sorted(dup)[:20]))
notes.append(f'canonical vessels: {len(vessels)}; populated IMO: {len(imos)}; unique IMO: {len(set(imos))}')
notes.append(f'companies: {len(companies)}; sources: {len(sources)}; assets: {len(assets)}')

print('P&C DEPLOYMENT VALIDATION'); print('='*28)
for n in notes: print('PASS:',n)
if errors:
    print('\nFAILURES')
    for e in errors: print('FAIL:',e)
    sys.exit(1)
print('\nREFERENCE INTEGRITY: PASS')
