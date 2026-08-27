"""
HuggingFace 博客搜索源适配器
===========================
通过 HuggingFace 博客 RSS 获取 AI 工具/模型动态。
- 公开 RSS，无需认证
- 国内可直连
"""
from typing import Dict, List

import requests
from bs4 import BeautifulSoup

from intelnexus.core.logger import get_logger
from intelnexus.core.search.source import BaseSearchSource, CATEGORY_NEWS
from intelnexus.core.search import get_session

logger = get_logger(__name__)


class HuggingFaceSource(BaseSearchSource):
    """HuggingFace 博客适配器。"""

    RSS_URL = "https://huggingface.co/blog/feed.xml"

    def __init__(self, name: str = "HuggingFace", category: str = CATEGORY_NEWS,
                 enabled: bool = True, requires_proxy: bool = True):
        super().__init__(name=name, category=category, enabled=enabled,
                         requires_proxy=requires_proxy)

    def search(self, query, max_results: int = 20) -> List[Dict]:
        try:
            proxies = self.get_proxies()
            session = get_session(proxies)

            headers = {"User-Agent": "Mozilla/5.0"}
            resp = session.get(self.RSS_URL, headers=headers, timeout=15)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.content, "xml")
            results = []
            query_lower = query.lower()

            items = soup.find_all("entry")
            for item in items:
                title_elem = item.find("title")
                link_elem = item.find("link")
                summary_elem = item.find("summary") or item.find("content")

                if not title_elem:
                    continue

                title = title_elem.get_text(strip=True)
                link = ""
                if link_elem:
                    link = link_elem.get("href", "")

                description = summary_elem.get_text(strip=True)[:300] if summary_elem else ""

                # 关键词过滤
                searchable = f"{title} {description}".lower()
                if query_lower not in searchable:
                    continue

                # 提取作者
                author_elem = item.find("author")
                author = author_elem.get_text(strip=True) if author_elem else ""

                # 提取发布时间
                published_elem = item.find("published") or item.find("updated")
                published = published_elem.get_text(strip=True) if published_elem else ""

                results.append({
                    "title": title,
                    "url": link,
                    "description": description,
                    "source": "HuggingFace",
                    "category": self.category,
                    "published_at": published,
                    "metadata": {
                        "author": author,
                    },
                })

                if len(results) >= max_results:
                    break

            return results
        except Exception as e:
            logger.warning(f"HuggingFaceSource 检索失败: {e}")
            self.last_error = f"{type(e).__name__}: {e}"[:200]
            return []
