"""NVD 与 CISA KEV 搜索源测试（现行契约：经共享 Session，输出统一 url 键）。"""
import time
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
        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp
        with patch("intelnexus.core.search.sources.nvd_source.get_session",
                   return_value=mock_session):
            src = NVDSearchSource()
            results = src.search("test query", max_results=5)
        assert len(results) == 1
        r = results[0]
        assert r["title"] == "CVE-2025-12345 (CVSS 9.8)"
        assert "nvd.nist.gov" in r["url"]
        assert r["source"] == "NVD"
        # BaseSearchSource 默认类别为 web
        assert r["category"] == src.category

    def test_empty_response(self):
        from intelnexus.core.search.sources.nvd_source import NVDSearchSource
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"vulnerabilities": []}
        mock_resp.raise_for_status = MagicMock()
        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp
        with patch("intelnexus.core.search.sources.nvd_source.get_session",
                   return_value=mock_session):
            src = NVDSearchSource()
            results = src.search("nothing")
        assert results == []

    def test_request_contract_2_0_endpoint_and_keyword_search(self):
        """契约守卫：2.0 端点 + keywordSearch 参数（2026-09-15 实测 HTTP 200）。

        历史注释称「NVD API查询格式错误（404）」而默认禁用；实测该端点与
        参数完全正常，此用例锁定契约防止回退到旧端点/旧参数名。
        """
        from intelnexus.core.search.sources.nvd_source import NVDSearchSource
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"vulnerabilities": []}
        mock_resp.raise_for_status = MagicMock()
        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp
        with patch("intelnexus.core.search.sources.nvd_source.get_session",
                   return_value=mock_session):
            NVDSearchSource().search("log4j", max_results=10)

        args, kwargs = mock_session.get.call_args
        assert args[0] == NVDSearchSource.BASE_URL
        assert NVDSearchSource.BASE_URL.endswith("/rest/json/cves/2.0")
        assert kwargs["params"]["keywordSearch"] == "log4j"
        assert kwargs["params"]["resultsPerPage"] <= 40


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
        # 现行缓存契约：_cache 为整表列表，_cache_time 为时间戳（需在 TTL 内）
        src._cache = vulns
        src._cache_time = time.time()
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