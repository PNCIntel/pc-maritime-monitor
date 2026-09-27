"""P&C v1.5 — fresh replay + bulk connected publication.

Analyst workflow: extract files/URLs in Universal intake -> open this page ->
queue fresh replay -> process to staging -> auto-resolve safe identities -> publish
eligible canonical objects -> sync event graph -> sync agreements. Ambiguities are
held as exceptions; no manual DB IDs are required.
"""
from __future__ import annotations
import hashlib, json, uuid, re, unicodedata, os
from difflib import SequenceMatcher
from datetime import datetime, timezone
from collections import defaultdict, Counter
import streamlit as st
import pandas as pd

ID_TABLES={'pc_entities':'entity_id','pc_assets':'asset_id','pc_mobile_assets':'mobile_asset_id','pc_events':'event_id'}
NAME_COL={'pc_entities':'name','pc_assets':'name','pc_mobile_assets':'name','pc_events':'title'}
PUBLISHER_VERSION='1.6.1-saved-research-recovery'


def _norm(x):
    """Normalize spelling/punctuation/underscores for candidate discovery, not legal-entity proof."""
    x = unicodedata.normalize('NFKD', str(x or '').casefold())
    x = ''.join(c for c in x if not unicodedata.combining(c))
    return ' '.join(re.findall(r'[a-z0-9]+', x))

# Never treat these generic words as useful evidence for an entity match.
_STOP = {'port','terminal','group','company','limited','ltd','inc','international',
         'corporation','authority','services','logistics','shipping','the','of','and',
         'in','at','for','a','an','new','development','project','2026','2025'}

def _tokens(x):
    return {v for v in _norm(x).split() if len(v) >= 3 and v not in _STOP}


def _canon_registry(sb, needed):
    """Complete, paginated shared Trade/Intel canonical lookups. Fail closed if incomplete.

    Old v1.5 checked SQL IN(name) only. That misses lower-case, punctuation,
    snake-case, alternative spacing, and Port of Los Angeles in the other table.
    This reads ONLY ID/name/type/IMO/date fields from canonical tables, not data bodies.
    """
    registry = {}
    # Cross-domain search is mandatory when publishing either entities or assets.
    if {'pc_entities','pc_assets'} & set(needed):
        needed = set(needed) | {'pc_entities','pc_assets'}
    for table in sorted(needed):
        pk = ID_TABLES[table]
        cols = pk + ',' + NAME_COL[table]
        if table == 'pc_entities': cols += ',entity_type,hq_country'
        elif table == 'pc_assets': cols += ',asset_type,country'
        elif table == 'pc_mobile_assets': cols += ',imo,flag'
        elif table == 'pc_events': cols += ',start_date'
        records=[]
        batch_size=500
        max_records=25000
        for start in range(0, max_records + batch_size, batch_size):
            page=(sb.table(table).select(cols).order(pk)
                  .range(start,start+batch_size-1).execute().data or [])
            if start >= max_records and page:
                raise RuntimeError(f'{table} exceeds {max_records} identity rows: '
                                   'registry scan incomplete; publication blocked until server-side lookup is added')
            records.extend(page)
            if len(page) < batch_size: break
        registry[table] = records
    return registry


# Alias discovery is confined to unambiguous names actually present in the shared
# canonical registry. These are match candidates, never evidence of ownership.
_LEGAL_SUFFIXES = (' sa de cv', ' s a de c v', ' s a', ' sa', ' llc', ' ltd',
                   ' limited', ' inc', ' plc', ' corporation')

def _identity_aliases(value):
    raw=str(value or '').strip()
    names={_norm(raw)}
    # Official canonical names sometimes carry a second recognized identity
    # following a slash, e.g. City of LA Harbor Department / Port of Los Angeles.
    for part in re.split(r'\s+/\s+|\s+\|\s+', raw):
        if part.strip(): names.add(_norm(part))
    for name in list(names):
        # Legal endings can be removed for candidate discovery only. The full
        # registered name remains intact in the canonical record.
        for suffix in _LEGAL_SUFFIXES:
            if name.endswith(suffix) and len(name)>len(suffix)+4:
                names.add(name[:-len(suffix)].strip())
    return {v for v in names if v}


def _type_family(table,value):
    val=_norm(value)
    if not val: return ''
    words=set(val.split())
    if table=='pc_entities':
        if words & {'government','ministry','department','authority','regulator','agency','state'}:
            return 'public_body'
        if words & {'company','corporation','operator','business','enterprise','logistics','shipping','group','subsidiary','carrier','consultancy'}:
            return 'business'
        if words & {'association','union','organisation','organization','network'}:
            return 'association'
        if words & {'person','individual'}: return 'person'
        if words & {'port','terminal','zone','airport','harbour','harbor'}: return 'physical_not_entity'
    if table=='pc_assets':
        if words & {'port','harbour','harbor','seaport'}: return 'port'
        if words & {'terminal','berth','quay'}: return 'terminal'
        if words & {'zone','sez','industrial','freezone'}: return 'zone'
        if words & {'airport','airfield'}: return 'airport'
        if words & {'rail','railway','station'}: return 'rail'
        if words & {'plant','factory','refinery'}: return 'plant'
    return ''  # Unknown subtype is not evidence of a conflict.


