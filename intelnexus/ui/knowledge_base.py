"""
知识库UI模块
============
显示用户收藏的简报条目、搜索结果和笔记
"""
import html

import streamlit as st
from typing import List, Optional
from intelnexus.ui.i18n import get_text
from intelnexus.ui.icons import icon


def render_knowledge_base():
    """渲染知识库主界面"""
    from intelnexus.config.knowledge_base import get_items, get_tags, get_stats, add_item, add_tag
    
    # 注入样式
    
    # 统计信息
    stats = get_stats()
    
    st.markdown(
        '<div class="bf-panel bf-panel--gen">'
        f'<div class="bf-label"><span class="bf-label__tag">KB</span>'
        f'<span class="bf-label__title">{get_text("knowledge_base")}</span></div>',
        unsafe_allow_html=True,
    )
    
    # 统计卡片
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(get_text("kb_stat_total"), stats["total"])
    with col2:
        st.metric(get_text("kb_briefing"), stats["by_type"].get("briefing_entry", 0))
    with col3:
        st.metric(get_text("kb_search"), stats["by_type"].get("search_result", 0))
    with col4:
        st.metric(get_text("kb_note"), stats["by_type"].get("note", 0))
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # 筛选栏
    col_filter1, col_filter2, col_filter3 = st.columns([2, 2, 1])
    with col_filter1:
        # value = type ID (translation only for display); avoids breakage on
        # wording changes / language switches
        _type_display = {
            "all": get_text("kb_all"),
            "briefing_entry": get_text("kb_briefing"),
            "search_result": get_text("kb_search"),
            "note": get_text("kb_note"),
        }
        selected_type = st.selectbox(
            get_text("kb_filter_type"),
            list(_type_display.keys()),
            format_func=lambda v: _type_display[v],
            key="kb_type_filter"
        )
    with col_filter2:
        tags = get_tags()
        tag_options = [get_text("kb_all")] + tags
        selected_tag = st.selectbox(
            get_text("kb_filter_tag"),
            tag_options,
            key="kb_tag_filter"
        )
    with col_filter3:
        if st.button(get_text("kb_add_note"), key="kb_add_note_btn"):
            st.session_state.show_add_note = True
    
    # 显示添加笔记表单
    if st.session_state.get("show_add_note"):
        _render_add_note_form()
    
    # 筛选类型
    filter_type = None if selected_type == "all" else selected_type
    
    # 获取条目
    items = get_items(
        item_type=filter_type,
        tag=selected_tag if selected_tag != get_text("kb_all") else None
    )
    
    # 显示条目列表
    if not items:
        st.info(get_text("kb_no_items"))
    else:
        for item in items:
            _render_kb_item(item)
    
    st.markdown('</div>', unsafe_allow_html=True)


def _render_add_note_form():
    """渲染添加笔记表单"""
    from intelnexus.config.knowledge_base import add_item, get_tags, add_tag
    
    with st.expander(get_text("kb_add_note"), expanded=True):
        title = st.text_input(get_text("kb_add_note_title"), key="note_title")
        content = st.text_area(get_text("kb_add_note_content"), key="note_content")
        
        # 标签选择
        existing_tags = get_tags()
        new_tags = st.multiselect(
            get_text("kb_tags"),
            options=existing_tags,
            key="note_tags"
        )
        
        # 添加新标签
        new_tag = st.text_input(get_text("kb_new_tag"), key="new_tag_input", placeholder=get_text("kb_new_tag"))
        if new_tag and st.button(get_text("kb_add_tag")):
            add_tag(new_tag)
            st.rerun()
        
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button(get_text("kb_add_note_btn")):
                if title and content:
                    add_item(
                        item_type="note",
                        title=title,
                        content=content,
                        tags=new_tags
                    )
                    st.success(get_text("kb_note_added"))
                    st.session_state.show_add_note = False
                    st.rerun()
                else:
                    st.warning(get_text("kb_note_fill_hint"))
        with col2:
            if st.button(get_text("cancel")):
                st.session_state.show_add_note = False
                st.rerun()


