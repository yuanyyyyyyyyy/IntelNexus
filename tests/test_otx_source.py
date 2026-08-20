"""AlienVault OTX 搜索源测试。"""
import pytest
from unittest.mock import patch, MagicMock


class TestOTXSource:
    def test_search_normalization(self):
        from intelnexus.core.search.sources.otx_source import AlienVaultOTXSource
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "results": [
                {
                    "indicator": "192.168.1.100",
                    "type": "IPv4",
                    "description": "Malicious IP detected"
                }
            ]
        }
        mock_resp.raise_for_status = MagicMock()
        with patch("intelnexus.core.search.sources.otx_source.requests.get", return_value=mock_resp):
            src = AlienVaultOTXSource()
            results = src.search("192.168.1.100")
        assert len(results) == 1
        r = results[0]
        assert r["title"] == "192.168.1.100 (IPv4)"
        assert "otx.alienvault.com" in r["link"]
        assert r["source"] == "AlienVault_OTX"

    def test_empty_response(self):
        from intelnexus.core.search.sources.otx_source import AlienVaultOTXSource
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"results": []}
        mock_resp.raise_for_status = MagicMock()
        with patch("intelnexus.core.search.sources.otx_source.requests.get", return_value=mock_resp):
            src = AlienVaultOTXSource()
            results = src.search("nothing")
        assert results == []
