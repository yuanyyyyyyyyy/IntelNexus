"""SearchSourceRegistry：注册、按 mode 查询、collect 跨源去重。"""
from unittest.mock import patch

from shared.search.registry import SearchSourceRegistry
from shared.search.modes import SEARCH_MODES


def _make_registry():
    """构造 registry 并替换内置源 search 行为，避免真实网络。"""
    reg = SearchSourceRegistry(news_api_key=None, darkweb_advanced=False, tor_port=9150)
    # 清空用户源，保证测试确定性
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

    dup = {"title": "Dup", "link": "http://dup.com/x", "description": "d", "source": "S"}

    def fake_web(query, max_workers, max_results):
        return [dup, {"title": "A", "link": "http://a.com", "description": "da", "source": "Web"}]

    def fake_news(query, max_results, api_key=None):
        return [dict(dup), {"title": "B", "link": "http://b.com", "description": "db", "source": "News"}]

    def fake_darkweb(query, max_workers, advanced_mode, tor_port, ui_sites):
        return []

    with patch("shared.search.sources.web_source.get_web_results", side_effect=fake_web), \
         patch("shared.search.sources.news_source.get_news_results", side_effect=fake_news), \
         patch("shared.search.sources.darkweb_source.get_darkweb_results", side_effect=fake_darkweb), \
         patch("shared.search.sources.darkweb_source.darkweb_available", return_value=True):
        results = reg.collect("all", "query", max_results=20, threads=3)

    links = [r["link"] for r in results]
    assert links.count("http://dup.com/x") == 1  # 跨源去重
    assert "http://a.com" in links
    assert "http://b.com" in links
    assert len(results) == 3


def test_collect_empty_when_no_sources():
    reg = _make_registry()
    with patch("shared.search.sources.web_source.get_web_results", return_value=[]), \
         patch("shared.search.sources.news_source.get_news_results", return_value=[]), \
         patch("shared.search.sources.darkweb_source.get_darkweb_results", return_value=[]), \
         patch("shared.search.sources.darkweb_source.darkweb_available", return_value=True):
        assert reg.collect("all", "q") == []


def test_mode_categories_known():
    for mode in SEARCH_MODES:
        reg = _make_registry()
        # 不应抛异常
        _ = reg.get_sources_by_mode(mode)
