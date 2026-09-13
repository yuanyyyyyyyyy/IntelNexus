"""UI 层缓存包装层
=================
把「跨 rerun 不变」的重型只读调用集中包进 Streamlit 缓存，避免每次切换 Tab
（＝整脚本重跑）都重复发起网络/磁盘探测。core 层函数保持 Streamlit 无关，
此处仅在 UI 渲染链路内包装，确保始终处于 Streamlit 脚本运行上下文。

- 网络/慢调用用 @st.cache_data(ttl=...) 按 TTL 复用结果；
- 非可序列化资源（搜索源注册表）用 @st.cache_resource 复用对象实例。
- 写操作（增删自定义模型、改源开关、改 NewsAPI key）成功后调用对应 .clear()，
  既不掩盖更新，又避免每帧重探。

只包装「读」，绝不在此做写操作（写副作用沿用 status_metrics.invalidate_status_metrics）。
"""

import streamlit as st


@st.cache_data(ttl=30, show_spinner=False)
def cached_model_choices() -> list:
    """模型下拉选项（含 Ollama 探测）：按 TTL 复用，消除每次切 Tab 的 HTTP 探测。"""
    from intelnexus.core.llm.utils import get_model_choices
    return get_model_choices()


@st.cache_data(ttl=15, show_spinner=False)
def cached_tor_state() -> tuple:
    """返回 (tor_port, tor_running)：探测 Tor SOCKS 端口，按 TTL 复用。"""
    from intelnexus.core.ui.helpers import find_tor_port
    port = find_tor_port()
    return port, port is not None


@st.cache_data(ttl=60, show_spinner=False)
def cached_system_proxy() -> str:
    """系统代理探测（读 Windows 注册表）：按 TTL 复用。"""
    from intelnexus.config.proxy_settings import detect_system_proxy
    return detect_system_proxy()


@st.cache_data(ttl=15, show_spinner=False)
def cached_all_health() -> list:
    """数据源健康表（只读）：与运行指标 15s 口径一致。"""
    from intelnexus.core.search.health import get_all_health
    return get_all_health()


@st.cache_resource(show_spinner=False)
def cached_registry(news_api_key=None) -> object:
    """搜索源注册表单例：按构造参数复用对象实例（非可序列化，用 cache_resource）。"""
    from intelnexus.core.search.registry import get_registry
    return get_registry(news_api_key=news_api_key)


def warm_ui_caches() -> None:
    """首屏一次性预热所有重型只读缓存，避免渲染期被网络/磁盘探测穿插导致逐段显现。

    必须在 Streamlit 脚本运行上下文中、发出**任何可见控件之前**调用：
    重型工作集中在此（浏览器停在「连接中」态），之后所有控件在几十毫秒内连发，
    浏览器一次性呈现。后续切 Tab 命中热缓存，warmup 仅剩函数调用+查缓存开销，近乎零成本。

    注意：cached_registry 有「无参」与「带 NewsAPI key 参」两种缓存键，需都预热。
    底部状态栏三个 get_*_cached() 故意不在此预热（见函数末尾注释）：它们是 15s 缓存、
    含较重读取，放到脚本最前会阻塞切 Tab，而作为页脚在末尾按需计算本就不影响主界面呈现。
    """
    # 模型下拉（含 Ollama HTTP 探测）
    try:
        cached_model_choices()
    except Exception:
        pass
    # Tor SOCKS 端口探测
    try:
        cached_tor_state()
    except Exception:
        pass
    # 系统代理探测（读注册表）
    try:
        cached_system_proxy()
    except Exception:
        pass
    # 搜索源注册表：两种缓存键都预热
    try:
        cached_registry()
    except Exception:
        pass
    try:
        from intelnexus.config.search_settings import get_news_api_key
        cached_registry(news_api_key=get_news_api_key())
    except Exception:
        pass
    # 数据源健康表
    try:
        cached_all_health()
    except Exception:
        pass
    # 注意：底部状态栏三个 get_*_cached() 故意不在此预热。它们是 15s 缓存、含
    # 简报/推送/搜索历史与调度器状态读取，并不轻量；原本在脚本最末尾 render_status_bar
    # 才计算，主界面早已显示、状态栏"晚半秒补上"无感。若在此预热，一旦 15s 缓存过期，
    # 重型计算会卡在脚本最顶端阻塞侧边栏+主区输出，导致切 Tab 变慢。状态栏是页脚，
    # 最后算、最后画本就不会造成主界面逐段显现，故保持末尾按需计算即可。
