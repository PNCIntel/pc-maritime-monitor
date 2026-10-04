from __future__ import annotations
import os, re, json
from datetime import datetime, timezone, timedelta
from urllib.parse import urlsplit
import pandas as pd
import streamlit as st

try:
    from shared.pc_auth import service_client, require_login
except Exception:
    from pc_auth import service_client, require_login


TRADE_INCLUDE = re.compile(
    r"(port|terminal|shipping|ship|vessel|tanker|container|freight|cargo|rail|railway|truck|road|airport|aviation|air cargo|"
    r"logistics|warehouse|supply chain|corridor|canal|strait|border|customs|pipeline|lng|oil|gas|energy|refinery|"
    r"acquisition|investment|project|capacity|yard|shipyard|service|route|concession|dredg|berth|fleet|strike|closure|"
    r"disruption|attack|sanction|tariff|trade)", re.I)
TRADE_EXCLUDE = re.compile(r"\b(election|presidency|parliament|senate|chamber of deputies|house of representatives)\b", re.I)
INTEL_INCLUDE = re.compile(
    r"(attack|missile|drone|projectile|piracy|hijack|boarding|seizure|interdiction|war|conflict|security|"
    r"sanction|smuggl|traffick|fraud|crime|terror|sabotage|strike|protest|riot|closure|disruption|cyber|"
    r"fire|explosion|collision|grounding|casualt|military|naval|airspace|border|election|political|unrest|"
    r"intelligence|risk|threat)", re.I)

TRADE_PRIORITY = [
    (re.compile(r"(closure|suspend|attack|strike|disruption|blocked|grounding|collision|fire|explosion)", re.I), 45),
    (re.compile(r"(strait of hormuz|red sea|suez|panama|black sea|bab el-mandeb)", re.I), 35),
    (re.compile(r"(port|terminal|airport|rail|freight|cargo|tanker|container|pipeline|lng)", re.I), 20),
    (re.compile(r"(acquisition|investment|capacity|project|facility|agreement|contract)", re.I), 10),
]
INTEL_PRIORITY = [
    (re.compile(r"(attack|missile|drone|projectile|piracy|seizure|interdiction|explosion|casualt)", re.I), 50),
    (re.compile(r"(strait of hormuz|red sea|suez|black sea|gulf of aden|yanbu)", re.I), 30),
    (re.compile(r"(sanction|security|military|naval|airspace|border|cyber|strike|protest)", re.I), 20),
]

def _clean(v):
    if v is None: return ""
    if isinstance(v, float) and pd.isna(v): return ""
    s=str(v).replace("\\n"," ").replace("\n"," ").replace("\r"," ").replace("\t"," ")
    return re.sub(r"\s+"," ",s).strip()

def _meta(row):
    m=row.get("metadata") or {}
    if isinstance(m,dict): return m
    if isinstance(m,str):
        try:
            x=json.loads(m)
            return x if isinstance(x,dict) else {}
        except Exception: return {}
    return {}

def _date(v):
    s=_clean(v)
    if not s: return None
    try: return pd.to_datetime(s,utc=True,errors="coerce")
    except Exception: return None

def _sources(row):
    m=_meta(row); raw=[]
    for key in ("research_sources","sources","source_evidence"):
        val=m.get(key)
        if isinstance(val,list): raw.extend(val)
        elif val: raw.append(val)
    val=row.get("source_evidence")
    if isinstance(val,list): raw.extend(val)
    elif val:
        try:
            x=json.loads(val) if isinstance(val,str) else val
            raw.extend(x if isinstance(x,list) else [x])
        except Exception: raw.append(val)
    out=[]; seen=set()
    for x in raw:
        u=x.get("url") or x.get("source_url") if isinstance(x,dict) else str(x)
        u=_clean(u)
        if u.startswith(("http://","https://")) and u not in seen:
            seen.add(u); out.append((u, x.get("title") or x.get("publisher") if isinstance(x,dict) else urlsplit(u).netloc))
    return out

def _event_text(r):
    m=_meta(r)
    return " ".join(_clean(x) for x in [
        r.get("title"),r.get("event_type"),r.get("event_domain"),r.get("location"),
        r.get("description"),r.get("operational_impact"),r.get("commercial_impact"),
        r.get("commercial_implications"),m.get("why_it_matters"),m.get("assessment")
    ] if x)

def _relevant(r,mode):
    text=_event_text(r)
    if mode=="trade":
        if TRADE_EXCLUDE.search(text) and not TRADE_INCLUDE.search(text.replace("election","")): return False
        return bool(TRADE_INCLUDE.search(text))
    return bool(INTEL_INCLUDE.search(text))

