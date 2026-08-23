"""
知识库存储模块
==============
统一存储用户收藏的简报条目、搜索结果和笔记
"""
import os
import json
from datetime import datetime
from typing import Dict, List, Optional
from intelnexus.core.logger import get_logger

logger = get_logger(__name__)

from intelnexus.config.paths import get_data_dir

DATA_DIR = get_data_dir()
KB_FILE = os.path.join(DATA_DIR, "knowledge_base.json")


def _ensure_data_dir():
    """确保数据目录存在"""
    os.makedirs(DATA_DIR, exist_ok=True)


def _load_kb() -> dict:
    """加载知识库"""
    _ensure_data_dir()
    if not os.path.exists(KB_FILE):
        return {"items": [], "tags": []}
    try:
        with open(KB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"加载知识库失败: {e}")
        return {"items": [], "tags": []}


def _save_kb(data: dict):
    """保存知识库"""
    _ensure_data_dir()
    try:
        with open(KB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"保存知识库失败: {e}")


def add_item(
    item_type: str,
    title: str,
    url: str = "",
    content: str = "",
    source: str = "",
    category: str = "",
    tags: List[str] = None,
    metadata: Dict = None
) -> str:
    """
    添加知识库条目
    
    Args:
        item_type: "briefing_entry" | "search_result" | "note"
        title: 标题
        url: 来源URL
        content: 内容
        source: 来源名称
        category: 分类
        tags: 标签列表
        metadata: 额外元数据
    
    Returns:
        str: 条目ID
    """
    kb = _load_kb()
    
    # 检查URL是否已存在（去重）
    if url:
        for item in kb["items"]:
            if item.get("url") == url and item.get("type") == item_type:
                return item["id"]
    
    # 生成ID
    item_id = f"kb_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    
    # 创建条目
    new_item = {
        "id": item_id,
        "type": item_type,
        "title": title,
        "url": url,
        "content": content,
        "source": source,
        "category": category,
        "tags": tags or [],
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "metadata": metadata or {}
    }
    
    kb["items"].insert(0, new_item)
    
    # 自动添加标签
    if tags:
        for tag in tags:
            if tag not in kb["tags"]:
                kb["tags"].append(tag)
    
    _save_kb(kb)
    return item_id


def get_items(
    item_type: Optional[str] = None,
    tag: Optional[str] = None,
    url: Optional[str] = None,
    limit: int = 50
) -> List[Dict]:
    """
    获取知识库条目
    
    Args:
        item_type: 筛选类型
        tag: 筛选标签
        url: 筛选URL
        limit: 返回数量限制
    
    Returns:
        List[Dict]: 条目列表
    """
    kb = _load_kb()
    items = kb.get("items", [])
    
    # 筛选
    if item_type:
        items = [i for i in items if i.get("type") == item_type]
    if tag:
        items = [i for i in items if tag in i.get("tags", [])]
    if url:
        items = [i for i in items if i.get("url") == url]
    
    return items[:limit]


def get_item(item_id: str) -> Optional[Dict]:
    """获取单个条目"""
    kb = _load_kb()
    for item in kb.get("items", []):
        if item.get("id") == item_id:
            return item
    return None


def update_item(item_id: str, updates: Dict) -> bool:
    """更新条目"""
    kb = _load_kb()
    for item in kb.get("items", []):
        if item.get("id") == item_id:
            item.update(updates)
            item["updated_at"] = datetime.now().isoformat()
            _save_kb(kb)
            return True
    return False


def remove_item(item_id: str) -> bool:
    """删除条目"""
    kb = _load_kb()
    for i, item in enumerate(kb.get("items", [])):
        if item.get("id") == item_id:
            kb["items"].pop(i)
            _save_kb(kb)
            return True
    return False


def add_tag(tag: str) -> bool:
    """添加标签"""
    kb = _load_kb()
    if tag not in kb.get("tags", []):
        kb.setdefault("tags", []).append(tag)
        _save_kb(kb)
        return True
    return False


def get_tags() -> List[str]:
    """获取所有标签"""
    kb = _load_kb()
    return kb.get("tags", [])


def remove_tag(tag: str) -> bool:
    """删除标签"""
    kb = _load_kb()
    if tag in kb.get("tags", []):
        kb["tags"].remove(tag)
        _save_kb(kb)
        return True
    return False


def get_stats() -> Dict:
    """获取知识库统计"""
    kb = _load_kb()
    items = kb.get("items", [])
    
    stats = {
        "total": len(items),
        "by_type": {
            "briefing_entry": 0,
            "search_result": 0,
            "note": 0
        },
        "by_category": {},
        "total_tags": len(kb.get("tags", []))
    }
    
    for item in items:
        item_type = item.get("type", "unknown")
        stats["by_type"][item_type] = stats["by_type"].get(item_type, 0) + 1
        
        category = item.get("category", "uncategorized")
        stats["by_category"][category] = stats["by_category"].get(category, 0) + 1
    
    return stats
