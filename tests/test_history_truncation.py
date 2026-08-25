"""Briefing history 索引截断与条目元数据更新测试。

背景：save_briefing 曾以 limit=100 读回再插入写回——索引满 100 条后，
每次保存都会把最老条目永久挤出索引。修复后读全量、插入后统一截断。
"""
import pytest

from intelnexus.config import briefing_history as bh


@pytest.fixture
def history(tmp_path):
    return bh.BriefingHistory(storage_dir=str(tmp_path))


def test_save_caps_index_at_max_entries(history):
    for i in range(bh.BriefingHistory._MAX_HISTORY_ENTRIES + 10):
        history.save_briefing(markdown_content=f"briefing-{i}")
    entries = history.get_briefings(limit=1000)
    assert len(entries) == bh.BriefingHistory._MAX_HISTORY_ENTRIES
    # 最新的在前面
    assert entries[0]["filename"].endswith(".md")


def test_update_entry_merges_fields(history):
    fn = history.save_briefing(markdown_content="md", subscribers_count=0)
    ok = history.update_entry(fn, {"subscribers_count": 1, "source": "scheduled"})
    assert ok is True
    entry = history.get_briefings(limit=1)[0]
    assert entry["subscribers_count"] == 1
    assert entry["source"] == "scheduled"


def test_update_entry_missing_returns_false(history):
    assert history.update_entry("briefing_ghost.md", {"x": 1}) is False
