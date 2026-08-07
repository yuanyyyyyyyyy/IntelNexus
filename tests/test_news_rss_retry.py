"""Unit tests for NewsSearch RSS retry logic (search_rss / _fetch_rss_with_retry)."""

from unittest.mock import patch, MagicMock

import pytest
import requests

from intelnexus.core.search.news import NewsSearch, RSS_FETCH_TIMEOUT


def _make_response(text: str = "<rss></rss>"):
    resp = MagicMock()
    resp.status_code = 200
    resp.content = text.encode("utf-8")
    return resp


def test_fetch_rss_with_retry_succeeds_after_two_failures():
    """前两次抛 RequestException、第三次成功时，应重试 2 次后返回响应。"""
    searcher = NewsSearch()
    bad = [
        requests.exceptions.ReadTimeout("read timeout=10"),
        requests.exceptions.ConnectionError("connection reset"),
    ]
    good = _make_response()

    with patch.object(requests, "get", side_effect=[*bad, good]) as mock_get:
        resp = searcher._fetch_rss_with_retry("https://36kr.com/feed", {}, None)

    assert resp is good
    assert mock_get.call_count == 3
    # 超时阈值应为统一的 10s
    _, kwargs = mock_get.call_args_list[0]
    assert kwargs["timeout"] == RSS_FETCH_TIMEOUT


def test_fetch_rss_with_retry_exhausted_raises():
    """始终失败时，应在重试耗尽后抛出最后一个 RequestException。"""
    searcher = NewsSearch()
    err = requests.exceptions.ConnectTimeout("connect timeout")

    with patch.object(requests, "get", side_effect=err):
        with pytest.raises(requests.exceptions.RequestException):
            searcher._fetch_rss_with_retry("https://36kr.com/feed", {}, None, max_retries=2)


def test_search_rss_skips_source_on_persistent_failure():
    """search_rss 面对持续不可达的源应记 warning 并跳过（不崩溃、返回其它源结果）。"""
    searcher = NewsSearch()
    err = requests.exceptions.ReadTimeout("read timeout=10")

    # 仅留一个易控的源，验证失败路径不抛异常
    with patch.object(searcher, "_fetch_rss_with_retry", side_effect=err), \
         patch("shared.search.news.RSS_SOURCES", [{"name": "36氪", "url": "https://36kr.com/feed", "requires_proxy": False}]):
        results = searcher.search_rss("AI", max_results=5)

    assert results == []


def test_search_newsapi_no_client_returns_empty():
    """未配置 NewsAPI client 时，search_newsapi 直接返回空列表。"""
    searcher = NewsSearch()
    assert searcher.news_client is None
    assert searcher.search_newsapi("AI") == []


def test_search_newsapi_with_client_parses_articles():
    """配置了 client 时，应把 articles 映射为目标结构。"""
    searcher = NewsSearch()
    fake_client = MagicMock()
    fake_client.get_everything.return_value = {
        "status": "ok",
        "articles": [
            {
                "title": "AI breakthrough",
                "description": "a long description " * 50,
                "content": "full content",
                "author": "Jane",
                "source": {"name": "Example"},
                "url": "https://example.com/ai",
                "publishedAt": "2024-01-01",
                "urlToImage": "https://example.com/img.png",
            }
        ],
    }
    searcher.news_client = fake_client
    results = searcher.search_newsapi("AI", max_results=10)
    assert len(results) == 1
    item = results[0]
    assert item["title"] == "AI breakthrough"
    assert item["source"] == "Example"
    assert item["url"] == "https://example.com/ai"
    assert item["image_url"] == "https://example.com/img.png"
    # description 应被截断到 300
    assert len(item["description"]) == 300


def test_search_rss_skips_proxy_source_without_proxy():
    """未配置代理时，requires_proxy=True 的源应被跳过（不发起请求）。"""
    searcher = NewsSearch()

    def fake_fetch(url, headers, proxies, timeout=RSS_FETCH_TIMEOUT, max_retries=2):
        # 若被调用则说明未跳过，直接报错让测试暴露
        raise AssertionError(f"代理源不应被请求: {url}")

    with patch.object(searcher, "_fetch_rss_with_retry", side_effect=fake_fetch), \
         patch("shared.search.news.get_http_proxies", return_value=None), \
         patch("shared.search.news.RSS_SOURCES", [
             {"name": "Google News", "url": "https://news.google.com/rss/search?q={query}", "requires_proxy": True},
             {"name": "36氪", "url": "https://36kr.com/feed", "requires_proxy": False},
         ]):
        results = searcher.search_rss("AI", max_results=5)
    assert results == []


def test_search_rss_parses_items_and_filters_blocked():
    """search_rss 应解析 item、过滤黑名单域名、对查询源做相关性过滤。"""
    searcher = NewsSearch()
    rss = """<?xml version="1.0"?>
    <rss version="2.0"><channel>
      <item><title>AI Security Update</title>
        <link>https://news.example.com/ai</link>
        <description>AI security patch released</description>
        <pubDate>2024-01-01</pubDate></item>
      <item><title>Wiki AI</title>
        <link>https://en.wikipedia.org/wiki/AI</link>
        <description>encyclopedia</description></item>
    </channel></rss>"""
    resp = _make_response(rss)

    with patch.object(searcher, "_fetch_rss_with_retry", return_value=resp), \
         patch("shared.search.news.get_http_proxies", return_value=None), \
         patch("shared.search.news.RSS_SOURCES", [
             {"name": "Bing News", "url": "https://www.bing.com/news/search?q={query}&format=rss", "requires_proxy": False},
         ]):
        results = searcher.search_rss("AI security", max_results=10)

    links = [r["url"] for r in results]
    assert "https://news.example.com/ai" in links
    assert not any("wikipedia" in l for l in links)


def test_search_aggregates_and_dedups():
    """NewsSearch.search 应并发聚合多个源并去重。"""
    searcher = NewsSearch()
    rss_item = {
        "title": "AI News", "description": "d", "content": "c", "author": "",
        "source": "36氪", "url": "https://news.example.com/ai", "published_at": "", "image_url": "",
    }

    def fake_rss(query, max_results=10):
        return [dict(rss_item)]

    def fake_bing(query, max_results=10):
        return [dict(rss_item), {"title": "Bing", "url": "https://bing.example.com/x", "description": "d",
                                  "content": "c", "author": "", "source": "Bing News", "published_at": "", "image_url": ""}]

    with patch.object(searcher, "search_rss", side_effect=fake_rss), \
         patch.object(searcher, "search_bing_news", side_effect=fake_bing), \
         patch.object(searcher, "search_google_news", side_effect=lambda *a, **k: []), \
         patch("shared.search.news.get_http_proxies", return_value=None):
        results = searcher.search("AI", max_results=10)

    # 两个源都返回了相同的 news.example.com/ai，应去重为一条
    dup = [r for r in results if r["url"] == "https://news.example.com/ai"]
    assert len(dup) == 1
    assert any(r["url"] == "https://bing.example.com/x" for r in results)


def test_search_skips_google_without_proxy():
    """未配置代理时，search 不应调用 google news。"""
    searcher = NewsSearch()
    called = {"google": False}

    with patch.object(searcher, "search_rss", return_value=[]), \
         patch.object(searcher, "search_bing_news", return_value=[]), \
         patch.object(searcher, "search_google_news", side_effect=lambda *a, **k: called.__setitem__("google", True) or []), \
         patch("shared.search.news.get_http_proxies", return_value=None):
        searcher.search("AI")
    assert called["google"] is False
