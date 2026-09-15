"""
通用站内定向检索源
==================
把「某站点的站内检索」抽象为可复用的搜索源：传入展示名、目标域名与主机
白名单，即可复用站内检索后端（博查 / Brave / Google CSE，见
``intelnexus.core.search.sitesearch``）。小红书是第一个使用者，
微博 / 知乎 / CSDN 等可直接复用本类（或再叠一个薄子类）。

职责边界：
- 取数交给 ``SiteSearchBackend``（可替换、可挂载外部自备实现）；
- 本源负责「主机白名单收口」与 ``last_error`` 语义。

``last_error`` 语义（与 ``registry._timed_search`` 的单轮生命周期约定自洽）：
- 未配置后端 / 额度耗尽 / 网络不可达 / 其它异常 → 非空，供健康统计与 UI 观测；
- 正常无结果、结果全被白名单滤除、成功命中 → None。

已知取舍：「未配置后端」会经健康统计记为失败，连续 6 次后该源转 ``down`` 并被
暂停投递（健康面板仍保留失败原因）。这是刻意选择——避免长期无谓重试，同时前几
次检索都会给出明确提示，不静默。错误文案统一经 ``redact_secrets`` 脱敏。

注：多子查询（``|`` 分隔）不再由本源拆分——查询原样交给后端，避免为每条
子查询额外消耗后端额度（博查为充值制，Brave / Google CSE 亦有严格额度）。
"""
from typing import Callable, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from intelnexus.core.logger import get_logger
from intelnexus.core.search.source import BaseSearchSource, CATEGORY_CUSTOM
from intelnexus.core.search.sitesearch.base import SiteSearchError, redact_secrets

logger = get_logger(__name__)


def _default_backend_factory():
    """默认后端工厂：按当前配置解析站内检索后端（未配置返回 None）。"""
    from intelnexus.core.search.sitesearch import get_site_search_backend
    return get_site_search_backend()


class SiteScopedSource(BaseSearchSource):
    """通用站内定向检索源。

    Args:
        name: 源显示名（registry 内唯一标识）。
        domains: 传给后端的站内限定域名（取第一个；通常仅一个）。
        allowed_hosts: 结果主机白名单（主机相等或以 ``.<域名>`` 结尾才保留）。
        category: 源类别，默认 ``custom``。
        display_source: 非空时覆盖结果 ``source`` 字段（用于把来源归因给
            站点本身而非检索后端）。
        enabled / requires_proxy: 同基类。
        max_results: 默认结果上限。
        backend: 直接注入的后端实例（测试/定制用；优先于工厂）。
        backend_factory: 后端工厂（默认取 sitesearch 工厂）。
    """

    def __init__(self, name: str, domains: Tuple[str, ...],
                 allowed_hosts: Tuple[str, ...],
                 category: str = CATEGORY_CUSTOM,
                 display_source: str = "",
                 enabled: bool = True, requires_proxy: bool = False,
                 max_results: int = 10,
                 backend=None,
                 backend_factory: Optional[Callable] = None):
        super().__init__(name=name, category=category, enabled=enabled,
                         requires_proxy=requires_proxy)
        self.domains = tuple(d for d in (domains or ()) if d)
        self.allowed_hosts = tuple(h.lower() for h in (allowed_hosts or ()) if h)
        self.display_source = display_source or ""
        self.max_results = int(max_results)
        self._backend = backend
        self._backend_factory = backend_factory or _default_backend_factory

    # ------------------------------------------------------------------
    def _resolve_backend(self):
        """解析后端。

        Returns:
            (backend, resolve_error)：正常返回 (实例, None)；未注入且工厂返回
            None（＝未配置）返回 (None, None)；工厂**抛错**返回 (None, 错误文案)，
            以便调用方把「配置读取故障」与「没填 Key」区分开。
        """
        if self._backend is not None:
            return self._backend, None
        try:
            return self._backend_factory(), None
        except Exception as e:
            logger.warning(f"{self.name} 站内检索后端解析失败: {e}")
            return None, redact_secrets(
                f"站内检索后端解析失败: {type(e).__name__}: {e}")

    def search(self, query, max_results: int = None) -> List[Dict]:
        q = str(query or "").strip()
        if not q or not self.domains:
            # 空查询/未配置域名：不发起检索，也不记为失败
            self.last_error = None
            return []

        backend, resolve_err = self._resolve_backend()
        if backend is None:
            if resolve_err:
                # 配置读取/构造故障 ≠「没填 Key」：文案必须可区分，否则误导排障
                self.last_error = resolve_err[:200]
            else:
                self.last_error = ("未配置站内检索后端（博查 / Brave / Google CSE），"
                                   "请在「搜索服务设置」填写 Key")[:200]
                logger.info(f"{self.name} 未配置站内检索后端，已跳过")
            return []

        limit = int(max_results or self.max_results)
        try:
            raw = backend.search(q, self.domains[0], limit)
        except SiteSearchError as e:
            # 未配置 / 额度耗尽 / 网络不可达等：保留 kind 便于区分与观测；
            # 统一 redact 防底部异常消息带出凭证
            self.last_error = redact_secrets(f"{e.kind}: {e}")[:200]
            logger.info(f"{self.name} 站内检索失败({e.kind}): {e}")
            return []
        except Exception as e:
            self.last_error = redact_secrets(f"{type(e).__name__}: {e}")[:200]
            logger.warning(f"{self.name} 站内检索异常: {e}")
            return []

        kept = [r for r in (raw or [])
                if isinstance(r, dict)
                and self.host_allowed(r.get("url") or r.get("link") or "",
                                      self.allowed_hosts)]

        # 成功路径（有结果，或结果均被白名单正常滤除）：清空失败信号
        self.last_error = None
        results = self.normalize_results(kept)[:limit]
        if self.display_source:
            for r in results:
                r["source"] = self.display_source
        return results

    # ------------------------------------------------------------------
    @staticmethod
    def host_allowed(url: str, allowed_hosts) -> bool:
        """主机是否属白名单。

        用「相等或以 ``.<域名>`` 结尾」判定，防止 ``x.com.evil.com``、
        ``x.com@evil.com``（userinfo 被 urlparse 剥离）等伪装绕过。
        """
        try:
            host = (urlparse(url or "").hostname or "").lower()
        except Exception:
            return False
        return any(host == h or host.endswith("." + h) for h in allowed_hosts)
