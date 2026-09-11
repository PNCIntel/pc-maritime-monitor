from __future__ import annotations
from pathlib import Path
import os, sys, json
import pandas as pd
import streamlit as st
ROOT=Path(__file__).resolve().parent; SHARED=ROOT/"shared"
if str(SHARED) not in sys.path: sys.path.insert(0,str(SHARED))
from pc_auth import require_login, service_client

st.set_page_config(page_title="NERAI | Power & Corridors",page_icon="◇",layout="wide")
if os.getenv('PC_REQUIRE_AUTH','false').lower()=='true': ctx=require_login('NERAI','NERAI')
else: ctx={'user_id':'local','memberships':[],'global_role':'super_admin'}
sb=service_client()
st.markdown("<div style='color:#d7b66a;letter-spacing:.14em;font-size:.75rem'>POWER & CORRIDORS · NERAI</div>",unsafe_allow_html=True)
st.title("NERAI Foresight")
st.caption("Signals, scenarios, probabilities, early warning and corridor pressure layered over the shared P&C data model.")

tabs=st.tabs(['Forecasts','Scenarios','Signals','My Runs'])
with tabs[0]:
    rows=sb.table('pc_analysis').select('*').eq('product_code','NERAI').order('start_date',desc=True).limit(200).execute().data or [] if sb else []
    st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
with tabs[1]:
    st.markdown('### Scenario request')
    prompt=st.text_area('What future should NERAI test?',placeholder='Model a 60-day Hormuz disruption and identify likely second-order effects across Gulf port, rail and logistics networks.')
    if st.button('Save scenario request',disabled=not bool(prompt)):
        if not sb: st.error('Supabase required.')
        elif ctx.get('user_id')=='local': st.info('Configure authentication before storing client scenarios.')
        else:
            oid=(ctx.get('memberships') or [{}])[0].get('organization_id')
            sb.table('pc_scenario_runs').insert({'organization_id':oid,'user_id':ctx['user_id'],'product_code':'NERAI','title':prompt[:100],'prompt':prompt,'inputs':{},'result':None}).execute(); st.success('Scenario request saved.')
with tabs[2]:
    rows=sb.table('pc_analysis').select('analysis_id,analysis_type,title,family,status,start_date,time_horizon,indicators,trigger_threshold,confidence').eq('product_code','NERAI').limit(200).execute().data or [] if sb else []
    st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
with tabs[3]:
    if sb and ctx.get('user_id')!='local':
        oid=(ctx.get('memberships') or [{}])[0].get('organization_id')
        rows=sb.table('pc_scenario_runs').select('*').eq('organization_id',oid).order('created_at',desc=True).limit(200).execute().data or []
        st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
    else: st.caption('Client scenario history appears after Supabase authentication is enabled.')
