import unittest
from pc_company_depth import internal_links,filter_proposal,discover_company_pages,exact_company,publish_core_enrichment

class TestCompanyResearch(unittest.TestCase):
 def test_link_selection_does_not_follow_external_sites(self):
  body='[Contact](https://svitzer.com/contact/) [Leadership](https://svitzer.com/who-we-are/global-leadership/) [Bad](https://other.com/fleet) [PDF](https://svitzer.com/docs/test.pdf)'
  links=internal_links(body,'https://svitzer.com/')
  self.assertIn('https://svitzer.com/contact/',links)
  self.assertIn('https://svitzer.com/who-we-are/global-leadership/',links)
  self.assertTrue(all(x.startswith('https://svitzer.com/') for x in links))
  self.assertEqual(len(links),2)
 def test_source_evidence_filter(self):
  p={'company_name':'Svitzer','headquarters':[{'office_name':'Copenhagen','source_url':'https://svitzer.com/contact/'},{'office_name':'fake','source_url':'https://unverified.example/'}],
     'vessel_candidates':[{'name':'Unknown tug','imo':'XXXX','source_url':'https://svitzer.com/contact/'}]}
  out=filter_proposal(p,['https://svitzer.com/contact/'],'Svitzer')
  self.assertEqual(len(out['headquarters']),1)
  self.assertEqual(len(out['rejected']),2)
  self.assertIsNone(out['vessel_candidates'][0]['imo'])
 def test_bounded_discovery_and_error_reporting(self):
  pages={'https://svitzer.com/':'[Leadership](https://svitzer.com/who-we-are/global-leadership/) [Fleet](https://svitzer.com/fleet/)','https://svitzer.com/who-we-are/global-leadership/':'A'*160}
  def reader(url):return pages[url]
  result,errors=discover_company_pages('https://svitzer.com/',reader)
  self.assertEqual(len(result),2)
  self.assertEqual(len(errors),1)
 def test_no_silent_match_to_false_company(self):
  class FakeExec:
   data=[{'entity_id':'1','name':'Svitzer','entity_type':'office','metadata':{}}]
  class FakeQuery:
   def select(self,*a):return self
   def ilike(self,*a):return self
   def limit(self,*a):return self
   def execute(self):return FakeExec()
  class FakeClient:
   def table(self,*a):return FakeQuery()
  with self.assertRaises(ValueError):exact_company(FakeClient(),'Svitzer')

if __name__=='__main__':unittest.main()

# A fake backing store proves the specialist write path does not create a
# second Svitzer and does not publish any unidentified fleet vessels.
class DBResult:
 def __init__(self,items):self.data=items
class FakeSB:
 def __init__(self):
  self.store={'pc_ingestion_jobs':[{'ingestion_job_id':'j1','status':'review','source_scope':{'homepage':'https://svitzer.com/','proposal':{'provenance_urls':['https://svitzer.com/']}}}],
       'pc_entities':[{'entity_id':'E1','name':'Svitzer','entity_type':'company'}],
       'pc_company_profiles':[],'pc_company_offices':[],'pc_company_people_roles':[],'pc_people':[]}
 def table(self,name):return FakeQ(self,name)
class FakeQ:
 def __init__(self,db,name):self.db=db;self.name=name;self.filters=[];self.action=None;self.payload=None
 def select(self,*a,**kw):return self
 def eq(self,k,v):self.filters.append((k,v));return self
 def ilike(self,k,v):self.filters.append((k,v));return self
 def limit(self,*a):return self
 def insert(self,p):self.action='insert';self.payload=p;return self
 def upsert(self,p,**kw):self.action='upsert';self.payload=p;return self
 def update(self,p):self.action='update';self.payload=p;return self
 def execute(self):
  rows=self.db.store[self.name]
  matches=[x for x in rows if all(str(x.get(k,'')).casefold()==str(v).casefold() for k,v in self.filters)]
  if self.action=='insert':rows.append(self.payload);return DBResult([self.payload])
  if self.action=='update':
   for x in matches:x.update(self.payload)
   return DBResult(matches)
  if self.action=='upsert':
   prior=[x for x in rows if x.get('entity_id')==self.payload.get('entity_id')]
   if prior:prior[0].update(self.payload)
   else:rows.append(self.payload)
   return DBResult([self.payload])
  return DBResult(matches)

class TestPublication(unittest.TestCase):
 def test_company_profile_preserves_identity_and_holds_fleet(self):
  db=FakeSB()
  proposal={'company_name':'Svitzer','provenance_urls':['https://svitzer.com/'],
   'business_description':'Towage','sector':'maritime','services':['towage'],
   'operating_countries':[],'headquarters':[{'office_name':'HQ','city':'Copenhagen',
   'country':'Denmark','office_type':'headquarters','source_url':'https://svitzer.com/'}],
   'people':[],'vessel_candidates':[{'name':'Unverified vessel','source_url':'https://svitzer.com/'}],
   'related_companies':[],'projects_contracts':[],'research_gaps':[]}
  db.store['pc_ingestion_jobs'][0]['source_scope']['proposal']=proposal
  out=publish_core_enrichment(db,'j1','E1',proposal,[0],[])
  self.assertEqual(out['offices_added'],1)
  self.assertEqual(out['vessels_held'],1)
  self.assertEqual(len(db.store['pc_entities']),1)
  self.assertEqual(len(db.store['pc_company_profiles']),1)
  self.assertEqual(db.store['pc_ingestion_jobs'][0]['status'],'partial')
  self.assertNotIn('pc_mobile_assets',db.store)
