"""Evidence-driven figure suggestions for Intelligence Report Studio.

Planner works only from retrieved rows. It does not infer missing geography,
incident trends, or corporate relationships.
"""
from collections import Counter
from datetime import date
import uuid

def plan_figures(assembled):
    events=assembled.get("events") or []
    blocks=assembled.get("blocks") or []
    recommendations=[]
    dated=[]
    for event in events:
        when=str(event.get("start_date") or "")[:10]
        if when:
            try:date.fromisoformat(when)
            except ValueError:continue
            dated.append({"Date":when,"Development":str(event.get("title") or "Untitled"),
                          "Verification":str(event.get("verification_status") or "Not established")})
    if dated:
        dated.sort(key=lambda row:row["Date"])
        recommendations.append({"id":"event-chronology","title":"Incident chronology","kind":"timeline",
            "status":"Ready to generate","reason":"Uses recorded event dates, not ingestion dates.",
            "rows":dated,"caption":"Selected developments by recorded event date. These are selected records, not a complete incident trend."})
    else:
        recommendations.append({"id":"event-chronology","title":"Incident chronology","kind":"timeline",
            "status":"Insufficient evidence","reason":"No valid event dates were retrieved.","rows":[]})
    facilities=next((b.get("rows") or [] for b in blocks if b.get("title")=="Connected facilities and organisations"),[])
    if facilities:
        rows=[{"Name":r.get("Name",""),"Type":r.get("Type",""),"Location":r.get("Location","")}
              for r in facilities if r.get("Name")]
        recommendations.append({"id":"exposure-matrix","title":"Connected infrastructure and organisations",
            "kind":"table","status":"Ready to generate","reason":"Uses explicitly connected retrieved records; it does not assert operational impact.",
            "rows":rows,"caption":"Linked facilities and organisations; a connection is not confirmation of damage or disruption."})
    recommendations.append({"id":"geographic-map","title":"Geographic exposure map","kind":"map",
        "status":"Additional research","reason":"Facility names and textual locations do not establish verified coordinates or whether a site was affected, threatened, or merely connected.","rows":[]})
    recommendations.append({"id":"period-trend","title":"Period-on-period incident trend","kind":"chart",
        "status":"Additional research","reason":"Requires comparable historical coverage, event deduplication and an explicit baseline; selected incidents alone cannot establish a trend.","rows":[]})
    recommendations.append({"id":"relationship-network","title":"Corporate and infrastructure network","kind":"network",
        "status":"Additional research","reason":"Requires the underlying typed, sourced relationship edges; a list of linked names is not a network.","rows":[]})
    return recommendations

def figure_block(recommendation):
    if recommendation.get("status")!="Ready to generate" or not recommendation.get("rows"):
        raise ValueError("The figure lacks sufficient retrieved data.")
    rows=recommendation["rows"]
    return {"id":uuid.uuid4().hex[:12],"kind":"Asset table",
            "title":"Figure — "+recommendation["title"],"preset":"Custom",
            "columns":list(rows[0]),"rows":[dict(r) for r in rows],
            "caption":recommendation.get("caption",""),"figure_type":recommendation.get("kind","table"),
            "figure_source":"retrieved evidence"}
