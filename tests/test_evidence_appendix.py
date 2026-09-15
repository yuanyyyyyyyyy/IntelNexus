"""原始证据附录（板块十五）与包装 URL 解析的回归测试。

覆盖三类缺陷：
1. 证据条目标题恒为空（scraped 为 {url: 正文}，取不到 title），标题位退化为整条 URL；
2. 兜底分支用 r.get("link")，而结果归一化后字段是 url，导致未抓取条目永不入证据；
3. 百度/Bing/Google 跳转包装 URL 未被解析为真实地址，缓存命中路径尤其无法回填。
"""

from unittest.mock import MagicMock, patch

import pytest

BAIDU_WRAPPER = (
    "http://www.baidu.com/link?url=Vn0Y1u5kfihqpXe6SM68SHuTsZ"
    "-_Ya2mkq3OfJXs9AdbZWGz1fIpR4vSHpmvEYrtYAFMDOttXMVqmM_5eeuo0"
)
REAL_URL = "https://tech.example.com/2026/09/free-token"
TITLE = "免费大模型 Token 领取指南"

META_REFRESH_HTML = (
    '<html><head><meta http-equiv="refresh" '
    'content="0;url=https://tech.example.com/real-target"></head>'
    "<body>正在跳转</body></html>"
)


def _resp(url=BAIDU_WRAPPER, text=""):
    resp = MagicMock()
    resp.status_code = 200
    resp.encoding = "utf-8"
    resp.text = text
    resp.url = url
    return resp


# ============================================================================
# 一、证据附录展示层
# ============================================================================

class TestEvidenceAppendixTitle:
    def test_title_comes_from_search_result(self):
        """标题应取搜索结果标题，而不是把 URL 顶到标题位。"""
        from intelnexus.export.report_builder import build_evidence_appendix

        md = build_evidence_appendix(
            {REAL_URL: "阿里云百炼宣布新用户免费额度……"},
            [{"title": TITLE, "url": REAL_URL, "source": "Web"}],
        )
        assert f"[1] **{TITLE}**" in md

    def test_title_line_is_not_the_url(self):
        from intelnexus.export.report_builder import build_evidence_appendix

        md = build_evidence_appendix(
            {BAIDU_WRAPPER: "正文内容"},
            [{"title": TITLE, "url": BAIDU_WRAPPER, "source": "Web"}],
        )
        first_item_line = [ln for ln in md.splitlines() if ln.startswith("[1] ")][0]
        assert BAIDU_WRAPPER not in first_item_line
        assert TITLE in first_item_line

    def test_fallback_title_from_scraped_content(self):
        """无搜索结果可匹配时，用抓取正文首句降级为标题，不得回落到整条 URL。"""
        from intelnexus.export.report_builder import build_evidence_appendix

        body = "阿里云百炼推出新用户免费额度活动，覆盖七十余款主流模型。" * 3
        md = build_evidence_appendix({REAL_URL: body}, [])
        first_item_line = [ln for ln in md.splitlines() if ln.startswith("[1] ")][0]
        assert REAL_URL not in first_item_line
        assert "阿里云百炼" in first_item_line


class TestEvidenceAppendixUrlKey:
    def test_unscraped_result_uses_url_key(self):
        """结果归一化后字段是 url，兜底分支必须按 url 取值。"""
        from intelnexus.export.report_builder import build_evidence_appendix

        md = build_evidence_appendix(
            {},
            [{"title": "未抓取条目标题", "url": "https://news.example.com/x", "source": "News"}],
        )
        assert "未抓取条目标题" in md
        assert "仅元数据" in md

    def test_result_matches_scraped_entry_by_url(self):
        """同一条 URL 只出现一次，且带上标题。"""
        from intelnexus.export.report_builder import build_evidence_appendix

        md = build_evidence_appendix(
            {REAL_URL: "正文"},
            [{"title": TITLE, "url": REAL_URL, "source": "Web"}],
        )
        assert md.count("- URL：") == 1
        assert TITLE in md


class TestEvidenceAppendixDisplay:
    def test_source_domain_shown(self):
        from intelnexus.export.report_builder import build_evidence_appendix

        md = build_evidence_appendix(
            {REAL_URL: "正文"},
            [{"title": TITLE, "url": REAL_URL, "source": "Web"}],
        )
        assert "tech.example.com" in md

    def test_unresolved_wrapper_marked(self):
        """解析不出真实地址的包装链接必须显式标注，不能假装是正常来源。"""
        from intelnexus.export.report_builder import build_evidence_appendix

        md = build_evidence_appendix(
            {BAIDU_WRAPPER: "正文"},
            [{"title": TITLE, "url": BAIDU_WRAPPER, "source": "Web"}],
        )
        assert "跳转包装" in md
        assert "未解析" in md

    def test_real_url_not_marked_unresolved(self):
        from intelnexus.export.report_builder import build_evidence_appendix

        md = build_evidence_appendix(
            {REAL_URL: "正文"},
            [{"title": TITLE, "url": REAL_URL, "source": "Web"}],
        )
        assert "未解析" not in md

    def test_empty_inputs_still_render_placeholder(self):
        from intelnexus.export.report_builder import build_evidence_appendix

        assert "无可用证据材料" in build_evidence_appendix({}, [])


# ============================================================================
# 二、缓存层：resolved_url 持久化
# ============================================================================

