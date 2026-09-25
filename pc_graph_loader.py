"""P&C Graph Loader v0.2: batched-lookup, schema-aware, review-only multi-domain ingestion.

Integration: from pc_graph_loader import render; render(sb)
No writes to canonical domain tables. All proposals go to pc_staged_records.
"""
from __future__ import annotations
import hashlib
import io
import json
import re
from collections import Counter
from datetime import date, datetime
from typing import Any
import pandas as pd

# Parent objects precede edges. The table inventory is verified against
# the 2026-09-25 Supabase column export; FK constraints require a separate export.
SHEET_TABLE = {
    'SOURCES': 'pc_sources', 'COMPANIES':'pc_entities', 'ENTITIES':'pc_entities',
    'ASSETS':'pc_assets', 'MOBILE_ASSETS':'pc_mobile_assets', 'VESSELS':'pc_mobile_assets',
    'ROUTES':'pc_transport_routes', 'CORRIDORS':'pc_trade_corridors',
    'CORRIDOR_NODES':'pc_corridor_nodes', 'CORRIDOR_SEGMENTS':'pc_corridor_segments',
    'CORRIDOR_ROUTES':'pc_corridor_route_references',
    'COMPANY_CORRIDORS':'pc_company_corridor_roles',
    'EVENTS':'pc_events', 'EVENT_LOCATIONS':'pc_event_locations',
    'RELATIONSHIPS':'pc_relationships', 'EVENT_LINKS':'pc_event_links',
    'EVENT_CORRIDORS':'pc_event_corridor_links',
    'CORRIDOR_EXPOSURES':'pc_corridor_exposures',
    'VESSEL_IDENTITIES':'pc_vessel_identity_history',
    'COMPANY_ASSET_ROLES':'pc_company_asset_roles',
    'SERVICES':'pc_transport_services', 'SERVICE_STOPS':'pc_transport_service_stops',
    'SERVICE_ASSETS':'pc_transport_service_mobile_assets',
}
REQUIRED = {
 'pc_sources': ('source_id',),
 'pc_entities': ('entity_id','name','entity_type'),
 'pc_assets': ('asset_id','name','asset_type'),
 'pc_mobile_assets': ('mobile_asset_id','name','asset_type'),
 'pc_transport_routes': ('route_id','route_name','mode'),
 'pc_trade_corridors': ('corridor_key','corridor_name','corridor_type','status'),
 'pc_corridor_nodes': ('corridor_node_key','corridor_key','node_type','display_name'),
 'pc_corridor_segments': ('segment_key','corridor_key','mode'),
 'pc_corridor_route_references':('corridor_key','route_id','association_type','verification_status'),
 'pc_company_corridor_roles': ('company_corridor_role_id','entity_id','corridor_key','corridor_role','role_status'),
 'pc_events':('event_id','title'),
 'pc_event_locations':('event_location_id','event_id'),
 'pc_relationships':('relationship_id','source_type','source_id','relationship_type','target_type','target_id'),
 'pc_event_links':('event_link_id','event_id','linked_type','linked_id','relationship'),
 # IMPORTANT: schema requires affected_segment_key AND affected_node_key, even if the
 # event is only geographically nearby. Do not invent a meaningful segment/node.
 'pc_event_corridor_links':('event_key','corridor_key','relationship','affected_segment_key','affected_node_key'),
 'pc_corridor_exposures':('corridor_exposure_id','corridor_key','exposure_type','impact_status'),
 'pc_vessel_identity_history':('vessel_identity_history_id','mobile_asset_id','identifier_type','identifier_value','verification_status'),
 'pc_company_asset_roles':('company_asset_role_id','entity_id','asset_role','role_status'),
 'pc_transport_services':('transport_service_id','service_name','mode'),
 'pc_transport_service_stops':('transport_service_id','direction','sequence_no','asset_id'),
 'pc_transport_service_mobile_assets':('transport_service_id','mobile_asset_id','service_role'),
}
PK = {
 'pc_sources':'source_id', 'pc_entities':'entity_id','pc_assets':'asset_id',
 'pc_mobile_assets':'mobile_asset_id','pc_transport_routes':'route_id',
 'pc_trade_corridors':'corridor_key','pc_corridor_nodes':'corridor_node_key',
 'pc_corridor_segments':'segment_key', 'pc_company_corridor_roles':'company_corridor_role_id',
 'pc_events':'event_id','pc_event_locations':'event_location_id',
 'pc_relationships':'relationship_id','pc_event_links':'event_link_id',
 'pc_corridor_exposures':'corridor_exposure_id',
 'pc_vessel_identity_history':'vessel_identity_history_id',
 'pc_company_asset_roles':'company_asset_role_id',
 'pc_transport_services':'transport_service_id',
}
# References covered by the current schema. An existing canonical record OR a
# parent proposed in the same batch may satisfy a reference; we never infer
# causation, ownership, or operator status from proximity or name similarity.
REFS = {
 'pc_corridor_nodes': {'corridor_key':('pc_trade_corridors','corridor_key')},
 'pc_corridor_segments': {'corridor_key':('pc_trade_corridors','corridor_key'),
                          'from_node_key':('pc_corridor_nodes','corridor_node_key'),
                          'to_node_key':('pc_corridor_nodes','corridor_node_key')},
 'pc_corridor_route_references': {'corridor_key':('pc_trade_corridors','corridor_key'),
                                  'route_id':('pc_transport_routes','route_id')},
 'pc_company_corridor_roles': {'corridor_key':('pc_trade_corridors','corridor_key'),
                               'entity_id':('pc_entities','entity_id')},
 'pc_event_links': {'event_id':('pc_events','event_id')},
 'pc_event_locations': {'event_id':('pc_events','event_id')},
 'pc_event_corridor_links': {'event_key':('pc_events','event_id'),
                              'corridor_key':('pc_trade_corridors','corridor_key'),
                              'affected_segment_key':('pc_corridor_segments','segment_key'),
                              'affected_node_key':('pc_corridor_nodes','corridor_node_key')},
 'pc_corridor_exposures': {'event_id':('pc_events','event_id'),
                           'corridor_key':('pc_trade_corridors','corridor_key')},
 'pc_vessel_identity_history': {'mobile_asset_id':('pc_mobile_assets','mobile_asset_id')},
 'pc_company_asset_roles': {'entity_id':('pc_entities','entity_id'),
                            'asset_id':('pc_assets','asset_id'),
                            'mobile_asset_id':('pc_mobile_assets','mobile_asset_id')},
 'pc_transport_service_stops': {'transport_service_id':('pc_transport_services','transport_service_id'),
                                 'asset_id':('pc_assets','asset_id')},
 'pc_transport_service_mobile_assets':{'transport_service_id':('pc_transport_services','transport_service_id'),
                                       'mobile_asset_id':('pc_mobile_assets','mobile_asset_id')},
}
ORDER = list(dict.fromkeys(SHEET_TABLE.values()))
# dependency order overrides sheet order
ORDER = ['pc_sources','pc_entities','pc_assets','pc_mobile_assets','pc_transport_routes',
         'pc_trade_corridors','pc_corridor_nodes','pc_corridor_segments',
         'pc_transport_services','pc_events','pc_event_locations','pc_relationships',
         'pc_vessel_identity_history','pc_company_asset_roles','pc_transport_service_stops',
         'pc_transport_service_mobile_assets','pc_corridor_route_references',
         'pc_company_corridor_roles','pc_event_links','pc_event_corridor_links',
         'pc_corridor_exposures']

