"""P&C staff-only connected developments INSIDE the main Trade News/Companies pages.

Reads *existing* v0.7/v0.8 staged graph and analytical content. Never guesses
identity, writes canonical rows, changes RLS, or exposes unpublished work to clients.
Relationships are source-supplied event links, verified canonical endpoints separately
labelled, and unverified corridor mentions explicitly labelled as suggestions.
"""
from __future__ import annotations
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit
import streamlit as st

KEYS = {'pc_entities': 'entity_id', 'pc_assets': 'asset_id', 'pc_mobile_assets': 'mobile_asset_id',
        'pc_trade_corridors': 'corridor_key', 'pc_events': 'event_id',
        'pc_transport_routes': 'route_id', 'pc_transport_services': 'service_id'}
GRAPH_TABLES = {'pc_event_links', 'pc_event_corridor_links', 'pc_company_corridor_roles',
                'pc_corridor_route_references'}


def _shared():
    path = Path(__file__).resolve().parent / 'shared'
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
    from pc_auth import require_super_admin, service_client, current_user, user_context
    return require_super_admin, service_client, current_user, user_context


def staff_available():
    """Safe check for incidental embedding in pages also visited by clients."""
    try:
        _, _, current_user, user_context = _shared()
        user = current_user()
        if not user:
            return False
        return (user_context(user) or {}).get('global_role') in {'super_admin', 'staff'}
    except Exception:
        return False


def _staff_client():
    required, client, _, _ = _shared()
    required()  # Explicit access gate even when host app has auth migration disabled.
    sb = client()
    if sb is None:
        st.error('Staff Supabase connection is not configured.')
        st.stop()
    return sb


def _page(sb, table, cols, **filters):
    result=[]
    for offset in range(0, 3000, 500):
        q=sb.table(table).select(cols)
        for name,value in filters.items():
            if isinstance(value, (list,tuple)):
                q=q.in_(name,list(value))
            else:
                q=q.eq(name,value)
        chunk=q.range(offset,offset+499).execute().data or []
        result.extend(chunk)
        if len(chunk)<500:
            break
    return result


def _obj(value):
    if isinstance(value,dict): return value
    if isinstance(value,str):
        try:
            got=json.loads(value)
            return got if isinstance(got,dict) else {}
        except (ValueError,TypeError): pass
    return {}


def _items(value):
    if isinstance(value,list): return value
    if isinstance(value,dict): return [value]
    if isinstance(value,str):
        try:
            x=json.loads(value)
            if isinstance(x,list):return x
            if isinstance(x,dict):return [x]
        except (ValueError,TypeError):pass
        return [x.strip('•- ') for x in value.split('\n') if x.strip('•- ')]
    return []


def _url(value):
    u=str(value or '').strip()
    p=urlsplit(u)
    return u if p.scheme in ('https','http') and p.netloc else ''


def _s(value):
    if isinstance(value,(dict,list)):return json.dumps(value,ensure_ascii=False)
    return str(value or '').strip()


def _link_sources(news,content,event):
    seen=set(); found=[]
    raw=[]
    for r in news:
        raw.append((r.get('source_url'),r.get('headline') or r.get('publisher'),r.get('source_role')))
    for item in _items(content.get('source_evidence')):
        if isinstance(item,dict):raw.append((item.get('url') or item.get('source_url'),item.get('headline') or item.get('title'),'evidence'))
        else:raw.append((item,None,'evidence'))
    meta=_obj(_obj(event.get('payload')).get('metadata'))
    for item in _items(meta.get('research_sources')):
        if isinstance(item,dict):raw.append((item.get('url'),item.get('title'),'original package'))
        else:raw.append((item,None,'original package'))
    for url,title,role in raw:
        u=_url(url)
        if not u or u in seen:continue
        seen.add(u)
        found.append({'url':u,'title':str(title or urlsplit(u).netloc),'role':str(role or '')})
    return found


def resolve_package_graph(events,all_rows):
    """Pure resolver. Exact source package IDs only; no fuzzy identity merging."""
    by_job=defaultdict(lambda:{'objects':{},'links':defaultdict(list),'corridors':defaultdict(list)})
    for row in all_rows:
        job=str(row.get('ingestion_job_id') or '')
        kind=str(row.get('target_table') or '')
        payload=_obj(row.get('payload'))
        if kind in KEYS:
            package_id=str(payload.get(KEYS[kind]) or '')
            if package_id: by_job[job]['objects'][package_id]=row
        if kind=='pc_event_links':
            event_id=str(payload.get('event_id') or '')
            if event_id: by_job[job]['links'][event_id].append(row)
        if kind=='pc_event_corridor_links':
            event_id=str(payload.get('event_id') or '')
            if event_id: by_job[job]['corridors'][event_id].append(row)
    resolved={}
    for event in events:
        job=str(event.get('ingestion_job_id') or '')
        event_id=str(_obj(event.get('payload')).get('event_id') or '')
        scope=by_job[job]; connected=[]
        for row in scope['links'].get(event_id,[]):
            payload=_obj(row.get('payload'))
            target=scope['objects'].get(str(payload.get('linked_id') or ''))
            connected.append({'edge':row,'target':target,'name':payload.get('linked_name') or (target or {}).get('natural_key') or 'Unresolved reference',
                              'relationship':payload.get('relationship') or 'mentioned',
                              'type':payload.get('linked_type') or 'unknown'})
        resolved[(job,event_id)]={'event':event,'links':connected,'corridors':scope['corridors'].get(event_id,[])}
    return resolved


