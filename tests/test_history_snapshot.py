"""搜索历史快照存储与回放测试。

覆盖：
- 快照组装（只保留回放所需字段，显式剔除 scraped 抓取正文）；
- 落盘与按需加载的往返一致性；
- 大体积产物独立落盘（知识图谱 HTML / 可信度雷达图 base64 → PNG）；
- 文件生命周期（软删除保留、物理清除 / 全清 / 超上限截断时回收）；
- 旧记录、损坏文件、落盘失败的优雅降级；
- ``ResultsView`` 数据源抽象的基本契约。
"""

import base64
import json
from pathlib import Path

import pytest

from intelnexus.config.history import SearchHistory

# 1x1 PNG 的 base64（避免测试依赖 Pillow）
_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8"
    "z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


@pytest.fixture
def history(tmp_path):
    """隔离存储目录的历史管理器（不触碰真实 data/）。"""
    return SearchHistory(storage_dir=str(tmp_path))


def _search_result(tmp_path: Path) -> dict:
    """构造一份形如 ``run_search_computation`` 返回值的搜索结果。"""
    kg_file = tmp_path / "kg_20260101_000000.html"
    kg_file.write_text("<html>knowledge graph</html>", encoding="utf-8")
    return {
        "query": "APT 组织",
        "search_mode": "all",
        "refined": "APT organization",
        "results": [{"title": "t1", "url": "https://a.example/1", "source": "S"}],
        "filtered": [{"title": "t1", "url": "https://a.example/1", "source": "S"}],
        # 抓取正文：体积最大，必须被快照排除
        "scraped": {"https://a.example/1": "正文" * 5000},
        "streamed_summary": "# 报告",
        "credibility_data": {"avg_score": 0.8, "scores": []},
        "credibility_radar_chart": _PNG_B64,
        "conflicts": [],
        "structured_summary": {"facts": []},
        "kg_entities": [{"name": "APT28", "type": "组织", "importance": 0.9}],
        "kg_relations": [],
        "kg_html_path": str(kg_file),
        "kg_context": "- APT28",
        "evidence_data": {"coverage": 0.5, "claims": []},
        "action_items": [{"action": "关注", "priority": "high"}],
        "tldr_card": "速览",
        "source_stats": {"web": {"status": "ok"}},
        "source_counts": {"web": 1},
        "source_info": "web",
        "query_variants": ["APT"],
        "search_query": "APT 组织 攻击",
        "report_timestamp": "2026-01-01_00-00-00",
    }


class TestBuildSnapshot:
    def test_excludes_scraped_and_keeps_replay_keys(self, tmp_path):
        snapshot = SearchHistory.build_snapshot(_search_result(tmp_path))
        assert "scraped" not in snapshot
        for key in ("query", "results", "filtered", "streamed_summary",
                    "credibility_data", "credibility_radar_chart", "conflicts",
                    "structured_summary", "kg_entities", "kg_html_path",
                    "evidence_data", "action_items", "tldr_card",
                    "source_stats", "source_info", "query_variants",
                    "search_query", "report_timestamp"):
            assert key in snapshot, f"缺少回放字段: {key}"

    def test_returns_none_for_empty_or_invalid(self):
        assert SearchHistory.build_snapshot({}) is None
        assert SearchHistory.build_snapshot(None) is None
        assert SearchHistory.build_snapshot("not-a-dict") is None


class TestSnapshotPersistence:
    def test_roundtrip(self, history, tmp_path):
        result = _search_result(tmp_path)
        entry = history.add_search(
            "APT 组织", "all", 1, "gpt", report_content="# 报告",
            snapshot=history.build_snapshot(result))

        assert entry["has_snapshot"] is True
        assert entry["snapshot_dir"] == f"snapshots/{entry['id']}"

        snapshot = history.get_snapshot(entry["id"])
        assert snapshot["streamed_summary"] == "# 报告"
        assert snapshot["results"] == result["results"]
        assert "scraped" not in snapshot
        # 知识图谱 HTML 还原为持久目录下的绝对路径，且文件真实存在
        kg_path = Path(snapshot["kg_html_path"])
        assert kg_path.exists()
        assert kg_path.parent.name == entry["id"]
        # 雷达图 base64 还原
        assert base64.b64decode(
            snapshot["credibility_radar_chart"]) == base64.b64decode(_PNG_B64)

    def test_snapshot_json_has_no_scraped_and_no_base64(self, history, tmp_path):
        result = _search_result(tmp_path)
        entry = history.add_search("q", "all", 1, "m",
                                   snapshot=history.build_snapshot(result))
        snapshot_file = history.snapshots_dir / entry["id"] / "snapshot.json"
        raw = json.loads(snapshot_file.read_text(encoding="utf-8"))

        assert "scraped" not in raw
        assert "credibility_radar_chart" not in raw
        assert raw["kg_html_path"] == "kg.html"
        # KG 副本 + 雷达图均为独立文件
        assert (snapshot_file.parent / "kg.html").exists()
        assert (snapshot_file.parent / "radar.png").exists()

    def test_legacy_entry_without_snapshot(self, history):
        entry = history.add_search("old", "all", 0, "m", report_content="旧报告")
        assert "has_snapshot" not in entry
        assert history.get_snapshot(entry["id"]) is None
        assert history.get_snapshot("") is None
        assert history.get_snapshot("no-such-id") is None

    def test_corrupted_snapshot_returns_none(self, history, tmp_path):
        entry = history.add_search(
            "q", "all", 1, "m",
            snapshot=history.build_snapshot(_search_result(tmp_path)))
        (history.snapshots_dir / entry["id"] / "snapshot.json").write_text(
            "{ not valid json", encoding="utf-8")

        assert history.get_snapshot(entry["id"]) is None

    def test_write_failure_degrades_without_losing_entry(self, history):
        # 不可 JSON 序列化的产物 -> 落盘失败，条目仍写入且标记为无快照
        entry = history.add_search(
            "q", "all", 1, "m", snapshot={"results": [{"bad": object()}]})

        assert "has_snapshot" not in entry
        assert not (history.snapshots_dir / entry["id"]).exists()
        assert history.get_history()[0]["id"] == entry["id"]

    def test_missing_kg_file_degrades_to_empty_path(self, history, tmp_path):
        result = _search_result(tmp_path)
        Path(result["kg_html_path"]).unlink()
        entry = history.add_search("q", "all", 1, "m",
                                   snapshot=history.build_snapshot(result))

        snapshot = history.get_snapshot(entry["id"])
        assert snapshot["kg_html_path"] == ""


