from pathlib import Path
import re
import pandas as pd
import streamlit as st

APP_TITLE = "P&C Trade System"
APP_VERSION = "v1.17"
DATA_DIR = Path(__file__).parent / "data"

st.set_page_config(
    page_title=f"{APP_TITLE} {APP_VERSION}",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------- Theme ----------
st.markdown("""
<style>
:root {
  --pc-bg:#07111f;
  --pc-panel:#0d1a2b;
  --pc-panel2:#101f33;
  --pc-border:#233852;
  --pc-text:#e9eef5;
  --pc-muted:#9fb0c4;
  --pc-gold:#c8a45b;
  --pc-blue:#4aa3df;
}
.stApp { background:var(--pc-bg); color:var(--pc-text); }
[data-testid="stSidebar"] { background:#081523; border-right:1px solid var(--pc-border); }
h1,h2,h3 { color:var(--pc-text); }
.pc-kicker { color:var(--pc-gold); font-size:.78rem; letter-spacing:.14em; text-transform:uppercase; font-weight:700; }
.pc-title { font-size:2rem; font-weight:800; margin:.2rem 0 .1rem; }
.pc-sub { color:var(--pc-muted); margin-bottom:1.1rem; }
.pc-card {
  background:linear-gradient(180deg,var(--pc-panel),var(--pc-panel2));
  border:1px solid var(--pc-border);
  border-radius:12px; padding:15px 17px; min-height:96px;
}
.pc-label { color:var(--pc-muted); font-size:.77rem; text-transform:uppercase; letter-spacing:.08em; }
.pc-value { color:var(--pc-text); font-size:1.45rem; font-weight:760; margin-top:3px; }
.pc-small { color:var(--pc-muted); font-size:.86rem; }
.pc-rule { border-top:1px solid var(--pc-border); margin:1rem 0; }
div[data-testid="stMetric"] {
  background:var(--pc-panel); border:1px solid var(--pc-border);
  border-radius:10px; padding:10px 13px;
}
.stDataFrame { border:1px solid var(--pc-border); border-radius:9px; }
a { color:#7cc3ef !important; }
</style>
""", unsafe_allow_html=True)

# ---------- Data helpers ----------
@st.cache_data(show_spinner=False)
def load_csv(name):
    path = DATA_DIR / name
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str, keep_default_na=False)
    except Exception:
        return pd.DataFrame()

TABLES = {
    "companies": "companies.csv",
    "ports": "ports.csv",
    "terminals": "port_terminals.csv",
    "port_operator_coverage": "port_operator_coverage.csv",
    "berths": "port_berths.csv",
    "equipment": "port_equipment.csv",
    "ownership": "port_ownership.csv",
    "port_news": "port_news.csv",
    "vessels": "vessels.csv",
    "vessel_relationships": "vessel_relationships.csv",
    "fleet_portfolios": "fleet_portfolios.csv",
    "fleet_orders": "fleet_orders.csv",
    "aircraft": "aircraft_registry.csv",
    "aircraft_relationships": "aircraft_relationships.csv",
    "aviation_summary": "aviation_fleet_summary.csv",
    "assets": "assets.csv",
    "shipyards": "shipyards.csv",
    "infra_works": "infrastructure_works.csv",
    "infra_deals": "infrastructure_deals.csv",
    "infra_investors": "infrastructure_investors.csv",
    "infra_holdings": "infrastructure_holdings.csv",
    "connections": "infrastructure_connections.csv",
    "logistics_networks": "integrated_logistics_networks.csv",
    "rail_operators": "rail_operators.csv",
    "rail_networks": "rail_networks.csv",
    "rail_nodes": "rail_nodes.csv",
    "rail_links": "rail_links.csv",
    "rail_relationships": "rail_relationships.csv",
    "rail_fleet": "rail_fleet.csv",
    "rail_connections": "rail_connections.csv",
    "rail_news": "rail_news.csv",
    "events": "strategic_events.csv",
    "event_observations": "event_observations.csv",
    "event_links": "event_entity_links.csv",
    "news": "news_registry.csv",
    "news_links": "news_entity_links.csv",
    "monitoring": "monitoring.csv",
    "monitoring_links": "monitoring_event_links.csv",
    "transaction_links": "transaction_asset_links.csv",
    "asset_constraints": "asset_constraints.csv",
    "asset_control": "asset_control_history.csv",
    "sources": "sources.csv",
    "ferry_systems": "ferry_systems.csv",
    "ferry_routes": "ferry_routes.csv",
    "ferry_terminals": "ferry_terminals.csv",
    "ferry_status": "ferry_fleet_status.csv",
    "ferry_performance": "ferry_performance.csv",
    "great_lakes_ports": "great_lakes_ports.csv",
    "great_lakes_vessels": "great_lakes_vessel_staging.csv",
    "great_lakes_corridors": "great_lakes_cargo_corridors.csv",
    "great_lakes_cruise": "great_lakes_cruise.csv",
    "great_lakes_disruptions": "great_lakes_disruptions.csv",
}

