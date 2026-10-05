import sys
from pathlib import Path
import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pc_market_lenses import render_market_terminal

st.set_page_config(
    page_title="P&C Strategic Industries",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)

render_market_terminal("strategic")
