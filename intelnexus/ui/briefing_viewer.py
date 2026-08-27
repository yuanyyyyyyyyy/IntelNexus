"""
简报预览和历史查看
==================
在 Streamlit 主面板中展示简报内容和历史记录

Design: Intelligence Workbench (cold-gray industrial)
- Function tag bars (4px colored left border) for each panel
- No emoji, no welcome page, no step cards
- Single-column vertical flow
"""

import html

import os
import streamlit as st
from datetime import datetime
from intelnexus.config.briefing_history import get_briefing_history
from intelnexus.ui.i18n import get_text
from intelnexus.ui.icons import icon
from intelnexus.ui import main_tabs


def _watch_category_options() -> dict:
    """动态读取关注点选项 {cid: 显示名}（含用户自定义）。

    单点真理：替代此前在 数据源/订阅 两面板各自硬编码的分类字典，
    新增关注点后两处下拉自动生效。
    """
    try:
        from intelnexus.config.watch_categories import get_all_categories
        return {cid: cfg.get("name", cid) for cid, cfg in get_all_categories().items()}
    except ImportError:
        return {}


def _render_scheduler_status_banner() -> None:
    """订阅管理面板顶部显示定时推送真实状态。

    状态判定（按优先级）：
    - 调度器未运行（--no-scheduler 或 CLI 模式）→ info 提示
    - 运行中但无任务（无启用的订阅者）→ warning
    - 运行中且有任务 → success + 下次推送时间；SMTP 未配置时附加警告
    """
    try:
        from intelnexus.briefing.scheduler_registry import get_scheduler
        sched = get_scheduler()
    except ImportError:
        sched = None

    if sched is None:
        st.info(get_text("sched_off"))
        return

    jobs = []
    try:
        jobs = [j for j in sched.scheduler.get_jobs() if j.next_run_time is not None]
    except Exception:
        pass

    if not jobs:
        st.warning(get_text("sched_no_jobs"))
        return

    next_runs = sorted(j.next_run_time for j in jobs)
    nxt = next_runs[0].strftime("%m-%d %H:%M")
    st.success(get_text("sched_on").format(n=nxt, count=len(jobs)))

    # 任务在跑但 LLM 不可用：定时简报将以降级模板文案推送，必须显式提醒
    try:
        from intelnexus.briefing.scheduler_registry import get_model_status
        model_status = get_model_status()
        if model_status.get("degraded"):
            reason = model_status.get("reason") or ""
            hint = get_text("sched_llm_degraded")
            if reason:
                hint += f"（{reason}）"
            st.warning(hint)
        elif model_status.get("model"):
            st.caption(get_text("sched_llm_ok").format(model=model_status["model"]))
    except Exception:
        pass

    # 任务在跑但 SMTP 缺失：推送注定失败，必须显式提醒
    try:
        from intelnexus.config.email_settings import get_email_settings
        cfg = get_email_settings() or {}
        if not (cfg.get("smtp_server") and cfg.get("username")):
            st.warning(get_text("sched_smtp_missing"))
    except Exception:
        pass


def _delete_with_confirm(key: str, label: str = None, help: str = None,
                         use_container_width: bool = False) -> bool:
    """两段式删除确认（无 fragment 的轻量实现）。

    第一次点击只进入确认态；确认态下出现 [确认删除]/[取消]。
    返回 True 表示用户已确认，调用方执行真实删除并 rerun。
    """
    flag = f"confirm_del_{key}"
    btn_label = label if label is not None else get_text("delete")
    if not st.session_state.get(flag):
        if st.button(btn_label, key=f"delbtn_{key}", help=help,
                     use_container_width=use_container_width):
            st.session_state[flag] = True
            st.rerun()
        return False
    c_yes, c_no = st.columns(2)
    with c_yes:
        confirmed = st.button(get_text("confirm_delete"), key=f"delyes_{key}",
                              type="primary", use_container_width=use_container_width)
    with c_no:
        cancelled = st.button(get_text("cancel"), key=f"delno_{key}",
                              use_container_width=use_container_width)
    if cancelled:
        st.session_state[flag] = False
        st.rerun()
    return confirmed


def render_briefing_preview():
    """
    渲染简报预览区域

    守卫条件：st.session_state.current_briefing 存在且非空
    显示内容：简报 Markdown + 关闭按钮 + 下载按钮
    """
    if not st.session_state.get("current_briefing"):
        return

    header_cols = st.columns([5, 1])
    with header_cols[0]:
        st.markdown(f'<div class="bf-output__header">{get_text("briefing_preview")}</div>', unsafe_allow_html=True)
    with header_cols[1]:
        # 关闭预览，回到初始状态（不再需要刷新整个页面）
        if st.button(get_text("close"), key="briefing_preview_close", use_container_width=True):
            st.session_state.current_briefing = None
            st.session_state.current_briefing_filename = None
            st.session_state.current_briefing_html = None
            st.rerun()

    st.markdown('<div class="bf-output">', unsafe_allow_html=True)
    st.markdown(st.session_state.current_briefing)

    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            label=get_text("download_md"),
            data=st.session_state.current_briefing,
            file_name=f"briefing_{datetime.now().strftime('%Y%m%d')}.md",
            mime="text/markdown",
            key="briefing_download_md_main"
        )
    with col2:
        if st.session_state.get("current_briefing_html"):
            st.download_button(
                label=get_text("download_html"),
                data=st.session_state.current_briefing_html,
                file_name=f"briefing_{datetime.now().strftime('%Y%m%d')}.html",
                mime="text/html",
                key="briefing_download_html_main"
            )

    st.markdown('</div>', unsafe_allow_html=True)


_OPERATOR_HOST_FALLBACK_ATTR = "_bf_host_identity"


def _get_current_operator_id() -> str:
    """当前操作者身份（反馈/行为数据的归属主体）。

    优先使用条目区「反馈身份」选择器绑定的订阅者 id；
    未选择时回退到 主机名（单机单人场景的稳定标识）。
    修复点：原实现全部记为 anonymous，导致分析面板"活跃用户"
    恒为 1、按订阅者个性化过滤收不到有效数据。
    """
    sub_id = st.session_state.get("bf_feedback_identity")
    if sub_id:
        return sub_id
    host = getattr(st.session_state, _OPERATOR_HOST_FALLBACK_ATTR, None)
    if not host:
        try:
            import socket
            host = f"host_{socket.gethostname()}"
        except Exception:
            host = "anonymous"
        setattr(st.session_state, _OPERATOR_HOST_FALLBACK_ATTR, host)
    return host


