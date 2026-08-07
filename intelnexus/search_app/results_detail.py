import streamlit as st
from intelnexus.ui.i18n import get_text


def render_results_detail():
    """渲染分页搜索结果列表 — Intel Report Document 风格"""
    if not (st.session_state.get("search_completed", False) and st.session_state.get("filtered")):
        return

    filtered = st.session_state.filtered
    if len(filtered) == 0:
        return

    if "result_page" not in st.session_state:
        st.session_state.result_page = 1

    all_results = filtered
    total_results = len(all_results)

    ITEMS_PER_PAGE = 40
    total_pages = (total_results + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE

    st.markdown('<hr class="ir-divider">', unsafe_allow_html=True)
    st.markdown(
        f'<div class="ir-section-title ir-section-title--cred">'
        f'Search Results ({total_results} items)</div>',
        unsafe_allow_html=True)

    # Pagination bar
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        pass
    with col2:
        st.markdown(f"**{st.session_state.result_page}/{total_pages}**")
    with col3:
        page_cols = st.columns(2)
        with page_cols[0]:
            if st.session_state.result_page > 1:
                if st.button(get_text("prev_page"), key="prev_page"):
                    st.session_state.result_page -= 1
                    st.rerun()
        with page_cols[1]:
            if st.session_state.result_page < total_pages:
                if st.button(get_text("next_page"), key="next_page"):
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
        with st.expander(
            f"{source} ({len(items)} items)", expanded=False
        ):
            for i, item in enumerate(items):
                actual_idx = start_idx + i + 1
                title = item.get('title', get_text('no_title'))[:150]
                st.markdown(f"**{actual_idx}. {title}**")

                desc = item.get('description') or item.get('summary')
                if desc:
                    st.markdown(f"<p style='color:#6B7280;font-size:13px;margin:2px 0 8px;'>{desc[:500]}...</p>",
                                unsafe_allow_html=True)

                link = item.get('link') or item.get('url')
                if link:
                    st.markdown(get_text("view_original").format(link=link))
                st.markdown('<hr class="ir-divider">', unsafe_allow_html=True)
