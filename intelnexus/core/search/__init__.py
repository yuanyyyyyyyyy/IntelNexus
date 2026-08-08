import random
import os
import re
import threading
import requests
from typing import Optional
from urllib.parse import urlparse
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Re-export shared constants/helpers from a standalone module to avoid a
# circular import when darkweb (pulled in by the search source registry)
# imports USER_AGENTS / get_tor_proxy_port.
from intelnexus.core.search_constants import USER_AGENTS, get_tor_proxy_port  # noqa: E402,F401


def get_tor_session():
    """
    Creates a requests Session with Tor SOCKS proxy and automatic retries.
    """
    session = requests.Session()
    retry = Retry(
        total=3,
        read=3,
        connect=3,
        backoff_factor=0.3,
        status_forcelist=[500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    port = get_tor_proxy_port()
    session.proxies = {
        "http": f"socks5h://127.0.0.1:{port}",
        "https": f"socks5h://127.0.0.1:{port}"
    }
    return session


# ========== 共享 Tor Session 单例（避免每次抓取都重建 SOCKS 连接） ==========
_shared_tor_session = None
_tor_session_lock = threading.Lock()


def get_shared_tor_session():
    """获取进程内复用的 Tor Session 单例（双检锁）。"""
    global _shared_tor_session
    if _shared_tor_session is None:
        with _tor_session_lock:
            if _shared_tor_session is None:
                _shared_tor_session = get_tor_session()
    return _shared_tor_session


# ========== 共享 HTTP Session 工厂（连接池 + 重试，按代理配置缓存） ==========
_session_cache = {}
_session_cache_lock = threading.Lock()


def get_session(proxies: Optional[dict] = None):
    """
    获取带连接池与自动重试的 requests.Session（按 proxies 配置缓存复用）。

    - proxies=None：直连（国内源、本地抓取）
    - proxies=dict：走指定代理（与 get_http_proxies() 返回一致）

    复用 Session 可避免每次请求重复 TCP/TLS 握手，显著降低抓取延迟。
    """
    key = None
    if proxies:
        key = tuple(sorted((k, v) for k, v in proxies.items()))
    with _session_cache_lock:
        cached = _session_cache.get(key)
        if cached is not None:
            return cached
        session = requests.Session()
        retry = Retry(
            total=3,
            read=3,
            connect=3,
            backoff_factor=0.3,
            status_forcelist=[500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=20)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        if proxies:
            session.proxies = proxies
        _session_cache[key] = session
        return session


def get_http_proxies():
    """
    返回 {'http':..., 'https':...} 或 None。
    优先读取 HTTP_PROXY/HTTPS_PROXY 环境变量（大小写不敏感），
    其次若 USE_TOR=true 则走本地 Tor SOCKS5 代理。
    返回 None 时调用方不传 proxies，行为与未配置代理时完全一致（零开销）。
    """
    http = os.getenv("HTTP_PROXY") or os.getenv("http_proxy")
    https = os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")
    if http or https:
        return {"http": http or https, "https": https or http}
    if os.getenv("USE_TOR", "").lower() == "true":
        port = get_tor_proxy_port()
        p = f"socks5h://127.0.0.1:{port}"
        return {"http": p, "https": p}
    return None


def get_http_proxies_for(requires_proxy: bool) -> Optional[dict]:
    """
    代理收口（核心修复点）。
    - 国内源 (requires_proxy=False)：强制直连，永远返回 None，绝不经过任何代理，
      即使存在「幽灵代理」环境变量也不会被拽进不可达代理而超时。
    - 代理源 (requires_proxy=True)：返回实际代理配置；未配置代理时返回 None
      （调用方应配合跳过逻辑，不发起请求）。
    """
    if not requires_proxy:
        return None
    return get_http_proxies()


# ========== 噪声过滤：域名黑名单 + 相关性评分 ==========
BLOCKED_DOMAINS = [
    # 百科 / 词典 / 问答类（非一手情报）
    "baike.baidu.com", "baike.bdimg.com", "baike.so.com", "baike.douban.com",
    "hanyu.baidu.com", "iciba.com", "dict.youdao.com", "dict.baidu.com",
    "wikipedia.org", "zh.wikipedia.org",
    # 电竞 / 游戏（与 AI/网安简报无关，曾污染 TOP3）
    "5eplay.com", "csgo", "dota2", "lol.qq.com", "gamersky.com", "3dmgame.com",
]

_STOPWORDS = {
    "a", "an", "the", "of", "to", "in", "on", "for", "and", "or", "is", "are",
    "was", "were", "with", "how", "what", "why", "news", "update", "latest",
    "incident", "disclosure", "report", "reports",
}


def _result_host(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def is_blocked_domain(url: str) -> bool:
    """命中黑名单域名（子串匹配，含 csgo 等关键词）即视为噪声。"""
    host = _result_host(url)
    if not host:
        return False
    return any(b in host for b in BLOCKED_DOMAINS)


def extract_query_tokens(query) -> set:
    """从查询中提取有意义的关键词 token（排除停用词与纯数字年份）。"""
    if isinstance(query, list):
        parts = query
    elif isinstance(query, str) and "|" in query:
        parts = [q.strip() for q in query.split("|")]
    else:
        parts = [query]

    tokens = set()
    for p in parts:
        if not p:
            continue
        for raw in re.split(r"[\s,，。、;；]+", p):
            tok = raw.strip().lower()
            if not tok or tok in _STOPWORDS or tok.isdigit() or len(tok) < 2:
                continue
            tokens.add(tok)
    return tokens


def relevance_passes(result: dict, query) -> bool:
    """
    相关性评分：仅用于「按查询检索」的来源。
    - 域名黑名单命中直接丢弃；
    - 否则要求标题+描述至少命中查询中 2 个（token 不足 2 个时要求全部）关键词，
      以剔除仅蹭单个关键词的噪声（如 K-pop「PENTAGON」组合）。
    返回 False 表示应被过滤。
    """
    link = result.get("link") or result.get("url") or ""
    if is_blocked_domain(link):
        return False

    tokens = extract_query_tokens(query)
    if not tokens:
        return True  # 无可判定关键词时不误杀

    text = ((result.get("title") or "") + " " + (result.get("description") or "")).lower()
    matched = sum(1 for t in tokens if t in text)

    threshold = 2 if len(tokens) >= 2 else len(tokens)
    return matched >= threshold


# ========== 统一搜索源抽象（SearchSource） ==========
# 新增：基类 / 模式常量 / 注册表 / 适配器包
from intelnexus.core.search.source import (  # noqa: E402,F401
    BaseSearchSource,
    CATEGORY_WEB, CATEGORY_NEWS, CATEGORY_DARKWEB, CATEGORY_CUSTOM,
)
from intelnexus.core.search.modes import (  # noqa: E402,F401
    SEARCH_MODES, MODE_DESCRIPTIONS, SEARCH_MODES_LABELS,
    get_mode_categories, get_mode_description,
)
from intelnexus.core.search.registry import SearchSourceRegistry  # noqa: E402,F401
from intelnexus.core.search import sources  # noqa: E402,F401

