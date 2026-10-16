"""Approximate geographic context for event maps, not asserted incident coordinates."""
from __future__ import annotations
import re
from urllib.parse import quote
import requests
import streamlit as st

LOCALITIES = (
    {"name":"Sharjah, United Arab Emirates","pattern":r"\\bsharjah\\b",
     "lat":25.3463,"lon":55.4209,"source":"https://www.openstreetmap.org/search?query=Sharjah%20United%20Arab%20Emirates",
     "precision":"city reference point; not a raid or arrest location"},
    {"name":"Medina, Saudi Arabia","pattern":r"\b(?:medina|madinah)\b",
     "lat":24.4672,"lon":39.6111,"source":"https://www.openstreetmap.org/search?query=Medina%20Saudi%20Arabia",
     "precision":"city reference point"},
    {"name":"Peshawar, Pakistan","pattern":r"\bpeshawar\b",
     "lat":34.008,"lon":71.57849,"source":"https://www.geonames.org/1168197/peshawar.html",
     "precision":"city reference point"},
)

def locality_point(location):
    text=str(location or "").strip()
    for item in LOCALITIES:
        if re.search(item["pattern"],text,re.I):
            return dict(item)
    return None

@st.cache_data(ttl=604800, show_spinner=False, max_entries=2000)
def named_place_point(location):
    """Resolve a named place for a regional reference map only; cache to limit requests."""
    name=re.sub(r"\s+"," ",str(location or "")).strip(" ,")
    if not name or len(name)>160 or name.lower() in {"unknown","not established","unrecorded","other"}:
        return None
    known=locality_point(name)
    if known: return known
    try:
        response=requests.get("https://nominatim.openstreetmap.org/search",
            params={"q":name,"format":"jsonv2","limit":1,"addressdetails":0},
            headers={"User-Agent":"PowerAndCorridors-Intelligence/1.0 (powerncorridors.com)"},
            timeout=5)
        response.raise_for_status()
        results=response.json()
        if not results: return None
        place=results[0]
        lat,lon=float(place["lat"]),float(place["lon"])
        if not (-90<=lat<=90 and -180<=lon<=180): return None
        return {"name":place.get("display_name") or name,"lat":lat,"lon":lon,
                "source":"https://www.openstreetmap.org/search?query="+quote(name),
                "precision":"geocoded named-place reference"}
    except (requests.RequestException,KeyError,ValueError,TypeError,IndexError):
        return None
