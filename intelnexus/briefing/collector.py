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
from intelnexus.config.search_settings import get_news_api_key as NEWS_API_KEY
from config import ENABLE_DARKWEB, TOR_PROXY_PORT


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
        self._scrape = None

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
        为所有关注点采集数据（并行执行，限制并发数避免 NewsAPI 限频）
        
        Returns:
            Dict[str, List[Dict]]: {category_id: [results]}
        """
        categories = _resolve_categories()
        results = {}
        category_ids = list(categories.keys())

        max_workers = min(5, len(category_ids))  # 限制并发数，I/O 密集型可适当提高

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
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

        # 跨类目全局去重（修复：_deduplicate_results 仅在类目内生效，
        # 同一新闻命中多个关注点时会重复出现——实测 360 条中 72 条为跨类目重复）
        seen_urls = set()
        dup_count = 0
        for cat_id, items in results.items():
            unique_items = []
            for item in items:
                u = (item.get("url") or "").rstrip("/")
                if not u:
                    unique_items.append(item)
                    continue
                if u in seen_urls:
                    dup_count += 1
                    continue
                seen_urls.add(u)
                unique_items.append(item)
            results[cat_id] = unique_items
        if dup_count:
            logger.info(f"Cross-category dedup removed {dup_count} duplicate entries")

        return results
    
    def _search_by_keywords(self, queries: List[str], max_results: int = 10) -> List[Dict]:
        """
        使用关键词进行搜索（通过 Registry 统一调度）。

        通过 SearchSourceRegistry.collect() 调度所有搜索源，
        获得跨源去重、权重排序和健康降级。

        Args:
            queries: 查询列表
            max_results: 每个查询的最大结果数

        Returns:
            List[Dict]: 搜索结果
        """
        from intelnexus.core.search.registry import get_registry

        try:
            registry = get_registry(
                news_api_key=NEWS_API_KEY(),
                darkweb_advanced=False,
                tor_port=TOR_PROXY_PORT
            )
        except Exception as e:
            logger.warning(f"Registry 初始化失败: {e}")
            return []

        # 类目内查询并行执行（I/O 密集型，并发远快于串行）
        def _run_single_query(query: str) -> List[Dict]:
            try:
                raw_results = registry.collect(
                    mode="all",
                    query=query,
                    max_results=max_results,
                    threads=5,
                    global_timeout=40  # 从60s降至40s，RSS源通常<5s响应
                )
                return [{
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "content": r.get("description", ""),
                    "description": r.get("description", ""),
                    "source": r.get("source", "Unknown"),
                    "category": r.get("category", ""),
                    "published_at": r.get("published_at", ""),
                    "metadata": r.get("metadata", {}),
                } for r in raw_results]
            except Exception as e:
                logger.warning(f"Registry 搜索失败 query='{query}': {e}")
                return []

        results = []
        query_workers = min(len(queries), 5)
        with ThreadPoolExecutor(max_workers=query_workers) as q_executor:
            q_futures = {
                q_executor.submit(_run_single_query, q): q
                for q in queries
            }
            for q_future in as_completed(q_futures):
                try:
                    results.extend(q_future.result())
                except Exception as e:
                    q = q_futures[q_future]
                    logger.warning(f"查询完成异常 query='{q}': {e}")

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
