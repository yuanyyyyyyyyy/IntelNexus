"""
Topic Store —— 持久化 Topic Registry 到 data/topics.json
=========================================================
- 首次使用时，将 briefing.config.WATCH_CATEGORIES 固化为 preset topics。
- 用户搜索固化的常驻 Topic（origin="user_search"）追加保存。
- 复用 safe_read_json / safe_write_json，与现有 config 读写一致。
"""
import os
from typing import Dict, List, Optional

from intelnexus.core.logger import get_logger
from intelnexus.core.settings.file_lock import safe_read_json, safe_write_json
from intelnexus.topics.registry import Topic, topic_from_category

logger = get_logger(__name__)

TOPICS_FILE = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "data", "topics.json"
)


def _ensure_store():
    """确保 topics.json 存在；首次写入 preset（来自 WATCH_CATEGORIES）。"""
    if os.path.exists(TOPICS_FILE):
        return
    try:
        from intelnexus.briefing.config import WATCH_CATEGORIES
        presets = [topic_from_category(cid, cfg, origin="preset")
                   for cid, cfg in WATCH_CATEGORIES.items()]
        _write_topics({t.id: t.to_dict() for t in presets})
        logger.info(f"初始化 Topic Registry：写入 {len(presets)} 个预设关注点")
    except Exception as e:
        logger.warning(f"初始化 preset topics 失败: {e}")
        _write_topics({})


def _read_topics() -> Dict[str, dict]:
    _ensure_store()
    data = safe_read_json(TOPICS_FILE) or {}
    if not isinstance(data, dict):
        return {}
    return data


def _write_topics(data: Dict[str, dict]) -> bool:
    try:
        os.makedirs(os.path.dirname(TOPICS_FILE), exist_ok=True)
        return safe_write_json(TOPICS_FILE, data)
    except Exception as e:
        logger.warning(f"写入 topics.json 失败: {e}")
        return False


def get_all_topics() -> List[Topic]:
    """返回全部 Topic（含 preset 与用户自建）。"""
    return [Topic(**v) for v in _read_topics().values()]


def get_enabled_topics() -> List[Topic]:
    """返回 enabled 的 Topic（驱动简报采集）。"""
    return [t for t in get_all_topics() if t.enabled]


def get_topic(topic_id: str) -> Optional[Topic]:
    data = _read_topics()
    if topic_id in data:
        return Topic(**data[topic_id])
    return None


def add_topic(topic: Topic) -> bool:
    """新增或覆盖一个 Topic（用户搜索固化时调用）。"""
    if not topic or not topic.id:
        return False
    data = _read_topics()
    data[topic.id] = topic.to_dict()
    return _write_topics(data)


def update_topic(topic_id: str, updates: Dict) -> bool:
    data = _read_topics()
    if topic_id not in data:
        return False
    data[topic_id].update(updates)
    return _write_topics(data)


def remove_topic(topic_id: str) -> bool:
    data = _read_topics()
    if topic_id in data:
        del data[topic_id]
        return _write_topics(data)
    return False


def set_enabled(topic_id: str, enabled: bool) -> bool:
    return update_topic(topic_id, {"enabled": enabled})


def topic_to_category_map() -> Dict[str, dict]:
    """返回与 WATCH_CATEGORIES 兼容的 {id: category_dict}，供 collector 使用。"""
    return {t.id: t.to_category_dict() for t in get_enabled_topics()}
