import requests
import random
import re
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib.parse import quote, urlencode, urlparse, unquote

from intelnexus.core.logger import get_logger
from intelnexus.core.search import USER_AGENTS, get_http_proxies_for, is_blocked_domain, relevance_passes, get_session as _get_shared_session

logger = get_logger(__name__)

# 词典/翻译/百科类域名黑名单：已并入 core.search 顶层单源 BLOCKED_DOMAINS，
# 此处保留兼容别名（原局部名单中的中文死规则与 deepmind.com 已剔除）
from intelnexus.core.search import BLOCKED_DOMAINS as BLOCKED_DOMAINS_WEB  # noqa: F401

ENGINE_CONFIGS = {
    "Bing": {
        # cn.bing.com：国际版对无 cookie 爬虫请求会把纯 CJK 地名查询误判
        # 为日文（实测"九江"返回日文"零行列"内容）或随机填充页，中国版端点稳定。
        "url": "https://cn.bing.com/search?q={query}&first={offset}",
        "offset_fn": lambda page: page * 10 + 1,
        "item_selector": "li.b_algo",
        "title_selector": "h2 a",
        "fallback_title_selector": "a[href]:not(.tilk)",
        "desc_selector": "p",
        "requires_http": True,
        "filter_bing": True,
        # 国内可直连：强制直连，避免被幽灵代理拽入不可达链路（代理收口）
        "requires_proxy": False,
    },
    "DuckDuckGo": {
        "url": "https://html.duckduckgo.com/html/?q={query}&b={offset}",
        "offset_fn": lambda page: page * 11,
        "item_selector": "div.result",
        "title_selector": "a.result__a",
        "desc_selector": "a.result__snippet",
        "requires_proxy": True,
    },
    "Yahoo": {
        "url": "https://search.yahoo.com/search?p={query}&b={offset}",
        "offset_fn": lambda page: page * 10 + 1,
        "item_selector": "div.algo",
        "title_selector": None,
        "desc_selector": "p",
        "requires_proxy": True,
    },
    "Yandex": {
        "url": "https://yandex.com/search/?text={query}&page={offset}",
        "offset_fn": lambda page: page + 1,
        "item_selector": "li.serp-item",
        "title_selector": "a.serp-item__title",
        "desc_selector": "div.serp-item__text",
        "requires_proxy": True,
    },
    "Baidu": {
        "url": "https://www.baidu.com/s?wd={query}&pn={offset}",
        "offset_fn": lambda page: page * 10,
        "item_selector": "div.result",
        "title_selector": None,
        "desc_selector": None,
        "requires_proxy": False,
    },
}

SEARCH_ENGINES = [
    {"name": name, "url": cfg["url"], "parser": name.lower().replace("duckduckgo", "ddg")}
    for name, cfg in ENGINE_CONFIGS.items()
]


import threading

_session_lock = threading.Lock()
_shared_session = None

# 最近一次网页检索各引擎的失败摘要；get_web_results 入口清空，
# 供适配器在空结果时汇总写入 last_error。读写经 _LAST_WEB_ERRORS_LOCK 保护：
# clear 与「读取聚合」为原子段（append 在锁内执行）。
# 已知局限：并发多次调用 get_web_results 时（共享模块级列表），错误文案可能跨检索串味；
# 当前架构下同一时刻只有一次检索在跑，可接受。
LAST_WEB_ERRORS: list = []
_LAST_WEB_ERRORS_LOCK = threading.Lock()


def get_session(requires_proxy: bool = False):
    """复用 core.search 顶层的共享 session 工厂（代理收口）。

    requires_proxy=False（国内引擎 Bing/Baidu）强制直连，绝不经过任何代理；
    requires_proxy=True 时才返回实际代理配置（未配置则为直连会话）。
    """
    return _get_shared_session(get_http_proxies_for(requires_proxy))


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
        session = get_session(cfg.get("requires_proxy", False))
        response = session.get(url, headers=headers, timeout=(8, 15))

        if response.status_code != 200:
            # 非 200 也记失败：全部引擎被反爬拦截（403/429）时不应误判为成功无结果。
            # 慢速引擎在国内被墙属预期失败，同样如实记录，由上层口径决定是否采信。
            with _LAST_WEB_ERRORS_LOCK:
                LAST_WEB_ERRORS.append(f"{engine_name}: HTTP {response.status_code}")
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
        # 失败信号：供适配器在空结果时汇总写入 last_error（锁内 append，与 clear/读取互斥）
        with _LAST_WEB_ERRORS_LOCK:
            LAST_WEB_ERRORS.append(f"{engine_name}: {type(e).__name__}")
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


# ---------------------------------------------------------------------------
# 搜索结果重定向包装解析
# ---------------------------------------------------------------------------
# Yahoo 把真实地址编码在路径段 RU= 中，DuckDuckGo 编码在 uddg= 参数中，
# 均可离线解码；不解码会导致同一篇文章以不同包装 URL 重复入库、去重失效、
# 证据库出现 r.search.yahoo.com 之类的无效溯源地址。
_YAHOO_RU_RE = re.compile(r'/RU=([^/]+)')
_DDG_UDDG_RE = re.compile(r'[?&]uddg=([^&]+)')

# 真实地址无法离线解码的包装域（如 Baidu link?url= 为加密串，需运行时
# 跟随重定向，由 scraper 抓取时记录 resolved_url）
_WRAPPER_HOSTS = (
    'r.search.yahoo.com', 'search.yahoo.com',
    'html.duckduckgo.com', 'duckduckgo.com',
    'www.baidu.com', 'baidu.com',
    'news.google.com', 'www.bing.com', 'cn.bing.com', 'bing.com',
)


def canonical_result_url(url: str) -> str:
    """解析搜索结果中的重定向包装，返回真实目标 URL（无法解析时原样返回）。"""
    if not url or '://' not in url:
        return url
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return url

    real = url
    if 'yahoo' in host:
        m = _YAHOO_RU_RE.search(url)
        if m:
            real = unquote(m.group(1))
    elif 'duckduckgo' in host:
        m = _DDG_UDDG_RE.search(url)
        if m:
            real = unquote(m.group(1))
    return real if real.startswith('http') else url


def _dedup_results(results):
    seen = set()
    unique = []
    for res in results:
        # 先解码重定向包装再入库：后续去重、域名评分、证据附录都以真实
        # URL 为准；同一篇文章即使来自不同引擎/包装也只保留一条
        link = canonical_result_url(res.get("url", "")).rstrip('/')
        if link and link not in seen and len(link) > 10:
            res["url"] = link
            seen.add(link)
            unique.append(res)
    return unique


def get_web_results(query, max_workers: int = 5, max_results: int = 50) -> list:
    results = []
    pages_per_engine = 2
    # 清空上一轮的引擎失败摘要，保证本次检索的失败信号不被串味（锁内原子清空）
    with _LAST_WEB_ERRORS_LOCK:
        LAST_WEB_ERRORS.clear()

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
        if not get_http_proxies_for(True):
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

    # 失败口径：只要有引擎成功产出过原始结果（过滤前非空），就属于「正常检索」，
    # 即使结果全被相关性/黑名单过滤掉也不是失败；慢速引擎在国内失败属预期。
    # 仅当「所有引擎零产出」时才保留错误信号供适配器聚合。
    if unique_results:
        with _LAST_WEB_ERRORS_LOCK:
            LAST_WEB_ERRORS.clear()

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
