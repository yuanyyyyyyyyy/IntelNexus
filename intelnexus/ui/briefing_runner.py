"""
简报生成控件（共享 · 后台执行版）
==================================
三处「立即生成简报」按钮复用同一套控件：类目多选 + 推送开关 + 模型选择（可选）
+ 生成按钮 + 后台进度轮询 + 结果统计面板。

业务逻辑由 ai_briefing.pipeline 承载，本模块负责：
- 启动后台线程执行管线（TaskRunner）
- 通过 @st.fragment(auto_rerun=1s) 轮询进度
- 完成后渲染结果统计

用法：
    from intelnexus.ui.briefing_runner import render_briefing_generate_controls
    render_briefing_generate_controls(key_prefix="sb", model=model, compact=True)
"""
import streamlit as st
from datetime import timedelta

from intelnexus.briefing.pipeline import run_briefing_pipeline
from intelnexus.briefing.config import get_all_categories
from intelnexus.core.task_runner import get_task_runner
from intelnexus.ui.i18n import get_text
from intelnexus.core.llm.utils import get_model_choices

# 后台任务 ID（全局唯一，三处按钮共用同一个 briefing 任务槽）
_BRIEFING_TASK_ID = "briefing"


def _category_options() -> dict:
    return {cid: cfg.get("name", cid) for cid, cfg in get_all_categories().items()}


def render_briefing_generate_controls(key_prefix: str, model: str = None, compact: bool = False, top: bool = False):
    """
    渲染生成控件与结果统计。

    Args:
        key_prefix: 控件 key 前缀，三处必须不同（如 "sb" / "quick" / "bf"）
        model: 已选定的模型；为 None 时本控件内提供一个紧凑选择器
        compact: 侧边栏宽度下用紧凑统计（caption），否则用 metrics 四宫格
        top: 置顶主操作模式。True 时类目多选 + 推送开关 + 生成按钮横向同一行，
             模型选择收进「高级」expander；False 时保持原纵向块布局
    """
    cat_options = _category_options()
    runner = get_task_runner()
    is_running = runner.is_running(_BRIEFING_TASK_ID)

    if top:
        # 置顶主操作：左侧「已选概览 + 选项折叠」，右侧「生成简报」主按钮，单行对齐
        selected_cats = st.session_state.get(
            f"{key_prefix}_cats",
            list(cat_options.keys()),
        )
        push_enabled = st.session_state.get(f"{key_prefix}_push", True)
        if model is None:
            model_options = get_model_choices()
            if not model_options:
                st.info(get_text("no_model_hint"))
                model = None
            else:
                model = st.session_state.get(f"{key_prefix}_model", model_options[0])

        col_summary, col_btn = st.columns([1, 1])
        with col_summary:
            summary_label = get_text("generate_summary").format(
                n=len(selected_cats), total=len(cat_options)
            )
            with st.expander(summary_label, expanded=False):
                st.multiselect(
                    get_text("select_categories"),
                    options=list(cat_options.keys()),
                    default=selected_cats,
                    format_func=lambda c: cat_options[c],
                    key=f"{key_prefix}_cats",
                    label_visibility="collapsed",
                )
                st.checkbox(
                    get_text("generate_push_enabled"),
                    value=push_enabled,
                    key=f"{key_prefix}_push",
                )
                if model is None:
                    m_opts = get_model_choices()
                    if not m_opts:
                        st.info(get_text("no_model_hint"))
                    else:
                        st.selectbox(get_text("llm_model"), m_opts, index=0, key=f"{key_prefix}_model")
        with col_btn:
            # 隐藏 marker：让 CSS 能稳定命中本列按钮（Streamlit 的 DOM 顺序不可靠）
            st.markdown('<div class="bf-gen-btn-marker" style="display:none"></div>', unsafe_allow_html=True)
            btn_disabled = (model is None) or is_running
            btn_label = get_text("briefing_running") if is_running else get_text("generate_briefing")
            if st.button(
                btn_label,
                key=f"{key_prefix}_btn",
                type="primary",
                disabled=btn_disabled,
            ):
                _start_background_pipeline(
                    key_prefix,
                    st.session_state.get(f"{key_prefix}_model", model),
                    st.session_state.get(f"{key_prefix}_cats", selected_cats),
                    st.session_state.get(f"{key_prefix}_push", push_enabled),
                )

        # 进度/结果 fragment
        _briefing_progress_fragment(key_prefix, compact)
        return

    selected_cats = st.multiselect(
        get_text("select_categories"),
        options=list(cat_options.keys()),
        default=list(cat_options.keys()),
        format_func=lambda c: cat_options[c],
        key=f"{key_prefix}_cats",
    )

    push_enabled = st.checkbox(
        get_text("generate_push_enabled"),
        value=True,
        key=f"{key_prefix}_push",
    )

    if model is None:
        model_options = get_model_choices()
        if not model_options:
            st.info(get_text("no_model_hint"))
            model = None
        else:
            model = st.selectbox(get_text("llm_model"), model_options, index=0, key=f"{key_prefix}_model")

    btn_disabled = (model is None) or is_running
    btn_label = get_text("briefing_running") if is_running else get_text("generate_briefing")
    if st.button(btn_label, key=f"{key_prefix}_btn", use_container_width=True, disabled=btn_disabled):
        _start_background_pipeline(key_prefix, model, selected_cats, push_enabled)

    # 进度/结果 fragment
    _briefing_progress_fragment(key_prefix, compact)


