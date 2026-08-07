"""
Topic Registry —— 情报主题中枢
================================
统一「搜索（单点取证）」与「简报（自动巡防）」的数据源：

- 系统预设（preset）关注点来自 briefing.config.WATCH_CATEGORIES（原 6 类）。
- 用户每次搜索可把查询固化为常驻 Topic（origin="user_search"），
  从而让「用户行为」反向驱动简报内容，形成双向飞轮。

Topic 数据结构刻意兼容 WATCH_CATEGORIES 条目字段
（name / description / search_queries / keywords_*），以便复用既有采集逻辑。
"""
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional


@dataclass
class Topic:
    id: str
    name: str
    description: str = ""
    search_queries: List[str] = field(default_factory=list)
    keywords_en: List[str] = field(default_factory=list)
    keywords_zh: List[str] = field(default_factory=list)
    icon: str = "🔎"
    sources: List[str] = field(default_factory=lambda: ["web", "news"])
    subscribers: List[str] = field(default_factory=list)
    threshold: float = 0.0
    origin: str = "preset"          # preset | user_search
    enabled: bool = True
    created_at: Optional[str] = None

    def to_category_dict(self) -> Dict:
        """转换为与 WATCH_CATEGORIES 条目兼容的 dict，供 collector 直接使用。"""
        return {
            "name": self.name,
            "name_en": self.name,
            "description": self.description,
            "icon": self.icon,
            "keywords_en": self.keywords_en,
            "keywords_zh": self.keywords_zh,
            "search_queries": self.search_queries,
            "origin": self.origin,
            "enabled": self.enabled,
        }

    def to_dict(self) -> Dict:
        return asdict(self)


def topic_from_category(cat_id: str, cat: Dict, origin: str = "preset") -> "Topic":
    """从 WATCH_CATEGORIES 条目构造 Topic（preset）。"""
    from datetime import datetime
    return Topic(
        id=cat_id,
        name=cat.get("name", cat_id),
        description=cat.get("description", ""),
        search_queries=cat.get("search_queries", []),
        keywords_en=cat.get("keywords_en", []),
        keywords_zh=cat.get("keywords_zh", []),
        icon=cat.get("icon", "🔎"),
        origin=origin,
        created_at=datetime.now().isoformat(),
    )
