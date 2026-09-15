"""站内定向检索后端单测（博查 Bocha / Brave / Google CSE）。

覆盖：工厂解析与缓存、Provider 参数构造、响应解析为统一字段、
额度/限速错误映射、TTL 缓存与最小请求间隔节流、未配置显式报错。
全部 mock 网络（get_session），不产生真实请求。
"""
from unittest.mock import MagicMock, patch

import pytest

from intelnexus.core.search.sitesearch import (
    available_providers, get_site_search_backend, reset_site_search_backend,
    resolve_provider,
)
from intelnexus.core.search.sitesearch.base import SiteSearchError, redact_secrets
from intelnexus.core.search.sitesearch.bocha import BochaBackend
from intelnexus.core.search.sitesearch.brave import BraveBackend
from intelnexus.core.search.sitesearch.google_cse import GoogleCSEBackend


def _cfg(**over):
    base = {
        "site_search_provider": "auto",
        "bocha_api_key": "",
        "google_cse_api_key": "",
        "google_cse_id": "",
        "brave_api_key": "",
    }
    base.update(over)
    return base


def _resp(status=200, json_data=None, text=""):
    r = MagicMock()
    r.status_code = status
    r.text = text
    r.json.return_value = json_data if json_data is not None else {}
    r.raise_for_status = MagicMock()
    return r


class _FakeClock:
    """可控时钟：便于断言限速与 TTL，不依赖真实时间。"""

    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t

    def advance(self, delta):
        self.t += delta


# ---------------------------------------------------------------------------
# 工厂：Provider 解析 / 自动择一 / 实例缓存与失效
# ---------------------------------------------------------------------------

def test_auto_prefers_bocha_when_all_configured():
    """auto 优先级：博查 > Brave > Google（博查国内直连，为当前推荐路径）。"""
    assert resolve_provider(_cfg(bocha_api_key="b", brave_api_key="br",
                                 google_cse_api_key="k", google_cse_id="c")) == "bocha"


def test_auto_prefers_brave_over_google_cse():
    assert resolve_provider(_cfg(brave_api_key="br", google_cse_api_key="k",
                                 google_cse_id="c")) == "brave"


def test_auto_falls_back_to_google_cse_last():
    """Google CSE 已对新客户关闭，仅保留给存量 Key，故排末位。"""
    assert resolve_provider(_cfg(google_cse_api_key="k",
                                 google_cse_id="c")) == "google_cse"


def test_auto_falls_back_to_brave():
    assert resolve_provider(_cfg(brave_api_key="b")) == "brave"


def test_auto_returns_empty_when_nothing_configured():
    assert resolve_provider(_cfg()) == ""


def test_explicit_provider_unconfigured_resolves_empty():
    """显式指定但凭证不全 → 视为不可用（不静默回退到另一家）。"""
    assert resolve_provider(_cfg(site_search_provider="brave",
                                 google_cse_api_key="k", google_cse_id="c")) == ""


def test_google_cse_needs_both_key_and_cx():
    assert resolve_provider(_cfg(site_search_provider="google_cse",
                                 google_cse_api_key="k")) == ""
    assert resolve_provider(_cfg(site_search_provider="google_cse",
                                 google_cse_api_key="k", google_cse_id="c")) == "google_cse"


def test_available_providers_lists_configured_only():
    assert available_providers(_cfg()) == []
    assert available_providers(_cfg(brave_api_key="b")) == ["brave"]
    assert available_providers(_cfg(bocha_api_key="b")) == ["bocha"]
    # 多配置时按优先级顺序返回
    assert available_providers(_cfg(google_cse_api_key="k", google_cse_id="c",
                                    brave_api_key="b",
                                    bocha_api_key="bb")) == [
        "bocha", "brave", "google_cse"]


def test_get_backend_returns_none_when_unconfigured():
    assert get_site_search_backend(_cfg()) is None


