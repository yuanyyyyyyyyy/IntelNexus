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


from intelnexus.config.paths import get_data_dir

SOURCES_FILE = os.path.join(get_data_dir(), "sources.json")


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


def get_sources_by_category(category: str) -> List[Dict]:
    """按类别获取数据源"""
    all_sources = get_all_sources()
    result = []
    for source_type in ["subscription_sources", "custom_sources"]:
        for source in all_sources.get(source_type, []):
            if source.get("category") == category and source.get("enabled", True):
                result.append(source)
    return result


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

    # URL 格式校验
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        logger.warning(f"URL 格式无效: {url} (必须以 http:// 或 https:// 开头)")
        return False

    # 禁止内网地址
    hostname = parsed.hostname or ""
    blocked_prefixes = ("127.", "10.", "192.168.", "169.254.", "0.")
    if hostname in ("localhost", "0.0.0.0") or any(hostname.startswith(p) for p in blocked_prefixes):
        logger.warning(f"禁止添加内网地址: {url}")
        return False

    data = safe_read_json(SOURCES_FILE)
    if not data:
        data = {"subscription_sources": [], "custom_sources": []}

    # URL 归一化去重（忽略大小写/末尾斜杠/查询串），避免同一源被重复添加后重复抓取
    from urllib.parse import urlunparse

    def _norm_url(u: str) -> str:
        p = urlparse(u or "")
        return urlunparse((p.scheme.lower(), p.netloc.lower(), (p.path or "").rstrip("/"), "", "", ""))

    norm_new = _norm_url(url)
    for existing in data.get("subscription_sources", []) + data.get("custom_sources", []):
        if _norm_url(existing.get("url", "")) == norm_new:
            logger.warning(f"重复数据源，取消添加: {url}")
            return False

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
    测试数据源是否可用（与采集链路同款网络策略）

    - 走 get_http_proxies() 代理（与 registry/scraper 一致；境外源直连会被墙）
    - 403/拦截时自动用浏览器 UA 重试一次（部分站点屏蔽非浏览器 UA）

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

    # 与采集器同款代理策略（未配置代理时为 None，行为同直连）
    try:
        from intelnexus.core.search import get_http_proxies
        proxies = get_http_proxies()
    except Exception:
        proxies = None

    header_sets = [
        {"User-Agent": "IntelNexus/1.0"},
        {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
         "Accept": "*/*"},
    ]

    def _looks_like_feed(text_head: str) -> bool:
        h = text_head[:300].lstrip().lower()
        return h.startswith("<?xml") or "<rss" in h or "<feed" in h

    last_msg = "测试失败"
    for headers in header_sets:
        try:
            start = time.time()
            resp = requests.get(source_url, timeout=timeout, headers=headers, proxies=proxies)
            elapsed = int((time.time() - start) * 1000)
            if fetch_type == "rss":
                if resp.status_code == 200 and _looks_like_feed(resp.text):
                    return {"success": True, "latency_ms": elapsed,
                            "message": f"RSS 源可用 ({elapsed}ms)"}
                if resp.status_code == 200:
                    # 内容确定不是 feed，换 UA 也无意义，直接返回
                    return {"success": False, "latency_ms": elapsed,
                            "message": "响应 200 但内容不是 RSS/Atom 格式"}
            else:
                if resp.status_code == 200:
                    return {"success": True, "latency_ms": elapsed,
                            "message": f"网页可达 ({elapsed}ms)"}
            if resp.status_code in (401, 403):
                last_msg = f"HTTP {resp.status_code}（站点拒绝访问），尝试浏览器 UA 重试…"
            else:
                last_msg = f"响应状态码 {resp.status_code}"
        except requests.Timeout:
            last_msg = f"请求超时 ({timeout}s)"
        except requests.ConnectionError:
            last_msg = "连接失败，请检查 URL 或代理配置"
        except Exception as e:
            last_msg = f"测试失败: {type(e).__name__}"

    return {"success": False, "latency_ms": 0, "message": last_msg}


def import_sources_opml(opml_content: str, category: str) -> Dict[str, int]:
    """从 OPML 内容批量导入 RSS 源（复用 add_source 的 URL 校验与去重）。

    Args:
        opml_content: OPML 文件文本（UTF-8）
        category: 归属关注点 ID

    Returns:
        {"imported": 成功数, "duplicates": 去重跳过数, "invalid": 无效条目数}
    """
    import xml.etree.ElementTree as ET

    result = {"imported": 0, "duplicates": 0, "invalid": 0}
    try:
        root = ET.fromstring(opml_content)
    except ET.ParseError as e:
        logger.warning(f"OPML 解析失败: {e}")
        result["invalid"] = -1  # -1 表示整个文件解析失败
        return result

    # 遍历所有 outline 节点，取带 xmlUrl 属性的（RSS 条目）
    for outline in root.iter("outline"):
        xml_url = (outline.get("xmlUrl") or "").strip()
        if not xml_url:
            continue
        title = (outline.get("title") or outline.get("text") or xml_url).strip()
        if add_source("rss", title[:100], xml_url, category):
            result["imported"] += 1
        else:
            # add_source 失败 = URL 非法或重复；无法精确区分时按重复计（更常见）
            result["duplicates"] += 1
    logger.info(f"OPML import: {result}")
    return result
