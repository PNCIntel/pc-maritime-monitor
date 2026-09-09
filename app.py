from pathlib import Path
import re
from collections import defaultdict
import pandas as pd
import streamlit as st

APP_TITLE = "P&C Trade System"
APP_VERSION = "v1.27.2"
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

# ---------- entity / relationship resolver ----------
@st.cache_data(show_spinner=False)
def entity_catalog():
    rows=[]
    specs=[
        (("Core Entities","Companies"),"Company ID","Company","Company"),
        (("Systems & Waterways","System Entities"),"Entity ID","Entity","System Entity"),
        (("Defence & Shipbuilding","Defence Companies"),"Entity ID","Entity","Defence / Shipbuilding"),
        (("Defence & Shipbuilding","Shipyards"),"Yard ID","Shipyard","Shipyard"),
        (("Defence & Shipbuilding","Programmes"),"Programme ID","Programme","Programme"),
        (("Defence & Shipbuilding","Sample Vessels"),"Vessel ID","Vessel","Vessel"),
    ]
    seen=set()
    for key,idc,namec,kind in specs:
        df=TABLES.get(key,pd.DataFrame())
        if idc not in df.columns or namec not in df.columns: continue
        for _,r in df.iterrows():
            eid=str(r.get(idc,"")).strip(); nm=str(r.get(namec,"")).strip()
            if eid and nm and eid not in seen:
                rows.append({"id":eid,"name":nm,"kind":kind}); seen.add(eid)
    return pd.DataFrame(rows)

ECAT=entity_catalog()

def _match_any(df, cols, values):
    if df is None or df.empty: return pd.DataFrame()
    values={str(v).strip() for v in values if str(v).strip()}
    if not values: return df.iloc[0:0].copy()
    mask=pd.Series(False,index=df.index)
    for c in cols:
        if c in df.columns:
            mask = mask | df[c].astype(str).isin(values)
    return df[mask].copy()

def _contains_any(df, values, cols=None):
    if df is None or df.empty: return pd.DataFrame()
    vals=[str(v).strip() for v in values if str(v).strip()]
    if not vals: return df.iloc[0:0].copy()
    use=df if cols is None else df[[c for c in cols if c in df.columns]]
    if use.empty: return df.iloc[0:0].copy()
    mask=pd.Series(False,index=df.index)
    for v in vals:
        mask = mask | use.astype(str).apply(lambda s:s.str.contains(re.escape(v),case=False,na=False)).any(axis=1)
    return df[mask].copy()

def related_tables(entity_id, entity_name):
    hits=[]
    needles=[entity_id,entity_name]
    for key,df in TABLES.items():
        if df.empty: continue
        sub=_contains_any(df,needles)
        if not sub.empty: hits.append((key,sub))
    return hits

def company_scope_ids(entity_id, max_depth=3):
    """Return the selected company plus controlled / owned subsidiaries and JVs.
    This is what makes an Inocea or EDGE profile expose the yards/programmes below it.
    """
    scope={str(entity_id)}
    rel=TABLES.get(("Core Entities","Relationships"),pd.DataFrame())
    if rel.empty: return scope
    ownership_terms=("OWNS","PARENT","CONTROLS","CONTROLLED","SUBSIDIARY","JV_PARTNER","OWNS_51","OWNS_49")
    frontier={str(entity_id)}
    for _ in range(max_depth):
        nxt=set()
        for src in frontier:
            rows=rel[rel.get("Source Entity",pd.Series(dtype=str)).astype(str).eq(src)]
            for _,r in rows.iterrows():
                relationship=str(r.get("Relationship","")).upper()
                tgt=str(r.get("Target Entity","")).strip()
                if tgt and any(term in relationship for term in ownership_terms):
                    if tgt not in scope:
                        scope.add(tgt); nxt.add(tgt)
        if not nxt: break
        frontier=nxt
    return scope

def company_scope_names(scope_ids):
    return [label(x) for x in scope_ids if label(x)!=x]

