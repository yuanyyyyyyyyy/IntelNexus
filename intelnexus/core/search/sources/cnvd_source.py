"""
CNVD (国家信息安全漏洞共享平台) 搜索源适配器
============================================
通过 CNVD 公开页面获取漏洞信息。

现场结论（2026-09-15 实测）：
- 官方域名为 https://www.cnvd.org.cn；曾误写为 cvd.org.cn（DNS 通但连接被 RST）。
- 站点当前由加速乐（Jiasule）保护：纯 HTTP 请求返回 HTTP 521 与
  __jsl_clearance JS 校验脚本。本源**不绕过**该反爬机制（不做 cookie 求解），
  命中校验时直接标记失败并返回空，交由注册表健康降级处理。
"""
from typing import Dict, List

from bs4 import BeautifulSoup

from intelnexus.core.logger import get_logger
from intelnexus.core.search.source import BaseSearchSource, CATEGORY_THREAT_INTEL
from intelnexus.core.search import get_session

logger = get_logger(__name__)


class CNVDSource(BaseSearchSource):
    """国家信息安全漏洞共享平台适配器。"""

    #: 官方域名（注意是 cnvd 而非 cvd）
    BASE_URL = "https://www.cnvd.org.cn"
    #: 漏洞列表/搜索接口路径
    SEARCH_PATH = "/flaw/list"
    #: 加速乐反爬校验特征
    ANTIBOT_STATUS = 521
    ANTIBOT_MARKER = "__jsl_clearance"

    def __init__(self, name: str = "CNVD", category: str = CATEGORY_THREAT_INTEL,
                 enabled: bool = True, requires_proxy: bool = False):
        # requires_proxy=False：CNVD 是国内源可直连，默认走代理反而会被
        # 「未配置代理→跳过」逻辑排除（与文件头注释"国内可直连"一致）
        super().__init__(name=name, category=category, enabled=enabled,
                         requires_proxy=requires_proxy)

    def search(self, query, max_results: int = 20) -> List[Dict]:
        try:
            # 国内站点：requires_proxy=False → self.get_proxies() 恒为 None（强制直连），
            # 与 ExploitDB 走 get_http_proxies()（国际站点有代理则走）的差异是有意为之。
            proxies = self.get_proxies()
            session = get_session(proxies)

            # CNVD 漏洞列表搜索接口：flag=true 走关键字检索
            url = f"{self.BASE_URL}{self.SEARCH_PATH}"
            params = {"flag": "true", "q": query}
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

            resp = session.get(url, params=params, headers=headers, timeout=15)

            # 反爬 JS 校验：不绕过（不求解 __jsl_clearance），标记失败后降级返回空
            if resp.status_code == self.ANTIBOT_STATUS or \
                    self.ANTIBOT_MARKER in (resp.text or "")[:1000]:
                self.last_error = (
                    f"CNVD 站点启用反爬 JS 校验（HTTP {resp.status_code}），"
                    f"纯 HTTP 无法抓取"
                )[:200]
                logger.info(f"CNVDSource 命中反爬校验，已跳过: HTTP {resp.status_code}")
                return []

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
            self.last_error = f"{type(e).__name__}: {e}"[:200]
            return []