def norm(s): return re.sub(r'[^a-z0-9]+','_',str(s).casefold()).strip('_')
def clean(value):
    if value is None: return None
    if isinstance(value,(float,int)) and pd.isna(value): return None
    if isinstance(value,(datetime,date)): return value.isoformat()
    if isinstance(value,str):
        value=value.strip()
        if not value or value.casefold() in ('nan','nat','null','none'): return None
        if value[:1] in ('[','{'):
            try: return json.loads(value)
            except json.JSONDecodeError: pass
    return value

def digest_id(table, natural_key):
    return hashlib.sha256(f'{table}|{natural_key}'.encode()).hexdigest().upper()[:22]

def parse_upload(filename, data):
    ext=filename.rsplit('.',1)[-1].lower()
    if ext=='xlsx':
        book=pd.read_excel(io.BytesIO(data),sheet_name=None,dtype=object)
    elif ext=='csv':
        book={'EVENTS':pd.read_csv(io.BytesIO(data),dtype=object)}
    elif ext=='json':
        obj=json.loads(data)
        if not isinstance(obj,dict): raise ValueError('JSON must map sheet/table names to arrays of rows')
        book={k:pd.DataFrame(v) for k,v in obj.items() if isinstance(v,list)}
    else: raise ValueError('Use .xlsx, .csv or .json')
    result=[]
    for sheet,frame in book.items():
        table=SHEET_TABLE.get(str(sheet).upper())
        if not table: continue
        frame.columns=[norm(x) for x in frame.columns]
        frame=frame.dropna(how='all')
        for idx,row in frame.iterrows():
            payload={k:clean(v) for k,v in row.to_dict().items()}
            payload={k:v for k,v in payload.items() if v is not None}
            result.append({'sheet':sheet,'row':int(idx)+2,'table':table,'payload':payload})
    return result

