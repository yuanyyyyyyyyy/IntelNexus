"""
统一外部 URL 校验器（SSRF 防御）
================================
供所有"用户输入 URL 入库/外发"的入口复用：自定义数据源、暗网站点、
自定义模型 base_url、自定义供应商 URL 等。

规则（默认严格模式）：
- 仅允许 ``http`` / ``https`` 协议（大小写不敏感）；
- 主机名必须非空；
- 字面 IP 用 ``ipaddress`` 判定，域名用 ``socket.getaddrinfo`` 解析，
  拒绝回环（127.0.0.0/8、::1）、私网（10/8、172.16/12、192.168/16、
  ULA、fe80::/10 等）、链路本地/云元数据（169.254.0.0/16）、
  组播/保留/未指定地址；
- DNS 解析失败视为非法；
- ``.onion`` 主机为 Tor 隐藏服务，本地 DNS 无法解析（须经 Tor 代理解析），
  仅校验协议与主机名非空，不做本地 DNS 解析；
- fail-close：校验器自身任何异常一律按"拒绝"处理。

``allow_local=True`` 模式（用于自定义模型/供应商 base_url）：
本地部署的 LLM 服务（如 Ollama 默认 http://127.0.0.1:11434、局域网内
自建推理服务）是产品的内置支持场景，若按严格模式封禁回环/私网会破坏
既有功能，故该模式仍强制 http/https 与主机名非空，但跳过地址段封禁。

纯函数、无 Streamlit 依赖、可单测。
"""

import ipaddress
import socket
from urllib.parse import urlparse

__all__ = [
    "validate_external_url",
    "REASON_OK", "REASON_EMPTY", "REASON_INVALID", "REASON_BAD_SCHEME",
    "REASON_NO_HOST", "REASON_DNS_FAILED", "REASON_BLOCKED",
]

_ALLOWED_SCHEMES = ("http", "https")

# 拒绝原因码：UI 层按 f"sec_url_{code}" 映射 i18n 文案
REASON_OK = "ok"
REASON_EMPTY = "empty"                # 空/非字符串输入
REASON_INVALID = "invalid"            # 畸形输入或校验器自身异常（fail-close）
REASON_BAD_SCHEME = "bad_scheme"      # 协议不是 http/https
REASON_NO_HOST = "no_host"            # 主机名为空
REASON_DNS_FAILED = "dns_failed"      # 域名解析失败
REASON_BLOCKED = "blocked_internal"   # 指向回环/私网/链路本地/元数据等地址


def _is_blocked_ip(ip) -> bool:
    """判断 IP 是否落在应封禁的地址段。

    覆盖：回环（127/8、::1）、私网（RFC1918、ULA、CGNAT）、
    链路本地（169.254/16 含云元数据、fe80::/10）、
    组播、保留段、未指定地址（0.0.0.0、::）。
    """
    return (
        ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def validate_external_url(url, allow_local: bool = False, allow_onion: bool = True):
    """校验外部 URL 是否允许入库/外发。

    Args:
        url: 待校验 URL（任意输入均安全处理，不抛异常）。
        allow_local: True 时允许回环/私网等本地地址（仅限用户自有
            服务端点场景，如 Ollama/局域网 LLM 的 base_url）；
            协议与主机名校验仍然生效。
        allow_onion: True 时放行 ``.onion`` 主机（Tor 隐藏服务，
            本地无法 DNS 解析，由 Tor 代理层负责寻址）。

    Returns:
        (bool, str): (是否合法, 拒绝原因码)。合法时原因码为 ``REASON_OK``。
    """
    try:
        if not isinstance(url, str) or not url.strip():
            return False, REASON_EMPTY

        parsed = urlparse(url.strip())
        scheme = (parsed.scheme or "").lower()
        if scheme not in _ALLOWED_SCHEMES:
            return False, REASON_BAD_SCHEME

        host = parsed.hostname  # 已小写化并剥离 IPv6 方括号
        if not host:
            return False, REASON_NO_HOST

        # Tor 隐藏服务：本地 DNS 必然失败，仅做协议/主机名约束
        if allow_onion and host.endswith(".onion"):
            return True, REASON_OK

        # 字面 IP 直接判定（避免无谓的 DNS 往返）
        try:
            ip = ipaddress.ip_address(host)
            if allow_local or not _is_blocked_ip(ip):
                return True, REASON_OK
            return False, REASON_BLOCKED
        except ValueError:
            pass  # 非字面 IP，走域名解析

        # 域名：DNS 解析并检查全部结果（防 DNS 重绑定到内网地址）
        try:
            infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
        except (socket.gaierror, UnicodeError, OSError):
            return False, REASON_DNS_FAILED
        if not infos:
            return False, REASON_DNS_FAILED

        if allow_local:
            return True, REASON_OK

        for info in infos:
            addr = info[4][0].split("%")[0]  # 剥离 IPv6 zone id
            try:
                ip = ipaddress.ip_address(addr)
            except ValueError:
                return False, REASON_BLOCKED  # 无法解析的地址按封禁处理
            if _is_blocked_ip(ip):
                return False, REASON_BLOCKED
        return True, REASON_OK
    except Exception:
        # fail-close：校验器自身异常一律拒绝
        return False, REASON_INVALID
