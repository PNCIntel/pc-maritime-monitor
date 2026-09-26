"""Persistent P&C v0.7 bounded worker. Designed for external cron / GitHub Actions.

It NEVER writes pc_events, pc_entities, pc_assets or any other canonical table.
Writes staged proposals, observations and draft analytical assessments only.
"""
import os
import sys
import uuid
from collections import Counter
import hashlib
import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from pc_v07_core import identity_candidates, extract_assessment, source_urls


def client():
 from supabase import create_client
 url=os.environ.get('SUPABASE_URL')
 key=os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
 if not url or not key: raise RuntimeError('SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required')
 return create_client(url,key)


def _chunks(items, n=100):
 for i in range(0,len(items),n): yield items[i:i+n]


def _stage_plan(r, matches):
 table=r['target_table'];p=r['payload'];key=r['source_record_key'];qid=r['queue_id']
 match=matches.get((r['ingestion_job_id'],key),{'status':'UNRESOLVED','id':None,'method':'non-identity domain; duplicate check pending'})
 is_edge=table in {'pc_event_links','pc_relationships','pc_event_corridor_links','pc_corridor_route_references','pc_company_corridor_roles'}
 if is_edge:match={'status':'UNRESOLVED','id':None,'method':'graph endpoints require verification'}
 if table=='pc_events':match={'status':'UNRESOLVED','id':None,'method':'event duplicate check required'}
 if table=='pc_trade_corridors':match={'status':'UNRESOLVED','id':None,'method':'corridor verification required'}
 status='MATCHED' if match['status']=='MATCHED' else 'NEW' if match['status']=='NEW' else 'UNRESOLVED'
 staged={'ingestion_job_id':r['ingestion_job_id'],'target_table':table,'natural_key':r['natural_key'],
    'action':'REVIEW','payload':p,'source_record_key':key,'validation_status':'pending','review_status':'pending',
    'resolution_status':status,'resolved_entity_id':str(match['id']) if status=='MATCHED' and match['id'] else None,
    'resolution_method':match['method'],'resolution_details':{'planner_version':'0.7','queue_id':qid,
      'proposed_canonical_id':match['id'],'source_urls':source_urls(p),
      'requires_dependency_review':is_edge},'confidence':None}
 supplied=p.get('confidence') or (p.get('metadata') or {}).get('extraction_confidence')
 try:
  if supplied is not None and 0<=float(supplied)<=1:staged['confidence']=float(supplied)
 except (TypeError,ValueError):pass
 return staged


