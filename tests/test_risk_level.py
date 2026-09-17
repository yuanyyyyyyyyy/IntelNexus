"""P0-2 风险等级回归：风险必须与实际威胁证据挂钩，与来源可信度无关。

审计背景（报告 INTEL-20260916-001）：风险等级由「来源平均可信度」反推
（avg_score < 0.6 → 中），导致「资料质量差」被呈现为「目标有中等风险」，
且资料越权威风险等级反而越低。本文件锚定的核心不变量是
**可信度不得参与风险等级计算**。
"""

import pytest

from intelnexus.analysis.risk_level import (
    LEVEL_INSUFFICIENT,
    compute_risk_level,
    collect_risk_evidence,
    risk_level_rank,
)


def _ev(**kw):
    base = {
        "kev_hits": 0,
        "cve_hits": 0,
        "exploit_hits": 0,
        "ti_source_hits": 0,
        "conflict_max_severity": 0.0,
    }
    base.update(kw)
    return base


# ===========================================================================
# 无证据 → 证据不足（绝不返回「中」）
# ===========================================================================

class TestNoEvidence:
    def test_empty_evidence_is_insufficient(self):
        level, _ = compute_risk_level(_ev())
        assert level == LEVEL_INSUFFICIENT

    def test_empty_evidence_dict(self):
        level, _ = compute_risk_level({})
        assert level == LEVEL_INSUFFICIENT

    def test_none_evidence(self):
        level, _ = compute_risk_level(None)
        assert level == LEVEL_INSUFFICIENT

    def test_never_returns_middle_without_evidence(self):
        """旧实现的病征：语料质量差 → 风险「中」。"""
        level, _ = compute_risk_level(_ev())
        assert level != "中"

    def test_reason_mentions_insufficient(self):
        _, reason = compute_risk_level(_ev())
        assert "证据" in reason


# ===========================================================================
# 有证据 → 按强度分级
# ===========================================================================

class TestGradedLevels:
    def test_kev_hit_is_high(self):
        level, _ = compute_risk_level(_ev(kev_hits=1))
        assert level == "高"

    def test_public_exploit_is_high(self):
        level, _ = compute_risk_level(_ev(exploit_hits=1))
        assert level == "高"

    def test_many_cves_is_high(self):
        level, _ = compute_risk_level(_ev(cve_hits=3))
        assert level == "高"

    def test_single_cve_is_medium(self):
        level, _ = compute_risk_level(_ev(cve_hits=1))
        assert level == "中"

    def test_ti_source_hit_is_medium(self):
        level, _ = compute_risk_level(_ev(ti_source_hits=1))
        assert level == "中"

    def test_high_severity_conflict_is_medium(self):
        level, _ = compute_risk_level(_ev(conflict_max_severity=0.6))
        assert level == "中"

    def test_low_severity_conflict_is_low(self):
        level, _ = compute_risk_level(_ev(conflict_max_severity=0.2))
        assert level == "低"

    def test_high_beats_medium_when_mixed(self):
        level, _ = compute_risk_level(_ev(kev_hits=1, cve_hits=1))
        assert level == "高"


# ===========================================================================
# 与可信度解耦（最关键的反向场景）
# ===========================================================================

class TestDecoupledFromCredibility:
    def test_high_credibility_does_not_lower_risk(self):
        """权威语料 + KEV 命中，仍应为高 —— 旧实现会因 avg 高而降到「低」。"""
        level, _ = compute_risk_level(_ev(kev_hits=1))
        assert level == "高"

    def test_low_credibility_does_not_raise_risk(self):
        """低质语料本身不是风险信号，不得因此升级。"""
        level, _ = compute_risk_level(_ev())
        assert level == LEVEL_INSUFFICIENT

    def test_credibility_key_is_ignored(self):
        """即便传入可信度字段也必须被忽略（防止暗中重新引入）。"""
        level, _ = compute_risk_level(_ev(avg_score=0.2, credibility=0.1))
        assert level == LEVEL_INSUFFICIENT


# ===========================================================================
# 证据采集
# ===========================================================================

