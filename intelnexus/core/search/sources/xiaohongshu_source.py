"""
小红书搜索源
============
通用站内检索源（``SiteScopedSource``）的小红书实例：经站内检索后端
（博查 Bocha / Brave / Google CSE，见
``intelnexus.core.search.sitesearch``）按站内限定语义检索小红书笔记，
再按主机白名单收口，产出平台统一字段结果。

为什么不复用公共网页引擎（2026-09-15 实测）：
- ``cn.bing.com`` 完全忽略 ``site:`` 算子（``log4j`` / ``site:github.com log4j`` /
  ``site:csdn.net log4j`` 返回同一结果集）；
- ``www.baidu.com`` 返回「百度安全验证」反爬页，解析不到条目；
- ``html.duckduckgo.com`` 返回 HTTP 202 挑战页；
- ``bing.com/search?format=rss`` 返回 200 但 RSS 同样忽略 ``site:``。
因此必须经站内检索后端取数（需在「搜索服务设置」配置 Key）。

合规边界：不直连小红书接口、不模拟登录/签名、不绕过任何反爬。
"""
from intelnexus.core.search.source import CATEGORY_CUSTOM
from intelnexus.core.search.sources.site_scoped_source import SiteScopedSource


class XiaohongshuSource(SiteScopedSource):
    """小红书站内内容检索源（经站内检索后端 site: 定向）。"""

    #: 主站与短链域名；结果 URL 主机需与其相等或以 ``.<域名>`` 结尾才保留
    ALLOWED_HOSTS = ("xiaohongshu.com", "xhslink.com")
    #: 传给后端的站内限定域名
    DOMAINS = ("xiaohongshu.com",)

    def __init__(self, name: str = "Xiaohongshu",
                 category: str = CATEGORY_CUSTOM,
                 enabled: bool = True, requires_proxy: bool = False,
                 max_results: int = 10,
                 backend=None, backend_factory=None):
        super().__init__(
            name=name, domains=self.DOMAINS, allowed_hosts=self.ALLOWED_HOSTS,
            category=category, display_source=name, enabled=enabled,
            requires_proxy=requires_proxy, max_results=max_results,
            backend=backend, backend_factory=backend_factory)

    @classmethod
    def _is_xhs_url(cls, url: str) -> bool:
        """兼容旧调用点：主机是否属小红书白名单。"""
        return cls.host_allowed(url, cls.ALLOWED_HOSTS)
