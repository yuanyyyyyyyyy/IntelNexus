"""
源健康状态追踪模块
==================
为每个搜索源记录成功/失败次数、平均延迟、连续失败数，
提供自动降级（degraded/down）判定与持久化。

降级阈值：
  consecutive_failures >= DEGRADE_THRESHOLD (3) → status = "degraded"
  consecutive_failures >= DOWN_THRESHOLD   (6) → status = "down"

时间维度（为什么 status 之外还需要 view_status）
-----------------------------------------------
``status`` 是**纯计数**推导出来的持久化结论，没有时间概念，于是有两个后果：

1. **down 是终态死锁**。``registry.get_sources_by_mode()`` 会剔除 down 源，
   被剔除 → 永不执行 → 永不成功 → ``consecutive_failures`` 永不下降 → 永远 down。
   数据侧唯一出口是用户手动点「清除标记」，而该按钮埋在简报中心设置区。
   实测真实健康表里 arXiv / HuggingFace / AlienVault_OTX / CNVD 四个源
   ``streak=6``、``last_success=None``，已处于该状态。
2. **degraded 会冻结**。只在特定 mode 下运行的源，若该 mode 长期不被使用，
   失败链既不增长也不衰减，界面永久显示「降级」——即使故障早已恢复。

因此引入 ``last_attempt``（最后一次**实际观测**的时间）与派生状态
``view_status()``：失败信号超过 ``STALE_AFTER_HOURS`` 无任何观测即转为
``stale``（待复核），down 源冷却 ``DOWN_COOLDOWN_MINUTES`` 后同样转为
``stale`` 并重新放行——用一次真实检索来证伪旧结论，而不是让旧结论永久生效。

``status`` 仍是唯一持久化字段（数据契约不变），``stale`` 只在读取时派生、
不落盘，因此不存在「stale 被写进文件后再也回不去」的问题。
"""
import os
import threading
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Dict, Iterable, List, Optional

from intelnexus.core.logger import get_logger
from intelnexus.core.settings.file_lock import (
    read_for_update, safe_read_json, safe_write_json,
)

logger = get_logger(__name__)

DEGRADE_THRESHOLD = 3
DOWN_THRESHOLD = 6

#: 失败信号有效期（小时）：超过该时长没有任何观测，旧的 degraded/down 判定
#: 视为过期 → 派生为 stale，并在下次检索时重新放行。
STALE_AFTER_HOURS = 24

#: down 源冷却时长（分钟）：冷却到期前按原判定剔除，到期后按 stale 放行重试。
#: 必须显著小于 STALE_AFTER_HOURS——它服务的是「快速自愈」，而不是「过期」。
DOWN_COOLDOWN_MINUTES = 30

#: 持久化状态（写入 status 字段的合法取值）
STORED_STATUSES = ("healthy", "degraded", "down")