def _type_conflict(table,source,canonical):
    a=_type_family(table,source); b=_type_family(table,canonical)
    if not (a and b): return False
    if table=='pc_assets' and {a,b}<={'port','terminal'}:
        # A port and its terminal can have identical names; hold rather than
        # conflating them, even when they sit inside one port complex.
        return a != b
    return a != b

def _identity_indexes(registry):
    ix={}
    for table,records in registry.items():
        by_name=defaultdict(list);by_imo=defaultdict(list);by_token=defaultdict(list)
        for item in records:
            name=_norm(item.get(NAME_COL[table]))
            if name:
                for alias in _identity_aliases(item.get(NAME_COL[table])):
                    by_name[alias].append(item)
            if table=='pc_mobile_assets' and item.get('imo'):
                by_imo[str(item['imo']).strip()].append(item)
            for token in _tokens(name): by_token[token].append(item)
        ix[table]={'name':by_name,'imo':by_imo,'token':by_token}
    return ix


def _identity_candidates(table,name,payload,index,registry):
    """Return exact candidates, plausible fuzzy review leads and cross-domain clashes."""
    ix=index[table]
    if table=='pc_mobile_assets' and payload.get('imo'):
        imo=str(payload['imo']).strip()
        matched=ix['imo'].get(imo,[])
        if matched: return matched,[],[], 'verified-IMO'
    key=_norm(name)
    exact=list({str(v[ID_TABLES[table]]):v for alias in _identity_aliases(name) for v in ix['name'].get(alias,[])}.values())
    if exact: return exact,[],[], 'normalized-exact-name'
    # Restrict fuzzy comparisons to indexed tokens, but search the complete registry.
    pool={}
    for token in _tokens(name):
        for r in ix['token'].get(token,[]):
            pool[str(r[ID_TABLES[table]])]=r
    fuzzy=[]
    for item in pool.values():
        other=_norm(item.get(NAME_COL[table]))
        if not other:continue
        shared=_tokens(key) & _tokens(other)
        short=min(_tokens(key),_tokens(other),key=len) if (_tokens(key) and _tokens(other)) else set()
        # E.g. Baltic Hub vs Baltic Hub Container Terminal or Los Angeles
        # vs Los Angeles Harbor Department: incomplete names are review leads.
        meaningful_subset=bool(len(shared)>=2 and short<=shared)
        acronym=bool(len(_tokens(key))==1 and next(iter(_tokens(key))).isalpha()
                     and len(next(iter(_tokens(key))))==3 and shared)
        if SequenceMatcher(None,key,other).ratio() >= 0.77 or meaningful_subset or acronym:
            fuzzy.append(item)
    # Cross-table exact names are a classification problem, NOT permission to
    # relabel the existing port as a government authority or vice versa.
    other='pc_assets' if table=='pc_entities' else 'pc_entities' if table=='pc_assets' else None
    cross=list({str(v[ID_TABLES[other]]):v for alias in _identity_aliases(name) for v in index.get(other,{}).get('name',{}).get(alias,[])}.values()) if other else []
    # A terminal may be registered as an asset under its full name while an
    # extraction proposes an abbreviated *company*. Do not create that company
    # before checking the cross-domain candidate. Never auto-merge domains.
    if other and not cross and len(_tokens(name)) >= 2:
        other_ix=index.get(other,{})
        pool={}
        for token in _tokens(name):
            for candidate in other_ix.get('token',{}).get(token,[]):
                pool[str(candidate[ID_TABLES[other]])]=candidate
        for candidate in pool.values():
            cname=candidate.get(NAME_COL[other]) or ''
            common=_tokens(name)&_tokens(cname)
            if len(common)>=2 and (common==_tokens(name) or
                                   SequenceMatcher(None,key,_norm(cname)).ratio()>=0.83):
                cross.append(candidate)
    return [],fuzzy,cross, 'name-search'


def _urls(row):
    p=row.get('payload') or {}; m=p.get('metadata') or {}; d=row.get('resolution_details') or {}
    vals=[]
    for v in (d.get('source_urls'),m.get('research_sources'),m.get('source_urls'),m.get('source_url'),p.get('source_url')):
        for x in v if isinstance(v,list) else ([v] if v else []):
            u=x.get('url') if isinstance(x,dict) else x
            if isinstance(u,str) and u.startswith(('http://','https://')) and u not in vals: vals.append(u)
    return vals

