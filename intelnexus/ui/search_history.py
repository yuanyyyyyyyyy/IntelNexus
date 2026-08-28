"""
搜索历史面板
=============
对齐简报中心的历史记录 UI：搜索过滤 / 日期范围 / 软删除恢复 / 单条操作 / toggle 控制。
"""

import html
from datetime import datetime

import streamlit as st

from intelnexus.ui.i18n import get_text
from intelnexus.ui.icons import icon


# ---------------------------------------------------------------------------
# 辅助：两段式删除确认（与 briefing_viewer._delete_with_confirm 同模式）
# ---------------------------------------------------------------------------

def _delete_with_confirm(key: str, label: str = None, use_container_width: bool = False) -> bool:
    """两段式删除确认。返回 True 表示用户已确认。"""
    flag = f"sh_confirm_del_{key}"
    btn_label = label if label is not None else get_text("delete")
    if not st.session_state.get(flag):
        if st.button(btn_label, key=f"sh_delbtn_{key}",
                     use_container_width=use_container_width):
            st.session_state[flag] = True
            st.rerun()
        return False
    c_yes, c_no = st.columns(2)
    with c_yes:
        confirmed = st.button(get_text("confirm_delete"), key=f"sh_delyes_{key}",
                              type="primary", use_container_width=use_container_width)
    with c_no:
        cancelled = st.button(get_text("cancel"), key=f"sh_delno_{key}",
                              use_container_width=use_container_width)
    if confirmed:
        st.session_state.pop(flag, None)
        return True
    if cancelled:
        st.session_state.pop(flag, None)
        st.rerun()
    return False


# ---------------------------------------------------------------------------
# 辅助：相对时间
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
# 辅助：模式标签
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
    if label == i18n_key and i18n_key.startswith("mode_"):
        return i18n_key[5:]
    return label


# ---------------------------------------------------------------------------
# 辅助：解析时间戳为日期+时间字符串
# ---------------------------------------------------------------------------

def _parse_timestamp(ts: str):
    """返回 (date_str, time_str) 元组。"""
    try:
        dt = datetime.fromisoformat(ts)
        return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M")
    except Exception:
        return "", ""


# ---------------------------------------------------------------------------
# 主渲染
# ---------------------------------------------------------------------------

