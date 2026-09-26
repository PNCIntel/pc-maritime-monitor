"""Display explicitly published descriptive sidecars, not draft editorial content.
Client-facing callers MUST enforce existing Trade authentication, tenant scope and entitlement.
"""
import streamlit as st
from pc_v09_presentation import render_sections


def render_published_content(sb, admin=False):
    st.subheader('Published Trade intelligence')
    st.caption('Only reviewed, explicitly published descriptions; staged drafts never appear here.')
    page=st.number_input('Published records page',min_value=1,value=1,step=1,key='v10_trade_page')
    q=sb.table('pc_v10_published_content').select('content_id,target_table,canonical_id,title,description,what_it_means,operational_impact,commercial_implications,pc_assessment,monitoring_indicators,research_gaps,source_evidence,visible_in_trade,published_at')
    if not admin:q=q.eq('visible_in_trade',True)
    rows=(q.order('published_at',desc=True).range((page-1)*25,page*25-1).execute().data or [])
    if not rows:st.info('No published records on this page yet.');return
    choices=[f"{r.get('target_table')} — {r.get('title')} ({r.get('published_at','')[:10]})" for r in rows]
    selected=st.selectbox('Inspect published development or asset',range(len(rows)),format_func=lambda i:choices[i],key='v10_trade_selected')
    rec=rows[selected]
    st.caption('Canonical ID: '+str(rec.get('canonical_id')))
    render_sections(st,rec,heading=True)
