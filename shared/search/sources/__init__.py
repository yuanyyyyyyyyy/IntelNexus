"""
搜索源适配器包
==============
将现有函数式搜索源（web/news/darkweb）薄包为 BaseSearchSource 子类。
各适配器内部保留原有性能/代理策略，registry 不感知。
"""
from shared.search.sources.web_source import WebSearchSource
from shared.search.sources.news_source import NewsSearchSource
from shared.search.sources.darkweb_source import DarkWebSource
from shared.search.sources.user_source import UserSource

__all__ = [
    "WebSearchSource",
    "NewsSearchSource",
    "DarkWebSource",
    "UserSource",
]
