"""
简报生成控件（共享）
====================
三处「立即生成简报」按钮复用同一套控件：类目多选 + 推送开关 + 模型选择（可选）
+ 生成按钮 + 实时进度 + 结果统计面板。业务逻辑均由 ai_briefing.pipeline 承载。

用法：
    from intelnexus.ui.briefing_runner import render_briefing_generate_controls
    render_briefing_generate_controls(key_prefix="sb", model=model, compact=True)
"""
import streamlit as st

from intelnexus.briefing.pipeline import run_briefing_pipeline
from intelnexus.briefing.config import get_all_categories
from intelnexus.ui.i18n import get_text
from intelnexus.core.llm.utils import get_model_choices


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
            if st.button(
                get_text("generate_briefing"),
                key=f"{key_prefix}_btn",
                type="primary",
                disabled=(model is None),
            ):
                _run_pipeline(
                    key_prefix,
                    st.session_state.get(f"{key_prefix}_model", model),
                    st.session_state.get(f"{key_prefix}_cats", selected_cats),
                    st.session_state.get(f"{key_prefix}_push", push_enabled),
                )

        _render_stats(key_prefix, compact)
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

    if st.button(get_text("generate_briefing"), key=f"{key_prefix}_btn", use_container_width=True, disabled=(model is None)):
        _run_pipeline(key_prefix, model, selected_cats, push_enabled)

    _render_stats(key_prefix, compact)


def _run_pipeline(key_prefix: str, model: str, selected_cats: list, push_enabled: bool):
    if not selected_cats:
        st.warning(get_text("briefing_no_category"))
        return

    progress_bar = st.progress(0.0)
    status = st.status(get_text("briefing_generating"), expanded=True)

    def _ui_progress(_stage: str, message: str, percent=None):
        if percent is not None:
            progress_bar.progress(min(1.0, max(0.0, percent)))
        status.update(label=message, state="running")

    try:
        result = run_briefing_pipeline(
            model=model,
            categories=selected_cats,
            push_enabled=push_enabled,
            org_name=get_text("default_org_name"),
            email_config=st.session_state.get("email_config", None),
            on_progress=_ui_progress,
        )
        progress_bar.progress(1.0)
        status.update(label=get_text("briefing_done"), state="complete")

        st.session_state.current_briefing = result["md"]
        st.session_state[f"{key_prefix}_result"] = result

        if result["warnings"]:
            st.warning(get_text("briefing_partial").format(n=len(result["warnings"])))
    except Exception as e:
        progress_bar.progress(1.0)
        status.update(label=get_text("briefing_failed"), state="error")
        st.error(f"{get_text('briefing_failed')}: {e}")


def _render_stats(key_prefix: str, compact: bool):
    result = st.session_state.get(f"{key_prefix}_result")
    if not result:
        return

    total_items = sum(result["collected_counts"].values())

    with st.container():
        st.markdown('<div class="bf-generate-stats">', unsafe_allow_html=True)
        if compact:
            st.caption(
                f"{get_text('briefing_stat_collected')}: {total_items} · "
                f"{get_text('briefing_stat_words')}: {len(result['md'])} · "
                f"{get_text('briefing_stat_pushed')}: {result['pushed']} · "
                f"{get_text('briefing_stat_elapsed')}: {result['elapsed']}s"
            )  # noqa: E501
        else:
            col1, col2, col3, col4 = st.columns(4)
            col1.metric(get_text("briefing_stat_collected"), total_items)
            col2.metric(get_text("briefing_stat_words"), len(result["md"]))
            col3.metric(get_text("briefing_stat_pushed"), result["pushed"])
            col4.metric(get_text("briefing_stat_elapsed"), f"{result['elapsed']}s")

        if result["warnings"]:
            with st.expander(get_text("briefing_stat_warnings"), expanded=False):
                for w in result["warnings"]:
                    st.caption(f"• {w}")
        st.markdown('</div>', unsafe_allow_html=True)
