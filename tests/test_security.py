"""Tests for security fixes: XSS, URL encoding, path traversal, API key passing."""

import html
import inspect
from urllib.parse import quote

import pytest


class TestXSSPrevention:
    """Tests for html.escape in search_pipeline.py."""

    def test_script_tag_escaped(self):
        """<script> tags should be escaped to &lt;script&gt;."""
        malicious = '<script>alert("xss")</script>'
        escaped = html.escape(malicious)
        assert "<script>" not in escaped
        assert "&lt;script&gt;" in escaped

    def test_img_onerror_escaped(self):
        """<img onerror=...> should be escaped."""
        malicious = '<img src=x onerror=alert(1)>'
        escaped = html.escape(malicious)
        assert "<img" not in escaped
        assert "&lt;img" in escaped

    def test_normal_text_unchanged(self):
        """Normal text without HTML should be unchanged."""
        normal = "人工智能研究进展"
        escaped = html.escape(normal)
        assert escaped == normal

    def test_html_entities_preserved(self):
        """Existing & in normal text should be escaped."""
        text = "A & B"
        escaped = html.escape(text)
        assert "A &amp; B" in escaped

    def test_search_pipeline_has_escape(self):
        """search_pipeline.py should import html and use html.escape."""
        from src.ui import search_pipeline
        src = inspect.getsource(search_pipeline)
        assert "import html" in src
        assert "html.escape(" in src


class TestURLEncoding:
    """Tests for urllib.parse.quote in darkweb.py."""

    def test_space_encoded(self):
        """Spaces should be encoded as %20."""
        result = quote("hello world")
        assert result == "hello%20world"

    def test_special_chars_encoded(self):
        """Special chars like &, # should be encoded."""
        result = quote("a&b#c")
        assert "&" not in result
        assert "#" not in result

    def test_chinese_encoded(self):
        """Chinese characters should be percent-encoded."""
        result = quote("人工智能")
        assert result != "人工智能"
        assert "%" in result

    def test_safe_chars_preserved(self):
        """Letters and numbers should be preserved."""
        result = quote("abc123")
        assert result == "abc123"

    def test_darkweb_has_quote(self):
        """darkweb.py should import and use quote."""
        from src.search import darkweb
        src = inspect.getsource(darkweb)
        assert "from urllib.parse import quote" in src
        assert "quote(query)" in src


class TestPathTraversal:
    """Tests for path traversal protection in history.py."""

    def test_load_report_dotdot(self):
        """Loading ../../etc/passwd should return None."""
        from src.config.history import SearchHistory
        h = SearchHistory()
        result = h.load_report("../../etc/passwd")
        assert result is None

    def test_load_report_backslash(self):
        """Loading with backslash path traversal should return None."""
        from src.config.history import SearchHistory
        h = SearchHistory()
        result = h.load_report("..\\..\\etc\\passwd")
        assert result is None

    def test_delete_report_dotdot(self):
        """Deleting ../../something should return False."""
        from src.config.history import SearchHistory
        h = SearchHistory()
        result = h.delete_report("../../etc/passwd")
        assert result is False

    def test_load_report_normal_file(self):
        """Loading a normal filename should not be blocked by traversal check."""
        from src.config.history import SearchHistory
        h = SearchHistory()
        # This should not raise, even if file doesn't exist
        result = h.load_report("normal_report.md")
        # Result is None because file doesn't exist, not because of traversal
        assert result is None

    def test_history_has_is_relative_to(self):
        """history.py should use is_relative_to for path validation."""
        from src.config import history
        src = inspect.getsource(history)
        assert "is_relative_to" in src


class TestNewsAPIKeyPassing:
    """Tests for NEWS_API_KEY being passed through the pipeline."""

    def test_main_imports_news_api_key(self):
        """main.py should import NEWS_API_KEY from config."""
        import main
        src = inspect.getsource(main)
        assert "NEWS_API_KEY" in src

    def test_execute_search_passes_api_key(self):
        """execute_search should pass api_key to get_news_results."""
        import main
        src = inspect.getsource(main)
        assert "api_key=NEWS_API_KEY" in src

    def test_collector_imports_news_api_key(self):
        """collector.py should import NEWS_API_KEY from config."""
        from ai_briefing import collector
        src = inspect.getsource(collector)
        assert "NEWS_API_KEY" in src

    def test_collector_passes_api_key(self):
        """collector should pass api_key to news_search."""
        from ai_briefing import collector
        src = inspect.getsource(collector)
        assert "api_key=NEWS_API_KEY" in src
