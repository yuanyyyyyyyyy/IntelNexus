"""
帮助弹窗（st.dialog 模态对话框）
================================
提供应用内帮助文档，分 Tab 展示：快速开始 / 搜索指南 / 简报指南 / 模型配置 / 常见问题。
内容从 i18n 读取，跟随中英文切换。

入口：
- 首页问候区旁「查看快速指南」按钮（首次自动弹出）
- 侧边栏底部「使用帮助」按钮
"""

import streamlit as st

from intelnexus.ui.i18n import get_text
from intelnexus.ui.icons import icon


@st.dialog("IntelNexus Help", width="large")
def _help_dialog():
    """帮助弹窗主体：5 个 Tab 分页展示帮助内容。"""
    st.markdown(f"<div style='text-align:center;margin-bottom:8px;font-size:15px;color:var(--wb-text-secondary,#666);'>{get_text('help_title')}</div>", unsafe_allow_html=True)
    tab_quick, tab_search, tab_briefing, tab_model, tab_faq = st.tabs([
        get_text("help_tab_quick"),
        get_text("help_tab_search"),
        get_text("help_tab_briefing"),
        get_text("help_tab_model"),
        get_text("help_tab_faq"),
    ])

    with tab_quick:
        st.markdown(get_text("help_quick_step1"))
        st.divider()
        st.markdown(get_text("help_quick_step2"))
        st.divider()
        st.markdown(get_text("help_quick_step3"))
        st.divider()
        st.markdown(get_text("help_quick_step4"))

    with tab_search:
        st.markdown(f"### {icon('search', color='blue', size='sm')} {get_text('help_search_title')}", unsafe_allow_html=True)
        st.markdown(get_text("help_search_desc"))
        st.divider()
        st.markdown(get_text("help_search_modes"))
        st.divider()
        st.markdown(get_text("help_search_tips"))

    with tab_briefing:
        st.markdown(f"### {icon('briefing', color='blue', size='sm')} {get_text('help_briefing_title')}", unsafe_allow_html=True)
        st.markdown(get_text("help_briefing_desc"))
        st.divider()
        st.markdown(get_text("help_briefing_steps"))

    with tab_model:
        st.markdown(f"### {icon('ai_model', color='gray', size='sm')} {get_text('help_model_title')}", unsafe_allow_html=True)
        st.markdown(get_text("help_model_local"))
        st.divider()
        st.markdown(get_text("help_model_custom"))

    with tab_faq:
        st.markdown(f"### {get_text('help_faq_title')}")
        st.markdown(get_text("help_faq_q1"))
        st.markdown(get_text("help_faq_a1"))
        st.divider()
        st.markdown(get_text("help_faq_q2"))
        st.markdown(get_text("help_faq_a2"))
        st.divider()
        st.markdown(get_text("help_faq_q3"))
        st.markdown(get_text("help_faq_a3"))
        st.divider()
        st.markdown(get_text("help_faq_q4"))
        st.markdown(get_text("help_faq_a4"))
        st.divider()
        st.markdown(get_text("help_faq_q5"))
        st.markdown(get_text("help_faq_a5"))

    st.divider()
    st.caption(get_text("help_footer"))


def open_help_dialog():
    """打开帮助弹窗。

    供 overview.py 和 sidebar.py 调用。
    """
    _help_dialog()


def render_first_time_help_card():
    """首页首次使用引导卡。

    仅在用户首次访问时显示（session_state 标记已读后不再显示）。
    点击按钮后自动弹出帮助弹窗。
    """
    if st.session_state.get("help_dismissed"):
        return

    col_tag, col_btn = st.columns([1, 1])
    with col_tag:
        st.markdown(
            f'<div style="font-size:13px;color:var(--wb-text-secondary,#666);'
            f'margin-top:8px;">'
            f'{icon("info", color="blue", size="sm")} {get_text("help_first_time_tag")}'
            f'</div>',
            unsafe_allow_html=True,
        )
    with col_btn:
        if st.button(
            get_text("help_first_time_btn"),
            key="help_first_time_btn",
            use_container_width=True,
        ):
            st.session_state.show_help_dialog = True
            st.session_state.help_dismissed = True
            st.rerun()


def render_sidebar_help_button():
    """侧边栏底部「使用帮助」按钮。

    常驻显示，任何页面都可点击打开帮助弹窗。
    """
    if st.button(
        f"{icon('info', color='gray', size='sm')} {get_text('help_btn')}",
        key="sidebar_help_btn",
        use_container_width=True,
    ):
        st.session_state.show_help_dialog = True
        st.rerun()


def check_and_show_auto_help():
    """检查是否需要自动弹出帮助弹窗。

    在 ui.py 主渲染流程中调用，处理 session_state 旗标。
    返回 True 表示弹窗已触发（调用方可继续正常渲染）。
    """
    if st.session_state.pop("show_help_dialog", False):
        open_help_dialog()
        return True
    return False
