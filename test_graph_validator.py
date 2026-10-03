"""Regression using the user-supplied St Helena v3.5 dossier (no web calls)."""
import json
from pathlib import Path
from pc_graph_validator import validate_dossier
from pc_research_dossier import graph_to_core_records

FIXTURE=Path(__file__).parent / 'fixtures' / 'st_helena_input.json'

def run():
    v,r=validate_dossier(json.loads(FIXTURE.read_text()))
    rows=graph_to_core_records(v,'St Helena')
    assert len(rows)==7
    assert len(v['graph']['physical_assets'])==0
    assert len(v['graph']['mobile_assets'])==1
    assert v['graph']['mobile_assets'][0]['imo']=='8716306'
    assert v['graph']['identity_history'][0]['identifier_type']=='name'
    assert v['graph']['identity_history'][0]['date_evidence']['valid_from']['value']=='2018-04'
    assert v['graph']['events'][0]['involved_identifiers'][0]=='imo:8716306'
    assert v['graph']['events'][0]['event_type']=='attack'
    assert len(v['graph']['claims'])==1
    assert len(r['holds'])==6
    assert not any(x.get('relationship')=='owned_and_operated_by' for x in v['graph']['relationships'])
    print('St Helena fixture regression: PASS (7 core objects, 6 held findings)')

if __name__=='__main__': run()
