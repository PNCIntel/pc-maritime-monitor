from pathlib import Path
import re
from collections import defaultdict
import pandas as pd
import streamlit as st

APP_TITLE = "P&C Trade System"
APP_VERSION = "v1.30"
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
.pc-source{margin-top:7px;font-size:.82rem}.pc-source a{color:var(--blue)!important;text-decoration:none;font-weight:650}
.pc-search-card{padding:16px 18px}.pc-search-details{margin-top:8px;line-height:1.65;color:var(--muted);font-size:.92rem}
.pc-object-card{margin-bottom:.35rem;min-height:72px}
.pc-detail-label{color:#d7b66a!important;font-weight:700}.pc-detail-value{color:#f3f6fa!important}.pc-sep{color:#6f849d!important;margin:0 .2rem}
/* top navigation */
div[role="radiogroup"]{gap:.35rem;flex-wrap:wrap}
div[role="radiogroup"] label{background:#0d1a2b;border:1px solid #28415f;border-radius:9px;padding:.35rem .75rem}
div[role="radiogroup"] label:has(input:checked){border-color:#d7b66a;background:#102238}
[data-baseweb="tab-list"]{gap:.25rem}[data-baseweb="tab"]{color:#f3f6fa!important}
[data-baseweb="select"]>div,[data-baseweb="input"]>div,.stTextInput input{background:var(--panel)!important;color:var(--text)!important;border-color:var(--border)!important}
.stDataFrame{border:1px solid var(--border);border-radius:8px}
/* Streamlit popovers, detail boxes, dialogs, expanders and tooltips must remain readable in dark mode */
[data-baseweb="popover"],[data-baseweb="popover"] *,
[data-baseweb="menu"],[data-baseweb="menu"] *,
[data-testid="stPopoverBody"],[data-testid="stPopoverBody"] *,
[data-testid="stDialog"],[data-testid="stDialog"] *,
[data-testid="stExpander"] details,[data-testid="stExpander"] summary,
div[role="dialog"],div[role="dialog"] *{
  color:#101820!important;
}
[data-baseweb="popover"],[data-baseweb="menu"],[data-testid="stPopoverBody"],[data-testid="stDialog"],div[role="dialog"]{
  background:#ffffff!important;
}
[data-baseweb="popover"] a,[data-baseweb="menu"] a,[data-testid="stPopoverBody"] a,div[role="dialog"] a{color:#145a8d!important}
[data-testid="stAlert"] p,[data-testid="stAlert"] span{color:inherit!important}
/* Streamlit Cloud / app chrome */
[data-testid="stHeader"],header[data-testid="stHeader"],[data-testid="stToolbar"],[data-testid="stDecoration"]{
  background:#07111f!important;
  color:#f3f6fa!important;
}
[data-testid="stHeader"] *,[data-testid="stToolbar"] *{
  color:#f3f6fa!important;
}
[data-testid="stHeader"] svg,[data-testid="stToolbar"] svg{
  fill:#f3f6fa!important;
  color:#f3f6fa!important;
}
[data-testid="stAppDeployButton"],[data-testid="stStatusWidget"]{
  background:#0d1a2b!important;
  color:#f3f6fa!important;
}
.stButton > button, .stDownloadButton > button{
  background:#102238!important;
  color:#f3f6fa!important;
  border:1px solid #28415f!important;
}
.stButton > button:hover, .stDownloadButton > button:hover{
  border-color:#d7b66a!important;
  color:#ffffff!important;
}
.stButton > button p, .stDownloadButton > button p{
  color:#f3f6fa!important;
}
/* White BaseWeb/Streamlit detail boxes get dark text */
[data-baseweb="popover"],[data-baseweb="popover"] *,
[data-baseweb="menu"],[data-baseweb="menu"] *,
[data-testid="stPopoverBody"],[data-testid="stPopoverBody"] *,
[data-testid="stDialog"],[data-testid="stDialog"] *,
div[role="dialog"],div[role="dialog"] *,
div[data-baseweb="tooltip"],div[data-baseweb="tooltip"] *{
  color:#101820!important;
}
[data-baseweb="popover"],[data-baseweb="menu"],[data-testid="stPopoverBody"],
[data-testid="stDialog"],div[role="dialog"],div[data-baseweb="tooltip"]{
  background:#ffffff!important;
}
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
    "Events & Hazards": "13_events_hazards.xlsx",
    "Trade Policy & Compliance": "14_trade_policy_compliance.xlsx",
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

ID_RE=re.compile(r"(^|\s)(id|entity id|company id|programme id|program id|yard id|vessel id|facility id|source id|relationship id|contract id|route id|news id|event id|port id|terminal id|asset id|link id|event link id|news link id|location record|status record|chain id|impact id|observation id|canonical event id|external event id|approval id|status history id|control record id)(\s|$)",re.I)

# Internal IDs are required for joins, but never need to be the normal user interface.
ID_FRIENDLY_NAMES={
    "Company ID":"Company","Company Entity ID":"Company","Entity ID":"Entity",
    "Source Entity":"Source","Target Entity":"Target","Source Entity ID":"Source","Target Entity ID":"Target",
    "Programme ID":"Programme","Program ID":"Programme","Yard ID":"Shipyard","Build Yard ID":"Shipyard",
    "Vessel ID":"Vessel","Port ID":"Port","Terminal ID":"Terminal","Parent Entity ID":"Parent Entity",
    "Asset/Facility Entity ID":"Asset / Facility","Asset / Facility Entity ID":"Asset / Facility",
    "Prime / Lead Entity ID":"Prime / Lead","Contractor Entity ID":"Contractor",
    "Seller / Builder Entity ID":"Seller / Builder","Primary Entity ID":"Primary Entity",
    "Owner / Operator Company ID":"Owner / Operator","Primary Operator Company ID":"Primary Operator",
    "Operator Company ID":"Operator","Owner Company ID":"Owner",
}

def _friendly_col_name(c):
    c=str(c)
    if c in ID_FRIENDLY_NAMES: return ID_FRIENDLY_NAMES[c]
    if ID_RE.search(c):
        s=re.sub(r"\bID\b","",c,flags=re.I).strip(" /_-")
        return s or "Entity"
    return c

def humanize_df(df, keep_urls=True, show_internal_ids=False):
    """Resolve internal keys to English names before presentation."""
    if df is None or df.empty: return pd.DataFrame()
    out=pd.DataFrame(index=df.index)
    for c in df.columns:
        cstr=str(c)
        if not keep_urls and "url" in cstr.lower():
            continue
        vals=df[c].copy()

        # Resolve ID-bearing fields into canonical English labels.
        is_id_col=bool(ID_RE.search(cstr) or cstr in ID_FRIENDLY_NAMES)
        if is_id_col:
            friendly=_friendly_col_name(cstr)
            resolved=vals.astype(str).map(label)
            # Suppress raw source/news/etc IDs if they cannot be translated to something human.
            unresolved=resolved.eq(vals.astype(str))
            technical_prefix=vals.astype(str).str.match(r"^(SRC|REL|NEWS|NL|OWN|BERTH|EQ|PRICE|FIN|CON|SALE|ANN|FAC|LNK|CM|INT|GOV|TEST|SYS|PORT|TERM|COMP|DEF|YARD|PROG|VES|ASSET|WATER|RAIL|CORR)_?",case=False,na=False)
            if technical_prefix.all() and unresolved.all() and not show_internal_ids:
                continue
            if friendly in out.columns:
                # avoid duplicate English columns such as Primary Operator ID + Primary Operator
                if out[friendly].astype(str).str.strip().eq("").all():
                    out[friendly]=resolved
                continue
            out[friendly]=resolved
            if show_internal_ids and friendly != cstr:
                out[cstr]=vals
        else:
            # Also translate exact entity-key values that happen to live in non-ID columns.
            def trans(v):
                s=str(v).strip()
                if s in LABELS:
                    return label(s)
                if cstr.lower() in {"relationship","link type","capability","event type","event family","asset type","control type","status","yard model"}:
                    return pretty_relationship(s) if cstr.lower() in {"relationship","link type"} else pretty_enum(s)
                return pretty_enum(s)
            out[cstr]=vals.map(trans)

    # Prefer populated human-readable columns and drop duplicate column names.
    out=out.loc[:,~out.columns.duplicated()].copy()
    return out

def hide_ids(df, keep_url=True):
    return humanize_df(df,keep_urls=keep_url,show_internal_ids=False)

def display_df(df, max_rows=150, show_ids=False):
    if df is None or df.empty:
        st.info("No matching records.")
        return
    show=humanize_df(df,show_internal_ids=show_ids).head(max_rows)
    cfg={}
    for c in show.columns:
        if "url" in str(c).lower():
            cfg[c]=st.column_config.LinkColumn(str(c).replace("URLs","Sources").replace("URL","Source"),display_text="Open")
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
        (("Maritime","Ports"),"Port ID","Port / Facility"),
        (("Maritime","Port Terminals"),"Terminal ID","Terminal / Facility"),
        (("Maritime","Vessels"),"Vessel ID","Vessel Name"),
        (("Infrastructure","Assets"),"Asset ID","Asset"),
        (("Systems & Waterways","Systems"),"System ID","System"),
        (("Events & Hazards","Events"),"Event ID","Title"),
        (("Events & Hazards","Event Asset Links"),"Asset ID","Asset"),
        (("Events & Hazards","Event Company Links"),"Company ID","Company"),
        (("Events & Hazards","Event System Links"),"System ID","System"),
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

def pretty_enum(v):
    """Turn implementation taxonomy into ordinary English for the UI."""
    s=str(v).strip()
    if not s:
        return ""
    # Do not touch URLs or normal prose.
    if s.startswith("http://") or s.startswith("https://"):
        return s
    # Resolve canonical IDs first.
    if s in LABELS:
        return LABELS[s]
    # ALL_CAPS_ENUM / SNAKE_CASE_ENUM -> title-like English.
    if "_" in s and re.fullmatch(r"[A-Z0-9_ /+-]+",s):
        s=s.replace("_"," ").strip()
        # Preserve common acronyms.
        words=[]
        keep={"MRO","JV","UAE","US","USA","UK","EU","IMO","OPV","LNG","TEU","CG","SAR","RFI","RFP"}
        for w in s.split():
            words.append(w if w in keep else w.lower())
        if words:
            words[0]=words[0] if words[0] in keep else words[0].capitalize()
        return " ".join(words)
    return s

def pretty_relationship(v):
    s=pretty_enum(v)
    replacements={
        "Directly affected":"Directly affected",
        "Connected network":"Connected network",
        "Indirect hinterland impact":"Indirect hinterland impact",
        "Affected network":"Affected network",
        "Project milestone":"Project milestone",
        "Connected project":"Connected project",
        "Temporary alternative":"Temporary alternative",
        "Negotiation target":"Negotiation target",
        "Connected gateway":"Connected gateway",
        "Investment target":"Investment target",
        "Infrastructure event":"Infrastructure event",
        "Commercial event":"Commercial event",
        "Commissioning event":"Commissioning event",
        "Regional security context":"Regional security context",
    }
    return replacements.get(s,s)

# ---------- global search ----------
SEARCH_PRIORITY={
    "Companies":8,"Entity Registry":7,"Defence Companies":9,"Shipyards":10,"Programmes":10,"Contracts":9,
    "Sales & Delivery Routes":9,"Announcements":9,"News Registry":8,"System Entities":8,"Systems":8,"Facilities":7,
    "Yard Facilities":8,"Yard Capabilities":8,"Sample Vessels":9,"System Links":7,"Relationships":7,
    "Events":12,"Strategic Events":12,"Event Asset Links":10,"Event Company Links":10,"Event System Links":10,"Impact Chains":11,
    "Trade Agreements":14,"Agreement Asset Links":12,"Agreement Company Links":12,"Tariff Coverage":13,"HS Product Tests":12,
    "Rules of Origin":11,"Customs & Procurement":11,"Trade Remedies & Restrictions":12,"Sanctions Designations":14,"Sanctions Entity Links":13,
    "Infra Deals":10,"Transactions V125":11,"Vessel Transactions":9,"Port Terminals":10,"Port Ownership":9,
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
            if not title:
                title=label(vals[0]) if vals[0] in LABELS else vals[0]
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
    for u in urls[:3]: st.markdown(f"[Open source ↗]({u})")

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

def company_investment_exposure_ids(scope_ids):
    """Return portfolio / investment targets without classifying them as controlled subsidiaries."""
    rel=TABLES.get(("Core Entities","Relationships"),pd.DataFrame())
    if rel.empty:
        return set()
    exposure_terms=("PORTFOLIO_INVESTMENT","MINORITY_INVESTMENT","STRATEGIC_INVESTMENT","CONSORTIUM_ACQUIRED")
    targets=set()
    if "Source Entity" not in rel.columns or "Target Entity" not in rel.columns:
        return targets
    rows=rel[rel["Source Entity"].astype(str).isin(set(str(x) for x in scope_ids))]
    for _,r in rows.iterrows():
        relationship=str(r.get("Relationship","")).upper()
        if any(term in relationship for term in exposure_terms):
            tgt=str(r.get("Target Entity","")).strip()
            if tgt:
                targets.add(tgt)
    return targets

def company_news_scope_ids(scope_ids):
    """Broaden news discovery through meaningful corporate/project relationships
    without changing ownership/control scope.
    Example: Fincantieri Infrastructure → participates in → PerGenova.
    """
    base=set(str(x) for x in scope_ids)
    rel=TABLES.get(("Core Entities","Relationships"),pd.DataFrame())
    if rel.empty or "Source Entity" not in rel.columns or "Target Entity" not in rel.columns:
        return base

    news_terms=(
        "PARTICIPATES_IN","LEADS_CONSORTIUM","JV_PARTICIPANT_IN","PARENT_OF","OWNS",
        "CONTROL","OPERATES","ADMINISTERS","COMMISSIONS","CONSTRUCTS","BUILDS",
        "PORTFOLIO_INVESTMENT","STRATEGIC_INVESTMENT"
    )
    expanded=set(base)
    for _,r in rel.iterrows():
        src=str(r.get("Source Entity","")).strip()
        tgt=str(r.get("Target Entity","")).strip()
        relationship=str(r.get("Relationship","")).upper()
        if not any(term in relationship for term in news_terms):
            continue
        if src in base and tgt:
            expanded.add(tgt)
        if tgt in base and src:
            expanded.add(src)
    return expanded

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
    investment_ids=company_investment_exposure_ids(scope_ids)
    asset_scope_ids=set(scope_ids) | set(investment_ids)

    prof["scope_ids"]=scope_ids
    prof["scope_names"]=company_scope_names(scope_ids)
    prof["investment_ids"]=investment_ids
    prof["investment_names"]=company_scope_names(investment_ids)
    prof["asset_scope_ids"]=asset_scope_ids

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

    # News via explicit links, meaningful related entities, and fallback text match.
    news=TABLES.get(("Intelligence","News Registry"),pd.DataFrame())
    nel=TABLES.get(("Intelligence","News Entity Links"),pd.DataFrame())
    news_scope_ids=company_news_scope_ids(asset_scope_ids)
    prof["news_scope_ids"]=news_scope_ids

    nids=set()
    if not nel.empty and "Entity ID" in nel.columns:
        linkrows=nel[nel["Entity ID"].astype(str).isin(news_scope_ids)]
        if "News ID" in linkrows.columns:
            nids.update(linkrows["News ID"].astype(str).tolist())

    nm=pd.Series(False,index=news.index) if not news.empty else pd.Series(dtype=bool)
    if not news.empty:
        if nids and "News ID" in news.columns:
            nm |= news["News ID"].astype(str).isin(nids)
        # exact company/group names remain a useful fallback for unlinked legacy rows.
        for search_name in set([entity_name] + company_scope_names(news_scope_ids)):
            if not search_name:
                continue
            for c in ["Headline","Summary","Notes"]:
                if c in news.columns:
                    nm |= news[c].astype(str).str.contains(re.escape(search_name),case=False,na=False)
    prof["news"]=news[nm].copy() if not news.empty else pd.DataFrame()

    # Strategic event history can function as news/activity when a company is linked
    # through a vessel or another canonical event entity. This is important for GFS Galaxy.
    strategic=TABLES.get(("Intelligence","Strategic Events"),pd.DataFrame())
    event_links=TABLES.get(("Intelligence","Event Entity Links"),pd.DataFrame())
    observations=TABLES.get(("Intelligence","Event Observations"),pd.DataFrame())

    strategic_ids=set()
    observation_ids=set()

    # Company/group/event scope.
    event_asset_ids=set(news_scope_ids)
    for key,col in [
        ("maritime_vessels","Vessel ID"),
        ("defence_vessels","Vessel ID"),
        ("yards","Yard ID"),
        ("port_terminals","Terminal ID"),
        ("ports","Port ID"),
        ("assets","Asset ID")
    ]:
        df=prof.get(key,pd.DataFrame())
        if isinstance(df,pd.DataFrame) and not df.empty and col in df.columns:
            event_asset_ids.update(df[col].astype(str).tolist())

    if not event_links.empty and "Entity ID" in event_links.columns:
        el=event_links[event_links["Entity ID"].astype(str).isin(event_asset_ids)].copy()
        if "Canonical Event ID" in el.columns:
            strategic_ids.update(x for x in el["Canonical Event ID"].astype(str).tolist() if x and x!="nan")
        if "Observation ID" in el.columns:
            observation_ids.update(x for x in el["Observation ID"].astype(str).tolist() if x and x!="nan")

    # Strategic Events can also directly name a company or asset.
    if not strategic.empty and "Subject Entity ID" in strategic.columns:
        sd=strategic[strategic["Subject Entity ID"].astype(str).isin(event_asset_ids)]
        if "Event ID" in sd.columns:
            strategic_ids.update(sd["Event ID"].astype(str).tolist())

    se_rows=strategic[strategic["Event ID"].astype(str).isin(strategic_ids)].copy() if (strategic_ids and not strategic.empty and "Event ID" in strategic.columns) else pd.DataFrame()

    # Convert strategic events into a news-like dataframe for the normal News tab.
    strategic_news=[]
    for _,r in se_rows.iterrows():
        eid=str(r.get("Event ID","")).strip()
        url=""
        # Prefer a URL-bearing observation for the canonical event.
        if not observations.empty:
            om=pd.Series(False,index=observations.index)
            if "Canonical Event ID" in observations.columns:
                om |= observations["Canonical Event ID"].astype(str).eq(eid)
            if observation_ids and "Observation ID" in observations.columns:
                om |= observations["Observation ID"].astype(str).isin(observation_ids)
            ors=observations[om]
            if not ors.empty and "Source Reference" in ors.columns:
                for v in ors["Source Reference"].astype(str).tolist():
                    if v.startswith("http"):
                        url=v
                        break
        strategic_news.append({
            "Published Date":str(r.get("Date","")).strip(),
            "Headline":str(r.get("Title","")).strip(),
            "Publisher":"Strategic event record",
            "URL":url,
            "Summary":str(r.get("Description","")).strip(),
            "Region":str(r.get("Location","")).strip(),
            "Country":"",
            "Sector":"",
            "Event Type":str(r.get("Event Type","")).strip(),
            "Event Subtype":"",
            "Verification Status":"Canonical event-linked",
            "Notes":str(r.get("Financial / Strategic Impact","")).strip(),
            "Strategic Event ID":eid,
        })
    prof["strategic_news"]=pd.DataFrame(strategic_news)

    # Port / terminal assets from Maritime workbook
    pt=TABLES.get(("Maritime","Port Terminals"),pd.DataFrame())
    po=TABLES.get(("Maritime","Port Ownership"),pd.DataFrame())
    pb=TABLES.get(("Maritime","Port Berths"),pd.DataFrame())
    pe=TABLES.get(("Maritime","Port Equipment"),pd.DataFrame())
    pnews=TABLES.get(("Maritime","Port News"),pd.DataFrame())
    ports=TABLES.get(("Maritime","Ports"),pd.DataFrame())

    # direct terminal operator rows
    tm=pd.Series(False,index=pt.index) if not pt.empty else pd.Series(dtype=bool)
    if not pt.empty:
        if "Primary Operator Company ID" in pt.columns:
            tm |= pt["Primary Operator Company ID"].astype(str).isin(asset_scope_ids)
        if "Operator / Network" in pt.columns:
            for nm in company_scope_names(asset_scope_ids):
                tm |= pt["Operator / Network"].astype(str).str.contains(re.escape(nm),case=False,na=False)
    direct_terms=pt[tm].copy() if not pt.empty else pd.DataFrame()

    # direct port operator/authority rows.
    # Some networks (e.g. Associated British Ports) are modelled at port level rather than terminal level.
    direct_ports=pd.DataFrame()
    if not ports.empty:
        pm=pd.Series(False,index=ports.index)
        if "Operator Company ID" in ports.columns:
            pm |= ports["Operator Company ID"].astype(str).isin(asset_scope_ids)
        if "Operator" in ports.columns:
            for nm in company_scope_names(asset_scope_ids):
                pm |= ports["Operator"].astype(str).str.contains(re.escape(nm),case=False,na=False)
        direct_ports=ports[pm].copy()

    # ownership / JV rows can surface terminals even where primary operator differs
    owned_term_ids=set()
    if not po.empty and "Company ID" in po.columns:
        porows=po[po["Company ID"].astype(str).isin(asset_scope_ids)].copy()
        prof["port_ownership"]=porows
        if "Terminal ID" in porows.columns:
            owned_term_ids.update(porows["Terminal ID"].astype(str).tolist())
    else:
        prof["port_ownership"]=pd.DataFrame()

    term_ids=set()
    if not direct_terms.empty and "Terminal ID" in direct_terms.columns:
        term_ids.update(direct_terms["Terminal ID"].astype(str).tolist())
    term_ids.update(owned_term_ids)

    if not pt.empty and term_ids and "Terminal ID" in pt.columns:
        extra_terms=pt[pt["Terminal ID"].astype(str).isin(term_ids)]
        prof["port_terminals"]=pd.concat([direct_terms,extra_terms],ignore_index=True).drop_duplicates()
    else:
        prof["port_terminals"]=direct_terms

    # parent ports + ports directly administered/operated by the company/network
    port_ids=set()
    if not prof["port_terminals"].empty and "Port ID" in prof["port_terminals"].columns:
        port_ids.update(prof["port_terminals"]["Port ID"].astype(str).tolist())

    terminal_parent_ports=ports[ports["Port ID"].astype(str).isin(port_ids)].copy() if (not ports.empty and port_ids and "Port ID" in ports.columns) else pd.DataFrame()
    port_frames=[x for x in [direct_ports,terminal_parent_ports] if isinstance(x,pd.DataFrame) and not x.empty]
    if port_frames:
        prof["ports"]=pd.concat(port_frames,ignore_index=True).drop_duplicates()
    else:
        prof["ports"]=pd.DataFrame()

    # terminal-level child assets
    prof["port_berths"]=_match_any(pb,["Terminal ID"],term_ids)
    prof["port_equipment"]=_match_any(pe,["Terminal ID"],term_ids)

    # port/terminal news
    pnids=set(term_ids)
    pnm=pd.Series(False,index=pnews.index) if not pnews.empty else pd.Series(dtype=bool)
    if not pnews.empty:
        if "Terminal ID" in pnews.columns and pnids:
            pnm |= pnews["Terminal ID"].astype(str).isin(pnids)
        for nm in company_scope_names(asset_scope_ids):
            for c in ["Headline","Summary","Operator","Port","Terminal"]:
                if c in pnews.columns:
                    pnm |= pnews[c].astype(str).str.contains(re.escape(nm),case=False,na=False)
    prof["port_news"]=pnews[pnm].copy() if not pnews.empty else pd.DataFrame()

    # Systems
    se=TABLES.get(("Systems & Waterways","System Entities"),pd.DataFrame())
    system_ids=set()
    if not se.empty:
        sem=pd.Series(False,index=se.index)
        if "Entity ID" in se.columns: sem |= se["Entity ID"].astype(str).isin(asset_scope_ids)
        if "Entity" in se.columns: sem |= se["Entity"].astype(str).str.contains(re.escape(entity_name),case=False,na=False)
        serows=se[sem]
        if "System ID" in serows.columns: system_ids.update(serows["System ID"].astype(str).tolist())
    systems=TABLES.get(("Systems & Waterways","Systems"),pd.DataFrame())
    prof["systems"]=systems[systems["System ID"].astype(str).isin(system_ids)].copy() if system_ids and "System ID" in systems.columns else pd.DataFrame()

    # Unified events / hazards / project announcements
    event_assets=entity_asset_ids_from_profile(prof)
    ev,eloc,ech=event_bundle_for_entities(asset_scope_ids,event_assets,system_ids)
    prof["events"]=ev
    prof["event_locations"]=eloc
    prof["impact_chains"]=ech

    # Trade policy / sanctions exposure
    acl=TABLES.get(("Trade Policy & Compliance","Agreement Company Links"),pd.DataFrame())
    aal=TABLES.get(("Trade Policy & Compliance","Agreement Asset Links"),pd.DataFrame())
    agr=TABLES.get(("Trade Policy & Compliance","Trade Agreements"),pd.DataFrame())
    san=TABLES.get(("Trade Policy & Compliance","Sanctions Entity Links"),pd.DataFrame())
    des=TABLES.get(("Trade Policy & Compliance","Sanctions Designations"),pd.DataFrame())

    policy_ids=set()
    if not acl.empty and "Company ID" in acl.columns:
        pcl=acl[acl["Company ID"].astype(str).isin(asset_scope_ids)].copy()
        prof["agreement_company_links"]=pcl
        if "Agreement ID" in pcl.columns: policy_ids.update(pcl["Agreement ID"].astype(str))
    else:
        prof["agreement_company_links"]=pd.DataFrame()
    if not aal.empty and "Asset / Entity ID" in aal.columns:
        pal=aal[aal["Asset / Entity ID"].astype(str).isin(event_assets | asset_scope_ids)].copy()
        prof["agreement_asset_links"]=pal
        if "Agreement ID" in pal.columns: policy_ids.update(pal["Agreement ID"].astype(str))
    else:
        prof["agreement_asset_links"]=pd.DataFrame()
    prof["trade_agreements"]=agr[agr["Agreement ID"].astype(str).isin(policy_ids)].copy() if (policy_ids and not agr.empty and "Agreement ID" in agr.columns) else pd.DataFrame()

    sanc_ids=set()
    if not san.empty and "Canonical Entity ID" in san.columns:
        sl=san[san["Canonical Entity ID"].astype(str).isin(event_assets | asset_scope_ids)].copy()
        prof["sanctions_links"]=sl
        if "Designation ID" in sl.columns: sanc_ids.update(sl["Designation ID"].astype(str))
    else:
        prof["sanctions_links"]=pd.DataFrame()
    prof["sanctions_designations"]=des[des["Designation ID"].astype(str).isin(sanc_ids)].copy() if (sanc_ids and not des.empty and "Designation ID" in des.columns) else pd.DataFrame()

    return prof

def profile_count(prof,key):
    df=prof.get(key,pd.DataFrame())
    return len(df) if isinstance(df,pd.DataFrame) else 0

def readable_relationships(df, entity_id):
    if df is None or df.empty:
        st.info("No relationship records.")
        return

    for i,(_,r) in enumerate(df.iterrows()):
        src=str(r.get("Source Entity","")).strip()
        tgt=str(r.get("Target Entity","")).strip()
        rel=pretty_relationship(r.get("Relationship",""))
        src_name=label(src)
        tgt_name=label(tgt)

        st.markdown(
            f"<div class='pc-rel'><b>{src_name}</b> → {rel} → <b>{tgt_name}</b></div>",
            unsafe_allow_html=True
        )

        # Give explicit navigation to every company endpoint except the profile already open.
        nav_cols=[]
        if src.startswith("COMP_") and src != str(entity_id):
            nav_cols.append(("Open "+src_name,src))
        if tgt.startswith("COMP_") and tgt != str(entity_id):
            nav_cols.append(("Open "+tgt_name,tgt))

        if nav_cols:
            cols=st.columns(min(len(nav_cols),3))
            for j,(button_label,target) in enumerate(nav_cols):
                with cols[j]:
                    if st.button(button_label,key=f"relopen_{i}_{target}",use_container_width=True):
                        request_nav("Companies","company_pick_id",target,label(target))
                        st.rerun()

def show_named_list(df, title_col, subtitle_cols=None, source_col="Source URL", max_items=100):
    """Readable cards with normal HTML links, never repeated Streamlit buttons."""
    if df is None or df.empty:
        st.info("No records.")
        return
    subtitle_cols=subtitle_cols or []
    for _,r in df.head(max_items).iterrows():
        title=str(r.get(title_col,"")).strip() or "Record"
        bits=[]
        for c in subtitle_cols:
            v=str(r.get(c,"")).strip()
            if v:
                bits.append(str(label(v)) if v in LABELS else v)
        sub=" · ".join(bits)
        u=str(r.get(source_col,"")).strip()
        source_html=""
        if u.startswith("http"):
            source_html=f"<div class='pc-source'><a href='{u}' target='_blank' rel='noopener noreferrer'>Open source ↗</a></div>"
        st.markdown(
            f"<div class='pc-card'><div class='pc-big'>{title}</div>"
            f"<div class='pc-small'>{sub}</div>{source_html}</div>",
            unsafe_allow_html=True
        )

def _numeric(s):
    return pd.to_numeric(s.astype(str).str.replace(",","",regex=False),errors="coerce")

PORT_CITY_COORDS={
    "Port of Rotterdam":(51.95,4.14),"Rotterdam":(51.95,4.14),
    "Port of Shanghai":(31.2304,121.4737),"Shanghai":(31.2304,121.4737),
    "Port of Genoa":(44.4056,8.9463),"Genoa":(44.4056,8.9463),
    "Port of Constanța":(44.1598,28.6348),"Constanța":(44.1598,28.6348),
    "Port of Odesa":(46.49,30.74),"Odesa":(46.49,30.74),
    "Zayed Port":(24.515,54.375),"Khalifa Port":(24.799,54.651),
    "Port of Poti":(42.15,41.67),"Poti":(42.15,41.67),
    "Port of Batumi":(41.65,41.64),"Batumi":(41.65,41.64),
    "Port of Itaqui":(-2.57,-44.37),"Itaqui":(-2.57,-44.37),
    "Port of Vancouver":(49.29,-123.11),"Vancouver":(49.29,-123.11),
    "Port of Prince Rupert":(54.31,-130.32),"Prince Rupert":(54.31,-130.32),
    "Port of Singapore":(1.264,103.84),"Singapore":(1.264,103.84),
    "Port of Gothenburg":(57.70,11.95),"Gothenburg":(57.70,11.95),
    "Port of Klaipėda":(55.70,21.13),"Klaipėda":(55.70,21.13),
    "Port of Gdańsk":(54.35,18.66),"Gdańsk":(54.35,18.66),
    "Port of South Louisiana":(30.05,-90.55),"Port of New Orleans":(29.95,-90.07),
    "Port of Thunder Bay":(48.38,-89.25),"Port of Duluth-Superior":(46.78,-92.10),
    "Port of Montreal":(45.50,-73.55),"Montréal / Contrecœur":(45.50,-73.55),
    "Port of Kuryk":(43.20,51.65),"Badagry Deep Sea Port":(6.415,2.886),
    "SimFer Morebaya Port":(9.45,-13.55)
}

YARD_CITY_COORDS={
    ("Abu Dhabi","UAE"):(24.4539,54.3773),
    ("Halifax, Nova Scotia","Canada"):(44.6488,-63.5752),
    ("North Vancouver, BC","Canada"):(49.3200,-123.0724),
    ("Victoria, BC","Canada"):(48.4284,-123.3656),
    ("Lévis, Québec","Canada"):(46.8033,-71.1779),
    ("Helsinki","Finland"):(60.1699,24.9384),
    ("Galveston, Texas","USA"):(29.3013,-94.7977),
    ("Port Arthur, Texas","USA"):(29.8849,-93.9399),
    ("Houma, Louisiana","USA"):(29.5958,-90.7195),
    ("Gulfport, Mississippi","USA"):(30.3674,-89.0928),
    ("Pascagoula, Mississippi","USA"):(30.3658,-88.5561),
    ("Rauma","Finland"):(61.1272,21.5113),
    ("Antalya","Turkey"):(36.8969,30.7133),
    ("Tuzla, Istanbul","Turkey"):(40.8167,29.3000),
    ("Altınova, Yalova","Turkey"):(40.6944,29.5097),
    ("La Spezia","Italy"):(44.1025,9.8241),
}

def shipyard_map_data(prof):
    yards=prof.get("yards",pd.DataFrame())
    if yards is None or yards.empty:
        return pd.DataFrame()
    rows=[]
    for _,r in yards.iterrows():
        loc=str(r.get("Location","")).strip()
        country=str(r.get("Country","")).strip()
        shipyard=str(r.get("Shipyard","")).strip()
        xy=YARD_CITY_COORDS.get((loc,country))
        if not xy:
            for (k_loc,k_country),coords in YARD_CITY_COORDS.items():
                if loc and (loc.lower()==k_loc.lower() or loc.lower() in k_loc.lower() or k_loc.lower() in loc.lower()):
                    xy=coords
                    break
        if xy:
            rows.append({"name":shipyard,"location":loc,"country":country,"lat":xy[0],"lon":xy[1]})
    return pd.DataFrame(rows)

def port_map_data(prof):
    """Canonical parent-port coordinates with stress-test fallback locations."""
    ports=prof.get("ports",pd.DataFrame()).copy()
    terms=prof.get("port_terminals",pd.DataFrame()).copy()
    rows=[]
    if not ports.empty:
        for _,r in ports.iterrows():
            nm=str(r.get("Port / Facility","")).strip()
            country=str(r.get("Country","")).strip()
            lat=pd.to_numeric(pd.Series([r.get("Latitude","")]),errors="coerce").iloc[0] if "Latitude" in ports.columns else None
            lon=pd.to_numeric(pd.Series([r.get("Longitude","")]),errors="coerce").iloc[0] if "Longitude" in ports.columns else None
            if pd.isna(lat) or pd.isna(lon):
                xy=PORT_CITY_COORDS.get(nm)
                if xy: lat,lon=xy
            if lat is not None and lon is not None and not pd.isna(lat) and not pd.isna(lon):
                rows.append({"name":nm,"country":country,"lat":float(lat),"lon":float(lon)})
    # fallback from parent-port names where canonical port rows are missing
    if not terms.empty:
        for _,r in terms.iterrows():
            nm=str(r.get("Parent Port","")).strip()
            if not nm: continue
            xy=PORT_CITY_COORDS.get(nm) or PORT_CITY_COORDS.get("Port of "+nm)
            if xy:
                rows.append({"name":nm,"country":str(r.get("Country","")).strip(),"lat":xy[0],"lon":xy[1]})
    if not rows: return pd.DataFrame()
    return pd.DataFrame(rows).drop_duplicates(subset=["name","lat","lon"])

def render_port_visuals(prof):
    terms=prof.get("port_terminals",pd.DataFrame())
    ports=prof.get("ports",pd.DataFrame())
    m=port_map_data(prof)
    if not m.empty:
        st.markdown("### Geographic footprint")
        st.map(m,latitude="lat",longitude="lon",size=70)

    # Direct port portfolios such as ABP should still produce a useful figure.
    if isinstance(ports,pd.DataFrame) and not ports.empty and "Country" in ports.columns:
        pc=ports["Country"].astype(str).replace("",pd.NA).dropna().value_counts().head(15)
        if not pc.empty:
            st.markdown("### Ports by country")
            st.bar_chart(pc,horizontal=True)

    if terms is None or terms.empty:
        return

    # Country footprint
    if "Country" in terms.columns:
        counts=terms["Country"].astype(str).replace("",pd.NA).dropna().value_counts().head(15)
        if not counts.empty:
            st.markdown("### Terminals by country")
            st.bar_chart(counts,horizontal=True)

    # Capacity where populated
    if "Container Capacity TEU/yr" in terms.columns:
        cap=terms[["Terminal / Facility","Container Capacity TEU/yr"]].copy()
        cap["Container Capacity TEU/yr"]=_numeric(cap["Container Capacity TEU/yr"])
        cap=cap.dropna().sort_values("Container Capacity TEU/yr",ascending=False).head(15)
        if not cap.empty:
            st.markdown("### Largest seeded terminal capacities")
            st.bar_chart(cap.set_index("Terminal / Facility")["Container Capacity TEU/yr"],horizontal=True)

def render_shipyard_visuals(prof):
    yards=prof.get("yards",pd.DataFrame())
    caps=prof.get("yard_capabilities",pd.DataFrame())
    sm=shipyard_map_data(prof)
    if not sm.empty:
        st.markdown("### Shipyard footprint")
        st.map(sm,latitude="lat",longitude="lon",size=85)
    if yards is not None and not yards.empty and "Country" in yards.columns:
        yc=yards["Country"].astype(str).replace("",pd.NA).dropna().value_counts()
        if not yc.empty:
            st.markdown("### Shipyards by country")
            st.bar_chart(yc,horizontal=True)
    if caps is not None and not caps.empty and "Capability" in caps.columns:
        cc=caps["Capability"].astype(str).replace("",pd.NA).dropna().value_counts().head(15)
        if not cc.empty:
            st.markdown("### Seeded yard capabilities")
            st.bar_chart(cc,horizontal=True)

def render_market_visuals(entity_id):
    prices=TABLES.get(("Corporate & Markets","Company Market Prices"),pd.DataFrame())
    if prices.empty or "Company ID" not in prices.columns:
        return
    scope=company_scope_ids(entity_id)
    p=prices[prices["Company ID"].astype(str).isin(scope)].copy()
    if p.empty or "Month End" not in p.columns or "Close" not in p.columns:
        return
    p["Date"]=pd.to_datetime(p["Month End"],errors="coerce")
    p["Close Numeric"]=_numeric(p["Close"])
    p=p.dropna(subset=["Date","Close Numeric"]).sort_values("Date")
    if len(p)>=3:
        st.markdown("### Market price")
        st.line_chart(p.set_index("Date")["Close Numeric"])


def event_bundle_for_entities(entity_ids=None, asset_ids=None, system_ids=None):
    entity_ids=set(str(x) for x in (entity_ids or []) if str(x))
    asset_ids=set(str(x) for x in (asset_ids or []) if str(x))
    system_ids=set(str(x) for x in (system_ids or []) if str(x))
    events=TABLES.get(("Events & Hazards","Events"),pd.DataFrame())
    ecl=TABLES.get(("Events & Hazards","Event Company Links"),pd.DataFrame())
    eal=TABLES.get(("Events & Hazards","Event Asset Links"),pd.DataFrame())
    esl=TABLES.get(("Events & Hazards","Event System Links"),pd.DataFrame())
    loc=TABLES.get(("Events & Hazards","Event Locations"),pd.DataFrame())
    chains=TABLES.get(("Events & Hazards","Impact Chains"),pd.DataFrame())
    ids=set()
    if entity_ids and not ecl.empty and "Company ID" in ecl.columns:
        x=ecl[ecl["Company ID"].astype(str).isin(entity_ids)]
        if "Event ID" in x.columns: ids.update(x["Event ID"].astype(str))
    if asset_ids and not eal.empty and "Asset ID" in eal.columns:
        x=eal[eal["Asset ID"].astype(str).isin(asset_ids)]
        if "Event ID" in x.columns: ids.update(x["Event ID"].astype(str))
    if system_ids and not esl.empty and "System ID" in esl.columns:
        x=esl[esl["System ID"].astype(str).isin(system_ids)]
        if "Event ID" in x.columns: ids.update(x["Event ID"].astype(str))
    ev=events[events["Event ID"].astype(str).isin(ids)].copy() if ids and not events.empty else pd.DataFrame()
    eloc=loc[loc["Event ID"].astype(str).isin(ids)].copy() if ids and not loc.empty else pd.DataFrame()
    ech=chains[chains["Event ID"].astype(str).isin(ids)].copy() if ids and not chains.empty else pd.DataFrame()
    return ev,eloc,ech

def render_event_map(events, locations, title="Event map"):
    if locations is None or locations.empty:
        st.info("No mapped event locations in this stress-test set.")
        return
    mp=locations.copy()
    mp["lat"]=_numeric(mp["Latitude"]); mp["lon"]=_numeric(mp["Longitude"])
    mp=mp.dropna(subset=["lat","lon"])
    if mp.empty:
        st.info("No mapped event locations.")
        return
    st.markdown(f"### {title}")
    st.map(mp,latitude="lat",longitude="lon",size=90)
    if events is not None and not events.empty and "Event Family" in events.columns:
        fam=events["Event Family"].astype(str).replace("",pd.NA).dropna().value_counts()
        if not fam.empty:
            st.markdown("### Event mix")
            st.bar_chart(fam,horizontal=True)

def render_event_cards(events,max_items=40):
    if events is None or events.empty:
        st.info("No linked events.")
        return
    e=events.copy()
    if "Start Date" in e.columns:
        e["_dt"]=pd.to_datetime(e["Start Date"],errors="coerce")
        e=e.sort_values("_dt",ascending=False)
    show_named_list(e,"Title",["Start Date","Event Family","Event Type","Severity","Status","Location"],source_col="Primary Source URL",max_items=max_items)

def entity_asset_ids_from_profile(prof):
    ids=set()
    for key,col in [
        ("port_terminals","Terminal ID"),("ports","Port ID"),("yards","Yard ID"),
        ("assets","Asset ID"),("defence_vessels","Vessel ID"),("maritime_vessels","Vessel ID")
    ]:
        df=prof.get(key,pd.DataFrame())
        if isinstance(df,pd.DataFrame) and not df.empty and col in df.columns:
            ids.update(df[col].astype(str).tolist())
    return ids

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

    investment_names=[x for x in prof.get("investment_names",[]) if x and x != entity_name]
    if investment_names:
        st.markdown("**Portfolio / investment exposure:** " + " · ".join(investment_names))

    c1,c2,c3,c4,c5,c6,c7=st.columns(7)
    c1.metric("Terminals",profile_count(prof,"port_terminals"))
    c2.metric("Ports",profile_count(prof,"ports"))
    c3.metric("Shipyards",profile_count(prof,"yards"))
    total_v=profile_count(prof,"defence_vessels")+profile_count(prof,"maritime_vessels")
    c4.metric("Linked vessels",total_v)
    c5.metric("Programmes",profile_count(prof,"programmes"))
    c6.metric("Events",profile_count(prof,"events"))
    c7.metric("News",profile_count(prof,"news")+profile_count(prof,"announcements")+profile_count(prof,"port_news")+profile_count(prof,"strategic_news"))

    tabs=st.tabs(["Overview","Port Assets","Shipyards & Facilities","Vessels","Programmes & Contracts","Sales Routes","Events & Impact","News","Relationships & Systems","Policy & Compliance","Evidence"])
    with tabs[0]:
        # Visual intelligence first
        if not prof["port_terminals"].empty or not prof["ports"].empty:
            render_port_visuals(prof)
        if not prof["yards"].empty:
            render_shipyard_visuals(prof)
        render_market_visuals(entity_id)
        if not prof["events"].empty:
            render_event_map(prof["events"],prof["event_locations"],"Linked events & announced activity")

        if not prof["ports"].empty:
            st.markdown("### Ports")
            show_named_list(prof["ports"],"Port / Facility",["Country","Operator","Facility Type","Key Role"])

        if not prof["port_terminals"].empty:
            st.markdown("### Port terminals / facilities")
            t=prof["port_terminals"].copy()
            show_named_list(t,"Terminal / Facility",["Parent Port","Country","City / Area","Primary Operator","Status","Ownership / Structure"])
        if not prof["yards"].empty:
            st.markdown("### Shipyards")
            y=prof["yards"].copy()
            if "Company Entity ID" in y.columns: y["Operating Company"]=y["Company Entity ID"].map(label)
            show_named_list(y,"Shipyard",["Operating Company","Country","Yard Model","Current / Representative Work"])
        if not prof["programmes"].empty:
            st.markdown("### Active / relevant programmes")
            show_named_list(prof["programmes"],"Programme",["Customer","Platform / Class","Status","Build / Sales Route"])

        # A profile should never hide relevant linked reporting merely because the
        # company is connected through a vessel, consortium or project entity.
        latest_frames=[]
        if not prof["news"].empty:
            x=prof["news"].copy()
            x["_source_kind"]="News"
            latest_frames.append(x)
        if not prof["strategic_news"].empty:
            x=prof["strategic_news"].copy()
            x["_source_kind"]="Strategic event"
            latest_frames.append(x)
        if latest_frames:
            latest=pd.concat(latest_frames,ignore_index=True,sort=False)
            date_col="Published Date" if "Published Date" in latest.columns else None
            if date_col:
                latest["_dt"]=pd.to_datetime(latest[date_col],errors="coerce")
                latest=latest.sort_values("_dt",ascending=False)
            st.markdown("### Latest linked reporting")
            show_named_list(latest.head(5),"Headline",["Published Date","Publisher","Event Type"],source_col="URL",max_items=5)

        if prof["port_terminals"].empty and prof["ports"].empty and prof["yards"].empty and prof["programmes"].empty:
            st.info("No mapped asset, shipyard or programme profile yet for this entity.")

    with tabs[1]:
        st.markdown("### Terminals / port facilities")
        if not prof["port_terminals"].empty:
            t=prof["port_terminals"].copy()
            display_df(t,250)
        else:
            st.info("No terminal assets currently linked.")
        if not prof["ports"].empty:
            st.markdown("### Parent ports")
            display_df(prof["ports"],150)
        if not prof["port_ownership"].empty:
            st.markdown("### Ownership / JV / operating-control relationships")
            display_df(prof["port_ownership"],250)
        if not prof["port_berths"].empty:
            st.markdown("### Berths / marine interfaces")
            display_df(prof["port_berths"],250)
        if not prof["port_equipment"].empty:
            st.markdown("### Terminal equipment")
            display_df(prof["port_equipment"],300)

    with tabs[2]:
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

    with tabs[3]:
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

    with tabs[4]:
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

    with tabs[5]:
        display_df(prof["sales_routes"],150)

    with tabs[6]:
        render_event_map(prof["events"],prof["event_locations"],"Event / activity map")
        st.markdown("### Linked events")
        render_event_cards(prof["events"],50)
        if not prof["impact_chains"].empty:
            st.markdown("### Impact propagation")
            display_df(prof["impact_chains"],100)

        if not prof["events"].empty:
            event_ids=set(prof["events"]["Event ID"].astype(str).tolist())
            eal=TABLES.get(("Events & Hazards","Event Asset Links"),pd.DataFrame())
            if not eal.empty and "Event ID" in eal.columns:
                eal=eal[eal["Event ID"].astype(str).isin(event_ids)]
                if not eal.empty:
                    st.markdown("### Affected / connected assets")
                    render_linked_objects(eal,"Asset Type","Asset ID","Asset","Relationship","Confidence",100)

    with tabs[7]:
        if not prof["announcements"].empty:
            st.markdown("### Announced activity")
            show_named_list(prof["announcements"],"Headline",["Date","Event Type"])
        if not prof["news"].empty:
            st.markdown("### News")
            show_named_list(prof["news"],"Headline",["Published Date","Publisher","Country","Event Type"],source_col="URL")
        if not prof["port_news"].empty:
            st.markdown("### Port / terminal news")
            show_named_list(prof["port_news"],"Headline",["Date","Port","Terminal","Event Type"],source_col="URL")
        if not prof["strategic_news"].empty:
            st.markdown("### Strategic event / incident coverage")
            show_named_list(
                prof["strategic_news"],
                "Headline",
                ["Published Date","Publisher","Event Type","Region"],
                source_col="URL",
                max_items=100
            )
        if prof["announcements"].empty and prof["news"].empty and prof["port_news"].empty and prof["strategic_news"].empty:
            st.info("No linked news, announcements or canonical event coverage.")

    with tabs[8]:
        st.markdown("### Corporate relationships")
        readable_relationships(prof["relationships"],entity_id)
        if not prof["systems"].empty:
            st.markdown("### Trade systems / corridors")
            display_df(prof["systems"],50)

    with tabs[9]:
        if not prof["trade_agreements"].empty:
            st.markdown("### Trade agreements / market-access exposure")
            display_df(prof["trade_agreements"],100)
        if not prof["agreement_company_links"].empty:
            st.markdown("### Company exposure")
            display_df(prof["agreement_company_links"],100)
        if not prof["agreement_asset_links"].empty:
            st.markdown("### Asset / corridor exposure")
            display_df(prof["agreement_asset_links"],100)
        if not prof["sanctions_links"].empty:
            st.markdown("### Sanctions / designation-linked exposure")
            st.caption("A linked company may be an owner, operator or manager named in a designation record; this does not automatically mean every linked party is itself separately designated.")
            display_df(prof["sanctions_links"],100)
        if not prof["sanctions_designations"].empty:
            st.markdown("### Related government designation records")
            display_df(humanize_sanctions_df(prof["sanctions_designations"]),100)
        if prof["trade_agreements"].empty and prof["sanctions_designations"].empty and prof["sanctions_links"].empty:
            st.info("No direct trade-policy or sanctions link has been mapped for this entity yet.")

    with tabs[10]:
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


def _is_technical_value(v):
    s=str(v).strip()
    if not s:
        return True
    return bool(re.match(r"^(TXN|IDEAL|COMP|SRC|NEWS|REL|PROG|YARD|VESSEL|PORT|TERM|ASSET|EVENT|EVT|OBS|ELINK|NLINK|TALINK|APPROVAL|TXNST|VTX|CTRL)[_-]", s, re.I))

def _pretty_field_name(c):
    c=str(c)
    replacements={
        "Buyer Company":"Buyer",
        "Buyer Company ID":"Buyer",
        "Seller / Owner IDs":"Seller / Owner",
        "Investor / Buyer IDs":"Investor / Buyer",
        "Co-Investor / Partner IDs":"Co-Investor / Partner",
        "Target Company":"Target",
        "Target / Asset":"Target / Asset",
        "Announcement Date":"Announced",
        "Announced Date":"Announced",
        "Expected Close":"Expected close",
        "Actual Close":"Closed",
        "Completed / Effective Date":"Completed / effective",
        "Transaction Type":"Type",
        "Deal Type":"Type",
        "Enterprise Value":"Value",
        "Reported Value":"Value",
        "Regulatory Status":"Regulatory status",
        "Operating Control":"Operating control",
    }
    return replacements.get(c,c)

def _split_and_resolve_ids(v):
    """Resolve semicolon-delimited company/entity IDs into English labels."""
    s=str(v).strip()
    if not s: return ""
    parts=[x.strip() for x in re.split(r"[;|]",s) if x.strip()]
    if len(parts)>1:
        resolved=[label(x) if label(x)!=x else x for x in parts]
        return " · ".join(resolved)
    return label(s) if label(s)!=s else s

def readable_search_card(hit):
    row=result_row(hit)
    sheet=str(hit.sheet)

    # Select a human title by record type instead of falling back to the row ID.
    preferred_by_sheet={
        "Transactions V125":["Target Company","Transaction Type"],
        "Infra Deals":["Target / Asset","Deal Type"],
        "Contracts":["Contract Type","Programme","Customer"],
        "Sales & Delivery Routes":["Platform / Vessel","Programme","Customer"],
        "Vessel Transactions":["Vessel Name","Transaction Type"],
        "Events":["Title"],
        "News Registry":["Headline"],
        "Announcements":["Headline"],
        "Port Terminals":["Terminal / Facility"],
        "Ports":["Port / Facility"],
        "Shipyards":["Shipyard"],
        "Sample Vessels":["Vessel"],
        "Vessels":["Vessel Name"],
        "Systems":["System"],
    }
    title=""
    for c in preferred_by_sheet.get(sheet,[]):
        if c in row.index and str(row.get(c,"")).strip() and not _is_technical_value(row.get(c,"")):
            title=str(row.get(c)).strip()
            break
    if not title:
        title=label(str(hit.title)) if label(str(hit.title))!=str(hit.title) else str(hit.title)
    if _is_technical_value(title):
        # Last fallback: use first readable non-ID textual value.
        for c,v in row.items():
            if ID_RE.search(str(c)) or "url" in str(c).lower():
                continue
            sv=str(v).strip()
            if sv and not _is_technical_value(sv):
                title=sv
                break

    # Commercial-specific title enhancement.
    if sheet=="Transactions V125":
        buyer=_split_and_resolve_ids(row.get("Buyer Company ID",""))
        target=str(row.get("Target Company","")).strip()
        ttype=str(row.get("Transaction Type","")).strip()
        if buyer and target:
            title=f"{buyer} → {target}"
        elif target:
            title=target
        if ttype:
            subtitle=ttype
        else:
            subtitle="Corporate transaction"
    elif sheet=="Infra Deals":
        inv=_split_and_resolve_ids(row.get("Investor / Buyer IDs",""))
        target=str(row.get("Target / Asset","")).strip()
        dtype=str(row.get("Deal Type","")).strip()
        title=f"{inv} → {target}" if inv and target else (target or inv or title)
        subtitle=dtype or "Infrastructure deal"
    else:
        subtitle=sheet

    # Build concise, fully readable fields.
    pairs=[]
    priority=[
        "Buyer Company ID","Investor / Buyer IDs","Co-Investor / Partner IDs",
        "Seller / Owner IDs","Target Company","Target / Asset",
        "Transaction Type","Deal Type","Announcement Date","Announced Date",
        "Expected Close","Completed / Effective Date","Enterprise Value","Reported Value",
        "Currency","Stake %","Status","Regulatory Status","Operating Control",
        "Country / Region","Country","Customer","Contract Value","Contract Currency",
        "Programme","Platform / Vessel","Start Date","Event Family","Event Type",
        "Severity","Location"
    ]
    seen=set()
    for c in priority + list(row.index):
        if c in seen or c not in row.index:
            continue
        seen.add(c)
        if "url" in str(c).lower() or c in {"Transaction ID","Deal ID","Contract ID","Source ID","Event ID","News ID"}:
            continue
        v=str(row.get(c,"")).strip()
        if not v:
            continue
        if ID_RE.search(str(c)) or " IDs" in str(c):
            v=_split_and_resolve_ids(v)
            if not v or _is_technical_value(v):
                continue
        elif _is_technical_value(v):
            # raw implementation key in a non-ID field: omit
            continue
        fname=_pretty_field_name(c)
        if fname in {"Target"} and v==title:
            continue
        pairs.append((fname,v))
        if len(pairs)>=6:
            break

    # Clean HTML card; no markdown ** markers inside raw HTML.
    details="".join(
        f"<span class='pc-detail-label'>{c}:</span> <span class='pc-detail-value'>{v}</span>"
        + (" <span class='pc-sep'>·</span> " if i < len(pairs)-1 else "")
        for i,(c,v) in enumerate(pairs)
    )

    url=""
    for c,v in row.items():
        if "url" in str(c).lower() and str(v).strip().startswith("http"):
            url=str(v).strip().split("|")[0].strip()
            break
    source_html=f"<div class='pc-source'><a href='{url}' target='_blank' rel='noopener noreferrer'>Open source ↗</a></div>" if url else ""

    st.markdown(
        f"<div class='pc-card pc-search-card'>"
        f"<div class='pc-label'>{subtitle}</div>"
        f"<div class='pc-big'>{title}</div>"
        f"<div class='pc-search-details'>{details}</div>"
        f"{source_html}</div>",
        unsafe_allow_html=True
    )


def request_nav(page_name, object_key=None, object_id=None, object_name=None):
    """Defer a page/object jump until the next Streamlit rerun.
    Destination pages consume *_pick_id requests before their selector widget is created.
    """
    st.session_state["nav_request"]=page_name
    if object_key and object_id:
        # Never write directly into a selector widget key here.
        # Store the requested canonical object ID separately.
        st.session_state[object_key]=str(object_id)
    if object_name:
        st.session_state["object_name_hint"]=str(object_name)

def object_route(entity_type, entity_id, entity_name):
    et=str(entity_type).lower()
    eid=str(entity_id).strip()
    name=str(entity_name).strip()

    if "port" in et or eid.startswith("PORT"):
        return ("Ports","port_pick_id",eid)
    if "terminal" in et or eid.startswith("TERM"):
        # A terminal opens the Ports page; Ports will resolve its parent port.
        return ("Ports","terminal_pick_id",eid)
    if "shipyard" in et or eid.startswith("YARD"):
        return ("Shipyards","yard_pick_id",eid)
    if "company" in et or eid.startswith("COMP"):
        return ("Companies","company_pick_id",eid)
    if "system" in et or eid.startswith("SYS") or eid.startswith("CORR"):
        return ("Systems","system_pick_id",eid)
    if "vessel" in et or eid.startswith("VESSEL") or eid.startswith("VES"):
        return ("Vessels","vessel_pick_id",eid)
    return (None,None,None)

def render_linked_objects(df, object_type_col, object_id_col, object_name_col, relationship_col=None, confidence_col=None, max_items=100):
    """Render linked graph objects as readable, navigable cards instead of dead dataframe rows."""
    if df is None or df.empty:
        st.info("No linked objects.")
        return

    for i,(_,r) in enumerate(df.head(max_items).iterrows()):
        otype=str(r.get(object_type_col,"")).strip()
        oid=str(r.get(object_id_col,"")).strip()
        oname=str(r.get(object_name_col,"")).strip() or label(oid)
        rel=pretty_relationship(r.get(relationship_col,"")) if relationship_col else ""
        conf=str(r.get(confidence_col,"")).strip() if confidence_col else ""

        route_page,route_key,route_id=object_route(otype,oid,oname)
        meta=[x for x in [pretty_enum(otype),rel,(f"Confidence: {conf}" if conf else "")] if x]

        c1,c2=st.columns([5,1])
        with c1:
            st.markdown(
                f"<div class='pc-card pc-object-card'>"
                f"<div class='pc-label'>{' · '.join(meta)}</div>"
                f"<div class='pc-big'>{oname}</div>"
                f"</div>",
                unsafe_allow_html=True
            )
        with c2:
            if route_page:
                if st.button("Open",key=f"objopen_{route_page}_{oid}_{i}",use_container_width=True):
                    request_nav(route_page,route_key,route_id,oname)
                    st.rerun()
            else:
                st.caption("Linked object")

def safe_index_state(key, default_index, option_count):
    """Normalize stale Streamlit widget state from older app versions.
    Selectbox index widgets must always contain an int in range.
    """
    try:
        current=st.session_state.get(key,default_index)
        current=int(current)
    except (TypeError,ValueError):
        current=int(default_index)

    if current < 0 or current >= int(option_count):
        current=int(default_index)

    st.session_state[key]=current
    return current


def vessel_profile_data(vessel_id, vessel_name):
    commercial=TABLES.get(("Maritime","Vessels"),pd.DataFrame())
    vrel=TABLES.get(("Maritime","Vessel Relationships"),pd.DataFrame())
    evid=TABLES.get(("Maritime","Vessel Evidence"),pd.DataFrame())
    build=TABLES.get(("Maritime","Vessel Build Records"),pd.DataFrame())
    news=TABLES.get(("Intelligence","News Registry"),pd.DataFrame())
    nlinks=TABLES.get(("Intelligence","News Entity Links"),pd.DataFrame())
    events=TABLES.get(("Intelligence","Strategic Events"),pd.DataFrame())
    sanctions=TABLES.get(("Trade Policy & Compliance","Sanctions Designations"),pd.DataFrame())

    row=commercial[commercial["Vessel ID"].astype(str).eq(str(vessel_id))].copy() if not commercial.empty and "Vessel ID" in commercial.columns else pd.DataFrame()
    rel=vrel[vrel["Vessel ID"].astype(str).eq(str(vessel_id))].copy() if not vrel.empty and "Vessel ID" in vrel.columns else pd.DataFrame()
    evd=evid[evid["Vessel ID"].astype(str).eq(str(vessel_id))].copy() if not evid.empty and "Vessel ID" in evid.columns else pd.DataFrame()
    bld=build[build["Vessel ID"].astype(str).eq(str(vessel_id))].copy() if not build.empty and "Vessel ID" in build.columns else pd.DataFrame()

    nids=set()
    if not nlinks.empty and "Entity ID" in nlinks.columns:
        nl=nlinks[nlinks["Entity ID"].astype(str).eq(str(vessel_id))]
        if "News ID" in nl.columns: nids.update(nl["News ID"].astype(str).tolist())
    n=news[news["News ID"].astype(str).isin(nids)].copy() if nids and not news.empty and "News ID" in news.columns else pd.DataFrame()

    ev=events[events["Subject Entity ID"].astype(str).eq(str(vessel_id))].copy() if not events.empty and "Subject Entity ID" in events.columns else pd.DataFrame()

    san=sanctions[sanctions["Canonical Entity ID"].astype(str).eq(str(vessel_id))].copy() if not sanctions.empty and "Canonical Entity ID" in sanctions.columns else pd.DataFrame()

    return row,rel,evd,bld,n,ev,san

def render_vessel_profile(vessel_id,vessel_name):
    row,rel,evd,bld,news,events,san=vessel_profile_data(vessel_id,vessel_name)
    if row.empty:
        st.info("No canonical commercial-vessel record available.")
        return
    r=row.iloc[0]
    st.markdown(f"## {vessel_name}")
    meta=[]
    for c in ["IMO","Vessel Type","Subtype / Class","Flag","Year Built","DWT","Gross Tonnage (GT)","Status","Primary Service"]:
        v=str(r.get(c,"")).strip()
        if v and v.lower()!="nan":
            meta.append(f"**{c}:** {pretty_enum(v)}")
    if meta: st.markdown("  \n".join(meta))

    c1,c2,c3,c4=st.columns(4)
    c1.metric("Sanctions",len(san))
    c2.metric("News",len(news))
    c3.metric("Events",len(events))
    c4.metric("Relationships",len(rel))

    tabs=st.tabs(["Overview","Ownership & Management","Sanctions & Compliance","News & Events","Evidence"])

    with tabs[0]:
        display_df(row,20)
        if not bld.empty:
            st.markdown("### Build record")
            display_df(bld,20)

    with tabs[1]:
        if rel.empty:
            st.info("No linked owner/operator/manager records.")
        else:
            for i,(_,rr) in enumerate(rel.iterrows()):
                cid=str(rr.get("Company ID","")).strip()
                cname=label(cid)
                relationship=pretty_relationship(rr.get("Relationship Type",""))
                c1,c2=st.columns([5,1])
                with c1:
                    st.markdown(
                        f"<div class='pc-rel'><b>{vessel_name}</b> → {relationship} → <b>{cname}</b></div>",
                        unsafe_allow_html=True
                    )
                with c2:
                    if cid.startswith("COMP_") and st.button(f"Open {cname}",key=f"vrel_{vessel_id}_{i}",use_container_width=True):
                        request_nav("Companies","company_pick_id",cid,cname)
                        st.rerun()

    with tabs[2]:
        if san.empty:
            st.info("No government sanctions designation linked to this canonical vessel.")
        else:
            display_df(humanize_sanctions_df(san),100)

    with tabs[3]:
        if not news.empty:
            st.markdown("### Related reporting")
            show_named_list(news,"Headline",["Published Date","Publisher","Event Type","Event Subtype"],source_col="URL",max_items=50)
        if not events.empty:
            st.markdown("### Strategic events")
            display_df(events,50)
        if news.empty and events.empty:
            st.info("No linked news or strategic events.")

    with tabs[4]:
        if not evd.empty:
            display_df(evd,100)
        else:
            st.info("No evidence records.")

# ---------- top navigation ----------
st.sidebar.markdown("### P&C Trade System")
st.sidebar.caption("v1.30 · Canonical sanctions vessel integration")
st.sidebar.markdown("**Normal use:** work from the top navigation. Internal tables remain under Data.")
st.sidebar.markdown("---")

pages=["Search","Companies","Ports","Shipyards","Vessels","Contracts","Trade Policy","Sanctions","News & Events","Systems","Data"]

# Navigation requests are applied BEFORE the top-nav widget is instantiated.
# This avoids StreamlitWidgetAlreadyInstantiatedError when a button changes pages.
if "nav_request" in st.session_state:
    requested=st.session_state.pop("nav_request")
    if requested in pages:
        st.session_state["top_nav"]=requested

if "top_nav" not in st.session_state or st.session_state["top_nav"] not in pages:
    st.session_state["top_nav"]="Search"

page=st.radio("Navigation",pages,horizontal=True,label_visibility="collapsed",key="top_nav")

# Old Streamlit sessions can retain widget values from previous app versions.
# Numeric selectors are normalized again on their destination page.

def page_company_selector():
    companies=TABLES.get(("Core Entities","Companies"),pd.DataFrame())
    if companies.empty: return None,None
    opts=companies[["Company ID","Company"]].drop_duplicates().sort_values("Company").to_dict("records")
    q=st.text_input("Find company",placeholder="APM Terminals, AD Ports, Inocea, Seaspan, Fincantieri, EDGE...")
    if q:
        opts=[x for x in opts if q.lower() in str(x["Company"]).lower()]
    if not opts:
        st.warning("No matching company.")
        return None,None
    pick=st.selectbox("Company",range(len(opts)),format_func=lambda i:opts[i]["Company"])
    return opts[pick]["Company ID"],opts[pick]["Company"]

if page=="Search":
    header("Search P&C","One query across companies, ports, shipyards, vessels, contracts, transactions, news, events and systems.")
    q=st.text_input("Query",placeholder="Try: APM Africa terminals, Seaspan US Coast Guard, AD Ports Black Sea, Rotterdam strike, Fincantieri UAE contracts")
    if q:
        em=entity_search_matches(q,20)
        if not em.empty:
            st.markdown("### Best entity matches")
            cols=st.columns(3)
            for n,(_,r) in enumerate(em.head(9).iterrows()):
                with cols[n%3]:
                    st.markdown(f"<div class='pc-card'><div class='pc-label'>{r['kind']}</div><div class='pc-big'>{r['name']}</div></div>",unsafe_allow_html=True)
                    if st.button("Open",key=f"topopen_{r['id']}_{n}"):
                        st.session_state["company_pick_id"]=r["id"]
                        st.session_state["nav_request"]="Companies"
                        st.rerun()

        hits=ranked_search(q,limit=100)
        if not hits.empty:
            groups=[
                ("Commercial / contracts",["Contracts","Infra Deals","Transactions V125","Sales & Delivery Routes","Vessel Transactions"]),
                ("Assets",["Port Terminals","Ports","Shipyards","Yard Facilities","Sample Vessels","Vessels","Assets"]),
                ("Trade policy & compliance",["Trade Agreements","Tariff Coverage","HS Product Tests","Rules of Origin","Customs & Procurement","Trade Remedies & Restrictions","Sanctions Designations"]),
                ("News & events",["Events","Strategic Events","Announcements","News Registry","Impact Chains"]),
                ("Systems & relationships",["Systems","System Entities","System Links","Relationships","Port Ownership"]),
            ]
            for title,sheets in groups:
                sub=hits[hits["sheet"].isin(sheets)].head(20)
                if sub.empty: continue
                st.markdown(f"### {title}")
                for _,h in sub.iterrows():
                    readable_search_card(h)
        if em.empty and hits.empty:
            st.warning("No matching records found.")

elif page=="Companies":
    header("Companies","Company-first view across assets, ports, shipyards, vessels, commercial relationships, programmes and events.")
    # honor direct navigation from Search
    companies=TABLES.get(("Core Entities","Companies"),pd.DataFrame())
    opts=companies[["Company ID","Company"]].drop_duplicates().sort_values("Company").to_dict("records") if not companies.empty else []

    # A cross-object jump should not be blocked by a stale search filter.
    requested_company=st.session_state.pop("company_pick_id",None)
    if requested_company:
        st.session_state["company_search_text"]=""

    q=st.text_input(
        "Find company",
        placeholder="APM Terminals, AD Ports, Inocea, Seaspan...",
        key="company_search_text"
    )
    if q:
        opts=[x for x in opts if q.lower() in x["Company"].lower()]

    if opts:
        requested_index=None
        if requested_company:
            for i,x in enumerate(opts):
                if x["Company ID"]==str(requested_company):
                    requested_index=i
                    break

        # Also honor prior selected canonical company if still available.
        prior_id=st.session_state.get("entity_pick","")
        prior_index=None
        if prior_id:
            for i,x in enumerate(opts):
                if x["Company ID"]==prior_id:
                    prior_index=i
                    break

        desired_index = requested_index if requested_index is not None else (prior_index if prior_index is not None else 0)

        # Critical: apply selection BEFORE keyed selectbox creation.
        if requested_index is not None:
            st.session_state["company_select_idx"]=int(desired_index)
        else:
            safe_index_state("company_select_idx",int(desired_index),len(opts))

        pick=st.selectbox(
            "Company",
            range(len(opts)),
            format_func=lambda i:opts[i]["Company"],
            key="company_select_idx"
        )
        ent=opts[pick]
        st.session_state["entity_pick"]=ent["Company ID"]
        render_company_profile(ent["Company ID"],ent["Company"])

elif page=="Ports":
    header("Ports","Port / terminal explorer with operators, facilities, geography and linked events.")
    ports=TABLES.get(("Maritime","Ports"),pd.DataFrame())
    terms=TABLES.get(("Maritime","Port Terminals"),pd.DataFrame())
    if ports.empty:
        st.info("Port data unavailable.")
    else:
        requested_port=st.session_state.pop("port_pick_id",None)
        if requested_port:
            st.session_state["port_search_text"]=""
        q=st.text_input("Find port",placeholder="Rotterdam, Shanghai, Odesa, Vancouver, Constanța...",key="port_search_text")
        p=ports.copy()

        requested_terminal=st.session_state.pop("terminal_pick_id",None)
        if requested_terminal:
            st.session_state["port_search_text"]=""
        if requested_terminal and not terms.empty and "Terminal ID" in terms.columns:
            tr=terms[terms["Terminal ID"].astype(str).eq(str(requested_terminal))]
            if not tr.empty and "Port ID" in tr.columns:
                requested_port=str(tr.iloc[0]["Port ID"])

        if q: p=_contains_any(p,[q],["Port / Facility","Country","Operator"])
        p=p.sort_values("Port / Facility").reset_index(drop=True)
        if p.empty:
            st.warning("No matching port.")
        else:
            default_port=0
            if requested_port and "Port ID" in p.columns:
                match_idx=p.index[p["Port ID"].astype(str).eq(str(requested_port))].tolist()
                if match_idx: default_port=int(match_idx[0])

            if requested_port:
                st.session_state["port_select_idx"]=int(default_port)
            else:
                safe_index_state("port_select_idx",int(default_port),len(p))

            pick=st.selectbox(
                "Port",
                range(len(p)),
                format_func=lambda i:f"{p.iloc[i].get('Port / Facility','')} — {p.iloc[i].get('Country','')}",
                key="port_select_idx"
            )
            row=p.iloc[pick]; pid=str(row.get("Port ID","")); pname=str(row.get("Port / Facility",""))
            st.markdown(f"## {pname}")
            c1,c2,c3=st.columns(3)
            pt=terms[terms["Port ID"].astype(str).eq(pid)].copy() if not terms.empty and "Port ID" in terms.columns else pd.DataFrame()
            c1.metric("Terminals",len(pt))
            c2.markdown(f"<div class='pc-card'><div class='pc-label'>Country</div><div class='pc-big'>{row.get('Country','')}</div></div>",unsafe_allow_html=True)
            c3.markdown(f"<div class='pc-card'><div class='pc-label'>Operator</div><div class='pc-big'>{row.get('Operator','') or 'Multiple / authority-led'}</div></div>",unsafe_allow_html=True)
            xy=PORT_CITY_COORDS.get(pname)
            if xy:
                st.map(pd.DataFrame([{"name":pname,"lat":xy[0],"lon":xy[1]}]),latitude="lat",longitude="lon",size=100)
            ev,loc,chains=event_bundle_for_entities(asset_ids=[pid])
            if not ev.empty:
                render_event_map(ev,loc,"Events affecting this port")
            tabs=st.tabs(["Terminals","Events & Impact","Evidence"])
            with tabs[0]: display_df(pt,300)
            with tabs[1]:
                render_event_cards(ev,50)
                if not chains.empty: display_df(chains,100)
            with tabs[2]: display_df(pd.DataFrame([row]),20)

elif page=="Shipyards":
    header("Shipyards","Physical shipyard assets: ownership, capabilities, facilities, programmes, vessels and events.")
    yards=TABLES.get(("Defence & Shipbuilding","Shipyards"),pd.DataFrame())
    if yards.empty:
        st.info("Shipyard data unavailable.")
    else:
        requested_yard=st.session_state.pop("yard_pick_id",None)
        if requested_yard:
            st.session_state["yard_search_text"]=""
        q=st.text_input("Find shipyard / country / company",placeholder="Lévis, Rauma, Antalya, Bollinger, Inocea...",key="yard_search_text")
        y=yards.copy()
        if q: y=_contains_any(y,[q],["Shipyard","Location","Country","Yard Model","Current / Representative Work"])
        y=y.sort_values("Shipyard").reset_index(drop=True)
        default_yard=0
        if requested_yard and "Yard ID" in y.columns:
            mi=y.index[y["Yard ID"].astype(str).eq(str(requested_yard))].tolist()
            if mi: default_yard=int(mi[0])

        if requested_yard:
            st.session_state["yard_select_idx"]=int(default_yard)
        else:
            safe_index_state("yard_select_idx",int(default_yard),len(y))

        pick=st.selectbox(
            "Shipyard",
            range(len(y)),
            format_func=lambda i:f"{y.iloc[i]['Shipyard']} — {y.iloc[i]['Country']}",
            key="yard_select_idx"
        )
        r=y.iloc[pick]; yid=str(r["Yard ID"]); cid=str(r["Company Entity ID"])
        st.markdown(f"## {r['Shipyard']}")
        st.caption(f"{label(cid)} · {r.get('Location','')} · {r.get('Yard Model','')}")
        sm=shipyard_map_data({"yards":pd.DataFrame([r])})
        if not sm.empty: st.map(sm,latitude="lat",longitude="lon",size=100)
        fac=TABLES.get(("Defence & Shipbuilding","Yard Facilities"),pd.DataFrame())
        caps=TABLES.get(("Defence & Shipbuilding","Yard Capabilities"),pd.DataFrame())
        vessels=TABLES.get(("Defence & Shipbuilding","Sample Vessels"),pd.DataFrame())
        yf=_match_any(fac,["Yard ID"],[yid]); yc=_match_any(caps,["Yard ID"],[yid]); yv=_match_any(vessels,["Build Yard ID"],[yid])
        ev,loc,chains=event_bundle_for_entities([cid],[yid],[])
        tabs=st.tabs(["Facilities","Capabilities","Vessels","Events","Evidence"])
        with tabs[0]: display_df(yf,150)
        with tabs[1]: display_df(yc,150)
        with tabs[2]: display_df(yv,150)
        with tabs[3]:
            render_event_map(ev,loc,"Shipyard-linked events")
            render_event_cards(ev,50)
        with tabs[4]: display_df(pd.DataFrame([r]),20)

elif page=="Vessels":
    header("Vessels","Commercial, defence and Coast Guard vessels with ownership, sanctions, incidents and reporting linked to the same canonical object.")
    commercial=TABLES.get(("Maritime","Vessels"),pd.DataFrame()).copy()
    defence=TABLES.get(("Defence & Shipbuilding","Sample Vessels"),pd.DataFrame()).copy()

    requested_vessel=st.session_state.pop("vessel_pick_id",None)
    if requested_vessel:
        st.session_state["vessel_search_text"]=label(requested_vessel)

    q=st.text_input(
        "Find vessel / IMO / owner / customer / class",
        placeholder="LADY MARIIA, SUN, 9220641, Polar Max, CMA CGM...",
        key="vessel_search_text"
    )

    c=commercial.copy()
    if q: c=_contains_any(c,[q])
    c=c.reset_index(drop=True)

    if not c.empty:
        requested_index=0
        if requested_vessel and "Vessel ID" in c.columns:
            mi=c.index[c["Vessel ID"].astype(str).eq(str(requested_vessel))].tolist()
            if mi: requested_index=int(mi[0])

        if "vessel_select_idx" not in st.session_state:
            st.session_state["vessel_select_idx"]=requested_index
        else:
            try:
                vi=int(st.session_state["vessel_select_idx"])
            except Exception:
                vi=requested_index
            if vi<0 or vi>=len(c): vi=requested_index
            st.session_state["vessel_select_idx"]=vi
        if requested_vessel:
            st.session_state["vessel_select_idx"]=requested_index

        pick=st.selectbox(
            "Commercial vessel",
            range(len(c)),
            format_func=lambda i:f"{c.iloc[i].get('Vessel Name','')} — IMO {c.iloc[i].get('IMO','')}",
            key="vessel_select_idx"
        )
        vr=c.iloc[pick]
        render_vessel_profile(str(vr.get("Vessel ID","")),str(vr.get("Vessel Name","")))
    else:
        st.info("No matching canonical commercial vessel.")

    with st.expander(f"Defence / Government vessel catalogue · {len(defence)}"):
        d=defence
        if q: d=_contains_any(d,[q])
        display_df(d,250)

elif page=="Contracts":
    header("Contracts & Commercial","Government procurement, commercial transactions, infrastructure deals, vessel sales and delivery routes.")
    q=st.text_input("Filter",placeholder="AD Ports, UAE, Coast Guard, CLI, port terminals, icebreakers...")
    defence=TABLES.get(("Defence & Shipbuilding","Contracts"),pd.DataFrame())
    tx=TABLES.get(("Transactions","Transactions V125"),pd.DataFrame())
    deals=TABLES.get(("Transactions","Infra Deals"),pd.DataFrame())
    routes=TABLES.get(("Defence & Shipbuilding","Sales & Delivery Routes"),pd.DataFrame())
    if q:
        defence=_contains_any(defence,[q]); tx=_contains_any(tx,[q]); deals=_contains_any(deals,[q]); routes=_contains_any(routes,[q])
    # simple commercial composition figure
    counts=pd.Series({"Defence / government":len(defence),"Corporate transactions":len(tx),"Infrastructure deals":len(deals),"Sales / delivery routes":len(routes)})
    st.bar_chart(counts,horizontal=True)
    t1,t2,t3,t4=st.tabs([f"Defence / Government · {len(defence)}",f"Transactions · {len(tx)}",f"Infrastructure Deals · {len(deals)}",f"Sales / Delivery · {len(routes)}"])
    with t1: display_df(defence,250)
    with t2: display_df(tx,250)
    with t3: display_df(deals,250)
    with t4: display_df(routes,250)

elif page=="Trade Policy":
    header("Trade Policy & Market Access","CEPAs, FTAs, customs unions, tariffs, rules of origin, procurement and trade remedies tied back to P&C assets and companies.")
    agreements=TABLES.get(("Trade Policy & Compliance","Trade Agreements"),pd.DataFrame()).copy()
    if agreements.empty:
        st.info("Trade-policy workbook not available.")
    else:
        q=st.text_input("Find agreement / country / corridor",placeholder="Georgia, Azerbaijan, Congo, DRC, Türkiye, Middle Corridor...")
        statuses=sorted([x for x in agreements["Status"].astype(str).unique().tolist() if x.strip()]) if "Status" in agreements.columns else []
        status_sel=st.multiselect("Status",statuses,default=[])
        a=agreements.copy()
        if q: a=_contains_any(a,[q])
        if status_sel: a=a[a["Status"].isin(status_sel)]

        c1,c2=st.columns(2)
        with c1:
            if not a.empty and "Status" in a.columns:
                st.markdown("### Agreements by status")
                st.bar_chart(a["Status"].value_counts(),horizontal=True)
        with c2:
            if not a.empty and "Agreement Type" in a.columns:
                st.markdown("### Agreement types")
                st.bar_chart(a["Agreement Type"].value_counts(),horizontal=True)

        opts=a.sort_values("Agreement").reset_index(drop=True)
        if opts.empty:
            st.warning("No matching agreements.")
        else:
            pick=st.selectbox("Agreement",range(len(opts)),format_func=lambda i:f"{opts.iloc[i]['Agreement']} — {opts.iloc[i]['Status']}")
            r=opts.iloc[pick]; aid=str(r["Agreement ID"])
            st.markdown(f"## {r['Agreement']}")
            st.caption(f"{r.get('Status','')} · {r.get('Strategic Geography','')}")
            st.markdown(f"**Tariff coverage:** {r.get('Tariff Coverage Summary','')}  ")
            st.markdown(f"**P&C relevance:** {r.get('P&C Relevance','')}")
            src=str(r.get("Source URL","")).strip()
            if src.startswith("http"): st.markdown(f"[Open official / primary source ↗]({src})")

            aal=TABLES.get(("Trade Policy & Compliance","Agreement Asset Links"),pd.DataFrame())
            acl=TABLES.get(("Trade Policy & Compliance","Agreement Company Links"),pd.DataFrame())
            tc=TABLES.get(("Trade Policy & Compliance","Tariff Coverage"),pd.DataFrame())
            hs=TABLES.get(("Trade Policy & Compliance","HS Product Tests"),pd.DataFrame())
            roo=TABLES.get(("Trade Policy & Compliance","Rules of Origin"),pd.DataFrame())
            cp=TABLES.get(("Trade Policy & Compliance","Customs & Procurement"),pd.DataFrame())
            tr=TABLES.get(("Trade Policy & Compliance","Trade Remedies & Restrictions"),pd.DataFrame())
            filt=lambda df: df[df["Agreement ID"].astype(str).eq(aid)].copy() if (not df.empty and "Agreement ID" in df.columns) else pd.DataFrame()
            tabs=st.tabs(["Linked Assets","Companies","Tariffs / HS Tests","Origin & Customs","Remedies / Restrictions"])
            with tabs[0]: display_df(filt(aal),200)
            with tabs[1]: display_df(filt(acl),200)
            with tabs[2]:
                display_df(filt(tc),100)
                display_df(filt(hs),150)
            with tabs[3]:
                display_df(filt(roo),100)
                display_df(filt(cp),100)
            with tabs[4]:
                # include global interaction rules as well
                x=filt(tr)
                global_rows=tr[tr.get("Agreement ID / Scope",pd.Series(dtype=str)).astype(str).eq("GLOBAL_RULE")].copy() if not tr.empty else pd.DataFrame()
                display_df(pd.concat([x,global_rows],ignore_index=True) if not global_rows.empty else x,100)

elif page=="Sanctions":
    header(
        "Sanctions & Compliance",
        "Government sanctions, programmes and designations. Government sanctions remain separate from analytical and operational watchlists."
    )
    des=TABLES.get(("Trade Policy & Compliance","Sanctions Designations"),pd.DataFrame()).copy()
    auth=TABLES.get(("Trade Policy & Compliance","Sanctions Authorities"),pd.DataFrame()).copy()
    progs=TABLES.get(("Trade Policy & Compliance","Sanctions Programmes"),pd.DataFrame()).copy()
    links=TABLES.get(("Trade Policy & Compliance","Sanctions Entity Links"),pd.DataFrame()).copy()
    watch=TABLES.get(("Trade Policy & Compliance","Watchlist Taxonomy"),pd.DataFrame()).copy()
    rules=TABLES.get(("Trade Policy & Compliance","Policy Interaction Rules"),pd.DataFrame()).copy()

    if des.empty:
        st.info("Sanctions data unavailable.")
    else:
        q=st.text_input(
            "Find vessel / company / IMO / authority / programme",
            placeholder="LADY MARIIA, SUN, 9220641, OFAC, Iran, Russia..."
        )

        # Search raw data so IDs/names/programmes all remain discoverable,
        # but never expose implementation IDs in the normal presentation.
        d=des.copy()
        l=links.copy()
        if q:
            d=_contains_any(d,[q])
            l=_contains_any(l,[q])

            # If the query matches an entity-link record, include its designation.
            if not l.empty and "Designation ID" in l.columns and "Designation ID" in des.columns:
                linked_ids=set(l["Designation ID"].astype(str))
                extra=des[des["Designation ID"].astype(str).isin(linked_ids)]
                d=pd.concat([d,extra],ignore_index=True).drop_duplicates()

            # If the query matches a designation, include its entity link.
            if not d.empty and "Designation ID" in d.columns and "Designation ID" in links.columns:
                dids=set(d["Designation ID"].astype(str))
                extra_links=links[links["Designation ID"].astype(str).isin(dids)]
                l=pd.concat([l,extra_links],ignore_index=True).drop_duplicates()

        # Compact headline metrics.
        m1,m2,m3,m4=st.columns(4)
        m1.metric("Designations",len(d))
        m2.metric("Vessels",int((d.get("Target Type",pd.Series(dtype=str)).astype(str).str.lower()=="vessel").sum()) if not d.empty else 0)
        m3.metric("Authorities",d["Authority ID"].nunique() if not d.empty and "Authority ID" in d.columns else 0)
        m4.metric("Programmes",d["Programme ID"].nunique() if not d.empty and "Programme ID" in d.columns else 0)

        counts=sanctions_programme_counts(d)
        if not counts.empty:
            render_dark_bar_list(counts,"Programme","Designations","Designations by programme")

        tabs=st.tabs([
            "Designations",
            "Linked Entities",
            "Authorities & Programmes",
            "Watchlists",
            "Policy Precedence"
        ])

        with tabs[0]:
            st.markdown("### Government sanctions designations")
            display_df(humanize_sanctions_df(d),250)

        with tabs[1]:
            st.markdown("### Designated / linked entities")
            if l.empty:
                st.info("No linked entities for this filter.")
            else:
                render_sanction_link_cards(l)

        with tabs[2]:
            a=auth.copy()
            if not a.empty:
                # Authority IDs are backend keys; show names and jurisdiction.
                a=a.drop(columns=[c for c in ["Authority ID"] if c in a.columns],errors="ignore")
                st.markdown("### Authorities")
                display_df(a,100)
            if not progs.empty:
                pp=progs.copy()
                if "Authority ID" in pp.columns:
                    pp["Authority"]=pp["Authority ID"].astype(str).map(lambda x:SAN_AUTH_MAP.get(x,x))
                pp=pp.drop(columns=[c for c in ["Programme ID","Authority ID"] if c in pp.columns],errors="ignore")
                st.markdown("### Programmes")
                display_df(pp,100)

        with tabs[3]:
            st.markdown("### Watchlist taxonomy")
            st.caption("These categories are intentionally separate: a security advisory, shadow-fleet flag or IUU listing is not automatically a government sanctions designation.")
            display_df(humanize_sanctions_df(watch),100)

        with tabs[4]:
            st.markdown("### Policy precedence")
            st.caption("Trade preferences never override sanctions, prohibitions or export-control requirements.")
            rr=rules.copy()
            rr=rr.drop(columns=[c for c in ["Rule ID"] if c in rr.columns],errors="ignore")
            display_df(rr,100)

elif page=="News & Events":
    header("News & Events","Map assets and systems affected by war, weather, natural hazards, labour, operational incidents and announced commercial activity.")
    events=TABLES.get(("Events & Hazards","Events"),pd.DataFrame()).copy()
    locations=TABLES.get(("Events & Hazards","Event Locations"),pd.DataFrame()).copy()
    q=st.text_input("Search events / location / company / system",placeholder="Rotterdam, strike, Black Sea, AD Ports, typhoon, Genoa...")
    families=sorted([x for x in events.get("Event Family",pd.Series(dtype=str)).unique().tolist() if str(x).strip()])
    selected=st.multiselect("Event families",families,default=[])
    e=events
    if q:
        e=_contains_any(e,[q])
        # also expand through company/asset/system link names
        ids=set(e["Event ID"].astype(str).tolist()) if not e.empty else set()
        for key in [("Events & Hazards","Event Company Links"),("Events & Hazards","Event Asset Links"),("Events & Hazards","Event System Links")]:
            df=TABLES.get(key,pd.DataFrame())
            if not df.empty:
                m=_contains_any(df,[q])
                if "Event ID" in m.columns: ids.update(m["Event ID"].astype(str).tolist())
        e=events[events["Event ID"].astype(str).isin(ids)] if ids else events.iloc[0:0]
    if selected:
        e=e[e["Event Family"].isin(selected)]
    ids=set(e["Event ID"].astype(str)) if not e.empty else set()
    loc=locations[locations["Event ID"].astype(str).isin(ids)] if ids else locations.iloc[0:0]
    render_event_map(e,loc,"Event & activity map")
    # severity / family figures
    if not e.empty:
        c1,c2=st.columns(2)
        with c1:
            fam=e["Event Family"].value_counts()
            if not fam.empty:
                st.markdown("### Events by family"); st.bar_chart(fam,horizontal=True)
        with c2:
            sev=e["Severity"].value_counts()
            if not sev.empty:
                st.markdown("### Events by severity"); st.bar_chart(sev,horizontal=True)
    t1,t2,t3=st.tabs(["Event Feed","Impact Chains","Linked Assets / Companies"])
    with t1: render_event_cards(e,100)
    with t2:
        chains=TABLES.get(("Events & Hazards","Impact Chains"),pd.DataFrame())
        if ids: chains=chains[chains["Event ID"].astype(str).isin(ids)]
        display_df(chains,200)
    with t3:
        al=TABLES.get(("Events & Hazards","Event Asset Links"),pd.DataFrame())
        cl=TABLES.get(("Events & Hazards","Event Company Links"),pd.DataFrame())
        sl=TABLES.get(("Events & Hazards","Event System Links"),pd.DataFrame())
        if ids:
            al=al[al["Event ID"].astype(str).isin(ids)]
            cl=cl[cl["Event ID"].astype(str).isin(ids)]
            sl=sl[sl["Event ID"].astype(str).isin(ids)]
        a,b,c=st.tabs(["Assets","Companies","Systems"])
        with a:
            render_linked_objects(
                al,
                object_type_col="Asset Type",
                object_id_col="Asset ID",
                object_name_col="Asset",
                relationship_col="Relationship",
                confidence_col="Confidence",
                max_items=200
            )
        with b:
            render_linked_objects(
                cl,
                object_type_col="Relationship",
                object_id_col="Company ID",
                object_name_col="Company",
                relationship_col="Relationship",
                confidence_col="Confidence",
                max_items=200
            )
        with c:
            render_linked_objects(
                sl,
                object_type_col="Relationship",
                object_id_col="System ID",
                object_name_col="System",
                relationship_col="Relationship",
                confidence_col="Confidence",
                max_items=200
            )

elif page=="Systems":
    header("Systems & Corridors","Connected port, rail, waterway and corridor systems with linked events.")
    systems=TABLES.get(("Systems & Waterways","Systems"),pd.DataFrame())
    if systems.empty:
        st.info("Systems workbook not available.")
    else:
        systems=systems.reset_index(drop=True)
        requested_system=st.session_state.pop("system_pick_id",None)
        default_system=0
        if requested_system and "System ID" in systems.columns:
            mi=systems.index[systems["System ID"].astype(str).eq(str(requested_system))].tolist()
            if mi: default_system=int(mi[0])

        names=systems["System"].tolist()
        if requested_system:
            st.session_state["system_select_name"]=names[default_system]
        else:
            current_system=st.session_state.get("system_select_name",names[default_system])
            if not isinstance(current_system,str) or current_system not in names:
                st.session_state["system_select_name"]=names[default_system]

        name=st.selectbox("System",names,key="system_select_name")
        srow=systems[systems["System"]==name].iloc[0]; sid=srow["System ID"]
        st.markdown(f"## {name}")
        st.caption(f"{srow.get('Geography','')} · {srow.get('Archetype','')}")
        se=TABLES.get(("Systems & Waterways","System Entities"),pd.DataFrame())
        sl=TABLES.get(("Systems & Waterways","System Links"),pd.DataFrame())
        sf=TABLES.get(("Systems & Waterways","Facilities"),pd.DataFrame())
        si=TABLES.get(("Systems & Waterways","Network Interfaces"),pd.DataFrame())
        sube=se[se["System ID"].astype(str).eq(str(sid))] if "System ID" in se.columns else pd.DataFrame()
        subs=sl[sl["System ID"].astype(str).eq(str(sid))] if "System ID" in sl.columns else pd.DataFrame()
        subf=sf[sf["System ID"].astype(str).eq(str(sid))] if "System ID" in sf.columns else pd.DataFrame()
        subi=si[si["System ID"].astype(str).eq(str(sid))] if "System ID" in si.columns else pd.DataFrame()
        ev,loc,chains=event_bundle_for_entities(system_ids=[sid])
        if not ev.empty: render_event_map(ev,loc,"System events")
        tabs=st.tabs(["Entities","Relationships","Facilities","Interfaces","Events"])
        with tabs[0]: display_df(sube,200)
        with tabs[1]:
            for _,r in subs.iterrows():
                st.markdown(f"<div class='pc-rel'><b>{label(r['Source Entity ID'])}</b> → {str(r['Relationship']).replace('_',' ').title()} → <b>{label(r['Target Entity ID'])}</b></div>",unsafe_allow_html=True)
        with tabs[2]: display_df(subf,200)
        with tabs[3]: display_df(subi,200)
        with tabs[4]:
            render_event_cards(ev,50)
            if not chains.empty: display_df(chains,100)

elif page=="Data":
    header("Data Explorer","Raw evidence and debugging tables. Internal IDs remain hidden unless explicitly enabled.")
    wb_label=st.selectbox("Workbook",list(WORKBOOKS.keys()))
    sheet=st.selectbox("Sheet",workbook_sheets(wb_label))
    df=load_sheet(wb_label,sheet)
    q=st.text_input("Filter this table")
    if q: df=_contains_any(df,[q])
    show_debug_ids=st.toggle("Show internal database IDs",value=False)
    display_df(df,600,show_ids=show_debug_ids)

st.sidebar.markdown("---")
st.sidebar.caption(f"{APP_TITLE} {APP_VERSION} · {len(TABLES):,} loaded tables")
