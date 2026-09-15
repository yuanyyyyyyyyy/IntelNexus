"""XiaohongshuSource：通用站内检索源的薄子类。

小红书不再依赖公共网页引擎（已实测其忽略 site: 算子），改为经
「站内检索后端」（Google CSE / Brave）取数；本源负责域名白名单收口与
last_error 四态语义（细节见 tests/test_site_scoped_source.py）。
"""
from unittest.mock import patch

import pytest

from intelnexus.core.search.sitesearch.base import SiteSearchError
from intelnexus.core.search.sources.xiaohongshu_source import XiaohongshuSource


class _StubBackend:
    name = "GoogleCSE"

    def __init__(self, rows=None, error=None):
        self.rows = list(rows or [])
        self.error = error
        self.calls = []

    def is_configured(self):
        return True

    def search(self, query, domain, max_results=10):
        self.calls.append((query, domain, max_results))
        if self.error is not None:
            raise self.error
        return list(self.rows)


def _row(url, title="笔记"):
    return {"title": title, "url": url, "description": "d", "source": "GoogleCSE"}


def _source(backend, **over):
    kwargs = dict(backend=backend)
    kwargs.update(over)
    return XiaohongshuSource(**kwargs)


# ---------------------------------------------------------------------------
# 取数参数：站内限定交给后端，源只传原始查询 + 目标域名
# ---------------------------------------------------------------------------

def test_passes_raw_query_and_xhs_domain_to_backend():
    be = _StubBackend()
    _source(be).search("数据泄露", max_results=10)
    assert be.calls == [("数据泄露", "xiaohongshu.com", 10)]


def test_multisubquery_passed_through_unchanged():
    """子查询拆分交由后端处理，源不干预（不再自行拼 site:）。"""
    be = _StubBackend()
    _source(be).search("暗网|勒索软件", max_results=5)
    assert be.calls == [("暗网|勒索软件", "xiaohongshu.com", 5)]


def test_normalizes_fields_and_category():
    be = _StubBackend([_row("https://www.xiaohongshu.com/explore/1")])
    out = _source(be).search("q")
    assert len(out) == 1
    assert out[0]["category"] == "custom"
    # 来源归因给站点本身，而非检索后端（否则 UI/可信度会显示 GoogleCSE）
    assert out[0]["source"] == "Xiaohongshu"
    for field in ("title", "url", "description", "source", "category",
                  "published_at", "metadata"):
        assert field in out[0]


# ---------------------------------------------------------------------------
# 域名白名单（主站 + 短链）
# ---------------------------------------------------------------------------

def test_keeps_only_xiaohongshu_hosts():
    be = _StubBackend([
        _row("https://www.xiaohongshu.com/explore/abc"),
        _row("https://xiaohongshu.com/discovery/item/def"),
        _row("https://xhslink.com/xyz"),
        _row("https://www.weibo.com/1"),
        _row("https://fake-xiaohongshu.com.evil.com/a"),
    ])
    out = _source(be).search("q")
    assert {r["url"] for r in out} == {
        "https://www.xiaohongshu.com/explore/abc",
        "https://xiaohongshu.com/discovery/item/def",
        "https://xhslink.com/xyz",
    }


@pytest.mark.parametrize("url,expected", [
    ("https://www.xiaohongshu.com/explore/a", True),
    ("https://xiaohongshu.com/x", True),
    ("https://xhslink.com/x", True),
    ("https://sub.xhslink.com/x", True),
    ("http://xiaohongshu.com/x", True),
    # 伪装/近似域一律拒绝
    ("https://xiaohongshu.com.evil.com/a", False),
    ("https://fake-xiaohongshu.com.evil.com/a", False),
    ("https://notxiaohongshu.com/a", False),
    ("https://evil-xiaohongshu.com/a", False),
    ("https://xiaohongshu.com@evil.com/a", False),
    ("https://www.weibo.com/a", False),
])
def test_host_whitelist_rejects_lookalike_domains(url, expected):
    assert XiaohongshuSource._is_xhs_url(url) is expected


# ---------------------------------------------------------------------------
# last_error 四态
# ---------------------------------------------------------------------------

def test_not_configured_backend_is_explicit():
    """未配置站内检索后端：必须给出可操作的失败信号，不得静默返回空。"""
    src = XiaohongshuSource(backend_factory=lambda: None)
    out = src.search("数据泄露")
    assert out == []
    assert src.last_error and "未配置" in src.last_error
    assert len(src.last_error) <= 200


def test_quota_error_is_reported():
    src = _source(_StubBackend(error=SiteSearchError(
        "GoogleCSE 额度耗尽或超速（HTTP 403: dailyLimitExceeded）", kind="quota")))
    out = src.search("q")
    assert out == []
    assert src.last_error and "额度" in src.last_error


def test_network_error_is_reported():
    src = _source(_StubBackend(error=SiteSearchError("网络不可达", kind="network")))
    out = src.search("q")
    assert out == []
    assert src.last_error and "不可达" in src.last_error


def test_empty_results_is_not_a_failure():
    src = _source(_StubBackend([]))
    assert src.search("q") == []
    assert src.last_error is None


def test_success_clears_stale_error():
    src = _source(_StubBackend([_row("https://www.xiaohongshu.com/explore/1")]))
    src.last_error = "stale"
    out = src.search("q")
    assert len(out) == 1
    assert src.last_error is None


def test_blank_query_returns_empty_without_calling_backend():
    be = _StubBackend()
    assert _source(be).search("   ") == []
    assert be.calls == []


# ---------------------------------------------------------------------------
# 工厂插件：默认从 sitesearch 工厂取后端
# ---------------------------------------------------------------------------

def test_default_backend_factory_uses_sitesearch_factory():
    # 标题需与查询相关：本用例验证的是「默认工厂是否从 sitesearch 取后端」，
    # 若用占位标题会被相关性过滤掉，断言就从「接线」变成了「过滤」的附庸
    be = _StubBackend([_row("https://www.xiaohongshu.com/explore/1",
                            title="漏洞应急响应笔记")])
    with patch("intelnexus.core.search.sitesearch.get_site_search_backend",
               return_value=be) as mock_get:
        out = XiaohongshuSource().search("漏洞")
    assert mock_get.called
    assert len(out) == 1
