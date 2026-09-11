#!/usr/bin/env python3
"""Populate P&C port metrics from the public IMF PortWatch daily port layer.

Writes:
- pc_observations
- pc_port_metrics

Matching is conservative and operates only against existing canonical pc_assets.
It does NOT create new canonical ports automatically.

Examples:
  python scripts/ingest_portwatch.py
  python scripts/ingest_portwatch.py --min-score 0.82
  python scripts/ingest_portwatch.py --limit-ports 100
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlencode

import requests

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "shared"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

from pc_db import client

PORTWATCH_QUERY_URL = (
    "https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services/"
    "Daily_Ports_Data/FeatureServer/0/query"
)
SOURCE_ID = "SRC_OPEN_IMF_PORTWATCH"
PAGE_SIZE = 1000

FIELDS = [
    "date", "year", "month", "day", "portid", "portname", "country", "ISO3",
    "portcalls_container", "portcalls_dry_bulk", "portcalls_general_cargo",
    "portcalls_roro", "portcalls_tanker", "portcalls_cargo", "portcalls",
    "import_container", "import_dry_bulk", "import_general_cargo", "import_roro",
    "import_tanker", "import_cargo", "import",
    "export_container", "export_dry_bulk", "export_general_cargo", "export_roro",
    "export_tanker", "export_cargo", "export", "ObjectId",
]

METRICS = {
    "portcalls": ("vessel_calls", "calls"),
    "portcalls_container": ("container_vessel_calls", "calls"),
    "portcalls_tanker": ("tanker_vessel_calls", "calls"),
    "portcalls_dry_bulk": ("dry_bulk_vessel_calls", "calls"),
    "portcalls_roro": ("roro_vessel_calls", "calls"),
    "import": ("estimated_import_volume", "metric_tons"),
    "export": ("estimated_export_volume", "metric_tons"),
    "import_container": ("estimated_container_import_volume", "metric_tons"),
    "export_container": ("estimated_container_export_volume", "metric_tons"),
    "import_tanker": ("estimated_tanker_import_volume", "metric_tons"),
    "export_tanker": ("estimated_tanker_export_volume", "metric_tons"),
}


def norm_name(value):
    s = str(value or "").strip().casefold()
    s = s.replace("&", " and ")
    s = re.sub(r"\b(port of|port|harbour|harbor|terminal|terminals|seaport)\b", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def req(params):
    r = requests.get(
        PORTWATCH_QUERY_URL,
        params=params,
        headers={"User-Agent": "PowerAndCorridors-Research/1.0"},
        timeout=25,
    )
    r.raise_for_status()
    payload = r.json()
    if "error" in payload:
        raise RuntimeError(str(payload["error"]))
    return payload


def latest_day():
    payload = req({
        "where": "1=1",
        "outFields": "date,year,month,day,ObjectId",
        "orderByFields": "date DESC,ObjectId DESC",
        "resultRecordCount": 1,
        "returnGeometry": "false",
        "f": "json",
    })
    f = payload.get("features") or []
    if not f:
        raise RuntimeError("PortWatch returned no records.")
    a = f[0]["attributes"]
    return int(a["year"]), int(a["month"]), int(a["day"])


def fetch_day(y, m, d):
    where = f"year={y} AND month={m} AND day={d}"
    rows = []
    offset = 0

    while True:
        payload = req({
            "where": where,
            "outFields": ",".join(FIELDS),
            "orderByFields": "ObjectId ASC",
            "resultOffset": offset,
            "resultRecordCount": PAGE_SIZE,
            "returnGeometry": "false",
            "f": "json",
        })

        batch = [x.get("attributes", {}) for x in payload.get("features", [])]
        rows.extend(batch)

        exceeded = bool(payload.get("exceededTransferLimit", False))
        if not batch or (len(batch) < PAGE_SIZE and not exceeded):
            break

        offset += len(batch)
        if offset > 30000:
            raise RuntimeError("PortWatch pagination safety limit reached.")

    return rows


def asset_is_port(row):
    blob = " ".join([
        str(row.get("asset_type") or ""),
        str(row.get("subtype") or ""),
        str(row.get("name") or ""),
    ]).casefold()
    return any(x in blob for x in ["port", "terminal", "harbour", "harbor"])


def match_port(asset, live_rows):
    cname = norm_name(asset.get("name"))
    ccountry = str(asset.get("country") or "").strip().casefold()
    if not cname:
        return None, 0.0

    best = None
    best_score = 0.0

    for row in live_rows:
        pname = norm_name(row.get("portname"))
        if not pname:
            continue

        score = 0.0
        if pname == cname:
            score = 1.0
        elif pname in cname or cname in pname:
            score = 0.91
        else:
            score = SequenceMatcher(None, cname, pname).ratio()

        if ccountry and str(row.get("country") or "").strip().casefold() == ccountry:
            score = min(1.0, score + 0.05)

        if score > best_score:
            best, best_score = row, score

    return best, best_score


def ensure_source(sb):
    sb.table("pc_sources").upsert({
        "source_id": SOURCE_ID,
        "publisher": "International Monetary Fund",
        "source_name": "IMF PortWatch",
        "source_type": "public operational dataset",
        "coverage": "Daily port calls and estimated shipment volumes",
        "url": "https://portwatch.imf.org/",
        "reliability": "high",
        "ingestion_method": "public ArcGIS FeatureServer",
        "license_name": "Verify dataset terms before redistribution",
        "redistribution_status": "attribution_required",
        "attribution_required": True,
        "terms_url": "https://portwatch.imf.org/",
        "active": True,
        "notes": "Imported as attributed operational context; methodology and revisions follow IMF PortWatch.",
    }, on_conflict="source_id").execute()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-score", type=float, default=0.80)
    ap.add_argument("--limit-ports", type=int, default=0)
    args = ap.parse_args()

    sb = client(service=True)
    if sb is None:
        raise SystemExit("Configure SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY first.")

    ensure_source(sb)

    y, m, d = latest_day()
    obs_date = f"{y:04d}-{m:02d}-{d:02d}"
    live = fetch_day(y, m, d)

    assets = sb.table("pc_assets").select(
        "asset_id,name,asset_type,subtype,country,region_city"
    ).limit(5000).execute().data or []

    ports = [x for x in assets if asset_is_port(x)]
    if args.limit_ports:
        ports = ports[:args.limit_ports]

    matched = 0
    metrics_inserted = 0
    unmatched = []

    for asset in ports:
        live_row, score = match_port(asset, live)

        if not live_row or score < args.min_score:
            unmatched.append({
                "asset_id": asset.get("asset_id"),
                "name": asset.get("name"),
                "country": asset.get("country"),
                "score": score,
            })
            continue

        # one provenance record per matched port/day
        observation = sb.table("pc_observations").insert({
            "source_id": SOURCE_ID,
            "source_name": "IMF PortWatch",
            "source_url": "https://portwatch.imf.org/",
            "source_type": "public operational dataset",
            "observation_date": obs_date,
            "redistribution_status": "attribution_required",
            "attribution_required": True,
            "raw_value": {
                "portid": live_row.get("portid"),
                "portname": live_row.get("portname"),
                "country": live_row.get("country"),
                "match_score": round(score, 4),
            },
            "methodology": (
                "P&C canonical-port name/country match to IMF PortWatch daily port record. "
                "PortWatch values are retained as source-reported/estimated operational context."
            ),
            "confidence": "High" if score >= 0.92 else "Moderate",
            "review_status": "approved",
            "record_status": "provisional",
            "metadata": {
                "canonical_asset_id": asset.get("asset_id"),
                "portwatch_portid": live_row.get("portid"),
            },
        }).execute().data[0]

        observation_id = observation["observation_id"]

        for source_field, (metric_name, unit) in METRICS.items():
            value = live_row.get(source_field)
            if value in (None, ""):
                continue

            try:
                numeric = float(value)
            except Exception:
                continue

            exists = (
                sb.table("pc_port_metrics")
                .select("port_metric_id")
                .eq("port_asset_id", asset["asset_id"])
                .eq("observation_date", obs_date)
                .eq("metric_name", metric_name)
                .eq("source_id", SOURCE_ID)
                .limit(1)
                .execute().data
                or []
            )
            if exists:
                continue

            sb.table("pc_port_metrics").insert({
                "port_asset_id": asset["asset_id"],
                "observation_date": obs_date,
                "period_start": obs_date,
                "period_end": obs_date,
                "metric_name": metric_name,
                "value": numeric,
                "unit": unit,
                "source_id": SOURCE_ID,
                "observation_id": observation_id,
                "metadata": {
                    "portwatch_field": source_field,
                    "portwatch_portid": live_row.get("portid"),
                    "matched_port_name": live_row.get("portname"),
                    "match_score": round(score, 4),
                },
            }).execute()
            metrics_inserted += 1

        matched += 1

    print(f"PortWatch date: {obs_date}")
    print(f"Canonical ports considered: {len(ports)}")
    print(f"Matched ports: {matched}")
    print(f"Port metric rows inserted: {metrics_inserted}")
    print(f"Unmatched / below threshold: {len(unmatched)}")

    if unmatched:
        out = ROOT / "external_data" / "portwatch_unmatched.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(unmatched, indent=2), encoding="utf-8")
        print(f"Review unmatched list: {out}")


if __name__ == "__main__":
    main()
