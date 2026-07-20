import streamlit as st
import base64
import json
import os
from shared.logger import get_logger
from src.ui.i18n import get_text
from shared.ui.helpers import SEARCH_MODES, DEFAULT_TOR_PORT, check_tor_status
from shared.llm.utils import get_model_choices
from shared.llm.models import add_custom_model, get_custom_model_names, remove_custom_model
from src.search.darkweb import is_available as darkweb_available

logger = get_logger(__name__)


def _render_search_mode():
    """搜索模式选择 + 暗网设置"""
    st.markdown(f'<div class="section-header">{get_text("search_mode")}</div>', unsafe_allow_html=True)

    mode_options = list(SEARCH_MODES.keys())
    search_mode = st.radio(
        "mode",
        mode_options,
        format_func=lambda x: get_text(SEARCH_MODES[x][0]),
        label_visibility="collapsed",
        index=0
    )

    if search_mode == "darkweb" and not darkweb_available():
        st.warning(get_text("darkweb_warning"))

    if search_mode == "darkweb":
        st.markdown("---")
        with st.expander(f"🧅 {get_text('darkweb_settings')}", expanded=True):
            tor_port = st.number_input(
                get_text("tor_port"),
                min_value=1,
                max_value=65535,
                value=st.session_state.get("tor_port", DEFAULT_TOR_PORT),
                key="tor_port"
            )

            tor_running = check_tor_status(tor_port)
            if tor_running:
                st.success(f"🟢 {get_text('tor_running')}")
            else:
                st.error(f"🔴 {get_text('tor_not_running')}")

            col_tor1, col_tor2 = st.columns([1, 1])
            with col_tor1:
                if st.button(get_text("detect_tor"), key="detect_tor_btn"):
                    st.rerun()

            advanced_mode = st.checkbox(
                get_text("advanced_mode"),
                value=st.session_state.get("advanced_mode", False),
                help=get_text("advanced_mode_desc"),
                key="advanced_mode"
            )

            if not tor_running and advanced_mode:
                st.warning(f"⚠️ {get_text('tor_not_running')} - {get_text('default_mode')}")

            st.markdown("---")
            st.markdown(f"**{get_text('custom_onion_sites')}**")

            if "custom_onion_sites" not in st.session_state:
                st.session_state.custom_onion_sites = []

            with st.container():
                st.markdown(f"**{get_text('add_site')}**")
                col_site1, col_site2 = st.columns(2)
                with col_site1:
                    new_site_name = st.text_input(get_text("site_name"), key="new_site_name", placeholder="My Site")
                    new_site_url = st.text_input(get_text("site_url"), key="new_site_url", placeholder="http://xxx.onion/search?q=")
                with col_site2:
                    new_site_auth = st.checkbox(get_text("site_need_auth"), key="new_site_auth")
                    new_site_user = ""
                    new_site_pass = ""
                    if new_site_auth:
                        new_site_user = st.text_input(get_text("breached_username"), key="new_site_user")
                        new_site_pass = st.text_input(get_text("breached_password"), type="password", key="new_site_pass")

                if st.button(get_text("add_site"), key="add_site_btn"):
                    if new_site_name and new_site_url:
                        new_site = {"name": new_site_name, "url": new_site_url}
                        if new_site_auth and new_site_user and new_site_pass:
                            encoded_pass = base64.b64encode(new_site_pass.encode("utf-8")).decode("utf-8")
                            new_site["auth"] = {"type": "basic", "username": new_site_user, "password": encoded_pass}
                        st.session_state.custom_onion_sites.append(new_site)
                        try:
                            os.makedirs("data", exist_ok=True)
                            with open("data/custom_onion_sites.json", "w", encoding="utf-8") as f:
                                json.dump(st.session_state.custom_onion_sites, f, ensure_ascii=False, indent=2)
                        except Exception as e:
                            logger.error(f"{get_text('briefing_save_site_failed')}: {e}")
                        st.success(f"✓ {get_text('site_saved')}")
                        st.rerun()

            try:
                sites_file = "data/custom_onion_sites.json"
                if os.path.exists(sites_file):
                    with open(sites_file, "r", encoding="utf-8") as f:
                        loaded_sites = json.load(f)
                        if loaded_sites and not st.session_state.custom_onion_sites:
                            st.session_state.custom_onion_sites = loaded_sites
            except Exception:
                pass

            if st.session_state.custom_onion_sites:
                st.markdown(f"**{get_text('added_sites')}**")
                for i, site in enumerate(st.session_state.custom_onion_sites):
                    col_site, col_del = st.columns([4, 1])
                    with col_site:
                        auth_info = " 🔒" if site.get("auth") else ""
                        st.markdown(f"- {site.get('name', 'Unknown')}{auth_info}")
                    with col_del:
                        if st.button("🗑️", key=f"del_site_{i}"):
                            st.session_state.custom_onion_sites.pop(i)
                            try:
                                with open("data/custom_onion_sites.json", "w", encoding="utf-8") as f:
                                    json.dump(st.session_state.custom_onion_sites, f, ensure_ascii=False, indent=2)
                            except Exception:
                                pass
                            st.rerun()
            else:
                st.markdown(f"_{get_text('no_sites')}_")

    return search_mode


