"""Tests for report audit fixes (2026-09 审计修复).

Covers:
- LLM 板块提取正则（证据链分析 / 情报判断与后续关注）
- 报告占位文案中性化
- 重定向 URL 离线解码与去重归一化
- 时间冲突检测的上下文校验与冲突去重
- 域名权威度按真实发布者域名评分
- 热度按去重独立文章数计算
- 实体 canonical_id 尾部标点合并
"""

import re
from unittest.mock import patch, MagicMock

import pytest


# ---------------------------------------------------------------------------
# P0: LLM 板块提取正则
# ---------------------------------------------------------------------------

class TestSectionExtraction:
    def test_evidence_chain_with_analysis_suffix(self):
        """LLM 按模板写「证据链分析」标题时必须能提取到。"""
        from intelnexus.export.report_builder import extract_analytical_sections
        llm = "## 六、证据链分析\n\n结论 1：某某\n- E1：证据\n\n## 七、实体\n"
        sections = extract_analytical_sections(llm)
        assert "结论 1" in sections["evidence_chain"]
        assert "实体" not in sections["evidence_chain"]

    def test_evidence_chain_without_suffix(self):
        from intelnexus.export.report_builder import extract_analytical_sections
        llm = "## 六、证据链\n\n结论内容\n"
        sections = extract_analytical_sections(llm)
        assert "结论内容" in sections["evidence_chain"]

    def test_intelligence_judgment_no_space(self):
        """「情报判断与后续关注」中间无空格，旧正则会漏提。"""
        from intelnexus.export.report_builder import extract_analytical_sections
        llm = "## 十三、情报判断与后续关注\n\n后续需关注 X 的定价变化。\n"
        sections = extract_analytical_sections(llm)
        assert "定价变化" in sections["intelligence_judgment"]

    def test_intelligence_judgment_with_space(self):
        from intelnexus.export.report_builder import extract_analytical_sections
        llm = "## 十三、情报判断 与后续关注\n\n内容A\n"
        sections = extract_analytical_sections(llm)
        assert "内容A" in sections["intelligence_judgment"]

    def test_risk_cleanup_accepts_chinese_ordinals(self):
        from intelnexus.export.report_builder import build_risk_assessment
        content = build_risk_assessment({"risk_assessment": "## 十、风险评估\n\n风险等级：中\n"})
        assert "风险等级：中" in content
        assert "##" not in content

    def test_attack_surface_cleanup(self):
        from intelnexus.export.report_builder import build_attack_surface
        content = build_attack_surface({"attack_surface": "## 十二、攻击面分析\n\nAPI 层风险\n"})
        assert "API 层风险" in content


class TestNeutralPlaceholders:
    def test_risk_placeholder_neutral(self):
        from intelnexus.export.report_builder import build_risk_assessment
        assert "不涉及" not in build_risk_assessment({})

    def test_judgment_placeholder_neutral(self):
        from intelnexus.export.report_builder import build_intelligence_judgment
        assert "不涉及" not in build_intelligence_judgment({})

    def test_attack_placeholder_neutral(self):
        from intelnexus.export.report_builder import build_attack_surface
        assert "不涉及" not in build_attack_surface({})


# ---------------------------------------------------------------------------
# P0: 报告编号
# ---------------------------------------------------------------------------

class TestReportId:
    def test_explicit_report_id_used(self):
        from intelnexus.export.report_builder import build_report_overview
        text = build_report_overview("q", "web", "m", report_id="INTEL-20260903-007")
        assert "INTEL-20260903-007" in text

    def test_fallback_id_format(self):
        from intelnexus.export.report_builder import _gen_report_id
        from datetime import datetime
        rid = _gen_report_id(datetime(2026, 9, 3, 2, 56, 0))
        assert re.fullmatch(r"INTEL-\d{8}-\d{3}", rid)


# ---------------------------------------------------------------------------
# P1: 重定向 URL 解码
# ---------------------------------------------------------------------------

YAHOO_WRAPPER = (
    "https://r.search.yahoo.com/_ylt=abc;_ylu=def/RV=2/RE=1789584809/RO=10/"
    "RU=https%3a%2f%2fjuejin.cn%2fpost%2f7678646261259092004/RK=2/RS=xyz"
)
DDG_WRAPPER = "https://duckduckgo.com/l/?uddg=https%3A%2F%2Fkelen.cc%2Fshare%2Fpost1&rut=abc"


