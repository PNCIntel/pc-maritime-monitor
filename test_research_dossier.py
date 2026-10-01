from pc_research_dossier import graph_to_core_records


def test_st_helena_graph_maps_one_vessel_and_history():
    dossier={
      'version':'research-first-v3','source_url':'https://example.com/st-helena','evidence_urls':['https://evidence.example/a'],
      'graph':{
        'primary_subject':{'name':'St Helena','type':'vessel'},
        'companies':[{'name':'MNG Maritime','entity_type':'company','role':'operator','source_urls':['https://evidence.example/a']}],
        'mobile_assets':[{'name':'St Helena','asset_type':'vessel','imo':'8716306','source_urls':['https://evidence.example/a']}],
        'identity_history':[{'asset_name':'St Helena','imo':'8716306','identifier_type':'name','identifier_value':'MNG Tahiti','valid_from':'2018','valid_to':'2021','source_urls':['https://evidence.example/a']}],
        'events':[{'title':'St Helena attacked in Strait of Hormuz','start_date':'2026-09-14','event_type':'attack','source_urls':['https://evidence.example/a']}],
        'relationships':[{'source_name':'MNG Maritime','target_name':'St Helena','relationship':'operator'}],
        'claims':[{'claim':'US Marines aboard','status':'unconfirmed'}],
        'people':[],'physical_assets':[],'transactions':[],'projects':[],'contracts':[],'locations':[],'timeline':[],'research_gaps':[]
      }
    }
    rows=graph_to_core_records(dossier,'TWZ')
    vessels=[r for r in rows if r['table']=='pc_mobile_assets']
    assert len(vessels)==1
    assert vessels[0]['payload']['imo']=='8716306'
    hist=vessels[0]['payload']['metadata']['identity_history']
    assert hist[0]['identifier_value']=='MNG Tahiti'
    assert any(r['table']=='pc_entities' and r['payload']['name']=='MNG Maritime' for r in rows)
    assert any(r['table']=='pc_events' for r in rows)


def test_abstract_fleet_not_physical_asset():
    dossier={'version':'research-first-v3','source_url':'https://svitzer.com/','evidence_urls':[], 'graph':{
      'primary_subject':{'name':'Svitzer','type':'company'},
      'companies':[{'name':'Svitzer','entity_type':'company'}],
      'physical_assets':[{'name':'Svitzer Fleet','asset_type':'fleet'}],
      'mobile_assets':[],'events':[],'people':[],'identity_history':[],'transactions':[],
      'relationships':[],'projects':[],'contracts':[],'locations':[],'claims':[],'timeline':[],'research_gaps':[]}}
    rows=graph_to_core_records(dossier,'Svitzer')
    assert not any(r['table']=='pc_assets' and r['payload']['name']=='Svitzer Fleet' for r in rows)
    assert any(r['table']=='pc_entities' and r['payload']['name']=='Svitzer' for r in rows)


def test_invalid_imo_is_not_preserved():
    dossier={'version':'research-first-v3','source_url':'','evidence_urls':[], 'graph':{
      'primary_subject':{},'companies':[],'physical_assets':[],
      'mobile_assets':[{'name':'Unknown Barge','asset_type':'inland barge','imo':'123'}],
      'events':[],'people':[],'identity_history':[],'transactions':[],'relationships':[],'projects':[],
      'contracts':[],'locations':[],'claims':[],'timeline':[],'research_gaps':[]}}
    rows=graph_to_core_records(dossier,'test')
    assert rows[0]['payload']['imo'] is None
