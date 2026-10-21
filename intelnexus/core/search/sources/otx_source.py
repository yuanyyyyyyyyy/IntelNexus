"""
AlienVault OTX 搜索源适配器
============================
通过 OTX (Open Threat Exchange) API 检索威胁情报。
- 按 pulse 关键词搜索；配额约 10k pulses/月
- 需要 X-OTX-API-KEY（otx.alienvault.com 免费注册）；未配置 OTX_API_KEY 时
  优雅跳过并给出可操作提示，不再盲打接口

R18（2026-10-21）：修复 API 路径错误——原 BASE_URL /api/v1/pulses/search
是不存在的路由（实测恒 404），正确路径为 /api/v1/search/pulses（实测无 key
返回 {"detail": "Authentication required"}）；同时补 API key 支持与未配
key 的可读跳过信息（原注释「无需认证」已过时）。
"""
import os
from typing import Dict, List

from intelnexus.core.logger import get_logger
from intelnexus.core.search.source import BaseSearchSource, CATEGORY_THREAT_INTEL
from intelnexus.core.search import get_session

logger = get_logger(__name__)


class AlienVaultOTXSource(BaseSearchSource):
    """AlienVault OTX (Open Threat Exchange) 适配器。"""

    BASE_URL = "https://otx.alienvault.com/api/v1/search/pulses"

    def __init__(self, name: str = "AlienVault_OTX", category: str = CATEGORY_THREAT_INTEL,
                 enabled: bool = True, requires_proxy: bool = False):
        super().__init__(name=name, category=category, enabled=enabled,
                         requires_proxy=requires_proxy)

    def search(self, query, max_results: int = 20) -> List[Dict]:
        try:
            # key 在调用时读取（此时 .env 已由 config 完成加载），便于测试注入
            api_key = os.getenv("OTX_API_KEY", "").strip()
            if not api_key:
                self.last_error = (
                    "OTX 需要免费 API key：otx.alienvault.com 注册后写入 .env "
                    "OTX_API_KEY=<key> 并重启（当前未配置，已跳过该源）"
                )
                logger.warning(f"AlienVaultOTXSource 跳过: {self.last_error}")
                return []
            proxies = self.get_proxies()
            params = {"q": query, "limit": min(max_results, 50)}
            session = get_session(proxies)
            resp = session.get(
                self.BASE_URL, params=params, timeout=15,
                headers={"X-OTX-API-KEY": api_key},
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
