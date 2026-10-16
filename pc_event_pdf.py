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

def _plain(value):
    return str(value or "Unrecorded").replace("_"," ").strip()

def _paragraph(value):
    return "<p>"+_h(value).replace("\\n","<br/>")+"</p>" if value else '<p class="muted">Not established in the current record.</p>'

def create_incident_brief(record, assessment, outlook, evidence, related, assets, metadata=None, map_point=None, editorial=None, publication_type="assessment", publication_context=None):
    """Return PDF bytes built from the same canonical dossier, not generated incident claims."""
    from weasyprint import HTML
    from pc_event_map_image import regional_map_uri
    meta=metadata if isinstance(metadata,dict) else {}
    edited=editorial if isinstance(editorial,dict) else {}
    context=publication_context if isinstance(publication_context,dict) else {}
    flash=publication_type=="flash"
    title=record.get("title") or record.get("event_id") or "Event"
    what=edited.get("what_happened") or assessment.get("what_happened") or record.get("description")
    meaning=edited.get("why_it_matters") or outlook.get("pc_assessment") or assessment.get("pc_assessment") or assessment.get("what_it_means") or meta.get("pc_assessment")
    forecast=outlook.get("risk_outlook") or meta.get("risk_outlook") or edited.get("risk_outlook")
    if str(outlook.get("current_risk") or "").lower().startswith("not assessed") and forecast and re.search(r"\\b(low|moderate|high|severe|critical) risk (persists|remains|is|continues)\\b",str(forecast),re.I):
        forecast=outlook.get("risk_outlook") or meta.get("risk_outlook") or ""
    indicators=_list(edited.get("monitoring_analysis") or outlook.get("monitoring_indicators") or assessment.get("monitoring_indicators") or meta.get("monitoring_indicators"))
    claims=evidence or [v for v in _list(meta.get("source_claims")) if isinstance(v,dict)]
    if not claims:
        claims=[{"publisher":"Recorded event source","url":u,"claim":"Source URL recorded in the event metadata"} for u in _list(meta.get("source_urls")) if _valid_url(u)]
    sources=[]
    for n,claim in enumerate(claims,1):
        url=claim.get("original_url") or claim.get("source_url") or claim.get("url") or claim.get("link")
        link=('<a href="'+_h(url)+'">Read original article / advisory ↗</a><div class="url">'+_h(url)+'</div>') if _valid_url(url) else '<span class="muted">Source link requires completion</span>'
        sources.append('<div class="source"><b>['+str(n)+'] '+_h(claim.get("publisher") or claim.get("document_title") or claim.get("source_name") or "Source")+'</b><span>'+_h(_date(claim.get("published_at")))+
            ' · '+_h(_plain(claim.get("verification_status") or claim.get("verification") or "Unreviewed"))+'</span><p>'+_h(claim.get("claim") or "Claim text not recorded.")+'</p>'+link+'</div>')
    related_html=[]
    for link,other in related:
        related_html.append('<tr><td>'+_h(_date(other.get("start_date")))+'</td><td>'+_h(other.get("title") or other.get("event_id"))+'</td><td>'+
            _h(_plain(link.get("relationship_type") or link.get("relationship")))+'</td><td>'+_h(_plain(other.get("verification_status") or "Unrecorded"))+'</td></tr>')
    infra=[]
    for v in assets:
        infra.append('<tr><td>'+_h(v.get("name") or v.get("Asset") or "Asset")+'</td><td>'+_h(v.get("mode") or v.get("asset_type") or v.get("Mode") or "Context")+
                     '</td><td>'+_h(_plain(v.get("relationship") or v.get("Relationship") or ""))+'</td><td>'+_h(v.get("impact_status") or v.get("Impact") or "Not established")+'</td></tr>')
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
        else: map_html+='<p class="muted">Basemap tiles unavailable at publication; locality reference only. Do not interpret this as a plotted casualty location.</p>'
        map_html+='<p>Approximate geographic reference — not the verified incident position.</p>'
        if _valid_url(url): map_html+='<p><a href="'+_h(url)+'">Open location map ↗</a></p>'
        map_html+='</div>'
    def table(heads,rows):
        return '<table><thead><tr>'+''.join('<th>'+_h(h)+'</th>' for h in heads)+'</tr></thead><tbody>'+''.join(rows)+'</tbody></table>' if rows else '<p class="muted">No documented linked records.</p>'
    issued=datetime.now(timezone.utc).strftime("%d %B %Y %H:%M UTC")
    logo_html='<div class="brand">POWER &amp; CORRIDORS</div>'
    # A committed transparent brand image is preferred; deployment can also use
    # an explicit st.secrets path for a managed asset. Do not load arbitrary URLs.
    for location in (Path(__file__).with_name("assets")/"power-corridors-logo-light-matched-transparent.png",):
        if location.is_file():
            logo_html='<img class="logo" src="data:image/png;base64,'+base64.b64encode(location.read_bytes()).decode("ascii")+'"/>'
            break
    opening=('<div class="strap">POWER &amp; CORRIDORS INTELLIGENCE &nbsp; / &nbsp; '+("FLASH INTELLIGENCE ALERT" if flash else "CONNECTED INTELLIGENCE ASSESSMENT")+"</div>")
    key_judgment=edited.get("key_judgment") or outlook.get("key_judgment") or assessment.get("key_judgment") or meaning
    bottom_line=edited.get("bottom_line") or outlook.get("bottom_line") or assessment.get("bottom_line")
    alternative=edited.get("alternative_explanation") or outlook.get("alternative_explanation") or assessment.get("alternative_explanation") or meta.get("alternative_explanation")
    gaps=_list(edited.get("uncertainties") or assessment.get("research_gaps") or meta.get("research_gaps"))
    triggers=_list(edited.get("decision_triggers") or outlook.get("decision_triggers") or assessment.get("decision_triggers") or meta.get("decision_triggers"))
    implications=[("Operational significance",edited.get("operational_significance") or assessment.get("operational_impact")),
                  ("Commercial significance",edited.get("commercial_significance") or assessment.get("commercial_impact"))]
    implications=[(label,value) for label,value in implications if value]
    if flash:
        # Keep clickable citations but avoid printing long URLs in the compact alert.
        sources=[re.sub(r'<div class="url">.*?</div>', '', item, flags=re.S) for item in sources]
    html='''<!doctype html><html><head><meta charset="utf-8"><style>
    @page{size:A4;margin:19mm 17mm 19mm 17mm;@bottom-left{content:"POWER & CORRIDORS / INTELLIGENCE · DATED SNAPSHOT";font:7pt Arial;color:#536679}
    @bottom-right{content:"Page " counter(page);font:8pt Arial;color:#536679}}
    body{font-family:Arial,sans-serif;font-size:9.5pt;color:#192a38;line-height:1.38}
    .logo{width:315px;height:auto;max-height:90px;object-fit:contain}.regional-map{width:100%;max-height:285px;object-fit:cover;margin:9px 0 4px}.brand{color:#0b344d;font-weight:800;letter-spacing:2.2px;font-size:17pt}.strap{font-size:8pt;letter-spacing:1.8px;color:#42748b}
    .rule{height:4px;background:#13556c;border-right:30px solid #bea365;margin:10px 0 22px}.title{font-size:24pt;line-height:1.15;margin:9px 0}
    .issue-date{font-size:10pt;font-weight:bold;color:#124e68;margin:14px 0 5px}.meta{font-size:8pt;color:#526778}.metrics{display:table;width:100%;margin:20px 0;border-collapse:separate;border-spacing:5px}
    .metric{display:table-cell;width:33%;background:#eff4f6;padding:10px}.metric small{display:block;color:#557185;font-size:7pt;text-transform:uppercase}
    .metric strong{font-size:12pt;color:#123c51}.section{margin-top:10px}.section h2{break-after:avoid;font-size:12pt;color:#124e68;border-bottom:1px solid #bdd0d8;padding-bottom:5px}
    .muted{color:#74818b} .box{background:#f1f5f7;padding:12px;border-left:3px solid #226781}
    .map{break-inside:avoid;min-height:95px;background:#eef3f5;border:1px solid #cbd9df;padding:12px}.map b{font-size:8pt;letter-spacing:1.1px}
    .place{font-size:16pt;font-weight:bold;color:#104c64;margin-bottom:0}
    table{border-collapse:collapse;width:100%;font-size:8pt}th{text-align:left;color:#164961;background:#e9f1f5}
    th,td{padding:5px 6px;border-bottom:1px solid #d4e0e6;vertical-align:top}thead{display:table-header-group}tr{break-inside:avoid;page-break-inside:avoid}
    .source{padding:4px 0;border-bottom:1px solid #dce6e9;break-inside:avoid}.source span{color:#657b89;font-size:8pt;display:block}
    .source p{margin:3px 0}.url{font-size:7.5pt;color:#526778;overflow-wrap:anywhere;margin-top:4px}a{color:#096381;text-decoration:underline;overflow-wrap:anywhere}
    li{margin-bottom:2px}.disclaimer{font-size:8pt;color:#566d7b;border-top:1px solid #b9ced6;margin-top:25px;padding-top:8px}
    .disclaimer{break-inside:avoid;page-break-inside:avoid}.prior-event h3{font-size:9.5pt;color:#164961;margin-bottom:3px}.prior-event p{margin:3px 0 6px}.prior-event{break-inside:avoid;border-bottom:1px solid #dce6e9;padding:5px 0}
    </style></head><body>'''
    if flash:
        html=html.replace('@page{size:A4;margin:19mm 17mm 19mm 17mm;', '@page{size:A4;margin:15mm 17mm 15mm 17mm;')
        html=html.replace('.rule{height:4px;', '.rule{height:3px;').replace('margin:10px 0 22px}', 'margin:7px 0 12px}')
        html=html.replace('.metrics{display:table;width:100%;margin:20px 0;', '.metrics{display:table;width:100%;margin:10px 0;')
        html=html.replace('.source{padding:4px 0;', '.source{padding:2px 0;')
    html+=logo_html+'<div class="strap"><b>POWER &amp; CORRIDORS INTELLIGENCE</b> · INDEPENDENT INTELLIGENCE ON MOVEMENT, INFRASTRUCTURE &amp; RISK</div><div class="rule"></div>'
    html+=(opening+'<div class="issue-date">ISSUED '+_h(issued)+'</div><h1 class="title">'+_h(title)+'</h1><div class="meta">Event date '+_h(_date(record.get("start_date")))+
        ' · Verification '+_h(record.get("verification_status") or "Unrecorded")+'</div>')
    risk_full=str(outlook.get("current_risk") or "Not assessed")
    confidence_full=str(outlook.get("confidence") or "Unassigned")
    risk_short=risk_full.split(" — ",1)[0].split(" - ",1)[0]
    confidence_short=confidence_full.split(" — ",1)[0].split(" - ",1)[0]
    html+=('<div class="metrics"><div class="metric"><small>Current risk</small><strong>'+_h(risk_short)+'</strong></div><div class="metric"><small>Confidence</small><strong>'+
        _h(confidence_short)+'</strong></div><div class="metric"><small>Assessed</small><strong>'+_h(_date(outlook.get("assessed_at")))+'</strong></div></div>')
    if risk_full!=risk_short or confidence_full!=confidence_short:
        html+='<p class="meta">'+_h("Risk: "+risk_full+" · Evidence: "+confidence_full)+'</p>'
    if outlook.get("valid_until"): html+='<p class="meta">Assessment valid until: '+_h(outlook["valid_until"])+' (check current conditions before reliance).</p>'
    if flash:
        html+='<div class="section"><h2>THE DEVELOPMENT</h2>'+_paragraph(what)+'</div>'
        if key_judgment and key_judgment != what:
            html+='<div class="section"><h2>KEY JUDGEMENT</h2><div class="box">'+_paragraph(key_judgment)+'</div></div>'
        if meaning and meaning not in (what,key_judgment):
            html+='<div class="section"><h2>IMMEDIATE IMPLICATIONS</h2>'+_paragraph(meaning)+'</div>'
        if indicators:
            html+='<div class="section"><h2>PRIORITY MONITORING</h2><ul>'+''.join('<li>'+_h(i)+'</li>' for i in indicators[:4])+'</ul></div>'
        if triggers:
            html+='<div class="section"><h2>DECISION TRIGGERS</h2><ul>'+''.join('<li>'+_h(i)+'</li>' for i in triggers[:3])+'</ul></div>'
        if map_point and map_html:
            html+='<div class="section"><h2>LOCATION REFERENCE</h2>'+map_html+'</div>'
    else:
        # Longer assessment is structured around the model and analytical argument,
        # rather than replaying the sequence of a flash alert.
        html+='<div class="section"><h2>EXECUTIVE ASSESSMENT</h2><div class="box">'+_paragraph(key_judgment)+'</div></div>'
        profile=context.get("vessel_profile") or {}
        company_history=context.get("company_history") or []
        history=edited.get("historical_context")
        wider=edited.get("wider_context")
        if history or wider:
            html+='<div class="section"><h2>BACKGROUND AND STRATEGIC CONTEXT</h2>'
            if history: html+=_paragraph(history)
            if wider and wider!=history: html+=_paragraph(wider)
            html+='</div>'
        identities=context.get("identity_history") or []
        dated_roles=context.get("dated_company_roles") or []
        if identities or dated_roles:
            html+='<div class="section"><h2>VESSEL BIOGRAPHY — IDENTITY AND CORPORATE HISTORY</h2>'
            html+='<p>Records below refer to the same resolved hull. A source observation does not establish a precise renaming date; dated corporate roles are not assumed to remain current.</p>'
            if identities:
                rows=[]
                for entry in identities:
                    h=entry.get("identity") or {}
                    label=h.get("identity_value")
                    if not label: continue
                    when=h.get("observed_on") or h.get("valid_from") or "Date unrecorded"
                    qualifier=("Source observation; rename date unverified" if h.get("date_basis")!="effective_period" else
                               "Recorded effective period: "+str(h.get("valid_from") or "unknown")+" to "+str(h.get("valid_to") or "unrecorded"))
                    url=h.get("source_url")
                    if _valid_url(url): qualifier+=' · <a href="'+_h(url)+'">Source ↗</a>'
                    rows.append('<tr><td>'+_h(label)+'</td><td>'+_h(_date(when))+'</td><td>'+qualifier+'</td></tr>')
                if rows: html+=table(["Recorded identity","Dated evidence","Qualification"],rows)
            if dated_roles:
                rows=[]
                for item in dated_roles:
                    role=item.get("role") or {}; company=item.get("company") or {}
                    if not company.get("name"): continue
                    period=("From "+str(role["valid_from"]) if role.get("valid_from") else
                            "Observed "+str(role["as_of"]) if role.get("as_of") else "Start date unrecorded")
                    if role.get("valid_to"): period+=" · to "+str(role["valid_to"])
                    else: period+=" · end date unrecorded"
                    rows.append('<tr><td>'+_h(company["name"])+'</td><td>'+_h(_plain(role.get("asset_role")))+'</td><td>'+_h(period)+'</td></tr>')
                if rows:
                    html+='<h3>Recorded company roles over time</h3><p>Legal owner, operator, manager and ISM records describe different responsibilities. An undated role is not evidence of continuous tenure.</p>'
                    html+=table(["Company","Recorded role","Evidence period"],rows)
            html+='</div>'
        graph_rows=[]
        if profile.get("name"):
            identity=str(profile["name"])+(" · IMO "+str(profile["imo"]) if profile.get("imo") else "")
            graph_rows.append('<tr><td>'+_h(identity)+'</td><td>Resolved mobile asset</td><td>Identity recorded in the model</td></tr>')
        for item in company_history:
            company=item.get("company") or {}; edge=item.get("relationship") or {}
            if company.get("name"):
                provenance=edge.get("metadata") or {}
                observation=provenance.get("observed_on") or provenance.get("observation_date")
                qualifier=(str(edge.get("confidence") or "Unrated")+" confidence"+
                           (" · observed "+str(observation) if observation else " · date unverified"))
                graph_rows.append('<tr><td>'+_h(company["name"])+'</td><td>'+_h(_plain(edge.get("relationship_type")))+'</td><td>'+_h(qualifier)+'</td></tr>')
        if graph_rows or infra:
            html+='<div class="section"><h2>CONNECTED NETWORK AND EXPOSURE</h2>'
            if graph_rows and edited.get("network_synthesis"): html+=_paragraph(edited["network_synthesis"])
            if graph_rows: html+=table(["Subject","Recorded role","Evidence qualification"],graph_rows)
            if infra and edited.get("infrastructure_synthesis"): html+=_paragraph(edited["infrastructure_synthesis"])
            if infra: html+='<h3>Infrastructure and dependencies</h3>'+table(["Asset","Mode","Recorded relationship","Impact status"],infra)
            html+='</div>'
        html+='<div class="section"><h2>GEOGRAPHIC CONTEXT</h2>'+(_paragraph(edited.get("geographic_synthesis")) if edited.get("geographic_synthesis") else "")+map_html+'</div>'
        html+='<div class="section"><h2>EVENT AND EVIDENCE</h2>'+_paragraph(what)+'</div>'
        if meaning and meaning!=key_judgment:
            html+='<div class="section"><h2>ANALYSIS — WHY IT MATTERS</h2>'+_paragraph(meaning)+'</div>'
        for label,value in implications:
            if value and value not in (meaning,key_judgment):
                html+='<div class="section"><h2>'+_h(label)+'</h2>'+_paragraph(value)+'</div>'
        if related_html:
            html+='<div class="section"><h2>CONNECTED DEVELOPMENTS</h2>'
            if edited.get("connected_developments_synthesis"):
                html+=_paragraph(edited["connected_developments_synthesis"])
            for edge, prior in related:
                description=prior.get("description") or (prior.get("metadata") or {}).get("summary")
                if not description: continue
                relation=_plain(edge.get("relationship_type") or edge.get("relationship") or "Contextual connection")
                html+='<div class="prior-event"><h3>'+_h(_date(prior.get("start_date")))+" · "+_h(prior.get("title") or "Prior development")+'</h3>'
                html+=_paragraph(description)
                if edge.get("rationale"): html+='<p><b>Connection to this assessment:</b> '+_h(edge["rationale"])+'</p>'
                else: html+='<p class="meta">Recorded relationship: '+_h(relation)+'. Context alone does not establish common cause or actor.</p>'
                html+='</div>'
            html+=table(["Date","Development","Relationship","Status"],related_html)+'</div>'
        if alternative or gaps:
            html+='<div class="section"><h2>ALTERNATIVES AND INTELLIGENCE GAPS</h2>'
            if alternative: html+=_paragraph(alternative)
            if gaps: html+='<ul>'+''.join('<li>'+_h(i)+'</li>' for i in gaps)+'</ul>'
            html+='</div>'
        if forecast: html+='<div class="section"><h2>OUTLOOK</h2>'+_paragraph(forecast)+'</div>'
        if triggers: html+='<div class="section"><h2>WHAT WOULD CHANGE THE ASSESSMENT</h2><ul>'+''.join('<li>'+_h(i)+'</li>' for i in triggers)+'</ul></div>'
        if indicators: html+='<div class="section"><h2>MONITORING AND INDICATORS</h2><ul>'+''.join('<li>'+_h(i)+'</li>' for i in indicators)+'</ul></div>'
    html+='<div class="section"><h2>SOURCES &amp; EVIDENCE</h2>'+(''.join(sources) if sources else '<p class="muted">No individual source claims available in this record.</p>')+'</div>'
    if flash:
        # Page footers already identify the publisher; do not create an orphan page
        # for a long disclaimer in a short-form alert.
        html+='</body></html>'
    else:
        html+='<div class="disclaimer">Power &amp; Corridors · powerncorridors.com · Analytical judgments are qualified by the cited evidence. Contextual links do not establish causation, attack attribution, damage, closure or current operating status. This PDF is a dated snapshot, not a live notice.</div></body></html>'
    return HTML(string=html,base_url="https://powerncorridors.com/").write_pdf()
