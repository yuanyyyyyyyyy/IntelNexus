"""HackerNews 搜索源测试（现行契约：经共享 Session，输出统一 url 键）。"""
import pytest
from unittest.mock import patch, MagicMock


class TestHackerNewsSource:
    def test_search_normalization(self):
        from intelnexus.core.search.sources.hackernews_source import HackerNewsSource
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "hits": [
                {
                    "title": "Show HN: New Security Tool",
                    "url": "https://github.com/tool",
                    "author": "pg",
                    "points": 150,
                    "num_comments": 42,
                    "objectID": "12345"
                }
            ]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp
        with patch("intelnexus.core.search.sources.hackernews_source.get_session",
                   return_value=mock_session):
            src = HackerNewsSource()
            results = src.search("security tool")
        assert len(results) == 1
        r = results[0]
        assert r["title"] == "Show HN: New Security Tool"
        assert r["url"] == "https://github.com/tool"
        assert r["source"] == "HackerNews"
        assert "pg" in r["description"]

    def test_empty_response(self):
        from intelnexus.core.search.sources.hackernews_source import HackerNewsSource
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"hits": []}
        mock_resp.raise_for_status = MagicMock()
        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp
        with patch("intelnexus.core.search.sources.hackernews_source.get_session",
                   return_value=mock_session):
            src = HackerNewsSource()
            results = src.search("nothing")
        assert results == []
