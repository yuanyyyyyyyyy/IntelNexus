import random
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from intelnexus.core.settings.cache import get_cached, set_cached

from intelnexus.core.logger import get_logger
from intelnexus.core.search import USER_AGENTS, get_tor_session

logger = get_logger(__name__)

def scrape_single(url_data, rotate=False, rotate_interval=5, control_port=9051, control_password=None):
    """
    Scrapes a single URL using a robust Tor session.
    Returns a tuple (url, scraped_text).
    """
    url = url_data['link']

    cached = get_cached(url)
    if cached is not None:
        return (url, cached)

    if url.lower().endswith('.pdf') or '.pdf?' in url.lower():
        return (url, f"{url_data['title']} - [PDF文件，请直接下载查看]")

    use_tor = ".onion" in url

    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    try:
        if use_tor:
            session = get_tor_session()
            response = session.get(url, headers=headers, timeout=45)
        else:
            response = requests.get(url, headers=headers, timeout=15)

        if response.status_code == 200:
            if response.encoding is None or response.encoding.lower() == 'iso-8859-1':
                response.encoding = response.apparent_encoding or 'utf-8'

            soup = BeautifulSoup(response.text, "html.parser")
            for script in soup(["script", "style"]):
                script.extract()
            text = soup.get_text(separator=' ', strip=True)
            text = ' '.join(text.split())

            if len(text) < 100:
                scraped_text = url_data['title']
            else:
                scraped_text = f"{url_data['title']} - {text}"
        else:
            scraped_text = url_data['title']
    except Exception as e:
        scraped_text = url_data['title']

    return url, scraped_text

def scrape_multiple(urls_data, max_workers=5):
    """
    Scrapes multiple URLs concurrently using a thread pool.
    """
    results = {}
    max_chars = 3000

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {
            executor.submit(scrape_single, url_data): url_data
            for url_data in urls_data
        }
        for future in as_completed(future_to_url):
            try:
                url, content = future.result()
                if len(content) > max_chars:
                    content = content[:max_chars] + "...(truncated)"
                results[url] = content
                set_cached(url, content)
            except Exception:
                continue

    return results
