"""通用站内检索源 SiteScopedSource 单测。

覆盖：域名传递与结果上限、主机白名单收口矩阵（含同形域/userinfo 伪装）、
last_error 四态（未配置 / 额度耗尽 / 不可达 / 正常无结果）、成功清空、空查询。
"""
import pytest

from intelnexus.core.search.sitesearch.base import SiteSearchError
from intelnexus.core.search.sources.site_scoped_source import SiteScopedSource


class _StubBackend:
    """可编程后端桩：记录调用参数，按需返回结果或抛错。"""

    name = "Stub"

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


def _source(backend, **over):
    kwargs = dict(name="Example", domains=("example.com",),
                  allowed_hosts=("example.com",), backend=backend)
    kwargs.update(over)
    return SiteScopedSource(**kwargs)


def _row(url, title="T"):
    return {"title": title, "url": url, "description": "d", "source": "Stub"}


# ---------------------------------------------------------------------------
# 取数与参数传递
# ---------------------------------------------------------------------------

def test_passes_raw_query_and_domain_to_backend():
    """源不做 site: 改写（那是后端职责），只传原始查询 + 目标域名。"""
    be = _StubBackend()
    _source(be).search("数据泄露", max_results=7)
    assert be.calls == [("数据泄露", "example.com", 7)]


def test_uses_first_domain_when_multiple_given():
    be = _StubBackend()
    _source(be, domains=("a.com", "b.com"), allowed_hosts=("a.com", "b.com")) \
        .search("q")
    assert be.calls[0][1] == "a.com"


def test_truncates_to_max_results():
    be = _StubBackend([_row(f"https://example.com/{i}") for i in range(5)])
    out = _source(be).search("q", max_results=2)
    assert len(out) == 2


def test_normalizes_and_sets_category():
    be = _StubBackend([_row("https://example.com/1")])
    out = _source(be).search("q")
    assert out[0]["category"] == "custom"
    assert out[0]["source"] == "Stub"  # 保留后端给出的 source
    for field in ("title", "url", "description", "source", "category",
                  "published_at", "metadata"):
        assert field in out[0]


def test_display_source_overrides_source_when_configured():
    be = _StubBackend([_row("https://example.com/1")])
    out = _source(be, display_source="ExampleSite").search("q")
    assert out[0]["source"] == "ExampleSite"


# ---------------------------------------------------------------------------
# 主机白名单
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("url,expected", [
    ("https://example.com/a", True),
    ("https://www.example.com/a", True),
    ("https://sub.example.com/a", True),
    ("http://example.com/a", True),
    # 伪装/近似域一律拒绝
    ("https://example.com.evil.com/a", False),
    ("https://fake-example.com.evil.com/a", False),
    ("https://notexample.com/a", False),
    ("https://evil-example.com/a", False),
    ("https://example.com@evil.com/a", False),
    ("https://other.com/a", False),
])
def test_host_whitelist_rejects_lookalike_domains(url, expected):
    assert SiteScopedSource.host_allowed(url, ("example.com",)) is expected


def test_offsite_results_are_dropped():
    be = _StubBackend([
        _row("https://www.example.com/keep"),
        _row("https://www.other.com/drop"),
    ])
    out = _source(be).search("q")
    assert [r["url"] for r in out] == ["https://www.example.com/keep"]


# ---------------------------------------------------------------------------
# last_error 四态
# ---------------------------------------------------------------------------

def test_not_configured_backend_is_explicit():
    """未配置后端：不得静默返回空，须给出可操作的失败信号。"""
    src = SiteScopedSource(name="Example", domains=("example.com",),
                           allowed_hosts=("example.com",),
                           backend_factory=lambda: None)
    out = src.search("q")
    assert out == []
    assert src.last_error and ("未配置" in src.last_error)
    assert len(src.last_error) <= 200


def test_quota_error_is_reported():
    src = _source(_StubBackend(error=SiteSearchError("额度耗尽", kind="quota")))
    out = src.search("q")
    assert out == []
    assert src.last_error and "额度" in src.last_error


def test_network_error_is_reported():
    src = _source(_StubBackend(error=SiteSearchError("不可达", kind="network")))
    out = src.search("q")
    assert out == []
    assert src.last_error and "不可达" in src.last_error


def test_unexpected_exception_is_reported():
    src = _source(_StubBackend(error=RuntimeError("boom")))
    out = src.search("q")
    assert out == []
    assert src.last_error and "RuntimeError" in src.last_error
    assert len(src.last_error) <= 200


def test_empty_results_is_not_a_failure():
    """正常无结果：last_error 保持 None。"""
    src = _source(_StubBackend([]))
    assert src.search("q") == []
    assert src.last_error is None


def test_all_filtered_offsite_is_not_a_failure():
    """结果全被白名单滤除属正常过滤，不算失败。"""
    src = _source(_StubBackend([_row("https://other.com/x")]))
    assert src.search("q") == []
    assert src.last_error is None


def test_success_clears_stale_error():
    src = _source(_StubBackend([_row("https://example.com/1")]))
    src.last_error = "stale"
    out = src.search("q")
    assert len(out) == 1
    assert src.last_error is None


def test_blank_query_returns_empty_without_calling_backend():
    be = _StubBackend()
    src = _source(be)
    assert src.search("   ") == []
    assert be.calls == []
    assert src.last_error is None


# ---------------------------------------------------------------------------
# 严格区分「工厂报错」与「未配置」；凭证脱敏
# ---------------------------------------------------------------------------

def test_backend_factory_failure_is_not_reported_as_unconfigured():
    """回归：工厂抛错时不得显示为「未配置」，否则把配置读取故障误导成没填 Key。"""

    def _boom():
        raise RuntimeError("cfg boom")

    src = SiteScopedSource(name="Example", domains=("example.com",),
                           allowed_hosts=("example.com",),
                           backend_factory=_boom)
    out = src.search("q")
    assert out == []
    assert src.last_error and "RuntimeError" in src.last_error
    assert "未配置" not in src.last_error


def test_last_error_redacts_credentials():
    """回归：底层异常消息可能含带 query 的完整 URL，不得把 Key 写进 last_error。"""
    src = _source(_StubBackend(error=SiteSearchError(
        "网络不可达: ConnectionError: Max retries exceeded with url: "
        "/v1?key=SECRETKEY123&cx=SECRETCX456", kind="network")))
    out = src.search("q")
    assert out == []
    assert "SECRETKEY123" not in src.last_error
    assert "SECRETCX456" not in src.last_error

