"""P1-3 证据链可核验性回归。

审计背景（报告 INTEL-20260916-001）：结论 1 的 E2 引用
「Expedia 页面标题显示…（来源：Expedia，来源等级：B，支持度：中）」，
但原始证据清单 14 条中没有任何 Expedia URL —— 该证据无法回溯，
却被赋予 B 级可信度。E3 则依赖 4 条不可溯源的 baidu 跳转链接。

要求：证据链中引用的来源若无法在本次原始证据清单中定位，必须显式标注
「未核验」，不得无声地当作已证实证据。
"""

import pytest

from intelnexus.export.report_builder import build_evidence_chain

# 本次检索的原始证据（摘要形式）：出版方为 agoda.com，检索渠道 Agoda/Baidu
RESULTS = [
    {"title": "华尔道夫酒店-华盛顿特区", "url": "https://www.agoda.com/hotel/a.html",
     "publisher": "agoda.com", "source": "Baidu"},
    {"title": "华盛顿酒店预订", "url": "https://hotels.ctrip.com/hotels/1.html",
     "publisher": "hotels.ctrip.com", "source": "Bing"},
]

# 审计报告中的真实证据链片段（含无法核验的 Expedia 引用）
AUDIT_EVIDENCE = """**结论 1**：华尔道夫酒店华盛顿特区在公开预订与旅游渠道中存在可见信息。
- E1：Agoda 页面标题显示相关预订信息（来源：Agoda，来源等级：B，支持度：中）
- E2：Expedia 页面标题显示点评与优惠（来源：Expedia，来源等级：B，支持度：中）
**综合置信度**：中
"""

# LLM 原始输出的形态：板块带标题
AUDIT_LLM_OUTPUT = "## 六、证据链分析\n\n" + AUDIT_EVIDENCE


class TestCitationVerification:
    def test_unverifiable_ascii_citation_flagged(self):
        out = build_evidence_chain(RESULTS, None, None,
                                   {"evidence_chain": AUDIT_EVIDENCE})
        assert "Expedia" in out
        assert "未核验" in out

    def test_verifiable_citation_not_flagged(self):
        out = build_evidence_chain(RESULTS, None, None,
                                   {"evidence_chain": AUDIT_EVIDENCE})
        warning_block = out.split("未核验")[-1]
        assert "Agoda" not in warning_block

    def test_no_warning_when_all_citations_resolve(self):
        evidence = "**结论 1**：x\n- E1：y（来源：Agoda，来源等级：B，支持度：中）\n"
        out = build_evidence_chain(RESULTS, None, None,
                                   {"evidence_chain": evidence})
        assert "未核验" not in out

    def test_cjk_citation_not_falsely_flagged(self):
        """中文品牌名与域名无法自动比对，宁可漏报也不误报。"""
        evidence = "**结论 1**：x\n- E1：y（来源：携程酒店，来源等级：B，支持度：中）\n"
        out = build_evidence_chain(RESULTS, None, None,
                                   {"evidence_chain": evidence})
        assert "未核验" not in out

    def test_no_results_means_no_verification_claim(self):
        """没有原始证据清单时不产生核验结论。"""
        out = build_evidence_chain([], None, None,
                                   {"evidence_chain": AUDIT_EVIDENCE})
        assert "未核验" not in out

    def test_end_to_end_report_surfaces_warning(self):
        from intelnexus.export.report_builder import build_intelligence_report
        out = build_intelligence_report(
            query="q", search_mode="all", model="m",
            llm_output=AUDIT_LLM_OUTPUT, results=RESULTS,
            source_counts={"Baidu": 1, "Bing": 1}, source_stats={},
            scraped={},
        )
        assert "未核验" in out
