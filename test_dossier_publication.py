import unittest
from copy import deepcopy
from test_loader_regressions import DB
from pc_dossier_publication import publish_dossier_graph

URL='https://example.org/article'
def setup():
    findings={'relationships':[{'source_name':'Buyer','target_name':'Terminal','target_type':'asset','relationship':'operates','source_urls':[URL]}],
      'transactions':[{'buyer_name':'Buyer','target_name':'Terminal','value':835000000,'currency':'USD','value_basis':'enterprise value','status':'completed','source_urls':[URL]}],
      'projects':[{'name':'Terminal','developer_name':'Buyer','delivery_year':2028,'status':'planned','source_urls':[URL]}],
      'contracts':[{'contract_name':'Facility agreement','participants':[{'name':'Buyer','role':'developer'}],'source_urls':[URL]}]}
    stages=[]; pubs=[]
    for i,(table,name) in enumerate([('pc_entities','Buyer'),('pc_entities','Terminal'),('pc_assets','Terminal'),('pc_events','Agreement')]):
        metadata={'ingestion_mode':'AI_RESEARCH_DOSSIER_V3','intake_source_key':'s','research_sources':[URL],
                  'research_dossier_connected_findings':findings}
        if table=='pc_events': metadata['event_links']=[{'linked_name':'Terminal','linked_type':'asset','relationship':'project subject'}]
        stages.append({'staged_record_id':str(i),'target_table':table,'payload':{'name':name,'metadata':metadata}})
        pubs.append({'staged_record_id':str(i),'canonical_id':'id'+str(i)})
    return stages,pubs