def _score(r,mode):
    text=_event_text(r)
    score=0
    for rx,pts in (TRADE_PRIORITY if mode=="trade" else INTEL_PRIORITY):
        if rx.search(text): score+=pts
    d=_date(r.get("start_date"))
    if d is not None and not pd.isna(d):
        age=max(0,(pd.Timestamp.now(tz="UTC")-d).days)
        score += max(0,18-age)
    if _clean(r.get("operational_impact")): score+=8
    if _clean(r.get("commercial_impact") or r.get("commercial_implications")): score+=8
    return score

@st.cache_data(ttl=45,show_spinner=False)
def _events(_sb):
    # Prefer the reviewed publication view because this is where new Power Admin
    # loads appear after canonical publication. Fall back to canonical events.
    try:
        rows=(_sb.table("pc_v12_live_developments").select("*")
              .order("start_date",desc=True).limit(400).execute().data or [])
        if rows: return rows
    except Exception: pass
    try:
        return (_sb.table("pc_events").select("*")
                .order("start_date",desc=True).limit(400).execute().data or [])
    except Exception:
        return []

@st.cache_data(ttl=60,show_spinner=False)
def _links(_sb,event_id):
    """Merge canonical and published graph edges for one event.

    A successful empty query is not evidence that no published links exist, so
    both graph surfaces are read and de-duplicated.
    """
    found=[]
    seen=set()
    for table in ("pc_event_links","pc_v12_published_links"):
        try:
            rows=(_sb.table(table)
                  .select("linked_type,linked_id,linked_name,relationship")
                  .eq("event_id",event_id).limit(100).execute().data or [])
        except Exception:
            rows=[]
        for r in rows:
            key=(str(r.get("linked_type") or ""),str(r.get("linked_id") or ""),
                 str(r.get("relationship") or ""))
            if key in seen:
                continue
            seen.add(key); found.append(r)
    return found

def _count(sb,table):
    try:
        res=sb.table(table).select("*",count="exact").limit(1).execute()
        return int(res.count or 0)
    except Exception:return None

def _style(theme="Dark"):
    if theme=="Light":
        palette="--bg:#f4f6f8;--panel:#ffffff;--panel2:#f8fafc;--line:#cbd5df;--text:#17202a;--muted:#5f6b78;--gold:#9a7626;--red:#a45149;--green:#4f7d67"
    else:
        palette="--bg:#0a111c;--panel:#101927;--panel2:#0d1623;--line:#26364a;--text:#edf2f7;--muted:#9facbd;--gold:#d1ad59;--red:#d37a72;--green:#72a78c"
    st.markdown(f"""
    <style>
    :root{{{palette}}}
    .stApp{{background:var(--bg);color:var(--text)}}
    [data-testid="stSidebar"]{{background:var(--panel2)!important;border-right:1px solid var(--line)}}
    [data-testid="stSidebar"] *{{color:var(--text)!important}}
    .block-container{{max-width:1550px;padding-top:1.3rem}}
    h1,h2,h3,h4,p,label,span{{color:var(--text)!important}}
    .pc-k{{color:var(--gold);font-size:.67rem;font-weight:700;letter-spacing:.13em;text-transform:uppercase}}
    .pc-sub{{color:var(--muted);font-size:.9rem;margin:.25rem 0 1rem}}
    .pc-meta{{color:var(--gold);font-size:.68rem;letter-spacing:.06em;text-transform:uppercase}}
    .pc-summary{{color:var(--muted);font-size:.88rem;line-height:1.45}}
    .pc-impact{{padding:.65rem .8rem;background:var(--panel2);border-left:2px solid var(--gold);margin:.45rem 0}}
    [data-testid="stExpander"]{{background:var(--panel);border:1px solid var(--line);border-radius:7px;margin-bottom:.42rem}}
    [data-testid="stMetric"]{{background:var(--panel);border:1px solid var(--line);border-top:2px solid var(--gold);padding:.65rem .8rem;border-radius:6px}}
    [data-testid="stDataFrame"]{{border:1px solid var(--line);border-radius:6px}}
    div.stButton>button{{background:var(--panel);color:var(--gold);border:1px solid #725f34}}
    [data-baseweb="input"]>div,[data-baseweb="select"]>div,input{{background:var(--panel)!important;color:var(--text)!important}}
    .pc-status{{display:inline-block;padding:.12rem .38rem;border:1px solid var(--line);border-radius:3px;font-size:.66rem;color:var(--muted);margin-right:.3rem}}
    </style>""",unsafe_allow_html=True)

def _display_location(v):
    if isinstance(v,dict):
        return _clean(v.get("name") or v.get("location") or v.get("country") or v.get("region"))
    if isinstance(v,str):
        s=v.strip()
        if s.startswith("{") and s.endswith("}"):
            try:
                obj=json.loads(s)
                if isinstance(obj,dict):
                    return _clean(obj.get("name") or obj.get("location") or obj.get("country") or obj.get("region"))
            except Exception:
                pass
    return _clean(v)