def render_briefing_entries():
    """
    渲染简报条目列表（反向飞轮：条目→一键取证）

    在简报预览下方展示原始情报条目，每条标注可信度评分和冲突状态，
    并提供「取证」按钮一键跳转到搜索工作台进行深度调查。
    """
    filename = st.session_state.get("current_briefing_filename", "")
    if not filename:
        return

    history = get_briefing_history()
    entries = history.load_briefing_data(filename)
    if not entries:
        return

    # URL 去重兜底（修复：历史简报数据含跨类目重复，360 条实测仅 288 个唯一 URL；
    # 采集端已加全局去重，这里保证旧文件渲染时同样干净）
    seen_urls = set()
    unique_entries = []
    for e in entries:
        u = (e.get("url") or "").rstrip("/")
        if not u:
            unique_entries.append(e)
            continue
        if u in seen_urls:
            continue
        seen_urls.add(u)
        unique_entries.append(e)
    entries = unique_entries

    st.markdown(
        '<div class="bf-output">'
        f'<div class="bf-output__header">{get_text("briefing_entries_title")} ({len(entries)})</div>',
        unsafe_allow_html=True,
    )

    # 类目筛选（默认「全部」；360+ 条一次性全渲会拖垮页面——每条约产生 8 个部件）
    _cat_counts = {}
    for e in entries:
        c = e.get("category", "unknown")
        _cat_counts[c] = _cat_counts.get(c, 0) + 1
    _cat_display = {cid: f"{cid} ({n})" for cid, n in _cat_counts.items()}
    try:
        from intelnexus.config.watch_categories import get_all_categories
        _names = {cid: cfg.get("name", cid) for cid, cfg in get_all_categories().items()}
        _cat_display = {cid: f"{_names.get(cid, cid)} ({n})" for cid, n in _cat_counts.items()}
    except ImportError:
        pass

    sel_cat = st.selectbox(
        get_text("briefing_filter_category"),
        ["__all__"] + list(_cat_counts.keys()),
        format_func=lambda c: get_text("briefing_filter_all") if c == "__all__"
        else _cat_display.get(c, c),
        key=f"bf_entries_cat_{filename}",
    )
    if sel_cat != "__all__":
        entries = [e for e in entries if e.get("category") == sel_cat]

    # 按严重度排序：有冲突的优先，按冲突严重度降序
    sorted_entries = sorted(
        entries,
        key=lambda e: (e.get("has_conflict", False), e.get("has_conflict", False) and e.get("conflict_severity", 0.0)),
        reverse=True,
    )

    # 分批加载：默认只渲染前 N 条，避免一次生成数千个 Streamlit 部件
    PAGE_SIZE = 30
    total_after_filter = len(sorted_entries)
    shown = st.session_state.get(f"bf_entries_shown_{filename}", PAGE_SIZE)
    page_entries = sorted_entries[:shown]
    if total_after_filter > shown:
        st.caption(get_text("briefing_showing").format(shown=len(page_entries), total=total_after_filter))
        if st.button(get_text("briefing_load_more"), key=f"bf_more_{filename}",
                     use_container_width=True):
            st.session_state[f"bf_entries_shown_{filename}"] = shown + PAGE_SIZE
            st.rerun()

    # 反馈身份选择器：把反馈/点击归到具体订阅者（分析统计与个性化推送依赖真实身份数据）
    try:
        from intelnexus.config.subscriptions import get_all_subscribers
        _subs_for_identity = get_all_subscribers()
    except ImportError:
        _subs_for_identity = []
    _identity_options = [""] + [s.get("id", "") for s in _subs_for_identity]

    def _fmt_identity(sid: str) -> str:
        if not sid:
            try:
                import socket
                return f"{get_text('feedback_identity_local')} ({socket.gethostname()})"
            except Exception:
                return get_text('feedback_identity_local')
        for s in _subs_for_identity:
            if s.get("id") == sid:
                return f"{s.get('name', sid)} <{s.get('email', '')}>"
        return sid

    st.selectbox(
        get_text("feedback_identity"),
        _identity_options,
        format_func=_fmt_identity,
        key="bf_feedback_identity",
    )

    for i, entry in enumerate(page_entries):
        raw_title = str(entry.get("title", "") or "")
        # 外部源标题/来源属不可信输入，进入 unsafe_allow_html 前必须转义（防存储型 XSS）
        title = html.escape(raw_title) or get_text("untitled")
        url = entry.get("url", "")
        source = html.escape(str(entry.get("source", "Unknown") or "Unknown"))
        score = entry.get("credibility_score", 0.5)
        has_conflict = entry.get("has_conflict", False)
        conflict_sev = entry.get("conflict_severity", 0.0)

        # 严重度标记
        if has_conflict and conflict_sev >= 0.7:
            sev_badge = '<span class="bf-sev-badge bf-sev-badge--high">HIGH</span>'
        elif has_conflict:
            sev_badge = '<span class="bf-sev-badge bf-sev-badge--med">MED</span>'
        else:
            sev_badge = ""

        # 可信度颜色
        if score >= 0.7:
            cred_color = "var(--wb-green)"
        elif score >= 0.4:
            cred_color = "var(--wb-orange)"
        else:
            cred_color = "var(--wb-red)"

        st.markdown(
            f'<div class="bf-entry-row">'
            f'<div class="bf-entry-info">'
            f'<span class="bf-entry-title">{title[:80]}</span>'
            f'<span class="bf-entry-source">{source}</span>'
            f'<span class="bf-entry-cred" style="color:{cred_color}">可信度 {score:.2f}</span>'
            f'{sev_badge}'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # ---- 操作行：单行 flex 布局（修复：旧版嵌套三列把 4 个按钮挤进
        #      约 1/21 页宽的小方块里，且 URL 独占一列造成大片空白）----
        entry_url = url or ""
        category = entry.get("category", "unknown")
        btn_prefix = "! " if (has_conflict and conflict_sev >= 0.7) else ""
        kb_saved = False
        if entry_url:
            try:
                from intelnexus.config.knowledge_base import get_items
                kb_saved = bool(get_items(url=entry_url, item_type="briefing_entry"))
            except Exception:
                kb_saved = False

        act_cols = st.columns([1.1, 1.1, 1.6, 2.2, 4])
        with act_cols[0]:
            if st.button(get_text("feedback_up"),
                         key=f"up_{category}_{filename}_{i}",
                         help=get_text("feedback_hint"),
                         use_container_width=True):
                from intelnexus.config.feedback import save_briefing_feedback, track_feedback
                _operator = _get_current_operator_id()
                save_briefing_feedback(category, entry_url, "up", subscriber_id=_operator)
                track_feedback(entry_url, "up", "briefing", subscriber_id=_operator)
                st.toast(get_text("feedback_marked"))
                st.rerun()
        with act_cols[1]:
            if st.button(get_text("feedback_down"),
                         key=f"down_{category}_{filename}_{i}",
                         help=get_text("feedback_hint"),
                         use_container_width=True):
                from intelnexus.config.feedback import save_briefing_feedback, track_feedback
                _operator = _get_current_operator_id()
                save_briefing_feedback(category, entry_url, "down", subscriber_id=_operator)
                track_feedback(entry_url, "down", "briefing", subscriber_id=_operator)
                st.toast(get_text("feedback_marked"))
                st.rerun()
        with act_cols[2]:
            if not entry_url:
                st.caption(" ")
            elif kb_saved:
                st.caption(get_text("kb_saved"))
            else:
                if st.button(get_text("kb_save"),
                             key=f"kb_{category}_{filename}_{i}",
                             help=get_text("kb_save"),
                             use_container_width=True):
                    from intelnexus.config.knowledge_base import add_item
                    add_item(
                        item_type="briefing_entry",
                        title=title,
                        url=entry_url,
                        content=entry.get("description", ""),
                        source=source,
                        category=category,
                        tags=[],
                        metadata={
                            "briefing_id": filename,
                            "credibility_score": score
                        }
                    )
                    st.toast(get_text("kb_saved_toast"))
                    st.rerun()
        with act_cols[3]:
            if st.button(f"{btn_prefix}{get_text('investigate_like_this')}",
                         key=f"forensic_{filename}_{i}",
                         type="primary",
                         use_container_width=True,
                         help=get_text("investigate_help")):
                query = raw_title if raw_title else (url or "unknown")
                st.session_state.pending_forensic_query = query
                st.session_state.pending_forensic_mode = "all"
                # 编程式跳转到搜索页（一次性旗标，ui.py 渲染前消费并同步 radio 选中态）
                main_tabs.request_tab(st.session_state, main_tabs.TAB_SEARCH)
                st.rerun()
        with act_cols[4]:
            if url:
                st.markdown(
                    f'<span class="bf-entry-url">{html.escape(url[:90])}</span>',
                    unsafe_allow_html=True,
                )

    st.markdown('</div>', unsafe_allow_html=True)


def _parse_created_at(created_at: str):
    """安全解析 created_at 字符串，返回 (date_str, time_str)；失败返回 ('—', '')"""
    if not created_at:
        return "—", ""
    try:
        dt = datetime.fromisoformat(created_at)
        return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M")
    except (ValueError, TypeError):
        return created_at[:10] if len(created_at) >= 10 else "—", created_at[11:16] if len(created_at) >= 16 else ""


def render_briefing_history():
    """
    渲染简报历史列表（含搜索过滤 / 批量选择 / 导出 / 软删除恢复）

    守卫条件：st.session_state.show_briefing_history 为 True
    """
    if not st.session_state.get("show_briefing_history"):
        return

    history_mgr = get_briefing_history()
    # 读全量（含软删除）以便恢复面板使用
    all_entries = history_mgr.get_briefings(limit=100, include_deleted=True)
    visible = [e for e in all_entries if not e.get("deleted")]
    deleted = [e for e in all_entries if e.get("deleted")]

    st.markdown(f'<div class="bf-output"><div class="bf-output__header">{get_text("briefing_history")}</div>', unsafe_allow_html=True)

    if not visible and not deleted:
        st.markdown(f"<p class='bf-hint'>{get_text('briefing_history_empty')}</p>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # ---- 搜索 & 日期过滤栏 ----
    _cat_map = _watch_category_options()
    f_search, f_from, f_to = st.columns([3, 1, 1])
    with f_search:
        search_q = st.text_input(
            get_text("history_search"),
            key="bf_hist_search",
            placeholder=get_text("history_search"),
            label_visibility="collapsed",
        )
    with f_from:
        date_from = st.date_input(
            get_text("history_date_from"),
            value=None,
            key="bf_hist_date_from",
            label_visibility="collapsed",
        )
    with f_to:
        date_to = st.date_input(
            get_text("history_date_to"),
            value=None,
            key="bf_hist_date_to",
            label_visibility="collapsed",
        )

    # 过滤逻辑
    def _match(entry):
        q = search_q.strip().lower()
        if q:
            org = (entry.get("organization") or "").lower()
            fn = (entry.get("filename") or "").lower()
            cats = " ".join(entry.get("categories", [])).lower()
            if q not in org and q not in fn and q not in cats:
                return False
        ca = entry.get("created_at", "")
        if ca:
            try:
                dt = datetime.fromisoformat(ca).date()
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
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # ---- 批量选择 + 导出 ----
    select_all_key = "bf_hist_select_all"
    st.session_state.setdefault(select_all_key, False)

    export_col, purge_col, _ = st.columns([1, 1, 4])
    with export_col:
        if st.button(get_text("history_export"), key="bf_hist_export_btn", disabled=not filtered):
            selected = [e["filename"] for e in filtered if st.session_state.get(f"bf_sel_{e['filename']}")]
            if not selected:
                st.warning(get_text("history_export_empty"))
            else:
                zip_data = history_mgr.export_briefings(selected)
                if zip_data:
                    st.download_button(
                        label=f"{get_text('history_export')} ({len(selected)})",
                        data=zip_data,
                        file_name=f"briefings_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                        mime="application/zip",
                        key="bf_hist_zip_download",
                    )
                    st.toast(get_text("history_export_done").format(n=len(selected)))
    with purge_col:
        if deleted and st.button(get_text("briefing_purged").format(n=len(deleted)), key="bf_hist_purge_btn"):
            n = history_mgr.purge_deleted(days=0)
            if n:
                st.toast(get_text("briefing_purged").format(n=n))
                st.rerun()

    # ---- 正常列表 ----
    for entry in filtered:
        date_str, time_str = _parse_created_at(entry.get("created_at", ""))
        org = entry.get("organization", "") or "—"
        categories = entry.get("categories") or []
        cats_text = "、".join(_cat_map.get(c, c) for c in categories[:3]) if categories else "—"
        if len(categories) > 3:
            cats_text += f" 等{len(categories)}个"
        subs = entry.get("subscribers_count", 0)
        fn = entry.get("filename", "")

        st.markdown('<div class="bf-history-item">', unsafe_allow_html=True)
        sel_col, info_col, act_col = st.columns([0.5, 4, 2])
        with sel_col:
            st.checkbox("", key=f"bf_sel_{fn}", label_visibility="collapsed")
        with info_col:
            time_label = f"{date_str} {time_str}".strip()
            st.markdown(
                f'<div class="bf-history-item__time">{time_label}</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<div class="bf-history-item__meta">'
                f'<span class="bf-history-item__org">{html.escape(org)}</span>'
                f'<span class="bf-history-item__sep">·</span>'
                f'<span>{cats_text}</span>'
                f'<span class="bf-history-item__sep">·</span>'
                f'<span>{subs}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        with act_col:
            v_col, d_col = st.columns(2)
            with v_col:
                if st.button(get_text("view"), key=f"view_{fn}", use_container_width=True):
                    load_briefing_for_preview(fn, entry.get("html_filename"))
            with d_col:
                if _delete_with_confirm(
                    f"bf_{fn}",
                    label=get_text("delete"),
                    use_container_width=True,
                ):
                    history_mgr.delete_briefing(fn)
                    st.success(get_text("briefing_deleted"))
                    st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    # ---- 已删除条目恢复区 ----
    if deleted:
        with st.expander(f"{get_text('restore')} ({len(deleted)})", expanded=False):
            for entry in deleted:
                date_str, time_str = _parse_created_at(entry.get("deleted_at") or entry.get("created_at", ""))
                org = entry.get("organization", "") or "—"
                fn = entry.get("filename", "")
                st.markdown(
                    f'<div class="bf-history-item" style="opacity:0.5">'
                    f'<div class="bf-history-item__time">{date_str} {time_str} — {html.escape(org)}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                if st.button(get_text("restore"), key=f"restore_{fn}", use_container_width=True):
                    history_mgr.restore_briefing(fn)
                    st.success(get_text("briefing_restored"))
                    st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)


def load_briefing_for_preview(filename: str, html_filename: str = None):
    """加载简报到预览区域"""
    content = get_briefing_history().load_briefing(filename)
    if content:
        st.session_state.current_briefing = content
        st.session_state.current_briefing_filename = filename
        if html_filename:
            html_content = get_briefing_history().load_briefing(html_filename)
            st.session_state.current_briefing_html = html_content
        st.session_state.show_briefing_history = False
        # sync the toggle widget state (else switch shows ON while list is hidden)
        if "bf_history_toggle" in st.session_state:
            st.session_state.bf_history_toggle = False
        st.rerun()


def delete_briefing(filename: str):
    """软删除简报"""
    get_briefing_history().delete_briefing(filename)
    st.success(get_text("briefing_deleted"))
    st.rerun()


# ============================================================
#  Briefing Config Panels (Workbench style with tag bars):
# ============================================================


def render_data_sources_panel():
    """数据源管理面板（蓝色标签条）"""
    st.markdown(f'''
    <div class="bf-panel bf-panel--source">
        <div class="bf-label">
            <span class="bf-label__tag">Sources</span>
            <span class="bf-label__title">{get_text("data_source_management")}</span>
        </div>
    ''', unsafe_allow_html=True)

    try:
        from intelnexus.config.sources import get_all_sources, add_source, remove_source, toggle_source, update_source, test_source
        SOURCES_AVAILABLE = True
    except ImportError:
        SOURCES_AVAILABLE = False

    if not SOURCES_AVAILABLE:
        st.markdown(f"<p class='bf-hint bf-hint--warn'>{get_text('module_unavailable')}</p>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        return

    with st.expander(get_text("add_data_source")):
        source_type = st.selectbox(
            get_text("source_type"),
            [get_text("source_type_rss"), get_text("source_type_web")],
            key="bf_source_type_selector"
        )
        source_name = st.text_input(get_text("source_name"), key="bf_source_name_input")
        source_url = st.text_input(get_text("source_url"), key="bf_source_url_input")

        # 动态读取关注点配置（含用户自定义）——修复：新关注点无法归属数据源
        categories = _watch_category_options()
        source_category = st.selectbox(
            get_text("source_category"),
            list(categories.keys()),
            format_func=lambda x: categories[x],
            key="bf_source_category_selector"
        )

        if st.button(get_text("add_source"), key="bf_add_source_btn"):
            if source_name and source_url:
                # 入库前 URL 安全校验；校验器不可用时放行原流程（库层 add_source 内仍有兜底校验）
                try:
                    from intelnexus.core.security.url_guard import validate_external_url
                    _url_ok, _url_reason = validate_external_url(source_url)
                except Exception:
                    _url_ok, _url_reason = True, ""
                if not _url_ok:
                    st.error(get_text(f"sec_url_{_url_reason}"))
                else:
                    type_val = "rss" if source_type == get_text("source_type_rss") else "web"
                    if add_source(type_val, source_name, source_url, source_category):
                        st.success(get_text("source_added"))
                        st.rerun()
                    else:
                        st.error(get_text("source_add_failed"))
            else:
                st.warning(get_text("fill_fields"))

    sources = get_all_sources()
    all_sources_list = sources.get("subscription_sources", []) + sources.get("custom_sources", [])

    # 精选情报源一键导入（内置经过验证的 12 个一手 RSS 源，按关注点分组）
    with st.expander(get_text("preset_import_title")):
        st.caption(get_text("preset_import_hint"))
        try:
            from intelnexus.config.watch_categories import get_all_categories as _gac_wc
            _wc_names = {cid: c.get("name", cid) for cid, c in _gac_wc().items()}
        except Exception:
            _wc_names = {}
        preset_cats = {
            "cyber_vuln": _wc_names.get("cyber_vuln", "网络安全漏洞"),
            "threat_intel": "威胁情报",
            "ai_news": "AI 资讯",
            "general_tech": "综合科技",
        }
        sel = st.multiselect(
            get_text("preset_select"),
            options=list(preset_cats.keys()),
            format_func=lambda c: preset_cats.get(c, c),
            key="bf_preset_cats",
        )
        if st.button(get_text("preset_import_btn"), key="bf_preset_btn"):
            import xml.etree.ElementTree as ET
            opml_path = os.path.join("presets", "intel_feeds.opml")
            if not os.path.exists(opml_path):
                st.error("presets/intel_feeds.opml 不存在")
            elif not sel:
                st.warning(get_text("fill_fields"))
            else:
                tree = ET.parse(opml_path)
                added = 0
                _pairs = []
                for _body in tree.iter("body"):
                    for _group in list(_body):
                        _glabel = _group.get("text", "")
                        for _child in list(_group):
                            _pairs.append((_glabel, _child))
                for _glabel, outline in _pairs:
                    xml_url = outline.get("xmlUrl")
                    if not xml_url:
                        continue
                    cat_for_feed = _glabel
                    if cat_for_feed is None or cat_for_feed not in sel:
                        continue
                    ok = add_source("rss", outline.get("text", "feed"), xml_url,
                                    cat_for_feed, fetch_type="rss")
                    added += 1 if ok else 0
                st.success(get_text("preset_imported").format(added=added))

    # OPML 批量导入 RSS
    with st.expander(get_text("import_opml")):
        opml_file = st.file_uploader(get_text("opml_upload"), type=["opml", "xml"], key="bf_opml_uploader")
        _cats_now = _watch_category_options()
        if opml_file is not None and _cats_now:
            opml_cat = st.selectbox(
                get_text("source_category"),
                list(_cats_now.keys()),
                format_func=lambda x: _cats_now[x],
                key="bf_opml_category"
            )
            if st.button(get_text("opml_import_btn"), key="bf_opml_import_btn"):
                try:
                    content = opml_file.getvalue().decode("utf-8", errors="replace")
                except Exception:
                    content = ""
                from intelnexus.config.sources import import_sources_opml
                r = import_sources_opml(content, opml_cat)
                if r.get("invalid") == -1:
                    st.error(get_text("opml_parse_failed"))
                else:
                    st.success(get_text("opml_import_result").format(
                        ok=r["imported"], dup=r["duplicates"]))
                    if r["imported"]:
                        st.rerun()
        elif opml_file is not None and not _cats_now:
            st.info(get_text("no_watch_categories"))

    if all_sources_list:
        with st.expander(get_text("manage_sources")):
            # 搜索过滤
            _src_search = st.text_input(
                get_text("search_placeholder"),
                key="bf_src_search",
                placeholder=get_text("search_placeholder"),
                label_visibility="collapsed",
            )
            _src_query = _src_search.strip().lower()
            _filtered_src = [
                s for s in all_sources_list
                if not _src_query
                or _src_query in s.get("name", "").lower()
                or _src_query in s.get("url", "").lower()
            ]

            # 批量测试
            if st.button(get_text("batch_test"), key="bf_src_batch_test"):
                st.session_state.bf_src_batch_running = True
            if st.session_state.get("bf_src_batch_running"):
                with st.spinner(get_text("testing")):
                    for _bs in _filtered_src:
                        _ft = _bs.get("fetch_type", "web_engine")
                        _br = test_source(_bs["url"], _ft, timeout=8)
                        _bcls = "active" if _br["success"] else "error"
                        _bstatus = get_text("source_ok") if _br["success"] else get_text("source_fail")
                        st.markdown(
                            f'<span class="status-dot {_bcls}"></span> '
                            f'{html.escape(_bs["name"])} — {_bstatus} ({_br.get("latency_ms", "—")}ms)',
                            unsafe_allow_html=True,
                        )
                st.session_state.bf_src_batch_running = False

            for source in _filtered_src:
                col_info, col_toggle, col_actions = st.columns([3, 1, 3])
                with col_info:
                    st.write(f"**{html.escape(str(source['name']))}**")
                    _type_label = "RSS" if source.get("fetch_type") == "rss" else get_text("source_type_web")
                    _cat_label = categories.get(source.get("category", ""), source.get("category", "—"))
                    st.caption(f"[{_type_label}] {_cat_label} · {source['url'][:60]}...")
                with col_toggle:
                    enabled = st.toggle(get_text("enabled_label"), value=source.get("enabled", True), key=f"bf_toggle_{source['id']}", label_visibility="collapsed")
                    if enabled != source.get("enabled", True):
                        toggle_source(source['id'], enabled)
                        st.rerun()
                with col_actions:
                    act_cols = st.columns(3)
                    with act_cols[0]:
                        if st.button(get_text("test_source_btn"), key=f"bf_test_{source['id']}",
                                     help=get_text("test_source_help")):
                            fetch_type = source.get("fetch_type", "web_engine")
                            result = test_source(source['url'], fetch_type)
                            if result["success"]:
                                st.success(result["message"])
                            else:
                                st.error(result["message"])
                    with act_cols[1]:
                        if st.button(get_text("edit"), key=f"bf_edit_{source['id']}",
                                     help=get_text("edit_source_help")):
                            st.session_state[f"editing_source_{source['id']}"] = True
                            st.rerun()
                    with act_cols[2]:
                        if _delete_with_confirm(f"src_{source['id']}"):
                            if remove_source(source['id']):
                                st.rerun()

                # 编辑表单
                if st.session_state.get(f"editing_source_{source['id']}"):
                    with st.container():
                        st.caption(get_text("edit_label"))
                        edit_name = st.text_input(get_text("name_label"), value=source['name'], key=f"bf_edit_name_{source['id']}")
                        edit_url = st.text_input("URL", value=source['url'], key=f"bf_edit_url_{source['id']}")
                        cat_options = list(categories.keys())
                        edit_cat = st.selectbox(
                            get_text("category_label"),
                            cat_options,
                            index=cat_options.index(source.get('category', 'ai_gov_usage')) if source.get('category') in cat_options else 0,
                            format_func=lambda x: categories[x],
                            key=f"bf_edit_cat_{source['id']}"
                        )
                        ecol1, ecol2 = st.columns(2)
                        with ecol1:
                            if st.button(get_text("save"), key=f"bf_save_{source['id']}"):
                                if edit_name and edit_url:
                                    # url 变更经库层安全校验；被拒时给出可见提示且不关闭编辑表单
                                    if update_source(source['id'], {"name": edit_name, "url": edit_url, "category": edit_cat}):
                                        st.session_state[f"editing_source_{source['id']}"] = False
                                        st.rerun()
                                    else:
                                        st.error(get_text("sec_url_rejected"))
                        with ecol2:
                            if st.button(get_text("cancel"), key=f"bf_cancel_{source['id']}"):
                                st.session_state[f"editing_source_{source['id']}"] = False
                                st.rerun()
    else:
        st.markdown(
            f"<p class='bf-hint'>{get_text('no_sources')} —— {get_text('welcome_step_sources_desc')}</p>",
            unsafe_allow_html=True
        )

    st.markdown('</div>', unsafe_allow_html=True)


def render_subscriptions_panel():
    """订阅者管理面板（绿色标签条）"""
    st.markdown(f'''
    <div class="bf-panel bf-panel--sub">
        <div class="bf-label">
            <span class="bf-label__tag">Subscribers</span>
            <span class="bf-label__title">{get_text("subscription_management")}</span>
        </div>
    ''', unsafe_allow_html=True)

    try:
        from intelnexus.config.subscriptions import get_all_subscribers, add_subscriber, remove_subscriber, update_subscriber
        SUBSCRIPTION_AVAILABLE = True
    except ImportError:
        SUBSCRIPTION_AVAILABLE = False

    if not SUBSCRIPTION_AVAILABLE:
        st.markdown(f"<p class='bf-hint bf-hint--warn'>{get_text('module_unavailable')}</p>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        return

    from intelnexus.config.email_settings import (
        get_email_settings, save_email_settings, test_email_settings
    )

    _render_scheduler_status_banner()

    with st.expander(get_text("email_settings"), expanded=False):
        stored_cfg = get_email_settings()

        col_smtp1, col_smtp2 = st.columns(2)
        with col_smtp1:
            smtp_server = st.text_input(
                get_text("smtp_server"),
                value=stored_cfg.get("smtp_server", ""),
                key="bf_smtp_server_input"
            )
            smtp_port = st.number_input(
                get_text("smtp_port"),
                value=int(stored_cfg.get("smtp_port", 587)),
                key="bf_smtp_port_input"
            )
        with col_smtp2:
            smtp_username = st.text_input(
                get_text("smtp_username"),
                value=stored_cfg.get("username", ""),
                key="bf_smtp_username_input"
            )
            smtp_password = st.text_input(
                get_text("smtp_password"),
                value=stored_cfg.get("password", ""),
                type="password",
                key="bf_smtp_password_input"
            )
        smtp_use_tls = st.checkbox(
            get_text("smtp_use_tls"),
            value=bool(stored_cfg.get("use_tls", True)),
            key="bf_smtp_use_tls_input"
        )

        def _collect_email_cfg() -> dict:
            return {
                "smtp_server": smtp_server.strip(), "smtp_port": int(smtp_port),
                "username": smtp_username.strip(), "password": smtp_password,
                "use_tls": smtp_use_tls
            }

        if st.button(get_text("save_email_settings"), key="bf_save_email_btn"):
            if save_email_settings(_collect_email_cfg()):
                st.success(get_text("email_settings_saved"))
            else:
                st.error(get_text("save_failed"))

        st.caption(get_text("smtp_settings_hint"))
        test_to = st.text_input(get_text("test_email_to"), key="bf_test_email_to")
        if st.button(get_text("send_test_email"), key="bf_send_test_email_btn"):
            cfg_now = _collect_email_cfg()
            if not cfg_now["smtp_server"] or not cfg_now["username"] \
                    or not cfg_now["password"] or not test_to.strip():
                st.warning(get_text("fill_fields"))
            else:
                save_email_settings(cfg_now)
                with st.spinner(get_text("testing")):
                    ok = test_email_settings(test_to.strip())
                if ok:
                    st.success(get_text("test_email_sent_ok"))
                else:
                    st.error(get_text("test_email_failed"))

    with st.expander(get_text("add_subscriber")):
        sub_name = st.text_input(get_text("subscriber_name"), key="bf_sub_name_input")
        sub_email = st.text_input(get_text("subscriber_email"), key="bf_sub_email_input")

        st.markdown(f"**{get_text('push_channels')}**")
        col_ch1, col_ch2, col_ch3 = st.columns(3)
        with col_ch1:
            email_enabled = st.checkbox(get_text("push_channel_email"), value=True, key="bf_email_enabled")
        with col_ch2:
            wecom_enabled = st.checkbox(get_text("push_channel_wecom"), value=False, key="bf_wecom_enabled")
        with col_ch3:
            dingtalk_enabled = st.checkbox(get_text("push_channel_dingtalk"), value=False, key="bf_dingtalk_enabled")

        wecom_webhook = dingtalk_webhook = dingtalk_secret = ""
        if wecom_enabled:
            wecom_webhook = st.text_input(get_text("wecom_webhook"), key="bf_wecom_webhook_input")
        if dingtalk_enabled:
            dingtalk_webhook = st.text_input(get_text("dingtalk_webhook"), key="bf_dingtalk_webhook_input")
            dingtalk_secret = st.text_input(get_text("dingtalk_secret"), key="bf_dingtalk_secret_input")

        st.markdown(f"**{get_text('schedule_settings')}**")
        col_time, col_tz = st.columns(2)
        with col_time:
            from datetime import datetime as dt
            push_time = st.time_input(get_text("push_time"), value=dt(2026, 1, 1, 8, 0), key="bf_push_time")
        with col_tz:
            push_timezone = st.selectbox(
                get_text("push_timezone"),
                ["Asia/Shanghai", "America/New_York", "Europe/London", "Asia/Tokyo"],
                key="bf_push_tz"
            )

        day_options = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        day_labels = [
            get_text("push_days_mon"), get_text("push_days_tue"), get_text("push_days_wed"),
            get_text("push_days_thu"), get_text("push_days_fri"), get_text("push_days_sat"), get_text("push_days_sun")
        ]
        push_days = st.multiselect(
            get_text("push_days"),
            day_options,
            default=["mon", "tue", "wed", "thu", "fri"],
            format_func=lambda x: day_labels[day_options.index(x)],
            key="bf_push_days"
        )

        st.markdown(f"**{get_text('watch_categories')}**")
        categories = _watch_category_options()
        selected_categories = []
        for cat_id, cat_name in categories.items():
            if st.checkbox(cat_name, value=True, key=f"bf_cat_{cat_id}"):
                selected_categories.append(cat_id)

        if st.button(get_text("add_subscriber_btn"), key="bf_add_sub_btn"):
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not sub_name or not sub_email:
                st.warning(get_text("fill_fields"))
            elif not re.match(email_pattern, sub_email):
                st.warning(get_text("invalid_email"))
            else:
                channels = {
                    "email": {"enabled": email_enabled, "address": sub_email},
                    "wecom": {"enabled": wecom_enabled, "webhook": wecom_webhook},
                    "dingtalk": {"enabled": dingtalk_enabled, "webhook": dingtalk_webhook, "secret": dingtalk_secret}
                }
                schedule = {
                    "time": push_time.strftime("%H:%M"),
                    "timezone": push_timezone,
                    "enabled": True,
                    "days": push_days
                }
                new_sub_id = add_subscriber(sub_name, sub_email, channels, schedule, selected_categories)
                if new_sub_id:
                    st.success(get_text("subscriber_added"))
                    from intelnexus.briefing.scheduler_registry import on_subscriber_changed
                    on_subscriber_changed(new_sub_id, "add")
                    st.rerun()
                else:
                    st.error(get_text("subscriber_add_failed"))

    subscribers = get_all_subscribers()
    if subscribers:
        with st.expander(get_text("manage_subscribers")):
            # 搜索过滤
            _sub_search = st.text_input(
                get_text("search_placeholder"),
                key="bf_sub_search",
                placeholder=get_text("search_placeholder"),
                label_visibility="collapsed",
            )
            _sub_query = _sub_search.strip().lower()
            _filtered_sub = [
                s for s in subscribers
                if not _sub_query
                or _sub_query in s.get("name", "").lower()
                or _sub_query in s.get("email", "").lower()
            ]

            for sub in _filtered_sub:
                col_info, col_status, col_actions = st.columns([3, 1, 3])
                with col_info:
                    st.write(f"**{sub['name']}**")
                    st.caption(sub['email'])
                with col_status:
                    status = "<span class='status-dot active'></span>" if sub.get("schedule", {}).get("enabled") else "<span class='status-dot error'></span>"
                    st.write(status, unsafe_allow_html=True)
                with col_actions:
                    act_cols = st.columns(3)
                    with act_cols[0]:
                        if st.button(get_text("manual_push_now"), key=f"bf_push_{sub['id']}",
                                     help=get_text("manual_push")):
                            try:
                                from intelnexus.briefing.scheduler_registry import get_scheduler
                                sched_obj = get_scheduler()
                                if sched_obj and hasattr(sched_obj, '_send_to_subscriber'):
                                    sched_obj._send_to_subscriber(sub)
                                    st.success(get_text("manual_push_success"))
                                else:
                                    st.warning("调度器不可用")
                            except Exception:
                                st.error(get_text("manual_push_failed"))
                    with act_cols[1]:
                        if st.button(get_text("edit"), key=f"bf_edit_sub_{sub['id']}",
                                     help=get_text("edit_subscriber_help")):
                            st.session_state[f"editing_sub_{sub['id']}"] = True
                            st.rerun()
                    with act_cols[2]:
                        if _delete_with_confirm(f"sub_{sub['id']}"):
                            if remove_subscriber(sub['id']):
                                from intelnexus.briefing.scheduler_registry import on_subscriber_changed
                                on_subscriber_changed(sub['id'], "remove")
                                st.rerun()

                with st.container():
                    st.caption(get_text("view_details"))
                    channels = sub.get("channels", {})
                    active_channels = [k for k, v in channels.items() if isinstance(v, dict) and v.get("enabled")]
                    schedule = sub.get("schedule", {})
                    cats = sub.get("categories", [])
                    _cat_names = _watch_category_options()
                    st.markdown(
                        f"- {get_text('push_channels')}: {', '.join(active_channels) or '—'}\n"
                        f"- {get_text('schedule_settings')}: {schedule.get('time', '—')} ({schedule.get('timezone', '—')})\n"
                        f"- {get_text('watch_categories')}: {', '.join(_cat_names.get(c, c) for c in cats) if cats else '—'}"
                    )

                # 编辑表单
                if st.session_state.get(f"editing_sub_{sub['id']}"):
                    with st.container():
                        st.caption(get_text("edit_label"))
                        edit_name = st.text_input(get_text("name_label"), value=sub['name'], key=f"bf_edit_sub_name_{sub['id']}")
                        edit_email = st.text_input(get_text("subscriber_email"), value=sub['email'], key=f"bf_edit_sub_email_{sub['id']}")

                        _ch = sub.get("channels", {})
                        _sch = sub.get("schedule", {})
                        e_ch1, e_ch2, e_ch3 = st.columns(3)
                        with e_ch1:
                            edit_email_on = st.checkbox(get_text("push_channel_email"),
                                                        value=(_ch.get("email", {}) or {}).get("enabled", False),
                                                        key=f"bf_ech_email_{sub['id']}")
                        with e_ch2:
                            edit_wecom_on = st.checkbox(get_text("push_channel_wecom"),
                                                        value=(_ch.get("wecom", {}) or {}).get("enabled", False),
                                                        key=f"bf_ech_wecom_{sub['id']}")
                        with e_ch3:
                            edit_ding_on = st.checkbox(get_text("push_channel_dingtalk"),
                                                       value=(_ch.get("dingtalk", {}) or {}).get("enabled", False),
                                                       key=f"bf_ech_ding_{sub['id']}")
                        edit_wecom_webhook = ""
                        edit_ding_webhook = edit_ding_secret = ""
                        if edit_wecom_on:
                            edit_wecom_webhook = st.text_input(
                                get_text("wecom_webhook"),
                                value=(_ch.get("wecom", {}) or {}).get("webhook", ""),
                                key=f"bf_ewh_wecom_{sub['id']}")
                        if edit_ding_on:
                            edit_ding_webhook = st.text_input(
                                get_text("dingtalk_webhook"),
                                value=(_ch.get("dingtalk", {}) or {}).get("webhook", ""),
                                key=f"bf_ewh_ding_{sub['id']}")
                            edit_ding_secret = st.text_input(
                                get_text("dingtalk_secret"),
                                value=(_ch.get("dingtalk", {}) or {}).get("secret", ""),
                                type="password",
                                key=f"bf_esec_ding_{sub['id']}")

                        e_sch1, e_sch2 = st.columns(2)
                        with e_sch1:
                            from datetime import time as dtime
                            try:
                                _hh, _mm = map(int, (_sch.get("time", "08:00")).split(":"))
                            except Exception:
                                _hh, _mm = 8, 0
                            edit_push_time = st.time_input(get_text("push_time"),
                                                           value=dtime(_hh, _mm), key=f"bf_etime_{sub['id']}")
                        with e_sch2:
                            _tz_options = ["Asia/Shanghai", "America/New_York", "Europe/London", "Asia/Tokyo"]
                            _cur_tz = _sch.get("timezone", "Asia/Shanghai")
                            edit_tz = st.selectbox(
                                get_text("push_timezone"),
                                _tz_options,
                                index=_tz_options.index(_cur_tz) if _cur_tz in _tz_options else 0,
                                key=f"bf_etz_{sub['id']}"
                            )
                        _day_options = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
                        _day_labels = [
                            get_text("push_days_mon"), get_text("push_days_tue"), get_text("push_days_wed"),
                            get_text("push_days_thu"), get_text("push_days_fri"), get_text("push_days_sat"),
                            get_text("push_days_sun")
                        ]
                        edit_days = st.multiselect(
                            get_text("push_days"),
                            _day_options,
                            default=_sch.get("days", ["mon", "tue", "wed", "thu", "fri"]),
                            format_func=lambda x: _day_labels[_day_options.index(x)],
                            key=f"bf_edays_{sub['id']}"
                        )
                        edit_enabled = st.toggle(get_text("enabled_label"),
                                                 value=_sch.get("enabled", False), key=f"bf_een_{sub['id']}")

                        edit_cats = []
                        for cat_id, cat_name in categories.items():
                            if st.checkbox(cat_name, value=cat_id in cats, key=f"bf_edit_sub_cat_{sub['id']}_{cat_id}"):
                                edit_cats.append(cat_id)

                        ecol1, ecol2 = st.columns(2)
                        with ecol1:
                            if st.button(get_text("save"), key=f"bf_save_sub_{sub['id']}"):
                                if edit_name and edit_email and edit_days:
                                    update_subscriber(sub['id'], {
                                        "name": edit_name,
                                        "email": edit_email,
                                        "categories": edit_cats,
                                        "channels": {
                                            "email": {"enabled": edit_email_on, "address": edit_email},
                                            "wecom": {"enabled": edit_wecom_on, "webhook": edit_wecom_webhook},
                                            "dingtalk": {"enabled": edit_ding_on, "webhook": edit_ding_webhook,
                                                         "secret": edit_ding_secret}
                                        },
                                        "schedule": {
                                            "time": edit_push_time.strftime("%H:%M"),
                                            "timezone": edit_tz,
                                            "days": edit_days,
                                            "enabled": edit_enabled
                                        }
                                    })
                                    from intelnexus.briefing.scheduler_registry import on_subscriber_changed
                                    on_subscriber_changed(sub['id'], "update")
                                    st.session_state[f"editing_sub_{sub['id']}"] = False
                                    st.rerun()
                        with ecol2:
                            if st.button(get_text("cancel"), key=f"bf_cancel_sub_{sub['id']}"):
                                st.session_state[f"editing_sub_{sub['id']}"] = False
                                st.rerun()
    else:
        st.markdown(
            f"<p class='bf-hint'>{get_text('no_subscribers')} —— {get_text('welcome_step_subscribers_desc')}</p>",
            unsafe_allow_html=True
        )

    st.markdown('</div>', unsafe_allow_html=True)


def render_watch_categories_panel():
    """关注点管理面板（紫标签条）：新增/编辑/删除关注点，可配置化"""
    st.markdown(f'''
    <div class="bf-panel bf-panel--cat">
        <div class="bf-label">
            <span class="bf-label__tag">Watch</span>
            <span class="bf-label__title">{get_text("watch_categories_mgmt")}</span>
        </div>
    ''', unsafe_allow_html=True)

    try:
        from intelnexus.config.watch_categories import (
            get_all_categories, add_category, remove_category, update_category,
            get_disabled_default_ids, restore_default,
        )
        CAT_AVAILABLE = True
    except ImportError:
        CAT_AVAILABLE = False

    if not CAT_AVAILABLE:
        st.markdown(f"<p class='bf-hint bf-hint--warn'>{get_text('module_unavailable')}</p>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        return

    cats = get_all_categories()

    try:
        from intelnexus.briefing.config import BRIEFING_SECTIONS as _sections
    except ImportError:
        _sections = []

    with st.expander(get_text("add_watch_category")):
        new_id = st.text_input(get_text("category_id"), key="bf_cat_new_id")
        new_name = st.text_input(get_text("category_name"), key="bf_cat_new_name")
        _section_options = [""] + list(_sections)
        new_section = st.selectbox(
            get_text("category_section"),
            _section_options,
            format_func=lambda s: s if s else get_text("category_section_none"),
            key="bf_cat_new_section"
        )
        new_queries = st.text_area(
            get_text("category_queries"),
            placeholder=get_text("category_queries_ph"),
            key="bf_cat_new_queries"
        )
        if st.button(get_text("add_watch_category_btn"), key="bf_cat_add_btn"):
            import re
            nid = new_id.strip()
            if new_id and new_name and new_queries:
                if not re.match(r"^[a-z0-9_]+$", nid):
                    st.warning(get_text("category_id_invalid"))
                elif nid in cats:
                    st.error(get_text("category_id_exists"))
                else:
                    cfg = {
                        "name": new_name,
                        "name_en": new_name,
                        "description": "",
                        "icon": "info",
                        "section": new_section,
                        "search_queries": [q.strip() for q in new_queries.splitlines() if q.strip()],
                        "enabled": True,
                    }
                    if add_category(nid, cfg):
                        st.success(get_text("watch_category_added"))
                        st.rerun()
                    else:
                        st.error(get_text("watch_category_failed"))
            else:
                st.warning(get_text("fill_fields"))

    if cats:
        from intelnexus.briefing.config import WATCH_CATEGORIES as _default_cats
        with st.expander(get_text("manage_watch_categories")):
            # 搜索过滤
            _cat_search = st.text_input(
                get_text("search_placeholder"),
                key="bf_cat_search",
                placeholder=get_text("search_placeholder"),
                label_visibility="collapsed",
            )
            _cat_query = _cat_search.strip().lower()
            _filtered_cats = {
                cid: cfg for cid, cfg in cats.items()
                if not _cat_query
                or _cat_query in cfg.get("name", "").lower()
                or _cat_query in cid.lower()
            }

            for cid, cfg in _filtered_cats.items():
                is_enabled = cfg.get("enabled", True)
                col_info, col_toggle, col_actions = st.columns([4, 1, 2])
                with col_info:
                    status_icon = "●" if is_enabled else "○"
                    st.write(f"{status_icon} **{cfg.get('name', cid)}**")
                    st.caption(f"{cid} · {len(cfg.get('search_queries', []))} 条查询")
                with col_toggle:
                    new_enabled = st.toggle(
                        get_text("enabled_label"), value=is_enabled,
                        key=f"bf_toggle_cat_{cid}",
                        label_visibility="collapsed"
                    )
                    if new_enabled != is_enabled:
                        update_category(cid, {"enabled": new_enabled})
                        st.rerun()
                with col_actions:
                    act_cols = st.columns(2)
                    with act_cols[0]:
                        if st.button(get_text("edit"), key=f"bf_edit_cat_{cid}",
                                     help=get_text("edit_category_help")):
                            st.session_state[f"editing_cat_{cid}"] = True
                            st.rerun()
                    with act_cols[1]:
                        is_default_cat = cid in _default_cats
                        del_label = get_text("disable_default") if is_default_cat else get_text("delete")
                        del_help = (
                            get_text("delete_default_help") if is_default_cat else get_text("delete_custom_help")
                        )
                        if is_default_cat:
                            if st.button(del_label, key=f"bf_del_cat_{cid}", help=del_help):
                                if remove_category(cid):
                                    st.success(get_text("watch_category_disabled"))
                                    st.rerun()
                        else:
                            if _delete_with_confirm(f"cat_{cid}", label=del_label, help=del_help):
                                if remove_category(cid):
                                    st.success(get_text("watch_category_deleted"))
                                    st.rerun()

                if st.session_state.get(f"editing_cat_{cid}"):
                    with st.container():
                        st.caption(get_text("edit_label"))
                        edit_name = st.text_input(get_text("name_label"), value=cfg.get('name', ''), key=f"bf_edit_cat_name_{cid}")
                        edit_queries = st.text_area(
                            get_text("category_queries"),
                            value='\n'.join(cfg.get('search_queries', [])),
                            key=f"bf_edit_cat_queries_{cid}"
                        )
                        ecol1, ecol2 = st.columns(2)
                        with ecol1:
                            if st.button(get_text("save"), key=f"bf_save_cat_{cid}"):
                                if edit_name and edit_queries:
                                    updates = {
                                        "name": edit_name,
                                        "name_en": edit_name,
                                        "search_queries": [q.strip() for q in edit_queries.splitlines() if q.strip()]
                                    }
                                    update_category(cid, updates)
                                    st.session_state[f"editing_cat_{cid}"] = False
                                    st.rerun()
                        with ecol2:
                            if st.button(get_text("cancel"), key=f"bf_cancel_cat_{cid}"):
                                st.session_state[f"editing_cat_{cid}"] = False
                                st.rerun()

    disabled_defaults = get_disabled_default_ids()
    if disabled_defaults:
        with st.expander(get_text("restore_defaults")):
            for did in disabled_defaults:
                r_info, r_act = st.columns([4, 1])
                with r_info:
                    st.caption(f"`{did}`")
                with r_act:
                    if st.button(get_text("restore_btn"), key=f"bf_restore_cat_{did}"):
                        if restore_default(did):
                            st.success(get_text("watch_category_restored"))
                            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)



def render_generate_top():
    """置顶生成主操作区（卡片头 + 下方「已选概览▾」折叠 + 右侧「生成简报」主按钮）

    默认已选好类目、推送开启，用户一眼可见直接点「生成简报」。
    卡片头与三个配置面板（Sources/Subscribers/Watch）保持同一视觉语言。
    """
    st.markdown(f'''
    <div class="bf-panel bf-panel--gen">
        <div class="bf-label">
            <span class="bf-label__tag">Generate</span>
            <span class="bf-label__title">{get_text("generate_briefing")}</span>
        </div>
    ''', unsafe_allow_html=True)

    from intelnexus.ui.briefing_runner import render_briefing_generate_controls
    render_briefing_generate_controls(key_prefix="bf", model=None, compact=False, top=True)

    st.markdown('</div>', unsafe_allow_html=True)


def render_briefing_settings():
    """可折叠配置区：用单个 toggle 收起三个配置面板，内部以横向 radio 组织

    点击引导条 step 会设置 st.session_state.bf_expand_settings / bf_active_tab，
    这里用 st.radio 的 index 参数控制默认选中，实现从引导条跳转到对应 tab。
    """
    # 用 toggle 控制配置区显隐（替代 st.expander，避免与面板内二级 expander 嵌套报错）
    expand_state = st.session_state.get("bf_expand_settings", False)
    st.session_state.bf_expand_settings = st.toggle(
        get_text("briefing_settings"),
        value=expand_state,
        key="bf_settings_toggle",
    )
    if not st.session_state.bf_expand_settings:
        return

    with st.container():
        tab_labels = [
            get_text("data_source_management"),
            get_text("subscription_management"),
            get_text("watch_categories_mgmt"),
            get_text("analytics_dashboard"),
            get_text("health_tab"),
        ]
        tab_keys = ["sources", "subs", "watch", "analytics", "health"]

        # Marker 供 CSS 把配置区 radio 渲染成 tab 样式
        st.markdown('<div class="bf-settings-tabs-marker" style="display:none"></div>', unsafe_allow_html=True)

        # 用 radio 替代 st.tabs。不传 index：带 key 的 radio 由自身维护选中状态，
        # 若传 index 会在每次 rerun 强制重置选中项，导致要点两下才生效。
        selected_label = st.radio(
            get_text("settings_tabs_label"),
            tab_labels,
            horizontal=True,
            label_visibility="collapsed",
            key="bf_settings_tab_radio",
        )
        active = tab_keys[tab_labels.index(selected_label)]
        st.session_state.bf_active_tab = active

        if active == "sources":
            render_data_sources_panel()
        elif active == "subs":
            render_subscriptions_panel()
        elif active == "analytics":
            from intelnexus.ui.analytics import render_analytics_dashboard
            render_analytics_dashboard()
        elif active == "health":
            from intelnexus.ui.health_dashboard import render_health_overview
            render_health_overview()
        else:
            render_watch_categories_panel()


def _render_onboarding():
    """简报中心 3 步引导条（纯展示 + 悬停提示，不跳转）

    用 session_state 中已有的数据源/订阅者配置进度标注当前到第几步；
    每个步骤为只读卡片，仅通过 help 提供悬停说明，不做点击跳转。
    """
    try:
        from intelnexus.config.sources import get_all_sources
        from intelnexus.config.subscriptions import get_all_subscribers
        sources = get_all_sources()
        subs = get_all_subscribers()
    except ImportError:
        sources, subs = {}, []

    step1_done = bool(sources.get("subscription_sources") or sources.get("custom_sources"))
    step2_done = bool(subs)

    steps = [
        (get_text("welcome_step_sources"), get_text("welcome_step_sources_desc"), step1_done, "sources"),
        (get_text("welcome_step_subscribers"), get_text("welcome_step_subscribers_desc"), step2_done, "subs"),
        (get_text("welcome_step_generate"), get_text("welcome_step_generate_desc"), False, None),
    ]

    st.markdown(f'<p style="color: var(--wb-text-secondary); font-size: 14px; margin: 0 0 12px 0;">{get_text("briefing_welcome_desc")}</p>', unsafe_allow_html=True)

    cols = st.columns(3)
    for i, (title, desc, done, tab_key) in enumerate(steps):
        if done:
            state_class = "bf-step--done"
            icon = "✓"
        elif i == 0 or (i == 1 and step1_done):
            # 当前应做的下一步：前一步已完成则为 current
            state_class = "bf-step--current"
            icon = "→"
        else:
            state_class = "bf-step--pending"
            icon = str(i + 1)
        label = f"{icon}  {title}"
        with cols[i]:
            # 隐藏 marker：携带状态类，供 CSS 经 :has() 给本列 button 上色
            st.markdown(
                f'<div class="bf-step-marker {state_class}" style="display:none"></div>',
                unsafe_allow_html=True,
            )
            # 纯展示卡片：仅悬停提示，点击不跳转（disabled 阻止交互但仍保留 help）
            st.button(
                label,
                key=f"bf_step_{tab_key or 'gen'}",
                use_container_width=True,
                help=desc,
                type="secondary",
                disabled=True,
            )


def render_briefing_center():
    """
    Briefing Center 主渲染函数（方案 A 布局重构）

    布局自上而下：
    - 隐藏标记（CSS :has() 作用域）
    - 3 步引导条（可点击跳转配置区）
    - 置顶生成主操作区（类目/推送/按钮同行 + 高级折叠模型）
    - 可折叠配置区（container + toggle 显隐 + 横向 tab 组织三个面板）
    - 结果输出区（预览 / 条目 / 历史 toggle + 历史列表）
    """
    # 隐藏标记 — 用于 CSS :has() 选择器将 workbench 样式限定到简报 Tab
    st.markdown('<div class="bf-workbench-scope"></div>', unsafe_allow_html=True)

    # 引导条（可点击）
    _render_onboarding()

    # 置顶生成主操作区
    render_generate_top()

    # 可折叠配置区
    render_briefing_settings()

    # 输出区
    render_briefing_preview()
    render_briefing_entries()

    # 历史记录常驻入口（toggle 替代原隐藏 session_state 开关）
    col_hist_toggle, _ = st.columns([2, 4])
    with col_hist_toggle:
        show_hist = st.toggle(
            get_text("show_history"),
            value=st.session_state.get("show_briefing_history", False),
            key="bf_history_toggle",
        )
        st.session_state.show_briefing_history = show_hist
    render_briefing_history()
