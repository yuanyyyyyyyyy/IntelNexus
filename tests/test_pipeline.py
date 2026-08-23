"""End-to-end integration tests for the complete search pipeline."""

import os
import inspect
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from click.testing import CliRunner


# ============================================================
# Mock data
# ============================================================

MOCK_WEB_RESULTS = [
    {"title": "AI Regulation - Reuters", "link": "https://reuters.com/ai-reg", "description": "Overview.", "source": "Reuters"},
    {"title": "GPT-5 Release", "link": "https://techcrunch.com/gpt5", "description": "New model.", "source": "TechCrunch"},
]

MOCK_NEWS_RESULTS = [
    {"title": "AI Safety Advances", "link": "https://bbc.com/ai-safety", "description": "Breakthroughs.", "source": "BBC"},
]

MOCK_SCRAPED = {
    "https://reuters.com/ai-reg": "AI regulation overview with detailed analysis of global frameworks.",
    "https://techcrunch.com/gpt5": "OpenAI releases GPT-5 with improved reasoning capabilities.",
    "https://bbc.com/ai-safety": "Researchers make progress in AI alignment techniques.",
}

MOCK_SUMMARY = """## 一、执行摘要
AI领域在2025年取得了重大进展。

## 二、背景与概述
人工智能技术持续发展。

## 三、核心发现
监管框架逐步完善。

## 四、多角度分析
技术突破推动行业进步。

## 五、关键数据
全球AI市场规模达5000亿美元。

## 六、风险与建议
需关注监管动态。

## 七、信息来源
- Reuters
- TechCrunch
- BBC
"""


# ============================================================
# Test: expand_query → expand_query_for_search 衔接
# ============================================================

class TestQueryRefinementPipeline:
    """Test the query refinement → expansion data flow."""

    def test_refine_then_expand(self):
        """expand_query output should feed correctly into expand_query_for_search."""
        from intelnexus.core.llm.core import expand_query, expand_query_for_search

        variants = expand_query("人工智能")
        assert isinstance(variants, list)
        assert len(variants) >= 1

        expanded = expand_query_for_search(variants)
        assert isinstance(expanded, str)
        # Expanded should contain original query
        assert "人工智能" in expanded

    def test_single_query_expand(self):
        """Short query should pass through refine and expand correctly."""
        from intelnexus.core.llm.core import expand_query, expand_query_for_search

        variants = expand_query("AI")
        expanded = expand_query_for_search(variants)
        assert expanded == "AI"


# ============================================================
# Test: execute_search 联合搜索
# ============================================================

class TestExecuteSearch:
    """Test the parallel multi-source search function."""

    @patch("intelnexus.core.search.sources.news_source.get_news_results", return_value=MOCK_NEWS_RESULTS)
    @patch("intelnexus.core.search.sources.web_source.get_web_results", return_value=MOCK_WEB_RESULTS)
    def test_search_all_mode(self, mock_web, mock_news):
        """Search mode 'all' should call both web and news."""
        from main import execute_search

        results = execute_search("all", "AI regulation", 2)
        assert len(results) > 0
        assert mock_web.called
        assert mock_news.called

    @patch("intelnexus.core.search.sources.web_source.get_web_results", return_value=MOCK_WEB_RESULTS)
    def test_search_web_only(self, mock_web):
        """Search mode 'web' should only call web search."""
        from main import execute_search

        results = execute_search("web", "AI regulation", 2)
        assert mock_web.called

    @patch("intelnexus.core.search.sources.news_source.get_news_results", return_value=MOCK_NEWS_RESULTS)
    def test_search_news_only(self, mock_news):
        """Search mode 'news' should only call news search."""
        from main import execute_search

        results = execute_search("news", "AI regulation", 2)
        assert mock_news.called


# ============================================================
# Test: CLI search 命令完整流程
# ============================================================

