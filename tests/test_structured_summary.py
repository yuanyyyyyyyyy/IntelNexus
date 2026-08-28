"""测试结构化摘要解析器"""
import pytest
from intelnexus.analysis.structured_summary import (
    extract_structured_summary,
    format_structured_summary_for_display,
)


class TestStructuredSummary:
    """结构化摘要解析器测试"""

    def test_extract_basic(self):
        """测试基本提取"""
        llm_output = """
## 二、结构化摘要（机器可读）

```json
{
  "facts": [
    {"text": "Ox Alpha 是 Z.ai 发布的模型", "confidence": 0.95, "sources": ["Bloomberg"]}
  ],
  "analyses": [
    {"text": "可能用于社区测试策略", "confidence": 0.65, "based_on": ["事实 1"]}
  ],
  "speculations": [
    {"text": "若开源则可能改变市场格局", "confidence": 0.45, "condition": "若开源"}
  ],
  "overall_confidence": 0.75
}
```
"""
        result = extract_structured_summary(llm_output)
        assert result is not None
        assert len(result["facts"]) == 1
        assert result["facts"][0]["text"] == "Ox Alpha 是 Z.ai 发布的模型"
        assert result["facts"][0]["confidence"] == 0.95
        assert len(result["analyses"]) == 1
        assert len(result["speculations"]) == 1
        assert result["overall_confidence"] == 0.75

    def test_extract_no_json(self):
        """测试无 JSON 时返回 None"""
        llm_output = "## 二、核心摘要\n没有 JSON 内容"
        result = extract_structured_summary(llm_output)
        assert result is None

    def test_extract_empty_input(self):
        """测试空输入"""
        result = extract_structured_summary("")
        assert result is None

    def test_extract_invalid_json(self):
        """测试无效 JSON"""
        llm_output = """
## 二、结构化摘要（机器可读）

```json
{invalid json}
```
"""
        result = extract_structured_summary(llm_output)
        assert result is None

    def test_extract_confidence_clamping(self):
        """测试 confidence 范围限制"""
        llm_output = """
```json
{
  "facts": [
    {"text": "事实", "confidence": 1.5, "sources": []}
  ],
  "analyses": [],
  "speculations": [
    {"text": "推测", "confidence": -0.5}
  ],
  "overall_confidence": 2.0
}
```
"""
        result = extract_structured_summary(llm_output)
        assert result is not None
        assert result["facts"][0]["confidence"] == 1.0  # 限制到 1.0
        assert result["speculations"][0]["confidence"] == 0.0  # 限制到 0.0
        assert result["overall_confidence"] == 1.0

    def test_format_display(self):
        """测试格式化显示"""
        data = {
            "facts": [
                {"text": "事实 1", "confidence": 0.95, "sources": ["Bloomberg"]}
            ],
            "analyses": [
                {"text": "分析 1", "confidence": 0.75, "based_on": ["事实 1"]}
            ],
            "speculations": [
                {"text": "推测 1", "confidence": 0.45, "condition": "若开源"}
            ],
            "overall_confidence": 0.75,
        }
        md = format_structured_summary_for_display(data)
        assert "总体置信度" in md
        assert "75%" in md
        assert "【事实】" in md
        assert "【分析判断】" in md
        assert "【推测】" in md
        assert "事实 1" in md
        assert "分析 1" in md
        assert "推测 1" in md

    def test_format_display_empty(self):
        """测试空数据格式化"""
        md = format_structured_summary_for_display({})
        assert md == ""

    def test_format_display_none(self):
        """测试 None 输入"""
        md = format_structured_summary_for_display(None)
        assert md == ""