#: 派生状态（view_status 的返回域）：在持久化状态之上多一个 stale
VIEW_STATUSES = STORED_STATUSES + ("stale",)
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
    status: str = "healthy"  # healthy / degraded / down（持久化状态）
    #: 最后一次**实际观测**的时间（成功、失败、连通但零结果都算观测）。
    #: 与 last_success 的区别：后者只在成功时刷新，因此无法回答
    #: 「这个源的失败判定是多久以前得出的」——而这正是判断信号是否过期的依据。
    last_attempt: Optional[str] = None

    @property
    def success_rate(self) -> float:
        total = self.success_count + self.fail_count
        return self.success_count / total if total > 0 else 1.0

    def record_success(self, latency_ms: float):
        self.success_count += 1
        self.consecutive_failures = 0
        self.last_error = None
        self.last_success = datetime.now().isoformat()
        self.last_attempt = self.last_success
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
        self.last_attempt = datetime.now().isoformat()
        self._update_status()

    def note_observation(self, latency_ms: float = 0.0):
        """记录一次「连通但零结果」的观测：刷新时间戳，不改失败链。

        零结果既不是成功也不是失败（源可能只是本次查询没命中），所以
        ``success_count`` / ``consecutive_failures`` 都不动；但**必须**刷新
        ``last_attempt``——否则该源会被判为「信号过期」而反复转为 stale，
        实际上我们刚刚才观测过它。
        """
        self.last_attempt = datetime.now().isoformat()
        if latency_ms > 0 and self.avg_latency_ms > 0:
            self.avg_latency_ms = self.avg_latency_ms * 0.7 + latency_ms * 0.3

    def reset(self):
        """手动解除降级：清零失败链与全部历史计数，回到全新起点。

        不只清零 ``consecutive_failures`` / ``last_error``，还一并清零
        ``success_count``、``fail_count``、``avg_latency_ms``、``last_success``：
        否则重置后 ``status`` 已是 healthy，``success_rate`` 却仍反映旧失败
        （如 33%），出现「绿色正常却低成功率」的矛盾展示。

        不含任何网络探测——仅清除陈旧信号，下次实际检索失败仍会重新降级。
        """
        self.consecutive_failures = 0
        self.last_error = None
        self.status = "healthy"
        self.success_count = 0
        self.fail_count = 0
        self.avg_latency_ms = 0.0
        self.last_success = None
        self.last_attempt = None

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


# ---------------------------------------------------------------------------
# 时间维度派生（纯函数：只读、不落盘、可注入 now 便于测试）
# ---------------------------------------------------------------------------

def _parse_ts(value) -> Optional[datetime]:
    """ISO 时间戳 → datetime；缺失/不可解析返回 None。"""
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def signal_age(entry, now: Optional[datetime] = None) -> Optional[timedelta]:
    """距离最后一次观测的时长。

    优先 ``last_attempt``（任意观测），退化到 ``last_success``——旧版健康表
    没有 ``last_attempt`` 字段，``last_success`` 是唯一可用的时间锚点。
    两者都没有时返回 None：**无法证明判定仍然有效**，由 ``view_status``
    决定按「待复核」处理。时钟回拨（负值）按 0 处理，不产生「-3 天前」。
    """
    ts = (_parse_ts(getattr(entry, "last_attempt", None))
          or _parse_ts(getattr(entry, "last_success", None)))
    if ts is None:
        return None
    delta = (now or datetime.now()) - ts
    return delta if delta.total_seconds() >= 0 else timedelta(0)


def view_status(entry, now: Optional[datetime] = None) -> str:
    """派生状态：在持久化 ``status`` 之上叠加时间维度。

    返回 healthy / degraded / down / **stale**。

    规则（按优先级）：
    1. ``healthy`` 直接返回——健康的源不需要复核，过期也无害。
    2. 无任何时间戳（历史条目、手写 JSON）→ ``stale``。没有时间锚点就无法
       证明「6 次失败」是刚刚发生还是上个月发生的，保守按待复核处理，
       让它在下次检索被真实重试一次，而不是永久跳过。
    3. 距今超过 ``STALE_AFTER_HOURS`` → ``stale``（失败信号已过期）。
    4. 状态为 ``down`` 且已过 ``DOWN_COOLDOWN_MINUTES`` → ``stale``
       （熔断冷却到期，放行半开重试）。
    5. 其余保持原状态。

    ``stale`` 不写盘，只影响读取侧的展示与调度判定：展示为「待复核」，
    调度上按最低优先级放行（见 ``registry.get_sources_by_mode``）。
    """
    status = getattr(entry, "status", None)
    if status not in STORED_STATUSES:
        # 与 ui.health_view 的历史兜底一致：损坏的条目按「降级」处理，
        # 既不静默绿灯，也不宣称已被检索剔除（那是 down 的语义）
        return "degraded"
    if status == "healthy":
        return "healthy"

    age = signal_age(entry, now)
    if age is None:
        return "stale"
    if age >= timedelta(hours=STALE_AFTER_HOURS):
        return "stale"
    if status == "down" and age >= timedelta(minutes=DOWN_COOLDOWN_MINUTES):
        return "stale"
    return status


