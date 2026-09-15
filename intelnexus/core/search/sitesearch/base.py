"""
站内定向检索后端抽象
====================
把「域名 + 查询」的站内限定检索抽象为一等能力：输入目标域名与关键词，
输出平台统一字段结果。小红书是第一个使用者，微博 / 知乎 / CSDN 等可直接复用。

设计要点：
- 只负责取数，不关心业务侧域名白名单（白名单由 ``SiteScopedSource`` 收口）。
- 公共实现 TTL 缓存与最小请求间隔节流，保护各家的严格额度（博查为充值制、
  Brave 与 Google CSE 亦有额度/速率限制；具体额度以各家官网为准）。
- 失败统一抛 ``SiteSearchError``（带 ``kind``）：调用方据此写入 ``last_error``，
  可区分「未配置 / 凭证无效 / 配置缺失 / 额度耗尽或超速 / 网络不可达 / 其它」。
- 缓存键按「有效请求规模」归一（``min(limit, MAX_RESULTS)``），避免同一查询
  因调用方 limit 不同而重复消耗日额度。

**扩展点**：本类是外部可扩展接口。用户自备的采集 Provider（含需登录态的
实现）只需继承本类并注册到 ``sitesearch`` 工厂，即可被 ``SiteScopedSource``
复用，核心系统无需改动。
"""
import re
import threading
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple

from intelnexus.core.search.source import CATEGORY_CUSTOM

#: 需脱敏的参数名（出现在 URL query 或文本中时，其值一律替换为 ***）
_SENSITIVE_PARAMS = ("key", "cx", "api_key", "apikey", "token", "access_token",
                     "subscription-token")

#: 自检查询词：无业务含义，只用于验证凭证与连通性（不关心命中什么）
PROBE_QUERY = "test"
#: 自检默认域名：未指定时的兜底目标，同样无业务含义
PROBE_DOMAIN = "example.com"


def redact_secrets(text: str) -> str:
    """脱敏敏感参数值。

    典型场景：``requests`` 的连接类异常消息内含带 query string 的完整 URL
    （如 ``.../customsearch/v1?key=AIza...&cx=...``；博查的密钥走请求头，
    其异常消息也经本函数处理作为防御）。若不脱敏，该消息会经 ``last_error``
    落盘到 ``data/source_health.json`` 并打进日志，造成凭证泄露。
    """
    out = text or ""
    for name in _SENSITIVE_PARAMS:
        out = re.sub(rf"([?&\s]{re.escape(name)}=)[^&\s]+", r"\1***",
                     out, flags=re.IGNORECASE)
    return out


class SiteSearchError(Exception):
    """站内检索失败。

    kind 取值：``not_configured`` / ``auth`` / ``config`` / ``quota`` /
    ``network`` / ``error``。
    """

    def __init__(self, message: str, kind: str = "error"):
        super().__init__(message)
        self.kind = kind


