"""Trade-first read-only Streamlit page.
Call render_trade_intelligence(sb, admin=True) inside an authenticated internal app.
Client-facing publication MUST use admin=False and its normal client access controls.
"""
import streamlit as st
import pandas as pd
from pc_v09_presentation import (render_sections, readable, entries, sources, quality_flags)


def render_trade_intelligence(sb,admin=False):
 st.header('Trade intelligence')
 st.caption('Canonical records are separate from unpublished research proposals.')
 tab_events,tab_assets,tab_corridors,tab_staged,tab_editorial=st.tabs(['Developments','Assets and companies','Corridors','Review pipeline','Descriptions & news'])
 with tab_events:
  page=st.number_input('Developments page',min_value=1,step=1,value=1)
  q=sb.table('pc_events').select('event_id,title,start_date,event_domain,location,description,operational_impact,commercial_impact,metadata')
  if not admin:q=q.eq('trade_visible',True)
  rows=(q.order('start_date',desc=True).range((page-1)*25,page*25-1).execute().data or [])
  # Client apps must ALSO apply their existing tenant authorization and RLS; this helper is not an auth layer.
  if rows:
   st.dataframe(pd.DataFrame([{'Date':r.get('start_date'),'Development':r.get('title'),'Domain':r.get('event_domain'),
       'Location':r.get('location'),'Operational impact':r.get('operational_impact'),
       'Commercial impact':r.get('commercial_impact')} for r in rows]),hide_index=True,use_container_width=True)
   ids=[r['event_id'] for r in rows if r.get('event_id')]
   if ids:
    linked=(sb.table('pc_event_links').select('event_id,linked_type,linked_id,linked_name,relationship').in_('event_id',ids).limit(500).execute().data or [])
    selected=st.selectbox('Inspect connected development',rows,format_func=lambda r:r.get('title') or str(r['event_id']))
    m=selected.get('metadata') or {}
    if not isinstance(m,dict):m={}
    presentation={
     'title':selected.get('title'),
     'description':m.get('what_happened') or selected.get('description'),
     'what_it_means':m.get('why_it_matters') or m.get('what_it_means'),
     'operational_impact':selected.get('operational_impact') or m.get('operational_impact'),
     'commercial_implications':selected.get('commercial_impact') or m.get('commercial_implications') or m.get('business_implications'),
     'pc_assessment':m.get('assessment') or m.get('pc_assessment'),
     'monitoring_indicators':m.get('monitoring_indicators'),
     'research_gaps':m.get('research_gaps'),
     'source_evidence':m.get('research_sources') or m.get('sources'),
    }
    render_sections(st,presentation,heading=True)
    matches=[x for x in linked if x['event_id']==selected['event_id']]
    if matches:st.dataframe(pd.DataFrame(matches),hide_index=True,use_container_width=True)
  else:st.info('No visible canonical developments on this page.')
 with tab_assets:
  kind=st.selectbox('Registry',['pc_assets','pc_mobile_assets','pc_entities'])
  columns={'pc_assets':'asset_id,name,asset_type,country,record_status',
           'pc_mobile_assets':'mobile_asset_id,name,asset_type,imo,flag,record_status',
           'pc_entities':'entity_id,name,entity_type,hq_country,record_status'}[kind]
  page=st.number_input('Registry page',min_value=1,value=1,step=1,key='trade_asset_page')
  q=sb.table(kind).select(columns).order('name').range((page-1)*50,page*50-1)
  if not admin:q=q.eq('record_status','verified')
  rows=q.execute().data or []
  st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
 with tab_corridors:
  page=st.number_input('Corridor page',min_value=1,value=1,step=1,key='trade_corridor_page')
  q=sb.table('pc_trade_corridors').select('corridor_key,corridor_name,corridor_type,geography,origin_region,destination_region,status').order('corridor_name').range((page-1)*50,page*50-1)
  if not admin:q=q.eq('status','active')
  rows=q.execute().data or []
  st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
 with tab_staged:
  if not admin:
   st.info('Review-stage proposals are restricted to administrators.')
   return
  jobs=sb.table('pc_ingestion_jobs').select('ingestion_job_id,title,status,stats,created_at').order('created_at',desc=True).limit(50).execute().data or []
  if not jobs:st.info('No ingestion jobs yet.');return
  st.dataframe(pd.DataFrame(jobs),hide_index=True,use_container_width=True)
  chosen=st.selectbox('Job to inspect',jobs,format_func=lambda j:f"{j.get('title')} — {j.get('status')}")
  page=st.number_input('Review page',min_value=1,value=1,step=1,key='trade_stage_page')
  rows=(sb.table('pc_staged_records').select('staged_record_id,target_table,natural_key,resolution_status,review_status,source_record_key')
        .eq('ingestion_job_id',chosen['ingestion_job_id']).order('created_at',desc=True)
        .range((page-1)*50,page*50-1).execute().data or [])
  st.dataframe(pd.DataFrame([{'Table':r['target_table'],'Name':r['natural_key'],
    'Status':r['resolution_status'],'Review':r['review_status']} for r in rows]),hide_index=True,use_container_width=True)
  if rows:
   pick=st.selectbox('Inspect source evidence / complete proposal',rows,
      format_func=lambda r:f"{r['target_table']} — {r['natural_key']}")
   if st.button('Load selected proposal details'):
    detail=(sb.table('pc_staged_records').select('payload,resolution_details').eq('staged_record_id',pick['staged_record_id']).limit(1).execute().data or [])
    if detail:st.json(detail[0],expanded=False)
  try:
   analyses=(sb.table('pc_v07_event_assessments').select('event_title,what_happened,what_it_means,operational_impact,commercial_impact,pc_assessment,monitoring_indicators,evidence_urls')
            .eq('ingestion_job_id',chosen['ingestion_job_id']).limit(20).execute().data or [])
  except Exception:
   analyses=[]
   st.warning('Draft assessments unavailable: run v0.7 SQL migration first.')
  if analyses:
   with st.expander('Draft business and trade assessments',expanded=True):
    for a in analyses:
     st.subheader(a['event_title'])
     render_sections(st,{
       'title':a.get('event_title'), 'description':a.get('what_happened'),
       'what_it_means':a.get('what_it_means'),
       'operational_impact':a.get('operational_impact'),
       'commercial_implications':a.get('commercial_impact'),
       'pc_assessment':a.get('pc_assessment'),
       'monitoring_indicators':a.get('monitoring_indicators'),
       'source_evidence':a.get('evidence_urls')})

  if rows:
   import hashlib
   keys={hashlib.sha256((r['target_table']+'|'+str(r['natural_key']).strip().casefold()).encode()).hexdigest():r['natural_key'] for r in rows
     if r['target_table'] in ('pc_entities','pc_assets','pc_mobile_assets','pc_trade_corridors')}
   if keys:
    try:
     research=sb.table('pc_v07_research_cache').select('research_key,subject,findings,evidence_urls,verified,researched_at').in_('research_key',list(keys)).limit(50).execute().data or []
     if research:
      with st.expander('AI research leads for this page — not verified',expanded=False):
       for rec in research:
        st.markdown('**'+rec['subject']+'**')
        st.write((rec.get('findings') or {}).get('text') or 'No research text')
        st.caption('Research lead only; analyst verification required before identity or ownership changes.')
        if rec.get('evidence_urls'):st.write('Source links:',rec['evidence_urls'])
    except Exception as exc:st.warning('Research cache not available: '+str(exc))

 with tab_editorial:
  if admin:
   try:render_trade_editorial(sb)
   except Exception as exc:st.error('Editorial records unavailable: '+str(exc)+' — apply v0.8 migration first.')
  else:st.info('Unpublished analyses are only available to administrators.')

