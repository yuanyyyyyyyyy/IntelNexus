"""
AI简报数据采集器
===============
根据关注点配置，从多个来源采集数据
"""

from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from intelnexus.briefing.config import get_all_categories, WATCH_CATEGORIES
from intelnexus.config.sources import get_enabled_sources, get_sources_by_category
from intelnexus.config.briefing_drafts import consume_drafts
from intelnexus.core.logger import get_logger
from intelnexus.topics.store import topic_to_category_map
from config import NEWS_API_KEY, ENABLE_DARKWEB


def _resolve_categories() -> dict:
    """优先使用 Topic Registry（用户可固化常驻关注点），回退 WATCH_CATEGORIES。"""
    try:
        topics_map = topic_to_category_map()
        if topics_map:
            return topics_map
    except Exception as e:
        logger.warning(f"Topic Registry 读取失败，回退预设关注点: {e}")
    return get_all_categories()

logger = get_logger(__name__)


class AIBriefingCollector:
    """AI简报数据采集器"""
    
    def __init__(self):
        """初始化采集器"""
        self._web_search = None
        self._news_search = None
        self._scrape = None
        self._darkweb_search = None
    
    def _get_web_search(self):
        """延迟加载web_search模块"""
        if self._web_search is None:
            try:
                from intelnexus.core.search.web import get_web_results
                self._web_search = get_web_results
            except ImportError:
                logger.warning("web_search module not available")
                self._web_search = lambda q, max_r=10: []
        return self._web_search
    
    def _get_news_search(self):
        """延迟加载news_search模块"""
        if self._news_search is None:
            try:
                from intelnexus.core.search.news import get_news_results
                self._news_search = get_news_results
            except ImportError:
                logger.warning("news_search module not available")
                self._news_search = lambda q, max_r=10, api_key=None: []
        return self._news_search
    
    def _get_scrape(self):
        """延迟加载scrape模块"""
        if self._scrape is None:
            try:
                from intelnexus.core.search.scraper import scrape_multiple
                self._scrape = scrape_multiple
            except ImportError:
                logger.warning("scrape module not available")
                self._scrape = lambda urls, max_workers=5: {}
        return self._scrape

    def _get_darkweb_search(self):
        """延迟加载暗网搜索模块（仅在 ENABLE_DARKWEB 为真时生效）"""
        if self._darkweb_search is None:
            try:
                from intelnexus.search_app.darkweb import get_darkweb_results
                # get_darkweb_results 内部已检查 ENABLE_DARKWEB 主开关
                self._darkweb_search = lambda q, max_r=10: get_darkweb_results(
                    q, max_workers=max_r, advanced_mode=False,
                    tor_port=9150, ui_sites=None)
            except ImportError:
                logger.warning("darkweb module not available")
                self._darkweb_search = lambda q, max_r=10: []
        return self._darkweb_search
    
    def collect_for_category(self, category: str, max_results: int = 20) -> List[Dict]:
        """
        为单个关注点采集数据
        
        Args:
            category: 关注点ID
            max_results: 每个来源的最大结果数
        
        Returns:
            List[Dict]: 搜索结果列表
        """
        categories = _resolve_categories()
        if category not in categories:
            logger.warning(f"Unknown category: {category}")
            return []
        
        cat_config = categories[category]
        all_results = []
        
        # 1. 使用关键词搜索（web + news + 暗网）
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
        
        # 3. 合并收藏草稿（高优：置顶该关注点）
        drafts = consume_drafts([category]).get(category, [])
        for d in drafts:
            all_results.insert(0, {
                "title": d.get("title", ""),
                "url": d.get("url", ""),
                "content": d.get("content", ""),
                "description": d.get("description", ""),
                "source": d.get("source", "Collected Draft"),
                "from_draft": True,
            })
        
        # 4. 去重
        all_results = self._deduplicate_results(all_results)
        
        return all_results[:max_results * 3]
    
    def collect_all_categories(self) -> Dict[str, List[Dict]]:
        """
        为所有关注点采集数据（并行执行）
        
        Returns:
            Dict[str, List[Dict]]: {category_id: [results]}
        """
        categories = _resolve_categories()
        results = {}
        category_ids = list(categories.keys())

        with ThreadPoolExecutor(max_workers=len(category_ids)) as executor:
            futures = {
                executor.submit(self.collect_for_category, cat_id): cat_id
                for cat_id in category_ids
            }
            for future in as_completed(futures):
                cat_id = futures[future]
                try:
                    results[cat_id] = future.result()
                    logger.info(f"Collected {len(results[cat_id])} results for {categories[cat_id]['name']}")
                except Exception as e:
                    logger.error(f"Error collecting {cat_id}: {e}")
                    results[cat_id] = []

        return results
    
    def _search_by_keywords(self, queries: List[str], max_results: int = 10) -> List[Dict]:
        """
        使用关键词进行搜索（web + news + 暗网）
        
        Args:
            queries: 查询列表
            max_results: 每个查询的最大结果数
        
        Returns:
            List[Dict]: 搜索结果
        """
        results = []
        web_search = self._get_web_search()
        news_search = self._get_news_search()
        darkweb_search = self._get_darkweb_search()
        
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
                news_results = news_search(query, max_results=max_results, api_key=NEWS_API_KEY)
                for r in news_results:
                    results.append({
                        "title": r.get("title", ""),
                        "url": r.get("url", r.get("link", "")),
                        "content": r.get("content", r.get("description", "")),
                        "description": r.get("description", ""),
                        "source": r.get("source", "News Search")
                    })

                # 暗网搜索（仅在 ENABLE_DARKWEB 为真时生效）
                if ENABLE_DARKWEB:
                    try:
                        darkweb_results = darkweb_search(query, max_results=max_results)
                        for r in darkweb_results:
                            results.append({
                                "title": r.get("title", ""),
                                "url": r.get("url", r.get("link", "")),
                                "content": r.get("content", r.get("description", "")),
                                "description": r.get("description", ""),
                                "source": r.get("source", "Dark Web")
                            })
                    except Exception as e:
                        logger.warning(f"Darkweb search error for query '{query}': {e}")
            except Exception as e:
                logger.warning(f"Search error for query '{query}': {e}")
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
            logger.warning(f"Scrape error: {e}")
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
