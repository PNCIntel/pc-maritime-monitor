"""Source-bounded proposals and lossless, conservative observation reconciliation."""
from copy import deepcopy
from datetime import date
import hashlib
import json
import re
from urllib.parse import urlsplit, urlunsplit


def norm(value):
    return ' '.join(re.findall(r'\w+', str(value or '').casefold()))


def source_key(url, label=''):
    if url:
        p = urlsplit(url.strip())
        value = urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path or '/', p.query, ''))
    else:
        value = 'document:' + label
    return hashlib.sha256(value.encode()).hexdigest()


def valid_imo(value):
    value = str(value or '')
    return bool(re.fullmatch(r'\d{7}', value)) and sum(int(value[i]) * (7-i) for i in range(6)) % 10 == int(value[-1])


def event_key(payload):
    """Explicit authority reference wins; fallback requires exact full context/title.

    Differently worded reports without a shared reference are candidates for review,
    never an automatic fuzzy merge. Same vessel/date alone is insufficient.
    """
    m = payload.get('metadata') or {}
    ref = m.get('incident_reference') or payload.get('incident_reference')
    authority = m.get('incident_authority') or payload.get('incident_authority')
    if ref and authority:
        return ('reference', norm(authority), norm(ref))
    ids = m.get('involved_identifiers') or payload.get('involved_identifiers') or []
    ids = sorted(set(str(x).strip() for x in ids if str(x).strip()))
    day = payload.get('start_date')
    try:
        day = date.fromisoformat(str(day)).isoformat()
    except ValueError:
        return None
    fields = [norm(payload.get(k)) for k in ('event_type', 'location', 'title')]
    if ids and all(fields):
        return ('exact_context', day, *fields, tuple(ids))
    return None


def object_key(row):
    table = row.get('table') or row.get('target_table')
    p = row.get('payload') or {}
    if table == 'pc_events':
        key = event_key(p)
        return (table, key) if key else None
    if table == 'pc_mobile_assets':
        if valid_imo(p.get('imo')):
            return (table, 'imo', str(p['imo']))
        # A name-only mobile asset has no safe physical identity for auto-merging.
        return None
    if table in {'pc_entities', 'pc_assets'}:
        country = p.get('hq_country') if table == 'pc_entities' else p.get('country')
        kind = p.get('entity_type') if table == 'pc_entities' else p.get('asset_type')
        return (table, norm(p.get('name')), norm(kind), norm(country))
    return None


def unique(values):
    out = []; seen = set()
    for value in values:
        key = json.dumps(value, sort_keys=True, default=str)
        if key not in seen:
            seen.add(key); out.append(deepcopy(value))
    return out


def observation(row):
    p = deepcopy(row.get('payload') or {})
    m = p.pop('metadata', {}) or {}
    return {'source_key': m.get('intake_source_key'), 'source_url': m.get('intake_source_url'),
            'source_label': m.get('source_label'), 'source_urls': m.get('research_sources') or [],
            'values': p, 'claims': m.get('claims') or [],
            'confidence': row.get('confidence') or m.get('extraction_confidence')}


def merge_rows(first, second):
    """Keep each source's full observation and flag conflicting scalar facts."""
    out = deepcopy(first); p = out['payload']; q = second['payload']
    m = p.setdefault('metadata', {}); n = q.get('metadata') or {}
    observations = unique((m.get('source_observations') or [observation(first)]) +
                          (n.get('source_observations') or [observation(second)]))
    conflicts = list(m.get('field_conflicts') or []) + list(n.get('field_conflicts') or [])
    for field, value in q.items():
        if field == 'metadata' or value in (None, '', []):
            continue
        if p.get(field) in (None, '', []):
            p[field] = deepcopy(value)
        elif p[field] != value:
            conflicts.append({'field': field, 'values': [deepcopy(p[field]), deepcopy(value)],
                              'status': 'unresolved'})
    for field, value in n.items():
        if isinstance(value, list):
            m[field] = unique((m.get(field) or []) + value)
        elif field not in m:
            m[field] = deepcopy(value)
        elif field == 'research_dossier_connected_findings':
            for key, vals in value.items():
                if isinstance(vals, list):
                    m[field][key] = unique((m[field].get(key) or []) + vals)
    m['source_observations'] = observations
    m['field_conflicts'] = unique(conflicts)
    if conflicts:
        m['review_required'] = True
        m['verification_status'] = 'contested'
    return out


