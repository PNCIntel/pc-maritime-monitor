"""Resumable, native OFAC Enhanced XML import into existing P&C sanctions tables."""
from __future__ import annotations
import hashlib
import io
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pc_ofac_xml import inspect_xml, records, stable_id, norm, SOURCE_URL, PARSER_VERSION

PKS = {'pc_source_records':'source_record_uuid','pc_sources':'source_id','pc_source_feeds':'source_feed_id','pc_source_snapshots':'source_snapshot_id',
 'pc_sanctions_authorities':'sanctions_authority_id','pc_sanctions_programmes':'sanctions_programme_id',
 'pc_sanctions_designations':'sanctions_designation_id','pc_sanctions_aliases':'sanctions_alias_id',
 'pc_sanctions_addresses':'sanctions_address_id','pc_sanctions_identifiers':'sanctions_identifier_id',
 'pc_sanctions_measures':'sanctions_measure_id','pc_sanctions_links':'sanctions_link_id',
 'pc_mobile_assets':'mobile_asset_id','pc_entities':'entity_id','pc_relationships':'relationship_id',
 'pc_vessel_identity_history':'vessel_identity_history_id','pc_document_links':'document_link_id'}


def all_rows(sb, table, columns='*'):
    out = []; start = 0
    while True:
        page = sb.table(table).select(columns).order(PKS[table]).range(start,start+499).execute().data or []
        out.extend(page)
        if len(page)<500: return out
        start += 500


def operation(table, payload):
    return {'table':table,'primary_key':PKS[table],'payload':payload}


def unique(rows, label):
    if len(rows)>1: raise ValueError('Ambiguous existing '+label+'; resolve before import')
    return rows[0] if rows else None


def context(sb, metadata, digest, stored_file, doc_id, import_id):
    authority = unique(sb.table('pc_sanctions_authorities').select('*').eq('authority_code','OFAC').limit(2).execute().data or [],'OFAC authority')
    aid = authority['sanctions_authority_id'] if authority else stable_id('authority','OFAC')
    source = unique(sb.table('pc_sources').select('*').eq('url',SOURCE_URL).limit(2).execute().data or [],'OFAC source')
    sid = source['source_id'] if source else stable_id('source','SDN')
    feed = unique(sb.table('pc_source_feeds').select('*').eq('source_id',sid).eq('parser_key',PARSER_VERSION).limit(2).execute().data or [],'OFAC XML feed')
    fid = feed['source_feed_id'] if feed else stable_id('feed',PARSER_VERSION)
    snap = stable_id('snapshot',digest)
    programmes = {r['programme_code']:r['sanctions_programme_id'] for r in (sb.table('pc_sanctions_programmes').select('sanctions_programme_id,programme_code').eq('sanctions_authority_id',aid).execute().data or [])}
    designations = all_rows(sb,'pc_sanctions_designations','sanctions_designation_id,sanctions_authority_id,source_list,source_external_id')
    existing = {}
    for row in designations:
        if str(row.get('sanctions_authority_id'))==str(aid) and row.get('source_list')=='SDN List':
            eid = str(row['source_external_id'])
            if eid in existing: raise ValueError('Duplicate OFAC source identifier '+eid)
            existing[eid]=row['sanctions_designation_id']
    mobile = all_rows(sb,'pc_mobile_assets','mobile_asset_id,name,imo,registration,asset_type,metadata')
    by_imo=defaultdict(list); names=defaultdict(list)
    for row in mobile:
        if row.get('imo'): by_imo[str(row['imo']).strip()].append(row['mobile_asset_id'])
        names[norm(row['name'])].append(row['mobile_asset_id'])
    entities = all_rows(sb,'pc_entities','entity_id,name,metadata')
    entity_names=defaultdict(list)
    for row in entities: entity_names[norm(row['name'])].append(row['entity_id'])
    links = all_rows(sb,'pc_sanctions_links','sanctions_link_id,sanctions_designation_id,linked_type,linked_id,is_direct_designation')
    canonical = {}
    for row in links:
        if row.get('is_direct_designation') and row['linked_type'] in ('entity','mobile_asset'):
            key=str(row['sanctions_designation_id'])
            target=(row['linked_type'],row['linked_id'])
            if key in canonical and canonical[key]!=target:
                canonical[key]=None
            elif key not in canonical: canonical[key]=target
    return {'authority_id':aid,'source_id':sid,'feed_id':fid,'snapshot_id':snap,'document_id':doc_id,
        'import_id':import_id,'existing':existing,'programmes':programmes,'by_imo':by_imo,
        'mobile_names':names,'entity_names':entity_names,'canonical':canonical,'endpoints':{},
        'source_ids':{},'data_as_of':metadata['data_as_of'],'digest':digest}, [
        operation('pc_sources',{'source_id':sid,'publisher':'US Treasury / OFAC','source_name':'OFAC SDN List',
            'source_type':'official','url':SOURCE_URL,'active':True}),
        operation('pc_source_feeds',{'source_feed_id':fid,'source_id':sid,'feed_name':'OFAC Enhanced SDN XML',
            'feed_type':'sanctions','format':'xml','landing_url':SOURCE_URL,'parser_key':PARSER_VERSION,
            'machine_readable':True,'requires_auth':False,'active':True}),
        operation('pc_source_snapshots',{'source_snapshot_id':snap,'source_feed_id':fid,
            'effective_date':metadata['data_as_of'][:10],'source_version':metadata['data_as_of'],
            'content_sha256':digest,'file_name':stored_file['file_name'],'storage_path':stored_file['storage_path'],
            'byte_count':metadata['byte_count'],'row_count':metadata['counts']['records'],
            'parser_version':PARSER_VERSION,'metadata':{'document_id':doc_id,'import_id':import_id,
                'expected_counts':metadata['counts'],'reference_values':metadata['references'],
                'feature_types':metadata['feature_types'],'publication_info':metadata['publication_info']}}),
        operation('pc_sanctions_authorities',{'sanctions_authority_id':aid,'authority_code':'OFAC',
            'authority_name':'US Treasury Office of Foreign Assets Control','jurisdiction':'United States',
            'official_url':'https://ofac.treasury.gov/','active':True})]


