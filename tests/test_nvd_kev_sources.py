"""NVD 与 CISA KEV 搜索源测试。"""
import pytest
from unittest.mock import patch, MagicMock


class TestNVDSource:
    def test_search_normalization(self):
        from intelnexus.core.search.sources.nvd_source import NVDSearchSource
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "vulnerabilities": [
                {
                    "cve": {
                        "id": "CVE-2025-12345",
                        "descriptions": [{"lang": "en", "value": "Test vuln description"}],
                        "metrics": {
                            "cvssMetricV31": [{"cvssData": {"baseScore": 9.8}}]
                        }
                    }
                }
            ]
        }
        mock_resp.raise_for_status = MagicMock()
        with patch("intelnexus.core.search.sources.nvd_source.requests.get", return_value=mock_resp):
            src = NVDSearchSource()
            results = src.search("test query", max_results=5)
        assert len(results) == 1
        r = results[0]
        assert r["title"] == "CVE-2025-12345 (CVSS 9.8)"
        assert "nvd.nist.gov" in r["link"]
        assert r["source"] == "NVD"
        assert r["category"] == "web"

    def test_empty_response(self):
        from intelnexus.core.search.sources.nvd_source import NVDSearchSource
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"vulnerabilities": []}
        mock_resp.raise_for_status = MagicMock()
        with patch("intelnexus.core.search.sources.nvd_source.requests.get", return_value=mock_resp):
            src = NVDSearchSource()
            results = src.search("nothing")
        assert results == []


class TestCISAKEVSource:
    def test_search_filtering(self):
        from intelnexus.core.search.sources.cisa_kev_source import CISAKEVSource
        vulns = [
            {"cveID": "CVE-2025-0001", "vendorProject": "VendorA", "product": "ProdX",
             "shortDescription": "Remote code execution", "dueDate": "2025-12-01", "requiredAction": "Patch"},
            {"cveID": "CVE-2025-0002", "vendorProject": "VendorB", "product": "ProdY",
             "shortDescription": "SQL injection", "dueDate": "2025-11-01", "requiredAction": "Update"},
        ]
        src = CISAKEVSource()
        src._cache = vulns
        src._cache_time = 999999999999
        results = src.search("VendorA")
        assert len(results) == 1
        assert "CVE-2025-0001" in results[0]["title"]

    def test_cache_hit(self):
        from intelnexus.core.search.sources.cisa_kev_source import CISAKEVSource
        import time
        src = CISAKEVSource()
        src._cache = [{"cveID": "CVE-2025-9999", "vendorProject": "V", "product": "P",
                        "shortDescription": "Test"}]
        src._cache_time = time.time()
        with patch("intelnexus.core.search.sources.cisa_kev_source.requests.get") as mock_get:
            results = src.search("CVE-2025-9999")
            mock_get.assert_not_called()
        assert len(results) == 1
