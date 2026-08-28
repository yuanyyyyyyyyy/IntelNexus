"""
搜索历史面板
=============
在搜索 Tab 无结果时展示可回溯的历史记录列表。
点击条目可重新执行该次搜索；支持一键清除全部历史。
"""

import html
from datetime import datetime

import streamlit as st

from intelnexus.ui.i18n import get_text
from intelnexus.ui.icons import icon


# ---------------------------------------------------------------------------
# 相对时间
# ---------------------------------------------------------------------------

def _relative_time(iso_ts: str) -> str:
    """将 ISO 时间戳转为人类可读的相对时间字符串。"""
    try:
        dt = datetime.fromisoformat(iso_ts)
    except Exception:
        return ""

    now = datetime.now()
    diff = now - dt
    seconds = int(diff.total_seconds())

    if seconds < 60:
        return get_text("search_history_agojust")
    minutes = seconds // 60
    if minutes < 60:
        return get_text("search_history_ago_min").format(n=minutes)
    hours = minutes // 60
    if hours < 24:
        return get_text("search_history_ago_hour").format(n=hours)
    days = hours // 24
    return get_text("search_history_ago_day").format(n=days)


# ---------------------------------------------------------------------------
# 模式标签
# ---------------------------------------------------------------------------

def _mode_label(mode: str) -> str:
    """将内部模式键映射为 i18n 显示标签。"""
    _MODE_I18N_MAP = {
        "all": "mode_all",
        "web": "mode_web",
        "news": "mode_news",
        "darkweb": "mode_darkweb",
        "threat": "mode_threat",
        "smart": "mode_smart",
        "smart_general": "mode_smart",
    }
    i18n_key = _MODE_I18N_MAP.get(mode, mode)
    label = get_text(i18n_key)
    # get_text 找不到时返回 key 本身，若 key 含 mode_ 前缀则剥离
    if label == i18n_key and i18n_key.startswith("mode_"):
        return i18n_key[5:]
    return label


# ---------------------------------------------------------------------------
# 主渲染
# ---------------------------------------------------------------------------

def render_search_history():
    """渲染搜索历史面板。

    仅在以下条件全部满足时显示：
    - 没有正在运行的搜索任务
    - 当前没有搜索结果（filtered 为空/None）
    """
    # 有搜索结果时不显示历史
    if st.session_state.get("filtered"):
        return
    # 搜索任务运行中不显示
    from intelnexus.core.task_runner import get_task_runner
    if get_task_runner().is_running("search"):
        return

    from intelnexus.config.history import get_history_manager
    history_mgr = get_history_manager()
    entries = history_mgr.get_history(limit=20)

    # 标题行：图标 + 标题 + 清除按钮
    header_html = f"""
    <div class="sh-header">
        <div class="sh-title-row">
            {icon('history', size='sm', color='blue')}
            <span class="sh-title">{get_text('search_history_title')}</span>
            <span class="sh-count">{len(entries)}</span>
        </div>
    </div>
    """
    st.markdown(header_html, unsafe_allow_html=True)

    if not entries:
        st.markdown(
            f'<div class="sh-empty">{icon("search", "sm", "gray")} '
            f'{get_text("search_history_empty")}</div>',
            unsafe_allow_html=True,
        )
        return

    # 清除按钮（放在标题行右侧）
    col_list, col_clear = st.columns([5, 1])
    with col_clear:
        if st.button(
            get_text("search_history_clear"),
            key="sh_clear_btn",
            type="secondary",
            use_container_width=True,
        ):
            st.session_state["_sh_confirm_clear"] = True
            st.rerun()

    # 二次确认
    if st.session_state.pop("_sh_confirm_clear", False):
        st.warning(get_text("search_history_clear_confirm"))
        col_confirm, col_cancel, _ = st.columns([1, 1, 4])
        with col_confirm:
            if st.button(get_text("delete"), key="sh_confirm_yes", use_container_width=True):
                history_mgr.clear_history()
                st.session_state.pop("_sh_confirm_clear", None)
                st.toast(get_text("search_history_cleared"))
                st.rerun()
        with col_cancel:
            if st.button(get_text("cancel_edit"), key="sh_confirm_no", use_container_width=True):
                st.session_state.pop("_sh_confirm_clear", None)
                st.rerun()

    # 历史列表
    with col_list:
        for idx, entry in enumerate(entries):
            _render_history_entry(entry, idx)


def _render_history_entry(entry: dict, idx: int):
    """渲染单条搜索历史记录。"""
    query = html.escape(entry.get("query", ""))
    mode = entry.get("mode", "")
    count = entry.get("results_count", 0)
    ts = entry.get("timestamp", "")
    rel_time = _relative_time(ts)
    mode_lbl = html.escape(_mode_label(mode))

    entry_html = f"""
    <div class="sh-entry">
        <div class="sh-entry-main">
            <div class="sh-entry-query">{query}</div>
            <div class="sh-entry-meta">
                <span class="sh-entry-badge">{mode_lbl}</span>
                <span class="sh-entry-count">{get_text('search_history_results').format(count=count)}</span>
                <span class="sh-entry-time">{html.escape(rel_time)}</span>
            </div>
        </div>
    </div>
    """
    st.markdown(entry_html, unsafe_allow_html=True)

    # 重新搜索按钮：与条目同行
    btn_cols = st.columns([1, 5])
    with btn_cols[0]:
        if st.button(
            get_text("search_history_rerun"),
            key=f"sh_rerun_{idx}",
            use_container_width=True,
            type="secondary",
        ):
            # 将查询填入搜索输入框并触发搜索
            st.session_state.query_input = entry.get("query", "")
            # 标记来自历史记录，ui.py 主循环检测后自动触发搜索
            st.session_state["_sh_pending_query"] = entry.get("query", "")
            st.rerun()
    with btn_cols[1]:
        st.markdown("<br>", unsafe_allow_html=True)
