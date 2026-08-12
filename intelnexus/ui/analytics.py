"""
分析仪表盘模块
==============
显示反馈统计、用户活跃度、最受欢迎分类等数据
放置在简报Tab设置区域内
"""
import streamlit as st
from intelnexus.ui.i18n import get_text
from intelnexus.ui.icons import icon, category_icon


def render_analytics_dashboard():
    """渲染分析仪表盘"""
    from intelnexus.config.feedback import (
        get_feedback_stats,
        get_top_categories,
        get_recent_feedback_with_names,
    )
    from intelnexus.core.ui.styles import render_workbench_css
    
    # 注入样式
    render_workbench_css()
    
    st.markdown(
        '<div class="bf-panel bf-panel--gen">'
        f'<div class="bf-label"><span class="bf-label__tag">STATS</span>'
        f'<span class="bf-label__title">{icon("chart", "sm", "blue")} {get_text("analytics_dashboard")}</span></div>',
        unsafe_allow_html=True,
    )
    
    # 获取统计数据
    stats = get_feedback_stats()
    
    # 反馈概览卡片
    total_feedback = stats["users"]["total_feedback"]
    total_up = stats["briefing"]["total_up"]
    total_down = stats["briefing"]["total_down"]
    up_ratio = total_up / (total_up + total_down) if (total_up + total_down) > 0 else 0.5
    active_users = stats["users"]["count"]
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(get_text("total_feedback"), total_feedback)
    with col2:
        st.metric(get_text("up_ratio"), f"{up_ratio:.0%}")
    with col3:
        st.metric(get_text("active_users"), active_users)
    with col4:
        st.metric(get_text("thumbsup"), total_up)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # 最受欢迎分类
    top_cats = get_top_categories(5)
    if top_cats:
        st.markdown(f"**{get_text('top_categories')}**")
        for cat in top_cats:
            score = cat.get("score", 0.5)
            up = cat.get("up", 0)
            down = cat.get("down", 0)
            # 显示分类名称和进度条
            cat_display = _get_category_display_name(cat["category"])
            st.markdown(f"{category_icon(cat['category'], 'sm')} {cat_display}: {icon('thumbsup', 'sm', 'sage')}{up} {icon('thumbsdown', 'sm', 'error')}{down}", unsafe_allow_html=True)
            st.progress(score)
    else:
        st.info(get_text("no_feedback"))
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # 最近反馈条目
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
            st.markdown(f"{feedback_icon} [{url}...] - {name}", unsafe_allow_html=True)
    else:
        st.info(get_text("no_feedback"))
    
    st.markdown('</div>', unsafe_allow_html=True)


def _get_category_display_name(category: str) -> str:
    """获取分类的显示名称"""
    category_names = {
        "ai_gov_usage": "美欧机构AI应用",
        "ai_china_narrative": "涉我AI舆论",
        "ai_legislation": "AI新法案",
        "ai_data_leak": "AI数据泄露",
        "cyber_vuln": "网络安全漏洞",
        "cyber_attack": "网络攻击事件",
    }
    return category_names.get(category, category)
