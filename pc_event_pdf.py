"""Branded, source-qualified P&C incident intelligence PDF. No screenshot printing."""
from __future__ import annotations
from datetime import datetime, timezone
from html import escape
from io import BytesIO
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
        map_html='<div class="map"><b>REGIONAL GEOGRAPHIC REFERENCE</b><p class="place">'+_h(name)+'</p><p>Approximate named-place context — not the verified incident position.</p>'
        if _valid_url(url): map_html+='<p><a href="'+_h(url)+'">Open location map ↗</a></p>'
        map_html+='</div>'
    def table(heads,rows):
        return '<table><thead><tr>'+''.join('<th>'+_h(h)+'</th>' for h in heads)+'</tr></thead><tbody>'+''.join(rows)+'</tbody></table>' if rows else '<p class="muted">No documented linked records.</p>'
    issued=datetime.now(timezone.utc).strftime("%d %B %Y %H:%M UTC")
    html='''<!doctype html><html><head><meta charset="utf-8"><style>
    @page{size:A4;margin:19mm 17mm 19mm 17mm;@bottom-left{content:"POWER & CORRIDORS  /  INTELLIGENCE";font:8pt Arial;color:#536679}
    @bottom-right{content:"Page " counter(page);font:8pt Arial;color:#536679}}
    body{font-family:Arial,sans-serif;font-size:10pt;color:#192a38;line-height:1.48}
    .brand{color:#0b344d;font-weight:800;letter-spacing:2.2px;font-size:17pt}.strap{font-size:8pt;letter-spacing:1.8px;color:#42748b}
    .rule{height:4px;background:#13556c;border-right:30px solid #bea365;margin:10px 0 22px}.title{font-size:24pt;line-height:1.15;margin:9px 0}
    .meta{font-size:8pt;color:#526778}.metrics{display:table;width:100%;margin:20px 0;border-collapse:separate;border-spacing:5px}
    .metric{display:table-cell;width:33%;background:#eff4f6;padding:10px}.metric small{display:block;color:#557185;font-size:7pt;text-transform:uppercase}
    .metric strong{font-size:12pt;color:#123c51}.section{margin-top:19px;break-inside:avoid}.section h2{font-size:12pt;color:#124e68;border-bottom:1px solid #bdd0d8;padding-bottom:5px}
    .muted{color:#74818b} .box{background:#f1f5f7;padding:12px;border-left:3px solid #226781}
    .map{min-height:95px;background:#eef3f5;border:1px solid #cbd9df;padding:12px}.map b{font-size:8pt;letter-spacing:1.1px}
    .place{font-size:16pt;font-weight:bold;color:#104c64;margin-bottom:0}
    table{border-collapse:collapse;width:100%;font-size:8pt}th{text-align:left;color:#164961;background:#e9f1f5}
    th,td{padding:7px 6px;border-bottom:1px solid #d4e0e6;vertical-align:top}
    .source{padding:8px 0;border-bottom:1px solid #dce6e9;break-inside:avoid}.source span{color:#657b89;font-size:8pt;display:block}
    .source p{margin:4px 0}.url{font-size:7.5pt;color:#526778;overflow-wrap:anywhere;margin-top:4px}a{color:#096381;text-decoration:underline;overflow-wrap:anywhere}
    li{margin-bottom:5px}.disclaimer{font-size:8pt;color:#566d7b;border-top:1px solid #b9ced6;margin-top:25px;padding-top:8px}
    </style></head><body>'''
    html+='<div class="brand">POWER &amp; CORRIDORS</div><div class="strap">INDEPENDENT INTELLIGENCE ON MOVEMENT, INFRASTRUCTURE &amp; RISK</div><div class="rule"></div>'
    html+=('<div class="strap">INCIDENT INTELLIGENCE BRIEF</div><h1 class="title">'+_h(title)+'</h1><div class="meta">Incident '+_h(incident_id)+' · Event '+_h(_date(record.get("start_date")))+
        ' · Published/exported '+_h(issued)+' · Verification '+_h(record.get("verification_status") or "Unrecorded")+'</div>')
    html+=('<div class="metrics"><div class="metric"><small>Current risk</small><strong>'+_h(outlook.get("current_risk") or "Not rated")+'</strong></div><div class="metric"><small>Confidence</small><strong>'+
        _h(outlook.get("confidence") or "Unassigned")+'</strong></div><div class="metric"><small>Assessed</small><strong>'+_h(_date(outlook.get("assessed_at")))+'</strong></div></div>')
    if outlook.get("valid_until"): html+='<p class="meta">Assessment valid until: '+_h(outlook["valid_until"])+' (check current conditions before reliance).</p>'
    html+='<div class="section"><h2>01 / What happened?</h2>'+_paragraph(what)+'</div>'
    html+='<div class="section"><h2>02 / What does it mean? — P&C assessment</h2>'+_paragraph(meaning)+'</div>'
    html+='<div class="section"><h2>03 / What could happen next? — Risk outlook</h2><div class="box">'+_paragraph(forecast)+'</div></div>'
    html+='<div class="section"><h2>04 / What are we monitoring, and why?</h2>'+('<ul>'+''.join('<li>'+_h(i)+'</li>' for i in indicators)+'</ul>' if indicators else '<p class="muted">No reviewed indicators recorded.</p>')+'</div>'
    html+='<div class="section"><h2>05 / Geographic and infrastructure context</h2>'+map_html+table(["Asset","Mode","Recorded relationship","Impact status"],infra)+'</div>'
    html+='<div class="section"><h2>06 / Connected developments</h2>'+table(["Date","Development","Relationship","Status"],related_html)+'</div>'
    html+='<div class="section"><h2>07 / Evidence and source provenance</h2>'+(''.join(sources) if sources else '<p class="muted">No individual source claims available in this record.</p>')+'</div>'
    html+='<div class="disclaimer">Power &amp; Corridors · powerncorridors.com · Analytical judgments are qualified by the cited evidence. Contextual links do not establish causation, attack attribution, damage, closure or current operating status. This PDF is a dated snapshot, not a live notice.</div></body></html>'
    return HTML(string=html,base_url="https://powerncorridors.com/").write_pdf()