def company_record(entity_id):
    df=TABLES.get(("Core Entities","Companies"),pd.DataFrame())
    if "Company ID" in df.columns:
        x=df[df["Company ID"].astype(str)==str(entity_id)]
        if not x.empty: return x.iloc[0]
    d=TABLES.get(("Defence & Shipbuilding","Defence Companies"),pd.DataFrame())
    if "Entity ID" in d.columns:
        x=d[d["Entity ID"].astype(str)==str(entity_id)]
        if not x.empty: return x.iloc[0]
    return None

def build_company_profile(entity_id, entity_name):
    prof={}
    prof["company_id"]=entity_id
    prof["name"]=entity_name
    scope_ids=company_scope_ids(entity_id)
    prof["scope_ids"]=scope_ids
    prof["scope_names"]=company_scope_names(scope_ids)

    # Corporate relationships
    rel=TABLES.get(("Core Entities","Relationships"),pd.DataFrame())
    if not rel.empty:
        m=pd.Series(False,index=rel.index)
        if "Source Entity" in rel.columns: m |= rel["Source Entity"].astype(str).isin(scope_ids)
        if "Target Entity" in rel.columns: m |= rel["Target Entity"].astype(str).isin(scope_ids)
        prof["relationships"]=rel[m].copy()
    else: prof["relationships"]=pd.DataFrame()

    # Shipyards owned / operated by this company
    yards=TABLES.get(("Defence & Shipbuilding","Shipyards"),pd.DataFrame())
    prof["yards"]=_match_any(yards,["Company Entity ID"],scope_ids)

    yard_ids=prof["yards"]["Yard ID"].astype(str).tolist() if not prof["yards"].empty and "Yard ID" in prof["yards"].columns else []
    yard_names=prof["yards"]["Shipyard"].astype(str).tolist() if not prof["yards"].empty and "Shipyard" in prof["yards"].columns else []

    # Programmes: direct lead + participant roles
    programmes=TABLES.get(("Defence & Shipbuilding","Programmes"),pd.DataFrame())
    pp=TABLES.get(("Defence & Shipbuilding","Programme Participants"),pd.DataFrame())
    direct=_match_any(programmes,["Prime / Lead Entity ID"],scope_ids)
    participant=_match_any(pp,["Entity ID"],scope_ids)
    pids=set(direct["Programme ID"].astype(str).tolist()) if not direct.empty and "Programme ID" in direct.columns else set()
    if not participant.empty and "Programme ID" in participant.columns: pids.update(participant["Programme ID"].astype(str).tolist())
    prof["programme_participants"]=participant
    prof["programmes"]=programmes[programmes["Programme ID"].astype(str).isin(pids)].copy() if pids and "Programme ID" in programmes.columns else direct
    pids=set(prof["programmes"]["Programme ID"].astype(str).tolist()) if not prof["programmes"].empty else set()

    # Sample defence / government vessels via programme and/or build yard
    sv=TABLES.get(("Defence & Shipbuilding","Sample Vessels"),pd.DataFrame())
    sm=pd.Series(False,index=sv.index) if not sv.empty else pd.Series(dtype=bool)
    if not sv.empty:
        if "Programme ID" in sv.columns and pids: sm |= sv["Programme ID"].astype(str).isin(pids)
        if "Build Yard ID" in sv.columns and yard_ids: sm |= sv["Build Yard ID"].astype(str).isin(yard_ids)
        prof["defence_vessels"]=sv[sm].copy()
    else: prof["defence_vessels"]=pd.DataFrame()

    # Commercial / broader maritime vessels in legacy maritime workbook.
    v=TABLES.get(("Maritime","Vessels"),pd.DataFrame())
    vr=TABLES.get(("Maritime","Vessel Relationships"),pd.DataFrame())
    vm=pd.Series(False,index=v.index) if not v.empty else pd.Series(dtype=bool)
    if not v.empty:
        for c in ["Owner Company ID","Operator Company ID"]:
            if c in v.columns: vm |= v[c].astype(str).isin(scope_ids)
    related_vessel_ids=set()
    if not vr.empty and "Company ID" in vr.columns:
        vrs=vr[vr["Company ID"].astype(str).isin(scope_ids)].copy()
        prof["vessel_relationships"]=vrs
        if "Vessel ID" in vrs.columns: related_vessel_ids.update(vrs["Vessel ID"].astype(str).tolist())
    else: prof["vessel_relationships"]=pd.DataFrame()
    if not v.empty and related_vessel_ids and "Vessel ID" in v.columns: vm |= v["Vessel ID"].astype(str).isin(related_vessel_ids)
    prof["maritime_vessels"]=v[vm].copy() if not v.empty else pd.DataFrame()

    # Vessel build records matching owned yards / sample defence vessels.
    builds=TABLES.get(("Maritime","Vessel Build Records"),pd.DataFrame())
    if not builds.empty:
        bm=pd.Series(False,index=builds.index)
        if "Shipyard" in builds.columns and yard_names:
            for yn in yard_names:
                bm |= builds["Shipyard"].astype(str).str.contains(re.escape(yn),case=False,na=False)
        prof["vessel_build_records"]=builds[bm].copy()
    else: prof["vessel_build_records"]=pd.DataFrame()

    # Contracts / sales routes
    contracts=TABLES.get(("Defence & Shipbuilding","Contracts"),pd.DataFrame())
    cm=pd.Series(False,index=contracts.index) if not contracts.empty else pd.Series(dtype=bool)
    if not contracts.empty:
        if "Contractor Entity ID" in contracts.columns: cm |= contracts["Contractor Entity ID"].astype(str).isin(scope_ids)
        if "Programme ID" in contracts.columns and pids: cm |= contracts["Programme ID"].astype(str).isin(pids)
    prof["contracts"]=contracts[cm].copy() if not contracts.empty else pd.DataFrame()

    routes=TABLES.get(("Defence & Shipbuilding","Sales & Delivery Routes"),pd.DataFrame())
    rm=pd.Series(False,index=routes.index) if not routes.empty else pd.Series(dtype=bool)
    if not routes.empty:
        if "Seller / Builder Entity ID" in routes.columns: rm |= routes["Seller / Builder Entity ID"].astype(str).isin(scope_ids)
        if "Programme ID" in routes.columns and pids: rm |= routes["Programme ID"].astype(str).isin(pids)
    prof["sales_routes"]=routes[rm].copy() if not routes.empty else pd.DataFrame()

    # Yard facilities and capabilities
    fac=TABLES.get(("Defence & Shipbuilding","Yard Facilities"),pd.DataFrame())
    prof["yard_facilities"]=_match_any(fac,["Yard ID"],yard_ids)
    caps=TABLES.get(("Defence & Shipbuilding","Yard Capabilities"),pd.DataFrame())
    prof["yard_capabilities"]=_match_any(caps,["Yard ID"],yard_ids)

    # Infrastructure assets / facilities directly owned by company
    assets=TABLES.get(("Infrastructure","Assets"),pd.DataFrame())
    prof["assets"]=_match_any(assets,["Company ID"],scope_ids)
    infra_fac=TABLES.get(("Infrastructure","Facilities"),pd.DataFrame())
    prof["infrastructure_facilities"]=_match_any(infra_fac,["Owner / Operator Company ID"],scope_ids)

    # Announcements related directly or through programmes
    anns=TABLES.get(("Defence & Shipbuilding","Announcements"),pd.DataFrame())
    am=pd.Series(False,index=anns.index) if not anns.empty else pd.Series(dtype=bool)
    if not anns.empty:
        if "Primary Entity ID" in anns.columns: am |= anns["Primary Entity ID"].astype(str).isin(scope_ids)
        if "Programme ID" in anns.columns and pids: am |= anns["Programme ID"].astype(str).isin(pids)
        if "Linked Entities / Topics" in anns.columns:
            am |= anns["Linked Entities / Topics"].astype(str).str.contains(re.escape(entity_name),case=False,na=False)
    prof["announcements"]=anns[am].copy() if not anns.empty else pd.DataFrame()

    # News via explicit News Entity Links + fallback name match.
    news=TABLES.get(("Intelligence","News Registry"),pd.DataFrame())
    nel=TABLES.get(("Intelligence","News Entity Links"),pd.DataFrame())
    nids=set()
    if not nel.empty and "Entity ID" in nel.columns:
        linkrows=nel[nel["Entity ID"].astype(str).isin(scope_ids)]
        if "News ID" in linkrows.columns: nids.update(linkrows["News ID"].astype(str).tolist())
    nm=pd.Series(False,index=news.index) if not news.empty else pd.Series(dtype=bool)
    if not news.empty:
        if nids and "News ID" in news.columns: nm |= news["News ID"].astype(str).isin(nids)
        for c in ["Headline","Summary","Notes"]:
            if c in news.columns: nm |= news[c].astype(str).str.contains(re.escape(entity_name),case=False,na=False)
    prof["news"]=news[nm].copy() if not news.empty else pd.DataFrame()

    # Systems
    se=TABLES.get(("Systems & Waterways","System Entities"),pd.DataFrame())
    system_ids=set()
    if not se.empty:
        sem=pd.Series(False,index=se.index)
        if "Entity ID" in se.columns: sem |= se["Entity ID"].astype(str).isin(scope_ids)
        if "Entity" in se.columns: sem |= se["Entity"].astype(str).str.contains(re.escape(entity_name),case=False,na=False)
        serows=se[sem]
        if "System ID" in serows.columns: system_ids.update(serows["System ID"].astype(str).tolist())
    systems=TABLES.get(("Systems & Waterways","Systems"),pd.DataFrame())
    prof["systems"]=systems[systems["System ID"].astype(str).isin(system_ids)].copy() if system_ids and "System ID" in systems.columns else pd.DataFrame()

    return prof