def process_batch(sb, rows, worker_id):
 # One batched identity lookup per distinct table and key chunk, not one RPC per row.
 matches={}
 # Keys are scoped by job as the same source_record_key may occur across jobs.
 for job_id in {r['ingestion_job_id'] for r in rows}:
  own=[r for r in rows if r['ingestion_job_id']==job_id]
  matches.update({(job_id,k):v for k,v in identity_candidates(sb,own).items()})
 byjob={}
 for r in rows:byjob.setdefault(r['ingestion_job_id'],[]).append(r)
 counts=Counter()
 for job,group in byjob.items():
  try:
   plans=[_stage_plan(r,matches) for r in group]
   prior=(sb.table('pc_staged_records').select('source_record_key,staged_record_id')
       .eq('ingestion_job_id',job).in_('source_record_key',[r['source_record_key'] for r in group]).execute().data or [])
   existing={r['source_record_key'] for r in prior}
   pending=[p for p in plans if p['source_record_key'] not in existing]
   for chunk in _chunks(pending):sb.table('pc_staged_records').insert(chunk).execute()
   assessments=[a for r in group if (a:=extract_assessment(r)) is not None]
   for chunk in _chunks(assessments):
    sb.table('pc_v07_event_assessments').upsert(chunk,on_conflict='ingestion_job_id,source_record_key,version',ignore_duplicates=True).execute()
   observations=[]
   for r in group:
    urls=source_urls(r['payload'])
    if urls:observations.append({'ingestion_job_id':job,'source_record_key':r['source_record_key'],
     'target_table':r['target_table'],'natural_key':r['natural_key'],'source_url':urls[0],
     'source_snapshot':{'source_urls':urls,'publisher':(r['payload'].get('metadata') or {}).get('publisher')}})
   for chunk in _chunks(observations):
    sb.table('pc_v07_observations').upsert(chunk,on_conflict='ingestion_job_id,source_record_key',ignore_duplicates=True).execute()
   # Persist bounded research requests only for unresolved real-world identities;
   # never spend an AI call for every event or edge.
   scopes=sb.table('pc_ingestion_jobs').select('source_scope').eq('ingestion_job_id',job).limit(1).execute().data or []
   allow_ai=bool(scopes and (scopes[0].get('source_scope') or {}).get('ai_research'))
   if allow_ai:
    plans_by_key={p['source_record_key']:p for p in plans}
    tasks={}
    for r in group:
     if r['target_table'] not in {'pc_entities','pc_assets','pc_mobile_assets','pc_trade_corridors'}:continue
     plan=plans_by_key[r['source_record_key']]
     if plan['resolution_status']=='MATCHED':continue
     domain=r['target_table'];subject=r['natural_key'].strip()
     k=hashlib.sha256(f'{domain}|{subject.casefold()}'.encode()).hexdigest()
     tasks[k]={'research_key':k,'ingestion_job_id':job,'target_table':domain,
       'subject':subject,'source_urls':source_urls(r['payload'])}
    if tasks:
     cache=sb.table('pc_v07_research_cache').select('research_key').in_('research_key',list(tasks)).execute().data or []
     hit={c['research_key'] for c in cache}
     for chunk in _chunks([v for k,v in tasks.items() if k not in hit]):
      sb.table('pc_v07_research_tasks').upsert(chunk,on_conflict='research_key',ignore_duplicates=True).execute()
   # A missing sidecar must not be treated as successfully staged.
   sb.table('pc_v07_queue').update({'status':'staged','error_text':None,'lease_owner':None,
      'lease_until':None,'updated_at':datetime.now(timezone.utc).isoformat()}) \
     .eq('ingestion_job_id',job).eq('lease_owner',worker_id) \
     .in_('queue_id',[r['queue_id'] for r in group]).execute()
   counts['staged']+=len(group)
  except Exception as exc:
   # Retry chunk after lease release; already-staged rows are recognized on retry.
   for retry_status,retry_rows in (
     ('failed',[r for r in group if int(r.get('attempts') or 1)>=3]),
     ('queued',[r for r in group if int(r.get('attempts') or 1)<3])):
    if retry_rows:
     sb.table('pc_v07_queue').update({'status':retry_status,'lease_owner':None,'lease_until':None,
       'error_text':str(exc)[:400]}).eq('ingestion_job_id',job).eq('lease_owner',worker_id) \
       .in_('queue_id',[r['queue_id'] for r in retry_rows]).execute()
     counts[retry_status]+=len(retry_rows)
 return counts


