import time
import requests
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor, as_completed
import random

try:
    from newsapi import NewsApiClient
except ImportError:
    NewsApiClient = None

from intelnexus.core.logger import get_logger
from intelnexus.core.search import USER_AGENTS, get_http_proxies, get_http_proxies_for, get_session, is_blocked_domain, relevance_passes

logger = get_logger(__name__)

RSS_FETCH_TIMEOUT = 25

RSS_SOURCES = [
    # ---- 国内可直连、无需代理（高质量订阅源，不过滤相关性，仅域名黑名单）----
    {"name": "Bing News", "url": "https://www.bing.com/news/search?q={query}&format=rss", "requires_proxy": False},
    {"name": "Solidot", "url": "https://www.solidot.org/index.rss", "requires_proxy": False},
    {"name": "量子位", "url": "https://www.qbitai.com/feed", "requires_proxy": False},
    {"name": "IT之家", "url": "https://www.ithome.com/rss/", "requires_proxy": False},
    {"name": "少数派", "url": "https://sspai.com/feed", "requires_proxy": False},
    # ---- 国内安全/技术订阅源（无需代理）----
    {"name": "FreeBuf", "url": "https://www.freebuf.com/feed", "requires_proxy": False},
    {"name": "安全客", "url": "https://api.anquanke.com/data/v1/rss", "requires_proxy": False},
    {"name": "InfoQ 中文", "url": "https://www.infoq.cn/feed", "requires_proxy": False},
    {"name": "先知社区", "url": "https://xz.aliyun.com/feed", "requires_proxy": False},
    # ---- 国内 AI 专项订阅源（无需代理）----
    {"name": "AI科技评论", "url": "https://www.leiphone.com/feed", "requires_proxy": False},
    # ---- 境外源，需代理（无代理时自动跳过，避免无效超时）----
    {"name": "Google News", "url": "https://news.google.com/rss/search?q={query}", "requires_proxy": True},
    {"name": "Yahoo News", "url": "https://news.yahoo.com/rss/search?p={query}", "requires_proxy": True},
    {"name": "Reuters", "url": "https://www.reutersagency.com/feed/?best-topics=tech&post_type=best", "requires_proxy": True},
    {"name": "TechCrunch", "url": "https://techcrunch.com/feed/", "requires_proxy": True},
    {"name": "The Verge", "url": "https://www.theverge.com/rss/index.xml", "requires_proxy": True},
    {"name": "Wired", "url": "https://www.wired.com/feed/rss", "requires_proxy": True},
    {"name": "BBC", "url": "http://feeds.bbci.co.uk/news/technology/rss.xml", "requires_proxy": True},
    {"name": "CNN", "url": "http://rss.cnn.com/rss/edition.rss", "requires_proxy": True},
    {"name": "Hacker News", "url": "https://hnrss.org/newest?q=AI+OR+LLM+OR+GPT+OR+deep+learning", "requires_proxy": True},
]