def profile_count(prof,key):
    df=prof.get(key,pd.DataFrame())
    return len(df) if isinstance(df,pd.DataFrame) else 0

def readable_relationships(df, entity_id):
    if df is None or df.empty:
        st.info("No relationship records.")
        return
    for _,r in df.iterrows():
        src=str(r.get("Source Entity",""))
        tgt=str(r.get("Target Entity",""))
        rel=str(r.get("Relationship","")).replace("_"," ").title()
        st.markdown(
            f"<div class='pc-rel'><b>{label(src)}</b> → {rel} → <b>{label(tgt)}</b></div>",
            unsafe_allow_html=True
        )

def show_named_list(df, title_col, subtitle_cols=None, source_col="Source URL", max_items=100):
    if df is None or df.empty:
        st.info("No records.")
        return
    subtitle_cols=subtitle_cols or []
    for _,r in df.head(max_items).iterrows():
        title=str(r.get(title_col,"")).strip() or "Record"
        bits=[]
        for c in subtitle_cols:
            v=str(r.get(c,"")).strip()
            if v: bits.append(v)
        sub=" · ".join(bits)
        st.markdown(f"<div class='pc-card'><div class='pc-big'>{title}</div><div class='pc-small'>{sub}</div></div>",unsafe_allow_html=True)
        u=str(r.get(source_col,"")).strip()
        if u.startswith("http"): st.link_button("Source",u,key=f"src_{title_col}_{r.name}_{abs(hash(u))%100000}")

