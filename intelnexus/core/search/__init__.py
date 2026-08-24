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
from intelnexus.core.search_constants import USER_AGENTS, get_tor_proxy_port, get_freshness_score, SYNONYM_DICT  # noqa: E402,F401


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
        else:
            # 直连会话必须屏蔽环境代理：requests 的 trust_env 默认为 True，
            # 即使不显式设置 proxies 也会读取 HTTP_PROXY/HTTPS_PROXY 环境变量，
            # 导致「国内源强制直连」被环境里的幽灵代理（尤其已失效的）击穿。
            session.trust_env = False
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
    # 词典 / 翻译类（原 web.py 局部名单 BLOCKED_DOMAINS_WEB 并入单源；
    # 中文死规则（"知乎"等永不匹配 netloc）已剔除，deepmind.com 误屏蔽已移除）
    "dictionary.cambridge.org", "zdic.net", "dict.cn", "youdao.com",
    "wikiwand.com",
    "merriam-webster.com", "oxfordlearnersdictionaries.com",
    "collinsdictionary.com", "macmillandictionary.com",
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


def expand_query_tokens(tokens: set) -> set:
    """
    对查询token进行同义词扩展。

    Args:
        tokens: 原始token集合

    Returns:
        扩展后的token集合（包含原始token和同义词）
    """
    from intelnexus.core.search_constants import SYNONYM_DICT

    expanded = set(tokens)
    for token in tokens:
        if token in SYNONYM_DICT:
            synonyms = SYNONYM_DICT[token]
            for syn in synonyms[:2]:  # 最多取2个同义词
                expanded.add(syn.lower())
    return expanded


def _calculate_bm25_score(text: str, query_tokens: set, k1: float = 1.5, b: float = 0.75) -> float:
    """
    计算简化版BM25评分。

    Args:
        text: 文本内容
        query_tokens: 查询token集合
        k1: 词频饱和参数
        b: 文档长度归一化参数

    Returns:
        BM25评分（0.0 ~ 1.0）
    """
    if not text or not query_tokens:
        return 0.0

    text_lower = text.lower()
    text_tokens = re.split(r"[\s,，。、;；]+", text_lower)
    doc_len = len(text_tokens)
    avg_dl = 50  # 假设平均文档长度

    # 计算每个查询token的TF
    score = 0.0
    for token in query_tokens:
        tf = text_lower.count(token)
        if tf == 0:
            continue

        # 简化版IDF（假设文档集大小为10000）
        idf = max(0, 1.0)  # 简化处理

        # BM25评分公式
        numerator = tf * (k1 + 1)
        denominator = tf + k1 * (1 - b + b * doc_len / avg_dl)
        score += idf * numerator / denominator

    # 归一化到0-1范围
    return min(score / 5.0, 1.0)


def relevance_passes(result: dict, query) -> bool:
    """
    相关性评分：仅用于「按查询检索」的来源。
    - 域名黑名单命中直接丢弃；
    - 结合同义词扩展、BM25评分和时效性评分进行综合评估；
    - 阈值：综合评分 >= 0.3 视为相关。
    返回 False 表示应被过滤。
    """
    url = result.get("url") or result.get("link") or ""
    if is_blocked_domain(url):
        return False

    tokens = extract_query_tokens(query)
    if not tokens:
        return True  # 无可判定关键词时不误杀

    # 同义词扩展
    expanded_tokens = expand_query_tokens(tokens)

    # 构建文本
    title = result.get("title") or ""
    description = result.get("description") or ""
    text = f"{title} {description}"

    # 计算关键词匹配分数（支持同义词）
    matched = 0
    for t in expanded_tokens:
        if t in text.lower():
            matched += 1

    keyword_score = matched / len(expanded_tokens) if expanded_tokens else 0.0

    # 计算BM25评分
    bm25_score = _calculate_bm25_score(text, expanded_tokens)

    # 计算时效性评分
    published_at = result.get("published_at") or ""
    freshness_score = get_freshness_score(published_at)

    # 综合评分（权重：关键词0.5 + BM250.3 + 时效性0.2）
    total_score = keyword_score * 0.5 + bm25_score * 0.3 + freshness_score

    # 阈值判断
    threshold = 0.3
    return total_score >= threshold


# ========== 统一搜索源抽象（SearchSource） ==========
# 新增：基类 / 模式常量 / 注册表 / 适配器包
from intelnexus.core.search.source import (  # noqa: E402,F401
    BaseSearchSource,
    CATEGORY_WEB, CATEGORY_NEWS, CATEGORY_DARKWEB, CATEGORY_CUSTOM,
    CATEGORY_THREAT_INTEL, CATEGORY_COMMUNITY, CATEGORY_EXPLOIT,
)
from intelnexus.core.search.modes import (  # noqa: E402,F401
    SEARCH_MODES, MODE_DESCRIPTIONS, SEARCH_MODES_LABELS,
    get_mode_categories, get_mode_description,
)
from intelnexus.core.search.registry import SearchSourceRegistry  # noqa: E402,F401
from intelnexus.core.search import sources  # noqa: E402,F401

