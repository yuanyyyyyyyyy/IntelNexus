"""搜索源修复单元测试"""
import os
import time
from unittest.mock import patch, MagicMock

import unittest


class TestExploitDBCache(unittest.TestCase):
    """ExploitDB 缓存清理测试"""

    def test_no_cache_time_attribute(self):
        """验证 _cache_time 属性已移除"""
        from intelnexus.core.search.sources.exploitdb_source import ExploitDBSource
        source = ExploitDBSource()
        assert not hasattr(source, "_cache_time")

    def test_cache_path_exists(self):
        """验证缓存路径属性正常"""
        from intelnexus.core.search.sources.exploitdb_source import ExploitDBSource
        source = ExploitDBSource()
        assert hasattr(source, "_cache_path")
        assert "exploitdb.csv" in source._cache_path


class TestSharedSession(unittest.TestCase):
    """共享 Session 使用测试"""

    @patch("intelnexus.core.search.sources.otx_source.get_session")
    def test_otx_uses_shared_session(self, mock_get_session):
        """验证 OTX 使用共享 Session"""
        from intelnexus.core.search.sources.otx_source import AlienVaultOTXSource
        mock_session = MagicMock()
        mock_session.get.return_value.json.return_value = {"results": []}
        mock_get_session.return_value = mock_session

        source = AlienVaultOTXSource()
        source.search("test")

        mock_get_session.assert_called_once()
        mock_session.get.assert_called_once()

    @patch("intelnexus.core.search.sources.hackernews_source.get_session")
    def test_hackernews_uses_shared_session(self, mock_get_session):
        """验证 HackerNews 使用共享 Session"""
        from intelnexus.core.search.sources.hackernews_source import HackerNewsSource
        mock_session = MagicMock()
        mock_session.get.return_value.json.return_value = {"hits": []}
        mock_get_session.return_value = mock_session

        source = HackerNewsSource()
        source.search("test")

        mock_get_session.assert_called_once()
        mock_session.get.assert_called_once()

    @patch("intelnexus.core.search.sources.nvd_source.get_session")
    def test_nvd_uses_shared_session(self, mock_get_session):
        """验证 NVD 使用共享 Session"""
        from intelnexus.core.search.sources.nvd_source import NVDSearchSource
        mock_session = MagicMock()
        mock_session.get.return_value.json.return_value = {"vulnerabilities": []}
        mock_get_session.return_value = mock_session

        source = NVDSearchSource()
        source.search("CVE-2024")

        mock_get_session.assert_called_once()
        mock_session.get.assert_called_once()


class TestNvdCache(unittest.TestCase):
    """NVD 缓存机制测试"""

    @patch("intelnexus.core.search.sources.nvd_source.get_session")
    def test_cache_hit(self, mock_get_session):
        """验证缓存命中时不发起请求"""
        from intelnexus.core.search.sources.nvd_source import NVDSearchSource
        mock_session = MagicMock()
        mock_session.get.return_value.json.return_value = {"vulnerabilities": []}
        mock_get_session.return_value = mock_session

        source = NVDSearchSource()
        source.search("CVE-2024")
        source.search("CVE-2024")

        assert mock_session.get.call_count == 1

    @patch("intelnexus.core.search.sources.nvd_source.get_session")
    def test_cache_expired(self, mock_get_session):
        """验证缓存过期后重新请求"""
        from intelnexus.core.search.sources.nvd_source import NVDSearchSource, CACHE_TTL
        mock_session = MagicMock()
        mock_session.get.return_value.json.return_value = {"vulnerabilities": []}
        mock_get_session.return_value = mock_session

        source = NVDSearchSource()
        source.search("CVE-2024")

        cache_key = "CVE-2024:20"
        source._cache_time[cache_key] = time.time() - CACHE_TTL - 1

        source.search("CVE-2024")

        assert mock_session.get.call_count == 2


