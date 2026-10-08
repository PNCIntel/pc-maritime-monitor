"""Power & Corridors: Commodities & Resources."""
import streamlit as st
from pc_specialist_markets import render
st.set_page_config(page_title='P&C Commodities & Resources',page_icon='◈',layout='wide')
render('commodities')
