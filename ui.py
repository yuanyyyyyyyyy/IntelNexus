"""
IntelNexus Unified Streamlit UI
===============================
Combines search and briefing UI from sub-projects.
"""

import os
import sys
import logging

logger = logging.getLogger(__name__)

# Ensure root project dir resolves first so root-level config.py and the
# intelnexus/ package are importable. Single-package layout removes the old
# sys.path hacks that worked around duplicated sub-project modules.
_root = os.path.dirname(os.path.abspath(__file__))
if _root not in sys.path:
    sys.path.insert(0, _root)

import streamlit as st

st.set_page_config(
    page_title="IntelNexus",
    page_icon=None,
    initial_sidebar_state="expanded",
)

# --- Fixed imports: use real merged modules ---
from intelnexus.ui.i18n import get_text
from intelnexus.core.ui.styles import render_light_theme_css, render_morandi_theme_css, render_workbench_css
from intelnexus.core.settings import set as set_config
from config import (
    OLLAMA_BASE_URL, OPENROUTER_BASE_URL, OPENROUTER_API_KEY,
    GOOGLE_API_KEY,
)
from intelnexus.ui.sidebar import render_sidebar
from intelnexus.ui.icons import icon
from intelnexus.ui.search_pipeline import run_search_pipeline
from intelnexus.ui.results import render_results_panels
from intelnexus.ui.download import render_download_section
from intelnexus.ui.results_detail import render_results_detail
from intelnexus.ui.briefing_viewer import render_briefing_center
from intelnexus.ui.onboarding import render_onboarding
from intelnexus.ui.knowledge_base import render_knowledge_base
from intelnexus.ui import main_tabs

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
    """搜索 Tab 底部：一键将当前全部结果存入简报草稿；
    可选「固化为常驻关注点（Topic）」，让本次查询进入简报自动巡防——实现搜→报双向飞轮。"""
    results = st.session_state.get("filtered") or []
    if not results:
        return
    from intelnexus.ui.i18n import get_text
    from intelnexus.config.briefing_drafts import add_draft
    from intelnexus.topics.store import add_topic
    from intelnexus.topics.registry import Topic

    st.markdown("<br>", unsafe_allow_html=True)
    pin = st.checkbox(get_text("pin_as_topic"), key="pin_as_topic",
                      help=get_text("pin_as_topic_help"))
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

        # 双向飞轮：把当前查询固化为常驻 Topic，纳入简报巡防
        if pin:
            query = (st.session_state.get("query_input")
                     or st.session_state.get("query_cache") or "").strip()
            if query:
                from datetime import datetime
                tid = "u_" + datetime.now().strftime("%Y%m%d%H%M%S%f")
                topic = Topic(
                    id=tid,
                    name=query[:40],
                    description=get_text("topic_from_search").format(q=query),
                    search_queries=[query],
                    keywords_en=[query],
                    keywords_zh=[query],
                    origin="user_search",
                    created_at=datetime.now().isoformat(),
                )
                if add_topic(topic):
                    st.toast(get_text("topic_pinned").format(q=query))
        st.rerun()

# --- Render theme ---
render_morandi_theme_css()

# Theme bootstrap: server knows the persisted choice (theme_choice.json),
# so no client-side storage read is needed. The iframe script applies it
# to the top document (st.iframe embeds via srcdoc, same-origin).
def _apply_saved_theme():
    try:
        import json as _json
        with open("data/theme_choice.json", encoding="utf-8") as _f:
            _th = (_json.load(_f) or {}).get("theme")
    except Exception:
        return
    if _th:
        # st.iframe embeds HTML strings via srcdoc and allows same-origin
        # access, so window.parent.document reaches the real app document.
        st.iframe(
            "<script>window.parent.document.documentElement"
            ".setAttribute('data-theme','" + str(_th) + "');</script>",
            height=0)


_apply_saved_theme()

# --- Check for onboarding ---
onboarding_active = render_onboarding()

# --- First-run model setup hint (no LLM configured yet) ---
if not onboarding_active:
    from intelnexus.ui.model_setup_wizard import render_model_setup_hint
    render_model_setup_hint()

# --- Inject icon CSS ---
from intelnexus.ui.icons import render_icon_css
render_icon_css()

