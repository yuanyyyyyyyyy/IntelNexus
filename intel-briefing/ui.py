import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st

st.set_page_config(
    page_title="IntelNexus - Briefing",
    page_icon=None,
    initial_sidebar_state="expanded",
)

from src.ui.i18n import get_text
from src.ui.styles import render_light_theme_css, render_morandi_theme_css
from src.ui.sidebar import render_sidebar
from src.ui.briefing_viewer import render_briefing_preview, render_briefing_history

if "lang" not in st.session_state:
    st.session_state.lang = "zh"

render_light_theme_css()
render_morandi_theme_css()

col1, col2 = st.columns([8, 2])
with col1:
    st.markdown(f'<div class="main-title">{get_text("title")}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="main-subtitle">{get_text("subtitle")}</div>', unsafe_allow_html=True)

model = render_sidebar()

render_briefing_preview()
render_briefing_history()
