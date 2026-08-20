"""报告可视化模块测试。"""
import pytest


class TestVisualizer:
    def test_generate_threat_chart_no_data(self):
        from intelnexus.analysis.visualizer import generate_threat_chart
        result = generate_threat_chart({"claims": []})
        assert result is None

    def test_generate_threat_chart_with_data(self):
        from intelnexus.analysis.visualizer import generate_threat_chart
        evidence = {
            "claims": [
                {"confidence": 0.8, "text": "high"},
                {"confidence": 0.5, "text": "medium"},
                {"confidence": 0.2, "text": "low"},
            ]
        }
        result = generate_threat_chart(evidence)
        assert result is not None
        assert isinstance(result, str)
        assert len(result) > 100

    def test_inject_visuals_no_charts(self):
        from intelnexus.analysis.visualizer import inject_visuals
        report = "## 五、关键数据\n\n表格内容"
        result = inject_visuals(report, {})
        assert result == report
