import streamlit as st
from pc_operating_picture import render_operating_picture

st.set_page_config(page_title="P&C Trade",page_icon="◈",layout="wide",initial_sidebar_state="expanded")
render_operating_picture("trade")