class NewsSearch:
    # 类级速率限制：记录上次 NewsAPI 限频时间，避免重复请求
    _newsapi_last_rate_limit = 0.0
    _newsapi_cooldown_seconds = 300  # 5分钟冷却期
    # 每日请求计数器（开发者账户限制 100次/24h，预留余量）
    _newsapi_daily_count = 0
    _newsapi_daily_limit = 80
    _newsapi_daily_reset_time = 0.0  # 上次重置时间戳

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        if NewsApiClient and api_key:
            try:
                self.news_client = NewsApiClient(api_key=api_key)
            except Exception as e:
                logger.warning(f"NewsAPI init error: {e}")
                self.news_client = None
        else:
            self.news_client = None

    def search_newsapi(self, query: str, max_results: int = 10) -> List[Dict]:
        results = []
        if not self.news_client:
            return results

        now = time.time()

        # 每日计数器重置（每24小时）
        if now - NewsSearch._newsapi_daily_reset_time > 86400:
            if NewsSearch._newsapi_daily_count > 0:
                logger.info(f"NewsAPI 每日计数器重置（昨日请求 {NewsSearch._newsapi_daily_count} 次）")
            NewsSearch._newsapi_daily_count = 0
            NewsSearch._newsapi_daily_reset_time = now

        # 每日限额检查
        if NewsSearch._newsapi_daily_count >= NewsSearch._newsapi_daily_limit:
            logger.info(f"NewsAPI 已达每日限额 ({NewsSearch._newsapi_daily_limit})，跳过本次请求")
            return results

        # 速率限制：如果刚被限频，跳过请求
        if now - self._newsapi_last_rate_limit < self._newsapi_cooldown_seconds:
            remaining = int(self._newsapi_cooldown_seconds - (now - self._newsapi_last_rate_limit))
            logger.info(f"NewsAPI 冷却中（剩余 {remaining}s），跳过本次请求")
            return results

        try:
            response = self.news_client.get_everything(
                q=query,
                language="en",
                sort_by="relevancy",
                page_size=max_results
            )

            if response.get("status") == "ok":
                NewsSearch._newsapi_daily_count += 1
                for article in response.get("articles", []):
                    results.append({
                        "title": article.get("title", ""),
                        "description": article.get("description", "")[:300],
                        "content": article.get("content", ""),
                        "author": article.get("author", ""),
                        "source": article.get("source", {}).get("name", "NewsAPI"),
                        "url": article.get("url", ""),
                        "published_at": article.get("publishedAt", ""),
                        "image_url": article.get("urlToImage", "")
                    })
            elif response.get("code") == "rateLimited":
                NewsSearch._newsapi_last_rate_limit = now
                NewsSearch._newsapi_daily_count += 1  # 限频请求也计入配额
                logger.warning(f"NewsAPI 限频，进入 {self._newsapi_cooldown_seconds}s 冷却期 (今日已用 {NewsSearch._newsapi_daily_count}/{NewsSearch._newsapi_daily_limit})")
        except Exception as e:
            err_str = str(e).lower()
            if "rate" in err_str or "429" in err_str:
                NewsSearch._newsapi_last_rate_limit = now
                NewsSearch._newsapi_daily_count += 1
                logger.warning(f"NewsAPI 限频异常，进入 {self._newsapi_cooldown_seconds}s 冷却期 (今日已用 {NewsSearch._newsapi_daily_count}/{NewsSearch._newsapi_daily_limit}): {e}")
            else:
                logger.warning(f"NewsAPI search error: {e}")

        return results

    def _fetch_rss_with_retry(self, url: str, headers: Dict, proxies, timeout: int = RSS_FETCH_TIMEOUT, max_retries: int = 2):
        """带指数退避的 RSS 请求封装，仅在 requests 异常时重试。"""
        session = get_session(proxies)
        last_err = None
        for attempt in range(max_retries + 1):
            try:
                return session.get(url, headers=headers, timeout=timeout)
            except requests.exceptions.RequestException as e:
                last_err = e
                if attempt < max_retries:
                    logger.debug(f"RSS 请求重试 {attempt + 1}/{max_retries}: {e}")
                    time.sleep(0.5 * (2 ** attempt))
                    continue
        raise last_err

    def search_rss(self, query: str, max_results: int = 10) -> List[Dict]:
        results = []

        query_lower = query.lower()
        query_tokens = set(query_lower.split())

        # 安全相关关键词（用于过滤非安全类RSS源的无关内容）
        SECURITY_KEYWORDS = [
            "漏洞", "安全", "攻击", "泄露", "CVE", "vulnerability", "hack",
            "cyber", "malware", "ransomware", "phishing", "breach", "exploit",
            "后门", "木马", "勒索", "钓鱼", "入侵", "防护", "补丁", "patch",
            "威胁", "情报", "审计", "加固", "应急", "响应", "检测", "监控",
            "防火墙", "IDS", "IPS", "WAF", "EDR", "XDR", "SIEM",
        ]

        # 非安全类RSS源（需要额外安全关键词过滤）
        NON_SECURITY_SOURCES = ["Solidot", "量子位", "IT之家", "少数派"]

        for source in RSS_SOURCES:
            if len(results) >= max_results:
                break
            if source.get("requires_proxy") and not get_http_proxies():
                logger.info(f"跳过需代理源 {source['name']}（未配置代理）")
                continue
            try:
                if "{query}" in source["url"]:
                    url = source["url"].format(query=quote(query))
                else:
                    url = source["url"]

                headers = {"User-Agent": random.choice(USER_AGENTS)}
                response = self._fetch_rss_with_retry(url, headers, get_http_proxies_for(source.get("requires_proxy")))

                source_results = 0
                source_limit = 5 if source["name"] == "Solidot" else max_results
                if response.status_code == 200:
                    try:
                        soup = BeautifulSoup(response.content, "xml")
                    except Exception:
                        soup = BeautifulSoup(response.content, "html.parser")

                    items = soup.find_all("item")[:max_results]
                    if not items:
                        items = soup.find_all("entry")[:max_results]

                    for item in items:
                        if source_results >= source_limit:
                            break

                        title = item.find("title")
                        link = item.find("link")
                        desc = item.find("description") or item.find("summary") or item.find("content")
                        pub_date = item.find("pubDate") or item.find("published") or item.find("dc:date")

                        link_text = ""
                        if link:
                            if hasattr(link, 'get_text'):
                                link_text = link.get_text(strip=True)
                            else:
                                link_text = str(link)

                        if title and link_text:
                            title_text = title.get_text(strip=True) if hasattr(title, 'get_text') else str(title)

                            title_lower = title_text.lower()
                            desc_text = (desc.get_text(strip=True) if desc and hasattr(desc, 'get_text') else "").lower()
                            combined_text = f"{title_lower} {desc_text}"

                            # 1. 查询token匹配（至少匹配1个）
                            has_query_match = any(token in combined_text for token in query_tokens)
                            if not has_query_match:
                                continue

                            # 2. 非安全类源：要求标题包含安全相关关键词
                            if source["name"] in NON_SECURITY_SOURCES:
                                has_security_keyword = any(kw.lower() in combined_text for kw in SECURITY_KEYWORDS)
                                if not has_security_keyword:
                                    continue

                            item = {
                                "title": title_text,
                                "description": desc.get_text(strip=True)[:300] if desc and hasattr(desc, 'get_text') else "",
                                "content": desc.get_text(strip=True) if desc and hasattr(desc, 'get_text') else "",
                                "author": "",
                                "source": source["name"],
                                "url": link_text,
                                "published_at": pub_date.get_text(strip=True) if pub_date and hasattr(pub_date, 'get_text') else "",
                                "image_url": ""
                            }

                            if is_blocked_domain(item["url"]):
                                continue

                            results.append(item)
                            source_results += 1
            except Exception as e:
                logger.warning(f"RSS search error from {source['name']}: {e}")

            if source_results > 0:
                logger.info(f"RSS源 {source['name']} 返回 {source_results} 条结果")

        return results

    def search_bing_news(self, query: str, max_results: int = 10) -> List[Dict]:
        results = []
        try:
            url = "https://www.bing.com/news/search"
            params = {"q": query, "form": "QBRE", "sp": "-1"}
            headers = {"User-Agent": random.choice(USER_AGENTS)}

            response = get_session(None).get(url, params=params, headers=headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")

                for item in soup.select("div.news-card")[:max_results]:
                    try:
                        title_elem = item.select_one("a.title")
                        snippet_elem = item.select_one("div.snippet")
                        source_elem = item.select_one("div.source")

                        if title_elem:
                            item = {
                                "title": title_elem.get_text(strip=True),
                                "description": snippet_elem.get_text(strip=True)[:300] if snippet_elem else "",
                                "content": snippet_elem.get_text(strip=True) if snippet_elem else "",
                                "author": "",
                                "source": source_elem.get_text(strip=True) if source_elem else "Bing News",
                                "url": title_elem.get("href", ""),
                                "published_at": "",
                                "image_url": ""
                            }
                            if is_blocked_domain(item["url"]) or not relevance_passes(item, query):
                                continue
                            results.append(item)
                    except Exception:
                        continue
        except Exception as e:
            logger.warning(f"Bing news search error: {e}")
        return results

    def search_google_news(self, query: str, max_results: int = 10) -> List[Dict]:
        results = []
        try:
            url = "https://news.google.com/rss/search"
            params = {"q": query, "hl": "en-US", "gl": "US"}
            headers = {"User-Agent": random.choice(USER_AGENTS)}

            response = get_session(get_http_proxies()).get(url, params=params, headers=headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, "xml")

                for item in soup.find_all("item")[:max_results]:
                    try:
                        title = item.find("title")
                        link = item.find("link")
                        desc = item.find("description")
                        pub_date = item.find("pubDate")

                        if title and link:
                            item = {
                                "title": title.get_text(strip=True),
                                "description": desc.get_text(strip=True)[:300] if desc else "",
                                "content": desc.get_text(strip=True) if desc else "",
                                "author": "",
                                "source": "Google News",
                                "url": link.get_text(strip=True),
                                "published_at": pub_date.get_text(strip=True) if pub_date else "",
                                "image_url": ""
                            }
                            if is_blocked_domain(item["url"]) or not relevance_passes(item, query):
                                continue
                            results.append(item)
                    except Exception:
                        continue
        except Exception as e:
            logger.warning(f"Google News search error: {e}")
        return results

    def search(self, query: str, max_results: int = 10) -> List[Dict]:
        results = []

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = []

            if self.news_client and get_http_proxies():
                futures.append(executor.submit(self.search_newsapi, query, max_results))
            elif self.news_client:
                logger.info("跳过 NewsAPI 检索（未配置代理）")

            futures.append(executor.submit(self.search_rss, query, max_results))
            futures.append(executor.submit(self.search_bing_news, query, max_results))
            if get_http_proxies():
                futures.append(executor.submit(self.search_google_news, query, max_results))
            else:
                logger.info("跳过 Google News 直连检索（未配置代理）")

            for future in futures:
                try:
                    r = future.result()
                    if r:
                        results.extend(r)
                except Exception as e:
                    logger.warning(f"Search error: {e}")

        seen_urls = set()
        unique_results = []
        for r in results:
            url = r.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_results.append(r)

        return unique_results[:max_results * 3]


def get_news_results(query, max_results: int = 10, api_key: Optional[str] = None) -> List[Dict]:
    searcher = NewsSearch(api_key=api_key)
    if isinstance(query, list):
        all_results = []
        for q in query:
            all_results.extend(searcher.search(q, max_results))
        return all_results[:max_results]
    return searcher.search(query, max_results)
