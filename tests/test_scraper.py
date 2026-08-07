"""
网页内容抓取层测试（shared/search/scraper.py）。

覆盖：
- scrape_single 缓存命中直接返回
- PDF 链接跳过真实请求，返回占位文本
- 正常 HTML 解析（mock requests.get / get_tor_session）
- 短文本（<100）回退为 title
- scrape_multiple 并发聚合 + 超长截断（>3000 字符）
- .onion 链接走 Tor session

所有 requests / cache / tor 均 mock，离线、快速、确定性。
"""
import sys
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))

from shared.search import scraper as scraper_module


def _html_response(text, status=200, encoding=None):
    resp = MagicMock()
    resp.status_code = status
    resp.text = text
    resp.encoding = encoding
    return resp


SAMPLE_HTML = """
<html><head><title>t</title></head><body>
<script>var x=1;</script>
<style>.a{color:red}</style>
<p>IntelNexus 是一个 AI 驱动的多源网络情报分析平台，支持网页、新闻与暗网检索，
并集成可信度评估、知识图谱与证据链溯源能力。该平台提供实时情报聚合、自动摘要、
来源可信度打分、跨源冲突检测与证据链溯源，帮助用户快速识别高价值信号并降低噪声干扰，
适用于安全运营、态势感知与开源情报研究等多种场景，显著提升分析效率与决策质量。</p>
</body></html>
"""


class TestScrapeSingle:
    def test_cache_hit_returns_cached(self):
        url_data = {"link": "https://news.example.com/ai", "title": "AI News"}
        with patch("shared.search.scraper.get_cached", return_value="CACHED TEXT"):
            url, content = scraper_module.scrape_single(url_data)
        assert content == "CACHED TEXT"
        assert url == "https://news.example.com/ai"

    def test_pdf_skips_request(self):
        url_data = {"link": "https://news.example.com/report.pdf", "title": "Report"}
        with patch("shared.search.scraper.get_cached", return_value=None) as mock_get, \
             patch("shared.search.scraper.requests.get") as mock_get_req:
            url, content = scraper_module.scrape_single(url_data)
        mock_get_req.assert_not_called()
        assert "PDF文件" in content
        assert content.startswith("Report -")

    def test_pdf_with_query_param_skips_request(self):
        url_data = {"link": "https://x.com/a.pdf?token=1", "title": "T"}
        with patch("shared.search.scraper.get_cached", return_value=None), \
             patch("shared.search.scraper.requests.get") as mock_get_req:
            _, content = scraper_module.scrape_single(url_data)
        mock_get_req.assert_not_called()
        assert "PDF文件" in content

    def test_normal_html_parsing(self):
        url_data = {"link": "https://news.example.com/ai", "title": "AI News"}
        resp = _html_response(SAMPLE_HTML)
        with patch("shared.search.scraper.get_cached", return_value=None), \
             patch("shared.search.scraper.requests.get", return_value=resp):
            url, content = scraper_module.scrape_single(url_data)
        assert "AI 驱动" in content
        assert "var x=1" not in content  # script 被移除
        assert content.startswith("AI News -")

    def test_short_text_falls_back_to_title(self):
        url_data = {"link": "https://news.example.com/x", "title": "Short Title"}
        # 解析后文本 < 100 字符
        resp = _html_response("<html><body><p>tiny</p></body></html>")
        with patch("shared.search.scraper.get_cached", return_value=None), \
             patch("shared.search.scraper.requests.get", return_value=resp):
            _, content = scraper_module.scrape_single(url_data)
        assert content == "Short Title"

    def test_non_200_falls_back_to_title(self):
        url_data = {"link": "https://news.example.com/404", "title": "Missing"}
        resp = _html_response("<html></html>", status=404)
        with patch("shared.search.scraper.get_cached", return_value=None), \
             patch("shared.search.scraper.requests.get", return_value=resp):
            _, content = scraper_module.scrape_single(url_data)
        assert content == "Missing"

    def test_request_exception_falls_back_to_title(self):
        url_data = {"link": "https://news.example.com/err", "title": "Err"}
        with patch("shared.search.scraper.get_cached", return_value=None), \
             patch("shared.search.scraper.requests.get", side_effect=Exception("boom")):
            _, content = scraper_module.scrape_single(url_data)
        assert content == "Err"

    def test_onion_uses_tor_session(self):
        url_data = {"link": "http://abcxyz.onion/page", "title": "Onion"}
        tor_session = MagicMock()
        tor_session.get.return_value = _html_response(SAMPLE_HTML)
        resp = _html_response(SAMPLE_HTML)
        with patch("shared.search.scraper.get_cached", return_value=None), \
             patch("shared.search.scraper.get_tor_session", return_value=tor_session), \
             patch("shared.search.scraper.requests.get", return_value=resp) as mock_direct:
            _, content = scraper_module.scrape_single(url_data)
        tor_session.get.assert_called_once()
        mock_direct.assert_not_called()
        assert "AI 驱动" in content

    def test_encoding_fix_for_iso8859(self):
        url_data = {"link": "https://news.example.com/enc", "title": "Enc"}
        resp = _html_response(SAMPLE_HTML, encoding="iso-8859-1")
        resp.apparent_encoding = "utf-8"
        with patch("shared.search.scraper.get_cached", return_value=None), \
             patch("shared.search.scraper.requests.get", return_value=resp):
            _, content = scraper_module.scrape_single(url_data)
        # apparent_encoding 被采用，解析仍成功
        assert "AI 驱动" in content


class TestScrapeMultiple:
    def test_aggregates_and_truncates(self):
        long_text = "A" * 5000
        url_data = [
            {"link": "https://news.example.com/a", "title": "A"},
            {"link": "https://news.example.com/b", "title": "B"},
        ]
        resp = _html_response(f"<html><body><p>{long_text}</p></body></html>")
        with patch("shared.search.scraper.get_cached", return_value=None), \
             patch("shared.search.scraper.requests.get", return_value=resp), \
             patch("shared.search.scraper.set_cached") as mock_set:
            results = scraper_module.scrape_multiple(url_data, max_workers=2)
        assert len(results) == 2
        for content in results.values():
            assert content.endswith("...(truncated)")
            assert len(content) == 3000 + len("...(truncated)")
        assert mock_set.called

    def test_empty_input(self):
        with patch("shared.search.scraper.get_cached", return_value=None):
            assert scraper_module.scrape_multiple([]) == {}