def render_company_profile(entity_id, entity_name):
    prof=build_company_profile(entity_id,entity_name)
    rec=company_record(entity_id)

    # Top summary
    st.markdown(f"## {entity_name}")
    if rec is not None:
        summary=[]
        for c in ["Entity Type","Industrial Model","HQ Country","Country / Geography","Business Segments","Markets","Ownership","Ownership / Role Note","Scale / Network Notes"]:
            if c in rec.index and str(rec.get(c,"")).strip():
                summary.append(f"**{c}:** {rec.get(c)}")
        if summary: st.markdown("  \n".join(summary[:6]))

    if len(prof.get("scope_ids",[]))>1:
        group_names=[x for x in prof.get("scope_names",[]) if x != entity_name]
        if group_names:
            st.markdown("**Included group / controlled entities:** " + " · ".join(group_names))

    c1,c2,c3,c4,c5=st.columns(5)
    c1.metric("Shipyards",profile_count(prof,"yards"))
    total_v=profile_count(prof,"defence_vessels")+profile_count(prof,"maritime_vessels")
    c2.metric("Linked vessels",total_v)
    c3.metric("Programmes",profile_count(prof,"programmes"))
    c4.metric("Contracts",profile_count(prof,"contracts"))
    c5.metric("News / Announcements",profile_count(prof,"news")+profile_count(prof,"announcements"))

    tabs=st.tabs(["Overview","Shipyards & Facilities","Vessels","Programmes & Contracts","Sales Routes","News","Relationships & Systems","Evidence"])
    with tabs[0]:
        if not prof["yards"].empty:
            st.markdown("### Shipyards")
            y=prof["yards"].copy()
            if "Company Entity ID" in y.columns: y["Operating Company"]=y["Company Entity ID"].map(label)
            show_named_list(y,"Shipyard",["Operating Company","Country","Yard Model","Current / Representative Work"])
        if not prof["programmes"].empty:
            st.markdown("### Active / relevant programmes")
            show_named_list(prof["programmes"],"Programme",["Customer","Platform / Class","Status","Build / Sales Route"])
        if prof["yards"].empty and prof["programmes"].empty:
            st.info("No shipyard/programme profile yet for this entity.")

    with tabs[1]:
        st.markdown("### Shipyards")
        y=prof["yards"].copy()
        if "Company Entity ID" in y.columns: y["Operating Company"]=y["Company Entity ID"].map(label)
        show_named_list(y,"Shipyard",["Operating Company","Location","Country","Yard Model","Status"])
        if not prof["yard_capabilities"].empty:
            st.markdown("### Yard capabilities")
            cap=prof["yard_capabilities"].copy()
            if "Yard ID" in cap.columns: cap["Shipyard"]=cap["Yard ID"].map(label)
            display_df(cap,100)
        if not prof["yard_facilities"].empty:
            st.markdown("### Yard facilities")
            fac=prof["yard_facilities"].copy()
            if "Yard ID" in fac.columns: fac["Shipyard"]=fac["Yard ID"].map(label)
            display_df(fac,100)
        if not prof["infrastructure_facilities"].empty:
            st.markdown("### Other infrastructure facilities")
            display_df(prof["infrastructure_facilities"],100)

    with tabs[2]:
        if not prof["defence_vessels"].empty:
            st.markdown("### Defence / Coast Guard / Government vessels")
            dv=prof["defence_vessels"].copy()
            if "Build Yard ID" in dv.columns: dv["Shipyard"]=dv["Build Yard ID"].map(label)
            display_df(dv,150)
        if not prof["maritime_vessels"].empty:
            st.markdown("### Commercial / maritime vessels")
            display_df(prof["maritime_vessels"],250)
        if not prof["vessel_build_records"].empty:
            st.markdown("### Vessel build records tied to these yards")
            display_df(prof["vessel_build_records"],150)
        if prof["defence_vessels"].empty and prof["maritime_vessels"].empty and prof["vessel_build_records"].empty:
            st.info("No vessel records currently linked to this entity. This is now shown explicitly rather than hidden in other tables.")

    with tabs[3]:
        st.markdown("### Programmes")
        pg=prof["programmes"].copy()
        if not pg.empty and "Prime / Lead Entity ID" in pg.columns:
            pg["Prime / Lead"]=pg["Prime / Lead Entity ID"].map(label)
        display_df(pg,150)
        if not prof["programme_participants"].empty:
            st.markdown("### Programme roles")
            display_df(prof["programme_participants"],100)
        st.markdown("### Contracts")
        display_df(prof["contracts"],150)

    with tabs[4]:
        display_df(prof["sales_routes"],150)

    with tabs[5]:
        if not prof["announcements"].empty:
            st.markdown("### Announced activity")
            show_named_list(prof["announcements"],"Headline",["Date","Event Type"])
        if not prof["news"].empty:
            st.markdown("### News")
            show_named_list(prof["news"],"Headline",["Published Date","Publisher","Country","Event Type"],source_col="URL")
        if prof["announcements"].empty and prof["news"].empty:
            st.info("No linked news or announcements.")

    with tabs[6]:
        st.markdown("### Corporate relationships")
        readable_relationships(prof["relationships"],entity_id)
        if not prof["systems"].empty:
            st.markdown("### Trade systems / corridors")
            display_df(prof["systems"],50)

    with tabs[7]:
        if not prof["assets"].empty:
            st.markdown("### Direct assets")
            display_df(prof["assets"],100)
        rels=related_tables(entity_id,entity_name)
        for (wb_label,sheet),sub in rels:
            if sheet in {"Sources","Overview","Companies","Defence Companies","Shipyards","Programmes","Contracts","Sample Vessels","Announcements","News Registry","Relationships"}:
                continue
            with st.expander(f"{sheet} · {len(sub)} record(s)"):
                display_df(sub,100)

