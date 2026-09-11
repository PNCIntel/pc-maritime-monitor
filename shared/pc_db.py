"""Small Supabase helpers shared by P&C admin/client apps."""
from __future__ import annotations
import os
try:
    import streamlit as st
except Exception:
    st=None
try:
    from supabase import create_client
except Exception:
    create_client=None


def secret(name,default=""):
    v=os.getenv(name,default)
    if v: return v
    if st is not None:
        try:
            if name in st.secrets: return str(st.secrets[name])
            if "supabase" in st.secrets:
                mp={"SUPABASE_URL":"url","SUPABASE_ANON_KEY":"anon_key","SUPABASE_SERVICE_ROLE_KEY":"service_role_key"}
                k=mp.get(name)
                if k and k in st.secrets["supabase"]: return str(st.secrets["supabase"][k])
        except Exception: pass
    return default


def client(service=True):
    if not create_client: return None
    url=secret("SUPABASE_URL"); key=secret("SUPABASE_SERVICE_ROLE_KEY" if service else "SUPABASE_ANON_KEY")
    if not url or not key: return None
    return create_client(url,key)


def count_rows(sb,table,filters=None):
    if sb is None: return 0
    q=sb.table(table).select("*",count="exact").limit(1)
    for k,v in (filters or {}).items(): q=q.eq(k,v)
    r=q.execute(); return int(r.count or 0)


def safe_rows(sb,table,columns="*",limit=1000,filters=None,order=None):
    if sb is None: return []
    try:
        q=sb.table(table).select(columns).limit(limit)
        for k,v in (filters or {}).items(): q=q.eq(k,v)
        if order: q=q.order(order,desc=True)
        return q.execute().data or []
    except Exception:
        return []
