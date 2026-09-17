"""P0-1 相关性链路回归：检索层过滤 + 报告层消费。

审计背景（报告 INTEL-20260916-001）：19 条语料中 5 条为与主题完全无关的
RSS 最新条目，原因是 news.py 按空白切词 + 子串匹配；报告层又用同一套
按空白切词的关键词过滤，中文整句塌成 1 个关键词必然零命中，随后
「无匹配就用全量」的兜底把噪声全量计入热度/可信度/时间线。

本文件锚定三条不变量：
1. 检索层：与主题无关的条目不得通过相关性闸门；
2. 报告层：弱相关条目不得进入关键情报 / 事件画像 / 事件演化；
3. 降级可观测：相关性不可用时必须显式提示，且不得把全量当相关结果统计。
"""

import pytest

# 审计样本中的真实噪声条目（来源：Solidot / AI科技评论 RSS 最新条目）
NOISE_ITEMS = [
    {"title": "AI 时代隐晦式安全已死",
     "description": "安全行业讨论隐晦式安全在 AI 时代的失效",
     "url": "https://www.solidot.org/story?sid=1", "source": "Solidot"},
    {"title": "微信蠕虫事件敲响 AI 安全警钟",
     "description": "微信蠕虫传播引发对 AI 安全的关注",
     "url": "https://www.solidot.org/story?sid=2", "source": "Solidot"},
    {"title": "横扫四榜，DM0.5 凭什么面面俱到？",
     "description": "模型评测榜单结果解读",
     "url": "https://www.leiphone.com/a/1.html", "source": "AI科技评论"},
    {"title": "英伟达开源 IMO 金牌配方",
     "description": "1.5TB 显存训练方案开源",
     "url": "https://www.leiphone.com/a/2.html", "source": "AI科技评论"},
]

# 审计中被系统判为「无法确认」的真实目标主体
HOTEL_QUERY = "华盛顿华尔道夫酒店位置华盛顿特区宾夕法尼亚大道西北1100号:对酒店所有设施开展调研加漏洞"


# ===========================================================================
# 检索层：相关性闸门
# ===========================================================================

class TestRelevanceGate:
    """与主题无关的条目不得通过相关性闸门（旧实现会让它们全部混入）。"""

    def test_noise_items_rejected(self):
        from intelnexus.core.search import relevance_passes
        for item in NOISE_ITEMS:
            assert relevance_passes(item, HOTEL_QUERY) is False, (
                f"无关条目通过了相关性闸门：{item['title']}"
            )

    def test_relevant_item_accepted(self):
        from intelnexus.core.search import relevance_passes
        item = {
            "title": "华尔道夫酒店-华盛顿特区（Waldorf Astoria Washington DC）预订",
            "description": "位于宾夕法尼亚大道的豪华酒店，靠近白宫",
            "url": "https://www.agoda.com/hotel/washington-d-c-us.html",
            "source": "Agoda",
        }
        assert relevance_passes(item, HOTEL_QUERY) is True

    def test_rss_no_longer_whitespace_tokenizes_query(self):
        """news.py 不得再按空白切词做子串匹配。"""
        import inspect
        from intelnexus.core.search import news
        src = inspect.getsource(news.NewsSearch.search_rss)
        assert "set(query_lower.split())" not in src
        assert "relevance_passes(" in src


# ===========================================================================
# 报告层：相关性消费
# ===========================================================================

def _mk(title, weak=False, score=0.9, rel=0.8):
    return {
        "title": title,
        "url": f"https://example.com/{abs(hash(title)) % 1000}",
        "source": "Bing",
        "credibility_score": score,
        "weak_related": weak,
        "relevance_score": rel,
        "published_at": "2026-09-14",
    }


class TestSplitRelevant:
    def test_weak_items_removed(self):
        from intelnexus.analysis.relevance import split_relevant
        items = [_mk("相关", weak=False), _mk("噪声", weak=True)]
        relevant, available = split_relevant(items)
        assert available is True
        assert [i["title"] for i in relevant] == ["相关"]

    def test_unavailable_when_no_marks(self):
        """没有 weak_related 标记 = 未经评估，不得当作相关结果。"""
        from intelnexus.analysis.relevance import split_relevant
        items = [{"title": "a"}, {"title": "b"}]
        relevant, available = split_relevant(items)
        assert available is False
        assert relevant == []

    def test_all_weak_returns_empty_but_available(self):
        from intelnexus.analysis.relevance import split_relevant, relevant_ratio
        items = [_mk("a", weak=True), _mk("b", weak=True)]
        relevant, available = split_relevant(items)
        assert (relevant, available) == ([], True)
        assert relevant_ratio(items) == 0.0

    def test_ratio_none_when_unavailable(self):
        from intelnexus.analysis.relevance import relevant_ratio
        assert relevant_ratio([{"title": "a"}]) is None