def plan(upload_rows, schema, existing=None):
    """Pure planner; 'existing' maps (table,key_col,key_value)->bool.
    The planner NEVER creates inferred links or fabricates source evidence.
    """
    existing=existing or {}
    planned=[]; proposed={}
    for row in upload_rows:
        table=row['table']; payload=dict(row['payload']); columns=schema.get(table)
        reasons=[]
        if columns is None:
            reasons.append('table absent from supplied schema')
            columns=set()
        extra=set(payload)-set(columns)
        if extra:
            reasons.append('unknown columns: '+', '.join(sorted(extra)))
            payload={k:v for k,v in payload.items() if k in columns}
        pk=PK.get(table)
        if pk and not payload.get(pk):
            natural=payload.get('imo') if table=='pc_mobile_assets' else None
            natural=natural or payload.get('source_record_key') or payload.get('name') or payload.get('corridor_name') or payload.get('title')
            # Deterministic provisional keys; production matcher still decides whether existing record should be reused.
            if natural:
                prefix={'pc_events':'EVENT','pc_mobile_assets':'MOBILE','pc_entities':'ENTITY',
                        'pc_assets':'ASSET','pc_trade_corridors':'corridor'}.get(table,table[3:].upper())
                payload[pk]=f'{prefix}_{digest_id(table,natural)}'
            else: reasons.append(f'missing {pk}; supply a stable source record key')
        for field in REQUIRED.get(table,()):
            if payload.get(field) is None: reasons.append('missing required '+field)
        url=(payload.get('source_url') or (payload.get('metadata') or {}).get('source_url')
             if isinstance(payload.get('metadata') or {},dict) else payload.get('source_url'))
        if table in {'pc_mobile_assets','pc_trade_corridors','pc_corridor_nodes','pc_corridor_segments','pc_event_corridor_links'} and not (url or payload.get('source_id')):
            reasons.append('missing source evidence')
        if table=='pc_event_corridor_links' and payload.get('relationship') in ('disrupted','affected'):
            if not url: reasons.append('claimed corridor impact requires direct source URL')
        if table=='pc_mobile_assets' and not payload.get('imo'):
            reasons.append('IMO missing: identity review required before canonical creation')
        planned.append({**row,'payload':payload,'reasons':reasons})
        if pk and payload.get(pk): proposed[(table,pk,str(payload[pk]))]=True
    for item in planned:
        p=item['payload']; table=item['table']
        for field,(ref_table,ref_col) in REFS.get(table,{}).items():
            value=p.get(field)
            if value is None: continue
            if not proposed.get((ref_table,ref_col,str(value))) and not existing.get((ref_table,ref_col,str(value))):
                item['reasons'].append(f'unresolved {field} -> {ref_table}.{ref_col} ({value})')
        if table=='pc_event_links' and p.get('linked_id'):
            target={'mobile_asset':'pc_mobile_assets','vessel':'pc_mobile_assets',
                    'asset':'pc_assets','entity':'pc_entities', 'company':'pc_entities',
                    'corridor':'pc_trade_corridors'}.get(str(p.get('linked_type','')).lower())
            if target:
                pk=PK[target]
                if not proposed.get((target,pk,str(p['linked_id']))) and not existing.get((target,pk,str(p['linked_id']))):
                    item['reasons'].append('unresolved polymorphic linked_id -> '+target)
        item['decision']='REVIEW' if item['reasons'] else 'STAGE'
    planned.sort(key=lambda row:ORDER.index(row['table']) if row['table'] in ORDER else 999)
    return planned

