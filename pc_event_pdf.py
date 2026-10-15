"""Branded, source-qualified P&C incident intelligence PDF. No screenshot printing."""
from __future__ import annotations
from datetime import datetime, timezone
from html import escape
from io import BytesIO
from pathlib import Path
import base64
from urllib.parse import quote
import re


def _h(value):
    return escape(str(value or ""), quote=True)

def _date(value):
    return str(value or "")[:10] or "Not recorded"

def _list(value):
    if isinstance(value, list): return value
    if isinstance(value, dict): return [str(k)+": "+str(v) for k,v in value.items()]
    if isinstance(value, str) and value.strip(): return [value]
    return []

def _valid_url(url):
    return isinstance(url,str) and url.startswith(("https://","http://")) and not any(ch.isspace() or ch in '<>"' for ch in url)

def _paragraph(value):
    return "<p>"+_h(value).replace("\\n","<br/>")+"</p>" if value else '<p class="muted">Not established in the current record.</p>'

def create_incident_brief(record, assessment, outlook, evidence, related, assets, metadata=None, map_point=None):
    """Return PDF bytes built from the same canonical dossier, not generated incident claims."""
    from weasyprint import HTML
    from pc_event_map_image import regional_map_uri
    meta=metadata if isinstance(metadata,dict) else {}
    title=record.get("title") or record.get("event_id") or "Event"
    incident_id=record.get("event_id") or "Unrecorded"
    what=assessment.get("what_happened") or record.get("description")
    meaning=outlook.get("pc_assessment") or assessment.get("pc_assessment") or assessment.get("what_it_means") or meta.get("pc_assessment")
    forecast=outlook.get("risk_outlook") or meta.get("risk_outlook")
    indicators=_list(outlook.get("monitoring_indicators") or assessment.get("monitoring_indicators") or meta.get("monitoring_indicators"))
    claims=evidence or [v for v in _list(meta.get("source_claims")) if isinstance(v,dict)]
    if not claims:
        claims=[{"publisher":"Recorded event source","url":u,"claim":"Source URL recorded in the event metadata"} for u in _list(meta.get("source_urls")) if _valid_url(u)]
    sources=[]
    for n,claim in enumerate(claims,1):
        url=claim.get("original_url") or claim.get("source_url") or claim.get("url") or claim.get("link")
        link=('<a href="'+_h(url)+'">Read original article / advisory ↗</a><div class="url">'+_h(url)+'</div>') if _valid_url(url) else '<span class="muted">Source link requires completion</span>'
        sources.append('<div class="source"><b>['+str(n)+'] '+_h(claim.get("publisher") or claim.get("document_title") or claim.get("source_name") or "Source")+'</b><span>'+_h(_date(claim.get("published_at")))+
            ' · '+_h(claim.get("verification_status") or claim.get("verification") or "Unreviewed")+'</span><p>'+_h(claim.get("claim") or "Claim text not recorded.")+'</p>'+link+'</div>')
    related_html=[]
    for link,other in related:
        related_html.append('<tr><td>'+_h(_date(other.get("start_date")))+'</td><td>'+_h(other.get("title") or other.get("event_id"))+'</td><td>'+
            _h(link.get("relationship_type") or link.get("relationship"))+'</td><td>'+_h(other.get("verification_status") or "Unrecorded")+'</td></tr>')
    infra=[]
    for v in assets:
        infra.append('<tr><td>'+_h(v.get("name") or v.get("Asset") or "Asset")+'</td><td>'+_h(v.get("mode") or v.get("asset_type") or v.get("Mode") or "Context")+
                     '</td><td>'+_h(v.get("relationship") or v.get("Relationship") or "")+'</td><td>'+_h(v.get("impact_status") or v.get("Impact") or "Not established")+'</td></tr>')
    map_html='<div class="map"><b>REGIONAL GEOGRAPHIC REFERENCE</b><p>Location could not be resolved to a mappable named place. No exact incident position is inferred.</p></div>'
    if map_point and map_point.get("name"):
        name=map_point["name"]
        url=map_point.get("source")
        embedded=None
        try:
            embedded=regional_map_uri(map_point["lat"],map_point["lon"],zoom=map_point.get("zoom",8))
        except (KeyError,TypeError,ValueError): pass
        map_html='<div class="map"><b>REGIONAL GEOGRAPHIC REFERENCE</b><p class="place">'+_h(name)+'</p>'
        if embedded: map_html+='<img class="regional-map" src="'+embedded+'" alt="Regional named-place context map"/>'
        map_html+='<p>Approximate geographic reference — not the verified incident position.</p>'
        if _valid_url(url): map_html+='<p><a href="'+_h(url)+'">Open location map ↗</a></p>'
        map_html+='</div>'
    def table(heads,rows):
        return '<table><thead><tr>'+''.join('<th>'+_h(h)+'</th>' for h in heads)+'</tr></thead><tbody>'+''.join(rows)+'</tbody></table>' if rows else '<p class="muted">No documented linked records.</p>'
    issued=datetime.now(timezone.utc).strftime("%d %B %Y %H:%M UTC")
    logo_html='<div class="brand">POWER &amp; CORRIDORS</div>'
    # A committed transparent brand image is preferred; deployment can also use
    # an explicit st.secrets path for a managed asset. Do not load arbitrary URLs.
    for location in (Path(__file__).with_name("assets")/"pc-logo.png",):
        if location.is_file():
            logo_html='<img class="logo" src="data:image/png;base64,'+base64.b64encode(location.read_bytes()).decode("ascii")+'"/>'
            break
    if logo_html.startswith('<div'):
        try:
            import requests
            response=requests.get(
                "https://storage.ghost.io/c/b7/5a/b75acb20-9d7a-4c8a-83eb-debbe0c72528/content/images/2026/07/power-corridors-logo-dark-matched-transparent-10.png",
                timeout=5)
            response.raise_for_status()
            if response.content.startswith(b"\\x89PNG") and len(response.content)<2000000:
                logo_html='<img class="logo" src="data:image/png;base64,'+base64.b64encode(response.content).decode("ascii")+'"/>'
        except (Exception,): pass
    opening=('<div class="strap">P&C INTELLIGENCE &nbsp; / &nbsp; INCIDENT INTELLIGENCE BRIEF</div>')
    key_judgment=outlook.get("key_judgment") or assessment.get("key_judgment") or meaning
    bottom_line=outlook.get("bottom_line") or assessment.get("bottom_line")
    alternative=outlook.get("alternative_explanation") or assessment.get("alternative_explanation") or meta.get("alternative_explanation")
    gaps=_list(assessment.get("research_gaps") or meta.get("research_gaps"))
    triggers=_list(outlook.get("decision_triggers") or assessment.get("decision_triggers") or meta.get("decision_triggers"))
    implications=[("Operational significance",assessment.get("operational_impact")),
                  ("Commercial significance",assessment.get("commercial_impact"))]
    implications=[(label,value) for label,value in implications if value]
    html='''<!doctype html><html><head><meta charset="utf-8"><style>
    @page{size:A4;margin:19mm 17mm 19mm 17mm;@bottom-left{content:"POWER & CORRIDORS  /  INTELLIGENCE";font:8pt Arial;color:#536679}
    @bottom-right{content:"Page " counter(page);font:8pt Arial;color:#536679}}
    body{font-family:Arial,sans-serif;font-size:10pt;color:#192a38;line-height:1.48}
    .logo{max-width:360px;max-height:72px;object-fit:contain}.regional-map{width:100%;max-height:285px;object-fit:cover;margin:9px 0 4px}.brand{color:#0b344d;font-weight:800;letter-spacing:2.2px;font-size:17pt}.strap{font-size:8pt;letter-spacing:1.8px;color:#42748b}
    .rule{height:4px;background:#13556c;border-right:30px solid #bea365;margin:10px 0 22px}.title{font-size:24pt;line-height:1.15;margin:9px 0}
    .meta{font-size:8pt;color:#526778}.metrics{display:table;width:100%;margin:20px 0;border-collapse:separate;border-spacing:5px}
    .metric{display:table-cell;width:33%;background:#eff4f6;padding:10px}.metric small{display:block;color:#557185;font-size:7pt;text-transform:uppercase}
    .metric strong{font-size:12pt;color:#123c51}.section{margin-top:10px}.section h2{break-after:avoid;font-size:12pt;color:#124e68;border-bottom:1px solid #bdd0d8;padding-bottom:5px}
    .muted{color:#74818b} .box{background:#f1f5f7;padding:12px;border-left:3px solid #226781}
    .map{break-inside:avoid;min-height:95px;background:#eef3f5;border:1px solid #cbd9df;padding:12px}.map b{font-size:8pt;letter-spacing:1.1px}
    .place{font-size:16pt;font-weight:bold;color:#104c64;margin-bottom:0}
    table{border-collapse:collapse;width:100%;font-size:8pt}th{text-align:left;color:#164961;background:#e9f1f5}
    th,td{padding:5px 6px;border-bottom:1px solid #d4e0e6;vertical-align:top}thead{display:table-header-group}tr{break-inside:avoid;page-break-inside:avoid}
    .source{padding:5px 0;border-bottom:1px solid #dce6e9;break-inside:avoid}.source span{color:#657b89;font-size:8pt;display:block}
    .source p{margin:3px 0}.url{font-size:7.5pt;color:#526778;overflow-wrap:anywhere;margin-top:4px}a{color:#096381;text-decoration:underline;overflow-wrap:anywhere}
    li{margin-bottom:2px}.disclaimer{font-size:8pt;color:#566d7b;border-top:1px solid #b9ced6;margin-top:25px;padding-top:8px}
    </style></head><body>'''
    html+=logo_html+'<div class="strap">INDEPENDENT INTELLIGENCE ON MOVEMENT, INFRASTRUCTURE &amp; RISK</div><div class="rule"></div>'
    html+=(opening+'<h1 class="title">'+_h(title)+'</h1><div class="meta">Incident '+_h(incident_id)+' · Event '+_h(_date(record.get("start_date")))+
        ' · Published/exported '+_h(issued)+' · Verification '+_h(record.get("verification_status") or "Unrecorded")+'</div>')
    html+=('<div class="metrics"><div class="metric"><small>Current risk</small><strong>'+_h(outlook.get("current_risk") or "Not rated")+'</strong></div><div class="metric"><small>Confidence</small><strong>'+
        _h(outlook.get("confidence") or "Unassigned")+'</strong></div><div class="metric"><small>Assessed</small><strong>'+_h(_date(outlook.get("assessed_at")))+'</strong></div></div>')
    if outlook.get("valid_until"): html+='<p class="meta">Assessment valid until: '+_h(outlook["valid_until"])+' (check current conditions before reliance).</p>'
    html+='<div class="section"><h2>KEY JUDGEMENT</h2><div class="box">'+_paragraph(key_judgment)+'</div></div>'
    html+='<div class="section"><h2>01 / What happened?</h2>'+_paragraph(what)+'</div>'
    if meaning and meaning != key_judgment:
        html+='<div class="section"><h2>02 / Why it matters — P&C assessment</h2>'+_paragraph(meaning)+'</div>'
    for label,value in implications:
        if value and value not in (meaning,key_judgment):
            html+='<div class="section"><h2>'+_h(label)+'</h2>'+_paragraph(value)+'</div>'
    if alternative:
        html+='<div class="section"><h2>Alternative explanation</h2>'+_paragraph(alternative)+'</div>'
    if gaps:
        html+='<div class="section"><h2>What remains unconfirmed</h2><ul>'+''.join('<li>'+_h(i)+'</li>' for i in gaps)+'</ul></div>'
    html+='<div class="section"><h2>03 / What could happen next? — Risk outlook</h2><div class="box">'+_paragraph(forecast)+'</div></div>'
    html+='<div class="section"><h2>04 / What are we monitoring, and why?</h2>'+('<ul>'+''.join('<li>'+_h(i)+'</li>' for i in indicators)+'</ul>' if indicators else '<p class="muted">No reviewed indicators recorded.</p>')+'</div>'
    if triggers:
        html+='<div class="section"><h2>Decision triggers</h2><ul>'+''.join('<li>'+_h(i)+'</li>' for i in triggers)+'</ul></div>'
    html+='<div class="section"><h2>05 / Geographic and infrastructure context</h2>'+map_html+table(["Asset","Mode","Recorded relationship","Impact status"],infra)+'</div>'
    html+='<div class="section"><h2>06 / Connected developments</h2>'+table(["Date","Development","Relationship","Status"],related_html)+'</div>'
    if bottom_line and bottom_line not in (key_judgment,meaning):
        html+='<div class="section"><h2>BOTTOM LINE</h2><div class="box">'+_paragraph(bottom_line)+'</div></div>'
    html+='<div class="section"><h2>07 / Evidence and source provenance</h2>'+(''.join(sources) if sources else '<p class="muted">No individual source claims available in this record.</p>')+'</div>'
    html+='<div class="disclaimer">Power &amp; Corridors · powerncorridors.com · Analytical judgments are qualified by the cited evidence. Contextual links do not establish causation, attack attribution, damage, closure or current operating status. This PDF is a dated snapshot, not a live notice.</div></body></html>'
    return HTML(string=html,base_url="https://powerncorridors.com/").write_pdf()
