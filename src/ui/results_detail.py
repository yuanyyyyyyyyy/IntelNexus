import streamlit as st
from src.ui.i18n import get_text


def render_results_detail():
    """渲染分页搜索结果列表"""
    if not (st.session_state.get("search_completed", False) and st.session_state.get("filtered")):
        return

    filtered = st.session_state.filtered
    if len(filtered) == 0:
        return

    st.markdown("---")

    if "result_page" not in st.session_state:
        st.session_state.result_page = 1

    all_results = filtered
    total_results = len(all_results)

    ITEMS_PER_PAGE = 40
    total_pages = (total_results + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE

    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f'<div class="report-title">📋 搜索结果详情 ({total_results}条)</div>', unsafe_allow_html=True)
    with col2:
        page_cols = st.columns([1, 1, 1])
        with page_cols[0]:
            if st.session_state.result_page > 1:
                if st.button("◀ 上一页", key="prev_page"):
                    st.session_state.result_page -= 1
                    st.rerun()
        with page_cols[1]:
            st.markdown(f"**{st.session_state.result_page}/{total_pages}**")
        with page_cols[2]:
            if st.session_state.result_page < total_pages:
                if st.button("下一页 ▶", key="next_page"):
                    st.session_state.result_page += 1
                    st.rerun()

    start_idx = (st.session_state.result_page - 1) * ITEMS_PER_PAGE
    end_idx = min(start_idx + ITEMS_PER_PAGE, total_results)
    page_results = all_results[start_idx:end_idx]

    source_groups = {}
    for item in page_results:
        source = item.get("source", "Unknown")
        if source not in source_groups:
            source_groups[source] = []
        source_groups[source].append(item)

    for source, items in source_groups.items():
        with st.expander(f"📌 {source} ({len(items)}条)", expanded=False):
            for i, item in enumerate(items):
                actual_idx = start_idx + i + 1
                st.markdown(f"**{actual_idx}. {item.get('title', '无标题')[:150]}**")
                if item.get('description'):
                    st.markdown(f"📝 {item.get('description', '')[:500]}...")
                elif item.get('summary'):
                    st.markdown(f"📝 {item.get('summary', '')[:500]}...")
                if item.get('link') or item.get('url'):
                    link = item.get('link') or item.get('url')
                    st.markdown(f"🔗 [查看原文]({link})")
                st.markdown("---")
