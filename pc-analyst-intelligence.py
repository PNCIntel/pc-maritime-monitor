from __future__ import annotations
from pathlib import Path
import os, sys, io, re, json, html, zipfile, hashlib
import xml.etree.ElementTree as ET
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

ROOT=Path(__file__).resolve().parent
SHARED=ROOT/"shared"
if str(SHARED) not in sys.path:
    sys.path.insert(0,str(SHARED))

from pc_auth import require_super_admin, service_client
try:
    from pc_ai import research as ai_research, configured as ai_configured
except Exception:
    ai_research=None
    ai_configured=lambda: False

st.set_page_config(page_title="P&C Intelligence Analyst",page_icon="◈",layout="wide")

if os.getenv("PC_REQUIRE_AUTH","false").lower()=="true":
    ctx=require_super_admin()
else:
    ctx={"global_role":"super_admin","email":"analyst-local"}

sb=service_client()

st.markdown("""
<style>
:root{--bg:#07111f;--panel:#0d1a2b;--line:#28415f;--text:#f3f6fa;--muted:#b8c5d4;--gold:#d7b66a}
.stApp{background:var(--bg);color:var(--text)}
[data-testid="stSidebar"]{background:#091725!important}
h1,h2,h3,p,label{color:var(--text)!important}
.pc-card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px;margin-bottom:10px}
.pc-k{color:var(--gold);font-size:.72rem;letter-spacing:.12em;text-transform:uppercase;font-weight:700}
</style>
""",unsafe_allow_html=True)

PRODUCTS={
    "Alert":{
        "product_type":"alert","ghost_tag":"intelligence-alert","site_path":"/intelligence/alerts/",
        "fields":[
            "Current Situation","What Happened","What Remains Unconfirmed","Operational Impact",
            "Trade / Commercial Impact","Assessment","Indicators to Watch"
        ]
    },
    "Assessment":{
        "product_type":"assessment","ghost_tag":"strategic-assessment","site_path":"/intelligence/assessments/",
        "fields":[
            "Executive Judgement","Key Judgements","Context","Analysis","Operational / Commercial Impact",
            "Scenarios","Indicators / What Would Change the Judgement"
        ]
    },
    "Monitoring":{
        "product_type":"monitoring","ghost_tag":"monitoring-indicators","site_path":"/intelligence/monitoring/",
        "fields":[
            "Current Judgement","Why We Are Monitoring","Priority Indicators","Baseline","Trigger / Threshold",
            "Assessment Impact","Secondary Indicators","Structural Indicators","What Would Change the Judgement"
        ]
    },
    "Situation Report":{
        "product_type":"situation_report","ghost_tag":"intelligence-situation-report","site_path":"/intelligence/situation-reports/",
        "fields":[
            "Executive Summary","Current Situation","Key Developments","Operational Impact","Trade / Commercial Impact",
            "Key Actors / Assets","Outlook / Next 24–72 Hours","Indicators to Watch"
        ]
    },
}

HEADING_ALIASES={
    "current judgement":"Current Judgement","why we are monitoring":"Why We Are Monitoring",
    "priority indicators":"Priority Indicators","baseline":"Baseline","trigger threshold":"Trigger / Threshold",
    "trigger / threshold":"Trigger / Threshold","assessment impact":"Assessment Impact",
    "secondary indicators":"Secondary Indicators","structural indicators":"Structural Indicators",
    "what would change the judgement":"What Would Change the Judgement",
    "current situation":"Current Situation","what happened":"What Happened",
    "what remains unconfirmed":"What Remains Unconfirmed","operational impact":"Operational Impact",
    "trade commercial impact":"Trade / Commercial Impact","trade / commercial impact":"Trade / Commercial Impact",
    "assessment":"Assessment","indicators to watch":"Indicators to Watch",
    "executive judgement":"Executive Judgement","key judgements":"Key Judgements","context":"Context",
    "analysis":"Analysis","operational commercial impact":"Operational / Commercial Impact",
    "scenarios":"Scenarios","indicators what would change the judgement":"Indicators / What Would Change the Judgement",
    "executive summary":"Executive Summary","key developments":"Key Developments",
    "key actors assets":"Key Actors / Assets","outlook next 24 72 hours":"Outlook / Next 24–72 Hours",
}

