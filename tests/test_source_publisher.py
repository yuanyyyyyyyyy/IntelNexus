"""P1-1 来源口径回归：可信度必须打在「真实出版方」上，而非检索渠道。

审计背景（报告 INTEL-20260916-001）：来源分布表把搜索引擎当作来源
（Baidu 47% / Bing 26%），真实出版方（ctrip / agoda / wikivoyage /
washington.org / zhihu）被完全遮蔽。Baidu 的 5 条是 `baidu.com/link?url=`
不透明跳转，其可信度 43% 实际打在 www.baidu.com 上；占语料近半、承载
唯一中文目标线索的渠道反而评分最低，出现「评分与价值倒挂」。
"""

import pytest

from intelnexus.analysis.credibility import SourceScorer

BAIDU_WRAPPER = "http://www.baidu.com/link?url=Vn0Y1u5kfihqpXe6SM68SHuTsZ"


@pytest.fixture(autouse=True)
def _no_embedding_model(monkeypatch):
    """纯打分逻辑测试，不加载嵌入模型（避免数秒级模型加载）。"""
    monkeypatch.setattr(
        "intelnexus.analysis.credibility.load_sentence_model", lambda: None)


def _scorer():
    return SourceScorer()


def _score(result):
    s = _scorer()
    s.evaluate([result], {})
    return result["credibility_details"]


# ===========================================================================
# 出版方识别
# ===========================================================================

class TestPublisherResolution:
    def test_resolved_url_takes_precedence_over_wrapper(self):
        r = {
            "title": "华尔道夫酒店预订",
            "url": BAIDU_WRAPPER,
            "resolved_url": "https://hotels.ctrip.com/hotels/2198955.html",
            "source": "Baidu",
        }
        detail = _score(r)
        # 只剥 www. 前缀，保留子域以区分同一站点的不同业务域
        assert r["publisher"] == "hotels.ctrip.com"

    def test_domain_score_uses_publisher_not_engine(self):
        """旧实现按 baidu.com 落在聚合器回退分支（0.5），与出版方无关。"""
        resolved = {
            "title": "t", "url": BAIDU_WRAPPER,
            "resolved_url": "https://hotels.ctrip.com/hotels/1.html",
            "source": "Baidu",
        }
        unresolved = {"title": "t", "url": BAIDU_WRAPPER, "source": "Baidu"}
        d_res = _score(resolved)
        d_unres = _score(unresolved)
        assert d_unres["publisher"] == ""
        assert d_unres["publisher_resolved"] is False
        assert d_res["domain_score"] != d_unres["domain_score"]

    def test_unresolved_wrapper_has_empty_publisher(self):
        r = {"title": "t", "url": BAIDU_WRAPPER, "source": "Baidu"}
        detail = _score(r)
        assert detail["publisher"] == ""
        assert detail["publisher_resolved"] is False

    def test_plain_url_publisher_is_its_domain(self):
        r = {"title": "t", "url": "https://zh.wikivoyage.org/wiki/华盛顿",
             "source": "Bing"}
        detail = _score(r)
        assert detail["publisher"] == "zh.wikivoyage.org"
        assert detail["publisher_resolved"] is True

    def test_www_prefix_stripped(self):
        r = {"title": "t", "url": "https://www.zhihu.com/question/32157261",
             "source": "Bing"}
        detail = _score(r)
        assert detail["publisher"] == "zhihu.com"

    def test_ota_domains_are_not_scored_as_unknown(self):
        """携程/Agoda 等预订平台不应落到「未收录域名」的 0.45 保守分。"""
        r = {"title": "t", "url": "https://hotels.ctrip.com/hotels/1.html",
             "source": "Baidu"}
        detail = _score(r)
        assert detail["domain_score"] > 0.45

    def test_engine_recorded_separately(self):
        r = {"title": "t", "url": "https://hotels.ctrip.com/hotels/1.html",
             "source": "Baidu"}
        detail = _score(r)
        assert detail["engine"] == "Baidu"


# ===========================================================================
# 报告层：来源分析分离两个维度
# ===========================================================================

def _cred_data():
    return {
        "scores": [
            {"name": "Baidu", "engine": "Baidu", "publisher": "ctrip.com",
             "score": 0.62, "reason": "内容丰富", "domain": 0.6},
            {"name": "Baidu", "engine": "Baidu", "publisher": "ctrip.com",
             "score": 0.55, "reason": "内容单薄", "domain": 0.6},
            {"name": "Bing", "engine": "Bing", "publisher": "zhihu.com",
             "score": 0.6, "reason": "内容丰富", "domain": 0.6},
            {"name": "Bing", "engine": "Bing", "publisher": "",
             "score": 0.45, "reason": "内容单薄", "domain": 0.5},
        ],
        "avg_score": 0.55, "high_count": 0, "low_count": 0,
    }


