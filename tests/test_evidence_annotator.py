"""证据角标注入器测试。"""
import pytest

from intelnexus.analysis.evidence_annotator import annotate_report


class TestEvidenceAnnotator:
    def test_annotate_injects_footnote(self):
        report = "这是一段测试文本，用于验证角标注入功能。"
        evidence = {
            "claims": [{
                "text": "这是一段测试文本，用于验证角标注入功能",
                "confidence": 0.8,
                "is_unsupported": False,
                "evidence": [{"url": "https://example.com/article", "confidence": 0.85}],
            }]
        }
        result = annotate_report(report, evidence)
        assert "<sup>[1]</sup>" in result
        assert "证据参考" in result

    def test_annotate_no_evidence(self):
        report = "没有证据数据"
        result = annotate_report(report, {})
        assert result == "没有证据数据"

    def test_annotate_reference_section(self):
        report = "关键发现：系统存在漏洞。"
        evidence = {
            "claims": [{
                "text": "关键发现：系统存在漏洞",
                "confidence": 0.6,
                "is_unsupported": False,
                "evidence": [{"url": "https://security.com/vuln", "confidence": 0.7}],
            }]
        }
        result = annotate_report(report, evidence)
        assert "## 证据参考" in result
        assert "Security" in result
        assert "查看原文" in result

    def test_annotate_low_confidence_skip(self):
        report = "低置信度内容。"
        evidence = {
            "claims": [{
                "text": "低置信度内容",
                "confidence": 0.3,
                "is_unsupported": False,
                "evidence": [{"url": "https://x.com", "confidence": 0.3}],
            }]
        }
        result = annotate_report(report, evidence)
        assert "<sup>" not in result
        assert result == "低置信度内容。"

    def test_annotate_empty_report(self):
        result = annotate_report("", {"claims": []})
        assert result == ""
