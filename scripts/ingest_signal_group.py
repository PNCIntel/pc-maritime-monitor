#!/usr/bin/env python3
"""Research/ingest The Signal Group public Weekly Market Monitor archive into staging market tables.

Design rules:
- Public pages only; no paywall/authentication bypass.
- Store attribution + normalized facts, not copies of full articles.
- All observations default to pending / not client-visible.
- Optional OpenAI extraction converts accessible page text into structured observations.
- Analysts approve data in P&C Power Admin before clients see it.

Examples:
  python scripts/ingest_signal_group.py --year 2026 --families dry,tanker --weeks 3-36
  python scripts/ingest_signal_group.py --year 2026 --archive-only --max-pages 10
"""
from __future__ import annotations
import argparse, hashlib, json, os, re, sys, time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'shared'))
from pc_db import client

ARCHIVE='https://www.thesignalgroup.com/weekly-market-monitor'
UA='PowerAndCorridors-Research/1.0 (+https://www.powerncorridors.com/)'


def clean_text(s):
    return re.sub(r'\s+',' ',s or '').strip()


def fetch(url,timeout=20):
    r=requests.get(url,headers={'User-Agent':UA,'Accept':'text/html,application/xhtml+xml'},timeout=timeout)
    if r.status_code!=200: return None
    if 'text/html' not in r.headers.get('content-type',''): return None
    return r.text