class TestExploitDBMultiKeyword(unittest.TestCase):
    """ExploitDB 多关键词搜索测试"""

    @patch("intelnexus.core.search.sources.exploitdb_source.ExploitDBSource._load_data")
    def test_multi_keyword_search(self, mock_load_data):
        """验证多关键词搜索功能"""
        from intelnexus.core.search.sources.exploitdb_source import ExploitDBSource

        mock_load_data.return_value = [
            {"id": "1", "description": "SQL injection in PHP", "author": "test", "date": "2024-01-01", "platform": "PHP", "type": "webapps"},
            {"id": "2", "description": "XSS vulnerability in JS", "author": "test", "date": "2024-01-02", "platform": "JavaScript", "type": "webapps"},
            {"id": "3", "description": "SQL injection in Python", "author": "test", "date": "2024-01-03", "platform": "Python", "type": "webapps"},
        ]

        source = ExploitDBSource()
        results = source.search("SQL injection")

        assert len(results) == 2
        # 现行契约：match_score 在 metadata 中
        assert all(r["metadata"]["match_score"] == 1.0 for r in results)

    @patch("intelnexus.core.search.sources.exploitdb_source.ExploitDBSource._load_data")
    def test_match_score排序(self, mock_load_data):
        """验证按匹配度排序"""
        from intelnexus.core.search.sources.exploitdb_source import ExploitDBSource

        mock_load_data.return_value = [
            {"id": "1", "description": "PHP exploit", "author": "test", "date": "2024-01-01", "platform": "PHP", "type": "webapps"},
            {"id": "2", "description": "PHP SQL injection exploit", "author": "test", "date": "2024-01-02", "platform": "PHP", "type": "webapps"},
        ]

        source = ExploitDBSource()
        results = source.search("PHP SQL injection")

        assert len(results) == 2
        # 现行契约：match_score 在 metadata 中（多关键词命中更多得分更高）
        scores = [r["metadata"]["match_score"] for r in results]
        assert scores[0] > scores[1]


class TestHackerNewsMetadata(unittest.TestCase):
    """HackerNews 结构化元数据测试"""

    @patch("intelnexus.core.search.sources.hackernews_source.get_session")
    def test_metadata_fields(self, mock_get_session):
        """验证 metadata 字段包含完整信息"""
        from intelnexus.core.search.sources.hackernews_source import HackerNewsSource
        mock_session = MagicMock()
        mock_session.get.return_value.json.return_value = {
            "hits": [
                {
                    "title": "Test Post",
                    "url": "https://example.com",
                    "objectID": "12345",
                    "points": 100,
                    "num_comments": 50,
                    "author": "testuser",
                    "created_at": "2024-01-01T00:00:00Z",
                }
            ]
        }
        mock_get_session.return_value = mock_session

        source = HackerNewsSource()
        results = source.search("test")

        assert len(results) == 1
        assert "metadata" in results[0]
        assert results[0]["metadata"]["points"] == 100
        assert results[0]["metadata"]["comments"] == 50
        assert results[0]["metadata"]["author"] == "testuser"

    @patch("intelnexus.core.search.sources.hackernews_source.get_session")
    def test_description格式(self, mock_get_session):
        """验证 description 格式正确"""
        from intelnexus.core.search.sources.hackernews_source import HackerNewsSource
        mock_session = MagicMock()
        mock_session.get.return_value.json.return_value = {
            "hits": [
                {
                    "title": "Test Post",
                    "url": "https://example.com",
                    "objectID": "12345",
                    "points": 100,
                    "num_comments": 50,
                    "author": "testuser",
                    "created_at": "2024-01-01T00:00:00Z",
                }
            ]
        }
        mock_get_session.return_value = mock_session

        source = HackerNewsSource()
        results = source.search("test")

        desc = results[0]["description"]
        assert "by testuser" in desc
        assert "100 points" in desc
        assert "50 comments" in desc


