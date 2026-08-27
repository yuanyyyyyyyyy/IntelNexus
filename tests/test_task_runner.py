"""
TaskRunner 单元测试
===================
验证后台任务运行器的核心生命周期：start → poll → complete/fail。
"""

import time
import threading
import pytest

from intelnexus.core.task_runner import TaskRunner, get_task_runner


class TestTaskRunner:
    """TaskRunner 核心功能测试。"""

    def test_start_and_complete(self):
        """正常任务：启动后完成，结果正确返回。"""
        runner = TaskRunner()

        def worker(progress_cb, value=10):
            progress_cb("step1", "处理中...", 0.5)
            return {"answer": value * 2}

        ok = runner.start("test1", worker, kwargs={"value": 10})
        assert ok is True
        assert runner.is_running("test1") is True

        # 等待完成
        time.sleep(0.3)
        assert runner.is_running("test1") is False

        state = runner.get_snapshot("test1")
        assert state["status"] == "completed"
        assert state["result"]["answer"] == 20
        assert state["progress"] == 1.0

    def test_start_duplicate_rejected(self):
        """重复提交同 ID 任务应被拒绝。"""
        runner = TaskRunner()

        def slow_worker(progress_cb):
            time.sleep(1.0)
            return {}

        ok1 = runner.start("dup_test", slow_worker)
        assert ok1 is True

        ok2 = runner.start("dup_test", slow_worker)
        assert ok2 is False

    def test_failure_handling(self):
        """worker 抛异常时任务状态为 failed。"""
        runner = TaskRunner()

        def failing_worker(progress_cb):
            progress_cb("step1", "即将失败...", 0.3)
            raise ValueError("模拟失败")

        ok = runner.start("fail_test", failing_worker)
        assert ok is True

        time.sleep(0.3)
        state = runner.get_snapshot("fail_test")
        assert state["status"] == "failed"
        assert "ValueError" in state["error"]
        assert "模拟失败" in state["error"]

    def test_progress_callback(self):
        """进度回调正确更新状态。"""
        runner = TaskRunner()

        def progress_worker(progress_cb):
            progress_cb("phase1", "第一步", 0.2)
            time.sleep(0.1)
            progress_cb("phase2", "第二步", 0.6)
            time.sleep(0.1)
            progress_cb("phase3", "第三步", 0.9)
            return {"done": True}

        runner.start("progress_test", progress_worker)

        # 等待第一个进度
        time.sleep(0.05)
        state = runner.get_snapshot("progress_test")
        # 可能处于任意阶段，但状态应该是 running
        assert state["status"] == "running"

        # 等待完成
        time.sleep(0.5)
        state = runner.get_snapshot("progress_test")
        assert state["status"] == "completed"

    def test_reset(self):
        """reset 清除任务状态。"""
        runner = TaskRunner()

        def simple_worker(progress_cb):
            return {"data": "test"}

        runner.start("reset_test", simple_worker)
        time.sleep(0.2)

        assert runner.has_result("reset_test") is True
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

        def slow_worker(progress_cb):
            time.sleep(0.5)
            return {}

        runner.start("any_test", slow_worker)
        assert runner.any_running() is True

        time.sleep(0.7)
        assert runner.any_running() is False

    def test_snapshot_is_copy(self):
        """get_snapshot 返回的是副本，修改不影响内部状态。"""
        runner = TaskRunner()

        def simple_worker(progress_cb):
            return {"key": "value"}

        runner.start("snapshot_test", simple_worker)
        time.sleep(0.2)

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
