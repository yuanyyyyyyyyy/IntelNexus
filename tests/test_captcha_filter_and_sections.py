"""Tests for captcha page filtering during scraping and entity noise filtering."""

import pytest


class TestCaptchaDetection:
    def test_wappass_url_detected(self):
        from intelnexus.core.search.scraper import _is_captcha_response
        assert _is_captcha_response(
            "https://wappass.baidu.com/static/captcha/tuxing_v2.html?ak=x", "随便什么文本")

    def test_captcha_path_detected(self):
        from intelnexus.core.search.scraper import _is_captcha_response
        assert _is_captcha_response("https://example.com/captcha/verify?id=1", "正常文本")

    def test_normal_url_not_detected(self):
        from intelnexus.core.search.scraper import _is_captcha_response
        assert not _is_captcha_response(
            "https://zhidao.baidu.com/question/123.html", "免费 token 领取攻略正文内容")

    def test_text_markers_fallback(self):
        """URL 无特征但正文出现多个验证特征词时兜底识别。"""
        from intelnexus.core.search.scraper import _is_captcha_response
        text = "安全验证 请完成安全验证 拖动滑块完成拼图 请输入验证码"
        assert _is_captcha_response("https://example.com/page", text)

    def test_single_marker_not_detected(self):
        from intelnexus.core.search.scraper import _is_captcha_response
        # 单个特征词（如正文恰好提到"安全验证"）不足以判定
        assert not _is_captcha_response(
            "https://example.com/post/1", "这篇文章讲的是网站的安全验证机制设计")

    def test_empty_inputs_safe(self):
        from intelnexus.core.search.scraper import _is_captcha_response
        assert not _is_captcha_response("", "")
        assert not _is_captcha_response(None, None)


class TestEntityNoiseFilter:
    def test_ui_instruction_phrases_filtered(self):
        """页面操作指令文案（验证码页/教程步骤）不应成为实体。"""
        from intelnexus.analysis.intelligence_graph import EntityExtractor
        assert EntityExtractor._is_noise_entity("点击右上角的用户中心")
        assert EntityExtractor._is_noise_entity("进入福利中心")
        assert EntityExtractor._is_noise_entity("后点击右上角用户中心")

    def test_normal_entity_kept(self):
        from intelnexus.analysis.intelligence_graph import EntityExtractor
        assert not EntityExtractor._is_noise_entity("阿里云百炼")
        assert not EntityExtractor._is_noise_entity("硅基流动")


class TestEvidenceChainMandatory:
    def test_validate_counts_evidence_chain(self):
        from intelnexus.core.llm.core import _validate_llm_output
        filler = "这是一段足够长的分析正文，用于通过输出长度下限校验。" * 3
        output = (
            "## 二、核心摘要\n" + filler + "\n"
            "## 六、证据链\n" + filler + "\n"
            "## 八、舆情趋势\n" + filler + "\n"
            "## 九、影响评估\n" + filler + "\n"
        )
        assert _validate_llm_output(output) == 4

    def test_validate_without_evidence_chain(self):
        from intelnexus.core.llm.core import _validate_llm_output
        filler = "这是一段足够长的分析正文，用于通过输出长度下限校验。" * 3
        output = (
            "## 二、核心摘要\n" + filler + "\n"
            "## 八、舆情趋势\n" + filler + "\n"
            "## 九、影响评估\n" + filler + "\n"
        )
        assert _validate_llm_output(output) == 3

    def test_short_output_returns_zero(self):
        from intelnexus.core.llm.core import _validate_llm_output
        assert _validate_llm_output("核心摘要 证据链 舆情趋势 影响评估") == 0

    def test_system_prompt_has_evidence_chain_as_mandatory(self):
        """证据链必须出现在必选板块组（可选板块判定语之前）。"""
        from intelnexus.core.llm.core import _build_system_prompt
        prompt = _build_system_prompt("测试主题", "web")
        mandatory_pos = prompt.find("必选板块")
        optional_pos = prompt.find("可选板块")
        chain_pos = prompt.find("## 六、证据链")
        assert 0 < mandatory_pos < optional_pos
        assert mandatory_pos < chain_pos < optional_pos

    def test_simplified_prompt_includes_evidence_chain(self):
        from intelnexus.core.llm.core import _build_simplified_prompt
        assert "证据链" in _build_simplified_prompt("测试主题", "web")
