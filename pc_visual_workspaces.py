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
        try:
            rows = db.table("pc_v_security_hormuz_stories").select("*").limit(100).execute().data or []
        except Exception as exc:
            st.error("The regional intelligence evidence feed is unavailable.")
            with st.expander("Connection details"): st.code(str(exc))
            return
        if not rows:
            st.info("No supported evidence is available for this demonstration.")
            return
        df = pd.DataFrame(rows)
        if "category" not in df.columns: df["category"] = "Other security"
        if "occurred_on" not in df.columns: df["occurred_on"] = None
        df["occurred_on"] = pd.to_datetime(df["occurred_on"], errors="coerce")
        maritime = df[df["category"].eq("Maritime security")].copy()
        infrastructure = df[df["category"].eq("Energy infrastructure")].copy()
        try:
            note = db.table("pc_v_security_editorial_latest").select("*").eq(
                "region_code", "HORMUZ_GULF_OF_OMAN").limit(1).execute().data or []
        except Exception:
            note = []
        summary = note[0] if note else {}
        st.markdown("""
        <style>
        .pc-brief-hero {background:#152D47;color:#f1f5fb;padding:24px 27px;
                        border-radius:12px;margin:10px 0 18px 0}
        .pc-brief-eyebrow {font-size:11px;letter-spacing:1.5px;text-transform:uppercase;color:#9ec0dd}
        .pc-brief-heading {font-size:23px;font-weight:700;margin:9px 0;color:#fff}
        .pc-brief-date {font-size:13px;color:#c7d7e7}
        </style>""",unsafe_allow_html=True)
        st.markdown('<div class="pc-brief-hero"><div class="pc-brief-eyebrow">P&C Intelligence / Regional Security</div>'
                    '<div class="pc-brief-heading">Hormuz and Gulf of Oman</div>'
                    '<div class="pc-brief-date">Maritime security, oil exports and connected infrastructure</div></div>',
                    unsafe_allow_html=True)
        st.caption("REGIONAL INTELLIGENCE BRIEF  ·  Historical evidence and analyst interpretation")
        st.markdown("### Executive assessment")
        st.write(summary.get("executive_summary") or
                 "The selected evidence links attacks affecting merchant shipping with earlier "
                 "disruptions to Fujairah's energy infrastructure. Wider regional incident and "
                 "commercial data are needed to establish the full current threat picture.")
        st.caption("P&C independent editorial analysis · Formal numerical threat rating not yet approved")
        if summary.get("analysis"):
            with st.expander("Why this matters — assessment reasoning"):
                st.write(summary["analysis"])
        st.markdown("#### Evidence at a glance")
        m1,m2,m3=st.columns(3)
        m1.metric("Affected vessel records",len(maritime))
        m2.metric("Fujairah observations",len(infrastructure))
        m3.metric("P&C numerical rating","Pending")
        st.caption("Counts refer to the eleven-record validation set; they are not total regional attacks.")
        st.markdown("### Risk and threat assessment")
        st.caption("P&C's independent analyst judgment is shown separately from outside providers.")
        observation = summary.get("observation_label") or "Independent P&C assessment in progress"
        st.markdown("**Independent analysis:** " + str(observation))
        st.caption("Not a calibrated numeric score. The security methodology remains a draft.")
        st.markdown("#### Threat drivers")
        col_a,col_b=st.columns(2)
        with col_a:
            st.markdown("**Maritime attacks and crew safety**")
            st.write("Repeated attacks on identified tankers raise operational concerns for vessels, crews and fleet operators.")
        with col_b:
            st.markdown("**Export infrastructure and redundancy**")
            st.write("Fujairah fires and loading disruptions expose the fragility of alternatives to Strait transit.")
        st.markdown("### Key developments")
        sections = (
            ("Maritime security","Merchant shipping",
             "Repeated vessel incidents bring crew safety, vessel availability and exposure of connected fleets into focus.",maritime),
            ("Energy infrastructure","Fujairah and alternative export routes",
             "Disruption at Fujairah threatens operations outside the Strait and can reduce supply-chain resilience.",infrastructure),
        )
        for kind,heading,interpretation,part in sections:
            with st.container(border=True):
                st.markdown("#### "+heading)
                st.write(interpretation)
                if not part.empty:
                    latest = part.sort_values("occurred_on",ascending=False).iloc[0]
                    st.caption("Most recent case-study record: "+str(latest.get("headline") or kind)
                               +" · "+str(latest["occurred_on"].date()) if pd.notna(latest["occurred_on"]) else str(latest.get("headline") or kind))
                st.caption(str(len(part))+" selected evidence records; open the chronology for details")
        st.markdown("### Historical pattern")
        timeline=df.dropna(subset=["occurred_on"]).copy()
        if not timeline.empty:
            timeline["Month"]=timeline["occurred_on"].dt.strftime("%b %Y")
            chart=timeline.groupby(["Month","category"]).size().unstack(fill_value=0)
            st.bar_chart(chart,y_label="Evidence records")
        st.caption("Recorded observations by month, not a calibrated risk index.")
        with st.expander("Incident chronology and sources",expanded=False):
            category=st.selectbox("Evidence category",["All","Maritime security","Energy infrastructure"],
                                  key="pc_sec_case_category")
            visible=df if category=="All" else df[df["category"]==category]
            for _,r in visible.sort_values("occurred_on",ascending=False).iterrows():
                with st.container(border=True):
                    st.markdown("**"+str(r.get("headline") or "Regional incident")+"**")
                    date=r.get("occurred_on")
                    st.caption((date.strftime("%d %b %Y") if pd.notna(date) else "Date under review")
                               +" · "+str(r.get("geographical_area") or "Regional location")
                               +" · "+str(r.get("category") or "Security"))
                    effect=str(r.get("operational_effect") or "")
                    if effect and effect.lower() not in ("nan","none"):
                        st.write(effect)
                    else:
                        st.write("Consequences remain under investigation.")
                    source=r.get("supporting_source")
                    if isinstance(source,str) and source.startswith(("https://","http://")):
                        st.link_button("View source",source)
                    with st.expander("Underlying evidence"):
                        st.write("Vessel: "+str(r.get("vessel") or "Not identified"))
                        st.write("Associated company: "+str(r.get("company") or "Not yet linked"))
                        event_id = r.get("event_id")
                        if event_id and st.button("Open full incident dossier",
                                                 key="pc_sec_dossier_"+str(event_id)):
                            _open(core,"event",event_id,r.get("headline") or "Incident")
                        imo = str(r.get("imo") or "").strip()
                        if imo and imo.lower() not in ("none","nan"):
                            if st.button("Open vessel dossier",key="pc_sec_vessel_"+str(event_id)):
                                try:
                                    matches=db.table("pc_mobile_assets").select(
                                        "mobile_asset_id,name").eq("imo",imo).limit(1).execute().data or []
                                    if matches:
                                        _open(core,"mobile_asset",matches[0]["mobile_asset_id"],
                                              matches[0].get("name") or imo)
                                    else:st.warning("No canonical vessel matches the recorded IMO.")
                                except Exception as exc:st.warning("Vessel lookup failed: "+str(exc))
                        st.caption("Evidence reference: "+str(event_id or ""))
        st.markdown("### Monitoring priorities")
        st.write("Watch for new maritime attacks, verified transit restrictions, interruptions to Fujairah oil "
                 "loading, changes to alternative export routes, and confirmed commercial or insurance consequences.")
        st.caption("These monitoring priorities are analyst prompts, not automatically met escalation thresholds.")
        st.info("Incident positions are not plotted as exact strike locations unless supported by verified coordinates. A regional infrastructure/corridor map is a separate development task.")
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
