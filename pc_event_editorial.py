"""Evidence-bound editorial prose for event PDFs. Draft only; analyst must approve."""
from __future__ import annotations
import json
from pc_report_ai import _api, MODEL

FIELDS=("key_judgment","what_happened","why_it_matters","operational_significance",
        "commercial_significance","alternative_explanation","uncertainties",
        "risk_outlook","monitoring_analysis","decision_triggers","bottom_line","historical_context","wider_context","network_synthesis","infrastructure_synthesis","geographic_synthesis","connected_developments_synthesis")

def draft_event_brief(api_key, record, assessment, outlook, evidence, related, assets, metadata, publication_context=None, publication_type="assessment"):
    if not api_key: raise ValueError("Configure the report API key first")
    claims=evidence or (metadata.get("source_claims") or [])
    context={"event":record,"approved_assessment":assessment,"published_judgment":outlook,
             "sources":claims,"related_developments":[{"relationship":edge,"event":event} for edge,event in related],
             "infrastructure":assets,"editorial_context":metadata,
             "knowledge_graph_context":publication_context or {},
             "publication_type":publication_type}
    if publication_type=="flash":
        system="""You are writing a short Power & Corridors Flash Intelligence Alert.
Use only supplied evidence and reviewed judgments. What changed, why it matters now,
what is confirmed or unresolved, and which decision triggers warrant attention.
Write crisp, non-repetitive paragraphs. Do not add historical or graph-tour sections.
Do not invent probabilities, current risk ratings, impact, attribution or normal operations.
Return JSON with the FIELDS keys; use empty strings/lists for long-form-only fields."""
    else:
        system="""You are writing a substantive Power & Corridors Connected Intelligence Assessment,
NOT an expanded Flash Alert. Use the canonical knowledge_graph_context as the analytical spine.
Write a distinct executive judgment synthesising the incident with historical, corporate,
geographic, infrastructure and related-event context. Separate known facts, reported claims
and analyst inference. Explain mechanisms and commercial/operational pathways only where
supported; do not infer direct damage, continuing risk, beneficial ownership or common attackers.
Provide:
- network_synthesis: a full interpretive paragraph BEFORE the connected identities/role table.
Explain why the specific resolved relationships matter to accountability, coordination or
exposure, with dates and source qualifications. If absent, say nothing (empty string).
- infrastructure_synthesis: BEFORE the infrastructure table, distinguish actual impact from
contextual or contingency exposure, and explain the relevance of recorded dependencies.
- geographic_synthesis: BEFORE the map, explain why this geography matters and explicitly
distinguish named locality, facility and incident coordinates. Do not manufacture positions.
- connected_developments_synthesis: BEFORE linked-event table, explain the contextual relationship and limits to causation or attribution. For EACH cited earlier event, give a self-contained description: date, location if recorded, event mechanism, reported outcome and verification status, then state exactly why it matters now. Never rely on a bare title, imply shared perpetrators from proximity, or invent missing details.
- historical_context and wider_context: independently meaningful source-grounded background,
not restatements of the incident.
- why_it_matters: assess systemic implications, not another account of what happened.
- monitoring_analysis: each item names an observable indicator, why it matters and what would
change the assessment; decision triggers only if grounded.
Do not repeat key_judgment, what_happened, why_it_matters or bottom_line.
Keep unsupported optional sections empty, never filler. Source-qualified and accessible prose;
do not expose internal IDs. Never copy another publisher's risk rating or invent probability.
Return JSON with the exact keys supplied in FIELDS, list values for uncertainties,
monitoring_analysis and decision_triggers, strings for all other keys."""
    system += "\\nExact JSON keys: "+", ".join(FIELDS)+". No markdown."
    response=_api(api_key,{"model":MODEL,"temperature":0.1,"response_format":{"type":"json_object"},
       "messages":[{"role":"system","content":system},
                   {"role":"user","content":json.dumps(context,ensure_ascii=False,default=str)[:95000]}],
       "max_tokens":3800},timeout=120)
    data=json.loads(response["choices"][0]["message"]["content"])
    return {k:(data.get(k) if isinstance(data.get(k),list) else []) if k in
            ("uncertainties","monitoring_analysis","decision_triggers")
            else str(data.get(k) or "") for k in FIELDS}
