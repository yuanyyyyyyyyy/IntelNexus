"""Tests for _is_small_model: explicit param-size flags only, no series-prefix guessing.

背景：旧实现用 'qwen3.' 等系列前缀猜小模型，把云端旗舰（qwen3-max、
qwen3.8-max）误判为小模型导致输入被截断到 25000 字符。
"""

import pytest


class TestIsSmallModel:
    @pytest.mark.parametrize("name", [
        "qwen3.8-max", "qwen3.8-max-0902", "qwen3-max", "qwen-max",
        "kimi-k3", "glm-5.3", "deepseek-v4-flash", "deepseek-v4-pro",
        "gpt-5", "claude-sonnet-4", "qwen3.8-flash", "llama-4",
    ])
    def test_flagship_and_cloud_models_not_small(self, name):
        from intelnexus.core.llm.core import _is_small_model
        assert _is_small_model(name) is False

    @pytest.mark.parametrize("name", [
        "qwen3.8-27b", "qwen2.5-7b", "llama-3.1-8b", "mistral-14b",
        "tiny-3b", "Qwen3-1.5B", "qwen2.5-0.5b",
    ])
    def test_explicit_param_flags_are_small(self, name):
        from intelnexus.core.llm.core import _is_small_model
        assert _is_small_model(name) is True

    def test_case_insensitive(self):
        from intelnexus.core.llm.core import _is_small_model
        assert _is_small_model("Qwen3.8-27B") is True
        assert _is_small_model("Qwen3.8-Max") is False

    def test_empty_name_not_small(self):
        from intelnexus.core.llm.core import _is_small_model
        assert _is_small_model("") is False
        assert _is_small_model(None) is False
