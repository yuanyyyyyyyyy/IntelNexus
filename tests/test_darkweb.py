"""Dark web search tests: availability switch, aggregation, URL encoding, custom sites."""
from unittest.mock import MagicMock, patch

import pytest

from intelnexus.search_app import darkweb as dw


def _html_response(text, status=200):
    resp = MagicMock()
    resp.status_code = status
    resp.text = text
    return resp


AHMIA_HTML = """
<html><body>
<a href="http://exampleonion1abcd.onion/page1">Leaked Database</a>
<a href="http://exampleonion2efgh.onion/page2">Forum Thread</a>
<a href="http://notonion.com/plain">Skip me</a>
</body></html>
"""

ONIONLINK_HTML = """
<html><body>
<a href="http://customonion3ijkl.onion/x">Market Listing</a>
</body></html>
"""


def test_is_available_false_by_default(monkeypatch):
    monkeypatch.setattr(dw, "ENABLE_DARKWEB", False)
    assert dw.is_available() is False


def test_is_available_true_when_enabled(monkeypatch):
    monkeypatch.setattr(dw, "ENABLE_DARKWEB", True)
    assert dw.is_available() is True


def test_get_darkweb_results_disabled_returns_empty(monkeypatch):
    monkeypatch.setattr(dw, "ENABLE_DARKWEB", False)
    with patch.object(dw, "fetch_ahmia_results") as m:
        results = dw.get_darkweb_results("test")
    assert results == []
    m.assert_not_called()


def test_get_darkweb_results_aggregates_ahmia(monkeypatch):
    monkeypatch.setattr(dw, "ENABLE_DARKWEB", True)
    with patch.object(dw, "fetch_ahmia_results", return_value=[
        {"title": "Leaked Database", "link": "http://exampleonion1abcd.onion/page1", "source": "Ahmia"},
        {"title": "Forum Thread", "link": "http://exampleonion2efgh.onion/page2", "source": "Ahmia"},
    ]), patch.object(dw, "fetch_onionlink_search", return_value=[]), \
         patch.object(dw, "fetch_tordex_search", return_value=[]), \
         patch.object(dw, "get_custom_onion_sites", return_value=[]):
        results = dw.get_darkweb_results("data breach")
    assert len(results) == 2
    assert results[0]["source"] == "Ahmia"


def test_get_darkweb_results_dedups_by_link(monkeypatch):
    monkeypatch.setattr(dw, "ENABLE_DARKWEB", True)
    dup = {"title": "X", "link": "http://exampleonion1abcd.onion/page1", "source": "Ahmia"}
    with patch.object(dw, "fetch_ahmia_results", return_value=[dup]), \
         patch.object(dw, "fetch_onionlink_search", return_value=[dict(dup)]), \
         patch.object(dw, "fetch_tordex_search", return_value=[]), \
         patch.object(dw, "get_custom_onion_sites", return_value=[]):
        results = dw.get_darkweb_results("query")
    assert len(results) == 1


def test_get_darkweb_results_list_query(monkeypatch):
    monkeypatch.setattr(dw, "ENABLE_DARKWEB", True)
    seen = {}

    def fake_ahmia(q):
        seen.setdefault(q, 0)
        seen[q] += 1
        return []

    with patch.object(dw, "fetch_ahmia_results", side_effect=fake_ahmia), \
         patch.object(dw, "fetch_onionlink_search", return_value=[]), \
         patch.object(dw, "fetch_tordex_search", return_value=[]), \
         patch.object(dw, "get_custom_onion_sites", return_value=[]):
        dw.get_darkweb_results(["a", "b", "c"])
    assert seen == {"a": 1, "b": 1, "c": 1}


