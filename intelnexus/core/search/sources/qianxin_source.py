"""
奇安信威胁情报中心搜索源适配器
==============================
通过奇安信威胁情报中心获取威胁情报。
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


class QianxinSource(BaseSearchSource):
    """奇安信威胁情报中心适配器。"""

    BASE_URL = "https://ti.qianxin.com"

    def __init__(self, name: str = "Qianxin", category: str = CATEGORY_THREAT_INTEL,
                 enabled: bool = True, requires_proxy: bool = False):
        super().__init__(name=name, category=category, enabled=enabled,
                         requires_proxy=requires_proxy)

    def search(self, query, max_results: int = 20) -> List[Dict]:
        try:
            proxies = self.get_proxies()
            session = get_session(proxies)

            # 奇安信威胁情报搜索
            url = f"{self.BASE_URL}/intelligence"
            params = {"q": query}
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

            resp = session.get(url, params=params, headers=headers, timeout=15)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")
            results = []

            # 解析威胁情报列表（带fallback选择器）
            items = (
                soup.select("div.intel-item") or
                soup.select("tr.table-row") or
                soup.select("div.threat-item") or
                soup.select("div.card")
            )
            for item in items[:max_results]:
                title_elem = (
                    item.select_one("a.title") or
                    item.select_one("td.name a") or
                    item.select_one("h4 a") or
                    item.select_one("a.card-title")
                )
                if not title_elem:
                    continue

                title = title_elem.get_text(strip=True)
                link = title_elem.get("href", "")
                if link and not link.startswith("http"):
                    link = f"{self.BASE_URL}{link}"

                desc_elem = (
                    item.select_one("div.desc") or
                    item.select_one("td.desc") or
                    item.select_one("p.description") or
                    item.select_one("div.content")
                )
                description = desc_elem.get_text(strip=True)[:300] if desc_elem else ""

                # 提取威胁类型
                type_elem = (
                    item.select_one("span.type") or
                    item.select_one("td.type") or
                    item.select_one("span.category")
                )
                threat_type = type_elem.get_text(strip=True) if type_elem else ""

                results.append({
                    "title": title,
                    "url": link,
                    "description": description,
                    "source": "Qianxin",
                    "category": self.category,
                    "published_at": "",
                    "metadata": {
                        "threat_type": threat_type,
                    },
                })

            return results
        except Exception as e:
            logger.warning(f"QianxinSource 检索失败: {e}")
            return []
