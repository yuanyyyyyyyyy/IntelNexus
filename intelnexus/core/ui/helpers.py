import socket
import streamlit as st

# 从唯一事实源派生（旧版此处硬编码四键拷贝，导致 threat 模式在 UI 不可达）。
# 结构兼容既有调用方：{mode: [i18n_key, 中文名]}
from intelnexus.core.search.modes import SEARCH_MODES as _CORE_SEARCH_MODES

SEARCH_MODES = {
    mode: list(values[:2]) for mode, values in _CORE_SEARCH_MODES.items()
}

DEFAULT_TOR_PORT = 9150


def check_tor_status(port=DEFAULT_TOR_PORT):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        return result == 0
    except Exception:
        return False


def get_tor_port():
    return st.session_state.get("tor_port", DEFAULT_TOR_PORT)
