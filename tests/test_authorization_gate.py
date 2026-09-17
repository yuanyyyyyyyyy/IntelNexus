"""P0-3 授权闸门回归：针对具名实体的侦察意图必须显式声明授权。

审计背景（报告 INTEL-20260916-001）：查询「华盛顿华尔道夫酒店位置华盛顿特区
宾夕法尼亚大道西北1100号:对酒店所有设施开展调研加漏洞」针对真实在营实体
（该址为联邦历史建筑 Old Post Office，GSA 资产）请求「设施 + 漏洞」侦察，
报告却没有任何授权状态 / 测试边界声明，并直接输出了攻击面分析章节。

未授权时系统必须降级为纯 OSINT：不生成攻击面、利用路径、探测步骤等
可被直接用于主动测试的内容。
"""

import pytest

from intelnexus.core.search.authorization import assess_authorization

HOTEL_QUERY = "华盛顿华尔道夫酒店位置华盛顿特区宾夕法尼亚大道西北1100号:对酒店所有设施开展调研加漏洞"


# ===========================================================================
# 意图识别
# ===========================================================================

class TestIntentDetection:
    def test_named_entity_plus_vuln_requires_authorization(self):
        r = assess_authorization(HOTEL_QUERY)
        assert r["requires_authorization"] is True
        assert r["authorized"] is False

    def test_company_penetration_requires_authorization(self):
        r = assess_authorization("对某某公司的办公网开展渗透测试，找出可利用漏洞")
        assert r["requires_authorization"] is True

    def test_hostname_scan_requires_authorization(self):
        r = assess_authorization("scan example.com for open ports and vulnerabilities")
        assert r["requires_authorization"] is True

    def test_ip_target_requires_authorization(self):
        r = assess_authorization("对 192.168.1.10 做漏洞扫描")
        assert r["requires_authorization"] is True

    def test_generic_cve_research_does_not(self):
        """公开 CVE 的原理研究不是针对具名实体的侦察，不应被闸门拦截。"""
        r = assess_authorization("log4shell 漏洞原理与影响范围")
        assert r["requires_authorization"] is False

    def test_pure_travel_query_does_not(self):
        r = assess_authorization("华盛顿特区旅游攻略与酒店推荐")
        assert r["requires_authorization"] is False

    def test_matched_intent_reported(self):
        r = assess_authorization(HOTEL_QUERY)
        assert r["matched_intent"]

    def test_scope_note_present_when_required(self):
        r = assess_authorization(HOTEL_QUERY)
        assert r["scope_note"]


# ===========================================================================
# 授权声明
# ===========================================================================

class TestAuthorizationDeclaration:
    def test_explicit_authorization_marker(self):
        r = assess_authorization("已获书面授权：对某某公司办公网开展渗透测试")
        assert r["requires_authorization"] is True
        assert r["authorized"] is True

    def test_english_authorization_marker(self):
        r = assess_authorization("authorized penetration test against example.com")
        assert r["authorized"] is True

    def test_explicit_flag_overrides(self):
        r = assess_authorization(HOTEL_QUERY, authorization_declared=True)
        assert r["authorized"] is True

    def test_gate_can_be_disabled_by_config(self):
        r = assess_authorization(HOTEL_QUERY, enabled=False)
        assert r["requires_authorization"] is False
        assert r["authorized"] is True


# ===========================================================================
# 降级：未授权不得输出攻击面内容
# ===========================================================================

class TestAttackSurfaceSuppression:
    def test_report_replaces_attack_surface_with_notice(self):
        from intelnexus.export.report_builder import build_attack_surface
        out = build_attack_surface({"attack_surface": "**1. API/接口层**\n- 风险点：越权"},
                                   authorized=False)
        assert "API/接口层" not in out
        assert "未声明授权" in out
        assert "OSINT" in out

    def test_authorized_report_keeps_attack_surface(self):
        from intelnexus.export.report_builder import build_attack_surface
        out = build_attack_surface({"attack_surface": "**1. API/接口层**\n- 风险点：越权"},
                                   authorized=True)
        assert "API/接口层" in out

    def test_prompt_drops_attack_surface_when_unauthorized(self):
        from intelnexus.core.llm.core import _build_system_prompt
        prompt = _build_system_prompt(HOTEL_QUERY, "all", authorized=False)
        assert "攻击面分析" not in prompt

    def test_prompt_keeps_attack_surface_when_authorized(self):
        from intelnexus.core.llm.core import _build_system_prompt
        prompt = _build_system_prompt(HOTEL_QUERY, "all", authorized=True)
        assert "攻击面分析" in prompt

    def test_prompt_adds_osint_boundary_when_unauthorized(self):
        from intelnexus.core.llm.core import _build_system_prompt
        prompt = _build_system_prompt(HOTEL_QUERY, "all", authorized=False)
        assert "公开信息" in prompt
        assert "禁止" in prompt

    def test_overview_renders_authorization_status(self):
        from intelnexus.export.report_builder import build_report_overview
        out = build_report_overview(
            HOTEL_QUERY, "all", "m", {"Bing": 1}, 1,
            authorization={"requires_authorization": True, "authorized": False},
        )
        assert "未声明授权" in out


# ===========================================================================
# 闸门精度（评审 B2/B3）
# ===========================================================================

