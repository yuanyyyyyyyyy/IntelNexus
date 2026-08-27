"""
搜索管线入口（后台执行 + fragment 轮询）
=============================================
本模块是搜索管线的入口层，负责：
- 启动后台计算任务（TaskRunner + search_worker）
- 通过 @st.fragment(auto_rerun=1s) 轮询进度
- 任务完成后将结果写入 session_state 并渲染 UI

计算逻辑已提取至 search_worker.py（纯函数，线程安全）。
原管线中的 st.status / st.empty / st.markdown 等 UI 操作
统一在 fragment 完成态中渲染。
"""

import html
import re
import streamlit as st
from datetime import datetime, timedelta

from intelnexus.core.logger import get_logger
from intelnexus.core.task_runner import get_task_runner
from intelnexus.ui.i18n import get_text
from intelnexus.ui.icons import icon

logger = get_logger(__name__)

# 后台任务 ID
_SEARCH_TASK_ID = "search"


def _start_search_task(query: str, search_mode: str, model: str, threads: int):
    """启动后台搜索任务。

    在主线程中读取必要的 session_state 参数，然后启动后台线程执行搜索管线。
    """
    runner = get_task_runner()
    if runner.is_running(_SEARCH_TASK_ID):
        return  # 已在运行，不重复提交

    # 智能路由：sidebar 返回的 "smart" 在此解析
    from intelnexus.core.search.modes import SMART_MODE_KEY, resolve_mode
    effective_mode = search_mode
    if effective_mode == SMART_MODE_KEY:
        effective_mode = resolve_mode(query)

    advanced_mode = st.session_state.get("advanced_mode", False)
    tor_port = st.session_state.get("tor_port", 9050)
    ui_sites = st.session_state.get("custom_onion_sites", [])

    from intelnexus.ui.search_worker import run_search_computation

    ok = runner.start(_SEARCH_TASK_ID, run_search_computation, kwargs={
        "query": query,
        "search_mode": effective_mode,
        "model": model,
        "threads": threads,
        "advanced_mode": advanced_mode,
        "tor_port": tor_port,
        "ui_sites": ui_sites,
    })

    if ok:
        # 记录查询信息供 fragment 渲染使用
        st.session_state.search_query = query
        st.session_state.search_mode = effective_mode
        st.session_state.query_cache = query
        st.session_state.model_cache = model
        # 清除上一轮结果（避免显示旧数据）
        for k in ["refined", "results", "filtered", "scraped", "streamed_summary",
                   "credibility_data", "conflicts", "kg_entities", "kg_relations",
                   "kg_html_path", "kg_context", "evidence_data", "action_items",
                   "source_stats", "source_counts", "source_info"]:
            st.session_state.pop(k, None)
        st.session_state.search_completed = False
        # 同简报：启动后立即 rerun，让导航锁和侧边栏提示立即生效
        st.rerun()


def run_search_pipeline(query: str, search_mode: str, model: str, threads: int, status_slot):
    """搜索管线入口。

    启动后台搜索任务。进度和结果由 _search_progress_fragment 轮询渲染。
    status_slot 用于显示启动前的即时提示（如模型不可用）。
    """
    # 模型为空检查
    if not model:
        logger.warning("搜索中止：未配置可用模型")
        status_slot.error(get_text("no_model_error"))
        st.session_state.search_completed = False
        return

    # 空查询检查
    if not query or not query.strip():
        status_slot.warning(get_text("search_placeholder"))
        return

    # 启动后台任务
    _start_search_task(query.strip(), search_mode, model, threads)


@st.fragment(run_every=timedelta(seconds=1))
def _search_progress_fragment(status_slot_key: str = ""):
    """搜索进度轮询 fragment。

    任务运行中：每秒 auto_rerun 显示进度阶段。
    任务完成：将结果写入 session_state，渲染完整搜索结果。
    任务失败：显示错误信息。
    """
    runner = get_task_runner()
    state = runner.get_snapshot(_SEARCH_TASK_ID)
    status = state["status"]

    if status == "running":
        # 进度显示
        progress_pct = state.get("progress", 0.0)
        message = state.get("message", "搜索中...")
        phase = state.get("phase", "")

        # 阶段图标映射
        phase_icons = {
            "preflight": "🔍", "refining": "🧠", "searching": "🌐",
            "ranking": "📊", "scraping": "📄", "kb_retrieval": "📚",
            "analyzing": "⚖️", "generating": "✍️", "evidence": "🔗",
            "finalizing": "🏁", "done": "✅",
        }
        phase_emoji = phase_icons.get(phase, "⏳")

        st.progress(min(1.0, max(0.0, progress_pct)))
        st.markdown(
            f'<div class="result-card">'
            f'<div class="section-header">{get_text("searching")}</div>'
            f'<div style="padding:8px 0;">'
            f'{phase_emoji} <strong>{message}</strong>'
            f' <span style="float:right;color:var(--wb-text-secondary);">{int(progress_pct*100)}%</span>'
            f'</div></div>',
            unsafe_allow_html=True,
        )
        return

    if status == "completed":
        result = state.get("result", {})
        if result:
            _apply_search_results(result)
            _render_search_results_ui(result)
        # 重置任务状态
        runner.reset(_SEARCH_TASK_ID)
        return

    if status == "failed":
        error_msg = state.get("error", "未知错误")
        st.error(f"{get_text('search_failed')}: {error_msg}")
        st.session_state.search_completed = False
        runner.reset(_SEARCH_TASK_ID)
        return

    # idle：不显示任何内容（fragment 不应在空闲时 auto_rerun）


