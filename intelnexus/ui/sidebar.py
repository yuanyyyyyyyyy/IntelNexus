import streamlit as st
import base64
import html
import json
import os
from intelnexus.core.logger import get_logger
from intelnexus.ui.i18n import get_text, localize_llm_test_error
from intelnexus.ui.icons import icon
from intelnexus.core.ui.helpers import (
    SEARCH_MODES, DEFAULT_TOR_PORT,
    find_tor_port, is_tor_running, get_tor_port,
)
from intelnexus.core.llm.utils import get_model_choices, is_vision_model
from intelnexus.core.llm.models import (
    add_custom_model, get_custom_model_names, remove_custom_model,
    get_custom_models, get_model_config, update_custom_model, test_model_connection,
    add_custom_provider, get_custom_providers, remove_custom_provider,
    get_custom_provider_names, get_provider_config, update_custom_provider,
    test_provider_connection,
)
from intelnexus.search_app.darkweb import is_available as darkweb_available

logger = get_logger(__name__)




def _render_search_mode():
    """搜索模式选择 + 暗网设置"""
    from intelnexus.ui.icons import icon as _icon
    from intelnexus.ui._caches import cached_tor_state
    # widget key 预置默认值：number_input 只给 key= 不给 value=，避免
    # 「default value but also had its value set via Session State API」政策警告刷屏
    # Tor 端口探测走缓存（ttl=15），避免每次切 Tab 重复探测
    _cached_tor_port, _cached_tor_running = cached_tor_state()
    if "tor_port" not in st.session_state:
        # 首次加载默认到探测到的真实 Tor 端口，否则回退 9150
        st.session_state.tor_port = _cached_tor_port or DEFAULT_TOR_PORT
    st.markdown(f'<div class="sb-section"><span class="sb-section__label">{_icon("investigate", "sm", "blue")} {get_text("sidebar_mode_label")}</span></div>', unsafe_allow_html=True)

    # 方案一（智能路由）：「智能」置顶为默认——按查询主题自动路由，
    # 手动 5 模式收进高级折叠区供精确控制；暗网仅在 Tor 存活时出现在手动列表。
    from intelnexus.core.search.modes import SMART_MODE_KEY, SMART_GENERAL_KEY

    # 手动列表只暴露用户可选的 5 模式；smart/smart_general 是路由内部值
    manual_modes = [m for m in SEARCH_MODES.keys() if m != SMART_GENERAL_KEY]
    # 可见性基于 Tor 真实连接状态（自动探测常见 SOCKS 端口），而非 ENABLE_DARKWEB 开关
    tor_running = _cached_tor_running
    if not tor_running:
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
                if not tor_running:
                    st.error(get_text("darkweb_tor_offline_hint"))
    elif not tor_running:
        st.caption(get_text("smart_hint_no_tor"))
    return search_mode

def _render_darkweb_settings():
    """暗网模式设置面板（Tor 端口/高级选项/自定义 onion 源）。返回所选 Tor 端口。"""
    with st.expander(get_text('darkweb_settings'), expanded=True):
        tor_port = st.number_input(
            get_text("tor_port"),
            min_value=1,
            max_value=65535,
            key="tor_port"
        )

        tor_running = is_tor_running(preferred=tor_port)
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

        st.divider()
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
                    # 入库前 URL 安全校验（协议/目标地址）；校验器不可用时放行原流程（仅记日志）
                    try:
                        from intelnexus.core.security.url_guard import validate_external_url
                        url_ok, url_reason = validate_external_url(new_site_url)
                    except Exception as e:
                        logger.warning(f"URL 校验器不可用，放行原流程: {e}")
                        url_ok, url_reason = True, ""
                    if not url_ok:
                        st.error(get_text(f"sec_url_{url_reason}"))
                    else:
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
    """数据源健康状态面板（只读展示；写副作用移到刷新按钮与会话一次性守卫）。

    旧实现每帧都调用 purge_stale_entries()（写盘）+ invalidate_status_metrics()，
    既浪费又把 15s 运行指标缓存每帧失效（等于废掉缓存），且每次切 Tab 都写盘。
    现改为：会话首帧自动清理一次 + 刷新按钮手动清理，平时只走只读缓存。
    """
    try:
        from intelnexus.core.search.health import save_health
        from intelnexus.ui._caches import cached_registry, cached_all_health
        from intelnexus.ui.status_metrics import (
            invalidate_status_metrics, get_health_summary_cached)
        from intelnexus.config.search_settings import get_news_api_key as NEWS_API_KEY
        registry = cached_registry(news_api_key=NEWS_API_KEY())
        active_names = [s.name for s in registry.all_sources()]
    except Exception:
        return

    # 会话首帧一次性清理测试残留/已删源的僵尸条目（写操作只发生一次，不阻塞切 Tab）
    if not st.session_state.get("_health_purged_once", False):
        try:
            from intelnexus.core.search.health import purge_stale_entries
            purge_stale_entries(active_names)
            invalidate_status_metrics()
            cached_all_health.clear()
        except Exception:
            pass
        st.session_state["_health_purged_once"] = True

    try:
        all_health = cached_all_health()
    except Exception:
        return

    with st.expander(get_text("source_health"), expanded=False):
        # 顶部聚合摘要：与状态栏/健康概览面板共享同一口径（15s 缓存）
        try:
            _s = get_health_summary_cached() or {}
            st.caption(get_text("health_summary_line").format(
                healthy=int(_s.get("healthy") or 0),
                degraded=int(_s.get("degraded") or 0),
                down=int(_s.get("down") or 0)))
        except Exception:
            pass

        # 刷新按钮：清理僵尸条目 + 失效缓存并重读（不发起网络探测）
        if st.button(get_text("health_refresh"), key="sb_health_refresh",
                     use_container_width=True):
            try:
                from intelnexus.core.search.health import purge_stale_entries
                purge_stale_entries(active_names)
                invalidate_status_metrics()
                cached_all_health.clear()
            except Exception:
                pass
            st.rerun()
        st.caption(get_text("health_refresh_hint"))

        if not all_health:
            st.markdown(f"_{get_text('no_sources')}_")
            return

        st.caption(get_text("health_reset_hint"))
        for h in all_health:
            # 白名单校验：注册表不存在的源名（异常写入/残留）不渲染，只记日志。
            # purge 已清理大部分僵尸条目，此处是二次防御。
            if h.source_name not in active_names:
                logger.warning(
                    f"sidebar health: skipping entry for unknown source "
                    f"{h.source_name!r} (not in active registry)")
                continue
            if h.status == "healthy":
                dot = '<span class="status-dot active"></span>'
            elif h.status == "degraded":
                dot = '<span class="status-dot warning"></span>'
            else:
                dot = '<span class="status-dot error"></span>'

            rate = f"{h.success_rate:.0%}"
            latency = f"{h.avg_latency_ms:.0f}ms" if h.avg_latency_ms > 0 else "-"

            col_name, col_stat, col_rate, col_latency, col_action = st.columns([3, 1.2, 1, 1, 1.5])
            with col_name:
                # source_name 用户可控（自定义源名），拼入 HTML 前必须转义防 XSS
                st.markdown(f"{dot} **{html.escape(h.source_name)}**", unsafe_allow_html=True)
            with col_stat:
                label = get_text(f"source_{h.status}")
                st.caption(label)
            with col_rate:
                st.caption(rate)
            with col_latency:
                st.caption(latency)
            with col_action:
                if h.status in ("degraded", "down"):
                    if st.button(get_text("source_reset"), key=f"reset_{h.source_name}",
                                 use_container_width=True):
                        h.reset()
                        save_health(h)
                        # 必须一并失效健康缓存：否则 st.rerun() 后面板仍显示旧的
                        # degraded/down，用户会以为「重置没生效」
                        _invalidate_health_caches()
                        st.rerun()


