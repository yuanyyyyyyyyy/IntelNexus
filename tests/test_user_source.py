"""UserSource：rss / web_engine / onion 三种抓取方式与代理收口。"""
from unittest.mock import MagicMock, patch

from intelnexus.core.search.sources.user_source import UserSource


def _resp(text, status=200):
    r = MagicMock()
    r.status_code = status
    r.content = text.encode("utf-8")
    r.text = text
    return r


RSS_XML = """<rss><channel>
<item><title>RSS Item</title><link>http://rss.com/1</link><description>news about query</description></item>
</channel></rss>"""

WEB_HTML = """<html><body>
<a href="http://result.com/a">Result A about query</a>
<a href="http://result.com/b">Result B about query</a>
</body></html>"""

ONION_HTML = """<html><body>
<a href="http://siteabcd.onion/page1">Onion Page about query</a>
</body></html>"""


def test_user_source_rss():
    cfg = {"id": "1", "name": "MyRSS", "url": "http://rss.com/feed?q={query}",
           "fetch_type": "rss", "category": "news", "enabled": True}
    src = UserSource(cfg)
    assert src.category == "news"
    assert src.fetch_type == "rss"
    with patch("intelnexus.core.search.sources.user_source.requests.get",
               return_value=_resp(RSS_XML)) as mg:
        out = src.search("query", max_results=10)
    # 断言代理收口：requires_proxy=False 时不传代理
    _, kwargs = mg.call_args
    assert kwargs.get("proxies") is None
    assert len(out) == 1
    assert out[0]["link"] == "http://rss.com/1"
    assert out[0]["source"] == "MyRSS"


def test_user_source_web_engine():
    cfg = {"id": "2", "name": "MyEngine", "url": "http://engine.com/s?q={query}",
           "fetch_type": "web_engine", "category": "web", "enabled": True}
    src = UserSource(cfg)
    with patch("intelnexus.core.search.sources.user_source.requests.get",
               return_value=_resp(WEB_HTML)):
        out = src.search("query", max_results=10)
    assert len(out) == 2
    assert out[0]["link"] == "http://result.com/a"


def test_user_source_onion_uses_tor_proxy():
    cfg = {"id": "3", "name": "MyOnion", "url": "http://siteabcd.onion",
           "fetch_type": "onion", "category": "darkweb", "enabled": True,
           "requires_proxy": True}
    src = UserSource(cfg)
    assert src.requires_proxy is True
    session_mock = MagicMock()
    session_mock.get.return_value = _resp(ONION_HTML)
    with patch("intelnexus.core.search.sources.user_source.requests.Session",
               return_value=session_mock), \
         patch("intelnexus.core.search.get_http_proxies", return_value={"http": "socks5h://127.0.0.1:9150"}):
        out = src.search("query", max_results=10)
    # 断言走 Tor SOCKS 代理（通过 session.proxies 设置）
    assert "socks5h" in str(session_mock.proxies)
    assert len(out) == 1
    assert ".onion" in out[0]["link"]


def test_user_source_blocks_noise():
    cfg = {"id": "4", "name": "RSS2", "url": "http://rss.com/feed?q={query}",
           "fetch_type": "rss", "category": "news", "enabled": True}
    src = UserSource(cfg)
    noise = """<rss><channel>
    <item><title>Wiki</title><link>https://en.wikipedia.org/wiki/X</link><description>d</description></item>
    </channel></rss>"""
    with patch("intelnexus.core.search.sources.user_source.requests.get", return_value=_resp(noise)):
        out = src.search("query", max_results=10)
    assert out == []  # 域名黑名单命中被过滤