class TestCollectRiskEvidence:
    def test_counts_cve_mentions(self):
        results = [
            {"title": "CVE-2026-1234 远程代码执行", "source": "NVD"},
            {"title": "CVE-2026-5678 提权", "source": "NVD"},
        ]
        ev = collect_risk_evidence(results)
        assert ev["cve_hits"] >= 2
        assert ev["ti_source_hits"] >= 1

    def test_counts_kev_source(self):
        results = [{"title": "某产品漏洞", "source": "CISA_KEV"}]
        ev = collect_risk_evidence(results)
        assert ev["kev_hits"] == 1

    def test_counts_exploit_source(self):
        results = [{"title": "PoC", "source": "ExploitDB"}]
        ev = collect_risk_evidence(results)
        assert ev["exploit_hits"] == 1

    def test_hotel_query_yields_no_threat_evidence(self):
        """审计样本：全是旅游/预订内容，不应产生任何威胁证据。"""
        results = [
            {"title": "华尔道夫酒店-华盛顿特区的必住理由", "source": "Baidu"},
            {"title": "华盛顿酒店预订价格", "source": "Bing"},
            {"title": "AI 时代隐晦式安全已死", "source": "Solidot"},
        ]
        ev = collect_risk_evidence(results)
        level, _ = compute_risk_level(ev)
        assert level == LEVEL_INSUFFICIENT

    def test_conflict_severity_propagates(self):
        ev = collect_risk_evidence(
            [{"title": "a", "source": "Bing"}],
            conflicts=[{"severity": 0.8}, {"severity": 0.3}],
        )
        assert ev["conflict_max_severity"] == pytest.approx(0.8)

    def test_repeated_cve_id_counted_once(self):
        """同一 CVE 被多篇报道转载不等于多个独立漏洞证据。"""
        results = [{"title": f"CVE-2026-1234 报道 {i}", "source": "Bing"}
                   for i in range(3)]
        ev = collect_risk_evidence(results)
        assert ev["cve_hits"] == 1

    def test_ti_hits_count_distinct_sources(self):
        """同一情报源的 3 篇文章只算 1 个来源。"""
        results = [{"title": f"情报 {i}", "source": "NVD"} for i in range(3)]
        ev = collect_risk_evidence(results)
        assert ev["ti_source_hits"] == 1

    def test_security_news_is_not_threat_intel(self):
        """FreeBuf/安全客等是安全媒体，不是威胁情报源，不得据此判「高」。"""
        results = [{"title": f"行业新闻 {i}", "source": s}
                   for i, s in enumerate(("FreeBuf", "安全客", "先知社区"))]
        level, _ = compute_risk_level(collect_risk_evidence(results))
        assert level != "高"


# ===========================================================================
# 等级序（供 event_store 比较风险变化）
# ===========================================================================

class TestRiskLevelRank:
    def test_ordering(self):
        assert risk_level_rank(LEVEL_INSUFFICIENT) < risk_level_rank("低")
        assert risk_level_rank("低") < risk_level_rank("中")
        assert risk_level_rank("中") < risk_level_rank("高")

    def test_unknown_level_is_lowest(self):
        assert risk_level_rank("未知") == risk_level_rank(LEVEL_INSUFFICIENT)


# ===========================================================================
# 历史变化检测：跨「证据不足」不产生风险升降
# ===========================================================================

@pytest.fixture
def store(tmp_path, monkeypatch):
    from intelnexus.analysis import event_store as es
    monkeypatch.setattr(es, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(es, "_STORE_PATH", tmp_path / "event_store.json")
    return es.EventStore()


def _snap(risk, heat=10):
    return {
        "identity_status": "unknown", "heat_level": heat,
        "risk_level": risk, "key_findings": [], "source_count": 1,
        "result_count": 1,
    }


class TestEventStoreRiskChange:
    def test_graded_change_reported(self, store):
        store.save_snapshot("t", _snap("低"))
        changes = store.detect_changes("t", _snap("中"))
        assert changes["risk_change"] == "低 → 中"

    def test_same_level_not_reported(self, store):
        store.save_snapshot("t", _snap("中"))
        changes = store.detect_changes("t", _snap("中"))
        assert not changes.get("risk_change")

    def test_insufficient_to_graded_is_not_risk_change(self, store):
        """「证据不足 → 高」是新增证据，不是风险升高，不能记为风险变化。"""
        store.save_snapshot("t", _snap(LEVEL_INSUFFICIENT))
        changes = store.detect_changes("t", _snap("高"))
        assert not changes.get("risk_change")
        assert changes.get("risk_evidence_change") == f"{LEVEL_INSUFFICIENT} → 高"

    def test_graded_to_insufficient_is_not_risk_change(self, store):
        store.save_snapshot("t", _snap("高"))
        changes = store.detect_changes("t", _snap(LEVEL_INSUFFICIENT))
        assert not changes.get("risk_change")
        assert changes.get("risk_evidence_change") == f"高 → {LEVEL_INSUFFICIENT}"

    def test_insufficient_constant_matches_risk_module(self):
        """存储层的常量必须与 risk_level 模块保持同值，防止口径漂移。"""
        from intelnexus.analysis import event_store as es
        assert es._INSUFFICIENT_LEVEL == LEVEL_INSUFFICIENT


class TestEventHistoryRendering:
    def test_risk_evidence_change_rendered(self):
        from intelnexus.export.report_builder import build_event_history
        out = build_event_history({
            "has_history": True, "search_count": 2,
            "risk_evidence_change": f"{LEVEL_INSUFFICIENT} → 高",
        })
        assert "风险证据状态变化" in out
        assert LEVEL_INSUFFICIENT in out

    def test_plain_risk_change_still_rendered(self):
        from intelnexus.export.report_builder import build_event_history
        out = build_event_history({
            "has_history": True, "search_count": 2, "risk_change": "低 → 中",
        })
        assert "风险等级变化" in out
