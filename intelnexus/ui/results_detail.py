import html
import re

import streamlit as st
from intelnexus.ui.i18n import get_text
from intelnexus.ui.icons import icon
# 复用 results.py 的 URL 安全处理，使「查看原文」链接与证据链链接共用同一套防护
from intelnexus.ui.results import _safe_md_url
from intelnexus.config.briefing_drafts import add_draft, get_drafts


def _strip_html_tags(text: str) -> str:
    """剥离文本中的 HTML 标签，防止 html.escape 后将标签源码暴露给用户。"""
    return re.sub(r'<[^>]+>', '', text)


def _safe_text(value) -> str:
    """外部不可信文本：先剥离 HTML 标签再转义，兼顾安全与可读性。"""
    return html.escape(_strip_html_tags(str(value if value is not None else "")))


def _is_onion_item(item: dict) -> bool:
    """判断一条结果是否指向 .onion 站点（暗网结果需要显式标注）。"""
    link = (item.get("link") or item.get("url") or "")
    return ".onion" in str(link).lower()


def _onion_badge() -> str:
    """暗网结果徽章。用 span 而非 emoji，避免不同字体下宽度跳动。"""
    return '<span class="onion-badge">ONION</span>'


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


def _render_useful_button(item: dict, key_suffix: str, feedback_map: dict = None):
    """为单条搜索结果渲染「有用」标记按钮。

    R17：feedback_map 由 render_results_detail 整页预载传入（get_search_feedback_map），
    避免每条结果各读一次反馈文件；未传时回退逐条读取（防御兼容）。
    """
    url = item.get("url") or item.get("link", "")
    if not url:
        return
    
    from intelnexus.config.feedback import get_search_feedback, save_search_feedback, track_feedback
    
    existing = feedback_map.get(url) if feedback_map is not None else get_search_feedback(url)
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


# 每页条数：主列表与弱相关折叠区共用同一口径（R17，2026-10-21）
ITEMS_PER_PAGE = 40


