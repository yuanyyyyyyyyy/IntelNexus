import streamlit as st
from src.ui.i18n import get_text
from src.config.briefing_drafts import add_draft, get_drafts


def _render_collect_button(item: dict, key_suffix: str):
    """为单条搜索结果渲染「收藏到简报」按钮（去重：已收藏则提示）。"""
    url = item.get("url") or item.get("link", "")
    if not url:
        return
    drafts = get_drafts()
    already = any(d.get("url") == url for d in drafts)
    label = get_text("collected") if already else get_text("collect_to_briefing")
    if st.button(label, key=f"collect_{key_suffix}", disabled=already,
                 help=get_text("collect_help")):
        ok = add_draft({
            "title": item.get("title", ""),
            "url": url,
            "content": item.get("content", item.get("description", "")),
            "description": item.get("description", ""),
            "source": item.get("source", "Unknown"),
        })
        if ok:
            st.toast(get_text("collect_ok"))
        else:
            st.toast(get_text("collect_dup"))
        st.rerun()


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
        st.markdown(f'<div class="report-title">{get_text("results_detail_title").format(count=total_results)}</div>', unsafe_allow_html=True)
    with col2:
        page_cols = st.columns([1, 1, 1])
        with page_cols[0]:
            if st.session_state.result_page > 1:
                if st.button(get_text("prev_page"), key="prev_page"):
                    st.session_state.result_page -= 1
                    st.rerun()
        with page_cols[1]:
            st.markdown(f"**{st.session_state.result_page}/{total_pages}**")
        with page_cols[2]:
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
        with st.expander(get_text("results_from_source").format(source=source, count=len(items)), expanded=False):
            for i, item in enumerate(items):
                actual_idx = start_idx + i + 1
                st.markdown(f"**{actual_idx}. {item.get('title', get_text('no_title'))[:150]}**")
                if item.get('description'):
                    st.markdown(f"📝 {item.get('description', '')[:500]}...")
                elif item.get('summary'):
                    st.markdown(f"📝 {item.get('summary', '')[:500]}...")
                if item.get('link') or item.get('url'):
                    link = item.get('link') or item.get('url')
                    st.markdown(get_text("view_original").format(link=link))
                # 收藏到简报草稿（搜→报飞轮闭环）
                _render_collect_button(item, f"{start_idx}_{i}")
                st.markdown("---")