def record_operations(r, ctx):
    eid=r['external_id']; did=ctx['existing'].get(eid) or stable_id('designation',eid)
    ctx['source_ids'][eid]=did
    record_uuid = stable_id('record', ctx['digest'] if ctx.get('digest') else ctx['snapshot_id'], eid)
    out=[operation('pc_source_records', {'source_record_uuid': record_uuid, 'source_id':ctx['source_id'],
        'source_snapshot_id':ctx['snapshot_id'],'source_record_key':eid,'record_type':'sanctions_designation',
        'record_date':ctx['data_as_of'][:10],'source_url':SOURCE_URL,'title':r['primary_name'],
        'raw_record':r['raw_record'],'content_hash':hashlib.sha256(json.dumps(r['raw_record'],sort_keys=True).encode()).hexdigest(),
        'is_current':True,'metadata':{'import_id':ctx['import_id'],'ofac_external_id':eid}})]; pgids=[]
    for programme in r['programmes']:
        code=programme['code']
        pgid=ctx['programmes'].get(code) or stable_id('programme',code)
        ctx['programmes'][code]=pgid; pgids.append(pgid)
        out.append(operation('pc_sanctions_programmes',{'sanctions_programme_id':pgid,
            'sanctions_authority_id':ctx['authority_id'],'programme_code':code,'programme_name':code,
            'active':True,'metadata':{'source_reference_id':programme['ref_id']}}))
    metadata={'parser_version':PARSER_VERSION,'document_id':ctx['document_id'],'import_id':ctx['import_id'],
        'data_as_of':ctx['data_as_of'],'identity_id':r['identity_id'],'all_programme_codes':[p['code'] for p in r['programmes']],
        'features':r['features'],'relationships':r['relationships'],'sanctions_lists':r['sanctions_lists'],
        'sanctions_types':r['sanctions_types'],'legal_authorities':r['legal_authorities'],'imo_resolution':r['imo_resolution']}
    out.append(operation('pc_sanctions_designations',{'sanctions_designation_id':did,
        'sanctions_authority_id':ctx['authority_id'],'sanctions_programme_id':pgids[0] if pgids else None,
        'source_id':ctx['source_id'],'source_snapshot_id':ctx['snapshot_id'],
        'source_record_uuid':record_uuid,'source_list':'SDN List','source_external_id':eid,
        'listed_entity_type':r['entity_type'].lower(),'primary_name':r['primary_name'],
        'normalized_name':norm(r['primary_name']),'designation_date':r['designation_date'],
        'source_url':SOURCE_URL,'raw_record':r['raw_record'],'metadata':metadata}))
    for name in r['names']:
        out.append(operation('pc_sanctions_aliases',{'sanctions_alias_id':stable_id('alias',eid,name['name_id'],name['translation_id']),
            'sanctions_designation_id':did,'alias':name['name'],'normalized_alias':norm(name['name']),
            'alias_type':name['alias_type'] or ('primary' if name['is_primary_name'] else 'alias'),
            'source_record_uuid':record_uuid,'metadata':{**name,'import_id':ctx['import_id']}}))
    for ident in r['identifiers']:
        out.append(operation('pc_sanctions_identifiers',{'sanctions_identifier_id':stable_id('identifier',eid,ident['document_id']),
            'sanctions_designation_id':did,'identifier_type':ident['type'],'identifier_value':ident['value'],
            'country':ident['country'],'issuing_authority':ident['issuing_authority'],
            'source_record_uuid':record_uuid,'metadata':{**ident,'import_id':ctx['import_id']}}))
    for address in r['addresses']:
        parts=defaultdict(list)
        for part in address['parts']:
            parts[(part['type'] or '').upper()].append(part['value'] or '')
        out.append(operation('pc_sanctions_addresses',{'sanctions_address_id':stable_id('address',eid,address['address_id'],address['translation_id']),
            'sanctions_designation_id':did,'country':address['country'],
            'line1':' '.join(parts.get('ADDRESS1',[]) or parts.get('STREET ADDRESS',[])) or None,
            'line2':' '.join(parts.get('ADDRESS2',[])) or None,'city':' '.join(parts.get('CITY',[])) or None,
            'region':' '.join(parts.get('STATE/PROVINCE',[])) or None,'postal_code':' '.join(parts.get('POSTAL CODE',[])) or None,
            'source_record_uuid':record_uuid,'metadata':{**address,'import_id':ctx['import_id']}}))
    for i,measure in enumerate(r['sanctions_types']):
        out.append(operation('pc_sanctions_measures',{'sanctions_measure_id':stable_id('measure',eid,i,measure),
            'sanctions_designation_id':did,'measure_type':measure,'source_id':ctx['source_id'],'source_url':SOURCE_URL,
            'metadata':{'all_programme_codes':metadata['all_programme_codes'],'legal_authorities':r['legal_authorities']}}))
    target=ctx['canonical'].get(str(did)); reason=None
    if r['entity_type']=='Vessel':
        candidates=ctx['by_imo'].get(r['imo'],[]) if r['imo'] else []
        if len(candidates)==1: target=('mobile_asset',candidates[0])
        elif len(candidates)>1: target=None; reason='ambiguous_existing_imo'
        elif not r['imo']: target=None; reason=r['imo_resolution']
        elif target and target[0]=='mobile_asset':
            # Existing direct links still require the same verified hull identifier.
            target=None; reason='direct_link_without_matching_imo'
        else:
            vid='MOBILE_IMO_'+r['imo']; target=('mobile_asset',vid); ctx['by_imo'][r['imo']]=[vid]
            features={f['type']:f['value'] for f in r['features']}
            out.append(operation('pc_mobile_assets',{'mobile_asset_id':vid,'name':r['primary_name'],'asset_type':'vessel',
                'imo':r['imo'],'flag':features.get('Vessel Flag'),'subtype':features.get('VESSEL TYPE'),
                'call_sign':features.get('Vessel Call Sign'),'source_id':ctx['source_id'],
                'metadata':{'ofac_external_id':eid,'identity_source_snapshot':ctx['snapshot_id'],
                            'research_sources':[SOURCE_URL],'confidence':1.0}}))
    elif not target and r['entity_type']=='Entity':
        candidates=ctx['entity_names'].get(norm(r['primary_name']),[])
        if candidates: reason='existing_name_requires_identity_review'
        else:
            cid='ENTITY_OFAC_'+eid;target=('entity',cid);ctx['entity_names'][norm(r['primary_name'])]=[cid]
            out.append(operation('pc_entities',{'entity_id':cid,'name':r['primary_name'],'entity_type':'organization',
                'source_id':ctx['source_id'],'metadata':{'ofac_external_id':eid,'research_sources':[SOURCE_URL],'confidence':1.0}}))
    elif not target and r['entity_type']=='Aircraft':
        reason='aircraft_serial_and_registration_resolution_required'
    elif not target:
        reason='person_identity_resolution_required'
    if target:
        ctx['endpoints'][eid]=target
        out.append(operation('pc_sanctions_links',{'sanctions_link_id':stable_id('direct_link',eid,*target),
            'sanctions_designation_id':did,'linked_type':target[0],'linked_id':target[1],'linked_name':r['primary_name'],
            'relationship_type':'direct_designation','is_direct_designation':True,
            'match_method':'exact_imo' if r['entity_type']=='Vessel' else 'ofac_source_id',
            'match_confidence':1.0,'source_id':ctx['source_id'],
            'metadata':{'import_id':ctx['import_id'],'source_external_id':eid}}))
        out.append(operation('pc_document_links',{'document_link_id':stable_id('document_link',ctx['document_id'],*target),
            'document_id':ctx['document_id'],'linked_type':target[0],'linked_id':target[1],
            'relationship':'source_for','metadata':{'source_external_id':eid,'source_url':SOURCE_URL}}))
        if target[0]=='mobile_asset':
            for name in r['names']:
                out.append(operation('pc_vessel_identity_history',{'vessel_identity_history_id':stable_id('vessel_name',ctx['snapshot_id'],eid,name['name_id'],name['translation_id']),
                    'mobile_asset_id':target[1],'identifier_type':'name','identifier_value':name['name'],
                    'verification_status':'reported','source_id':ctx['source_id'],
                    'metadata':{'import_id':ctx['import_id'],'source_name':name}}))
            for feature in r['features']:
                if feature['type'] in ('Vessel Flag','Former Vessel Flag','Other Vessel Flag') and feature['value']:
                    out.append(operation('pc_vessel_identity_history',{'vessel_identity_history_id':stable_id('vessel_flag',ctx['snapshot_id'],eid,feature['feature_id']),
                        'mobile_asset_id':target[1],'identifier_type':'flag','identifier_value':feature['value'],
                        'verification_status':'reported','source_id':ctx['source_id'],
                        'metadata':{'import_id':ctx['import_id'],'source_feature':feature}}))
    else:
        metadata['canonical_link_hold']=reason
    return out,did,pgids


