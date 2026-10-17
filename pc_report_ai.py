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
                 query: str, context_bundle: dict, title_hint: str="", editorial_direction: str="", research_mode: str="Standard") -> dict:
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

REPORTING STANDARD:
Write a concise, evidence-dense publication. Length is earned by distinct findings, never by filling a template. Omit unsupported or redundant sections rather than repeating incident facts.
The executive summary must synthesise the shared pattern and explain why the developments
belong in one assessment. In the main sections, use meaningful paragraphs, clear topic
sentences, and distinguish the different legal mechanisms and geographical contexts.
Use specific vessel NAMES AND IMO numbers whenever supplied. Include their source-backed
registered owners, managers, registry and regulatory actors where relevant. Do not invent them.
Separate confirmed boarding/action from suspected wrongdoing, and initial deregistration
proceedings from a completed flag cancellation. Never infer an automatic link between the
French incident, Panama actions, and Japanese designations; identify their common theme as
analysis rather than a demonstrated operational relationship.

CITATION STANDARD:
Evidence URLs appear in context.events[].sources and context.evidence_urls.
For factual claims supported by an event's listed source, cite its numbered source inline
using [1], [2] etc., where numbers refer to the evidence_urls array (1-based).
Only cite a number if the cited URL actually supports that claim based on supplied evidence.
If URL evidence is insufficient or unlinked, identify the gap; do not invent a citation.
Use citations throughout the narrative, not solely at the end.
In a section use separate paragraphs separated by blank lines; a short labelled opening
may appear on its own line. Avoid numbered telegraphic points in a section unless they
are genuinely useful (such as distinct indicators or vessel particulars).
If the data supplies no specific figure, source, operational implication, or asset
relationship, say so. Prefer precise analysis over generic filler. Each fact should be established once; subsequent sections must add a new inference, evidence distinction, network connection or decision implication. Do not repeat the incident summary, crew status, corporate names or generic chokepoint importance. Consolidate duplicate corporate-role observations for prose without merging their evidence or implying continuing tenure. Flash alerts should fit approximately one page and assessments should be as short as the evidence warrants. Do not print Python/JSON structures in narrative; monitoring indicators must be human-readable. Return only sections with meaningful distinct content.

Return JSON only with:
title,
executive_line,
confidence (Low|Medium|Moderate|High),
sections {{section_name: text}},
gaps [strings].
Every section name must exactly match one of the requested section names."""

    if lens == "intelligence":
        system += "\nWrite a cohesive intelligence publication. Distinguish observations, reported claims, and inferences. Avoid repeating the chronology across sections. Explain cross-domain implications only when supported, consider alternative explanations, and state specific indicators that could change the assessment. Do not equate a claim with confirmed impact. Flag source gaps, and do not invent probabilities or trends.\n"
    if editorial_direction.strip():
        system += "\nOPTIONAL EDITORIAL DIRECTION: Follow the user direction only where supported by supplied evidence. Do not override source integrity, citation rules, or product length. If the direction requests external research, identify specific research questions and missing sources in gaps; do not pretend to browse or invent findings. Consider alternative explanations as hypotheses, not established facts.\n"
    if research_mode == "Deeper analysis":
        system += "\nAdd depth only through new evidence-backed connections, implications and uncertainty analysis, not more words.\n"
    elif research_mode == "Alternative explanations":
        system += "\nEvaluate plausible competing explanations, clearly distinguish evidence for and against each, and do not present speculation as fact.\n"
    elif research_mode == "Research gaps and source leads":
        system += "\nPrioritise concrete unanswered questions and identify the type of primary or independent source needed for each in gaps. No claim of completed external research.\n"
    prompt={
        "editorial_direction": editorial_direction.strip()[:4000],
        "research_mode": research_mode,
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


def assist_block(api_key: str, instruction: str, block: dict, context_bundle: dict) -> dict:
    """Propose a change to ONE block; caller must explicitly accept it."""
    if not api_key:
        raise ValueError("OpenAI API key is not configured")
    system="""You are the Power & Corridors evidence-grounded editorial assistant.
Revise only the supplied block according to the instruction. Use only provided context.
Maintain confirmed/reported/alleged distinctions. Never invent facts, legal designations,
identifiers, sources or relationships. Use coherent prose and [n] references only
where the matching source is present in context.evidence_urls (1-based).
Return JSON containing title, body, gaps (list of strings). Do not modify other blocks."""
    payload={"model":MODEL,"temperature":0.1,"response_format":{"type":"json_object"},
             "messages":[{"role":"system","content":system},
                         {"role":"user","content":json.dumps({"instruction":instruction,
                           "block":block,"context":context_bundle},ensure_ascii=False,default=str)[:100000]}],
             "max_tokens":3500}
    result=_api(api_key,payload)
    return json.loads(result["choices"][0]["message"]["content"])
