"""Tests for search relevance scoring: tokenizer, stopword filtering, relevance_passes.

对应 P0「评分分母修复 + 中文停用词」与 P1「tokenizer 抽象」的回归防线，
验证 query 清单来自搜索相关性方案第四轮审计。
"""

from datetime import datetime


# ============================================================
# Test: tokenizer（jieba 优先 / bi-gram 兜底）
# ============================================================

class TestTokenize:
    """统一分词接口：中文按词切分、英文按空白切分、降级路径可用。"""

    def test_chinese_segments_into_words(self):
        from intelnexus.core.search.tokenizer import tokenize
        # jieba 与 bi-gram 兜底都必须产出「免费」「模型」「额度」，
        # 且绝不能把整句当作单一 token（零匹配的根源）
        words = tokenize("送免费模型额度")
        assert "免费" in words
        assert "模型" in words
        assert "额度" in words
        assert "送免费模型额度" not in words

    def test_english_splits_on_whitespace(self):
        from intelnexus.core.search.tokenizer import tokenize
        assert tokenize("ransomware attack hospital") == [
            "ransomware", "attack", "hospital",
        ]

    def test_mixed_language_keeps_english_words_whole(self):
        from intelnexus.core.search.tokenizer import tokenize
        words = tokenize("DeepSeek free API quota")
        assert "deepseek" in [w.lower() for w in words]

    def test_empty_input(self):
        from intelnexus.core.search.tokenizer import tokenize
        assert tokenize("") == []

    def test_bigram_fallback_when_jieba_unavailable(self, monkeypatch):
        from intelnexus.core.search import tokenizer as tok
        monkeypatch.setattr(tok, "_jieba_available", False)
        # bi-gram 滑动窗口：相邻 2 字组合保证子串可命中
        words = tok.tokenize("免费模型额度")
        assert "免费" in words
        assert "模型" in words
        assert "额度" in words


# ============================================================
# Test: extract_query_tokens（停用词 + 短 token + 纯数字过滤）
# ============================================================

class TestExtractQueryTokens:
    """P0 验证 query 清单：五类查询的 token 提取行为。"""

    def test_chinese_long_query_no_zero_result(self):
        # 「送免费模型额度」不再整句成 token，产出有意义的关键词
        from intelnexus.core.search import extract_query_tokens
        tokens = extract_query_tokens("送免费模型额度")
        assert "免费" in tokens
        assert "额度" in tokens

    def test_mixed_language_query(self):
        from intelnexus.core.search import extract_query_tokens
        tokens = extract_query_tokens("DeepSeek free API quota")
        assert tokens == {"deepseek", "free", "api", "quota"}

    def test_stopword_filtered_out(self):
        # 「的」不成为 token（结构助词），但实义词「安全漏洞」保留
        from intelnexus.core.search import extract_query_tokens
        tokens = extract_query_tokens("最新的AI安全漏洞分析")
        assert "的" not in tokens
        assert "安全漏洞" in tokens
        assert "ai" in tokens

    def test_cve_id_kept_whole(self):
        # 短查询 CVE 编号不受影响：不拆分、不因含数字被过滤
        from intelnexus.core.search import extract_query_tokens
        assert extract_query_tokens("CVE-2026") == {"cve-2026"}

    def test_pure_english_query(self):
        from intelnexus.core.search import extract_query_tokens
        tokens = extract_query_tokens("ransomware attack hospital")
        assert tokens == {"ransomware", "attack", "hospital"}

    def test_stopword_only_query_yields_empty(self):
        # 全停用词查询返回空集合，relevance_passes 应放行（不误杀）
        from intelnexus.core.search import extract_query_tokens
        assert extract_query_tokens("的 了 是") == set()

    def test_list_query_parts_merged(self):
        from intelnexus.core.search import extract_query_tokens
        tokens = extract_query_tokens(["ransomware", "免费模型额度"])
        assert "ransomware" in tokens
        assert "免费" in tokens


# ============================================================
# Test: relevance_passes（评分 + 过滤）
# ============================================================

