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

from src.logger import get_logger
from src.search import USER_AGENTS

logger = get_logger(__name__)

RSS_SOURCES = [
    {"name": "Google News", "url": "https://news.google.com/rss/search?q={query}"},
    {"name": "Bing News", "url": "https://www.bing.com/news/search?q={query}&format=rss"},
    {"name": "Yahoo News", "url": "https://news.yahoo.com/rss/search?p={query}"},
    {"name": "Reuters", "url": "https://www.reutersagency.com/feed/?best-topics=tech&post_type=best"},
    {"name": "TechCrunch", "url": "https://techcrunch.com/feed/"},
    {"name": "The Verge", "url": "https://www.theverge.com/rss/index.xml"},
    {"name": "Wired", "url": "https://www.wired.com/feed/rss"},
    {"name": "BBC", "url": "http://feeds.bbci.co.uk/news/technology/rss.xml"},
    {"name": "CNN", "url": "http://rss.cnn.com/rss/edition.rss"},
]


class NewsSearch:
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
        
        try:
            response = self.news_client.get_everything(
                q=query,
                language="en",
                sort_by="relevancy",
                page_size=max_results
            )
            
            if response.get("status") == "ok":
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
        except Exception as e:
            logger.warning(f"NewsAPI search error: {e}")
        
        return results
    
    def search_rss(self, query: str, max_results: int = 10) -> List[Dict]:
        results = []
        
        query_lower = query.lower()
        
        for source in RSS_SOURCES:
            if len(results) >= max_results:
                break
            try:
                if "{query}" in source["url"]:
                    url = source["url"].format(query=quote(query))
                else:
                    url = source["url"]
                
                headers = {"User-Agent": random.choice(USER_AGENTS)}
                response = requests.get(url, headers=headers, timeout=8)
                
                if response.status_code == 200:
                    try:
                        soup = BeautifulSoup(response.content, "xml")
                    except Exception:
                        soup = BeautifulSoup(response.content, "html.parser")
                    
                    items = soup.find_all("item")[:max_results]
                    if not items:
                        items = soup.find_all("entry")[:max_results]
                    
                    for item in items:
                        if len(results) >= max_results:
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
                            
                            if query_lower not in title_text.lower() and "{query}" in source["url"]:
                                continue
                            
                            results.append({
                                "title": title_text,
                                "description": desc.get_text(strip=True)[:300] if desc and hasattr(desc, 'get_text') else "",
                                "content": desc.get_text(strip=True) if desc and hasattr(desc, 'get_text') else "",
                                "author": "",
                                "source": source["name"],
                                "url": link_text,
                                "published_at": pub_date.get_text(strip=True) if pub_date and hasattr(pub_date, 'get_text') else "",
                                "image_url": ""
                            })
            except Exception as e:
                logger.warning(f"RSS search error from {source['name']}: {e}")
        
        return results
    
    def search_bing_news(self, query: str, max_results: int = 10) -> List[Dict]:
        results = []
        try:
            url = "https://www.bing.com/news/search"
            params = {"q": query, "form": "QBRE", "sp": "-1"}
            headers = {"User-Agent": random.choice(USER_AGENTS)}
            
            response = requests.get(url, params=params, headers=headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                
                for item in soup.select("div.news-card")[:max_results]:
                    try:
                        title_elem = item.select_one("a.title")
                        snippet_elem = item.select_one("div.snippet")
                        source_elem = item.select_one("div.source")
                        
                        if title_elem:
                            results.append({
                                "title": title_elem.get_text(strip=True),
                                "description": snippet_elem.get_text(strip=True)[:300] if snippet_elem else "",
                                "content": snippet_elem.get_text(strip=True) if snippet_elem else "",
                                "author": "",
                                "source": source_elem.get_text(strip=True) if source_elem else "Bing News",
                                "url": title_elem.get("href", ""),
                                "published_at": "",
                                "image_url": ""
                            })
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
            
            response = requests.get(url, params=params, headers=headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, "xml")
                
                for item in soup.find_all("item")[:max_results]:
                    try:
                        title = item.find("title")
                        link = item.find("link")
                        desc = item.find("description")
                        pub_date = item.find("pubDate")
                        
                        if title and link:
                            results.append({
                                "title": title.get_text(strip=True),
                                "description": desc.get_text(strip=True)[:300] if desc else "",
                                "content": desc.get_text(strip=True) if desc else "",
                                "author": "",
                                "source": "Google News",
                                "url": link.get_text(strip=True),
                                "published_at": pub_date.get_text(strip=True) if pub_date else "",
                                "image_url": ""
                            })
                    except Exception:
                        continue
        except Exception as e:
            logger.warning(f"Google News search error: {e}")
        return results
    
    def search(self, query: str, max_results: int = 10) -> List[Dict]:
        results = []
        
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            
            if self.news_client:
                futures.append(executor.submit(self.search_newsapi, query, max_results))
            
            futures.append(executor.submit(self.search_rss, query, max_results))
            futures.append(executor.submit(self.search_bing_news, query, max_results))
            futures.append(executor.submit(self.search_google_news, query, max_results))
            
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
