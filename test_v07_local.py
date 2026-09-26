"""Run: python test_v07_local.py (no credentials/network needed)."""
import io,sys,json,time,types
from pathlib import Path
from collections import Counter
sys.path.insert(0,str(Path(__file__).parent))
sys.modules['streamlit']=types.SimpleNamespace()  # import parser without starting a UI
from pc_v07_core import normalize_rows, identity_candidates, extract_assessment
from pc_v07_admin_panel import load_structured_file
from pc_bulk_worker import process_batch

class Response:
 def __init__(self, data=None,count=0):self.data=data or [];self.count=count
class Query:
 def __init__(self,sb,table):self.sb=sb;self.table=table;self.filters=[];self.writing=None;self.data=None;self.fields='*'
 def select(self,cols,**kw):self.fields=cols;self.count_mode=kw.get('count');return self
 def eq(self,c,v):self.filters.append((c,'eq',v));return self
 def in_(self,c,v):self.filters.append((c,'in',v));return self
 def contains(self,c,v):self.filters.append((c,'contains',v));return self
 def limit(self,n):return self
 def order(self,*a,**kw):return self
 def range(self,*a):return self
 def insert(self,rows):self.writing='insert';self.data=rows if isinstance(rows,list) else [rows];return self
 def upsert(self,rows,**kw):self.writing='upsert';self.data=rows if isinstance(rows,list) else [rows];self.ignore=kw.get('ignore_duplicates',False);return self
 def update(self,val):self.writing='update';self.data=val;return self
 def _filter(self,rows):
  for col,op,val in self.filters:
   if op=='eq':rows=[r for r in rows if r.get(col)==val]
   if op=='in':rows=[r for r in rows if r.get(col) in val]
   if op=='contains':rows=[r for r in rows if all((r.get(col) or {}).get(k)==v for k,v in val.items())]
  return rows
 def execute(self):
  self.sb.calls[self.table+':'+(self.writing or 'select')]+=1
  dataset=self.sb.tables.setdefault(self.table,[])
  if self.writing=='insert':
   for r in self.data:
    row=r.copy()
    if self.table=='pc_staged_records':row['staged_record_id']='s-'+str(len(dataset)+1)
    dataset.append(row)
   return Response(self.data)
  if self.writing=='upsert':
   uniq={'pc_v07_event_assessments':['ingestion_job_id','source_record_key'],
         'pc_v07_observations':['ingestion_job_id','source_record_key'],
         'pc_v07_research_tasks':['research_key'],
         'pc_v07_queue':['ingestion_job_id','source_record_key']}.get(self.table,[])
   inserted=[]
   for r in self.data:
    old=next((e for e in dataset if all(e.get(k)==r.get(k) for k in uniq)),None) if uniq else None
    if old and self.ignore:continue
    if old:old.update(r)
    else:dataset.append(r.copy());inserted.append(r)
   return Response(inserted)
  if self.writing=='update':
   for r in self._filter(dataset):r.update(self.data)
   return Response([])
  result=self._filter(dataset)
  return Response([{k:r.get(k) for k in self.fields.split(',')} for r in result] if self.fields!='*' else result,len(result))
class FakeSB:
 def __init__(self):self.tables={};self.calls=Counter()
 def table(self,n):return Query(self,n)
class Uploaded:
 def __init__(self,path):self.name=Path(path).name;self.blob=Path(path).read_bytes()
 def getvalue(self):return self.blob

root=Path(__file__).parent
# Source workbook contains 28 events, 70 links, and 28 editorial analysis rows.
workbook='/mnt/data/PC_ANALYTICAL_MULTIMODAL_MASTER_28_EVENTS_20260925(3).xlsx'
parsed=load_structured_file(Uploaded(workbook))
counts=Counter(r['table'] for r in parsed)
assert counts['pc_events']==28,counts
assert counts['pc_event_links']==70,counts
sample=next(r for r in parsed if r['table']=='pc_events')
assert 'why_it_matters' in sample['payload']['metadata']
assert 'commercial_implications' in sample['payload']['metadata']
print('WORKBOOK:',dict(counts),'analysis metadata retained: PASS')

package=json.loads(Path('/mnt/data/pc_staging_proposals (1).json').read_text())
assert len(package)==229
start=time.perf_counter();queue=normalize_rows(package);duration=time.perf_counter()-start
assert len(queue)==229
print('PACKAGE:',len(queue),'normalized in',round(duration,4),'sec')
sb=FakeSB()
sb.tables['pc_entities']=[{'entity_id':'ENTITY_EXISTING','name':'22 Plus Invest Limited'}]
sb.tables['pc_ingestion_jobs']=[{'ingestion_job_id':'test-job','source_scope':{'ai_research':False}}]
rows=[dict(r,ingestion_job_id='test-job',queue_id=i+1,attempts=1,lease_owner='local') for i,r in enumerate(queue)]
sb.tables['pc_v07_queue']=[{'queue_id':r['queue_id'],'ingestion_job_id':'test-job','lease_owner':'local','status':'processing'} for r in rows]
started=time.perf_counter();summary=process_batch(sb,rows,'local');secs=time.perf_counter()-started
assert summary['staged']==229,summary
assert len(sb.tables['pc_staged_records'])==229
assert len(sb.tables['pc_v07_event_assessments'])==60
assert len([r for r in sb.tables['pc_staged_records'] if r['target_table']=='pc_event_links'])==70
assert not any(t in sb.calls for t in ['pc_events:insert','pc_entities:insert','pc_assets:insert'])
assert sb.tables['pc_v07_event_assessments'][0]['assessment_status']=='draft'
print('MOCK WORKER:',dict(summary),'event assessment drafts:',len(sb.tables['pc_v07_event_assessments']),
 'event links:',70,'duration:',round(secs,3),'sec')
print('MOCK DB CALLS:',dict(sb.calls))
# A retry recognizes staged rows, without appending duplicates.
again=process_batch(sb,rows,'local')
assert len(sb.tables['pc_staged_records'])==229
assert len(sb.tables['pc_v07_event_assessments'])==60
print('RETRY: no duplicate stage rows or analyses: PASS')
large=[{'table':'pc_mobile_assets','natural_key':str(i),'payload':{'name':'TEST VESSEL '+str(i),'imo':str(9000000+i)}} for i in range(10000)]
start=time.perf_counter();parsed10k=normalize_rows(large);duration=time.perf_counter()-start
assert len(parsed10k)==10000
print('TEN THOUSAND ROW PREP:',round(duration,3),'seconds (memory only)')
