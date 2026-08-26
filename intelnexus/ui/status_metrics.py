"""
运行指标聚合层
==============
为状态栏 / 数据源健康面板 / 首页提供「单一口径」的只读运行指标。

设计原则：
- 纯采集函数（collect_*）不依赖 streamlit 运行时，便于单元测试；
  缓存包装函数（get_*_cached）是 @st.cache_data(ttl=15) 的薄包装，
  UI 层一律调用包装函数；数据变更后统一经 invalidate_status_metrics() 失效。
- 全只读：任何采集路径绝不触发写操作（如健康表的
  purge_stale_entries 清理必须留在侧边栏原调用点，不得挪到这里）。
- 全兜底：新装环境 / 空数据目录 / 损坏 JSON 一律返回安全默认值，绝不抛错。

依赖约定：对底层模块（健康表 / 调度器 / 简报历史 / 推送日志 / 搜索历史）
一律在函数体内延迟导入，避免与 ui 包其他模块形成循环依赖。
"""

from datetime import datetime

import streamlit as st

# 缓存 TTL（秒）：状态栏等高频刷新组件共用，15s 口径
_METRICS_TTL = 15

# 安全默认值：任何异常/缺失数据的返回形态（测试与下游渲染以此为契约）
_HEALTH_DEFAULT = {"healthy": 0, "degraded": 0, "down": 0, "total": 0}
_SCHEDULER_DEFAULT = {"running": False, "job_count": 0, "next_run_str": None}
_TODAY_DEFAULT = {
    "briefings_today": 0,
    "pushes_today": 0,
    "searches_today": 0,
    "last_briefing": None,
}


# ---------------------------------------------------------------------------
# 纯采集函数（不依赖 streamlit，可直接单测）
# ---------------------------------------------------------------------------

def collect_health_summary() -> dict:
    """采集数据源健康汇总：{"healthy": n, "degraded": n, "down": n, "total": n}。

    仅调用 get_all_health()（只读）。严禁调用 purge_stale_entries——
    那是写操作，必须留在侧边栏原调用点。
    """
    try:
        from intelnexus.core.search.health import get_all_health
        entries = get_all_health() or []
        counts = {"healthy": 0, "degraded": 0, "down": 0, "total": len(entries)}
        for h in entries:
            status = getattr(h, "status", None)
            if status in counts:
                counts[status] += 1
        return counts
    except Exception:
        # 新装环境 / 文件损坏 / 模块缺失：兜底而非抛错
        return dict(_HEALTH_DEFAULT)


def collect_scheduler_summary() -> dict:
    """采集定时调度器状态：{"running": bool, "job_count": int, "next_run_str": str|None}。

    判定逻辑与 briefing_viewer._render_scheduler_status_banner 保持一致：
    - get_scheduler() 为 None（含 ImportError，如 --no-scheduler 手动模式）→ 未运行；
    - 否则过滤 next_run_time 非空的任务计数，最早的执行时间格式化为 "%m-%d %H:%M"。
    任何异常返回安全默认值。
    """
    try:
        try:
            from intelnexus.briefing.scheduler_registry import get_scheduler
            sched = get_scheduler()
        except ImportError:
            return dict(_SCHEDULER_DEFAULT)

        if sched is None:
            return {"running": False, "job_count": 0, "next_run_str": None}

        jobs = [j for j in sched.scheduler.get_jobs()
                if getattr(j, "next_run_time", None) is not None]
        if not jobs:
            # 调度器在跑但无启用任务（无订阅者）：running 仍为 True
            return {"running": True, "job_count": 0, "next_run_str": None}

        next_run = sorted(j.next_run_time for j in jobs)[0]
        return {
            "running": True,
            "job_count": len(jobs),
            "next_run_str": next_run.strftime("%m-%d %H:%M"),
        }
    except Exception:
        return dict(_SCHEDULER_DEFAULT)


def collect_today_stats() -> dict:
    """采集「今日」运行数据：
    {"briefings_today": int, "pushes_today": int,
     "searches_today": int, "last_briefing": dict|None}

    - 简报：briefing_history.get_briefings(limit=100)（简报历史上限即 100 条），
      按 created_at 前 10 位与今天（YYYY-MM-DD）比对计数；last_briefing 取索引首条（最新），
      其 title 字段由 organization 或文件名派生（历史索引本身无标题字段）。
    - 推送：自然日口径——读推送日志原始条目（push_log.get_push_entries），
      按 timestamp 前 10 位 == 今天过滤，语义为「今日至少一渠道成功的推送数」
      （success 判定与 get_push_stats 一致：any(channels.values())）。
    - 搜索：history.get_history_manager().get_history(limit=100)，
      按 timestamp 前 10 位计数。
    各来源独立兜底，单个来源失败不影响其余字段。
    """
    result = dict(_TODAY_DEFAULT)
    today = datetime.now().strftime("%Y-%m-%d")

    # ---- 简报 ----
    try:
        from intelnexus.config.briefing_history import get_briefing_history
        briefings = get_briefing_history().get_briefings(limit=100) or []
        result["briefings_today"] = sum(
            1 for b in briefings if (b.get("created_at") or "")[:10] == today
        )
        if briefings:
            latest = briefings[0]
            result["last_briefing"] = {
                "filename": latest.get("filename") or "",
                "created_at": latest.get("created_at") or "",
                # 历史索引条目无独立标题：以组织名回退文件名作为显示标题
                "title": latest.get("organization") or latest.get("filename") or "",
                "categories": latest.get("categories") or [],
            }
    except Exception:
        pass

    # ---- 推送（自然日口径：timestamp[:10] == 今天 且至少一渠道成功）----
    try:
        from intelnexus.config.push_log import get_push_entries
        result["pushes_today"] = sum(
            1 for e in get_push_entries()
            if (e.get("timestamp") or "")[:10] == today
            and any((e.get("channels") or {}).values())
        )
    except Exception:
        pass

    # ---- 搜索 ----
    try:
        from intelnexus.config.history import get_history_manager
        entries = get_history_manager().get_history(limit=100) or []
        result["searches_today"] = sum(
            1 for e in entries if (e.get("timestamp") or "")[:10] == today
        )
    except Exception:
        pass

    return result


# ---------------------------------------------------------------------------
# st.cache_data 薄包装（UI 层调用入口；纯函数与缓存包装分开命名）
# ---------------------------------------------------------------------------

@st.cache_data(ttl=_METRICS_TTL, show_spinner=False)
def get_health_summary_cached() -> dict:
    """健康汇总（15s 缓存）。"""
    return collect_health_summary()


@st.cache_data(ttl=_METRICS_TTL, show_spinner=False)
def get_scheduler_summary_cached() -> dict:
    """调度器状态（15s 缓存）。"""
    return collect_scheduler_summary()


@st.cache_data(ttl=_METRICS_TTL, show_spinner=False)
def get_today_stats_cached() -> dict:
    """今日运行数据（15s 缓存）。"""
    return collect_today_stats()


def invalidate_status_metrics() -> None:
    """统一失效入口：逐个清空三个缓存包装函数的缓存。

    数据发生写入（新增简报 / 推送 / 搜索记录等）后调用，
    保证状态栏、健康面板、首页下次读取即拿到最新口径。

    设计取舍：失效仅作用于当前会话的 st.cache_data，多会话并发下
    其它会话的三指标间最多存在 15s 口径不一致，由 TTL 到期自愈。
    """
    for fn in (get_health_summary_cached,
               get_scheduler_summary_cached,
               get_today_stats_cached):
        try:
            fn.clear()
        except Exception:
            # 失效失败最坏后果是多看 15s 旧数据，绝不向上抛
            pass