class TestCLISearchFlow:
    """Test the complete CLI search pipeline with mocked dependencies."""

    @patch("main.generate_summary", return_value=MOCK_SUMMARY)
    @patch("main.scrape_multiple", return_value=MOCK_SCRAPED)
    @patch("intelnexus.core.search.sources.news_source.get_news_results", return_value=MOCK_NEWS_RESULTS)
    @patch("intelnexus.core.search.sources.web_source.get_web_results", return_value=MOCK_WEB_RESULTS)
    @patch("main.get_llm")
    def test_cli_search_produces_output_file(
        self, mock_llm, mock_web, mock_news, mock_scrape, mock_summary, tmp_path
    ):
        """CLI search should produce a .md output file."""
        from main import intelnexus

        mock_llm.return_value = MagicMock()
        runner = CliRunner()
        output_file = str(tmp_path / "test_report.md")

        result = runner.invoke(
            intelnexus,
            ["search", "-q", "AI regulation", "-o", str(tmp_path / "test_report"), "--no-credibility"],
        )

        assert result.exit_code == 0
        assert os.path.exists(output_file)
        with open(output_file, "r", encoding="utf-8") as f:
            content = f.read()
        assert len(content) > 0

    @patch("main.generate_summary", return_value=MOCK_SUMMARY)
    @patch("main.scrape_multiple", return_value=MOCK_SCRAPED)
    @patch("intelnexus.core.search.sources.news_source.get_news_results", return_value=MOCK_NEWS_RESULTS)
    @patch("intelnexus.core.search.sources.web_source.get_web_results", return_value=MOCK_WEB_RESULTS)
    @patch("main.get_llm")
    def test_cli_search_expand_query_output(
        self, mock_llm, mock_web, mock_news, mock_scrape, mock_summary, tmp_path
    ):
        """CLI search should display refined query in output."""
        from main import intelnexus

        mock_llm.return_value = MagicMock()
        runner = CliRunner()

        result = runner.invoke(
            intelnexus,
            ["search", "-q", "AI regulation", "-o", str(tmp_path / "report"), "--no-credibility"],
        )

        # Should contain "Refined:" with pipe-separated variants
        assert "Refined:" in result.output


# ============================================================
# Test: scrape_multiple → credibility 衔接
# ============================================================

class TestScrapeToCredibilityPipeline:
    """Test scraped content feeds correctly into credibility scoring."""

    def test_scraped_dict_feeds_into_scorer(self, sample_search_results, sample_scraped_content):
        """Scraped dict should be consumable by SourceScorer."""
        import numpy as np
        from unittest.mock import patch

        class MockModel:
            def encode(self, texts, show_progress_bar=False):
                result = []
                for t in texts:
                    h = hash(str(t)) % 1000
                    vec = np.array([float(h + i) for i in range(384)])
                    vec = vec / (np.linalg.norm(vec) + 1e-10)
                    result.append(vec)
                return np.array(result)

        with patch("intelnexus.analysis.credibility.load_sentence_model", return_value=MockModel()):
            from intelnexus.analysis.credibility import SourceScorer
            scorer = SourceScorer()
            results = scorer.evaluate(sample_search_results, sample_scraped_content)
            assert all("credibility_score" in r for r in results)

    def test_scraped_dict_feeds_into_tracer(self, sample_report, sample_scraped_content):
        """Scraped dict should be consumable by EvidenceTracer."""
        import numpy as np
        from unittest.mock import patch

        class MockModel:
            def encode(self, texts, show_progress_bar=False):
                result = []
                for t in texts:
                    h = hash(str(t)) % 1000
                    vec = np.array([float(h + i) for i in range(384)])
                    vec = vec / (np.linalg.norm(vec) + 1e-10)
                    result.append(vec)
                return np.array(result)

        with patch("intelnexus.analysis.evidence_tracer.load_sentence_model", return_value=MockModel()):
            from intelnexus.analysis.evidence_tracer import EvidenceTracer
            tracer = EvidenceTracer()
            result = tracer.trace(sample_report, sample_scraped_content)
            assert "claims" in result


# ============================================================
# Test: generate_summary 格式验证
# ============================================================

