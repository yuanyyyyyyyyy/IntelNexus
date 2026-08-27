"""intelnexus.core.security.url_guard 单测。

域名形式用例通过 monkeypatch 打桩 socket.getaddrinfo，
保证离线环境（无 DNS）下测试依然确定性通过。
"""

import socket

import pytest

from intelnexus.core.security import url_guard
from intelnexus.core.security.url_guard import (
    validate_external_url,
    REASON_OK, REASON_EMPTY, REASON_INVALID, REASON_BAD_SCHEME, REASON_NO_HOST,
    REASON_DNS_FAILED, REASON_BLOCKED,
)


def _fake_addr(ip: str):
    """构造 getaddrinfo 风格的返回结构（仅校验器用到的字段）。"""
    family = socket.AF_INET6 if ":" in ip else socket.AF_INET
    return [(family, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (ip, 0))]


@pytest.fixture
def mock_dns_public(monkeypatch):
    """域名解析 → 公网 IP。"""
    monkeypatch.setattr(
        url_guard.socket, "getaddrinfo",
        lambda host, port, proto=None: _fake_addr("93.184.216.34"))


@pytest.fixture
def mock_dns_fail(monkeypatch):
    """域名解析失败。"""
    def _raise(host, port, proto=None):
        raise socket.gaierror("Name or service not known")
    monkeypatch.setattr(url_guard.socket, "getaddrinfo", _raise)


# ---------- 合法输入 ----------

def test_http_literal_public_ip_passes():
    ok, reason = validate_external_url("http://93.184.216.34/feed.xml")
    assert ok and reason == REASON_OK


def test_https_literal_public_ip_with_port_passes():
    ok, reason = validate_external_url("https://8.8.8.8:8443/api")
    assert ok and reason == REASON_OK


def test_https_domain_passes(mock_dns_public):
    ok, reason = validate_external_url("https://example.com/news")
    assert ok and reason == REASON_OK


def test_scheme_case_insensitive(mock_dns_public):
    ok, reason = validate_external_url("HTTPS://example.com/x")
    assert ok and reason == REASON_OK


def test_onion_host_passes_without_dns():
    # .onion 为 Tor 隐藏服务，本地无法 DNS 解析，仅校验协议与主机名
    ok, reason = validate_external_url(
        "http://abcdefghijklmnop23456789012345678901234567890123456789012345.onion/search?q=")
    assert ok and reason == REASON_OK


# ---------- 非法协议 ----------

@pytest.mark.parametrize("url", [
    "ftp://example.com/file",
    "file:///etc/passwd",
    "javascript:alert(1)",
    "gopher://example.com/",
    "example.com/no-scheme",
])
def test_bad_scheme_rejected(url):
    ok, reason = validate_external_url(url)
    assert not ok and reason == REASON_BAD_SCHEME


# ---------- 内网/回环/链路本地/元数据地址 ----------

@pytest.mark.parametrize("url", [
    "http://127.0.0.1:11434/api",      # 回环
    "http://169.254.169.254/latest",   # 云元数据
    "http://192.168.1.1/",             # RFC1918
    "http://10.0.0.1/",                # RFC1918
    "http://172.16.0.1/",              # RFC1918
    "http://[::1]/",                   # IPv6 回环
    "http://0.0.0.0/",                 # 未指定
])
def test_blocked_internal_addresses(url):
    ok, reason = validate_external_url(url)
    assert not ok and reason == REASON_BLOCKED


def test_domain_resolving_to_internal_ip_rejected(monkeypatch):
    # DNS 重绑定防御：域名解析到内网地址同样拒绝
    monkeypatch.setattr(
        url_guard.socket, "getaddrinfo",
        lambda host, port, proto=None: _fake_addr("192.168.0.10"))
    ok, reason = validate_external_url("http://evil.example.com/")
    assert not ok and reason == REASON_BLOCKED


# ---------- 空/畸形输入 ----------

@pytest.mark.parametrize("url", ["", "   ", None, 123, ["http://x.com"]])
def test_empty_or_malformed_rejected(url):
    ok, reason = validate_external_url(url)
    assert not ok and reason in (REASON_EMPTY, REASON_INVALID)


def test_missing_host_rejected():
    ok, reason = validate_external_url("http://")
    assert not ok and reason == REASON_NO_HOST


def test_dns_failure_rejected(mock_dns_fail):
    ok, reason = validate_external_url("http://nonexistent-domain-xyz.invalid/")
    assert not ok and reason == REASON_DNS_FAILED


# ---------- allow_local（本地模型端点场景，如 Ollama）----------

def test_allow_local_permits_loopback():
    ok, reason = validate_external_url("http://127.0.0.1:11434", allow_local=True)
    assert ok and reason == REASON_OK


def test_allow_local_still_enforces_scheme():
    ok, reason = validate_external_url("ftp://127.0.0.1/", allow_local=True)
    assert not ok and reason == REASON_BAD_SCHEME


def test_allow_local_still_requires_host():
    ok, reason = validate_external_url("http://", allow_local=True)
    assert not ok and reason == REASON_NO_HOST
