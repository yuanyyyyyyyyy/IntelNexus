"""计量代理测试（离线，主要用假 handler，不依赖真实 socket）。

覆盖两个曾导致线上崩溃的缺陷：
1. 代理把请求转发给了自己（``base_url`` 整体替换后丢掉上游路径前缀）；
2. 上游异常时 ``finally`` 引用未赋值的 ``payload`` → UnboundLocalError。
"""
from __future__ import annotations

import io

import pytest

from experiments.privacy.capture import (
    ProxyStats,
    _ProxyHandler,
    _aggregate,
    build_target_url,
    judge_run,
    parse_upstream_path,
)


# --------------------------------------------------------------------- 纯函数
def test_parse_upstream_path_keeps_path_and_query():
    assert parse_upstream_path("http://127.0.0.1:8080/v1/chat/completions?x=1") == \
        "/v1/chat/completions?x=1"
    assert parse_upstream_path("/v1/models") == "/v1/models"
    assert parse_upstream_path("") == "/"


def test_build_target_url_restores_provider_prefix():
    """核心缺陷：客户端 base_url 换成代理后，/compatible-mode/v1 前缀必须由代理补回。"""
    url, host = build_target_url("https://dashscope.aliyuncs.com/compatible-mode/v1",
                                 "/chat/completions")
    assert url == "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    assert host == "dashscope.aliyuncs.com"


def test_build_target_url_handles_absolute_uri_from_proxy_client():
    url, host = build_target_url("http://127.0.0.1:11434",
                                 "http://127.0.0.1:11434/api/chat")
    assert url == "http://127.0.0.1:11434/api/chat"
    assert host == "127.0.0.1"


def test_build_target_url_without_upstream_falls_back_to_host_header():
    """未配置上游时退化为标准正向代理（按 Host 头转发）。"""
    url, host = build_target_url("", "/v1/models", "api.example.com:443")
    assert url == "http://api.example.com:443/v1/models"
    assert host == "api.example.com"


def test_build_target_url_never_points_at_proxy_itself():
    """配置了上游时，结果里不得出现代理自身地址。"""
    url, _ = build_target_url("https://api.deepseek.com/v1", "/chat/completions")
    assert url.startswith("https://api.deepseek.com/v1/")


# --------------------------------------------------------------------- 转发
class _FakeWFile:
    def __init__(self) -> None:
        self.data = b""

    def write(self, b) -> None:  # noqa: ANN001
        self.data += b


def _make_handler(path: str, upstream_base: str, body: bytes = b"") -> _ProxyHandler:
    """构造一个不绑定 socket 的 handler，用于直接调用 _forward_plain。"""
    h = object.__new__(_ProxyHandler)
    h.stats = ProxyStats()
    h.upstream_base = upstream_base
    h.path = path
    h.command = "POST" if body else "GET"
    h.headers = {"Host": "127.0.0.1:9", "Content-Length": str(len(body))}
    h.rfile = io.BytesIO(body)
    h.wfile = _FakeWFile()
    h._status = None
    h.send_response = lambda code, msg=None: setattr(h, "_status", code)
    h.send_header = lambda k, v=None: None
    h.end_headers = lambda: None
    h.send_error = lambda code, msg=None: setattr(h, "_status", code)
    return h


def test_forward_plain_does_not_crash_when_upstream_is_down():
    """上游不可达：不得抛 UnboundLocalError，必须 502 并完成计数。"""
    h = _make_handler("/v1/chat/completions", "http://127.0.0.1:9", body=b"x" * 100)
    h._forward_plain()          # 不抛异常即为通过
    assert h._status == 502
    snap = h.stats.snapshot()
    assert snap["requests"] == 1
    assert snap["bytes_out"] >= 100          # 出域字节照常计入
    assert snap["destinations"] == ["127.0.0.1"]


def test_forward_plain_counts_request_bytes():
    """出域量按请求体 + 请求行计算（无论上游是否可达都要计数）。"""
    h = _make_handler("/v1/chat/completions", "http://127.0.0.1:9", body=b"y" * 2048)
    h._forward_plain()
    assert h.stats.snapshot()["bytes_out"] > 2048


# ------------------------------------------------------- 运行有效性判定（表6 口径）
def _run(**kwargs):
    base = {"bytes_out": 100, "bytes_in": 200, "requests": 10,
            "destinations": ["dashscope.aliyuncs.com"], "error": None, "backend": "openai_compatible"}
    base.update(kwargs)
    return base


def test_judge_run_accepts_normal_cloud_run():
    ok, reason = judge_run(_run(bytes_total=85048), "openai_compatible")
    assert ok and reason is None


def test_judge_run_rejects_proxy_loopback_cloud_run():
    """代理转发回自身：目的地全为回环，必须判为无效（否则表6 出域量失真）。"""
    ok, reason = judge_run(_run(destinations=["127.0.0.1"], requests=132805,
                                bytes_out=1128086677), "openai_compatible")
    assert not ok
    assert "loopback" in (reason or "")


def test_judge_run_accepts_loopback_for_local_backend():
    """本地组本来就只走回环，不算无效。"""
    ok, _ = judge_run(_run(destinations=["127.0.0.1"], backend="ollama"), "ollama")
    assert ok


@pytest.mark.parametrize("bad", [
    {"error": "RuntimeError: boom"},
    {"requests": 0},
    {"destinations": []},
])
def test_judge_run_rejects_broken_runs(bad):
    ok, reason = judge_run(_run(**bad), "openai_compatible")
    assert not ok and reason


def test_aggregate_excludes_invalid_runs_from_totals():
    """无效运行保留原件，但不进入合计；本地组出域以 bytes_total 为准。"""
    entry = {"runs": [
        _run(destinations=["127.0.0.1"], requests=132805, bytes_out=1128086677),
        _run(bytes_total=85048),
    ]}
    _aggregate("cloud_flagship", entry)
    assert entry["bytes_total"] == 85048
    assert entry["destinations"] == ["dashscope.aliyuncs.com"]
    assert entry["valid_runs"] == 1 and len(entry["invalid_runs"]) == 1
    assert entry["runs"][0]["valid"] is False and entry["runs"][1]["valid"] is True


def test_aggregate_local_egress_is_zero_but_loopback_kept():
    entry = {"runs": [_run(destinations=["127.0.0.1"], backend="ollama",
                           bytes_out=123456, bytes_total=0)]}
    _aggregate("qwen3:8b", entry)
    assert entry["bytes_total"] == 0
    assert entry["runs"][0]["bytes_out"] == 123456      # 回环量可复核
