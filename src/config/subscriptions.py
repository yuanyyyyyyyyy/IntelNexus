"""
订阅用户配置管理模块
===================
管理AI简报的订阅用户信息和推送配置
"""

import os
import json
from typing import Dict, List, Optional
from pathlib import Path
from datetime import datetime


SUBSCRIPTIONS_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "data", "subscriptions.json")


def _ensure_subscriptions_file():
    """确保订阅配置文件存在"""
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    
    if not os.path.exists(SUBSCRIPTIONS_FILE):
        initial_data = {"subscribers": []}
        with open(SUBSCRIPTIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(initial_data, f, ensure_ascii=False, indent=2)


def get_all_subscribers() -> List[Dict]:
    """获取所有订阅用户"""
    _ensure_subscriptions_file()
    try:
        with open(SUBSCRIPTIONS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get("subscribers", [])
    except Exception as e:
        print(f"Error reading subscribers: {e}")
        return []


def get_subscriber(subscriber_id: str) -> Optional[Dict]:
    """获取单个订阅用户"""
    subscribers = get_all_subscribers()
    for sub in subscribers:
        if sub["id"] == subscriber_id:
            return sub
    return None


def add_subscriber(
    name: str,
    email: str,
    channels: Dict,
    schedule: Dict,
    categories: List[str]
) -> bool:
    """
    添加订阅用户
    
    Args:
        name: 用户名称
        email: 邮箱地址
        channels: 推送渠道配置
        schedule: 定时配置
        categories: 关注类别列表
    
    Returns:
        bool: 是否添加成功
    """
    _ensure_subscriptions_file()
    
    if not name or not email:
        return False
    
    try:
        with open(SUBSCRIPTIONS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        new_subscriber = {
            "id": f"sub_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            "name": name,
            "email": email,
            "channels": channels,
            "schedule": schedule,
            "categories": categories,
            "created_at": datetime.now().isoformat(),
            "last_sent": None
        }
        
        data["subscribers"].append(new_subscriber)
        
        with open(SUBSCRIPTIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return True
    except Exception as e:
        print(f"Error adding subscriber: {e}")
        return False


def remove_subscriber(subscriber_id: str) -> bool:
    """
    删除订阅用户
    
    Args:
        subscriber_id: 用户ID
    
    Returns:
        bool: 是否删除成功
    """
    _ensure_subscriptions_file()
    
    try:
        with open(SUBSCRIPTIONS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        original_len = len(data["subscribers"])
        data["subscribers"] = [s for s in data["subscribers"] if s["id"] != subscriber_id]
        
        if len(data["subscribers"]) == original_len:
            return False
        
        with open(SUBSCRIPTIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return True
    except Exception as e:
        print(f"Error removing subscriber: {e}")
        return False


def update_subscriber(subscriber_id: str, updates: Dict) -> bool:
    """
    更新订阅用户
    
    Args:
        subscriber_id: 用户ID
        updates: 要更新的字段
    
    Returns:
        bool: 是否更新成功
    """
    _ensure_subscriptions_file()
    
    try:
        with open(SUBSCRIPTIONS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        found = False
        for sub in data["subscribers"]:
            if sub["id"] == subscriber_id:
                sub.update(updates)
                found = True
                break
        
        if not found:
            return False
        
        with open(SUBSCRIPTIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return True
    except Exception as e:
        print(f"Error updating subscriber: {e}")
        return False


def update_last_sent(subscriber_id: str) -> bool:
    """
    更新订阅用户的最后发送时间
    
    Args:
        subscriber_id: 用户ID
    
    Returns:
        bool: 是否更新成功
    """
    return update_subscriber(subscriber_id, {"last_sent": datetime.now().isoformat()})


def get_active_subscribers() -> List[Dict]:
    """获取所有已启用定时推送的订阅用户"""
    subscribers = get_all_subscribers()
    return [s for s in subscribers if s.get("schedule", {}).get("enabled", False)]


def get_subscribers_by_category(category: str) -> List[Dict]:
    """获取关注特定类别的订阅用户"""
    subscribers = get_all_subscribers()
    return [s for s in subscribers if category in s.get("categories", [])]
