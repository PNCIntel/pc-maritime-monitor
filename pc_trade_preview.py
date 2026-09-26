"""Admin-only read-only Trade preview. Deploy separately while integrating into Trade app."""
import sys
from pathlib import Path
import streamlit as st
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'shared'))
from pc_auth import service_client, require_super_admin
from pc_trade_intelligence import render_trade_intelligence
st.set_page_config(page_title='P&C Trade Intelligence Preview',layout='wide')
require_super_admin()
sb=service_client()
render_trade_intelligence(sb,admin=True)
