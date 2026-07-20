"""
IntelNexus Unified Streamlit UI
===============================
Combines search and briefing UI from sub-projects.
"""

import os
import sys

# Add sub-projects and shared to path (required by internal imports)
_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_root, "shared"))
sys.path.insert(0, os.path.join(_root, "intel-search"))
sys.path.insert(0, os.path.join(_root, "intel-briefing"))

import streamlit as st

st.set_page_config(
    page_title="IntelNexus",
    page_icon=None,
    initial_sidebar_state="expanded",
)

# --- Fixed imports: use real merged modules ---
from src.ui.i18n import get_text
from shared.ui.styles import render_light_theme_css, render_morandi_theme_css
from src.ui.sidebar import render_sidebar
from src.ui.search_pipeline import run_search_pipeline
from src.ui.results import render_results_panels
from src.ui.download import render_download_section
from src.ui.results_detail import render_results_detail
from src.ui.briefing_viewer import render_briefing_preview, render_briefing_history

# --- Initialize session state ---
if "lang" not in st.session_state:
    st.session_state.lang = "zh"
if "query_cache" not in st.session_state:
    st.session_state.query_cache = ""

# --- Render theme ---
render_light_theme_css()
render_morandi_theme_css()

# --- Title ---
col1, col2 = st.columns([8, 2])
with col1:
    st.markdown(f'<div class="main-title">{get_text("title")}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="main-subtitle">{get_text("subtitle")}</div>', unsafe_allow_html=True)

# --- Sidebar (serves both search mode + briefing management) ---
search_mode, model, threads = render_sidebar()

# --- Tabs ---
if st.session_state.lang == "zh":
    tab_labels = ["🔍 情报搜索", "📊 简报中心"]
else:
    tab_labels = ["🔍 Intel Search", "📊 Briefing"]
tab_search, tab_briefing = st.tabs(tab_labels)

# =====================
#  Search Tab
# =====================
with tab_search:
    col_search_input, col_search_btn = st.columns([10, 1])
    with col_search_input:
        query = st.text_input(
            "query",
            placeholder=get_text("search_placeholder"),
            label_visibility="collapsed",
            key="query_input",
        )
    with col_search_btn:
        run_button = st.button(get_text("search_button"), key="search_btn")

    status_slot = st.empty()

    if run_button and query:
        run_search_pipeline(query, search_mode, model, threads, status_slot)

    render_results_panels()
    render_download_section()
    render_results_detail()

# =====================
#  Briefing Tab
# =====================
with tab_briefing:
    if st.session_state.get("show_briefing_history"):
        render_briefing_history()
    else:
        render_briefing_preview()
