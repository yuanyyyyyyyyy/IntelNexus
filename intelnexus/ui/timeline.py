"""
知识演进时间线UI
================
可视化用户的知识演进历程
"""
import streamlit as st
from typing import Dict, List
from intelnexus.ui.i18n import get_text
from intelnexus.ui.icons import icon


def render_timeline():
    """渲染知识演进时间线"""
    from intelnexus.config.feedback import get_user_behavior
    from intelnexus.config.knowledge_base import get_items
    from intelnexus.config.briefing_history import get_briefing_history
    
    # 获取用户行为数据
    behavior = get_user_behavior()
    clicks = behavior.get("clicks", [])
    
    # 获取知识库条目
    kb_items = get_items(limit=100)
    
    # 获取简报历史
    history = get_briefing_history().get_briefings(limit=50)
    
    # 按天聚合事件
    daily_events = {}
    
    # 添加点击事件
    for click in clicks:
        date = click.get("timestamp", "")[:10]
        if date:
            if date not in daily_events:
                daily_events[date] = []
            
            if click.get("source") == "briefing":
                click_icon = icon('briefing', 'sm', 'gray')
            else:
                click_icon = icon('search', 'sm', 'blue')
            
            daily_events[date].append({
                "type": "click",
                "icon": click_icon,
                "title": click.get("url", "")[:50],
                "detail": f"来源: {click.get('source', 'unknown')}"
            })
    
    # 添加知识库条目
    for item in kb_items:
        date = item.get("created_at", "")[:10]
        if date:
            if date not in daily_events:
                daily_events[date] = []
            
            type_icons = {
                "briefing_entry": ("entry", "gray"),
                "search_result": ("result", "blue"),
                "note": ("note", "lavender")
            }
            icon_name, icon_color = type_icons.get(item.get("type", ""), ("entry", "gray"))
            
            daily_events[date].append({
                "type": "kb_item",
                "icon": icon(icon_name, 'sm', icon_color),
                "title": item.get("title", "")[:50],
                "detail": f"类型: {item.get('type', 'unknown')}"
            })
    
    # 渲染时间线
    if not daily_events:
        st.info(get_text("no_recommendations"))
        return
    
    # 按日期倒序排列
    sorted_dates = sorted(daily_events.keys(), reverse=True)[:7]  # 最近7天
    
    for date in sorted_dates:
        events = daily_events[date]
        st.markdown(f"**{icon('trend', 'sm', 'blue')} {date}**", unsafe_allow_html=True)
        
        for event in events:
            st.markdown(f"  {event['icon']} {event['title']}...", unsafe_allow_html=True)
            st.caption(f"    {event['detail']}")
        
        st.markdown("")  # 空行分隔


def render_timeline_sidebar():
    """在侧边栏渲染时间线入口"""
    from intelnexus.config.feedback import get_user_behavior
    
    behavior = get_user_behavior()
    click_count = len(behavior.get("clicks", []))
    
    st.markdown(
        f'<div class="sb-section"><span class="sb-section__label">Activity</span></div>',
        unsafe_allow_html=True
    )
    
    if st.button(
        f"{get_text('timeline')} ({click_count})",
        key="nav_timeline",
        use_container_width=True
    ):
        st.session_state.show_timeline = True
        st.rerun()
