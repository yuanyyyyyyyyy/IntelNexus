"""
简报收藏草稿读写
===============
搜索结果可被「收藏」为简报素材，沉淀到 data/briefing_drafts.json。
简报生成时作为高优输入拼入对应栏目，打通「搜→报」飞轮。

结构（单条草稿）：
{
  "id": "drf_xxx",
  "title": str,
  "url": str,
  "content": str,
  "description": str,
  "source": str,
  "saved_at": ISO datetime,
  "category_hint": str   # 可选，用户/系统建议归入的关注点 ID
}
"""

import os
from typing import Dict, List, Optional

from shared.logger import get_logger
from shared.settings.file_lock import safe_read_json, safe_write_json

logger = get_logger(__name__)


DRAFTS_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "data", "briefing_drafts.json")


def _ensure_file():
    if not os.path.exists(DRAFTS_FILE):
        try:
            safe_write_json(DRAFTS_FILE, [])
        except Exception as e:
            logger.warning(f"创建 briefing_drafts.json 失败: {e}")


def add_draft(item: Dict) -> bool:
    """追加一条收藏草稿。item 应含 title/url/content/source 等字段。

    去重：若已存在相同 url 的草稿则跳过（避免重复收藏）。
    """
    if not item or not item.get("url"):
        return False
    _ensure_file()
    drafts = safe_read_json(DRAFTS_FILE) or []
    if any(d.get("url") == item.get("url") for d in drafts):
        return False

    from datetime import datetime
    draft = {
        "id": f"drf_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
        "title": item.get("title", ""),
        "url": item.get("url", ""),
        "content": item.get("content", ""),
        "description": item.get("description", item.get("content", "")[:200]),
        "source": item.get("source", "Unknown"),
        "saved_at": datetime.now().isoformat(),
        "category_hint": item.get("category_hint", ""),
    }
    drafts.append(draft)
    return safe_write_json(DRAFTS_FILE, drafts)


def get_drafts(limit: int = 200) -> List[Dict]:
    """读取收藏草稿（按保存时间倒序，最多 limit 条）。"""
    _ensure_file()
    drafts = safe_read_json(DRAFTS_FILE) or []
    drafts = sorted(drafts, key=lambda d: d.get("saved_at", ""), reverse=True)
    return drafts[:limit]


def remove_draft(draft_id: str) -> bool:
    """删除指定草稿。"""
    _ensure_file()
    drafts = safe_read_json(DRAFTS_FILE) or []
    new_drafts = [d for d in drafts if d.get("id") != draft_id]
    if len(new_drafts) == len(drafts):
        return False
    return safe_write_json(DRAFTS_FILE, new_drafts)


def clear_drafts() -> None:
    """清空全部草稿。"""
    _ensure_file()
    safe_write_json(DRAFTS_FILE, [])


def consume_drafts(categories: Optional[List[str]] = None) -> Dict[str, List[Dict]]:
    """取出全部草稿并按 category_hint 归并到对应类目。

    返回 {category_id: [drafts]}。无 category_hint 的草稿归入 "_uncategorized"，
    调用方可自行决定如何并入自动采集。读取后不会删除草稿（便于复用/复查）。
    """
    drafts = get_drafts()
    grouped: Dict[str, List[Dict]] = {}
    for d in drafts:
        cat = d.get("category_hint") or "_uncategorized"
        grouped.setdefault(cat, []).append(d)
    if categories:
        # 仅保留与本次生成类目相关的草稿；未分类的始终保留
        grouped = {k: v for k, v in grouped.items()
                   if k in categories or k == "_uncategorized"}
    return grouped
