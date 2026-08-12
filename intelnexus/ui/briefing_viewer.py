"""
简报预览和历史查看
==================
在 Streamlit 主面板中展示简报内容和历史记录

Design: Intelligence Workbench (cold-gray industrial)
- Function tag bars (4px colored left border) for each panel
- No emoji, no welcome page, no step cards
- Single-column vertical flow
"""

import streamlit as st
from datetime import datetime
from intelnexus.config.briefing_history import get_briefing_history
from intelnexus.ui.i18n import get_text
from intelnexus.ui.icons import icon


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

    st.markdown(
        '<div class="bf-output">'
        f'<div class="bf-output__header">{get_text("briefing_entries_title")} ({len(entries)})</div>',
        unsafe_allow_html=True,
    )

    # 按严重度排序：有冲突的优先，按冲突严重度降序
    sorted_entries = sorted(
        entries,
        key=lambda e: (e.get("has_conflict", False), e.get("conflict_severity", 0)),
        reverse=True,
    )

    for i, entry in enumerate(sorted_entries):
        title = entry.get("title", get_text("untitled"))
        url = entry.get("url", "")
        source = entry.get("source", "Unknown")
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

        col_feedback, col_btn, col_url = st.columns([1, 1, 5])
        
        with col_feedback:
            # 反馈按钮（按分类记录）
            entry_url = url or ""
            category = entry.get("category", "unknown")
            if entry_url:
                c1, c2, c3 = st.columns(3)
                with c1:
                    if st.button(
                        get_text("feedback_up"),
                        key=f"up_{category}_{filename}_{i}",
                        help=get_text("feedback_hint"),
                    ):
                        from intelnexus.config.feedback import save_briefing_feedback, track_feedback
                        save_briefing_feedback(category, entry_url, "up")
                        track_feedback(entry_url, "up", "briefing")
                        st.toast(get_text("feedback_marked"))
                        st.rerun()
                with c2:
                    if st.button(
                        get_text("feedback_down"),
                        key=f"down_{category}_{filename}_{i}",
                        help=get_text("feedback_hint"),
                    ):
                        from intelnexus.config.feedback import save_briefing_feedback, track_feedback
                        save_briefing_feedback(category, entry_url, "down")
                        track_feedback(entry_url, "down", "briefing")
                        st.toast(get_text("feedback_marked"))
                        st.rerun()
                with c3:
                    # 收藏到知识库
                    from intelnexus.config.knowledge_base import get_items, add_item
                    existing_kb = get_items(url=entry_url, item_type="briefing_entry")
                    if existing_kb:
                        st.caption(get_text('kb_saved'))
                    else:
                        if st.button(get_text("kb_save"), key=f"kb_{category}_{filename}_{i}",
                                     help=get_text("kb_save")):
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
                            st.toast("已收藏到知识库")
                            st.rerun()
        
        with col_btn:
            btn_label = get_text('investigate_like_this')
            if has_conflict and conflict_sev >= 0.7:
                btn_label = f"! {btn_label}"
            if st.button(
                btn_label,
                key=f"forensic_{filename}_{i}",
                use_container_width=True,
                help=get_text("investigate_help"),
            ):
                query = title if title else (url or "unknown")
                st.session_state.pending_forensic_query = query
                st.session_state.pending_forensic_mode = "all"
                st.session_state.switch_to_search = True
                st.rerun()
        with col_url:
            if url:
                st.caption(url[:100])

    st.markdown('</div>', unsafe_allow_html=True)