def _chunks(values, size=75):
    """Small indexed IN sets avoid the N+1 query bottleneck and long URLs."""
    values=list(values)
    for i in range(0,len(values),size):
        yield values[i:i+size]


def lookup_existing(sb, rows, batch_size=75):
    """Batched explicit-key existence checks, with error-closed semantics.

    Reads only supplied canonical IDs and referenced keys.  A failed query is an
    error, never treated as evidence a record is absent.  Avoid full-table pulls.
    """
    requests={}
    for row in rows:
        table=row['table'];p=row['payload']
        if table in PK and p.get(PK[table]):
            requests.setdefault((table,PK[table]),set()).add(str(p[PK[table]]))
        for field,(rt,rc) in REFS.get(table,{}).items():
            if p.get(field):requests.setdefault((rt,rc),set()).add(str(p[field]))
        if table=='pc_event_links' and p.get('linked_id'):
            target={'mobile_asset':'pc_mobile_assets','vessel':'pc_mobile_assets',
              'asset':'pc_assets','entity':'pc_entities','company':'pc_entities',
              'corridor':'pc_trade_corridors'}.get(str(p.get('linked_type','')).lower())
            if target:requests.setdefault((target,PK[target]),set()).add(str(p['linked_id']))
    found={};errors=[]
    for (table,col),values in sorted(requests.items()):
        for chunk in _chunks(sorted(values),batch_size):
            try:
                response=sb.table(table).select(col).in_(col,chunk).execute()
                hits={str(hit[col]) for hit in (response.data or []) if hit.get(col) is not None}
                for value in chunk:found[(table,col,value)]=value in hits
            except Exception as exc:
                errors.append(f'{table}.{col} lookup failed: {exc}')
                # Do not mark those identities as missing: caller blocks staging.
    return found,errors


def resolve_verified_imos(sb, rows, batch_size=75):
    """Conservatively propose existing IDs for verified 7-digit IMOs only.

    These matches are reported, NOT silently rewritten: analyst review is still
    required for conflicting names, dates or repeated IMO candidates.
    """
    imos={str(r['payload']['imo']).strip() for r in rows
          if r['table']=='pc_mobile_assets' and r['payload'].get('imo')
          and re.fullmatch(r'\d{7}',str(r['payload']['imo']).strip())}
    matches={}; errors=[]
    for chunk in _chunks(sorted(imos),batch_size):
        try:
            result=sb.table('pc_mobile_assets').select('mobile_asset_id,imo,name').in_('imo',chunk).execute().data or []
            for hit in result:matches.setdefault(str(hit['imo']),[]).append(hit)
        except Exception as exc:errors.append(f'IMO lookup: {exc}')
    return matches,errors


def add_imo_match_advice(planned, matches):
    """Annotate, never overwrite canonical rows on a name-only assumption."""
    for item in planned:
        p=item['payload']
        if item['table']!='pc_mobile_assets' or not p.get('imo'):continue
        candidates=matches.get(str(p['imo']).strip(),[])
        if len(candidates)==1:
            hit=candidates[0]
            item['matched_canonical_id']=hit['mobile_asset_id']
            if p.get('mobile_asset_id')!=hit['mobile_asset_id']:
                item['reasons'].append('verified IMO points to existing canonical '+str(hit['mobile_asset_id'])+'; remap dependent links before apply')
                item['decision']='REVIEW'
        elif len(candidates)>1:
            item['reasons'].append('duplicate IMO candidates: identity conflict')
            item['decision']='REVIEW'
    return planned

