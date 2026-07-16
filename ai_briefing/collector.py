"""
AI简报数据采集器
===============
根据关注点配置，从多个来源采集数据
"""

import sys
import os
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from ai_briefing.config import WATCH_CATEGORIES
from src.config.sources import get_enabled_sources, get_sources_by_category


class AIBriefingCollector:
    """AI简报数据采集器"""
    
    def __init__(self):
        """初始化采集器"""
        self._web_search = None
        self._news_search = None
        self._scrape = None
    
    def _get_web_search(self):
        """延迟加载web_search模块"""
        if self._web_search is None:
            try:
                from web_search import get_web_results
                self._web_search = get_web_results
            except ImportError:
                print("Warning: web_search module not available")
                self._web_search = lambda q, max_r=10: []
        return self._web_search
    
    def _get_news_search(self):
        """延迟加载news_search模块"""
        if self._news_search is None:
            try:
                from news_search import get_news_results
                self._news_search = get_news_results
            except ImportError:
                print("Warning: news_search module not available")
                self._news_search = lambda q, max_r=10, api_key=None: []
        return self._news_search
    
    def _get_scrape(self):
        """延迟加载scrape模块"""
        if self._scrape is None:
            try:
                from scrape import scrape_multiple
                self._scrape = scrape_multiple
            except ImportError:
                print("Warning: scrape module not available")
                self._scrape = lambda urls, max_workers=5: {}
        return self._scrape
    
    def collect_for_category(self, category: str, max_results: int = 20) -> List[Dict]:
        """
        为单个关注点采集数据
        
        Args:
            category: 关注点ID
            max_results: 每个来源的最大结果数
        
        Returns:
            List[Dict]: 搜索结果列表
        """
        if category not in WATCH_CATEGORIES:
            print(f"Unknown category: {category}")
            return []
        
        cat_config = WATCH_CATEGORIES[category]
        all_results = []
        
        # 1. 使用关键词搜索
        search_results = self._search_by_keywords(
            cat_config.get("search_queries", []),
            max_results
        )
        all_results.extend(search_results)
        
        # 2. 抓取自定义URL
        custom_urls = get_sources_by_category(category)
        if custom_urls:
            url_results = self._scrape_custom_urls(custom_urls)
            for url, content in url_results.items():
                if content and len(content) > 100:
                    # 找到对应的源信息
                    source_info = next(
                        (s for s in custom_urls if s["url"] == url),
                        {"name": url, "url": url}
                    )
                    all_results.append({
                        "title": source_info.get("name", url[:50]),
                        "url": url,
                        "content": content,
                        "description": content[:200],
                        "source": source_info.get("name", "Custom Source")
                    })
        
        # 3. 去重
        all_results = self._deduplicate_results(all_results)
        
        return all_results[:max_results * 3]
    
    def collect_all_categories(self) -> Dict[str, List[Dict]]:
        """
        为所有关注点采集数据
        
        Returns:
            Dict[str, List[Dict]]: {category_id: [results]}
        """
        results = {}
        
        for category_id in WATCH_CATEGORIES.keys():
            print(f"Collecting data for: {WATCH_CATEGORIES[category_id]['name']}")
            results[category_id] = self.collect_for_category(category_id)
        
        return results
    
    def _search_by_keywords(self, queries: List[str], max_results: int = 10) -> List[Dict]:
        """
        使用关键词进行搜索
        
        Args:
            queries: 查询列表
            max_results: 每个查询的最大结果数
        
        Returns:
            List[Dict]: 搜索结果
        """
        results = []
        web_search = self._get_web_search()
        news_search = self._get_news_search()
        
        for query in queries:
            try:
                # 网页搜索
                web_results = web_search(query, max_results=max_results)
                for r in web_results:
                    results.append({
                        "title": r.get("title", ""),
                        "url": r.get("url", r.get("link", "")),
                        "content": r.get("content", r.get("description", "")),
                        "description": r.get("description", ""),
                        "source": r.get("source", "Web Search")
                    })
                
                # 新闻搜索
                news_results = news_search(query, max_results=max_results)
                for r in news_results:
                    results.append({
                        "title": r.get("title", ""),
                        "url": r.get("url", r.get("link", "")),
                        "content": r.get("content", r.get("description", "")),
                        "description": r.get("description", ""),
                        "source": r.get("source", "News Search")
                    })
            except Exception as e:
                print(f"Search error for query '{query}': {e}")
                continue
        
        return results
    
    def _scrape_custom_urls(self, urls: List[Dict]) -> Dict[str, str]:
        """
        抓取自定义URL的内容
        
        Args:
            urls: URL列表，每项包含url字段
        
        Returns:
            Dict[str, str]: {url: content}
        """
        scrape = self._get_scrape()
        
        urls_data = []
        for source in urls:
            urls_data.append({
                "url": source["url"],
                "title": source.get("name", source["url"][:50])
            })
        
        if not urls_data:
            return {}
        
        try:
            return scrape(urls_data, max_workers=5)
        except Exception as e:
            print(f"Scrape error: {e}")
            return {}
    
    def _deduplicate_results(self, results: List[Dict]) -> List[Dict]:
        """
        去重：基于URL去重
        
        Args:
            results: 搜索结果列表
        
        Returns:
            List[Dict]: 去重后的结果
        """
        seen_urls = set()
        unique_results = []
        
        for r in results:
            url = r.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_results.append(r)
            elif not url and r.get("title"):
                # 如果没有URL，基于标题去重
                title = r.get("title", "")
                if title not in seen_urls:
                    seen_urls.add(title)
                    unique_results.append(r)
        
        return unique_results
    
    def collect_rss_feeds(self, feeds: List[Dict]) -> List[Dict]:
        """
        从RSS订阅源采集数据
        
        Args:
            feeds: RSS源列表
        
        Returns:
            List[Dict]: RSS条目列表
        """
        results = []
        
        try:
            import requests
            from bs4 import BeautifulSoup
            import random
            
            USER_AGENTS = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101"
            ]
            
            for feed in feeds:
                try:
                    headers = {"User-Agent": random.choice(USER_AGENTS)}
                    response = requests.get(feed["url"], headers=headers, timeout=10)
                    
                    if response.status_code == 200:
                        try:
                            soup = BeautifulSoup(response.content, "xml")
                        except:
                            soup = BeautifulSoup(response.content, "html.parser")
                        
                        items = soup.find_all("item")[:10]
                        if not items:
                            items = soup.find_all("entry")[:10]
                        
                        for item in items:
                            title = item.find("title")
                            link = item.find("link")
                            desc = item.find("description") or item.find("summary")
                            pub_date = item.find("pubDate") or item.find("published")
                            
                            if title and link:
                                link_text = link.get_text(strip=True) if hasattr(link, 'get_text') else str(link)
                                results.append({
                                    "title": title.get_text(strip=True) if hasattr(title, 'get_text') else str(title),
                                    "url": link_text,
                                    "content": desc.get_text(strip=True) if desc and hasattr(desc, 'get_text') else "",
                                    "description": desc.get_text(strip=True)[:200] if desc and hasattr(desc, 'get_text') else "",
                                    "source": feed.get("name", "RSS Feed"),
                                    "published_at": pub_date.get_text(strip=True) if pub_date and hasattr(pub_date, 'get_text') else ""
                                })
                except Exception as e:
                    print(f"RSS feed error for {feed.get('name', 'unknown')}: {e}")
                    continue
        except ImportError:
            print("Warning: requests or bs4 not available for RSS parsing")
        
        return results
