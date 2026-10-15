"""Sourced, approximate locality points for event map context.

These are geographic reference points, not verified incident coordinates.
Never infer physical damage, footprint, or route from them.
"""
from __future__ import annotations
import re

LOCALITIES = (
    {"name":"Medina, Saudi Arabia","pattern":r"\\b(?:medina|madinah)\\b",
     "lat":24.4672,"lon":39.6111,
     "source":"https://www.openstreetmap.org/search?query=Medina%20Saudi%20Arabia",
     "precision":"approximate city reference, not an incident location"},
    {
        "name": "Peshawar, Pakistan",
        "pattern": "peshawar",
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
