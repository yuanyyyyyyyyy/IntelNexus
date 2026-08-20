"""
arXiv 论文搜索源适配器
======================
通过 arXiv RSS 获取最新论文。
- 公开 API，无需认证
- 国内可直连
"""
from typing import Dict, List

import requests
from bs4 import BeautifulSoup

from intelnexus.core.logger import get_logger
from intelnexus.core.search.source import BaseSearchSource, CATEGORY_NEWS
from intelnexus.core.search import get_session

logger = get_logger(__name__)

# arXiv 分类
ARXIV_CATEGORIES = {
    "ai": "cs.AI",
    "ml": "cs.LG",
    "cv": "cs.CV",
    "nlp": "cs.CL",
    "security": "cs.CR",
    "ir": "cs.IR",
}


class ArxivSource(BaseSearchSource):
    """arXiv 论文适配器（基于 RSS）。"""

    BASE_URL = "https://rss.arxiv.org/rss"

    def __init__(self, name: str = "arXiv", category: str = CATEGORY_NEWS,
                 enabled: bool = True, requires_proxy: bool = True):
        super().__init__(name=name, category=category, enabled=enabled,
                         requires_proxy=requires_proxy)

    def search(self, query, max_results: int = 20) -> List[Dict]:
        try:
            proxies = self.get_proxies()
            session = get_session(proxies)

            # 根据查询确定分类
            category = self._get_category(query)
            url = f"{self.BASE_URL}/{category}"

            headers = {"User-Agent": "Mozilla/5.0"}
            resp = session.get(url, headers=headers, timeout=15)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.content, "xml")
            results = []

            # 解析 RSS 条目
            items = soup.find_all("item") or soup.find_all("entry")
            query_lower = query.lower()

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
                if query_lower not in searchable and query_lower not in category.lower():
                    continue

                # 提取作者
                author_elem = item.find("author") or item.find("dc:creator")
                author = author_elem.get_text(strip=True) if author_elem else ""

                results.append({
                    "title": title,
                    "url": link,
                    "description": description,
                    "source": "arXiv",
                    "category": self.category,
                    "published_at": "",
                    "metadata": {
                        "author": author,
                        "arxiv_category": category,
                    },
                })

                if len(results) >= max_results:
                    break

            return results
        except Exception as e:
            logger.warning(f"ArxivSource 检索失败: {e}")
            return []

    def _get_category(self, query: str) -> str:
        """根据查询关键词确定 arXiv 分类。"""
        query_lower = query.lower()
        for keyword, cat in ARXIV_CATEGORIES.items():
            if keyword in query_lower:
                return cat
        return "cs.AI"  # 默认 AI 分类
