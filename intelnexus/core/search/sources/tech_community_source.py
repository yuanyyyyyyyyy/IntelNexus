"""
技术社区搜索源适配器
====================
聚合 V2EX、LinuxDo、阮一峰博客等技术社区。
- 公开 RSS，无需认证
- 国内可直连
"""
from typing import Dict, List

import requests
from bs4 import BeautifulSoup

from intelnexus.core.logger import get_logger
from intelnexus.core.search.source import BaseSearchSource, CATEGORY_COMMUNITY
from intelnexus.core.search import get_session

logger = get_logger(__name__)

# 技术社区 RSS 源
TECH_RSS_SOURCES = [
    {"name": "V2EX", "url": "https://www.v2ex.com/feed/tab/hot.xml", "type": "v2ex"},
    {"name": "LinuxDo", "url": "https://linux.do/latest.rss", "type": "linuxdo"},
    {"name": "阮一峰", "url": "http://www.ruanyifeng.com/blog/atom.xml", "type": "ruanyifeng"},
    {"name": "掘金", "url": "https://api.juejin.cn/content_api/v1/content/article_rank?category_id=1&type=hot", "type": "juejin_api"},
]


class TechCommunitySource(BaseSearchSource):
    """技术社区聚合适配器。"""

    def __init__(self, name: str = "TechCommunity", category: str = CATEGORY_COMMUNITY,
                 enabled: bool = True, requires_proxy: bool = False):
        super().__init__(name=name, category=category, enabled=enabled,
                         requires_proxy=requires_proxy)

    def search(self, query, max_results: int = 20) -> List[Dict]:
        try:
            proxies = self.get_proxies()
            session = get_session(proxies)
            results = []

            for source in TECH_RSS_SOURCES:
                if len(results) >= max_results:
                    break

                try:
                    items = self._fetch_rss(session, source, query)
                    results.extend(items)
                except Exception as e:
                    logger.debug(f"获取 {source['name']} 失败: {e}")
                    continue

            return results[:max_results]
        except Exception as e:
            logger.warning(f"TechCommunitySource 检索失败: {e}")
            return []

    def _fetch_rss(self, session, source: dict, query: str) -> List[Dict]:
        """获取单个 RSS 源。"""
        url = source["url"]
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

        resp = session.get(url, headers=headers, timeout=10)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.content, "xml")
        results = []
        query_lower = query.lower()

        items = soup.find_all("item") or soup.find_all("entry")
        for item in items:
            title_elem = item.find("title")
            link_elem = item.find("link")
            desc_elem = item.find("description") or item.find("summary")

            if not title_elem:
                continue

            title = title_elem.get_text(strip=True)
            link = ""
            if link_elem:
                link = link_elem.get_text(strip=True) if hasattr(link_elem, 'get_text') else str(link_elem)

            description = desc_elem.get_text(strip=True)[:300] if desc_elem else ""

            # 关键词过滤
            searchable = f"{title} {description}".lower()
            if query_lower not in searchable:
                continue

            results.append({
                "title": title,
                "url": link,
                "description": description,
                "source": source["name"],
                "category": self.category,
                "published_at": "",
                "metadata": {},
            })

        return results
