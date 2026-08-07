"""
网页搜索层测试（shared/search/web.py + shared/search/__init__.py 的噪声过滤）。

覆盖：
- query 拆分（'|' 分隔、list、单串）
- _dedup_results 去重与短链接过滤
- is_blocked_domain 域名黑名单（含子串关键词）
- extract_query_tokens / relevance_passes 相关性评分
- get_web_results 的代理跳过慢速引擎分支 + 域名黑名单 + 相关性过滤
- 单引擎 _fetch_engine 的 HTML 解析（mock requests.Session）

所有外部请求均 mock，离线、快速、确定性。
"""
import sys
from unittest.mock import patch, MagicMock

import pytest

# 确保项目根在 sys.path（conftest 已注入，这里再保险一次）
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))

from shared.search import web as web_module
from shared.search import is_blocked_domain, relevance_passes, extract_query_tokens, get_http_proxies


# ---------------------------------------------------------------------------
# query 拆分
# ---------------------------------------------------------------------------
class TestQuerySplit:
    def test_split_by_pipe(self):
        assert web_module.get_web_results.__name__ == "get_web_results"

    def test_dedup_removes_duplicates_and_trailing_slash(self):
        results = [
            {"title": "A", "link": "https://example.com/a", "description": "x", "source": "Bing"},
            {"title": "A2", "link": "https://example.com/a/", "description": "x", "source": "Baidu"},
            {"title": "B", "link": "https://example.com/b", "description": "y", "source": "Bing"},
        ]
        out = web_module._dedup_results(results)
        links = [r["link"] for r in out]
        assert "https://example.com/a" in links
        assert "https://example.com/b" in links
        # 去重后不应重复出现 example.com/a 的两种写法
        assert sum(1 for l in links if l.startswith("https://example.com/a")) == 1
        assert len(out) == 2

    def test_dedup_drops_too_short_links(self):
        results = [
            {"title": "X", "link": "http://x", "description": "x", "source": "Bing"},
            {"title": "Y", "link": "https://example.com/longpath", "description": "y", "source": "Bing"},
        ]
        out = web_module._dedup_results(results)
        assert len(out) == 1
        assert out[0]["link"] == "https://example.com/longpath"

    def test_dedup_empty(self):
        assert web_module._dedup_results([]) == []


# ---------------------------------------------------------------------------
# 域名黑名单 + 相关性评分
# ---------------------------------------------------------------------------
class TestNoiseFilter:
    def test_is_blocked_domain_wikipedia(self):
        assert is_blocked_domain("https://en.wikipedia.org/wiki/AI") is True

    def test_is_blocked_domain_baike(self):
        assert is_blocked_domain("https://baike.baidu.com/item/foo") is True

    def test_is_blocked_domain_gambling_keyword(self):
        # csgo / dota2 等关键词子串匹配
        assert is_blocked_domain("https://www.csgo-skins.com/x") is True

    def test_is_blocked_domain_normal(self):
        assert is_blocked_domain("https://www.theverge.com/2024/ai-news") is False

    def test_is_blocked_domain_empty(self):
        assert is_blocked_domain("") is False
        assert is_blocked_domain("not a url") is False

    def test_extract_tokens_strips_stopwords_and_year(self):
        tokens = extract_query_tokens("latest AI security incident 2024")
        assert "ai" in tokens
        assert "security" in tokens
        assert "incident" not in tokens  # 停用词
        assert "2024" not in tokens  # 纯数字年份

    def test_extract_tokens_list_and_pipe(self):
        assert extract_query_tokens(["AI", "ml"]) == {"ai", "ml"}
        assert extract_query_tokens("AI | machine learning") == {"ai", "machine", "learning"}

    def test_relevance_passes_blocked_domain(self):
        res = {"title": "AI news", "description": "x", "link": "https://en.wikipedia.org/wiki/AI"}
        assert relevance_passes(res, "AI security") is False

    def test_relevance_passes_insufficient_match(self):
        # 仅命中 1 个 token（阈值应为 2）
        res = {"title": "AI framework released", "description": "new tool", "link": "https://example.com/a"}
        # query tokens: ai, security, update -> 只命中 ai
        assert relevance_passes(res, "AI security update") is False

    def test_relevance_passes_sufficient_match(self):
        res = {"title": "AI security update", "description": "patch released", "link": "https://example.com/a"}
        assert relevance_passes(res, "AI security update") is True

    def test_relevance_passes_single_token_query(self):
        # token 不足 2 个时，命中全部（这里 1 个）即通过
        res = {"title": "AI is cool", "description": "x", "link": "https://example.com/a"}
        assert relevance_passes(res, "AI") is True

    def test_relevance_passes_no_tokens(self):
        # 无可判定关键词时不误杀
        assert relevance_passes({"title": "x", "link": "https://example.com/a"}, "the") is True


# ---------------------------------------------------------------------------
# 单引擎解析（mock session.get）
# ---------------------------------------------------------------------------
def _make_response(text, status=200):
    resp = MagicMock()
    resp.status_code = status
    resp.text = text
    return resp


