"""Admin-only fast intake and job dashboard. Call from pc-power-admin after auth.
This module does not publish anything into canonical tables.
"""
from pathlib import Path
import io
import json
import math
import pandas as pd
import streamlit as st
from pc_v07_core import enqueue, normalize_rows


def _clean_cell(value):
 try:
  if pd.isna(value):return None
 except (TypeError,ValueError):pass
 return value


def _maybe_json(x):
 if isinstance(x,dict):return x
 if isinstance(x,str) and x.strip():
  try:return json.loads(x)
  except (TypeError,ValueError):pass
 return None


def load_structured_file(file):
 data=file.getvalue(); ext=Path(file.name).suffix.lower()
 if len(data)>25_000_000:raise ValueError('Limit imports to 25 MB per file; split larger inputs.')
 if ext=='.json':
  obj=json.loads(data)
  if isinstance(obj,dict):obj=obj.get('records') or obj.get('proposals') or obj
  if not isinstance(obj,list):raise ValueError('Expected a JSON array or {records: [...]}')
  return obj
 if ext=='.csv':
  df=pd.read_csv(io.BytesIO(data)).where(lambda x:x.notna(),None)
  if not ({'table','payload'}<=set(df.columns) or {'target_table','payload'}<=set(df.columns)):
   raise ValueError('CSV requires table or target_table and payload columns')
  return df.to_dict('records')
 if ext in {'.xlsx','.xlsm'}:
  xl=pd.ExcelFile(io.BytesIO(data)); rows=[];analysis={}
  if 'ALL_EVENT_ANALYSIS' in xl.sheet_names:
   a=pd.read_excel(xl,'ALL_EVENT_ANALYSIS').where(lambda x:x.notna(),None)
   for _,r in a.iterrows():
    eid=str(_clean_cell(r.get('Event ID')) or '').strip()
    if eid and eid.lower()!='none':
     analysis[eid]={
      'event_summary':r.get('Event summary'),
      'what_happened':r.get('What happened'),
      'why_it_matters':r.get('What it means'),
      'commercial_implications':r.get('Commercial implications'),
      'assessment':r.get('P&C assessment'),
      'monitoring_indicators':[s.strip() for s in str(r.get('Monitoring indicators') or '').split(';') if s.strip()],
      'research_sources':[{'url':r['Article URL']}] if isinstance(r.get('Article URL'),str) and r['Article URL'].startswith('http') else [],
      'research_status':r.get('Source status')}
  for sheet in xl.sheet_names:
   if not sheet.startswith('pc_'):continue
   df=pd.read_excel(xl,sheet_name=sheet).where(lambda x:x.notna(),None)
   for _,r in df.iterrows():
    d={k:_clean_cell(v) for k,v in r.to_dict().items()};payload=_maybe_json(d.get('payload'))
    if not isinstance(payload,dict):
     payload={k:v for k,v in d.items() if k not in {'natural_key','action','confidence','source_url'} and v is not None}
    if sheet=='pc_events' and str(payload.get('event_id')) in analysis:
     meta=payload.setdefault('metadata',{})
     if not isinstance(meta,dict):meta={};payload['metadata']=meta
     overlay={k:v for k,v in analysis[str(payload['event_id'])].items() if v is not None}
     for k,v in overlay.items():
      if k=='research_sources':meta[k]=list(meta.get(k) or [])+v
      else:meta.setdefault(k,v)
    rows.append({'table':sheet,'natural_key':d.get('natural_key') or payload.get('name') or payload.get('title') or payload.get('event_id'),
                 'payload':payload,'confidence':d.get('confidence')})
  return rows
 raise ValueError('Only structured JSON, CSV or XLSX for fast queue; use existing Research workspace for PDF/URL intake.')


def render_bulk_intake(sb, active_package=None):
 st.title('Universal Loader · Bulk intake')
 st.caption('Queue thousands of proposals quickly. Processing runs outside Streamlit; all changes stay in review staging.')
 st.info('Upload structured data without AI processing for every row. The existing research workspace handles URLs and PDFs; both can feed this queue.')
 source=st.radio('Batch source',['Use current extracted package','Upload structured file'],horizontal=True)
 if source=='Upload structured file':
  file=st.file_uploader('JSON, CSV or analytical Excel workbook',type=['json','csv','xlsx','xlsm'],key='pc_v07_upload')
  if file:
   try:records=load_structured_file(file)
   except Exception as e:st.error(str(e));records=[]
  else:records=[]
 else: records=active_package or []
 title=st.text_input('Job title','P&C batch: Trade, infrastructure and events')
 research=st.checkbox('Queue targeted AI research for unresolved identities',value=False,
   help='Runs only when the scheduled worker has OPENAI_API_KEY and PC_ENABLE_AI_RESEARCH=1.')
 if records:
  st.metric('Incoming rows',len(records))
  st.dataframe(pd.DataFrame([{'Table':r.get('table') or r.get('target_table'),
    'Key':r.get('natural_key') or (r.get('payload') or {}).get('name')} for r in records[:25]]),
    hide_index=True,use_container_width=True)
  if st.button('Queue complete package',type='primary'):
   try:
    job,count,reused=enqueue(sb,records,title=title,ai_research=research)
    st.success(f"{'Existing job reused' if reused else 'Queued'}: {count:,} rows · {job}")
   except Exception as e:st.error(f'Queue failed safely: {e}')
 else: st.caption('Choose an existing extracted package or upload a structured file.')
 st.divider();st.subheader('Recent jobs')
 if st.button('Refresh jobs',key='pc_v07_refresh'):st.cache_data.clear()
 try:
  jobs=(sb.table('pc_ingestion_jobs').select('ingestion_job_id,title,status,stats,created_at')
     .eq('job_type','UNIVERSAL_BATCH_V07').order('created_at',desc=True).limit(30).execute().data or [])
  if jobs:
   st.dataframe(pd.DataFrame(jobs),hide_index=True,use_container_width=True)
   selected=st.selectbox('Inspect queue',jobs,format_func=lambda j:f"{j['title']} ({j['status']})")
   statuses={}
   for status in ('queued','processing','staged','needs_review','failed'):
    r=sb.table('pc_v07_queue').select('queue_id',count='exact',head=True).eq('ingestion_job_id',selected['ingestion_job_id']).eq('status',status).execute()
    statuses[status]=r.count or 0
   cols=st.columns(5)
   for col,(name,value) in zip(cols,statuses.items()):col.metric(name.title(),value)
   page=st.number_input('Queue page',min_value=1,value=1,step=1)
   rows=sb.table('pc_v07_queue').select('target_table,natural_key,status,error_text,source_record_key').eq('ingestion_job_id',selected['ingestion_job_id']).order('queue_id').range((page-1)*50,page*50-1).execute().data or []
   if rows:st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
  else:st.info('No v0.7 jobs yet. Run the SQL migration, queue a package and enable the worker.')
 except Exception as e:st.error(f'Could not load queue dashboard: {e}. Run 01_SUPABASE_V07.sql first.')
