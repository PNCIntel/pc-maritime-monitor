#!/usr/bin/env python3
"""AI-assisted public-web research -> P&C staging queue.

This script NEVER writes AI output directly into canonical tables. It creates
one pc_ingestion_jobs record and writes proposed records to pc_staged_records
for analyst review in pc-power-admin.py.

Examples:
  python scripts/ai_research_stage.py --campaign african_ports
  python scripts/ai_research_stage.py --campaign gcc_refineries
  python scripts/ai_research_stage.py --prompt "Research Brookfield transport and logistics acquisitions since 2018"
  python scripts/ai_research_stage.py --prompt "Research major nickel mines and export chains in Indonesia" --product TRADE
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "shared"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

from pc_db import client
from pc_ai import research

CAMPAIGNS = {
    "african_ports": (
        "Research major commercial ports, container terminals, dry ports and "
        "port-linked logistics zones across Africa. Prioritize operator, owner, "
        "terminal name, country, city, capacity where explicitly sourced, rail "
        "or road connectivity, recent investment, and source URLs. Propose only "
        "records that are supported by public evidence."
    ),
    "gcc_refineries": (
        "Research operational refineries, LNG plants, gas-processing facilities, "
        "oil export terminals and major storage hubs in the GCC and Red Sea. "
        "Capture owner/operator, location, explicit capacity, operating status, "
        "port/pipeline connections and source URLs."
    ),
    "mines_export_chains": (
        "Research major global mines and export chains for iron ore, bauxite, "
        "copper, nickel, cobalt, lithium, manganese, phosphate and potash. Link "
        "mine or industrial asset to rail/road, export port and destination "
        "markets only where supported by evidence."
    ),
    "logistics_parks": (
        "Research major port-linked logistics parks, free zones, economic zones, "
        "warehouses and inland/intermodal terminals in Africa, the Gulf and Asia. "
        "Capture owner, operator, area/capacity where explicit, port/rail/road "
        "connections, investment values and source URLs."
    ),
    "infra_investors": (
        "Research transport, port, terminal, rail, logistics, airport and related "
        "infrastructure acquisitions or investments by Brookfield, KKR, Macquarie, "
        "OMERS, GIP and other major infrastructure investors since 2018. Capture "
        "transaction date, target, stake, value, geography and evidence."
    ),
}

TARGET_TABLES = {
    "pc_entities",
    "pc_assets",
    "pc_mobile_assets",
    "pc_relationships",
    "pc_events",
    "pc_transactions",
    "pc_security_compliance",
    "pc_energy_assets",
    "pc_energy_asset_connections",
    "pc_industrial_assets",
    "pc_logistics_facilities",
    "pc_market_instruments",
    "pc_market_exposure_links",
    "pc_trade_flows",
    "pc_supply_series",
    "pc_port_capabilities",
    "pc_transport_routes",
    "pc_chokepoints",
    "pc_observations",
}

CONTRACT = """
Return:
{
  "records": [
    {
      "target_table": "one allowed P&C table",
      "natural_key": "stable proposed natural key or descriptive key",
      "action": "REVIEW",
      "confidence": 0.0-1.0,
      "payload": {
        "...": "only fields supported by evidence",
        "metadata": {
          "research_sources": [
            {"url": "...", "publisher": "...", "title": "..."}
          ]
        }
      }
    }
  ],
  "sources": [
    {"url": "...", "publisher": "...", "title": "..."}
  ],
  "conflicts": [],
  "notes": []
}

Allowed target tables:
""" + ", ".join(sorted(TARGET_TABLES))


def safe_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--campaign", choices=sorted(CAMPAIGNS))
    ap.add_argument("--prompt")
    ap.add_argument("--product", default="TRADE", choices=["TRADE", "INTELLIGENCE"])
    ap.add_argument("--no-web", action="store_true")
    args = ap.parse_args()

    prompt = args.prompt or (CAMPAIGNS.get(args.campaign) if args.campaign else None)
    if not prompt:
        raise SystemExit("Use --prompt or --campaign.")

    sb = client(service=True)
    if sb is None:
        raise SystemExit("Configure SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY first.")

    now = datetime.now(timezone.utc).isoformat()

    job = sb.table("pc_ingestion_jobs").insert({
        "job_type": "AI_RESEARCH",
        "title": args.campaign or prompt[:120],
        "query_text": prompt,
        "source_scope": {"product": args.product, "web_search": not args.no_web},
        "status": "running",
        "started_at": now,
    }).execute().data[0]

    job_id = job["ingestion_job_id"]

    try:
        result = research(
            prompt=prompt,
            product_context=args.product,
            use_web=not args.no_web,
            output_contract=CONTRACT,
        )

        records = result.get("records") or []
        staged = []
        rejected = 0

        for idx, rec in enumerate(records, 1):
            table = str(rec.get("target_table") or "").strip()
            payload = rec.get("payload")

            if table not in TARGET_TABLES or not isinstance(payload, dict):
                rejected += 1
                continue

            natural_key = str(
                rec.get("natural_key")
                or payload.get("entity_id")
                or payload.get("asset_id")
                or payload.get("mobile_asset_id")
                or payload.get("route_id")
                or payload.get("chokepoint_id")
                or safe_key(json.dumps(payload, sort_keys=True, default=str))
            )

            staged.append({
                "ingestion_job_id": job_id,
                "target_table": table,
                "natural_key": natural_key,
                "action": "REVIEW",
                "payload": payload,
                "confidence": rec.get("confidence"),
                "validation_status": "pending",
                "review_status": "pending",
            })

        for i in range(0, len(staged), 100):
            sb.table("pc_staged_records").insert(staged[i:i+100]).execute()

        sb.table("pc_ingestion_jobs").update({
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "stats": {
                "staged_records": len(staged),
                "discarded_invalid_records": rejected,
                "sources_returned": len(result.get("sources") or []),
                "model": result.get("_model"),
                "response_id": result.get("_response_id"),
            },
        }).eq("ingestion_job_id", job_id).execute()

        print(f"AI research complete. Staged {len(staged)} proposed records for review.")
        print(f"Ingestion job: {job_id}")

    except Exception as exc:
        sb.table("pc_ingestion_jobs").update({
            "status": "failed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "error_text": str(exc)[:4000],
        }).eq("ingestion_job_id", job_id).execute()
        raise


if __name__ == "__main__":
    main()