#: 各站内检索 Provider 对应的凭证字段（用于掩码展示「到底存上了没有」）
_SITE_SEARCH_CREDENTIAL_FIELDS = {
    "bocha": ("bocha_api_key",),
    "brave": ("brave_api_key",),
    "google_cse": ("google_cse_api_key", "google_cse_id"),
}


def _mask_secret(value: str) -> str:
    """掩码密钥：只留首尾各 4 位。

    界面与日志**绝不回显明文**——密码框恒为空白（不回填），用户只能从掩码串
    确认凭证是否已保存。

    长度阈值取 12：短凭证（如 Google CSE 的 cx、自挂 Provider 的短 token）
    若仍留首尾各 4 位，掩码后几乎等于明文，故一律只显示 ``****``。
    """
    v = (value or "").strip()
    if not v:
        return ""
    if len(v) <= 12:
        return "****"
    return f"{v[:4]}****{v[-4:]}"


def _site_search_masked(cfg: dict, provider: str) -> str:
    """返回该 Provider 已保存凭证的掩码串；未配置返回空串。"""
    vals = [str(cfg.get(f, "") or "").strip()
            for f in _SITE_SEARCH_CREDENTIAL_FIELDS.get(provider, ())]
    vals = [v for v in vals if v]
    return " / ".join(_mask_secret(v) for v in vals) if vals else ""


def _site_scoped_sources():
    """返回依赖「站内检索后端」的源实例列表（取不到时返回空列表，不阻塞 UI）。"""
    try:
        from intelnexus.ui._caches import cached_registry
        from intelnexus.config.search_settings import get_news_api_key
        from intelnexus.core.search.sources.site_scoped_source import SiteScopedSource
        reg = cached_registry(news_api_key=get_news_api_key())
        return [s for s in reg.all_sources() if isinstance(s, SiteScopedSource)]
    except Exception as e:
        logger.warning(f"获取站内源失败: {e}")
        return []


def _site_scoped_source_names():
    """依赖站内检索后端的源名列表。"""
    return [s.name for s in _site_scoped_sources()]


def _site_scoped_probe_domain():
    """自检目标域名：用站内源**自己的**域名，而不是通用占位域。

    若拿 ``example.com`` 自检却把结论记在「小红书」名下，那么「include 限定
    失效 / 该站点被后端限制」这类**只在召回层可见**的故障会被系统性掩盖——
    源会一直显示 healthy 却始终取不到站内内容。
    """
    for src in _site_scoped_sources():
        for dom in (getattr(src, "domains", ()) or ()):
            if dom:
                return dom
    return ""


def _invalidate_health_caches():
    """健康状态已变更：失效 UI 缓存，否则面板仍显示旧状态。"""
    try:
        from intelnexus.ui._caches import cached_all_health
        from intelnexus.ui.status_metrics import invalidate_status_metrics
        cached_all_health.clear()
        invalidate_status_metrics()
    except Exception as e:
        logger.warning(f"失效健康缓存失败: {e}")


def _reset_site_scoped_health():
    """重置站内源的健康状态（保存凭证后调用）。

    凭证更新前的失败（「未配置后端」「网络不可达」等）已成**陈旧信号**，不清掉
    会让源继续挂在 degraded/down，用户明明修好了却仍取不到数据。
    """
    try:
        from intelnexus.core.search.health import reset_health_for
        names = _site_scoped_source_names()
        if names and reset_health_for(names):
            _invalidate_health_caches()
            logger.info(f"已重置站内源健康状态: {names}")
    except Exception as e:
        logger.warning(f"重置站内源健康状态失败: {e}")


