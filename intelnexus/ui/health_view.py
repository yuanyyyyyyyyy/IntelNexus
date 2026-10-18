"""源健康视图数据层（单一口径）
================================
侧边栏「数据源状态」与简报中心「源健康检查」共用同一份数据与同一套推导，
避免两处各算一套导致「卡片说 12 个正常、下面只列出 9 行」。

本模块**不 import streamlit**：只做过滤 / 排序 / 计数 / 格式化，
便于直接单测；渲染留在 ``ui.health_dashboard``。

状态取值（4 个，由 ``health.view_status`` 统一派生）
--------------------------------------------------
``down`` → ``degraded`` → ``stale`` → ``healthy``（严重度降序）

``stale``（待复核）是本轮新增：持久化的 ``status`` 只有 healthy/degraded/down，
没有时间概念，导致「只在特定 mode 下运行的源」一旦降级就永久冻结在降级，
而 ``down`` 更会因为被检索管线剔除而永远无法自愈。``view_status`` 叠加
``last_attempt`` 后，过期信号转为 ``stale``——语义是「这个结论太旧了，
下次检索会重试，别当成已确认的故障」。

审计修掉的三处口径问题
----------------------
1. **汇总与明细不同源**：旧实现汇总走 ``get_health_summary_cached()``
   （15s 缓存、不按注册表过滤），明细走 ``get_all_health()``（实时、过滤
   active_names）。僵尸条目存在时两者对不上。现在汇总由 ``build_snapshot``
   从**过滤后的同一批 entries** 推导，卡片数恒等于明细行数。
2. **两处排序不同**：侧边栏按 JSON 插入序、简报中心按严重度。现在统一
   ``down → degraded → stale → healthy``，同级按名称字典序，保证两处顺序一致。
3. **重置后的假绿灯**：``reset()`` 会清零全部计数，``success_rate`` 因此回到
   100%（无样本时定义为 1.0），界面显示「正常 / 100% / -」，比重置前更像
   一切正常。``format_rate`` 在**无样本**时返回 "—" 而非 100%，让「没有数据」
   和「全部成功」在视觉上区分开。
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List, Optional, Sequence, Tuple

from intelnexus.core.search.health import view_status as _view_status

#: 严重度排序：问题越严重越靠前
SEVERITY_ORDER = {"down": 0, "degraded": 1, "stale": 2, "healthy": 3}

#: 需要用户关注的三种状态（stale 也需要：它代表「结论已过期、待复核」）
PROBLEM_STATUSES = ("down", "degraded", "stale")

#: 状态 → 既有 ``status-dot`` 修饰类（首页点阵 / 侧边栏 / 明细表共用）
STATUS_DOT_CLASS = {
    "healthy": "active",
    "degraded": "warning",
    "down": "error",
    "stale": "muted",
}

#: 状态字段缺失/取值异常时的兜底：按「降级」处理
#: —— 既不静默显示绿灯（掩盖损坏的条目），也不宣称已被检索剔除（那是 down 的语义）
_FALLBACK_STATUS = "degraded"


def status_of(entry) -> str:
    """取条目状态（含时间维度派生）：healthy / degraded / down / stale。

    委托 ``health.view_status``——状态推导只能有一处定义，否则 UI 与检索管线
    会各算一套（旧版两处面板各写一套排序与计数，就是这么漂移的）。
    """
    return _view_status(entry)


@dataclass
class HealthSnapshot:
    """一次读取得到的健康快照（过滤 + 排序后的唯一样本）。"""

    entries: List[object]
    summary: dict
    #: 注册表中的活跃源名集合；None 表示注册表不可用（跳过过滤，不静默整个面板）
    active_names: Optional[set] = None
    #: 被白名单过滤掉的条目数（僵尸条目 / 已删除源）
    dropped: int = 0

    @property
    def problems(self) -> List[object]:
        """仅降级/不可用的条目（侧边栏默认只展示这些）。"""
        return [e for e in self.entries if status_of(e) in PROBLEM_STATUSES]

    @property
    def healthy(self) -> List[object]:
        return [e for e in self.entries if status_of(e) == "healthy"]

    @property
    def all_ok(self) -> bool:
        """有数据且全部正常（用于侧边栏标题「全部正常」）。"""
        return bool(self.entries) and not self.problems

    @property
    def is_empty(self) -> bool:
        return not self.entries


def build_snapshot(entries: Optional[Iterable], active_names: Optional[Iterable] = None) -> HealthSnapshot:
    """把健康表原始条目整理成快照。

    Args:
        entries: ``get_all_health()`` 的返回值（SourceHealth 列表）。
        active_names: 注册表中的活跃源名；``None`` 表示注册表不可用，
            **跳过过滤**——宁可多显示几行，也不要把整个面板静默成空。

    Returns:
        HealthSnapshot：entries 已过滤并排序，summary 由 entries 自身推导，
        因此 ``summary["total"] == len(entries)`` 恒成立。
    """
    active = set(active_names) if active_names is not None else None
    kept: List[object] = []
    dropped = 0
    for entry in entries or ():
        name = getattr(entry, "source_name", None)
        if active is not None and name not in active:
            dropped += 1
            continue
        kept.append(entry)

    kept.sort(key=lambda e: (
        SEVERITY_ORDER.get(status_of(e), SEVERITY_ORDER[_FALLBACK_STATUS]),
        (getattr(e, "source_name", "") or "").lower(),
    ))

    summary = {"healthy": 0, "degraded": 0, "down": 0, "stale": 0, "total": len(kept)}
    for entry in kept:
        status = status_of(entry)
        if status in summary:
            summary[status] += 1
    return HealthSnapshot(entries=kept, summary=summary,
                          active_names=active, dropped=dropped)


# ---------------------------------------------------------------------------
# 格式化（纯函数，供两处渲染共用）
# ---------------------------------------------------------------------------

def sample_count(entry) -> int:
    """已观测样本数 = 成功次数 + 失败次数。"""
    return int(getattr(entry, "success_count", 0) or 0) + \
        int(getattr(entry, "fail_count", 0) or 0)


def format_rate(entry) -> str:
    """成功率展示串。

    **无样本时返回 "—"**（而不是 100%）：``SourceHealth.success_rate`` 在
    total==0 时按定义返回 1.0，直接格式化会让「刚重置、一次都没跑过」的源
    显示成满分绿灯，与「从未成功」的事实相反。
    """
    if sample_count(entry) <= 0:
        return "—"
    try:
        return f"{float(getattr(entry, 'success_rate', 0.0)):.0%}"
    except (TypeError, ValueError):
        return "—"


def format_latency(entry) -> str:
    """平均延迟展示串：<1s 用毫秒，否则用秒（保留一位小数）。"""
    try:
        ms = float(getattr(entry, "avg_latency_ms", 0.0) or 0.0)
    except (TypeError, ValueError):
        return "—"
    if ms <= 0:
        return "—"
    if ms < 1000:
        return f"{ms:.0f}ms"
    return f"{ms / 1000:.1f}s"


def format_streak(entry) -> str:
    """连续失败次数；0 次返回 "—"（避免满屏 0 干扰阅读）。"""
    try:
        n = int(getattr(entry, "consecutive_failures", 0) or 0)
    except (TypeError, ValueError):
        return "—"
    return str(n) if n > 0 else "—"


def ago_parts(iso_ts: Optional[str],
              now: Optional[datetime] = None) -> Optional[Tuple[str, int]]:
    """把 ISO 时间戳换算成「多久以前」，返回 (单位, 数值) 供 i18n 组装。

    单位：``now``（刚刚）/ ``s`` / ``m`` / ``h`` / ``d``。
    时间戳缺失或不可解析返回 None（界面显示 "—"）。
    未来时间（时钟回拨）按「刚刚」处理，不出现「-3 分钟前」。
    """
    if not iso_ts:
        return None
    try:
        ts = datetime.fromisoformat(str(iso_ts))
    except (TypeError, ValueError):
        return None
    delta = (now or datetime.now()) - ts
    seconds = delta.total_seconds()
    if seconds < 60:
        return ("now", 0)
    if seconds < 3600:
        return ("m", int(seconds // 60))
    if seconds < 86400:
        return ("h", int(seconds // 3600))
    return ("d", int(seconds // 86400))


def last_error_text(entry, limit: int = 120) -> str:
    """最近一次错误文本（截断）；无错误返回空串。"""
    err = getattr(entry, "last_error", None)
    if not err:
        return ""
    text = str(err).strip()
    return text[:limit] + ("…" if len(text) > limit else "")


def status_key(entry) -> str:
    """i18n 键后缀：``source_healthy`` / ``source_degraded`` / ``source_down``。"""
    return f"source_{status_of(entry)}"


def dot_class(entry) -> str:
    """``status-dot`` 修饰类（active / warning / error）。"""
    return STATUS_DOT_CLASS[status_of(entry)]


def severity_rank(entry) -> int:
    """排序位（供调用方二次排序时复用同一口径）。"""
    return SEVERITY_ORDER[status_of(entry)]


__all__ = [
    "SEVERITY_ORDER",
    "PROBLEM_STATUSES",
    "STATUS_DOT_CLASS",
    "HealthSnapshot",
    "build_snapshot",
    "status_of",
    "status_key",
    "dot_class",
    "severity_rank",
    "sample_count",
    "format_rate",
    "format_latency",
    "format_streak",
    "ago_parts",
    "last_error_text",
]
