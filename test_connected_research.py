import pc_connected_research as m


def test_imo():
    assert m._valid_imo('8716306')
    assert not m._valid_imo('8716307')
    assert not m._valid_imo('123')


def test_company_research_filters_unidentified_fleet(monkeypatch):
    def fake_web(api_key,q,model=None):
        return 'evidence', ['https://example.com/source']
    def fake_struct(api_key,system,prompt,model=None,max_tokens=0):
        return {
            'company':{'name':'Example Towage','entity_type':'company','source_urls':['https://example.com/source']},
            'offices':[], 'people':[], 'related_companies':[],
            'vessels':[{'name':'Example Fleet','imo':None,'source_urls':['https://example.com/source']}],
            'footprint':[], 'transactions':[], 'contracts':[], 'projects':[], 'research_gaps':[]
        }
    monkeypatch.setattr(m,'_web',fake_web); monkeypatch.setattr(m,'_json_struct',fake_struct)
    p=m.research_company('k','Example Towage',['https://example.com/source'])
    assert p['vessels']==[]
    assert any('verified IMO' in x for x in p['research_gaps'])


def test_date_numeric_cleaners():
    assert m._date('2026-09-30')=='2026-09-30'
    assert m._date('September 2026') is None
    assert m._num('1,234.5')==1234.5
    assert m._int('2020.0')==2020