def is_retryable(entry, now: Optional[datetime] = None) -> bool:
    """该源本次检索是否应被放行（仅处于冷却期内的 down 会被拦下）。"""
    return view_status(entry, now) != "down"


def _ensure_health_file():
    os.makedirs(os.path.dirname(HEALTH_FILE), exist_ok=True)
    if not os.path.exists(HEALTH_FILE):
        try:
            safe_write_json(HEALTH_FILE, {"sources": {}})
        except Exception as e:
            logger.warning(f"创建 source_health.json 失败: {e}")


def _load_health_data(strict: bool = False):
    """读取健康表。

    ``strict=True`` 专供读-改-写路径（update_health / apply_health_updates）：
    读取失败时返回 ``None``，调用方必须放弃写回。健康表是检索线程每次写入的
    热点文件，读竞争真实存在；若把失败当成空表继续写，会把其它源的统计全部抹掉。
    只读路径（get_health / get_all_health / get_health_map）不传 strict。

    Returns:
        dict 正常；None 表示读取失败（仅 strict=True）
    """
    _ensure_health_file()
    if strict:
        data = read_for_update(HEALTH_FILE)
        if data is None:
            return None
        return data if isinstance(data, dict) else {"sources": {}}
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


def get_health_map(source_names: Optional[Iterable[str]] = None) -> Dict[str, SourceHealth]:
    """批量读取健康表：**一次**磁盘读取返回 ``{源名: SourceHealth}``。

    取代「对每个源各调一次 ``get_health()``」的 N 次 IO。实测 22 个源时
    ``get_health`` 循环 33.5ms/轮 vs 本函数 1.5ms/轮（约 22 倍），
    而 ``get_sources_by_mode`` 在**每次检索**前都要跑一遍。

    Args:
        source_names: 需要查询的源名；``None`` 表示返回表中全部条目。
            不存在的源名按「全新条目」补齐（与 ``get_health`` 语义一致），
            调用方无需再判空。
    """
    data = _load_health_data()
    sources = data.get("sources", {})
    if not isinstance(sources, dict):
        sources = {}

    if source_names is None:
        out: Dict[str, SourceHealth] = {}
        for name, raw in sources.items():
            health = SourceHealth.from_dict(raw) if isinstance(raw, dict) else SourceHealth(source_name=name)
            # 文件里 source_name 与键不一致（手改/迁移残留）时以键为准
            health.source_name = name
            out[name] = health
        return out

    out = {}
    for name in source_names:
        raw = sources.get(name)
        health = SourceHealth.from_dict(raw) if isinstance(raw, dict) else SourceHealth(source_name=name)
        health.source_name = name
        out[name] = health
    return out


def _apply_observation(health: "SourceHealth", result_count: int, latency_ms: float,
                       error: Optional[str], empty_is_healthy: bool) -> None:
    """把一次观测施加到条目上（单条与批量两条路径共用的唯一判定逻辑）。"""
    if error is not None:
        health.record_failure(error)
    elif result_count > 0:
        health.record_success(latency_ms)
    elif empty_is_healthy:
        # 源自述「空结果＝未命中」：按成功计，使故障恢复后能自愈回 healthy
        health.record_success(latency_ms)
    else:
        # 连通但零结果：不计成功也不计失败，只刷新观测时间与延迟。
        # 必须刷新 last_attempt，否则刚观测过的源会被误判为「信号过期」。
        health.note_observation(latency_ms)


