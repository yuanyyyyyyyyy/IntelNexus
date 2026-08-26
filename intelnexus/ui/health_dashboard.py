"""
数据源健康检查概览面板
======================
简报中心设置区第 5 个 radio 面板，三层结构：

- 聚合层：3 张 st.metric 卡（正常/降级/异常），数据取自
  get_health_summary_cached() —— 与状态栏、侧边栏摘要共享单一口径；
- 明细层：先取活跃源名 purge 僵尸条目，再遍历 get_all_health()，
  按严重度排序（down → degraded → healthy）逐源渲染；
- 操作层：「刷新检查」仅失效缓存并 rerun（绝不发起网络探测）；
  降级/异常源行内「重置」按钮复用 h.reset() + save_health(h) 模式。

卡片视觉沿用 bf-panel 语言（浅色底 + 左侧 4px 色条），
.hc-card 样式见 core/ui/styles.py render_workbench_css 末尾段。
"""

import html

import streamlit as st

from intelnexus.core.logger import get_logger
from intelnexus.ui.i18n import get_text

logger = get_logger(__name__)

# 明细排序：问题越严重越靠前
_SEVERITY_ORDER = {"down": 0, "degraded": 1, "healthy": 2}

# 状态 → 既有 status-dot 修饰类
_STATUS_DOT_CLASS = {
    "healthy": "active",
    "degraded": "warning",
    "down": "error",
}


def render_health_overview():
    """渲染数据源健康检查概览面板（只读展示 + 缓存失效/单条重置两类轻量操作）"""
    from intelnexus.ui.status_metrics import (
        get_health_summary_cached, invalidate_status_metrics)

    st.markdown(f'''
    <div class="bf-panel bf-panel--source">
        <div class="bf-label">
            <span class="bf-label__tag">{get_text("health_panel_tag")}</span>
            <span class="bf-label__title">{get_text("health_panel_title")}</span>
        </div>
    ''', unsafe_allow_html=True)

    # ---- 操作层：刷新检查（只失效缓存 + rerun，严禁发起任何网络探测）----
    if st.button(get_text("health_refresh"), key="hc_refresh_check"):
        invalidate_status_metrics()
        st.rerun()

    # ---- 聚合层：3 张指标卡（共享口径 get_health_summary_cached）----
    try:
        summary = get_health_summary_cached() or {}
    except Exception:
        summary = {}
    cards = [
        ("hc-card--healthy", "health_card_healthy", summary.get("healthy", 0)),
        ("hc-card--degraded", "health_card_degraded", summary.get("degraded", 0)),
        ("hc-card--down", "health_card_down", summary.get("down", 0)),
    ]
    cols = st.columns(3)
    for col, (cls, label_key, value) in zip(cols, cards):
        with col:
            st.markdown(f'<div class="hc-card {cls}">', unsafe_allow_html=True)
            st.metric(get_text(label_key), value)
            st.markdown('</div>', unsafe_allow_html=True)

    # ---- 明细层：先清僵尸条目（面板内合法写操作点），再读健康表 ----
    try:
        from intelnexus.core.search.health import (
            get_all_health, save_health, purge_stale_entries)
        from intelnexus.core.search.registry import get_registry
        from intelnexus.config.search_settings import get_news_api_key
        active_names = [s.name for s in get_registry(
            news_api_key=get_news_api_key()).all_sources()]
        purge_stale_entries(active_names)
        all_health = get_all_health()
    except Exception:
        all_health = None
        active_names = None

    if not all_health:
        st.markdown(
            f"<p class='bf-hint'>{get_text('health_empty')}</p>",
            unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        return

    ordered = sorted(
        all_health,
        key=lambda h: _SEVERITY_ORDER.get(getattr(h, "status", ""), 3))

    for h in ordered:
        # 白名单校验：注册表不存在的源名（异常写入/残留）不渲染，只记日志。
        # 注：active_names 为 None（注册表构建失败）时跳过校验，避免静默整个面板。
        if active_names is not None and h.source_name not in active_names:
            logger.warning(
                f"health dashboard: skipping entry for unknown source "
                f"{h.source_name!r} (not in active registry)")
            continue
        dot_cls = _STATUS_DOT_CLASS.get(h.status, "error")
        dot = f'<span class="status-dot {dot_cls}"></span>'
        rate = f"{h.success_rate:.0%}"
        latency = f"{h.avg_latency_ms:.0f}ms" if h.avg_latency_ms > 0 else "-"

        col_name, col_stat, col_rate, col_latency, col_action = st.columns([3, 1, 1, 1, 1])
        with col_name:
            # source_name 用户可控（自定义源名），拼入 HTML 前必须转义防 XSS
            st.markdown(f"{dot} **{html.escape(h.source_name)}**", unsafe_allow_html=True)
            if h.last_error:
                st.caption(h.last_error[:80])
        with col_stat:
            st.caption(get_text(f"source_{h.status}"))
        with col_rate:
            st.caption(rate)
        with col_latency:
            st.caption(latency)
        with col_action:
            if h.status in ("degraded", "down"):
                if st.button(get_text("source_reset"), key=f"hc_reset_{h.source_name}"):
                    h.reset()
                    save_health(h)
                    invalidate_status_metrics()
                    st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)
