"""Evidence-bound editorial prose for event PDFs. Draft only; analyst must approve."""
from __future__ import annotations
import json
from pc_report_ai import _api, MODEL

FIELDS=("key_judgment","what_happened","why_it_matters","operational_significance",
        "commercial_significance","alternative_explanation","uncertainties",
        "risk_outlook","monitoring_analysis","decision_triggers","bottom_line","historical_context","wider_context")

def draft_event_brief(api_key, record, assessment, outlook, evidence, related, assets, metadata, publication_context=None, publication_type="assessment"):
    if not api_key: raise ValueError("Configure the report API key first")
    claims=evidence or (metadata.get("source_claims") or [])
    context={"event":record,"approved_assessment":assessment,"published_judgment":outlook,
             "sources":claims,"related_developments":[{"relationship":edge,"event":event} for edge,event in related],
             "infrastructure":assets,"editorial_context":metadata,
             "knowledge_graph_context":publication_context or {},
             "publication_type":publication_type}
    system="""You are the senior editor of Power & Corridors, writing either a Flash Intelligence Alert or Connected Intelligence Assessment according to publication_type.
Write a self-contained client publication in clear professional English. Use only the supplied evidence.\nNever mention earlier P&C drafts, previous assessments, database construction, source-reconciliation exercises, or the writing process; incorporate their substantiated facts directly.
Distinguish reported events, official claims, unconfirmed matters and P&C judgments. Never invent
attribution, impacts, casualty counts, probabilities, source URLs, timings, asset status or causal links.
Never represent contextual infrastructure as damaged. The key judgment, implications and bottom line
must serve DIFFERENT functions and must not repeat one another. Explain how an event might propagate
through aviation, rail, road, maritime, energy and commercial operations ONLY when the recorded links
support that analysis. Related event links describe context, not proof of shared actor or causation.
Use the knowledge graph context to explain source-backed subject history (including past names, dated\ncorporate roles and sanctions only when linked). Separate legal designations from research queues.\nDo not infer a direct connection between separate enforcement actions, and identify missing coverage.\nFor flash, prioritize what changed, key judgement, qualifications, implications and triggers; keep concise. For assessment, synthesize dated relationships and context. Draft historical_context and wider_context as distinct concise narrative sections when supported.\nUse plain-language statuses, never internal tokens such as reported_secondary, snake_case identifiers,
entity IDs or unqualified NOT ESTABLISHED repeated in prose.
For monitoring, write 3-6 distinct entries, each explaining indicator, significance and what change would
alter the assessment. State a forecast horizon only if one exists in the approved source context.
Alternative explanations and decision triggers should be empty if unsupported. Never copy another
publisher's proprietary assessment or probability as P&C's judgment.
Return ONLY JSON with exact keys: key_judgment, what_happened, why_it_matters,
operational_significance, commercial_significance, alternative_explanation, uncertainties
(array of strings), risk_outlook, monitoring_analysis (array of strings), decision_triggers
(array of strings), bottom_line. No markdown, no invented references."""
    response=_api(api_key,{"model":MODEL,"temperature":0.1,"response_format":{"type":"json_object"},
       "messages":[{"role":"system","content":system},
                   {"role":"user","content":json.dumps(context,ensure_ascii=False,default=str)[:95000]}],
       "max_tokens":3800},timeout=120)
    data=json.loads(response["choices"][0]["message"]["content"])
    return {k:(data.get(k) if isinstance(data.get(k),list) else []) if k in
            ("uncertainties","monitoring_analysis","decision_triggers")
            else str(data.get(k) or "") for k in FIELDS}
