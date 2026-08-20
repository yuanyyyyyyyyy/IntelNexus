"""
搜索源适配器包
==============
将现有函数式搜索源（web/news/darkweb）薄包为 BaseSearchSource 子类。
各适配器内部保留原有性能/代理策略，registry 不感知。
"""
from intelnexus.core.search.sources.web_source import WebSearchSource
from intelnexus.core.search.sources.news_source import NewsSearchSource
from intelnexus.core.search.sources.darkweb_source import DarkWebSource
from intelnexus.core.search.sources.user_source import UserSource
from intelnexus.core.search.sources.exploitdb_source import ExploitDBSource
from intelnexus.core.search.sources.otx_source import AlienVaultOTXSource
from intelnexus.core.search.sources.hackernews_source import HackerNewsSource
from intelnexus.core.search.sources.nvd_source import NVDSearchSource
from intelnexus.core.search.sources.cisa_kev_source import CISAKEVSource
from intelnexus.core.search.sources.cnvd_source import CNVDSource
from intelnexus.core.search.sources.security_news_source import SecurityNewsSource
from intelnexus.core.search.sources.arxiv_source import ArxivSource
from intelnexus.core.search.sources.tech_community_source import TechCommunitySource
from intelnexus.core.search.sources.huggingface_source import HuggingFaceSource
from intelnexus.core.search.sources.qianxin_source import QianxinSource

__all__ = [
    "WebSearchSource",
    "NewsSearchSource",
    "DarkWebSource",
    "UserSource",
    "ExploitDBSource",
    "AlienVaultOTXSource",
    "HackerNewsSource",
    "NVDSearchSource",
    "CISAKEVSource",
    "CNVDSource",
    "SecurityNewsSource",
    "ArxivSource",
    "TechCommunitySource",
    "HuggingFaceSource",
    "QianxinSource",
]
