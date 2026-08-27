"""Briefing history tests: save/load/delete, listing, path traversal protection."""
import os

import pytest

from intelnexus.config import briefing_history as bh


@pytest.fixture
def history(tmp_path):
    return bh.BriefingHistory(storage_dir=str(tmp_path))


def test_save_and_load_briefing(history):
    fn = history.save_briefing(
        markdown_content="# 简报\n内容",
        organization_name="Org", categories=["ai"], subscribers_count=3)
    assert fn.startswith("briefing_")
    assert fn.endswith(".md")
    # 文件应存在
    assert os.path.exists(os.path.join(history.briefings_dir, fn))
    # 加载内容
    content = history.load_briefing(fn)
    assert "# 简报" in content


def test_save_with_html(history):
    fn = history.save_briefing(
        markdown_content="md", html_content="<h1>html</h1>")
    entry = history.get_briefings(limit=1)[0]
    assert entry["html_filename"].endswith(".html")
    html_path = os.path.join(history.briefings_dir, entry["html_filename"])
    assert os.path.exists(html_path)


def test_get_briefings_returns_most_recent_first(history):
    history.save_briefing(markdown_content="first")
    history.save_briefing(markdown_content="second")
    entries = history.get_briefings(limit=10)
    assert len(entries) == 2
    # 最新插入的在前面
    assert entries[0]["content_length"] == len("second")


def test_delete_briefing_soft_delete(history):
    fn = history.save_briefing(markdown_content="to delete")
    # 软删除成功
    assert history.delete_briefing(fn) is True
    # 文件仍在磁盘
    assert os.path.exists(os.path.join(history.briefings_dir, fn))
    # 默认不显示已删除
    assert len(history.get_briefings(limit=10)) == 0
    # include_deleted=True 可见
    deleted = history.get_briefings(limit=10, include_deleted=True)
    assert len(deleted) == 1
    assert deleted[0]["deleted"] is True
    # 重复删除返回 False
    assert history.delete_briefing(fn) is False


def test_restore_briefing(history):
    fn = history.save_briefing(markdown_content="to restore")
    history.delete_briefing(fn)
    assert history.restore_briefing(fn) is True
    entries = history.get_briefings(limit=10)
    assert len(entries) == 1
    assert entries[0]["deleted"] is False
    # 恢复未删除的返回 False
    assert history.restore_briefing(fn) is False


def test_restore_nonexistent_returns_false(history):
    assert history.restore_briefing("ghost.md") is False


def test_purge_deleted(history):
    import time
    fn1 = history.save_briefing(markdown_content="old")
    fn2 = history.save_briefing(markdown_content="new")
    history.delete_briefing(fn1)
    history.delete_briefing(fn2)
    # 手动把 deleted_at 改为 60 天前（模拟过期）
    all_entries = history.get_briefings(limit=10, include_deleted=True)
    for e in all_entries:
        if e["filename"] == fn1:
            from datetime import datetime, timedelta
            e["deleted_at"] = (datetime.now() - timedelta(days=60)).isoformat()
    from intelnexus.core.settings.file_lock import safe_write_json
    safe_write_json(history.history_file, all_entries)
    # purge 30 天：只清 fn1
    n = history.purge_deleted(days=30)
    assert n == 1
    remaining = history.get_briefings(limit=10, include_deleted=True)
    assert len(remaining) == 1
    assert remaining[0]["filename"] == fn2
    # fn1 物理文件应被删除
    assert not os.path.exists(os.path.join(history.briefings_dir, fn1))


def test_export_briefings(history):
    history.save_briefing(markdown_content="# report 1")
    history.save_briefing(markdown_content="# report 2")
    entries = history.get_briefings(limit=10)
    filenames = [e["filename"] for e in entries]
    zip_data = history.export_briefings(filenames)
    assert zip_data is not None
    assert len(zip_data) > 0
    import zipfile, io
    with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
        assert len(zf.namelist()) == 2


def test_export_briefings_no_valid_files(history):
    result = history.export_briefings(["nonexistent.md"])
    assert result is None


def test_get_briefings_excludes_deleted_by_default(history):
    fn1 = history.save_briefing(markdown_content="visible")
    fn2 = history.save_briefing(markdown_content="hidden")
    history.delete_briefing(fn2)
    visible = history.get_briefings(limit=10)
    assert len(visible) == 1
    assert visible[0]["filename"] == fn1


def test_load_missing_briefing_returns_none(history):
    assert history.load_briefing("nonexistent.md") is None


def test_path_traversal_blocked_on_load(history):
    # 尝试穿越到 storage 之外
    assert history.load_briefing("../secret.md") is None


def test_path_traversal_blocked_on_delete(history):
    assert history.delete_briefing("../../etc/passwd") is False


def test_get_briefings_limit(history):
    for i in range(5):
        history.save_briefing(markdown_content=f"b{i}")
    assert len(history.get_briefings(limit=3)) == 3
    assert len(history.get_briefings(limit=20)) == 5


def test_singleton_get_briefing_history(tmp_path):
    # 不同 storage_dir 不应影响单例（单例固定默认 data/）
    inst = bh.get_briefing_history()
    assert isinstance(inst, bh.BriefingHistory)
