"""
源健康状态追踪模块
==================
为每个搜索源记录成功/失败次数、平均延迟、连续失败数，
提供自动降级（degraded/down）判定与持久化。

降级阈值：
  consecutive_failures >= DEGRADE_THRESHOLD (3) → status = "degraded"
  consecutive_failures >= DOWN_THRESHOLD   (6) → status = "down"
"""
import os
import threading
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Optional

from intelnexus.core.logger import get_logger
from intelnexus.core.settings.file_lock import safe_read_json, safe_write_json

logger = get_logger(__name__)

DEGRADE_THRESHOLD = 3
DOWN_THRESHOLD = 6
# RLock：update_health 的「读-改-写」需全程持锁，内部再调 save_health 时可重入
_health_lock = threading.RLock()

# 与 intelnexus.config.paths.get_data_dir() 同一锚点（本地计算以避免跨包导入）
HEALTH_FILE = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "data", "source_health.json"
))


@dataclass
class SourceHealth:
    source_name: str
    success_count: int = 0
    fail_count: int = 0
    consecutive_failures: int = 0
    avg_latency_ms: float = 0.0
    last_success: Optional[str] = None
    last_error: Optional[str] = None
    status: str = "healthy"  # healthy / degraded / down

    @property
    def success_rate(self) -> float:
        total = self.success_count + self.fail_count
        return self.success_count / total if total > 0 else 1.0

    def record_success(self, latency_ms: float):
        self.success_count += 1
        self.consecutive_failures = 0
        self.last_error = None
        self.last_success = datetime.now().isoformat()
        # 滑动平均
        if self.avg_latency_ms > 0:
            self.avg_latency_ms = self.avg_latency_ms * 0.7 + latency_ms * 0.3
        else:
            self.avg_latency_ms = latency_ms
        self._update_status()

    def record_failure(self, error: str = ""):
        self.fail_count += 1
        self.consecutive_failures += 1
        self.last_error = error[:200] if error else ""
        self._update_status()

    def reset(self):
        self.consecutive_failures = 0
        self.last_error = None
        self.status = "healthy"

    def _update_status(self):
        if self.consecutive_failures >= DOWN_THRESHOLD:
            self.status = "down"
        elif self.consecutive_failures >= DEGRADE_THRESHOLD:
            self.status = "degraded"
        else:
            self.status = "healthy"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "SourceHealth":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


def _ensure_health_file():
    os.makedirs(os.path.dirname(HEALTH_FILE), exist_ok=True)
    if not os.path.exists(HEALTH_FILE):
        try:
            safe_write_json(HEALTH_FILE, {"sources": {}})
        except Exception as e:
            logger.warning(f"创建 source_health.json 失败: {e}")


def _load_health_data() -> dict:
    _ensure_health_file()
    data = safe_read_json(HEALTH_FILE)
    if not isinstance(data, dict):
        return {"sources": {}}
    return data


def _save_health_data(data: dict) -> bool:
    try:
        return safe_write_json(HEALTH_FILE, data)
    except Exception as e:
        logger.warning(f"保存 source_health.json 失败: {e}")
        return False


def get_health(source_name: str) -> SourceHealth:
    data = _load_health_data()
    sources = data.get("sources", {})
    if source_name in sources:
        return SourceHealth.from_dict(sources[source_name])
    return SourceHealth(source_name=source_name)


def save_health(health: SourceHealth) -> bool:
    with _health_lock:
        data = _load_health_data()
        data.setdefault("sources", {})[health.source_name] = health.to_dict()
        data["updated_at"] = datetime.now().isoformat()
        return _save_health_data(data)


def get_all_health() -> List[SourceHealth]:
    data = _load_health_data()
    sources = data.get("sources", {})
    return [SourceHealth.from_dict(v) for v in sources.values()]


def update_health(source_name: str, result_count: int, latency_ms: float,
                  error: Optional[str] = None):
    """统一更新入口：成功时 result_count > 0，失败时 error 非 None。

    读-改-写全程持锁（RLock 允许内部 save_health 重入），
    否则并发源线程会互相覆盖计数。
    """
    with _health_lock:
        health = get_health(source_name)
        if error is not None:
            health.record_failure(error)
        else:
            health.record_success(latency_ms)
        save_health(health)