def _render_model_settings():
    """模型选择 + 线程数 + 语言"""
    st.markdown("---")
    st.markdown(f'<div class="section-header">{get_text("settings")}</div>', unsafe_allow_html=True)

    model_options = get_model_choices()
    default_model = "qwen2.5:7b" if "qwen2.5:7b" in model_options else (model_options[0] if model_options else "gpt-4o")
    model_index = model_options.index(default_model) if default_model in model_options else 0

    model = st.selectbox(get_text("llm_model"), model_options, index=model_index)
    threads = st.slider(get_text("threads"), 1, 16, 5)

    lang_options = {get_text("zh"): "zh", get_text("en"): "en"}
    selected_lang = st.selectbox(get_text("language"), list(lang_options.keys()),
                                  index=0 if st.session_state.lang == "zh" else 1,
                                  key="lang_selector")
    if lang_options.get(selected_lang) != st.session_state.lang:
        st.session_state.lang = lang_options[selected_lang]
        st.rerun()

    return model, threads


def _render_custom_models():
    """自定义模型管理"""
    st.markdown("---")
    with st.expander(get_text("add_custom_model"), expanded=False):
        col_name, col_type = st.columns(2)
        with col_name:
            custom_model_name = st.text_input(get_text("model_name"), key="custom_model_name")
        with col_type:
            model_type = st.selectbox(
                get_text("model_type"),
                ["OpenAI", "Azure OpenAI", "Anthropic", "Google", "Cohere",
                 "Mistral", "DeepSeek", "Ollama", get_text("model_type_qwen"), get_text("model_type_zhipu"),
                 get_text("model_type_baidu"), get_text("model_type_xunfei"), "Moonshot", "01.AI"],
                key="model_type_selector"
            )

        base_url = api_key = model_id = None
        if model_type == "OpenAI":
            base_url = st.text_input(get_text("base_url"))
            api_key = st.text_input(get_text("api_key"), type="password", key="openai_api_key")
            model_id = st.text_input(get_text("model_id"))
        elif model_type == "Anthropic":
            api_key = st.text_input(get_text("api_key"), type="password", key="anthropic_api_key")
            model_id = st.text_input(get_text("model_id"))
        elif model_type in ["Google", "Cohere", "Mistral", "DeepSeek", get_text("model_type_qwen"), get_text("model_type_zhipu"), get_text("model_type_baidu"), get_text("model_type_xunfei"), "Moonshot", "01.AI"]:
            api_key = st.text_input(get_text("api_key"), type="password", key=f"{model_type.lower()}_api_key")
            base_url = st.text_input(get_text("base_url"), key=f"{model_type.lower()}_base_url")
            model_id = st.text_input(get_text("model_id"))
        else:
            base_url = st.text_input(get_text("ollama_base_url"), value="http://127.0.0.1:11434", key="ollama_base_url")
            model_id = st.text_input(get_text("model_name"))

        if st.button(get_text("add_model")):
            if custom_model_name and model_id:
                config = {"model_name": model_id}
                if model_type in ["OpenAI", "Azure OpenAI"]:
                    if base_url:
                        config["base_url"] = base_url
                    if api_key:
                        config["api_key"] = api_key
                elif model_type == "Anthropic":
                    if api_key:
                        config["api_key"] = api_key
                elif model_type in ["Google", "Cohere", "Mistral", "DeepSeek", get_text("model_type_qwen"), get_text("model_type_zhipu"), get_text("model_type_baidu"), get_text("model_type_xunfei"), "Moonshot", "01.AI"]:
                    if api_key:
                        config["api_key"] = api_key
                    if base_url:
                        config["base_url"] = base_url
                else:
                    config["base_url"] = base_url

                if add_custom_model(custom_model_name, model_type.lower(), config):
                    st.success(get_text("model_add_success"))
                    st.rerun()
                else:
                    st.error(get_text("model_exists"))
            else:
                st.error(get_text("fill_fields"))

        custom_models = get_custom_model_names()
        if custom_models:
            st.markdown(f"**{get_text('custom_models_list')}**")
            for custom_model in custom_models:
                col_model, col_delete = st.columns([3, 1])
                with col_model:
                    st.write(custom_model)
                with col_delete:
                    if st.button(get_text("delete"), key=f"delete_{custom_model}"):
                        if remove_custom_model(custom_model):
                            st.success(get_text("deleted"))
                            st.rerun()


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

                with st.expander(get_text("view_details"), key=f"details_{sub['id']}"):
                    st.json(sub)
    else:
        st.info(get_text("no_subscribers"))