D = {k: load_csv(v) for k, v in TABLES.items()}

def col(df, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    return None

def clean(df):
    if df.empty:
        return df
    drop_exact = {
        "Source ID","Source Asset ID","Source Asset IDs","Canonicalization Note",
        "Company ID","Port ID","Vessel ID","Asset ID","Entity ID","Terminal ID",
        "Observation ID","Canonical Event ID","Source Record ID","News ID",
        "Monitoring ID","Deal ID","Work ID","Shipyard ID","Equipment Record ID",
        "Ownership ID","Event Link ID","News Link ID","Transaction Link ID",
        "Control Record ID","Constraint ID","Relationship ID"
    }
    cols = [c for c in df.columns if c not in drop_exact and not c.lower().endswith("_id")]
    return df[cols].copy()

def text_search(df, q):
    if df.empty or not q:
        return df
    mask = df.astype(str).apply(
        lambda s: s.str.contains(re.escape(q), case=False, na=False)
    ).any(axis=1)
    return df[mask]

def safe_display(df, max_rows=250, height=None):
    if df.empty:
        st.info("No matching records in the current model.")
        return
    show = clean(df).head(max_rows)
    cfg = {}
    for c in show.columns:
        lc = c.lower()
        if lc in {"url","source url","feed url","source reference"} or "url" in lc:
            cfg[c] = st.column_config.LinkColumn(c, display_text="Open")
    st.dataframe(show, use_container_width=True, hide_index=True, height=height, column_config=cfg)

def entity_news(entity_id):
    nl = D["news_links"]
    n = D["news"]
    if not entity_id or nl.empty or n.empty:
        return pd.DataFrame()
    eid = col(nl, ["Entity ID"])
    nid = col(nl, ["News ID"])
    nnid = col(n, ["News ID"])
    if not all([eid,nid,nnid]):
        return pd.DataFrame()
    links = nl[nl[eid] == entity_id]
    if links.empty:
        return pd.DataFrame()
    return n[n[nnid].isin(links[nid].tolist())].copy()

def event_news(event_id):
    n = D["news"]
    if n.empty or "Canonical Event ID" not in n.columns:
        return pd.DataFrame()
    return n[n["Canonical Event ID"] == event_id].copy()

def entity_events(entity_id):
    el = D["event_links"]
    eo = D["event_observations"]
    if not entity_id or el.empty or eo.empty:
        return pd.DataFrame()
    eid = col(el, ["Entity ID"])
    oid = col(el, ["Observation ID"])
    eoid = col(eo, ["Observation ID"])
    if not all([eid,oid,eoid]):
        return pd.DataFrame()
    hits = el[el[eid] == entity_id]
    return eo[eo[eoid].isin(hits[oid].tolist())].copy() if not hits.empty else pd.DataFrame()

def profile_pairs(row, fields):
    items = []
    for label, key in fields:
        if key in row and str(row[key]).strip():
            items.append((label, row[key]))
    return items

def render_pairs(items, cols=4):
    if not items:
        return
    containers = st.columns(cols)
    for i,(label,value) in enumerate(items):
        containers[i % cols].markdown(
            f"<div class='pc-card'><div class='pc-label'>{label}</div>"
            f"<div class='pc-small'>{value}</div></div>",
            unsafe_allow_html=True
        )

def metric_card(label, value, note=""):
    st.markdown(
        f"<div class='pc-card'><div class='pc-label'>{label}</div>"
        f"<div class='pc-value'>{value}</div><div class='pc-small'>{note}</div></div>",
        unsafe_allow_html=True
    )

def page_header(title, sub):
    st.markdown("<div class='pc-kicker'>Power & Corridors Intelligence</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='pc-title'>{title}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='pc-sub'>{sub}</div>", unsafe_allow_html=True)

# ---------- Sidebar ----------
st.sidebar.markdown("### P&C Trade System")
st.sidebar.caption("Intelligence Model v1.17")
page = st.sidebar.radio(
    "Navigate",
    [
        "Operating Picture",
        "Companies",
        "Ports & Terminals",
        "Vessels",
        "Air Cargo",
        "News & Events",
        "Monitoring",
        "Transactions & Projects",
        "Infrastructure",
        "Rail Networks",
        "Ferry Systems",
        "Great Lakes",
        "Ask P&C",
    ],
)
st.sidebar.markdown("---")
st.sidebar.caption("Ports • rail • fleets • entity-enriched news • monitoring • transactions")

# ---------- Pages ----------
if page == "Operating Picture":
    page_header("Operating Picture", "A cross-domain view of companies, assets, ports, fleets, events and developing situations.")
    c = st.columns(7)
    vals = [
        ("Companies", len(D["companies"]), "canonical organizations"),
        ("Ports", len(D["ports"]), "canonical port/facility records"),
        ("Vessels", len(D["vessels"]), "canonical vessel records"),
        ("Aircraft", len(D["aircraft"]), "registration-level identities"),
        ("Rail", len(D["rail_networks"]), "canonical networks / corridors"),
        ("News", len(D["news"]), "entity-linked current stories"),
        ("Monitoring", len(D["monitoring"]), "active analytical watches"),
    ]
    for x,(label,val,note) in zip(c, vals):
        with x: metric_card(label, f"{val:,}", note)

    st.markdown("### Latest news")
    news = D["news"].copy()
    dc = col(news, ["Published Date","Date"])
    if dc:
        news = news.sort_values(dc, ascending=False)
    safe_display(news.head(12), 12)

    a,b = st.columns(2)
    with a:
        st.markdown("### Latest event observations")
        eo = D["event_observations"].copy()
        dc = col(eo, ["Date"])
        if dc:
            eo = eo.sort_values(dc, ascending=False)
        safe_display(eo.head(12), 12)
    with b:
        st.markdown("### Active monitoring")
        safe_display(D["monitoring"], 20)

elif page == "Companies":
    page_header("Companies", "Corporate ecosystems, ownership, assets, fleets, transactions and related reporting.")
    df = D["companies"]
    if df.empty:
        st.warning("companies.csv is missing.")
        st.stop()
    namec = col(df, ["Company","Company Name"])
    options = sorted([x for x in df[namec].unique() if x]) if namec else []
    selected = st.selectbox("Company", options)
    row = df[df[namec] == selected].iloc[0]
    cid = row.get("Company ID","")

    render_pairs(profile_pairs(row, [
        ("Entity type","Entity Type"),("HQ","HQ City"),("Country","HQ Country"),
        ("Ownership","Ownership"),("Business segments","Business Segments"),
        ("Senior leader","Senior Leader"),("Title","Title"),("Status","Status"),
        ("Scale / network","Scale / Network Notes"),
    ]), 3)

    tabs = st.tabs(["Relationships","Assets","Fleet","Transactions","Events","News"])
    with tabs[0]:
        rel = D["relationships"]
        if not rel.empty:
            mask = (rel.get("Source Entity","") == cid) | (rel.get("Target Entity","") == cid)
            safe_display(rel[mask])
        else: st.info("No relationship table.")
    with tabs[1]:
        assets = D["assets"]
        safe_display(assets[assets.get("Company ID","") == cid] if not assets.empty else assets)
        ptc = D["terminals"]
        if not ptc.empty and "Primary Operator Company ID" in ptc.columns:
            linked_t = ptc[ptc["Primary Operator Company ID"].astype(str) == cid]
            if not linked_t.empty:
                st.markdown("#### Port / terminal assets")
                safe_display(linked_t)
        ftc = D["ferry_terminals"]
        if not ftc.empty and "Operator Company ID" in ftc.columns:
            linked_ft = ftc[ftc["Operator Company ID"].astype(str) == cid]
            if not linked_ft.empty:
                st.markdown("#### Ferry terminals")
                safe_display(linked_ft)
        rr = D["rail_relationships"]
        rn = D["rail_networks"]
        if not rr.empty and "Company ID" in rr.columns and "Rail Network ID" in rr.columns:
            rids = rr[rr["Company ID"].astype(str) == cid]["Rail Network ID"].dropna().astype(str).unique().tolist()
            linked_rn = rn[rn["Rail Network ID"].isin(rids)] if not rn.empty and "Rail Network ID" in rn.columns else pd.DataFrame()
            if not linked_rn.empty:
                st.markdown("#### Rail networks / corridors")
                safe_display(linked_rn)
        rnodes = D["rail_nodes"]
        if not rnodes.empty and "Primary Company ID" in rnodes.columns:
            linked_nodes = rnodes[rnodes["Primary Company ID"].astype(str) == cid]
            if not linked_nodes.empty:
                st.markdown("#### Rail terminals / nodes")
                safe_display(linked_nodes)
    with tabs[2]:
        vessel_rel = D["vessel_relationships"]
        vessels = D["vessels"]
        direct = vessels[
            (vessels.get("Owner Company ID","") == cid) |
            (vessels.get("Operator Company ID","") == cid)
        ] if not vessels.empty else vessels
        if not vessel_rel.empty and "Company ID" in vessel_rel.columns and "Vessel ID" in vessel_rel.columns:
            ids = vessel_rel[vessel_rel["Company ID"] == cid]["Vessel ID"].unique().tolist()
            extra = vessels[vessels["Vessel ID"].isin(ids)] if not vessels.empty and "Vessel ID" in vessels.columns else pd.DataFrame()
            direct = pd.concat([direct, extra]).drop_duplicates(subset=["Vessel ID"]) if not extra.empty else direct
        safe_display(direct)
        # Canonical aircraft linked by operator or network customer
        ac = D["aircraft"]
        if not ac.empty:
            amask = pd.Series(False, index=ac.index)
            for cc in ["Operator Company ID","Network Customer Company ID"]:
                if cc in ac.columns:
                    amask = amask | (ac[cc].astype(str) == cid)
            av = ac[amask]
            if not av.empty:
                st.markdown("#### Individual aircraft")
                safe_display(av)
        # Ferry-system overlay stays visible, but vessels remain canonical Vessels above
        fs = D["ferry_systems"]
        if not fs.empty and "Operator Company ID" in fs.columns:
            fsv = fs[fs["Operator Company ID"].astype(str) == cid]
            if not fsv.empty:
                st.markdown("#### Ferry systems")
                safe_display(fsv)
        rf = D["rail_fleet"]
        if not rf.empty and "Company ID" in rf.columns:
            rv = rf[rf["Company ID"].astype(str) == cid]
            if not rv.empty:
                st.markdown("#### Rail fleet / rolling stock")
                safe_display(rv)
    with tabs[3]:
        deals = D["infra_deals"]
        tl = D["transaction_links"]
        if not deals.empty:
            mask = deals.astype(str).apply(lambda s: s.str.contains(re.escape(cid), case=False, na=False)).any(axis=1)
            linked_deals = deals[mask]
            if not tl.empty and "Entity / Asset ID" in tl.columns and "Deal ID" in tl.columns and "Deal ID" in deals.columns:
                d_ids = tl[tl["Entity / Asset ID"] == cid]["Deal ID"].unique().tolist()
                linked_deals = pd.concat([linked_deals, deals[deals["Deal ID"].isin(d_ids)]]).drop_duplicates()
            safe_display(linked_deals)
    with tabs[4]:
        safe_display(entity_events(cid))
    with tabs[5]:
        safe_display(entity_news(cid))

elif page == "Ports & Terminals":
    page_header("Ports & Terminals", "Canonical port profiles with terminals, berths, equipment, ownership, projects, incidents and news.")
    ports = D["ports"]
    namec = col(ports, ["Port / Facility","Port"])
    pview = ports.copy()
    terminals_all = D["terminals"]
    # Filter from the canonical terminal layer so shared ports and operator networks resolve correctly.
    if not terminals_all.empty and "Primary Operator" in terminals_all.columns:
        opvals = sorted([x for x in terminals_all["Primary Operator"].dropna().astype(str).unique() if x.strip()])
        opopts = ["All operators"] + opvals
        opick = st.selectbox("Operator / network", opopts)
        if opick != "All operators":
            tids = terminals_all[terminals_all["Primary Operator"].astype(str) == opick]["Port ID"].dropna().astype(str).unique().tolist()
            if "Port ID" in pview.columns:
                pview = pview[pview["Port ID"].astype(str).isin(tids)]
    coverage = D.get("port_operator_coverage", pd.DataFrame())
    if not coverage.empty:
        with st.expander("Operator network coverage"):
            safe_display(coverage)
    options = sorted([x for x in pview[namec].unique() if x]) if not pview.empty and namec else []
    selected = st.selectbox("Port", options)
    row = pview[pview[namec] == selected].iloc[0]
    pid = row.get("Port ID","")

    render_pairs(profile_pairs(row, [
        ("Country","Country"),("Facility type","Facility Type"),("Operator","Operator"),
        ("Key role","Key Role"),("Coverage","Coverage Note"),
    ]), 3)

    tabs = st.tabs(["Terminals","Berths & Equipment","Ownership","Rail","Projects & Constraints","Events","News"])
    terminals = D["terminals"]
    pt = terminals[terminals.get("Port ID","") == pid] if not terminals.empty else terminals
    with tabs[0]:
        safe_display(pt)
    with tabs[1]:
        if pt.empty or "Terminal ID" not in pt.columns:
            st.info("No terminal detail.")
        else:
            tids = pt["Terminal ID"].tolist()
            a,b = st.columns(2)
            with a:
                st.markdown("#### Berths")
                safe_display(D["berths"][D["berths"].get("Terminal ID","").isin(tids)] if not D["berths"].empty else D["berths"])
            with b:
                st.markdown("#### Equipment")
                safe_display(D["equipment"][D["equipment"].get("Terminal ID","").isin(tids)] if not D["equipment"].empty else D["equipment"])
    with tabs[2]:
        if pt.empty or "Terminal ID" not in pt.columns:
            st.info("No terminal ownership detail.")
        else:
            tids = pt["Terminal ID"].tolist()
            own = D["ownership"]
            safe_display(own[own.get("Terminal ID","").isin(tids)] if not own.empty else own)
    with tabs[3]:
        rc = D["rail_connections"]
        rn = D["rail_nodes"]
        phits = rc[rc["Connected Entity ID"].astype(str) == pid] if not rc.empty and "Connected Entity ID" in rc.columns else pd.DataFrame()
        if not pt.empty and "Terminal ID" in pt.columns and not rc.empty and "Connected Entity ID" in rc.columns:
            thits = rc[rc["Connected Entity ID"].astype(str).isin(pt["Terminal ID"].astype(str).tolist())]
            phits = pd.concat([phits, thits]).drop_duplicates() if not thits.empty else phits
        if phits.empty:
            st.info("No canonical rail connection captured for this port yet.")
        else:
            safe_display(phits)
            if "Rail Node ID" in phits.columns and not rn.empty:
                nids=phits["Rail Node ID"].dropna().astype(str).unique().tolist()
                linked_nodes=rn[rn["Rail Node ID"].isin(nids)] if "Rail Node ID" in rn.columns else pd.DataFrame()
                if not linked_nodes.empty:
                    st.markdown("#### Connected rail nodes")
                    safe_display(linked_nodes)
    with tabs[4]:
        works = D["infra_works"]
        hits = text_search(works, selected)
        safe_display(hits)
        cons = D["asset_constraints"]
        c_hits = text_search(cons, selected)
        if not c_hits.empty:
            st.markdown("#### Asset constraints")
            safe_display(c_hits)
    with tabs[5]:
        safe_display(entity_events(pid))
    with tabs[6]:
        n1 = entity_news(pid)
        # add terminal-linked news too
        if not pt.empty and "Terminal ID" in pt.columns and not D["port_news"].empty:
            pn = D["port_news"]
            pn = pn[pn.get("Terminal ID","").isin(pt["Terminal ID"].tolist())]
        else:
            pn = pd.DataFrame()
        if not n1.empty:
            safe_display(n1)
        if not pn.empty:
            st.markdown("#### Terminal-linked developments")
            safe_display(pn)

elif page == "Vessels":
    page_header("Vessels", "Individual vessels with IMO, ownership/operator relationships, incidents and linked reporting.")
    df = D["vessels"]
    q = st.text_input("Search vessel name or IMO")
    view = text_search(df, q) if q else df
    if view.empty:
        st.info("No vessel match.")
    else:
        namec = col(view, ["Vessel Name"])
        labels = []
        for _,r in view.head(500).iterrows():
            imo = r.get("IMO","")
            labels.append(f"{r.get(namec,'')} — IMO {imo}" if imo else r.get(namec,""))
        pick = st.selectbox("Vessel", labels)
        idx = labels.index(pick)
        row = view.head(500).iloc[idx]
        vid = row.get("Vessel ID","")
        render_pairs(profile_pairs(row, [
            ("IMO","IMO"),("Type","Vessel Type"),("Subtype / class","Subtype / Class"),
            ("Flag","Flag"),("Built","Year Built"),("DWT","DWT"),("Capacity","Capacity"),
            ("Primary service","Primary Service"),("Status","Status"),
            ("Registered owner","Registered Owner (Legal)"),("Manager","Technical / ISM Manager"),
        ]), 3)
        tabs = st.tabs(["Relationships","Events","News"])
        with tabs[0]:
            vr = D["vessel_relationships"]
            safe_display(vr[vr.get("Vessel ID","") == vid] if not vr.empty else vr)
        with tabs[1]:
            safe_display(entity_events(vid))
        with tabs[2]:
            safe_display(entity_news(vid))

elif page == "Air Cargo":
    page_header("Air Cargo", "Registration-level aircraft identities, operator/network relationships and portfolio coverage.")
    a,b,c = st.columns(3)
    with a: metric_card("Aircraft identities", f"{len(D['aircraft']):,}", "physical aircraft rows")
    with b: metric_card("Relationship edges", f"{len(D['aircraft_relationships']):,}", "operator / network / ownership links")
    with c: metric_card("Portfolio programs", f"{len(D['aviation_summary']):,}", "official fleet denominator snapshots")
    q = st.text_input("Search airline, registration, MSN or aircraft type")
    safe_display(text_search(D["aircraft"], q) if q else D["aviation_summary"], 300)

elif page == "News & Events":
    page_header("News & Events", "Reporting is kept separate from the underlying canonical event, then linked back to affected entities.")
    tab1,tab2 = st.tabs(["News","Canonical / observed events"])
    with tab1:
        n = D["news"].copy()
        c1,c2 = st.columns(2)
        with c1:
            q = st.text_input("Search news", key="newsq")
        with c2:
            event_type = st.selectbox("Event type", ["All"] + sorted([x for x in n.get("Event Type",pd.Series(dtype=str)).unique() if x]))
        if q:
            n = text_search(n,q)
        if event_type != "All" and "Event Type" in n.columns:
            n = n[n["Event Type"] == event_type]
        dc = col(n,["Published Date","Date"])
        if dc: n = n.sort_values(dc, ascending=False)
        safe_display(n,500)
    with tab2:
        eo = D["event_observations"].copy()
        q2 = st.text_input("Search event observations", key="eventq")
        if q2: eo = text_search(eo,q2)
        dc = col(eo,["Date"])
        if dc: eo = eo.sort_values(dc, ascending=False)
        safe_display(eo,500)

elif page == "Monitoring":
    page_header("Monitoring", "Active watch objects aggregate developing events, indicators, thresholds and next milestones.")
    m = D["monitoring"].copy()
    if m.empty:
        st.info("No monitoring records.")
    else:
        titles = m.get("Title", pd.Series(dtype=str)).tolist()
        sel = st.selectbox("Monitoring topic", titles)
        row = m[m["Title"] == sel].iloc[0]
        render_pairs(profile_pairs(row, [
            ("Family","Family"),("Geography","Geography"),("Status","Status"),
            ("Time horizon","Time Horizon"),("Confidence","Confidence"),
            ("Last reviewed","Last Reviewed"),("Next milestone","Next Review / Milestone"),
        ]),3)
        st.markdown("#### What is being monitored")
        st.write(row.get("What Is Being Monitored",""))
        st.markdown("#### Key indicators")
        st.write(row.get("Key Indicators",""))
        st.markdown("#### Trigger / threshold")
        st.write(row.get("Trigger / Threshold",""))
        mid = row.get("Monitoring ID","")
        ml = D["monitoring_links"]
        events = D["events"]
        if not ml.empty and "Monitoring ID" in ml.columns and "Canonical Event ID" in ml.columns and "Event ID" in events.columns:
            eids = ml[ml["Monitoring ID"] == mid]["Canonical Event ID"].tolist()
            linked = events[events["Event ID"].isin(eids)]
            if not linked.empty:
                st.markdown("#### Linked canonical events")
                safe_display(linked)

elif page == "Transactions & Projects":
    page_header("Transactions & Projects", "M&A, strategic bids, port/terminal investment and the physical assets affected.")
    t1,t2 = st.tabs(["Transactions","Projects / works"])
    with t1:
        deals = D["infra_deals"].copy()
        q = st.text_input("Search transactions", key="dealq")
        if q: deals = text_search(deals,q)
        safe_display(deals,500)
    with t2:
        works = D["infra_works"].copy()
        q = st.text_input("Search projects", key="workq")
        if q: works = text_search(works,q)
        safe_display(works,500)

elif page == "Infrastructure":
    page_header("Infrastructure", "Ports, rail, dry ports, economic zones, logistics real estate, shipyards and system connections.")
    tabs = st.tabs(["Assets","Shipyards","Connections","Investors / holdings","Control & constraints"])
    with tabs[0]:
        q=st.text_input("Search infrastructure assets",key="assetq")
        safe_display(text_search(D["assets"],q) if q else D["assets"],500)
    with tabs[1]:
        safe_display(D["shipyards"],500)
    with tabs[2]:
        safe_display(D["connections"],500)
    with tabs[3]:
        safe_display(D["infra_investors"],300)
        if not D["infra_holdings"].empty:
            st.markdown("#### Holdings")
            safe_display(D["infra_holdings"],500)
    with tabs[4]:
        a,b=st.columns(2)
        with a:
            st.markdown("#### Asset control history")
            safe_display(D["asset_control"])
        with b:
            st.markdown("#### Asset constraints")
            safe_display(D["asset_constraints"])

elif page == "Rail Networks":
    page_header("Rail Networks", "Companies, corridors, origin/destination nodes, port and dry-port connections, rolling stock and rail developments.")
    a,b,c,d = st.columns(4)
    with a: metric_card("Rail operators", f"{len(D['rail_operators']):,}", "company-linked operators / authorities")
    with b: metric_card("Networks", f"{len(D['rail_networks']):,}", "named corridors / systems")
    with c: metric_card("Physical nodes", f"{len(D['rail_nodes']):,}", "ports, dry ports, borders, hubs")
    with d: metric_card("Movement links", f"{len(D['rail_links']):,}", "origin → destination edges")
    tabs=st.tabs(["Networks","Nodes","Links","Operators","Fleet","Port / asset connections","News"])
    with tabs[0]:
        q=st.text_input("Search rail network / corridor",key="railnetq")
        safe_display(text_search(D["rail_networks"],q) if q else D["rail_networks"],500)
    with tabs[1]:
        q=st.text_input("Search rail node / terminal / port",key="railnodeq")
        safe_display(text_search(D["rail_nodes"],q) if q else D["rail_nodes"],500)
    with tabs[2]:
        q=st.text_input("Search origin, destination or corridor",key="raillinkq")
        safe_display(text_search(D["rail_links"],q) if q else D["rail_links"],500)
    with tabs[3]:
        safe_display(D["rail_operators"],300)
        st.markdown("#### Network ownership / operating relationships")
        safe_display(D["rail_relationships"],500)
    with tabs[4]:
        safe_display(D["rail_fleet"],300)
    with tabs[5]:
        safe_display(D["rail_connections"],500)
    with tabs[6]:
        rn=D["rail_news"].copy()
        if not rn.empty and "Date" in rn.columns: rn=rn.sort_values("Date",ascending=False)
        safe_display(rn,300)

elif page == "Ferry Systems":
    page_header("Ferry Systems", "Systems, routes, terminals, fleet status and service-performance observations.")
    tabs=st.tabs(["Systems","Routes","Terminals","Fleet status","Performance"])
    with tabs[0]: safe_display(D["ferry_systems"],200)
    with tabs[1]: safe_display(D["ferry_routes"],500)
    with tabs[2]: safe_display(D["ferry_terminals"],500)
    with tabs[3]: safe_display(D["ferry_status"],300)
    with tabs[4]: safe_display(D["ferry_performance"],300)

elif page == "Great Lakes":
    page_header("Great Lakes", "Ports, vessel staging, cargo corridors, cruise and disruption coverage.")
    tabs=st.tabs(["Ports","Vessels","Cargo corridors","Cruise","Disruptions"])
    with tabs[0]: safe_display(D["great_lakes_ports"],300)
    with tabs[1]: safe_display(D["great_lakes_vessels"],300)
    with tabs[2]: safe_display(D["great_lakes_corridors"],300)
    with tabs[3]: safe_display(D["great_lakes_cruise"],300)
    with tabs[4]: safe_display(D["great_lakes_disruptions"],300)

elif page == "Ask P&C":
    page_header("Ask P&C", "Local evidence search across the normalized model. It works without an external AI API.")
    q = st.text_input("Ask or search", placeholder="e.g. Yemen ports tanker enforcement, ICTSI TLG, Oakland turning basin")
    if q:
        search_tables = {
            "Companies":D["companies"],"Ports":D["ports"],"Terminals":D["terminals"],
            "Vessels":D["vessels"],"Aircraft":D["aircraft"],"News":D["news"],
            "Events":D["event_observations"],"Monitoring":D["monitoring"],
            "Transactions":D["infra_deals"],"Projects":D["infra_works"],
            "Assets":D["assets"],"Shipyards":D["shipyards"],
            "Rail networks":D["rail_networks"],"Rail nodes":D["rail_nodes"],"Rail links":D["rail_links"],"Rail news":D["rail_news"],
        }
        total=0
        for title,df in search_tables.items():
            hits=text_search(df,q)
            if not hits.empty:
                total += len(hits)
                with st.expander(f"{title} — {len(hits)} match(es)", expanded=(title in {"News","Events","Companies","Ports","Vessels"})):
                    safe_display(hits,100)
        if total==0:
            # Token fallback for natural-language queries.
            tokens=[t for t in re.findall(r"[A-Za-z0-9\-]+",q) if len(t)>3]
            for title,df in search_tables.items():
                if df.empty: continue
                mask=pd.Series(False,index=df.index)
                for tok in tokens:
                    mask |= df.astype(str).apply(lambda s:s.str.contains(re.escape(tok),case=False,na=False)).any(axis=1)
                hits=df[mask]
                if not hits.empty:
                    total += len(hits)
                    with st.expander(f"{title} — {len(hits)} related match(es)"):
                        safe_display(hits,100)
        if total==0:
            st.info("No evidence match found in the current local model.")
    else:
        st.caption("This page is deliberately evidence-bound. An LLM layer can be added later without changing the underlying entity graph.")
