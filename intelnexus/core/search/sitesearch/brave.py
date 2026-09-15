"""
Brave Web Search API 后端
=========================
- 端点：``GET https://api.search.brave.com/res/v1/web/search``
- 头：``X-Subscription-Token: <api_key>``、``Accept: application/json``
- 站内限定：``q`` 内使用 ``site:<domain>`` 算子（Brave 原生支持）
- 额度/计费：**以官网为准**。据第三方资料（2026-02）免费层已取消、改为按量计费且
  可能需绑定信用卡；本实现只依赖「超速返回 HTTP 429」这一行为，不假定具体额度。

凭证走请求头（不进入 URL），但异常消息仍统一做 ``redact_secrets`` 脱敏。
"""
import requests

from intelnexus.core.logger import get_logger
from intelnexus.core.search import get_session
from intelnexus.core.search.sitesearch.base import (
    SiteSearchBackend, SiteSearchError, redact_secrets,
)

logger = get_logger(__name__)

ENDPOINT = "https://api.search.brave.com/res/v1/web/search"
#: 单次请求上限（Brave 的 count 最大为 20）
MAX_COUNT = 20


class BraveBackend(SiteSearchBackend):
    """Brave Web Search API 适配器。"""

    name = "Brave"
    # Brave 免费档限制 1 请求/秒
    DEFAULT_MIN_INTERVAL = 1.0
    MAX_RESULTS = MAX_COUNT

    def __init__(self, api_key: str = "", **kwargs):
        super().__init__(**kwargs)
        self._api_key = api_key or ""

    def is_configured(self) -> bool:
        return bool(self._api_key)

    # ------------------------------------------------------------------
    def _fetch(self, query: str, domain: str, max_results: int) -> list:
        params = {
            "q": f"{query} site:{domain}",
            "count": min(max(1, int(max_results)), MAX_COUNT),
        }
        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self._api_key,
            "User-Agent": "IntelNexus/1.0",
        }
        try:
            session = get_session(self._proxies())
            resp = session.get(ENDPOINT, params=params, headers=headers, timeout=15)
        except requests.RequestException as e:
            raise SiteSearchError(
                redact_secrets(f"Brave 网络不可达: {type(e).__name__}: {e}")[:200],
                kind="network")
        except Exception as e:
            raise SiteSearchError(
                redact_secrets(f"Brave 调用失败: {type(e).__name__}: {e}")[:200],
                kind="error")

        if resp.status_code != 200:
            raise self._map_error(resp)

        try:
            data = resp.json() or {}
        except Exception as e:
            raise SiteSearchError(f"Brave 响应解析失败: {type(e).__name__}",
                                  kind="error")

        results = ((data.get("web") or {}).get("results")) or []
        out = []
        for item in results:
            out.append(self._unified(
                title=item.get("title", ""),
                url=item.get("url", ""),
                description=item.get("description", ""),
                source=self.name,
                # Brave 的 age 是 "2 days ago" 这类相对文本，无法被时效评分
                # （registry._recency_rank）解析，写入 published_at 会污染排序与
                # 展示，故仅存 metadata。
                published_at="",
                metadata={"age": item.get("age", "") or "",
                          "profile": item.get("profile", "")},
            ))
        logger.info(f"Brave 站内检索 {domain!r} 返回 {len(out)} 条")
        return [r for r in out if r["url"]]

    def _map_error(self, resp) -> SiteSearchError:
        if resp.status_code == 429:
            return SiteSearchError(
                "Brave 触发速率限制（HTTP 429）；免费档约 2000 次/月、1 请求/秒",
                kind="quota")
        if resp.status_code in (401, 403):
            return SiteSearchError(
                f"Brave 凭证无效或无权限（HTTP {resp.status_code}）", kind="auth")
        return SiteSearchError(f"Brave 请求失败（HTTP {resp.status_code}）",
                               kind="error")
