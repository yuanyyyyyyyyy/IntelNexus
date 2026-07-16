"""
数据源配置管理模块
=================
管理AI简报的数据源（RSS订阅源、自定义网页等）
"""

import os
import json
from typing import Dict, List, Optional
from pathlib import Path
from datetime import datetime


SOURCES_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "data", "sources.json")


def _ensure_sources_file():
    """确保数据源配置文件存在"""
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    
    if not os.path.exists(SOURCES_FILE):
        initial_data = {
            "subscription_sources": [],
            "custom_sources": []
        }
        with open(SOURCES_FILE, 'w', encoding='utf-8') as f:
            json.dump(initial_data, f, ensure_ascii=False, indent=2)


def get_all_sources() -> Dict[str, List[Dict]]:
    """获取所有数据源"""
    _ensure_sources_file()
    try:
        with open(SOURCES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error reading sources: {e}")
        return {"subscription_sources": [], "custom_sources": []}


def get_sources_by_category(category: str) -> List[Dict]:
    """按类别获取数据源"""
    all_sources = get_all_sources()
    result = []
    for source_type in ["subscription_sources", "custom_sources"]:
        for source in all_sources.get(source_type, []):
            if source.get("category") == category and source.get("enabled", True):
                result.append(source)
    return result


def get_sources_by_type(source_type: str) -> List[Dict]:
    """按类型获取数据源（rss或web）"""
    all_sources = get_all_sources()
    type_key = "subscription_sources" if source_type == "rss" else "custom_sources"
    return all_sources.get(type_key, [])


def add_source(source_type: str, name: str, url: str, category: str) -> bool:
    """
    添加数据源
    
    Args:
        source_type: 数据源类型（rss或web）
        name: 数据源名称
        url: 数据源URL
        category: 分类
    
    Returns:
        bool: 是否添加成功
    """
    _ensure_sources_file()
    
    if not name or not url:
        return False
    
    try:
        with open(SOURCES_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        new_source = {
            "id": f"src_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            "name": name,
            "url": url,
            "type": source_type,
            "category": category,
            "enabled": True,
            "added_at": datetime.now().isoformat()
        }
        
        if source_type == "rss":
            data["subscription_sources"].append(new_source)
        else:
            data["custom_sources"].append(new_source)
        
        with open(SOURCES_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return True
    except Exception as e:
        print(f"Error adding source: {e}")
        return False


def remove_source(source_id: str) -> bool:
    """
    删除数据源
    
    Args:
        source_id: 数据源ID
    
    Returns:
        bool: 是否删除成功
    """
    _ensure_sources_file()
    
    try:
        with open(SOURCES_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        found = False
        for source_type in ["subscription_sources", "custom_sources"]:
            original_len = len(data[source_type])
            data[source_type] = [s for s in data[source_type] if s["id"] != source_id]
            if len(data[source_type]) < original_len:
                found = True
                break
        
        if not found:
            return False
        
        with open(SOURCES_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return True
    except Exception as e:
        print(f"Error removing source: {e}")
        return False


def update_source(source_id: str, updates: Dict) -> bool:
    """
    更新数据源
    
    Args:
        source_id: 数据源ID
        updates: 要更新的字段
    
    Returns:
        bool: 是否更新成功
    """
    _ensure_sources_file()
    
    try:
        with open(SOURCES_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        found = False
        for source_type in ["subscription_sources", "custom_sources"]:
            for source in data[source_type]:
                if source["id"] == source_id:
                    source.update(updates)
                    found = True
                    break
            if found:
                break
        
        if not found:
            return False
        
        with open(SOURCES_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return True
    except Exception as e:
        print(f"Error updating source: {e}")
        return False


def toggle_source(source_id: str, enabled: bool) -> bool:
    """
    启用/禁用数据源
    
    Args:
        source_id: 数据源ID
        enabled: 是否启用
    
    Returns:
        bool: 是否操作成功
    """
    return update_source(source_id, {"enabled": enabled})


def get_enabled_sources() -> List[Dict]:
    """获取所有已启用的数据源"""
    all_sources = get_all_sources()
    result = []
    for source_type in ["subscription_sources", "custom_sources"]:
        for source in all_sources.get(source_type, []):
            if source.get("enabled", True):
                result.append(source)
    return result
