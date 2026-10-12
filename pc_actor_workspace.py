"""Actor directory, activity and networks for the current intelligence terminal."""
from __future__ import annotations
import datetime as dt
import math
import re
import pandas as pd
import streamlit as st


def open_actor_workspace(actor_id, core=None):
    if core is None:
        import pc_terminal as core
    keys=('pc_terminal_nav_intelligence','pc_terminal_workspace_intelligence','pc_terminal_search_intelligence','pc_terminal_type','pc_terminal_id','pc_terminal_name')
    st.session_state['pc_actor_return']={k:st.session_state.get(k) for k in keys}
    core._clear_context()
    st.session_state['pc_actor_requested']=str(actor_id)
    st.session_state['pc_terminal_nav_intelligence']='Actors & Networks'
    st.session_state['pc_terminal_workspace_intelligence']='__actors__'
    st.session_state['pc_document_browser']=False
    st.session_state['pc_uae_ofac_overlap']=False
    st.rerun()


def _pages(db,table,**kwargs):
    from pc_visual_workspaces import _load
    rows=[]
    for offset in range(0,10000,500):
        chunk,error=_load(db,table,limit=500,offset=offset,**kwargs)
        if error:return [],error,False
        rows.extend(chunk)
        if len(chunk)<500:return rows,None,False
    return rows,None,True


def _display(value, default='Not recorded'):
    if value is None:return default
    text=str(value).strip()
    return default if text.lower() in ('', 'none', 'nan', 'nat', 'null') else text


def _date_label(value):
    stamp=pd.to_datetime(value,utc=True,errors='coerce')
    return 'Date not recorded' if pd.isna(stamp) else stamp.tz_convert('Asia/Dubai').strftime('%d %b %Y')


def _role_label(value):
    return {'referenced_actor':'Mentioned in report','attributed_actor':'Attributed by source','confirmed_actor':'Confirmed involvement',
            'claimant':'Claimed involvement','reporting_authority':'Reporting authority'}.get(value,str(value or 'Role not recorded').replace('_',' ').capitalize())


def _attribution_label(value):
    return {'associated':'Contextual association','context_only':'Context only','claimed':'Claimed','assessed':'Assessed','confirmed':'Confirmed',
            'unknown':'Unresolved','disputed':'Disputed'}.get(value,str(value or 'Unresolved').replace('_',' ').capitalize())


def _exposure_domains(db,events):
    from pc_visual_workspaces import _load
    ids=[e['event_id'] for e in events];links=[];vessel_events=set()
    for offset in range(0,len(ids),100):
        batch=ids[offset:offset+100]
        rows,err=_load(db,'pc_event_asset_links',filters=(('event_id','in',batch),),limit=500)
        if not err:links.extend(rows)
        vessels,err=_load(db,'pc_v_event_vessel_links',filters=(('event_id','in',batch),),limit=500)
        if not err:vessel_events.update(v['event_id'] for v in vessels if v.get('event_id'))
    asset_ids=sorted({l['asset_id'] for l in links if l.get('asset_id')});assets={}
    for offset in range(0,len(asset_ids),100):
        rows,err=_load(db,'pc_assets',columns='asset_id,asset_type',filters=(('asset_id','in',asset_ids[offset:offset+100]),),limit=100)
        if not err:assets.update({a['asset_id']:a for a in rows})
    port_terminals=set()
    for offset in range(0,len(asset_ids),100):
        rows,err=_load(db,'pc_terminal_details',columns='asset_id,parent_port_asset_id',filters=(('asset_id','in',asset_ids[offset:offset+100]),),limit=100)
        if not err:port_terminals.update(r['asset_id'] for r in rows if r.get('parent_port_asset_id'))
    domains={}
    for link in links:
        typ=str(assets.get(link.get('asset_id'),{}).get('asset_type') or '').lower()
        if re.search(r'airport|air_base|airfield|aerodrome',typ):domain='Air'
        elif (re.search(r'port|maritime|marine|container_terminal',typ) or link.get('asset_id') in port_terminals) and not re.search(r'airport|rail|pipeline|bus|road|dry_port',typ):domain='Maritime'
        elif re.search(r'refinery|pipeline|pumping|oil|gas|energy|industrial|road|rail|land|logistics|dry_port',typ):domain='Land'
        else:continue
        domains.setdefault(link['event_id'],set()).add(domain)
    for eid in vessel_events:domains.setdefault(eid,set()).add('Maritime')
    for event in events:
        d=domains.get(event['event_id'],set())
        if d:event['_linked_domain']=next(iter(d)) if len(d)==1 else 'Multimodal'
    return events


