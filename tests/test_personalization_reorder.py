"""参与度重排（personalization.filter_briefing_by_engagement）回归测试。

背景：旧实现按 '\\n' 字面量切分（转义错误）→ 功能从未生效；且重排用
'\\n\\n'.join 会丢分隔线、打乱模板「摘要→正文→附录」结构。修复后：
仅重排命中权重的分类板块，通用板块保持原位，逐行重组不丢内容。
"""
import pytest

from intelnexus.briefing import personalization
from intelnexus.briefing.personalization import filter_briefing_by_engagement


@pytest.fixture
def weights_for_cyber(monkeypatch):
    monkeypatch.setattr(
        personalization, "compute_category_weights",
        lambda sid: {"cyber_vuln": 1.5, "ai_gov_usage": 0.6},
    )


SAMPLE = "\n".join([
    "# AI 与网络安全每日情报简报",       # preamble（首个 ## 之前）
    "**AI情报团队**",
    "",
    "## 来源可信度概览",                 # 无分类映射（通用板块）
    "概览内容",
    "",
    "---",
    "",
    "## 近日要闻 TOP3",                  # 无分类映射（通用板块）
    "top3 内容",
    "",
    "---",
    "",
    "## 政府机构应用追踪",               # 「机构」→ ai_gov_usage，权重 0.6
    "AI 内容",
    "",
    "---",
    "",
    "## 漏洞利用预警",                   # 「漏洞」→ cyber_vuln，权重 1.5
    "安全内容",
])


def test_no_weights_returns_original():
    assert filter_briefing_by_engagement(SAMPLE, "sub-1") == SAMPLE


def test_reorder_keeps_preamble_and_structure(weights_for_cyber):
    out = filter_briefing_by_engagement(SAMPLE, "sub-1")
    lines = out.split("\n")
    # 头部不动
    assert lines[0] == "# AI 与网络安全每日情报简报"
    # 无内容丢失：行多重集一致（只允许顺序变化）
    assert sorted(out.split("\n")) == sorted(SAMPLE.split("\n"))
    # 分隔线数量不变
    assert out.count("---") == SAMPLE.count("---")
    # 高权重板块先于低权重板块
    assert out.index("## 漏洞利用预警") < out.index("## 政府机构应用追踪")
    # 加权板块整体前移到通用板块之前
    assert out.index("## 漏洞利用预警") < out.index("## 来源可信度概览")


def test_unmapped_sections_keep_relative_order(weights_for_cyber):
    out = filter_briefing_by_engagement(SAMPLE, "sub-1")
    idx_top3 = out.index("## 近日要闻 TOP3")
    idx_overview = out.index("## 来源可信度概览")
    # 未加权板块相对顺序保持（概览在 TOP3 前，与原文一致）
    assert idx_overview < idx_top3


def test_extract_category_from_title_maps_known_sections():
    f = personalization._extract_category_from_title
    assert f("漏洞预警与利用动态") == "cyber_vuln"
    assert f("政府机构使用动态") == "ai_gov_usage"
    assert f("完全无关的板块标题") is None