def _event_expander(sb,r,mode,key_prefix="evt"):
    title=_clean(r.get("title")) or "Untitled development"
    date=_clean(r.get("start_date"))[:10]
    typ=_clean(r.get("event_type") or r.get("event_domain") or "Development")
    loc=_display_location(r.get("location") or r.get("country"))
    m=_meta(r)
    eid=_clean(r.get("event_id"))
    label=f"{date} · {title}" if date else title
    with st.expander(label,expanded=False):
        st.markdown(f'<div class="pc-meta">{typ}{" · "+loc if loc else ""}</div>',unsafe_allow_html=True)

        desc=_clean(m.get("what_happened") or r.get("description"))
        why=_clean(m.get("why_it_matters") or m.get("what_it_means") or r.get("what_it_means"))
        op=_clean(r.get("operational_impact") or m.get("operational_impact"))
        commercial=_clean(r.get("commercial_impact") or r.get("commercial_implications") or m.get("commercial_implications") or m.get("business_implications"))
        capacity=_clean(m.get("capacity_impact") or m.get("infrastructure_impact") or m.get("capacity_change"))
        assess=_clean(m.get("assessment") or m.get("pc_assessment") or r.get("pc_assessment"))

        links=_links(sb,eid) if eid else []

        if mode=="trade":
            if desc:
                st.markdown("**Development**")
                st.write(desc)
            if op:
                st.markdown('<div class="pc-impact"><b>Operational change</b><br>'+op+'</div>',unsafe_allow_html=True)
            if commercial:
                st.markdown('<div class="pc-impact"><b>Trade / commercial effect</b><br>'+commercial+'</div>',unsafe_allow_html=True)
            if capacity:
                st.markdown("**Capacity / infrastructure effect**")
                st.write(capacity)
            if links:
                st.markdown("**Companies / assets / corridors affected**")
                for x in links[:15]:
                    nm=_clean(x.get("linked_name")) or _clean(x.get("linked_id"))
                    rel=_clean(x.get("relationship")).replace("_"," ")
                    if nm:
                        st.markdown("- "+nm+(f" — {rel}" if rel else ""))
        else:
            if desc:
                st.markdown("**What happened**")
                st.write(desc)
            if why:
                st.markdown("**Why it matters**")
                st.write(why)
            if op:
                st.markdown('<div class="pc-impact"><b>Operational impact</b><br>'+op+'</div>',unsafe_allow_html=True)
            if assess:
                st.markdown("**Assessment**")
                st.write(assess)
            if links:
                st.markdown("**Linked actors / assets / vessels**")
                for x in links[:15]:
                    nm=_clean(x.get("linked_name")) or _clean(x.get("linked_id"))
                    rel=_clean(x.get("relationship")).replace("_"," ")
                    if nm:
                        st.markdown("- "+nm+(f" — {rel}" if rel else ""))

        inds=m.get("monitoring_indicators") or r.get("monitoring_indicators")
        if inds:
            st.markdown("**What to watch operationally**" if mode=="trade" else "**Monitoring / next indicators**")
            if isinstance(inds,list):
                for x in inds[:8]:
                    v=x.get("indicator") or x.get("text") if isinstance(x,dict) else str(x)
                    if v: st.markdown("- "+_clean(v))
            else:
                st.write(_clean(inds))

        src=_sources(r)
        if src:
            st.markdown("**Sources**")
            for u,lbl in src[:8]:
                st.markdown(f"- [{_clean(lbl) or urlsplit(u).netloc}]({u})")

def _priority_feed(sb,rows,mode,n=10):
    ranked=sorted([r for r in rows if _relevant(r,mode)],key=lambda r:_score(r,mode),reverse=True)[:n]
    if not ranked: st.info("No matching developments in the current canonical feed."); return
    for i,r in enumerate(ranked):
        _event_expander(sb,r,mode,f"prio_{i}")

def _recent_feed(sb,rows,mode,n=30):
    rel=[r for r in rows if _relevant(r,mode)]
    rel.sort(key=lambda r:str(r.get("start_date") or ""),reverse=True)
    for i,r in enumerate(rel[:n]): _event_expander(sb,r,mode,f"recent_{i}")

