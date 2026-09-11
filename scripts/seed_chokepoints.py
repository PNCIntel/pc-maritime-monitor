#!/usr/bin/env python3
"""Seed a conservative baseline of globally important trade chokepoints.

This is a geography/identity seed only. It deliberately leaves capacity and
current-status fields blank unless separately ingested from an attributed source.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "shared"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

from pc_db import client

ROWS = [
    ("CHOKE_HORMUZ", "Strait of Hormuz", "strait", "Iran", "Oman", 26.56, 56.25, ["crude oil","petroleum products","LNG"], ["Red Sea / Cape routing where feasible"]),
    ("CHOKE_BAB_EL_MANDEB", "Bab el-Mandeb", "strait", "Yemen", "Djibouti / Eritrea", 12.58, 43.33, ["containerized trade","crude oil","petroleum products"], ["Cape of Good Hope"]),
    ("CHOKE_SUEZ", "Suez Canal", "canal", "Egypt", None, 30.45, 32.35, ["containerized trade","crude oil","petroleum products","LNG"], ["Cape of Good Hope"]),
    ("CHOKE_PANAMA", "Panama Canal", "canal", "Panama", None, 9.08, -79.68, ["containerized trade","LNG","LPG","dry bulk"], ["Cape Horn / intermodal alternatives"]),
    ("CHOKE_MALACCA", "Strait of Malacca", "strait", "Malaysia", "Indonesia", 2.50, 101.00, ["containerized trade","crude oil","LNG","dry bulk"], ["Sunda Strait","Lombok Strait"]),
    ("CHOKE_SINGAPORE", "Singapore Strait", "strait", "Singapore", "Indonesia", 1.20, 103.85, ["containerized trade","crude oil","petroleum products"], ["Malacca / Sunda / Lombok routing depending voyage"]),
    ("CHOKE_GIBRALTAR", "Strait of Gibraltar", "strait", "Spain", "Morocco", 35.96, -5.60, ["containerized trade","energy","bulk"], ["Cape routing"]),
    ("CHOKE_BOSPORUS", "Bosporus", "strait", "Türkiye", None, 41.12, 29.07, ["grain","crude oil","petroleum products"], ["No equivalent maritime bypass for Black Sea access"]),
    ("CHOKE_DARDANELLES", "Dardanelles", "strait", "Türkiye", None, 40.20, 26.40, ["grain","crude oil","petroleum products"], ["No equivalent maritime bypass for Black Sea access"]),
    ("CHOKE_DOVER", "Strait of Dover", "strait", "United Kingdom", "France", 51.00, 1.50, ["containerized trade","ferries","ro-ro"], ["Western English Channel routes"]),
    ("CHOKE_DANISH_STRAITS", "Danish Straits", "strait system", "Denmark", "Sweden", 55.70, 12.70, ["containerized trade","energy","bulk"], ["Kiel Canal for eligible traffic"]),
    ("CHOKE_KIEL", "Kiel Canal", "canal", "Germany", None, 54.32, 10.14, ["containerized trade","general cargo","bulk"], ["Skagerrak / Kattegat"]),
    ("CHOKE_MOZAMBIQUE", "Mozambique Channel", "maritime passage", "Mozambique", "Madagascar", -18.00, 41.50, ["energy","bulk","containerized trade"], ["Open Indian Ocean routing"]),
    ("CHOKE_TAIWAN", "Taiwan Strait", "strait", "China", "Taiwan", 24.00, 119.50, ["containerized trade","electronics","energy"], ["Routes east of Taiwan"]),
]

def main():
    sb = client(service=True)
    if sb is None:
        raise SystemExit("Configure SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY first.")

    payloads = []
    for cid, name, typ, ca, cb, lat, lon, deps, alts in ROWS:
        payloads.append({
            "chokepoint_id": cid,
            "name": name,
            "chokepoint_type": typ,
            "country_a": ca,
            "country_b": cb,
            "latitude": lat,
            "longitude": lon,
            "commodity_dependency": deps,
            "alternative_routes": alts,
            "current_status": None,
            "metadata": {
                "seed_type": "P&C geographic baseline",
                "verification_note": (
                    "Identity/geography seed only. Capacity, restrictions and current "
                    "status must come from attributed operational sources."
                ),
            },
        })

    sb.table("pc_chokepoints").upsert(
        payloads,
        on_conflict="chokepoint_id",
    ).execute()

    print(f"Upserted {len(payloads)} chokepoint baseline records.")


if __name__ == "__main__":
    main()
