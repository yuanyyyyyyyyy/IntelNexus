import html

import streamlit as st
from intelnexus.ui.i18n import get_text
from intelnexus.ui.icons import icon
from intelnexus.config.briefing_drafts import add_draft, get_drafts


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


def _render_useful_button(item: dict, key_suffix: str):
    """为单条搜索结果渲染「有用」标记按钮。"""
    url = item.get("url") or item.get("link", "")
    if not url:
        return
    
    from intelnexus.config.feedback import get_search_feedback, save_search_feedback, track_feedback
    
    existing = get_search_feedback(url)
    if existing == "useful":
        st.caption(get_text("feedback_marked"))
    else:
        if st.button(get_text("feedback_useful"), key=f"useful_{key_suffix}",
                     help=get_text("feedback_hint")):
            save_search_feedback(url, "useful")
            track_feedback(url, "useful", "search")
            st.toast(get_text("feedback_marked"))
            st.rerun()


def _render_save_to_kb_button(item: dict, key_suffix: str):
    """为单条搜索结果渲染「收藏到知识库」按钮。"""
    url = item.get("url") or item.get("link", "")
    if not url:
        return
    
    from intelnexus.config.knowledge_base import get_items, add_item
    
    # 检查是否已收藏
    existing = get_items(url=url, item_type="search_result")
    if existing:
        st.caption(get_text("kb_saved"))
    else:
        if st.button(get_text("kb_save"), key=f"kb_{key_suffix}",
                     help=get_text("kb_save")):
            add_item(
                item_type="search_result",
                title=item.get("title", ""),
                url=url,
                content=item.get("description", item.get("summary", "")),
                source=item.get("source", "Unknown"),
                tags=[]
            )
            st.toast("已收藏到知识库")
            st.rerun()


def render_results_detail():
    """渲染分页搜索结果列表。

    只要搜索已完成（search_completed）即渲染：即便无结果也展示明确的空结果提示，
    不再因缺少 streamed_summary 或 filtered 为空而整片留白。
    """
    if not st.session_state.get("search_completed", False):
        return

    filtered = st.session_state.get("filtered", [])
    if len(filtered) == 0:
        st.markdown("---")
        st.info(get_text("no_results"))
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
                # 外部源的标题/描述属不可信输入，进 unsafe_allow_html 前必须转义（防存储型 XSS，
                # 与 briefing_viewer.render_briefing_entries 同一规范）
                safe_title = html.escape(str(item.get('title', '') or '')) or get_text("no_title")
                safe_desc = html.escape(str(item.get('description', '') or ''))
                safe_summary = html.escape(str(item.get('summary', '') or ''))
                st.markdown(f"**{actual_idx}. {safe_title[:150]}**")
                if item.get('description'):
                    st.markdown(f"{icon('entry', 'sm', 'gray')} {safe_desc[:500]}...", unsafe_allow_html=True)
                elif item.get('summary'):
                    st.markdown(f"{icon('note', 'sm', 'lavender')} {safe_summary[:500]}...", unsafe_allow_html=True)
                if item.get('link') or item.get('url'):
                    link = item.get('link') or item.get('url')
                    st.markdown(get_text("view_original").format(link=link))
                # 收藏到简报草稿（搜→报飞轮闭环）
                # key 必须全局唯一：i 是组内索引会重复，故用 source+全局序号组合
                # 三个按钮横向同行，避免各占一整行
                _btn_cols = st.columns(3)
                with _btn_cols[0]:
                    _render_collect_button(item, f"{source}_{actual_idx}")
                with _btn_cols[1]:
                    _render_useful_button(item, f"{source}_{actual_idx}")
                with _btn_cols[2]:
                    _render_save_to_kb_button(item, f"{source}_{actual_idx}")
                st.markdown("---")

    # 弱相关结果（被语义相关性过滤降权，不进报告/KG 主干，但保留可追溯）
    _all_results = st.session_state.get("results", []) or []
    weak_items = [r for r in _all_results if r.get("weak_related", False)]
    if weak_items:
        with st.expander(
            f"{get_text('weak_related_title').format(count=len(weak_items))}",
            expanded=False
        ):
            st.caption(get_text("weak_related_hint"))
            for wi, item in enumerate(weak_items):
                wkey = f"weak_{wi}"
                # 不可信外部输入先转义再进 unsafe 渲染（同上，防存储型 XSS）
                safe_title = html.escape(str(item.get('title', '') or '')) or get_text("no_title")
                safe_desc = html.escape(str(item.get('description', '') or ''))
                safe_summary = html.escape(str(item.get('summary', '') or ''))
                st.markdown(f"**{safe_title[:150]}**")
                if item.get('description'):
                    st.markdown(f"{icon('entry', 'sm', 'gray')} {safe_desc[:500]}...", unsafe_allow_html=True)
                elif item.get('summary'):
                    st.markdown(f"{icon('note', 'sm', 'lavender')} {safe_summary[:500]}...", unsafe_allow_html=True)
                if item.get('link') or item.get('url'):
                    link = item.get('link') or item.get('url')
                    st.markdown(get_text("view_original").format(link=link))
                # key 加 weak_ 前缀，与主列表的 source_actual_idx 区分，避免 DuplicateWidgetID
                _render_collect_button(item, f"weak_{wkey}")
                st.markdown("---")
