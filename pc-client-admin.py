from __future__ import annotations
from pathlib import Path
import os, sys
import pandas as pd
import streamlit as st
ROOT=Path(__file__).resolve().parent; SHARED=ROOT/"shared"
if str(SHARED) not in sys.path: sys.path.insert(0,str(SHARED))
from pc_auth import require_login, service_client, organization_for_context

st.set_page_config(page_title="P&C Client Admin",page_icon="◈",layout="wide")
ctx=require_login(None,"P&C Client Workspace") if os.getenv("PC_REQUIRE_AUTH","true").lower()=="true" else {"global_role":"super_admin","memberships":[]}
sb=service_client()
st.title("P&C Client Administration")
st.caption("Organization workspace for users, roles, product access requests, saved queries and watchlists.")

if not ctx.get('memberships'):
    st.info("No organization membership is attached to this login yet. P&C Power Admin must assign the account to an organization.")
    st.stop()
membership=ctx['memberships'][0]
oid=membership['organization_id']; role=membership.get('role','viewer')
org=membership.get('pc_organizations') or {}
st.metric("Organization",org.get('name','Client'))
c1,c2,c3=st.columns(3); c1.metric("Your role",role); c2.metric("Seat limit",org.get('seat_limit','—'))
members=sb.table('pc_organization_members').select('user_id,role,active,joined_at,pc_profiles(email,display_name)').eq('organization_id',oid).execute().data or [] if sb else []
c3.metric("Active users",sum(1 for m in members if m.get('active')))

tabs=st.tabs(["Users","Products","Saved Queries","Watchlists","Access Requests"])
with tabs[0]:
    st.dataframe(pd.DataFrame(members),use_container_width=True,hide_index=True)
    if role=='org_admin':
        st.caption("Client admins submit user/role changes. P&C retains final seat and entitlement control.")
with tabs[1]:
    ent=sb.table('pc_organization_entitlements').select('*').eq('organization_id',oid).execute().data or [] if sb else []
    st.dataframe(pd.DataFrame(ent),use_container_width=True,hide_index=True)
with tabs[2]:
    q=sb.table('pc_saved_queries').select('saved_query_id,product_code,title,query_text,query_type,created_at,updated_at').eq('organization_id',oid).order('updated_at',desc=True).execute().data or [] if sb else []
    st.dataframe(pd.DataFrame(q),use_container_width=True,hide_index=True)
with tabs[3]:
    w=sb.table('pc_saved_watchlists').select('watchlist_id,product_code,name,description,shared_with_org,created_at').eq('organization_id',oid).execute().data or [] if sb else []
    st.dataframe(pd.DataFrame(w),use_container_width=True,hide_index=True)
with tabs[4]:
    req=sb.table('pc_client_admin_requests').select('*').eq('organization_id',oid).order('created_at',desc=True).execute().data or [] if sb else []
    st.dataframe(pd.DataFrame(req),use_container_width=True,hide_index=True)
    if role!='org_admin':
        st.info("Only the organization's Client Admin can submit account changes.")
    else:
        with st.form('access_request'):
            typ=st.selectbox('Request type',['INVITE_USER','CHANGE_ROLE','ADD_PRODUCT_ACCESS','REMOVE_USER'])
            email=st.text_input('User email')
            newrole=st.selectbox('Role',['viewer','executive','analyst','senior_analyst','org_admin'])
            product=st.selectbox('Product',['','TRADE','INTELLIGENCE','NERAI'])
            note=st.text_area('Notes')
            if st.form_submit_button('Submit request'):
                sb.table('pc_client_admin_requests').insert({'organization_id':oid,'requested_by':ctx['user_id'],'request_type':typ,'requested_email':email or None,'requested_role':newrole or None,'requested_product':product or None,'details':{'note':note}}).execute(); st.success('Request submitted to P&C.')
