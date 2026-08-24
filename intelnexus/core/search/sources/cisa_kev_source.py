"""
CISA KEV (Known Exploited Vulnerabilities) 搜索源适配器
======================================================
通过 CISA KEV Catalog 公开 JSON 获取已知被利用的漏洞信息。
- 公开 API，无需认证
- 整表缓存（约 1000 条），TTL 1 小时
"""
import os
import re
import time
from typing import Dict, List

import requests

from intelnexus.core.logger import get_logger
from intelnexus.core.search import get_http_proxies
from intelnexus.core.search.source import BaseSearchSource, CATEGORY_THREAT_INTEL

logger = get_logger(__name__)

KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
CACHE_TTL = 3600  # 1 小时


class CISAKEVSource(BaseSearchSource):
    """CISA Known Exploited Vulnerabilities Catalog 适配器。"""

    def __init__(self, name: str = "CISA_KEV", category: str = CATEGORY_THREAT_INTEL,
                 enabled: bool = True, requires_proxy: bool = False):
        super().__init__(name=name, category=category, enabled=enabled,
                         requires_proxy=requires_proxy)
        # 与 intelnexus.config.paths 同一锚点：仓库内 data/cache/（本地计算避免导入环）
        self._cache_path = os.path.abspath(os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "..", "data", "cache", "cisa_kev.json"
        ))
        self._cache = None
        self._cache_time = 0.0

    def search(self, query, max_results: int = 20) -> List[Dict]:
        try:
            vulns = self._load_kev_data()
            if not vulns:
                return []

            results = []
            # 多词 AND 匹配：查询按空白拆 token，每个 token 都须命中。
            # （旧实现整串子串匹配，"Oracle WebLogic" 这类多词查询恒空）
            query_tokens = [t for t in re.split(r"\s+", query.lower()) if t]

            for v in vulns:
                cve_id = v.get("cveID", "")
                vendor = v.get("vendorProject", "")
                product = v.get("product", "")
                desc = v.get("shortDescription", "")

                # 关键词匹配
                searchable = f"{cve_id} {vendor} {product} {desc}".lower()
                if not all(tok in searchable for tok in query_tokens):
                    continue

                due_date = v.get("dueDate", "")
                status = v.get("requiredAction", "")

                title = f"{cve_id} — {vendor} {product}"

                description = desc[:300]
                if due_date:
                    description += f" [修复期限: {due_date}]"
                if status:
                    description += f" [要求: {status[:80]}]"

                results.append({
                    "title": title,
                    "url": f"https://www.cisa.gov/known-exploited-vulnerabilities-catalog?search={cve_id}",
                    "description": description,
                    "source": "CISA_KEV",
                    "category": self.category,
                    "published_at": v.get("dateAdded", ""),
                    "metadata": {
                        "cve_id": cve_id,
                        "vendor": vendor,
                        "product": product,
                        "due_date": due_date,
                        "required_action": status,
                    },
                })

                if len(results) >= max_results:
                    break

            return results
        except Exception as e:
            logger.warning(f"CISAKEVSource 检索失败: {e}")
            return []

    def _load_kev_data(self) -> list:
        """加载 KEV 数据，优先缓存。"""
        now = time.time()

        # 检查内存缓存
        if self._cache is not None and (now - self._cache_time) < CACHE_TTL:
            return self._cache

        # 检查文件缓存
        if os.path.exists(self._cache_path):
            try:
                import json
                with open(self._cache_path, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                cache_time = cached.get("_cache_time", 0)
                if (now - cache_time) < CACHE_TTL:
                    self._cache = cached.get("vulnerabilities", [])
                    self._cache_time = cache_time
                    return self._cache
            except Exception as e:
                logger.warning(f"读取 CISA KEV 缓存失败: {e}")

        # 从远程拉取
        try:
            proxies = get_http_proxies()
            resp = requests.get(KEV_URL, proxies=proxies, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            vulns = data.get("vulnerabilities", [])

            # 写入缓存
            self._save_cache(vulns, now)
            self._cache = vulns
            self._cache_time = now
            return vulns
        except Exception as e:
            logger.warning(f"CISA KEV 远程拉取失败: {e}")
            # 回退到过期文件缓存
            if os.path.exists(self._cache_path):
                try:
                    import json
                    with open(self._cache_path, "r", encoding="utf-8") as f:
                        cached = json.load(f)
                    return cached.get("vulnerabilities", [])
                except Exception:
                    pass
            return []

    def _save_cache(self, vulns: list, cache_time: float):
        try:
            import json
            os.makedirs(os.path.dirname(self._cache_path), exist_ok=True)
            with open(self._cache_path, "w", encoding="utf-8") as f:
                json.dump({"vulnerabilities": vulns, "_cache_time": cache_time}, f,
                          ensure_ascii=False)
        except Exception as e:
            logger.warning(f"保存 CISA KEV 缓存失败: {e}")