class PublicationTests(unittest.TestCase):
    def test_unrelated_generic_name_tokens_are_not_identity_candidates(self):
        from pc_v15_bulk_replay import _identity_candidates,_identity_indexes
        cases=[('pc_entities','Noatum Ports',{'name':'Neltume Ports','entity_id':'other'}),
          ('pc_entities','JD.com',{'name':'Amazon.com, Inc.','entity_id':'other'}),
          ('pc_assets','Navi Mumbai International Airport',{'name':'Navoi International Airport','asset_id':'other'}),
          ('pc_mobile_assets','Mersin Prosperity',{'name':'Malaysia Prosperity','mobile_asset_id':'other','imo':'9251822'})]
        for table,name,other in cases:
            registry={table:[other]}; index=_identity_indexes(registry)
            payload={'name':name}
            if table=='pc_mobile_assets':payload['imo']='9327554'
            exact,fuzzy,cross,_=_identity_candidates(table,name,payload,index,registry)
            self.assertEqual((exact,fuzzy,cross),([],[],[]),name)
    def test_medium_confidence_does_not_erase_distinct_incident_names(self):
        from pc_graph_validator import validate_dossier
        events=[{'title':name+' reported struck','event_type':'projectile strike','start_date':'2026-09-29',
          'location':'Hormuz','confidence':'medium','source_urls':[URL],
          'event_links':[{'linked_type':'mobile_asset','linked_name':name}]} for name in ('Mersin Prosperity','Sinbad')]
        events.append({'title':'Reported strike disrupts Yanbu loading','event_type':'projectile strike','location':'Yanbu',
          'source_urls':[URL],'event_links':[{'linked_type':'asset','linked_name':'Yanbu Port'}]})
        value,_=validate_dossier({'graph':{'events':events,'claims':[{'claim':'Yanbu attacker attribution remains unconfirmed','status':'unconfirmed','source_urls':[URL]}]}})
        self.assertEqual([e['title'] for e in value['graph']['events'][:2]],[e['title'] for e in events[:2]])
        self.assertIn('Yanbu Port',value['graph']['events'][2]['title'])
        self.assertNotIn('vessel',value['graph']['events'][2]['description'].lower())
    def test_published_company_is_not_resolved_again_by_name(self):
        from unittest.mock import patch
        from pc_connected_research import publish_company_plan
        plan={'subject_name':'AD Ports Group','replayed_from_validated_dossier':True,
          'published_canonical_id':'COMP_ADPORTS','company':{'name':'AD Ports Group','source_urls':[URL]}}
        db=DB({'pc_entities':[{'entity_id':'COMP_ADPORTS','name':'AD Ports Group'},
                                 {'entity_id':'duplicate','name':'AD Ports Group'}]})
        with patch('pc_connected_research._resolve_entity',side_effect=AssertionError('Should use publication ID')):
            report=publish_company_plan(db,'job',plan)
        self.assertEqual(report['holds'],[])
        self.assertEqual(db.rows['pc_company_profiles'][0]['entity_id'],'COMP_ADPORTS')
    def test_source_graph_uses_published_organization_for_vessel_role(self):
        stages,pubs=setup()
        stages.append({'staged_record_id':'4','target_table':'pc_mobile_assets','payload':{'name':'St Helena',
            'metadata':{'ingestion_mode':'AI_RESEARCH_DOSSIER_V3','intake_source_key':'s'}}})
        pubs.append({'staged_record_id':'4','canonical_id':'vessel-id'})
        stages[0]['payload']['metadata']['research_dossier_connected_findings']['relationships'].append({
            'source_name':'Buyer','target_name':'St Helena','relationship':'historical charterer','status':'historical','source_urls':[URL]})
        db=DB();report=publish_dossier_graph(db,'job',stages,pubs)
        self.assertEqual(report['relationships'],2)
        self.assertTrue(any(r['target_id']=='vessel-id' and r['source_id']=='id0' for r in db.rows['pc_relationships']))
    def test_typed_links_sidecars_and_retry(self):
        stages,pubs=setup(); db=DB()
        report=publish_dossier_graph(db,'job',stages,pubs)
        self.assertEqual(report['holds'],[])
        self.assertEqual(db.rows['pc_relationships'][0]['target_id'],'id2')
        self.assertEqual(db.rows['pc_transactions'][0]['target_entity_id'],'id1')
        self.assertEqual(db.rows['pc_transactions'][0]['reported_value'],835000000)
        self.assertEqual(db.rows['pc_transactions'][0]['metadata']['source_finding']['value_basis'],'enterprise value')
        self.assertEqual(db.rows['pc_project_details'][0]['asset_id'],'id2')
        self.assertNotIn('project_stage',db.rows['pc_project_details'][0])
        self.assertEqual(db.rows['pc_event_links'][0]['linked_id'],'id2')
        before=deepcopy(db.rows)
        publish_dossier_graph(db,'job',stages,pubs)
        self.assertEqual(before,db.rows)
    def test_unpublished_company_cannot_be_created_by_edges(self):
        stages,pubs=setup(); db=DB()
        report=publish_dossier_graph(db,'job',stages,pubs[1:])
        self.assertEqual(report['transactions'],0)
        self.assertEqual(report['event_links'],1)
        self.assertEqual(len(report['holds']),4)
        self.assertNotIn('pc_entities',db.rows)
    def test_pending_owner_and_ambiguous_name_held(self):
        stages,pubs=setup()
        findings=stages[0]['payload']['metadata']['research_dossier_connected_findings']
        findings['relationships'][0].update(relationship='owns',status='proposed')
        db=DB(); report=publish_dossier_graph(db,'job',stages,pubs)
        self.assertEqual(report['relationships'],0)
        self.assertEqual(report['transactions'],1)
        findings['relationships'][0].update(relationship='supports',status='reported')
        findings['relationships'][0].pop('target_type')
        report=publish_dossier_graph(db,'job',stages,pubs)
        self.assertTrue(any('ambiguous' in h['reason'] for h in report['holds']))
    def test_constraint_failure_visible_independent_writes_continue(self):
        class BrokenDB(DB):
            def table(self,t):
                if t=='pc_transactions': raise ValueError('transaction constraint violation')
                return super().table(t)
        stages,pubs=setup(); db=BrokenDB(); report=publish_dossier_graph(db,'job',stages,pubs)
        self.assertEqual(report['transactions'],0)
        self.assertEqual(report['projects'],1)
        self.assertEqual(report['event_links'],1)
        self.assertEqual(report['holds'][0]['reason'],'transaction constraint violation')

if __name__=='__main__': unittest.main()