class TestSourceAnalysisDimensions:
    def test_publisher_dimension_rendered(self):
        from intelnexus.export.report_builder import build_source_analysis
        out = build_source_analysis({"Baidu": 2, "Bing": 2}, {}, _cred_data())
        assert "出版方" in out
        assert "ctrip.com" in out
        assert "zhihu.com" in out

    def test_engine_dimension_still_rendered(self):
        from intelnexus.export.report_builder import build_source_analysis
        out = build_source_analysis({"Baidu": 2, "Bing": 2}, {}, _cred_data())
        assert "检索渠道" in out
        assert "Baidu" in out

    def test_same_publisher_aggregated_once(self):
        from intelnexus.export.report_builder import build_source_analysis
        out = build_source_analysis({"Baidu": 2, "Bing": 2}, {}, _cred_data())
        publisher_lines = [l for l in out.splitlines() if l.startswith("- **ctrip.com**")]
        assert len(publisher_lines) == 1

    def test_unresolved_publisher_is_flagged_not_disguised(self):
        from intelnexus.export.report_builder import build_source_analysis
        out = build_source_analysis({"Bing": 1}, {}, _cred_data())
        assert "出版方未解析" in out

    def test_falls_back_to_source_name_without_publisher_data(self):
        """旧数据结构（无 publisher 字段）仍须可用。"""
        from intelnexus.export.report_builder import build_source_analysis
        legacy = {"scores": [{"name": "Bing", "score": 0.7, "reason": "", "domain": 0.8}],
                  "avg_score": 0.7}
        out = build_source_analysis({"Bing": 1}, {}, legacy)
        assert "Bing" in out
        assert "出版方" not in out


# ===========================================================================
# 透明度修复：已检索但未产出相关结果的渠道应被揭示（不再误判为单渠道配置）
# ===========================================================================

class TestEmptyChannelNotes:
    def test_empty_channels_rendered(self):
        from intelnexus.export.report_builder import build_source_analysis
        source_stats = {
            "Web": {"status": "ok", "count": 4},
            "News": {"status": "ok", "count": 0},
            "HackerNews": {"status": "error", "count": 0},
        }
        out = build_source_analysis({"Baidu": 4}, source_stats, _cred_data())
        assert "已检索但未产出相关结果" in out
        assert "新闻(News/RSS)（无相关结果）" in out
        assert "Hacker News（检索异常）" in out

    def test_empty_channels_absent_when_all_contributed(self):
        from intelnexus.export.report_builder import build_source_analysis
        # 所有渠道都有产出，不应出现空渠道说明
        source_stats = {"Web": {"status": "ok", "count": 4}}
        out = build_source_analysis({"Baidu": 4}, source_stats, _cred_data())
        assert "已检索但未产出相关结果" not in out

    def test_distribution_table_unchanged_by_empty_channels(self):
        """空渠道说明不得进入 4.1 分布表，也不改变分布行。"""
        from intelnexus.export.report_builder import build_source_analysis
        source_stats = {"News": {"status": "ok", "count": 0}}
        out = build_source_analysis({"Baidu": 4}, source_stats, _cred_data())
        # 分布表仍只反映有贡献渠道
        dist_rows = [l for l in out.splitlines() if l.strip().startswith("| Baidu")]
        assert len(dist_rows) == 1
        assert "100%" in dist_rows[0]

    def test_no_crash_when_source_stats_missing_or_empty(self):
        from intelnexus.export.report_builder import build_source_analysis
        out = build_source_analysis({"Baidu": 4}, {}, _cred_data())
        assert "Baidu" in out
        # 兼容调用方未传 / 传 None 的历史路径
        out2 = build_source_analysis({"Baidu": 4}, None, _cred_data())
        assert "Baidu" in out2
        assert "已检索但未产出相关结果" not in out2


# ===========================================================================
# 共享来源元数据：SOURCE_LABELS / STATUS_REASONS / summarize_empty_channels
# （无 streamlit 依赖，可直接 import，保证报告与 UI 两端口径单一来源）
# ===========================================================================

class TestSummarizeEmptyChannels:
    def test_labels_status_reasons_match_report(self):
        """报告与 UI 共用的标签/原因必须来自同一处，且字符串与既有断言一致。"""
        from intelnexus.core.search.source_meta import (
            SOURCE_LABELS, STATUS_REASONS, summarize_empty_channels)
        # 既有断言 test_source_publisher.py:167 依赖的标签
        assert SOURCE_LABELS["HackerNews"] == "Hacker News"
        assert STATUS_REASONS["ok"] == "无相关结果"
        assert STATUS_REASONS["error"] == "检索异常"
        assert STATUS_REASONS["timeout"] == "检索超时"

    def test_empty_channels_labeled(self):
        from intelnexus.core.search.source_meta import summarize_empty_channels
        source_stats = {
            "Web": {"status": "ok", "count": 4},
            "News": {"status": "ok", "count": 0},
            "HackerNews": {"status": "error", "count": 0},
            "DarkWeb": {"status": "timeout", "count": 0},
        }
        notes = summarize_empty_channels(source_stats)
        assert len(notes) == 3
        assert "新闻(News/RSS)（无相关结果）" in notes
        assert "Hacker News（检索异常）" in notes
        assert "暗网(DarkWeb)（检索超时）" in notes

    def test_no_empty_when_all_contributed(self):
        from intelnexus.core.search.source_meta import summarize_empty_channels
        source_stats = {"Web": {"status": "ok", "count": 4}}
        assert summarize_empty_channels(source_stats) == []

    def test_empty_or_missing_source_stats_safe(self):
        from intelnexus.core.search.source_meta import summarize_empty_channels
        assert summarize_empty_channels({}) == []
        assert summarize_empty_channels(None) == []
