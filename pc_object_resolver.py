"""P&C cross-product object context. Read-only; no geography/name-based exposure inference.

All functions accept a data adapter (normally pc_terminal), which provides
_rows_matching_ids, object_record and optionally _local_infrastructure.
This keeps the resolver independent from Streamlit, secrets and a port-specific UI.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ObjectContext:
    object_type: str
    object_id: str
    facilities: list[dict] = field(default_factory=list)
    direct_events: list[dict] = field(default_factory=list)
    connected_events: list[dict] = field(default_factory=list)
    coverage: dict = field(default_factory=dict)


def _rows(adapter: Any, table: str, column: str, values: set[str]) -> list[dict]:
    if not values:
        return []
    try:
        return adapter._rows_matching_ids(table, column, tuple(sorted(values))) or []
    except Exception:
        return []  # Missing permissions/table: coverage reflects that lookup isn't exhaustive.


def _label(record: dict, fallback: str) -> str:
    return str(record.get('name') or record.get('title') or fallback)


def resolve_facilities(adapter: Any, asset_id: str, rec: dict | None = None,
                       max_depth: int = 4, max_nodes: int = 250) -> list[dict]:
    """Resolve *explicit* physical containment; no inferred owner/city-neighbor links.

    The existing generic structural traversal remains the baseline. Terminal
    parentage supplements it, but never becomes the universal infrastructure model.
    """
    rec = rec or adapter.object_record('asset', asset_id) or {}
    by_id: dict[str, dict] = {}
    try:
        existing = adapter._local_infrastructure(rec, max_depth=max_depth, max_nodes=max_nodes)
    except Exception:
        existing = []
    for row in existing:
        key = str(row.get('id') or '')
        if key and key != asset_id:
            by_id[key] = dict(row)

    frontier = {str(asset_id)}
    visited = {str(asset_id)}
    for depth in range(1, max_depth + 1):
        if not frontier or len(visited) >= max_nodes:
            break
        children = _rows(adapter, 'pc_terminal_details', 'parent_port_asset_id', frontier)
        next_frontier: set[str] = set()
        for item in children:
            child = str(item.get('asset_id') or '')
            if not child or child in visited or len(visited) >= max_nodes:
                continue
            asset = adapter.object_record('asset', child) or {}
            if not asset:
                continue
            visited.add(child)
            next_frontier.add(child)
            if child not in by_id:
                by_id[child] = {
                    'type': 'asset', 'id': child, 'name': _label(asset, child),
                    'relationship': 'contained facility', 'asset_type': asset.get('asset_type'),
                    'subtype': asset.get('subtype'), 'country': asset.get('country'),
                    'region': asset.get('region_city'), 'depth': depth,
                }
        frontier = next_frontier
    return list(by_id.values())[:max_nodes - 1]


def _event_ids(adapter: Any, obj_type: str, ids: set[str]) -> set[str]:
    found: set[str] = set()
    if obj_type == 'asset':
        for row in _rows(adapter, 'pc_event_asset_links', 'asset_id', ids):
            if row.get('event_id'):
                found.add(str(row['event_id']))
    for row in _rows(adapter, 'pc_event_links', 'linked_id', ids):
        link_type = str(row.get('linked_type') or '').lower()
        allowed = {'asset', 'infrastructure'} if obj_type == 'asset' else (
            {'entity', 'company', 'organisation', 'organization'} if obj_type == 'entity'
            else {'mobile_asset', 'vessel', 'aircraft'}
        )
        if link_type in allowed and row.get('event_id'):
            found.add(str(row['event_id']))
    # Event-vessel specialist tables, only if present. Never infer a link from names.
    if obj_type == 'mobile_asset':
        for column in ('mobile_asset_id', 'vessel_id'):
            for row in _rows(adapter, 'pc_event_vessel_links', column, ids):
                if row.get('event_id'):
                    found.add(str(row['event_id']))
        for row in _rows(adapter, 'pc_v_event_vessel_links', 'mobile_asset_id', ids):
            if row.get('event_id'):
                found.add(str(row['event_id']))
    return found


def resolve_object(adapter: Any, obj_type: str, obj_id: str, rec: dict | None = None,
                   max_depth: int = 4, max_nodes: int = 250) -> ObjectContext:
    if obj_type not in {'asset', 'entity', 'mobile_asset'}:
        raise ValueError(f'Unsupported object type: {obj_type}')
    result = ObjectContext(obj_type, str(obj_id))
    if obj_type == 'asset':
        result.facilities = resolve_facilities(adapter, str(obj_id), rec, max_depth, max_nodes)
    direct_ids = _event_ids(adapter, obj_type, {str(obj_id)})
    connected_ids: set[str] = set()
    if obj_type == 'asset':
        related_ids = {str(row['id']) for row in result.facilities if row.get('id')}
        connected_ids = _event_ids(adapter, 'asset', related_ids) - direct_ids
    # Do not classify a company-owned fleet's incidents as direct incidents on a site.
    for event_id in sorted(direct_ids):
        item = adapter.object_record('event', event_id)
        if item:
            result.direct_events.append(dict(item))
    for event_id in sorted(connected_ids):
        item = adapter.object_record('event', event_id)
        if item:
            result.connected_events.append(dict(item))
    result.coverage = {
        'facility_count': len(result.facilities),
        'direct_event_count': len(result.direct_events),
        'connected_event_count': len(result.connected_events),
        'regional_events_included': False,
        'relationship_basis': 'explicit database links only',
        'completeness_verified': False,
    }
    return result
