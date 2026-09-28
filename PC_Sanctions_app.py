
import os, re
import pandas as pd
import streamlit as st
try:
    from supabase import create_client
except Exception:
    create_client=None

REGIONS={
"Global":[],
"Middle East / Gulf":["UAE","United Arab Emirates","Saudi Arabia","Oman","Qatar","Bahrain","Kuwait","Iraq","Iran"],
"Red Sea & East Africa":["Saudi Arabia","Yemen","Egypt","Sudan","Eritrea","Djibouti","Somalia","Ethiopia"],
"Europe":["United Kingdom","France","Germany","Netherlands","Belgium","Italy","Spain","Poland","Romania","Bulgaria","Greece","Turkey","Türkiye","Ukraine","Russia"],
"Africa":["South Africa","Nigeria","Kenya","Tanzania","Mozambique","Morocco","Algeria","Tunisia","Ghana","Angola","Namibia"],
"South Asia":["India","Pakistan","Bangladesh","Sri Lanka","Nepal","Maldives"],
"Asia-Pacific":["China","Japan","South Korea","Singapore","Malaysia","Indonesia","Philippines","Vietnam","Australia","New Zealand"],
"Central Asia & Caucasus":["Kazakhstan","Uzbekistan","Turkmenistan","Kyrgyzstan","Tajikistan","Georgia","Azerbaijan","Armenia"],
"North America":["United States","USA","Canada","Mexico"],
"South America":["Brazil","Argentina","Chile","Peru","Colombia","Ecuador","Uruguay"],
"Arctic":["Canada","United States","USA","Russia","Norway","Denmark","Greenland","Iceland","Finland","Sweden"]}

def secret(name):
    try:return str(st.secrets.get(name,"") or "")
    except Exception:return str(os.getenv(name,"") or "")

@st.cache_resource
def db():
    url=secret("SUPABASE_URL"); key=secret("SUPABASE_SERVICE_ROLE_KEY") or secret("SUPABASE_KEY") or secret("SUPABASE_ANON_KEY")
    if create_client and url and key:
        try:return create_client(url,key)
        except Exception:return None
    return None

@st.cache_data(ttl=90,show_spinner=False)
def rows(table,columns="*",limit=5000):
    sb=db()
    if sb is None:return pd.DataFrame()
    try:return pd.DataFrame(sb.table(table).select(columns).limit(limit).execute().data or [])
    except Exception:return pd.DataFrame()

def region_filter(df,region):
    if df is None or df.empty or region=="Global":return df.copy() if isinstance(df,pd.DataFrame) else pd.DataFrame()
    cols=[c for c in df.columns if any(k in c.lower() for k in ["country","countries","region","location","hq_"])]
    if not cols:return df
    blob=pd.Series("",index=df.index,dtype="string")
    for c in cols:blob=blob.str.cat(df[c].fillna("").astype(str),sep=" ")
    pat="|".join(re.escape(x) for x in REGIONS.get(region,[]))
    return df[blob.str.contains(pat,case=False,regex=True,na=False)].copy() if pat else df

def search(df,q):
    if df is None or df.empty or not q:return df
    blob=df.fillna("").astype(str).agg(" ".join,axis=1)
    return df[blob.str.contains(re.escape(q),case=False,regex=True,na=False)]

def show(df,h=420):
    if df is None or df.empty:st.caption("No matching canonical records are currently available.")
    else:st.dataframe(df,hide_index=True,use_container_width=True,height=h)

def metrics(items):
    cs=st.columns(len(items))
    for c,(k,v) in zip(cs,items):c.metric(k,v)

def style():
    st.markdown("""<style>
    :root{--bg:#0b1117;--panel:#111a22;--line:#293744;--text:#f1eee6;--muted:#aab6c0;--gold:#d4af57}
    .stApp,[data-testid="stAppViewContainer"]{background:var(--bg);color:var(--text)}
    [data-testid="stSidebar"]{background:#080d12;border-right:1px solid var(--line)}
    h1,h2,h3,p,label,li,span{color:var(--text)}
    .pc-k{color:var(--gold);font-size:.72rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase}
    .pc-deck{color:var(--muted);max-width:1000px;margin-bottom:1rem}
    .pc-card{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:14px 16px;margin:8px 0}
    .pc-card b{color:var(--gold)}
    [data-testid="stMetric"]{background:var(--panel);border:1px solid var(--line);border-top:2px solid var(--gold);padding:.7rem;border-radius:6px}
    </style>""",unsafe_allow_html=True)

