import requests
import random
import re
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib.parse import quote
import warnings
warnings.filterwarnings("ignore")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]

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


def get_session():
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
    return session


def fetch_bing_results(query: str, page: int = 0):
    results = []
    try:
        url = f"https://www.bing.com/search?q={quote(query)}&first={page * 10 + 1}"
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        session = get_session()
        response = session.get(url, headers=headers, timeout=20)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            
            for item in soup.select('li.b_algo'):
                try:
                    a_tag = item.find('a')
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
                except:
                    continue
    except Exception as e:
        print(f"Bing search error: {e}")
    return results


def fetch_ddg_results(query: str, page: int = 0):
    results = []
    try:
        url = f"https://html.duckduckgo.com/html/?q={quote(query)}&b={page * 11}"
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        session = get_session()
        response = session.get(url, headers=headers, timeout=20)
        
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
                except:
                    continue
    except Exception as e:
        print(f"DuckDuckGo search error: {e}")
    return results


def fetch_yahoo_results(query: str, page: int = 0):
    results = []
    try:
        url = f"https://search.yahoo.com/search?p={quote(query)}&b={page * 10 + 1}"
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        session = get_session()
        response = session.get(url, headers=headers, timeout=20)
        
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
                except:
                    continue
    except Exception as e:
        print(f"Yahoo search error: {e}")
    return results


def fetch_yandex_results(query: str, page: int = 0):
    results = []
    try:
        url = f"https://yandex.com/search/?text={quote(query)}&page={page + 1}"
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        session = get_session()
        response = session.get(url, headers=headers, timeout=20)
        
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
                except:
                    continue
    except Exception as e:
        print(f"Yandex search error: {e}")
    return results


def fetch_baidu_results(query: str, page: int = 0):
    results = []
    try:
        url = f"https://www.baidu.com/s?wd={quote(query)}&pn={page * 10}"
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        session = get_session()
        response = session.get(url, headers=headers, timeout=20)
        
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
                except:
                    continue
    except Exception as e:
        print(f"Baidu search error: {e}")
    return results


def get_web_results(query: str, max_workers: int = 5, max_results: int = 50) -> list:
    results = []
    pages_per_engine = 4
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        
        for page in range(pages_per_engine):
            futures.append(executor.submit(fetch_bing_results, query, page))
            futures.append(executor.submit(fetch_ddg_results, query, page))
            futures.append(executor.submit(fetch_yahoo_results, query, page))
            futures.append(executor.submit(fetch_yandex_results, query, page))
            futures.append(executor.submit(fetch_baidu_results, query, page))
        
        for future in as_completed(futures):
            try:
                result_urls = future.result()
                results.extend(result_urls)
            except Exception as e:
                print(f"Search error: {e}")
    
    seen_links = set()
    unique_results = []
    for res in results:
        link = res.get("link", "").rstrip('/')
        if link and link not in seen_links and len(link) > 10:
            seen_links.add(link)
            unique_results.append(res)
    
    return unique_results[:max_results]
