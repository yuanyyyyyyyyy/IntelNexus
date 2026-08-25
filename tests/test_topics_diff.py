"""Topics diff（本期增量速览）回归测试。

P0 修复背景：_prev_briefing_markdown 旧实现读 entry["content"]，
但 briefing_history 索引从不写该字段（正文在 briefings/*.md 文件里），
导致增量板块恒为「暂无上一期存档」。本文件固化正确读法与降级行为。

所有用例通过 stub 替换 get_briefing_history，绝不触碰真实 data/ 目录。
"""
import pytest

from intelnexus.topics import diff


class StubHistory:
    """BriefingHistory 最小替身：可控的索引条目与 .md 文件内容。"""

    def __init__(self, entries=None, files=None):
        self._entries = entries or []
        self._files = files or {}

    def get_briefings(self, limit=20):
        return self._entries[:limit]

    def load_briefing(self, filename):
        return self._files.get(filename)


@pytest.fixture
def history_stub_factory(monkeypatch):
    """把 diff 模块实际读取的 get_briefing_history 替换为可控 stub。"""

    def _install(stub):
        monkeypatch.setattr(
            "intelnexus.config.briefing_history.get_briefing_history",
            lambda: stub,
        )

    return _install


PREV_MD = (
    "# 简报\n\n"
    "- [旧闻A](https://news.example.com/old-a)\n"
    "- [旧闻B](https://news.example.com/old-b)\n"
)


def test_prev_briefing_reads_content_from_md_file(history_stub_factory):
    """索引只有元数据（无 content 键）时，应按 filename 回读 .md 正文。"""
    stub = StubHistory(
        entries=[{
            "id": "20260822_040000",
            "filename": "briefing_20260822_040000.md",
            "content_length": len(PREV_MD),
            "created_at": "2026-08-22T04:00:00",
        }],
        files={"briefing_20260822_040000.md": PREV_MD},
    )
    history_stub_factory(stub)
    assert "https://news.example.com/old-a" in diff._prev_briefing_markdown()


def test_prev_briefing_skips_missing_file_and_falls_back(history_stub_factory):
    """最新条目的 .md 文件缺失（如被手工清理）时向前找下一期，而非直接放弃。"""
    stub = StubHistory(
        entries=[
            {"filename": "briefing_ghost.md"},   # 文件不存在
            {"filename": "briefing_ok.md"},
        ],
        files={"briefing_ok.md": PREV_MD},
    )
    history_stub_factory(stub)
    assert "https://news.example.com/old-a" in diff._prev_briefing_markdown()


def test_prev_briefing_prefers_inline_content_when_present(history_stub_factory):
    """兼容假想的内嵌 content 索引格式（优先使用，不重复读文件）。"""
    stub = StubHistory(entries=[{"filename": "briefing_x.md", "content": PREV_MD}])
    history_stub_factory(stub)
    assert "https://news.example.com/old-b" in diff._prev_briefing_markdown()


def test_compute_delta_baseline_without_history(history_stub_factory):
    """无任何存档时输出基线提示（首次运行场景）。"""
    history_stub_factory(StubHistory())
    out = diff.compute_delta({})
    assert "暂无上一期存档" in out


def test_compute_delta_reports_added_and_removed(history_stub_factory):
    """端到端：上期有 old-a/old-b，本期有 old-a+两条新 URL → 报告新增与消失。"""
    stub = StubHistory(
        entries=[{"filename": "briefing_prev.md"}],
        files={"briefing_prev.md": PREV_MD},
    )
    history_stub_factory(stub)

    collected = {
        "cyber_vuln": [
            {"title": "旧闻A续报", "url": "https://news.example.com/old-a"},
            {"title": "新鲜事一", "url": "https://news.example.com/fresh-1",
             "source": "SrcA", "description": "描述一"},
            {"title": "新鲜事二", "url": "https://news.example.com/fresh-2",
             "source": "SrcB", "description": "描述二"},
        ]
    }
    out = diff.compute_delta(collected)

    assert "新增情报（2 条）" in out
    assert "https://news.example.com/fresh-1" in out
    assert "[新鲜事二]" in out
    # 上期有、本期无的 old-b 应进入「本期未收录」清单
    assert "https://news.example.com/old-b" in out
    assert "本期未收录（上期有 1 条）" in out
    # 不应再出现基线提示
    assert "暂无上一期存档" not in out


def test_compute_delta_no_change_when_same_urls(history_stub_factory):
    """两期 URL 集合一致时报「无新增」，不误报。"""
    stub = StubHistory(
        entries=[{"filename": "briefing_prev.md"}],
        files={"briefing_prev.md": PREV_MD},
    )
    history_stub_factory(stub)
    collected = {
        "cyber_vuln": [{"title": "旧闻A续报", "url": "https://news.example.com/old-a"}],
    }
    out = diff.compute_delta(collected)
    assert "本期无相对上期的新条目" in out
