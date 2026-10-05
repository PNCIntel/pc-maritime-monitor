"""Run without Streamlit/Supabase: python test_terminal_live_relationships.py."""
import ast
import unittest
from pathlib import Path

class TerminalRelationships(unittest.TestCase):
    def setUp(self):
        source=ast.parse(Path(__file__).with_name('pc_terminal.py').read_text())
        wanted={'_relationships','_linked_objects_from_relationships','_asset_companies','_local_infrastructure'}
        selected=[n for n in source.body if isinstance(n,ast.FunctionDef) and n.name in wanted]
        self.canonical=[]; self.indexed=[]
        self.ns={'_clean':lambda v:'' if v is None else str(v),
          '_entity_identity_bundle':lambda oid:{'ids':[oid]},
          '_filtered_rows':lambda table,col,val,limit:[r for r in self.canonical if str(r.get(col,''))==val] if table=='pc_relationships' else [],
          '_indexed_links':lambda typ,oid,limit:self.indexed,
          '_object_name':lambda typ,oid:oid,
          'object_record':lambda typ,oid:{'asset_type':'terminal','country':'Netherlands'},
          'OBJECTS':{'asset':(), 'entity':(), 'event':()}}
        exec(compile(ast.Module(body=selected,type_ignores=[]),'pc_terminal.py','exec'),self.ns)
    def edge(self,rid,kind,oid,rel):
        return {'relationship_id':rid,'source_type':kind,'source_id':oid,'relationship_type':rel,'target_type':'asset','target_id':'PORTG0242'}
    def test_partial_index_keeps_live_network(self):
        self.canonical=[self.edge('facility','asset','terminal1','located_in'),self.edge('authority','entity','authority1','manages'),self.edge('service','entity','service1','serves')]
        self.indexed=[{'link_key':'alias','source_type':'asset','source_id':'PORTG0020','target_type':'asset','target_id':'PORTG0242','relation_type':'alias_of'}]
        links=self.ns['_relationships']('asset','PORTG0242')
        self.assertEqual(len(links),4)
        infra=self.ns['_local_infrastructure']({'asset_id':'PORTG0242'})
        self.assertEqual({r['id'] for r in infra},{'terminal1','PORTG0020'})
        companies=self.ns['_asset_companies']({'asset_id':'PORTG0242'})
        self.assertEqual([r['id'] for r in companies],['authority1'])
        self.assertEqual(companies[0]['role'],'manages')
    def test_index_copy_deduplicated_and_specialist_retained(self):
        self.canonical=[self.edge('facility','asset','terminal1','located_in')]
        self.indexed=[{'link_key':'copy','source_table':'pc_relationships','source_record_id':'facility','source_type':'asset','source_id':'terminal1','target_type':'asset','target_id':'PORTG0242','relation_type':'located_in'},
         {'link_key':'special','source_table':'pc_company_asset_roles','source_type':'entity','source_id':'owner1','target_type':'asset','target_id':'PORTG0242','relation_type':'owns'}]
        self.assertEqual(len(self.ns['_relationships']('asset','PORTG0242')),2)
    def test_same_id_other_object_type_excluded(self):
        self.canonical=[{'relationship_id':'wrong','source_type':'entity','source_id':'PORTG0242','target_type':'entity','target_id':'other','relationship_type':'owns'}]
        self.assertEqual(self.ns['_relationships']('asset','PORTG0242'),[])

if __name__=='__main__': unittest.main()
