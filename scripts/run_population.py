#!/usr/bin/env python3
"""Run the safe initial P&C population sequence.

This orchestrator runs deterministic/public-source jobs. AI campaigns are opt-in.

Examples:
  python scripts/run_population.py
  python scripts/run_population.py --with-airports --with-signal
  python scripts/run_population.py --with-ai --ai-campaign african_ports
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(args):
    print("\n>", " ".join(args))
    subprocess.run(args, cwd=ROOT, check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--with-airports", action="store_true")
    ap.add_argument("--with-signal", action="store_true")
    ap.add_argument("--with-ai", action="store_true")
    ap.add_argument("--ai-campaign", default="african_ports")
    ap.add_argument("--signal-weeks", default="1-36")
    args = ap.parse_args()

    py = sys.executable

    run([py, "scripts/seed_open_source_registry.py"])
    run([py, "scripts/seed_market_instruments.py"])
    run([py, "scripts/ingest_world_bank_macro.py", "--start", "2016"])
    run([py, "scripts/seed_chokepoints.py"])
    run([py, "scripts/ingest_portwatch.py"])

    if args.with_airports:
        run([py, "scripts/stage_ourairports.py"])

    if args.with_signal:
        run([
            py,
            "scripts/ingest_signal_group.py",
            "--year", "2026",
            "--families", "dry,tanker",
            "--weeks", args.signal_weeks,
        ])

    if args.with_ai:
        run([
            py,
            "scripts/ai_research_stage.py",
            "--campaign", args.ai_campaign,
            "--product", "TRADE",
        ])

    run([py, "scripts/verify_migration.py"])
    print("\nPopulation run complete.")


if __name__ == "__main__":
    main()
