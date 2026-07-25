import random
import os
import re
import requests
from typing import Optional
from urllib.parse import urlparse
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) Gecko/20100101 Firefox/137.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.7; rv:137.0) Gecko/20100101 Firefox/137.0",
    "Mozilla/5.0 (X11; Linux i686; rv:137.0) Gecko/20100101 Firefox/137.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.3 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.3179.54",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.3179.54",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]


def get_tor_proxy_port():
    """获取Tor代理端口（与 darkweb.py 保持一致）"""
    custom_port = os.getenv("TOR_PROXY_PORT")
    if custom_port:
        try:
            return int(custom_port)
        except Exception:
            pass
    return 9150


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