def hero(k,t,d):
    st.markdown(f"<div class='pc-k'>{k}</div><h1>{t}</h1><div class='pc-deck'>{d}</div>",unsafe_allow_html=True)

st.set_page_config(page_title="P&C Sanctions",page_icon="◈",layout="wide",initial_sidebar_state="expanded")
style()
st.sidebar.markdown("<div class='pc-k'>Power & Corridors</div><h2>P&C Sanctions</h2>",unsafe_allow_html=True)
NAV=["Exposure Picture","Regional Dashboard","Entities & Designations","Vessels & Mobile Assets","Ownership & Networks","Activity & Events","Cases & Review","Monitoring","Evidence & Sources","Search"]
page=st.sidebar.radio("Workspace",NAV,label_visibility="collapsed")
if st.sidebar.button("↻ Refresh database",use_container_width=True):
    st.cache_data.clear();st.cache_resource.clear();st.rerun()
designations=rows("pc_sanctions_designations");links=rows("pc_sanctions_links");screening=rows("pc_screening_results")
entities=rows("pc_entities");mobiles=rows("pc_mobile_assets");events=rows("pc_events");event_links=rows("pc_event_links");sources=rows("pc_sources")
hero("P&C SANCTIONS","Sanctions & Exposure Intelligence","Resolve identity, ownership, activity and designation exposure against the canonical P&C graph. Evidence first; screening and analyst decisions remain distinguishable from canonical facts.")
if page in ["Exposure Picture","Regional Dashboard"]:
    region=st.selectbox("Region",list(REGIONS))
    d=region_filter(designations,region);e=region_filter(entities,region);m=region_filter(mobiles,region);ev=region_filter(events,region)
    metrics([("Designations",len(d)),("Entities in view",len(e)),("Mobile assets",len(m)),("Events",len(ev)),("Screening records",len(screening))])
    st.caption("Regional presence is a discovery lens, not itself a sanctions finding.")
    a,b,c,dtab=st.tabs(["Designations","Entities","Vessels / mobile assets","Activity"])
    with a:show(d)
    with b:show(e)
    with c:show(m)
    with dtab:show(ev)
elif page=="Entities & Designations":
    q=st.text_input("Search entity or designation");show(search(designations,q));st.markdown("### Canonical entities");show(search(entities,q))
elif page=="Vessels & Mobile Assets":
    q=st.text_input("Search IMO, MMSI, vessel name, flag or asset");show(search(mobiles,q),540)
elif page=="Ownership & Networks":
    st.markdown("### Ownership, control & association");st.caption("Trace evidence-backed relationships; do not infer beneficial ownership from a name match alone.");show(links,560)
elif page=="Activity & Events":
    q=st.text_input("Search activity, port, vessel, company or location");show(search(events,q),480)
    with st.expander("Canonical event links"):show(search(event_links,q),360)
elif page=="Cases & Review":
    st.markdown("<div class='pc-card'><b>Intake → Resolve → Screen → Network → Activity → Exposure → Evidence → Review → Decision → Monitor</b><br><br>Case decisions remain workspace-specific. Verified identity, ownership and activity facts can be promoted to the shared graph after review.</div>",unsafe_allow_html=True);show(screening,480)
elif page=="Monitoring":show(screening,360);st.markdown("### Recent activity");show(events.head(250),420)
elif page=="Evidence & Sources":show(sources,600)
else:
    q=st.text_input("Search the sanctions workspace")
    if q:
        for title,df in [("Designations",designations),("Links",links),("Entities",entities),("Mobile assets",mobiles),("Events",events)]:
            x=search(df,q)
            if x is not None and not x.empty:st.markdown("### "+title);show(x.head(200),300)
