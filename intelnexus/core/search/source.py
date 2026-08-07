"""
搜索源统一抽象基类
====================
将分散在 shared/search/web.py、shared/search/news.py、intel-search 暗网模块的
函数式搜索源封装为对象（SearchSource），使「搜索源」成为一等公民。

设计原则：
- 现有 get_*_results 成熟实现零改动，仅由适配器薄包调用（见 sources/ 包）。
- 每个源统一产出 {title, link, description, source, category} 字典。
- 代理收口沿用 shared/search.__init__.get_http_proxies_for(requires_proxy)。
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from intelnexus.core.logger import get_logger
from intelnexus.core.search import get_http_proxies_for

logger = get_logger(__name__)

# 源类别常量
CATEGORY_WEB = "web"
CATEGORY_NEWS = "news"
CATEGORY_DARKWEB = "darkweb"
CATEGORY_CUSTOM = "custom"


class BaseSearchSource(ABC):
    """搜索源抽象基类。

    子类必须实现 ``search``；``normalize_result`` 提供默认归一化，可按需覆写。
    """

    #: 显示名（registry 内唯一标识）
    name: str = ""
    #: 类别：web / news / darkweb / custom
    category: str = CATEGORY_CUSTOM
    #: 是否启用（可由配置或 UI 控制）
    enabled: bool = True
    #: 是否需要代理（决定代理收口行为，避免幽灵代理超时）
    requires_proxy: bool = False

    def __init__(self, name: str = "", category: str = "", enabled: bool = True,
                 requires_proxy: bool = False):
        if name:
            self.name = name
        if category:
            self.category = category
        self.enabled = enabled
        self.requires_proxy = requires_proxy

    @abstractmethod
    def search(self, query, max_results: int = 20) -> List[Dict]:
        """执行检索，返回结果列表（元素尽量为归一化字典）。"""
        raise NotImplementedError

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------
    def get_proxies(self) -> Optional[dict]:
        """返回适用于本源的代理配置（收口自 get_http_proxies_for）。

        requires_proxy=False 时永远返回 None（强制直连）；
        requires_proxy=True 时返回实际代理，未配置则返回 None。
        """
        return get_http_proxies_for(self.requires_proxy)

    def normalize_result(self, item: Dict) -> Dict:
        """将单个结果归一化为统一结构。

        统一字段：title / link / description / source / category。
        暗网与新闻源使用 ``url`` 而非 ``link``，此处统一映射。
        """
        if not isinstance(item, dict):
            return {}
        link = item.get("link") or item.get("url") or ""
        return {
            "title": item.get("title", ""),
            "link": link,
            "description": item.get("description", ""),
            "source": item.get("source", self.name) or self.name,
            "category": self.category,
        }

    def normalize_results(self, items: List[Dict]) -> List[Dict]:
        """批量归一化并剔除无效项（无 link 的丢弃）。"""
        out = []
        for it in items or []:
            norm = self.normalize_result(it)
            if norm.get("link"):
                out.append(norm)
        return out

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.name!r} category={self.category} enabled={self.enabled}>"
