"""结果列表弱相关区渲染回归测试（R17）。

背景（2026-10-21 用户报告「查看历史记录先卡出排版错乱的卡墙、很久才显示内容」）：
R15（b0fbb49）把弱相关循环抽成 ``_render_weak_block`` 时遗留了原内联循环
（``if True:`` 残块），弱相关条目被整块渲染两遍且 widget key 完全相同——
第二遍开头即抛 DuplicateWidgetID，被历史预览兜底捕获后静默降级；
同时「条数 × 2 遍 × 每条 11 元素」的巨量 delta 流正是卡墙与长等待的主因
（实测 china 快照 898 条结果中 785 条为弱相关）。

本文件锁定五个行为：
1. 含弱相关条目的结果页完整渲染、不抛异常；
2. 弱相关条目只渲染一次；
3. 弱相关区随主列表口径分页（40 条/页），不再不分页整块渲染；
4. 主列表为空、弱相关直接展开时（R15 特性）同样分页且不崩；
5. 「查看一条记录」时历史列表让位：预览打开即不再渲染整张列表。
"""

import pytest


def _weak_snapshot(n_weak: int, n_main: int = 1) -> dict:
    main = [
        {"title": f"主结果{i}", "url": f"https://a.example/m{i}",
         "source": "Web", "description": "主结果描述"}
        for i in range(n_main)
    ]
    weak = [
        {"title": f"弱相关条目{i:03d}", "url": f"https://a.example/w{i}",
         "source": "Web", "description": "弱相关描述", "weak_related": True}
        for i in range(n_weak)
    ]
    return {"filtered": main, "results": main + weak}


def _render_results_script():
    """主列表非空 + 45 条弱相关：R15 残块在此路径触发 DuplicateWidgetID。

    快照数据经 ``at.session_state['_test_snapshot']`` 注入——AppTest 只
    序列化函数源码，模块级辅助函数在脚本命名空间不可见。
    """
    import streamlit as st
    from intelnexus.ui.results_detail import render_results_detail
    from intelnexus.ui.results_view import ResultsView

    render_results_detail(
        ResultsView(st.session_state["_test_snapshot"]),
        key_prefix="hist_test_",
        page_key="hist_test_result_page",
    )


def _render_zero_main_script():
    """主列表为空、弱相关直接展开（R15 引入的路径）。"""
    import streamlit as st
    from intelnexus.ui.results_detail import render_results_detail
    from intelnexus.ui.results_view import ResultsView

    render_results_detail(
        ResultsView(st.session_state["_test_snapshot"]),
        key_prefix="hist_zero_",
        page_key="hist_zero_result_page",
    )


def _run(script_fn, snapshot: dict, timeout: int = 120):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_function(script_fn, default_timeout=timeout)
    at.session_state["_test_snapshot"] = snapshot
    at.run()
    return at


# ---------------------------------------------------------------------------
# 1. 弱相关条目完整渲染、不抛异常（修复前：DuplicateWidgetID）
# ---------------------------------------------------------------------------

def test_weak_related_renders_without_exception():
    at = _run(_render_results_script, _weak_snapshot(n_weak=45))
    assert not at.exception, at.exception


def test_zero_main_weak_expanded_renders_without_exception():
    at = _run(_render_zero_main_script, _weak_snapshot(n_weak=45, n_main=0))
    assert not at.exception, at.exception


# ---------------------------------------------------------------------------
# 2. 弱相关条目只渲染一次（修复前：折叠区 + 内联残块各渲染一遍）
# ---------------------------------------------------------------------------

def test_weak_related_rendered_exactly_once():
    at = _run(_render_results_script, _weak_snapshot(n_weak=45))
    assert not at.exception, at.exception
    hits = [m for m in at.markdown if "弱相关条目000" in m.value]
    assert len(hits) == 1, f"弱相关条目000 应只渲染一次，实际 {len(hits)} 次"


# ---------------------------------------------------------------------------
# 3. 弱相关区分页：第 1 页 40 条，翻页后出后续条目
# ---------------------------------------------------------------------------

def test_weak_related_paged():
    at = _run(_render_results_script, _weak_snapshot(n_weak=45))
    assert not at.exception, at.exception
    values = [m.value for m in at.markdown]
    assert any("弱相关条目039" in v for v in values), "第 1 页应含第 40 条弱相关"
    assert not any("弱相关条目040" in v for v in values), "第 1 页不应渲染第 41 条弱相关"

    # 翻到第 2 页
    nxt = [b for b in at.button if b.key == "hist_test_result_page_weak_next"]
    assert nxt, "弱相关区应提供下一页按钮"
    nxt[0].click().run()
    assert not at.exception, at.exception
    values = [m.value for m in at.markdown]
    assert any("弱相关条目040" in v for v in values), "第 2 页应含第 41 条弱相关"
    assert not any("弱相关条目039" in v for v in values), "第 2 页不应再渲染第 40 条弱相关"


def test_zero_main_weak_expanded_paged():
    at = _run(_render_zero_main_script, _weak_snapshot(n_weak=45, n_main=0))
    assert not at.exception, at.exception
    values = [m.value for m in at.markdown]
    assert any("弱相关条目000" in v for v in values), "空主列表时应直接展示弱相关"
    assert not any("弱相关条目040" in v for v in values), "弱相关展开区也应分页"