class TestRelevancePasses:
    """综合评分：关键词(0.5) + BM25(0.3) + 时效性(0~0.2)，阈值 0.3。"""

    def test_chinese_matching_result_passes(self):
        from intelnexus.core.search import relevance_passes
        result = {
            "title": "免费模型额度活动来袭",
            "description": "本模型免费额度领取教程",
            "url": "https://example.com/free-tier",
        }
        assert relevance_passes(result, "送免费模型额度") is True

    def test_chinese_unrelated_result_filtered(self):
        from intelnexus.core.search import relevance_passes
        result = {
            "title": "英超联赛最新战况",
            "description": "足球比赛结果与积分榜",
            "url": "https://example.com/football",
        }
        assert relevance_passes(result, "送免费模型额度") is False

    def test_blocked_domain_dropped_even_if_relevant(self):
        from intelnexus.core.search import relevance_passes
        result = {
            "title": "免费模型额度说明",
            "description": "免费模型额度百科词条",
            "url": "https://zh.wikipedia.org/wiki/免费额度",
        }
        assert relevance_passes(result, "送免费模型额度") is False

    def test_all_tokens_matched_passes_without_date(self):
        # 无发布时间（freshness=0）时，全量命中关键词得分 0.5+ 仍过阈值
        from intelnexus.core.search import relevance_passes
        result = {
            "title": "Ransomware attack cripples hospital network",
            "description": "The ransomware attack forced the hospital offline.",
            "url": "https://example.com/ransomware",
        }
        assert relevance_passes(result, "ransomware attack hospital") is True

    def test_zero_match_not_rescued_by_freshness(self):
        # 时效性满分 0.2 低于阈值 0.3：完全无关的新结果必须被过滤
        from intelnexus.core.search import relevance_passes
        result = {
            "title": "英式橄榄球新赛季赛程公布",
            "description": "橄榄球联盟公布赛程安排",
            "url": "https://example.com/rugby",
            "published_at": datetime.now().isoformat(),
        }
        assert relevance_passes(result, "ransomware attack hospital") is False

    def test_synonym_expansion_does_not_dilute_score(self):
        # P0 核心回归点：扩展词参与匹配但不进分母，
        # 原词全命中时不得因同义词扩容而被稀释到阈值以下
        from intelnexus.core.search import relevance_passes
        result = {
            "title": "某系统漏洞预警",
            "description": "官方发布漏洞补丁",
            "url": "https://example.com/vuln",
        }
        assert relevance_passes(result, "漏洞") is True

    def test_no_judgeable_tokens_passes_through(self):
        # 全停用词查询：无可判定关键词时不误杀
        from intelnexus.core.search import relevance_passes
        result = {
            "title": "任意内容",
            "description": "描述",
            "url": "https://example.com/anything",
        }
        assert relevance_passes(result, "的 了 是") is True


# ============================================================
# Test: 辅助评分函数
# ============================================================

class TestScoringHelpers:
    def test_bm25_zero_on_empty(self):
        from intelnexus.core.search import _calculate_bm25_score
        assert _calculate_bm25_score("", {"token"}) == 0.0
        assert _calculate_bm25_score("text", set()) == 0.0

    def test_bm25_higher_on_repeated_token(self):
        from intelnexus.core.search import _calculate_bm25_score
        single = _calculate_bm25_score("vulnerability report", {"vulnerability"})
        repeated = _calculate_bm25_score(
            "vulnerability details: this vulnerability affects many; "
            "another vulnerability listed here",
            {"vulnerability"},
        )
        assert repeated > single > 0.0

    def test_freshness_unknown_date_is_zero(self):
        from intelnexus.core.search_constants import get_freshness_score
        assert get_freshness_score("") == 0.0
        assert get_freshness_score("Unknown date") == 0.0

    def test_freshness_recent_is_max(self):
        from intelnexus.core.search_constants import get_freshness_score
        now = datetime.now().isoformat()
        assert get_freshness_score(now) == 0.2


# ============================================================
# Test: 搜索日志 selected_url（相关性排序首位结果）
# ============================================================

class TestSearchHistorySelectedUrl:
    """P1-2 收尾：selected_url 记录排序首位结果 URL，不再永远为空。"""

    def test_add_search_stores_selected_url(self, tmp_path):
        from intelnexus.config.history import SearchHistory
        h = SearchHistory(storage_dir=str(tmp_path))
        entry = h.add_search(
            "送免费模型额度", "web", 5, "test-model",
            selected_url="https://example.com/top-result",
        )
        assert entry["selected_url"] == "https://example.com/top-result"
        stored = h.get_history()[0]
        assert stored["selected_url"] == "https://example.com/top-result"

    def test_selected_url_defaults_empty(self, tmp_path):
        from intelnexus.config.history import SearchHistory
        h = SearchHistory(storage_dir=str(tmp_path))
        entry = h.add_search("ransomware", "web", 0, "test-model")
        assert entry["selected_url"] == ""
