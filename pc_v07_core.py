"""P&C v0.7 bulk queue: imports safely, without any canonical-table writes."""
import hashlib
import json
import math
from copy import deepcopy
from datetime import datetime, timezone

SUPPORTED = frozenset({
 'pc_sources','pc_entities','pc_assets','pc_mobile_assets','pc_events',
 'pc_event_links','pc_relationships','pc_trade_corridors','pc_corridor_nodes',
 'pc_corridor_segments','pc_corridor_route_references','pc_event_corridor_links',
 'pc_transport_routes','pc_transport_services','pc_company_corridor_roles',
})
PK = {'pc_entities':'entity_id','pc_assets':'asset_id','pc_mobile_assets':'mobile_asset_id',
      'pc_events':'event_id','pc_trade_corridors':'corridor_key','pc_transport_routes':'route_id'}


def canonical_json(value):
 return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), default=str)


def source_urls(payload):
 meta = payload.get('metadata') if isinstance(payload.get('metadata'),dict) else {}
 raw = meta.get('research_sources') or []
 result = [x if isinstance(x,str) else x.get('url') for x in raw if isinstance(x,(dict,str))]
 for v in (meta.get('source_url'), payload.get('source_url')):
  if isinstance(v,str): result.append(v)
 return list(dict.fromkeys(x for x in result if isinstance(x,str) and x.startswith(('https://','http://'))))



def json_safe(value):
 """Remove pandas/Excel NaN, dates and numpy scalars before Supabase JSON transport."""
 if value is None:return None
 if str(value) in ('<NA>','NaT','nan'):return None
 if isinstance(value,(float,)) and not math.isfinite(value):return None
 if isinstance(value,(datetime,)):return value.isoformat()
 if hasattr(value,'isoformat') and not isinstance(value,str):
  try:return value.isoformat()
  except (AttributeError,TypeError):pass
 if hasattr(value,'item') and callable(value.item):
  try:return json_safe(value.item())
  except (TypeError,ValueError):pass
 if isinstance(value,dict):return {str(k):json_safe(v) for k,v in value.items()}
 if isinstance(value,(list,tuple)):return [json_safe(x) for x in value]
 if isinstance(value,(bool,int,float,str)):return value
 return str(value)


def normalize_rows(records):
 out=[]
 seen_keys=set()
 for i, r in enumerate(records):
  table=r.get('table') or r.get('target_table')
  if table not in SUPPORTED: raise ValueError(f'Row {i}: unsupported table {table!r}')
  payload=r.get('payload')
  if isinstance(payload,str): payload=json.loads(payload)
  if not isinstance(payload,dict): raise ValueError(f'Row {i}: missing payload')
  payload=json_safe(payload)
  key=str(r.get('natural_key') or payload.get('name') or payload.get('title') or payload.get('corridor_name') or payload.get(PK.get(table,'')) or '').strip()
  if not key: raise ValueError(f'Row {i}: missing natural key')
  if r.get('confidence') is not None:
   if not isinstance(payload.get('metadata'),dict):
    existing_meta=payload.get('metadata')
    try:existing_meta=json.loads(existing_meta) if isinstance(existing_meta,str) else {}
    except (TypeError,ValueError):existing_meta={}
    payload['metadata']=existing_meta if isinstance(existing_meta,dict) else {}
   payload['metadata']['extraction_confidence']=json_safe(r['confidence'])
  original=str(r.get('source_record_key') or f'input:{i}')
  if original in seen_keys:raise ValueError(f'Duplicate source_record_key: {original}; cannot safely retry')
  seen_keys.add(original)
  out.append({'source_record_key':str(original),'target_table':table,'natural_key':key,
              'payload':deepcopy(payload),'source_url':next(iter(source_urls(payload)),None),
              'priority':90 if table in {'pc_entities','pc_assets','pc_mobile_assets'} else 50})
 return out


