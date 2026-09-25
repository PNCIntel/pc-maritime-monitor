import asyncio
import json
import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple, Set
import hashlib
import re

import psycopg
from pydantic import BaseModel, Field, field_validator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("P&C_LoaderEngine")

# Explicit table ingestion ordering based on physical FK hierarchies
INGESTION_ORDER = [
    'pc_sources', 'pc_entities', 'pc_assets', 'pc_mobile_assets', 
    'pc_transport_routes', 'pc_trade_corridors', 'pc_corridor_nodes', 
    'pc_corridor_segments', 'pc_transport_services', 'pc_events', 
    'pc_event_locations', 'pc_relationships', 'pc_vessel_identity_history', 
    'pc_company_asset_roles', 'pc_transport_service_stops', 
    'pc_transport_service_mobile_assets', 'pc_corridor_route_references', 
    'pc_company_corridor_roles', 'pc_event_links', 'pc_event_corridor_links', 
    'pc_corridor_exposures'
]

# Physical constraint dictionary mapping tables to their atomic unique/conflict keys
APPLY_CONFLICT_KEYS = {
    "pc_entities": "entity_id",
    "pc_assets": "asset_id",
    "pc_mobile_assets": "mobile_asset_id",
    "pc_relationships": "relationship_id",
    "pc_events": "event_id",
    "pc_event_links": "event_link_id",
    "pc_trade_corridors": "corridor_key",
    "pc_corridor_nodes": "corridor_node_key",
    "pc_transport_services": "transport_service_id"
}

def normalize_date(v: Any) -> Optional[str]:
    if v is None: return None
    if isinstance(v, (datetime, date)): return v.isoformat()
    if isinstance(v, str):
        v = v.strip()
        if not v or v.lower() in ('nan', 'nat', 'null', 'none'): return None
        return v
    return str(v)

class BaseEnvelope(BaseModel):
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @field_validator('metadata', mode='before')
    @classmethod
    def parse_json_string(cls, v: Any) -> Any:
        if isinstance(v, str):
            try: return json.loads(v)
            except json.JSONDecodeError: pass
        return v or {}

class SourceEnvelope(BaseEnvelope):
    source_id: str
    source_name: Optional[str] = None
    publisher: Optional[str] = None
    source_type: Optional[str] = None
    url: Optional[str] = None
    active: bool = True

class EntityEnvelope(BaseEnvelope):
    entity_id: str
    name: str
    entity_type: str
    subtype: Optional[str] = None
    hq_country: Optional[str] = None
    status: Optional[str] = None
    record_status: str = "provisional"

class AssetEnvelope(BaseEnvelope):
    asset_id: str
    name: str
    asset_type: str
    subtype: Optional[str] = None
    country: Optional[str] = None
    region_city: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    status: Optional[str] = None
    record_status: str = "provisional"

class MobileAssetEnvelope(BaseEnvelope):
    mobile_asset_id: str
    name: str
    asset_type: str
    subtype: Optional[str] = None
    imo: Optional[str] = None
    mmsi: Optional[str] = None
    flag: Optional[str] = None
    status: Optional[str] = None
    record_status: str = "provisional"

class EventEnvelope(BaseEnvelope):
    event_id: str
    title: str
    start_date: Optional[str] = None
    event_nature: Optional[str] = None
    event_domain: Optional[str] = None
    event_type: Optional[str] = None
    severity: Optional[str] = None
    status: Optional[str] = None
    location: Optional[str] = None
    countries: Optional[str] = None
    record_status: str = "provisional"
    
    @field_validator('start_date', mode='before')
    @classmethod
    def check_date(cls, v: Any) -> Optional[str]: return normalize_date(v)

class RelationshipEnvelope(BaseEnvelope):
    relationship_id: str
    source_type: str
    source_id: str
    relationship_type: str
    target_type: str
    target_id: str
    record_status: str = "provisional"

class EventLinkEnvelope(BaseEnvelope):
    event_link_id: str
    event_id: str
    linked_type: str
    linked_id: str
    relationship: str
    linked_name: Optional[str] = None