class TestGatePrecision:
    def test_bare_brand_name_target_is_caught(self):
        """「华尔道夫」不带通用后缀也必须触发（B2 漏报场景）。"""
        r = assess_authorization("对华尔道夫做渗透测试，找出可利用漏洞")
        assert r["requires_authorization"] is True

    def test_english_asset_word_is_caught(self):
        r = assess_authorization("scan the hotel network for vulnerabilities")
        assert r["requires_authorization"] is True

    def test_generic_platform_query_not_flagged(self):
        """通用产品的防守型研究不是针对性侦察（B3 误报场景）。"""
        for q in ("Windows 系统漏洞修复建议",
                  "CVE-2021-44228 log4shell 漏洞复现与防护",
                  "网站漏洞扫描工具对比"):
            assert assess_authorization(q)["requires_authorization"] is False, q

    def test_platform_named_with_real_org_still_flagged(self):
        r = assess_authorization("对某某公司部署的 Windows 系统做渗透测试")
        assert r["requires_authorization"] is True


# ===========================================================================
# 闸门可靠性（评审 B4）
# ===========================================================================

class TestGateReliability:
    def test_context_words_do_not_self_authorize(self):
        """「红队/靶场」是场景词不是授权声明，不得据此放行。"""
        r = assess_authorization("对某某公司办公网开展渗透测试（红队靶场环境）")
        assert r["requires_authorization"] is True
        assert r["authorized"] is False

    def test_gate_failure_fails_closed(self, monkeypatch):
        """闸门异常时必须按未授权降级，不能 fail-open。"""
        import intelnexus.core.search.authorization as auth

        def _boom(*args, **kwargs):
            raise RuntimeError("gate exploded")

        monkeypatch.setattr(auth, "assess_authorization", _boom)
        from intelnexus.ui import search_worker
        result = search_worker._assess_authorization_safe("对某某公司做渗透测试")
        assert result["authorized"] is False
        assert result["requires_authorization"] is True

    def test_unauthorized_addendum_survives_retry_prompt(self):
        """LLM 重试路径也不得丢失合规约束。"""
        from intelnexus.core.llm.core import _build_simplified_prompt
        prompt = _build_simplified_prompt(HOTEL_QUERY, "all", authorized=False)
        assert "OSINT" in prompt or "公开信息" in prompt


# ===========================================================================
# LLM 兜底判定（只收紧、不放宽）
# ===========================================================================

def _llm(answer: str):
    """LCEL 要求链上每个组件都是 Runnable，直接用 RunnableLambda 伪装 LLM。"""
    from langchain_core.runnables import RunnableLambda
    return RunnableLambda(lambda _input: answer)


def _broken_llm():
    from langchain_core.runnables import RunnableLambda

    def _raise(_input):
        raise RuntimeError("llm down")

    return RunnableLambda(_raise)


# 规则层无法命中目标的查询（无「对 X 做」句式、无后缀词、无主机名）
BARE_BRAND_QUERY = "调研华尔道夫的所有设施是否存在漏洞"


class TestLlmTargetCheck:
    def test_targeted_answer(self):
        from intelnexus.core.search.authorization import llm_target_check
        assert llm_target_check(_llm("TARGETED"), BARE_BRAND_QUERY) is True

    def test_not_targeted_answer(self):
        from intelnexus.core.search.authorization import llm_target_check
        assert llm_target_check(
            _llm("NOT_TARGETED"), "log4shell 漏洞原理") is False

    def test_no_llm_returns_none(self):
        from intelnexus.core.search.authorization import llm_target_check
        assert llm_target_check(None, "q") is None

    def test_llm_failure_returns_none(self):
        from intelnexus.core.search.authorization import llm_target_check
        assert llm_target_check(_broken_llm(), BARE_BRAND_QUERY) is None

    def test_garbage_answer_returns_none(self):
        from intelnexus.core.search.authorization import llm_target_check
        assert llm_target_check(_llm("我觉得还行吧"), BARE_BRAND_QUERY) is None


class TestLlmHintOnlyTightens:
    def test_hint_turns_missed_target_into_hit(self):
        from intelnexus.core.search.authorization import assess_authorization
        r = assess_authorization(BARE_BRAND_QUERY, llm_target_hint=True)
        assert r["requires_authorization"] is True
        assert r["authorized"] is False

    def test_hint_without_intent_does_nothing(self):
        from intelnexus.core.search.authorization import assess_authorization
        r = assess_authorization("华尔道夫酒店住宿体验", llm_target_hint=True)
        assert r["requires_authorization"] is False

    def test_hint_cannot_relax_rule_hit(self):
        """规则层已命中目标时，LLM 说「否」也不得放行。"""
        from intelnexus.core.search.authorization import assess_authorization
        r = assess_authorization("对某某公司办公网开展渗透测试",
                                 llm_target_hint=False)
        assert r["requires_authorization"] is True

    def test_hint_none_keeps_rule_result(self):
        from intelnexus.core.search.authorization import assess_authorization
        r = assess_authorization(BARE_BRAND_QUERY, llm_target_hint=None)
        assert r["requires_authorization"] is False


class TestWorkerLlmFallback:
    def test_worker_uses_llm_fallback_for_bare_brand(self):
        from intelnexus.ui import search_worker
        assert search_worker._assess_authorization_safe(
            BARE_BRAND_QUERY, llm=_llm("TARGETED")
        )["requires_authorization"] is True

    def test_worker_does_not_call_llm_when_rule_hits(self, monkeypatch):
        import intelnexus.core.search.authorization as auth
        calls = {"n": 0}

        def _spy(llm, query):
            calls["n"] += 1
            return True

        monkeypatch.setattr(auth, "llm_target_check", _spy)
        from intelnexus.ui import search_worker
        search_worker._assess_authorization_safe("对某某公司办公网开展渗透测试",
                                                 llm=object())
        assert calls["n"] == 0

    def test_worker_no_llm_keeps_rule_result(self):
        from intelnexus.ui import search_worker
        r = search_worker._assess_authorization_safe(BARE_BRAND_QUERY)
        assert r["requires_authorization"] is False
