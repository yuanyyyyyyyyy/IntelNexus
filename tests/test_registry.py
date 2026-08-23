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
