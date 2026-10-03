import unittest
from copy import deepcopy
from test_loader_regressions import DB
from pc_reviewed_job_repair import fingerprint, preview_repair, apply_repair

class RepairDB(DB):
    def rpc(self,name,args):
        from types import SimpleNamespace
        assert name=='pc_v10_backup_staged'
        self.rows.setdefault('backups',[]).append(deepcopy(args))
        return SimpleNamespace(execute=lambda:SimpleNamespace(data='backup'))

class RepairTests(unittest.TestCase):
    def setUp(self):
        self.stage={'ingestion_job_id':'job','staged_record_id':'stage','target_table':'pc_assets',
                    'natural_key':'CLI Sul','payload':{'name':'CLI Sul','asset_type':'terminal','country':'Brazil'}}
        self.db=RepairDB({'pc_staged_records':[self.stage], 'pc_assets':[{'asset_id':'terminal','name':'CLI Sul Santos Terminal','asset_type':'terminal','country':'Brazil'}],
                         'pc_ingestion_jobs':[{'ingestion_job_id':'job','source_scope':{}}]})
        self.repair={'job_id':'job','reason':'Verified terminal alias', 'items':[{
            'staged_record_id':'stage','expected_fingerprint':fingerprint({'payload':self.stage['payload'],'natural_key':'CLI Sul'}),
            'decision':'match_existing','canonical_id':'terminal','evidence_urls':['https://example.org/official']}]}
    def test_stale_edit_and_wrong_job_are_rejected(self):
        self.db.rows['pc_staged_records'][0]['payload']['country']='India'
        with self.assertRaises(ValueError):preview_repair(self.db,'job',self.repair)
        with self.assertRaises(ValueError):preview_repair(self.db,'other',self.repair)
    def test_country_and_missing_target_are_rejected(self):
        self.db.rows['pc_assets'][0]['country']='India'
        with self.assertRaises(ValueError):preview_repair(self.db,'job',self.repair)
        self.db.rows['pc_assets']=[]
        with self.assertRaises(ValueError):preview_repair(self.db,'job',self.repair)
    def test_apply_preserves_originals_and_persists_review(self):
        result=apply_repair(self.db,'job',self.repair,'DCM')
        scope=self.db.rows['pc_ingestion_jobs'][0]['source_scope']
        self.assertEqual(result['backup_id'],'backup')
        self.assertEqual(scope['reviewed_repair_journal'][0]['before'][0]['before'],self.stage)
        self.assertEqual(scope['reviewed_identity_decisions']['stage']['canonical_id'],'terminal')
        self.assertEqual(scope['reviewed_repair_journal'][0]['status'],'applied')

if __name__=='__main__':unittest.main()