def _start_background_pipeline(key_prefix: str, model: str, selected_cats: list, push_enabled: bool):
    """启动后台简报生成管线。

    将 run_briefing_pipeline 包入 worker 函数，通过 TaskRunner 在后台线程执行。
    进度通过 TaskRunner 状态暴露，UI 由 _briefing_progress_fragment 轮询渲染。
    """
    if not selected_cats:
        st.warning(get_text("briefing_no_category"))
        return

    runner = get_task_runner()
    if runner.is_running(_BRIEFING_TASK_ID):
        st.info(get_text("briefing_running"))
        return

    # 在主线程中预先解析邮件配置（避免后台线程访问文件系统的边界问题）
    try:
        from intelnexus.config.email_settings import get_active_email_config
        email_config = get_active_email_config()
    except Exception:
        email_config = {}

    org_name = get_text("default_org_name")

    def _worker(progress_cb, **kwargs):
        """后台 worker：桥接 pipeline 的 on_progress 到 TaskRunner 的 progress_callback。"""
        def _on_progress(stage: str, message: str, percent=None):
            progress_cb(stage, message, percent if percent is not None else 0.0)

        result = run_briefing_pipeline(
            model=kwargs["model"],
            categories=kwargs["selected_cats"],
            push_enabled=kwargs["push_enabled"],
            org_name=kwargs["org_name"],
            email_config=kwargs["email_config"],
            on_progress=_on_progress,
        )
        return result

    ok = runner.start(_BRIEFING_TASK_ID, _worker, kwargs={
        "model": model,
        "selected_cats": selected_cats,
        "push_enabled": push_enabled,
        "org_name": org_name,
        "email_config": email_config,
    })

    if ok:
        # 记录 key_prefix 供 fragment 渲染结果时写入正确的 session_state 键
        st.session_state[f"{_BRIEFING_TASK_ID}_key_prefix"] = key_prefix
        # 启动后立即触发整页 rerun：让导航锁、按钮文字、侧边栏提示等
        # 在按钮点击前渲染的组件能读到「任务已运行」的最新状态。
        # 不 rerun 的话，这些组件在本次执行中已计算完毕（状态为旧值），
        # 只有 fragment 能实时更新，用户必须切换页面才能看到完整状态。
        st.rerun()
    else:
        st.info(get_text("briefing_running"))


