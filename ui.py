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
from intelnexus.core.ui.styles import render_hermes_theme_css, render_workbench_css, render_status_bar
from intelnexus.core.settings import set as set_config
from config import (
    OLLAMA_BASE_URL, OPENROUTER_BASE_URL, OPENROUTER_API_KEY,
    GOOGLE_API_KEY,
)
from intelnexus.ui.sidebar import render_sidebar
from intelnexus.ui.icons import icon
from intelnexus.ui.search_pipeline import run_search_pipeline, _search_progress_fragment
from intelnexus.ui.results import render_results_panels
from intelnexus.ui.download import render_download_section
from intelnexus.ui.results_detail import render_results_detail
from intelnexus.ui.briefing_viewer import render_briefing_center
from intelnexus.ui.onboarding import render_onboarding
from intelnexus.ui.knowledge_base import render_knowledge_base
from intelnexus.ui import main_tabs
from intelnexus.core.task_runner import get_task_runner

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
render_hermes_theme_css()

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

    # --- 主导航（横向 radio 代替 st.tabs：支持编程式跳页 + 互斥渲染） ---
    nav_tab_keys = [main_tabs.TAB_HOME, main_tabs.TAB_SEARCH, main_tabs.TAB_BRIEFING, main_tabs.TAB_KB]

    # 导航锁：任务运行期间阻止用户切换 Tab（防止 rerun 中断后台任务的结果渲染）
    _runner = get_task_runner()
    _search_running = _runner.is_running("search")
    _briefing_running = _runner.is_running("briefing")
    _any_task_running = _search_running or _briefing_running

    # 激活页计算：优先消费一次性跳转旗标（取证深查等编程式跳页）。
    # radio 选项值直接用 tab 键（显示标签由 format_func 按 i18n 映射），
    # 保证 session_state.main_nav_radio 存的始终是键而非标签文本。
    active = main_tabs.resolve_active_tab(
        st.session_state.get("main_nav_radio") or main_tabs.TAB_HOME,
        st.session_state,
    )

    # 导航锁：任务运行期间锁定在当前 Tab（不允许切换到其他页面）
    if _any_task_running:
        _prev_tab = st.session_state.get("_locked_tab", active)
        if active != _prev_tab:
            # 用户试图切换 Tab → 强制回到锁定的 Tab
            active = _prev_tab
            st.session_state.main_nav_radio = active
        # 显示任务运行提示
        _task_msg = []
        if _search_running:
            _task_msg.append(get_text("task_search_running"))
        if _briefing_running:
            _task_msg.append(get_text("task_briefing_running"))
        st.info(f"{' / '.join(_task_msg)} {get_text('task_running_nav_lock')}")
    else:
        st.session_state["_locked_tab"] = active

    # 被编程跳转改写时，在下一次渲染前同步 radio 选中态（不传 index，避免每次 rerun 重置）
    if st.session_state.get("main_nav_radio") != active:
        st.session_state.main_nav_radio = active

    # 隐藏 marker：供 CSS 把导航 radio 渲染成横向 tab 外观（见 styles.py）
    st.markdown('<div class="main-nav-marker" style="display:none"></div>', unsafe_allow_html=True)
    # 任务运行期间禁用导航 radio 交互
    _nav_disabled = _any_task_running
    st.radio(
        "main navigation",
        nav_tab_keys,
        horizontal=True,
        label_visibility="collapsed",
        key="main_nav_radio",
        format_func=lambda key: get_text(f"nav_{key}"),
        disabled=_nav_disabled,
    )

    # 隐藏作用域 marker：主区稳定锚点，替代旧 div[role="tabpanel"] 选择器外层前缀（见 styles.py）
    st.markdown('<div class="app-main-scope" style="display:none"></div>', unsafe_allow_html=True)

    # =====================
    #  Home（今日概览）
    # =====================
    if active == main_tabs.TAB_HOME:
        # 首页指标卡复用 .hc-card 样式（定义于 render_workbench_css）；
        # 互斥渲染保证同一时刻只有一个分支注入，不会重复注入。
        render_workbench_css()
        from intelnexus.ui.overview import render_overview
        render_overview()

    # =====================
    #  Search Tab
    # =====================
    elif active == main_tabs.TAB_SEARCH:
        # 反向飞轮：从简报条目跳转过来的取证任务（导航已自动切到本页，无需再提示用户手动点 Tab）
        pending_query = st.session_state.pop("pending_forensic_query", None)
        pending_mode = st.session_state.pop("pending_forensic_mode", "all")
        # 简报跳转的预填值写入输入框 session state（控件不再用 value= 回填）
        if pending_query:
            st.session_state.query_input = pending_query

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
                                                   use_container_width=True,
                                                   type="primary")

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

        # 搜索进度轮询 fragment（后台任务运行时显示进度，完成时渲染结果）
        _search_progress_fragment()

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

        # 结果面板（session_state 有数据时渲染，由 fragment 完成后写入）
        if st.session_state.get("filtered") is not None:
            render_results_panels()
            render_download_section()
            render_results_detail()

            # 搜→报飞轮：一键将当前全部搜索结果存入简报草稿
            _render_bulk_collect_button()

    # =====================
    #  Briefing Tab
    # =====================
    elif active == main_tabs.TAB_BRIEFING:
        render_workbench_css()
        render_briefing_center()

    # =====================
    #  Knowledge Base Tab
    # =====================
    elif active == main_tabs.TAB_KB:
        render_workbench_css()
        render_knowledge_base()


# --- Bottom status bar ---
def _collect_status_bar_metrics():
    """组装底部状态栏运行指标：{"health", "scheduler", "today"}。

    聚合层（status_metrics）已内部兜底；此处再包一层 try/except，
    任何异常（含模块不可用）返回 None，状态栏退化为静态渲染。
    onboarding 期间也安全调用。
    """
    try:
        from intelnexus.ui.status_metrics import (
            get_health_summary_cached,
            get_scheduler_summary_cached,
            get_today_stats_cached,
        )
        return {
            "health": get_health_summary_cached(),
            "scheduler": get_scheduler_summary_cached(),
            "today": get_today_stats_cached(),
        }
    except Exception:
        return None


render_status_bar(_collect_status_bar_metrics())
