"""Sourced, approximate locality points for event map context.

These are geographic reference points, not verified incident coordinates.
Never infer physical damage, footprint, or route from them.
"""
from __future__ import annotations
import re

LOCALITIES = (
    {
        "name": "Peshawar, Pakistan",
        "pattern": r"\\bpeshawar\\b",
        "lat": 34.00800,
        "lon": 71.57849,
        "source": "https://www.geonames.org/1168197/peshawar.html",
        "precision": "city reference point",
    },
)

def locality_point(location):
    text=str(location or "")
    for item in LOCALITIES:
        if re.search(item["pattern"],text,re.I):
            return dict(item)
    return None
