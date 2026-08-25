import streamlit as st
import base64
import json
import os
from intelnexus.core.logger import get_logger
from intelnexus.ui.i18n import get_text
from intelnexus.ui.icons import icon
from intelnexus.core.ui.helpers import SEARCH_MODES, DEFAULT_TOR_PORT, check_tor_status
from intelnexus.core.llm.utils import get_model_choices, is_vision_model
from intelnexus.core.llm.models import (
    add_custom_model, get_custom_model_names, remove_custom_model,
    get_custom_models, get_model_config, update_custom_model, test_model_connection,
)
from intelnexus.search_app.darkweb import is_available as darkweb_available

logger = get_logger(__name__)


def _render_search_mode():
    """搜索模式选择 + 暗网设置"""
    st.markdown('<div class="sb-section"><span class="sb-section__label">Search Mode</span></div>', unsafe_allow_html=True)

    # 方案一（智能路由）：「智能」置顶为默认——按查询主题自动路由，
    # 手动 5 模式收进高级折叠区供精确控制；暗网仅在 Tor 存活时出现在手动列表。
    from intelnexus.core.search.modes import SMART_MODE_KEY

    manual_modes = list(SEARCH_MODES.keys())
    if not darkweb_available():
        manual_modes.remove("darkweb")  # Tor 未运行时隐藏死选项

    top = st.radio(
        "mode_top",
        [SMART_MODE_KEY, "manual"],
        format_func=lambda x: ("🎯 " + get_text("mode_smart")) if x == SMART_MODE_KEY else get_text("mode_manual"),
        label_visibility="collapsed",
        index=0,
    )

    search_mode = SMART_MODE_KEY
    tor_port_used = DEFAULT_TOR_PORT
    if top == "manual":
        with st.expander(get_text("mode_manual"), expanded=True):
            search_mode = st.radio(
                "mode",
                manual_modes,
                format_func=lambda x: get_text(SEARCH_MODES[x][0]),
                label_visibility="collapsed",
                index=0,
            )
            if search_mode == "darkweb":
                tor_port_used = _render_darkweb_settings()
    elif not darkweb_available():
        st.caption(get_text("smart_hint_no_tor"))
    if top == "manual":
        with st.expander(get_text("mode_manual"), expanded=True):
            search_mode = st.radio(
                "mode",
                manual_modes,
                format_func=lambda x: get_text(SEARCH_MODES[x][0]),
                label_visibility="collapsed",
                index=0,
            )
            if search_mode == "darkweb":
                _render_darkweb_settings()
    elif not darkweb_available():
        st.caption(get_text("smart_hint_no_tor"))
    return search_mode

def _render_darkweb_settings():
    """暗网模式设置面板（Tor 端口/高级选项/自定义 onion 源）。返回所选 Tor 端口。"""
    with st.expander(get_text('darkweb_settings'), expanded=True):
        tor_port = st.number_input(
            get_text("tor_port"),
            min_value=1,
            max_value=65535,
            value=st.session_state.get("tor_port", DEFAULT_TOR_PORT),
            key="tor_port"
        )

        tor_running = check_tor_status(tor_port)
        if tor_running:
            st.markdown(f"<span class='status-dot active'></span>{get_text('tor_running')}", unsafe_allow_html=True)
        else:
            st.markdown(f"<span class='status-dot error'></span>{get_text('tor_not_running')}", unsafe_allow_html=True)

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
            st.warning(f"{get_text('tor_not_running')} - {get_text('default_mode')}")

        st.markdown('<hr class="sb-divider">', unsafe_allow_html=True)
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
                    st.success(f"OK — {get_text('site_saved')}")
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
                    auth_info = " (auth)" if site.get("auth") else ""
                    st.markdown(f"- {site.get('name', 'Unknown')}{auth_info}")
                with col_del:
                    if st.button(get_text("delete"), key=f"del_site_{i}"):
                        st.session_state.custom_onion_sites.pop(i)
                        try:
                            with open("data/custom_onion_sites.json", "w", encoding="utf-8") as f:
                                json.dump(st.session_state.custom_onion_sites, f, ensure_ascii=False, indent=2)
                        except Exception:
                            pass
                        st.rerun()
        else:
            st.markdown(f"_{get_text('no_sites')}_")

    return int(st.session_state.get("tor_port", DEFAULT_TOR_PORT))