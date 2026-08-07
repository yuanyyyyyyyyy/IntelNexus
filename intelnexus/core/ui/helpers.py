import socket
import streamlit as st

SEARCH_MODES = {
    "all": ["mode_all", "全部来源"],
    "web": ["mode_web", "网页搜索"],
    "news": ["mode_news", "新闻资讯"],
    "darkweb": ["mode_darkweb", "暗网搜索"],
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
