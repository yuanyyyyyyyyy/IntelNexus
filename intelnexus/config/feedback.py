"""
用户反馈存储模块
================
- 简报条目反馈（按分类）
- 搜索结果反馈
- 用户行为追踪（简单版：点击+反馈）
"""
import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from intelnexus.core.logger import get_logger

logger = get_logger(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data")
FEEDBACK_FILE = os.path.join(DATA_DIR, "feedback.json")
BEHAVIOR_FILE = os.path.join(DATA_DIR, "user_behavior.json")

# 数据保留天数
RETENTION_DAYS = 30


def _ensure_data_dir():
    """确保数据目录存在"""
    os.makedirs(DATA_DIR, exist_ok=True)


def _load_json(filepath: str) -> dict:
    """加载JSON文件"""
    _ensure_data_dir()
    if not os.path.exists(filepath):
        return {}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"加载 {filepath} 失败: {e}")
        return {}


def _save_json(filepath: str, data: dict):
    """保存JSON文件"""
    _ensure_data_dir()
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"保存 {filepath} 失败: {e}")


def _cleanup_old_data(data: dict, days: int = RETENTION_DAYS) -> dict:
    """清理过期数据（滚动窗口）"""
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    cleaned = {}
    for key, entries in data.items():
        if isinstance(entries, list):
            cleaned[key] = [e for e in entries if e.get("timestamp", "") >= cutoff]
        else:
            cleaned[key] = entries
    return cleaned


# ============================================
# 简报条目反馈（按分类）
# ============================================

def save_briefing_feedback(
    category: str,
    entry_url: str,
    feedback: str,
    subscriber_id: str = "anonymous"
):
    """
    保存简报条目反馈
    feedback: "up" | "down"
    """
    data = _load_json(FEEDBACK_FILE)
    
    # 初始化分类结构
    if "briefing" not in data:
        data["briefing"] = {}
    if category not in data["briefing"]:
        data["briefing"][category] = {"entries": [], "summary": {"up": 0, "down": 0}}
    
    cat_data = data["briefing"][category]
    
    # 检查是否已有反馈
    existing = None
    for entry in cat_data["entries"]:
        if entry["url"] == entry_url and entry["subscriber_id"] == subscriber_id:
            existing = entry
            break
    
    if existing:
        # 更新反馈
        old_feedback = existing["feedback"]
        if old_feedback != feedback:
            cat_data["summary"][old_feedback] -= 1
            cat_data["summary"][feedback] += 1
            existing["feedback"] = feedback
            existing["timestamp"] = datetime.now().isoformat()
    else:
        # 新增反馈
        cat_data["entries"].append({
            "url": entry_url,
            "feedback": feedback,
            "subscriber_id": subscriber_id,
            "timestamp": datetime.now().isoformat()
        })
        cat_data["summary"][feedback] += 1
    
    _save_json(FEEDBACK_FILE, data)


def get_category_feedback_summary(category: str) -> Dict:
    """获取分类反馈汇总"""
    data = _load_json(FEEDBACK_FILE)
    cat_data = data.get("briefing", {}).get(category, {})
    summary = cat_data.get("summary", {"up": 0, "down": 0})
    total = summary["up"] + summary["down"]
    return {
        "up": summary["up"],
        "down": summary["down"],
        "total": total,
        "score": summary["up"] / total if total > 0 else 0.5
    }


def get_all_category_feedback() -> Dict[str, Dict]:
    """获取所有分类反馈汇总"""
    data = _load_json(FEEDBACK_FILE)
    result = {}
    for category, cat_data in data.get("briefing", {}).items():
        summary = cat_data.get("summary", {"up": 0, "down": 0})
        total = summary["up"] + summary["down"]
        result[category] = {
            "up": summary["up"],
            "down": summary["down"],
            "total": total,
            "score": summary["up"] / total if total > 0 else 0.5
        }
    return result


def get_recent_feedback(limit: int = 10) -> List[Dict]:
    """获取最近的反馈条目"""
    data = _load_json(FEEDBACK_FILE)
    all_entries = []
    
    for category, cat_data in data.get("briefing", {}).items():
        for entry in cat_data.get("entries", []):
            all_entries.append({**entry, "category": category})
    
    # 按时间排序
    all_entries.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return all_entries[:limit]


# ============================================
# 搜索结果反馈
# ============================================

