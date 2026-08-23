"""Tests for query refinement and expansion logic."""

import pytest
from intelnexus.core.llm.core import expand_query, expand_query_for_search


class TestRefineQuery:
    """Tests for expand_query()."""

    def test_short_query_no_expand(self):
        """Queries shorter than 3 chars should not be expanded."""
        result = expand_query("AI")
        assert result == ["AI"]

    def test_single_char_query(self):
        result = expand_query("x")
        assert result == ["x"]

    def test_empty_query(self):
        result = expand_query("")
        assert result == [""]

    def test_chinese_query_expands(self):
        """Chinese queries should get exactly one English cross-language variant."""
        result = expand_query("人工智能")
        assert "人工智能" in result
        assert any("English" in q for q in result)
        # Only ONE cross-language variant is added to avoid search-engine overload
        assert len(result) == 2

    def test_english_query_expands(self):
        """English queries should get exactly one Chinese cross-language variant."""
        result = expand_query("machine learning")
        assert "machine learning" in result
        assert any("中文" in q for q in result)
        # Only ONE cross-language variant is added to avoid search-engine overload
        assert len(result) == 2

    def test_mixed_language_query(self):
        """Mixed Chinese+English should expand."""
        result = expand_query("AI人工智能")
        assert "AI人工智能" in result
        assert len(result) >= 2

    def test_typo_fix_sarch(self):
        result = expand_query("sarch engine")
        assert "search engine" in result

    def test_typo_fix_serach(self):
        result = expand_query("serach results")
        assert "search results" in result

    def test_typo_fix_reuslt(self):
        result = expand_query("reuslt analysis")
        assert "result analysis" in result

    def test_typo_fix_resutl(self):
        result = expand_query("resutl processing")
        assert "result processing" in result

    def test_returns_list(self):
        """expand_query always returns a list."""
        result = expand_query("test query")
        assert isinstance(result, list)

    def test_original_always_first(self):
        """Original query (after typo fix) should always be the first element."""
        result = expand_query("machine learning trends")
        assert result[0] == "machine learning trends"

    def test_whitespace_stripped(self):
        """Leading/trailing whitespace should be stripped."""
        result = expand_query("  hello world  ")
        assert result[0] == "hello world"


class TestExpandQueryForSearch:
    """Tests for expand_query_for_search()."""

    def test_single_query(self):
        result = expand_query_for_search(["AI"])
        assert result == "AI"

    def test_multiple_queries(self):
        """多语言变体不再 OR 拼接（会稀释意图），仅取首个最贴近原意的变体。"""
        result = expand_query_for_search(["AI", "AI English", "AI news"])
        assert result == "AI"

    def test_string_passthrough(self):
        """If input is already a string, return as-is."""
        result = expand_query_for_search("AI | AI English")
        assert result == "AI | AI English"

    def test_empty_list(self):
        result = expand_query_for_search([])
        assert result == ""
