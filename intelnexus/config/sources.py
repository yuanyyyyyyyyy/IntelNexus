"""
数据源配置管理模块
=================
管理AI简报的数据源（RSS订阅源、自定义网页等）
"""

import os
from typing import Dict, List, Optional
from pathlib import Path
from datetime import datetime

from intelnexus.core.logger import get_logger
from intelnexus.core.settings.file_lock import safe_read_json, safe_write_json

logger = get_logger(__name__)


SOURCES_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "sources.json")


def _ensure_sources_file():
    """确保数据源配置文件存在"""
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)

    if not os.path.exists(SOURCES_FILE):
        initial_data = {
            "subscription_sources": [],
            "custom_sources": []
        }
        safe_write_json(SOURCES_FILE, initial_data)


def get_all_sources() -> Dict[str, List[Dict]]:
    """获取所有数据源"""
    _ensure_sources_file()
    data = safe_read_json(SOURCES_FILE)
    if not data:
        return {"subscription_sources": [], "custom_sources": []}
    return data


def add_source(source_type: str, name: str, url: str, category: str,
               fetch_type: str = None) -> bool:
    """
    添加数据源

    Args:
        source_type: 数据源类型（rss或web）
        name: 数据源名称
        url: 数据源URL
        category: 分类（简报业务类，如 ai_gov_usage；搜索源类别由 fetch_type 决定）
        fetch_type: 抓取方式（rss / web_engine / onion）。为 None 时按 source_type 推断：
                    rss -> rss，web -> web_engine。

    Returns:
        bool: 是否添加成功
    """
    _ensure_sources_file()

    if not name or not url:
        return False

    data = safe_read_json(SOURCES_FILE)
    if not data:
        data = {"subscription_sources": [], "custom_sources": []}

    # fetch_type 推断：rss 源用 rss，web 源默认 web_engine
    if fetch_type is None:
        fetch_type = "rss" if source_type == "rss" else "web_engine"

    new_source = {
        "id": f"src_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
        "name": name,
        "url": url,
        "type": source_type,
        "category": category,
        "enabled": True,
        "fetch_type": fetch_type,
        "added_at": datetime.now().isoformat()
    }

    if source_type == "rss":
        data.setdefault("subscription_sources", []).append(new_source)
    else:
        data.setdefault("custom_sources", []).append(new_source)

    return safe_write_json(SOURCES_FILE, data)


def remove_source(source_id: str) -> bool:
    """
    删除数据源

    Args:
        source_id: 数据源ID

    Returns:
        bool: 是否删除成功
    """
    _ensure_sources_file()

    data = safe_read_json(SOURCES_FILE)
    if not data:
        return False

    found = False
    for source_type in ["subscription_sources", "custom_sources"]:
        original_len = len(data.get(source_type, []))
        data[source_type] = [s for s in data.get(source_type, []) if s["id"] != source_id]
        if len(data[source_type]) < original_len:
            found = True
            break

    if not found:
        return False

    return safe_write_json(SOURCES_FILE, data)


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

    data = safe_read_json(SOURCES_FILE)
    if not data:
        return False

    found = False
    for source_type in ["subscription_sources", "custom_sources"]:
        for source in data.get(source_type, []):
            if source["id"] == source_id:
                source.update(updates)
                found = True
                break
        if found:
            break

    if not found:
        return False

    return safe_write_json(SOURCES_FILE, data)


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


def test_source(source_url: str, fetch_type: str = "web_engine", timeout: int = 10) -> Dict:
    """
    测试数据源是否可用

    Args:
        source_url: 数据源URL
        fetch_type: 抓取方式 (rss / web_engine)
        timeout: 超时时间(秒)

    Returns:
        dict: {"success": bool, "latency_ms": int, "message": str}
    """
    import time
    import requests
    from urllib.parse import urlparse

    # URL 格式校验
    parsed = urlparse(source_url)
    if parsed.scheme not in ("http", "https"):
        return {"success": False, "latency_ms": 0, "message": "URL 必须以 http:// 或 https:// 开头"}

    # 禁止内网地址
    hostname = parsed.hostname or ""
    blocked_prefixes = ("127.", "10.", "192.168.", "169.254.", "0.")
    if hostname in ("localhost", "0.0.0.0") or any(hostname.startswith(p) for p in blocked_prefixes):
        return {"success": False, "latency_ms": 0, "message": "禁止访问内网地址"}

    try:
        start = time.time()
        if fetch_type == "rss":
            resp = requests.get(source_url, timeout=timeout, headers={"User-Agent": "IntelNexus/1.0"})
            elapsed = int((time.time() - start) * 1000)
            if resp.status_code == 200 and ("<?xml" in resp.text[:200] or "<rss" in resp.text[:200] or "<feed" in resp.text[:200]):
                return {"success": True, "latency_ms": elapsed, "message": f"RSS 源可用 ({elapsed}ms)"}
            else:
                return {"success": False, "latency_ms": elapsed, "message": f"响应状态码 {resp.status_code}，或内容非 RSS 格式"}
        else:
            resp = requests.get(source_url, timeout=timeout, headers={"User-Agent": "IntelNexus/1.0"})
            elapsed = int((time.time() - start) * 1000)
            if resp.status_code == 200:
                return {"success": True, "latency_ms": elapsed, "message": f"网页可达 ({elapsed}ms)"}
            else:
                return {"success": False, "latency_ms": elapsed, "message": f"响应状态码 {resp.status_code}"}
    except requests.Timeout:
        return {"success": False, "latency_ms": timeout * 1000, "message": f"请求超时 ({timeout}s)"}
    except requests.ConnectionError:
        return {"success": False, "latency_ms": 0, "message": "连接失败，请检查 URL"}
    except Exception as e:
        return {"success": False, "latency_ms": 0, "message": f"测试失败: {type(e).__name__}"}
