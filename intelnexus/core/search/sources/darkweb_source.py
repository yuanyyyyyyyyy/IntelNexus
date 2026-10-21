"""
暗网搜索源适配器
==============
薄包 intel-search/src/search/darkweb.py 的 get_darkweb_results。
注意：暗网源本身内部已做去重，但未做域名黑名单/相关性过滤。

网络拓扑与 HTTP 代理门控无关：Ahmia/OnionLink 是明网站点（requests 自动
读系统代理），TorDex/自定义 onion 走内置 socks5h 会话直连本地 Tor 端口——
因此 requires_proxy 恒为 False。旧默认 True 时，「UI 未配 HTTP 代理」会让
collect 的 no_proxy 门控把整个源静默跳过，连免 Tor 的 Ahmia 都没有机会执行。

get_darkweb_results 签名含 advanced_mode / tor_port / ui_sites，
这些参数在构造时捕获，统一 search(query, max_results) 接口只传 query。
"""
import time
from typing import Dict, List, Optional

from intelnexus.core.logger import get_logger
from intelnexus.search_app.darkweb import (
    CUSTOM_SITE_LAST_ERRORS,
    get_darkweb_results,
    get_custom_onion_sites,
    is_available as darkweb_available,
    tor_reachable,
)
from intelnexus.core.search.source import BaseSearchSource, CATEGORY_DARKWEB

logger = get_logger(__name__)


class DarkWebSource(BaseSearchSource):
    """暗网搜索源（Ahmia / OnionLink / TorDex / 自定义 onion 站点）。"""

    def __init__(self, name: str = "DarkWeb", max_workers: int = 5,
                 advanced_mode: bool = False, tor_port: int = 9150,
                 ui_sites: Optional[List[Dict]] = None,
                 enabled: bool = True, requires_proxy: bool = False):
        # 暗网主开关由 ENABLE_DARKWEB 决定；advanced 模式与自定义 onion 需本地 Tor
        super().__init__(name=name, category=CATEGORY_DARKWEB,
                         enabled=enabled, requires_proxy=requires_proxy)
        self.max_workers = max_workers
        self.advanced_mode = advanced_mode
        self.tor_port = tor_port
        self.ui_sites = ui_sites or []

    def search(self, query, max_results: int = 20) -> List[Dict]:
        # 主开关关闭时直接返回空，与旧行为一致。
        # 警告作用域（F3 修复）：仅在 advanced 模式（用户明确想用 Tor）且一次性
        # 提示，不再对每次普通搜索刷「Tor 未连接」——多数用户根本没打算用暗网。
        if not darkweb_available():
            if self.advanced_mode and not getattr(self, "_warned_unavailable", False):
                logger.info("暗网高级模式已启用但 Tor/Ahmia 不可用，本次跳过暗网源")
                self._warned_unavailable = True
            return []
        # Tor 依赖探测：TorDex 与自定义 onion 站点都要本地 Tor SOCKS。
        # 不可达时把原因写进 last_error——collect 对「空结果 + last_error」
        # 按失败入健康面板，Tor 没开不再被误读为「没有暗网结果」。
        tor_warning = None
        if (self.advanced_mode or get_custom_onion_sites(self.ui_sites)) \
                and not tor_reachable(self.tor_port):
            tor_warning = (f"Tor SOCKS 代理不可达 (127.0.0.1:{self.tor_port})，"
                           f".onion 检索已跳过，仅明网引擎（Ahmia）可用")
            logger.warning(f"DarkWebSource: {tor_warning}")
        try:
            raw = get_darkweb_results(
                query, self.max_workers, self.advanced_mode,
                self.tor_port, self.ui_sites)
        except Exception as e:
            logger.warning(f"DarkWebSource 检索失败: {e}")
            self.last_error = f"{type(e).__name__}: {e}"[:200]
            return []
        # R5：0 条先重试一次（Ahmia 软限流/壳页抖动多为瞬时），仍为 0 则写可观测
        # 信号——健康面板由「无相关结果」变为「检索异常+原因」，不再无解释。
        if not raw:
            time.sleep(2)
            try:
                raw = get_darkweb_results(
                    query, self.max_workers, self.advanced_mode,
                    self.tor_port, self.ui_sites)
            except Exception as e:
                logger.warning(f"DarkWebSource 重试失败: {e}")
        if not raw:
            self.last_error = ("暗网引擎返回 0 条（Ahmia 可能限流/抖动，或该查询"
                               "在暗网索引无覆盖；稍候重试或换威胁类关键词）")
        # 保留降级警告：不能被无条件清空，否则「Tor 不通」在健康面板上永远不可见。
        # R7a（2026-10-20）：仅在确有降级警告时覆盖——此前无条件赋值会把 R5b 的
        # 「0 条重试后仍空」信号冲掉，健康面板退回无解释的「无相关结果」。
        if tor_warning:
            self.last_error = tor_warning
        # R1：自定义站点失败原因透出——拼进 last_error，空结果时随源进健康面板。
        # 已知边界：registry 对非空结果路径会清 last_error（F3），故「站点失败但
        # Ahmia 有结果」时仍可能不可见；彻底修复需 registry 收口（见 P2 路线）。
        try:
            if CUSTOM_SITE_LAST_ERRORS:
                detail = "; ".join(f"{k}: {v}"
                                   for k, v in list(CUSTOM_SITE_LAST_ERRORS.items())[:3])
                self.last_error = f"{self.last_error}; " if self.last_error else ""
                self.last_error += f"自定义源失败 — {detail}"
        except Exception:
            pass
        return self.normalize_results(raw)