def render_operating_picture(mode="trade"):
    title="Trade Operating Picture" if mode=="trade" else "Intelligence Operating Picture"
    deck=("What is moving, disrupted, constrained or changing across multimodal trade and logistics."
          if mode=="trade" else
          "What changed, why it matters, who is involved and what should be watched next.")
    brand="P&C Trade" if mode=="trade" else "P&C Intelligence"

    auth_required=os.getenv("PC_REQUIRE_AUTH","false").lower()=="true"
    if auth_required:
        try: require_login("TRADE" if mode=="trade" else "INTELLIGENCE",brand)
        except TypeError: require_login()
    sb=service_client()
    if sb is None:
        st.error("Supabase connection is not configured."); st.stop()

    with st.sidebar:
        st.markdown(f'<div class="pc-k">POWER & CORRIDORS INTELLIGENCE</div>',unsafe_allow_html=True)
        st.markdown(f"### {brand}")
        st.caption("Shared canonical database · different analytical lens")
        theme=st.radio("Appearance",["Dark","Light"],
                       index=1 if st.session_state.get("pc_op_theme","Dark")=="Light" else 0,
                       horizontal=True,key="pc_op_theme")
        page=st.radio("Workspace",["Operating picture","Latest developments","Search"],index=0)
        st.divider()
        if st.button("Refresh database",use_container_width=True):
            st.cache_data.clear(); st.rerun()

    _style(theme)
    rows=_events(sb)
    st.markdown('<div class="pc-k">POWER & CORRIDORS / OPERATING PICTURE</div>',unsafe_allow_html=True)
    st.title(title)
    st.markdown(f'<div class="pc-sub">{deck}</div>',unsafe_allow_html=True)

    q=st.text_input("Find a development, company, vessel, port, corridor or place",
                    placeholder="Hormuz, AD Ports, Navi Mumbai, CLI, KEZAD, rail, tanker…")
    if q.strip():
        terms=[t.casefold() for t in q.split() if t.strip()]
        matched=[r for r in rows if all(t in _event_text(r).casefold() for t in terms)]
        st.caption(f"{len(matched)} matching developments in the current feed")
        for i,r in enumerate(matched[:50]): _event_expander(sb,r,mode,f"search_{i}")
        return

    if page=="Latest developments":
        st.subheader("Latest relevant developments")
        st.caption("Newest relevant records first. Expand in place; no jump down the page.")
        _recent_feed(sb,rows,mode,50)
        return

    if page=="Search":
        st.info("Use the search box above. It searches the current canonical development feed across title, description, impact and location.")
        return

    relevant=[r for r in rows if _relevant(r,mode)]
    disruptions=[r for r in relevant if re.search(r"(disruption|closure|suspend|strike|attack|fire|explosion|collision|grounding|blocked)",_event_text(r),re.I)]
    future=[]
    now=pd.Timestamp.now(tz="UTC")
    for r in relevant:
        d=_date(r.get("start_date"))
        if d is not None and not pd.isna(d) and d>=now and d<=now+pd.Timedelta(days=14):
            future.append(r)

    c1,c2,c3,c4=st.columns(4)
    c1.metric("Relevant developments",len(relevant))
    c2.metric("Active disruption signals",len(disruptions))
    c3.metric("Canonical events",_count(sb,"pc_events") or "—")
    c4.metric("Corridors",_count(sb,"pc_trade_corridors") or "—")

    left,right=st.columns([3.2,1.1],gap="large")
    with left:
        st.subheader("Priority developments")
        st.caption("Ranked by operational / analytical significance, then recency. Expand each item in place.")
        _priority_feed(sb,relevant,mode,10)
    with right:
        st.subheader("Forward watch")
        if future:
            for r in sorted(future,key=lambda x:str(x.get("start_date") or ""))[:8]:
                st.markdown(f"**{_clean(r.get('start_date'))[:10]}**  \\n{_clean(r.get('title'))}")
        else:
            st.caption("No relevant dated items in the next 14 days.")

        st.divider()
        st.subheader("Recently loaded / current")
        newest=sorted(relevant,key=lambda r:str(r.get("published_at") or r.get("created_at") or r.get("start_date") or ""),reverse=True)[:8]
        for r in newest:
            st.markdown(f"**{_clean(r.get('title'))}**")
            st.caption((_clean(r.get("start_date"))[:10]+" · "+_clean(r.get("location"))).strip(" ·"))

    st.divider()
    if mode=="trade":
        st.subheader("Active operational disruptions")
        st.caption("Trade-relevant events with a direct movement, capacity, infrastructure or service effect.")
        for i,r in enumerate(sorted(disruptions,key=lambda x:_score(x,mode),reverse=True)[:12]):
            _event_expander(sb,r,mode,f"disrupt_{i}")
    else:
        st.subheader("Active situations")
        st.caption("Security, disruption and escalation developments requiring continuing analytical attention.")
        for i,r in enumerate(sorted(disruptions,key=lambda x:_score(x,mode),reverse=True)[:12]):
            _event_expander(sb,r,mode,f"situation_{i}")
