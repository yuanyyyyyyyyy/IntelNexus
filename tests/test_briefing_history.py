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


def test_delete_briefing(history):
    fn = history.save_briefing(markdown_content="to delete")
    assert history.delete_briefing(fn) is True
    assert history.load_briefing(fn) is None
    # 删除不存在的返回 False
    assert history.delete_briefing(fn) is False


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
