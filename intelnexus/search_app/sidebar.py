import streamlit as st
import base64
import json
import os
from intelnexus.core.logger import get_logger
from intelnexus.ui.i18n import get_text
from intelnexus.core.ui.helpers import SEARCH_MODES, DEFAULT_TOR_PORT, check_tor_status
from intelnexus.core.llm.utils import get_model_choices
from intelnexus.core.llm.models import add_custom_model, get_custom_model_names, remove_custom_model
from intelnexus.search_app.darkweb import is_available as darkweb_available

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
                            logger.error(f"Failed to save site: {e}")
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


def render_sidebar():
    with st.sidebar:
        st.markdown(f'<div class="sidebar-title">{get_text("title")}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="sidebar-subtitle">{get_text("subtitle")}</div>', unsafe_allow_html=True)

        st.markdown("---")
        search_mode = _render_search_mode()
        model, threads = _render_model_settings()
        _render_custom_models()

    return search_mode, model, threads