def _run_site_search_trial(query: str) -> dict:
    """端到端试搜：真跑一次站内检索，回答「能不能取到站内内容」。

    与 ``probe_site_search`` 分工明确——自检只验证凭证与连通性（便宜），试搜才
    验证召回（贵，消耗 1 次额度）。两者都由用户显式点击触发，绝不在检索管线里
    自动加测。
    """
    out: dict = {"query": query, "rows": [], "error": "", "raw": 0, "kept": 0}
    try:
        from intelnexus.ui._caches import cached_registry
        from intelnexus.config.search_settings import get_news_api_key
        from intelnexus.core.search.sources.site_scoped_source import SiteScopedSource
        reg = cached_registry(news_api_key=get_news_api_key())
        scoped = [s for s in reg.all_sources() if isinstance(s, SiteScopedSource)]
        if not scoped:
            out["error"] = get_text("site_search_trial_no_source")
            return out
        raw = 0
        for src in scoped:
            out["rows"].extend(list(src.search(query) or []))
            # 取源的过滤统计：用于区分「后端没返回」与「过滤后没留下」
            stats = getattr(src, "last_filter_stats", None) or {}
            raw += int(stats.get("raw") or 0)
        out["raw"] = raw
        out["kept"] = len(out["rows"])
    except Exception as e:
        logger.warning(f"站内试搜失败: {e}")
        # 异常文本可能带出 query 中的凭证（Google CSE 的 Key 走 query）
        from intelnexus.core.search.sitesearch.base import redact_secrets
        out["error"] = redact_secrets(f"{type(e).__name__}: {e}")
    return out


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
                    from intelnexus.ui._caches import cached_registry
                    cached_registry.clear()  # NewsAPI key 已变，刷新注册表缓存
                    st.rerun()
                else:
                    st.error(get_text("fill_fields"))
        with col_clear:
            if current and st.button(get_text("newsapi_clear"), key="newsapi_clear_btn"):
                if save_search_settings({"news_api_key": ""}):
                    st.success(get_text("newsapi_cleared"))
                    from intelnexus.ui._caches import cached_registry
                    cached_registry.clear()  # NewsAPI key 已变，刷新注册表缓存
                    st.rerun()

        # ---- 站内检索后端（小红书等 SiteScopedSource 的取数依赖）----
        st.markdown("---")
        try:
            from intelnexus.config.search_settings import get_site_search_config
            from intelnexus.core.search.sitesearch import (
                available_providers, reset_site_search_backend, probe_site_search)
            from intelnexus.core.search.sitesearch.base import redact_secrets

            sec_cfg = get_site_search_config()
            _available = available_providers(sec_cfg)
        except Exception as e:
            # try 只覆盖「导入 + 读配置」：渲染期故障应显式暴露，而不是界面空白
            logger.warning(f"站内检索后端配置不可用: {e}")
            sec_cfg = None

        if sec_cfg is not None:
            st.caption(get_text("site_search_section"))
            st.caption(get_text("site_search_apply_steps"))

            _provider_labels = {
                "bocha": get_text("site_search_provider_bocha"),
                "brave": get_text("site_search_provider_brave"),
                "google_cse": get_text("site_search_provider_google"),
            }
            _avail_text = " / ".join(_provider_labels[p] for p in _available) \
                if _available else get_text("site_search_provider_none")
            st.caption(get_text("site_search_provider_hint").format(current=_avail_text))

            # 各 Provider 的凭证状态（掩码）。输入框恒为空白（密码框不回填明文），
            # 用户只能从这里确认「上次保存的 Key 到底还在不在」。
            for _p in ("bocha", "brave", "google_cse"):
                _masked = _site_search_masked(sec_cfg, _p)
                _state = (get_text("site_search_cfg_configured").format(masked=_masked)
                          if _masked else get_text("site_search_cfg_unset"))
                st.caption(f"{_provider_labels[_p]}：{_state}")

            _options = [
                ("auto", get_text("site_search_provider_auto")),
                ("bocha", get_text("site_search_provider_bocha")),
                ("brave", get_text("site_search_provider_brave")),
                ("google_cse", get_text("site_search_provider_google")),
            ]
            _labels = [label for _k, label in _options]
            _cur = sec_cfg.get("site_search_provider", "auto")
            _idx = next((i for i, (k, _l) in enumerate(_options) if k == _cur), 0)
            _sel = st.selectbox(get_text("site_search_provider"), _labels,
                                index=_idx, key="site_search_provider_select")

            _new_bc_key = st.text_input(
                get_text("bocha_api_key"), value="", type="password",
                key="bocha_api_key_input",
                placeholder=get_text("site_search_key_placeholder"))
            _new_g_key = st.text_input(
                get_text("google_cse_api_key"), value="", type="password",
                key="google_cse_api_key_input",
                placeholder=get_text("site_search_key_placeholder"))
            _new_g_cx = st.text_input(
                get_text("google_cse_id"), value="", type="password",
                key="google_cse_id_input",
                placeholder=get_text("site_search_key_placeholder"))
            _new_b_key = st.text_input(
                get_text("brave_api_key"), value="", type="password",
                key="brave_api_key_input",
                placeholder=get_text("site_search_key_placeholder"))

            col_sec_save, col_sec_clear = st.columns([1, 1])
            with col_sec_save:
                if st.button(get_text("save_changes"), key="site_search_save_btn"):
                    updates = {"site_search_provider": _options[_labels.index(_sel)][0]}
                    if _new_bc_key.strip():
                        updates["bocha_api_key"] = _new_bc_key.strip()
                    if _new_g_key.strip():
                        updates["google_cse_api_key"] = _new_g_key.strip()
                    if _new_g_cx.strip():
                        updates["google_cse_id"] = _new_g_cx.strip()
                    if _new_b_key.strip():
                        updates["brave_api_key"] = _new_b_key.strip()
                    if save_search_settings(updates):
                        reset_site_search_backend()  # 凭证已变，重建后端实例
                        # 凭证更新前的失败（未配置/不可达）已成陈旧信号，不清掉
                        # 会让源继续挂在 degraded，用户明明修好了却仍取不到数据
                        _reset_site_scoped_health()
                        from intelnexus.ui._caches import cached_registry
                        cached_registry.clear()
                        st.success(get_text("site_search_saved"))
                        st.rerun()
                    else:
                        # 此处只可能是写盘失败（updates 恒含 provider），
                        # 不应提示「请填写所有必填字段」
                        st.error(get_text("site_search_save_failed"))
            with col_sec_clear:
                if any(sec_cfg.get(k) for k in
                       ("bocha_api_key", "google_cse_api_key", "google_cse_id",
                        "brave_api_key")):
                    if st.button(get_text("site_search_clear"), key="site_search_clear_btn"):
                        if save_search_settings({"bocha_api_key": "",
                                                 "google_cse_api_key": "",
                                                 "google_cse_id": "",
                                                 "brave_api_key": ""}):
                            reset_site_search_backend()
                            # 与保存路径对称：清掉陈旧的健康状态与上一次的结论。
                            # 否则界面会一直显示「连接正常」，而凭证其实已被清除
                            # ——陈旧的成功结论比没有结论更危险。
                            _reset_site_scoped_health()
                            for _k in ("site_search_probe_result",
                                       "site_search_trial_result"):
                                st.session_state.pop(_k, None)
                            from intelnexus.ui._caches import cached_registry
                            cached_registry.clear()
                            st.success(get_text("site_search_cleared"))
                            st.rerun()

            # ---- 连通性自检：只回答「后端能不能通、Key 有没有效」----
            # 不做端到端召回验证（那是下方「试搜」的职责，成本更高）。
            st.caption(get_text("site_search_test_cost_hint"))
            if st.button(get_text("site_search_test"), key="site_search_test_btn",
                         use_container_width=True):
                with st.spinner(get_text("site_search_testing")):
                    try:
                        # 未保存的输入优先纳入探测：用户「填完 Key 直接点测试」
                        # 时若只读已保存配置，会报「未配置任何后端」，恰好制造
                        # 「Key 没保存上」的错觉。
                        _probe_cfg = dict(sec_cfg)
                        for _f, _v in (("bocha_api_key", _new_bc_key),
                                       ("google_cse_api_key", _new_g_key),
                                       ("google_cse_id", _new_g_cx),
                                       ("brave_api_key", _new_b_key)):
                            if _v.strip():
                                _probe_cfg[_f] = _v.strip()
                        # 用站内源自己的域名自检，避免「占位域可用」被记成
                        # 「小红书源健康」而掩盖召回层故障
                        _res = probe_site_search(
                            _probe_cfg, domain=_site_scoped_probe_domain())
                    except Exception as _e:
                        # 自检本身异常不得让面板崩掉：降级为一个 error 结论
                        _res = {"provider": "", "configured": False, "ok": False,
                                "kind": "error", "latency_ms": 0.0,
                                "message": f"{type(_e).__name__}: {_e}"}
                # 存 session_state：st.rerun() 会丢弃本帧内联渲染，重绘后仍要看到结论
                st.session_state["site_search_probe_result"] = _res
                try:
                    # 复用「用户源批量测试」的探测语义（失败即时降级、成功即恢复）
                    from intelnexus.core.search.health import record_probe_result
                    for _n in _site_scoped_source_names():
                        record_probe_result(_n, bool(_res.get("ok")),
                                            float(_res.get("latency_ms") or 0),
                                            _res.get("message") or None)
                    _invalidate_health_caches()
                except Exception as _e:
                    logger.warning(f"写入自检探测结果失败: {_e}")
                # 健康面板在本帧「搜索服务设置」之前已渲染完，不重跑就看不到
                # 刚写入的结论（与重置按钮保持一致）
                st.rerun()

            _probe = st.session_state.get("site_search_probe_result")
            if _probe:
                if _probe.get("ok"):
                    st.success(get_text("site_search_test_ok").format(
                        provider=_probe.get("provider", ""),
                        latency=_probe.get("latency_ms", 0)))
                else:
                    st.error(get_text("site_search_test_failed").format(
                        reason=get_text(
                            f"site_search_err_{_probe.get('kind')}")))
                    if _probe.get("message"):
                        # message 已在 probe_site_search 内统一 redact 脱敏
                        st.caption(str(_probe["message"]))

            # ---- 端到端试搜：确认真能取到小红书站内内容 ----
            # 与「测试连接」分工：后者只验凭证与连通性，前者才验证召回。
            st.caption(get_text("site_search_trial_hint"))
            _trial_q = st.text_input(
                get_text("site_search_trial_query"), value="",
                key="site_search_trial_input",
                placeholder=get_text("site_search_trial_placeholder"))
            if st.button(get_text("site_search_trial"), key="site_search_trial_btn",
                         use_container_width=True):
                with st.spinner(get_text("site_search_testing")):
                    st.session_state["site_search_trial_result"] = \
                        _run_site_search_trial(_trial_q.strip() or "数据泄露")

            _trial = st.session_state.get("site_search_trial_result")
            if _trial:
                if _trial.get("error"):
                    st.error(get_text("site_search_trial_failed").format(
                        # 异常文本可能带出 query 中的凭证（Google CSE 走 query），
                        # 且要防 Markdown 注入
                        message=html.escape(redact_secrets(str(
                            _trial["error"]))[:200])))
                elif _trial.get("rows"):
                    st.success(get_text("site_search_trial_ok").format(
                        n=len(_trial["rows"])))
                    st.caption(get_text("site_search_trial_stats").format(
                        raw=_trial.get("raw", 0), kept=_trial.get("kept", 0)))
                    for _r in _trial["rows"][:5]:
                        # 标题/URL 来自外部检索结果，用 st.text（原样文本）而非
                        # st.caption（走 Markdown）：否则标题可构造
                        # [点我](http://evil) 渲染成可点击链接
                        st.text(f"- {str(_r.get('title') or '')[:60]}"
                                f" — {str(_r.get('url') or '')[:80]}")
                elif int(_trial.get("raw") or 0) > 0:
                    # 两种「0 条」必须区分：后端有返回却被过滤干净 ≠ 后端没返回
                    st.warning(get_text("site_search_trial_filtered_all").format(
                        raw=_trial.get("raw", 0)))
                else:
                    st.warning(get_text("site_search_trial_zero"))

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
                "ENABLE_XIAOHONGSHU": "小红书 社区笔记",
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
                    from intelnexus.ui._caches import cached_registry
                    reset_registry_cache()
                    cached_registry.clear()  # 源开关已变，刷新注册表缓存
                    st.success(get_text("source_toggles_saved"))
                    st.rerun()
        except Exception as e:
            logger.warning(f"源开关面板不可用: {e}")


