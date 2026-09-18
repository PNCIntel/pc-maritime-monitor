from __future__ import annotations

import ast
import json
import re
from datetime import date, datetime

import pandas as pd

# -----------------------------------------------------------------------------
# Power & Corridors shared presentation layer
# -----------------------------------------------------------------------------
# Canonical database values remain machine-oriented.  This module is only for
# human-facing tables, charts, cards, filters and labels.
# -----------------------------------------------------------------------------

_ACRONYMS = {
    "AIS","ADNOC","ADQ","ADX","AI","API","CMA","CGM","DWT","EEZ","EU","FIR",
    "GCC","GTL","HQ","IMO","IMF","IRGC","LNG","LPG","MMSI","MRO","NATO",
    "OFAC","OPEC","OPV","PCTC","RFI","RFP","RO","RO-RO","SAR","STS","TEU",
    "UAE","UK","UN","UNSC","US","USA","USD","VLCC"
}

_EMPTY = {"", "nan", "none", "<na>", "null", "nat"}

_COLUMN_ENUM_HINTS = (
    "type","subtype","family","domain","nature","mode","status","severity",
    "confidence","relationship","role","class","phase","category","temporality",
    "verification","precision","scope","method","action"
)

_COUNTRY_HINTS = ("country", "countries", "jurisdiction")
_DATE_HINTS = (
    "date","created at","updated at","published at","retrieved at","verified at",
    "start","end","effective","announced","signed","closing","maturity","delivery"
)

_EXACT_LABELS = {
    "law_enforcement": "Law Enforcement",
    "military_command": "Military Command",
    "port_authority": "Port Authority",
    "government_agency": "Government Agency",
    "state_security_actor": "State Security Actor",
    "maritime_casualty": "Maritime Casualty",
    "route_adaptation": "Route Adaptation",
    "security_diplomacy": "Security Diplomacy",
    "sanctions_trade_policy": "Sanctions & Trade Policy",
    "labour_disruption": "Labour & Disruption",
    "carrier_routing": "Carrier Routing",
    "drug_smuggling": "Drug Smuggling",
    "cocaine_smuggling": "Cocaine Smuggling",
    "cannabis_smuggling": "Cannabis Smuggling",
    "migrant_smuggling": "Migrant Smuggling",
    "weapons_smuggling": "Weapons Smuggling",
    "fuel_smuggling": "Fuel Smuggling",
    "captagon_smuggling": "Captagon Smuggling",
    "narco_logistics_interdiction": "Narco-Logistics Interdiction",
    "search_and_rescue_update": "Search and Rescue Update",
    "sar_lifeboat_service_entry": "SAR Lifeboat Service Entry",
    "secondary_tariff_exposure": "Secondary Tariff Exposure",
    "labour_watch": "Labour Watch",
    "route_change": "Route Change",
    "crude_export_security_rerouting": "Crude Export Security Rerouting",
    "us_houthi_maritime_security_talks": "US–Houthi Maritime Security Talks",
    "narcotics_interdiction": "Narcotics Interdiction",
    "interdicting_authority": "Interdicting Authority",
    "strike_authority": "Strike Authority",
    "affected_asset": "Affected Asset",
    "affected_vessel": "Affected Vessel",
    "occurred_in": "Occurred In",
    "directly_affected": "Directly Affected",
    "regional_security_exposure": "Regional Security Exposure",
    "northern_gulf_exposure": "Northern Gulf Exposure",
    "direct_system_impact": "Direct System Impact",
    "regional_escalation": "Regional Escalation",
    "security_advisory": "Security Advisory",
}

def clean_text(value):
    if value is None:
        return ""
    try:
        if isinstance(value,float) and pd.isna(value):
            return ""
    except Exception:
        pass
    s=str(value)
    s=s.replace("\\r\\n"," ").replace("\\n"," ").replace("\\r"," ").replace("\\t"," ")
    s=s.replace("\r\n"," ").replace("\n"," ").replace("\r"," ").replace("\t"," ")
    s=re.sub(r"\s+"," ",s).strip()
    return "" if s.casefold() in _EMPTY else s

def _sentence_words(text):
    words=[]
    for raw in text.split():
        stripped=raw.strip()
        if not stripped:
            continue
        # Preserve punctuation while converting enum-like words.
        prefix=re.match(r"^[^A-Za-z0-9]*",stripped).group(0)
        suffix=re.search(r"[^A-Za-z0-9]*$",stripped).group(0)
        core=stripped[len(prefix):len(stripped)-len(suffix) if suffix else None]
        upper=core.upper()
        if upper in _ACRONYMS:
            display=upper
        elif core:
            display=core.lower()
        else:
            display=core
        words.append(prefix+display+suffix)
    if not words:
        return ""
    out=" ".join(words)
    return out[:1].upper()+out[1:]

def pretty_enum(value):
    """Render machine taxonomy values as ordinary English without mutating data."""
    s=clean_text(value)
    if not s:
        return ""
    if s.startswith(("http://","https://")):
        return s

    key=re.sub(r"[\s-]+","_",s.strip()).casefold()
    key=re.sub(r"_+","_",key)
    if key in _EXACT_LABELS:
        return _EXACT_LABELS[key]

    # Already-written prose / display labels should not be aggressively title-cased.
    if (
        " " in s
        and "_" not in s
        and not s.isupper()
        and not re.fullmatch(r"[a-z0-9/-]+",s)
    ):
        return s[:1].upper()+s[1:]

    x=s.replace("_"," ").replace("-", " ")
    x=re.sub(r"\s+"," ",x).strip()
    return _sentence_words(x)

