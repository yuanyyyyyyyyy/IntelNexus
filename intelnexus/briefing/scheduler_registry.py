"""
调度器注册表（模块级单例）
========================
让 UI 层（订阅管理面板等）能在运行时拿到当前调度器实例，
实现「新增/编辑/删除订阅者后立即热更新定时任务」，无需重启进程。

修复的问题：原实现中订阅者增删改只写 JSON 文件，APScheduler 任务
要到进程重启才变化（旧注释自己承认"调度器将在重启时自动清理"）。
"""

import threading
from typing import Optional

from intelnexus.core.logger import get_logger

logger = get_logger(__name__)

_lock = threading.Lock()
_scheduler = None  # AIBriefingScheduler | None
_model_status = {"model": None, "degraded": False, "reason": ""}


def set_model_status(model, degraded: bool, reason: str = "") -> None:
    """记录定时链路的 LLM 解析结果，供 UI 状态横幅展示。

    Args:
        model: 解析到的模型名（如 "qwen2.5:7b"）；None 表示无可用模型
        degraded: True 时定时简报将以降级模式生成（无 LLM）
        reason: 降级原因（人读文本，可直接展示）
    """
    global _model_status
    with _lock:
        _model_status = {"model": model, "degraded": bool(degraded), "reason": reason or ""}
    if degraded:
        logger.warning("Scheduler LLM degraded: model=%r reason=%s", model, reason)
    else:
        logger.info("Scheduler LLM resolved: %r", model)


def get_model_status() -> dict:
    """返回最近一次解析的模型状态；调度器未启动时 degraded=False、model=None。"""
    with _lock:
        return dict(_model_status)


def register_scheduler(scheduler) -> None:
    """由应用启动流程（main._start_ai_scheduler / CLI scheduler 命令）调用注册。"""
    global _scheduler
    with _lock:
        _scheduler = scheduler
    logger.info("Briefing scheduler registered for hot-reload")


def unregister_scheduler() -> None:
    """调度器停止时注销引用。"""
    global _scheduler
    with _lock:
        _scheduler = None


def get_scheduler():
    """返回当前调度器实例；未启动（如 --no-scheduler 手动模式）时返回 None。"""
    with _lock:
        return _scheduler


def on_subscriber_changed(subscriber_id: str, change: str = "update") -> bool:
    """订阅者配置变更后热更新其定时任务。

    Args:
        subscriber_id: 订阅者 id
        change: "add" | "update" → 按最新配置重建该订阅者的 cron 任务；
                "remove" → 移除该订阅者的任务

    Returns:
        bool: 是否实际执行了热更新。未注册调度器（手动模式）或更新失败
              时返回 False——调用方不应因此中断配置写入主流程。
    """
    sched = get_scheduler()
    if sched is None:
        return False
    try:
        if change == "remove":
            sched.remove_subscriber_schedule(subscriber_id)
        else:
            sched.update_subscriber_schedule(subscriber_id)
        logger.info("Scheduler hot-reloaded after %s of subscriber %s", change, subscriber_id)
        return True
    except Exception as e:
        logger.warning("Scheduler hot-reload failed (%s %s): %s", change, subscriber_id, e)
        return False
