import json
from pathlib import Path
from pc_graph_validator import validate_dossier
from pc_research_dossier import graph_to_core_records

FIXTURE=Path('/mnt/data/v34base/https_www.twz.com_news-features_claims-swirl-around-u-s-marines-injured-aboard-m_research_dossier.json')

def run():
    d=json.loads(FIXTURE.read_text())
    v,r=validate_dossier(d)
    assert v['validated_version']=='research-first-v3.4'
    ev=v['graph']['events'][0]
    assert ev['title']=='Projectile strike on M/V St. Helena in Strait of Hormuz'
    assert ev['verification_status']=='reported'
    assert 'Iranian cruise missile' not in ev['description']
    assert any(x.get('identifier_value')=='MNG Tahiti' for x in v['graph']['identity_history'])
    assert any(x.get('relationship')=='owner' and x.get('effective_to') is None for x in v['graph']['relationships'])
    assert any(x.get('relationship')=='charterer' and x.get('source_name')=='Extreme E' for x in v['graph']['relationships'])
    assert not any('charter' in str(x.get('transaction_type') or '').lower() for x in v['graph']['transactions'])
    assert len(v['graph']['people'])==0
    assert len(r['repairs'])>=5
    assert len(r['holds'])>=2  # combined role + incomplete sale transaction
    rec=graph_to_core_records(v,'fixture')
    assert any(x['table']=='pc_mobile_assets' and x['payload'].get('imo')=='8716306' for x in rec)
    assert any(x['table']=='pc_events' and x['payload']['title'].startswith('Projectile strike') for x in rec)
    print('graph-validator tests: PASS', {'repairs':len(r['repairs']),'holds':len(r['holds']),'records':len(rec)})

if __name__=='__main__': run()
