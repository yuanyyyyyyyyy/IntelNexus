import requests
import random
import re
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib.parse import quote, urlencode

from intelnexus.core.logger import get_logger
from intelnexus.core.search import USER_AGENTS, get_http_proxies, is_blocked_domain, relevance_passes, get_session as _get_shared_session

logger = get_logger(__name__)

# 词典/翻译/百科类域名黑名单：已并入 core.search 顶层单源 BLOCKED_DOMAINS，
# 此处保留兼容别名（原局部名单中的中文死规则与 deepmind.com 已剔除）
from intelnexus.core.search import BLOCKED_DOMAINS as BLOCKED_DOMAINS_WEB  # noqa: F401

ENGINE_CONFIGS = {
    "Bing": {
        "url": "https://www.bing.com/search?q={query}&first={offset}",
        "offset_fn": lambda page: page * 10 + 1,
        "item_selector": "li.b_algo",
        "title_selector": "h2 a",
        "fallback_title_selector": "a[href]:not(.tilk)",
        "desc_selector": "p",
        "requires_http": True,
        "filter_bing": True,
    },
    "DuckDuckGo": {
        "url": "https://html.duckduckgo.com/html/?q={query}&b={offset}",
        "offset_fn": lambda page: page * 11,
        "item_selector": "div.result",
        "title_selector": "a.result__a",
        "desc_selector": "a.result__snippet",
    },
    "Yahoo": {
        "url": "https://search.yahoo.com/search?p={query}&b={offset}",
        "offset_fn": lambda page: page * 10 + 1,
        "item_selector": "div.algo",
        "title_selector": None,
        "desc_selector": "p",
    },
    "Yandex": {
        "url": "https://yandex.com/search/?text={query}&page={offset}",
        "offset_fn": lambda page: page + 1,
        "item_selector": "li.serp-item",
        "title_selector": "a.serp-item__title",
        "desc_selector": "div.serp-item__text",
    },
    "Baidu": {
        "url": "https://www.baidu.com/s?wd={query}&pn={offset}",
        "offset_fn": lambda page: page * 10,
        "item_selector": "div.result",
        "title_selector": None,
        "desc_selector": None,
    },
}

SEARCH_ENGINES = [
    {"name": name, "url": cfg["url"], "parser": name.lower().replace("duckduckgo", "ddg")}
    for name, cfg in ENGINE_CONFIGS.items()
]


import threading

_session_lock = threading.Lock()
_shared_session = None


def get_session():
    """复用 core.search 顶层的共享 session 工厂（全局代理配置）。"""
    return _get_shared_session(get_http_proxies())


def _fetch_engine(engine_name: str, query: str, page: int = 0):
    """Generic fetch function for any search engine."""
    cfg = ENGINE_CONFIGS.get(engine_name)
    if cfg is None:
        return []

    results = []
    try:
        encoded_query = quote(query, safe='')
        offset = cfg["offset_fn"](page)
        url = cfg["url"].format(query=encoded_query, offset=offset)
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        session = get_session()
        response = session.get(url, headers=headers, timeout=(8, 15))

        if response.status_code != 200:
            return results

        soup = BeautifulSoup(response.text, "html.parser")

        for item in soup.select(cfg["item_selector"]):
            try:
                a_tag = None
                if cfg.get("title_selector"):
                    a_tag = item.select_one(cfg["title_selector"])
                if not a_tag and cfg.get("fallback_title_selector"):
                    a_tag = item.select_one(cfg["fallback_title_selector"])
                if not a_tag:
                    a_tag = item.find("a")
                if not a_tag:
                    continue

                title = a_tag.get_text(strip=True)
                href = a_tag.get("href", "")

                description = ""
                if cfg.get("desc_selector"):
                    snippet = item.select_one(cfg["desc_selector"])
                    if snippet:
                        description = snippet.get_text(strip=True)

                if not href or not href.startswith("http"):
                    continue
                if cfg.get("filter_bing") and "bing.com" in href:
                    continue

                # 过滤词典/翻译/百科类域名
                from urllib.parse import urlparse
                try:
                    domain = urlparse(href).netloc.lower()
                    if any(blocked in domain for blocked in BLOCKED_DOMAINS_WEB):
                        continue
                except Exception:
                    pass

                results.append({
                    "title": title,
                    "url": href,
                    "description": description[:200],
                    "source": engine_name,
                })
            except Exception:
                continue
    except Exception as e:
        # Yahoo/DuckDuckGo/Yandex 在中国经常被墙，降级为 DEBUG 避免日志噪音
        if engine_name in ("Yahoo", "DuckDuckGo", "Yandex"):
            logger.debug(f"{engine_name} search error (expected in CN): {type(e).__name__}")
        else:
            logger.warning(f"{engine_name} search error: {e}")
    return results


def fetch_bing_results(query: str, page: int = 0):
    return _fetch_engine("Bing", query, page)


def fetch_ddg_results(query: str, page: int = 0):
    return _fetch_engine("DuckDuckGo", query, page)


def fetch_yahoo_results(query: str, page: int = 0):
    return _fetch_engine("Yahoo", query, page)


def fetch_yandex_results(query: str, page: int = 0):
    return _fetch_engine("Yandex", query, page)


def fetch_baidu_results(query: str, page: int = 0):
    return _fetch_engine("Baidu", query, page)


FAST_ENGINES = ["Bing", "Baidu"]
SLOW_ENGINES = ["DuckDuckGo", "Yahoo", "Yandex"]

ENGINE_FUNCS = {
    "Bing": fetch_bing_results,
    "DuckDuckGo": fetch_ddg_results,
    "Yahoo": fetch_yahoo_results,
    "Yandex": fetch_yandex_results,
    "Baidu": fetch_baidu_results,
}


def _dedup_results(results):
    seen = set()
    unique = []
    for res in results:
        link = res.get("url", "").rstrip('/')
        if link and link not in seen and len(link) > 10:
            seen.add(link)
            unique.append(res)
    return unique


def get_web_results(query, max_workers: int = 5, max_results: int = 50) -> list:
    results = []
    pages_per_engine = 2

    if isinstance(query, list):
        queries = query
    elif '|' in query:
        queries = [q.strip() for q in query.split('|')]
    else:
        queries = [query]

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for q in queries:
            for page in range(pages_per_engine):
                for name in FAST_ENGINES:
                    futures.append(executor.submit(ENGINE_FUNCS[name], q, page))
        for future in as_completed(futures):
            try:
                results.extend(future.result())
            except Exception as e:
                logger.warning(f"Search error: {e}")

    unique_so_far = _dedup_results(results)
    if len(unique_so_far) < 20:
        if not get_http_proxies():
            logger.info("快速引擎结果不足，但无代理配置，跳过慢速引擎（DuckDuckGo/Yahoo/Yandex）避免无效超时")
        else:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = []
                for q in queries:
                    for page in range(pages_per_engine):
                        for name in SLOW_ENGINES:
                            futures.append(executor.submit(ENGINE_FUNCS[name], q, page))
                for future in as_completed(futures):
                    try:
                        results.extend(future.result())
                    except Exception as e:
                        logger.warning(f"Search error: {e}")
    else:
        logger.info(f"快速引擎已返回 {len(unique_so_far)} 条结果，跳过慢速引擎")

    unique_results = _dedup_results(results)

    filtered = []
    for r in unique_results[:max_results]:
        if is_blocked_domain(r.get("url", "")):
            continue
        if not relevance_passes(r, query):
            continue
        filtered.append(r)

    kept = filtered
    logger.info(f"网页检索原始 {len(unique_results[:max_results])} 条，过滤后保留 {len(kept)} 条")
    return kept
