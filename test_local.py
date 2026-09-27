import importlib.util, sys, types
try: import streamlit
except ImportError: sys.modules['streamlit']=types.ModuleType('streamlit')
try: import pandas
except ImportError: sys.modules['pandas']=types.ModuleType('pandas')
spec=importlib.util.spec_from_file_location('v152','pc_v15_bulk_replay.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def row(table,name,**payload):
  return {'target_table':table,'natural_key':name,'payload':{'name':name,**payload},'staged_record_id':name,'ingestion_job_id':'job'}
assert 'incomplete date' in m._validation_issue(row('pc_events','Month-only',start_date='2024-06'))
assert m._validation_issue(row('pc_events','Exact',start_date='2024-06-21')) is None
assert 'invalid date' in m._validation_issue(row('pc_events','Impossible',start_date='2024-02-30'))
for name in ('HPC Hamburg Port Consulting advisory 2026','Port of Hastings 2055 Development Strategy','Australian Rail Freight Sector'):
  assert 'record-type' in m._validation_issue(row('pc_entities',name)),name
assert 'equipment delivery' in m._validation_issue(row('pc_assets','Tecon Rio Grande STS and RTG cranes 2026'))
assert 'redevelopment' in m._validation_issue(row('pc_assets','Port of Quebec Container Terminal Redevelopment'))
assert m._validation_issue(row('pc_mobile_assets','Vindnes',imo='1234567')) is None
# When a batch fails because of one row, isolate it and allow other rows to publish.
class FakeQuery:
 def select(self,*a,**k):return self
 def in_(self,*a):return self
 def execute(self):return types.SimpleNamespace(data=[])
class FakeDB:
 def table(self,*a):return FakeQuery()
fail='bad'
def mock_publish(sb,job,items,reviewer):
 if any(x[0]['staged_record_id']==fail for x in items):raise ValueError('invalid input syntax for type date')
 return [{'published':[x[0]['staged_record_id'] for x in items]}]
m._publish_chunk=mock_publish
ready=[(row('pc_events',name),'create_new',None) for name in ['good-a','bad','good-b']]
results,nfollowers,errors=m._publish_ready(FakeDB(),'job',ready,[],'DCM')
assert nfollowers==0
assert [r['published'] for r in results]==[['good-a'],['good-b']],results
assert len(errors)==1 and errors[0]['Staged record ID']=='bad',errors
print('PASS: 9 validation cases and isolated bulk publication; valid records continue after one invalid date.')
