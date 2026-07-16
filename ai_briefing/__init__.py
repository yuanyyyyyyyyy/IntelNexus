"""
AI简报模块
=========
提供AI领域每日情报简报的采集、分析、生成和推送功能
"""

from ai_briefing.config import WATCH_CATEGORIES, BRIEFING_CONFIG
from ai_briefing.collector import AIBriefingCollector
from ai_briefing.analyzer import AIBriefingAnalyzer
from ai_briefing.notifier import AIBriefingNotifier
from ai_briefing.scheduler import AIBriefingScheduler

__all__ = [
    "WATCH_CATEGORIES",
    "BRIEFING_CONFIG",
    "AIBriefingCollector",
    "AIBriefingAnalyzer",
    "AIBriefingNotifier",
    "AIBriefingScheduler"
]
