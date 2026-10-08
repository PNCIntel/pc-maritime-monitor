"""Power & Corridors: Markets & Freight."""
import streamlit as st
from pc_specialist_markets import render
st.set_page_config(page_title='P&C Markets & Freight',page_icon='◈',layout='wide')
render('markets')
