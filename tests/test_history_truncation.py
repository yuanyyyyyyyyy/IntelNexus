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


def test_soft_deleted_entries_count_toward_cap(history):
    """软删除条目仍占索引位，防止删除后新条目被误挤出"""
    max_n = bh.BriefingHistory._MAX_HISTORY_ENTRIES
    for i in range(max_n):
        history.save_briefing(markdown_content=f"b-{i}")
    # 软删除前 10 条
    entries = history.get_briefings(limit=max_n, include_deleted=True)
    for e in entries[-10:]:
        history.delete_briefing(e["filename"])
    # 总数仍为 max_n（含已删除）
    all_entries = history.get_briefings(limit=max_n + 100, include_deleted=True)
    assert len(all_entries) == max_n
    # 保存新条目，应挤出最老的（含已删除的）
    history.save_briefing(markdown_content="newest")
    all_after = history.get_briefings(limit=max_n + 100, include_deleted=True)
    assert len(all_after) == max_n