def entity_search_matches(q, limit=20):
    if ECAT.empty or not q: return pd.DataFrame()
    tokens=[t.lower() for t in re.findall(r"[\w&+.-]+",q) if len(t)>1]
    scores=[]
    for _,r in ECAT.iterrows():
        text=f"{r['name']} {r['kind']}".lower()
        s=sum(10 for t in tokens if t in text)
        if q.lower() in text: s+=30
        if s: scores.append((s,r["id"],r["name"],r["kind"]))
    scores.sort(reverse=True)
    return pd.DataFrame(scores[:limit],columns=["score","id","name","kind"])

def go_entity(eid):
    st.session_state["entity_pick"]=eid
    st.session_state["nav_page"]="Entity Explorer"

# ---------- sidebar ----------
st.sidebar.markdown("### P&C Trade System")
st.sidebar.caption("v1.27.2 · Group-aware Entity Explorer")
pages=["Search P&C","Entity Explorer","Systems & Corridors","Shipyards & Defence","Intelligence","Data Explorer"]
if "nav_page" not in st.session_state: st.session_state["nav_page"]="Search P&C"
page=st.sidebar.radio("Navigate",pages,key="nav_page")
st.sidebar.markdown("---")
st.sidebar.caption("Search and company/entity profiles are primary. Tables are now the evidence layer.")

