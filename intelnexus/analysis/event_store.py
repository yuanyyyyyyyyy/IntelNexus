"""
Event Store Module
==================
事件存储与增量变化检测。

每次搜索完成后，将事件快照存入本地 JSON 文件。
后续搜索同一主题时，自动对比历史快照，检测身份状态/热度/风险/新发现的变化。

数据模型（data/event_store.json）：
{
  "events": {
    "<topic_key>": {
      "topic": "原始查询主题",
      "first_seen": "YYYY-MM-DD",
      "last_seen": "YYYY-MM-DD",
      "search_count": N,
      "snapshots": [
        {
          "timestamp": "ISO格式时间戳",
          "identity_status": "unknown|suspected|confirmed|disputed",
          "heat_level": 0-100,
          "risk_level": "低|中|高",
          "key_findings": ["发现1", "发现2"],
          "source_count": N,
          "result_count": N
        }
      ]
    }
  }
}
"""

import json
import os
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from intelnexus.core.logger import get_logger

logger = get_logger(__name__)

# 事件存储文件路径
_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_STORE_PATH = _DATA_DIR / "event_store.json"
_store_lock = threading.Lock()


def _normalize_topic(topic: str) -> str:
    """将查询主题归一化为存储键（小写、去空格、去标点）。

    确保 "Ox Alpha"、"ox alpha"、"OX-ALPHA" 映射到同一事件。
    """
    cleaned = topic.lower().strip()
    cleaned = re.sub(r'[\s\-_]+', '', cleaned)
    cleaned = re.sub(r'[^\w\u4e00-\u9fff]', '', cleaned)
    return cleaned


def _load_store() -> Dict[str, Any]:
    """加载事件存储（线程安全）。"""
    if not _STORE_PATH.exists():
        return {"events": {}}
    try:
        with open(_STORE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"事件存储加载失败，使用空存储: {e}")
        return {"events": {}}


def _save_store(store: Dict[str, Any]) -> None:
    """保存事件存储（线程安全）。"""
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp_path = _STORE_PATH.with_suffix(".json.tmp")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(store, f, ensure_ascii=False, indent=2)
        tmp_path.replace(_STORE_PATH)
    except OSError as e:
        logger.error(f"事件存储保存失败: {e}")


