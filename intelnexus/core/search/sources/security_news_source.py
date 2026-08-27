"""
安全内参 (SecRSS) 搜索源适配器
==============================
通过安全内参网站获取安全新闻与漏洞通告。
- 公开数据，无需认证
- 国内可直连
"""
from typing import Dict, List

import requests
from bs4 import BeautifulSoup

from intelnexus.core.logger import get_logger
from intelnexus.core.search.source import BaseSearchSource, CATEGORY_THREAT_INTEL
from intelnexus.core.search import get_session

logger = get_logger(__name__)


class SecurityNewsSource(BaseSearchSource):
    """安全内参适配器。"""

    BASE_URL = "https://www.secrss.com"

    def __init__(self, name: str = "SecRSS", category: str = CATEGORY_THREAT_INTEL,
                 enabled: bool = True, requires_proxy: bool = False):
        super().__init__(name=name, category=category, enabled=enabled,
                         requires_proxy=requires_proxy)

    def search(self, query, max_results: int = 20) -> List[Dict]:
        try:
            proxies = self.get_proxies()
            session = get_session(proxies)

            # 安全内参搜索
            url = f"{self.BASE_URL}/search"
            params = {"q": query}
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

            resp = session.get(url, params=params, headers=headers, timeout=15)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")
            results = []

            # 解析文章列表（带fallback选择器）
            items = (
                soup.select("article") or
                soup.select("div.article-item") or
                soup.select("div.post-item") or
                soup.select("div.news-item")
            )
            for item in items[:max_results]:
                title_elem = (
                    item.select_one("h2 a") or
                    item.select_one("a.title") or
                    item.select_one("h3 a") or
                    item.select_one("a.post-title")
                )
                if not title_elem:
                    continue

                title = title_elem.get_text(strip=True)
                link = title_elem.get("href", "")
                if link and not link.startswith("http"):
                    link = f"{self.BASE_URL}{link}"

                desc_elem = (
                    item.select_one("p.summary") or
                    item.select_one("div.content") or
                    item.select_one("div.post-excerpt") or
                    item.select_one("p")
                )
                description = desc_elem.get_text(strip=True)[:300] if desc_elem else ""

                # 提取标签
                tags = []
                for tag_elem in (
                    item.select("span.tag") or
                    item.select("a.tag") or
                    item.select("span.category")
                ):
                    tags.append(tag_elem.get_text(strip=True))

                results.append({
                    "title": title,
                    "url": link,
                    "description": description,
                    "source": "SecRSS",
                    "category": self.category,
                    "published_at": "",
                    "metadata": {
                        "tags": tags,
                    },
                })

            return results
        except Exception as e:
            logger.warning(f"SecurityNewsSource 检索失败: {e}")
            self.last_error = f"{type(e).__name__}: {e}"[:200]
            return []
