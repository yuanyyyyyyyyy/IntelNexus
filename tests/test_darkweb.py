"""Dark web search tests: availability switch, aggregation, URL encoding, custom sites."""
from unittest.mock import MagicMock, patch

import pytest

from intelnexus.search_app import darkweb as dw


def _html_response(text, status=200):
    resp = MagicMock()
    resp.status_code = status
    resp.text = text
    return resp


# Ahmia 2026 改版后的真实结果结构：标题在 h4>a，真实地址藏在站方跳转包装的
# redirect_url 参数里，摘要在 h4 之后的 <p>。
AHMIA_HTML = """
<html><body>
<h4><a href="/search/redirect?redirect_url=http%3A%2F%2Fexampleonion1abcd.onion%2Fpage1">Leaked Database</a></h4>
<p>Dump of credentials from a breached forum.</p>
<h4><a href="/search/redirect?redirect_url=http%3A%2F%2Fexampleonion2efgh.onion%2Fpage2">Forum Thread</a></h4>
<p>Discussion thread about the leak.</p>
<h4><a href="http://notonion.com/plain">Skip me</a></h4>
<p>clearnet link, must be filtered</p>
</body></html>
"""

# 壳页：无 h4 结果，只有反爬隐藏 token
AHMIA_SHELL_HTML = """
<html><body>
<form id="searchForm" action="/search/">
  <input type="hidden" name="f119ab" value="156abb">
  <input type="text" name="q">
</form>
<p>we have not deployed non-JavaScript version yet</p>
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

    def fake_ahmia(q, *args, **kwargs):
        # R7b：备用通道会带 trust_env/proxies 等 kwargs 重试
        seen.setdefault(q, 0)
        seen[q] += 1
        return []

    with patch.object(dw, "fetch_ahmia_results", side_effect=fake_ahmia), \
         patch.object(dw, "fetch_onionlink_search", return_value=[]), \
         patch.object(dw, "fetch_tordex_search", return_value=[]), \
         patch.object(dw, "get_custom_onion_sites", return_value=[]):
        dw.get_darkweb_results(["a", "b", "c"])
    # R7b：空结果会触发备用网络通道重试一次，每个查询共执行两次
    assert seen == {"a": 2, "b": 2, "c": 2}


def test_fetch_ahmia_parses_onion_links(monkeypatch):
    monkeypatch.setattr(dw, "ENABLE_DARKWEB", True)
    resp = _html_response(AHMIA_HTML)
    # 实现用 requests.Session()（需保持 cookie 跨两次请求），故 patch Session 而非模块级 get
    with patch.object(dw.requests, "Session") as session_cls:
        session_cls.return_value.get.return_value = resp
        results = dw.fetch_ahmia_results("leak")
    links = [r["link"] for r in results]
    assert "http://exampleonion1abcd.onion/page1" in links
    assert "http://exampleonion2efgh.onion/page2" in links
    # 非 .onion 链接应被过滤
    assert not any("notonion" in l for l in links)
    # 摘要应被带出，供相关性评分使用
    assert results[0]["description"].startswith("Dump of credentials")


def test_fetch_ahmia_encodes_query(monkeypatch):
    monkeypatch.setattr(dw, "ENABLE_DARKWEB", True)
    captured = {}

    def fake_get(url, **kwargs):
        captured["url"] = url
        return _html_response(AHMIA_HTML)

    with patch.object(dw.requests, "Session") as session_cls:
        session_cls.return_value.get.side_effect = fake_get
        dw.fetch_ahmia_results("data breach test")
    assert "data%20breach%20test" in captured["url"]


def test_fetch_ahmia_retries_with_hidden_token(monkeypatch):
    """壳页无结果时应提取隐藏 token 二次请求，并解析出真实 onion 地址。"""
    monkeypatch.setattr(dw, "ENABLE_DARKWEB", True)
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs.get("params")))
        return _html_response(AHMIA_SHELL_HTML if len(calls) == 1 else AHMIA_HTML)

    with patch.object(dw.requests, "Session") as session_cls:
        session_cls.return_value.get.side_effect = fake_get
        results = dw.fetch_ahmia_results("leak")

    assert len(calls) == 2, "壳页无结果时必须带 token 再请求一次"
    assert calls[1][1] == {"q": "leak", "f119ab": "156abb"}
    assert len(results) == 2


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

    def fake_fetch(url, auth=None, tor_port=None):
        captured["auth"] = auth
        return resp

    with patch.object(dw, "fetch_with_auth", side_effect=fake_fetch):
        results = dw.search_custom_onion_site(site, "query")
    # 密码应被解码为明文
    assert captured["auth"]["password"] == raw_pw
    assert len(results) >= 1
