"""知识库闭环集成点测试：RAG 注入搜索报告 / 简报 prompt 注入 kb_context。"""

from unittest.mock import patch

from intelnexus.briefing.analyzer import AIBriefingAnalyzer
from intelnexus.briefing.prompts import get_prompt
from intelnexus.core.llm.core import _build_augmented_content


class TestSearchReportKbContext:
    def test_augmented_content_appends_kb_section(self):
        out = _build_augmented_content("正文", kb_context="- 历史收藏条目")
        assert "=== 历史知识库参考" in out
        assert "- 历史收藏条目" in out

    def test_no_kb_context_unchanged(self):
        out = _build_augmented_content("正文", kb_context="")
        assert "历史知识库参考" not in out


class TestBriefingKbContext:
    def test_get_prompt_appends_kb_block(self):
        prompt = get_prompt("top3", search_results="结果", kb_context="- 旧收藏")
        assert "用户历史知识库收藏" in prompt
        assert "- 旧收藏" in prompt
        assert "结果" in prompt

    def test_get_prompt_without_kb_unchanged(self):
        prompt = get_prompt("top3", search_results="结果")
        assert "历史知识库收藏" not in prompt

    def test_run_prompt_forwards_kb_context(self, mock_llm):
        analyzer = AIBriefingAnalyzer(mock_llm)
        analyzer._kb_context = "- 旧收藏上下文"

        captured = {}

        def fake_get_prompt(prompt_name, **kwargs):
            captured.update(kwargs)
            return "生成内容占位"

        with patch("intelnexus.briefing.analyzer.get_prompt", side_effect=fake_get_prompt):
            analyzer._run_prompt(
                "ai_dynamic",
                [{"title": "t", "url": "u", "source": "s"}],
                mock_llm, "system")

        assert captured.get("kb_context") == "- 旧收藏上下文"
        assert captured.get("search_results")
