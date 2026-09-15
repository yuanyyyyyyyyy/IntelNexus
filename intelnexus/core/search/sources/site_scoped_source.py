"""
通用站内定向检索源
==================
把「某站点的站内检索」抽象为可复用的搜索源：传入展示名、目标域名与主机
白名单，即可复用站内检索后端（博查 / Brave / Google CSE，见
``intelnexus.core.search.sitesearch``）。小红书是第一个使用者，
微博 / 知乎 / CSDN 等可直接复用本类（或再叠一个薄子类）。

职责边界：
- 取数交给 ``SiteSearchBackend``（可替换、可挂载外部自备实现）；
- 本源负责「主机白名单收口」「去噪」与 ``last_error`` 语义。

去噪分两级，**默认行为并不完全相同**，勿混淆：
- 非目标页面黑名单（``blocked_hosts`` / ``blocked_paths``）：**默认空**，未配置
  即完全不拦截，既有通用源行为不变；
- 相关性过滤：与网页源共用 ``RELEVANCE_THRESHOLD``，**无条件生效**、无开关。
  需要豁免的源请覆写 ``_relevant()``。

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
        blocked_hosts: 站内**非目标页面**的子域黑名单（如小红书的
            ``pgy.xiaohongshu.com`` 商业平台、``ipp.xiaohongshu.com`` 登录页）。
            默认空——既有通用源行为完全不变。
        blocked_paths: 非目标页面路径黑名单（如根路径 ``/``、``/explore`` 索引页）。
            默认空。刻意用黑名单而非路径白名单：白名单会误杀笔记的其它 URL
            形态（``/user/profile/``、``/search_result``、带 ``xsec_token`` 的新版
            链接），黑名单的失败模式只是「漏掉个别垃圾」，可接受。
    """

    #: 零结果＝查询未命中，不是故障：后端正常返回空列表（冷门查询、站内索引稀疏）。
    #: 必须置真——否则连续几次未命中后 consecutive_failures 永不下降，源被永久
    #: 钉在 degraded，攒满阈值转 down 后还会被停止投递、彻底失去自愈路径。
    empty_is_healthy = True

    def __init__(self, name: str, domains: Tuple[str, ...],
                 allowed_hosts: Tuple[str, ...],
                 category: str = CATEGORY_CUSTOM,
                 display_source: str = "",
                 enabled: bool = True, requires_proxy: bool = False,
                 max_results: int = 10,
                 backend=None,
                 backend_factory: Optional[Callable] = None,
                 blocked_hosts: Tuple[str, ...] = (),
                 blocked_paths: Tuple[str, ...] = ()):
        super().__init__(name=name, category=category, enabled=enabled,
                         requires_proxy=requires_proxy)
        self.domains = tuple(d for d in (domains or ()) if d)
        self.allowed_hosts = tuple(h.lower() for h in (allowed_hosts or ()) if h)
        self.display_source = display_source or ""
        self.max_results = int(max_results)
        self._backend = backend
        self._backend_factory = backend_factory or _default_backend_factory
        self.blocked_hosts = tuple(h.strip().lower()
                                   for h in (blocked_hosts or ()) if h)
        # 路径归一：去掉结尾斜杠（根路径归为 "/"），消掉 /explore 与 /explore/ 的差异
        self.blocked_paths = frozenset((p.strip().rstrip("/") or "/")
                                       for p in (blocked_paths or ()) if p)
        #: 最近一次检索的过滤统计。语义同 ``last_error``：成功路径更新，空查询
        #: 与失败路径归零。用于把「后端无返回」与「过滤后无留存」区分开——两者
        #: 排障方向完全不同。
        #: - ``raw``：后端返回的有效条目数；
        #: - ``kept``：**最终返回**条数（已含 ``max_results`` 截断）；
        #: - ``dropped``：``raw - kept``，即未进入最终结果的条目数。
        self.last_filter_stats: Dict[str, int] = {"raw": 0, "kept": 0,
                                                  "dropped": 0}

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
            # 空查询/未配置域名：不发起检索，也不记为失败（统计一并归零，
            # 避免残留上一轮数字被 UI 误读）
            self.last_error = None
            self._reset_filter_stats()
            return []

        backend, resolve_err = self._resolve_backend()
        if backend is None:
            self._reset_filter_stats()
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
            self._reset_filter_stats()
            logger.info(f"{self.name} 站内检索失败({e.kind}): {e}")
            return []
        except Exception as e:
            self.last_error = redact_secrets(f"{type(e).__name__}: {e}")[:200]
            self._reset_filter_stats()
            logger.warning(f"{self.name} 站内检索异常: {e}")
            return []

        raw_rows = [r for r in (raw or []) if isinstance(r, dict)]
        # 过滤顺序（先便宜后昂贵）：主机白名单 → 非目标页面黑名单 → 相关性评分
        kept = [r for r in raw_rows
                if self.host_allowed(r.get("url") or r.get("link") or "",
                                     self.allowed_hosts)
                and not self.is_noise(r.get("url") or r.get("link") or "")
                and self._relevant(r, q)]

        # 成功路径（有结果，或结果均被正常滤除）：清空失败信号
        self.last_error = None
        results = self.normalize_results(kept)[:limit]
        self.last_filter_stats = {"raw": len(raw_rows), "kept": len(results),
                                  "dropped": len(raw_rows) - len(results)}
        logger.info(f"{self.name} 站内检索：后端 {len(raw_rows)} 条 → "
                    f"过滤后 {len(results)} 条")
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

    # ------------------------------------------------------------------
    # 去噪：非目标页面黑名单 + 相关性过滤 + 过滤统计
    # ------------------------------------------------------------------
    def _reset_filter_stats(self) -> None:
        """过滤统计归零（时机同 ``last_error`` 的清空：空查询与失败路径）。"""
        self.last_filter_stats = {"raw": 0, "kept": 0, "dropped": 0}

    def is_noise(self, url: str) -> bool:
        """是否已知的非目标页面（黑名单命中：非笔记子域或索引页路径）。

        未配置黑名单时恒为 False——既有通用源行为完全不变。
        """
        try:
            parsed = urlparse(url or "")
            host = (parsed.hostname or "").lower()
            # 路径归一：/explore 与 /explore/ 视为同一路径
            path = (parsed.path or "/").rstrip("/") or "/"
        except Exception:
            return False
        if any(host == h or host.endswith("." + h) for h in self.blocked_hosts):
            return True
        return path in self.blocked_paths

    def _relevant(self, item: Dict, query: str) -> bool:
        """相关性过滤：与网页源共用评分器与阈值（``RELEVANCE_THRESHOLD``）。

        宁可返回 0 条也不返回噪声——实测站内源若不做此过滤，与查询毫无关系的
        笔记会原样进入结果集（安全类查询实测 10/10 条评分均为 0.0）。

        无关键词时 ``relevance_detail`` 返回 ``passed=True``（不误杀），此处
        沿用该语义，不覆写。

        已知口径差异：``total`` 含时效分，而各后端对发布时间的供给不同（博查
        给 ``datePublished``、Brave 恒空、web 源恒空），故**同一查询换后端可能
        得到不同的过滤结果**。这是刻意的：时效是真实信号，不为了对齐而抹平。
        """
        from intelnexus.core.search import relevance_detail
        try:
            return bool((relevance_detail(item, query) or {}).get("passed"))
        except Exception as e:
            # 评分器异常不得让整个源失效：放行（宁可多收，不因评分崩溃丢结果）
            logger.warning(f"{self.name} 相关性评分异常，已放行: "
                           f"{redact_secrets(str(e))}")
            return True