def enqueue(sb, records, title='P&C universal bulk intake', ai_research=False):
 rows=normalize_rows(records)
 if not rows: raise ValueError('Empty package')
 fingerprint=hashlib.sha256(canonical_json([(r['target_table'],r['natural_key'],r['payload']) for r in rows]).encode()).hexdigest()
 existing=(sb.table('pc_ingestion_jobs').select('ingestion_job_id').contains('source_scope',{'v07_sha256':fingerprint}).limit(2).execute().data or [])
 if len(existing)>1: raise RuntimeError('Duplicate ingestion jobs detected; investigate')
 if existing: job_id=existing[0]['ingestion_job_id']; reused=True
 else:
  inserted=sb.table('pc_ingestion_jobs').insert({
   'job_type':'UNIVERSAL_BATCH_V07','title':title[:180],'status':'queued',
   'source_scope':{'v07_sha256':fingerprint,'workflow':'review_only','ai_research':bool(ai_research)},
   'stats':{'expected_records':len(rows)}
  }).execute().data
  if not inserted: raise RuntimeError('Could not create ingestion job')
  job_id=inserted[0]['ingestion_job_id']; reused=False
 # Stable key + database unique constraint => retry safe; never overwrite prior reviews.
 rows=[{'ingestion_job_id':job_id,**r} for r in rows]
 for i in range(0,len(rows),100):
  sb.table('pc_v07_queue').upsert(rows[i:i+100],on_conflict='ingestion_job_id,source_record_key',ignore_duplicates=True).execute()
 return str(job_id),len(rows),reused


def unique_lookup(sb,table,column,values,select_cols,key_col=None,chunk=70):
 vals=sorted({str(v).strip() for v in values if v is not None and str(v).strip()})
 found={}
 for i in range(0,len(vals),chunk):
  result=sb.table(table).select(select_cols).in_(column, vals[i:i+chunk]).execute().data or []
  for r in result: found.setdefault(str(r[column]).strip().casefold(),[]).append(r)
 return found


def identity_candidates(sb, rows):
 """Bounded database calls. Name alone is REVIEW, never automatic owner/alias merge."""
 result={}
 for table,pk in [('pc_entities','entity_id'),('pc_assets','asset_id'),('pc_mobile_assets','mobile_asset_id')]:
  own=[r for r in rows if r['target_table']==table]
  if not own:continue
  vals=[r['payload'].get('name') for r in own]
  byname=unique_lookup(sb,table,'name',vals, f'{pk},name'+(',imo' if table=='pc_mobile_assets' else ''))
  byimo={}
  if table=='pc_mobile_assets':
   imos=[r['payload'].get('imo') for r in own if str(r['payload'].get('imo') or '').isdigit() and len(str(r['payload']['imo']))==7]
   if imos: byimo=unique_lookup(sb,table,'imo',imos,f'{pk},name,imo')
  for r in own:
   key=r['source_record_key'];p=r['payload']; n=str(p.get('name') or '').casefold()
   imo=str(p.get('imo') or '')
   candidates=byimo.get(imo.casefold(),[]) if table=='pc_mobile_assets' and len(imo)==7 else []
   if len(candidates)==1:
    result[key]={'status':'MATCHED','id':candidates[0][pk],'method':'unique exact IMO'};continue
   if len(candidates)>1:
    result[key]={'status':'UNRESOLVED','id':None,'method':'conflicting duplicate IMO'};continue
   candidates=byname.get(n,[])
   result[key]={'status': 'REVIEW' if candidates else 'NEW',
                'id':candidates[0][pk] if len(candidates)==1 else None,
                'method':'name candidate only' if candidates else 'no exact identifier match'}
   if len(candidates)>1:result[key]['status']='UNRESOLVED';result[key]['method']='multiple exact name matches'
 return result


def extract_assessment(row):
 """Preserve provided analytical fields, never fabricate an AI conclusion."""
 if row['target_table']!='pc_events':return None
 p=row['payload'];m=p.get('metadata') if isinstance(p.get('metadata'),dict) else {}
 a=m.get('analysis') if isinstance(m.get('analysis'),dict) else {}
 def field(*names):
  for n in names:
   val=p.get(n) or a.get(n) or m.get(n)
   if isinstance(val,str) and val.strip():return val.strip()
  return None
 indicators=a.get('monitoring_indicators') or m.get('monitoring_indicators') or []
 if isinstance(indicators,str):indicators=[indicators]
 gaps=a.get('research_gaps') or m.get('research_gaps') or []
 if isinstance(gaps,str):gaps=[gaps]
 return {'ingestion_job_id':row['ingestion_job_id'],'source_record_key':row['source_record_key'],
  'event_id':p.get('event_id'),'event_title':p.get('title') or row['natural_key'],
  'what_happened':field('what_happened','description','event_summary'),
  'what_it_means':field('what_it_means','why_it_matters'),
  'operational_impact':field('operational_impact'), 'commercial_impact':field('commercial_impact','business_implications','commercial_implications'),
  'pc_assessment':field('pc_assessment','assessment'), 'monitoring_indicators':indicators,
  'research_gaps':gaps,'evidence_urls':source_urls(p),'assessment_status':'draft'}
