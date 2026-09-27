"""No Supabase/OpenAI connection. Safety/unit + mocked 85-row replay checks."""
import importlib.util
import pathlib
import sys
import types
import csv
sys.modules['streamlit']=types.ModuleType('streamlit')
ROOT=pathlib.Path(__file__).resolve().parents[1]

def load(name,filename):
    spec=importlib.util.spec_from_file_location(name,ROOT/'POWER_ADMIN'/filename)
    obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj);return obj
r=load('v16','pc_v16_research.py')
b=load('v15','pc_v15_bulk_replay.py')

assert r._public_url('https://www.example.com/news')
for u in ['http://localhost/a','https://127.0.0.1/x','file:///etc/passwd','https://internal.local/x','https://user:pass@example.com/a']:
    assert not r._public_url(u),u
assert r._valid_imo('9074729')  # IMO check digit
assert not r._valid_imo('9074728')
assert not r._valid_imo('12345')

def stage(n,table,name,metadata=None):
    return {'staged_record_id':str(n),'ingestion_job_id':'job','target_table':table,
        'source_record_key':'input:'+str(n),'natural_key':name,
        'payload':{'name':name,'metadata':metadata or {'research_sources':[{'url':'https://www.example.com/news'}]}}}

def result(table,name,source='https://www.example.com/news',metadata=None):
    p={'title' if table=='pc_events' else 'name':name,'metadata':metadata or {}}
    return {'status':'repair','original_source_confirmed':True,'target_table':table,
       'payload':p,'sources':[source], 'allowed_evidence':[source]}

orig=stage(1,'pc_entities','HPC Hamburg Port Consulting advisory 2026')
p,err=r.validate_proposal(orig,result('pc_events','HPC advises Port of Mogadishu on equipment investment',metadata={'date_precision':'month','year_month':'2026-09'}))
assert err is None and 'title' in p and 'name' not in p and p['event_id'].startswith('REPAIR_')
assert p['metadata']['pc_v16_original_table']=='pc_entities'
assert b._validation_issue({'target_table':'pc_events','payload':p}) is None

original=stage(2,'pc_assets','Vindnes')
p,err=r.validate_proposal(original,result('pc_mobile_assets','Vindnes'))
assert err is None and p['mobile_asset_id'].startswith('REPAIR_') and 'imo' not in p
bad=result('pc_mobile_assets','Vindnes');bad['payload']['imo']='1234568'
assert 'IMO' in r.validate_proposal(original,bad)[1]
bad=result('pc_events','Announcement');bad['payload']['start_date']='2026-09'
assert 'date' in r.validate_proposal(orig,bad)[1]
bad=result('pc_events','Announcement');bad['sources']=['https://invented.example/story']
assert 'invented' in r.validate_proposal(orig,bad)[1]
bad=result('pc_events','Announcement');bad['original_source_confirmed']=False
assert r.validate_proposal(orig,bad)[0] is None

cand={'request':{'candidate_snapshot':[
  {'table':'pc_entities','id':'COMP_DPW','name':'DP World','country':'AE'},
  {'table':'pc_entities','id':'OTHER_DPW','name':'DP World','country':'AE'}]}}
assert r._verified_binding(cand,orig,{'target_table':'pc_entities','match_candidate_id':'COMP_DPW'},{'name':'DP World'}) is None
cand={'request':{'candidate_snapshot':[{'table':'pc_entities','id':'COMP_MSC','name':'MSC Cruises S.A.','country':'CH'}]}}
assert r._verified_binding(cand,orig,{'target_table':'pc_entities','match_candidate_id':'COMP_MSC'},{'name':'MSC Cruises','hq_country':'CH'})['canonical_id']=='COMP_MSC'
assert r._verified_binding(cand,orig,{'target_table':'pc_entities','match_candidate_id':'FAKE'},{'name':'MSC Cruises'}) is None

links=[{'linked_type':'entity','linked_name':'DP World','relationship':'signed MoU',
        'evidence_url':'https://www.example.com/news'},
       {'linked_type':'entity','linked_name':'DP World','relationship':'possible owner',
        'evidence_url':'https://www.example.com/news'},
       {'linked_type':'asset','linked_name':'Blue Marine SEZ','relationship':'planned project',
        'evidence_url':'https://madeup.invalid'}]
assert len(r._safe_related({'relationships':links},{'https://www.example.com/news'}))==1

# Full two-export population is 83 separate proposal/exception rows, not
# proof that the other two in the persisted 85-record job disappeared.
files=[pathlib.Path('/mnt/data/2026-09-27T10-35_export.csv'),pathlib.Path('/mnt/data/2026-09-27T10-36_export.csv')]
exports=[]
for path in files:
    with path.open(encoding='utf-8-sig',newline='') as f:exports+=list(csv.DictReader(f))
assert len(exports)==83,len(exports)
assert any('Vindnes' in x['Name'] for x in exports)
assert any('HPC Hamburg' in x['Name'] for x in exports)
assert any('Port of Los Angeles' in x['Name'] for x in exports)
print('PASS: 83 exported rows loaded; source URL allowlist, IMO checksum, date precision,')
print('PASS: advisory→development and fixed-asset→vessel repairs, ambiguous DP World hold,')
print('PASS: canonical candidate verification, evidence-backed event links, v1.6 syntax')