def _all_staged(sb,job):
    out=[]
    for start in range(0,5000,500):
        b=(sb.table('pc_staged_records').select('*').eq('ingestion_job_id',job)
           .order('source_record_key').range(start,start+499).execute().data or [])
        out.extend(b)
        if len(b)<500: break
    return out

def _published(sb,ids):
    out={}
    for start in range(0,len(ids),100):
        chunk=ids[start:start+100]
        if not chunk: continue
        rows=(sb.table('pc_v10_publication_items').select('staged_record_id,canonical_table,canonical_id')
              .in_('staged_record_id',chunk).execute().data or [])
        out.update({r['staged_record_id']:r for r in rows})
    return out

def _content_keys(sb,job,keys):
    found=set()
    for start in range(0,len(keys),100):
        chunk=keys[start:start+100]
        if chunk:
            rows=(sb.table('pc_v08_trade_content').select('source_record_key')
                  .eq('ingestion_job_id',job).in_('source_record_key',chunk).execute().data or [])
            found.update(r['source_record_key'] for r in rows)
    return found

def _validation_issue(row):
    """Conservative pre-publication guard; hold, never silently alter, uncertain data."""
    table = row.get('target_table') or ''
    p = row.get('payload') or {}
    name = str(p.get(NAME_COL.get(table, 'name')) or row.get('natural_key') or '').strip()
    low = _norm(name)

    # The canonical SQL DATE type cannot accept YYYY-MM. A missing day is
    # missing information, not permission to invent the first of the month.
    def walk(value, path='payload'):
        if isinstance(value, dict):
            for k, v in value.items():
                key = str(k).lower()
                if isinstance(v, str) and (key.endswith('_date') or key in ('date', 'start', 'end')):
                    if re.fullmatch(r'\d{4}-\d{2}', v.strip()):
                        return f'incomplete date {path}.{k}={v!r}; source day required'
                    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', v.strip()):
                        try: datetime.strptime(v.strip(), '%Y-%m-%d')
                        except ValueError: return f'invalid date {path}.{k}={v!r}'
                if isinstance(v, (dict, list)):
                    found = walk(v, f'{path}.{k}')
                    if found: return found
        elif isinstance(value, list):
            for i, v in enumerate(value):
                if isinstance(v, (dict, list)):
                    found = walk(v, f'{path}[{i}]')
                    if found: return found
        return None
    # Only SQL DATE columns demand day precision. JSON metadata is allowed to
    # retain source precision (e.g. seizure_date='2026-04').
    issue = walk({k:v for k,v in p.items() if k != 'metadata'})
    if issue: return issue

    if table == 'pc_entities':
        # An extractor calling a port/terminal/zone a company does not make it one.
        # Only hold when its own declared type clearly indicates infrastructure.
        if _type_family(table,p.get('entity_type'))=='physical_not_entity':
            return 'record-type review: physical infrastructure supplied as an entity'
        # Stories, strategies and industry groupings are not legal entities.
        if any(term in low for term in ('development strategy', 'advisory 20',
                  'rail freight sector', 'terminal operator 20', 'expansion project',
                  'investment announcement','autonomous centre','robotic autonomous centre')):
            return 'record-type review: development/topic supplied as an entity'
        if re.search(r'\b(advisory|expansion|redevelopment|groundbreaking|tender|strategy|delivery)\b',low):
            return 'record-type review: announcement or project supplied as an entity'
        if re.search(r'\b(centre|center)\b',low) and ('navy' in low or 'robotic' in low):
            return 'record-type review: organisational unit versus standalone company requires evidence'
    if table == 'pc_assets':
        # Equipment purchases are developments; individual cranes need
        # equipment identities before being registered as standalone assets.
        if (('cranes' in low or 'crane fleet' in low or 'rmg fleet' in low or 'rtgs' in low) and
                any(term in low for term in ('2026','sts and rtg','delivery','bolsters','expansion'))):
            return 'record-type review: equipment delivery supplied as an asset'
        if any(term in low for term in ('terminal redevelopment','terminal overhaul','container terminal redevelopment')):
            return 'record-type review: existing terminal versus redevelopment project'
        if re.search(r'\b(expansion|overhaul|delivery|procurement|upgrade)\b',low):
            return 'record-type review: development/equipment programme supplied as physical asset'
        if re.search(r'\b(cranes?|rtgs?|rmgs?)\b',low) and not p.get('equipment_serial_number'):
            return 'record-type review: unnamed equipment fleet is not an identified standalone physical asset'
        # Vessel identities belong to pc_mobile_assets, including planned hulls;
        # a vessel name embedded in an asset row must not manufacture a port asset.
        if ('van oord' in low and ('vindnes' in low or 'vestnes' in low)) or re.search(r'\b(vessel|tanker|ship)\b',low):
            return 'record-type review: vessel supplied as pc_assets; use pc_mobile_assets with verified identity'
    if table == 'pc_mobile_assets':
        imo = str(p.get('imo') or '').strip()
        if imo and (not re.fullmatch(r'\d{7}', imo)):
            return 'invalid IMO; source-backed identity review required'
    return None


