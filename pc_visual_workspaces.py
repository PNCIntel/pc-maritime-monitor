"""P&C Trade/Security customer workspaces v4. Read-only Supabase access.

Uses LIVE SQL delivery views; avoids fixed initial-window filtering and bulk button rendering.
No hypothetical threat ratings, vessel locations, or geographic event pins.
"""
from __future__ import annotations
import datetime as dt
import pandas as pd
import streamlit as st

PAGE_SIZE = 12

@st.cache_data(ttl=75, show_spinner=False)
def _fetch(_db, table, *, columns='*', filters=(), search='', search_columns=('name',), limit=300, offset=0):
    q = _db.table(table).select(columns)
    for column, operator, value in filters:
        if operator == 'eq': q = q.eq(column, value)
        elif operator == 'gte': q = q.gte(column, value)
        elif operator == 'lte': q = q.lte(column, value)
    if search:
        term = search.replace('%', '').replace(',', ' ').strip()
        if term: q = q.or_(','.join(f'{col}.ilike.%{term}%' for col in search_columns))
    return q.range(offset, offset+limit-1).execute().data or []

def _load(db, table, **kwargs):
    try: return _fetch(db, table, **kwargs), None
    except Exception as error: return [], str(error)

def _open(core, typ, oid, title):
    core._set_context(str(typ), str(oid), str(title)); st.rerun()

def _coordinate(row):
    try:
        lat, lon = float(row.get('latitude')), float(row.get('longitude'))
        if -90 <= lat <= 90 and -180 <= lon <= 180 and (lat, lon) != (0, 0): return lat, lon
    except (ValueError, TypeError): pass
    return None

def _geo_map(rows, *, label_key='name', height=520):
    mapped=[]
    for r in rows:
        xy = _coordinate(r)
        if xy: mapped.append({'lat':xy[0], 'lon':xy[1], 'label':str(r.get(label_key) or '')})
    if mapped:
        st.map(pd.DataFrame(mapped), latitude='lat', longitude='lon', height=height, use_container_width=True)
    else:
        st.info('No verified map coordinates for this selection. Records remain available below.')
    return len(mapped)

def _security_cluster_map(rows):
    """Cluster identical coordinates; never manufacture an incident pin."""
    grouped = {}
    missing = []
    for r in rows:
        xy = _coordinate(r)
        if not xy:
            missing.append(r)
            continue
        bucket = grouped.setdefault(xy, {"lat":xy[0],"lon":xy[1],"count":0,"titles":[]})
        bucket["count"] += 1
        if len(bucket["titles"])<4:bucket["titles"].append(str(r.get("title") or "Incident"))
    if grouped:
        import pydeck as pdk
        df=pd.DataFrame(list(grouped.values()))
        df["radius"]=df["count"].pow(0.5)*12000
        df["description"]=df["titles"].map(lambda x:" | ".join(x))
        layer=pdk.Layer("ScatterplotLayer",data=df,get_position="[lon, lat]",
                        get_radius="radius",radius_min_pixels=7,radius_max_pixels=30,
                        get_fill_color=[24,110,178,175],pickable=True)
        st.pydeck_chart(pdk.Deck(layers=[layer],initial_view_state=pdk.ViewState(
            latitude=float(df["lat"].mean()),longitude=float(df["lon"].mean()),zoom=5),
            tooltip={"html":"<b>{count} records</b><br/>{description}<br/>Location can be linked-facility context, not verified strike position."}),
            use_container_width=True)
        st.caption(f"{sum(x['count'] for x in grouped.values())} located records at {len(grouped)} distinct coordinates. Overlaps are clustered.")
    else:st.info("No coordinate-backed incident locations available.")
    if missing:
        with st.expander(f"Evidence without verified coordinates ({len(missing)})"):
            for r in missing[:40]:
                st.write(str(r.get("title") or "Incident")+" — "+str(r.get("location_label") or "Location under review"))
    return len(grouped)

