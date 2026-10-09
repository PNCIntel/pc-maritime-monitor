import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pc_object_resolver import resolve_object

class Adapter:
    def __init__(self):
        self.records = {
            ('asset','AIRPORT_A'): {'asset_id':'AIRPORT_A','name':'Airport A'},
            ('asset','CARGO_TERMINAL'): {'asset_id':'CARGO_TERMINAL','name':'Cargo Terminal'},
            ('asset','PORT_B'): {'asset_id':'PORT_B','name':'Port B'},
            ('asset','PORT_TERMINAL'): {'asset_id':'PORT_TERMINAL','name':'Port Terminal'},
            ('event','EV1'): {'event_id':'EV1','title':'Airport incident'},
            ('event','EV2'): {'event_id':'EV2','title':'Terminal incident'},
            ('event','EV3'): {'event_id':'EV3','title':'Vessel incident'},
        }
        self.tables = {
            'pc_terminal_details': [{'parent_port_asset_id':'PORT_B','asset_id':'PORT_TERMINAL'}],
            'pc_event_asset_links': [{'asset_id':'AIRPORT_A','event_id':'EV1'}, {'asset_id':'PORT_TERMINAL','event_id':'EV2'}],
            'pc_v_event_vessel_links': [{'mobile_asset_id':'SHIP_1','event_id':'EV3'}],
        }
    def _rows_matching_ids(self, table, column, values):
        return [r for r in self.tables.get(table,[]) if r.get(column) in values]
    def object_record(self, typ, oid):
        return self.records.get((typ,oid))
    def _local_infrastructure(self, rec, **kwargs):
        if rec.get('asset_id') == 'AIRPORT_A':
            return [{'id':'CARGO_TERMINAL','name':'Cargo Terminal','type':'asset'}]
        return []

class ResolverTests(unittest.TestCase):
    def setUp(self): self.a=Adapter()
    def test_airport_direct(self):
        x=resolve_object(self.a,'asset','AIRPORT_A')
        self.assertEqual([r['event_id'] for r in x.direct_events],['EV1'])
        self.assertEqual(len(x.facilities),1)
    def test_port_child(self):
        x=resolve_object(self.a,'asset','PORT_B')
        self.assertEqual(x.facilities[0]['id'],'PORT_TERMINAL')
        self.assertEqual([r['event_id'] for r in x.connected_events],['EV2'])
        self.assertEqual(x.direct_events,[])
    def test_mobile(self):
        x=resolve_object(self.a,'mobile_asset','SHIP_1')
        self.assertEqual(x.direct_events[0]['event_id'],'EV3')
    def test_no_geography_inference(self):
        x=resolve_object(self.a,'asset','AIRPORT_A')
        self.assertEqual(x.connected_events,[])
        self.assertFalse(x.coverage['regional_events_included'])

if __name__ == '__main__': unittest.main()
