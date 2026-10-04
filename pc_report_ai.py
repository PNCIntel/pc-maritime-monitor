"""Shared AI drafting for P&C report workspaces.

Uses supplied canonical/database context only. No web search is performed here.
The caller controls which facts, links, events and evidence URLs are included.
"""
from __future__ import annotations
import json, os, urllib.request
from typing import Any

MODEL=os.environ.get("PC_REPORT_MODEL","gpt-4.1-mini")


def _api(api_key: str, payload: dict, timeout: int=150) -> dict:
    req=urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload,ensure_ascii=False).encode("utf-8"),
        headers={"Authorization":"Bearer "+api_key.strip(),"Content-Type":"application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req,timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def draft_report(api_key: str, lens: str, product: str, sections: list[str],
                 query: str, context_bundle: dict, title_hint: str="") -> dict:
    if not api_key:
        raise ValueError("OpenAI API key is not configured")

    system=f"""You are the senior analyst drafting a Power & Corridors {lens} product.
Use ONLY the supplied canonical/database context and evidence. Do not browse the web.
Do not invent names, dates, ownership, sanctions status, locations, vessel identities,
financial values, causal claims or source URLs.

Distinguish:
1. VERIFIED / REPORTED FACTS from the supplied data;
2. ANALYTICAL ASSESSMENT or inference;
3. GAPS / UNCONFIRMED points.

If the supplied context does not support a section, say what is missing rather than filling
it with generic language. Avoid vague phrases such as 'monitor the situation' unless you
state exactly what indicator, threshold, actor, route, asset, filing or event would change
the judgement. Make the output commercially and operationally useful.

Return JSON only with:
title,
executive_line,
confidence (Low|Medium|Moderate|High),
sections {{section_name: text}},
gaps [strings].
Every section name must exactly match one of the requested section names."""

    prompt={
        "lens":lens,
        "product":product,
        "query":query,
        "title_hint":title_hint,
        "requested_sections":sections,
        "context":context_bundle,
    }
    payload={
        "model":MODEL,
        "temperature":0.1,
        "response_format":{"type":"json_object"},
        "messages":[
            {"role":"system","content":system},
            {"role":"user","content":json.dumps(prompt,ensure_ascii=False,default=str)[:110000]},
        ],
        "max_tokens":7000,
    }
    r=_api(api_key,payload)
    return json.loads(r["choices"][0]["message"]["content"])
