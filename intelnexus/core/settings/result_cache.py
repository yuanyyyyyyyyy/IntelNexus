"""
查询级整段结果缓存
================
以 (mode, refined_query, model, threads, advanced, tor_port) 等维度为 key，
缓存整段搜索流水线的产物（results/scraped/credibility/kg/summary/evidence）。
命中时跳过所有重耗时阶段，直接渲染，首屏时间趋近 0。

底层复用文件型 TTL 缓存（与 scraper 的 cache 同目录），
避免进程重启后丢失热点查询；同时提供进程内 dict 加速重复命中。
"""

import hashlib
import json
import os
import time
import threading
from typing import Any, Dict, Optional

_RESULT_CACHE_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "result_cache")
_RESULT_TTL = int(os.getenv("INTELNEXUS_RESULT_CACHE_TTL", "3600"))

# 进程内加速层
_local_cache: Dict[str, Dict[str, Any]] = {}
_local_lock = threading.Lock()


def _ensure_dir():
    os.makedirs(_RESULT_CACHE_DIR, exist_ok=True)


def _make_key(*parts) -> str:
    raw = "|".join(str(p) for p in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _path(key: str) -> str:
    return os.path.join(_RESULT_CACHE_DIR, f"{key}.json")


def get_result(key: str, ttl: int = _RESULT_TTL) -> Optional[Dict[str, Any]]:
    """读取查询级整段结果缓存，过期返回 None。"""
    with _local_lock:
        cached = _local_cache.get(key)
        if cached is not None:
            # 进程内层不校验 TTL（由调用方控制 key 稳定性），直接返回
            return cached

    _ensure_dir()
    path = _path(key)
    try:
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            entry = json.load(f)
        if time.time() > entry.get("expires_at", 0):
            try:
                os.remove(path)
            except OSError:
                pass
            return None
        payload = entry.get("payload")
        with _local_lock:
            _local_cache[key] = payload
        return payload
    except Exception:
        return None


def set_result(key: str, payload: Dict[str, Any], ttl: int = _RESULT_TTL) -> None:
    """写入整段结果缓存（文件 + 进程内）。"""
    with _local_lock:
        _local_cache[key] = payload
    _ensure_dir()
    path = _path(key)
    entry = {
        "key": key,
        "payload": payload,
        "cached_at": time.time(),
        "expires_at": time.time() + ttl,
    }
    tmp_path = path + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(entry, f, ensure_ascii=False)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def build_key(mode: str, refined_query: str, model: str, threads: int,
              advanced_mode: bool = False, tor_port: int = 0,
              include_ts: bool = False) -> str:
    """根据流水线维度构造稳定的缓存 key（可选排除随时间变化的维度）。"""
    return _make_key(mode, refined_query, model, threads, advanced_mode, tor_port)