def _plan(sb,job,staged):
    candidates=[r for r in staged if r['target_table'] in ID_TABLES]
    content=_content_keys(sb,job,[r['source_record_key'] for r in candidates])
    pub=_published(sb,[r['staged_record_id'] for r in candidates])
    # Research exceptions are not eligible merely because the old deterministic
    # planner would have declared them new. AI must repair or explicitly hold.
    from pc_v16_research import TABLES as V16_TABLES
    tasks=(sb.table('pc_v16_research_tasks').select('staged_record_id,status,error_text')
             .eq('ingestion_job_id',job).limit(5000).execute().data or [])
    holds={str(x['staged_record_id']):x for x in tasks if x['status']!='applied'}
    binding_rows=(sb.table('pc_v16_verified_bindings').select('staged_record_id,canonical_table,canonical_id')
             .eq('ingestion_job_id',job).limit(5000).execute().data or [])
    bindings={str(x['staged_record_id']):x for x in binding_rows}
    needed={r['target_table'] for r in candidates if r['staged_record_id'] not in pub}
    registry=_canon_registry(sb,needed)
    index=_identity_indexes(registry)
    groups=defaultdict(list)
    for r in candidates:
        if r['staged_record_id'] in pub or str(r['staged_record_id']) in holds:continue
        p=r.get('payload') or {}; table=r['target_table']
        if table=='pc_mobile_assets' and p.get('imo'):
            g=(table,'imo:'+str(p['imo']).strip())
        elif table=='pc_events':
            g=(table,_norm(p.get('title') or r['natural_key'])+'|'+str(p.get('start_date') or ''))
        else: g=(table,_norm(p.get(NAME_COL[table]) or r['natural_key']))
        groups[g].append(r)
    ready=[]; followers=[]; exceptions=[]
    for r in candidates:
        h=holds.get(str(r['staged_record_id']))
        if h and r['staged_record_id'] not in pub:
            exceptions.append({'Table':r['target_table'],'Name':r['natural_key'],
                'Reason':'AI research '+h['status']+': '+str(h.get('error_text') or 'pending evidence'),
                'Staged record ID':r['staged_record_id']})
    for g,rows in groups.items():
        leader=rows[0];table=leader['target_table'];p=leader.get('payload') or {}
        name=str(p.get(NAME_COL[table]) or leader['natural_key']).strip()
        bad=[(r,_validation_issue(r)) for r in rows]
        if any(issue for _,issue in bad):
            for row,issue in bad:
                exceptions.append({'Table':table,'Name':str((row.get('payload') or {}).get(NAME_COL[table]) or row['natural_key']),
                  'Reason':issue or 'duplicate group requires correction', 'Staged record ID':row['staged_record_id']})
            continue
        # A journalled, source-backed alias binding may resolve a fuzzy match,
        # but ONLY if the same canonical row still exists and types/countries agree.
        binding=bindings.get(str(leader['staged_record_id'])) if table!='pc_events' else None
        if binding and binding['canonical_table']==table:
            pk=ID_TABLES[table]
            hits=[x for x in registry.get(table,[]) if str(x.get(pk))==str(binding['canonical_id'])]
            if len(hits)==1:
                hit=hits[0]
                typecol='entity_type' if table=='pc_entities' else 'asset_type' if table=='pc_assets' else None
                countrycol='hq_country' if table=='pc_entities' else 'country' if table=='pc_assets' else None
                if ((not typecol or not _type_conflict(table,p.get(typecol),hit.get(typecol))) and
                    (not countrycol or not p.get(countrycol) or not hit.get(countrycol) or _norm(p[countrycol])==_norm(hit[countrycol]))):
                    for r in rows:ready.append((r,'match_existing',str(binding['canonical_id'])))
                    continue
        exact,fuzzy,cross,method=_identity_candidates(table,name,p,index,registry)
        # Event titles are not identities by themselves; match on original event date too.
        if table=='pc_events':
            date=str(p.get('start_date') or '')
            exact=[x for x in exact if str(x.get('start_date') or '')==date]
            fuzzy=[]  # Similar events must not silently be merged.
        pk=ID_TABLES[table]
        unique={str(x[pk]):x for x in exact if x.get(pk)}
        if len(unique)>1:
            exceptions.append({'Table':table,'Name':name,'Reason':'multiple canonical candidates',
                    'Candidates':', '.join(f'{x.get(NAME_COL[table])} [{x[pk]}]' for x in unique.values())})
            continue
        if len(unique)==1:
            cid=next(iter(unique))
            # Never silently bridge a unique name match when conflicting company type/region
            # evidence is present. This is an exception, not an opportunity to create a duplicate.
            hit=next(iter(unique.values()))
            tcol='entity_type' if table=='pc_entities' else 'asset_type' if table=='pc_assets' else None
            ptype=_norm(p.get(tcol)) if tcol else ''
            htype=_norm(hit.get(tcol)) if tcol else ''
            if _type_conflict(table,ptype,htype):
                exceptions.append({'Table':table,'Name':name,'Reason':'canonical name matches, verified record types differ',
                                   'Candidates':str(hit.get(pk))})
                continue
            # Divergent geographic identities with the same short name must
            # not be merged. Missing country is not a conflict by itself.
            country_field='hq_country' if table=='pc_entities' else 'country' if table=='pc_assets' else None
            if country_field and p.get(country_field) and hit.get(country_field):
                if _norm(p[country_field])!=_norm(hit[country_field]):
                    exceptions.append({'Table':table,'Name':name,'Reason':'canonical name matches but country differs',
                                       'Candidates':str(hit.get(pk))})
                    continue
            for r in rows:ready.append((r,'match_existing',cid))
            continue
        if fuzzy:
            fuzzy=sorted(fuzzy,key=lambda item:SequenceMatcher(None,_norm(name),_norm(item.get(NAME_COL[table]))).ratio(),reverse=True)
            exceptions.append({'Table':table,'Name':name,'Reason':'fuzzy canonical candidate — research before creating',
              'Candidates':', '.join(f"{x.get(NAME_COL[table])} [{x[pk]}]" for x in fuzzy[:5])})
            continue
        if cross:
            other='pc_assets' if table=='pc_entities' else 'pc_entities'
            exceptions.append({'Table':table,'Name':name,'Reason':'same-name object exists in another canonical domain — classify before creating',
              'Candidates':', '.join(f"{x.get(NAME_COL[other])} [{x[ID_TABLES[other]]}]" for x in cross[:5])})
            continue
        if table=='pc_entities' and re.fullmatch(r'[A-Za-z]{2,4}',name.strip()):
            # Short names/acronyms (QSL, etc.) have too many possible legal
            # identities for a name-only absence claim to be sufficient.
            exceptions.append({'Table':table,'Name':name,
               'Reason':'short-name entity requires authoritative identity / alias verification before creation'})
            continue
        if not _urls(leader):
            exceptions.append({'Table':table,'Name':name,'Reason':'no original source URL'})
            continue
        if table=='pc_events' and leader['source_record_key'] not in content:
            exceptions.append({'Table':table,'Name':name,'Reason':'no narrative/assessment sidecar'})
            continue
        # An absence claim can only be made after the complete registry scan.
        ready.append((leader,'create_new',None))
        for follower in rows[1:]:followers.append((follower,leader['staged_record_id']))
    return ready,followers,exceptions,pub


