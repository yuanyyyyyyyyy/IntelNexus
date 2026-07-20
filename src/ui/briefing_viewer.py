"""
简报预览和历史查看
==================
在 Streamlit 主面板中展示简报内容和历史记录
"""

import streamlit as st
from datetime import datetime
from src.config.briefing_history import get_briefing_history
from src.ui.i18n import get_text


def render_briefing_preview():
    """
    渲染简报预览区域

    守卫条件：st.session_state.current_briefing 存在且非空
    显示内容：简报 Markdown + 下载按钮
    """
    if not st.session_state.get("current_briefing"):
        return

    st.markdown("---")
    st.markdown(f"## 📄 {get_text('briefing_preview')}")
    st.markdown(st.session_state.current_briefing)

    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            label=get_text("download_md"),
            data=st.session_state.current_briefing,
            file_name=f"briefing_{datetime.now().strftime('%Y%m%d')}.md",
            mime="text/markdown",
            key="briefing_download_md_main"
        )
    with col2:
        if st.session_state.get("current_briefing_html"):
            st.download_button(
                label=get_text("download_html"),
                data=st.session_state.current_briefing_html,
                file_name=f"briefing_{datetime.now().strftime('%Y%m%d')}.html",
                mime="text/html",
                key="briefing_download_html_main"
            )


def render_briefing_history():
    """
    渲染简报历史列表

    守卫条件：st.session_state.show_briefing_history 为 True
    显示内容：历史简报列表，支持查看和删除
    """
    if not st.session_state.get("show_briefing_history"):
        return

    history = get_briefing_history().get_briefings(limit=20)

    st.markdown("---")
    st.markdown(f"## 📋 {get_text('briefing_history')}")

    if not history:
        st.info(get_text("briefing_history_empty"))
        return

    for entry in history:
        col1, col2, col3 = st.columns([4, 1, 1])
        with col1:
            date_str = entry.get("created_at", "")[:10]
            org = entry.get("organization", "")
            st.markdown(f"**{date_str}** — {org}")
        with col2:
            if st.button("👁️", key=f"view_{entry.get('filename')}"):
                load_briefing_for_preview(
                    entry.get("filename"),
                    entry.get("html_filename")
                )
        with col3:
            if st.button("🗑️", key=f"del_{entry.get('filename')}"):
                delete_briefing(entry.get("filename"))


def load_briefing_for_preview(filename: str, html_filename: str = None):
    """加载简报到预览区域"""
    content = get_briefing_history().load_briefing(filename)
    if content:
        st.session_state.current_briefing = content
        if html_filename:
            html_content = get_briefing_history().load_briefing(html_filename)
            st.session_state.current_briefing_html = html_content
        st.session_state.show_briefing_history = False
        st.rerun()


def delete_briefing(filename: str):
    """删除简报"""
    get_briefing_history().delete_briefing(filename)
    st.success(get_text("briefing_deleted"))
    st.rerun()


def render_briefing_welcome():
    """渲染简报中心欢迎页面（当无预览且未查看历史时显示）"""
    if st.session_state.get("current_briefing") or st.session_state.get("show_briefing_history"):
        return

    st.markdown("---")
    col_left, col_right = st.columns([1, 2])

    with col_left:
        st.markdown(f"### 📰 {get_text('briefing_center')}")
        st.markdown(f"""
        <div style="padding: 20px; background: var(--morandi-card); border-radius: 12px; margin-top: 16px;">
            <p style="margin: 0 0 12px 0; color: var(--morandi-text-light);">
                {get_text('briefing_welcome_desc')}
            </p>
            <ul style="margin: 0; padding-left: 20px; color: var(--morandi-text-light); line-height: 2;">
                <li>📡 {get_text('welcome_step_sources')}</li>
                <li>👥 {get_text('welcome_step_subscribers')}</li>
                <li>🚀 {get_text('welcome_step_generate')}</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

    with col_right:
        st.markdown(f"#### ⚡ {get_text('quick_actions')}")
        st.info(get_text('briefing_quick_tip'), icon="💡")