class EventStore:
    """事件存储与增量变化检测。

    Usage:
        store = EventStore()
        store.save_snapshot("Ox Alpha", snapshot_data)
        changes = store.detect_changes("Ox Alpha", new_snapshot_data)
    """

    def __init__(self):
        self._store = _load_store()

    def reload(self):
        """重新加载存储（用于多进程/手动刷新场景）。"""
        self._store = _load_store()

    def save_snapshot(self, topic: str, snapshot: Dict[str, Any]) -> None:
        """为指定主题保存一个事件快照。

        Args:
            topic: 用户查询主题（如 "Ox Alpha"）
            snapshot: 快照数据，包含:
                - identity_status: str ("unknown"|"suspected"|"confirmed"|"disputed")
                - heat_level: int (0-100)
                - risk_level: str ("低"|"中"|"高")
                - key_findings: List[str]
                - source_count: int
                - result_count: int
        """
        with _store_lock:
            key = _normalize_topic(topic)
            events = self._store.setdefault("events", {})

            if key not in events:
                events[key] = {
                    "topic": topic,
                    "topic_key": key,
                    "first_seen": datetime.now().strftime("%Y-%m-%d"),
                    "last_seen": datetime.now().strftime("%Y-%m-%d"),
                    "search_count": 0,
                    "snapshots": [],
                }

            event = events[key]
            event["last_seen"] = datetime.now().strftime("%Y-%m-%d")
            event["search_count"] = len(event["snapshots"]) + 1

            # 添加时间戳
            snapshot_with_ts = {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                **snapshot,
            }
            event["snapshots"].append(snapshot_with_ts)

            # 限制快照数量（保留最近 20 次）
            if len(event["snapshots"]) > 20:
                event["snapshots"] = event["snapshots"][-20:]

            _save_store(self._store)
            logger.info(
                f"事件快照已保存: {topic} (key={key}, "
                f"snapshot #{event['search_count']})"
            )

    def get_event(self, topic: str) -> Optional[Dict[str, Any]]:
        """获取指定主题的事件记录（不含最新快照，用于对比）。"""
        key = _normalize_topic(topic)
        return self._store.get("events", {}).get(key)

    def get_latest_snapshot(self, topic: str) -> Optional[Dict[str, Any]]:
        """获取指定主题的最新快照。"""
        event = self.get_event(topic)
        if not event or not event.get("snapshots"):
            return None
        return event["snapshots"][-1]

    def detect_changes(
        self, topic: str, new_snapshot: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """对比最新快照与新数据，检测变化。

        Returns:
            None: 无历史记录
            dict: {
                "has_history": True,
                "identity_change": "unknown → suspected" | None,
                "heat_change": "+35" | "-10" | None,
                "risk_change": "低 → 中" | None,
                "new_findings": ["新发现1", ...],
                "search_count": N,
                "days_since_last": N,
            }
        """
        latest = self.get_latest_snapshot(topic)
        if latest is None:
            return None

        changes = {
            "has_history": True,
            "identity_change": None,
            "heat_change": None,
            "risk_change": None,
            "new_findings": [],
            "search_count": self.get_event(topic).get("search_count", 0),
            "days_since_last": 0,
        }

        # 身份状态变化
        old_status = latest.get("identity_status", "unknown")
        new_status = new_snapshot.get("identity_status", "unknown")
        if old_status != new_status:
            changes["identity_change"] = f"{old_status} → {new_status}"

        # 热度变化
        old_heat = latest.get("heat_level", 0)
        new_heat = new_snapshot.get("heat_level", 0)
        heat_diff = new_heat - old_heat
        if abs(heat_diff) >= 5:  # 变化超过 5 才报告
            sign = "+" if heat_diff > 0 else ""
            changes["heat_change"] = f"{sign}{heat_diff}"

        # 风险等级变化
        old_risk = latest.get("risk_level", "低")
        new_risk = new_snapshot.get("risk_level", "低")
        if old_risk != new_risk:
            changes["risk_change"] = f"{old_risk} → {new_risk}"

        # 新发现（在旧快照中不存在的发现）
        old_findings = set(latest.get("key_findings", []))
        new_findings = new_snapshot.get("key_findings", [])
        changes["new_findings"] = [
            f for f in new_findings if f not in old_findings
        ]

        # 距上次搜索天数
        try:
            last_ts = datetime.fromisoformat(latest["timestamp"])
            changes["days_since_last"] = (
                datetime.now() - last_ts
            ).days
        except (KeyError, ValueError):
            pass

        return changes

    def find_related_events(self, topic: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """查找与当前主题相关的其他事件（基于关键词重叠）。

        Args:
            topic: 当前查询主题
            max_results: 最多返回数量

        Returns:
            相关事件列表，按搜索次数降序
        """
        key = _normalize_topic(topic)
        topic_words = set(re.findall(r'[\w\u4e00-\u9fff]+', topic.lower()))

        related = []
        for event_key, event in self._store.get("events", {}).items():
            if event_key == key:
                continue
            event_words = set(
                re.findall(r'[\w\u4e00-\u9fff]+', event.get("topic", "").lower())
            )
            overlap = topic_words & event_words
            if overlap:
                related.append({
                    "topic": event.get("topic", ""),
                    "topic_key": event_key,
                    "search_count": event.get("search_count", 0),
                    "last_seen": event.get("last_seen", ""),
                    "overlap_keywords": list(overlap),
                })

        related.sort(key=lambda x: x["search_count"], reverse=True)
        return related[:max_results]

    def get_all_events_summary(self) -> List[Dict[str, Any]]:
        """获取所有事件的摘要列表（用于事件库浏览）。"""
        events = self._store.get("events", {})
        summary = []
        for key, event in events.items():
            snapshots = event.get("snapshots", [])
            latest = snapshots[-1] if snapshots else {}
            summary.append({
                "topic": event.get("topic", ""),
                "topic_key": key,
                "first_seen": event.get("first_seen", ""),
                "last_seen": event.get("last_seen", ""),
                "search_count": event.get("search_count", 0),
                "identity_status": latest.get("identity_status", "unknown"),
                "heat_level": latest.get("heat_level", 0),
                "risk_level": latest.get("risk_level", "低"),
            })
        summary.sort(key=lambda x: x["last_seen"], reverse=True)
        return summary


# 模块级单例
_shared_store = None
_store_init_lock = threading.Lock()


def get_event_store() -> EventStore:
    """获取进程内复用的 EventStore 单例。"""
    global _shared_store
    if _shared_store is None:
        with _store_init_lock:
            if _shared_store is None:
                _shared_store = EventStore()
    return _shared_store
