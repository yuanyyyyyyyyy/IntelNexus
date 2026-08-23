"""
推送结果日志模块
================
把每次简报推送的各渠道成败落盘到 data/push_log.json，
供分析面板展示「推送成功率 / 最近失败原因」（修复：失败只进 logger，管理员不可见）。
"""

import os
from datetime import datetime, timedelta
from typing import Dict

from intelnexus.core.logger import get_logger
from intelnexus.core.settings.file_lock import safe_read_json, safe_write_json
from intelnexus.config.paths import get_data_dir

logger = get_logger(__name__)

PUSH_LOG_FILE = os.path.join(get_data_dir(), "push_log.json")

# 上限保护：只保留最近 N 条记录
_MAX_ENTRIES = 500


def _load() -> dict:
    data = safe_read_json(PUSH_LOG_FILE)
    if not isinstance(data, dict):
        return {"entries": []}
    data.setdefault("entries", [])
    return data


def record_push_result(briefing_id: str, subscriber_id: str,
                       channel_results: Dict[str, bool]) -> None:
    """记录一次对单个订阅者的推送结果。

    Args:
        briefing_id: 简报标识（历史文件名）
        subscriber_id: 订阅者 id
        channel_results: 各渠道发送结果，如 {"email": True, "wecom": False}
    """
    try:
        data = _load()
        data["entries"].append({
            "briefing_id": briefing_id,
            "subscriber_id": subscriber_id,
            "channels": dict(channel_results or {}),
            "timestamp": datetime.now().isoformat(),
        })
        if len(data["entries"]) > _MAX_ENTRIES:
            data["entries"] = data["entries"][-_MAX_ENTRIES:]
        safe_write_json(PUSH_LOG_FILE, data)
    except Exception as e:
        # 日志失败绝不影响推送主流程
        logger.warning(f"record_push_result failed: {e}")


def get_push_stats(days: int = 7) -> Dict:
    """汇总最近 N 天的推送统计。

    Returns:
        {
          "total_sends": 触达尝试次数（订阅者×次）,
          "success_sends": 至少一个渠道成功的次数,
          "success_rate": float 0~1（无数据时为 None）,
          "channel_failures": {"email": n, ...},
          "recent_failures": [最近5条失败明细],
        }
    """
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    entries = [
        e for e in _load()["entries"]
        if e.get("timestamp", "") >= cutoff
    ]

    total = len(entries)
    success = sum(1 for e in entries if any((e.get("channels") or {}).values()))
    failures_by_channel: Dict[str, int] = {}
    failed_entries = []
    for e in entries:
        ch = e.get("channels") or {}
        for name, ok in ch.items():
            if ok is False:
                failures_by_channel[name] = failures_by_channel.get(name, 0) + 1
        if not any(ch.values()) and ch:
            failed_entries.append(e)

    return {
        "total_sends": total,
        "success_sends": success,
        "success_rate": (success / total) if total else None,
        "channel_failures": failures_by_channel,
        "recent_failures": failed_entries[-5:][::-1],
    }