@st.fragment(run_every=timedelta(seconds=1))
def _briefing_progress_fragment(key_prefix: str, compact: bool):
    """简报进度轮询 fragment。

    任务运行中：每秒自动 rerun 显示最新进度。
    任务完成：渲染结果统计，停止 auto_rerun。
    任务失败：显示错误信息。
    无任务：渲染上一轮结果（如有）。
    """
    runner = get_task_runner()
    state = runner.get_snapshot(_BRIEFING_TASK_ID)
    status = state["status"]

    if status == "running":
        # 进度显示（卡片式，与搜索进度 UI 一致）
        progress_pct = state.get("progress", 0.0)
        message = state.get("message", get_text("briefing_generating"))
        phase = state.get("phase", "")

        # 阶段图标映射
        phase_icons = {
            "starting": "\u23f3",
            "collect_start": "\U0001f4e1",
            "collect_done": "\u2705",
            "credibility_overview": "\U0001f6e1\ufe0f",
            "knowledge_graph": "\U0001f578\ufe0f",
            "kb_recall": "\U0001f4da",
            "generate_start": "\u270d\ufe0f",
            "generate_progress": "\u270d\ufe0f",
            "llm_error": "\u26a0\ufe0f",
            "llm_skipped": "\u26a0\ufe0f",
            "summary": "\U0001f4dd",
            "save": "\U0001f4be",
            "save_entries": "\U0001f4be",
            "push": "\U0001f4e4",
            "push_done": "\u2705",
            "push_no_subs": "\u2705",
            "push_skipped": "\u2705",
        }
        phase_emoji = phase_icons.get(phase, "\u23f3")

        st.progress(min(1.0, max(0.0, progress_pct)))
        st.markdown(
            f'<div class="result-card">'
            f'<div class="section-header">{get_text("briefing_generating")}</div>'
            f'<div style="padding:8px 0;">'
            f'{phase_emoji} <strong>{message}</strong>'
            f' <span style="float:right;color:var(--wb-text-secondary);">{int(progress_pct*100)}%</span>'
            f'</div></div>',
            unsafe_allow_html=True,
        )
        # fragment 将 auto_rerun 继续轮询
        return

    if status == "completed":
        result = state.get("result", {})
        if result:
            # 写入 session_state 供 briefing_preview 等下游使用
            st.session_state.current_briefing = result.get("md", "")
            st.session_state[f"{key_prefix}_result"] = result
            # 渲染统计
            _render_stats(key_prefix, compact, result)
            # 显示警告
            warnings = result.get("warnings", [])
            if warnings:
                st.warning(get_text("briefing_partial").format(n=len(warnings)))
        # 重置任务状态（只消费一次结果）
        runner.reset(_BRIEFING_TASK_ID)
        return

    if status == "failed":
        error_msg = state.get("error", "未知错误")
        st.error(f"{get_text('briefing_failed')}: {error_msg}")
        # 重置失败状态
        runner.reset(_BRIEFING_TASK_ID)
        return

    # idle 状态：渲染上一轮缓存结果（如有）
    _render_stats(key_prefix, compact)


def _render_stats(key_prefix: str, compact: bool, result: dict = None):
    """渲染结果统计（四宫格或紧凑文本）。

    result 为 None 时从 session_state 读取（兼容旧逻辑）。
    """
    if result is None:
        result = st.session_state.get(f"{key_prefix}_result")
    if not result:
        return

    total_items = sum(result.get("collected_counts", {}).values())

    # 用 st.container 替代手动 <div>：Streamlit widget（columns/metric）
    # 会被正确渲染在 container 内部，而非作为 div 的兄弟元素。
    # CSS 通过 [data-key="bf-stats-{key_prefix}"] 定位容器样式。
    with st.container(key=f"bf-stats-{key_prefix}"):
        if compact:
            st.caption(
                f"{get_text('briefing_stat_collected')}: {total_items} · "
                f"{get_text('briefing_stat_words')}: {len(result.get('md', ''))} · "
                f"{get_text('briefing_stat_pushed')}: {result.get('pushed', 0)} · "
                f"{get_text('briefing_stat_elapsed')}: {result.get('elapsed', 0)}s"
            )
        else:
            col1, col2, col3, col4 = st.columns(4)
            col1.metric(get_text("briefing_stat_collected"), total_items)
            col2.metric(get_text("briefing_stat_words"), len(result.get("md", "")))
            col3.metric(get_text("briefing_stat_pushed"), result.get("pushed", 0))
            col4.metric(get_text("briefing_stat_elapsed"), f"{result.get('elapsed', 0)}s")

        warnings = result.get("warnings", [])
        if warnings:
            with st.expander(get_text("briefing_stat_warnings"), expanded=False):
                for w in warnings:
                    st.caption(f"• {w}")
