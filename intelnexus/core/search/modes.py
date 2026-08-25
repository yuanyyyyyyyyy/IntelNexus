"""
搜索模式集中定义
================
消除 main.py / shared/ui/helpers.py / shared/llm/core.py 三处重复的 mode 常量与描述。
调度层与 UI 统一从此处导入。

CLI --mode 取值保持向后兼容：all / web / news / darkweb。
"""
from typing import Dict, List, Tuple

# 模式 -> (i18n key, 中文名, 包含的来源类别)
# UI 渲染用 i18n key；后端用 categories 决定 registry 查询哪些源。
SEARCH_MODES: Dict[str, Tuple[str, str, List[str]]] = {
    "all": ("mode_all", "全部来源", ["web", "news", "darkweb", "custom",
                                     "threat_intel", "community", "exploit"]),
    "web": ("mode_web", "网页搜索", ["web"]),
    "news": ("mode_news", "新闻资讯", ["news"]),
    "darkweb": ("mode_darkweb", "暗网搜索", ["darkweb"]),
    "threat": ("mode_threat", "威胁情报", ["threat_intel", "exploit"]),
    # 内部模式：智能路由的通用分支（不进侧边栏 radio，仅 resolve_mode 返回）
    "smart_general": ("mode_smart_general", "智能通用", ["web", "news", "community"]),
}

# 人类可读描述（供 LLM 系统提示词与 CLI 回显使用）
MODE_DESCRIPTIONS: Dict[str, str] = {
    "all": "综合所有来源：网页、新闻、暗网、威胁情报、社区、漏洞利用",
    "web": "主要来源：网页搜索结果",
    "news": "主要来源：新闻资讯",
    "darkweb": "主要来源：暗网资源（.onion 网站）",
    "threat": "威胁情报与漏洞利用代码",
}

# 向后兼容：旧 main.py 用 {mode: 英文标签} 形式
SEARCH_MODES_LABELS: Dict[str, str] = {
    "web": "Web Search",
    "news": "News Articles",
    "darkweb": "Dark Web (Optional)",
    "all": "All Sources",
    "threat": "Threat Intelligence",
}


SMART_MODE_KEY = "smart"
SMART_GENERAL_KEY = "smart_general"


def resolve_mode(query: str) -> str:
    """smart 模式按查询主题动态路由到实际模式；其余模式原样返回。

    智能路由规则（与 llm.core.classify_query_topic 同一套安全提示词）：
    - 安全类查询 -> threat 聚焦（威胁情报+漏洞利用源），叠加 web 补充公开报道
    - 通用类查询 -> web+news+community（不浪费暗网/漏洞库的检索时间）
    """
    if not query:
        return "all"
    from intelnexus.core.llm.core import classify_query_topic
    kind = classify_query_topic(query)
    return "threat" if kind == "security" else SMART_GENERAL_KEY


# 通用查询的类别集合（web+news+community；不含暗网与漏洞库）
GENERAL_CATEGORIES: List[str] = ["web", "news", "community"]


def get_mode_categories(mode: str) -> List[str]:
    """返回该模式应覆盖的源类别；未知模式回退到 all。"""
    if mode == SMART_MODE_KEY:
        return GENERAL_CATEGORIES
    return SEARCH_MODES.get(mode, SEARCH_MODES["all"])[2]


def get_mode_description(mode: str) -> str:
    """返回模式描述，未知回退到 all。"""
    return MODE_DESCRIPTIONS.get(mode, MODE_DESCRIPTIONS["all"])