def _read_graph(sb,job_ids):
    # Fetch each table independently to avoid streaming the entire corporate registry.
    rows=[]
    for job in job_ids:
        rows.extend(_page(sb,'pc_staged_records',
            'staged_record_id,ingestion_job_id,source_record_key,target_table,natural_key,payload,resolution_status,review_status,resolved_entity_id',
            ingestion_job_id=job))
    return rows


@st.cache_data(ttl=90,show_spinner=False)
def _read_jobs(_sb):
    return (_sb.table('pc_ingestion_jobs').select('ingestion_job_id,title,created_at,status')
            .order('created_at',desc=True).limit(70).execute().data or [])


@st.cache_data(ttl=90,show_spinner=False)
def _read_content(_sb,job):
    return _page(_sb,'pc_v08_trade_content',
        'content_id,ingestion_job_id,source_record_key,target_table,target_key,canonical_id,title,description,what_it_means,operational_impact,commercial_implications,pc_assessment,monitoring_indicators,research_gaps,source_evidence,editorial_status',
        ingestion_job_id=job)


def _load_published(sb,stage_ids):
    if not stage_ids:return {}
    found={}
    for start in range(0,len(stage_ids),100):
        try:
            rows=(sb.table('pc_v10_publication_items').select('staged_record_id,canonical_table,canonical_id')
                .in_('staged_record_id',stage_ids[start:start+100]).execute().data or [])
            found.update({str(r['staged_record_id']):r for r in rows})
        except Exception:return found
    return found


def _load_approvals(sb,stage_ids):
    if not stage_ids:return {}
    found={}
    for start in range(0,len(stage_ids),100):
        try:
            rows=(sb.table('pc_v10_approvals').select('staged_record_id,decision,canonical_id,source_verified,content_reviewed')
                 .in_('staged_record_id',stage_ids[start:start+100]).execute().data or [])
            found.update({str(r['staged_record_id']):r for r in rows})
        except Exception:return found
    return found


def _jump(table,canonical_id,key):
    pages={'pc_entities':('Companies','company_pick_id'),
           'pc_assets':('Ports & Terminals','port_pick_id'),
           'pc_mobile_assets':('Vessels','vessel_pick_id')}
    if table not in pages or not canonical_id:return
    label,state_key=pages[table]
    if st.button('Open '+label+' profile',key=key):
        st.session_state[state_key]=str(canonical_id)
        st.session_state['nav_request']=label
        st.rerun()


def _render_text(label,value):
    s=_s(value)
    if s and s.casefold() not in {'not assessed','not applicable','null','none','[]','{}'}:
        st.markdown('**'+label+'**')
        st.write(s)
    else:
        st.caption(label+': analysis pending')