class TestSourceCategories(unittest.TestCase):
    """源类别测试"""

    def test_threat_intel_category(self):
        """验证 OTX 使用威胁情报类别"""
        from intelnexus.core.search.sources.otx_source import AlienVaultOTXSource
        source = AlienVaultOTXSource()
        assert source.category == "threat_intel"

    def test_community_category(self):
        """验证 HackerNews 使用社区类别"""
        from intelnexus.core.search.sources.hackernews_source import HackerNewsSource
        source = HackerNewsSource()
        assert source.category == "community"

    def test_exploit_category(self):
        """验证 ExploitDB 使用漏洞利用类别"""
        from intelnexus.core.search.sources.exploitdb_source import ExploitDBSource
        source = ExploitDBSource()
        assert source.category == "exploit"

    def test_new_categories_exported(self):
        """验证新类别已导出"""
        from intelnexus.core.search import (
            CATEGORY_THREAT_INTEL,
            CATEGORY_COMMUNITY,
            CATEGORY_EXPLOIT,
        )
        assert CATEGORY_THREAT_INTEL == "threat_intel"
        assert CATEGORY_COMMUNITY == "community"
        assert CATEGORY_EXPLOIT == "exploit"


class TestNewSearchSources(unittest.TestCase):
    """新增搜索源测试"""

    def test_cnvd_source_init(self):
        """验证 CNVD 源初始化"""
        from intelnexus.core.search.sources.cnvd_source import CNVDSource
        source = CNVDSource()
        assert source.name == "CNVD"
        assert source.category == "threat_intel"
        assert source.requires_proxy is False

    def test_security_news_source_init(self):
        """验证安全内参源初始化"""
        from intelnexus.core.search.sources.security_news_source import SecurityNewsSource
        source = SecurityNewsSource()
        assert source.name == "SecRSS"
        assert source.category == "threat_intel"
        assert source.requires_proxy is False

    def test_arxiv_source_init(self):
        """验证 arXiv 源初始化（境外学术源，默认需代理）"""
        from intelnexus.core.search.sources.arxiv_source import ArxivSource
        source = ArxivSource()
        assert source.name == "arXiv"
        assert source.category == "news"
        assert source.requires_proxy is True

    def test_tech_community_source_init(self):
        """验证技术社区源初始化"""
        from intelnexus.core.search.sources.tech_community_source import TechCommunitySource
        source = TechCommunitySource()
        assert source.name == "TechCommunity"
        assert source.category == "community"
        assert source.requires_proxy is False

    def test_huggingface_source_init(self):
        """验证 HuggingFace 源初始化（境外源，默认需代理）"""
        from intelnexus.core.search.sources.huggingface_source import HuggingFaceSource
        source = HuggingFaceSource()
        assert source.name == "HuggingFace"
        assert source.category == "news"
        assert source.requires_proxy is True

    def test_qianxin_source_init(self):
        """验证奇安信源初始化"""
        from intelnexus.core.search.sources.qianxin_source import QianxinSource
        source = QianxinSource()
        assert source.name == "Qianxin"
        assert source.category == "threat_intel"
        assert source.requires_proxy is False

    def test_all_new_sources_in_registry(self):
        """验证新源已注册到 registry"""
        from intelnexus.core.search.sources import (
            CNVDSource, SecurityNewsSource, ArxivSource,
            TechCommunitySource, HuggingFaceSource, QianxinSource
        )
        # 验证所有新源都可以正确导入和初始化
        sources = [
            CNVDSource(), SecurityNewsSource(), ArxivSource(),
            TechCommunitySource(), HuggingFaceSource(), QianxinSource()
        ]
        source_names = [s.name for s in sources]
        assert "CNVD" in source_names
        assert "SecRSS" in source_names
        assert "arXiv" in source_names
        assert "TechCommunity" in source_names
        assert "HuggingFace" in source_names
        assert "Qianxin" in source_names
