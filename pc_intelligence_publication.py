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
    .pcpub{max-width:850px;margin:auto;padding:38px 43px;background:#fff;color:#182536;font:16px/1.65 Georgia,serif}
    .pcpub .kicker,.pcpub .meta,.pcpub .overline{font:700 11px/1.5 Arial,sans-serif;letter-spacing:2px;color:#a58028;text-transform:uppercase}
    .pcpub h1{font:700 34px/1.17 Georgia,serif;color:#10213a;margin:14px 0}
    .pcpub h2{font:700 21px/1.25 Georgia,serif;color:#10213a;margin:32px 0 12px;border-top:1px solid #dce3ec;padding-top:18px}
    .pcpub .dek{font:18px/1.5 Georgia,serif;color:#3d4c5e;border-left:3px solid #a58028;padding-left:18px;margin:24px 0}
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
    for b in blocks:
        typ=b.get("kind")
        if typ=="References":continue
        out.append('<h2>'+h(b.get("title"))+'</h2>')
        if typ=="Asset table":
            cols=b.get("columns") or list((b.get("rows") or [{}])[0].keys())
            cols=[c for c in cols if c.casefold() not in ("record","event id","linked id","record status")]
            rows=b.get("rows") or []
            if rows:
                out.append('<table><thead><tr>'+''.join('<th>'+h(c)+'</th>' for c in cols)+'</tr></thead><tbody>')
                for row in rows:out.append('<tr>'+''.join('<td>'+h(row.get(c) or "Not established")+'</td>' for c in cols)+'</tr>')
                out.append('</tbody></table>')
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