def _render_model_settings():
    """模型选择（核心设置）"""
    from intelnexus.ui._caches import cached_model_choices
    # 单行带图标区块标题：与 sidebar_mode_label 同风格（英文 · 中文，i18n 单键）
    st.markdown(f'<div class="sb-section"><span class="sb-section__label">{icon("ai_model", "sm", "blue")} {get_text("sidebar_model_label")}</span></div>', unsafe_allow_html=True)

    # 模型选项含 Ollama HTTP 探测，走缓存（ttl=30）避免每次切 Tab 重探（Ollama 未运行时会卡约 3s）
    model_options = cached_model_choices()
    if not model_options:
        st.info(get_text("no_model_hint"))
        model = None
    else:
        # 加载上次选择的模型（持久化到 data/ui_settings.json）
        from intelnexus.config.paths import get_data_dir
        from intelnexus.core.settings.file_lock import safe_read_json, safe_write_json
        ui_settings_file = os.path.join(get_data_dir(), "ui_settings.json")
        ui_settings = safe_read_json(ui_settings_file) or {}
        saved_model = ui_settings.get("last_model", "")
        
        # 计算默认索引：优先使用上次选择的模型，否则用第一个
        default_index = 0
        if saved_model and saved_model in model_options:
            default_index = model_options.index(saved_model)
        
        # 标题已含「AI模型」文案，折叠 selectbox 标签避免第二行重复（与参照区 radio 的 label_visibility 处理一致）
        model = st.selectbox(
            get_text("llm_model"),
            model_options,
            index=default_index,
            label_visibility="collapsed",
            key="model_selectbox",
        )
        
        # 保存选择（仅当模型变化时）
        if model != saved_model:
            ui_settings["last_model"] = model
            safe_write_json(ui_settings_file, ui_settings)
        
        if is_vision_model(model):
            st.warning(get_text("vision_model_warning").format(model=model))

    return model