def save_search_feedback(url: str, feedback: str, subscriber_id: str = "anonymous"):
    """保存搜索结果反馈"""
    data = _load_json(FEEDBACK_FILE)
    
    if "search" not in data:
        data["search"] = []
    
    # 检查是否已有反馈
    for entry in data["search"]:
        if entry["url"] == url and entry["subscriber_id"] == subscriber_id:
            entry["feedback"] = feedback
            entry["timestamp"] = datetime.now().isoformat()
            _save_json(FEEDBACK_FILE, data)
            return
    
    # 新增反馈
    data["search"].append({
        "url": url,
        "feedback": feedback,
        "subscriber_id": subscriber_id,
        "timestamp": datetime.now().isoformat()
    })
    _save_json(FEEDBACK_FILE, data)


def get_search_feedback(url: str, subscriber_id: str = "anonymous") -> Optional[str]:
    """获取搜索结果反馈"""
    data = _load_json(FEEDBACK_FILE)
    for entry in data.get("search", []):
        if entry["url"] == url and entry["subscriber_id"] == subscriber_id:
            return entry["feedback"]
    return None


# ============================================
# 用户行为追踪（简单版）
# ============================================

def track_click(url: str, source: str, subscriber_id: str = "anonymous"):
    """追踪点击行为"""
    data = _load_json(BEHAVIOR_FILE)
    
    if subscriber_id not in data:
        data[subscriber_id] = {"clicks": [], "feedback": []}
    
    data[subscriber_id]["clicks"].append({
        "url": url,
        "source": source,  # "briefing" | "search"
        "timestamp": datetime.now().isoformat()
    })
    
    _save_json(BEHAVIOR_FILE, _cleanup_old_data(data))


def track_feedback(url: str, feedback: str, source: str, subscriber_id: str = "anonymous"):
    """追踪反馈行为"""
    data = _load_json(BEHAVIOR_FILE)
    
    if subscriber_id not in data:
        data[subscriber_id] = {"clicks": [], "feedback": []}
    
    data[subscriber_id]["feedback"].append({
        "url": url,
        "feedback": feedback,
        "source": source,
        "timestamp": datetime.now().isoformat()
    })
    
    _save_json(BEHAVIOR_FILE, _cleanup_old_data(data))


def get_user_behavior(subscriber_id: str = "anonymous") -> Dict:
    """获取用户行为数据"""
    data = _load_json(BEHAVIOR_FILE)
    return data.get(subscriber_id, {"clicks": [], "feedback": []})


def get_all_users_behavior() -> Dict[str, Dict]:
    """获取所有用户行为数据"""
    return _load_json(BEHAVIOR_FILE)


# ============================================
# 统计函数（用于仪表盘）
# ============================================

def get_feedback_stats() -> Dict:
    """获取反馈统计"""
    feedback_data = _load_json(FEEDBACK_FILE)
    behavior_data = _load_json(BEHAVIOR_FILE)
    
    # 简报反馈统计
    briefing_stats = {"total_up": 0, "total_down": 0, "categories": {}}
    for category, cat_data in feedback_data.get("briefing", {}).items():
        summary = cat_data.get("summary", {"up": 0, "down": 0})
        briefing_stats["total_up"] += summary["up"]
        briefing_stats["total_down"] += summary["down"]
        briefing_stats["categories"][category] = summary
    
    # 搜索反馈统计
    search_stats = {"total": len(feedback_data.get("search", []))}
    
    # 用户活跃度
    user_count = len(behavior_data)
    total_clicks = sum(len(u.get("clicks", [])) for u in behavior_data.values())
    total_feedback = sum(len(u.get("feedback", [])) for u in behavior_data.values())
    
    return {
        "briefing": briefing_stats,
        "search": search_stats,
        "users": {
            "count": user_count,
            "total_clicks": total_clicks,
            "total_feedback": total_feedback
        }
    }


def get_top_categories(limit: int = 5) -> List[Dict]:
    """获取最受欢迎的分类"""
    stats = get_all_category_feedback()
    sorted_cats = sorted(stats.items(), key=lambda x: x[1]["up"], reverse=True)
    return [{"category": cat, **data} for cat, data in sorted_cats[:limit]]


def get_recent_feedback_with_names(limit: int = 10) -> List[Dict]:
    """获取带订阅者名称的最近反馈"""
    recent = get_recent_feedback(limit)
    try:
        from intelnexus.config.subscriptions import get_all_subscribers
        subscribers = {s["id"]: s["name"] for s in get_all_subscribers()}
    except Exception:
        subscribers = {}
    
    for entry in recent:
        entry["subscriber_name"] = subscribers.get(entry.get("subscriber_id"), "匿名")
    
    return recent
