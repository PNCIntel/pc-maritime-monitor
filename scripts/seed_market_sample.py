#!/usr/bin/env python3
"""Seed the first attributed P&C market observations from the included Signal Group sample.

All rows remain pending/non-client-visible until approved in P&C Power Admin.
Run after sql/008_market_intelligence.sql.
"""
from __future__ import annotations
import csv, os, sys
from pathlib import Path
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'shared'))
from pc_db import client

SEED=ROOT/'data_seed'/'signal_group_2026_seed.csv'


def blank(v):
    return None if v is None or str(v).strip()=='' else str(v).strip()

def num(v):
    v=blank(v)
    if v is None: return None
    try: return float(v)
    except Exception: return None

def integer(v):
    v=blank(v)
    if v is None: return None
    try: return int(float(v))
    except Exception: return None


def main():
    sb=client(service=True)
    if sb is None:
        raise SystemExit('Configure SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY first.')
    rows=list(csv.DictReader(SEED.open(encoding='utf-8-sig')))
    report_cache={}
    inserted=0
    for r in rows:
        url=r['source_url'].strip()
        if url not in report_cache:
            existing=(sb.table('pc_market_reports').select('market_report_id').eq('source_url',url).limit(1).execute().data or [])
            if existing:
                rid=existing[0]['market_report_id']
            else:
                payload={
                    'provider':r['provider'], 'report_family':r['report_family'],
                    'report_title':r['report_title'], 'report_date':blank(r['report_date']),
                    'iso_year':integer((r['report_date'] or '')[:4]), 'week_number':integer(r['week_number']),
                    'market_scope':r['market'] or None, 'source_url':url,
                    'source_methodology':'Public Weekly Market Monitor page text; only values explicitly stated in accessible page text are seeded.',
                    'review_status':'pending','client_visible':False,
                    'metadata':{'seed':'signal_group_2026_seed.csv'}
                }
                rid=sb.table('pc_market_reports').insert(payload).execute().data[0]['market_report_id']
            report_cache[url]=rid
        rid=report_cache[url]
        # Avoid duplicate seed observations by report + date + metric + route/vessel class.
        q=(sb.table('pc_market_observations').select('market_observation_id')
           .eq('market_report_id',rid).eq('metric_name',r['metric_name']))
        if blank(r['observation_date']): q=q.eq('observation_date',r['observation_date'])
        if blank(r['route_code']): q=q.eq('route_code',r['route_code'])
        existing=q.limit(10).execute().data or []
        same=False
        for e in existing:
            # metric/date/route is sufficiently deterministic for this seed.
            same=True; break
        if same: continue
        payload={
            'market_report_id':rid,'observation_date':blank(r['observation_date']),
            'market':blank(r['market']),'vessel_class':blank(r['vessel_class']),
            'route_code':blank(r['route_code']),'route_description':blank(r['route_description']),
            'origin_text':blank(r['origin_text']),'destination_text':blank(r['destination_text']),
            'commodity':blank(r['commodity']),'metric_family':r['metric_family'],'metric_name':r['metric_name'],
            'value_numeric':num(r['value_numeric']),'value_text':blank(r['value_text']),
            'unit':blank(r['unit']),'currency':blank(r['currency']),
            'change_wow':num(r['change_wow']),'change_yoy':num(r['change_yoy']),
            'benchmark':blank(r['benchmark']),'pc_market_signal':blank(r['pc_market_signal']),
            'pc_direction':blank(r['pc_direction']),'pc_driver':blank(r['pc_driver']),
            'confidence':blank(r['confidence']),'source_excerpt':(r['source_excerpt'] or '')[:220],
            'review_status':'pending','client_visible':False,
            'metadata':{'seed':'signal_group_2026_seed.csv'}
        }
        sb.table('pc_market_observations').insert(payload).execute(); inserted+=1
    print(f'Seed complete: {len(report_cache)} reports, {inserted} new observations. Review/approve in pc-power-admin.py.')

if __name__=='__main__': main()