def _render_advanced_settings():
    """高级设置（线程数 + 语言 + 自定义模型）"""
    with st.expander(get_text("sidebar_advanced_settings"), expanded=False):
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
    from intelnexus.ui._caches import cached_model_choices
    st.markdown(f'<div class="sb-section"><span class="sb-section__label">{icon("layers", "sm", "blue")} {get_text("sidebar_custom_models_label")}</span></div>', unsafe_allow_html=True)

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

    # 动态添加自定义供应商到模型类型列表
    custom_providers = get_custom_providers()
    for provider in custom_providers:
        pname = provider["name"]
        if pname not in MODEL_TYPES:
            MODEL_TYPES.append(pname)
        if pname not in DEFAULT_BASE_URLS:
            DEFAULT_BASE_URLS[pname] = provider.get("base_url", "")

    # ---- 已有模型列表 ----
    # 列表标题已并入区块单行标题（sidebar_custom_models_label），不再单独渲染一行加粗文案；
    # 列表本体（紧凑间距容器 + 等宽等距按钮行）保持不变。
    custom_models = get_custom_models()
    if custom_models:
        # 外层容器统一小间距，压缩模型条目之间的垂直留白（替代侧边栏默认 1rem gap）；
        # key="cm_list" 使框架渲染 .st-key-cm_list 包装类，供 5c CSS 锚定条目分隔线（净化器无法剥离）
        with st.container(gap="small", key="cm_list"):
            for model in custom_models:
                mname = model["name"]
                mtype = model.get("type", "")
                editing_key = f"editing_{mname}"
                is_editing = st.session_state.get(editing_key, False)

                # 信息+按钮行整体包入容器归组；gap=8 保证名称行与按钮行之间恒定的 8px
                # 垂直间隔（gap=None 会因框架对 markdown 容器的 -1rem 补偿 margin 导致按钮行上移侵蚀文字）
                with st.container(gap=8):
                    # 模型信息
                    st.markdown(f"**{mname}** ` `{mtype}` `")

                    # 按钮行：等宽 columns + stretch 按钮，保证三按钮宽度一致、间隔严格相等（单层，不嵌套）
                    if is_editing:
                        btn_save, btn_cancel = st.columns(2, gap="small")
                        with btn_save:
                            if st.button(get_text("save_changes"), key=f"save_{mname}", type="primary", width="stretch"):
                                new_config = {
                                    "model_name": st.session_state.get(f"edit_model_id_{mname}", ""),
                                    "base_url": st.session_state.get(f"edit_base_url_{mname}", ""),
                                    "api_key": st.session_state.get(f"edit_api_key_{mname}", ""),
                                }
                                new_type = st.session_state.get(f"edit_type_{mname}", mtype)
                                new_display_name = st.session_state.get(f"edit_display_name_{mname}", "").strip()
                                if new_display_name and new_display_name != mname and new_display_name in get_custom_model_names():
                                    st.error(get_text("model_exists"))
                                elif update_custom_model(mname, new_type, new_config, new_name=new_display_name):
                                    st.success(get_text("model_update_success"))
                                    cached_model_choices.clear()  # 模型选项已变，刷新缓存
                                    st.session_state[editing_key] = False
                                    st.rerun()
                                else:
                                    st.error(get_text("error"))
                        with btn_cancel:
                            if st.button(get_text("cancel_edit"), key=f"cancel_{mname}", width="stretch"):
                                st.session_state[editing_key] = False
                                st.rerun()
                    else:
                        btn_edit, btn_test, btn_del = st.columns(3, gap="small")
                        with btn_edit:
                            if st.button(get_text("edit_model"), key=f"edit_{mname}", width="stretch"):
                                mconfig = get_model_config(mname)
                                cfg = mconfig.get("config", {}) if mconfig else {}
                                _norm_type = next((t for t in MODEL_TYPES if t.lower() == mtype.lower()), mtype)
                                st.session_state[f"edit_display_name_{mname}"] = mname
                                st.session_state[f"edit_type_{mname}"] = _norm_type
                                st.session_state[f"edit_model_id_{mname}"] = cfg.get("model_name", "")
                                st.session_state[f"edit_base_url_{mname}"] = cfg.get("base_url", "")
                                st.session_state[f"edit_api_key_{mname}"] = cfg.get("api_key", "")
                                st.session_state[editing_key] = True
                                st.rerun()
                        with btn_test:
                            if st.button(get_text("test_connection"), key=f"test_{mname}", width="stretch"):
                                mconfig = get_model_config(mname)
                                if mconfig:
                                    with st.spinner(get_text("testing_connection")):
                                        ok, msg = test_model_connection(
                                            mconfig.get("type", ""),
                                            mconfig.get("config", {}),
                                        )
                                        if ok:
                                            st.success(get_text("connection_success"))
                                        else:
                                            st.error(localize_llm_test_error(msg))
                        with btn_del:
                            if st.button(get_text("delete"), key=f"delete_{mname}", width="stretch"):
                                if remove_custom_model(mname):
                                    st.success(get_text("deleted"))
                                    cached_model_choices.clear()  # 模型选项已变，刷新缓存
                                    st.rerun()

                # 编辑表单（展开在模型条目下方，同样归入容器保持条目分组一致）
                if is_editing:
                    with st.container(gap=None):
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

                        st.text_input(
                            get_text("model_name"),
                            key=f"edit_display_name_{mname}",
                        )
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

                        if st.button(get_text("test_connection"), key=f"test_edit_{mname}", width="stretch"):
                            test_config = {
                                "model_name": st.session_state.get(f"edit_model_id_{mname}", ""),
                                "base_url": st.session_state.get(f"edit_base_url_{mname}", ""),
                                "api_key": st.session_state.get(f"edit_api_key_{mname}", ""),
                            }
                            test_type = st.session_state.get(f"edit_type_{mname}", mtype)
                            with st.spinner(get_text("testing_connection")):
                                ok, msg = test_model_connection(test_type, test_config)
                                if ok:
                                    st.success(get_text("connection_success"))
                                else:
                                    st.error(localize_llm_test_error(msg))

                # 条目分隔线：标准 st.divider()，由 5c CSS 通过 .st-key-cm_list 容器锚定（4px 紧凑 margin）
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

        btn_add, btn_cancel, btn_test = st.columns(3)
        with btn_add:
            if st.button(get_text("add_model"), type="primary"):
                if custom_model_name and model_id and base_url:
                    config = {"model_name": model_id, "base_url": base_url, "api_key": api_key}
                    if add_custom_model(custom_model_name, model_type.lower(), config):
                        st.success(get_text("model_add_success"))
                        cached_model_choices.clear()  # 模型选项已变，刷新缓存
                        st.rerun()
                    else:
                        st.error(get_text("model_exists"))
                else:
                    st.error(get_text("fill_fields"))
        with btn_cancel:
            if st.button(get_text("cancel_add")):
                st.session_state["show_add_model"] = False
                st.rerun()
        with btn_test:
            if st.button(get_text("test_connection"), key="test_new_model"):
                if model_id and base_url:
                    with st.spinner(get_text("testing_connection")):
                        config = {"model_name": model_id, "base_url": base_url, "api_key": api_key}
                        ok, msg = test_model_connection(model_type.lower(), config)
                        if ok:
                            st.success(msg)
                        else:
                            st.error(localize_llm_test_error(msg))
                else:
                    st.error(get_text("fill_fields"))

    # ---- 自定义供应商 ----
    _render_custom_providers()


