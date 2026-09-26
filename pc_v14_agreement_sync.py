"""v1.4 staff-only, idempotent, source-backed agreement materialization.

Reads ALREADY published events and v1.2 canonical links. A named event without
an existing canonical event and primary original source cannot create a record.
Never infers ownership or concessions from source mentions. Publication of the
canonical event and its dependencies is still controlled by v1.3.
"""
from __future__ import annotations
import hashlib
import re
from urllib.parse import urlsplit

PUBLIC_OFFICIAL_DOMAINS = ('statehouse.gov.ng', 'ogunstate.gov.ng', 'dpworld.com')


def valid_url(url):
    value = str(url or '').strip()
    parts = urlsplit(value)
    return value if parts.scheme in ('https', 'http') and parts.netloc else ''


def _sources(record):
    """Merge vetted URLs from staged evidence and associated news observations."""
    payload=record.get('payload') or {}
    meta=payload.get('metadata') or {}
    details=record.get('resolution_details') or {}
    urls=[]
    for item in (meta.get('research_sources'),meta.get('sources'),meta.get('source_urls'),
                 meta.get('source_url'),details.get('source_urls')):
        for entry in item if isinstance(item,list) else ([item] if item else []):
            u=valid_url(entry.get('url') or entry.get('source_url') if isinstance(entry,dict) else entry)
            if u and u not in urls: urls.append(u)
    return urls


def _official(url):
    host=(urlsplit(url).hostname or '').lower()
    return any(host==d or host.endswith('.'+d) for d in PUBLIC_OFFICIAL_DOMAINS)


def is_agreement(title,description):
    body=' '.join([str(title or ''),str(description or '')]).lower()
    return bool(re.search(r'\b(mous?|memorand(?:um|a) of understanding|agreement[s]?|concession[s]?|contracts?|letter[s]? of intent)\b',body))


def instrument(title):
    t=str(title or '').lower()
    if re.search(r'\b(mous?|memorand(?:um|a) of understanding)\b',t):return 'memorandum_of_understanding'
    if 'concession' in t:return 'concession'
    if 'contract' in t:return 'contract'
    if 'letter of intent' in t:return 'letter_of_intent'
    return 'agreement'


def _reported_ogun_signatory(title,name,urls):
    """Specific source-grounded Ogun MoU claim, never a general name-match inference."""
    t=str(title or '').lower();n=str(name or '').lower()
    explicit=('ogun' in t and 'dp world' in t and bool(re.search(r'\b(mous?|memorand|sign(?:s|ed)?)\b',t)))
    if not explicit or not any(_official(u) for u in urls):return False
    return n=='dp world' or 'ogun state government' in n


def _rows(sb,table,cols,**filters):
    q=sb.table(table).select(cols)
    for field,value in filters.items():q=q.eq(field,value)
    return q.limit(300).execute().data or []


