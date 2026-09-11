#!/usr/bin/env python3
"""Mirror the 14 current P&C Excel workbooks into pc_legacy_sheet_rows.

This is the safest first migration step because the existing Streamlit pages can read
Supabase without changing their sheet-shaped assumptions. Run canonical normalization
second with normalize_core.py.
"""
from __future__ import annotations
import argparse, hashlib, json, os, sys
from pathlib import Path
import pandas as pd
from supabase import create_client

BOOKS=[
"01_core_entities.xlsx","02_maritime.xlsx","03_rail.xlsx","04_road_trucking.xlsx",
"05_aviation.xlsx","06_infrastructure.xlsx","07_corporate_markets.xlsx","08_transactions.xlsx",
"09_intelligence.xlsx","10_sources_evidence.xlsx","11_systems_waterways_governance.xlsx",
"12_defence_shipbuilding.xlsx","13_events_hazards.xlsx","14_trade_policy_compliance.xlsx"]


def clean(v):
    if v is None or (isinstance(v,float) and pd.isna(v)):
        return None
    if hasattr(v,"isoformat") and not isinstance(v,str):
        try: return v.isoformat()
        except Exception: pass
    if pd.isna(v): return None
    return v.item() if hasattr(v,"item") else v


def checksum(payload):
    raw=json.dumps(payload,sort_keys=True,default=str,ensure_ascii=False,separators=(",",":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def first_key(row):
    for k,v in row.items():
        if v not in (None,""):
            return str(v)
    return None


def chunks(seq,n):
    for i in range(0,len(seq),n): yield seq[i:i+n]


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--data-dir",default="data")
    ap.add_argument("--batch-size",type=int,default=500)
    ap.add_argument("--truncate",action="store_true",help="Delete legacy mirror before load")
    ap.add_argument("--dry-run",action="store_true")
    args=ap.parse_args()
    url=os.getenv("SUPABASE_URL")
    key=os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not args.dry_run and (not url or not key):
        raise SystemExit("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY")
    sb=None if args.dry_run else create_client(url,key)
    if args.truncate and sb:
        # Delete by book in bounded calls so this also works through PostgREST.
        for b in BOOKS:
            sb.table("pc_legacy_sheet_rows").delete().eq("source_book",b).execute()
    total=0
    for book in BOOKS:
        path=Path(args.data_dir)/book
        if not path.exists():
            print(f"WARN missing {path}")
            continue
        xls=pd.ExcelFile(path)
        print(f"{book}: {len(xls.sheet_names)} sheets")
        for sheet in xls.sheet_names:
            try:
                df=pd.read_excel(path,sheet_name=sheet,dtype=object).dropna(how="all")
            except Exception as exc:
                print(f"  ERROR {sheet}: {exc}")
                continue
            if df.empty:
                continue
            rows=[]
            for idx,record in enumerate(df.to_dict("records"),start=2):
                payload={str(k):clean(v) for k,v in record.items() if str(k)!="nan"}
                payload={k:v for k,v in payload.items() if v is not None}
                if not payload: continue
                rows.append({
                    "source_book":book,
                    "source_sheet":sheet,
                    "row_number":idx,
                    "row_key":first_key(payload),
                    "row_data":payload,
                    "checksum":checksum(payload),
                })
            if args.dry_run:
                print(f"  {sheet}: {len(rows)} rows")
            else:
                for part in chunks(rows,args.batch_size):
                    sb.table("pc_legacy_sheet_rows").upsert(part,on_conflict="source_book,source_sheet,row_number").execute()
                print(f"  loaded {sheet}: {len(rows)}")
            total += len(rows)
    print(f"TOTAL legacy rows: {total}")

if __name__=="__main__": main()