def _render_custom_providers():
    """自定义供应商管理：添加 / 编辑 / 删除"""
    st.markdown(f'<div class="sb-section"><span class="sb-section__label">{icon("plug", "sm", "blue")} {get_text("sidebar_custom_providers_label")}</span></div>', unsafe_allow_html=True)

    # ---- 已有供应商列表 ----
    # 列表标题已并入区块单行标题（sidebar_custom_providers_label），不再单独渲染一行加粗文案。
    custom_providers = get_custom_providers()
    if custom_providers:
        # 外层容器统一小间距，压缩供应商条目之间的垂直留白（与模型列表保持一致）；
        # key="cp_list" 使框架渲染 .st-key-cp_list 包装类，供 5c CSS 锚定条目分隔线（净化器无法剥离）
        with st.container(gap="small", key="cp_list"):
            for provider in custom_providers:
                pname = provider["name"]
                purl = provider.get("base_url", "")
                premark = provider.get("remark", "")
                editing_key = f"editing_provider_{pname}"
                is_editing = st.session_state.get(editing_key, False)

                # 信息+按钮行整体包入容器归组；gap=8 保证名称行与按钮行之间恒定的 8px 垂直间隔
                # （与模型列表一致；详见 _render_custom_models 内同类注释）
                with st.container(gap=8):
                    # 供应商信息
                    display_text = f"**{pname}**"
                    if premark:
                        display_text += f" *{premark}*"
                    display_text += f" `{purl}`"
                    st.markdown(display_text)

                    # 按钮行：等宽 columns + stretch 按钮，保证三按钮宽度一致、间隔严格相等
                    if is_editing:
                        btn_save, btn_cancel, btn_test = st.columns(3, gap="small")
                        with btn_save:
                            if st.button(get_text("save_changes"), key=f"save_provider_{pname}", type="primary", width="stretch"):
                                new_config = {
                                    "base_url": st.session_state.get(f"edit_provider_url_{pname}", ""),
                                    "remark": st.session_state.get(f"edit_provider_remark_{pname}", ""),
                                    "website": st.session_state.get(f"edit_provider_website_{pname}", ""),
                                    "api_key": st.session_state.get(f"edit_provider_api_key_{pname}", ""),
                                    "api_format": st.session_state.get(f"edit_provider_api_format_{pname}", "openai"),
                                    "auth_field": st.session_state.get(f"edit_provider_auth_field_{pname}", "Authorization"),
                                }
                                if update_custom_provider(pname, **new_config):
                                    st.success(get_text("provider_added"))
                                    st.session_state[editing_key] = False
                                    st.rerun()
                                else:
                                    st.error(get_text("error"))
                        with btn_cancel:
                            if st.button(get_text("cancel_edit"), key=f"cancel_provider_{pname}", width="stretch"):
                                st.session_state[editing_key] = False
                                st.rerun()
                        with btn_test:
                            if st.button(get_text("test_connection"), key=f"test_provider_{pname}", width="stretch"):
                                test_url = st.session_state.get(f"edit_provider_url_{pname}", "")
                                test_key = st.session_state.get(f"edit_provider_api_key_{pname}", "")
                                test_format = st.session_state.get(f"edit_provider_api_format_{pname}", "openai")
                                with st.spinner(get_text("testing_connection")):
                                    ok, msg = test_provider_connection(test_url, test_key, test_format)
                                    if ok:
                                        st.success(msg)
                                    else:
                                        st.error(msg)
                    else:
                        btn_edit, btn_del, btn_test = st.columns(3, gap="small")
                        with btn_edit:
                            if st.button(get_text("edit_provider"), key=f"edit_provider_{pname}", width="stretch"):
                                pconfig = get_provider_config(pname)
                                if pconfig:
                                    st.session_state[f"edit_provider_url_{pname}"] = pconfig.get("base_url", "")
                                    st.session_state[f"edit_provider_remark_{pname}"] = pconfig.get("remark", "")
                                    st.session_state[f"edit_provider_website_{pname}"] = pconfig.get("website", "")
                                    st.session_state[f"edit_provider_api_key_{pname}"] = pconfig.get("api_key", "")
                                    st.session_state[f"edit_provider_api_format_{pname}"] = pconfig.get("api_format", "openai")
                                    st.session_state[f"edit_provider_auth_field_{pname}"] = pconfig.get("auth_field", "Authorization")
                                st.session_state[editing_key] = True
                                st.rerun()
                        with btn_del:
                            if st.button(get_text("delete_provider"), key=f"delete_provider_{pname}", width="stretch"):
                                if remove_custom_provider(pname):
                                    st.success(get_text("provider_deleted"))
                                    st.rerun()
                        with btn_test:
                            if st.button(get_text("test_connection"), key=f"test_provider_list_{pname}", width="stretch"):
                                with st.spinner(get_text("testing_connection")):
                                    pconfig = get_provider_config(pname)
                                    ok, msg = test_provider_connection(
                                        pconfig.get("base_url", "") if pconfig else provider.get("base_url", ""),
                                        pconfig.get("api_key", "") if pconfig else "",
                                        pconfig.get("api_format", "openai") if pconfig else provider.get("api_format", "openai"),
                                    )
                                    if ok:
                                        st.success(msg)
                                    else:
                                        st.error(msg)

                # 编辑表单（归入容器保持条目分组一致）
                if is_editing:
                    with st.container(gap=None):
                        row1_col1, row1_col2 = st.columns(2)
                        with row1_col1:
                            st.text_input(
                                get_text("provider_name"),
                                key=f"edit_provider_name_{pname}",
                                value=pname,
                                disabled=True,
                            )
                        with row1_col2:
                            st.text_input(
                                get_text("provider_remark"),
                                key=f"edit_provider_remark_{pname}",
                            )

                        st.text_input(
                            get_text("provider_website"),
                            key=f"edit_provider_website_{pname}",
                        )

                        st.text_input(
                            get_text("provider_api_key"),
                            type="password",
                            key=f"edit_provider_api_key_{pname}",
                        )

                        st.text_input(
                            get_text("base_url"),
                            key=f"edit_provider_url_{pname}",
                        )

                        with st.expander(get_text("provider_advanced_options"), expanded=False):
                            st.caption(get_text("provider_advanced_hint"))
                            api_format_options = ["openai", "anthropic", "custom"]
                            st.selectbox(
                                get_text("provider_api_format"),
                                api_format_options,
                                key=f"edit_provider_api_format_{pname}",
                            )
                            st.text_input(
                                get_text("provider_auth_field"),
                                key=f"edit_provider_auth_field_{pname}",
                            )

                # 条目分隔线：标准 st.divider()，由 5c CSS 通过 .st-key-cp_list 容器锚定（4px 紧凑 margin）
                st.divider()

    # ---- 添加新供应商（按钮折叠） ----
    show_add_provider = st.session_state.get("show_add_provider", False)
    if st.button(get_text("add_new_provider"), key="toggle_add_provider"):
        st.session_state["show_add_provider"] = not show_add_provider
        st.rerun()

    if show_add_provider:
        row1_col1, row1_col2 = st.columns(2)
        with row1_col1:
            provider_name = st.text_input(
                get_text("provider_name"),
                key="add_provider_name",
                placeholder=get_text("provider_name_placeholder"),
            )
        with row1_col2:
            provider_remark = st.text_input(
                get_text("provider_remark"),
                key="add_provider_remark",
                placeholder=get_text("provider_remark_placeholder"),
            )

        provider_website = st.text_input(
            get_text("provider_website"),
            key="add_provider_website",
            placeholder=get_text("provider_website_placeholder"),
        )

        provider_api_key = st.text_input(
            get_text("provider_api_key"),
            type="password",
            key="add_provider_api_key",
        )

        provider_url = st.text_input(
            get_text("base_url"),
            key="add_provider_url",
        )
        st.caption(get_text("provider_base_url_hint"))

        with st.expander(get_text("provider_advanced_options"), expanded=False):
            st.caption(get_text("provider_advanced_hint"))
            api_format_options = ["openai", "anthropic", "custom"]
            provider_api_format = st.selectbox(
                get_text("provider_api_format"),
                api_format_options,
                key="add_provider_api_format",
            )
            provider_auth_field = st.text_input(
                get_text("provider_auth_field"),
                key="add_provider_auth_field",
                value="Authorization",
            )

        btn_add, btn_cancel, btn_test = st.columns(3)
        with btn_add:
            if st.button(get_text("add_provider"), type="primary"):
                if provider_name:
                    if add_custom_provider(
                        name=provider_name,
                        base_url=provider_url,
                        remark=provider_remark,
                        website=provider_website,
                        api_key=provider_api_key,
                        api_format=provider_api_format,
                        auth_field=provider_auth_field,
                    ):
                        st.success(get_text("provider_added"))
                        st.rerun()
                    else:
                        st.error(get_text("provider_exists"))
                else:
                    st.error(get_text("fill_fields"))
        with btn_cancel:
            if st.button(get_text("cancel_add"), key="cancel_add_provider"):
                st.session_state["show_add_provider"] = False
                st.rerun()
        with btn_test:
            if st.button(get_text("test_connection"), key="test_new_provider"):
                with st.spinner(get_text("testing_connection")):
                    ok, msg = test_provider_connection(provider_url, provider_api_key, provider_api_format)
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)