def _plan_digest(ready,followers,exceptions):
    """Used to invalidate stale Streamlit approvals after canonical DB changes."""
    snapshot={
      'ready':[(r['staged_record_id'],d,c) for r,d,c in ready],
      'followers':[(r['staged_record_id'],leader) for r,leader in followers],
      'exceptions':[(x.get('Staged record ID'),x.get('Table'),x.get('Name'),x.get('Reason')) for x in exceptions],
    }
    return hashlib.sha256(json.dumps(snapshot,sort_keys=True,default=str).encode()).hexdigest()

def _approval(row,decision,cid,reviewer,visible):
    return {'staged_record_id':row['staged_record_id'],'ingestion_job_id':row['ingestion_job_id'],
      'decision':decision,'canonical_id':cid,'source_verified':True,
      'event_duplicate_checked':row['target_table']=='pc_events','content_reviewed':True,
      'client_visible':bool(visible and row['target_table']=='pc_events'),'approved_by':reviewer,
      'reviewed_at':datetime.now(timezone.utc).isoformat()}

def _publish_chunk(sb,job,items,reviewer):
    if not items:return []
    approvals=[_approval(r,d,c,reviewer,True) for r,d,c in items]
    sb.table('pc_v10_approvals').upsert(approvals,on_conflict='staged_record_id').execute()
    ids=[r['staged_record_id'] for r,_,_ in items]
    backup=sb.rpc('pc_v10_backup_staged',{'p_job':job,'p_stage_ids':ids,'p_reviewer':reviewer}).execute().data
    result=sb.rpc('pc_v10_publish_approved',{'p_job':job,'p_stage_ids':ids,'p_backup':backup,'p_reviewer':reviewer}).execute().data
    return [{'backup':backup,'result':result}]