class TestCanonicalResultUrl:
    def test_yahoo_wrapper_decoded(self):
        from intelnexus.core.search.web import canonical_result_url
        assert canonical_result_url(YAHOO_WRAPPER) == "https://juejin.cn/post/7678646261259092004"

    def test_ddg_wrapper_decoded(self):
        from intelnexus.core.search.web import canonical_result_url
        assert canonical_result_url(DDG_WRAPPER) == "https://kelen.cc/share/post1"

    def test_baidu_wrapper_unchanged(self):
        """Baidu 加密串无法离线解码，原样返回（运行时由 scraper 解析）。"""
        from intelnexus.core.search.web import canonical_result_url
        u = "http://www.baidu.com/link?url=seCYjor6Kg4"
        assert canonical_result_url(u) == u

    def test_plain_url_unchanged(self):
        from intelnexus.core.search.web import canonical_result_url
        assert canonical_result_url("https://kelen.cc/share/post1") == "https://kelen.cc/share/post1"

    def test_dedup_after_canonicalization(self):
        """同一篇文章经不同引擎/包装入库时只保留一条。"""
        from intelnexus.core.search.web import _dedup_results
        results = [
            {"title": "a", "url": YAHOO_WRAPPER, "source": "Yahoo"},
            {"title": "a-bing", "url": "https://juejin.cn/post/7678646261259092004/", "source": "Bing"},
            {"title": "b", "url": "https://kelen.cc/other", "source": "Bing"},
        ]
        unique = _dedup_results(results)
        assert len(unique) == 2
        # 保留的 URL 是解码后的真实地址
        assert unique[0]["url"] == "https://juejin.cn/post/7678646261259092004"


# ---------------------------------------------------------------------------
# P1: 时间冲突检测
# ---------------------------------------------------------------------------

def _make_results(n):
    return [{"title": f"result {i}", "source": f"Src{i}", "url": f"https://ex.com/{i}"}
            for i in range(n)]


class TestConflictDetector:
    def _detector(self):
        from intelnexus.analysis.credibility import ConflictDetector
        return ConflictDetector()

    def test_copyright_years_not_conflict(self):
        """版权页脚年份不应触发时间冲突（旧实现会报「相差 17 年」）。"""
        d = self._detector()
        results = _make_results(2)
        scraped = {
            "https://ex.com/0": "事件发生于 2026 年 8 月。© 2009-2026 All Rights Reserved",
            "https://ex.com/1": "事件发生于 2026 年 8 月。版权所有 ICP备12345号 2016-2026",
        }
        conflicts = [c for c in d.detect(results, scraped) if c["type"] == "temporal"]
        assert conflicts == []

    def test_bare_year_not_conflict(self):
        d = self._detector()
        results = _make_results(2)
        scraped = {
            "https://ex.com/0": "公司成立于 2009 年，一直在发展",
            "https://ex.com/1": "公司成立于 2009 年，一直在发展",
        }
        conflicts = [c for c in d.detect(results, scraped) if c["type"] == "temporal"]
        assert conflicts == []

    def test_real_date_conflict_detected_with_source_names(self):
        d = self._detector()
        results = _make_results(2)
        scraped = {
            "https://ex.com/0": "模型于 2026-08-20 发布上线",
            "https://ex.com/1": "模型于 2010-08-20 发布上线",
        }
        conflicts = [c for c in d.detect(results, scraped) if c["type"] == "temporal"]
        assert len(conflicts) == 1
        assert "Src0" in conflicts[0]["description"]
        assert "Src1" in conflicts[0]["description"]
        # 严重度随年份差伸缩（差 16 年 → 触顶 0.9；差 2 年应为 0.58）
        assert conflicts[0]["severity"] == pytest.approx(0.9, abs=0.01)

    def test_small_year_gap_lower_severity(self):
        d = self._detector()
        results = _make_results(2)
        scraped = {
            "https://ex.com/0": "模型于 2026-08-20 发布上线",
            "https://ex.com/1": "模型于 2024-08-20 发布上线",
        }
        conflicts = [c for c in d.detect(results, scraped) if c["type"] == "temporal"]
        assert len(conflicts) == 1
        assert conflicts[0]["severity"] == pytest.approx(0.58, abs=0.01)

    def test_close_years_not_conflict(self):
        d = self._detector()
        results = _make_results(2)
        scraped = {
            "https://ex.com/0": "发布于 2025-06-01",
            "https://ex.com/1": "发布于 2026-06-01",
        }
        conflicts = [c for c in d.detect(results, scraped) if c["type"] == "temporal"]
        assert conflicts == []

    def test_identical_stance_conflicts_deduped(self):
        """不同来源对产出相同描述时只保留一条。"""
        d = self._detector()
        results = _make_results(4)
        pos = "成功 突破 领先 进步 " * 3
        neg = "失败 风险 问题 危机 " * 3
        scraped = {
            "https://ex.com/0": pos, "https://ex.com/1": neg,
            "https://ex.com/2": pos, "https://ex.com/3": neg,
        }
        conflicts = [c for c in d.detect(results, scraped) if c["type"] == "stance"]
        descs = [c["description"] for c in conflicts]
        assert len(descs) == len(set(descs))
        # 描述里应带上来源名以便区分
        assert all("Src" in s for s in descs)


