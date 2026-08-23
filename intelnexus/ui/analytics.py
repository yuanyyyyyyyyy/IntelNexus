"""
分析仪表盘模块
==============
显示反馈统计、推送成功率、简报生成趋势等运营数据。
放置在简报Tab设置区域内。

P2 重构要点：
- 时间范围筛选（7/30 天），与反馈数据 30 天滚动窗口配套
- 推送成功率 + 渠道失败明细（数据源：push_log.json，此前失败只进日志不可见）
- 简报生成趋势（按日计数，数据源：briefing_history.json）
- 「活跃用户」改为「参与人数」（去重身份计数，修复原恒为 1 的失真指标）
"""
from datetime import datetime, timedelta

import streamlit as st

from intelnexus.ui.i18n import get_text
from intelnexus.ui.icons import icon, category_icon


def _gen_trend_bars(history: list, days: int) -> dict:
    """按日统计最近 N 天的简报生成次数，返回 {日期: 次数}（按日期升序）。"""
    cutoff = (datetime.now() - timedelta(days=days)).date().isoformat()
    per_day = {}
    for h in history:
        created = h.get("created_at", "") or ""
        day = created[:10]
        if day and day >= cutoff:
            per_day[day] = per_day.get(day, 0) + 1
    return dict(sorted(per_day.items()))


def render_analytics_dashboard():
    """渲染分析仪表盘"""
    from intelnexus.config.feedback import (
        get_feedback_stats,
        get_top_categories,
        get_recent_feedback_with_names,
        get_all_users_behavior,
    )
    from intelnexus.config.push_log import get_push_stats
    from intelnexus.config.briefing_history import get_briefing_history
    from intelnexus.core.ui.styles import render_workbench_css

    render_workbench_css()

    st.markdown(
        '<div class="bf-panel bf-panel--gen">'
        f'<div class="bf-label"><span class="bf-label__tag">STATS</span>'
        f'<span class="bf-label__title">{icon("chart", "sm", "blue")} {get_text("analytics_dashboard")}</span></div>',
        unsafe_allow_html=True,
    )

    # ---- 时间范围筛选 ----
    days = st.radio(
        get_text("analytics_period"),
        options=[7, 30],
        format_func=lambda d: get_text("analytics_period_days").format(n=d),
        horizontal=True,
        key="bf_analytics_days",
    )

    stats = get_feedback_stats()
    push_stats = get_push_stats(days)

    # ---- 第一行：反馈概览 ----
    total_up = stats["briefing"]["total_up"]
    total_down = stats["briefing"]["total_down"]
    up_ratio = total_up / (total_up + total_down) if (total_up + total_down) > 0 else 0.5
    # 参与人数：按去重身份计数（排除遗留的 anonymous 键）
    try:
        behavior_keys = set(get_all_users_behavior().keys()) - {"anonymous"}
        participants = len(behavior_keys)
    except Exception:
        participants = 0

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(get_text("total_feedback"), stats["users"]["total_feedback"])
    with col2:
        st.metric(get_text("up_ratio"), f"{up_ratio:.0%}")
    with col3:
        st.metric(get_text("active_participants"), participants)
    with col4:
        st.metric(get_text("thumbsup"), total_up)

    st.markdown("<br>", unsafe_allow_html=True)

    # ---- 第二行：推送成功率 ----
    st.markdown(f"**{get_text('push_success_rate')}**")
    if push_stats["total_sends"] > 0:
        c1, c2, c3 = st.columns([2, 1, 2])
        with c1:
            rate = push_stats["success_rate"] or 0.0
            st.metric(
                f"{push_stats['success_sends']}/{push_stats['total_sends']}",
                f"{rate:.0%}",
            )
            st.progress(rate)
        with c3:
            fails = push_stats.get("channel_failures") or {}
            if fails:
                fail_text = " · ".join(f"{k}: {v}" for k, v in fails.items())
                st.markdown(f":material/error: {get_text('channel_failures')}: {fail_text}")
            else:
                st.success(get_text("no_channel_failures"))
        recent_fails = push_stats.get("recent_failures") or []
        if recent_fails:
            with st.expander(get_text("recent_push_failures"), expanded=False):
                for f in recent_fails:
                    failed_ch = [k for k, v in (f.get("channels") or {}).items() if v is False]
                    st.caption(
                        f"• {f.get('timestamp', '')[:16]}  {f.get('subscriber_id', '?')}  "
                        f"[{', '.join(failed_ch)}]"
                    )
    else:
        st.info(get_text("no_push_data"))

    st.markdown("<br>", unsafe_allow_html=True)

    # ---- 第三行：简报生成趋势 ----
    st.markdown(f"**{get_text('gen_trend')}**")
    trend = _gen_trend_bars(get_briefing_history().get_briefings(limit=100), days)
    if trend:
        max_n = max(trend.values())
        for day, n in trend.items():
            bar = "█" * max(1, round(n / max_n * 20))
            st.caption(f"`{day}` {bar} {n}")
    else:
        st.info(get_text("gen_trend_empty"))

    st.markdown("<br>", unsafe_allow_html=True)

    # ---- 第四行：最受欢迎分类 ----
    top_cats = get_top_categories(5)
    if top_cats:
        st.markdown(f"**{get_text('top_categories')}**")
        for cat in top_cats:
            score = cat.get("score", 0.5)
            up = cat.get("up", 0)
            down = cat.get("down", 0)
            cat_display = _get_category_display_name(cat["category"])
            st.markdown(
                f"{category_icon(cat['category'], 'sm')} {cat_display}: "
                f"{icon('thumbsup', 'sm', 'sage')}{up} {icon('thumbsdown', 'sm', 'error')}{down}",
                unsafe_allow_html=True,
            )
            st.progress(score)
    else:
        st.info(get_text("no_feedback"))

    st.markdown("<br>", unsafe_allow_html=True)

    # ---- 第五行：最近反馈 ----
    recent = get_recent_feedback_with_names(5)
    if recent:
        st.markdown(f"**{get_text('recent_feedback')}**")
        for entry in recent:
            if entry.get("feedback") == "up":
                feedback_icon = icon('thumbsup', 'sm', 'sage')
            else:
                feedback_icon = icon('thumbsdown', 'sm', 'error')
            url = entry.get("url", "")[:50]
            name = entry.get("subscriber_name", "匿名")
            ts = entry.get("timestamp", "")[:16]
            st.markdown(f"{feedback_icon} [{url}...] - {name} · {ts}", unsafe_allow_html=True)
    else:
        st.info(get_text("no_feedback"))

    st.markdown('</div>', unsafe_allow_html=True)


def _get_category_display_name(category: str) -> str:
    """获取分类的显示名称（动态：关注点配置优先——含用户自定义；回退内置映射）"""
    try:
        from intelnexus.briefing.config import get_all_categories
        cfg = get_all_categories().get(category)
        if cfg and cfg.get("name"):
            return cfg["name"]
    except Exception:
        pass
    category_names = {
        "ai_gov_usage": "美欧机构AI应用",
        "ai_china_narrative": "涉我AI舆论",
        "ai_legislation": "AI新法案",
        "ai_data_leak": "AI数据泄露",
        "cyber_vuln": "网络安全漏洞",
        "cyber_attack": "网络攻击事件",
    }
    return category_names.get(category, category)