if page=="Search P&C":
    header("Search P&C","Search for a company or subject, then open the connected profile instead of hunting through tables.")
    q=st.text_input("Search",placeholder="Try: Seaspan, Inocea, Fincantieri UAE, Bollinger, AD Ports Black Sea, Simandou")
    st.caption("For the clearest results, start with a company/entity name. The profile then exposes yards, vessels, programmes, contracts, routes and news.")
    if q:
        em=entity_search_matches(q)
        if not em.empty:
            st.markdown("### Entities")
            cols=st.columns(2)
            for n,(_,r) in enumerate(em.head(10).iterrows()):
                with cols[n%2]:
                    st.markdown(f"<div class='pc-card'><div class='pc-label'>{r['kind']}</div><div class='pc-big'>{r['name']}</div></div>",unsafe_allow_html=True)
                    st.button("Open full profile",key=f"open_{r['id']}_{n}",on_click=go_entity,args=(r["id"],))
        hits=ranked_search(q,limit=40)
        if not hits.empty:
            st.markdown("### Other matching records")
            # Group matches so a query does not feel like a flat table dump.
            for sheet in ["Programmes","Sample Vessels","Shipyards","Contracts","Sales & Delivery Routes","Announcements","News Registry","Systems","System Entities"]:
                sub=hits[hits["sheet"]==sheet].head(8)
                if sub.empty: continue
                with st.expander(f"{sheet} · {len(sub)} match(es)",expanded=sheet in {"Programmes","Sample Vessels","Shipyards"}):
                    for _,h in sub.iterrows():
                        row=result_row(h)
                        st.markdown(f"**{h.title}**")
                        pairs=[]
                        for c,v in row.items():
                            if ID_RE.search(str(c)) or not str(v).strip() or "url" in str(c).lower(): continue
                            pairs.append(f"{c}: {v}")
                        st.caption(" · ".join(pairs[:5]))
        if em.empty and hits.empty:
            st.warning("No matching records found.")

