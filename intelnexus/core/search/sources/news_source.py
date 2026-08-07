"""
新闻源适配器
============
薄包 shared/search/news.py 的 get_news_results（RSS / NewsAPI / Bing News / Google News）。
保留源内域名黑名单与相关性过滤行为，registry 出口仅做跨源去重。
"""
from typing import Dict, List, Optional

from intelnexus.core.logger import get_logger
from intelnexus.core.search.news import get_news_results
from intelnexus.core.search.source import BaseSearchSource, CATEGORY_NEWS

logger = get_logger(__name__)


class NewsSearchSource(BaseSearchSource):
    """新闻搜索源（RSS / NewsAPI / Bing News / Google News 统一入口）。"""

    def __init__(self, name: str = "News", api_key: Optional[str] = None,
                 enabled: bool = True, requires_proxy: bool = False):
        super().__init__(name=name, category=CATEGORY_NEWS,
                         enabled=enabled, requires_proxy=requires_proxy)
        self.api_key = api_key

    def search(self, query, max_results: int = 15) -> List[Dict]:
        try:
            raw = get_news_results(query, max_results, api_key=self.api_key)
        except Exception as e:
            logger.warning(f"NewsSearchSource 检索失败: {e}")
            return []
        return self.normalize_results(raw)
