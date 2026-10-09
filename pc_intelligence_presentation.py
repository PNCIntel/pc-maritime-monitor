"""Customer-facing presentation of PostgreSQL intelligence delivery views.

Read-only; no implied risk ratings, positions, sanctions, or regional impacts.
Requires SQL 20261009_intelligence_layer.sql.
"""
from __future__ import annotations
import pandas as pd
import streamlit as st


def _query(db, table: str, columns='*', *, eq=None, limit=150, order=None):
    if db is None:
        return [], 'Database unavailable'
    try:
        q=db.table(table).select(columns)
        for key, val in (eq or {}).items():
            q=q.eq(key, val)
        if order:
            q=q.order(order,desc=True)
        return q.limit(limit).execute().data or [],None
    except Exception as exc:
        return [], str(exc)


def _number(v):
    try:
        n=float(v)
        return n if -180<=n<=180 else None
    except (TypeError,ValueError):
        return None


def _map(rows, *, latitude='latitude', longitude='longitude', label='title'):
    points=[]
    for r in rows:
        lat=_number(r.get(latitude));lon=_number(r.get(longitude))
        if lat is None or lon is None or not -90<=lat<=90:
            continue
        points.append({'lat':lat,'lon':lon,'name':r.get(label,'')})
    if points:
        st.map(pd.DataFrame(points),latitude='lat',longitude='lon',use_container_width=True)
        st.caption(f'{len(points)} mapped records with stored coordinates; unmapped records remain accessible below.')
    else:
        st.caption('No verified coordinates available for the selected records.')


def render_market_highlights(db, product):
    """Supplement existing home; never replace its established maps and navigation."""
    if product not in ('trade','intelligence'):
        return
    with st.expander('Latest verified-data picture', expanded=False):
        if product == 'intelligence':
            data,err=_query(db,'pc_intel_security_picture',
                'event_id,title,event_type,event_family,occurred_at,recorded_severity,source_risk_level,source_risk_trend,latitude_text,longitude_text',
                order='occurred_at',limit=180)
            if err:
                st.warning('Current intelligence picture unavailable; the previous operating picture remains accessible.')
                return
            if not data:
                st.info('No published events found in this view.')
                return
            family=sorted({str(r.get('event_family') or 'Other') for r in data})
            selected=st.multiselect('Incident categories',family,default=family,key='pc_intel_family_filter')
            show=[r for r in data if str(r.get('event_family') or 'Other') in selected]
            _map(show,latitude='latitude_text',longitude='longitude_text')
            for row in show[:12]:
                when=str(row.get('occurred_at') or '')[:10]
                st.markdown(f"**{row.get('title') or 'Development'}** · {when}")
                details=[row.get('event_type'),row.get('source_risk_level'),row.get('source_risk_trend')]
                st.caption(' · '.join(str(x).replace('_',' ') for x in details if x))
        else:
            data,err=_query(db,'pc_intel_trade_picture',
                'object_id,name,section,category,country,latitude,longitude',limit=750)
            if err:
                st.warning('Infrastructure delivery view unavailable; existing maps and profiles are unaffected.')
                return
            choices=sorted({r.get('section') for r in data if r.get('section')})
            selected=st.multiselect('Infrastructure and activity',choices,default=choices,key='pc_trade_map_types')
            selected_rows=[r for r in data if r.get('section') in selected]
            _map(selected_rows,label='name')


def render_event_profile(db, event_id: str, product: str) -> bool:
    """Full-width event briefing; relationship/evidence details are opt-in."""
    rows, err = _query(db, "pc_intel_event_details", eq={"event_id": event_id}, limit=1)
    if err or not rows:
        return False
    e = rows[0]
    title = str(e.get("title") or "Incident report")
    st.caption("P&C INTELLIGENCE / INCIDENT BRIEF")
    st.title(title)
    occurred = str(e.get("occurred_at") or "")[:10] or "Date under review"
    location = str(e.get("location_label") or "Location under review")
    family = str(e.get("event_family") or "Security development").replace("_", " ").title()
    st.caption(" · ".join([occurred, location, family]))
    narrative = e.get("narrative")
    if narrative:
        st.markdown("### What happened")
        st.write(narrative)
    else:
        st.info("A verified account is not yet available for this record.")

    tabs = st.tabs(["Impact and exposure", "Location and connections", "Sources"])
    with tabs[0]:
        st.markdown("#### Operational significance")
        st.write(e.get("operational_impact") or
                 "Operational effects have not yet been established from recorded evidence.")
        st.markdown("#### Commercial implications")
        st.write(e.get("commercial_impact") or
                 "Commercial consequences remain under review.")
        risk = e.get("source_risk_level")
        trend = e.get("source_risk_trend")
        if risk or trend:
            with st.expander("Attributed external assessment"):
                st.caption("An external source's classification is not an independent P&C threat rating.")
                st.write("Recorded source level: " + str(risk or "Not available"))
                st.write("Recorded source trend: " + str(trend or "Not available"))
        else:
            st.caption("No separately validated P&C incident risk rating is currently linked.")
    with tabs[1]:
        st.markdown("#### Reported geographic context")
        st.write(location)
        _map([e], latitude="latitude_text", longitude="longitude_text")
        st.caption("Mapped points may represent a linked facility rather than a verified strike position.")
        linked, link_error = _query(db, "pc_intel_object_events",
                                   "object_type,object_id,link_sources",
                                   eq={"event_id":event_id},limit=60)
        if linked:
            st.markdown("#### Linked vessels, companies and facilities")
            for ix,x in enumerate(linked):
                kind = str(x.get("object_type") or "").lower()
                identifier = str(x.get("object_id") or "")
                table, id_column, label_column = {
                    "mobile_asset": ("pc_mobile_assets","mobile_asset_id","name"),
                    "entity": ("pc_entities","entity_id","name"),
                    "asset": ("pc_assets","asset_id","name"),
                }.get(kind, (None,None,None))
                if not table or not identifier:
                    continue
                found,_ = _query(db,table,f"{id_column},{label_column}",
                                 eq={id_column:identifier},limit=1)
                display = (found[0].get(label_column) if found else None) or kind.replace("_"," ").title()
                col1,col2 = st.columns([4,1])
                col1.write("**"+str(display)+"** · "+kind.replace("_"," ").title())
                if col2.button("Explore",key=f"event_related_{event_id}_{ix}"):
                    try:
                        from pc_terminal import _set_context
                        _set_context(kind,identifier,str(display))
                        st.rerun()
                    except Exception:
                        st.warning("This linked record could not be opened.")
        elif link_error:
            st.caption("Related-object lookup unavailable.")
        else:
            st.caption("No explicit linked objects in this delivery view.")
    with tabs[2]:
        evidence = e.get("evidence") or []
        if evidence:
            for i, item in enumerate(evidence):
                st.write(item.get("claim") or "Supporting observation")
                source = item.get("url")
                if isinstance(source,str) and source.startswith(("https://","http://")):
                    st.link_button("Open source "+str(i+1),source)
        else:
            st.caption("No evidence rows returned in this view. Check the original incident dossier for further provenance.")
        with st.expander("Technical details"):
            st.caption("Internal canonical reference: "+str(event_id))
    try:
        from pc_event_dual_lens import render_event_lens
        with st.expander("Additional analytical views"):
            render_event_lens(db,event_id,product)
    except ImportError:
        pass
    return True