elif page=="Entity Explorer":
    header("Entity Explorer","A single connected profile: shipyards, facilities, vessels, programmes, contracts, sales routes, news and relationships.")
    if ECAT.empty:
        st.info("No entity catalog available.")
    else:
        search=st.text_input("Find entity",placeholder="Seaspan, Inocea, Bollinger, MAESTRAL, Fincantieri, AD Ports...")
        pool=ECAT.copy()
        if search:
            m=entity_search_matches(search,100)
            if not m.empty: pool=ECAT[ECAT["id"].isin(m["id"].tolist())]
        pool=pool.sort_values(["kind","name"]).reset_index(drop=True)
        default_id=st.session_state.get("entity_pick","")
        opts=pool.to_dict("records")
        if not opts:
            st.warning("No matching entity.")
        else:
            default=0
            for i,x in enumerate(opts):
                if x["id"]==default_id: default=i; break
            pick=st.selectbox("Entity",range(len(opts)),index=default,format_func=lambda i:f"{opts[i]['name']} — {opts[i]['kind']}")
            ent=opts[pick]; st.session_state["entity_pick"]=ent["id"]
            if ent["kind"] in {"Company","Defence / Shipbuilding"} or ent["id"].startswith("COMP_"):
                render_company_profile(ent["id"],ent["name"])
            else:
                st.markdown(f"## {ent['name']}")
                rels=related_tables(ent["id"],ent["name"])
                priority=["Shipyards","Programmes","Sample Vessels","Contracts","Sales & Delivery Routes","Announcements","News Registry","Relationships","System Links","Facilities","Assets"]
                rels.sort(key=lambda x: priority.index(x[0][1]) if x[0][1] in priority else 99)
                for (wb_label,sheet),sub in rels:
                    if sheet in {"Sources","Overview"}: continue
                    with st.expander(f"{sheet} · {len(sub)} record(s)",expanded=sheet in {"Programmes","Sample Vessels","Shipyards","Relationships"}):
                        display_df(sub,150)

elif page=="Systems & Corridors":
    header("Systems & Corridors","Explore ports, waterways, rail interfaces, governance and project lifecycle as connected trade systems.")
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
                else: display_df(df,150)

elif page=="Shipyards & Defence":
    header("Shipyards & Defence","Start with a company and immediately see its yards, vessels, programmes, contracts and delivery routes.")
    dc=TABLES.get(("Defence & Shipbuilding","Defence Companies"),pd.DataFrame())
    if dc.empty:
        st.info("Defence & shipbuilding workbook not available.")
    else:
        names=dc[["Entity ID","Entity"]].drop_duplicates().sort_values("Entity")
        choices=names.to_dict("records")
        pick=st.selectbox("Company / industrial group",range(len(choices)),format_func=lambda i:choices[i]["Entity"])
        ent=choices[pick]
        render_company_profile(ent["Entity ID"],ent["Entity"])

elif page=="Intelligence":
    header("Intelligence & Announcements","News and announced activity tied to companies, assets, shipyards, programmes, vessels and systems.")
    q=st.text_input("Filter",placeholder="e.g. Seaspan, Davie, UAE, icebreaker, Simandou, Genoa")
    news=TABLES.get(("Intelligence","News Registry"),pd.DataFrame())
    anns=TABLES.get(("Defence & Shipbuilding","Announcements"),pd.DataFrame())
    if q:
        news=_contains_any(news,[q]); anns=_contains_any(anns,[q])
    t1,t2=st.tabs([f"News · {len(news)}",f"Announcements · {len(anns)}"])
    with t1: show_named_list(news,"Headline",["Published Date","Publisher","Country","Event Type"],source_col="URL",max_items=150)
    with t2: show_named_list(anns,"Headline",["Date","Event Type"],max_items=150)

elif page=="Data Explorer":
    header("Data Explorer","Raw evidence and debugging tables. Use Search or Entity Explorer for normal analysis.")
    wb_label=st.selectbox("Workbook",list(WORKBOOKS.keys()))
    sheet=st.selectbox("Sheet",workbook_sheets(wb_label))
    df=load_sheet(wb_label,sheet)
    q=st.text_input("Filter this table")
    if q: df=_contains_any(df,[q])
    display_df(df,500)

st.sidebar.markdown("---")
st.sidebar.caption(f"{APP_TITLE} {APP_VERSION} · {len(TABLES):,} loaded tables")
