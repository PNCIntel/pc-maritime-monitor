"""Live, read-only shipping network. Uses all existing service records, including two-stop routes."""
from __future__ import annotations
import pandas as pd
import streamlit as st

def _pages(db, table, fields, order=None, page_size=1000, max_pages=30):
    rows=[]
    for i in range(max_pages):
        q=db.table(table).select(fields)
        if order: q=q.order(order)
        batch=q.range(i*page_size,(i+1)*page_size-1).execute().data or []
        rows.extend(batch)
        if len(batch)<page_size: break
    return rows, len(batch)==page_size and i==max_pages-1

def _port_coordinates(db, ids):
    # Existing Trade delivery view supplies coordinates; never invent missing locations.
    points={}
    for offset in range(0,len(ids),100):
        batch=db.table('pc_app_trade_records').select('object_id,name,latitude,longitude').in_('object_id',ids[offset:offset+100]).execute().data or []
        for p in batch:
            try:
                lat=float(p['latitude']); lon=float(p['longitude'])
                if -90<=lat<=90 and -180<=lon<=180: points[p['object_id']]=(lat,lon,p['name'])
            except (ValueError,TypeError,KeyError): pass
    return points

def render(db):
    st.subheader('Shipping Network')
    st.caption('Global, live database services. Lines connect consecutive published stops only; they are not AIS tracks or evidence of completed voyages.')
    try:
        services,truncated=_pages(db,'pc_transport_services','transport_service_id,service_code,primary_operator_entity_id,status,record_status,frequency_value,frequency_unit,effective_start,effective_end')
        stops,stops_truncated=_pages(db,'pc_transport_service_stops','transport_service_id,sequence_no,asset_id,direction,valid_from,valid_to',order='sequence_no')
    except Exception as exc:
        st.error('Shipping network data unavailable. Confirm the existing service tables and read permissions.')
        with st.expander('Technical details'): st.code(str(exc))
        return
    if truncated or stops_truncated: st.warning('Result safety limit reached: network may be incomplete; increase pagination before treating this as full coverage.')
    if not services:
        st.info('No shipping services returned by current database permissions.')
        return
    operators=sorted({str(s.get('primary_operator_entity_id')) for s in services if s.get('primary_operator_entity_id')})
    op=st.selectbox('Company / operator',['All operators']+operators)
    status=st.selectbox('Operational status',['All statuses']+sorted({str(s.get('status')) for s in services if s.get('status')}))
    needle=st.text_input('Find service code',placeholder='KIX1, SIX, or any existing service')
    selected=[s for s in services if (op=='All operators' or s.get('primary_operator_entity_id')==op) and (status=='All statuses' or s.get('status')==status) and (not needle or needle.lower() in str(s.get('service_code') or '').lower())]
    service_ids={s['transport_service_id'] for s in selected}
    filtered=[p for p in stops if p['transport_service_id'] in service_ids]
    grouped={}
    for p in filtered: grouped.setdefault(p['transport_service_id'],[]).append(p)
    st.caption(f'{len(selected)} matching services; {sum(len(v)>=2 for v in grouped.values())} have at least two linked stops. Two-point routes are included.')
    labels={f"{s.get('service_code') or s['transport_service_id']} · {s.get('primary_operator_entity_id') or 'Operator not linked'} · {s.get('status') or 'Status unspecified'}":s for s in selected}
    choice=st.selectbox('Inspect a service',['Select a service…']+list(labels))
    if choice not in labels:
        st.dataframe(pd.DataFrame(selected),hide_index=True,use_container_width=True)
        return
    s=labels[choice]; sid=s['transport_service_id']
    ordered=sorted(grouped.get(sid,[]),key=lambda p:(str(p.get('direction') or ''),p.get('sequence_no') or 0))
    st.markdown(f"**{s.get('service_code') or sid}** · {s.get('status') or 'Unspecified'} · {s.get('frequency_value') or 'Frequency not recorded'} {s.get('frequency_unit') or ''}")
    if not ordered:
        st.info('No ordered port calls are linked yet. The service remains discoverable.')
        return
    ids=list(dict.fromkeys(p['asset_id'] for p in ordered if p.get('asset_id')))
    try: coords=_port_coordinates(db,ids)
    except Exception as exc:
        coords={}; st.warning('Port coordinates unavailable: '+str(exc)[:160])
    display=[{'Sequence':p.get('sequence_no'),'Port':coords.get(p.get('asset_id'),(None,None,p.get('asset_id')))[2],'Asset ID':p.get('asset_id'),'Direction':p.get('direction')} for p in ordered]
    st.dataframe(pd.DataFrame(display),hide_index=True,use_container_width=True)
    segments=[]
    # Do not bridge missing coordinates, or connect separate directions.
    for a,b in zip(ordered,ordered[1:]):
        if a.get('direction')!=b.get('direction'): continue
        x=coords.get(a.get('asset_id')); y=coords.get(b.get('asset_id'))
        if x and y: segments.append({'from':x[2],'to':y[2],'start':[x[1],x[0]],'end':[y[1],y[0]]})
    if segments:
        try:
            import pydeck as pdk
            layer=pdk.Layer('LineLayer',segments,get_source_position='start',get_target_position='end',get_width=3,get_color=[39,174,192],pickable=True)
            dots=[{'name':v[2],'position':[v[1],v[0]]} for v in coords.values()]
            points=pdk.Layer('ScatterplotLayer',dots,get_position='position',get_radius=18000,get_fill_color=[250,190,70],pickable=True)
            st.pydeck_chart(pdk.Deck(layers=[layer,points],initial_view_state=pdk.ViewState(latitude=sum(v[0] for v in coords.values())/len(coords),longitude=sum(v[1] for v in coords.values())/len(coords),zoom=2),tooltip={'text':'{name}{from}{to}'}),use_container_width=True)
        except Exception as exc: st.warning('Map renderer unavailable; ordered port table remains available: '+str(exc)[:120])
    else: st.info('A geographic line cannot be drawn until at least two consecutive stops have stored coordinates. No route geometry has been guessed.')
    st.markdown('**Intelligence connections**')
    st.caption('Direct event links to the route\'s ports are shown below. This establishes a linked-port incident, not automatically a confirmed service interruption or vessel casualty.')
    try:
        links=[]
        for offset in range(0,len(ids),100):
            links.extend(db.table('pc_delivery_direct_incidents').select('object_id,event_id,link_source').eq('object_type','asset').in_('object_id',ids[offset:offset+100]).limit(1000).execute().data or [])
        if links: st.dataframe(pd.DataFrame(links).drop_duplicates(),hide_index=True,use_container_width=True)
        else: st.caption('No directly linked port incidents returned. Area-wide corridor exposure requires a separately evidenced geographic relation.')
    except Exception as exc: st.warning('Intelligence connection unavailable: '+str(exc)[:150])
    st.markdown('**Vessel deployments**')
    st.caption('Only evidenced IMO-to-service deployments should appear here. No vessel is assigned merely because it belongs to the same company. The current service schema does not establish a deployment link, so none is inferred.')
