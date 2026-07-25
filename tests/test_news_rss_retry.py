"""Unit tests for NewsSearch RSS retry logic (search_rss / _fetch_rss_with_retry)."""

from unittest.mock import patch, MagicMock

import pytest
import requests

from shared.search.news import NewsSearch, RSS_FETCH_TIMEOUT


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