def test_get_backend_caches_instance_until_reset():
    reset_site_search_backend()
    first = get_site_search_backend(_cfg(brave_api_key="b"))
    second = get_site_search_backend(_cfg(brave_api_key="b"))
    assert first is not None and first is second
    reset_site_search_backend()
    third = get_site_search_backend(_cfg(brave_api_key="b"))
    assert third is not first


def test_bocha_key_rotation_invalidates_backend_cache():
    """凭证轮换必须让缓存失效（缓存键须含 bocha_api_key，否则会继续用旧 Key）。"""
    reset_site_search_backend()
    first = get_site_search_backend(_cfg(bocha_api_key="key-1"))
    assert first is not None
    second = get_site_search_backend(_cfg(bocha_api_key="key-2"))
    assert second is not first
    reset_site_search_backend()


# ---------------------------------------------------------------------------
# Google CSE
# ---------------------------------------------------------------------------

def test_google_is_configured_requires_key_and_cx():
    assert GoogleCSEBackend(api_key="k", cse_id="c").is_configured() is True
    assert GoogleCSEBackend(api_key="k", cse_id="").is_configured() is False
    assert GoogleCSEBackend(api_key="", cse_id="c").is_configured() is False


def test_google_request_is_site_scoped_and_num_capped():
    """Google 用 siteSearch + siteSearchFilter=i 做站内限定；num 上限 10。"""
    payload = {"items": [
        {"title": "T1", "link": "https://www.xiaohongshu.com/explore/1",
         "snippet": "S1"},
    ]}
    session = MagicMock()
    session.get.return_value = _resp(200, payload)
    with patch("intelnexus.core.search.sitesearch.google_cse.get_session",
               return_value=session):
        out = GoogleCSEBackend(api_key="k", cse_id="cx").search(
            "数据泄露", "xiaohongshu.com", max_results=25)

    args, kwargs = session.get.call_args
    assert args[0] == "https://www.googleapis.com/customsearch/v1"
    params = kwargs["params"]
    assert params["key"] == "k" and params["cx"] == "cx"
    assert params["q"] == "数据泄露"
    assert params["siteSearch"] == "xiaohongshu.com"
    assert params["siteSearchFilter"] == "i"
    assert params["num"] == 10  # 上限收敛
    assert len(out) == 1
    for field in ("title", "url", "description", "source", "category",
                  "published_at", "metadata"):
        assert field in out[0]
    assert out[0]["url"] == "https://www.xiaohongshu.com/explore/1"
    assert out[0]["source"] == "GoogleCSE"


def test_google_empty_items_returns_empty():
    session = MagicMock()
    session.get.return_value = _resp(200, {})
    with patch("intelnexus.core.search.sitesearch.google_cse.get_session",
               return_value=session):
        assert GoogleCSEBackend(api_key="k", cse_id="c").search("q", "d.com") == []


def test_google_daily_limit_maps_to_quota_error():
    session = MagicMock()
    session.get.return_value = _resp(403, {"error": {"errors": [
        {"reason": "dailyLimitExceeded"}]}})
    with patch("intelnexus.core.search.sitesearch.google_cse.get_session",
               return_value=session):
        with pytest.raises(SiteSearchError) as ei:
            GoogleCSEBackend(api_key="k", cse_id="c").search("q", "d.com")
    assert ei.value.kind == "quota"


def test_google_invalid_key_maps_to_auth_error():
    session = MagicMock()
    session.get.return_value = _resp(400, {"error": {"errors": [
        {"reason": "keyInvalid"}]}})
    with patch("intelnexus.core.search.sitesearch.google_cse.get_session",
               return_value=session):
        with pytest.raises(SiteSearchError) as ei:
            GoogleCSEBackend(api_key="k", cse_id="c").search("q", "d.com")
    assert ei.value.kind == "auth"


# ---------------------------------------------------------------------------
# Brave
# ---------------------------------------------------------------------------

def test_brave_is_configured_requires_api_key():
    assert BraveBackend(api_key="b").is_configured() is True
    assert BraveBackend(api_key="").is_configured() is False


