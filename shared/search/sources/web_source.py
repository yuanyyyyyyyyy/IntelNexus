"""
网页搜索引擎适配器
================
薄包 shared/search/web.py 的 get_web_results。
保留内部 FAST/SLOW 引擎分级与「结果不足再触发慢引擎」策略，registry 不感知。
"""
from typing import Dict, List

from shared.logger import get_logger
from shared.search.web import get_web_results
from shared.search.source import BaseSearchSource, CATEGORY_WEB

logger = get_logger(__name__)


class WebSearchSource(BaseSearchSource):
    """网页搜索源（Bing/DuckDuckGo/Yahoo/Yandex/Baidu 统一入口）。"""

    def __init__(self, name: str = "Web", max_workers: int = 5,
                 enabled: bool = True, requires_proxy: bool = False):
        super().__init__(name=name, category=CATEGORY_WEB,
                         enabled=enabled, requires_proxy=requires_proxy)
        self.max_workers = max_workers

    def search(self, query, max_results: int = 25) -> List[Dict]:
        try:
            raw = get_web_results(query, self.max_workers, max_results)
        except Exception as e:
            logger.warning(f"WebSearchSource 检索失败: {e}")
            return []
        return self.normalize_results(raw)
