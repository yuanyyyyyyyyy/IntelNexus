"""
AI简报模块
=========
提供AI领域每日情报简报的采集、分析、生成和推送功能
"""

from intelnexus.briefing.config import WATCH_CATEGORIES, BRIEFING_CONFIG
from intelnexus.briefing.collector import AIBriefingCollector
from intelnexus.briefing.analyzer import AIBriefingAnalyzer
from intelnexus.briefing.notifier import AIBriefingNotifier
from intelnexus.briefing.scheduler import AIBriefingScheduler

__all__ = [
    "WATCH_CATEGORIES",
    "BRIEFING_CONFIG",
    "AIBriefingCollector",
    "AIBriefingAnalyzer",
    "AIBriefingNotifier",
    "AIBriefingScheduler"
]