def test_brave_request_uses_site_operator_count_and_token_header():
    payload = {"web": {"results": [
        {"title": "T1", "url": "https://www.xiaohongshu.com/explore/2",
         "description": "D1"},
    ]}}
    session = MagicMock()
    session.get.return_value = _resp(200, payload)
    with patch("intelnexus.core.search.sitesearch.brave.get_session",
               return_value=session):
        out = BraveBackend(api_key="tok").search("漏洞复现", "xiaohongshu.com",
                                                max_results=50)

    args, kwargs = session.get.call_args
    assert args[0] == "https://api.search.brave.com/res/v1/web/search"
    assert kwargs["headers"]["X-Subscription-Token"] == "tok"
    assert kwargs["params"]["q"] == "漏洞复现 site:xiaohongshu.com"
    assert kwargs["params"]["count"] == 20  # 上限收敛
    assert len(out) == 1
    assert out[0]["url"] == "https://www.xiaohongshu.com/explore/2"
    assert out[0]["source"] == "Brave"


def test_brave_rate_limit_maps_to_quota_error():
    session = MagicMock()
    session.get.return_value = _resp(429, {})
    with patch("intelnexus.core.search.sitesearch.brave.get_session",
               return_value=session):
        with pytest.raises(SiteSearchError) as ei:
            BraveBackend(api_key="tok").search("q", "d.com")
    assert ei.value.kind == "quota"


def test_brave_unauthorized_maps_to_auth_error():
    session = MagicMock()
    session.get.return_value = _resp(401, {})
    with patch("intelnexus.core.search.sitesearch.brave.get_session",
               return_value=session):
        with pytest.raises(SiteSearchError) as ei:
            BraveBackend(api_key="bad").search("q", "d.com")
    assert ei.value.kind == "auth"


# ---------------------------------------------------------------------------
# 基类公共行为：未配置 / 空查询 / 缓存 / 节流
# ---------------------------------------------------------------------------

def test_unconfigured_backend_raises_not_configured():
    with pytest.raises(SiteSearchError) as ei:
        BraveBackend(api_key="").search("q", "d.com")
    assert ei.value.kind == "not_configured"


def test_blank_query_or_domain_returns_empty_without_request():
    session = MagicMock()
    with patch("intelnexus.core.search.sitesearch.brave.get_session",
               return_value=session):
        be = BraveBackend(api_key="tok")
        assert be.search("   ", "d.com") == []
        assert be.search("q", "  ") == []
    session.get.assert_not_called()


def test_repeated_search_hits_cache():
    payload = {"web": {"results": [
        {"title": "T", "url": "https://www.xiaohongshu.com/explore/3",
         "description": "D"}]}}
    session = MagicMock()
    session.get.return_value = _resp(200, payload)
    with patch("intelnexus.core.search.sitesearch.brave.get_session",
               return_value=session):
        be = BraveBackend(api_key="tok")
        first = be.search("q", "d.com")
        second = be.search("q", "d.com")
    assert session.get.call_count == 1
    assert first == second


def test_cache_expires_after_ttl():
    payload = {"web": {"results": []}}
    clock = _FakeClock()
    session = MagicMock()
    session.get.return_value = _resp(200, payload)
    with patch("intelnexus.core.search.sitesearch.brave.get_session",
               return_value=session):
        be = BraveBackend(api_key="tok", ttl=300, clock=clock, sleeper=lambda s: None)
        be.search("q", "d.com")
        clock.advance(299)
        be.search("q", "d.com")
        assert session.get.call_count == 1
        clock.advance(2)  # 累计 301s > TTL
        be.search("q", "d.com")
    assert session.get.call_count == 2


def test_throttle_waits_remaining_min_interval():
    payload = {"web": {"results": []}}
    clock = _FakeClock()
    slept = []

    def _sleeper(sec):
        slept.append(sec)
        clock.advance(sec)

    session = MagicMock()
    session.get.return_value = _resp(200, payload)
    with patch("intelnexus.core.search.sitesearch.brave.get_session",
               return_value=session):
        be = BraveBackend(api_key="tok", min_interval=1.0,
                          clock=clock, sleeper=_sleeper)
        be.search("q1", "d.com")      # 首次：无等待
        clock.advance(0.2)
        be.search("q2", "d.com")      # 距上次仅 0.2s → 等待约 0.8s
    assert len(slept) == 1
    assert slept[0] == pytest.approx(0.8, abs=0.05)


