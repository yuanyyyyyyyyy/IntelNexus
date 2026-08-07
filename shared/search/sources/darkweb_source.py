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

from shared.logger import get_logger
from src.search.darkweb import get_darkweb_results, is_available as darkweb_available
from shared.search.source import BaseSearchSource, CATEGORY_DARKWEB

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
        # 主开关关闭时直接返回空，与旧行为一致
        if not darkweb_available():
            logger.warning("暗网搜索已启用但 Tor 未连接或 Ahmia 不可用")
            return []
        try:
            raw = get_darkweb_results(
                query, self.max_workers, self.advanced_mode,
                self.tor_port, self.ui_sites)
        except Exception as e:
            logger.warning(f"DarkWebSource 检索失败: {e}")
            return []
        return self.normalize_results(raw)