def _render_kb_item(item: dict):
    """渲染单个知识库条目"""
    from intelnexus.config.knowledge_base import remove_item, update_item
    
    item_id = item.get("id", "")
    item_type = item.get("type", "")
    title = item.get("title", "")
    url = item.get("url", "")
    content = item.get("content", "")
    source = item.get("source", "")
    category = item.get("category", "")
    tags = item.get("tags", [])
    created_at = item.get("created_at", "")[:10]
    
    # 类型图标
    type_icons = {
        "briefing_entry": ("entry", "gray"),
        "search_result": ("result", "blue"),
        "note": ("note", "lavender")
    }
    icon_name, icon_color = type_icons.get(item_type, ("entry", "gray"))
    
    # 渲染条目卡片（title/source 为外部不可信输入，先转义再进 unsafe HTML，防存储型 XSS）
    st.markdown(
        f'<div class="bf-entry-row">'
        f'<div class="bf-entry-info">'
        f'<span class="bf-entry-title">{icon(icon_name, "sm", icon_color)} {html.escape(str(title or ""))[:80]}</span>'
        f'<span class="bf-entry-source">{html.escape(str(source or category or item_type or ""))}</span>'
        f'<span class="bf-entry-cred">{created_at}</span>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    
    # 显示标签
    if tags:
        tags_display = " ".join([f"`{tag}`" for tag in tags])
        st.markdown(tags_display)
    
    # 显示内容预览
    if content:
        st.caption(content[:150] + "..." if len(content) > 150 else content)
    
    # 操作按钮
    converted_topic_id = (item.get("metadata") or {}).get("converted_topic_id")
    col1, col2, col3, col4 = st.columns([1, 1, 1, 3])
    with col1:
        if url:
            st.link_button(get_text("view"), url)
    with col2:
        if converted_topic_id:
            st.markdown(get_text("kb_watching"))
        elif st.button(get_text("kb_watch"), key=f"watch_{item_id}"):
            topic_id = _convert_item_to_topic(item)
            if topic_id:
                update_item(item_id, {"metadata": {
                    **(item.get("metadata") or {}), "converted_topic_id": topic_id}})
                st.success(get_text("kb_watch_success"))
                st.rerun()
            else:
                st.info(get_text("topic_subscribed").format(name=(title or item_id)[:50]))
    with col3:
        if st.button(get_text("delete"), key=f"del_{item_id}"):
            remove_item(item_id)
            st.rerun()

    st.markdown("---")


def _convert_item_to_topic(item: dict):
    """把知识库条目转为常驻 Topic 进入简报巡防；已存在同类 Topic 时返回 None。"""
    from intelnexus.topics.store import add_topic, find_by_query
    from intelnexus.topics.registry import Topic
    import hashlib

    title = (item.get("title") or "").strip()
    if not title:
        return None
    if find_by_query(title):
        return None

    keywords = list(dict.fromkeys(
        [title] + [t for t in (item.get("tags") or []) if t]))[:5]
    topic_id = f"topic_{hashlib.md5(title.encode()).hexdigest()[:8]}"
    new_topic = Topic(
        id=topic_id,
        name=title[:50],
        description=f"知识库收藏沉淀：{title[:100]}",
        search_queries=[title],
        keywords_zh=keywords,
        keywords_en=[title],
        origin="kb_item",
    )
    return topic_id if add_topic(new_topic) else None


def render_knowledge_base_sidebar():
    from intelnexus.config.knowledge_base import get_stats
    
    stats = get_stats()
    
    st.markdown(
        f'<div class="sb-section"><span class="sb-section__label">Navigation</span></div>',
        unsafe_allow_html=True
    )
    
    if st.button(
        f"{get_text('knowledge_base')} ({stats['total']})",
        key="nav_kb",
        use_container_width=True
    ):
        st.session_state.show_knowledge_base = True
        st.rerun()
