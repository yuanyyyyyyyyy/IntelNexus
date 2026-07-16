import streamlit as st
from src.ui.i18n import get_text
from src.ui.helpers import SEARCH_MODES, BREACHED_URL, DEFAULT_TOR_PORT, check_tor_status, get_tor_port
from src.llm.utils import get_model_choices
from src.llm.models import add_custom_model, get_custom_model_names, remove_custom_model
from src.search.darkweb import is_available as darkweb_available


def render_sidebar():
    with st.sidebar:
        st.markdown(f'<div class="sidebar-title">{get_text("title")}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="sidebar-subtitle">{get_text("subtitle")}</div>', unsafe_allow_html=True)
        
        st.markdown("---")
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
        
        # 暗网设置区域
        if search_mode == "darkweb":
            st.markdown("---")
            with st.expander(f"🧅 {get_text('darkweb_settings')}", expanded=True):
                # Tor状态检测
                tor_port = st.number_input(
                    get_text("tor_port"),
                    min_value=1,
                    max_value=65535,
                    value=st.session_state.get("tor_port", DEFAULT_TOR_PORT),
                    key="tor_port"
                )
                
                # 检测Tor状态
                tor_running = check_tor_status(tor_port)
                if tor_running:
                    st.success(f"🟢 {get_text('tor_running')}")
                else:
                    st.error(f"🔴 {get_text('tor_not_running')}")
                
                col_tor1, col_tor2 = st.columns([1, 1])
                with col_tor1:
                    if st.button(get_text("detect_tor"), key="detect_tor_btn"):
                        st.rerun()
                
                # 高级模式选项
                advanced_mode = st.checkbox(
                    get_text("advanced_mode"),
                    value=st.session_state.get("advanced_mode", False),
                    help=get_text("advanced_mode_desc"),
                    key="advanced_mode"
                )
                
                if not tor_running and advanced_mode:
                    st.warning(f"⚠️ {get_text('tor_not_running')} - {get_text('default_mode')}")
                
                # Breached论坛配置
                st.markdown("---")
                st.markdown(f"**{get_text('breached_forum')}**")
                
                # 注册链接 + 提示
                st.markdown(f"""
                <a href="{BREACHED_URL}" target="_blank" style="text-decoration: none;">
                    <span style="color: #4A90D9;">🔗 {get_text('breached_register')}</span>
                </a>
                <br><br>
                <span style="color: #6B7280; font-size: 0.9em;">{get_text('breached_hint')}</span>
                """, unsafe_allow_html=True)
                
                col_breach1, col_breach2 = st.columns(2)
                with col_breach1:
                    breached_user = st.text_input(
                        get_text("breached_username"),
                        value=st.session_state.get("breached_username", ""),
                        key="breached_user"
                    )
                with col_breach2:
                    breached_pass = st.text_input(
                        get_text("breached_password"),
                        value=st.session_state.get("breached_password", ""),
                        type="password",
                        key="breached_pass"
                    )
                
                if breached_user and breached_pass:
                    st.session_state.breached_username = breached_user
                    st.session_state.breached_password = breached_pass
                    st.success(f"✓ {get_text('breached_saved')}")
                
                # 自定义暗网站点配置
                st.markdown("---")
                st.markdown(f"**{get_text('custom_onion_sites')}**")
                
                # 初始化自定义站点列表
                if "custom_onion_sites" not in st.session_state:
                    st.session_state.custom_onion_sites = []
                
                # 添加新站点表单（使用container代替expander避免嵌套）
                with st.container():
                    st.markdown(f"**{get_text('add_site')}**")
                    col_site1, col_site2 = st.columns(2)
                    with col_site1:
                        new_site_name = st.text_input(
                            get_text("site_name"),
                            key="new_site_name",
                            placeholder="My Site"
                        )
                        new_site_url = st.text_input(
                            get_text("site_url"),
                            key="new_site_url",
                            placeholder="http://xxx.onion/search?q="
                        )
                    with col_site2:
                        new_site_auth = st.checkbox(
                            get_text("site_need_auth"),
                            key="new_site_auth"
                        )
                        new_site_user = ""
                        new_site_pass = ""
                        if new_site_auth:
                            new_site_user = st.text_input(
                                get_text("breached_username"),
                                key="new_site_user"
                            )
                            new_site_pass = st.text_input(
                                get_text("breached_password"),
                                type="password",
                                key="new_site_pass"
                            )
                    
                    if st.button(get_text("add_site"), key="add_site_btn"):
                        if new_site_name and new_site_url:
                            new_site = {
                                "name": new_site_name,
                                "url": new_site_url,
                            }
                            if new_site_auth and new_site_user and new_site_pass:
                                new_site["auth"] = {
                                    "type": "basic",
                                    "username": new_site_user,
                                    "password": new_site_pass
                                }
                            # 保存到session
                            st.session_state.custom_onion_sites.append(new_site)
                            # 持久化保存到文件
                            try:
                                import json
                                import os
                                os.makedirs("data", exist_ok=True)
                                sites_file = "data/custom_onion_sites.json"
                                with open(sites_file, "w", encoding="utf-8") as f:
                                    json.dump(st.session_state.custom_onion_sites, f, ensure_ascii=False, indent=2)
                            except Exception as e:
                                print(f"保存站点失败: {e}")
                            st.success(f"✓ {get_text('site_saved')}")
                            st.rerun()
                
                # 显示已添加的站点
                # 尝试从文件加载站点
                try:
                    import json
                    import os
                    sites_file = "data/custom_onion_sites.json"
                    if os.path.exists(sites_file):
                        with open(sites_file, "r", encoding="utf-8") as f:
                            loaded_sites = json.load(f)
                            if loaded_sites and not st.session_state.custom_onion_sites:
                                st.session_state.custom_onion_sites = loaded_sites
                except:
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
                                # 更新文件
                                try:
                                    import json
                                    import os
                                    sites_file = "data/custom_onion_sites.json"
                                    with open(sites_file, "w", encoding="utf-8") as f:
                                        json.dump(st.session_state.custom_onion_sites, f, ensure_ascii=False, indent=2)
                                except:
                                    pass
                                st.rerun()
                else:
                    st.markdown(f"_{get_text('no_sites')}_")

        st.markdown("---")
        st.markdown(f'<div class="section-header">{get_text("settings")}</div>', unsafe_allow_html=True)

        model_options = get_model_choices()
        default_model = "qwen2.5:7b" if "qwen2.5:7b" in model_options else (model_options[0] if model_options else "gpt-4o")
        model_index = model_options.index(default_model) if default_model in model_options else 0

        model = st.selectbox(get_text("llm_model"), model_options, index=model_index)
        threads = st.slider(get_text("threads"), 1, 16, 5)
        
        # 语言切换 - 在设置中
        lang_options = {get_text("zh"): "zh", get_text("en"): "en"}
        current_lang_display = get_text("zh") if st.session_state.lang == "zh" else get_text("en")
        selected_lang = st.selectbox(get_text("language"), list(lang_options.keys()), 
                                      index=0 if st.session_state.lang == "zh" else 1, 
                                      key="lang_selector")
        if lang_options.get(selected_lang) != st.session_state.lang:
            st.session_state.lang = lang_options[selected_lang]
            st.rerun()
        
        # 自定义模型管理
        st.markdown("---")
        with st.expander(get_text("add_custom_model")):
            col_name, col_type = st.columns(2)
            with col_name:
                custom_model_name = st.text_input(
                    get_text("model_name"),
                    key="custom_model_name"
                )
            with col_type:
                model_type = st.selectbox(
                    get_text("model_type"),
                    [
                        "OpenAI", "Azure OpenAI", "Anthropic", "Google", "Cohere", 
                        "Mistral", "DeepSeek", "Ollama", "通义千问", "智谱AI", 
                        "百度文心一言", "讯飞星火", "Moonshot", "01.AI"
                    ],
                    key="model_type_selector"
                )
            
            if model_type == "OpenAI":
                base_url = st.text_input(get_text("base_url"))
                api_key = st.text_input(get_text("api_key"), type="password", key="openai_api_key")
                model_id = st.text_input(get_text("model_id"))
            elif model_type == "Anthropic":
                api_key = st.text_input(get_text("api_key"), type="password", key="anthropic_api_key")
                model_id = st.text_input(get_text("model_id"))
            elif model_type in ["Google", "Cohere", "Mistral", "DeepSeek", "通义千问", "智谱AI", "百度文心一言", "讯飞星火", "Moonshot", "01.AI"]:
                api_key = st.text_input(get_text("api_key"), type="password", key=f"{model_type.lower()}_api_key")
                base_url = st.text_input(get_text("base_url"), key=f"{model_type.lower()}_base_url")
                model_id = st.text_input(get_text("model_id"))
            else:  # Ollama
                base_url = st.text_input(get_text("ollama_base_url"), value="http://127.0.0.1:11434", key="ollama_base_url")
                api_key = None
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
                elif model_type in ["Google", "Cohere", "Mistral", "DeepSeek", "通义千问", "智谱AI", "百度文心一言", "讯飞星火", "Moonshot", "01.AI"]:
                    if api_key:
                        config["api_key"] = api_key
                    if base_url:
                        config["base_url"] = base_url
                else:  # Ollama
                    config["base_url"] = base_url
                
                if add_custom_model(custom_model_name, model_type.lower(), config):
                    st.success(get_text("model_add_success"))
                    st.rerun()
                else:
                    st.error(get_text("model_exists"))
            else:
                st.error(get_text("fill_fields"))
        
        # 显示已添加的自定义模型
        custom_models = get_custom_model_names()
        if custom_models:
            with st.expander(get_text("custom_models_list")):
                for custom_model in custom_models:
                    col_model, col_delete = st.columns([3, 1])
                    with col_model:
                        st.write(custom_model)
                    with col_delete:
                        if st.button(get_text("delete"), key=f"delete_{custom_model}"):
                            if remove_custom_model(custom_model):
                                st.success(get_text("deleted"))
                                st.rerun()

        # AI简报 - 数据源管理
        st.markdown("---")
        st.markdown(f'<div class="section-header">📡 {get_text("data_source_management")}</div>', unsafe_allow_html=True)
        
        # 导入数据源配置函数
        try:
            from src.config.sources import get_all_sources, add_source, remove_source, toggle_source
            SOURCES_AVAILABLE = True
        except ImportError:
            SOURCES_AVAILABLE = False
        
        if SOURCES_AVAILABLE:
            # 添加数据源表单
            with st.expander(get_text("add_data_source")):
                source_type = st.selectbox(
                    get_text("source_type"),
                    [get_text("source_type_rss"), get_text("source_type_web")],
                    key="source_type_selector"
                )
                
                source_name = st.text_input(get_text("source_name"), key="source_name_input")
                source_url = st.text_input(get_text("source_url"), key="source_url_input")
                
                # 关注点类别
                categories = {
                    "ai_gov_usage": "🏛️ 美欧机构AI应用",
                    "ai_china_narrative": "🇨🇳 涉我AI舆论",
                    "ai_legislation": "📜 AI新法案",
                    "ai_data_leak": "🔒 AI数据泄露"
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
            
            # 显示数据源列表
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
                            enabled = st.toggle(
                                "",
                                value=source.get("enabled", True),
                                key=f"toggle_{source['id']}"
                            )
                            if enabled != source.get("enabled", True):
                                toggle_source(source['id'], enabled)
                                st.rerun()
                        with col_delete:
                            if st.button("🗑️", key=f"del_source_{source['id']}"):
                                if remove_source(source['id']):
                                    st.rerun()
            else:
                st.info(get_text("no_sources"))

        # AI简报 - 订阅管理
        st.markdown("---")
        st.markdown(f'<div class="section-header">📬 {get_text("subscription_management")}</div>', unsafe_allow_html=True)
        
        # 导入订阅配置函数
        try:
            from src.config.subscriptions import get_all_subscribers, add_subscriber, remove_subscriber
            SUBSCRIPTION_AVAILABLE = True
        except ImportError:
            SUBSCRIPTION_AVAILABLE = False
        
        if SUBSCRIPTION_AVAILABLE:
            # 添加订阅者表单
            with st.expander(get_text("add_subscriber")):
                sub_name = st.text_input(get_text("subscriber_name"), key="sub_name_input")
                sub_email = st.text_input(get_text("subscriber_email"), key="sub_email_input")
                
                # 推送渠道
                st.markdown(f"**{get_text('push_channels')}**")
                col_ch1, col_ch2, col_ch3 = st.columns(3)
                with col_ch1:
                    email_enabled = st.checkbox(get_text("push_channel_email"), value=True, key="email_enabled")
                with col_ch2:
                    wecom_enabled = st.checkbox(get_text("push_channel_wecom"), value=False, key="wecom_enabled")
                with col_ch3:
                    dingtalk_enabled = st.checkbox(get_text("push_channel_dingtalk"), value=False, key="dingtalk_enabled")
                
                if wecom_enabled:
                    wecom_webhook = st.text_input(get_text("wecom_webhook"), key="wecom_webhook_input")
                if dingtalk_enabled:
                    dingtalk_webhook = st.text_input(get_text("dingtalk_webhook"), key="dingtalk_webhook_input")
                    dingtalk_secret = st.text_input(get_text("dingtalk_secret"), key="dingtalk_secret_input")
                
                # 定时设置
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
                
                # 推送日期
                day_options = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
                day_labels = [
                    get_text("push_days_mon"),
                    get_text("push_days_tue"),
                    get_text("push_days_wed"),
                    get_text("push_days_thu"),
                    get_text("push_days_fri"),
                    get_text("push_days_sat"),
                    get_text("push_days_sun")
                ]
                push_days = st.multiselect(
                    get_text("push_days"),
                    day_options,
                    default=["mon", "tue", "wed", "thu", "fri"],
                    format_func=lambda x: day_labels[day_options.index(x)],
                    key="push_days"
                )
                
                # 关注类别
                st.markdown(f"**{get_text('watch_categories')}**")
                categories = {
                    "ai_gov_usage": "🏛️ 美欧机构AI应用",
                    "ai_china_narrative": "🇨🇳 涉我AI舆论",
                    "ai_legislation": "📜 AI新法案",
                    "ai_data_leak": "🔒 AI数据泄露"
                }
                selected_categories = []
                for cat_id, cat_name in categories.items():
                    if st.checkbox(cat_name, value=True, key=f"cat_{cat_id}"):
                        selected_categories.append(cat_id)
                
                if st.button(get_text("add_subscriber_btn"), key="add_sub_btn"):
                    if sub_name and sub_email:
                        channels = {
                            "email": {"enabled": email_enabled, "address": sub_email},
                            "wecom": {"enabled": wecom_enabled, "webhook": wecom_webhook if wecom_enabled else ""},
                            "dingtalk": {"enabled": dingtalk_enabled, "webhook": dingtalk_webhook if dingtalk_enabled else "", "secret": dingtalk_secret if dingtalk_enabled else ""}
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
            
            # 显示订阅者列表
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
                        
                        # 显示配置详情
                        with st.expander(get_text("view_details"), key=f"details_{sub['id']}"):
                            st.json(sub)
            else:
                st.info(get_text("no_subscribers"))

        # AI简报 - 邮件设置
        st.markdown("---")
        st.markdown(f'<div class="section-header">📧 {get_text("email_settings")}</div>', unsafe_allow_html=True)
        
        with st.expander(get_text("email_settings")):
            # 初始化邮件配置
            if "email_config" not in st.session_state:
                st.session_state.email_config = {
                    "smtp_server": "",
                    "smtp_port": 587,
                    "username": "",
                    "password": "",
                    "use_tls": True
                }
            
            email_config = st.session_state.email_config
            
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
                    "smtp_server": smtp_server,
                    "smtp_port": smtp_port,
                    "username": smtp_username,
                    "password": smtp_password,
                    "use_tls": smtp_use_tls
                }
                st.success(get_text("email_settings_saved"))

        st.markdown("---")
        st.markdown(f'<div class="section-header">{get_text("download_format")}</div>', unsafe_allow_html=True)
        
        # 初始化下载格式
        if "sidebar_download_format" not in st.session_state:
            st.session_state.sidebar_download_format = "md"
        
        # 初始化下载状态（用于解决页面消失问题）
        if "download_ready" not in st.session_state:
            st.session_state.download_ready = False
        if "download_data" not in st.session_state:
            st.session_state.download_data = None
        if "download_filename" not in st.session_state:
            st.session_state.download_filename = None
        if "download_mime" not in st.session_state:
            st.session_state.download_mime = None
        
        format_options = ["md", "pdf", "docx", "xlsx"]
        format_labels = {
            "md": "Markdown",
            "pdf": "PDF",
            "docx": "Word",
            "xlsx": "Excel"
        }
        
        sidebar_format = st.selectbox(
            "选择下载格式",
            format_options,
            format_func=lambda x: format_labels[x],
            label_visibility="collapsed",
            key="sidebar_format_select"
        )
        st.session_state.sidebar_download_format = sidebar_format
        
        st.markdown("---")
        st.markdown(f'<div class="section-header">{get_text("sources")}</div>', unsafe_allow_html=True)
        st.caption("Semantic Scholar, RSS, Reddit, Bing")

    return search_mode, model, threads