def update_health(source_name: str, result_count: int, latency_ms: float,
                  error: Optional[str] = None, empty_is_healthy: bool = False):
    """统一更新入口：error 非 None 记失败；否则按是否返回结果分级。

    修复：result_count == 0 且无 error（源连通但本次查询无结果，如暗网开关开、
    Tor 未连时返回空列表）不再计入 success——旧语义让 DarkWeb 在 Tor 未连接
    时也能刷出 200+ 次"100% 成功"，健康面板失真。

    ``empty_is_healthy``（默认 False）：由源**自述**「零结果是否等于健康」。
    - False（默认，既有语义）：零结果既不计成功也不计失败，保住上面 DarkWeb
      的修复不被推翻；
    - True：零结果按成功计（清零连续失败）。适用于明确知道「空列表＝查询未命中、
      而非静默故障」的源（如站内检索源 ``SiteScopedSource``）——否则召回天然偏低
      的源连续几次未命中后，``consecutive_failures`` 永不下降，会被永久钉在
      degraded，攒到阈值 6 转 down 后还会被停止投递、彻底失去自愈路径。

    性能：整个读-改-写在**一次** ``_load_health_data`` + 一次 ``_save_health_data``
    内完成（旧实现经 ``get_health`` + ``save_health``，同一份文件被读两遍）。

    但单条更新仍有约 10ms 的**固定**开销（文件锁 + 临时文件 + 原子重命名），
    与文件大小几乎无关（实测 4.8KB 10.05ms / 63.5KB 13.58ms）。因此一次检索
    里 15 个源各更新一次就是 150ms 的串行 IO——检索路径应改用
    ``HealthBatch`` 合并成一次写盘，本函数只服务单点更新（UI 按钮、探测）。

    锁：读-改-写全程持锁，否则并发源线程会互相覆盖计数。
    """
    with _health_lock:
        data = _load_health_data(strict=True)
        if data is None:
            # 读失败绝不能按空表写回：会把其它所有源的统计抹掉
            logger.warning(f"读取 source_health.json 失败，放弃更新 {source_name} 的健康观测")
            return False
        sources = data.setdefault("sources", {})
        raw = sources.get(source_name)
        health = SourceHealth.from_dict(raw) if isinstance(raw, dict) else SourceHealth(source_name=source_name)
        health.source_name = source_name

        _apply_observation(health, result_count, latency_ms, error, empty_is_healthy)

        sources[source_name] = health.to_dict()
        data["updated_at"] = datetime.now().isoformat()
        _save_health_data(data)


def apply_health_updates(updates) -> int:
    """把一批观测合并成**一次**读-改-写，返回实际写入的条目数。

    ``updates`` 为 ``(source_name, result_count, latency_ms, error,
    empty_is_healthy)`` 五元组的可迭代对象。

    为什么需要它：单条 ``update_health`` 约 10ms，且这 10ms 几乎全是固定开销
    （见该函数 docstring 的实测）。一次检索 15 个源就是 150ms 串行 IO，
    100 个源就是 1.2s——**问题不在文件格式，在写次数**。合并后一次检索只写一次。

    异常兜底：写盘失败只记日志，绝不向上抛——健康统计失败不该让整次检索失败。
    """
    items = list(updates or ())
    if not items:
        return 0
    try:
        with _health_lock:
            data = _load_health_data(strict=True)
            if data is None:
                # 读失败时按空表写回会把所有源的统计清零，比丢这一批观测严重得多
                logger.warning(f"读取 source_health.json 失败，放弃本批 {len(items)} 条健康观测")
                return 0
            sources = data.setdefault("sources", {})
            for name, result_count, latency_ms, error, empty_is_healthy in items:
                raw = sources.get(name)
                health = SourceHealth.from_dict(raw) if isinstance(raw, dict) else SourceHealth(source_name=name)
                health.source_name = name
                _apply_observation(health, result_count, latency_ms, error, empty_is_healthy)
                sources[name] = health.to_dict()
            data["updated_at"] = datetime.now().isoformat()
            if not _save_health_data(data):
                logger.warning(f"批量写入健康状态失败（{len(items)} 条）")
                return 0
            return len(items)
    except Exception as e:
        logger.warning(f"批量写入健康状态异常: {e}")
        return 0


