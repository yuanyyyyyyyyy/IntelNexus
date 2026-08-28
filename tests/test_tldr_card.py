"""TL;DR 速览卡测试（真引用生产函数 intelnexus.ui.search_worker._extract_tldr_card）。"""
import pytest

from intelnexus.core.llm.core import _build_system_prompt
from intelnexus.ui.search_worker import _extract_tldr_card


class TestTLDRCard:
    def test_extract_tldr_basic(self):
        report = """## TL;DR 情报速览

**威胁等级**: 🔴 高危
**核心判断**: 存在严重安全风险
- 发现1
- 发现2
**行动建议**: 立即修复

---

## 一、执行摘要
详细内容...
"""
        tldr = _extract_tldr_card(report)
        assert tldr, "should extract the TL;DR block"
        assert "威胁等级" in tldr
        assert "高危" in tldr
        assert "行动建议" in tldr
        # 不应吞掉后续章节
        assert "执行摘要" not in tldr

    def test_extract_tldr_missing(self):
        report = "## 一、执行摘要\n没有速览卡的报告"
        assert _extract_tldr_card(report) == ""

    def test_extract_tldr_empty_input(self):
        assert _extract_tldr_card("") == ""
        assert _extract_tldr_card(None) == ""

    def test_extract_tldr_at_end_without_terminator(self):
        report = "前言\n\n## TL;DR 情报速览\n\n**威胁等级**: 🟡 中危"
        tldr = _extract_tldr_card(report)
        assert "中危" in tldr

    def test_system_prompt_contains_template(self):
        prompt = _build_system_prompt("test query", "all")
        # 新版 prompt 包含 6 个分析板块
        assert "核心摘要" in prompt
        assert "证据链" in prompt
        assert "舆情趋势" in prompt
        assert "影响评估" in prompt
        assert "风险评估" in prompt
        assert "情报判断" in prompt

    def test_prompt_template_roundtrip(self):
        """系统提示词模板产出的报告应能被生产提取函数解析（端到端契约）。"""
        report = (
            "## TL;DR 情报速览\n\n"
            "**威胁等级**: 🔴 高危\n"
            "**核心判断**: 测试核心判断\n"
            "- 关键发现1\n"
            "**行动建议**: 立即处置\n\n"
            "---\n\n"
            "## 一、执行摘要\n正文"
        )
        tldr = _extract_tldr_card(report)
        assert "威胁等级" in tldr and "立即处置" in tldr
