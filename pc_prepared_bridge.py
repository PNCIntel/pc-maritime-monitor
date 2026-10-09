"""Read-only bridge from prepared PostgreSQL intelligence views to existing dossiers.

Requires pc_intel_network, pc_intel_object_events, pc_intel_event_details.
No database writes, no user-specific asset logic, no inferred geographic incidents.
"""
from __future__ import annotations


def query(db, table, eq=None, limit=1000):
    if db is None:
        return None
    try:
        request = db.table(table).select('*')
        for column, value in (eq or {}).items():
            request = request.eq(column, value)
        return request.limit(limit).execute().data or []
    except Exception:
        return None


def facility_network(db, object_id):
    """None means the prepared view is unavailable; [] means query succeeded empty."""
    rows = query(db, 'pc_intel_network', {'object_type': 'asset', 'object_id': str(object_id)}, 2000)
    if rows is None:
        return None
    facilities = {}
    companies = {}
    for row in rows:
        oid = str(row.get('connected_id') or '')
        if not oid:
            continue
        target = str(row.get('connected_type') or '')
        if target == 'asset' and oid != str(object_id):
            facilities[oid] = {
                'type': 'asset', 'id': oid,
                'name': row.get('connected_name') or oid,
                'relationship': str(row.get('business_relationship') or '').replace('_', ' '),
                'asset_type': row.get('connected_category'),
                'country': row.get('country'),
                'latitude': row.get('latitude'),
                'longitude': row.get('longitude'),
            }
        elif target == 'entity':
            companies[oid] = {
                'id': oid,
                'name': row.get('connected_name') or oid,
                'role': str(row.get('business_relationship') or 'associated').replace('_', ' '),
            }
    return {'facilities': list(facilities.values()), 'companies': list(companies.values())}


def object_developments(db, object_type, object_id, *, include_children=False, limit=500):
    """Explicit event links only, with complete event narratives and source evidence."""
    scope = {str(object_id)}
    if object_type == 'asset' and include_children:
        network = facility_network(db, object_id)
        if network is not None:
            scope.update(f['id'] for f in network['facilities'])
    if db is None:
        return None
    try:
        links = []
        values = sorted(scope)
        for i in range(0, len(values), 100):
            links += (db.table('pc_intel_object_events').select('*')
                      .eq('object_type', object_type)
                      .in_('object_id', values[i:i+100])
                      .limit(5000).execute().data or [])
    except Exception:
        return None
    matches = {}
    for link in links:
        if str(link.get('object_id')) in scope:
            eid = link.get('event_id')
            if eid:
                matches[str(eid)] = {'direct': str(link.get('object_id')) == str(object_id)}
    result = []
    event_details = []
    try:
        ids = list(matches)[:limit]
        for i in range(0, len(ids), 100):
            event_details += (db.table('pc_intel_event_details').select('*')
                              .in_('event_id', ids[i:i+100]).limit(200).execute().data or [])
    except Exception:
        return None
    for e in event_details:
        eid = str(e.get('event_id') or '')
        info = matches.get(eid)
        if not info:
            continue
        result.append({
            **e,
            'start_date': e.get('occurred_at'),
            'description': e.get('narrative'),
            'direct_relationship': info['direct'],
            'display_event_class': e.get('event_family') or e.get('event_type'),
        })
    result.sort(key=lambda x: str(x.get('occurred_at') or ''), reverse=True)
    return result
