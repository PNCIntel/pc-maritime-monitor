"""Publish source graph edges/sidecars using already published core endpoints.

Never creates a core identity, never guesses an ID, never reruns AI. Missing or
ambiguous endpoints and server constraint errors remain visible in the report.
"""
from collections import defaultdict
from pc_source_graph import norm, unique

ROOTS={'pc_entities':('entity','entity_id'), 'pc_assets':('asset','asset_id'),
       'pc_mobile_assets':('mobile_asset','mobile_asset_id')}

def publish_dossier_graph(sb,job,stages,pubs):
    from pc_connected_research import _hash_id, _date, _num
    publication={str(p['staged_record_id']):p for p in pubs}
    sources={}; index=defaultdict(list); events=[]
    report={'relationships':0,'event_links':0,'transactions':0,'projects':0,'contracts':0,'holds':[]}
    for stage in stages:
        payload=stage.get('payload') or {}; meta=payload.get('metadata') or {}
        if not str(meta.get('ingestion_mode') or '').startswith('AI_RESEARCH_DOSSIER'):continue
        views=meta.get('source_proposals') or [stage]
        pub=publication.get(str(stage.get('staged_record_id')))
        for view in views:
            p=view.get('payload') or {};m=p.get('metadata') or {}
            source=m.get('intake_source_key') or 'legacy'
            sources.setdefault(source,m.get('research_dossier_connected_findings') or {})
            table=stage.get('target_table') or stage.get('table')
            if not pub:continue
            if table in ROOTS:
                kind,_=ROOTS[table]
                endpoint=(kind,pub['canonical_id'])
                index[(source,norm(p.get('name')))].append(endpoint)
                for history in m.get('identity_history') or []:
                    if history.get('identifier_type')=='name':
                        index[(source,norm(history.get('identifier_value')))].append(endpoint)
            elif table=='pc_events': events.append((source,pub['canonical_id'],p,m))

    def endpoint(source,name,kind=None):
        found=list(dict.fromkeys(index.get((source,norm(name)),[])))
        if kind:found=[x for x in found if x[0]==kind]
        if len(found)!=1:raise ValueError('Endpoint missing, unpublished or ambiguous: '+str(name))
        return found[0]
    def metadata(finding):
        return {'research_sources':finding.get('source_urls') or [],
                'connected_research_job':str(job),'source_finding':finding,
                'verification_status':finding.get('verification_status') or 'reported'}
    def attempt(section,finding,fn):
        if not finding.get('source_urls'):
            report['holds'].append({'type':section,'finding':finding,'reason':'No cited evidence'});return
        try: fn();report[section]+=1
        except Exception as exc:report['holds'].append({'type':section,'finding':finding,'reason':str(exc)})

    for source,findings in sources.items():
        for rel in unique(findings.get('relationships') or []):
            def edge(rel=rel):
                src=endpoint(source,rel.get('source_name'),rel.get('source_type'))
                dst=endpoint(source,rel.get('target_name'),rel.get('target_type'))
                role=norm(rel.get('relationship')).replace(' ','_')
                if not role or '/' in str(rel.get('relationship')):raise ValueError('Unresolved relationship role')
                status=norm(rel.get('status'))
                if any(x in status for x in ('pending','proposed','preliminary','announced')) and role in {'owner','owns','owned_by','parent','subsidiary'}:
                    raise ValueError('Pending ownership must not become completed ownership')
                row={'relationship_id':_hash_id('REL',src[1],role,dst[1],rel.get('effective_from')),
                     'source_type':src[0],'source_id':src[1],'target_type':dst[0],'target_id':dst[1],
                     'relationship_type':role,'valid_from':_date(rel.get('effective_from')),
                     'valid_to':_date(rel.get('effective_to')),'confidence':'reported','record_status':'approved',
                     'notes':rel.get('evidence_summary'),'metadata':metadata(rel)}
                if rel.get('ownership_percent') is not None:row['ownership_percent']=_num(rel['ownership_percent'])
                if rel.get('operating_control') is not None:row['operating_control']=rel['operating_control']
                sb.table('pc_relationships').upsert(row,on_conflict='relationship_id').execute()
            attempt('relationships',rel,edge)

        for txn in unique(findings.get('transactions') or []):
            def transaction(t=txn):
                buyer=endpoint(source,t.get('buyer_name'),'entity')[1] if t.get('buyer_name') else None
                target=endpoint(source,t.get('target_name'),'entity')[1] if t.get('target_name') else None
                seller=endpoint(source,t.get('seller_name'),'entity')[1] if t.get('seller_name') else None
                if not target:raise ValueError('Transaction requires a published company target')
                row={'transaction_id':_hash_id('TXN',buyer,target,t.get('announced_date'),t.get('transaction_type')),
                     'buyer_entity_id':buyer,'seller_entity_id':seller,'target_entity_id':target,
                     'target_name':t.get('target_name'),'transaction_type':t.get('transaction_type'),
                     'announced_date':_date(t.get('announced_date')),'effective_date':_date(t.get('effective_date')),
                     'equity_percent':_num(t.get('equity_percent')),
                     'reported_value':_num(t.get('reported_value') if t.get('reported_value') is not None else t.get('value')),
                     'currency':t.get('currency'),'status':t.get('status'),'regulatory_status':t.get('regulatory_status'),
                     'notes':t.get('evidence_summary'),'metadata':metadata(t)}
                row['metadata']['seller_participants']=[{**part,'entity_id':endpoint(source,part['name'],'entity')[1]}
                    for part in t.get('seller_participants') or []]
                sb.table('pc_transactions').upsert(row,on_conflict='transaction_id').execute()
            attempt('transactions',txn,transaction)

        for project in unique(findings.get('projects') or []):
            def project_row(pr=project):
                aid=endpoint(source,pr.get('name'),'asset')[1]
                row={'asset_id':aid,'announced_date':_date(pr.get('announced_date')),
                     'expected_completion_date':_date(pr.get('expected_completion_date')),
                     'scope_description':pr.get('scope_description') or pr.get('evidence_summary'),
                     'source_url':pr['source_urls'][0],'metadata':metadata(pr)}
                for field in ('sponsor','developer','delivery'):
                    if pr.get(field+'_name'):row[field+'_entity_id']=endpoint(source,pr[field+'_name'],'entity')[1]
                # Taxonomy values are not inferred from free text. Status remains in metadata.
                sb.table('pc_project_details').upsert(row,on_conflict='asset_id').execute()
            attempt('projects',project,project_row)
        for contract in unique(findings.get('contracts') or []):
            def contract_row(c=contract):
                name=c.get('contract_name')
                if not name:raise ValueError('Contract requires explicit name')
                parts=[{**part,'entity_id':endpoint(source,part['name'],'entity')[1]} for part in c.get('participants') or []]
                if not parts:raise ValueError('Contract requires published participants')
                cid=_hash_id('CONTRACT',name,c.get('announced_date'))
                sb.table('pc_contracts').upsert({'contract_id':cid,'contract_name':name,
                    'contract_type':c.get('contract_type') or 'commercial_agreement','status':c.get('status') or 'reported',
                    'announced_date':_date(c.get('announced_date')),'signed_date':_date(c.get('signed_date')),
                    'effective_date':_date(c.get('effective_date')),'expiry_date':_date(c.get('expiry_date')),
                    'scope_summary':c.get('evidence_summary'),'source_url':c['source_urls'][0],
                    'metadata':metadata(c)},on_conflict='contract_id').execute()
                for part in parts:
                    old=(sb.table('pc_contract_participants').select('*').eq('contract_id',cid)
                         .eq('participant_name',part['name']).eq('role',part.get('role') or 'participant').limit(1).execute().data or [])
                    if not old:sb.table('pc_contract_participants').insert({'contract_id':cid,'entity_id':part['entity_id'],
                         'participant_name':part['name'],'role':part.get('role') or 'participant','metadata':metadata(c)}).execute()
            attempt('contracts',contract,contract_row)

    for source,eid,p,m in events:
        links=list(m.get('event_links') or [])
        for token in m.get('involved_identifiers') or []:
            kind,_,name=str(token).partition(':')
            if kind in {'entity','asset'}:links.append({'linked_type':kind,'linked_name':name,'relationship':'involved '+kind})
        for link in unique(links):
            finding={**link,'source_urls':link.get('source_urls') or m.get('research_sources') or []}
            def event_link(l=finding):
                kind,lid=endpoint(source,l.get('linked_name'),l.get('linked_type'))
                role=l.get('relationship') or 'involved '+kind
                row={'event_link_id':_hash_id('EVLINK',eid,lid,role),'event_id':eid,'linked_type':kind,
                     'linked_id':lid,'linked_name':l.get('linked_name'),'relationship':role,
                     'confidence':l.get('confidence') or 'medium','metadata':metadata(l)}
                sb.table('pc_event_links').upsert(row,on_conflict='event_link_id').execute()
            attempt('event_links',finding,event_link)
    return report
