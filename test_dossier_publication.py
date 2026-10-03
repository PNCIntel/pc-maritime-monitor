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