# --- Title (only show when not in onboarding) ---
if not onboarding_active:
    col1, col2 = st.columns([8, 2])
    with col1:
        st.markdown(f'<div class="main-title">{get_text("title")}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="main-subtitle">{get_text("subtitle")}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="main-guidance">{get_text("module_guidance")}</div>', unsafe_allow_html=True)

    # --- Sidebar (serves both search mode + briefing management) ---
    search_mode, model, threads = render_sidebar()

    # --- Tabs ---
    if st.session_state.lang == "zh":
        tab_labels = ["情报搜索", "简报中心", "知识库"]
    else:
        tab_labels = ["Intel Search", "Briefing", "Knowledge Base"]
    tab_search, tab_briefing, tab_kb = st.tabs(tab_labels)

    # =====================
    #  Search Tab
    # =====================
    with tab_search:
        # 反向飞轮：从简报条目跳转过来的取证任务
        pending_query = st.session_state.pop("pending_forensic_query", None)
        pending_mode = st.session_state.pop("pending_forensic_mode", "all")
        # 简报跳转的预填值写入输入框 session state（控件不再用 value= 回填）
        if pending_query:
            st.session_state.query_input = pending_query
            # 显示切换提示
            st.info(f"{icon('investigate', 'sm', 'blue')} 已准备取证分析：**{pending_query}** ← 请点击「情报搜索」Tab查看")

        # 用 st.form 包裹输入框与提交按钮：表单提交时所有 widget 值会先同步到
        # session_state，再触发 rerun，从而彻底解决"点按钮时输入框值未提交"的问题。
        with st.form(key="search_form", clear_on_submit=False):
            # [6,1]：按钮占 ~14% 宽，「情报搜索」四字不再挤压换行（旧 [10,1] 仅 ~9%）
            col_search_input, col_search_btn = st.columns([6, 1])
            with col_search_input:
                query = st.text_input(
                    "query",
                    placeholder=get_text("search_placeholder"),
                    label_visibility="collapsed",
                    key="query_input",
                )
            with col_search_btn:
                run_button = st.form_submit_button(get_text("search_button"),
                                                   use_container_width=True)

        status_slot = st.empty()

        # 表单提交后 session_state.query_input 已是最新输入值
        live_query = st.session_state.get("query_input", query or "").strip()
        effective_query = live_query or (query or "").strip()

        logger.debug(
            f"run_button={run_button!r}, query={query!r}, "
            f"live_query={live_query!r}, pending_query={pending_query!r}, model={model!r}"
        )

        # 来自简报的取证任务：自动触发搜索
        if pending_query and not (run_button and effective_query):
            run_search_pipeline(pending_query, pending_mode, model, threads, status_slot)
        elif run_button and effective_query:
            run_search_pipeline(effective_query, search_mode, model, threads, status_slot)
        elif run_button and not effective_query:
            # 兜底：点了搜索但关键词为空，给出可见提示而非静默无反应
            status_slot.warning(get_text("search_placeholder"))

        # 搜索→简报订阅提示：检查当前查询是否已订阅为Topic
        if effective_query:
            from intelnexus.topics.store import find_by_query, add_topic
            from intelnexus.topics.registry import Topic
            import hashlib

            existing_topic = find_by_query(effective_query)
            if existing_topic:
                st.success(get_text("topic_subscribed").format(name=existing_topic.name))
            elif st.session_state.get("filtered"):  # 有搜索结果时才显示订阅提示
                with st.container():
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.info(get_text("topic_subscribe_prompt"))
                    with col2:
                        if st.button(get_text("topic_subscribe_btn"), key="subscribe_topic_btn"):
                            topic_id = f"topic_{hashlib.md5(effective_query.encode()).hexdigest()[:8]}"
                            new_topic = Topic(
                                id=topic_id,
                                name=effective_query[:50],
                                description=f"用户搜索沉淀：{effective_query}",
                                search_queries=[effective_query],
                                keywords_zh=[effective_query],
                                keywords_en=[effective_query],
                                origin="user_search",
                            )
                            if add_topic(new_topic):
                                st.success(get_text("topic_subscribe_success"))
                                st.rerun()

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

    # =====================
    #  Knowledge Base Tab
    # =====================
    with tab_kb:
        render_workbench_css()
        render_knowledge_base()
