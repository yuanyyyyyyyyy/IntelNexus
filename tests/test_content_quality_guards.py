"""内容质量护栏测试：反编造抽查 + protection 板块豁免/优雅降级。

P0 背景（实锤自 briefing_20260822_041207.md）：
1. 攻击事件深度分析把模型脑补的数据写成事实（「1.875亿至7.5亿美元」
   「股价下跌逾12%」「ShieldBreak零日利用链」）——prompt 未要求标注推断。
2. 防护建议板块因「连续纯英文段落」校验误杀 LLM 输出，回退到
   _fallback_subsections 直接倾倒抓取器原始英文文本（粘连词转储）。
"""
import pytest

from intelnexus.briefing.analyzer import AIBriefingAnalyzer


@pytest.fixture
def analyzer():
    return AIBriefingAnalyzer(llm=None)


SOURCE = (
    "1. GitLab Critical Flaw\n   链接：https://example.com/a\n"
    "   来源：SecurityWeek\n   日期：2026-08-18\n   摘要：GitLab披露CVE-2026-19478，"
    "约375万名用户受影响，官方已发布补丁。\n"
)


def test_fabricated_percentage_detected(analyzer):
    """来源中没有的百分比、且无【推断】标注 → 判为疑似编造。"""
    out = "攻击者利用该漏洞后，相关公司股价在披露后一度下跌逾12%。"
    assert analyzer._find_unsourced_figures(out, SOURCE) == ["12%"]


def test_fabricated_money_detected(analyzer):
    """来源中没有的美元估值（含 million）→ 判为疑似编造。"""
    out = "潜在黑市价值高达 $187.5 million 至 $750 million。"
    suspects = analyzer._find_unsourced_figures(out, SOURCE)
    assert "$187.5million" in [s.replace(" ", "") for s in suspects]


def test_sourced_figures_pass(analyzer):
    """来源中真实存在的数字（375万）→ 放行。"""
    out = "本次事件影响约375万名用户。"
    assert analyzer._find_unsourced_figures(out, SOURCE) == []


def test_marked_inference_passes(analyzer):
    """显式标注【推断】的行不做抽查。"""
    out = "【推断】按行业均价估算，潜在损失或达数百万美元规模。"
    assert analyzer._find_unsourced_figures(out, SOURCE) == []


def test_validate_rejects_unsourced_attack_analysis(analyzer):
    """端到端：attack_analysis 输出含无来源数据 → 校验失败。"""
    bad = (
        "### 攻击事件深度分析\n\n#### 事件1：X 事件\n\n**事件概述**\n"
        "某公司遭遇攻击，股价下跌逾12%，市场震动。\n" + "补充说明。" * 10
    )
    assert analyzer._validate_llm_output(bad, "attack_analysis", source_text=SOURCE) is False


def test_validate_accepts_sourced_attack_analysis(analyzer):
    good = (
        "### 攻击事件深度分析\n\n#### 事件1：GitLab 事件\n\n**事件概述**\n"
        "官方确认约375万名用户受影响，已发布补丁并建议立即升级。\n" + "补充说明。" * 10
    )
    assert analyzer._validate_llm_output(good, "attack_analysis", source_text=SOURCE) is True


def test_protection_exempt_from_english_rule(analyzer):
    """protection 板块不再被连续纯英文规则误杀；其他板块仍拦截。"""
    english_dump = "\n".join(
        f"Vendor line {i}: critical security vulnerability patch released today"
        for i in range(4)
    )  # 4 行连续纯英文，>80 字符
    assert analyzer._validate_llm_output(english_dump, "protection") is True
    assert analyzer._validate_llm_output(english_dump, "links") is False


def test_protection_fallback_is_notice_not_raw_dump(analyzer):
    """降级输出明确告知，而不是倒抓取器原始英文条目。"""
    raw_results = [{
        "title": "zero-day-threat-reportZero-Day Threat Report May 2026",
        "description": "May 5,2026·This is arguably the most actively exploitedvulnerabilityon",
        "source": "Yahoo", "url": "https://example.com/x",
        "published_at": "2026-08-22",
    }]
    out = analyzer._get_fallback_content("protection", raw_results)
    assert "本日暂无可整理的防护建议" in out
    assert "exploitedvulnerabilityon" not in out
