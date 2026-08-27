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
from intelnexus.core.search.source import BaseSearchSource, CATEGORY_THREAT_INTEL
from intelnexus.core.search import get_session, get_http_proxies

logger = get_logger(__name__)

CACHE_TTL = 300  # 5分钟缓存


class NVDSearchSource(BaseSearchSource):
    """NVD (National Vulnerability Database) API 适配器。"""

    BASE_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"
    #: NVD 官方限速：无 key 约 5~6s/请求，有 key 约 0.6s/请求（留余量）
    NO_KEY_MIN_INTERVAL = 6.0
    WITH_KEY_MIN_INTERVAL = 0.7

    def __init__(self, name: str = "NVD", category: str = CATEGORY_THREAT_INTEL,
                 enabled: bool = True, requires_proxy: bool = False):
        super().__init__(name=name, category=category, enabled=enabled,
                         requires_proxy=requires_proxy)
        self._api_key = os.getenv("NVD_API_KEY", "")
        self._cache = {}
        self._cache_time = {}
        self._last_request_ts = 0.0

    def _throttle(self):
        """实例级限速：按是否持有 API key 强制最小请求间隔，避免 403/429。"""
        interval = self.NO_KEY_MIN_INTERVAL if not self._api_key \
            else self.WITH_KEY_MIN_INTERVAL
        elapsed = time.time() - self._last_request_ts
        if self._last_request_ts > 0 and elapsed < interval:
            time.sleep(interval - elapsed)
        self._last_request_ts = time.time()

    def search(self, query, max_results: int = 20) -> List[Dict]:
        cache_key = f"{query}:{max_results}"
        now = time.time()
        if cache_key in self._cache:
            if (now - self._cache_time.get(cache_key, 0)) < CACHE_TTL:
                return self._cache[cache_key]

        try:
            proxies = get_http_proxies()
            headers = {}
            if self._api_key:
                headers["apiKey"] = self._api_key

            params = {
                "keywordSearch": query,
                "resultsPerPage": min(max_results, 40),
            }
            self._throttle()
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
            self.last_error = f"{type(e).__name__}: {e}"[:200]
            return []

    def search_recent_critical(self, days: int = 7, max_results: int = 20) -> List[Dict]:
        """按时间窗 + 严重度拉取近期高危 CVE（用于漏洞预警表）。

        使用 NVD 2.0 的 pubStartDate/pubEndDate + cvssV3Severity 过滤，
        避免 keywordSearch="CVE" 这类无意义查询。无 API key 时 NVD 限速
        约 6s/请求，本方法内部做必要限速等待。
        """
        cache_key = f"recent_critical:{days}:{max_results}"
        now = time.time()
        if cache_key in self._cache:
            if (now - self._cache_time.get(cache_key, 0)) < CACHE_TTL:
                return self._cache[cache_key]

        try:
            from datetime import datetime, timedelta, timezone
            proxies = get_http_proxies()
            headers = {}
            if self._api_key:
                headers["apiKey"] = self._api_key

            end = datetime.now(timezone.utc)
            start = end - timedelta(days=days)
            fmt = "%Y-%m-%dT%H:%M:%S.000Z"
            params = {
                "pubStartDate": start.strftime(fmt),
                "pubEndDate": end.strftime(fmt),
                "cvssV3Severity": "CRITICAL",
                "resultsPerPage": min(max_results, 40),
                "startIndex": 0,
            }
            session = get_session(proxies)
            # 无 key 时 NVD 限速 ~6s/请求，等待以避免 403/429
            if not self._api_key:
                time.sleep(6)
            resp = session.get(
                self.BASE_URL, params=params, headers=headers or None,
                timeout=20
            )
            resp.raise_for_status()
            data = resp.json()
            results = self._parse_cves(data.get("vulnerabilities", []))

            self._cache[cache_key] = results
            self._cache_time[cache_key] = now
            return results
        except Exception as e:
            logger.warning(f"NVD 近期高危 CVE 拉取失败: {e}")
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