def stage(sb, planned, filename, file_bytes):
    """Stage only, never touch canonical tables. REVIEW rows remain pending."""
    sha=hashlib.sha256(file_bytes).hexdigest()
    job=sb.table('pc_ingestion_jobs').insert({
       'job_type':'BULK_IMPORT', 'title':'Graph Loader | '+filename,
       'source_scope':{'file_sha256':sha,'staging_only':True,'graph_loader_version':'0.2'},
       'status':'running'
    }).execute().data[0]
    jid=job['ingestion_job_id']
    staged=[]
    for item in planned:
        p=item['payload']; pk=PK.get(item['table']); natural=str(p.get(pk) if pk else json.dumps(p,sort_keys=True,default=str))
        staged.append({'ingestion_job_id':jid,'target_table':item['table'],
           'source_record_key':f'{item["sheet"]}:{item["row"]}', 'natural_key':natural,
           'action':'REVIEW','payload':p,'confidence':0.0 if item['reasons'] else 0.95,
           'validation_status':'pending', 'review_status':'pending',
           'resolution_status':'UNRESOLVED' if item['reasons'] else 'READY',
           'resolution_details':{'graph_loader_preflight':item['reasons'],
                                  'staging_only':True}})
    try:
        for i in range(0,len(staged),100):
            sb.table('pc_staged_records').insert(staged[i:i+100]).execute()
        sb.table('pc_ingestion_jobs').update({'status':'completed','stats':{
            'staged':len(staged),'requires_review':sum(bool(x['reasons']) for x in planned),
            'file_sha256':sha,'staging_only':True}}).eq('ingestion_job_id',jid).execute()
    except Exception as exc:
        sb.table('pc_ingestion_jobs').update({'status':'failed','error_text':str(exc)}).eq('ingestion_job_id',jid).execute()
        raise
    return jid

def render(sb,schema):
    import streamlit as st
    st.title('Graph Loader v0.2 — Batch preview and stage')
    st.info('Review-only: this cannot publish canonical records. Batched indexed lookups replace N+1 calls.')
    up=st.file_uploader('Research workbook, events CSV, or multi-sheet JSON',type=['xlsx','csv','json'])
    if not up:return
    data=up.getvalue(); sha=hashlib.sha256(data).hexdigest()
    if st.session_state.get('_pc_graph_v02_hash') != sha:
        st.session_state['_pc_graph_v02_hash']=sha
        st.session_state.pop('_pc_graph_v02_preview',None)
    if st.button('Run batched preflight',type='primary'):
        try:
            rows=parse_upload(up.name,data)
            if not rows:st.error('No recognised sheets');return
            existing,errors=lookup_existing(sb,rows) if sb else ({},['No database connection'])
            matches,imo_errors=resolve_verified_imos(sb,rows) if sb else ({},[])
            errors+=imo_errors
            planned=add_imo_match_advice(plan(rows,schema,existing),matches)
            st.session_state['_pc_graph_v02_preview']={'planned':planned,'errors':errors}
        except Exception as exc:st.error(f'Preflight failed: {exc}');return
    preview=st.session_state.get('_pc_graph_v02_preview')
    if not preview:return
    planned=preview['planned'];errors=preview['errors']
    if errors:st.error('Database lookup incomplete. No staging until resolved: '+'; '.join(errors[:10]))
    st.dataframe(pd.DataFrame([{'table':r['table'],'sheet':r['sheet'],'row':r['row'],
       'decision':r['decision'],'matched_id':r.get('matched_canonical_id'),
       'issues':'; '.join(r['reasons'])} for r in planned]),use_container_width=True,hide_index=True)
    st.json(dict(Counter(r['decision'] for r in planned)))
    st.download_button('Download preflight',json.dumps(planned,default=str,indent=2),
                       'pc_graph_v02_preflight.json','application/json')
    if not errors and st.checkbox('Stage for human review; no canonical writes'):
        if st.button('Stage reviewed proposals'):
            jid=stage(sb,planned,up.name,data)
            st.success(f'Staged {len(planned)} rows: {jid}. No canonical writes.')
