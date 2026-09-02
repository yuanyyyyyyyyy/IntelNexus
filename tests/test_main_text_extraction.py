"""Tests for main-content extraction (trafilatura) and lazy Streamlit secrets probing."""

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parent.parent

# 模拟一个带导航/广告/侧栏 + 正文的页面
PAGE_HTML = """
<html><head><title>测试文章标题</title></head><body>
<nav><a href="/">首页</a><a href="/login">登录</a><a href="/vip">开通会员</a></nav>
<div class="ad">重型卡车 全能SUV 限时优惠 广告位招租</div>
<div class="sidebar"><ul><li>任务中心</li><li>讲师中心</li><li>账户中心</li></ul></div>
<article>
<h1>免费大模型 Token 领取指南</h1>
<p>阿里云百炼宣布新用户开通即可领取超过七千万 Token 的免费额度，覆盖七十多款主流模型，
有效期九十天，仅用于抵扣实时推理调用费用，用户可以在控制台开启免费额度用完即停功能。</p>
<p>除了阿里云之外，智谱 AI、火山引擎、百度千帆和硅基流动等平台也提供了类似的注册赠送活动，
开发者可以按需选择合适的平台进行模型评测和原型验证，注意各平台的额度有效期与计费边界。</p>
</article>
<footer>版权所有 © 2026 示例站点 备案号 12345678</footer>
</body></html>
"""

NAV_NOISE_WORDS = ("任务中心", "讲师中心", "限时优惠", "开通会员")
ARTICLE_WORDS = ("免费额度", "阿里云百炼", "计费边界")


class TestLazySecretsProbe:
    def test_no_runtime_secrets_not_accessed(self, monkeypatch):
        """非 Streamlit 运行时（CLI 启动进程）不得访问 st.secrets。"""
        import config
        monkeypatch.setattr("streamlit.runtime.exists", lambda: False)
        secrets_mock = MagicMock()
        secrets_mock.__contains__ = MagicMock(return_value=True)
        monkeypatch.setattr("streamlit.secrets", secrets_mock)
        monkeypatch.delenv("INTELNEXUS_TEST_KEY", raising=False)
        assert config._get_secret("INTELNEXUS_TEST_KEY", "fallback") == "fallback"
        secrets_mock.__contains__.assert_not_called()

    def test_runtime_secrets_used(self, monkeypatch):
        import config
        monkeypatch.setattr("streamlit.runtime.exists", lambda: True)
        monkeypatch.setattr("streamlit.secrets", {"INTELNEXUS_TEST_KEY": "from_secrets"})
        assert config._get_secret("INTELNEXUS_TEST_KEY") == "from_secrets"


class TestConfigImportDoesNotParse:
    def test_importing_config_skips_streamlit_config_parse(self):
        """直接验证根因消除：import config 不应触发 streamlit 配置解析。"""
        code = (
            "import sys; sys.path.insert(0, r'" + str(ROOT) + "');"
            "import streamlit.config as streamlit_config;"
            "import config;"
            "assert streamlit_config._config_options is None, "
            "'import config triggered streamlit config parse (st.secrets accessed at module level)'"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=str(ROOT), capture_output=True, text=True, timeout=120,
        )
        assert result.returncode == 0, f"stderr:\n{result.stderr[-2000:]}"