def reconcile_records(records):
    out = []; seen = {}
    for row in records:
        row = deepcopy(row); key = object_key(row)
        if key is not None and key in seen:
            idx = seen[key]; out[idx] = merge_rows(out[idx], row)
        else:
            if key is not None: seen[key] = len(out)
            out.append(row)
    return out


def is_dossier(row):
    m = (row.get('payload') or {}).get('metadata') or {}
    return bool(m.get('dossier_version') or m.get('validated_dossier_replay') or
                str(m.get('ingestion_mode') or '').startswith('AI_RESEARCH_DOSSIER'))


def event_candidate_key(payload):
    m=payload.get('metadata') or {}
    ids=tuple(sorted(set(str(x) for x in m.get('involved_identifiers') or [])))
    day=str(payload.get('start_date') or '')[:10]
    kind=norm(payload.get('event_type')); location=norm(payload.get('location'))
    if not day or not kind or not location: return None
    if ids: return (day,kind,location,ids)
    title=norm(payload.get('title'))
    return (day,kind,location,title) if title else None


def require_unambiguous_events(records):
    """Uncertain in-batch event matches are held before any queue write."""
    seen={}
    for row in records:
        if (row.get('table') or row.get('target_table'))!='pc_events': continue
        p=row['payload']; candidate=event_candidate_key(p)
        if not candidate: continue
        if candidate in seen:
            prior=seen[candidate]; a=event_key(prior); b=event_key(p)
            # Distinct official incident references explicitly establish distinct events.
            distinct=a and b and a[0]==b[0]=='reference' and a[1]==b[1] and a!=b
            if not distinct:
                raise ValueError('Possible duplicate event needs analyst resolution before enqueue: '+
                                 str(prior.get('title'))+' / '+str(p.get('title'))+
                                 '. Supply a shared official incident reference to merge, or separate references for distinct incidents.')
        else: seen[candidate]=p


def bind_existing_events(sb, records):
    """Resolve against stored events using the same conservative event identity.

    Never use a model-generated ID. An uncertain same-asset/date candidate blocks
    enqueue for analyst review, rather than creating a second event automatically.
    Queries are bounded; exceeding the bound is a hold, not silent truncation.
    """
    out=[]
    for row in records:
        row=deepcopy(row)
        if (row.get('table') or row.get('target_table'))!='pc_events':
            out.append(row); continue
        p=row['payload']; key=event_key(p); candidates=[]
        if key and key[0]=='reference':
            m=p.get('metadata') or {}
            candidates=(sb.table('pc_events').select('*').contains('metadata',{
                'incident_reference':m.get('incident_reference') or p.get('incident_reference'),
                'incident_authority':m.get('incident_authority') or p.get('incident_authority')}).limit(201).execute().data or [])
        elif p.get('start_date'):
            candidates=(sb.table('pc_events').select('*').eq('start_date',p['start_date']).limit(201).execute().data or [])
        if key and key[0]=='reference' and p.get('start_date'):
            daily=(sb.table('pc_events').select('*').eq('start_date',p['start_date']).limit(201).execute().data or [])
            candidates=unique(candidates+daily)
        if len(candidates)>200:
            raise ValueError('Event candidate limit exceeded; event resolution needs analyst review')
        exact=[c for c in candidates if key and event_key(c)==key]
        if len(exact)>1:
            raise ValueError('Multiple canonical events share the incident identity; resolve duplicates before enqueue')
        if not exact:
            candidate=event_candidate_key(p)
            possible=[c for c in candidates if candidate and event_candidate_key(c)==candidate]
            # Different official references demonstrate distinct incidents; otherwise hold.
            possible=[c for c in possible if not (key and event_key(c) and
                      key[0]==event_key(c)[0]=='reference' and key[1]==event_key(c)[1] and key!=event_key(c))]
            if possible:
                raise ValueError('Possible match to an existing event needs analyst resolution: '+str(p.get('title')))
        if exact:
            existing=exact[0]
            row=merge_rows({'table':'pc_events','natural_key':existing['title'],'payload':existing},row)
            row['payload']['event_id']=existing['event_id']
            row['natural_key']=existing['title']
            row['payload'].setdefault('metadata',{})['event_resolution']='matched_existing_strong_identity'
        out.append(row)
    return out