def title(text,copy=""):
    st.markdown("<div class='pc-k'>POWER & CORRIDORS INTELLIGENCE</div>",unsafe_allow_html=True)
    st.title(text)
    if copy: st.caption(copy)

def _docx_text(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        xml=z.read("word/document.xml")
    root=ET.fromstring(xml)
    ns="{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    lines=[]
    for p in root.iter(ns+"p"):
        s="".join((n.text or "") for n in p.iter(ns+"t")).strip()
        if s: lines.append(s)
    return "\n".join(lines)

def extract_text(upload):
    raw=upload.getvalue()
    n=upload.name.lower()
    if n.endswith(".docx"): return _docx_text(raw)
    if n.endswith((".txt",".md")): return raw.decode("utf-8-sig",errors="replace")
    if n.endswith(".pdf"):
        from pypdf import PdfReader
        return "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(raw)).pages)
    raise RuntimeError("Supported: DOCX, PDF, TXT, MD")

def norm_heading(s):
    return re.sub(r"[^a-z0-9]+"," ",str(s or "").casefold()).strip()

def parse_sections(text,allowed_fields):
    lines=[x.strip() for x in text.splitlines()]
    sections={}
    current=None
    buf=[]
    allowed=set(allowed_fields)
    def flush():
        nonlocal buf,current
        if current and buf:
            sections[current]="\n".join(buf).strip()
        buf=[]
    for line in lines:
        key=HEADING_ALIASES.get(norm_heading(line.rstrip(":")))
        if key in allowed:
            flush(); current=key; continue
        # Bold-like / all caps simple heading fallback.
        if len(line)<90:
            key=HEADING_ALIASES.get(norm_heading(line))
            if key in allowed:
                flush(); current=key; continue
        if current:
            buf.append(line)
    flush()
    return sections

def extract_urls(text):
    urls=re.findall(r'https?://[^\s<>\]\)"]+',text or "")
    out=[]
    for u in urls:
        u=u.rstrip(".,;")
        if u not in out: out.append(u)
    return out

def fourteen_words(text):
    words=re.findall(r"\S+",str(text or "").strip())
    return " ".join(words[:14])

def ai_structure_document(text,product):
    spec=PRODUCTS[product]
    fields=spec["fields"]
    contract={
        "report":{
            "title":"",
            "region":"",
            "confidence":"",
            "summary_14":"",
            "fields":{f:"" for f in fields},
            "sources":[{"url":"","title":"","publisher":""}]
        }
    }
    prompt=f"""Structure the supplied document into a Power & Corridors Intelligence {product}.
Use only information present in the document. Do not add outside facts.
Preserve uncertainty. Populate only supported fields. Return JSON exactly matching this contract:
{json.dumps(contract,indent=2)}

DOCUMENT:
{text[:60000]}
"""
    result=ai_research(prompt,"P&C INTELLIGENCE AUTHORING",False,output_contract=json.dumps(contract))
    return result.get("report",result) if isinstance(result,dict) else {}

def canonical_search(kind,q,limit=80):
    cfg={
        "entity":("pc_entities","entity_id,name,entity_type,hq_country","name","entity_id"),
        "asset":("pc_assets","asset_id,name,asset_type,country","name","asset_id"),
        "mobile_asset":("pc_mobile_assets","mobile_asset_id,name,asset_type,imo,flag","name","mobile_asset_id"),
        "event":("pc_events","event_id,title,event_type,start_date","title","event_id"),
    }
    table,cols,disp,pk=cfg[kind]
    try:
        rows=(sb.table(table).select(cols).ilike(disp,f"%{q}%").limit(limit).execute().data or [])
    except Exception:
        rows=[]
    return rows,pk,disp

def build_html(product,title_text,report_date,region,confidence,summary,fields,sources,email=False):
    gold="#b08a2e"; navy="#101827"; line="#d6dce5"; bg="#ffffff"; text="#17202a"
    width="760px"
    parts=[f"""<div style="max-width:{width};margin:0 auto;background:{bg};color:{text};font-family:Arial,Helvetica,sans-serif;line-height:1.62;">
<div style="border-top:5px solid {gold};padding:24px 8px 14px;">
<div style="font-size:12px;letter-spacing:2px;color:{gold};font-weight:700;">POWER &amp; CORRIDORS INTELLIGENCE</div>
<h1 style="font-size:30px;line-height:1.15;margin:8px 0 8px;color:{navy};">{html.escape(title_text)}</h1>
<div style="color:#5b6675;font-size:14px;">{html.escape(str(report_date))} · {html.escape(region or 'Global')} · {html.escape(product)} · Confidence: {html.escape(confidence or 'Not stated')}</div>
</div>"""]
    if summary:
        parts.append(f"""<div style="border:1px solid {line};padding:14px 16px;margin:10px 8px 20px;background:#f7f9fc;">
<strong>Summary:</strong> {html.escape(summary)}
</div>""")
    for name,value in fields.items():
        if not str(value or "").strip(): continue
        paras="".join(f"<p style='margin:0 0 12px'>{html.escape(p.strip())}</p>" for p in re.split(r"\n\s*\n",str(value)) if p.strip())
        parts.append(f"""<div style="padding:4px 8px 16px;border-bottom:1px solid {line};">
<h2 style="font-size:18px;color:{navy};margin:12px 0 8px;">{html.escape(name)}</h2>
{paras}
</div>""")
    if sources:
        parts.append(f"<div style='padding:16px 8px'><h2 style='font-size:18px;color:{navy}'>Sources</h2><ol>")
        for s in sources:
            url=s.get("url") if isinstance(s,dict) else str(s)
            title=s.get("title") if isinstance(s,dict) else ""
            pub=s.get("publisher") if isinstance(s,dict) else ""
            label=title or url
            if url:
                parts.append(f"<li style='margin-bottom:7px'><a href='{html.escape(url)}'>{html.escape(label)}</a>{' — '+html.escape(pub) if pub else ''}</li>")
        parts.append("</ol></div>")
    parts.append("</div>")
    return "".join(parts)

def save_document_record(upload,text,title_text):
    if not sb: return None
    raw=upload.getvalue()
    h=hashlib.sha256(raw).hexdigest()
    try:
        hit=(sb.table("pc_documents").select("document_id").eq("file_sha256",h).limit(1).execute().data or [])
        payload={
            "title":title_text or Path(upload.name).stem,
            "document_type":"intelligence_source",
            "file_name":upload.name,
            "file_sha256":h,
            "extracted_text":text,
            "metadata":{"analyst_authoring":True}
        }
        if hit:
            did=hit[0]["document_id"]
            sb.table("pc_documents").update(payload).eq("document_id",did).execute()
        else:
            did=sb.table("pc_documents").insert(payload).execute().data[0]["document_id"]
        return did
    except Exception:
        return None

page=st.sidebar.radio("Analyst workspace",["Author Intelligence","Draft Library","Published / Exported"])
st.sidebar.caption("P&C site structure: Alerts · Assessments · Monitoring · Situation Reports")

if page=="Author Intelligence":
    title("Intelligence Authoring","Structured analyst production aligned directly to the Power & Corridors Intelligence website.")

    product=st.selectbox("Product type",list(PRODUCTS))
    spec=PRODUCTS[product]

    source_doc=st.file_uploader("Load source Word/PDF document (optional)",type=["docx","pdf","txt","md"])
    doc_text=""
    source_doc_id=None
    if source_doc:
        try:
            doc_text=extract_text(source_doc)
            st.success(f"Extracted {len(doc_text):,} characters from {source_doc.name}.")
            with st.expander("Source document text"):
                st.text(doc_text[:15000])

            c1,c2=st.columns(2)
            if c1.button("Populate form from document",type="primary"):
                parsed=parse_sections(doc_text,spec["fields"])
                for f,v in parsed.items():
                    st.session_state[f"field_{product}_{f}"]=v
                urls=extract_urls(doc_text)
                if urls:
                    st.session_state["report_sources_text"]="\n".join(urls)
                # Try first non-empty line as title if not already set.
                first=next((x.strip() for x in doc_text.splitlines() if x.strip()),"")
                if first and not st.session_state.get("report_title"):
                    st.session_state["report_title"]=first[:180]
                st.success(f"Populated {len(parsed)} structured section(s).")
                st.rerun()

            if c2.button("AI structure document",disabled=not ai_configured()):
                with st.spinner("Structuring document into P&C intelligence fields..."):
                    rr=ai_structure_document(doc_text,product)
                if rr.get("title"): st.session_state["report_title"]=rr["title"]
                if rr.get("region"): st.session_state["report_region"]=rr["region"]
                if rr.get("confidence"): st.session_state["report_confidence"]=rr["confidence"]
                if rr.get("summary_14"): st.session_state["report_summary"]=rr["summary_14"]
                for f,v in (rr.get("fields") or {}).items():
                    if f in spec["fields"] and v:
                        st.session_state[f"field_{product}_{f}"]=v
                srcs=rr.get("sources") or []
                if srcs:
                    st.session_state["report_sources_text"]="\n".join(x.get("url","") for x in srcs if isinstance(x,dict) and x.get("url"))
                st.success("AI structure complete. Review every field before saving.")
                st.rerun()
        except Exception as exc:
            st.exception(exc)

    c1,c2,c3,c4=st.columns([2.2,1,1,1])
    report_title=c1.text_input("Headline / title",key="report_title")
    report_date=c2.date_input("Report date")
    region=c3.text_input("Region",key="report_region")
    confidence=c4.selectbox("Confidence",["","Low","Medium","Moderate","High"],key="report_confidence")

    summary=st.text_input("14-word summary",key="report_summary")
    if st.button("Create 14-word summary from title"):
        st.session_state["report_summary"]=fourteen_words(report_title)
        st.rerun()

    st.markdown("### Structured report")
    fields={}
    for f in spec["fields"]:
        fields[f]=st.text_area(f,key=f"field_{product}_{f}",height=130)

    st.markdown("### Sources")
    source_text=st.text_area("Source URLs — one per line",key="report_sources_text",height=110)
    sources=[{"url":x.strip()} for x in source_text.splitlines() if x.strip().startswith(("http://","https://"))]

    st.markdown("### Link canonical records")
    link_rows=[]
    for kind,label in [("entity","Companies / entities"),("asset","Ports / assets"),("mobile_asset","Vessels"),("event","Events")]:
        q=st.text_input(f"Find {label}",key=f"linkq_{kind}")
        if q.strip():
            rows,pk,disp=canonical_search(kind,q)
            options={f"{r.get(disp) or r.get(pk)} | {r.get(pk)}":r.get(pk) for r in rows}
            chosen=st.multiselect(f"Link {label}",list(options),key=f"links_{kind}")
            link_rows.extend({"linked_type":kind,"linked_id":options[x],"relationship":"referenced_in"} for x in chosen)

    web_html=build_html(product,report_title,report_date,region,confidence,summary,fields,sources,False)
    email_html=build_html(product,report_title,report_date,region,confidence,summary,fields,sources,True)

    tabs=st.tabs(["Preview","Web HTML","Email-safe HTML"])
    with tabs[0]:
        components.html(web_html,height=900,scrolling=True)
    with tabs[1]:
        st.code(web_html,language="html")
        st.download_button("Download web HTML",web_html,file_name=f"{product.lower().replace(' ','-')}.html",mime="text/html")
    with tabs[2]:
        st.code(email_html,language="html")
        st.download_button("Download email-safe HTML",email_html,file_name=f"{product.lower().replace(' ','-')}-email.html",mime="text/html")

    c1,c2,c3=st.columns(3)
    if c1.button("Save draft",type="primary",disabled=not bool(report_title.strip())):
        if not sb:
            st.error("Supabase is not configured.")
        else:
            if source_doc and doc_text:
                source_doc_id=save_document_record(source_doc,doc_text,report_title)
            payload={
                "product_type":spec["product_type"],"subtype":product,"title":report_title,
                "report_date":str(report_date),"region":region or None,"status":"draft",
                "confidence":confidence or None,"summary_14":summary or None,
                "site_path":spec["site_path"],"ghost_tag":spec["ghost_tag"],"fields":fields,
                "body_markdown":"\n\n".join(f"## {k}\n{v}" for k,v in fields.items() if v.strip()),
                "web_html":web_html,"email_html":email_html,"source_document_id":source_doc_id,
                "created_by":ctx.get("email"),"metadata":{"site_stream":product}
            }
            rid=sb.table("pc_intelligence_reports").insert(payload).execute().data[0]["report_id"]
            for lr in link_rows:
                sb.table("pc_intelligence_report_links").insert({"report_id":rid,**lr}).execute()
            for i,s in enumerate(sources,1):
                sb.table("pc_intelligence_report_sources").insert({
                    "report_id":rid,"source_order":i,"source_url":s["url"]
                }).execute()
            st.success(f"Draft saved: {rid}")
            st.session_state["_last_report_id"]=rid

    if c2.button("Save as ready for review",disabled=not bool(report_title.strip())):
        if not sb: st.error("Supabase is not configured.")
        else:
            source_doc_id=save_document_record(source_doc,doc_text,report_title) if source_doc and doc_text else None
            rid=sb.table("pc_intelligence_reports").insert({
                "product_type":spec["product_type"],"subtype":product,"title":report_title,
                "report_date":str(report_date),"region":region or None,"status":"review",
                "confidence":confidence or None,"summary_14":summary or None,
                "site_path":spec["site_path"],"ghost_tag":spec["ghost_tag"],"fields":fields,
                "body_markdown":"\n\n".join(f"## {k}\n{v}" for k,v in fields.items() if v.strip()),
                "web_html":web_html,"email_html":email_html,"source_document_id":source_doc_id,
                "created_by":ctx.get("email")
            }).execute().data[0]["report_id"]
            st.success(f"Report sent to review: {rid}")

    if c3.button("Clear form"):
        for k in list(st.session_state):
            if k.startswith("field_") or k.startswith("report_") or k.startswith("linkq_") or k.startswith("links_"):
                del st.session_state[k]
        st.rerun()

elif page=="Draft Library":
    title("Draft Library","Open analyst drafts and reports awaiting review.")
    if not sb:
        st.error("Supabase required.")
    else:
        rows=(sb.table("pc_intelligence_reports").select(
            "report_id,product_type,subtype,title,report_date,region,status,confidence,summary_14,created_by,updated_at"
        ).in_("status",["draft","review"]).order("updated_at",desc=True).limit(300).execute().data or [])
        st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)

elif page=="Published / Exported":
    title("Published / Exported","Approved and published P&C Intelligence products.")
    if not sb:
        st.error("Supabase required.")
    else:
        rows=(sb.table("pc_intelligence_reports").select(
            "report_id,product_type,subtype,title,report_date,region,status,confidence,summary_14,published_at,updated_at"
        ).in_("status",["approved","published"]).order("report_date",desc=True).limit(300).execute().data or [])
        st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
