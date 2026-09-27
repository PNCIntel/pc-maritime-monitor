"""Deterministic local tests; no Supabase access and no live writes."""
import importlib.util, types, sys, csv
from pathlib import Path
root=Path(__file__).parent
sys.modules['streamlit']=types.SimpleNamespace()
spec=importlib.util.spec_from_file_location('replay',root/'pc_v15_bulk_replay.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class R:
    def __init__(self,data):self.data=data
class Q:
    def __init__(self, rows):self.rows=rows;self.start=0;self.end=499
    def select(self,*x,**kw):return self
    def order(self,*x):return self
    def range(self,a,b):self.start=a;self.end=b;return self
    def execute(self):return R(self.rows[self.start:self.end+1])
class SB:
    def __init__(self, data):self.data=data;self.calls={}
    def table(self,name):
        self.calls[name]=self.calls.get(name,0)+1
        return Q(self.data[name])

canon={
 'pc_entities':[{'entity_id':'ENTITY_PORT_LA','name':'Port of Los Angeles','entity_type':'port_authority'},
                {'entity_id':'COMP_MAERSK','name':'A.P. Moller-Maersk','entity_type':'shipping_group'},
                {'entity_id':'COMP_BALTIC','name':'Baltic Hub Container Terminal','entity_type':'terminal_operator'},
                {'entity_id':'COMP_QSL','name':'QSL International','entity_type':'logistics_company'}],
 'pc_assets':[{'asset_id':'PORT_LA','name':'Port of Los Angeles','asset_type':'port'},
              {'asset_id':'ASSET_HUB','name':'Baltic Hub Container Terminal','asset_type':'terminal'}],
 'pc_mobile_assets':[{'mobile_asset_id':'VESSEL1','name':'Historical Name','imo':'1234567','flag':'UK'}],
 'pc_events':[{'event_id':'EVENT1','title':'DP World Ogun Deep Seaport Agreement','start_date':'2026-09-24'}]
}
sb=SB(canon)
reg=m._canon_registry(sb,canon.keys());idx=m._identity_indexes(reg)
assert m._identity_candidates('pc_entities','port_of_los_angeles',{},idx,reg)[0][0]['entity_id']=='ENTITY_PORT_LA'
assert m._identity_candidates('pc_entities','a_p_moller_maersk',{},idx,reg)[0][0]['entity_id']=='COMP_MAERSK'
assert m._identity_candidates('pc_assets','port_of_los_angeles',{},idx,reg)[0][0]['asset_id']=='PORT_LA'
assert m._identity_candidates('pc_assets','Baltic Hub',{},idx,reg)[1], 'fuzzy partial terminal'
assert m._identity_candidates('pc_entities','QSL',{},idx,reg)[1], 'acronym match'
assert m._identity_candidates('pc_mobile_assets','new name',{'imo':'1234567'},idx,reg)[0][0]['mobile_asset_id']=='VESSEL1'
assert m._identity_candidates('pc_entities','Brand New Port',{},idx,reg)[0]==[]
assert m._identity_candidates('pc_entities','Brand New Port',{},idx,reg)[2]==[]
assert m._validation_issue({'target_table':'pc_assets','payload':{'name':'Baltic Hub RMG fleet expansion 2026'}})
assert m._validation_issue({'target_table':'pc_entities','payload':{'name':'Port of Hastings 2055 Development Strategy'}})
assert m._validation_issue({'target_table':'pc_events','payload':{'title':'Sample','start_date':'2024-06'}})
# 501 records proves complete pagination rather than old name IN exact lookup.
many=SB({'pc_entities':[{'entity_id':str(i),'name':f'Company {i}'} for i in range(501)],'pc_assets':[]})
assert len(m._canon_registry(many,['pc_entities'])['pc_entities'])==501
# Source export demonstrates problematic names actually present in the held batch.
with open('/mnt/data/2026-09-27T10-03_export.csv',encoding='utf-8-sig') as f:
    old=list(csv.DictReader(f))
assert any(x['Name']=='port_of_los_angeles' and x['Decision']=='create_new' for x in old)
assert any(x['Name']=='a_p_moller_maersk' and x['Decision']=='create_new' for x in old)
# Complete _plan integration: proposed NEW must match an existing canonical identity.
class Query:
    def __init__(self, sb, table): self.sb=sb;self.table=table;self.filters=[];self.start=0;self.end=499
    def select(self,*a,**kw):return self
    def order(self,*a):return self
    def range(self,a,b):self.start=a;self.end=b;return self
    def eq(self,col,val):self.filters.append((col,val));return self
    def in_(self,col,vals):self.filters.append((col,set(vals)));return self
    def execute(self):
        rows=self.sb.data[self.table]
        for col,val in self.filters:
            rows=[r for r in rows if r.get(col) in val] if isinstance(val,set) else [r for r in rows if r.get(col)==val]
        return R(rows[self.start:self.end+1])
class LiveSB:
    def __init__(self,data):self.data=data
    def table(self,t):return Query(self,t)
job='job-85';r1='staged-LA';r2='staged-Maersk';r3='staged-QSL'
def staging(id, table,name):
    return {'staged_record_id':id,'target_table':table,'natural_key':name,'payload':{'name':name,'metadata':{'source_url':'https://example.com/source'}},'source_record_key':id,'ingestion_job_id':job}
mock=LiveSB({**canon,'pc_v08_trade_content':[],'pc_v10_publication_items':[]})
ready,followers,errors,published=m._plan(mock,job,[staging(r1,'pc_entities','port_of_los_angeles'),staging(r2,'pc_entities','a_p_moller_maersk'),staging(r3,'pc_entities','QSL')])
assert {(r['staged_record_id'],d,c) for r,d,c in ready}=={(r1,'match_existing','ENTITY_PORT_LA'),(r2,'match_existing','COMP_MAERSK')}
assert len(errors)==1 and 'fuzzy' in errors[0]['Reason'] and errors[0]['Name']=='QSL'
assert m._plan_digest(ready,followers,errors) != m._plan_digest(ready[:1],followers,errors)
print('PASS: _plan integration prevents LA/Maersk duplicates; holds QSL for identity review; plan digest invalidates stale approvals')
print('PASS: normalized exact matches (Los Angeles, Maersk), fuzzy candidate holds (Baltic Hub, QSL), cross-category protection, IMO identity, unsafe types and dates, 501-row pagination, exported regressions')
print('LIMIT: mocked Supabase data; live registry and publishing NOT tested')

# Model-first classifier regression: dates and known 85-record misclassifications.
wrong_kind=[
 ('pc_entities','HPC Hamburg Port Consulting advisory 2026'),
 ('pc_entities','Port of Hastings 2055 Development Strategy'),
 ('pc_entities','us_navy_robotic_autonomous_centre_2026'),
 ('pc_assets','Baltic Hub RMG cranes'),
 ('pc_assets','Contecon Manzanillo hybrid RTGs 2026'),
 ('pc_assets','Tecon Rio Grande STS and RTG cranes 2026'),
 ('pc_assets','van_oord_vindnes_2028'),
 ('pc_assets','van_oord_vestnes_2029'),
]
for table,name in wrong_kind:
    issue=m._validation_issue({'target_table':table,'payload':{'name':name}})
    assert issue,(table,name)
# A physical proposed facility is different from an announcement and stays eligible for match/research.
assert m._validation_issue({'target_table':'pc_assets','payload':{'name':'Deendayal Port e-methanol plant'}}) is None
assert m.PUBLISHER_VERSION=='1.5.4-model-guard'

# Cross-domain fuzzy warning: existing terminal should block creation of homonymous new company.
ix=m._identity_indexes({'pc_entities':[],'pc_assets':canon['pc_assets']})
cross=m._identity_candidates('pc_entities','Baltic Hub',{},ix,{'pc_entities':[],'pc_assets':canon['pc_assets']})[2]
assert cross and cross[0]['asset_id']=='ASSET_HUB'

# Integration: all incorrectly typed rows held; acronym QSL cannot become a NEW company
extra=[staging(f'wrong-{i}',table,name) for i,(table,name) in enumerate(wrong_kind)]
extra.append(staging('short-QSL','pc_entities','QSL'))
new_ready,_,new_errors,_=m._plan(mock,job,extra)
assert not new_ready,(new_ready,new_errors)
assert len(new_errors)==len(extra),(new_errors,len(extra))
print('PASS: 8 misclassified source records and short-acronym creation blocked; proposed infrastructure retained; cross-domain terminal detected')
