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
    _patch_healthy(monkeypatch)  # 隔离持久化健康状态，避免历史 down 条目剔除本源
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
    """全局超时触发后仍走宽限收割：晚到的成功结果不被丢弃，且不重复收割。

    契约：快源完成时已超全局超时（主循环随后 break/抛超时），慢源在宽限期内
    完成 → 其结果必须被收割；collected 去重保证主循环已收的快源结果不重复。

    时序加固：用闸门编排两个源的先后，替代旧的 0.3/0.5/0.9/3 秒紧耦合时长
    （机器负载高时 sleep 被拉长会随机失效，本用例曾在负载下偶发失败）——
    快源刻意睡过 global_timeout，慢源等快源结束放行后立即返回。

    注：两条超时退出路径（循环体内超时 break ／ as_completed 抛超时）最终都调用
    同一个 _harvest()，且循环体内那条需要「future 在提交开销窗口内完成」才可能
    进入（as_completed 的 timeout 通常先到期），实际几乎总走 as_completed 那条。
    因此本用例断言的是**宽限收割契约**本身，与命中哪条分支无关。
    """
    import threading
    import time as _time
    _patch_healthy(monkeypatch)  # 隔离持久化健康状态，避免历史 down 条目剔除本源
    monkeypatch.setattr("intelnexus.core.search.registry._GRACE_PERIOD", 15)
    reg = _make_registry()
    fast_src, slow_src = reg._builtin[0], reg._builtin[1]
    reg._builtin = [fast_src, slow_src]

    release_slow = threading.Event()

    def fast_search(query, max_results=20):
        # 睡过 global_timeout(2s)：主循环取到其结果/超时时，慢源必然还在跑
        _time.sleep(2.5)
        release_slow.set()  # 快源结束才放行慢源 → 慢源必然「晚于快源」完成
        return [{"title": "fast", "url": "http://fast.example.com/a",
                 "description": "d", "source": "S"}]

    def slow_search(query, max_results=20):
        # 不再依赖固定 sleep：等快源放行后立即返回，稳定落在宽限期内
        release_slow.wait(timeout=30)
        return [{"title": "slow", "url": "http://slow.example.com/a",
                 "description": "d", "source": "S"}]

    fast_src.search = fast_search
    slow_src.search = slow_search
    results = reg.collect("all", "q", max_results=5, threads=2, global_timeout=2.0)

    urls = [r["url"] for r in results]
    # 慢源晚到结果被宽限收割，不被丢弃（两条超时退出路径口径一致）
    assert "http://slow.example.com/a" in urls
    # 两源各被收割恰好一次：快源由 _harvest 宽限收割（或主循环直接收集），
    # collected 集合保证不会重复入库
    assert urls.count("http://fast.example.com/a") == 1
    assert urls.count("http://slow.example.com/a") == 1


# ---------------------------------------------------------------------------
# 小红书源注册 + 源权重键名对齐
# ---------------------------------------------------------------------------

def _patch_healthy(monkeypatch):
    """隔离持久化健康状态：全部源视为 healthy，避免历史 down 条目影响用例。"""
    from intelnexus.core.search.health import SourceHealth
    monkeypatch.setattr(
        "intelnexus.core.search.health.get_health",
        lambda name: SourceHealth(source_name=name))


def test_xiaohongshu_source_registered_when_enabled(monkeypatch):
    monkeypatch.setattr("intelnexus.core.search.registry.ENABLE_XIAOHONGSHU", True)
    reg = SearchSourceRegistry(news_api_key=None)
    names = {type(s).__name__ for s in reg.all_sources()}
    assert "XiaohongshuSource" in names
    # 归入 custom 类别 → 仅 all 模式命中
    xhs = next(s for s in reg.all_sources() if type(s).__name__ == "XiaohongshuSource")
    assert xhs.category == "custom"


def test_xiaohongshu_source_absent_when_disabled(monkeypatch):
    monkeypatch.setattr("intelnexus.core.search.registry.ENABLE_XIAOHONGSHU", False)
    reg = SearchSourceRegistry(news_api_key=None)
    names = {type(s).__name__ for s in reg.all_sources()}
    assert "XiaohongshuSource" not in names


def test_source_weight_applied_by_actual_source_name(monkeypatch):
    """权重键须与 src.name 对齐（回归：曾以类名作键导致 get(name) 恒为 1.0）。"""
    _patch_healthy(monkeypatch)
    reg = _make_registry()
    src = reg._builtin[0]
    src.name = "NVD"
    src.search = lambda query, max_results=20: [
        {"title": "CVE-2025-0001", "url": "http://nvd.example/1",
         "description": "d", "source": "NVD"}]
    reg._builtin = [src]

    out = reg.collect("all", "q", max_results=5, threads=1)

    assert len(out) == 1
    assert out[0]["_source_weight"] == 2.0


def test_cjk_query_downweights_en_only_by_actual_name(monkeypatch):
    """中文查询对英文专属源降权（回归：en_only 曾以类名作键而失效）。"""
    _patch_healthy(monkeypatch)
    reg = _make_registry()
    src = reg._builtin[0]
    src.name = "HackerNews"
    src.search = lambda query, max_results=20: [
        {"title": "English Security Post", "url": "http://hn.example/1",
         "description": "d", "source": "HackerNews"}]
    reg._builtin = [src]

    out = reg.collect("all", "漏洞", max_results=5, threads=1)

    assert len(out) == 1
    assert out[0]["_source_weight"] == 0.7

