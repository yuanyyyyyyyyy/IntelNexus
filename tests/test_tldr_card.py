"""TL;DR 速览卡测试。"""
import pytest

from intelnexus.core.llm.core import _build_system_prompt


class TestTLDRCard:
    def test_extract_tldr_basic(self):
        report = """## TL;DR 情报速览

**威胁等级**: 🔴 高危
**核心判断**: 存在严重安全风险
- 发现1
- 发现2
**行动建议**: 立即修复

---

## 一、执行摘要
详细内容...
"""
        # 内联提取逻辑测试
        import re
        m = re.search(r'## TL;DR 情报速览\s*\n(.*?)(?=\n---|\n## |\Z)', report, re.DOTALL)
        assert m is not None
        tldr = m.group(1).strip()
        assert "威胁等级" in tldr
        assert "高危" in tldr

    def test_extract_tldr_missing(self):
        report = "## 一、执行摘要\n没有速览卡的报告"
        import re
        m = re.search(r'## TL;DR 情报速览\s*\n(.*?)(?=\n---|\n## |\Z)', report, re.DOTALL)
        assert m is None

    def test_system_prompt_contains_template(self):
        prompt = _build_system_prompt("test query", "all")
        assert "TL;DR 情报速览" in prompt
        assert "威胁等级" in prompt
        assert "行动建议" in prompt