class TestCacheResolvedUrl:
    def test_entry_keeps_resolved_url(self, monkeypatch, tmp_path):
        import intelnexus.core.settings.cache as cache_mod

        monkeypatch.setattr(cache_mod, "CACHE_DIR", str(tmp_path))
        cache_mod.set_cached(BAIDU_WRAPPER, "正文", resolved_url=REAL_URL)
        entry = cache_mod.get_cached_entry(BAIDU_WRAPPER)
        assert entry["resolved_url"] == REAL_URL
        # 旧调用方只读正文，行为不变
        assert cache_mod.get_cached(BAIDU_WRAPPER) == "正文"

    def test_entry_without_resolved_url_is_tolerated(self, monkeypatch, tmp_path):
        """旧缓存条目（无 resolved_url 字段）读取不得报错。"""
        import intelnexus.core.settings.cache as cache_mod

        monkeypatch.setattr(cache_mod, "CACHE_DIR", str(tmp_path))
        cache_mod.set_cached(REAL_URL, "正文")
        assert cache_mod.get_cached(REAL_URL) == "正文"
        assert cache_mod.get_cached_entry(REAL_URL).get("resolved_url") is None


# ============================================================================
# 三、抓取层：真实地址解析
# ============================================================================

class TestScrapeSingleResolve:
    def test_cache_hit_backfills_resolved_url(self):
        """缓存命中也必须回填真实地址，否则换键与去重永远失效。"""
        import intelnexus.core.search.scraper as scraper_mod

        url_data = {"title": TITLE, "url": BAIDU_WRAPPER}
        entry = {"content": "缓存正文", "resolved_url": REAL_URL}
        with patch.object(scraper_mod, "get_cached_entry", return_value=entry):
            url, text = scraper_mod.scrape_single(url_data)
        assert url == BAIDU_WRAPPER
        assert text == "缓存正文"
        assert url_data["resolved_url"] == REAL_URL

    def test_meta_refresh_resolves_wrapper_target(self):
        """包装域未跟随重定向时，从已下载 HTML 的 meta refresh 解析目标。"""
        import intelnexus.core.search.scraper as scraper_mod

        session = MagicMock()
        session.get.return_value = _resp(text=META_REFRESH_HTML)
        url_data = {"title": TITLE, "url": BAIDU_WRAPPER}
        with patch.object(scraper_mod, "get_session", return_value=session), \
             patch.object(scraper_mod, "get_cached_entry", return_value=None), \
             patch.object(scraper_mod, "set_cached"):
            scraper_mod.scrape_single(url_data)
        assert url_data["resolved_url"] == "https://tech.example.com/real-target"

    def test_redirect_followed_uses_response_url(self):
        """requests 已跟随 301/302 时直接用 response.url。"""
        import intelnexus.core.search.scraper as scraper_mod

        session = MagicMock()
        session.get.return_value = _resp(url=REAL_URL, text="正文" * 60)
        url_data = {"title": TITLE, "url": BAIDU_WRAPPER}
        with patch.object(scraper_mod, "get_session", return_value=session), \
             patch.object(scraper_mod, "get_cached_entry", return_value=None), \
             patch.object(scraper_mod, "set_cached"):
            scraper_mod.scrape_single(url_data)
        assert url_data["resolved_url"] == REAL_URL

    def test_captcha_page_never_writes_resolved_url(self):
        """验证码页的降级路径不得回写地址（既有回归保护）。"""
        import intelnexus.core.search.scraper as scraper_mod

        session = MagicMock()
        session.get.return_value = _resp(
            url="https://wappass.baidu.com/static/captcha/tuxing_v2.html?ak=x",
            text="安全验证 请完成安全验证 拖动滑块完成拼图 请输入验证码 " + "填充" * 30,
        )
        url_data = {"title": TITLE, "url": BAIDU_WRAPPER}
        with patch.object(scraper_mod, "get_session", return_value=session), \
             patch.object(scraper_mod, "get_cached_entry", return_value=None), \
             patch.object(scraper_mod, "set_cached"):
            scraper_mod.scrape_single(url_data)
        assert "resolved_url" not in url_data


class TestScrapeMultipleResolve:
    def test_keys_switched_to_resolved_url_with_map(self):
        import intelnexus.core.search.scraper as scraper_mod

        def fake_scrape(url_data, *a, **kw):
            url_data["resolved_url"] = REAL_URL
            return url_data["url"], "正文"

        resolved_map = {}
        with patch.object(scraper_mod, "scrape_single", side_effect=fake_scrape), \
             patch.object(scraper_mod, "set_cached"):
            out = scraper_mod.scrape_multiple(
                [{"title": TITLE, "url": BAIDU_WRAPPER}], resolved_map=resolved_map)
        assert REAL_URL in out
        assert resolved_map[BAIDU_WRAPPER] == REAL_URL

    def test_without_resolved_url_keeps_original_key(self):
        import intelnexus.core.search.scraper as scraper_mod

        def fake_scrape(url_data, *a, **kw):
            return url_data["url"], "正文"

        with patch.object(scraper_mod, "scrape_single", side_effect=fake_scrape), \
             patch.object(scraper_mod, "set_cached"):
            out = scraper_mod.scrape_multiple([{"title": TITLE, "url": BAIDU_WRAPPER}])
        assert BAIDU_WRAPPER in out