class TestSnapshotLifecycle:
    def test_soft_delete_keeps_snapshot_for_restore(self, history, tmp_path):
        entry = history.add_search(
            "q", "all", 1, "m",
            snapshot=history.build_snapshot(_search_result(tmp_path)))

        assert history.delete_entry(entry["id"]) is True
        # 软删除条目可恢复，因此快照保留
        assert (history.snapshots_dir / entry["id"]).exists()
        assert history.restore_entry(entry["id"]) is True
        assert history.get_snapshot(entry["id"]) is not None

    def test_purge_deleted_removes_snapshot(self, history, tmp_path):
        entry = history.add_search(
            "q", "all", 1, "m",
            snapshot=history.build_snapshot(_search_result(tmp_path)))
        history.delete_entry(entry["id"])

        assert history.purge_deleted() == 1
        assert not (history.snapshots_dir / entry["id"]).exists()

    def test_clear_history_removes_all_snapshots(self, history, tmp_path):
        for _ in range(3):
            history.add_search(
                "q", "all", 1, "m",
                snapshot=history.build_snapshot(_search_result(tmp_path)))

        history.clear_history()

        assert history.get_history(include_deleted=True) == []
        assert list(history.snapshots_dir.iterdir()) == []

    def test_new_search_reclaims_snapshot_of_dropped_deleted_entry(
            self, history, tmp_path):
        """软删除条目在下一次 add_search 重写索引时被丢弃，快照目录必须同步回收。"""
        entry = history.add_search(
            "q", "all", 1, "m",
            snapshot=history.build_snapshot(_search_result(tmp_path)))
        assert history.delete_entry(entry["id"]) is True
        assert (history.snapshots_dir / entry["id"]).exists()

        history.add_search("q2", "all", 1, "m",
                           snapshot=history.build_snapshot(_search_result(tmp_path)))

        remaining = [e["id"] for e in history.get_history(
            limit=9999, include_deleted=True)]
        assert entry["id"] not in remaining
        # 关键：被淘汰条目的快照不能作为无法访问的孤儿文件留在磁盘上
        assert not (history.snapshots_dir / entry["id"]).exists()

    def test_snapshot_dir_traversal_guard(self, history, tmp_path):
        """entry_id 源自可被篡改的 JSON：越界 id 不得读写 snapshots 之外的文件。"""
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "keep.txt").write_text("keep", encoding="utf-8")

        assert history.get_snapshot("../outside") is None
        history._remove_snapshot("../outside")

        assert outside.exists()
        assert (outside / "keep.txt").exists()

    def test_truncation_removes_oldest_snapshot(self, history, tmp_path,
                                                monkeypatch):
        import intelnexus.config.history as history_module
        monkeypatch.setattr(history_module, "MAX_HISTORY_ENTRIES", 2)

        first = history.add_search(
            "q1", "all", 1, "m",
            snapshot=history.build_snapshot(_search_result(tmp_path)))
        for query in ("q2", "q3"):
            history.add_search(
                query, "all", 1, "m",
                snapshot=history.build_snapshot(_search_result(tmp_path)))

        kept_ids = [e["id"] for e in history.get_history(include_deleted=True)]
        assert len(kept_ids) == 2
        assert first["id"] not in kept_ids
        assert not (history.snapshots_dir / first["id"]).exists()


class TestResultsView:
    def test_enabled_reflects_payload(self):
        from intelnexus.ui.results_view import ResultsView

        assert ResultsView({}).enabled is False
        assert ResultsView(None).enabled is False
        assert ResultsView({"results": [1]}).enabled is True

    def test_get_and_contains(self):
        from intelnexus.ui.results_view import ResultsView

        view = ResultsView({"results": [1]})
        assert view.get("results") == [1]
        assert view.get("missing", "fallback") == "fallback"
        assert "results" in view
        assert "missing" not in view

    def test_render_history_snapshot_returns_false_for_empty(self):
        from intelnexus.ui.results_view import render_history_snapshot

        assert render_history_snapshot({}, key_prefix="hist_") is False
        assert render_history_snapshot(None, key_prefix="hist_") is False