def _render_proxy_settings():
    """网络代理设置：自动检测系统代理 + 手动覆盖 + 连接测试"""
    with st.expander(get_text("proxy_settings"), expanded=False):
        try:
            from intelnexus.config.proxy_settings import (
                get_proxy_settings, save_proxy_settings,
                test_proxy_connection, _normalize_proxy_url,
            )
            from intelnexus.ui._caches import cached_system_proxy
        except Exception as e:
            logger.warning(f"代理设置模块不可用: {e}")
            return

        current = get_proxy_settings()
        source_labels = {
            "manual": get_text("proxy_source_manual"),
            "system": get_text("proxy_source_system"),
            "env": get_text("proxy_source_env"),
            "none": get_text("proxy_source_none"),
        }
        source_label = source_labels.get(current["source"], current["source"])
        current_url = current.get("proxy_url", "")

        # 当前状态展示
        if current_url:
            st.caption(f"{get_text('proxy_current_source')}: **{source_label}** — `{current_url}`")
        else:
            st.caption(f"{get_text('proxy_current_source')}: **{source_label}**")

        # 自动检测开关
        auto_detect = st.checkbox(
            get_text("proxy_auto_detect"),
            value=current.get("auto_detect", True),
            help=get_text("proxy_auto_detect_hint"),
            key="proxy_auto_detect_cb",
        )

        # 系统代理实时检测值（只读展示，走缓存 ttl=60 避免每次重探）
        sys_proxy = cached_system_proxy()
        if sys_proxy:
            st.markdown(
                f"<div class='stCaption'>{icon('search', size='sm', color='gray')} "
                f"{get_text('proxy_source_system')}: <code>{sys_proxy}</code></div>",
                unsafe_allow_html=True,
            )

        # 手动输入
        manual_url = st.text_input(
            get_text("proxy_manual_url"),
            value="" if current["source"] != "manual" else current_url,
            placeholder=get_text("proxy_manual_placeholder"),
            key="proxy_manual_input",
        )
        st.caption(get_text("proxy_manual_hint"))

        # 操作按钮
        col_save, col_test, col_clear = st.columns([1, 1, 1])
        with col_save:
            if st.button(get_text("proxy_save_btn"), key="proxy_save_btn"):
                save_proxy_settings({
                    "proxy_url": manual_url.strip(),
                    "auto_detect": auto_detect,
                })
                st.success(get_text("proxy_saved"))
                st.rerun()
        with col_test:
            test_url = _normalize_proxy_url(manual_url.strip()) if manual_url.strip() else current_url
            if st.button(get_text("proxy_test_btn"), key="proxy_test_btn"):
                if test_url:
                    with st.spinner(get_text("proxy_testing")):
                        ok, msg = test_proxy_connection(test_url)
                    if ok:
                        st.success(f"{get_text('proxy_test_ok')}: {msg}")
                    else:
                        st.error(f"{get_text('proxy_test_fail')}: {msg}")
                else:
                    st.warning(get_text("proxy_source_none"))
        with col_clear:
            if st.button(get_text("proxy_clear_btn"), key="proxy_clear_btn"):
                save_proxy_settings({"proxy_url": "", "auto_detect": auto_detect})
                st.info(get_text("proxy_cleared"))
                st.rerun()


