"""文件锁与原子写入测试。

重点覆盖 ``safe_write_json`` 的临时文件生命周期：
Windows 下 ``shutil.move`` 在目标被读者以共享锁打开时抛 ``PermissionError``，
这是「读多写多」文件（source_health.json / briefing_history.json）的常态竞态。
历史缺陷：只有最后一个 except 分支清理 ``.tmp.<pid>.<ms>``，其余失败分支
直接 return，导致每次失败泄漏一个临时文件（实测 data/ 下累积 51 个）。
"""
import json
import os

import pytest

from intelnexus.core.settings import file_lock
from intelnexus.core.settings.file_lock import safe_read_json, safe_write_json


@pytest.fixture(autouse=True)
def _no_retry_delay(monkeypatch):
    """去掉重试间隔，让失败路径的测试保持快速。"""
    monkeypatch.setattr(file_lock, "RETRY_DELAY", 0.0)


def _tmp_files(directory):
    return [n for n in os.listdir(directory) if ".tmp." in n]


class TestSafeWriteJsonHappyPath:
    def test_writes_and_leaves_no_tmp_file(self, tmp_path):
        target = str(tmp_path / "data.json")
        assert safe_write_json(target, {"a": 1}) is True

        assert json.loads((tmp_path / "data.json").read_text(encoding="utf-8")) == {"a": 1}
        assert _tmp_files(tmp_path) == []

    def test_creates_parent_directory(self, tmp_path):
        target = str(tmp_path / "deep" / "nested" / "data.json")
        assert safe_write_json(target, {"a": 1}) is True
        assert (tmp_path / "deep" / "nested" / "data.json").exists()

    def test_overwrites_existing_file(self, tmp_path):
        target = str(tmp_path / "data.json")
        safe_write_json(target, {"v": 1})
        safe_write_json(target, {"v": 2})

        assert json.loads((tmp_path / "data.json").read_text(encoding="utf-8")) == {"v": 2}
        assert _tmp_files(tmp_path) == []


class TestSafeWriteJsonLeakPrevention:
    """三个失败分支都必须清理临时文件，否则 data/ 会被 .tmp.* 垃圾填满。"""

    def test_permission_error_on_move_cleans_tmp(self, tmp_path, monkeypatch):
        target = str(tmp_path / "data.json")

        def _raise(src, dst):
            raise PermissionError(13, "The process cannot access the file")

        monkeypatch.setattr(file_lock.shutil, "move", _raise)

        assert safe_write_json(target, {"a": 1}) is False
        assert _tmp_files(tmp_path) == [], "PermissionError 分支泄漏了临时文件"

    def test_os_error_on_move_cleans_tmp(self, tmp_path, monkeypatch):
        target = str(tmp_path / "data.json")

        def _raise(src, dst):
            raise OSError(22, "Invalid argument")

        monkeypatch.setattr(file_lock.shutil, "move", _raise)

        assert safe_write_json(target, {"a": 1}) is False
        assert _tmp_files(tmp_path) == [], "OSError 分支泄漏了临时文件"

    def test_unexpected_error_cleans_tmp(self, tmp_path, monkeypatch):
        target = str(tmp_path / "data.json")

        def _raise(src, dst):
            raise RuntimeError("boom")

        monkeypatch.setattr(file_lock.shutil, "move", _raise)

        assert safe_write_json(target, {"a": 1}) is False
        assert _tmp_files(tmp_path) == [], "兜底分支泄漏了临时文件"

    def test_each_retry_attempt_cleans_its_own_tmp(self, tmp_path, monkeypatch):
        """重试 3 次 → 应只尝试 3 次且最终不留任何临时文件。"""
        target = str(tmp_path / "data.json")
        calls = []

        def _raise(src, dst):
            calls.append(src)
            raise PermissionError(13, "locked")

        monkeypatch.setattr(file_lock.shutil, "move", _raise)

        assert safe_write_json(target, {"a": 1}) is False
        assert len(calls) == file_lock.MAX_RETRIES
        assert _tmp_files(tmp_path) == []

    def test_retry_then_success_leaves_no_tmp(self, tmp_path, monkeypatch):
        """首次占用、第二次成功 → 返回 True 且无残留。"""
        target = str(tmp_path / "data.json")
        real_move = file_lock.shutil.move
        state = {"n": 0}

        def _flaky(src, dst):
            state["n"] += 1
            if state["n"] == 1:
                raise PermissionError(13, "locked")
            return real_move(src, dst)

        monkeypatch.setattr(file_lock.shutil, "move", _flaky)

        assert safe_write_json(target, {"a": 1}) is True
        assert state["n"] == 2
        assert _tmp_files(tmp_path) == []
        assert json.loads((tmp_path / "data.json").read_text(encoding="utf-8")) == {"a": 1}


class TestSafeWriteJsonObservability:
    def test_permission_error_logs_warning_not_debug(self, tmp_path, monkeypatch, caplog):
        """写入失败必须可见——历史实现用 debug，默认级别下完全静默。"""
        target = str(tmp_path / "data.json")
        monkeypatch.setattr(
            file_lock.shutil, "move",
            lambda src, dst: (_ for _ in ()).throw(PermissionError(13, "locked")),
        )

        with caplog.at_level("DEBUG"):
            safe_write_json(target, {"a": 1})

        assert any(r.levelname == "WARNING" for r in caplog.records), \
            "写入失败应记 warning，而不是 debug"


class TestSafeReadJson:
    def test_missing_file_returns_empty_dict(self, tmp_path):
        assert safe_read_json(str(tmp_path / "nope.json")) == {}

    def test_corrupt_json_returns_empty_dict(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("{not json", encoding="utf-8")
        assert safe_read_json(str(p)) == {}

    def test_roundtrip_preserves_unicode(self, tmp_path):
        target = str(tmp_path / "cn.json")
        safe_write_json(target, {"名称": "情报源", "值": [1, 2]})

        assert safe_read_json(target) == {"名称": "情报源", "值": [1, 2]}