def _render_event(sb,item,content,approved,published,crossjob_verified=None):
    crossjob_verified=crossjob_verified or {}
    event=item['event']; job=event['ingestion_job_id']
    stage_id=str(event.get('staged_record_id') or '')
    pub=published.get(stage_id)
    if pub:
        st.success('Canonical event published: '+str(pub['canonical_id']))
    else:
        st.warning('Research / staging only — not client-visible; verified publication pending.')
    metadata=_obj(_obj(event.get('payload')).get('metadata'))
    st.subheader(content.get('title') or _obj(event.get('payload')).get('title') or event.get('natural_key') or 'Untitled development')
    st.caption('Source package: '+str(job)[:8]+' · '+str(content.get('editorial_status') or 'draft'))
    for label,field,fallback in (
        ('What happened','description',_obj(event.get('payload')).get('description')),
        ('Why it matters','what_it_means',metadata.get('why_it_matters')),
        ('Operational implications','operational_impact',None),
        ('Commercial implications','commercial_implications',metadata.get('business_implications')),
        ('P&C assessment','pc_assessment',metadata.get('assessment'))):
        _render_text(label,content.get(field) or fallback)
    st.markdown('**Monitoring indicators**')
    indicators=_items(content.get('monitoring_indicators') or metadata.get('monitoring_indicators'))
    if indicators:
        for x in indicators:
            text=x.get('indicator') or x.get('text') if isinstance(x,dict) else str(x)
            if text:st.markdown('- '+str(text))
    else:st.caption('Monitoring indicators pending.')
    st.markdown('#### Connected organisations, companies and assets')
    if not item['links']:
        st.info('No source-provided event links found in this package; do not infer ownership.')
    for i,linked in enumerate(item['links']):
        target=linked['target']; r=linked['edge']
        kind=(target or {}).get('target_table') or linked['type']
        stage_ref=str((target or {}).get('staged_record_id') or '')
        pub=published.get(stage_ref)
        approval=approved.get(stage_ref) or {}
        resolved=(pub or {}).get('canonical_id') or (approval.get('canonical_id') if approval.get('source_verified') and approval.get('decision')=='match_existing' else None)
        cross_match=False
        if not resolved and target:
            kind_id=KEYS.get(str(target.get('target_table') or ''))
            pkg=str(_obj(target.get('payload')).get(kind_id) or '') if kind_id else ''
            identity=(str(target.get('target_table') or ''),pkg,str(target.get('natural_key') or '').strip().casefold())
            if identity in crossjob_verified:
                resolved=crossjob_verified[identity]
                cross_match=True
        status='Canonical endpoint published; relationship still staged' if pub else 'Identical package identity confirmed in another import; edge still staged' if cross_match else 'Identity approved; relationship still staged' if resolved else 'Identity / relationship review pending'
        with st.container(border=True):
            st.markdown('**'+str(linked['name'])+'** · '+str(linked['relationship']).replace('_',' '))
            st.caption(str(kind)+' · '+status)
            if resolved: _jump(kind,resolved,f'conn_jump_{stage_id}_{i}')
            if not target:st.caption('Source reference not resolved within this intake batch.')
    st.markdown('#### Corridors')
    if item['corridors']:
        for link in item['corridors']:
            p=_obj(link.get('payload'))
            st.write(str(p.get('corridor_name') or p.get('corridor_key') or 'Unresolved corridor')+' — source-supplied, pending endpoint verification')
    else:
        st.caption('No verified explicit corridor association in this package. Route mentions are not treated as established links.')
    try:
        news=(sb.table('pc_v08_news_items').select('source_url,publisher,headline,published_at,source_role')
             .eq('ingestion_job_id',job).eq('source_record_key',event['source_record_key']).limit(90).execute().data or [])
    except Exception as exc:
        news=[];st.warning('News lookup unavailable: '+str(exc))
    links=_link_sources(news,content,event)
    st.markdown('#### Original articles and evidence')
    if not links:st.warning('No connected source URLs. Editorial review required.')
    for source in links:st.markdown('- ['+source['title'].replace(']','')+']('+source['url']+')'+(' · '+source['role'] if source['role'] else ''))
    return links


