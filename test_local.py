"""Offline regressions; does not connect to or modify Supabase."""
import sys, types, importlib.util
sys.modules.setdefault('streamlit',types.ModuleType('streamlit'))
spec=importlib.util.spec_from_file_location('bulk','/mnt/data/PC_V15_5_MATCH_FIX/pc_v15_bulk_replay.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
reg={'pc_entities':[
    {'entity_id':'CA_AUTH_LA','name':'City of Los Angeles Harbor Department / Port of Los Angeles','entity_type':'port_authority','hq_country':'US'},
    {'entity_id':'COMP_MSC_CRUISES','name':'MSC Cruises S.A.','entity_type':'cruise_operator'},
    {'entity_id':'COMP_APMT','name':'APM Terminals','entity_type':'ports_logistics_group'},
    {'entity_id':'COMP_DPW','name':'DP World','entity_type':'ports_logistics_group'},
    {'entity_id':'ENTITY_AUTO_D45','name':'DP World','entity_type':'ports_logistics_group'},
    {'entity_id':'OGUN','name':'Ogun State Government','entity_type':'government_agency'}],
    'pc_assets':[{'asset_id':'ASSET_GWAY','name':'Gateway Deep Seaport','asset_type':'proposed_port','country':'NG'},
                 {'asset_id':'ASSET_OGUN_SEZ','name':'Ogun State Blue Marine Special Economic Zone','asset_type':'special_economic_zone','country':'NG'}],
    'pc_mobile_assets':[],'pc_events':[]}
ix=b._identity_indexes(reg)
def cand(table,name,payload=None):return b._identity_candidates(table,name,payload or {},ix,reg)
assert len(cand('pc_entities','MSC Cruises')[0])==1
assert cand('pc_entities','MSC Cruises')[0][0]['entity_id']=='COMP_MSC_CRUISES'
assert cand('pc_entities','Port of Los Angeles')[0][0]['entity_id']=='CA_AUTH_LA'
assert b._type_conflict('pc_entities','company','port_authority')
assert not b._type_conflict('pc_entities','port_authority','government_agency')
assert not b._type_conflict('pc_entities','company','ports_logistics_group')
assert not b._type_conflict('pc_assets','proposed_port','port')
assert b._type_conflict('pc_assets','terminal','port')
assert len(cand('pc_entities','DP World')[0])==2
assert len(cand('pc_assets','Gateway Deep Seaport')[0])==1
assert cand('pc_assets','Blue Marine Special Economic Zone')[1], 'SEZ fuzzy candidate should be held'
assert b._validation_issue({'target_table':'pc_mobile_assets','payload':{'name':'Tifani','metadata':{'seizure_date':'2026-04'}}}) is None
assert 'incomplete date' in b._validation_issue({'target_table':'pc_events','payload':{'title':'Example','start_date':'2024-06'}})
assert 'record-type' in b._validation_issue({'target_table':'pc_entities','payload':{'name':'HPC Hamburg Port Consulting advisory 2026'}})
assert 'record-type' in b._validation_issue({'target_table':'pc_assets','payload':{'name':'van_oord_vindnes_2028'}}), 'vessel metadata classifier'
print('PASS: 13 offline identity/classification/date checks; all publication operations untested')
# _plan offline smoke test with the same canonical registries and synthetic
# staged rows reproducing the exported problem cases; NO remote connection.
class Resp:
    def __init__(self,data=None):self.data=data or []
class Query:
    def __init__(self,rows):self.rows=rows;self.limit_value=None;self.offset=0
    def select(self,*a,**k):return self
    def eq(self,*a):return self
    def in_(self,*a):return self
    def order(self,*a):return self
    def range(self,start,end):self.offset=start;self.limit_value=end-start+1;return self
    def execute(self):return Resp(self.rows[self.offset:self.offset+self.limit_value] if self.limit_value is not None else self.rows)
class SB:
    def table(self,name):
        if name=='pc_v08_trade_content' or name=='pc_v10_publication_items':return Query([])
        return Query(reg.get(name,[]))
def row(i,t,n,typ,meta=None):
    payload={b.NAME_COL[t]:n,'metadata':meta or {'research_sources':[{'url':'https://example.org/source'}]}}
    payload['entity_type' if t=='pc_entities' else 'asset_type']=typ
    return {'staged_record_id':str(i),'ingestion_job_id':'job','source_record_key':f'input:{i}',
            'target_table':t,'natural_key':n,'payload':payload}
staged=[row(1,'pc_entities','MSC Cruises','cruise_operator'),
        row(2,'pc_entities','DP World','ports_logistics_group'),
        row(3,'pc_entities','Ogun State Government','government'),
        row(4,'pc_assets','Gateway Deep Seaport','proposed_port'),
        row(5,'pc_entities','HPC Hamburg Port Consulting advisory 2026','company')]
ready,followers,exceptions,pub=b._plan(SB(),'job',staged)
matched={r['natural_key']:cid for r,d,cid in ready if d=='match_existing'}
assert matched=={'MSC Cruises':'COMP_MSC_CRUISES','Ogun State Government':'OGUN','Gateway Deep Seaport':'ASSET_GWAY'},matched
assert {x['Name'] for x in exceptions}=={'DP World','HPC Hamburg Port Consulting advisory 2026'},exceptions
assert not followers
print('PASS: 5-record mock batch matched 3, held ambiguous DP World and misclassified HPC')