def _publish_ready(sb,job,ready,followers,reviewer):
    """Publish independently; one malformed record must not strand the batch.

    Every successful unit gets its own immutable backup. If a group fails,
    split it until the failing stage record can be reported by name.
    """
    results=[]; failures=[]
    def publish_isolated(items):
        if not items:return
        try:
            results.extend(_publish_chunk(sb,job,items,reviewer))
        except Exception as exc:
            if len(items)>1:
                mid=len(items)//2
                publish_isolated(items[:mid]);publish_isolated(items[mid:])
            else:
                row=items[0][0]
                failures.append({'Table':row['target_table'],'Name':row['natural_key'],
                   'Staged record ID':row['staged_record_id'],'Error':str(exc)[:500]})
    # Ensure canonical identity tables are handled before developments.
    priority={'pc_entities':0,'pc_assets':1,'pc_mobile_assets':2,'pc_events':3}
    ordered=sorted(ready,key=lambda item:priority.get(item[0]['target_table'],4))
    for start in range(0,len(ordered),12):publish_isolated(ordered[start:start+12])
    leader_ids=list(dict.fromkeys(leader for _,leader in followers))
    leader_map={}
    for start in range(0,len(leader_ids),100):
        rows=(sb.table('pc_v10_publication_items').select('staged_record_id,canonical_id')
              .in_('staged_record_id',leader_ids[start:start+100]).execute().data or [])
        leader_map.update({r['staged_record_id']:r['canonical_id'] for r in rows})
    follow_ready=[]
    for row,leader in followers:
        cid=leader_map.get(leader)
        if cid:follow_ready.append((row,'match_existing',cid))
        else:failures.append({'Table':row['target_table'],'Name':row['natural_key'],
          'Staged record ID':row['staged_record_id'],'Error':'package leader not published'})
    for start in range(0,len(follow_ready),12):publish_isolated(follow_ready[start:start+12])
    return results,len(follow_ready),failures

def _process_job_queue(sb,job,batch=50,max_batches=30):
    from pc_bulk_worker import process_batch, update_job_summary
    worker='pc-v15-'+uuid.uuid4().hex[:12];total=Counter();claimed=0
    for _ in range(max_batches):
        rows=sb.rpc('pc_v15_claim_job_queue',{'p_job':job,'p_worker':worker,'p_limit':batch}).execute().data or []
        if not rows:break
        claimed+=len(rows);total.update(process_batch(sb,rows,worker))
    update_job_summary(sb,job)
    return claimed,dict(total)