def render_trade_editorial(sb):
 """Admin-only view of the full source-provided analysis and news trail (v0.8)."""
 st.subheader('Descriptions, business implications & news')
 st.caption('Draft intelligence for analyst review. This is NOT client-visible canonical publication.')
 jobs=(sb.table('pc_ingestion_jobs').select('ingestion_job_id,title,status,created_at')
       .order('created_at',desc=True).limit(50).execute().data or [])
 if not jobs:
  st.info('Queue an import to populate the editorial review.');return
 job=st.selectbox('Select research batch',jobs,
       format_func=lambda j:f"{j.get('title')} — {j.get('status')}",key='pc_v08_editorial_job')
 page=st.number_input('Editorial page',min_value=1,step=1,value=1,key='pc_v08_editorial_page')
 kind=st.selectbox('Type',['All','pc_events','pc_entities','pc_assets','pc_mobile_assets',
                              'pc_trade_corridors','pc_transport_routes','pc_transport_services'],
                   key='pc_v08_editorial_type')
 q=sb.table('pc_v08_trade_content').select('content_id,target_table,target_key,canonical_id,title,description,what_it_means,operational_impact,commercial_implications,pc_assessment,monitoring_indicators,research_gaps,source_evidence,text_origin,editorial_status')
 q=q.eq('ingestion_job_id',job['ingestion_job_id'])
 if kind!='All':q=q.eq('target_table',kind)
 rows=q.order('content_id',desc=True).range((page-1)*25,page*25-1).execute().data or []
 if not rows:st.info('No narrative records for this batch / category yet.');return
 st.dataframe(pd.DataFrame([{'Type':r['target_table'],'Title':r['title'],
       'Description':(r.get('description') or '')[:140],
       'Business':(r.get('commercial_implications') or '')[:100],
       'Review':r['editorial_status']} for r in rows]),
       use_container_width=True,hide_index=True)
 chosen=st.selectbox('Read full intelligence record',rows,
        format_func=lambda r:r['title'],key='pc_v08_editorial_selection')
 st.caption('Source-provided material · '+chosen['target_table']+' · '+chosen['editorial_status'])
 render_sections(st,chosen,heading=True)
 st.markdown('#### Related source articles')
 source_rows=(sb.table('pc_v08_news_items').select('source_url,publisher,headline,published_at,source_role')
     .eq('ingestion_job_id',job['ingestion_job_id'])
     .eq('source_record_key',next((r['source_record_key'] for r in (sb.table('pc_v08_trade_content')
           .select('source_record_key').eq('content_id',chosen['content_id']).limit(1).execute().data or [])),''))
     .limit(50).execute().data or [])
 for r in source_rows:
  for source in sources([{'url':r['source_url'],'headline':r.get('headline'),'publisher':r.get('publisher')} ]):
   st.markdown('- ['+(source['headline'] or source['publisher'])+']('+source['url']+')')
