"""Web/News/DarkWeb 适配器薄包测试（mock 底层 get_*_results）。"""
from unittest.mock import patch

from intelnexus.core.search.sources.web_source import WebSearchSource
from intelnexus.core.search.sources.news_source import NewsSearchSource
from intelnexus.core.search.sources.darkweb_source import DarkWebSource


def test_web_adapter_normalizes():
    raw = [{"title": "T", "link": "http://b.com", "description": "d", "source": "Bing"}]
    with patch("intelnexus.core.search.sources.web_source.get_web_results", return_value=raw):
        src = WebSearchSource()
        out = src.search("query", max_results=25)
    assert len(out) == 1
    assert out[0]["url"] == "http://b.com"
    assert out[0]["category"] == "web"
    assert out[0]["source"] == "Bing"


def test_web_adapter_records_last_error_on_exception():
    """底层 get_web_results 抛异常：适配器返回 [] 且 last_error 非空（含异常类型）。"""
    with patch("intelnexus.core.search.sources.web_source.get_web_results",
               side_effect=RuntimeError("proxy unreachable")):
        src = WebSearchSource()
        out = src.search("query", max_results=25)
    assert out == []
    assert src.last_error
    assert "RuntimeError" in src.last_error
    assert len(src.last_error) <= 200


def test_web_adapter_aggregates_engine_errors_on_empty():
    """空结果且引擎有失败记录：汇总写入 last_error（截断 200 字符）。"""
    with patch("intelnexus.core.search.sources.web_source.get_web_results", return_value=[]), \
         patch("intelnexus.core.search.sources.web_source.LAST_WEB_ERRORS",
               ["Bing: ConnectionError", "Baidu: Timeout"]):
        src = WebSearchSource()
        out = src.search("query")
    assert out == []
    assert "Bing: ConnectionError" in src.last_error
    assert len(src.last_error) <= 200


def test_news_adapter_normalizes():
    raw = [{"title": "N", "url": "http://n.com", "description": "d", "source": "TechCrunch"}]
    with patch("intelnexus.core.search.sources.news_source.get_news_results", return_value=raw):
        src = NewsSearchSource(api_key="k")
        out = src.search("query", max_results=15)
    assert len(out) == 1
    assert out[0]["url"] == "http://n.com"  
    assert out[0]["category"] == "news"


def test_news_adapter_records_last_error_on_exception():
    """底层 get_news_results 抛异常：适配器返回 [] 且 last_error 非空（含异常类型）。
    news 模式下 News 常为唯一源，全失败必须可辨识，不得误报「无结果」。
    """
    with patch("intelnexus.core.search.sources.news_source.get_news_results",
               side_effect=RuntimeError("rss unreachable")):
        src = NewsSearchSource(api_key="k")
        out = src.search("query")
    assert out == []
    assert src.last_error
    assert "RuntimeError" in src.last_error
    assert len(src.last_error) <= 200


def test_news_adapter_aggregates_subsource_errors_on_empty():
    """空结果且子源有失败记录：锁内聚合写入 last_error（截断 200 字符）。"""
    with patch("intelnexus.core.search.sources.news_source.get_news_results", return_value=[]), \
         patch("intelnexus.core.search.sources.news_source.LAST_NEWS_ERRORS",
               ["TechCrunch RSS: Timeout", "Bing News: HTTP 403"]):
        src = NewsSearchSource(api_key="k")
        out = src.search("query")
    assert out == []
    assert "TechCrunch RSS: Timeout" in src.last_error
    assert len(src.last_error) <= 200


def test_news_adapter_empty_without_errors_is_not_failure():
    """空结果且无失败记录（正常无结果）：last_error 保持 None，不误判失败。"""
    with patch("intelnexus.core.search.sources.news_source.get_news_results", return_value=[]), \
         patch("intelnexus.core.search.sources.news_source.LAST_NEWS_ERRORS", []):
        src = NewsSearchSource(api_key="k")
        out = src.search("query")
    assert out == []
    assert src.last_error is None


def test_darkweb_adapter_respects_availability():
    with patch("intelnexus.core.search.sources.darkweb_source.darkweb_available", return_value=False):
        src = DarkWebSource()
        assert src.search("query") == []

    raw = [{"title": "O", "link": "http://x.onion/p", "source": "Ahmia"}]
    with patch("intelnexus.core.search.sources.darkweb_source.darkweb_available", return_value=True), \
         patch("intelnexus.core.search.sources.darkweb_source.get_darkweb_results", return_value=raw):
        src = DarkWebSource(advanced_mode=True, tor_port=9150)
        out = src.search("query")
    assert len(out) == 1
    assert out[0]["category"] == "darkweb"
    assert out[0]["url"] == "http://x.onion/p"


def test_darkweb_adapter_passes_advanced_params():
    captured = {}

    def fake(query, max_workers, advanced_mode, tor_port, ui_sites):
        captured.update(dict(advanced_mode=advanced_mode, tor_port=tor_port, ui_sites=ui_sites))
        return []

    with patch("intelnexus.core.search.sources.darkweb_source.darkweb_available", return_value=True), \
         patch("intelnexus.core.search.sources.darkweb_source.get_darkweb_results", side_effect=fake):
        DarkWebSource(advanced_mode=True, tor_port=1234, ui_sites=[{"name": "u"}]).search("q")
    assert captured["advanced_mode"] is True
    assert captured["tor_port"] == 1234
    assert captured["ui_sites"] == [{"name": "u"}]
