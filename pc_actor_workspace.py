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


def _mode(event):
    value=str(event.get('mode') or '').lower().strip()
    if value in ('maritime','marine','sea','shipping'):return 'Maritime'
    if value in ('air','aviation','air_transport'):return 'Air'
    if value in ('land','road','rail','ground','land_transport'):return 'Land'
    if value in ('multimodal','multi_modal'):return 'Multimodal'
    return 'Unclassified'


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
            'Roles':', '.join(sorted({str(l.get('actor_role') or '').replace('_',' ') for l in ls})),
            'Attribution':', '.join(sorted({str(l.get('attribution_status') or 'unknown') for l in ls}))})
    return pd.DataFrame(rows)


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
    st.caption('Recorded relationships only. Edge direction and evidence appear in the table below.')


def render_actor_workspace(db,core):
    from pc_visual_workspaces import _load
    st.title('Actors & Networks')
    st.caption('Explore actor profiles, activity over time, operating domains and recorded relationships.')
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
    actor_class=st.selectbox('Actor class',classes,key='pc_actor_class')
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
    activity=_activity_frame(events,links)
    profile,charts,network,designations=st.tabs(['Profile & events','Activity & domains','Network','Designations'])
    with profile:
        x,y=st.columns(2);x.metric('Published linked events',len(activity));y.metric('Recorded actor roles',len({l.get('actor_role') for l in links}))
        st.caption('Referenced and associated actors are not automatically confirmed perpetrators.')
        if not activity.empty:
            st.dataframe(activity.rename(columns={'start_date':'Date','title':'Event','operational_impact':'Consequence'})[['Date','Event','Domain','Roles','Attribution','Consequence']],hide_index=True,use_container_width=True)
            options={e['event_id']:e for e in events}
            event=st.selectbox('Explore an event',list(options),format_func=lambda k:str(options[k].get('title')),key='pc_actor_event_'+selected)
            if st.button('Open event dossier',key='pc_actor_event_open'):
                st.session_state['pc_terminal_workspace_intelligence']='';core._set_context('event',event,options[event].get('title'));st.rerun()
        else:st.info('No readable published event activity for this actor.')
    with charts:
        a,b,c=st.columns(3)
        coverage=a.selectbox('Reports to chart',['All linked reports','Attack-related reports'],key='pc_actor_chart_scope')
        attribution=b.selectbox('Attribution',['All','confirmed','claimed','assessed','associated','context_only','disputed','unknown'],key='pc_actor_chart_attribution')
        period=c.selectbox('Period',['All history','Last 12 months','Last 30 days','Last 14 days'],key='pc_actor_chart_period')
        work=activity.copy()
        if not work.empty:
            if coverage=='Attack-related reports':work=work[work['Attack-related report']]
            if attribution!='All':
                allowed={l['event_id'] for l in links if l.get('attribution_status')==attribution};work=work[work['event_id'].isin(allowed)]
            if period!='All history':
                days={'Last 12 months':365,'Last 30 days':30,'Last 14 days':14}[period];work=work[work['_date']>=pd.Timestamp.now(tz='UTC')-pd.Timedelta(days=days)]
            work=work[work['_date']<=pd.Timestamp.now(tz='UTC')]
        st.caption('Counts are distinct published reports, not independently verified attacks. Claims and contextual associations retain their recorded attribution. Domains come from stored transport mode; missing mode stays unclassified.')
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
            st.bar_chart(atr.groupby('attribution_status').event_id.nunique().rename('Reports'))
    with network:
        rows,err,cap=_pages(db,'pc_v_intelligence_actor_relationships',order=(('actor_relationship_id',False),))
        rows=[r for r in rows if str(r.get('from_actor_id'))==selected or str(r.get('to_actor_id'))==selected]
        if err:st.info('Run the Actors & Networks SQL to enable recorded network relationships.')
        elif not rows:st.info('No structured relationships are recorded for this actor. Shared event references are not treated as alliances.')
        else:
            try:_network(rows[:100],selected)
            except ImportError:st.caption('Graph rendering unavailable; recorded relationships are shown below.')
            if len(rows)>100 or cap:st.caption('Graph shows up to 100 relationships; the table preserves the loaded relationship records.')
            st.dataframe(pd.DataFrame([{'From':r.get('from_actor_name'),'Relationship':r.get('relationship_type'),'To':r.get('to_actor_name'),'Status':r.get('status'),'Confidence':r.get('confidence'),'Basis':r.get('basis')} for r in rows]),hide_index=True,use_container_width=True)
    with designations:
        rows,err,cap=_pages(db,'pc_v_intelligence_actor_designations',filters=(('actor_id','eq',selected),),order=(('actor_designation_id',False),))
        if err:st.info('Run the Actors & Networks SQL to enable structured designation records.')
        elif not rows:st.caption('No structured designations are recorded for this actor.')
        else:
            st.dataframe(pd.DataFrame(rows)[['authority','designation_name','programme','effective_date','end_date','status','confidence']],hide_index=True,use_container_width=True)
            st.caption('Recorded designation status and dates; check the issuing authority for current legal applicability.')
            for url in dict.fromkeys(r.get('source_url') for r in rows if str(r.get('source_url') or '').startswith(('https://','http://'))):st.link_button('Read designation source',url)