# ---------------------------------------------------------------------------
# 4. 预览打开时历史列表让位（search_history.render_search_history）
# ---------------------------------------------------------------------------

def _history_preview_open_script():
    import streamlit as st
    from intelnexus.ui.search_history import render_search_history

    st.session_state["show_search_history"] = True
    st.session_state["current_search_view"] = {
        "id": "unit_test_entry",
        "query": "china",
        "mode": "all",
        "model": "",
        "results_count": 898,
        "timestamp": "2026-10-21T10:37:44",
        "has_snapshot": False,
        "report_content": "# 历史报告内容",
    }
    render_search_history()


def test_preview_open_hides_history_list():
    at = _run(_history_preview_open_script, {}, timeout=60)
    assert not at.exception, at.exception
    # 预览内容出现
    assert any("历史报告内容" in m.value for m in at.markdown), "应渲染该记录内容"
    # 历史列表不再渲染：列表过滤框（key=sh_hist_search）不应存在
    keys = [t.key for t in at.text_input]
    assert "sh_hist_search" not in keys, "预览打开时不应渲染历史列表（过滤框不应存在）"


# ---------------------------------------------------------------------------
# 5. R17 Phase1：历史面板 fragment 化 + 快照签名缓存（search_history.py）
# ---------------------------------------------------------------------------

class _FakeHistoryManager:
    """面板列表测试替身：只提供列表读取接口（不触真实 data/）。"""

    def __init__(self, entries):
        self._entries = entries

    def get_history(self, limit=100, include_deleted=False):
        return self._entries


def _panel_list_script():
    import streamlit as st
    from intelnexus.ui.search_history import render_search_history

    st.session_state["show_search_history"] = True
    render_search_history()


def test_panel_view_click_opens_preview_without_exception(monkeypatch):
    """点「查看」→ 预览出现、列表让位。

    AppTest 的模拟 run 对 fragment 无感知（走整页 run），本用例同时覆盖
    _panel_rerun 的整页回退路径：回退后行为与 Phase1 之前一致。
    """
    entries = [{
        "id": "entry_1", "query": "china", "mode": "all", "model": "",
        "results_count": 5, "timestamp": "2026-10-21T10:00:00",
        "has_snapshot": False, "report_content": "# 面板报告", "deleted": False,
    }]
    from intelnexus.config import history as history_mod
    monkeypatch.setattr(history_mod, "get_history_manager",
                        lambda: _FakeHistoryManager(entries))

    at = _run(_panel_list_script, {}, timeout=60)
    assert not at.exception, at.exception
    assert "sh_hist_search" in [t.key for t in at.text_input], "初始应渲染列表"
    view_btns = [b for b in at.button if b.key == "sh_view_entry_1"]
    assert view_btns, "应渲染 查看 按钮"

    view_btns[0].click().run()
    assert not at.exception, at.exception
    assert any("面板报告" in m.value for m in at.markdown), "点查看后应渲染该记录内容"
    assert "sh_hist_search" not in [t.key for t in at.text_input], "预览打开时列表让位"


def test_snapshot_cached_load_signature_and_copy(tmp_path, monkeypatch):
    """2D：签名缓存——签名命中不重复解析、命中返回副本防渲染侧污染。"""
    import os

    from intelnexus.config import history as history_mod
    from intelnexus.ui.search_history import _load_snapshot_cached

    manager = history_mod.SearchHistory(storage_dir=str(tmp_path))
    kg_file = tmp_path / "kg.html"
    kg_file.write_text("<html>kg</html>", encoding="utf-8")
    result = {
        "query": "china",
        "results": [{"title": "t1", "url": "https://a.example/1"}],
        "filtered": [{"title": "t1", "url": "https://a.example/1"}],
        "streamed_summary": "# 快照报告",
        "kg_html_path": str(kg_file),
    }
    entry = manager.add_search("china", "all", 1, "m",
                               snapshot=manager.build_snapshot(result))
    assert entry["has_snapshot"] is True

    sig = manager.snapshot_signature(entry["id"])
    assert sig is not None and sig[0].endswith("snapshot.json")
    assert manager.snapshot_signature("no-such-id") is None

    monkeypatch.setattr(history_mod, "get_history_manager", lambda: manager)

    s1 = _load_snapshot_cached(entry["id"], sig)
    assert s1["streamed_summary"] == "# 快照报告"
    s1["streamed_summary"] = "MUTATED"
    s2 = _load_snapshot_cached(entry["id"], sig)
    assert s2["streamed_summary"] == "# 快照报告", "命中必须返回副本，防渲染侧污染缓存"

    # 快照文件 mtime 变化 → 签名变化 → 缓存失效重新读盘
    snap_path = manager.snapshots_dir / entry["id"] / "snapshot.json"
    st_info = snap_path.stat()
    os.utime(snap_path, (st_info.st_atime, st_info.st_mtime + 5))
    sig2 = manager.snapshot_signature(entry["id"])
    assert sig2 != sig, "mtime 变化后签名必须不同"
    s3 = _load_snapshot_cached(entry["id"], sig2)
    assert s3["streamed_summary"] == "# 快照报告"