def test_fetch_ahmia_parses_onion_links(monkeypatch):
    monkeypatch.setattr(dw, "ENABLE_DARKWEB", True)
    resp = _html_response(AHMIA_HTML)
    with patch.object(dw, "requests") as req:
        req.get.return_value = resp
        results = dw.fetch_ahmia_results("leak")
    links = [r["link"] for r in results]
    assert "http://exampleonion1abcd.onion/page1" in links
    assert "http://exampleonion2efgh.onion/page2" in links
    # 非 .onion 链接应被过滤
    assert not any("notonion" in l for l in links)


def test_fetch_ahmia_encodes_query(monkeypatch):
    monkeypatch.setattr(dw, "ENABLE_DARKWEB", True)
    captured = {}

    def fake_get(url, **kwargs):
        captured["url"] = url
        return _html_response(AHMIA_HTML)

    with patch.object(dw, "requests") as req:
        req.get.side_effect = fake_get
        dw.fetch_ahmia_results("data breach test")
    assert "data%20breach%20test" in captured["url"]


def test_advanced_mode_calls_tor_engines(monkeypatch):
    monkeypatch.setattr(dw, "ENABLE_DARKWEB", True)
    with patch.object(dw, "fetch_ahmia_results", return_value=[]), \
         patch.object(dw, "fetch_onionlink_search", return_value=[
             {"title": "M", "link": "http://customonion3ijkl.onion/x", "source": "OnionLink"}]), \
         patch.object(dw, "fetch_tordex_search", return_value=[]), \
         patch.object(dw, "get_custom_onion_sites", return_value=[]):
        results = dw.get_darkweb_results("q", advanced_mode=True)
    assert any(r["source"] == "OnionLink" for r in results)


def test_custom_onion_sites_from_env(monkeypatch):
    monkeypatch.setenv("CUSTOM_ONION_SITES",
                       '[{"name": "MySite", "url": "http://mysite.onion", "auth": null}]')
    # 确保文件不存在，避免干扰
    monkeypatch.setattr(dw, "CUSTOM_ONION_SITES", '[{"name": "MySite", "url": "http://mysite.onion", "auth": null}]')
    sites = dw.get_custom_onion_sites()
    assert any(s["name"] == "MySite" for s in sites)


def test_custom_onion_sites_with_ui_sites(monkeypatch):
    monkeypatch.setattr(dw, "CUSTOM_ONION_SITES", "")
    ui_sites = [{"name": "UI", "url": "http://ui.onion"}]
    sites = dw.get_custom_onion_sites(ui_sites=ui_sites)
    assert any(s["name"] == "UI" for s in sites)


def test_search_custom_onion_site_parses_links(monkeypatch):
    monkeypatch.setattr(dw, "ENABLE_DARKWEB", True)
    site = {"name": "MySite", "url": "http://mysite.onion", "auth": None}
    html = '<html><body><a href="http://mysite.onion/inner?q=1">Inner Page</a></body></html>'
    resp = _html_response(html)
    with patch.object(dw, "fetch_with_auth", return_value=resp):
        results = dw.search_custom_onion_site(site, "query")
    assert len(results) >= 1
    assert results[0]["source"] == "MySite"


def test_search_custom_onion_site_decodes_b64_password(monkeypatch):
    import base64
    monkeypatch.setattr(dw, "ENABLE_DARKWEB", True)
    raw_pw = "secret123"
    b64 = base64.b64encode(raw_pw.encode()).decode()
    site = {"name": "AuthSite", "url": "http://auth.onion",
            "auth": {"type": "basic", "username": "u", "password": b64}}
    html = '<html><body><a href="http://auth.onion/result">Auth Result Page</a></body></html>'
    resp = _html_response(html)
    captured = {}

    def fake_fetch(url, auth=None):
        captured["auth"] = auth
        return resp

    with patch.object(dw, "fetch_with_auth", side_effect=fake_fetch):
        results = dw.search_custom_onion_site(site, "query")
    # 密码应被解码为明文
    assert captured["auth"]["password"] == raw_pw
    assert len(results) >= 1
