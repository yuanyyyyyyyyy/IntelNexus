"""源连通性主动探测（``core.search.probe``）的回归测试。

钉住四类判定 + 落盘语义 + 跳过语义，全部使用假源，**不发起任何真实网络请求**：

1. 判定口径与 ``registry._timed_search`` 对齐：有结果=ok、空+last_error=fail、
   空+无错误=empty、异常=fail；
2. 超时：慢源按 timeout 记录，且不拖住同批其他源；
3. 跳过：需代理未配置 / 暗网功能未启用 → skip_*，且**不落盘**（跳过不是观测）；
4. 落盘：ok/empty 记成功，fail/timeout 记失败并带错误；落盘自身异常不影响探测；
5. 范围：enabled=False 的源不参与探测。
"""

import time

import pytest

from intelnexus.core.search.probe import (
    PROBE_MAX_RESULTS,
    PROBE_QUERY,
    ProbeOutcome,
    probe_registry,
)


class _FakeSource:
    """最小搜索源桩：按 behavior 走不同分支。"""

    category = "web"
    enabled = True
    requires_proxy = False

    def __init__(self, name: str, behavior: str = "ok"):
        self.name = name
        self.behavior = behavior
        self.last_error = None
        self.calls = []

    def search(self, query, max_results: int = 20):
        self.calls.append((query, max_results))
        if self.behavior == "ok":
            return [{"title": "t", "url": "https://example.com"}]
        if self.behavior == "empty":
            return []
        if self.behavior == "empty_error":
            self.last_error = "认证失败：Key 无效"
            return []
        if self.behavior == "raise":
            raise RuntimeError("boom")
        if self.behavior == "slow":
            time.sleep(1.0)
            return []
        return []


class _FakeRegistry:
    def __init__(self, sources):
        self._sources = list(sources)

    def all_sources(self):
        return list(self._sources)


@pytest.fixture()
def recorded(monkeypatch):
    """拦截 health.record_probe_result，记录落盘调用。"""
    calls = []

    def fake_record(name, success, latency_ms, error=None):
        calls.append({"name": name, "success": success,
                      "latency_ms": latency_ms, "error": error})

    monkeypatch.setattr("intelnexus.core.search.health.record_probe_result", fake_record)
    return calls


def _by_name(outcomes):
    return {o.source_name: o for o in outcomes}


# ---------------------------------------------------------------------------
# 判定口径
# ---------------------------------------------------------------------------

def test_states_follow_timed_search_semantics(recorded):
    ok = _FakeSource("OkSrc", "ok")
    empty = _FakeSource("EmptySrc", "empty")
    empty_err = _FakeSource("EmptyErrSrc", "empty_error")
    boom = _FakeSource("BoomSrc", "raise")

    outcomes = _by_name(probe_registry(
        _FakeRegistry([ok, empty, empty_err, boom]), persist=True))

    assert outcomes["OkSrc"].state == "ok"
    assert outcomes["OkSrc"].result_count == 1
    assert outcomes["EmptySrc"].state == "empty"
    assert outcomes["EmptyErrSrc"].state == "fail"
    assert "认证失败" in outcomes["EmptyErrSrc"].error
    assert outcomes["BoomSrc"].state == "fail"
    assert "RuntimeError" in outcomes["BoomSrc"].error

    # 落盘语义：ok/empty 成功，fail 失败且携带错误
    got = {c["name"]: c for c in recorded}
    assert got["OkSrc"]["success"] is True
    assert got["EmptySrc"]["success"] is True
    assert got["EmptyErrSrc"]["success"] is False
    assert "认证失败" in got["EmptyErrSrc"]["error"]
    assert got["BoomSrc"]["success"] is False


def test_probe_uses_query_and_result_cap(recorded):
    src = _FakeSource("QuerySrc", "ok")
    probe_registry(_FakeRegistry([src]), persist=False)
    assert src.calls == [(PROBE_QUERY, PROBE_MAX_RESULTS)]


# ---------------------------------------------------------------------------
# 超时
# ---------------------------------------------------------------------------

def test_timeout_recorded_without_blocking_others(recorded):
    slow = _FakeSource("SlowSrc", "slow")
    fast = _FakeSource("FastSrc", "ok")
    t0 = time.monotonic()
    outcomes = _by_name(probe_registry(
        _FakeRegistry([slow, fast]), timeout_overrides={"SlowSrc": 0.15},
        persist=True))
    elapsed = time.monotonic() - t0

    assert outcomes["SlowSrc"].state == "timeout"
    assert outcomes["SlowSrc"].success is False
    assert "超时" in outcomes["SlowSrc"].error
    assert outcomes["FastSrc"].state == "ok"
    # 慢源不该把同批探测拖满（sleep 1.0s >> 0.15s 预算）
    assert elapsed < 0.9
    got = {c["name"]: c for c in recorded}
    assert got["SlowSrc"]["success"] is False
    assert got["FastSrc"]["success"] is True


# ---------------------------------------------------------------------------
# 跳过：不探测、不落盘
# ---------------------------------------------------------------------------

def test_skip_when_proxy_required_but_missing(monkeypatch, recorded):
    src = _FakeSource("ProxySrc", "ok")
    src.requires_proxy = True
    monkeypatch.setattr("intelnexus.core.search.get_http_proxies", lambda: None)

    outcomes = _by_name(probe_registry(_FakeRegistry([src]), persist=True))

    assert outcomes["ProxySrc"].state == "skip_no_proxy"
    assert src.calls == []  # 没有发起检索
    assert recorded == []   # 跳过不是观测，不得改动健康统计


def test_skip_when_darkweb_disabled(monkeypatch, recorded):
    src = _FakeSource("DarkWeb", "ok")
    src.category = "darkweb"
    monkeypatch.setattr("intelnexus.search_app.darkweb.is_available", lambda: False)

    outcomes = _by_name(probe_registry(_FakeRegistry([src]), persist=True))

    assert outcomes["DarkWeb"].state == "skip_disabled"
    assert src.calls == []
    assert recorded == []


def test_disabled_sources_not_probed(recorded):
    off = _FakeSource("DisabledSrc", "ok")
    off.enabled = False
    on = _FakeSource("EnabledSrc", "ok")

    outcomes = _by_name(probe_registry(_FakeRegistry([off, on]), persist=False))

    assert "DisabledSrc" not in outcomes
    assert off.calls == []
    assert outcomes["EnabledSrc"].state == "ok"


# ---------------------------------------------------------------------------
# 回调与容错
# ---------------------------------------------------------------------------

def test_on_result_callback_and_persist_off(recorded):
    seen = []
    probe_registry(_FakeRegistry([_FakeSource("A", "ok"), _FakeSource("B", "empty")]),
                   on_result=seen.append, persist=False)
    assert {o.source_name for o in seen} == {"A", "B"}
    assert recorded == []


def test_persist_failure_does_not_break_probe(monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("disk full")

    monkeypatch.setattr("intelnexus.core.search.health.record_probe_result", broken)
    outcomes = probe_registry(_FakeRegistry([_FakeSource("A", "ok")]), persist=True)
    assert outcomes and outcomes[0].state == "ok"


def test_outcome_success_property():
    assert ProbeOutcome("A", "ok").success is True
    assert ProbeOutcome("A", "empty").success is True
    assert ProbeOutcome("A", "fail").success is False
    assert ProbeOutcome("A", "timeout").success is False
