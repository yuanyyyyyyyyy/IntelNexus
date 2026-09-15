"""
TaskRunner 单元测试
===================
验证后台任务运行器的核心生命周期：start → poll → complete/fail。

时序说明：本文件原有多处「固定 sleep 后断言」——固定等待时长与线程调度抖动
同量级，机器负载高时会随机失效（快了判太早、慢了白等）。现统一改为
「闸门编排先后（threading.Event）+ 条件等待（_wait_until）」，
断言本身一条未放宽、未删除。
"""

import time
import threading

from intelnexus.core.task_runner import TaskRunner, get_task_runner


def _wait_until(predicate, timeout: float = 10.0, interval: float = 0.01) -> bool:
    """条件等待：轮询直到 predicate() 为真或超时。

    返回谓词的最终取值，使失败信息仍定位到调用处的断言，而不是卡死。
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


class TestTaskRunner:
    """TaskRunner 核心功能测试。"""

    def test_start_and_complete(self):
        """正常任务：启动后完成，结果正确返回。"""
        runner = TaskRunner()
        gate = threading.Event()

        def worker(progress_cb, value=10):
            progress_cb("step1", "处理中...", 0.5)
            # 闸门卡住 worker：start() 在起线程前已持锁写入 running 状态，
            # 因此下面「运行中」的断言必然成立（消除与线程的竞速）
            gate.wait(timeout=30)
            return {"answer": value * 2}

        ok = runner.start("test1", worker, kwargs={"value": 10})
        assert ok is True
        assert runner.is_running("test1") is True

        # 放开闸门，条件等待收敛（替代固定 sleep(0.3)）
        gate.set()
        assert _wait_until(lambda: runner.is_running("test1") is False)

        state = runner.get_snapshot("test1")
        assert state["status"] == "completed"
        assert state["result"]["answer"] == 20
        assert state["progress"] == 1.0

    def test_start_duplicate_rejected(self):
        """重复提交同 ID 任务应被拒绝。"""
        runner = TaskRunner()
        gate = threading.Event()

        def slow_worker(progress_cb):
            # 闸门卡住：确定性地保证首次任务仍在运行时才提交第二次
            # （替代原 sleep(1.0) 的墙钟假设）
            gate.wait(timeout=30)
            return {}

        try:
            ok1 = runner.start("dup_test", slow_worker)
            assert ok1 is True

            ok2 = runner.start("dup_test", slow_worker)
            assert ok2 is False
        finally:
            gate.set()

    def test_failure_handling(self):
        """worker 抛异常时任务状态为 failed。"""
        runner = TaskRunner()

        def failing_worker(progress_cb):
            progress_cb("step1", "即将失败...", 0.3)
            raise ValueError("模拟失败")

        ok = runner.start("fail_test", failing_worker)
        assert ok is True

        # 条件等待失败态收敛（替代固定 sleep(0.3)）
        assert _wait_until(
            lambda: runner.get_snapshot("fail_test")["status"] == "failed")

        state = runner.get_snapshot("fail_test")
        assert state["status"] == "failed"
        assert "ValueError" in state["error"]
        assert "模拟失败" in state["error"]

    def test_progress_callback(self):
        """进度回调正确更新状态。"""
        runner = TaskRunner()
        first_progress = threading.Event()
        gate = threading.Event()

        def progress_worker(progress_cb):
            progress_cb("phase1", "第一步", 0.2)
            first_progress.set()
            # 闸门卡住：确保断言时状态仍为 running 且已记录首个进度
            gate.wait(timeout=30)
            progress_cb("phase2", "第二步", 0.6)
            progress_cb("phase3", "第三步", 0.9)
            return {"done": True}

        runner.start("progress_test", progress_worker)

        # 用闸门替代原 sleep(0.05) 的时序假设
        assert first_progress.wait(timeout=30)
        state = runner.get_snapshot("progress_test")
        assert state["status"] == "running"
        assert state["progress"] == 0.2

        # 等待完成（替代固定 sleep(0.5)）
        gate.set()
        assert _wait_until(
            lambda: runner.get_snapshot("progress_test")["status"] == "completed")
        state = runner.get_snapshot("progress_test")
        assert state["status"] == "completed"

    def test_reset(self):
        """reset 清除任务状态。"""
        runner = TaskRunner()

        def simple_worker(progress_cb):
            return {"data": "test"}

        runner.start("reset_test", simple_worker)
        # 条件等待结果就绪（替代固定 sleep(0.2)）
        assert _wait_until(lambda: runner.has_result("reset_test") is True)

        runner.reset("reset_test")
        assert runner.has_result("reset_test") is False
        state = runner.get_snapshot("reset_test")
        assert state["status"] == "idle"

    def test_get_result_nonexistent(self):
        """获取不存在的任务结果返回 None。"""
        runner = TaskRunner()
        assert runner.get_result("nonexistent") is None

    def test_is_running_nonexistent(self):
        """检查不存在的任务返回 False。"""
        runner = TaskRunner()
        assert runner.is_running("nonexistent") is False

    def test_any_running(self):
        """any_running 正确反映全局状态。"""
        runner = TaskRunner()
        assert runner.any_running() is False

        gate = threading.Event()

        def slow_worker(progress_cb):
            # 闸门卡住：确定性地保持「运行中」，替代原 sleep(0.5) 的时序假设
            gate.wait(timeout=30)
            return {}

        runner.start("any_test", slow_worker)
        assert runner.any_running() is True

        # 条件等待全部结束（替代固定 sleep(0.7)）
        gate.set()
        assert _wait_until(lambda: runner.any_running() is False)

    def test_snapshot_is_copy(self):
        """get_snapshot 返回的是副本，修改不影响内部状态。"""
        runner = TaskRunner()

        def simple_worker(progress_cb):
            return {"key": "value"}

        runner.start("snapshot_test", simple_worker)
        # 条件等待完成（替代固定 sleep(0.2)）
        assert _wait_until(
            lambda: runner.get_snapshot("snapshot_test")["status"] == "completed")

        snap1 = runner.get_snapshot("snapshot_test")
        snap1["status"] = "tampered"
        snap2 = runner.get_snapshot("snapshot_test")
        assert snap2["status"] == "completed"  # 内部状态未被篡改


class TestTaskRunnerSingleton:
    """单例模式测试。"""

    def test_get_task_runner_returns_same_instance(self):
        """get_task_runner 返回同一实例。"""
        r1 = get_task_runner()
        r2 = get_task_runner()
        assert r1 is r2

    def test_thread_safety(self):
        """多线程并发启动不崩溃。"""
        runner = TaskRunner()
        results = []
        errors = []

        def start_task(task_id):
            try:
                def worker(progress_cb, tid=task_id):
                    time.sleep(0.1)
                    return {"id": tid}
                ok = runner.start(f"thread_{task_id}", worker)
                results.append(ok)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=start_task, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert all(results)  # 所有任务都应成功启动
