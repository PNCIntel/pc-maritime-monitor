"""Shared, read-only navigation of explicit production event links.
No inference from prose, geography, or similar names.
"""
import streamlit as st


def _query(db, table, column, value, limit=200):
    try:
        return db.table(table).select('*').eq(column, value).limit(limit).execute().data or [], None
    except Exception as exc:
        return [], str(exc)


def _name(db, table, key, value):
    rows, error = _query(db, table, key, value, 1)
    if error:
        return str(value), False
    return (str(rows[0].get('name') or value), True) if rows else (str(value), False)


def render_event_connections(db, event_id, navigate, *, key_prefix='connected', compact=False):
    """navigate(type, canonical_id, name) is supplied by the hosting page."""
    if db is None or not event_id:
        st.caption('Event connections unavailable.'); return
    entities, ee = _query(db, 'pc_event_entity_links', 'event_id', event_id)
    assets, ae = _query(db, 'pc_event_asset_links', 'event_id', event_id)
    graph, ge = _query(db, 'pc_event_links', 'event_id', event_id)
    if ee or ae or ge:
        st.caption('Some production relationships could not be retrieved; displayed links may be incomplete.')
    unique_entities = {(str(r.get('entity_id')), str(r.get('role')), str((r.get('metadata') or {}).get('specific_relationship') or '')):r for r in entities if r.get('entity_id')}
    unique_assets = {(str(r.get('asset_id')), str(r.get('relation_type'))):r for r in assets if r.get('asset_id')}
    # Merge explicit source-attributed generic graph edges into the same existing navigation.
    # Do not imply that membership, location context, and impact are equivalent.
    for r in graph:
        kind = str(r.get('linked_type') or '').lower()
        oid = str(r.get('linked_id') or '')
        rel = str(r.get('relationship') or 'related')
        if not oid:
            continue
        if kind in ('entity', 'company', 'organisation', 'organization'):
            if not any(k[0] == oid for k in unique_entities):
                unique_entities[(oid, rel, rel)] = {'entity_id': oid, 'role': rel,
                    'metadata': {'specific_relationship': rel},
                    'verification_status': r.get('confidence') or 'recorded'}
        elif kind in ('asset', 'infrastructure', 'port', 'canal'):
            if not any(k[0] == oid for k in unique_assets):
                unique_assets[(oid, rel)] = {'asset_id': oid, 'relation_type': rel,
                    'metadata': {'specific_relationship': rel},
                    'impact_status': 'Context only — no direct impact inferred'}
    count = len({k[0] for k in unique_entities}) + len({k[0] for k in unique_assets})
    st.caption(f'Canonical graph: {len({k[0] for k in unique_entities})} organisations · {len({k[0] for k in unique_assets})} facilities')
    if not count:
        if not ee and not ae and not ge:
            st.caption('Article-only in this relationship layer — canonical participants or assets need reconciliation. Specialist sanctions links may exist separately.')
        return
    with st.expander('Open connected companies and infrastructure', expanded=not compact):
        if unique_entities:
            st.markdown('**Organisations**')
            for i, ((cid, role, specific), link) in enumerate(unique_entities.items()):
                name, valid = _name(db, 'pc_entities', 'entity_id', cid)
                relation = (specific or role or 'related organisation').replace('_', ' ')
                left, right = st.columns([5, 1])
                left.write('**' + name + '**')
                left.caption(relation + ' · ' + str(link.get('verification_status') or 'Recorded'))
                if right.button('Open ↗', key=f'{key_prefix}_co_{event_id}_{i}', disabled=not valid):
                    navigate('entity', cid, name)
        if unique_assets:
            st.markdown('**Infrastructure**')
            for i, ((aid, rel), link) in enumerate(unique_assets.items()):
                name, valid = _name(db, 'pc_assets', 'asset_id', aid)
                meta = link.get('metadata') or {}
                specific = str(meta.get('specific_relationship') or meta.get('parent_context') or rel or 'related asset').replace('_', ' ')
                left, right = st.columns([5, 1])
                left.write('**' + name + '**')
                left.caption(specific + ' · ' + str(link.get('impact_status') or 'Recorded'))
                if right.button('Open ↗', key=f'{key_prefix}_as_{event_id}_{i}', disabled=not valid):
                    navigate('asset', aid, name)