def _render_briefing_actions():
    """生成简报 + 下载格式"""
    st.markdown("---")
    st.markdown(f'<div class="section-header">🚀 {get_text("generate_briefing")}</div>', unsafe_allow_html=True)

    if st.button(get_text("generate_briefing"), key="generate_briefing_btn", use_container_width=True):
        from ai_briefing.collector import AIBriefingCollector
        from ai_briefing.analyzer import AIBriefingAnalyzer
        from ai_briefing.notifier import AIBriefingNotifier
        from src.config.subscriptions import get_active_subscribers

        with st.spinner(get_text("briefing_generating")):
            try:
                collector = AIBriefingCollector()
                collected = {}
                for cat in ["ai_gov_usage", "ai_china_narrative", "ai_legislation", "ai_data_leak"]:
                    collected[cat] = collector.collect_for_category(cat)

                analyzer = AIBriefingAnalyzer()
                briefing_md = analyzer.generate_briefing(collected)

                # 保存简报到历史
                from src.config.briefing_history import get_briefing_history
                get_briefing_history().save_briefing(
                    markdown_content=briefing_md,
                    organization_name=get_text("default_org_name"),
                    categories=["ai_gov_usage", "ai_china_narrative", "ai_legislation", "ai_data_leak"]
                )

                email_config = st.session_state.get("email_config", {
                    "smtp_server": "", "smtp_port": 587,
                    "username": "", "password": "", "use_tls": True
                })
                notifier = AIBriefingNotifier(email_config=email_config)
                subscribers = get_active_subscribers()

                if not subscribers:
                    st.warning(get_text("briefing_no_subscribers"))
                else:
                    success_count = 0
                    for sub in subscribers:
                        results = notifier.notify(sub, briefing_md)
                        if any(results.values()):
                            success_count += 1
                    st.success(get_text("briefing_success").format(count=f"{success_count}/{len(subscribers)}"))

                # 存入 session_state 用于预览
                st.session_state.current_briefing = briefing_md
            except Exception as e:
                st.error(f"{get_text('briefing_failed')}: {str(e)}")

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
        search_mode = _render_search_mode()
        model, threads = _render_model_settings()
        _render_custom_models()
        _render_data_sources()
        _render_subscriptions()
        _render_briefing_actions()

    return search_mode, model, threads
