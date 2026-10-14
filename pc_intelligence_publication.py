"""Publication-focused rendering and evidence audit for Intelligence reports."""
import html
import re

def evidence_audit(events):
    total=len(events)
    sourced=sum(bool(e.get("sources")) for e in events)
    return {"total":total,"sourced":sourced,"missing":total-sourced}

def render_publication(title, date, region, product, summary, blocks, sources, events=None):
    h=lambda x:html.escape(str(x or ""))
    audit=evidence_audit(events or [])
    css="""<style>
    .pcpub{max-width:980px;margin:auto;padding:44px 50px;background:#fff;color:#182536;font:15px/1.6 Arial,sans-serif;border-top:6px solid #a58028}
    .pcpub .kicker,.pcpub .meta,.pcpub .overline{font:700 11px/1.5 Arial,sans-serif;letter-spacing:2px;color:#a58028;text-transform:uppercase}
    .pcpub h1{font:700 39px/1.12 Georgia,serif;color:#10213a;margin:18px 0;max-width:800px}
    .pcpub h2{font:700 21px/1.25 Arial,sans-serif;color:#10213a;margin:34px 0 13px;border-top:2px solid #dce3ec;padding-top:18px}
    .pcpub .dek{font:18px/1.5 Georgia,serif;color:#3d4c5e;border-left:4px solid #a58028;padding:14px 18px;margin:24px 0;background:#f5f7fa} .pcpub .judgments{border:1px solid #dce3ec;background:#f7f8fa;padding:18px 22px;margin:26px 0}.pcpub .judgments h2{margin:0 0 13px;padding:0;border:0;font:700 12px Arial;letter-spacing:2px;text-transform:uppercase;color:#99701d}.pcpub .judgment{display:grid;grid-template-columns:34px 1fr;gap:12px;padding:11px 0;border-top:1px solid #dce3ec}.pcpub .judgment b{color:#a58028;font:700 20px Arial}.pcpub .judgment span{font:15px/1.55 Arial}.pcpub .audit{border-left:4px solid #a58028;padding:10px 14px;background:#faf8f2;margin:22px 0}
    .pcpub .meta{color:#687789;letter-spacing:1px}.pcpub p{margin:0 0 15px}
    .pcpub table{border-collapse:collapse;width:100%;font:12px/1.45 Arial,sans-serif;margin:18px 0}
    .pcpub th{color:#10213a;text-align:left;border-bottom:2px solid #a58028;padding:9px 6px}
    .pcpub td{border-bottom:1px solid #dce3ec;padding:9px 6px;vertical-align:top}
    .pcpub .note{font:12px/1.5 Arial,sans-serif;color:#627286}
    .pcpub a{color:#805d17;overflow-wrap:anywhere}
    </style>"""
    out=[css,'<article class="pcpub"><div class="kicker">Power &amp; Corridors / Intelligence</div>',
         '<h1>'+h(title)+'</h1>','<div class="meta">'+h(date)+' · '+h(region or "Global")+' · '+h(product)+'</div>']
    if summary:out.append('<div class="dek">'+h(summary)+'</div>')
    # Lead with existing analytical judgments, rather than another duplicate chronology.
    judgments=next((b for b in blocks if str(b.get("title","")).lower() in ("key judgements","key judgments") and b.get("body")),None)
    if judgments:
        items=[p.strip() for p in re.split(r'\\n\\s*\\n',str(judgments.get("body") or "")) if p.strip()]
        if len(items)==1:
            items=[p.strip() for p in re.split(r'(?m)^\\s*(?:[-*]|\\d+[.)])\\s+',items[0]) if p.strip()]
        if len(items)>1:
            out.append('<section class="judgments"><h2>Key judgments</h2>')
            for n,item in enumerate(items[:5],1):
                out.append('<div class="judgment"><b>'+str(n).zfill(2)+'</b><span>'+h(item)+'</span></div>')
            out.append('</section>')
    if events and audit["missing"]:
        out.append('<div class="audit"><strong>Evidence limitation:</strong> '+str(audit["missing"])+
                   ' of '+str(audit["total"])+
                   ' selected incident records lack a linked source URL. Reported claims require editorial verification.</div>')
    for b in blocks:
        typ=b.get("kind")
        if typ=="References":continue
        if judgments is b and len(items)>1:continue
        out.append('<h2>'+h(b.get("title"))+'</h2>')
        if typ=="Asset table":
            cols=b.get("columns") or list((b.get("rows") or [{}])[0].keys())
            cols=[c for c in cols if c.casefold() not in ("record","event id","linked id","record status")]
            rows=b.get("rows") or []
            if rows:
                out.append('<table><thead><tr>'+''.join('<th>'+h(c)+'</th>' for c in cols)+'</tr></thead><tbody>')
                for row in rows:out.append('<tr>'+''.join('<td>'+h(row.get(c) or "Not established")+'</td>' for c in cols)+'</tr>')
                out.append('</tbody></table>')
                if b.get('caption'):out.append('<p class="note">'+h(b['caption'])+'</p>')
        else:
            for paragraph in re.split(r'\n\s*\n',str(b.get("body") or "")):
                if paragraph.strip():
                    txt=h(paragraph.strip())
                    txt=re.sub(r'\[(\d{1,3})\]',lambda m: '<sup><a href="#source-'+m[1]+'">['+m[1]+']</a></sup>' if 1<=int(m[1])<=len(sources) else m[0],txt)
                    out.append('<p>'+txt+'</p>')
    if events:
        out.append('<h2>Evidence coverage</h2><p class="note">'+str(audit["sourced"])+' of '+str(audit["total"])+' incident records have at least one linked source URL. Source presence is not independent verification.</p>')
    out.append('<h2>Sources and limitations</h2>')
    if sources:
        for n,url in enumerate(sources,1):
            out.append('<p class="note" id="source-'+str(n)+'">['+str(n)+'] <a href="'+html.escape(url,quote=True)+'" rel="noopener noreferrer" target="_blank">'+h(url)+'</a></p>')
    else:out.append('<p class="note">No source URLs were retrieved; publication requires editorial source review.</p>')
    out.append('</article>')
    return ''.join(out)
