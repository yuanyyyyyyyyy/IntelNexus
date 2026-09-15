import json
import os
import time
import hashlib
import tempfile
from datetime import datetime, timedelta

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "cache")
CACHE_TTL = 86400


def _ensure_cache_dir():
    os.makedirs(CACHE_DIR, exist_ok=True)


def _url_hash(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def _cache_path(url: str) -> str:
    return os.path.join(CACHE_DIR, f"{_url_hash(url)}.json")


def get_cached_entry(url: str) -> dict | None:
    """读取完整缓存条目（正文 + 解析出的真实地址等元数据）。

    与 get_cached 的区别：返回整个 entry 字典，供抓取层回填 resolved_url
    （包装链接的真实地址在抓取时才能得到，缓存命中后必须能读回，否则
    每次命中缓存都会丢失真实地址，去重与证据溯源永远失效）。
    """
    path = _cache_path(url)
    try:
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            entry = json.load(f)
        if time.time() > entry.get("expires_at", 0):
            os.remove(path)
            return None
        return entry
    except Exception:
        return None


def get_cached(url: str) -> str | None:
    entry = get_cached_entry(url)
    return entry.get("content") if entry else None


def set_cached(url: str, content: str, ttl: int = CACHE_TTL, resolved_url: str | None = None):
    _ensure_cache_dir()
    path = _cache_path(url)
    try:
        entry = {
            "url": url,
            "content": content,
            # 跟随重定向后得到的真实地址（包装链接如 baidu.com/link?url= 才有值）
            "resolved_url": resolved_url,
            "cached_at": time.time(),
            "expires_at": time.time() + ttl,
        }
        fd, tmp_path = tempfile.mkstemp(dir=CACHE_DIR, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(entry, f, ensure_ascii=False)
            os.replace(tmp_path, path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
    except Exception:
        pass


def clean_expired(ttl: int = CACHE_TTL) -> int:
    _ensure_cache_dir()
    now = time.time()
    count = 0
    for fname in os.listdir(CACHE_DIR):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(CACHE_DIR, fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                entry = json.load(f)
            if now > entry.get("expires_at", 0):
                os.remove(path)
                count += 1
        except Exception:
            try:
                os.remove(path)
                count += 1
            except Exception:
                pass
    return count