class CanonicalGraphLoader:
    def __init__(self, dsn: str):
        self.dsn = dsn
        self.table_schemas = {
            'pc_sources': SourceEnvelope, 'pc_entities': EntityEnvelope,
            'pc_assets': AssetEnvelope, 'pc_mobile_assets': MobileAssetEnvelope,
            'pc_events': EventEnvelope, 'pc_relationships': RelationshipEnvelope,
            'pc_event_links': EventLinkEnvelope
        }

    @staticmethod
    def generate_deterministic_id(table: str, natural_key: str) -> str:
        """Computes clean deterministic hashes to enforce data deduplication."""
        raw_key = f"{table}|{str(natural_key).strip().lower()}"
        digest = hashlib.sha256(raw_key.encode('utf-8')).hexdigest().upper()
        prefix = {'pc_events': 'EVENT', 'pc_mobile_assets': 'MOBILE', 'pc_entities': 'ENTITY', 'pc_assets': 'ASSET'}.get(table, table[3:].upper()[:6])
        return f"{prefix}_{digest[:16]}"

    async def fetch_write_columns(self, conn, table: str) -> Set[str]:
        query = "SELECT column_name FROM information_schema.columns WHERE table_name = %s;"
        async with conn.cursor() as cur:
            await cur.execute(query, (table,))
            rows = await cur.fetchall()
            return {row[0] for row in rows}

    async def fetch_existing_identities(self, table: str) -> List[Tuple[str, str, Optional[str]]]:
        """Queries production registers to populate real-time matching tables."""
        pk = APPLY_CONFLICT_KEYS.get(table, 'id')
        name_col = 'title' if table == 'pc_events' else 'name'
        imo_col = ", imo" if table == 'pc_mobile_assets' else ""
        
        query = f"SELECT {pk}, {name_col} {imo_col} FROM {table};"
        results = []
        try:
            async with await psycopg.AsyncConnection.connect(self.dsn) as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query)
                    rows = await cur.fetchall()
                    for r in rows:
                        imo_val = r[2] if table == 'pc_mobile_assets' else None
                        results.append((str(r[0]), str(r[1]), imo_val))
        except Exception as e:
            logger.error(f"Failed to populate preflight matching pool index for {table}: {e}")
        return results

    async def ingest_package(self, payload_package: List[Dict[str, Any]]):
        sorted_package = sorted(
            payload_package,
            key=lambda x: INGESTION_ORDER.index(x['table']) if x['table'] in INGESTION_ORDER else 999
        )
        async with await psycopg.AsyncConnection.connect(self.dsn) as conn:
            for table_name in INGESTION_ORDER:
                batch_items = [row for row in sorted_package if row['table'] == table_name]
                if not batch_items: continue

                valid_columns = await self.fetch_write_columns(conn, table_name)
                schema_model = self.table_schemas.get(table_name)
                records_to_upsert = []

                for idx, item in enumerate(batch_items):
                    raw_payload = dict(item.get('payload', {}))
                    pk_col = APPLY_CONFLICT_KEYS.get(table_name)

                    if pk_col and "," not in pk_col and not raw_payload.get(pk_col):
                        natural = item.get('natural_key') or raw_payload.get('name') or raw_payload.get('title')
                        if natural: raw_payload[pk_col] = self.generate_deterministic_id(table_name, natural)
                        else: continue

                    if schema_model:
                        try:
                            validated_box = schema_model(**raw_payload)
                            cleaned_dict = validated_box.model_dump(exclude_unset=False)
                        except Exception as val_error:
                            logger.error(f"Validation failure in {table_name}: {val_error}")
                            continue
                    else:
                        cleaned_dict = raw_payload

                    final_payload = {k: v for k, v in cleaned_dict.items() if k in valid_columns}
                    records_to_upsert.append(final_payload)

                if records_to_upsert:
                    await self._execute_upsert_stream(conn, table_name, records_to_upsert)

    async def _execute_upsert_stream(self, conn, table: str, records: List[Dict[str, Any]]):
        columns = list(records[0].keys())
        conflict_target = APPLY_CONFLICT_KEYS.get(table, 'id')
        update_assignments = [f"{col} = EXCLUDED.{col}" for col in columns if col not in conflict_target.split(',')]
        
        valid_cols = await self.fetch_write_columns(conn, table)
        if "updated_at" in valid_cols:
            update_assignments.append("updated_at = now()")

        sql = f"""
            INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join(['%s'] * len(columns))})
            ON CONFLICT ({conflict_target}) DO UPDATE SET {', '.join(update_assignments)};
        """
        tuple_batch = [tuple(json.dumps(row[c]) if isinstance(row[c], (dict, list)) else row[c] for c in columns) for row in records]
        try:
            async with conn.cursor() as cur:
                await cur.executemany(sql, tuple_batch)
                await conn.commit()
        except Exception as db_ex:
            await conn.rollback()
            raise db_ex
