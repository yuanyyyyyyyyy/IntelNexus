"""
AI简报模块
=========
提供AI领域每日情报简报的采集、分析、生成和推送功能
"""

from ai_briefing.config import WATCH_CATEGORIES, BRIEFING_CONFIG

_LAZY_IMPORTS = {
    "AIBriefingCollector": ("ai_briefing.collector", "AIBriefingCollector"),
    "AIBriefingAnalyzer":  ("ai_briefing.analyzer",   "AIBriefingAnalyzer"),
    "AIBriefingNotifier":  ("ai_briefing.notifier",   "AIBriefingNotifier"),
    "AIBriefingScheduler": ("ai_briefing.scheduler",  "AIBriefingScheduler"),
}


def __getattr__(name):
    if name in _LAZY_IMPORTS:
        module_path, attr = _LAZY_IMPORTS[name]
        import importlib
        module = importlib.import_module(module_path)
        return getattr(module, attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "WATCH_CATEGORIES",
    "BRIEFING_CONFIG",
    "AIBriefingCollector",
    "AIBriefingAnalyzer",
    "AIBriefingNotifier",
    "AIBriefingScheduler"
]
