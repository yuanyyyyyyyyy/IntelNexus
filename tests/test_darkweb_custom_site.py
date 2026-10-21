"""R1/R2 回归测试：自定义 onion 站点失败可见化 + 链接归一（2026-10-20）。

独立成文件的原因：test_darkweb.py 内含既有 b64 口令测试夹具，工作区写入
守卫会拦截对它的整文件重写；本文件零凭据字面量，便于维护。
"""
from unittest.mock import MagicMock, patch

import pytest

from intelnexus.search_app import darkweb as dw


def _html_response(text, status=200):
    resp = MagicMock()
    resp.status_code = status
    resp.text = text
    return resp


@pytest.fixture(autouse=True)
def _clean_custom_site_errors():
    """错误登记表是模块级状态，前后各清一次，避免用例间/跨文件泄漏。"""
    dw.CUSTOM_SITE_LAST_ERRORS.clear()
    yield
    dw.CUSTOM_SITE_LAST_ERRORS.clear()


def test_custom_site_error_recorded_on_fetch_failure():
    """fetch 失败（返回 None）时应把原因写进 CUSTOM_SITE_LAST_ERRORS。"""
    site = {"name": "FailSite", "url": "http://fail.onion", "auth": None}
    with patch.object(dw, "fetch_with_auth", return_value=None):
        results = dw.search_custom_onion_site(site, "query")
    assert results == []
    assert "FailSite" in dw.CUSTOM_SITE_LAST_ERRORS
    assert "请求失败" in dw.CUSTOM_SITE_LAST_ERRORS["FailSite"]


def test_custom_site_error_recorded_on_http_500():
    site = {"name": "ErrSite", "url": "http://err.onion", "auth": None}
    with patch.object(dw, "fetch_with_auth",
                      return_value=_html_response("<html></html>", status=500)):
        results = dw.search_custom_onion_site(site, "query")
    assert results == []
    assert dw.CUSTOM_SITE_LAST_ERRORS["ErrSite"] == "HTTP 500"


def test_custom_site_error_cleared_on_success():
    """HTTP 200 且解析出结果时应清除旧错误，不留陈旧归因。"""
    site = {"name": "MySite", "url": "http://mysite.onion", "auth": None}
    html = '<html><body><a href="http://mysite.onion/inner?q=1">Inner Page</a></body></html>'
    dw.CUSTOM_SITE_LAST_ERRORS["MySite"] = "stale"
    with patch.object(dw, "fetch_with_auth", return_value=_html_response(html)):
        results = dw.search_custom_onion_site(site, "query")
    assert len(results) >= 1
    assert "MySite" not in dw.CUSTOM_SITE_LAST_ERRORS


def test_custom_site_zero_results_hint():
    """HTTP 200 但 0 条时应记录软提示（最常见：站点不支持 ?search= 查询）。"""
    site = {"name": "EmptySite", "url": "http://empty.onion", "auth": None}
    with patch.object(dw, "fetch_with_auth",
                      return_value=_html_response("<html><body><p>nothing</p></body></html>")):
        results = dw.search_custom_onion_site(site, "query")
    assert results == []
    assert "?search=" in dw.CUSTOM_SITE_LAST_ERRORS["EmptySite"]


def test_custom_site_relative_onion_link_normalized():
    """R2：带域名但缺 scheme 的 href 应补 http://，而不是硬拼出坏链。"""
    site = {"name": "MySite", "url": "http://mysite.onion", "auth": None}
    html = '<html><body><a href="mysite.onion/thread/1">Thread One</a></body></html>'
    with patch.object(dw, "fetch_with_auth", return_value=_html_response(html)):
        results = dw.search_custom_onion_site(site, "query")
    # 旧实现会拼出 http://mysite.onionmysite.onion/thread/1
    assert results[0]["link"] == "http://mysite.onion/thread/1"
