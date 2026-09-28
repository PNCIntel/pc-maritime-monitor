
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

st.set_page_config(page_title="P&C Strategic Industries",page_icon="◈",layout="wide",initial_sidebar_state="expanded")
style()
st.sidebar.markdown("<div class='pc-k'>Power & Corridors</div><h2>P&C Strategic Industries</h2><div style='color:#aab6c0'>Government, defence & critical industrial capability</div>",unsafe_allow_html=True)
NAV=["Capability Picture","Regional Dashboard","Companies","Government Organisations","Programmes","Contracts","Facilities & Shipyards","Fleets & Assets","Industrial Capacity","Events & Announcements","Evidence & Sources","Search"]
page=st.sidebar.radio("Workspace",NAV,label_visibility="collapsed")
if st.sidebar.button("↻ Refresh database",use_container_width=True):
    st.cache_data.clear();st.cache_resource.clear();st.rerun()
entities=rows("pc_entities");assets=rows("pc_assets");mobiles=rows("pc_mobile_assets");contracts=rows("pc_contracts");orders=rows("pc_shipbuilding_orders");projects=rows("pc_project_details");events=rows("pc_events");sources=rows("pc_sources")
def strategic(df):
    if df.empty:return df
    blob=df.fillna("").astype(str).agg(" ".join,axis=1)
    return df[blob.str.contains(r"defen|defence|military|navy|naval|coast guard|government|shipbuild|aerospace|security|strategic|marine|yard",case=False,regex=True,na=False)].copy()
se=strategic(entities);sa=strategic(assets);sm=strategic(mobiles)
hero("P&C STRATEGIC INDUSTRIES","Strategic Industries & Government Capability","Map the organisations, facilities, programmes, contracts, fleets and assets through which governments and strategic industries build, buy, operate and sustain capability.")
if page in ["Capability Picture","Regional Dashboard"]:
    region=st.selectbox("Region",list(REGIONS))
    re=region_filter(se,region);ra=region_filter(sa,region);rm=region_filter(sm,region);rc=region_filter(contracts,region);ro=region_filter(orders,region);rp=region_filter(projects,region)
    metrics([("Strategic organisations",len(re)),("Facilities / assets",len(ra)),("Fleet / mobile assets",len(rm)),("Contracts",len(rc)),("Orders / programmes",len(ro)+len(rp))])
    tabs=st.tabs(["Organisations","Facilities","Fleets & assets","Programmes & orders","Contracts"])
    with tabs[0]:show(re)
    with tabs[1]:show(ra)
    with tabs[2]:show(rm)
    with tabs[3]:show(pd.concat([ro,rp],ignore_index=True,sort=False) if not ro.empty or not rp.empty else pd.DataFrame())
    with tabs[4]:show(rc)
elif page=="Companies":
    q=st.text_input("Search strategic company");show(search(se,q),560)
elif page=="Government Organisations":
    q=st.text_input("Search ministry, armed force, navy, coast guard or authority");x=search(entities,q)
    if not x.empty:
        blob=x.fillna("").astype(str).agg(" ".join,axis=1);x=x[blob.str.contains(r"government|ministry|navy|naval|coast guard|armed force|authority|command",case=False,regex=True,na=False)]
    show(x,560)
elif page=="Programmes":st.markdown("### Projects & programmes");show(projects,380);st.markdown("### Shipbuilding / platform orders");show(orders,420)
elif page=="Contracts":show(contracts,600)
elif page=="Facilities & Shipyards":
    q=st.text_input("Search facility, shipyard or industrial site");show(search(sa,q),560)
elif page=="Fleets & Assets":
    q=st.text_input("Search vessel, class, fleet, aircraft or mobile asset");show(search(sm,q),560)
elif page=="Industrial Capacity":
    st.markdown("<div class='pc-card'><b>Capacity lens</b><br>Existing → under construction → ordered → planned. Distinguish current capability from future capacity.</div>",unsafe_allow_html=True);show(orders,340);show(projects,340)
elif page=="Events & Announcements":
    q=st.text_input("Search strategic-industry event");x=search(events,q)
    if not x.empty:
        blob=x.fillna("").astype(str).agg(" ".join,axis=1);x=x[blob.str.contains(r"defen|naval|navy|coast guard|shipyard|shipbuild|procurement|contract|military|aerospace|icebreaker|patrol",case=False,regex=True,na=False)]
    show(x,560)
elif page=="Evidence & Sources":show(sources,600)
else:
    q=st.text_input("Search Strategic Industries")
    if q:
        for title,df in [("Organisations",se),("Facilities",sa),("Fleets / assets",sm),("Contracts",contracts),("Projects",projects),("Orders",orders),("Events",events)]:
            x=search(df,q)
            if x is not None and not x.empty:st.markdown("### "+title);show(x.head(200),300)
