import socket
from concurrent.futures import ThreadPoolExecutor
import streamlit as st

# 从唯一事实源派生（旧版此处硬编码四键拷贝，导致 threat 模式在 UI 不可达）。
# 结构兼容既有调用方：{mode: [i18n_key, 中文名]}
from intelnexus.core.search.modes import SEARCH_MODES as _CORE_SEARCH_MODES

SEARCH_MODES = {
    mode: list(values[:2]) for mode, values in _CORE_SEARCH_MODES.items()
}

DEFAULT_TOR_PORT = 9150

# 常见 Tor SOCKS 端口，自动探测用：并发探测，任一通即视为 Tor 运行中
TOR_PORT_CANDIDATES = (2080, 9150, 9050)
# 单端口探测超时：localhost 关闭端口本应即时 refused，但部分环境（防火墙/安全软件
# 对 loopback 静默丢弃 SYN）会等到超时；取较小值，并配合并发避免多端口超时累加。
_TOR_PROBE_TIMEOUT = 1.0


def check_tor_status(port=DEFAULT_TOR_PORT):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(_TOR_PROBE_TIMEOUT)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        return result == 0
    except Exception:
        return False


def find_tor_port(preferred=None, candidates=TOR_PORT_CANDIDATES):
    """探测 Tor 是否在本地 SOCKS 端口上监听。

    优先探测 preferred（用户在设置面板选择的端口，可能为 None），
    否则并发探测候选端口，返回首个开放端口；都不通返回 None。
    并发探测使总耗时约为单端口超时，而非各端口超时之和——
    在 loopback 被静默丢弃的环境下，原「依次探测」会累加为 6s，现约 1s。
    """
    ports = list(candidates)
    if preferred is not None and preferred not in ports:
        ports.insert(0, preferred)
    if not ports:
        return None
    with ThreadPoolExecutor(max_workers=len(ports)) as ex:
        futs = {ex.submit(check_tor_status, p): p for p in ports}
        for f in futs:
            try:
                if f.result(timeout=_TOR_PROBE_TIMEOUT + 0.3):
                    return futs[f]
            except Exception:
                pass
    return None


def is_tor_running(preferred=None):
    """Tor 是否在任一常见 SOCKS 端口上监听（自动探测）。"""
    return find_tor_port(preferred=preferred) is not None


def get_tor_port():
    return st.session_state.get("tor_port", DEFAULT_TOR_PORT)