def _mode(event):
    value=str(event.get('mode') or '').lower().strip()
    if value in ('maritime','marine','sea','shipping'):return 'Maritime'
    if value in ('air','aviation','air_transport'):return 'Air'
    if value in ('land','road','rail','ground','land_transport'):return 'Land'
    if event.get('_linked_domain'):return event['_linked_domain']
    if value in ('multimodal','multi_modal'):return 'Multimodal'
    return 'Not specified'


def _attack_report(event):
    # A report classification, never a claim that this actor is a confirmed perpetrator.
    meta=event.get('metadata') or {}
    kind=str(event.get('event_type') or '').lower()
    if event.get('parent_event_id') is None and meta.get('briefing'):return False
    if str(meta.get('status') or '').lower()=='scheduled':return False
    if re.search(r'advisory|warning|assessment|notice|restriction|construction|closure|briefing',kind):return False
    return bool(re.search(r'\b(attack|attacks|attacked|airstrike|bombing|missile strike|drone strike)\b',str(event.get('title') or '').lower()+' '+kind))


def _activity_frame(events,links):
    by_event={}
    for link in links:by_event.setdefault(link['event_id'],[]).append(link)
    rows=[]
    for event in events:
        if event['event_id'] not in by_event:continue
        ls=by_event[event['event_id']]
        rows.append({**event,'_date':pd.to_datetime(event.get('start_date'),utc=True,errors='coerce'),
            'Domain':_mode(event),'Attack-related report':_attack_report(event),
            'Roles':', '.join(sorted({_role_label(l.get('actor_role')) for l in ls})),
            'Attribution':', '.join(sorted({str(l.get('attribution_status') or 'unknown') for l in ls}))})
    return pd.DataFrame(rows)


def _connected_relationships(rows,actor_id,steps=2):
    nodes={str(actor_id)}
    for _ in range(steps):
        neighbours=set(nodes)
        for r in rows:
            a=str(r['from_actor_id']);b=str(r['to_actor_id'])
            if a in nodes or b in nodes:neighbours.update((a,b))
        nodes=neighbours
    return [r for r in rows if str(r['from_actor_id']) in nodes and str(r['to_actor_id']) in nodes]


def _network(rows,actor_id):
    """Force layout of recorded actor relationships; unknown relationships aren't added."""
    import altair as alt
    names={}
    for row in rows:
        names[str(row['from_actor_id'])]=row.get('from_actor_name') or 'Name unavailable'
        names[str(row['to_actor_id'])]=row.get('to_actor_name') or 'Name unavailable'
    keys=sorted(names);n=len(keys)
    pos={key:[math.cos(i*2*math.pi/max(n,1))*200,math.sin(i*2*math.pi/max(n,1))*200] for i,key in enumerate(keys)}
    for _ in range(100):
        force={key:[0.,0.] for key in keys}
        for i,a in enumerate(keys):
            for b in keys[i+1:]:
                dx=pos[a][0]-pos[b][0];dy=pos[a][1]-pos[b][1];d2=max(dx*dx+dy*dy,16);f=2500/d2
                force[a][0]+=dx*f;force[a][1]+=dy*f;force[b][0]-=dx*f;force[b][1]-=dy*f
        for r in rows:
            a=str(r['from_actor_id']);b=str(r['to_actor_id']);dx=pos[b][0]-pos[a][0];dy=pos[b][1]-pos[a][1]
            force[a][0]+=dx*.018;force[a][1]+=dy*.018;force[b][0]-=dx*.018;force[b][1]-=dy*.018
        for key in keys:
            for axis in (0,1):pos[key][axis]+=max(-5,min(5,force[key][axis]-pos[key][axis]*.003))
    edges=pd.DataFrame([{'x':pos[str(r['from_actor_id'])][0],'y':pos[str(r['from_actor_id'])][1],'x2':pos[str(r['to_actor_id'])][0],'y2':pos[str(r['to_actor_id'])][1],
        'From':r.get('from_actor_name'),'To':r.get('to_actor_name'),'Relationship':r.get('relationship_type'),'Confidence':r.get('confidence')} for r in rows])
    nodes=pd.DataFrame([{'x':pos[k][0],'y':pos[k][1],'Actor':names[k],'Selected':k==str(actor_id)} for k in keys])
    line=alt.Chart(edges).mark_rule(color='#718096').encode(x=alt.X('x:Q',axis=None),y=alt.Y('y:Q',axis=None),x2='x2:Q',y2='y2:Q',tooltip=['From','Relationship','To','Confidence'])
    dots=alt.Chart(nodes).mark_circle(size=350).encode(x='x:Q',y='y:Q',color=alt.condition('datum.Selected',alt.value('#b7791f'),alt.value('#3182ce')),tooltip=['Actor'])
    labels=alt.Chart(nodes).mark_text(dy=-16).encode(x='x:Q',y='y:Q',text='Actor:N')
    st.altair_chart((line+dots+labels).properties(height=420).interactive(),use_container_width=True)
    st.caption('Recorded relationships only. Read the connections below for direction, dates and evidence. A shared supporter does not establish an alliance between groups.')