class HealthBatch:
    """一次检索的观测缓冲：正常路径合并成一次写盘，迟到线程退回单条写。

    为什么需要「迟到线程」兜底：``collect()`` 在全局超时后会
    ``shutdown(wait=False, cancel_futures=True)``，被放弃的源线程仍会在稍后
    完成并调用记录入口。若缓冲已 flush 就丢弃，那条失败信号就永远丢了。
    因此 ``record()`` 在关闭后返回 False，调用方退回 ``update_health`` 单条写。

    线程安全：``record()`` 会被多个源线程并发调用。
    """

    __slots__ = ("_items", "_lock", "_closed")

    def __init__(self):
        self._items: List[tuple] = []
        self._lock = threading.Lock()
        self._closed = False

    def record(self, source_name: str, result_count: int, latency_ms: float,
               error: Optional[str] = None, empty_is_healthy: bool = False) -> bool:
        """缓冲一条观测；缓冲已关闭时返回 False（调用方应回退为单条写）。"""
        with self._lock:
            if self._closed:
                return False
            self._items.append((source_name, result_count, latency_ms,
                                error, empty_is_healthy))
            return True

    @property
    def pending(self) -> int:
        with self._lock:
            return len(self._items)

    def flush(self) -> int:
        """关闭缓冲并一次性写盘；重复调用返回 0（幂等）。"""
        with self._lock:
            self._closed = True
            items, self._items = self._items, []
        return apply_health_updates(items)



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
                # 探测是一次真实观测：必须刷新 last_attempt，否则用户刚点完
                # 批量测试，面板仍可能因「信号过期」把它显示成待复核。
                health.last_attempt = datetime.now().isoformat()
                health._update_status()
            save_health(health)
    except Exception as e:
        logger.warning(f"记录探测结果失败 [{source_name}]: {e}")


def mark_for_retry(source_name: str) -> bool:
    """让 ``down`` 源**立即**具备重试资格，不等冷却到期。

    只清 ``last_attempt``，不碰任何计数，因此语义精确：
    - ``view_status`` 因缺少时间锚点派生为 ``stale`` → 下次检索立刻放行；
    - 若仍然失败，``record_failure`` 会盖上新的时间戳，状态立刻回到 ``down``
      并重新开始冷却——不会因为点过按钮就变成「假绿灯」。

    与 ``reset()`` 的区别：后者清零全部历史统计（等于宣称「一切重新开始」），
    适合「配置已修好」；本函数只表达「现在就再试一次」，统计保持原样。
    """
    try:
        with _health_lock:
            data = _load_health_data()
            sources = data.get("sources", {})
            raw = sources.get(source_name)
            if not isinstance(raw, dict):
                return False
            health = SourceHealth.from_dict(raw)
            health.last_attempt = None
            sources[source_name] = health.to_dict()
            data["sources"] = sources
            data["updated_at"] = datetime.now().isoformat()
            return _save_health_data(data)
    except Exception as e:
        logger.warning(f"标记立即重试失败 [{source_name}]: {e}")
        return False


def reset_health_for(source_names) -> int:
    """按源名批量重置健康条目并落盘，返回实际重置的条数。

    用于「用户已修好配置」的场景（如保存站内检索 Key、重新启用某源）：此时历史
    失败已成**陈旧信号**，继续挂着会让源在下次检索前就被判定为 degraded/down。

    只重置**已存在**的条目，不凭空创建——健康面板会渲染表里所有条目，为不存在的
    源造条目等于制造僵尸行。
    """
    names = {n for n in (source_names or ()) if n}
    if not names:
        return 0
    try:
        with _health_lock:
            data = _load_health_data()
            sources = data.get("sources", {})
            reset = 0
            for name in names:
                if name not in sources:
                    continue
                health = SourceHealth.from_dict(sources[name])
                health.reset()
                sources[name] = health.to_dict()
                reset += 1
            if reset:
                data["sources"] = sources
                data["updated_at"] = datetime.now().isoformat()
                # 写盘失败必须让调用方知道：返回 0 使其能提示用户，而不是
                # 「明明重置了却仍是降级」且无任何反馈
                if not _save_health_data(data):
                    logger.error("批量重置健康状态失败：写盘未成功")
                    return 0
            return reset
    except Exception as e:
        logger.warning(f"批量重置健康状态失败: {e}")
        return 0


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