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


def preferred_id(db, object_type, object_id):
    """Resolve approved aliases; retain the original selection if unavailable."""
    result = query(db, 'pc_delivery_identity_aliases',
                   {'object_type': object_type, 'alias_object_id': str(object_id)}, 1)
    if result:
        row = result[0]
        if row.get('resolution_status') == 'reviewed':
            return str(row.get('preferred_object_id') or object_id)
    return str(object_id)


def facility_network(db, object_id):
    """Combine prepared network with verified specialist hierarchy, no guessed links.

    Returns None only when BOTH datasets cannot be queried successfully.
    """
    oid = preferred_id(db, 'asset', object_id)
    prepared = query(db, 'pc_intel_network', {'object_type': 'asset', 'object_id': oid}, 1500)
    hierarchy = query(db, 'pc_v5_infrastructure_connections', {'parent_asset_id': oid}, 1500)
    roles = query(db, 'pc_v5_infrastructure_companies', {'asset_id': oid}, 800)
    if prepared is None and hierarchy is None and roles is None:
        return None
    facilities, companies = {}, {}
    for row in prepared or []:
        target = str(row.get('connected_type') or '')
        dest = str(row.get('connected_id') or '')
        if target == 'asset' and dest and dest != oid:
            facilities[dest] = {'type':'asset','id':dest,
                'name':row.get('connected_name') or dest,
                'relationship':str(row.get('business_relationship') or 'Connected facility').replace('_',' '),
                'asset_type':row.get('connected_category'), 'country':row.get('country'),
                'latitude':row.get('latitude'), 'longitude':row.get('longitude')}
        elif target == 'entity' and dest:
            companies[dest] = {'id':dest,'name':row.get('connected_name') or dest,
                               'role':str(row.get('business_relationship') or 'Connected').replace('_',' ')}
    for row in hierarchy or []:
        dest = str(row.get('child_asset_id') or '')
        if dest and dest != oid:
            facilities[dest] = {'type':'asset','id':dest,
                'name':row.get('connected_name') or dest,
                'relationship':'; '.join(row.get('relationship_labels') or []),
                'asset_type':row.get('asset_type'),'subtype':row.get('subtype'),
                'country':row.get('country'),'latitude':row.get('latitude'),
                'longitude':row.get('longitude'),
                'operator_entity_id':row.get('operator_entity_id'),
                'operator_name':row.get('operator_name')}
    for row in roles or []:
        dest = str(row.get('entity_id') or '')
        if dest:
            companies[dest] = {'id':dest,'name':row.get('company_name') or dest,
                               'role':str(row.get('role') or 'Connected').replace('_',' ')}
    return {'facilities':list(facilities.values()), 'companies':list(companies.values()),
            'preferred_asset_id':oid}


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
