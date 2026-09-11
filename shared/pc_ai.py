"""Optional OpenAI research helper for P&C Admin.

All AI output is staged for review; this module never writes directly to canonical tables.
Set OPENAI_API_KEY and OPENAI_MODEL in Streamlit secrets/environment.
"""
from __future__ import annotations
import os, json
try:
    from openai import OpenAI
except Exception:
    OpenAI = None


def _secret(name, default=""):
    v=os.getenv(name,default)
    if v: return v
    try:
        import streamlit as st
        if name in st.secrets: return str(st.secrets[name])
        if "openai" in st.secrets:
            mp={"OPENAI_API_KEY":"api_key","OPENAI_MODEL":"model"}
            k=mp.get(name)
            if k and k in st.secrets["openai"]: return str(st.secrets["openai"][k])
    except Exception: pass
    return default


def configured():
    return bool(OpenAI and _secret("OPENAI_API_KEY") and _secret("OPENAI_MODEL"))


def research(prompt: str, product_context: str="TRADE", use_web: bool=True) -> dict:
    if not configured():
        raise RuntimeError("OPENAI_API_KEY and OPENAI_MODEL must be configured")
    client=OpenAI(api_key=_secret("OPENAI_API_KEY"))
    instructions=(
        "You are the internal Power & Corridors research engine. Research and extract evidence, "
        "but do not claim database changes have been applied. Return concise JSON-compatible research "
        "with proposed_entities, proposed_assets, proposed_relationships, proposed_events, sources, "
        "conflicts, and notes. For P&C Intelligence, exclude routine corporate developments unless they "
        "create a security or operational disruption. For P&C Trade, retain commercial/investment developments."
    )
    tools=[{"type":"web_search"}] if use_web else []
    resp=client.responses.create(model=_secret("OPENAI_MODEL"),instructions=instructions,input=f"Product context: {product_context}\n\n{prompt}",tools=tools)
    text=getattr(resp,"output_text","") or ""
    try:
        parsed=json.loads(text)
    except Exception:
        parsed={"raw_output":text}
    parsed["response_id"]=getattr(resp,"id",None)
    parsed["model"]=_secret("OPENAI_MODEL")
    return parsed
