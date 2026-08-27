"""
新闻源适配器
============
薄包 shared/search/news.py 的 get_news_results（RSS / NewsAPI / Bing News / Google News）。
保留源内域名黑名单与相关性过滤行为，registry 出口仅做跨源去重。
"""
from typing import Dict, List, Optional

from intelnexus.core.logger import get_logger
from intelnexus.core.search.news import get_news_results, LAST_NEWS_ERRORS, _LAST_NEWS_ERRORS_LOCK
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
            self.last_error = f"{type(e).__name__}: {e}"[:200]
            return []
        if raw:
            # 成功路径：清空失败信号（正常检索返回空与检索失败必须可区分）
            self.last_error = None
        else:
            # 空结果：锁内原子读取聚合（与 news.py 的 clear/append 互斥），
            # 全部子源零产出且有失败记录才写 last_error（news 模式下 News 常为唯一源，
            # 断网/代理挂时必须可辨识为失败而非「无结果」）。
            with _LAST_NEWS_ERRORS_LOCK:
                summary = "; ".join(LAST_NEWS_ERRORS)
            self.last_error = summary[:200] if summary else None
        return self.normalize_results(raw)
