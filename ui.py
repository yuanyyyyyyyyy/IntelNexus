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
# Appended (not inserted at 0) so ai_briefing resolves to intel-briefing/ai_briefing/
# without letting intel-briefing/src/ shadow the root-level src/ package.
sys.path.append(os.path.join(_root, "intel-briefing"))

import streamlit as st

st.set_page_config(
    page_title="IntelNexus",
    page_icon=None,
    initial_sidebar_state="expanded",
)

# --- Fixed imports: use real merged modules ---
from src.ui.i18n import get_text
from shared.ui.styles import render_light_theme_css, render_morandi_theme_css, render_workbench_css
from shared.settings import set as set_config
from config import (
    OLLAMA_BASE_URL, OPENROUTER_BASE_URL, OPENROUTER_API_KEY,
    GOOGLE_API_KEY,
)
from src.ui.sidebar import render_sidebar
from src.ui.search_pipeline import run_search_pipeline
from src.ui.results import render_results_panels
from src.ui.download import render_download_section
from src.ui.results_detail import render_results_detail
from src.ui.briefing_viewer import render_briefing_center

# --- Inject config for shared modules ---
set_config({
    "OLLAMA_BASE_URL": OLLAMA_BASE_URL,
    "OPENROUTER_BASE_URL": OPENROUTER_BASE_URL,
    "OPENROUTER_API_KEY": OPENROUTER_API_KEY,
    "GOOGLE_API_KEY": GOOGLE_API_KEY,
})

# --- Initialize session state ---
if "lang" not in st.session_state:
    st.session_state.lang = "zh"
if "query_cache" not in st.session_state:
    st.session_state.query_cache = ""


def _render_bulk_collect_button():
    """搜索 Tab 底部：一键将当前全部结果存入简报草稿。"""
    results = st.session_state.get("filtered") or []
    if not results:
        return
    from src.ui.i18n import get_text
    from src.config.briefing_drafts import add_draft

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button(get_text("collect_all_to_briefing"),
                 key="bulk_collect_btn", use_container_width=True):
        added = 0
        for item in results:
            url = item.get("url") or item.get("link", "")
            if not url:
                continue
            ok = add_draft({
                "title": item.get("title", ""),
                "url": url,
                "content": item.get("content", item.get("description", "")),
                "description": item.get("description", ""),
                "source": item.get("source", "Unknown"),
            })
            if ok:
                added += 1
        if added:
            st.toast(get_text("collect_all_ok").format(n=added))
        else:
            st.toast(get_text("collect_all_dup"))
        st.rerun()

# --- Render theme ---
render_light_theme_css()
render_morandi_theme_css()

# --- Title ---
col1, col2 = st.columns([8, 2])
with col1:
    st.markdown(f'<div class="main-title">{get_text("title")}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="main-subtitle">{get_text("subtitle")}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="main-guidance">{get_text("module_guidance")}</div>', unsafe_allow_html=True)

# --- Sidebar (serves both search mode + briefing management) ---
search_mode, model, threads = render_sidebar()

# --- Tabs ---
if st.session_state.lang == "zh":
    tab_labels = ["情报搜索", "简报中心"]
else:
    tab_labels = ["Intel Search", "Briefing"]
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

    # 搜→报飞轮：一键将当前全部搜索结果存入简报草稿
    _render_bulk_collect_button()

# =====================
#  Briefing Tab
# =====================
with tab_briefing:
    render_workbench_css()
    render_briefing_center()
