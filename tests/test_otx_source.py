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

    def test_correct_endpoint_path_and_key_header(self):
        """R18：路由必须是 /api/v1/search/pulses，且携带 X-OTX-API-KEY。"""
        from intelnexus.core.search.sources.otx_source import AlienVaultOTXSource
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"results": []}
        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp
        with patch("intelnexus.core.search.sources.otx_source.get_session",
                   return_value=mock_session):
            src = AlienVaultOTXSource()
            src.search("ransomware")
        args, kwargs = mock_session.get.call_args
        assert "/api/v1/search/pulses" in str(args[0])
        assert kwargs.get("headers", {}).get("X-OTX-API-KEY") == "test-key"

    def test_missing_key_skips_cleanly(self, monkeypatch):
        """R18：未配 key 时优雅跳过，给出可操作提示而非 404 报错。"""
        from intelnexus.core.search.sources.otx_source import AlienVaultOTXSource
        monkeypatch.delenv("OTX_API_KEY", raising=False)
        src = AlienVaultOTXSource()
        results = src.search("ransomware")
        assert results == []
        assert "OTX_API_KEY" in src.last_error