def parse_page(url,html):
    soup=BeautifulSoup(html,'html.parser')
    for tag in soup(['script','style','noscript','svg']): tag.decompose()
    title=clean_text((soup.find('h1') or soup.title).get_text(' ',strip=True) if (soup.find('h1') or soup.title) else '')
    text=clean_text(soup.get_text(' ',strip=True))
    # Avoid persisting article text; keep enough in-memory for extraction only.
    date=None
    m=re.search(r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+20\d{2}\b',text)
    if m:
        try: date=datetime.strptime(m.group(0),'%B %d, %Y').date().isoformat()
        except Exception: pass
    wm=re.search(r'Week\s+(\d{1,2})',title,re.I)
    week=int(wm.group(1)) if wm else None
    family='TANKER' if 'tanker' in title.lower() else ('DRY_BULK' if 'dry' in title.lower() else 'COMMODITY_RADAR')
    return {'url':url,'title':title,'report_date':date,'week_number':week,'family':family,'text':text[:50000]}


def archive_links(html):
    soup=BeautifulSoup(html,'html.parser')
    out=set()
    for a in soup.find_all('a',href=True):
        href=urljoin(ARCHIVE,a['href'])
        if '/weekly-market-monitor/' in href and href.rstrip('/')!=ARCHIVE.rstrip('/'):
            out.add(href.split('?')[0])
    return sorted(out)


def candidate_urls(year,families,weeks):
    out=[]
    for w in weeks:
        if 'dry' in families:
            out.append(f'https://www.thesignalgroup.com/weekly-market-monitor/weekly-dry-market-monitor-week-{w:02d}-{year}')
            out.append(f'https://www.thesignalgroup.com/weekly-market-monitor/weekly-dry-market-monitor-week-{w}-{year}')
        if 'tanker' in families:
            out.append(f'https://www.thesignalgroup.com/weekly-market-monitor/weekly-tanker-market-monitor-week-{w:02d}-{year}')
            out.append(f'https://www.thesignalgroup.com/weekly-market-monitor/weekly-tanker-market-monitor-week-{w}-{year}')
    return out


def ai_extract(page):
    key=os.getenv('OPENAI_API_KEY','').strip(); model=os.getenv('OPENAI_MODEL','gpt-5.6').strip()
    if not key: return []
    from openai import OpenAI
    c=OpenAI(api_key=key)
    instructions='''You extract structured shipping-market observations for Power & Corridors Trade.\nReturn ONLY JSON as {"summary":"...","observations":[...]}.\nUse only facts explicitly present in the supplied page text. Never infer chart values that are not stated in text.\nEach observation may use: observation_date, market, vessel_class, route_code, route_description, origin_text, destination_text, commodity, metric_family, metric_name, value_numeric, value_text, unit, currency, change_wow, change_yoy, benchmark, pc_market_signal, pc_direction, pc_driver, confidence, source_excerpt.\nmetric_family must be one of FREIGHT_RATE, MARKET_INDEX, FLEET_SUPPLY, SUPPLY_DEMAND, COMMODITY_FLOW, PORT_CONDITION, ASSET_VALUE, SECURITY_MARKET, MARKET_SIGNAL.\nsource_excerpt must be a short paraphrase/max 180 characters, not a copied passage. If a number/unit is ambiguous, preserve it in value_text and leave value_numeric null.'''
    inp=f"REPORT: {page['title']}\nDATE: {page['report_date']}\nURL: {page['url']}\n\nACCESSIBLE PAGE TEXT:\n{page['text']}"
    r=c.responses.create(model=model,instructions=instructions,input=inp)
    raw=getattr(r,'output_text','') or ''
    raw=re.sub(r'^```(?:json)?\s*|\s*```$','',raw.strip(),flags=re.S)
    try:
        data=json.loads(raw)
        return data if isinstance(data,dict) else {'summary':'','observations':[]}
    except Exception:
        return {'summary':'','observations':[]}


def upsert_report(sb,page,summary=''):
    h=hashlib.sha256(page['text'].encode('utf-8')).hexdigest()
    payload={
      'provider':'The Signal Group','report_family':page['family'],'report_title':page['title'],
      'report_date':page['report_date'],'iso_year':int(page['report_date'][:4]) if page['report_date'] else None,
      'week_number':page['week_number'],'market_scope':page['family'],'source_url':page['url'],
      'source_methodology':'Public Weekly Market Monitor page. Structured values are accepted only when explicitly stated in accessible page text.',
      'content_hash':h,'extracted_summary':(summary or '')[:600],
      'review_status':'pending','client_visible':False,'last_checked_at':datetime.utcnow().isoformat(),
      'metadata':{'ingestion':'signal_group_public_archive'}
    }
    existing=sb.table('pc_market_reports').select('market_report_id,content_hash').eq('source_url',page['url']).limit(1).execute().data or []
    if existing:
        rid=existing[0]['market_report_id']
        sb.table('pc_market_reports').update(payload).eq('market_report_id',rid).execute(); return rid, existing[0].get('content_hash')!=h
    return sb.table('pc_market_reports').insert(payload).execute().data[0]['market_report_id'], True


def normalize_obs(o,rid,page):
    def n(k):
        v=o.get(k)
        if v in ('',None): return None
        return v
    return {
      'market_report_id':rid,'observation_date':n('observation_date') or page['report_date'],
      'market':n('market'),'vessel_class':n('vessel_class'),'route_code':n('route_code'),
      'route_description':n('route_description'),'origin_text':n('origin_text'),'destination_text':n('destination_text'),
      'commodity':n('commodity'),'metric_family':n('metric_family') or 'MARKET_SIGNAL','metric_name':n('metric_name') or 'UNSPECIFIED',
      'value_numeric':n('value_numeric'),'value_text':n('value_text'),'unit':n('unit'),'currency':n('currency'),
      'change_wow':n('change_wow'),'change_yoy':n('change_yoy'),'benchmark':n('benchmark'),
      'pc_market_signal':n('pc_market_signal'),'pc_direction':n('pc_direction'),'pc_driver':n('pc_driver'),
      'confidence':n('confidence') or 'Moderate','source_excerpt':str(n('source_excerpt') or '')[:220],
      'review_status':'pending','client_visible':False,'metadata':{'ai_extracted':True,'provider':'The Signal Group'}
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--year',type=int,default=2026)
    ap.add_argument('--families',default='dry,tanker')
    ap.add_argument('--weeks',default='1-53')
    ap.add_argument('--archive-only',action='store_true')
    ap.add_argument('--max-pages',type=int,default=0)
    ap.add_argument('--sleep',type=float,default=0.4)
    args=ap.parse_args()
    sb=client(service=True)
    if sb is None: raise SystemExit('Configure SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY first.')
    a,b=[int(x) for x in args.weeks.split('-',1)] if '-' in args.weeks else (int(args.weeks),int(args.weeks))
    families={x.strip().lower() for x in args.families.split(',') if x.strip()}
    urls=set()
    ah=fetch(ARCHIVE)
    if ah: urls.update(archive_links(ah))
    if not args.archive_only: urls.update(candidate_urls(args.year,families,range(a,b+1)))
    # Filter obvious families/year without excluding archive-only commodity radars.
    ordered=sorted(urls)
    if args.max_pages: ordered=ordered[:args.max_pages]
    seen_titles=set(); reports=obs_count=0
    for i,url in enumerate(ordered,1):
        html=fetch(url)
        if not html: continue
        page=parse_page(url,html)
        if not page['title'] or 'Weekly Market Monitor' == page['title']: continue
        # Deduplicate 01/1 slug variants by title.
        if page['title'] in seen_titles: continue
        seen_titles.add(page['title'])
        if page['report_date'] and not page['report_date'].startswith(str(args.year)) and not args.archive_only: continue
        if page['family']=='DRY_BULK' and 'dry' not in families: continue
        if page['family']=='TANKER' and 'tanker' not in families: continue
        extracted=ai_extract(page)
        rid,changed=upsert_report(sb,page,extracted.get('summary','') if isinstance(extracted,dict) else '')
        reports+=1
        observations=(extracted.get('observations',[]) if isinstance(extracted,dict) else []) or []
        if changed and observations:
            # Replace prior pending AI observations for this report; approved records are preserved.
            old=sb.table('pc_market_observations').select('market_observation_id,review_status').eq('market_report_id',rid).execute().data or []
            for row in old:
                if row.get('review_status')=='pending': sb.table('pc_market_observations').delete().eq('market_observation_id',row['market_observation_id']).execute()
            payload=[normalize_obs(o,rid,page) for o in observations if isinstance(o,dict)]
            if payload:
                sb.table('pc_market_observations').insert(payload).execute(); obs_count+=len(payload)
        print(f'[{i}/{len(ordered)}] {page["report_date"] or "?"} {page["title"]} -> {len(observations)} observations')
        time.sleep(max(args.sleep,0))
    print(f'Complete: {reports} reports stored/updated; {obs_count} pending observations extracted.')
    if not os.getenv('OPENAI_API_KEY'):
        print('OPENAI_API_KEY not set: reports were indexed, but structured observation extraction was skipped.')

if __name__=='__main__': main()