def _render_task_status_indicator():
    """侧边栏后台任务状态指示器。

    搜索或简报任务运行期间显示可见的进度信息，
    让用户知道后台有任务在运行（即使他们已切换到其他 Tab）。
    无任务时不渲染任何内容。
    """
    try:
        from intelnexus.core.task_runner import get_task_runner
        runner = get_task_runner()
    except ImportError:
        return

    search_state = runner.get_snapshot("search")
    briefing_state = runner.get_snapshot("briefing")

    tasks = []
    if search_state["status"] == "running":
        tasks.append(("search", search_state))
    if briefing_state["status"] == "running":
        tasks.append(("briefing", briefing_state))

    if not tasks:
        return

    for task_id, state in tasks:
        phase = state.get("phase", "")
        message = state.get("message", "")
        progress = state.get("progress", 0.0)
        task_label = get_text(f"task_{task_id}_running")
        st.markdown(
            f'<div style="background:var(--bg-card, #f5f5f5);border-radius:6px;'
            f'padding:8px 12px;margin-bottom:8px;border-left:3px solid var(--accent-blue, #4a90d9);">'
            f'<div style="font-size:12px;color:var(--wb-text-secondary,#666);">{task_label}</div>'
            f'<div style="font-size:13px;font-weight:500;margin-top:2px;">{message}</div>'
            f'<div style="background:#e0e0e0;border-radius:3px;height:4px;margin-top:4px;">'
            f'<div style="background:var(--accent-blue, #4a90d9);height:100%;border-radius:3px;'
            f'width:{int(progress*100)}%;transition:width 0.3s;"></div></div></div>',
            unsafe_allow_html=True,
        )


def _render_authorization_settings():
    """授权声明设置（P0-3 授权闸门的用户入口）。

    针对具名实体的「漏洞/渗透/攻击面」类查询需要显式声明授权；
    未声明时系统降级为纯 OSINT 并禁用攻击面章节。控件写入
    session_state（key: authorization_declared / authorization_scope），
    由 ``search_pipeline._start_search_task`` 读取并传入闸门。
    """
    declared = st.checkbox(
        get_text("authorization_declared"),
        help=get_text("authorization_declared_help"),
        key="authorization_declared",
    )
    if declared:
        st.text_area(
            get_text("authorization_scope"),
            help=get_text("authorization_scope_help"),
            key="authorization_scope",
            height=68,
        )


def render_sidebar():
    """
    Sidebar: cold-gray workbench style.

    Structure:
      Brand → Task Status → Search Mode → Model → [Advanced Settings]

    简报业务（数据源/订阅者/生成）已收拢至简报 Tab，侧边栏仅保留全局设置。
    """
    with st.sidebar:
        # Brand
        st.markdown(f'<div class="sidebar-title">{get_text("title")}</div>', unsafe_allow_html=True)

        # 后台任务状态指示器（搜索/简报运行期间显示进度）
        _render_task_status_indicator()

        # Core: Search Mode
        search_mode = _render_search_mode()

        # Authorization declaration (合规闸门入口)
        _render_authorization_settings()

        # Source Health Panel
        _render_source_health()

        # Search service settings (NewsAPI key)
        _render_search_service_settings()

        # Network proxy settings
        _render_proxy_settings()

        # Core: Model Settings
        model = _render_model_settings()

        # Advanced: Threads, Language, Custom Models
        threads = _render_advanced_settings()

        # 底部：使用帮助按钮（常驻，任何页面可点击打开帮助弹窗）
        st.divider()
        from intelnexus.ui.help_dialog import render_sidebar_help_button
        render_sidebar_help_button()

    return search_mode, model, threads
