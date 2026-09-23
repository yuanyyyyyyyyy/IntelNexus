"""证据角标必须在结构化组装之后注入（回归：组装覆盖导致角标丢失）。"""
import inspect

from intelnexus.ui import search_worker
from intelnexus.ui.search_worker import apply_evidence_anchors

_EVIDENCE = {
    "claims": [{
        "text": "该漏洞影响范围为 OpenSSL 1.1.1 至 3.0.7",
        "confidence": 0.8,
        "is_unsupported": False,
        "evidence": [{"url": "https://nvd.nist.gov/vuln/detail/CVE-2024-0001",
                      "confidence": 0.85}],
    }]
}

# 模拟 build_intelligence_report 的产物：LLM 结论文本被并入板块正文
_ASSEMBLED = (
    "# 情报报告\n\n## 二. 核心摘要\n\n"
    "该漏洞影响范围为 OpenSSL 1.1.1 至 3.0.7，需尽快排查受影响资产。\n"
)


class TestApplyEvidenceAnchors:
    def test_injects_into_assembled_report(self):
        result = {"streamed_summary": _ASSEMBLED, "evidence_data": _EVIDENCE}
        assert apply_evidence_anchors(result) is True
        assert "<sup>[1]</sup>" in result["streamed_summary"]
        assert "## 证据参考" in result["streamed_summary"]

    def test_no_evidence_keeps_report_untouched(self):
        result = {"streamed_summary": _ASSEMBLED, "evidence_data": None}
        assert apply_evidence_anchors(result) is False
        assert result["streamed_summary"] == _ASSEMBLED

    def test_empty_report_skipped(self):
        result = {"streamed_summary": "", "evidence_data": _EVIDENCE}
        assert apply_evidence_anchors(result) is False

    def test_anchor_absent_still_lists_references(self):
        """结论板块在组装时被裁掉：不插上标，但「证据参考」清单仍会附上。

        这是 annotate_report 的既有行为——参考清单按 URL 聚合，不依赖锚点是否
        命中。这里把行为钉住，防止以后被顺手改掉；若要让清单也一并省略，
        需要改 annotate_report 并同步 06 板块的展示口径。
        """
        result = {"streamed_summary": "# 报告\n\n正文里没有那句结论。\n",
                  "evidence_data": _EVIDENCE}
        assert apply_evidence_anchors(result) is True
        body = result["streamed_summary"]
        assert "<sup>" not in body
        assert "## 证据参考" in body


class TestInjectionOrder:
    def test_anchors_applied_after_report_assembly(self):
        """角标注入必须晚于组装覆盖，否则又被 streamed_summary 整体替换掉。"""
        src = inspect.getsource(search_worker.run_search_computation)
        assemble = src.find('result["streamed_summary"] = assembled')
        inject = src.find("apply_evidence_anchors(result)")
        assert assemble != -1 and inject != -1
        assert inject > assemble
        # 组装之前不得再有直接调用 annotate_report 的旧路径
        assert src.find("annotate_report(") == -1 or src.find("annotate_report(") > assemble