def country_tokens(value):
    """Return consistent country/geography tokens from JSON arrays or legacy strings."""
    if value is None:
        return []
    if isinstance(value,(list,tuple,set)):
        raw=list(value)
    else:
        s=clean_text(value)
        if not s:
            return []
        raw=None
        if s[:1] in "[(" and s[-1:] in "])":
            for parser in (json.loads, ast.literal_eval):
                try:
                    parsed=parser(s)
                    if isinstance(parsed,(list,tuple,set)):
                        raw=list(parsed)
                        break
                except Exception:
                    pass
        if raw is None:
            s=re.sub(r'^[\[\(\{]\s*|\s*[\]\)\}]$',"",s)
            s=s.replace('"',"").replace("'","")
            raw=re.split(r"\s*[;|]+\s*",s)

    out=[]
    seen=set()
    for v in raw:
        item=clean_text(v)
        if not item:
            continue
        for part in re.split(r"\s+/\s+",item):
            part=clean_text(part)
            if part and part.casefold() not in seen:
                seen.add(part.casefold())
                out.append(part)
    return out

def pretty_countries(value, separator="; "):
    return separator.join(country_tokens(value))

def pretty_date(value, include_time="auto"):
    s=clean_text(value)
    if not s:
        return ""
    try:
        ts=pd.to_datetime(value,errors="coerce",utc=True)
    except Exception:
        return s
    if pd.isna(ts):
        return s
    try:
        py=ts.to_pydatetime()
    except Exception:
        return s

    has_time=not (py.hour==0 and py.minute==0 and py.second==0)
    if include_time is True or (include_time=="auto" and has_time):
        return py.strftime("%d %b %Y · %H:%M UTC")
    return py.strftime("%d %b %Y")

def pretty_bool(value):
    if isinstance(value,bool):
        return "Yes" if value else "No"
    s=clean_text(value).casefold()
    if s in {"true","yes","y","1"}:
        return "Yes"
    if s in {"false","no","n","0"}:
        return "No"
    return clean_text(value)

def display_value(value,column_name=""):
    col=clean_text(column_name).casefold().replace("_"," ")
    if value is None:
        return ""

    if any(h in col for h in _COUNTRY_HINTS):
        return pretty_countries(value)

    if any(h in col for h in _DATE_HINTS):
        # Do not reinterpret numeric quantities whose header happens to include "start/end".
        if not isinstance(value,(int,float)) or isinstance(value,bool):
            return pretty_date(value)

    if isinstance(value,bool):
        return pretty_bool(value)

    if any(h in col for h in _COLUMN_ENUM_HINTS):
        return pretty_enum(value)

    # Catch obvious machine enums even if the column header is generic.
    s=clean_text(value)
    if (
        s
        and not s.startswith(("http://","https://"))
        and (
            "_" in s
            or (s.isupper() and len(s)>3 and not re.fullmatch(r"[A-Z]{2,5}\d*",s))
        )
    ):
        return pretty_enum(s)

    return s

def display_series(series,column_name=""):
    return series.map(lambda v: display_value(v,column_name))

def standardize_dataframe(df, columns=None):
    if df is None:
        return pd.DataFrame()
    out=df.copy()
    if columns:
        cols=[c for c in columns if c in out.columns]
        out=out[cols].copy()
    for c in out.columns:
        # Keep URLs untouched.
        if "url" in str(c).casefold():
            out[c]=out[c].map(clean_text)
        elif (
            out[c].dtype == object
            or pd.api.types.is_string_dtype(out[c])
            or isinstance(out[c].dtype, pd.CategoricalDtype)
            or pd.api.types.is_datetime64_any_dtype(out[c])
        ):
            out[c]=display_series(out[c],c)
        elif pd.api.types.is_bool_dtype(out[c]):
            out[c]=out[c].map(pretty_bool)
    return out

def display_dimension(value, dimension=""):
    """Chart/filter label normalizer."""
    d=clean_text(dimension).casefold()
    if d in {"country","countries","country / countries","country / corridor"}:
        vals=country_tokens(value)
        return vals[0] if vals else "Unspecified"
    return display_value(value,dimension) or "Unspecified"


_EVENT_COLUMNS = {
    "Start Date","End Date","Event Date","Date",
    "Event Family","Event Type","Event Domain","Event Nature",
    "Severity","Status","Mode","Confidence",
    "Country / Countries","Country","Countries",
    "Relationship","Actor Role","Entity Type","Asset Type","Subtype"
}

def standardize_event_dataframe(df, columns=None):
    """Stronger event/intelligence display pass used by both P&C apps."""
    out=standardize_dataframe(df,columns)
    if out.empty:
        return out
    for c in out.columns:
        cstr=str(c)
        if cstr in {"Start Date","End Date","Event Date","Date"}:
            out[c]=out[c].map(lambda v: pretty_date(v,include_time=False))
        elif cstr in {"Country / Countries","Countries"}:
            out[c]=out[c].map(pretty_countries)
        elif cstr in {
            "Event Family","Event Type","Event Domain","Event Nature",
            "Severity","Status","Mode","Relationship","Actor Role",
            "Entity Type","Asset Type","Subtype"
        }:
            out[c]=out[c].map(pretty_enum)
    return out

def format_filter_option(value, dimension=""):
    """Readable selectbox label while keeping the raw option value for filtering."""
    if value in (None,""):
        return ""
    if str(value)=="All":
        return "All"
    d=clean_text(dimension).casefold()
    if "country" in d or "countries" in d or "region" in d:
        return pretty_countries(value) or clean_text(value)
    if "date" in d:
        return pretty_date(value,include_time=False)
    return pretty_enum(value)