# ---------------------------------------------------------------------------
# 凭证脱敏（严重项回归）：requests 异常消息含带 query 的完整 URL
# ---------------------------------------------------------------------------

def test_redact_secrets_masks_query_credentials():
    raw = ("HTTPConnectionPool(host='www.googleapis.com', port=443): Max retries "
           "exceeded with url: /customsearch/v1?key=AIzaSECRET123&cx=CXSECRET456&num=10")
    out = redact_secrets(raw)
    assert "AIzaSECRET123" not in out
    assert "CXSECRET456" not in out
    assert "key=***" in out and "cx=***" in out


def test_google_network_error_does_not_leak_api_key():
    import requests as _rq

    session = MagicMock()
    session.get.side_effect = _rq.exceptions.ConnectionError(
        "Max retries exceeded with url: "
        "/customsearch/v1?key=SECRETKEY123&cx=SECRETCX456&num=10")
    with patch("intelnexus.core.search.sitesearch.google_cse.get_session",
               return_value=session):
        with pytest.raises(SiteSearchError) as ei:
            GoogleCSEBackend(api_key="SECRETKEY123", cse_id="SECRETCX456") \
                .search("q", "d.com")
    assert ei.value.kind == "network"
    msg = str(ei.value)
    assert "SECRETKEY123" not in msg
    assert "SECRETCX456" not in msg


# ---------------------------------------------------------------------------
# 错误分类准确性
# ---------------------------------------------------------------------------

def test_google_bad_request_is_not_classified_as_auth():
    """badRequest 是通用参数错误，不应误导用户去换 Key。"""
    session = MagicMock()
    session.get.return_value = _resp(400, {"error": {"errors": [
        {"reason": "badRequest"}]}})
    with patch("intelnexus.core.search.sitesearch.google_cse.get_session",
               return_value=session):
        with pytest.raises(SiteSearchError) as ei:
            GoogleCSEBackend(api_key="k", cse_id="c").search("q", "d.com")
    assert ei.value.kind == "error"


def test_google_access_not_configured_has_specific_kind():
    """未在云项目启用 API，与「凭证无效」不是一回事。"""
    session = MagicMock()
    session.get.return_value = _resp(403, {"error": {"errors": [
        {"reason": "accessNotConfigured"}]}})
    with patch("intelnexus.core.search.sitesearch.google_cse.get_session",
               return_value=session):
        with pytest.raises(SiteSearchError) as ei:
            GoogleCSEBackend(api_key="k", cse_id="c").search("q", "d.com")
    assert ei.value.kind == "config"


# ---------------------------------------------------------------------------
# 缓存键按「有效请求规模」归一（避免无谓消耗 Google CSE 日额度）
# ---------------------------------------------------------------------------

def test_cache_key_normalized_by_effective_cap():
    """limit=10 与 limit=25 对 Google 是同一个请求（num 上限 10）→ 只请求一次。"""
    session = MagicMock()
    session.get.return_value = _resp(200, {"items": []})
    with patch("intelnexus.core.search.sitesearch.google_cse.get_session",
               return_value=session):
        be = GoogleCSEBackend(api_key="k", cse_id="c")
        be.search("q", "d.com", max_results=10)
        be.search("q", "d.com", max_results=25)
    assert session.get.call_count == 1


# ---------------------------------------------------------------------------
# Brave 时效字段：相对文本不可作 published_at（无法被时效评分解析）
# ---------------------------------------------------------------------------

