"""P&C data bridge.

Migration-night strategy:
1) If Supabase is configured and pc_legacy_sheet_rows is populated, existing apps read
   the same workbook/sheet-shaped DataFrames from Supabase.
2) Otherwise they fall back to the existing /data Excel workbooks.

This keeps the two client apps operational while the normalized canonical tables are
populated and progressively adopted page-by-page.
"""
from __future__ import annotations

from pathlib import Path
import os
from typing import Optional
import pandas as pd

try:
    from supabase import create_client
except Exception:  # pragma: no cover
    create_client = None


BOOK_ALIASES = {
    "Core Entities": "01_core_entities.xlsx",
    "Maritime": "02_maritime.xlsx",
    "Rail": "03_rail.xlsx",
    "Road & Trucking": "04_road_trucking.xlsx",
    "Aviation": "05_aviation.xlsx",
    "Infrastructure": "06_infrastructure.xlsx",
    "Corporate & Markets": "07_corporate_markets.xlsx",
    "Transactions": "08_transactions.xlsx",
    "Intelligence": "09_intelligence.xlsx",
    "Sources": "10_sources_evidence.xlsx",
    "Systems & Waterways": "11_systems_waterways_governance.xlsx",
    "Defence & Shipbuilding": "12_defence_shipbuilding.xlsx",
    "Events & Hazards": "13_events_hazards.xlsx",
    "Trade Policy & Compliance": "14_trade_policy_compliance.xlsx",
    "Market Intelligence Reference": "15_market_intelligence_reference.xlsx",
    "Global Ports Reference": "16_global_ports_reference.xlsx",
    "Trade Connectivity Reference": "17_trade_connectivity_reference.xlsx",
    "Official Maritime Security": "18_official_maritime_security.xlsx",
    "Risk Benchmarks": "19_risk_benchmarks.xlsx",
}


def _secret(name: str, default: str = "") -> str:
    """Read env first. Streamlit secrets are attempted lazily to keep scripts importable."""
    value = os.getenv(name, default)
    if value:
        return value
    try:
        import streamlit as st
        if name in st.secrets:
            return str(st.secrets[name])
        # common nested secrets
        if "supabase" in st.secrets:
            m = {
                "SUPABASE_URL": "url",
                "SUPABASE_ANON_KEY": "anon_key",
                "SUPABASE_SERVICE_ROLE_KEY": "service_role_key",
            }
            k = m.get(name)
            if k and k in st.secrets["supabase"]:
                return str(st.secrets["supabase"][k])
    except Exception:
        pass
    return default


def backend_mode() -> str:
    mode = _secret("PC_DATA_BACKEND", "auto").strip().lower()
    if mode not in {"auto", "supabase", "excel"}:
        mode = "auto"
    if mode == "auto":
        return "supabase" if supabase_available() else "excel"
    return mode


def supabase_available() -> bool:
    return bool(create_client and _secret("SUPABASE_URL") and (_secret("SUPABASE_ANON_KEY") or _secret("SUPABASE_SERVICE_ROLE_KEY")))


def _client(service: bool = False):
    if not create_client:
        return None
    url = _secret("SUPABASE_URL")
    key = _secret("SUPABASE_SERVICE_ROLE_KEY") if service else _secret("SUPABASE_ANON_KEY")
    if not key:
        key = _secret("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        return None
    return create_client(url, key)


def _book_name(label_or_file: str) -> str:
    return BOOK_ALIASES.get(label_or_file, label_or_file)


def excel_sheet(data_dir: Path, label_or_file: str, sheet: str, dtype_str: bool = True) -> pd.DataFrame:
    path = data_dir / _book_name(label_or_file)
    if not path.exists():
        return pd.DataFrame()
    try:
        kwargs = {"dtype": str} if dtype_str else {}
        return pd.read_excel(path, sheet_name=sheet, **kwargs).dropna(how="all").fillna("")
    except Exception:
        return pd.DataFrame()


def supabase_sheet(label_or_file: str, sheet: str, page_size: int = 1000) -> pd.DataFrame:
    c = _client(service=True)
    if c is None:
        return pd.DataFrame()
    book = _book_name(label_or_file)
    rows = []
    start = 0
    try:
        while True:
            end = start + page_size - 1
            resp = (
                c.table("pc_legacy_sheet_rows")
                .select("row_number,row_data")
                .eq("source_book", book)
                .eq("source_sheet", sheet)
                .order("row_number")
                .range(start, end)
                .execute()
            )
            data = getattr(resp, "data", None) or []
            rows.extend(data)
            if len(data) < page_size:
                break
            start += page_size
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame([r.get("row_data", {}) or {} for r in rows]).fillna("")
    except Exception:
        return pd.DataFrame()


def load_sheet(data_dir: Path, label_or_file: str, sheet: str, dtype_str: bool = True) -> pd.DataFrame:
    mode = backend_mode()
    if mode == "supabase":
        df = supabase_sheet(label_or_file, sheet)
        if not df.empty or _secret("PC_SUPABASE_NO_FALLBACK", "false").lower() == "true":
            return df
    return excel_sheet(data_dir, label_or_file, sheet, dtype_str=dtype_str)


def workbook_sheets(data_dir: Path, label_or_file: str) -> list[str]:
    book = _book_name(label_or_file)
    if backend_mode() == "supabase":
        c = _client(service=True)
        if c is not None:
            try:
                # Supabase REST has no distinct shortcut; pull sheet column and unique locally.
                resp = c.table("pc_legacy_sheet_rows").select("source_sheet").eq("source_book", book).limit(10000).execute()
                names = sorted({r.get("source_sheet") for r in (getattr(resp, "data", None) or []) if r.get("source_sheet")})
                if names:
                    return names
            except Exception:
                pass
    path = data_dir / book
    if not path.exists():
        return []
    try:
        return pd.ExcelFile(path).sheet_names
    except Exception:
        return []


def backend_status() -> dict:
    mode = backend_mode()
    return {
        "mode": mode,
        "supabase_configured": supabase_available(),
        "excel_fallback": mode != "supabase" or _secret("PC_SUPABASE_NO_FALLBACK", "false").lower() != "true",
    }
