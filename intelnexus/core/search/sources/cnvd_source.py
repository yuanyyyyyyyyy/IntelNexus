"""
CNVD (国家信息安全漏洞共享平台) 搜索源适配器
============================================
通过 CNVD 公开页面获取漏洞信息。
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


class CNVDSource(BaseSearchSource):
    """国家信息安全漏洞共享平台适配器。"""

    BASE_URL = "https://www.cvd.org.cn"

    def __init__(self, name: str = "CNVD", category: str = CATEGORY_THREAT_INTEL,
                 enabled: bool = True, requires_proxy: bool = True):
        super().__init__(name=name, category=category, enabled=enabled,
                         requires_proxy=requires_proxy)

    def search(self, query, max_results: int = 20) -> List[Dict]:
        try:
            proxies = self.get_proxies()
            session = get_session(proxies)

            # CNVD 搜索接口
            url = f"{self.BASE_URL}/faw/list.htm"
            params = {"q": query}
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

            resp = session.get(url, params=params, headers=headers, timeout=15)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")
            results = []

            # 解析漏洞列表（带fallback选择器）
            items = (
                soup.select("ul.list li") or
                soup.select("div.vuln-list li") or
                soup.select("div.list-group-item") or
                soup.select("table.table tbody tr")
            )
            for item in items[:max_results]:
                title_elem = (
                    item.select_one("a") or
                    item.select_one("span.title") or
                    item.select_one("td a")
                )
                if not title_elem:
                    continue

                title = title_elem.get_text(strip=True)
                link = title_elem.get("href", "")
                if link and not link.startswith("http"):
                    link = f"{self.BASE_URL}{link}"

                desc_elem = (
                    item.select_one("span.desc") or
                    item.select_one("p") or
                    item.select_one("td:nth-child(2)")
                )
                description = desc_elem.get_text(strip=True)[:300] if desc_elem else ""

                # 提取 CVE ID
                cve_id = ""
                if "CVE-" in title or "CVE-" in description:
                    import re
                    cve_match = re.search(r"CVE-\d{4}-\d+", title + " " + description)
                    if cve_match:
                        cve_id = cve_match.group()

                results.append({
                    "title": f"{cve_id} - {title}" if cve_id else title,
                    "url": link,
                    "description": description,
                    "source": "CNVD",
                    "category": self.category,
                    "published_at": "",
                    "metadata": {
                        "cve_id": cve_id,
                    },
                })

            return results
        except Exception as e:
            logger.warning(f"CNVDSource 检索失败: {e}")
            return []
