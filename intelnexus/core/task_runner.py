"""
后台任务运行器
==============
线程安全的任务管理器，支持在后台线程中执行长耗时任务（搜索、简报生成），
同时通过进度回调通知 UI 层。UI 通过 st.fragment + auto_rerun 轮询进度。

设计要点：
- worker 线程**不访问** st.session_state（无 ScriptRunContext），
  仅通过 progress_callback 和返回值与主线程通信。
- 状态读写全部由 threading.Lock 保护，保证线程安全。
- daemon=True 确保主进程退出时自动清理残留线程。
"""

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

from intelnexus.core.logger import get_logger

logger = get_logger(__name__)

# 进度回调签名：(phase: str, message: str, progress: float) -> None
ProgressCallback = Callable[[str, str, float], None]

# worker 函数签名：fn(progress_callback, **kwargs) -> dict
WorkerFn = Callable[..., Dict[str, Any]]


@dataclass
class TaskState:
    """线程安全的任务状态快照。

    由 TaskRunner 在锁保护下读写，外部只通过 get_snapshot() 获取不可变副本。
    """
    status: str = "idle"          # idle | running | completed | failed
    phase: str = ""               # 当前阶段标识（如 "searching", "generating"）
    message: str = ""             # 人类可读进度信息
    progress: float = 0.0         # 0.0 - 1.0
    result: Optional[Dict[str, Any]] = None
    error: str = ""
    started_at: float = 0.0
    completed_at: float = 0.0

    def get_snapshot(self) -> dict:
        """返回当前状态的不可变快照（dict），供 UI 层安全读取。"""
        return {
            "status": self.status,
            "phase": self.phase,
            "message": self.message,
            "progress": self.progress,
            "result": self.result,
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


class TaskRunner:
    """全局后台任务管理器（单例模式）。

    用法::

        runner = get_task_runner()

        # 启动任务
        def my_worker(progress_cb, query="test"):
            progress_cb("step1", "处理中...", 0.5)
            # ... 耗时操作 ...
            return {"data": "result"}

        runner.start("search", my_worker, kwargs={"query": "test"})

        # 轮询状态（在 st.fragment 中）
        state = runner.get_snapshot("search")
        if state["status"] == "completed":
            result = state["result"]

    """

    def __init__(self):
        self._lock = threading.Lock()
        self._states: Dict[str, TaskState] = {}
        self._threads: Dict[str, threading.Thread] = {}

    def start(self, task_id: str, fn: WorkerFn,
              kwargs: Optional[Dict[str, Any]] = None) -> bool:
        """启动后台任务。

        Args:
            task_id: 任务唯一标识（如 "search", "briefing"）
            fn: worker 函数，签名 fn(progress_callback, **kwargs) -> dict
            kwargs: 传给 worker 的额外参数

        Returns:
            True 表示成功启动；False 表示同 ID 任务已在运行，拒绝重复提交。
        """
        with self._lock:
            existing = self._states.get(task_id)
            if existing and existing.status == "running":
                # 检查线程是否真的还活着（防止僵尸状态）
                thread = self._threads.get(task_id)
                if thread and thread.is_alive():
                    logger.warning("任务 %s 已在运行，拒绝重复提交", task_id)
                    return False
                # 线程已死但状态未更新（异常情况），允许重新启动
                logger.info("任务 %s 线程已终止但状态残留，允许重新启动", task_id)

            # 初始化状态
            self._states[task_id] = TaskState(
                status="running",
                phase="starting",
                message="正在启动...",
                progress=0.0,
                started_at=time.time(),
            )

            # 创建并启动后台线程
            thread = threading.Thread(
                target=self._run_worker,
                args=(task_id, fn, kwargs or {}),
                daemon=True,
                name=f"task-{task_id}",
            )
            self._threads[task_id] = thread
            thread.start()
            logger.info("任务 %s 已启动后台线程", task_id)
            return True

    def _run_worker(self, task_id: str, fn: WorkerFn, kwargs: dict):
        """后台线程入口：执行 worker 并管理状态转换。"""
        def progress_callback(phase: str, message: str, progress: float):
            with self._lock:
                state = self._states.get(task_id)
                if state:
                    state.phase = phase
                    state.message = message
                    state.progress = min(1.0, max(0.0, progress))

        try:
            result = fn(progress_callback, **kwargs)
            with self._lock:
                state = self._states.get(task_id)
                if state:
                    state.status = "completed"
                    state.result = result or {}
                    state.progress = 1.0
                    state.phase = "done"
                    state.message = "完成"
                    state.completed_at = time.time()
            logger.info("任务 %s 执行完成", task_id)
        except Exception as e:
            logger.error("任务 %s 执行失败: %s", task_id, e, exc_info=True)
            with self._lock:
                state = self._states.get(task_id)
                if state:
                    state.status = "failed"
                    state.error = f"{type(e).__name__}: {e}"
                    state.phase = "error"
                    state.message = f"任务失败: {type(e).__name__}"
                    state.completed_at = time.time()

    def is_running(self, task_id: str) -> bool:
        """指定任务是否正在运行。"""
        with self._lock:
            state = self._states.get(task_id)
            if not state:
                return False
            if state.status == "running":
                # 双重检查线程存活
                thread = self._threads.get(task_id)
                if thread and thread.is_alive():
                    return True
                # 线程已死但状态未更新 → 标记失败
                state.status = "failed"
                state.error = "线程意外终止"
                state.completed_at = time.time()
                return False
            return False

    def get_snapshot(self, task_id: str) -> dict:
        """获取任务状态的不可变快照。

        任务不存在时返回 idle 状态的默认快照。
        """
        with self._lock:
            state = self._states.get(task_id)
            if not state:
                return TaskState().get_snapshot()
            # 顺便检查线程存活（惰性修正僵尸状态）
            if state.status == "running":
                thread = self._threads.get(task_id)
                if thread and not thread.is_alive():
                    state.status = "failed"
                    state.error = "线程意外终止"
                    state.completed_at = time.time()
            return state.get_snapshot()

    def get_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务结果（仅 completed 状态有值）。"""
        with self._lock:
            state = self._states.get(task_id)
            return state.result if state and state.status == "completed" else None

    def reset(self, task_id: str):
        """重置任务状态为 idle，清除结果。

        通常在 UI 层消费完结果后调用，为下次任务腾出空间。
        """
        with self._lock:
            self._states[task_id] = TaskState()
            self._threads.pop(task_id, None)

    def has_result(self, task_id: str) -> bool:
        """任务是否已完成且有结果。"""
        with self._lock:
            state = self._states.get(task_id)
            return bool(state and state.status == "completed" and state.result is not None)

    def any_running(self) -> bool:
        """是否有任何任务正在运行。

        供导航锁等全局防护逻辑使用。
        """
        with self._lock:
            for task_id, state in self._states.items():
                if state.status == "running":
                    thread = self._threads.get(task_id)
                    if thread and thread.is_alive():
                        return True
            return False


# ---- 单例管理 ----

_runner_instance: Optional[TaskRunner] = None
_runner_lock = threading.Lock()


def get_task_runner() -> TaskRunner:
    """获取全局 TaskRunner 单例（线程安全懒初始化）。"""
    global _runner_instance
    if _runner_instance is None:
        with _runner_lock:
            if _runner_instance is None:
                _runner_instance = TaskRunner()
    return _runner_instance
