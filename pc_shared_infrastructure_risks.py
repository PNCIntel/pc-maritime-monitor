"""P&C shared security/operational timeline: read-only, asset-graph grounded."""
import streamlit as st

DIRECT={'directly_affected','targeted'}

def _meta(obj):
    return obj.get('metadata') if isinstance(obj.get('metadata'),dict) else {}

def _category(event):
    meta=_meta(event)
    category=str(meta.get('infrastructure_incident_category') or meta.get('intelligence_subcategory') or '').lower()
    typ=str(event.get('event_type') or '').lower()
    blob=(category+' '+typ)
    if any(x in blob for x in ('sanction','designation','compliance')): return 'Sanctions / compliance'
    if any(x in blob for x in ('advisory','notam','restriction','warning','travel_advice')): return 'Restrictions / advisories'
    if any(x in blob for x in ('cargo','flight','aviation_disruption','congestion','service_disruption','booking_suspension','labour')): return 'Trade / operational effects'
    if any(x in blob for x in ('attack','drone','missile','strike','interception','security_incident','sabotage','aerial','explosion')): return 'Attacks / threats'
    return 'Other linked developments'

def _status(event):
    return str(event.get('verification_status') or event.get('status') or 'Not classified')

def _link_detail(core,event_id,asset_id):
    try:
        rows=core._filtered_rows('pc_event_asset_links','event_id',event_id,300)
        return [r for r in rows if str(r.get('asset_id'))==str(asset_id)]
    except Exception: return []

def _specific(link):
    return str(_meta(link).get('specific_relationship') or '').replace('_',' ')

def _scope_label(relationship, scope):
    rel=str(relationship or 'unclassified')
    if scope=='connected': return 'Connected facility — not a direct link to this asset'
    return {'directly_affected':'Directly affected — not necessarily damaged',
      'targeted':'Targeted — strike/impact not automatically established',
      'nearby':'Nearby — no impact implied', 'exposed':'Exposure/context — no damage implied',
      'operator_asset':'Operator connection only', 'origin':'Route origin',
      'destination':'Route destination','route_node':'Route node',
      'other':'Other relationship — impact not inferred'}.get(rel,rel.replace('_',' '))

def render_incident_evidence(core, asset_id, direct, connected, product='intelligence'):
    """Replace legacy flat event lists in existing Risks & Disruptions pane."""
    index={}
    for scope,events in [('direct',direct),('connected',connected)]:
        for event in events:
            eid=str(event.get('event_id') or '')
            if not eid:continue
            if eid not in index or scope=='direct':index[eid]=(event,scope)
    if not index:return
    items=[]
    for eid,(event,scope) in index.items():
        links=_link_detail(core,eid,asset_id) if scope=='direct' else []
        # The resolver can mark a direct event from an indexed relationship even when
        # a current pc_event_asset_links row is absent. Do not claim direct physical damage.
        relation=sorted([str(x.get('relation_type') or '') for x in links],key=lambda x: {'directly_affected':0,'targeted':1,'exposed':2,'nearby':3}.get(x,4))
        primary=relation[0] if relation else ('legacy/indexed direct relation' if scope=='direct' else 'connected facility')
        items.append((event,scope,primary,links))
    items.sort(key=lambda a:str(a[0].get('start_date') or ''),reverse=True)
    st.markdown('#### Dated infrastructure developments')
    st.caption('An event may be linked directly, via a connected facility, or through an exposure record. An event-to-asset link alone never establishes physical damage.')
    f1,f2=st.columns(2)
    choices=['All types']+sorted({_category(x[0]) for x in items})
    cat=f1.selectbox('Development type',choices,key='pc_unified_cat_'+str(asset_id))
    scope_filter=f2.selectbox('Asset relationship',['All relationships','Direct records','Connected facilities'],key='pc_unified_scope_'+str(asset_id))
    for i,(event,scope,relation,links) in enumerate(items):
        kind=_category(event)
        if cat!='All types' and kind!=cat:continue
        if scope_filter=='Direct records' and scope!='direct':continue
        if scope_filter=='Connected facilities' and scope!='connected':continue
        date=str(event.get('start_date') or '')[:10] or 'Undated'
        heading=f'{date}  ·  {kind}  ·  {event.get("title") or event["event_id"]}'
        with st.expander(heading):
            st.caption(_scope_label(relation,scope)+'  ·  Evidence status: '+_status(event))
            details=[_specific(l) for l in links if _specific(l)]
            if details:st.write('Recorded relationship detail: '+'; '.join(dict.fromkeys(details)))
            detail=event.get('description') or event.get('summary') or event.get('operational_impact')
            if detail:st.write(detail)
            if event.get('commercial_impact'):st.write('Recorded commercial impact: '+str(event['commercial_impact']))
            # Preserve reporting qualifiers for GSA Update 10; no live reopening claim.
            u=_meta(event).get('gsa_update10_20261012') or {}
            if isinstance(u,dict) and u:
                if u.get('notam_end_reported_utc'):st.caption('Reported NOTAM expiry: '+str(u['notam_end_reported_utc'])+' — not a confirmed reopening.')
                if u.get('cirium_reported_saudi_cancellations_pct') is not None:st.caption('Reported Saudi-wide scheduled cancellations: '+str(u['cirium_reported_saudi_cancellations_pct'])+'%; not airport-specific.')
            a,b=st.columns(2)
            a.button('Open event dossier',key='pc_u_event_'+str(asset_id)+'_'+str(i),on_click=core._set_context,args=('event',str(event['event_id']),str(event.get('title') or 'Event')))
            urls=core._event_source_urls(event)
            if urls:b.link_button('Source',urls[0])
    st.caption('This is a dated observation timeline, not a real-time operational status feed. Default categories use structured event fields; unclassified records remain visible.')

def render_designated_actor_context(core, asset_id):
    """Only actor relationships explicitly encoded on linked events; no attribution inference."""
    try:
        direct=core._filtered_rows('pc_event_asset_links','asset_id',asset_id,300)
    except Exception:return
    event_ids=sorted({str(r.get('event_id')) for r in direct if r.get('event_id')})
    if not event_ids:return
    evidence=[];seen=set()
    for eid in event_ids[:100]:
        try:roles=core._filtered_rows('pc_event_entity_links','event_id',eid,200)
        except Exception:continue
        for r in roles:
            entity=str(r.get('entity_id') or '')
            if not entity:continue
            key=(eid,entity,str(r.get('role') or ''))
            if key in seen:continue
            seen.add(key)
            evidence.append({'Event':eid,'Actor':core._object_name('entity',entity),
                'Recorded role':str(_meta(r).get('specific_relationship') or r.get('role') or 'Not specified').replace('_',' '),
                'Source ID':str(r.get('source_id') or '')})
    st.markdown('#### Actors in linked developments')
    st.caption('Event participation/attribution is separate from sanctions designation. IRGC, Houthi or any other actor is displayed only if explicitly linked; no guilt-by-association or automatic sanction status.')
    if evidence:
        import pandas as pd
        st.dataframe(pd.DataFrame(evidence),hide_index=True,use_container_width=True)
    else:st.info('No explicitly linked actors have been recorded for these infrastructure events.')
    st.caption('Check legal designation, jurisdiction, effective date, designated legal identity and ownership/control relationships separately in the sanctions tables.')
