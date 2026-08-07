import streamlit as st
from shared.logger import get_logger
from src.ui.i18n import get_text
from shared.llm.utils import get_model_choices

logger = get_logger(__name__)


def _render_model_settings():
    """模型选择 + 语言"""
    st.markdown("---")
    st.markdown(f'<div class="section-header">{get_text("settings")}</div>', unsafe_allow_html=True)

    model_options = get_model_choices()
    default_model = "qwen2.5:7b" if "qwen2.5:7b" in model_options else (model_options[0] if model_options else "gpt-4o")
    model_index = model_options.index(default_model) if default_model in model_options else 0

    model = st.selectbox(get_text("llm_model"), model_options, index=model_index)

    lang_options = {get_text("zh"): "zh", get_text("en"): "en"}
    selected_lang = st.selectbox(get_text("language"), list(lang_options.keys()),
                                  index=0 if st.session_state.lang == "zh" else 1,
                                  key="lang_selector")
    if lang_options.get(selected_lang) != st.session_state.lang:
        st.session_state.lang = lang_options[selected_lang]
        st.rerun()

    return model


def _render_data_sources():
    """数据源管理"""
    st.markdown("---")
    st.markdown(f'<div class="section-header">📡 {get_text("data_source_management")}</div>', unsafe_allow_html=True)

    try:
        from src.config.sources import get_all_sources, add_source, remove_source, toggle_source
        SOURCES_AVAILABLE = True
    except ImportError:
        SOURCES_AVAILABLE = False

    if not SOURCES_AVAILABLE:
        return

    with st.expander(get_text("add_data_source")):
        source_type = st.selectbox(
            get_text("source_type"),
            [get_text("source_type_rss"), get_text("source_type_web")],
            key="source_type_selector"
        )
        source_name = st.text_input(get_text("source_name"), key="source_name_input")
        source_url = st.text_input(get_text("source_url"), key="source_url_input")

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
            key="source_category_selector"
        )

        if st.button(get_text("add_source"), key="add_source_btn"):
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
                    enabled = st.toggle(get_text("enabled_label"), value=source.get("enabled", True), key=f"toggle_{source['id']}", label_visibility="collapsed")
                    if enabled != source.get("enabled", True):
                        toggle_source(source['id'], enabled)
                        st.rerun()
                with col_delete:
                    if st.button("🗑️", key=f"del_source_{source['id']}"):
                        if remove_source(source['id']):
                            st.rerun()
    else:
        st.info(get_text("no_sources"))


def _render_subscriptions():
    """订阅者管理"""
    st.markdown("---")
    st.markdown(f'<div class="section-header">📬 {get_text("subscription_management")}</div>', unsafe_allow_html=True)

    try:
        from src.config.subscriptions import get_all_subscribers, add_subscriber, remove_subscriber
        SUBSCRIPTION_AVAILABLE = True
    except ImportError:
        SUBSCRIPTION_AVAILABLE = False

    if not SUBSCRIPTION_AVAILABLE:
        return

    # SMTP 全局配置
    with st.expander(f"📧 {get_text('email_settings')}", expanded=False):
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
                key="smtp_server_input"
            )
            smtp_port = st.number_input(
                get_text("smtp_port"),
                value=email_config.get("smtp_port", 587),
                key="smtp_port_input"
            )
        with col_smtp2:
            smtp_username = st.text_input(
                get_text("smtp_username"),
                value=email_config.get("username", ""),
                key="smtp_username_input"
            )
            smtp_password = st.text_input(
                get_text("smtp_password"),
                value=email_config.get("password", ""),
                type="password",
                key="smtp_password_input"
            )
        smtp_use_tls = st.checkbox(
            get_text("smtp_use_tls"),
            value=email_config.get("use_tls", True),
            key="smtp_use_tls_input"
        )

        if st.button(get_text("save_email_settings"), key="save_email_btn"):
            st.session_state.email_config = {
                "smtp_server": smtp_server, "smtp_port": smtp_port,
                "username": smtp_username, "password": smtp_password,
                "use_tls": smtp_use_tls
            }
            st.success(get_text("email_settings_saved"))

    with st.expander(get_text("add_subscriber")):
        sub_name = st.text_input(get_text("subscriber_name"), key="sub_name_input")
        sub_email = st.text_input(get_text("subscriber_email"), key="sub_email_input")

        st.markdown(f"**{get_text('push_channels')}**")
        col_ch1, col_ch2, col_ch3 = st.columns(3)
        with col_ch1:
            email_enabled = st.checkbox(get_text("push_channel_email"), value=True, key="email_enabled")
        with col_ch2:
            wecom_enabled = st.checkbox(get_text("push_channel_wecom"), value=False, key="wecom_enabled")
        with col_ch3:
            dingtalk_enabled = st.checkbox(get_text("push_channel_dingtalk"), value=False, key="dingtalk_enabled")

        wecom_webhook = dingtalk_webhook = dingtalk_secret = ""
        if wecom_enabled:
            wecom_webhook = st.text_input(get_text("wecom_webhook"), key="wecom_webhook_input")
        if dingtalk_enabled:
            dingtalk_webhook = st.text_input(get_text("dingtalk_webhook"), key="dingtalk_webhook_input")
            dingtalk_secret = st.text_input(get_text("dingtalk_secret"), key="dingtalk_secret_input")

        st.markdown(f"**{get_text('schedule_settings')}**")
        col_time, col_tz = st.columns(2)
        with col_time:
            from datetime import datetime as dt
            push_time = st.time_input(get_text("push_time"), value=dt(2026, 1, 1, 8, 0), key="push_time")
        with col_tz:
            push_timezone = st.selectbox(
                get_text("push_timezone"),
                ["Asia/Shanghai", "America/New_York", "Europe/London", "Asia/Tokyo"],
                key="push_tz"
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
            key="push_days"
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
            if st.checkbox(cat_name, value=True, key=f"cat_{cat_id}"):
                selected_categories.append(cat_id)

        if st.button(get_text("add_subscriber_btn"), key="add_sub_btn"):
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
                    status = "✅" if sub.get("schedule", {}).get("enabled") else "❌"
                    st.write(status)
                with col_delete:
                    if st.button("🗑️", key=f"del_sub_{sub['id']}"):
                        if remove_subscriber(sub['id']):
                            st.rerun()

                with st.container():
                    st.caption(get_text("view_details"))
                    st.json(sub)
    else:
        st.info(get_text("no_subscribers"))


def _render_briefing_actions(model: str):
    """生成简报 + 下载格式"""
    st.markdown("---")
    st.markdown(f'<div class="section-header">🚀 {get_text("generate_briefing")}</div>', unsafe_allow_html=True)

    from src.ui.briefing_runner import render_briefing_generate_controls
    render_briefing_generate_controls(key_prefix="sb", model=model, compact=True)

    # 查看简报历史按钮
    st.markdown("---")
    if st.button(get_text("briefing_view_history"), key="view_history_btn", use_container_width=True):
        st.session_state.show_briefing_history = True
        st.rerun()


def render_sidebar():
    with st.sidebar:
        st.markdown(f'<div class="sidebar-title">{get_text("title")}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="sidebar-subtitle">{get_text("subtitle")}</div>', unsafe_allow_html=True)

        st.markdown("---")
        model = _render_model_settings()
        _render_data_sources()
        _render_subscriptions()
        _render_briefing_actions(model)

    return model
