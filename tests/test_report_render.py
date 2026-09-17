"""P2 渲染一致性回归。

审计背景（报告 INTEL-20260916-001）：
- 报告头部输出「分析模式：smart_general」—— 内部模式名未汉化（mode_labels
  只登记了 "smart"，而 resolve_mode 实际返回 "smart_general"）；
- 舆情趋势的 45/40/15 把异址主体（Courtyard Waldorf）的负面观点计入分母，
  报告自己在方法论声明里承认却仍保留比例。
"""

import pytest


class TestModeLabel:
    def test_smart_general_translated(self):
        from intelnexus.export.report_builder import build_report_overview
        out = build_report_overview("q", "smart_general", "m", {"Bing": 1}, 1)
        assert "**分析模式**：智能通用" in out
        assert "smart_general" not in out

    def test_all_mode_translated(self):
        from intelnexus.export.report_builder import build_report_overview
        out = build_report_overview("q", "all", "m", {"Bing": 1}, 1)
        assert "**分析模式**：全部来源" in out

    def test_unknown_mode_falls_back_to_raw_value(self):
        """未登记的模式名必须原样出现，而不是被误映射成「全部来源」。"""
        from intelnexus.export.report_builder import build_report_overview
        out = build_report_overview("q", "some_future_mode", "m", {"Bing": 1}, 1)
        assert "**分析模式**：some_future_mode" in out

    def test_mode_description_covers_smart_general(self):
        from intelnexus.core.search.modes import get_mode_description
        assert "全部来源" != get_mode_description("smart_general")


class TestSentimentPrompt:
    def test_prompt_forbids_attributing_other_subjects(self):
        from intelnexus.core.llm.core import _build_system_prompt
        prompt = _build_system_prompt("q", "all")
        assert "其他主体" in prompt
        assert "分母" in prompt or "不得计入" in prompt