def render_recommendations():
    """渲染推荐区域"""
    from intelnexus.briefing.recommendation import get_related_topics, get_similar_briefings
    
    # 获取当前简报
    current_briefing_id = st.session_state.get("current_briefing_filename", "")
    if not current_briefing_id:
        # 尝试从历史记录获取最近的简报
        history = get_briefing_history().get_briefings(limit=1)
        if history:
            current_briefing_id = history[0].get("id", "")
    
    if not current_briefing_id:
        return
    
    # 获取推荐
    related_topics = get_related_topics()
    similar_briefings = get_similar_briefings(current_briefing_id)
    
    if not related_topics and not similar_briefings:
        return
    
    st.markdown(
        '<div class="bf-panel bf-panel--gen">'
        f'<div class="bf-label"><span class="bf-label__tag">TIPS</span>'
        f'<span class="bf-label__title">{get_text("recommendation")}</span></div>',
        unsafe_allow_html=True,
    )
    
    if related_topics:
        st.markdown(f"**{get_text('related_topics')}：**")
        for item in related_topics:
            topic = item["topic"]
            st.markdown(f"- {icon('link', 'sm', 'terracotta')} {topic.name}", unsafe_allow_html=True)
    
    if similar_briefings:
        st.markdown(f"**{get_text('similar_briefings')}：**")
        for item in similar_briefings:
            briefing = item["briefing"]
            sim = item["similarity"]
            st.markdown(f"- {icon('entry', 'sm', 'gray')} {briefing.get('id', '')} ({sim:.0%}相似)", unsafe_allow_html=True)
    
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
                if st.button(get_text("delete"), key=f"del_{entry.get('filename')}", use_container_width=True):
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
    """数据源管理面板（蓝色标签条）"""
    st.markdown(f'''
    <div class="bf-panel bf-panel--source">
        <div class="bf-label">
            <span class="bf-label__tag">Sources</span>
            <span class="bf-label__title">{get_text("data_source_management")}</span>
        </div>
    ''', unsafe_allow_html=True)

    try:
        from intelnexus.config.sources import get_all_sources, add_source, remove_source, toggle_source
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

        categories = {
            "ai_gov_usage": get_text("category_gov"),
            "ai_china_narrative": get_text("category_china"),
            "ai_legislation": get_text("category_legislation"),
            "ai_data_leak": get_text("category_leak")
        }
        source_category = st.selectbox(
            get_text("source_category"),
            list(categories.keys()),
            format_func=lambda x: categories[x],
            key="bf_source_category_selector"
        )

        if st.button(get_text("add_source"), key="bf_add_source_btn"):
            if source_name and source_url:
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

    if all_sources_list:
        with st.expander(get_text("manage_sources")):
            for source in all_sources_list:
                col_info, col_toggle, col_delete = st.columns([4, 1, 1])
                with col_info:
                    st.write(f"**{source['name']}**")
                    st.caption(f"{source['url'][:50]}...")
                with col_toggle:
                    enabled = st.toggle(get_text("enabled_label"), value=source.get("enabled", True), key=f"bf_toggle_{source['id']}", label_visibility="collapsed")
                    if enabled != source.get("enabled", True):
                        toggle_source(source['id'], enabled)
                        st.rerun()
                with col_delete:
                    if st.button(get_text("delete"), key=f"bf_del_source_{source['id']}"):
                        if remove_source(source['id']):
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
        from intelnexus.config.subscriptions import get_all_subscribers, add_subscriber, remove_subscriber
        SUBSCRIPTION_AVAILABLE = True
    except ImportError:
        SUBSCRIPTION_AVAILABLE = False

    if not SUBSCRIPTION_AVAILABLE:
        st.markdown(f"<p class='bf-hint bf-hint--warn'>{get_text('module_unavailable')}</p>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # SMTP 全局配置
    with st.expander(get_text("email_settings"), expanded=False):
        if "email_config" not in st.session_state:
            st.session_state.email_config = {
                "smtp_server": "", "smtp_port": 587,
                "username": "", "password": "", "use_tls": True
            }

        email_config = st.session_state.email_config
        col_smtp1, col_smtp2 = st.columns(2)
        with col_smtp1:
            smtp_server = st.text_input(
                get_text("smtp_server"),
                value=email_config.get("smtp_server", ""),
                key="bf_smtp_server_input"
            )
            smtp_port = st.number_input(
                get_text("smtp_port"),
                value=email_config.get("smtp_port", 587),
                key="bf_smtp_port_input"
            )
        with col_smtp2:
            smtp_username = st.text_input(
                get_text("smtp_username"),
                value=email_config.get("username", ""),
                key="bf_smtp_username_input"
            )
            smtp_password = st.text_input(
                get_text("smtp_password"),
                value=email_config.get("password", ""),
                type="password",
                key="bf_smtp_password_input"
            )
        smtp_use_tls = st.checkbox(
            get_text("smtp_use_tls"),
            value=email_config.get("use_tls", True),
            key="bf_smtp_use_tls_input"
        )

        if st.button(get_text("save_email_settings"), key="bf_save_email_btn"):
            st.session_state.email_config = {
                "smtp_server": smtp_server, "smtp_port": smtp_port,
                "username": smtp_username, "password": smtp_password,
                "use_tls": smtp_use_tls
            }
            st.success(get_text("email_settings_saved"))

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
        categories = {
            "ai_gov_usage": get_text("category_gov"),
            "ai_china_narrative": get_text("category_china"),
            "ai_legislation": get_text("category_legislation"),
            "ai_data_leak": get_text("category_leak")
        }
        selected_categories = []
        for cat_id, cat_name in categories.items():
            if st.checkbox(cat_name, value=True, key=f"bf_cat_{cat_id}"):
                selected_categories.append(cat_id)

        if st.button(get_text("add_subscriber_btn"), key="bf_add_sub_btn"):
            if sub_name and sub_email:
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
                if add_subscriber(sub_name, sub_email, channels, schedule, selected_categories):
                    st.success(get_text("subscriber_added"))
                    st.rerun()
                else:
                    st.error(get_text("subscriber_add_failed"))
            else:
                st.warning(get_text("fill_fields"))

    subscribers = get_all_subscribers()
    if subscribers:
        with st.expander(get_text("manage_subscribers")):
            for sub in subscribers:
                col_info, col_status, col_delete = st.columns([4, 1, 1])
                with col_info:
                    st.write(f"**{sub['name']}**")
                    st.caption(sub['email'])
                with col_status:
                    status = "<span class='status-dot active'></span>" if sub.get("schedule", {}).get("enabled") else "<span class='status-dot error'></span>"
                    st.write(status, unsafe_allow_html=True)
                with col_delete:
                    if st.button(get_text("delete"), key=f"bf_del_sub_{sub['id']}"):
                        if remove_subscriber(sub['id']):
                            st.rerun()

                with st.container():
                    st.caption(get_text("view_details"))
                    channels = sub.get("channels", {})
                    active_channels = [k for k, v in channels.items() if isinstance(v, dict) and v.get("enabled")]
                    schedule = sub.get("schedule", {})
                    cats = sub.get("watch_categories", [])
                    st.markdown(
                        f"- {get_text('push_channels')}: {', '.join(active_channels) or '—'}\n"
                        f"- {get_text('schedule_settings')}: {schedule.get('time', '—')} ({schedule.get('timezone', '—')})\n"
                        f"- {get_text('watch_categories')}: {', '.join(cats) if cats else '—'}"
                    )
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
            get_all_categories, add_category, remove_category
        )
        CAT_AVAILABLE = True
    except ImportError:
        CAT_AVAILABLE = False

    if not CAT_AVAILABLE:
        st.markdown(f"<p class='bf-hint bf-hint--warn'>{get_text('module_unavailable')}</p>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        return

    cats = get_all_categories()

    # 新增关注点表单
    with st.expander(get_text("add_watch_category")):
        new_id = st.text_input(get_text("category_id"), key="bf_cat_new_id")
        new_name = st.text_input(get_text("category_name"), key="bf_cat_new_name")
        new_queries = st.text_area(
            get_text("category_queries"),
            placeholder=get_text("category_queries_ph"),
            key="bf_cat_new_queries"
        )
        if st.button(get_text("add_watch_category_btn"), key="bf_cat_add_btn"):
            if new_id and new_name and new_queries:
                cfg = {
                    "name": new_name,
                    "name_en": new_name,
                    "description": "",
                    "icon": "info",
                    "search_queries": [q.strip() for q in new_queries.splitlines() if q.strip()],
                    "enabled": True,
                }
                if add_category(new_id, cfg):
                    st.success(get_text("watch_category_added"))
                    st.rerun()
                else:
                    st.error(get_text("watch_category_failed"))
            else:
                st.warning(get_text("fill_fields"))

    # 现有关注点列表（可删除）
    if cats:
        with st.expander(get_text("manage_watch_categories")):
            for cid, cfg in cats.items():
                col_info, col_del = st.columns([5, 1])
                with col_info:
                    st.write(f"**{cfg.get('name', cid)}**")
                    st.caption(f"{cid} · {len(cfg.get('search_queries', []))} 条查询")
                with col_del:
                    if st.button(get_text("delete"), key=f"bf_del_cat_{cid}"):
                        if remove_category(cid):
                            st.success(get_text("watch_category_deleted"))
                            st.rerun()
    else:
        st.markdown(
            f"<p class='bf-hint'>{get_text('no_watch_categories')}</p>",
            unsafe_allow_html=True
        )

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
        ]
        tab_keys = ["sources", "subs", "watch", "analytics"]

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
    render_recommendations()

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
