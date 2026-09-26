"""Source-faithful, multimodal descriptions and source observations for P&C Trade.

Never invents analysis, ownership, sanctions designations, corridor effects or data.
Produces private REVIEW/DRAFT sidecars, not canonical publications.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from typing import Any

DOMAIN = {
    'pc_events':'event', 'pc_entities':'company_or_organization',
    'pc_assets':'infrastructure', 'pc_mobile_assets':'mobile_asset',
    'pc_trade_corridors':'corridor', 'pc_transport_routes':'route',
    'pc_transport_services':'transport_service'
}
IDENTIFIER = {
    'pc_events':'event_id', 'pc_entities':'entity_id', 'pc_assets':'asset_id',
    'pc_mobile_assets':'mobile_asset_id', 'pc_trade_corridors':'corridor_key',
    'pc_transport_routes':'route_id', 'pc_transport_services':'transport_service_id'
}
FIELD_ALIASES = {
    'description': ('what_happened','event_summary','description','summary', 'company_summary',
                    'asset_description','route_description','corridor_description'),
    'what_it_means': ('what_it_means','why_it_matters','significance'),
    'operational_impact': ('operational_impact','operational_implications'),
    'commercial_implications': ('commercial_implications','business_implications','commercial_impact','business_impact'),
    'pc_assessment': ('pc_assessment','assessment'),
    'monitoring_indicators': ('monitoring_indicators','what_to_monitor','monitoring'),
    'research_gaps': ('research_gaps','unverified_facts','verification_needed')
}

def _first(*layers, names):
    for layer in layers:
        if isinstance(layer, dict):
            for name in names:
                value = layer.get(name)
                if value is not None and value != '' and value != []:
                    return value
    return None

def _string(value):
    if value is None: return None
    if isinstance(value,str): return value.strip() or None
    if isinstance(value,(list,dict)): return json.dumps(value,ensure_ascii=False)
    return str(value)

def _list(value):
    if isinstance(value,list): return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value,str): return [s.strip() for s in value.replace('\n',';').split(';') if s.strip()]
    return []

def _source_list(payload):
    meta=payload.get('metadata') if isinstance(payload.get('metadata'),dict) else {}
    raw=meta.get('research_sources') if isinstance(meta.get('research_sources'),list) else []
    for k in ('source_url','article_url'):
        if payload.get(k):raw=[*raw,{'url':payload[k]}]
        if meta.get(k):raw=[*raw,{'url':meta[k]}]
    result=[];seen=set()
    for item in raw:
        obj={'url':item} if isinstance(item,str) else item if isinstance(item,dict) else {}
        url=obj.get('url')
        if not isinstance(url,str) or not url.startswith(('https://','http://')) or url in seen: continue
        seen.add(url)
        result.append({'url':url,'role':obj.get('role','supporting'),
            'publisher':obj.get('publisher') or meta.get('publisher'),
            'published_at':obj.get('published_at') or meta.get('published_at'),
            'headline':obj.get('headline') or obj.get('title')})
    return result

def extract_content(row:dict[str,Any], resolution:dict|None=None)->dict|None:
    """Make a description/analysis proposal for any first-class Trade object."""
    table=row.get('target_table') or row.get('table')
    if table not in DOMAIN:return None
    p=row.get('payload') or {}
    if not isinstance(p,dict):return None
    m=p.get('metadata') if isinstance(p.get('metadata'),dict) else {}
    a=m.get('analysis') if isinstance(m.get('analysis'),dict) else {}
    layers=(p,a,m)
    values={name:_first(*layers,names=aliases) for name,aliases in FIELD_ALIASES.items()}
    if not values.get('description') and table=='pc_events':
        values['description']=p.get('title') # title only fallback: label, not a claimed summary
    if not any(values.get(field) for field in ('description','what_it_means','operational_impact','commercial_implications','pc_assessment')):
        return None
    sources=_source_list(p)
    target_id=p.get(IDENTIFIER[table])
    resolution=resolution or {}
    # A matched canonical ID is only advisory; remains unpublished and requires review.
    canonical_id=str(resolution['id']) if resolution.get('status')=='MATCHED' and resolution.get('id') else None
    return {
        'ingestion_job_id':row['ingestion_job_id'],
        'source_record_key':row['source_record_key'],
        'target_table':table,
        'target_key':str(target_id or row.get('natural_key') or '').strip(),
        'canonical_id':canonical_id,
        'title':str(p.get('title') or p.get('name') or p.get('corridor_name') or p.get('route_name') or row.get('natural_key') or '').strip(),
        'description':_string(values['description']),
        'what_it_means':_string(values['what_it_means']),
        'operational_impact':_string(values['operational_impact']),
        'commercial_implications':_string(values['commercial_implications']),
        'pc_assessment':_string(values['pc_assessment']),
        'monitoring_indicators':_list(values['monitoring_indicators']),
        'research_gaps':_list(values['research_gaps']),
        'source_evidence':sources,
        'editorial_status':'draft',
        'version':1,
        'text_origin':'source_supplied',
    }

def extract_news(row:dict[str,Any])->list[dict]:
    """Retain EVERY supplied source URL, never merge news articles into fictional incidents."""
    p=row.get('payload') or {}
    if not isinstance(p,dict):return []
    meta=p.get('metadata') if isinstance(p.get('metadata'),dict) else {}
    table=row.get('target_table') or row.get('table')
    out=[]
    for source in _source_list(p):
        url=source['url']
        out.append({
            'ingestion_job_id':row['ingestion_job_id'],
            'source_record_key':row['source_record_key'],
            'source_hash':hashlib.sha256(url.encode('utf-8')).hexdigest(),
            'source_url':url,
            'publisher':source.get('publisher'),
            'headline':source.get('headline') or (meta.get('source_title') if meta.get('source_url')==url else None),
            'published_at':source.get('published_at') if isinstance(source.get('published_at'),str) else None,
            'target_table':table,
            'target_key':str(p.get(IDENTIFIER.get(table,'')) or row.get('natural_key') or ''),
            'source_role':source.get('role') or 'supporting',
        })
    return out
