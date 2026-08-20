"""
Hacker News 搜索源适配器
========================
通过 Algolia HN Search API 检索 Hacker News 帖子。
- 公开 API，无需认证
- 按关键词搜索 story 类型帖子
"""
from typing import Dict, List

from intelnexus.core.logger import get_logger
from intelnexus.core.search.source import BaseSearchSource, CATEGORY_COMMUNITY
from intelnexus.core.search import get_session

logger = get_logger(__name__)


class HackerNewsSource(BaseSearchSource):
    """Hacker News (via Algolia) 适配器。"""

    BASE_URL = "https://hn.algolia.com/api/v1/search"

    def __init__(self, name: str = "HackerNews", category: str = CATEGORY_COMMUNITY,
             enabled: bool = True, requires_proxy: bool = True):
        super().__init__(name=name, category=category, enabled=enabled,
                         requires_proxy=requires_proxy)

    def search(self, query, max_results: int = 20) -> List[Dict]:
        try:
            proxies = self.get_proxies()
            params = {
                "query": query,
                "tags": "story",
                "hitsPerPage": min(max_results, 50),
            }
            session = get_session(proxies)
            resp = session.get(
                self.BASE_URL, params=params, timeout=10
            )
            resp.raise_for_status()
            data = resp.json()
            return self._parse_results(data.get("hits", []))
        except Exception as e:
            logger.warning(f"HackerNewsSource 检索失败: {e}")
            return []

    def _parse_results(self, hits: list) -> List[Dict]:
        results = []
        for item in hits:
            title = item.get("title", "")
            url = item.get("url") or ""
            hn_id = item.get("objectID", "")
            points = item.get("points", 0)
            comments = item.get("num_comments", 0)
            created_at = item.get("created_at", "")

            if not title:
                continue

            link = url if url else f"https://news.ycombinator.com/item?id={hn_id}"

            desc_parts = []
            if item.get("author"):
                desc_parts.append(f"by {item['author']}")
            if points:
                desc_parts.append(f"{points} points")
            if comments:
                desc_parts.append(f"{comments} comments")
            if created_at:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    desc_parts.append(dt.strftime("%Y-%m-%d"))
                except Exception:
                    desc_parts.append(created_at[:10])

            description = " | ".join(desc_parts) if desc_parts else ""

            results.append({
                "title": title,
                "url": link,
                "description": description,
                "source": "HackerNews",
                "category": self.category,
                "published_at": created_at,
                "metadata": {
                    "points": points,
                    "comments": comments,
                    "author": item.get("author", ""),
                }
            })
        return results