def test_brave_age_goes_to_metadata_not_published_at():
    payload = {"web": {"results": [
        {"title": "T", "url": "https://www.xiaohongshu.com/explore/9",
         "description": "D", "age": "2 days ago"}]}}
    session = MagicMock()
    session.get.return_value = _resp(200, payload)
    with patch("intelnexus.core.search.sitesearch.brave.get_session",
               return_value=session):
        out = BraveBackend(api_key="tok").search("q", "xiaohongshu.com")
    assert out[0]["published_at"] == ""
    assert out[0]["metadata"]["age"] == "2 days ago"


# ---------------------------------------------------------------------------
# 博查（Bocha）：POST + Bearer + include 站点限定；国内直连
# ---------------------------------------------------------------------------

def _bocha_payload(**over):
    item = {
        "name": "数据泄露应急响应笔记",
        "url": "https://www.xiaohongshu.com/explore/abc",
        "snippet": "短摘要",
        "summary": "长摘要",
        "siteName": "小红书",
        "datePublished": "2024-07-22T00:00:00+08:00",
    }
    item.update(over)
    return {"_type": "SearchResponse",
            "webPages": {"totalEstimatedMatches": 100, "value": [item]}}


def test_bocha_is_configured_requires_api_key():
    assert BochaBackend(api_key="sk-x").is_configured() is True
    assert BochaBackend(api_key="").is_configured() is False


def test_bocha_posts_json_with_bearer_and_site_include():
    """站内限定用 include 参数（字段名源自第三方文档，未获官方证实）。"""
    session = MagicMock()
    session.post.return_value = _resp(200, _bocha_payload())
    with patch("intelnexus.core.search.sitesearch.bocha.get_session",
               return_value=session):
        out = BochaBackend(api_key="sk-token").search(
            "数据泄露", "xiaohongshu.com", max_results=10)

    args, kwargs = session.post.call_args
    assert args[0] == "https://api.bocha.cn/v1/web-search"
    assert kwargs["headers"]["Authorization"] == "Bearer sk-token"
    assert kwargs["headers"]["Content-Type"] == "application/json"
    body = kwargs["json"]
    assert body["query"] == "数据泄露"
    assert body["include"] == "xiaohongshu.com"
    assert body["count"] == 10
    assert body["summary"] is True
    assert len(out) == 1


def test_bocha_parses_web_pages_and_prefers_summary():
    session = MagicMock()
    session.post.return_value = _resp(200, _bocha_payload())
    with patch("intelnexus.core.search.sitesearch.bocha.get_session",
               return_value=session):
        out = BochaBackend(api_key="sk").search("q", "xiaohongshu.com")

    r = out[0]
    assert r["title"] == "数据泄露应急响应笔记"
    assert r["url"] == "https://www.xiaohongshu.com/explore/abc"
    assert r["description"] == "长摘要"  # summary 优先于 snippet
    assert r["source"] == "Bocha"
    assert r["published_at"] == "2024-07-22T00:00:00+08:00"
    assert r["metadata"]["site_name"] == "小红书"
    for field in ("title", "url", "description", "source", "category",
                  "published_at", "metadata"):
        assert field in r


def test_bocha_falls_back_to_snippet_without_summary():
    session = MagicMock()
    session.post.return_value = _resp(200, _bocha_payload(summary=""))
    with patch("intelnexus.core.search.sitesearch.bocha.get_session",
               return_value=session):
        out = BochaBackend(api_key="sk").search("q", "d.com")
    assert out[0]["description"] == "短摘要"


def test_bocha_count_is_capped():
    session = MagicMock()
    session.post.return_value = _resp(200, {"webPages": {"value": []}})
    with patch("intelnexus.core.search.sitesearch.bocha.get_session",
               return_value=session):
        BochaBackend(api_key="sk").search("q", "d.com", max_results=999)
    assert session.post.call_args.kwargs["json"]["count"] == BochaBackend.MAX_RESULTS


def test_bocha_forces_direct_connection():
    """博查是国内服务：必须强制直连（get_session(None)），不吃代理配置。"""
    session = MagicMock()
    session.post.return_value = _resp(200, {"webPages": {"value": []}})
    with patch("intelnexus.core.search.sitesearch.bocha.get_session",
               return_value=session) as mock_get_session, \
         patch("intelnexus.core.search.get_http_proxies",
               side_effect=AssertionError("国内源不应读取代理配置")):
        BochaBackend(api_key="sk").search("q", "d.com")
    assert mock_get_session.call_args.args[0] is None


