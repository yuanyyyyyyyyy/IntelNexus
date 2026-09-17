"""
来源元数据（共享、零 streamlit 依赖）
====================================

集中维护「检索渠道短名 → 中文展示名」「检索状态码 → 原因」两套映射，以及
``summarize_empty_channels`` 辅助函数，供报告构建层（export/report_builder）
与 UI 展示层（ui/results_view）共用，**保证两端口径单一来源、不再漂移**。

设计约束：本模块严禁 import streamlit / icons，否则 report_builder 与
results_view 互相牵连且无法在缺 streamlit 环境下单测。
"""

from typing import Dict, List

# 渠道短名（与 registry 各源 src.name 对齐）→ 中文展示名
SOURCE_LABELS: Dict[str, str] = {
    "Web": "网页(Web)",
    "News": "新闻(News/RSS)",
    "DarkWeb": "暗网(DarkWeb)",
    "HackerNews": "Hacker News",
    "NVD": "NVD 漏洞库",
    "CISA_KEV": "CISA KEV",
    "CNVD": "CNVD",
    "SecRSS": "安全媒体(SecRSS)",
    "arXiv": "arXiv",
    "TechCommunity": "技术社区",
    "HuggingFace": "HuggingFace",
    "Xiaohongshu": "小红书",
    "AlienVault_OTX": "AlienVault OTX",
    "ExploitDB": "ExploitDB",
    "Qianxin": "奇安信",
}

# 检索状态码（registry._mark 写入的 status 取值）→ 中文原因
STATUS_REASONS: Dict[str, str] = {
    "ok": "无相关结果",
    "error": "检索异常",
    "timeout": "检索超时",
    "no_proxy": "未配置代理已跳过",
    "down": "源不可用",
}


def summarize_empty_channels(source_stats: Dict[str, dict]) -> List[str]:
    """列出「已检索但未产出相关结果」的渠道（count==0），返回说明片段列表。

    仅纳入 ``count==0`` 的渠道（含 status=ok 被相关性过滤剔除、error、timeout 等），
    返回形如 ``["新闻(News/RSS)（无相关结果）", "Hacker News（检索异常）"]``；
    无空渠道时返回空列表。供报告与 UI 共用，保证展示口径一致。
    """
    if not source_stats:
        return []

    notes: List[str] = []
    for name, stat in source_stats.items():
        if not isinstance(stat, dict):
            continue
        # 仅纳入「确实被检索过但 0 产出」的渠道；有贡献的渠道已在分布表中展示。
        count = stat.get("count", 0)
        if count and count > 0:
            continue
        label = SOURCE_LABELS.get(name, name)
        reason = STATUS_REASONS.get(stat.get("status", "ok"), "无相关结果")
        notes.append(f"{label}（{reason}）")

    return notes
