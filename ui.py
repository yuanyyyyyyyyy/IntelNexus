import streamlit as st

st.set_page_config(
    page_title="IntelNexus",
    page_icon=None,
    initial_sidebar_state="expanded",
)

from src.ui.i18n import get_text
from src.ui.styles import render_light_theme_css, render_morandi_theme_css
from src.ui.sidebar import render_sidebar
from src.ui.search_pipeline import run_search_pipeline
from src.ui.results import render_results_panels
from src.ui.download import render_download_section
from src.ui.results_detail import render_results_detail
from src.ui.briefing_viewer import render_briefing_preview, render_briefing_history

if "lang" not in st.session_state:
    st.session_state.lang = "zh"
if "query_cache" not in st.session_state:
    st.session_state.query_cache = ""

render_light_theme_css()
render_morandi_theme_css()

col1, col2 = st.columns([8, 2])
with col1:
    st.markdown(f'<div class="main-title">{get_text("title")}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="main-subtitle">{get_text("subtitle")}</div>', unsafe_allow_html=True)

col_search_input, col_search_btn = st.columns([10, 1])
with col_search_input:
    query = st.text_input(
        "query",
        placeholder=get_text("search_placeholder"),
        label_visibility="collapsed",
        key="query_input"
    )
with col_search_btn:
    run_button = st.button(get_text("search_button"), key="search_btn")

status_slot = st.empty()

search_mode, model, threads = render_sidebar()

if run_button and query:
    run_search_pipeline(query, search_mode, model, threads, status_slot)

render_briefing_preview()
render_briefing_history()
render_results_panels()
render_download_section()
render_results_detail()