def test_bocha_empty_value_returns_empty():
    session = MagicMock()
    session.post.return_value = _resp(200, {"webPages": {"value": []}})
    with patch("intelnexus.core.search.sitesearch.bocha.get_session",
               return_value=session):
        assert BochaBackend(api_key="sk").search("q", "d.com") == []


@pytest.mark.parametrize("status,expected_kind", [
    (400, "error"),   # 参数错误
    (401, "auth"),    # Invalid API KEY
    (403, "quota"),   # You do not have enough money（余额不足）
    (429, "quota"),   # You have reached the request limit
    (500, "error"),
])
def test_bocha_error_mapping(status, expected_kind):
    session = MagicMock()
    session.post.return_value = _resp(status, {"code": str(status),
                                               "message": "boom"})
    with patch("intelnexus.core.search.sitesearch.bocha.get_session",
               return_value=session):
        with pytest.raises(SiteSearchError) as ei:
            BochaBackend(api_key="sk").search("q", "d.com")
    assert ei.value.kind == expected_kind


def test_bocha_network_error_maps_to_network_without_leaking_key():
    import requests as _rq
    session = MagicMock()
    session.post.side_effect = _rq.exceptions.ConnectionError("conn refused")
    with patch("intelnexus.core.search.sitesearch.bocha.get_session",
               return_value=session):
        with pytest.raises(SiteSearchError) as ei:
            BochaBackend(api_key="sk-SECRET").search("q", "d.com")
    assert ei.value.kind == "network"
    assert "sk-SECRET" not in str(ei.value)


# ---------------------------------------------------------------------------
# 博查响应结构（2026-09-15 真实抓包修正）：结果嵌在 data 层内
# ---------------------------------------------------------------------------

def test_bocha_parses_results_nested_under_data():
    """回归（致命）：真实响应为 ``{code, log_id, msg, data:{webPages:{value:[...]}}}``。

    旧代码直接取**顶层** ``webPages``，而顶层根本没有该字段 → 永远解析出 0 条。
    这是小红书源配置正确、Key 有效、后端连通却始终取不到数据的根因。
    """
    body = {"code": 200, "log_id": "abc", "msg": None,
            "data": _bocha_payload()}
    session = MagicMock()
    session.post.return_value = _resp(200, body)
    with patch("intelnexus.core.search.sitesearch.bocha.get_session",
               return_value=session):
        out = BochaBackend(api_key="sk").search("数据泄露", "xiaohongshu.com")

    assert len(out) == 1
    assert out[0]["url"] == "https://www.xiaohongshu.com/explore/abc"
    assert out[0]["title"] == "数据泄露应急响应笔记"


def test_bocha_still_parses_flat_shape_as_fallback():
    """兼容：无 data 包裹时仍按顶层解析（历史夹具与该形状一致）。"""
    session = MagicMock()
    session.post.return_value = _resp(200, _bocha_payload())
    with patch("intelnexus.core.search.sitesearch.bocha.get_session",
               return_value=session):
        out = BochaBackend(api_key="sk").search("q", "xiaohongshu.com")

    assert len(out) == 1


def test_bocha_business_error_code_raises_instead_of_empty():
    """HTTP 200 但 body.code != 200（业务失败）必须报错，不能静默返回空列表。

    静默返回空会让上层误判为「站点索引无命中」，把真正的业务故障藏起来。
    """
    session = MagicMock()
    session.post.return_value = _resp(200, {"code": 400, "log_id": "x",
                                            "msg": "bad request", "data": None})
    with patch("intelnexus.core.search.sitesearch.bocha.get_session",
               return_value=session):
        with pytest.raises(SiteSearchError) as ei:
            BochaBackend(api_key="sk").search("q", "d.com")

    assert "bad request" in str(ei.value)