class TestKeyIntelligence:
    def test_weak_items_excluded(self):
        from intelnexus.export.report_builder import build_key_intelligence
        results = [_mk("强相关条目", rel=0.9), _mk("无关噪声", weak=True, rel=0.1, score=0.99)]
        out = build_key_intelligence(results)
        assert "强相关条目" in out
        assert "无关噪声" not in out

    def test_high_credibility_noise_cannot_top_list(self):
        """旧实现只按可信度排序，权威来源的无关条目会顶到榜首。"""
        from intelnexus.export.report_builder import build_key_intelligence
        results = [
            _mk("无关但权威", score=0.99, rel=0.05),
            _mk("高度相关", score=0.4, rel=0.95),
        ]
        out = build_key_intelligence(results, top_n=1)
        assert "高度相关" in out
        assert "无关但权威" not in out

    def test_all_weak_reports_no_valid_item(self):
        from intelnexus.export.report_builder import build_key_intelligence
        out = build_key_intelligence([_mk("a", weak=True), _mk("b", weak=True)])
        assert "无有效情报条目" in out

    def test_truncation_is_annotated(self):
        from intelnexus.export.report_builder import build_key_intelligence
        results = [_mk(f"条目{i}", rel=0.9 - i * 0.01) for i in range(15)]
        out = build_key_intelligence(results, top_n=10)
        assert "展示前 10 条" in out

    def test_degradation_is_visible(self):
        """相关性不可用时必须显式提示，而不是静默全量。"""
        from intelnexus.export.report_builder import build_key_intelligence
        out = build_key_intelligence([{"title": "a", "credibility_score": 0.8}])
        assert "相关性评估不可用" in out


class TestEventProfile:
    def test_weak_items_excluded_from_stats(self):
        from intelnexus.export.report_builder import build_event_profile
        results = [_mk("相关")] + [_mk("噪声", weak=True)]
        out = build_event_profile(results, {})
        assert "噪声" not in out

    def test_all_weak_does_not_silently_fallback(self):
        """旧实现零命中就回退全量；现在必须给出无有效样本提示。"""
        from intelnexus.export.report_builder import build_event_profile
        out = build_event_profile([_mk("a", weak=True), _mk("b", weak=True)], {})
        assert "全部被判定为弱相关" in out
        assert "无有效数据生成事件画像" in out

    def test_duration_unknown_has_no_unit_suffix(self):
        from intelnexus.export.report_builder import build_event_profile
        out = build_event_profile([{"title": "a", "weak_related": False}], {})
        assert "未知 天" not in out
        assert "**持续时间**：未知" in out

    def test_heat_penalized_by_relevance_ratio(self):
        from intelnexus.export.report_builder import build_event_profile
        noisy = [_mk(f"n{i}", weak=True) for i in range(10)]
        noisy += [_mk("rel", weak=False)]
        out = build_event_profile(noisy, {})
        # 11 篇去重文章 + 1 个来源：旧口径 11*4=44；相关率 1/11 后应大幅降低
        heat_line = [l for l in out.splitlines() if l.startswith("**热度**")][0]
        heat = int(heat_line.split()[-1])
        assert heat <= 10, f"热度未受相关率惩罚：{heat_line}"


class TestEventEvolution:
    def test_weak_items_excluded(self):
        from intelnexus.export.report_builder import build_event_evolution
        results = [_mk("相关事件")] + [_mk("噪声时间线", weak=True)]
        out = build_event_evolution(results, {})
        assert "相关事件" in out
        assert "噪声时间线" not in out


class TestHeatLevel:
    def test_backward_compatible_without_ratio(self):
        from intelnexus.export.report_builder import compute_heat_level
        results = [{"url": "https://a.com/x", "source": "Bing"}]
        assert compute_heat_level(results) == 4

    def test_zero_ratio_yields_zero_articles(self):
        from intelnexus.export.report_builder import compute_heat_level
        results = [{"url": f"https://a.com/{i}", "source": "Bing"} for i in range(10)]
        assert compute_heat_level(results, relevance_ratio=0.0) == 0

    def test_ratio_scales_base(self):
        from intelnexus.export.report_builder import compute_heat_level
        results = [{"url": f"https://a.com/{i}", "source": "Bing"} for i in range(10)]
        assert compute_heat_level(results, relevance_ratio=0.5) == 20


class TestOverviewNumbering:
    def test_overview_section_present(self):
        from intelnexus.export.report_builder import build_report_overview
        out = build_report_overview("q", "all", "m", {"Bing": 1}, 1)
        assert "## 一、报告概览" in out


class TestSnapshotHeatConsistency:
    """事件快照的热度必须与报告事件画像同口径（评审 B5）。"""

    def test_snapshot_heat_matches_event_profile(self):
        from intelnexus.export.report_builder import (
            build_event_profile, compute_snapshot_heat,
        )
        results = [_mk(f"相关{i}") for i in range(8)]
        results += [_mk(f"噪声{i}", weak=True) for i in range(8)]
        out = build_event_profile(results, {})
        reported = int([l for l in out.splitlines()
                        if l.startswith("**热度**")][0].split()[-1])
        assert compute_snapshot_heat(results) == reported
