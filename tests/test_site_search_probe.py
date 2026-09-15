"""站内检索后端自检（probe_site_search）。

覆盖：
- 未配置 → ``unconfigured``；各错误码映射到 auth / quota / config / network / error；
- 成功→ ``ok``，并回带 provider 与耗时；失败也要回带耗时（供健康探测记录）；
- 文案统一脱敏（Key 走 query 的 Google CSE 尤其危险）；
- 博查自检用**最小载荷**（count=1、summary=False），且**绕过缓存**——
  否则「Key 已吊销/余额已耗尽」会被上一次的缓存命中误报为成功。
"""
from unittest.mock import patch, MagicMock

import pytest

from intelnexus.core.search import sitesearch as ss
from intelnexus.core.search.sitesearch.base import SiteSearchError
from intelnexus.core.search.sitesearch.bocha import BochaBackend
from intelnexus.core.search.sitesearch import probe_site_search


class _StubBackend:
    """可编程后端桩：记录 probe 调用，按需返回或抛错。"""

    name = "Stub"

    def __init__(self, rows=None, error=None):
        self.rows = list(rows or [])
        self.error = error
        self.probe_calls = []

    def is_configured(self):
        return True

    def probe(self, domain=""):
        self.probe_calls.append(domain)
        if self.error is not None:
            raise self.error
        return list(self.rows)


@pytest.fixture
def stub_builder(monkeypatch):
    """把工厂的 Provider 构造替换为桩，避免任何真实网络。"""
    def _install(backend, provider="bocha"):
        monkeypatch.setattr(ss, "_BUILDERS", {provider: lambda cfg: backend})
        monkeypatch.setattr(ss, "PROVIDER_PRIORITY", (provider,))
        return backend
    return _install


def _cfg(provider="bocha", key="sk-test"):
    return {"site_search_provider": provider, "bocha_api_key": key,
            "google_cse_api_key": "", "google_cse_id": "", "brave_api_key": ""}


# ---------------------------------------------------------------------------
# 结论分类
# ---------------------------------------------------------------------------

def test_unconfigured_when_no_credentials():
    """无任何 Key → 走真实构造器判定未配置（不发请求）。

    注意：这里**不能**用 stub_builder——桩的 is_configured() 恒为 True，
    会把「凭证为空」这一分支掩盖掉。
    """
    out = probe_site_search({"site_search_provider": "auto", "bocha_api_key": "",
                             "google_cse_api_key": "", "google_cse_id": "",
                             "brave_api_key": ""})
    assert out["ok"] is False
    assert out["kind"] == "unconfigured"
    assert out["configured"] is False
    assert out["provider"] == ""


def test_success_reports_ok_with_provider_and_latency(stub_builder):
    backend = stub_builder(_StubBackend(rows=[{"url": "https://x.test/a"}]))
    out = probe_site_search(_cfg())

    assert out["ok"] is True
    assert out["kind"] == "ok"
    assert out["configured"] is True
    assert out["provider"] == "bocha"
    assert out["latency_ms"] >= 0


@pytest.mark.parametrize("kind,expect", [
    ("auth", "auth"),        # 401 凭证无效
    ("quota", "quota"),      # 403 余额不足/权限受限、429 限流
    ("config", "config"),    # 未启用该 API
    ("network", "network"),  # 不可达
    ("error", "error"),
])
def test_error_kinds_are_passed_through(stub_builder, kind, expect):
    stub_builder(_StubBackend(error=SiteSearchError(f"失败了 kind={kind}",
                                                    kind=kind)))
    out = probe_site_search(_cfg())

    assert out["ok"] is False
    assert out["kind"] == expect
    assert out["latency_ms"] >= 0  # 失败也要有耗时，供 record_probe_result 使用


def test_unexpected_exception_maps_to_error(stub_builder):
    stub_builder(_StubBackend(error=RuntimeError("boom")))
    out = probe_site_search(_cfg())

    assert out["ok"] is False
    assert out["kind"] == "error"


def test_message_is_redacted(stub_builder):
    """Key 走 query 的 Provider，其异常消息含完整 URL —— 必须脱敏后返回。"""
    stub_builder(_StubBackend(
        error=SiteSearchError(".../customsearch/v1?key=AIzaSECRET&cx=CX",
                              kind="auth")))
    out = probe_site_search(_cfg())

    assert "AIzaSECRET" not in out["message"]
    assert "key=***" in out["message"]


# ---------------------------------------------------------------------------
# 博查：最小载荷 + 绕过缓存
# ---------------------------------------------------------------------------

def _bocha_with_mock_session():
    """返回 (backend, mock_session)：POST 返回空结果集。"""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"webPages": {"value": []}}
    mock_resp.raise_for_status = MagicMock()
    session = MagicMock()
    session.post.return_value = mock_resp
    backend = BochaBackend(api_key="sk-test", min_interval=0)
    return backend, session


def _probe_payload(backend, session):
    with patch("intelnexus.core.search.sitesearch.bocha.get_session",
               return_value=session):
        backend.probe()
    return session.post.call_args.kwargs["json"]


def test_bocha_probe_uses_minimal_payload():
    """自检必须最小成本：count=1 且关掉 summary（summary 显著抬高耗时与成本）。"""
    backend, session = _bocha_with_mock_session()

    payload = _probe_payload(backend, session)

    assert payload["count"] == 1
    assert payload["summary"] is False


def test_bocha_search_still_requests_summary():
    """对照：正常检索仍带 summary（信息量大于 snippet），自检不得改变它。"""
    backend, session = _bocha_with_mock_session()

    with patch("intelnexus.core.search.sitesearch.bocha.get_session",
               return_value=session):
        backend.search("数据泄露", "xiaohongshu.com", 10)
    payload = session.post.call_args.kwargs["json"]

    assert payload["summary"] is True
    assert payload["count"] == 10


def test_probe_bypasses_cache():
    """自检必须每次真发请求：命中缓存会把「Key 已失效」误报为成功。"""
    backend, session = _bocha_with_mock_session()

    with patch("intelnexus.core.search.sitesearch.bocha.get_session",
               return_value=session):
        backend.probe()
        backend.probe()

    assert session.post.call_count == 2


def test_search_uses_cache_as_before():
    """对照：正常检索仍走缓存（保护充值制额度），自检不得破坏该行为。"""
    backend, session = _bocha_with_mock_session()

    with patch("intelnexus.core.search.sitesearch.bocha.get_session",
               return_value=session):
        backend.search("q", "xiaohongshu.com", 10)
        backend.search("q", "xiaohongshu.com", 10)

    assert session.post.call_count == 1
