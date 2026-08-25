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
    from intelnexus.ui.icons import icon as _icon
    st.markdown(f'<div class="sb-section"><span class="sb-section__label">{_icon("investigate", "sm", "blue")} Search Mode · 智能路由优先</span></div>', unsafe_allow_html=True)

    # 方案一（智能路由）：「智能」置顶为默认——按查询主题自动路由，
    # 手动 5 模式收进高级折叠区供精确控制；暗网仅在 Tor 存活时出现在手动列表。
    from intelnexus.core.search.modes import SMART_MODE_KEY, SMART_GENERAL_KEY

    # 手动列表只暴露用户可选的 5 模式；smart/smart_general 是路由内部值
    manual_modes = [m for m in SEARCH_MODES.keys() if m != SMART_GENERAL_KEY]
    if not darkweb_available():
        manual_modes.remove("darkweb")  # Tor 未运行时隐藏死选项

    top = st.radio(
        "mode_top",
        [SMART_MODE_KEY, "manual"],
        format_func=lambda x: get_text("mode_smart") if x == SMART_MODE_KEY else get_text("mode_manual"),
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
                if not darkweb_available():
                    st.error(get_text("darkweb_tor_offline_hint"))
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

def _render_source_health():
    """数据源健康状态面板"""
    try:
        from intelnexus.core.search.health import get_all_health, save_health, purge_stale_entries
        from intelnexus.core.search.registry import get_registry
        from intelnexus.config.search_settings import get_news_api_key as NEWS_API_KEY
        active_names = [s.name for s in get_registry(
            news_api_key=NEWS_API_KEY()).all_sources()]
        purge_stale_entries(active_names)  # 清掉测试残留/已删源的僵尸条目
        all_health = get_all_health()
    except Exception:
        return

    with st.expander(get_text("source_health"), expanded=False):
        if not all_health:
            st.markdown(f"_{get_text('no_sources')}_")
            return

        for h in all_health:
            if h.status == "healthy":
                dot = '<span class="status-dot active"></span>'
            elif h.status == "degraded":
                dot = '<span class="status-dot warning"></span>'
            else:
                dot = '<span class="status-dot error"></span>'

            rate = f"{h.success_rate:.0%}"
            latency = f"{h.avg_latency_ms:.0f}ms" if h.avg_latency_ms > 0 else "-"

            col_name, col_stat, col_rate, col_latency, col_action = st.columns([3, 1, 1, 1, 1])
            with col_name:
                st.markdown(f"{dot} **{h.source_name}**", unsafe_allow_html=True)
            with col_stat:
                label = get_text(f"source_{h.status}")
                st.caption(label)
            with col_rate:
                st.caption(rate)
            with col_latency:
                st.caption(latency)
            with col_action:
                if h.status in ("degraded", "down"):
                    if st.button(get_text("source_reset"), key=f"reset_{h.source_name}"):
                        h.reset()
                        save_health(h)
                        st.rerun()


def _render_search_service_settings():
    """第三方搜索服务设置（NewsAPI key：文件 > env，保存后立即生效）"""
    with st.expander(get_text("search_service_settings"), expanded=False):
        try:
            from intelnexus.config.search_settings import (
                get_search_settings, save_search_settings)
            current = get_search_settings().get("news_api_key", "")
        except Exception as e:
            logger.warning(f"搜索设置模块不可用: {e}")
            return

        masked = (current[:4] + "****" + current[-4:]) if len(current) > 8 else current
        st.caption(get_text("newsapi_key_hint").format(masked=masked or "未配置"))

        new_key = st.text_input(
            get_text("newsapi_key"),
            value="",
            type="password",
            key="newsapi_key_input",
            placeholder=get_text("newsapi_key_placeholder"),
        )
        col_save, col_clear = st.columns([1, 1])
        with col_save:
            if st.button(get_text("save_changes"), key="newsapi_save_btn"):
                if new_key.strip() and save_search_settings({"news_api_key": new_key.strip()}):
                    st.success(get_text("newsapi_saved"))
                    st.rerun()
                else:
                    st.error(get_text("fill_fields"))
        with col_clear:
            if current and st.button(get_text("newsapi_clear"), key="newsapi_clear_btn"):
                if save_search_settings({"news_api_key": ""}):
                    st.success(get_text("newsapi_cleared"))
                    st.rerun()

        # ---- 搜索源开关（F: 源太少问题的 UI 入口）----
        st.markdown("---")
        try:
            from intelnexus.config.search_settings import (
                get_source_toggles, save_source_toggles)
            import config as _app_cfg
            toggles = get_source_toggles()
            st.caption(get_text("source_toggles_hint"))
            labels = {
                "ENABLE_NVD": "NVD 漏洞库", 
                "ENABLE_CISA_KEV": "CISA KEV 已知被利用漏洞", 
                "ENABLE_CNVD": "CNVD 国内漏洞库", 
                "ENABLE_ARXIV": "arXiv 论文", 
                "ENABLE_HUGGINGFACE": "HuggingFace", 
                "ENABLE_EXPLOITDB": "Exploit-DB 利用代码", 
                "ENABLE_OTX": "AlienVault OTX", 
                "ENABLE_DARKWEB": "暗网 (Tor)", 
                "ENABLE_HN": "Hacker News",
            }
            new_toggles = {}
            for key, label in labels.items():
                new_toggles[key] = st.checkbox(
                    label, value=bool(toggles.get(key, False)),
                    key=f"src_toggle_{key}")
            if st.button(get_text("source_toggles_save"), key="src_toggles_save_btn"):
                if save_source_toggles(new_toggles):
                    for k, v in new_toggles.items():
                        setattr(_app_cfg, k, v)
                    from intelnexus.core.search.registry import reset_registry_cache
                    reset_registry_cache()
                    st.success(get_text("source_toggles_saved"))
                    st.rerun()
        except Exception as e:
            logger.warning(f"源开关面板不可用: {e}")


def _render_model_settings():
    """模型选择（核心设置）"""
    st.markdown('<div class="sb-section"><span class="sb-section__label">Model</span></div>', unsafe_allow_html=True)

    model_options = get_model_choices()
    if not model_options:
        st.info(get_text("no_model_hint"))
        model = None
    else:
        model = st.selectbox(get_text("llm_model"), model_options, index=0)
        if is_vision_model(model):
            st.warning(get_text("vision_model_warning").format(model=model))

    return model


def _render_advanced_settings():
    """高级设置（线程数 + 语言 + 自定义模型）"""
    with st.expander("高级设置", expanded=False):
        # 线程数
        threads = st.slider(get_text("threads"), 1, 16, 5, key="threads_slider")

        # 语言选择
        lang_options = {get_text("zh"): "zh", get_text("en"): "en"}
        selected_lang = st.selectbox(get_text("language"), list(lang_options.keys()),
                                      index=0 if st.session_state.lang == "zh" else 1,
                                      key="lang_selector")
        if lang_options.get(selected_lang) != st.session_state.lang:
            st.session_state.lang = lang_options[selected_lang]
            st.rerun()

        # 自定义模型
        _render_custom_models()

    return threads


def _render_custom_models():
    """自定义模型管理：添加 / 编辑 / 测试连接 / 删除"""
    st.markdown('<div class="sb-section"><span class="sb-section__label">Custom Models</span></div>', unsafe_allow_html=True)

    MODEL_TYPES = [
        "OpenAI", "Azure OpenAI", "Anthropic", "Google", "Cohere",
        "Mistral", "DeepSeek", "Ollama",
        get_text("model_type_qwen"), get_text("model_type_zhipu"),
        get_text("model_type_baidu"), get_text("model_type_xunfei"),
        "Moonshot", "01.AI",
    ]

    DEFAULT_BASE_URLS = {
        "OpenAI": "https://api.openai.com/v1",
        "Azure OpenAI": "",
        "DeepSeek": "https://api.deepseek.com",
        "Anthropic": "https://api.anthropic.com",
        "Google": "https://generativelanguage.googleapis.com/v1beta",
        "Ollama": "http://127.0.0.1:11434",
        "Moonshot": "https://api.moonshot.cn/v1",
        get_text("model_type_qwen"): "https://dashscope.aliyuncs.com/compatible-mode/v1",
        get_text("model_type_zhipu"): "https://open.bigmodel.cn/api/paas/v4",
        get_text("model_type_baidu"): "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop",
        get_text("model_type_xunfei"): "https://spark-api-open.xf-yun.com/v1",
        "01.AI": "https://api.01.ai/v1",
        "Cohere": "https://api.cohere.ai",
        "Mistral": "https://api.mistral.ai/v1",
    }

    MULTI_BASE_URLS = {
        "DeepSeek": [
            ("OpenAI 格式 (https://api.deepseek.com)", "https://api.deepseek.com"),
            ("Anthropic 格式 (https://api.deepseek.com/anthropic)", "https://api.deepseek.com/anthropic"),
        ],
        "Azure OpenAI": [
            ("自定义", ""),
        ],
    }

    # ---- 已有模型列表 ----
    custom_models = get_custom_models()
    if custom_models:
        st.markdown(f"**{get_text('custom_models_list')}**")
        for model in custom_models:
            mname = model["name"]
            mtype = model.get("type", "")
            editing_key = f"editing_{mname}"
            is_editing = st.session_state.get(editing_key, False)

            # 模型信息
            st.markdown(f"**{mname}** ` `{mtype}` `")

            # 按钮行（单层 columns，不嵌套）
            if is_editing:
                btn_save, btn_cancel = st.columns(2)
                with btn_save:
                    if st.button(get_text("save_changes"), key=f"save_{mname}", type="primary"):
                        new_config = {
                            "model_name": st.session_state.get(f"edit_model_id_{mname}", ""),
                            "base_url": st.session_state.get(f"edit_base_url_{mname}", ""),
                            "api_key": st.session_state.get(f"edit_api_key_{mname}", ""),
                        }
                        new_type = st.session_state.get(f"edit_type_{mname}", mtype)
                        if update_custom_model(mname, new_type, new_config):
                            st.success(get_text("model_update_success"))
                            st.session_state[editing_key] = False
                            st.rerun()
                        else:
                            st.error(get_text("error"))
                with btn_cancel:
                    if st.button(get_text("cancel_edit"), key=f"cancel_{mname}"):
                        st.session_state[editing_key] = False
                        st.rerun()
            else:
                btn_edit, btn_test, btn_del = st.columns(3)
                with btn_edit:
                    if st.button(get_text("edit_model"), key=f"edit_{mname}"):
                        mconfig = get_model_config(mname)
                        cfg = mconfig.get("config", {}) if mconfig else {}
                        _norm_type = next((t for t in MODEL_TYPES if t.lower() == mtype.lower()), mtype)
                        st.session_state[f"edit_type_{mname}"] = _norm_type
                        st.session_state[f"edit_model_id_{mname}"] = cfg.get("model_name", "")
                        st.session_state[f"edit_base_url_{mname}"] = cfg.get("base_url", "")
                        st.session_state[f"edit_api_key_{mname}"] = cfg.get("api_key", "")
                        st.session_state[editing_key] = True
                        st.rerun()
                with btn_test:
                    if st.button(get_text("test_connection"), key=f"test_{mname}"):
                        mconfig = get_model_config(mname)
                        if mconfig:
                            with st.spinner(get_text("testing_connection")):
                                ok, msg = test_model_connection(
                                    mconfig.get("type", ""),
                                    mconfig.get("config", {}),
                                )
                                if ok:
                                    st.success(f"✅ {get_text('connection_success')}")
                                else:
                                    st.error(f"❌ {msg}")
                with btn_del:
                    if st.button(get_text("delete"), key=f"delete_{mname}"):
                        if remove_custom_model(mname):
                            st.success(get_text("deleted"))
                            st.rerun()

            # 编辑表单（展开在模型条目下方）
            if is_editing:
                prev_type_key = f"_prev_edit_type_{mname}"
                cur_edit_type = st.session_state.get(f"edit_type_{mname}", mtype)
                if prev_type_key not in st.session_state:
                    st.session_state[prev_type_key] = cur_edit_type
                elif cur_edit_type != st.session_state[prev_type_key]:
                    if cur_edit_type in MULTI_BASE_URLS:
                        st.session_state[f"edit_base_url_{mname}"] = MULTI_BASE_URLS[cur_edit_type][0][1]
                    elif cur_edit_type in DEFAULT_BASE_URLS:
                        st.session_state[f"edit_base_url_{mname}"] = DEFAULT_BASE_URLS[cur_edit_type]
                    st.session_state[prev_type_key] = cur_edit_type

                edit_type = st.selectbox(
                    get_text("model_type"),
                    MODEL_TYPES,
                    key=f"edit_type_{mname}",
                )
                st.text_input(
                    get_text("model_id"),
                    key=f"edit_model_id_{mname}",
                )

                if edit_type in MULTI_BASE_URLS:
                    options = MULTI_BASE_URLS[edit_type]
                    labels = [opt[0] for opt in options]
                    cur_url = st.session_state.get(f"edit_base_url_{mname}", "")
                    cur_label = next((lbl for lbl, url in options if url == cur_url), labels[0])
                    sel_label = st.selectbox(
                        get_text("base_url"),
                        labels,
                        index=labels.index(cur_label) if cur_label in labels else 0,
                        key=f"edit_base_url_format_{mname}",
                    )
                    st.session_state[f"edit_base_url_{mname}"] = options[labels.index(sel_label)][1]
                else:
                    st.text_input(
                        get_text("base_url"),
                        key=f"edit_base_url_{mname}",
                    )

                st.text_input(
                    get_text("api_key"),
                    type="password",
                    key=f"edit_api_key_{mname}",
                )

                if st.button(get_text("test_connection"), key=f"test_edit_{mname}"):
                    test_config = {
                        "model_name": st.session_state.get(f"edit_model_id_{mname}", ""),
                        "base_url": st.session_state.get(f"edit_base_url_{mname}", ""),
                        "api_key": st.session_state.get(f"edit_api_key_{mname}", ""),
                    }
                    test_type = st.session_state.get(f"edit_type_{mname}", mtype)
                    with st.spinner(get_text("testing_connection")):
                        ok, msg = test_model_connection(test_type, test_config)
                        if ok:
                            st.success(f"✅ {get_text('connection_success')}")
                        else:
                            st.error(f"❌ {msg}")

            st.divider()

    # ---- 添加新模型（按钮折叠，不使用 expander 避免嵌套） ----
    show_add = st.session_state.get("show_add_model", False)
    if st.button(get_text("add_new_model"), key="toggle_add_model"):
        st.session_state["show_add_model"] = not show_add
        st.rerun()

    if show_add:
        custom_model_name = st.text_input(get_text("model_name"), key="custom_model_name")
        model_type = st.selectbox(
            get_text("model_type"),
            MODEL_TYPES,
            key="model_type_selector",
        )

        if model_type in MULTI_BASE_URLS:
            options = MULTI_BASE_URLS[model_type]
            labels = [opt[0] for opt in options]
            selected_label = st.selectbox(get_text("base_url"), labels, key="add_base_url_format")
            base_url = options[labels.index(selected_label)][1]
        else:
            default_url = DEFAULT_BASE_URLS.get(model_type, "")
            if model_type != st.session_state.get("_prev_add_model_type", ""):
                st.session_state["add_model_base_url"] = default_url
                st.session_state["_prev_add_model_type"] = model_type
            base_url = st.text_input(
                get_text("base_url"),
                key="add_model_base_url",
            )

        api_key = st.text_input(get_text("api_key"), type="password", key="add_model_api_key")
        model_id = st.text_input(get_text("model_id"), key="add_model_id")

        if st.button(get_text("add_model")):
            if custom_model_name and model_id and base_url:
                config = {"model_name": model_id, "base_url": base_url, "api_key": api_key}
                if add_custom_model(custom_model_name, model_type.lower(), config):
                    st.success(get_text("model_add_success"))
                    st.rerun()
                else:
                    st.error(get_text("model_exists"))
            else:
                st.error(get_text("fill_fields"))


def render_sidebar():
    """
    Sidebar: cold-gray workbench style.

    Structure:
      Brand → Search Mode → Model → [Advanced Settings]

    简报业务（数据源/订阅者/生成）已收拢至简报 Tab，侧边栏仅保留全局设置。
    """
    with st.sidebar:
        # Brand
        st.markdown(f'<div class="sidebar-title">{get_text("title")}</div>', unsafe_allow_html=True)

        # Core: Search Mode
        search_mode = _render_search_mode()

        # Source Health Panel
        _render_source_health()

        # Search service settings (NewsAPI key)
        _render_search_service_settings()

        # Core: Model Settings
        model = _render_model_settings()

        # Advanced: Threads, Language, Custom Models
        threads = _render_advanced_settings()

    return search_mode, model, threads
