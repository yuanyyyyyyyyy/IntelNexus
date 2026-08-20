"""行动项提取模块测试。"""
import pytest

from intelnexus.analysis.action_extractor import extract_actions, format_actions


class TestActionExtractor:
    def test_extract_actions_basic(self):
        report = """## 六、风险与建议

### 6.1 主要风险
存在安全漏洞。

### 6.2 行动建议
- 立即修复所有高危漏洞
- 本周完成安全审计
- 建议关注后续更新
"""
        actions = extract_actions(report)
        assert len(actions) == 3
        assert actions[0]["priority"] == "high"
        assert actions[0]["deadline"] == "immediate"
        assert actions[1]["deadline"] == "this_week"
        assert actions[2]["priority"] == "low"

    def test_extract_actions_empty_report(self):
        assert extract_actions("") == []
        assert extract_actions("没有行动建议部分") == []

    def test_format_actions(self):
        actions = [
            {"priority": "high", "action": "修复漏洞", "deadline": "immediate"},
            {"priority": "low", "action": "关注更新", "deadline": "this_month"},
        ]
        result = format_actions(actions)
        assert "行动项清单" in result
        assert "🔴" in result
        assert "🟢" in result
        assert "修复漏洞" in result
