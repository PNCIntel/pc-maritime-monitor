"""Admin-only durable extraction snapshots; never relies on Streamlit session storage."""
from datetime import datetime, timezone

TABLE = "pc_admin_intake_snapshots"

def persist_extraction(sb, records, source_stats=None, errors=None, source_reference=None):
    if not isinstance(records, list) or not records:
        raise ValueError("Cannot save an empty extraction")
    data = {"records": records,
            "source_stats": source_stats or [], "source_errors": errors or [],
            "source_reference": source_reference or "batch_upload"}
    result = sb.table(TABLE).insert({
        "label": "Universal intake · " + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "record_count": len(records), "payload": data,
    }).execute()
    rows = result.data or []
    if not rows or not rows[0].get("snapshot_id"):
        raise RuntimeError("Supabase did not confirm the extraction snapshot")
    return rows[0]["snapshot_id"]

def recent_extractions(sb, limit=10):
    return (sb.table(TABLE).select("snapshot_id,label,record_count,created_at")
            .order("created_at",desc=True).limit(limit).execute().data or [])

def recover_extraction(sb, snapshot_id):
    rows=(sb.table(TABLE).select("snapshot_id,payload,record_count")
          .eq("snapshot_id",snapshot_id).limit(1).execute().data or [])
    if not rows: raise ValueError("Extraction snapshot not found")
    data=rows[0]["payload"]
    if not isinstance(data, dict) or not isinstance(data.get("records"), list):
        raise ValueError("Snapshot payload invalid")
    if len(data["records"]) != rows[0]["record_count"]:
        raise ValueError("Snapshot record count mismatch; cannot restore")
    return data
