"""HackerNews 搜索源测试。"""
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
        with patch("intelnexus.core.search.sources.hackernews_source.requests.get", return_value=mock_resp):
            src = HackerNewsSource()
            results = src.search("security tool")
        assert len(results) == 1
        r = results[0]
        assert r["title"] == "Show HN: New Security Tool"
        assert r["link"] == "https://github.com/tool"
        assert r["source"] == "HackerNews"
        assert "pg" in r["description"]

    def test_empty_response(self):
        from intelnexus.core.search.sources.hackernews_source import HackerNewsSource
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"hits": []}
        mock_resp.raise_for_status = MagicMock()
        with patch("intelnexus.core.search.sources.hackernews_source.requests.get", return_value=mock_resp):
            src = HackerNewsSource()
            results = src.search("nothing")
        assert results == []
