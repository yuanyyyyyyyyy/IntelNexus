"""Web/News/DarkWeb 适配器薄包测试（mock 底层 get_*_results）。"""
from unittest.mock import patch

from intelnexus.core.search.sources.web_source import WebSearchSource
from intelnexus.core.search.sources.news_source import NewsSearchSource
from intelnexus.core.search.sources.darkweb_source import DarkWebSource


def test_web_adapter_normalizes():
    raw = [{"title": "T", "link": "http://b.com", "description": "d", "source": "Bing"}]
    with patch("shared.search.sources.web_source.get_web_results", return_value=raw):
        src = WebSearchSource()
        out = src.search("query", max_results=25)
    assert len(out) == 1
    assert out[0]["link"] == "http://b.com"
    assert out[0]["category"] == "web"
    assert out[0]["source"] == "Bing"


def test_news_adapter_normalizes():
    raw = [{"title": "N", "url": "http://n.com", "description": "d", "source": "TechCrunch"}]
    with patch("shared.search.sources.news_source.get_news_results", return_value=raw):
        src = NewsSearchSource(api_key="k")
        out = src.search("query", max_results=15)
    assert len(out) == 1
    assert out[0]["link"] == "http://n.com"  # url -> link
    assert out[0]["category"] == "news"


def test_darkweb_adapter_respects_availability():
    with patch("shared.search.sources.darkweb_source.darkweb_available", return_value=False):
        src = DarkWebSource()
        assert src.search("query") == []

    raw = [{"title": "O", "link": "http://x.onion/p", "source": "Ahmia"}]
    with patch("shared.search.sources.darkweb_source.darkweb_available", return_value=True), \
         patch("shared.search.sources.darkweb_source.get_darkweb_results", return_value=raw):
        src = DarkWebSource(advanced_mode=True, tor_port=9150)
        out = src.search("query")
    assert len(out) == 1
    assert out[0]["category"] == "darkweb"
    assert out[0]["link"] == "http://x.onion/p"


def test_darkweb_adapter_passes_advanced_params():
    captured = {}

    def fake(query, max_workers, advanced_mode, tor_port, ui_sites):
        captured.update(dict(advanced_mode=advanced_mode, tor_port=tor_port, ui_sites=ui_sites))
        return []

    with patch("shared.search.sources.darkweb_source.darkweb_available", return_value=True), \
         patch("shared.search.sources.darkweb_source.get_darkweb_results", side_effect=fake):
        DarkWebSource(advanced_mode=True, tor_port=1234, ui_sites=[{"name": "u"}]).search("q")
    assert captured["advanced_mode"] is True
    assert captured["tor_port"] == 1234
    assert captured["ui_sites"] == [{"name": "u"}]
