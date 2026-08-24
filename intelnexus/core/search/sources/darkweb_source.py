"""
暗网搜索源适配器
==============
薄包 intel-search/src/search/darkweb.py 的 get_darkweb_results。
注意：暗网源本身内部已做去重，但未做域名黑名单/相关性过滤；
其 requires_proxy 取决于 advanced_mode（OnionLink/TorDex 需 Tor）。

由于 get_darkweb_results 签名含 advanced_mode / tor_port / ui_sites，
这些参数在构造时捕获，统一 search(query, max_results) 接口只传 query。
"""
from typing import Dict, List, Optional

from intelnexus.core.logger import get_logger
from intelnexus.search_app.darkweb import get_darkweb_results, is_available as darkweb_available
from intelnexus.core.search.source import BaseSearchSource, CATEGORY_DARKWEB

logger = get_logger(__name__)


class DarkWebSource(BaseSearchSource):
    """暗网搜索源（Ahmia / OnionLink / TorDex / 自定义 onion 站点）。"""

    def __init__(self, name: str = "DarkWeb", max_workers: int = 5,
                 advanced_mode: bool = False, tor_port: int = 9150,
                 ui_sites: Optional[List[Dict]] = None,
                 enabled: bool = True, requires_proxy: bool = True):
        # 暗网主开关由 ENABLE_DARKWEB 决定；advanced 模式需 Tor 代理
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
        try:
            raw = get_darkweb_results(
                query, self.max_workers, self.advanced_mode,
                self.tor_port, self.ui_sites)
        except Exception as e:
            logger.warning(f"DarkWebSource 检索失败: {e}")
            return []
        return self.normalize_results(raw)
