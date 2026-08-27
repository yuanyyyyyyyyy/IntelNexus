"""SearchSourceRegistry：注册、按 mode 查询、collect 跨源去重。"""
from unittest.mock import patch

from intelnexus.core.search.registry import SearchSourceRegistry
from intelnexus.core.search.modes import SEARCH_MODES


def _make_registry():
    """构造 registry 并把全部源替换为可控 stub，避免任何真实网络。"""
    reg = SearchSourceRegistry(news_api_key=None, darkweb_advanced=False, tor_port=9150)
    # 清空用户源；内置源以 stub 替换（测试按需注入 fake search）
    for src in reg.all_sources():
        src.search = lambda query, max_results=20: []
    reg._user_sources = []
    return reg


def test_builtin_sources_registered():
    reg = _make_registry()
    names = {type(s).__name__ for s in reg.all_sources()}
    assert "WebSearchSource" in names
    assert "NewsSearchSource" in names
    assert "DarkWebSource" in names


def test_get_sources_by_mode_filters_by_category():
    reg = _make_registry()
    web_srcs = reg.get_sources_by_mode("web")
    assert all(s.category == "web" for s in web_srcs)

    news_srcs = reg.get_sources_by_mode("news")
    assert all(s.category == "news" for s in news_srcs)

    all_srcs = reg.get_sources_by_mode("all")
    cats = {s.category for s in all_srcs}
    assert "web" in cats and "news" in cats and "darkweb" in cats


def test_disabled_source_excluded():
    reg = _make_registry()
    reg._builtin[0].enabled = False  # 禁用 WebSearchSource
    web_srcs = reg.get_sources_by_mode("web")
    assert all(not isinstance(s, type(reg._builtin[0])) for s in web_srcs)


def test_collect_dedup_across_sources():
    reg = _make_registry()

    dup = {"title": "Dup", "url": "http://dup.com/x", "description": "d", "source": "S"}

    def make_stub(items):
        def _search(query, max_results=20):
            return [dict(i) for i in items]
        return _search

    web_src, news_src, dark_src = (None, None, None)
    for s in reg.all_sources():
        if type(s).__name__ == "WebSearchSource":
            web_src = s
        elif type(s).__name__ == "NewsSearchSource":
            news_src = s
        elif type(s).__name__ == "DarkWebSource":
            dark_src = s
    web_src.search = make_stub([dup, {"title": "A", "url": "http://a.com",
                                      "description": "da", "source": "Web"}])
    news_src.search = make_stub([dict(dup), {"title": "B", "url": "http://b.com",
                                             "description": "db", "source": "News"}])
    dark_src.search = make_stub([])

    results = reg.collect("all", "query", max_results=20, threads=3)

    links = [r["url"] for r in results]
    assert links.count("http://dup.com/x") == 1  # 跨源去重
    assert "http://a.com" in links
    assert "http://b.com" in links
    assert len(results) == 3


def test_collect_empty_when_no_sources():
    reg = _make_registry()
    assert reg.collect("all", "q") == []


def test_mode_categories_known():
    for mode in SEARCH_MODES:
        reg = _make_registry()
        # 不应抛异常
        _ = reg.get_sources_by_mode(mode)


def test_last_error_empty_result_marks_error_and_updates_health():
    """桩源在调用期间写 last_error 且返回 [] → 统计记 error，update_health 收到 error 参数。

    注：_timed_search 在调用 src.search 前会清残留信号（单轮生命周期语义），
    因此桩必须在调用期间写入失败信号，调用前预设的残留会被清除。
    """
    reg = _make_registry()
    src = reg._builtin[0]
    reg._builtin = [src]

    def _search(query, max_results=20):
        src.last_error = "Bing: ConnectionError"
        return []

    src.search = _search

    with patch("intelnexus.core.search.health.update_health") as mock_uh:
        results = reg.collect("all", "q", max_results=5, threads=1)

    assert results == []
    assert reg.last_search_stats[src.name]["status"] == "error"
    assert mock_uh.called
    # update_health 的 error 参数非空（函数内 import，patch 模块属性生效）
    assert any(c.kwargs.get("error") for c in mock_uh.call_args_list)
    # 失败信号被消费后应清空，避免下一轮误判
    assert src.last_error is None


def test_last_error_cleared_on_nonempty_results():
    """非空结果路径：残留的 last_error 应被清除且统计记 ok。"""
    reg = _make_registry()
    src = reg._builtin[0]
    reg._builtin = [src]
    src.search = lambda query, max_results=20: [
        {"title": "T", "url": "http://a.com/x", "description": "d", "source": "S"}]
    src.last_error = "stale error"

    results = reg.collect("all", "q", max_results=5, threads=1)

    assert len(results) == 1
    assert reg.last_search_stats[src.name]["status"] == "ok"
    assert src.last_error is None


def test_uncollected_sources_marked_timeout(monkeypatch):
    """全局超时后、宽限期内仍未完成的源应标 timeout（而非旧的 skipped）。"""
    import time as _time
    monkeypatch.setattr("intelnexus.core.search.registry._GRACE_PERIOD", 0.2)
    reg = _make_registry()
    src = reg._builtin[0]
    reg._builtin = [src]

    def slow_search(query, max_results=20):
        _time.sleep(3)
        return [{"title": "late", "url": "http://late.example.com/a",
                 "description": "d", "source": "S"}]

    src.search = slow_search
    results = reg.collect("all", "q", max_results=5, threads=1, global_timeout=1)

    assert reg.last_search_stats[src.name]["status"] == "timeout"
    # 晚到的结果未被收割进本次返回（宽限期短于慢源剩余耗时）
    assert all(r.get("url") != "http://late.example.com/a" for r in results)


def test_grace_harvest_on_loop_timeout_break(monkeypatch):
    """路径 B：循环体内超时检查触发 break 后仍走宽限收割，晚到成功结果不丢。

    构造：global_timeout 很小，快源完成时已超全局超时（主循环取到其结果后
    break），慢源在宽限期内很快完成 → 其结果必须被收割；且 collected 去重保证
    主循环已收的快源结果不重复。
    """
    import time as _time
    monkeypatch.setattr("intelnexus.core.search.registry._GRACE_PERIOD", 3)
    reg = _make_registry()
    fast_src, slow_src = reg._builtin[0], reg._builtin[1]
    reg._builtin = [fast_src, slow_src]

    def fast_search(query, max_results=20):
        _time.sleep(0.5)  # 完成时已超 global_timeout（0.3s）→ 触发路径 B
        return [{"title": "fast", "url": "http://fast.example.com/a",
                 "description": "d", "source": "S"}]

    def slow_search(query, max_results=20):
        _time.sleep(0.9)  # 宽限期（3s）内完成 → 应被宽限收割
        return [{"title": "slow", "url": "http://slow.example.com/a",
                 "description": "d", "source": "S"}]

    fast_src.search = fast_search
    slow_src.search = slow_search
    results = reg.collect("all", "q", max_results=5, threads=2, global_timeout=0.3)

    urls = [r["url"] for r in results]
    # 慢源晚到结果被宽限收割，不被丢弃（路径 B 与路径 A 口径一致）
    assert "http://slow.example.com/a" in urls
    # 快源结果已被主循环收集，不重复收割（各仅一条）
    assert urls.count("http://fast.example.com/a") == 1
    assert urls.count("http://slow.example.com/a") == 1