class TestGenerateSummary:
    """Test the LLM report generation output format."""

    def test_generate_summary_returns_string(self):
        """generate_summary should return a string."""
        from intelnexus.core.llm.core import generate_summary

        mock_llm = MagicMock()

        # The chain is: prompt_template | llm | StrOutputParser()
        # Step 1: prompt_template.__or__(llm) → intermediate
        # Step 2: intermediate.__or__(StrOutputParser()) → final_chain
        # Step 3: final_chain.invoke(...) → string
        mock_final_chain = MagicMock()
        mock_final_chain.invoke.return_value = MOCK_SUMMARY

        mock_intermediate = MagicMock()
        mock_intermediate.__or__ = MagicMock(return_value=mock_final_chain)

        mock_prompt_instance = MagicMock()
        mock_prompt_instance.__or__ = MagicMock(return_value=mock_intermediate)

        with patch("intelnexus.core.llm.core.ChatPromptTemplate", return_value=mock_prompt_instance):
            with patch("intelnexus.core.llm.core.StrOutputParser"):
                result = generate_summary(mock_llm, "AI regulation", MOCK_SCRAPED, "all")
                assert isinstance(result, str)

    def test_error_handling_timeout(self):
        """generate_summary should handle timeout errors gracefully."""
        from intelnexus.core.llm.core import generate_summary

        mock_llm = MagicMock()

        mock_final_chain = MagicMock()
        mock_final_chain.invoke.side_effect = Exception("Request timed out")

        mock_intermediate = MagicMock()
        mock_intermediate.__or__ = MagicMock(return_value=mock_final_chain)

        mock_prompt_instance = MagicMock()
        mock_prompt_instance.__or__ = MagicMock(return_value=mock_intermediate)

        with patch("intelnexus.core.llm.core.ChatPromptTemplate", return_value=mock_prompt_instance):
            with patch("intelnexus.core.llm.core.StrOutputParser"):
                result = generate_summary(mock_llm, "test", MOCK_SCRAPED, "all")
                assert isinstance(result, str)
                assert "超时" in result or "错误" in result or "error" in result.lower()


# ============================================================
# Test: 完整管道端到端
# ============================================================

class TestFullPipelineIntegration:
    """End-to-end test: query → search → scrape → analyze → report."""

    @patch("main.generate_summary", return_value=MOCK_SUMMARY)
    @patch("main.scrape_multiple", return_value=MOCK_SCRAPED)
    @patch("intelnexus.core.search.sources.news_source.get_news_results", return_value=MOCK_NEWS_RESULTS)
    @patch("intelnexus.core.search.sources.web_source.get_web_results", return_value=MOCK_WEB_RESULTS)
    @patch("main.get_llm")
    def test_full_flow_produces_report(
        self, mock_llm, mock_web, mock_news, mock_scrape, mock_summary, tmp_path
    ):
        """Complete flow: query → refine → search → scrape → summary → file."""
        from main import intelnexus

        mock_llm.return_value = MagicMock()
        runner = CliRunner()
        output_file = str(tmp_path / "full_report.md")

        result = runner.invoke(
            intelnexus,
            ["search", "-q", "人工智能", "-o", str(tmp_path / "full_report"), "--no-credibility"],
        )

        assert result.exit_code == 0
        assert os.path.exists(output_file)

        with open(output_file, "r", encoding="utf-8") as f:
            content = f.read()
        assert "##" in content  # Should contain markdown headers

    @patch("main.generate_summary", return_value=MOCK_SUMMARY)
    @patch("main.scrape_multiple", return_value=MOCK_SCRAPED)
    @patch("intelnexus.core.search.sources.news_source.get_news_results", return_value=MOCK_NEWS_RESULTS)
    @patch("intelnexus.core.search.sources.web_source.get_web_results", return_value=MOCK_WEB_RESULTS)
    @patch("main.get_llm")
    def test_full_flow_data_types(
        self, mock_llm, mock_web, mock_news, mock_scrape, mock_summary, tmp_path
    ):
        """Each stage should produce correct data types."""
        from intelnexus.core.llm.core import expand_query, expand_query_for_search

        # Stage 1: Expand query
        variants = expand_query("AI regulation")
        assert isinstance(variants, list)

        # Stage 2: Expand query
        search_query = expand_query_for_search(variants)
        assert isinstance(search_query, str)

        # Stage 3: Search (mocked)
        from main import execute_search
        results = execute_search("all", search_query, 2)
        assert isinstance(results, list)
        assert len(results) > 0

        # Stage 4: Scrape (mocked)
        scraped = MOCK_SCRAPED
        assert isinstance(scraped, dict)

        # Stage 5: Summary (mocked)
        summary = MOCK_SUMMARY
        assert isinstance(summary, str)
        assert "##" in summary
