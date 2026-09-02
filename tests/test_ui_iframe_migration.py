"""Tests for the st.components.v1.html → st.iframe migration and KG HTML pruning."""

import os
import time
from pathlib import Path

import pytest

RESULTS_PY = Path(__file__).resolve().parent.parent / "intelnexus" / "ui" / "results.py"


class TestIframeMigration:
    def test_no_components_v1_in_results(self):
        """results.py 不得再使用已弃用的 st.components.v1（防回归）。"""
        src = RESULTS_PY.read_text(encoding="utf-8")
        assert "st.components.v1" not in src

    def test_uses_st_iframe_with_path(self):
        """必须以 pathlib.Path 传入 kg 文件（字符串路径会触发迁移警告）。"""
        src = RESULTS_PY.read_text(encoding="utf-8")
        assert "st.iframe(Path(" in src


class TestPruneKgHtml:
    @pytest.fixture
    def kg_dir(self, tmp_path):
        """12 个不同 mtime 的 kg_*.html，外加 2 个不该被清理的文件。"""
        now = time.time()
        for i in range(12):
            p = tmp_path / f"kg_2026090{i % 10}_{i:06d}.html"
            p.write_text(f"<html>{i}</html>", encoding="utf-8")
            os.utime(p, (now - 1000 + i, now - 1000 + i))
        # 非 KG 文件与其他前缀文件不应被清理函数触碰
        (tmp_path / "other.html").write_text("x", encoding="utf-8")
        (tmp_path / "kg_meta.json").write_text("{}", encoding="utf-8")
        return tmp_path

    def test_keeps_newest_files(self, kg_dir):
        from intelnexus.analysis.intelligence_graph import prune_kg_html
        removed = prune_kg_html(str(kg_dir), keep=10)
        assert removed == 2
        remaining = sorted(p.name for p in kg_dir.glob("kg_*.html"))
        assert len(remaining) == 10
        # 被删的应是最旧的两个（mtime 最小）
        assert "kg_20260900_000000.html" not in remaining
        assert "kg_20260901_000001.html" not in remaining

    def test_noop_when_under_limit(self, kg_dir):
        from intelnexus.analysis.intelligence_graph import prune_kg_html
        assert prune_kg_html(str(kg_dir), keep=20) == 0
        assert len(list(kg_dir.glob("kg_*.html"))) == 12

    def test_missing_directory_is_silent(self, tmp_path):
        from intelnexus.analysis.intelligence_graph import prune_kg_html
        assert prune_kg_html(str(tmp_path / "nonexistent")) == 0
