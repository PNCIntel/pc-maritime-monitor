"""Editorial treatment planning, independent of Streamlit controls.

Recommendations describe what a figure can establish and what evidence is missing.
No inferred coordinates, relationships, trend baselines, or incident causation.
"""
from datetime import date

def plan_treatment(assembled):
    events=assembled.get("events") or []
    blocks=assembled.get("blocks") or []
    valid_dates=[]
    for e in events:
        d=str(e.get("start_date") or "")[:10]
        try: date.fromisoformat(d); valid_dates.append(d)
        except ValueError: pass
    facilities=next((b.get("rows") or [] for b in blocks if b.get("title")=="Connected facilities and organisations"),[])
    claims=next((b.get("rows") or [] for b in blocks if b.get("title")=="Reported or contested developments"),[])
    result=[]
    if len(events)>1 and valid_dates:
        result.append({"id":"sequence","title":"Threat-to-response sequence","type":"sequence",
          "status":"Research-ready","purpose":"Separate threats, reported impacts, interceptions and operational responses.",
          "limitation":"Same-day dates do not establish intraday sequence or causation.",
          "next_step":"Retrieve source-backed timestamps and event classifications before drawing connecting arrows."})
    if facilities:
        result.append({"id":"exposure","title":"Operational exposure comparison","type":"comparison",
          "status":"Research-ready","purpose":"Contrast named assets and organisations against reported effects and unresolved exposure.",
          "limitation":"A connected facility is not necessarily affected.",
          "next_step":"Verify each event-to-asset relationship and effect status."})
    result.append({"id":"map","title":"Geographic exposure map","type":"map",
      "status":"Needs geolocation review","purpose":"Distinguish incident locations, threatened targets and associated infrastructure.",
      "limitation":"Text locations alone cannot establish exact incident positions or impact status.",
      "next_step":"Validate asset coordinates and incident-location precision."})
    if len(set(valid_dates))<2:
        result.append({"id":"trend","title":"Incident trend chart","type":"trend",
          "status":"Not recommended","purpose":"A trend requires a comparable time series.",
          "limitation":"Selected incidents are concentrated on one recorded day.",
          "next_step":"Retrieve historical coverage and deduplicate recurring updates before reconsidering."})
    if not events:
        result=[{"id":"none","title":"No figure recommended","type":"none","status":"Insufficient evidence",
                 "purpose":"No incident records retrieved.","limitation":"No factual basis for a figure.",
                 "next_step":"Select and assemble developments."}]
    return result