def _trade(db, core):
    st.caption('POWER & CORRIDORS  /  TRADE & LOGISTICS')
    st.title('Global Trade Network')
    st.caption('Explore operating infrastructure, transport connections, companies and commercial developments.')
    tabs = st.tabs(['Infrastructure map', 'Companies & operations', 'Commercial developments'])
    with tabs[0]:
        a,b,c=st.columns([2,1,1])
        term=a.text_input('Search places and facilities', placeholder='Fujairah, Khalifa, Rotterdam, airport…', key='v4_t_search')
        country=b.text_input('Country',placeholder='United Arab Emirates',key='v4_t_country')
        layer=c.selectbox('Infrastructure layer',['All facilities','Ports & terminals','Airports','Rail & intermodal','Road & logistics','Energy & industry'],key='v4_t_layer')
        page=st.number_input('Map results page',min_value=1,max_value=100000,value=1,key='v4_t_page')
        f=[]
        if country: f.append(('country','eq',country))
        names={'Ports & terminals':'port,terminal,harbour,berth','Airports':'airport,aviation','Rail & intermodal':'rail,intermodal,dry port','Road & logistics':'road,warehouse,logistics','Energy & industry':'oil,gas,refin,industrial,energy,pipeline'}
        # All category filters are applied server side, not after fetching the first 1,500 rows.
        rows,err=_load(db,'pc_v4_trade_facilities',filters=tuple(f),search=term,
                       search_columns=('name','category','subtype'),limit=250,offset=(page-1)*250)
        if err:
            st.error('The Trade delivery view is unavailable. Apply the v4 SQL migration and verify database permissions.');st.caption(err);return
        if layer != 'All facilities':
            words=names[layer].split(',')
            rows=[r for r in rows if any(w in ' '.join(str(r.get(k)or'') for k in ('category','subtype','name')).lower() for w in words)]
            st.caption('Layer filtering applies to this result page. Use a search term to narrow the dataset.')
        st.subheader('Infrastructure & transport map')
        mapped=_geo_map(rows,height=580)
        x,y,z=st.columns(3)
        x.metric('Facilities on page',len(rows));y.metric('Mapped facilities',mapped);z.metric('Countries represented',len({r.get('country') for r in rows if r.get('country')}))
        st.subheader('Explore the network')
        if not rows:st.info('No facilities match these filters. Try a broader search or country name.')
        for i in range(0,min(len(rows),36),3):
            cells=st.columns(3)
            for col,r in zip(cells,rows[i:i+3]):
                with col:
                    with st.container(border=True):
                        st.markdown('**'+str(r.get('name') or 'Facility')+'**')
                        st.caption(' · '.join(str(v) for v in (r.get('category'),r.get('country')) if v))
                        if r.get('operator_name'): st.caption('Operated by '+str(r['operator_name']))
                        if st.button('Explore facility',key=f'v4_fac_{page}_{i}_{r.get("object_id")}'):
                            _open(core,'asset',r.get('object_id'),r.get('name'))
        if len(rows)>36:st.caption('Showing the first 36 facility cards from this page. Narrow your filters for more targeted results.')
    with tabs[1]:
        st.subheader('Companies & operating networks')
        name=st.text_input('Find a company',key='v4_company_search',placeholder='AD Ports Group, DP World, Vopak…')
        if len(name.strip())<2:st.info('Search for a company to explore its operating footprint and corporate relationships.')
        else:
            companies,err=_load(db,'pc_delivery_objects',filters=(('object_type','eq','entity'),),
                                search=name,search_columns=('name',),limit=15)
            if err:st.warning('Company search temporarily unavailable.')
            for r in companies:
                left,right=st.columns([5,1]);left.write('**'+str(r.get('name'))+'**')
                if right.button('Explore',key='v4_company_'+str(r.get('object_id'))):_open(core,'entity',r.get('object_id'),r.get('name'))
    with tabs[2]:
        st.subheader('Commercial developments')
        term=st.text_input('Find developments',key='v4_developments_search')
        updates,err=_load(db,'pc_intel_trade_developments',search=term,search_columns=('title','narrative'),limit=20)
        if err:st.warning('Developments are temporarily unavailable.')
        seen=set()
        for row in updates:
            eid=row.get('event_id')
            if not eid or eid in seen:continue
            seen.add(eid)
            with st.container(border=True):
                st.markdown('**'+str(row.get('title') or 'Development')+'**')
                st.caption(str(row.get('occurred_at') or '')[:10])
                if row.get('narrative'):st.write(str(row['narrative'])[:550])
                if st.button('Read development',key='v4_dev_'+str(eid)):_open(core,'event',eid,row.get('title'))

