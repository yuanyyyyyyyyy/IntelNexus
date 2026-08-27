"""
AlienVault OTX 搜索源适配器
============================
通过 OTX (Open Threat Exchange) API 检索威胁情报。
- 公开 API，无需认证（限速 10k/月）
- 按 indicator/pulse 关键词搜索
"""
from typing import Dict, List

from intelnexus.core.logger import get_logger
from intelnexus.core.search.source import BaseSearchSource, CATEGORY_THREAT_INTEL
from intelnexus.core.search import get_session

logger = get_logger(__name__)


class AlienVaultOTXSource(BaseSearchSource):
    """AlienVault OTX (Open Threat Exchange) 适配器。"""

    BASE_URL = "https://otx.alienvault.com/api/v1/pulses/search"

    def __init__(self, name: str = "AlienVault_OTX", category: str = CATEGORY_THREAT_INTEL,
                 enabled: bool = True, requires_proxy: bool = False):
        super().__init__(name=name, category=category, enabled=enabled,
                         requires_proxy=requires_proxy)

    def search(self, query, max_results: int = 20) -> List[Dict]:
        try:
            proxies = self.get_proxies()
            params = {"q": query, "limit": min(max_results, 50)}
            session = get_session(proxies)
            resp = session.get(
                self.BASE_URL, params=params, timeout=15
            )
            resp.raise_for_status()
            data = resp.json()
            return self._parse_results(data.get("results", []))
        except Exception as e:
            logger.warning(f"AlienVaultOTXSource 检索失败: {e}")
            self.last_error = f"{type(e).__name__}: {e}"[:200]
            return []

    def _parse_results(self, pulses: list) -> List[Dict]:
        results = []
        for item in pulses:
            name = item.get("name", "")
            desc = item.get("description", "")
            tags = item.get("tags", [])
            pulse_id = item.get("id", "")
            if not name and not pulse_id:
                continue

            title = name or f"Pulse {pulse_id}"
            link = f"https://otx.alienvault.com/pulse/{pulse_id}" if pulse_id else ""

            results.append({
                "title": title,
                "url": link,
                "description": desc[:300] if desc else f"OTX pulse: {title}",
                "source": "AlienVault_OTX",
                "category": self.category,
                "published_at": item.get("created", ""),
                "metadata": {
                    "tags": tags[:5],
                    "pulse_id": pulse_id,
                },
            })
        return results