def render_results_detail(view=None, key_prefix: str = "", page_key: str = "result_page"):
    """渲染分页搜索结果列表。

    只要搜索已完成（search_completed）即渲染：即便无结果也展示明确的空结果提示，
    不再因缺少 streamed_summary 或 filtered 为空而整片留白。

    Args:
        view: 结果数据源（``ResultsView``）。为 None 时读取 ``st.session_state``
            （实时搜索结果路径）。
        key_prefix: widget key 前缀，历史回放传 ``hist_<entry_id>_`` 隔离命名空间。
        page_key: 分页游标在 session_state 中的键。历史回放使用独立键，
            避免把历史页码写进实时结果页。
    """
    if view is not None:
        if not view.enabled:
            return
        _get = view.get
    else:
        if not st.session_state.get("search_completed", False):
            return
        _get = st.session_state.get

    # R17：反馈索引整页预载——「有用」按钮逐条 get_search_feedback 会把反馈文件
    # 整读 N 次（弱相关 785 条时 ≈2355 次/页），改为一次读盘建索引后传引用。
    from intelnexus.config.feedback import get_search_feedback_map
    _feedback_map = get_search_feedback_map()

    def _render_weak_block(weak_items, expanded: bool):
        """R15：弱相关折叠区渲染（主列表为空时也可独立调用）。

        R17：与主列表同口径分页（ITEMS_PER_PAGE 条/页）——china 快照曾一次
        渲染 785 条弱相关（每条 11 个元素），巨量 delta 流正是历史回放卡墙的
        主因。游标与按钮 key 派生自 page_key，实时/各历史回放命名空间互不串扰；
        数据收缩后游标越界则钳回第 1 页。
        """
        weak_cursor_key = f"{page_key}_weak"
        if weak_cursor_key not in st.session_state:
            st.session_state[weak_cursor_key] = 1
        if st.session_state[weak_cursor_key] < 1:
            st.session_state[weak_cursor_key] = 1
        total_weak = len(weak_items)
        total_weak_pages = (total_weak + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
        if st.session_state[weak_cursor_key] > total_weak_pages:
            st.session_state[weak_cursor_key] = 1
        w_start = (st.session_state[weak_cursor_key] - 1) * ITEMS_PER_PAGE
        w_end = min(w_start + ITEMS_PER_PAGE, total_weak)
        page_weak = weak_items[w_start:w_end]

        with st.expander(
            f"{get_text('weak_related_title').format(count=len(weak_items))}",
            expanded=expanded
        ):
            st.caption(get_text("weak_related_hint"))
            if total_weak_pages > 1:
                w_page_cols = st.columns([1, 1, 1])
                with w_page_cols[0]:
                    if st.session_state[weak_cursor_key] > 1:
                        if st.button(get_text("prev_page"), key=f"{page_key}_weak_prev"):
                            st.session_state[weak_cursor_key] -= 1
                            st.rerun()
                with w_page_cols[1]:
                    st.markdown(f"**{st.session_state[weak_cursor_key]}/{total_weak_pages}**")
                with w_page_cols[2]:
                    if st.session_state[weak_cursor_key] < total_weak_pages:
                        if st.button(get_text("next_page"), key=f"{page_key}_weak_next"):
                            st.session_state[weak_cursor_key] += 1
                            st.rerun()
            for wi, item in enumerate(page_weak, start=w_start):
                wkey = f"weak_{wi}"
                # 不可信外部输入先剥离 HTML 标签再转义（防存储型 XSS + 避免标签源码暴露）
                safe_title = _safe_text(item.get('title', '') or '') or get_text("no_title")
                safe_desc = _safe_text(item.get('description', '') or '')
                safe_summary = _safe_text(item.get('summary', '') or '')
                st.markdown(f"**{safe_title[:150]}**")
                if item.get('description'):
                    st.markdown(f"{icon('entry', 'sm', 'gray')} {safe_desc[:500]}...", unsafe_allow_html=True)
                elif item.get('summary'):
                    st.markdown(f"{icon('note', 'sm', 'lavender')} {safe_summary[:500]}...", unsafe_allow_html=True)
                if item.get('link') or item.get('url'):
                    link = item.get('link') or item.get('url')
                    # 外部 URL 可能是伪协议或含破坏 markdown 链接语法的字符：
                    # 先过安全处理，不合法则降级为转义纯文本（与证据链链接口径一致）
                    safe_link = _safe_md_url(link)
                    if safe_link:
                        st.markdown(get_text("view_original").format(link=safe_link))
                    else:
                        st.markdown(_safe_text(link))
                # key 加 weak_ 前缀，与主列表的 source_actual_idx 区分，避免 DuplicateWidgetID
                st.markdown('<div class="result-btn-row">', unsafe_allow_html=True)
                _wbtn_cols = st.columns(3)
                with _wbtn_cols[0]:
                    _render_collect_button(item, f"{key_prefix}weak_{wkey}")
                with _wbtn_cols[1]:
                    _render_useful_button(item, f"{key_prefix}weak_{wkey}",
                                          feedback_map=_feedback_map)
                with _wbtn_cols[2]:
                    _render_save_to_kb_button(item, f"{key_prefix}weak_{wkey}")
                st.markdown('</div>', unsafe_allow_html=True)
                st.markdown("---")

    filtered = _get("filtered", []) or []
    if len(filtered) == 0:
        st.markdown("---")
        # R15（2026-10-21）：主列表 0 条但弱相关有结果时，直接展开弱相关区——
        # 避免「8 条结果只显示未检索到任何结果」的误导（华盛顿酒店实测）
        weak_items = [r for r in (_get("results", []) or []) if r.get("weak_related", False)]
        if weak_items:
            st.info(get_text("no_results_weak").format(n=len(weak_items)))
            _render_weak_block(weak_items, expanded=True)
        else:
            st.info(get_text("no_results"))
        return

    st.markdown("---")

    if page_key not in st.session_state:
        st.session_state[page_key] = 1

    all_results = filtered
    total_results = len(all_results)

    total_pages = (total_results + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE

    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f'<div class="report-title">{get_text("results_detail_title").format(count=total_results)}</div>', unsafe_allow_html=True)
        # 暗网覆盖度：明确「本次覆盖几个暗网源、命中多少条 .onion」，
        # 让暗网能力成为可量化的指标，而不是混在结果总数里看不出来
        _onion_total = sum(1 for it in all_results if _is_onion_item(it))
        if _onion_total:
            _onion_sources = len({(it.get("source") or "Unknown")
                                  for it in all_results if _is_onion_item(it)})
            st.caption(get_text("darkweb_coverage").format(
                sources=_onion_sources, count=_onion_total))
    with col2:
        page_cols = st.columns([1, 1, 1])
        with page_cols[0]:
            if st.session_state[page_key] > 1:
                if st.button(get_text("prev_page"), key=f"{key_prefix}prev_page"):
                    st.session_state[page_key] -= 1
                    st.rerun()
        with page_cols[1]:
            st.markdown(f"**{st.session_state[page_key]}/{total_pages}**")
        with page_cols[2]:
            if st.session_state[page_key] < total_pages:
                if st.button(get_text("next_page"), key=f"{key_prefix}next_page"):
                    st.session_state[page_key] += 1
                    st.rerun()

    start_idx = (st.session_state[page_key] - 1) * ITEMS_PER_PAGE
    end_idx = min(start_idx + ITEMS_PER_PAGE, total_results)
    page_results = all_results[start_idx:end_idx]

    source_groups = {}
    for item in page_results:
        source = item.get("source", "Unknown")
        if source not in source_groups:
            source_groups[source] = []
        source_groups[source].append(item)

    for source, items in source_groups.items():
        # 分组标题标注该组内的 .onion 条目数，让暗网来源在折叠态也一眼可见
        onion_count = sum(1 for it in items if _is_onion_item(it))
        group_label = get_text("results_from_source").format(source=source, count=len(items))
        if onion_count:
            group_label += f" · ONION ×{onion_count}"
        with st.expander(group_label, expanded=False):
            for i, item in enumerate(items):
                actual_idx = start_idx + i + 1
                # 外部源的标题/描述属不可信输入，先剥离 HTML 标签再转义（防存储型 XSS + 避免标签源码暴露）
                safe_title = _safe_text(item.get('title', '') or '') or get_text("no_title")
                safe_desc = _safe_text(item.get('description', '') or '')
                safe_summary = _safe_text(item.get('summary', '') or '')
                # 徽章拼在加粗外层：标题已转义，徽章是本地常量，混排安全
                _badge = _onion_badge() if _is_onion_item(item) else ""
                if _badge:
                    st.markdown(f'{_badge}**{actual_idx}. {safe_title[:150]}**',
                                unsafe_allow_html=True)
                else:
                    st.markdown(f"**{actual_idx}. {safe_title[:150]}**")
                if item.get('description'):
                    st.markdown(f"{icon('entry', 'sm', 'gray')} {safe_desc[:500]}...", unsafe_allow_html=True)
                elif item.get('summary'):
                    st.markdown(f"{icon('note', 'sm', 'lavender')} {safe_summary[:500]}...", unsafe_allow_html=True)
                if item.get('link') or item.get('url'):
                    link = item.get('link') or item.get('url')
                    # 外部 URL 可能是伪协议或含破坏 markdown 链接语法的字符：
                    # 先过安全处理，不合法则降级为转义纯文本（与证据链链接口径一致）
                    safe_link = _safe_md_url(link)
                    if safe_link:
                        st.markdown(get_text("view_original").format(link=safe_link))
                    else:
                        st.markdown(_safe_text(link))
                # 收藏到简报草稿（搜→报飞轮闭环）
                # key 必须全局唯一：i 是组内索引会重复，故用 source+全局序号组合
                # 三个按钮横向同行，避免各占一整行；.result-btn-row 控制紧凑间距
                st.markdown('<div class="result-btn-row">', unsafe_allow_html=True)
                _btn_cols = st.columns(3)
                with _btn_cols[0]:
                    _render_collect_button(item, f"{key_prefix}{source}_{actual_idx}")
                with _btn_cols[1]:
                    _render_useful_button(item, f"{key_prefix}{source}_{actual_idx}",
                                          feedback_map=_feedback_map)
                with _btn_cols[2]:
                    _render_save_to_kb_button(item, f"{key_prefix}{source}_{actual_idx}")
                st.markdown('</div>', unsafe_allow_html=True)
                st.markdown("---")

    # 弱相关结果（被语义相关性过滤降权，不进报告/KG 主干，但保留可追溯）。
    # R15 重构遗留修复（2026-10-21）：_render_weak_block 落地时旧的内联渲染未删
    # （if True: 残段），同一批弱相关条目的 收藏/有用/知识库 按钮以相同 key 注册
    # 两次，弱相关条目一出现即抛 StreamlitDuplicateElementKey(collect_weak_weak_0)。
    # 现只保留折叠区块一次渲染；提示文案在 expander 内已有，无信息损失。
    _all_results = _get("results", []) or []
    weak_items = [r for r in _all_results if r.get("weak_related", False)]
    if weak_items:
        _render_weak_block(weak_items, expanded=False)
