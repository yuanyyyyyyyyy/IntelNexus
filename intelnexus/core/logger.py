"""
统一日志模块
============
提供全项目一致的日志配置，替代分散的 print() 调用。
"""

import logging
import sys
import time
import threading


class _DedupFilter(logging.Filter):
    """去重过滤器：_DEDUP_WINDOW 秒内完全相同的日志消息只输出一次。

    简报采集以 max_workers=3 并发执行 3 个类目的搜索，
    每个类目独立调用 registry.collect()，导致 "源 X 状态为 down"、
    "全局超时"、"宽限期超时" 等同质消息被输出 3 次。
    本过滤器在 handler 层统一去重，所有模块共享同一缓存。
    """
    _window = 5.0  # 秒
    _cache: dict = {}          # msg → timestamp
    _lock = threading.Lock()

    def filter(self, record: logging.LogRecord) -> bool:
        now = time.time()
        msg = record.getMessage()
        with self._lock:
            # 清理过期条目
            expired = [k for k, t in self._cache.items()
                       if now - t > self._window]
            for k in expired:
                del self._cache[k]
            # 判断重复
            if msg in self._cache:
                return False
            self._cache[msg] = now
        return True


# 全局共享实例——所有 handler 复用同一缓存，保证跨 logger 去重口径一致
_dedup_filter = _DedupFilter()


def get_logger(name: str) -> logging.Logger:
    """
    获取一个配置好的 logger 实例。

    Args:
        name: logger 名称，通常传 __name__

    Returns:
        配置好格式和级别的 Logger
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "[%(asctime)s %(levelname)s %(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        handler.addFilter(_dedup_filter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    return logger
