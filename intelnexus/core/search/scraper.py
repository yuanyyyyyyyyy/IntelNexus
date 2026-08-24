import random
import ipaddress
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from intelnexus.core.settings.cache import get_cached, set_cached

from intelnexus.core.logger import get_logger
from intelnexus.core.search import USER_AGENTS, get_http_proxies, get_session, get_shared_tor_session

logger = get_logger(__name__)


def is_safe_scrape_target(url: str) -> bool:
    """抓取目标防护（SSRF 第一层）：仅允许 http(s)，拒绝内网/环回地址。

    与 sources.py 的用户源校验独立——搜索结果 URL 同样可能指向内网
    （恶意页面投放 http://169.254.169.254/ 类地址诱导抓取）。
    DNS 解析后的 Rebinding 防护超出本层职责，此处只做语法与字面 IP 判定。
    """
    if not url or not isinstance(url, str):
        return False
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        host = (parsed.hostname or "").lower().strip(".")
        if not host:
            return False
        # 字面量 IPv4/IPv6 直接判定；域名做常见内网名后缀拦截
        if ":" in host:  # IPv6 字面量
            return not ipaddress.ip_address(host.strip("[]")).is_private \
                and not ipaddress.ip_address(host.strip("[]")).is_loopback
        try:
            ip = ipaddress.ip_address(host)
            return not ip.is_private and not ip.is_loopback and not ip.is_link_local
        except ValueError:
            pass
        if host == "localhost" or host.endswith((".local", ".localhost", ".internal")):
            return False
        return True
    except Exception:
        return False


def scrape_single(url_data, rotate=False, rotate_interval=5, control_port=9051, control_password=None):
    """
    Scrapes a single URL using a robust Tor session.
    Returns a tuple (url, scraped_text).
    """
    # 兼容 link/url 双键：registry 归一化输出 url 键，darkweb 等旧路径输出 link 键
    url = url_data.get('link') or url_data.get('url') or ''
    if not url:
        return '', ''
    if not is_safe_scrape_target(url):
        logger.warning(f"跳过不安全抓取目标: {url[:120]}")
        return url, ''

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
            # 复用共享 Tor Session 单例（带连接池与重试）
            session = get_shared_tor_session()
            response = session.get(url, headers=headers, timeout=45)
        else:
            # 复用共享 HTTP Session（连接池 + 自动重试）
            session = get_session(get_http_proxies())
            response = session.get(url, headers=headers, timeout=15)

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
