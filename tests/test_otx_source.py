"""AlienVault OTX 搜索源测试（现行契约：经共享 Session，输出统一 url 键）。"""
import pytest
from unittest.mock import patch, MagicMock


class TestOTXSource:
    def test_search_normalization(self):
        from intelnexus.core.search.sources.otx_source import AlienVaultOTXSource
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "results": [
                {
                    "id": "abc123",
                    "name": "Malicious IP campaign",
                    "description": "Malicious IP detected",
                    "tags": ["malware"],
                }
            ]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp
        with patch("intelnexus.core.search.sources.otx_source.get_session",
                   return_value=mock_session):
            src = AlienVaultOTXSource()
            results = src.search("192.168.1.100")
        assert len(results) == 1
        r = results[0]
        assert r["title"] == "Malicious IP campaign"
        assert "otx.alienvault.com" in r["url"]
        assert r["source"] == "AlienVault_OTX"

    def test_empty_response(self):
        from intelnexus.core.search.sources.otx_source import AlienVaultOTXSource
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"results": []}
        mock_resp.raise_for_status = MagicMock()
        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp
        with patch("intelnexus.core.search.sources.otx_source.get_session",
                   return_value=mock_session):
            src = AlienVaultOTXSource()
            results = src.search("nothing")
        assert results == []
