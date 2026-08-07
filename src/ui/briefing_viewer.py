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
from src.config.briefing_history import get_briefing_history
from src.ui.i18n import get_text


def render_briefing_preview():
    """
    渲染简报预览区域

    守卫条件：st.session_state.current_briefing 存在且非空
    显示内容：简报 Markdown + 下载按钮
    """
    if not st.session_state.get("current_briefing"):
        return

    st.markdown(f'<div class="bf-output"><div class="bf-output__header">{get_text("briefing_preview")}</div>', unsafe_allow_html=True)
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
        st.info(get_text("briefing_history_empty"))
        st.markdown('</div>', unsafe_allow_html=True)
        return

    for entry in history:
        col1, col2, col3 = st.columns([4, 1, 1])
        with col1:
            date_str = entry.get("created_at", "")[:10]
            org = entry.get("organization", "")
            st.markdown(f"**{date_str}** — {org}")
        with col2:
            if st.button(get_text("view"), key=f"view_{entry.get('filename')}"):
                load_briefing_for_preview(
                    entry.get("filename"),
                    entry.get("html_filename")
                )
        with col3:
            if st.button(get_text("delete"), key=f"del_{entry.get('filename')}"):
                delete_briefing(entry.get("filename"))

    st.markdown('</div>', unsafe_allow_html=True)


def load_briefing_for_preview(filename: str, html_filename: str = None):
    """加载简报到预览区域"""
    content = get_briefing_history().load_briefing(filename)
    if content:
        st.session_state.current_briefing = content
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
        from src.config.sources import get_all_sources, add_source, remove_source, toggle_source
        SOURCES_AVAILABLE = True
    except ImportError:
        SOURCES_AVAILABLE = False

    if not SOURCES_AVAILABLE:
        st.warning(get_text("module_unavailable"))
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
        st.info(f"{get_text('no_sources')} —— {get_text('welcome_step_sources_desc')}")

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
        from src.config.subscriptions import get_all_subscribers, add_subscriber, remove_subscriber
        SUBSCRIPTION_AVAILABLE = True
    except ImportError:
        SUBSCRIPTION_AVAILABLE = False

    if not SUBSCRIPTION_AVAILABLE:
        st.warning(get_text("module_unavailable"))
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
        st.info(f"{get_text('no_subscribers')} —— {get_text('welcome_step_subscribers_desc')}")

    st.markdown('</div>', unsafe_allow_html=True)


def render_generate_panel():
    """生成简报操作面板（青蓝标签条 + 全宽主按钮）"""
    st.markdown(f'''
    <div class="bf-panel bf-panel--gen">
        <div class="bf-label">
            <span class="bf-label__tag">Generate</span>
            <span class="bf-label__title">{get_text("generate_briefing")}</span>
        </div>
        <div class="bf-generate-btn-wrapper">
    ''', unsafe_allow_html=True)

    from src.ui.briefing_runner import render_briefing_generate_controls
    render_briefing_generate_controls(key_prefix="bf", model=None, compact=False)

    st.markdown('</div></div>', unsafe_allow_html=True)


def _render_onboarding():
    """简报中心 3 步引导条（无 emoji、不嵌套 expander）

    用 session_state 中已有的数据源/订阅者配置进度标注当前到第几步。
    """
    try:
        from src.config.sources import get_all_sources
        from src.config.subscriptions import get_all_subscribers
        sources = get_all_sources()
        subs = get_all_subscribers()
    except ImportError:
        sources, subs = {}, []

    step1_done = bool(sources.get("subscription_sources") or sources.get("custom_sources"))
    step2_done = bool(subs)

    steps = [
        (get_text("welcome_step_sources"), get_text("welcome_step_sources_desc"), step1_done),
        (get_text("welcome_step_subscribers"), get_text("welcome_step_subscribers_desc"), step2_done),
        (get_text("welcome_step_generate"), get_text("welcome_step_generate_desc"), False),
    ]

    st.markdown(f'<p style="color: var(--wb-text-secondary); font-size: 14px; margin: 4px 0 12px 0;">{get_text("briefing_welcome_desc")}</p>', unsafe_allow_html=True)

    cols = st.columns(3)
    for i, (title, desc, done) in enumerate(steps):
        dot = '<span class="status-dot active"></span>' if done else '<span class="status-dot"></span>'
        label = f'<span style="opacity:.5;">{i + 1}.</span> {title}'
        with cols[i]:
            st.markdown(
                f'<div class="bf-step">'
                f'<div class="bf-step__head">{dot} {label}</div>'
                f'<div class="bf-step__desc">{desc}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )


def render_briefing_center():
    """
    Briefing Center 主渲染函数

    使用 workbench 风格的单栏垂直布局：
    - bf-workbench 容器包裹全部内容
    - 顶部 3 步引导条（数据源 → 订阅者 → 生成）
    - 三个功能面板（SOURCES / SUBSCRIBERS / GENERATE）各有彩色标签条
    - 结果输出区（OUTPUT）无标签条
    """
    st.markdown('<div class="bf-workbench">', unsafe_allow_html=True)

    # 标题
    st.markdown(f'<div class="main-title">{get_text("briefing_center")}</div>', unsafe_allow_html=True)

    # 引导条
    _render_onboarding()

    # 功能面板区
    render_data_sources_panel()
    render_subscriptions_panel()
    render_generate_panel()

    # 输出区
    render_briefing_preview()
    render_briefing_history()

    st.markdown('</div>', unsafe_allow_html=True)
