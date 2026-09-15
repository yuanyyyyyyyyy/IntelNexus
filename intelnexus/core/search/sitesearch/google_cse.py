"""
Google Custom Search JSON API 后端
==================================
- 端点：``GET https://www.googleapis.com/customsearch/v1``
- 站内限定：``siteSearch=<domain>`` + ``siteSearchFilter=i``（include）
  —— 用 API 原生参数做站内限定，而非在 ``q`` 里拼 ``site:``，
  因为实测公共网页引擎（cn.bing.com / baidu / DDG）会忽略 ``site:`` 算子。
- 凭证：API Key + 可编程搜索引擎 ID（``cx``），二者缺一不可。
- 免费额度：100 次查询/天（超限 HTTP 403 ``dailyLimitExceeded``）。

安全提示：API Key 以 **query 参数** 传递，因此 ``requests`` 的连接类异常消息
会带上含 ``key=``/``cx=`` 的完整 URL —— 本源对这些消息统一做 ``redact_secrets``
脱敏，避免凭证经 ``last_error`` 落盘到 ``source_health.json`` 或打进日志。
"""
import requests

from intelnexus.core.logger import get_logger
from intelnexus.core.search import get_session
from intelnexus.core.search.sitesearch.base import (
    SiteSearchBackend, SiteSearchError, redact_secrets,
)

logger = get_logger(__name__)

ENDPOINT = "https://www.googleapis.com/customsearch/v1"
#: 单次请求上限（Google CSE 的 num 最大为 10）
MAX_NUM = 10
#: 日额度/速率相关的 error reason
_QUOTA_REASONS = {"dailyLimitExceeded", "rateLimitExceeded", "quotaExceeded",
                  "userRateLimitExceeded"}
#: 凭证相关的 error reason（仅 keyInvalid 属真正的凭证问题）
_AUTH_REASONS = {"keyInvalid"}
#: 配置缺失（本项目未启用 Custom Search JSON API），与凭证无效不是一回事
_CONFIG_REASONS = {"accessNotConfigured"}


class GoogleCSEBackend(SiteSearchBackend):
    """Google Custom Search JSON API 适配器。"""

    name = "GoogleCSE"
    # CSE 日额度极紧（100 次/天），节流放宽到 1s 并依赖 TTL 缓存
    DEFAULT_MIN_INTERVAL = 1.0
    MAX_RESULTS = MAX_NUM

    def __init__(self, api_key: str = "", cse_id: str = "", **kwargs):
        super().__init__(**kwargs)
        self._api_key = api_key or ""
        self._cse_id = cse_id or ""

    def is_configured(self) -> bool:
        return bool(self._api_key and self._cse_id)

    # ------------------------------------------------------------------
    def _fetch(self, query: str, domain: str, max_results: int) -> list:
        params = {
            "key": self._api_key,
            "cx": self._cse_id,
            "q": query,
            "num": min(max(1, int(max_results)), MAX_NUM),
            "siteSearch": domain,
            "siteSearchFilter": "i",
        }
        try:
            session = get_session(self._proxies())
            resp = session.get(ENDPOINT, params=params, timeout=15,
                               headers={"User-Agent": "IntelNexus/1.0"})
        except requests.RequestException as e:
            # Key 在 query 中 → 异常消息含完整 URL，必须先脱敏再上抛
            raise SiteSearchError(
                redact_secrets(
                    f"GoogleCSE 网络不可达: {type(e).__name__}: {e}")[:200],
                kind="network")
        except Exception as e:  # 防御：session 构造等非 requests 异常
            raise SiteSearchError(
                redact_secrets(
                    f"GoogleCSE 调用失败: {type(e).__name__}: {e}")[:200],
                kind="error")

        if resp.status_code != 200:
            raise self._map_error(resp)

        try:
            data = resp.json() or {}
        except Exception as e:
            raise SiteSearchError(f"GoogleCSE 响应解析失败: {type(e).__name__}",
                                  kind="error")

        out = []
        for item in data.get("items") or []:
            out.append(self._unified(
                title=item.get("title", ""),
                url=item.get("link", ""),
                description=item.get("snippet", ""),
                source=self.name,
                metadata={"display_link": item.get("displayLink", "")},
            ))
        logger.info(f"GoogleCSE 站内检索 {domain!r} 返回 {len(out)} 条")
        return [r for r in out if r["url"]]

    def _map_error(self, resp) -> SiteSearchError:
        """把 HTTP 错误映射为带 kind 的可读错误。

        顺序很关键：额度 → 凭证 reason → 配置 reason → 401/403 兜底。
        ``badRequest`` 属通用参数错误，不归为凭证问题（避免误导用户去换 Key）。
        """
        reason = ""
        try:
            errors = ((resp.json() or {}).get("error") or {}).get("errors") or []
            if errors:
                reason = (errors[0] or {}).get("reason", "") or ""
        except Exception:
            reason = ""
        detail = f": {reason}" if reason else ""

        if resp.status_code == 429 or reason in _QUOTA_REASONS:
            return SiteSearchError(
                f"GoogleCSE 额度耗尽或超速（HTTP {resp.status_code}{detail}）；"
                f"免费额度 100 次/天", kind="quota")
        if reason in _AUTH_REASONS:
            return SiteSearchError(
                f"GoogleCSE 凭证无效（HTTP {resp.status_code}{detail}）", kind="auth")
        if reason in _CONFIG_REASONS:
            return SiteSearchError(
                f"GoogleCSE 未启用 Custom Search JSON API 或无权限"
                f"（HTTP {resp.status_code}{detail}）", kind="config")
        if resp.status_code in (401, 403):
            return SiteSearchError(
                f"GoogleCSE 无权限（HTTP {resp.status_code}{detail}）", kind="auth")
        return SiteSearchError(
            f"GoogleCSE 请求失败（HTTP {resp.status_code}{detail}）", kind="error")
