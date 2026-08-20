"""
NVD API 搜索源适配器
====================
通过 NVD REST API v2.0 检索 CVE 漏洞信息。
- 无 API key 时限速（约 6s/请求），有 key 时约 0.6s/请求
- 免费、无需注册即可使用
"""
import os
import time
from typing import Dict, List, Optional

from intelnexus.core.logger import get_logger
from intelnexus.core.search.source import BaseSearchSource, CATEGORY_WEB
from intelnexus.core.search import get_session

logger = get_logger(__name__)

CACHE_TTL = 300  # 5分钟缓存


class NVDSearchSource(BaseSearchSource):
    """NVD (National Vulnerability Database) API 适配器。"""

    BASE_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"

    def __init__(self, name: str = "NVD", category: str = CATEGORY_WEB,
                 enabled: bool = True, requires_proxy: bool = False):
        super().__init__(name=name, category=category, enabled=enabled,
                         requires_proxy=requires_proxy)
        self._api_key = os.getenv("NVD_API_KEY", "")
        self._cache = {}
        self._cache_time = {}

    def search(self, query, max_results: int = 20) -> List[Dict]:
        cache_key = f"{query}:{max_results}"
        now = time.time()
        if cache_key in self._cache:
            if (now - self._cache_time.get(cache_key, 0)) < CACHE_TTL:
                return self._cache[cache_key]

        try:
            proxies = self.get_proxies()
            headers = {}
            if self._api_key:
                headers["apiKey"] = self._api_key

            params = {
                "keywordSearch": query,
                "resultsPerPage": min(max_results, 40),
            }
            session = get_session(proxies)
            resp = session.get(
                self.BASE_URL, params=params, headers=headers or None,
                timeout=15
            )
            resp.raise_for_status()
            data = resp.json()
            results = self._parse_cves(data.get("vulnerabilities", []))

            self._cache[cache_key] = results
            self._cache_time[cache_key] = now

            return results
        except Exception as e:
            logger.warning(f"NVDSearchSource 检索失败: {e}")
            return []

    def _parse_cves(self, cves: list) -> List[Dict]:
        results = []
        for item in cves:
            cve = item.get("cve", {})
            cve_id = cve.get("id", "")
            if not cve_id:
                continue

            # 取英文描述
            descriptions = cve.get("descriptions", [])
            desc = ""
            for d in descriptions:
                if d.get("lang") == "en":
                    desc = d.get("value", "")
                    break

            # CVSS v3.1 评分
            metrics = cve.get("metrics", {})
            cvss_score = ""
            if "cvssMetricV31" in metrics:
                cvss_score = str(metrics["cvssMetricV31"][0].get("cvssData", {}).get("baseScore", ""))
            elif "cvssMetricV30" in metrics:
                cvss_score = str(metrics["cvssMetricV30"][0].get("cvssData", {}).get("baseScore", ""))

            title = f"{cve_id}"
            if cvss_score:
                title += f" (CVSS {cvss_score})"

            description = desc[:300]
            if cvss_score:
                description += f" [CVSS: {cvss_score}]"

            # 提取受影响产品
            affected_products = []
            for config in cve.get("configurations", []):
                for node in config.get("nodes", []):
                    for match in node.get("cpeMatch", []):
                        product = match.get("criteria", "")
                        if product:
                            affected_products.append(product.split(":")[4] if ":" in product else product)

            # 提取漏洞类型
            vuln_types = []
            for weakness in cve.get("weaknesses", []):
                for desc in weakness.get("description", []):
                    if desc.get("lang") == "en":
                        vuln_types.append(desc.get("value", ""))

            results.append({
                "title": title,
                "url": f"https://nvd.nist.gov/vuln/detail/{cve_id}",
                "description": description,
                "source": "NVD",
                "category": self.category,
                "published_at": cve.get("published", ""),
                "metadata": {
                    "cve_id": cve_id,
                    "cvss_score": cvss_score,
                    "affected_products": affected_products[:5],
                    "vuln_types": vuln_types,
                },
            })
        return results