def render_actor_workspace(db,core):
    from pc_visual_workspaces import _load
    st.title('Actors & Networks')
    st.caption('Who they are, where their activity appears, and the relationships supported by our sources.')
    saved=st.session_state.get('pc_actor_return')
    if saved and st.button('← Back to briefing',key='pc_actor_return_button'):
        core._clear_context()
        for k,v in saved.items():
            if v is None:st.session_state.pop(k,None)
            else:st.session_state[k]=v
        if saved.get('pc_terminal_type') and saved.get('pc_terminal_id'):
            core._set_context(saved['pc_terminal_type'],saved['pc_terminal_id'],saved.get('pc_terminal_name'))
        st.session_state.pop('pc_actor_return',None);st.rerun()
    actors,error,truncated=_pages(db,'pc_v_intelligence_actor_directory',order=(('canonical_name',False),))
    if error:
        delivered,error,truncated=_pages(db,'pc_v_intelligence_actor_details',order=(('event_actor_link_id',False),))
        actors=list({r['actor_id']:r for r in delivered}.values())
        st.caption('Showing actors linked to published intelligence. The Actors & Networks SQL enables the full directory, relationships and designations.')
    if error:st.error('Actor profiles could not be loaded.');return
    if not actors:st.info('No readable actor profiles are available.');return
    if truncated:st.warning('The directory is limited to the first 10,000 readable records.')
    query=st.text_input('Find an actor',placeholder='Houthis, Ansar Allah, Saudi Armed Forces…',key='pc_actor_search')
    classes=['All']+sorted({str(a.get('actor_class')) for a in actors if a.get('actor_class')})
    actor_class=st.selectbox('Actor class',classes,format_func=lambda value:value.replace('_',' ').title(),key='pc_actor_class')
    candidates=[a for a in actors if (actor_class=='All' or a.get('actor_class')==actor_class) and (not query.strip() or query.lower().strip() in ' '.join([str(a.get('canonical_name') or ''),str(a.get('short_name') or ''),' '.join(a.get('aliases') or [])]).lower())]
    request=st.session_state.pop('pc_actor_requested',None)
    if request:
        candidate=next((a for a in actors if str(a['actor_id'])==request),None)
        if candidate and candidate not in candidates:
            st.info('The actor linked from the briefing is included below despite the directory filters.');candidates.append(candidate)
    choices={str(a['actor_id']):a for a in sorted(candidates,key=lambda a:str(a.get('canonical_name') or ''))}
    if not choices:st.info('No actors match your filters.');return
    if request in choices:st.session_state['pc_actor_selected']=request
    elif st.session_state.get('pc_actor_selected') not in choices:st.session_state['pc_actor_selected']=next(iter(choices))
    selected=st.selectbox('Actor profile',list(choices),format_func=lambda k:str(choices[k].get('canonical_name')),key='pc_actor_selected')
    actor=choices[selected]
    st.subheader(actor.get('canonical_name') or 'Actor')
    st.caption(' · '.join(str(actor.get(k)).replace('_',' ') for k in ('actor_class','actor_subtype','primary_country') if actor.get(k)))
    if actor.get('description'):st.write(actor['description'])
    if actor.get('aliases'):st.write('Also known as: '+', '.join(actor['aliases']))
    links,error,limited=_pages(db,'pc_v_intelligence_actor_details',filters=(('actor_id','eq',selected),),order=(('event_actor_link_id',False),))
    if error:st.warning('Linked event activity could not be read.');links=[]
    event_ids=sorted({l['event_id'] for l in links});events=[]
    for start in range(0,len(event_ids),100):
        rows,err=_load(db,'pc_events',filters=(('event_id','in',event_ids[start:start+100]),),limit=100)
        if err:st.warning('Some event details could not be loaded.');continue
        events.extend(rows)
    events=_exposure_domains(db,events)
    activity=_activity_frame(events,links)
    if not activity.empty:activity=activity.sort_values('_date',ascending=False,na_position='last')
    profile,charts,network,designations=st.tabs(['Profile & events','Activity & domains','Network','Designations'])
    with profile:
        x,y=st.columns(2)
        x.metric('Reports in our coverage',len(activity))
        latest=activity['_date'].max() if not activity.empty else None
        y.metric('Latest report',_date_label(latest) if latest is not None else 'No dated reports')
        st.caption('A mention or contextual association does not establish responsibility for an incident.')
        if not activity.empty:
            st.subheader('Recent developments')
            for _,event_row in activity.head(6).iterrows():
                with st.container(border=True):
                    st.markdown('**'+_display(event_row.get('title'),'Untitled report')+'**')
                    st.caption(_date_label(event_row.get('start_date'))+' · '+_display(event_row.get('Domain'),'Not specified')+' exposure')
                    if _display(event_row.get('description'),''):st.write(event_row['description'])
                    if _display(event_row.get('operational_impact'),''):st.markdown('**Why it matters:** '+str(event_row['operational_impact']))
                    attributions=', '.join(_attribution_label(v.strip()) for v in str(event_row.get('Attribution') or '').split(',') if v.strip())
                    st.caption('Actor connection: '+_display(event_row.get('Roles'))+' · '+attributions)
                    meta=event_row.get('metadata') or {};url=meta.get('source_url')
                    if isinstance(url,str) and url.startswith(('http://','https://')):st.link_button('Read source',url)
            with st.expander('All reports — dates and attribution'):
                table=pd.DataFrame([{'Date':_date_label(e.get('start_date')),'Report':_display(e.get('title')),
                    'Exposure':_display(e.get('Domain')),'Connection':_display(e.get('Roles')),
                    'Attribution':', '.join(_attribution_label(v.strip()) for v in str(e.get('Attribution') or '').split(',') if v.strip())}
                    for _,e in activity.iterrows()])
                st.dataframe(table,hide_index=True,use_container_width=True)
            options={e['event_id']:e for e in events}
            event=st.selectbox('Explore an event',list(options),format_func=lambda k:str(options[k].get('title')),key='pc_actor_event_'+selected)
            if st.button('Open event dossier',key='pc_actor_event_open'):
                st.session_state['pc_terminal_workspace_intelligence']='';core._set_context('event',event,options[event].get('title'));st.rerun()
        else:st.info('No readable published event activity for this actor.')
    with charts:
        a,b,c=st.columns(3)
        coverage=a.selectbox('Reports to chart',['All linked reports','Attack-related reports'],key='pc_actor_chart_scope')
        attribution=b.selectbox('Attribution',['All','confirmed','claimed','assessed','associated','context_only','disputed','unknown'],format_func=lambda value:'All' if value=='All' else _attribution_label(value),key='pc_actor_chart_attribution')
        period=c.selectbox('Period',['All history','Last 12 months','Last 30 days','Last 14 days'],key='pc_actor_chart_period')
        work=activity.copy()
        if not work.empty:
            if coverage=='Attack-related reports':work=work[work['Attack-related report']]
            if attribution!='All':
                allowed={l['event_id'] for l in links if l.get('attribution_status')==attribution};work=work[work['event_id'].isin(allowed)]
            if period!='All history':
                days={'Last 12 months':365,'Last 30 days':30,'Last 14 days':14}[period];work=work[work['_date']>=pd.Timestamp.now(tz='UTC')-pd.Timedelta(days=days)]
            work=work[work['_date']<=pd.Timestamp.now(tz='UTC')]
        st.caption('Counts are distinct published reports, not independently verified attacks. Claims and contextual associations retain their recorded attribution. Domains describe operating exposure, using the recorded transport mode or connected facility/vessel type. They do not describe the weapon used; absent data stays unspecified.')
        if work.empty:st.info('No dated reports match these chart filters.')
        else:
            dated=work.dropna(subset=['_date']).copy()
            if not dated.empty:
                dated['Date']=dated['_date'].dt.tz_convert('Asia/Dubai').dt.tz_localize(None).dt.to_period('M' if period in ('All history','Last 12 months') else 'D').dt.to_timestamp()
                series=dated.groupby(['Date','Domain']).event_id.nunique().unstack(fill_value=0)
                st.subheader('Reports over time');st.bar_chart(series)
            st.subheader('Maritime, land, air and other domains')
            st.bar_chart(work.groupby('Domain').event_id.nunique().rename('Reports'))
            st.subheader('Attribution in the selected reports')
            kept=set(work.event_id);atr=pd.DataFrame([l for l in links if l['event_id'] in kept])
            atr['Attribution']=atr['attribution_status'].map(_attribution_label)
            st.bar_chart(atr.groupby('Attribution').event_id.nunique().rename('Reports'))
    with network:
        rows,err,cap=_pages(db,'pc_v_intelligence_actor_relationships',order=(('actor_relationship_id',False),))
        scope=st.selectbox('Network reach',['Connected network — two steps','Direct relationships only'],key='pc_actor_network_reach')
        rows=_connected_relationships(rows,selected,2 if scope.startswith('Connected') else 1)
        if err:st.info('Run the Actors & Networks SQL to enable recorded network relationships.')
        elif not rows:st.info('No structured relationships are recorded for this actor. Shared event references are not treated as alliances.')
        else:
            try:_network(rows[:100],selected)
            except ImportError:st.caption('Graph rendering unavailable; recorded relationships are shown below.')
            if len(rows)>100 or cap:st.caption('Graph shows up to 100 relationships; the table preserves the loaded relationship records.')
            for relation in rows:
                with st.expander(_display(relation.get('from_actor_name'))+' → '+_display(relation.get('to_actor_name'))):
                    st.write(_display(relation.get('relationship_type')).replace('_',' ').capitalize())
                    st.write(_display(relation.get('basis')))
                    st.caption('Evidence as of '+_display(relation.get('source_as_of'),_date_label(relation.get('source_published_at')))+' · Source confidence: '+_display(relation.get('confidence')))
                    url=relation.get('source_url')
                    if isinstance(url,str) and url.startswith(('http://','https://')):st.link_button('Read relationship source',url)
    with designations:
        rows,err,cap=_pages(db,'pc_v_intelligence_actor_designations',filters=(('actor_id','eq',selected),),order=(('actor_designation_id',False),))
        if err:st.info('Run the Actors & Networks SQL to enable structured designation records.')
        elif not rows:st.caption('No structured designations are recorded for this actor.')
        else:
            for designation in rows:
                with st.container(border=True):
                    st.markdown('**'+_display(designation.get('authority'))+' · '+_display(designation.get('designation_name'))+'**')
                    label=designation.get('effective_date_label')
                    if label and re.fullmatch(r'\d{4}-\d{2}-\d{2}',str(label)):label=_date_label(label)
                    st.caption('Effective: '+_display(label,_date_label(designation.get('effective_date')))+' · '+_display(designation.get('programme')))
                    if designation.get('end_date'):st.caption('Ended: '+_date_label(designation['end_date']))
                    if designation.get('notes'):st.write(designation['notes'])
                    if designation.get('current_status_requires_refresh'):st.caption('Designation history; current legal status has not been independently refreshed.')
                    else:st.caption('Record status: '+_display(designation.get('status')).replace('_',' '))
                    url=designation.get('source_url')
                    if isinstance(url,str) and url.startswith(('http://','https://')):st.link_button('Read issuing authority’s source',url)