def render_bulk_replay(sb,active_package):
    st.header('Reload & republish — end-to-end')
    st.caption(f'Publisher build: {PUBLISHER_VERSION} · model-first classification and shared canonical matching')
    st.caption('Existing staged job → paginated shared canonical lookup + fuzzy identity hold → publish validated records → sync verified graph and agreements. No ID lookup or reload.')
    if active_package:
        st.success(f'{len(active_package):,} extracted records are in memory from Universal intake.')
    else:
        st.info('First open Universal intake, add your files / URLs and run extraction. Then return here. The extracted package stays in this Streamlit session.')
    reviewer=st.text_input('Audit name',value='DCM',key='v15_reviewer')
    title=st.text_input('Fresh replay job name',value='P&C fresh reload and republish',key='v15_title')
    c1,c2=st.columns(2)
    with c1:
        if st.button('1 · Queue FRESH replay from current extracted package',type='primary',disabled=not active_package):
            try:
                from pc_v07_core import enqueue
                # Timestamp in title makes the replay intentionally fresh rather than reusing old fingerprint title semantics.
                fresh_title=title+' · '+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
                job,count,reused=enqueue(sb,active_package,title=fresh_title,ai_research=False)
                st.session_state['v15_job']=job
                st.success(f'Fresh replay job {job} queued with {count:,} records.')
            except Exception as exc:st.error('Could not queue fresh replay: '+str(exc))
    job=st.text_input('Replay job ID',value=st.session_state.get('v15_job',''),key='v15_job_box')
    if job: st.session_state['v15_job']=job.strip()
    if not job:return
    try:
        stats={}
        for s in ('queued','processing','staged','failed'):
            q=sb.table('pc_v07_queue').select('queue_id',count='exact',head=True).eq('ingestion_job_id',job).eq('status',s).execute();stats[s]=q.count or 0
        a,b,c,d=st.columns(4);a.metric('Queued',stats['queued']);b.metric('Processing',stats['processing']);c.metric('Staged',stats['staged']);d.metric('Failed',stats['failed'])
    except Exception as exc:st.error('Cannot read replay job: '+str(exc));return
    with c2:
        if st.button('2 · Process ALL queued records in Streamlit',disabled=stats['queued']==0):
            try:
                claimed,counts=_process_job_queue(sb,job,batch=50,max_batches=40)
                st.success(f'Processed {claimed:,} queue rows. Result: {counts}.')
                st.rerun()
            except Exception as exc:st.error('Queue processing stopped: '+str(exc))
    if stats['queued'] or stats['processing']:
        st.warning('Finish queue processing before canonical publication.');return
    staged=_all_staged(sb,job)
    if not staged:st.warning('No staged rows found yet.');return
    # v1.6: model-aware AI research is IN the existing staged job, not another
    # extraction screen. Durable task state and reversible repair survive logout.
    from pc_v16_research import (enqueue_research,status_counts,process_research_batch,
        retry_failed,link_researched_events,recover_incomplete_research,requeue_stale_running)
    st.divider()
    st.subheader('AI research + repair · existing staged job')
    st.caption('Researches the original articles and authoritative leads, corrects wrong record types, '
               'creates source-backed missing object proposals and prepares event links. '
               'Progress is saved in Supabase after each record; no new ingestion job.')
    try:
        rs=status_counts(sb,job)
        cols=st.columns(5)
        for col,(label,kind) in zip(cols,[('Pending','pending'),('Repaired','applied'),
                                           ('Evidence holds','held'),('Failed','failed'),('Running','running')]):
            col.metric(label,rs[kind])
    except Exception as exc:
        st.error('AI research storage unavailable. Run the v1.6 SQL migration first: '+str(exc))
        return
    if st.button('Prepare AI research for this entire staged job',key='v16_prepare'):
        try:
            canonical=_canon_registry(sb,{'pc_entities','pc_assets','pc_mobile_assets'})
            count,prior=enqueue_research(sb,job,staged,canonical,all_records=True)
            st.success(f'Prepared {count} new persistent research tasks; {prior} already present. No re-upload.')
            st.session_state.pop('v15_plan',None)
            st.rerun()
        except Exception as exc:st.error('Could not prepare persistent research: '+str(exc))
    # Streamlit itself runs these bounded requests. Auto-continue needs the tab
    # open, but completed tasks persist and can resume safely after a restart.
    auto=st.checkbox('Continue AI research automatically while this tab stays open',
                     value=False,key='v16_autocontinue')
    chunk=st.select_slider('Research calls per pass',options=[1,2,3,5],value=2,key='v16_chunk')
    clicked=st.button('Research + repair next records',disabled=rs['pending']==0,key='v16_next')
    if rs['pending'] and (clicked or auto):
        try:
            key=st.secrets.get('OPENAI_API_KEY') or st.secrets.get('OPENAI_KEY') or os.environ.get('OPENAI_API_KEY')
            if not key:raise RuntimeError('Configure OPENAI_API_KEY in Streamlit secrets')
            with st.spinner('Researching original sources and repairing staged records...'):
                registry=_canon_registry(sb,{'pc_entities','pc_assets','pc_mobile_assets'})
                outcome=process_research_batch(sb,job,key,registry,batch_size=chunk)
            st.session_state.pop('v15_plan',None)
            st.session_state.pop('v15_confirm',None)
            st.session_state['v16_last']=outcome
            st.rerun()
        except Exception as exc:st.error('AI research pass stopped: '+str(exc))
    if st.session_state.get('v16_last'):
        st.caption('Most recent research pass: '+str(st.session_state['v16_last']))
    if rs['failed'] and st.button('Retry failed research calls',key='v16_retry'):
        count=retry_failed(sb,job);st.success(f'Requeued {count} failed tasks.');st.rerun()
    e1,e2=st.columns(2)
    with e1:
        if st.button('Recover saved research after restart',key='v16_recover'):
            try:
                result=recover_incomplete_research(sb,job)
                st.success(str(result))
                st.session_state.pop('v15_plan',None)
                st.rerun()
            except Exception as exc:st.error('Recovery stopped: '+str(exc))
    with e2:
        if rs['running'] and st.button('Requeue stale running tasks (>20 min)',key='v16_stale'):
            try:
                n=requeue_stale_running(sb,job)
                st.success(f'Requeued {n} stale tasks; active research not interrupted.')
                st.rerun()
            except Exception as exc:st.error('Stale task recovery failed: '+str(exc))
    if rs['held'] and st.button('Recover corroborated NO-CHANGE research (no API charges)',key='v161_held_recover'):
        try:
            from pc_v16_research import recover_unchanged_holds
            result=recover_unchanged_holds(sb,job)
            st.session_state['v161_recovery_report']=result
            st.session_state.pop('v15_plan',None)
            st.rerun()
        except Exception as exc:st.error('Saved research recovery stopped: '+str(exc))
    if st.session_state.get('v161_recovery_report'):
        st.info('Saved research recovery: '+str(st.session_state['v161_recovery_report'])+
                '. Released rows still go through normal canonical matching; unresolved identities remain held.')
    with st.expander('Research holds and errors'):
        held=(sb.table('pc_v16_research_tasks').select('staged_record_id,status,error_text')
                 .eq('ingestion_job_id',job).in_('status',['held','failed']).limit(250).execute().data or [])
        if held:st.dataframe(pd.DataFrame(held),hide_index=True,use_container_width=True)
        else:st.write('No research holds yet.')
    if rs['pending'] or rs['running']:
        st.warning('AI research is still in progress. Finish or pause it before approving this job. '
                   'Nothing has been published by the research worker.')
        return
    if not sum(rs.values()):
        st.warning('Prepare the AI research task list before bulk publication; no canonical records are changed by preparation.')
        return
    if st.button('3 · Analyse entire staged batch for automatic publication'):
        st.session_state.pop('v15_plan',None)
        st.session_state.pop('v15_result',None)
        st.session_state.pop('v15_confirm',None)
        try:
            ready,followers,exceptions,pub=_plan(sb,job,staged)
            st.session_state['v15_plan']={'job':job,'ready':ready,'followers':followers,'exceptions':exceptions, 'digest':_plan_digest(ready,followers,exceptions)}
        except Exception as exc:st.error('Batch analysis failed: '+str(exc))
    plan=st.session_state.get('v15_plan')
    if not plan or plan.get('job')!=job:return
    ready=plan['ready'];followers=plan['followers'];exceptions=plan['exceptions']
    e1,e2,e3=st.columns(3);e1.metric('Auto-publish eligible',len(ready)+len(followers));e2.metric('Package duplicate followers',len(followers));e3.metric('Exceptions',len(exceptions))
    if exceptions:
        with st.expander('Exceptions requiring analyst review',expanded=False):st.dataframe(pd.DataFrame(exceptions),hide_index=True,use_container_width=True)
    with st.expander('Eligible sample',expanded=False):
        st.dataframe(pd.DataFrame([{'Table':r['target_table'],'Name':(r.get('payload') or {}).get(NAME_COL.get(r['target_table'],'name')) or r['natural_key'],'Decision':d,'Canonical':c or 'NEW'} for r,d,c in ready[:200]]),hide_index=True,use_container_width=True)
    confirm=st.checkbox('I approve automatic publication of source-backed, unambiguous records; hold all exceptions.',key='v15_confirm')
    if st.button('4 · BACKUP + PUBLISH ELIGIBLE BATCH + SYNC GRAPH',type='primary',disabled=not confirm or not ready):
        try:
            # Another user/job may have created these records after the analysis page loaded.
            # No cached approval may authorize creating a duplicate on a stale registry.
            current,follow_now,except_now,pub_now=_plan(sb,job,_all_staged(sb,job))
            if _plan_digest(current,follow_now,except_now)!=plan['digest']:
                st.session_state.pop('v15_plan',None)
                st.warning('Canonical records or batch eligibility changed. Re-run step 3 to review refreshed matches before publishing.')
                return
            results,follow_count,failed_rows=_publish_ready(sb,job,current,follow_now,reviewer.strip() or 'DCM')
            graph=sb.rpc('pc_v12_sync_published_links',{'p_job':job}).execute().data
            researched_links={}
            try:
                refreshed=_canon_registry(sb,{'pc_entities','pc_assets','pc_mobile_assets'})
                idx=_identity_indexes(refreshed)
                researched_links=link_researched_events(sb,job,refreshed,
                    lambda table,name,payload,reg:_identity_candidates(table,name,payload,idx,reg))
            except Exception as exc: researched_links={'warning':str(exc)}
            agreements={}
            try:
                from pc_v14_agreement_sync import sync_published_job
                agreements=sync_published_job(sb,job,limit=500,reviewer=reviewer.strip() or 'DCM')
            except Exception as exc: agreements={'warning':str(exc)}
            st.session_state['v15_result']={'publication_batches':results,'duplicate_followers':follow_count,'graph':graph,'researched_links':researched_links,'agreements':agreements,'exceptions':exceptions,'publication_failures':failed_rows}
            if failed_rows: st.warning(f'Partial publication: {len(failed_rows)} records held after isolated publication errors. Review report, then reanalyse this same job.')
            else: st.success('Eligible batch publication finished. Check the report and LIVE Trade.')
        except Exception as exc:st.error('Publication stopped safely: '+str(exc))
    result=st.session_state.get('v15_result')
    if result:
        st.subheader('Replay & republish report')
        st.json(result,expanded=False)
        st.download_button('Download complete replay report',json.dumps(result,indent=2,default=str),file_name='pc_v15_replay_report.json',mime='application/json')
        st.info('Now open the Trade app → Connected developments → LIVE. Published companies/assets are reusable across all developments; unresolved exceptions remain staged.')
