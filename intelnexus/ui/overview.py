"""
今日概览首页（Home / Overview）
===============================
主导航横向 radio 的默认页：问候区 + 三张运行指标卡 + 两个主操作入口。

设计原则：
- 零数据依赖的静态部分（问候语骨架）先行渲染，数据部分任何异常
  都降级为文案展示，绝不让首页白屏；
- 指标一律走 intelnexus/ui/status_metrics 聚合层（15s 缓存 + 全兜底），
  与底部状态栏共用同一口径；
- 视觉沿用浅色纸白主题：卡片复用 .hc-card 语言（见 render_workbench_css），
  首页专属样式挂在 styles.py 的 ov-scope 段（:has() 作用域）。
"""

import html
from datetime import datetime

import streamlit as st

from intelnexus.ui.i18n import get_text
from intelnexus.ui import main_tabs


# ---------------------------------------------------------------------------
# 时段问候
# ---------------------------------------------------------------------------

def _hour_segment(hour: int) -> str:
    """按时段分段：5-11 早 / 12-17 午 / 其余（18-4）晚。"""
    if 5 <= hour <= 11:
        return "morning"
    if 12 <= hour <= 17:
        return "afternoon"
    return "evening"


def _render_greeting(segment: str, briefings_today: "int | None") -> None:
    """问候区：大标题（静态时段问候）+ 情感化副文案（拼接简报状态）。

    briefings_today 为 None 表示数据读取失败，副文案退化为中性文案。
    """
    st.markdown(
        f'<div class="main-title">{html.escape(get_text(f"ov_greet_{segment}"))}</div>',
        unsafe_allow_html=True,
    )
    try:
        date_str = datetime.now().strftime("%Y-%m-%d")
    except Exception:
        date_str = ""

    if briefings_today is None:
        line_key = "ov_greet_fallback"
    elif briefings_today > 0:
        line_key = f"ov_greet_{segment}_ready"
    else:
        line_key = f"ov_greet_{segment}_pending"
    line = get_text(line_key)
    date_part = f'<span class="ov-date">{date_str}</span>' if date_str else ""
    st.markdown(
        f'<div class="ov-tagline">{html.escape(line)}{date_part}</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# 指标采集（聚合层已兜底，这里再包一层防导入级异常）
# ---------------------------------------------------------------------------

def _collect_metrics() -> "dict | None":
    try:
        from intelnexus.ui.status_metrics import (
            get_health_summary_cached,
            get_scheduler_summary_cached,
            get_today_stats_cached,
        )
        return {
            "health": get_health_summary_cached(),
            "scheduler": get_scheduler_summary_cached(),
            "today": get_today_stats_cached(),
        }
    except Exception:
        return None


def _fmt_briefing_time(created_at: str) -> str:
    """created_at（ISO 串）→ 'HH:MM'；解析失败原样截短返回。"""
    try:
        return datetime.fromisoformat(created_at).strftime("%H:%M")
    except Exception:
        return (created_at or "")[:16]


# ---------------------------------------------------------------------------
# 三张指标卡
# ---------------------------------------------------------------------------

def _render_metric_cards(metrics: "dict | None") -> None:
    health = (metrics or {}).get("health") or {"healthy": 0, "degraded": 0, "down": 0, "total": 0}
    sched = (metrics or {}).get("scheduler") or {"running": False, "job_count": 0, "next_run_str": None}
    today = (metrics or {}).get("today") or {
        "briefings_today": 0, "pushes_today": 0, "searches_today": 0, "last_briefing": None,
    }

    # ---- 卡1：今日简报 ----
    if today.get("briefings_today", 0) > 0:
        last = today.get("last_briefing") or {}
        title = last.get("title") or get_text("untitled")
        value = html.escape(title)
        sub_bits = []
        when = _fmt_briefing_time(last.get("created_at") or "")
        if when:
            sub_bits.append(when)
        sub_bits.append(get_text("ov_briefing_count").format(n=today.get("briefings_today", 0)))
        sub = " · ".join(sub_bits)
        card_cls = "hc-card ov-card hc-card--healthy"
    else:
        value = get_text("ov_briefing_none")
        sub = ""
        card_cls = "hc-card ov-card"

    briefing_card = (
        f'<div class="{card_cls}">'
        f'<div class="ov-card__tag">{html.escape(get_text("ov_card_briefing"))}</div>'
        f'<div class="ov-card__value">{value}</div>'
        + (f'<div class="ov-card__sub">{html.escape(sub)}</div>' if sub else "")
        + "</div>"
    )

    # ---- 卡2：调度器（口径与状态栏一致） ----
    if sched.get("running") and sched.get("job_count", 0) > 0:
        sched_value = get_text("ov_sched_next").format(
            when=sched.get("next_run_str") or "--",
            n=sched.get("job_count", 0),
        )
        sched_cls = "hc-card ov-card hc-card--healthy"
    elif sched.get("running"):
        sched_value = get_text("sb_scheduler_idle")
        sched_cls = "hc-card ov-card hc-card--degraded"
    else:
        sched_value = get_text("sb_manual_mode")
        sched_cls = "hc-card ov-card"

    scheduler_card = (
        f'<div class="{sched_cls}">'
        f'<div class="ov-card__tag">{html.escape(get_text("ov_card_scheduler"))}</div>'
        f'<div class="ov-card__value">{html.escape(sched_value)}</div>'
        + f'<div class="ov-card__sub">{html.escape(get_text("ov_sched_sub"))}</div>'
        + "</div>"
    )

    # ---- 卡3：数据源健康 ----
    healthy = int(health.get("healthy", 0) or 0)
    degraded = int(health.get("degraded", 0) or 0)
    down = int(health.get("down", 0) or 0)
    total = int(health.get("total", 0) or 0)

    if total == 0:
        health_value = get_text("ov_health_empty")
        health_cls = "hc-card ov-card"
    else:
        health_value = get_text("health_summary_line").format(
            healthy=healthy, degraded=degraded, down=down)
        if down > 0:
            health_cls = "hc-card ov-card hc-card--down"
        elif degraded > 0:
            health_cls = "hc-card ov-card hc-card--degraded"
        else:
            health_cls = "hc-card ov-card hc-card--healthy"

    health_card = (
        f'<div class="{health_cls}">'
        f'<div class="ov-card__tag">{html.escape(get_text("ov_card_health"))}</div>'
        f'<div class="ov-card__value">{html.escape(health_value)}</div>'
        + f'<div class="ov-card__sub">{html.escape(get_text("ov_health_sub").format(total=total))}</div>'
        + "</div>"
    )

    cols = st.columns(3)
    for col, card in zip(cols, (briefing_card, scheduler_card, health_card)):
        with col:
            st.markdown(card, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# 主操作入口
# ---------------------------------------------------------------------------

def _render_action_buttons() -> None:
    """「情报搜索」「生成简报」两个主入口：白底蓝字影（样式见 ov-scope 段）。

    点击经 request_tab 写一次性跳转旗标后 rerun，导航即切到目标页。
    """
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button(get_text("ov_btn_search"), key="ov_btn_search",
                     use_container_width=True):
            main_tabs.request_tab(st.session_state, main_tabs.TAB_SEARCH)
            st.rerun()
    with col_b:
        if st.button(get_text("ov_btn_briefing"), key="ov_btn_briefing",
                     use_container_width=True):
            main_tabs.request_tab(st.session_state, main_tabs.TAB_BRIEFING)
            st.rerun()


# ---------------------------------------------------------------------------
# 页面入口
# ---------------------------------------------------------------------------

def render_overview() -> None:
    """今日概览首页：问候区 → 指标卡片区 → 主操作入口。"""
    # 隐藏 marker：供 styles.py 以 :has(.ov-scope) 作用域挂载首页专属 CSS
    st.markdown('<div class="ov-scope" style="display:none"></div>', unsafe_allow_html=True)

    segment = _hour_segment(datetime.now().hour)

    # 数据部分整体兜底：任何异常只降级文案，不影响问候区与按钮
    try:
        metrics = _collect_metrics()
        briefings_today = (metrics or {}).get("today", {}).get("briefings_today", 0) \
            if metrics else None
    except Exception:
        metrics = None
        briefings_today = None

    # ---- 问候区 ----
    _render_greeting(segment, briefings_today)

    # ---- 指标卡片区 ----
    try:
        _render_metric_cards(metrics)
    except Exception:
        st.markdown(get_text("ov_greet_fallback"))

    # ---- 主操作入口 ----
    _render_action_buttons()
