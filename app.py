from pathlib import Path
import re
from collections import defaultdict
import pandas as pd
import streamlit as st

APP_TITLE = "P&C Trade System"
APP_VERSION = "v1.27"
DATA_DIR = Path(__file__).parent / "data"

st.set_page_config(page_title=f"{APP_TITLE} {APP_VERSION}", page_icon="◈", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
:root{--bg:#07111f;--panel:#0d1a2b;--panel2:#102238;--border:#28415f;--text:#f3f6fa;--muted:#b8c5d4;--gold:#d7b66a;--blue:#7bc3ef}
.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"]{background:var(--bg);color:var(--text)}
[data-testid="stSidebar"]{background:#091725!important;border-right:1px solid var(--border)}
h1,h2,h3,h4,h5,h6,p,li,span,label{color:var(--text)}
a{color:var(--blue)!important}
.pc-kicker{color:var(--gold);font-size:.76rem;letter-spacing:.14em;text-transform:uppercase;font-weight:700}.pc-title{font-size:2rem;font-weight:800}.pc-sub{color:var(--muted);margin:.2rem 0 1.2rem}.pc-card{background:linear-gradient(180deg,var(--panel),var(--panel2));border:1px solid var(--border);border-radius:12px;padding:14px 16px;margin-bottom:8px}.pc-label{font-size:.72rem;color:var(--muted);text-transform:uppercase;letter-spacing:.08em}.pc-big{font-size:1.3rem;font-weight:750}.pc-small{color:var(--muted);font-size:.88rem}.pc-rel{padding:8px 11px;border-left:3px solid var(--gold);background:var(--panel);margin:6px 0;border-radius:5px}.pc-chip{display:inline-block;border:1px solid var(--border);background:var(--panel);padding:3px 8px;border-radius:999px;font-size:.76rem;color:var(--muted);margin:2px 3px 2px 0}
[data-baseweb="select"]>div,[data-baseweb="input"]>div,.stTextInput input{background:var(--panel)!important;color:var(--text)!important;border-color:var(--border)!important}.stDataFrame{border:1px solid var(--border);border-radius:8px}
</style>
""", unsafe_allow_html=True)

# ---------- workbook loading ----------
WORKBOOKS = {
    "Core Entities": "01_core_entities.xlsx",
    "Maritime": "02_maritime.xlsx",
    "Rail": "03_rail.xlsx",
    "Road & Trucking": "04_road_trucking.xlsx",
    "Aviation": "05_aviation.xlsx",
    "Infrastructure": "06_infrastructure.xlsx",
    "Corporate & Markets": "07_corporate_markets.xlsx",
    "Transactions": "08_transactions.xlsx",
    "Intelligence": "09_intelligence.xlsx",
    "Sources": "10_sources_evidence.xlsx",
    "Systems & Waterways": "11_systems_waterways_governance.xlsx",
    "Defence & Shipbuilding": "12_defence_shipbuilding.xlsx",
}

@st.cache_data(show_spinner=False)
def workbook_sheets(label):
    path = DATA_DIR / WORKBOOKS[label]
    if not path.exists(): return []
    try: return pd.ExcelFile(path).sheet_names
    except Exception: return []

@st.cache_data(show_spinner=False)
def load_sheet(label, sheet):
    path = DATA_DIR / WORKBOOKS[label]
    if not path.exists(): return pd.DataFrame()
    try: return pd.read_excel(path, sheet_name=sheet, dtype=str).fillna("")
    except Exception: return pd.DataFrame()

@st.cache_data(show_spinner=False)
def all_tables():
    out={}
    for wb_label in WORKBOOKS:
        for sheet in workbook_sheets(wb_label):
            df=load_sheet(wb_label,sheet)
            if not df.empty: out[(wb_label,sheet)] = df
    return out

TABLES=all_tables()

ID_RE=re.compile(r"(^|\s)(id|entity id|company id|programme id|program id|yard id|vessel id|facility id|source id|relationship id|contract id|route id|news id|event id)(\s|$)",re.I)

def hide_ids(df, keep_url=True):
    if df is None or df.empty: return pd.DataFrame()
    cols=[]
    for c in df.columns:
        s=str(c)
        if ID_RE.search(s): continue
        if not keep_url and "url" in s.lower(): continue
        cols.append(c)
    return df[cols].copy()

def display_df(df, max_rows=150):
    if df is None or df.empty:
        st.info("No matching records.")
        return
    show=hide_ids(df).head(max_rows)
    cfg={}
    for c in show.columns:
        if "url" in str(c).lower(): cfg[c]=st.column_config.LinkColumn(c,display_text="Open")
    st.dataframe(show,use_container_width=True,hide_index=True,column_config=cfg)

def header(title,sub):
    st.markdown("<div class='pc-kicker'>Power & Corridors Intelligence</div>",unsafe_allow_html=True)
    st.markdown(f"<div class='pc-title'>{title}</div>",unsafe_allow_html=True)
    st.markdown(f"<div class='pc-sub'>{sub}</div>",unsafe_allow_html=True)

# ---------- ID label index ----------
@st.cache_data(show_spinner=False)
def build_label_index():
    idx={}
    candidates=[
        (("Core Entities","Entity Registry"),"Entity ID","Canonical Name"),
        (("Core Entities","Companies"),"Company ID","Company"),
        (("Systems & Waterways","System Entities"),"Entity ID","Entity"),
        (("Defence & Shipbuilding","Defence Companies"),"Entity ID","Entity"),
        (("Defence & Shipbuilding","Shipyards"),"Yard ID","Shipyard"),
        (("Defence & Shipbuilding","Programmes"),"Programme ID","Programme"),
        (("Defence & Shipbuilding","Sample Vessels"),"Vessel ID","Vessel"),
    ]
    for key,idc,namec in candidates:
        df=TABLES.get(key,pd.DataFrame())
        if idc in df.columns and namec in df.columns:
            for _,r in df.iterrows():
                if str(r[idc]).strip(): idx[str(r[idc]).strip()] = str(r[namec]).strip() or str(r[idc])
    return idx
LABELS=build_label_index()

def label(x):
    s=str(x).strip(); return LABELS.get(s,s)

# ---------- global search ----------
SEARCH_PRIORITY={
    "Companies":8,"Entity Registry":7,"Defence Companies":9,"Shipyards":10,"Programmes":10,"Contracts":9,
    "Sales & Delivery Routes":9,"Announcements":9,"News Registry":8,"System Entities":8,"Systems":8,"Facilities":7,
    "Yard Facilities":8,"Yard Capabilities":8,"Sample Vessels":9,"System Links":7,"Relationships":7,
}

@st.cache_data(show_spinner=False)
def search_index():
    rows=[]
    skip={"Data Dictionary","Runtime Table Crosswalk","Research Queue","Overview","Sources","Source Feeds"}
    for (wb_label,sheet),df in TABLES.items():
        if sheet in skip: continue
        for i,r in df.iterrows():
            vals=[str(v).strip() for v in r.tolist() if str(v).strip()]
            if not vals: continue
            txt=" | ".join(vals)
            # best readable title
            preferred=["Company","Entity","Canonical Name","Shipyard","Programme","Vessel","Headline","System","Port / Facility","Asset","Facility","Customer","Contract Type"]
            title=""
            for c in preferred:
                if c in r.index and str(r.get(c,"")).strip(): title=str(r[c]).strip(); break
            if not title: title=vals[0]
            rows.append({"wb":wb_label,"sheet":sheet,"row":int(i),"title":title,"text":txt})
    return pd.DataFrame(rows)
SINDEX=search_index()

def ranked_search(q, limit=80):
    if not q or SINDEX.empty: return pd.DataFrame()
    phrase=q.strip().lower(); tokens=[t for t in re.findall(r"[\w&+.-]+",phrase) if len(t)>1]
    scored=[]
    for _,r in SINDEX.iterrows():
        text=r.text.lower(); title=r.title.lower();
        matched=sum(1 for t in tokens if t in text)
        if matched==0: continue
        score=matched*10 + (30 if phrase in text else 0) + (20 if phrase in title else 0) + SEARCH_PRIORITY.get(r.sheet,3)
        if tokens and all(t in text for t in tokens): score+=20
        scored.append((score,r.wb,r.sheet,r.row,r.title))
    scored.sort(reverse=True,key=lambda x:x[0])
    return pd.DataFrame(scored[:limit],columns=["score","wb","sheet","row","title"])

def result_row(hit):
    return TABLES[(hit.wb,hit.sheet)].iloc[int(hit.row)]

def show_result_detail(hit):
    row=result_row(hit)
    st.markdown(f"### {hit.title}")
    st.caption(f"{hit.wb} · {hit.sheet}")
    pairs=[]
    for c,v in row.items():
        if ID_RE.search(str(c)) or not str(v).strip(): continue
        if "url" in str(c).lower(): continue
        pairs.append((str(c),str(v)))
    for c,v in pairs[:12]: st.markdown(f"**{c}:** {v}")
    urls=[str(v) for c,v in row.items() if "url" in str(c).lower() and str(v).startswith("http")]
    for u in urls[:3]: st.link_button("Open source",u)

# ---------- entity resolver ----------
@st.cache_data(show_spinner=False)
def entity_catalog():
    rows=[]
    specs=[
        (("Core Entities","Companies"),"Company ID","Company","Company"),
        (("Systems & Waterways","System Entities"),"Entity ID","Entity","System Entity"),
        (("Defence & Shipbuilding","Defence Companies"),"Entity ID","Entity","Defence / Shipbuilding"),
        (("Defence & Shipbuilding","Shipyards"),"Yard ID","Shipyard","Shipyard"),
        (("Defence & Shipbuilding","Programmes"),"Programme ID","Programme","Programme"),
    ]
    seen=set()
    for key,idc,namec,kind in specs:
        df=TABLES.get(key,pd.DataFrame())
        if idc not in df.columns or namec not in df.columns: continue
        for _,r in df.iterrows():
            eid=str(r[idc]).strip(); nm=str(r[namec]).strip()
            if eid and nm and eid not in seen:
                rows.append({"id":eid,"name":nm,"kind":kind}); seen.add(eid)
    return pd.DataFrame(rows)
ECAT=entity_catalog()

def related_tables(entity_id, entity_name):
    hits=[]
    needles=[entity_id,entity_name]
    for key,df in TABLES.items():
        if df.empty: continue
        mask=pd.Series(False,index=df.index)
        for needle in needles:
            if not needle: continue
            mask = mask | df.astype(str).apply(lambda s:s.str.contains(re.escape(needle),case=False,na=False)).any(axis=1)
        sub=df[mask]
        if not sub.empty: hits.append((key,sub))
    return hits

# ---------- sidebar ----------
st.sidebar.markdown("### P&C Trade System")
st.sidebar.caption("v1.27 · Global Trade + Defence Industrial Systems")
page=st.sidebar.radio("Navigate",["Search P&C","Entity Explorer","Systems & Corridors","Shipyards & Defence","Intelligence","Data Explorer"])
st.sidebar.markdown("---")
st.sidebar.caption("Tables remain available as evidence, but search and entity/system views are now the primary interface.")

if page=="Search P&C":
    header("Search P&C","Search companies, ports, shipyards, programmes, vessels, contracts, corridors and news without knowing the table structure.")
    q=st.text_input("Search",placeholder="Try: Seaspan US Coast Guard, Inocea icebreakers, Fincantieri UAE, AD Ports Black Sea, Simandou rail port")
    st.caption("Examples: **dual-use shipyards Turkey** · **UAE coast guard Italy** · **Bollinger Rauma Seaspan** · **Badagry APM**")
    if q:
        hits=ranked_search(q)
        if hits.empty: st.warning("No matching records found.")
        else:
            st.markdown(f"#### Best matches ({len(hits)})")
            for n,(_,h) in enumerate(hits.head(20).iterrows()):
                with st.expander(f"{h.title}  ·  {h.sheet}",expanded=(n==0)):
                    show_result_detail(h)

elif page=="Entity Explorer":
    header("Entity Explorer","One profile across corporate structure, assets, shipyards, programmes, vessels, contracts, systems and news.")
    if ECAT.empty:
        st.info("No entity catalog available.")
    else:
        default_id=st.session_state.get("entity_pick","")
        options=ECAT.sort_values(["kind","name"]).to_dict("records")
        labels=[f"{x['name']} — {x['kind']}" for x in options]
        default=0
        for i,x in enumerate(options):
            if x["id"]==default_id: default=i; break
        pick=st.selectbox("Entity",range(len(options)),index=default,format_func=lambda i:labels[i])
        ent=options[pick]; st.session_state["entity_pick"]=ent["id"]
        c1,c2,c3=st.columns(3)
        c1.markdown(f"<div class='pc-card'><div class='pc-label'>Entity</div><div class='pc-big'>{ent['name']}</div></div>",unsafe_allow_html=True)
        c2.markdown(f"<div class='pc-card'><div class='pc-label'>Type</div><div class='pc-big'>{ent['kind']}</div></div>",unsafe_allow_html=True)
        rels=related_tables(ent['id'],ent['name'])
        c3.markdown(f"<div class='pc-card'><div class='pc-label'>Connected tables</div><div class='pc-big'>{len(rels)}</div></div>",unsafe_allow_html=True)
        priority=["Defence Companies","Shipyards","Yard Facilities","Yard Capabilities","Programmes","Programme Participants","Contracts","Sales & Delivery Routes","Sample Vessels","Announcements","News Registry","Relationships","System Links","System Entities","Facilities","Assets"]
        rels.sort(key=lambda x: priority.index(x[0][1]) if x[0][1] in priority else 99)
        for (wb_label,sheet),sub in rels:
            if sheet in {"Sources","Overview"}: continue
            with st.expander(f"{sheet} · {len(sub)} record(s)",expanded=sheet in {"Shipyards","Programmes","Contracts","Announcements","Relationships"}):
                display_df(sub,80)

elif page=="Systems & Corridors":
    header("Systems & Corridors","Explore ports, inland waterways, rail interfaces, governance and lifecycle relationships as connected trade systems.")
    systems=TABLES.get(("Systems & Waterways","Systems"),pd.DataFrame())
    if systems.empty: st.info("Systems workbook not available.")
    else:
        names=systems["System"].tolist(); name=st.selectbox("System",names)
        srow=systems[systems["System"]==name].iloc[0]; sid=srow["System ID"]
        a,b=st.columns(2)
        a.markdown(f"<div class='pc-card'><div class='pc-label'>Geography</div><div class='pc-big'>{srow.get('Geography','')}</div></div>",unsafe_allow_html=True)
        b.markdown(f"<div class='pc-card'><div class='pc-label'>Archetype</div><div class='pc-big'>{srow.get('Archetype','')}</div></div>",unsafe_allow_html=True)
        tabs=st.tabs(["Relationships","Entities","Facilities","Interfaces","Stress Test"])
        keys=["System Links","System Entities","Facilities","Network Interfaces","Stress Tests"]
        for tab,sheet in zip(tabs,keys):
            with tab:
                df=TABLES.get(("Systems & Waterways",sheet),pd.DataFrame())
                if "System ID" in df.columns: df=df[df["System ID"]==sid]
                if sheet=="System Links" and not df.empty:
                    for _,r in df.iterrows():
                        st.markdown(f"<div class='pc-rel'><b>{label(r['Source Entity ID'])}</b> → {str(r['Relationship']).replace('_',' ').title()} → <b>{label(r['Target Entity ID'])}</b></div>",unsafe_allow_html=True)
                else: display_df(df,100)

elif page=="Shipyards & Defence":
    header("Shipyards & Defence","Stress-test defence, coast guard and commercial shipbuilding from company to yard, facilities, programmes, contracts, vessels and sales routes.")
    yards=TABLES.get(("Defence & Shipbuilding","Shipyards"),pd.DataFrame())
    caps=TABLES.get(("Defence & Shipbuilding","Yard Capabilities"),pd.DataFrame())
    if yards.empty: st.info("Defence & shipbuilding workbook not available.")
    else:
        f1,f2,f3=st.columns(3)
        country=f1.selectbox("Country",["All"]+sorted([x for x in yards.get("Country",pd.Series(dtype=str)).unique() if x]))
        comp=f2.selectbox("Company",["All"]+sorted([label(x) for x in yards.get("Company Entity ID",pd.Series(dtype=str)).unique() if x]))
        capopts=["All"]+sorted(caps["Capability"].unique().tolist()) if not caps.empty else ["All"]
        cap=f3.selectbox("Capability",capopts)
        filt=yards.copy()
        if country!="All": filt=filt[filt["Country"]==country]
        if comp!="All":
            ids=[k for k,v in LABELS.items() if v==comp]
            if ids: filt=filt[filt["Company Entity ID"].isin(ids)]
        if cap!="All" and not caps.empty:
            yids=caps[caps["Capability"]==cap]["Yard ID"].tolist(); filt=filt[filt["Yard ID"].isin(yids)]
        st.markdown(f"#### {len(filt)} yard(s)")
        for _,r in filt.iterrows():
            with st.expander(f"{r['Shipyard']} — {r['Country']}"):
                st.markdown(f"**Company:** {label(r['Company Entity ID'])}  ")
                st.markdown(f"**Model:** {r['Yard Model']}  ")
                st.markdown(f"**Representative work:** {r['Current / Representative Work']}  ")
                yid=r['Yard ID']
                ycaps=caps[caps["Yard ID"]==yid] if not caps.empty else pd.DataFrame()
                if not ycaps.empty:
                    chips="".join([f"<span class='pc-chip'>{x}</span>" for x in ycaps['Capability'].tolist()]); st.markdown(chips,unsafe_allow_html=True)
                fac=TABLES.get(("Defence & Shipbuilding","Yard Facilities"),pd.DataFrame())
                if not fac.empty and "Yard ID" in fac.columns:
                    sub=fac[fac["Yard ID"]==yid]
                    if not sub.empty:
                        st.markdown("**Facilities**"); display_df(sub,40)
                if str(r.get("Source URL","")).startswith("http"): st.link_button("Source",r["Source URL"])
        st.markdown("### Programmes & sales routes")
        t1,t2,t3=st.tabs(["Programmes","Contracts","Sales / delivery routes"])
        with t1: display_df(TABLES.get(("Defence & Shipbuilding","Programmes"),pd.DataFrame()),100)
        with t2: display_df(TABLES.get(("Defence & Shipbuilding","Contracts"),pd.DataFrame()),100)
        with t3: display_df(TABLES.get(("Defence & Shipbuilding","Sales & Delivery Routes"),pd.DataFrame()),100)

elif page=="Intelligence":
    header("Intelligence & Announcements","News and announced activity tied back to companies, assets, yards, programmes, contracts and systems.")
    q=st.text_input("Filter news / announcements",placeholder="e.g. icebreaker, UAE, Simandou, Genoa, Badagry")
    blocks=[]
    news=TABLES.get(("Intelligence","News Registry"),pd.DataFrame())
    anns=TABLES.get(("Defence & Shipbuilding","Announcements"),pd.DataFrame())
    for title,df in [("News Registry",news),("Defence & Shipbuilding Announcements",anns)]:
        if q and not df.empty:
            mask=df.astype(str).apply(lambda s:s.str.contains(re.escape(q),case=False,na=False)).any(axis=1); df=df[mask]
        blocks.append((title,df))
    for title,df in blocks:
        st.markdown(f"### {title}"); display_df(df,120)

elif page=="Data Explorer":
    header("Data Explorer","Raw evidence tables remain available for validation and debugging, but are no longer the main navigation model.")
    wb_label=st.selectbox("Workbook",list(WORKBOOKS.keys()))
    sheet=st.selectbox("Sheet",workbook_sheets(wb_label))
    df=load_sheet(wb_label,sheet)
    q=st.text_input("Filter this table")
    if q and not df.empty:
        mask=df.astype(str).apply(lambda s:s.str.contains(re.escape(q),case=False,na=False)).any(axis=1); df=df[mask]
    display_df(df,500)

st.sidebar.markdown("---")
st.sidebar.caption(f"{APP_TITLE} {APP_VERSION} · {len(TABLES):,} loaded tables")
