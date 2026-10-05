import ast,re,unittest
from pathlib import Path

class InfrastructureRoutes(unittest.TestCase):
    def setUp(self):
        tree=ast.parse(Path(__file__).with_name('pc_terminal.py').read_text())
        names={'_infrastructure_routes','_infrastructure_service_scope','_rows_matching_ids'}
        functions=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
        for n in functions:n.decorator_list=[]
        self.tables={}
        self.ns={'_clean':lambda v:'' if v is None else str(v),'_norm':lambda v:' '.join(re.findall('[a-z0-9]+',str(v).lower()))}
        exec(compile(ast.Module(body=functions,type_ignores=[]),'terminal','exec'),self.ns)
        self.ns['_rows_matching_ids']=lambda table,col,values:[r for r in self.tables.get(table,[]) if r.get(col) in values]
    def edge(self,src,rel,dst):return {'source_type':'asset','source_id':src,'relationship_type':rel,'target_type':'asset','target_id':dst}
    def test_direct_terminal_alias_and_network_services_deduplicate(self):
        self.tables['pc_relationships']=[self.edge('oldport','alias_of','port'),self.edge('zone','located_in','port'),self.edge('terminal','located_in','zone'),self.edge('remote','rail_connected_to','port')]
        self.tables['pc_transport_services']=[{'transport_service_id':'direct','origin_asset_id':'port'},{'transport_service_id':'terminalcall'},{'transport_service_id':'aliascall'},{'transport_service_id':'network'},{'transport_service_id':'remote'},{'transport_service_id':'operatoronly','primary_operator_entity_id':'maersk'}]
        self.tables['pc_transport_service_stops']=[{'transport_service_id':'terminalcall','asset_id':'port','terminal_asset_id':'terminal'},{'transport_service_id':'aliascall','asset_id':'oldport'},{'transport_service_id':'remote','asset_id':'remote'}]
        self.tables['pc_transport_service_network_links']=[{'transport_service_id':'network','asset_id':'terminal'}]
        rows=self.ns['_infrastructure_routes']('port')
        self.assertEqual({r['_route_id'] for r in rows},{'direct','terminalcall','aliascall','network'})
        self.assertEqual(next(r for r in rows if r['_route_id']=='terminalcall')['_matched_asset_ids'],['port','terminal'])
    def test_ferry_stops_and_typed_legacy_endpoints(self):
        self.tables['pc_transport_routes']=[{'route_id':'road','origin_type':'asset','origin_id':'port'},{'route_id':'wrong','origin_type':'entity','origin_id':'port'}]
        self.tables['pc_ferry_routes']=[{'ferry_route_id':'ferry'}]
        self.tables['pc_ferry_route_stops']=[{'ferry_route_id':'ferry','stop_asset_id':'port'}]
        rows=self.ns['_infrastructure_routes']('port')
        self.assertEqual({(r['_route_kind'],r['_route_id']) for r in rows},{('route','road'),('ferry','ferry')})
    def test_graph_cycles_and_orphan_service_links(self):
        self.tables['pc_relationships']=[self.edge('port','alias_of','oldport'),self.edge('oldport','alias_of','port')]
        self.tables['pc_transport_service_stops']=[{'transport_service_id':'missing','asset_id':'oldport'}]
        self.assertEqual(self.ns['_infrastructure_service_scope']('port'),{'port','oldport'})
        self.assertEqual(self.ns['_infrastructure_routes']('port'),[])
    def test_pagination_reads_more_than_1000_rows(self):
        tree=ast.parse(Path(__file__).with_name('pc_terminal.py').read_text())
        function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_rows_matching_ids');function.decorator_list=[]
        rows=[{'id':i} for i in range(1201)]
        class Query:
            def table(self,*a):return self
            def select(self,*a):return self
            def in_(self,*a):return self
            def range(self,a,b):self.a=a;self.b=b;return self
            def execute(self):return type('Result',(),{'data':rows[self.a:self.b+1]})()
        ns={'_sb':lambda:Query()};exec(compile(ast.Module(body=[function],type_ignores=[]),'terminal','exec'),ns)
        self.assertEqual(len(ns['_rows_matching_ids']('table','column',('port',))),1201)

if __name__=='__main__':unittest.main()