# ---------------------------------------------------------------------------
# P1: 域名权威度
# ---------------------------------------------------------------------------

class TestDomainAuthority:
    def _scorer(self):
        with patch("intelnexus.analysis.credibility.load_sentence_model", return_value=MagicMock()):
            from intelnexus.analysis.credibility import SourceScorer
            return SourceScorer()

    def test_platform_domain_scored_not_engine(self):
        """juejin.cn 的文章不应因来自 Yahoo 而按聚合器计分。"""
        s = self._scorer()
        assert s._domain_authority("https://juejin.cn/post/123", "Yahoo") == 0.6

    def test_subdomain_platform_matched(self):
        s = self._scorer()
        assert s._domain_authority("https://zhuanlan.zhihu.com/p/1", "Yahoo") == 0.6

    def test_redirect_host_falls_back_to_engine(self):
        """无法识别发布者的包装域才退回按引擎名评分。"""
        s = self._scorer()
        assert s._domain_authority("https://r.search.yahoo.com/x", "Yahoo") == 0.5

    def test_unknown_publisher_conservative_score(self):
        s = self._scorer()
        assert s._domain_authority("https://kelen.cc/share/x", "Yahoo") == 0.45


# ---------------------------------------------------------------------------
# P2: 热度
# ---------------------------------------------------------------------------

class TestHeatLevel:
    def test_duplicate_articles_counted_once(self):
        from intelnexus.export.report_builder import compute_heat_level
        results = [
            {"url": "https://a.com/x", "source": s}
            for s in ("Bing", "Yahoo", "Yandex", "Baidu")
        ]
        # 1 篇独立文章 + 3 个额外来源
        assert compute_heat_level(results) == 4 + 3 * 5

    def test_query_params_ignored(self):
        from intelnexus.export.report_builder import compute_heat_level
        results = [
            {"url": "https://a.com/x?utm=1", "source": "Bing"},
            {"url": "https://a.com/x", "source": "Bing"},
            {"url": "https://a.com/x/", "source": "Bing"},
        ]
        assert compute_heat_level(results) == 4

    def test_capped_at_100(self):
        from intelnexus.export.report_builder import compute_heat_level
        results = [{"url": f"https://a.com/{i}", "source": "Bing"} for i in range(60)]
        assert compute_heat_level(results) == 100


# ---------------------------------------------------------------------------
# P2: 实体 canonical_id
# ---------------------------------------------------------------------------

class TestEntityCanonicalId:
    def test_trailing_punctuation_merged(self):
        from intelnexus.analysis.intelligence_graph import EntityExtractor
        assert EntityExtractor._canonical_id("Ox Alpha") == EntityExtractor._canonical_id("Ox Alpha.")

    def test_noise_slug_filtered(self):
        from intelnexus.analysis.intelligence_graph import EntityExtractor
        assert EntityExtractor._is_noise_entity("about_get")
        assert EntityExtractor._is_noise_entity("specs_guides_try")

    def test_chinese_demonstrative_filtered(self):
        from intelnexus.analysis.intelligence_graph import EntityExtractor
        assert EntityExtractor._is_noise_entity("首次")
        assert EntityExtractor._is_noise_entity("这种技术")

    def test_real_entity_kept(self):
        from intelnexus.analysis.intelligence_graph import EntityExtractor
        assert not EntityExtractor._is_noise_entity("Ox Alpha")
        assert not EntityExtractor._is_noise_entity("智谱AI")
