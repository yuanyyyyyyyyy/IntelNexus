"""
搜索结果数据源抽象与统一渲染编排
=====================================
同一套结果渲染代码同时服务两条路径：

- **实时结果**：数据来自 ``st.session_state``（搜索完成时由 fragment 写回）；
- **历史回放**：数据来自 ``data/snapshots/<entry_id>/snapshot.json`` 快照。

历史回放**不能**把快照写回 session_state 再调用既有渲染函数（会覆盖实时结果，
且触发 widget key 冲突），因此所有渲染函数参数化为接收 ``ResultsView``，
配合 ``key_prefix`` 隔离 widget 命名空间，保证历史详情与实时结果页完全一致。
"""

import html

import streamlit as st

from intelnexus.ui.i18n import get_text


class ResultsView:
    """搜索结果数据源统一抽象。

    实时结果来自 st.session_state，历史回放来自快照 dict；
    渲染函数只依赖本接口，从而复用同一套 UI 代码。
    """

    def __init__(self, data=None, *, live: bool = False):
        """
        Args:
            data: 实时路径传 ``st.session_state``；历史回放传快照 dict。
            live: 是否为实时视图（``enabled`` 由 search_completed 决定，
                  且每次取数都读 session_state 的最新值）。
        """
        self._data = {} if data is None else data
        self._live = live

    @classmethod
    def live(cls) -> "ResultsView":
        """构造代理 ``st.session_state`` 的实时视图。"""
        return cls(st.session_state, live=True)

    @property
    def enabled(self) -> bool:
        """是否存在可渲染的数据（实时为 search_completed，回放为快照非空）。"""
        if self._live:
            return bool(st.session_state.get("search_completed", False))
        return bool(self._data)

    def get(self, key: str, default=None):
        """读取字段；会话状态未就绪等异常一律返回 default，不中断渲染。"""
        try:
            return self._data.get(key, default)
        except Exception:
            return default

    def __contains__(self, key: str) -> bool:
        try:
            return key in self._data
        except Exception:
            return False


def render_query_stats_cards(view: ResultsView, key_prefix: str = "") -> None:
    """渲染查询优化卡 + 结果统计卡 + 数据源完整性透明度条。

    从 ``search_pipeline._render_search_results_ui`` 抽出，供实时搜索（完成态
    fragment）与历史回放共用，保证两处呈现完全一致。
    """
    query = view.get("query", "") or ""
    results = view.get("results", []) or []
    results_count = len(results)
    source_info = view.get("source_info", "") or ""
    source_stats = view.get("source_stats", {}) or {}

    # 查询优化展示：透明化检索范围 —— 原始查询 / 实际检索串 / 变体列表
    search_query = view.get("search_query", query) or query
    query_variants = view.get("query_variants", []) or []
    variants_html = "".join(
        f'<div class="result-subtitle">· {html.escape(v)}</div>'
        for v in query_variants
    )
    st.markdown(f"""
    <div class="result-card">
        <div class="section-header">{get_text("refined_query")}</div>
        <div class="result-title">{get_text("original_query")} {html.escape(query)}</div>
        <div class="result-title">{get_text("search_query_label")} {html.escape(search_query)}</div>
        {variants_html}
    </div>
    """, unsafe_allow_html=True)

    # 结果统计卡
    st.markdown(f"""
    <div class="result-card">
        <div class="result-stats">
            <div class="stat-item">
                <div class="stat-value">{results_count}</div>
                <div class="stat-label">{get_text("results_count")}</div>
            </div>
        </div>
        <div class="stat-label" style="margin-top: 10px;">{get_text("data_source_label")} {html.escape(source_info)}</div>
    </div>
    """, unsafe_allow_html=True)

    # 源完整性透明度条
    if source_stats:
        ok_sources = [n for n, s in source_stats.items() if s.get("status") == "ok"]
        skipped = [(n, s.get("status")) for n, s in source_stats.items()
                   if s.get("status") != "ok"]
        if skipped:
            reason_map = {"timeout": get_text("src_skip_timeout"),
                          "no_proxy": get_text("src_skip_no_proxy"),
                          "error": get_text("src_skip_error"),
                          "skipped": get_text("src_skip_skipped")}
            detail = ", ".join(f"{n} ({reason_map.get(s, s)})"
                               for n, s in skipped)
            st.info(get_text("source_integrity").format(
                ok=len(ok_sources), skip=len(skipped)) +
                f" <sub>{html.escape(detail[:200])}</sub>")
        else:
            st.success(get_text("all_sources_ok").format(ok=len(ok_sources)))


def render_full_results(view: ResultsView, key_prefix: str = "",
                        include_query_stats: bool = False) -> None:
    """按与实时结果页一致的顺序渲染全部分区。

    顺序：查询卡/统计条（可选）→ 报告 + TL;DR → 可视化面板 → 下载区 → 分页结果列表。

    Args:
        view: 结果数据源。
        key_prefix: widget key 前缀。历史回放传 ``hist_<entry_id>_``
            以隔离命名空间，避免与实时结果的同名控件冲突。
        include_query_stats: 是否渲染查询统计卡。实时路径也传 True —— 搜索完成态
            fragment 渲染的内容会随随后的整页 rerun 丢弃，必须由主页面持久渲染；
            历史回放同样传 True，保证「历史回放 = 搜索当时的页面」。
    """
    # 延迟 import：results / search_pipeline 等模块反向引用本模块类型，
    # 模块级 import 会形成循环依赖。
    from intelnexus.ui.results import render_results_panels
    from intelnexus.ui.results_detail import render_results_detail
    from intelnexus.ui.download import render_download_section
    from intelnexus.ui.search_pipeline import render_search_report

    if not view.enabled:
        return

    if include_query_stats:
        render_query_stats_cards(view, key_prefix=key_prefix)

    render_search_report(view)
    render_results_panels(view)
    render_download_section(view, key_prefix=key_prefix)
    # 分页游标使用独立 key：历史回放不得复用全局 result_page，
    # 否则会把历史页码写进实时结果页
    render_results_detail(view, key_prefix=key_prefix,
                          page_key=f"{key_prefix}result_page" or "result_page")


def render_history_snapshot(snapshot: dict, key_prefix: str) -> bool:
    """按快照完整还原搜索结果页。

    Returns:
        bool: True 表示已渲染；False 表示快照为空（调用方应降级到
        report_content / 元数据展示）。
    """
    view = ResultsView(snapshot)
    if not view.enabled:
        return False
    render_full_results(view, key_prefix=key_prefix, include_query_stats=True)
    return True
