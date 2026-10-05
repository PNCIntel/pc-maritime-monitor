import ast,json,unittest
from pathlib import Path

class DossierHistory(unittest.TestCase):
    def setUp(self):
        tree=ast.parse(Path(__file__).with_name('pc_terminal.py').read_text())
        names={'_clean','_meta','_facility_fact_rows','_event_source_urls','_render_map_for_asset','_coords_from_record','_render_infrastructure_history'}
        self.ns={'Any':object,'json':json,'_norm':lambda x:x}
        exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names],type_ignores=[]),'terminal','exec'),self.ns)
    def test_nested_capacity_keeps_proposal_and_source(self):
        row={'metadata':{'rotterdam_company_depth':{'checked_on':'2026-10-05','observations':[{'source_url':'https://example.test','proposed_investment':{'capacity':2000000,'unit':'TEU/year'},'access':['rail','barge']}]}}}
        out=self.ns['_facility_fact_rows'](row)
        self.assertEqual(len(out),3)
        self.assertEqual(out[0]['Observation'],'Proposed investment / capacity')
        self.assertTrue(all(x['Source']=='https://example.test' for x in out))
        self.assertEqual(out[-1]['Reported value'],'rail, barge')
    def test_reused_event_gets_history_primary_source(self):
        row={'metadata':{'rotterdam_history':{'evidence':{'url':'https://primary.test'}}}}
        self.assertEqual(self.ns['_event_source_urls'](row),['https://primary.test'])
    def test_history_shows_all_29_events_and_year_filter(self):
        import contextlib
        class UI:
            def __init__(self,year): self.year=year;self.titles=[]
            def selectbox(self,*args,**kwargs): return self.year
            def expander(self,title):self.titles.append(title);return contextlib.nullcontext()
            def __getattr__(self,name): return lambda *a,**k:None
        events=[{'event_id':str(i),'start_date':f'{2021+i%6}-11-01','title':str(i)} for i in range(29)]
        self.ns['_render_event_rows']=lambda *a:None
        ui=UI('All years');self.ns['st']=ui
        self.ns['_render_infrastructure_history']('port',{},events)
        self.assertEqual(len(ui.titles),29)
        ui=UI('2022');self.ns['st']=ui
        self.ns['_render_infrastructure_history']('port',{},events)
        self.assertEqual(len(ui.titles),5)
    def test_map_uses_connected_assets_and_metadata_coordinates(self):
        import contextlib
        class UI:
            def __init__(self):self.frame=None
            def map(self,frame,**kw):self.frame=frame
            def expander(self,*a):return contextlib.nullcontext()
            def __getattr__(self,name):return lambda *a,**k:None
        ui=UI();self.ns['st']=ui
        import pandas as pd
        self.ns['pd']=pd
        self.ns['_local_infrastructure']=lambda r:[{'id':'terminal','name':'Chane'}]
        self.ns['object_record']=lambda t,i:{'name':'Chane','metadata':{'latitude':51.88,'longitude':4.32}}
        self.ns['_render_map_for_asset']({'name':'Port','asset_id':'port'})
        self.assertEqual(ui.frame.iloc[0]['name'],'Chane')
        self.assertEqual(ui.frame.iloc[0]['lat'],51.88)

if __name__=='__main__':unittest.main()