def sync_one(sb,job,stage_event,reviewer='DCM'):
    """Upsert canonical event -> agreement -> verified existing endpoint links.

    Idempotent by canonical event; repeated imports of one event cannot create
    duplicate agreements. A successful group publish is a prerequisite.
    """
    if stage_event.get('target_table')!='pc_events':return {'status':'skipped','reason':'not_event'}
    stage_id=stage_event['staged_record_id'];p=stage_event.get('payload') or {}
    published=_rows(sb,'pc_v10_publication_items','canonical_id,canonical_table',staged_record_id=stage_id)
    published=[x for x in published if x.get('canonical_table')=='pc_events']
    if not published:return {'status':'pending','reason':'event_not_published'}
    event_id=published[0]['canonical_id']
    canon=_rows(sb,'pc_events','event_id,title,start_date,description',event_id=event_id)
    if not canon:return {'status':'pending','reason':'canonical_event_missing'}
    event=canon[0]; title=str(event.get('title') or p.get('title') or stage_event.get('natural_key') or '')
    desc=str(event.get('description') or p.get('description') or '')
    if not is_agreement(title,desc):return {'status':'skipped','reason':'not_agreement'}
    urls=_sources(stage_event)
    try:
        news=_rows(sb,'pc_v08_news_items','source_url',ingestion_job_id=job,source_record_key=stage_event['source_record_key'])
        for row in news:
            u=valid_url(row.get('source_url'))
            if u and u not in urls:urls.append(u)
    except Exception:pass
    if not urls:return {'status':'pending','reason':'source_url_missing'}
    # Never assert original signed documents are available based on a press release.
    agreement_id='AGR_'+hashlib.sha256(('pc_events|'+event_id).encode()).hexdigest()[:24].upper()
    agreement={'agreement_id':agreement_id,'event_id':event_id,'ingestion_job_id':job,
       'title':title,'instrument_type':instrument(title),
       'agreement_status':'announced','announced_date':event.get('start_date') or None,
       'summary':desc[:4000] if desc else None,
       'official_document_available':False,'official_document_url':None,
       'evidence':[{'url':u,'kind':'announcement_or_article'} for u in urls],
       'reviewed_by':reviewer,'staff_visible':True,'client_visible':False}
    sb.table('pc_v14_agreements').upsert(agreement,on_conflict='agreement_id').execute()
    # Link only v1.2 already-verified canonical endpoints, not unresolved staged mentions.
    links=_rows(sb,'pc_v12_published_links','linked_type,linked_id,linked_name,relationship,evidence',event_id=event_id)
    parties=[];projects=[]
    for link in links:
        if link.get('linked_type')=='entity':
            role='reported_signatory' if _reported_ogun_signatory(title,link.get('linked_name'),urls) else 'mentioned_organisation'
            parties.append({'agreement_id':agreement_id,'entity_id':link['linked_id'],
              'role':role,'evidence':{'event_link':link.get('relationship'),'article_urls':urls}})
        elif link.get('linked_type')=='asset':
            projects.append({'agreement_id':agreement_id,'asset_id':link['linked_id'],
              'relationship':'referenced_project','evidence':{'event_link':link.get('relationship'),'article_urls':urls}})
    # These are idempotent by (agreement_id, entity_id/asset_id). Empty link sets
    # remain visible as incomplete: we do not invent targets to make a full graph.
    if parties:sb.table('pc_v14_agreement_parties').upsert(parties,on_conflict='agreement_id,entity_id').execute()
    if projects:sb.table('pc_v14_agreement_projects').upsert(projects,on_conflict='agreement_id,asset_id').execute()
    return {'status':'synced' if (parties and projects) else 'partial',
            'agreement_id':agreement_id,'event_id':event_id,
            'parties':len(parties),'projects':len(projects),
            'unresolved_links':len([x for x in _rows(sb,'pc_v12_link_exceptions','staged_link_id',ingestion_job_id=job)
                if x])}


def sync_published_job(sb,job,limit=150,reviewer='DCM'):
    """Safe backfill for the EXISTING batch without rerunning ingestion/publication."""
    results=[];errors=[];offset=0
    while offset < limit:
        staged=(sb.table('pc_staged_records').select('staged_record_id,source_record_key,target_table,natural_key,payload,resolution_details')
             .eq('ingestion_job_id',job).eq('target_table','pc_events')
             .order('source_record_key').range(offset,min(offset+49,limit-1)).execute().data or [])
        if not staged:break
        published=[]
        ids=[x['staged_record_id'] for x in staged]
        if ids:
            published=(sb.table('pc_v10_publication_items').select('staged_record_id')
                       .eq('canonical_table','pc_events').in_('staged_record_id',ids)
                       .limit(50).execute().data or [])
        pubids={x['staged_record_id'] for x in published}
        for event in staged:
            if event['staged_record_id'] not in pubids:continue
            try:results.append(sync_one(sb,job,event,reviewer))
            except Exception as ex:errors.append({'development':event.get('natural_key'),'error':str(ex)})
        offset+=len(staged)
        if len(staged)<50:break
    return {'processed':len(results),'fully_linked':sum(x.get('status')=='synced' for x in results),
            'partially_linked':sum(x.get('status')=='partial' for x in results),
            'pending':sum(x.get('status')=='pending' for x in results),'errors':errors}