def render_search_history():
    """渲染搜索历史面板（对齐简报中心 render_briefing_history）。

    守卫条件：st.session_state.show_search_history 为 True
    """
    if not st.session_state.get("show_search_history"):
        return

    from intelnexus.config.history import get_history_manager
    history_mgr = get_history_manager()

    # 读全量（含软删除）以便恢复面板使用
    all_entries = history_mgr.get_history(limit=100, include_deleted=True)
    visible = [e for e in all_entries if not e.get("deleted")]
    deleted = [e for e in all_entries if e.get("deleted")]

    with st.container(key="sh-history"):
        # 标题行
        header_html = f"""
        <div class="sh-header">
            <div class="sh-title-row">
                {icon('history', size='sm', color='blue')}
                <span class="sh-title">{get_text('search_history_title')}</span>
                <span class="sh-count">{len(visible)}</span>
            </div>
        </div>
        """
        st.markdown(header_html, unsafe_allow_html=True)

        if not visible and not deleted:
            st.markdown(
                f'<div class="sh-empty">{icon("search", "sm", "gray")} '
                f'{get_text("search_history_empty")}</div>',
                unsafe_allow_html=True,
            )
            return

        # ---- 搜索 & 日期过滤栏 ----
        f_search, f_from, f_to = st.columns([3, 1, 1])
        with f_search:
            search_q = st.text_input(
                get_text("history_search"),
                key="sh_hist_search",
                placeholder=get_text("history_search"),
                label_visibility="collapsed",
            )
        with f_from:
            date_from = st.date_input(
                get_text("history_date_from"),
                value=None,
                key="sh_hist_date_from",
                label_visibility="collapsed",
            )
        with f_to:
            date_to = st.date_input(
                get_text("history_date_to"),
                value=None,
                key="sh_hist_date_to",
                label_visibility="collapsed",
            )

        # 过滤逻辑
        def _match(entry):
            q = search_q.strip().lower()
            if q:
                query_text = (entry.get("query") or "").lower()
                mode_text = _mode_label(entry.get("mode", "")).lower()
                model_text = (entry.get("model") or "").lower()
                if q not in query_text and q not in mode_text and q not in model_text:
                    return False
            ts = entry.get("timestamp", "")
            if ts:
                try:
                    dt = datetime.fromisoformat(ts).date()
                except (ValueError, TypeError):
                    dt = None
                if dt:
                    if date_from and dt < date_from:
                        return False
                    if date_to and dt > date_to:
                        return False
            return True

        filtered = [e for e in visible if _match(e)]

        if not filtered and not deleted:
            st.markdown(f"<p class='bf-hint'>{get_text('history_no_match')}</p>", unsafe_allow_html=True)
            return

        # ---- 清除 / 物理清除按钮行 ----
        clear_col, purge_col, _ = st.columns([1, 1, 4])
        with clear_col:
            if visible and st.button(get_text("search_history_clear"), key="sh_clear_all_btn",
                                     use_container_width=True):
                st.session_state["_sh_confirm_clear_all"] = True
                st.rerun()
        with purge_col:
            if deleted and st.button(
                get_text("search_history_purged").format(n=len(deleted)),
                key="sh_purge_btn",
                use_container_width=True,
            ):
                n = history_mgr.purge_deleted(days=0)
                if n:
                    st.toast(get_text("search_history_purged").format(n=n))
                    st.rerun()

        # 全量清除二次确认
        if st.session_state.pop("_sh_confirm_clear_all", False):
            st.warning(get_text("search_history_clear_confirm"))
            col_yes, col_no, _ = st.columns([1, 1, 4])
            with col_yes:
                if st.button(get_text("confirm_delete"), key="sh_clear_yes", type="primary",
                             use_container_width=True):
                    history_mgr.clear_history()
                    st.toast(get_text("search_history_cleared"))
                    st.rerun()
            with col_no:
                if st.button(get_text("cancel"), key="sh_clear_no", use_container_width=True):
                    st.rerun()

        # ---- 正常列表 ----
        for entry in filtered:
            date_str, time_str = _parse_timestamp(entry.get("timestamp", ""))
            query_text = entry.get("query", "")
            mode_lbl = _mode_label(entry.get("mode", ""))
            count = entry.get("results_count", 0)
            rel_time = _relative_time(entry.get("timestamp", ""))
            entry_id = entry.get("id", "")

            st.markdown('<div class="sh-entry">', unsafe_allow_html=True)
            sel_col, info_col, act_col = st.columns([0.5, 4, 2])
            with sel_col:
                st.checkbox("\u00A0", key=f"sh_sel_{entry_id}", label_visibility="collapsed")
            with info_col:
                time_label = f"{date_str} {time_str}".strip()
                st.markdown(
                    f'<div class="sh-entry__time">{html.escape(time_label)}'
                    f' <span style="color:var(--text-tertiary);font-size:12px;">({html.escape(rel_time)})</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f'<div class="sh-entry__meta">'
                    f'<span class="sh-entry__query">{html.escape(query_text)}</span>'
                    f'<span class="sh-entry__sep">&middot;</span>'
                    f'<span class="sh-entry__badge">{html.escape(mode_lbl)}</span>'
                    f'<span class="sh-entry__sep">&middot;</span>'
                    f'<span class="sh-entry__count">{get_text("search_history_results").format(count=count)}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            with act_col:
                r_col, d_col = st.columns(2)
                with r_col:
                    if st.button(get_text("search_history_rerun"), key=f"sh_rerun_{entry_id}",
                                 use_container_width=True):
                        st.session_state.query_input = query_text
                        st.session_state["_sh_pending_query"] = query_text
                        st.rerun()
                with d_col:
                    if _delete_with_confirm(entry_id, use_container_width=True):
                        history_mgr.delete_entry(entry_id)
                        st.toast(get_text("search_history_deleted"))
                        st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        # ---- 已删除条目恢复区 ----
        if deleted:
            with st.expander(f"{get_text('restore')} ({len(deleted)})", expanded=False):
                for entry in deleted:
                    date_str, time_str = _parse_timestamp(
                        entry.get("deleted_at") or entry.get("timestamp", "")
                    )
                    query_text = entry.get("query", "")
                    entry_id = entry.get("id", "")
                    st.markdown(
                        f'<div class="sh-entry" style="opacity:0.5">'
                        f'<div class="sh-entry__time">{date_str} {time_str}'
                        f' &mdash; {html.escape(query_text)}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    if st.button(get_text("restore"), key=f"sh_restore_{entry_id}",
                                 use_container_width=True):
                        history_mgr.restore_entry(entry_id)
                        st.success(get_text("search_history_restored"))
                        st.rerun()