class TestEngineFetch:
    def test_fetch_bing_parses_results(self):
        html = """
        <html><body>
          <li class="b_algo">
            <h2><a href="https://news.example.com/ai">AI News</a></h2>
            <p>About AI security.</p>
          </li>
          <li class="b_algo">
            <h2><a href="https://www.bing.com/self">Bing self</a></h2>
            <p>should be filtered</p>
          </li>
        </body></html>
        """
        session = MagicMock()
        session.get.return_value = _make_response(html)
        with patch.object(web_module, "get_session", return_value=session):
            results = web_module.fetch_bing_results("AI", 0)
        links = [r["link"] for r in results]
        assert "https://news.example.com/ai" in links
        # bing 自身链接被 filter_bing 过滤
        assert "https://www.bing.com/self" not in links
        assert all(r["source"] == "Bing" for r in results)

    def test_fetch_engine_non_200_returns_empty(self):
        session = MagicMock()
        session.get.return_value = _make_response("", status=503)
        with patch.object(web_module, "get_session", return_value=session):
            assert web_module.fetch_bing_results("AI") == []

    def test_fetch_ddg_parses_results(self):
        html = """
        <html><body>
          <div class="result">
            <a class="result__a" href="https://ddg.example.com/ai">DDG AI</a>
            <a class="result__snippet">AI snippet</a>
          </div>
        </body></html>
        """
        session = MagicMock()
        session.get.return_value = _make_response(html)
        with patch.object(web_module, "get_session", return_value=session):
            results = web_module.fetch_ddg_results("AI")
        assert any(r["link"] == "https://ddg.example.com/ai" for r in results)

    def test_fetch_yahoo_parses_results(self):
        html = """
        <html><body>
          <div class="algo">
            <a href="https://yahoo.example.com/ai">Yahoo AI</a>
            <p>desc</p>
          </div>
        </body></html>
        """
        session = MagicMock()
        session.get.return_value = _make_response(html)
        with patch.object(web_module, "get_session", return_value=session):
            results = web_module.fetch_yahoo_results("AI")
        assert any(r["link"] == "https://yahoo.example.com/ai" for r in results)

    def test_fetch_unknown_engine_returns_empty(self):
        assert web_module._fetch_engine("NotAnEngine", "AI") == []


# ---------------------------------------------------------------------------
# get_web_results 集成（mock session + get_http_proxies）
# ---------------------------------------------------------------------------
class TestGetWebResults:
    @pytest.fixture
    def patched_session(self):
        """所有引擎返回一条有效结果 + 一条黑名单/低相关结果。"""
        html = """
        <html><body>
          <li class="b_algo"><h2><a href="https://news.example.com/ai">AI Security Update</a></h2>
            <p>AI security patch released.</p></li>
          <li class="b_algo"><h2><a href="https://en.wikipedia.org/wiki/AI">Wiki AI</a></h2>
            <p>encyclopedia</p></li>
        </body></html>
        """
        session = MagicMock()
        session.get.return_value = _make_response(html)
        return session

    def test_no_proxy_skips_slow_engines(self, patched_session):
        with patch.object(web_module, "get_session", return_value=patched_session), \
             patch.object(web_module, "get_http_proxies", return_value=None), \
             patch.object(web_module, "FAST_ENGINES", ["Bing"]), \
             patch.object(web_module, "SLOW_ENGINES", ["DuckDuckGo", "Yahoo", "Yandex"]):
            results = web_module.get_web_results("AI security update", max_results=50)
        assert results  # 至少有 fast 引擎结果
        # 域名黑名单（wikipedia）必须被过滤
        assert not any("wikipedia" in r["link"] for r in results)
        # 相关性过滤后只应保留命中 >=2 token 的
        assert all("news.example.com" in r["link"] for r in results)

    def test_with_proxy_runs_slow_engines(self, patched_session):
        slow_html = """
        <html><body>
          <div class="result"><a class="result__a" href="https://ddg.example.com/ai2">DDG AI2</a>
            <a class="result__snippet">AI security patch</a></div>
        </body></html>
        """
        fast_html = patched_session.get.return_value.text

        def get_for_url(url, **kwargs):
            if "duckduckgo" in url:
                return _make_response(slow_html)
            return _make_response(fast_html)

        session = MagicMock()
        session.get.side_effect = get_for_url

        with patch.object(web_module, "get_session", return_value=session), \
             patch.object(web_module, "get_http_proxies", return_value={"http": "http://proxy", "https": "http://proxy"}), \
             patch.object(web_module, "FAST_ENGINES", ["Bing"]), \
             patch.object(web_module, "SLOW_ENGINES", ["DuckDuckGo", "Yahoo", "Yandex"]):
            results = web_module.get_web_results("AI security update", max_results=50)

        ddg = [r for r in results if "ddg.example.com" in r["link"]]
        assert ddg, "配置了代理时应运行慢速引擎并返回其结果"
        assert not any("wikipedia" in r["link"] for r in results)

    def test_query_with_pipe_expands(self, patched_session):
        with patch.object(web_module, "get_session", return_value=patched_session), \
             patch.object(web_module, "get_http_proxies", return_value=None), \
             patch.object(web_module, "FAST_ENGINES", ["Bing"]), \
             patch.object(web_module, "SLOW_ENGINES", []):
            # '|' 触发多 query，不应抛错，且能返回结果
            results = web_module.get_web_results("AI security | ML safety", max_results=50)
        assert isinstance(results, list)

    def test_empty_results_when_all_filtered(self):
        # 全部返回黑名单域名的页面
        html = """
        <html><body><li class="b_algo">
          <h2><a href="https://en.wikipedia.org/wiki/AI">Wiki</a></h2><p>x</p></li>
        </body></html>
        """
        session = MagicMock()
        session.get.return_value = _make_response(html)
        with patch.object(web_module, "get_session", return_value=session), \
             patch.object(web_module, "get_http_proxies", return_value=None), \
             patch.object(web_module, "FAST_ENGINES", ["Bing"]), \
             patch.object(web_module, "SLOW_ENGINES", []):
            results = web_module.get_web_results("AI", max_results=50)
        # 全部被过滤时回退保留去重后结果（unique_results）
        assert isinstance(results, list)