def apply_batch(sb,import_id,number,ops):
    digest=hashlib.sha256(json.dumps(ops,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    return sb.rpc('pc_apply_ofac_import_batch',{'p_import_id':import_id,'p_batch_number':number,
        'p_batch_sha256':digest,'p_operations':ops}).execute().data


def import_xml(sb, uploaded, progress=None):
    from pc_document_vessels import retain_original
    data=uploaded.getvalue(); digest=hashlib.sha256(data).hexdigest()
    metadata=inspect_xml(io.BytesIO(data)); metadata['byte_count']=len(data)
    schema=sb.rpc('pc_ofac_import_schema').execute().data
    for table in ['pc_source_records','pc_sources','pc_source_feeds','pc_source_snapshots','pc_sanctions_authorities','pc_sanctions_programmes','pc_sanctions_designations','pc_sanctions_aliases','pc_sanctions_addresses','pc_sanctions_identifiers','pc_sanctions_measures','pc_sanctions_links']:
        if not schema.get(table): raise RuntimeError('Missing sanctions model table: '+table)
    stored=retain_original(sb,uploaded)
    prior=sb.table('pc_documents').select('*').eq('file_sha256',digest).limit(2).execute().data or []
    existing=unique(prior,'source document')
    if existing: doc_id=existing['document_id']
    else:
        doc_id=stable_id('document',digest)
        sb.table('pc_documents').insert({**stored,'document_id':doc_id,'title':'OFAC SDN Enhanced XML — '+metadata['data_as_of'][:10],
            'document_type':'sanctions_list','source_name':'OFAC','source_url':SOURCE_URL,
            'published_date':metadata['data_as_of'][:10],'products':['Sanctions','Trade','Intelligence'],
            'extraction_status':'native_importing','metadata':{'document_sha256':digest,'native_xml':metadata}}).execute()
    import_id=stable_id('import',digest)
    runs=sb.table('pc_ofac_import_runs').select('*').eq('import_id',import_id).limit(1).execute().data or []
    if runs and runs[0]['status']=='complete': return runs[0]['verified_counts']
    if not runs:
        sb.table('pc_ofac_import_runs').insert({'import_id':import_id,'document_id':doc_id,'file_sha256':digest,
            'data_as_of':metadata['data_as_of'],'expected_counts':metadata['counts'],'metadata':{'source_document':stored}}).execute()
    try:
        ctx,parents=context(sb,metadata,digest,stored,doc_id,import_id)
        # Store the exact operation set once. Regenerating it after a partial run
        # could change decisions because newly-created objects now exist.
        state=(runs[0].get('metadata') or {}).get('resolver_state') if runs else None
        if state:
            for key in ('existing','programmes','by_imo','entity_names','canonical','mobile_names'):
                ctx[key]=state[key]
            ctx['by_imo']=defaultdict(list,ctx['by_imo']);ctx['entity_names']=defaultdict(list,ctx['entity_names'])
            ctx['canonical']={k:tuple(v) if v else None for k,v in ctx['canonical'].items()}
        else:
            state={key:dict(ctx[key]) for key in ('existing','programmes','by_imo','entity_names','canonical','mobile_names')}
            sb.table('pc_ofac_import_runs').update({'metadata':{'source_document':stored,'resolver_state':state}}).eq('import_id',import_id).execute()
        apply_batch(sb,import_id,0,parents)
        pending=[]; programmes=[]; batch=1; count=0; expected=metadata['counts']['records']
        parsed_meta={}
        for record in records(io.BytesIO(data),parsed_meta):
            ops,did,pgids=record_operations(record,ctx);pending.extend(ops);count+=1
            programmes.extend({'import_id':import_id,'designation_id':str(did),'programme_id':str(pid),'programme_code':p['code']}
                for p,pid in zip(record['programmes'],pgids))
            if count%50==0 or count==expected:
                apply_batch(sb,import_id,batch,pending)
                if programmes: sb.table('pc_ofac_designation_programmes').upsert(programmes,on_conflict='import_id,designation_id,programme_code').execute()
                pending=[];programmes=[];batch+=1
                if progress: progress(count/expected,f'{count:,} / {expected:,} complete source records')
        # A second pass resolves relationships using OFAC IDs, never guessed names.
        relationship_rows=[];relops=[];nrels=0
        for record in records(io.BytesIO(data)):
            source=ctx['endpoints'].get(record['external_id'])
            for rel in record['relationships']:
                target=ctx['endpoints'].get(rel['related_entity_id'])
                relationship_rows.append({'import_id':import_id,'source_relationship_id':rel['relationship_id'],
                    'source_external_id':record['external_id'],'target_external_id':rel['related_entity_id'],
                    'relationship_type':rel['type'],'target_name':rel['related_entity_name'],
                    'endpoint_status':'canonical' if source and target else 'designation_only' if rel['related_entity_id'] in ctx['source_ids'] else 'external_target',
                    'raw_record':rel['raw']})
                if source and target:
                    relops.append(operation('pc_relationships',{'relationship_id':stable_id('relationship',record['external_id'],rel['relationship_id']),
                        'source_type':source[0],'source_id':source[1],'relationship_type':rel['type'],
                        'target_type':target[0],'target_id':target[1],'evidence_source_id':ctx['source_id'],
                        'metadata':{'import_id':import_id,'ofac_source_relationship':rel}}))
                nrels+=1
                if len(relationship_rows)>=100:
                    sb.table('pc_ofac_source_relationships').upsert(relationship_rows,on_conflict='import_id,source_external_id,source_relationship_id').execute()
                    if relops: apply_batch(sb,import_id,batch,relops)
                    batch+=1;relationship_rows=[];relops=[]
        if relationship_rows:
            sb.table('pc_ofac_source_relationships').upsert(relationship_rows,on_conflict='import_id,source_external_id,source_relationship_id').execute()
            if relops: apply_batch(sb,import_id,batch,relops)
        verification={}
        # Count using snapshot provenance, not the size of the entire database.
        for table,key in [('pc_sanctions_designations','records'),('pc_sanctions_aliases','names'),
                          ('pc_sanctions_identifiers','identifiers'),('pc_sanctions_addresses','addresses'),
                          ('pc_ofac_source_relationships','relationships')]:
            query=sb.table(table).select('*',count='exact').limit(1)
            if table=='pc_ofac_source_relationships': query=query.eq('import_id',import_id)
            elif table=='pc_sanctions_designations': query=query.eq('source_snapshot_id',ctx['snapshot_id'])
            else: query=query.contains('metadata',{'import_id':import_id})
            actual=query.execute().count
            verification[key]=actual
            if actual!=metadata['counts'][key]: raise RuntimeError(f'{table}: stored {actual}, expected {metadata["counts"][key]}')
        preserved = sb.rpc('pc_verify_ofac_import', {'p_import_id':import_id,'p_snapshot_id':str(ctx['snapshot_id'])}).execute().data
        for key in ('features','legal_authorities','sanctions_types','programmes'):
            if preserved.get(key)!=metadata['counts'][key]:
                raise RuntimeError(f'Preserved {key}: {preserved.get(key)} != {metadata["counts"][key]}')
        if preserved.get('source_records')!=expected:
            raise RuntimeError('Source record count mismatch')
        verification.update(preserved)
        sb.table('pc_ofac_import_runs').update({'status':'complete','verified_counts':verification}).eq('import_id',import_id).execute()
        sb.table('pc_documents').update({'extraction_status':'native_imported'}).eq('document_id',doc_id).execute()
        try:
            sb.rpc('pc_refresh_terminal_indexes').execute()
        except Exception as exc:
            verification['search_index_refresh_error']=str(exc)[:200]
        return verification
    except Exception:
        sb.table('pc_ofac_import_runs').update({'status':'incomplete'}).eq('import_id',import_id).execute()
        raise


def render_ofac_loader(sb, uploads):
    import streamlit as st
    st.info('OFAC Enhanced XML: native import of every record and field. No OpenAI API key is needed.')
    if not st.button('Import complete OFAC XML',type='primary',key='pc_ofac_import'): return
    for uploaded in uploads:
        bar=st.progress(0,text='Validate complete OFAC export')
        try:
            report=import_xml(sb,uploaded,lambda value,label:bar.progress(value,text=label))
            bar.progress(1,text='Verified native sanctions import complete')
            st.success('Stored all source records, aliases, identifiers, addresses and relationships. Unresolved canonical identities remain evidenced sanctions records.')
            st.json(report)
        except Exception as exc:
            st.error('OFAC import incomplete: '+str(exc)+'. Apply 061_ofac_native_import.sql if the native import functions are missing. The same file can be retried without duplicating completed batches.')
