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


def render_briefing_history():
    """
    渲染简报历史列表

    守卫条件：st.session_state.show_briefing_history 为 True
    显示内容：历史简报列表，支持查看和删除
    """
    if not st.session_state.get("show_briefing_history"):
        return

    history = get_briefing_history().get_briefings(limit=20)

    st.markdown(f'<div class="bf-output"><div class="bf-output__header">{get_text("briefing_history")}</div>', unsafe_allow_html=True)

    if not history:
        st.markdown(f"<p class='bf-hint'>{get_text('briefing_history_empty')}</p>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        return

    for entry in history:
        created_at = entry.get("created_at", "")
        date_str = created_at[:10] if created_at else "—"
        time_str = created_at[11:16] if len(created_at) >= 16 else ""
        org = entry.get("organization", "") or "—"
        categories = entry.get("categories") or []
        cats_text = "、".join(categories[:3]) if categories else "—"
        if len(categories) > 3:
            cats_text += f" 等{len(categories)}个"
        subs = entry.get("subscribers_count", 0)

        st.markdown('<div class="bf-history-item">', unsafe_allow_html=True)
        info_col, act_col = st.columns([5, 2])
        with info_col:
            # 第一行：日期时间（主标题）
            time_label = f"{date_str} {time_str}".strip()
            st.markdown(
                f'<div class="bf-history-item__time">{time_label}</div>',
                unsafe_allow_html=True,
            )
            # 第二行：机构 + 关注点 + 推送（次要信息）
            st.markdown(
                f'<div class="bf-history-item__meta">'
                f'<span class="bf-history-item__org">{org}</span>'
                f'<span class="bf-history-item__sep">·</span>'
                f'<span>关注点：{cats_text}</span>'
                f'<span class="bf-history-item__sep">·</span>'
                f'<span>推送 {subs} 人</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        with act_col:
            v_col, d_col = st.columns(2)
            with v_col:
                if st.button(get_text("view"), key=f"view_{entry.get('filename')}", use_container_width=True):
                    load_briefing_for_preview(
                        entry.get("filename"),
                        entry.get("html_filename")
                    )
            with d_col:
                if _delete_with_confirm(
                    f"bf_{entry.get('filename')}",
                    label=get_text("delete"),
                    use_container_width=True,
                ):
                    delete_briefing(entry.get("filename"))
        st.markdown('</div>', unsafe_allow_html=True)

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
    """删除简报"""
    get_briefing_history().delete_briefing(filename)
    st.success(get_text("briefing_deleted"))
    st.rerun()


# ============================================================
#  Briefing Config Panels (Workbench style with tag bars):
# ============================================================


def render_data_sources_panel():
    """数据源管理面板 — 左右分栏：左侧搜索+列表，右侧详情/表单"""
    st.markdown(f'''
    <div class="bf-panel bf-panel--source">
        <div class="bf-label">
            <span class="bf-label__tag">Sources</span>
            <span class="bf-label__title">{get_text("data_source_management")}</span>
        </div>
    ''', unsafe_allow_html=True)

    try:
        from intelnexus.config.sources import (
            get_all_sources, add_source, remove_source, toggle_source,
            update_source, test_source,
        )
        SOURCES_AVAILABLE = True
    except ImportError:
        SOURCES_AVAILABLE = False

    if not SOURCES_AVAILABLE:
        st.markdown(f"<p class='bf-hint bf-hint--warn'>{get_text('module_unavailable')}</p>",
                     unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        return

    sources = get_all_sources()
    all_sources_list = sources.get("subscription_sources", []) + sources.get("custom_sources", [])
    categories = _watch_category_options()

    # ---- 左栏：搜索 + 列表 ----
    left, right = st.columns([1, 2])

    with left:
        search = st.text_input(
            get_text("search_placeholder"),
            key="bf_src_search",
            placeholder=get_text("search_placeholder"),
            label_visibility="collapsed",
        )
        query = search.strip().lower()
        filtered = [
            s for s in all_sources_list
            if not query
            or query in s.get("name", "").lower()
            or query in s.get("url", "").lower()
        ]

        if not filtered:
            st.caption(get_text("no_items"))
        else:
            for src in filtered:
                status_cls = "active" if src.get("enabled", True) else ""
                tag = "RSS" if src.get("fetch_type") == "rss" else "Web"
                label = f"{src['name'][:20]}  [{tag}]"
                if st.button(
                    label,
                    key=f"bf_src_sel_{src['id']}",
                    use_container_width=True,
                ):
                    st.session_state.bf_src_selected = src["id"]
                    st.rerun()

        # 底部：添加按钮 + 批量测试
        st.markdown("---")
        if st.button(f"+ {get_text('add_data_source')}", key="bf_src_add_btn",
                      use_container_width=True):
            st.session_state.bf_src_selected = None
            st.session_state.bf_src_mode = "add"
            st.rerun()

        if all_sources_list:
            if st.button(get_text("batch_test"), key="bf_src_batch_test",
                          use_container_width=True):
                st.session_state.bf_src_batch_test = True
                st.rerun()

    # ---- 批量测试结果 ----
    if st.session_state.get("bf_src_batch_test"):
        with st.spinner(get_text("testing")):
            results = []
            for src in all_sources_list:
                ft = src.get("fetch_type", "web_engine")
                r = test_source(src["url"], ft, timeout=8)
                results.append((src["name"], r))
            st.session_state.bf_src_batch_test = False

        with right:
            st.markdown(f"**{get_text('test_results')}**")
            for name, r in results:
                cls = "active" if r["success"] else "error"
                status = get_text("source_ok") if r["success"] else get_text("source_fail")
                st.markdown(
                    f'<span class="status-dot {cls}"></span> '
                    f'{html.escape(name)} — {status} ({r.get("latency_ms", "—")}ms)',
                    unsafe_allow_html=True,
                )
            st.markdown("---")

    # ---- 右栏：详情 / 添加 / 编辑 ----
    with right:
        mode = st.session_state.get("bf_src_mode")
        sel_id = st.session_state.get("bf_src_selected")

        if mode == "add":
            # ---- 添加表单 ----
            st.markdown(f"**{get_text('add_data_source')}**")
            src_type = st.selectbox(
                get_text("source_type"),
                [get_text("source_type_rss"), get_text("source_type_web")],
                key="bf_src_new_type",
            )
            src_name = st.text_input(get_text("source_name"), key="bf_src_new_name")
            src_url = st.text_input(get_text("source_url"), key="bf_src_new_url")
            cat_keys = list(categories.keys())
            src_cat = st.selectbox(
                get_text("source_category"), cat_keys,
                format_func=lambda x: categories[x],
                key="bf_src_new_cat",
            )
            c1, c2 = st.columns(2)
            with c1:
                if st.button(get_text("add_source"), key="bf_src_new_submit",
                              use_container_width=True):
                    if src_name and src_url:
                        tv = "rss" if src_type == get_text("source_type_rss") else "web"
                        if add_source(tv, src_name, src_url, src_cat):
                            st.success(get_text("source_added"))
                            st.session_state.bf_src_mode = None
                            st.rerun()
                        else:
                            st.error(get_text("source_add_failed"))
                    else:
                        st.warning(get_text("fill_fields"))
            with c2:
                if st.button(get_text("cancel"), key="bf_src_new_cancel",
                              use_container_width=True):
                    st.session_state.bf_src_mode = None
                    st.rerun()

            # 预设导入 + OPML 导入
            _render_source_import_section(categories)

        elif mode == "edit" and sel_id:
            # ---- 编辑表单 ----
            src = next((s for s in all_sources_list if s["id"] == sel_id), None)
            if not src:
                st.session_state.bf_src_mode = None
            else:
                st.markdown(f"**{get_text('edit_label')}**")
                edit_name = st.text_input(get_text("name_label"), value=src["name"],
                                           key="bf_src_ed_name")
                edit_url = st.text_input("URL", value=src["url"], key="bf_src_ed_url")
                cat_keys = list(categories.keys())
                cur_cat = src.get("category", "")
                edit_cat = st.selectbox(
                    get_text("category_label"), cat_keys,
                    index=cat_keys.index(cur_cat) if cur_cat in cat_keys else 0,
                    format_func=lambda x: categories[x],
                    key="bf_src_ed_cat",
                )
                c1, c2 = st.columns(2)
                with c1:
                    if st.button(get_text("save"), key="bf_src_ed_save",
                                  use_container_width=True):
                        if edit_name and edit_url:
                            update_source(sel_id, {
                                "name": edit_name, "url": edit_url,
                                "category": edit_cat,
                            })
                            st.session_state.bf_src_mode = None
                            st.rerun()
                        else:
                            st.warning(get_text("fill_fields"))
                with c2:
                    if st.button(get_text("cancel"), key="bf_src_ed_cancel",
                                  use_container_width=True):
                        st.session_state.bf_src_mode = None
                        st.rerun()

        elif sel_id:
            # ---- 详情视图 ----
            src = next((s for s in all_sources_list if s["id"] == sel_id), None)
            if not src:
                st.session_state.bf_src_selected = None
            else:
                enabled = src.get("enabled", True)
                tag = "RSS" if src.get("fetch_type") == "rss" else get_text("source_type_web")
                cat_label = categories.get(src.get("category", ""), src.get("category", "—"))
                st.markdown(f"### {html.escape(src['name'])}")
                st.caption(f"{tag} · {cat_label}")
                st.markdown(f"`{html.escape(src['url'][:80])}`")
                status_cls = "active" if enabled else "error"
                status_text = get_text("enabled_label") if enabled else get_text("disabled_label")
                st.markdown(
                    f'<span class="status-dot {status_cls}"></span> {status_text}',
                    unsafe_allow_html=True,
                )

                c1, c2, c3 = st.columns(3)
                with c1:
                    if st.button(get_text("test_source_btn"), key="bf_src_detail_test",
                                  use_container_width=True):
                        ft = src.get("fetch_type", "web_engine")
                        result = test_source(src["url"], ft)
                        if result["success"]:
                            st.success(get_text("source_test_ok_msg").format(
                                latency=result.get("latency_ms", "?")))
                        else:
                            st.error(get_text("source_test_fail_msg").format(
                                reason=result["message"]))
                with c2:
                    if st.button(get_text("edit"), key="bf_src_detail_edit",
                                  use_container_width=True):
                        st.session_state.bf_src_mode = "edit"
                        st.rerun()
                with c3:
                    if st.button(get_text("delete"), key="bf_src_detail_del",
                                  use_container_width=True):
                        st.session_state[f"confirm_del_src_{sel_id}"] = True
                        st.rerun()

                if st.session_state.get(f"confirm_del_src_{sel_id}"):
                    st.warning(get_text("confirm_delete") + "?")
                    dc1, dc2 = st.columns(2)
                    with dc1:
                        if st.button(get_text("confirm_delete"), key="bf_src_del_confirm",
                                      use_container_width=True, type="primary"):
                            remove_source(sel_id)
                            st.session_state.bf_src_selected = None
                            st.session_state.bf_src_mode = None
                            st.session_state.pop(f"confirm_del_src_{sel_id}", None)
                            st.rerun()
                    with dc2:
                        if st.button(get_text("cancel"), key="bf_src_del_cancel",
                                      use_container_width=True):
                            st.session_state.pop(f"confirm_del_src_{sel_id}", None)
                            st.rerun()

                # 启用/禁用切换
                st.markdown("---")
                new_enabled = st.toggle(
                    get_text("enabled_label"), value=enabled,
                    key="bf_src_toggle",
                )
                if new_enabled != enabled:
                    toggle_source(sel_id, new_enabled)
                    st.rerun()

        else:
            st.info(get_text("no_selection"))

    st.markdown('</div>', unsafe_allow_html=True)


def _render_source_import_section(categories: dict) -> None:
    """数据源面板内的预设导入 + OPML 导入（仅在添加模式下显示）"""
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
                from intelnexus.config.sources import add_source as _add_src
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
                    ok = _add_src("rss", outline.get("text", "feed"), xml_url,
                                  cat_for_feed, fetch_type="rss")
                    added += 1 if ok else 0
                st.success(get_text("preset_imported").format(added=added))

    with st.expander(get_text("import_opml")):
        opml_file = st.file_uploader(get_text("opml_upload"), type=["opml", "xml"],
                                      key="bf_opml_uploader")
        _cats_now = _watch_category_options()
        if opml_file is not None and _cats_now:
            opml_cat = st.selectbox(
                get_text("source_category"),
                list(_cats_now.keys()),
                format_func=lambda x: _cats_now[x],
                key="bf_opml_category",
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


def render_subscriptions_panel():
    """订阅者管理面板 — 左右分栏：左侧搜索+列表，右侧详情/表单"""
    st.markdown(f'''
    <div class="bf-panel bf-panel--sub">
        <div class="bf-label">
            <span class="bf-label__tag">Subscribers</span>
            <span class="bf-label__title">{get_text("subscription_management")}</span>
        </div>
    ''', unsafe_allow_html=True)

    try:
        from intelnexus.config.subscriptions import (
            get_all_subscribers, add_subscriber, remove_subscriber, update_subscriber,
        )
        SUBSCRIPTION_AVAILABLE = True
    except ImportError:
        SUBSCRIPTION_AVAILABLE = False

    if not SUBSCRIPTION_AVAILABLE:
        st.markdown(f"<p class='bf-hint bf-hint--warn'>{get_text('module_unavailable')}</p>",
                     unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        return

    from intelnexus.config.email_settings import (
        get_email_settings, save_email_settings, test_email_settings,
    )
    _render_scheduler_status_banner()

    subscribers = get_all_subscribers()
    categories = _watch_category_options()

    # ---- 左栏：搜索 + 列表 ----
    left, right = st.columns([1, 2])

    with left:
        search = st.text_input(
            get_text("search_placeholder"),
            key="bf_sub_search",
            placeholder=get_text("search_placeholder"),
            label_visibility="collapsed",
        )
        query = search.strip().lower()
        filtered = [
            s for s in subscribers
            if not query
            or query in s.get("name", "").lower()
            or query in s.get("email", "").lower()
        ]

        if not filtered:
            st.caption(get_text("no_items"))
        else:
            for sub in filtered:
                sched_enabled = sub.get("schedule", {}).get("enabled", False)
                status_cls = "active" if sched_enabled else "error"
                label = f"{sub['name'][:20]}  {sub['email'][:18]}"
                if st.button(
                    label,
                    key=f"bf_sub_sel_{sub['id']}",
                    use_container_width=True,
                ):
                    st.session_state.bf_sub_selected = sub["id"]
                    st.rerun()

        st.markdown("---")
        if st.button(f"+ {get_text('add_subscriber')}", key="bf_sub_add_btn",
                      use_container_width=True):
            st.session_state.bf_sub_selected = None
            st.session_state.bf_sub_mode = "add"
            st.rerun()

    # ---- 右栏：详情 / 添加 / 编辑 ----
    with right:
        mode = st.session_state.get("bf_sub_mode")
        sel_id = st.session_state.get("bf_sub_selected")

        if mode == "add":
            st.markdown(f"**{get_text('add_subscriber')}**")
            _render_subscriber_form(categories, is_edit=False)

        elif mode == "edit" and sel_id:
            sub = next((s for s in subscribers if s["id"] == sel_id), None)
            if not sub:
                st.session_state.bf_sub_mode = None
            else:
                st.markdown(f"**{get_text('edit_label')}**")
                _render_subscriber_form(categories, is_edit=True, subscriber=sub)

        elif sel_id:
            sub = next((s for s in subscribers if s["id"] == sel_id), None)
            if not sub:
                st.session_state.bf_sub_selected = None
            else:
                sched = sub.get("schedule", {})
                channels = sub.get("channels", {})
                active_ch = [k for k, v in channels.items()
                             if isinstance(v, dict) and v.get("enabled")]
                cats = sub.get("categories", [])

                st.markdown(f"### {html.escape(sub['name'])}")
                st.caption(html.escape(sub['email']))

                status_cls = "active" if sched.get("enabled") else "error"
                status_text = get_text("enabled_label") if sched.get("enabled") else get_text("disabled_label")
                st.markdown(
                    f'<span class="status-dot {status_cls}"></span> {status_text}',
                    unsafe_allow_html=True,
                )

                st.markdown(
                    f"**{get_text('push_channels')}:** {', '.join(active_ch) or '—'}  \n"
                    f"**{get_text('schedule_settings')}:** {sched.get('time', '—')} "
                    f"({sched.get('timezone', '—')})  \n"
                    f"**{get_text('watch_categories')}:** "
                    f"{', '.join(categories.get(c, c) for c in cats) if cats else '—'}"
                )

                c1, c2, c3 = st.columns(3)
                with c1:
                    if st.button(get_text("manual_push_now"), key="bf_sub_push",
                                  use_container_width=True):
                        try:
                            from intelnexus.briefing.scheduler_registry import get_scheduler
                            sched_obj = get_scheduler()
                            if sched_obj and hasattr(sched_obj, '_send_to_subscriber'):
                                sched_obj._send_to_subscriber(sub)
                                st.success(get_text("manual_push_success"))
                            else:
                                st.warning("调度器不可用")
                        except Exception as e:
                            st.error(get_text("manual_push_failed"))
                with c2:
                    if st.button(get_text("edit"), key="bf_sub_detail_edit",
                                  use_container_width=True):
                        st.session_state.bf_sub_mode = "edit"
                        st.rerun()
                with c3:
                    if st.button(get_text("delete"), key="bf_sub_detail_del",
                                  use_container_width=True):
                        st.session_state[f"confirm_del_sub_{sel_id}"] = True
                        st.rerun()

                if st.session_state.get(f"confirm_del_sub_{sel_id}"):
                    st.warning(get_text("confirm_delete") + "?")
                    dc1, dc2 = st.columns(2)
                    with dc1:
                        if st.button(get_text("confirm_delete"), key="bf_sub_del_confirm",
                                      use_container_width=True, type="primary"):
                            remove_subscriber(sel_id)
                            from intelnexus.briefing.scheduler_registry import on_subscriber_changed
                            on_subscriber_changed(sel_id, "remove")
                            st.session_state.bf_sub_selected = None
                            st.session_state.bf_sub_mode = None
                            st.session_state.pop(f"confirm_del_sub_{sel_id}", None)
                            st.rerun()
                    with dc2:
                        if st.button(get_text("cancel"), key="bf_sub_del_cancel",
                                      use_container_width=True):
                            st.session_state.pop(f"confirm_del_sub_{sel_id}", None)
                            st.rerun()

        else:
            st.info(get_text("no_selection"))

    st.markdown('</div>', unsafe_allow_html=True)


def _render_subscriber_form(categories: dict, is_edit: bool = False,
                            subscriber: dict = None) -> None:
    """订阅者添加/编辑共用表单"""
    sub = subscriber or {}
    _ch = sub.get("channels", {})
    _sch = sub.get("schedule", {})
    prefix = "bf_sub_ed" if is_edit else "bf_sub_new"
    cats_selected = sub.get("categories", [])

    name = st.text_input(get_text("subscriber_name"),
                          value=sub.get("name", ""), key=f"{prefix}_name")
    email_val = st.text_input(get_text("subscriber_email"),
                               value=sub.get("email", ""), key=f"{prefix}_email")

    st.markdown(f"**{get_text('push_channels')}**")
    c1, c2, c3 = st.columns(3)
    with c1:
        email_on = st.checkbox(get_text("push_channel_email"),
                                value=(_ch.get("email") or {}).get("enabled", True),
                                key=f"{prefix}_ch_email")
    with c2:
        wecom_on = st.checkbox(get_text("push_channel_wecom"),
                                value=(_ch.get("wecom") or {}).get("enabled", False),
                                key=f"{prefix}_ch_wecom")
    with c3:
        ding_on = st.checkbox(get_text("push_channel_dingtalk"),
                               value=(_ch.get("dingtalk") or {}).get("enabled", False),
                               key=f"{prefix}_ch_ding")

    wecom_wh = ding_wh = ding_sec = ""
    if wecom_on:
        wecom_wh = st.text_input(get_text("wecom_webhook"),
                                  value=(_ch.get("wecom") or {}).get("webhook", ""),
                                  key=f"{prefix}_wh_wecom")
    if ding_on:
        ding_wh = st.text_input(get_text("dingtalk_webhook"),
                                 value=(_ch.get("dingtalk") or {}).get("webhook", ""),
                                 key=f"{prefix}_wh_ding")
        ding_sec = st.text_input(get_text("dingtalk_secret"),
                                  value=(_ch.get("dingtalk") or {}).get("secret", ""),
                                  type="password", key=f"{prefix}_sec_ding")

    st.markdown(f"**{get_text('schedule_settings')}**")
    from datetime import time as dtime
    try:
        _hh, _mm = map(int, (_sch.get("time", "08:00")).split(":"))
    except Exception:
        _hh, _mm = 8, 0
    c1, c2 = st.columns(2)
    with c1:
        push_time = st.time_input(get_text("push_time"),
                                   value=dtime(_hh, _mm), key=f"{prefix}_time")
    with c2:
        _tz_opts = ["Asia/Shanghai", "America/New_York", "Europe/London", "Asia/Tokyo"]
        _cur_tz = _sch.get("timezone", "Asia/Shanghai")
        push_tz = st.selectbox(
            get_text("push_timezone"), _tz_opts,
            index=_tz_opts.index(_cur_tz) if _cur_tz in _tz_opts else 0,
            key=f"{prefix}_tz",
        )

    _day_opts = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    _day_lbl = [get_text("push_days_mon"), get_text("push_days_tue"),
                get_text("push_days_wed"), get_text("push_days_thu"),
                get_text("push_days_fri"), get_text("push_days_sat"),
                get_text("push_days_sun")]
    push_days = st.multiselect(
        get_text("push_days"), _day_opts,
        default=_sch.get("days", ["mon", "tue", "wed", "thu", "fri"]),
        format_func=lambda x: _day_lbl[_day_opts.index(x)],
        key=f"{prefix}_days",
    )

    st.markdown(f"**{get_text('watch_categories')}**")
    selected_cats = []
    for cid, cname in categories.items():
        if st.checkbox(cname, value=cid in cats_selected, key=f"{prefix}_cat_{cid}"):
            selected_cats.append(cid)

    c1, c2 = st.columns(2)
    with c1:
        if st.button(get_text("save"), key=f"{prefix}_save", use_container_width=True):
            import re
            email_re = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not name or not email_val:
                st.warning(get_text("fill_fields"))
            elif not re.match(email_re, email_val):
                st.warning(get_text("invalid_email"))
            else:
                channels = {
                    "email": {"enabled": email_on, "address": email_val},
                    "wecom": {"enabled": wecom_on, "webhook": wecom_wh},
                    "dingtalk": {"enabled": ding_on, "webhook": ding_wh, "secret": ding_sec},
                }
                schedule = {
                    "time": push_time.strftime("%H:%M"),
                    "timezone": push_tz,
                    "enabled": True,
                    "days": push_days,
                }
                if is_edit and sub:
                    update_subscriber(sub["id"], {
                        "name": name, "email": email_val,
                        "categories": selected_cats,
                        "channels": channels, "schedule": schedule,
                    })
                    from intelnexus.briefing.scheduler_registry import on_subscriber_changed
                    on_subscriber_changed(sub["id"], "update")
                    st.session_state.bf_sub_mode = None
                else:
                    new_id = add_subscriber(name, email_val, channels, schedule, selected_cats)
                    if new_id:
                        st.success(get_text("subscriber_added"))
                        from intelnexus.briefing.scheduler_registry import on_subscriber_changed
                        on_subscriber_changed(new_id, "add")
                        st.session_state.bf_sub_mode = None
                    else:
                        st.error(get_text("subscriber_add_failed"))
                st.rerun()
    with c2:
        if st.button(get_text("cancel"), key=f"{prefix}_cancel", use_container_width=True):
            st.session_state.bf_sub_mode = None
            st.rerun()


def render_watch_categories_panel():
    """关注点管理面板 — 左右分栏：左侧搜索+列表，右侧详情/表单"""
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
        st.markdown(f"<p class='bf-hint bf-hint--warn'>{get_text('module_unavailable')}</p>",
                     unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        return

    cats = get_all_categories()
    try:
        from intelnexus.briefing.config import BRIEFING_SECTIONS as _sections
    except ImportError:
        _sections = []

    # ---- 左栏：搜索 + 列表 ----
    left, right = st.columns([1, 2])

    with left:
        search = st.text_input(
            get_text("search_placeholder"),
            key="bf_cat_search",
            placeholder=get_text("search_placeholder"),
            label_visibility="collapsed",
        )
        query = search.strip().lower()
        filtered = {
            cid: cfg for cid, cfg in cats.items()
            if not query
            or query in cfg.get("name", "").lower()
            or query in cid.lower()
        }

        if not filtered:
            st.caption(get_text("no_items"))
        else:
            for cid, cfg in filtered.items():
                is_enabled = cfg.get("enabled", True)
                status_cls = "active" if is_enabled else ""
                label = f"{cfg.get('name', cid)[:20]}"
                if st.button(
                    label,
                    key=f"bf_cat_sel_{cid}",
                    use_container_width=True,
                ):
                    st.session_state.bf_cat_selected = cid
                    st.rerun()

        st.markdown("---")
        if st.button(f"+ {get_text('add_watch_category')}", key="bf_cat_add_btn",
                      use_container_width=True):
            st.session_state.bf_cat_selected = None
            st.session_state.bf_cat_mode = "add"
            st.rerun()

        # 恢复被禁用的内置类目
        disabled_defaults = get_disabled_default_ids()
        if disabled_defaults:
            with st.expander(get_text("restore_defaults")):
                for did in disabled_defaults:
                    if st.button(did, key=f"bf_restore_{did}", use_container_width=True):
                        if restore_default(did):
                            st.success(get_text("watch_category_restored"))
                            st.rerun()

    # ---- 右栏：详情 / 添加 / 编辑 ----
    with right:
        mode = st.session_state.get("bf_cat_mode")
        sel_id = st.session_state.get("bf_cat_selected")

        if mode == "add":
            st.markdown(f"**{get_text('add_watch_category')}**")
            new_id = st.text_input(get_text("category_id"), key="bf_cat_new_id")
            new_name = st.text_input(get_text("category_name"), key="bf_cat_new_name")
            _section_opts = [""] + list(_sections)
            new_section = st.selectbox(
                get_text("category_section"), _section_opts,
                format_func=lambda s: s if s else get_text("category_section_none"),
                key="bf_cat_new_section",
            )
            new_queries = st.text_area(
                get_text("category_queries"),
                placeholder=get_text("category_queries_ph"),
                key="bf_cat_new_queries",
            )
            c1, c2 = st.columns(2)
            with c1:
                if st.button(get_text("add_watch_category_btn"), key="bf_cat_new_submit",
                              use_container_width=True):
                    import re
                    nid = new_id.strip()
                    if new_id and new_name and new_queries:
                        if not re.match(r"^[a-z0-9_]+$", nid):
                            st.warning(get_text("category_id_invalid"))
                        elif nid in cats:
                            st.error(get_text("category_id_exists"))
                        else:
                            cfg = {
                                "name": new_name, "name_en": new_name,
                                "description": "", "icon": "info",
                                "section": new_section,
                                "search_queries": [q.strip() for q in new_queries.splitlines() if q.strip()],
                                "enabled": True,
                            }
                            if add_category(nid, cfg):
                                st.success(get_text("watch_category_added"))
                                st.session_state.bf_cat_mode = None
                                st.rerun()
                            else:
                                st.error(get_text("watch_category_failed"))
                    else:
                        st.warning(get_text("fill_fields"))
            with c2:
                if st.button(get_text("cancel"), key="bf_cat_new_cancel",
                              use_container_width=True):
                    st.session_state.bf_cat_mode = None
                    st.rerun()

        elif mode == "edit" and sel_id:
            cfg = cats.get(sel_id)
            if not cfg:
                st.session_state.bf_cat_mode = None
            else:
                st.markdown(f"**{get_text('edit_label')}**")
                edit_name = st.text_input(get_text("name_label"),
                                           value=cfg.get("name", ""),
                                           key="bf_cat_ed_name")
                edit_queries = st.text_area(
                    get_text("category_queries"),
                    value="\n".join(cfg.get("search_queries", [])),
                    key="bf_cat_ed_queries",
                )
                c1, c2 = st.columns(2)
                with c1:
                    if st.button(get_text("save"), key="bf_cat_ed_save",
                                  use_container_width=True):
                        if edit_name and edit_queries:
                            update_category(sel_id, {
                                "name": edit_name, "name_en": edit_name,
                                "search_queries": [q.strip() for q in edit_queries.splitlines() if q.strip()],
                            })
                            st.session_state.bf_cat_mode = None
                            st.rerun()
                        else:
                            st.warning(get_text("fill_fields"))
                with c2:
                    if st.button(get_text("cancel"), key="bf_cat_ed_cancel",
                                  use_container_width=True):
                        st.session_state.bf_cat_mode = None
                        st.rerun()

        elif sel_id:
            cfg = cats.get(sel_id)
            if not cfg:
                st.session_state.bf_cat_selected = None
            else:
                is_enabled = cfg.get("enabled", True)
                st.markdown(f"### {html.escape(cfg.get('name', sel_id))}")
                st.caption(f"`{sel_id}`")

                status_cls = "active" if is_enabled else "error"
                status_text = get_text("enabled_label") if is_enabled else get_text("disabled_label")
                st.markdown(
                    f'<span class="status-dot {status_cls}"></span> {status_text}',
                    unsafe_allow_html=True,
                )

                queries = cfg.get("search_queries", [])
                if queries:
                    st.markdown(f"**{get_text('category_queries')}** ({len(queries)})")
                    for q in queries:
                        st.markdown(f"- `{q}`")

                c1, c2, c3 = st.columns(3)
                with c1:
                    new_enabled = st.toggle(
                        get_text("enabled_label"), value=is_enabled,
                        key="bf_cat_toggle",
                    )
                    if new_enabled != is_enabled:
                        update_category(sel_id, {"enabled": new_enabled})
                        st.rerun()
                with c2:
                    if st.button(get_text("edit"), key="bf_cat_detail_edit",
                                  use_container_width=True):
                        st.session_state.bf_cat_mode = "edit"
                        st.rerun()
                with c3:
                    from intelnexus.briefing.config import WATCH_CATEGORIES as _default_cats
                    is_default = sel_id in _default_cats
                    del_label = get_text("disable_default") if is_default else get_text("delete")
                    if st.button(del_label, key="bf_cat_detail_del",
                                  use_container_width=True):
                        if is_default:
                            if remove_category(sel_id):
                                st.success(get_text("watch_category_disabled"))
                                st.session_state.bf_cat_selected = None
                                st.rerun()
                        else:
                            st.session_state[f"confirm_del_cat_{sel_id}"] = True
                            st.rerun()

                if st.session_state.get(f"confirm_del_cat_{sel_id}"):
                    st.warning(get_text("confirm_delete") + "?")
                    dc1, dc2 = st.columns(2)
                    with dc1:
                        if st.button(get_text("confirm_delete"), key="bf_cat_del_confirm",
                                      use_container_width=True, type="primary"):
                            if remove_category(sel_id):
                                st.success(get_text("watch_category_deleted"))
                            st.session_state.bf_cat_selected = None
                            st.session_state.bf_cat_mode = None
                            st.session_state.pop(f"confirm_del_cat_{sel_id}", None)
                            st.rerun()
                    with dc2:
                        if st.button(get_text("cancel"), key="bf_cat_del_cancel",
                                      use_container_width=True):
                            st.session_state.pop(f"confirm_del_cat_{sel_id}", None)
                            st.rerun()
        else:
            st.info(get_text("no_selection"))

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
