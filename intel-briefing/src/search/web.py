import requests
import random
import re
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib.parse import quote, urlencode

from src.logger import get_logger
from src.search import USER_AGENTS

logger = get_logger(__name__)

SEARCH_ENGINES = [
    {
        "name": "Bing",
        "url": "https://www.bing.com/search?q={query}&first={page}",
        "parser": "bing"
    },
    {
        "name": "DuckDuckGo",
        "url": "https://html.duckduckgo.com/html/?q={query}&b={page}",
        "parser": "ddg"
    },
    {
        "name": "Yahoo",
        "url": "https://search.yahoo.com/search?p={query}&b={page}",
        "parser": "yahoo"
    },
    {
        "name": "Yandex",
        "url": "https://yandex.com/search/?text={query}&page={page}",
        "parser": "yandex"
    },
    {
        "name": "Baidu",
        "url": "https://www.baidu.com/s?wd={query}&pn={page}",
        "parser": "baidu"
    },
]


import threading

_session_lock = threading.Lock()
_shared_session = None


def get_session():
    global _shared_session
    if _shared_session is None:
        with _session_lock:
            if _shared_session is None:
                session = requests.Session()
                retry = Retry(
                    total=2,
                    read=2,
                    connect=2,
                    backoff_factor=0.5,
                    status_forcelist=[500, 502, 503, 504]
                )
                adapter = HTTPAdapter(max_retries=retry)
                session.mount("http://", adapter)
                session.mount("https://", adapter)
                _shared_session = session
    return _shared_session


def fetch_bing_results(query: str, page: int = 0):
    results = []
    try:
        encoded_query = quote(query, safe='')
        url = f"https://www.bing.com/search?q={encoded_query}&first={page * 10 + 1}"
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        session = get_session()
        response = session.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            
            for item in soup.select('li.b_algo'):
                try:
                    # 修复：使用h2 a获取正确标题，而不是第一个链接
                    a_tag = item.select_one('h2 a')
                    if not a_tag:
                        a_tag = item.select_one('a[href]:not(.tilk)')
                    if a_tag:
                        title = a_tag.get_text(strip=True)
                        href = a_tag.get('href', '')
                        
                        snippet = item.find('p')
                        description = snippet.get_text(strip=True) if snippet else ""
                        
                        if href and href.startswith('http') and 'bing.com' not in href:
                            results.append({
                                "title": title,
                                "link": href,
                                "description": description[:200],
                                "source": "Bing"
                            })
                except Exception:
                    continue
    except Exception as e:
        logger.warning(f"Bing search error: {e}")
    return results


def fetch_ddg_results(query: str, page: int = 0):
    results = []
    try:
        encoded_query = quote(query, safe='')
        url = f"https://html.duckduckgo.com/html/?q={encoded_query}&b={page * 11}"
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        session = get_session()
        response = session.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            
            for item in soup.select('div.result'):
                try:
                    a_tag = item.select_one('a.result__a')
                    if a_tag:
                        title = a_tag.get_text(strip=True)
                        href = a_tag.get('href', '')
                        
                        snippet = item.select_one('a.result__snippet')
                        description = snippet.get_text(strip=True) if snippet else ""
                        
                        if href:
                            results.append({
                                "title": title,
                                "link": href,
                                "description": description[:200],
                                "source": "DuckDuckGo"
                            })
                except Exception:
                    continue
    except Exception as e:
        logger.warning(f"DuckDuckGo search error: {e}")
    return results


def fetch_yahoo_results(query: str, page: int = 0):
    results = []
    try:
        encoded_query = quote(query, safe='')
        url = f"https://search.yahoo.com/search?p={encoded_query}&b={page * 10 + 1}"
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        session = get_session()
        response = session.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            
            for item in soup.select('div.algo'):
                try:
                    a_tag = item.find('a')
                    if a_tag:
                        title = a_tag.get_text(strip=True)
                        href = a_tag.get('href', '')
                        
                        snippet = item.find('p')
                        description = snippet.get_text(strip=True) if snippet else ""
                        
                        if href and href.startswith('http'):
                            results.append({
                                "title": title,
                                "link": href,
                                "description": description[:200],
                                "source": "Yahoo"
                            })
                except Exception:
                    continue
    except Exception as e:
        logger.warning(f"Yahoo search error: {e}")
    return results


def fetch_yandex_results(query: str, page: int = 0):
    results = []
    try:
        encoded_query = quote(query, safe='')
        url = f"https://yandex.com/search/?text={encoded_query}&page={page + 1}"
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        session = get_session()
        response = session.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            
            for item in soup.select('li.serp-item'):
                try:
                    a_tag = item.select_one('a.serp-item__title')
                    if a_tag:
                        title = a_tag.get_text(strip=True)
                        href = a_tag.get('href', '')
                        
                        snippet = item.select_one('div.serp-item__text')
                        description = snippet.get_text(strip=True) if snippet else ""
                        
                        if href and href.startswith('http'):
                            results.append({
                                "title": title,
                                "link": href,
                                "description": description[:200],
                                "source": "Yandex"
                            })
                except Exception:
                    continue
    except Exception as e:
        logger.warning(f"Yandex search error: {e}")
    return results


def fetch_baidu_results(query: str, page: int = 0):
    results = []
    try:
        encoded_query = quote(query, safe='')
        url = f"https://www.baidu.com/s?wd={encoded_query}&pn={page * 10}"
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        session = get_session()
        response = session.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            
            for item in soup.select('div.result'):
                try:
                    a_tag = item.find('a')
                    if a_tag:
                        title = a_tag.get_text(strip=True)
                        href = a_tag.get('href', '')
                        
                        if href and href.startswith('http'):
                            results.append({
                                "title": title,
                                "link": href,
                                "description": "",
                                "source": "Baidu"
                            })
                except Exception:
                    continue
    except Exception as e:
        logger.warning(f"Baidu search error: {e}")
    return results


FAST_ENGINES = ["Baidu", "Bing"]
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
        link = res.get("link", "").rstrip('/')
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

    # Phase 1: 快速引擎（Baidu, Bing）
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

    # 如果快速引擎结果足够，跳过慢速引擎
    unique_so_far = _dedup_results(results)
    if len(unique_so_far) < 20:
        # Phase 2: 慢速引擎（DuckDuckGo, Yahoo, Yandex）
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
    return unique_results[:max_results]
