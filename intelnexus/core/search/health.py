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
    """统一更新入口：error 非 None 记失败；否则按是否返回结果分级。

    修复：result_count == 0 且无 error（源连通但本次查询无结果，如暗网开关开、
    Tor 未连时返回空列表）不再计入 success——旧语义让 DarkWeb 在 Tor 未连接
    时也能刷出 200+ 次"100% 成功"，健康面板失真。

    读-改-写全程持锁（RLock 允许内部 save_health 重入），
    否则并发源线程会互相覆盖计数。
    """
    with _health_lock:
        health = get_health(source_name)
        if error is not None:
            health.record_failure(error)
        elif result_count > 0:
            health.record_success(latency_ms)
        else:
            # 连通但零结果：不计成功也不计失败，仅滑动更新延迟观测
            if latency_ms > 0 and health.avg_latency_ms > 0:
                health.avg_latency_ms = health.avg_latency_ms * 0.7 + latency_ms * 0.3
        save_health(health)


def record_probe_result(source_name: str, success: bool, latency_ms: float,
                        error: Optional[str] = None):
    """记录一次主动连通性探测（如数据源管理面板的批量测试）结果。

    与 update_health 的差异：探测是用户主动发起的连通性结论，不是被动
    采集的旁路观测，因此失败时绕过被动积累（攒满 3 次才 degraded），
    单次探测失败立即降级。

    探测失败置 "degraded" 而非 "down"，down 仅由被动连续失败阈值产生：
    - registry.get_sources_by_mode() 会跳过 status=="down" 的源，一次用户点击遇到
      瞬时网络抖动即会把源从搜索管线整体剔除，且被剔除后无自愈路径；
    - 状态经 _update_status() 统一推导（与 record_failure 同一推导路径），保证探测与
      被动失败的后续状态演化自洽（不会一次被动失败就翻回 healthy）。

    - 成功：record_success（累计 success_count、滑动平均延迟、刷新
      last_success、清零 consecutive_failures、status 恢复 healthy）；
    - 失败：fail_count +1、consecutive_failures 抬升至至少 DEGRADE_THRESHOLD、
      但封顶于 DOWN_THRESHOLD - 1（被动失败已累计到 5 时，一次探测失败不得把源
      推入 down——与「探测失败置 degraded 而非 down」语义一致）、
      更新 last_error（截断 200），_update_status() 推导为 degraded，
      last_success 保持不变。
    两种路径均 save_health 落盘。全程持锁；全异常兜底（只记日志不抛出）。
    """
    try:
        with _health_lock:
            health = get_health(source_name)
            if success:
                health.record_success(latency_ms)
            else:
                health.fail_count += 1
                # 封顶到阈值下沿：探测失败最多推到 degraded，绝不一步到 down；
                # 否则被动失败已累计到 5 时，一次探测失败即抬到 6 → 推导为 down，
                # 与 docstring「探测失败置 degraded 而非 down」矛盾。
                health.consecutive_failures = min(
                    max(health.consecutive_failures + 1, DEGRADE_THRESHOLD),
                    DOWN_THRESHOLD - 1)
                health.last_error = (error or "")[:200]
                health._update_status()
            save_health(health)
    except Exception as e:
        logger.warning(f"记录探测结果失败 [{source_name}]: {e}")


def purge_stale_entries(active_source_names) -> int:
    """清理健康表中不属于任何当前注册源的残留条目。

    测试运行（src0/verify_src*/OkSrc 等）和已删除用户源会在持久化表里留下
    永久条目，UI 数据源状态面板会把它们当真实源展示——失真。
    返回清除的条目数。
    """
    with _health_lock:
        data = _load_health_data()
        sources = data.get("sources", {})
        active = set(active_source_names)
        stale = [n for n in sources if n not in active]
        for n in stale:
            sources.pop(n, None)
        if stale:
            data["sources"] = sources
            safe_write_json(HEALTH_FILE, data)
        return len(stale)