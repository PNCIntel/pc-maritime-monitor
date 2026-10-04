import io
import json
import unittest
from pc_ofac_xml import NS, records, inspect_xml, stable_id
from pc_ofac_importer import record_operations
from collections import defaultdict
from pc_document_vessels import retain_large_original, download_original


def xml(entity, extra=''):
    return ('<sanctionsData xmlns="'+NS+'"><publicationInfo><dataAsOf>2026-10-02T00:00:00-04:00</dataAsOf><filters><sanctionsLists><sanctionsList>SDN List</sanctionsList></sanctionsLists></filters></publicationInfo>'+extra+'<entities>'+entity+'</entities></sanctionsData>').encode()


def entity(eid='10', type_='Vessel', additions=''):
    return '<entity id="'+eid+'"><generalInfo><identityId>999</identityId><entityType>'+type_+'</entityType></generalInfo><sanctionsLists><sanctionsList datePublished="2026-09-01">SDN List</sanctionsList></sanctionsLists><names><name id="1"><isPrimary>true</isPrimary><isLowQuality>false</isLowQuality><translations><translation id="2"><isPrimary>true</isPrimary><script>Latin</script><formattedFullName>TEST VESSEL</formattedFullName></translation></translations></name></names>'+additions+'</entity>'


class OFACParserTests(unittest.TestCase):
    def test_source_and_identity_ids_remain_distinct(self):
        r=next(records(io.BytesIO(xml(entity()))))
        self.assertEqual(r['external_id'],'10');self.assertEqual(r['identity_id'],'999')
        self.assertEqual(r['designation_date'],'2026-09-01')

    def test_reference_dictionary_and_unknown_fields_preserved(self):
        reference='<referenceValues><referenceValue refId="8"><type>VESSEL TYPE</type><value>Tanker</value></referenceValue></referenceValues>'
        addition='<features><feature id="7"><type>VESSEL TYPE</type><valueRefId>8</valueRefId><isPrimary>true</isPrimary><novelField attr="keep">new value</novelField></feature></features>'
        metadata={};r=list(records(io.BytesIO(xml(entity(additions=addition),reference)),metadata))[0]
        self.assertEqual(r['features'][0]['value'],'Tanker')
        self.assertEqual(r['features'][0]['raw']['children'][-1]['attributes'],{'attr':'keep'})
        self.assertEqual(len(metadata['references']),1)

    def test_printed_imo_validity_and_external_relationship_are_retained(self):
        additions='<identityDocuments><identityDocument id="9"><type>Vessel Registration Identification</type><documentNumber>IMO 9251822</documentNumber><isValid>true</isValid></identityDocument></identityDocuments><relationships><relationship id="4"><type>Owned or Controlled By</type><relatedEntity entityId="300">OWNER</relatedEntity></relationship></relationships>'
        data=xml(entity(additions=additions))
        r=next(records(io.BytesIO(data)))
        self.assertEqual(r['imo'],'9251822')
        meta=inspect_xml(io.BytesIO(data))
        self.assertEqual(meta['external_relationship_targets'],['300'])
        self.assertEqual(meta['counts']['relationships'],1)

    def test_address_without_translation_is_not_discarded(self):
        r=next(records(io.BytesIO(xml(entity(additions='<addresses><address id="4"><country>UAE</country></address></addresses>')))))
        self.assertEqual(len(r['addresses']),1);self.assertEqual(r['addresses'][0]['country'],'UAE')

    def test_doctype_wrong_namespace_and_duplicate_ids_fail(self):
        samples=[xml(entity()).replace(b'<sanctionsData',b'<!DOCTYPE a [<!ENTITY x "boom">]><sanctionsData',1),
                 xml(entity()).replace(NS.encode(),b'wrong-namespace'),xml(entity()+entity())]
        for sample in samples:
            with self.assertRaises(ValueError): inspect_xml(io.BytesIO(sample))

    def test_same_imo_reuses_uae_canonical_vessel_and_does_not_overwrite_it(self):
        additions='<identityDocuments><identityDocument id="9"><type>Vessel Registration Identification</type><documentNumber>IMO 9251822</documentNumber><isValid>true</isValid></identityDocument></identityDocuments>'
        r=next(records(io.BytesIO(xml(entity(additions=additions)))))
        ctx={'existing':{},'programmes':{},'authority_id':stable_id('authority','OFAC'),
             'source_id':stable_id('source','OFAC'),'snapshot_id':stable_id('snapshot','test'),
             'document_id':stable_id('document','test'),'import_id':stable_id('import','test'),
             'data_as_of':'2026-10-02T00:00:00-04:00','source_ids':{},'canonical':{},
             'by_imo':defaultdict(list,{'9251822':['EXISTING_UAE_VESSEL']}),'endpoints':{},
             'entity_names':defaultdict(list),'mobile_names':defaultdict(list)}
        ops,did,pids=record_operations(r,ctx)
        self.assertFalse(any(o['table']=='pc_mobile_assets' for o in ops))
        link=next(o['payload'] for o in ops if o['table']=='pc_sanctions_links')
        self.assertEqual(link['linked_id'],'EXISTING_UAE_VESSEL')
        self.assertTrue(all(o['payload']['metadata']['import_id']==ctx['import_id'] for o in ops if o['table']=='pc_sanctions_aliases'))

    def test_original_chunk_manifest_round_trip(self):
        class Bucket:
            def __init__(self):self.data={}
            def download(self,path):return self.data[path]
            def upload(self,path,data,**kwargs):self.data[path]=data
        class Storage:
            def __init__(self,bucket):self.bucket=bucket
            def from_(self,name):return self.bucket
        class DB:pass
        sb=DB();bucket=Bucket();sb.storage=Storage(bucket)
        file=io.BytesIO(b'preserve exactly'*100);file.name='sdn.xml'
        stored=retain_large_original(sb,file)
        self.assertEqual(download_original(sb,stored),file.getvalue())
        manifest=json.loads(bucket.data[stored['storage_path']])
        bucket.data[manifest['chunks'][0]['path']]=b'damaged'
        with self.assertRaises(RuntimeError):download_original(sb,stored)

if __name__=='__main__':unittest.main()