def _apply_search_results(result: dict):
    """将后台任务的计算结果写入 session_state。

    在主线程中执行（fragment 内），保证 session_state 写入安全。
    """
    if result.get("success"):
        # 写入搜索结果到 session_state
        for key in ["refined", "results", "filtered", "scraped", "streamed_summary",
                     "credibility_data", "conflicts", "kg_entities", "kg_relations",
                     "kg_html_path", "kg_context", "evidence_data", "action_items",
                     "source_stats", "report_timestamp"]:
            if key in result and result[key] is not None:
                st.session_state[key] = result[key]

        # 特殊处理：source_counts / source_info 用于统计展示
        if "source_counts" in result:
            st.session_state["source_counts"] = result["source_counts"]
        if "source_info" in result:
            st.session_state["source_info"] = result["source_info"]

        st.session_state.search_completed = True
        st.session_state.export_format_choice = "md"
    else:
        st.session_state.search_completed = False


def _render_search_results_ui(result: dict):
    """渲染搜索结果的完整 UI（在 fragment 完成态中执行）。

    包含：查询信息卡、源统计、透明度条、弱相关折叠、报告、TL;DR 卡等。
    逻辑与原 search_pipeline.py 的渲染部分一致。
    """
    if not result.get("success"):
        if result.get("error"):
            st.error(result["error"])
        return

    query = result.get("query", "")
    results = result.get("results", [])
    results_count = len(results)
    source_info = result.get("source_info", "")
    source_stats = result.get("source_stats", {})

    # 查询优化展示
    st.markdown(f"""
    <div class="result-card">
        <div class="section-header">{get_text("refined_query")}</div>
        <div class="result-title">{get_text("original_query")} {html.escape(query)}</div>
    </div>
    """, unsafe_allow_html=True)

    # 结果统计卡
    st.markdown(f"""
    <div class="result-card">
        <div class="result-stats">
            <div class="stat-item">
                <div class="stat-value">{results_count}</div>
                <div class="stat-label">{get_text("results_count")}</div>
            </div>
        </div>
        <div class="stat-label" style="margin-top: 10px;">{get_text("data_source_label")} {html.escape(source_info)}</div>
    </div>
    """, unsafe_allow_html=True)

    # 源完整性透明度条
    if source_stats:
        ok_sources = [n for n, s in source_stats.items() if s.get("status") == "ok"]
        skipped = [(n, s.get("status")) for n, s in source_stats.items()
                   if s.get("status") != "ok"]
        if skipped:
            reason_map = {"timeout": get_text("src_skip_timeout"),
                          "no_proxy": get_text("src_skip_no_proxy"),
                          "error": get_text("src_skip_error"),
                          "skipped": get_text("src_skip_skipped")}
            detail = ", ".join(f"{n} ({reason_map.get(s, s)})"
                               for n, s in skipped)
            st.info(get_text("source_integrity").format(
                ok=len(ok_sources), skip=len(skipped)) +
                f" <sub>{html.escape(detail[:200])}</sub>")
        else:
            st.success(get_text("all_sources_ok").format(ok=len(ok_sources)))

    # 零结果处理
    if result.get("zero_results"):
        if result.get("all_failed"):
            st.error(get_text("search_all_failed"))
        else:
            st.warning(get_text("no_results"))
        return

    # 弱相关折叠展示
    weak_results = result.get("weak_results", [])
    if weak_results:
        with st.expander(get_text("weak_related_expander").format(n=len(weak_results))):
            for wr in weak_results:
                _wscore = wr.get("relevance_score", 0.0)
                st.markdown(
                    f"- [{_wscore:.2f}] {html.escape(str(wr.get('title', ''))[:70])} "
                    f"({html.escape(str(wr.get('source', '')))})")

    # 报告标题
    st.markdown(f"""
    <div class="report-section">
        <div class="report-title">{get_text("report_title")}</div>
    </div>
    """, unsafe_allow_html=True)

    # 报告全文
    report = result.get("streamed_summary", "")
    if report:
        st.markdown(report)

    # TL;DR 速览卡
    tldr = result.get("tldr_card", "")
    if tldr:
        _escaped = html.escape(tldr)
        _escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", _escaped)
        _escaped = re.sub(r"(?m)^- ", "• ", _escaped)
        st.markdown(
            f'<div class="tldr-card" style="background:var(--bg-card);border-radius:8px;'
            f'padding:16px;margin-bottom:16px;border-left:4px solid var(--border-light);">'
            f'{_escaped.replace(chr(10), "<br>")}</div>',
            unsafe_allow_html=True,
        )

    # 完成提示
    st.success(get_text("complete"))
