"""Tests for custom model CRUD: update_custom_model rename behavior."""

import pytest


@pytest.fixture
def models_file(tmp_path, monkeypatch):
    """Redirect CUSTOM_MODELS_FILE to a temp location and seed two models."""
    import intelnexus.core.llm.models as models

    target = tmp_path / "custom_models.json"
    monkeypatch.setattr(models, "CUSTOM_MODELS_FILE", str(target))
    # base_url 安全校验含 DNS 解析，离线测试环境直接放行
    monkeypatch.setattr(models, "_base_url_guard_ok", lambda url: True)
    models._ensure_custom_models_file()
    assert models.add_custom_model("m-a", "openai", {
        "model_name": "gpt-a", "base_url": "https://a.example.com", "api_key": "sk-a",
    })
    assert models.add_custom_model("m-b", "openai", {
        "model_name": "gpt-b", "base_url": "https://b.example.com", "api_key": "sk-b",
    })
    return models


class TestUpdateCustomModelRename:
    def test_rename_success(self, models_file):
        models = models_file
        assert models.update_custom_model("m-a", "openai", {
            "model_name": "gpt-a2", "base_url": "https://a.example.com", "api_key": "sk-a",
        }, new_name="m-renamed")
        names = models.get_custom_model_names()
        assert names == ["m-renamed", "m-b"]
        cfg = models.get_model_config("m-renamed")
        assert cfg["config"]["model_name"] == "gpt-a2"

    def test_rename_to_existing_name_rejected(self, models_file):
        models = models_file
        assert not models.update_custom_model("m-a", "openai", {
            "model_name": "gpt-a", "base_url": "https://a.example.com", "api_key": "sk-a",
        }, new_name="m-b")
        # 原条目不被破坏
        assert models.get_custom_model_names() == ["m-a", "m-b"]

    def test_empty_new_name_keeps_name(self, models_file):
        models = models_file
        assert models.update_custom_model("m-a", "openai", {
            "model_name": "gpt-a", "base_url": "https://a.example.com", "api_key": "sk-a",
        }, new_name="   ")
        assert models.get_custom_model_names() == ["m-a", "m-b"]

    def test_same_name_no_op_rename(self, models_file):
        models = models_file
        assert models.update_custom_model("m-a", "openai", {
            "model_name": "gpt-a", "base_url": "https://a.example.com", "api_key": "sk-a",
        }, new_name="m-a")
        assert models.get_custom_model_names() == ["m-a", "m-b"]

    def test_update_missing_model_fails(self, models_file):
        models = models_file
        assert not models.update_custom_model("no-such", "openai", {
            "model_name": "x", "base_url": "https://x.example.com", "api_key": "sk-x",
        }, new_name="whatever")