class SiteSearchBackend(ABC):
    """站内定向检索后端基类。"""

    #: 后端显示名（用于统一字段的 source 与日志）
    name: str = ""
    #: 结果缓存 TTL（秒）
    DEFAULT_TTL = 300
    #: 最小请求间隔（秒），用于额度保护；0 表示不节流
    DEFAULT_MIN_INTERVAL = 1.0
    #: 单次请求的有效结果上限（子类按各自 API 上限覆盖）
    MAX_RESULTS = 10
    #: 是否经由项目代理访问：海外 API 用 True；**国内 API 应设 False 强制直连**
    USE_PROXY = True

    def __init__(self, ttl: Optional[int] = None,
                 min_interval: Optional[float] = None,
                 clock=None, sleeper=None):
        """
        Args:
            ttl: 结果缓存 TTL（秒），默认 DEFAULT_TTL。
            min_interval: 最小请求间隔（秒），默认 DEFAULT_MIN_INTERVAL。
            clock: 时钟函数（可注入以便测试），默认 time.monotonic。
            sleeper: 休眠函数（可注入以便测试），默认 time.sleep。
        """
        self._ttl = self.DEFAULT_TTL if ttl is None else int(ttl)
        self._min_interval = (self.DEFAULT_MIN_INTERVAL if min_interval is None
                              else float(min_interval))
        self._clock = clock or time.monotonic
        self._sleeper = sleeper or time.sleep
        self._cache: Dict[Tuple, List[Dict]] = {}
        self._cache_time: Dict[Tuple, float] = {}
        # None 表示「尚未发起过请求」——不用 0.0 作哨兵，避免注入时钟初值为 0 时节流失效
        self._last_request_ts: Optional[float] = None
        # 保护缓存与节流状态的读-改-写（并发检索时避免重复请求与缓存竞争）
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # 子类实现
    # ------------------------------------------------------------------
    @abstractmethod
    def is_configured(self) -> bool:
        """凭证是否齐备；工厂只在已配置的 Provider 中择一。"""

    @abstractmethod
    def _fetch(self, query: str, domain: str, max_results: int) -> List[Dict]:
        """实际取数，返回统一字段结果；失败时抛 ``SiteSearchError``。

        ``max_results`` 已由基类收敛到 ``MAX_RESULTS`` 以内。
        """

    # ------------------------------------------------------------------
    # 公共流程（缓存 + 节流 + 未配置显式报错）
    # ------------------------------------------------------------------
    def search(self, query, domain, max_results: int = 10) -> List[Dict]:
        q = str(query or "").strip()
        d = str(domain or "").strip().lower()
        if not q or not d:
            # 空查询/空域名：不发起请求，也不视为失败
            return []
        if not self.is_configured():
            raise SiteSearchError(
                f"{self.name or '站内检索后端'} 未配置凭证，请在「搜索服务设置」填写",
                kind="not_configured")

        limit = max(1, int(max_results or self.MAX_RESULTS))
        effective = min(limit, self.MAX_RESULTS)
        key = (d, q, effective)
        cached = self._get_cached(key)
        if cached is not None:
            return list(cached)

        self._throttle()
        rows = self._fetch(q, d, effective)
        self._set_cached(key, rows)
        return list(rows)

    def probe(self, domain: str = "") -> List[Dict]:
        """最小成本自检：只回答「凭证是否有效、后端是否可达」。

        与 ``search`` 的差异（两者都对，用途不同，勿互相替代）：
        - 固定最小载荷（只要 1 条结果），把额度消耗与耗时压到最低；
        - **绕过缓存**：自检结论必须来自当次真实请求——命中上一次的缓存会把
          「Key 已被吊销 / 余额已耗尽」误报为成功，而那正是自检要发现的问题。

        失败语义与 ``search`` 一致：抛 ``SiteSearchError``（按 kind 分类），
        未配置时抛 ``not_configured``。
        """
        d = str(domain or "").strip().lower() or PROBE_DOMAIN
        if not self.is_configured():
            raise SiteSearchError(
                f"{self.name or '站内检索后端'} 未配置凭证，请在「搜索服务设置」填写",
                kind="not_configured")
        self._throttle()
        return list(self._fetch(PROBE_QUERY, d, 1) or [])

    def clear_cache(self) -> None:
        """清空结果缓存（凭证变更后由工厂失效钩子调用）。"""
        with self._lock:
            self._cache.clear()
            self._cache_time.clear()

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------
    def _get_cached(self, key) -> Optional[List[Dict]]:
        with self._lock:
            if key not in self._cache:
                return None
            if self._clock() - self._cache_time.get(key, 0.0) >= self._ttl:
                self._cache.pop(key, None)
                self._cache_time.pop(key, None)
                return None
            return self._cache[key]

    def _set_cached(self, key, rows: List[Dict]) -> None:
        with self._lock:
            self._cache[key] = list(rows or [])
            self._cache_time[key] = self._clock()

    def _throttle(self) -> None:
        """按最小请求间隔节流，避免触发日额度/速率限制。

        持锁等待：并发调用被串行化，从而真正保证「最小间隔」语义。
        """
        with self._lock:
            now = self._clock()
            if self._last_request_ts is not None:
                elapsed = now - self._last_request_ts
                if elapsed < self._min_interval:
                    self._sleeper(self._min_interval - elapsed)
            self._last_request_ts = self._clock()

    def _proxies(self):
        """返回本源应使用的代理配置（复用统一收口 ``get_http_proxies_for``）。

        ``USE_PROXY=False``（国内 API）时返回 ``None`` 强制直连，且该路径**不会
        读取**代理配置（``get_http_proxies_for`` 提前返回），避免国内源被不可达
        的代理拖垮；``USE_PROXY=True``（海外 API）时走统一代理配置。
        """
        from intelnexus.core.search import get_http_proxies_for
        return get_http_proxies_for(self.USE_PROXY)

    @staticmethod
    def _unified(title: str, url: str, description: str, source: str,
                 published_at: str = "", metadata: Optional[Dict] = None) -> Dict:
        """产出平台统一字段（与 BaseSearchSource 契约一致）。"""
        return {
            "title": (title or "").strip(),
            "url": (url or "").strip(),
            "description": (description or "").strip(),
            "source": source,
            "category": CATEGORY_CUSTOM,
            "published_at": published_at or "",
            "metadata": metadata or {},
        }