def _security(db, core):
    """Focused intelligence workspace first; raw global discovery is secondary."""
    st.caption("POWER & CORRIDORS / SECURITY & DISRUPTIONS")
    st.title("Security Operating Picture")
    st.caption("Events, vulnerabilities and company exposure · Canonical evidence, independent analysis")
    scope = st.selectbox(
        "Operating area",
        ["Hormuz & Gulf of Oman | Demonstration", "Global incident explorer"],
        key="pc_sec_operating_area",
    )
    if scope == "Hormuz & Gulf of Oman | Demonstration":
        st.markdown("### Hormuz and Gulf of Oman")
        st.caption("Vessel incidents · Fujairah energy infrastructure · linked companies")
        try:
            q = db.table("pc_v_security_hormuz_stories").select("*").limit(100).execute()
            rows = q.data or []
        except Exception as exc:
            rows = []
            st.warning("The Hormuz editorial data view is unavailable. Apply the v3 SQL migration.")
            with st.expander("Technical details"): st.code(str(exc))
        if rows:
            df = pd.DataFrame(rows)
            a,b,c=st.columns(3)
            a.metric("Maritime evidence records",int((df["category"]=="Maritime security").sum()))
            b.metric("Infrastructure observations",int((df["category"]=="Energy infrastructure").sum()))
            c.metric("Total selected records",len(df))
            st.caption("Evidence records, not a count of confirmed independent attacks.")
            try:
                note = db.table("pc_v_security_editorial_latest").select("*").eq(
                    "region_code","HORMUZ_GULF_OF_OMAN").limit(1).execute().data or []
            except Exception: note=[]
            if note:
                n=note[0]
                with st.container(border=True):
                    st.caption("P&C | INDEPENDENT ANALYST BRIEF")
                    st.markdown("#### "+str(n.get("headline") or "Assessment"))
                    st.write(n.get("executive_summary") or "Further assessment underway.")
                    st.caption(str(n.get("observation_label") or "Unscored editorial assessment"))
                    with st.expander("Assessment reasoning"):
                        st.write(n.get("analysis") or "")
            else:
                st.info("No independent P&C editorial note accessible. External source ratings are not P&C ratings.")
            dates=pd.to_datetime(df["occurred_on"],errors="coerce")
            trend=pd.DataFrame({"Month":dates.dt.strftime("%Y-%m"),"Category":df["category"]})
            trend=trend.dropna()
            if not trend.empty:
                st.subheader("Incident and disruption history")
                st.bar_chart(trend.groupby(["Month","Category"]).size().unstack(fill_value=0),
                             y_label="Evidence records")
            st.subheader("What happened")
            for _,r in df.sort_values("occurred_on",ascending=False).iterrows():
                with st.container(border=True):
                    st.markdown("**"+str(r.get("headline") or "Incident")+"**")
                    st.caption(" · ".join(str(r.get(k) or "") for k in
                                ("occurred_on","geographical_area","category")))
                    st.write(str(r.get("operational_effect") or "Consequences being verified"))
                    if r.get("supporting_source") and pd.notna(r.get("supporting_source")):
                        st.link_button("Source and evidence",str(r["supporting_source"]))
                    with st.expander("Related companies and evidence"):
                        st.write("Vessel: "+str(r.get("vessel") or "Not identified"))
                        st.write("Company: "+str(r.get("company") or "Not linked"))
                        st.caption("Reference: "+str(r.get("event_id") or ""))
            st.info("Exact incident pins are not available for this evidence set. The operating-area map requires validated geographic shapes or linked facilities; no false strike coordinates will be shown.")
        else:
            st.info("No demonstration records available yet. The global incident explorer remains accessible.")
        with st.expander("Browse other risk assessments"):
            if st.button("Open assessment history",key="sec_assessments"):
                from pc_global_security_risk import render_global_security_risk
                render_global_security_risk(db,key="sec_optional_assessment")
        return

    st.subheader("Global incident explorer")
    st.caption("Search title, geographic description, or incident type. Results are a page of records, not a regional incident count.")
    a,b=st.columns([3,1])
    term=a.text_input("Search evidence",placeholder="Hormuz, Fujairah, Rotterdam, Red Sea...",key="sec_global_term")
    period=b.selectbox("Period",["Last 30 days","Last 12 months","All history"],key="sec_global_period")
    filters=[]
    now=dt.datetime.now(dt.timezone.utc)
    if period=="Last 30 days":
        filters.append(("occurred_at","gte",(now-dt.timedelta(days=30)).isoformat()))
    elif period=="Last 12 months":
        filters.append(("occurred_at","gte",(now-dt.timedelta(days=365)).isoformat()))
    page=st.number_input("Results page",min_value=1,value=1,key="sec_global_page")
    rows,err=_load(db,"pc_v4_security_geo",filters=tuple(filters),search=term,
                   search_columns=("title","location_label","event_type"),limit=100,offset=(page-1)*100)
    if err:st.warning("Global evidence unavailable.");st.caption(err);return
    rows=list({r.get("event_id"):r for r in rows if r.get("event_id")}.values())
    st.caption(f"{len(rows)} records on this page")
    st.subheader("Mapped and unmapped evidence")
    _security_cluster_map(rows)
    for r in rows[:20]:
        with st.container(border=True):
            st.markdown("**"+str(r.get("title") or "Development")+"**")
            st.caption(str(r.get("occurred_at") or "")[:10]+" · "+str(r.get("location_label") or "Unlocated"))
            st.write(str(r.get("narrative") or "")[:500])
            if st.button("Open incident",key="sec_global_"+str(r.get("event_id"))):
                _open(core,"event",r.get("event_id"),r.get("title"))


def render_home(db,core,lens):
    if db is None:
        st.error('Supabase connection unavailable. Check the configured database client.');return
    if lens=='trade':return _trade(db,core)
    if lens=='intelligence':return _security(db,core)
    raise ValueError('Unsupported P&C workspace '+str(lens))