def render_connected_developments(*,compact=False,keyword='',selected_id=None):
    """Staff reader inside primary News/Companies workflows, not another import screen."""
    sb=_staff_client()
    if not compact:
        st.header('Connected Trade developments')
        st.caption('Your existing Supabase intelligence, connected to companies, agencies, assets and verified corridor references. Unpublished material stays staff-only.')
    try:
        jobs=_read_jobs(sb)
    except Exception as exc:
        st.error('Cannot load ingestion jobs: '+str(exc));return
    if not jobs:
        st.warning('No ingestion jobs found.');return
    pinned=st.session_state.pop('pc_connected_pick',None)
    job_labels={j['ingestion_job_id']:j['title'] for j in jobs}
    options=[j['ingestion_job_id'] for j in jobs]
    wanted=['8b1ce7e5-cd67-4be8-af3d-95dd788739d9','9aa6de14-fddc-4f2d-8087-7ffa8b2f9e45']
    defaults=[pinned[0]] if isinstance(pinned,tuple) and pinned[0] in options else [next((x for x in wanted if x in options),options[0])]
    job_scope=st.multiselect('Source batches',options,default=defaults or options[:2],
        format_func=lambda v:job_labels.get(v,v),key='pc_conn_jobs')
    if not job_scope:st.info('Select at least one intake batch.');return
    try:
        # Other versions of the SAME source package can contain already-published ID decisions.
        # Read these only to reuse unique, verified exact-package identities; never fuzzy merge.
        identity_jobs=list(dict.fromkeys(job_scope+[j for j in wanted if j in options]))
        rows=_read_graph(sb,identity_jobs)
        events=[r for r in rows if r['target_table']=='pc_events' and r['ingestion_job_id'] in job_scope]
        graph=resolve_package_graph(events,rows)
        content=[]
        for job in job_scope:content.extend([c for c in _read_content(sb,job) if c['target_table']=='pc_events'])
    except Exception as exc:
        st.error('Could not construct existing source relationships: '+str(exc));return
    narratives={(c['ingestion_job_id'],c['source_record_key']):c for c in content}
    stages=[str(r.get('staged_record_id')) for r in rows if r.get('staged_record_id')]
    approved=_load_approvals(sb,stages);published=_load_published(sb,stages)
    possible=defaultdict(set)
    for row in rows:
        kind=row.get('target_table'); id_field=KEYS.get(kind)
        if not id_field or kind=='pc_events':continue
        pkg=str(_obj(row.get('payload')).get(id_field) or '')
        stage=str(row.get('staged_record_id') or '')
        pub=published.get(stage) or {}
        approval=approved.get(stage) or {}
        canonical=pub.get('canonical_id') or (approval.get('canonical_id') if approval.get('source_verified') and approval.get('decision')=='match_existing' else None)
        if pkg and canonical:possible[(kind,pkg,str(row.get('natural_key') or '').strip().casefold())].add(str(canonical))
    crossjob_verified={key:next(iter(ids)) for key,ids in possible.items() if len(ids)==1}
    st.caption(f'{len(events)} staged event rows · {len(content)} draft narratives · {sum(len(x["links"]) for x in graph.values())} exact package relationship edges')
    query=st.text_input('Find development, company, agency, port or corridor',value='' if pinned else keyword,
        placeholder='DP World, Ogun, GT USA, Port Canaveral, Etihad Rail…',key='pc_conn_search')
    terms=[t.casefold() for t in query.split() if t.strip()]
    choices=[]
    for key,item in graph.items():
        event=item['event'];c=narratives.get((key[0],event['source_record_key']),{})
        label=str(c.get('title') or _obj(event.get('payload')).get('title') or event.get('natural_key') or '')
        searchable=' '.join([label,str(c.get('description') or ''),str(c.get('what_it_means') or '')]+
            [str(x.get('name') or '') for x in item['links']]+[str(_obj(x.get('payload')).get('corridor_name') or '') for x in item['corridors']]).casefold()
        if all(t in searchable for t in terms):choices.append((key,label))
    choices.sort(key=lambda x:x[1].casefold())
    if not choices:
        st.info('No connected development matches this search in the selected batches. Try “Ogun”, “DP World” or another batch.');return
    first=next((i for i,(k,_) in enumerate(choices) if k==pinned or k==selected_id),0)
    chosen=st.selectbox('Development',list(range(len(choices))),index=first,
        format_func=lambda i:choices[i][1]+' · '+choices[i][0][0][:8],key='pc_conn_pick')
    key=choices[chosen][0];item=graph[key];event=item['event'];c=narratives.get((key[0],event['source_record_key']),{})
    _render_event(sb,item,c,approved,published,crossjob_verified)


def render_company_connections(company_id,company_name):
    """Staff-only related development links embedded in main canonical Company page."""
    if not staff_available():return
    sb=_staff_client()
    with st.expander('Related developments from recent imports (staff)',expanded=True):
        try:
            jobs=_read_jobs(sb)[:25]
            rows=_read_graph(sb,[j['ingestion_job_id'] for j in jobs[:7]])
            events=[r for r in rows if r['target_table']=='pc_events']
            graph=resolve_package_graph(events,rows)
            approvals=_load_approvals(sb,[str(r['staged_record_id']) for r in rows if r['target_table']=='pc_entities'])
            published=_load_published(sb,[str(r['staged_record_id']) for r in rows if r['target_table']=='pc_entities'])
            matched=[]
            for key,item in graph.items():
                for link in item['links']:
                    target=link['target']
                    if not target or target.get('target_table')!='pc_entities':continue
                    stage=str(target.get('staged_record_id') or '')
                    validated_id=(published.get(stage) or {}).get('canonical_id') or (approvals.get(stage) or {}).get('canonical_id')
                    is_same=validated_id==company_id or str(target.get('natural_key') or '').casefold()==str(company_name).casefold()
                    if is_same:
                        matched.append((key,item['event']['natural_key'],link['relationship'],validated_id==company_id));break
            if not matched:st.caption('No source-linked developments found in the most recent import batches.');return
            unique=[];seen=set()
            for entry in matched:
                signature=(str(entry[1]).casefold(),str(entry[2]).casefold())
                if signature not in seen:seen.add(signature);unique.append(entry)
            for n,(key,title,role,verified) in enumerate(unique[:30]):
                col1,col2=st.columns([5,1])
                col1.write(title+' · '+role.replace('_',' '))
                col1.caption('Verified canonical association' if verified else 'Source name match only — identity review')
                if col2.button('Open',key='pc_co_dev_'+str(company_id)+'_'+str(n)):
                    st.session_state['pc_connected_pick']=key
                    st.session_state['nav_request']='News & Developments'
                    st.rerun()
        except Exception as exc:st.warning('Related import links unavailable: '+str(exc))