def run_research(sb,worker_id,max_tasks=3):
 """Persistent bounded research. Findings are leads, never automatic identity bindings."""
 if os.environ.get('PC_ENABLE_AI_RESEARCH','0')!='1':return 0
 api_key=os.environ.get('OPENAI_API_KEY')
 if not api_key:return 0
 claimed=sb.rpc('pc_v07_claim_research',{'p_worker':worker_id,'p_limit':max_tasks}).execute().data or []
 completed=0
 for item in claimed:
  key=item['research_key']
  try:
   prompt=(f"Research the identity of {item['subject']} as {item['target_table']}. "
     'Search original corporate, registry, port, IMO or government sources first. '
     'Distinguish different companies or ships with the same name and provide full URLs. '
     'Record missing evidence explicitly; do not guess canonical database IDs. '
     f"Starting sources: {json.dumps(item.get('source_urls') or [])}")
   req=urllib.request.Request('https://api.openai.com/v1/responses',
      data=json.dumps({'model':'gpt-4.1-mini','tools':[{'type':'web_search_preview'}],
         'input':prompt,'max_output_tokens':1400}).encode(),
      headers={'Authorization':'Bearer '+api_key,'Content-Type':'application/json'})
   with urllib.request.urlopen(req,timeout=100) as response:
    result=json.load(response)
   findings='\n'.join(c['text'] for out in result.get('output',[])
       for c in out.get('content',[]) if isinstance(c,dict) and c.get('text'))
   if not findings:raise RuntimeError('No usable web research returned')
   evidence=sorted(set(re.findall(r'https?://[^\s)\]<>\"\']+',findings)))[:30]
   sb.table('pc_v07_research_cache').upsert({'research_key':key,'domain':item['target_table'],
     'subject':item['subject'],'findings':{'text':findings,'ingestion_job_id':item['ingestion_job_id']},
     'evidence_urls':evidence,'verified':False,
     'refresh_after':(datetime.now(timezone.utc)+__import__('datetime').timedelta(days=30)).isoformat()}).execute()
   sb.table('pc_v07_research_tasks').update({'status':'completed','lease_owner':None,
     'lease_until':None,'error_text':None}).eq('research_key',key).eq('lease_owner',worker_id).execute()
   completed+=1
  except Exception as exc:
   status='failed' if int(item.get('attempts') or 1)>=3 else 'queued'
   sb.table('pc_v07_research_tasks').update({'status':status,'lease_owner':None,
     'lease_until':None,'error_text':str(exc)[:300]}).eq('research_key',key).eq('lease_owner',worker_id).execute()
 return completed

def update_job_summary(sb,job_id):
 # Job-scoped and bounded by status categories; PostgREST count-only requests.
 status_counts={}
 for status in ('queued','processing','staged','needs_review','failed'):
  response=sb.table('pc_v07_queue').select('queue_id',count='exact',head=True).eq('ingestion_job_id',job_id).eq('status',status).execute()
  status_counts[status]=response.count or 0
 pending=status_counts['queued']+status_counts['processing']
 job_status='failed' if status_counts['failed'] and pending==0 else 'completed' if pending==0 else 'running'
 payload={'status':job_status,'stats':status_counts}
 if pending==0:payload['completed_at']=datetime.now(timezone.utc).isoformat()
 sb.table('pc_ingestion_jobs').update(payload).eq('ingestion_job_id',job_id).execute()
 return status_counts


def run(max_batches=10, batch_size=100):
 sb=client(); worker_id='pc07-'+uuid.uuid4().hex[:16]
 total=Counter(); jobs=set()
 for _ in range(max_batches):
  rows=sb.rpc('pc_v07_claim_queue',{'p_worker':worker_id,'p_limit':batch_size}).execute().data or []
  if not rows:break
  for r in rows:jobs.add(r['ingestion_job_id'])
  try:total.update(process_batch(sb,rows,worker_id))
  except Exception as exc:
   # Lookup outage must not turn identity candidates into new entities.
   print('BATCH LOOKUP ERROR:', type(exc).__name__,file=sys.stderr)
   for r in rows:
    new_status='failed' if int(r.get('attempts') or 1)>=3 else 'queued'
    sb.table('pc_v07_queue').update({'status':new_status,'lease_until':None,'lease_owner':None,
     'error_text':'Identity lookup failed; retry scheduled'}).eq('queue_id',r['queue_id']).eq('lease_owner',worker_id).execute()
   break
 for job in jobs:update_job_summary(sb,job)
 researched=run_research(sb,worker_id,max_tasks=3)
 print('Worker complete:',dict(total),'jobs:',len(jobs),'research_tasks_completed:',researched)
 return total

if __name__=='__main__':
 run(max_batches=int(os.environ.get('PC_MAX_BATCHES','8')),
     batch_size=min(200,int(os.environ.get('PC_BATCH_SIZE','100'))))
