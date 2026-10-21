"""R10f：OnionLand / Tor66 引擎接线回归（高级模式）。"""
from unittest.mock import MagicMock, patch

from intelnexus.search_app import darkweb as dw


def _resp(html):
    return MagicMock(status_code=200, text=html)


def test_fetch_onionland_parses_onion_links():
    html = '<a href="http://abc.onion/page">Market Item</a>'
    with patch.object(dw.requests, "get", return_value=_resp(html)) as m:
        results = dw.fetch_onionland_search("query", tor_port=2080)
    assert results and results[0]["source"] == "OnionLand"
    assert results[0]["link"] == "http://abc.onion/page"
    assert "socks5h://127.0.0.1:2080" in m.call_args.kwargs["proxies"]["http"]


def test_fetch_tor66_parses_onion_links():
    html = '<a href="http://def.onion/x">Shop Entry</a>'
    with patch.object(dw.requests, "get", return_value=_resp(html)):
        results = dw.fetch_tor66_search("query", tor_port=2080)
    assert results and results[0]["source"] == "Tor66"


def test_advanced_mode_calls_new_engines(monkeypatch):
    monkeypatch.setattr(dw, "ENABLE_DARKWEB", True)
    with patch.object(dw, "fetch_ahmia_results", return_value=[]), \
         patch.object(dw, "fetch_onionlink_search", return_value=[]), \
         patch.object(dw, "fetch_tordex_search", return_value=[]), \
         patch.object(dw, "fetch_onionland_search",
                      return_value=[{"title": "X", "link": "http://x.onion",
                                     "source": "OnionLand"}]), \
         patch.object(dw, "fetch_tor66_search", return_value=[]), \
         patch.object(dw, "get_custom_onion_sites", return_value=[]):
        results = dw.get_darkweb_results("q", advanced_mode=True)
    assert any(r["source"] == "OnionLand" for r in results)
