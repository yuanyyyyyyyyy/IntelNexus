"""
博查（Bocha）Web Search API 后端
================================
- 端点：``POST https://api.bocha.cn/v1/web-search``
  （第三方文档另写 ``api.bochaai.com``；2026-09-15 实测两个域名均返回
  ``401 {"code":"401","message":"Invalid API KEY"}``，此处按官方文档取 ``.cn``）
- 鉴权：``Authorization: Bearer <API KEY>`` + ``Content-Type: application/json``
- 站内限定：``include`` 参数（多域名用 ``|`` 或 ``,`` 分隔）
- **国内可直连**：``USE_PROXY = False``，不经项目代理（这是相对另两家的决定性优势）

⚠️ 未证实项（务必按此理解）：官方飞书文档本次抓取在 ``freshness`` 参数处截断，
``include`` / ``count`` / ``summary`` 与**错误码语义**均来自**第三方文档**（2025-07），
未经官方确认。因此设计上做了三层防御：
1. 站内限定字段名做成模块级常量 ``SITE_INCLUDE_PARAM``，异常时只需一处调整；
2. 正确性由 ``SiteScopedSource`` 的主机白名单**后置过滤**兜底 —— 即使 ``include``
   被忽略，也不会返回站外结果，只是召回下降；
3. 错误文案不写死单一原因（403 只说「余额可能不足或权限受限」，把判定让给响应体
   ``message``），避免误导排障。
"""
import requests

from intelnexus.core.logger import get_logger
from intelnexus.core.search import get_session
from intelnexus.core.search.sitesearch.base import (
    SiteSearchBackend, SiteSearchError, redact_secrets,
)

logger = get_logger(__name__)

ENDPOINT = "https://api.bocha.cn/v1/web-search"
#: 站内限定参数字段名（第三方文档来源，未获官方证实；如需调整只改这里）
SITE_INCLUDE_PARAM = "include"
#: 单次结果上限：第三方文档称 count 上限 50，这里保守取 20（源默认只请求 10），
#: 避免上限不确定时被 400 拒绝
RESULT_CAP = 20
#: 请求超时（秒）。注意 ``summary=True`` 会显著抬高服务端耗时，弱网下可上调此处
REQUEST_TIMEOUT = 15
#: 是否请求 AI 摘要：为 True 时 description 用 ``summary``（信息量大于 snippet），
#: 代价是响应更慢；如遇稳定超时可将此开关与 REQUEST_TIMEOUT 一并调整
USE_SUMMARY = True


class BochaBackend(SiteSearchBackend):
    """博查 Web Search API 适配器（国内直连）。"""

    name = "Bocha"
    DEFAULT_MIN_INTERVAL = 1.0
    MAX_RESULTS = RESULT_CAP
    # 国内服务：强制直连，不读取代理配置
    USE_PROXY = False

    def __init__(self, api_key: str = "", **kwargs):
        super().__init__(**kwargs)
        self._api_key = api_key or ""

    def is_configured(self) -> bool:
        return bool(self._api_key)

    # ------------------------------------------------------------------
    def _fetch(self, query: str, domain: str, max_results: int) -> list:
        payload = {
            "query": query,
            SITE_INCLUDE_PARAM: domain,
            "count": min(max(1, int(max_results)), RESULT_CAP),
            "summary": USE_SUMMARY,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "User-Agent": "IntelNexus/1.0",
        }
        try:
            session = get_session(self._proxies())
            resp = session.post(ENDPOINT, json=payload, headers=headers,
                                timeout=REQUEST_TIMEOUT)
        except requests.RequestException as e:
            raise SiteSearchError(
                redact_secrets(f"Bocha 网络不可达: {type(e).__name__}: {e}")[:200],
                kind="network")
        except Exception as e:
            raise SiteSearchError(
                redact_secrets(f"Bocha 调用失败: {type(e).__name__}: {e}")[:200],
                kind="error")

        if resp.status_code != 200:
            raise self._map_error(resp)

        try:
            data = resp.json() or {}
        except Exception as e:
            raise SiteSearchError(f"Bocha 响应解析失败: {type(e).__name__}",
                                  kind="error")

        pages = ((data.get("webPages") or {}).get("value")) or []
        out = []
        for item in pages:
            out.append(self._unified(
                title=item.get("name", ""),
                url=item.get("url", ""),
                # summary 为摘要增强，缺失时退回 snippet
                description=item.get("summary") or item.get("snippet") or "",
                source=self.name,
                # datePublished 为标准 ISO（官方建议优先于 dateLastCrawled，
                # 后者标称 UTC 实为 UTC+8）
                published_at=item.get("datePublished", "") or "",
                metadata={"site_name": item.get("siteName", ""),
                          "site_icon": item.get("siteIcon", "")},
            ))
        logger.info(f"Bocha 站内检索 {domain!r} 返回 {len(out)} 条")
        return [r for r in out if r["url"]]

    def _map_error(self, resp) -> SiteSearchError:
        """映射 HTTP 错误（响应体形如 ``{"code","message","log_id"}``）。"""
        message = ""
        try:
            message = (resp.json() or {}).get("message", "") or ""
        except Exception:
            message = ""
        detail = f": {message}" if message else ""

        if resp.status_code == 401:
            return SiteSearchError(f"Bocha 凭证无效（HTTP 401{detail}）", kind="auth")
        if resp.status_code == 403:
            # 不写死单一原因：余额不足与权限/策略拒绝都可能返回 403，
            # 具体以响应体 message 为准
            return SiteSearchError(
                f"Bocha 拒绝请求（403，可能为余额不足或权限受限{detail}）",
                kind="quota")
        if resp.status_code == 429:
            return SiteSearchError(
                f"Bocha 触发请求频率限制（HTTP 429{detail}）", kind="quota")
        return SiteSearchError(
            f"Bocha 请求失败（HTTP {resp.status_code}{detail}）", kind="error")
